# CONTEXT -> CLAUDE CODE (Windsurf, dual-repo workspace) — edge-lab auditor onboarding
Date: 2026-06-05
Author: Claude Code (btc-bot session)
For: the Claude Code instance running in the Windsurf workspace as AUDITOR of edge-lab.

> Self-contained. Read this + the three migration docs and you have full context — no
> dependency on the originating btc-bot chat.

## Your role (non-negotiable)
You are the AUDITOR/EVALUATOR, the ONLY auditor. You do NOT build. Codex builds in
`edge-lab`; you audit after each push. Generator–evaluator split — never rubber-stamp,
never self-mark "done", default stance skeptical: prove it works, don't assume.
(Operating model = `CLAUDE.md` once authored in edge-lab; until then, this doc governs.)

## Workspace
Two repos mounted:
- `btc-bot` — READ-ONLY reference. Real architecture on `deploy/multi-asset-paper-v1`.
  Migration docs live on branch `claude/project-abandonment-DGlO0` under
  `docs/edge-lab-migration/`. Never write here.
- `edge-lab` — the AUDIT TARGET. Private, clean independent history. Codex commits here.

## Why edge-lab exists (one paragraph)
btc-bot tested directional prediction on BTC microstructure across six strategy families;
none showed an edge. The product owner abandoned the strategy AND the contaminated
documentation/narrative, keeping only what honestly worked: the data pipeline, the
deterministic replay/backtest harness, and the walk-forward + control-cohort research
methodology. `edge-lab` is that dry, strategy-agnostic skeleton with fresh docs. The
value is integrity and speed of falsification — a fast, honest NO is a success, not a
failure. The skeleton does NOT manufacture an edge.

## What Codex is building (v1 bootstrap)
Scope + steps: `btc-bot:docs/edge-lab-migration/HANDOFF_EDGE_LAB_BOOTSTRAP.md` and
`HANDOFF_CODEX_WINDSURF.md`. File-class cut line: `MIGRATION_MANIFEST.md`.
Summary: extract strategy-agnostic skeleton (core/data/backtest/execution/storage +
methodology subset of research_lab), replace signal_engine with a `SignalStrategy`
interface, two trivial baselines (BuyAndHold + seeded RandomEntry), minimal settings,
fresh docs, CI/ruff/pytest, deterministic JSON report. NO new edge, NO old narrative.

## Four binding conditions you imposed (audit against these explicitly)
Codex confirmed the plan; you added four conditions that are part of v1 scope:
1. **Data reproducibility** — baseline runs on a FIXED, committed snapshot/fixture in
   edge-lab (candles + funding), NOT live-fetch. "Real data" = real snapshot. Without
   this, byte-identity is impossible. FAIL the audit if the baseline depends on a
   non-reproducible live pull.
2. **Report byte-identity** — the byte-compared artifact is a NORMALIZED metrics object;
   run-timestamp, duration, absolute paths, hostname are excluded or fixed. Stable key
   order, deterministic float formatting. Verify two runs are byte-identical yourself.
3. **Frozen pre-registration is REAL, not verdict-only** — gates declared BEFORE the run
   (pre-registration artifact); verdict computed mechanically against them; the baseline
   must actually traverse this path. A verdict function with no frozen gate = LOOKS_DONE
   on Methodology Integrity. This is the crown jewel; hold the line.
4. **Scope purity** — `dashboard/` and `monitoring/` are OUT of v1 (separate milestone).
   Flag any observability creep.
Minor: RandomEntry seed counts toward the ≤3 param cap; RNG must be seeded
(numpy/`random.Random`), not hash-based, for cross-platform determinism.

## Audit standard to apply
Run the full `CLAUDE.md` audit (layer separation, contract compliance, determinism,
state integrity, error handling, smoke coverage, tech debt, discipline) PLUS the
Research Lab axes: Methodology Integrity, Promotion Safety, Reproducibility & Lineage,
Data Isolation, Search-Space Governance, Artifact Consistency, Boundary Coupling.
Acceptance checklist: bootstrap §6 + the four conditions above.

### Verdict for v1
- **MVP_DONE** = clean skeleton, deterministic baseline on a committed snapshot, control
  cohorts + nested WF exercised, frozen-gate mechanism real, zero strategy/narrative
  residue, plumbing tests + ruff + CI green. (This is the realistic v1 target.)
- **DONE** = above + production-grade hardening (unlikely needed at v1).
- **LOOKS_DONE** = files exist but frozen gate is a stub, data isn't reproducible, or
  byte-identity unproven.
- A baseline ER materially different from ~0 is a HARNESS BUG — investigate, do not pass.

## Process
1. After Codex pushes, audit `edge-lab` HEAD.
2. Write report to `edge-lab:docs/audits/AUDIT_<milestone>_<YYYY-MM-DD>.md` (the
   CLAUDE.md report format). Verdict not opinion. Name risks. One recommended next step.
3. Push policy: on DONE/MVP_DONE push the audit immediately; on LOOKS_DONE/NOT_DONE,
   fix list to Codex first (generate a Codex handoff), do not bless.
4. Do NOT pick the first edge hypothesis — that's a later, pre-registered milestone and
   the product owner's strategic call.

## Access note
You can only audit edge-lab if this session has edge-lab in scope (it does, in this
workspace). If a future session lacks it, say so rather than guessing.
