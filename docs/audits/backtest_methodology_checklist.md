# Backtest Methodology Checklist
Date: 2026-04-24
Auditor: Claude Code

## Lookahead Prevention
- ✅ No `.shift(-N)` patterns found in backtest/ or research_lab/
- ✅ Features computed from current `snapshot` with explicit lookback windows
- ✅ `FeatureEngine` uses deques for rolling windows (FIFO, no future access)
- ⚠️ FeatureEngine warmup period not explicitly discarded (first ~200 bars may have degraded features)

## Cost Model
- ✅ Slippage model exists: `slippage_bps_limit=1.0`, `slippage_bps_market=3.0`
- ✅ Fee model exists: `fee_rate_maker=0.0004`, `fee_rate_taker=0.0004`
- ❌ Funding fee model: NOT IMPLEMENTED (perpetual futures funding not simulated)
- ⚠️ Partial fill simulation: NOT IMPLEMENTED (always full fills)
- ⚠️ Slippage is static (does not vary with volatility or liquidity)

## Backtest-Production Parity
- ✅ Same core engines (`FeatureEngine`, `RegimeEngine`, `SignalEngine`, `GovernanceLayer`, `RiskEngine`)
- ✅ Same signal generation logic
- ✅ Same risk sizing logic
- ❌ **Parity broken:** Backtest charges fees (0.04%), paper runtime charges zero fees
- ❌ **Parity broken:** Backtest has no funding fees, paper also has no funding fees (both incomplete)

## Walk-Forward Methodology
- ✅ Implemented in `research_lab/walkforward.py`
- ✅ Two modes supported: `post_hoc` (default) and `nested`
- ✅ Anchored and rolling window modes
- ✅ Degradation threshold tracking (`max_degradation_pct` in protocol)
- ✅ Walk-forward report persisted in experiment store

## Data Split Integrity
- ✅ Train/val/test date ranges explicit in protocol JSON
- ✅ Walk-forward windows non-overlapping in validation phase
- ✅ No data leakage between optimization and validation (Optuna sees train only in nested mode)
- ✅ Warm-start filtering by `protocol_hash` prevents cross-protocol contamination

## Replay Capability
- ✅ `BacktestRunner` is deterministic (same input → same output)
- ✅ `research_lab/workflows/replay_candidate.py` supports re-running stored candidates
- ✅ Trial lineage tracked: `protocol_hash`, `search_space_signature`, `baseline_version`
- ✅ DB snapshot per trial enables exact data reproduction

## Research Lab Governance
- ✅ Parameter sandbox (`param_registry.py`): ACTIVE, FROZEN, DEFERRED, UNSUPPORTED
- ✅ Baseline gate (`baseline_gate.py`): hard checks block broken pipelines, soft checks warn on weak baselines
- ✅ Approval bundle (`approval.py`): gated by blocking promotion risks, no auto-promotion
- ✅ Two-phase workflow documented (`BLUEPRINT_RESEARCH_LAB.md`, `RESEARCH_LAB_WORKFLOW.md`)
- ✅ Audit artifacts persisted (`research_lab/research_lab.db`)

## Overall Assessment
**Methodology is production-grade within its current scope.** Backtest is deterministic, reproducible, and well-governed. Walk-forward validation is sound. Research lab has strong separation and approval gates.

**Critical gaps:** Funding fees not simulated. Backtest-paper fee parity broken. These gaps create paper-to-live transition risk.
