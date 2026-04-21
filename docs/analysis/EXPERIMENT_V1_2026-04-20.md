# Experiment V1 — Throughput Validation (2026-04-20)

## Goal

Increase paper-runtime throughput from `detected setup -> executable signal -> opened trade` without changing the research baseline or claiming that the edge is already proven.

This experiment is intentionally about **opportunity flow**, not final profitability.

## Classification

Current problem type:

- implementation / gating issue, not proven edge failure
- filtering / opportunity-loss issue, not exchange-fill issue
- live-vs-research mismatch, not infrastructure failure

Operator shorthand:

- if `signal_candidates` stay near zero, the bottleneck is still in `signal_engine`
- if `signal_candidates` rise but `executable_signals` stay low, the bottleneck is governance
- if `executable_signals` rise but `trade_log` stays low, the bottleneck is risk or execution
- if trades appear and execution is normal but PnL remains weak, only then does edge/setup quality become the primary question

## Experiment Profile

Runtime profile name: `experiment`

This profile is PAPER-only and leaves `research` untouched.

### Signal relaxations

- `confluence_min`: `4.5 -> 3.6`
- `direction_tfi_threshold`: `0.08 -> 0.05`
- `direction_tfi_threshold_inverse`: `-0.05 -> -0.03`
- `tfi_impulse_threshold`: `0.13 -> 0.10`
- `crowded_leverage` whitelist: `SHORT-only -> LONG/SHORT`

### Governance / risk relaxations

- `min_rr`: `2.1 -> 1.6`
- `max_open_positions`: `1 -> 2`
- `max_trades_per_day`: `3 -> 6`
- `cooldown_minutes_after_loss`: `95 -> 30`
- `duplicate_level_tolerance_pct`: `0.0007 -> 0.0004`
- `duplicate_level_window_hours`: `114 -> 24`

## Why These Changes

These changes target the reported funnel failures directly:

- `direction_unresolved`: lower TFI thresholds should let more setups resolve direction
- `regime_direction_whitelist`: `crowded_leverage` no longer blocks LONG by policy alone
- late governance / risk vetoes: lower `min_rr`, shorter cooldown, wider daily throughput caps

## Deliberately Out Of Scope

Not included in Experiment V1:

- time-of-day logic
- regime redesign
- uptrend-pullback promotion
- research-lab parameter promotion
- execution-engine redesign

Reason: those changes would mix throughput debugging with methodology redesign.

## Success Criteria

Minimum evidence target:

- paper runtime produces materially more `signal_candidates`
- reclaim execution rate is no longer near zero
- opened-trade frequency improves from "one trade every few days" to a usable sample rate

Suggested operating targets:

- `1-2` opened trades per day in paper
- `30-50%` reclaim execution rate
- top rejection reasons shift away from `direction_unresolved` / `regime_direction_whitelist`

## Run Command

Paper experiment:

```bash
set BOT_SETTINGS_PROFILE=experiment
python scripts/run_paper.py
```

Direct entrypoint alternative:

```bash
python main.py --mode PAPER --settings-profile experiment
```

## Stop Conditions

Stop and reassess if:

- `signal_candidates` remain near zero despite the relaxed profile
- trades appear but almost all fail immediately with poor structure
- rejection mix simply moves from signal gates to a new single dominant veto reason

That outcome would mean the next problem is no longer throughput. It would be setup quality or edge quality.

---

## Conclusion (2026-04-21)

**Status:** EXPERIMENT VALIDATED — Hypothesis confirmed

**Decision:** Proceed with roadmap implementation (DATA-INTEGRITY-V1 → MODELING-V1)

**Key findings:**
- Filter relaxation demonstrated measurable throughput improvement
- Hypothesis validated: opportunity loss was primarily gating-related, not edge-related
- Data quality was not perfect during experiment, but sufficient to prove the core hypothesis

**Important notes:**
- Experiment was conducted on imperfect data (acknowledged limitation)
- Results provide sufficient evidence to justify continuing planned roadmap
- DATA-INTEGRITY-V1 remains prerequisite before MODELING-V1 (no change to dependency order)
- Experiment profile remains PAPER-only (no promotion to live)

**Next steps:**
1. Continue DATA-INTEGRITY-V1 implementation (already in progress)
2. After DATA-INTEGRITY-V1 completes: begin MODELING-V1
3. MODELING-V1 will add session-aware and volatility-aware context layer on validated data foundation
