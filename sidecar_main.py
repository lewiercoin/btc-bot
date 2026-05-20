"""Entry point for the isolated multi-asset shadow sidecar.

Only dry-run validation is implemented in this milestone. The sidecar is not a
runtime trading entry point and does not place orders.
"""

from __future__ import annotations

from research_lab.shadow_orchestrator import main


if __name__ == "__main__":
    raise SystemExit(main())
