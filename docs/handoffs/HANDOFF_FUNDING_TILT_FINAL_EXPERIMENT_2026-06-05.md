## CLAUDE HANDOFF -> CODEX

### Checkpoint
- Branch of record: `deploy/multi-asset-paper-v1` (real production; `main` is 278 commits stale — do NOT build on `main`)
- Pre-registration (FROZEN, read first): `docs/FUNDING_TILT_FINAL_EXPERIMENT_PREREGISTRATION_2026-06-05.md`
- Working tree: clean

### Before you code
Read these (mandatory):
1. `docs/FUNDING_TILT_FINAL_EXPERIMENT_PREREGISTRATION_2026-06-05.md` — frozen criteria, decision rule, parameter cap.
2. `docs/BLUEPRINT_RESEARCH_LAB.md` — research lab workflow + control-cohort methodology.
3. `AGENTS.md` — discipline + commit rules.
4. Existing diagnostics for the control-cohort pattern, e.g. the volatility/regime edge-discovery diagnostics under `research_lab/diagnostics/` and `docs/audits/AUDIT_VOLATILITY_BREAKOUTS_*`.

### Milestone: FUNDING-TILT-FINAL-EXPERIMENT (single shot, terminal decision)
Scope: research-lab diagnostic ONLY. No live/paper deployment in this milestone.
Reuse the existing backtest/walk-forward harness and fill model. Do NOT touch
`core/signal_engine.py` sweep/reclaim logic; implement the funding signal as a
separate, isolated research generator.

Deliverables:
- `research_lab/diagnostics/funding_tilt_edge_discovery_v1.py` — deterministic diagnostic:
  - Signal: funding z-score over window `W`; SHORT if z > +`Z`, LONG if z < -`Z`; exit after holding `H` (time-based) or funding mean-reverts to 0. **Hard cap: 3 parameters. No structure/confluence features.**
  - Costs: funding paid/received + taker fees + slippage (existing fill model).
  - Control cohorts: random-entry, time-shifted-funding, inverse-signal. Main vs each, per fold.
  - Walk-forward >= 2 folds, fold windows pre-declared in the script header (no peeking).
- Output: single JSON with per-fold main-vs-controls metrics ending in `"verdict": "PASS" | "FAIL"`, computed mechanically against the frozen gates in the pre-registration.
- Pre-declared parameter grid in the script header (declare BEFORE running; selection by out-of-sample WF, not max in-sample).
- Validation report: `research_lab/validation_report_funding_tilt_v1.md` (numbers only; no narrative spin).

Target files: `research_lab/diagnostics/funding_tilt_edge_discovery_v1.py`, `research_lab/validation_report_funding_tilt_v1.md`.

### Frozen gates (from pre-registration — do not re-derive)
OOS, all must hold: trades >= 30; ER > 0.10 R; PF > 1.2; beats all 3 controls in EVERY fold; positive ER every fold; degradation < 40%. Any miss = FAIL.

### Decision rule (terminal)
- PASS → separate follow-up milestone for ONE paper deployment.
- FAIL → wind-down recommendation; no further hypothesis treadmill.

### Known Issues (from Claude Code audit)
| # | Issue | Blocking for this milestone? |
|---|---|---|
| 1 | Documented prod != actual prod (trial-00095 hash 0 trades; live = `c01f79…`) | NO for the diagnostic, but governance fix (tracker reconcile, monitor tracks real hash, trial-00095 closed DEAD) must land before any PASS→paper step. |
| 2 | Project docs misreport trial-00095 as "ER 2.1 PF 4.6 validated" while raw WF = passed:false | NO — but do not cite those numbers anywhere. |
| 3 | ~42 active params already; overfitting surface high | YES — enforce the 3-parameter cap; do not add the funding signal on top of the 42-param stack. |

### Your first response must contain:
1. Confirmed scope (what you will implement) + the pre-declared parameter grid.
2. Acceptance criteria restated (the frozen gates).
3. The fold windows you will use (pre-declared).
4. Implementation plan (ordered steps).
5. Only then: start coding.

### Commit discipline
- WHAT / WHY / STATUS in every commit.
- Do NOT self-mark "done". Claude Code audits after push, against the frozen gates only.
