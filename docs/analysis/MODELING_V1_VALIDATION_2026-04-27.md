# MODELING-V1-VALIDATION: Offline Retrospective Analysis

> **Type:** OFFLINE RETROSPECTIVE — context reconstructed from historical data
> **NOT** runtime telemetry (context fields start populating after Modeling V1 deploy)
> **Report grade:** ⚠️ PARTIAL

**Date:** 2026-04-27
**DB:** `storage/btc_bot.db`
**Since filter:** `2026-04-14`
**Total closed trades analyzed:** 16
**Total decision cycles analyzed:** 998
**Baseline win rate (all trades):** 50.0% (8W / 8L)
**Baseline expectancy:** +0.318R

**Context classification thresholds (mirrors ContextConfig defaults):**
- Session: ASIA 22:00–06:59 UTC | EU 07:00–13:59 | EU_US 14:00–15:59 | US 16:00–21:59
- Volatility LOW: atr_4h_norm < 0.002 | HIGH: > 0.004 | NORMAL: between

---

## Data Quality: atr_4h_norm Coverage

| Source | Trades | Share |
|--------|--------|-------|
| A: features_at_entry_json (primary) | 0 | 0.0% |
| B: feature_snapshots fallback | 4 | 25.0% |
| Missing (UNKNOWN bucket) | 12 | 75.0% |

⚠️ **PARTIAL REPORT** — UNKNOWN volatility > 20% (75.0%)

- **Session analysis:** ✅ USABLE (not affected by missing atr_4h_norm)
- **Volatility analysis:** ❌ NOT DECISION-GRADE
- **Activation criteria (volatility buckets):** ❌ NOT APPROVED
- **Recommendation:** Re-run after runtime telemetry collects atr_4h_norm in context fields,
  or use fallback join via backtest feature_snapshots if available.

---

## 1–4. Trade Metrics by Session Bucket

| Session | Trades | Wins | Win Rate | Expectancy R | Profit Factor |
|---------|--------|------|----------|--------------|---------------|
| ASIA | 5 | 3 | 60.0% | +0.031R | 1.14 |
| EU | 3 | 3 | 100.0% | +1.697R | ∞ |
| EU_US | 5 | 1 | 20.0% | -0.187R | 0.77 |
| US | 3 | 1 | 33.3% | +0.260R | 1.44 |
| **BASELINE** | 16 | 8 | 50.0% | +0.318R | — |

## 5–7. Trade Metrics by Volatility Bucket _(⚠️ NOT DECISION-GRADE — UNKNOWN > 20%, see Data Quality above)_

| Volatility | Trades | Wins | Win Rate | Expectancy R | Profit Factor |
|------------|--------|------|----------|--------------|---------------|
| HIGH | 4 | 2 | 50.0% | -0.037R | 0.90 |
| UNKNOWN | 12 | 6 | 50.0% | +0.436R | 1.95 |

## 8. Session × Volatility Matrix (Win Rate)

| Session \ Volatility | LOW | NORMAL | HIGH |
|---------------------|-----|--------|------|
| ASIA | — | — | 66.7% (3) |
| EU | — | — | — |
| EU_US | — | — | 0.0% (1) |
| US | — | — | — |

## 9. Base Edge Present vs No Edge by Context

*Edge present = outcome_group in (signal_generated, governance_veto, risk_block, execution_failed)*

### By Session

| Session | Total Cycles | Edge Cycles | No-Edge Cycles | Edge Rate |
|---------|-------------|-------------|----------------|-----------|
| ASIA | 371 | 29 | 342 | 7.8% |
| EU | 308 | 24 | 284 | 7.8% |
| EU_US | 80 | 7 | 73 | 8.8% |
| US | 239 | 24 | 215 | 10.0% |

### By Volatility

| Volatility | Total Cycles | Edge Cycles | No-Edge Cycles | Edge Rate |
|------------|-------------|-------------|----------------|-----------|
| HIGH | 675 | 53 | 622 | 7.9% |
| UNKNOWN | 323 | 31 | 292 | 9.6% |

## 10. Activation Criteria Assessment

**Criteria (from BLUEPRINT_MODELING_V1.md):**
- win_rate_delta ≥ 10.0 percentage points vs baseline
- p_value < 0.05 (chi-square test vs rest of trades)
- **Both** must pass to propose MODELING-V1-ACTIVATION milestone
- ⚠️ **Volatility buckets: NOT APPROVED** (PARTIAL report — UNKNOWN > 20%)

| Bucket | N | Win Rate | Δ vs Baseline | p-value | WR≥10pp | p<0.05 | Eligible |
|--------|---|----------|---------------|---------|---------|--------|---------|
| session:EU | 3 | 100.0% | +50.0pp | 0.055 | ✅ | ❌ | 🔴 NO |
| session:ASIA | 5 | 60.0% | +10.0pp | 0.590 | ✅ | ❌ | 🔴 NO |
| volatility:HIGH | 4 | 50.0% | +0.0pp | >0.99 | ❌ | ❌ | 🔴 BLOCKED |
| volatility:UNKNOWN | 12 | 50.0% | +0.0pp | >0.99 | ❌ | ❌ | 🔴 BLOCKED |
| session:US | 3 | 33.3% | -16.7pp | 0.522 | ❌ | ❌ | 🔴 NO |
| session:EU_US | 5 | 20.0% | -30.0pp | 0.106 | ❌ | ❌ | 🔴 NO |

## Verdict

⚠️ **PARTIAL REPORT — ACTIVATION NOT APPROVED**

- Session analysis is usable but no session bucket met activation criteria.
- Volatility analysis is not decision-grade (UNKNOWN > 20%).
→ Keep `neutral_mode=True` (no change).
→ Re-run after runtime telemetry provides atr_4h_norm in context fields.
→ Do NOT activate context blocking based on this analysis.

---

## Data Notes

- atr_4h_norm fallback chain: A) features_at_entry_json → B) feature_snapshots (via decision_outcomes join)
- Session classification: `trade_log.opened_at` UTC hour (not affected by missing atr_4h_norm)
- Cycle analysis: `decision_outcomes` LEFT JOIN `feature_snapshots`
- Context classification uses same thresholds as `ContextConfig` defaults
- p-values: chi-square 2×2 (bucket vs rest), df=1
- Trades with missing `atr_4h_norm` (both sources) assigned UNKNOWN volatility bucket
- PARTIAL threshold: UNKNOWN > 20% → volatility analysis not decision-grade
- This is retrospective analysis, NOT runtime telemetry
- Runtime context telemetry (Modeling V1 deploy) will provide atr_4h_norm natively

**Generated:** 2026-04-27 11:46:52 UTC