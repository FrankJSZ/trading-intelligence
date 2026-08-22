from __future__ import annotations

from app.models import Decision


WEIGHTS = {"technical": 0.35, "macro": 0.25, "news": 0.20, "sentiment": 0.10, "psychology": 0.10}


def decide(technical: float, macro: float, news: float, sentiment: float, psychology: float, psych_severe: bool, regime: str) -> dict:
    score = technical * WEIGHTS["technical"] + macro * WEIGHTS["macro"] + news * WEIGHTS["news"] + sentiment * WEIGHTS["sentiment"] + psychology * WEIGHTS["psychology"]
    warnings = []
    if psych_severe:
        warnings.append("Riesgo psicológico alto: la operación queda bloqueada.")
    if "ALTA_VOLATILIDAD" in regime:
        warnings.append("Volatilidad alta: reducir tamaño y exigir mayor confirmación.")
    threshold = 32 if "ALTA_VOLATILIDAD" in regime else 28
    if psych_severe:
        decision = Decision.WAIT
    elif score >= threshold:
        decision = Decision.BUY
    elif score <= -threshold:
        decision = Decision.SELL
    else:
        decision = Decision.WAIT
    same_side = [technical, macro, news, sentiment]
    agreement = sum(x >= 15 for x in same_side) if score >= 0 else sum(x <= -15 for x in same_side)
    confidence = 48 + min(abs(score), 60) * 0.45 + agreement * 5
    if psych_severe:
        confidence -= 18
    if "ALTA_VOLATILIDAD" in regime:
        confidence -= 6
    confidence = max(20.0, min(94.0, confidence))
    return {"decision": decision, "score": round(score, 2), "confidence": round(confidence, 1), "warnings": warnings}
