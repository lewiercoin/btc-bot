# btc-bot

Deterministyczny bot tradingowy BTC perpetual futures (Binance) oparty na technikach instytucjonalnych: liquidity sweep/reclaim, regime gating, governance layer, risk engine.

## Status

All blueprint phases A–H: **MVP_DONE**. Research Lab Governance Foundation, Cleanup, v0.1, v1, v2, v3, and vFuture are closed (`MVP_DONE`; hardening is `DONE`). Baseline restore point: tag `v1.0-baseline`.

Szczegółowy stan: [`docs/MILESTONE_TRACKER.md`](docs/MILESTONE_TRACKER.md)

---

## Tryby uruchomienia

### Paper trading

```bash
BOT_MODE=PAPER python main.py
```

### Live trading

```bash
BOT_MODE=LIVE BINANCE_API_KEY=... BINANCE_API_SECRET=... python main.py
```

### Backtest (single run)

```bash
python scripts/run_backtest.py \
  --start-date 2025-01-01 \
  --end-date 2025-03-31 \
  --initial-equity 10000 \
  --output-json results.json
```

---

## Wymagania

```bash
pip install -r requirements.txt
```

Klucze API (tylko dla live/paper z prawdziwym exchange):

```
BINANCE_API_KEY=...
BINANCE_API_SECRET=...
```

---

## Research Lab — optymalizacja offline

Narzędzie do systematycznej optymalizacji parametrów strategii. Działa offline, izolowane od live execution path.

### Pierwszy search run (20 triali)

```bash
python -m research_lab optimize \
  --source-db-path storage/btc_bot.db \
  --store-path research_lab_runs/store.db \
  --snapshots-dir research_lab_runs/snapshots \
  --start-date 2025-01-01 \
  --end-date 2025-03-31 \
  --n-trials 20 \
  --study-name search-v1
```

### Raport z wynikami

```bash
python -m research_lab build-report \
  --store-path research_lab_runs/store.db \
  --output-json research_lab_runs/reports/search-v1.json
```

### Cleanup starych snapshotów i benchmarków

```bash
python -m research_lab cleanup-artifacts --days 7 --dry-run
python -m research_lab cleanup-artifacts --days 7
```

Polecenie czyści tylko generowane artefakty z `research_lab/snapshots`, `research_lab_runs/*/snapshots` oraz `research_lab_runs/snapshot_benchmark/`. Nie usuwa `storage/*.db`, `research_lab/research_lab.db` ani store'ów wyników w `research_lab_runs/*/store.db`.

### Replay wybranego kandydata

```bash
python -m research_lab replay-candidate \
  --candidate-id <trial_id> \
  --store-path research_lab_runs/store.db \
  --source-db-path storage/btc_bot.db \
  --snapshots-dir research_lab_runs/snapshots \
  --output-dir research_lab_runs/replays/<trial_id>
```

### Approval bundle (przed zmianą produkcyjnego configa)

```bash
python -m research_lab build-approval-bundle \
  --candidate-id <trial_id> \
  --store-path research_lab_runs/store.db \
  --output-dir research_lab_runs/approvals/<trial_id>
```

Approval bundle zawiera `recommendation.json`, `params_diff.json`, `candidate_settings.json`. Nie modyfikuje `settings.py` automatycznie — zmiana produkcyjnego configa wymaga ręcznej decyzji.

### Walk-forward protocol

Stałe okna zdefiniowane w [`research_lab/configs/default_protocol.json`](research_lab/configs/default_protocol.json):
- Train: 90 dni, Validation: 30 dni, Step: 30 dni
- Min trades/okno: 10, Min trades/kandydat: 30
- Fragility threshold: 30% degradacji IS→OOS

---

## Architektura

```
MarketSnapshot → FeatureEngine → RegimeEngine → SignalEngine
              → GovernanceLayer → RiskEngine → Execution
```

Konfiguracja: [`settings.py`](settings.py) (`StrategyConfig` + `RiskConfig`)

Blueprint: [`docs/BLUEPRINT_V1.md`](docs/BLUEPRINT_V1.md)

---

## Testy i CI

```bash
python -m pytest tests/ -x --tb=short
python -m ruff check research_lab/ tests/
python -m compileall . -q
```

CI: GitHub Actions na push/PR do `main` (`.github/workflows/ci.yml`)
