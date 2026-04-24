# AUDIT: Configuration / Reproducibility
Date: 2026-04-24
Auditor: Cascade (Builder Mode)
Commit: 5712fbd

## Verdict: MVP_DONE

## Config Versioning: WARN
## Determinism / Reproducibility: FAIL
## Environment Overrides Documentation: WARN
## Config Drift Detection: FAIL
## Dependency Lock Quality: FAIL
## Config Snapshot Mechanism: WARN

## Findings

### Evidence reviewed
- `settings.py`
- `.env.example`
- `requirements.txt`
- `.gitignore`
- `main.py`
- `scripts/run_paper.py`
- `scripts/run_live.py`
- `scripts/server/btc-bot.service`
- `scripts/server/btc-bot-dashboard.service`
- `scripts/server/run_dashboard.sh`
- `scripts/server/setup.sh`
- `storage/schema.sql`
- `storage/state_store.py`
- `storage/repositories.py`
- `tests/test_settings.py`
- `tests/test_settings_profile.py`
- `tests/test_orchestrator_runtime_logging.py`
- `.github/workflows/ci.yml`
- Production read-only evidence:
  - deployed `btc-bot.service`
  - deployed `btc-bot-dashboard.service`
  - `config_snapshots` sample rows from production DB

### Assessment summary
- Configuration files and service templates are largely tracked in git, and `.env` is correctly ignored.
- `config_hash` is deterministic for the subset it covers, and startup persists `config_snapshots` in both tests and production.
- Exact runtime reconstruction is incomplete because `config_hash` excludes `exchange`, `proxy`, `alerts`, `storage`, service-level overrides, and environment provenance.
- Production service drift already exists relative to repo-tracked units:
  - repo `btc-bot.service`: `EnvironmentFile=/home/btc-bot/btc-bot/.env`, no explicit `BOT_SETTINGS_PROFILE`, `Restart=on-failure`
  - deployed `btc-bot.service`: `Environment="BOT_SETTINGS_PROFILE=experiment"`, no `EnvironmentFile`, `Restart=always`
  - repo dashboard unit: `--host 127.0.0.1`
  - deployed dashboard unit: `--host 0.0.0.0`
- Dependency reproducibility is weak:
  - no lockfile
  - no `.python-version`
  - CI uses Python `3.11`
  - local interpreter observed during audit: Python `3.13.1`
  - local installed package sample diverges from `requirements.txt` (`yfinance 1.2.1` exceeds `<1.0.0`; `PySocks` and `psutil` absent in the audited local interpreter)

## Critical Issues (must fix before next milestone)
- `config_hash` and `config_snapshots` do not capture the full runtime configuration surface. Current hash includes `schema_version`, `mode`, `strategy`, `risk`, `execution`, and `data_quality`, but excludes `exchange`, `proxy`, `alerts`, `storage`, interpreter version, dependency set, and service/unit metadata.
- There is no automated config drift detection between repo-tracked service definitions and deployed units. This allowed production drift on `BOT_SETTINGS_PROFILE`, restart policy, and dashboard binding.
- The project has no exact dependency lock and no pinned interpreter file, so commit checkout alone is insufficient to recreate the audited environment reliably.

## Warnings (fix soon)
- `settings.py` supports `research`, `live`, and `experiment`, but `main.py` only accepts `live` and `experiment`; this is a documentation/entrypoint asymmetry that makes environment intent less explicit.
- `scripts/run_paper.py` defaults `BOT_SETTINGS_PROFILE` to `live`, so paper runtime can silently inherit live-profile thresholds unless the operator overrides it.
- `config_snapshots` persist only `strategy_json`; `risk`, `execution`, and other runtime-critical settings are not archived alongside the hash payload in a queryable form.

## Observations (non-blocking)
- `tests/test_settings.py` verifies stable `config_hash` generation for identical configuration and confirms it changes when `ALLOW_UPTREND_PULLBACK` changes.
- `tests/test_settings_profile.py` documents and verifies profile-specific overrides for `research`, `live`, and `experiment`.
- `tests/test_orchestrator_runtime_logging.py` verifies startup persistence of a config snapshot.
- Production `config_snapshots` rows exist, with the latest observed entry at `2026-04-24T04:10:40.668168+00:00` for hash `156310a4c137ca9458acc3e06ed033cb511effe8fdb9aa8de1a15b03fdf518b1`.

## Recommended Next Step
After Phase 0 audits complete, add a full runtime config manifest and drift check that captures the entire `AppSettings` payload plus environment/profile provenance, service-unit hash, Python version, and dependency lock state per deploy.
