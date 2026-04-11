# BOTTLENECK-ANALYSIS — Pipeline Funnel Report
Date: 2026-04-09
Analyst: Codex (data) + Claude Code (audit verdict)
Commit: 8f2c6f2
Data range: 2022-03-29 to 2026-03-28 (4 years, 15m bars, default baseline params)

---

## Cel

Zlokalizować gdzie w pipeline bota giną potencjalne trade'y. Zidentyfikować bramki zbyt restrykcyjne, martwe features i design mismatch w governance.

---

## Pipeline

```
MarketSnapshot → Features → Regime → SignalCandidate → Governance → RiskGate → Execution
```

---

## Part 1 — Mapa bramek (funnel)

Dane empiryczne z 4-letniego replay na defaultowych parametrach baseline.

| Bramka | Plik | Warunek odrzucenia | Przepuszczalność (stage) | Przepuszczalność (overall) | Rejecty |
|---|---|---|---|---|---|
| `sweep_detected` | signal_engine.py:49 | `if not features.sweep_detected` | 99.49% | 99.49% | — |
| `reclaim_detected` | signal_engine.py:51 | `if not features.reclaim_detected` | 7.16% of sweep bars | 7.12% overall | — |
| `direction_inference` | signal_engine.py:95 | no CVD/TFI direction | 90.8% | 6.46% overall | — |
| `sweep_side match` | signal_engine.py:106 | direction ≠ sweep_side | 63.3% | 4.09% overall | — |
| `regime_whitelist` | signal_engine.py:61 | direction not allowed in regime | 46.1% | 1.88% overall | **3,090** |
| `confluence_min` | signal_engine.py:65 | score < 3.0 | 92.4% | 1.74% overall | 202 |
| `governance: weekly_dd` | governance.py:48 | weekly_dd ≥ 6% | — | — | **438** |
| `governance: cooldown` | governance.py:60 | < 60m after last loss | ~92.6% stage-pass | — | 133 |
| `governance: duplicate_level` | governance.py:66 | within 0.1% / 24h | ~73.2% stage-pass | — | **445** |
| `governance: max_trades_per_day` | governance.py:52 | ≥ 3 trades today | ~93.9% stage-pass | — | 117 |
| `governance: daily_dd` | governance.py:46 | daily_dd ≥ 3% | — | — | 93 |
| `risk: min_rr` | risk_engine.py:57 | RR < 2.8 | ~84.1% stage-pass | — | 192 |
| `risk: max_open_positions` | risk_engine.py:55 | ≥ 2 open positions | ~99.7% stage-pass | — | 4 |

**Uwaga krytyczna:** `reclaim` jest twardą bramką (hard return przed confluence), nie elementem scoringu. Scoring w ogóle nie odpala bez reclaim=True.

---

## Part 2 — Dead feature: force_orders

### Przepływ danych

- W live runtime: `force_order_events_60s` pochodzi z in-memory websocket buffer (market_data.py:122, websocket_client.py:157-159). Feature **działa** w live.
- W backtest/research: pochodzi z tabeli `force_orders` przez replay_loader.py:272. Tabela ma **0 wierszy** w lokalnej DB.
- Brak bootstrap path: `bootstrap_history.py` buduje tylko aggtrade buckets. Nie ma odpowiednika dla force_orders.

### Konsekwencje (trwałe w backtest/research)

| Strata | Wartość |
|---|---|
| `weight_force_order_spike` permanentnie zablokowane | -0.40 z każdego sygnału |
| `POST_LIQUIDATION` regime nigdy nie odpala | -0.35 z każdego LONG |
| Łączna utrata headroom dla LONGów | **-0.75** |
| Łączna utrata headroom dla SHORTów | **-0.40** |

`confluence_min = 3.0`. Max reachable (bez force_orders, bez POST_LIQ dla LONG) = ~4.20 zamiast 4.95.

### Czy POST_LIQUIDATION może odpalić?

Nie. `regime_engine.py _is_post_liquidation()` wymaga `force_order_spike = True`. `_is_force_order_spike()` zwraca False gdy historia jest pusta (len < 6). Circular dependency: bez danych historycznych, feature nigdy się nie bootstrapuje.

---

## Part 3 — Direction inference: TFI vs CVD

### TFI (Trade Flow Imbalance)

Definicja: `TFI = cvd / total_volume` → zakres `[-1, 1]`.

| Statystyka | Wartość (4 lata, 60s buckets) |
|---|---|
| min / max | -0.995 / +0.996 |
| median | -0.007 |
| 5th / 95th pct | -0.614 / +0.603 |
| `tfi > 0.05` (LONG direction) | **44.5%** bars |
| `tfi < -0.05` (SHORT direction) | **45.9%** bars |
| poza dead zone `[-0.05, +0.05]` | **90.4%** bars |

**Wniosek: `direction_tfi_threshold = 0.05` jest permissywny, nie restrykcyjny. Direction inference NIE jest bottleneckiem.**

### CVD vs TFI jako źródło kierunku

W 4-letnim replay:
- Kierunek z TFI: **8,284** przypadków
- Kierunek z CVD divergence: **765** przypadków

CVD jest drugoplanowe. TFI dostarcza 91.6% sygnałów kierunkowych.

### CVD warm-up blindness

`cvd_divergence_window_bars = 10` (feature_engine.py:25). Po każdym `reset()` (feature_engine.py:156), pierwsze 10 barów = CVD zawsze False. W backtest_runner.py:98 i :251 reset jest wołany. Efekt: marginalna strata przy krótkich runach, nie dominujący problem przy 4 latach historii.

---

## Part 4 — Duplicate level: design mismatch

### Problem

`governance.py _is_duplicate_level()` (linie 108-118): blokuje entry jeśli poprzedni zaakceptowany sygnał był w odległości 0.1% ceny (= ~$85 przy BTC=$85k) w ciągu 24h.

**445 rejectów** — największy governance bloker po DD vetoes.

### Dlaczego to jest design mismatch dla sweep/reclaim

Sweep/reclaim strategy zakłada, że te same strefy płynności są testowane wielokrotnie zanim zostaną wyczerpane. "Powrót do tego samego poziomu" jest normalny i może być lepszym sygnałem (drugi test po potwierdzeniu). Blokowanie ponownych wejść na tej samej strefie usuwa potencjalnie najlepsze trade'y.

### Dodatkowy problem: pamięć runtime-only

```python
self._accepted_levels: deque = deque(maxlen=200)  # governance.py:39
```

Restart bota = governance traci całą historię poziomów. Zachowanie po restarcie jest inne niż przed. Dla systemu produkcyjnego: niedopuszczalne — ten sam setup który byłby zablokowany przed restartem, przechodzi po restarcie.

---

## Part 5 — min_rr = 2.8 edge case

### Nominalna geometria

```
risk_distance  = ATR * (0.75 + 0.05) = ATR * 0.80
reward_to_TP1  = ATR * 2.5
nominal_RR     = 3.125  → przechodzi 2.8
```

### Kiedy min_stop_distance_pct wiąże

`signal_engine.py:168`: `actual_stop = max(raw_stop, entry * min_stop_distance_pct)`

Gdy `min_stop_distance_pct = 0.0015` (default) wiąże:
```
RR = 2.5 * ATR / (entry * 0.0015)
```

Spada poniżej 2.8 gdy `ATR < 0.00168 * entry`. Przy BTC=$85,000: **ATR < ~$143**.

W 4-letnim replay: **192 rejecty** z `rr_below_min`. Zakres runtime RR: 0.418 – 3.125.

### Paper mode fill assumption

`fill_model.py:70` wypełnia zlecenie wokół `requested_price` z fixed slippage. Paper mode zakłada że limit po `entry_offset_atr=0.05` jest fillable. Optymistyczne założenie — w live może nie być filled.

---

## Part 6 — Confluence scoring: stan obecny

| Składnik | Waga | Dostępność w backtest |
|---|---|---|
| sweep_detected | 1.25 | 99.49% ✓ |
| reclaim_confirmed | 1.25 | 7.16% |
| cvd_divergence | 0.75 | rzadkie (765 / 4 lata) |
| tfi_impulse | 0.50 | ~44-46% bars |
| force_order_spike | 0.40 | **0% — dead** |
| regime_special (POST_LIQ) | 0.35 | **0% — dead dla LONG** |
| ema_trend_alignment | 0.25 | zależy od regime |
| funding_supportive | 0.20 | zależy od funding |
| **Max teoretyczne** | **4.95** | |
| **Trwale zablokowane** | **0.75** | |
| **Max reachable** | **~4.20** | |

`confluence_min = 3.0` blokuje tylko 202 z 2,641 whitelist-passing setups (7.6%). **Confluence nie jest bottleneckiem.**

---

## Ranking bottlenecków

| # | Bottleneck | Rejecty | Klasyfikacja |
|---|---|---|---|
| 1 | **regime_whitelist** (UPTREND=43% czasu) | 3,090 | Strukturalny — częściowo naprawiony przez SIGNAL-UNLOCK-V1, ale `allow_long_in_uptrend=False` jest nadal default |
| 2 | **duplicate_level** | 445 | Design mismatch dla sweep strategy |
| 3 | **weekly_dd governance** | 438 | Może być właściwy — zależy od equity curve |
| 4 | **force_orders dead** | N/A (confluence loss) | Brak danych historycznych — utrata 0.75 headroom dla LONG |
| 5 | **min_rr edge case** | 192 | Parametryczny, nie architektoniczny |
| 6 | **cooldown_after_loss** | 133 | Prawdopodobnie właściwy |
| 7 | **max_trades_per_day** | 117 | Prawdopodobnie właściwy |

**NIE są bottleneck:** `direction_tfi_threshold`, `confluence_min`, `max_open_positions`.

---

## Audit Verdict

### #1 — Immediate check (przed analizą Run #3)

Zweryfikuj czy `allow_long_in_uptrend` jest sampowany w baseline-v3:

```bash
cat research_lab/configs/baseline-v3.json | grep allow_long
```

Jeśli flaga nie jest w configu lub jest `false` — Run #3 mierzy wyniki ze starym głównym bottleneckiem aktywnym. Analiza wyników Run #3 musi uwzględnić tę informację.

### #2 — Rekomendowany następny milestone

**GOVERNANCE-DUPLICATE-LEVEL-REDESIGN**

Zmiana logiki: zamiast blokować każde ponowne wejście na tym samym poziomie, blokuj tylko jeśli poprzedni trade na tym poziomie zakończył się SL. Lub skróć okno z 24h do 4h. Lub uzależnij od sweep_side (ten sam kierunek blokuj, przeciwny przepuść).

Dodatkowe: persistence dla `_accepted_levels` — governance powinna przeżywać restart.

---

## Otwarte pytania

1. Czy force_orders można bootstrapować historycznie? Czy Binance udostępnia force_order events przez REST API (nie tylko WS)?
2. Jak `duplicate_level` zachowuje się w Optuna trials — czy każdy trial zaczyna z pustą deque czy z reinitializowaną governance?
3. Czy `weekly_dd_exceeded` (438 rejectów) koreluje z prawdziwymi złymi warunkami rynkowymi, czy z curve fittingiem złej strategii?
