# AUDIT: PRODUCTION-DIAGNOSTICS-V1
Date: 2026-04-30
Auditor: Claude Code
Commit: 553ccf8 (modeling-context-closure)

## Verdict: MVP_DONE

## Layer Separation: PASS
## Contract Compliance: PASS
## Determinism: PASS
## State Integrity: WARN
## Error Handling: WARN
## Smoke Coverage: PASS
## Tech Debt: HIGH
## AGENTS.md Compliance: PASS
## Methodology Integrity: PASS

---

## Independent Verification

### Bug confirmed in data/market_data.py

`_load_agg_trade_windows()` computes one shared flag for both windows:

```python
limit_reached = bool(source == "rest" and len(ws_events) >= self.config.agg_trades_limit)
coverage_60s = self._flow_window_metadata(..., limit_reached=limit_reached)  # shared
coverage_15m = self._flow_window_metadata(..., limit_reached=limit_reached)  # shared
```

`_quality_from_flow_metadata()` checks `clipped_by_limit` BEFORE `coverage_ratio` — any True
value short-circuits to DEGRADED regardless of actual window coverage. Bug confirmed.

### Critical correction to builder's analysis

Builder states: "REST API fetches max 1000 trades total" — INCORRECT.

`_load_rest_agg_trade_window()` paginates via fromId loop. At high volume (e.g. 5000 trades/15m),
`ws_events` may contain all 5000 trades after pagination. `len(ws_events) >= 1000` fires → both
windows flagged DEGRADED despite 100% coverage.

Consequence: the bug scope is wider than described. `limit_reached=True` is a false positive even
for the 15m window when pagination completed successfully. The "39% degraded" figure may be
overstated — some buckets may have had complete data despite the flag.

This does NOT change the operational decision (WF_LIGHT window is pre-bug and safe), but it
affects the fix design.

### Deliverable verification

| Deliverable | Status |
|---|---|
| Root cause identified with code evidence | PASS — data/market_data.py:248 confirmed |
| flow_window_rest_limit_clipped classified | PASS — SIGNAL_IMPACT confirmed |
| Data quality verdict CLEAN/DEGRADED/BLOCKED | PASS — DEGRADED post-2026-04-27, CLEAN for WF_LIGHT window |
| Diagnostic report docs/analysis/PRODUCTION_DIAGNOSTICS_V1_2026-05-01.md | PASS |
| DECISIONS_LOG.md updated | PASS — entry "2026-05-01 flow_window_rest_limit_clipped" present |
| Diagnostic scripts (diagnose_flow_clipping.py) | PASS — read-only SQL, correct queries |

---

## Critical Issues
None. Diagnostic milestone deliverables complete.

## Warnings

**W1 — Fix design needs revision**
Builder's proposed fix (count-based per-window limit detection) is based on incorrect premise
that REST fetches max 1000 trades. Since _load_rest_agg_trade_window paginates, the correct fix
must not use `len(trades_60s) >= expected_coverage_60s` as the signal.

Correct fix direction: either (a) remove `limit_reached` dependency in `_quality_from_flow_metadata`
and rely on `first_ts > window_start` + `coverage_ratio` only, or (b) make `limit_reached` represent
"REST fetch was INCOMPLETE" (first batch == limit AND no pagination) rather than "total count >= limit".
The fix milestone must include a unit test for the pagination + high-volume scenario.

**W2 — State Integrity: degraded data accumulating in production**
Every bucket since 2026-04-27 is incorrectly flagged. Fix is non-blocking for WF_LIGHT Optuna
(pre-bug window) but blocks MODELING-CONTEXT-CLOSURE validation rerun on post-2026-04-27 data.
Each day without fix narrows the future clean data window.

**W3 — Tech Debt HIGH: no test for limit_reached + per-window scenario**
Commit c9307f3e (2026-04-25) introduced the bug without test coverage for the shared-flag
scenario. Fix milestone must add regression test.

## Observations

- WF_LIGHT window (2026-01-01 to 2026-03-28) classified as CLEAN: correct. Bug introduced
  2026-04-25, window closes 2026-03-28. Optuna on this window is safe.
- 39% degradation (223/571) may be overstated per W1. Does not affect operational decision.
- SQL output in diagnostic report presented as facts without raw production output shown.
  Acceptable for diagnostic report — builder had SSH access.

---

## Recommended Next Step

Two parallel tracks (operator approval needed):

**Track 1 — immediate:** Optuna with wf_light_protocol.json on 2026-01-01 to 2026-03-28.
UNBLOCKED. Data is pre-bug and clean.

**Track 2 — blocks future data:** FLOW-WINDOW-FIX-V1 milestone. Fix
`_quality_from_flow_metadata` per-window logic (see W1 for direction), add regression test
covering pagination + high-volume scenario, deploy to production. Without this fix,
MODELING-CONTEXT-CLOSURE validation rerun on post-2026-04-27 data remains impossible.

Builder for both tracks: Cascade.
