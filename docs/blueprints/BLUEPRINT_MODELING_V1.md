# BLUEPRINT_MODELING_V1

**Status:** final blueprint, post independent audit synthesis and Codex contract cleanup  
**Date:** 2026-04-21  
**Supersedes:** `docs/blueprints/BLUEPRINT_MODELING_V1_SYNTHESIS.md`  
**Roadmap position:** after `DATA-INTEGRITY-V1`, before `EXECUTION-REALISM-V1` and `OPTUNA-RECALIBRATION-V1`

---

## 0. How this document was produced

This blueprint is the result of independent architectural audit rounds by
Perplexity, Cascade, Codex, and Claude. The final version incorporates the
builder-facing contract corrections from the audit cycle:

1. `SessionBucket` uses 4 deterministic UTC hour buckets.
2. Empirical activation requires both win-rate delta and statistical support.
3. `ContextConfig` uses an explicit session/volatility whitelist.
4. Runtime config updates are forbidden.
5. `ContextEngine.classify()` is the only context entrypoint.
6. Context-block persistence is explicit.
7. Context fields are dedicated `decision_outcomes` columns.
8. `DATA-INTEGRITY-V1` remains a hard prerequisite.
9. Neutral mode requires exact candidate parity.
10. Reclaim edge helper functions are explicitly protected.

This is the canonical architectural reference for the builder handoff. The
handoff must be derived from this document, not from the older synthesis.

---

## 1. Purpose and scope

### What MODELING-V1 solves

The system already has a working reclaim edge. MODELING-V1 does not invent a
new edge. It adds a deterministic, auditable context eligibility layer over the
existing edge.

MODELING-V1 answers one question:

> In which session/volatility contexts should the existing reclaim edge be
> allowed, and in which should it be blocked?

This is a contextual eligibility milestone, not an alpha generation milestone.

### What MODELING-V1 does not solve

- reclaim detection redesign
- new external data sources
- position sizing or leverage changes
- runtime ML or LLM
- polluted diagnostic bucket cleanup
- execution realism
- Optuna or parameter search
- quality-aware context gating

---

## 2. Prerequisite: empirical validation before activation

Empirical validation is required before activating non-neutral eligibility
rules, but it does not block implementation of the context layer. The first
deployment state is `neutral_mode=True`, where context is classified and logged
but never blocks.

### Session win-rate analysis

```sql
SELECT
    CASE
        WHEN CAST(strftime('%H', opened_at) AS INT) >= 22
          OR CAST(strftime('%H', opened_at) AS INT) < 7  THEN 'ASIA'
        WHEN CAST(strftime('%H', opened_at) AS INT) >= 7
         AND CAST(strftime('%H', opened_at) AS INT) < 14 THEN 'EU'
        WHEN CAST(strftime('%H', opened_at) AS INT) >= 14
         AND CAST(strftime('%H', opened_at) AS INT) < 16 THEN 'EU_US'
        ELSE 'US'
    END AS session,
    COUNT(*) AS trades,
    ROUND(
        AVG(CASE WHEN pnl_r > 0 THEN 1.0 ELSE 0.0 END) * 100, 1
    ) AS win_rate_pct,
    SUM(CASE WHEN pnl_r > 0 THEN 1 ELSE 0 END) AS wins,
    SUM(CASE WHEN pnl_r <= 0 THEN 1 ELSE 0 END) AS losses
FROM trade_log
GROUP BY session
ORDER BY session;
```

### Activation criteria

Both criteria must be met before session gating may be activated:

```python
from scipy.stats import chi2_contingency

table = [
    [asia_wins, asia_losses],
    [eu_wins, eu_losses],
    [eu_us_wins, eu_us_losses],
    [us_wins, us_losses],
]
chi2, p_value, dof, expected = chi2_contingency(table)

win_rate_delta = max(win_rates) - min(win_rates)
activate_session_gating = (win_rate_delta >= 10.0) and (p_value < 0.05)
```

If only one criterion is met, `neutral_mode=True` remains active and the
operator documents the result in
`docs/analysis/MODELING_V1_VALIDATION_<date>.md`.

The same procedure applies to volatility gating, using ATR bucket membership
instead of session bucket membership.

Important: empirical validation is an offline analysis step. It must not add
SciPy or any other statistical dependency to the runtime decision path.

---

## 3. Architecture: one decision, no variants

Selected pipeline:

```text
MarketSnapshot
  -> FeatureEngine.compute(snapshot)                         -> Features
  -> RegimeEngine.classify(features)                          -> RegimeState
  -> ContextEngine.classify(features)                         -> MarketContext
  -> SignalEngine.diagnose(features, regime, context)         -> SignalDiagnostics
  -> SignalEngine.generate(features, regime, diagnostics, context)
                                                              -> SignalCandidate | None
  -> GovernanceLayer.evaluate(candidate)                      -> GovernanceDecision
  -> RiskEngine.evaluate(executable)                          -> RiskDecision
  -> Execution
```

### What ContextEngine is

`ContextEngine` is a stateless deterministic context eligibility classifier. It
classifies session and volatility from `Features`, checks the result against
`ContextConfig.session_volatility_whitelist`, and returns `MarketContext`.

It is not a governance layer and not a signal generator, but it does compute
context eligibility. That is its explicit and sole purpose.

### Why not the other options

**Do not extend RegimeEngine.** `RegimeEngine` owns market-structure
classification. Session and volatility context are orthogonal dimensions and
would create combinatorial regime bloat if folded into `RegimeState`.

**Do not hide context helpers inside SignalEngine.** `SignalEngine` owns the
reclaim edge. Burying session/volatility policy inside it would create hidden
coupling between context policy and edge logic.

**Do not add a post-candidate gate.** A post-candidate context veto would look
like a shadow governance layer and would reduce observability of base edge
presence.

---

## 4. Frozen contracts

### 4.1 SessionBucket

```python
class SessionBucket(str, Enum):
    ASIA = "ASIA"    # 22:00-06:59 UTC  (hour >= 22 or hour < 7)
    EU = "EU"        # 07:00-13:59 UTC  (7 <= hour < 14)
    EU_US = "EU_US"  # 14:00-15:59 UTC  (14 <= hour < 16)
    US = "US"        # 16:00-21:59 UTC  (16 <= hour < 22)
```

V1 uses UTC hour boundaries only. Minute-precision session splits are deferred
until data justifies the extra complexity.

### 4.2 VolatilityBucket

```python
class VolatilityBucket(str, Enum):
    LOW = "LOW"        # atr_4h_norm < atr_low_threshold
    NORMAL = "NORMAL"  # atr_low_threshold <= atr_4h_norm <= atr_high_threshold
    HIGH = "HIGH"      # atr_4h_norm > atr_high_threshold
```

Source: `features.atr_4h_norm` directly. It is not read through
`RegimeEngine`. Thresholds are `ContextConfig` parameters, not hardcoded
strategy thresholds.

### 4.3 ContextConfig

```python
@dataclass(frozen=True)
class ContextConfig:
    atr_low_threshold: float = 0.002
    atr_high_threshold: float = 0.004

    session_volatility_whitelist: dict[
        SessionBucket, tuple[VolatilityBucket, ...]
    ] = field(
        default_factory=lambda: {
            SessionBucket.ASIA: (
                VolatilityBucket.LOW,
                VolatilityBucket.NORMAL,
                VolatilityBucket.HIGH,
            ),
            SessionBucket.EU: (
                VolatilityBucket.LOW,
                VolatilityBucket.NORMAL,
                VolatilityBucket.HIGH,
            ),
            SessionBucket.EU_US: (
                VolatilityBucket.LOW,
                VolatilityBucket.NORMAL,
                VolatilityBucket.HIGH,
            ),
            SessionBucket.US: (
                VolatilityBucket.LOW,
                VolatilityBucket.NORMAL,
                VolatilityBucket.HIGH,
            ),
        }
    )

    neutral_mode: bool = True
    policy_version: str = "v1.0.0"
```

Default whitelist values are fully permissive. Non-permissive whitelist values
are allowed only after Section 2 validation is completed and documented.

`ContextConfig` is immutable deployment-time configuration. Runtime updates to
thresholds or whitelist entries are forbidden.

### 4.4 MarketContext

```python
@dataclass(slots=True, frozen=True)
class MarketContext:
    session_bucket: SessionBucket
    volatility_bucket: VolatilityBucket
    context_eligible: bool
    context_block_reason: str | None
    context_policy_version: str
    neutral_mode_active: bool
    quality_flags: tuple[str, ...] = ()
```

Rules:

- `context_eligible` is never `None` in MODELING-V1.
- When `neutral_mode=True`, `context_eligible=True` and
  `context_block_reason=None`.
- `quality_flags` is always an empty tuple in V1.
- Quality-aware context gating is deferred to a future milestone.

### 4.5 ContextEngine

```python
@dataclass(slots=True)
class ContextEngine:
    config: ContextConfig

    def classify(self, features: Features) -> MarketContext:
        """
        Stateless deterministic context eligibility classifier.
        Same features + same config -> same MarketContext.
        Does not receive RegimeState.
        """
        session = self._classify_session(features.timestamp)
        volatility = self._classify_volatility(features.atr_4h_norm)

        if self.config.neutral_mode:
            return MarketContext(
                session_bucket=session,
                volatility_bucket=volatility,
                context_eligible=True,
                context_block_reason=None,
                context_policy_version=self.config.policy_version,
                neutral_mode_active=True,
            )

        allowed = self.config.session_volatility_whitelist.get(session, ())
        eligible = volatility in allowed
        reason = None if eligible else (
            f"context_unfavorable:{session.value}:{volatility.value}"
        )

        return MarketContext(
            session_bucket=session,
            volatility_bucket=volatility,
            context_eligible=eligible,
            context_block_reason=reason,
            context_policy_version=self.config.policy_version,
            neutral_mode_active=False,
        )

    def _classify_session(self, timestamp: datetime) -> SessionBucket:
        h = timestamp.hour  # UTC required
        if h >= 22 or h < 7:
            return SessionBucket.ASIA
        if 7 <= h < 14:
            return SessionBucket.EU
        if 14 <= h < 16:
            return SessionBucket.EU_US
        return SessionBucket.US

    def _classify_volatility(self, atr_norm: float) -> VolatilityBucket:
        if atr_norm < self.config.atr_low_threshold:
            return VolatilityBucket.LOW
        if atr_norm > self.config.atr_high_threshold:
            return VolatilityBucket.HIGH
        return VolatilityBucket.NORMAL
```

### 4.6 SignalDiagnostics extension

The existing `blocked_by` field remains the owner of signal-level rejection
reasons such as `no_sweep`, `no_reclaim`, and `confluence_below_min`.

Add these fields to `SignalDiagnostics`:

```python
context_session_label: str | None = None
context_volatility_label: str | None = None
context_policy_version: str | None = None
context_eligible: bool | None = None
context_block_reason: str | None = None
context_neutral_mode_active: bool | None = None
```

In the MODELING-V1 path, these values are populated every cycle. `None` is
reserved only for code paths that have not yet been migrated.

### 4.7 SignalEngine consumption contract

```python
def diagnose(
    self,
    features: Features,
    regime: RegimeState,
    context: MarketContext,
) -> SignalDiagnostics: ...

def generate(
    self,
    features: Features,
    regime: RegimeState,
    diagnostics: SignalDiagnostics,
    context: MarketContext,
) -> SignalCandidate | None: ...
```

Consumption rules:

1. `SignalEngine` reads `context.context_eligible` as a readonly fact.
2. `SignalEngine` does not classify session or volatility internally.
3. `SignalEngine` does not modify `confluence_score`, direction inference,
   reclaim detection, entry, stop, target, or any `StrategyConfig` threshold
   based on context.
4. Base edge state is always computed before context blocking.
5. If `context.context_eligible is False`, `diagnose()` emits context fields
   and `generate()` returns `None`.
6. `MarketContext` is not passed to `GovernanceLayer` or `RiskEngine`.

Required diagnosis flow:

```text
Step 1: compute base edge state unconditionally.
Step 2: if base edge is absent, return signal-level blocked_by plus context fields.
Step 3: if base edge is present and context is ineligible, return
        blocked_by=None plus context_block_reason.
Step 4: if base edge is present and context is eligible, candidate remains possible.
```

The operator must be able to distinguish:

- no base edge in ASIA
- base edge present in ASIA but blocked by context

### 4.8 Orchestrator changes

```python
features = feature_engine.compute(snapshot)
regime = regime_engine.classify(features)
context = context_engine.classify(features)
diagnostics = signal_engine.diagnose(features, regime, context)
candidate = signal_engine.generate(features, regime, diagnostics, context)
```

Rules:

- `ContextEngine.classify()` is called exactly once per decision cycle.
- The orchestrator owns the call and passes the resulting `MarketContext`
  downstream.
- `SignalEngine` must not instantiate or call `ContextEngine`.
- Backtest code must use the same `ContextEngine.classify()` path.

### 4.9 Persistence mapping for context blocks

Current persistence maps signal absence through `diagnostics.blocked_by`.
MODELING-V1 must explicitly preserve context block reasons:

```python
if diagnostics.context_eligible is False:
    outcome_reason = diagnostics.context_block_reason
elif diagnostics.blocked_by is not None:
    outcome_reason = diagnostics.blocked_by
else:
    outcome_reason = "candidate_generated"
```

Context-blocked cycles must not be recorded as generic `"no_signal"`.

### 4.10 ContextConfig in config_hash

`AppSettings.config_hash` must include canonical context serialization:

```python
"context": {
    "atr_low_threshold": self.context.atr_low_threshold,
    "atr_high_threshold": self.context.atr_high_threshold,
    "neutral_mode": self.context.neutral_mode,
    "policy_version": self.context.policy_version,
    "session_volatility_whitelist": {
        k.value: sorted(v.value for v in vs)
        for k, vs in self.context.session_volatility_whitelist.items()
    },
}
```

Changing thresholds, whitelist entries, `neutral_mode`, or `policy_version`
must change `config_hash`.

---

## 5. Relationship to existing mechanisms

### 5.1 Governance session gates vs context session classification

| Layer | Question | Owner | Mechanism |
|---|---|---|---|
| Governance session gate | Are we operationally allowed to trade now? | GovernanceLayer | `session_start/end_hour_utc`, `no_trade_windows_utc` |
| Context session classification | What modeling context applies now? | ContextEngine | `SessionBucket`, whitelist |

Both layers may block, but they have different meanings. Governance remains an
operational hard gate. Context remains signal-level eligibility framing.

`GovernanceLayer` must not accept `MarketContext`. `RiskEngine` must not
accept `MarketContext`.

### 5.2 Relationship to RegimeEngine

`RegimeEngine` classifies market structure. `ContextEngine` classifies session
and volatility context. `RegimeState` is not an input to
`ContextEngine.classify()` in V1.

Regime-conditional context eligibility is deferred to a future milestone if
empirical data justifies it.

### 5.3 Relationship to DATA-INTEGRITY-V1

`DATA-INTEGRITY-V1` is prerequisite for MODELING-V1 implementation, merge, and
deployment.

MODELING-V1 is implemented against the canonical post-DATA-INTEGRITY
`Features` model.

In V1, `ContextEngine` does not consume quality fields for eligibility
decisions. `MarketContext.quality_flags` remains an empty tuple. Quality-aware
context gating is deferred to a future milestone.

There is no pre-DATA-INTEGRITY compatibility mode. Any MODELING-V1 branch
started before DATA-INTEGRITY is merged is a speculative draft and must be
rebased onto the final DATA-INTEGRITY contract before implementation begins.

---

## 6. Neutral mode

`neutral_mode=True` is mandatory for initial deployment and regression
validation.

Semantics:

- `MarketContext.context_eligible=True` always.
- `MarketContext.context_block_reason=None` always.
- `MarketContext.neutral_mode_active=True`.
- Session and volatility labels are still computed and persisted.
- Candidate sequence must be exactly identical to pre-MODELING-V1 baseline,
  except for floating-point persistence epsilon where applicable.

Neutral mode is not a degraded path. It is the default V1 deployment state
until Section 2 validation supports active context gating.

---

## 7. Frozen module and file names

| Element | Name |
|---|---|
| Module | `core/context_engine.py` |
| Engine class | `ContextEngine` |
| Method | `classify(features) -> MarketContext` |
| Output model | `MarketContext` in `core/models.py` |
| Enums | `SessionBucket`, `VolatilityBucket` in `core/models.py` |
| Config | `ContextConfig` in `settings.py` |
| AppSettings field | `context: ContextConfig` |

The `Engine` suffix is retained for consistency with `RegimeEngine`,
`SignalEngine`, and `RiskEngine`. Scope control comes from the contract, not
from renaming.

---

## 8. Storage and persistence contract

Context fields are dedicated `decision_outcomes` columns, not only
`details_json`.

### 8.1 Files to update

The repo currently defines and uses `decision_outcomes` in multiple places.
The handoff must include all of them:

- `storage/schema.sql`: update the table definition.
- `storage/state_store.py`: update idempotent table creation and existing DB
  migration logic.
- `storage/repositories.py`: update `insert_decision_outcome(...)` insert
  fields and parameters.
- `orchestrator.py`: pass context fields into the decision outcome write path.

### 8.2 New columns

Add these nullable columns:

```sql
context_session_label TEXT,
context_volatility_label TEXT,
context_policy_version TEXT,
context_eligible INTEGER,
context_block_reason TEXT,
context_neutral_mode_active INTEGER
```

`context_eligible` and `context_neutral_mode_active` are persisted as `0/1`.

### 8.3 Existing database migration

For an existing database, apply idempotent runtime migration logic in
`StateStore._apply_migrations()` equivalent to:

```sql
ALTER TABLE decision_outcomes ADD COLUMN context_session_label TEXT;
ALTER TABLE decision_outcomes ADD COLUMN context_volatility_label TEXT;
ALTER TABLE decision_outcomes ADD COLUMN context_policy_version TEXT;
ALTER TABLE decision_outcomes ADD COLUMN context_eligible INTEGER;
ALTER TABLE decision_outcomes ADD COLUMN context_block_reason TEXT;
ALTER TABLE decision_outcomes ADD COLUMN context_neutral_mode_active INTEGER;
```

The implementation must inspect `PRAGMA table_info(decision_outcomes)` before
adding columns so migration is safe to run repeatedly.

Do not assume a standalone migration runner unless one exists in the target
branch.

---

## 9. Forbidden moves

The following are forbidden in MODELING-V1:

1. `ALLOW_REDUCED` or any context-linked size modifier.
2. Threshold multipliers in `ContextConfig`.
3. Modifying `confluence_score`, direction, entry, stop, or targets based on
   context.
4. Adding `favorable: bool` to `MarketContext`.
5. Passing `MarketContext` to `GovernanceLayer`.
6. Passing `MarketContext` to `RiskEngine`.
7. Session logic inside `SignalEngine`.
8. Extending `RegimeState` with session or volatility labels.
9. Storing context only in `details_json` instead of dedicated columns.
10. Calling `ContextEngine.classify()` more than once per cycle.
11. Omitting `ContextConfig` from `config_hash`.
12. Silent context blocking without diagnostics and persistence.
13. Skipping base edge computation when context is ineligible.
14. Backtest path diverging from runtime path.
15. Lifecycle or state-machine tracking across cycles.
16. Runtime ML, LLM, or adaptive thresholds.
17. Runtime updates to whitelist or ATR thresholds.
18. Quality-aware blocking logic in V1.

---

## 10. Acceptance criteria

### AC-1: Determinism

Same `Features`, same `ContextConfig`, same code version produces the same
`MarketContext`.

### AC-2: Replayability

Historical replay with identical data snapshot and `config_hash` reproduces
identical `MarketContext` and `SignalDiagnostics` per cycle.

### AC-3: Neutral mode exact parity

With `neutral_mode=True`, MODELING-V1 must produce the same candidate sequence
as the pre-MODELING-V1 baseline:

- candidate count delta is `0`
- candidate timestamps match
- candidate direction matches
- entry, stop, and targets match, allowing only float persistence epsilon
- regime at generation time matches

Any logic-level delta blocks merge.

### AC-4: No hidden edge rewrite

These `signal_engine.py` helpers or equivalent edge subroutines must remain
unchanged:

- `_infer_direction()`
- `_confluence_score()`
- `_build_levels()`
- sweep detection checks
- reclaim detection checks
- `StrategyConfig` weight and threshold usage

Permitted `signal_engine.py` changes:

- add `context: MarketContext` to `diagnose()` and `generate()`
- populate context diagnostics fields
- add the context gate after base edge computation
- make `generate()` return `None` when `diagnostics.context_eligible is False`

### AC-5: No governance/risk contamination

`core/governance.py` and `core/risk_engine.py` must not import or reference
`MarketContext`.

### AC-6: Diagnostics completeness

Every MODELING-V1 runtime and backtest cycle persists non-null values for:

- `context_session_label`
- `context_volatility_label`
- `context_policy_version`
- `context_eligible`
- `context_neutral_mode_active`

`context_block_reason` is non-null if and only if `context_eligible=0`.

### AC-7: Config hash completeness

Changing any `ContextConfig` field changes `config_hash`.

### AC-8: Runtime/backtest parity

`BacktestRunner` uses the same `ContextEngine.classify()` path as runtime.

### AC-9: Base edge visibility under context block

When `context_eligible=False`, persisted diagnostics still allow the operator
to distinguish base-edge absence from base-edge-present context rejection.

### AC-10: Persistence path correctness

Context-blocked cycles must not be recorded as `outcome_reason='no_signal'`.

---

## 11. Test matrix

All tests are mandatory before merge.

| ID | Test | Goal |
|---|---|---|
| T-01 | `ContextEngine.classify()` determinism | Identical inputs produce identical output |
| T-02 | Session boundary correctness | `06:59 ASIA`, `07:00 EU`, `13:59 EU`, `14:00 EU_US`, `15:59 EU_US`, `16:00 US`, `21:59 US`, `22:00 ASIA` |
| T-03 | Volatility threshold boundaries | Equal-to thresholds classify as `NORMAL` |
| T-04 | `neutral_mode=True` passthrough | Eligible always true, block reason always null |
| T-05 | Whitelist eligible combination | Allowed pair returns eligible |
| T-06 | Whitelist blocked combination | Disallowed pair returns block reason |
| T-07 | Empty whitelist entry | Blocks all volatility buckets for that session |
| T-08 | Base edge before context gate | Context block does not hide base edge state |
| T-09 | Signal-level block plus context fields | `blocked_by` coexists with context labels |
| T-10 | `context_eligible` never null | MODELING-V1 path always sets bool |
| T-11 | Block reason iff ineligible | Persistence invariant holds |
| T-12 | `generate()` context stop | Ineligible context returns `None` |
| T-13 | Persistence path | Context block reason is not stored as `no_signal` |
| T-14 | Hash changes with neutral mode | Config identity includes context |
| T-15 | Hash changes with whitelist | Config identity includes whitelist |
| T-16 | Hash changes with ATR threshold | Config identity includes thresholds |
| T-17 | Governance isolation | No `MarketContext` in governance |
| T-18 | Risk isolation | No `MarketContext` in risk |
| T-19 | Neutral exact parity | Candidate sequence matches baseline |
| T-20 | Backtest/runtime parity | Same context output per cycle |
| T-21 | One context call per cycle | Orchestrator call count is one |
| T-22 | No edge helper mutation | Protected helpers unchanged |
| T-23 | Quality flags empty | `MarketContext.quality_flags == ()` |
| T-24 | Storage schema update | New columns exist and legacy rows remain readable |

---

## 12. Observability queries

```sql
SELECT COUNT(*)
FROM decision_outcomes
WHERE context_session_label IS NULL;
```

Must return `0` after the first MODELING-V1 backtest run.

```sql
SELECT COUNT(*)
FROM decision_outcomes
WHERE (context_eligible = 1 AND context_block_reason IS NOT NULL)
   OR (context_eligible = 0 AND context_block_reason IS NULL);
```

Must return `0`.

```sql
SELECT COUNT(*)
FROM decision_outcomes
WHERE context_eligible = 0
  AND outcome_reason = 'no_signal';
```

Must return `0`.

```sql
SELECT
    context_session_label,
    context_volatility_label,
    COUNT(*) AS base_edge_present_context_blocked
FROM decision_outcomes
WHERE context_eligible = 0
  AND json_extract(details_json, '$.blocked_by') IS NULL
GROUP BY context_session_label, context_volatility_label
ORDER BY base_edge_present_context_blocked DESC;
```

This query is required for post-deployment context-block diagnostics. Context
fields are dedicated columns. Existing signal diagnostics such as `blocked_by`
may continue to live in `details_json` unless the handoff explicitly adds a
dedicated signal-level reason column. The implementation must not leave base
edge visibility analytically ambiguous.

---

## 13. Out of scope

- execution realism
- position sizing per context
- leverage per context
- risk cap changes
- reclaim detection redesign
- confluence weight redesign
- Optuna / parameter search
- new external data sources
- runtime ML classifier
- HMM or tabular ML in runtime
- lifecycle/state-machine tracking across cycles
- session-specific execution templates
- polluted bucket cleanup
- adaptive thresholds
- dashboard expansion beyond minimum diagnostics
- `ALLOW_REDUCED`
- regime-conditional eligibility
- quality-aware context gating

---

## 14. Roadmap position and dependencies

```text
DATA-INTEGRITY-V1
  prerequisite for MODELING-V1 implementation, merge, and deployment
  architectural drafting may happen in parallel
    |
    v
MODELING-V1
  Phase 1: implement with neutral_mode=True
  Phase 2: empirical validation
  Phase 3: activate eligibility rules via config change only
    |
    v
EXECUTION-REALISM-V1
    |
    v
OPTUNA-RECALIBRATION-V1
```

Acceptable before DATA-INTEGRITY-V1 merge:

- architectural blueprint drafting
- builder handoff drafting
- test matrix preparation

Not acceptable before DATA-INTEGRITY-V1 merge:

- starting builder implementation of MODELING-V1
- merging MODELING-V1 code
- deploying MODELING-V1

Reason: DATA-INTEGRITY-V1 changes the canonical model contract. MODELING-V1
must not add compatibility debt for pre-DATA-INTEGRITY models.

---

## 15. What this blueprint does not freeze

Two calibration decisions remain open until empirical validation:

1. Concrete `session_volatility_whitelist` values.
2. Final `atr_low_threshold` and `atr_high_threshold` values.

All architecture, pipeline placement, ownership boundaries, diagnostics
requirements, storage requirements, and forbidden moves are frozen.

---

## 16. Builder handoff checklist

The handoff derived from this blueprint must include:

### Files to create

- `core/context_engine.py`

### Files to modify

- `core/models.py`
  - add `SessionBucket`
  - add `VolatilityBucket`
  - add `MarketContext`
  - extend `SignalDiagnostics`
- `settings.py`
  - add `ContextConfig`
  - add `AppSettings.context`
  - include context in `config_hash`
- `core/signal_engine.py`
  - add context parameters
  - add context diagnostics fields
  - add context gate after base edge computation
  - add context stop condition in `generate()`
  - do not change protected edge helpers
- `orchestrator.py`
  - instantiate/use `ContextEngine`
  - call `context_engine.classify(features)` once per cycle
  - persist context fields and context outcome reason
- `backtest/backtest_runner.py`
  - mirror runtime context path
- `storage/schema.sql`
  - add context columns to `decision_outcomes`
- `storage/state_store.py`
  - update table creation and idempotent existing DB migration logic
- `storage/repositories.py`
  - update decision outcome insert path

### Explicit builder prohibitions

- do not modify protected reclaim-edge helpers
- do not pass `MarketContext` to governance or risk
- do not call `ContextEngine` inside `SignalEngine`
- do not store context only in `details_json`
- do not implement quality-aware blocking
- do not use non-permissive whitelist values until validation is documented

---

## Appendix A. Session boundary reference

| Session | UTC start | UTC end | Hour condition |
|---|---:|---:|---|
| ASIA | 22:00 | 06:59 | `hour >= 22 or hour < 7` |
| EU | 07:00 | 13:59 | `7 <= hour < 14` |
| EU_US | 14:00 | 15:59 | `14 <= hour < 16` |
| US | 16:00 | 21:59 | `16 <= hour < 22` |

Mandatory boundary cases:

| Timestamp UTC | Expected bucket |
|---|---|
| 06:59 | ASIA |
| 07:00 | EU |
| 13:59 | EU |
| 14:00 | EU_US |
| 15:59 | EU_US |
| 16:00 | US |
| 21:59 | US |
| 22:00 | ASIA |
| 00:00 | ASIA |
| 12:00 | EU |
| 14:30 | EU_US |
| 18:00 | US |

---

## Appendix B. Final recommendation

MODELING-V1 should be implemented as a small stateless deterministic
`ContextEngine.classify(features) -> MarketContext` contract inserted after
`RegimeEngine` and before `SignalEngine`.

The layer may block signal generation only after base edge diagnosis is
computed and persisted. It must not modify edge logic, governance, risk,
execution, or runtime configuration.
