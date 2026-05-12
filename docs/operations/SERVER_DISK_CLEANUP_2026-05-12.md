# Server Disk Cleanup - Research Lab Snapshot Offload

Date: 2026-05-12  
Operator: Codex  
Server: `root@204.168.146.253`  
Branch: `research/trend-continuation-v1`

## Reason

Before running additional research validation, server capacity was checked. CPU and RAM were acceptable, but disk usage was critical:

```text
/dev/sda1  75G  71G  1.4G  99% /
```

The largest usage was not the runtime bot. It was Research Lab SQLite snapshots:

```text
/home/btc-bot/btc-bot/research_lab           56G
/home/btc-bot/btc-bot/research_lab/snapshots 48G
```

The active bot database was preserved:

```text
/home/btc-bot/btc-bot/storage/btc_bot.db
```

## Bot Status Before Cleanup

The bot was not stopped.

```text
Mode: PAPER
Healthy: 1
Safe Mode: 0
Open Positions: 0
```

No active `research_lab`, `optuna`, `autoresearch`, or grid process was running.

## Files Offloaded

The following rejected autoresearch snapshot DBs were copied from:

```text
/home/btc-bot/btc-bot/research_lab/snapshots/
```

to local archive:

```text
D:\btc-bot-server-archives\2026-05-12_research_lab_autoresearch_snapshots\
```

Files:

```text
autoresearch-4f2faf71-000.db  4527730688 bytes
autoresearch-4f2faf71-001.db  4531015680 bytes
autoresearch-4f2faf71-002.db  4534030336 bytes
autoresearch-4f2faf71-003.db  4536922112 bytes
autoresearch-4f2faf71-004.db  4539846656 bytes
autoresearch-4f2faf71-005.db  4542373888 bytes
autoresearch-4f2faf71-006.db  4545114112 bytes
```

Local archive also contains:

```text
REMOTE_SHA256SUMS.txt
LOCAL_SHA256SUMS.txt
```

`Compare-Object` found no differences between remote and local SHA256 manifests before deletion.

## Deletion

After checksum verification, only the seven verified remote `autoresearch-4f2faf71-*.db` files were removed from the server.

No production DB, runtime file, report, audit, code file, service, or live configuration was removed.

## Result

Server disk after cleanup:

```text
/dev/sda1  75G  41G  31G  57% /
```

Approximate recovered space: 30 GB.

Research Lab usage after cleanup:

```text
/home/btc-bot/btc-bot/research_lab  26G
```

Bot status after cleanup:

```text
Mode: PAPER
Healthy: 1
Safe Mode: 0
Open Positions: 0
```

## Remaining Large Files

Largest remaining data files include:

```text
5.0G /home/btc-bot/btc-bot/storage/btc_bot.db
4.6G /home/btc-bot/btc-bot/research_lab/snapshots/grid-20260511T140002Z_trial_00095_constrained_grid.db
3.7G /home/btc-bot/btc-bot/research_lab/snapshots/replay-optuna-default-v3-trial-00095.db
3.7G /home/btc-bot/btc-bot/deployment_backups/pre_trial_00095_20260508T205449Z/btc_bot.db
7.4G /home/btc-bot/btc-bot/research_lab/revalidation/trial63_revalidation_20260429T131550Z/
```

## Recommendation

Do not run heavy Research Lab jobs on the production server unless:

- available disk remains comfortably above 20 GB,
- generated snapshots are explicitly cleaned or offloaded,
- runtime bot status is checked before and after,
- cleanup/offload manifests are recorded.

Future hygiene milestone should add an automated retention policy for `research_lab/snapshots/*.db`.
