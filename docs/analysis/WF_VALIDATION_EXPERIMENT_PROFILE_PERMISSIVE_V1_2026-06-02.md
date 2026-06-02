# WF Validation: experiment-profile-permissive-v1

Date: 2026-06-02
Builder: Codex
Milestone: Phase A2 offline WF validation

## Scope

Run offline walk-forward validation for `experiment-profile-permissive-v1`,
the legalized identity for the production PAPER profile with BTC
`strategy.min_sweep_depth_pct = 0.005`.

This is a builder validation report, not a Claude Code final audit or promotion
approval.

## GitHub Pre-Check

Before running A2 on this PC, Codex fetched GitHub and fast-forwarded
`deploy/multi-asset-paper-v1` from local `dc7a37b` to
`origin/deploy/multi-asset-paper-v1` at `db9973a`.

No A2 implementation/report commit was present on the deploy branch after
fetch. The audit branch `origin/claude/epic-darwin-z8Moa` was present at
`0648c4c` with A1.deploy audit DONE.

## Data Source

Expected A2 amendment requested a read-only SSH fetch of the BTC snapshot from
`root@204.168.146.253` and a server-side/local SHA256 comparison.

On this PC, SSH access was blocked before data transfer:

- documented key path `c:\development\btc-bot\btc-bot-deploy-v2` did not exist;
- direct SSH with the local agent failed with `Permission denied (publickey)`;
- no production state was modified.

Because local PC already had a historical SQLite DB with BTC coverage through
the required validation range, the run used local read-only source DB:

| Item | Value |
|---|---|
| Source DB | `storage/btc_bot.db` |
| Source DB SHA256 | `4d6a3f9e8a97d095fcbf6221e24c720c516fe7373b0c4a306978b56cf54e8eba` |
| BTCUSDT 15m coverage | `2020-09-01T00:00:00+00:00` to `2026-05-25T21:45:00+00:00` |
| BTCUSDT 15m rows | `200,907` |
| Validation range | `2022-01-01` to `2026-03-28` |
| Production state modified | `false` |

This data-source deviation is audit-relevant. The run validates the legalized
parameter set against the available local historical DB, but it does not satisfy
the amended server-side snapshot SHA requirement.

## Execution

Local PC path: `c:\Users\lewie\Projects\btc-bot`

Runtime:

- `.venv\Scripts\python.exe`
- Python `3.11.9`
- Research Lab protocol: `research_lab/configs/default_protocol.json`
- Protocol hash: `023dc84c2cd8eff7e0226a1cb74cca24ce64a896aacac7f8c4a61199fac9e1b8`

Candidate construction:

- base settings: `load_settings(profile="experiment")`
- candidate override: `{"min_sweep_depth_pct": 0.005}`
- candidate config hash: `68fd6caf83ff549f1741d04585a06f6b758a87c40380bc15450d5e35b0319593`
- base config hash before A2 override: `c21ce9f4ef5da819b8d038bf66b0af73375829b1c1dd5d31e3b5578dccc7b084`

Local generated artifacts, not committed:

- `research_lab/revalidation/experiment-profile-permissive-v1/summary.json`
- `research_lab/revalidation/experiment-profile-permissive-v1/evaluation.json`
- `research_lab/revalidation/experiment-profile-permissive-v1/walkforward_report.json`
- `research_lab/revalidation/experiment-profile-permissive-v1/recommendation.json`

The temporary SQLite snapshot under `research_lab/snapshots/` was removed after
the run.

## Candidate Full-Range Metrics

| Metric | Value |
|---|---:|
| Expectancy R | `1.6684` |
| Profit factor | `3.6275` |
| Max drawdown | `6.13%` |
| Trades | `500` |
| Sharpe | `10.2509` |
| Win rate | `52.20%` |
| pnl_abs | `278,220.28` |

Full-range minimum trade gate passed. The candidate produced materially more
trades than frozen trial-00095, as expected from the permissive BTC threshold.

## Walk-Forward Result

| Gate | Result |
|---|---|
| WF passed | PASS: `2/2` windows |
| Fragile | PASS: `false` |
| IS degradation | `-35.80%` |
| Pipeline verdict | `SCREENING_ONLY` |
| Recommendation risks | `pnl_sanity_review_required`, `oos_outperformance_review_required` |

### Per-Window Metrics

| Window | Passed | Train ER | Val ER | Degradation | Train PF | Val PF | Train DD | Val DD | Train trades | Val trades | Val Sharpe |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | true | `1.3139` | `2.1188` | `-61.26%` | `2.7897` | `4.1496` | `6.13%` | `5.06%` | `238` | `177` | `12.9335` |
| 2 | true | `1.6621` | `1.8341` | `-10.35%` | `3.8003` | `4.0733` | `6.13%` | `5.63%` | `416` | `72` | `10.4009` |

## Builder Verdict

`SCREENING_ONLY`

`experiment-profile-permissive-v1` passes the mechanical post-hoc WF gate:

- `2/2` WF windows passed;
- `fragile=false`;
- validation trade counts are strong: `177` and `72`;
- no low-OOS-trade review flag;
- no PF hard review flag.

It is not promotion-ready without Claude Code audit because:

- `pnl_sanity_review_required=true` due high absolute historical pnl;
- `oos_outperformance_review_required=true` due negative IS degradation,
  especially window 1;
- the amended server-side snapshot SHA requirement was not satisfied on this PC
  because the deploy key was absent.

## Recommended Next Step

Claude Code should audit this A2 report and decide whether the PC data-source
deviation is acceptable or whether Codex must rerun A2 after the production
deploy key is installed on this PC.

Until audit closure, `experiment-profile-permissive-v1` remains
`SCREENING_ONLY` and must not be treated as a promotion-approved replacement for
frozen trial-00095.
