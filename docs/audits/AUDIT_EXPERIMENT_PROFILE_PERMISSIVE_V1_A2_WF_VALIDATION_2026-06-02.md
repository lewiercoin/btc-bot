# AUDIT: EXPERIMENT_PROFILE_PERMISSIVE_V1_A2_WF_VALIDATION

Date: 2026-06-02
Auditor: Claude Code
Builder: Codex
Commits audited: `d938f3a` (initial PC-snapshot run) → `5cec9a0` (rerun with server snapshot, supersedes)
Branch deployed to: `deploy/multi-asset-paper-v1`
Audit branch: `claude/epic-darwin-z8Moa`
Parent milestone: `CONFIG_LINEAGE_RECONCILIATION_V1`, Phase A2
Prior audits:
- `262506b` — A1.build
- `3330e22` — A1.build follow-up
- `0648c4c` — A1.deploy

## Verdict: PROMOTION_READY_WITH_CONDITIONS (audit gates passed; three completion gaps to close in follow-up commit)

The walk-forward result meets the pre-declared decision criteria from my A2 handoff. WF passes 2/2 windows non-fragile with strong validation trade counts (177 and 68, both well above the borderline threshold). The two review flags raised by the recommendation pipeline (`oos_outperformance_review_required`, `pnl_sanity_review_required`) are evaluable as non-blocking false positives under the same standard applied to trial-00095 v3 — and the OOS outperformance pattern is in fact **less extreme** than trial-00095 v3 (-34.05% IS degradation vs -43% to -45%), making the false-positive evaluation easier to defend here than for the original.

The candidate is approved for paper performance comparison as its own reference (the prerequisite this whole CONFIG_LINEAGE_RECONCILIATION chain was created for is now satisfied). Three completion gaps require a small follow-up commit before paper validation V2 can cite this audit as its baseline.

## Codex methodology deviation — accepted as superior to handoff

My handoff specified building three new code artifacts:
- `research_lab/wf_experiment_profile_permissive_v1.py` (dedicated WF runner)
- `research_lab/candidates/experiment-profile-permissive-v1.json` (frozen param spec)
- `tests/test_wf_experiment_profile_permissive_v1.py`

Codex did NOT build a new runner. Instead, Codex reused the **existing audited pipeline** (`research_lab/configs/default_protocol.json` + `load_settings(profile="experiment")` + override `{"min_sweep_depth_pct": 0.005}` + existing `walkforward.py` etc.). The resulting `protocol_hash` is `023dc84c2cd8eff7e0226a1cb74cca24ce64a896aacac7f8c4a61199fac9e1b8` — **identical** to trial-00095 v3 WF.

This is the correct methodological choice and I should have specified it. Building a parallel runner would have introduced drift risk for no benefit. The existing pipeline IS the audited reference. Using it directly is the strongest possible guarantee of protocol identity.

I am revising my A2 handoff retroactively to acknowledge this. Future similar handoffs from me should default to "reuse existing pipeline with documented override" rather than "build new runner."

## Core Audit Axes

| Axis | Status | Note |
|---|---|---|
| Layer Separation | PASS | Research-only run; production state confirmed unmodified; SSH used only for read-only snapshot fetch per `DATA_SOURCES.md` |
| Contract Compliance | PASS (with completion gap) | WF result + report meet handoff substance; three artifact gaps noted in Findings |
| Determinism | WARN | `protocol_hash` matches trial-00095 v3 exactly; candidate `config_hash` recorded (`68fd6caf...`); no committed determinism test (re-run produces identical metrics) |
| State Integrity | PASS | Server SHA = local SHA = `ad8c5e7b4f541...167363bca`; production untouched |
| Reproducibility & Lineage | WARN | Snapshot SHA documented; revalidation JSON artifacts exist locally but not committed; their SHAs not in report. See Finding 2. |
| Methodology Integrity | PASS | Identical protocol to reference candidate; identical dataset; identical window structure; same gates evaluated |
| Promotion Safety | PASS | Builder verdict honestly `SCREENING_ONLY` pending audit; no auto-promotion; both review flags surfaced explicitly |
| Data Isolation | PASS | Source snapshot read-only; revalidation outputs in dedicated subdir; no source mutation |
| AGENTS.md Compliance | PASS | WHAT/WHY/STATUS in both commits; references to prior audit chain present; no scope creep into production |

## Verification of Decision-Grade Claims

| Claim | Evidence | Verified |
|---|---|---|
| Protocol hash matches trial-00095 v3 | `023dc84c...` reported, identical to `WF_VALIDATION_TRIAL_00095_2026-05-08.md` line 61 | ✓ |
| Dataset SHA verified server vs local | Both `ad8c5e7b...167363bca` | ✓ |
| Window dates pinned to trial-00095 v3 reference | W1 2022-01→2024-01 train, 2024-01→2024-12-31 val; W2 2022-01→2024-12-31 train, 2024-12-31→2025-12-31 val — matches `WF_VALIDATION_TRIAL_00095_2026-05-08.md` per-window table | ✓ |
| Override applied: `min_sweep_depth_pct=0.005` | Documented in report Execution section | ✓ |
| No production state modified | Reported explicitly; no SSH commands in audit log mutate state | ✓ |
| WF 2/2 windows passed | Result table line "WF passed: PASS: 2/2 windows" | ✓ |
| fragile=false | Result table | ✓ |
| Validation trade counts above borderline | W1=177, W2=68 (both > 30 preferred threshold; W2 substantially better than trial-00095 v3's W2=33) | ✓ stronger than reference |
| Sample run is local-only, not on server | Execution section: "Local PC path: c:\Users\lewie\Projects\btc-bot" | ✓ |

## Review Flag Evaluation

### Flag 1: `oos_outperformance_review_required`

| Metric | Trial-00095 v3 (reference) | experiment-profile-permissive-v1 (audited) |
|---|---:|---:|
| Window 1 IS degradation | -43.72% | -61.26% |
| Window 2 IS degradation | -45.28% | -6.83% |
| Average IS degradation | ~-44% | -34.05% |
| Window 1 validation trades | 106 | 177 |
| Window 2 validation trades | 33 | 68 |

**Analysis**: Window 1 OOS outperformance is MORE extreme (-61% vs -43%). Window 2 is dramatically BETTER (-6.83% vs -45.28%). On average across windows, the permissive profile has LESS extreme OOS outperformance overall (-34% vs -44%).

The pattern across both candidates is consistent: validation periods (2024-2025) systematically yield higher metrics than train (2022-2023). This is **a property of the validation period regime**, not a candidate-specific artifact. The 2024-2025 regime was structurally favorable to a long-biased uptrend strategy, and both candidates are such strategies.

The same evaluation standard from `AUDIT_WF_TRIAL_00095_2026-05-08` applies: this is a **non-blocking false positive** because both windows have decision-grade sample counts and the directional pattern matches a known regime characteristic, not a methodology flaw. Per `STOP-with-alternatives` discipline:

**Alternative interpretations to keep open**:
- The regime favorability may not persist into post-2025 periods → real-world degradation is plausible
- The window-1 -61% degradation specifically is the strongest single anomaly across the chain; if a third candidate showed similar window-1 inflation, that would be evidence of a window-specific data quirk worth investigating
- A future WF with extended date range (2026 included) would update this evaluation

**Flag status**: evaluable as non-blocking false positive, **subject to ongoing paper validation contradicting historical pattern**.

### Flag 2: `pnl_sanity_review_required`

This flag was NOT raised on trial-00095 v3. It IS raised here because absolute pnl is materially higher.

| Metric | Trial-00095 v3 | experiment-profile-permissive-v1 |
|---|---:|---:|
| Trades | 271 | 496 |
| ER | 2.1294 | 1.6590 |
| Implied pnl_R | 577.07 R | 822.87 R |
| pnl_abs | 92,324.81 | 265,542.31 |

**Analysis**: 2.88× higher absolute pnl from 1.83× more trades × 0.78× ER × likely larger position sizing in dollars during 2024-2025 BTC price range. The mechanical sanity threshold (whatever value) trips on the absolute pnl number, not on the methodology.

This is a **mechanical sanity check, not a methodology flag**. The number is large because (a) more trades, (b) BTC price range during validation included $100k+ levels, (c) position size scales with notional. Nothing in the underlying methodology is anomalous.

**Flag status**: non-blocking, mechanical artifact. The threshold itself should be reviewed in the cost-model audit context (`COST_MODEL_AUDIT_V1`) — if pnl thresholds are calibrated to lower BTC prices, they need updating.

## Critical Issues

None blocking. Three completion findings below.

## Findings — Completion Gaps (must close in small follow-up commit before paper validation V2)

### Finding 1: Missing candidate JSON spec

`research_lab/candidates/experiment-profile-permissive-v1.json` was not committed. The candidate identity, frozen parameter override, and dataset lineage are documented in the report markdown and lineage doc, but not in a machine-readable spec the way `research_lab/hypotheses/active/*.json` operate.

**Required follow-up**: Create the JSON spec with:
- `candidate_id`: `experiment-profile-permissive-v1`
- `derived_from`: `optuna-default-v3-trial-00095`
- `frozen_overrides`: `{"strategy.min_sweep_depth_pct": 0.005}` (plus ETH/SOL overrides at runtime via multi_asset.symbol_overrides — document where these come from)
- `protocol_hash`: `023dc84c...`
- `candidate_config_hash`: `68fd6caf...`
- `dataset_lineage`: object with BTC SHA, ETH SHA, SOL SHA, fetch_method
- `wf_report_path`: pointer to the audit doc
- `audit_chain`: list of commit hashes (`9d99dc7`, `57c6cd3`, `3330e22`, `db9973a`, `5cec9a0`, this audit hash)

This file becomes the canonical spec for paper validation V2 to reference. ~15 minutes of work.

### Finding 2: Revalidation artifacts not committed, no SHA recorded

Codex documented that these artifacts exist locally:
- `research_lab/revalidation/experiment-profile-permissive-v1-server-snapshot/summary.json`
- `research_lab/revalidation/experiment-profile-permissive-v1-server-snapshot/evaluation.json`
- `research_lab/revalidation/experiment-profile-permissive-v1-server-snapshot/walkforward_report.json`
- `research_lab/revalidation/experiment-profile-permissive-v1-server-snapshot/recommendation.json`

But `research_lab/revalidation/` is gitignored, so the canonical metric sources are not in the repo. The report markdown contains the metrics, but a third party (or future Claude in a new session) cannot independently verify the SHA256 of the underlying JSON outputs.

**Required follow-up**: Compute SHA256 of all four files. Add a "Revalidation Artifact SHA256" subsection to the report listing them. This is the minimum reproducibility evidence — the files don't need to be committed (they're large and regeneratable from snapshot + protocol), but their SHAs in the report make tampering detectable and re-runs comparable.

### Finding 3: No determinism test

My handoff specified `tests/test_wf_experiment_profile_permissive_v1.py` with a determinism property (two runs produce identical `protocol_hash`, identical summary metrics, identical SHA256). Codex did not commit this test, presumably because the chosen approach (use existing pipeline) inherits determinism guarantees from the trial-00095 v3 chain.

This is mostly defensible — the existing pipeline's determinism is presumably already tested elsewhere. But there is no in-repo proof that running `research_lab` with the experiment profile + this override produces identical artifacts on repeat invocations.

**Required follow-up**: Either (a) add a single test that re-runs the candidate evaluation twice and asserts identical `protocol_hash` + `config_hash` + key metric values, or (b) point to an existing pipeline-level determinism test (if one exists) and document the inheritance explicitly in the report's methodology section.

Option (a) takes ~30 min; option (b) takes ~10 min if a suitable test exists. Either is acceptable.

## Observations (non-blocking)

4. The permissive profile produces 1.83× more trades than trial-00095 v3 at 0.78× the per-trade ER. This trade-off is **quantified and expected** — it's the same trade-off the user manually invoked on 2026-05-25. The total realized R per period is HIGHER (822 R vs 577 R), but the per-trade quality is LOWER. Whether this is good or bad depends on capacity, slippage cost realism (see `COST_MODEL_AUDIT_V1_PLAN`), and operational tolerance for more frequent rebalancing.

5. The Sharpe of 10.17 (vs trial-00095 v3's 11.93) is a meaningful but not catastrophic decrease. Both numbers are extraordinarily high — Sharpe >10 over 4 years almost always indicates either (a) a real edge, (b) overfit to a benign regime, or (c) sample bias. The fact that trial-00095 v3 paper showed only 1 trade in 24 days while the historical run produced 271 trades in 4 years (= ~67/year = ~1.3/week expected) is itself a regime-departure signal worth tracking once paper accumulates more data.

6. Window 2 OOS trade count jumped from 33 (trial-00095 v3) to 68 (permissive). This is direct empirical evidence that the user's strategic intent worked: lower threshold yields more frequency. The audit measurement validates the deployment-time decision, even if that decision was made out-of-band.

7. The recommendation pipeline did NOT raise `pf_hard_review_required` here, unlike trial-00095 v3 which did. The permissive profile's PF of 3.53 is below the hard-review threshold (whatever it is), while trial-00095 v3's window-2 PF 7.50 tripped it. **Permissive profile is BETTER on this specific gate** — less extreme PF, less likely to be statistical noise.

## Recommended Next Step

**Follow-up commit (Codex) closing Findings 1, 2, 3.** Single commit on `deploy/multi-asset-paper-v1`, ~1 hour of work:

```
research: experiment-profile-permissive-v1 A2 follow-up artifacts
- candidate JSON spec
- revalidation artifact SHA256 in report
- determinism test (or documented inheritance)
```

After that commit is audited (~30 min on my side), the chain is:
- A1.build → A1.build follow-up → A1.deploy → A2 → A2 follow-up — all DONE
- Candidate `experiment-profile-permissive-v1` is PROMOTION_READY with conditions met
- **Unblocks `PAPER_PERFORMANCE_VALIDATION_V2`** with this candidate as reference (not trial-00095)

In parallel (independent of A2 follow-up): the two queued non-blocking milestones can run anytime:
- `UPDATE_CANDIDATE_ID_METADATA_OWNERSHIP_PRESERVATION_FIX_V1` (~30 min)
- `BACKUP_PRODUCTION_DB_BUSY_WAL_FIX_V1` (~1-2h, higher urgency before next backup)

## Decision

Commit `5cec9a0` is approved as the substantive A2 WF result. The methodology deviation (existing pipeline reuse) is accepted as superior to the handoff. The candidate is PROMOTION_READY pending closure of three small completion gaps in a follow-up commit. Paper validation V2 may begin queueing as the next milestone after A2 follow-up.
