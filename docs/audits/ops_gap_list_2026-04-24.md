# Ops Gap List
Date: 2026-04-24

## Critical
- Public dashboard exposure on `0.0.0.0:8080`
- UFW allows `8080/tcp` from anywhere
- Unauthenticated dashboard control endpoints available on public interface

## High
- Repo unit files drift from deployed unit files
- Deployment docs state loopback-only dashboard, but production is public
- No proven crash alert routing beyond app-level audit/Telegram hooks
- Safe-mode diagnostic script is stale for current log/schema layout

## Medium
- `scripts/query_bot_status.py` partially mismatched with current schema/event vocabulary
- Manual recovery guide file not present at expected docs path
- Empty-reason `cleared` safe-mode events reduce forensic clarity
