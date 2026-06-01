# OANDA_SESSION_EDGE_RECONNAISSANCE_V1

**Date:** 2026-06-01T13:24:30.874202+00:00
**Type:** OANDA-native session edge reconnaissance; not a profitability diagnostic
**Recommendation:** PROCEED_TO_FULL_PLANNING

## 1. Executive Summary

This report evaluates OANDA-native session structure after direct sweep/reclaim transfer was invalidated.
It does not rescue sweep/reclaim, does not use SMC logic, does not run Optuna, and does not modify production code.

Result: `PROCEED_TO_FULL_PLANNING`.

Multiple candidates passed structure gates; highest-ranked is ASIA_RANGE_LONDON_BREAKOUT with 424 events and 4/4 stable folds.

## 2. Prior OANDA Research Boundary

- `XAU_USD H1` strict BTC sweep/reclaim transfer remains `STOP` due sample collapse.
- `EUR_USD M15` same-bar sweep/reclaim remains `STOP` due negative expectancy and control outperformance.
- This milestone tests session-driven forex structure only.
- Any future edge claim requires a separate full planning document and diagnostic.

## 3. Data Inventory

| Instrument | Candles | First | Last | OHLC Bad | Duplicates | Gaps >72h | Max Gap Hours | Gate |
| --- | ---: | --- | --- | ---: | ---: | ---: | ---: | --- |
| `EUR_USD` | 59989 | 2024-01-01T22:00:00+00:00 | 2026-05-29T20:45:00+00:00 | 0 | 0 | 0 | 49.25 | `PASS` |
| `XAU_USD` | 57002 | 2024-01-01T23:00:00+00:00 | 2026-05-29T20:45:00+00:00 | 0 | 0 | 3 | 73.25 | `PASS` |

## 4. Fixed Session Definitions

| Session | UTC Window | Purpose |
| --- | --- | --- |
| `asia_range` | 00:00-07:00 | Compression / range formation |
| `london_open` | 07:00-09:00 | Early European volatility expansion |
| `london_continuation` | 09:00-12:00 | London follow-through |
| `new_york_overlap` | 13:00-16:00 | Institutional overlap / reversal or continuation |
| `rollover` | 21:00-23:00 | Illiquid window / fade or avoidance |

## 5. Candidate Mechanism Definitions

- `ASIA_RANGE_LONDON_BREAKOUT`: Asia range from 00:00-07:00, breakout close during 07:00-09:00.
- `LONDON_OPEN_RANGE_BREAKOUT`: 07:00-08:00 opening range, breakout during 08:00-12:00.
- `NY_REVERSAL_AFTER_LONDON_EXTENSION`: London 07:00-12:00 extension, reversal confirmation during 13:00-16:00.
- `ROLLOVER_FADE_OR_AVOIDANCE`: 19:00-21:00 pre-rollover range, fade breakout during 21:00-23:00.

## 6. Structural Frequency Matrix

### EUR_USD M15

| Candidate | Count | Events/yr | Follow-through | False breakout | Median MFE consumed | Stable folds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `ASIA_RANGE_LONDON_BREAKOUT` | 424 | 176.4 | 84.43% | 18.16% | 11.54% | 4 / 4 |
| `LONDON_OPEN_RANGE_BREAKOUT` | 587 | 244.2 | 79.90% | 25.21% | 14.12% | 4 / 4 |
| `NY_REVERSAL_AFTER_LONDON_EXTENSION` | 367 | 152.7 | 84.74% | 19.07% | 16.46% | 4 / 4 |
| `ROLLOVER_FADE_OR_AVOIDANCE` | 228 | 94.8 | 82.46% | 28.51% | 36.36% | 4 / 4 |

### XAU_USD M15 (comparison only)

| Candidate | Count | Events/yr | Follow-through | False breakout | Median MFE consumed | Stable folds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `ASIA_RANGE_LONDON_BREAKOUT` | 277 | 115.2 | 85.92% | 18.41% | 12.55% | 4 / 4 |
| `LONDON_OPEN_RANGE_BREAKOUT` | 587 | 244.2 | 77.34% | 25.55% | 14.48% | 4 / 4 |
| `NY_REVERSAL_AFTER_LONDON_EXTENSION` | 368 | 153.1 | 82.88% | 19.57% | 17.64% | 4 / 4 |
| `ROLLOVER_FADE_OR_AVOIDANCE` | 197 | 82.0 | 82.74% | 26.90% | 37.06% | 3 / 4 |

## 7. Range and Volatility Analysis

| Instrument | Candidate | Median Range % | Median Range ATR |
| --- | --- | ---: | ---: |
| `EUR_USD` | `ASIA_RANGE_LONDON_BREAKOUT` | 0.1856% | 5.31 |
| `EUR_USD` | `LONDON_OPEN_RANGE_BREAKOUT` | 0.1286% | 2.67 |
| `EUR_USD` | `NY_REVERSAL_AFTER_LONDON_EXTENSION` | 0.2764% | 4.83 |
| `EUR_USD` | `ROLLOVER_FADE_OR_AVOIDANCE` | 0.0884% | 2.17 |
| `XAU_USD` | `ASIA_RANGE_LONDON_BREAKOUT` | 0.5988% | 5.74 |
| `XAU_USD` | `LONDON_OPEN_RANGE_BREAKOUT` | 0.2697% | 2.07 |
| `XAU_USD` | `NY_REVERSAL_AFTER_LONDON_EXTENSION` | 0.5777% | 4.48 |
| `XAU_USD` | `ROLLOVER_FADE_OR_AVOIDANCE` | 0.2435% | 2.34 |

## 8. Breakout / Reversal Behavior

| Instrument | Candidate | Count | Follow-through | False breakout | Direction counts |
| --- | --- | ---: | ---: | ---: | --- |
| `EUR_USD` | `ASIA_RANGE_LONDON_BREAKOUT` | 424 | 84.43% | 18.16% | `{'SHORT': 203, 'LONG': 221}` |
| `EUR_USD` | `LONDON_OPEN_RANGE_BREAKOUT` | 587 | 79.90% | 25.21% | `{'SHORT': 289, 'LONG': 298}` |
| `EUR_USD` | `NY_REVERSAL_AFTER_LONDON_EXTENSION` | 367 | 84.74% | 19.07% | `{'SHORT': 178, 'LONG': 189}` |
| `EUR_USD` | `ROLLOVER_FADE_OR_AVOIDANCE` | 228 | 82.46% | 28.51% | `{'LONG': 76, 'SHORT': 152}` |
| `XAU_USD` | `ASIA_RANGE_LONDON_BREAKOUT` | 277 | 85.92% | 18.41% | `{'LONG': 158, 'SHORT': 119}` |
| `XAU_USD` | `LONDON_OPEN_RANGE_BREAKOUT` | 587 | 77.34% | 25.55% | `{'SHORT': 275, 'LONG': 312}` |
| `XAU_USD` | `NY_REVERSAL_AFTER_LONDON_EXTENSION` | 368 | 82.88% | 19.57% | `{'LONG': 165, 'SHORT': 203}` |
| `XAU_USD` | `ROLLOVER_FADE_OR_AVOIDANCE` | 197 | 82.74% | 26.90% | `{'SHORT': 132, 'LONG': 65}` |

## 9. MFE Accessibility

| Instrument | Candidate | Median MFE Consumed | Median MFE After Entry | Median MAE After Entry |
| --- | --- | ---: | ---: | ---: |
| `EUR_USD` | `ASIA_RANGE_LONDON_BREAKOUT` | 11.54% | 0.000855 | 0.000915 |
| `EUR_USD` | `LONDON_OPEN_RANGE_BREAKOUT` | 14.12% | 0.000760 | 0.000900 |
| `EUR_USD` | `NY_REVERSAL_AFTER_LONDON_EXTENSION` | 16.46% | 0.001120 | 0.001100 |
| `EUR_USD` | `ROLLOVER_FADE_OR_AVOIDANCE` | 36.36% | 0.000495 | 0.000355 |
| `XAU_USD` | `ASIA_RANGE_LONDON_BREAKOUT` | 12.55% | 5.250000 | 4.775000 |
| `XAU_USD` | `LONDON_OPEN_RANGE_BREAKOUT` | 14.48% | 4.795000 | 5.820000 |
| `XAU_USD` | `NY_REVERSAL_AFTER_LONDON_EXTENSION` | 17.64% | 8.550000 | 9.400000 |
| `XAU_USD` | `ROLLOVER_FADE_OR_AVOIDANCE` | 37.06% | 4.485000 | 4.115000 |

## 10. False Breakout and Follow-Through

- False breakout: closes back inside source range within `4` bars and fails to make `0.5 * ATR14` favorable excursion.
- Follow-through: reaches `0.5 * ATR14` favorable excursion within `8` bars after entry candidate.
- Entry candidate is always the next bar open after state-known close.

### EUR_USD ASIA_RANGE_LONDON_BREAKOUT

| Fold | Count | Follow-through | False breakout | Median MFE consumed | Stable |
| --- | ---: | ---: | ---: | ---: | --- |
| `fold_1_2024H1` | 98 | 83.67% | 17.35% | 9.25% | True |
| `fold_2_2024H2` | 101 | 89.11% | 13.86% | 10.61% | True |
| `fold_3_2025` | 160 | 82.50% | 20.00% | 13.94% | True |
| `fold_4_2026` | 65 | 83.08% | 21.54% | 12.37% | True |

### EUR_USD NY_REVERSAL_AFTER_LONDON_EXTENSION

| Fold | Count | Follow-through | False breakout | Median MFE consumed | Stable |
| --- | ---: | ---: | ---: | ---: | --- |
| `fold_1_2024H1` | 74 | 90.54% | 12.16% | 14.76% | True |
| `fold_2_2024H2` | 82 | 86.59% | 14.63% | 16.49% | True |
| `fold_3_2025` | 153 | 81.70% | 22.22% | 16.67% | True |
| `fold_4_2026` | 58 | 82.76% | 25.86% | 19.37% | True |

### EUR_USD LONDON_OPEN_RANGE_BREAKOUT

| Fold | Count | Follow-through | False breakout | Median MFE consumed | Stable |
| --- | ---: | ---: | ---: | ---: | --- |
| `fold_1_2024H1` | 124 | 87.90% | 15.32% | 9.18% | True |
| `fold_2_2024H2` | 121 | 79.34% | 27.27% | 14.81% | True |
| `fold_3_2025` | 241 | 80.50% | 24.48% | 13.92% | True |
| `fold_4_2026` | 101 | 69.31% | 36.63% | 17.24% | True |

### EUR_USD ROLLOVER_FADE_OR_AVOIDANCE

| Fold | Count | Follow-through | False breakout | Median MFE consumed | Stable |
| --- | ---: | ---: | ---: | ---: | --- |
| `fold_1_2024H1` | 41 | 82.93% | 31.71% | 36.36% | True |
| `fold_2_2024H2` | 44 | 81.82% | 29.55% | 29.73% | True |
| `fold_3_2025` | 98 | 81.63% | 27.55% | 38.05% | True |
| `fold_4_2026` | 45 | 84.44% | 26.67% | 38.19% | True |

## 11. Direction / Weekday / Session Splits

### EUR_USD

- `ASIA_RANGE_LONDON_BREAKOUT` direction counts: `{'SHORT': 203, 'LONG': 221}`; weekday counts: `{'Tuesday': 88, 'Wednesday': 82, 'Thursday': 76, 'Friday': 93, 'Monday': 85}`
- `LONDON_OPEN_RANGE_BREAKOUT` direction counts: `{'SHORT': 289, 'LONG': 298}`; weekday counts: `{'Tuesday': 116, 'Wednesday': 118, 'Thursday': 118, 'Friday': 116, 'Monday': 119}`
- `NY_REVERSAL_AFTER_LONDON_EXTENSION` direction counts: `{'SHORT': 178, 'LONG': 189}`; weekday counts: `{'Thursday': 63, 'Friday': 87, 'Monday': 69, 'Tuesday': 72, 'Wednesday': 76}`
- `ROLLOVER_FADE_OR_AVOIDANCE` direction counts: `{'LONG': 76, 'SHORT': 152}`; weekday counts: `{'Tuesday': 55, 'Friday': 19, 'Wednesday': 51, 'Thursday': 51, 'Monday': 52}`

### XAU_USD

- `ASIA_RANGE_LONDON_BREAKOUT` direction counts: `{'LONG': 158, 'SHORT': 119}`; weekday counts: `{'Thursday': 56, 'Tuesday': 64, 'Wednesday': 53, 'Friday': 55, 'Monday': 49}`
- `LONDON_OPEN_RANGE_BREAKOUT` direction counts: `{'SHORT': 275, 'LONG': 312}`; weekday counts: `{'Tuesday': 120, 'Wednesday': 119, 'Thursday': 116, 'Friday': 115, 'Monday': 117}`
- `NY_REVERSAL_AFTER_LONDON_EXTENSION` direction counts: `{'LONG': 165, 'SHORT': 203}`; weekday counts: `{'Thursday': 76, 'Friday': 64, 'Monday': 73, 'Tuesday': 75, 'Wednesday': 80}`
- `ROLLOVER_FADE_OR_AVOIDANCE` direction counts: `{'SHORT': 132, 'LONG': 65}`; weekday counts: `{'Thursday': 44, 'Friday': 12, 'Sunday': 7, 'Wednesday': 44, 'Tuesday': 39, 'Monday': 51}`

## 12. Candidate Ranking

| Rank | Candidate | Score | Count | Follow-through | False breakout | Median MFE Consumed | Stable folds |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | `ASIA_RANGE_LONDON_BREAKOUT` | 7.820 | 424 | 84.43% | 18.16% | 11.54% | 4 / 4 |
| 2 | `NY_REVERSAL_AFTER_LONDON_EXTENSION` | 7.533 | 367 | 84.74% | 19.07% | 16.46% | 4 / 4 |
| 3 | `LONDON_OPEN_RANGE_BREAKOUT` | 7.305 | 587 | 79.90% | 25.21% | 14.12% | 4 / 4 |
| 4 | `ROLLOVER_FADE_OR_AVOIDANCE` | 5.971 | 228 | 82.46% | 28.51% | 36.36% | 4 / 4 |

## 13. Future Controls

If a candidate proceeds to full planning, future controls should include:

1. Random session timing.
2. Opposite direction entry.
3. Same breakout rule outside target session.
4. Breakout without compression.
5. Compression without breakout.
6. Shifted entry +2 bars.
7. Weekday-shuffled control.
8. Previous-day range breakout control.

## 14. Recommendation

### Verdict: PROCEED_TO_FULL_PLANNING

**Reason:** Multiple candidates passed structure gates; highest-ranked is ASIA_RANGE_LONDON_BREAKOUT with 424 events and 4/4 stable folds.

**Next:** Create a full planning document for `ASIA_RANGE_LONDON_BREAKOUT`. This reconnaissance does not prove edge.

## Artifact

- JSON path: `C:/development/btc-bot/research_lab/reports/oanda_session_edge_reconnaissance_v1.json`
- JSON SHA256: `eb5870b447f2ce7a12c9594ac7f069cf83116625a9ca7c4bd75bfd429d258bc3`
