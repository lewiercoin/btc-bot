# PRE-REGISTERED KILL-TEST: trial-00095

**Date registered:** 2026-06-05
**Registered by:** Claude Code (independent auditor)
**Status of criteria at registration:** FROZEN — written before any result is observed.

> Purpose: the project owner does not trust the prior audits or research. This
> document removes the need for trust. The pass/fail thresholds below are fixed
> in git **before** the test is run. The verdict is mechanical: a script
> (`scripts/kill_test_trial_00095.py`) computes the numbers, compares them to
> these frozen thresholds, and prints a single PASS / FAIL. No narrative,
> no interpretation, no audit summary stands between the data and the verdict.

---

## What is under test

The entire surviving project rests on a single "edge": `optuna-default-v1-run2-trial-00095`.
The Milestone Tracker advertises it as *"proven edge, ER 2.1, PF 4.6"*.

**Null hypothesis (H0):** trial-00095 has NO robust positive edge on data that
was not used to select it. We attempt to REJECT H0. If we cannot, the thesis is
dead and the project is abandoned (or reset to honest baseline).

## Evidence already on file (NOT trusted — stated for the record)

The committed walk-forward artifact `docs/walkforward/wf_trial_00095.json` —
the file the promotion audit was based on — already reports, on genuinely
out-of-sample 2025 data (validation window never trained on):

```
wf_report.passed         = false
wf_report.fragile        = true
is_degradation_pct       = 64.27%   (threshold 30%)
window_001 validation:   profit_factor = 0.84  (< 1.0 — losing money)
window_001 validation:   sharpe        = -0.89 (negative)
```

The promotion audit relabeled this `PROMOTION_READY`. That contradiction is the
reason this kill-test exists.

---

## FROZEN PASS/FAIL CRITERIA

Two independent evidence streams. **Both must PASS** to keep the project.
Any FAIL → abandon the trial-00095 thesis.

### Stream A — Live forward paper trading (the untainted test)

Source: `trade_log` on production server, rows where
`config_hash = afbd2eb052af3be748950d6b639880ef05c33a03380d8e6ba9fb243170b747d5`
and `closed_at >= 2026-05-08` (deployment date). Forward data cannot be
overfit — it did not exist when the model was selected.

| Metric | PASS threshold |
|---|---|
| Closed trades | >= 20 |
| Expectancy (mean pnl_r) | > 0.0 |
| Profit factor (R-based) | > 1.0 |

PASS only if all three hold. If closed trades < 20 → verdict `INSUFFICIENT`
(not a pass); re-run when >= 20 trades exist.

### Stream B — Fresh historical holdout (2026 YTD)

Source: re-run the system's own walk-forward / backtest on
`2026-01-01 .. today`, data strictly after the selection cutoff (<= 2025-12-31).
Apply the system's own validation gates:

| Metric | PASS threshold |
|---|---|
| Trades | >= 20 |
| Expectancy_r | > 0.05 |
| Profit factor | > 1.2 |
| Sharpe | > 0.5 |
| Max drawdown | < 25% |

PASS only if all hold.

---

## FROZEN DECISION RULE

| Stream A | Stream B | Decision |
|---|---|---|
| PASS | PASS | Edge plausibly real → KEEP. Then investigate why audits misreported. |
| PASS | INSUFFICIENT | Wait for Stream B; do not expand strategy families meanwhile. |
| FAIL | any | **ABANDON** trial-00095 thesis. |
| any | FAIL | **ABANDON** trial-00095 thesis. |

## PRE-REGISTERED PREDICTION (recorded before result)

**FAIL.** Rationale: the already-committed out-of-sample window (2025) yields
PF 0.84 and Sharpe -0.89 — both below the Stream B gates. For the project to
survive, 2026 data and live forward trading must sharply reverse that. The
auditor predicts they will not. This prediction is logged here so it cannot be
revised after the fact.

---

## How to run (on the production server, where data lives)

```bash
# Stream A — live forward verdict (mechanical, frozen thresholds):
python3 scripts/kill_test_trial_00095.py \
    --db /home/btc-bot/btc-bot/storage/btc_bot.db

# Stream B — provide a fresh-holdout walk-forward JSON produced by the
# existing WF runner on 2026 data, then:
python3 scripts/kill_test_trial_00095.py \
    --db /home/btc-bot/btc-bot/storage/btc_bot.db \
    --holdout-wf-json path/to/wf_2026_holdout.json
```

The script prints one JSON object ending in `"verdict": "PASS" | "FAIL" | "INSUFFICIENT"`.
That line is the result. Nothing else needs to be trusted.
