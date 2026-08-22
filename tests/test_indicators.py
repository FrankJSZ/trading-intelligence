import numpy as np
import pandas as pd
from app.engines.technical import atr, rsi, timeframe_analysis


def sample_frame(n=260, rising=True):
    base = np.linspace(100, 150 if rising else 70, n)
    return pd.DataFrame({"timestamp": pd.date_range("2025-01-01", periods=n, freq="D", tz="UTC"), "open": base, "high": base + 1, "low": base - 1, "close": base + 0.25, "volume": np.full(n, 1000.0)})


def test_rsi_bounds():
    values = rsi(sample_frame()["close"])
    assert values.between(0, 100).all()


def test_atr_positive():
    values = atr(sample_frame()).dropna()
    assert (values >= 0).all()


def test_trending_frame_has_nonzero_score():
    result = timeframe_analysis(sample_frame())
    assert result["score"] != 0
    assert result["price"] > 0
