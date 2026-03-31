# Contextual Report: BTC Bot Optimization System Audit Request

## Executive Summary

This document provides comprehensive context for Claude Code to conduct an independent audit of the proposed BTC bot optimization system (autoresearch adaptation). The system aims to enable autonomous parameter tuning while maintaining strict separation from live trading operations.

## Background

### Project Status
- All Blueprint v1.0 phases (A-H) are MVP_DONE
- Currently completing historical data backfill (03-01→03-27)
- Next milestone: Decision point after full backtest results
- Blueprint v1.0 explicitly excludes automated parameter optimization (v2.0 feature)

### Optimization System Origin
1. **Research Request**: User requested quant-algo-agentic AI system for bot tuning
2. **Prompt Development**: Created `docs/prompts/RESEARCH_SYSTEM_SEARCH.md` 
3. **Perplexity Implementation**: Generated autoresearch adaptation in `docs/autoresearch/`
4. **Dual Audit Conducted**: 
   - Cascade (technical integration audit)
   - GPT (methodological rigor audit)

## System Architecture Overview

### Core Components
```
research/
├── config_space.py          # Parameter space definition (agent-modifiable)
├── prepare_research.py       # Fixed infrastructure (DO NOT MODIFY)
├── run_experiment.py        # Experiment orchestration
├── governance_analysis.py   # Governance filter deep-dive
└── analyze_trades.py         # Existing trade analysis (already present)
```

### Parameter Space Coverage
- **45 parameters** across 5 engine configs
- **FeatureEngine**: ATR, EMAs, sweep/reclaim buffers, funding windows
- **RegimeEngine**: EMA gaps, compression thresholds, crowded leverage limits
- **SignalEngine**: Confluence weights, TFI thresholds, entry/exit offsets
- **Governance**: Cooldowns, trade limits, drawdown controls
- **Risk**: Position sizing, leverage, RR requirements

### Optimization Pipeline
```
1. Optuna Study (TPE sampler) → Best Parameters
2. Walk-Forward Validation → Stability Check
3. Governance Deep-Dive → Filter Analysis
4. Sensitivity Analysis → Parameter Importance
5. Human Review → Promotion Decision
```

## Key Findings from Previous Audits

### Technical Integration Issues (Cascade)
| Issue | Severity | Impact |
|---|---|---|
| Wrong class names (`RegimeEngineConfig` vs `RegimeConfig`) | 🔴 Blocker | Code won't run |
| Incorrect imports (configs not in `settings.py`) | 🔴 Blocker | Code won't run |
| `BacktestRunner` API mismatch (expects `AppSettings`, not individual configs) | 🔴 Blocker | Code won't run |
| `analyze_closed_trades()` wrong signature | 🔴 Blocker | Code won't run |
| Table names in `verify_data()` may not match schema | 🟡 Medium | Data verification fails |
| Hardcoded DB path | 🟡 Medium | Portability issue |

### Methodological Issues (GPT)
| Issue | Severity | Impact |
|---|---|---|
| Walk-forward is stability check, not true nested optimization | 🔴 Critical | Overfitting risk |
| Agent can modify validation protocol (windows, thresholds) | 🔴 Critical | Can optimize validation itself |
| Multi-objective flattened to single fitness scalar | 🟡 Medium | Loses Pareto trade-offs |
| Governance analysis too primitive (only ON/OFF comparison) | 🟡 Medium | Misses per-rule attribution |
| Minimum trade count < 3 too weak | 🟡 Medium | Statistical significance |
| Regime-aware optimization only conceptual | 🟢 Low | Future enhancement |

### Blueprint Compliance Assessment
| Aspect | Blueprint v1.0 Status | Autoresearch Status |
|---|---|---|
| Automated parameter optimization | ❌ Explicitly excluded | ✅ Core feature |
| LLM in live loop | ❌ Explicitly excluded | ✅ Offline only |
| Offline research | ✅ Phase H scope | ✅ Full implementation |
| Deterministic core pipeline | ✅ Required | ✅ Preserved |
| Audit trail | ✅ Required | ✅ Git + results.tsv |

## Integration Complexity Analysis

### Required Changes
1. **Import Fixes**: Update all config class imports to actual locations
2. **BacktestRunner Adapter**: Build `AppSettings` from flat parameter dict
3. **Schema Verification**: Ensure table names match actual DB schema
4. **Path Configuration**: Use `settings.storage.db_path` instead of hardcoded
5. **Function Signature**: Fix `analyze_closed_trades()` call signature

### Estimated Effort
- **Technical Integration**: 2-3 days (Codex)
- **Methodological Fixes**: 3-4 days (GPT + Codex)
- **Testing & Validation**: 2-3 days (Codex + Cascade)
- **Total**: 7-10 days

## Risks and Limitations

### Technical Risks
- **Layer Separation Violation**: Adapter code may create hidden dependencies
- **State Leakage**: BacktestRunner reuse across experiments
- **Data Consistency**: Multiple concurrent experiments may corrupt DB

### Methodological Risks
- **Overfitting**: Even with walk-forward, agent can game the system
- **Parameter Instability**: Best params may change dramatically between windows
- **Governance Blind Spots**: 93% rejection rate needs per-rule analysis
- **Statistical Power**: Insufficient trades for reliable optimization

### Operational Risks
- **Production Drift**: Optimized params may not generalize to live market
- **Maintenance Overhead**: Research system requires ongoing human oversight
- **Resource Consumption**: Optuna studies are computationally expensive

## Specific Questions for Claude Audit

### 1. Architectural Compliance
- Does the proposed system maintain Blueprint's deterministic core requirement?
- Are layer separation principles preserved?
- Is the offline-only constraint properly enforced?

### 2. Methodological Rigor
- Is the walk-forward implementation sufficient for overfitting prevention?
- Are the statistical safeguards (minimum trades, significance tests) adequate?
- Does the multi-objective scalarization hide important trade-offs?

### 3. Integration Feasibility
- Can the technical issues be resolved without core architecture changes?
- Is the BacktestRunner adapter approach sound?
- What are the hidden integration complexities?

### 4. Production Readiness
- What additional safeguards are needed before production parameter changes?
- How should promotion decisions be structured?
- What monitoring is required for optimized parameters in live trading?

### 5. Alternative Approaches
- Should we consider simpler optimization methods first?
- Are there existing quant research frameworks that better fit our constraints?
- Would a staged approach (sensitivity → regime-aware → full optimization) be safer?

## Expected Deliverables

### Audit Report Structure
1. **Executive Summary**: Overall assessment and recommendation
2. **Technical Findings**: Integration feasibility and complexity
3. **Methodological Review**: Statistical rigor and overfitting safeguards
4. **Risk Assessment**: Technical, methodological, and operational risks
5. **Implementation Roadmap**: Recommended sequence and milestones
6. **Go/No-Go Decision**: Clear recommendation on proceeding with optimization system

### Success Criteria
- Clear determination of whether the system meets Blueprint requirements
- Prioritized list of blocking vs. non-blocking issues
- Specific implementation guidance for technical fixes
- Methodological improvements with measurable impact
- Risk mitigation strategies with monitoring protocols

## Context Constraints

### Must Preserve
- Deterministic live trading pipeline
- Layer separation (feature → regime → signal → governance → risk → execution)
- Offline-only research constraint
- Full audit trail capability
- AGENTS.md engineering discipline

### Must Avoid
- LLM in live decision loop
- Hidden state mutations
- Production code modifications for research
- Unconstrained agent autonomy
- Statistical overfitting

---

**Prepared by**: Cascade (Independent Auditor)
**Date**: 2026-03-29
**Purpose**: Request for independent audit of proposed optimization system
**Next Step**: Claude Code audit report and recommendation
