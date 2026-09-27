/* ============================================================
   EnergyChart — gráfico de control energético (canvas, sin librerías).

   Dibuja sobre el mismo eje temporal:
     - consumo real (histórico)           -> línea sólida
     - predicción del siguiente turno     -> línea discontinua
     - límite superior / inferior         -> líneas discontinuas
   Muestra una banda de control y colorea el consumo real según su
   estado (NORMAL / WARNING / ALERT). Incluye tooltip al pasar el ratón.
   ============================================================ */

"use strict";

const COLORS = {
  real: "#38bdf8",
  prediction: "#fbbf24",
  upper: "#f87171",
  lower: "#34d399",
  bandHistory: "rgba(56, 189, 248, 0.07)",
  bandForecast: "rgba(251, 191, 36, 0.09)",
  grid: "rgba(142, 160, 191, 0.12)",
  axis: "rgba(142, 160, 191, 0.45)",
  text: "#8ea0bf",
  normal: "#22c55e",
  warning: "#fbbf24",
  alert: "#ef4444",
  divider: "rgba(142, 160, 191, 0.35)",
};

const STATUS_COLOR = { NORMAL: COLORS.normal, WARNING: COLORS.warning, ALERT: COLORS.alert };

class EnergyChart {
  /**
   * @param {HTMLCanvasElement} canvas
   * @param {HTMLElement} tooltipEl
   */
  constructor(canvas, tooltipEl) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.tooltipEl = tooltipEl;
    this.model = null; // [{t, value, upper, lower, status, phase}]
    this.hoverIndex = -1;
    this._bindEvents();
  }

  /* ---------- API ---------- */

  /**
   * @param {object} data dashboard tal como lo devuelve /api/dashboard
   */
  render(data) {
    this.model = buildModel(data);
    this.hoverIndex = -1;
    this.hideTooltip();
    this._draw();
  }

  hideTooltip() {
    this.tooltipEl.classList.add("hidden");
  }

  /* ---------- eventos ---------- */

  _bindEvents() {
    this.canvas.addEventListener("mousemove", (e) => this._onMove(e));
    this.canvas.addEventListener("mouseleave", () => {
      this.hoverIndex = -1;
      this.hideTooltip();
      this._draw();
    });
    window.addEventListener("resize", () => {
      if (this.model) this._draw();
    });
  }

  _onMove(e) {
    if (!this.model || this.model.length === 0) return;
    const layout = this._computeLayout();
    const rect = this.canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const idx = Math.round((x - layout.plotLeft) / layout.pxPerPoint);
    if (layout.pxPerPoint <= 0 || idx < 0 || idx >= this.model.length) {
      this.hoverIndex = -1;
      this.hideTooltip();
      this._draw();
      return;
    }
    if (idx !== this.hoverIndex) {
      this.hoverIndex = idx;
      this._draw();
    }
    this._showTooltip(e, idx);
  }

  _showTooltip(e, idx) {
    const p = this.model[idx];
    const est = p.status;
    const rows = [
      `<div class="tt-time">${formatTime(p.t)}</div>`,
    ];
    if (p.phase === "hist") {
      rows.push(rowTT("Consumo real", `${p.value.toFixed(1)} kWh`));
    } else {
      rows.push(rowTT("Predicción", `${p.value.toFixed(1)} kWh`));
    }
    rows.push(rowTT("Límite sup.", `${p.upper.toFixed(1)} kWh`));
    rows.push(rowTT("Límite inf.", `${p.lower.toFixed(1)} kWh`));
    rows.push(rowTT("Estado", statusSymbol(est), `tt-status-${est}`));

    this.tooltipEl.innerHTML = rows.join("");
    this.tooltipEl.classList.remove("hidden");

    // Posiciona el tooltip cerca del cursor, dentro de la ventana.
    const pad = 14;
    const tw = this.tooltipEl.offsetWidth;
    const th = this.tooltipEl.offsetHeight;
    let left = e.clientX + pad;
    let top = e.clientY + pad;
    if (left + tw > window.innerWidth - 8) left = e.clientX - tw - pad;
    if (top + th > window.innerHeight - 8) top = e.clientY - th - pad;
    this.tooltipEl.style.left = `${left}px`;
    this.tooltipEl.style.top = `${top}px`;
  }

  /* ---------- layout ---------- */

  _computeLayout() {
    const rect = this.canvas.getBoundingClientRect();
    const m = { top: 22, right: 18, bottom: 32, left: 62 };
    const plotWidth = Math.max(1, rect.width - m.left - m.right);
    const plotHeight = Math.max(1, this.canvas.height - m.top - m.bottom);
    const span = Math.max(1, this.model.length - 1);
    return {
      ...m,
      plotWidth,
      plotHeight,
      pxPerPoint: plotWidth / span,
    };
  }

  _extents() {
    let yMin = Infinity;
    let yMax = -Infinity;
    for (const p of this.model) {
      yMin = Math.min(yMin, p.value, p.lower, p.upper);
      yMax = Math.max(yMax, p.value, p.lower, p.upper);
    }
    yMin = Math.max(0, yMin);
    if (yMin === yMax) { yMin -= 1; yMax += 1; }
    const pad = (yMax - yMin) * 0.08;
    return { yMin: Math.max(0, yMin - pad), yMax: yMax + pad };
  }

  /* ---------- dibujado ---------- */

  _draw() {
    if (!this.model || this.model.length === 0) return;
    this._resizeCanvas();

    const ctx = this.ctx;
    const dpr = window.devicePixelRatio || 1;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    const layout = this._computeLayout();
    const { yMin, yMax } = this._extents();
    const ySpan = yMax - yMin;

    const x = (i) => layout.plotLeft + i * layout.pxPerPoint;
    const y = (v) => layout.plotTop + layout.plotHeight - ((v - yMin) / ySpan) * layout.plotHeight;

    ctx.clearRect(0, 0, this.canvas.width / dpr, this.canvas.height / dpr);

    // --- rejilla y ejes ------------------------------------------------
    const ticks = niceTicks(yMin, yMax, 5);
    ctx.strokeStyle = COLORS.grid;
    ctx.fillStyle = COLORS.text;
    ctx.font = "11px ui-monospace, Menlo, Consolas, monospace";
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (const t of ticks) {
      const yy = y(t);
      ctx.moveTo(layout.plotLeft, yy);
      ctx.lineTo(layout.plotLeft + layout.plotWidth, yy);
    }
    ctx.stroke();

    ctx.textAlign = "right";
    ctx.textBaseline = "middle";
    for (const t of ticks) {
      ctx.fillText(t.toFixed(0), layout.plotLeft - 8, y(t));
    }
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    const n = this.model.length;
    const labelEvery = Math.max(1, Math.ceil(n / 7));
    for (let i = 0; i < n; i += labelEvery) {
      ctx.fillText(formatAxisTime(this.model[i].t), x(i), layout.plotTop + layout.plotHeight + 8);
    }

    ctx.save();
    ctx.beginPath();
    ctx.rect(layout.plotLeft, layout.plotTop, layout.plotWidth, layout.plotHeight);
    ctx.clip();

    const nHist = this.model.filter((p) => p.phase === "hist").length;

    // --- bandas de control --------------------------------------------
    fillBand(ctx, this.model, 0, nHist, x, y, COLORS.bandHistory);
    fillBand(ctx, this.model, nHist, this.model.length, x, y, COLORS.bandForecast);

    // --- límites superior / inferior -----------------------------------
    const styleDash = [5, 4];
    drawPolyline(ctx, this.model, x, y, (p) => p.upper, 0, nHist, COLORS.upper, 1.4, styleDash);
    drawPolyline(ctx, this.model, x, y, (p) => p.upper, nHist, this.model.length, COLORS.upper, 1.4, styleDash);
    drawPolyline(ctx, this.model, x, y, (p) => p.lower, 0, nHist, COLORS.lower, 1.4, styleDash);
    drawPolyline(ctx, this.model, x, y, (p) => p.lower, nHist, this.model.length, COLORS.lower, 1.4, styleDash);

    // --- separador histórico / futuro ----------------------------------
    const sepX = x(nHist - 1) + layout.pxPerPoint / 2;
    ctx.strokeStyle = COLORS.divider;
    ctx.setLineDash([2, 3]);
    ctx.beginPath();
    ctx.moveTo(sepX, layout.plotTop);
    ctx.lineTo(sepX, layout.plotTop + layout.plotHeight);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = COLORS.text;
    ctx.font = "bold 11px ui-monospace, Menlo, Consolas, monospace";
    ctx.textAlign = "right";
    ctx.textBaseline = "bottom";
    ctx.fillText("PRÓXIMO TURNO →", layout.plotRight - 6, layout.plotTop + layout.plotHeight - 4);

    // --- consumo real (segmentos coloreados por estado) ----------------
    for (let i = 0; i < nHist - 1; i++) {
      const a = this.model[i];
      const b = this.model[i + 1];
      const worst = worstStatus(a.status, b.status);
      ctx.strokeStyle = STATUS_COLOR[worst];
      ctx.lineWidth = 2.2;
      ctx.beginPath();
      ctx.moveTo(x(i), y(a.value));
      ctx.lineTo(x(i + 1), y(b.value));
      ctx.stroke();
    }
    // punto actual
    const cur = this.model[nHist - 1];
    ctx.beginPath();
    ctx.arc(x(nHist - 1), y(cur.value), 4.5, 0, Math.PI * 2);
    ctx.fillStyle = STATUS_COLOR[cur.status];
    ctx.fill();
    ctx.strokeStyle = COLORS.real;
    ctx.lineWidth = 2;
    ctx.stroke();

    // --- predicción (discontinua) ---------------------------------------
    drawPolyline(ctx, this.model, x, y, (p) => p.value, nHist, this.model.length, COLORS.prediction, 2.2, [6, 4]);
    for (let i = nHist; i < this.model.length; i++) {
      const p = this.model[i];
      ctx.beginPath();
      ctx.arc(x(i), y(p.value), 3, 0, Math.PI * 2);
      ctx.fillStyle = COLORS.prediction;
      ctx.fill();
    }

    // --- cursor de hover ------------------------------------------------
    if (this.hoverIndex >= 0 && this.hoverIndex < this.model.length) {
      const hx = x(this.hoverIndex);
      ctx.strokeStyle = "rgba(230, 237, 247, 0.35)";
      ctx.setLineDash([2, 3]);
      ctx.beginPath();
      ctx.moveTo(hx, layout.plotTop);
      ctx.lineTo(hx, layout.plotTop + layout.plotHeight);
      ctx.stroke();
      ctx.setLineDash([]);

      const p = this.model[this.hoverIndex];
      const pts = [
        { v: p.value, c: p.phase === "hist" ? STATUS_COLOR[p.status] : COLORS.prediction },
        { v: p.upper, c: COLORS.upper },
        { v: p.lower, c: COLORS.lower },
      ];
      for (const pt of pts) {
        ctx.beginPath();
        ctx.arc(hx, y(pt.v), 3.5, 0, Math.PI * 2);
        ctx.fillStyle = pt.c;
        ctx.fill();
      }
    }

    ctx.restore();
  }

  _resizeCanvas() {
    const dpr = window.devicePixelRatio || 1;
    const rect = this.canvas.getBoundingClientRect();
    const width = Math.max(100, Math.round(rect.width));
    const height = Math.max(200, Math.round(this.canvas.clientHeight || rect.height));
    const cssH = height;
    if (this.canvas.width !== width * dpr || this.canvas.height !== cssH * dpr) {
      this.canvas.width = width * dpr;
      this.canvas.height = cssH * dpr;
      this.canvas.style.height = `${cssH}px`;
    }
  }
}

/* ---------- utilidades ---------- */

function buildModel(data) {
  const model = [];
  const hist = data.history;
  const hLimits = data.history_limits;
  const hStatuses = data.history_statuses;
  for (let i = 0; i < hist.length; i++) {
    model.push({
      t: new Date(hist[i].timestamp),
      value: hist[i].consumption,
      upper: hLimits.upper[i],
      lower: hLimits.lower[i],
      status: hStatuses[i],
      phase: "hist",
    });
  }
  const pts = data.prediction.points;
  for (const p of pts) {
    model.push({
      t: new Date(p.timestamp),
      value: p.predicted,
      upper: p.upper,
      lower: p.lower,
      status: p.status,
      phase: "fore",
    });
  }
  return model;
}

function fillBand(ctx, model, from, to, x, y, color) {
  if (to - from < 2) return;
  ctx.beginPath();
  for (let i = from; i < to; i++) ctx.lineTo(x(i), y(model[i].upper));
  for (let i = to - 1; i >= from; i--) ctx.lineTo(x(i), y(model[i].lower));
  ctx.closePath();
  ctx.fillStyle = color;
  ctx.fill();
}

function drawPolyline(ctx, model, x, y, pick, from, to, color, width, dash) {
  if (to - from < 2) return;
  ctx.beginPath();
  for (let i = from; i < to; i++) {
    const px = x(i);
    const py = y(pick(model[i]));
    if (i === from) ctx.moveTo(px, py);
    else ctx.lineTo(px, py);
  }
  ctx.strokeStyle = color;
  ctx.lineWidth = width;
  ctx.setLineDash(dash);
  ctx.stroke();
  ctx.setLineDash([]);
}

function worstStatus(a, b) {
  if (a === "ALERT" || b === "ALERT") return "ALERT";
  if (a === "WARNING" || b === "WARNING") return "WARNING";
  return "NORMAL";
}

function statusSymbol(s) {
  if (s === "NORMAL") return "✓ Dentro de límites";
  if (s === "WARNING") return "▲ Cercano a límites";
  return "✕ Fuera de límites";
}

function rowTT(label, value, cls = "") {
  return `<div class="tt-row"><span class="tt-label">${label}</span><span class="mono ${cls || "tt-value"}">${value}</span></div>`;
}

function niceTicks(min, max, targetCount) {
  const range = max - min;
  if (range <= 0) return [min];
  const rough = range / Math.max(1, targetCount - 1);
  const mag = Math.pow(10, Math.floor(Math.log10(rough)));
  const norm = rough / mag;
  const step = (norm <= 1 ? 1 : norm <= 2 ? 2 : norm <= 2.5 ? 2.5 : norm <= 5 ? 5 : 10) * mag;
  const ticks = [];
  for (let v = Math.ceil(min / step) * step; v <= max + 1e-9; v += step) ticks.push(Number(v.toFixed(6)));
  return ticks;
}

function pad2(n) { return String(n).padStart(2, "0"); }

function formatTime(d) {
  return `${pad2(d.getDate())}/${pad2(d.getMonth() + 1)} ${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
}

function formatAxisTime(d) {
  return `${pad2(d.getMonth() + 1)}-${pad2(d.getDate())} ${pad2(d.getHours())}:00`;
}