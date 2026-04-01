# BTC Institutional Trading Bot — Implementation Blueprint v1.0

## 1. Cel v1.0

Zbudować deterministyczny rdzeń bota tradingowego BTCUSDT Perpetual do:
- paper tradingu,
- realistycznego backtestu,
- późniejszego uruchomienia live na małym kapitale.

### v1.0 świadomie NIE zawiera
- LLM w pętli live,
- multi-agent orchestration,
- on-chain jako sygnału intraday,
- mikroserwisów,
- depth/OBI rebuild,
- automatycznej optymalizacji parametrów.

### v1.0 zawiera
- data ingestion,
- feature engine,
- regime engine,
- signal candidate,
- governance layer,
- risk engine,
- execution engine,
- persistence,
- audit logging,
- Telegram alerts,
- startup recovery,
- oddzielny backtest.

## 2. Zasada architektoniczna

System działa według sekwencji:

```
Market data → Features → Regime → SignalCandidate → Governance → ExecutableSignal → RiskGate → Execution → Audit
```

To oznacza:
- **SignalCandidate** = setup istnieje
- **ExecutableSignal** = setup nadal ma sens po filtrach zachowania systemu
- **RiskGate** = nawet dobry setup może zostać zablokowany przez limity ryzyka
- **Execution** = osobna warstwa, nie podejmuje decyzji strategicznych

## 3. Scope funkcjonalny v1.0

### 3.1 Instrument i venue
- instrument: BTCUSDT
- venue: Binance Futures
- tryb: najpierw paper, potem minimal live
- margin: isolated only

### 3.2 Timeframe'y
- 4H → bias i regime context
- 1H → kontekst średni
- 15M → setup i entry logic
- 1M / 60s buckets z aggTrades → flow context

### 3.3 Główna logika strategii

Core edge:
- liquidity sweep
- reclaim
- funding skew
- OI context
- forced flow context
- optional passive ETF bias logging

## 4. Finalna struktura repo

```
btc-bot/
├── .github/
│   └── workflows/
│       └── ci.yml
├── main.py
├── orchestrator.py
├── settings.py
├── requirements.txt
├── README.md
├── pytest.ini
├── ruff.toml
│
├── data/
│   ├── market_data.py
│   ├── websocket_client.py
│   ├── rest_client.py
│   ├── etf_bias_collector.py
│   └── exchange_guard.py
│
├── core/
│   ├── models.py
│   ├── feature_engine.py
│   ├── regime_engine.py
│   ├── signal_engine.py
│   ├── governance.py
│   ├── risk_engine.py
│   └── execution_types.py
│
├── execution/
│   ├── execution_engine.py
│   ├── paper_execution_engine.py
│   ├── live_execution_engine.py
│   ├── order_manager.py
│   └── recovery.py
│
├── storage/
│   ├── db.py
│   ├── schema.sql
│   ├── repositories.py
│   ├── state_store.py
│   └── position_persister.py
│
├── monitoring/
│   ├── audit_logger.py
│   ├── telegram_notifier.py
│   ├── health.py
│   └── metrics.py
│
├── backtest/
│   ├── backtest_runner.py
│   ├── fill_model.py
│   ├── performance.py
│   └── replay_loader.py
│
├── scripts/
│   ├── init_db.py
│   ├── bootstrap_history.py
│   ├── run_backtest.py
│   ├── run_paper.py
│   ├── run_live.py
│   ├── daily_summary.py
│   └── smoke_*.py
│
├── research/
│   ├── analyze_trades.py
│   └── llm_post_trade_review.py
│
├── research_lab/
│   ├── cli.py
│   ├── main.py
│   ├── __main__.py
│   ├── autoresearch_loop.py
│   ├── workflows/
│   ├── configs/
│   └── ...
│
├── tests/
│   ├── test_feature_engine.py
│   ├── test_models.py
│   ├── test_performance.py
│   ├── test_research_lab_smoke.py
│   ├── test_settings.py
│   └── test_settings_adapter.py
│
└── docs/
    ├── BLUEPRINT_V1.md
    ├── BLUEPRINT_RESEARCH_LAB.md
    ├── MILESTONE_TRACKER.md
    └── audits/
```

## 5. Odpowiedzialność modułów

### 5.1 main.py
Cienki entrypoint:
- ładuje config,
- inicjalizuje DB,
- odpala orchestrator,
- obsługuje graceful shutdown.

### 5.2 orchestrator.py
Serce przepływu:
- uruchamia startup recovery i feedy,
- scheduluje health check, monitoring pozycji i 15m decision cycle,
- koordynuje feature/regime/signal/governance/risk/execution,
- w `safe_mode` dalej zarządza istniejącymi pozycjami, ale blokuje nowe wejścia,
- nie liczy feature samodzielnie.

### 5.3 settings.py
Jedno źródło prawdy dla:
- parametrów strategii,
- risk limits,
- API settings,
- timeoutów,
- pathów,
- trybu paper/live.

Zero live edits. Zmiana configu = restart.

### 5.4 data/*

**websocket_client.py** — Obsługa: aggTrades, forceOrder, reconnect, heartbeat, local buffering.

**rest_client.py** — Obsługa: klines, funding history, open interest, bookTicker, exchange info.

**market_data.py** — Łączy REST + WS w spójny snapshot.

**etf_bias_collector.py** — Pasywny zapis dziennego ETF biasu. Nie wpływa na v1.0 trading loop.

**exchange_guard.py** — Sprawdza: symbol rules, precision, min qty, min notional, leverage limits, isolated mode, tick size / step size.

### 5.5 core/*

**models.py** — Dataclasses: MarketSnapshot, Features, RegimeState, SignalCandidate, ExecutableSignal, Position, TradeLog, DailyStats, BotState.

**feature_engine.py** — Liczy: ATR, EMA50/200, equal highs/lows, sweep/reclaim, funding SMA/percentile, CVD, TFI, forceOrder rate, OI z-score.

**regime_engine.py** — Finite State Machine: NORMAL, UPTREND, DOWNTREND, COMPRESSION, CROWDED_LEVERAGE, POST_LIQUIDATION.

**signal_engine.py** — Generuje tylko SignalCandidate.

**governance.py** — Filtruje zachowanie systemu: cooldown po lossie, clustering, duplicate level avoidance, session logic, no-trade windows, trade frequency sanity.

**risk_engine.py** — Twarde limity: risk per trade, daily DD, weekly DD, max positions, max leverage, min RR, max hold time, max consecutive losses.

### 5.6 execution/*

**paper_execution_engine.py** — Symuluje order lifecycle.

**live_execution_engine.py** — Realna integracja z Binance.

**order_manager.py** — Składanie / anulowanie / modyfikacja zleceń.

**recovery.py** — Startup sync + recovery flow.

### 5.7 storage/*

**db.py** — Połączenie SQLite.

**schema.sql** — Definicje tabel.

**repositories.py** — Operacje CRUD.

**state_store.py** — Trwały runtime state, drawdowny i widoki stanu dla governance/risk.

**position_persister.py** — Persystencja pozycji i execution-state dla execution layer.

### 5.8 monitoring/*

**audit_logger.py** — Pełny ślad decyzji.

**telegram_notifier.py** — Alerty: entry, exit, kill-switch, error, daily summary.

**health.py** — Status komponentów: websocket alive, db writable, exchange reachable.

**metrics.py** — Podstawowe liczniki i statystyki.

### 5.9 backtest/*
Oddzielony całkowicie od live: replay danych, fill assumptions, fee/slippage, performance metrics.

### 5.10 research/*
Offline only: analiza trade'ów, późniejszy LLM post-trade review.

## 6. Główne modele danych

### 6.1 MarketSnapshot
```python
@dataclass
class MarketSnapshot:
    symbol: str
    timestamp: datetime
    price: float
    bid: float
    ask: float
    candles_15m: list
    candles_1h: list
    candles_4h: list
    funding_history: list
    open_interest: float
    aggtrades_bucket_60s: dict
    aggtrades_bucket_15m: dict
    force_order_events_60s: list
    etf_bias_daily: float | None
    dxy_daily: float | None
```

### 6.2 Features
```python
@dataclass
class Features:
    schema_version: str
    config_hash: str
    timestamp: datetime
    atr_15m: float
    atr_4h: float
    atr_4h_norm: float
    ema50_4h: float
    ema200_4h: float
    equal_lows: list[float]
    equal_highs: list[float]
    sweep_detected: bool
    reclaim_detected: bool
    sweep_level: float | None
    sweep_depth_pct: float | None
    funding_8h: float
    funding_sma3: float
    funding_sma9: float
    funding_pct_60d: float
    oi_value: float
    oi_zscore_60d: float
    oi_delta_pct: float
    cvd_15m: float
    cvd_bullish_divergence: bool
    cvd_bearish_divergence: bool
    tfi_60s: float
    force_order_rate_60s: float
    force_order_spike: bool
    force_order_decreasing: bool
    passive_etf_bias_5d: float | None
```

### 6.3 RegimeState
```python
class RegimeState(str, Enum):
    NORMAL = "normal"
    UPTREND = "uptrend"
    DOWNTREND = "downtrend"
    COMPRESSION = "compression"
    CROWDED_LEVERAGE = "crowded_leverage"
    POST_LIQUIDATION = "post_liquidation"
```

### 6.4 SignalCandidate
```python
@dataclass
class SignalCandidate:
    signal_id: str
    timestamp: datetime
    direction: Literal["LONG", "SHORT"]
    setup_type: str
    entry_reference: float
    invalidation_level: float
    tp_reference_1: float
    tp_reference_2: float
    confluence_score: float
    regime: RegimeState
    reasons: list[str]
    features_json: dict
```

### 6.5 ExecutableSignal
```python
@dataclass
class ExecutableSignal:
    signal_id: str
    timestamp: datetime
    direction: Literal["LONG", "SHORT"]
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    rr_ratio: float
    approved_by_governance: bool
    governance_notes: list[str]
```

### 6.6 Position
```python
@dataclass
class Position:
    position_id: str
    symbol: str
    direction: Literal["LONG", "SHORT"]
    status: Literal["OPEN", "PARTIAL", "CLOSED"]
    entry_price: float
    size: float
    leverage: int
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    opened_at: datetime
    updated_at: datetime
    signal_id: str
```

### 6.7 TradeLog
```python
@dataclass
class TradeLog:
    trade_id: str
    signal_id: str
    opened_at: datetime
    closed_at: datetime | None
    direction: str
    regime: str
    confluence_score: float
    entry_price: float
    exit_price: float | None
    size: float
    fees: float
    slippage_bps: float
    pnl_abs: float
    pnl_r: float
    mae: float
    mfe: float
    exit_reason: str | None
    features_at_entry_json: dict
```

### 6.8 BotState
```python
@dataclass
class BotState:
    mode: Literal["PAPER", "LIVE"]
    healthy: bool
    safe_mode: bool
    open_positions_count: int
    consecutive_losses: int
    daily_dd_pct: float
    weekly_dd_pct: float
    last_trade_at: datetime | None
    last_error: str | None
```

## 7. SQLite schema

### Tabele obowiązkowe

| Table | Key Columns |
|---|---|
| candles | id, symbol, timeframe, open_time, open, high, low, close, volume |
| funding | id, symbol, funding_time, funding_rate |
| open_interest | id, symbol, timestamp, oi_value |
| aggtrade_buckets | id, symbol, bucket_time, timeframe, taker_buy_volume, taker_sell_volume, tfi, cvd |
| force_orders | id, symbol, event_time, side, qty, price |
| signal_candidates | signal_id, timestamp, direction, setup_type, confluence_score, regime, reasons_json, features_json, schema_version, config_hash |
| executable_signals | signal_id, timestamp, direction, entry_price, stop_loss, take_profit_1, take_profit_2, rr_ratio, governance_notes_json |
| positions | position_id, signal_id, symbol, direction, status, entry_price, size, leverage, stop_loss, take_profit_1, take_profit_2, opened_at, updated_at |
| executions | execution_id, position_id, order_type, side, requested_price, filled_price, qty, fees, slippage_bps, executed_at |
| trade_log | trade_id, signal_id, position_id, opened_at, closed_at, direction, regime, confluence_score, entry_price, exit_price, size, fees_total, slippage_bps_avg, pnl_abs, pnl_r, mae, mfe, exit_reason, features_at_entry_json, schema_version, config_hash |
| bot_state | id, timestamp, mode, healthy, safe_mode, open_positions_count, consecutive_losses, daily_dd_pct, weekly_dd_pct, last_trade_at, last_error |
| daily_metrics | date, trades_count, wins, losses, pnl_abs, pnl_r_sum, daily_dd_pct, expectancy_r |
| daily_external_bias | date, etf_bias_5d, dxy_close, notes |
| alerts_errors | id, timestamp, type, severity, component, message, payload_json |

## 8. Finalne parametry v1.0

```
SYMBOL = "BTCUSDT"

TF_SETUP = "15m"
TF_CONTEXT = "1h"
TF_BIAS = "4h"

ATR_PERIOD = 14
EMA_FAST = 50
EMA_SLOW = 200

EQUAL_LEVEL_LOOKBACK = 50
EQUAL_LEVEL_TOL_ATR = 0.25
SWEEP_BUF_ATR = 0.15
RECLAIM_BUF_ATR = 0.05
WICK_MIN_ATR = 0.40

FUNDING_WINDOW_DAYS = 60
OI_Z_WINDOW_DAYS = 60

CONFLUENCE_MIN = 3.0

RISK_PER_TRADE_PCT = 0.01
MAX_LEVERAGE = 5
HIGH_VOL_LEVERAGE = 3
MIN_RR = 2.8

MAX_OPEN_POSITIONS = 2
MAX_TRADES_PER_DAY = 3
MAX_CONSECUTIVE_LOSSES = 3
DAILY_DD_LIMIT = 0.03
WEEKLY_DD_LIMIT = 0.06
MAX_HOLD_HOURS = 24

ENTRY_TIMEOUT_SECONDS = 90
POSITION_MONITOR_INTERVAL_SECONDS = 15
DECISION_CYCLE_ON_15M_CLOSE = True
```

## 9. Startup / recovery flow

Przy każdym uruchomieniu bot wykonuje:

### 9.1 Exchange sync
- sprawdza aktywne pozycje na Binance,
- sprawdza aktywne zlecenia,
- sprawdza isolated mode i leverage.

### 9.2 Local state sync
- ładuje ostatni bot_state,
- ładuje otwarte positions,
- porównuje z danymi giełdy.

### 9.3 Niespójności

Jeśli:
- pozycja jest na giełdzie, ale nie ma jej lokalnie → **unknown_position**
- pozycja lokalna istnieje, ale nie ma jej na giełdzie → **phantom_position**
- są otwarte zlecenia bez pozycji → **orphan_orders**

to:
- loguje alert,
- ustawia safe_mode = True,
- nie szuka nowych trade'ów,
- przechodzi w tryb wyłącznie zarządzania istniejącymi pozycjami lub oczekiwania na ręczny review.

### 9.4 Cold start success

Jeśli wszystko jest spójne:
- wznawia monitoring pozycji,
- uruchamia feedy,
- przechodzi do normal mode.

## 10. Workflow end-to-end

### 10.1 Live loop

Start procesu:
1. `main.py` ładuje `AppSettings`, inicjalizuje SQLite i uruchamia `BotOrchestrator`.
2. `RecoveryCoordinator` wykonuje startup sync; przy niespójności ustawia `safe_mode=True`.
3. Orchestrator uruchamia feedy i harmonogram runtime.

Pętla runtime:
1. `HealthMonitor` działa niezależnie od cyklu decyzyjnego.
2. Monitoring pozycji działa również w `safe_mode`, żeby domknąć lifecycle otwartych trade'ów.
3. Na każdej granicy 15m orchestrator odświeża runtime state i buduje `MarketSnapshot`.
4. Najpierw przetwarzany jest trade lifecycle i settlement już otwartych pozycji.
5. Jeśli `safe_mode` jest aktywny, nowe wejścia są pomijane.
6. W przeciwnym razie pipeline działa deterministycznie:
   `MarketSnapshot -> Features -> RegimeState -> SignalCandidate -> Governance -> ExecutableSignal -> Risk -> Execution`.
7. Po fill execution layer zapisuje pozycję, a storage aktualizuje persistent bot state.

Każde veto, błąd, lifecycle event i alert przechodzą przez `AuditLogger`, `TelegramNotifier` i SQLite persistence.

### 10.2 Daily loop
- zapisz pasywny ETF bias,
- zapisz DXY,
- policz daily metrics,
- wyślij summary.

### 10.3 Post-trade loop

Po zamknięciu trade'a:
- zapisz pełny trade_log,
- policz MAE/MFE/PnL_R,
- zaktualizuj DD i consecutive losses,
- uruchom kill-switch jeśli trzeba.

## 11. Kill-switches v1.0

Bot natychmiast wstrzymuje nowe wejścia, jeśli:
- daily DD > 3%
- weekly DD > 6%
- 3 straty z rzędu
- więcej niż 2 krytyczne błędy execution
- exchange sync failed
- state inconsistency unresolved
- pre-defined no-trade macro window
- safe mode aktywny

**Emergency flatten:** tylko jeśli system wykrywa krytyczną niespójność lub aktywną pozycję bez zdolności zarządzania nią.

## 12. Kolejność developmentu

| Phase | Scope | Status |
|---|---|---|
| **A — fundament** | settings.py, models.py, schema.sql, db.py + repositories.py, exchange_guard.py | MVP_DONE |
| **B — dane** | rest_client.py, websocket_client.py, market_data.py, bootstrap_history.py | MVP_DONE |
| **C — logika** | feature_engine.py, regime_engine.py, signal_engine.py, governance.py, risk_engine.py | MVP_DONE |
| **D — execution** | paper_execution_engine.py, execution_engine.py, live_execution_engine.py, order_manager.py, recovery.py | MVP_DONE |
| **E — monitoring** | audit_logger.py, telegram_notifier.py, health.py, metrics.py | MVP_DONE |
| **F — orchestracja** | orchestrator.py, main.py, run_paper.py | MVP_DONE |
| **G — backtest** | replay_loader.py, fill_model.py, performance.py, backtest_runner.py | MVP_DONE |
| **H — research** | analyze_trades.py, llm_post_trade_review.py | MVP_DONE |

**Note:** All blueprint phases A-H are MVP_DONE. Cross-cutting milestones for runtime state persistence, trade lifecycle + PnL settlement, drawdown persistence, recovery startup sync, CI/test foundation, and tracked tech-debt cleanup are closed at `v1.0-baseline`.

## 13. Definition of Done dla MVP v1.0

MVP jest gotowe, jeśli:

### Technicznie
- bot uruchamia się bez błędu,
- potrafi pobierać dane,
- potrafi policzyć features,
- generuje signal candidates,
- governance i risk działają,
- paper execution działa,
- SQLite zapisuje pełny audit trail,
- recovery działa po restarcie.

### Strategicznie
- backtest na 6–12 miesiącach daje:
  - dodatnie expectancy po kosztach,
  - minimum > 0.3R,
  - sensowny drawdown,
  - brak oczywistego curve fittingu.

### Operacyjnie
- minimum 30 dni paper tradingu lub 40–60 zamkniętych trade'ów
- stabilność feedów,
- brak krytycznych niespójności stanu,
- poprawne alerty i daily summaries.

### Dopiero potem
- minimal live trading
- mały size
- bez LLM w pętli live

## 14. Roadmapa po v1.0

### v1.1
- passive ETF bias aktywnie w governance
- DXY kill-switch
- LLM post-trade reviewer
- daily LLM review

### v1.2
- LLM pre-trade veto / size reduction
- strict JSON contract
- timeout fallback
- Volume Profile

### v2.0
- research agent offline
- OBI / depth
- liquidity collapse regime
- adaptive parameter proposals
