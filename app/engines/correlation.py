from __future__ import annotations

import asyncio

import pandas as pd

from app.providers.yahoo import YahooProvider


BENCHMARKS = {
    "SPY": "S&P 500 ETF",
    "QQQ": "Nasdaq 100 ETF",
    "^VIX": "VIX",
    "DX-Y.NYB": "Índice dólar (DXY)",
    "^TNX": "Treasury US 10Y",
    "GC=F": "Oro",
    "BTC-USD": "Bitcoin",
}


def _daily_returns(frame: pd.DataFrame, name: str) -> pd.Series:
    """Return daily returns indexed by normalized UTC calendar date.

    Yahoo daily candles for crypto and exchange-traded assets can carry
    different UTC times for the same trading date. Normalizing timestamps to
    midnight avoids losing otherwise valid overlapping observations.
    """
    if frame.empty:
        return pd.Series(dtype=float, name=name)
    data = frame[["timestamp", "close"]].dropna().copy()
    timestamps = pd.to_datetime(data["timestamp"], utc=True).dt.normalize()
    series = pd.Series(data["close"].to_numpy(), index=timestamps, name=name)
    series = series[~series.index.duplicated(keep="last")].sort_index()
    return series.pct_change(fill_method=None).dropna()


def _interpret(value: float) -> str:
    magnitude = abs(value)
    direction = "positiva" if value > 0 else "negativa" if value < 0 else "neutral"
    if magnitude >= 0.75:
        strength = "muy alta"
    elif magnitude >= 0.55:
        strength = "alta"
    elif magnitude >= 0.30:
        strength = "moderada"
    elif magnitude >= 0.15:
        strength = "débil"
    else:
        return "Prácticamente neutral"
    return f"{direction.capitalize()} {strength}"


async def correlations(provider: YahooProvider, symbol: str) -> dict:
    symbol = symbol.upper()
    tickers = [ticker for ticker in BENCHMARKS if ticker.upper() != symbol]
    semaphore = asyncio.Semaphore(3)

    async def load(ticker: str):
        try:
            async with semaphore:
                frame = await provider.candles(ticker, "1d", "1y")
            return ticker, _daily_returns(frame, ticker), None
        except Exception as exc:
            return ticker, None, str(exc)

    base_frame = await provider.candles(symbol, "1d", "1y")
    base = _daily_returns(base_frame, symbol)
    loaded = await asyncio.gather(*(load(ticker) for ticker in tickers))

    items: list[dict] = []
    unavailable: list[dict] = []

    for ticker, series, error in loaded:
        if series is None or series.empty:
            unavailable.append({"symbol": ticker, "name": BENCHMARKS[ticker], "reason": error or "Sin datos"})
            continue

        pair = pd.concat([base, series], axis=1, join="inner").dropna()
        if len(pair) < 30:
            unavailable.append(
                {
                    "symbol": ticker,
                    "name": BENCHMARKS[ticker],
                    "reason": f"Muestra insuficiente ({len(pair)} observaciones coincidentes)",
                }
            )
            continue

        value = float(pair.corr().iloc[0, 1])
        if pd.isna(value):
            unavailable.append({"symbol": ticker, "name": BENCHMARKS[ticker], "reason": "Correlación no definida"})
            continue

        rounded = round(value, 3)
        items.append(
            {
                "symbol": ticker,
                "name": BENCHMARKS[ticker],
                "value": rounded,
                "interpretation": _interpret(rounded),
                "data_points": int(len(pair)),
            }
        )

    items.sort(key=lambda item: abs(item["value"]), reverse=True)
    return {
        "window": "1 año",
        "basis": "Retornos diarios; fechas normalizadas a UTC",
        "items": items,
        "unavailable": unavailable,
    }
