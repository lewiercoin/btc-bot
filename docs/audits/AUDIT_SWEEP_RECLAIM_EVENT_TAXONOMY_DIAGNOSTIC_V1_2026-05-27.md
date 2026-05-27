# AUDIT: SWEEP_RECLAIM_EVENT_TAXONOMY_DIAGNOSTIC_V1

**Date:** 2026-05-27  
**Auditor:** Claude Code  
**Builder:** Codex  
**Verdict:** IMPLEMENTATION APPROVED; HYPOTHESIS INVALIDATED

## Implementation Compliance

Claude Code approved the implementation as compliant with the approved plan.

Research-only files created:

- `research_lab/analysis_sweep_reclaim_event_taxonomy_diagnostic_v1.py`
- `tests/test_research_lab_sweep_reclaim_event_taxonomy_diagnostic_v1.py`
- `research_lab/analysis_output/sweep_reclaim_event_taxonomy_diagnostic_v1_2026-05-27.json`
- `docs/analysis/SWEEP_RECLAIM_EVENT_TAXONOMY_DIAGNOSTIC_V1_2026-05-27.md`

Large output artifact note:

- The JSON output was generated locally and is reproducible from the committed
  research script.
- Size: 115,819,135 bytes.
- SHA256:
  `E3DB291C510AEB58287AEA86FB1444FD255AB7B33BBF181B29C7B71825C4ADDA`
- It is not committed to Git because `research_lab/analysis_output/` is ignored
  as generated output and GitHub rejects normal Git blobs over 100 MB.

Production boundary check:

- No changes to `core/**`
- No changes to `execution/**`
- No changes to `orchestrator.py`
- No changes to `settings.py` or `settings.json`
- No changes to `storage/schema.sql`
- No live trading behavior change

Validation:

- Focused pytest: 7/7 passed
- Compile validation passed
- Synthetic SQLite integration test passed

## Data Quality

- Dataset: `BTCUSDT` `5m`
- Rows: 447,000
- Date range: 2022-01-01 to 2026-04-02
- Missing gaps: 0
- OHLC violations: 0
- Duplicate timestamps: 0
- Events total: 535,710

## Result

The diagnostic invalidated the event-taxonomy upgrade hypothesis.

Key findings:

- Immediate reclaim underperformed raw wick cross on 5-bar median signed return:
  - immediate close reclaim: `0.000184`
  - raw wick cross: `0.000237`
- Delayed reclaim edge collapsed when measured from label-available timing:
  - detection bar: `0.001189`
  - label-available bar: `0.000054`
- True breakout/no-reclaim reversed when measured from label-available timing:
  - detection bar: `0.001028`
  - label-available bar: `-0.000268`
- Control cohort validated the methodology:
  - deterministic shifted control median: `0.000000`
  - win rate approximately 50%

## Invalidation Criteria Met

The following approved invalidation criteria were met:

- Immediate or delayed reclaim does not outperform raw wick cross.
- Forward returns from label-available bars remove the apparent delayed-label edge.
- True breakout/no-reclaim is not useful when measured from knowable timing.
- Taxonomy does not add enough explanatory value over the current equal-level baseline.

## Final Recommendation

Close `SWEEP_RECLAIM_EVENT_TAXONOMY_DIAGNOSTIC_V1` as complete and invalidated.

Do not proceed to:

- V2 FeatureEngine facts
- V3 SignalEngine interpretation
- feature-flag integration
- threshold rescue
- regime/session rescue
- detection-bar-only success claims

Trial-00095 remains the validated baseline.

## Scope Boundary For Future Research

This V1 result invalidates the isolated pivot/wick/close/reclaim taxonomy. It
does not invalidate a full SMC sequence, because V1 did not test:

- displacement after liquidity sweep,
- CHOCH/MSS,
- FVG or imbalance,
- retest or mitigation,
- order block logic,
- premium/discount or HTF dealing range,
- the full workflow of liquidity sweep to displacement to structure shift to
  imbalance/FVG to mitigation/retest to realistic entry.

Any future full-SMC research must be a separate planning milestone, for example
`SMC_SEQUENCE_EDGE_FEASIBILITY_V1`, and must start with plan and audit before
implementation.

Key lesson preserved:

> Delayed labels measured from `detection_bar` create fake edge. Always measure
> from `label_available_bar` or a realistic `entry_candidate_bar`.
