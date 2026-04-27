# AUDIT: Backtest / Research Lab
Date: 2026-04-24
Auditor: Claude Code
Commit: 2be7a8c

## Verdict: MVP_DONE

## Lookahead Detection: PASS
## Backtest-Production Parity: WARN
## Cost Model Completeness: WARN
## Walk-Forward Methodology: PASS
## Data Split Integrity: PASS
## Replay Capability: PASS
## Research Lab Methodology: PASS

## Findings

### Evidence reviewed
- `backtest/backtest_runner.py` — historical replay engine
- `backtest/fill_model.py` — deterministic fee/slippage simulation
- `backtest/performance.py` — trade metrics summarization
- `backtest/replay_loader.py` — historical data loading
- `research_lab/` — complete research lab module tree (28 files)
- `docs/BLUEPRINT_RESEARCH_LAB.md` — research lab architecture and methodology
- `docs/RESEARCH_LAB_WORKFLOW.md` — two-phase optimization workflow
- `research_lab/param_registry.py` — optimization sandbox registry
- `research_lab/walkforward.py` — walk-forward validation logic
- `research_lab/baseline_gate.py` — hard/soft baseline checks
- `research_lab/approval.py` — approval bundle generation (no auto-promotion)
- Lookahead scan: `grep -rn "\.shift(-"` across backtest/ and research_lab/ returned zero results (only roadmap doc reference)

### Assessment summary
- **Backtest engine is architecturally sound.** `BacktestRunner` uses same core engines as live runtime (`FeatureEngine`, `RegimeEngine`, `SignalEngine`, `GovernanceLayer`, `RiskEngine`). Replay is deterministic and reproducible.
- **No lookahead leakage detected.** Code scan for `.shift(-` (pandas future-indexing pattern) found zero occurrences in production backtest or research lab code. Features are computed from `snapshot` (current bar) with explicit lookback windows.
- **Cost model exists but is incomplete.** `SimpleFillModel` applies deterministic slippage (`slippage_bps_limit=1.0` for LIMIT, `slippage_bps_market=3.0` for MARKET) and fees (`fee_rate_maker=0.0004`, `fee_rate_taker=0.0004`). **Missing: funding fees.** Binance perpetual futures funding is not simulated.
- **Backtest-to-production parity gap exists.** Backtest charges fees via `SimpleFillModel`. Paper runtime charges zero fees (per AUDIT-07). This creates methodology drift: backtest PnL is more conservative than paper PnL.
- **Walk-forward methodology is documented and implemented.** `research_lab/walkforward.py` supports two modes: `post_hoc` (default) and `nested`. Protocol JSON controls mode selection. Walk-forward windows are anchored or rolling, configurable via protocol.
- **Research lab has production-grade separation.** `BLUEPRINT_RESEARCH_LAB.md` explicitly forbids: auto-promotion to `settings.py`, mutation of live path, bypassing approval artifacts. Approval bundle is the end of the automated path; human review is required before candidate application.
- **Parameter sandbox is well-governed.** `param_registry.py` classifies all parameters as ACTIVE (search-eligible), FROZEN (baseline-fixed), DEFERRED (future version), or UNSUPPORTED (not reachable via adapter). This prevents accidental search over frozen architectural parameters like `ema_fast=50`, `ema_slow=200`.
- **Baseline gate prevents broken-pipeline searches.** `baseline_gate.py` runs hard checks (block if baseline is nonsensical) and soft checks (warn if weak but evaluable). This prevents wasting 300 trials on a broken signal engine.

## Critical Issues (must fix before next milestone)
- **Backtest does not simulate funding fees.** Perpetual futures funding rate is applied every 8 hours. For multi-day positions, cumulative funding can be material (0.01%-0.03% per 8h). Backtest PnL overstates net returns by excluding this cost.
- **Backtest-to-paper fee parity broken.** Backtest uses realistic fees (0.04% maker/taker). Paper runtime uses zero fees (per AUDIT-07). When paper trading validates a backtest candidate, PnL will diverge due to missing fee charges. This invalidates paper-as-validation-stage assumption.

## Warnings (fix soon)
- **Partial fill simulation is absent.** `SimpleFillModel` always returns fully-filled executions. Real exchange fills can be partial, especially for limit orders in low-liquidity conditions. Backtest assumes instant full fills.
- **Slippage model is static.** `slippage_bps_limit=1.0`, `slippage_bps_market=3.0` are constants. Real slippage varies with volatility, order size, and liquidity. Backtest may understate execution cost during high-volatility periods.
- **FeatureEngine warmup is acknowledged but not mitigated.** `BacktestRunner` docstring states: "Known limitation (tracked issue #2): each run creates a fresh FeatureEngine. Early bars can have degraded feature values until internal rolling windows warm up." This means first N bars of backtest may have lower-quality features than steady-state bars.

## Observations (non-blocking)
- **Research lab has comprehensive audit artifacts.** Experiment store (`research_lab/research_lab.db`) persists trial lineage, walk-forward reports, recommendations, and Pareto frontier metadata. This enables post-campaign forensics.
- **Two-phase workflow is well-documented.** Phase 1 (Optuna discovery, broad search) → Phase 2 (autoresearch refinement, local optimization). Warm-start filtering by `protocol_hash` and `search_space_signature` prevents cross-protocol contamination.
- **Protocol versioning exists.** `research_lab/protocol.py` computes deterministic `protocol_hash` from date range, walk-forward config, and search space. This enables reproducible campaign comparison.
- **Approval bundle generation is gated by risk.** `approval.py` checks for blocking promotion risks (e.g., too few trades, extreme drawdown) before writing approval artifacts. This prevents accidental promotion of overfitted candidates.
- **Walk-forward degradation threshold is explicit.** Protocol config includes `max_degradation_pct`. Candidates with >threshold degradation are flagged as fragile. This is production-grade risk control.

## Recommended Next Step
After Phase 0 audits complete, add funding fee simulation to backtest (sample funding rate at position open, accumulate funding cost over hold period, deduct from PnL), restore realistic fee charges in paper runtime to match backtest methodology, and document FeatureEngine warmup period (recommend discarding first 200 bars or adding explicit warmup phase before backtest start date).
