from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone

from app.engines.backtest import run_backtest
from app.engines.correlation import correlations
from app.engines.decision import decide
from app.engines.macro import analyze_macro
from app.engines.news_sentiment import analyze_news, sentiment_component
from app.engines.psychology import analyze_psychology
from app.engines.risk import build_risk_plan
from app.engines.technical import (
    analyze_multi_timeframe,
    historical_direction_probability,
    timeframe_analysis,
)
from app.models import (
    AnalysisRequest,
    AnalysisResponse,
    PsychologyInput,
    SignalComponent,
    WatchlistRequest,
)
from app.providers.translator import SpanishNewsTranslator
from app.providers.yahoo import YahooProvider
from app.storage.history import AnalysisHistory


class TradingAnalysisService:
    """Coordinates data acquisition, analysis engines and local persistence."""

    def __init__(
        self,
        provider: YahooProvider | None = None,
        cache_ttl_seconds: int = 60,
        translator: SpanishNewsTranslator | None = None,
        history: AnalysisHistory | None = None,
    ):
        self.provider = provider or YahooProvider()
        self.translator = translator or SpanishNewsTranslator()
        self.history = history or AnalysisHistory()
        self.cache_ttl_seconds = max(0, int(cache_ttl_seconds))
        self._snapshot_cache: dict[str, tuple[float, dict]] = {}
        self._snapshot_locks: dict[str, asyncio.Lock] = {}

    async def _external_snapshot(self, symbol: str) -> dict:
        now = time.monotonic()
        cached = self._snapshot_cache.get(symbol)
        if cached and now - cached[0] < self.cache_ttl_seconds:
            return cached[1]

        lock = self._snapshot_locks.setdefault(symbol, asyncio.Lock())
        async with lock:
            now = time.monotonic()
            cached = self._snapshot_cache.get(symbol)
            if cached and now - cached[0] < self.cache_ttl_seconds:
                return cached[1]

            frames = await self.provider.multi_timeframe(symbol)

            try:
                articles = await self.provider.news(symbol)
                # News direction/relevance is computed on the original language.
                news = analyze_news(articles)
                try:
                    translated_articles, translation_meta = await self.translator.translate_articles(
                        news.get("articles", [])
                    )
                    news["articles"] = translated_articles
                    news["translation"] = translation_meta
                except Exception as exc:
                    news["translation"] = {
                        "target_language": "es",
                        "translated": 0,
                        "fallback": len(news.get("articles", [])),
                        "error": str(exc),
                    }
            except Exception as exc:
                news = {
                    "score": 0.0,
                    "label": "sin datos",
                    "high_impact_count": 0,
                    "articles": [],
                    "translation": {"target_language": "es", "translated": 0, "fallback": 0},
                    "error": str(exc),
                }

            try:
                macro = await analyze_macro(self.provider, symbol)
            except Exception as exc:
                macro = {
                    "score": 0.0,
                    "label": "neutral",
                    "proxies": {},
                    "note": f"Macro no disponible: {exc}",
                }

            snapshot = {
                "frames": frames,
                "news": news,
                "macro": macro,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
            self._snapshot_cache[symbol] = (time.monotonic(), snapshot)
            return snapshot

    async def analyze(
        self,
        req: AnalysisRequest,
        *,
        persist_history: bool = True,
    ) -> AnalysisResponse:
        symbol = req.symbol.strip().upper()
        snapshot = await self._external_snapshot(symbol)
        frames = snapshot["frames"]
        news = snapshot["news"]
        macro = snapshot["macro"]

        technical = analyze_multi_timeframe(frames)
        price = float(frames["1H"]["close"].iloc[-1])
        # This remains useful as an explanatory descriptor but is NOT another
        # weighted input because it is derived from the same news headlines.
        sentiment = sentiment_component(news)
        psychology = analyze_psychology(req.psychology)

        d = decide(
            technical=technical["score"],
            macro=macro["score"],
            news=news["score"],
            psych_severe=psychology["severe"],
            regime=technical["regime"],
        )

        daily = frames["1D"]
        probability = historical_direction_probability(daily)
        atr_value = float(
            technical["timeframes"]["1D"].get("atr")
            or technical["timeframes"]["4H"].get("atr")
            or 0
        )
        risk = build_risk_plan(
            d["decision"],
            price,
            atr_value,
            req.capital,
            req.risk_profile,
            d["confidence"],
            psychology["severe"],
        )

        warnings = list(d["warnings"])
        if news.get("high_impact_count", 0) >= 3:
            warnings.append("Hay varias noticias de alta relevancia; revisar titulares antes de ejecutar.")
        if sentiment.get("state") in {"euforia", "pánico"}:
            warnings.append(
                f"Sentimiento extremo derivado de titulares: {sentiment['state']}. "
                "Se muestra como contexto y no se suma otra vez al score."
            )

        rationale = {
            "technical": (
                f"Score técnico {technical['score']:+.1f}; régimen "
                f"{technical['regime']} con lectura multitemporal."
            ),
            "fundamental": (
                f"Score macro {macro['score']:+.1f}; {macro['label']}. "
                f"{macro.get('note', '')}"
            ),
            "news": (
                f"Noticias/eventos {news['label']} ({news['score']:+.1f}); "
                "su relevancia, actualidad y credibilidad sí forman parte de la señal."
            ),
            "sentiment": (
                f"Sentimiento descriptivo {sentiment['label']} "
                f"({sentiment['score']:+.1f}); estado {sentiment.get('state', 'mixto')}. "
                "Peso direccional: 0 para evitar doble conteo."
            ),
            "psychological": (
                f"Estado de ejecución: {d['execution_status']}. {psychology['advice']}"
            ),
        }

        market_decision = d["market_decision"]
        if market_decision.value == "COMPRAR":
            alt = (
                "La tesis de mercado se invalida si el score cae por debajo de +15 "
                "o 4H/Diario pierden estructura. Si la psicología bloquea la ejecución, "
                "esperar aunque la tesis siga alcista."
            )
        elif market_decision.value == "VENDER":
            alt = (
                "La tesis de mercado se invalida si el score sube por encima de -15 "
                "o 4H/Diario recuperan estructura. Si la psicología bloquea la ejecución, "
                "esperar aunque la tesis siga bajista."
            )
        else:
            alt = (
                "Esperar a que la confluencia de mercado supere el umbral de decisión; "
                "no anticipar una entrada por FOMO."
            )

        sentiment_details = {
            **sentiment,
            "directional_weight": 0.0,
            "derived_from": "news_headlines",
            "note": "Componente informativo; no se suma al score institucional.",
        }

        response = AnalysisResponse(
            symbol=symbol,
            price=round(price, 6),
            market_decision=market_decision,
            decision=d["decision"],
            execution_status=d["execution_status"],
            confidence=d["confidence"],
            institutional_score=d["score"],
            technical=SignalComponent(
                score=technical["score"],
                label=technical["timeframes"]["1D"]["label"],
                details={**technical, "directional_weight": d["weights"]["technical"]},
            ),
            fundamental_macro=SignalComponent(
                score=macro["score"],
                label=macro["label"],
                details={**macro, "directional_weight": d["weights"]["macro"]},
            ),
            news=SignalComponent(
                score=news["score"],
                label=news["label"],
                details={**news, "directional_weight": d["weights"]["news"]},
            ),
            sentiment=SignalComponent(
                score=sentiment["score"],
                label=sentiment["label"],
                details=sentiment_details,
            ),
            psychology=SignalComponent(
                score=psychology["score"],
                label=psychology["label"],
                details={**psychology, "directional_weight": 0.0},
            ),
            market_regime=technical["regime"],
            historical_probability=probability,
            risk=risk,
            rationale=rationale,
            alternative_scenario=alt,
            warnings=warnings,
            generated_at=snapshot["fetched_at"],
        )

        if persist_history:
            try:
                self.history.save(response.model_dump(mode="json"))
            except Exception:
                # Persistence must never prevent an analysis from being delivered.
                pass

        return response

    async def chart(self, symbol: str, timeframe: str = "1D", limit: int = 120) -> dict:
        symbol = symbol.strip().upper()
        timeframe = timeframe.strip().upper()
        limit = max(30, min(int(limit), 300))

        if timeframe == "1H":
            frame = await self.provider.candles(symbol, "1h", "3mo")
        elif timeframe == "4H":
            hourly = await self.provider.candles(symbol, "1h", "6mo")
            frame = self.provider._resample_4h(hourly)
        elif timeframe == "1W":
            frame = await self.provider.candles(symbol, "1wk", "5y")
        else:
            timeframe = "1D"
            frame = await self.provider.candles(symbol, "1d", "1y")

        frame = frame.tail(limit).copy()
        technical = timeframe_analysis(frame)
        candles = [
            {
                "timestamp": row.timestamp.isoformat(),
                "open": round(float(row.open), 6),
                "high": round(float(row.high), 6),
                "low": round(float(row.low), 6),
                "close": round(float(row.close), 6),
                "volume": float(row.volume) if row.volume is not None and row.volume == row.volume else 0.0,
            }
            for row in frame.itertuples(index=False)
        ]
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "candles": candles,
            "support": technical.get("support"),
            "resistance": technical.get("resistance"),
            "ema20": technical.get("ema20"),
            "ema50": technical.get("ema50"),
            "ema200": technical.get("ema200"),
        }

    async def watchlist(self, req: WatchlistRequest) -> dict:
        semaphore = asyncio.Semaphore(2)

        async def one(symbol: str) -> dict:
            async with semaphore:
                try:
                    result = await self.analyze(
                        AnalysisRequest(
                            symbol=symbol,
                            capital=req.capital,
                            risk_profile=req.risk_profile,
                            psychology=PsychologyInput(),
                        ),
                        persist_history=False,
                    )
                    return {
                        "symbol": result.symbol,
                        "price": result.price,
                        "market_decision": result.market_decision,
                        "decision": result.decision,
                        "execution_status": result.execution_status,
                        "confidence": result.confidence,
                        "institutional_score": result.institutional_score,
                        "regime": result.market_regime,
                        "technical_score": result.technical.score,
                        "macro_score": result.fundamental_macro.score,
                        "news_score": result.news.score,
                    }
                except Exception as exc:
                    return {"symbol": symbol, "error": str(exc)}

        items = await asyncio.gather(*(one(symbol) for symbol in req.symbols))
        valid = [item for item in items if "error" not in item]
        valid.sort(key=lambda item: abs(float(item["institutional_score"])), reverse=True)
        errors = [item for item in items if "error" in item]
        return {
            "items": valid,
            "errors": errors,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def recent_history(self, symbol: str | None = None, limit: int = 50) -> dict:
        return {"items": self.history.recent(symbol=symbol, limit=limit)}

    async def backtest(self, symbol: str) -> dict:
        frame = await self.provider.candles(symbol.upper(), "1d", "5y")
        return {"symbol": symbol.upper(), **run_backtest(frame)}

    async def correlation(self, symbol: str) -> dict:
        payload = await correlations(self.provider, symbol.upper())
        return {"symbol": symbol.upper(), **payload}
