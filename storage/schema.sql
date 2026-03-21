PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS candles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    open_time TEXT NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume REAL NOT NULL,
    UNIQUE(symbol, timeframe, open_time)
);

CREATE TABLE IF NOT EXISTS funding (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    funding_time TEXT NOT NULL,
    funding_rate REAL NOT NULL,
    UNIQUE(symbol, funding_time)
);

CREATE TABLE IF NOT EXISTS open_interest (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    oi_value REAL NOT NULL,
    UNIQUE(symbol, timestamp)
);

CREATE TABLE IF NOT EXISTS aggtrade_buckets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    bucket_time TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    taker_buy_volume REAL NOT NULL,
    taker_sell_volume REAL NOT NULL,
    tfi REAL NOT NULL,
    cvd REAL NOT NULL,
    UNIQUE(symbol, timeframe, bucket_time)
);

CREATE TABLE IF NOT EXISTS force_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    event_time TEXT NOT NULL,
    side TEXT NOT NULL CHECK(side IN ('BUY', 'SELL')),
    qty REAL NOT NULL,
    price REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS signal_candidates (
    signal_id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    direction TEXT NOT NULL CHECK(direction IN ('LONG', 'SHORT')),
    setup_type TEXT NOT NULL,
    confluence_score REAL NOT NULL,
    regime TEXT NOT NULL,
    reasons_json TEXT NOT NULL,
    features_json TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    config_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS executable_signals (
    signal_id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    direction TEXT NOT NULL CHECK(direction IN ('LONG', 'SHORT')),
    entry_price REAL NOT NULL,
    stop_loss REAL NOT NULL,
    take_profit_1 REAL NOT NULL,
    take_profit_2 REAL NOT NULL,
    rr_ratio REAL NOT NULL,
    governance_notes_json TEXT NOT NULL,
    FOREIGN KEY (signal_id) REFERENCES signal_candidates(signal_id)
);

CREATE TABLE IF NOT EXISTS positions (
    position_id TEXT PRIMARY KEY,
    signal_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL CHECK(direction IN ('LONG', 'SHORT')),
    status TEXT NOT NULL CHECK(status IN ('OPEN', 'PARTIAL', 'CLOSED')),
    entry_price REAL NOT NULL,
    size REAL NOT NULL,
    leverage INTEGER NOT NULL,
    stop_loss REAL NOT NULL,
    take_profit_1 REAL NOT NULL,
    take_profit_2 REAL NOT NULL,
    opened_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (signal_id) REFERENCES executable_signals(signal_id)
);

CREATE TABLE IF NOT EXISTS executions (
    execution_id TEXT PRIMARY KEY,
    position_id TEXT NOT NULL,
    order_type TEXT NOT NULL,
    side TEXT NOT NULL CHECK(side IN ('BUY', 'SELL')),
    requested_price REAL,
    filled_price REAL,
    qty REAL NOT NULL,
    fees REAL NOT NULL DEFAULT 0,
    slippage_bps REAL NOT NULL DEFAULT 0,
    executed_at TEXT NOT NULL,
    FOREIGN KEY (position_id) REFERENCES positions(position_id)
);

CREATE TABLE IF NOT EXISTS trade_log (
    trade_id TEXT PRIMARY KEY,
    signal_id TEXT NOT NULL,
    position_id TEXT NOT NULL,
    opened_at TEXT NOT NULL,
    closed_at TEXT,
    direction TEXT NOT NULL CHECK(direction IN ('LONG', 'SHORT')),
    regime TEXT NOT NULL,
    confluence_score REAL NOT NULL,
    entry_price REAL NOT NULL,
    exit_price REAL,
    size REAL NOT NULL,
    fees_total REAL NOT NULL DEFAULT 0,
    slippage_bps_avg REAL NOT NULL DEFAULT 0,
    pnl_abs REAL NOT NULL DEFAULT 0,
    pnl_r REAL NOT NULL DEFAULT 0,
    mae REAL NOT NULL DEFAULT 0,
    mfe REAL NOT NULL DEFAULT 0,
    exit_reason TEXT,
    features_at_entry_json TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    config_hash TEXT NOT NULL,
    FOREIGN KEY (signal_id) REFERENCES signal_candidates(signal_id),
    FOREIGN KEY (position_id) REFERENCES positions(position_id)
);

CREATE TABLE IF NOT EXISTS bot_state (
    id INTEGER PRIMARY KEY CHECK(id = 1),
    timestamp TEXT NOT NULL,
    mode TEXT NOT NULL CHECK(mode IN ('PAPER', 'LIVE')),
    healthy INTEGER NOT NULL CHECK(healthy IN (0, 1)),
    safe_mode INTEGER NOT NULL CHECK(safe_mode IN (0, 1)),
    open_positions_count INTEGER NOT NULL DEFAULT 0,
    consecutive_losses INTEGER NOT NULL DEFAULT 0,
    daily_dd_pct REAL NOT NULL DEFAULT 0,
    weekly_dd_pct REAL NOT NULL DEFAULT 0,
    last_trade_at TEXT,
    last_error TEXT
);

CREATE TABLE IF NOT EXISTS daily_metrics (
    date TEXT PRIMARY KEY,
    trades_count INTEGER NOT NULL DEFAULT 0,
    wins INTEGER NOT NULL DEFAULT 0,
    losses INTEGER NOT NULL DEFAULT 0,
    pnl_abs REAL NOT NULL DEFAULT 0,
    pnl_r_sum REAL NOT NULL DEFAULT 0,
    daily_dd_pct REAL NOT NULL DEFAULT 0,
    expectancy_r REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS daily_external_bias (
    date TEXT PRIMARY KEY,
    etf_bias_5d REAL,
    dxy_close REAL,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS alerts_errors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    type TEXT NOT NULL,
    severity TEXT NOT NULL,
    component TEXT NOT NULL,
    message TEXT NOT NULL,
    payload_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_candles_symbol_tf_time
    ON candles(symbol, timeframe, open_time);
CREATE INDEX IF NOT EXISTS idx_funding_symbol_time
    ON funding(symbol, funding_time);
CREATE INDEX IF NOT EXISTS idx_open_interest_symbol_time
    ON open_interest(symbol, timestamp);
CREATE INDEX IF NOT EXISTS idx_aggtrade_symbol_tf_time
    ON aggtrade_buckets(symbol, timeframe, bucket_time);
CREATE INDEX IF NOT EXISTS idx_force_orders_symbol_time
    ON force_orders(symbol, event_time);
CREATE INDEX IF NOT EXISTS idx_signal_candidates_timestamp
    ON signal_candidates(timestamp);
CREATE INDEX IF NOT EXISTS idx_executable_signals_timestamp
    ON executable_signals(timestamp);
CREATE INDEX IF NOT EXISTS idx_positions_status_updated_at
    ON positions(status, updated_at);
CREATE INDEX IF NOT EXISTS idx_executions_position_executed
    ON executions(position_id, executed_at);
CREATE INDEX IF NOT EXISTS idx_trade_log_closed_at
    ON trade_log(closed_at);
CREATE INDEX IF NOT EXISTS idx_alerts_errors_ts_severity
    ON alerts_errors(timestamp, severity);
