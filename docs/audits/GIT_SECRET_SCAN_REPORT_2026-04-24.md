# Git Secret Scan Report
Date: 2026-04-24
Branch: market-truth-v3
Commit Baseline: 2b59bb5

## Scope
- `git log --all --name-status -- .env .env.example btc-bot-deploy btc-bot-deploy.pub btc-bot-deploy-v2 btc-bot-deploy-v2.pub`
- `git log --all -G "BINANCE_API_(KEY|SECRET)|TELEGRAM_BOT_TOKEN|PRIVATE KEY|BEGIN RSA|BEGIN OPENSSH|X-MBX-APIKEY" --oneline -- .`
- `git log --all -G "BINANCE_API_(KEY|SECRET)|TELEGRAM_BOT_TOKEN|PRIVATE KEY|BEGIN RSA|BEGIN OPENSSH|X-MBX-APIKEY" -p --max-count=6 -- .`

## Results
- Confirmed tracked env-template file:
  - commit `590064c` adds `.env.example`
- No tracked `.env` file found in sampled git history review
- No tracked deploy private key file found in sampled git history review
- Regex hits were dominated by:
  - env variable names in `.env.example`
  - docs about deployment / egress / environment setup
  - tests using obvious dummy values such as repeated `a` / `b`
  - runtime/client code that references `X-MBX-APIKEY` or env var names

## Evidence Notes
- `.gitignore` excludes `.env` and both deploy key pairs
- The sampled patch review did not surface any obvious live secret literal, private key body, or committed credential value
- This was a targeted git-history review, not a dedicated high-entropy scanner output from `gitleaks` or `trufflehog`

## Confidence / Limitation
- Confidence is moderate for the sampled history and tracked sensitive filenames
- Confidence is not equivalent to a full dedicated secret-scanner run across all history blobs
- No conclusion was drawn about secrets outside git history or outside repository tracking
