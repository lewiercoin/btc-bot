# AUDIT: DEPLOYMENT-REMEDIATION-2026-04-17
Date: 2026-04-17
Auditor: Claude Code
Commits: 1efa7e5 (fix), 32cf770 (docs)

## Verdict: DONE

## Acceptance Criteria Fulfillment: PASS
All acceptance criteria met:
- ✅ Deployment baseline chosen and justified (1efa7e5, rationale in tracker)
- ✅ Dirty worktree backed up (`/home/btc-bot/deployment-backups/20260417T133246Z-deployment-remediation`)
- ✅ Dirty worktree classified (orchestrator.py = 0950215 patch, backups = ad-hoc artifacts)
- ✅ Server redeployed cleanly to 1efa7e5
- ✅ btc-bot.service stable (healthy=1, safe_mode=0, restarted 13:32:54 UTC)
- ✅ force-collector restored end-to-end (bootstrap fixed, service active, WS connected, live rows flowing)
- ✅ daily-collector verified (healthy on timer, DXY updates daily)
- ✅ DB freshness restored (candles/OI to 14:00Z, aggtrade to 14:04Z, force_orders to 14:15:35Z count=5)
- ✅ bot_state verified after remediation (healthy=1, safe_mode=0, last_error=null)
- ✅ no_signal re-classified after remediation (3 post-remediation cycles, all no_signal → classified as strategy/market, NOT infrastructure)
- ✅ Tracker updated with findings

## Baseline Choice: PASS
Selected 1efa7e5 (current main tip) - justified:
- Rejected d245617: missing WEBSOCKET-MIGRATION + SAFE-MODE-AUTO-RECOVERY-MVP + required dirty orchestrator.py patch
- Rejected 7a7a743: missing runtime visibility patch (0950215)
- Chose 1efa7e5: includes all fixes + force-collector restoration, aligns server with origin/main
- All commits between 0950215 and 1efa7e5 are documentation-only (verified in git log)
- Sound choice: minimal drift, includes critical fixes, clean alignment

## force-collector Fix Quality: PASS
Commit 1efa7e5 fix is targeted and correct:
- Root cause: Binance forceOrders endpoint requires USER_DATA permission (signed request) + limit max 100
- Old code: unsigned → 401 → signed with limit=1000 → 400 (limit invalid) → crash loop
- New code:
  - Require API credentials upfront (raise if missing)
  - Clamp limit to MAX_FORCE_ORDER_LIMIT=100 with warning
  - Always use signed=True (no auth escalation retry)
  - Direct _request call, no loop
- Addresses both errors from runtime reconciliation:
  - 401 API-key format invalid → fixed by always using signed requests
  - 400 limit is not valid → fixed by clamping to 100
- Test coverage added: `tests/test_data_collectors.py` +72 lines (regression coverage for crash loop path)
- Validation: compileall PASS, pytest test_data_collectors.py 9 passed

## Data Freshness Verification: PASS
All critical tables restored to expected freshness:
- candles: 2026-04-17T14:00:00Z ✅ (< 1 hour old at audit time)
- open_interest: 2026-04-17T14:00:00Z ✅
- aggtrade_buckets: 2026-04-17T14:04:00Z ✅
- force_orders: 2026-04-17T14:15:35.128Z, count=5 ✅ (live WS flowing)
- daily_external_bias: 2026-04-17 ✅
- daily_metrics: 2026-04-17 ✅
- funding: 2026-04-17T08:00:00.011Z ✅ (latest 8h interval, not stale)

All collectors operational:
- btc-bot.service: active, healthy=1, safe_mode=0
- btc-bot-force-collector.service: active, WS connected, live rows arriving
- btc-bot-daily-collector.timer: active, DXY updates daily

## no_signal Classification: PASS
Classification is justified and evidence-based:
- 3 post-remediation decision cycles verified (13:45, 14:00, 14:15 UTC)
- All cycles: outcome=no_signal
- Bot state: healthy=1, safe_mode=0, last_error=null
- Data freshness: verified above (all critical tables fresh)
- Infrastructure blockers eliminated:
  - ✅ Deployment drift resolved (server at 1efa7e5, aligned with origin/main)
  - ✅ Dirty worktree cleaned
  - ✅ Collectors restored and verified
  - ✅ Data freshness confirmed
  - ✅ No safe_mode, no service failures, no stale environment

**Classification: no_signal is strategy/market conditions, NOT infrastructure blocker** ✅

This is the correct classification. Bot is operating normally on fresh data with clean deployment. no_signal outcome indicates strategy is not finding edge in current market conditions, not that infrastructure is broken.

## Scope Discipline: PASS
In-scope work executed:
- Deployment baseline choice ✅
- Dirty worktree backup and cleanup ✅
- Clean redeploy ✅
- Collector restoration and data refresh ✅
- Post-remediation verification ✅
- Documentation (tracker only) ✅

Out-of-scope correctly avoided:
- Strategy/signal/risk/governance tuning ✅
- Forcing trades ✅
- Dashboard features ✅
- Broad documentation rewrites ✅
- Production fixes outside remediation scope ✅

## Documentation Quality: PASS
- Baseline choice rationale explicit and justified
- Dirty worktree classification concrete (file-by-file)
- Data freshness timestamps exact
- Decision cycles documented with timestamps
- Classification evidence-based
- Residual caveat acknowledged (force-order REST bootstrap semantics)

## Critical Issues: NONE

## Warnings: NONE

## Observations

### O1: WebSocket /market path still returns 404
Finding (tracker lines 70-73): /market path 404, automatic fallback to legacy /stream works.

This is expected behavior from WEBSOCKET-MIGRATION milestone. Binance /market path is not yet reliable, fallback to /stream is the designed behavior. No action needed.

### O2: force-order REST bootstrap returns 0 rows
Finding (tracker lines 96-98, K1): REST bootstrap for historical force_orders returns 0 rows, but live WS collection works.

**Assessment:** This is a known limitation, correctly documented as residual caveat. Live collection is functional and sufficient for forward-looking operation. Historical backfill via REST is not critical for current operation. Low-priority follow-up to document or redesign assumptions is appropriate. Not blocking.

### O3: Config hash mismatch persists
Deployed config_hash `e8c7180d` (Trial #63 settings) does not match latest DB signals/trades hash `778678b0` (old backtest from 2026-03-29).

**Assessment:** This is expected and correct. Bot has not generated new signals/trades with Trial #63 settings yet because:
1. Data was stale until this remediation (no valid signals on stale data)
2. Post-remediation cycles show no_signal (strategy finding no edge in current market)

Once strategy generates a signal, new rows will have config_hash `e8c7180d`. This is not a bug.

## Recommended Next Step

**Accept DEPLOYMENT-REMEDIATION-2026-04-17 as DONE.**

Infrastructure/deployment remediation is complete. Bot is clean, stable, and operating on fresh data.

**Next milestone options:**

1. **Strategy Assessment** (if user wants to understand no_signal):
   - Analyze current market conditions vs strategy edge requirements
   - Review signal generation logs for confluence/regime/governance decisions
   - Assess whether Trial #63 parameters are appropriate for current regime
   - Out-of-scope: parameter tuning (assessment only)

2. **Return to Research Lab** (if user wants to find better candidate):
   - Run #13 continuation with level_min_age_bars tunable
   - Regime meta-layer exploration
   - Walk-forward with current market conditions

3. **Monitor and Wait** (if user trusts strategy):
   - Bot is healthy and will trade when edge appears
   - no_signal may be correct risk management in current market
   - Monitor for signal generation without intervention

**User decides priority.** Infrastructure is no longer blocking.

---

## Summary

Deployment remediation complete. Baseline 1efa7e5 deployed cleanly, dirty worktree backed up and removed, force-collector restored end-to-end, data freshness verified for all critical tables. Bot is healthy, stable, and cycling normally on fresh data. Post-remediation cycles show no_signal, correctly classified as strategy/market conditions rather than infrastructure blocker. All deployment/data issues resolved. Next milestone: strategy assessment or research continuation (user choice).
