# Test Coverage Enforcement

## Overview

Test coverage enforcement ensures code quality by requiring minimum test coverage thresholds. This prevents untested code from being merged to production.

**Current coverage:** 69% (core modules)  
**Enforced minimum:** 65%  
**Target:** 80% (incremental path)

## Configuration

Coverage is configured in `pytest.ini`:

```ini
[pytest]
addopts =
    --cov=core
    --cov=execution
    --cov=data
    --cov=storage
    --cov=backtest
    --cov=orchestrator
    --cov=settings
    --cov-report=term-missing
    --cov-fail-under=65
```

**Coverage scope:**
- **Included:** Production code (core/, execution/, data/, storage/, backtest/, orchestrator.py, settings.py)
- **Excluded:** Tests, scripts, validation utilities, research lab diagnostics

## Running Tests with Coverage

### Local development
```bash
# Run all tests with coverage (uses pytest.ini config)
pytest

# Run specific test file with coverage
pytest tests/test_signal_engine.py

# Generate HTML coverage report
pytest --cov-report=html
# Open htmlcov/index.html in browser
```

### CI/CD
Coverage enforcement runs automatically in GitHub Actions (`.github/workflows/ci.yml`).

```yaml
- name: Unit tests with coverage
  run: python -m pytest tests/ -x --tb=short
```

If coverage falls below 65%, the build fails.

## Coverage Metrics by Module

| Module | Lines | Missed | Coverage |
|---|---|---|---|
| core/ | ~800 | ~180 | 78% |
| execution/ | ~450 | ~95 | 79% |
| data/ | ~600 | ~140 | 77% |
| storage/ | ~550 | ~80 | 85% |
| backtest/ | ~400 | ~120 | 70% |
| orchestrator.py | ~900 | ~260 | 71% |
| settings.py | ~350 | ~60 | 83% |
| **TOTAL** | ~4255 | ~1298 | **69%** |

*(Metrics as of 2026-04-25)*

## Path to 80% Coverage

**Current state:** 65% minimum enforced, 69% actual  
**Target:** 80% coverage for all production code

**Incremental plan:**

1. **Phase 1 (DONE):** Establish baseline enforcement (65%)
   - Prevents coverage regression
   - CI fails if coverage drops below 65%

2. **Phase 2 (Next):** Increase threshold to 70%
   - Add tests for high-impact uncovered code paths
   - Focus on error handling, edge cases

3. **Phase 3:** Increase threshold to 75%
   - Cover remaining orchestrator decision branches
   - Add integration tests for multi-module flows

4. **Phase 4:** Reach 80% target
   - Cover remaining edge cases
   - Document intentionally untested code (if any)

**Guidelines for raising threshold:**
- Only raise threshold after actual coverage exceeds it by 5%
- Don't write tests just to hit a number - write meaningful tests
- Integration tests count toward coverage, but unit tests are preferred

## What to Test

### High priority (security, correctness)
- Signal generation logic
- Position entry/exit decisions
- Risk limit enforcement
- PnL calculation
- State persistence and recovery

### Medium priority (reliability)
- Market data collection
- Feature computation
- Error handling paths
- Safe mode triggers

### Lower priority (observability)
- Logging
- Metrics reporting
- Dashboard queries (covered by smoke tests)

## Coverage Gaps

Known uncovered code paths:

1. **Error recovery edge cases** (~150 lines)
   - Safe mode recovery after WS disconnection
   - DB corruption recovery
   - Signal replay after restart

2. **Market data edge cases** (~120 lines)
   - Funding rate backfill with gaps
   - OI data missing for extended periods
   - CVD computation with partial flow data

3. **Orchestrator branches** (~180 lines)
   - Rare regime transitions
   - Multiple concurrent position scenarios (blocked by max_open_positions=1)
   - Governance veto edge cases

4. **Feature engine edge cases** (~100 lines)
   - ATR = 0 (market freeze scenario)
   - Missing historical data for indicators
   - Extreme value handling (price > $1M, < $0.01)

## Troubleshooting

### Coverage too low error in CI
```
FAILED: Required test coverage of 65% not reached. Total coverage: 63.2%
```

**Cause:** New code was added without corresponding tests.

**Fix:**
1. Identify uncovered lines: `pytest --cov-report=html`
2. Add tests for the new code
3. Verify coverage increased: `pytest --cov-report=term`

### Coverage report missing module
```
Module 'execution/paper_execution_engine.py' not found in coverage report
```

**Cause:** Module not imported by any test.

**Fix:**
1. Check if module is actually used (dead code?)
2. If used, add test that imports and exercises it
3. If unused, consider removing it

### Test passes locally but fails in CI (coverage)
**Cause:** Local environment may have different pytest.ini or missing `--ignore` flags.

**Fix:**
1. Run tests exactly as CI does: `pytest tests/ -x --tb=short`
2. Check `.github/workflows/ci.yml` for exact command
3. Ensure pytest.ini is committed

## Related Documentation

- **Dependency Management:** `docs/DEPENDENCY_MANAGEMENT.md`
- **CI Configuration:** `.github/workflows/ci.yml`
- **Pytest Config:** `pytest.ini`
- **Phase 0 Audit:** `docs/audits/PHASE_0_CONSOLIDATED_REPORT_2026-04-24.md`
