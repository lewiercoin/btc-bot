# Dashboard: Server Resources Panel

## Overview

The **Server Resources** panel provides lightweight, read-only monitoring of server resource usage: CPU, memory, load average, and disk space. Panel auto-refreshes every 10 seconds via polling (`/api/server-resources`).

---

## API Endpoint

**`GET /api/server-resources`**

### Response Schema

```json
{
  "cpu_percent": 12.5,
  "memory_percent": 45.3,
  "memory_total_gb": 8.0,
  "memory_used_gb": 3.62,
  "load_avg": {
    "1m": 0.42,
    "5m": 0.38,
    "15m": 0.35
  },
  "disk_percent": 32.1,
  "disk_total_gb": 100.0,
  "disk_used_gb": 32.1
}
```

### Data Sources

| Field | Source |
|---|---|
| All metrics | `psutil` library — cross-platform system metrics |
| CPU | `psutil.cpu_percent(interval=0.1)` |
| Memory | `psutil.virtual_memory()` |
| Load average | `psutil.getloadavg()` (Unix/Linux only; returns zeros on Windows) |
| Disk | `psutil.disk_usage("/")` (root partition) |

---

## Panel Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│ Server Resources                               Updated HH:MM:SS     │
├─────────────────────────────────────────────────────────────────────┤
│  CPU         12.5% [green]                                         │
│  Memory      45.3% (3.62 / 8.0 GB) [green]                        │
│  Load (1m/5m/15m)  0.42 / 0.38 / 0.35                             │
│  Disk        32.1% (32.1 / 100.0 GB) [green]                        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Color Logic

| Metric | Threshold | Badge Color |
|---|---|---|
| CPU / Memory / Disk | < 80% | Green (ok) |
| CPU / Memory / Disk | ≥ 80% and < 95% | Yellow/Amber (warn) |
| CPU / Memory / Disk | ≥ 95% | Red (error) |

Load average has no color coding — it displays raw values for interpretation based on CPU core count.

---

## Load Average Interpretation

Load average represents the average number of processes waiting for CPU time over 1, 5, and 15 minutes.

- **Load < CPU cores**: System is idle
- **Load ≈ CPU cores**: System is at capacity
- **Load > CPU cores**: System is overloaded

Example on a 2-core VPS:
- Load 0.5/0.4/0.3 = healthy (50% of capacity)
- Load 2.0/2.1/2.0 = at capacity (100%)
- Load 4.0/4.5/5.0 = overloaded (200%+)

---

## Performance Impact

- `psutil.cpu_percent(interval=0.1)` samples CPU over 100ms — negligible overhead
- `psutil.virtual_memory()` and `psutil.disk_usage("/")` read OS-level metrics — fast
- `psutil.getloadavg()` reads `/proc/loadavg` on Linux — fast
- Endpoint is read-only — no state mutation
- Polling interval 10s — low frequency

---

## Platform Notes

| Platform | Load average | Disk path |
|---|---|---|
| Linux | Supported (reads `/proc/loadavg`) | `/` (root) |
| macOS | Supported | `/` |
| Windows | Returns zeros (not supported) | `C:\` (root) |

On Windows, load average will show `0.0 / 0.0 / 0.0` — this is expected behavior from `psutil`.

---

## Related Documentation

- [`docs/dashboard/risk-visualisation.md`](risk-visualisation.md) — Risk & Governance panel
- [`docs/dashboard/egress-integration.md`](egress-integration.md) — Egress Health panel
- [`docs/dashboard/access-guide.md`](access-guide.md) — Production access guide
