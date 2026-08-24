import asyncio

import pandas as pd

import app.engines.macro as macro_module


class FakeMacroProvider:
    def __init__(self):
        self.calls = 0

    async def candles(self, symbol, interval, range_):
        self.calls += 1
        timestamps = pd.date_range("2026-01-01", periods=30, freq="D", tz="UTC")
        close = pd.Series([100 + i for i in range(30)], dtype=float)
        return pd.DataFrame(
            {
                "timestamp": timestamps,
                "open": close,
                "high": close + 1,
                "low": close - 1,
                "close": close,
                "volume": [1000] * 30,
            }
        )


async def _exercise_shared_cache():
    macro_module._PROXY_CACHE = None
    provider = FakeMacroProvider()
    first = await macro_module.analyze_macro(provider, "BTC-USD")
    second = await macro_module.analyze_macro(provider, "ETH-USD")
    return provider, first, second


def test_macro_proxies_are_reused_across_symbols():
    provider, first, second = asyncio.run(_exercise_shared_cache())

    assert provider.calls == len(macro_module.PROXIES)
    assert first["proxies"] == second["proxies"]
