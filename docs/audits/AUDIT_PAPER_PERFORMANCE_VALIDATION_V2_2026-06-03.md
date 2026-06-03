# AUDIT: PAPER_PERFORMANCE_VALIDATION_V2

Date: 2026-06-03
Auditor: Claude Code
Builder: Codex
Commit audited: `ea1a03c` on `deploy/multi-asset-paper-v1`
Audit branch: `claude/epic-darwin-z8Moa`
Parent: `AUDIT_BLUEPRINT_FOUNDATIONS_V1_2026-06-01.md` Risk 1
Prior in chain: `AUDIT_PAPER_PERFORMANCE_VALIDATION_V1_2026-06-01.md` (commit `8d5c25f`)

## Verdict: DONE (measurement correct; Risk 1 remains OPEN with attribution)

The Codex report is methodologically clean, follows the pre-declared Path B tier matrix verbatim, and applies the fail-closed aggregation rule correctly. The `NO_DATA / TIER_DEGRADATION` verdict is supported by the data: zero closed trades on three active assets across 23 hours of legalized-lineage operation. The audit approves the measurement itself.

The finding it surfaces does not close Foundation Risk 1 — it merely **records the first decision-grade measurement** under correct lineage. Risk 1 moves from "untested with correct lineage" to "tested once, insufficient sample, awaiting accumulation." This is meaningful progress even without a verdict tier above NO_DATA, because Risk 1 had been blocked on lineage problems for nearly four weeks.

## Core Audit Axes

| Axis | Status | Note |
|---|---|---|
| Layer Separation | PASS | Read-only SSH per `DATA_SOURCES.md`; SQLite URI `mode=ro`; no writes/restarts/settings changes |
| Contract Compliance | PASS | All 3 deliverables present (MD report, JSON companion, MILESTONE_TRACKER update); pre-declared tier matrix echoed verbatim |
| Determinism | PASS | Time window pinned to `2026-06-02T04:28:26Z`; production HEAD recorded; JSON SHA256 in footer |
| State Integrity | PASS | Production state untouched; verified candidate_id reads `experiment-profile-permissive-v1`, not legacy |
| Error Handling | PASS | Fail-closed aggregation applied per AGENTS.md; null metrics for n=0 cases handled explicitly without claiming overfit or validation |
| Reproducibility & Lineage | PASS | Config lineage check confirms production params = frozen spec; production runtime config_hash recorded; companion JSON SHA recorded |
| Methodology Integrity | PASS | Refuses to claim performance conclusion from zero trades; refuses to compare against trial-00095; reports decision funnel for attribution rather than just headline counts |
| AGENTS.md Compliance | PASS | WHAT/WHY/STATUS commit; references prior audit chain; no scope creep into remediation |

## Number consistency cross-checks

| Claim | Math | Verified |
|---|---|---|
| 92 decision cycles per symbol over 23h | 23h × 4 cycles/h (15-min cadence) = 92 ✓ | ✓ |
| 276 decision_outcomes in V2 window | 92 per symbol × 3 symbols = 276 ✓ | ✓ |
| 16 critical multi_asset 429s | 8 ETH + 8 SOL = 16 ✓ | ✓ |
| 39 alerts_errors in window | 16 critical + 8 health + 1 telegram + 14 info = 39 ✓ | ✓ |
| Cycle failures appear in decision funnel | ETH 8 + SOL 8 symbol_cycle_failed = 16 ✓ matches the 429 count | ✓ |
| Production HEAD | `d3bee883` matches our prior closure audit `80181f1` | ✓ |
| Candidate ID source | `settings.json:deployment.candidate_id` per A1.deploy lineage doc Section 8 | ✓ |

## Decision funnel analysis

Per-asset breakdown over 92 cycles:

| Symbol | no_sweep | sweep_too_shallow | no_reclaim | symbol_cycle_failed | signal_generated |
|---|---:|---:|---:|---:|---:|
| BTC | 67 (73%) | 20 (22%) | 5 (5%) | 0 | 0 |
| ETH | 81 (88%) | 3 (3%) | 0 | 8 (9%) | 0 |
| SOL | 82 (89%) | 2 (2%) | 0 | 8 (9%) | 0 |

### Comparison to V1 (8-day window, 2026-05-24 → 2026-06-01)

| Symbol | V1 sweep events / cycles | V2 sweep events / cycles | Direction |
|---|---:|---:|---|
| BTC | 437/763 = 57% | 25/92 = 27% | Lower sweep rate in V2 window |
| ETH | (V1 data unavailable per symbol breakdown) | 3/92 = 3% | Very low |
| SOL | (V1 data unavailable per symbol breakdown) | 2/92 = 2% | Very low |

V2's lower BTC sweep rate is consistent with two possibilities: (a) market regime change over the 2-day window (lower volatility, fewer pivot tests), (b) statistical noise on a single-day sample. Not enough data to discriminate.

### Expected trade rate vs observed

Per A2 WF reference, `experiment-profile-permissive-v1` produced 496 BTC trades over ~50 months = ~10/month = **0.33 trades/day**. In 23 hours: **expected ~0.32 BTC trades**. Observed: 0. This is within plausible noise — Poisson with mean 0.32 has P(0) ≈ 73%.

For ETH and SOL historical rates from A2 WF were higher (ETH 544 trades over similar period, SOL 1201 trades) but neither produced trades. ETH expected ~0.4/day, SOL ~0.8/day in 23h. P(0) under Poisson: ETH ~67%, SOL ~45%. SOL's 0 trades is mildly unusual (45% probability) but not alarming on a single day.

**Conclusion**: 0 trades in 23h is **plausible** at the historical rate, not evidence of broken strategy logic. The bot is cycling correctly, parameters are correct, no governance/risk vetoes — sweep events simply did not produce qualifying signals in this window.

## Critical Issues

None blocking. Two material findings escalated below.

## Findings escalated

### Finding 1: MULTI_ASSET_WEBSOCKET_V1 still not deployed; 429 errors persist

The PAPER_PERFORMANCE_VALIDATION_V1 audit (2026-06-01) flagged 14 Binance HTTP 429 errors concentrated on ETH/SOL and noted `MULTI_ASSET_WEBSOCKET_V1` sat in `READY_FOR_AUDIT`. **Two days later, V2 shows 16 more 429 errors on the same endpoints (`/fapi/v1/aggTrades`, `/fapi/v1/klines`), same per-symbol distribution.** The websocket milestone has not been deployed in the intervening period.

Quantification:
- ETH cycle failures: 8/92 = 9% of cycles miss data
- SOL cycle failures: 8/92 = 9% of cycles miss data
- BTC cycle failures: 0/92 = 0%

Impact on V2 attribution: of ETH's 92 cycles, ~84 produced sweep evaluations (3 detected). If the 8 failed cycles had succeeded at the same sweep rate, ETH might have detected ~0-1 additional sweeps. Material but not dominant cause of 0 trades. SOL same story.

**The 429 pattern is operational debt accruing.** Each day this persists means ~9% of ETH/SOL data missed. Over a 30-day measurement window aimed at reaching `STATISTICAL_SIGNIFICANCE` tier, that's ~3 days of effective ETH/SOL observation lost.

**Recommendation**: prioritize deploying `MULTI_ASSET_WEBSOCKET_V1` before next V2 rerun. If the milestone is still queued in `READY_FOR_AUDIT`, audit it now. If it's already audited, deploy at next operational window (low risk — websocket migration is server-side code, not data mutation).

### Finding 2: Path B requires defined rerun cadence

Codex's report ends with "re-run V2 after new closed trades accumulate." That's the right action but the cadence is not pre-declared. Without a defined rerun schedule, V2 either runs reactively (on-request, ad-hoc) or never (if the trigger condition isn't observed).

At observed BTC rate of 0 trades/day (with 23h sample), reaching tiers takes:
- ANECDOTAL (1-2 trades): 3-6 days (at historical 0.33/day rate) or potentially never (at observed 0/day)
- EARLY_SIGNAL (3 trades): 9 days at historical rate
- DIRECTIONAL_CONFIRMATION (5 trades): 15 days
- STATISTICAL_SIGNIFICANCE (10 trades): 30 days

Path B's value depends on observation discipline. **Recommendation**: rerun V2 weekly until aggregate tier reaches at least `EARLY_SIGNAL`, then biweekly until `DIRECTIONAL_CONFIRMATION`, then monthly until `STATISTICAL_SIGNIFICANCE` or operational decision to retire the metric.

Add this cadence to the Path B methodology documentation. Update MILESTONE_TRACKER entry for V2 to include "next scheduled rerun: 2026-06-10" (one week from this audit).

## Observations (non-blocking)

3. **`bot_state.candidate_id` column non-existence** is documented but worth re-flagging: V1 also noted this. The candidate identity lives in `settings.json` exclusively. If any future tooling assumes it can read candidate ID from `bot_state`, it will fail. Not a blocker — the metadata script and runtime both correctly read from `settings.json`.

4. **Decision funnel reveals strategy timing matches WF expectations**. The funnel composition (`no_sweep` dominant, `sweep_too_shallow` secondary, `no_reclaim` tertiary, `symbol_cycle_failed` rate-limit driven on ETH/SOL only) is identical in structure to V1. The strategy is operating per design. The lack of trades is not a logic defect; it's a market-rate phenomenon.

5. **Service uptime is clean**: started 2026-06-02 04:29:34, observed 23h continuous operation, no restart events. Bot health = 1, safe_mode = 0. Operational stability is good.

6. **`alerts_errors` shows 8 "health audit" warnings** — Codex's report categorizes them but doesn't elaborate. These may be benign periodic checks or a smaller infrastructure signal worth investigating in a separate operational audit. Not in V2 scope.

## Recommended Next Step

### Immediate (next 7 days)

1. **Deploy `MULTI_ASSET_WEBSOCKET_V1`** to eliminate 429 errors as a confounder before next V2 rerun. If the milestone has not been audited yet, audit it. If audited, deploy.
2. **Continue paper observation**. No parameter changes. No strategy changes.
3. **Rerun V2 on 2026-06-10** regardless of new trade count — this establishes the rerun cadence.

### Medium-term (weeks 2-4)

1. **V2 rerun cadence**: weekly until aggregate tier ≥ `EARLY_SIGNAL`, then biweekly until `DIRECTIONAL_CONFIRMATION`, then monthly.
2. **If by 2026-07-03 (one month) BTC trades remain below ANECDOTAL tier**: escalate to investigation of strategy-deployment mismatch — possibility that legalized parameters produce structurally fewer trades than WF predicted (e.g., due to data-pipeline difference between research snapshots and live data). Open new milestone `STRATEGY_LIVE_DATA_PARITY_INVESTIGATION_V1`.

### Independent (any time)

- `UPDATE_CANDIDATE_ID_METADATA_OWNERSHIP_PRESERVATION_FIX_V1` (queued, ~30 min) — no scheduling pressure
- `COMPLEMENT_OF_DEPLOYED_EDGE_FRAMEWORK_V1` (Risk 2, auditor-only) — can proceed in parallel; would be useful input if paper observation drags past `STATISTICAL_SIGNIFICANCE` timeline

## Foundation Audit Risks status update

| Risk | Status before V2 | Status after V2 |
|---|---|---|
| Risk 1 (paper performance untested) | UNBLOCKED, awaiting first measurement | **TESTED ONCE, AWAITING ACCUMULATION** (real progress; first decision-grade measurement under correct lineage logged) |
| Risk 2 (post-trial generic searches) | OPEN | OPEN — complement framework still pending |
| Risk 3 (cost model) | CLOSED | CLOSED |
| Risk 4 (closure language) | OPEN | OPEN |
| Risk 5 (search space <5% coverage) | OPEN | OPEN |

## Decision

`ea1a03c` is approved. V2 is the first decision-grade measurement under correct lineage. The NO_DATA verdict is honest and well-supported; no statistical claim is made beyond what the data supports.

The persistent 429 pattern (Finding 1) is the most actionable item from this audit. Next operational window: deploy MULTI_ASSET_WEBSOCKET_V1 if/when it's audited; that change removes the cleanest confounder from future V2 reruns.

Foundation Risk 1 cannot close yet, but it has moved from "untestable due to lineage" to "tested, awaiting accumulation." That's meaningful structural progress.
