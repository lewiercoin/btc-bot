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
