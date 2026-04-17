#!/usr/bin/env python3
"""Manual script to refresh candles from Binance REST API."""

import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from data.rest_client import BinanceFuturesRestClient, RestClientConfig
from data.proxy_transport import ProxyTransport


def get_connection() -> sqlite3.Connection:
    """Get database connection."""
    db_path = Path(__file__).parent.parent / "storage" / "btc_bot.db"
    return sqlite3.connect(str(db_path))


def upsert_candles(conn: sqlite3.Connection, symbol: str, timeframe: str, klines: list[list]) -> int:
    """Insert or update candles from Binance klines format."""
    # Binance klines format: [open_time, open, high, low, close, volume, close_time, ...]
    rows = [
        (
            symbol,
            timeframe,
            datetime.fromtimestamp(k[0] / 1000, tz=timezone.utc).isoformat(),
            float(k[1]),  # open
            float(k[2]),  # high
            float(k[3]),  # low
            float(k[4]),  # close
            float(k[5]),  # volume
        )
        for k in klines
    ]

    conn.executemany(
        """
        INSERT INTO candles (symbol, timeframe, open_time, open, high, low, close, volume)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(symbol, timeframe, open_time) DO UPDATE SET
            open = excluded.open,
            high = excluded.high,
            low = excluded.low,
            close = excluded.close,
            volume = excluded.volume
        """,
        rows,
    )
    return len(rows)


def main():
    """Fetch and store latest candles."""
    # Get config from env
    proxy_enabled = os.getenv("PROXY_ENABLED", "false").lower() == "true"

    # Setup proxy if enabled
    proxy_transport = None
    if proxy_enabled:
        proxy_transport = ProxyTransport(
            proxy_url=os.getenv("SOCKS_PROXY_URL", "socks5://80.240.17.161:1080"),
            proxy_type="socks5",
            sticky_minutes=60,
        )

    config = RestClientConfig(
        base_url="https://fapi.binance.com",
        timeout_seconds=30,
        max_retries=3,
        proxy_transport=proxy_transport,
    )

    client = BinanceFuturesRestClient(config)
    conn = get_connection()

    # Fetch last 7 days of 15m candles
    symbol = "BTCUSDT"
    interval = "15m"
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=7)

    print(f"Fetching {symbol} {interval} candles...")
    print(f"  Period: {start_time.strftime('%Y-%m-%d %H:%M')} → {end_time.strftime('%Y-%m-%d %H:%M')}")

    try:
        klines = client.fetch_klines(
            symbol=symbol,
            interval=interval,
            start_time=int(start_time.timestamp() * 1000),
            end_time=int(end_time.timestamp() * 1000),
            limit=1000,
        )

        if klines:
            count = upsert_candles(conn, symbol, interval, klines)
            conn.commit()
            first_time = datetime.fromtimestamp(klines[0][0] / 1000, tz=timezone.utc)
            last_time = datetime.fromtimestamp(klines[-1][0] / 1000, tz=timezone.utc)
            print(f"✅ Stored {count} candles")
            print(f"   First: {first_time.isoformat()}")
            print(f"   Last:  {last_time.isoformat()}")
        else:
            print("❌ No candles returned from API")

    except Exception as exc:
        print(f"❌ Error: {exc}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
