# M6 PRE-FLIGHT DATA CHECKLIST

Date: 2026-06-04
For: Codex (builder), starting M6 RED_TEAM_REPLICATION_V1 on PC.

This checklist must be completed BEFORE commit 1 (plan document). It
identifies every file Codex needs locally to actually execute M6.

If any file is missing, escalate to operator. Operator will copy the
missing file from laptop to pendrive, then from pendrive to PC. Do not
start the plan with missing data — the plan would have to guess at
artifact contents and that defeats the M6 purpose.

---

## 1. Files already in repository

These arrive via `git fetch` + `git checkout`. No external copying needed.

### From `origin/deploy/multi-asset-paper-v1` @ `683d0ca`

| Path | Purpose in M6 |
|---|---|
| `research_lab/analysis_smc_sequence_edge_feasibility_v1.py` | Part A baseline + perturbations target module |
| `research_lab/diagnostics/trial_00095_conditional_edge_attribution_v1.py` | Part B reference module (DO NOT import, only read for understanding) |
| `research_lab/reports/trial_00095_conditional_edge_attribution_v1.json` | Part B baseline metrics (PF=4.216, ER=2.121, WR=56.57%) |
| `research_lab/reports/trial_00095_conditional_edge_attribution_v1.md` | Part B baseline tables |
| `docs/audits/AUDIT_SMC_SEQUENCE_EDGE_FEASIBILITY_V1_2026-05-27.md` | Part A prior verdict reference |
| `docs/audits/AUDIT_TRIAL_00095_ATTRIBUTION_V1_2026-05-30.md` | Part B prior verdict reference |
| `docs/research/SMC_SEQUENCE_EDGE_FEASIBILITY_V1_PLAN.md` | Part A original plan |
| `docs/analysis/SMC_SEQUENCE_EDGE_FEASIBILITY_V1_2026-05-27.md` | Part A baseline SHA (`8CA802FD...`) |
| `tests/test_research_lab_smc_sequence_edge_feasibility_v1.py` | Part A test patterns to follow |
| `AGENTS.md`, `docs/BLUEPRINT_RESEARCH_LAB.md`, `docs/QUANT_RESEARCH_OPERATING_MODEL.md` | Discipline references |

### From `origin/claude/festive-maxwell-iciBo`

| Path | Purpose |
|---|---|
| `docs/handoffs/HANDOFF_M6_RED_TEAM_REPLICATION_V1_2026-06-04.md` | The M6 handoff itself |
| `docs/audits/AUDIT_M3_RECLAIM_REJECTION_DIAGNOSTIC_V1_2026-06-04.md` | M3 context |
| `docs/research/RESEARCH_LANDSCAPE_RESET_2026-06-04.md` | Landscape reset memo (cited in M6 handoff §2) |
| `docs/MILESTONE_TRACKER.md` | M5 PAUSED + M6 ACTIVE entries |
| `docs/handoffs/M6_PRE_FLIGHT_DATA_CHECKLIST_2026-06-04.md` | This file |

**Fetch commands for PC:**

```powershell
cd c:\development\btc-bot
git fetch origin deploy/multi-asset-paper-v1
git fetch origin claude/festive-maxwell-iciBo
```

If `git status` shows clean working tree on `deploy/multi-asset-paper-v1`
at `683d0ca`, proceed. If dirty, escalate to operator before any further
action.

---

## 2. External data files — required on PC, NOT in repo

These artifacts are not committed (too large or generated outputs). Codex
must verify each exists on PC before starting commit 1. If any is
missing, operator copies from laptop via pendrive.

### F-1 — Canonical market database

| Field | Value |
|---|---|
| Expected path | `research_lab/data/crowded_unwind_backtest.db` |
| Size (approx) | ~600+ MB |
| Used by | Part A (entire SMC_SEQUENCE diagnostic) |
| Already on pendrive? | YES — used in M3 re-run (`683d0ca`) |

**Verification (must match exactly):**

```powershell
cd c:\development\btc-bot
.\.venv\Scripts\python.exe -c "import sqlite3; c=sqlite3.connect('research_lab/data/crowded_unwind_backtest.db'); print('aggtrade cvd non-null:', c.execute('SELECT COUNT(*) FROM aggtrade_buckets WHERE cvd IS NOT NULL').fetchone()[0]); print('cvd_price_history:', c.execute('SELECT COUNT(*) FROM cvd_price_history').fetchone()[0]); print('candles 15m BTCUSDT in window:', c.execute(\"SELECT COUNT(*) FROM candles WHERE symbol='BTCUSDT' AND timeframe='15m' AND open_time >= '2022-01-01' AND open_time <= '2026-03-01'\").fetchone()[0])"
```

Expected output (exact):

```
aggtrade cvd non-null: 3122272
cvd_price_history: 0
candles 15m BTCUSDT in window: 145921
```

If any number differs, STOP. Wrong DB attached. Escalate to operator.

### F-2 — Trial-00095 frozen accepted trades

| Field | Value |
|---|---|
| Expected path | `research_lab/analysis_output/trial_00095_trades.json` |
| Used by | Part B (loads 274 accepted trades — `trade_id`, `opened_at`, `direction`, `regime`, `pnl_r`, `exit_reason`, etc.) |
| Source module reference | `trial_00095_conditional_edge_attribution_v1.py:28` `DEFAULT_TRADES_PATH` |

**Verification:**

```powershell
.\.venv\Scripts\python.exe -c "import json; d=json.load(open('research_lab/analysis_output/trial_00095_trades.json')); print('type:', type(d).__name__); n = len(d) if isinstance(d, list) else (d.get('count') or len(d.get('trades', []))); print('count:', n); print('expected: 274')"
```

If count != 274, STOP. Wrong artifact. Escalate.

### F-3 — Trial-00095 intrabar frozen entries

| Field | Value |
|---|---|
| Expected path | `research_lab/analysis_output/trial_00095_intrabar_frozen_entries.json` |
| Used by | Part B (loads frozen entry context: entry price, SL, TP, trail config per trade) |
| Source module reference | `trial_00095_conditional_edge_attribution_v1.py:29` `DEFAULT_ENTRIES_PATH` |

**Verification:**

```powershell
.\.venv\Scripts\python.exe -c "import json; d=json.load(open('research_lab/analysis_output/trial_00095_intrabar_frozen_entries.json')); print('type:', type(d).__name__); print('keys/count:', len(d) if isinstance(d, (dict,list)) else 'unknown'); print('sample keys:', list(d.keys())[:3] if isinstance(d, dict) else 'list')"
```

Expected: count or dict-keys count ~274 (one per trade). If empty or
missing, STOP. Escalate.

### F-4 — Market DB snapshot (replay run13)

| Field | Value |
|---|---|
| Expected path | `research_lab/snapshots/replay-run13-regime-aware-trial-00063.db` |
| Used by | Part B (market context fallback if canonical DB lacks columns needed for replay) — verify in attribution module which DB it actually queries |
| Source module reference | `trial_00095_conditional_edge_attribution_v1.py:30` `DEFAULT_MARKET_DB_PATH` |

**Verification:**

```powershell
.\.venv\Scripts\python.exe -c "import pathlib, sqlite3; p = pathlib.Path('research_lab/snapshots/replay-run13-regime-aware-trial-00063.db'); print('exists:', p.exists(), 'size_mb:', round(p.stat().st_size/1e6, 1) if p.exists() else None); c = sqlite3.connect(p); print('tables:', [r[0] for r in c.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()][:10])"
```

If missing AND Part B replication can be done using only canonical DB
(F-1) without F-4, that is acceptable — but document the decision
explicitly in the plan (Section "Database choice for Part B"). Do NOT
silently substitute.

If Part B truly needs F-4 (e.g., it has different fold boundaries, different
candle window, different ATR series), STOP and escalate. Operator
copies F-4 from laptop via pendrive.

---

## 3. Python environment

Codex's existing PC `.venv` should already have:

- `python` (3.11+ assumed from prior milestones)
- `pandas`, `sqlite3` (stdlib), `pytest`, `pathlib`, `dataclasses`, `hashlib`, `json`

If pytest is missing or any import fails, escalate; do not pip-install
without operator approval.

**Verification:**

```powershell
.\.venv\Scripts\python.exe -c "import pandas, sqlite3, pytest, hashlib, json, pathlib; print('env OK')"
```

---

## 4. Pendrive transfer plan (if any file is missing on PC)

Operator workflow if F-2, F-3, or F-4 is missing on PC:

1. On laptop (where files exist), copy to pendrive root:

   ```
   trial_00095_trades.json
   trial_00095_intrabar_frozen_entries.json
   replay-run13-regime-aware-trial-00063.db
   ```

2. Move pendrive from laptop to PC.

3. On PC, copy from pendrive to working tree:

   ```powershell
   cd c:\development\btc-bot
   copy E:\trial_00095_trades.json research_lab\analysis_output\
   copy E:\trial_00095_intrabar_frozen_entries.json research_lab\analysis_output\
   copy E:\replay-run13-regime-aware-trial-00063.db research_lab\snapshots\
   ```

   (Adjust `E:` to actual pendrive drive letter.)

4. Re-run verifications F-2, F-3, F-4 above. If they pass, proceed to
   plan commit.

Canonical DB (F-1) stays on pendrive — already in M3 workflow. Operator
keeps pendrive attached during M6 runs.

---

## 5. Confirmation gate before commit 1

Codex's first response on M6 must include this exact block, filled in:

```
PRE-FLIGHT M6 DATA CHECKLIST CONFIRMATION

Repo state:
- branch: <branch>
- HEAD: <commit hash>
- working tree: <clean | dirty>

External files on PC:
- F-1 canonical DB: <PRESENT | MISSING>
  - aggtrade cvd non-null: <number, expected 3122272>
  - candles 15m BTCUSDT in window: <number, expected 145921>
- F-2 trial-00095 trades: <PRESENT | MISSING>
  - count: <number, expected 274>
- F-3 intrabar frozen entries: <PRESENT | MISSING>
  - count: <number, expected ~274>
- F-4 market DB snapshot: <PRESENT | MISSING | NOT_NEEDED_FOR_PART_B>

Python env: <OK | MISSING_DEPS: list>

Decision: <READY_TO_DRAFT_PLAN | BLOCKED: list missing>
```

If `Decision: BLOCKED`, stop. Wait for operator. Do not draft a plan that
assumes file contents you cannot verify.

If `Decision: READY_TO_DRAFT_PLAN`, proceed to the 7 items in the M6
handoff §"Your first response must contain" and then draft commit 1.

---

## End of pre-flight checklist.
