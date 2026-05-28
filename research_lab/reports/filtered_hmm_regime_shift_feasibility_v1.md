# FILTERED_HMM_REGIME_SHIFT_FEASIBILITY_V1 — Diagnostic Report

Generated: 2026-05-28T20:34:45.409698+00:00
Recommendation: **STOP**

## Data Quality

- Total bars: 195347
- Range: 2020-09-01T00:00:00+00:00 to 2026-03-28T20:30:00+00:00
- Gaps: 0
- OHLC violations: 0
- Zero-volume bars: 10

## HMM Configuration

- States: 2
- Covariance type: `diag`
- Training window: 500 bars
- Retrain interval: 100 bars
- Random seed: 42
- Probability threshold: 0.7

## Training Statistics

- Total retrains: 1952
- Failed retrains: 0
- Ambiguous retrains: 170
- State interpretation flips: 787

## Timing Model

- Detection bar: i
- State known bar: i (at close)
- Entry candidate bar: i+1
- Return start bar: i+1
- Primary returns from detection bar: False

## Main Cohort Metrics

- Event count: 5062
- Expectancy ratio (ER): -0.1221
- Profit factor (PF): 0.7920
- Median net return: -0.1839%
- Mean net return: -0.1307%
- Win rate: 0.4131
- Avg win: 1.2051%
- Avg loss: 1.0709%
- Win/loss ratio: 1.1253

## MFE Accessibility

- Median MFE consumed before entry: 22.8%
- Median HMM lag (bars): 37.0
- Median lag-adjusted MFE consumed: 60.8%

## Control Cohort Comparison

| Cohort | Count | ER | PF | Median Net | Win Rate |
| --- | ---: | ---: | ---: | ---: | ---: |
| `main_hmm_filtered` | 5062 | -0.1221 | 0.7920 | -0.1839% | 0.4131 |
| `control_simple_volatility` | 449 | 0.0223 | 1.0420 | -0.0559% | 0.4699 |
| `control_adx_chop` | 321 | -0.0263 | 0.9538 | -0.1811% | 0.4299 |
| `control_wrong_interpretation` | 4790 | -0.1168 | 0.7986 | -0.1873% | 0.4200 |
| `control_shifted_entry` | 5061 | -0.1134 | 0.8052 | -0.1744% | 0.4181 |
| `control_random_offset` | 4911 | -0.0926 | 0.8335 | -0.0982% | 0.4437 |
| `control_smoothed_audit` | 0 | n/a | n/a | n/a% | n/a |

## Benchmark Comparison

- Trial-00095 reference: ER=2.1, PF=4.6
- ADX/CHOP reference: ER=-0.027, PF=0.954 (STOP)

## Walk-Forward Metrics

| Fold | Count | ER | Median Net | Win Rate | Positive |
| --- | ---: | ---: | ---: | ---: | --- |
| `fold_1` | 1424 | -0.1326 | -0.2446% | 0.4136 | `False` |
| `fold_2` | 1655 | -0.1280 | -0.2019% | 0.3952 | `False` |
| `fold_3` | 1201 | -0.0949 | -0.1132% | 0.4363 | `False` |
| `fold_4` | 782 | -0.1183 | -0.1635% | 0.4143 | `False` |

## Seed Sensitivity

- Verdict consistent across seeds: `True`

| Seed | Count | ER | PF | Recommendation |
| ---: | ---: | ---: | ---: | --- |
| 0 | 8670 | -0.1157 | 0.8023 | `STOP` |
| 123 | 8699 | -0.1186 | 0.7972 | `STOP` |
| 456 | 8711 | -0.1215 | 0.7931 | `STOP` |

## Invalidation Gate Evaluation

- Recommendation: `STOP`
- STOP reasons: `['median_net_return=-0.1839% <= 0', 'ER=-0.1221 < 1.2', 'PF=0.7920 < 1.2', 'control_simple_volatility (ER=0.0223) beats main (ER=-0.1221)', 'control_adx_chop (ER=-0.0263) beats main (ER=-0.1221)', 'control_wrong_interpretation (ER=-0.1168) beats main (ER=-0.1221)', 'control_shifted_entry (ER=-0.1134) beats main (ER=-0.1221)', 'control_random_offset (ER=-0.0926) beats main (ER=-0.1221)', 'walk_forward: 0/4 folds positive < 2', 'state_interpretation_flips=787/1952 (40.3%) > 30%']`
- EXPLORE gate passed: `True`
- Walk-forward: 0/4 folds positive
- State flip rate: 40.3%

## Artifact

- JSON path: `C:\development\btc-bot\research_lab\reports\filtered_hmm_regime_shift_feasibility_v1.json`
- JSON SHA256: `DE460FBFC47A98DDF4447E1656826C8B937B2CFD90B6BDDB87313E467C8D4648`

## Recommendation: STOP

**Reason:** median_net_return=-0.1839% <= 0; ER=-0.1221 < 1.2; PF=0.7920 < 1.2; control_simple_volatility (ER=0.0223) beats main (ER=-0.1221); control_adx_chop (ER=-0.0263) beats main (ER=-0.1221); control_wrong_interpretation (ER=-0.1168) beats main (ER=-0.1221); control_shifted_entry (ER=-0.1134) beats main (ER=-0.1221); control_random_offset (ER=-0.0926) beats main (ER=-0.1221); walk_forward: 0/4 folds positive < 2; state_interpretation_flips=787/1952 (40.3%) > 30%

**Next:** Claude Code audits this diagnostic implementation and result before any follow-up work.
