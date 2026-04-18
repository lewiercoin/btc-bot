# Server Access - Production Bot

## SSH Credentials

**Server:** `root@204.168.146.253`  
**SSH Key Location:** `c:\development\btc-bot\btc-bot-deploy-v2`  
**Bot Directory:** `/home/btc-bot/btc-bot`  
**Service Name:** `btc-bot.service`

## Key Rotation History

| Date | Key File | Status | Reason |
|---|---|---|---|
| 2026-04-19 | `btc-bot-deploy-v2` | **ACTIVE** | Rotation after key exposure in chat |
| 2026-04-18 | `btc-bot-deploy` | REVOKED | Compromised (exposed in Perplexity chat) |

## Standard Commands

### Connection
```bash
ssh -i "c:\development\btc-bot\btc-bot-deploy-v2" root@204.168.146.253
```

### Status Check
```bash
ssh -i "c:\development\btc-bot\btc-bot-deploy-v2" root@204.168.146.253 'sudo systemctl status btc-bot --no-pager -l'
```

### Logs (last 100 lines)
```bash
ssh -i "c:\development\btc-bot\btc-bot-deploy-v2" root@204.168.146.253 'sudo journalctl -u btc-bot -n 100 --no-pager'
```

### Deploy (fetch + merge from GitHub)
```bash
ssh -i "c:\development\btc-bot\btc-bot-deploy-v2" root@204.168.146.253 'cd /home/btc-bot/btc-bot && git fetch github && git merge github/main --ff-only && sudo systemctl restart btc-bot'
```

### Restart Bot
```bash
ssh -i "c:\development\btc-bot\btc-bot-deploy-v2" root@204.168.146.253 'sudo systemctl restart btc-bot && sleep 3 && sudo systemctl status btc-bot --no-pager'
```

## Security Notes

- **Private key location:** `c:\development\btc-bot\btc-bot-deploy-v2`
- **Never share private key** in chat, email, or commit to git
- **Key is in .gitignore** - verify before any commit
- **Rotation procedure:** Generate new keypair → add to server → remove old → update this doc

## For External Consultants (e.g., Perplexity)

**DO NOT share private key.** Use Option A workflow:

1. User runs command locally with key
2. User pastes output to consultant
3. Consultant analyzes output
4. No secrets leave user's machine

Example:
```bash
ssh -i "c:\development\btc-bot\btc-bot-deploy-v2" root@204.168.146.253 'bash /home/btc-bot/btc-bot/scripts/analyze_reclaim_margins_24h.sh' > analysis.txt
# Paste analysis.txt to consultant
```

## Builder Instructions

All builders (Codex, Cascade, Claude Code) should:
- Reference this file for current key location
- Use quoted paths on Windows: `"c:\development\btc-bot\btc-bot-deploy-v2"`
- Never attempt to read or display the private key contents
- Always check this doc for latest key rotation status before SSH commands
