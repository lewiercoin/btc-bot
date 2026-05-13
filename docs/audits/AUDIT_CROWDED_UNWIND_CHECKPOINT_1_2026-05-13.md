# AUDIT: CROWDED-UNWIND-CHECKPOINT-1

Date: 2026-05-13  
Auditor: Claude Code  
Commit: `30ba876` - `research: add crowded unwind checkpoint 1`  
Branch: `research/crowded-unwind-v1`

## Verdict: HYPOTHESIS FAILED

## Layer Separation: PASS
- Research-only setups isolated in `research_lab/setups/crowded_unwind.py`
- No production path contamination
- Clean imports from `core.models`, `backtest/`, `research_lab/`
- Research DB copy (`research_lab/data/crowded_unwind_backtest.db`) kept separate from `storage/btc_bot.db`

## Contract Compliance: PASS
- `CrowdedUnwindLong` and `CrowdedUnwindShort` inherit from `BaseSetup`
- `evaluate_structure()` and `generate_signal_candidate()` implemented correctly
- Returns `SignalCandidate` with all required fields
- Reasons array populated with signal context

## Determinism: PASS
- Setup logic is deterministic (no random state, no external API calls)
- Decisions driven by features, snapshot, regime only
- Confluence scoring and threshold checks are reproducible

## State Integrity: PASS
- Backtest uses research-only DB copy, does not mutate original `storage/btc_bot.db`
- No persistent state between runs

## Error Handling: PASS
- Defensive checks: price > 0, ATR floor (1e-8), safe min/max on empty lists
- No uncaught exceptions in setup logic

## Smoke Coverage: PASS
- Tests: `tests/test_research_lab_crowded_unwind.py` (50 passed, 2 skipped)
- `compileall` OK
- Backtest run completed without errors

## Tech Debt: LOW
- Implementation is clean, no NotImplementedError stubs in executed paths
- Config uses dataclass with sensible defaults
- No obvious duplication or complexity issues

## AGENTS.md Compliance: PASS
- Commit message follows WHAT/WHY/STATUS format
- Research-only work isolated per rules
- No production settings or orchestrator changes

## Methodology Integrity: PASS
- Hypothesis clearly documented in `research_lab/research/CROWDED_UNWIND_HYPOTHESIS.md`
- Setup claims objective metrics (funding, OI, force orders, TFI) with concurrent timing
- Implementation matches hypothesis specification
- Data backfill from production server (146,864 force orders) ensures honest test
- Audit package transparent about results

## Promotion Safety: PASS
- No promotion artifacts generated (correctly - results failed gates)
- Hard gates evaluated and documented in `crowded_gate_results.json`
- Red flags correctly identify REJECT actions

## Reproducibility & Lineage: PASS
- Commit hash, branch, date range, and setup config recorded
- Force order backfill documented (source, count, time range)
- Results stored in audit package and validation report

## Data Isolation: PASS
- Source DB (`storage/btc_bot.db`) treated as read-only input
- Research copy created for backfill, untracked, no mutation of original

## Search Space Governance: PASS
- Parameters use dataclass defaults, no hidden tuning
- Thresholds set based on domain knowledge (funding percentiles, force rates, etc.)
- No parameter rescue attempted

## Artifact Consistency: PASS
- Audit package, gate results, and validation report tell consistent story
- Builder verdict (REJECT) matches gate outcomes

## Boundary Coupling: PASS
- Dependencies on `backtest/`, `core/models`, `settings` are explicit and bounded
- No leaked ownership into live path

---

## Critical Issues

### 1. Hypothesis failed: Force spike + crowding metrics not predictive

**Evidence:**
- 71 trades, all in `crowded_leverage` regime (correct targeting)
- ER: -0.352508 (gate: >1.5) → **FAILED by 1.85 R**
- PF: 0.40411 (credible: 1.5-6.0) → **FAILED, deeply losing**
- Liquidation capture: 32.4% (gate: >=50%) → **FAILED by 17.6 pp**
- Both LONG and SHORT directions lose money (ER -0.31 and -0.37)

**Root cause:**
The setup requires:
1. Funding extreme (crowding present)
2. OI elevated (leverage high)
3. Force order spike (liquidations starting)
4. Unwind confirmation (TFI flip OR OI delta)

By the time all four conditions are met at 15m decision frequency, the liquidation cascade opportunity has already passed. The 32% liquidation capture rate confirms: most entries occur AFTER the cascade exhausts, not during its profitable phase.

**Why this is different from measurement error:**
- Implementation is correct (matches handoff specification)
- Data is complete (146,864 force orders backfilled from production)
- Sample size is adequate (71 trades prove the thesis)
- Results are not marginal (ER deeply negative, not near threshold)

**Why this is a hypothesis failure:**
The concurrent event timing (force spike + crowding + confirmation) combined with 15m decision latency creates structural entry delay. Similar to compression_breakout (sequential timing incompatibility), this setup has **decision frequency incompatibility**.

Force-driven liquidation cascades happen on seconds-to-minutes timescales. 15m decision cycles arrive too late to capture the profitable unwind phase.

### 2. Core validation metric failed significantly

**Liquidation capture rate: 32.4%** (gate: >=50%, reject threshold: <40%)

This metric directly tests the hypothesis: "Can we profitably capture liquidation unwinding?"

Answer: **No.** Only 1 in 3 trades captured liquidations, and even those that did averaged negative expectancy.

---

## Warnings

None. The failure is clear and unambiguous.

---

## Observations

### Data handling: Professional approach
Codex correctly:
- Identified local DB had 0 force orders
- Created untracked research DB copy (no production mutation)
- Backfilled 146,864 force orders from production server
- Documented backfill metadata (source, count, range)
- Ran full-range replay on complete data

This prevented false rejection due to data sparsity while maintaining production DB integrity.

### Entry requirements: Appropriately strict
The setup requires 11 conditions to pass:
- Regime allowed
- Valid price
- Funding extreme
- OI elevated
- Force spike detected
- Force rate >= threshold
- Unwind confirmation (TFI OR OI delta)
- Funding not normalized
- Volatility not panic
- RR >= minimum
- Confluence >= minimum

Despite strict requirements, setup generated 71 trades (adequate sample). The issue is not entry scarcity but edge absence.

### Direction imbalance: 50 SHORT vs 21 LONG
- SHORT (long-squeeze): 50 trades, ER -0.37
- LONG (short-squeeze): 21 trades, ER -0.31

Both directions lose money, but SHORTs are more frequent. This reflects BTC's historical funding bias (more often positive = crowded longs).

Imbalance does not explain failure - both directions failed independently.

---

## Recommended Next Step

**Close CROWDED-UNWIND-RESEARCH-V1 with verdict: HYPOTHESIS FAILED**

**Rationale:**
1. **No measurement flaw identified.** Implementation is correct, data is complete, sample is adequate.
2. **Results are not marginal.** ER is -0.35 (1.85 R below gate), liquidation capture is 32% (18 pp below gate).
3. **Hard stop criteria triggered.** Two critical gates failed with significant margins.
4. **Core thesis disproven.** Force spikes + crowding metrics do not predict profitable unwinding at 15m frequency.

**No diagnostic iteration warranted.** The handoff specified:
> "one diagnostic iteration only for marginal cases"

This is not marginal. A diagnostic iteration would only be justified if there were:
- Concrete measurement flaw identified (none found)
- Results near gate thresholds (ER -0.35 vs >1.5 is not near)
- Plausible parameter rescue (violates fast-failure discipline)

**Portfolio research status after closure:**
- absorption_continuation: FAILED (interpretive CVD signals not predictive)
- compression_breakout: FAILED (sequential event timing incompatible)
- crowded_unwind: FAILED (decision frequency incompatible with cascade timing)
- Remaining: volatility_breakout, regime_reversal, post_cascade_momentum

**Key lesson learned:**
> Liquidation cascade signals (force orders, funding extremes) at 15m decision frequency arrive too late. The profitable phase occurs in seconds-to-minutes, not decision-cycle intervals.

Avoid setups requiring sub-minute timing precision when decision engine runs every 15 minutes. The structural latency gap cannot be closed without architecture changes.

---

## Audit Classification

**Research Lab Bug:** No implementation violations found.

**Strategy Methodology Debt:** The 15m decision frequency limitation is a known constraint, honestly documented. Cascade-timing setups are deferred pending faster decision infrastructure (not in current roadmap).

**Final Verdict:** HYPOTHESIS FAILED - edge does not exist under current system constraints.
