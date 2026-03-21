# BTC Bot Development Operating System

This repository is developed as a production trading system.

## Commit/Push Discipline
- Commit only at meaningful checkpoints:
- after completing a blueprint phase (A, B, C, D, ...)
- after finishing a coherent component (for example execution engine or state persistence)
- after smoke tests or validation pass
- Never commit:
- incomplete logic fragments
- unvalidated code
- random/context-free edits
- Every commit must include:
- WHAT: what was implemented
- WHY: why this change was made
- STATUS: what is done and what is still pending
- Keep history clean and actionable; each commit must be a reliable rollback point.

## Execution Discipline
- Never mix layers:
- data != feature != regime != signal != governance != risk != execution != storage
- Any layer-separation violation must be explicitly justified.
- No hidden side effects:
- functions must be deterministic unless explicitly marked as stateful
- No implicit data mutation across modules.

## Deterministic Core
- Core decision pipeline must be deterministic:
- MarketSnapshot -> Features -> Regime -> SignalCandidate -> Governance -> ExecutableSignal
- No randomness allowed in:
- feature_engine
- regime_engine
- signal_engine
- governance
- risk_engine
- Any stochastic or ML logic must be:
- isolated
- explicitly flagged
- never used in core decision path without explicit approval

## Data Integrity
- All timestamps must be UTC and explicitly normalized.
- No mixing of timeframes without explicit alignment logic.
- Bucketing logic must be deterministic and reproducible.
- Never silently drop data.
- Missing data must be logged and handled explicitly.

## State & Recovery
- Bot state must be recoverable after restart.
- No critical runtime state only in memory.
- All limits must be derived from persistent state:
- daily DD
- weekly DD
- consecutive losses
- trades per day
- Recovery must be idempotent and safe to run multiple times.

## Validation Discipline
- Every major component must have:
- smoke test
- deterministic check
- No commit without:
- compileall passing
- basic runtime validation
- Feature calculations must be independently testable and reproducible with fixed input.

## Signal Quality Rules
- SignalCandidate must:
- include explicit reasons[]
- include confluence_score
- be explainable
- No black-box signals.
- Every signal must be traceable to:
- features
- regime
- specific conditions
- If a signal cannot be explained, it is invalid.

## Risk & Governance Authority
- Governance can veto signal.
- Risk engine can veto execution.
- Signal engine cannot force execution.
- Priority:
- signal < governance < risk
- If any layer rejects, trade is not executed.

## Module Contracts
- Each module must:
- expose clear input/output types
- avoid dependency on internals of other modules
- communicate via models in core/models.py
- No cross-import shortcuts.

## Implementation Strategy
- Build in phases:
- A -> B -> C -> D -> E -> F -> G -> H
- Do not skip phases.
- Do not partially implement future phases.
- Each phase must be:
- complete
- validated
- committed before moving forward

## LLM Usage Policy
- LLM is allowed only for:
- research
- post-trade analysis
- reporting
- LLM is not allowed in:
- execution path
- real-time decision loop
- Any future AI integration must be:
- offline
- auditable
- non-blocking

## Debugging Protocol
- When a bug occurs:
- 1) assume data issue first
- 2) then feature calculation
- 3) then logic error
- 4) only then external dependencies
- Never patch blindly; always trace root cause.

## Performance Awareness
- Avoid unnecessary API calls.
- Prefer batching and caching.
- Prefer WS over REST for live data.
- Keep computations efficient for real-time usage.

## System Philosophy
This is not a script. This is a trading system.

- Every decision must be explainable.
- Every action must be auditable.
- Every failure must be recoverable.

Clarity > cleverness
Stability > speed
Discipline > complexity
