# AUDIT: PHASE 0 CONSOLIDATED FINDINGS

Date: 2026-04-24
Auditor: Codex
Roadmap: `docs/audits/QUANT_GRADE_AUDIT_ROADMAP_2026-04-24.md`

## Verdict: NOT_DONE

Phase 0 is not cleanly closable yet. The repository and deployment docs independently confirm several blockers already hinted at in prior audit notes, with the two highest-risk issues being unauthenticated operator controls in the dashboard deployment path and incomplete execution/accounting realism.

## Scope

Read-only review against the roadmap's READY_NOW tracks, focused on:
- AUDIT-13 Security / Secrets / Exchange Safety
- AUDIT-12 Production Ops / SRE
- AUDIT-11 Observability / Dashboard
- AUDIT-19 Recovery / Safe Mode / State Reconciliation
- AUDIT-14 Configuration / Reproducibility
- AUDIT-07 Execution / Paper Fill Integrity
- AUDIT-08 Trade Lifecycle / PnL Accounting
- AUDIT-15 Testing / CI / Quality Gates

## Evidence

- `python -m compileall . -q` -> PASS
- `pytest tests/test_process_manager.py tests/test_paper_fill_fix.py tests/test_recovery_trigger_aware.py tests/test_dashboard_db_reader.py -q` -> PASS, `51 passed in 1.23s`

## Layer Separation: PASS

The repo structure still respects the core separations required by `AGENTS.md`. The main issues found are contract and operations gaps, not layer leakage.

## Contract Compliance: WARN

The roadmap expects realistic paper execution, explainable operational control, and reproducible configuration state. Those contracts are only partially satisfied today.

## Determinism: PASS

The reviewed code paths are deterministic. The major risks are realism and traceability gaps, not hidden randomness.

## State Integrity: WARN

Safe-mode persistence and state refresh paths exist, but accounting and deployment-state reproducibility remain incomplete.

## Error Handling: PASS

The reviewed runtime paths include defensive handling for process management and safe-mode transitions. No immediate blind exception path was identified in the sampled areas.

## Smoke Coverage: WARN

Targeted tests pass, but CI still lacks a coverage gate and exact interpreter pinning.

## Tech Debt: MEDIUM

The debt is not diffuse. It is concentrated in a few high-value operational contracts:
- dashboard exposure model
- fee/funding accounting parity
- config reproducibility surface
- CI enforcement depth

## AGENTS.md Compliance: WARN

The repository remains disciplined, but Phase 0 cannot be called complete while critical runtime and auditability gaps remain open.

## Critical Issues (must fix before next milestone)

1. Unauthenticated dashboard control endpoints are one deploy change away from public bot control. The FastAPI app exposes `POST /api/bot/start` and `POST /api/bot/stop` with no authentication layer in [dashboard/server.py](/c:/development/btc-bot/dashboard/server.py:212) and directly forwards to `ProcessManager`. The repo default bind is local-only in [scripts/server/btc-bot-dashboard.service](/c:/development/btc-bot/scripts/server/btc-bot-dashboard.service:9) and [scripts/run_dashboard.py](/c:/development/btc-bot/scripts/run_dashboard.py:13), but the documented production path explicitly recommends `0.0.0.0:8080` for direct browser access in [docs/dashboard/access-guide.md](/c:/development/btc-bot/docs/dashboard/access-guide.md:63), and the tracker records that this external exposure was actually deployed in [docs/MILESTONE_TRACKER.md](/c:/development/btc-bot/docs/MILESTONE_TRACKER.md:129). That combination fails the security intent of AUDIT-13 and the ops intent of AUDIT-12.

2. Funding is not part of the persisted trade-accounting contract, so the roadmap acceptance criteria for PnL accounting are not met. The trade schema stores only `fees_total` in [storage/schema.sql](/c:/development/btc-bot/storage/schema.sql:133), `config_snapshots` only keep strategy JSON, and there is no `funding_paid` or equivalent field in the runtime trade model in [core/models.py](/c:/development/btc-bot/core/models.py:234). Trade open/close persistence writes and updates no funding component in [storage/repositories.py](/c:/development/btc-bot/storage/repositories.py:643). This leaves AUDIT-08 at best partial and creates paper/backtest/live accounting drift.

3. Paper execution is still structurally optimistic relative to the roadmap's fill-integrity standard. [execution/paper_execution_engine.py](/c:/development/btc-bot/execution/paper_execution_engine.py:16) fills immediately at `snapshot_price`, emits a single `ExecutionStatus.FILLED`, records `fees=0.0`, and computes slippage only versus signal reference rather than the market spread. The execution contract supports `PARTIALLY_FILLED` in [core/execution_types.py](/c:/development/btc-bot/core/execution_types.py:11), but the paper engine never uses it. This keeps AUDIT-07 in partial/fail territory and weakens Gate D confidence.

## Warnings (fix soon)

1. Configuration reproducibility is incomplete. `config_hash` is derived only from `schema_version`, `mode`, `strategy`, `risk`, `execution`, and `data_quality` in [settings.py](/c:/development/btc-bot/settings.py:256). It excludes storage paths, proxy settings, exchange env wiring, Telegram/alert config, and other runtime-affecting surfaces. The persisted snapshot is even narrower: `config_snapshots` stores only `strategy_json` in [storage/schema.sql](/c:/development/btc-bot/storage/schema.sql:262) and [storage/repositories.py](/c:/development/btc-bot/storage/repositories.py:466). That is insufficient for full replay of a production day.

2. Dependency reproducibility is still weak. CI installs from `requirements.txt` on Python 3.11 in [.github/workflows/ci.yml](/c:/development/btc-bot/.github/workflows/ci.yml:18), while the audited local interpreter is Python 3.13.1 and the repo has no `.python-version`, `poetry.lock`, `Pipfile.lock`, or `uv.lock`. This is exactly the sort of environment drift AUDIT-14 is supposed to surface.

3. CI quality gates do not enforce coverage. The workflow runs compile, pytest, ruff, and one smoke script in [.github/workflows/ci.yml](/c:/development/btc-bot/.github/workflows/ci.yml:23), and `pytest.ini` contains no coverage configuration in [pytest.ini](/c:/development/btc-bot/pytest.ini:1). That leaves AUDIT-15 as only partially satisfied.

## Observations (non-blocking)

1. Secret hygiene in the repo itself looks sane at the policy level. `.env` is ignored in [.gitignore](/c:/development/btc-bot/.gitignore:105), and the sample file in [.env.example](/c:/development/btc-bot/.env.example:1) contains placeholders rather than live credentials.

2. Recovery scaffolding appears materially better than the earlier incidents suggest. Safe-mode transitions and trigger-aware recovery paths are present in [execution/recovery.py](/c:/development/btc-bot/execution/recovery.py:82), [storage/state_store.py](/c:/development/btc-bot/storage/state_store.py:358), and the targeted recovery tests passed.

3. The repo default dashboard posture is conservative. The dangerous state comes from documented/deployed ops choices rather than from the default checked-in service definition.

## Recommended Next Step

Freeze Phase 0 as `NOT_DONE`, treat dashboard exposure plus accounting/execution parity as the first remediation bundle, and only then re-run the Phase 0 audit closure decision.
