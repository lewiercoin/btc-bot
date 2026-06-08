"""Tests for multi-symbol WebSocket support.

Milestone: MULTI_ASSET_WEBSOCKET_V1
"""
from __future__ import annotations

from datetime import datetime, timezone

from data.websocket_client import (
    BinanceFuturesWebsocketClient,
    WebsocketClientConfig,
    normalize_ws_agg_trade_event,
    normalize_ws_force_order_event,
)


NOW = datetime.now(timezone.utc)


def _make_config() -> WebsocketClientConfig:
    return WebsocketClientConfig(
        ws_base_url="wss://fstream.binance.com/ws",
        ws_market_base_url="wss://fstream.binance.com/stream",
        heartbeat_seconds=30,
        reconnect_seconds=5,
        agg_trade_buffer_size=100,
        force_order_buffer_size=50,
    )


# --- Test: Multi-symbol initialization ---

def test_multi_symbol_client_initializes_per_symbol_buffers() -> None:
    """Client creates separate buffers for each symbol."""
    config = _make_config()
    client = BinanceFuturesWebsocketClient(config, symbols=["BTCUSDT", "ETHUSDT", "SOLUSDT"])
    assert client._symbols == ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    assert "BTCUSDT" in client._agg_trade_events
    assert "ETHUSDT" in client._agg_trade_events
    assert "SOLUSDT" in client._agg_trade_events
    assert "BTCUSDT" in client._force_order_events
    assert "ETHUSDT" in client._force_order_events
    assert "SOLUSDT" in client._force_order_events


def test_single_symbol_client_initializes_single_buffer() -> None:
    """Backward compatibility: single symbol still works."""
    config = _make_config()
    client = BinanceFuturesWebsocketClient(config, symbols=["BTCUSDT"])
    assert client._symbols == ["BTCUSDT"]
    assert "BTCUSDT" in client._agg_trade_events
    assert len(client._agg_trade_events) == 1


def test_default_symbols_fallback_to_btc() -> None:
    """No symbols provided defaults to BTCUSDT."""
    config = _make_config()
    client = BinanceFuturesWebsocketClient(config)
    assert client._symbols == ["BTCUSDT"]


# --- Test: Stream URL generation ---

def test_market_stream_url_multi_symbol() -> None:
    """Market stream URL includes all symbols with aggTrade and forceOrder."""
    config = _make_config()
    client = BinanceFuturesWebsocketClient(config, symbols=["BTCUSDT", "ETHUSDT"])
    url = client._build_market_stream_url()
    assert url.startswith("wss://fstream.binance.com/market/stream?streams=")
    assert "btcusdt@aggTrade" in url
    assert "btcusdt@forceOrder" in url
    assert "ethusdt@aggTrade" in url
    assert "ethusdt@forceOrder" in url


def test_legacy_stream_url_multi_symbol() -> None:
    """Legacy builder stays pinned to the live market endpoint."""
    config = _make_config()
    client = BinanceFuturesWebsocketClient(config, symbols=["BTCUSDT", "SOLUSDT"])
    url = client._build_legacy_stream_url()
    assert url.startswith("wss://fstream.binance.com/market/stream?streams=")
    assert "btcusdt@aggTrade" in url
    assert "btcusdt@forceOrder" in url
    assert "solusdt@aggTrade" in url
    assert "solusdt@forceOrder" in url


# --- Test: Per-symbol aggTrade routing ---

def test_agg_trade_routes_to_correct_symbol_buffer() -> None:
    """aggTrade event with stream field routes to correct symbol buffer."""
    config = _make_config()
    client = BinanceFuturesWebsocketClient(config, symbols=["BTCUSDT", "ETHUSDT"])

    # Simulate ETHUSDT aggTrade message
    payload = {
        "stream": "ethusdt@aggTrade",
        "data": {
            "e": "aggTrade",
            "s": "ETHUSDT",
            "a": 123456,
            "T": 1716460800000,
            "p": "3000.50",
            "q": "1.5",
            "m": False,
        },
    }
    client._handle_message('{"stream": "ethusdt@aggTrade", "data": {"e": "aggTrade", "s": "ETHUSDT", "a": 123456, "T": 1716460800000, "p": "3000.50", "q": "1.5", "m": false}}')

    # ETH buffer should have event, BTC buffer should not
    assert len(client._agg_trade_events["ETHUSDT"]) == 1
    assert len(client._agg_trade_events["BTCUSDT"]) == 0
    assert client._agg_trade_events["ETHUSDT"][0]["symbol"] == "ETHUSDT"


def test_agg_trade_fallback_to_event_symbol_if_stream_missing() -> None:
    """If stream field missing, use symbol from event data."""
    config = _make_config()
    client = BinanceFuturesWebsocketClient(config, symbols=["BTCUSDT", "SOLUSDT"])

    # Message without stream field
    payload = {
        "e": "aggTrade",
        "s": "SOLUSDT",
        "a": 789012,
        "T": 1716460800000,
        "p": "150.25",
        "q": "10.0",
        "m": True,
    }
    client._handle_message('{"e": "aggTrade", "s": "SOLUSDT", "a": 789012, "T": 1716460800000, "p": "150.25", "q": "10.0", "m": true}')

    assert len(client._agg_trade_events["SOLUSDT"]) == 1
    assert len(client._agg_trade_events["BTCUSDT"]) == 0


# --- Test: Per-symbol forceOrder routing ---

def test_force_order_routes_to_correct_symbol_buffer() -> None:
    """forceOrder event with stream field routes to correct symbol buffer."""
    config = _make_config()
    client = BinanceFuturesWebsocketClient(config, symbols=["BTCUSDT", "ETHUSDT"])

    # Simulate BTCUSDT forceOrder message
    payload = {
        "stream": "btcusdt@forceOrder",
        "data": {
            "e": "forceOrder",
            "o": {
                "s": "BTCUSDT",
                "S": "SELL",
                "q": "0.5",
                "p": "65000.0",
                "T": 1716460800000,
            },
        },
    }
    client._handle_message('{"stream": "btcusdt@forceOrder", "data": {"e": "forceOrder", "o": {"s": "BTCUSDT", "S": "SELL", "q": "0.5", "p": "65000.0", "T": 1716460800000}}}')

    # BTC buffer should have event, ETH buffer should not
    assert len(client._force_order_events["BTCUSDT"]) == 1
    assert len(client._force_order_events["ETHUSDT"]) == 0
    assert client._force_order_events["BTCUSDT"][0]["symbol"] == "BTCUSDT"


# --- Test: get_recent_agg_trades with symbol parameter ---

def test_get_recent_agg_trades_returns_symbol_specific_events() -> None:
    """get_recent_agg_trades(symbol=...) returns only that symbol's events."""
    config = _make_config()
    client = BinanceFuturesWebsocketClient(config, symbols=["BTCUSDT", "ETHUSDT"])

    # Add events to both buffers
    client._agg_trade_events["BTCUSDT"].append(
        {"symbol": "BTCUSDT", "event_time": NOW, "aggregate_trade_id": 1, "price": 65000.0, "qty": 1.0, "is_buyer_maker": False}
    )
    client._agg_trade_events["ETHUSDT"].append(
        {"symbol": "ETHUSDT", "event_time": NOW, "aggregate_trade_id": 2, "price": 3000.0, "qty": 1.0, "is_buyer_maker": True}
    )

    btc_events = client.get_recent_agg_trades(60, symbol="BTCUSDT")
    assert len(btc_events) == 1
    assert btc_events[0]["symbol"] == "BTCUSDT"

    eth_events = client.get_recent_agg_trades(60, symbol="ETHUSDT")
    assert len(eth_events) == 1
    assert eth_events[0]["symbol"] == "ETHUSDT"


def test_get_recent_agg_trades_without_symbol_returns_all() -> None:
    """get_recent_agg_trades() without symbol returns all symbols' events."""
    config = _make_config()
    client = BinanceFuturesWebsocketClient(config, symbols=["BTCUSDT", "ETHUSDT"])

    client._agg_trade_events["BTCUSDT"].append(
        {"symbol": "BTCUSDT", "event_time": NOW, "aggregate_trade_id": 1, "price": 65000.0, "qty": 1.0, "is_buyer_maker": False}
    )
    client._agg_trade_events["ETHUSDT"].append(
        {"symbol": "ETHUSDT", "event_time": NOW, "aggregate_trade_id": 2, "price": 3000.0, "qty": 1.0, "is_buyer_maker": True}
    )

    all_events = client.get_recent_agg_trades(60)
    assert len(all_events) == 2


def test_get_recent_agg_trades_unknown_symbol_returns_empty() -> None:
    """Requesting unknown symbol returns empty list."""
    config = _make_config()
    client = BinanceFuturesWebsocketClient(config, symbols=["BTCUSDT"])
    events = client.get_recent_agg_trades(60, symbol="ETHUSDT")
    assert events == []


# --- Test: get_recent_force_orders with symbol parameter ---

def test_get_recent_force_orders_returns_symbol_specific_events() -> None:
    """get_recent_force_orders(symbol=...) returns only that symbol's events."""
    config = _make_config()
    client = BinanceFuturesWebsocketClient(config, symbols=["BTCUSDT", "SOLUSDT"])

    client._force_order_events["BTCUSDT"].append(
        {"symbol": "BTCUSDT", "event_time": NOW, "side": "SELL", "qty": 0.5, "price": 65000.0}
    )
    client._force_order_events["SOLUSDT"].append(
        {"symbol": "SOLUSDT", "event_time": NOW, "side": "BUY", "qty": 10.0, "price": 150.0}
    )

    btc_events = client.get_recent_force_orders(60, symbol="BTCUSDT")
    assert len(btc_events) == 1
    assert btc_events[0]["symbol"] == "BTCUSDT"

    sol_events = client.get_recent_force_orders(60, symbol="SOLUSDT")
    assert len(sol_events) == 1
    assert sol_events[0]["symbol"] == "SOLUSDT"


def test_get_recent_force_orders_without_symbol_returns_all() -> None:
    """get_recent_force_orders() without symbol returns all symbols' events."""
    config = _make_config()
    client = BinanceFuturesWebsocketClient(config, symbols=["BTCUSDT", "ETHUSDT"])

    client._force_order_events["BTCUSDT"].append(
        {"symbol": "BTCUSDT", "event_time": NOW, "side": "SELL", "qty": 0.5, "price": 65000.0}
    )
    client._force_order_events["ETHUSDT"].append(
        {"symbol": "ETHUSDT", "event_time": NOW, "side": "BUY", "qty": 1.0, "price": 3000.0}
    )

    all_events = client.get_recent_force_orders(60)
    assert len(all_events) == 2


# --- Test: start() accepts symbols list ---

def test_start_accepts_symbols_list() -> None:
    """start() can override symbols at runtime."""
    config = _make_config()
    client = BinanceFuturesWebsocketClient(config, symbols=["BTCUSDT"])
    assert client._symbols == ["BTCUSDT"]

    # Override with new symbols
    client.start(symbols=["ETHUSDT", "SOLUSDT"])
    assert client._symbols == ["ETHUSDT", "SOLUSDT"]


def test_start_without_symbols_uses_existing() -> None:
    """start() without symbols preserves existing symbols."""
    config = _make_config()
    client = BinanceFuturesWebsocketClient(config, symbols=["BTCUSDT", "ETHUSDT"])
    client.start()
    assert client._symbols == ["BTCUSDT", "ETHUSDT"]


# --- Test: Buffer isolation (no cross-contamination) ---

def test_agg_trade_buffer_isolation() -> None:
    """Events for one symbol don't contaminate another symbol's buffer."""
    config = _make_config()
    client = BinanceFuturesWebsocketClient(config, symbols=["BTCUSDT", "ETHUSDT", "SOLUSDT"])

    # Add events to BTC only
    for i in range(5):
        client._agg_trade_events["BTCUSDT"].append(
            {"symbol": "BTCUSDT", "event_time": NOW, "aggregate_trade_id": i, "price": 65000.0, "qty": 1.0, "is_buyer_maker": False}
        )

    # ETH and SOL should remain empty
    assert len(client._agg_trade_events["BTCUSDT"]) == 5
    assert len(client._agg_trade_events["ETHUSDT"]) == 0
    assert len(client._agg_trade_events["SOLUSDT"]) == 0


def test_force_order_buffer_isolation() -> None:
    """Force orders for one symbol don't contaminate another symbol's buffer."""
    config = _make_config()
    client = BinanceFuturesWebsocketClient(config, symbols=["BTCUSDT", "ETHUSDT"])

    client._force_order_events["BTCUSDT"].append(
        {"symbol": "BTCUSDT", "event_time": NOW, "side": "SELL", "qty": 0.5, "price": 65000.0}
    )

    assert len(client._force_order_events["BTCUSDT"]) == 1
    assert len(client._force_order_events["ETHUSDT"]) == 0


# --- Test: Normalization functions still work ---

def test_normalize_ws_agg_trade_event() -> None:
    """aggTrade normalization produces expected output."""
    payload = {
        "s": "btcusdt",
        "a": 123456,
        "T": 1716460800000,
        "p": "65000.50",
        "q": "1.5",
        "m": False,
    }
    normalized = normalize_ws_agg_trade_event(payload)
    assert normalized["symbol"] == "BTCUSDT"
    assert normalized["aggregate_trade_id"] == 123456
    assert normalized["price"] == 65000.50
    assert normalized["qty"] == 1.5
    assert normalized["is_buyer_maker"] is False


def test_normalize_ws_force_order_event() -> None:
    """forceOrder normalization produces expected output."""
    payload = {
        "o": {
            "s": "ethusdt",
            "S": "SELL",
            "q": "0.5",
            "p": "3000.0",
            "T": 1716460800000,
        }
    }
    normalized = normalize_ws_force_order_event(payload)
    assert normalized["symbol"] == "ETHUSDT"
    assert normalized["side"] == "SELL"
    assert normalized["qty"] == 0.5
    assert normalized["price"] == 3000.0
