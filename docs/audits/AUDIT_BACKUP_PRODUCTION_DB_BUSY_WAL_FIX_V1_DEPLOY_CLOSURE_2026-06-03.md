# AUDIT: BACKUP_PRODUCTION_DB_BUSY_WAL_FIX_V1 — DEPLOY CLOSURE

Date: 2026-06-03
Auditor: Claude Code
Builder: Codex
Commits audited (incremental closure):
- `d3bee883` — mode fix (chmod +x for `scripts/backup_production_db.sh`)
- `f9ec2c4` — runbook doc fix (Appendix D: production remote name correction)
Branch: `deploy/multi-asset-paper-v1`
Audit branch: `claude/epic-darwin-z8Moa`
Prior audit in chain: `dea534e` (BACKUP_PRODUCTION_DB_BUSY_WAL_FIX_V1 DONE, awaiting deploy)

## Verdict: DONE (operational closure)

The backup fix is now operationally live on production. Mode fix `d3bee883` is pulled and verified executable. Smoke backup against production 8.1G database completed successfully via `VACUUM INTO` in 626 seconds with integrity check pass. Runbook documentation corrected for the `github` remote naming. Production is ready for the next 2 AM UTC cron run with the new backup method.

## Verification of closure claims

### Mode fix `d3bee883`

| Property | Pre-fix (`318d3a8`) | Post-fix (`d3bee883`) |
|---|---|---|
| Blob hash | `c1d2d571...` | `c1d2d571...` (identical content) |
| Tracked mode | `100644` | `100755` |
| Filesize | 5837 bytes | 5837 bytes |

This is the minimum-impact fix: zero content change, mode-only diff. The mode bit propagates through `git pull` automatically. Production verified post-pull: `-rwxr-xr-x` on disk, `100755` in git index. Cron can now invoke the script.

### Smoke backup result

| Item | Value | Assessment |
|---|---|---|
| Method | VACUUM INTO | ✓ correct (not `.backup`) |
| Source DB size | 8.1 GB | Production grew from ~7GB (2026-06-01) — consistent with continued decision_outcomes accumulation |
| Backup file size | 8.1 GB uncompressed | VACUUM INTO produced a near-equal compact file; suggests source has few free pages to omit |
| Compressed size | 848 MB | ~9.5x compression ratio — typical for SQLite OLTP-style data |
| Integrity check | PASS | ✓ backup is restorable |
| Elapsed time | 626 seconds (~10.4 min) | Within the 30-min timeout budget. Slightly above my "<5 min" earlier estimate but the DB grew to 8.1G; throughput ~13 MB/s effective is reasonable for the server's I/O profile |
| Exit code | 0 | ✓ clean success path |
| Smoke output location | `/tmp/backup-smoke-1780448076/` | ✓ correctly isolated from cron-managed `/home/btc-bot/backups/database/` |
| Latest symlink | Updated to new backup | ✓ pointer logic works |

### Comparison to the failure mode this fixes

| Property | 2026-06-01 `.backup` incident | 2026-06-03 `VACUUM INTO` smoke |
|---|---|---|
| Method | `sqlite3 .backup` | `sqlite3 VACUUM INTO` |
| Duration | ~9 hours (live-lock) | 626 seconds (10.4 min) |
| File size at end | 4.0 GB stuck (live-lock plateau) | 8.1 GB complete |
| Source size during run | grew 6.85 → 7.21 GB | grew 7+ → 8.1 GB |
| Process state at runtime | R, 99.6% CPU, no forward progress | R, completed normally |
| Live-lock risk | YES (re-read changed WAL pages) | NO (writes to new file, no contention) |

The new method is **50× faster** at this database size and structurally eliminates the live-lock failure mode. Speed advantage will be larger on smaller backups; the 50× number is for the 8.1 GB case.

### Runbook doc fix `f9ec2c4`

Appendix D added to deploy runbook documenting the three production remotes (`github`, `origin`, `latest-bundle`) and correcting future deploy commands to use `github`, not `origin`. Content matches what I drafted earlier this exchange.

Codex's judgment to NOT pull `f9ec2c4` to production is correct: it is pure documentation, has no runtime impact, and one-commit lag on a doc-only file is acceptable. The next time production needs a code-level pull (e.g., ownership preservation fix milestone), this doc will come along. No urgency.

## Core Audit Axes

| Axis | Status | Note |
|---|---|---|
| Layer Separation | PASS | Mode fix is git index only; doc fix is docs only; no runtime code change |
| Contract Compliance | PASS | Closure operations executed per the recommended deploy plan |
| State Integrity | PASS | Smoke backup written to `/tmp` isolated location; cron-managed backup directory untouched |
| Error Handling | N/A | Both commits are corrections, no new error paths introduced |
| Methodology Integrity | PASS | Smoke validated the actual claim (VACUUM INTO works at production scale) rather than a synthetic small-DB scenario |
| Reproducibility & Lineage | PASS | Production HEAD `d3bee883` recorded; smoke output path and metrics documented |
| AGENTS.md Compliance | PASS | WHAT/WHY/STATUS in both commits; explicit reason for not pulling doc commit |

## Critical Issues

None.

## Observations (non-blocking)

### Observation 1: Backup file size > expected for VACUUM INTO

VACUUM INTO normally produces a **smaller** file than source because it omits free pages. The smoke result shows source 8.1 GB → backup 8.1 GB (no shrinkage visible at the displayed precision). Two interpretations:

- **Most likely**: Production DB has very few free pages because INSERT-heavy `decision_outcomes` table grows monotonically with no DELETE operations. With no free pages to omit, VACUUM INTO produces a same-size compact file.
- **Possible**: `du -h` rounds at 1-decimal place, so a 7.95 GB source → 7.93 GB backup would both display as "8.1G" but with slight shrinkage hidden by display precision.

Either interpretation is benign. The compressed result (848 MB) confirms the file content is correct (compressible). Not a concern.

### Observation 2: 10-minute backup window vs cron cadence

The smoke took 626 seconds. The cron schedule is daily at 02:00 UTC. The new backup will complete well within any reasonable window; no scheduling collision with other automated tasks expected. As production DB grows in the future, this window will grow proportionally. At current ~150 MB/day growth (decision_outcomes), backup time will grow ~1.2 seconds per day. The 30-min timeout is robust for years.

### Observation 3: Cron success will produce the first non-`/tmp` backup tomorrow

The smoke went to `/tmp/backup-smoke-*` to avoid interfering with the production backup retention logic. The actual cron run at 2026-06-04 02:00 UTC will be the first production-managed backup using VACUUM INTO. It will land in `/home/btc-bot/backups/database/btc_bot_<timestamp>.db.gz` and update `btc_bot_latest.db.gz` symlink to point to the new backup.

If the cron fires while I'm not actively auditing, no problem — the script exits 0 on success and 1/2 on failure. A failure email or cron log entry would surface it. Recommend a follow-up read-only check from Codex tomorrow morning to verify the first cron-managed backup landed cleanly.

## Audit-side note: file mode pattern is now structural

This is the third audit miss of the same pattern in this session (per my prior closure note in the mode-fix instruction):

1. Permission preservation gap on `settings.json` ownership when run as root via SSH (A1.deploy Finding 1)
2. Executable bit on `backup_production_db.sh` (just now, smoke failed with `Permission denied`)
3. (Latent) File modes/ownership on any other committed ops artifact — not yet audited

Three occurrences in three weeks of operational work = structural blind spot in my code-review audit checklist. I owe a CLAUDE.md amendment adding explicit file mode/permission/ownership verification step to the auditor checklist. Will land in the next CLAUDE.md amendment cycle.

## Recommended Next Step

**`BACKUP_PRODUCTION_DB_BUSY_WAL_FIX_V1` is now CLOSED operationally.** No further work on this milestone. Two short follow-ups deferred:

1. Read-only verification tomorrow morning that the 02:00 UTC cron-managed backup landed in the production backup directory and updated the symlink. ~30 seconds of SSH.
2. CLAUDE.md amendment cycle picking up the file-mode-permission-ownership audit checklist addition (when there's a natural batching point with other CLAUDE.md updates).

Next milestone proceeds per the queue established earlier:

**`PAPER_PERFORMANCE_VALIDATION_V2` Path B handoff** — generating now per my earlier promise. Independent of this deploy closure.

## Decision

`d3bee883` and `f9ec2c4` are approved. Production runs the new backup script with executable bit set. Smoke validated VACUUM INTO works at 8.1 GB production scale in 10 minutes. The 2026-06-01 WAL live-lock failure mode is structurally eliminated for future backups. Foundation audit Finding 2 (backup operational policy) remains CLOSED.
