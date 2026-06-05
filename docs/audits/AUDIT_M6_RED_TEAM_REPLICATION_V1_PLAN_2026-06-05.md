# AUDIT: M6 RED_TEAM_REPLICATION_V1 — PLAN

Date: 2026-06-05
Auditor: Claude Code (adversarial framing)
Commit: 6668576a4081c8e2ea124409ec57fa3f9ca6214d
Branch: research/m6-red-team-replication
Plan file: docs/research/RED_TEAM_REPLICATION_V1_PLAN.md
Builder: Codex
Type: Plan-only commit audit (commit 1 of 2)

## Verdict

**`REJECT_FIX_REQUIRED`** — plan is structurally sound but has one
verdict-mechanic hole (Part B trailing-stop reproducibility) that could
fire a false `VALIDATED_EDGE_NOT_REPRODUCIBLE` alarm. Single targeted
fix required as a small plan amendment commit before commit 2 proceeds.

Six observations recorded (one HIGH, one MEDIUM, two LOW, two INSIGHT).

This is exactly the kind of finding adversarial framing is supposed to
catch. Builder did good work; auditor's job is to push harder where
production-impact is largest, and Part B is the production-impact path
because a false `VALIDATED_EDGE_NOT_REPRODUCIBLE` would pause all
production decisions.

## Standard Audit Axes

| Axis | Status |
|---|---|
| Layer Separation | PASS |
| Contract Compliance | PASS |
| Determinism | PASS |
| Error Handling | PASS |
| Smoke Coverage | PASS (8 Part A + 8 Part B unit tests specified) |
| Tech Debt | LOW |
| AGENTS.md Compliance | PASS |

## Research Lab Audit Axes

| Axis | Status |
|---|---|
| Methodology Integrity | PASS |
| Promotion Safety | PASS |
| Reproducibility & Lineage | PASS |
| Data Isolation | PASS |
| Search Space Governance | PASS |
| Artifact Consistency | PASS |
| Boundary Coupling | PASS |

## Quant Research Audit Axes

| Axis | Status |
|---|---|
| Methodology Rigor | PASS |
| Source Coverage | PASS |
| Repo/Code Inspection | PASS |
| Timing Discipline | PASS |
| Entry Realism | PASS |
| Lookahead Risk | PASS |
| Novelty vs Rescue | PASS |
| Creativity vs Cherry-Picking | PASS |

## Adversarial Framing Application

The audit applied adversarial framing as specified in the M6 handoff
§"Notes on auditor framing". Specifically the audit hunted for:

| Adversarial vector | Finding |
|---|---|
| Hidden escape hatches in verdict rules | Caught — F-M6P-002 (loose DB fallback language) |
| Verdict-mechanic holes that fire false alarms | Caught — F-M6P-001 (Part B trail reproducibility) |
| Cherry-picked perturbations that can't actually flip | Not found — P1-P5 cover both axes and the explicit prior conclusion (P3) |
| Soft gates that pass on procedure but miss substance | Not found — all gates are numeric with hard thresholds |
| Anti-rescue clauses missing | Not found — §6 explicit "No post-data rescue interpretation may change these rules" + §9 risks cover A.3 scope creep |

## Compliance Verification

### Handoff fidelity

| Handoff requirement | Plan section | Status |
|---|---|---|
| Part A baseline + P1-P5 + A.3 | §4 | PASS — verbatim |
| Part B SQL replication with frozen acceptance criteria | §5, §6 | PASS — verbatim |
| Pre-data interpretation sentences (P1-P5 + A.3, six total) | §4 lines 164-169 | PASS — verbatim from item-5 reply, locked |
| A.5 verdict rules (SMC_SEQUENCE_INVALIDATION_ROBUST etc.) | §6 lines 248-261 | PASS — verbatim |
| B.2 acceptance bounds (count ±2, ER ±5%, PF ±5%, WR ±3pp, Pearson ≥ 0.95) | §6 lines 263-272 | PASS — verbatim |
| Final M6 verdict mechanism | §6 lines 276-285 | PASS — verbatim |
| Part A imports SMC module as-is | §4 lines 124-127, §8 line 334 | PASS |
| Part B uses independent simulator, no bot/strategy imports | §5 lines 173-175, §8 line 339-340 | PASS |
| Forbidden patterns | §1 lines 24-32, §8 line 344-345 | PASS |
| Adversarial framing statement | §1 lines 19-20 | PASS |
| Plan-only commit | git show --stat: 1 file, 396 lines | PASS |
| STATUS=PLAN_READY_FOR_CLAUDE_AUDIT | commit msg + plan header (implicit) | PASS |
| Pre-existing PC untracked files NOT in commit | git show 6668576 --stat | PASS — only the plan file staged |

### Baseline reference values

| Field | Plan §3 | Verified against |
|---|---:|---|
| Prior SMC JSON SHA256 | `8CA802FD610DFE...` | matches `docs/analysis/SMC_SEQUENCE_EDGE_FEASIBILITY_V1_2026-05-27.md` |
| SMC sequence event count | 1271 | matches prior analysis |
| Net 5b PF | 1.061059 | matches prior |
| Net 5b median return | -0.000442 | matches prior |
| Median MFE before | 0.011565 | matches prior |
| Median MFE after | 0.004916 | matches prior |
| Trial-00095 count | 274 | matches attribution baseline |
| Trial-00095 ER | 2.1211338666525608 | matches attribution baseline |
| Trial-00095 PF | 4.216455510596996 | matches attribution baseline |
| Trial-00095 WR | 0.5656934306569343 | matches attribution baseline |
| Trial-00095 Total R | 581.1906794628017 | matches attribution baseline |

All reference values match the cited prior commits. No silent transcription
drift.

## Findings

### F-M6P-001 — Part B verdict mechanism fires false alarm if simulator lacks trail logic

Severity: **HIGH** | Confidence: 5/5 | **BLOCKING for plan approval**

The attribution report shows the 274 trial-00095 trades split by exit
reason as **SL: 119 trades (43%) and TP_TRAIL: 155 trades (57%)**.

The frozen entry artifact (Plan §5 lines 205-218) exposes:
`entry_price`, `stop_loss`, `tp1`, `tp2`, `baseline_pnl_r`,
`baseline_exit_reason`.

It does NOT expose: trail activation level, trail distance, trail-step
size, partial-fill fraction at `tp1`, or runner sizing rules.

This means the independent simulator can reproduce SL exits correctly
(crossing logic on `stop_loss`) and TP2-flat exits correctly (crossing
logic on `tp2`), but cannot reproduce TP_TRAIL exits without
knowing the trail rule. Reasonable trail models include:

- arm trail at `tp1`, trail by `K * ATR` (K and ATR window unknown);
- arm trail at `tp1`, trail by fixed `(tp1 - entry) * K` (K unknown);
- arm trail at `tp1`, breakeven + step-up at each subsequent `N * ATR`
  (N and ATR window unknown);
- something else entirely from the strategy's `signal_engine.py`
  trailing-stop logic.

**Consequence under current plan §6 verdict rules:**

If the simulator implements a reasonable-but-wrong trail model (e.g.,
"close at `tp2` for TP_TRAIL trades"), the 155 TP_TRAIL trades will
diverge systematically. Pearson on the full 274 will likely fall well
below 0.95. Plan §6 then returns
`VALIDATED_EDGE_NOT_REPRODUCIBLE`.

Per Plan §6 line 283 and the M6 handoff, this verdict triggers
**"critical, all production decisions paused pending root cause"**.

This would be a **false alarm**. The actual finding would be "the
frozen artifact lacks the trail rule needed to reproduce 57% of
trades" — a documentation/lineage gap, not an edge falsification.

**The plan as written cannot distinguish "edge is fake" from "simulator
is incomplete".**

This is exactly the failure mode the M3 audit chain trained us to
look for: a verdict mechanism that mechanically fires under conditions
that don't match its label.

**Required fix (small plan amendment commit):**

1. Add a pre-implementation reconnaissance step: Codex reads the frozen
   entry and trade artifact in full, lists every field actually present,
   and explicitly states whether a closed-form trail rule is derivable
   from those fields alone. If derivable, document the rule and proceed.
   If not derivable, flag immediately and the plan must adopt
   stratification (below).

2. Add stratified verdict rule to Plan §6 Part B:

   > Stratified analysis: compute Pearson separately on the SL-exit subset
   > (~119 trades) and the TP_TRAIL-exit subset (~155 trades).
   >
   > - If both subsets Pearson ≥ 0.95: verdict is full reproduction,
   >   contributes to `REPLICATION_VERIFIES_PRIOR_VERDICTS`.
   > - If SL-subset Pearson ≥ 0.95 AND TP_TRAIL-subset Pearson < 0.95:
   >   verdict is `PARTB_SIMULATOR_INSUFFICIENT_FOR_TRAIL` — actionable
   >   finding distinct from `VALIDATED_EDGE_NOT_REPRODUCIBLE`. Edge is
   >   not invalidated; simulator scope is limited by available
   >   artifact fields. Action item: recover trail rule from
   >   `signal_engine.py` / strategy source before re-running.
   > - If SL-subset Pearson < 0.95: verdict is
   >   `VALIDATED_EDGE_NOT_REPRODUCIBLE` — even the unambiguous SL case
   >   fails to reproduce. This IS the production-pause critical alarm.

3. Add corresponding test cases to Plan §7:
   - SL-subset Pearson computed independently.
   - TP_TRAIL-subset Pearson computed independently.
   - Verdict mechanism returns the correct stratified label for each
     of the three scenarios above.

4. Update Plan §6 final verdict block to incorporate
   `PARTB_SIMULATOR_INSUFFICIENT_FOR_TRAIL` as a fourth possible Part B
   outcome distinct from the existing three.

**Without this fix, M6 carries non-trivial risk of a high-impact false
alarm.** The fix is small (probably 30-50 lines of plan markdown), can
be done in a single amendment commit on the same branch
(`research/m6-red-team-replication`), and does not change scope or
schedule materially.

### F-M6P-002 — DB fallback language contains hedge word "demonstrably"

Severity: MEDIUM | Confidence: 4/5

Plan §5 line 242: *"The fallback snapshot may be used only if the
canonical DB lacks data needed for trial replay or if timestamp
alignment demonstrably requires it."*

"Demonstrably" is a hedge word. It creates room for the implementation
to silently substitute the fallback if it produces convenient results,
and then post-hoc justify "alignment demonstrably required it."

This is exactly the failure pattern that triggered M3 silent-fallback —
the original M3 code path also had "fallback only if canonical missing"
language, which Codex's run interpreted permissively.

**Required fix (include in the same amendment commit as F-M6P-001):**

Rewrite Plan §5 lines 236-244 as:

> Database choice for Part B:
>
> - Primary: canonical DB at the explicit path supplied via CLI
>   (`F:\crowded_unwind_backtest.db` on PC). All Part B verdict
>   computation is bound to canonical-DB results.
> - Comparison: replay-run13 snapshot at
>   `research_lab/snapshots/replay-run13-regime-aware-trial-00063.db`.
>   The simulator may ALSO be run against the snapshot to produce a
>   side-by-side comparison table, BUT the snapshot result NEVER
>   substitutes for the canonical result in verdict computation.
> - If canonical-DB Part B produces `VALIDATED_EDGE_NOT_REPRODUCIBLE`
>   while snapshot-DB Part B passes acceptance, the report classifies
>   the divergence as a `DATABASE_LINEAGE_MISMATCH` finding (canonical
>   verdict still stands as the result).
> - Silent substitution is forbidden. The simulator must record which
>   DB produced which result in the JSON output.

§9 risk register already mentions this risk — the fix is to tighten the
governing rule in §5 to match the risk-register intent.

### F-M6P-003 — Binary verdict on continuous metrics may obscure near-miss results

Severity: LOW | Confidence: 3/5

Plan §6 line 256: "If any perturbation produces net 5-bar PF >= 1.5,
net 5-bar median >= 0, and MFE ratio <= 1.0, Part A returns
`SMC_SEQUENCE_VERDICT_NOT_ROBUST`."

A perturbation that produces PF 1.45 (close to but not crossing 1.5)
would be classified as "verdict robust" alongside a perturbation that
produces PF 0.6.

Plan §4 line 160 already includes "delta versus A.1 baseline" as a
recorded field, so the underlying continuous data IS visible in the
report. Audit at commit 2 will read the deltas, not just the binary
labels.

**No action required.** Documenting here so that commit-2 audit reader
knows to inspect deltas, not just verdict strings.

### F-M6P-004 — Multi-perturbation flip case not explicitly handled

Severity: LOW | Confidence: 3/5

What if BOTH P1 (tighter) AND P2 (looser) flip the verdict? That would
be contradictory — the parameter cannot be simultaneously too loose AND
too strict. It would suggest the metric is hypersensitive to ANY change,
which would mean the diagnostic was measuring noise.

Plan §6 doesn't address this combinatorial case. Likely it would resolve
to `SMC_SEQUENCE_VERDICT_NOT_ROBUST` via the "any perturbation flips"
rule, but the interpretation would be different from a single-axis flip.

**No required action.** Codex can add a single sentence to §6 in the
amendment commit if convenient: "If two contradictory perturbations
(P1 and P2) both flip, the report must flag
`METRIC_HYPERSENSITIVE` as an additional diagnostic note alongside the
primary verdict." Not blocking.

### F-M6P-005 — Risk register addresses M3 process failure directly (INSIGHT)

Severity: INSIGHT | Confidence: 5/5

Plan §9 risk row 8: *"Snapshot fallback hides canonical DB issue / Document
DB choice and forbid silent fallback."*

This is the M3 regression encoded as an explicit risk in M6's own
register. Codex pre-emptively armed M6 against repeating the exact
failure mode that triggered M6 in the first place. Strong methodology
discipline.

### F-M6P-006 — A.3 ablation flip pre-acknowledges prior closure contradiction (INSIGHT)

Severity: INSIGHT | Confidence: 5/5

Plan §6 line 260: *"If A.3 flips but A.1-P5 do not, Part A returns
`SMC_GATES_DESTROYED_RAW_EDGE`."*

This verdict explicitly contradicts the prior
`SWEEP_RECLAIM_EVENT_TAXONOMY` closure. Codex pre-acknowledged that an
A.3 flip would require **re-opening a closed family**, not just
flagging SMC. The plan accepts that as a possible outcome rather than
softening A.3 to avoid the implication. This is exactly what
adversarial replication requires.

## Critical Issues

F-M6P-001 — Part B simulator may produce false
`VALIDATED_EDGE_NOT_REPRODUCIBLE` alarm if trail rule is not derivable
from frozen artifact. **Blocks plan approval.**

## Warnings

F-M6P-002 — DB fallback hedge language. Must be tightened.

## Observations

F-M6P-003, F-M6P-004 (informational).

## Insights (positive)

F-M6P-005, F-M6P-006.

## Recommended Next Step

**Codex creates a single amendment commit on the same branch
(`research/m6-red-team-replication`) that updates Plan §5, §6, §7 with
the F-M6P-001 stratified-verdict patch and the F-M6P-002 DB-fallback
hardening.**

The amendment is small (~30-50 lines), keeps the rest of the plan
intact, and unblocks commit 2 implementation. No new milestone, no
plan rewrite.

Specifically:

1. **Add Plan §5 sub-section "Trail rule reconnaissance"** — pre-impl
   step where Codex inspects frozen artifact fields and classifies
   whether trail rule is closed-form derivable. If not, stratification
   becomes mandatory.

2. **Add Plan §6 Part B verdict stratification** — three-way SL-subset /
   TP_TRAIL-subset / full-population Pearson with corresponding verdict
   labels including new `PARTB_SIMULATOR_INSUFFICIENT_FOR_TRAIL`.

3. **Rewrite Plan §5 lines 236-244 "Database choice"** — canonical DB
   binds verdict; snapshot is comparison-only; `DATABASE_LINEAGE_MISMATCH`
   classification path; explicit "silent substitution forbidden".

4. **Add Plan §7 test cases** — three SL/TRAIL/full stratification tests +
   one DB-binding test that verdict respects canonical result.

5. **Update Plan §6 final M6 verdict block** to add
   `PARTB_SIMULATOR_INSUFFICIENT_FOR_TRAIL` as a fourth Part B
   classification (does not trigger production-pause; triggers
   trail-rule recovery action item).

Commit message:

```
research: M6 plan amendment for trail stratification and DB binding

WHAT: Apply Claude plan audit fixes F-M6P-001 (Part B trail-rule
stratified verdict, new PARTB_SIMULATOR_INSUFFICIENT_FOR_TRAIL outcome)
and F-M6P-002 (canonical DB binds verdict, snapshot is comparison-only,
DATABASE_LINEAGE_MISMATCH classification, no silent substitution).
Adds matching tests to §7.

WHY: Plan as written could fire false VALIDATED_EDGE_NOT_REPRODUCIBLE
on a simulator-incompleteness signal (155 of 274 trades exit via
TP_TRAIL whose rule is not derivable from frozen artifact fields). DB
fallback hedge word "demonstrably" allowed silent substitution
identical to the M3 regression that triggered M6.

STATUS: PLAN_READY_FOR_CLAUDE_AUDIT (re-audit on amendment).
```

After amendment commit, Claude re-audits the plan delta only (small
re-audit, ~30 min). If APPROVE on amendment, commit 2 implementation
proceeds.

## Re-Audit Scope Statement

The re-audit on the amendment commit will verify:
1. Stratified verdict logic is encoded with explicit three-way labels.
2. `PARTB_SIMULATOR_INSUFFICIENT_FOR_TRAIL` is a distinct verdict, not
   a softened `VALIDATED_EDGE_NOT_REPRODUCIBLE`.
3. DB binding language eliminates "demonstrably" and similar hedges.
4. Test cases cover the new stratification.
5. No new escape hatches were introduced while fixing the existing ones.

The re-audit will not re-examine §1-§4 (already approved), §5 trail
reconnaissance sub-section addition, §6 stratification, §7 new tests,
or §9 risk register additions.
