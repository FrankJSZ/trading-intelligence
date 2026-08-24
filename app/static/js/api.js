export async function request(url, options = {}) {
  const response = await fetch(url, options);
  let data;
  try {
    data = await response.json();
  } catch {
    data = {detail: "Respuesta inválida del servidor"};
  }
  if (!response.ok) throw new Error(data.detail || ("HTTP " + response.status));
  return data;
}

export function analyze(payload) {
  return request("/api/analyze", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload),
  });
}

export function chart(symbol, timeframe = "1D", limit = 120) {
  return request("/api/chart/" + encodeURIComponent(symbol) + "?timeframe=" + encodeURIComponent(timeframe) + "&limit=" + limit);
}

export function watchlist(payload) {
  return request("/api/watchlist", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload),
  });
}

export function history(symbol = "", limit = 50) {
  const query = new URLSearchParams({limit: String(limit)});
  if (symbol) query.set("symbol", symbol);
  return request("/api/history?" + query.toString());
}

export function backtest(symbol) {
  return request("/api/backtest/" + encodeURIComponent(symbol));
}

export function correlations(symbol) {
  return request("/api/correlations/" + encodeURIComponent(symbol));
}

export function health() {
  return request("/api/health");
}
