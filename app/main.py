from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.models import AnalysisRequest, AnalysisResponse, WatchlistRequest
from app.service import TradingAnalysisService


app = FastAPI(
    title="Trading Intelligence",
    version="0.2.5",
    description=(
        "Motor de confluencia para análisis técnico, macro, noticias, "
        "psicología, riesgo, watchlist e historial local."
    ),
)
service = TradingAnalysisService()
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "trading-intelligence", "version": "0.2.5"}


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


@app.get("/api/backtest/{symbol}")
async def backtest(symbol: str):
    try:
        return await service.backtest(symbol)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/correlations/{symbol}")
async def correlation(symbol: str):
    try:
        return await service.correlation(symbol)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/", include_in_schema=False)
async def dashboard():
    return FileResponse(static_dir / "index.html")
