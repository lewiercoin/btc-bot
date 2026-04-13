# Milestone Tracker

Last updated: 2026-04-13

---

## Current Active Milestone

**Milestone:** RUN13-REGIME-AWARE — Regime-robust campaign with anchored walk-forward
**Status:** ACTIVE — Run #13 running on server (tmux `optimize13`, PID 120863, started 2026-04-13 10:50 UTC)
**Active builder:** Codex (D1-D4) + Cascade (commit cleanup)
**Decision date:** 2026-04-13
**Commits:**
- `85cbdc2` RUN13-REGIME-AWARE: hard-block low-trade trials + anchored WF
- `2980a6b` RUN13-WARM-START-FALLBACK: reuse prior winners across protocol changes
- `2f7e047` RUN13-WARM-START-ORDER: seed prior winners before baseline
- `3b81285` RUN13-WARM-START-FILTER: skip stale incompatible history seeds
- `376095f` RUN13-REGIME-AWARE: add artifact cleanup CLI + README update

**Campaign config:**
- study_name: run13-regime-aware
- n_trials: 300
- start_date: 2022-01-01 / end_date: 2026-03-01
- max_sweep_rate: 1.0
- warm_start: yes — seeded from Run #12 winners (trial #26 and #31)

**Key changes vs Run #12:**
- Hard min_trades floor: trades<80 → constraint violation (hard block), not soft penalty
- Walk-forward: anchored_expanding mode, train_days=730, validation_days=365, step_days=365
  (was rolling 180/90 — too short to evaluate 2022-2026 regime robustness)
- Warm start: loads Run #12 Pareto winners before baseline (fixed ordering + compatibility filter)
- Protocol: 2 anchored windows — train 2022-2024 + val 2024-2025, train 2022-2025 + val 2025-2026

**Run #13 mid-campaign results (119+ trials, 2026-04-13 ~15:00 UTC):**

| Trial | exp_r | PF | DD | trades | Note |
|-------|-------|-----|-----|--------|------|
| #0/#1 | +0.636 | 1.617 | 40.5% | 339 | warm start = Run #12 #26 |
| **#63** | **+0.994** | **2.486** | **5.4%** | **183** | **NEW BEST — anchored WF PASSED** |
| #19 | +0.155 | 1.292 | 12.7% | 464 | stable backup |

**Trial #63 walk-forward result (anchored expanding, 730/365 days):**
- passed: TRUE — 2/2 windows (100%)
- fragile: FALSE
- **degradation: -11.2%** ← exceptional (Run #12 trial #26 had -238%)
- failures: ZERO

**DECISION (2026-04-13, confirmed by Grok):** Trial #63 approved for paper trading.
- Degradation -11.2% far below Grok's threshold of -55%
- 2/2 windows passed including 2024-2025 and 2025-2026 bull market windows
- Note: allow_long_in_uptrend=False — bot very selective in bull markets (shorts in corrections only)
- Note: max_leverage=high_vol_leverage=8 — monitor closely in live

**Campaign still running** (~7h remaining). Trial #63 is locked in as paper trading candidate.

---

## Completed Milestone: RUN12-SOFT-PENALTY
**Status:** DONE — 310 trials, 2026-04-12/13
**Active builder:** Claude Code (auditor executed directly) + Cascade (anti-overfitting guard)
**Commits:** `45cea8a` + `51513f2` + `92df4b4` + `92bbbfd` + `e8abab3`

**Final results (310 trials):**

| Category | Count | % |
|----------|-------|---|
| Max penalty (0 trades) | 176 | 56% |
| Constraint violations | 63 | 20% |
| Real backtest | 71 | 22% |
| Credible positive (PF≤3) | 15 | 4% |

**Top credible candidates (PF≤3.0):**

| Trial | exp_r | PF | DD | trades | Note |
|-------|-------|-----|-----|--------|------|
| #26/#93 | **+0.636** | 1.617 | 40.5% | 339 | **best — confirmed twice** |
| #31/#94 | +0.384 | 1.359 | 30.2% | ~150 | solid |
| #221 | +0.342 | 1.493 | 25.5% | ~130 | good DD |

Discarded (PF>3 = overfitted): trials #47, #56, #73, #89, #264 (raw PF=∞, only 20-30 trades).

**Walk-forward result for trial #26:**
- Protocol: 28 rolling nested windows, 2022-2026
- Result: PASSED (15/28 windows = 54%), fragile=false
- **Degradation: -238%** — NOT suitable for live trading
- Root cause: signal works in bear/chop 2022, fails in bull market 2023-2024
- Windows 006-010 (2023-2024): expectancy -0.18 to -1.40 on both train and validation

**Why Run #13:** Run #12 proved edge exists but is regime-dependent. Run #13 tests with anchored WF that explicitly covers 2024-2025 bull market in validation window.

---

## Diagnostic Results (2026-04-12)

### Crash Test (confluence_min=0.0, min_rr=1.0, 8f2c6f2 signal)
- 1,262 trades / 4 years
- expectancy_r = **-0.054** (not anti-edge; headroom to Run #3 best = +0.195 R)
- profit_factor = 0.934
- Regime blocked 53% of signals (healthy filtering)
- Governance blocked 26%

### Test B (min_hits=3 cherry-pick, same conditions)
- 1,183 trades (-6.3% vs baseline)
- expectancy_r = **-0.053** (marginally better)
- **Verdict: safe cherry-pick. min_hits=3 cleans noise without killing signal.**

### Run #3 reference (best historical result, pre-SWEEP-RECLAIM-FIX-V1)
- study: baseline-v3-trial-00195
- expectancy_r = +0.141, profit_factor = 1.192, **607 trades**

---

## Diagnostic Results (2026-04-12)

### Crash Test (confluence_min=0.0, min_rr=1.0, 8f2c6f2 signal)
- 1,262 trades / 4 years
- expectancy_r = **-0.054** (not anti-edge; headroom to Run #3 best = +0.195 R)
- profit_factor = 0.934
- Regime blocked 53% of signals (healthy filtering)
- Governance blocked 26%
- Risk rejected <1% (min_rr=1.0 passes everything)

### Test B (min_hits=3 cherry-pick, same conditions)
- 1,183 trades (-6.3% vs baseline)
- expectancy_r = **-0.053** (marginally better)
- profit_factor = 0.939
- **Verdict: safe cherry-pick. min_hits=3 cleans noise without killing signal.**

### Run #3 reference (best historical result, pre-SWEEP-RECLAIM-FIX-V1)
- study: baseline-v3-trial-00195
- expectancy_r = +0.141, profit_factor = 1.192, **607 trades**
- Walk-forward: mixed (some windows failed — normal for trend-following in regime-mixed 2022-2025)

---

## Completed Milestones (reverse chronological)

### PAPER_BOT_SAFE_RESTART
**Status:** BLOCKED (2026-04-13)
**Builder:** Cascade
**What:** Attempted to restart btc-bot.service to exit safe_mode and start generating Trial #63 data. Bot restarted successfully but immediately re-enters safe_mode due to Binance API connectivity issue.
**Status before restart:**
- Active: active (running) since 17:48:24 UTC (4h 23min uptime)
- Config_hash: e8c7180d829d8c9c8296b09ba7ad8d0316251d4161d36be26fccc2051d4e5718
- Safe_mode: true (snapshot_build_failed: bookTicker)
**Restart executed:**
- systemctl restart btc-bot → successful
- Active: active (running) since 22:11:38 UTC
- Config_hash: e8c7180d829d8c9c8296b09ba7ad8d0316251d4161d36be26fccc2051d4e5718 (unchanged)
- Safe_mode: true (snapshot_build_failed: bookTicker) — IMMEDIATE RE-ENTRY
**Root cause:**
- Bot cannot reach Binance Futures API endpoint `/fapi/v1/ticker/bookTicker`
- Error: "Failed request GET /fapi/v1/ticker/bookTicker after retries"
- This is a network/infrastructure issue, not a configuration issue
- Restart cannot fix this — the bot needs working Binance API connectivity
**Config_hash mismatch:**
- Expected: f807b7057... (Trial #63)
- Actual: e8c7180d... (current server configuration)
- The bot is using a different config_hash than expected
- This may require settings deployment or configuration update on the server
**Database verification:**
- storage/btc_bot.db exists (697 MB) — correct location
- Empty btc-bot.db and storage.db files in root are artifacts (ignored)
- Bot is correctly using storage/btc_bot.db
**Acceptance criteria NOT met:**
- ❌ Bot did NOT exit safe_mode (re-entered immediately due to API failure)
- ❌ Config_hash is NOT f807b7057... (it's e8c7180d...)
- ❌ Dashboard still shows old data (no new signals/trades generated)
**Next steps required:**
1. Fix Binance API connectivity (network/firewall/VPN issue)
2. Verify/update server configuration to use Trial #63 config_hash (f807b7057...)
3. Once API is reachable, bot should exit safe_mode automatically
**SSH key:** `c:\development\btc-bot\btc-bot-deploy` (root@204.168.146.253)

### DASHBOARD_DATA_INTEGRITY_DEPLOY
**Status:** DONE (2026-04-13)
**Builder:** Cascade
**What:** Deployed config_hash/timestamp filtering fix (commit 6e34649) to production server. Server updated from 131e9e7a → ccceccb5 via `git pull github main`. Restarted `btc-bot-dashboard.service`.
**Deployment steps:**
1. git pull github main → 3 files changed (db_reader.py +69/-20, MILESTONE_TRACKER.md +56, tests +180)
2. systemctl restart btc-bot-dashboard → active (running) PID 134016
**Verification (2026-04-13 22:04 UTC):**
- `/api/trades`: Returns trades filtered by most recent config_hash (all trades show same config_hash: 778678b05b5f...)
- `/api/signals`: Returns signals filtered by most recent config_hash (all signals show same config_hash: 778678b05b5f...)
- `/api/metrics`: Timestamp filter working → shows only last 7 days (2026-04-11 to 2026-04-13), trades_count=0
- `/api/alerts`: Timestamp filter working → shows only last 24 hours (2026-04-13 safe mode alerts)
- Bot status: PAPER mode, safe_mode=true (snapshot_build_failed: bookTicker)
**Important note:** The bot is in safe_mode and has not executed any paper trades yet. The most recent config_hash in the database is from the backtest (March 2026). Once the bot exits safe_mode and generates paper trades with Trial #63 config_hash (starts with f807b7057...), the dashboard will automatically filter to the new config_hash. The filtering logic is working correctly — it just needs new paper trading data to establish the current config_hash.
**SSH key:** `c:\development\btc-bot\btc-bot-deploy` (root@204.168.146.253)

### DASHBOARD_DATA_INTEGRITY_RESEARCH
**Status:** DONE (2026-04-13)
**Builder:** Cascade
**What:** Fixed dashboard showing old backtest data (December 2025/March 2026) instead of current paper trading data. Root cause: SQL queries in `read_trades_from_conn` and `read_signals_from_conn` had NO config_hash filter, returning ALL historical data. Added:
- `_get_current_config_hash()` helper: reads config_hash from most recent trade_log (fallback to signal_candidates)
- `read_trades_from_conn`: now filters by current config_hash (optional parameter for override)
- `read_signals_from_conn`: now filters by current config_hash (optional parameter for override)
- `read_daily_metrics_from_conn`: added timestamp filter (last 7 days) — table has no config_hash column
- `read_alerts_from_conn`: added timestamp filter (last 24 hours) — table has no config_hash column
- Added config_hash field to trade payload for verification
**Files changed:** dashboard/db_reader.py, tests/test_dashboard_db_reader.py
**Tests:** 81 passed, 24 skipped (2 new tests for config_hash filtering)
**Layer separation:** clean — only dashboard/db_reader.py, no core/ changes
**Determinism:** preserved — no automatic data cleanup, only read-time filtering
**SSH key:** `c:\development\btc-bot\btc-bot-deploy` (root@204.168.146.253)

### DASHBOARD_FIX_EXTERNAL_ACCESS
**Status:** DONE (2026-04-13)
**Builder:** Cascade
**What:** Fixed external access blocked by UFW firewall. Dashboard was binding correctly to `0.0.0.0:8080` but UFW only allowed port 22 (SSH). Added `ufw allow 8080/tcp` to open the firewall.
**Diagnostic findings:**
- `ss -tlnp`: Port 8080 listening on `0.0.0.0:8080` ✅
- `curl 127.0.0.1`: Server responded (HTTP 405 on HEAD, but GET works) ✅
- `ufw status`: Only port 22 allowed, port 8080 blocked ❌
- `journalctl`: uvicorn running correctly on `0.0.0.0:8080`
**Fix executed:** `ufw allow 8080/tcp` (added rule for both IPv4 and IPv6)
**Verified:**
- `ufw status`: Now shows 8080/tcp ALLOWED ✅
- External curl from Windows: `curl.exe http://204.168.146.253:8080/api/status` returns live JSON ✅
- Dashboard accessible at http://204.168.146.253:8080 ✅
**SSH key:** `c:\development\btc-bot\btc-bot-deploy` (root@204.168.146.253)

### DASHBOARD_FIX_LIVE
**Status:** DONE (2026-04-13)
**Builder:** Cascade
**What:** Fixed dashboard external access. systemd service had `--host 127.0.0.1` (localhost only). Changed to `--host 0.0.0.0` in `/etc/systemd/system/btc-bot-dashboard.service`, daemon-reloaded, restarted service.
**Verified:**
- Port 8080 now listening on `0.0.0.0:8080` (all interfaces) — externally accessible ✅
- Dashboard service: active (running) PID 132835 ✅
- Bot service: active (running) PID 128229, mode PAPER, uninterrupted ✅
- `/api/status` returns dashboard_version: m3, mode: PAPER ✅
**SSH key:** `c:\development\btc-bot\btc-bot-deploy` (root@204.168.146.253)

### PAPER_TRADING_ACTIVATION_DEPLOY
**Status:** DONE (2026-04-13)
**Builder:** Cascade
**What:** Deployed DASHBOARD_PROD_POLISH changes (db340f0 + a17ac49 + 131e9e7a) to production server. Server updated from d2456178 → 131e9e7a via `git pull github main`. Restarted `btc-bot-dashboard.service` (systemctl). SSH key: `c:\development\btc-bot\btc-bot-deploy` (root@204.168.146.253).
**Verified live on server:**
- `/api/signals` → 20 live signal entries from paper bot DB
- `/api/metrics` → 2026-04-13 daily metrics row
- `/api/alerts` → live alerts (id 949, decision/orchestrator)
- `/api/trades/export` → CSV with correct headers + rows
- `btc-bot.service` → PAPER mode, PID 128229, uninterrupted
- Dashboard version: m3
**Note:** Bot in safe_mode=true due to `snapshot_build_failed: bookTicker` (Binance WS connectivity issue — pre-existing, unrelated to this deployment).

### DASHBOARD_PROD_POLISH
**Status:** DONE (commit db340f0, 2026-04-13)
**Builder:** Cascade
**What:** Signal traceability panel (reasons[], regime, confluence_score, promoted status), daily metrics panel, alerts panel, CSV export for trades+signals, dark mode toggle, config hash display, enriched trade columns (regime, confluence, exit_reason, fees, mae, mfe). 7 new DB reader functions + 7 new tests.
**Why:** Dashboard M1/M3 MVP_DONE but did not surface existing DB data (signal_candidates, daily_metrics, alerts_errors tables already populated by core engine). Polish milestone to expose all traceable data and harden UI.
**Files changed:** dashboard/db_reader.py, dashboard/server.py, dashboard/static/index.html, dashboard/static/app.js, dashboard/static/style.css, tests/test_dashboard_db_reader.py
**Tests:** 79 passed, 24 skipped, 0 failed (7 new tests for signals/metrics/alerts readers)
**Layer separation:** Zero imports from core/**, execution/**, risk/**, governance/**. All reads via storage.* + SQL only.

### SIGNAL-REVERT-V1 + SIGNAL-REVERT-V1-FIX
**Status:** DONE (commits 45cea8a + 51513f2, 2026-04-12)
**What:** Restored core signal files to commit 8f2c6f2 (pre-SWEEP-RECLAIM-FIX-V1). Applied cherry-pick min_hits=3. Fixed optimize_loop.py incompatibility (removed deleted FeatureEngineConfig fields).
**Why:** Runs #5-#11 all failed. Root cause: SWEEP-RECLAIM-FIX-V1 (ba1d6d1) removed sweep/reclaim from confluence scoring AND SIGNAL-ENGINE-REARCH-V1 (cc0024c) made sweep_side the direction source — both changes broke the edge proven in Run #3. Crash Test confirmed raw signal at 8f2c6f2 is not anti-edge (expectancy -0.054).
**Files changed:** core/feature_engine.py, core/signal_engine.py, settings.py, orchestrator.py, backtest/backtest_runner.py, research_lab/param_registry.py, tests/
**Tests:** 63 passed, 24 skipped (intentional — skips reference removed fields)

### DATA-COLLECTORS-V1
**Status:** DONE (commits 5a3c09e + a8dc92e, 2026-04-11)
**What:** Systemd services for live data collection: btc-bot-force-collector (WebSocket liquidations, 24/7), btc-bot-daily-collector (DXY via yfinance, ETF flows via SoSoValue, daily at 00:05 UTC).
**Note:** force-collector has 401 error on server (BINANCE_API_KEY format). Data gaps exist until fixed.

### RUN9-CONFIG / RUN10-CONFIG
**Status:** DONE (commits cf65604, 600aada)
**What:** Progressive lowering of min_trades_full_candidate: 750→300→100. Added warm_start flag.
**Result:** With min_trades=100 and warm start, baseline finally returned non-zero values (-0.874). Confirmed zero-vector problem was cliff + TPE gradient absence, not bad signal per se.

### RUN7-SEARCHSPACE
**Status:** DONE (commit 6612dea, 2026-04-11)
**What:** Tightened 7 unrealistic parameter ranges:
- min_rr: [1.01, 10.0] → [1.5, 4.0]
- tp1_atr_mult: [0.1, 10.0] → [0.5, 5.0]
- tp2_atr_mult: [0.2, 15.0] → [1.0, 8.0]
- high_vol_leverage: [1, 10] → [1, 9]
- max_open_positions: [1, 10] → [1, 3]
- max_trades_per_day: [1, 20] → [1, 6]
- max_hold_hours: [1, 168] → [1, 72]
**Why:** Run #6 had 54% risk rejections (high_vol_leverage > max_leverage), avg min_rr=5.62 (unreachable RR). All changes still active in current campaign.

### SIGNAL-SCORE-RESTORE-V1
**Status:** SUPERSEDED by SIGNAL-REVERT-V1 (commit d66d0d8, 2026-04-11)
**What:** Restored weight_sweep_detected=0.35 and weight_reclaim_confirmed=0.35 to confluence scoring (removed in ba1d6d1). Also fixed weight_cvd_divergence range max 0.50→0.75.
**Result:** Run #10 baseline improved from -0.874 to -0.795. TPE still 95% zero-vectors.
**Why superseded:** Root cause was deeper — SIGNAL-ENGINE-REARCH-V1 sweep_side direction also needed revert. SIGNAL-REVERT-V1 is the complete fix.

### SIGNAL-ENGINE-REARCH-V1
**Status:** REVERTED by SIGNAL-REVERT-V1 (commit cc0024c, 2026-04-10)
**What was wrong:** Made sweep_side the direction source (LOW→LONG, HIGH→SHORT). CVD/TFI demoted to confluence only.
**Why reverted:** At 8f2c6f2, sweep_side was NOT the direction source — CVD/TFI + regime drove direction, sweep was a confluence weight. This architecture produced +0.141 in Run #3. Post-REARCH all campaigns produced negative or zero results.

### SWEEP-RECLAIM-FIX-V1
**Status:** PARTIALLY REVERTED by SIGNAL-REVERT-V1 (commits ba1d6d1 + a111ac9 + 442ff3b, 2026-04-09)
**What was reverted:** Removal of sweep/reclaim from confluence scoring (C2a change in ba1d6d1). Also proximity filter (a111ac9) and tightened default (442ff3b).
**What was kept:** min_hits=3 (cherry-picked back as Test B confirmed safety).
**level_min_age_bars=5 NOT yet implemented** — not in 8f2c6f2 codebase. Deferred to Run #13 as tunable parameter [2, 6].
**Original problem:** sweep_detected_rate was 99.49% — real implementation bug in detect_equal_levels. Fix (min_hits) is correct; removing from scoring was wrong.

### SIGNAL-INVERSION-V1
**Status:** REVERTED by SIGNAL-REVERT-V1 (commit ab664e2, 2026-04-10)
**What was wrong:** Flipped LONG/SHORT direction. Run #5 result: 563 trades, WR=10.5%, ExpR=-0.94.

---

## Campaign History

| Run | Trials | Best exp_r | Status | Root cause of failure |
|-----|--------|-----------|--------|----------------------|
| Run #1 | ~50 | +0.031 (31 trades) | Not promoted | allow_long_in_uptrend disabled; only 31 trades |
| Run #2 | ~100 | — | Not promoted | Low trade count |
| Run #3 | 273 | **+0.141** (607 trades) | **Best historical** | Walk-forward mixed — acceptable |
| Run #4 | ~100 | negative | Not promoted | SWEEP-RECLAIM-FIX-V1 just applied; signal degraded |
| Run #5 | 200 | 0.0 (all zero) | Failed | min_trades=2000 > signal frequency; TPE blind |
| Run #6 | 300 | 0.0 (all zero) | Failed | min_trades=750, 54% risk rejections from unrealistic high_vol_leverage |
| Run #7 | 300 | 0.0 (all zero) | Failed | Realistic search space but zero-vector cliff still present |
| Run #8 | 45 | 0.0 (all zero) | Stopped | min_trades=300, same cliff |
| Run #9 | ~145 | -0.874 (warm start) | Stopped | SIGNAL-ENGINE-REARCH-V1 negative baseline; TPE 95% zero-vectors |
| Run #10 | 141 | -0.462 | Stopped | SIGNAL-SCORE-RESTORE-V1 helped slightly; still 95% zero-vectors |
| Run #11 | 92 | -0.034 (warm start) | Stopped | Signal restored but 88% zero-vectors; no soft penalty yet |
| **Run #12** | **300 (active)** | **+0.636** (trial #26) | **ACTIVE** | **First campaign with working gradient** |

---

## Known Issues (open)

| # | Issue | Priority | Notes |
|---|-------|----------|-------|
| K1 | BINANCE_API_KEY format invalid on server | LOW | force-collector failing with 401; not blocking optimization |
| K2 | force_orders table has 0 rows | LOW | No historical liquidation data; feature frozen in param_registry |
| K3 | daily_external_bias (ETF/DXY) table empty | LOW | EtfBiasCollector runs but ETF data incomplete |
| K4 | Walk-forward uses 6 windows over 4 years | MEDIUM | ~150 trades/window may be insufficient; defer to post-Run#12 |
| K5 | level_min_age_bars not yet in 8f2c6f2 codebase | LOW | Deferred to Run #13; add as tunable [2, 6] |
| K6 | PF=999999 trials (#47/#56/#73) in Run #12 journal | LOW | Anti-overfitting guard deployed at trial #88; future trials unaffected |

---

## Baseline Checkpoint

| Field | Value |
|---|---|
| **Tag** | `v1.0-baseline` |
| **Commit** | `a1a82b5` |
| **Date** | 2026-04-01 |
| **How to restore** | `git checkout v1.0-baseline` |
| **What it contains** | Fazy A–H MVP_DONE · Research Lab RL-V1 do RL-FUTURE MVP_DONE · 18/18 Known Issues zamknięte · dokumentacja zsynchronizowana · 35/35 testów zielonych |
| **Strategy at tag** | PF 1.40 · WR 43.6% · Sharpe 4.37 · DD 17.0% |

---

## Architecture Decisions Log

| Date | Decision | Outcome |
|------|----------|---------|
| 2026-04-09 | SWEEP-RECLAIM-FIX-V1: remove sweep from scoring, add proximity filter | REVERTED — degraded signal |
| 2026-04-10 | SIGNAL-ENGINE-REARCH-V1: sweep_side as direction source | REVERTED — all campaigns failed |
| 2026-04-10 | SIGNAL-INVERSION-V1: flip LONG/SHORT | REVERTED — negative expectancy |
| 2026-04-11 | RUN7-SEARCHSPACE: realistic param ranges | KEPT — sound improvement |
| 2026-04-12 | SIGNAL-REVERT-V1: restore 8f2c6f2 + min_hits=3 | ACTIVE — Crash Test confirmed safe |
| 2026-04-12 | SOFT-PENALTY-V1: replace zero-vector cliff | ACTIVE — TPE death spiral broken |
| 2026-04-12 | Anti-overfitting guard: cap PF>5.0 | ACTIVE — deployed at trial #88 |

---

## Next Steps After Run #12 (proposed, pending audit)

1. Filter all trials with PF > 3.0 (statistically unreliable — zero-loss over 4yr is impossible in BTC perps)
2. Take top 5-7 credible trials (PF 1.3–2.5, trades > 120)
3. Anchored walk-forward: train 2022-2024, test 2024-2025, test 2025-2026
4. If best candidate passes both OOS windows → paper trading validation
5. Run #13: add level_min_age_bars as tunable [2, 6] + simple regime meta-layer (volatility × funding × cvd_strength)
