# AUDIT: BLUEPRINT_FOUNDATIONS_V1

Date: 2026-06-01
Auditor: Claude Code
Commit: `eed1db7` (last on `deploy/multi-asset-paper-v1`); audit branch: `claude/epic-darwin-z8Moa`
Type: Foundations audit — non-routine. Initiated after user question "moze blueprint jest słaby?" following 5 consecutive `HYPOTHESIS_INVALIDATED` verdicts (SMC sequence, MFE accessibility V1, OANDA EURUSD sweep, OANDA Asia range, OANDA NY reversal).

## Verdict: MVP_DONE (blueprint is structurally sound; five named risks are unresolved)

The blueprint is **not** structurally broken. `trial-00095` is empirically validated, the ETH transfer was successful, the SOL transfer failed correctly on a pre-declared gate, and the discipline that produced the recent `STOP` verdicts is the same discipline that previously surfaced the only validated edge. Killing the blueprint at this point would discard the only positive signal the project has produced.

However, the five `HYPOTHESIS_INVALIDATED` verdicts in succession are **not noise**. They expose unresolved foundational risks that have been carried since the 2026-05-08 promotion decision. Each subsequent search has effectively been an expensive way to rediscover the same underlying issues. Continuing to spawn new diagnostics without addressing them is the failure mode the user correctly senses.

This audit names the risks, classifies them by severity, and recommends one next step.

## Scope

In scope:
- The deployed edge identity (`optuna-default-v3-trial-00095`) and its validation chain
- The cost model and gate thresholds that drive every `STOP` verdict
- The search-space coverage that frames "edge discovery"
- The methodological pattern of post-trial-00095 milestones

Out of scope:
- Runtime engineering quality of the bot (separately audited and deployed)
- Multi-asset orchestrator / PAPER infrastructure (separately audited)
- Specific signal mechanics inside `trial-00095` parameters (not the failure mode)

## Source material reviewed

- `docs/walkforward/wf_trial_00095.json` (v1-run2 WF — failed, fragile)
- `docs/analysis/WF_VALIDATION_TRIAL_00095_2026-05-08.md` (v3 WF — passed)
- `docs/audits/AUDIT_WF_TRIAL_00095_2026-05-08.md` (promotion decision)
- `docs/audits/AUDIT_DEPLOYMENT_TRIAL_00095_2026-05-08.md` (deployment audit)
- `docs/audits/AUDIT_ETH_TRIAL_00095_TRANSFER_FEASIBILITY_2026-05-19.md` (ETH PASS)
- `docs/audits/AUDIT_SOL_TRIAL_00095_TRANSFER_FEASIBILITY_2026-05-20.md` (SOL PASS in portfolio context)
- `docs/audits/AUDIT_TRIAL_00095_ATTRIBUTION_V1_2026-05-30.md` (conditional structure)
- `research_lab/reports/oanda_*_v1.{md,json}` (4 OANDA diagnostics, all STOP)
- `research_lab/reports/trial_00095_conditional_edge_attribution_v1.md`
- `docs/research/REVERSE_QUANT_EDGE_REVIEW_2026-05-27.md`
- `docs/MILESTONE_TRACKER.md`
- `research_lab/diagnostics/trial_00095_conditional_edge_attribution_v1.py`

## What is established as real

These are not in question and should not be re-litigated:

1. **trial-00095 v3 passed walk-forward.** 2/2 windows, full-range ER 2.1294, PF 4.6625, 271 trades, WR 56.46%, MDD 6.51%, Sharpe 11.93. Protocol hash `023dc84...` is recorded. The earlier v1-run2 trial-00095 that failed WF (in `docs/walkforward/wf_trial_00095.json`) is a **different optimization run**, not the deployed candidate. Do not conflate them.
2. **ETH transfer empirically validated.** 544 trades (11.6× BTC frequency), ER 1.804, 4/4 positive walk-forward folds, all preregistered gates pass.
3. **SOL transfer failed cleanly on a pre-declared gate.** Standalone DD 15.46% > 12% threshold, concentrated in 2022 crash. Portfolio-context PASS. Builder verdict was correct; the gate did what it was supposed to do.
4. **Attribution V1 found genuine conditional structure.** LONG ER 2.377 (252 trades) vs SHORT ER -0.805 (22 trades). Uptrend regime ER 2.614 (205 trades, 75% of population) vs downtrend ER 0.690. TFI-aligned ER 2.391 vs TFI-opposed ER 0.816. 92.4% of losses reached ≥1R MFE before closing red.
5. **MFE accessibility V1 is a real finding.** 28 knowable states × 212,871 observations on BTCUSDT 15m: **not a single state produced positive median net return after 0.10% round-trip cost.** Best state (`reject_no_reclaim_known`): -0.0095% net, PF 0.879. This is a property of the *space*, not of any single hypothesis.

## Risk Findings

### Risk 1 (HIGH): OOS-outperforms-train flag was waived without re-test

| What was waived | Window 1 OOS ER 2.46 vs Train ER 1.71 (+43.72%); Window 2 OOS ER 3.00 vs Train ER 2.06 (+45.28%) |
|---|---|
| Why it matters | OOS systematically outperforming train by ~44% in *both* windows is statistically unusual. It is either (a) genuine regime-favorable selection (true robustness), or (b) a window-period artifact: validation periods 2024 and 2025 were structurally favorable to a long-biased uptrend strategy, which trial-00095 is. |
| Why it was waived | Window 1 had 106 OOS trades (acceptable). Architectural validation against confirmed gate vs premium pattern. |
| Why the waiver is fragile | Window 2 had **only 33 OOS trades** — Sharpe 12.21 on 33 trades is dominated by 2-5 tail winners. The validation periods (2024-01 → 2025-12) overlap with the regime in which `trial-00095` was already showing conditional dominance (uptrend, LONG-biased). Validating an uptrend-biased strategy in an uptrend period is not independent confirmation of robustness; it is in-regime confirmation. |
| What is unmeasured | The bot has been on PAPER since 2026-05-08 (BTC) and 2026-05-21 (multi-asset). That is 10-24 days of live-regime out-of-sample data, but no `AUDIT_PAPER_PERFORMANCE_*` exists in `docs/audits/`. The most decisive validation possible — does the deployed edge track the historical ER/PF? — has not been written down. |

**Classification:** Foundation risk, not a methodology bug. The promotion decision was defensible at the time. It is **untested in production**, and that test exists and has not been read.

### Risk 2 (HIGH): Post-trial-00095 searches were generic, not conditional

| Observation | trial-00095 attribution shows the edge is **LONG-biased (92% of trades), uptrend-concentrated (75% of trades), and TFI-alignment-dependent**. The remaining 8% SHORT trades have ER -0.805. The remaining 20% downtrend trades have ER 0.690. |
|---|---|
| Implication | The pre-existing edge already covers the LONG-uptrend cell of the strategy matrix at high ER. A generic post-hoc search ("find an edge on BTC 15m") competes for the *same* market state and cannot beat what is already deployed. The natural search direction is **conditional specialization**: find a SHORT specialist for downtrend regime, find a range/chop specialist for sideways regime, find an exit-timing improvement to reclaim the 92.4% losses with ≥1R MFE. |
| What was done instead | SMC sequence (re-searched the same long-bias structural space), MFE accessibility (audited general accessibility — useful but unconditional), OANDA sessions (transferred to a different asset class with degraded features). None targeted the *complement* of trial-00095. |
| Result | Each search rediscovered that the LONG-uptrend cell is already saturated. STOP verdicts are correct but uninformative. |

**Classification:** Methodology drift, not a blueprint defect. Trace: `QUANT_RESEARCH_OPERATING_MODEL.md` does not require "complement-of-deployed-edge" framing as a gate. It should.

### Risk 3 (MEDIUM-HIGH): The 0.10% cost model has never been re-audited against current venue economics

| What the model assumes | 0.10% round-trip on BTCUSDT futures. Applied as a flat median-net gate threshold across all diagnostics. |
|---|---|
| What current venues offer | Binance Futures: maker -0.005% (rebate) to 0.02% by VIP tier; taker 0.017% to 0.04%. Realistic round-trip for a mixed maker/taker strategy at VIP 1-3: 0.04-0.06%. At maker-only: can be net negative on rebates alone. |
| Impact | The median-net gate at 0.10% rejects strategies that would be profitable at 0.04%. The 4 OANDA diagnostics and the MFE accessibility study were all evaluated under this cost assumption. At 0.04%, several of the closed hypotheses would re-cross the median-net gate. |
| Why this is a foundation risk | Every future search inherits this gate. If the gate is calibrated to a pessimistic fantasy cost, the entire search space is artificially shrunk. |

**Classification:** Foundation risk. Cheap to resolve. High leverage.

### Risk 4 (MEDIUM): Closure language for failed hypotheses overstates scope

| Pattern | Audit reports use language like "OANDA Session Edge Research: CLOSED. OHLC-only OANDA without TFI/OI/funding has no tradable edge." |
|---|---|
| What was actually tested | 4 specific session hypotheses (EUR_USD sweep/reclaim, XAU_USD sweep/reclaim, ASIA_RANGE continuation, NY_REVERSAL reversion) on M15 timeframe, with the OANDA OHLC feed, under the 0.10% cost model and 5-bar primary horizon. |
| What "CLOSED" implies | The asset class / feed type is exhausted as an edge source. |
| What is logically supported | Those 4 hypotheses, on that timeframe, with those features, at that cost, with that horizon, fail. The asset class is not exhausted. |
| Why it matters | Premature closure removes search regions from the active hypothesis space and concentrates future search in the BTC-15m-sweep-reclaim corner that is already saturated by trial-00095. |

**Classification:** Documentation discipline issue. Audit language must distinguish "this hypothesis is invalidated" from "this region of the search space is exhausted".

### Risk 5 (MEDIUM): Search-space coverage is < 5% of the matrix

| Dimension | Covered | Not covered |
|---|---|---|
| Asset | BTC, ETH, SOL futures (Binance); EUR_USD, XAU_USD (OANDA) | Other crypto majors, altcoins, basis pairs (perp vs spot), funding-rate-paying assets |
| Timeframe | 15m primary; some 5m liquidation studies | 1m, 1h, 4h, daily (no systematic coverage) |
| Strategy class | Sweep/reclaim continuation, SMC sequence, session continuation/reversion | Mean reversion, market making, funding-rate harvesting, OI-divergence, basis arb, cross-exchange |
| Entry style | Market entry at `state_known_bar+1` | Limit at FVG creation, scaled entry, conditional limit ladder |
| Holding horizon | 5-bar primary | Sub-bar (intrabar exit on MFE trigger), multi-bar adaptive, position-flip |

**Classification:** Strategic scope risk. Not a defect — the project legitimately chose to deepen one corner before broadening. But after 5 consecutive STOPs in the same corner, the case for broadening is now stronger than the case for further depth.

## Core Audit Axes

| Axis | Status | Note |
|---|---|---|
| Layer Separation | PASS | Research lab is read-only against production DB; transfer diagnostics correctly avoid `core/`, `execution/`, `orchestrator/` |
| Contract Compliance | PASS | trial-00095 promotion artifacts, ETH/SOL transfer artifacts, attribution V1 all conform to expected I/O shapes |
| Determinism | PASS | Frozen parameters, recorded protocol hashes, recorded SHA256 on JSON outputs |
| State Integrity | PASS | No memory-only state in deployed edge; settings versioned |
| Error Handling | PASS | Pre-declared gates produce explicit STOP verdicts; no undefined states |
| Smoke Coverage | WARN | Historical backtest coverage is strong; **production PAPER performance is not documented in an audit artifact** (Risk 1) |
| Tech Debt | LOW | No `NotImplementedError` in the validated path; tracked debt is research-side and explicit |
| AGENTS.md Compliance | PASS | Commit discipline observed across the chain; auditor/builder separation clean |
| Methodology Integrity | WARN | Closure language overstates scope (Risk 4); waived OOS-outperforms-train flag not re-tested against PAPER (Risk 1) |
| Promotion Safety | WARN | Promotion was correct at the time but rests on a waived flag and a 33-trade OOS window. No PAPER performance re-audit gate exists in workflow. |
| Reproducibility & Lineage | PASS | trial_id, protocol_hash, dataset SHA256, window dates all recorded |
| Data Isolation | PASS | Read-only snapshots, no source mutation |
| Search Space Governance | FAIL | Coverage < 5% of feasible matrix; closure language premature; complement-of-deployed-edge search direction not formalized (Risks 2, 4, 5) |
| Artifact Consistency | PASS | Stored trials, WF reports, attribution, transfer reports tell a consistent story |
| Boundary Coupling | PASS | Research lab does not leak into live-path ownership |

## Critical Issues (must address before next research milestone)

1. **No production PAPER performance audit exists.** Risk 1 cannot be resolved by more backtest work. It can only be resolved by reading the deployed bot's actual fills and comparing realized ER / PF / WR / DD against the historical reference. This is the single most decisive piece of evidence available and it is unread.

## Warnings (fix soon)

2. Cost model `0.10%` round-trip is treated as a foundation constant and has not been re-audited against actual Binance fee schedule at current VIP tier. Re-evaluating closed hypotheses at realistic cost may resurrect 1-2 of them.
3. Audit closure language is too broad ("Session Edge Research: CLOSED"). Replace with hypothesis-scoped language ("EUR_USD M15 sweep/reclaim CLOSED"). Workflow change.
4. Post-trial-00095 search direction lacks a "complement-of-deployed-edge" framing. Attribution V1 already identified the gaps (SHORT, downtrend, exit timing). The research backlog should be reorganized around those gaps.

## Observations (non-blocking)

5. The 5 consecutive STOP verdicts are evidence of audit discipline working, not of blueprint failure. Without the median-based gates, several of these would have been falsely accepted on the basis of mean ER and slipped into deployment.
6. The reverse quant edge review (2026-05-27) reached a substantively similar verdict ("trial-00095 is the current benchmark, not a religion") and proposed a similar pivot. Two independent reviews converging on the same conclusion increases confidence.
7. `wf_trial_00095.json` in `docs/walkforward/` holds the **v1-run2** trial-00095 (failed), not the deployed v3 candidate. This is a documentation hazard. The file should be renamed or the v3 WF artifact should sit alongside it for clarity.

## Recommended Next Step

**Run `PAPER_PERFORMANCE_VALIDATION_V1` as the next milestone.**

This is a one-shot diagnostic, no production code, no Codex, no Cascade. Deliverables:

1. Query the production database directly (`ssh root@204.168.146.253 /home/btc-bot/btc-bot/storage/btc_bot.db` per `CLAUDE.md` runtime-data-source rules) for all trades executed since `2026-05-08T00:00:00Z` for BTC, and since `2026-05-21T21:00:00Z` for ETH and SOL.
2. Compute realized ER, PF, WR, MDD, average MFE consumed, LONG vs SHORT split, by asset.
3. Compare against historical reference per asset (BTC: ER 2.13, PF 4.66, WR 56.46%; ETH: ER 1.80, 4/4 folds; SOL: portfolio-only).
4. Apply pre-declared decision rule:
   - **If realized ER ≥ 50% of historical ER per asset and PF ≥ 1.5** → blueprint validated, proceed to complement-of-deployed-edge search per Risk 2.
   - **If realized ER < 50% of historical OR PF < 1.0** → blueprint has WF overfit problem. Trigger cost model audit (Risk 3) and pause new edge discovery until causes are identified.
   - **If trade count < 10 per asset** → inconclusive, extend observation window 14 days and re-run.

This single milestone resolves Risk 1 directly and informs every other risk. It is cheaper than another diagnostic, faster than another OANDA-class search, and it answers the question the user actually has: *is the deployed edge real in live conditions, or has the blueprint been protecting a backtest artifact?*

Until this question is answered, every further edge discovery milestone is searching with one eye closed. After it is answered, the research direction is determined by the answer.

## Decision

This audit does not approve a new edge discovery milestone. It approves a **production validation milestone** as the prerequisite for any further research direction.

The blueprint is sound enough to keep. It is not sound enough to keep building on top of without reading what production has been telling us for 24 days.
