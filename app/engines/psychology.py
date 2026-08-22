from __future__ import annotations

from app.models import PsychologyInput


def analyze_psychology(p: PsychologyInput) -> dict:
    penalties = 0
    active = []
    for name, enabled, penalty in [
        ("FOMO", p.fomo, 18),
        ("sesgo de confirmación", p.confirmation_bias, 12),
        ("revenge trading", p.revenge_trading, 25),
        ("exceso de confianza", p.overconfidence, 15),
    ]:
        if enabled:
            active.append(name)
            penalties += penalty

    penalties += max(0, p.fear_level - 55) * 0.25
    penalties += max(0, p.greed_level - 55) * 0.25
    discipline_bonus = (p.discipline_level - 50) * 0.35
    score = max(-100, min(100, discipline_bonus - penalties))
    severe = p.revenge_trading or p.discipline_level < 30 or len(active) >= 3

    if severe:
        advice = "No ejecutar la operación. Reducir exposición y volver a evaluar cuando la disciplina y el plan estén restablecidos."
    elif active:
        advice = "Hay sesgos activos: reducir tamaño, fijar invalidación antes de entrar y no mover el stop por emoción."
    else:
        advice = "Estado compatible con una ejecución disciplinada; mantener el plan predefinido."

    return {"score": round(score, 2), "label": "alerta" if severe else "vigilancia" if active else "estable", "severe": severe, "active_biases": active, "advice": advice}
