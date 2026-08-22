from __future__ import annotations

from app.models import Decision, RiskPlan, RiskProfile


BASE_RISK = {
    RiskProfile.CONSERVATIVE: 0.005,
    RiskProfile.MODERATE: 0.01,
    RiskProfile.AGGRESSIVE: 0.015,
}


def _price_change_percent(entry: float, target: float | None) -> float | None:
    if not entry or target is None:
        return None
    return round((target / entry - 1) * 100, 3)


def build_risk_plan(
    decision: Decision,
    price: float,
    atr_value: float,
    capital: float,
    profile: RiskProfile,
    confidence: float,
    psychology_severe: bool,
) -> RiskPlan:
    risk_pct = BASE_RISK[profile]
    if confidence < 65:
        risk_pct *= 0.65
    if psychology_severe:
        risk_pct *= 0.25
    risk_pct = max(0.0025, min(risk_pct, 0.015))
    max_loss = capital * risk_pct

    if decision == Decision.WAIT or atr_value <= 0:
        return RiskPlan(
            entry=None,
            stop_loss=None,
            stop_loss_percent=None,
            take_profit_1=None,
            take_profit_1_percent=None,
            take_profit_2=None,
            take_profit_2_percent=None,
            risk_reward=None,
            risk_percent=round(risk_pct * 100, 3),
            max_loss=round(max_loss, 2),
            position_size=None,
        )

    stop_distance = max(atr_value * 1.5, price * 0.006)
    rr1 = 2.0 if confidence < 78 else 2.4
    rr2 = rr1 + 1.0
    if decision == Decision.BUY:
        stop = price - stop_distance
        tp1 = price + stop_distance * rr1
        tp2 = price + stop_distance * rr2
    else:
        stop = price + stop_distance
        tp1 = price - stop_distance * rr1
        tp2 = price - stop_distance * rr2
    size = max_loss / stop_distance if stop_distance > 0 else None

    return RiskPlan(
        entry=round(price, 6),
        stop_loss=round(stop, 6),
        stop_loss_percent=_price_change_percent(price, stop),
        take_profit_1=round(tp1, 6),
        take_profit_1_percent=_price_change_percent(price, tp1),
        take_profit_2=round(tp2, 6),
        take_profit_2_percent=_price_change_percent(price, tp2),
        risk_reward=rr1,
        risk_percent=round(risk_pct * 100, 3),
        max_loss=round(max_loss, 2),
        position_size=round(size, 8) if size is not None else None,
    )
