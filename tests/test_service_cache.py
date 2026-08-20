import asyncio

import app.service as service_module
from app.service import TradingAnalysisService


class FakeProvider:
    def __init__(self):
        self.frame_calls = 0
        self.news_calls = 0

    async def multi_timeframe(self, symbol):
        self.frame_calls += 1
        return {"symbol": symbol, "frames": "placeholder"}

    async def news(self, symbol):
        self.news_calls += 1
        return []


async def _exercise_cache(monkeypatch):
    provider = FakeProvider()
    macro_calls = {"count": 0}

    async def fake_macro(_provider, _symbol):
        macro_calls["count"] += 1
        return {"score": 0.0, "label": "neutral", "proxies": {}, "note": "test"}

    monkeypatch.setattr(service_module, "analyze_macro", fake_macro)
    service = TradingAnalysisService(provider=provider, cache_ttl_seconds=60)

    first = await service._external_snapshot("BTC-USD")
    second = await service._external_snapshot("BTC-USD")

    assert first is second
    assert provider.frame_calls == 1
    assert provider.news_calls == 1
    assert macro_calls["count"] == 1


def test_external_snapshot_uses_short_lived_cache(monkeypatch):
    asyncio.run(_exercise_cache(monkeypatch))
