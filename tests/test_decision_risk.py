from app.engines.decision import decide
from app.engines.risk import build_risk_plan
from app.models import Decision, RiskProfile


def test_strong_market_confluence_buys():
    out = decide(
        technical=80,
        macro=60,
        news=70,
        psych_severe=False,
        regime="TENDENCIA_ALCISTA",
    )
    assert out["market_decision"] == Decision.BUY
    assert out["decision"] == Decision.BUY
    assert out["execution_status"] == "HABILITADA"
    assert out["confidence"] >= 60


def test_psychology_blocks_execution_but_not_market_signal():
    normal = decide(
        technical=90,
        macro=90,
        news=90,
        psych_severe=False,
        regime="TENDENCIA_ALCISTA",
    )
    blocked = decide(
        technical=90,
        macro=90,
        news=90,
        psych_severe=True,
        regime="TENDENCIA_ALCISTA",
    )

    assert normal["market_decision"] == Decision.BUY
    assert blocked["market_decision"] == Decision.BUY
    assert normal["score"] == blocked["score"]
    assert blocked["decision"] == Decision.WAIT
    assert blocked["execution_status"] == "BLOQUEADA_POR_PSICOLOGIA"


def test_market_score_has_no_sentiment_or_psychology_weight():
    out = decide(
        technical=40,
        macro=20,
        news=10,
        psych_severe=False,
        regime="RANGO",
    )
    assert out["weights"] == {"technical": 0.45, "macro": 0.30, "news": 0.25}
    assert round(out["score"], 2) == 26.5


def test_risk_plan_position_size_and_percentages_for_buy():
    plan = build_risk_plan(Decision.BUY, 100, 2, 10_000, RiskProfile.MODERATE, 80, False)
    assert plan.stop_loss < plan.entry
    assert plan.take_profit_1 > plan.entry
    assert plan.position_size > 0
    assert plan.risk_percent <= 1.5
    assert plan.stop_loss_percent < 0
    assert plan.take_profit_1_percent > 0
    assert plan.take_profit_2_percent > plan.take_profit_1_percent
    assert round(plan.stop_loss_percent, 2) == -3.00
    assert round(plan.take_profit_1_percent, 2) == 7.20
    assert round(plan.take_profit_2_percent, 2) == 10.20


def test_risk_plan_percentages_for_sell_keep_price_direction_sign():
    plan = build_risk_plan(Decision.SELL, 100, 2, 10_000, RiskProfile.MODERATE, 80, False)
    assert plan.stop_loss > plan.entry
    assert plan.take_profit_1 < plan.entry
    assert plan.stop_loss_percent > 0
    assert plan.take_profit_1_percent < 0
    assert plan.take_profit_2_percent < plan.take_profit_1_percent


def test_wait_plan_has_no_target_percentages():
    plan = build_risk_plan(Decision.WAIT, 100, 2, 10_000, RiskProfile.MODERATE, 80, False)
    assert plan.entry is None
    assert plan.stop_loss_percent is None
    assert plan.take_profit_1_percent is None
    assert plan.take_profit_2_percent is None
