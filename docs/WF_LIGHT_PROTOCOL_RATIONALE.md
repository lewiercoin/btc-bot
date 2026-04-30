# WF Light Protocol Rationale

**Version:** 1.0.0  
**Created:** 2026-05-01  
**Status:** Approved by external auditor  
**Config:** `research_lab/configs/wf_light_protocol.json`

## Purpose

Light walk-forward protocol for **preliminary screening** of Optuna candidates when clean data window is insufficient for default protocol (730/365/365 days).

**Key constraint:** This is NOT a substitute for full walk-forward validation. Candidates passing light protocol must still pass default protocol before live deployment.

---

## When to Use

- Clean data window < 365 days but ≥ 87 days
- Preliminary parameter screening before full historical backfill
- Research-only validation (paper trading evaluation)
- Explicit operator decision to proceed with known limitations

## When NOT to Use

1. **Clean data ≥ 365 days available** → Use default protocol instead. Light protocol is weaker by design.
2. **Expected trades < 50 total in window** → Results will be dominated by noise. Statistical significance impossible.
3. **Live deployment decision** → Light protocol is preliminary screening only. Full WF required for live promotion.
4. **High-stakes parameter search** → Need ≥10 folds for stable metric distribution. 3 folds insufficient for confidence intervals.

---

## Parameters and Justification

### Core Parameters

| Parameter | Value | Justification |
|---|---|---|
| `train_days` | 50 | Minimum for observing full BTC regime cycle (uptrend → downtrend or vice versa). Below 50 days, all folds may see single regime only, causing regime-specific overfitting. |
| `validation_days` | 20 | Sufficient to observe regime shift vs train period. ~32 trades per validation window at 1.6 trades/day. Below 20 days, validation metric variance too high. |
| `step_days` | 7 | Trade-off: larger step = fewer folds, smaller step = overlapping data. 7 days = 1 week, natural unit for BTC volatility cycles. Below 7 days, folds too correlated. |
| `min_trades_per_window` | 15 | **Light protocol reduction** from default 30 → 15. Below 15: single outlier trade has >6% impact on metrics. 15 trades = statistically sensible sample for directional edge estimation. This relaxation is intentional for preliminary screening on short windows. |
| `min_trades_full_candidate` | 50 | **Relaxed from default 100** due to 87-day window constraint (~139 total trades expected). Candidates with 50-200 trades are viable for preliminary evaluation but must meet default 100+ threshold in full WF before live promotion. |

### Trade Rate Assumption

**Baseline:** ~1.5–1.7 trades/day based on recent windows (geometry_sensitivity runs 2025-2026)

Evidence:
- Nov 2025 – Jan 2026 (61 days): 104 trades baseline = ~1.7/day
- Jan 2026 – Mar 2026 (61 days): 104 trades baseline = ~1.7/day
- Mar 2026 – Apr 2026 (47 days): 69 trades baseline = ~1.5/day

**Conservative estimate for protocol:** 1.6 trades/day

---

## Walk-Forward Fold Calculation

### Available Window
**2026-01-01 → 2026-03-28 = 87 days**

### Formula
```
folds = floor((total_days - train_days - validation_days) / step_days) + 1
```

### Calculation
```
total_days = 87
train_days = 50
validation_days = 20
usable_for_stepping = 87 - 50 - 20 = 17 days

folds = floor(17 / 7) + 1 = floor(2.43) + 1 = 3 folds
```

**Result: 3 folds walk-forward**

### Fold Breakdown

**Fold 1:**
- Train: Day 1-50 (2026-01-01 → 2026-02-19) → ~80 trades
- Validation: Day 51-70 (2026-02-20 → 2026-03-11) → ~32 trades

**Fold 2:**
- Train: Day 8-57 (2026-01-08 → 2026-02-26) → ~80 trades
- Validation: Day 58-77 (2026-02-27 → 2026-03-18) → ~32 trades

**Fold 3:**
- Train: Day 15-64 (2026-01-15 → 2026-03-05) → ~80 trades
- Validation: Day 65-84 (2026-03-06 → 2026-03-25) → ~32 trades

**Unused remainder:** 2026-03-26 → 2026-03-28 (3 days, too short for additional fold)

---

## Expected Trade Counts Per Fold

| Fold Component | Days | Trades (1.6/day) |
|---|---|---|
| Train | 50 | ~80 |
| Validation | 20 | ~32 |
| **Total per fold** | **70** | **~112** |

**Min trades gate (15/fold):** Easily satisfied with ~80 train trades. Gate exists for edge cases where trade rate drops below 0.3/day.

---

## Explicit Limitations

### 1. 3 Folds Total
- **Impact:** Marginally sufficient for trend detection, insufficient for robust confidence intervals.
- **Risk:** Single poor-performing fold has 33% weight on aggregate metrics. In default protocol (≥10 folds), single outlier fold has ≤10% weight.

### 2. ~80 Trades Per Train Fold
- **Impact:** Vulnerable to regime-specific overfitting compared to full protocol (~1200 trades/train).
- **Risk:** Candidate may optimize for Q1 2026 regime characteristics that don't generalize to Q2-Q4 or other years.

### 3. No Full Regime Cycle Guarantee
- **Impact:** 50-day train window may capture partial uptrend or partial downtrend only.
- **Risk:** Strategy may learn "buy dips in uptrend" but never see "short rallies in downtrend". Asymmetric regime exposure.

### 4. 87-Day Window = Q1 2026 Only
- **Impact:** Seasonal bias risk. Crypto Q1 historically differs from Q2-Q4 (tax loss harvesting, macro calendar effects).
- **Risk:** Candidate passing light protocol may fail on Q2/Q3 data due to seasonal regime shift.

### 5. Min Trades Gate Relaxed (30 → 15)
- **Impact:** Increases false positive risk on marginal candidates.
- **Risk:** Candidate with 15-20 trades/fold may pass light protocol but fail default protocol's 30-trade gate.

---

## Promotion Gate

**Operator advisory fields in `wf_light_protocol.json`:**

```json
{
  "promotion_gate": "preliminary_only",
  "requires_full_wf_before_live": true,
  "max_promotion_target": "paper_only"
}
```

**IMPORTANT:** These fields are **operator advisory only**, not code-enforced. The research lab pipeline (`approval.py`, `walkforward.py`) does not read or enforce these constraints. Operators must manually respect the paper-only intent when evaluating candidates.

**Future enforcement:** Adding code-level enforcement would require modifying `research_lab/approval.py` to check `protocol.get("max_promotion_target")` and block live promotion bundles for light protocol candidates. This is tracked as future hardening work.

### Promotion Rules (Operator Manual)

1. **Paper trading:** Allowed after light protocol PASS + operator approval
2. **Live trading:** **BLOCKED** until candidate passes full default protocol (730/365/365)
3. **Research-only campaigns:** Light protocol sufficient for Optuna screening, parameter sensitivity analysis

### Escalation Path

```
Light WF PASS → Paper trading (optional) → Full WF (mandatory) → Live deployment
```

No shortcuts. Light protocol is preliminary screening, not production validation.

---

## Comparison: Light vs Default Protocol

| Metric | Light Protocol | Default Protocol | Ratio |
|---|---|---|---|
| Train days | 50 | 730 | 1:14.6 |
| Validation days | 20 | 365 | 1:18.25 |
| Step days | 7 | 365 | 1:52 |
| Expected folds | 3 | ≥10 | 1:3.3 |
| Total trades (all folds) | ~336 | ~2000+ | 1:6 |
| Min trades/fold | 15 | 30 | 1:2 |
| **Confidence level** | **Preliminary** | **Production-grade** | — |

---

## Operational Workflow

### Before Starting Optuna with Light Protocol

1. **Verify data window:** Confirm gap-free window ≥ 87 days via `scripts/db_status.py`
2. **Document decision:** Add entry to `docs/DECISIONS_LOG.md` explaining why light protocol chosen over waiting for backfill
3. **Set expectations:** Communicate to stakeholders that results are preliminary

### After Optuna Completes

1. **Review candidates:** Check that top candidates have ≥15 trades/fold (may reject some if trade rate was overestimated)
2. **Promotion decision:** 
   - If promoting to paper: Document as preliminary trial, set review date for full WF
   - If promoting to live: **BLOCKED** - full WF required first
3. **Archive results:** Store trial DB and walk-forward reports with explicit "LIGHT_PROTOCOL" tag in metadata

---

## Review and Sunset Criteria

**This protocol should be retired when:**
- Clean data window extends to ≥ 365 days (switch to default protocol)
- Backfill of aggtrade/OI gaps completes
- New data collection makes 87-day window obsolete

**Review date:** 2026-06-01 (reassess data coverage, consider backfill progress)

---

## References

- **Data gaps:** `scripts/db_status.py` output 2026-04-30
- **Decision context:** `docs/DECISIONS_LOG.md` entry "NEW_BASELINE_DATE_OPTUNA remains open"
- **Trade rate evidence:** `research_lab/geometry_sensitivity.py` runs (Nov 2025 – Apr 2026)
- **Default protocol:** `research_lab/configs/default_protocol.json`

---

## Approval

- **Author:** Claude Code
- **Auditor:** External Claude (browser)
- **Approval Date:** 2026-05-01
- **Status:** Approved for implementation

**Auditor notes:** "Parametry 50/20/7, min_trades=15 — ZATWIERDZONE. Trade rate estimate corrected to ~1.5-1.7/day based on geometry_sensitivity evidence. Protocol is preliminary screening only, not production validation."
