from __future__ import annotations

import asyncio
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.engines.macro import PROXIES
from app.models import AnalysisRequest, AnalysisResponse, QuantBacktestRequest, WatchlistRequest
from app.quant.research import SimulationConfig, run_quant_research
from app.service import TradingAnalysisService
from app.storage.quant import QuantRunStore


app = FastAPI(
    title="Trading Intelligence",
    version="0.3.0",
    description=(
        "Motor de confluencia para análisis técnico, macro, noticias, psicología, "
        "riesgo, watchlist, historial y laboratorio cuantitativo."
    ),
)
service = TradingAnalysisService()
quant_store = QuantRunStore()
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "trading-intelligence", "version": "0.3.0"}


@app.post("/api/analyze", response_model=AnalysisResponse)
async def analyze(req: AnalysisRequest):
    try:
        return await service.analyze(req)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/chart/{symbol}")
async def chart(
    symbol: str,
    timeframe: str = Query(default="1D", pattern="^(1H|4H|1D|1W)$"),
    limit: int = Query(default=120, ge=30, le=300),
):
    try:
        return await service.chart(symbol, timeframe=timeframe, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/watchlist")
async def watchlist(req: WatchlistRequest):
    try:
        return await service.watchlist(req)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/history")
async def history(
    symbol: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
):
    try:
        return service.recent_history(symbol=symbol, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


async def _historical_quant_inputs(req: QuantBacktestRequest):
    async def load_proxy(name: str, ticker: str):
        frame = await service.provider.candles(ticker, "1d", "5y")
        return name, frame

    asset_task = service.provider.candles(req.symbol, "1d", "5y")
    proxy_tasks = [load_proxy(name, ticker) for name, ticker in PROXIES.items()]
    asset_frame, *loaded = await asyncio.gather(asset_task, *proxy_tasks)
    proxies = dict(loaded)

    latest = pd.to_datetime(asset_frame["timestamp"], utc=True).max()
    cutoff = latest - pd.DateOffset(years=req.years)
    asset_frame = asset_frame[pd.to_datetime(asset_frame["timestamp"], utc=True) >= cutoff].reset_index(drop=True)
    trimmed = {}
    for name, frame in proxies.items():
        timestamps = pd.to_datetime(frame["timestamp"], utc=True)
        trimmed[name] = frame[timestamps >= cutoff].reset_index(drop=True)
    return asset_frame, trimmed


@app.post("/api/quant/backtest")
async def quant_backtest(req: QuantBacktestRequest):
    try:
        asset_frame, proxy_frames = await _historical_quant_inputs(req)
        config = SimulationConfig(
            capital=req.capital,
            risk_percent=req.risk_percent,
            fee_bps=req.fee_bps,
            slippage_bps=req.slippage_bps,
            max_holding_bars=req.max_holding_bars,
        )
        result = run_quant_research(
            req.symbol,
            asset_frame,
            proxy_frames,
            config,
            walk_forward=req.walk_forward,
            monte_carlo_runs=req.monte_carlo_runs,
        )
        run_id = quant_store.save(result)
        return {"run_id": run_id, **result}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/quant/runs")
async def quant_runs(
    symbol: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
):
    try:
        return {"items": quant_store.recent(symbol=symbol, limit=limit)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/quant/runs/{run_id}")
async def quant_run(run_id: int):
    try:
        result = quant_store.get(run_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Corrida cuantitativa no encontrada.")
        return {"run_id": run_id, **result}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/backtest/{symbol}")
async def backtest(symbol: str):
    try:
        return await service.backtest(symbol)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/correlations/{symbol}")
async def correlation(symbol: str):
    try:
        return await service.correlation(symbol.upper())
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/", include_in_schema=False)
async def dashboard():
    html = (static_dir / "index.html").read_text(encoding="utf-8")
    enhancement = '<script type="module" src="/static/js/quant.js?v=30"></script>'
    if enhancement not in html:
        html = html.replace("</body>", f"{enhancement}\n</body>")
    return HTMLResponse(html)
