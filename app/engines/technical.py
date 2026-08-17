from __future__ import annotations

import numpy as np
import pandas as pd

TF_WEIGHTS = {"1H": 0.15, "4H": 0.25, "1D": 0.35, "1W": 0.25}


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)
    avg_gain = gains.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = losses.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    values = 100 - (100 / (1 + rs))
    return values.fillna(50)


def macd(series: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    fast = ema(series, 12)
    slow = ema(series, 26)
    line = fast - slow
    signal = ema(line, 9)
    return line, signal, line - signal


def atr(frame: pd.DataFrame, period: int = 14) -> pd.Series:
    high = frame["high"]
    low = frame["low"]
    close = frame["close"]
    prev_close = close.shift(1)
    tr = pd.concat([(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def adx(frame: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = frame["high"], frame["low"], frame["close"]
    up = high.diff()
    down = -low.diff()
    plus_dm = up.where((up > down) & (up > 0), 0.0)
    minus_dm = down.where((down > up) & (down > 0), 0.0)
    tr = pd.concat([(high - low), (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
    atr_sm = tr.ewm(alpha=1 / period, adjust=False).mean().replace(0, np.nan)
    plus_di = 100 * plus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr_sm
    minus_di = 100 * minus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr_sm
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.ewm(alpha=1 / period, adjust=False).mean().fillna(0)


def _support_resistance(frame: pd.DataFrame, lookback: int = 80) -> tuple[float | None, float | None]:
    df = frame.tail(lookback)
    if len(df) < 10:
        return None, None
    current = float(df["close"].iloc[-1])
    highs = df["high"].rolling(5, center=True).max()
    lows = df["low"].rolling(5, center=True).min()
    piv_high = df.loc[df["high"].eq(highs), "high"].dropna().tolist()
    piv_low = df.loc[df["low"].eq(lows), "low"].dropna().tolist()
    resistance_candidates = [x for x in piv_high if x > current]
    support_candidates = [x for x in piv_low if x < current]
    resistance = min(resistance_candidates) if resistance_candidates else float(df["high"].max())
    support = max(support_candidates) if support_candidates else float(df["low"].min())
    return support, resistance


def timeframe_analysis(frame: pd.DataFrame) -> dict:
    if len(frame) < 30:
        return {"score": 0.0, "label": "datos insuficientes"}
    df = frame.copy()
    close = df["close"]
    e20 = ema(close, 20)
    e50 = ema(close, 50)
    e200 = ema(close, min(200, max(30, len(df) // 2)))
    rv = rsi(close)
    _, _, mh = macd(close)
    av = atr(df)
    ax = adx(df)
    price = float(close.iloc[-1])
    score = 0.0
    score += 18 if price > e20.iloc[-1] else -18
    score += 16 if e20.iloc[-1] > e50.iloc[-1] else -16
    score += 12 if price > e200.iloc[-1] else -12
    latest_rsi = float(rv.iloc[-1])
    if 52 <= latest_rsi <= 68:
        score += 14
    elif 32 <= latest_rsi < 48:
        score -= 10
    elif latest_rsi >= 75:
        score -= 4
    elif latest_rsi <= 25:
        score += 4
    score += 12 if mh.iloc[-1] > 0 else -12
    if len(mh) > 3:
        score += 6 if mh.iloc[-1] > mh.iloc[-3] else -6
    ret20 = (price / float(close.iloc[-20]) - 1) if len(close) >= 20 else 0
    score += float(np.clip(ret20 * 220, -12, 12))
    avg_volume = float(df["volume"].tail(20).mean() or 0)
    latest_volume = float(df["volume"].iloc[-1] or 0)
    relative_volume = latest_volume / avg_volume if avg_volume > 0 else 1.0
    if relative_volume > 1.5:
        score += 5 * (1 if score >= 0 else -1)
    score = float(np.clip(score, -100, 100))
    support, resistance = _support_resistance(df)
    return {"score": score, "label": "alcista" if score >= 20 else "bajista" if score <= -20 else "lateral/mixto", "price": price, "rsi": round(latest_rsi, 2), "macd_hist": round(float(mh.iloc[-1]), 6), "ema20": round(float(e20.iloc[-1]), 6), "ema50": round(float(e50.iloc[-1]), 6), "ema200": round(float(e200.iloc[-1]), 6), "atr": round(float(av.iloc[-1]), 6), "adx": round(float(ax.iloc[-1]), 2), "relative_volume": round(relative_volume, 2), "support": round(support, 6) if support else None, "resistance": round(resistance, 6) if resistance else None}


def analyze_multi_timeframe(frames: dict[str, pd.DataFrame]) -> dict:
    per_tf = {name: timeframe_analysis(frame) for name, frame in frames.items()}
    weighted = sum(per_tf[k]["score"] * TF_WEIGHTS.get(k, 0) for k in per_tf)
    d = per_tf.get("1D", {})
    regime = "RANGO"
    if d.get("adx", 0) >= 25 and weighted >= 20:
        regime = "TENDENCIA_ALCISTA"
    elif d.get("adx", 0) >= 25 and weighted <= -20:
        regime = "TENDENCIA_BAJISTA"
    atr_pct = (d.get("atr", 0) / d.get("price", 1) * 100) if d.get("price") else 0
    if atr_pct >= 5:
        regime += "+ALTA_VOLATILIDAD"
    elif atr_pct <= 1:
        regime += "+BAJA_VOLATILIDAD"
    return {"score": round(float(weighted), 2), "timeframes": per_tf, "regime": regime}


def historical_direction_probability(frame: pd.DataFrame, horizon: int = 5) -> float | None:
    """Empirical probability conditioned on EMA trend + RSI bucket; descriptive, not predictive guarantee."""
    if len(frame) < 180:
        return None
    df = frame.copy()
    df["ema20"] = ema(df["close"], 20)
    df["ema50"] = ema(df["close"], 50)
    df["rsi"] = rsi(df["close"])
    df["future"] = df["close"].shift(-horizon) / df["close"] - 1
    latest = df.iloc[-1]
    bullish = latest["ema20"] > latest["ema50"]
    bucket = int(float(latest["rsi"]) // 10) * 10
    mask = (df["ema20"] > df["ema50"]) == bullish
    mask &= df["rsi"].between(bucket, bucket + 10, inclusive="left")
    sample = df.loc[mask, "future"].dropna()
    if len(sample) < 20:
        return None
    directional = (sample > 0).mean() if bullish else (sample < 0).mean()
    return round(float(directional * 100), 1)
