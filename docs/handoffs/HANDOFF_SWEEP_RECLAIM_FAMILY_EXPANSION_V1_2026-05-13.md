# HANDOFF: SWEEP-RECLAIM-FAMILY-EXPANSION-V1

## CLAUDE HANDOFF -> CODEX

### Checkpoint
- Last commit: `b8a2bd7` (`docs: strategic 15m portfolio closure and sweep family pivot`)
- Branch: `main`
- Working tree: clean (strategic docs pushed)

### Before you code
Read these files (mandatory):
1. Relevant blueprints:
   - `docs/BLUEPRINT_V1.md` - bot/runtime architecture
   - `docs/BLUEPRINT_RESEARCH_LAB.md` - research lab architecture and workflow
2. `AGENTS.md` - discipline + your workflow rules
3. `docs/MILESTONE_TRACKER.md` - current status + known issues
4. `docs/analysis/STRATEGIC_15M_PORTFOLIO_ASSESSMENT_2026-05-13.md` - strategic context (15m portfolio closure, pivot rationale)
5. `docs/DECISIONS_LOG.md` - decision record (2026-05-13 entry)
6. `research_lab/optuna_campaigns/` - trial-00095 baseline params for independence analysis

### Strategic Context: Proven Edge Expansion

**Why this milestone:**

15m multi-setup portfolio research conclusively failed (6 families, 0% success). Pattern: timing incompatibility (event timescale, detection latency) OR edge absence. Only sweep_reclaim works at 15m because:
- State-independent logic (no regime phase timing needed)
- Mean-reversion edge (not momentum-following)
- Edge persists 15-60 min (compatible with 15m latency)
- Objective measurable signals

**Strategic pivot:**
- Close 15m multi-setup portfolio research (NOT VIABLE)
- Expand proven edge (trial-00095 ER 2.1, PF 4.6, PAPER live) through structure context variations
- Known edge expansion (lower risk) vs new unknown edges (0% success in 6 families)
- No new independent setup families at 15m without architectural decision

### Milestone: SWEEP-RECLAIM-FAMILY-EXPANSION-V1

**Scope:** Expand sweep_reclaim edge through structure context variations. Start with Range Sweep Specialist variant.

**Blueprint reference:** Section 3.2 (Signal Engine), Section 4 (Regime Engine - for context filters), research lab validation protocol

### Variant 1: Range Sweep Specialist

**Hypothesis:**

Liquidity sweeps in range-bound markets (normal regime, horizontal structure context) have highest mean-reversion probability due to:
1. Tighter structure boundaries → clearer sweep invalidation levels
2. No directional bias → mean reversion dominates over trend continuation
3. Horizontal support/resistance → liquidity pools more predictable
4. Lower volatility environment → stop hunts more precise

**Entry conditions (MUST differ from trial-00095):**

**Core logic (inherited from sweep_reclaim):**
- Liquidity sweep detected (sweep side, premium distance, reclaim confirmation)
- TFI alignment (forced positioning pressure supports mean reversion)
- Flow confirmation (order flow supports reversal)

**NEW filters (what makes this variant independent):**

1. **Regime filter:** `normal` only (NOT uptrend, NOT downtrend, NOT compression, NOT post_liquidation)
   - trial-00095 operates across all regimes (regime-agnostic)
   - Range Sweep Specialist requires `normal` regime explicitly

2. **Structure filter:** Horizontal structure context only
   - Measure: Rolling structure slope over N cycles (e.g., 96 cycles = 24h)
   - Threshold: `abs(structure_slope_atr)` < X (e.g., 0.3 ATR per 24h)
   - Interpretation: Horizontal → range-bound, steep slope → trending (filtered out)

3. **Volatility filter (optional refinement):** ATR percentile < Y (e.g., 60th percentile)
   - Rationale: Lower volatility environments = tighter ranges = higher reversion probability

**Independence measurement (CRITICAL):**

After Checkpoint 1 backtest, measure overlap with trial-00095:
- Extract trial-00095 trade timestamps from research_lab.db
- Count how many Range Sweep Specialist trades overlap with trial-00095 trades (same timestamp)
- Calculate overlap rate: `overlap_trades / total_range_sweep_trades`
- **GATE:** Overlap must be < 30% to prove independence

If overlap >= 30%: Variant is NOT independent, tighten filters (more restrictive regime/structure/volatility conditions).

**Validation gates (same as other research setups):**

- ER > 1.5 (hard gate)
- Min trades >= 20
- Walk-forward 2/2 pass (only if Checkpoint 1 passes)
- No blocking safety flags
- PF > 2.5 (institutional quality)
- Win rate >= 50% (consistency)

**Exit logic:**

Same as trial-00095 baseline:
- TP: Premium reclaim + distance buffer
- SL: Sweep invalidation (structure break)
- Trailing stop: Optional based on flow confirmation strength

### Deliverables

**Checkpoint 1 (backtest validation):**

1. **Setup implementation:**
   - `research_lab/setups/range_sweep_specialist.py`
   - Config dataclass with parameters: regime_filter, structure_slope_threshold, volatility_percentile_max, etc.
   - Entry logic: regime check + structure slope check + volatility check + sweep/reclaim/TFI/flow (inherited)
   - Exit logic: same as trial-00095
   - `reasons[]`: Log regime, structure_slope, volatility_percentile, sweep/reclaim/TFI/flow

2. **Integration:**
   - Add Range Sweep Specialist to research lab runner
   - Configure as independent candidate (NOT modifying trial-00095)

3. **Backtest execution:**
   - Full replay: 2022-01-01 to 2026-03-29 (same window as other research setups)
   - Generate validation report: `research_lab/reports/range_sweep_specialist_validation_report.md`

4. **Audit package:**
   - `research_lab/reports/RANGE_SWEEP_SPECIALIST_AUDIT_PACKAGE.md`
   - Include: Metrics (ER, PF, trades, win rate, etc.), independence analysis (overlap rate with trial-00095), regime/structure distribution, per-direction/per-regime breakdown, safety flags
   - **Independence proof:** Overlap rate < 30% gate

5. **Tests:**
   - Unit tests: regime filter, structure slope calculation, volatility filter
   - Integration test: End-to-end entry logic

**Target files:**
- `research_lab/setups/range_sweep_specialist.py` (new)
- `research_lab/reports/range_sweep_specialist_validation_report.md` (new)
- `research_lab/reports/RANGE_SWEEP_SPECIALIST_AUDIT_PACKAGE.md` (new)
- `tests/research_lab/test_range_sweep_specialist.py` (new)

### Implementation Plan (Required in Your First Response)

**Your first response must contain:**

1. **Confirmed milestone scope:** What you will implement
2. **Acceptance criteria:** How we know Checkpoint 1 is done
3. **Independence strategy:** How you will measure overlap with trial-00095 (specific method)
4. **Structure slope calculation:** Rolling window size, ATR normalization method, threshold
5. **Volatility filter details:** Percentile calculation, window, threshold
6. **Implementation plan:** Ordered steps (setup → integration → backtest → independence analysis → audit package)
7. Only then: start coding

### Known Issues (from strategic assessment)

| # | Issue | Blocking for this milestone? |
|---|---|---|
| 1 | trial-00095 trades ~2-5/month (low frequency) | NO - family expansion goal is trade frequency increase |
| 2 | 15m multi-setup portfolio failed 6/6 families | NO - this is family expansion (proven edge), not new setup |
| 3 | No regime definition for `post_liquidation` aftermath | NO - Range Sweep Specialist uses `normal` regime only |
| 4 | CVD not predictive (absorption_continuation finding) | NO - sweep_reclaim doesn't rely on CVD prediction |
| 5 | Event timescale incompatibility for cascades | NO - sweep_reclaim is state-independent, not cascade-dependent |

**Assessment:** No blocking issues for Range Sweep Specialist. Known issues apply to failed setups or infrastructure gaps outside this scope.

### Success Scenario (Checkpoint 1)

**If ER > 1.5, overlap < 30%, min trades >= 20, no safety flags:**
- Verdict: CANDIDATE
- Next: Walk-forward validation (Window 1: 2024-01-01 to 2025-12-31, Window 2: 2025-01-01 to 2026-03-29)
- If WF 2/2 pass: Ready for promotion audit (research-to-production integration)

**If ER < 1.5 OR overlap >= 30%:**
- Verdict: REJECT or ITERATE (depending on specific issue)
- If overlap too high: Tighten filters (more restrictive regime/structure conditions)
- If ER weak: Hypothesis failed for range context, move to Variant 2 (Trend Sweep Specialist)

### Failure Scenario (Checkpoint 1)

**If ER < 1.0 (hard stop):**
- Verdict: HYPOTHESIS FAILED
- Next: Move immediately to Variant 2 (Trend Sweep Specialist) - test opposite hypothesis (sweeps in trending markets)

**If overlap >= 50% (severe dependence):**
- Verdict: NOT INDEPENDENT
- Next: Re-evaluate filter design OR move to Variant 2 if filters can't reduce overlap

**If sample < 20 trades:**
- Verdict: INSUFFICIENT_SAMPLE
- Next: Relax filters slightly OR defer variant (structure context too rare)

### Exit Criteria for Family Expansion

**After 3 variants tested:**
- If 0-1 variants succeed (meet ER > 1.5, overlap < 30%): Family expansion saturated, pivot to 5m frequency assessment
- If overlap across variants > 50%: Variants not independent, family expansion not viable

**After 6 months (or when trial-00095 live performance available):**
- If trial-00095 live ER < 1.0: Edge degrading, strategic reassessment
- If trial-00095 live ER >= 1.5: Edge confirmed, continue family expansion

**Hard stop (anytime):**
- If 3 consecutive variants fail ER > 1.5 gate: Family expansion not viable, strategic reassessment

### Timeline

- Checkpoint 1 (backtest validation): 2-3 weeks
- Walk-forward validation (if Checkpoint 1 passes): 1 week
- Promotion audit (if WF passes): 1 week
- Total per variant: 4-5 weeks

**Fast failure discipline:** If Checkpoint 1 fails hard stop (ER < 1.0), move to next variant immediately (no iteration).

### Institutional Character Preservation

**Liquidity-centric edge:**
- Sweep → mean reversion (forced positioning reversal)
- Structure-aware entry (range boundaries, sweep invalidation)

**Measurable counterparty pressure:**
- TFI (forced positioning via funding)
- Sweep confirmation (liquidity absorption)
- Flow alignment (order flow supports reversal)

**Market structure discipline:**
- Regime context (normal = range-bound)
- Structure context (horizontal boundaries)
- Volatility context (lower volatility = tighter ranges)

**Hard validation gates:**
- ER > 1.5, WF 2/2, overlap < 30%, no safety flags

**Deterministic audit trail:**
- `reasons[]`: regime, structure_slope, volatility_percentile, sweep/reclaim/TFI/flow
- Governance logs: Entry/exit decisions with context
- Reproducible: Same params + same data = same trades

### Commit Discipline

- WHAT / WHY / STATUS in every commit message
- Do NOT self-mark as "done" - Claude Code audits after push
- Research branch: `research/sweep-family-expansion-v1`
- Push to research branch when Checkpoint 1 complete

### Next Steps After This Milestone

**If Range Sweep Specialist succeeds (ER > 1.5, overlap < 30%, WF 2/2):**
- Variant 2: Trend Sweep Specialist (uptrend/downtrend regime, trending structure)
- Hypothesis: Sweeps in trending markets have edge when trend exhaustion + sweep coincide

**If Range Sweep Specialist fails (ER < 1.5):**
- Variant 2: Trend Sweep Specialist (test opposite hypothesis)

**If family expansion saturates (3 variants, 0-1 success):**
- Strategic reassessment: 5m frequency upgrade feasibility

### Questions for Clarification (If Needed)

Before starting implementation, confirm:
1. Structure slope calculation method (rolling regression? ATR-per-hour? Other?)
2. Volatility percentile window (24h? 7d? 30d?)
3. Should volatility filter be mandatory or optional refinement for iteration?
4. Independence analysis: Exact timestamp match or same 15m cycle?

If any parameters need clarification, ask before implementing. Otherwise, proceed with reasonable defaults and document assumptions in code comments.

---

**Critical Success Factors:**

1. **Independence proof:** Overlap < 30% with trial-00095 (measured, not assumed)
2. **Regime filter enforced:** `normal` only (no exceptions)
3. **Structure context measurable:** Slope calculation deterministic, reproducible
4. **Edge validation:** ER > 1.5 (hard gate, no excuses)
5. **Fast failure discipline:** If hard stop triggered, move to next variant immediately

**Remember:** This is proven edge expansion, not new setup discovery. trial-00095 works (ER 2.1, live). Your job: Find structure contexts where sweep_reclaim edge is STRONGER or MORE FREQUENT, not discover new edges.

Good luck. Claude Code audits when you push.
