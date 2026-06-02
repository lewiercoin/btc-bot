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

After the server key became available on this PC, Codex completed the amended
A2 requirement: read-only SSH discovery, server-side SHA256, local fetch, and
post-fetch local SHA256 verification.

The canonical A2 run in this report uses the fetched server snapshot:

| Item | Value |
|---|---|
| Server snapshot | `/home/btc-bot/btc-bot/research_lab/snapshots/replay-optuna-default-v3-trial-00095.db` |
| Local fetched snapshot | `research_lab/snapshots/replay-optuna-default-v3-trial-00095.db` |
| Server SHA256 | `ad8c5e7b4f541d5c34b2d6dde83aa0110f885a9eb4e0fa2d67c6705167363bca` |
| Local SHA256 | `ad8c5e7b4f541d5c34b2d6dde83aa0110f885a9eb4e0fa2d67c6705167363bca` |
| SHA256 verified | `true` |
| BTCUSDT 15m coverage | `2020-09-01T00:00:00+00:00` to `2026-04-17T19:15:00+00:00` |
| BTCUSDT 15m rows | `197,262` |
| Validation range | `2022-01-01` to `2026-03-28` |
| Production state modified | `false` |

An earlier local-PC run used `storage/btc_bot.db` because SSH was initially
unavailable. That local run is superseded by the server-snapshot run above.

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

- `research_lab/revalidation/experiment-profile-permissive-v1-server-snapshot/summary.json`
- `research_lab/revalidation/experiment-profile-permissive-v1-server-snapshot/evaluation.json`
- `research_lab/revalidation/experiment-profile-permissive-v1-server-snapshot/walkforward_report.json`
- `research_lab/revalidation/experiment-profile-permissive-v1-server-snapshot/recommendation.json`

The fetched source snapshot is retained locally under `research_lab/snapshots/`
for audit reproduction and is ignored by git.

## Candidate Full-Range Metrics

| Metric | Value |
|---|---:|
| Expectancy R | `1.6590` |
| Profit factor | `3.5310` |
| Max drawdown | `6.13%` |
| Trades | `496` |
| Sharpe | `10.1650` |
| Win rate | `51.81%` |
| pnl_abs | `265,542.31` |

Full-range minimum trade gate passed. The candidate produced materially more
trades than frozen trial-00095, as expected from the permissive BTC threshold.

## Walk-Forward Result

| Gate | Result |
|---|---|
| WF passed | PASS: `2/2` windows |
| Fragile | PASS: `false` |
| IS degradation | `-34.05%` |
| Pipeline verdict | `SCREENING_ONLY` |
| Recommendation risks | `pnl_sanity_review_required`, `oos_outperformance_review_required` |

### Per-Window Metrics

| Window | Passed | Train ER | Val ER | Degradation | Train PF | Val PF | Train DD | Val DD | Train trades | Val trades | Val Sharpe |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | true | `1.3139` | `2.1188` | `-61.26%` | `2.7897` | `4.1496` | `6.13%` | `5.06%` | `238` | `177` | `12.9335` |
| 2 | true | `1.6621` | `1.7757` | `-6.83%` | `3.8003` | `3.7698` | `6.13%` | `5.63%` | `416` | `68` | `9.8330` |

## Builder Verdict

`SCREENING_ONLY`

`experiment-profile-permissive-v1` passes the mechanical post-hoc WF gate:

- `2/2` WF windows passed;
- `fragile=false`;
- validation trade counts are strong: `177` and `68`;
- no low-OOS-trade review flag;
- no PF hard review flag.

It is not promotion-ready without Claude Code audit because:

- `pnl_sanity_review_required=true` due high absolute historical pnl;
- `oos_outperformance_review_required=true` due negative IS degradation,
  especially window 1.

## Recommended Next Step

Claude Code should audit this A2 report, the server/local snapshot SHA evidence,
and the persisted local revalidation artifacts.

Until audit closure, `experiment-profile-permissive-v1` remains
`SCREENING_ONLY` and must not be treated as a promotion-approved replacement for
frozen trial-00095.
