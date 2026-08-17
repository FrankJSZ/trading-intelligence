from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from urllib.parse import quote

import httpx
import pandas as pd


class YahooProvider:
    """Keyless Yahoo Finance provider for market candles and headlines."""

    BASE_CHART = "https://query1.finance.yahoo.com/v8/finance/chart"
    SEARCH = "https://query1.finance.yahoo.com/v1/finance/search"

    def __init__(self, timeout: float = 15.0):
        self.timeout = timeout
        self.headers = {
            "User-Agent": "Mozilla/5.0 TradingIntelligence/1.0",
            "Accept": "application/json,text/plain,*/*",
        }

    async def candles(self, symbol: str, interval: str, range_: str) -> pd.DataFrame:
        url = f"{self.BASE_CHART}/{quote(symbol, safe='')}"
        params = {"interval": interval, "range": range_, "includePrePost": "false"}
        async with httpx.AsyncClient(timeout=self.timeout, headers=self.headers) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()

        result = payload.get("chart", {}).get("result")
        if not result:
            error = payload.get("chart", {}).get("error") or "No data returned"
            raise ValueError(f"Yahoo market data unavailable for {symbol}: {error}")

        block = result[0]
        ts = block.get("timestamp", [])
        quote_data = block.get("indicators", {}).get("quote", [{}])[0]
        if not ts:
            raise ValueError(f"No candles returned for {symbol}")

        frame = pd.DataFrame(
            {
                "timestamp": pd.to_datetime(ts, unit="s", utc=True),
                "open": quote_data.get("open", []),
                "high": quote_data.get("high", []),
                "low": quote_data.get("low", []),
                "close": quote_data.get("close", []),
                "volume": quote_data.get("volume", []),
            }
        )
        return frame.dropna(subset=["open", "high", "low", "close"]).reset_index(drop=True)

    async def multi_timeframe(self, symbol: str) -> dict[str, pd.DataFrame]:
        h1, d1, w1 = await asyncio.gather(
            self.candles(symbol, "1h", "6mo"),
            self.candles(symbol, "1d", "2y"),
            self.candles(symbol, "1wk", "5y"),
        )
        h4 = self._resample_4h(h1)
        return {"1H": h1, "4H": h4, "1D": d1, "1W": w1}

    @staticmethod
    def _resample_4h(frame: pd.DataFrame) -> pd.DataFrame:
        if frame.empty:
            return frame.copy()
        df = frame.set_index("timestamp").sort_index()
        agg = df.resample("4h").agg(
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
            volume=("volume", "sum"),
        )
        return agg.dropna(subset=["open", "high", "low", "close"]).reset_index()

    async def news(self, symbol: str, count: int = 20) -> list[dict]:
        params = {"q": symbol, "quotesCount": 1, "newsCount": count, "enableFuzzyQuery": "false"}
        async with httpx.AsyncClient(timeout=self.timeout, headers=self.headers) as client:
            response = await client.get(self.SEARCH, params=params)
            response.raise_for_status()
            payload = response.json()

        articles = []
        for item in payload.get("news", []):
            ts = item.get("providerPublishTime")
            published = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat() if ts else None
            articles.append(
                {
                    "title": item.get("title") or "",
                    "publisher": item.get("publisher") or "Unknown",
                    "link": item.get("link"),
                    "published_at": published,
                    "type": item.get("type") or "STORY",
                    "related_tickers": item.get("relatedTickers") or [],
                }
            )
        return articles
