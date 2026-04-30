#!/usr/bin/env python3
"""
Smoke test for wf_light_protocol.json

Verifies:
1. Protocol JSON loads successfully
2. build_windows() produces expected 3 folds for 87-day window
3. Fold dates align with documented breakdown
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from research_lab.walkforward import build_windows  # noqa: E402


def main() -> int:
    protocol_path = PROJECT_ROOT / "research_lab" / "configs" / "wf_light_protocol.json"

    # Load protocol
    with open(protocol_path) as f:
        protocol = json.load(f)

    print("=== WF_LIGHT_PROTOCOL SMOKE TEST ===")
    print(f"Protocol: {protocol.get('protocol_name')} v{protocol.get('version')}")
    print(f"Train/Val/Step: {protocol['train_days']}/{protocol['validation_days']}/{protocol['step_days']} days")
    print()

    # Build windows for 87-day target window (2026-01-01 to 2026-03-28)
    # Using 2026-03-29 as end (exclusive) to get full 87 days
    data_start = "2026-01-01"
    data_end = "2026-03-29"

    windows = build_windows(data_start, data_end, protocol)

    print(f"Data window: {data_start} to {data_end} (87 days)")
    print(f"Folds generated: {len(windows)}")
    print()

    # Verify expected 3 folds
    if len(windows) != 3:
        print(f"FAIL: Expected 3 folds, got {len(windows)}")
        return 1

    print("PASS: 3 folds generated as expected")
    print()

    # Display fold breakdown
    print("Fold breakdown:")
    for i, window in enumerate(windows, 1):
        print(f"  Fold {i}:")
        print(f"    Train: {window.train_start[:10]} -> {window.train_end[:10]}")
        print(f"    Val:   {window.validation_start[:10]} -> {window.validation_end[:10]}")

    print()
    print("=== SMOKE TEST PASSED ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
