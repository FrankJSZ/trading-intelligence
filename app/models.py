from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Decision(str, Enum):
    BUY = "COMPRAR"
    SELL = "VENDER"
    WAIT = "ESPERAR"


class RiskProfile(str, Enum):
    CONSERVATIVE = "conservador"
    MODERATE = "moderado"
    AGGRESSIVE = "agresivo"


class PsychologyInput(BaseModel):
    fomo: bool = False
    confirmation_bias: bool = False
    revenge_trading: bool = False
    overconfidence: bool = False
    fear_level: int = Field(default=30, ge=0, le=100)
    greed_level: int = Field(default=30, ge=0, le=100)
    discipline_level: int = Field(default=70, ge=0, le=100)


class AnalysisRequest(BaseModel):
    symbol: str = Field(default="BTC-USD", min_length=1, max_length=24)
    capital: float = Field(default=10_000, gt=0)
    risk_profile: RiskProfile = RiskProfile.MODERATE
    psychology: PsychologyInput = Field(default_factory=PsychologyInput)


class SignalComponent(BaseModel):
    score: float = Field(ge=-100, le=100)
    label: str
    details: dict[str, Any] = Field(default_factory=dict)


class RiskPlan(BaseModel):
    entry: float | None
    stop_loss: float | None
    take_profit_1: float | None
    take_profit_2: float | None
    risk_reward: float | None
    risk_percent: float
    max_loss: float
    position_size: float | None


class AnalysisResponse(BaseModel):
    symbol: str
    price: float
    decision: Decision
    confidence: float
    institutional_score: float
    technical: SignalComponent
    fundamental_macro: SignalComponent
    news: SignalComponent
    sentiment: SignalComponent
    psychology: SignalComponent
    market_regime: str
    historical_probability: float | None
    risk: RiskPlan
    rationale: dict[str, str]
    alternative_scenario: str
    warnings: list[str]
    generated_at: str
