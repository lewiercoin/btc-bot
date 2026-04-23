# Feature Drift Report

Status date: 2026-04-23
Status type: initial V3 baseline

## Current status

This repository now contains:
- `market_snapshots` persistence
- `feature_snapshots` persistence
- `validation/recompute_features.py`

What it does **not** yet contain is a populated production sample from the new tables. Because of that, a 200-cycle drift report cannot be produced yet from live runtime data.

## Thresholds

- ATR fields: 2.0%
- EMA fields: 1.0%
- TFI / force-order / reclaim-distance diagnostics: 5.0%

## Current verdict

- `atr_15m`: N/A
- `atr_4h`: N/A
- `atr_4h_norm`: N/A
- `ema50_4h`: N/A
- `ema200_4h`: N/A
- `tfi_60s`: N/A
- `force_order_rate_60s`: N/A

Overall status: **WARNING**

Reason:
- the recompute engine exists,
- unit/integration round-trip passes locally,
- production has not yet accumulated V3 `market_snapshots` / `feature_snapshots`.

## Regeneration command

After deployment and after at least 200 cycles are captured:

```bash
c:\development\btc-bot\.venv\Scripts\python.exe validation\recompute_features.py --db storage\btc_bot.db --limit 200 --markdown-out validation\feature_drift_report.md
```
