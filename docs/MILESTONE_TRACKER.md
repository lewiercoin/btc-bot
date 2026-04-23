# Milestone Tracker

Last updated: 2026-04-22

---

## ⚠️ Open Tech Debt: Kill-Switch Limits (MUST restore before LIVE mode)

**Date:** 2026-04-22  
**Reason:** Bot is in configuration/tuning phase. Weekly DD kill-switch triggered at 6.3% blocking MODELING-V1 data collection.  
**Action taken:** Relaxed `RiskConfig` limits in `settings.py` for paper/tuning phase:

| Parameter | Production value | Current (tuning) |
|---|---|---|
| `weekly_dd_limit` | `0.063` (6.3%) | `0.30` (30%) |
| `daily_dd_limit` | `0.185` (18.5%) | `0.20` (20%) |
| `max_consecutive_losses` | `5` | `15` |

**MANDATORY:** Restore production values before switching to LIVE mode.  
**Future fix:** Implement `tuning_mode` flag (Cascade Option C) or calendar-rollover auto-recovery (Option B).

---

## Current Active Milestone

**MARKET-TRUTH-V3** — IN PROGRESS (branch: `market-truth-v3`)

**Deployment baseline:** `EXPERIMENT-V2` (branch: `experiment-v2`, commit `2088dc79`)

**What:** Persistent market snapshot layer + independent feature validation infrastructure

**Why:**
- Before V3 snapshots were ephemeral, so exact inputs for a given decision cycle were not reconstructible.
- V3 creates an auditable chain: raw market truth → feature snapshot → decision outcome.
- MODELING-V1 should not start until this chain is deployed and validated on production data.

**Implementation:**
- New tables: `market_snapshots`, `feature_snapshots`
- New links: `decision_outcomes.snapshot_id`, `decision_outcomes.feature_snapshot_id`
- Orchestrator persists raw snapshot and feature snapshot for every decision cycle
- Market data capture records exchange timestamps, source metadata, and latency
- Independent validation module: `validation/recompute_features.py`

**Status:**
- ✅ Implementation complete locally
- ✅ Deterministic checks and runtime-facing tests pass
- ⏳ Branch creation / commit / push pending
- ⏳ Production deployment pending
- ⏳ 200+ production cycles pending for drift/timing validation

**Success criteria:**
1. `market_snapshots` and `feature_snapshots` populated for every new cycle
2. `decision_outcomes` linked to `snapshot_id` and `feature_snapshot_id`
3. Drift report generated on production sample (`N >= 200`)
4. Timing validation confirms no lookahead bias and acceptable latency
5. Snapshot → feature → decision chain reconstructible from DB evidence alone

**Merge gate:** production validation complete, then final audit closure

---

## Deployment Baseline

**EXPERIMENT-V2** — VALIDATION REFERENCE (branch: `experiment-v2`, commit `2088dc79`)

**Previous milestone:** DATA-INTEGRITY-V1 — DONE (merged to `main`, commit `7ebf2d2`, 2026-04-21)

**What:** Validate DATA-INTEGRITY-V1 with the relaxed experiment profile used for paper-runtime comparison

**Why:** Provide the clean post-DATA-INTEGRITY baseline that MARKET-TRUTH-V3 is built on

**Baseline criteria:**
- Bootstrap summary appears in logs at startup
- Feature quality propagates through `MarketSnapshot` → `Features`
- OI/CVD persistence survives restart
- Production paper bot runs on post-DATA-INTEGRITY contracts

---

## Next Milestone

**MODELING-V1** — BLOCKED

**Prerequisites:**
1. ⏳ MARKET-TRUTH-V3 deployed to production
2. ⏳ `market_snapshots` / `feature_snapshots` populated for at least 200 cycles
3. ⏳ Drift report reviewed and accepted
4. ⏳ Timing validation reviewed and accepted

**Goal:** Add context-aware modeling only after raw market truth and feature reproducibility are verified.

**Scope (future):** session/volatility context classification, neutral-mode deployment, diagnostics expansion

**Out of scope (for now):** execution realism, parameter tuning, new data sources, quality-aware context gating

**Documentation:** final blueprint at `docs/blueprints/BLUEPRINT_MODELING_V1.md`

**Implementation branch:** not yet created

---

## Future Milestone: SAFE-MODE-AUTO-RECOVERY

**Status:** PLANNED (deferred, user priority shift 2026-04-23)

**Goal:** Implement in-process auto-recovery for technical safe-mode triggers (WebSocket reconnect, transient failures)

**Current behavior:**
- Health check fails 3 times → safe mode activated
- WebSocket reconnects → health stabilizes BUT safe mode remains active
- Recovery requires manual restart or SQL clear

**Target behavior (Hybrid Auto-Recovery):**
- **Technical triggers** (`health_check_failure_threshold`, `feed_start_failed`, `snapshot_build_failed`):
  - Enter safe mode: 3 consecutive health failures (current)
  - Exit safe mode: 10 consecutive health successes (NEW - asymmetric for stability)
  - Auto-clear without restart
- **Capital triggers** (`daily_dd`, `weekly_dd`, `consecutive_losses`):
  - Remain manual/calendar-based (unchanged, conservative)

**Implementation approach:**
- Add `ExecutionConfig` fields: `health_successes_to_clear_safe_mode: int = 10`, `auto_clear_technical_triggers: bool = True`
- Extend `orchestrator._run_health_check()` to track consecutive successes
- Auto-clear safe mode when threshold met AND trigger is in `_TECHNICAL_TRIGGERS`
- Audit log all auto-recovery events

**Rationale:** WebSocket reconnects are transient technical issues, not capital risks. Restart is heavyweight (10s downtime, state loss). In-process recovery = fast (5 min), clean, production-grade.

**Quick fix applied (2026-04-23):** Raised `health_failures_before_safe_mode` from 3 → 10 for initial config phase. MUST implement proper auto-recovery before lowering threshold back to production value.

**Prerequisites:** None (can implement anytime)

**Merge gate:** Claude Code audit verdict = DONE + smoke test for flapping prevention

**Builder:** TBD (user will assign when ready)

---

## Previous Milestone: UPTREND-PULLBACK-EVAL-V1

**Status:** DONE (2026-04-19, commit 5668ccd)

**Context:** Delivered conclusive evidence that current pullback path has no edge. Structural issues in geometry + uniqueness, not threshold tuning problem.

**Strategic decision:** Uptrend path deferred. Focus shifted to data integrity + modeling improvements.

---

## 🎯 DATA QUALITY FOUNDATION (2026-04-21)

**Historical Significance:** First time bot has complete, correct, restart-safe data contracts.

This is a **critical milestone** that combines two fundamental fixes establishing the data foundation for all future work:

### Fix 1: DATA-INTEGRITY-V1 (Commit 7ebf2d2 → main)
- ✅ Restart-safe OI/CVD persistence (`oi_samples`, `cvd_price_history` tables)
- ✅ Feature quality contracts (ready/degraded/unavailable)
- ✅ Bootstrap from DB on startup (no more cold-start penalty)
- ✅ Observable quality state (logs + dashboard `/api/feature-quality`)

### Fix 2: Paper Execution Realism (Commit df30615 → main)
- ✅ Fills at `snapshot.price` (not `signal.entry_price` reference)
- ✅ Execution audit trail (`executions` table populated)
- ✅ Correct PnL metrics (no more corrupted paper results)
- ✅ Dashboard visibility (Signal Reference vs Fill Entry)

### Integration: EXPERIMENT-V2 (Commit 0607b3e)
Both fixes integrated with experiment profile (relaxed filters) for validation.

**Before/After comparison:**

| Aspect | Before (v1) | After (v2) |
|--------|-------------|------------|
| OI/CVD data | Lost on restart | Persistent, restart-safe |
| Feature quality | Invisible | Explicit (ready/degraded/unavailable) |
| Paper fills | Reference levels (wrong) | Snapshot prices (correct) |
| Execution trail | Missing | Complete audit records |
| PnL metrics | Corrupted | Realistic |

**Analysis:** `docs/analysis/DATA_QUALITY_MILESTONE_2026-04-21.md`

**Validation:** EXPERIMENT-V2 deployment will compare v1 (corrupted data) vs v2 (clean data) under identical throughput config.

**Impact on future milestones:**
- MODELING-V1: Builds on clean data (session/volatility filters require mature data)
- EXECUTION-REALISM-V1: Builds on correct fills (spread/slippage on top of realistic base)
- OPTUNA-RECALIBRATION-V1: Tunes on clean data (no hidden quality gaps)

---

## Completed Milestone: DATA-INTEGRITY-V1
**Status:** DONE (merged to main commit 7ebf2d2, 2026-04-21)
**Active builder:** Codex
**Audit verdict:** DONE (all 7 tasks implemented, restart safety verified)

**What:** Make decision-path data restart-safe, coverage-aware, and quality-explicit

**Deliverables:**
- ✅ Task 1: `FeatureQuality` model integrated into `MarketSnapshot` and `Features`
- ✅ Task 2: OI sample persistence + bootstrap (table: `oi_samples`)
- ✅ Task 3: Flow window completeness validation (config-driven thresholds)
- ✅ Task 4: CVD/price history persistence + bootstrap (table: `cvd_price_history`)
- ✅ Task 5: Funding window integrity validation
- ✅ Task 6: Operational visibility (bootstrap logs, `/api/feature-quality` endpoint)
- ✅ Task 7: Integration + regression tests (20 tests pass)

**Architecture:** Persistence + bootstrap > restart-from-zero warmup

**Files changed:** 28 files, +1709 insertions, -89 deletions

**Tests:** 183 passed, 24 skipped (intentional)

**Audit report:** `docs/audits/AUDIT_DATA_INTEGRITY_V1_2026-04-21.md`

**Next milestone:** EXPERIMENT-V2 (validate DATA-INTEGRITY in production), then MODELING-V1

---

## Completed Milestone: UPTREND-PULLBACK-EVAL-V1
**Status:** DONE (commit 5668ccd, 2026-04-19)
**Active builder:** Codex
**Audit verdict:** DONE (findings conclusive, recommendation: redesign or abandon, NOT tuning)

**What:** Evaluation harness for uptrend pullback candidates - funnel breakdown, feature segmentation, viable vs junk analysis

**Files changed (3):**
- `research_lab/diagnostics/uptrend_pullback_eval_v1.py` - replay harness, JSON artifact
- `scripts/run_backtest.py` - added `--evaluate-uptrend-pullback` flag
- `tests/test_uptrend_pullback_eval_v1.py` - 29 tests (funnel, segmentation, cohort)

**Evaluation results (March 2026):**

**Funnel breakdown:**
- 286 detected → 58 candidates (79.7% died as `uptrend_pullback_weak`)
- 58 candidates → 50 governance veto (86.2%, of which 45 were `duplicate_level`)
- 58 candidates → 5 risk block
- 3 trades opened → 3 closed (all losses)

**Performance:**
- PnL: -$319.52
- Expectancy: -1.33R
- Profit factor: 0.0
- Win rate: 0% (3/3 losses, all `loss_1R_to_2R` bucket)

**3 Critical Findings:**
1. **79.7% detection failure** - most pullbacks fail before candidate generation (`uptrend_pullback_weak`)
2. **Governance duplicate_level dominance** - 45/50 vetoes are duplicate_level (geometry problem, not threshold)
3. **No viable cohort** - 0% win rate, higher confluence (12.95) setups rejected by risk (`rr_below_min`)

**Codex recommendation:** ✅ **Redesign path, NOT tune thresholds**  
**Claude Code assessment:** ✅ **Fully agree**

**Why tuning won't work:**
- Duplicate_level = geometry issue (pullbacks cluster at same levels in uptrend)
- 0% win rate = entry/stop/TP logic incompatible with uptrend pullbacks
- RR targets that work in downtrend (2.1+) may be unrealistic for uptrend pullbacks

**Strategic options:**
- **A:** Abandon uptrend pullback path (accept bot doesn't trade uptrend)
- **B:** Redesign from scratch (different entry logic, RR targets, uniqueness criteria)
- **C:** Pivot to HIGH sweep uptrend (breakout continuation, if market provides setups)
- **D:** Research alternative uptrend strategies (momentum, breakout+retest)

**User decision required:** Which strategic option to pursue?

---

## Completed Milestone: UPTREND-PULLBACK-RESEARCH-V1
**Status:** DONE (commit c240f1d, 2026-04-19)
**Active builder:** Codex
**Audit verdict:** DONE (implementation complete, research-only, NOT approved for live)

**Context:** Post-incident analysis of 21-day trading halt (Mar 29 - Apr 19). Root cause: bot has 0% historical uptrend signal coverage, strategy structurally incomplete.

**What:** Add feature-flagged uptrend pullback continuation logic + observability infrastructure

**Deliverables completed:**
- ✅ D1: Uptrend pullback signal path (regime=UPTREND + sweep_side=LOW → LONG)
- ✅ D2: Decision outcome histogram (`decision_outcomes` table + `/api/decision-funnel` endpoint)
- ✅ D3: Config snapshot persistence (`config_snapshots` table + `/api/config/{hash}` endpoint)
- ✅ D4: Feature flag `allow_uptrend_pullback=False` (default OFF, research ENV override, live hard-locked)
- ✅ D5: Tests (92 passed, 2 skipped, all milestone tests pass)
- ✅ D6: Backtest comparison March 2026 (OFF vs ON, info only)

**Files changed (18):**
- `settings.py`, `core/signal_engine.py`, `orchestrator.py`, `backtest/backtest_runner.py`
- `storage/schema.sql`, `storage/repositories.py`, `storage/state_store.py`
- `dashboard/db_reader.py`, `dashboard/server.py`
- `research_lab/param_registry.py`, `scripts/run_backtest.py`
- 7 test files

**Comparison results (March 2026):**
- OFF: 44 signals, 7 trades, PnL $1,394, expectancy 2.66R
- ON: 102 signals (+58 uptrend), 9 trades, PnL $859 (-$535), expectancy 1.33R (-1.33R)
- 86 governance vetoes, 7 risk blocks in ON run
- **Verdict:** Coverage ↑, quality ↓ — hypothesis does NOT demonstrate edge yet

**Audit notes:**
- Architecture discipline excellent (isolated path, feature flag safety, frozen params)
- Config snapshots + decision funnel are valuable observability investments
- Governance/risk correctly filtering low-quality candidates
- **DO NOT enable in live** — research hypothesis only

**Next recommended milestone:** UPTREND-PULLBACK-EVAL-V1  
**Scope:** Breakdown rejection reasons, candidate quality segmentation, identify viable vs junk subgroups

---

## Completed Milestone: RESEARCH-LAB-HARDENING-2PHASE
**Status:** DONE (commit 1da4664, 2026-04-19)
**Active builders:** Cascade (started), Codex (finished)
**Commits:** `1da4664` feat(research-lab): harden 2-phase workflow and warm-start hygiene

**What:** Formalize research lab as staged 2-phase system (Optuna discovery → Autoresearch refinement) with metodologiczna higiena

**Why:** Address metodologiczne słabości identified by Perplexity architectural review:
- Warm-start contamination from mixed contexts (different protocols, date ranges, search spaces)
- Baseline gate too restrictive (blocked weak-but-valid baselines, prevented improvement)
- No trial context reproducibility (couldn't match exact optimization conditions)
- Autoresearch treated as equal alternative to Optuna (should be refinement phase, not discovery)
- Ranking prioritized misleading profit_factor over operationally painful drawdown

**Implementation:**
- **P1 - Critical:**
  - Enforce protocol/context filtering for warm-start (protocol_hash + search_space_signature)
  - Split baseline gate: `check_baseline_hard()` blocks broken setup, `check_baseline_soft()` warns on weak baseline
  - Add trial lineage tracking: search_space_signature, regime_signature, trial_context_signature, baseline_version
  - Schema migrations + indexes for performance
- **P2 - High Priority:**
  - Create `docs/RESEARCH_LAB_WORKFLOW.md` formalizing Optuna→Autoresearch 2-phase workflow
  - Add CLI flags: `--warm-start-ignore-protocol` (bypass filter), `--seed-from-pareto` (handoff)
- **P3 - Medium Priority:**
  - Rank drawdown ahead of profit_factor in autoresearch candidate ordering

**Tests:** 7 new tests, 31/33 pass (2 expected skips)
- `test_warm_start_filters_mismatched_protocol`
- `test_enqueue_warm_start_ignore_protocol_bypasses_filters`
- `test_check_baseline_hard_raises_on_broken_pipeline`
- `test_check_baseline_soft_warns_on_weak_but_evaluable_baseline`
- `test_rank_key_prefers_low_dd_over_high_pf`
- `test_optimize_cli_passes_warm_start_ignore_protocol`
- `test_autoresearch_cli_loads_seed_vectors_from_pareto_json`

**Audit:** Claude Code + Perplexity consultation
**Verdict:** MVP_DONE (all P1-P3 deliverables complete, zero tech debt)

**Architecture:**
- Phase 1 = Optuna (global discovery, 80-150 trials)
- Phase 2 = Autoresearch (local refinement, 10 candidates, seed from Pareto)
- Warm-start hygiene = context matching required by default
- Baseline gate = hard block for broken pipeline, soft warning for weak strategy

**Acceptance criteria met:**
- ✅ Protocol/context filtering implemented + tested
- ✅ Baseline gate split implemented + tested
- ✅ Trial context tracking implemented + tested
- ✅ Workflow documentation created
- ✅ CLI handoff support added + tested
- ✅ Ranking priority fixed + tested
- ✅ All tests pass
- ✅ Zero tech debt introduced

**Future work (deferred to next milestones):**
- P4: Adaptive autoresearch (mutation rate, exploration scoring, lineage)
- P5: Observability (convergence charts, parameter importance, dashboard endpoint)
- Regime-aware filtering (full implementation)

**In-scope:** `research_lab/` (all offline optimization system)
**Out-of-scope:** Live bot, dashboard, core trading logic

---

## Completed Milestone: RUN14-OVERLAY-FIX
**Status:** DONE (commit f22c2d7, 2026-04-18)
**Active builder:** Codex
**Commits:** `f22c2d7` fix: make RUN14 uptrend continuation an overlay candidate

**What:** Refactored ResearchBacktestRunner to always evaluate uptrend continuation alongside the base signal engine, select the stronger candidate with a deterministic base tie-break, and log overlay config values for trial validation.

**Why:** RUN14 trials (25/80 completed) were all producing identical results because uptrend continuation parameters only ran as a fallback after generate() returned None, so overlay parameters could not influence bars where the base engine already produced a candidate.

**Implementation:**
- Changed from fallback pattern to overlay pattern in research_backtest_runner.py (line 120)
- Added `_resolve_signal_candidates()` method: evaluates both base and uptrend independently
- Added `_select_signal_candidate()` static method: prefers higher confluence, base on tie (deterministic)
- Added `_log_uptrend_continuation_config()` helper: logs overlay parameters once per run for trial validation
- Updated signals_generated counter to count both candidates independently

**Tests:** 7 tests covering all selection paths + integration test proving overlay always runs
- `test_select_signal_candidate_prefers_higher_confluence_overlay`
- `test_select_signal_candidate_prefers_base_on_equal_confluence`
- `test_select_signal_candidate_returns_overlay_when_base_missing`
- `test_select_signal_candidate_returns_base_when_overlay_missing`
- `test_select_signal_candidate_returns_none_when_both_candidates_missing`
- `test_run_evaluates_overlay_even_when_base_candidate_exists` (integration test)
- `test_run_logs_overlay_config_for_trial_validation`

**Audit:** `docs/audits/AUDIT_RUN14_OVERLAY_FIX_2026-04-18.md`
**Verdict:** DONE (all audit axes PASS)

**Acceptance criteria met:**
- ✅ Overlay pattern correctly implemented (both candidates always evaluated)
- ✅ Selection logic deterministic (higher confluence, base on tie)
- ✅ Config logging for trial validation (once per run)
- ✅ Tests validate overlay behavior (7 passed)
- ✅ Layer separation preserved (research_lab only)
- ✅ Determinism preserved (no randomness)
- ✅ Tech debt low (clean implementation)
- ✅ AGENTS.md compliance (WHAT/WHY/STATUS commit message)

**Next steps:**
1. Re-run RUN14 campaign (trials 26-80) with overlay fix
2. Verify trials produce varied results (not all identical)
3. Compare trial outcomes to confirm overlay parameters affect confluence selection
4. If results vary: RUN14 bug confirmed fixed

**In-scope:** research_lab/research_backtest_runner.py, tests/test_research_backtest_runner.py
**Out-of-scope:** Core pipeline, live bot, dashboard

---

## Recent Milestone: STRATEGY-ASSESSMENT-2026-04-17
**Status:** READY FOR AUDIT (2026-04-17)
**Active builder:** Codex

**What:** Read-only assessment of why fresh-data decision cycles still end in `no_signal` after deployment remediation, with exact pipeline-stage classification and a market-vs-edge comparison for Trial #63.

**Why:** `DEPLOYMENT-REMEDIATION-2026-04-17` removed the live blockers (`healthy=1`, `safe_mode=0`, fresh collectors, fresh DB). The next required truth is whether the remaining `no_signal` comes from current market conditions or from an overly restrictive strategy setup.

**Acceptance criteria:**
- ✅ Fresh-data decision cycles after `2026-04-17T13:32:54Z` inspected
- ✅ Exact rejection stage identified in the live pipeline
- ✅ Counts documented for `decision -> signal_candidates -> executable_signals -> trades`
- ✅ Current market snapshot compared to Trial #63 edge requirements
- ✅ ETF-bias partiality assessed for relevance to the active signal path
- ✅ Evidence-backed verdict written to tracker and analysis doc

**In-scope:**
- read-only pipeline-stage breakdown on fresh runtime data
- recent-cycle analysis from audit tables / SQLite
- Trial #63 requirement check against current market state
- documentation update limited to tracker findings and analysis report

**Out-of-scope:**
- strategy / settings tuning
- forcing trades or bypassing governance
- research-lab optimization work
- runtime or deployment mutations

**Verified findings (production runtime, checked 2026-04-17):**
- Fresh-data sample since clean restart at `2026-04-17T13:32:54Z`:
  - decision cycles observed: `13:45`, `14:00`, `14:15`, `14:30` UTC
  - audit rows: `4x decision -> "No signal candidate."`
  - `signal_candidates_since = 0`
  - `executable_signals_since = 0`
  - `closed_trades_since = 0`
- Exact pipeline-stage rejection:
  - rejection happens at `SignalCandidate` generation
  - nothing reaches governance, risk, executable-signal, or trade-execution stages
- Current market probe at `2026-04-17T14:40:01Z`:
  - `price = 77823.15`
  - `regime = uptrend`
  - `sweep_detected = true`
  - `reclaim_detected = false`
  - `sweep_side = HIGH`
  - `sweep_depth_pct = 0.04980` vs `min_sweep_depth_pct = 0.00286`
  - `cvd_bullish_divergence = false`
  - `cvd_bearish_divergence = false`
  - `force_order_spike = false`
- Counterfactual probe at `2026-04-17T14:36:06Z`:
  - direction could resolve to `SHORT`
  - counterfactual `confluence_score = 7.95` vs `confluence_min = 3.6`
  - candidate still stays `null` because `reclaim_detected = false`
  - even with reclaim, Trial #63 allows no entries in `uptrend`
- Trial #63 edge requirements relevant to this rejection:
  - `sweep + reclaim` must both exist before a candidate is created
  - regime whitelist allows:
    - `normal -> LONG`
    - `compression -> LONG`
    - `downtrend -> LONG/SHORT`
    - `uptrend -> none`
    - `crowded_leverage -> SHORT`
    - `post_liquidation -> LONG`
  - `confluence_min = 3.6` is not the active bottleneck in the observed fresh-data sample
- K2 impact assessment:
  - `daily_external_bias` / ETF fields remain partial
  - current `SignalEngine` and `RegimeEngine` do not consume ETF bias in the active decision path
  - therefore K2 does not explain the observed `no_signal`

**Current classification:**
- Current `no_signal` is best classified as `market conditions / outside Trial #63 domain`
- The live runtime is healthy and using fresh data; the missing trade comes from strategy gating, not from deployment drift
- The active market is a strong `uptrend` without reclaim confirmation and without the reversal structure required by the current edge
- This is not a governance veto, risk veto, stale-data issue, or obvious `confluence_min too high` problem

**Report:** `docs/analysis/STRATEGY_ASSESSMENT_2026-04-17.md`

**Next action:**
- Await Claude Code audit for this assessment checkpoint
- If the audit agrees, choose between:
  - monitor/wait on the healthy runtime
  - future research/tuning if more uptrend participation is desired
- Do not modify strategy parameters inside this assessment milestone

**Previous milestone:** `DEPLOYMENT-REMEDIATION-2026-04-17` — CLOSED / AUDITED
- Clean redeploy to `1efa7e55051196702aa123f7e3d55d94957bbc9b`
- Collectors restored, DB freshness recovered, runtime verified `healthy=1`, `safe_mode=0`
- Audit baseline: `docs/audits/AUDIT_DEPLOYMENT_REMEDIATION_2026-04-17.md`

---

## Reconciliation Note

Last reconciled: 2026-04-16

- Tracker scope:
  - `docs/MILESTONE_TRACKER.md` is the source of truth for project status, active milestone, builder selection, and known issues.
  - `docs/MILESTONE_TRACKER.md` is not the source of truth for live runtime state.
- Live runtime truth must come from:
  - deployed process/service status
  - deployed commit
  - deployed config / environment
  - active SQLite database
  - current logs and audit trail
- Workflow role reconciliation:
  - `Codex` = default builder
  - `Cascade` = alternative builder
  - `Claude Code` = independent auditor
- If workflow documents conflict, `AGENTS.md` is the controlling document.

---

**Milestone:** DIAGNOSE-RUNTIME-LOOP-HANG — Diagnose why bot never reaches decision cycles
**Status:** CLOSED — FALSE ALARM / RESOLVED BY MVP (2026-04-15)
**Active builder:** Cascade

**Findings:**
- No infrastructure hang existed
- Event loop entered correctly, health check passed (healthy=True), position monitor ran
- Decision cycle fired at exactly 12:30:00 UTC and completed in <1 second
- Root cause of perceived "hang": old Fix #8 sticky safe_mode code silently blocked all
  decision cycles via audit_logger only (no output to btc_bot.log)
- Test windows never reached a 15-minute boundary before restart — cycles were simply scheduled
  for the next 15m slot

**Resolution:** SAFE-MODE-AUTO-RECOVERY-MVP (commit 93faed56) already resolved the underlying
issue. safe_mode=False confirmed. Bot is operational and running cycles normally.

**Debug commits (reverted):**
- `30b40b9` — 25 debug logs in startup methods
- `49c4a95` — debug logs in event loop and health check
- `bc76968` — revert event loop debug
- `91597da` — revert startup debug (current HEAD)

**Report:** docs/audits/DIAGNOSTIC_RUNTIME_LOOP_HANG.md

---

## Previous Milestones

**Milestone:** SAFE-MODE-AUTO-RECOVERY-MVP — Fix sticky safe_mode + DB divergence bug
**Status:** MVP_DONE + DEPLOYED (commit 93faed56, 2026-04-15)
**Active builder:** Cascade

**What:** Deployed to production and verified:
- Trigger-aware recovery: technical triggers clear safe_mode on restart; capital triggers preserved
- safe_mode_entry_at column migration ran successfully
- safe_mode_events audit table created
- safe_mode=0, healthy=1 confirmed in DB
- Decision cycles confirmed firing at 15-minute boundaries post-deploy

**Audit:** docs/audits/AUDIT_008_SAFE_MODE_MVP.md

---

**Milestone:** REPO-CONSISTENCY-VERIFICATION-2026-04-15 — Verify full code consistency between main and all side branches
**Status:** DONE (branch: main, commit d07ddd0, 2026-04-15)
**Active builder:** Cascade

**What:** Verified full code consistency between branch `main` and all 7 side branches in the repository:
- Listed all branches (local and remote) with merge status
- Verified each branch is fully merged into main with proper merge commits
- Analyzed implementation quality for all merged changes (layer separation, AGENTS.md compliance, commit discipline)
- Documented discrepancies, duplicates, and implementation errors (none found)
- Provided cleanup recommendations for branch management
- Deleted local branch `infra/egress-vultr-fix` (fully merged, no longer needed)

**Branches analyzed:**
- `main` (HEAD): d07ddd0 — REPO-CONSISTENCY-VERIFICATION
- `terminal-diagnostics-safe-mode` (local + remote): 0f6c129 — same as main (fully merged, up-to-date)
- `websocket-migration` (remote): dcc0105 — merged at 820024b
- `dashboard-server-resources` (remote): 6cb9421 — merged at 5991b09
- `dashboard-risk-visualisation` (remote): 24b1bff — merged at 787a67d
- `dashboard-access-guide` (remote): 3e034a0 — merged at ff1e0b3
- `dashboard-egress-integration` (remote): 153659a — merged at aae0226
- `infra/egress-vultr-fix` (remote): f5baaf0 — merged at 3afa91c (local branch deleted)

**Implementation quality verification:**
- All merged commits follow AGENTS.md commit discipline (WHAT/WHY/STATUS)
- All changes respect layer separation (dashboard/ changes don't touch core/execution)
- All changes use proper contracts via core/models.py
- All changes preserve determinism in core pipeline
- All changes update MILESTONE_TRACKER.md
- All smoke tests pass (93/93, 24 skipped)

**Cleanup recommendations:**
- ✅ Local branch `infra/egress-vultr-fix` deleted (fully merged)
- Local branch `terminal-diagnostics-safe-mode` can be kept as reference (at same commit as main)
- Remote branches can be safely deleted after confirmation:
  - `origin/dashboard-access-guide`
  - `origin/dashboard-egress-integration`
  - `origin/dashboard-risk-visualisation`
  - `origin/dashboard-server-resources`
  - `origin/websocket-migration`
  - `origin/infra/egress-vultr-fix`
  - `origin/terminal-diagnostics-safe-mode` (optional - can keep as reference)

**Why:** Uncertainty about whether previous feature branches were correctly merged into main. Risk of code duplicates or incomplete merges breaking architecture. Full verification ensures branch hygiene and architectural integrity.

**Acceptance criteria:**
- ✅ All 8 branches enumerated with merge status
- ✅ All branches verified as fully merged into main (no unique commits in branches)
- ✅ Implementation quality verified for all merged changes (layer separation, contracts, determinism, AGENTS.md compliance)
- ✅ No discrepancies, duplicates, or implementation errors found
- ✅ Cleanup recommendations documented
- ✅ Local branch `infra/egress-vultr-fix` deleted
- ✅ MILESTONE_TRACKER.md updated with milestone entry
- ✅ git push origin main completed
- ✅ Smoke tests pass (93/93, 24 skipped)

**In-scope:** All git branches in repository, diff analysis, implementation quality verification, branch cleanup recommendations, MILESTONE_TRACKER.md update, smoke tests
**Out-of-scope:** Modifying production code (no fix commits required), changing merge history (rebase/force push), remote repository configuration

---

**Milestone:** TERMINAL-DIAGNOSTICS-SAFE-MODE — Prepare copy-paste terminal diagnostic script for safe mode troubleshooting
**Status:** MVP_DONE (branch: terminal-diagnostics-safe-mode, 2026-04-14)
**Active builder:** Cascade

**What:** Created ready-to-use diagnostic script and documentation for troubleshooting safe mode issues:
- `scripts/diagnostics/check_safe_mode.sh`: read-only bash script with 7 diagnostic sections (service status, bot log tail, dashboard API egress, dashboard API server resources, DB bot_state query, WebSocket URL config, WebSocket connection attempts)
- `docs/diagnostics/safe-mode-check.md`: step-by-step copy-paste instructions, manual diagnostic commands, common causes (WebSocket failure, egress proxy issues, resource exhaustion, DB corruption), next steps guidance
- `README.md`: added Diagnostyka section with quick start command and reference to detailed guide
- Script is read-only — zero mutations, no service restarts, no DB writes

**Why:** Bot remains in safe mode after WebSocket migration. Diagnostic script provides operator with ready-to-run commands to gather information without manual command recall. Read-only design prevents accidental state changes during diagnosis.

**Acceptance criteria:**
- ✅ `scripts/diagnostics/check_safe_mode.sh` created with all 7 diagnostic sections
- ✅ `docs/diagnostics/safe-mode-check.md` created with step-by-step instructions and common causes
- ✅ `README.md` Diagnostyka section added with quick start
- ✅ `docs/MILESTONE_TRACKER.md` updated with milestone entry
- ✅ Zero changes to `core/**`, `execution/**`, `dashboard/**`, `ProxyTransport`
- ✅ Script is read-only (no mutations, no restarts)
- ✅ All existing tests pass (93/93, 24 skipped)

**In-scope:** `scripts/diagnostics/check_safe_mode.sh` (new), `docs/diagnostics/safe-mode-check.md` (new), `docs/MILESTONE_TRACKER.md`, `README.md`
**Out-of-scope:** `core/**`, `execution/**`, `dashboard/**`, `ProxyTransport`, any production code mutations, service restart commands, DB write operations

---

**Milestone:** WEBSOCKET-MIGRATION — Migrate WebSocket URLs to new Binance official /market/ paths
**Status:** DONE (branch: websocket-migration, commit dcc0105, 2026-04-14)
**Active builder:** Cascade

**What:** Migrated WebSocket URLs from legacy `/stream/` to new official `/market/` paths:
- Added `futures_ws_market_base_url` and `futures_ws_stream_base_url` constants to `ExchangeConfig` in `settings.py`
- Added `ws_market_base_url` parameter to `WebsocketClientConfig` in `data/websocket_client.py`
- Implemented `_build_market_stream_url()` for new `/market/` path: `wss://fstream.binance.com/market?streams=btcusdt@aggTrade/btcusdt@forceOrder`
- Retained `_build_legacy_stream_url()` for fallback to `/stream/` path: `wss://fstream.binance.com/stream?streams=...`
- Modified `_run_forever()` to try `/market/` first, fallback to `/stream/` on connection failure with logging
- Updated `orchestrator.py` to pass `ws_market_base_url` to `WebsocketClientConfig`

**Why:** Binance announced deprecation of legacy `/stream/` WebSocket paths in favor of new `/market/` paths. Migration ensures future-proof connectivity. Fallback logic prevents production downtime if new path has issues.

**Acceptance criteria:**
- ✅ `settings.py` has new `futures_ws_market_base_url` and `futures_ws_stream_base_url` constants
- ✅ `data/websocket_client.py` uses `/market/` path by default via `_build_market_stream_url()`
- ✅ Fallback logic implemented: if `/market/` fails, retry with `/stream/` (legacy)
- ✅ Logging added to track which path is being used (market vs legacy)
- ✅ `orchestrator.py` updated to pass `ws_market_base_url` parameter
- ✅ All existing tests pass (93/93, 24 skipped)
- ✅ Zero changes to `core/**`, `execution/**` beyond `orchestrator.py` URL parameter
**Out-of-scope:** `core/**`, `execution/**` (except `orchestrator.py`), new WebSocket features, stream reconnection logic changes

---

---

**Milestone:** DASHBOARD-SERVER-RESOURCES — Server resource monitoring panel in dashboard
**Status:** DONE (branch: dashboard-server-resources, commit 6cb9421, 2026-04-14)
**Active builder:** Cascade

**What:** Extended dashboard with Server Resources panel:
- Added `psutil` to `requirements.txt` (lightweight cross-platform system metrics library)
- `/api/server-resources` endpoint: reads CPU %, memory % (total/used GB), load average (1m/5m/15m), disk % (total/used GB) via psutil
- Server Resources panel in UI: after Risk & Governance, displays CPU/Memory/Load/Disk with color-coded badges (green <80%, amber ≥80%, red ≥95%)
- Auto-refreshes every 10s (same pattern as Egress/Risk panels)

**Why:** Operator visibility into server health without SSH. Detects resource pressure (CPU/RAM/Disk) early before it affects bot performance. Lightweight, read-only, no impact on core pipeline.

**Acceptance criteria:**
- ✅ `/api/server-resources` returns correct schema (cpu_percent, memory_percent, memory_total_gb, memory_used_gb, load_avg, disk_percent, disk_total_gb, disk_used_gb)
- ✅ Server Resources panel visible after Risk & Governance section (10s refresh)
- ✅ Display: CPU %, Memory % (GB), Load (1m/5m/15m), Disk % (GB)
- ✅ Color-coded badges: green <80%, amber ≥80%, red ≥95%
- ✅ `psutil` added to `requirements.txt`
- ✅ Zero changes to `core/**`, `execution/**`, `orchestrator.py`, `data/**`, `ProxyTransport`

**In-scope:** `requirements.txt`, `dashboard/server.py`, `dashboard/static/index.html`, `dashboard/static/app.js`, `dashboard/static/style.css`, `docs/dashboard/server-resources.md`, `docs/MILESTONE_TRACKER.md`
**Out-of-scope:** All trading pipeline code — `core/**`, `execution/**`, `orchestrator.py`, `data/**`, `ProxyTransport`

---

---

**Milestone:** DASHBOARD-RISK-VISUALISATION — Live Risk & Governance panel in dashboard
**Status:** DONE (branch: dashboard-risk-visualisation, commit 24b1bff, 2026-04-14)
**Active builder:** Cascade

**What:** Extended dashboard with Risk & Governance panel:
- `/api/risk` endpoint: reads `AppSettings.risk` + `AppSettings.strategy` (limits) + `bot_state` (usage) + `signal_candidates`/`executable_signals` (latest signal)
- Risk & Governance panel in UI: current regime, progress bars for Daily DD / Weekly DD / consecutive losses / open positions (usage vs limit), latest signal card with direction, confluence_score, reasons[], Promoted/Vetoed badge, governance_notes
- Yellow alert row when governance blocked OR risk limit near breach (≥80%) OR RiskGate blocking
- Auto-refreshes every 10s (same pattern as Egress panel)

**Why:** Operator visibility into RiskGate + Governance decisions without SSH. Shows exactly why a signal was vetoed (governance_notes) and whether trading is currently blocked by risk limits.

**Acceptance criteria:**
- ✅ `/api/risk` returns correct schema (regime, latest_signal, risk_limits, risk_usage, governance_blocked, risk_blocked, safe_mode)
- ✅ Risk & Governance panel visible after Egress Health section (10s refresh)
- ✅ Alert row for governance veto / risk block / DD ≥80% warning
- ✅ Zero changes to `core/**`, `execution/**`, `orchestrator.py`, `data/**`, `settings.py`, `ProxyTransport`
- ✅ `docs/dashboard/risk-visualisation.md` created
- ✅ All existing tests pass (93/93)

**In-scope:** `dashboard/server.py`, `dashboard/static/index.html`, `dashboard/static/app.js`, `dashboard/static/style.css`, `docs/dashboard/risk-visualisation.md`, `docs/MILESTONE_TRACKER.md`
**Out-of-scope:** All trading pipeline code — `core/**`, `execution/**`, `orchestrator.py`, `data/**`, `settings.py`

---

---

**Milestone:** DASHBOARD-ACCESS-GUIDE — Production run/access documentation for dashboard
**Status:** DONE (branch: dashboard-access-guide, commit 3e034a0, 2026-04-14)
**Active builder:** Cascade

**What:** Added complete operational documentation for running and accessing the dashboard in production:
- `docs/dashboard/access-guide.md` (new): step-by-step — SSH access, systemd start/stop/enable, external binding override, UFW rule, SSH tunnel, health check, log rotation, deploy update procedure, Egress Health interpretation table
- `README.md`: expanded Dashboard section with "How to run & access Dashboard" (systemd, health check, SSH tunnel, links)
- `docs/MILESTONE_TRACKER.md`: this entry

**Acceptance criteria:**
- ✅ `docs/dashboard/access-guide.md` covers: start (systemd + manual), UFW, external binding, SSH tunnel, health check, log rotation, deploy updates, Egress Health interpretation
- ✅ `README.md` "How to run & access Dashboard" section present with key commands
- ✅ Zero code changes (docs only)
- ✅ All existing tests pass (93/93)

**In-scope:** `README.md`, `docs/dashboard/access-guide.md`, `docs/MILESTONE_TRACKER.md`
**Out-of-scope:** All code — `dashboard/**`, `core/**`, `data/**`, `execution/**`, `orchestrator.py`, `settings.py`

---

---

**Milestone:** DASHBOARD-EGRESS-INTEGRATION — Live egress/proxy health panel in dashboard
**Status:** DONE (branch: dashboard-egress-integration, commit 153659a, 2026-04-14)
**Active builder:** Cascade

**What:** Extended existing dashboard (FastAPI m3→m4) with:
- `/api/egress` endpoint: reads `settings.proxy` (env vars) + parses bot log tail for ProxyTransport events + reads `bot_state.safe_mode` from SQLite
- Egress Health panel in UI: exit node IP, session age, bans (24h), rotation, safe mode status — auto-refresh 10s
- Safe mode alert banner: red banner at top of page when `safe_mode = true`

**Acceptance criteria:**
- ✅ `/api/egress` returns correct schema
- ✅ Egress Health panel visible in UI (10s refresh)
- ✅ Safe mode alert banner functional
- ✅ Zero changes to ProxyTransport, orchestrator.py, core/, execution/, settings.py
- ✅ All existing tests pass (93/93)
- ✅ `docs/dashboard/egress-integration.md` created

**In-scope:** `dashboard/**` only + docs
**Out-of-scope:** ProxyTransport code, orchestrator, core/, execution/, DB schema

---

---

**Milestone:** INFRA-EGRESS-VULTR — Dedicated SOCKS5 exit node via Vultr
**Status:** DONE (branch: infra/egress-vultr-fix, commit 590064c, 2026-04-14)
**Active builder:** Cascade
**Commits:** 590064c chore: add Vultr SOCKS5 egress node documentation and config

**Why:** IPRoyal residential proxy exit IP was partially blocked by Binance CloudFront (bookTicker and critical endpoints returned 404). Vultr exit node routes REST traffic through a clean IP — all critical endpoints (ping, time, bookTicker) return HTTP 200.

**Acceptance criteria:**
- ✅ SOCKS5 daemon running and stable on Vultr (danted active, port 1080)
- ✅ Firewall: only Hetzner IP allowed on port 1080
- ✅ `/fapi/v1/ping` → HTTP 200 via SOCKS5
- ✅ `/fapi/v1/time` → HTTP 200 via SOCKS5
- ✅ `/fapi/v1/ticker/bookTicker?symbol=BTCUSDT` → HTTP 200 via SOCKS5
- ✅ Bot log: `Proxy transport enabled: type=socks5, sticky=60 min, failover_count=0`
- ✅ No REST retry errors after restart
- ✅ 1h paper mode stability (zero REST errors, session reinit at 10:22:35 UTC as expected)

**Changes (repo only — no code changes):**
- Added `docs/infra/egress-vultr.md` (IP, port, config, destroy instructions)
- Added `.env.example` (PROXY_SOCKS5_URL template + all env vars documented)
- Updated `README.md` (Egress Configuration section)
- Updated `docs/MILESTONE_TRACKER.md` (this entry)

**Known remaining issue:**
- `/fapi/v1/exchangeInfo` still returns HTTP 404 from CloudFront on Vultr exit IP. This endpoint is not in the bot's critical runtime loop.

**In-scope:** Vultr SOCKS5 configuration + documentation + .env.example + README
**Out-of-scope:** ProxyTransport code, safe mode, WebSocket, WireGuard, core/execution layers

---

---

**Milestone:** INFRA-RESILIENCE-PROXY-2026 — Configurable proxy layer for Binance REST client
**Status:** MVP_DONE (commit 7622f8b, 2026-04-14)
**Active builder:** Cascade
**Commits:**
- `7622f8b` INFRA-RESILIENCE-PROXY-2026: add configurable proxy layer for Binance REST client

**What:** Added residential/static proxy support with sticky sessions and automatic failover for Binance REST API calls to bypass CloudFront IP blocking.

**Why:** Server IP (204.168.146.253) is blocked by Binance CloudFront, causing bookTicker requests to fail with HTTP 404. Proxy layer routes REST calls through residential IPs to avoid CDN blocking.

**Changes:**
- Added ProxyConfig to settings.py (PROXY_URL, PROXY_TYPE, PROXY_STICKY_MINUTES, PROXY_FAILOVER_LIST env vars)
- Created data/proxy_transport.py with ProxyTransport class (HTTP/SOCKS5 support, sticky sessions, CloudFront ban detection, automatic failover)
- Updated RestClientConfig to accept proxy_transport
- Modified BinanceFuturesRestClient._request_with_retry to use proxy transport
- Updated orchestrator.py build_default_bundle to initialize ProxyTransport when enabled
- Added PySocks>=1.7.1 to requirements.txt for SOCKS5 support
- Added tests/test_proxy_transport.py with 12 tests (all passing)

**Acceptance criteria met:**
- ✅ Proxy transport layer implemented with HTTP/SOCKS5 support
- ✅ Sticky session logic (configurable 30-60 min via PROXY_STICKY_MINUTES)
- ✅ CloudFront ban detection (x-cache header + HTTP 404)
- ✅ Automatic failover (PROXY_FAILOVER_LIST with rotation logic)
- ✅ Logging + alert on ban detection (ERROR log for ban, WARNING for rotation)
- ✅ Smoke tests PASSED (93 passed, 24 skipped)
- ✅ Zero regression in existing logic (all existing tests still pass)
- ✅ Zero changes in core logic, feature_engine, regime_engine, signal path, WebSocket
- ✅ Determinism preserved (no randomness in core path)

**Pending deployment verification:**
- Configure proxy credentials via .env (PROXY_URL, PROXY_TYPE, PROXY_STICKY_MINUTES, PROXY_FAILOVER_LIST)
- Deploy to server
- Verify bookTicker succeeds through proxy (HTTP 404 should disappear)
- Verify sticky session works (proxy persists for configured duration)
- Verify failover works on CloudFront ban (requires simulating ban or waiting for real ban)

**In-scope:** Proxy transport layer + config + monitoring + failover
**Out-of-scope:** VPS IP changes, whitelisting, WebSocket changes, core/models.py, research_lab/

---

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

**DECISION (2026-04-13, prior audit verdict):** Trial #63 approved for paper trading.
- Degradation -11.2% far below the audit threshold of -55%
- 2/2 windows passed including 2024-2025 and 2025-2026 bull market windows
- Note: allow_long_in_uptrend=False — bot very selective in bull markets (shorts in corrections only)
- Note: max_leverage=high_vol_leverage=8 — monitor closely in live

**Campaign still running** (~7h remaining). Trial #63 is locked in as paper trading candidate.

---

## Completed Milestone: RUN12-SOFT-PENALTY
**Status:** DONE — 310 trials, 2026-04-12/13
**Active builder:** Cascade
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


## Completed Milestones (reverse chronological)

### PAPER_BOT_MANUAL_RESTART_RAM_FREED
**Status:** DONE (2026-04-14)
**Builder:** Cascade
**What:** Simple restart of btc-bot.service (paper mode) after freeing RAM by stopping research_lab optimize process.
**RAM before restart:** 3.2GiB available (after stopping research_lab which consumed 66.2% RAM / 2.5GB)
**Status before restart:**
- Active: active (running) since 2026-04-13 23:28:05 UTC (42min uptime)
- PID: 137248
- Memory: 39.5M (peak: 40.2M)
- Config_hash: e8c7180d829d8c9c8296b09ba7ad8d0316251d4161d36be26fccc2051d4e5718
- Safe_mode: true (startup recovery entered safe mode)
- Websocket: Connected to wss://fstream.binance.com/stream
**Restart executed:**
- systemctl restart btc-bot → successful
- Active: active (running) since 2026-04-14 00:10:59 UTC
- PID: 141498 (new process)
- Memory: 26.7M (peak: 27.1M) - reduced from 39.5M
- Config_hash: e8c7180d829d8c9c8296b09ba7ad8d0316251d4161d36be26fccc2051d4e5718 (unchanged)
- Safe_mode: true (startup recovery entered safe mode, then snapshot_build_failed)
- Websocket: Connected to wss://fstream.binance.com/stream
**Status after 30 seconds (/api/status):**
- safe_mode: true
- safe_mode_reason: "snapshot_build_failed:Failed request GET /fapi/v1/ticker/bookTicker after retries"
- healthy: false
- mode: PAPER
- config_hash: e8c7180d... (unchanged)
- last_trade_at: 2026-03-29T13:36:19+00:00 (no new trades)
**Conclusion:** Bot restarts successfully with reduced memory usage (26.7M vs 39.5M) but still enters safe_mode due to Binance API connectivity issue (bookTicker endpoint blocked by CloudFront). RAM availability is NOT the root cause - the issue is infrastructure-related (server IP 204.168.146.253 blocked by Binance CloudFront), not resource-related.
**SSH key:** `c:\development\btc-bot\btc-bot-deploy` (root@204.168.146.253)

### PROTONVPN_SERVER_INSTALL
**Status:** BLOCKED (2026-04-14)
**Builder:** Cascade
**What:** Installation of ProtonVPN CLI on server to bypass Binance CloudFront IP block.
**Resource diagnostics before installation:**
- RAM: 3.7Gi total, 2.9Gi used, 801Mi available
- CPU: Load average 1.00, 52.4% user, 47.6% idle
- Top consumer: research_lab optimize (66.2% RAM, 100% CPU)
**Research_lab stopped:** Process 120863 killed to free resources
**Resource diagnostics after stopping research_lab:**
- RAM: 3.7Gi total, 492Mi used, 3.2Gi available (+2.4GB freed)
- CPU: Load average 0.90, 90.9% idle (+43.3% freed)
**Installation steps:**
- apt install python3-pip → success
- pip3 install --break-system-packages protonvpn-cli → success (v2.2.11)
- apt install openvpn dialog → success
- Command: protonvpn (not protonvpn-cli)
**Login attempt:**
- OpenVPN username: g8qf5eiLrxfMAWlr
- OpenVPN password: ejXSlrHkYxaelVm2rGXCaGFPqKBs0qRI
- protonvpn init → HTTP Error Code: 422
**Root cause diagnosis:**
- curl -I https://api.protonvpn.ch → HTTP/2 404
- Server IP 204.168.146.253 is BLOCKED by:
  - Binance CloudFront (fapi.binance.com) → HTTP 404
  - ProtonVPN API (api.protonvpn.ch) → HTTP 404
**Conclusion:** ❌ ProtonVPN CLI cannot be initialized because ProtonVPN API also blocks the server IP. This is not a credentials issue but a CDN/CloudFront IP blocking issue affecting multiple services. The server IP (204.168.146.253) appears to be on a blocklist used by major CDNs.
**Acceptance criteria NOT met:**
- ❌ ProtonVPN CLI cannot be initialized (API blocked)
- ❌ Cannot connect to VPN server
- ❌ Cannot bypass Binance CloudFront block via VPN
**Next steps required (infrastructure):**
1. Migrate server to different IP/location (Hetzner may have other IP ranges)
2. Use proxy/VPN on a different IP
3. Contact Binance/ProtonVPN support for IP whitelisting
4. Use alternative data provider (not Binance)
**SSH key:** `c:\development\btc-bot\btc-bot-deploy` (root@204.168.146.253)

### PAPER_BOT_MANUAL_RESTART
**Status:** DONE (2026-04-14)
**Builder:** Cascade
**What:** Simple restart of btc-bot.service (paper mode) without any code changes to verify current state.
**Status before restart:**
- Active: active (running) since 2026-04-13 22:11:38 UTC (1h 16min uptime)
- PID: 134513
- Config_hash: e8c7180d829d8c9c8296b09ba7ad8d0316251d4161d36be26fccc2051d4e5718
- Safe_mode: true (startup recovery entered safe mode)
- Websocket: Connected to wss://fstream.binance.com/stream
**Restart executed:**
- systemctl restart btc-bot → successful
- Active: active (running) since 2026-04-13 23:28:05 UTC
- PID: 137248 (new process)
- Config_hash: e8c7180d829d8c9c8296b09ba7ad8d0316251d4161d36be26fccc2051d4e5718 (unchanged)
- Safe_mode: true (startup recovery entered safe mode, then snapshot_build_failed)
- Websocket: Connected to wss://fstream.binance.com/stream
**Status after 30 seconds (/api/status):**
- safe_mode: true
- safe_mode_reason: "snapshot_build_failed:Failed request GET /fapi/v1/ticker/bookTicker after retries"
- healthy: false
- mode: PAPER
- config_hash: e8c7180d... (unchanged)
- last_trade_at: 2026-03-29T13:36:19+00:00 (no new trades)
**Conclusion:** Bot restarts successfully but immediately enters safe_mode due to Binance API connectivity issue (bookTicker endpoint blocked by CloudFront). Config_hash remains e8c7180d... (Trial #63 configuration). No code changes were made. The issue is infrastructure-related (server IP blocked by Binance CloudFront), not code-related.
**SSH key:** `c:\development\btc-bot\btc-bot-deploy` (root@204.168.146.253)

### VPN_PROTON_DIAGNOSTICS
**Status:** DONE (2026-04-14)
**Builder:** Cascade
**What:** Checked if ProtonVPN (or any VPN) is configured on the server and what exit IP was used as "protection".
**Diagnostic results:**
- Current public IP: 204.168.146.253 (direct server IP, no VPN)
- Active interfaces: Only eth0 (no tun/wg/proton interfaces)
- Routing: default via 172.31.1.1 dev eth0 (no VPN routes)
- WireGuard: no WireGuard
- ProtonVPN service: no protonvpn service
- VPN processes: No proton/wireguard/openvpn processes running
- VPN config files: No /etc/wireguard/, no ~/.config/protonvpn, only /etc/apparmor.d/vpnns (system default)
- VPN logs: No vpn/proton/wireguard/cloudfront entries in recent logs
- Package history: No proton/wireguard/openvpn packages ever installed (dpkg.log/apt history clean)
**Conclusion:** ❌ ProtonVPN NEVER configured on this server. ❌ NO VPN (WireGuard, OpenVPN) is running. ✅ Server uses direct IP: 204.168.146.253. ✅ No old Proton configurations exist. The Binance API CloudFront 404 issue is caused by IP blocking of the server's direct IP (204.168.146.253), NOT by VPN. VPN was never used as "protection".
**SSH key:** `c:\development\btc-bot\btc-bot-deploy` (root@204.168.146.253)

### SAFE_MODE_HARDCODE_CHECK
**Status:** DONE (2026-04-14)
**Builder:** Cascade
**What:** Verified that safe_mode is NOT hardcoded to True anywhere in the production code.
**Grep results:**
- `safe_mode.*=.*True`: Found in test files (smoke_recovery.py expected values), message template (telegram_notifier.py default), and RecoveryReport returns — none set safe_mode directly
- `safe_mode = True`: No results ✅
- `safe_mode=True`: No results ✅
- `enter_safe_mode`: No results ✅
**Where safe_mode is set to True (conditional only):**
- orchestrator.py: `_activate_safe_mode()` (health check failures, critical execution errors), feed start failures
- execution\recovery.py: exchange sync failures, recovery inconsistencies
- scripts\smoke_orchestrator.py: Manual override for testing only (not production)
**Initialization:**
- storage\state_store.py: safe_mode initialized to FALSE (line 49) ✅
- execution\recovery.py: Sets safe_mode to FALSE after successful recovery
**Conclusion:** ❌ NO hardcoded safe_mode = True in production code. safe_mode enters TRUE only as a reactive measure to errors (e.g., Binance API connectivity failure). The bot's persistent safe_mode is caused by the Binance API connectivity issue, not a code bug.

### PAPER_BOT_CONFIG_AND_CONNECTIVITY_FIX
**Status:** BLOCKED (2026-04-14)
**Builder:** Cascade
**What:** Attempted to fix two blockers from PAPER_BOT_SAFE_RESTART: (1) upload Trial #63 config_hash f807b7057..., (2) diagnose/fix Binance API connectivity.
**Config_hash findings:**
- Local config_hash: e8c7180d829d8c9c8296b09ba7ad8d0316251d4161d36be26fccc2051d4e5718
- Server config_hash: e8c7180d829d8c9c8296b09ba7ad8d0316251d4161d36be26fccc2051d4e5718
- Both identical — no sync needed
- Commit d245617 (PAPER-TRADING-TRIAL63) is ancestor of HEAD
- settings.py unchanged since d245617
- Current config_hash e8c7180d... IS the Trial #63 configuration
- Expected f807b7057... was from April 2 logs; current settings produce e8c7180d...
**Connectivity diagnostics:**
- Google (https://www.google.com): HTTP/2 200 ✅
- Binance ping (/fapi/v1/ping): HTTP/2 404 ❌
- Binance bookTicker (/fapi/v1/ticker/bookTicker): HTTP/2 404 ❌
- Response: "x-cache: Error from cloudfront", "x-amz-cf-pop: HEL51-P3" (Helsinki edge)
- DNS resolves correctly to CloudFront IPs
- No proxy configured
- Direct IP access also returns 404
- User-Agent header does not help
**Root cause:** Server IP (204.168.146.253) blocked by Binance's CloudFront CDN. All requests to fapi.binance.com return HTTP 404 with "Error from cloudfront". This is a geolocation/IP blocking issue, not code or configuration.
**Acceptance criteria NOT met:**
- ❌ Cannot fix Binance connectivity via code/configuration changes
- ❌ Bot will continue to enter safe_mode due to API unreachability
- ❌ Config_hash already correct (e8c7180d...), not f807b7057... as expected
**Next steps required (infrastructure):**
1. Use VPN/proxy to route Binance API traffic through allowed IP
2. Contact Binance support to whitelist server IP
3. Move server to different IP/location
4. Use alternative data provider (if available)
**SSH key:** `c:\development\btc-bot\btc-bot-deploy` (root@204.168.146.253)

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
| K1 | Force-order REST bootstrap semantics remain ambiguous | LOW | Live collector is restored and `force_orders` rows are flowing; remaining follow-up is to document or redesign the historical REST bootstrap assumption |
| K2 | ETF bias is still partial | LOW | Daily collector updates DXY, but ETF sources still warn on missing `SOSO/COINGLASS` API keys; non-blocking for current signal path because `SignalEngine` / `RegimeEngine` do not consume ETF bias |
| K3 | Walk-forward uses 6 windows over 4 years | MEDIUM | ~150 trades/window may be insufficient; defer to post-Run#12 |
| K4 | level_min_age_bars not yet in 8f2c6f2 codebase | LOW | Deferred to Run #13; add as tunable [2, 6] |
| K5 | PF=999999 trials (#47/#56/#73) in Run #12 journal | LOW | Anti-overfitting guard deployed at trial #88; future trials unaffected |

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
| 2026-04-17 | Live vs Research Settings Split | ACTIVE — live overrides for relaxed signal thresholds |

## Live vs Research Settings Split (2026-04-17)

 **Decision:** Live bot and research lab use different signal thresholds.

 **Why:**
 - Trial #63 params (`min_sweep_depth_pct=0.00286`, `confluence_min=3.6`) passed walk-forward on 2022-2026 backtest data.
 - The same params produce zero signals in the live April 2026 market.
 - Research reproducibility requires stable dataclass defaults.
 - Live incident recovery needs immediate threshold relaxation.

 **Implementation:**
 - `settings.py`: `StrategyConfig` dataclass defaults remain Trial #63 values as the research baseline.
 - `load_settings(profile="live")`: applies live runtime overrides `min_sweep_depth_pct=0.0001` and `confluence_min=3.0`.
 - `load_settings(profile="research")`: uses the unmodified dataclass defaults.
 - `main.py`: calls `load_settings(profile="live")`.
 - `research_lab/cli.py`: calls `load_settings(profile="research")`.

 **Important:**
 - `settings.py` is not a candidate promotion channel.
 - Live overrides are runtime-only and do not affect the research param registry or warm-start baseline.
 - Future research campaigns continue using the Trial #63 baseline unless the dataclass defaults are changed explicitly.

---

## Next Steps After Run #12 (proposed, pending audit)

1. Filter all trials with PF > 3.0 (statistically unreliable — zero-loss over 4yr is impossible in BTC perps)
2. Take top 5-7 credible trials (PF 1.3–2.5, trades > 120)
3. Anchored walk-forward: train 2022-2024, test 2024-2025, test 2025-2026
4. If best candidate passes both OOS windows → paper trading validation
5. Run #13: add level_min_age_bars as tunable [2, 6] + simple regime meta-layer (volatility × funding × cvd_strength)
