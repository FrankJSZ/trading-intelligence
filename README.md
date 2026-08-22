# Trading Intelligence

Aplicación local de análisis de trading que combina datos reales de mercado, análisis técnico multitemporal, noticias, sentimiento, macro-proxies, psicología del trader y gestión de riesgo para producir una salida **COMPRAR / VENDER / ESPERAR**.

> **Aviso:** proyecto educativo y de investigación. No constituye asesoramiento financiero ni garantiza resultados futuros.

## Qué incluye

- Datos de mercado reales desde Yahoo Finance sin API key.
- Temporalidades 1H, 4H (resampleada), Diario y Semanal.
- EMA 20/50/200, RSI, MACD, ATR, ADX, volumen relativo, soportes y resistencias.
- Clasificación de régimen: tendencia/rango y volatilidad.
- Noticias recientes de Yahoo Finance, puntaje de credibilidad/relevancia y sentimiento de titulares.
- Traducción automática de los titulares al español para la interfaz, conservando el título original para trazabilidad.
- Contexto macro mediante DXY, US10Y, VIX, SPY, QQQ y oro.
- Cuestionario de psicología: FOMO, confirmación, revenge trading, exceso de confianza, miedo, avaricia y disciplina.
- Motor institucional ponderado con veto psicológico y ajuste por volatilidad.
- Entry, Stop Loss, TP1/TP2, R:R, riesgo máximo y position sizing.
- Probabilidad histórica condicionada (descriptiva, no garantía).
- Endpoint de correlaciones con benchmarks.
- Backtest base de 5 años con win rate, profit factor, Sharpe, drawdown y expectancy.
- Autoactualización configurable del análisis principal.
- Dashboard web local.
- Docker y CI con pytest.

## Inicio rápido

### Python

Compatible con Python 3.12 y 3.14. En Windows se recomienda usar siempre `python -m pip` y `python -m uvicorn` para garantizar que los comandos se ejecuten dentro del entorno virtual activo.

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

Abre `http://127.0.0.1:8000`.

### Docker

```bash
cp .env.example .env
docker compose up --build
```

## Símbolos comunes

- `BTC-USD`, `ETH-USD`
- `AAPL`, `NVDA`, `SPY`, `QQQ`
- `EURUSD=X`, `GBPUSD=X`
- `GC=F` (oro), `CL=F` (petróleo)

## API

- `POST /api/analyze`
- `GET /api/backtest/{symbol}`
- `GET /api/correlations/{symbol}`
- Swagger: `http://127.0.0.1:8000/docs`

## Noticias en español

El motor conserva el titular original para calcular relevancia y sentimiento con el clasificador actual. Después del análisis, el título mostrado en el dashboard se traduce automáticamente al español mediante un proveedor externo sin API key. Las traducciones se guardan temporalmente en memoria para evitar repetir llamadas. Si la traducción falla o el proveedor está temporalmente bloqueado, la aplicación no se detiene: muestra el titular original como fallback.

## Limitaciones importantes

1. El feed gratuito de Yahoo Finance puede tener retrasos y límites; no es un feed institucional de ejecución.
2. El sentimiento usa un clasificador léxico transparente de titulares; puede sustituirse posteriormente por FinBERT u otro modelo financiero.
3. La traducción automática depende de un servicio externo y puede fallar o aplicar límites; el título original se conserva como respaldo.
4. El fundamental profundo por empresa/activo queda como extensión; el MVP usa contexto macro keyless y reproducible.
5. Los pesos del motor son iniciales y deben calibrarse con walk-forward/out-of-sample antes de usar capital real.
6. No hay ejecución automática con broker/exchange. Esto es intencional hasta validar señal, riesgo y controles.

## Roadmap institucional

- Proveedor premium y websocket en tiempo real.
- Calendario macro oficial y discursos de bancos centrales.
- Fundamentals por tipo de activo.
- FinBERT/LLM para clasificación de eventos financieros con fuente primaria.
- Detección avanzada de patrones y volume profile.
- Walk-forward, Monte Carlo y calibración de probabilidades.
- Portfolio risk: exposición agregada, correlación, VaR/CVaR y drawdown.
- Paper trading y journal.
- Integración con broker/exchange solo después de controles y validación.
