# AUDIT: MULTI_ASSET_PAPER_QUALITY_M4_WINDOW_V1
Date: 2026-05-22
Auditor: Claude Code
Commit: 8219e8d

## Verdict: DONE

**Scope:** Add `--since` timestamp filter to M4 near-miss diagnostic reporting for clean post-activation quality window (NO production deployment in this commit).

## Layer Separation: PASS
- Standalone reporting script enhancement (no runtime code changes)
- Read-only database access (no writes to btc_bot.db)
- No changes to orchestrator, settings, core, execution, or trading logic
- Standard library imports only (argparse, json, sqlite3, datetime)

## Contract Compliance: PASS
- Scope: add exact UTC `--since` timestamp filter to M4 reporting
- Reporting/query change only (no strategy, risk, execution changes)
- Read-only database access (SELECT only)
- No production settings changes
- No historical BTC-only M4 evidence deleted or overwritten

## Determinism: PASS
- Timestamp parsing deterministic (`_normalize_since()` converts Z to +00:00, naive to UTC-aware)
- Query cutoff deterministic (`--since` timestamp or `now - days`)
- Symbol filtering deterministic (same as before)
- Report generation deterministic (window description updated to reflect `--since` or `--days`)

## Backward Compatibility: PASS
- `--days` fallback preserved (default 7 when `--since` not provided)
- Existing M4 usage unchanged (no `--since` → uses `--days` as before)
- 596 tests pass (24 skipped) — 3 new tests for `--since` filter
- No changes to production reporting (not deployed yet)

## State Integrity: PASS
- Read-only database access (no INSERT, UPDATE, DELETE)
- No state mutation
- Historical BTC-only M4 evidence preserved (no deletion, no overwrite)

## Error Handling: PASS
- Empty `--since` → ValueError ("--since must not be empty")
- Invalid ISO format → datetime.fromisoformat raises error
- Timestamp normalization handles: Z suffix (Zulu time), naive UTC (adds +00:00), timezone-aware (converts to UTC)

## Smoke Coverage: PASS
- **M4 --since tests (3 new):**
  - `test_query_decision_outcomes_filters_by_since_timestamp()` → filters rows with cycle_timestamp >= since
  - `test_normalize_since_accepts_zulu_and_naive_utc()` → Z and naive timestamps normalized to +00:00
  - `test_generate_report_labels_since_window()` → report shows "Since 2026-05-21T21:00:00+00:00" when --since provided
- **Total M4 tests: 25 passed**
- **Full suite: 596 passed (24 skipped)**

## Tech Debt: LOW
- Clean enhancement (extends existing query with optional timestamp filter)
- No magic numbers (timestamp parsing uses datetime.fromisoformat)
- Report description updated to reflect window type (since vs days)

## AGENTS.md Compliance: PASS
- Commit discipline: WHAT/WHY/STATUS in commit message (8219e8d)
- Scope purity: reporting only, no trading or activation changes
- Documentation: DECISIONS_LOG and MILESTONE_TRACKER updated

## Premature Activation: N/A
- This milestone does NOT change multi_asset.enabled (already enabled)
- This milestone does NOT change production settings
- This milestone does NOT restart production services
- Purpose: enhance M4 reporting for clean post-activation quality window

## Reproducibility & Lineage: PASS
- Addresses post-activation M4 quality review
- Multi-asset PAPER activated at 2026-05-21T21:00:00Z (previous milestone)
- `--days` window mixes BTC-only (pre-activation) and multi-asset (post-activation) evidence
- `--since 2026-05-21T21:00:00Z` provides clean post-activation window for BTC/ETH/SOL quality comparison
- Documented in DECISIONS_LOG.md (2026-05-22 entry)

## Artifact Consistency: PASS
- Script enhancement matches documentation (DECISIONS_LOG, MILESTONE_TRACKER)
- Tests verify `--since` filter, timestamp normalization, report window description
- Runbook example updated to use `--since` for post-activation M4

## Boundary Coupling: PASS
- Standalone script, no coupling to runtime code
- Database reads are read-only queries (SELECT only)
- No imports from orchestrator, settings, core, execution

## M4 --since Enhancement Specifics: PASS

**CLI enhancement:**
```bash
# Old (--days only):
python scripts/report_near_miss_diagnostics.py --all-symbols --days 7

# New (--since for exact window):
python scripts/report_near_miss_diagnostics.py --all-symbols --since 2026-05-21T21:00:00Z

# Fallback (--days when --since not provided):
python scripts/report_near_miss_diagnostics.py --all-symbols --days 7  # Still works
```

**Timestamp normalization (`_normalize_since`):**
```python
def _normalize_since(raw: str) -> str:
    value = raw.strip()
    if not value:
        raise ValueError("--since must not be empty.")
    if value.endswith("Z"):
        value = f"{value[:-1]}+00:00"  # Z → +00:00
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)  # Naive → UTC-aware
    return parsed.astimezone(timezone.utc).isoformat()  # Convert to UTC, ISO format
```

**Query change:**
```python
def query_decision_outcomes(conn, days, *, symbols, all_symbols, since=None):
    cutoff = _normalize_since(since) if since else (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    
    query = """
    SELECT ...
    FROM decision_outcomes do
    LEFT JOIN market_snapshots ms ON ms.snapshot_id = do.snapshot_id
    WHERE do.cycle_timestamp >= ?  -- Inclusive start
    ORDER BY do.cycle_timestamp DESC
    """
    
    cursor.execute(query, (cutoff,))
```

**Report window description:**
```python
def generate_report(analysis, days, output_path, *, since=None):
    lines = ["# Near-Miss Diagnostics Report", ""]
    if since:
        lines.append(f"**Analysis Window:** Since {_normalize_since(since)}")
    else:
        lines.append(f"**Analysis Window:** Last {days} days")
```

**Post-activation M4 command (clean window):**
```bash
# Generate M4 quality report for multi-asset PAPER runtime only (no pre-activation BTC-only contamination)
python scripts/report_near_miss_diagnostics.py \
  --all-symbols \
  --since 2026-05-21T21:00:00Z \
  --output /tmp/m4_multi_asset_paper_quality.md
```

**Use cases:**
1. **Post-activation quality:** Clean window from activation timestamp (no BTC-only contamination)
2. **Incident analysis:** Exact window for specific event or change
3. **A/B comparison:** Compare multi-asset PAPER quality vs BTC-only baseline using separate windows

## Critical Issues (must fix before next milestone)
None.

## Warnings (fix soon)
None.

## Observations (non-blocking)
1. Standalone reporting script enhancement (no runtime coupling)
2. Read-only database access (safe for production execution)
3. `--since` provides exact UTC timestamp boundary for clean windows
4. `--days` fallback preserved for backward compatibility
5. Timestamp normalization handles Z suffix, naive UTC, and timezone-aware formats
6. Report description updated to reflect window type (since vs days)
7. Multi-asset PAPER activated at 2026-05-21T21:00:00Z (previous milestone)
8. `--since 2026-05-21T21:00:00Z` provides clean post-activation M4 window
9. BTC-only M4 and multi-asset PAPER M4 can be compared without mixing windows
10. Tests verify `--since` filter, timestamp normalization, report window description
11. Not deployed to production yet (code-only deployment + M4 run pending)
12. Clean M4 report will be generated after deployment

## Recommended Next Step

**M4 --since enhancement is DONE. Ready for code-only deployment and post-activation quality report.**

### Phase 1: Deploy M4 --since enhancement (code-only)

**Goal:** Deploy enhanced M4 script to production for clean post-activation quality reporting.

**Deployment command:**
```bash
ssh root@204.168.146.253
cd /home/btc-bot/btc-bot
git pull origin deploy/multi-asset-paper-v1  # expect: 8219e8d or later
# No restart needed (standalone script)
```

**Post-deployment verification:**
```bash
# Verify script available
python scripts/report_near_miss_diagnostics.py --help | grep -- --since
# Expected: --since help text visible
```

### Phase 2: Generate clean post-activation M4 quality report

**Goal:** Generate M4 report for multi-asset PAPER runtime only (since activation at 2026-05-21T21:00:00Z).

**Command:**
```bash
python scripts/report_near_miss_diagnostics.py \
  --all-symbols \
  --since 2026-05-21T21:00:00Z \
  --output /tmp/m4_multi_asset_paper_quality.md
```

**Expected report sections:**
- **Analysis Window:** Since 2026-05-21T21:00:00+00:00 (activation timestamp)
- **Symbol Breakdown:** BTC/ETH/SOL rows (all post-activation)
- **Near-Miss Counts:** Per-symbol near-miss events (depth >= 0.004)
- **Portfolio Gate:** Multi-symbol portfolio decisions (if any signals generated)
- **Regime Breakdown:** Per-symbol regime distribution

**Quality assessment criteria:**
- All 3 symbols (BTC/ETH/SOL) have decision rows (multi-symbol cycle executing)
- ETH/SOL depth threshold @ 0.0075 (asset-specific override applied)
- Portfolio gate evaluated when multiple signals in same cycle
- No unexpected blocker reasons (execution gates, state corruption)
- Cycle duration within capacity limits (~8-12s observed)

### Phase 3: Compare BTC-only baseline vs multi-asset PAPER quality

**BTC-only baseline (pre-activation):**
```bash
python scripts/report_near_miss_diagnostics.py \
  --symbol BTCUSDT \
  --days 7 \
  --output /tmp/m4_btc_only_baseline.md
```

**Multi-asset PAPER (post-activation):**
```bash
python scripts/report_near_miss_diagnostics.py \
  --all-symbols \
  --since 2026-05-21T21:00:00Z \
  --output /tmp/m4_multi_asset_paper_quality.md
```

**Comparison points:**
- BTC near-miss rate (pre vs post activation)
- ETH/SOL near-miss rate (post-activation only)
- Portfolio gate veto rate (multi-symbol only)
- Cycle duration (single vs multi-symbol)
- Resource consumption (capacity check trends)

---

**Next milestone decision:** Deploy M4 enhancement → generate clean post-activation quality report → assess BTC/ETH/SOL multi-asset PAPER quality.
