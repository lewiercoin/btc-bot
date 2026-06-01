# AUDIT: PAPER_PERFORMANCE_VALIDATION_V1

Date: 2026-06-01
Auditor: Claude Code
Builder: Codex
Builder report: `docs/analysis/PAPER_PERFORMANCE_VALIDATION_V1_2026-06-01.md`
Commit audited: `680af2d` on `deploy/multi-asset-paper-v1`
Audit branch: `claude/epic-darwin-z8Moa`

## Verdict: DONE

Codex's report is methodologically clean, follows the pre-declared decision rule honestly, and surfaces a finding that is more important than the verdict label suggests. The report itself is approved.

The **finding** it surfaces — that the deployed runtime is not running the parameters of the candidate we promoted — supersedes the paper-performance question entirely. The blueprint foundations audit asked "is the deployed edge real in live conditions?" Codex's answer is: *we cannot answer that question, because the deployed thing is not the edge we audited.*

## Core Audit Axes

| Axis | Status | Note |
|---|---|---|
| Layer Separation | PASS | Read-only SSH query, no production writes, no settings or code changes |
| Contract Compliance | PASS | All 4 tables queried; pre-declared rule applied verbatim |
| Determinism | PASS | Query commands listed, server commit `1797a209` pinned, timestamps recorded |
| State Integrity | PASS | No process restart, no DB writes, no local file modifications |
| Error Handling | PASS | Verdict explicitly handles the small-sample case via pre-declared rule |
| Smoke Coverage | PASS | Funnel, lineage, infra-health all checked; not just headline metrics |
| Tech Debt | LOW | No new debt added; existing debt named (websocket, lineage) |
| AGENTS.md Compliance | PASS | Read-only contract honored, no scope creep |
| Methodology Integrity | PASS | Refuses to claim overfit conclusion from N=1; refuses to claim validation; small-sample inconclusive verdict is the correct stance |
| Reproducibility & Lineage | PASS | Server commit, profile name, parameter values all recorded |
| Data Isolation | PASS | Source DB treated as read input |
| Artifact Consistency | PASS | Report numbers cross-check against funnel + lineage table |
| Boundary Coupling | PASS | No live-path coupling |

## Critical Issues surfaced by this audit

The report itself is sound. What it found is not. Three issues require action before resuming any edge discovery work.

### Critical 1: Config lineage break

The deployed runtime profile is `experiment`, with BTC `min_sweep_depth_pct=0.005` and ETH/SOL overrides at `0.0075`. Frozen trial-00095 has `min_sweep_depth_pct=0.00649` (BTC-only baseline, no ETH/SOL overrides defined).

The single executed trade had `sweep_depth_pct=0.0051487`. **This trade would have been rejected by frozen trial-00095** (0.0051 < 0.00649). It is not a trial-00095 fill. It is an experiment-profile fill.

Implication: the 2026-05-08 chain — `AUDIT_WF_TRIAL_00095` → `AUDIT_DEPLOYMENT_TRIAL_00095` → `PROMOTION_READY` — promoted candidate `optuna-default-v3-trial-00095`. What is running in production is something else. Either the experiment profile must be brought into alignment with frozen trial-00095 parameters, or the deployed candidate must be re-identified and re-promoted under its actual parameter set.

The earlier `AUDIT_DEPLOYMENT_TRIAL_00095_2026-05-08.md` recorded "Codex correctly used DB values as authoritative source" and treated the discrepancy as a documentation issue. That audit's tolerance for parameter drift in the deployment audit is **the original sin**. The deployment audit should have either rejected the deployment until parameters matched the promoted candidate, or it should have promoted a different candidate identity. It did neither.

This finding **partially invalidates Risk 1 of the foundations audit**. The paper performance question is unanswerable not because we lack data, but because the data we have is from a different system than the one we audited.

### Critical 2: Trade frequency is 3-5× below historical

| Source | Trades | Window | Trades / month |
|---|---:|---|---:|
| trial-00095 WF reference | 271 | ~50 months (2022-01 → 2026-03) | ~5.4 |
| ETH transfer | 544 | ~50 months | ~10.9 |
| SOL transfer | 1,201 | ~50 months | ~24.0 |
| Production PAPER, BTC | 1 | 8 days DB coverage | ~3.8 |
| Production PAPER, ETH | 0 | 8 days | 0 |
| Production PAPER, SOL | 0 | 8 days | 0 |

The active profile uses a **lower** BTC threshold (0.005 vs 0.00649) than frozen, which should produce **more** signals, not fewer. Yet realized frequency is below historical pace, and ETH/SOL produced zero trades despite their historical rates being 2-5× higher than BTC.

The decision funnel makes this concrete:
- BTC: 763 cycles, 1 signal_generated, 432 `sweep_too_shallow`, 318 `no_sweep`
- ETH: 763 cycles, 0 signals, 647 `no_sweep`, 110 `sweep_too_shallow`
- SOL: 763 cycles, 0 signals, 713 `no_sweep`, 42 `sweep_too_shallow`

ETH and SOL are showing `no_sweep` ratios of 85% and 93% respectively, against BTC's 42%. The historical attribution showed ETH at 11.6× BTC trade frequency. The runtime is showing the opposite ordering. Something in sweep detection or input data for ETH/SOL is materially different from the offline backtest snapshots.

This is not a strategy issue. It is either a feature-engine port issue or a data-feed issue. The 429 rate-limit failures (Critical 3) are a candidate explanation but not yet proven to be the full explanation.

### Critical 3: 429 rate-limit failures concentrated on ETH/SOL

14 symbol_cycle_failed events, all Binance HTTP 429 on `/fapi/v1/aggTrades` and `/fapi/v1/klines`. Distribution: ETHUSDT 6, SOLUSDT 8, BTCUSDT 0.

The Binance error response explicitly recommends WebSocket. The `MULTI_ASSET_WEBSOCKET_V1` milestone exists in `READY_FOR_AUDIT` state and has not been deployed. Multi-asset PAPER is running on REST polling that is hitting rate limits, and the failures are biased toward exactly the symbols that are also showing anomalous `no_sweep` rates.

This is not the only candidate cause for Critical 2, but it must be eliminated before any other cause is investigated.

### Critical 4 (subordinate): Production DB coverage starts 2026-05-24, BTC PAPER deployed 2026-05-08

The deployment record is `DEPLOYMENT_TRIAL_00095_PAPER_2026-05-08.md`. The production DB's first decision cycle is `2026-05-24T16:45:00`. That is a 16-day gap. Either:
- The DB was reset/rotated on or around 2026-05-24 (and prior trade evidence is lost or archived elsewhere), or
- BTC PAPER was inactive for 16 days post-deployment, or
- The earlier deployment was on a different DB path.

This must be reconciled. If 16 days of BTC PAPER fills exist somewhere else, they materially expand the sample for Risk 1 evaluation.

## Warnings (fix soon)

5. Codex's verdict label `INCONCLUSIVE_WAIT_WITH_CONFIG_LINEAGE_BLOCKER` is correct, but the operational implication is stronger than "wait." Resuming any multi-asset transfer or new edge discovery work **before** Critical 1 is resolved would be building further on a foundation that the original deployment audit failed to validate.

## Observations (non-blocking)

6. The single closed trade had a credible signal profile: OI z-score 3.93 (extreme), TFI 0.59 (aligned), funding percentile 84.9, confluence 6.85, LONG, uptrend regime, TP exit. This trade looks like a textbook trial-00095-style signal *in shape*. It just doesn't satisfy the frozen threshold.
7. `daily_metrics` has only 9 rows for a 9-day window — daily metrics are being computed, so observability infrastructure works.
8. `decision_outcomes` has 2,289 rows — the decision audit trail is rich. That table is the right place to do a fuller RCA on Critical 2.

## Recommended Next Step

**Milestone: `CONFIG_LINEAGE_RECONCILIATION_V1`.** Single milestone, covers Criticals 1, 2, 3, 4 sequentially.

Phased deliverables, in strict order:

**Phase A — Reconcile (auditor + ops; no code).**
- Decide identity: is the deployed system "frozen trial-00095" or "experiment-profile-derived-from-trial-00095"? If the former, change the experiment profile to match frozen parameters and redeploy. If the latter, give the deployed configuration its own candidate ID, run its own WF validation, and audit it as a fresh promotion.
- Reconcile the 2026-05-08 → 2026-05-24 DB coverage gap. Find or rule out the 16 days of missing history.

**Phase B — Deploy `MULTI_ASSET_WEBSOCKET_V1` (audit pending → deploy).**
- I audit the existing `READY_FOR_AUDIT` milestone. If it passes, deploy. This removes Critical 3 as a candidate explanation for Critical 2.

**Phase C — RCA on trade frequency (builder query; no code).**
- After WebSocket deploy, observe for 7 days. If ETH/SOL `no_sweep` rates remain above 80%, run a comparison between offline backtest sweep detection rates (which historically produced 544 ETH trades / 1,201 SOL trades) and runtime sweep detection rates against the same input data. Determine whether the feature engine in production matches the backtest harness.

**Phase D — Resume Risk 1 (paper performance validation).**
- Only after Phases A-C are complete and observation has accumulated 10+ closed trades per active symbol on **known lineage**, re-run `PAPER_PERFORMANCE_VALIDATION_V2` against frozen trial-00095 reference and apply the foundation decision rule.

What is **not** the next step:
- `TRIAL_00095_MULTI_ASSET_TRANSFER_FEASIBILITY_V1` — premature; transfer to ETH/SOL was already audited and passed offline, and the live runtime is the failing link.
- Any new hypothesis or diagnostic on a different edge — the current edge has not been validated in production yet.
- New OANDA work — closed.

## Decision

Codex's report is approved. The blueprint is sound; the **deployment chain that connects the validated blueprint to the live runtime is broken** at the configuration-lineage layer. Fix the chain before searching for new edges.
