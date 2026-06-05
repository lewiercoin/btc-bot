# EDGE-LAB MIGRATION MANIFEST
Date: 2026-06-05
Author: Claude Code (architect/auditor)
Source: `btc-bot` @ `deploy/multi-asset-paper-v1` (the REAL architecture; NOT stale `main`)
Target: new independent repo `edge-lab` (private), clean history, clean docs.

> Principle: extract the **dry, strategy-agnostic skeleton** (the plumbing that
> honestly worked), deliberately LEAVE the failed strategy and the contaminated
> documentation/narrative. A naive `git clone + delete signal_engine` re-imports the
> exact mistakes (42-param config, sweep-coupled schema/features, doc drift). Extract
> by this manifest, file-class by file-class — do NOT copy wholesale.

## Legend
- **KEEP** — copy as-is (generic plumbing).
- **GENERALIZE** — copy but strip strategy-specific coupling before first commit.
- **LEAVE** — do NOT copy. Belongs to the dead strategy or the old narrative.
- **AUTHOR-FRESH** — new file written from scratch in edge-lab (no lineage to old).

---

## core/ (11 py)
| File | Action | Note |
|---|---|---|
| `__init__.py`, `models.py` | GENERALIZE | Keep the contract dataclasses; strip sweep/reclaim-specific fields (`sweep_*`, `reclaim_*`) from `MarketSnapshot`/feature models. Models stay strategy-agnostic. |
| `context_engine.py` | KEEP | Session/time-of-day classification — generic. |
| `regime_engine.py` | KEEP (optional) | Generic volatility/regime buckets. Keep as a feature source, not a gate. |
| `risk_engine.py` | GENERALIZE | Position sizing/risk — keep; detach from the 42-param strategy config. |
| `governance.py`, `portfolio_gate.py` | GENERALIZE | Pre-trade gating abstraction — keep the mechanism, drop sweep-specific rules. |
| `execution_types.py`, `funding.py` | KEEP | Generic types + funding data helper. |
| `feature_engine.py` | LEAVE → REBUILD | Sweep/reclaim features baked in. Replace with a thin `FeatureProvider` interface; features are per-edge, authored later. |
| `signal_engine.py` | LEAVE → REPLACE | The dead edge. Replace with a `SignalStrategy` interface (see baseline below). |

## data/ (7 py) — KEEP WHOLESALE
The rare, valuable asset: Binance USD-M REST/WS clients + collectors (candles,
funding, OI, aggtrades/CVD, force_orders). Strategy-agnostic. This is the crown
plumbing. Carry the collectors and the persistence path intact.

## backtest/ (5 py) — KEEP
`replay_loader`, `backtest_runner`, `fill_model`, `performance`. Deterministic
replay harness. GENERALIZE only the `MarketSnapshot` assembly in `replay_loader`
to match the generalized `core/models.py` (no sweep fields).

## execution/ (6 py) — KEEP
Paper/live execution abstraction + bracket logic. Single-leg directional is the
base. (Delta-neutral/multi-leg, if ever pursued, is a deliberate later extension —
not part of the v1 skeleton.)

## storage/ (5 py + schema) — GENERALIZE
KEEP `db.py`, `state_store.py`, `position_persister.py`, `repositories.py`.
`schema.sql`: KEEP all market-data tables (candles, funding, open_interest,
oi_samples, aggtrade_buckets, cvd_price_history, force_orders) and runtime tables
(bot_state, trade_log, executions, positions, runtime_metrics, daily_metrics).
DROP/RENAME any column or table that encodes sweep/reclaim semantics. Migrations:
fold into a single clean baseline schema for edge-lab (no migration history needed
in a fresh repo).

## research_lab/ (104 py) — SELECTIVE (highest-value methodology, heaviest cruft)
**KEEP (the methodology that honestly killed every bad edge):**
- Walk-forward engine + fold-window machinery.
- Control-cohort framework (random / time-shifted / inverse).
- Param registry / search-space governance mechanism.
- Experiment store + deterministic reporting.
- Pre-registration + frozen-gate evaluation pattern.

**LEAVE (all of it):**
- Every `diagnostics/*` tied to a specific strategy (sweep, OANDA, funding-tilt,
  level_scanner, liquidation, regime, volatility…).
- Every blueprint / audit / validation_report describing an old strategy.

## scripts/ (54 py) — SELECTIVE
KEEP operational: data collectors, `run_backtest`, `run_paper`, `run_dashboard`,
backup/DR. LEAVE all strategy-specific (trial monitors, sweep/funding diagnostics,
`kill_test_*`).

## tests/ (102 py) — SELECTIVE
KEEP tests for kept plumbing (data, backtest, execution, storage, replay, fill
model, state recovery). LEAVE strategy-specific tests.

## Top-level
| Item | Action |
|---|---|
| `main.py`, `orchestrator.py` | GENERALIZE — keep the loop/recovery skeleton; remove strategy wiring; depend on the `SignalStrategy` interface. |
| `settings.py`, `settings.json` | GENERALIZE — **hard reset to a minimal config.** No 42-param strategy block. Strategy params live with each edge, capped. |
| `.github/` (CI), `pytest.ini`, `ruff.toml`, `requirements*.txt`, `.env.example`, `.gitignore`, `.python-version` | KEEP — engineering hygiene. |
| `dashboard/`, `monitoring/` | KEEP (optional v1) — generic observability. |
| `AGENTS.md`, `CLAUDE.md`, `CASCADE.md`, `GROK.md` | AUTHOR-FRESH — new agent/operating docs, no old text. |
| `docs/`, `research/`, `deploy/`, `*.service`, `*.timer`, `validation/` | LEAVE — old narrative/deployment. |
| `README.md` | AUTHOR-FRESH |

---

## Hard rules for the extraction (carried forward as discipline, not as files)
1. **Frozen pre-registration** with mechanical gates before every experiment.
2. **Control cohorts** (random/shifted/inverse) mandatory; main must beat all.
3. **Nested walk-forward**: select on training folds, confirm on an untouched holdout.
4. **Parameter cap** per edge (start ≤3); no 42-param search machine.
5. **Docs == reality**: deployed config hash must match documentation. No drift.
6. **Raw artifact > narrative**: verdicts read from JSON, never from a summary doc.
7. **Generator–evaluator split**: builder writes, one auditor evaluates; auditor never rubber-stamps.

These seven are the real inheritance from btc-bot — the only part that worked.
