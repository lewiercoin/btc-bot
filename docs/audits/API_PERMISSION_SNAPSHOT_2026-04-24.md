# API Permission Snapshot
Date: 2026-04-24
Source: Audit evidence note

## Status
INCOMPLETE

## Verified
- Exchange credentials are loaded from environment variables in `settings.py`
- Signed Binance requests are implemented in `data/rest_client.py`
- Recovery startup sync and open-order / active-position checks use signed request paths when applicable

## Not Independently Verified During This Audit
- withdrawal disabled
- IP whitelist enabled
- exact exchange-side trading permission scope

## Reason
- no operator screenshot from Binance API Management UI was provided
- no exchange-side permission export artifact existed in the repository
- this audit intentionally avoided printing or handling raw secrets

## Required Follow-Up Evidence
Provide one of the following:
- Binance API Management screenshot showing:
  - trading enabled as intended
  - withdrawal disabled
  - IP restriction enabled
- or a read-only exchange/API restriction report that prints only booleans / capability flags and never exposes secrets
