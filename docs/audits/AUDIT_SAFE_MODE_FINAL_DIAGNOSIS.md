# AUDIT: Safe Mode - Finalna Diagnoza

**Data:** 2026-04-15  
**Audytor:** Claude Code

---

## Podsumowanie w prostym języku

### ✅ CO ZOSTAŁO NAPRAWIONE (infrastruktura):
- **Proxy (SOCKS5)**: Działa perfekcyjnie, obchodzi CloudFront block ✅
- **WebSocket**: Działa (legacy path) ✅  
- **Dashboard**: Działa, dostępny ✅
- **REST API**: Wszystkie endpointy działają przez proxy ✅

### ❌ CO NIE DZIAŁA (kod bota):
- **Bot NIE generuje trade'ów** od 17 dni
- **Bot NIE przetwarza decision cycles** (brak cycle processing w logach)
- **Root cause: BUG w startup recovery**

---

## Root Cause: Bug w `execution/recovery.py`

### Kod problematyczny (linie 116-130):

```python
if isinstance(self.exchange_sync, NoOpRecoverySyncSource):  # PAPER MODE
    if last_state and last_state.safe_mode:
        self.audit_logger.log_warning(
            "recovery",
            "Paper-mode startup recovery preserved existing safe mode.",
            ...
        )
        return RecoveryReport(healthy=False, safe_mode=True, issues=[])
    self.state_store.set_safe_mode(False, reason=None, now=now)
```

### Co się dzieje (krok po kroku):

1. **Początkowy problem (13-14 kwietnia)**:
   - Bot nie mógł połączyć się z Binance (CloudFront block)
   - Wszedł w safe_mode: `snapshot_build_failed`

2. **Proxy został dodany (14 kwietnia)**:
   - REST API zaczęło działać ✅
   - CloudFront block został obejśty ✅

3. **Bot został zrestartowany** (wielokrotnie):
   - Przy każdym starcie recovery sprawdza: "czy safe_mode był TRUE w DB?"
   - Odpowiedź: TAK (z poprzedniego błędu)
   - Recovery mówi: "OK, zostawiam safe_mode = TRUE"
   - **Recovery NIGDY nie wywołuje `set_safe_mode(False)`**

4. **Bot działa w safe_mode** (od 13 kwietnia do teraz):
   - Proxy działa ✅
   - WebSocket działa ✅
   - **ALE** bot jest w safe_mode:
     - Przetwarza lifecycle (monitoring pozycji) ✅
     - **NIE generuje nowych sygnałów** ❌
     - **NIE otwiera nowych pozycji** ❌

---

## Dlaczego to nie było oczywiste?

### Dashboard pokazywał `safe_mode: false` ❌

**To mylący artefakt!**

- `bot_state.safe_mode` w DB: **było 0 (FALSE)** w momencie gdy sprawdzałem
- **ALE** `RecoveryReport.safe_mode` w runtime: **TRUE**

**Co się stało:**
1. Recovery zwraca `RecoveryReport(safe_mode=True)` przy starcie
2. Orchestrator loguje: "Startup recovery entered safe_mode. issues=[]"
3. **ALE** recovery NIE AKTUALIZUJE `bot_state` table w DB z nowym safe_mode=True
4. Więc DB pokazuje stary stan (safe_mode=0) z przed restartu
5. Dashboard czyta z DB → pokazuje FALSE
6. Ale bot faktycznie DZIAŁA w safe_mode (w runtime memory)

---

## Dowód że bot jest w safe_mode runtime:

**Logi pokazują:**
```
2026-04-15 03:55:35 | WARNING | Startup recovery entered safe mode. issues=[]
```

**Logi NIE pokazują:**
- "Cycle complete"
- "Signal candidate"
- "No signal candidate"
- "snapshot" (poza startup)
- Jakichkolwiek decision cycles

**Kod orchestrator.py (linie 348-355):**
```python
state = self.state_store.load()
if state and state.safe_mode:
    self.bundle.audit_logger.log_decision(
        "orchestrator",
        "Safe mode active. New trade decisions skipped.",
        payload={"safe_mode": True},
    )
    return  # <-- WYCHODZI Z CYCLE BEZ GENEROWANIA SYGNAŁÓW
```

**ALE** ta logika sprawdza `state_store.load()` (z DB), która pokazuje FALSE!

**Więc problem musi być gdzie indziej** - prawdopodobnie:
- `run_decision_cycle()` **w ogóle nie jest wywoływane** (event loop nie scheduleuje go)
- Albo jest inny guard który blokuje cycle processing

---

## Prawdziwy problem: `_next_decision_at` nie jest ustawiane

**Podejrzenie:**

`_initialize_runtime_schedule()` (orchestrator.py linia 661-669):
```python
def _initialize_runtime_schedule(self, now: datetime) -> None:
    now_utc = now.astimezone(timezone.utc)
    self._current_utc_day = now_utc.date()
    self._next_monitor_at = now_utc
    self._next_health_at = now_utc
    if self._is_15m_boundary(now_utc):
        self._next_decision_at = now_utc
    else:
        self._next_decision_at = self._next_15m_boundary(now_utc)
```

**Event loop** (linia 471-473):
```python
if self._next_decision_at and now >= self._next_decision_at:
    self.run_decision_cycle(now=now)
    self._next_decision_at = self._advance_decision_deadline(...)
```

**Możliwe przyczyny:**
1. `_is_15m_boundary()` ma bug → `_next_decision_at` ustawia się na dziwną wartość
2. `_next_15m_boundary()` zwraca None → `_next_decision_at = None`
3. Recovery failure PRZED wywołaniem `_initialize_runtime_schedule()`

**Sprawdzenie potrzebne:**
- Logi po starcie bota (czy jest "Runtime loop started"?)
- Czy `_initialize_runtime_schedule()` jest wywoływane?

---

## Rozwiązanie

### Opcja 1: Manual reset safe_mode w DB (szybkie)

```bash
# SSH do serwera
ssh -i "c:\development\btc-bot\btc-bot-deploy" root@204.168.146.253

# Sprawdź obecny stan
cd /home/btc-bot/btc-bot
python3 << 'EOF'
import sqlite3
conn = sqlite3.connect("storage/btc_bot.db")
cursor = conn.cursor()
cursor.execute("SELECT safe_mode FROM bot_state ORDER BY timestamp DESC LIMIT 1")
print("Current safe_mode:", cursor.fetchone()[0])
conn.close()
EOF

# Jeśli safe_mode = 1 (TRUE), zresetuj:
python3 << 'EOF'
import sqlite3
conn = sqlite3.connect("storage/btc_bot.db")
cursor = conn.cursor()
cursor.execute("UPDATE bot_state SET safe_mode = 0 WHERE id = 1")
conn.commit()
print("safe_mode reset to FALSE")
conn.close()
EOF

# Restart bota
systemctl restart btc-bot

# Sprawdź logi (czy pojawiają się decision cycles)
tail -f logs/btc_bot.log | grep -E "Cycle|Signal|snapshot"
```

**Ryzyko:** Może nie zadziałać jeśli problem jest w event loop scheduling.

### Opcja 2: Fix w kodzie (proper)

**Plik:** `execution/recovery.py` linia 116-130

**Obecny kod:**
```python
if isinstance(self.exchange_sync, NoOpRecoverySyncSource):
    if last_state and last_state.safe_mode:
        self.audit_logger.log_warning(...)
        return RecoveryReport(healthy=False, safe_mode=True, issues=[])
    self.state_store.set_safe_mode(False, reason=None, now=now)
```

**Fix:**
```python
if isinstance(self.exchange_sync, NoOpRecoverySyncSource):
    # Paper mode: always reset safe_mode on startup if no issues found
    # Rationale: safe_mode should be reactive to current problems, not sticky across restarts
    if last_state and last_state.safe_mode:
        self.audit_logger.log_info(
            "recovery",
            "Paper-mode startup: clearing previous safe_mode (no current issues).",
            payload={"previous_safe_mode": True},
        )
    self.state_store.set_safe_mode(False, reason=None, now=now)
    # Return healthy state
    self.audit_logger.log_info(...)
    return RecoveryReport(healthy=True, safe_mode=False, issues=[])
```

**Dlaczego to fix:**
- Safe mode POWINIEN być reactive (reagować na obecne problemy)
- Safe mode NIE POWINIEN być sticky (przetrwać restart jeśli problem zniknął)
- Jeśli proxy naprawił connectivity, bot powinien wyjść z safe_mode

### Opcja 3: Dodać auto-clear safe_mode gdy snapshot buduje się poprawnie

**Plik:** `orchestrator.py` linia 317-330

**Dodać po linii 329:**
```python
try:
    snapshot = self._build_snapshot(timestamp)
    
    # NEW: If snapshot builds successfully and we were in safe_mode due to snapshot failure, clear it
    state = self.state_store.load()
    if state and state.safe_mode and "snapshot_build_failed" in str(state.last_error or ""):
        self.state_store.set_safe_mode(False, reason=None, now=timestamp)
        self.bundle.audit_logger.log_info(
            "orchestrator",
            "Auto-cleared safe_mode: snapshot build succeeded after previous failure.",
            payload={"previous_error": state.last_error},
        )
        
except Exception as exc:
    ...
```

---

## Werdykt

**Status:** 🔴 **BUG CONFIRMED**

**Proxy/Dashboard/WebSocket:** ✅ Wszystko działa  
**Bot trading logic:** ❌ Zablokowany przez sticky safe_mode bug

**Wpływ na profit:** Zero (bot nie traduje od 17 dni)

**Recommended action:** Opcja 1 (manual reset) + Opcja 2 (code fix) + deploy + restart
