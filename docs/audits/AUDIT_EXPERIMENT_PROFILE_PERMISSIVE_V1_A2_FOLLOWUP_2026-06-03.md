# AUDIT: EXPERIMENT_PROFILE_PERMISSIVE_V1_A2_FOLLOWUP

Date: 2026-06-03
Auditor: Claude Code
Builder: Codex
Commit audited: `d9fad78` on `deploy/multi-asset-paper-v1`
Audit branch: `claude/epic-darwin-z8Moa`
Parent milestone: `CONFIG_LINEAGE_RECONCILIATION_V1`, Phase A2 follow-up (closure of 3 completion gaps from `d09a255` audit)
Prior audits in chain:
- `262506b` — A1.build
- `3330e22` — A1.build follow-up
- `0648c4c` — A1.deploy
- `d09a255` — A2 WF validation PROMOTION_READY_WITH_CONDITIONS

## Verdict: DONE

All three completion gaps from `d09a255` are closed. The candidate `experiment-profile-permissive-v1` is now **PROMOTION_READY** (conditions met). The CONFIG_LINEAGE_RECONCILIATION_V1 chain is complete end-to-end. Paper validation V2 may proceed with this candidate as its reference.

## Verification of three findings closure

### Finding 1: Candidate JSON spec — CLOSED

`research_lab/candidates/experiment-profile-permissive-v1.json` (79 lines) contains all required fields per my A2 audit Finding 1 specification:

| Required field | Present | Value |
|---|---|---|
| `candidate_id` | ✓ | `experiment-profile-permissive-v1` |
| `derived_from` | ✓ | `optuna-default-v3-trial-00095` |
| `frozen_overrides.strategy.min_sweep_depth_pct` | ✓ | `0.005` (BTC default scope) |
| `frozen_overrides.multi_asset.symbol_overrides` | ✓ | ETHUSDT + SOLUSDT both `0.0075` |
| `frozen_overrides.risk.risk_per_trade_pct` | ✓ | `0.005` with source attribution |
| `protocol_hash` | ✓ | `023dc84c...` matches trial-00095 v3 |
| `candidate_config_hash` | ✓ | `68fd6caf...` from A2 run |
| `dataset_lineage.btc.sha256` | ✓ | full `ad8c5e7b...167363bca` |
| `dataset_lineage.btc.server_path` | ✓ | recorded |
| `dataset_lineage.btc.verified_server_local_match` | ✓ | `true` |
| `dataset_lineage.fetch_method` | ✓ | "read-only SSH fetch... followed by local SHA256 verification" |
| `wf_report_path` | ✓ | pointer to A2 report |
| `audit_chain` | ✓ | 6 commits with role + summary per entry |
| `legalization_status` | ✓ | `PROMOTION_READY_WITH_CONDITIONS` (will update after this audit) |

The audit_chain is particularly well-structured — each entry has commit hash, role (builder/auditor), and one-line summary. Future paper validation V2 can read this single JSON to reconstruct the entire promotion lineage without grep'ing markdown.

### Finding 2: Revalidation artifact SHA256 — CLOSED

Report addition (37 lines added to `WF_VALIDATION_EXPERIMENT_PROFILE_PERMISSIVE_V1_2026-06-02.md`) lists SHA256 of all four canonical revalidation artifacts:

| Artifact | SHA256 |
|---|---|
| `evaluation.json` | `19fc9579...8a08f9` |
| `recommendation.json` | `670a0807...e66ee5d` |
| `summary.json` | `35d1c660...d97291` |
| `walkforward_report.json` | `d08e713d...95d9830` |

These are the actual metric sources. Any future re-run on the same snapshot + same protocol + same overrides MUST produce identical SHAs. Tampering, drift, or methodology change becomes detectable.

### Finding 3: Determinism evidence — CLOSED via Option (b)

Codex chose Option (b) from my Finding 3 — documented inheritance from existing pipeline tests instead of writing a new candidate-specific determinism test. The three referenced tests are real and verified present:

| Test | File:line | What it asserts |
|---|---|---|
| `test_config_hash_deterministic` | `tests/test_config_hash_reproducibility.py:139` | Identical settings → identical config_hash |
| `test_run_walkforward_applies_multicriteria_thresholds` | `tests/test_research_lab_smoke.py:1706` | `run_walkforward()` persists `hash_protocol(protocol)` into report |
| `test_protocol_hash_persists_through_store_and_report` | `tests/test_research_lab_smoke.py:1919` | Protocol hash persists through trials, walk-forward reports, recommendations, generated reports |

Plus the candidate-specific anchors (protocol_hash, candidate_config_hash, snapshot SHA) are restated in the determinism section as the deterministic identifiers for THIS specific run.

This is acceptable as Option (b) per my A2 audit. The inheritance is real, the tests exist, the anchors are pinned. No drift risk introduced.

## Core Audit Axes

| Axis | Status | Note |
|---|---|---|
| Layer Separation | PASS | Only docs + candidates spec; no production touch; no code in core/execution |
| Contract Compliance | PASS | All 3 completion gaps closed per A2 audit specification |
| Determinism | PASS | Inheritance from pre-existing audited pipeline tests; candidate-specific anchors pinned |
| State Integrity | PASS | No production state modified |
| Reproducibility & Lineage | PASS | Spec JSON + revalidation SHAs + protocol hash + dataset SHA + config hash all in repo |
| Methodology Integrity | PASS | No methodology changes, no new metrics, scope held |
| AGENTS.md Compliance | PASS | WHAT/WHY/STATUS in commit; references prior audit hash; no scope creep |

## Critical Issues

None.

## Observations (non-blocking)

1. ETH and SOL dataset_lineage in the candidate spec record only `sha256_prefix` (first 8 chars), not full SHA256. The rationale ("runtime multi-asset lineage reference" — these are not the WF validation dataset) is defensible since A2 only used BTC snapshot for the WF run. However, full SHAs were already provided by Codex in the first-response confirmation (ETH `C0358A15B5EE661A683E8BF6BFDBA50C98563D0C4B09D4C31CCF47D45D3244FB`, SOL `F994D98FF996367B1F2C0F229D2B9F34228A7136F302E9695FF5513FF2BF06D5`). Recording full SHAs would be marginally better for tamper detection on those snapshots. Not blocking; can be tightened in a future cleanup if needed.

2. The pytest local-environment workaround (`-o addopts=''` because local venv lacks `pytest-cov`) is a Codex-side workflow issue, not an audit concern. The tests passed when run. The production CI presumably runs with full pytest config. Worth noting in case future Codex runs need the same workaround.

3. The `legalization_status` field in the candidate spec is set to `PROMOTION_READY_WITH_CONDITIONS` based on the audit prior to this one. After this audit closes the conditions, the field should be updated to `PROMOTION_READY`. This is a tiny one-line update — can be handled in the first follow-up commit that needs to modify this file (e.g., the paper validation V2 milestone, which would add `paper_validation_v2_status` and bump `legalization_status` simultaneously). Or done now as a single-line PR. Not blocking.

## Status update: candidate is now PROMOTION_READY

The candidate `experiment-profile-permissive-v1` has now completed the full CONFIG_LINEAGE_RECONCILIATION_V1 chain:

```
9d99dc7 (A1.build)
  └─ 3330e22 (audit DONE with 2 warnings)
57c6cd3 (A1.build follow-up addressing warnings)
  └─ 0648c4c (audit DONE)
db9973a (A1.deploy ops record)
  └─ 0648c4c (audit DONE with 2 findings escalated)
5cec9a0 (A2 WF validation)
  └─ d09a255 (audit PROMOTION_READY_WITH_CONDITIONS with 3 gaps)
d9fad78 (A2 follow-up closing 3 gaps)
  └─ this audit: DONE
```

Production runtime is the candidate. WF reference is the candidate's own (not trial-00095's). All lineage breaks from the 2026-05-25 manual settings drift are resolved. The candidate has its own promotion record, traceable from a single JSON spec file.

## Recommended Next Step

**`PAPER_PERFORMANCE_VALIDATION_V2`** with `experiment-profile-permissive-v1` as the reference (replacing trial-00095 v3).

This is the original Risk 1 from `AUDIT_BLUEPRINT_FOUNDATIONS_V1` — "production PAPER performance not audited; decisive evidence unread." With legalized lineage in place, this audit becomes meaningful for the first time.

Caveat: paper trade frequency was 1 trade per ~8 days for BTC in the first PAPER_PERFORMANCE_VALIDATION_V1 window. Reference rule from foundations: "<10 trades per asset → INCONCLUSIVE_WAIT." At current frequency, reaching 10 trades per asset on BTC could take ~80 days. ETH/SOL had 0 trades.

This is its own gating problem. Two paths forward, both legitimate:

**Path A — Wait for paper accumulation, run V2 when ≥10 trades/asset.**
Cost: weeks to months of wait. Risk: deployed system is the cornerstone but its real-world behavior remains unverified.

**Path B — Run V2 sooner with relaxed sample-size verdict.**
Define an intermediate verdict tier (e.g., `EARLY_SIGNAL` for ≥3 trades/asset) that reports observed metrics without claiming statistical significance. Use it as a directional sanity check, not a promotion gate. Cost: lower confidence per run. Benefit: faster feedback loop, can re-run V2 quarterly as data accumulates.

**My recommendation: Path B, with explicit confidence tiers.** Production lineage is now sound; waiting indefinitely for statistical significance leaves the foundation's Risk 1 open longer than necessary. A staged validation with explicit tier reporting is the same discipline pattern as `MVP_DONE` vs `DONE` — it acknowledges incomplete evidence while providing forward visibility.

Decision is the user's. Whichever path, the milestone after that is independent: **`COST_MODEL_AUDIT_V1`** can proceed in parallel since paper validation does not affect cost model calibration directly.

## Parallel queued non-blocking milestones (unchanged from prior audits)

- `BACKUP_PRODUCTION_DB_BUSY_WAL_FIX_V1` (~1-2h Codex) — higher urgency, should run before next backup
- `UPDATE_CANDIDATE_ID_METADATA_OWNERSHIP_PRESERVATION_FIX_V1` (~30 min Codex) — runs whenever; only matters at next metadata-changing script invocation

## Decision

`d9fad78` is approved. The CONFIG_LINEAGE_RECONCILIATION_V1 chain is complete. `experiment-profile-permissive-v1` is PROMOTION_READY. Paper validation V2 is unblocked.

The original blueprint foundations audit Risk 1 ("production PAPER performance not audited") is now actionable for the first time — we have a clean lineage to validate against. Decision on Path A vs B awaits user input.
