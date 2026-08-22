from __future__ import annotations

import asyncio
from collections import OrderedDict

import httpx


class SpanishNewsTranslator:
    """Best-effort headline translator for the dashboard.

    Translation is deliberately separated from sentiment analysis: the engines
    score the original headline first, then this provider creates the Spanish
    display title. The original title is always preserved for traceability.

    The public Google Translate endpoint used here does not require an API key,
    but it is still an external dependency and can be rate-limited or blocked.
    Translation failures therefore fall back to the original headline instead
    of failing the complete market analysis.
    """

    ENDPOINT = "https://translate.googleapis.com/translate_a/single"

    def __init__(
        self,
        timeout: float = 8.0,
        max_concurrency: int = 4,
        max_cache_items: int = 1000,
    ):
        self.timeout = timeout
        self._semaphore = asyncio.Semaphore(max(1, max_concurrency))
        self._cache: OrderedDict[str, str] = OrderedDict()
        self.max_cache_items = max(50, int(max_cache_items))
        self.headers = {
            "User-Agent": "Mozilla/5.0 TradingIntelligence/1.0",
            "Accept": "application/json,text/plain,*/*",
        }

    @staticmethod
    def _parse_payload(payload) -> str:
        """Extract translated text from Google's compact response payload."""
        if not isinstance(payload, list) or not payload or not isinstance(payload[0], list):
            raise ValueError("Respuesta de traducción no reconocida")
        chunks = []
        for part in payload[0]:
            if isinstance(part, list) and part and isinstance(part[0], str):
                chunks.append(part[0])
        translated = "".join(chunks).strip()
        if not translated:
            raise ValueError("La traducción llegó vacía")
        return translated

    def _remember(self, source: str, translated: str) -> None:
        self._cache[source] = translated
        self._cache.move_to_end(source)
        while len(self._cache) > self.max_cache_items:
            self._cache.popitem(last=False)

    async def translate(self, text: str) -> tuple[str, bool]:
        source = (text or "").strip()
        if not source:
            return source, False

        cached = self._cache.get(source)
        if cached is not None:
            self._cache.move_to_end(source)
            return cached, cached != source

        params = {
            "client": "gtx",
            "sl": "auto",
            "tl": "es",
            "dt": "t",
            "q": source,
        }

        async with self._semaphore:
            # Respect the user's environment first, then retry directly in case
            # an obsolete HTTP(S)_PROXY variable is interfering on Windows.
            for trust_env in (True, False):
                try:
                    async with httpx.AsyncClient(
                        timeout=self.timeout,
                        headers=self.headers,
                        trust_env=trust_env,
                        follow_redirects=True,
                    ) as client:
                        response = await client.get(self.ENDPOINT, params=params)
                        response.raise_for_status()
                        translated = self._parse_payload(response.json())
                        self._remember(source, translated)
                        return translated, translated.casefold() != source.casefold()
                except (httpx.RequestError, httpx.HTTPStatusError, ValueError):
                    continue

        # Translation is presentation-only. Never make the trading analysis fail
        # because the translation provider is unavailable.
        self._remember(source, source)
        return source, False

    async def translate_articles(self, articles: list[dict]) -> tuple[list[dict], dict]:
        async def one(article: dict) -> tuple[dict, bool]:
            original = article.get("title") or ""
            translated, changed = await self.translate(original)
            return {
                **article,
                "original_title": original,
                "title": translated,
                "language": "es" if changed else "original",
                "translated": changed,
            }, changed

        if not articles:
            return [], {"target_language": "es", "translated": 0, "fallback": 0}

        results = await asyncio.gather(*(one(article) for article in articles))
        translated_articles = [article for article, _ in results]
        translated_count = sum(changed for _, changed in results)
        return translated_articles, {
            "target_language": "es",
            "translated": translated_count,
            "fallback": len(results) - translated_count,
        }
