from __future__ import annotations

import asyncio
import time

import numpy as np

from app.providers.yahoo import YahooProvider


PROXIES = {
    "DXY": "DX-Y.NYB",
    "US10Y": "^TNX",
    "VIX": "^VIX",
    "SPY": "SPY",
    "QQQ": "QQQ",
    "GOLD": "GC=F",
}

_PROXY_CACHE: tuple[float, dict[str, float]] | None = None
_PROXY_LOCK = asyncio.Lock()
_PROXY_TTL_SECONDS = 90


def _return_score(frame, lookback: int = 20) -> float:
    if frame is None or len(frame) <= lookback:
        return 0.0
    r = float(frame["close"].iloc[-1] / frame["close"].iloc[-lookback] - 1)
    return float(np.clip(r * 400, -100, 100))


async def _load_proxy_scores(provider: YahooProvider) -> dict[str, float]:
    global _PROXY_CACHE

    now = time.monotonic()
    if _PROXY_CACHE and now - _PROXY_CACHE[0] < _PROXY_TTL_SECONDS:
        return _PROXY_CACHE[1].copy()

    async with _PROXY_LOCK:
        now = time.monotonic()
        if _PROXY_CACHE and now - _PROXY_CACHE[0] < _PROXY_TTL_SECONDS:
            return _PROXY_CACHE[1].copy()

        async def get(name: str, ticker: str):
            try:
                frame = await provider.candles(ticker, "1d", "6mo")
                return name, _return_score(frame)
            except Exception:
                return name, 0.0

        pairs = await asyncio.gather(*(get(name, ticker) for name, ticker in PROXIES.items()))
        scores = dict(pairs)
        _PROXY_CACHE = (time.monotonic(), scores)
        return scores.copy()


def _score_symbol(symbol: str, scores: dict[str, float]) -> dict:
    upper = symbol.upper()
    is_crypto = upper.endswith("-USD") and upper.split("-")[0] in {
        "BTC", "ETH", "SOL", "XRP", "ADA", "DOGE", "BNB"
    }
    is_gold = "GC=" in upper or "XAU" in upper or "GOLD" in upper

    if is_crypto:
        raw = (
            0.30 * scores["QQQ"]
            + 0.20 * scores["SPY"]
            - 0.20 * scores["DXY"]
            - 0.15 * scores["US10Y"]
            - 0.15 * scores["VIX"]
        )
    elif is_gold:
        raw = (
            -0.35 * scores["DXY"]
            - 0.25 * scores["US10Y"]
            - 0.15 * scores["SPY"]
            + 0.25 * scores["VIX"]
        )
    else:
        raw = (
            0.40 * scores["SPY"]
            + 0.30 * scores["QQQ"]
            - 0.15 * scores["US10Y"]
            - 0.15 * scores["VIX"]
        )

    raw = float(np.clip(raw, -100, 100))
    return {
        "score": round(raw, 2),
        "label": "favorable" if raw >= 15 else "adverso" if raw <= -15 else "neutral",
        "proxies": {key: round(value, 2) for key, value in scores.items()},
        "note": (
            "Proxy macro de mercado basado en DXY, US10Y, VIX, SPY, QQQ y oro; "
            "snapshot compartido en caché para reducir consultas. No sustituye "
            "datos oficiales de bancos centrales."
        ),
    }


async def analyze_macro(provider: YahooProvider, symbol: str) -> dict:
    scores = await _load_proxy_scores(provider)
    return _score_symbol(symbol, scores)
