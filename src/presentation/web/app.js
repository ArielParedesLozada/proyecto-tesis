/* ============================================================
   app.js — controlador del dashboard.

   Carga /api/dashboard, actualiza KPIs, estado operacional,
   condiciones, detalle de predicción y el gráfico EnergyChart.
   Auto-refresh cada 10 s.
   ============================================================ */

"use strict";

const REFRESH_MS = 10_000;

const STATUS_META = {
  NORMAL: { icon: "✓", label: "Dentro de límites" },
  WARNING: { icon: "▲", label: "Cercano a límites" },
  ALERT: { icon: "✕", label: "Fuera de límites" },
};

const LEGEND = [
  { color: COLORS.real, label: "Consumo real" },
  { color: COLORS.prediction, label: "Predicción" },
  { color: COLORS.upper, label: "Límite superior" },
  { color: COLORS.lower, label: "Límite inferior" },
];

const $ = (id) => document.getElementById(id);
const fmt1 = (v) => Number(v).toFixed(1);
// const pad2 = (n) => String(n).padStart(2, "0");

function fmtTime(iso) {
  const d = new Date(iso);
  return `${pad2(d.getDate())}/${pad2(d.getMonth() + 1)}/${d.getFullYear()} ${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
}

function fmtHorizon(startIso, endIso) {
  const a = new Date(startIso);
  const b = new Date(endIso);
  return `${pad2(a.getHours())}:${pad2(a.getMinutes())} – ${pad2(b.getHours())}:${pad2(b.getMinutes())}`;
}

const energyChart = new EnergyChart($("chart"), $("tooltip"));

renderLegend();

/* ---------- render ---------- */

function renderDashboard(data) {
  // Topbar
  $("machine-id").textContent = data.machine_id;
  $("machine-desc").textContent = data.machine_description;
  setBadge($("machine-state"), `badge-${data.machine_state}`, data.machine_state);

  // KPIs
  $("kpi-current").textContent = `${fmt1(data.current_consumption)} kWh`;
  $("kpi-shift-name").textContent = data.current_shift;
  $("kpi-shift").textContent = `${fmt1(data.current_shift_consumption)} kWh`;
  $("kpi-shift-remaining").textContent = `${data.shift_remaining_hours} h`;
  $("kpi-pred-shift").textContent = data.prediction.shift;
  $("kpi-prediction").textContent = `${fmt1(data.prediction.consumption)} kWh`;
  $("kpi-pred-range").textContent = `[${fmt1(data.prediction.lower_bound)} – ${fmt1(data.prediction.upper_bound)}] kWh`;

  const n = data.history.length;
  const lastLimitUp = data.history_limits.upper[n - 1];
  const lastLimitLow = data.history_limits.lower[n - 1];
  $("kpi-upper").textContent = `${fmt1(lastLimitUp)} kWh`;
  $("kpi-lower").textContent = `${fmt1(lastLimitLow)} kWh`;

  // Estado operacional (consumo actual vs banda actual)
  const status = data.history_statuses[n - 1];
  const meta = STATUS_META[status];
  $("kpi-status").textContent = `${meta.icon} ${meta.label}`;
  $("kpi-status-detail").textContent =
    `Consumo ${fmt1(data.current_consumption)} kWh · banda [${fmt1(lastLimitLow)} – ${fmt1(lastLimitUp)}] kWh`;
  $("status-card").className = `card kpi status-card status-${status}`;
  $("kpi-status").className = `value status-value status-${status}`;

  // Detalle de predicción
  const p = data.prediction;
  const pMeta = STATUS_META[p.status];
  $("pred-shift").textContent = p.shift;
  $("pred-horizon").textContent = fmtHorizon(p.start, p.end);
  $("pred-consumption").textContent = `${fmt1(p.consumption)} kWh`;
  $("pred-interval").textContent = `[${fmt1(p.lower_bound)} – ${fmt1(p.upper_bound)}] kWh`;
  const predStatusEl = $("pred-status");
  predStatusEl.textContent = `${pMeta.icon} ${pMeta.label}`;
  predStatusEl.className = `prediction-value status-${p.status}`;

  // Condiciones actuales
  const c = data.current_conditions;
  $("cond-temperature").textContent = `${fmt1(c.temperature)} °C`;
  $("cond-production").textContent = `${fmt1(c.production)} uds/h`;
  $("cond-load").textContent = `${fmt1(c.load)} %`;
  $("cond-state").textContent = c.state;
  $("cond-timestamp").textContent = fmtTime(c.timestamp);
  $("cond-last-shift").textContent = `${data.previous_shift} · ${fmt1(data.previous_shift_consumption)} kWh`;

  // Gráfico
  energyChart.render(data);

  // Footer
  $("footer-updated").textContent = fmtTime(data.generated_at);
}

/* ---------- carga de datos ---------- */

async function loadDashboard() {
  try {
    const res = await fetch("/api/dashboard");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    renderDashboard(data);
    $("auto-refresh-label").textContent = `auto-refresh ${REFRESH_MS / 1000} s`;
  } catch (err) {
    $("auto-refresh-label").textContent = "sin conexión · reintentando…";
    console.warn("No se pudo cargar el dashboard:", err);
  }
}

/* ---------- legend ---------- */

function renderLegend() {
  const el = $("legend");
  el.innerHTML = "";
  for (const item of LEGEND) {
    const chip = document.createElement("span");
    chip.className = "chip";
    chip.innerHTML = `<span class="dot" style="background:${item.color}"></span>${item.label}`;
    el.appendChild(chip);
  }
}

function setBadge(el, cls, text) {
  el.className = `badge ${cls}`;
  el.textContent = text;
}

/* ---------- arranque ---------- */

$("btn-refresh").addEventListener("click", loadDashboard);
loadDashboard();
setInterval(loadDashboard, REFRESH_MS);