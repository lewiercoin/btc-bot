# AUDIT: EXPERIMENT_PROFILE_PERMISSIVE_V1_A1_BUILD_FOLLOWUP

Date: 2026-06-01
Auditor: Claude Code
Builder: Cascade (BUILDER MODE)
Commit audited: `57c6cd3` on `deploy/multi-asset-paper-v1`
Audit branch: `claude/epic-darwin-z8Moa`
Parent milestone: `CONFIG_LINEAGE_RECONCILIATION_V1`, Phase A1.build follow-up
Prior audit: `AUDIT_EXPERIMENT_PROFILE_PERMISSIVE_V1_LINEAGE_LEGALIZATION_A1_BUILD_2026-06-01.md` (commit `262506b`)

## Verdict: DONE

Cascade resolved both warnings raised in the A1.build audit. Warning 1 (runbook restart policy) is fixed by re-titling the section "Service Restart (Mandatory)", adding explicit justification, mandating timestamp capture, adding a post-restart log verification step, and removing the "skip this step" hedge. Warning 2 (monitor script hardcoded identity) is resolved via Option A: `_apply_safe_mode` now takes `candidate_id` as a keyword-only parameter, the call site passes `config["candidate_id"]`, and `main()` exits non-zero with a clear stderr message if `monitoring.candidate_id` is missing. Four new tests cover the dynamic candidate-id behavior and the missing-field failure mode.

Phase A1.deploy is **unblocked** subject to one non-blocking observation about an unverified log-line pattern in the runbook (see Observation 1).

## Core Audit Axes

| Axis | Status | Note |
|---|---|---|
| Layer Separation | PASS | Repo-only commit; touches one script, one test, two docs; no `core/`, `execution/`, `orchestrator/`, no strategy/risk module changes |
| Contract Compliance | PASS | Single commit on `deploy/multi-asset-paper-v1`; both warnings addressed; Option A chosen with one-sentence rationale; no scope creep |
| Determinism | PASS | Explicit settings-path argument; validated config dict; no implicit defaults that would mask missing identity |
| State Integrity | PASS | No production touch; no DB writes outside test fixtures |
| Error Handling | PASS | `main()` returns 1 with stderr message when `monitoring.candidate_id` is missing; private helper raises naturally on bad input via dict access |
| Smoke Coverage | PASS | 4 new tests cover all required cases: dynamic candidate-id in `evaluate()`, different candidate-id propagation, `main()` loud failure on missing field, dynamic candidate-id in output JSON |
| Tech Debt | LOW | Script-filename rename remains explicitly deferred and documented as separate scope; no new debt added |
| AGENTS.md Compliance | PASS | WHAT/WHY/STATUS commit message; single commit; no self-promotion to DONE; builder-mode boundaries respected |
| Methodology Integrity | PASS | Option A chosen explicitly with rationale; Option B rejection documented in lineage doc with reasoning ("one-parameter change with no design risk; deferring would leave the lineage leak open") |
| Promotion Safety | PASS | No promotion claim; candidate remains `AWAITING_WF_VALIDATION` |
| Reproducibility & Lineage | PASS | Lineage doc section 4 updated with Warning 2 Resolution subsection; both runtime-effective and historical table rows reflect the change |
| Data Isolation | PASS | No source-data mutation; tests use temp fixtures |
| Artifact Consistency | PASS | Runbook, lineage doc, script changes, and tests tell the same story |
| Boundary Coupling | PASS | Monitor script touches only `settings.json` reads and SQLite test/production DB writes which are already its scope |

## Verification of changes

**Runbook (Warning 1):**
- Section 6 retitled "Service Restart (Mandatory)" ✓
- Explicit justification added: "The restart IS the deploy." ✓
- Restart command captures UTC timestamp via `date -u '+%Y-%m-%dT%H:%M:%SZ'` ✓
- Added `journalctl --since '5 seconds ago' --no-pager | head -20` post-restart verification ✓
- "If Claude audit requires no restart, skip this step" hedge removed ✓
- Failure-mode language: "If the log line still shows `optuna-default-v3-trial-00095`, stop and investigate" ✓
- Preconditions step 5 added (operator commits to capturing restart timestamp) ✓
- Step 7 post-deploy record expanded to include restart UTC, `systemctl is-active` output, and first post-restart log line ✓

**Monitor script (Warning 2, Option A):**
- `_apply_safe_mode` signature changed from `(conn, *, reason, now, dry_run)` to `(conn, *, reason, now, dry_run, candidate_id)` (line 111) ✓
- Hardcoded `"optuna-default-v3-trial-00095"` literal replaced with `candidate_id` parameter at line 145 ✓
- Sole call site (line 246) passes `candidate_id=config["candidate_id"]` ✓
- `main()` validates `"candidate_id" not in config`, exits 1 with stderr message ✓
- CLI description and source-identifier strings (`"trial_00095_monitor"`) unchanged per handoff ✓
- `evaluate()` already returned `candidate_id` from config — output JSON `candidate_id` field already dynamic by construction. Cascade did not break this. ✓
- Private helper signature change is safe: grep confirms only one caller in the module, no external callers ✓

**Lineage doc:**
- Warning 2 Resolution subsection added (10 lines) ✓
- Runtime-effective table row for `logs/trial_00095_monitoring.json` updated from "Verify after metadata update" to "Resolved in this follow-up commit by reading candidate_id from settings.json at runtime" ✓
- Historical-locations table row for `scripts/monitor_trial_00095.py` updated to "candidate_id payload now reads from `monitoring.candidate_id` in settings.json at runtime" ✓

**Tests:**
- `test_evaluate_reads_candidate_id_from_config` — verifies dynamic ID propagation through `evaluate()` ✓
- `test_evaluate_uses_different_candidate_id` — verifies behavior is data-driven, not literal-driven ✓
- `test_main_fails_loudly_when_candidate_id_missing` — verifies rc != 0 and "candidate_id" in stderr ✓
- `test_main_writes_dynamic_candidate_id_to_output` — verifies end-to-end `main()` flow writes dynamic ID to output JSON ✓
- Test fixtures use temp SQLite with realistic minimal schema (`trade_log`, `bot_state`) ✓

## Critical Issues

None.

## Warnings

None.

## Observations (non-blocking)

### Observation 1: Runbook log-line pattern is unverified against actual bot startup format

Runbook step 6 specifies the expected post-restart verification pattern:

```
deployment.candidate_id = experiment-profile-permissive-v1
```

Cascade did not verify that the bot actually logs this exact line at startup. If the bot logs a different format (e.g., `candidate_id=experiment-profile-permissive-v1`, or `deployment={'candidate_id': 'experiment-profile-permissive-v1', ...}`, or nothing at all), the runbook's verification step will fail in a confusing way — the metadata may be correctly applied but the operator's grep returns nothing.

This is **not blocking** for two reasons:
1. The broader verification logic is sound: post-restart, the journalctl output should somewhere reveal the loaded identity. The operator has SSH and can adjust the grep pattern in real time during A1.deploy.
2. Even if the bot doesn't log the candidate id explicitly, the absence of the OLD id `optuna-default-v3-trial-00095` in the post-restart logs is itself sufficient evidence (combined with the verify-only exit 0 from the metadata updater).

Recommend: during A1.deploy, operator first runs a quick `journalctl -u btc-bot.service --since '2 hours ago' | grep candidate_id` against the currently-running (pre-restart) service to determine the actual log format the bot emits, then adapts step 6 verification accordingly. If no startup log line mentions candidate_id at all, operator should grep for the literal `experiment-profile-permissive-v1` and `optuna-default-v3-trial-00095` separately to confirm new presence and old absence.

This is a small runbook-execution flexibility note, not a code change required before deploy.

### Observation 2: `main()` validates presence but not non-empty value

`main()` validates `"candidate_id" not in config`. It does not validate that the value is non-empty or non-null. If `settings.json` somehow had `monitoring.candidate_id: null` or `monitoring.candidate_id: ""`, the dict key would be present and the check would pass, then `_apply_safe_mode` would receive a falsy value and the test_evaluate_* tests' assertions would not catch this in production.

Risk is theoretical (no path through the updater script creates this state; the updater requires `EXPECTED_ID` as prior value), but tightening to `if not config.get("candidate_id"):` would close the gap.

This is **not blocking**. The audited updater script writes a known target string, so the realistic threat model is null. Worth noting for any future settings hand-edit scenario (which AGENTS.md should also prohibit).

### Observation 3: Restart command robustness

The runbook step 6 restart command:

```
date -u '+%Y-%m-%dT%H:%M:%SZ' && systemctl restart btc-bot.service && sleep 5 && systemctl is-active btc-bot.service
```

If `systemctl restart` fails mid-chain (rare but possible — e.g., unit file is broken), `is-active` will run anyway and may print `failed` or `inactive`. The chain-with-`&&` short-circuits on failure, so this path is handled. ✓

If the bot fails to start (e.g., import error from a missed dependency on the new server commit), `is-active` will return non-zero and the operator sees the failure. The runbook should explicitly state: "If `is-active` returns anything other than `active`, stop and investigate before continuing." Currently it only states the journalctl check should show the new candidate ID. A failure to start would be visible there but the runbook doesn't make this explicit. Worth a small tightening in a future runbook iteration, not blocking for A1.deploy.

## Recommended Next Step

**Proceed to Phase A1.deploy.**

Operator executes the runbook in `docs/operations/EXPERIMENT_PROFILE_PERMISSIVE_V1_DEPLOY_RUNBOOK.md`. The runbook commit at A1.deploy completion must reference both this audit hash (A1.build follow-up audit) and the original A1.build audit hash (`262506b`) in its post-deploy record.

Notes for the operator:
- Have the journalctl command from Observation 1 ready to determine actual log format before invoking the documented grep pattern.
- If `is-active` returns anything other than `active` after restart, stop immediately and post the failure to this audit thread before any further action.
- The DB backup from step 1 is the rollback path. If anything in steps 4-6 produces unexpected state, restore from backup before re-trying.

After A1.deploy completes and is audited, Phase A2 (offline WF validation of `experiment-profile-permissive-v1`) becomes the next milestone. Until then, A2 remains blocked.

## Decision

`57c6cd3` is approved. The follow-up resolves both warnings cleanly. Phase A1.deploy may proceed.
