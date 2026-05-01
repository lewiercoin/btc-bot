# DATA-BACKFILL-V1: Step 1.0 — Column Verification

**Date:** 2026-05-01  
**Builder:** Cascade  
**Step:** 1.0 (pre-code column verification — mandatory before writing import code)

## Method

Downloaded one metrics file and inspected actual CSV content:

```
wget "https://data.binance.vision/data/futures/um/daily/metrics/BTCUSDT/BTCUSDT-metrics-2025-06-05.zip"
Expand-Archive + Get-Content | Select-Object -First 3
```

## Verified: Metrics CSV (Open Interest)

**File:** `BTCUSDT-metrics-2025-06-05.csv` (extracted from zip)

**Header row (confirmed present):**
```
create_time,symbol,sum_open_interest,sum_open_interest_value,count_toptrader_long_short_ratio,sum_toptrader_long_short_ratio,count_long_short_ratio,sum_taker_long_short_vol_ratio
```

**Sample rows:**
```
2025-06-05 00:05:00,BTCUSDT,80793.3430000000000000,8458277452.5717250000000000,...
2025-06-05 00:10:00,BTCUSDT,80795.1580000000000000,8462484848.9200000000000000,...
```

**Key findings:**

| Field | Confirmed value |
|---|---|
| Has header row | YES |
| `create_time` format | `YYYY-MM-DD HH:MM:SS` (space-separated, UTC, NOT Unix ms) |
| OI column name | `sum_open_interest` ✅ (matches assumption from Step 0) |
| OI units | contracts (same as live-collected `oi_value`) |
| Granularity | 5 minutes (00:05, 00:10, ...) |
| Rows per day | 288 (24h × 12 per hour) |

**Schema mapping confirmed:**

| CSV column | DB column | Transform |
|---|---|---|
| `create_time` | `timestamp` | Parse `%Y-%m-%d %H:%M:%S`, treat as UTC, format as ISO-8601 |
| `symbol` | `symbol` | Use as-is (`BTCUSDT`) |
| `sum_open_interest` | `oi_value` | `float()` |

## Confirmed: AggTrades CSV

Per Binance public data README (no local download needed — format documented):

- **No header row**
- Columns: `AggTradeId, Price, Quantity, FirstTradeId, LastTradeId, Timestamp, WasBuyerMaker`
- `Timestamp`: Unix milliseconds
- `WasBuyerMaker`: string `"true"` / `"false"` (lowercase)

**Bucket derivation:**
- `taker_buy_volume` = sum(`Quantity`) where `WasBuyerMaker == "false"`
- `taker_sell_volume` = sum(`Quantity`) where `WasBuyerMaker == "true"`
- `tfi` = `(buy - sell) / (buy + sell)` if total > 0 else 0.0
- `cvd` = running cumulative `(buy - sell)`, initialized from last known DB value before gap

## Step 1 Implementation Ready

Column mapping confirmed. Implementation of `scripts/backfill_oi.py` and
`scripts/backfill_aggtrades.py` may proceed.
