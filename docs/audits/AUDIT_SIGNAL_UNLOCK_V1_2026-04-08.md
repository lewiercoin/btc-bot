# AUDIT: SIGNAL-UNLOCK-V1
Date: 2026-04-08
Auditor: Claude Code
Commit: (pre-commit — audited from working tree)

## Verdict: DONE

All 5 deliverables correct. Architecture sound. 58/58 tests green. Default behaviour unchanged.

## Layer Separation: PASS
`signal_engine.py` untouched logically. Whitelist composition delegated to builders (orchestrator, backtest_runner) and helper `build_signal_regime_direction_whitelist()` in `settings.py`. Clean separation.

## Contract Compliance: PASS
`StrategyConfig` extended with `allow_long_in_uptrend: bool = False`. Default preserves full backward compatibility — existing smoke tests pass without modification. `build_signal_regime_direction_whitelist()` is additive: only appends LONG to uptrend tuple when flag is True.

## Determinism: PASS
`build_signal_regime_direction_whitelist()` is a pure function — same input always produces same whitelist. No hidden state.

## State Integrity: PASS
## Error Handling: PASS

## Smoke Coverage: PASS
- 58/58 pytest green
- `smoke_config_injection.py` updated to cover new field
- `smoke_phase_c.py` passes
- Research lab smoke: 3-trial optimize run samples `allow_long_in_uptrend` as both True and False — confirmed active in Optuna

## Tech Debt: LOW

## AGENTS.md Compliance: PASS
No self-commit. Awaiting Claude Code audit before committing.

## Methodology Integrity: PASS
`ema_trend_gap_pct` and `compression_atr_norm_max` correctly unfrozen — ranges already existed in `_RANGE_OVERRIDES`. No methodology scope change.

## Promotion Safety: PASS
## Reproducibility & Lineage: PASS
`allow_long_in_uptrend` is part of `StrategyConfig` which feeds into `config_hash` — any candidate with this flag set will have a different hash than baseline. Lineage preserved.

## Data Isolation: PASS
## Search Space Governance: PASS
Five range overrides narrowed as specified. `allow_long_in_uptrend` correctly ACTIVE as bool. `regime_direction_whitelist` remains FROZEN (composite type — correct). `ema_trend_gap_pct` and `compression_atr_norm_max` correctly removed from `_FROZEN_REASONS`.

## Artifact Consistency: PASS
## Boundary Coupling: PASS

---

## Critical Issues

None.

---

## Warnings

None.

---

## Observations

### O1 — `allow_long_in_uptrend` position in StrategyConfig

Field is placed before `regime_direction_whitelist` (line 87). This is correct — `build_signal_regime_direction_whitelist()` reads it before composing the whitelist. No issue.

### O2 — `direction_tfi_threshold_inverse` remains FROZEN

`direction_tfi_threshold_inverse` is frozen as "derived constraint; changes with direction_tfi_threshold". Now that `direction_tfi_threshold` range is narrowed to 0.01–0.5 (positive only), `direction_tfi_threshold_inverse` should always equal `-direction_tfi_threshold`. The freeze is correct — but the settings_adapter should ensure this derived relationship is maintained when building candidate settings. Worth verifying in next research lab milestone.

### O3 — `equal_level_tol_atr` range narrowed but sweep=99.49% issue unresolved

Range narrowed from 0.01–1.0 to 0.01–0.3. This helps Optuna avoid degenerate high-tolerance configs. The underlying sweep semantics (99.49% True) is deferred to next milestone — correctly scoped out of this milestone.

---

## Recommended Next Step

Commit, push, then run optimize run #3 on server with updated code (`git pull` on server first). This will be the first run with `allow_long_in_uptrend` available to Optuna and unfrozen regime thresholds. Expected: meaningfully higher trial acceptance rate and more trades per candidate.
