# AUDIT: EXPERIMENT_PROFILE_PERMISSIVE_V1_LINEAGE_LEGALIZATION_A1.build

Date: 2026-06-01
Auditor: Claude Code
Builder: Codex
Commit audited: `9d99dc7` on `deploy/multi-asset-paper-v1`
Audit branch: `claude/epic-darwin-z8Moa`
Parent milestone: `CONFIG_LINEAGE_RECONCILIATION_V1`, Phase A1.build
Prior audit: `AUDIT_PAPER_PERFORMANCE_VALIDATION_V1_2026-06-01.md` (commit `8d5c25f`)

## Verdict: DONE (with one warning to address before A1.deploy)

Phase A1.build delivers a complete lineage legalization bundle that does what the handoff required and does it correctly. The bundle is approved for the next phase, conditional on one warning being resolved in or before A1.deploy.

Codex caught and corrected a wrong assumption in my handoff: I specified updating `bot_state.candidate_id` in the production database, but production `bot_state` has no `candidate_id` column. Codex did not silently substitute a schema modification or invent a workaround. Instead it documented the schema reality, identified where the false identity actually lives (`settings.json:deployment.candidate_id` and `settings.json:monitoring.candidate_id`), and adapted the deploy path accordingly. This is the correct response to a flawed handoff.

## Core Audit Axes

| Axis | Status | Note |
|---|---|---|
| Layer Separation | PASS | Repo-only commit, no production touch, no runtime imports, no strategy/risk module changes |
| Contract Compliance | PASS | All 4 required deliverables present; A1.build scope met; A1.deploy and A2 explicitly deferred |
| Determinism | PASS | Atomic JSON write via tempfile+os.replace; `sort_keys=False` preserves settings.json key order; timestamps recorded; explicit constants for `EXPECTED_ID` / `TARGET_ID` |
| State Integrity | PASS | Production state untouched; backup file `settings.json.bak_btc_threshold_` preserved; `config_snapshots` history preserved |
| Error Handling | PASS | Three explicit exit codes (0, 2, 3); refusal on unexpected prior state; refusal on missing schema; `--dry-run`/`--verify-only` mutual exclusion enforced |
| Smoke Coverage | PASS (borderline) | 7 tests cover all required cases including schema-correction case (missing column). JSON-side parity tests could be deeper but the most important property (only `candidate_id` changes, all other fields preserved) is verified |
| Tech Debt | LOW | One tracked debt (monitor script static label) explicitly out of scope and documented |
| AGENTS.md Compliance | PASS | Discipline restored via the bundle itself; commit message follows WHAT/WHY/STATUS; no self-promotion to DONE |
| Methodology Integrity | PASS | Refuses to claim validation; status is `AWAITING_WF_VALIDATION`; explicit non-approval language ("does not approve the profile and does not validate its edge") |
| Promotion Safety | PASS | Bundle does not promote anything; legalizes identity only |
| Reproducibility & Lineage | PASS | Drift incident timeline with second-level precision; backup file evidence; systemd restart timestamps; config snapshot references both pre- and post-drift |
| Data Isolation | PASS | Read-only against production; the backup script invoked in runbook is the project's documented DR procedure |
| Search Space Governance | PASS | No research scope expansion in this milestone |
| Artifact Consistency | PASS | Lineage doc, runbook, script CLI, and tests all reference the same identifiers and exit codes |
| Boundary Coupling | PASS | Updater script has no imports from `core/`, `execution/`, `orchestrator/`, or strategy modules |

## Critical Issues

None.

## Warnings (must address in or before A1.deploy)

### Warning 1 (BLOCKING for A1.deploy): Runbook restart policy is conditional, should be unconditional

Runbook step 6 reads "If runtime logs or monitoring must immediately reflect the new ID, restart the service after the metadata update. If Claude audit requires no restart, skip this step..."

This hedges in the wrong direction. The candidate ID is loaded from `settings.json` at process start. Until the service restarts, the running process continues to emit `optuna-default-v3-trial-00095` in every monitoring write, every log line, every alert. The purpose of this milestone is to stop emitting the false identity from runtime. A metadata update without restart leaves the runtime lying.

Two consequences:
1. Until restart, every monitoring run produces artifacts with the old label, contaminating any downstream paper-performance evaluation.
2. The next unrelated restart (system reboot, deploy of an unrelated milestone, crash) will pick up the new label silently. The change becomes invisible in `journalctl` history because it is not tied to its own audited restart event.

Action: change runbook step 6 to mandate the restart as part of the runbook, not conditional on operator judgment. The restart is the act that makes the metadata change runtime-effective. It is the deploy.

Risk of the restart on PAPER: low. No live capital at risk. WebSocket reconnect is standard service behavior. `multi_asset_position_monitor_symbol_routing_fix_v1` and `paper_simulation_account_foundation_v1` audits both confirm state recovery handles restart cleanly.

### Warning 2 (MEDIUM, can defer if explicitly accepted): Monitor script will continue writing the false identity after A1.deploy

`scripts/monitor_trial_00095.py` line 144 contains a hardcoded payload `{"candidate_id": "optuna-default-v3-trial-00095"}`. Line 142 hardcodes `"trial_00095_monitor"` as the source identifier. The runtime artifact `logs/trial_00095_monitoring.json` is generated by this script.

After A1.deploy, `settings.json` will say `experiment-profile-permissive-v1`, but every run of `monitor_trial_00095.py` will write `optuna-default-v3-trial-00095` into the monitoring log. Codex correctly classified this as "do not modify in A1.build; future monitor rename is separate scope." This is defensible but leaves a lineage leak open after deploy.

Two acceptable resolutions:
1. **Before A1.deploy** add a minimal follow-up commit that updates the monitor script's payload to read candidate ID from `settings.json` at runtime instead of hardcoding it. Lowest-friction option.
2. **After A1.deploy** pause monitor runs (or accept that monitor output retains the legacy label as a noted artifact) until a separate `MONITOR_TRIAL_00095_RENAME_V1` milestone updates the script.

Either resolution is acceptable. What is not acceptable is silently letting the monitor continue writing the false identity into runtime artifacts while reporting that A1.deploy has eliminated the false identity. Pick one explicitly and document it.

## Observations (non-blocking)

3. `risk.risk_per_trade_pct` row in the parameter diff table shows `0.0055` (trial param) vs `0.005` (paper guardrail from 2026-05-08). Cross-checked against `AUDIT_DEPLOYMENT_TRIAL_00095_2026-05-08.md`: the `0.005` guardrail was an approved deployment-time conservative override, not part of the recent drift. Codex's classification is correct.
4. The script supports both JSON and SQLite update paths even though only JSON is used in this deploy. The SQLite path is well-tested and useful for future cases where a `candidate_id` column may exist. Keeping it does no harm.
5. Atomic JSON write via tempfile + `os.replace` is the right pattern. Race-condition window with the running bot is theoretically nonzero, but `settings.json` is not written by the running bot at runtime, so the practical risk is zero on PAPER.
6. Log artifact (`docs/operations/CANDIDATE_ID_UPDATE_<timestamp>.log`) is written to the server's working directory and not auto-committed. The deploy phase commit (runbook step 7) will capture it retroactively. Operator must remember to include the log path artifact in that commit.
7. Discovery section properly distinguishes runtime-effective from historical locations. Historical references in `docs/audits/AUDIT_*TRIAL_00095*` are correctly preserved — they are accurate records of what was promoted on 2026-05-08, not artifacts of the current runtime.
8. The DB coverage gap (2026-05-08 → 2026-05-24) is correctly deferred. It is a parent-milestone concern, not in A1's scope.

## Recommended Next Step

Codex addresses Warnings 1 and 2 in a small follow-up commit on `deploy/multi-asset-paper-v1`:

1. Edit `docs/operations/EXPERIMENT_PROFILE_PERMISSIVE_V1_DEPLOY_RUNBOOK.md` step 6: restart is mandatory, not optional. Document expected log line after restart confirming new candidate ID.
2. Choose one of the Warning 2 resolutions and document the choice in `docs/research/EXPERIMENT_PROFILE_PERMISSIVE_V1_LINEAGE.md` section 4. If resolution (1), include the monitor script update in the same follow-up commit with one additional test.

After that follow-up is audited and approved, A1.deploy proceeds per runbook.

A2 (offline WF validation) is blocked until A1.deploy completes.

## Decision

`9d99dc7` is approved as the A1.build commit. Phase A1.deploy must not begin until the two warnings above are resolved in a follow-up commit and that follow-up is audited.
