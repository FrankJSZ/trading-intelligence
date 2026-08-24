import asyncio

import pandas as pd

from app.service import TradingAnalysisService
from app.storage.history import AnalysisHistory


class FakeChartProvider:
    async def candles(self, symbol, interval, range_):
        timestamps = pd.date_range("2026-01-01", periods=90, freq="D", tz="UTC")
        close = pd.Series([100 + i * 0.5 for i in range(90)], dtype=float)
        return pd.DataFrame(
            {
                "timestamp": timestamps,
                "open": close - 0.2,
                "high": close + 0.8,
                "low": close - 0.8,
                "close": close,
                "volume": [1000 + i for i in range(90)],
            }
        )

    @staticmethod
    def _resample_4h(frame):
        return frame


async def _load_chart(tmp_path):
    service = TradingAnalysisService(
        provider=FakeChartProvider(),
        history=AnalysisHistory(str(tmp_path / "history.db")),
    )
    return await service.chart("btc-usd", timeframe="1D", limit=60)


def test_chart_returns_normalized_candles_and_levels(tmp_path):
    data = asyncio.run(_load_chart(tmp_path))

    assert data["symbol"] == "BTC-USD"
    assert data["timeframe"] == "1D"
    assert len(data["candles"]) == 60
    assert data["candles"][-1]["close"] > data["candles"][0]["close"]
    assert data["support"] is not None
    assert data["resistance"] is not None
