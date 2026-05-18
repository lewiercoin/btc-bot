# BTC Bot Decisions Log

This file records operator decisions and their rationale. It is not a live status
document. Runtime facts live in the production database and should be checked with
`python scripts/db_status.py` on the production server.

## 2026-05-18 - Treat trial-00095 exit surface as diagnostic only
**Decision:** Run `TRIAL_00095_EXIT_SURFACE_DIAGNOSTIC_V1` as an offline distribution diagnostic, not as an exit optimization or promotion candidate.

**Reason:** Internal consultation flagged the small sample and intrabar-path limitations. The first safe step is to examine frozen trial-00095 realized-R outcomes for broad sensitivity, while preserving the entry population and leaving runtime untouched.

**Result:** The diagnostic found that capping realized losses near -1R would improve ER by approximately +10.6%, PF to 6.40, and max DD ratio to 0.68 on the replay artifact. Winner caps degraded expectancy sharply. This supports only a future validation hypothesis around tighter loss control; it does not approve a runtime exit change.

**Consequences:** Do not promote exit changes from this diagnostic. A future milestone would need full frozen-entry intrabar replay with adverse-first fills, exact entry/stop/TP reconstruction, cost stress, and audit.

**Related:** `research_lab/analysis_trial_00095_exit_surface_diagnostic.py`; `docs/analysis/TRIAL_00095_EXIT_SURFACE_DIAGNOSTIC_2026-05-18.md`.

## 2026-05-18 - Test trend pullback reaccept only as offline research
**Decision:** Approve `TREND_PULLBACK_REACCEPT_FEASIBILITY_V1` as a Research Lab-only feasibility milestone after external model consultation narrowed the broader Precision Flow Entry idea.

**Reason:** Claude, Perplexity, DeepSeek, and internal sub-agent consultation converged on the same conclusion: the naive Precision Flow Entry score stack was not falsifiable and repeated prior failed CVD/flow/crowded paths. The narrowed test had a concrete trigger: BTC LONG-only 15m reacceptance of a pre-frozen equal-low support level inside a completed 4h EMA uptrend.

**Consequences:** The milestone may write only Research Lab artifacts and reports. CVD, OI, funding, and force orders remain diagnostic-only. Runtime, `core/**`, `orchestrator.py`, `settings.py`, `execution/**`, and PAPER/LIVE behavior remain unchanged.

**Result:** Offline feasibility failed quality gates decisively despite high frequency. Best variant produced 1257 trades with ER -0.392, PF 0.59, max DD 500.57R, and 0/4 WF folds with ER > 1. Do not rescue by widening or retuning thresholds.

**Related:** `research_lab/hypotheses/active/trend_pullback_reaccept.json`; `docs/analysis/TREND_PULLBACK_REACCEPT_FEASIBILITY_2026-05-18.md`.

## 2026-04-09 — Preserve the restored signal-engine edge
**Decision:** Keep the restored signal architecture as the baseline edge and do not casually rewrite `core/signal_engine.py`.

**Reason:** `docs/MILESTONE_TRACKER.md` records that later signal rearchitecture broke the observed edge and that the system was restored to the `8f2c6f2` signal-era behavior with `min_hits=3`. The important architectural decision was to preserve the sweep/reclaim confluence model where direction comes from flow/regime context rather than from sweep side alone.

**Consequences:** Future strategy work must be research-only first. Changes to signal semantics require explicit evidence and audit, not threshold tuning or opportunistic edits.

**Related:** `docs/MILESTONE_TRACKER.md` SIGNAL-REVERT-V1 notes; `8f2c6f2` is referenced there as the restored signal-era baseline. The literal commit `8f2c6f2` in git is a later walk-forward snapshot cleanup commit, so this reference should be treated as historical project shorthand and rechecked before any code revert.

## 2026-04-13 — Trial #63 approved for paper, not permanently canonical
**Decision:** Trial #63 was approved for paper trading as a candidate at that time, but it is not a permanent source of truth for future optimization.

**Reason:** `docs/MILESTONE_TRACKER.md` records Trial #63 as approved for paper trading on 2026-04-13, with positive walk-forward results. Later data-integrity and market-truth work changed the data contract and exposed that old candidate results should not be conflated with current runtime profiles.

**Consequences:** Trial #63 remains useful for lineage and comparison, but fresh campaigns must explicitly state their data window and protocol. Exact Trial #63 replay must rebuild settings from stored candidate params rather than current `settings.py`.

**Related:** `docs/research_lab/TRIAL_63_FEASIBILITY.md`; trial id `run13-regime-aware-trial-00063`; commit `d245617` referenced as applying Trial #63 params.

## 2026-04-21 — DATA-INTEGRITY-V1 becomes prerequisite for new research
**Decision:** New modeling and optimization work must build on the post-DATA-INTEGRITY data contract.

**Reason:** DATA-INTEGRITY-V1 made decision-path data restart-safe, coverage-aware, and quality-explicit. The milestone added persistent OI/CVD state, feature-quality propagation, and operational visibility, which changed what counts as trustworthy data.

**Consequences:** Research results from before DATA-INTEGRITY are not automatically invalid, but they need revalidation before being used as decision evidence. Future Optuna campaigns must declare whether their source data is pre- or post-DATA-INTEGRITY.

**Related:** `docs/audits/AUDIT_DATA_INTEGRITY_V1_2026-04-21.md`; commit `7ebf2d2`; `docs/MILESTONE_TRACKER.md`.

## 2026-04-27 — Gate A validates Market Truth, not strategy edge
**Decision:** Treat Gate A as validation of the market-truth data layer only.

**Reason:** `AUDIT_GATE_A_VERDICT_2026-04-27.md` records Gate A PASS with 206 quality-ready buckets and complete lineage from market snapshots to feature snapshots to decision outcomes. The same report explicitly states that Gate A validates data infrastructure, not the trading strategy.

**Consequences:** Gate A unlocks further audits and modeling work, but it does not approve a strategy change, a live deployment, or a new parameter campaign by itself.

**Related:** `docs/audits/AUDIT_GATE_A_VERDICT_2026-04-27.md`; branch `market-truth-v3`; commit `e06a3dd` in the audit report.

## 2026-04-27 — MODELING-V1 remains neutral until validation evidence is decision-grade
**Decision:** Keep context filtering in neutral/validation mode until modeling validation produces decision-grade evidence.

**Reason:** `docs/MILESTONE_TRACKER.md` records that MODELING-V1 was implemented after Gate A, but active context blocking was not approved. The later validation checkpoint was partial because volatility telemetry had too much UNKNOWN leakage and the trade sample was too thin for activation.

**Consequences:** Context telemetry can be collected and analyzed, but it must not silently become a live gating layer without a separate activation verdict.

**Related:** `docs/analysis/MODELING_V1_VALIDATION_2026-04-27.md`; `docs/MILESTONE_TRACKER.md`; commit `2dc3112`.

## 2026-04-30 — Reject `min_stop_relief_only` as a promotion candidate
**Decision:** Do not promote `min_stop_relief_only` to paper/live configuration.

**Reason:** The geometry sensitivity Tier 1 runs showed that lowering `min_stop_distance_pct` improved raw expectancy and trade count, but worsened drawdown-normalized performance versus baseline in all tested windows. Slippage stress also showed fragility: at 3x slippage, one tested window collapsed to approximately flat expectancy with materially higher drawdown and longer loss streaks.

**Consequences:** `min_stop_relief_only` remains a research hypothesis only. Any future geometry change must include drawdown-normalized metrics, slippage stress, and audit before promotion.

**Related:** `research_lab/geometry_sensitivity.py`; local generated reports under ignored `research_lab/runs/`; operator/Codex/Claude audit discussion on 2026-04-30. [wymaga weryfikacji operatora]

## 2026-04-30 — NEW_BASELINE_DATE_OPTUNA remains open
**Decision:** Do not start Optuna until the replay data window and protocol are explicitly approved.

**Reason:** Production diagnostics found that the replay tables are not gap-free from 2022-03-09 to 2026-04-17. `aggtrade_15m` has gaps, including a large gap from 2026-03-28 to 2026-04-17, and `open_interest` has a large gap from 2025-06-05 to 2026-01-01 plus later April gaps. The current clean candidate window is `2026-01-01T00:15:00+00:00` to `2026-03-28T21:00:00+00:00`, but that is too short for the default 730/365/365 protocol.

**Consequences:** Optuna must either wait for backfilled/longer data, use an explicitly labeled light protocol, or be deferred until more clean data accumulates. The default protocol must not be applied blindly to an 87-day window.

**Related:** `scripts/db_status.py`; `research_lab/configs/default_protocol.json`; 2026-04-30 production DB diagnostics. [wymaga weryfikacji operatora]

## 2026-04-30 — Runtime state lives in `db_status.py`, decisions live in this log
**Decision:** Do not manually maintain a status document as the source of runtime truth.

**Reason:** Documentation state drifts quickly. Recent diagnostics showed this directly: remembered branch/status context differed from the production server. Runtime facts should be queried from the production database on demand, while documents should preserve stable decisions and rationale.

**Consequences:** Operators and agents should run `python scripts/db_status.py` on production for current facts. This log records why decisions were made, not whether the bot is currently healthy, which branch is deployed, or how many rows are in the database today.

**Related:** `scripts/db_status.py`; `docs/DATA_SOURCES.md`; DOCS-FOUNDATION-V1. [wymaga weryfikacji operatora]

## 2026-05-12 - Keep sweep-reclaim baseline and move to multi-setup research
**Decision:** Keep `optuna-default-v3-trial-00095` as the active PAPER sweep-reclaim baseline. Do not promote any candidate from the constrained grid. Start the next work as research-only `TREND-CONTINUATION-RESEARCH-V1`, with no production behavior change.

**Reason:** The constrained grid around trial-00095 tested 60 combinations and increased trade frequency in several candidates, but every meaningful frequency improvement degraded ER/PF and triggered blocking safety concerns, especially `pnl_sanity_review_required`. This confirms that sweep-reclaim is a bounded liquidity-reclaim / mean-reversion setup, not a clean-trend continuation setup.

**Consequences:** Future work should not try to force sweep-reclaim to trade every market structure. The bot should evolve toward a portfolio of independent, context-specific setups. Each setup must prove edge independently through explicit market-structure hypothesis, deterministic logic, `reasons[]`, standalone backtest, walk-forward validation, safety gates, and audit before it can be integrated through a deterministic multi-setup arbiter.

**Related:** `docs/audits/AUDIT_GRID_SEARCH_TRIAL00095_2026-05-12.md`; `docs/analysis/POST_GRID_PORTFOLIO_PLAN_2026-05-12.md`; `docs/ROADMAP_MULTI_SETUP_ARCHITECTURE.md`; `docs/MILESTONE_TRACKER.md` Multi-Setup Portfolio Architecture section.

## 2026-05-13 - Close 15m multi-setup portfolio research, pivot to sweep-reclaim family expansion
**Decision:** Close 15m multi-setup portfolio research as conclusively NOT VIABLE. Pivot to sweep-reclaim family expansion (structure context variations). No new independent setup families will be tested at 15m without separate architectural decision. Defer 5m/1m frequency upgrade for future evaluation.

**Context:** Six-day research cycle tested 6 independent setup families: absorption_continuation (25 trades, ER -0.48), compression_breakout (3 trades, ER -0.30), crowded_unwind (71 trades, ER -0.35), post_cascade_momentum (0 trades, blocked by infrastructure), volatility_breakout (63 trades, ER 0.52), regime_reversal (11 trades, ER 0.11). Success rate: 0/6 (0%). No candidates reached ER > 1.5 gate (volatility_breakout came closest at ER 0.52, still below 1.0 hard stop).

**Reason:** Three-layer timing incompatibility pattern proven across all 6 families:
1. **Event timescale incompatibility** (crowded_unwind, post_cascade_momentum): Profitable events occur on seconds-to-minutes scale, too fast for 15m decision cycles
2. **Detection latency within states** (volatility_breakout): State classification correct but 15m enters mid-phase, missing early high-profit phase
3. **Edge absence** (absorption_continuation, compression_breakout, regime_reversal): Even with correct timing/state detection, no tradeable edge exists

Only sweep_reclaim works at 15m because: state-independent logic (no regime phase timing needed), mean-reversion edge (not momentum-following), edge persists 15-60 min (compatible with 15m latency), objective measurable signals (sweep/reclaim detection).

**Consequences:**
- Proven edge expansion (sweep_reclaim family, ER 2.1 baseline) prioritized over new unknown edges (0% success rate in 6 families)
- Family expansion validates structure context variations: range specialist, trend specialist, post-liquidation specialist, volume specialist
- Each variant must prove independence (overlap < 30%), meet validation gates (ER > 1.5, WF 2/2), and preserve institutional character
- First variant: Range Sweep Specialist (liquidity sweeps in normal regime, horizontal structure, highest mean-reversion probability hypothesis)
- Exit criteria: After 3 variants, if 0-1 succeed OR overlap > 50% → pivot to 5m frequency assessment
- After 6 months: If trial-00095 live ER < 1.0 → edge degrading, strategic reassessment
- No new setup families rule: No independent setup families tested at 15m without explicit architectural decision

**Alternatives considered and rejected:**
- Continue testing more 15m setups: 0% success rate after 6 families proves 15m timing incompatibility, not sampling issue
- Immediate 5m upgrade: High infrastructure cost (rebuild decision engine, data pipeline, state management, replay tooling) with uncertain benefit (may hit new timing constraints). Exhaust 15m proven edge first.
- Hybrid approach (mixing family expansion + new families): Violates scope discipline, dilutes focus, complicates audit trail

**Related:** `docs/analysis/STRATEGIC_15M_PORTFOLIO_ASSESSMENT_2026-05-13.md` (comprehensive analysis); 6 research branches (absorption, compression, crowded_unwind, post_cascade, volatility, regime_reversal); 6 audit reports; `docs/MILESTONE_TRACKER.md` updated; next milestone `SWEEP-RECLAIM-FAMILY-EXPANSION-V1`.

## 2026-05-13 — Context expansion NOT viable, accept singular sweep_reclaim edge
**Decision:** Close SWEEP-RECLAIM-FAMILY-EXPANSION-V1 (verdict: NOT_VIABLE, 4/4 failures). Accept trial-00095 as the singular sweep_reclaim edge at 15m. Transition to live validation phase. Defer 5m frequency upgrade and parameter-based variants.

**Context:** One-day research cycle tested 4 context expansion variants across 340 trades:
- V1 Range Sweep (normal regime, LONG): 16 trades, ER 0.02 — zero edge
- V2 Trend Sweep (downtrend LONG + uptrend SHORT): 159 trades, ER 0.63 — below threshold
- V3 Special Regime (crowded_leverage, LONG): 34 trades, ER 0.30 — below threshold
- V4 Session Sweep (Asia 00:00-08:00 UTC, LONG): 126 trades, ER 0.78 — best variant, still < 1.0
- Best single micro-context: Asia + Uptrend LONG (90 trades, ER 0.89, PF 2.85) — still < 1.0

**Reason:** Four independent mechanisms tested (3 regime-based + 1 microstructure-based). All failed ER 1.0 hard stop. Evidence conclusive:
1. **Context filtering cannot create edge.** It can only subset trial-00095's trade set, degrading ER vs the full parameter-optimized set.
2. **sweep_reclaim edge is parameter-dependent, not context-dependent.** ER 2.1 comes from Optuna-tuned confluence/TFI/risk thresholds across ALL regimes and ALL sessions.
3. **SHORT universally destructive.** Normal SHORT ER -0.92, Uptrend SHORT ER 0.09. LONG-only bias is fundamental, not tunable.
4. **No further 15m context variants justified.** 10 hypotheses tested (6 setup families + 4 context variants), 0% success rate.

**Consequences:**
- trial-00095 IS the edge — no further context specialization attempts
- Live validation focus: collect 30-50 paper trades over 6-10 months
- Decision points: After 30 trades (preliminary ER check), after 50 trades (final validation)
- If live ER > 1.5 after 50 trades → promote to LIVE (with restored kill-switch limits)
- If live ER < 1.0 after 30 trades → reassess edge viability
- 5m frequency upgrade deferred until live ER stability confirmed (estimated 6-8 weeks cost if undertaken)
- No new research milestones until live validation produces decision-grade evidence

**Alternatives considered and rejected:**
- More 15m context variants: 0/10 success rate proves this is not a sampling problem
- Immediate 5m upgrade: High cost (6-8 weeks), uncertain benefit, premature without live validation
- Parameter-based variants (re-optimize with context constraints): Context filtering degrades ER; Optuna already found global optimum
- New edge families at 15m: 0/6 success rate in portfolio research; timing incompatibility proven

**Related:** `research/sweep-family-expansion-v1` branch (commits efd9ef3..61a8aaa); `docs/MILESTONE_TRACKER.md`; `docs/analysis/SWEEP_RECLAIM_SINGULAR_EDGE_ASSESSMENT_2026-05-13.md`; 4 audit packages in `research_lab/reports/` and `docs/audits/`.

## 2026-05-14 - Reject standalone 5m sweep/reclaim runtime migration
**Decision:** Close `BTC_5M_SWEEP_RECLAIM_FEASIBILITY_V1` as `5M_FREQUENCY_FAIL_QUALITY_PASS`. Do not migrate the live decision runtime from 15m to standalone 5m sweep/reclaim based on this evidence.

**Reason:** The standalone 5m harness improved quality metrics versus its matched 15m comparison (ER 2.351 vs 2.110, PF 6.63 vs 3.95, WR 72.1% vs 51.1%, MAE improved by roughly 40%), but it only increased trade count by 1.30x against a required >=2x gate. The structural bottleneck is reclaim detection: 5m bars detect more raw sweeps but are less likely to sweep and reclaim inside a single bar.

**Consequences:**
- Full 5m runtime migration remains unjustified.
- 5m may be studied only as an offline timing/quality layer until separately validated.
- Results are not directly comparable to official BacktestRunner metrics because the study used a standalone harness with simplified fills.

**Related:** `docs/analysis/BTC_5M_SWEEP_RECLAIM_FEASIBILITY_2026-05-14.md`; `docs/MILESTONE_TRACKER.md`.

## 2026-05-15 - Reject 15m signal plus 5m energy confirmation overlay
**Decision:** Close `15M_SIGNAL_5M_ENERGY_OVERLAY_FEASIBILITY` as `HYBRID_FAIL`.

**Reason:** Waiting for a 5m high-energy candle after a 15m signal produced timeout rates of 78-91%. SKIP mode left too few trades for decision-grade evidence, while FALLBACK mode preserved count but degraded ER from the 15m baseline and did not improve MAE. The evidence indicates 5m energy confirms the move too late rather than improving the entry.

**Consequences:**
- Do not add 5m energy confirmation to the 15m execution path.
- The standalone 5m quality improvement should not be interpreted as proof that post-signal 5m confirmation improves 15m entries.

**Related:** `docs/analysis/15M_SIGNAL_5M_ENERGY_OVERLAY_2026-05-15.md`; `docs/MILESTONE_TRACKER.md`.

## 2026-05-15 - Mark 5m multi-candle event setups ready for audit, not rescue
**Decision:** `BTC_5M_MULTI_CANDLE_EVENT_SETUP_FEASIBILITY_V1` is `READY_FOR_AUDIT` with builder verdict `MULTI_CANDLE_FAIL`. Do not rescue failed variants by expanding the grid unless Claude Code identifies a methodology issue.

**Reason:** Both tested setup families increased event counts but failed required quality gates. Compression fakeout reclaim best variant produced 73 trades but negative ER and weak PF. Crowded unwind reversal produced 174 trades but also negative ER, weak PF, and severe drawdown.

**Consequences:**
- Claude Code audit is required before scheduling follow-up research.
- The result does not approve any production, PAPER, settings, core, execution, or orchestrator change.
- The failure supports the current stance that 5m geometry alone does not solve the BTC frequency problem without quality degradation.

**Related:** `docs/analysis/BTC_5M_MULTI_CANDLE_EVENT_SETUP_FEASIBILITY_2026-05-15.md`; `docs/MILESTONE_TRACKER.md`.

## 2026-05-15 - Add research automation foundation as audit-pending infrastructure
**Decision:** `RESEARCH_AUTOMATION_FOUNDATION_LITE_V1` is `READY_FOR_AUDIT`. Treat it as research-lab-only infrastructure, not an autonomous research agent and not a production integration.

**Reason:** The milestone standardizes hypothesis specs, experiment registry records, data manifest hashes, deterministic gate evaluation, and markdown reporting after several manual research scripts. It intentionally avoids LLM-generated code execution, automatic experiment execution, external repositories, and runtime coupling.

**Consequences:**
- Claude Code audit must pass before relying on the framework as the standard research workflow.
- `research_lab/autoresearch_loop.py` remains separate and unchanged.
- Hypothesis specs must remain declarative data and must not become a code execution channel.

**Related:** `docs/analysis/RESEARCH_AUTOMATION_FOUNDATION_LITE_2026-05-15.md`; `docs/MILESTONE_TRACKER.md`.

## 2026-05-17 - Add runtime single-instance guard after duplicate PAPER bot incident
**Decision:** Implement `M4-RUNTIME-SINGLE-INSTANCE-GUARD` immediately as operational hardening. The guard prevents a second `main.py --mode PAPER` or `main.py --mode LIVE` runtime from starting, regardless of whether it is launched by systemd or manually with `nohup`.

**Reason:** A second manual PAPER runtime ran from 2026-05-14 to 2026-05-17 alongside the managed systemd bot, creating duplicate `decision_outcomes` rows and a second active config hash. This was the second duplicate-runtime incident in recent history. A systemd PIDFile alone would not prevent manual launches; an application-level file lock protects all launch paths.

**Consequences:**
- The guard applies only to `main.py` runtime startup.
- One-shot scripts, diagnostics, dashboard, collectors, and research harnesses remain unaffected.
- Lock path defaults to `/tmp/btc-bot-runtime.lock` and can be overridden with `BTC_BOT_RUNTIME_LOCK_PATH`.
- Claude Code audit is required before deploying this guard to PAPER production.

**Related:** `docs/operations/RUNTIME_INSTANCE_CONTROL.md`; `docs/MILESTONE_TRACKER.md`; M4 deploy verification on 2026-05-17.

## 2026-05-16 - Close 5m multi-candle research path after three failures
**Decision:** Close `BTC_5M_MULTI_CANDLE_EVENT_SETUP_FEASIBILITY_V1` as `MULTI_CANDLE_FAIL` (audit verdict: ACCEPT). Implementation correct, hypothesis decisively falsified. 5m research path exhausted after three major attempts.

**Reason:** Audit confirmed methodology integrity (no-lookahead discipline, one-position constraint, proper force-orders data integration) and verified that both tested setup families produced catastrophically negative results:
- Compression Fakeout Reclaim (CFR_V3): 73 trades, ER -0.192, PF 0.371, DD 14.0R (3.1x baseline)
- Crowded Unwind Reversal (CUR_V1): 174 trades, ER -0.415, PF 0.224, DD 72.4R (16.1x baseline)

Both setups achieved frequency goals (1.55x, 3.70x vs baseline) but failed 4 of 6 required quality gates. Direction split shows both LONG and SHORT negative (not a direction bias issue). Force-orders correction was material (integrated 146,864 historical force-order rows from 2022-2024) but did not create edge.

Combined 5m research evidence:
1. **M5 (BTC_5M_SWEEP_RECLAIM_FEASIBILITY):** Frequency fail (1.30x < 2.0x gate) — sweep/reclaim detection less efficient at 5m
2. **M6 (15M_SIGNAL_5M_ENERGY_OVERLAY):** Quality fail (ER degrades, 78-91% timeout) — 5m confirmation too late
3. **M7 (BTC_5M_MULTI_CANDLE_EVENT_SETUP):** Quality catastrophic fail (negative ER, DD 3-16x baseline) — multi-candle patterns have no edge

Conclusion: **5m resolution does not solve BTC frequency problem.** Multi-candle event windows increased detection frequency but destroyed edge quality.

**Consequences:**
- Do not attempt to rescue 5m multi-candle setups by expanding parameter grid
- Three research paths now exhausted: threshold optimization (degrades quality), 5m resolution (all variants failed), context expansion (0% success rate)
- Wait for M4 near-miss monitoring checkpoint (2026-06-13, 29 days), then decide strategic direction:
  - **Option A:** Continue monitoring if M4 reveals actionable sweep-depth regime shift
  - **Option B:** ETH multi-asset feasibility study (test if low-frequency issue is BTC-specific)
  - **Option C:** Accept current frequency, focus on live validation of trial-00095

**Related:** `docs/audits/AUDIT_BTC_5M_MULTI_CANDLE_EVENT_SETUP_FEASIBILITY_2026-05-16.md`; `docs/analysis/BTC_5M_MULTI_CANDLE_EVENT_SETUP_FEASIBILITY_2026-05-15.md`; `docs/MILESTONE_TRACKER.md`; commit 2e0679b (implementation), commit 74ef7a8 (audit closure).

## 2026-05-16 - Approve research automation foundation framework for production use
**Decision:** Approve `RESEARCH_AUTOMATION_FOUNDATION_LITE_V1` for production use in research context (audit verdict: DONE). Framework is production-grade research infrastructure.

**Reason:** Audit verified all safety boundaries, comprehensive test coverage (15/15 passed), and complete implementation:
- **Zero production coupling:** No imports from core/, execution/, data/, orchestrator, settings. Framework is self-contained.
- **Append-only registry:** No delete API (verified by test). Experiment records are permanent audit trail.
- **Safe hypothesis specs:** Recursive validation rejects executable field names (python_code, code, module_path, function_name, import, eval, exec, shell_command). No code execution channel from JSON specs.
- **Deterministic gate evaluator:** Pure function, no randomness, verdict logic (BLOCKED > INCONCLUSIVE > FAIL > MARGINAL > PASS) is explicit and testable.
- **Reproducibility:** Experiment fingerprints, data manifest hashes, combined manifest hashing for multi-dataset experiments, full lineage capture (hypothesis_id, config_hash, data_manifest_hash, git_commit, runner_name, date_range, baseline_reference).
- **Standard report contract:** All required sections generated, test validates presence.

Framework standardizes the repeatable workflow: `hypothesis -> experiment -> evaluation -> report`. Designed for Karpathy-style loop patterns without vendoring external code, adding LLM agents, or touching production runtime.

**Consequences:**
- Use framework for all future offline research programs (ETH feasibility, exit studies, diagnostic analyses)
- Hypothesis specs must be authored by builder, reviewed by Claude Code before experiment execution
- Experiment registry is single source of truth for offline research results
- Standard report generator replaces manual report formatting
- Gate evaluator provides deterministic pass/fail evaluation (no subjective judgment)
- Framework is complementary to existing Optuna integration (autoresearch_loop.py remains unchanged)
- Framework does NOT execute backtests (by design) — backtest execution is separate concern

**Usage scope:**
- **In scope:** Offline research programs, hypothesis tracking, experiment registry, gate evaluation, report generation
- **Out of scope:** Production runtime changes, PAPER deployment, automatic experiment execution, LLM code generation, parameter optimization (use Optuna for that)
- **Not a promotion channel:** Framework stores results, does not auto-promote to production. Separate approval workflow required for live deployment.

**Related:** `docs/audits/AUDIT_RESEARCH_AUTOMATION_FOUNDATION_LITE_2026-05-16.md`; `docs/analysis/RESEARCH_AUTOMATION_FOUNDATION_LITE_2026-05-15.md`; `docs/MILESTONE_TRACKER.md`; commit 35d78f2 (implementation), commit cbe4ad2 (audit closure).

## 2026-05-17 - M4 near-miss payload contract fix deployed, rogue process incident resolved
**Decision:** Deploy M4 near-miss payload contract fix (commit 33a0df1) to PAPER production. Do not quarantine the 305 duplicate decision_outcomes created by rogue process during May 14-17 overlap period.

**Reason:** Production database showed `sweep_depth_pct` only at top-level `details_json`, not inside nested `near_miss_diagnostics`. This conflicted with documented M4 query contract and required backward-compatible fix.

During deploy verification, Codex discovered a second bot instance running via manual `nohup` launch (started 2026-05-14 15:15 UTC). This created 305 duplicate decision_outcomes with different config_hash across ~3 days overlap.

**Payload fix details:**
- Added nested `sweep_depth_pct` to `near_miss_diagnostics` payload in orchestrator.py
- Report parser made backward-compatible (fallback to top-level if nested missing)
- Nested payload only added for near-misses (depth >= 0.004), not all sweep_too_shallow rejections (by design)
- Tests verify both old and new payload shapes work (24/24 passed)

**Rogue process incident:**
- **Scope:** 2026-05-14 15:15 to 2026-05-17 19:15 UTC (~3 days 4 hours)
- **Impact:** 305 rogue records, only 4 exact timestamp duplicates (LOW severity)
- **Root cause:** Manual `nohup .venv/bin/python main.py --mode PAPER` launched alongside systemd bot
- **Detection:** Codex noticed two active config_hash values during deploy verification
- **Resolution:** Rogue process killed, only systemd bot (PID 790301) remains
- **Data integrity:** No execution conflicts (PAPER mode), both bots used same M4 parameters, most timestamps unique due to microsecond drift

**Comparison to April 24-27 dual-runtime incident:**
- April incident: 344 exact duplicates over 3.5 days
- May incident: 305 total rogue records, only 4 exact duplicates
- May incident less severe due to timing drift between processes

**Consequences:**
- M4 monitoring continues unchanged (no parameter changes)
- Near-miss counts in May 14-17 period slightly inflated but usable
- M4 checkpoint analysis should filter by `config_hash = 'afbd2eb...'` or use data after 2026-05-17 19:15 UTC for clean sample
- No database cleanup required (diagnostics-only data, PAPER mode, historical record of incident useful)
- **Hardening needed:** Single-instance runtime guard to prevent future manual bot launches

**Next operational fix:** Implement file-lock-based single-instance guard in main.py to prevent both manual nohup launches and systemd race conditions. This should be separate hardening milestone, not mixed with research work.

**Related:** `docs/audits/AUDIT_M4_NEAR_MISS_PAYLOAD_FIX_2026-05-16.md`; `docs/diagnostics/M4_NEAR_MISS_MONITORING_CHECKPOINT_2026-05-16.md`; commit 33a0df1 (implementation), commit d4ab073 (audit); incident detected and resolved by Codex on 2026-05-17.
