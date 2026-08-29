import pandas as pd

from app.quant.research import (
    SimulationConfig,
    _simulate_trade,
    metrics_from_trades,
    monte_carlo_analysis,
    prepare_research_frame,
)


def signal_frame(next_high=110.0, next_low=95.0):
    return pd.DataFrame(
        [
            {
                "timestamp": pd.Timestamp("2026-01-01", tz="UTC"),
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.0,
                "volume": 1000.0,
                "atr": 2.0,
                "signal": 1,
                "confidence": 70.0,
                "market_score": 50.0,
                "technical_core": 60.0,
                "macro_core": 35.0,
                "regime": "TENDENCIA_ALCISTA",
            },
            {
                "timestamp": pd.Timestamp("2026-01-02", tz="UTC"),
                "open": 100.0,
                "high": next_high,
                "low": next_low,
                "close": 104.0,
                "volume": 1000.0,
                "atr": 2.0,
                "signal": 0,
                "confidence": 50.0,
                "market_score": 0.0,
                "technical_core": 0.0,
                "macro_core": 0.0,
                "regime": "RANGO",
            },
        ]
    )


def test_intrabar_ambiguity_uses_stop_first():
    trade = _simulate_trade(
        signal_frame(next_high=110.0, next_low=95.0),
        0,
        SimulationConfig(fee_bps=0, slippage_bps=0),
    )
    assert trade is not None
    assert trade["entry_at"].startswith("2026-01-02")
    assert trade["exit_reason"] == "SL"
    assert trade["r_multiple"] == -1.0


def test_tp2_partial_exit_returns_two_and_half_r():
    trade = _simulate_trade(
        signal_frame(next_high=110.0, next_low=99.0),
        0,
        SimulationConfig(fee_bps=0, slippage_bps=0),
    )
    assert trade is not None
    assert trade["exit_reason"] == "TP2"
    assert trade["tp1_hit"] is True
    assert trade["tp2_hit"] is True
    assert trade["r_multiple"] == 2.5


def synthetic_ohlcv(periods=520):
    timestamps = pd.date_range("2024-01-01", periods=periods, freq="D", tz="UTC")
    close = pd.Series([100 + i * 0.08 + (i % 11) * 0.04 for i in range(periods)], dtype=float)
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": close - 0.15,
            "high": close + 0.8,
            "low": close - 0.8,
            "close": close,
            "volume": [1000 + (i % 7) * 20 for i in range(periods)],
        }
    )


def proxy_frames(periods=520):
    base = synthetic_ohlcv(periods)
    return {name: base.copy() for name in ["DXY", "US10Y", "VIX", "SPY", "QQQ", "GOLD"]}


def test_future_prices_do_not_change_earlier_features():
    original = synthetic_ohlcv()
    altered = original.copy()
    altered.loc[altered.index[-30:], ["open", "high", "low", "close"]] *= 3

    before = prepare_research_frame("BTC-USD", original, proxy_frames())
    after = prepare_research_frame("BTC-USD", altered, proxy_frames())

    cutoff = pd.Timestamp("2025-03-01", tz="UTC")
    left = before[before["timestamp"] < cutoff][["timestamp", "technical_core", "macro_core"]].reset_index(drop=True)
    right = after[after["timestamp"] < cutoff][["timestamp", "technical_core", "macro_core"]].reset_index(drop=True)
    pd.testing.assert_frame_equal(left, right)


def test_metrics_compound_equity_from_r_multiples():
    trades = [
        {"r_multiple": 2.0, "entry_at": "2026-01-01T00:00:00+00:00", "exit_at": "2026-01-02T00:00:00+00:00", "holding_bars": 1, "tp1_hit": True, "tp2_hit": False, "mfe_r": 2.2, "mae_r": -0.2},
        {"r_multiple": -1.0, "entry_at": "2026-01-03T00:00:00+00:00", "exit_at": "2026-01-04T00:00:00+00:00", "holding_bars": 1, "tp1_hit": False, "tp2_hit": False, "mfe_r": 0.2, "mae_r": -1.1},
    ]
    metrics = metrics_from_trades(trades, capital=10_000, risk_percent=1.0)
    assert metrics["trades"] == 2
    assert metrics["win_rate"] == 50.0
    assert metrics["ending_capital"] > 10_000
    assert metrics["max_drawdown_pct"] < 0


def test_monte_carlo_is_deterministic_for_fixed_seed():
    trades = [
        {"r_multiple": value}
        for value in [2.0, -1.0, 1.2, -0.8, 2.5, -1.0, 0.9, 1.5]
    ]
    first = monte_carlo_analysis(trades, 10_000, 1.0, runs=200, seed=7)
    second = monte_carlo_analysis(trades, 10_000, 1.0, runs=200, seed=7)
    assert first == second
    assert first["runs"] == 200
