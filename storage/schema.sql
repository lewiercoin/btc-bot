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

CREATE TABLE IF NOT EXISTS oi_samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    oi_value REAL NOT NULL,
    source TEXT NOT NULL DEFAULT 'unknown',
    captured_at TEXT NOT NULL,
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

CREATE TABLE IF NOT EXISTS cvd_price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    bar_time TEXT NOT NULL,
    price_close REAL NOT NULL,
    cvd REAL NOT NULL,
    tfi REAL,
    source TEXT NOT NULL DEFAULT 'unknown',
    captured_at TEXT NOT NULL,
    UNIQUE(symbol, timeframe, bar_time)
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
    snapshot_id TEXT,
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
    funding_paid REAL NOT NULL DEFAULT 0,
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
    last_error TEXT,
    safe_mode_entry_at TEXT
);

CREATE TABLE IF NOT EXISTS runtime_metrics (
    id INTEGER PRIMARY KEY CHECK(id = 1),
    updated_at TEXT NOT NULL,
    last_decision_cycle_started_at TEXT,
    last_decision_cycle_finished_at TEXT,
    last_decision_outcome TEXT,
    decision_cycle_status TEXT,
    last_snapshot_built_at TEXT,
    last_snapshot_symbol TEXT,
    last_15m_candle_open_at TEXT,
    last_1h_candle_open_at TEXT,
    last_4h_candle_open_at TEXT,
    last_ws_message_at TEXT,
    last_health_check_at TEXT,
    last_runtime_warning TEXT,
    feature_quality_json TEXT,
    config_hash TEXT
);

CREATE TABLE IF NOT EXISTS decision_outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_timestamp TEXT NOT NULL,
    outcome_group TEXT NOT NULL,
    outcome_reason TEXT NOT NULL,
    regime TEXT,
    config_hash TEXT NOT NULL,
    signal_id TEXT,
    snapshot_id TEXT,
    feature_snapshot_id TEXT,
    details_json TEXT,
    context_session_label TEXT,
    context_volatility_label TEXT,
    context_policy_version TEXT,
    context_eligible INTEGER,
    context_block_reason TEXT,
    context_neutral_mode_active INTEGER
);

CREATE TABLE IF NOT EXISTS market_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    cycle_timestamp TEXT NOT NULL,
    exchange_timestamp TEXT,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume REAL NOT NULL,
    funding_rate REAL,
    open_interest REAL,
    bid_price REAL,
    ask_price REAL,
    source TEXT NOT NULL,
    latency_ms REAL,
    data_quality_flag TEXT NOT NULL,
    book_ticker_json TEXT NOT NULL,
    open_interest_json TEXT NOT NULL,
    candles_15m_json TEXT NOT NULL,
    candles_1h_json TEXT NOT NULL,
    candles_4h_json TEXT NOT NULL,
    funding_history_json TEXT NOT NULL,
    aggtrade_events_60s_json TEXT NOT NULL,
    aggtrade_events_15m_json TEXT NOT NULL,
    aggtrade_bucket_60s_json TEXT NOT NULL,
    aggtrade_bucket_15m_json TEXT NOT NULL,
    force_order_events_60s_json TEXT NOT NULL,
    source_meta_json TEXT,
    captured_at TEXT NOT NULL,
    -- Quant-grade lineage: per-input exchange timestamps
    candles_15m_exchange_ts TEXT,
    candles_1h_exchange_ts TEXT,
    candles_4h_exchange_ts TEXT,
    funding_exchange_ts TEXT,
    oi_exchange_ts TEXT,
    aggtrades_exchange_ts TEXT,
    force_orders_exchange_ts TEXT,
    -- Quant-grade lineage: snapshot build timing
    snapshot_build_started_at TEXT,
    snapshot_build_finished_at TEXT
);

CREATE TABLE IF NOT EXISTS feature_snapshots (
    feature_snapshot_id TEXT PRIMARY KEY,
    snapshot_id TEXT NOT NULL,
    cycle_timestamp TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    config_hash TEXT NOT NULL,
    features_json TEXT NOT NULL,
    quality_json TEXT NOT NULL,
    captured_at TEXT NOT NULL,
    FOREIGN KEY (snapshot_id) REFERENCES market_snapshots(snapshot_id)
);

CREATE TABLE IF NOT EXISTS config_snapshots (
    config_hash TEXT PRIMARY KEY,
    captured_at TEXT NOT NULL,
    strategy_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS safe_mode_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    trigger TEXT,
    reason TEXT,
    probe_successes INTEGER DEFAULT 0,
    probe_failures INTEGER DEFAULT 0,
    remaining_triggers TEXT,
    timestamp TEXT NOT NULL
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
CREATE INDEX IF NOT EXISTS idx_oi_samples_symbol_time
    ON oi_samples(symbol, timestamp);
CREATE INDEX IF NOT EXISTS idx_aggtrade_symbol_tf_time
    ON aggtrade_buckets(symbol, timeframe, bucket_time);
CREATE INDEX IF NOT EXISTS idx_cvd_price_history_symbol_tf_time
    ON cvd_price_history(symbol, timeframe, bar_time);
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
CREATE INDEX IF NOT EXISTS idx_decision_outcomes_ts_group
    ON decision_outcomes(cycle_timestamp, outcome_group);
CREATE INDEX IF NOT EXISTS idx_decision_outcomes_reason
    ON decision_outcomes(outcome_reason, cycle_timestamp);
CREATE INDEX IF NOT EXISTS idx_market_snapshots_cycle_ts
    ON market_snapshots(cycle_timestamp);
CREATE INDEX IF NOT EXISTS idx_feature_snapshots_snapshot_id
    ON feature_snapshots(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_feature_snapshots_cycle_ts
    ON feature_snapshots(cycle_timestamp);
CREATE INDEX IF NOT EXISTS idx_alerts_errors_ts_severity
    ON alerts_errors(timestamp, severity);
