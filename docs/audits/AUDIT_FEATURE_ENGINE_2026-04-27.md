# AUDIT: Feature Engine

**Date:** 2026-04-27  
**Auditor:** Claude Code  
**Branch:** `main`  
**Commit:** `a8c5937` (after Signal/Research Lab audits)  
**Status:** Read-only code review + test coverage analysis

---

## Executive Summary

**Verdict: MVP_DONE** ⚠️

Feature engine has good test coverage for sweep/reclaim logic (critical for signal generation) but lacks explicit unit tests for numerical calculations (ATR, EMA, funding stats, OI zscore). These are validated indirectly through integration tests and 790+ production trades.

---

## Test Coverage

**Files:**
- [`tests/test_feature_engine.py`](../tests/test_feature_engine.py) - 7 tests
- [`tests/test_feature_quality_visibility.py`](../tests/test_feature_quality_visibility.py) - 3 tests

**Total:** 10 tests

| Feature Family | Tests | Coverage |
|---|---|---|
| **Sweep/Reclaim detection** | 4 | ✅ Well-tested |
| **CVD divergence** | 1 | ✅ Windowing logic validated |
| **Quality visibility** | 3 | ✅ Serialization + DB integration |
| **State management** | 2 | ✅ Idempotency + reset |
| **ATR calculation** | 0 | ⚠️ **Missing unit test** |
| **EMA calculation** | 0 | ⚠️ **Missing unit test** |
| **Funding stats** | 0 | ⚠️ **Missing unit test** |
| **OI zscore/delta** | 0 | ⚠️ **Missing unit test** |
| **Force order spike/decreasing** | 0 | ⚠️ **Missing unit test** |

---

## Code Review

### Well-Tested Components ✅

**1. Sweep/Reclaim Detection** ([`feature_engine.py:detect_sweep_reclaim`](../core/feature_engine.py))

Tests:
- `test_compute_features_marks_low_sweep_side()` - validates LOW sweep detection
- `test_compute_features_marks_high_sweep_side()` - validates HIGH sweep detection
- `test_detect_sweep_reclaim_reports_low_sweep_diagnostic_margins()` - validates margin calculations
- `test_detect_sweep_reclaim_reports_high_sweep_diagnostic_margins()` - validates margin calculations

**Critical for:** Signal engine direction inference (LONG requires LOW sweep, SHORT requires HIGH sweep)

**2. CVD Divergence** ([`feature_engine.py:_compute_cvd_divergence`](../core/feature_engine.py))

Test:
- `test_cvd_divergence_uses_windowed_swing_reference_not_last_bar_only()` - validates 4-bar window logic

**Critical for:** Confluence scoring (0.75 weight)

**3. State Management**

Tests:
- `test_compute_features_is_idempotent()` - same input → same output (determinism)
- `test_compute_features_independent_of_prior_state()` - reset() clears state correctly

**Critical for:** Feature engine correctness after restarts

---

### Missing Unit Tests ⚠️

**1. ATR Calculation**

**Method:** `compute_atr()` (standalone function)

**Logic:**
```python
def compute_atr(candles: list[dict], period: int) -> float:
    # True Range = max(high-low, abs(high-prev_close), abs(low-prev_close))
    # ATR = EMA of true ranges
```

**Why missing test matters:**
- ATR is used for:
  - Level building (entry/stop offsets)
  - Sweep depth normalization
  - Volatility regime classification (atr_4h_norm)
- Incorrect ATR → incorrect position sizing + stop placement

**Impact:** MEDIUM (used in critical calculations, but validated indirectly via 790 trades)

**2. EMA Calculation**

**Method:** `compute_ema()` (standalone function)

**Logic:**
```python
def compute_ema(values: list[float], period: int) -> float:
    # Exponential moving average with smoothing factor 2/(period+1)
```

**Why missing test matters:**
- EMA50/EMA200 used for:
  - Trend classification (uptrend/downtrend regime)
  - Confluence scoring (trend alignment 0.25 weight)
- Incorrect EMA → wrong regime classification

**Impact:** MEDIUM (regime detection is critical, but EMA is standard formula)

**3. Funding Stats**

**Methods:**
- `funding_8h` - latest funding rate
- `funding_sma3` - 3-period SMA of funding
- `funding_sma9` - 9-period SMA of funding
- `funding_pct_60d` - percentile rank of current funding vs 60-day history

**Why missing test matters:**
- Funding stats used for:
  - Confluence scoring (funding_supportive 0.20 weight)
  - Crowded leverage regime detection
- Incorrect funding → wrong regime, wrong confluence

**Impact:** LOW (funding is secondary signal, not primary)

**4. OI Zscore/Delta**

**Methods:**
- `oi_zscore_60d` - z-score of current OI vs 60-day rolling window
- `oi_delta_pct` - percentage change in OI since last cycle

**Why missing test matters:**
- OI stats used for:
  - Crowded leverage regime (zscore >= 1.5)
- Incorrect OI → wrong regime classification

**Impact:** MEDIUM (crowded leverage regime is a blocker for LONG)

**5. Force Order Spike/Decreasing**

**Methods:**
- `force_order_spike` - spike in liquidations detected
- `force_order_decreasing` - liquidations decreasing after spike

**Why missing test matters:**
- Used for:
  - Post-liquidation regime detection (spike + decreasing + high TFI)
  - Confluence scoring (spike 0.40 weight)
- Incorrect detection → missed post-liq opportunities

**Impact:** LOW (post-liq regime is rare, 0.40 weight is secondary)

---

## Production Validation

**Indirect validation through:**
- 790 closed trades (Apr 2024 - Apr 2026)
- No evidence of feature calculation bugs causing obvious misbehavior
- Sweep/reclaim features produce valid signals (TP/SL exits working correctly)

**However:**
- No explicit validation that ATR/EMA/funding/OI calculations match expected formulas
- No test cases for edge cases (zero volatility, missing funding data, etc.)

---

## Edge Cases / Tech Debt

| Issue | Severity | Status |
|---|---|---|
| Missing ATR unit test | MEDIUM | Recommend: test against known candle sequences |
| Missing EMA unit test | MEDIUM | Recommend: test against known value sequences |
| Missing funding stats tests | LOW | Recommend: test SMA + percentile calculations |
| Missing OI zscore tests | MEDIUM | Recommend: test z-score calculation + rolling window |
| Missing force order spike tests | LOW | Recommend: test spike detection threshold |
| No test for zero/tiny ATR edge case | LOW | Current: uses max(atr, 1e-8), but not tested |

---

## Recommendations

### 1. Add ATR correctness test:
```python
def test_compute_atr_matches_expected_value():
    # Known candle sequence with hand-calculated ATR
    candles = [
        {"high": 110.0, "low": 105.0, "close": 108.0},
        {"high": 112.0, "low": 107.0, "close": 111.0},
        {"high": 115.0, "low": 109.0, "close": 113.0},
    ]
    # Expected ATR for period=2 with these candles
    # (hand-calculated or validated against TradingView/TA-Lib)
    expected_atr = 5.5  # example value
    
    result = compute_atr(candles, period=2)
    
    assert result == pytest.approx(expected_atr, abs=0.01)
```

### 2. Add EMA correctness test:
```python
def test_compute_ema_matches_expected_value():
    values = [100.0, 102.0, 104.0, 103.0, 105.0]
    # Hand-calculated EMA(5) or validated against TA-Lib
    expected_ema = 103.2  # example value
    
    result = compute_ema(values, period=5)
    
    assert result == pytest.approx(expected_ema, abs=0.01)
```

### 3. Add funding percentile test:
```python
def test_funding_pct_60d_calculates_percentile_rank_correctly():
    # Mock 60-day funding history
    # Current funding = 0.0005 (higher than 75% of history)
    # Expected funding_pct_60d = 75.0
    
    features = engine.compute(snapshot_with_funding_history, "v1.0", "hash")
    
    assert features.funding_pct_60d == pytest.approx(75.0, abs=1.0)
```

### 4. Add OI zscore test:
```python
def test_oi_zscore_60d_calculates_z_score_correctly():
    # Mock 60-day OI history with known mean/stddev
    # Current OI = mean + 1.5 * stddev
    # Expected zscore = 1.5
    
    features = engine.compute(snapshot_with_oi_history, "v1.0", "hash")
    
    assert features.oi_zscore_60d == pytest.approx(1.5, abs=0.1)
```

---

## Verdict

**Feature Engine: MVP_DONE** ⚠️

- ✅ Core signal-critical features well-tested (sweep/reclaim)
- ✅ State management validated (idempotency, reset)
- ✅ Quality visibility tested
- ⚠️ Missing explicit unit tests for numerical calculations (ATR, EMA, funding, OI)
- ⚠️ Relies on integration tests + production validation for correctness

**Not a blocker for Phase 1 completion.**

The missing tests are important for regression prevention, but 790 production trades provide empirical validation that calculations are not grossly wrong. However, edge cases and subtle bugs may exist undetected.

**Recommendation:** Add numerical correctness tests (ATR, EMA, funding, OI) in next maintenance cycle to improve regression coverage.

---

## Metadata

- **Lines of code:** ~600 (core/feature_engine.py)
- **Test lines:** ~239 (tests/test_feature_engine.py + test_feature_quality_visibility.py)
- **Test-to-code ratio:** ~0.4:1 (lower than ideal for numerical code)
- **Cyclomatic complexity:** Medium-High (stateful rolling windows, quality tracking)
