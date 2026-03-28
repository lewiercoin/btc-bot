# Codex Handoff: Backtest-Driven Bot Improvements

## Kontekst — co odkryliśmy w backtestach

Cascade (audytor) przeprowadził serię backtestów na pełnych danych historycznych (03-01 → 03-27, 26 dni, ~35k aggtrade buckets, 2499 barów 15m). Oto kluczowe ustalenia:

### Wyniki backtestów

| Run | Zakres | Bars | Signals | Trades | W/L | PnL | Expectancy R |
|-----|--------|------|---------|--------|-----|-----|-------------|
| A | 03-16→03-23 | 768 | 42 | 4 | 1W/3L | -$135 | -0.04R |
| B | 03-01→03-27 | 2499 | 150 | 3 | 0W/3L | -$351 | -1.88R |

**Kluczowe odkrycie:** Run A (startujący 03-16) miał **wygrywający trade** LONG +$273 (+4.97R) na 03-16 12:30. Run B (startujący 03-01) **nigdy nie wykonał tego trade'a** — bo governance zablokował bota po 3 losach 1 marca rano i **nigdy nie odblokował**.

### Trade-by-trade — Run A (03-16→03-23)

| # | Dir | Time | Regime | PnL | R | Exit |
|---|-----|------|--------|-----|---|------|
| 1 | LONG | 03-16 12:30→13:45 | uptrend | +$273 | +4.97R | TP ✅ |
| 2 | SHORT | 03-16 15:15→15:30 | uptrend | -$153 | -1.58R | SL |
| 3 | SHORT | 03-16 23:15→23:30 | uptrend | -$123 | -1.83R | SL |
| 4 | SHORT | 03-17 06:15→06:30 | uptrend | -$132 | -1.72R | SL |

### Trade-by-trade — Run B (03-01→03-27)

| # | Dir | Time | Regime | PnL | R | MFE | Exit |
|---|-----|------|--------|-----|---|-----|------|
| 1 | LONG | 03-01 07:15→09:00 | downtrend | -$117 | -1.88R | $262 | SL |
| 2 | SHORT | 03-01 08:15→08:30 | downtrend | -$113 | -1.95R | $0 | SL |
| 3 | SHORT | 03-01 10:15→10:30 | downtrend | -$121 | -1.81R | $0 | SL |

Bot dostaje 3 losery w 3 godziny → governance lock → **26 dni ciszy**. 150 sygnałów wygenerowanych, 147 odrzuconych.

---

## Zidentyfikowane problemy (priorytet od najwyższego)

### BUG 1 (CRITICAL): `consecutive_losses` nigdy się nie resetuje

**Lokalizacja:** `backtest/backtest_runner.py` linia 725-734, `core/governance.py` linia 60-61

**Problem:** Funkcja `_consecutive_losses()` iteruje po WSZYSTKICH zamkniętych trades od końca i liczy straty do pierwszego wina. Raz osiągnięty limit `max_consecutive_losses=3`, governance blokuje PERMANENTNIE — brak mechanizmu daily reset, brak cooldown-based reset, brak trailing window.

```python
# Aktualny kod — liczy od końca historii, bez okna czasowego
def _consecutive_losses(closed_records: list[_ClosedTradeRecord]) -> int:
    losses = 0
    for record in reversed(closed_records):
        pnl_abs = float(record.trade.pnl_abs)
        if pnl_abs < 0:
            losses += 1
            continue
        if pnl_abs > 0:
            break
    return losses
```

**Efekt:** 3 losery w poniedziałek rano = bot zamrożony do końca świata. To czyni `max_consecutive_losses` de facto kill-switchem, nie safety guardem.

**Rekomendacja Cascade:**

Opcja A (minimalna, zalecana): **Daily reset** — `consecutive_losses` liczy tylko trades z bieżącego dnia UTC. Nowy dzień = nowy licznik.

Opcja B (alternatywa): **Trailing window** — liczy consecutive losses tylko w ostatnich N godzinach (np. 24h). Konfigurowalne via nowy parametr `consecutive_losses_window_hours`.

Opcja C (hybryd): Daily reset + cooldown. Po osiągnięciu limitu, governance blokuje na `cooldown_after_consecutive_losses_hours` (np. 6h), potem reset.

**UWAGA:** Fix musi być spójny między `backtest_runner.py` (metoda `_consecutive_losses` + `_build_runtime_state`) i `orchestrator.py` (live `state_provider`). Oba muszą używać tej samej logiki resetu.

---

### BUG 2 (MEDIUM): `analyze_closed_trades` miesza live trades z backtest trades

**Lokalizacja:** `research/analyze_trades.py` → `analyze_closed_trades()`

**Problem:** Funkcja czyta WSZYSTKIE zamknięte trades z DB bez filtrowania. Backtest trades mają prefix `bt-trd-*`, live trades nie. JSON report z backtesta zawiera sekcję `analysis` z 5 trades (3 backtest + 1 live + 1 z poprzedniego runu) vs `performance` z 3 trades.

**Rekomendacja:** Dodać parametr `trade_id_prefix` do `analyze_closed_trades()` lub filtrować po `bt-trd-*` w backtest mode. Alternatywnie, `run_backtest.py` powinien analizować tylko trades z bieżącego runu (lista `closed_records` z BacktestRunner), a nie z DB.

---

### OBSERVATION 3 (LOW): SHORT w downtrend z MFE=0

**Kontekst:** Trades 2 i 3 z Run B to SHORT w downtrend z MFE=0 (cena nigdy nie poszła w kierunku trade'a). `_infer_direction` daje SHORT na podstawie CVD/TFI, ale w downtrend shortowanie dołka to łapanie noży.

**Rekomendacja:** Rozważyć dodanie regime-aware direction filter w `SignalEngine.generate()`:
- W downtrend: preferuj LONG (kontrarian mean-reversion) lub block SHORT
- W uptrend: preferuj SHORT (kontrarian) lub block LONG
- To jest dyskusyjne i wymaga parametryzacji, nie hardcode

To NIE jest bug — to strategiczna decyzja do analizy w research. Nie implementuj bez dyskusji.

---

### OBSERVATION 4 (LOW): Trade 1 Run B miał MFE +$262 ale hit SL

**Kontekst:** LONG trade z 03-01 07:15 poszedł w dobrą stronę o $262, ale potem zawrócił i uderzył stop-loss. Sugeruje że:
- TP jest za daleko (nie zrealizował zysku)
- LUB SL jest za ciasny (wyrzucony na normalnym pullbacku)
- LUB brak trailing stop / partial TP logic

**Rekomendacja:** To jest parametr do tuning'u w research, nie bug do naprawy. Kluczowe parametry: `tp1_atr_mult`, `invalidation_offset_atr`.

---

## Scope implementacji (dla Codex)

### MUST FIX (ten commit):

1. **BUG 1:** Dodaj daily reset do `consecutive_losses` w:
   - `backtest/backtest_runner.py` → `_consecutive_losses()` i `_build_runtime_state()`
   - `core/governance.py` → `GovernanceConfig` (opcjonalnie nowy parametr `consecutive_losses_reset: str = "daily"`)
   - `orchestrator.py` → `build_default_bundle` governance state provider (jeśli dotyczy)
   - Upewnij się że live i backtest używają tej samej logiki

2. **BUG 2:** Napraw `analyze_closed_trades` żeby w backtest mode analizowała tylko trades z bieżącego runu
   - Opcja: dodaj `trade_id_prefix` filter
   - Opcja: przekaż listę trade_ids z BacktestRunner zamiast czytać z DB

### DO NOT TOUCH:
- Signal weights, confluence thresholds, TP/SL multipliers — to idzie do research
- Regime-aware direction filtering — wymaga dyskusji
- Governance parametry (max_trades_per_day, cooldowns) — to parameter tuning, nie bugfix

### Acceptance criteria:
- Backtest 03-01→03-27 generuje >3 trades (governance nie blokuje permanentnie)
- `analyze_closed_trades` w backtest mode zwraca TYLKO backtest trades
- `python -m compileall . -q` passes
- Istniejące smoke testy przechodzą
- Commit message: WHAT/WHY/STATUS format per AGENTS.md

### Pliki do modyfikacji:
- `backtest/backtest_runner.py` — `_consecutive_losses()`, `_build_runtime_state()`
- `core/governance.py` — `GovernanceConfig` (opcjonalnie nowy parametr)
- `research/analyze_trades.py` — `analyze_closed_trades()` trade filtering
- `scripts/run_backtest.py` — przekazanie trade_ids do analizy (jeśli potrzebne)
- `orchestrator.py` — spójność z backtest logiką (jeśli dotyczy)

### Dane do weryfikacji:
- DB: `storage/btc_bot.db` — pełne aggtrade 03-01→03-27
- Backtest CLI: `python scripts/run_backtest.py --start-date 2026-03-01 --end-date 2026-03-27 --output-json logs/backtest_verification.json`
- Oczekiwanie: więcej niż 3 trades, governance nie blokuje permanentnie

---

## Source of truth

- `docs/BLUEPRINT_V1.md` — architektura
- `AGENTS.md` — dyscyplina inżynierska
- `docs/MILESTONE_TRACKER.md` — status faz
- `settings.py` — konfiguracja parametrów
- `core/governance.py` — governance logic
- `backtest/backtest_runner.py` — backtest orchestration
