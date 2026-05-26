# PC Handoff: Deep Historical Threshold Research

This file is the communication channel for continuing BTC Bot work on a PC.

If you are Codex or Cascade running in Windsurf on the PC: read this file first, then perform the environment sync checks below. Do not start the full research until the checks pass and the user explicitly confirms.

## Project Context

- Project: BTC Bot production trading system.
- Laptop workspace used so far: `c:\development\btc-bot`.
- Target branch: `deploy/multi-asset-paper-v1`.
- Production server: `root@204.168.146.253`.
- Production mode: PAPER.
- Current production BTC threshold: `0.005` / `0.5%`.
- Current ETH/SOL thresholds: `0.0075` / `0.75%`.
- Do not change production without explicit user approval.
- Do not change thresholds without explicit user approval.
- Do not run heavy research until the PC environment is verified.

## Required Commits

These commits must be present after `git pull`:

- `14e4ac3 research: evaluate atr relative sweep thresholds`
- `8839fce fix: reset parity backtest portfolio periods`
- `6485d4d research: add deep threshold attribution`

Important: commit `8839fce` fixes stale daily/weekly portfolio PnL resets in long runtime-parity backtests. Without it, threshold research results are unreliable.

Commit `6485d4d` adds the research script:

```text
research_lab/analysis_deep_threshold_attribution.py
```

## Current Research Milestone

Milestone:

```text
DEEP_HISTORICAL_THRESHOLD_ATTRIBUTION_V1
```

Goal:

Run a full multi-year BTC-only runtime-parity research to understand when shallow sweeps are profitable and when they are noise. This is not a simple threshold change. The purpose is deep attribution across depth, regime, session, ATR, confluence, OI, TFI, funding, costs, and trade outcomes.

Scope:

- Symbol: `BTCUSDT` only.
- Period: `2022-01-01` to `2026-05-24`.
- Backtest type: runtime-parity only.
- Costs: fees, slippage, funding.
- Threshold variants:
  - `0.0035`
  - `0.0040`
  - `0.0045`
  - `0.0050`
  - `0.0060`
  - `0.00649`

Do not replace this with a shortcut or simplified methodology.

The full research command, only after environment checks and user approval:

```powershell
.venv\Scripts\python.exe research_lab\analysis_deep_threshold_attribution.py --start-date 2022-01-01 --end-date 2026-05-24
```

Run without `--force` unless the user explicitly asks to recompute all variants from scratch.

## First Task On PC

Prepare the PC as a second safe working machine. Do not run the full research yet.

1. Find/open the repo on PC.
2. Check git state:

```powershell
git status --short --branch
git log --oneline -5
git fetch origin
```

Confirm:

- branch is `deploy/multi-asset-paper-v1`;
- commit `6485d4d` is present;
- working tree state is known.

If the repo is dirty, do not reset or delete anything. Report the dirty files and ask the user before any cleanup.

3. Check `.venv`:

```powershell
.venv\Scripts\python.exe --version
.venv\Scripts\python.exe -m pip --version
```

4. Check required imports:

- `pandas`
- `sqlite3`
- local project modules

5. Run only lightweight validation:

```powershell
.venv\Scripts\python.exe -m py_compile research_lab\analysis_deep_threshold_attribution.py scripts\run_runtime_parity_backtest.py
.venv\Scripts\python.exe -m pytest tests\test_runtime_parity_cost_model.py -q -o addopts=
```

6. Check local database:

```text
storage\btc_bot.db
```

Report DB size and BTC data ranges for:

- `candles`
- `aggtrade_buckets`
- `open_interest`
- `funding`

Expected laptop BTC ranges were:

- candles: `2020-09-01` to about `2026-05-25`;
- aggtrade_buckets: `2020-09-01` to `2026-05-24`;
- open_interest: `2020-09-01` to about `2026-05-25`;
- funding: `2020-09-01` to about `2026-05-25`.

If PC data is missing or shorter, do not automatically backfill everything. Report the difference first and propose one of:

- copy `storage\btc_bot.db` from laptop;
- run a controlled backfill;
- use another user-approved data sync path.

7. Ensure output folders exist:

```text
research_lab\analysis_output
research_lab\reports
research_lab\analysis_output\deep_threshold_attribution_runs
```

Create them if missing.

## Communication Report Back To Repo

After PC sanity checks, create a small markdown status report and push it to GitHub.

Report path:

```text
docs/agent_communication/PC_ENV_SYNC_STATUS_2026-05-26.md
```

Use this template:

```md
# PC Environment Sync Status

Date:
Machine:
Branch:
HEAD commit:
Working tree status:

## Git
- origin:
- branch:
- latest commits:
- dirty files:

## Python / Venv
- Python version:
- pip version:
- py_compile result:
- pytest result:

## Data
BTC local DB ranges:
- candles:
- aggtrade_buckets:
- open_interest:
- funding:

DB size:

## Production Access
- SSH key present: yes/no
- production query attempted: yes/no
- result:

Do not include private key contents.

## Research Readiness
- script present: yes/no
- commit `6485d4d` present: yes/no
- ready for full run: yes/no
- blocker:

## Notes
...
```

Commit only that small markdown report.

Example commit message:

```text
docs: add PC environment sync status

WHAT: Document PC repo, venv, data, and research readiness checks.
WHY: Provide a safe handoff channel between PC, laptop, and audit/research agents.
STATUS: Environment checked; full historical research not started yet.
```

Do not commit:

- `.env`
- SSH keys
- tokens
- `storage\btc_bot.db`
- `research_lab.db`
- snapshots
- large JSON research outputs
- generated approval bundles
- ad hoc run reports outside this communication channel

## Operating Rules

- Follow `AGENTS.md`.
- This is a production trading system.
- Do not mix layers.
- Do not change production.
- Do not change thresholds.
- Do not commit data files or generated large artifacts.
- GitHub is source of truth for code and small text status reports only.
- Local DB state may differ between laptop and PC, so DB ranges must be explicitly checked.

The PC is being prepared as a second safe work machine. Avoid any action that makes laptop and PC diverge silently.
