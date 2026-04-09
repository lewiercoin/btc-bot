## CLAUDE HANDOFF -> CODEX

### Checkpoint
- Last commit: `2d8fa2f` (`SWEEP-RECLAIM-PRELAUNCH-REPORT`)
- Branch: `main`
- Working tree: clean

---

### Before you code
Read these files (mandatory):
1. `docs/BLUEPRINT_RESEARCH_LAB.md` — research lab architecture
2. `AGENTS.md` — discipline + your workflow rules
3. `docs/MILESTONE_TRACKER.md` — current status
4. `docs/OPTUNA_UTILITY_REPORT.md` — analiza którą sam napisałeś; kontekst całego milestone'u
5. `docs/SWEEP_RECLAIM_PRELAUNCH_REPORT.md` — pre-launch research; Q1-Q3 są bezpośrednio powiązane z deliverables #0 i #7

---

### Milestone: OPTUNA-UTILITY-V1

Scope: implementacja 8 usprawnień Optuna wynikających z OPTUNA_UTILITY_REPORT i SWEEP_RECLAIM_PRELAUNCH_REPORT, w kolejności priorytetów. Zakres TYLKO w obrębie Research Lab — zero zmian w live-path.

**Deliverables:**

0. **Pre-campaign signal health gate** (`research_lab/workflows/optimize_loop.py`)
   - Przed wywołaniem `run_optuna_study()`: uruchom krótki replay na danych wejściowych i sprawdź `sweep_detected rate`
   - Jeśli `sweep_detected > 0.5` (50% barów) — rzuć `SignalHealthError` z komunikatem diagnostycznym i zatrzymaj kampanię
   - Próg konfigurowalny przez CLI flag `--max-sweep-rate` (default: 0.5)
   - Cel: uniemożliwić kampanię Optuna na zdegradowanym sygnale bez manualnej interwencji
   - NIE wymaga pełnego backtestu — wystarczy replay feature_engine na próbce danych (np. ostatnie 500 barów)

1. **Fix `_to_finite_float()`** (`research_lab/objective.py:24-27`)
   - `inf` profit_factor musi mapować na dużą skończoną wartość (np. `1e6`), nie na `0.0`
   - `0.0` dla inf jest błędem logicznym — maximizer Optuna traktuje idealną strategię jako najgorszą
   - Sprawdź czy ta sama funkcja jest używana dla innych metryk i czy tam `0.0` jest poprawny

2. **Persistent Optuna storage + resume** (`research_lab/integrations/optuna_driver.py:124-128`)
   - Użyj `optuna.storages.JournalStorage` (file-based, bez SQLite concurrency issues)
   - Dodaj `load_if_exists=True` semantics
   - Ścieżka storage konfigurowalana przez CLI (nowy flag `--optuna-storage-path`, default: obok `--store-path`)
   - Storage Optuna jest ODDZIELNY od `research_lab.db` — nie mieszaj warstw

3. **Warm-start z baseline + prior winners** (`research_lab/integrations/optuna_driver.py:125-176`)
   - Przed `study.optimize()`: enqueue baseline config (z `research_lab/baseline_gate.py`)
   - Opcjonalnie (jeśli `--warm-start-from-store`): enqueue top-N Pareto winners z `experiment_store` dla matching `study_name` lub per CLI flag
   - Warm-start jest OPCJONALNY — domyślnie off, nie wymuszaj go

4. **Missing constraint: `high_vol_leverage <= max_leverage`** (`research_lab/constraints.py:6-52`)
   - Dodaj walidację w `assert_valid()` lub podczas samplingu w `optuna_driver.py`
   - Zbadaj czy runtime clamp w `core/risk_engine.py:82-85` powoduje kolizję trial vectors — jeśli tak, enforce constraint przed oceną

5. **`TPESampler(multivariate=True)` — flag eksperymentalny** (`research_lab/integrations/optuna_driver.py:124`)
   - Dodaj CLI flag `--multivariate-tpe` (default: False)
   - Gdy True: `TPESampler(seed=seed, multivariate=True)`
   - Nie zmieniaj domyślnego zachowania

6. **Optuna metadata observability** (`research_lab/integrations/optuna_driver.py`)
   - `study.set_metric_names(["expectancy_r", "profit_factor", "max_drawdown_pct"])`
   - `trial.set_user_attr("protocol_hash", ...)`, `trial.set_user_attr("trial_wall_time_s", ...)`
   - Opcjonalnie: `trial.set_user_attr("rejection_reason", ...)` jeśli trial jest rejected

7. **Surface funnel_json w standardowym raporcie kampanii** (`research_lab/reporter.py`)
   - `funnel_json` jest już persystowany w `experiment_store` per trial — wystarczy go wyciągnąć
   - Dodaj sekcję "Signal Funnel Summary" do raportu: agregat per kampania (średnie rates: sweep, reclaim, regime_blocked, governance_rejected, executed)
   - Cel: operator widzi degradację sygnału bez konieczności bezpośredniego odpytania DB
   - Brak nowych kolumn w DB — dane już są, tylko surfacing

**Target files:**
- `research_lab/workflows/optimize_loop.py` (fix #0)
- `research_lab/objective.py` (fix #1)
- `research_lab/integrations/optuna_driver.py` (fix #2, #3, #4 partial, #5, #6)
- `research_lab/constraints.py` (fix #4)
- `research_lab/reporter.py` (fix #7)
- `research_lab/cli.py` (nowe CLI flags dla #0, #2, #3, #5)
- `tests/test_research_lab_smoke.py` (update smoke tests)

---

### Known Issues (from Claude Code audit)
| # | Issue | Blocking? |
|---|---|---|
| 0 | Brak pre-campaign signal health gate — Optuna może kalibrować zdegradowany sygnał bez ostrzeżenia | **YES** — fix jako pierwsze |
| 1 | `_to_finite_float()` mapuje `inf` → `0.0` zamiast dużej wartości skończonej | **YES** |
| 2 | Study in-memory, brak resume | YES dla tego milestone'u |
| 3 | `high_vol_leverage <= max_leverage` brakuje w constraints | YES |
| 4 | Brak warm-start | NO (opcjonalne) |
| 5 | Brak `multivariate=True` option | NO (eksperymentalne) |
| 6 | Brak Optuna metadata | NO (nice-to-have) |
| 7 | `funnel_json` nie jest widoczny w raporcie kampanii | NO (nice-to-have, ale ważne diagnostycznie) |

---

### Architektoniczne granice — nie przekraczaj

- **Zero zmian** w `core/`, `backtest/`, `live/`, `data_loader/`
- Persistent Optuna storage = oddzielny plik, nie `research_lab.db`
- Warm-start nigdy nie importuje candidate-ów z innego protocol_hash bez explicit flag
- `multivariate=True` jest zawsze opt-in, nigdy domyślne

---

### Twoja pierwsza odpowiedź musi zawierać:
1. Potwierdzenie zakresu (co implementujesz z listy 0-7)
2. Acceptance criteria dla każdego deliverable
3. Które known issues są w-scope vs out-of-scope (z reasoning)
4. Plan implementacji (ordered steps)
5. Następnie: zacznij kod

---

### Commit discipline
```
WHAT: OPTUNA-UTILITY-V1 — <specific deliverable>
WHY: maximize Optuna search efficiency; see docs/OPTUNA_UTILITY_REPORT.md
STATUS: IN_PROGRESS | DONE
```
Nie samodzielnie oznaczaj jako "done". Claude Code audytuje po push.
