from __future__ import annotations

import math
import pandas as pd
from app.engines.technical import ema, rsi


def run_backtest(frame: pd.DataFrame) -> dict:
    """Simple research baseline: EMA20/50 + RSI filter, next-day close exits."""
    if len(frame) < 120:
        return {"trades": 0, "error": "Datos insuficientes"}
    df = frame.copy()
    df["ema20"] = ema(df["close"], 20)
    df["ema50"] = ema(df["close"], 50)
    df["rsi"] = rsi(df["close"])
    df["ret"] = df["close"].pct_change().shift(-1)
    df["signal"] = 0
    df.loc[(df["ema20"] > df["ema50"]) & df["rsi"].between(50, 70), "signal"] = 1
    df.loc[(df["ema20"] < df["ema50"]) & df["rsi"].between(30, 50), "signal"] = -1
    trades = (df["signal"] * df["ret"]).dropna()
    trades = trades[trades != 0]
    if trades.empty:
        return {"trades": 0}
    wins = trades[trades > 0]
    losses = trades[trades < 0]
    equity = (1 + trades).cumprod()
    drawdown = equity / equity.cummax() - 1
    std = float(trades.std(ddof=0))
    sharpe = (float(trades.mean()) / std * math.sqrt(252)) if std > 0 else 0.0
    gross_profit = float(wins.sum())
    gross_loss = abs(float(losses.sum()))
    return {"trades": int(len(trades)), "win_rate": round(float((trades > 0).mean() * 100), 2), "average_return_pct": round(float(trades.mean() * 100), 4), "expectancy_pct": round(float(trades.mean() * 100), 4), "profit_factor": round(gross_profit / gross_loss, 3) if gross_loss > 0 else None, "sharpe": round(sharpe, 3), "max_drawdown_pct": round(float(drawdown.min() * 100), 2), "total_return_pct": round(float((equity.iloc[-1] - 1) * 100), 2), "note": "Backtest de referencia para investigación; no representa el motor completo ni garantiza resultados futuros."}
