# Trading Intelligence

Aplicación local de análisis de trading que combina datos reales de mercado, análisis técnico multitemporal, noticias, macro-proxies, psicología del trader y gestión de riesgo para producir una lectura de mercado **COMPRAR / VENDER / ESPERAR** y una decisión operativa separada.

> **Aviso:** proyecto educativo y de investigación. No constituye asesoramiento financiero ni garantiza resultados futuros.

## Fase 2.5

La consolidación 2.5 separa explícitamente **señal de mercado** y **ejecución**:

- Técnico, macro y noticias forman el score direccional.
- El sentimiento derivado de esas mismas noticias se muestra como contexto, pero tiene peso 0 para evitar doble conteo.
- La psicología no vuelve alcista o bajista al mercado: puede bloquear una ejecución o reducir riesgo.
- La respuesta distingue `market_decision`, `decision` y `execution_status`.

También añade:

- gráfico de velas 1H / 4H / 1D / 1W con Entrada, SL, TP1, TP2, soporte y resistencia;
- historial local persistente en SQLite;
- watchlist comparativa de hasta 8 activos;
- frontend modular (`css/` + `js/`) en lugar de un único HTML monolítico;
- autoactualización del análisis principal;
- noticias traducidas al español conservando el título original;
- pruebas Python y validación sintáctica de módulos JavaScript en CI.

## Datos y análisis

- Yahoo Finance keyless para OHLCV y titulares.
- Fallback entre `query1` y `query2`.
- Temporalidades 1H, 4H, Diario y Semanal.
- EMA 20/50/200, RSI, MACD, ATR, ADX, volumen relativo, soportes y resistencias.
- Régimen de tendencia/rango y volatilidad.
- Proxy macro con DXY, US10Y, VIX, SPY, QQQ y oro.
- Noticias ponderadas por relevancia, actualidad y credibilidad.
- Psicología: FOMO, confirmación, revenge trading, exceso de confianza, miedo, avaricia y disciplina.
- Entry, Stop Loss, TP1/TP2, R:R, riesgo máximo y position sizing.
- Correlaciones contra benchmarks.
- Backtest baseline de 5 años.

## Inicio rápido

### Windows

```bat
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

Abre `http://127.0.0.1:8000`.

La base local se crea automáticamente en:

```text
data/trading_intelligence.db
```

Puedes cambiarla con la variable de entorno `TI_DB_PATH`.

### Docker

```bash
cp .env.example .env
docker compose up --build
```

El directorio local `./data` se monta en `/app/data` para conservar el historial entre reinicios.

## API

- `POST /api/analyze`
- `GET /api/chart/{symbol}?timeframe=1D&limit=120`
- `POST /api/watchlist`
- `GET /api/history?symbol=BTC-USD&limit=50`
- `GET /api/backtest/{symbol}`
- `GET /api/correlations/{symbol}`
- Swagger: `http://127.0.0.1:8000/docs`

## Noticias en español

El motor analiza relevancia y sentimiento sobre el titular original. Después traduce el título al español para presentación. Si el traductor externo falla o aplica límites, la aplicación continúa con el titular original.

## Limitaciones importantes

1. Yahoo Finance puede tener retrasos, límites o cambios de endpoint; no es un feed institucional de ejecución.
2. El sentimiento actual deriva de titulares y no es todavía una fuente independiente de posicionamiento/mercado.
3. La “confianza” sigue siendo heurística; no debe interpretarse como probabilidad calibrada.
4. El backtest actual sigue siendo un baseline EMA/RSI y no representa todavía el motor completo.
5. El contexto macro usa proxies de mercado y no sustituye datos oficiales de bancos centrales/agencias estadísticas.
6. No existe ejecución automática con broker/exchange.

## Siguiente etapa cuantitativa

- backtest del motor completo;
- walk-forward y separación temporal train/validation/test;
- calibración de probabilidades;
- Sortino, Calmar, MAE/MFE y Monte Carlo;
- fuentes macro/fundamentales oficiales;
- portfolio risk y paper trading.
