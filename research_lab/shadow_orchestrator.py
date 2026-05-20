"""Isolated one-shot orchestration for the multi-asset shadow sidecar."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import shutil
import subprocess
import sys
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator, TextIO

from research_lab.shadow_schema import (
    SHADOW_DB_DEFAULT,
    connect_shadow_db,
    initialize_shadow_schema,
    insert_near_miss,
    resolve_shadow_db_path,
)


BTC_RUNTIME_LOCK_PATH = Path("/tmp/btc-bot-runtime.lock")
SIDECAR_LOCK_DEFAULT = Path("/tmp/multi-asset-shadow.lock")
MIN_DISK_FREE_BYTES = 12 * 1024**3
CODE_VERSION = "multi_asset_shadow_sidecar_v1"
DEFAULT_SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT")
DISALLOWED_IMPORT_ROOTS = {"core", "data", "execution"}


class ShadowGuardError(RuntimeError):
    """Raised when a sidecar guard blocks execution."""


@dataclass(frozen=True)
class ResourceSample:
    timestamp_utc: str
    disk_free_bytes: int
    disk_total_bytes: int
    memory_rss_bytes: int | None
    cpu_user_seconds: float | None
    cpu_system_seconds: float | None
    process_id: int
    guard_status: str


@dataclass(frozen=True)
class DryRunResult:
    shadow_run_id: str
    db_path: Path
    lock_path: Path
    symbols: tuple[str, ...]
    decision_rows: int
    near_miss_rows: int
    resource_rows: int
    production_db_touched: bool
    operational_mode: str


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def git_commit(repo_root: Path | None = None) -> str:
    root = (repo_root or Path.cwd()).resolve()
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(root),
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return "unknown"


def default_shadow_config_hash(symbols: tuple[str, ...], operational_mode: str = "dry_run") -> str:
    payload = {
        "code_version": CODE_VERSION,
        "operational_mode": operational_mode,
        "symbols": symbols,
        "db_default": SHADOW_DB_DEFAULT.as_posix(),
        "lock_default": SIDECAR_LOCK_DEFAULT.as_posix(),
    }
    raw = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def ensure_lock_separation(lock_path: Path) -> None:
    if lock_path.resolve() == BTC_RUNTIME_LOCK_PATH.resolve():
        raise ShadowGuardError(
            f"Sidecar lock must not reuse BTC runtime lock: {BTC_RUNTIME_LOCK_PATH}"
        )


@contextmanager
def acquire_sidecar_lock(lock_path: Path = SIDECAR_LOCK_DEFAULT) -> Iterator[TextIO]:
    ensure_lock_separation(lock_path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_fd = lock_path.open("a+", encoding="utf-8")
    try:
        try:
            import fcntl  # type: ignore

            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except ImportError:
            import msvcrt  # type: ignore

            lock_fd.seek(0)
            msvcrt.locking(lock_fd.fileno(), msvcrt.LK_NBLCK, 1)
        lock_fd.seek(0)
        lock_fd.truncate()
        lock_fd.write(f"{os.getpid()}\n")
        lock_fd.flush()
        yield lock_fd
    finally:
        try:
            lock_fd.close()
        except OSError:
            pass


def _import_roots_from_file(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".", 1)[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", 1)[0])
    return roots


def assert_no_order_path_imports(paths: tuple[Path, ...] | None = None) -> None:
    source_paths = paths or (
        Path(__file__).resolve(),
        Path(__file__).resolve().with_name("shadow_schema.py"),
        Path.cwd() / "sidecar_main.py",
    )
    violations: dict[str, list[str]] = {}
    for path in source_paths:
        if not path.exists():
            continue
        roots = _import_roots_from_file(path)
        forbidden = sorted(roots & DISALLOWED_IMPORT_ROOTS)
        if forbidden:
            violations[str(path)] = forbidden
    if violations:
        raise ShadowGuardError(f"Order path imports are forbidden: {violations}")


def collect_resource_sample(path_for_disk: Path, min_disk_free_bytes: int) -> ResourceSample:
    usage = shutil.disk_usage(path_for_disk)
    if usage.free < min_disk_free_bytes:
        raise ShadowGuardError(
            f"Insufficient disk for sidecar: free={usage.free}, required={min_disk_free_bytes}"
        )

    rss_bytes: int | None = None
    cpu_user: float | None = None
    cpu_system: float | None = None
    try:
        import resource

        usage_self = resource.getrusage(resource.RUSAGE_SELF)
        rss = int(usage_self.ru_maxrss)
        rss_bytes = rss * 1024 if sys.platform != "darwin" else rss
        cpu_user = float(usage_self.ru_utime)
        cpu_system = float(usage_self.ru_stime)
    except Exception:
        times = os.times()
        cpu_user = float(times.user)
        cpu_system = float(times.system)

    return ResourceSample(
        timestamp_utc=utc_now_iso(),
        disk_free_bytes=int(usage.free),
        disk_total_bytes=int(usage.total),
        memory_rss_bytes=rss_bytes,
        cpu_user_seconds=cpu_user,
        cpu_system_seconds=cpu_system,
        process_id=os.getpid(),
        guard_status="pass",
    )


def production_db_signature(repo_root: Path) -> tuple[bool, int | None, float | None]:
    path = repo_root / "storage" / "btc_bot.db"
    if not path.exists():
        return (False, None, None)
    stat = path.stat()
    return (True, int(stat.st_size), float(stat.st_mtime))


def _insert_shadow_run(
    conn,
    *,
    shadow_run_id: str,
    started_at: str,
    config_hash: str,
    db_path: Path,
    lock_path: Path,
    dry_run: bool,
    repo_root: Path,
) -> None:
    conn.execute(
        """
        INSERT INTO shadow_runs (
            shadow_run_id, service_start_time_utc, git_commit, code_version,
            config_hash, dry_run, lock_path, db_path, created_at_utc
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            shadow_run_id,
            started_at,
            git_commit(repo_root),
            CODE_VERSION,
            config_hash,
            1 if dry_run else 0,
            lock_path.as_posix(),
            db_path.as_posix(),
            utc_now_iso(),
        ),
    )
    conn.commit()


def _insert_resource_sample(
    conn, shadow_run_id: str, sample: ResourceSample, *, source: str
) -> None:
    conn.execute(
        """
        INSERT INTO shadow_resource_samples (
            shadow_run_id, timestamp_utc, disk_free_bytes, disk_total_bytes,
            memory_rss_bytes, cpu_user_seconds, cpu_system_seconds, process_id,
            guard_status, details_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            shadow_run_id,
            sample.timestamp_utc,
            sample.disk_free_bytes,
            sample.disk_total_bytes,
            sample.memory_rss_bytes,
            sample.cpu_user_seconds,
            sample.cpu_system_seconds,
            sample.process_id,
            sample.guard_status,
            json.dumps({"source": source}, sort_keys=True),
        ),
    )
    conn.commit()


def _risk_profile(symbol: str) -> tuple[str, float, str]:
    if symbol == "SOLUSDT":
        return ("sol_015_shadow_candidate", 0.0015, "shadow_no_orders")
    if symbol == "BTCUSDT":
        return ("btc_035_shadow_compare", 0.0035, "shadow_compare_only")
    return ("eth_035_shadow_candidate", 0.0035, "shadow_no_orders")


def _insert_stub_decision(
    conn,
    *,
    shadow_run_id: str,
    symbol: str,
    timestamp_utc: str,
    config_hash: str,
    operational_mode: str,
) -> None:
    risk_profile, risk_pct, shadow_mode = _risk_profile(symbol)
    details = {
        "dry_run": operational_mode == "dry_run",
        "operational_mode": operational_mode,
        "symbol": symbol,
        "reason": operational_mode,
        "orders_allowed": False,
    }
    signal_blocker = (
        "dry_run_no_market_data"
        if operational_mode == "dry_run"
        else "operational_heartbeat"
    )
    conn.execute(
        """
        INSERT INTO shadow_decision_outcomes (
            shadow_run_id, symbol, timestamp_utc, strategy_profile,
            risk_policy_profile, shadow_mode, config_hash, signal_generated,
            signal_blocker, sweep_detected, reclaim_detected, sweep_depth_pct,
            min_sweep_depth_pct, regime, context_session,
            confluence_score_preview, candidate_direction_preview,
            symbol_governance_shadow_decision, symbol_risk_shadow_decision,
            portfolio_shadow_decision, portfolio_veto_reason, candidate_risk_pct,
            portfolio_risk_after_pct, resource_guard_status, details_json,
            created_at_utc
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            shadow_run_id,
            symbol,
            timestamp_utc,
            "trial_00095_transfer",
            risk_profile,
            shadow_mode,
            config_hash,
            0,
            signal_blocker,
            0,
            0,
            None,
            0.00649,
            "unknown",
            operational_mode,
            0.0,
            None,
            "not_evaluated",
            "not_evaluated",
            "not_evaluated",
            f"{operational_mode}_no_signal",
            risk_pct,
            0.0,
            "pass",
            json.dumps(details, sort_keys=True),
            utc_now_iso(),
        ),
    )
    conn.commit()


def _run_one_shot_cycle(
    *,
    db_path: str | Path = SHADOW_DB_DEFAULT,
    lock_path: str | Path = SIDECAR_LOCK_DEFAULT,
    repo_root: str | Path | None = None,
    symbols: tuple[str, ...] = DEFAULT_SYMBOLS,
    min_disk_free_bytes: int = MIN_DISK_FREE_BYTES,
    operational_mode: str,
    dry_run: bool,
    include_payload_probe: bool,
) -> DryRunResult:
    root = Path(repo_root or Path.cwd()).resolve()
    lock = Path(lock_path)
    ensure_lock_separation(lock)
    resolved_db_path = resolve_shadow_db_path(db_path, repo_root=root)
    before_prod = production_db_signature(root)
    assert_no_order_path_imports(
        (
            Path(__file__).resolve(),
            Path(__file__).resolve().with_name("shadow_schema.py"),
            root / "sidecar_main.py",
        )
    )

    with acquire_sidecar_lock(lock):
        sample = collect_resource_sample(resolved_db_path.parent, min_disk_free_bytes)
        with connect_shadow_db(resolved_db_path, repo_root=root) as conn:
            initialize_shadow_schema(conn)
            shadow_run_id = f"shadow-{operational_mode}-{uuid.uuid4().hex[:12]}"
            config_hash = default_shadow_config_hash(symbols, operational_mode)
            started_at = utc_now_iso()
            _insert_shadow_run(
                conn,
                shadow_run_id=shadow_run_id,
                started_at=started_at,
                config_hash=config_hash,
                db_path=resolved_db_path,
                lock_path=lock,
                dry_run=dry_run,
                repo_root=root,
            )
            _insert_resource_sample(conn, shadow_run_id, sample, source=operational_mode)
            for symbol in symbols:
                _insert_stub_decision(
                    conn,
                    shadow_run_id=shadow_run_id,
                    symbol=symbol,
                    timestamp_utc=started_at,
                    config_hash=config_hash,
                    operational_mode=operational_mode,
                )
            if include_payload_probe:
                insert_near_miss(
                    conn,
                    shadow_run_id=shadow_run_id,
                    symbol=symbols[-1],
                    timestamp_utc=started_at,
                    sweep_depth_pct=0.00584,
                    threshold=0.00649,
                    depth_bucket="near_miss_high",
                    regime=operational_mode,
                    session_hour=0,
                    rejection_reasons=[f"{operational_mode}_payload_validation"],
                    created_at_utc=utc_now_iso(),
                )

            decision_rows = conn.execute(
                "SELECT COUNT(*) FROM shadow_decision_outcomes WHERE shadow_run_id = ?",
                (shadow_run_id,),
            ).fetchone()[0]
            near_miss_rows = conn.execute(
                "SELECT COUNT(*) FROM shadow_near_miss_diagnostics WHERE shadow_run_id = ?",
                (shadow_run_id,),
            ).fetchone()[0]
            resource_rows = conn.execute(
                "SELECT COUNT(*) FROM shadow_resource_samples WHERE shadow_run_id = ?",
                (shadow_run_id,),
            ).fetchone()[0]

    after_prod = production_db_signature(root)
    return DryRunResult(
        shadow_run_id=shadow_run_id,
        db_path=resolved_db_path,
        lock_path=lock,
        symbols=symbols,
        decision_rows=int(decision_rows),
        near_miss_rows=int(near_miss_rows),
        resource_rows=int(resource_rows),
        production_db_touched=before_prod != after_prod,
        operational_mode=operational_mode,
    )


def run_dry_run(
    *,
    db_path: str | Path = SHADOW_DB_DEFAULT,
    lock_path: str | Path = SIDECAR_LOCK_DEFAULT,
    repo_root: str | Path | None = None,
    symbols: tuple[str, ...] = DEFAULT_SYMBOLS,
    min_disk_free_bytes: int = MIN_DISK_FREE_BYTES,
) -> DryRunResult:
    return _run_one_shot_cycle(
        db_path=db_path,
        lock_path=lock_path,
        repo_root=repo_root,
        symbols=symbols,
        min_disk_free_bytes=min_disk_free_bytes,
        operational_mode="dry_run",
        dry_run=True,
        include_payload_probe=True,
    )


def run_cycle_once(
    *,
    db_path: str | Path = SHADOW_DB_DEFAULT,
    lock_path: str | Path = SIDECAR_LOCK_DEFAULT,
    repo_root: str | Path | None = None,
    symbols: tuple[str, ...] = DEFAULT_SYMBOLS,
    min_disk_free_bytes: int = MIN_DISK_FREE_BYTES,
) -> DryRunResult:
    return _run_one_shot_cycle(
        db_path=db_path,
        lock_path=lock_path,
        repo_root=repo_root,
        symbols=symbols,
        min_disk_free_bytes=min_disk_free_bytes,
        operational_mode="operational_heartbeat",
        dry_run=False,
        include_payload_probe=False,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Multi-asset shadow sidecar")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Run one isolated validation cycle and exit")
    mode.add_argument(
        "--cycle-once",
        action="store_true",
        help="Run one operational heartbeat cycle and exit",
    )
    parser.add_argument("--db-path", default=SHADOW_DB_DEFAULT.as_posix())
    parser.add_argument("--lock-path", default=SIDECAR_LOCK_DEFAULT.as_posix())
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    parser.add_argument("--min-disk-free-gb", type=float, default=12.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    symbols = tuple(symbol.strip().upper() for symbol in args.symbols.split(",") if symbol.strip())
    runner = run_dry_run if args.dry_run else run_cycle_once
    try:
        result = runner(
            db_path=args.db_path,
            lock_path=args.lock_path,
            repo_root=args.repo_root,
            symbols=symbols,
            min_disk_free_bytes=int(args.min_disk_free_gb * 1024**3),
        )
    except ShadowGuardError as exc:
        print(json.dumps({"error": str(exc), "status": "guard_failed"}, sort_keys=True))
        return 1
    print(
        json.dumps(
            {
                "shadow_run_id": result.shadow_run_id,
                "db_path": result.db_path.as_posix(),
                "lock_path": result.lock_path.as_posix(),
                "symbols": result.symbols,
                "decision_rows": result.decision_rows,
                "near_miss_rows": result.near_miss_rows,
                "operational_mode": result.operational_mode,
                "resource_rows": result.resource_rows,
                "production_db_touched": result.production_db_touched,
            },
            sort_keys=True,
        )
    )
    return 1 if result.production_db_touched else 0


if __name__ == "__main__":
    raise SystemExit(main())
