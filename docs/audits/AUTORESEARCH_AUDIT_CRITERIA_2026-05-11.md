# Autoresearch Output Audit Criteria

Date: 2026-05-11  
Auditor: Claude Code  
Context: Autoresearch run seeded from trial-00095 (optuna-default-v3)  
Purpose: Define evaluation framework for parameter optimization candidates  

## 1. Baseline: Trial-00095

Trial-00095 is the seed for this autoresearch run and serves as the minimum acceptable bar.

| Metric | Baseline Value | Notes |
|---|---|---|
| Raw ER | 2.129 | Solid, not suspiciously high |
| Raw PF | 4.662 | Very good |
| Max DD | 6.51% | Low |
| Trades | 271 | High statistical weight |
| Sharpe | 11.933 | Excellent |
| Win rate | 56.46% | Credible |
| Safety flags | `clean_by_pre_audit_heuristic` | No red flags |

**Key Parameters:**
- `min_sweep_depth_pct`: 0.006 (0.6%)
- `confluence_min`: 3.9
- `allow_long_in_uptrend`: True
- `weight_sweep_detected`: 2.200
- `weight_reclaim_confirmed`: 2.150

## 2. Success Definition: "Good Candidate"

A candidate from autoresearch is **promotion-worthy** if it meets ALL hard gates and MOST soft criteria.

### 2.1 Hard Gates (Must Pass All)

| Gate | Criterion | Rationale |
|---|---|---|
| **Walk-Forward Pass** | 2/2 windows passed | Demonstrates OOS stability |
| **Not Fragile** | `fragile=False` in WF report | Avoids single-period flukes |
| **Minimum Trades** | Total trades >= 80 | Statistical significance |
| **Trade Frequency Improvement** | Trades > 271 OR (Trades >= 200 AND ER improvement) | Addresses current bottleneck (sweep_too_shallow) |
| **No Blocking Safety Flags** | No `pnl_sanity_review_required` | Eliminates obvious artefacts |
| **Expectancy R Credible** | ER in range [0.5, 5.0] | Outside this range is suspicious |
| **Profit Factor Credible** | PF in range [1.5, 6.0] | PF > 6 often indicates overfitting |
| **Drawdown Acceptable** | DD <= 15% | Risk tolerance limit |

### 2.2 Soft Criteria (Prefer Higher Score)

Score each candidate on these dimensions. A **strong candidate** scores high on >=4 of these:

| Dimension | Target | Weight |
|---|---|---|
| **ER vs Baseline** | ER >= 2.129 | High |
| **ER/Trade Balance** | (ER >= 2.0 AND Trades >= 150) OR (ER >= 1.5 AND Trades >= 250) | High |
| **DD vs Baseline** | DD <= 6.51% | Medium |
| **Sharpe vs Baseline** | Sharpe >= 11.933 | Medium |
| **IS Degradation** | Abs(IS degradation) <= 20% | Medium |
| **Win Rate Credible** | Win rate in [40%, 70%] | Low |
| **OOS Trade Distribution** | Each WF window >= 15 trades | Low |

### 2.3 Red Flags (Disqualifying or High-Scrutiny)

| Red Flag | Meaning | Action |
|---|---|---|
| `pnl_sanity_review_required` | PnL artefact (unrealistic magnitude) | **REJECT** |
| `oos_outperformance_review_required` | Suspiciously high OOS performance | **SCRUTINIZE** (likely overfitting) |
| `pf_hard_review_required` | PF > 6.0 or other PF anomaly | **SCRUTINIZE** |
| `low_oos_trade_count_review_required` | < 15 trades in any WF window | **SCRUTINIZE** (statistical fragility) |
| Rescue via methodology loosening | Parameters changed in ways that weaken signal quality gates | **REJECT** |
| Zero-information weights | `weight_X = 0` for critical features (sweep, reclaim, tfi_impulse) | **WARN** |

**Rescue via methodology loosening examples:**
- `min_sweep_depth_pct` drops below 0.002 (0.2%) — likely catching noise
- `confluence_min` drops below 2.5 — too permissive
- `invalidation_offset_atr` grows > 0.20 — stops too loose
- `entry_offset_atr` grows > 0.15 — chasing price

### 2.4 Green Flags (Positive Signals)

| Green Flag | Meaning | Impact |
|---|---|---|
| `clean_by_pre_audit_heuristic` | No pre-audit red flags | Increases confidence |
| Trade frequency 2x+ baseline | Addresses core problem (sweep_too_shallow bottleneck) | High value |
| ER improvement + DD reduction | Better return AND safer | High value |
| Sharpe improvement | Better risk-adjusted returns | Medium value |
| Balanced parameter changes | No extreme outliers, changes are interpretable | Increases trust |

## 3. Audit Workflow

When `loop_report.json` is ready, follow this sequence:

### Step 1: Load and Inventory
- Read `loop_report.json`
- Count total candidates evaluated
- Count candidates marked as "keep" vs "discard"
- Identify top 3-5 by ER, PF, balanced score

### Step 2: Hard Gate Filter
For each "keep" candidate:
1. Check WF pass (2/2 windows, not fragile)
2. Check trade count >= 80
3. Check trade frequency vs baseline (>271 or >=200 with ER improvement)
4. Check no `pnl_sanity_review_required`
5. Check ER in [0.5, 5.0], PF in [1.5, 6.0], DD <= 15%

**Candidates that fail ANY hard gate → REJECT**

### Step 3: Soft Criteria Scoring
For candidates that passed hard gates:
- Score each on the 7 soft criteria dimensions
- Rank by total soft score
- Flag any with <4 high scores → marginal candidates

### Step 4: Red Flag Review
For each remaining candidate:
- List all safety flags
- Check for rescue via methodology loosening (parameter extremes)
- Check for zero-information weights
- **REJECT** candidates with `pnl_sanity_review_required`
- **SCRUTINIZE** candidates with `oos_outperformance_review_required` or `pf_hard_review_required`

### Step 5: Comparative Analysis
- Compare top candidates to baseline trial-00095
- Highlight trade-offs (e.g., higher ER but more DD)
- Identify which parameter changes drove improvements
- Check if improvements are interpretable (not random lucky draws)

### Step 6: Verdict
For each candidate that reaches this stage:

**Promotion Tiers:**

| Tier | Verdict | Criteria | Action |
|---|---|---|---|
| **Tier 1: PROMOTION_READY** | Passes all hard gates + >=5 soft criteria + no red flags | Deploy to paper immediately |
| **Tier 2: QUALIFIED_WITH_REVIEW** | Passes all hard gates + 4 soft criteria + 1 yellow flag | Paper test 48h, monitor closely |
| **Tier 3: MARGINAL** | Passes hard gates + <4 soft criteria OR 2+ yellow flags | Backtest replay on different date ranges for validation |
| **Tier 4: REJECT** | Fails any hard gate OR has blocking red flag | Do not promote |

### Step 7: Recommendation Report
Deliver structured report:
- **Executive summary:** X candidates evaluated, Y passed hard gates, Z promotion-ready
- **Top candidate:** Trial ID, metrics, parameter changes, tier, recommendation
- **Runner-up(s):** If Tier 1 or Tier 2, list as alternatives
- **Failure analysis:** Why rejected candidates failed (common patterns)
- **Next steps:** Deploy Tier 1, paper-test Tier 2, or run V4 if no Tier 1/2

## 4. Special Considerations for This Run

### 4.1 Context: Production Bottleneck
Current production has:
- 132x `sweep_too_shallow` (74% of rejections)
- 110x `no_sweep` (45% of rejections)
- Only 1 trade in 245 decision cycles

**Autoresearch Goal:** Increase trade frequency without sacrificing quality.

**Therefore:**
- Trade count improvement is CRITICAL success metric
- But not at expense of ER/PF collapse
- Accept modest ER degradation (e.g., 2.129 → 1.8) IF trade count 2x AND DD stable

### 4.2 Parameter Focus Areas
Autoresearch should primarily explore:
- `min_sweep_depth_pct`: [0.002, 0.008] — main bottleneck
- `reclaim_buf_atr`, `sweep_buf_atr`: related to sweep validation
- `equal_level_lookback`, `equal_level_tol_atr`: level detection sensitivity
- `confluence_min`: [3.0, 4.5] — secondary gate

**Less critical for this run:**
- `weight_*` parameters (unless addressing specific confluence component)
- Risk parameters (not the bottleneck)

### 4.3 Methodology Integrity
Trial-00095 is from OPTUNA_CAMPAIGN_V3 with established methodology. Autoresearch must NOT:
- Change `allow_long_in_uptrend` (already True, correct)
- Enable `allow_uptrend_continuation` (V3 determined this is dead branch)
- Modify walk-forward protocol
- Weaken hard gates (min trades, DD limits)

If autoresearch modified these → flag as **methodology violation**.

## 5. Audit Report Template

```markdown
# AUDIT: Autoresearch Output - Trial-00095 Parameter Refinement

Date: 2026-05-11
Auditor: Claude Code
Autoresearch Run: research_lab/runs/20260511T103402Z_trial_00095_autoresearch/
Baseline: trial-00095 (optuna-default-v3)

## Verdict: [PROMOTION_READY / QUALIFIED_WITH_REVIEW / MARGINAL / NO_CANDIDATES]

## Executive Summary
- Total candidates evaluated: X
- Candidates passing hard gates: Y
- Tier 1 (promotion-ready): Z
- Tier 2 (qualified with review): W
- Recommendation: [action]

## Top Candidate: [Trial ID or "None"]

### Metrics vs Baseline
| Metric | Baseline | Candidate | Delta | Assessment |
|---|---|---|---|---|
| ER | 2.129 | X.XXX | +X.X% | [better/worse/stable] |
| PF | 4.662 | X.XXX | +X.X% | [better/worse/stable] |
| DD | 6.51% | X.XX% | +X.Xpp | [better/worse/stable] |
| Trades | 271 | XXX | +XX% | [better/worse/stable] |
| Sharpe | 11.933 | XX.XXX | +X.X% | [better/worse/stable] |

### Walk-Forward Performance
- Windows: 2/2 passed [yes/no]
- Fragile: [True/False]
- IS degradation: X.X%
- Per-window trades: [X, Y]

### Parameter Changes
| Parameter | Baseline | Candidate | Interpretation |
|---|---|---|---|
| min_sweep_depth_pct | 0.006 | X.XXX | [interpretation] |
| confluence_min | 3.9 | X.X | [interpretation] |
| [others] | ... | ... | ... |

### Safety Flags
- [List all flags]
- Assessment: [blocking / scrutiny / clean]

### Hard Gates
- [x] WF 2/2 passed, not fragile
- [x] Trades >= 80
- [x] Trade frequency improvement
- [x] No blocking safety flags
- [x] ER/PF/DD in credible ranges

### Soft Criteria Score: X/7
- [List scores]

### Tier: [1/2/3/4]
- Reasoning: [why this tier]

### Recommendation
[Specific action: deploy to paper / 48h paper test / backtest replay / reject]

## Runner-Up Candidates
[If applicable, list Tier 1 or Tier 2 alternatives]

## Failure Analysis
[Common patterns in rejected candidates - what didn't work?]

## Next Steps
1. [Primary action]
2. [Monitoring / verification steps]
3. [Contingency if primary fails]
```

## 6. Decision Matrix Summary

Quick reference for promotion verdict:

| Hard Gates | Soft Score | Red Flags | Verdict |
|---|---|---|---|
| All pass | 5-7 | None | TIER 1: PROMOTION_READY |
| All pass | 4-5 | 1 yellow | TIER 2: QUALIFIED_WITH_REVIEW |
| All pass | <4 | 2+ yellow | TIER 3: MARGINAL |
| Any fail | — | — | TIER 4: REJECT |
| All pass | — | Any blocking | TIER 4: REJECT |

---

**Final Note:** This audit framework prioritizes **trade frequency improvement** (current bottleneck) while maintaining quality guardrails. A candidate that doubles trade count with modest ER degradation may be preferable to one with slightly better ER but no frequency gain, provided DD and safety remain acceptable.
