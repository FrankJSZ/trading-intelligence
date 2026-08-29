# Trading Intelligence

Aplicación local de análisis de trading que combina datos reales de mercado, análisis técnico multitemporal, noticias, macro-proxies, psicología del trader y gestión de riesgo para producir una lectura de mercado **COMPRAR / VENDER / ESPERAR** y una decisión operativa separada.

> **Aviso:** proyecto educativo y de investigación. No constituye asesoramiento financiero ni garantiza resultados futuros.

## Fase 3 — Laboratorio cuantitativo

La Fase 3 añade un entorno reproducible para medir el núcleo del sistema con histórico, sin presentar la heurística como una probabilidad validada.

### Quant Core v1

El backtest cuantitativo usa:

- técnico histórico: 75% Diario + 25% última semana **completada**;
- macro histórico: DXY, US10Y, VIX, SPY y QQQ;
- señal generada al cierre y entrada simulada en la apertura siguiente;
- SL basado en ATR / distancia mínima;
- salida 50% en TP1 y 50% restante hacia TP2 con stop a breakeven;
- comisiones y slippage configurables;
- sin posiciones solapadas;
- regla conservadora: si SL y TP aparecen en la misma vela sin secuencia intradía, se asume SL primero.

Las noticias históricas **no se incluyen** en Quant Core v1 porque el feed gratuito actual no permite reconstruir de forma suficientemente reproducible varios años de titulares con timestamps verificables. El laboratorio lo muestra explícitamente en lugar de imputar datos inexistentes.

### Métricas

- trades, win rate, expectancy y profit factor;
- retorno total y capital final;
- max drawdown;
- Sharpe, Sortino y Calmar;
- R medio / mediano;
- TP1/TP2 hit rate;
- MAE y MFE;
- holding medio;
- equity curve;
- resultados separados por régimen.

### Walk-forward

El laboratorio prueba combinaciones de peso Técnico/Macro y umbral **solo en la ventana de entrenamiento** y aplica la mejor configuración a la siguiente ventana fuera de muestra. Los resultados agregados `OOS` se muestran separados de la simulación completa.

### Calibración de confianza

La confianza del motor sigue siendo heurística. Fase 3 construye bandas de confianza y reporta:

- tamaño de muestra `n`;
- win rate observado;
- intervalo de Wilson aproximado al 95%;
- R medio.

Cuando existe muestra OOS suficiente, la tabla usa únicamente trades fuera de muestra. Si no existe, se marca como `full_sample_fallback` y **no debe interpretarse como probabilidad validada**.

### Monte Carlo

Se realiza bootstrap de los múltiplos R históricos para estimar:

- capital final P05 / mediana / P95;
- drawdown mediano y P95;
- probabilidad de drawdown ≥10% y ≥20%;
- racha de pérdidas P95.

Monte Carlo no elimina el riesgo de cambio estructural del mercado; solo cuantifica sensibilidad a la secuencia de resultados observados.

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
- frontend modular (`css/` + `js/`);
- autoactualización del análisis principal;
- noticias traducidas al español conservando el título original.

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
- Backtest baseline de 5 años, conservado como control de referencia.

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

El directorio local `./data` se monta en `/app/data` para conservar historial y corridas cuantitativas entre reinicios.

## API

- `POST /api/analyze`
- `GET /api/chart/{symbol}?timeframe=1D&limit=120`
- `POST /api/watchlist`
- `GET /api/history?symbol=BTC-USD&limit=50`
- `POST /api/quant/backtest`
- `GET /api/quant/runs?symbol=BTC-USD&limit=20`
- `GET /api/quant/runs/{run_id}`
- `GET /api/backtest/{symbol}` (baseline legado)
- `GET /api/correlations/{symbol}`
- Swagger: `http://127.0.0.1:8000/docs`

## Noticias en español

El motor analiza relevancia y sentimiento sobre el titular original. Después traduce el título al español para presentación. Si el traductor externo falla o aplica límites, la aplicación continúa con el titular original.

## Limitaciones importantes

1. Yahoo Finance puede tener retrasos, límites o cambios de endpoint; no es un feed institucional de ejecución.
2. El sentimiento actual deriva de titulares y no es todavía una fuente independiente de posicionamiento/mercado.
3. La confianza en vivo sigue siendo heurística; la tabla de calibración debe leerse según su fuente (`out_of_sample` o fallback full-sample).
4. Quant Core v1 no reconstruye noticias históricas ni el componente intradía 1H/4H del motor live; usa Diario + semana completada para obtener una base histórica reproducible de 3–5 años.
5. Los proxies macro no sustituyen series oficiales de bancos centrales/agencias estadísticas.
6. Un backtest positivo no demuestra que el rendimiento continuará fuera de muestra futura.
7. No existe ejecución automática con broker/exchange.

## Próximos pasos

- proveedor histórico de noticias/eventos con timestamps verificables;
- datos macro oficiales y revision-aware;
- validación multi-activo y por clase de activo;
- sensitivity analysis más amplio de pesos/umbrales;
- paper trading con comparación señal vs resultado real;
- portfolio risk, VaR/CVaR y stress testing.
