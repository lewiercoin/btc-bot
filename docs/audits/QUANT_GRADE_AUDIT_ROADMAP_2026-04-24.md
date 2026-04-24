# QUANT-GRADE AUDIT ROADMAP

**Date:** 2026-04-24  
**Branch:** `market-truth-v3`  
**Document:** `docs/audits/QUANT_GRADE_AUDIT_ROADMAP_2026-04-24.md`  
**Purpose:** Quant-grade, repo-specific audit strategy for the production BTC trading bot from Market Truth validation through paper-trust, modeling unlock, research trust, and live-readiness gating  
**Context:** Market Truth V3 + quant-grade hardening deployed and currently collecting `200+` validation cycles under runtime freeze conditions

---

## EXECUTIVE SUMMARY

**Current State:**
- Market Truth V3 deployed with quant-grade per-input timestamp lineage
- Snapshot, feature, decision, and config linkage paths exist in the current repo state
- Production is collecting `200+` validation cycles for timing, staleness, and drift review
- `MODELING-V1` remains blocked until Market Truth acceptance is explicitly granted
- Current work must remain read-only with no runtime or production DB behavior changes

**Strategic Imperative:**

While the bot collects `200` Market Truth cycles, only **read-only audits, documentation, planning, offline analysis, and non-mutating analytical scripts** are allowed. No signal, governance, risk, execution, market-data, or restart changes should be made unless there is a critical operational need.

**Roadmap Scope:**

18 audit tracks organized in 5 phases:
- **Phase 0** (NOW): 5 read-only audits during 200-cycle collection
- **Phase 1** (POST-200): Market Truth acceptance + feature integrity
- **Phase 2** (MODELING): Signal analysis + research lab validation
- **Phase 3** (RESEARCH): replay, experiment lineage, and observability trust
- **Phase 4** (LIVE READINESS): execution hardening + security + ops sign-off

**Authority Note:**

If any summary in the executive map below conflicts with current repo artifacts, the detailed mini-specs in Section 4 and the source-of-truth documents in `AGENTS.md`, `docs/BLUEPRINT_V1.md`, `docs/BLUEPRINT_RESEARCH_LAB.md`, `docs/MILESTONE_TRACKER.md`, and `docs/DATA_SOURCES.md` are authoritative.

---

## AUDIT TRACK EXECUTIVE MAP

### 1. Market Truth / Data Source Audit

**Primary Question:** Is persisted market data the true, complete, and timely record of bot inputs?

**Why Important:** Foundation of all downstream decisions. Incorrect/stale market data = invalid feature computation = invalid signals.

**Key Risks:**
- Staleness: Exchange timestamps lag cycle timestamps
- Gaps: Missing candles, OI, funding
- Corruption: JSON parse failures, schema mismatches
- Lookahead: Features computed on future data

**Primary Files:**
- `storage/schema.sql` (market_snapshots, feature_snapshots)
- `data/market_data.py` (MarketDataAssembler)
- `data/rest_client.py`, `data/websocket_client.py`
- `validation/recompute_features.py`

**Evidence Required:**
- 200+ snapshots with non-NULL quant-grade lineage fields
- Staleness analysis per input (candles_15m, candles_1h, candles_4h, funding, OI, aggTrades)
- Build timing percentiles (p50, p95, p99)
- Drift report: ATR/EMA < 1% mean error

**Can Run Now?** ⏳ **WAIT_FOR_200_CYCLES** (need production sample)

**Output:** `docs/audits/AUDIT_MARKET_TRUTH_FINAL_2026-04-26.md`

---

### 2. FeatureEngine Audit

**Primary Question:** Are computed features deterministic, correct, and replayable from persisted snapshots?

**Why Important:** Features drive regime classification and signal generation. Non-deterministic features = non-reproducible backtests.

**Key Risks:**
- Drift: Live features differ from recomputed features (>1% error)
- Non-determinism: Random seeds, wall-clock dependencies
- Warm-up: Cold-start features vs bootstrapped features
- Time-series leakage: Using data not available at cycle timestamp

**Primary Files:**
- `core/feature_engine.py`
- `core/models.py` (Features dataclass)
- `validation/recompute_features.py`
- `validation/replay_safety_coverage_matrix.md`

**Evidence Required:**
- Drift report for 200+ snapshots (ATR, EMA, equal_levels, distance metrics)
- Replay safety validation: 22/29 VERIFIED features confirmed
- Warm-up integrity: OI delta, CVD, funding SMA require 200+ cycles
- Bootstrap vs cold-start comparison

**Can Run Now?** ⏳ **WAIT_FOR_200_CYCLES** (need production sample)

**Output:** `docs/audits/AUDIT_FEATURE_ENGINE_INTEGRITY_2026-04-26.md`

---

### 3. Signal Modeling / Stage-1 Audit

**Primary Question:** Does current signal logic (Trial #63 baseline) have edge in post-April 2026 market?

**Why Important:** Bot halted 21 days (Mar 29 - Apr 19) due to uptrend structural gap. Need to quantify current signal domain and identify regime-specific edge.

**Key Risks:**
- Regime blindness: Signal works in downtrend/chop, fails in uptrend
- Overfitting: Walk-forward degradation -238% (trial #26)
- Confluence threshold too high: Zero signals in April 2026 market
- Sweep/reclaim logic inverted: Post-SWEEP-RECLAIM-FIX-V1 degradation

**Primary Files:**
- `core/signal_engine.py`
- `settings.py` (StrategyConfig)
- `research_lab/param_registry.py`
- `backtest/backtest_runner.py`

**Evidence Required:**
- Signal candidates from 200+ cycles (rejected vs accepted)
- Rejection funnel: regime veto, governance veto, risk block
- Near-miss analysis: confluence < 3.6, sweep_depth < 0.00286
- Uptrend continuation candidates (if allow_long_in_uptrend enabled)
- Regime-specific expectancy: normal, compression, downtrend, uptrend, crowded_leverage, post_liquidation

**Can Run Now?** ⏳ **WAIT_FOR_200_CYCLES** (need signal candidate sample)

**Output:** `docs/audits/AUDIT_SIGNAL_MODELING_STAGE1_2026-04-26.md`

---

### 4. Regime Engine / Market State Audit

**Primary Question:** Does regime classification correctly capture market microstructure for signal gating?

**Why Important:** Trial #63 blocks all entries in uptrend regime. Need to verify regime accuracy and whether gating is too restrictive.

**Key Risks:**
- Regime lag: Classification lags true market state
- Regime flapping: Oscillates between states on noise
- Regime blindness: Missing intermediate states (e.g., uptrend-chop)
- Funding/OI bias incorrect: False regime triggers

**Primary Files:**
- `core/regime_engine.py`
- `core/models.py` (Regime enum)
- `settings.py` (RegimeConfig)

**Evidence Required:**
- Regime distribution from 200+ cycles
- Regime transition matrix (normal → uptrend → downtrend → ...)
- Regime stability: mean duration per regime
- Regime vs BTC price correlation (does uptrend = higher highs?)
- Regime vs signal acceptance rate

**Can Run Now?** ⏳ **WAIT_FOR_200_CYCLES** (need regime sample)

**Output:** `docs/audits/AUDIT_REGIME_ENGINE_ACCURACY_2026-04-26.md`

---

### 5. Governance Audit

**Primary Question:** Is governance filtering out junk or blocking viable setups?

**Why Important:** 86.2% of uptrend candidates vetoed by duplicate_level (trial #26 post-mortem). Need to verify governance is risk control, not edge killer.

**Key Risks:**
- Duplicate_level too strict: Rejects valid pullbacks in trending markets
- Price_too_close_to_last overly conservative: Blocks valid re-entries
- Same_side_as_open logic flawed: Prevents hedge/reversal
- Governance notes missing: Can't diagnose veto reasons

**Primary Files:**
- `core/governance.py`
- `settings.py` (GovernanceConfig)
- `storage/repositories.py` (decision_outcomes.governance_notes)

**Evidence Required:**
- Governance veto breakdown from 200+ cycles: duplicate_level, price_too_close_to_last, same_side_as_open
- Vetoed candidate quality distribution: confluence, RR, regime
- Near-miss analysis: would-be-accepted if governance relaxed
- Historical comparison: Run #3 vs Trial #63 governance veto rate

**Can Run Now?** ⏳ **WAIT_FOR_200_CYCLES** (need candidate sample)

**Output:** `docs/audits/AUDIT_GOVERNANCE_FILTERING_2026-04-26.md`

---

### 6. Risk Engine Audit

**Primary Question:** Are risk limits calibrated for paper tuning vs production discipline?

**Why Important:** Current limits relaxed for MODELING-V1 data collection (weekly_dd_limit 30% vs production 6.3%). Need to verify risk gate is enforceable for LIVE.

**Key Risks:**
- Kill-switch too loose: Allows catastrophic DD in LIVE
- Kill-switch too tight: Triggers on normal variance in PAPER
- Position sizing wrong: Leverage too high for realized volatility
- Daily/weekly DD tracking incorrect: Accounting bugs

**Primary Files:**
- `core/risk_engine.py`
- `settings.py` (RiskConfig)
- `execution/paper_execution_engine.py`

**Evidence Required:**
- Risk gate rejection breakdown from 200+ cycles: position_limit, leverage_limit, daily_dd, weekly_dd, consecutive_losses
- RR_below_min frequency: Are setups failing minimum RR threshold?
- DD tracking accuracy: Compare computed DD vs manual PnL calculation
- Production-ready risk limits proposal (restore from tuning → LIVE)

**Can Run Now?** ⏳ **WAIT_FOR_200_CYCLES** (need risk gate sample)

**Output:** `docs/audits/AUDIT_RISK_ENGINE_CALIBRATION_2026-04-26.md`

---

### 7. Execution / Paper-Live Parity Audit

**Primary Question:** Do paper fills match realistic live execution expectations?

**Why Important:** Known bug: TP fills in 10-15 seconds with negative PnL, MAE=0 cases (perfect fills). Paper results corrupt if fills unrealistic.

**Key Risks:**
- Instant fills at snapshot.price: No slippage/spread
- TP/SL fills <30s: Unrealistic in illiquid periods
- Negative PnL on TP exit: Logic bug in paper engine
- MAE=0: Fill at exact stop (impossible)
- Funding not applied: Paper PnL ignores 8h charges

**Primary Files:**
- `execution/paper_execution_engine.py`
- `execution/execution_engine.py`
- `backtest/fill_model.py`
- `storage/repositories.py` (executions table)

**Evidence Required:**
- Fill timing distribution: entry, TP1, TP2, SL (histogram)
- Fill price vs reference price delta (should have slippage)
- MAE/MFE distribution (should never be MAE=0 or MFE=0)
- PnL sanity check: TP exits should be positive, SL exits should be negative
- Funding impact on PnL (8h cycles)

**Can Run Now?** ✅ **READY_NOW** (production DB has ~7 paper trades from March/April)

**Output:** `docs/audits/AUDIT_EXECUTION_PAPER_FILL_INTEGRITY_2026-04-24.md`

---

### 8. Trade Lifecycle / PnL Accounting Audit

**Primary Question:** Is trade PnL correctly computed from entry → TP/SL → funding → fees?

**Why Important:** Corrupt PnL metrics = wrong backtesting results = bad optimization = losing LIVE strategy.

**Key Risks:**
- TP/SL exit PnL sign wrong: Gains shown as losses
- Funding not applied: 8h charges missing
- Fees not applied: Maker/taker ignored
- MAE/MFE incorrect: Excursion tracking logic bug
- Position size wrong: Leverage miscalculation

**Primary Files:**
- `execution/paper_execution_engine.py`
- `storage/repositories.py` (trade_log, executions)
- `core/models.py` (Trade, Execution)

**Evidence Required:**
- Manual PnL recalculation for 5-10 trades: entry_price → exit_price → position_size → fees → funding
- TP exit PnL distribution (should be >0)
- SL exit PnL distribution (should be <0)
- MAE/MFE bounds check (0 < MAE < |PnL|, 0 < MFE)
- Funding application verification (8h cycles logged in executions)

**Can Run Now?** ✅ **READY_NOW** (production DB has trade_log + executions)

**Output:** `docs/audits/AUDIT_TRADE_LIFECYCLE_PNL_ACCOUNTING_2026-04-24.md`

---

### 9. Backtest / Replay / Research Lab Audit

**Primary Question:** Is backtest engine replay-safe and free of lookahead bias?

**Why Important:** Optimization campaigns (Run #12, Run #13) depend on backtest accuracy. Lookahead = false edge = losing LIVE.

**Key Risks:**
- Lookahead bias: Features use future data
- Survivor bias: Only backtesting winners
- Overfitting: Walk-forward degradation -238%
- Fill model unrealistic: Instant fills at midpoint
- Warm-up missing: Cold-start features vs production

**Primary Files:**
- `backtest/backtest_runner.py`
- `backtest/fill_model.py`
- `research_lab/research_backtest_runner.py`
- `validation/replay_safety_coverage_matrix.md`

**Evidence Required:**
- Replay safety validation: 22/29 VERIFIED features confirmed from production snapshots
- Lookahead scan: grep for datetime.now(), time.time() in feature/signal code
- Walk-forward methodology audit: anchored_expanding (730/365) vs rolling (180/90)
- Fill model audit: slippage, latency, spread assumptions
- Warm-up policy: OI delta, CVD, funding SMA require 200+ bars

**Can Run Now?** ✅ **READY_NOW** (can audit code + methodology without production data)

**Output:** `docs/audits/AUDIT_BACKTEST_REPLAY_RESEARCH_LAB_2026-04-24.md`

---

### 10. Experiment Management Audit

**Primary Question:** Is research lab trial lineage traceable and reproducible?

**Why Important:** 310 trials (Run #12) produced 176 zero-vector failures, 63 constraint violations, 15 credible candidates. Need to verify trial context is reproducible.

**Key Risks:**
- Trial context missing: protocol_hash, search_space_signature, regime_signature
- Warm-start contamination: Mismatched protocol/date-range seeds
- Baseline gate too loose: Broken pipelines pass (expectancy -0.87 accepted)
- Pareto artifacts missing: Can't reproduce trial #26 config

**Primary Files:**
- `research_lab/param_registry.py`
- `research_lab/workflows/optimize.py`
- `research_lab/workflows/autoresearch.py`
- `storage/optimization_trials` (SQLite table)

**Evidence Required:**
- Trial lineage audit: protocol_hash, search_space_signature, regime_signature populated for Run #12/#13
- Warm-start filtering audit: Does context matching prevent contamination?
- Baseline gate audit: Does check_baseline_hard() block broken pipelines?
- Pareto artifact audit: Can trial #26 be reproduced from stored config?

**Can Run Now?** ✅ **READY_NOW** (research DB + trial artifacts available)

**Output:** `docs/audits/AUDIT_EXPERIMENT_MANAGEMENT_2026-04-24.md`

---

### 11. Observability / Dashboard Audit

**Primary Question:** Does dashboard surface current bot state without stale/wrong data?

**Why Important:** User reported dashboard shows December 2025/March 2026 data instead of current April 2026 paper trades.

**Key Risks:**
- Config_hash filtering missing: Shows backtest data mixed with live
- Timestamp filtering missing: Shows old data mixed with recent
- Safe_mode not visible: Operator unaware bot is halted
- Egress/proxy health missing: Can't diagnose CloudFront blocking

**Primary Files:**
- `dashboard/server.py`
- `dashboard/db_reader.py`
- `dashboard/static/app.js`, `dashboard/static/index.html`

**Evidence Required:**
- `/api/trades` filtered by current config_hash
- `/api/signals` filtered by current config_hash
- `/api/metrics` filtered by last 7 days
- `/api/alerts` filtered by last 24 hours
- Safe mode banner visible when safe_mode=true
- Egress panel shows current proxy exit IP

**Can Run Now?** ✅ **READY_NOW** (dashboard running on production)

**Output:** `docs/audits/AUDIT_OBSERVABILITY_DASHBOARD_2026-04-24.md`

---

### 12. Production Ops / SRE Audit

**Primary Question:** Is production deployment reproducible, monitored, and recoverable?

**Why Important:** Multiple deployment issues (WebSocket migration, egress proxy, safe_mode sticky, RAM pressure) indicate ops gaps.

**Key Risks:**
- Deployment not documented: No runbook for deploy/restart/rollback
- Backup/restore not tested: DR plan untested
- Resource limits unknown: RAM/CPU/disk exhaustion scenarios
- Log rotation missing: Disk fills with btc_bot.log
- Service dependencies fragile: Dashboard/collectors crash bot

**Primary Files:**
- `scripts/server/btc-bot.service`
- `scripts/server/btc-bot-dashboard.service`
- `scripts/server/btc-bot-force-collector.service`
- `scripts/server/btc-bot-daily-collector.service`
- `docs/SERVER_DEPLOYMENT.md`, `docs/DISASTER_RECOVERY.md`

**Evidence Required:**
- Deployment checklist: SSH, git pull, systemctl restart, health check, rollback plan
- Backup policy: Daily automated, 30-day retention, verified restore test
- Resource monitoring: RAM/CPU/disk usage baselines, alert thresholds
- Log rotation: btc_bot.log, dashboard.log, collector logs
- Service dependency map: What crashes if dashboard fails?

**Can Run Now?** ✅ **READY_NOW** (can audit docs + systemd configs)

---

### 13. Security / Secrets / Exchange Safety Audit

**Primary Question:** Are API keys, DB credentials, and exchange rate limits protected?

**Why Important:** Live mode requires real capital. Leaked API keys = account drain. Rate limit violations = IP ban.

**Key Risks:**
- API keys in git: BINANCE_API_KEY committed to repo
- .env not gitignored: Secrets exposed
- API key permissions too broad: WITHDRAWAL enabled (should be NO)
- Rate limits not enforced: Binance CloudFront ban risk
- Proxy credentials exposed: SOCKS5 password in logs

**Primary Files:**
- `.env.example`, `.gitignore`
- `settings.py` (load from environment)
- `data/rest_client.py` (rate limiting)
- `data/exchange_guard.py`

**Evidence Required:**
- git log scan: grep for API_KEY, SECRET, PASSWORD
- .gitignore audit: .env, *.key, credentials.json listed
- API key permissions audit: Binance dashboard screenshot (should be READ + TRADE only, NO WITHDRAWAL)
- Rate limit enforcement audit: Does REST client respect 2400 req/min?
- Proxy credential audit: Are SOCKS5 passwords logged?

**Can Run Now?** ✅ **READY_NOW** (can audit code + git history)

**Output:** `docs/audits/AUDIT_SECURITY_SECRETS_EXCHANGE_SAFETY.md`

---

### 14. Configuration / Reproducibility Audit

**Primary Question:** Is bot configuration versioned, traceable, and reproducible per deployment?

**Why Important:** Dashboard shows config_hash e8c7180d... but expected f807b7057... (Trial #63). Need to verify config consistency.

**Key Risks:**
- Config drift: Live bot settings ≠ expected trial config
- Config_hash collision: Different params → same hash
- Config not versioned: Can't reproduce trial #26 setup
- Config snapshot missing: decision_outcomes not linked to config

**Primary Files:**
- `settings.py` (StrategyConfig, RiskConfig, GovernanceConfig)
- `storage/repositories.py` (config_snapshots table)
- `core/models.py` (config dataclasses)

**Evidence Required:**
- Config_hash reproducibility: Does same StrategyConfig → same hash?
- Config snapshot persistence: Does decision_outcomes.config_hash link to config_snapshots?
- Trial #63 config audit: Does production config_hash match trial artifact?
- Live vs research split audit: Are live overrides (min_sweep_depth_pct 0.0001) documented?

**Can Run Now?** ✅ **READY_NOW** (can query production DB + compare trial artifacts)

**Output:** `docs/audits/AUDIT_CONFIGURATION_REPRODUCIBILITY_2026-04-26.md`

---

### 15. Testing / CI / Quality Gates Audit

**Primary Question:** Do tests and CI protect the contracts that matter for a production trading system?

**Why Important:** A green pipeline does not help if execution, lifecycle, and persistence contracts are under-tested.

**Key Risks:**
- Smoke coverage misses critical failures
- CI green status hides audit-critical blind spots
- Integration coverage too shallow around decision persistence and trade lifecycle

**Primary Files:**
- `.github/workflows/ci.yml`
- `pytest.ini`
- `tests/test_market_truth_layer.py`
- `tests/test_paper_fill_fix.py`
- `tests/test_orchestrator_runtime_logging.py`
- `tests/test_research_lab_smoke.py`

**Evidence Required:**
- Test inventory mapped to critical modules
- CI workflow coverage for compile, tests, smoke checks
- Gap map for execution, accounting, dashboard, and research-lab contracts

**Can Run Now?** ✅ **READY_NOW** (code and tests can be audited read-only)

**Output:** `docs/audits/AUDIT_TESTING_CI_QUALITY_GATES_2026-04-24.md`

---

### 16. Live Readiness Audit

**Primary Question:** After paper validation and audit closure, what blocks minimal live deployment?

**Why Important:** Live readiness is a systems gate, not just a code-complete gate.

**Key Risks:**
- Recovery path unproven
- Kill-switch behavior not fully signed off
- Live order path assumptions not reconciled with paper findings

**Primary Files:**
- `execution/live_execution_engine.py`
- `execution/order_manager.py`
- `execution/recovery.py`
- `data/exchange_guard.py`
- `docs/paper_trading_validation.md`
- `docs/DISASTER_RECOVERY.md`

**Evidence Required:**
- Live engine contract review
- Recovery behavior review
- Kill-switch readiness checklist
- Security and ops sign-off package

**Can Run Now?** ⏳ **WAIT_FOR_PRIOR_GATES**

**Output:** `docs/audits/AUDIT_LIVE_READINESS_CANDIDATE_2026-04-27.md`

---

### 17. Performance / Latency / Resource Audit

**Primary Question:** Does runtime timing and resource behavior stay inside acceptable bounds during the validation window?

**Why Important:** Market Truth acceptance depends on timing trust, not only on correct schemas.

**Key Risks:**
- Snapshot-build tail latency
- Resource creep across long-running paper validation
- Runtime freshness degradation under load

**Primary Files:**
- `orchestrator.py`
- `data/market_data.py`
- `storage/state_store.py`
- `monitoring/metrics.py`
- `monitoring/health.py`
- `validation/timing_validation_report.md`

**Evidence Required:**
- p50 / p95 / p99 timing summaries
- Runtime freshness evidence
- Resource baseline observations

**Can Run Now?** ⏳ **WAIT_FOR_200_CYCLES**

**Output:** `docs/audits/AUDIT_PERFORMANCE_LATENCY_RESOURCES_2026-04-26.md`

---

### 18. Documentation / Agent Workflow Audit

**Primary Question:** Are source-of-truth docs and agent workflow files aligned with the repo and current validation state?

**Why Important:** Workflow discipline is part of the system safety model.

**Key Risks:**
- Milestone tracker drift
- Blueprint / repo drift
- Builder / auditor role ambiguity

**Primary Files:**
- `AGENTS.md`
- `CASCADE.md`
- `GROK.md`
- `docs/BLUEPRINT_V1.md`
- `docs/BLUEPRINT_RESEARCH_LAB.md`
- `docs/MILESTONE_TRACKER.md`
- `docs/templates/AUDIT_TEMPLATE.md`

**Evidence Required:**
- Source-of-truth comparison
- Milestone-state comparison
- Workflow-role comparison

**Can Run Now?** ✅ **READY_NOW**

**Output:** `docs/audits/AUDIT_DOCUMENTATION_AGENT_WORKFLOW_2026-04-24.md`

---

## PRIORITY PHASING

### Phase 0 — During 200-cycle collection

- **Rule:** read-only only
- **Priority:** execution fill integrity, trade lifecycle accounting, production ops / SRE, backtest / replay / research-lab methodology, security / secrets / exchange safety
- **Allowed:** documentation, planning, offline analysis, non-mutating analytical scripts
- **Forbidden:** runtime behavior changes, parameter changes, data-collection changes, non-critical restarts

### Phase 1 — After 200+ Market Truth cycles

- **Goal:** decide Gate A (`Market Truth Accepted`)
- **Priority:** Market Truth final audit, FeatureEngine integrity, replay / timing confirmation, config reconciliation
- **Output:** merge / no-merge recommendation for `market-truth-v3`

### Phase 2 — Modeling unlock

- **Goal:** decide Gate B (`MODELING-V1 Unblocked`)
- **Priority:** signal funnel, rejected vs accepted dataset, near-miss analysis, regime-specific behavior, governance / risk interpretation
- **Output:** modeling-ready dataset and modeling-unlock recommendation

### Phase 3 — Research / optimization trust

- **Goal:** decide Gate C (`Research Lab Trusted`)
- **Priority:** replay parity, walk-forward discipline, experiment lineage, observability of research outputs
- **Output:** research trust verdict and methodology closure

### Phase 4 — Live readiness

- **Goal:** decide Gate D (`Live Readiness Candidate`)
- **Priority:** live order path, risk hardening, kill-switch, security sign-off, ops sign-off, recovery path
- **Output:** live-readiness recommendation for minimal deployment

---

## AUDIT MINI-SPECS

| Audit | Status | Scope | Evidence | DONE / PARTIAL / FAIL | Output |
|---|---|---|---|---|---|
| Market Truth / Data Source | `WAIT_FOR_200_CYCLES` | lineage, staleness, snapshot linkage, timing contract | `market_snapshots`, `feature_snapshots`, `decision_outcomes`, recompute report | DONE = `200+` cycles and no critical freshness gap; PARTIAL = usable but degraded slices; FAIL = broken source-of-truth chain | `AUDIT_MARKET_TRUTH_FINAL_2026-04-26.md` |
| FeatureEngine | `WAIT_FOR_200_CYCLES` | determinism, drift, replayability, warmup | recompute report, replay-safety matrix, feature samples | DONE = decision-critical features reproduce; PARTIAL = core passes but rolling gaps remain; FAIL = core reproducibility broken | `AUDIT_FEATURE_ENGINE_INTEGRITY_2026-04-26.md` |
| Signal Modeling / Stage-1 | `WAIT_FOR_200_CYCLES` | candidate funnel, labels, near-misses, dataset shape | signal candidates, decision outcomes, executable signals, trade log | DONE = clean labeled funnel; PARTIAL = low sample or config-mixed; FAIL = not trustworthy enough to unblock modeling | `AUDIT_SIGNAL_MODELING_STAGE1_2026-04-26.md` |
| Regime Engine / Market State | `WAIT_FOR_200_CYCLES` | classification, transitions, relation to outcomes | regime distribution, transition matrix, snapshot slices | DONE = interpretable and stable; PARTIAL = useful but noisy; FAIL = not actionable | `AUDIT_REGIME_ENGINE_MARKET_STATE_2026-04-26.md` |
| Governance | `WAIT_FOR_200_CYCLES` | veto reasons, session logic, cooldowns, funnel | rejection cohorts, notes, time-of-day veto patterns | DONE = veto path explainable; PARTIAL = reasons exist but weak resolution; FAIL = cannot audit from stored evidence | `AUDIT_GOVERNANCE_FILTERING_2026-04-26.md` |
| Risk Engine | `WAIT_FOR_200_CYCLES` | RR floor, sizing, leverage, DD state | decision outcomes, bot state, daily metrics, trade log | DONE = math and state reconcile; PARTIAL = mostly correct but live calibration open; FAIL = material sizing or DD error | `AUDIT_RISK_ENGINE_CALIBRATION_2026-04-26.md` |
| Execution / Paper-Live Parity | `READY_NOW` | fill semantics, TP/SL timing, exit reason vs PnL | trade log, positions, executions, paper validation report | DONE = no semantic contradictions; PARTIAL = coherent but realism weak; FAIL = critical contradiction like TP-negative-PnL | `AUDIT_EXECUTION_PAPER_FILL_INTEGRITY_2026-04-24.md` |
| Trade Lifecycle / PnL Accounting | `READY_NOW` | open-close lifecycle, close bookkeeping, PnL sign, MAE/MFE | trade log, positions, executions, daily metrics | DONE = outcomes reconcile from stored values; PARTIAL = core signs correct but costs partial; FAIL = material accounting mismatch | `AUDIT_TRADE_LIFECYCLE_PNL_ACCOUNTING_2026-04-24.md` |
| Backtest / Replay / Research Lab | `READY_NOW` | replay safety, lookahead, walk-forward, warmup, fill realism | replay matrix, backtest contracts, smoke tests, research outputs | DONE = no lookahead blocker; PARTIAL = replay-safe core but realism weak; FAIL = invalidates optimization trust | `AUDIT_BACKTEST_REPLAY_RESEARCH_LAB_2026-04-24.md` |
| Experiment Management | `READY_NOW` | trial lineage, recommendation lineage, protocol reproducibility | experiment store schema, trials, reports, recommendations | DONE = reproducible lineage; PARTIAL = useful but incomplete context; FAIL = cannot reconstruct experiments | `AUDIT_EXPERIMENT_MANAGEMENT_LINEAGE_2026-04-24.md` |
| Observability / Dashboard | `READY_NOW` | current-state visibility, filtering, safe mode, freshness | API payloads, screenshots, dashboard tests | DONE = current truth visible; PARTIAL = mostly correct with stale slices; FAIL = operator view misleading | `AUDIT_OBSERVABILITY_DASHBOARD_2026-04-24.md` |
| Production Ops / SRE | `READY_NOW` | service topology, deploy workflow, backup/restore, log rotation | service files, backup scripts, DR docs, deployment docs | DONE = deploy/recovery path auditable; PARTIAL = path exists but proof incomplete; FAIL = no credible recovery path | `AUDIT_PRODUCTION_OPS_SRE_2026-04-24.md` |
| Security / Secrets / Exchange Safety | `READY_NOW` | secret handling, key permissions, proxy hygiene, request discipline | git scan, ignore rules, env-loading review, key policy checklist | DONE = controls auditably safe; PARTIAL = no exposure but proof manual; FAIL = material secret or exchange-safety gap | `AUDIT_SECURITY_SECRETS_EXCHANGE_SAFETY_2026-04-24.md` |
| Configuration / Reproducibility | `READY_NOW_FOR_STRUCTURE` | config hash, config snapshots, runtime profile differences | config snapshots, decision outcomes, settings profile tests | DONE = config lineage reproducible; PARTIAL = structure exists but deployment lineage manual; FAIL = config lineage ambiguous | `AUDIT_CONFIGURATION_REPRODUCIBILITY_2026-04-26.md` |
| Testing / CI / Quality Gates | `READY_NOW` | CI workflow, smoke inventory, audit-critical test coverage | CI config, tests, smoke scripts, gap map | DONE = critical contracts covered; PARTIAL = CI green but gaps remain; FAIL = major critical paths unguarded | `AUDIT_TESTING_CI_QUALITY_GATES_2026-04-24.md` |
| Live Readiness | `WAIT_FOR_PRIOR_GATES` | live order path, recovery, kill-switch, final sign-off | live engine review, recovery review, sign-off package | DONE = preconditions closed; PARTIAL = one sign-off family open; FAIL = unsafe to promote | `AUDIT_LIVE_READINESS_CANDIDATE_2026-04-27.md` |
| Performance / Latency / Resource | `WAIT_FOR_200_CYCLES` | timing, freshness, storage latency, resource stability | timing report, freshness data, resource observations | DONE = no material cadence risk; PARTIAL = cadence holds but tail-risk open; FAIL = timing/resource behavior undermines trust | `AUDIT_PERFORMANCE_LATENCY_RESOURCES_2026-04-26.md` |
| Documentation / Agent Workflow | `READY_NOW` | source-of-truth docs, milestone state, role clarity | blueprint comparison, milestone comparison, workflow comparison | DONE = coherent authority chain; PARTIAL = mostly coherent with lagging docs; FAIL = material doc/workflow conflict | `AUDIT_DOCUMENTATION_AGENT_WORKFLOW_2026-04-24.md` |

---

## FIRST 5 AUDITS (READY NOW)

### 1. Execution / Paper Fill Integrity Audit

- **Why now** Known paper-fill integrity questions directly affect trust in every paper-trading result.
- **Read-only** Yes.
- **Needs production access** Yes, for trade / execution evidence.
- **Effort** Medium.
- **Deliverable** `docs/audits/AUDIT_EXECUTION_PAPER_FILL_INTEGRITY_2026-04-24.md`
- **Pass condition** No critical contradiction between fill semantics, exit reason, and stored PnL.

### 2. Trade Lifecycle / PnL Accounting Audit

- **Why now** It validates whether lifecycle bookkeeping and derived PnL are reliable enough for later research and risk audits.
- **Read-only** Yes.
- **Needs production access** Yes.
- **Effort** Medium.
- **Deliverable** `docs/audits/AUDIT_TRADE_LIFECYCLE_PNL_ACCOUNTING_2026-04-24.md`
- **Pass condition** Manual reconciliation matches stored lifecycle outcomes for representative trades.

### 3. Production Ops / SRE Audit

- **Why now** It can be completed during the freeze window and directly improves trust in recoverability and operator discipline.
- **Read-only** Yes.
- **Needs production access** Yes, for service and backup verification.
- **Effort** Small.
- **Deliverable** `docs/audits/AUDIT_PRODUCTION_OPS_SRE_2026-04-24.md`
- **Pass condition** Service topology, deployment path, backup path, and restore path are explicit and credible.

### 4. Backtest / Replay / Research Lab Audit

- **Why now** It is safe to audit methodology before `MODELING-V1` and before any new optimization work is trusted.
- **Read-only** Yes.
- **Needs production access** No.
- **Effort** Large.
- **Deliverable** `docs/audits/AUDIT_BACKTEST_REPLAY_RESEARCH_LAB_2026-04-24.md`
- **Pass condition** No lookahead blocker and no unexplained replay / methodology contract gap.

### 5. Security / Secrets / Exchange Safety Audit

- **Why now** It is fully read-only and must be closed before any future live-readiness decision.
- **Read-only** Yes.
- **Needs production access** No.
- **Effort** Small.
- **Deliverable** `docs/audits/AUDIT_SECURITY_SECRETS_EXCHANGE_SAFETY_2026-04-24.md`
- **Pass condition** No material secret-handling or exchange-safety gap.

---

## STATUS GATES

### Gate A — Market Truth Accepted

- **Pass when** `200+` cycles exist, timing/freshness are acceptable, and Market Truth plus FeatureEngine audits have no critical blocker.
- **If pass** Accept `market-truth-v3` as source-of-truth baseline and unblock `MODELING-V1`.
- **If fail** Fix source-of-truth gaps and repeat validation.

### Gate B — MODELING-V1 Unblocked

- **Pass when** Gate A passes and a clean labeled signal dataset exists from trusted production truth.
- **If pass** Start modeling work from the accepted dataset only.
- **If fail** Keep modeling blocked and resolve label / funnel / config-lineage ambiguity.

### Gate C — Research Lab Trusted

- **Pass when** replay, walk-forward, and experiment-lineage audits show that research outputs are methodologically trustworthy.
- **If pass** Research optimization can be treated as decision-supporting evidence.
- **If fail** Research remains advisory only and cannot drive promotion decisions.

### Gate D — Live Readiness Candidate

- **Pass when** execution, accounting, risk, security, ops, and recovery audits all close without critical blockers.
- **If pass** Approve minimal live-readiness candidate review.
- **If fail** Stay in paper / validation mode.

---

## RECOMMENDATIONS

### What to do now

- **Run the first five audits** in parallel where they are independent.
- **Keep all work read-only** during the 200-cycle window.
- **Prepare query packs and offline worksheets** for Gate A as data accumulates.
- **Document every finding as PASS / PARTIAL / FAIL** with explicit evidence and open questions.

### What not to do now

- **Do not change runtime behavior** in signal, governance, risk, execution, or market-data paths.
- **Do not restart the bot** unless there is a critical operational reason.
- **Do not mix validation with tuning** or promotion work.
- **Do not treat research outputs as trusted** until Gate C.

---

## CONCLUSION

This roadmap defines the full quant-grade audit surface of the bot, the correct phase order, the evidence required per audit, the first five safe audits to run now, and the decision gates that separate Market Truth validation, modeling unlock, research trust, and live readiness.

**Expected completion:** 2026-04-26 (initial validation window plus immediate read-only audits)  
**Gate A decision target:** Market Truth accepted → unblock `MODELING-V1`  
**Final goal:** Gate D passed → minimal live-readiness candidate

---

**Roadmap prepared for:** `market-truth-v3` validation window
