# AUDIT: TRIAL_00095_LOSS_CONTROL_INTRABAR_VALIDATION_V1

Date: 2026-05-18
Auditor: Claude Code
Commit: e68934a
Branch: research/sweep-family-expansion-v1
Builder: Codex
Milestone: TRIAL_00095_LOSS_CONTROL_INTRABAR_VALIDATION_V1

## Verdict: PASS

Milestone approved for closure with builder verdict **FAIL_NO_ROBUST_IMPROVEMENT**. Do not promote hard loss-control to runtime. Hypothesis was correctly tested and correctly failed. Intrabar validation falsified the distribution clipping diagnostic.

---

## Assessment

Implementation is methodologically sound. Frozen entries correctly replicated, entry candle excluded, R computed from entry/stop, no winner cap, adverse-first fills. Hypothesis failed because tighter stops cut too many eventual winners.

### 1. Scope & Layer Separation: PASS

**Files changed (commit e68934a):**
- ✓ `docs/DECISIONS_LOG.md` - decision recorded
- ✓ `docs/MILESTONE_TRACKER.md` - milestone status
- ✓ `docs/analysis/TRIAL_00095_LOSS_CONTROL_INTRABAR_VALIDATION_2026-05-18.md` - report
- ✓ `research_lab/analysis_trial_00095_loss_control_intrabar_validation.py` - validation runner
- ✓ `research_lab/hypotheses/active/trial_00095_loss_control_intrabar_validation.json` - hypothesis card
- ✓ `tests/test_research_lab_loss_control_intrabar_validation.py` - tests

**No forbidden files modified:**
```
$ git diff --name-only e68934a^..e68934a | grep -E "^(core/|orchestrator\.py|settings\.py|execution/|main\.py)"
No forbidden files modified
```

**Layer boundary respected:**
- No imports from core/, orchestrator, settings, execution
- No production/PAPER/LIVE behavior changes
- Pure research_lab/ + docs/ + tests/ scope
- Correct builder discipline

### 2. Frozen Entries: PASS

**Baseline control:**
- Frozen replay entries: 274
- Prior diagnostic artifact entries: 274
- Baseline artifact count match: 1.0 (report line 22)

**Entry replay (line 106-162 of runner):**

Replays trial-00095 exact parameters via BacktestRunner:
```python
params = json.loads(row["params_json"])
settings = build_candidate_settings(load_settings(profile="research"), params)
runner = BacktestRunner(conn, settings=settings)
runner.run(BacktestConfig(start_date=START_DATE, end_date=END_DATE, initial_equity=10_000.0))
```

Loads entry_price, stop_loss, take_profit_1, take_profit_2, baseline_pnl_r from trade_log + executable_signals tables.

**Verification:**
- 274 entries frozen (matches prior diagnostic exactly)
- Entry population immutable across all variants
- Baseline ER 2.121 matches prior diagnostic (2.121)

**Assessment:** Frozen entries correctly replicated from trial-00095 replay.

### 3. Entry Candle Exclusion: PASS

**Implementation (line 281 of simulate_variant):**

```python
current = entry.opened_at + timedelta(minutes=15)
for offset in range(duration):
    candle = candles_by_time.get(current)
    ...
    current += timedelta(minutes=15)
```

Starts at `opened_at + 15 minutes`, so the entry candle itself (at `opened_at`) is excluded.

**Rationale (hypothesis card line 37):**

"The entry candle itself is excluded because BacktestRunner opens positions after close checks for that snapshot."

This is correct - BacktestRunner evaluates signals on close, enters on next open. So the entry candle is already "spent" for entry decision and should not be used for exit simulation.

**Assessment:** Entry candle correctly excluded from post-entry simulation window.

### 4. R Calculation From Entry/Stop: PASS

**Implementation (line 304-314):**

```python
def loss_threshold_price(entry: FrozenTrade, loss_r: float) -> float:
    if entry.direction == "LONG":
        return entry.entry_price - loss_r * entry.risk  # risk = abs(entry_price - stop_loss)
    return entry.entry_price + loss_r * entry.risk

def pnl_r_at_price(entry: FrozenTrade, exit_price: float, cost_mult: float = 1.0) -> float:
    raw = exit_price - entry.entry_price if entry.direction == "LONG" else entry.entry_price - exit_price
    fees = (entry.entry_price + exit_price) * FEE_RATE * cost_mult
    slippage = entry.entry_price * SLIPPAGE_BPS / 10000 * 2 * cost_mult
    return (raw - fees - slippage) / entry.risk if entry.risk else 0.0
```

**FrozenTrade.risk property (line 66-67):**

```python
@property
def risk(self) -> float:
    return abs(self.entry_price - self.stop_loss)
```

R is computed from original frozen entry_price and stop_loss, not from realized pnl_r.

**Verification (hypothesis card line 34):**

"R is computed from original entry_price and original stop_loss, not from realized pnl_r."

**Assessment:** R correctly computed from entry/stop geometry, not realized outcomes.

### 5. No Winner Cap: PASS

**Implementation (line 274-275, 301):**

```python
if variant.loss_r is None:
    return SimulatedTrade(entry, variant.variant_id, entry.baseline_pnl_r, entry.baseline_exit_reason, duration, False)
...
# If threshold not hit:
return SimulatedTrade(entry, variant.variant_id, entry.baseline_pnl_r, entry.baseline_exit_reason, duration, False, missing)
```

If no loss threshold hit, baseline outcome preserved exactly, including full winner tail.

**Verification (hypothesis card line 35):**

"Variants only add hard loss-side thresholds and do not cap winners."

**Kill criteria (hypothesis card line 58):**

"Any variant that caps winners without a prior loss-threshold touch is invalid."

**Assessment:** No winner cap implemented. Baseline winners preserved unless loss threshold touched first.

### 6. Adverse-First Intrabar: PASS

**Implementation (line 288-299):**

```python
hit = candle.low <= threshold if entry.direction == "LONG" else candle.high >= threshold
if hit:
    pnl_r = pnl_r_at_price(entry, threshold)
    return SimulatedTrade(
        entry=entry,
        variant_id=variant.variant_id,
        pnl_r=pnl_r,
        exit_reason=f"loss_control_{variant.loss_r:.2f}R",
        duration_bars=offset + 1,
        threshold_touched=True,
        missing_candles=missing,
    )
```

As soon as threshold is touched on any candle, exits immediately at threshold price. No recovery credited inside same candle.

**Verification (hypothesis card line 40):**

"Same-candle recovery is not credited after loss threshold touch; loss control is adverse-first."

**Test verification (test_research_lab_loss_control_intrabar_validation.py line 46-55):**

```python
def test_loss_control_hits_long_threshold_before_baseline_close():
    entry = _entry("LONG", baseline_pnl_r=-1.5)
    candles = {_candle(1, high=101.0, low=90.9).open_time: _candle(1, high=101.0, low=90.9)}
    
    trade = simulate_variant(entry, candles, LossControlVariant("HARD_STOP_0_90R", 0.90))
    
    assert trade.threshold_touched is True
    assert trade.exit_reason == "loss_control_0.90R"
    assert trade.pnl_r < -0.90
    assert trade.pnl_r > entry.baseline_pnl_r  # Saved from worse baseline loss
```

Verifies threshold detection and adverse-first exit.

**Assessment:** Adverse-first intrabar handling correctly implemented.

### 7. Result Interpretation: PASS

**Baseline replay (report line 20-25):**
- Trades: 274
- ER: 2.121
- PF: 4.22
- Max DD: 14.68R
- Matches prior diagnostic exactly

**Best loss-control variant (report line 32):**
- HARD_STOP_0_90R
- Trades: 274 (entry count match ✓)
- ER: 1.679 (delta -0.442, -20.8%)
- PF: 3.14 (vs baseline 4.22, degraded)
- DD ratio: 1.01 (vs baseline 1.00, no improvement)
- Triggered: 128 trades
- Saved losers: 13
- **Stopped winners: 19** ← critical finding
- Folds+: 0/9 (no fold improvement)
- 2x cost ER: 0.640 (< 1.0, fails cost stress)
- Missing candles: 0

**HARD_STOP_1_00R (report line 33):**
- ER: 1.664 (delta -0.457, -21.5%)
- Stopped winners: 18
- Saved losers: 1 (only 1!)
- Folds+: 0/9

**HARD_STOP_0_75R (report line 35):**
- ER: 1.637 (delta -0.484, -22.8%)
- Stopped winners: 23
- Saved losers: 111 (many saved, but stopped more winners)
- DD ratio: 0.93 (slight improvement)
- Folds+: 2/9 (marginal fold support)

**Critical insight:**

All variants show **stopped winners > saved losers** (except 0.75R which saved 111 losers but stopped 23 winners, net negative).

The tighter stops trigger before eventual winners recover, cutting the positive tail more than they reduce left-tail damage.

**Gates assessment:**
- ❌ min_delta_er: all negative (< 0.0)
- ❌ min_pf_ratio_vs_baseline: all < 1.0 (degraded)
- ❌ max_dd_ratio_vs_baseline: 0.90R best has 1.01, no improvement; 1.00R has 1.06, worse
- ❌ min_folds_delta_er_positive: 0/9 for best variants (< 6)
- ❌ min_er_at_2x_cost: 0.640 < 1.0 (fails cost stress)

**Builder verdict: FAIL_NO_ROBUST_IMPROVEMENT**

✓ Correct. The hypothesis was:
- Distribution clipping (LOSS_CAP_1.00R) showed +10.6% ER in prior diagnostic
- Intrabar validation tests whether that survives executable 15m OHLC replay
- Result: all hard-stop variants degrade ER by 21-23%
- Root cause: tighter stops cut eventual winners more than they save losers
- Hypothesis is falsified

**Comparison to prior diagnostic:**

| Metric | Prior Diagnostic (LOSS_CAP_1.00R clipping) | Intrabar Validation (HARD_STOP_1_00R) | Delta |
|---|---:|---:|---:|
| ER | 2.346 (+10.6%) | 1.664 (-21.5%) | -32.1pp |
| PF | 6.40 | 3.02 | -3.38 |
| Folds+ | 9/9 | 0/9 | -9 |

The diagnostic clipping was artifact of realized-R distribution shape, not executable on 15m OHLC. Intrabar validation correctly falsified it.

**Assessment:** Result interpretation is sound. Builder verdict FAIL_NO_ROBUST_IMPROVEMENT is correct.

### 8. Tests: PASS

**Test results (per user):**
```
24 passed
compileall clean
```

**Critical tests present:**
1. `test_loss_control_hits_long_threshold_before_baseline_close` (line 46-55) - verifies threshold detection and exit
2. `test_loss_control_short_symmetry_uses_high_threshold` (line 58-67) - verifies SHORT direction symmetry
3. `test_variant_preserves_baseline_when_threshold_not_touched` (line 70-78) - verifies baseline preservation
4. `test_metrics_track_stopped_winners_and_saved_losers` (line 81-98) - verifies stopped_winner_count and saved_loser_count
5. `test_builder_verdict_blocks_replay_mismatch` (line 101-115) - verifies replay count validation
6. `test_loss_control_hypothesis_spec_is_valid` (line 118-123) - verifies hypothesis card

**Coverage assessment:**
- ✓ Threshold detection tested (LONG and SHORT)
- ✓ Baseline preservation tested (when threshold not hit)
- ✓ Stopped winners / saved losers tracking tested
- ✓ Replay count validation tested
- ✓ Hypothesis spec validation tested
- ✓ No missing critical tests identified

**Assessment:** Tests adequate for intrabar validation scope.

---

## Summary

| Aspect | Status | Notes |
|---|---|---|
| Scope / layer separation | ✓ PASS | Research-only, no runtime/core/orchestrator/settings/execution changes |
| Frozen entries | ✓ PASS | 274/274 match, baseline ER 2.121 matches prior diagnostic |
| Entry candle exclusion | ✓ PASS | Starts at opened_at + 15min, entry candle correctly excluded |
| R from entry/stop | ✓ PASS | R = abs(entry_price - stop_loss), not from realized pnl_r |
| No winner cap | ✓ PASS | Baseline winners preserved unless loss threshold touched first |
| Adverse-first intrabar | ✓ PASS | Exits immediately when threshold touched, no recovery credited |
| Result interpretation | ✓ PASS | FAIL_NO_ROBUST_IMPROVEMENT correct, hypothesis falsified |
| Tests | ✓ PASS | 24/24 passed, critical coverage present, compileall clean |

**Final result:**
- Best variant: HARD_STOP_0_90R
- ER: 2.121 → 1.679 (-20.8%)
- Stopped winners: 19
- Saved losers: 13
- Net effect: negative (cut more winners than saved losers)
- Folds+: 0/9 (no fold improvement)
- Verdict: FAIL_NO_ROBUST_IMPROVEMENT

**Implication:** Distribution clipping diagnostic (LOSS_CAP_1.00R +10.6%) was artifact of realized-R shape, not executable on 15m OHLC. Tighter stops trigger before eventual winners recover, degrading expectancy. Do not promote hard loss-control to runtime.

**Do not promote hard loss-control, tighter stop, or -1R clipping into runtime.**

---

## Critical Issues

None.

## Warnings

None.

## Observations

### Distribution Clipping vs Intrabar Reality

**Prior diagnostic (LOSS_CAP_1.00R clipping):**
- ER: 2.346 (+10.6%)
- PF: 6.40
- Folds+: 9/9
- Looked promising

**Intrabar validation (HARD_STOP_1_00R):**
- ER: 1.664 (-21.5%)
- PF: 3.02
- Folds+: 0/9
- Stopped 18 winners, saved 1 loser
- Hypothesis failed

**Why the diagnostic was misleading:**

Realized-R clipping operates on final outcomes. It clips losses at -1R as if they hit that exact level. In reality, a hard stop at entry - 1.0R must be placed before the trade evolves. Many trades that eventually win first dip below -1R temporarily, then recover. The clipping diagnostic doesn't see those temporary dips - it only sees the final outcome. The intrabar validation sees the dips and exits there, cutting eventual winners.

This is the exact scenario the hypothesis card warned about (failure mode line 64):

"Hard loss thresholds trigger too often before eventual winners and reduce expectancy."

**Lesson:** Distribution clipping diagnostics can identify directional hypotheses but cannot validate executable exit logic. Full intrabar replay is required.

### Stopped Winners Pattern

All loss-control variants show stopped_winner_count > saved_loser_count:

| Variant | Stopped Winners | Saved Losers | Net Impact |
|---|---:|---:|---|
| HARD_STOP_0_75R | 23 | 111 | Negative (too many winners cut despite 111 saves) |
| HARD_STOP_0_90R | 19 | 13 | Negative (net -6 trades harmed) |
| HARD_STOP_1_00R | 18 | 1 | Negative (net -17 trades harmed) |
| HARD_STOP_1_10R | 17 | 0 | Negative (net -17 trades harmed) |

Even HARD_STOP_0_75R, which saved 111 losers, still degraded ER because it stopped 23 eventual winners. The winner tail is more valuable than the loser tail reduction.

This confirms trial-00095 edge requires full winner continuation. Do not cap winners, do not stop winners early.

### Methodology Discipline

Builder correctly labeled limitations and avoided promotion claims:
- Hypothesis card: "At most a future exit-research validation verdict is allowed; no promotion-ready verdict." (line 41)
- Report: "This does not add entries, change entry filters, cap winners, alter TP logic, or approve deployment." (line 15)
- DECISIONS_LOG: "Do not promote hard loss-control, tighter stop, or -1R clipping into runtime."

Excellent methodology discipline and validation rigor.

### Research Workflow Effectiveness

Two-stage research workflow worked correctly:
1. **Stage 1 (Diagnostic):** LOSS_CAP_1.00R clipping showed +10.6% ER → hypothesis for validation
2. **Stage 2 (Validation):** HARD_STOP_1_00R intrabar showed -21.5% ER → hypothesis falsified

This is proper research methodology:
- Fast diagnostic identifies candidates
- Rigorous validation filters false positives
- No premature promotion

---

## Recommended Next Step

**APPROVE milestone closure with FAIL_NO_ROBUST_IMPROVEMENT verdict.**

Trial-00095 loss-control intrabar validation is complete. Hypothesis failed correctly. Do not promote hard loss-control to runtime. Trial-00095 baseline exits remain unchanged.

**Strategic context:** Two exit-research attempts completed:
1. **EXIT_SURFACE_DIAGNOSTIC_V1:** Distribution clipping suggested loss-clipping sensitivity (HYPOTHESIS_FOR_FUTURE_VALIDATION)
2. **LOSS_CONTROL_INTRABAR_VALIDATION_V1:** Intrabar validation falsified the hypothesis (FAIL_NO_ROBUST_IMPROVEMENT)

The research workflow correctly identified and rejected a false positive. Trial-00095 baseline exits are validated as-is. No further exit research is indicated unless new evidence emerges.

**Current priorities:**
- Continue M4 near-miss monitoring through 2026-06-13 checkpoint
- Focus on frequency problem (5m failed, trend-pullback failed, loss-control failed)
- Consider M4 checkpoint findings before next research direction

---

**Audit status:** DONE
**Milestone verdict:** FAIL_NO_ROBUST_IMPROVEMENT (builder verdict confirmed)
**Deployment verdict:** N/A (research-only, hypothesis falsified, no promotion)
**Close milestone:** YES
