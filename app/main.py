from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.models import AnalysisRequest, AnalysisResponse
from app.service import TradingAnalysisService


app = FastAPI(
    title="Trading Intelligence",
    version="0.1.0",
    description="Motor de confluencia para análisis técnico, macro, noticias, sentimiento, psicología y riesgo.",
)
service = TradingAnalysisService()
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "trading-intelligence"}


@app.post("/api/analyze", response_model=AnalysisResponse)
async def analyze(req: AnalysisRequest):
    try:
        return await service.analyze(req)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


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
