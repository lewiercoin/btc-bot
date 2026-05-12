# BTC Bot Decisions Log

This file records operator decisions and their rationale. It is not a live status
document. Runtime facts live in the production database and should be checked with
`python scripts/db_status.py` on the production server.

## 2026-04-09 — Preserve the restored signal-engine edge
**Decision:** Keep the restored signal architecture as the baseline edge and do not casually rewrite `core/signal_engine.py`.

**Reason:** `docs/MILESTONE_TRACKER.md` records that later signal rearchitecture broke the observed edge and that the system was restored to the `8f2c6f2` signal-era behavior with `min_hits=3`. The important architectural decision was to preserve the sweep/reclaim confluence model where direction comes from flow/regime context rather than from sweep side alone.

**Consequences:** Future strategy work must be research-only first. Changes to signal semantics require explicit evidence and audit, not threshold tuning or opportunistic edits.

**Related:** `docs/MILESTONE_TRACKER.md` SIGNAL-REVERT-V1 notes; `8f2c6f2` is referenced there as the restored signal-era baseline. The literal commit `8f2c6f2` in git is a later walk-forward snapshot cleanup commit, so this reference should be treated as historical project shorthand and rechecked before any code revert.

## 2026-04-13 — Trial #63 approved for paper, not permanently canonical
**Decision:** Trial #63 was approved for paper trading as a candidate at that time, but it is not a permanent source of truth for future optimization.

**Reason:** `docs/MILESTONE_TRACKER.md` records Trial #63 as approved for paper trading on 2026-04-13, with positive walk-forward results. Later data-integrity and market-truth work changed the data contract and exposed that old candidate results should not be conflated with current runtime profiles.

**Consequences:** Trial #63 remains useful for lineage and comparison, but fresh campaigns must explicitly state their data window and protocol. Exact Trial #63 replay must rebuild settings from stored candidate params rather than current `settings.py`.

**Related:** `docs/research_lab/TRIAL_63_FEASIBILITY.md`; trial id `run13-regime-aware-trial-00063`; commit `d245617` referenced as applying Trial #63 params.

## 2026-04-21 — DATA-INTEGRITY-V1 becomes prerequisite for new research
**Decision:** New modeling and optimization work must build on the post-DATA-INTEGRITY data contract.

**Reason:** DATA-INTEGRITY-V1 made decision-path data restart-safe, coverage-aware, and quality-explicit. The milestone added persistent OI/CVD state, feature-quality propagation, and operational visibility, which changed what counts as trustworthy data.

**Consequences:** Research results from before DATA-INTEGRITY are not automatically invalid, but they need revalidation before being used as decision evidence. Future Optuna campaigns must declare whether their source data is pre- or post-DATA-INTEGRITY.

**Related:** `docs/audits/AUDIT_DATA_INTEGRITY_V1_2026-04-21.md`; commit `7ebf2d2`; `docs/MILESTONE_TRACKER.md`.

## 2026-04-27 — Gate A validates Market Truth, not strategy edge
**Decision:** Treat Gate A as validation of the market-truth data layer only.

**Reason:** `AUDIT_GATE_A_VERDICT_2026-04-27.md` records Gate A PASS with 206 quality-ready buckets and complete lineage from market snapshots to feature snapshots to decision outcomes. The same report explicitly states that Gate A validates data infrastructure, not the trading strategy.

**Consequences:** Gate A unlocks further audits and modeling work, but it does not approve a strategy change, a live deployment, or a new parameter campaign by itself.

**Related:** `docs/audits/AUDIT_GATE_A_VERDICT_2026-04-27.md`; branch `market-truth-v3`; commit `e06a3dd` in the audit report.

## 2026-04-27 — MODELING-V1 remains neutral until validation evidence is decision-grade
**Decision:** Keep context filtering in neutral/validation mode until modeling validation produces decision-grade evidence.

**Reason:** `docs/MILESTONE_TRACKER.md` records that MODELING-V1 was implemented after Gate A, but active context blocking was not approved. The later validation checkpoint was partial because volatility telemetry had too much UNKNOWN leakage and the trade sample was too thin for activation.

**Consequences:** Context telemetry can be collected and analyzed, but it must not silently become a live gating layer without a separate activation verdict.

**Related:** `docs/analysis/MODELING_V1_VALIDATION_2026-04-27.md`; `docs/MILESTONE_TRACKER.md`; commit `2dc3112`.

## 2026-04-30 — Reject `min_stop_relief_only` as a promotion candidate
**Decision:** Do not promote `min_stop_relief_only` to paper/live configuration.

**Reason:** The geometry sensitivity Tier 1 runs showed that lowering `min_stop_distance_pct` improved raw expectancy and trade count, but worsened drawdown-normalized performance versus baseline in all tested windows. Slippage stress also showed fragility: at 3x slippage, one tested window collapsed to approximately flat expectancy with materially higher drawdown and longer loss streaks.

**Consequences:** `min_stop_relief_only` remains a research hypothesis only. Any future geometry change must include drawdown-normalized metrics, slippage stress, and audit before promotion.

**Related:** `research_lab/geometry_sensitivity.py`; local generated reports under ignored `research_lab/runs/`; operator/Codex/Claude audit discussion on 2026-04-30. [wymaga weryfikacji operatora]

## 2026-04-30 — NEW_BASELINE_DATE_OPTUNA remains open
**Decision:** Do not start Optuna until the replay data window and protocol are explicitly approved.

**Reason:** Production diagnostics found that the replay tables are not gap-free from 2022-03-09 to 2026-04-17. `aggtrade_15m` has gaps, including a large gap from 2026-03-28 to 2026-04-17, and `open_interest` has a large gap from 2025-06-05 to 2026-01-01 plus later April gaps. The current clean candidate window is `2026-01-01T00:15:00+00:00` to `2026-03-28T21:00:00+00:00`, but that is too short for the default 730/365/365 protocol.

**Consequences:** Optuna must either wait for backfilled/longer data, use an explicitly labeled light protocol, or be deferred until more clean data accumulates. The default protocol must not be applied blindly to an 87-day window.

**Related:** `scripts/db_status.py`; `research_lab/configs/default_protocol.json`; 2026-04-30 production DB diagnostics. [wymaga weryfikacji operatora]

## 2026-04-30 — Runtime state lives in `db_status.py`, decisions live in this log
**Decision:** Do not manually maintain a status document as the source of runtime truth.

**Reason:** Documentation state drifts quickly. Recent diagnostics showed this directly: remembered branch/status context differed from the production server. Runtime facts should be queried from the production database on demand, while documents should preserve stable decisions and rationale.

**Consequences:** Operators and agents should run `python scripts/db_status.py` on production for current facts. This log records why decisions were made, not whether the bot is currently healthy, which branch is deployed, or how many rows are in the database today.

**Related:** `scripts/db_status.py`; `docs/DATA_SOURCES.md`; DOCS-FOUNDATION-V1. [wymaga weryfikacji operatora]

## 2026-05-12 - Keep sweep-reclaim baseline and move to multi-setup research
**Decision:** Keep `optuna-default-v3-trial-00095` as the active PAPER sweep-reclaim baseline. Do not promote any candidate from the constrained grid. Start the next work as research-only `TREND-CONTINUATION-RESEARCH-V1`, with no production behavior change.

**Reason:** The constrained grid around trial-00095 tested 60 combinations and increased trade frequency in several candidates, but every meaningful frequency improvement degraded ER/PF and triggered blocking safety concerns, especially `pnl_sanity_review_required`. This confirms that sweep-reclaim is a bounded liquidity-reclaim / mean-reversion setup, not a clean-trend continuation setup.

**Consequences:** Future work should not try to force sweep-reclaim to trade every market structure. The bot should evolve toward a portfolio of independent, context-specific setups. Each setup must prove edge independently through explicit market-structure hypothesis, deterministic logic, `reasons[]`, standalone backtest, walk-forward validation, safety gates, and audit before it can be integrated through a deterministic multi-setup arbiter.

**Related:** `docs/audits/AUDIT_GRID_SEARCH_TRIAL00095_2026-05-12.md`; `docs/analysis/POST_GRID_PORTFOLIO_PLAN_2026-05-12.md`; `docs/ROADMAP_MULTI_SETUP_ARCHITECTURE.md`; `docs/MILESTONE_TRACKER.md` Multi-Setup Portfolio Architecture section.
