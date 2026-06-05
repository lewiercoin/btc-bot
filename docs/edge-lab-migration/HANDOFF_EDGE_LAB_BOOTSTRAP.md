# HANDOFF: EDGE-LAB BOOTSTRAP (turn-key)
Date: 2026-06-05
Author: Claude Code
For: the first session opened on repo `edge-lab` (auditor + builder).

> This handoff makes the new repo turn-key. It is self-contained: read this +
> `MIGRATION_MANIFEST.md` (copy both into edge-lab) and you can bootstrap without
> re-deriving context. The old btc-bot repo is REFERENCE ONLY — never a dependency.

## 0. Prerequisite (human, one-time)
Create private GitHub repo `edge-lab` (init with README). The btc-bot session could
NOT create it (integration scoped to btc-bot; got 403). Then open a Claude Code
session scoped to `edge-lab` and run this handoff.

## 1. Goal of v1
Stand up the **strategy-agnostic skeleton** + a **trivial baseline** that proves the
workshop runs end-to-end and deterministically — BEFORE any edge hypothesis. This is
explicitly NOT about finding an edge. Success = a clean, honest, reproducible harness.

## 2. Bootstrap steps (ordered)
1. Initialize structure per `MIGRATION_MANIFEST.md` (KEEP / GENERALIZE / LEAVE / AUTHOR-FRESH).
   Pull source files by reference from btc-bot `deploy/multi-asset-paper-v1`; do not
   carry git history.
2. Generalize `core/models.py` (strip sweep/reclaim fields) and `replay_loader` to match.
3. Replace `signal_engine.py` with a `SignalStrategy` interface (§4) + the baseline (§5).
4. Hard-reset `settings.py`/`settings.json` to a minimal config (no 42-param block).
5. Author the fresh doc set (§3).
6. Wire CI (`.github/`), ruff, pytest. Port only plumbing tests; they must pass.
7. Run the baseline end-to-end on real data (§5); commit the deterministic report.
8. Do NOT self-mark done; audit against §6 acceptance criteria.

## 3. Fresh documentation set (AUTHOR-FRESH — zero old text)
- `README.md` — what edge-lab is: a strategy-agnostic quant research workshop.
- `docs/ARCHITECTURE.md` — layer map (data → storage → replay/backtest → strategy
  interface → execution → research harness), boundaries, determinism guarantees.
- `docs/RESEARCH_PROTOCOL.md` — the inherited discipline, verbatim the seven hard
  rules from the manifest §"Hard rules": frozen pre-registration, control cohorts,
  nested walk-forward, parameter cap, docs==reality, raw>narrative, generator–evaluator
  split. This is the crown jewel; make it the first doc.
- `AGENTS.md` / `CLAUDE.md` — operating model for builder vs auditor, fresh, concise.
- `docs/DECISIONS_LOG.md` — start empty; every strategic decision recorded here.

## 4. `SignalStrategy` interface (the de-coupling that fixes btc-bot's #1 design flaw)
A minimal, strategy-agnostic contract so the harness never again hard-codes one edge:
```
class SignalStrategy(Protocol):
    name: str
    params: Mapping[str, float]          # capped, declared per strategy
    def on_snapshot(self, snapshot: MarketSnapshot) -> Signal | None: ...
```
Execution / risk / governance / accounting consume `Signal` and stay edge-agnostic
(they already are in btc-bot — preserve that). Features become per-strategy, not a
shared sweep-coupled engine.

## 5. Trivial baseline (the v1 deliverable)
Implement TWO reference strategies, both expected to show ~zero edge — the point is to
prove the pipeline, not to win:
- `BuyAndHoldStrategy` — enter long once, hold. Sanity-checks accounting vs market drift.
- `RandomEntryStrategy(seed)` — deterministic random entries with fixed holding. This
  doubles as the first control cohort and proves determinism.
Run both through replay → execution → trade_log → walk-forward → JSON report, on real
collected data. Expected: ER ≈ 0 (after costs, slightly negative). A non-trivial ER
from these means a harness BUG — investigate before trusting any future edge.

## 6. Acceptance criteria (auditor checks; do NOT self-mark done)
- [ ] Skeleton compiles; plumbing tests pass; ruff clean; CI green.
- [ ] No sweep/reclaim/strategy-specific code or docs present (grep clean).
- [ ] `settings` has NO 42-param strategy block; baseline uses ≤3 declared params.
- [ ] Baseline runs end-to-end on real data and emits a **deterministic** JSON report
      (same input → byte-identical metrics across two runs).
- [ ] Control-cohort + nested-WF machinery present and exercised by the baseline.
- [ ] `RESEARCH_PROTOCOL.md` exists and the harness enforces frozen-gate evaluation
      (verdict computed mechanically, not narrated).
- [ ] Docs==reality: any deployed/config identity is surfaced and matches docs.

## 7. Honest caveat to keep in the repo (so v2 doesn't repeat v1's self-deception)
A clean workshop accelerates honest iteration; it does NOT manufacture an edge. The
btc-bot finding stands: discretionary/parametric directional prediction on BTC
microstructure showed no edge across six families. edge-lab's value is integrity and
speed of falsification — treat a fast, honest NO as a success of the workshop.

## 8. First experiment (AFTER baseline passes — separate milestone)
Do not pick it now. When ready, pre-register ONE hypothesis under
`RESEARCH_PROTOCOL.md` with frozen gates and ≤3 params. Candidate directions are an
open question for the product owner; the workshop is deliberately edge-agnostic.
