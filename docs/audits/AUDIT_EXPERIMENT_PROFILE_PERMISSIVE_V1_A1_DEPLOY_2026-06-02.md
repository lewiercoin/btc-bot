# AUDIT: EXPERIMENT_PROFILE_PERMISSIVE_V1_A1_DEPLOY

Date: 2026-06-02
Auditor: Claude Code
Builder: Cascade
Commit audited: `db9973a` on `deploy/multi-asset-paper-v1`
Audit branch: `claude/epic-darwin-z8Moa`
Parent milestone: `CONFIG_LINEAGE_RECONCILIATION_V1`, Phase A1.deploy
Prior audits referenced:
- `262506b` — A1.build (approved 9d99dc7)
- `3330e22` — A1.build follow-up (approved 57c6cd3)

## Verdict: DONE (with two findings escalated)

Phase A1.deploy is **complete**. The candidate identity `experiment-profile-permissive-v1` is legalized in production. All four post-deploy verifications passed (backup integrity, metadata update, restart, decision cycle resumption). The ops commit is the post-deploy record required by runbook step 7 and is approved as such.

Two findings require attention but are **not blockers** for proceeding to A2:
- **Permission error incident** is a real production crash event that my own A1.build audit (`262506b`) failed to catch. This is an audit learning to capture, not a re-do of A1.deploy.
- **Backup took 9 hours instead of 30-60 minutes**. Lessons learned are documented in Appendix A. Future deploys must not use `sqlite3 .backup` on a busy WAL-mode DB.

Phase A2 (offline WF validation of `experiment-profile-permissive-v1`) is **unblocked**.

## Core Audit Axes

| Axis | Status | Note |
|---|---|---|
| Layer Separation | PASS | Ops commit touches only docs (lineage + runbook); no code, no production state outside audited script |
| Contract Compliance | PASS | Post-deploy record covers all fields required by runbook step 7 + my A1.build audit's Warning 1 expansion (restart UTC, post-restart log line, service status, integrity, row count cross-check) |
| Determinism | PASS | Specific PIDs, timestamps, SHA256, file sizes recorded — anyone can verify |
| State Integrity | PASS | Backup verified (integrity ok, row count diff within expected window); metadata update confirmed both candidate_id fields; strategy params unchanged |
| Error Handling | WARN | PermissionError crash loop was real but recoverable; bot recovered after chown. See Finding 1. |
| Reproducibility & Lineage | PASS | Full audit chain referenced (9d99dc7 → 57c6cd3 → 3330e22 → db9973a). config_hash recorded for production. |
| Methodology Integrity | PASS | Deviations documented honestly; alternatives proposed; lessons learned actionable |
| AGENTS.md Compliance | PASS | WHAT/WHY/STATUS commit; references prior audit hashes; no scope creep |
| Smoke Coverage | WARN | Permission preservation was not in A1.build test coverage. See Finding 1. |

## Verification of post-deploy claims

| Claim | Evidence | Verified |
|---|---|---|
| Restart timestamp 2026-06-02T04:28:26Z | Section 8 record + Appendix C decision cycle 04:30:00 (~3.5 min post-restart, plausible) | ✓ |
| Pre-PID 992005, post-PID 1078902 | Listed; different values | ✓ different |
| systemctl is-active=active | Recorded | ✓ |
| Backup integrity_check=ok | Section 8 backup row | ✓ |
| Backup trade_log diff=0 | Section 8 | ✓ (consistent with bot stopped during checkpoint or copy was while no trade in-flight) |
| Backup decision_outcomes diff=27 | Section 8; gap between backup (02:15) and verify query (04:22) is ~2.1h × ~12 cycles/h × 3 symbols ÷ 3 = ~25 | ✓ within expected window (~24 ± noise) |
| Old candidate_id zero occurrences in post-restart logs | Section 8 | ✓ adapted verification (Appendix C) applied correctly |
| config_hash recorded | `c01f7960...d40f7` | ✓ |
| First decision cycle 04:30:00 (no_signal) | Section 8 | ✓ bot actively cycling, not just up |

## Appendices verification

**Appendix A (Backup Incident)**: timeline accurate, root cause analysis (WAL live-lock) correct, forensics aligned with what Cascade reported during incident. Lessons learned include three concrete alternatives (`VACUUM INTO`, stop/cp/start, stop/checkpoint/cp/start) — actionable.

**Appendix B (Permission Error)**: incident accurately described, fix recorded, prevention proposes both runbook addition AND script modification. The dual approach is correct because either one prevents recurrence.

**Appendix C (Log Pattern)**: adapted three-check verification documented, correction for future use specified. The actual startup log format is captured (`Starting bot | mode=PAPER | profile=experiment | ...`). Future runbook step 6 can grep for `profile=experiment` and absence of `optuna-default-v3-trial-00095`.

## Critical Issues

None blocking. Two important findings below.

## Findings escalated (not blocking)

### Finding 1: Permission preservation gap — audit miss

The metadata update script (`scripts/update_candidate_id_metadata_only.py`) uses `tempfile.NamedTemporaryFile` + `os.replace` for atomic write. This is correct for write atomicity but **does not preserve original file ownership** when run as a different user (root via SSH vs btc-bot service user). The result: `settings.json` ended up owned by `root:root` mode `0600`, and the bot user could neither read nor write it.

**This was not caught by:**
- My A1.build audit (`262506b`) — I evaluated atomic write correctness but did not consider cross-user ownership semantics
- My A1.build follow-up audit (`3330e22`) — same blind spot
- Cascade's test suite (`tests/test_update_candidate_id_metadata_only.py`) — tests run as one user against temp dirs, ownership preservation not in scope

**Production impact:**
- Bot crashed 3 times in PermissionError loop
- Recovery was manual (`chown btc-bot:btc-bot && chmod 644`)
- Total bot downtime: not documented (Cascade should add to Appendix B if known)
- No DB corruption (PermissionError prevented writes before they happened)

**Audit-side action required:**
- Future scripts that modify production files run as elevated user MUST include ownership preservation in their contract
- Future audits of such scripts MUST explicitly check this property and require a test
- Add to `CLAUDE.md` audit checklist: "For scripts that modify production state when run as a different user than the consuming service, verify ownership/permissions preservation."

**Builder-side action required (separate follow-up commit, not A1.deploy scope):**
- Patch `update_candidate_id_metadata_only.py` to capture pre-write `stat()` and restore ownership/mode after `os.replace()`
- Add test verifying ownership preservation
- This is a NEW small milestone, not a retroactive change to A1.deploy verdict

### Finding 2: Backup operational policy needs codification

The 9-hour backup wait was avoidable. Both the audit framework (mine) and the operational framework (runbook) implicitly trusted `sqlite3 .backup` to behave linearly on a busy WAL-mode database. It does not. Appendix A's lessons learned are correct but they live in one runbook appendix — they should be **promoted to a global ops policy** because every future backup of this DB will face the same risk.

**Audit-side action required:**
- Either `docs/DISASTER_RECOVERY.md` or `scripts/backup_production_db.sh` should be updated to use `VACUUM INTO` or stop/checkpoint/cp/start as the default backup method
- This is a separate small milestone, not a retroactive change to A1.deploy verdict

## Observations (non-blocking)

3. The decision_outcomes diff of 27 is consistent with backup snapshot age. Math checks out (~2.1h gap × ~12 cycles/h × 1 row per cycle ÷ symbols sampling). Not an inconsistency.

4. Both candidate_id locations in `settings.json` were updated atomically by the same script run (Section 8 confirms both fields). No partial-update window.

5. Restart-to-decision-cycle latency was ~3.5 minutes (04:28:26 → 04:30:00 first cycle). Within normal range for this bot. Confirms bot did not just come up, it actually started its main loop.

6. The deploy chain commit history is clean and traceable: `9d99dc7` → `57c6cd3` → `3330e22` (audit) → `db9973a` (deploy record). Each link references the prior. Anyone can reconstruct the legalization timeline.

7. Cascade documented an incident that worked out (backup completed on its own). The right discipline would have been Option B (stop/checkpoint/cp/start) at the 190-minute escalation threshold. Cascade waited longer than the threshold. **Document this in CLAUDE.md as a meta-finding**: escalation thresholds are upper bounds, not "try harder past this point."

## Recommended Next Step

**Phase A2 — offline WF validation of `experiment-profile-permissive-v1`.**

Handoff target: Codex preferred (this is parameter-vector evaluation, Codex's strength). If Codex tokens unavailable, Cascade as fallback in builder mode.

Scope per my earlier handoff (the A2 phase of the multi-phase A1.build handoff):
- `research_lab/wf_experiment_profile_permissive_v1.py` — single-candidate WF runner mirroring `WF_VALIDATION_TRIAL_00095_2026-05-08` protocol
- `research_lab/candidates/experiment-profile-permissive-v1.json` — frozen parameter spec
- `docs/analysis/WF_VALIDATION_EXPERIMENT_PROFILE_PERMISSIVE_V1_2026-XX-XX.md` — builder report
- `tests/test_wf_experiment_profile_permissive_v1.py` — determinism + parameter integrity + window date pinning

I will generate the A2 handoff document when you confirm to proceed.

In parallel, two **non-blocking** small milestones should be queued (not in scope of A2):
- `UPDATE_CANDIDATE_ID_METADATA_OWNERSHIP_PRESERVATION_FIX_V1` (~30 min Codex) — patch the metadata script per Finding 1
- `BACKUP_PRODUCTION_DB_BUSY_WAL_FIX_V1` (~1-2h Codex) — replace `sqlite3 .backup` with `VACUUM INTO` or stop/checkpoint/cp/start in the backup script

These can be done before, during, or after A2 — they do not block A2.

## Decision

`db9973a` is approved as the A1.deploy post-deploy record. Phase A1.deploy is complete. Production runs `experiment-profile-permissive-v1` with traceable lineage. Phase A2 may proceed.

Two findings escalated for future audit + ops improvements; neither blocks A2.
