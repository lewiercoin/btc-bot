## Research Lab 2-Phase Workflow

Research Lab is a staged offline system.

It does not treat `optimize` and `autoresearch` as interchangeable modes.

The canonical order is:

1. Phase 1 discovery with Optuna
2. Phase 2 refinement with autoresearch
3. Human review through approval artifacts

## Phase 1: Discovery

Entry point:

```bash
python -m research_lab optimize \
  --start-date 2022-01-01 \
  --end-date 2026-03-01 \
  --n-trials 100 \
  --study-name run-discovery \
  --warm-start-from-store
```

Purpose:

- explore the ACTIVE search space broadly
- build fresh trial history for the current protocol and date range
- produce Pareto candidates for later refinement

Contracts:

- hard baseline gate blocks broken or nonsensical baselines
- soft baseline gate warns on weak but evaluable baselines and returns summary metrics
- warm-start loads only matching trial history by default:
  - `protocol_hash`
  - `search_space_signature`
- operators may bypass warm-start hygiene with `--warm-start-ignore-protocol`
  - this is unsafe
  - it exists for deliberate forensic or migration cases only

Artifacts:

- `research_lab/research_lab.db` stores trials, walk-forward reports, and recommendations
- each persisted trial carries lineage:
  - `protocol_hash`
  - `search_space_signature`
  - `regime_signature` when available
  - `trial_context_signature`
  - `baseline_version`
- optimize summary includes:
  - baseline warning state
  - baseline metrics
  - Pareto-ranked candidates

## Phase 2: Refinement

Entry point:

```bash
python -m research_lab autoresearch \
  --start-date 2022-01-01 \
  --end-date 2026-03-01 \
  --output-dir research_lab/runs/autoresearch_run \
  --seed-from-pareto research_lab/runs/latest_report.json
```

Purpose:

- mutate and refine candidates after discovery has already mapped the current search context
- focus search around credible historical regions instead of re-running broad exploration

Contracts:

- autoresearch is post-hoc walk-forward only in v1
- nested mode is rejected
- candidate generation may be seeded from Pareto JSON through `--seed-from-pareto`
- Pareto seeding is a handoff, not promotion
- ranking is deterministic and prefers:
  - walk-forward pass
  - non-fragile candidates
  - higher expectancy
  - lower drawdown
  - higher profit factor
  - higher trade count
  - deterministic candidate id tie-break

## Handoff Between Phases

Recommended handoff:

1. Run `optimize`
2. Build or reuse a report containing `pareto_ranked`
3. Pass that JSON into `autoresearch --seed-from-pareto`
4. Review `loop_report.json`
5. If no blocking risks exist, review the approval bundle

Accepted Pareto JSON shapes:

- report object with `pareto_ranked`
- plain list of candidate objects

Each candidate must include `params`.

## Methodological Hygiene

- do not mix protocols or search spaces inside warm-start by default
- do not treat a weak baseline as identical to a broken baseline
- do not refine candidates before Phase 1 has produced context-matching history
- do not relax promotion or walk-forward gates to rescue a candidate
- do not promote automatically into `settings.py`

## Operator Notes

- `optimize` is the discovery engine
- `autoresearch` is the refinement engine
- approval bundles are review artifacts only
- human review remains the only promotion path
