#!/usr/bin/env python3
"""Manual script to refresh candles from Binance REST API."""

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from data.rest_api_client import BinanceFuturesRestClient, RestApiClientConfig
from storage.repositories import get_connection, upsert_candles


def main():
    """Fetch and store latest candles."""
    # Get config from env
    api_key = os.getenv("BINANCE_API_KEY", "")
    api_secret = os.getenv("BINANCE_API_SECRET", "")
    proxy_enabled = os.getenv("PROXY_ENABLED", "false").lower() == "true"

    config = RestApiClientConfig(
        api_base_url="https://fapi.binance.com",
        api_key=api_key,
        api_secret=api_secret,
        proxy_enabled=proxy_enabled,
    )

    client = BinanceFuturesRestClient(config)
    conn = get_connection()

    # Fetch last 7 days of 15m candles
    symbol = "BTCUSDT"
    interval = "15m"
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=7)

    print(f"Fetching {symbol} {interval} candles from {start_time} to {end_time}")

    try:
        candles = client.get_klines(
            symbol=symbol,
            interval=interval,
            start_time=int(start_time.timestamp() * 1000),
            end_time=int(end_time.timestamp() * 1000),
            limit=1000,
        )

        if candles:
            upsert_candles(conn, symbol, interval, candles)
            conn.commit()
            print(f"✅ Stored {len(candles)} candles")
            print(f"   First: {candles[0]['open_time']}")
            print(f"   Last:  {candles[-1]['open_time']}")
        else:
            print("❌ No candles returned")

    except Exception as exc:
        print(f"❌ Error: {exc}")
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
