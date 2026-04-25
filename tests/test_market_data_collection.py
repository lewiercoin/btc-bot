from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core.feature_engine import FeatureEngine, FeatureEngineConfig
from core.models import MarketSnapshot
from data.market_data import MarketDataAssembler, MarketDataConfig
from data.websocket_client import BinanceFuturesWebsocketClient, WebsocketClientConfig


def _agg_trade(trade_id: int, event_time: datetime) -> dict:
    return {
        "symbol": "BTCUSDT",
        "aggregate_trade_id": trade_id,
        "event_time": event_time,
        "price": 100_000.0,
        "qty": 1.0,
        "is_buyer_maker": bool(trade_id % 2),
        "_exchange_raw": {"a": trade_id},
    }


def _funding_row(funding_time: datetime, funding_rate: float = 0.0001) -> dict:
    return {
        "symbol": "BTCUSDT",
        "funding_time": funding_time,
        "funding_rate": funding_rate,
        "_exchange_raw": {"fundingTime": int(funding_time.timestamp() * 1000)},
    }


class PagingRestClient:
    def __init__(self, *, agg_trades: list[dict] | None = None, funding_rows: list[dict] | None = None) -> None:
        self.agg_trades = sorted(agg_trades or [], key=lambda item: item["event_time"])
        self.funding_rows = sorted(funding_rows or [], key=lambda item: item["funding_time"])

    def fetch_agg_trades_window(
        self,
        *,
        symbol: str,
        start_time: datetime,
        end_time: datetime,
        limit: int,
    ) -> list[dict]:
        return [
            trade
            for trade in self.agg_trades
            if start_time <= trade["event_time"] <= end_time
        ][:limit]

    def fetch_agg_trades(
        self,
        symbol: str,
        limit: int = 1000,
        start_time_ms: int | None = None,
        end_time_ms: int | None = None,
        from_id: int | None = None,
    ) -> list[dict]:
        rows = self.agg_trades
        if from_id is not None:
            rows = [trade for trade in rows if trade["aggregate_trade_id"] >= from_id]
        return rows[:limit]

    def fetch_funding_history(
        self,
        symbol: str,
        limit: int = 200,
        start_time_ms: int | None = None,
        end_time_ms: int | None = None,
    ) -> list[dict]:
        rows = self.funding_rows
        if start_time_ms is not None:
            start_dt = datetime.fromtimestamp(start_time_ms / 1000, tz=timezone.utc)
            rows = [row for row in rows if row["funding_time"] >= start_dt]
        if end_time_ms is not None:
            end_dt = datetime.fromtimestamp(end_time_ms / 1000, tz=timezone.utc)
            rows = [row for row in rows if row["funding_time"] <= end_dt]
        return rows[:limit]


def test_market_websocket_url_normalizes_market_base_to_combined_stream() -> None:
    client = BinanceFuturesWebsocketClient(
        WebsocketClientConfig(
            ws_base_url="wss://fstream.binance.com/ws",
            ws_market_base_url="wss://fstream.binance.com/market",
            heartbeat_seconds=30,
            reconnect_seconds=5,
        )
    )

    assert (
        client._build_market_stream_url()
        == "wss://fstream.binance.com/stream?streams=btcusdt@aggTrade/btcusdt@forceOrder"
    )


def test_rest_agg_trade_pagination_restores_complete_15m_and_60s_flow_windows() -> None:
    now = datetime(2026, 1, 1, 0, 15, tzinfo=timezone.utc)
    start = now - timedelta(minutes=15)
    trades: list[dict] = []
    trade_id = 1
    current = start
    while current <= now:
        trades.append(_agg_trade(trade_id, current))
        trade_id += 1
        trades.append(_agg_trade(trade_id, current))
        trade_id += 1
        current += timedelta(seconds=1)

    assembler = MarketDataAssembler(
        rest_client=PagingRestClient(agg_trades=trades),  # type: ignore[arg-type]
        config=MarketDataConfig(agg_trades_limit=1000),
    )

    _, _, trades_60s, trades_15m, quality, _ = assembler._load_agg_trade_windows("BTCUSDT", now)

    assert len(trades_15m) == len(trades)
    assert len(trades_60s) > 0
    assert quality["flow_15m"].status == "ready"
    assert quality["flow_60s"].status == "ready"


def test_funding_window_loader_paginates_to_full_coverage() -> None:
    now = datetime(2026, 4, 25, 0, 0, tzinfo=timezone.utc)
    required_samples = 82 * 3
    funding_rows = [
        _funding_row(now - timedelta(hours=8 * offset))
        for offset in reversed(range(required_samples))
    ]

    assembler = MarketDataAssembler(
        rest_client=PagingRestClient(funding_rows=funding_rows),  # type: ignore[arg-type]
        config=MarketDataConfig(funding_limit=200, funding_window_days=82),
    )

    funding_history = assembler._load_funding_window(symbol="BTCUSDT", now=now)
    features = FeatureEngine(FeatureEngineConfig(funding_window_days=82)).compute(
        MarketSnapshot(
            symbol="BTCUSDT",
            timestamp=now,
            price=100.0,
            bid=99.5,
            ask=100.5,
            funding_history=funding_history,
        ),
        "v1.0",
        "hash",
    )

    assert len(funding_history) == required_samples
    assert features.quality["funding_window"].status == "ready"
