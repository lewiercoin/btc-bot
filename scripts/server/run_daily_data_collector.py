from __future__ import annotations

import logging
import os
import sys
import time
from collections import deque
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests
import yfinance as yf

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from settings import load_settings
from storage.db import connect, init_db, transaction

LOG = logging.getLogger(__name__)

DXY_TICKER = "DX-Y.NYB"
DXY_BACKFILL_START = date(2020, 9, 1)
ETF_BACKFILL_START = date(2024, 1, 10)
SOSOVALUE_ENDPOINT = "https://api.sosovalue.xyz/openapi/v2/etf/historicalInflowChart"
COINGLASS_ENDPOINT = "https://open-api-v4.coinglass.com/api/etf/bitcoin/flow-history"
HTTP_TIMEOUT_SECONDS = 30


class UtcFormatter(logging.Formatter):
    converter = time.gmtime


class ExternalApiError(RuntimeError):
    pass


@dataclass(slots=True)
class EtfSyncResult:
    raw_rows: int = 0
    upserted_rows: int = 0
    primary_source: str = "none"
    fallback_used: bool = False


def configure_logging(level: str = "INFO") -> None:
    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    numeric_level = getattr(logging, level.upper(), logging.INFO)
    root_logger.setLevel(numeric_level)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(numeric_level)
    handler.setFormatter(
        UtcFormatter(
            fmt="%(asctime)sZ %(levelname)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )
    root_logger.addHandler(handler)


def load_last_non_null_date(conn, column_name: str) -> date | None:
    row = conn.execute(
        f"""
        SELECT MAX(date) AS last_date
        FROM daily_external_bias
        WHERE {column_name} IS NOT NULL
        """
    ).fetchone()
    if row is None or row["last_date"] in (None, ""):
        return None
    return date.fromisoformat(str(row["last_date"]))


def resolve_collection_start(last_collected: date | None, initial_start: date) -> date:
    if last_collected is None:
        return initial_start
    return last_collected + timedelta(days=1)


def _normalize_market_date(value: Any) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).date() if value.tzinfo is not None else value.date()
    raw_value = str(value)
    if " " in raw_value:
        raw_value = raw_value.split(" ", maxsplit=1)[0]
    return date.fromisoformat(raw_value[:10])


def _to_float_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed != parsed:
        return None
    return parsed


def fetch_dxy_history(*, start_date: date, end_date: date) -> list[tuple[date, float]]:
    if start_date > end_date:
        return []

    history = yf.Ticker(DXY_TICKER).history(
        start=start_date.isoformat(),
        end=(end_date + timedelta(days=1)).isoformat(),
        auto_adjust=False,
    )
    if history.empty:
        return []

    rows: list[tuple[date, float]] = []
    for idx, row in history.iterrows():
        close_value = _to_float_or_none(row.get("Close"))
        if close_value is None:
            continue
        trade_date = _normalize_market_date(idx)
        if start_date <= trade_date <= end_date:
            rows.append((trade_date, close_value))

    rows.sort(key=lambda item: item[0])
    return rows


def upsert_dxy_rows(conn, rows: list[tuple[date, float]]) -> int:
    if not rows:
        return 0

    before = conn.total_changes
    with transaction(conn):
        conn.executemany(
            """
            INSERT INTO daily_external_bias (date, dxy_close)
            VALUES (?, ?)
            ON CONFLICT(date) DO UPDATE SET
                dxy_close = excluded.dxy_close
            """,
            [(day.isoformat(), close_value) for day, close_value in rows],
        )
    return conn.total_changes - before


def _first_env(*names: str) -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def _request_json(
    session: requests.Session,
    *,
    method: str,
    url: str,
    headers: dict[str, str] | None = None,
    json_body: dict[str, Any] | None = None,
) -> Any:
    response = session.request(
        method=method,
        url=url,
        headers=headers,
        json=json_body,
        timeout=HTTP_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    try:
        return response.json()
    except ValueError as exc:
        raise ExternalApiError(f"Non-JSON response from {url}") from exc


def fetch_sosovalue_etf_flows(session: requests.Session) -> list[tuple[date, float]]:
    api_key = _first_env("SOSO_API_KEY", "SOSOVALUE_API_KEY")
    if not api_key:
        raise ExternalApiError("Missing SOSO_API_KEY/SOSOVALUE_API_KEY.")

    payload = _request_json(
        session,
        method="POST",
        url=SOSOVALUE_ENDPOINT,
        headers={
            "accept": "application/json",
            "content-type": "application/json",
            "x-soso-api-key": api_key,
        },
        json_body={"type": "us-btc-spot"},
    )
    if not isinstance(payload, dict):
        raise ExternalApiError("Unexpected SoSoValue response payload.")

    code = payload.get("code")
    if str(code) not in {"0", "200"}:
        raise ExternalApiError(str(payload.get("msg") or "SoSoValue request failed."))

    data = payload.get("data")
    if not isinstance(data, dict):
        raise ExternalApiError("Unexpected SoSoValue response payload.")
    entries = data.get("list")
    if not isinstance(entries, list):
        raise ExternalApiError("Unexpected SoSoValue response payload.")

    rows: list[tuple[date, float]] = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        trade_date_raw = item.get("date")
        total_net_inflow = _to_float_or_none(item.get("totalNetInflow"))
        if trade_date_raw in (None, "") or total_net_inflow is None:
            continue
        rows.append((date.fromisoformat(str(trade_date_raw)), total_net_inflow))

    rows.sort(key=lambda item: item[0])
    return rows


def extract_coinglass_flow_usd(item: dict[str, Any]) -> float | None:
    for key in ("flow_usd", "change_usd", "changeUsd", "net_inflow_usd", "netInflowUsd"):
        value = _to_float_or_none(item.get(key))
        if value is not None:
            return value

    details = item.get("etf_flows")
    if not isinstance(details, list):
        return None

    total = 0.0
    found_any = False
    for detail in details:
        if not isinstance(detail, dict):
            continue
        detail_value = extract_coinglass_flow_usd(detail)
        if detail_value is None:
            continue
        total += detail_value
        found_any = True

    return total if found_any else None


def fetch_coinglass_etf_flows(session: requests.Session) -> list[tuple[date, float]]:
    api_key = _first_env("COINGLASS_API_KEY", "CG_API_KEY")
    if not api_key:
        raise ExternalApiError("Missing COINGLASS_API_KEY/CG_API_KEY.")

    payload = _request_json(
        session,
        method="GET",
        url=COINGLASS_ENDPOINT,
        headers={
            "accept": "application/json",
            "CG-API-KEY": api_key,
        },
    )
    if not isinstance(payload, dict):
        raise ExternalApiError("Unexpected CoinGlass response payload.")

    code = payload.get("code")
    if str(code) not in {"0", "200"}:
        raise ExternalApiError(str(payload.get("msg") or "CoinGlass request failed."))

    entries = payload.get("data")
    if not isinstance(entries, list):
        raise ExternalApiError("Unexpected CoinGlass response payload.")

    rows: list[tuple[date, float]] = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        timestamp_ms = item.get("timestamp")
        flow_usd = extract_coinglass_flow_usd(item)
        if timestamp_ms in (None, "") or flow_usd is None:
            continue
        trade_date = datetime.fromtimestamp(int(timestamp_ms) / 1000, tz=timezone.utc).date()
        rows.append((trade_date, flow_usd))

    rows.sort(key=lambda item: item[0])
    return rows


def merge_preferred_etf_flows(
    primary_rows: list[tuple[date, float]],
    fallback_rows: list[tuple[date, float]],
) -> list[tuple[date, float]]:
    merged: dict[date, float] = {day: value for day, value in fallback_rows}
    for day, value in primary_rows:
        merged[day] = value
    return sorted(merged.items(), key=lambda item: item[0])


def compute_rolling_bias_5d(rows: list[tuple[date, float]]) -> list[tuple[date, float]]:
    rolling: list[tuple[date, float]] = []
    window: deque[float] = deque()
    running_total = 0.0

    deduped = merge_preferred_etf_flows(rows, [])
    for trade_date, net_inflow in deduped:
        window.append(net_inflow)
        running_total += net_inflow
        if len(window) > 5:
            running_total -= window.popleft()
        rolling.append((trade_date, running_total))

    return rolling


def upsert_etf_bias_rows(conn, rows: list[tuple[date, float]]) -> int:
    if not rows:
        return 0

    before = conn.total_changes
    with transaction(conn):
        conn.executemany(
            """
            INSERT INTO daily_external_bias (date, etf_bias_5d)
            VALUES (?, ?)
            ON CONFLICT(date) DO UPDATE SET
                etf_bias_5d = excluded.etf_bias_5d
            """,
            [(day.isoformat(), bias_value) for day, bias_value in rows],
        )
    return conn.total_changes - before


def sync_etf_bias(
    conn,
    *,
    session: requests.Session,
    start_date: date,
    end_date: date,
) -> EtfSyncResult:
    result = EtfSyncResult()
    if start_date > end_date:
        return result

    soso_rows: list[tuple[date, float]] = []
    fallback_rows: list[tuple[date, float]] = []
    need_fallback = True

    try:
        soso_rows = fetch_sosovalue_etf_flows(session)
        result.primary_source = "sosovalue"
        if soso_rows:
            earliest_date = soso_rows[0][0]
            if start_date >= earliest_date:
                need_fallback = False
            else:
                LOG.warning(
                    "event=etf_sosovalue_history_gap requested_start=%s earliest_available=%s note=using_coinglass_fallback_for_older_dates",
                    start_date.isoformat(),
                    earliest_date.isoformat(),
                )
        else:
            LOG.warning("event=etf_sosovalue_empty note=using_coinglass_fallback")
    except (ExternalApiError, requests.RequestException) as exc:
        LOG.warning(
            "event=etf_source_warning source=sosovalue reason=%s",
            str(exc).replace(" ", "_"),
        )
        result.primary_source = "coinglass"

    if need_fallback:
        try:
            fallback_rows = fetch_coinglass_etf_flows(session)
            if fallback_rows:
                result.fallback_used = True
                if result.primary_source == "none":
                    result.primary_source = "coinglass"
        except (ExternalApiError, requests.RequestException) as exc:
            LOG.warning(
                "event=etf_source_warning source=coinglass reason=%s",
                str(exc).replace(" ", "_"),
            )

    merged_rows = merge_preferred_etf_flows(soso_rows, fallback_rows)
    filtered_rows = [(day, value) for day, value in merged_rows if ETF_BACKFILL_START <= day <= end_date]
    rolling_rows = compute_rolling_bias_5d(filtered_rows)
    target_rows = [(day, bias) for day, bias in rolling_rows if start_date <= day <= end_date]

    result.raw_rows = len(filtered_rows)
    result.upserted_rows = upsert_etf_bias_rows(conn, target_rows)
    return result


def main() -> None:
    configure_logging()

    settings = load_settings()
    assert settings.storage is not None
    today_utc = datetime.now(timezone.utc).date()

    conn = connect(settings.storage.db_path)
    conn.execute("PRAGMA busy_timeout = 5000;")
    init_db(conn, settings.storage.schema_path)

    session = requests.Session()
    try:
        last_dxy_date = load_last_non_null_date(conn, "dxy_close")
        dxy_start = resolve_collection_start(last_dxy_date, DXY_BACKFILL_START)
        dxy_rows = fetch_dxy_history(start_date=dxy_start, end_date=today_utc)
        dxy_upserted = upsert_dxy_rows(conn, dxy_rows)

        LOG.info(
            "event=dxy_sync_complete ticker=%s start=%s end=%s fetched=%s upserted=%s",
            DXY_TICKER,
            dxy_start.isoformat(),
            today_utc.isoformat(),
            len(dxy_rows),
            dxy_upserted,
        )

        last_etf_date = load_last_non_null_date(conn, "etf_bias_5d")
        etf_start = resolve_collection_start(last_etf_date, ETF_BACKFILL_START)
        etf_result = sync_etf_bias(conn, session=session, start_date=etf_start, end_date=today_utc)

        LOG.info(
            "event=etf_sync_complete start=%s end=%s raw_rows=%s upserted=%s primary_source=%s fallback_used=%s",
            etf_start.isoformat(),
            today_utc.isoformat(),
            etf_result.raw_rows,
            etf_result.upserted_rows,
            etf_result.primary_source,
            str(etf_result.fallback_used).lower(),
        )
        LOG.info(
            "event=daily_data_collector_complete dxy_upserted=%s etf_upserted=%s",
            dxy_upserted,
            etf_result.upserted_rows,
        )
    finally:
        session.close()
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
