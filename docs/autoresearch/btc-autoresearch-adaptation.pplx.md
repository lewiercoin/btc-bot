# Adaptacja karpathy/autoresearch do BTC Bot Research System

## Podsumowanie

Repozytorium [karpathy/autoresearch](https://github.com/karpathy/autoresearch) implementuje elegancki wzorzec: agent AI autonomicznie modyfikuje jeden plik (`train.py`), uruchamia eksperyment z ustaloną metryką (`val_bpb`), decyduje keep/discard, i powtarza w nieskończoność. Ten sam wzorzec mapuje się bezpośrednio na optymalizację parametrów bota tradingowego — zamiast modyfikować architekturę sieci neuronowej, agent modyfikuje przestrzeń parametrów i strategię optymalizacji, a zamiast `val_bpb` mierzy `fitness` (expectancy_r + profit_factor - max_drawdown).

Poniżej pełne mapowanie konceptów, struktura plików, i instrukcja integracji z istniejącym botem.

---

## Mapowanie konceptów 1:1

| autoresearch (Karpathy) | BTC Bot Research | Uzasadnienie |
|---|---|---|
| `train.py` — jedyny plik modyfikowany przez agenta | `research/config_space.py` — jedyny plik modyfikowany przez agenta | Agent nie dotyka pipeline'u — zmienia tylko parametry, zakresy, constrainty, strategię optymalizacji |
| `prepare.py` — stałe, data prep, evaluation (DO NOT MODIFY) | `research/prepare_research.py` — backtest runner, walk-forward, sensitivity, evaluation (DO NOT MODIFY) | Cała infrastruktura pomiarowa jest zamrożona, tak jak ewaluacja w autoresearch |
| `program.md` — instrukcje dla agenta | `program.md` — instrukcje dla agenta | Identyczna rola: "skill" definiujący zachowanie agenta |
| `val_bpb` — jedyna metryka (niżej = lepiej) | `fitness` — scalaryzowana metryka (wyżej = lepiej) | Multi-objective: expectancy_r × 0.4 + profit_factor × 0.3 - max_drawdown × 0.3 |
| 5 min time budget per experiment | ~7-17 min per experiment (200 Optuna trials × 2-5 sec) | Porównywalny czas na eksperyment |
| `results.tsv` — log eksperymentów | `research/results.tsv` — log eksperymentów | Identyczny format (rozszerzony o WF status i dodatkowe metryki) |
| git branch `autoresearch/<tag>` | git branch `research/<tag>` | Identyczny git workflow |
| keep/discard na podstawie val_bpb | keep/discard na podstawie fitness + walk-forward PASS/FAIL | Dodatkowy warunek: walk-forward musi przejść (anti-overfitting) |
| Modyfikacje: architektura, hyperparameters, optimizer, batch size | Modyfikacje: zakresy parametrów, which params to optimize, constraints, fitness weights, WF windows | Analogiczna swoboda w innym domenie |
| `uv run train.py` | `python -m research.run_experiment` | Jedno polecenie uruchamia pełny eksperyment |
| GPU (H100) | CPU (backtesty są lekkie, ~2-5 sec each) | Nie wymaga GPU — backtesty to pure Python na danych historycznych |

---

## Kluczowa różnica: Walk-Forward Validation

Autoresearch nie ma problemu overfittingu — model trenuje na danych treningowych i ewaluuje na stałym zbiorze walidacyjnym. W tradingu overfitting jest krytycznym ryzykiem. Dlatego adaptacja dodaje obowiązkową warstwę walk-forward validation:

```
autoresearch:  modify → train → eval(val_bpb) → keep/discard
BTC research:  modify → optimize(Optuna) → eval(fitness) → walk_forward() → keep/discard
                                                              ↑
                                              Musi przejść (degradacja < 30%)
                                              Inaczej: discard jako overfit
```

To jest jedyny istotny element, który autoresearch nie posiada, a który jest absolutnie krytyczny w tradingu.

---

## Struktura plików

```
your-bot-repo/
├── engines/                    # Core pipeline — DO NOT MODIFY (= prepare.py)
│   ├── feature_engine.py
│   ├── regime_engine.py
│   ├── signal_engine.py
│   ├── governance_layer.py
│   └── risk_engine.py
├── backtest/
│   ├── backtest_runner.py      # BacktestRunner.run() — DO NOT MODIFY
│   └── fill_model.py
├── storage/
│   └── trading_bot.db          # SQLite z danymi historycznymi
├── settings.py                 # Production config (frozen dataclasses) — READ ONLY
├── scripts/
│   └── run_backtest.py         # CLI backtest entry point
│
├── research/                   # ← NOWY KATALOG (autoresearch adaptation)
│   ├── __init__.py
│   ├── prepare_research.py     # ≡ prepare.py — fixed infrastructure, DO NOT MODIFY
│   ├── config_space.py         # ≡ train.py  — THE FILE THE AGENT MODIFIES
│   ├── run_experiment.py       # Entry point: python -m research.run_experiment
│   ├── governance_analysis.py  # Standalone governance deep-dive
│   ├── results.tsv             # Experiment log (untracked by git)
│   ├── experiments.db          # Optuna SQLite storage (untracked)
│   └── *.json                  # Per-experiment reports (importance, WF, etc.)
│
├── program.md                  # ≡ program.md — agent instructions
└── .gitignore                  # Add: research/results.tsv, research/experiments.db
```

---

## Co agent modyfikuje (config_space.py)

Agent ma pełną swobodę modyfikacji `research/config_space.py`, analogicznie do `train.py` w autoresearch. Konkretnie może:

### 1. Zmieniać zakresy parametrów
```python
# Przed (szerokie, eksploracyjne)
"confluence_min": {"type": "float", "low": 1.5, "high": 5.0, "default": 3.0}

# Po (zwężone po Phase 1 — sensitivity analysis)
"confluence_min": {"type": "float", "low": 2.0, "high": 3.5, "default": 3.0}
```

### 2. Zamrażać/odmrażać parametry
```python
# Zamrożony (pominięty w optymalizacji)
"wick_min_atr": {"type": "fixed", "value": 0.40, "default": 0.40}

# Odmrożony (włączony do optymalizacji)
"wick_min_atr": {"type": "float", "low": 0.20, "high": 0.80, "default": 0.40}
```

### 3. Modyfikować constrainty
```python
def check_constraints(params):
    # Nowy constraint: min_rr musi być > tp1/invalidation ratio
    effective_rr = params["tp1_atr_mult"] / params["invalidation_offset_atr"]
    if params["min_rr"] > effective_rr * 1.5:
        return False  # min_rr zbyt restrykcyjne dla tego TP/SL setup
    return True
```

### 4. Zmieniać strategię optymalizacji
```python
# Zwiększona liczba triali po zawężeniu przestrzeni
N_TRIALS = 500

# Zmienione wagi fitness
FITNESS_WEIGHTS = {
    "expectancy_r": 0.5,     # Więcej wagi na expectancy
    "profit_factor": 0.2,
    "max_drawdown": 0.3,
}
```

### 5. Modyfikować walk-forward windows
```python
# Krótsze okna dla testowania stabilności na różnych interwałach
WF_TRAIN_BARS = 300
WF_TEST_BARS = 100
WF_STEP_BARS = 100
```

---

## Experiment Loop — porównanie z autoresearch

### autoresearch (oryginał)
```
LOOP FOREVER:
  1. Read git state
  2. Hack train.py (architecture, hyperparams, optimizer)
  3. git commit
  4. uv run train.py > run.log 2>&1
  5. grep val_bpb run.log
  6. If crashed → tail, fix or skip
  7. Log to results.tsv
  8. If improved → keep. Else → git reset.
```

### BTC bot research (adaptacja)
```
LOOP FOREVER:
  1. Read results.tsv (analyze what worked/failed)
  2. Generate hypothesis (which params, what ranges, why)
  3. Modify config_space.py
  4. git commit
  5. python -m research.run_experiment > research/run.log 2>&1
  6. grep best_fitness wf_status run.log
  7. If crashed → tail, fix or skip
  8. Log to results.tsv
  9. If fitness improved AND wf_status=PASS → keep.
     If fitness improved BUT wf_status=FAIL → discard (overfit!).
     Else → git reset.
```

Identyczny flow z jednym dodatkowym warunkiem: walk-forward PASS.

---

## Integracja z twoim botem — krok po kroku

### Krok 1: Skopiuj pliki research/ do swojego repo
```bash
cp -r btc-autoresearch/research/ your-bot-repo/research/
cp btc-autoresearch/program.md your-bot-repo/program.md
```

### Krok 2: Dostosuj importy w prepare_research.py
Znajdź sekcje oznaczone `# --- ADAPT THESE IMPORTS TO YOUR PROJECT ---` i zmień importy na twoje rzeczywiste ścieżki:

```python
# Zmień te importy na twoje faktyczne
from settings import (
    FeatureEngineConfig, RegimeEngineConfig, SignalEngineConfig,
    GovernanceConfig, RiskConfig
)
from backtest.backtest_runner import BacktestRunner
from research.analyze_trades import analyze_closed_trades
```

### Krok 3: Dostosuj build_configs() w config_space.py
Funkcja `build_configs()` mapuje płaski dict parametrów na twoje frozen dataclasses. Dostosuj nazwy pól, jeśli różnią się od tych w raporcie:

```python
feature = FeatureEngineConfig(
    atr_period=params.get("atr_period", 14),
    # ... dopasuj do twoich faktycznych pól
)
```

### Krok 4: Ustaw DB_PATH
W `prepare_research.py`, zmień `DB_PATH` na ścieżkę do twojej bazy SQLite:

```python
DB_PATH = Path("storage/trading_bot.db")  # ← twoja ścieżka
```

### Krok 5: Dodaj zależności
```bash
pip install optuna
# MLflow jest opcjonalny na starcie:
# pip install mlflow
```

### Krok 6: Zweryfikuj dane i uruchom
```bash
# Weryfikacja
python -c "from research.prepare_research import verify_data; verify_data()"

# Pierwszy eksperyment (baseline)
python -m research.run_experiment --n-trials 50

# Governance analysis
python -m research.governance_analysis
```

### Krok 7: Uruchom agenta
Otwórz Claude/Codex/Windsurf w katalogu repo i wklej:
```
Przeczytaj program.md i zacznijmy nową sesję research. Najpierw setup.
```

Agent przeczyta `program.md`, zrozumie system, ustali baseline, i zacznie autonomicznie eksperymentować — dokładnie jak w autoresearch.

---

## Mapowanie do rekomendacji z oryginalnego raportu

| Rekomendacja z raportu | Jak zrealizowana w adaptacji |
|---|---|
| **Optuna jako primary optimizer** | Wbudowane w `prepare_research.py` — `run_optuna_study()` z TPE sampler i SQLite persistence |
| **Multi-objective optimization** | Scalaryzowane przez `compute_fitness()` z konfigurowalnymi wagami w `config_space.py` |
| **Walk-forward validation** | `walk_forward_validate()` w `prepare_research.py`, obowiązkowe (agent nie może pominąć) |
| **fANOVA sensitivity analysis** | `sensitivity_analysis()` w `prepare_research.py`, automatycznie po każdym Optuna study |
| **Governance filter analysis** | `governance_deep_dive()` + standalone `governance_analysis.py` |
| **Agentic loop (LangGraph)** | Zastąpione prostszym wzorcem autoresearch — agent (Claude/Codex) jest loopem. Nie potrzebujesz LangGraph, bo `program.md` pełni tę samą rolę co state machine. Agent sam decyduje co dalej. |
| **MLflow experiment tracking** | Opcjonalnie — na starcie wystarczy `results.tsv` + JSON reports + Optuna SQLite. MLflow można dodać później. |
| **Experiment storage schema** | Optuna SQLite (`experiments.db`) + per-experiment JSON reports |
| **Human approval gate** | Git: agent commituje, human reviewuje diffy na branchu `research/<tag>` |

---

## Dlaczego autoresearch pattern jest lepszy od pełnego LangGraph

Kluczowa obserwacja: w oryginalnym raporcie zaproponowałem LangGraph jako agentic orchestrator.
Adaptacja autoresearch **eliminuje tę potrzebę**, ponieważ:

1. **Agent (Claude/Codex) JUŻ JEST state machine.** `program.md` definiuje stany (setup → baseline → loop), tranzycje (keep/discard/crash), i pamięć (results.tsv, git history). Nie potrzebujesz dodatkowej warstwy orkiestracji.

2. **Zero dodatkowego kodu.** LangGraph wymaga napisania ~300 linii kodu state machine. Autoresearch pattern wymaga 0 linii — agent interpretuje instrukcje z `program.md` i sam zarządza loopem.

3. **Audytowalność przez git.** Każdy eksperyment = commit. Każdy discard = `git reset`. Każdy keep = commit na branchu. Pełna historia, zero niestandardowej infrastruktury.

4. **Human-in-the-loop = git review.** Zamiast programować `interrupt()` w LangGraph, po prostu przeglądasz diffy na branchu `research/mar27` gdy wrócisz do komputera.

LangGraph warto rozważyć dopiero gdy:
- Potrzebujesz wielu agentów współpracujących jednocześnie
- Chcesz scheduled/unattended runs bez interaktywnego agenta
- Potrzebujesz bardziej złożonej logiki niż keep/discard

Na starcie, wzorzec autoresearch jest prostszy, natychmiastowo funkcjonalny, i nie wymaga żadnej dodatkowej infrastruktury.

---

## Estimacja czasowa integracji

| Krok | Czas | Uwagi |
|------|------|-------|
| Skopiuj pliki, dostosuj importy | 1-2 godziny | Zależy od struktury twojego settings.py |
| Testuj `verify_data()` + pierwszy backtest | 30 min | Upewnij się, że wrapper backtestu działa |
| Pierwszy pełny experiment (50 trials) | 30 min | Walidacja end-to-end |
| Governance analysis | 15 min | Jedno polecenie |
| Skonfiguruj agenta + uruchom | 15 min | Claude/Codex + program.md |
| **Total** | **~3 godziny** | Od zera do autonomicznego research |

Porównanie: oryginalny raport szacował 7 dni roboczych dla pełnego systemu z LangGraph + MLflow.
Adaptacja autoresearch redukuje to do jednego popołudnia, ponieważ eliminuje LangGraph i upraszcza experiment tracking do results.tsv + git.

---

## Ścieżka ewolucji

```
Faza 1 (teraz):     autoresearch pattern — program.md + config_space.py + git
                     Prosty, natychmiastowy, wystarczający na 90% potrzeb.

Faza 2 (opcjonalnie): Dodaj MLflow tracking do run_experiment.py
                       (~50 linii kodu, lepsze dashboardy i porównania)

Faza 3 (opcjonalnie): Dodaj pymoo/NSGA-II jako alternatywny optimizer
                       (Pareto front zamiast scalaryzacji, ~100 linii)

Faza 4 (jeśli potrzebujesz): LangGraph dla scheduled unattended research
                              (gdy chcesz uruchamiać research crona bez interaktywnego agenta)
```

Każda faza jest niezależna. Zacznij od Fazy 1, reszta jest opcjonalna na podstawie wyników.
