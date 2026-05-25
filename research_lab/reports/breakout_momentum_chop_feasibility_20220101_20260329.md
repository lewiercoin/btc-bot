# Breakout/Momentum CHOP Feasibility

Research-only checkpoint. This tests whether Choppiness Index improves a simple 15m breakout/momentum setup.

## Method

- Symbol: `BTCUSDT`
- Timeframe: `15m`
- Date range: `2022-01-01` to `2026-03-29`
- Candles loaded: `148595`
- Entry: next 15m open after a close breaks prior 48-bar high/low.
- Costs: taker entry, maker exit, 3 bps slippage per side; funding excluded in this first pass.
- CHOP meaning: low CHOP = directional/trending; high CHOP = range/chop.

## Results

| Config | Trades | Net ER | Net PnL R | Net PF | Win Rate | Median R | Avg Cost R | Max DD R | Candidates | CHOP Rejects |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `BMO_BASE_NO_CHOP` | 3004 | -0.3179 | -955.12 | 0.63 | 33.69% | -1.1763 | 0.3191 | 961.57 | 3004 | 0 |
| `BMO_CHOP_LOW_38_2` | 1649 | -0.2777 | -457.99 | 0.67 | 35.11% | -1.1704 | 0.3137 | 472.56 | 3853 | 2204 |
| `BMO_CHOP_TREND_45` | 2435 | -0.2971 | -723.33 | 0.65 | 34.25% | -1.1755 | 0.3180 | 734.00 | 3375 | 940 |
| `BMO_LONG_ONLY_CHOP_45` | 1304 | -0.3066 | -399.82 | 0.64 | 34.51% | -1.1818 | 0.3368 | 399.82 | 1762 | 458 |
| `BMO_SHORT_ONLY_CHOP_45` | 1132 | -0.2868 | -324.61 | 0.66 | 33.92% | -1.1684 | 0.2962 | 340.32 | 1614 | 482 |
| `BMO_STRICT_48_CHOP_45` | 1947 | -0.3047 | -593.16 | 0.64 | 34.00% | -1.1814 | 0.3198 | 598.81 | 2452 | 505 |
| `BMO_STRONG_48_CHOP_45` | 1509 | -0.2909 | -438.99 | 0.69 | 31.21% | -1.2317 | 0.3683 | 445.77 | 1738 | 229 |
| `BMO_STRUCT_96_CHOP_45` | 1248 | -0.1747 | -218.09 | 0.79 | 32.85% | -1.1638 | 0.2708 | 236.85 | 1490 | 242 |
| `BMO_STRUCT_96_LOW_CHOP` | 968 | -0.1262 | -122.12 | 0.85 | 34.50% | -1.1593 | 0.2739 | 145.08 | 1623 | 655 |

## Base Run By CHOP Bucket

| Bucket | Trades | Net ER | Net PnL R | Net PF | Win Rate | Median R |
|---|---:|---:|---:|---:|---:|---:|
| `high_chop` | 8 | -0.5927 | -4.74 | 0.41 | 25.00% | -1.2686 |
| `low_trend` | 1281 | -0.3039 | -389.33 | 0.64 | 34.27% | -1.1687 |
| `mid` | 1715 | -0.3271 | -561.04 | 0.62 | 33.29% | -1.1813 |

## Best Variant Direction Split: `BMO_STRUCT_96_LOW_CHOP`

| Direction | Trades | Net ER | Net PnL R | Net PF | Win Rate | Median R |
|---|---:|---:|---:|---:|---:|---:|
| `LONG` | 545 | -0.1955 | -106.53 | 0.77 | 33.21% | -1.1771 |
| `SHORT` | 423 | -0.0369 | -15.59 | 0.95 | 36.17% | -1.1351 |

## Interpretation

- CHOP is not a momentum signal by itself because it has no direction.
- Its useful role is a regime filter: low CHOP can mark cleaner continuation conditions, while high CHOP can warn that breakout entries are likely to chop back.
- This checkpoint should not be promoted. It is a feasibility screen for whether a proper breakout/momentum hypothesis deserves a stricter walk-forward study.
