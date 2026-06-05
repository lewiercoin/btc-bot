# PRE-REGISTERED FINAL EXPERIMENT: Funding-Tilt Directional Edge (single shot)

**Date registered:** 2026-06-05
**Registered by:** Claude Code (independent auditor)
**Branch of record:** `deploy/multi-asset-paper-v1` (the real production branch; `main` is 278 commits stale)
**Criteria status:** FROZEN — written before any result is observed.

> This is the project's **last structurally-different attempt**. Every other edge
> family has been exhausted: sweep/reclaim/SMC (dead — 0 live trades, WF failed),
> volatility breakout (ER -0.092, controls beat main), regime-shift ADX/CHOP
> (ER -0.027), regime-shift HMM (ER -0.122, controls beat main), liquidation burst
> 15m/5m (timing failure, 100% MFE consumed). Funding-rate **directional** entry is
> the only structural, data-backed family never attempted (funding was only ever a
> confluence weight, never a primary signal).
>
> The decision rule below is terminal in both directions. PASS → one paper
> deployment. FAIL → wind down the trading thesis. No further hypothesis treadmill.

---

## Why this is a DIFFERENT philosophy (not another pattern-prediction bet)

The dead families all tried to **predict short-term price direction from chart
structure**. This one does not. The edge source is the **perpetual funding
premium**: a recurring, economically-grounded payment that compensates the
imbalance between leveraged longs and shorts. The thesis is mean-reversion of
*crowded leverage*, paid to wait via funding accrual. It is a position/swing
edge (multi-day holds), not a 15m scalp.

## Hypotheses

- **H1 (alt):** BTCUSDT perp funding-rate extremes predict mean-reverting forward
  returns: extreme-positive funding (overcrowded longs) → SHORT; extreme-negative
  funding (overcrowded shorts) → LONG. Edge survives funding + fee + slippage costs
  and beats control cohorts out-of-sample.
- **H0 (null):** Funding extremes do not predict forward returns better than
  controls. (Auditor's prior: H0 is more likely. Base rate of this project's
  hypotheses surviving = 0/6.)

---

## Design (FROZEN)

- **Instrument:** BTCUSDT perp (the only live-executable instrument).
- **Data:** `funding` table (8h) + `candles` (full available history, >= 3y if present). Read-only snapshot of canonical DB.
- **Signal (≤3 parameters — hard cap):**
  1. `W` — rolling window for funding z-score.
  2. `Z` — entry threshold (enter SHORT if z > +Z, LONG if z < -Z).
  3. `H` — fixed holding period (time-based exit), or exit on funding mean-revert to 0.
  No structure features, no confluence weights, no sweep/reclaim. A deliberately
  dumb rule — so the result cannot be an overfit artifact.
- **Parameter selection:** small pre-declared grid, chosen by walk-forward
  out-of-sample performance, NOT by max in-sample. Grid declared in the handoff
  before running.
- **Costs:** funding paid/received + taker fees + slippage via existing fill model.
- **Control cohorts (mandatory — the project's honest practice, kept):**
  1. Random-entry (same trade count/holding).
  2. Time-shifted funding (signal decorrelated from price).
  3. Inverse signal (sign-flipped).
  Main must beat ALL three in EVERY fold.

---

## FROZEN PASS/FAIL CRITERIA

Out-of-sample (walk-forward, >= 2 folds). **PASS requires ALL:**

| Gate | Threshold |
|---|---|
| Out-of-sample trades | >= 30 |
| Expectancy (ER) per trade | > 0.10 R |
| Profit factor | > 1.2 |
| Beats all 3 control cohorts | in EVERY fold |
| Robustness (no one-fold fragility) | positive ER in EVERY fold; degradation < 40% |

Any gate missed → **FAIL**. No filter-rescue, no parameter widening, no "looks
close" — those are exactly the moves that produced trial-00095.

---

## FROZEN DECISION RULE (terminal)

| Result | Action |
|---|---|
| **PASS** | Promote to ONE paper deployment: small size, monitoring tracking the *actually-deployed* config hash, hard kill if live ER < 0 after 30 trades. |
| **FAIL** | **Wind down the trading thesis.** Structure + volatility + regime + liquidation + funding families are then all exhausted under honest tests. Preserve data + harness + (honest) audit culture as the only retained value. Stop generating new hypotheses. |

## PRE-REGISTERED PREDICTION (recorded before result)

**Marginal-to-FAIL.** Rationale: funding edges are well known and partly
arbitraged; 8h funding cadence is slow; basis is endogenous to price. If an edge
exists it will be small and cost-sensitive. The auditor expects ER near the 0.10
gate, likely below after costs. Logged so it cannot be revised after the fact.

---

## Governance guardrails (prerequisite — non-negotiable)

The kill-test already exposed that documented production != actual production
(trial-00095 hash had 0 trades; live runs hash `c01f79…` on a branch `main`
does not describe). Before this experiment is trusted:

1. All work and validation happen on `deploy/multi-asset-paper-v1` (branch of record).
2. The deployment monitor must track the **actually-deployed** config hash, not a
   stale documented one.
3. `docs/MILESTONE_TRACKER.md` on the branch of record must describe the real
   production state. Reconcile `main` or formally retire it.
4. Trial-00095 is formally closed: **DEAD** (0 live trades + WF passed=false).
   No artifact may continue to describe it as a "proven edge, ER 2.1, PF 4.6".

---

## How the result is reported

The diagnostic prints a single JSON ending in `"verdict": "PASS" | "FAIL"`,
plus the per-fold main-vs-controls table. That line is the result. No audit
summary stands between the data and the verdict.
