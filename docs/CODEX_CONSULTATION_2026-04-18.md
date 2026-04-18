# CODEX CONSULTATION — 2026-04-18

**Issued by:** External strategy review (institutional daytrading perspective)
**Commit context:** f22c2d7 (RUN14-OVERLAY-FIX — DONE)
**Tracker state:** IDLE — awaiting next milestone
**Scope:** Read-only consultation. No code changes without explicit user approval.

---

## Background

This consultation is the result of an institutional-grade review of the full strategy stack
(signal_engine, regime_engine, risk_engine, feature_engine, settings.py, research_lab protocols,
OPTUNA_UTILITY_REPORT, AUDIT_STRATEGY_ASSESSMENT_2026-04-17). Four independent findings were
identified that materially limit daytrading performance. They are presented below in priority order
with exact code references, proposed fixes, and implementation constraints.

The user must approve each finding before any milestone is opened.

---

## Finding #1 — UPTREND regime blocks all entries (critical)

### Evidence

`settings.py:24–27` — default whitelist:
```python
def _default_regime_direction_whitelist() -> dict[str, tuple[str, ...]]:
    return {
        ...
        "uptrend": (),          # ← zero directions allowed
        ...
    }
```

`signal_engine.py:48–52` (diagnose path):
```python
direction_allowed = self._is_direction_allowed_for_regime(direction=direction, regime=regime)
if not direction_allowed:
    blocked_by = "regime_direction_whitelist"
```

`AUDIT_STRATEGY_ASSESSMENT_2026-04-17.md` (confirmed in production):
- 4 fresh decision cycles: 13:45, 14:00, 14:15, 14:30 UTC → 0 candidates
- Root cause: market in UPTREND, uptrend whitelist = ()
- Counterfactual: even with reclaim=true, uptrend regime blocks entries regardless

The flag `allow_long_in_uptrend: bool = False` exists in `StrategyConfig` and the dispatch
logic in `build_signal_regime_direction_whitelist()` is already wired, but the flag is never
set to True in production settings or any deployed trial.

### Impact

BTC spends the majority of bull-cycle time in UPTREND (ema50_4h > ema200_4h + 0.63%).
Zero entries in this regime means the bot is structurally inactive during the dominant
market condition for a long-biased asset.

### Proposed fix

**Milestone scope:** `settings.py` only — do NOT touch `signal_engine.py` or `regime_engine.py`.

Set `allow_long_in_uptrend = True` in `StrategyConfig` defaults, AND raise `confluence_min`
from 3.6 to a higher value (4.5–5.0 range, to be determined by research) so that uptrend
LONG entries are gated more strictly than reversal entries.

The uptrend gate already requires `sweep_detected=True` AND `reclaim_detected=True` (hard gates
in `signal_engine.py:44–47`) before any confluence scoring runs. Adding `allow_long_in_uptrend=True`
does not loosen these structural gates — it only removes the regime-level veto after they pass.

**This is NOT a general "allow long in uptrend" relaxation.** It is: existing sweep+reclaim gate
remains, existing confluence scoring remains, only the regime whitelist veto is removed for LONG
in UPTREND.

**Research path (recommended before deploy):**
- Open research lab trial with `allow_long_in_uptrend=True`, `confluence_min` swept 4.2–5.5
- Evaluate: does uptrend LONG contribution add expectancy vs Trial #63 baseline?
- Success criterion: overall expectancy_r >= 0.994 (baseline), no degradation of NORMAL/DOWNTREND trades
- Promote only if research confirms edge

**Fast path (if user wants live test):**
- Set `allow_long_in_uptrend=True` + `confluence_min=4.8` in `settings.py`
- Deploy as paper trade for 7 days, compare signal count and outcomes to STRATEGY-ASSESSMENT window
- Revert if no improvement

---

## Finding #2 — sweep_detected fires on ~99.5% of bars (critical)

### Evidence

`feature_engine.py:17–18` (FeatureEngineConfig defaults):
```python
equal_level_tol_atr: float = 0.25
```

With ATR_15m ≈ $175–200 on BTC, tolerance = 0.25 × $200 = $50. A 50-bar 15m window spans
roughly $1,000–$1,500 in range. At $50 tolerance, this produces 4–8 merged low clusters
and 4–8 merged high clusters. Nearly every bar touches at least one cluster.

`feature_engine.py:89–104` — `detect_equal_levels()`:
```python
def detect_equal_levels(levels: list[float], tolerance: float, min_hits: int = 2) -> list[float]:
    ...
    merged = [round(_mean(cluster), 2) for cluster in clusters if len(cluster) >= min_hits]
```

`feature_engine.py:181–182` — current call (note: `min_hits=3` is already hardcoded here,
matching the SWEEP-RECLAIM-FIX-V1 deliverable #2):
```python
equal_lows = detect_equal_levels(lows, tolerance=level_tolerance, min_hits=3)
equal_highs = detect_equal_levels(highs, tolerance=level_tolerance, min_hits=3)
```

OPTUNA_UTILITY_REPORT.md (sweep/reclaim analysis, 2026-04-09):
> "With ATR≈$200 and tolerance=ATR×0.25=$50, a typical 50-bar 15m window produces 4-8 merged
> low clusters and 4-8 merged high clusters. The early-return architecture at feature_engine.py:130
> turns this dense cluster set into sweep_detected=True on 99.49% of bars."
>
> "Optuna learns a threshold offset, not sweep quality, because weight_sweep_detected and
> weight_reclaim_confirmed are constant intercepts once scoring runs."

### Consequence

- `weight_sweep_detected = 2.1` and `weight_reclaim_confirmed = 4.25` in `settings.py`
  (StrategyConfig) act as **constant intercepts**, not evidence weights — they are added
  unconditionally to every candidate that passes the hard gates
- Confluence scoring is therefore systematically inflated by +6.35 on every signal
- `confluence_min = 3.6` is practically measuring only the remaining features (CVD, TFI,
  funding, EMA alignment) — not sweep/reclaim quality

### Proposed fix

**Milestone: SWEEP-QUALITY-V1** (this is the previously planned SWEEP-RECLAIM-FIX-V1 —
verify current implementation status before opening)

Check: has SWEEP-RECLAIM-FIX-V1 already been implemented?

```bash
grep -n "level_min_age_bars\|min_hits" core/feature_engine.py settings.py
```

If not yet implemented, scope is:

1. Add `level_min_age_bars: int = 10` to `FeatureEngineConfig`
   - A cluster qualifies as a level only if the time span between first and last candle
     in the cluster is >= `level_min_age_bars` bars (i.e., ≥150 minutes on 15m TF)
   - Modify `detect_equal_levels()` or `detect_sweep_reclaim()` to enforce this

2. Tighten `equal_level_tol_atr` default to 0.12–0.15 (from current 0.25)
   - This narrows cluster merging to ±$21–$27 at ATR=$175, producing significantly fewer
     but more structurally meaningful levels

3. Add both to `param_registry.py` as ACTIVE:
   - `level_min_age_bars`: int, range 5–20, step 1
   - `equal_level_tol_atr`: already ACTIVE (confirm range is tightened to 0.08–0.20)

4. Smoke test gate: `sweep_detected` rate must drop below 20% on any 500-bar historical
   sample with default parameters (`level_min_age_bars=10`, `equal_level_tol_atr=0.13`,
   `min_hits=3`)

**Do NOT change** `weight_sweep_detected` / `weight_reclaim_confirmed` until the gate-vs-score
architecture decision (Decision 1 from OPTUNA_UTILITY_REPORT) is resolved by the user.

---

## Finding #3 — force_orders DB is empty → POST_LIQUIDATION regime never fires

### Evidence

`OPTUNA_UTILITY_REPORT.md` (Decision 2):
> "force_orders table has 0 rows in production DB. Consequences: force_order_spike = always False
> → POST_LIQUIDATION regime never fires. weight_force_order_spike=0.40 is permanently locked out
> of confluence scoring."

`feature_engine.py:201–203`:
```python
force_order_rate_60s = len(snapshot.force_order_events_60s) / 60.0
self._force_order_rate_history.append(force_order_rate_60s)
force_order_spike = self._is_force_order_spike(force_order_rate_60s)
```

`core/models.py:36`:
```python
force_order_events_60s: list[dict[str, Any]] = field(default_factory=list)
```

### Investigation required (read-only, before any fix)

Codex must answer these two questions by reading the collector code and DB:

**Q1:** Does `market_data.py` (or equivalent WS collector) subscribe to
`btcusdt@forceOrder` stream and write events to `force_order_events_60s`
in the snapshot? Find the exact line.

**Q2:** Run this query against `storage/btc_bot.db`:
```sql
SELECT COUNT(*) FROM force_orders;
SELECT MAX(event_time) FROM force_orders;
```
If count = 0, is the table schema present but never written to,
or does the table not exist at all?

### Expected fix (pending investigation)

If the WS subscription is missing: add `btcusdt@forceOrder` to the websocket subscriptions
and implement the event handler to persist liquidation events to `force_orders` table.

If the subscription exists but writes are broken: find and fix the storage path.

**This is a data-pipeline fix, not a strategy change.** No `settings.py` or core pipeline
changes required.

---

## Finding #4 — Risk parameters misaligned between risk_engine.py defaults and settings.py

### Evidence

`risk_engine.py` (RiskConfig internal defaults, read directly from file):
```python
max_consecutive_losses: int = 3
daily_dd_limit: float = 0.03      # 3%
weekly_dd_limit: float = 0.06     # 6%
partial_exit_pct: float = 0.5     # 50%
trailing_atr_mult: float = 1.0
```

`settings.py` (RiskConfig production values, what actually runs):
```python
max_consecutive_losses: int = 5
daily_dd_limit: float = 0.185     # 18.5% ← 6× more permissive than engine default
weekly_dd_limit: float = 0.063    # 6.3%
partial_exit_pct: float = 0.26    # 26% ← half of engine default
trailing_atr_mult: float = 2.9    # 2.9× engine default
```

The production `settings.py` values are significantly more permissive on daily DD (18.5% vs 3%)
and less protective on partial exit (26% vs 50%) than the risk_engine's own defaults suggest
were intended for conservative operation.

### Impact for daytrading

- `daily_dd_limit = 0.185`: a 18.5% intraday drawdown before the circuit breaker fires is
  extremely wide for a 3-hour max_hold_hours bot. At risk_per_trade=0.7% and max_leverage=8×,
  the bot would need ~26 consecutive full-stop losses in one day to hit this limit — it is
  effectively non-functional as a protection.

- `partial_exit_pct = 0.26`: closing only 26% of the position at TP1 means 74% of size
  continues to TP2 or trailing. In a reversal-style strategy this increases average holding time
  and variance.

- `trailing_atr_mult = 2.9` with `tp1_atr_mult = 1.9`: the trailing stop is wider than TP1,
  meaning the trailing stop can lock in less profit than TP1 would have captured if price
  reverses between TP1 and the trailing trigger.

### Proposed fix (settings.py only — not risk_engine.py)

These are **proposed values for user review**, not mandated changes:

| Parameter | Current production | Proposed | Rationale |
|---|---|---|---|
| `daily_dd_limit` | 0.185 | 0.04 | Meaningful intraday circuit breaker |
| `weekly_dd_limit` | 0.063 | 0.08 | Slightly wider for weekly to allow recovery |
| `max_consecutive_losses` | 5 | 3 | Stop same-day after 3 losses, reassess |
| `partial_exit_pct` | 0.26 | 0.50 | Capture 50% at TP1, let 50% run |
| `trailing_atr_mult` | 2.9 | 1.8 | Tighter trailing after TP1 confirmed |

**These changes do not require research lab validation** — they are risk envelope changes
and can be tested in paper mode immediately. Revert is trivial.

---

## Open architectural decisions (require user resolution before implementation)

These were identified in OPTUNA_UTILITY_REPORT.md and are reproduced here for completeness.
Codex must NOT implement any of these without explicit user approval:

**Decision A — Gate-vs-Score architecture (weight_sweep_detected / weight_reclaim_confirmed)**
Both weights are constant intercepts because sweep+reclaim are hard-gated before confluence runs.
Options: (A) remove from scoring and lower confluence_min by 2.5, (B) replace with continuous
quality score, (C) freeze at 0.0 in Optuna to reduce search budget waste.
Recommended: Option A. Requires user approval + confluence_min recalibration.

**Decision B — HTF levels for sweep detection (B6)**
Use 4h/1h candles for level detection instead of 15m. Stronger semantic alignment with blueprint
(institutional levels are multi-hour structures). Deferred in SWEEP-RECLAIM-FIX-V1 due to scope.
Revisit after Finding #2 is resolved and new campaign produces sufficient trades.

---

## Suggested milestone sequence (user to confirm)

```
1. FORCE-ORDERS-INVESTIGATION   (read-only diagnosis — Codex)
2. SWEEP-QUALITY-V1             (feature_engine + param_registry — Codex)
3. RISK-ENVELOPE-DAYTRADING     (settings.py risk params — Codex)
4. UPTREND-RESEARCH-V1          (research lab, allow_long_in_uptrend — Codex)
5. UPTREND-DEPLOY               (promote to live settings if research confirms edge — after 4)
```

Milestones 1–3 are low-risk and can be parallelized.
Milestone 4 requires research lab run (Run14 or new run under UPTREND-RESEARCH-V1 protocol).
Milestone 5 requires explicit user approval after research results.

---

## Constraints for all milestones

Per AGENTS.md:
- Every commit: WHAT / WHY / STATUS
- No milestone self-marked as done — Claude Code audits after push
- Layer separation must be preserved in all changes
- No core pipeline changes without explicit scope definition
- Working tree must be clean before each milestone start
- Smoke tests required for feature_engine changes (sweep rate check)
- No randomness introduced in any core decision path
