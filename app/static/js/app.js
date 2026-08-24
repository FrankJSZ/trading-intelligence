import * as API from "./api.js";
import {renderCandlestickChart, renderLegend} from "./chart.js";

const $ = function(id) { return document.getElementById(id); };
const state = {
  analysis: null,
  chart: null,
  chartTf: "1D",
  busy: false,
  nextRefreshAt: null,
  refreshTimer: null,
  countdownTimer: null,
};

function esc(value) {
  return String(value == null ? "" : value).replace(/[&<>'"]/g, function(c) {
    return {"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[c];
  });
}

function fmt(value, digits) {
  if (digits === undefined) digits = 4;
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  return Number(value).toLocaleString("es-CR", {maximumFractionDigits: digits});
}

function pct(value, digits) {
  if (digits === undefined) digits = 2;
  return value === null || value === undefined ? "—" : fmt(value, digits) + "%";
}

function signedPct(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return null;
  const number = Number(value);
  return (number > 0 ? "+" : "") + number.toLocaleString("es-CR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }) + "%";
}

function decisionClass(value) {
  return value === "COMPRAR" ? "buy" : value === "VENDER" ? "sell" : "wait";
}

function scoreClass(value) {
  const number = Number(value);
  return number > 15 ? "buy" : number < -15 ? "sell" : "wait";
}

function safeUrl(value) {
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) ? url.href : "#";
  } catch {
    return "#";
  }
}

function mini(label, value, sub, kind) {
  let html = '<div class="mini"><div class="label">' + esc(label) + '</div><strong>' + esc(value) + '</strong>';
  if (sub) html += '<span class="risk-sub ' + esc(kind || "") + '">' + esc(sub) + ' desde entrada</span>';
  return html + "</div>";
}

function riskMini(label, price, percent, kind) {
  return mini(label, fmt(price, 6), signedPct(percent), kind);
}

function scoreCard(name, component, description) {
  const score = Number(component && component.score || 0);
  const details = component && component.details || {};
  const weight = Number(details.directional_weight || 0);
  const width = Math.min(50, Math.abs(score) / 2);
  const style = score >= 0
    ? "left:50%;width:" + width + "%;background:var(--good)"
    : "right:50%;width:" + width + "%;background:var(--bad)";
  const weightText = weight > 0
    ? "Peso direccional " + Math.round(weight * 100) + "%"
    : "Informativo / filtro · peso direccional 0%";
  return '<div class="card score-card">' +
    '<div class="score-top"><div><div class="label">' + esc(name) + '</div>' +
    '<div class="score ' + scoreClass(score) + '">' + (score > 0 ? "+" : "") + fmt(score, 1) + '</div></div>' +
    '<span class="badge ' + scoreClass(score) + '">' + esc(component && component.label || "neutral") + '</span></div>' +
    '<div><div class="track"><span class="fill" style="' + style + '"></span></div>' +
    '<div class="weight-note">' + esc(weightText) + '</div>' +
    (description ? '<div class="kicker">' + esc(description) + '</div>' : "") +
    '</div></div>';
}

function formPayload() {
  return {
    symbol: $("symbol").value,
    capital: Number($("capital").value),
    risk_profile: $("profile").value,
    psychology: {
      fomo: $("fomo").checked,
      confirmation_bias: $("confirm").checked,
      revenge_trading: $("revenge").checked,
      overconfidence: $("overconf").checked,
      fear_level: Number($("fear").value),
      greed_level: Number($("greed").value),
      discipline_level: Number($("discipline").value),
    },
  };
}

function showError(message) {
  $("error").textContent = message;
  $("error").style.display = "block";
}

function setLoading(active, auto) {
  state.busy = active;
  $("loading").classList.toggle("show", active);
  $("loadingText").textContent = auto
    ? "Actualizando automáticamente los datos…"
    : "Consultando mercado y ejecutando los motores…";
  $("analyze").disabled = active;
  $("analyze").textContent = active ? "Analizando…" : "Analizar ahora";
}

function renderAnalysis(data) {
  state.analysis = data;
  $("result").hidden = false;
  $("heroSymbol").textContent = data.symbol;

  $("marketDecision").textContent = data.market_decision;
  $("marketDecision").className = "decision " + decisionClass(data.market_decision);
  $("executionDecision").textContent = data.decision;
  $("executionDecision").className = decisionClass(data.decision);
  $("executionStatus").textContent = data.execution_status.replaceAll("_", " ");

  let explanation = "Confluencia insuficiente; el mercado no ofrece una ventaja clara.";
  if (data.market_decision === "COMPRAR") explanation = "La evidencia de mercado es alcista.";
  if (data.market_decision === "VENDER") explanation = "La evidencia de mercado es bajista.";
  if (data.market_decision !== data.decision) {
    explanation += " La ejecución está bloqueada por el filtro psicológico.";
  }
  $("marketExplanation").textContent = explanation;

  $("confidence").textContent = pct(data.confidence, 0);
  $("score").textContent = (Number(data.institutional_score) > 0 ? "+" : "") + fmt(data.institutional_score, 1);
  $("price").textContent = fmt(data.price, 6);
  $("heroRR").textContent = data.risk.risk_reward ? "1 : " + fmt(data.risk.risk_reward, 1) : "—";
  $("generatedAt").textContent = "Datos " + new Date(data.generated_at).toLocaleString("es-CR");

  $("components").innerHTML =
    scoreCard("Técnico", data.technical, "Estructura y momentum multitemporal.") +
    scoreCard("Macro", data.fundamental_macro, "Contexto de activos de riesgo y tasas.") +
    scoreCard("Noticias", data.news, "Eventos ponderados por relevancia, actualidad y fuente.") +
    scoreCard("Sentimiento", data.sentiment, "Derivado de titulares; visible, pero sin doble conteo.") +
    scoreCard("Psicología", data.psychology, "Filtro de ejecución, no dirección de mercado.");

  const risk = data.risk || {};
  $("risk").innerHTML =
    mini("Entrada", fmt(risk.entry, 6)) +
    riskMini("Stop Loss", risk.stop_loss, risk.stop_loss_percent, "sl") +
    riskMini("TP1", risk.take_profit_1, risk.take_profit_1_percent, "tp") +
    riskMini("TP2", risk.take_profit_2, risk.take_profit_2_percent, "tp") +
    mini("R:R", risk.risk_reward ? "1 : " + fmt(risk.risk_reward, 1) : "—") +
    mini("Capital en riesgo", pct(risk.risk_percent, 2)) +
    mini("Pérdida máxima", "$" + fmt(risk.max_loss, 2)) +
    mini("Tamaño teórico", fmt(risk.position_size, 6));
  $("riskBadge").textContent = "Máx. " + pct(risk.risk_percent, 2);

  $("regime").innerHTML =
    '<div class="metric-value">' + esc(data.market_regime) + '</div>' +
    '<p class="kicker">Régimen detectado por estructura, tendencia y volatilidad.</p>' +
    mini("Probabilidad histórica", data.historical_probability == null ? "Muestra insuficiente" : pct(data.historical_probability, 1));

  const rationaleNames = {
    technical:"Técnico",
    fundamental:"Fundamental / Macro",
    news:"Noticias",
    sentiment:"Sentimiento informativo",
    psychological:"Psicología / ejecución",
  };
  $("rationale").innerHTML = Object.entries(data.rationale || {}).map(function(entry) {
    return '<div class="rationale-item"><strong>' + esc(rationaleNames[entry[0]] || entry[0]) +
      '</strong><p class="kicker">' + esc(entry[1]) + '</p></div>';
  }).join("");

  $("warnings").innerHTML = (data.warnings || []).map(function(warning) {
    return '<div class="warning">⚠ ' + esc(warning) + '</div>';
  }).join("");
  $("alternative").textContent = data.alternative_scenario;

  const timeframes = data.technical.details.timeframes || {};
  $("timeframes").innerHTML =
    '<table><thead><tr><th>TF</th><th>Score</th><th>Tendencia</th><th>RSI</th><th>ADX</th><th>Soporte</th><th>Resistencia</th></tr></thead><tbody>' +
    Object.entries(timeframes).map(function(entry) {
      const name = entry[0], value = entry[1];
      return '<tr><td><strong>' + esc(name) + '</strong></td>' +
        '<td class="' + scoreClass(value.score) + '">' + (Number(value.score) > 0 ? "+" : "") + fmt(value.score, 1) + '</td>' +
        '<td>' + esc(value.label) + '</td><td>' + fmt(value.rsi, 1) + '</td><td>' + fmt(value.adx, 1) + '</td>' +
        '<td>' + fmt(value.support, 6) + '</td><td>' + fmt(value.resistance, 6) + '</td></tr>';
    }).join("") + '</tbody></table>';

  const articles = data.news.details.articles || [];
  $("newsCount").textContent = articles.length + " noticia" + (articles.length === 1 ? "" : "s");
  $("news").innerHTML = articles.length ? articles.map(function(article) {
    const link = safeUrl(article.link);
    const title = esc(article.title || "Sin título");
    const titleHtml = link === "#"
      ? "<strong>" + title + "</strong>"
      : '<a href="' + esc(link) + '" target="_blank" rel="noopener noreferrer">' + title + "</a>";
    return '<article class="news"><div>' + titleHtml + '</div><div class="meta">' +
      '<span>' + esc(article.publisher || "Fuente") + '</span>' +
      '<span class="badge">' + esc(article.relevance || "—") + '</span>' +
      '<span class="badge ' + scoreClass(Number(article.sentiment || 0) * 100) + '">Sent. ' + fmt(article.sentiment, 2) + '</span>' +
      (article.translated ? '<span class="badge">ES</span>' : "") +
      '</div></article>';
  }).join("") : '<div class="empty">Sin noticias disponibles.</div>';
}

async function loadChart(timeframe) {
  if (!state.analysis) return;
  state.chartTf = timeframe || state.chartTf;
  Array.from(document.querySelectorAll("#tfButtons button")).forEach(function(button) {
    button.classList.toggle("active", button.dataset.tf === state.chartTf);
  });
  try {
    const data = await API.chart(state.analysis.symbol, state.chartTf, 120);
    state.chart = data;
    renderCandlestickChart($("priceChart"), data, state.analysis.risk);
    renderLegend($("chartLegend"), data, state.analysis.risk);
  } catch (error) {
    $("chartLegend").textContent = "No se pudo cargar el gráfico: " + error.message;
  }
}

async function analyzeNow(auto) {
  if (state.busy) return;
  $("error").style.display = "none";
  setLoading(true, auto);
  try {
    const data = await API.analyze(formPayload());
    renderAnalysis(data);
    $("lastUpdate").textContent = new Date().toLocaleTimeString("es-CR", {
      hour:"2-digit", minute:"2-digit", second:"2-digit"
    });
    await loadChart(state.chartTf);
    loadHistory();
  } catch (error) {
    showError(error.message);
  } finally {
    setLoading(false, auto);
    scheduleAuto();
  }
}

function intervalMs() {
  return Number($("refreshInterval").value) * 60 * 1000;
}

function formatCountdown(ms) {
  if (ms <= 0) return "00:00";
  const total = Math.ceil(ms / 1000);
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return String(minutes).padStart(2, "0") + ":" + String(seconds).padStart(2, "0");
}

function updateAutoUi() {
  const enabled = $("autoRefresh").checked;
  const minutes = $("refreshInterval").value;
  $("autoBadge").textContent = enabled ? "Auto · " + minutes + " min" : "Auto desactivado";
  $("nextUpdate").textContent = enabled && state.nextRefreshAt
    ? formatCountdown(state.nextRefreshAt - Date.now())
    : "—";
}

function scheduleAuto() {
  clearTimeout(state.refreshTimer);
  state.nextRefreshAt = null;
  updateAutoUi();
  if (!$("autoRefresh").checked) return;
  state.nextRefreshAt = Date.now() + intervalMs();
  state.refreshTimer = setTimeout(async function() {
    if (document.hidden) {
      scheduleAuto();
      return;
    }
    await analyzeNow(true);
  }, intervalMs());
  updateAutoUi();
}

function startCountdown() {
  clearInterval(state.countdownTimer);
  state.countdownTimer = setInterval(function() {
    if ($("autoRefresh").checked && state.nextRefreshAt && Date.now() >= state.nextRefreshAt && !state.busy) {
      $("nextUpdate").textContent = "Actualizando…";
    } else {
      updateAutoUi();
    }
  }, 1000);
}

function watchSymbols() {
  return Array.from(document.querySelectorAll('input[name="watch"]:checked')).map(function(input) {
    return input.value;
  }).slice(0, 8);
}

async function loadWatchlist() {
  const button = $("loadWatchlist");
  const symbols = watchSymbols();
  if (!symbols.length) {
    $("watchlist").innerHTML = '<div class="empty">Selecciona al menos un activo.</div>';
    return;
  }
  button.disabled = true;
  button.textContent = "Analizando…";
  $("watchlist").innerHTML = '<div class="placeholder"><span class="spinner"></span></div>';
  try {
    const data = await API.watchlist({
      symbols: symbols,
      capital: Number($("capital").value),
      risk_profile: $("profile").value,
    });
    const items = data.items || [];
    if (!items.length) {
      $("watchlist").innerHTML = '<div class="empty">No se pudieron analizar los activos seleccionados.</div>';
      return;
    }
    $("watchlist").innerHTML =
      '<div class="table-wrap"><table><thead><tr><th>Activo</th><th>Mercado</th><th>Operativa</th><th>Conf.</th><th>Score</th><th>Técnico</th><th>Macro</th><th>Noticias</th><th>Régimen</th></tr></thead><tbody>' +
      items.map(function(item) {
        return '<tr data-watch-symbol="' + esc(item.symbol) + '"><td><strong>' + esc(item.symbol) + '</strong><br><span class="kicker">' + fmt(item.price, 6) + '</span></td>' +
          '<td class="' + decisionClass(item.market_decision) + '">' + esc(item.market_decision) + '</td>' +
          '<td class="' + decisionClass(item.decision) + '">' + esc(item.decision) + '</td>' +
          '<td>' + pct(item.confidence, 0) + '</td><td class="' + scoreClass(item.institutional_score) + '">' + (Number(item.institutional_score) > 0 ? "+" : "") + fmt(item.institutional_score, 1) + '</td>' +
          '<td>' + fmt(item.technical_score, 1) + '</td><td>' + fmt(item.macro_score, 1) + '</td><td>' + fmt(item.news_score, 1) + '</td><td>' + esc(item.regime) + '</td></tr>';
      }).join("") + '</tbody></table></div>' +
      ((data.errors || []).length ? '<p class="kicker">' + data.errors.length + ' activo(s) no disponible(s).</p>' : "");
    Array.from(document.querySelectorAll("[data-watch-symbol]")).forEach(function(row) {
      row.style.cursor = "pointer";
      row.addEventListener("click", function() {
        const symbol = row.dataset.watchSymbol;
        const option = Array.from($("symbol").options).find(function(o) { return o.value === symbol; });
        if (option) {
          $("symbol").value = symbol;
          analyzeNow(false);
          window.scrollTo({top:0, behavior:"smooth"});
        }
      });
    });
  } catch (error) {
    $("watchlist").innerHTML = '<div class="empty">' + esc(error.message) + '</div>';
  } finally {
    button.disabled = false;
    button.textContent = "Actualizar watchlist";
  }
}

async function loadHistory() {
  try {
    const data = await API.history("", 50);
    const items = data.items || [];
    if (!items.length) {
      $("history").innerHTML = '<div class="empty">Aún no hay análisis guardados.</div>';
      return;
    }
    $("history").innerHTML =
      '<div class="table-wrap"><table><thead><tr><th>Fecha</th><th>Activo</th><th>Mercado</th><th>Operativa</th><th>Conf.</th><th>Score</th><th>Precio</th><th>Entrada</th><th>SL</th><th>TP1</th></tr></thead><tbody>' +
      items.map(function(item) {
        return '<tr><td>' + esc(new Date(item.generated_at).toLocaleString("es-CR")) + '</td><td><strong>' + esc(item.symbol) + '</strong></td>' +
          '<td class="' + decisionClass(item.market_decision) + '">' + esc(item.market_decision) + '</td>' +
          '<td class="' + decisionClass(item.decision) + '">' + esc(item.decision) + '</td>' +
          '<td>' + pct(item.confidence, 0) + '</td><td class="' + scoreClass(item.institutional_score) + '">' + (Number(item.institutional_score) > 0 ? "+" : "") + fmt(item.institutional_score, 1) + '</td>' +
          '<td>' + fmt(item.price, 6) + '</td><td>' + fmt(item.entry, 6) + '</td><td>' + fmt(item.stop_loss, 6) + '</td><td>' + fmt(item.take_profit_1, 6) + '</td></tr>';
      }).join("") + '</tbody></table></div>';
  } catch (error) {
    $("history").innerHTML = '<div class="empty">' + esc(error.message) + '</div>';
  }
}

function assessBacktest(data) {
  if (data.error) return [data.error, "sell"];
  if (!data.trades) return ["Sin operaciones suficientes", "wait"];
  if (Number(data.profit_factor) >= 1.3 && Number(data.sharpe) >= 0.8) return ["Baseline históricamente favorable", "buy"];
  if (Number(data.profit_factor) >= 1.05) return ["Baseline marginal; requiere validación", "wait"];
  return ["Baseline débil; no usar como argumento de entrada", "sell"];
}

async function loadBacktest() {
  const button = $("loadBacktest");
  button.disabled = true;
  button.textContent = "Cargando…";
  $("backtest").innerHTML = '<div class="placeholder"><span class="spinner"></span></div>';
  try {
    const symbol = state.analysis ? state.analysis.symbol : $("symbol").value;
    const data = await API.backtest(symbol);
    if (data.error || !data.trades) {
      $("backtest").innerHTML = '<div class="empty">' + esc(data.error || "Sin operaciones suficientes.") + '</div>';
      return;
    }
    const assessment = assessBacktest(data);
    const metrics = [
      ["Trades", fmt(data.trades, 0)],
      ["Win rate", pct(data.win_rate)],
      ["Profit factor", fmt(data.profit_factor, 3)],
      ["Sharpe", fmt(data.sharpe, 3)],
      ["Max drawdown", pct(data.max_drawdown_pct)],
      ["Retorno total", pct(data.total_return_pct)],
      ["Retorno medio", pct(data.average_return_pct, 4)],
      ["Expectancy", pct(data.expectancy_pct, 4)],
    ];
    $("backtest").innerHTML =
      '<div class="summary"><div><div class="label">Lectura</div><strong>' + esc(assessment[0]) + '</strong></div><span class="badge ' + assessment[1] + '">' + esc(data.symbol) + '</span></div>' +
      '<div class="metric-grid">' + metrics.map(function(metric) { return mini(metric[0], metric[1]); }).join("") + '</div>' +
      '<p class="kicker">' + esc(data.note || "") + '</p>';
  } catch (error) {
    $("backtest").innerHTML = '<div class="empty">' + esc(error.message) + '</div>';
  } finally {
    button.disabled = false;
    button.textContent = "Cargar";
  }
}

async function loadCorr() {
  const button = $("loadCorr");
  button.disabled = true;
  button.textContent = "Cargando…";
  $("corr").innerHTML = '<div class="placeholder"><span class="spinner"></span></div>';
  try {
    const symbol = state.analysis ? state.analysis.symbol : $("symbol").value;
    const data = await API.correlations(symbol);
    const items = data.items || [];
    if (!items.length) {
      $("corr").innerHTML = '<div class="empty">No hay correlaciones suficientes.</div>';
      return;
    }
    const rows = items.map(function(item) {
      const value = Number(item.value);
      const width = Math.min(50, Math.abs(value) * 50);
      const style = value >= 0
        ? "left:50%;width:" + width + "%;background:var(--good)"
        : "right:50%;width:" + width + "%;background:var(--bad)";
      return '<div class="corr"><div><strong>' + esc(item.symbol) + '</strong><small>' + esc(item.name) + '</small></div>' +
        '<div><div class="corrbar"><span class="corrfill" style="' + style + '"></span></div><small>' + esc(item.interpretation) + ' · n=' + fmt(item.data_points, 0) + '</small></div>' +
        '<strong class="' + (value > 0 ? "buy" : value < 0 ? "sell" : "wait") + '">' + (value > 0 ? "+" : "") + fmt(value, 3) + '</strong></div>';
    }).join("");
    $("corr").innerHTML =
      '<div class="summary"><strong>' + esc(data.window || "1 año") + '</strong><span class="badge">' + items.length + ' calculadas</span></div>' +
      '<div class="corr-list">' + rows + '</div><p class="kicker">' + esc(data.basis || "Retornos diarios") + '</p>';
  } catch (error) {
    $("corr").innerHTML = '<div class="empty">' + esc(error.message) + '</div>';
  } finally {
    button.disabled = false;
    button.textContent = "Cargar";
  }
}

async function checkHealth() {
  try {
    const data = await API.health();
    $("apiDot").className = "dot ok";
    $("apiStatus").textContent = "API lista · v" + (data.version || "");
  } catch {
    $("apiDot").className = "dot bad";
    $("apiStatus").textContent = "API no disponible";
  }
}

["fear", "greed", "discipline"].forEach(function(id) {
  $(id).addEventListener("input", function() { $(id + "Value").textContent = $(id).value; });
});
$("analyze").addEventListener("click", function() { analyzeNow(false); });
$("autoRefresh").addEventListener("change", scheduleAuto);
$("refreshInterval").addEventListener("change", scheduleAuto);
$("symbol").addEventListener("change", scheduleAuto);
$("profile").addEventListener("change", scheduleAuto);
$("capital").addEventListener("change", scheduleAuto);
$("loadWatchlist").addEventListener("click", loadWatchlist);
$("loadHistory").addEventListener("click", loadHistory);
$("loadBacktest").addEventListener("click", loadBacktest);
$("loadCorr").addEventListener("click", loadCorr);
Array.from(document.querySelectorAll("#tfButtons button")).forEach(function(button) {
  button.addEventListener("click", function() { loadChart(button.dataset.tf); });
});
document.addEventListener("visibilitychange", function() {
  if (!document.hidden && $("autoRefresh").checked && state.nextRefreshAt && Date.now() >= state.nextRefreshAt) {
    analyzeNow(true);
  }
});
let resizeTimer = null;
window.addEventListener("resize", function() {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(function() {
    if (state.chart && state.analysis) {
      renderCandlestickChart($("priceChart"), state.chart, state.analysis.risk);
      renderLegend($("chartLegend"), state.chart, state.analysis.risk);
    }
  }, 120);
});

checkHealth();
startCountdown();
loadHistory();
analyzeNow(false);
