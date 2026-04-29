# HANDOFF → CODEX: RECLAIM-EDGE-REVALIDATION-V1 Full Replay

**Date:** 2026-04-29  
**From:** Claude Code (auditor)  
**To:** Codex (builder)  
**Type:** Offline research work (does NOT modify runtime)

---

## Checkpoint

**Last commit:** `d89f7a6` (feat: add runtime config tracking to modeling checkpoint)  
**Branch:** `modeling-context-closure`  
**Working tree:** clean

**Step 0 artifacts:**
- ✅ `docs/research_lab/TRIAL_63_FEASIBILITY.md` - verdict GO
- ✅ `research_lab/trial_63_baseline_config.json` - exact Trial #63 params

---

## Before you start

Read these files (mandatory):
1. `docs/research_lab/TRIAL_63_FEASIBILITY.md` - Step 0 findings, operational caveats
2. `research_lab/trial_63_baseline_config.json` - exact baseline params
3. `AGENTS.md` - discipline + your workflow rules

---

## Scope: RECLAIM-EDGE-REVALIDATION-V1 Full Replay

**Pytanie badawcze:** Czy Trial #63 edge (expectancy_r=0.99, PF=2.49, trades=183) reprodukuje się w clean pre-MODELING-V1 data?

**Method:** Offline backtest replay z exact Trial #63 params na pre-MODELING-V1 window.

---

## Deliverables

1. **Backtest execution:**
   - Config: exact Trial #63 params z `trial_63_baseline_config.json`
   - Data window: pre-MODELING-V1 (recommendation: 2025-04-01 to 2026-04-13, lub comparable)
   - Fill model: `SimpleFillModel` (0.04% fees, funding accrued, deterministic)
   - Output: trade log + metrics

2. **Metrics comparison:**
   | Metric | Original Trial #63 | Replay | Delta | Verdict |
   |---|---:|---:|---:|---|
   | Trades count | 183 | ? | ? | ? |
   | Win rate | 52.5% | ? | ? | ? |
   | Expectancy (R) | 0.99 | ? | ? | ? |
   | Profit factor | 2.49 | ? | ? | ? |
   | Max DD % | 5.4% | ? | ? | ? |

3. **Revalidation report:**
   - File: `docs/research_lab/TRIAL_63_REVALIDATION_YYYY-MM-DD.md`
   - Verdict: REPRODUCED | DEGRADED | FAILED
   - Edge quality: same/better/worse vs original
   - Recommendation: keep baseline | redesign baseline | investigate divergence

---

## Operational Safety (CRITICAL)

### Environment selection

**Option A: Local/separate machine (RECOMMENDED)**
- ✅ Zero risk dla production runtime
- ✅ Pełna kontrola nad resources
- ✅ Nie konkuruje z MODELING-CONTEXT-CLOSURE sample collection
- ⚠️ Wymaga DB snapshot copy

**Option B: Production server (tylko jeśli A niemożliwe)**
- ⚠️ Risk: CPU/I/O contention z production bot
- ⚠️ Risk: opóźnienia decision cycles, missed signals
- ✅ Dostęp do production data bez kopiowania
- **MANDATORY mitigations:**
  1. Snapshot DB przed replay (nie operować bezpośrednio na `storage/btc_bot.db`)
  2. Throttling: `nice -n 19 ionice -c3 python3 ...`
  3. CPU limit (jeśli dostępne): `cpulimit -l 50` OR `systemd-run --property=CPUQuota=50%`
  4. Active monitoring podczas replay (load average, bot logs, checkpoint output)
  5. Kill switch: jeśli bot degradacja → STOP replay (nie bota)

**Default recommendation: Option A** (lokalny/osobny replay)

### Pre-flight checklist (jeśli Option B)

- [ ] Production bot health verified (healthy=1, no errors)
- [ ] DB snapshot created (`cp storage/btc_bot.db /tmp/btc_bot_snapshot_YYYYMMDD.db`)
- [ ] Throttling command prepared (`nice -n 19 ionice -c3 ...`)
- [ ] Monitoring plan: watch `journalctl -u btc-bot -f` + load average
- [ ] Kill command ready: `pkill -f backtest_runner.py` (not `systemctl stop btc-bot`)
- [ ] MODELING-CONTEXT-CLOSURE checkpoint baseline captured (pre-replay state)

### During replay monitoring (Option B)

**Watch for:**
- Load average spike > 2.0 (1-core VPS threshold)
- Bot log warnings: "decision cycle delayed", "websocket lag"
- Checkpoint degradation: decision_cycles count stagnation, signal miss rate spike

**Action if degraded:**
1. `pkill -f backtest_runner.py` (stop replay, not bot)
2. Verify bot recovery (`systemctl status btc-bot`)
3. Run checkpoint to confirm sample collection resumed
4. Switch to Option A (local replay)

---

## Target files

**Input:**
- `research_lab/trial_63_baseline_config.json` - params source
- `storage/btc_bot.db` - production data (snapshot copy recommended)

**Output:**
- `docs/research_lab/TRIAL_63_REVALIDATION_YYYY-MM-DD.md` - report
- `research_lab/trial_63_replay_trades.csv` (optional) - detailed trade log
- `research_lab/trial_63_replay_metrics.json` (optional) - full metrics

---

## Implementation approach

### Recommended: Standalone backtest script

**Rationale:**
- Production `research_lab/research_lab.db` has older schema (Step 0 caveat)
- Standalone backtest avoids research lab DB modifications
- Cleaner isolation

**Tool:** `backtest/backtest_runner.py` (direct invocation, not via research lab CLI)

**Steps:**
1. Load Trial #63 params from `trial_63_baseline_config.json` (programmatically)
2. Initialize backtest runner with exact params
3. Run against DB snapshot (local copy OR production snapshot)
4. Write output to new file (not research_lab.db)

### Alternative: Research lab CLI replay

**Tool:** `python3 -m research_lab.cli replay-candidate --candidate-id run13-regime-aware-trial-00063`

**Caveat:** Requires dedicated revalidation store (not production research_lab.db in-place)

---

## Config reconstruction

**CRITICAL:** Trial #63 params are EXACT, stored in `trial_63_baseline_config.json`.

**Do NOT:**
- Use current `settings.py` profiles (experiment/default differ from Trial #63)
- Mix Trial #63 params with current runtime config

**DO:**
- Load params programmatically from JSON
- Verify key params match original (min_rr=2.1, confluence_min=3.6, allow_long_in_uptrend=false)

---

## Known issues

None from Step 0. Feasibility check passed all gates.

---

## Your first response must contain

1. **Environment choice:** Option A (local) OR Option B (production throttled)
2. **Data window selection:** start/end dates for replay
3. **Tool selection:** backtest_runner.py standalone OR research lab CLI
4. **Acceptance criteria:** what metrics deviation counts as REPRODUCED vs DEGRADED
5. **Implementation plan:** ordered steps
6. **Safety checklist completion** (if Option B)
7. Only then: start execution

---

## Commit discipline

- WHAT / WHY / STATUS in every commit message
- Do NOT self-mark as "done". Claude Code audits after completion.

---

## Parallel work context

**MODELING-CONTEXT-CLOSURE continues in parallel:**
- Production monitoring active (daily checkpoints)
- This replay work does NOT block MODELING
- This replay does NOT change runtime config
- Two independent fronts: prospective (MODELING) + retrospective (RECLAIM)

**Operational priority:** MODELING sample collection > RECLAIM replay  
**If conflict:** Stop replay, preserve MODELING runtime

---

**Handoff complete. Awaiting Codex environment choice + implementation plan.**
