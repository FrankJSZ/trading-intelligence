const q = id => document.getElementById(id);

function esc(value) {
  return String(value == null ? "" : value).replace(/[&<>'"]/g, c => ({
    "&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"
  })[c]);
}

function fmt(value, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  return Number(value).toLocaleString("es-CR", {maximumFractionDigits: digits});
}

function pct(value, digits = 2) {
  return value === null || value === undefined ? "—" : fmt(value, digits) + "%";
}

function metric(label, value, note = "") {
  return '<div class="quant-metric"><div class="label">' + esc(label) + '</div><strong>' +
    esc(value) + '</strong>' + (note ? '<small>' + esc(note) + '</small>' : '') + '</div>';
}

async function request(url, options = {}) {
  const response = await fetch(url, options);
  let data;
  try { data = await response.json(); } catch { data = {detail: "Respuesta inválida"}; }
  if (!response.ok) throw new Error(data.detail || ("HTTP " + response.status));
  return data;
}

function injectStyles() {
  if (document.querySelector('link[data-quant-style]')) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = "/static/css/quant.css?v=30";
  link.dataset.quantStyle = "1";
  document.head.appendChild(link);
}

function injectLab() {
  if (q("quantLab")) return;
  const research = document.querySelector(".research.section");
  const section = document.createElement("section");
  section.id = "quantLab";
  section.className = "card section quant-lab";
  section.innerHTML = `
    <div class="head">
      <div>
        <h2>Laboratorio cuantitativo · Fase 3</h2>
        <p class="kicker">Backtest core, walk-forward, calibración empírica y Monte Carlo. Las noticias históricas se excluyen deliberadamente.</p>
      </div>
      <span class="badge">Quant Core v1</span>
    </div>
    <div class="quant-controls">
      <label class="field">Años
        <select id="quantYears"><option value="3">3 años</option><option value="4">4 años</option><option value="5" selected>5 años</option></select>
      </label>
      <label class="field">Riesgo por trade %<input id="quantRisk" type="number" min="0.25" max="2" step="0.25" value="1"></label>
      <label class="field">Comisión bps<input id="quantFee" type="number" min="0" max="100" step="1" value="10"></label>
      <label class="field">Slippage bps<input id="quantSlip" type="number" min="0" max="100" step="1" value="5"></label>
      <label class="field">Máx. barras<input id="quantHold" type="number" min="2" max="60" step="1" value="20"></label>
      <label class="field">Monte Carlo
        <select id="quantMc"><option value="500">500</option><option value="1000" selected>1 000</option><option value="2000">2 000</option><option value="5000">5 000</option></select>
      </label>
    </div>
    <div class="quant-actions" style="margin-top:10px">
      <label class="switch"><input id="quantWalk" type="checkbox" checked> Walk-forward</label>
      <button id="runQuant" class="primary">Ejecutar Fase 3</button>
      <button id="loadQuantRuns">Historial quant</button>
    </div>
    <div class="quant-note">El backtest usa señal al cierre y entrada en la apertura siguiente. Cuando SL y TP aparecen dentro de la misma vela sin secuencia intradía, se asume SL primero. Esto evita inflar resultados.</div>
    <div id="quantLoading" class="quant-loading"><span class="spinner"></span><span>Descargando histórico y ejecutando simulación…</span></div>
    <div id="quantError" class="error"></div>
    <div id="quantResult" class="placeholder" style="margin-top:12px">Ejecuta el laboratorio para medir el núcleo técnico + macro.</div>
    <div id="quantRuns" style="margin-top:12px"></div>
  `;
  if (research) research.parentNode.insertBefore(section, research);
  else document.querySelector(".footer")?.before(section);
}

function metricsHtml(data) {
  const m = data.metrics || {};
  return '<div class="quant-metrics">' +
    metric("Trades", fmt(m.trades, 0)) +
    metric("Win rate", pct(m.win_rate)) +
    metric("Expectancy", fmt(m.expectancy_r, 3) + " R") +
    metric("Profit factor", fmt(m.profit_factor, 3)) +
    metric("Retorno", pct(m.total_return_pct)) +
    metric("Max drawdown", pct(m.max_drawdown_pct)) +
    metric("Sharpe", fmt(m.sharpe, 3)) +
    metric("Sortino", fmt(m.sortino, 3)) +
    metric("Calmar", fmt(m.calmar, 3)) +
    metric("Capital final", "$" + fmt(m.ending_capital, 2)) +
    metric("TP1 hit", pct(m.tp1_hit_rate)) +
    metric("TP2 hit", pct(m.tp2_hit_rate)) +
    metric("MFE medio", fmt(m.average_mfe_r, 2) + " R") +
    metric("MAE medio", fmt(m.average_mae_r, 2) + " R") +
    metric("Holding medio", fmt(m.average_holding_bars, 1) + " barras") +
    '</div>';
}

function methodHtml(data) {
  const method = data.methodology || {};
  const entries = [
    ["Timing", method.signal_timing],
    ["Técnico", method.technical_core],
    ["Macro", method.macro_core],
    ["Noticias", method.news],
    ["Intrabar", method.intrabar_rule],
    ["Posición", method.position_rule],
    ["Confianza", method.confidence],
  ];
  return '<div class="quant-method">' + entries.map(([k,v]) =>
    '<div><strong>' + esc(k) + '</strong>' + esc(v || "—") + '</div>'
  ).join('') + '</div>';
}

function regimeTable(rows) {
  if (!rows || !rows.length) return '<div class="empty">Sin desglose por régimen.</div>';
  return '<div class="table-wrap"><table><thead><tr><th>Régimen</th><th>Trades</th><th>Win rate</th><th>Expectancy</th><th>PF</th></tr></thead><tbody>' +
    rows.map(r => '<tr><td>' + esc(r.regime) + '</td><td>' + fmt(r.trades,0) + '</td><td>' + pct(r.win_rate) + '</td><td>' + fmt(r.expectancy_r,3) + ' R</td><td>' + fmt(r.profit_factor,3) + '</td></tr>').join('') +
    '</tbody></table></div>';
}

function walkForwardTable(wf) {
  const rows = wf && wf.folds || [];
  if (!rows.length) return '<div class="empty">' + esc(wf && wf.note || "Sin walk-forward") + '</div>';
  return '<div class="table-wrap"><table><thead><tr><th>Fold</th><th>Test</th><th>Peso T/M</th><th>Umbral</th><th>Trades OOS</th><th>Win rate</th><th>Expectancy</th></tr></thead><tbody>' +
    rows.map(r => '<tr><td>' + fmt(r.fold,0) + '</td><td>' + esc(r.test_start) + ' → ' + esc(r.test_end) + '</td><td>' + Math.round(Number(r.tech_weight)*100) + '/' + Math.round(Number(r.macro_weight)*100) + '</td><td>' + fmt(r.threshold,0) + '</td><td>' + fmt(r.test_trades,0) + '</td><td>' + pct(r.test_win_rate) + '</td><td>' + fmt(r.test_expectancy_r,3) + ' R</td></tr>').join('') +
    '</tbody></table></div>';
}

function calibrationTable(calibration) {
  const rows = calibration && calibration.rows || [];
  if (!rows.length) return '<div class="empty">Muestra insuficiente para calibración.</div>';
  const warning = calibration.warning ? '<div class="quant-note">' + esc(calibration.warning) + '</div>' : '';
  return warning + '<div class="table-wrap"><table><thead><tr><th>Confianza heurística</th><th>n</th><th>Win observado</th><th>IC 95%</th><th>R medio</th></tr></thead><tbody>' +
    rows.map(r => '<tr><td>' + esc(r.confidence_band) + '</td><td>' + fmt(r.n,0) + '</td><td>' + pct(r.observed_win_rate) + '</td><td>' + pct(r.interval_low) + ' – ' + pct(r.interval_high) + '</td><td>' + fmt(r.mean_r,3) + ' R</td></tr>').join('') +
    '</tbody></table></div>';
}

function monteCarloHtml(mc) {
  if (!mc || !mc.runs) return '<div class="empty">' + esc(mc && mc.note || "Sin Monte Carlo") + '</div>';
  return '<div class="quant-metrics">' +
    metric("Simulaciones", fmt(mc.runs,0)) +
    metric("Capital P05", "$" + fmt(mc.ending_capital_p05,2)) +
    metric("Capital mediano", "$" + fmt(mc.ending_capital_median,2)) +
    metric("Capital P95", "$" + fmt(mc.ending_capital_p95,2)) +
    metric("DD P95", pct(mc.max_drawdown_p95)) +
    metric("P(DD ≥10%)", pct(mc.probability_drawdown_10pct)) +
    metric("P(DD ≥20%)", pct(mc.probability_drawdown_20pct)) +
    metric("Racha pérdidas P95", fmt(mc.loss_streak_p95,0)) +
    '</div><p class="kicker">Fuente: ' + esc(mc.source || "—") + '. ' + esc(mc.note || "") + '</p>';
}

function tradesTable(trades) {
  if (!trades || !trades.length) return '<div class="empty">No se generaron trades.</div>';
  return '<div class="table-wrap"><table><thead><tr><th>Entrada</th><th>Dir.</th><th>Score</th><th>Conf.</th><th>Régimen</th><th>Salida</th><th>R</th><th>MFE</th><th>MAE</th></tr></thead><tbody>' +
    trades.slice().reverse().map(t => '<tr><td>' + esc(new Date(t.entry_at).toLocaleDateString("es-CR")) + '</td><td>' + esc(t.direction) + '</td><td>' + fmt(t.market_score,1) + '</td><td>' + pct(t.confidence,0) + '</td><td>' + esc(t.regime) + '</td><td>' + esc(t.exit_reason) + '</td><td class="' + (Number(t.r_multiple)>0 ? 'buy' : 'sell') + '">' + fmt(t.r_multiple,3) + ' R</td><td>' + fmt(t.mfe_r,2) + '</td><td>' + fmt(t.mae_r,2) + '</td></tr>').join('') +
    '</tbody></table></div>';
}

function drawEquity(canvas, curve) {
  if (!canvas || !curve || curve.length < 2) return;
  const rect = canvas.getBoundingClientRect();
  const dpr = Math.max(1, window.devicePixelRatio || 1);
  canvas.width = Math.floor(rect.width * dpr);
  canvas.height = Math.floor(rect.height * dpr);
  const ctx = canvas.getContext("2d");
  ctx.scale(dpr,dpr);
  const w = rect.width, h = rect.height, pad = 28;
  const values = curve.map(p => Number(p.equity));
  let min = Math.min(...values), max = Math.max(...values);
  if (max === min) { max += 1; min -= 1; }
  ctx.fillStyle = "#07111c"; ctx.fillRect(0,0,w,h);
  ctx.strokeStyle = "#203650"; ctx.lineWidth = 1;
  for (let i=0;i<5;i++) {
    const y = pad + (h-pad*2)*i/4;
    ctx.beginPath(); ctx.moveTo(pad,y); ctx.lineTo(w-pad,y); ctx.stroke();
  }
  ctx.strokeStyle = "#5aa7ff"; ctx.lineWidth = 2; ctx.beginPath();
  curve.forEach((p,i) => {
    const x = pad + (w-pad*2) * i/(curve.length-1);
    const y = pad + (max-Number(p.equity))/(max-min)*(h-pad*2);
    if (i===0) ctx.moveTo(x,y); else ctx.lineTo(x,y);
  });
  ctx.stroke();
  ctx.fillStyle = "#91a6bf"; ctx.font = "10px system-ui";
  ctx.fillText("$" + fmt(max,0), 4, 12);
  ctx.fillText("$" + fmt(min,0), 4, h-8);
}

function renderResult(data) {
  const m = data.metrics || {};
  const wfMetrics = data.walk_forward && data.walk_forward.metrics || {};
  q("quantResult").className = "";
  q("quantResult").innerHTML = `
    <div class="summary"><div><div class="label">${esc(data.symbol)} · ${esc(data.version)}</div><strong>${esc(data.data.start)} → ${esc(data.data.end)}</strong></div><span class="badge">Run #${fmt(data.run_id,0)}</span></div>
    ${metricsHtml(data)}
    <div class="quant-status">
      <span class="badge">OOS trades ${fmt(wfMetrics.trades,0)}</span>
      <span class="badge">OOS expectancy ${fmt(wfMetrics.expectancy_r,3)} R</span>
      <span class="badge">Calibración ${esc(data.calibration && data.calibration.source || "—")}</span>
      <span class="badge">Noticias históricas excluidas</span>
    </div>
    <div class="quant-split">
      <div class="quant-panel"><h3>Equity curve</h3><div class="quant-equity"><canvas id="quantEquity"></canvas></div></div>
      <div class="quant-panel"><h3>Metodología</h3>${methodHtml(data)}</div>
    </div>
    <div class="quant-split">
      <div class="quant-panel"><h3>Desempeño por régimen</h3>${regimeTable(data.regimes)}</div>
      <div class="quant-panel"><h3>Calibración de confianza</h3>${calibrationTable(data.calibration)}</div>
    </div>
    <div class="quant-panel" style="margin-top:12px"><h3>Walk-forward fuera de muestra</h3>${walkForwardTable(data.walk_forward)}</div>
    <div class="quant-panel" style="margin-top:12px"><h3>Monte Carlo</h3>${monteCarloHtml(data.monte_carlo)}</div>
    <div class="quant-panel" style="margin-top:12px"><h3>Journal de trades · últimos ${Math.min((data.trades||[]).length,250)}</h3>${tradesTable(data.trades)}</div>
  `;
  requestAnimationFrame(() => drawEquity(q("quantEquity"), m.equity_curve || []));
}

async function runQuant() {
  const button = q("runQuant");
  const error = q("quantError");
  error.style.display = "none";
  q("quantLoading").classList.add("show");
  button.disabled = true;
  button.textContent = "Ejecutando…";
  try {
    const mainSymbol = q("symbol");
    const mainCapital = q("capital");
    const payload = {
      symbol: mainSymbol ? mainSymbol.value : "BTC-USD",
      capital: mainCapital ? Number(mainCapital.value) : 10000,
      risk_percent: Number(q("quantRisk").value),
      fee_bps: Number(q("quantFee").value),
      slippage_bps: Number(q("quantSlip").value),
      max_holding_bars: Number(q("quantHold").value),
      years: Number(q("quantYears").value),
      walk_forward: q("quantWalk").checked,
      monte_carlo_runs: Number(q("quantMc").value),
    };
    const data = await request("/api/quant/backtest", {
      method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload)
    });
    renderResult(data);
    await loadRuns();
  } catch (e) {
    error.textContent = e.message;
    error.style.display = "block";
  } finally {
    q("quantLoading").classList.remove("show");
    button.disabled = false;
    button.textContent = "Ejecutar Fase 3";
  }
}

async function loadRuns() {
  const container = q("quantRuns");
  if (!container) return;
  try {
    const symbol = q("symbol") ? q("symbol").value : "";
    const data = await request("/api/quant/runs?symbol=" + encodeURIComponent(symbol) + "&limit=8");
    const items = data.items || [];
    if (!items.length) { container.innerHTML = ""; return; }
    container.innerHTML = '<div class="quant-panel"><h3>Corridas cuantitativas recientes</h3><div class="quant-runs">' +
      items.map(item => '<div class="quant-run"><div><strong>#' + fmt(item.id,0) + ' · ' + esc(item.symbol) + '</strong><small>' + esc(new Date(item.generated_at).toLocaleString("es-CR")) + '</small></div><div><strong>' + fmt(item.metrics && item.metrics.expectancy_r,3) + ' R</strong><small>' + fmt(item.metrics && item.metrics.trades,0) + ' trades · DD ' + pct(item.metrics && item.metrics.max_drawdown_pct) + '</small></div></div>').join('') +
      '</div></div>';
  } catch (e) {
    container.innerHTML = '<div class="empty">No se pudo cargar el historial quant: ' + esc(e.message) + '</div>';
  }
}

function init() {
  injectStyles();
  injectLab();
  q("runQuant")?.addEventListener("click", runQuant);
  q("loadQuantRuns")?.addEventListener("click", loadRuns);
  loadRuns();
}

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
else init();
