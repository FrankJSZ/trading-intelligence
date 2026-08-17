from app.engines.decision import decide
from app.engines.risk import build_risk_plan
from app.models import Decision, RiskProfile


def test_strong_confluence_buys():
    out = decide(80, 60, 70, 55, 20, False, "TENDENCIA_ALCISTA")
    assert out["decision"] == Decision.BUY
    assert out["confidence"] >= 60


def test_psychology_veto_waits():
    out = decide(90, 90, 90, 90, -80, True, "TENDENCIA_ALCISTA")
    assert out["decision"] == Decision.WAIT


def test_risk_plan_position_size():
    plan = build_risk_plan(Decision.BUY, 100, 2, 10_000, RiskProfile.MODERATE, 80, False)
    assert plan.stop_loss < plan.entry
    assert plan.take_profit_1 > plan.entry
    assert plan.position_size > 0
    assert plan.risk_percent <= 1.5
