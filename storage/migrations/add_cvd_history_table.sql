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

CREATE INDEX IF NOT EXISTS idx_cvd_price_history_symbol_tf_time
    ON cvd_price_history(symbol, timeframe, bar_time);
