# Runtime Instance Control

## Purpose

The bot runtime must have exactly one active `main.py --mode PAPER` or
`main.py --mode LIVE` process. A second runtime can duplicate decision cycles
and write conflicting diagnostic rows to `storage/btc_bot.db`.

## Incident Reference

On 2026-05-14 through 2026-05-17, a manually launched `nohup .venv/bin/python
main.py --mode PAPER` process ran alongside the managed `btc-bot.service`
process. The incident created duplicate `decision_outcomes` rows with a second
config hash. The rogue process was stopped on 2026-05-17.

## Guard

`main.py` acquires an exclusive runtime file lock before bot initialization for
PAPER and LIVE modes.

Default lock path:

```text
/tmp/btc-bot-runtime.lock
```

Override:

```bash
BTC_BOT_RUNTIME_LOCK_PATH=/custom/path/btc-bot-runtime.lock
```

The lock is process-held. It is released automatically when the process exits,
including crash or `SIGKILL`. The lock file itself may remain on disk, but a
stale file does not block startup unless another process still holds the lock.

## Troubleshooting

If the bot refuses to start with:

```text
Another bot runtime instance is already running.
```

check active processes first:

```bash
ps -eo pid,ppid,lstart,cmd | grep "main.py --mode" | grep -v grep
```

If a rogue manual process exists, stop only that process. Do not stop
`btc-bot.service` unless intentionally restarting the managed runtime.

If no bot process exists and startup still fails, remove the stale lock file:

```bash
rm -f /tmp/btc-bot-runtime.lock
systemctl restart btc-bot
```

## Validation

After deploy or restart:

```bash
systemctl is-active btc-bot
ps -eo pid,ppid,lstart,cmd | grep "main.py --mode" | grep -v grep
```

Expected result: exactly one bot runtime process.

