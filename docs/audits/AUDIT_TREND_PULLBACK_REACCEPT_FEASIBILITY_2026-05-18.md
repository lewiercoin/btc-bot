# AUDIT: TREND_PULLBACK_REACCEPT_FEASIBILITY_V1

Date: 2026-05-18
Auditor: Claude Code
Commit: 31884a0
Branch: research/sweep-family-expansion-v1
Builder: Codex
Milestone: TREND_PULLBACK_REACCEPT_FEASIBILITY_V1

## Verdict: NEEDS_FIX

**Blocking issue:** Report file has uncommitted changes that alter results by ~4-5x (1257→5896 trades). Methodology integrity requires committed, final results before audit. Either commit corrected results with explanation, or revert uncommitted changes and re-audit.

**If blocking issue is resolved:** Implementation is methodologically sound, lookahead-safe, and correctly implements hypothesis-failed research. See detailed assessment below.

---

## Blocking Issue

**Uncommitted changes to report:**

```
$ git status
 M docs/analysis/TREND_PULLBACK_REACCEPT_FEASIBILITY_2026-05-18.md

$ git diff --stat docs/analysis/TREND_PULLBACK_REACCEPT_FEASIBILITY_2026-05-18.md
 32 +++++++++++-----------
 1 file changed, 16 insertions(+), 16 deletions(-)
```

**Committed (31884a0) vs Local Modified:**

| Metric | Committed | Local | Delta |
|---|---:|---:|---:|
| Best variant trades | 1257 | 5896 | +4.7x |
| Best variant ER | -0.392 | -0.382 | +2.6% |
| Best variant PF | 0.587 | 0.598 | +1.9% |
| Best variant Max DD | 500.57R | 2279.76R | +4.6x |
| Ablation trades | 1605 | 14604 | +9.1x |

**Impact:** Results differ materially. Trade count increased ~5x, drawdown increased ~5x. This suggests either:
1. Analysis window changed (e.g., 2024-2026 subset → full 2022-2026)
2. Bug was fixed and re-run performed
3. Parameters changed post-commit

**Methodology rule:** Results must be committed and final before audit. Post-commit changes without explanation violate reproducibility and anti-post-hoc-tuning principles.

**Required fix:**
1. **If local changes are corrections:** Commit them with explanation of what changed and why (bug fix? window extension?), then re-request audit
2. **If committed version is correct:** Revert local changes, then proceed with audit of committed results
3. **Do not audit** until committed file matches working tree

---

## Conditional Assessment (if blocking issue resolved)

The assessment below is based on reading the committed code (31884a0) and assumes final results would follow the same methodology.

### 1. Scope & Layer Separation: PASS

**Files changed (commit 31884a0):**
- ✓ `docs/DECISIONS_LOG.md` - decision recorded
- ✓ `docs/MILESTONE_TRACKER.md` - milestone status
- ✓ `docs/analysis/TREND_PULLBACK_REACCEPT_FEASIBILITY_2026-05-18.md` - report
- ✓ `research_lab/analysis_trend_pullback_reaccept_feasibility.py` - runner
- ✓ `research_lab/hypotheses/active/trend_pullback_reaccept.json` - hypothesis
- ✓ `tests/test_research_lab_trend_pullback_reaccept.py` - tests

**No forbidden files modified:**
```
$ git diff --name-only 31884a0^..31884a0 | grep -E "^(core/|orchestrator\.py|settings\.py|execution/|main\.py)"
No forbidden files modified
```

**Layer boundary respected:**
- No imports from core/, orchestrator, settings, execution
- No production/PAPER/LIVE behavior changes
- Pure research_lab/ + docs/ + tests/ scope
- Correct builder discipline

### 2. Methodology Integrity: PASS (pending resolution)

**Hypothesis card (trend_pullback_reaccept.json):**

✓ **Frozen assumptions explicit** (line 47-58):
- "BTC LONG-only in V1"
- "15m trigger uses closed bars only; entry is next 15m open"
- "4h EMA trend uses completed 4h candles only"
- "Equal-low support frozen >= 5 completed 15m bars before trigger"
- "CVD, funding, OI, force-order diagnostic-only"
- "No post-hoc threshold rescue"

✓ **Gates pre-registered** (line 60-70):
- min_oos_trades: 60
- min_expectancy_r: 1.5
- min_profit_factor: 1.8
- max_drawdown_r: 6.0
- min_er_at_2x_cost: 0.5
- max_timeout_share: 0.4
- max_month_trade_share: 0.5
- min_wf_folds_er_gt_1: 3
- max_overlap_vs_trial_00095: 0.3

✓ **Kill criteria defined** (line 71-80)

✓ **Out of scope explicit** (line 88-96): SHORT, 5m, CVD-as-trigger, production deployment, adaptive optimization

**Runner implementation (analysis_trend_pullback_reaccept_feasibility.py):**

✓ **Gates match hypothesis** (line 593-603 of runner):
```python
gates = [
    Gate("min_oos_trades", ">=", 60, "trade_count", "REQUIRED"),
    Gate("min_er", ">=", 1.5, "expectancy_r", "REQUIRED"),
    Gate("min_pf", ">=", 1.8, "profit_factor", "REQUIRED"),
    Gate("max_dd", "<=", 6.0, "max_dd_r", "REQUIRED"),
    Gate("cost_sensitivity_2x", ">", 0.5, "er_at_2x_cost", "REQUIRED"),
    Gate("timeout_share", "<=", 0.4, "timeout_share", "REQUIRED"),
    Gate("max_month_trade_share", "<=", 0.5, "max_month_trade_share", "REQUIRED"),
    Gate("wf_folds_er_gt_1", ">=", 3, "folds_er_gt_1", "REQUIRED"),
    Gate("overlap_vs_trial_00095", "<=", 0.3, "overlap_vs_trial_00095", "RECOMMENDED"),
]
```

Exact match with hypothesis JSON. No post-hoc loosening.

✓ **Coarse grid only** (line 611-624):
- 2 ema_gap values × 2 pullback_max_bars × 2 reclaim_buffer_atr = 8 variants
- Plus 1 no-TFI ablation = 9 total
- No fine-tuning, no adaptive search

✓ **CVD/OI/funding diagnostic-only:**
- No `cvd`, `oi`, `funding`, `force_order` parameters in `SetupVariant` (line 75-96)
- TFI is only flow field, used as fixed threshold filter, not scoring stack
- Ablation tests no-TFI variant to verify incremental value

**No post-hoc rescue observed in committed files.**

### 3. Lookahead & Data Leakage: PASS

**Frozen level detection (line 270-308):**

✓ **Min age enforcement:**
```python
def detect_equal_low_levels(candles, trigger_idx, *, min_age_bars=5, ...):
    window_end = trigger_idx - min_age_bars  # Line 279
    if window_end <= 0:
        return []
    window_start = max(0, window_end - lookback_bars)
    prior = candles[window_start:window_end]  # Line 283 - only BEFORE min_age cutoff
```

Frozen level is guaranteed to be at least `min_age_bars` (default 5) completed 15m bars before trigger. This matches hypothesis requirement.

**Test verification (test_research_lab_trend_pullback_reaccept.py line 61-68):**
```python
def test_detect_equal_low_levels_respects_min_age_cutoff():
    candles[54] = _bar(54, 100, 102, 80, 101)  # Very low level
    candles[55] = _bar(55, 100, 102, 80.01, 101)
    levels = detect_equal_low_levels(candles, trigger_idx=58, min_age_bars=5)
    assert all(level > 90 for level in levels)  # 80-level excluded (too recent)
```

Test creates low at index 54-55, trigger at 58 (only 3-4 bars later), with min_age=5. Verifies recent low is excluded.

✓ **4h trend context (line 233-267):**
```python
def completed_4h_context(candles_4h, target_open):
    cutoff = target_open - timedelta(hours=4)  # Line 234
    times = _candle_times(candles_4h)
    return candles_4h[:bisect_right(times, cutoff)]  # Line 236 - only completed candles
```

Only uses 4h candles with `open_time <= target_open - 4h`, ensuring current uncompleted 4h candle is excluded.

**Test verification (line 51-58):**
```python
def test_completed_4h_context_excludes_current_unclosed_4h_candle():
    candles = [_h4(i, 100 + i) for i in range(205)]
    target = candles[-1].open_time + timedelta(hours=1)  # 1h into last candle
    context = completed_4h_context(candles, target)
    assert candles[-1] not in context  # Uncompleted candle excluded
    assert context[-1].open_time <= target - timedelta(hours=4)
```

✓ **Entry timing (line 360-372):**
```python
signal = find_reaccept_signal(candles_15m, candles_4h, agg_60s, idx, variant)
# idx = trigger bar (reclaim close)
entry_bar = candles_15m[idx + 1]  # Line 360 - NEXT bar
entry_price = entry_bar.open  # Line 362 - next 15m open
```

Entry is explicitly the open of the bar AFTER the trigger bar. This matches hypothesis requirement "entry is next 15m open after reclaim close."

**Test verification (line 71-101):**
```python
def test_find_reaccept_signal_uses_prior_pullback_and_next_open_entry():
    # ... setup with pullback at idx 72, trigger at idx 73, entry expected at idx 74
    signal = find_reaccept_signal(candles_15m, candles_4h, agg, 73, variant)
    assert signal.entry_idx == 74
    assert signal.entry_time == candles_15m[74].open_time
```

✓ **TFI timing (line 220-230, 356):**
```python
def aggregate_tfi_60s(agg_60s, candle_open):
    buy = 0.0
    sell = 0.0
    for minute in range(15):  # Only 0-14 minutes of THIS candle
        bucket = agg_60s.get(candle_open + timedelta(minutes=minute))
        ...
    return (buy - sell) / total if total > 0 else 0.0

# Usage:
tfi = aggregate_tfi_60s(agg_60s, trigger.open_time)  # Line 356
```

TFI aggregates only the 15 minutes of the trigger candle itself (minutes 0-14). No future data.

**Test verification (line 40-48):**
```python
def test_aggregate_tfi_60s_uses_only_current_15m_bucket():
    # Creates agg buckets for minutes 0-14 with TFI=1/3
    # Creates future bucket at minute 15 with TFI=1.0
    assert aggregate_tfi_60s(agg, start) == 1 / 3  # Uses only 0-14, not future minute 15
```

✓ **Pullback timing (line 335-350):**
```python
pullback_start = max(0, idx - variant.pullback_max_bars)
pullback_window = candles_15m[pullback_start:idx]  # Line 336 - only BEFORE trigger
```

Pullback detection uses only bars strictly before the trigger bar. No lookahead.

**No lookahead detected in implementation.**

### 4. Research Harness Correctness: PASS

✓ **One position at a time (line 472):**
```python
run.trades.append(trade)
idx = max(idx + 1, trade.exit_idx + 1)  # Advance to bar AFTER exit
```

After a trade exits, index advances to at least the bar after exit. This prevents overlapping positions and accurately simulates "one open research trade at a time."

✓ **Trade simulation (line 396-435):**
- Entry: next 15m open + slippage
- Stop: frozen_level - 0.75 * ATR
- Target: entry + 2.5R
- Max hold: 96 bars (24 hours)
- Fees: FEE_RATE * (entry + exit) * cost_multiplier
- Slippage: SLIPPAGE_BPS / 10000 * entry * cost_multiplier * 2

Standard, coherent simulation.

✓ **Metrics (line 532-573):**
- Expectancy R: mean(pnl_r)
- Profit factor: gross_profit / abs(gross_loss)
- Max DD: standard cumulative peak-to-trough
- Cost stress: recomputed from base pnl by adding incremental costs per trade
- Overlap: `sum(1 for trade in trades if trade.entry_time in baseline_times) / len(trades)`
- Concentration: max monthly/quarterly trade share
- Walk-forward folds: 4 half-year folds (2024H1, 2024H2, 2025H1, 2025H2+2026Q1)

Metrics are internally coherent and match standard research harness expectations.

✓ **CVD/OI/funding/force-order diagnostic-only:**

Checked all `SetupVariant`, `ReacceptSignal`, and `find_reaccept_signal` code. No CVD, OI, funding, or force-order fields influence pass/fail logic. Only TFI is used as a fixed threshold filter (tfi >= 0.05), and no-TFI ablation tests its incremental value.

CVD could be added to diagnostics dict (line 389) but is not present in current code. Correctly out of scoring.

### 5. Result Interpretation: PASS (assuming committed results)

**Builder verdict (committed 31884a0):**
- Best variant: TPR_G0.010_B5_R0.08_TFI
- Trades: 1257
- ER: -0.392
- PF: 0.587 (0.59 rounded)
- Max DD: 500.57R
- 2x cost ER: -0.810
- WF folds ER > 1: 0/4
- Overlap vs trial-00095: 0.7%

**Gates failed: 5/9**
- min_er: -0.392 < 1.5 ❌
- min_pf: 0.587 < 1.8 ❌
- max_dd: 500.57 > 6.0 ❌
- cost_sensitivity_2x: -0.810 < 0.5 ❌
- wf_folds_er_gt_1: 0 < 3 ❌

**Gates passed: 4/9**
- min_oos_trades: 1257 > 60 ✓
- timeout_share: 2.8% < 40% ✓
- max_month_trade_share: 9.6% < 50% ✓
- overlap_vs_trial_00095: 0.7% < 30% ✓

✓ **HYPOTHESIS_FAILED is correct builder verdict:**
- Negative expectancy across all variants and all walk-forward folds
- Drawdown catastrophic (500R on 1257 trades, vs 4.5R on 47 trades for trial-00095)
- Cost sensitivity negative (ER -0.810 at 2x cost)
- No walk-forward fold achieved ER > 1.0
- Setup is empirically not tradeable

✓ **Reject promotion is correct:**
- ER < 0 means setup loses money on average
- No amount of parameter tuning can rescue negative expectancy without overfitting
- Hypothesis frozen assumptions forbid post-hoc threshold rescue

✓ **Low overlap proves distinctness but not edge:**
- 0.7% overlap with trial-00095 confirms this is a different setup (not a sweep/reclaim variant)
- But distinctness ≠ edge. This setup captures different events, but those events are not profitable.

**Interpretation is sound. Builder correctly concluded hypothesis failed and must not be promoted.**

### 6. Tests: PASS

**Test results (per user):**
```
pytest tests/test_research_lab_trend_pullback_reaccept.py tests/test_research_lab_multi_candle_events.py tests/test_research_lab_experiments.py -q
27 passed
```

**Critical tests present:**
1. `test_aggregate_tfi_60s_uses_only_current_15m_bucket` - verifies TFI no future leak
2. `test_completed_4h_context_excludes_current_unclosed_4h_candle` - verifies 4h trend no future leak
3. `test_detect_equal_low_levels_respects_min_age_cutoff` - verifies frozen level >= 5 bars before trigger
4. `test_find_reaccept_signal_uses_prior_pullback_and_next_open_entry` - verifies entry is next 15m open
5. `test_find_reaccept_signal_rejects_without_prior_pullback` - verifies pullback requirement enforced
6. `test_trend_pullback_hypothesis_spec_is_valid` - verifies hypothesis card loads correctly

**Coverage assessment:**
- ✓ Lookahead risks covered (frozen level, 4h context, entry timing, TFI timing)
- ✓ Trigger logic covered (pullback requirement)
- ✓ Hypothesis spec validation covered
- ✓ No missing critical tests identified

**compileall clean (per user):**
- research_lab/analysis_trend_pullback_reaccept_feasibility.py
- tests/test_research_lab_trend_pullback_reaccept.py

No syntax errors.

---

## Documentation Quality

**DECISIONS_LOG.md (commit 31884a0):**

✓ Records decision to approve milestone as research-only
✓ Documents external consultation process (Claude, Perplexity, DeepSeek)
✓ Records result (hypothesis failed)
✓ Explicitly states "do not rescue by retuning thresholds"

**MILESTONE_TRACKER.md (commit 31884a0):**

✓ Updates status from CANDIDATE to READY_FOR_AUDIT
✓ Records builder (Codex), decision date, hypothesis path, report path
✓ Shows protocol summary
✓ Shows results (trades, ER, PF, DD, WF, verdict)
✓ Builder conclusion: HYPOTHESIS_FAILED, do not promote

Documentation is complete and consistent with committed report.

---

## Summary

| Aspect | Status | Notes |
|---|---|---|
| Scope / layer separation | ✓ PASS | Research-only, no runtime/core/orchestrator/settings/execution changes |
| Methodology integrity | ⚠ BLOCKED | Uncommitted report changes invalidate audit basis |
| Lookahead / data leakage | ✓ PASS | Frozen level, 4h trend, entry timing, TFI timing all correct |
| Research harness correctness | ✓ PASS | One position at a time, metrics coherent, CVD/OI/funding diagnostic-only |
| Result interpretation | ✓ PASS | HYPOTHESIS_FAILED is correct verdict, reject promotion is correct |
| Tests | ✓ PASS | 27/27 passed, critical lookahead tests present, compileall clean |

**Blocking issue:** Report file has 32 lines of uncommitted changes that alter results by ~4-5x. Cannot audit until committed file matches working tree.

**If blocking issue is resolved by committing corrected results:** Implementation is methodologically sound. Hypothesis failed quality gates decisively. Correct builder verdict is HYPOTHESIS_FAILED. Milestone can close with this verdict after audit PASS.

---

## Required Action

**Before re-audit:**

1. **Commit final report** with explanation of changes (bug fix? window extension? parameter correction?)
2. **Update MILESTONE_TRACKER** if numbers changed materially
3. **Re-run tests** to verify corrected results
4. **Re-request audit** with updated commit hash

**Do not:**
- Audit uncommitted work
- Accept partial/draft reports
- Mix committed and uncommitted results

**Audit discipline:** Committed files are source of truth. Uncommitted changes mean milestone is not ready for final audit.

---

**Audit status:** BLOCKED on methodology integrity
**Required fix:** Commit final report or revert uncommitted changes
**Re-audit:** After commit, re-request with new commit hash

Conditional verdict (if blocking issue resolved): **PASS for milestone closure with HYPOTHESIS_FAILED verdict**
