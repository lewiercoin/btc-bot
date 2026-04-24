# AUDIT: Governance Layer
Date: 2026-04-24
Auditor: Claude Code
Commit: 9f00457

## Verdict: DONE

## Signal Filtering Logic: PASS
## Cooldown Enforcement: PASS
## Duplicate Level Detection: PASS
## State Persistence: PASS
## Race Condition Risk: PASS
## Audit Trail: PASS

## Findings

### Evidence reviewed
- `core/governance.py` — complete governance layer implementation (163 lines)
- `core/models.py` — `GovernanceRuntimeState`, `SignalCandidate`, `ExecutableSignal` contracts
- `backtest/backtest_runner.py` — governance layer usage in backtest
- `storage/schema.sql` — `signal_candidates`, `executable_signals` tables (audit trail)
- Production evidence: MILESTONE_TRACKER.md references to governance veto stats (e.g., "86 governance vetoes" in UPTREND-PULLBACK-RESEARCH-V1)

### Assessment summary
- **Signal filtering logic is comprehensive.** `evaluate()` checks (in order): daily_dd_limit, weekly_dd_limit, consecutive_losses, max_trades_per_day, session gating, no-trade windows, cooldown after loss, duplicate level. Returns `GovernanceDecision(False, notes=[reason])` on veto.
- **Cooldown enforcement is correct.** After a loss, `cooldown_minutes_after_loss` (default 60 min) must elapse before next signal. Uses `timedelta` for accurate time arithmetic.
- **Duplicate level detection is sound.** Maintains deque of `(timestamp, entry_reference)` for last 24h (configurable via `duplicate_level_window_hours`). Vetos signals within `duplicate_level_tolerance_pct` (default 0.1%) of existing level. This prevents clustered entries at same price.
- **State persistence is audit-trail only.** Governance layer itself is stateless except for `_accepted_levels` deque (in-memory only). DB tables (`signal_candidates`, `executable_signals`) provide audit trail but governance does not read from DB. This is correct: backtest and live use same logic.
- **No race conditions detected.** `_accepted_levels` deque is append-only during `evaluate()` call. No concurrent modification, no shared mutable state across threads.
- **Audit trail is complete.** Every `evaluate()` call appends to `decision.notes`. DB schema captures rejected candidates in `signal_candidates` table (with `config_hash` linkage). Veto reasons are traceable.

## Critical Issues (must fix before next milestone)
None identified. Governance layer is production-grade.

## Warnings (fix soon)
- **In-memory `_accepted_levels` is lost on restart.** Governance layer uses deque for duplicate level tracking, but this is in-memory only. After bot restart, deque is empty, so duplicate level check has no history. **Impact:** First signal after restart may bypass duplicate check if similar signal was accepted <24h before restart. **Mitigation:** Low risk in practice (24h window, 0.1% tolerance), but could persist `_accepted_levels` to DB for full restart safety.

## Observations (non-blocking)
- **RR ratio calculation is governance responsibility.** `to_executable()` computes `rr_ratio = (tp - entry) / (entry - stop)` for LONG. This is correct placement: governance decides RR before risk engine sees it.
- **Session gating is flexible.** `session_start_hour_utc` and `session_end_hour_utc` define trading hours (default 0-23 = 24/7). `no_trade_windows_utc` allows blackout periods (e.g., major news events).
- **Cooldown is loss-triggered only.** `cooldown_minutes_after_loss` applies after realized loss, not after every trade. This is correct: winning trades don't need cooldown.
- **Duplicate level tolerance is tight.** Default `0.001` (0.1%) means entries must be >0.1% apart in price. For BTC at $80k, this is ~$80 minimum separation. Good anti-clustering discipline.
- **Governance does NOT size positions.** `to_executable()` converts `SignalCandidate` → `ExecutableSignal` but does NOT add size/leverage. That's `RiskEngine.evaluate()` responsibility. Clean separation.
- **`_accepted_levels` deque has maxlen=200.** This is generous for 24h window (default). Even at max_trades_per_day=3, 200 slots = 66 days of history (far exceeds 24h window).

## Recommended Next Step
Governance layer is production-ready. Optional: persist `_accepted_levels` to DB for restart safety (low priority). Current implementation is sound and separation of concerns is excellent.
