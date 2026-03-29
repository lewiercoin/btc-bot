## CLAUDE HANDOFF → CODEX

### Checkpoint
- Last commit: `8e48bee` (Strategy Optimization v1 — regime gating, SL redesign, partial exits + trailing)
- Branch: `main`
- Working tree: clean

### Before you code
Read these files (mandatory):
1. `docs/BLUEPRINT_V1.md` — architecture
2. `AGENTS.md` — discipline + your workflow rules
3. `docs/MILESTONE_TRACKER.md` — current status + known issues
4. `core/signal_engine.py` — signal generation (regime whitelist at lines 10-18, direction logic at lines 94-103)
5. `settings.py` — `_default_regime_direction_whitelist()` at lines 17-25

### Milestone: Strategy Optimization v1.1 — Kill SHORT signals + SHORT-side research instrumentation

**Context:** v1.0 optimization brought PF from 0.40 → 0.97, but SHORT side remains 0% WR across both v0 (0/49) and v1 (0/19). Total SHORT losses: -$2,672 in v1. Without shorts, system would be PF ~1.52, +$2,383 profit on 87 days.

SHORT signals are broken because:
1. **CVD bearish divergence / negative TFI as directional authority does not work on 15m BTC** — order-flow signals decay too fast for this timeframe (confirmed by independent literature review).
2. **32/49 original shorts had MFE = $0** — price never moved in their favor. Entry location is where downside is already exhausted.
3. **No trend confirmation** — SHORT fires in uptrends, downtrends, everywhere. Regime gating helped (removed downtrend+SHORT) but uptrend+SHORT still 0/17.

Scope: Two deliverables. Minimal code change.

---

### Deliverable 1: Disable SHORT signals via config

**File:** `settings.py` — `_default_regime_direction_whitelist()`

**What:** Change ALL regime whitelist entries to LONG-only. SHORT is removed from every regime.

**Current:**
```python
def _default_regime_direction_whitelist() -> dict[str, tuple[str, ...]]:
    return {
        "normal": ("LONG", "SHORT"),
        "compression": ("LONG", "SHORT"),
        "downtrend": ("LONG",),
        "uptrend": ("SHORT",),
        "crowded_leverage": (),
        "post_liquidation": ("LONG", "SHORT"),
    }
```

**New:**
```python
def _default_regime_direction_whitelist() -> dict[str, tuple[str, ...]]:
    return {
        "normal": ("LONG",),
        "compression": ("LONG",),
        "downtrend": ("LONG",),
        "uptrend": (),
        "crowded_leverage": (),
        "post_liquidation": ("LONG",),
    }
```

**Key decisions:**
- `uptrend` → empty (no trades). LONG in uptrend had 0% WR in v1 backtest. No evidence of edge.
- `crowded_leverage` → remains empty. 5.3% WR historically.
- All other regimes → LONG only.
- SHORT is not deleted from code — only disabled via config. This preserves the ability to re-enable SHORT if a proper directional model is developed later.

**Acceptance criteria:**
- Backtest produces 0 SHORT trades.
- Zero trades in uptrend regime.
- Zero trades in crowded_leverage regime.
- PF > 1.0 on 87-day range (2026-01-01 → 2026-03-29).
- All existing smoke tests pass.

---

### Deliverable 2: Add diagnostic counters to backtest output

**File:** `scripts/run_backtest.py`

**What:** After running the backtest, print additional diagnostic lines showing signal filtering breakdown. This helps understand how many signals are generated vs blocked at each stage.

Add these counters to the `InstrumentedBacktestRunner` (or extend `BacktestRunner`):
- `signals_generated` (already exists)
- `signals_regime_blocked` — count of signals rejected by regime whitelist
- `signals_governance_rejected` — count of signals rejected by governance
- `signals_risk_rejected` — count of signals rejected by risk engine

Print them in the summary output:
```
signal_funnel: generated=N regime_blocked=N governance_rejected=N risk_rejected=N → trades_opened=N
```

**Implementation:** Override or instrument `run()` in `InstrumentedBacktestRunner` to count rejections at each stage. The existing `_SignalCountingProxy` pattern can be extended.

**Acceptance criteria:**
- `run_backtest.py` output includes `signal_funnel:` line.
- Sum of all funnel stages accounts for all generated signals: `regime_blocked + governance_rejected + risk_rejected + trades_opened = signals_generated` (approximately — some signals may be blocked before reaching later stages).
- No changes to core engine code. Instrumentation is backtest-runner only.

---

### Validation Plan

After implementing both deliverables:

1. **`python -m compileall . -q`** — zero errors.
2. **All existing smoke tests pass** — no regressions.
3. **Backtest rerun:**
   ```
   python scripts/run_backtest.py --start-date 2026-01-01 --end-date 2026-03-29 --output-json logs/backtest_opt_v1_1.json
   ```
   Expected:
   - 0 SHORT trades
   - 0 uptrend trades
   - PF > 1.0
   - PnL positive (estimated ~+$2,000-2,500)
   - `signal_funnel:` line in output
4. **Compare with v1.0:** Report the before/after table.

---

### Known Issues (from Claude Code audit)

| # | Issue | Blocking? |
|---|---|---|
| 1 | Layer leak: state_store imports from core engines | NO |
| 2 | FeatureEngine internal deques break reproducibility | NO |
| 4 | Execution engines import from storage.repositories | NO |
| — | `weight_regime_special` dead parameter in SignalConfig | NO — cosmetic, leave for now |

None are blocking. Do NOT mix these fixes into this milestone.

---

### Commit discipline
- WHAT / WHY / STATUS in every commit message
- One commit for both deliverables (small scope, atomic change)
- Do NOT self-mark as "done" — Claude Code audits after push

### Your first response must contain:
1. Confirmed milestone scope (what you will implement)
2. Acceptance criteria (how we know it's done)
3. Which known issues are in-scope vs out-of-scope (with reasoning)
4. Implementation plan (ordered steps)
5. Only then: start coding
