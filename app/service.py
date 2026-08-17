from __future__ import annotations

from datetime import datetime, timezone
from app.engines.backtest import run_backtest
from app.engines.correlation import correlations
from app.engines.decision import decide
from app.engines.macro import analyze_macro
from app.engines.news_sentiment import analyze_news, sentiment_component
from app.engines.psychology import analyze_psychology
from app.engines.risk import build_risk_plan
from app.engines.technical import analyze_multi_timeframe, historical_direction_probability
from app.models import AnalysisRequest, AnalysisResponse, SignalComponent
from app.providers.yahoo import YahooProvider


class TradingAnalysisService:
    def __init__(self, provider: YahooProvider | None = None):
        self.provider = provider or YahooProvider()

    async def analyze(self, req: AnalysisRequest) -> AnalysisResponse:
        symbol = req.symbol.strip().upper()
        frames = await self.provider.multi_timeframe(symbol)
        technical = analyze_multi_timeframe(frames)
        price = float(frames["1H"]["close"].iloc[-1])
        try:
            articles = await self.provider.news(symbol)
            news = analyze_news(articles)
        except Exception as exc:
            news = {"score": 0.0, "label": "sin datos", "high_impact_count": 0, "articles": [], "error": str(exc)}
        sentiment = sentiment_component(news)
        try:
            macro = await analyze_macro(self.provider, symbol)
        except Exception as exc:
            macro = {"score": 0.0, "label": "neutral", "proxies": {}, "note": f"Macro no disponible: {exc}"}
        psychology = analyze_psychology(req.psychology)
        d = decide(technical=technical["score"], macro=macro["score"], news=news["score"], sentiment=sentiment["score"], psychology=psychology["score"], psych_severe=psychology["severe"], regime=technical["regime"])
        daily = frames["1D"]
        probability = historical_direction_probability(daily)
        atr_value = float(technical["timeframes"]["1D"].get("atr") or technical["timeframes"]["4H"].get("atr") or 0)
        risk = build_risk_plan(d["decision"], price, atr_value, req.capital, req.risk_profile, d["confidence"], psychology["severe"])
        warnings = list(d["warnings"])
        if news.get("high_impact_count", 0) >= 3:
            warnings.append("Hay varias noticias de alta relevancia; revisar titulares antes de ejecutar.")
        if sentiment.get("state") in {"euforia", "pánico"}:
            warnings.append(f"Sentimiento extremo detectado: {sentiment['state']}.")
        rationale = {"technical": f"Score técnico {technical['score']:+.1f}; régimen {technical['regime']} con lectura multitemporal.", "fundamental": f"Score macro {macro['score']:+.1f}; {macro['label']}. {macro.get('note', '')}", "sentiment": f"Sentimiento {sentiment['label']} ({sentiment['score']:+.1f}); estado: {sentiment.get('state', 'mixto')}.", "psychological": psychology["advice"]}
        if d["decision"].value == "COMPRAR":
            alt = "Si el score institucional cae por debajo de +15 o 4H/Diario pierden estructura, cancelar la tesis alcista y volver a ESPERAR."
        elif d["decision"].value == "VENDER":
            alt = "Si el score institucional sube por encima de -15 o 4H/Diario recuperan estructura, cancelar la tesis bajista y volver a ESPERAR."
        else:
            alt = "Esperar a que la confluencia supere el umbral de decisión con riesgo y psicología controlados; no anticipar por FOMO."
        return AnalysisResponse(symbol=symbol, price=round(price, 6), decision=d["decision"], confidence=d["confidence"], institutional_score=d["score"], technical=SignalComponent(score=technical["score"], label=technical["timeframes"]["1D"]["label"], details=technical), fundamental_macro=SignalComponent(score=macro["score"], label=macro["label"], details=macro), news=SignalComponent(score=news["score"], label=news["label"], details=news), sentiment=SignalComponent(score=sentiment["score"], label=sentiment["label"], details=sentiment), psychology=SignalComponent(score=psychology["score"], label=psychology["label"], details=psychology), market_regime=technical["regime"], historical_probability=probability, risk=risk, rationale=rationale, alternative_scenario=alt, warnings=warnings, generated_at=datetime.now(timezone.utc).isoformat())

    async def backtest(self, symbol: str) -> dict:
        frame = await self.provider.candles(symbol.upper(), "1d", "5y")
        return {"symbol": symbol.upper(), **run_backtest(frame)}

    async def correlation(self, symbol: str) -> dict:
        return {"symbol": symbol.upper(), "correlations": await correlations(self.provider, symbol.upper())}
