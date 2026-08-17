from __future__ import annotations

import asyncio
import pandas as pd
from app.providers.yahoo import YahooProvider

BENCHMARKS = ["SPY", "QQQ", "^VIX", "DX-Y.NYB", "^TNX", "GC=F", "BTC-USD"]


async def correlations(provider: YahooProvider, symbol: str) -> dict[str, float]:
    tickers = [t for t in BENCHMARKS if t.upper() != symbol.upper()]
    async def load(ticker: str):
        try:
            df = await provider.candles(ticker, "1d", "1y")
            return df.set_index("timestamp")["close"].pct_change().dropna().rename(ticker)
        except Exception:
            return None
    base_df = await provider.candles(symbol, "1d", "1y")
    base = base_df.set_index("timestamp")["close"].pct_change().dropna().rename(symbol)
    others = await asyncio.gather(*(load(t) for t in tickers))
    data = [base] + [s for s in others if s is not None]
    if len(data) < 2:
        return {}
    merged = pd.concat(data, axis=1).dropna(how="all")
    corr = merged.corr()[symbol].drop(labels=[symbol]).dropna()
    return {k: round(float(v), 3) for k, v in corr.items()}
