from __future__ import annotations

from pathlib import Path

from dashboard.runtime_config import extract_runtime_config_hash


def test_extract_runtime_config_hash_returns_latest_start_entry(tmp_path: Path) -> None:
    log_path = tmp_path / "btc_bot.log"
    log_path.write_text(
        "\n".join(
            [
                "2026-04-17 19:09:15 | INFO | __main__ | Starting bot | mode=PAPER | symbol=BTCUSDT | config_hash=e8c7180d829d8c9c8296b09ba7ad8d0316251d4161d36be26fccc2051d4e5718",
                "2026-04-17 19:15:00 | INFO | orchestrator | Decision cycle started",
                "2026-04-17 19:09:54 | INFO | __main__ | Starting bot | mode=PAPER | symbol=BTCUSDT | config_hash=cf15d9e5326ee5a4af27d2afa3ef57ce153c542aac1238656f130b38ca2420f5",
            ]
        ),
        encoding="utf-8",
    )

    assert extract_runtime_config_hash(log_path) == "cf15d9e5326ee5a4af27d2afa3ef57ce153c542aac1238656f130b38ca2420f5"


def test_extract_runtime_config_hash_returns_none_without_start_line(tmp_path: Path) -> None:
    log_path = tmp_path / "btc_bot.log"
    log_path.write_text(
        "2026-04-17 19:15:00 | INFO | orchestrator | Decision cycle started",
        encoding="utf-8",
    )

    assert extract_runtime_config_hash(log_path) is None
