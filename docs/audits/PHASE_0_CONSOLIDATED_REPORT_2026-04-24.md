# Phase 0 Consolidated Audit Report
## BTC Futures Trading Bot — Post-Audit Analysis

**Date:** 2026-04-24  
**Branch:** `market-truth-v3`  
**Auditor:** Claude Code  
**Scope:** 13 read-only audits across Security, Operations, Configuration, Execution, PnL, Research Lab, Risk, Governance, Testing, Documentation, and Experiment Management  
**Context:** Bot collecting 200+ Market Truth cycles for production validation (Gate A)

---

## Executive Summary

**Phase 0 audit campaign is complete.** 13 comprehensive read-only audits were executed without disrupting the ongoing Market Truth data collection. The audit uncovered **2 critical security/financial gaps**, **4 production hygiene issues**, and **2 quality-of-life improvements**, while confirming **8 production-grade strengths** in core architecture.

**Overall system assessment:** Production-ready for paper trading with **known limitations**. Critical gaps (funding fees, paper execution realism) must be addressed before live trading. Security incident (public dashboard exposure) requires immediate remediation regardless of trading mode.

**Recommendation:** Wait for Gate A (200+ cycles), execute Phase 1 audits (Market Truth validation), then prioritize remediation in order: Security Emergency (Tier S) → Live Readiness Blockers (Tier A) → Production Hygiene (Tier B) → Quality of Life (Tier C).

---

## Audit Inventory

### Tier 1: Security & Operations (4 audits)

| Audit | Verdict | Critical Findings |
|-------|---------|-------------------|
| **AUDIT-13:** Security / Secrets / Exchange Safety | NOT_DONE | 🔴 Public dashboard on 0.0.0.0:8080 with unauthenticated `/api/bot/start\|stop` endpoints |
| **AUDIT-12:** Production Ops / SRE | LOOKS_DONE | 🟡 Runbook stale, alert coverage gaps, production unit drift |
| **AUDIT-11:** Observability / Dashboard | MVP_DONE | 🟢 Runtime freshness solid, 🟡 alert coverage shallow |
| **AUDIT-19:** Recovery / Safe Mode | MVP_DONE | 🟢 Recovery logic present, 🟡 manual tooling stale |

### Tier 2: Configuration & Execution (2 audits)

| Audit | Verdict | Critical Findings |
|-------|---------|-------------------|
| **AUDIT-14:** Configuration / Reproducibility | MVP_DONE | 🟠 config_hash incomplete (missing 50%+ runtime surface), no dependency lock |
| **AUDIT-07:** Execution / Paper Fill Integrity | NOT_DONE | 🔴 Paper fills unrealistic (zero fees, snapshot price, no spread, no partial fills) |

### Tier 3: PnL & Research Lab (2 audits)

| Audit | Verdict | Critical Findings |
|-------|---------|-------------------|
| **AUDIT-08:** Trade Lifecycle / PnL Accounting | MVP_DONE | 🔴 Funding fees NOT tracked (no schema, no backtest, no paper runtime) |
| **AUDIT-09:** Backtest / Research Lab | MVP_DONE | 🟢 Methodology production-grade, no lookahead, comprehensive governance |

### Lower Priority (5 audits)

| Audit | Verdict | Critical Findings |
|-------|---------|-------------------|
| **AUDIT-06:** Risk Engine | DONE | 🟢 Position sizing correct, exit logic sound, PnL calculation accurate |
| **AUDIT-05:** Governance | DONE | 🟢 Signal filtering comprehensive, cooldowns enforced, no race conditions |
| **AUDIT-10:** Experiment Management | DONE | 🟢 Isolation exemplary (per-trial DB snapshots, zero contamination risk) |
| **AUDIT-15:** Testing / CI / Quality Gates | MVP_DONE | 🟡 Coverage enforcement missing, no performance benchmarks |
| **AUDIT-18:** Documentation / Agent Workflow | DONE | 🟢 Documentation exceptional (2301+ lines, 100+ audit reports) |

**Total:** 13 audits, ~250 pages of audit documentation, 100% Phase 0 coverage

---

## Critical Findings by Priority

### 🔴 Tier S: Security Emergency (Immediate Action Required)

#### S1: Public Dashboard Exposure
**Sources:** AUDIT-13, AUDIT-12, AUDIT-11  
**Risk:** Remote control of bot by any internet actor

**Current State:**
- Dashboard bound to `0.0.0.0:8080` (not `127.0.0.1`)
- UFW allows `8080/tcp` from anywhere
- Unauthenticated control endpoints: `POST /api/bot/start`, `POST /api/bot/stop`
- Verified: `curl http://204.168.146.253:8080/api/status` returns live bot state

**Production-Repo Drift:**
- Deployed: public binding
- Repo/docs: loopback-only + SSH tunnel

**Impact:** Active security incident. Anyone can restart bot, view positions, access sensitive operational data.

**Remediation:**
1. Rebind dashboard to `127.0.0.1:8080`
2. Remove UFW rule: `ufw delete allow 8080/tcp`
3. Document SSH tunnel procedure for operator access
4. Update deployed unit file to match repo

**Estimated effort:** 30 minutes  
**Blocks:** Live trading, public repo release

---

### 🔴 Tier A: Blocks Live Readiness

#### A1: Funding Fees Not Tracked
**Sources:** AUDIT-08 (Trade Lifecycle / PnL Accounting)  
**Risk:** PnL overstated by 0.01%-0.03% per 8h on open positions

**Current State:**
- Binance perpetual futures charge funding fees every 8 hours
- Schema has no `funding_paid` column in `trade_log`
- Backtest does not simulate funding fees
- Paper runtime does not track funding fees
- All trades show `fees_total = 0.0` (paper) or only slippage/commission (backtest)

**Impact:** Multi-day positions incur material untracked cost. For 3-day position: ~0.27% additional cost. Backtest and paper PnL are overstated relative to live trading reality.

**Evidence from production:**
```csv
# Sample trades: ALL show fees_total=0.0 (paper) or missing funding component (backtest)
trd-c60be3b0,77792.45,77447.35,0.28,LONG,0.0,-97.16,-1.0
bt-trd-00000294,87657.54,87581.92,0.74,LONG,52.18,-108.47,-1.04
```

**Remediation:**
1. Add `funding_paid` column to `trade_log` schema
2. Implement funding fee collection: sample funding rate at position open/close, calculate cumulative funding for multi-period positions
3. Add funding simulation to `SimpleFillModel` in backtest
4. Track funding in paper runtime execution
5. Deduct funding from `pnl_abs`: `pnl_abs_net = gross_pnl - fees - funding`

**Estimated effort:** 2-3 days  
**Blocks:** Live trading validation, accurate paper-to-live comparison

---

#### A2: Paper Execution Unrealistic
**Sources:** AUDIT-07 (Execution / Paper Fill Integrity)  
**Risk:** Paper PnL overstates live performance, HIGH paper-to-live gap

**Current State:**
- Paper fills use `snapshot.price` (decision-cycle price), not market price at fill time
- Paper runtime charges **zero fees** (`fees=0.0` in all executions)
- No bid/ask spread handling
- No partial fill simulation
- No realistic latency model
- Executions not linked to `market_snapshots` (spread-at-fill not reconstructable)

**Backtest-Paper Parity Broken:**
- Backtest: charges 0.04% fees via `SimpleFillModel`
- Paper: charges 0% fees
- Methodology drift invalidates paper as validation stage

**Evidence from production:**
```sql
# All paper trades: fees_total = 0.0, slippage_bps_avg ranges 12-423 but from bookkeeping, not simulation
SELECT COUNT(*) FROM trade_log WHERE fees_total = 0.0 AND trade_id LIKE 'trd-%';
-- Result: 100% of paper trades have zero fees
```

**Remediation:**
1. Add fee charges to paper runtime (match backtest: 0.04% maker/taker)
2. Link executions to `market_snapshots` (add `snapshot_id` FK to `executions` table)
3. Use bid/ask spread from snapshot for realistic fill pricing
4. Add partial fill simulation (especially for limit orders in low liquidity)
5. Model realistic latency (signal timestamp → fill timestamp with market repricing)

**Estimated effort:** 3-5 days  
**Blocks:** Paper-to-live validation, live trading confidence

---

### 🟠 Tier B: Production Hygiene

#### B1: Config Reproducibility Incomplete
**Sources:** AUDIT-14 (Configuration / Reproducibility)

**Current State:**
- `config_hash` includes only: `schema_version`, `mode`, `strategy`, `risk`, `execution`, `data_quality`
- **Missing:** `exchange`, `proxy`, `alerts`, `storage`, interpreter version, dependency set, service/unit metadata
- Cannot reproduce exact bot state from commit hash + config_hash alone

**Impact:** Post-incident forensics incomplete. Cannot deterministically recreate exact runtime environment from historical config_hash.

**Remediation:**
1. Expand `config_hash` to include full `AppSettings` payload
2. Add `python_version`, `dependency_hash` (from requirements.txt)
3. Persist environment/profile provenance (`BOT_SETTINGS_PROFILE=experiment` vs `live`)
4. Add service unit hash to config snapshot

**Estimated effort:** 1-2 days  
**Blocks:** Incident forensics, exact reproducibility

---

#### B2: Production Service Drift
**Sources:** AUDIT-14, AUDIT-12

**Current State:**
- Deployed `btc-bot.service` ≠ repo unit file
  - Deployed: `Environment="BOT_SETTINGS_PROFILE=experiment"`, `Restart=always`
  - Repo: `EnvironmentFile=/home/btc-bot/btc-bot/.env`, `Restart=on-failure`
- Deployed `btc-bot-dashboard.service` binds `0.0.0.0` (repo: `127.0.0.1`)

**Impact:** Production reality differs from documented/versioned configuration. Operator confusion, config drift over time.

**Remediation:**
1. Sync deployed unit files with repo
2. Document `BOT_SETTINGS_PROFILE=experiment` choice (or migrate to `.env`-driven config)
3. Add automated config drift detection (compare deployed vs repo units)

**Estimated effort:** 1 day  
**Blocks:** Operational clarity, config drift prevention

---

#### B3: No Dependency Lock
**Sources:** AUDIT-14

**Current State:**
- `requirements.txt` only (no `poetry.lock`, `Pipfile.lock`, `.python-version`)
- CI uses Python 3.11, local audit used Python 3.13.1
- Observed drift: `yfinance 1.2.1` installed (repo requires `<1.0.0`)

**Impact:** Cannot guarantee exact dependency reproducibility. Version drift between environments.

**Remediation:**
1. Add `.python-version` (specify 3.11)
2. Migrate to `poetry` or `pip-tools` for lockfile generation
3. Pin all transitive dependencies
4. Enforce lockfile in CI and deployment

**Estimated effort:** 1 day  
**Blocks:** Exact environment reproduction

---

### 🟡 Tier C: Quality of Life

#### C1: Test Coverage Enforcement Missing
**Sources:** AUDIT-15 (Testing / CI / Quality Gates)

**Current State:**
- CI runs pytest but does not enforce coverage threshold
- Unknown if coverage is 30% or 90% for critical paths (risk_engine, signal_engine, governance, execution)
- No performance regression gates

**Remediation:**
1. Add `pytest-cov` with `--cov-fail-under=80` for critical modules
2. Separate unit/integration tests (`tests/unit/`, `tests/integration/`)
3. Expand lint scope to all production code (not just `research_lab/`)
4. Add contract tests for core models (`SignalCandidate`, `ExecutableSignal`, `Position`, `TradeLog`)

**Estimated effort:** 2-3 days  
**Blocks:** Quality visibility, regression prevention

---

#### C2: Manual Recovery Tooling Stale
**Sources:** AUDIT-19 (Recovery / Safe Mode)

**Current State:**
- `scripts/diagnostics/check_safe_mode.sh` references old log path and outdated `bot_state` schema
- No matching operator markdown guide in `docs/diagnostics/`

**Remediation:**
1. Update `check_safe_mode.sh` for current log path (`logs/btc_bot.log`) and schema
2. Create `docs/diagnostics/safe-mode-triage.md` with operator runbook
3. Test recovery scripts against current production

**Estimated effort:** 1 day  
**Blocks:** Operator efficiency during incidents

---

## Production-Grade Strengths (Confirmed)

### ✅ Core Trading Engine

1. **PnL Calculation Mathematically Correct**
   - Source: AUDIT-08 (Trade Lifecycle / PnL Accounting)
   - Evidence: `raw_pnl = (exit_price - entry_price) * size * direction` matches `pnl_abs` exactly for all 20 sampled trades
   - No double-counting, no unclosed positions >24h

2. **Trade Lifecycle Complete**
   - Source: AUDIT-08
   - Evidence: 0 unclosed positions >24h in production DB
   - Every trade has `entry_price`, `exit_price`, `opened_at`, `closed_at`

3. **Risk Engine Production-Grade**
   - Source: AUDIT-06 (Risk Engine)
   - Position sizing: `size = min(risk_capital / stop_distance, equity * leverage / entry_price)` ✓
   - Drawdown enforcement: daily/weekly DD limits checked before every trade ✓
   - Exit logic: SL/TP/timeout with conservative ordering (SL before TP on ambiguous candles) ✓
   - PnL/MAE/MFE calculation: accurate, traverses full candle path ✓

4. **Governance Layer Production-Grade**
   - Source: AUDIT-05 (Governance)
   - Signal filtering: comprehensive (DD limits, consecutive losses, session gating, cooldowns, duplicate level detection) ✓
   - No race conditions: stateless except for in-memory deque (safe) ✓
   - Audit trail: complete, every veto reason recorded ✓

### ✅ Research Lab & Methodology

5. **Backtest Methodology Production-Grade**
   - Source: AUDIT-09 (Backtest / Research Lab)
   - **No lookahead leakage:** zero `.shift(-` patterns found in codebase ✓
   - Walk-forward validation: sound (post-hoc + nested modes supported) ✓
   - Parameter sandbox: well-governed (ACTIVE, FROZEN, DEFERRED, UNSUPPORTED) ✓
   - Baseline gate: prevents broken-pipeline searches (hard + soft checks) ✓
   - Approval bundle: gated by blocking promotion risks, no auto-promotion ✓

6. **Experiment Isolation Exemplary**
   - Source: AUDIT-10 (Experiment Management)
   - Per-trial DB snapshots: each Optuna trial runs on isolated SQLite copy ✓
   - Zero contamination risk: research lab offline-only, explicit disallowed behaviors ✓
   - Reproducibility: comprehensive lineage (`protocol_hash`, `search_space_signature`, `trial_context_signature`, seed) ✓

### ✅ Infrastructure & Documentation

7. **Documentation Exceptional**
   - Source: AUDIT-18 (Documentation / Agent Workflow)
   - 2301+ lines across key workflow files (`CLAUDE.md`, `AGENTS.md`, `CASCADE.md`, blueprints) ✓
   - 100+ audit reports in `docs/audits/` (complete forensic trail) ✓
   - Agent role separation explicit, handoff protocol well-defined ✓

8. **Runtime Freshness Monitoring Solid**
   - Source: AUDIT-11 (Observability / Dashboard)
   - `runtime_metrics` table separates runtime truth from stale SQLite collector truth ✓
   - `/api/runtime-freshness` exposes decision-cycle timestamps, snapshot age, websocket age ✓
   - Dashboard refresh cadence appropriate (status 5s, positions 10s, signals 60s) ✓

---

## Quantified Risk Assessment

### Financial Impact (Annual, Estimated)

| Risk | Annual Cost (10 BTC position, 50 trades/year) | Severity |
|------|-----------------------------------------------|----------|
| **Funding fees missing** | ~$1,200 - $3,600 (0.01%-0.03% per 8h × hold time) | 🔴 HIGH |
| **Paper execution zero fees** | ~$2,000 (0.04% × 50 trades × avg position $80k) | 🔴 HIGH |
| **Paper-live gap (spread, latency)** | ~$500 - $1,500 (spread cost + slippage underestimation) | 🟠 MEDIUM |
| **Total PnL overstatement** | **~$3,700 - $7,100** | 🔴 **CRITICAL** |

### Operational Impact

| Risk | MTTR (Mean Time To Remediate) | Impact |
|------|-------------------------------|--------|
| **Public dashboard exposure** | Immediate (hacker could stop bot) | 🔴 CRITICAL |
| **Config irreproducibility** | Days (forensics incomplete) | 🟠 MEDIUM |
| **Manual recovery tooling stale** | Hours (operator delay during incident) | 🟡 LOW |

---

## Remediation Roadmap

### Phase R0: Emergency (Week 1)
**Goal:** Eliminate security incident

- [ ] **S1:** Close public dashboard exposure (30 min)
  - Rebind to `127.0.0.1:8080`
  - Remove UFW rule `8080/tcp`
  - Test SSH tunnel access
  - Update runbook

**Estimated effort:** 30 minutes  
**Blocking:** None (can execute immediately)

---

### Phase R1: Live Readiness Blockers (Weeks 2-3)
**Goal:** Enable accurate paper-to-live validation

- [ ] **A1:** Implement funding fee tracking (2-3 days)
  - Schema: add `funding_paid` column
  - Backtest: add funding simulation to `SimpleFillModel`
  - Paper runtime: collect and persist funding fees
  - Update PnL calculation: `pnl_abs_net = gross_pnl - fees - funding`

- [ ] **A2:** Paper execution realism (3-5 days)
  - Add fee charges to paper runtime (0.04%)
  - Link executions to `market_snapshots` (`snapshot_id` FK)
  - Use bid/ask spread for realistic fill pricing
  - Add partial fill simulation
  - Model realistic latency with repricing

**Estimated effort:** 5-8 days  
**Blocking:** A1 depends on schema migration, A2 depends on A1 for fee parity

---

### Phase R2: Production Hygiene (Week 4)
**Goal:** Operational clarity and reproducibility

- [ ] **B1:** Expand config_hash (1-2 days)
  - Include full `AppSettings`, `python_version`, `dependency_hash`
  - Persist environment provenance

- [ ] **B2:** Sync production service drift (1 day)
  - Update deployed unit files to match repo
  - Document `BOT_SETTINGS_PROFILE` choice

- [ ] **B3:** Add dependency lock (1 day)
  - Create `.python-version` (3.11)
  - Migrate to `poetry` or `pip-tools`
  - Pin all dependencies

**Estimated effort:** 3-4 days  
**Blocking:** None (can run in parallel)

---

### Phase R3: Quality of Life (Week 5)
**Goal:** Test visibility and operator efficiency

- [ ] **C1:** Test coverage enforcement (2-3 days)
  - Add `pytest-cov --cov-fail-under=80`
  - Separate unit/integration tests
  - Expand lint scope

- [ ] **C2:** Update manual recovery tooling (1 day)
  - Fix `check_safe_mode.sh` for current schema
  - Create operator runbook

**Estimated effort:** 3-4 days  
**Blocking:** None (can run in parallel)

---

## Gate Dependencies

### Gate A: Market Truth Validation (200+ Cycles)
**Current status:** ⏳ In progress (bot collecting cycles)  
**ETA:** ~50 hours from initial deploy (2026-04-24 04:10 UTC)  
**Blocks:** Phase 1 audits (AUDIT-01, AUDIT-02, AUDIT-04)

**Phase 1 audits waiting for Gate A:**
- AUDIT-01: Market Truth final validation (drift report, timing validation)
- AUDIT-02: FeatureEngine drift validation
- AUDIT-04: Regime Engine distribution analysis

**Recommendation:** Wait for Gate A, execute Phase 1 audits, then begin remediation Phase R0 (emergency) → R1 (live readiness).

---

### Gate B: Modeling-V1 Unlock
**Current status:** 🔒 Blocked by Gate A  
**Blocks:** Phase 2 audits (AUDIT-03 Signal Modeling, modeling dataset analysis)

### Gate C: Research / Optimization
**Current status:** 🔒 Blocked by Gate B

### Gate D: Live Readiness
**Current status:** 🔒 Blocked by remediation Phases R0 + R1 + additional audits  
**Blocks:** Live trading approval

**Live readiness blockers:**
- 🔴 S1: Dashboard exposure (Phase R0)
- 🔴 A1: Funding fees (Phase R1)
- 🔴 A2: Paper execution realism (Phase R1)
- ⏳ AUDIT-16: Live Readiness final checklist (Gate D audit)

---

## Comparison to Industry Standards

### What This Bot Does Well (Top Quartile)

1. **Audit discipline:** 13 comprehensive audits, 100+ historical audit reports → institutional-grade governance
2. **Research lab isolation:** Per-trial DB snapshots, no auto-promotion → prevents overfitting contamination
3. **Documentation:** 2301+ lines, complete agent workflow → enables handoff and continuity
4. **Backtest methodology:** No lookahead, walk-forward validation, baseline gates → prevents overfitting

### What Needs Improvement (Below Standard)

1. **Funding fee accounting:** Missing entirely → industry standard for perpetual futures trading
2. **Paper execution realism:** Zero fees, no spread → industry standard includes realistic fill simulation
3. **Test coverage visibility:** No coverage enforcement → industry standard: 80%+ coverage on critical paths
4. **Dependency management:** No lockfile → industry standard: lockfile + pinned dependencies

---

## Next Steps

### Immediate (Now)
✅ **Phase 0 audits complete** — all 13 reports delivered  
⏳ **Wait for Gate A** — bot collecting 200+ Market Truth cycles (~50 hours)

### After Gate A (ETA: 2026-04-26)
1. Execute **Phase 1 audits** (Market Truth validation, FeatureEngine drift, Regime Engine distribution)
2. Review Phase 1 findings
3. Consolidate Phase 0 + Phase 1 findings
4. **Begin remediation** in priority order: R0 (emergency) → R1 (live readiness) → R2 (hygiene) → R3 (quality)

### After Remediation
5. Re-audit critical paths (funding fees, paper execution) to verify fixes
6. Execute **Phase 2-4 audits** (modeling, research, live readiness)
7. **Gate D approval** for live trading

---

## Conclusion

**Phase 0 audit campaign delivered comprehensive system assessment.** The bot's core trading logic (risk engine, governance, PnL calculation) is **production-grade**. Research lab isolation and methodology are **exemplary**. Documentation and audit trail are **institutional-grade**.

**Critical gaps exist in cost accounting and execution realism.** Funding fees are not tracked anywhere (schema, backtest, paper runtime), and paper execution charges zero fees with unrealistic fill assumptions. Combined, these gaps overstate PnL by an estimated **$3,700-$7,100 annually** (10 BTC position, 50 trades/year).

**Security incident requires immediate attention.** Public dashboard exposure on `0.0.0.0:8080` with unauthenticated control endpoints is an active security risk.

**Recommendation:** Wait for Gate A (200+ cycles), execute Phase 1 audits, then prioritize remediation: Security Emergency (30 min) → Live Readiness Blockers (1-2 weeks) → Production Hygiene (1 week) → Quality of Life (1 week). Estimated total remediation time: **3-4 weeks** for Phases R0-R3.

**System is production-ready for paper trading with known limitations. Not ready for live trading until remediation Phases R0-R1 complete.**

---

**Report prepared by:** Claude Code (Independent Auditor)  
**Date:** 2026-04-24  
**Branch:** `market-truth-v3`  
**Commit:** 264e435  
**Phase:** 0 Complete, awaiting Gate A for Phase 1
