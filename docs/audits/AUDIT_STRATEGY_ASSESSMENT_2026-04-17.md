# AUDIT: STRATEGY-ASSESSMENT-2026-04-17
Date: 2026-04-17
Auditor: Claude Code
Commit: 9f0800a

## Verdict: DONE

## Acceptance Criteria Fulfillment: PASS
All acceptance criteria met:
- ✅ Fresh-data cycles inspected (4 cycles: 13:45, 14:00, 14:15, 14:30 UTC)
- ✅ Exact rejection stage identified (SignalCandidate generation, 0 candidates created)
- ✅ Counts documented (4 decisions → 0 candidates → 0 executables → 0 trades)
- ✅ Market snapshot vs Trial #63 requirements compared (2 probes, gap analysis)
- ✅ ETF-bias partiality assessed (K2 not relevant - SignalEngine/RegimeEngine don't use ETF bias)
- ✅ Evidence-backed verdict delivered (tracker + detailed analysis report)

## Analysis Quality: PASS

### Pipeline Breakdown
Concrete and verifiable:
- Assessment window: since 2026-04-17T13:32:54Z (clean restart)
- 4 fresh-data cycles observed with exact timestamps
- Stage counts from DB queries (alerts_errors, signal_candidates, executable_signals, trade_log)
- **Finding**: Rejection at SignalCandidate generation stage (0 candidates created)
- Nothing reaches governance, risk, or execution stages

### Market Snapshot
Two probes executed (14:36:06Z, 14:40:01Z):
- Consistent pattern: uptrend, sweep=true, reclaim=false
- No CVD divergence, no liquidation spike
- Sweep depth exceeds threshold (0.04896-0.04980 vs min 0.00286)
- **Counterfactual analysis** (14:36:06Z): Even if reclaim were true, uptrend blocks entries per Trial #63 regime policy
- This counterfactual demonstrates that confluence_min (3.6) is NOT the bottleneck (counterfactual confluence=7.95)

### Trial #63 Requirements
Correctly extracted from deployed code:
- SignalEngine requires: sweep=true AND reclaim=true
- Regime policy for uptrend: no entries allowed
- confluence_min=3.6 (verified as NOT the active bottleneck)

### Gap Analysis
Clear identification of what market satisfies vs does not satisfy:
- **Satisfies**: sweep present, depth exceeds threshold, data fresh, runtime healthy
- **Does NOT satisfy**: no reclaim, no CVD divergence, uptrend blocks entries, no liquidation spike
- **Critical finding**: confluence_min is not the bottleneck (counterfactual shows it would pass if candidate creation succeeded)

## Classification: PASS
Verdict is evidence-based and justified:
- **Classification**: market conditions / outside Trial #63 domain
- **NOT**: governance veto, risk veto, stale data, confluence_min problem
- **Evidence**:
  - All rejections occur before SignalCandidate creation (not at governance/risk stages)
  - Market state: strong uptrend without reclaim confirmation
  - Strategy design: uptrend allows no entries, requires sweep+reclaim for candidate creation
  - Counterfactual: even with high confluence, candidate would fail on reclaim requirement and regime policy

**This is the correct classification** ✅

Bot is behaving according to strategy design on healthy infrastructure. no_signal is a legitimate output, not a bug.

## Scope Discipline: PASS
In-scope work executed:
- Read-only pipeline analysis ✅
- Fresh-cycle inspection from DB ✅
- Market probe reconstruction ✅
- Trial #63 requirement extraction ✅
- Documentation (tracker + analysis report) ✅

Out-of-scope correctly avoided:
- No settings.py modifications ✅
- No core/ changes ✅
- No parameter tuning ✅
- No governance/risk relaxation ✅
- No forced trades ✅
- No research lab work ✅

## Documentation Quality: PASS
- Tracker findings: concise, concrete, timestamp-based
- Analysis report: detailed, evidence-based, structured
- Both documents tell consistent story
- No speculation - all findings backed by DB queries or code inspection
- Implication clearly stated: "bot works as designed, future tuning is separate question"

## Critical Issues: NONE

## Warnings: NONE

## Observations

### O1: confluence_min is not the bottleneck
Analysis demonstrates (via counterfactual at 14:36:06Z) that even with confluence=7.95 (well above min 3.6), candidate creation fails earlier due to:
1. Missing reclaim (required for candidate creation)
2. Uptrend regime policy (no entries allowed even if candidate existed)

This finding **rules out** "confluence_min too high" as explanation for no_signal. The bottleneck is earlier in the pipeline (reclaim requirement + regime policy).

### O2: Trial #63 is conservative in uptrends
Strategy design explicitly disallows entries in uptrend regime. This is by design (from Run #13 trial #63 parameters), not a bug. Current market is strong uptrend, so zero signals is expected behavior.

If user wants uptrend participation, that requires:
- Research lab exploration (different parameter set)
- OR strategy modification (allow uptrend entries with appropriate risk controls)
- NOT bug fix or infrastructure remediation

### O3: Reclaim requirement is strict
SignalEngine requires BOTH sweep AND reclaim before candidate creation. Current market shows sweep without reclaim (high-side sweep in uptrend). This is a structural market condition, not a data quality issue.

Strategy is waiting for reversal confirmation (reclaim) that hasn't appeared in observed window.

## Recommended Next Step

**Accept STRATEGY-ASSESSMENT-2026-04-17 as DONE.**

Bot is healthy and behaving according to strategy design. no_signal is legitimate output for current market conditions (uptrend without reclaim).

**User has 3 options:**

**Option 1: Monitor and Wait** (recommended if user trusts strategy)
- Bot will trade when market conditions satisfy edge requirements
- Current no_signal is correct risk management (no edge in uptrend without reversal setup)
- No action needed

**Option 2: Research Lab - Uptrend Participation Exploration** (if user wants more uptrend exposure)
- Scope: Explore parameter sets that allow selective uptrend entries
- Target: Find edge in uptrend continuation vs current "reversal only" approach
- Risk: May reduce overall edge if uptrend entries are lower quality
- Out-of-scope: Modifying current deployed strategy (research first, deploy later)

**Option 3: Live Strategy Modification** (NOT recommended without research)
- Direct tuning of deployed settings.py to allow uptrend entries
- High risk: No validation that edge exists in uptrend with current strategy
- Better approach: Run research first (Option 2), then deploy validated parameters

**Recommended: Option 1** (monitor and wait). Bot is working correctly. no_signal in strong uptrend without reversal setup is sound risk management.

---

## Summary

Strategy assessment complete. Fresh-data analysis confirms all 4 post-remediation cycles reject at SignalCandidate generation (0 candidates created). Current market: strong uptrend with sweep but no reclaim. Trial #63 strategy: requires sweep+reclaim for candidate creation, disallows entries in uptrend. Counterfactual analysis proves confluence_min is not the bottleneck. Classification: **market conditions / outside Trial #63 domain** (bot works as designed). Recommendation: monitor and wait, or explore uptrend participation in research lab if desired.
