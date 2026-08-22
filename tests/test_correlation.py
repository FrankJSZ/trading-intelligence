import pandas as pd

from app.engines.correlation import _daily_returns, _interpret


def test_daily_returns_normalize_different_market_hours():
    crypto = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                ["2026-01-05T00:00:00Z", "2026-01-06T00:00:00Z", "2026-01-07T00:00:00Z"],
                utc=True,
            ),
            "close": [100.0, 102.0, 101.0],
        }
    )
    equity = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                ["2026-01-05T14:30:00Z", "2026-01-06T14:30:00Z", "2026-01-07T14:30:00Z"],
                utc=True,
            ),
            "close": [200.0, 204.0, 202.0],
        }
    )

    crypto_returns = _daily_returns(crypto, "BTC-USD")
    equity_returns = _daily_returns(equity, "SPY")
    pair = pd.concat([crypto_returns, equity_returns], axis=1, join="inner").dropna()

    assert len(pair) == 2
    assert all(timestamp.hour == 0 for timestamp in pair.index)


def test_correlation_interpretation_labels():
    assert _interpret(0.82) == "Positiva muy alta"
    assert _interpret(-0.61) == "Negativa alta"
    assert _interpret(0.05) == "Prácticamente neutral"
