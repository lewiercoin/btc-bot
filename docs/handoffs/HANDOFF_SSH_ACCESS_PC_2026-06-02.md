# Handoff: restore SSH access from PC

Date: 2026-06-02
Audience: Codex running on the laptop

## Problem

The PC at `c:\Users\lewie\Projects\btc-bot` cannot use SSH fetch/access because this machine does not have a usable SSH private key. The laptop has working access.

Do not transfer any private SSH key through this repository, GitHub, chat, issues, commits, or agent communication files.

## Preferred safe path

Create a new SSH keypair on the PC, then use only the PC public key to grant access.

The user should run this on the PC:

```powershell
ssh-keygen -t ed25519 -C "btc-bot-pc-2026-06-02"
Get-Content $env:USERPROFILE\.ssh\id_ed25519.pub
```

The user can paste the `.pub` output to Codex on the laptop, or place only that public key in a temporary handoff message/file. Public keys are safe to share.

## Laptop Codex task

When the user provides the PC public key:

1. Verify it starts with `ssh-ed25519 ` and contains no private-key block text.
2. Add the key to any required remote access targets.

For production server access, append the PC public key to:

```text
root@204.168.146.253:/root/.ssh/authorized_keys
```

Suggested command from the laptop:

```bash
printf '%s\n' '<PC_PUBLIC_KEY_HERE>' | ssh root@204.168.146.253 'umask 077; mkdir -p ~/.ssh; cat >> ~/.ssh/authorized_keys'
```

Then ask the PC Codex/user to test:

```powershell
ssh root@204.168.146.253
```

For GitHub SSH fetch access, add the PC public key to the user's GitHub account as a new authentication key. If GitHub CLI is authenticated on the laptop, use:

```bash
gh ssh-key add -t "btc-bot PC 2026-06-02" <path-to-temp-public-key-file>
```

Otherwise, the user can add it manually in GitHub:

Settings -> SSH and GPG keys -> New SSH key.

Then ask the PC Codex/user to test:

```powershell
ssh -T git@github.com
git fetch
```

## If the user insists on moving the existing private key

Prefer not to do this. A new per-machine key is cleaner, revocable, and auditable.

If it must be done, transfer the private key only over a direct encrypted channel or physical medium, never through repo/GitHub. After copying, set restrictive permissions on Windows and verify the key works. This is a fallback, not the recommended route.

