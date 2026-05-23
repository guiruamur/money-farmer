# Diseño — Motor de backtesting

**Fecha:** 2026-05-23
**Estado:** aprobado en brainstorming, pendiente de plan de implementación
**Relacionado:** `2026-05-12-crypto-farmer-fase1-design.md` (Fase 2 — métricas)

## 1. Contexto y objetivo

`crypto-farmer` corre hoy en *forward testing* (paper trading en vivo): cada
ciclo decide en tiempo real y hay que esperar días para acumular resultados.
Eso hace lentísimo iterar la estrategia y dejó un hueco de aprendizaje cuando
el bot estuvo caído.

El **backtesting** permite correr exactamente el mismo sistema sobre un rango
histórico de fechas, "como si fuera entonces", y obtener resultados en minutos
en vez de semanas. Sirve a los dos objetivos a largo plazo del proyecto:

- **Ganar dinero (A):** herramienta para entender por qué la estrategia
  pierde y validar mejoras rápido.
- **Aprender / web3 (B):** el mismo motor evaluará estrategias on-chain en el
  futuro (solo cambia la fuente de datos).

Decisiones de producto ya tomadas (brainstorming 2026-05-23):

- Produce **tanto un informe de rendimiento como una memoria RAG separada**.
- Usa **la IA real** (Qwen vía Ollama) con **caché**, no una versión simplificada.
- Reutiliza el `Cycle.run()` de producción (no se duplica la lógica).

## 2. Alcance

**Incluye:**

- Un "reloj" inyectable que sustituye `datetime.now()` en el camino de decisión.
- Una fuente de datos de mercado histórica que sirve velas hasta un instante dado.
- Un runner que itera el reloj vela a vela reutilizando `Cycle.run()`.
- Medición de outcomes con velas futuras ya conocidas (reutiliza `OutcomeService`).
- Aislamiento total de los datos del backtest respecto al sistema en vivo.
- Caché persistente de respuestas del LLM.
- Un informe con métricas clave y comparación con HODL.
- Un comando `python -m crypto_farmer backtest`.

**No incluye (YAGNI, se añade después si hace falta):**

- Métricas financieras avanzadas (Sharpe, profit factor, expectancy).
- Dashboard web (Fase 2 posterior).
- Optimización de hiperparámetros / barridos de configuración.
- Backtesting de estrategias web3 (futuro; el motor queda preparado).
- Checkpointing/reanudación de runs largos (el caché de LLM ya mitiga el coste de re-correr).

## 3. Arquitectura y componentes

Piezas nuevas, todas con una responsabilidad clara:

| Componente | Responsabilidad | Depende de |
|---|---|---|
| `Clock` (protocolo) | Devolver "ahora" | — |
| `SystemClock` | `now()` = hora real (producción) | — |
| `BacktestClock` | `now()` = instante fijado por el runner | — |
| `HistoricalMarketSource` | Servir velas ≤ `clock.now()` y el ticker de la vela en curso | `Clock`, almacén OHLCV |
| `OhlcvStore` | Descargar/cachear OHLCV de un rango por par | CCXT |
| `CachedLLMClient` | Cachear respuestas del LLM por hash de prompt | `OllamaClient` |
| `BacktestRunner` | Orquestar el bucle y producir el informe | todos los anteriores + `Cycle` |
| `BacktestReport` | Calcular y renderizar métricas | `Storage` del run |

El `Cycle`, el prefiltro, el prompt, el parser, el `PaperTrader` y el
`OutcomeService` se reutilizan **sin cambios de lógica** (solo reciben el reloj
por inyección).

## 4. El reloj inyectable

Protocolo mínimo:

```python
class Clock(Protocol):
    def now(self) -> datetime: ...

class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)

class BacktestClock:
    def __init__(self) -> None:
        self.current: datetime  # fijado por el runner antes de cada paso
    def now(self) -> datetime:
        return self.current
```

**Cambios en producción (los únicos):**

- `cycle.py`: sustituir `datetime.now(timezone.utc)` por `self._deps.clock.now()`
  en los cuatro puntos actuales (ventana de noticias, render del prompt,
  timestamp de la entrada de memoria, `schedule_measurements`). Añadir `clock`
  a `CycleDeps`.
- `storage.py`: inyectar `clock` y usar `clock.now()` donde hoy estampa
  `datetime.now()` (`start_cycle`, `finish_cycle`, `save_signal`). Así las
  señales y ciclos del backtest llevan el timestamp histórico, no el real.
- `app.py`: construir `SystemClock()` e inyectarlo. **Comportamiento en vivo
  idéntico al actual.**

Este refactor es deuda técnica buena: hace el camino de decisión testeable en
el tiempo, no solo backtesteable.

## 5. Fuente de datos histórica

`OhlcvStore` descarga, vía CCXT, el OHLCV de cada par para el rango
`[desde − margen_lookback, hasta + 24h]` (el margen pasado da contexto a la
primera vela; el +24h permite medir los outcomes a 24h del último día) y lo
cachea en disco (`data/backtest/ohlcv/<par>-<timeframe>.parquet` o similar)
para no re-descargar entre runs.

`HistoricalMarketSource` implementa la interfaz `MarketDataSource`:

- `fetch_ohlcv(pair, timeframe, lookback)` → las últimas `lookback` velas con
  `timestamp ≤ clock.now()`. **Nunca devuelve velas futuras** (sería mirar el
  futuro: el bug clásico de los backtests).
- `fetch_ticker(pair)` → `Ticker` con el cierre de la vela cuyo periodo
  contiene `clock.now()`.

## 6. El runner y el bucle

```
1. Cargar/descargar OHLCV del rango (+ márgenes) para todos los pares.
2. Para cada vela de 15m entre `desde` y `hasta`:
     clock.current = T
     Cycle.run()        # prefiltra, consulta IA (caché), guarda señal @T,
                        # programa outcomes @ T+1h/+4h/+24h, opera paper
3. Drenado de outcomes: avanzar el reloj 24h más allá de `hasta`,
   ejecutando solo OutcomeService.run_due_jobs() en cada paso, para medir
   con las velas futuras ya cacheadas.
4. Generar el informe.
```

El análisis se hace **una vez por vela** (más fino no aporta: los datos solo
cambian cada 15m). El backtest corre **sin noticias** (no hay histórico de
CryptoPanic; se usa la fuente vacía, igual que el live hoy).

## 7. Outcomes

Sin cambios en `OutcomeService`. Cuando un job vence (`due_at ≤ clock.now()`),
`run_due_jobs()` lo mide con `fetch_ticker`, que en backtest devuelve el precio
histórico de ese instante (futuro ya cacheado). Reutiliza la misma lógica de
veredicto (`_verdict`) que en vivo.

## 8. Aislamiento de datos

Cada ejecución crea `data/backtest/<run_id>/` con:

- su propia base de datos SQLite (`crypto_farmer.db`),
- su propia memoria RAG (`chroma/`),
- el informe (`report.md`).

El sistema en vivo (`data/crypto_farmer.db`, `data/chroma/`) **no se toca
jamás**. `run_id` será el rango + un sello temporal (p.ej.
`2026-05-17_2026-05-22__20260523-1900`) para poder comparar runs.

Opción `--export-rag`: al terminar, copia las entradas de memoria del backtest
a la RAG en vivo (por defecto **no** lo hace, para no contaminar).

## 9. Caché de la IA

`CachedLLMClient` envuelve a `OllamaClient`:

- Clave = hash SHA-256 del prompt renderizado completo.
- Valor = respuesta cruda del LLM.
- Almacén persistente en `data/backtest/llm_cache.sqlite`, **compartido entre
  runs** (la misma situación da la misma respuesta → re-correr periodos
  solapados es casi instantáneo y reproducible).
- Miss → llama a Ollama y guarda; hit → devuelve lo cacheado.

La primera pasada de un periodo nuevo es lenta (una llamada al LLM por par que
pase el prefiltro); las siguientes son rápidas.

## 10. El informe

`BacktestReport` lee la base de datos del run y calcula:

- **Señales:** total y desglose BUY/SELL/HOLD; cuántas se habrían entregado.
- **Aciertos:** win-rate por horizonte (1h / 4h / 24h).
- **Paper trading:** P&L total y % de retorno; nº de operaciones cerradas
  (ganadoras/perdedoras); caja fuerte acumulada; *max drawdown*; bancarrotas.
- **Benchmark HODL:** retorno de comprar a partes iguales los pares al inicio
  del rango y aguantar hasta el final. Responde a "¿la IA bate a no hacer nada?".

Salida: resumen por consola + `report.md` en la carpeta del run.

## 11. Cómo se lanza

```
python -m crypto_farmer backtest --from 2026-05-17 --to 2026-05-22 \
    [--pairs BTC/USDT,ETH/USDT] [--export-rag]
```

- `--from` / `--to`: rango de fechas (ISO).
- `--pairs`: por defecto, los de `config.yaml`.
- `--export-rag`: exportar la memoria del run a la RAG en vivo (off por defecto).

El resto de parámetros (modelo, timeframe, lookback, sizing del paper trader…)
se leen de `config.yaml`, igual que el modo en vivo.

## 12. Testing (TDD)

- `BacktestClock`: `now()` refleja `current`; el runner lo avanza correctamente.
- `HistoricalMarketSource`: con OHLCV sintético, `fetch_ohlcv` nunca devuelve
  velas futuras y respeta el `lookback`; `fetch_ticker` da la vela en curso.
- `OhlcvStore`: cachea y no re-descarga (CCXT mockeado).
- `CachedLLMClient`: miss → llama y guarda; hit → no llama; persistencia.
- `BacktestRunner` end-to-end: con un LLM falso determinista + OHLCV sintético,
  produce el número esperado de señales y outcomes, y aísla los datos en
  `data/backtest/<run_id>/`.
- `BacktestReport`: métricas y HODL verificadas con datasets pequeños.
- Regresión: el camino en vivo con `SystemClock` se comporta igual que antes
  (tests existentes de `cycle`/`storage` siguen verdes).

## 13. Decisiones y notas

- **Una pasada por vela de 15m**, no por minuto.
- **Sin noticias** en backtest (no hay histórico de CryptoPanic).
- El refactor del reloj es el único cambio en código de producción; se hace
  con tests y en una rama aparte, sin tocar el bot que está en forward testing.
- Métricas avanzadas y dashboard quedan fuera; se priorizan P&L, win-rate,
  drawdown y HODL por ser las que responden "¿esto funciona?".
