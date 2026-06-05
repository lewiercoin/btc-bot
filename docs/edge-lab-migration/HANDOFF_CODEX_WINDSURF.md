# HANDOFF -> CODEX (Windsurf, dual-repo workspace)
Date: 2026-06-05
Author: Claude Code (architect/auditor)
Mode: BUILDER. You generate; Claude Code audits after push. Do NOT audit your own output.

## Workspace setup (assumed)
Windsurf workspace with TWO repos mounted:
- `btc-bot` — **READ-ONLY REFERENCE.** Never commit here. Source of files to extract.
  Real architecture lives on branch `deploy/multi-asset-paper-v1` (NOT stale `main`).
- `edge-lab` — **WRITE TARGET.** New private repo, clean history. All commits go here.

If `edge-lab` is empty except README: you are doing the v1 bootstrap. Good.

## Mandatory reads before any code
From `btc-bot` (reference):
1. `docs/edge-lab-migration/MIGRATION_MANIFEST.md` — file-class extraction decisions
   (KEEP / GENERALIZE / LEAVE / AUTHOR-FRESH). This is the cut line. Obey it.
2. `docs/edge-lab-migration/HANDOFF_EDGE_LAB_BOOTSTRAP.md` — bootstrap steps, fresh doc
   set, `SignalStrategy` interface, trivial-baseline deliverable, acceptance criteria.
3. `AGENTS.md` — engineering discipline (commit format, layer rules).

## Why this restart exists (context, one paragraph)
btc-bot tested directional prediction on BTC microstructure across six strategy
families; none showed an edge. The product owner is abandoning the strategy AND the
contaminated documentation/narrative, but keeping the parts that honestly worked: the
data pipeline, deterministic replay/backtest harness, and the walk-forward +
control-cohort research methodology. `edge-lab` is that dry skeleton, strategy-agnostic,
with clean independent history. Do not carry over any strategy code, any sweep/reclaim
feature logic, the 42-parameter config, or any old doc/narrative.

## Milestone: edge-lab v1 bootstrap
Scope = `HANDOFF_EDGE_LAB_BOOTSTRAP.md` §2–§5.

Deliverables:
1. Skeleton extracted into `edge-lab` per the manifest (extract by reference — do NOT
   `git clone` btc-bot history; copy file contents, then generalize).
2. `core/models.py` + `backtest/replay_loader` generalized (no sweep/reclaim fields).
3. `signal_engine.py` replaced by a `SignalStrategy` interface (Protocol in §4).
4. `settings.py`/`settings.json` hard-reset to minimal config (NO 42-param block).
5. Fresh doc set authored from scratch (README, ARCHITECTURE, RESEARCH_PROTOCOL with the
   seven hard rules, AGENTS/CLAUDE operating docs, empty DECISIONS_LOG).
6. Two trivial baselines (`BuyAndHoldStrategy`, `RandomEntryStrategy(seed)`) running
   end-to-end on real data, emitting a DETERMINISTIC JSON report.
7. CI (`.github/`), ruff, pytest wired; ported plumbing tests pass.

Target areas in `edge-lab`: `core/`, `data/`, `backtest/`, `execution/`, `storage/`,
`research_lab/` (methodology subset only), `scripts/` (operational subset), `tests/`
(plumbing subset), `docs/`, top-level config.

## Known traps (from the audit of btc-bot — do NOT re-import)
| # | Trap | Rule |
|---|---|---|
| 1 | Harness hard-coded to one edge | Depend on `SignalStrategy` only. Harness stays edge-agnostic. |
| 2 | 42-parameter strategy config | Cap params per strategy (start ≤3). Baseline proves this. |
| 3 | Sweep/reclaim baked into `feature_engine`/`models`/`schema` | Strip on extraction. Grep must be clean. |
| 4 | Doc drift (docs described what code didn't do) | Docs==reality. Config identity surfaced and matches docs. |
| 5 | Verdict read from narrative summaries | Verdicts computed mechanically from raw JSON. |

## Your first response MUST contain (before coding)
1. Confirmed milestone scope (what you will implement).
2. Acceptance criteria (restate from bootstrap §6; add any you'd tighten).
3. Which manifest items you'll GENERALIZE vs KEEP verbatim, with reasoning for any
   deviation from the manifest.
4. Ordered implementation plan.
5. Only then: start coding, committing ONLY to `edge-lab`.

## Commit discipline
- WHAT / WHY / STATUS in every commit message. Commit to `edge-lab` only.
- Do NOT self-mark "done". Claude Code audits after push (against bootstrap §6).
- Do NOT touch `btc-bot` — it is read-only reference.

## Definition of done for v1 (auditor will verify)
Clean skeleton + deterministic baseline on real data + control-cohort/nested-WF
machinery exercised + RESEARCH_PROTOCOL enforced mechanically + zero strategy/narrative
residue. A baseline ER materially different from ~0 is a HARNESS BUG, not an edge.
