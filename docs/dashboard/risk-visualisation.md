# Dashboard: Risk & Governance Panel

## Overview

The **Risk & Governance** panel provides live visibility into the upper layers of the trading pipeline: RiskGate status, Governance decisions, and the latest SignalCandidate with full explainability (reasons[], confluence_score, veto notes).

Panel auto-refreshes every 10 seconds via polling (`/api/risk`).

---

## API Endpoint

**`GET /api/risk`**

### Response Schema

```json
{
  "regime": "normal | uptrend | downtrend | compression | crowded_leverage | post_liquidation | null",
  "regime_as_of": "ISO 8601 timestamp | null",
  "latest_signal": {
    "signal_id": "string",
    "timestamp": "ISO 8601",
    "direction": "LONG | SHORT",
    "setup_type": "string",
    "confluence_score": 3.8,
    "reasons": ["reason1", "reason2"],
    "promoted": true,
    "governance_notes": ["governance veto reason if any"],
    "entry_price": 84000.0,
    "rr_ratio": 3.2
  },
  "risk_limits": {
    "daily_dd_limit_pct": 0.185,
    "weekly_dd_limit_pct": 0.063,
    "max_consecutive_losses": 5,
    "max_open_positions": 1,
    "max_trades_per_day": 3,
    "confluence_min": 3.6,
    "min_rr": 2.1
  },
  "risk_usage": {
    "daily_dd_pct": 0.0,
    "weekly_dd_pct": 0.0,
    "consecutive_losses": 0,
    "open_positions_count": 0
  },
  "governance_blocked": false,
  "risk_blocked": false,
  "safe_mode": false
}
```

### Data Sources

| Field | Source |
|---|---|
| `regime`, `latest_signal.*` | `signal_candidates` + `executable_signals` tables (SQLite) — most recent row |
| `risk_limits.*` | `AppSettings.risk` + `AppSettings.strategy` (from `.env` / defaults at startup) |
| `risk_usage.*` | `bot_state` table (SQLite) |
| `governance_blocked` | `latest_signal.promoted == false` |
| `risk_blocked` | Any usage/limit ratio ≥ 1.0 OR `safe_mode == true` |

---

## Panel Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│ Risk & Governance                              Updated HH:MM:SS       │
├─────────────────────────────────────────────────────────────────────┤
│ [risk-alert if governance blocked / risk limit breach warning]        │
├───────────────────────────┬─────────────────────────────────────────┤
│ Current Regime            │ Latest Signal                            │
│  Regime: NORMAL           │  [LONG]  [Promoted ✓]  sweep_reclaim    │
│  As of: Apr 14, 13:52     │  Regime: NORMAL                         │
│                           │  Confluence: 4.20  (min 3.6)            │
│ Risk Gate                 │  RR ratio:  3.40   (min 2.1)            │
│  Daily DD    ██░░░ 1%/19% │  Entry: 84120.00                        │
│  Weekly DD   █░░░░ 1%/ 6% │  Time: Apr 14, 13:52                    │
│  Consec. losses 0/5       │                                         │
│  Open positions 0/1       │  Reasons:                               │
│                           │  • sweep_detected                       │
│  Risk blocked: No         │  • reclaim_confirmed                    │
│                           │  • funding_supportive                   │
└───────────────────────────┴─────────────────────────────────────────┘
```

---

## Risk Bar Color Logic

| Fill % | Bar color | Meaning |
|---|---|---|
| 0–79% | Green | Normal — limit not under pressure |
| 80–99% | Yellow/Amber | Warning — approaching limit |
| 100% | Red | Limit reached — trades blocked by RiskGate |

---

## Alert Row

A yellow alert banner appears at the top of the panel when:

- **Governance blocked** latest signal (promoted = false, governance_notes present)
- **RiskGate is blocking** new trades (any usage/limit ≥ 1.0 or safe_mode = true)
- **Daily or weekly DD ≥ 80%** of limit (warning before full breach)

---

## Regime Interpretation

| Regime | Color | Description |
|---|---|---|
| `NORMAL` | Green | Standard market — LONG only |
| `UPTREND` | Green | Strong uptrend — direction per whitelist |
| `DOWNTREND` | Red | Downtrend — LONG and SHORT allowed |
| `COMPRESSION` | Grey | Range-bound — LONG only |
| `CROWDED_LEVERAGE` | Amber | Leveraged market — SHORT only |
| `POST_LIQUIDATION` | Brown | Post-liquidation bounce — LONG |

---

## Governance Blocked vs Risk Blocked

| Status | Meaning | Recovery |
|---|---|---|
| `governance_blocked: true` | Latest signal did not pass Governance filter. Governance notes show reason. Next 15m cycle may produce a different signal. | Automatic — next signal cycle |
| `risk_blocked: true` | RiskGate limit breached or safe mode active. New trades are fully blocked until limits reset or safe mode cleared. | Depends on cause — daily DD resets daily; consecutive losses reset after winning trade; safe mode requires restart |

---

## Signal Explainability

Every `reasons[]` entry maps directly to a feature flag from `feature_engine.py`:

| Reason key | Meaning |
|---|---|
| `sweep_detected` | Liquidity sweep below/above equal level |
| `reclaim_confirmed` | Price reclaimed sweep level with close |
| `cvd_divergence` | CVD divergence vs price (bullish or bearish) |
| `tfi_impulse` | Taker Flow Imbalance spike |
| `force_order_spike` | Forced order rate spike (liquidation flush) |
| `regime_special` | Regime state adds directional confluence |
| `ema_trend_alignment` | EMA 50/200 aligned with trade direction |
| `funding_supportive` | Funding rate skew supports trade direction |

---

## Related Documentation

- [`docs/dashboard/egress-integration.md`](egress-integration.md) — Egress Health panel
- [`docs/dashboard/access-guide.md`](access-guide.md) — Production access guide
- [`docs/BLUEPRINT_V1.md`](../BLUEPRINT_V1.md) — Pipeline architecture: SignalCandidate → Governance → RiskGate
