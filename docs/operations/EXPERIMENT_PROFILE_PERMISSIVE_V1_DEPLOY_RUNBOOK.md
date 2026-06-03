# EXPERIMENT_PROFILE_PERMISSIVE_V1_DEPLOY_RUNBOOK

**Scope:** Phase A1.deploy for `experiment-profile-permissive-v1`  
**Status:** Draft runbook for Claude Code audit; do not execute before A1.build approval  

---

## Preconditions

1. Claude Code has audited the A1.build commit and returned `DONE` or
   `MVP_DONE` with no blocking issues.
2. Operator has SSH access to `root@204.168.146.253`.
3. Production branch is `deploy/multi-asset-paper-v1`.
4. Production strategy parameters already match the target runtime behavior:
   BTC `min_sweep_depth_pct=0.005`, ETH/SOL `0.0075`.
5. Operator commits to capturing restart timestamp and post-restart log
   evidence as part of step 6.

This runbook changes metadata identity only. It does not change strategy
parameters.

---

## 1. Pre-Deploy Backup

Run the documented production DB backup procedure:

```powershell
ssh -i "c:\development\btc-bot\btc-bot-deploy-v2" root@204.168.146.253 `
  "cd /home/btc-bot/btc-bot && bash scripts/backup_production_db.sh"
```

Record the backup path and SHA256 in the deploy log.

---

## 2. Deploy Reviewed Bundle

Pull the audited commit:

```powershell
ssh -i "c:\development\btc-bot\btc-bot-deploy-v2" root@204.168.146.253 `
  "cd /home/btc-bot/btc-bot && git fetch origin && git pull --ff-only origin deploy/multi-asset-paper-v1"
```

Do not hand-edit files on the server.

---

## 3. Dry Run Metadata Update

Run dry-run against production `settings.json`:

```powershell
ssh -i "c:\development\btc-bot\btc-bot-deploy-v2" root@204.168.146.253 `
  "cd /home/btc-bot/btc-bot && python3 scripts/update_candidate_id_metadata_only.py --settings-json settings.json --dry-run"
```

Expected:

- `deployment.candidate_id` would change from
  `optuna-default-v3-trial-00095` to `experiment-profile-permissive-v1`;
- `monitoring.candidate_id` would change from
  `optuna-default-v3-trial-00095` to `experiment-profile-permissive-v1`;
- no strategy/risk/multi-asset parameter is changed.

If output differs, stop.

---

## 4. Execute Metadata Update

Run the real metadata update:

```powershell
ssh -i "c:\development\btc-bot\btc-bot-deploy-v2" root@204.168.146.253 `
  "cd /home/btc-bot/btc-bot && python3 scripts/update_candidate_id_metadata_only.py --settings-json settings.json"
```

Capture stdout. The script prints the log path under
`docs/operations/CANDIDATE_ID_UPDATE_<timestamp>.log`.

---

## 5. Verify Metadata

Run:

```powershell
ssh -i "c:\development\btc-bot\btc-bot-deploy-v2" root@204.168.146.253 `
  "cd /home/btc-bot/btc-bot && python3 scripts/update_candidate_id_metadata_only.py --settings-json settings.json --verify-only"
```

Expected exit code: `0`.

Then inspect candidate metadata and strategy thresholds:

```powershell
ssh -i "c:\development\btc-bot\btc-bot-deploy-v2" root@204.168.146.253 `
  "cd /home/btc-bot/btc-bot && python3 - <<'PY'
import json
data = json.load(open('settings.json'))
print(data['deployment']['candidate_id'])
print(data['monitoring']['candidate_id'])
print(data['strategy']['min_sweep_depth_pct'])
print(data['multi_asset']['symbol_overrides'])
PY"
```

Expected:

- both candidate IDs equal `experiment-profile-permissive-v1`;
- BTC threshold remains `0.005`;
- ETH/SOL overrides remain `0.0075`.

---

## 6. Service Restart (Mandatory)

The candidate ID is loaded from `settings.json` at process start. Until the
service restarts, the running process continues to emit the old
`optuna-default-v3-trial-00095` identity in every log line, monitoring write,
and alert. The metadata update only takes effect at next process start.
**The restart IS the deploy.**

After step 5 verify-only exits 0, restart the service and capture the
timestamp:

```powershell
ssh -i "c:\development\btc-bot\btc-bot-deploy-v2" root@204.168.146.253 `
  "date -u '+%Y-%m-%dT%H:%M:%SZ' && systemctl restart btc-bot.service && sleep 5 && systemctl is-active btc-bot.service"
```

Record the UTC timestamp printed by the `date` command.

Then confirm the first post-restart log line shows the new candidate ID:

```powershell
ssh -i "c:\development\btc-bot\btc-bot-deploy-v2" root@204.168.146.253 `
  "journalctl -u btc-bot.service --since '5 seconds ago' --no-pager | head -20"
```

Expected log line pattern after restart:

```
deployment.candidate_id = experiment-profile-permissive-v1
```

If the log line still shows `optuna-default-v3-trial-00095`, stop and
investigate before proceeding. Do not restart for any strategy parameter
change; no strategy parameter change is permitted in this runbook.

---

## 7. Post-Deploy Record

Append a deploy completion record to
`docs/research/EXPERIMENT_PROFILE_PERMISSIVE_V1_LINEAGE.md` in a follow-up ops
commit containing:

- audited A1.build commit hash;
- Claude audit hash;
- backup path and SHA256;
- candidate update log path and SHA256;
- verification command outputs;
- restart UTC timestamp (from step 6 `date -u` output);
- `systemctl is-active btc-bot.service` output after restart;
- first post-restart log line showing the new candidate ID
  (`deployment.candidate_id = experiment-profile-permissive-v1`).

Commit prefix:

```text
ops: experiment-profile-permissive-v1 candidate id metadata deploy
```

The commit must include WHAT / WHY / STATUS and reference the A1.build audit
hash.

---

## Appendix A: Backup Incident 2026-06-01

### Timeline

| Time (UTC) | Event |
|---|---|
| Jun 1 17:44 | `sqlite3 .backup` started via `scripts/backup_production_db.sh` |
| Jun 1 ~19:50 | File grew to 4.0 GB, then size stopped increasing |
| Jun 1 ~19:50–Jun 2 02:15 | Process in R state, 99.6% CPU, mtime advancing but file size unchanged at 4,192,256,000 bytes |
| Jun 2 02:15 | Backup completed on its own; file grew to 7,075,704,832 bytes (7.07 GB) |
| Jun 2 04:22 | Diagnostics confirmed process exited; backup verified via integrity_check + row count cross-check + SHA256 |

### Root Cause

**WAL live-lock.** The bot was actively writing to the source DB throughout the
backup. The source DB grew from 6.85 GB to 7.21 GB during the backup window.
`sqlite3 .backup` on a busy WAL-mode database re-reads changed WAL pages before
finalizing, creating a feedback loop where the backup repeatedly overwrites
already-written pages in the target. The file size plateau at 4.0 GB with
advancing mtime confirms in-place page rewrites without forward progress.

### Forensics (captured before kill attempt)

- Process state: R (running), 99.6% CPU, 27,214s elapsed
- Source DB: 7,032,918,016 bytes (lsof), WAL: 30 MB
- Target: 4,192,256,000 bytes (stuck)
- No I/O errors in journalctl
- 13 GB free disk space
- Process had already exited by the time kill was attempted

### Lessons Learned

1. **Do not use `sqlite3 .backup` on a busy WAL-mode DB.** Use one of:
   - `VACUUM INTO '<path>'` (online, no WAL contention, available since SQLite 3.27)
   - Stop bot → file-level `cp` → start bot (3-5 min PAPER downtime)
   - Stop bot → `PRAGMA wal_checkpoint(TRUNCATE)` → `cp` → start bot (cleanest)

2. **Set a backup timeout.** If backup exceeds 30 minutes on a 7 GB DB, escalate
   immediately rather than waiting hours.

3. **Monitor file size growth, not just mtime.** Mtime advancing without size
   growth is a WAL replay indicator, not forward progress.

---

## Appendix B: Permission Error Deviation

### Incident

The `update_candidate_id_metadata_only.py` script ran as `root` (via SSH as
root) and wrote `settings.json` with ownership `root:root` and mode `0600`.
The bot service runs as user `btc-bot` and crashed 3 times with
`PermissionError: [Errno 13] Permission denied: '/home/btc-bot/btc-bot/settings.json'`
before the issue was identified.

### Fix Applied

```bash
chown btc-bot:btc-bot /home/btc-bot/btc-bot/settings.json
chmod 644 /home/btc-bot/btc-bot/settings.json
```

### Prevention

Future runbook executions must add a post-update ownership verification step
after step 4:

```bash
# After metadata update, verify file ownership matches bot service user
ls -la /home/btc-bot/btc-bot/settings.json
# Expected: btc-bot btc-bot
# If root:root, fix with: chown btc-bot:btc-bot /home/btc-bot/btc-bot/settings.json
```

Alternatively, the `update_candidate_id_metadata_only.py` script should be
modified to preserve original file ownership after atomic write.

---

## Appendix C: Startup Log Pattern Correction

### Issue

Step 6 expected the log line:

```
deployment.candidate_id = experiment-profile-permissive-v1
```

The bot does not emit this exact line at startup. The actual startup log shows:

```
Starting bot | mode=PAPER | profile=experiment | symbol=BTCUSDT | config_hash=...
```

### Adapted Verification Used

1. **Positive check:** `settings.json` confirmed both candidate_id fields set to
   `experiment-profile-permissive-v1`
2. **Negative check:** `grep -c 'optuna-default-v3-trial-00095'` on post-restart
   logs returned 0
3. **Health check:** service active, new PID (1078902 ≠ 992005), first decision
   cycle at 04:30:00 UTC

### Correction for Future Use

Step 6 verification should use the adapted three-check approach rather than
relying on a specific log line pattern that does not exist.

---

## Appendix D: Production Remote Name Correction 2026-06-03

Production server has 3 git remotes:

- `github` -> `https://github.com/lewiercoin/btc-bot.git` (canonical)
- `origin` -> `/home/btc-bot/btc-bot.bundle` (local bundle, main only)
- `latest-bundle` -> `/home/btc-bot/btc-bot-latest.bundle` (local bundle)

Runbook step 2 originally used `origin` which on production points to a local
bundle without deploy branches. The correct remote name is `github`.

Future deploy commands MUST use:

```bash
git fetch github
git pull --ff-only github deploy/multi-asset-paper-v1
```

Open question: A1.deploy (2026-06-02) succeeded with the same incorrect
command. Investigation deferred to post-mortem milestone.
