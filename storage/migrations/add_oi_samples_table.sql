CREATE TABLE IF NOT EXISTS oi_samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    oi_value REAL NOT NULL,
    source TEXT NOT NULL DEFAULT 'unknown',
    captured_at TEXT NOT NULL,
    UNIQUE(symbol, timestamp)
);

CREATE INDEX IF NOT EXISTS idx_oi_samples_symbol_time
    ON oi_samples(symbol, timestamp);
