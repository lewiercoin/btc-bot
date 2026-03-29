## CLAUDE HANDOFF → CODEX

### Checkpoint
- Last commit: `7b38955` (Add bulk ZIP bootstrap scripts for aggTrades and OI)
- Branch: `main`
- Working tree: clean (1 untracked doc file — irrelevant)

### Before you code
Read these files (mandatory):
1. `docs/BLUEPRINT_V1.md` — architecture
2. `AGENTS.md` — discipline + your workflow rules
3. `docs/MILESTONE_TRACKER.md` — current status + known issues
4. `core/signal_engine.py` — signal generation (direction, levels, confluence)
5. `core/regime_engine.py` — regime classification
6. `core/risk_engine.py` — position sizing, SL/TP exit logic
7. `core/governance.py` — governance filters and cooldowns

### Milestone: Strategy Optimization v1 — Regime Gating + SL Redesign + Partial Exits

**Context:** 87-day backtest (2026-01-01 → 2026-03-29) shows:
- PF = 0.40, expectancy = -1.05R, max DD = 47.8%, Sharpe = -12.46
- 107 trades: 16 wins / 91 losses. Win rate 15%.
- **SHORT: 0 wins in 49 trades (0% WR, -$4,158)**. Structurally broken.
- **LONG: 16 wins in 58 trades (27.6% WR, -$546)**. Close to breakeven.
- 66% of trades last exactly 1 bar (15min) — immediate SL hits.
- Avg loser = -2.07R (should be ~-1R). Fee drag: $3,274 total.
- Higher confluence (4-5) performs WORSE than lower (3-4).
- Losing LONGs had avg MFE = $113 before reversing to SL.
- Regime "uptrend": 6.9% WR. "crowded_leverage": 5.3% WR. Both destructive.

**Full backtest report:** `logs/backtest_full_87d.json`
**Independent research:** `docs/prompts/chatgpt_optimization_research.md` (ChatGPT analysis with literature references)

Scope: Three surgical changes. No new modules. No new features. Modify existing engines only.

---

### Deliverable 1: Regime → Hard Direction Blocker

**File:** `core/signal_engine.py` (generate method) + `core/models.py` (if config model needed)

**What:** After `_infer_direction()` returns a direction, add a regime-direction eligibility check BEFORE confluence scoring. If regime+direction combo is not whitelisted, return `None`.

**Whitelist (initial — configurable via SignalConfig):**

| Regime | LONG allowed | SHORT allowed |
|---|---|---|
| NORMAL | YES | YES |
| COMPRESSION | YES | YES |
| DOWNTREND | YES | NO |
| UPTREND | NO | YES |
| CROWDED_LEVERAGE | NO | NO |
| POST_LIQUIDATION | YES | YES |

**Rationale:**
- DOWNTREND + SHORT = 0% WR (trading with the trend, no reversal edge). Block.
- UPTREND + LONG = 6.9% WR (counter-trend in uptrend, not working). Block.
- CROWDED_LEVERAGE = 5.3% WR both sides. Block all.
- POST_LIQUIDATION = theoretical edge (liquidation cascade reversal). Allow both.
- NORMAL/COMPRESSION = allow both (small sample but positive or neutral expectancy).

**Implementation detail:**
- Add a class-level or config dict: `regime_direction_whitelist: dict[str, set[str]]`
- Default per table above. Must be configurable in `settings.yaml` → `SignalConfig`.
- In `generate()`, after line ~50 (after `direction = self._infer_direction(features)`):
  ```
  allowed_dirs = self.config.regime_direction_whitelist.get(regime.value, set())
  if direction not in allowed_dirs:
      return None
  ```
- Remove the +0.35 confluence bonus for regime (lines ~114-116) — regime is now a gatekeeper, not a score contributor.

**Acceptance criteria:**
- Backtest with same 87-day range produces 0 trades in blocked regime+direction combos.
- Existing smoke tests pass.
- Config is injectable from settings.yaml.

---

### Deliverable 2: Stop-Loss Redesign — Wider SL + Volatility Floor

**File:** `core/signal_engine.py` (`_build_levels` method, ~line 134)

**What:** Change SL placement from `0.25 × ATR` to `0.75 × ATR` with a minimum floor of `0.15%` of entry price.

**Current (broken):**
```python
# LONG
invalidation = base - (atr * 0.25)   # 0.25 × ATR from sweep level
# Effective risk = 0.30 × ATR (because entry is 0.05 × ATR above base)
```

**New:**
```python
# LONG
raw_invalidation = base - (atr * invalidation_offset_atr)  # now 0.75
# Apply volatility floor
min_stop_distance = entry * min_stop_distance_pct            # 0.0015 (0.15%)
actual_stop_distance = max(abs(entry - raw_invalidation), min_stop_distance)
invalidation = entry - actual_stop_distance  # for LONG
invalidation = entry + actual_stop_distance  # for SHORT
```

**Parameter changes in SignalConfig:**
- `invalidation_offset_atr`: 0.25 → **0.75** (default)
- NEW: `min_stop_distance_pct`: **0.0015** (0.15% floor)
- `tp1_atr_mult`: 2.0 → **2.5** (adjust to maintain ~3:1 RR with wider stop)
- `tp2_atr_mult`: 3.5 → **4.0**

**Rationale:**
- 0.25×ATR on 15m BTC ≈ $75-90 — single candle noise. 66% of trades die in 1 bar.
- 0.75×ATR ≈ $225-270 — gives 2-3 bars of breathing room.
- 0.15% floor = ~$105-140 at $70K-$93K BTC — absolute minimum to survive market microstructure.
- TP adjustment maintains minimum RR ratio of 2.8 (governance enforced).
- Wider SL → smaller position size (risk_engine auto-adjusts via `equity * 0.01 / stop_distance`). This is correct — fewer but better-sized trades.

**Acceptance criteria:**
- No trade in backtest has `abs(entry - SL) < entry * 0.0015`.
- Avg loser R should be closer to -1.0R to -1.3R (not -2.07R).
- Fewer 1-bar stop-outs (target: <40% trades lasting 1 bar, down from 66%).
- RR ratio >= 2.8 enforced by governance (existing check).
- Existing smoke tests pass.

---

### Deliverable 3: Partial Exit + Trailing Stop

**Files:** `core/risk_engine.py` (`evaluate_exit`), `core/models.py` (Position model if needed), `backtest/backtest_runner.py` (position tracking)

**What:** Implement two-stage exit:
1. **Partial TP at TP1 (50% of position)** — take profit on half at first target.
2. **Trailing stop on remainder** — move SL to breakeven after TP1 hit, then trail at `1.0 × ATR` below highest high (LONG) or above lowest low (SHORT).

**Current (all-or-nothing):**
```python
# risk_engine.py evaluate_exit
if latest_high >= position.take_profit_1:
    return ExitDecision(True, "TP", position.take_profit_1)  # exits 100%
```

**New logic:**
```python
# After TP1 is hit:
# 1. Close 50% at TP1 price → "TP_PARTIAL"
# 2. Move stop_loss to entry_price (breakeven)
# 3. Trail stop: new_sl = max(current_sl, highest_high - trailing_atr_mult * atr)
# 4. Final exit: trailing SL hit → "TP_TRAIL" or timeout → "TIMEOUT"
```

**Implementation approach (recommended):**
- Add `partial_exit_done: bool` field to Position (or to the backtest's `_OpenPositionRecord`).
- Add `trailing_stop: float | None` field.
- In `evaluate_exit`:
  - If `not partial_exit_done` and TP1 reached → return `ExitDecision(True, "TP_PARTIAL", tp1_price, partial_pct=0.5)`
  - If `partial_exit_done` → check trailing stop instead of fixed TP/SL.
- In `backtest_runner._close_positions_if_needed`:
  - Handle `TP_PARTIAL`: reduce `position.size` by 50%, set `partial_exit_done = True`, move `stop_loss = entry_price`, record partial PnL.
  - Update trailing stop each bar: `trail_sl = max(position.stop_loss, latest_high - trailing_atr * atr_15m)` (for LONG).
- ExitDecision may need a `partial_pct` field or separate `PartialExitDecision`.

**New parameters:**
- `partial_exit_pct`: **0.5** (50% at TP1)
- `trailing_atr_mult`: **1.0** (trail at 1×ATR from swing high/low)
- These go in `RiskConfig` (risk_engine.py).

**Rationale:**
- 40/42 losing LONGs had avg MFE = $113 — price moved favorably before reversing.
- Partial exit at TP1 locks in profit on half the position.
- Trailing stop on remainder captures extended moves (TP2+ potential).
- Breakeven stop after partial eliminates further loss on remainder.
- Winners avg ~+4.73R currently — some might have gone to +7-10R if allowed to run.

**Acceptance criteria:**
- Backtest shows "TP_PARTIAL" and "TP_TRAIL" exit reasons in trade records.
- Avg winner R should increase (runners captured beyond TP1).
- Avg loser R should improve slightly (partial exits on trades that reach TP1 then reverse).
- Position size tracking is correct (partial close reduces size, PnL proportional).
- No trade has negative remaining size or duplicate closes.
- Existing smoke tests pass + new smoke test for partial exit logic.

---

### Known Issues (from Claude Code audit)

| # | Issue | Blocking for this milestone? |
|---|---|---|
| 1 | Layer leak: state_store imports from core engines | NO — not in scope |
| 2 | FeatureEngine internal deques break reproducibility | NO — not in scope |
| 4 | Execution engines import from storage.repositories | NO — not in scope |
| 14 | ReplayLoader N+1 queries (slow backtest) | NO — performance, not correctness |
| 15 | Sharpe uses population variance | NO — cosmetic |

None are blocking. Do NOT mix these fixes into this milestone.

---

### Validation Plan

After implementing all 3 deliverables:

1. **`python -m compileall . -q`** — zero errors.
2. **All existing smoke tests pass** — no regressions.
3. **New smoke test: `scripts/smoke_strategy_opt_v1.py`** — verifies:
   - Regime gating blocks correct combos (e.g., SHORT+DOWNTREND returns None)
   - SL distance >= min_stop_distance_pct * entry_price
   - Partial exit reduces position size correctly
   - Trailing stop updates correctly
4. **Backtest rerun:**
   ```
   python scripts/run_backtest.py --start-date 2026-01-01 --end-date 2026-03-29 --output-json logs/backtest_opt_v1.json
   ```
   Expected improvements (directional, not exact targets):
   - PF > 0.40 (ideally > 0.8)
   - Fewer trades (regime gating removes ~40-50% of trades)
   - Avg loser closer to -1.0R (wider SL, properly sized)
   - Fewer 1-bar stop-outs (<40%, down from 66%)
   - SHORT WR > 0% (or zero SHORT trades if all blocked by gating)

---

### Commit discipline
- WHAT / WHY / STATUS in every commit message
- One commit per deliverable (3 commits total) — allows isolated rollback
- Commit order: Deliverable 1 → 2 → 3 (each builds on prior)
- Do NOT self-mark as "done" — Claude Code audits after push

### Your first response must contain:
1. Confirmed milestone scope (what you will implement)
2. Acceptance criteria (how we know it's done)
3. Which known issues are in-scope vs out-of-scope (with reasoning)
4. Implementation plan (ordered steps)
5. Only then: start coding
