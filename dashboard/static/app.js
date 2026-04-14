const statusBadge = document.getElementById("status-badge");
const dashboardVersion = document.getElementById("dashboard-version");
const positionsAge = document.getElementById("positions-age");
const positionsBody = document.getElementById("positions-body");
const tradesBody = document.getElementById("trades-body");
const signalsBody = document.getElementById("signals-body");
const metricsBody = document.getElementById("metrics-body");
const alertsBody = document.getElementById("alerts-body");
const alertsCount = document.getElementById("alerts-count");
const logStream = document.getElementById("log-stream");
const logFilter = document.getElementById("log-filter");
const processStatus = document.getElementById("process-status");
const controlMessage = document.getElementById("control-message");
const botModeSelect = document.getElementById("bot-mode");
const startButton = document.getElementById("btn-start");
const stopButton = document.getElementById("btn-stop");
const themeButton = document.getElementById("btn-theme");
const safeModeAlert = document.getElementById("safe-mode-alert");
const safeModeAlertReason = document.getElementById("safe-mode-alert-reason");

const riskMeta = document.getElementById("risk-meta");
const riskAlert = document.getElementById("risk-alert");
const riskAlertText = document.getElementById("risk-alert-text");
const riskRegime = document.getElementById("risk-regime");
const riskRegimeAsOf = document.getElementById("risk-regime-as-of");
const riskSignalCard = document.getElementById("risk-signal-card");
const riskBlocked = document.getElementById("risk-blocked");

const riskBars = {
  dailyDd: { bar: document.getElementById("risk-bar-daily-dd"), val: document.getElementById("risk-val-daily-dd") },
  weeklyDd: { bar: document.getElementById("risk-bar-weekly-dd"), val: document.getElementById("risk-val-weekly-dd") },
  losses: { bar: document.getElementById("risk-bar-losses"), val: document.getElementById("risk-val-losses") },
  positions: { bar: document.getElementById("risk-bar-positions"), val: document.getElementById("risk-val-positions") },
};

const egressFields = {
  enabled: document.getElementById("egress-enabled"),
  type: document.getElementById("egress-type"),
  host: document.getElementById("egress-host"),
  sticky: document.getElementById("egress-sticky"),
  sessionAge: document.getElementById("egress-session-age"),
  sessionStart: document.getElementById("egress-session-start"),
  failCount: document.getElementById("egress-fail-count"),
  lastBan: document.getElementById("egress-last-ban"),
  lastRotation: document.getElementById("egress-last-rotation"),
  safeMode: document.getElementById("egress-safe-mode"),
  meta: document.getElementById("egress-meta"),
};

const statusFields = {
  mode: document.getElementById("status-mode"),
  healthy: document.getElementById("status-healthy"),
  safeMode: document.getElementById("status-safe-mode"),
  safeModeReason: document.getElementById("status-safe-mode-reason"),
  openPositions: document.getElementById("status-open-positions"),
  consecutiveLosses: document.getElementById("status-consecutive-losses"),
  dailyDd: document.getElementById("status-daily-dd"),
  weeklyDd: document.getElementById("status-weekly-dd"),
  lastTrade: document.getElementById("status-last-trade"),
  timestamp: document.getElementById("status-timestamp"),
  configHash: document.getElementById("status-config-hash"),
  processMode: document.getElementById("status-process-mode"),
  processPid: document.getElementById("status-process-pid"),
  processExitCode: document.getElementById("status-process-exit-code"),
  uptime: document.getElementById("status-uptime"),
};

const logEntries = [];
let controlBusy = false;

function formatDate(value) {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

function formatNumber(value, digits = 2) {
  if (value === null || value === undefined) {
    return "-";
  }
  return Number(value).toFixed(digits);
}

function formatPercent(value) {
  if (value === null || value === undefined) {
    return "-";
  }
  return `${(Number(value) * 100).toFixed(2)}%`;
}

function formatUptime(seconds) {
  if (seconds === null || seconds === undefined) {
    return "-";
  }
  const total = Math.max(Math.floor(Number(seconds)), 0);
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const remainingSeconds = total % 60;
  if (hours > 0) {
    return `${hours}h ${minutes}m ${remainingSeconds}s`;
  }
  if (minutes > 0) {
    return `${minutes}m ${remainingSeconds}s`;
  }
  return `${remainingSeconds}s`;
}

function setControlEnabled(processRunning) {
  startButton.disabled = controlBusy || processRunning;
  stopButton.disabled = controlBusy || !processRunning;
  botModeSelect.disabled = controlBusy || processRunning;
}

function setControlBusy(action) {
  controlBusy = action !== null;
  startButton.textContent = action === "start" ? "Starting..." : "Start";
  stopButton.textContent = action === "stop" ? "Stopping..." : "Stop";
}

function setControlMessage(message) {
  controlMessage.textContent = message;
}

function setBadge(state) {
  statusBadge.className = "badge";
  if (!state) {
    statusBadge.classList.add("badge--unknown");
    statusBadge.textContent = "No data";
    return;
  }
  if (state.healthy && !state.safe_mode) {
    statusBadge.classList.add("badge--ok");
    statusBadge.textContent = "Healthy";
    return;
  }
  if (state.safe_mode) {
    statusBadge.classList.add("badge--warn");
    statusBadge.textContent = "Safe mode";
    return;
  }
  statusBadge.classList.add("badge--error");
  statusBadge.textContent = "Unhealthy";
}

function updateSafeModeAlert(state) {
  if (state && state.safe_mode) {
    safeModeAlertReason.textContent = state.safe_mode_reason || "unknown";
    safeModeAlert.style.display = "";
  } else {
    safeModeAlert.style.display = "none";
  }
}

function setRiskBar(entry, usage, limit, formatFn) {
  const pct = limit > 0 ? Math.min((usage / limit) * 100, 100) : 0;
  entry.bar.style.width = `${pct}%`;
  entry.bar.className = "risk-bar";
  if (pct >= 100) {
    entry.bar.classList.add("risk-bar--full");
  } else if (pct >= 80) {
    entry.bar.classList.add("risk-bar--warn");
  }
  entry.val.textContent = formatFn ? formatFn(usage, limit) : `${usage} / ${limit}`;
}

function renderRisk(payload) {
  const limits = payload.risk_limits || {};
  const usage = payload.risk_usage || {};

  riskRegime.textContent = payload.regime ? payload.regime.toUpperCase() : "-";
  riskRegime.className = payload.regime ? `regime-badge regime--${payload.regime.toLowerCase().replace("_", "-")}` : "";
  riskRegimeAsOf.textContent = formatDate(payload.regime_as_of);

  setRiskBar(
    riskBars.dailyDd,
    usage.daily_dd_pct || 0,
    limits.daily_dd_limit_pct || 1,
    (u, l) => `${formatPercent(u)} / ${formatPercent(l)}`
  );
  setRiskBar(
    riskBars.weeklyDd,
    usage.weekly_dd_pct || 0,
    limits.weekly_dd_limit_pct || 1,
    (u, l) => `${formatPercent(u)} / ${formatPercent(l)}`
  );
  setRiskBar(
    riskBars.losses,
    usage.consecutive_losses || 0,
    limits.max_consecutive_losses || 1,
    (u, l) => `${u} / ${l}`
  );
  setRiskBar(
    riskBars.positions,
    usage.open_positions_count || 0,
    limits.max_open_positions || 1,
    (u, l) => `${u} / ${l}`
  );

  const blocked = payload.risk_blocked || payload.safe_mode;
  riskBlocked.textContent = blocked ? "Yes" : "No";
  riskBlocked.className = blocked ? "badge badge--error" : "badge badge--ok";

  const sig = payload.latest_signal;
  if (!sig) {
    riskSignalCard.innerHTML = '<p class="empty">No signals recorded.</p>';
  } else {
    const promotedClass = sig.promoted ? "promoted" : "vetoed";
    const promotedLabel = sig.promoted ? "Promoted ✓" : "Vetoed ✗";
    const reasonsHtml = Array.isArray(sig.reasons) && sig.reasons.length
      ? sig.reasons.map((r) => `<li>${r}</li>`).join("")
      : "<li>-</li>";
    const govNotesHtml = Array.isArray(sig.governance_notes) && sig.governance_notes.length
      ? `<div class="sig-gov-notes"><strong>Governance:</strong> ${sig.governance_notes.join("; ")}</div>`
      : "";
    riskSignalCard.innerHTML = `
      <div class="sig-header">
        <span class="sig-direction sig-direction--${(sig.direction || "").toLowerCase()}">${sig.direction || "-"}</span>
        <span class="sig-badge sig-badge--${promotedClass}">${promotedLabel}</span>
        <span class="sig-setup">${sig.setup_type || "-"}</span>
      </div>
      <dl class="stat-list sig-stats">
        <div class="stat-row"><dt>Regime</dt><dd>${sig.regime ? sig.regime.toUpperCase() : "-"}</dd></div>
        <div class="stat-row"><dt>Confluence</dt><dd>${sig.confluence_score !== null && sig.confluence_score !== undefined ? formatNumber(sig.confluence_score, 2) : "-"} <small>(min ${formatNumber(limits.confluence_min, 1)})</small></dd></div>
        <div class="stat-row"><dt>RR ratio</dt><dd>${sig.rr_ratio !== null && sig.rr_ratio !== undefined ? formatNumber(sig.rr_ratio, 2) : "-"} <small>(min ${formatNumber(limits.min_rr, 1)})</small></dd></div>
        <div class="stat-row"><dt>Entry</dt><dd>${sig.entry_price !== null && sig.entry_price !== undefined ? formatNumber(sig.entry_price) : "-"}</dd></div>
        <div class="stat-row"><dt>Time</dt><dd>${formatDate(sig.timestamp)}</dd></div>
      </dl>
      <div class="sig-reasons"><strong>Reasons:</strong><ul>${reasonsHtml}</ul></div>
      ${govNotesHtml}
    `;
  }

  const alerts = [];
  if (payload.governance_blocked) alerts.push("Governance blocked latest signal.");
  if (payload.risk_blocked && !payload.governance_blocked) alerts.push("RiskGate is blocking new trades.");
  const dailyUsagePct = limits.daily_dd_limit_pct > 0 ? (usage.daily_dd_pct / limits.daily_dd_limit_pct) : 0;
  const weeklyUsagePct = limits.weekly_dd_limit_pct > 0 ? (usage.weekly_dd_pct / limits.weekly_dd_limit_pct) : 0;
  if (dailyUsagePct >= 0.8 && dailyUsagePct < 1.0) alerts.push(`Daily DD at ${formatPercent(usage.daily_dd_pct)} (${Math.round(dailyUsagePct * 100)}% of limit).`);
  if (weeklyUsagePct >= 0.8 && weeklyUsagePct < 1.0) alerts.push(`Weekly DD at ${formatPercent(usage.weekly_dd_pct)} (${Math.round(weeklyUsagePct * 100)}% of limit).`);

  if (alerts.length > 0) {
    riskAlertText.textContent = alerts.join(" ");
    riskAlert.style.display = "";
  } else {
    riskAlert.style.display = "none";
  }

  riskMeta.textContent = `Updated ${new Date().toLocaleTimeString()}`;
}

function renderEgress(payload) {
  const enabled = payload.proxy_enabled;
  egressFields.enabled.textContent = enabled ? "Yes" : "No";
  egressFields.enabled.className = enabled ? "badge badge--ok" : "badge badge--warn";

  egressFields.type.textContent = payload.proxy_type || "-";

  if (payload.proxy_host && payload.proxy_port) {
    egressFields.host.textContent = `${payload.proxy_host}:${payload.proxy_port}`;
  } else {
    egressFields.host.textContent = "-";
  }

  egressFields.sticky.textContent = payload.sticky_minutes !== null
    ? `${payload.sticky_minutes} min`
    : "-";

  egressFields.sessionAge.textContent = payload.session_age_minutes !== null
    ? `${payload.session_age_minutes} min`
    : "-";

  egressFields.sessionStart.textContent = formatDate(payload.last_session_start);

  const bans = payload.fail_count_24h;
  egressFields.failCount.textContent = String(bans);
  egressFields.failCount.className = bans > 0 ? "badge badge--error" : "";

  egressFields.lastBan.textContent = payload.last_ban_at ? formatDate(payload.last_ban_at) : "None";
  egressFields.lastRotation.textContent = payload.last_rotation_at ? formatDate(payload.last_rotation_at) : "None";

  const safe = payload.safe_mode;
  if (safe === null || safe === undefined) {
    egressFields.safeMode.textContent = "-";
    egressFields.safeMode.className = "";
  } else if (safe) {
    egressFields.safeMode.textContent = "Active";
    egressFields.safeMode.className = "badge badge--warn";
  } else {
    egressFields.safeMode.textContent = "Off";
    egressFields.safeMode.className = "badge badge--ok";
  }

  egressFields.meta.textContent = `Updated ${new Date().toLocaleTimeString()}`;

  if (safe) {
    safeModeAlertReason.textContent = payload.safe_mode_reason || "unknown";
    safeModeAlert.style.display = "";
  } else {
    safeModeAlert.style.display = "none";
  }
}

function renderStatus(payload) {
  dashboardVersion.textContent = payload.dashboard_version || "m4";
  const state = payload.bot_state;
  const process = payload.process || { running: false, pid: null, mode: null, exit_code: null };
  setBadge(state);
  updateSafeModeAlert(state);
  processStatus.textContent = process.running
    ? `Running PID ${process.pid} (${process.mode})`
    : "Stopped";
  setControlEnabled(process.running);

  if (!state) {
    statusFields.mode.textContent = "-";
    statusFields.healthy.textContent = "-";
    statusFields.safeMode.textContent = "-";
    statusFields.safeModeReason.textContent = "-";
    statusFields.openPositions.textContent = "-";
    statusFields.consecutiveLosses.textContent = "-";
    statusFields.dailyDd.textContent = "-";
    statusFields.weeklyDd.textContent = "-";
    statusFields.lastTrade.textContent = "-";
    statusFields.timestamp.textContent = "-";
    statusFields.configHash.textContent = "-";
  } else {
    statusFields.mode.textContent = state.mode;
    statusFields.healthy.textContent = state.healthy ? "Yes" : "No";
    statusFields.safeMode.textContent = state.safe_mode ? "Yes" : "No";
    statusFields.safeModeReason.textContent = state.safe_mode_reason || "-";
    statusFields.openPositions.textContent = String(state.open_positions_count);
    statusFields.consecutiveLosses.textContent = String(state.consecutive_losses);
    statusFields.dailyDd.textContent = formatPercent(state.daily_dd_pct);
    statusFields.weeklyDd.textContent = formatPercent(state.weekly_dd_pct);
    statusFields.lastTrade.textContent = formatDate(state.last_trade_at);
    statusFields.timestamp.textContent = formatDate(state.state_timestamp);
  }

  statusFields.configHash.textContent = payload.config_hash ? payload.config_hash.slice(0, 12) + "…" : "-";
  statusFields.processMode.textContent = process.mode || "-";
  statusFields.processPid.textContent = process.pid === null ? "-" : String(process.pid);
  statusFields.processExitCode.textContent = process.exit_code === null ? "-" : String(process.exit_code);
  statusFields.uptime.textContent = formatUptime(payload.uptime_seconds);
}

function appendCells(row, values) {
  for (const value of values) {
    const cell = document.createElement("td");
    cell.textContent = value;
    row.appendChild(cell);
  }
}

function renderEmptyTableRow(tbody, colspan, message) {
  tbody.replaceChildren();
  const row = document.createElement("tr");
  const cell = document.createElement("td");
  cell.colSpan = colspan;
  cell.className = "empty";
  cell.textContent = message;
  row.appendChild(cell);
  tbody.appendChild(row);
}

function renderPositions(payload) {
  positionsAge.textContent = payload.data_age_seconds === null
    ? "Age: -"
    : `Age: ${Math.round(payload.data_age_seconds)}s`;

  if (!payload.positions.length) {
    renderEmptyTableRow(positionsBody, 7, "No open positions.");
    return;
  }

  positionsBody.replaceChildren();
  for (const position of payload.positions) {
    const row = document.createElement("tr");
    appendCells(row, [
      position.direction,
      formatNumber(position.entry_price),
      formatNumber(position.size, 4),
      position.stop_loss === null ? "-" : formatNumber(position.stop_loss),
      position.take_profit_1 === null ? "-" : formatNumber(position.take_profit_1),
      position.status,
      formatDate(position.opened_at),
    ]);
    positionsBody.appendChild(row);
  }
}

function renderTrades(payload) {
  if (!payload.trades.length) {
    renderEmptyTableRow(tradesBody, 10, "No closed trades.");
    return;
  }

  tradesBody.replaceChildren();
  for (const trade of payload.trades) {
    const row = document.createElement("tr");
    if (trade.outcome === "WIN") row.classList.add("row--win");
    if (trade.outcome === "LOSS") row.classList.add("row--loss");
    appendCells(row, [
      trade.direction,
      formatNumber(trade.entry_price),
      trade.exit_price === null ? "-" : formatNumber(trade.exit_price),
      trade.pnl_abs === null ? "-" : formatNumber(trade.pnl_abs),
      trade.pnl_r === null ? "-" : formatNumber(trade.pnl_r, 3),
      trade.regime || "-",
      trade.confluence_score === null ? "-" : formatNumber(trade.confluence_score, 2),
      trade.exit_reason || "-",
      trade.outcome || "-",
      formatDate(trade.closed_at),
    ]);
    tradesBody.appendChild(row);
  }
}

function renderSignals(payload) {
  if (!payload.signals.length) {
    renderEmptyTableRow(signalsBody, 8, "No signals recorded.");
    return;
  }

  signalsBody.replaceChildren();
  for (const sig of payload.signals) {
    const row = document.createElement("tr");
    if (!sig.promoted) row.classList.add("row--vetoed");
    const reasonsText = Array.isArray(sig.reasons) ? sig.reasons.join(", ") : "-";
    appendCells(row, [
      formatDate(sig.timestamp),
      sig.direction,
      sig.regime,
      formatNumber(sig.confluence_score, 2),
      reasonsText || "-",
      sig.promoted ? "✓" : "✗",
      sig.rr_ratio === null ? "-" : formatNumber(sig.rr_ratio, 2),
      sig.entry_price === null ? "-" : formatNumber(sig.entry_price),
    ]);
    signalsBody.appendChild(row);
  }
}

function renderMetrics(payload) {
  if (!payload.metrics.length) {
    renderEmptyTableRow(metricsBody, 7, "No daily metrics yet.");
    return;
  }

  metricsBody.replaceChildren();
  for (const m of payload.metrics) {
    const row = document.createElement("tr");
    appendCells(row, [
      m.date,
      String(m.trades_count),
      String(m.wins),
      String(m.losses),
      formatNumber(m.pnl_abs),
      formatNumber(m.expectancy_r, 3),
      formatPercent(m.daily_dd_pct),
    ]);
    metricsBody.appendChild(row);
  }
}

function renderAlerts(payload) {
  const count = payload.alerts.length;
  alertsCount.textContent = count === 0 ? "None" : `${count} alert${count === 1 ? "" : "s"}`;

  if (!count) {
    renderEmptyTableRow(alertsBody, 4, "No alerts.");
    return;
  }

  alertsBody.replaceChildren();
  for (const alert of payload.alerts) {
    const row = document.createElement("tr");
    row.classList.add(`alert--${alert.severity.toLowerCase()}`);
    appendCells(row, [
      formatDate(alert.timestamp),
      alert.severity,
      alert.component,
      alert.message,
    ]);
    alertsBody.appendChild(row);
  }
}

function lineLevel(line) {
  if (line.includes("| ERROR |")) {
    return "error";
  }
  if (line.includes("| WARNING |") || line.includes("| WARN |")) {
    return "warn";
  }
  return "info";
}

function passesFilter(entry, filterValue) {
  if (filterValue === "all") {
    return true;
  }
  if (filterValue === "warn") {
    return entry.level === "warn" || entry.level === "error";
  }
  return entry.level === "error";
}

function renderLogStream() {
  const filterValue = logFilter.value;
  const lines = logEntries
    .filter((entry) => passesFilter(entry, filterValue))
    .map((entry) => entry.line);
  logStream.textContent = lines.join("\n");
  logStream.scrollTop = logStream.scrollHeight;
}

function appendLogLine(line) {
  logEntries.push({ line, level: lineLevel(line) });
  if (logEntries.length > 400) {
    logEntries.shift();
  }
  renderLogStream();
}

async function loadJson(url) {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json();
}

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json();
}

async function refreshStatus() {
  try {
    renderStatus(await loadJson("/api/status"));
  } catch (error) {
    statusBadge.className = "badge badge--error";
    statusBadge.textContent = "Status error";
  }
}

async function refreshPositions() {
  try {
    renderPositions(await loadJson("/api/positions"));
  } catch (error) {
    positionsAge.textContent = "Age: error";
  }
}

async function refreshTrades() {
  try {
    renderTrades(await loadJson("/api/trades?limit=20"));
  } catch (error) {
    renderEmptyTableRow(tradesBody, 10, "Trades unavailable.");
  }
}

async function refreshSignals() {
  try {
    renderSignals(await loadJson("/api/signals?limit=20"));
  } catch (error) {
    renderEmptyTableRow(signalsBody, 8, "Signals unavailable.");
  }
}

async function refreshMetrics() {
  try {
    renderMetrics(await loadJson("/api/metrics?days=14"));
  } catch (error) {
    renderEmptyTableRow(metricsBody, 7, "Metrics unavailable.");
  }
}

async function refreshAlerts() {
  try {
    renderAlerts(await loadJson("/api/alerts?limit=20"));
  } catch (error) {
    renderEmptyTableRow(alertsBody, 4, "Alerts unavailable.");
  }
}

async function refreshEgress() {
  try {
    renderEgress(await loadJson("/api/egress"));
  } catch (error) {
    egressFields.meta.textContent = "Egress unavailable";
  }
}

async function refreshRisk() {
  try {
    renderRisk(await loadJson("/api/risk"));
  } catch (error) {
    if (riskMeta) riskMeta.textContent = "Risk data unavailable";
  }
}

function handleThemeToggle() {
  const html = document.documentElement;
  const isDark = html.getAttribute("data-theme") === "dark";
  html.setAttribute("data-theme", isDark ? "light" : "dark");
  themeButton.textContent = isDark ? "🌙" : "☀️";
  try {
    localStorage.setItem("dashboard-theme", isDark ? "light" : "dark");
  } catch (_) {}
}

function initTheme() {
  try {
    const saved = localStorage.getItem("dashboard-theme");
    if (saved === "dark") {
      document.documentElement.setAttribute("data-theme", "dark");
      themeButton.textContent = "☀️";
    }
  } catch (_) {}
}

async function handleStart() {
  const mode = botModeSelect.value;
  if (mode === "LIVE") {
    const confirmed = window.confirm("Start LIVE trading with real funds? This will place real orders.");
    if (!confirmed) {
      return;
    }
  }

  setControlBusy("start");
  setControlEnabled(false);
  try {
    const result = await postJson("/api/bot/start", { mode });
    if (result.started) {
      setControlMessage(`Started PID ${result.pid} in ${result.mode} mode.`);
    } else {
      setControlMessage(`Error: ${result.reason}.`);
    }
    await refreshStatus();
  } catch (error) {
    setControlMessage(`Error: ${error.message}`);
  } finally {
    setControlBusy(null);
    await refreshStatus();
  }
}

async function handleStop() {
  setControlBusy("stop");
  setControlEnabled(false);
  try {
    const result = await postJson("/api/bot/stop", { reason: "operator_stop" });
    if (result.stopped) {
      setControlMessage(result.graceful ? `Stopped gracefully (PID ${result.pid}).` : `Stopped with hard fallback (PID ${result.pid}).`);
    } else {
      setControlMessage(`Error: ${result.reason}.`);
    }
    await refreshStatus();
  } catch (error) {
    setControlMessage(`Error: ${error.message}`);
  } finally {
    setControlBusy(null);
    await refreshStatus();
  }
}

function connectLogs() {
  const source = new EventSource("/api/logs/stream");
  source.onmessage = (event) => {
    const payload = JSON.parse(event.data);
    appendLogLine(payload.line);
  };
  source.onerror = () => {
    appendLogLine("Log stream disconnected. Waiting for reconnect...");
  };
}

logFilter.addEventListener("change", renderLogStream);
startButton.addEventListener("click", handleStart);
stopButton.addEventListener("click", handleStop);
themeButton.addEventListener("click", handleThemeToggle);

initTheme();
setControlEnabled(false);
refreshStatus();
refreshPositions();
refreshTrades();
refreshSignals();
refreshMetrics();
refreshAlerts();
refreshEgress();
refreshRisk();
connectLogs();

window.setInterval(refreshStatus, 5000);
window.setInterval(refreshPositions, 10000);
window.setInterval(refreshTrades, 30000);
window.setInterval(refreshSignals, 60000);
window.setInterval(refreshMetrics, 120000);
window.setInterval(refreshAlerts, 60000);
window.setInterval(refreshEgress, 10000);
window.setInterval(refreshRisk, 10000);
