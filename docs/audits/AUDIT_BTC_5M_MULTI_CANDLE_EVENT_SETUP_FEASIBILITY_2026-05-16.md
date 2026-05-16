# AUDIT: BTC_5M_MULTI_CANDLE_EVENT_SETUP_FEASIBILITY_V1

Date: 2026-05-16
Auditor: Claude Code
Commit: 2e0679b
Branch: research/sweep-family-expansion-v1

## Verdict: ACCEPT

Implementation is methodologically sound and correctly executed. The hypothesis was properly tested and decisively falsified. Verdict `MULTI_CANDLE_FAIL` is supported by evidence.

## Layer Separation: PASS

- Research-only code isolated in `research_lab/`
- No production, PAPER, runtime, core, execution, or settings changes
- Imports clean: hypothesis specs, experiment logic, SQLite analysis only
- No dependency bleeding into bot runtime paths

## Contract Compliance: PASS

- Hypothesis specs follow `research_lab/hypotheses/spec.py` schema
- Both JSON files validated by `test_multi_candle_hypothesis_specs_are_valid()`
- Report follows standard contract from RESEARCH_AUTOMATION_FOUNDATION_LITE_V1
- Data manifests correctly documented (5m candles, OI, funding, force_orders)

## Determinism: PASS

- Event-window detection is deterministic (no randomness, no external API calls)
- Compression, reclaim, snapback logic uses only past data
- Tests verify no-lookahead constraints:
  - `test_reclaim_confirmation_starts_after_event_bar()` - confirmation window starts AFTER event
  - `test_is_compressed_uses_only_prior_widths()` - compression uses only prior bars
- One-position constraint implemented (skip signal if position open)

## State Integrity: PASS

- Read-only analysis: source DBs not modified
- Force-orders DB correctly loaded from `research_lab/data/crowded_unwind_backtest.db` (146,864 rows)
- Data mode correctly determined: `OI_FUNDING_FORCE_ORDERS` when all sources available
- No state corruption risk (offline script, no runtime integration)

## Error Handling: PASS

- DB file existence checks before queries
- Table existence validation (`force_orders` in sqlite_master)
- Data availability audit logged before analysis
- Graceful handling of missing force-orders (would fall back to proxy mode, but not needed here)

## Smoke Coverage: PASS

6 unit tests in `tests/test_research_lab_multi_candle_events.py`:
- `test_compute_range_uses_half_open_window()` - range calculation correctness
- `test_reclaim_confirmation_starts_after_event_bar()` - no-lookahead enforcement
- `test_reclaim_confirmation_times_out_without_future_reclaim()` - confirmation timeout logic
- `test_snapback_confirmation_uses_event_midpoint_after_event()` - snapback detection
- `test_is_compressed_uses_only_prior_widths()` - compression precondition integrity
- `test_multi_candle_hypothesis_specs_are_valid()` - hypothesis JSON validation

All tests verify event-window methodology correctness, not just implementation details.

## Tech Debt: LOW

No `NotImplementedError` stubs, no TODOs, no placeholder logic. Implementation complete for the tested scope.

Acknowledged limitations (documented in report):
- Simplified TP/SL simulation (no partial exits, no trailing, no funding accrual)
- Crowded unwind force-orders coverage ends 2024-12-01
- No official trial-00095 signal timestamps for direct overlap measurement

These are research scope boundaries, not implementation debt.

## AGENTS.md Compliance: PASS

- Commit discipline followed: "research: BTC_5M_MULTI_CANDLE_EVENT_SETUP_FEASIBILITY_V1 - compression fakeout reclaim + crowded unwind reversal"
- No production layer violations
- No timestamp manipulation
- Branch strategy correct (`research/sweep-family-expansion-v1`)

## Methodology Integrity: PASS

**No-lookahead discipline:**
- Event detection uses bar N data only
- Confirmation window starts at bar N+1 (after event close)
- Tests explicitly verify this constraint

**One-position constraint:**
- Skip new signal if position already open
- `overlap_skipped_count` tracked in signal funnels
- CFR_V3: 24 skipped, CUR_V1: 0 skipped (consistent with event spacing)

**Anti-overfit compliance:**
- All predefined variants reported (no cherry-picking)
- No parameter rescue after seeing results
- No gate relaxation to force a pass
- Both LONG and SHORT results shown (both negative)

**Walk-forward claims:**
- Report correctly states OOS validation performed
- Test ER remains negative/zero (CFR: -0.159, CUR: 0.000)
- No false claims of nested optimization or post-hoc fitting

## Promotion Safety: PASS

Hard gates correctly applied:
- min_trades >= 20: PASS for both setups
- min_er >= 1.0: FAIL (CFR: -0.192, CUR: -0.415)
- min_pf >= 1.5: FAIL (CFR: 0.371, CUR: 0.224)
- max_dd_ratio <= 1.5: FAIL (CFR: 3.128, CUR: 16.132)
- cost_sensitivity >= 0.5: FAIL (CFR: -0.495, CUR: -0.808)

Verdict `MULTI_CANDLE_FAIL` is blocking. No path to promotion exists. No soft warnings masquerading as vetos.

## Reproducibility & Lineage: PASS

- Data manifest hash: `ca7d6158606706dc`
- Analysis period: 2024-01-01 to 2026-03-28
- Baseline reference: trial-00095 M5 (same period)
- Git commit: 2e0679b
- Experiment IDs: `exp-3e43a9d6d5a174b4` (CFR), `exp-fcfe67f74a383d11` (CUR)
- Force-orders source: `research_lab/data/crowded_unwind_backtest.db` (146,864 rows, 2022-01-01 to 2024-12-01)
- Setup B data mode: `OI_FUNDING_FORCE_ORDERS`

All context needed to reproduce or compare experiments is explicit.

## Data Isolation: PASS

- Source DBs read-only: `research_lab/snapshots/btc_5m_2022_2026.db`, `research_lab/snapshots/replay_snapshot.db`, `research_lab/data/crowded_unwind_backtest.db`
- No modification of source data
- Results written to separate report file, not trial DB
- No experiment registry interaction (RESEARCH_AUTOMATION_FOUNDATION_LITE_V1 framework available but not used for this milestone)

## Search Space Governance: PASS

- Hypothesis specs define frozen_assumptions explicitly
- Variables predefined: compression_lookback [96, 144], range_lookback [24, 36, 48], reclaim_window [3, 4] for CFR
- Variables predefined: crowding_lookback [24, 48], forced_move_atr_mult [1.5, 2.0], snapback_window [3, 4], min_force_z [2.0, 2.5] for CUR
- No parameter rescue after results
- All variants tested and reported (6 total: 3 CFR + 3 CUR)

## Artifact Consistency: PASS

Report tells consistent story:
- Frequency gates passed (1.55x, 3.70x vs baseline 47 trades)
- Quality gates catastrophically failed (ER negative, PF < 0.5, DD 3-16x baseline)
- Both LONG and SHORT directions negative (not direction bias)
- OOS validation confirms failure (test ER negative/zero)
- Verdict MULTI_CANDLE_FAIL is the only correct conclusion

Hypothesis specs, test coverage, analysis script, and final report all align.

## Boundary Coupling: PASS

- No `backtest/` dependency
- No `settings.py` interaction
- Research lab owns hypothesis specs, experiment logic, and offline analysis
- Force-orders data sourced from standalone DB, not runtime state
- Clear boundary: this is offline research, not candidate promotion path

---

## Critical Issues

None.

## Warnings

None.

## Observations

### Force-Orders Correction Was Material

Initial implementation used volume/range proxy for Setup B precondition. User flagged that historical force_orders exist in separate database. Codex corrected to load 146,864 force-order rows from `research_lab/data/crowded_unwind_backtest.db` (2022-2024 coverage).

**Impact:** Setup B data quality improved from proxy to real force-order filtering, but results remained decisively negative (ER -0.415, PF 0.224, DD 72.4R). This confirms the pattern has no edge even with high-quality precondition data.

### Strategic Implications: 5m Research Path Closed

This is the third major 5m study, all failures:
1. **BTC_5M_SWEEP_RECLAIM_FEASIBILITY_V1 (M5):** Frequency fail (1.30x < 2.0x gate)
2. **15M_SIGNAL_5M_ENERGY_OVERLAY_FEASIBILITY (M6):** Quality fail (ER degrades, 78-91% timeout)
3. **BTC_5M_MULTI_CANDLE_EVENT_SETUP_FEASIBILITY_V1 (M7):** Quality catastrophic fail (negative ER, DD 3-16x baseline)

Combined conclusion: **5m resolution does not solve BTC frequency problem.** Multi-candle event windows increased detection frequency but destroyed edge quality. The patterns tested (compression fakeout reclaim, crowded unwind reversal) have negative expectancy.

Three research paths now exhausted:
- Threshold optimization (degrades quality)
- 5m resolution (all variants failed)
- Context expansion (0% success rate)

### Direction Split: Both LONG and SHORT Negative

- CFR LONG: ER -0.147, PF 0.456
- CFR SHORT: ER -0.250, PF 0.287
- CUR LONG: ER -0.363, PF 0.278
- CUR SHORT: ER -0.499, PF 0.148

This is not a direction bias issue. The patterns themselves have no edge in either direction.

### Concentration: PASS (not a fragility issue)

- CFR max month: 16.3% (2025-07)
- CFR max day: 5.2% (2024-06-29)
- CUR max month: 16.0% (2024-06)
- CUR max day: 5.7% (2024-09-26)

Concentration gates passed (< 60% month, < 40% day), but this is irrelevant given negative ER. If these patterns had positive edge, concentration would be acceptable.

---

## Recommended Next Step

**ACCEPT and CLOSE milestone.** Implementation is correct. Hypothesis was properly tested and decisively falsified. Verdict `MULTI_CANDLE_FAIL` is methodologically sound and supported by evidence.

**Strategic recommendation:** Wait for M4 near-miss monitoring checkpoint (2026-06-13, 29 days remaining), then decide between:
- **Option A:** Continue monitoring (if M4 reveals actionable sweep-depth regime shift)
- **Option B:** ETH multi-asset feasibility study (test if low-frequency issue is BTC-specific)
- **Option C:** Accept current frequency, focus on live validation of trial-00095

Do NOT attempt to rescue 5m multi-candle setups by expanding parameter grid. The patterns have negative edge.

---

**Audit status:** DONE
**Milestone status:** CLOSED
**Branch recommendation:** Merge research branch after updating MILESTONE_TRACKER.md, or keep open for M4 checkpoint if user prefers single research branch
