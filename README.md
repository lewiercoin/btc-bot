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

### Historical data backfill

Before deploying experiment-v2 on a production database that predates DATA QUALITY FOUNDATION, run the one-time OI/CVD backfill:

```bash
python scripts/run_backfill.py
```

The script creates missing persistence tables, copies historical OI from `open_interest`, refreshes current OI and recent 15m prices from Binance REST, and fills `cvd_price_history`. Expected readiness output:

```text
READY: OI=60.00 days (... samples), CVD=30 bars
```

If the output is `NOT READY`, do not restart the experiment-v2 bot yet. Inspect the script logs for missing OI history, REST failures, or insufficient 15m price bars.

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

## Dashboard

Read-only observability UI (FastAPI m4, SSE log stream, polling).

**Production URL:** `http://204.168.146.253:8080`

**Panels:** Bot Status, Bot Control (start/stop), Open Positions, Egress Health, Recent Trades, Signals, Daily Metrics, Alerts, Log Stream

**Egress Health panel** — live SOCKS5 proxy status (exit node IP, session age, bans/24h, safe mode). Auto-refreshes every 10s. Safe mode alert banner appears at top of page in red when trading is paused.

### How to run & access Dashboard

**Start via systemd (production):**

```bash
sudo systemctl start btc-bot-dashboard
sudo systemctl status btc-bot-dashboard
```

**Quick health check:**

```bash
curl -s http://localhost:8080/api/status | python3 -m json.tool | head -10
curl -s http://localhost:8080/api/egress  | python3 -m json.tool
```

**SSH tunnel (no firewall change needed):**

```bash
ssh -i btc-bot-deploy -L 8080:127.0.0.1:8080 btc-bot@204.168.146.253 -N
# then open http://localhost:8080
```

Full step-by-step guide (UFW, external binding, log rotation, deploy updates): [`docs/dashboard/access-guide.md`](docs/dashboard/access-guide.md)

API docs (Egress Health endpoint): [`docs/dashboard/egress-integration.md`](docs/dashboard/egress-integration.md)

---

## Egress Configuration

When the server IP is blocked by Binance CloudFront, route REST traffic through a SOCKS5 exit node.

### Setup

See [`docs/infra/egress-vultr.md`](docs/infra/egress-vultr.md) for full setup instructions.

### Quick configuration (`.env`)

```bash
PROXY_ENABLED=true
PROXY_URL=<exit-node-ip>:1080   # SOCKS5 exit node
PROXY_TYPE=socks5
PROXY_STICKY_MINUTES=60
PROXY_FAILOVER_LIST=            # optional: comma-separated backup proxies
```

See [`.env.example`](.env.example) for all available options.

---

## WebSocket

Bot connects to Binance Futures WebSocket for live market data (aggTrade, forceOrder).

**URLs:**
- New official path: `wss://fstream.binance.com/market?streams=btcusdt@aggTrade/btcusdt@forceOrder`
- Legacy fallback path: `wss://fstream.binance.com/stream?streams=...`

**Migration:** Bot uses new `/market/` path by default. If connection fails, it automatically falls back to legacy `/stream/` path with logging. This ensures future-proof connectivity while preventing production downtime.

Configuration in `settings.py`: `ExchangeConfig.futures_ws_market_base_url`, `ExchangeConfig.futures_ws_stream_base_url`

---

## Diagnostyka

Jeśli bot pozostaje w safe mode lub ma problemy z połączeniem WebSocket, użyj skryptu diagnostycznego:

```bash
ssh -i btc-bot-deploy root@204.168.146.253
cd /home/btc-bot/btc-bot
bash scripts/diagnostics/check_safe_mode.sh
```

Skrypt sprawdza:
- Status usług (btc-bot.service, btc-bot-dashboard.service)
- Ostatnie 100 linii logu bota
- API dashboard: Egress Health
- API dashboard: Server Resources
- Stan bazy danych (bot_state)
- Konfigurację WebSocket URL
- Ostatnie próby połączenia WebSocket

Szczegółowy przewodnik: [`docs/diagnostics/safe-mode-check.md`](docs/diagnostics/safe-mode-check.md)

---

## Testy i CI

```bash
python -m pytest tests/ -x --tb=short
python -m ruff check research_lab/ tests/
python -m compileall . -q
```

CI: GitHub Actions na push/PR do `main` (`.github/workflows/ci.yml`)
