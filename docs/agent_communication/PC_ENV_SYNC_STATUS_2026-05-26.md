# PC Environment Sync Status

Date: 2026-05-26
Machine: DESKTOP-M9HEH95
Branch: deploy/multi-asset-paper-v1
HEAD commit before this update: 072fd28
Working tree status: clean tracked tree before this report update; local ignored artifacts present (`.venv`, caches, `storage\btc_bot.db`)

## Git
- origin: https://github.com/lewiercoin/btc-bot.git
- branch: deploy/multi-asset-paper-v1
- latest commits:
  - 072fd28 docs: add PC environment sync status
  - 471eef2 docs: add PC research handoff channel
  - 6485d4d research: add deep threshold attribution
  - 8839fce fix: reset parity backtest portfolio periods
  - 14e4ac3 research: evaluate atr relative sweep thresholds
- dirty files:
  - docs/agent_communication/PC_ENV_SYNC_STATUS_2026-05-26.md
- ignored local artifacts:
  - `.venv/`
  - `.pytest_cache/`
  - `__pycache__/`
  - `storage/btc_bot.db`
  - `research_lab/analysis_output/`

## Python / Venv
- Python version: Python 3.11.9 from `.venv\Scripts\python.exe`
- pip version: pip 26.1.1 from `.venv\Lib\site-packages\pip` (python 3.11)
- required imports:
  - `pandas`: OK
  - `sqlite3`: OK
  - `research_lab.analysis_deep_threshold_attribution`: OK
  - `scripts.run_runtime_parity_backtest`: OK
- py_compile result:
  - passed with `.venv\Scripts\python.exe`
  - files:
    - `research_lab\analysis_deep_threshold_attribution.py`
    - `scripts\run_runtime_parity_backtest.py`
- pytest result:
  - passed with `.venv\Scripts\python.exe -m pytest tests\test_runtime_parity_cost_model.py -q -o addopts=`
  - result: 4 passed in 0.45s

## Data
BTC local DB ranges:
- candles:
  - count: 263,692
  - range: `2020-09-01T00:00:00+00:00` to `2026-05-25T21:45:00+00:00`
  - timeframes:
    - 15m: 200,907 rows, `2020-09-01T00:00:00+00:00` to `2026-05-25T21:45:00+00:00`
    - 1h: 50,227 rows, `2020-09-01T00:00:00+00:00` to `2026-05-25T21:00:00+00:00`
    - 4h: 12,558 rows, `2020-09-01T00:00:00+00:00` to `2026-05-25T20:00:00+00:00`
- aggtrade_buckets:
  - count: 3,209,824
  - range: `2020-09-01T00:00:00+00:00` to `2026-05-24T23:59:00+00:00`
  - timeframes:
    - 15m: 200,622 rows, `2020-09-01T00:00:00+00:00` to `2026-05-24T23:45:00+00:00`
    - 60s: 3,009,202 rows, `2020-09-01T00:00:00+00:00` to `2026-05-24T23:59:00+00:00`
- open_interest:
  - count: 541,649
  - range: `2020-09-01T00:00:00+00:00` to `2026-05-25T21:50:00+00:00`
- funding:
  - count: 6,279
  - range: `2020-09-01T00:00:00+00:00` to `2026-05-25T16:00:00.001000+00:00`

DB size: 1,828,192,256 bytes (`storage\btc_bot.db`)

## Production Access
- SSH key present: no; `%USERPROFILE%\.ssh` was not found
- production query attempted: no
- result: not attempted; production access was not required for local environment/data sanity checks

## Research Readiness
- script present: yes
- commit `6485d4d` present: yes
- ready for full run: yes, pending explicit user approval
- blocker:
  - none for local deep threshold attribution sanity prerequisites
- caveat:
  - `.python-version` pins 3.12.3, but this PC has no Python 3.12 installed; `.venv` was created with Python 3.11.9

## Notes
- Per handoff, full historical research was not started.
- No database backfill was run.
- `storage\btc_bot.db` was copied from `F:\btc_bot_db_2026-05-26.db` to `storage\btc_bot.db`.
- Required output folders were ensured:
  - `research_lab\analysis_output`
  - `research_lab\reports`
  - `research_lab\analysis_output\deep_threshold_attribution_runs`
