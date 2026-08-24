function n(v) {
  const x = Number(v);
  return Number.isFinite(x) ? x : null;
}

function fmt(v) {
  const x = n(v);
  if (x === null) return "—";
  const abs = Math.abs(x);
  const digits = abs >= 1000 ? 2 : abs >= 1 ? 4 : 6;
  return x.toLocaleString("es-CR", {maximumFractionDigits: digits});
}

function levelList(payload, risk) {
  const raw = [
    ["Entrada", risk && risk.entry, "#5aa7ff", []],
    ["Stop", risk && risk.stop_loss, "#fb7185", [6, 4]],
    ["TP1", risk && risk.take_profit_1, "#34d399", [6, 4]],
    ["TP2", risk && risk.take_profit_2, "#70e1b5", [3, 4]],
    ["Soporte", payload && payload.support, "#fbbf24", [2, 4]],
    ["Resistencia", payload && payload.resistance, "#c084fc", [2, 4]],
  ];
  return raw
    .map(function(item) {
      return {label:item[0], value:n(item[1]), color:item[2], dash:item[3]};
    })
    .filter(function(item) { return item.value !== null; });
}

export function renderCandlestickChart(canvas, payload, risk) {
  risk = risk || {};
  if (!canvas || !payload || !payload.candles || !payload.candles.length) return;
  const rect = canvas.getBoundingClientRect();
  const dpr = Math.max(1, window.devicePixelRatio || 1);
  canvas.width = Math.floor(rect.width * dpr);
  canvas.height = Math.floor(rect.height * dpr);
  const ctx = canvas.getContext("2d");
  ctx.scale(dpr, dpr);

  const width = rect.width;
  const height = rect.height;
  const margin = {top:18, right:86, bottom:28, left:12};
  const plotW = width - margin.left - margin.right;
  const plotH = height - margin.top - margin.bottom;
  const candles = payload.candles;
  const levels = levelList(payload, risk);

  const prices = [];
  candles.forEach(function(c) {
    [c.low, c.high].forEach(function(v) {
      const value = n(v);
      if (value !== null) prices.push(value);
    });
  });
  levels.forEach(function(level) { prices.push(level.value); });

  let min = Math.min.apply(null, prices);
  let max = Math.max.apply(null, prices);
  const span = Math.max(max - min, Math.abs(max || 1) * 0.01);
  min -= span * 0.08;
  max += span * 0.08;

  const y = function(value) {
    return margin.top + ((max - value) / (max - min)) * plotH;
  };
  const slot = plotW / candles.length;
  const bodyW = Math.max(2, Math.min(9, slot * 0.62));

  ctx.fillStyle = "#08121f";
  ctx.fillRect(0, 0, width, height);
  ctx.font = "11px system-ui, sans-serif";
  ctx.textBaseline = "middle";
  ctx.strokeStyle = "#1c2b40";
  ctx.fillStyle = "#91a6bf";
  ctx.lineWidth = 1;

  for (let i = 0; i <= 5; i += 1) {
    const yy = margin.top + (plotH / 5) * i;
    const value = max - ((max - min) / 5) * i;
    ctx.beginPath();
    ctx.moveTo(margin.left, yy);
    ctx.lineTo(width - margin.right, yy);
    ctx.stroke();
    ctx.fillText(fmt(value), width - margin.right + 8, yy);
  }

  candles.forEach(function(c, i) {
    const open = n(c.open), high = n(c.high), low = n(c.low), close = n(c.close);
    if ([open, high, low, close].some(function(v) { return v === null; })) return;
    const x = margin.left + slot * i + slot / 2;
    const up = close >= open;
    const color = up ? "#34d399" : "#fb7185";
    ctx.strokeStyle = color;
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.moveTo(x, y(high));
    ctx.lineTo(x, y(low));
    ctx.stroke();
    const top = Math.min(y(open), y(close));
    const h = Math.max(1.5, Math.abs(y(open) - y(close)));
    ctx.fillRect(x - bodyW / 2, top, bodyW, h);
  });

  levels.forEach(function(level) {
    const yy = y(level.value);
    ctx.save();
    ctx.strokeStyle = level.color;
    ctx.fillStyle = level.color;
    ctx.lineWidth = 1.2;
    ctx.setLineDash(level.dash);
    ctx.beginPath();
    ctx.moveTo(margin.left, yy);
    ctx.lineTo(width - margin.right, yy);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.font = "10px system-ui, sans-serif";
    ctx.fillText(level.label + " " + fmt(level.value), margin.left + 6, Math.max(9, yy - 8));
    ctx.restore();
  });

  const first = new Date(candles[0].timestamp);
  const last = new Date(candles[candles.length - 1].timestamp);
  ctx.fillStyle = "#91a6bf";
  ctx.font = "10px system-ui, sans-serif";
  ctx.textBaseline = "alphabetic";
  ctx.fillText(first.toLocaleDateString("es-CR"), margin.left, height - 8);
  const lastText = last.toLocaleDateString("es-CR");
  const lastWidth = ctx.measureText(lastText).width;
  ctx.fillText(lastText, width - margin.right - lastWidth, height - 8);
}

export function renderLegend(container, payload, risk) {
  risk = risk || {};
  if (!container) return;
  const levels = levelList(payload, risk);
  container.innerHTML = levels.map(function(level) {
    return '<span class="legend-item" style="color:' + level.color + '"><span class="legend-dot"></span>' +
      level.label + ': ' + fmt(level.value) + '</span>';
  }).join("");
}
