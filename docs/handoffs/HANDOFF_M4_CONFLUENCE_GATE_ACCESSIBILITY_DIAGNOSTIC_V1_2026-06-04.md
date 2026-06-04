# HANDOFF: M4 CONFLUENCE_GATE_ACCESSIBILITY_DIAGNOSTIC_V1

> **STATUS: CANCELLED — DO NOT IMPLEMENT.**
>
> Cancelled 2026-06-04 by Claude Code after retroactive landscape review.
>
> **Reason:** `MFE_ACCESSIBILITY_EARLIEST_KNOWABLE_SIGNAL_V1` (2026-05-27,
> verdict `STOP_SMC_RESEARCH_TRIAL_00095_ALREADY_OPTIMAL`) already measured
> all three M4-proposed confluence proxies plus 24 other knowable states on
> the same 145k-candle dataset:
>
> | M4 proxy | Existing equivalent state | k med | net 5b | PF | MFE consumed |
> |---|---|---:|---:|---:|---:|
> | P1_immediate_tfi_sign | `tfi_aligned_known` | 3 | -0.00096 | 0.680 | 0.55 |
> | P2_short_window_cvd_delta | `cvd_absorption_proxy_known` | 4 | -0.00082 | 0.728 | 0.68 |
> | P3_no_confluence | `raw_sweep_known` | 0 | -0.00061 | 0.758 | 0.34 |
>
> All three FAIL net expectancy after costs. Best PF in the entire 27-state
> table is 0.890 (`deep_sweep_threshold_known`, 3245 events) — still <1.
> M4 incremental value vs prior diagnostic estimated at ~10%.
>
> See `docs/research/RESEARCH_LANDSCAPE_RESET_2026-06-04.md` for the full
> landscape review and recommended next directions.
>
> **Codex action:** discard any plan-stub started for M4. Stand down on this
> milestone. Await new direction from operator.

---

# Original handoff content (retained for audit lineage)

Date: 2026-06-04
From: Claude Code (auditor)
To: Codex (builder)
Branch base: `deploy/multi-asset-paper-v1` @ `683d0ca`
Builder commit branch: `research/m4-confluence-gate-accessibility` (Codex creates if absent)

---

## CLAUDE HANDOFF -> CODEX

### Checkpoint

- Last commit: `683d0ca` (`research: reclaim_rejection diagnostic V1 re-run on canonical DB`)
- Branch base: `deploy/multi-asset-paper-v1`
- M3 audit: `docs/audits/AUDIT_M3_RECLAIM_REJECTION_DIAGNOSTIC_V1_2026-06-04.md`
  (commit `a701a92` on `claude/festive-maxwell-iciBo`)
- Working tree expected clean before start.

### Why this milestone

Two consecutive setup hypotheses have been falsified for the **same
structural reason**:

| Diagnostic | F-3 ratio | Consumed share | Outcome |
|---|---:|---:|---|
| `SMC_SEQUENCE_EDGE_FEASIBILITY_V1` | 2.35 | ~0.70 | HYPOTHESIS_INVALIDATED |
| `RECLAIM_REJECTION_DIAGNOSTIC_V1` | 1.23 | ~0.84 | HYPOTHESIS_INVALIDATED |

Both setups identify state-knowable triggers correctly. Both wait for
TFI/CVD confluence agreement. By the time confluence arrives, the majority
of the favorable excursion is gone. **The bottleneck is the confluence-gate
wait, not the trigger geometry.**

A third setup hypothesis built on the same confluence primitive will most
likely fail the same way. Before designing one, diagnose the gate itself.

### Before you code

Read (mandatory):

1. `docs/BLUEPRINT_RESEARCH_LAB.md`
2. `AGENTS.md` (your operating rules)
3. `docs/MILESTONE_TRACKER.md` (M4 entry under "Research Implementation Checkpoint - 2026-06-04")
4. `docs/audits/AUDIT_M3_RECLAIM_REJECTION_DIAGNOSTIC_V1_2026-06-04.md` (full M3 verdict + rationale)
5. `docs/QUANT_RESEARCH_OPERATING_MODEL.md`
6. `docs/research/RECLAIM_REJECTION_DIAGNOSTIC_V1_PLAN.md` (reuse timing model + falsification discipline)
7. `research_lab/diagnostics/reclaim_rejection_feasibility_v1.py` (reuse primitives: load_flow_15m, ATR, swing maps, deterministic event_id, json_ready, monthly_pnl, aligned_monthly_correlation, gate_result)

### Milestone: M4 CONFLUENCE_GATE_ACCESSIBILITY_DIAGNOSTIC_V1

**Research-only.** No production code, no settings, no schema, no SignalEngine,
no FeatureEngine, no Governance, no Risk, no execution changes.

**Commit split (mandatory, do not collapse):**

1. **Commit 1 — Plan document.** Single file:
   `docs/research/CONFLUENCE_GATE_ACCESSIBILITY_DIAGNOSTIC_V1_PLAN.md`.
   STATUS: `PLAN_READY_FOR_CLAUDE_AUDIT`. No code, no tests, no artifacts.
   STOP after this commit and wait for Claude audit + plan approval.
2. **Commit 2 — Implementation.** After plan approval, implement diagnostic +
   tests + run + artifacts in a single commit. STATUS:
   `READY_FOR_CLAUDE_AUDIT`. Do not self-audit.

### Research Questions

**Q1 — Wait-time distribution.** Per trigger family below, what is the
distribution of bars from `state_known_bar` to the first bar where TFI/CVD
confluence agreement holds?

Trigger families (reuse where possible):

- `sweep_only` — equal-level cluster sweep with `swept_at = idx` (analogous to
  reclaim_swing baseline in M3).
- `wick_rejection_at_extreme` — exact reuse of M3 primary candidate
  conditions (wick at confirmed swing extreme + state_known_bar = idx+1).
- `displacement` — large bar relative to ATR (e.g., body / ATR >= 1.5)
  at state_known_bar = idx+1; deterministic threshold, frozen pre-data.
- `reclaim_swing` — equal-cluster sweep + reclaim (event-study defaults), as
  built in M3 `build_reclaim_swing_baseline`.

For each family, compute the wait distribution. Report:
- counts at each integer wait length 0..N (where N is configurable, suggest 32);
- median, p25, p75, p90, p99 wait lengths;
- timeout fraction (no confluence found within the configured search window).

**Q2 — MFE-consumed-share as a function of wait.**

Definition (reuse M3 formula):

```
consumed_share(w) = median_over_events_with_wait_exactly_w(
    mfe_before_entry / (mfe_before_entry + mfe_post_entry_5bar)
)
```

`mfe_before_entry` uses the M3 definition: max favorable excursion from
`detection_close` across bars `[detection_bar+1, entry_candidate_bar]`.
`mfe_post_entry_5bar` uses M3 `forward_window_metrics(start_bar=return_start, bars=5)`.

Report `consumed_share(w)` per trigger family. Also report the
break-even wait length: largest `w` at which `consumed_share(w) <= 0.50`
(if any).

**Q3 — Candidate faster confluence proxies.**

Define and freeze (pre-data) AT LEAST 3 candidate faster proxies. Each must
include an **explicit lookahead-safety argument** in the plan document. Each
must be implementable using only data available no later than
`state_known_bar`. Suggested starting set (Codex may add or substitute):

- `P1_immediate_tfi_sign` — confluence holds iff TFI sign on the closed
  `state_known_bar` (already-closed candle, no future leak) matches the
  trigger direction. CVD ignored.
- `P2_short_window_cvd_delta` — confluence holds iff CVD delta over the
  last K seconds within `state_known_bar` (e.g., K=300s of the 900s 15m
  bar) matches the trigger direction. Must use only aggtrade rows that
  closed by `state_known_bar.close_time`.
- `P3_no_confluence` — null-gate control: every state-knowable trigger is
  immediately tradable at `state_known_bar + 1` open. Pure timing baseline.
- (Codex may add P4..PN.)

For each proxy, evaluate:
- effective wait length (often 0 for P1/P3, K-seconds-bounded for P2);
- MFE-consumed-share at that wait;
- **F-3 gate on at least one trigger family** (suggested:
  `wick_rejection_at_extreme` to allow direct comparison to M3 results);
- entry count vs M3 baseline (to flag throughput cost or false-positive
  inflation).

**Q4 — Joint verdict per proxy.** Per (proxy x trigger_family), report
PASS/FAIL on a reduced gate set:

| Rule | Threshold |
|---|---:|
| F-1' | net PF >= 1.5 |
| F-2' | median net return >= 0 |
| F-3' | median MFE_before / median MFE_post_5bar <= 0.70 |

F-4 / F-5 / F-6 are not required at the diagnostic stage; they apply when a
proxy graduates to a setup candidate.

### Forbidden Patterns (lifted from M3 plan, reaffirmed)

- Do not relax thresholds after seeing results.
- Do not add regime/session filters to rescue a result.
- Do not measure primary returns from `detection_bar`.
- Do not use future bars to declare a swing extreme or confluence state
  without carrying the confirmation delay into timing.
- Do not modify `core/signal_engine.py`, `core/feature_engine.py`,
  governance, risk, settings, schema, or dependency manifests.
- Do not introduce parameter optimization or grid search.
- Do not propose a new setup geometry hypothesis as part of M4.

### Deliverables

**Commit 1 — Plan only:**

- `docs/research/CONFLUENCE_GATE_ACCESSIBILITY_DIAGNOSTIC_V1_PLAN.md`
  with sections:
  1. Executive summary + scope guards.
  2. Why M4 is different from M3 / SMC (cite both invalidations).
  3. Repository inventory (primitives reused from M3 diagnostic).
  4. Trigger family specifications (frozen parameters).
  5. Confluence proxy specifications (frozen, with lookahead-safety
     argument per proxy).
  6. Measurement model (wait distribution, consumed_share, F-3 per proxy).
  7. Data + replay primitives (canonical DB only, hard-fail guard).
  8. Test plan (unit tests for wait calculation, proxy lookahead safety,
     deterministic SHA, etc.).
  9. Acceptance criteria for completion.
  10. Risk register.
  11. Open questions for operator (if any).

**Commit 2 — Implementation:**

- `research_lab/diagnostics/confluence_gate_accessibility_v1.py` —
  diagnostic module. Reuse `load_flow_15m`, ATR, swing maps, deterministic
  helpers from M3 module via import (do not duplicate). New helpers go in
  this file.
- `tests/test_confluence_gate_accessibility_v1.py` — unit tests covering
  every named test from plan Section 8 + lookahead-safety regression per
  proxy.
- `research_lab/analysis_output/confluence_gate_accessibility_v1.json` —
  deterministic JSON output.
- `research_lab/analysis_output/confluence_gate_accessibility_v1.sha256`.
- `research_lab/analysis_output/confluence_gate_accessibility_v1_report.md`.

### Database (mandatory)

Canonical DB only:
`research_lab/data/crowded_unwind_backtest.db` (operator pendrive).

Pre-run sanity (must match exactly):
- `aggtrade_buckets` non-null cvd count: `3,122,272`
- `cvd_price_history` row count: `0`
- BTCUSDT 15m row SHA256 (window `2022-01-01..2026-03-01`):
  `F6BD821E4C829B0B7259B6F0F442607FA213A2D66BCB4D201E6EDCBF07FA79DC`
  (inclusive end, 145,921 rows)

If sanity check fails, STOP — escalate to operator.

Hard-fail guard from M3 (`resolve_default_db`) must be respected. No
`--allow-fallback` in production research run.

### Known Issues from M3 audit (for awareness, not in M4 scope)

| # | Issue | In M4 scope? |
|---|---|---|
| 1 | `level_scanner` provenance is decorative for reclaim_rejection | NO — informational; do not bake into M4 design |
| 2 | F-6 PASS is informationally weak when no detection-bar edge exists | NO — M4 does not re-evaluate F-6 |
| 3 | Baseline timing model differs from primary in M3 | NO — M4 may set its own baseline if needed |
| 4 | `mfe_before_entry` uses `detection_close` reference price | NO — keep same formula for cross-comparability with M3 |

### Your first response must contain

1. Confirmed milestone scope (what you will implement in commit 1 vs 2).
2. Acceptance criteria you propose (may extend Claude's; cannot weaken).
3. Which known issues are in-scope vs out-of-scope (with reasoning).
4. Plan implementation outline (ordered steps to produce commit 1).
5. Pre-run sanity confirmation plan for commit 2.
6. Only then: start drafting the plan document.

### Commit discipline

- Single plan file in commit 1. WHAT / WHY / STATUS = `PLAN_READY_FOR_CLAUDE_AUDIT`.
- After audit approval, single implementation commit. WHAT / WHY / STATUS =
  `READY_FOR_CLAUDE_AUDIT`.
- Do NOT self-mark as "done". Claude Code audits after push.
- Do NOT include model identifier strings or tool-related metadata in
  commit messages.

### Time budget guidance

- Plan draft: 2-4 hours.
- Plan audit + revisions: 2-4 hours.
- Implementation + tests + run + artifacts: 12-20 hours.
- Implementation audit: 4-8 hours.

Total milestone budget: roughly 20-36 hours from start to verdict.

---

## End of handoff.
