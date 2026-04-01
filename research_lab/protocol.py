from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


def load_protocol(protocol_path: Path) -> dict[str, Any]:
    return json.loads(protocol_path.read_text(encoding="utf-8"))


def hash_protocol(protocol: Mapping[str, Any]) -> str:
    canonical = json.dumps(protocol, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
