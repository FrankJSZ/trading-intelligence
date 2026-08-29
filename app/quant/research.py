from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

from app.engines.technical import adx, atr, ema, macd, rsi


CORE_VERSION = "quant-core-v1"
DEFAULT_TECH_WEIGHT = 0.60
DEFAULT_THRESHOLD = 28.0


@dataclass(frozen=True)
class SimulationConfig:
    capital: float = 10_000.0
    risk_percent: float = 1.0
    fee_bps: float = 10.0
    slippage_bps: float = 5.0
    max_holding_bars: int = 20
    tech_weight: float = DEFAULT_TECH_WEIGHT
    threshold: float = DEFAULT_THRESHOLD

    @property
    def macro_weight(self) -> float:
        return 1.0 - self.tech_weight


# ---------- Feature preparation ----------


def _normalized_frame(frame: pd.DataFrame) -> pd.DataFrame:
    required = {"timestamp", "open", "high", "low", "close", "volume"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Faltan columnas OHLCV: {sorted(missing)}")
    df = frame[list(required)].copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True).dt.normalize()
    df = df.dropna(subset=["open", "high", "low", "close"])
    df = df.drop_duplicates(subset=["timestamp"], keep="last").sort_values("timestamp")
    return df.reset_index(drop=True)


def _technical_score_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Vectorized equivalent of the transparent technical scoring rules.

    All indicators at row t depend only on observations <= t. This function is
    used by the research engine so historical signals never see future prices.
    """
    df = _normalized_frame(frame)
    close = df["close"].astype(float)
    volume = df["volume"].fillna(0).astype(float)

    df["ema20"] = ema(close, 20)
    df["ema50"] = ema(close, 50)
    df["ema200"] = ema(close, 200)
    df["rsi"] = rsi(close)
    _, _, histogram = macd(close)
    df["macd_hist"] = histogram
    df["atr"] = atr(df)
    df["adx"] = adx(df)
    df["ret20"] = close / close.shift(20) - 1
    df["relative_volume"] = volume / volume.rolling(20, min_periods=5).mean().replace(0, np.nan)

    score = pd.Series(0.0, index=df.index)
    score += np.where(close > df["ema20"], 18.0, -18.0)
    score += np.where(df["ema20"] > df["ema50"], 16.0, -16.0)
    score += np.where(close > df["ema200"], 12.0, -12.0)

    r = df["rsi"]
    score += np.select(
        [r.between(52, 68), r.between(32, 48, inclusive="left"), r >= 75, r <= 25],
        [14.0, -10.0, -4.0, 4.0],
        default=0.0,
    )
    score += np.where(df["macd_hist"] > 0, 12.0, -12.0)
    score += np.where(df["macd_hist"] > df["macd_hist"].shift(2), 6.0, -6.0)
    score += np.clip(df["ret20"].fillna(0).to_numpy() * 220.0, -12.0, 12.0)

    high_volume = df["relative_volume"].fillna(1.0) > 1.5
    score += np.where(high_volume, np.where(score >= 0, 5.0, -5.0), 0.0)
    df["technical_score"] = np.clip(score, -100.0, 100.0)
    return df


def _weekly_score_aligned(daily: pd.DataFrame) -> pd.Series:
    """Use only the last *completed* weekly candle for each daily row.

    Weekly bars are shifted one full week before forward filling to daily dates,
    preventing Friday's completed OHLC from leaking into Monday-Thursday rows.
    """
    indexed = daily.set_index("timestamp").sort_index()
    weekly = indexed.resample("W-FRI").agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
    ).dropna(subset=["open", "high", "low", "close"]).reset_index()
    weekly_scored = _technical_score_frame(weekly)
    series = weekly_scored.set_index("timestamp")["technical_score"].shift(1)
    return series.reindex(daily["timestamp"], method="ffill").set_axis(daily.index)


def _proxy_score_series(frame: pd.DataFrame, dates: pd.Series) -> pd.Series:
    df = _normalized_frame(frame)
    values = np.clip((df["close"] / df["close"].shift(20) - 1) * 400.0, -100.0, 100.0)
    series = pd.Series(values.to_numpy(), index=df["timestamp"])
    # Historical proxies are exchange-traded; for weekend crypto rows the last
    # known observation is carried forward, never backward from a future date.
    return series.reindex(pd.DatetimeIndex(dates), method="ffill").set_axis(dates.index).fillna(0.0)


def _macro_score(symbol: str, proxies: dict[str, pd.Series]) -> pd.Series:
    upper = symbol.upper()
    is_crypto = upper.endswith("-USD") and upper.split("-")[0] in {
        "BTC", "ETH", "SOL", "XRP", "ADA", "DOGE", "BNB"
    }
    is_gold = "GC=" in upper or "XAU" in upper or "GOLD" in upper

    if is_crypto:
        raw = (
            0.30 * proxies["QQQ"]
            + 0.20 * proxies["SPY"]
            - 0.20 * proxies["DXY"]
            - 0.15 * proxies["US10Y"]
            - 0.15 * proxies["VIX"]
        )
    elif is_gold:
        raw = (
            -0.35 * proxies["DXY"]
            - 0.25 * proxies["US10Y"]
            - 0.15 * proxies["SPY"]
            + 0.25 * proxies["VIX"]
        )
    else:
        raw = (
            0.40 * proxies["SPY"]
            + 0.30 * proxies["QQQ"]
            - 0.15 * proxies["US10Y"]
            - 0.15 * proxies["VIX"]
        )
    return pd.Series(np.clip(raw, -100.0, 100.0), index=raw.index)


def prepare_research_frame(
    symbol: str,
    asset_frame: pd.DataFrame,
    proxy_frames: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    daily = _technical_score_frame(asset_frame)
    daily["weekly_score"] = _weekly_score_aligned(daily).fillna(0.0)
    daily["technical_core"] = daily["technical_score"] * 0.75 + daily["weekly_score"] * 0.25

    proxy_series = {
        name: _proxy_score_series(frame, daily["timestamp"])
        for name, frame in proxy_frames.items()
    }
    required = {"DXY", "US10Y", "VIX", "SPY", "QQQ"}
    missing = required.difference(proxy_series)
    if missing:
        raise ValueError(f"Faltan proxies macro históricos: {sorted(missing)}")
    daily["macro_core"] = _macro_score(symbol, proxy_series)

    atr_pct = daily["atr"] / daily["close"].replace(0, np.nan) * 100.0
    base_regime = np.select(
        [
            (daily["adx"] >= 25) & (daily["technical_core"] >= 20),
            (daily["adx"] >= 25) & (daily["technical_core"] <= -20),
        ],
        ["TENDENCIA_ALCISTA", "TENDENCIA_BAJISTA"],
        default="RANGO",
    )
    suffix = np.where(atr_pct >= 5, "+ALTA_VOLATILIDAD", np.where(atr_pct <= 1, "+BAJA_VOLATILIDAD", ""))
    daily["regime"] = pd.Series(base_regime, index=daily.index) + pd.Series(suffix, index=daily.index)
    return daily.replace([np.inf, -np.inf], np.nan).dropna(subset=["atr", "technical_core"]).reset_index(drop=True)


# ---------- Signals and trade simulation ----------


def apply_signal_model(frame: pd.DataFrame, tech_weight: float, threshold: float) -> pd.DataFrame:
    df = frame.copy()
    macro_weight = 1.0 - tech_weight
    df["market_score"] = df["technical_core"] * tech_weight + df["macro_core"] * macro_weight
    high_vol = df["regime"].str.contains("ALTA_VOLATILIDAD", na=False)
    df["effective_threshold"] = threshold + np.where(high_vol, 4.0, 0.0)
    df["signal"] = np.where(
        df["market_score"] >= df["effective_threshold"],
        1,
        np.where(df["market_score"] <= -df["effective_threshold"], -1, 0),
    )

    same_side = np.where(
        df["market_score"] >= 0,
        (df["technical_core"] >= 15).astype(int) + (df["macro_core"] >= 15).astype(int),
        (df["technical_core"] <= -15).astype(int) + (df["macro_core"] <= -15).astype(int),
    )
    confidence = 48 + np.minimum(np.abs(df["market_score"]), 60) * 0.45 + same_side * 8
    confidence -= np.where(high_vol, 6, 0)
    df["confidence"] = np.clip(confidence, 20.0, 94.0)
    return df


def _adverse_price(price: float, direction: int, slippage_rate: float, is_entry: bool) -> float:
    # Buy entries and sell exits pay up; sell entries and buy exits receive less.
    sign = direction if is_entry else -direction
    return price * (1.0 + sign * slippage_rate)


def _trade_fee_r(entry: float, weighted_exit: float, stop_distance: float, fee_rate: float) -> float:
    if stop_distance <= 0:
        return 0.0
    return fee_rate * (entry + weighted_exit) / stop_distance


def _simulate_trade(df: pd.DataFrame, signal_index: int, config: SimulationConfig) -> dict[str, Any] | None:
    if signal_index + 1 >= len(df):
        return None
    signal_row = df.iloc[signal_index]
    direction = int(signal_row["signal"])
    if direction == 0:
        return None

    entry_index = signal_index + 1
    entry_row = df.iloc[entry_index]
    slippage = config.slippage_bps / 10_000.0
    fee_rate = config.fee_bps / 10_000.0
    entry = _adverse_price(float(entry_row["open"]), direction, slippage, True)

    stop_distance = max(float(signal_row["atr"]) * 1.5, float(signal_row["close"]) * 0.006)
    if not math.isfinite(stop_distance) or stop_distance <= 0:
        return None

    rr1 = 2.0 if float(signal_row["confidence"]) < 78 else 2.4
    rr2 = rr1 + 1.0
    stop = entry - direction * stop_distance
    tp1 = entry + direction * stop_distance * rr1
    tp2 = entry + direction * stop_distance * rr2

    last_index = min(len(df) - 1, entry_index + config.max_holding_bars - 1)
    tp1_hit = False
    exit_index = last_index
    exit_reason = "TIMEOUT"
    weighted_exit = None
    mfe_r = 0.0
    mae_r = 0.0

    for idx in range(entry_index, last_index + 1):
        row = df.iloc[idx]
        high = float(row["high"])
        low = float(row["low"])
        if direction > 0:
            favorable = (high - entry) / stop_distance
            adverse = (low - entry) / stop_distance
        else:
            favorable = (entry - low) / stop_distance
            adverse = (entry - high) / stop_distance
        mfe_r = max(mfe_r, favorable)
        mae_r = min(mae_r, adverse)

        if not tp1_hit:
            stop_touched = low <= stop if direction > 0 else high >= stop
            tp2_touched = high >= tp2 if direction > 0 else low <= tp2
            tp1_touched = high >= tp1 if direction > 0 else low <= tp1

            # Conservative ambiguity rule: if stop and a target are both inside
            # the same OHLC candle, assume the stop occurred first.
            if stop_touched:
                raw_exit = _adverse_price(stop, direction, slippage, False)
                weighted_exit = raw_exit
                exit_index = idx
                exit_reason = "SL"
                break
            if tp2_touched:
                exit1 = _adverse_price(tp1, direction, slippage, False)
                exit2 = _adverse_price(tp2, direction, slippage, False)
                weighted_exit = 0.5 * exit1 + 0.5 * exit2
                exit_index = idx
                exit_reason = "TP2"
                tp1_hit = True
                break
            if tp1_touched:
                tp1_hit = True
                partial_exit = _adverse_price(tp1, direction, slippage, False)
                # The second half now uses entry as a breakeven stop.
                weighted_exit = 0.5 * partial_exit
                continue
        else:
            be_touched = low <= entry if direction > 0 else high >= entry
            tp2_touched = high >= tp2 if direction > 0 else low <= tp2
            if be_touched:
                be_exit = _adverse_price(entry, direction, slippage, False)
                weighted_exit += 0.5 * be_exit
                exit_index = idx
                exit_reason = "TP1_BE"
                break
            if tp2_touched:
                exit2 = _adverse_price(tp2, direction, slippage, False)
                weighted_exit += 0.5 * exit2
                exit_index = idx
                exit_reason = "TP2"
                break

    if exit_reason == "TIMEOUT":
        raw_close = float(df.iloc[last_index]["close"])
        final_exit = _adverse_price(raw_close, direction, slippage, False)
        if tp1_hit and weighted_exit is not None:
            weighted_exit += 0.5 * final_exit
            exit_reason = "TP1_TIMEOUT"
        else:
            weighted_exit = final_exit

    assert weighted_exit is not None
    gross_r = direction * (weighted_exit - entry) / stop_distance
    fee_r = _trade_fee_r(entry, weighted_exit, stop_distance, fee_rate)
    net_r = gross_r - fee_r

    return {
        "signal_index": int(signal_index),
        "entry_index": int(entry_index),
        "exit_index": int(exit_index),
        "signal_at": pd.Timestamp(signal_row["timestamp"]).isoformat(),
        "entry_at": pd.Timestamp(entry_row["timestamp"]).isoformat(),
        "exit_at": pd.Timestamp(df.iloc[exit_index]["timestamp"]).isoformat(),
        "direction": "COMPRAR" if direction > 0 else "VENDER",
        "signal": direction,
        "market_score": round(float(signal_row["market_score"]), 3),
        "confidence": round(float(signal_row["confidence"]), 2),
        "technical_score": round(float(signal_row["technical_core"]), 3),
        "macro_score": round(float(signal_row["macro_core"]), 3),
        "regime": str(signal_row["regime"]),
        "entry": round(entry, 6),
        "stop_loss": round(stop, 6),
        "take_profit_1": round(tp1, 6),
        "take_profit_2": round(tp2, 6),
        "stop_distance_pct": round(stop_distance / entry * 100.0, 4),
        "holding_bars": int(exit_index - entry_index + 1),
        "exit_reason": exit_reason,
        "tp1_hit": bool(tp1_hit),
        "tp2_hit": exit_reason == "TP2",
        "gross_r": round(float(gross_r), 4),
        "cost_r": round(float(fee_r), 4),
        "r_multiple": round(float(net_r), 4),
        "mfe_r": round(float(mfe_r), 4),
        "mae_r": round(float(mae_r), 4),
    }


def simulate_strategy(
    frame: pd.DataFrame,
    config: SimulationConfig,
    start_index: int = 220,
    end_index: int | None = None,
) -> list[dict[str, Any]]:
    df = apply_signal_model(frame, config.tech_weight, config.threshold)
    end_index = min(end_index if end_index is not None else len(df) - 2, len(df) - 2)
    trades: list[dict[str, Any]] = []
    index = max(1, start_index)
    while index <= end_index:
        if int(df.iloc[index]["signal"]) == 0:
            index += 1
            continue
        trade = _simulate_trade(df, index, config)
        if trade is None:
            index += 1
            continue
        trades.append(trade)
        # No overlapping positions: a new signal may be considered only after
        # the current trade has exited.
        index = max(index + 1, int(trade["exit_index"]) + 1)
    return trades


# ---------- Metrics ----------


def _max_drawdown(equity: list[float]) -> float:
    peak = equity[0]
    worst = 0.0
    for value in equity:
        peak = max(peak, value)
        if peak > 0:
            worst = min(worst, value / peak - 1.0)
    return worst


def metrics_from_trades(
    trades: list[dict[str, Any]],
    capital: float,
    risk_percent: float,
) -> dict[str, Any]:
    if not trades:
        return {
            "trades": 0,
            "win_rate": 0.0,
            "expectancy_r": 0.0,
            "profit_factor": None,
            "total_return_pct": 0.0,
            "max_drawdown_pct": 0.0,
            "ending_capital": round(capital, 2),
            "equity_curve": [],
        }

    equity = float(capital)
    risk_fraction = risk_percent / 100.0
    curve = [{"at": trades[0]["entry_at"], "equity": round(equity, 2)}]
    returns: list[float] = []
    r_values: list[float] = []
    wins: list[float] = []
    losses: list[float] = []

    for trade in trades:
        r_value = float(trade["r_multiple"])
        trade_return = r_value * risk_fraction
        pnl = equity * trade_return
        equity += pnl
        r_values.append(r_value)
        returns.append(trade_return)
        (wins if r_value > 0 else losses).append(r_value)
        curve.append({"at": trade["exit_at"], "equity": round(equity, 2)})

    equity_values = [item["equity"] for item in curve]
    max_dd = _max_drawdown(equity_values)
    win_rate = sum(r > 0 for r in r_values) / len(r_values) * 100.0
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else None

    start = pd.Timestamp(trades[0]["entry_at"])
    end = pd.Timestamp(trades[-1]["exit_at"])
    years = max((end - start).days / 365.25, 1 / 365.25)
    cagr = (equity / capital) ** (1 / years) - 1 if equity > 0 and capital > 0 else -1.0
    trades_per_year = max(len(trades) / years, 1.0)

    arr = np.asarray(returns, dtype=float)
    std = float(arr.std(ddof=0))
    sharpe = float(arr.mean() / std * math.sqrt(trades_per_year)) if std > 0 else 0.0
    downside = arr[arr < 0]
    downside_std = float(downside.std(ddof=0)) if len(downside) else 0.0
    sortino = float(arr.mean() / downside_std * math.sqrt(trades_per_year)) if downside_std > 0 else 0.0
    calmar = cagr / abs(max_dd) if max_dd < 0 else None

    return {
        "trades": len(trades),
        "win_rate": round(win_rate, 2),
        "average_r": round(float(np.mean(r_values)), 4),
        "median_r": round(float(np.median(r_values)), 4),
        "expectancy_r": round(float(np.mean(r_values)), 4),
        "profit_factor": round(float(profit_factor), 3) if profit_factor is not None else None,
        "total_r": round(float(sum(r_values)), 3),
        "total_return_pct": round((equity / capital - 1.0) * 100.0, 2),
        "cagr_pct": round(cagr * 100.0, 2),
        "max_drawdown_pct": round(max_dd * 100.0, 2),
        "sharpe": round(sharpe, 3),
        "sortino": round(sortino, 3),
        "calmar": round(float(calmar), 3) if calmar is not None else None,
        "average_holding_bars": round(float(np.mean([t["holding_bars"] for t in trades])), 2),
        "tp1_hit_rate": round(sum(bool(t["tp1_hit"]) for t in trades) / len(trades) * 100.0, 2),
        "tp2_hit_rate": round(sum(bool(t["tp2_hit"]) for t in trades) / len(trades) * 100.0, 2),
        "average_mfe_r": round(float(np.mean([t["mfe_r"] for t in trades])), 3),
        "average_mae_r": round(float(np.mean([t["mae_r"] for t in trades])), 3),
        "ending_capital": round(equity, 2),
        "equity_curve": curve,
    }


def regime_breakdown(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not trades:
        return []
    groups: dict[str, list[dict[str, Any]]] = {}
    for trade in trades:
        groups.setdefault(str(trade["regime"]), []).append(trade)
    result = []
    for regime, items in groups.items():
        values = [float(t["r_multiple"]) for t in items]
        wins = [r for r in values if r > 0]
        losses = [r for r in values if r <= 0]
        gp = sum(wins)
        gl = abs(sum(losses))
        result.append({
            "regime": regime,
            "trades": len(items),
            "win_rate": round(len(wins) / len(items) * 100.0, 2),
            "expectancy_r": round(float(np.mean(values)), 4),
            "profit_factor": round(gp / gl, 3) if gl > 0 else None,
        })
    result.sort(key=lambda item: item["trades"], reverse=True)
    return result


# ---------- Walk-forward and calibration ----------


def _candidate_score(metrics: dict[str, Any]) -> float:
    trades = int(metrics.get("trades", 0))
    if trades < 8:
        return -1_000.0 + trades
    expectancy = float(metrics.get("expectancy_r", 0.0))
    drawdown = abs(float(metrics.get("max_drawdown_pct", 0.0))) / 100.0
    sample_factor = min(1.0, trades / 25.0)
    return expectancy * sample_factor - drawdown * 0.15


def walk_forward_analysis(
    frame: pd.DataFrame,
    config: SimulationConfig,
    train_bars: int = 504,
    test_bars: int = 126,
) -> dict[str, Any]:
    if len(frame) < train_bars + test_bars + 220:
        return {"folds": [], "oos_trades": [], "metrics": {}, "note": "Muestra insuficiente para walk-forward."}

    candidates = [(tw, th) for tw in (0.50, 0.60, 0.70) for th in (24.0, 28.0, 32.0)]
    folds: list[dict[str, Any]] = []
    oos_trades: list[dict[str, Any]] = []
    test_start = train_bars
    fold_id = 1

    while test_start + test_bars <= len(frame):
        train_start = max(0, test_start - train_bars)
        train_frame = frame.iloc[train_start:test_start].reset_index(drop=True)
        best: tuple[float, float, float, dict[str, Any]] | None = None

        for tech_weight, threshold in candidates:
            candidate = SimulationConfig(
                capital=config.capital,
                risk_percent=config.risk_percent,
                fee_bps=config.fee_bps,
                slippage_bps=config.slippage_bps,
                max_holding_bars=config.max_holding_bars,
                tech_weight=tech_weight,
                threshold=threshold,
            )
            train_trades = simulate_strategy(train_frame, candidate, start_index=min(220, max(30, len(train_frame) // 3)))
            train_metrics = metrics_from_trades(train_trades, config.capital, config.risk_percent)
            score = _candidate_score(train_metrics)
            if best is None or score > best[0]:
                best = (score, tech_weight, threshold, train_metrics)

        assert best is not None
        _, tech_weight, threshold, train_metrics = best
        # Include 220 bars of pre-test context for indicators, but trade only in
        # the actual test window. Features were already computed without leakage.
        context_start = max(0, test_start - 220)
        test_end = test_start + test_bars
        test_frame = frame.iloc[context_start:test_end].reset_index(drop=True)
        local_start = test_start - context_start
        local_end = test_end - context_start - 2
        fold_config = SimulationConfig(
            capital=config.capital,
            risk_percent=config.risk_percent,
            fee_bps=config.fee_bps,
            slippage_bps=config.slippage_bps,
            max_holding_bars=config.max_holding_bars,
            tech_weight=tech_weight,
            threshold=threshold,
        )
        test_trades = simulate_strategy(test_frame, fold_config, start_index=local_start, end_index=local_end)
        test_metrics = metrics_from_trades(test_trades, config.capital, config.risk_percent)
        for trade in test_trades:
            trade["walk_forward_fold"] = fold_id
        oos_trades.extend(test_trades)

        folds.append({
            "fold": fold_id,
            "train_start": pd.Timestamp(frame.iloc[train_start]["timestamp"]).date().isoformat(),
            "train_end": pd.Timestamp(frame.iloc[test_start - 1]["timestamp"]).date().isoformat(),
            "test_start": pd.Timestamp(frame.iloc[test_start]["timestamp"]).date().isoformat(),
            "test_end": pd.Timestamp(frame.iloc[test_end - 1]["timestamp"]).date().isoformat(),
            "tech_weight": tech_weight,
            "macro_weight": round(1.0 - tech_weight, 2),
            "threshold": threshold,
            "train_expectancy_r": train_metrics.get("expectancy_r", 0.0),
            "train_trades": train_metrics.get("trades", 0),
            "test_expectancy_r": test_metrics.get("expectancy_r", 0.0),
            "test_trades": test_metrics.get("trades", 0),
            "test_win_rate": test_metrics.get("win_rate", 0.0),
        })
        fold_id += 1
        test_start += test_bars

    return {
        "folds": folds,
        "oos_trades": oos_trades,
        "metrics": metrics_from_trades(oos_trades, config.capital, config.risk_percent),
        "note": "Optimización únicamente en ventana train; métricas agregadas sobre ventanas test fuera de muestra.",
    }


def _wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    if total <= 0:
        return 0.0, 0.0
    p = successes / total
    denom = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denom
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denom
    return max(0.0, center - margin), min(1.0, center + margin)


def calibration_table(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    bins = [(20, 50), (50, 60), (60, 70), (70, 80), (80, 95)]
    rows: list[dict[str, Any]] = []
    for low, high in bins:
        sample = [t for t in trades if low <= float(t["confidence"]) < high]
        if not sample:
            continue
        wins = sum(float(t["r_multiple"]) > 0 for t in sample)
        lower, upper = _wilson_interval(wins, len(sample))
        rows.append({
            "confidence_band": f"{low}-{high}%",
            "n": len(sample),
            "observed_win_rate": round(wins / len(sample) * 100.0, 2),
            "interval_low": round(lower * 100.0, 2),
            "interval_high": round(upper * 100.0, 2),
            "mean_r": round(float(np.mean([t["r_multiple"] for t in sample])), 4),
        })
    return rows


# ---------- Monte Carlo ----------


def _longest_loss_streak(values: list[float]) -> int:
    current = 0
    longest = 0
    for value in values:
        if value <= 0:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def monte_carlo_analysis(
    trades: list[dict[str, Any]],
    capital: float,
    risk_percent: float,
    runs: int = 1000,
    seed: int = 42,
) -> dict[str, Any]:
    if len(trades) < 5 or runs <= 0:
        return {"runs": 0, "note": "Muestra insuficiente para Monte Carlo."}
    rng = random.Random(seed)
    source = [float(t["r_multiple"]) for t in trades]
    risk_fraction = risk_percent / 100.0
    endings: list[float] = []
    drawdowns: list[float] = []
    streaks: list[int] = []

    for _ in range(runs):
        sampled = [rng.choice(source) for _ in source]
        equity = capital
        curve = [equity]
        for r_value in sampled:
            equity += equity * risk_fraction * r_value
            curve.append(equity)
        endings.append(equity)
        drawdowns.append(abs(_max_drawdown(curve)) * 100.0)
        streaks.append(_longest_loss_streak(sampled))

    return {
        "runs": runs,
        "sample_trades": len(source),
        "ending_capital_p05": round(float(np.percentile(endings, 5)), 2),
        "ending_capital_median": round(float(np.percentile(endings, 50)), 2),
        "ending_capital_p95": round(float(np.percentile(endings, 95)), 2),
        "max_drawdown_p50": round(float(np.percentile(drawdowns, 50)), 2),
        "max_drawdown_p95": round(float(np.percentile(drawdowns, 95)), 2),
        "probability_drawdown_10pct": round(sum(dd >= 10 for dd in drawdowns) / runs * 100.0, 2),
        "probability_drawdown_20pct": round(sum(dd >= 20 for dd in drawdowns) / runs * 100.0, 2),
        "loss_streak_p95": int(math.ceil(float(np.percentile(streaks, 95)))),
        "note": "Bootstrap de múltiplos R históricos; no modela cambios estructurales futuros.",
    }


# ---------- Public orchestration ----------


def run_quant_research(
    symbol: str,
    asset_frame: pd.DataFrame,
    proxy_frames: dict[str, pd.DataFrame],
    config: SimulationConfig,
    walk_forward: bool = True,
    monte_carlo_runs: int = 1000,
) -> dict[str, Any]:
    prepared = prepare_research_frame(symbol, asset_frame, proxy_frames)
    if len(prepared) < 300:
        raise ValueError("Se requieren al menos 300 velas históricas para el laboratorio cuantitativo.")

    trades = simulate_strategy(prepared, config)
    metrics = metrics_from_trades(trades, config.capital, config.risk_percent)
    wf = walk_forward_analysis(prepared, config) if walk_forward else {"folds": [], "oos_trades": [], "metrics": {}, "note": "Walk-forward desactivado."}
    oos_trades = wf.get("oos_trades", [])
    calibration_source = oos_trades if len(oos_trades) >= 10 else trades
    calibration = calibration_table(calibration_source)
    mc_source = oos_trades if len(oos_trades) >= 10 else trades
    monte_carlo = monte_carlo_analysis(mc_source, config.capital, config.risk_percent, runs=monte_carlo_runs)

    public_trades = trades[-250:]
    # Keep the response compact: the raw OOS trades are represented by fold and
    # aggregate metrics, while the main simulation trade journal is inspectable.
    wf_public = {key: value for key, value in wf.items() if key != "oos_trades"}
    return {
        "version": CORE_VERSION,
        "symbol": symbol.upper(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "methodology": {
            "signal_timing": "Señal al cierre; entrada en la apertura siguiente.",
            "technical_core": "75% Diario + 25% última semana completada.",
            "macro_core": "Proxies históricos DXY, US10Y, VIX, SPY y QQQ; carry-forward solo desde observaciones pasadas.",
            "news": "Excluidas del backtest v1 por falta de feed histórico reproducible y timestamped.",
            "intrabar_rule": "Si SL y TP aparecen en la misma vela sin secuencia intradía, gana SL (regla conservadora).",
            "position_rule": "Sin posiciones solapadas; 50% en TP1 y 50% restante hacia TP2 con stop a breakeven.",
            "confidence": "Heurística en señal; calibración empírica reportada por separado, preferentemente OOS.",
        },
        "config": {
            "capital": config.capital,
            "risk_percent": config.risk_percent,
            "fee_bps": config.fee_bps,
            "slippage_bps": config.slippage_bps,
            "max_holding_bars": config.max_holding_bars,
            "tech_weight": config.tech_weight,
            "macro_weight": config.macro_weight,
            "threshold": config.threshold,
        },
        "data": {
            "bars": len(prepared),
            "start": pd.Timestamp(prepared.iloc[0]["timestamp"]).date().isoformat(),
            "end": pd.Timestamp(prepared.iloc[-1]["timestamp"]).date().isoformat(),
        },
        "metrics": metrics,
        "regimes": regime_breakdown(trades),
        "walk_forward": wf_public,
        "calibration": {
            "source": "out_of_sample" if len(oos_trades) >= 10 else "full_sample_fallback",
            "rows": calibration,
            "warning": None if len(oos_trades) >= 10 else "Muestra OOS insuficiente; tabla basada en la muestra completa y no debe interpretarse como probabilidad validada.",
        },
        "monte_carlo": {
            **monte_carlo,
            "source": "out_of_sample" if len(oos_trades) >= 10 else "full_sample_fallback",
        },
        "trades": public_trades,
    }
