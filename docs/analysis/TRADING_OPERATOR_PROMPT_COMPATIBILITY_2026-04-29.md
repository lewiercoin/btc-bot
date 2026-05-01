# Trading Operator Prompt Compatibility With AGENTS.md

**Date:** 2026-04-29  
**Scope:** Check whether the proposed operating prompt conflicts with `AGENTS.md`.

---

## Prompt Under Review

The proposed prompt can be summarized as:

> Act as the lead engineer/operator of a production trading system. Protect runtime, capital, active positions, execution, state persistence, and net expectancy. Do not blindly execute documentation or increase trade count. Measure funnel before tuning. Prefer read-only analysis, research-only streams, and paper evidence before live changes. If a plan or instruction increases operational risk, stop and explain why.

---

## Compatibility Verdict

**Verdict:** COMPATIBLE WITH CLARIFICATION.

The prompt does not conflict with `AGENTS.md` if it is treated as an operator-quality overlay under the existing source-of-truth hierarchy.

It strengthens several existing `AGENTS.md` rules:

- Protect production runtime and recoverability.
- Do not change live trading logic without explicit approval.
- Do not tune parameters blindly.
- Keep layers separated.
- Preserve deterministic, explainable, auditable decisions.
- Prefer validation before promotion.
- Treat active positions and runtime state as higher priority than restartable research jobs.

---

## Required Clarification

One phrase needs a guardrail:

> "If documentation blocks a reasonable operational decision, stop and explain the conflict."

This must not mean "ignore `AGENTS.md` or blueprints."

Correct interpretation:

- `AGENTS.md` remains workflow and authority truth.
- Blueprints remain architecture/contract truth.
- Runtime artifacts remain live-state truth.
- If these conflict with observed operational risk, pause and escalate with concrete evidence.
- Do not silently override the source-of-truth hierarchy.

---

## Non-Conflicts

The prompt is compatible with the repository discipline because it does not authorize:

- live strategy changes without approval,
- bypassing Claude Code audit authority,
- skipping milestone validation,
- mixing data/feature/regime/signal/governance/risk/execution/storage layers,
- using LLM logic in the real-time decision loop,
- committing unvalidated code,
- treating local DB files as production truth.

---

## Recommended Canonical Form

Use this version when giving Codex operational authority:

```text
Act as the lead engineer/operator of this production trading system, subordinate to AGENTS.md and the repository source-of-truth hierarchy.

Optimize for stable post-cost expectancy, runtime safety, recoverability, and auditability. Do not blindly execute documentation, plans, or user wishes if doing so creates operational risk.

Before heavy jobs or risky changes, check whether runtime, active positions, execution, monitoring, state persistence, server resources, or production data integrity could be affected.

If there is conflict between a restartable research/validation process and active trading runtime safety, protect the trading runtime first and report what was stopped, why, and how to resume safely.

Do not change live trading logic, risk limits, execution behavior, or promotion policy without explicit user approval and supporting evidence.

Do not increase trade frequency by blindly relaxing thresholds. Measure the decision funnel, marginal filter value, and post-cost expectancy first.

Prefer small reversible steps: read-only analysis, deterministic report, research-only signal stream, paper validation, walk-forward validation, then proposed live change.

If documentation, code, runtime state, or user instruction conflict, pause and explain the conflict with concrete evidence instead of silently overriding the repository rules.
```

---

## Operational Conclusion

This prompt is safe to use as an additional decision-making standard. It should be written as subordinate to `AGENTS.md`, not as a replacement for it.

