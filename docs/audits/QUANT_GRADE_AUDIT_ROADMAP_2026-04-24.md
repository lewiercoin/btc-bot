# QUANT GRADE AUDIT ROADMAP
## BTC Futures Trading Bot — `lewiercoin/btc-bot`

> 📍 **Lokalizacja w repo:** `docs/audits/QUANT_GRADE_AUDIT_ROADMAP_2026-04-24.md`  
> 🌿 **Branch:** `market-truth-v3`  
> 🔗 **GitHub:** `https://github.com/lewiercoin/btc-bot/blob/market-truth-v3/docs/audits/QUANT_GRADE_AUDIT_ROADMAP_2026-04-24.md`

**Date:** 2026-04-24  
**Branch:** `market-truth-v3`  
**Mode:** PAPER → Production Validation  
**Status systemu:** `APPROVED FOR PRODUCTION VALIDATION` | Collecting 200+ Market Truth cycles  
**Modeling-V1:** `BLOCKED` — czeka na Gate A

---

## ⚠️ ZŁOTA ZASADA

> **Podczas gdy bot zbiera 200 cykli Market Truth, wykonujemy wyłącznie audyty read-only, dokumentację i planowanie. Żadna zmiana runtime, parametrów ani logiki nie jest dozwolona.**

---

## CZĘŚĆ 1 — EXECUTIVE SUMMARY

System jest w krytycznym oknie walidacji. `market-truth-v3` przeszedł first snapshot verification (PASS) i aktualnie zbiera dane produkcyjne do finalnej walidacji source-of-truth. Do odblokowania `MODELING-V1` wymagane jest zebranie 200+ cykli bez ingerencji w runtime.

**Kluczowy wniosek:** Ten okres jest idealny do przeprowadzenia audytów read-only (Phase 0), które zwiększają zaufanie do systemu bez ryzyka zanieczyszczenia eksperymentu. Roadmapa poniżej definiuje **19 torów audytu**, ich kolejność, kryteria i artefakty wyjściowe.

**Priorytety Phase 0 — sekwencja Tier:**

**Tier 1 — uruchom natychmiast, niezależnie od siebie:**
1. Security / Secrets / Exchange Safety
2. Production Ops / SRE
3. Observability / Dashboard
4. **Recovery / Safe Mode / State Reconciliation** — nowy, krytyczny

**Tier 2 — równolegle z Tier 1 lub tuż po:**
5. Configuration / Reproducibility
6. Execution / Paper Fill Integrity

**Tier 3 — po zebraniu evidence z Tier 2:**
7. Trade Lifecycle / PnL Accounting
8. Backtest / Research Lab

> ⚠️ **Uwaga:** Dodatkowe refinementy z zewnętrznych konsultacji są odroczone do **Roadmap V2** po Gate A — chyba że identyfikują bloker bezpieczeństwa lub krytyczny bloker zaufania do systemu.

---

## CZĘŚĆ 2 — EXECUTIVE MAP: 19 TORÓW AUDYTU

### AUDIT-01: Market Truth / Data Source Audit

| Pole | Wartość |
|------|---------|
| **Główne pytanie** | Czy dane rynkowe trafiające do pipeline'u są kompletne, aktualne, deterministyczne i wolne od lookahead? |
| **Dlaczego ważne** | Cały system buduje decyzje na danych. Błąd source-of-truth = zanieczyszczony model i błędne sygnały. |
| **Kluczowe ryzyka** | Stale data, clock drift, gaps w historii, różnice exchange vs lokalny cache, timestamp poisoning |
| **Pliki / katalogi** | `data/`, `market_data/`, `snapshot*.py`, `market_truth*.py`, `db/migrations/`, `logs/snapshots/` |
| **Dane / artefakty** | Snapshot logs, timestamp diff reports, gap analysis, DB row count vs expected, staleness metrics |
| **Równolegle teraz?** | Read-only TAK — nie wolno zmieniać logiki kolekcji |
| **Wymaga 200 cykli?** | TAK (finalny raport po 200+), read-only analiza możliwa teraz |
| **Output** | `AUDIT_MARKET_TRUTH_DATA_SOURCE_2026-04-24.md` + staleness/gap CSV |

---

### AUDIT-02: FeatureEngine Audit

| Pole | Wartość |
|------|---------|
| **Główne pytanie** | Czy wszystkie features są obliczane poprawnie, bez lookahead, z pełną determinizmem i stabilnością numeryczną? |
| **Dlaczego ważne** | Feature leakage = invalidacja całego modelowania. Feature drift = degradacja sygnału. |
| **Kluczowe ryzyka** | Lookahead leakage, NaN propagation, rolling window edge cases, feature ordering nieciągłości |
| **Pliki / katalogi** | `feature_engine.py`, `features/`, `tests/test_features*.py`, `notebooks/feature_analysis/` |
| **Dane / artefakty** | Feature distribution stats, unit testy coverage, lookahead detection script output |
| **Równolegle teraz?** | Read-only TAK |
| **Wymaga 200 cykli?** | NIE (code review + static analysis) |
| **Output** | `AUDIT_FEATURE_ENGINE_2026-04-24.md` + feature_integrity_report.csv |

---

### AUDIT-03: Signal Modeling / Stage-1 Audit

| Pole | Wartość |
|------|---------|
| **Główne pytanie** | Czy pipeline modelowania jest gotowy do bezpiecznego uruchomienia po akceptacji Market Truth? |
| **Dlaczego ważne** | `MODELING-V1` jest zablokowany — musimy wiedzieć, co dokładnie blokuje i co jest gotowe |
| **Kluczowe ryzyka** | Dataset leakage, label bias, train/test contamination, premature signal confidence |
| **Pliki / katalogi** | `signal_engine.py`, `modeling/`, `models/`, `datasets/`, `train*.py` |
| **Dane / artefakty** | Dataset schema, label distribution, train/val/test split config |
| **Równolegle teraz?** | Tylko code review — NIE wolno uruchamiać treningu |
| **Wymaga 200 cykli?** | TAK (dataset export dopiero po Gate A) |
| **Output** | `AUDIT_SIGNAL_MODELING_STAGE1_2026-04-24.md` |

---

### AUDIT-04: Regime Engine / Market State Audit

| Pole | Wartość |
|------|---------|
| **Główne pytanie** | Czy RegimeEngine poprawnie klasyfikuje stany rynkowe i czy klasyfikacja jest stabilna i nie nadmiernie przełącza się? |
| **Dlaczego ważne** | Błędny reżim = SignalEngine operuje w złym kontekście — fałszywe sygnały |
| **Kluczowe ryzyka** | Regime instability (flickering), boundary artefakty, brak hysterezis, overfit do jednego reżimu |
| **Pliki / katalogi** | `regime_engine.py`, `regime/`, `logs/regime/`, `tests/test_regime*.py` |
| **Dane / artefakty** | Regime transition logs, distribution of regimes over 200 cykli, regime duration stats |
| **Równolegle teraz?** | Read-only TAK |
| **Wymaga 200 cykli?** | Częściowo (pełna analiza po 200+) |
| **Output** | `AUDIT_REGIME_ENGINE_2026-04-24.md` + regime_distribution.csv |

---

### AUDIT-05: Governance Audit

| Pole | Wartość |
|------|---------|
| **Główne pytanie** | Czy GovernanceLayer poprawnie filtruje sygnały, egzekwuje cooldowny i nie wprowadza race conditions ani stanu ubocznego? |
| **Dlaczego ważne** | Governance jest ostatnią linią obrony przed złym sygnałem. Buggy governance = pominięte ryzyko. |
| **Kluczowe ryzyka** | State persistence bugs, cooldown bypassy, race conditions w multi-thread, brak audit trail |
| **Pliki / katalogi** | `governance*.py`, `orchestrator.py`, `logs/governance/`, `tests/test_governance*.py` |
| **Dane / artefakty** | Governance decision logs, cooldown timestamps, rejected signal stats |
| **Równolegle teraz?** | Read-only TAK |
| **Wymaga 200 cykli?** | NIE (code review możliwy teraz) |
| **Output** | `AUDIT_GOVERNANCE_2026-04-24.md` |

---

### AUDIT-06: Risk Engine Audit

| Pole | Wartość |
|------|---------|
| **Główne pytanie** | Czy RiskEngine poprawnie oblicza rozmiary pozycji, drawdown limits i czy limity są faktycznie respektowane w runtime? |
| **Dlaczego ważne** | Risk engine = granica między stratą kontrolowaną a katastrofą. Błąd = nadekspozycja. |
| **Kluczowe ryzyka** | Rozmiar pozycji off-by-one, margin calculation error, drawdown counter reset bug, soft vs hard limit confuzja |
| **Pliki / katalogi** | `risk_engine.py`, `risk/`, `tests/test_risk*.py`, `logs/risk/` |
| **Dane / artefakty** | Position size audit (expected vs actual), drawdown tracking logs, limit breach reports |
| **Równolegle teraz?** | Read-only TAK |
| **Wymaga 200 cykli?** | NIE (code + log analysis) |
| **Output** | `AUDIT_RISK_ENGINE_2026-04-24.md` + position_size_audit.csv |

---

### AUDIT-07: Execution / Paper-Live Parity Audit

| Pole | Wartość |
|------|---------|
| **Główne pytanie** | Czy paper fills odzwierciedlają realistyczne warunki rynkowe? Czy symulacja execution nie jest nadmiernie optymistyczna? |
| **Dlaczego ważne** | Paper-to-live gap = główne ryzyko przy przejściu na live trading |
| **Kluczowe ryzyka** | Instant fill assumption, zero slippage, brak partial fills, brak latency modelowania |
| **Pliki / katalogi** | `execution*.py`, `paper_broker*.py`, `logs/execution/`, `tests/test_execution*.py` |
| **Dane / artefakty** | Fill timestamps vs signal timestamps, theoretical vs actual fill price, slippage distribution |
| **Równolegle teraz?** | Read-only TAK (analiza logów) |
| **Wymaga 200 cykli?** | Częściowo (więcej danych = lepsza statystyka) |
| **Output** | `AUDIT_EXECUTION_PAPER_FILL_INTEGRITY_2026-04-24.md` |

---

### AUDIT-08: Trade Lifecycle / PnL Accounting Audit

| Pole | Wartość |
|------|---------|
| **Główne pytanie** | Czy każda transakcja od otwarcia do zamknięcia jest kompletnie i poprawnie zaksięgowana w PnL? |
| **Dlaczego ważne** | Błąd w accounting = fałszywy performance report — złe decyzje o strategii |
| **Kluczowe ryzyka** | Unclosed positions, funding fee pominięcie, commission accounting error, PnL double-counting |
| **Pliki / katalogi** | `trade_lifecycle*.py`, `pnl*.py`, `db/trades/`, `reports/`, `logs/trades/` |
| **Dane / artefakty** | SQL: open vs closed trades reconciliation, PnL waterfall, funding fee ledger |
| **Równolegle teraz?** | Read-only TAK (SQL queries na kopii / read replica) |
| **Wymaga 200 cykli?** | NIE — im wcześniej tym lepiej |
| **Output** | `AUDIT_TRADE_LIFECYCLE_PNL_ACCOUNTING_2026-04-24.md` + pnl_reconciliation.csv |

---

### AUDIT-09: Backtest / Replay / Research Lab Audit

| Pole | Wartość |
|------|---------|
| **Główne pytanie** | Czy backtest engine jest wolny od lookahead, parity z produkcją i metodologicznie sound? |
| **Dlaczego ważne** | Overfitted backtest = fałszywa pewność siebie przed live. |
| **Kluczowe ryzyka** | Look-ahead leakage, survivorship bias, cost/slippage model brakujący, walk-forward brak |
| **Pliki / katalogi** | `backtest_runner.py`, `research/`, `notebooks/`, `backtest/`, `replay*.py` |
| **Dane / artefakty** | Backtest methodology doc, cost model config, walk-forward setup, replay vs live comparison |
| **Równolegle teraz?** | Read-only TAK |
| **Wymaga 200 cykli?** | NIE (code review + methodology review) |
| **Output** | `AUDIT_BACKTEST_RESEARCH_LAB_2026-04-24.md` |

---

### AUDIT-10: Experiment Management Audit

| Pole | Wartość |
|------|---------|
| **Główne pytanie** | Czy eksperymenty są izolowane, reproducible i czy nie ma ryzyka zanieczyszczenia produkcji przez research branch? |
| **Dlaczego ważne** | Experiment bleed = nieświadoma zmiana zachowania bota |
| **Kluczowe ryzyka** | Shared DB między prod i research, brak experiment IDs, brak seed fixowania, brak isolation |
| **Pliki / katalogi** | `config/`, `experiments/`, `.env*`, `docker-compose*.yml`, `Makefile` |
| **Dane / artefakty** | Experiment isolation audit, DB schema per env, seed config audit |
| **Równolegle teraz?** | Read-only TAK |
| **Wymaga 200 cykli?** | NIE |
| **Output** | `AUDIT_EXPERIMENT_MANAGEMENT_2026-04-24.md` |

---

### AUDIT-11: Observability / Dashboard Audit

| Pole | Wartość |
|------|---------|
| **Główne pytanie** | Czy monitoring i dashboardy dają pełny, poprawny obraz stanu systemu w real-time? |
| **Dlaczego ważne** | Blind spot w monitoringu = wykrywamy problem zbyt późno |
| **Kluczowe ryzyka** | Metryki lagging, missing alerts, dashboard showing stale data, no anomaly detection |
| **Pliki / katalogi** | `monitoring/`, `dashboards/`, `alerts/`, `metrics*.py`, `grafana/`, `prometheus/` |
| **Dane / artefakty** | Alert coverage matrix, dashboard screenshot + gap analysis, metric staleness report |
| **Równolegle teraz?** | Read-only TAK |
| **Wymaga 200 cykli?** | NIE |
| **Output** | `AUDIT_OBSERVABILITY_DASHBOARD_2026-04-24.md` |

---

### AUDIT-12: Production Ops / SRE Audit

| Pole | Wartość |
|------|---------|
| **Główne pytanie** | Czy system jest operacyjnie stabilny, auto-restartuje się poprawnie i ma kompletny runbook? |
| **Dlaczego ważne** | Brak ops discipline = nieplanowany downtime podczas krytycznej sesji rynkowej |
| **Kluczowe ryzyka** | Restart bez state recovery, brak healthcheck, brak alertu na crash, brak runbook |
| **Pliki / katalogi** | `ops/`, `scripts/`, `systemd/`, `docker/`, `recovery.py`, `README.md`, `docs/ops/` |
| **Dane / artefakty** | Uptime logs, restart history, process manager config, runbook completeness checklist |
| **Równolegle teraz?** | Read-only TAK |
| **Wymaga 200 cykli?** | NIE |
| **Output** | `AUDIT_PRODUCTION_OPS_SRE_2026-04-24.md` |

---

### AUDIT-13: Security / Secrets / Exchange Safety Audit

| Pole | Wartość |
|------|---------|
| **Główne pytanie** | Czy klucze API, sekrety i uprawnienia są zarządzane bezpiecznie i z minimalnym zakresem? |
| **Dlaczego ważne** | Leak API key = utrata środków na giełdzie. Brak kill-switch = brak kontroli nad botem. |
| **Kluczowe ryzyka** | Secrets w repo, nierotowane klucze, brak IP whitelist, brak withdraw disabled, brak kill-switch |
| **Pliki / katalogi** | `.env*`, `config/`, `.gitignore`, `secrets/`, `exchange_client*.py` |
| **Dane / artefakty** | Secret scanning report (git history), API key permission audit, kill-switch test plan |
| **Równolegle teraz?** | Read-only TAK (git history scan offline) |
| **Wymaga 200 cykli?** | NIE — krytyczne |
| **Output** | `AUDIT_SECURITY_SECRETS_2026-04-24.md` |

---

### AUDIT-14: Configuration / Reproducibility Audit

| Pole | Wartość |
|------|---------|
| **Główne pytanie** | Czy konfiguracja jest wersjonowana, deterministyczna i czy można odtworzyć dokładny stan bota z danego dnia? |
| **Dlaczego ważne** | Brak reproducibility = niemożność debugowania incydentów post-factum |
| **Kluczowe ryzyka** | Config drift bez wersjonowania, env-specific overrides niezadokumentowane, brak config snapshot |
| **Pliki / katalogi** | `config/`, `settings*.py`, `pyproject.toml`, `requirements*.txt`, `.python-version` |
| **Dane / artefakty** | Config snapshot per deploy, dependency lock audit, config diff between envs |
| **Równolegle teraz?** | Read-only TAK |
| **Wymaga 200 cykli?** | NIE |
| **Output** | `AUDIT_CONFIGURATION_REPRODUCIBILITY_2026-04-24.md` |

---

### AUDIT-15: Testing / CI / Quality Gates Audit

| Pole | Wartość |
|------|---------|
| **Główne pytanie** | Czy testy pokrywają krytyczne ścieżki, CI blokuje regresje i czy są quality gates przed deployem? |
| **Dlaczego ważne** | Brak quality gates = regresja dociera na produkcję bez wykrycia |
| **Kluczowe ryzyka** | Niska coverage na risk/execution, brak integration testów, CI tylko lint, brak contract testów |
| **Pliki / katalogi** | `tests/`, `.github/workflows/`, `Makefile`, `pytest.ini`, `coverage*.xml` |
| **Dane / artefakty** | Coverage report, CI pipeline audit, test classification matrix (unit/integration/e2e) |
| **Równolegle teraz?** | Read-only TAK |
| **Wymaga 200 cykli?** | NIE |
| **Output** | `AUDIT_TESTING_CI_QUALITY_GATES_2026-04-24.md` |

---

### AUDIT-16: Live Readiness Audit

| Pole | Wartość |
|------|---------|
| **Główne pytanie** | Czy system jest gotowy do przejścia z PAPER na LIVE trading z akceptowalnym ryzykiem? |
| **Dlaczego ważne** | Premature live = ryzyko finansowe. Za późno live = stracone okazje. |
| **Kluczowe ryzyka** | Paper-live behavior divergence, brak kill-switch, brak circuit breaker, exchange failure handling |
| **Pliki / katalogi** | `execution*.py`, `live_broker*.py`, `risk_engine.py`, `docs/live_readiness/` |
| **Dane / artefakty** | Live readiness checklist, paper-live simulation diff, exchange failure test cases |
| **Równolegle teraz?** | Tylko planowanie |
| **Wymaga 200 cykli?** | TAK (Gate D) |
| **Output** | `AUDIT_LIVE_READINESS_2026-04-24.md` |

---

### AUDIT-17: Performance / Latency / Resource Audit

| Pole | Wartość |
|------|---------|
| **Główne pytanie** | Czy bot mieści się w wymaganiach latencji i nie powoduje resource leaków pod obciążeniem? |
| **Dlaczego ważne** | Memory leak = crash po N godzinach. High latency = stale signal execution. |
| **Kluczowe ryzyka** | Memory growth w pętli głównej, CPU spikes przy feature calc, DB connection pool exhaustion |
| **Pliki / katalogi** | `orchestrator.py`, `feature_engine.py`, `monitoring/metrics/`, `logs/perf/` |
| **Dane / artefakty** | Memory/CPU profile over 200 cykli, signal-to-execution latency histogram, DB query timing |
| **Równolegle teraz?** | Read-only TAK (profiling logs analiza) |
| **Wymaga 200 cykli?** | Częściowo |
| **Output** | `AUDIT_PERFORMANCE_LATENCY_2026-04-24.md` |

---

### AUDIT-18: Documentation / Agent Workflow Audit

| Pole | Wartość |
|------|---------|
| **Główne pytanie** | Czy dokumentacja i workflow dla AI agentów (Claude/GPT) jest wystarczająca do bezpiecznej kontynuacji pracy? |
| **Dlaczego ważne** | Brak kontekstu = AI agent może wprowadzić zmianę bez rozumienia implikacji |
| **Kluczowe ryzyka** | Brak CLAUDE.md, brak claude-progress.txt, blueprint nieaktualny, brak decision log |
| **Pliki / katalogi** | `docs/`, `CLAUDE.md`, `claude-progress.txt`, `gpt_bot_instytuzional_blueprint_v1.md`, `CHANGELOG.md` |
| **Dane / artefakty** | Doc completeness checklist, agent workflow review, decision log audit |
| **Równolegle teraz?** | Read-only + tworzenie dokumentów TAK |
| **Wymaga 200 cykli?** | NIE |
| **Output** | `AUDIT_DOCUMENTATION_AGENT_WORKFLOW_2026-04-24.md` |

---

### AUDIT-19: Recovery / Safe Mode / State Reconciliation Audit

| Pole | Wartość |
|------|---------|
| **Główne pytanie** | Czy bot poprawnie odtwarza swój stan po restarcie, safe_mode nie jest sticky bez powodu i nie istnieje ryzyko phantom position po awarii? |
| **Dlaczego ważne** | Historia bota obejmuje incydenty: sticky safe_mode, niepewny stan po restarcie, ryzyko phantom position. To bezpośrednio wpływa na zaufanie do systemu — niezależnie od Market Truth walidacji. |
| **Kluczowe ryzyka** | Stale safe_mode po restarcie, phantom position (bot myśli że ma pozycję gdy jej nie ma lub odwrotnie), DB state vs runtime state desync, brak auto-recovery rules, ręczna ścieżka recovery niezdefiniowana |
| **Pliki / katalogi** | `orchestrator.py`, `storage/state_store.py`, `storage/repositories.py`, `core/risk_engine.py`, `execution/paper_execution_engine.py`, `storage/schema.sql`, service logs, startup logs |
| **Dane / artefakty** | Startup log analysis, safe_mode transition history, bot_state DB snapshot vs runtime state, open position reconciliation report |
| **Równolegle teraz?** | Read-only TAK — Tier 1, nie wymaga żadnych zmian runtime |
| **Wymaga 200 cykli?** | NIE — krytyczne niezależnie od fazy |
| **Output** | `docs/audits/AUDIT_RECOVERY_SAFE_MODE_STATE_RECONCILIATION_2026-04-24.md` |

---

## CZĘŚĆ 3 — PRIORYTETY FAZOWE

### 🟢 Phase 0 — TERAZ (podczas 200-cycle collection, read-only only)

> Podzielone na Tiery — nie "wszystko równolegle". Tier 1 startuje natychmiast i niezależnie.

**Tier 1 — start natychmiast, bez dependencji:**

| Priorytet | Audyt | Status |
|-----------|-------|--------|
| P0.1 | AUDIT-13: Security / Secrets / Exchange Safety | **READY_NOW** |
| P0.2 | AUDIT-12: Production Ops / SRE | **READY_NOW** |
| P0.3 | AUDIT-11: Observability / Dashboard | **READY_NOW** |
| P0.4 | AUDIT-19: Recovery / Safe Mode / State Reconciliation | **READY_NOW** |

**Tier 2 — równolegle z Tier 1 lub po jego starcie:**

| Priorytet | Audyt | Status |
|-----------|-------|--------|
| P0.5 | AUDIT-14: Configuration / Reproducibility | **READY_NOW** |
| P0.6 | AUDIT-07: Execution / Paper Fill Integrity | **READY_NOW** |

**Tier 3 — po zebraniu evidence z Tier 2:**

| Priorytet | Audyt | Status |
|-----------|-------|--------|
| P0.7 | AUDIT-08: Trade Lifecycle / PnL Accounting | **READY_NOW** |
| P0.8 | AUDIT-09: Backtest / Research Lab | **READY_NOW** |

**Pozostałe (Phase 0, lower priority):**

| Priorytet | Audyt | Status |
|-----------|-------|--------|
| P0.9 | AUDIT-06: Risk Engine (code review tylko) | **READY_NOW** |
| P0.10 | AUDIT-15: Testing / CI / Quality Gates | **READY_NOW** |
| P0.11 | AUDIT-18: Documentation / Agent Workflow | **READY_NOW** |

---

### 🟡 Phase 1 — Po 200+ Market Truth Cycles (Gate A)

| Priorytet | Audyt |
|-----------|-------|
| P1.1 | AUDIT-01: Market Truth final validation |
| P1.2 | AUDIT-02: FeatureEngine drift validation |
| P1.3 | AUDIT-04: Regime Engine distribution analysis |
| P1.4 | Merge decision dla `market-truth-v3` |

---

### 🟵 Phase 2 — Modeling Unlock (Gate B)

| Priorytet | Audyt |
|-----------|-------|
| P2.1 | AUDIT-03: Signal Modeling / Stage-1 |
| P2.2 | `uptrend_continuation_weak` signal deep-dive |
| P2.3 | Rejected vs accepted signal dataset |
| P2.4 | Near-miss candidate analysis |
| P2.5 | Regime-specific signal behavior analysis |

---

### 🟣 Phase 3 — Research / Optimization (Gate C)

| Priorytet | Audyt |
|-----------|-------|
| P3.1 | AUDIT-09: Backtest parity (full) |
| P3.2 | Walk-forward methodology validation |
| P3.3 | Optuna hyperparameter audit |
| P3.4 | AUDIT-10: Experiment Management (full) |
| P3.5 | Autoresearch readiness review |

---

### 🔴 Phase 4 — Live Readiness (Gate D)

| Priorytet | Audyt |
|-----------|-------|
| P4.1 | AUDIT-16: Live Readiness (pełny checklist) |
| P4.2 | Risk hardening final review |
| P4.3 | Exchange failure handling |
| P4.4 | Kill-switch end-to-end test |
| P4.5 | Security / API key policy final |
| P4.6 | Production incident playbook |

---

## CZĘŚĆ 4 — SPEC PIERWSZYCH 5 AUDYTÓW (READY_NOW)

---

## AUDIT-07 — EXECUTION / PAPER FILL INTEGRITY

**Status:** READY_NOW

**Primary question:**  
Czy paper broker symuluje realistyczne fills — czy zakłada instant execution bez slippage i tym samym zawyża wyniki?

**Scope:**  
Analiza logów execution z aktualnych cykli, porównanie timestamp sygnału do timestamp fill, analiza rozpiętości cen w momencie fill, identyfikacja czy fill ceny są inside bid/ask czy na midprice.

**Out of scope:**  
Nie wolno zmieniać logiki paper brokera — to jest read-only analiza.

**Evidence required:**  
- Logi execution: signal timestamp, fill timestamp, fill price, market price at fill
- SQL: `SELECT signal_ts, fill_ts, fill_price, side, qty FROM executions ORDER BY signal_ts DESC`
- Spread data z tego samego timestamp co fill

**Files to inspect:**  
```
execution*.py
paper_broker*.py
logs/execution/
db/tables/executions (schema + sample rows)
tests/test_execution*.py
```

**Read-only now?** YES

**Acceptance criteria:**  
- **DONE:** Fill timestamps within acceptable latency, fill prices realistic vs spread, no instant fill at better-than-market prices
- **PARTIAL:** Niektóre fills podejrzane, ale pattern niezrozumiały — wymaga dalszej analizy
- **FAIL:** Fills systematically at mid-price ignoring spread / zero latency — paper PnL zawyżony

**Expected output:**  
`docs/audits/AUDIT_EXECUTION_PAPER_FILL_INTEGRITY_2026-04-24.md`  
+ `artifacts/execution_fill_audit.csv`

---

## AUDIT-08 — TRADE LIFECYCLE / PnL ACCOUNTING

**Status:** READY_NOW

**Primary question:**  
Czy każda transakcja jest kompletnie zaksięgowana — otwarcie, zamknięcie, prowizja, funding fee — i czy PnL jest poprawnie obliczany bez double-counting?

**Scope:**  
Reconciliation wszystkich trades: open/close integrity, PnL waterfall, commission accounting, funding fee inclusion, unclosed position detection.

**Out of scope:**  
Nie wolno edytować DB ani korygować rekordów. Tylko read i raport.

**Evidence required:**  
```sql
-- Unclosed positions check
SELECT * FROM trades WHERE close_ts IS NULL AND open_ts < NOW() - INTERVAL '24 hours';

-- PnL reconciliation
SELECT trade_id, (close_price - open_price) * qty * direction AS raw_pnl, 
       commission_paid, funding_paid, realized_pnl 
FROM trades WHERE close_ts IS NOT NULL;

-- Funding fee coverage
SELECT COUNT(*) FROM trades WHERE funding_paid IS NULL AND close_ts IS NOT NULL;
```

**Files to inspect:**  
```
pnl*.py
trade_lifecycle*.py
db/trades/ (schema)
reports/daily_pnl*
logs/trades/
```

**Read-only now?** YES (read replica lub SELECT-only session)

**Acceptance criteria:**  
- **DONE:** 0 unclosed trades starszych niż 24h, PnL match ±0.01%, funding fees included
- **PARTIAL:** <5 anomalii, wytłumaczalne technicznie
- **FAIL:** Systematyczny błąd accounting, unclosed positions, funding fee missing mass

**Expected output:**  
`docs/audits/AUDIT_TRADE_LIFECYCLE_PNL_ACCOUNTING_2026-04-24.md`  
+ `artifacts/pnl_reconciliation.csv`

---

## AUDIT-12 — PRODUCTION OPS / SRE

**Status:** READY_NOW

**Primary question:**  
Czy bot działa stabilnie, auto-restartuje się poprawnie i czy istnieje kompletny runbook dla operatora?

**Scope:**  
Analiza uptime logów, konfiguracji process manager (systemd/supervisord/PM2), healthcheck endpoints, restart policy, alert coverage dla crash event.

**Out of scope:**  
Nie wolno restartować bota ani zmieniać systemd unit files.

**Evidence required:**  
- `journalctl -u btc-bot --since "30 days ago"` (read-only SSH)
- Process manager config file
- Uptime / crash history
- Alert routing config (PagerDuty/Slack webhook)
- Runbook dokument (jeśli istnieje)

**Files to inspect:**  
```
ops/
systemd/*.service lub supervisord.conf lub pm2.config.js
recovery.py
scripts/healthcheck*.sh
docs/ops/runbook*.md
monitoring/alerts/
```

**Read-only now?** YES (wymaga SSH read-only na prod)

**Acceptance criteria:**  
- **DONE:** Auto-restart działa, runbook istnieje i jest aktualny, alert na crash działa, healthcheck endpoint odpowiada
- **PARTIAL:** Auto-restart OK, ale brak runbooka lub brak alertu
- **FAIL:** Brak auto-restart, brak alertu, bot mógł być down bez wiedzy

**Expected output:**  
`docs/audits/AUDIT_PRODUCTION_OPS_SRE_2026-04-24.md`  
+ ops_gap_list.md

---

## AUDIT-09 — BACKTEST / RESEARCH LAB

**Status:** READY_NOW

**Primary question:**  
Czy backtest engine jest metodologicznie sound — brak lookahead, realistyczny model kosztów, separacja train/test — i czy wyniki można zaufać jako bazę dla Modeling-V1?

**Scope:**  
Code review backtest_runner.py, cost/slippage/funding model, walk-forward setup, data split configuration, replay vs live comparison (read-only).

**Out of scope:**  
Nie wolno uruchamiać nowych backtest runs z nowymi parametrami — tylko analiza istniejącego kodu i wyników.

**Evidence required:**  
- `backtest_runner.py` — szukaj: forward-looking funkcji w features, `.shift(-N)` patterns, czy test set jest "unseen"
- Cost model config — czy prowizja, slippage i funding fee są uwzględnione
- Walk-forward config — czy istnieje i jest poprawny
- Stare wyniki backtest — czy są archiwizowane z wersją kodu?

**Files to inspect:**  
```
backtest_runner.py
research/
notebooks/*.ipynb
backtest/config/*.yaml
replay*.py
docs/research/methodology*.md
```

**Read-only now?** YES

**Acceptance criteria:**  
- **DONE:** Brak lookahead, cost model kompletny, walk-forward zdefiniowany, wyniki archiwizowane z hash commitu
- **PARTIAL:** Drobne metodologiczne luki, ale nie dyskwalifikujące
- **FAIL:** Lookahead wykryty, brak cost model, overfitted in-sample results

**Expected output:**  
`docs/audits/AUDIT_BACKTEST_RESEARCH_LAB_2026-04-24.md`  
+ backtest_methodology_checklist.md

---

## AUDIT-13 — SECURITY / SECRETS / EXCHANGE SAFETY

**Status:** READY_NOW — KRYTYCZNY

**Primary question:**  
Czy klucze API giełdy mają minimalne uprawnienia, nie ma secretów w repo, withdrawal jest wyłączone i istnieje kill-switch?

**Scope:**  
Git history scan na sekrety, analiza uprawnień API key, konfiguracja IP whitelist, withdrawal disabled check, kill-switch existence.

**Out of scope:**  
Nie wolno rotować kluczy podczas zbierania cykli (chyba że wykryty leak — wtedy priorytet bezpieczeństwa).

**Evidence required:**  
```bash
# Git secret scan (lokalnie/offline)
git log --all --full-history -- "**/.env*" 
trufflehog git file://. --only-verified
# lub: gitleaks detect --source .

# API key permissions (read-only API call)
# Sprawdzić: trading=YES, withdrawal=NO, IP restriction=YES
```

**Files to inspect:**  
```
.env (lokalna kopia, nie commit)
.gitignore (czy .env jest ignorowane)
.git/logs/ (git history na wycieki)
exchange_client*.py (jak są ładowane klucze)
config/api_config*.py
docs/security/
```

**Read-only now?** YES (git scan offline, API permission check read-only)

**Acceptance criteria:**  
- **DONE:** 0 secretów w git history, withdrawal disabled, IP whitelist aktywna, kill-switch istnieje
- **PARTIAL:** IP whitelist brak, ale withdrawal disabled i brak w git
- **FAIL:** Secret w git history, withdrawal enabled, brak kill-switch

**Expected output:**  
`docs/audits/AUDIT_SECURITY_SECRETS_EXCHANGE_SAFETY_2026-04-24.md`  
⚠️ Jeśli FAIL — immediate remediation plan niezależnie od 200-cycle freeze

---

## CZĘŚĆ 5 — STATUS GATES

### 🟢 Gate A — Market Truth Accepted

**Warunki wejścia:**

| Kryterium | Wymagany status |
|-----------|----------------|
| 200+ cycles collected | PASS |
| Drift report (feature stability) | PASS |
| Timing/staleness report | PASS lub DOCUMENTED |
| No critical source-of-truth gaps | CONFIRMED |
| AUDIT-01 Market Truth final | DONE lub PARTIAL (z akceptacją) |

**Decyzja:** Merge `market-truth-v3` do main — odblokowanie Gate B

---

### 🟵 Gate B — Modeling-V1 Unblocked

**Warunki wejścia:**

| Kryterium | Wymagany status |
|-----------|----------------|
| Gate A | PASSED |
| AUDIT-02 FeatureEngine | DONE |
| Modeling dataset export spec | READY |
| Rejected/candidate signal labels | AVAILABLE |
| No known feature integrity blocker | CONFIRMED |

**Decyzja:** Uruchomienie MODELING-V1 pipeline

---

### 🟣 Gate C — Research Lab Trusted

**Warunki wejścia:**

| Kryterium | Wymagany status |
|-----------|----------------|
| Gate B | PASSED |
| AUDIT-09 Backtest (full) | DONE |
| No lookahead leakage | CONFIRMED |
| Walk-forward methodology | ACCEPTED |
| Cost/slippage/funding model | DOCUMENTED |

**Decyzja:** Wyniki backtestów można użyć jako podstawy decyzji o strategii

---

### 🔴 Gate D — Live Readiness Candidate

**Warunki wejścia:**

| Kryterium | Wymagany status |
|-----------|----------------|
| Gate C | PASSED |
| AUDIT-07 Paper fill parity | DONE |
| AUDIT-08 PnL Accounting | DONE |
| AUDIT-06 Risk Engine | DONE |
| AUDIT-12 Ops / SRE | DONE |
| AUDIT-13 Security | DONE |
| AUDIT-19 Recovery / Safe Mode | DONE |
| Kill-switch | TESTED |
| Exchange failure handling | TESTED |
| Production incident playbook | EXISTS |

**Decyzja:** Zielone światło dla przejścia PAPER → LIVE (z osobną decyzją o kapitale)

---

## CZĘŚĆ 6 — PHASE 0 TIER 1 — PIERWSZE 4 AUDYTY (START NATYCHMIAST)

| # | Audyt | Dlaczego teraz | Read-only | SSH prod | Effort | Deliverable | Blokuje |
|---|-------|---------------|-----------|----------|--------|-------------|---------|
| 1 | Security / Secrets / Exchange Safety | Leak API key lub withdrawal enabled = ryzyko finansowe niezależnie od fazy. Zerowy koszt, maksymalny ROI. | YES | NIE (git scan lokalnie) | **S** | `docs/audits/AUDIT_SECURITY_SECRETS_EXCHANGE_SAFETY_2026-04-24.md` | Wszystkie fazy |
| 2 | Production Ops / SRE | Bot musi zebrać 200 cykli bez przerwy — auto-restart i alert muszą działać zanim dojdzie do incydentu. | YES | TAK (journalctl) | **S** | `docs/audits/AUDIT_PRODUCTION_OPS_SRE_2026-04-24.md` | Live Readiness |
| 3 | Observability / Dashboard | Bez monitoringu blind spot na cały czas walidacji. Audyt jest read-only i nie wymaga SSH. | YES | NIE | **S** | `docs/audits/AUDIT_OBSERVABILITY_DASHBOARD_2026-04-24.md` | Live Readiness |
| 4 | **Recovery / Safe Mode / State Reconciliation** | Historia incydentów: sticky safe_mode, phantom position, restart recovery. Dotyczy zaufania do produkcji, nie wymaga 200 cykli. | YES | TAK (logi startowe) | **M** | `docs/audits/AUDIT_RECOVERY_SAFE_MODE_STATE_RECONCILIATION_2026-04-24.md` | Live Readiness + Gate D |

---

## CZĘŚĆ 7 — REKOMENDACJE

### ✅ CO ROBIĆ TERAZ

**Tier 1 — start natychmiast:**
1. **Uruchom AUDIT-13 (Security) jako pierwsze** — jeśli jest leak secretu, remediation jest priorytetem absolutnym, niezależnie od freeze.
2. **Uruchom AUDIT-12 (Ops/SRE)** — bot musi zebrać 200 cykli bez przerwy; auto-restart i alert muszą działać.
3. **Uruchom AUDIT-11 (Observability)** — bez dashboardu jesteś ślepy przez cały czas walidacji.
4. **Uruchom AUDIT-19 (Recovery / Safe Mode)** — historia incydentów sticky safe_mode i phantom position wymaga osobnego audytu zaufania.

**Tier 2 — po starcie Tier 1:**

5. **AUDIT-14 (Configuration / Reproducibility)** — zweryfikuj deterministyczność przed Gate A.
6. **AUDIT-07 (Execution Fill Integrity)** — buduj baseline paper-vs-live expectations.

**Tier 3 — po zebraniu evidence:**

7. **AUDIT-08 (PnL Accounting)** — SELECT-only query na DB, 0 ryzyka, dużo wartości.
8. **AUDIT-09 (Backtest)** — code review + methodology doc, gotowość na Gate B.

### ❌ CZEGO NIE ROBIĆ TERAZ

- ❌ Nie zmieniaj `SignalEngine`, `RiskEngine`, `GovernanceLayer`, `ExecutionEngine`
- ❌ Nie restartuj bota bez krytycznej potrzeby
- ❌ Nie uruchamiaj nowych backtest runs z nowymi parametrami
- ❌ Nie rozpoczynaj MODELING-V1 przed Gate A
- ❌ Nie merguj żadnego branch do main przed Gate A
- ❌ Nie zmieniaj schemy DB produkcyjnej
- ❌ Nie wprowadzaj nowych dependencies do runtime

---

## APPENDIX — QUICK REFERENCE

### Legenda statusów

| Status | Znaczenie |
|--------|-----------|
| `READY_NOW` | Można zacząć natychmiast, read-only |
| `WAIT_FOR_200_CYCLES` | Blokowane przez Gate A |
| `BLOCKED` | Zależy od wcześniejszego gate |
| `TODO` | Zaplanowane, jeszcze nie priorytetyzowane |

### Legenda Effort

| Effort | Szacunkowy czas |
|--------|----------------|
| **S** | 2–4h |
| **M** | 1–2 dni |
| **L** | 3–5 dni |

---

*Dokument wygenerowany: 2026-04-24*  
*Patch v1.1 — 2026-04-24: dodano AUDIT-19, zaktualizowano Phase 0 Tier sequencing, ujednolicono nazwy artefaktów*  
*Branch: `market-truth-v3`*  
*Następna rewizja: Roadmap V2 po Gate A (200+ cykli zebranych)*
