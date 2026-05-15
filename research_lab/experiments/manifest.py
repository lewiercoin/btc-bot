from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DataManifest:
    dataset_id: str
    path: str
    timeframe: str
    symbol: str
    date_start: str
    date_end: str
    row_count: int
    content_hash: str
    quality_status: str
    source: str

    def to_dict(self) -> dict[str, str | int]:
        return {
            "dataset_id": self.dataset_id,
            "path": self.path,
            "timeframe": self.timeframe,
            "symbol": self.symbol,
            "date_start": self.date_start,
            "date_end": self.date_end,
            "row_count": self.row_count,
            "content_hash": self.content_hash,
            "quality_status": self.quality_status,
            "source": self.source,
        }

    def compute_hash(self) -> str:
        return _hash_tokens(
            [
                self.dataset_id,
                self.path,
                self.timeframe,
                self.symbol,
                self.date_start,
                self.date_end,
                str(self.row_count),
                self.content_hash,
                self.quality_status,
                self.source,
            ]
        )


def create_manifest(
    *,
    dataset_id: str,
    path: str | Path,
    timeframe: str,
    symbol: str,
    date_start: str,
    date_end: str,
    row_count: int,
    quality_status: str,
    source: str,
) -> DataManifest:
    path_obj = Path(path)
    content_hash = _file_hash(path_obj) if path_obj.exists() and path_obj.is_file() else "missing"
    return DataManifest(
        dataset_id=dataset_id,
        path=str(path_obj),
        timeframe=timeframe,
        symbol=symbol,
        date_start=date_start,
        date_end=date_end,
        row_count=int(row_count),
        content_hash=content_hash,
        quality_status=quality_status,
        source=source,
    )


def compute_combined_manifest_hash(manifests: list[DataManifest]) -> str:
    tokens = [manifest.compute_hash() for manifest in sorted(manifests, key=lambda m: m.dataset_id)]
    return _hash_tokens(tokens)


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _hash_tokens(tokens: list[str]) -> str:
    digest = hashlib.sha256()
    for token in tokens:
        digest.update(token.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()
