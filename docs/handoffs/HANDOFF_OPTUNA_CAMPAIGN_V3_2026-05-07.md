## CLAUDE HANDOFF -> CODEX

### Checkpoint
- Last commit: `988b347` ("audit: OPTUNA-INFRASTRUCTURE-V3-HARDENING — DONE")
- Branch: `claude/audit-wf-light-protocol-ZXDA9`
- Working tree: clean

### Before you code
Read these files (mandatory):
1. Relevant blueprint(s):
   - `docs/BLUEPRINT_RESEARCH_LAB.md` — research lab architecture and workflow
2. `AGENTS.md` — discipline + your workflow rules
3. `docs/MILESTONE_TRACKER.md` — current status + known issues
4. `docs/audits/AUDIT_OPTUNA_INFRASTRUCTURE_V3_HARDENING_2026-05-07.md` — V3 infrastructure audit

### Milestone: OPTUNA-CAMPAIGN-V3
Scope: Launch 350-trial Optuna campaign using V3 infrastructure hardening on server

**Context:**
- V3 infrastructure audit: DONE (all axes PASS, zero blockers)
- V3 improvements:
  1. Raw/objective metrics separation (audit trail for TPE transforms)
  2. WF-winners-only warm-start mode (production default, filters to trial-00000 only)
  3. Multivariate TPE auto-disable (prevents RandomSampler fallback for dynamic-bound params)
  4. Richer trial metadata (14 new Optuna attrs)
  5. V3 range tightening (7 params, evidence-based)
  6. Drawdown unit alignment (0.5 = 50%)
- Campaign V1: trial-00000 is only WF-passed candidate (OOS ER=2.668, Sharpe=13.61)
- Campaign V2: 350 trials, 85 accepted, 5 WF pass, ZERO promotion-ready (trial-00152 verdict SCREENING_ONLY)
- Server: root@204.168.146.253, key: `c:\development\btc-bot\btc-bot-deploy-v2`

**Deliverables:**
1. Update `MILESTONE_TRACKER.md`: mark OPTUNA-CAMPAIGN-V3 ACTIVE with launch command and V3 summary
2. Launch Campaign V3 on server via SSH
3. Monitor launch (first 5-10 trials to confirm infrastructure working)
4. Commit tracker update with Campaign V3 ACTIVE status
5. Report back: campaign launched, PID, expected completion time, first trial summary

**Target files:**
- `docs/MILESTONE_TRACKER.md` (update only, no code changes needed)

**Launch command (server: root@204.168.146.253):**
```bash
cd /home/btc-bot/btc-bot
nohup .venv/bin/python -m research_lab optimize \
  --start-date 2022-01-01 --end-date 2026-03-28 \
  --study-name optuna-default-v3 --n-trials 350 --seed 44 \
  --warm-start-from-store --warm-start-mode wf-winners-only \
  --multivariate-tpe \
  --max-sweep-rate 0.60 \
  --optuna-storage-path /home/btc-bot/btc-bot/research_lab/optuna_default_v3.db \
  > /tmp/optuna_v3.log 2>&1 &
```

**Expected behavior:**
- Warm-start will enqueue trial-00000 params (only WF-passed trial in store)
- Baseline config will be enqueued
- Multivariate TPE will auto-disable (dynamic-bound params: ema_slow, tp2_atr_mult, high_vol_leverage)
- Study attrs will document: `multivariate_tpe_effective=false`, `multivariate_tpe_policy="disabled_dynamic_bounds:..."`, `warm_start_mode="wf-winners-only"`
- First trial should complete in ~2-3 minutes (backtest + snapshot overhead)
- 350 trials estimated: ~12-14 hours total

**Verification checklist:**
- [ ] SSH connection works (key: `c:\development\btc-bot\btc-bot-deploy-v2`)
- [ ] Working directory is `/home/btc-bot/btc-bot`
- [ ] Git status clean or safely stale (campaign doesn't need latest commit)
- [ ] Bot service running (don't interrupt live bot)
- [ ] Launch command returns PID
- [ ] `/tmp/optuna_v3.log` created and has initial output
- [ ] First trial completes successfully (check log for trial-00000 or trial-00001 completion)
- [ ] `research_lab/optuna_default_v3.db` created
- [ ] Optuna study attrs confirm: `warm_start_mode=wf-winners-only`, `multivariate_tpe_effective=false`

### Known Issues (from Claude Code audit)
| # | Issue | Blocking for this milestone? |
|---|---|---|
| D18 | `max_sweep_rate` threshold not validated for full 2022-2026 range with fixed detector | NO — Campaign V3 uses 0.60 (same as V2) |

-> All known issues are non-blocking for V3 launch.

### Your first response must contain:
1. Confirmed milestone scope (what you will implement)
2. Acceptance criteria (how we know it is done)
3. Which known issues are in-scope vs out-of-scope (with reasoning)
4. Implementation plan (ordered steps)
5. Only then: start executing

### Commit discipline
- WHAT / WHY / STATUS in every commit message
- Do NOT self-mark as "done". Claude Code audits after campaign completes.
- Commit tracker update BEFORE launching campaign (so state is recorded)
- After launch, report: PID, estimated completion time, first trial summary

### Notes
- This is a launch milestone, NOT an implementation milestone — no code changes
- Campaign will run for ~12-14 hours; you don't need to wait for completion
- After launch confirmation, milestone is complete from your perspective
- Claude Code will audit results after campaign completes (separate milestone)
- If launch fails, diagnose and report — do NOT retry blindly
- Server load: bot is running in PAPER mode, but campaign is CPU-intensive — acceptable overlap
