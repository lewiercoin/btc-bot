from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ArtifactCleanupCandidate:
    path: Path
    category: str
    size_bytes: int
    modified_at_utc: datetime


_SQLITE_ARTIFACT_SUFFIXES = (
    ".db",
    ".db-shm",
    ".db-wal",
    ".sqlite",
    ".sqlite-shm",
    ".sqlite-wal",
    ".journal",
)


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _is_within(path: Path, root: Path) -> bool:
    resolved_path = path.resolve()
    resolved_root = root.resolve()
    return resolved_path == resolved_root or resolved_root in resolved_path.parents


def _is_sqlite_artifact(path: Path) -> bool:
    name = path.name.lower()
    return any(name.endswith(suffix) for suffix in _SQLITE_ARTIFACT_SUFFIXES)


def _iter_cleanup_roots(project_root: Path) -> tuple[tuple[str, Path, bool], ...]:
    roots: list[tuple[str, Path, bool]] = []

    research_lab_snapshots = project_root / "research_lab" / "snapshots"
    if research_lab_snapshots.is_dir():
        roots.append(("research_lab_snapshots", research_lab_snapshots, False))

    research_lab_runs = project_root / "research_lab_runs"
    if research_lab_runs.is_dir():
        for run_dir in sorted(path for path in research_lab_runs.iterdir() if path.is_dir()):
            if run_dir.name == "snapshot_benchmark":
                roots.append(("research_lab_benchmark_snapshots", run_dir, True))
                continue

            run_snapshots = run_dir / "snapshots"
            if run_snapshots.is_dir():
                roots.append(("research_lab_run_snapshots", run_snapshots, False))

    return tuple(roots)


def _iter_root_files(root: Path, *, sqlite_only: bool) -> tuple[Path, ...]:
    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if not _is_within(path, root):
            continue
        if sqlite_only and not _is_sqlite_artifact(path):
            continue
        files.append(path.resolve())
    return tuple(files)


def collect_artifact_cleanup_candidates(
    project_root: Path,
    *,
    older_than_days: int,
    now_utc: datetime | None = None,
) -> tuple[datetime, tuple[ArtifactCleanupCandidate, ...]]:
    if older_than_days < 0:
        raise ValueError("older_than_days must be >= 0.")
    if not project_root.exists():
        raise ValueError(f"project_root does not exist: {project_root}")

    cutoff_utc = _to_utc(now_utc or datetime.now(timezone.utc)) - timedelta(days=older_than_days)
    candidates: list[ArtifactCleanupCandidate] = []
    resolved_root = project_root.resolve()

    for category, cleanup_root, sqlite_only in _iter_cleanup_roots(resolved_root):
        for file_path in _iter_root_files(cleanup_root, sqlite_only=sqlite_only):
            if not _is_within(file_path, resolved_root):
                continue
            stat = file_path.stat()
            modified_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
            if modified_at >= cutoff_utc:
                continue
            candidates.append(
                ArtifactCleanupCandidate(
                    path=file_path,
                    category=category,
                    size_bytes=int(stat.st_size),
                    modified_at_utc=modified_at,
                )
            )

    candidates.sort(key=lambda item: item.path.as_posix())
    return cutoff_utc, tuple(candidates)


def cleanup_artifacts(
    project_root: Path,
    *,
    older_than_days: int,
    dry_run: bool = False,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    cutoff_utc, candidates = collect_artifact_cleanup_candidates(
        project_root,
        older_than_days=older_than_days,
        now_utc=now_utc,
    )

    categories: dict[str, dict[str, int]] = {}
    for candidate in candidates:
        bucket = categories.setdefault(candidate.category, {"files": 0, "bytes": 0})
        bucket["files"] += 1
        bucket["bytes"] += candidate.size_bytes

    deleted_files = 0
    deleted_bytes = 0
    if not dry_run:
        for candidate in candidates:
            candidate.path.unlink(missing_ok=True)
            deleted_files += 1
            deleted_bytes += candidate.size_bytes

    return {
        "project_root": str(project_root.resolve()),
        "dry_run": dry_run,
        "older_than_days": older_than_days,
        "cutoff_utc": cutoff_utc.isoformat(),
        "matched_files": len(candidates),
        "matched_bytes": sum(candidate.size_bytes for candidate in candidates),
        "deleted_files": deleted_files,
        "deleted_bytes": deleted_bytes,
        "categories": categories,
    }
