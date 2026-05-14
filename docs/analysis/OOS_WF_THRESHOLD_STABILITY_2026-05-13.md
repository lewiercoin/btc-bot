# OOS Walk-Forward Threshold Stability Analysis

**Date:** 2026-05-13  
**Author:** Cascade (builder)  
**Milestone:** OOS_WF_THRESHOLD_STABILITY_ANALYSIS (M3)  
**Status:** COMPLETE  
**Verdict:** THRESHOLD_NATURAL

## Executive Summary

Walk-forward threshold stability test across 3 OOS windows with 6 threshold values (18 backtest runs). Testing whether `min_sweep_depth_pct = 0.00649` is stable across time windows or window-specific / overfitted.

**Verdict: THRESHOLD_NATURAL**

- Warning: ['WF3'] has insufficient data (< 20 trades). Verdict based on remaining windows.
- WF1: best threshold=0.00700 (ER=2.798, trades=88)
- WF2: best threshold=0.00800 (ER=2.951, trades=22)
- WF1: baseline 0.00649 ranks #4 of 6
- WF2: baseline 0.00649 ranks #2 of 6
- Best-threshold spread across valid windows: 0.00100
- Baseline is top-3 in 1/2 valid windows. Threshold is reasonably stable.

## Walk-Forward Methodology

| Window | Train (In-Sample) | Test (Out-of-Sample) | Notes |
|---|---|---|---|
| WF1 | 2022-01-01 to 2023-12-31 | 2024-01-01 to 2024-12-31 | 2 years train, 1 year test |
| WF2 | 2023-01-01 to 2024-12-31 | 2025-01-01 to 2025-12-31 | 2 years train, 1 year test |
| WF3 | 2024-01-01 to 2025-12-31 | 2026-01-01 to 2026-03-28 | 2 years train, 3 months test |

**Threshold grid:** 0.004, 0.005, 0.006, 0.00649 (baseline), 0.007, 0.008

**All parameters except `min_sweep_depth_pct`** are held constant at trial-00095 exact values. This isolates the threshold effect (ceteris paribus), unlike M2's cross-trial analysis which conflated depth with ~40 co-varying Optuna parameters.

**Minimum threshold for statistical validity:** 20 OOS trades per window. Cells with fewer trades are flagged as INSUFFICIENT_DATA.

## OOS Results (Primary Evidence)

### WF1: OOS 2024-01-01 to 2024-12-31

| Threshold | Trades | ER | PF | Max DD% | Win Rate | Safety Flags | Valid? |
|---:|---:|---:|---:|---:|---:|---|---|
| 0.00400 | 255 | 1.368 | 2.588 | 7.27% | 46.7% | duplicate_level_proximity(3), consecutive_loss_streak(12) | YES |
| 0.00500 | 172 | 2.176 | 4.330 | 5.20% | 58.1% | duplicate_level_proximity(3), consecutive_loss_streak(8) | YES |
| 0.00600 | 122 | 2.471 | 5.096 | 3.42% | 60.7% | duplicate_level_proximity(1), consecutive_loss_streak(5) | YES |
| **0.00649** | **106** | **2.463** | **4.841** | **4.29%** | **58.5%** | consecutive_loss_streak(7) | YES |
| 0.00700 | 88 | 2.798 | 5.756 | 3.77% | 63.6% | duplicate_level_proximity(2), consecutive_loss_streak(6) | YES |
| 0.00800 | 69 | 2.737 | 5.680 | 2.70% | 62.3% | none | YES |

### WF2: OOS 2025-01-01 to 2025-12-31

| Threshold | Trades | ER | PF | Max DD% | Win Rate | Safety Flags | Valid? |
|---:|---:|---:|---:|---:|---:|---|---|
| 0.00400 | 103 | 1.715 | 3.701 | 3.15% | 60.2% | consecutive_loss_streak(5) | YES |
| 0.00500 | 70 | 1.804 | 4.068 | 5.56% | 62.9% | consecutive_loss_streak(9) | YES |
| 0.00600 | 43 | 2.219 | 4.693 | 2.08% | 65.1% | none | YES |
| **0.00649** | **36** | **2.862** | **7.071** | **1.94%** | **72.2%** | none | YES |
| 0.00700 | 30 | 2.727 | 6.479 | 1.94% | 70.0% | none | YES |
| 0.00800 | 22 | 2.951 | 7.413 | 1.32% | 72.7% | none | YES |

### WF3: OOS 2026-01-01 to 2026-03-28

| Threshold | Trades | ER | PF | Max DD% | Win Rate | Safety Flags | Valid? |
|---:|---:|---:|---:|---:|---:|---|---|
| 0.00400 | 15 | 0.403 | 1.291 | 3.82% | 26.7% | consecutive_loss_streak(6) | **NO** (< 20) |
| 0.00500 | 10 | 0.573 | 1.431 | 3.22% | 30.0% | consecutive_loss_streak(5) | **NO** (< 20) |
| 0.00600 | 7 | -0.818 | 0.331 | 3.82% | 14.3% | consecutive_loss_streak(6) | **NO** (< 20) |
| **0.00649** | **5** | **-0.535** | **0.497** | **2.58%** | **20.0%** | none | **NO** (< 20) |
| 0.00700 | 5 | -0.535 | 0.497 | 2.58% | 20.0% | none | **NO** (< 20) |
| 0.00800 | 2 | -1.432 | 0.000 | 1.36% | 0.0% | none | **NO** (< 20) |

### Best Threshold Per OOS Window

| Window | Best Threshold | ER | Trades | Baseline Rank |
|---|---:|---:|---:|---:|
| WF1 | 0.00700 | 2.798 | 88 | #4 of 6 |
| WF2 | 0.00800 | 2.951 | 22 | #2 of 6 |
| WF3 | — | — | — | INSUFFICIENT_DATA |

## Train vs OOS Degradation (Context Only — Not Primary Evidence)

> Train/IS results are context for understanding overfitting risk. OOS results above are the primary evidence.

### WF1

| Threshold | Train ER | OOS ER | Degradation |
|---:|---:|---:|---:|
| 0.00400 | 0.942 | 1.368 | -45% |
| 0.00500 | 1.267 | 2.176 | -72% |
| 0.00600 | 1.709 | 2.471 | -45% |
| **0.00649** | **1.714** | **2.463** | **-44%** |
| 0.00700 | 1.930 | 2.798 | -45% |
| 0.00800 | 1.954 | 2.737 | -40% |

### WF2

| Threshold | Train ER | OOS ER | Degradation |
|---:|---:|---:|---:|
| 0.00400 | 1.299 | 1.715 | -32% |
| 0.00500 | 1.979 | 1.804 | 9% |
| 0.00600 | 2.325 | 2.219 | 5% |
| **0.00649** | **2.445** | **2.862** | **-17%** |
| 0.00700 | 2.789 | 2.727 | 2% |
| 0.00800 | 2.655 | 2.951 | -11% |

### WF3

| Threshold | Train ER | OOS ER | Degradation |
|---:|---:|---:|---:|
| 0.00400 | 1.468 | 0.403 | 73% |
| 0.00500 | 2.069 | 0.573 | 72% |
| 0.00600 | 2.406 | -0.818 | 134% |
| **0.00649** | **2.565** | **-0.535** | **121%** |
| 0.00700 | 2.780 | -0.535 | 119% |
| 0.00800 | 2.789 | -1.432 | 151% |

## Safety Flag Analysis

| Threshold | Total OOS Safety Flags |
|---:|---:|
| 0.00400 | 4 |
| 0.00500 | 4 |
| 0.00600 | 3 |
| **0.00649** | **1** |
| 0.00700 | 2 |
| 0.00800 | 0 |

## Verdict

**THRESHOLD_NATURAL**

### Reasoning

- Warning: ['WF3'] has insufficient data (< 20 trades). Verdict based on remaining windows.
- WF1: best threshold=0.00700 (ER=2.798, trades=88)
- WF2: best threshold=0.00800 (ER=2.951, trades=22)
- WF1: baseline 0.00649 ranks #4 of 6
- WF2: baseline 0.00649 ranks #2 of 6
- Best-threshold spread across valid windows: 0.00100
- Baseline is top-3 in 1/2 valid windows. Threshold is reasonably stable.

### Limitations

- Windows with insufficient data excluded from verdict: ['WF3']
- Threshold grid is coarse (6 values, ~0.001 steps). Finer grid not tested.
- Walk-forward uses fixed 2-year train windows. Expanding/rolling window not tested.
- Market regime varies across windows (2022 bear vs 2024-2025 bull). Optimal threshold may legitimately vary with regime.

## Recommendation

Current threshold `0.00649` is stable across OOS windows. Do not adjust. Proceed to 30-day paper monitoring.

## Methodology

### Analysis Script

`research_lab/analysis_oos_wf_threshold_stability.py`

### Data Sources

- **Replay DB:** `research_lab/snapshots/replay-run13-regime-aware-trial-00063.db` (2020-09-01 to 2026-03-28)
- **Trial params:** `research_lab/research_lab.db.v3` (trial `optuna-default-v3-trial-00095`)

### Key Design Decisions

- **Ceteris paribus:** Only `min_sweep_depth_pct` varies. All other ~40 parameters are held at trial-00095 exact values. This isolates the threshold effect, addressing M2's cross-trial selection bias limitation.
- **OOS only as primary evidence:** Train/IS results are reported for context (degradation analysis) but NOT used for verdict determination.
- **No Optuna cross-trial analysis:** M2 audit identified this as selection bias. This milestone uses direct threshold manipulation instead.
