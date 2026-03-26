# AUDIT_006: Config Injection Bugfix + Phase H Research

Date: 2026-03-26
Auditor: Cascade
Commit: (pending — Codex changes unstaged at time of audit)

## Verdict: MVP_DONE

Both deliverables (config injection bugfix + Phase H offline research) meet acceptance criteria.

## Scope

| Deliverable | Status |
|---|---|
| Config injection gap fix (issue #16) | DONE |
| Phase H: analyze_trades.py | DONE |
| Phase H: llm_post_trade_review.py | DONE |
| Smoke tests (injection + research) | DONE |
| No regressions (backtest, orchestrator) | DONE |

---

## Part 1: Config Injection Bugfix

### Problem Statement

27 configuration parameters were defined in `settings.py` dataclasses but never wired to their target engines:
- 5 `RegimeConfig` fields: all ignored (`RegimeEngine(RegimeConfig())`)
- 5 `SignalConfig` fields: only `confluence_min` passed; 4 others ignored
- 5 `GovernanceConfig` fields: cooldown, duplicate level, session hours ignored
- 1 `RiskConfig` field: `high_vol_stop_distance_pct` ignored
- 11 hardcoded values in `signal_engine.py`: 8 confluence weights + 3 thresholds

Bug affected both live (`orchestrator.py`) and backtest (`backtest_runner.py`) paths.

### Fix Verification

#### signal_engine.py — Externalization: PASS

| Field | Default | Used In |
|---|---|---|
| `weight_sweep_detected` | 1.25 | `_confluence_score` |
| `weight_reclaim_confirmed` | 1.25 | `_confluence_score` |
| `weight_cvd_divergence` | 0.75 | `_confluence_score` |
| `weight_tfi_impulse` | 0.50 | `_confluence_score` |
| `weight_force_order_spike` | 0.40 | `_confluence_score` |
| `weight_regime_special` | 0.35 | `_confluence_score` |
| `weight_ema_trend_alignment` | 0.25 | `_confluence_score` |
| `weight_funding_supportive` | 0.20 | `_confluence_score` |
| `direction_tfi_threshold` | 0.05 | `_infer_direction` |
| `direction_tfi_threshold_inverse` | -0.05 | `_infer_direction` |
| `tfi_impulse_threshold` | 0.10 | `_confluence_score` |

All 11 formerly hardcoded values now use `self.config.xxx`. Zero hardcoded literals remain in logic methods.

#### settings.py — Surface Expansion: PASS

- `StrategyConfig`: +21 new fields (5 regime + 5 signal level + 8 weights + 3 thresholds)
- `RiskConfig`: +7 new fields (1 `high_vol_stop_distance_pct` + 6 governance fields)
- All defaults match original hardcoded values exactly.

#### orchestrator.py — Live Wiring: PASS

| Engine | Fields Wired | Before | After |
|---|---|---|---|
| RegimeEngine | 5/5 | 0/5 | 5/5 |
| SignalEngine | 17/17 | 1/6 | 17/17 |
| GovernanceLayer | 9/9 | 4/9 | 9/9 |
| RiskEngine | 10/10 | 8/9 | 10/10 |

#### backtest_runner.py — Backtest Wiring: PASS

Mirrors orchestrator exactly — same field set, same source mappings.

#### smoke_config_injection.py: PASS

- Tests both live bundle AND backtest runner with non-default values
- Verifies end-to-end propagation: `settings → Config → Engine.config`
- 27+ assertions covering all previously dead parameters

---

## Part 2: Phase H Research

### analyze_trades.py (439 lines): PASS

| Feature | Status |
|---|---|
| Closed-trade loading from `trade_log + positions` | DONE |
| Summary metrics (wins/losses/breakeven, expectancy_R, profit_factor) | DONE |
| Hold time stats (avg, median) | DONE |
| Streak analysis (max consecutive wins/losses) | DONE |
| Grouped breakdowns (direction, regime, exit_reason, confluence_bucket) | DONE |
| Top 5 winners/losers with full context | DONE |
| JSON serialization with inf/nan safety | DONE |
| CLI interface (--db-path, --symbol, --start-ts, --end-ts, --limit, --output-json) | DONE |
| UTC normalization on all timestamps | DONE |
| `now_provider` injection for deterministic testing | DONE |

### llm_post_trade_review.py (313 lines): PASS

| Feature | Status |
|---|---|
| Deterministic sample selection (top N winners + losers, deduplicated) | DONE |
| Feature focus with priority ordering | DONE |
| Strict response schema (summary, strengths, weaknesses, parameter_hypotheses, risk_flags, next_actions) | DONE |
| System prompt (offline-only, strict JSON, no live automation) | DONE |
| User prompt packaging (query + analysis + sampled trades + instruction) | DONE |
| JSON output + CLI interface | DONE |
| `now_provider` injection for deterministic testing | DONE |

Design note: Codex implemented this as a **payload builder** rather than an API caller. The module constructs the complete LLM prompt package but does not make HTTP calls. This is the correct approach per AGENTS.md: "LLM is allowed only for research, post-trade analysis, reporting" and must be "offline, auditable, non-blocking".

### smoke_research.py (221 lines): PASS

- Seeds 6 synthetic trades covering: LONG/SHORT, multiple regimes, TP/SL/TIMEOUT exits
- Verifies: trade counts, win/loss/breakeven, PnL sums, streak analysis, breakdown keys
- Determinism assertion: `report.to_dict() == report_repeat.to_dict()`
- LLM package: sample counts, schema presence, system prompt content

---

## Layer Separation: PASS

Research modules import only:
- `settings` (config loading)
- `research.analyze_trades` (intra-package)
- stdlib (`sqlite3`, `json`, `argparse`, `datetime`, `math`, `statistics`, `pathlib`, `dataclasses`)

Zero imports from `core/`, `execution/`, `data/`, `monitoring/`, `backtest/`.

## Contract Compliance: PASS

- `ClosedTradeRecord` fields match `trade_log + positions` schema exactly
- `TradeAnalysisReport` exposes clear input/output types
- `LLMReviewPackage` has well-defined serialization via `to_dict()`
- No cross-import shortcuts

## Determinism: PASS

- `analyze_closed_trades` is deterministic given fixed DB state + `now_provider`
- `build_llm_review_package` is deterministic given fixed DB state + `now_provider`
- Smoke test verifies `report == report_repeat`
- Signal weights/thresholds now configurable but defaults unchanged — existing behavior preserved

## State Integrity: PASS

- Research modules are read-only — no DB writes
- No runtime state mutation
- Config dataclasses are `frozen=True`

## Error Handling: PASS

- Missing timestamps raise `ValueError` with field name
- JSON parse failures return empty dict (graceful)
- `math.inf` / `math.nan` handled in JSON serialization
- DB connection properly closed in `try/finally`

## Smoke Coverage: PASS

| Smoke Test | Result |
|---|---|
| `smoke_config_injection.py` | OK |
| `smoke_research.py` | OK |
| `smoke_backtest.py` | OK (no regression) |
| `smoke_orchestrator.py` | OK (no regression) |
| `compileall` | OK |

## Tech Debt: LOW

No new tech debt introduced.

## AGENTS.md Compliance: PASS

- Deterministic core preserved — no randomness in decision path
- All timestamps UTC and explicitly normalized
- Config parameters externalized and traceable
- LLM usage strictly offline per policy
- Layer separation maintained
- Commit discipline pending (changes unstaged at audit time)

---

## Critical Issues (must fix before next milestone)

None.

## Warnings (non-blocking)

| # | Warning | Severity |
|---|---|---|
| W-1 | `.claude/` directory created by Codex — should be added to `.gitignore` | Low |

## Observations (non-blocking)

| # | Observation | Notes |
|---|---|---|
| O-1 | Governance fields placed in `RiskConfig` (not `StrategyConfig`) | Arguably more correct — cooldowns and DD limits are risk parameters |
| O-2 | `direction_tfi_threshold_inverse` as separate field | Enables asymmetric thresholds (stricter for shorts). Useful for future optimization. |
| O-3 | LLM module is payload builder, not API caller | Better per AGENTS.md ("offline, auditable, non-blocking"). User sends payload manually. |
| O-4 | `ClosedTradeRecord` imported but used only as type annotation in llm_post_trade_review.py | Valid usage — no unnecessary import |

## Resolved Issues

| Issue | Resolution |
|---|---|
| #16 (config injection gap) | Fixed — all 27+ parameters now wired in both live and backtest paths |

## Recommended Next Step

All phases A-H are now MVP_DONE. Recommended options:
1. **Paper trading validation** — run bot on live data in PAPER mode to validate end-to-end
2. **Tech debt cleanup** — address remaining known issues (#1, #2, #4)
3. **Backtest with real data** — use bootstrapped Binance data for first real backtest run
