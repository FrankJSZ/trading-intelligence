from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


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


class WatchlistRequest(BaseModel):
    symbols: list[str] = Field(default_factory=lambda: ["BTC-USD", "ETH-USD", "NVDA", "SPY"], min_length=1, max_length=8)
    capital: float = Field(default=10_000, gt=0)
    risk_profile: RiskProfile = RiskProfile.MODERATE

    @field_validator("symbols")
    @classmethod
    def normalize_symbols(cls, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        for value in values:
            symbol = value.strip().upper()
            if symbol and symbol not in cleaned:
                cleaned.append(symbol)
        if not cleaned:
            raise ValueError("La watchlist debe contener al menos un símbolo.")
        return cleaned[:8]


class QuantBacktestRequest(BaseModel):
    symbol: str = Field(default="BTC-USD", min_length=1, max_length=24)
    capital: float = Field(default=10_000, gt=0)
    risk_percent: float = Field(default=1.0, ge=0.25, le=2.0)
    fee_bps: float = Field(default=10.0, ge=0.0, le=100.0)
    slippage_bps: float = Field(default=5.0, ge=0.0, le=100.0)
    max_holding_bars: int = Field(default=20, ge=2, le=60)
    years: int = Field(default=5, ge=3, le=5)
    walk_forward: bool = True
    monte_carlo_runs: int = Field(default=1000, ge=100, le=5000)

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        symbol = value.strip().upper()
        if not symbol:
            raise ValueError("El símbolo no puede estar vacío.")
        return symbol


class SignalComponent(BaseModel):
    score: float = Field(ge=-100, le=100)
    label: str
    details: dict[str, Any] = Field(default_factory=dict)


class RiskPlan(BaseModel):
    entry: float | None
    stop_loss: float | None
    stop_loss_percent: float | None = None
    take_profit_1: float | None
    take_profit_1_percent: float | None = None
    take_profit_2: float | None
    take_profit_2_percent: float | None = None
    risk_reward: float | None
    risk_percent: float
    max_loss: float
    position_size: float | None


class AnalysisResponse(BaseModel):
    symbol: str
    price: float
    market_decision: Decision
    decision: Decision
    execution_status: str
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
