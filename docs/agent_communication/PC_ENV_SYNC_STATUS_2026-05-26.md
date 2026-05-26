# PC Environment Sync Status

Date: 2026-05-26
Machine: DESKTOP-M9HEH95
Branch: deploy/multi-asset-paper-v1
HEAD commit: 471eef2
Working tree status: clean before this report; report file added for commit

## Git
- origin: https://github.com/lewiercoin/btc-bot.git
- branch: deploy/multi-asset-paper-v1
- latest commits:
  - 471eef2 docs: add PC research handoff channel
  - 6485d4d research: add deep threshold attribution
  - 8839fce fix: reset parity backtest portfolio periods
  - 14e4ac3 research: evaluate atr relative sweep thresholds
  - 741c9cd research: test sweep acceptance retest continuation
- dirty files:
  - docs/agent_communication/PC_ENV_SYNC_STATUS_2026-05-26.md

## Python / Venv
- Python version: `.venv` missing; system `python --version` reports Python 3.10.11
- pip version: not checked in `.venv` because `.venv\Scripts\python.exe` is missing
- required imports:
  - system Python import check failed: `ModuleNotFoundError: No module named 'pandas'`
  - `sqlite3` is expected from the standard library, but the combined import check stopped at missing `pandas`
- py_compile result:
  - passed with system Python 3.10.11:
    - `research_lab\analysis_deep_threshold_attribution.py`
    - `scripts\run_runtime_parity_backtest.py`
  - not run with `.venv` because `.venv\Scripts\python.exe` is missing
- pytest result:
  - failed with system Python 3.10.11: `No module named pytest`
  - not run with `.venv` because `.venv\Scripts\python.exe` is missing

## Data
BTC local DB ranges:
- candles: not available; `storage\btc_bot.db` missing
- aggtrade_buckets: not available; `storage\btc_bot.db` missing
- open_interest: not available; `storage\btc_bot.db` missing
- funding: not available; `storage\btc_bot.db` missing

DB size: not available; `storage\btc_bot.db` missing

## Production Access
- SSH key present: no; `%USERPROFILE%\.ssh` was not found
- production query attempted: no
- result: not attempted; no SSH key present and production access was not required for the local sanity check

## Research Readiness
- script present: yes
- commit `6485d4d` present: yes
- ready for full run: no
- blocker:
  - `.venv\Scripts\python.exe` is missing
  - required Python packages are not available in system Python (`pandas`, `pytest`)
  - `storage\btc_bot.db` is missing, so BTC historical ranges cannot be verified

## Notes
- Per handoff, full historical research was not started.
- Required output folders were ensured:
  - `research_lab\analysis_output`
  - `research_lab\reports`
  - `research_lab\analysis_output\deep_threshold_attribution_runs`
- Recommended next step is user-approved environment/data sync:
  - recreate or copy the project `.venv`;
  - copy `storage\btc_bot.db` from the laptop, run a controlled backfill, or use another approved data sync path.
