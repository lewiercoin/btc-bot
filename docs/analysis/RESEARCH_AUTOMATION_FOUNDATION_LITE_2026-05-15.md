# Research Automation Foundation Lite - Design Document

**Date:** 2026-05-15
**Milestone:** RESEARCH_AUTOMATION_FOUNDATION_LITE_V1
**Status:** READY_FOR_AUDIT

## Why This Exists

After M1-M6, the research lab has valuable but manual one-off scripts for live signal diagnosis, threshold stability, 5m feasibility, and 5m overlay testing. Each script solved a specific question, but the workflow was not standardized.

This milestone adds a lightweight foundation for the repeatable workflow:

`hypothesis -> experiment -> evaluation -> report`

The goal is faster, comparable, and reproducible research without adding any autonomous agent, LLM-generated code, or production runtime coupling.

## What It Standardizes

1. Hypothesis specs as declarative JSON data
2. Experiment registry as SQLite records
3. Data manifest hashes for reproducibility
4. Gate evaluator for deterministic pass/fail decisions
5. Standard markdown report generation

## How It Relates To Existing autoresearch_loop.py

`research_lab/autoresearch_loop.py` already implements a bounded parametric refinement loop. It remains unchanged.

The new foundation is broader and lower-level. It can describe research programs, hypotheses, datasets, experiment results, gate outcomes, and reports for future work such as ETH feasibility, exit studies, compression filters, and feature importance. It does not execute backtests by itself.

## Scope Now

Included:

- Research program and hypothesis dataclasses
- Safe hypothesis spec validation
- SQLite experiment registry
- Data manifest contract and combined hash
- Deterministic gate evaluator
- Standard report template
- Non-executing example hypothesis
- Unit tests

Deferred:

- LLM hypothesis generation
- Karpathy-style autonomous loop
- Multi-iteration agent
- External tools or repos
- Automatic experiment execution
- Batch runner integration
- Real backtest integration

## Architecture

Research programs define boundaries. Hypotheses belong to a program and specify rationale, variables, frozen assumptions, expected observation, acceptance criteria, kill criteria, and out-of-scope areas.

Experiments record a concrete run against a hypothesis and data manifest. The registry stores config hash, data manifest hash, runner name, date range, metrics, gates, artifacts, status, and verdict.

The evaluator consumes metrics and gates. It returns a deterministic verdict:

- `PASS`: all required gates pass
- `MARGINAL`: required gates pass, recommended gates fail
- `FAIL`: required gates fail
- `INCONCLUSIVE`: trade count is insufficient
- `BLOCKED`: required metrics or data are missing

The report generator turns hypothesis, metrics, manifests, gates, and artifacts into a standard markdown report.

## Usage Example

```python
from pathlib import Path

from research_lab.evaluators.gate_evaluator import Gate, evaluate_gates
from research_lab.experiments.api import create_experiment, record_result
from research_lab.experiments.manifest import DataManifest

registry_path = Path("research_lab/experiments/experiments.db")
manifest = DataManifest(
    dataset_id="btc_15m_replay_run13",
    path="research_lab/snapshots/replay-run13-regime-aware-trial-00063.db",
    timeframe="15m",
    symbol="BTCUSDT",
    date_start="2024-01-01",
    date_end="2026-03-28",
    row_count=78433,
    content_hash="example",
    quality_status="PASS",
    source="replay-run13",
)

experiment_id = create_experiment(
    registry_path=registry_path,
    hypothesis_id="example_hypothesis_v1",
    config={"threshold": 0.00649},
    data_manifests=[manifest],
    baseline_reference="trial-00095",
    runner_name="offline_runner",
    date_range_start="2024-01-01",
    date_range_end="2026-03-28",
    git_commit="abc123",
)

metrics = {"trade_count": 47, "expectancy_r": 2.11, "profit_factor": 3.95}
evaluation = evaluate_gates(
    metrics,
    [
        Gate("min_trades", ">=", 20, "trade_count"),
        Gate("min_er", ">=", 1.0, "expectancy_r"),
        Gate("min_pf", ">=", 1.5, "profit_factor"),
    ],
    experiment_id=experiment_id,
)

record_result(
    registry_path=registry_path,
    experiment_id=experiment_id,
    verdict=evaluation.verdict,
    metrics=metrics,
    gates=list(evaluation.gate_results),
    artifacts={"report": "docs/analysis/example.md"},
)
```

## Safety Boundaries

- Hypothesis specs are data-only.
- The validator rejects executable fields such as `python_code`, `module_path`, `function_name`, `eval`, `exec`, and `shell_command`.
- No YAML or JSON spec can import or execute code.
- No production, PAPER, runtime, settings, core, execution, or orchestrator files are modified.
- Existing `autoresearch_loop.py` remains unchanged.

## Future Work

- CLI commands for experiment creation and report generation
- Batch runner integration
- Real backtest runner adapters
- ETH and exit optimization studies using the registry
- Offline LLM hypothesis proposals that emit safe JSON specs for human approval
