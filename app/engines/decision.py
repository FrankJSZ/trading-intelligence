from __future__ import annotations

from app.models import Decision


# Directional market score only. Psychology is deliberately excluded: trader
# state can block execution, but it cannot make the market itself bullish/bearish.
WEIGHTS = {"technical": 0.45, "macro": 0.30, "news": 0.25}


def decide(
    technical: float,
    macro: float,
    news: float,
    psych_severe: bool,
    regime: str,
) -> dict:
    market_score = (
        technical * WEIGHTS["technical"]
        + macro * WEIGHTS["macro"]
        + news * WEIGHTS["news"]
    )

    warnings: list[str] = []
    if "ALTA_VOLATILIDAD" in regime:
        warnings.append("Volatilidad alta: reducir tamaño y exigir mayor confirmación.")

    threshold = 32 if "ALTA_VOLATILIDAD" in regime else 28
    if market_score >= threshold:
        market_decision = Decision.BUY
    elif market_score <= -threshold:
        market_decision = Decision.SELL
    else:
        market_decision = Decision.WAIT

    same_side = [technical, macro, news]
    agreement = (
        sum(x >= 15 for x in same_side)
        if market_score >= 0
        else sum(x <= -15 for x in same_side)
    )

    # Still a heuristic confidence score, not a calibrated probability.
    confidence = 48 + min(abs(market_score), 60) * 0.45 + agreement * 6
    if "ALTA_VOLATILIDAD" in regime:
        confidence -= 6
    confidence = max(20.0, min(94.0, confidence))

    if psych_severe and market_decision != Decision.WAIT:
        decision = Decision.WAIT
        execution_status = "BLOQUEADA_POR_PSICOLOGIA"
        warnings.append(
            "La señal de mercado existe, pero el riesgo psicológico alto bloquea la ejecución."
        )
    else:
        decision = market_decision
        execution_status = (
            "SIN_OPERACION" if market_decision == Decision.WAIT else "HABILITADA"
        )

    return {
        "market_decision": market_decision,
        "decision": decision,
        "execution_status": execution_status,
        "score": round(market_score, 2),
        "confidence": round(confidence, 1),
        "warnings": warnings,
        "weights": WEIGHTS.copy(),
    }
