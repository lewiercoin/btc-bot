# AUDIT: TELEGRAM_ALERTS_RUNTIME_ACTIVATION_V1
Date: 2026-05-22
Auditor: Claude Code
Commit: 4f7ba25

## Verdict: DONE

**Scope:** Runtime overlay support for Telegram alert activation with secrets from environment only. Disabled by default, includes one-shot test script.

## Layer Separation: PASS
- Config layer: AlertConfig validation and runtime overlay in settings.py
- Script layer: send_telegram_test_alert.py (one-shot test, no runtime coupling)
- Notifier layer: TelegramNotifier (already exists, unchanged in this milestone)
- Test layer: test_settings_profile.py (4 new tests for overlay validation)
- No cross-layer violations or unexpected dependencies

## Contract Compliance: PASS
- **Runtime overlay contract:** settings.json → validation → config hash (same pattern as multi_asset, paper_simulation)
- **Notifier contract:** TelegramConfig(enabled, bot_token, chat_id) already exists, unchanged
- **Activation surface:** Environment variables + settings.json (no secrets in repository)
- **Backward compatibility:** Default telegram_enabled=False, no behavior change when disabled

## Determinism: PASS
- Overlay parsing deterministic (JSON → validation → dataclass replace)
- Config validation deterministic (boolean check, non-empty string check)
- Config hash includes alerts (activation changes hash → audit trail)
- Test script deterministic (load settings → check credentials → send message)
- Property reads from environment (os.getenv) deterministic for given env state

## Backward Compatibility: PASS
- Default `telegram_enabled=False` (no production impact until activated)
- AlertConfig already exists (overlay adds activation surface, not new config class)
- TelegramNotifier already exists (no changes to notifier logic)
- 623 tests pass (24 skipped) — 4 new tests for alerts overlay
- No changes to runtime behavior when telegram_enabled=False
- Existing orchestrator Telegram integration unchanged (already calls notifier)

## State Integrity: PASS
- No state mutation (config-only change, no database writes)
- No persistent state in test script (one-shot send, exits immediately)
- Environment variables are external state (managed by systemd, not runtime)
- Config hash change on activation provides audit trail

## Error Handling: PASS
- **Invalid telegram_enabled (not boolean):** ValueError at config load (fail-fast)
- **Empty env var name:** ValueError at config validation (telegram_bot_token_env/telegram_chat_id_env must be non-empty)
- **Missing credentials in test script:** Exit code 2 ("telegram credentials missing"), no send attempt
- **Disabled in test script:** Exit code 2 ("telegram_enabled=false"), no send attempt
- **Network/API failure:** Exit code 1 ("sent=false"), error contained

## Smoke Coverage: PASS
- **Config overlay tests (4 new):**
  - `test_load_settings_experiment_profile_applies_alerts_runtime_overlay()` → telegram_enabled=True applied, env names preserved
  - `test_load_settings_experiment_profile_alerts_overlay_changes_config_hash()` → config hash changes when enabled
  - `test_load_settings_experiment_profile_rejects_invalid_alerts_overlay()` → telegram_enabled="yes" (string) rejected
  - `test_load_settings_experiment_profile_rejects_empty_alert_env_name()` → telegram_bot_token_env="" rejected
- **Test script behavior:** User verified script returns "telegram_enabled=false" when not configured (exit 2)
- **Full suite: 623 passed (24 skipped)**

## Tech Debt: LOW
- Clean implementation (extends runtime overlay pattern)
- No NotImplementedError stubs
- No duplication (reuses _section_overrides, validation pattern)
- One-shot test script (simple, no complexity or persistent state)
- No interactive Telegram commands (explicitly deferred, documented in DECISIONS_LOG)

## AGENTS.md Compliance: PASS
- Commit discipline: WHAT/WHY/STATUS in commit message (4f7ba25)
- Scope purity: overlay + test script only, no interactive commands, no behavior changes
- Documentation: DECISIONS_LOG and MILESTONE_TRACKER updated with boundaries and activation plan

## Security Analysis: PASS

**Critical: No secrets in repository** ✓
- `telegram_bot_token_env` stores env var NAME ("TELEGRAM_BOT_TOKEN"), not actual token
- `telegram_chat_id_env` stores env var NAME ("TELEGRAM_CHAT_ID"), not actual chat ID
- settings.json contains only env var names, not secrets
- Actual secrets read at runtime via @property methods:
  ```python
  @property
  def telegram_bot_token(self) -> str:
      return os.getenv(self.telegram_bot_token_env, "")
  
  @property
  def telegram_chat_id(self) -> str:
      return os.getenv(self.telegram_chat_id_env, "")
  ```
- Default empty string if env var not set (safe fallback)

**Credential validation in test script:** ✓
```python
if not settings.alerts.telegram_enabled:
    print("telegram_enabled=false")
    return 2  # No send attempt
if not settings.alerts.telegram_bot_token or not settings.alerts.telegram_chat_id:
    print("telegram credentials missing")
    return 2  # No send attempt
```
- Script validates telegram_enabled=True before sending
- Script validates credentials present (not None/empty) before sending
- Exit code 2 = not configured (safe, no error exposure)

**Activation safety:** ✓
- Disabled by default (no unsolicited Telegram sends on deploy)
- Requires explicit operator action:
  1. Set env vars (systemd drop-in)
  2. Enable in settings.json (alerts.telegram_enabled=true)
  3. Restart service
  4. Run test script to verify
- Test script provides safe verification before orchestrator uses Telegram
- Deactivation: set telegram_enabled=false in settings.json, restart

**Env var name validation:** ✓
- telegram_bot_token_env must be non-empty string (prevents accidental empty env var name)
- telegram_chat_id_env must be non-empty string
- Default values hardcoded ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID") are standard names
- Can override in settings.json if different env var names needed (e.g., separate bots per environment)

## Test Script Analysis: PASS

**scripts/send_telegram_test_alert.py:**
- **Purpose:** One-shot test alert after code-only deploy, before enabling in orchestrator
- **Input:** --profile (default: experiment), --message (default: "BTC bot Telegram test alert.")
- **Behavior:**
  1. Load settings from profile
  2. Check telegram_enabled=True (exit 2 if False)
  3. Check credentials present (exit 2 if missing)
  4. Send message via TelegramNotifier
  5. Print "sent=true" or "sent=false"
- **Exit codes:**
  - 0: Success (message sent)
  - 1: Send failed (network/API error)
  - 2: Not configured (telegram_enabled=False or credentials missing)
- **Safety:**
  - No send if disabled or credentials missing ✓
  - One-shot (exits immediately, no loop/retry) ✓
  - Doesn't modify state (read-only check + send) ✓

## Production Activation Surface: PASS

**Example systemd drop-in (`/etc/systemd/system/btc-bot.service.d/telegram.conf`):**
```ini
[Service]
Environment="TELEGRAM_BOT_TOKEN=<actual-token>"
Environment="TELEGRAM_CHAT_ID=<actual-chat-id>"
```

**Example settings.json:**
```json
{
  "schema_version": "v1.0",
  "multi_asset": { ... },
  "paper_simulation": { ... },
  "alerts": {
    "telegram_enabled": true
  }
}
```

**Activation sequence:**
1. Code-only deploy (feature code deployed, telegram_enabled=False by default)
2. Create systemd drop-in with env vars (systemctl daemon-reload)
3. Edit settings.json: alerts.telegram_enabled=true
4. Restart service: systemctl restart btc-bot.service
5. Test: python scripts/send_telegram_test_alert.py --profile experiment
6. Verify: "sent=true" printed, message received in Telegram

**Deactivation/rollback:**
1. Edit settings.json: alerts.telegram_enabled=false (or remove alerts section)
2. Restart service: systemctl restart btc-bot.service
3. Telegram sends stop, env vars preserved but unused

**Env var names override (if needed):**
```json
{
  "alerts": {
    "telegram_enabled": true,
    "telegram_bot_token_env": "PAPER_BOT_TOKEN",
    "telegram_chat_id_env": "PAPER_CHAT_ID"
  }
}
```
- Allows separate bots per environment (e.g., PAPER_BOT_TOKEN vs LIVE_BOT_TOKEN)
- Env var names validated (must be non-empty strings)

## Critical Issues (must fix before next milestone)
None.

## Warnings (fix soon)
None. Interactive Telegram commands explicitly deferred to separate milestone.

## Observations (non-blocking)
1. Clean runtime overlay for Telegram alert activation (no secrets in repo)
2. Disabled by default (telegram_enabled=False)
3. Secrets sourced from environment variables only (systemd drop-in)
4. Existing TelegramNotifier unchanged (milestone adds activation surface only)
5. One-shot test script for safe post-deploy verification
6. Config hash includes alerts (activation changes hash → audit trail)
7. Env var name validation (must be non-empty strings)
8. Test script exit codes: 0=success, 1=send failed, 2=not configured
9. 623 tests pass (4 new tests for alerts overlay)
10. No interactive Telegram commands (explicitly deferred, documented)
11. Can override env var names in settings.json (allows separate bots per environment)
12. Backward compatible (AlertConfig already exists, overlay adds activation only)

## Recommended Next Step

**Telegram alert activation surface is DONE. Ready for code-only deployment. Activation is separate operational decision.**

### Deployment: Code-only (no activation)

**Goal:** Deploy Telegram alert overlay to production without activating.

**Deployment command:**
```bash
ssh root@204.168.146.253
cd /home/btc-bot/btc-bot
git pull origin deploy/multi-asset-paper-v1  # expect: 4f7ba25 or later

# Restart service (settings.py changes)
systemctl restart btc-bot.service
```

**Post-deployment verification:**
```bash
# Verify service restart
systemctl status btc-bot.service --no-pager  # Active, no restart loop

# Verify bot status (telegram should be disabled by default)
python scripts/query_bot_status.py  # alerts.telegram_enabled=False

# Test script without activation (should exit 2)
python scripts/send_telegram_test_alert.py --profile experiment
# Expected: "telegram_enabled=false", exit code 2
```

**Expected first state:**
- Service active with clean restart
- alerts.telegram_enabled=False (default, not activated)
- No Telegram sends (disabled)
- Test script exits 2 (not configured)

### Future Activation (Separate Operational Decision)

**When ready to enable Telegram alerts:**

1. Create systemd drop-in:
   ```bash
   sudo mkdir -p /etc/systemd/system/btc-bot.service.d/
   sudo tee /etc/systemd/system/btc-bot.service.d/telegram.conf <<EOF
   [Service]
   Environment="TELEGRAM_BOT_TOKEN=<actual-token>"
   Environment="TELEGRAM_CHAT_ID=<actual-chat-id>"
   EOF
   sudo systemctl daemon-reload
   ```

2. Verify env vars loaded:
   ```bash
   systemctl show btc-bot.service | grep TELEGRAM
   # Expected: TELEGRAM_BOT_TOKEN=..., TELEGRAM_CHAT_ID=...
   ```

3. Edit production settings.json:
   ```bash
   # Add or update alerts section
   cat > settings.json <<'EOF'
   {
     "schema_version": "v1.0",
     "multi_asset": { ... },
     "paper_simulation": { ... },
     "alerts": {
       "telegram_enabled": true
     }
   }
   EOF
   ```

4. Restart service:
   ```bash
   systemctl restart btc-bot.service
   ```

5. Test alert:
   ```bash
   python scripts/send_telegram_test_alert.py --profile experiment --message "BTC/ETH/SOL PAPER bot test alert"
   # Expected: "sent=true", exit code 0, message received in Telegram
   ```

6. Verify orchestrator can send:
   - Wait for next signal or position close
   - Check Telegram for runtime alerts
   - Verify logs show Telegram send attempts

---

**Next milestone decision:** Code-only deploy overlay → verify clean restart → defer activation to future operational decision → retire old SMC signal bot after verified test alert.
