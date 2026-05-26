# PC Deep Research Status

Date: 2026-05-26
Machine: DESKTOP-M9HEH95
Branch: deploy/multi-asset-paper-v1
Milestone: DEEP_HISTORICAL_THRESHOLD_ATTRIBUTION_V1

## Command

```powershell
.\.venv\Scripts\python.exe research_lab\analysis_deep_threshold_attribution.py --start-date 2022-01-01 --end-date 2026-05-24
```

Run mode: without `--force`.

## Status

- full research completed
- no production access used
- no threshold/config production change made
- no database backfill run
- `storage\btc_bot.db` was not committed
- large JSON run artifacts were not committed

## Runtime Note

The first attempt failed with `MemoryError` in `backtest/replay_loader.py` while materializing all multi-year BTC snapshots in memory.

Resolution used for this run:

- `scripts/run_runtime_parity_backtest.py` now streams snapshots for single-symbol runs.
- Multi-symbol behavior remains on the existing preloaded path.
- Validation after the change:
  - `py_compile`: passed
  - `tests\test_runtime_parity_cost_model.py`: 4 passed

## Result Artifacts

Local generated artifacts:

- `research_lab\analysis_output\deep_threshold_attribution_btc_2022_2026.json`
- `research_lab\reports\deep_threshold_attribution_btc_2022_2026.md`
- `research_lab\analysis_output\deep_threshold_attribution_runs\BTC_FIXED_*_20220101_20260524.json`

These artifacts are intentionally not committed except for this small communication summary.

## Threshold Summary

| threshold | trades | net_pnl_r | net_er | win_rate | profit_factor |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0.0035 | 12 | -14.3741 | -1.1978 | 0.0833 | 0.2126 |
| 0.0040 | 12 | -14.3741 | -1.1978 | 0.0833 | 0.2126 |
| 0.0045 | 12 | -8.1491 | -0.6791 | 0.1667 | 0.5082 |
| 0.0050 | 12 | -8.1491 | -0.6791 | 0.1667 | 0.5082 |
| 0.0060 | 51 | 59.6656 | 1.1699 | 0.3725 | 2.1406 |
| 0.00649 | 48 | 46.8318 | 0.9757 | 0.3542 | 1.9261 |

## Initial Read

- Shallow thresholds from `0.0035` through `0.0050` were negative net after costs.
- The current deeper baseline zone around `0.0060` to `0.00649` remained positive in this multi-year runtime-parity run.
- The generated research report notes that trade-level reclaim speed/depth is not yet persisted by parity output, so attribution is limited to available entry features.

## Warnings

The run emitted NumPy `RuntimeWarning: invalid value encountered in divide` during correlation calculations on small/constant shallow samples. The run still completed and wrote final JSON/report artifacts.
