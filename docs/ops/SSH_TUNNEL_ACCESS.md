# SSH Tunnel Access for BTC Bot Dashboard

The production dashboard must stay bound to `127.0.0.1:8080`. Operators access it through an SSH tunnel only.

## Prerequisites

- SSH key: `c:\development\btc-bot\btc-bot-deploy-v2`
- Server: `root@204.168.146.253`
- Local dashboard URL after tunnel setup: `http://127.0.0.1:8080`

## Open the Tunnel from Windows

Run:

```powershell
C:\Windows\System32\OpenSSH\ssh.exe -i c:\development\btc-bot\btc-bot-deploy-v2 -L 8080:127.0.0.1:8080 root@204.168.146.253
```

Keep that SSH session open. While it is open, browse to:

```text
http://127.0.0.1:8080
```

The dashboard API is then available locally, for example:

```powershell
curl.exe http://127.0.0.1:8080/api/status
```

## Verify the Dashboard Is Not Public

From a machine that is not tunneled into the server, this request must fail:

```powershell
curl.exe http://204.168.146.253:8080/api/status
```

Expected result: connection refused or timeout.

## Server-Side Verification

Use these checks after deployment:

```bash
systemctl cat btc-bot-dashboard
ufw status
ss -tlnp | grep 8080
journalctl -u btc-bot-dashboard -n 50 --no-pager
```

Expected state:

- `ExecStart` uses `--host 127.0.0.1 --port 8080`
- `ufw status` does not list `8080/tcp`
- `ss -tlnp` shows `127.0.0.1:8080`, not `0.0.0.0:8080`
- `journalctl` shows clean startup without binding errors
