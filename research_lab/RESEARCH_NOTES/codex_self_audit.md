# Codex Self-Audit - Research Mining Deliverables

## Five Reasons My Recommendations May Be Wrong

1. I may be over-penalizing SMC candidates because recent btc-bot research invalidated post-sweep confirmations. A different earliest-knowable implementation could still find accessible edge.
2. I reconstructed the paper's 10 feature formulas from SHAP image labels and paper prose because the source package did not include a formal formula table. Some formulas, especially `concentration_of_volume`, may differ from the authors' implementation.
3. I treated PyIndicators PyPI code as the relevant implementation because GitHub main is docs-heavy. If the maintainers use another branch/source workflow, my "repo source mismatch" critique may be incomplete.
4. I did not run empirical comparisons on BTC data. All setup confidence ratings are methodological, not measured expectancy.
5. I may be too conservative about `reclaim_session`; if the new implementation uses session levels as provenance rather than a time filter, it may not repeat the failed session-sweep specialist.

## Three Implicit Assumptions

1. Current project priority is throughput without degrading trial-00095 quality. This appears true from the brief and tracker.
2. Future implementation can read enough aggTrade/book-ticker data to compute microstructure context. This is uncertain; bid/ask sizes and tick history availability need confirmation.
3. Claude's prior audit conclusions are binding unless the new hypothesis is materially different. This is true under AGENTS.md workflow.

## Two Things Requiring Operator Decision

1. Should the next implementation phase start with `level_scanner` foundation or `MicrostructureContext` telemetry? These are both defensible, but they serve different bottlenecks.
2. Should `reclaim_session` be allowed back as a session-level-provenance candidate despite the failed session-sweep specialist, or should session work be limited to non-entry context?

## One Disagreement With Claude In Browser

Claude's ranking put joshyattridge/smart-money-concepts as high-value mainly because `smc.sessions()` is "gold" for `reclaim_session`. I disagree with the strength of that framing. The existing btc-bot session-sweep specialist already failed, and joshyattridge's session implementation is a fixed-clock helper with timezone edge cases, not an edge source. It is useful as a cross-validation reference for session labels, but not "gold" as a setup generator unless the new candidate is explicitly level-provenance-based and passes MFE accessibility.

## Risk Register

| Risk | Probability | Impact | Mitigation |
| --- | ---: | ---: | --- |
| Repeating invalidated SMC delayed-entry research | 4 | 4 | Require MFE before/after entry and `label_available_bar` for every candidate |
| Microstructure context leaks into live decision path too early | 2 | 5 | V1 contract informational-only; audit for no signal/governance/risk reads |
| Paper feature formulas differ from reconstructed definitions | 3 | 3 | Operator approval of local formulas; cite reconstruction caveat; compare to any future author code if released |
| Missing bid/ask quantity makes L1 imbalance unavailable | 3 | 3 | Design graceful fallback; do not block context object on unavailable fields |
| Session timezone/DST errors create false levels | 3 | 4 | Define sessions in UTC only; unit-test boundaries; avoid local clock claims |
| PyIndicators package/repo mismatch weakens reproducibility | 3 | 3 | Vendor no code; use wheel version only as external validation; store hashes if used |
| Level scanner becomes signal engine by scope creep | 2 | 5 | Enforce scanner emits facts only; setup modules interpret facts later |
| Tardis/liquidation backfill grows beyond sprint scope | 3 | 4 | Keep liquidation clusters placeholder until DATA-INTEGRITY-V1/backfill scope is explicit |
| Overfitting to flash-crash microstructure behavior | 3 | 4 | Treat flash crashes as stress slices; require ordinary-regime WF results |
| Markdown docs too broad for direct implementation | 2 | 3 | Use decision points and interface contracts as handoff; Claude audit to flag gaps |

## Confidence Ratings For Deliverables

| Deliverable | Confidence |
| --- | ---: |
| `research_lab/RESEARCH_NOTES/bieganowski_slepaczuk_2026.md` | 3/5 |
| `research_lab/RESEARCH_NOTES/smc_libraries_mining.md` | 3/5 |
| `research_lab/blueprints/microstructure_context_v1_blueprint.md` | 3/5 |
| `research_lab/blueprints/level_scanner_spec.md` | 4/5 |
| `research_lab/nautilus_tardis_pattern_notes.md` | 2/5 |

## Estimated Further Implementation Effort

Option A: `level_scanner` foundation only

- Codex: 10-16h
- Claude: 3-5h
- Scope: sessions, PDH/PDL/PWH/PWL, EQH/EQL, output schema, tests, six-month cross-validation report.

Option B: `MicrostructureContext` telemetry only

- Codex: 10-16h
- Claude: 3-5h
- Scope: formulas, quality flags, replay tests, offline attribution report.

Option C: first candidate setup after scanner

- Codex: 14-24h per candidate
- Claude: 4-8h per candidate
- Recommended first candidate: `reclaim_rejection`, not `reclaim_mitigation`.

Option D: full five-candidate portfolio exploration

- Codex: 45-70h
- Claude: 15-25h
- Not recommended as one milestone; too much scope and too high risk of mixing hypothesis families.

## Self-Audit Verdict

The strongest part of this work is boundary discipline: all recommendations keep ML, SMC, and level detection out of the live decision path until offline evidence exists. The weakest part is empirical absence: I did not run BTC validation, so candidate confidence is methodological rather than measured. With hindsight, I would spend more time extracting exact PyIndicators package tests and Nautilus source files, but that would exceed the core research-mining scope and likely reduce focus on the higher-value deliverables.
