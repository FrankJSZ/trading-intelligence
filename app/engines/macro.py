from __future__ import annotations

import asyncio
import numpy as np
from app.providers.yahoo import YahooProvider

PROXIES = {"DXY": "DX-Y.NYB", "US10Y": "^TNX", "VIX": "^VIX", "SPY": "SPY", "QQQ": "QQQ", "GOLD": "GC=F"}


def _return_score(frame, lookback: int = 20) -> float:
    if frame is None or len(frame) <= lookback:
        return 0.0
    r = float(frame["close"].iloc[-1] / frame["close"].iloc[-lookback] - 1)
    return float(np.clip(r * 400, -100, 100))


async def analyze_macro(provider: YahooProvider, symbol: str) -> dict:
    async def get(name: str, ticker: str):
        try:
            return name, await provider.candles(ticker, "1d", "6mo")
        except Exception:
            return name, None
    pairs = await asyncio.gather(*(get(name, ticker) for name, ticker in PROXIES.items()))
    frames = dict(pairs)
    scores = {name: _return_score(frame) for name, frame in frames.items()}
    upper = symbol.upper()
    is_crypto = upper.endswith("-USD") and upper.split("-")[0] in {"BTC", "ETH", "SOL", "XRP", "ADA", "DOGE"}
    is_gold = "GC=" in upper or "XAU" in upper or "GOLD" in upper
    if is_crypto:
        raw = 0.30 * scores["QQQ"] + 0.20 * scores["SPY"] - 0.20 * scores["DXY"] - 0.15 * scores["US10Y"] - 0.15 * scores["VIX"]
    elif is_gold:
        raw = -0.35 * scores["DXY"] - 0.25 * scores["US10Y"] - 0.15 * scores["SPY"] + 0.25 * scores["VIX"]
    else:
        raw = 0.40 * scores["SPY"] + 0.30 * scores["QQQ"] - 0.15 * scores["US10Y"] - 0.15 * scores["VIX"]
    raw = float(np.clip(raw, -100, 100))
    return {"score": round(raw, 2), "label": "favorable" if raw >= 15 else "adverso" if raw <= -15 else "neutral", "proxies": {k: round(v, 2) for k, v in scores.items()}, "note": "Proxy macro de mercado basado en DXY, US10Y, VIX, SPY, QQQ y oro; no sustituye datos oficiales de bancos centrales."}
