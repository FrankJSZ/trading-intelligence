from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from urllib.parse import quote

import httpx
import pandas as pd


class YahooProvider:
    """Keyless Yahoo Finance provider for market candles and headlines.

    Yahoo's chart/search endpoints are internal and can occasionally be blocked,
    rate-limited, or fail DNS resolution on a specific host. We therefore try
    both query1 and query2 and retry once without proxy-related environment
    variables when a connection-level failure occurs.
    """

    HOSTS = (
        "https://query1.finance.yahoo.com",
        "https://query2.finance.yahoo.com",
    )

    def __init__(self, timeout: float = 15.0):
        self.timeout = timeout
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 TradingIntelligence/1.0",
            "Accept": "application/json,text/plain,*/*",
        }

    async def _get_json(self, path: str, params: dict) -> dict:
        attempts: list[str] = []

        # First respect the user's normal proxy/environment configuration. If a
        # stale HTTP(S)_PROXY variable is the cause of getaddrinfo failures,
        # retry directly with trust_env=False.
        for trust_env in (True, False):
            mode = "environment" if trust_env else "direct"
            for host in self.HOSTS:
                url = f"{host}{path}"
                try:
                    async with httpx.AsyncClient(
                        timeout=self.timeout,
                        headers=self.headers,
                        trust_env=trust_env,
                        follow_redirects=True,
                    ) as client:
                        response = await client.get(url, params=params)
                        response.raise_for_status()
                        return response.json()
                except httpx.HTTPStatusError as exc:
                    status = exc.response.status_code
                    attempts.append(f"{host} [{mode}] HTTP {status}")
                    # Try Yahoo's alternate hostname for transient/blocking errors.
                    if status in {401, 403, 404, 408, 429, 500, 502, 503, 504}:
                        continue
                    raise
                except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout) as exc:
                    attempts.append(f"{host} [{mode}] {exc}")
                    continue
                except httpx.RequestError as exc:
                    attempts.append(f"{host} [{mode}] {exc}")
                    continue

        detail = "; ".join(attempts[-4:]) or "no connection attempts completed"
        raise ConnectionError(
            "No se pudo conectar con Yahoo Finance. "
            "Esto suele indicar un problema de DNS, proxy, VPN, firewall o bloqueo de red. "
            f"Intentos: {detail}. "
            "En Windows prueba: nslookup query1.finance.yahoo.com y "
            "nslookup query2.finance.yahoo.com."
        )

    async def candles(self, symbol: str, interval: str, range_: str) -> pd.DataFrame:
        encoded = quote(symbol, safe="")
        params = {"interval": interval, "range": range_, "includePrePost": "false"}
        payload = await self._get_json(f"/v8/finance/chart/{encoded}", params)

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
        payload = await self._get_json("/v1/finance/search", params)

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
