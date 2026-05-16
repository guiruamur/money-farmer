# crypto-farmer — Diseño de la Fase 1 (señales con IA local)

- **Fecha:** 2026-05-12
- **Estado:** Diseño aprobado, pendiente de plan de implementación
- **Autor:** guiruamur
- **Proyecto:** `money-farmer` (paquete principal: `crypto_farmer`)

## 1. Contexto y objetivo

El usuario quiere construir una aplicación de inversión en criptomonedas que use una IA local como cerebro de decisión. El objetivo a largo plazo es trading automatizado real. El usuario tiene experiencia previa con IA local (Ollama, llama.cpp), pero no con ML/Data Science ni con trading manual.

Por experiencia y riesgo, **no es realista saltar a trading automatizado real como primer paso**. Se acuerda un camino por fases en el que cada fase es un sistema funcional por sí mismo y valida la siguiente. Este documento especifica la **Fase 1: generación de señales con aprendizaje in-context y memoria selectiva (RAG)**, con arquitectura preparada para evolucionar a paper trading (Fase 2), trading real acotado (Fase 3) y aprendizaje avanzado (Fase 4).

### 1.1 Alcance de la Fase 1

**Incluye:**

- Servicio Python local que cada 15 min toma datos de mercado de un universo configurable (por defecto top 10-20 cripto por capitalización), calcula indicadores técnicos, recoge titulares de noticias relevantes, aplica una pre-criba determinista, invoca a un LLM local vía Ollama sobre los pares que la pasan, valida la respuesta JSON y entrega las señales con confianza suficiente por Telegram.
- Sistema de aprendizaje **Nivel 1 (in-context feedback) + Nivel 2 (RAG sobre memoria propia)**: cada señal queda persistida con su contexto, y se mide su outcome a 1h, 4h y 24h. El LLM ve sus señales recientes y situaciones pasadas similares en cada nueva decisión.
- Persistencia local en SQLite (datos estructurados) y ChromaDB (vectores).
- Bot de Telegram como canal único de entrega y panel de control.

**No incluye en Fase 1 (explícito):**

- No ejecuta órdenes reales ni simuladas (eso es Fase 2/3).
- No tiene UI web (Fase 2 la añadirá cuando haya P&L que visualizar).
- No reentrena modelos (Fase 4).
- No usa datos on-chain ni sentimiento social (Fase 5).

### 1.2 Hardware objetivo

- CPU: Intel i7 9700
- RAM: 32 GB DDR4
- GPU: NVIDIA RTX 3070 (8 GB VRAM)

Este hardware es **holgado** para una IA local que decide cada 15 min sobre 15-20 pares con pre-criba. No sería suficiente para LLMs grandes operando cada segundo.

## 2. Arquitectura general

### 2.1 Enfoque elegido

**Monolito modular** (un único proceso Python con módulos bien separados e interfaces limpias). Razones:

- Para 15-20 pares cada 15 min, una arquitectura con cola (Redis + workers) sería sobreingeniería.
- Las interfaces claras entre módulos permiten migrar a un pipeline con cola en Fase 4-6 cambiando solo el orquestador, sin reescribir lógica de negocio.
- Más fácil de depurar y desarrollar en local.

Enfoques descartados:

- Pipeline con cola (Redis/RQ/Celery): aporta resiliencia pero la complejidad no se justifica con un ciclo de 15 min.
- Microservicios / Docker Compose: sobreingeniería evidente para Fase 1.

### 2.2 Estructura del proyecto

```
money-farmer/
├── crypto_farmer/              ← paquete principal
│   ├── __init__.py
│   ├── __main__.py             ← entry point: python -m crypto_farmer
│   ├── config.py               ← carga YAML + env vars, dataclasses tipadas
│   ├── scheduler.py            ← APScheduler, dispara ciclo cada 15 min
│   ├── cycle.py                ← orquestador de un ciclo completo
│   ├── data/
│   │   ├── __init__.py
│   │   ├── market.py           ← MarketDataSource (interfaz) + CcxtBinanceSource
│   │   └── news.py             ← NewsSource (interfaz) + CryptoPanicSource
│   ├── analysis/
│   │   ├── __init__.py
│   │   ├── indicators.py       ← cálculo con pandas-ta
│   │   └── prefilter.py        ← reglas deterministas de pre-criba
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── client.py           ← LLMClient (interfaz) + OllamaClient
│   │   ├── prompts.py          ← templates Jinja2
│   │   └── parser.py           ← valida y parsea JSON de respuesta
│   ├── learning/
│   │   ├── __init__.py
│   │   ├── outcomes.py         ← mide qué pasó con el precio 1h/4h/24h después
│   │   ├── feedback.py         ← construye el bloque "tus últimas N señales y resultados"
│   │   ├── situation.py        ← convierte snapshot de mercado en texto vectorizable
│   │   ├── embeddings.py       ← cliente Ollama de embeddings (nomic-embed-text)
│   │   └── memory.py           ← vector store local (ChromaDB)
│   ├── signals/
│   │   ├── __init__.py
│   │   └── models.py           ← dataclasses Signal, Cycle, NewsItem, etc.
│   ├── delivery/
│   │   ├── __init__.py
│   │   ├── notifier.py         ← Notifier (interfaz)
│   │   └── telegram.py         ← TelegramNotifier + comandos del bot
│   ├── storage/
│   │   ├── __init__.py
│   │   └── db.py               ← SQLite (sqlite3 stdlib; SQLAlchemy si crece)
│   ├── metrics.py              ← contadores y latencias en memoria
│   └── logging_setup.py        ← logging estructurado JSON
├── config/
│   ├── config.example.yaml
│   └── prompts/
│       └── analyze_pair.j2     ← template del prompt principal
├── tests/
│   ├── unit/
│   └── integration/
├── data/                       ← SQLite + Chroma + logs (gitignored)
├── docs/
│   └── design/specs/
├── pyproject.toml
├── README.md
└── .env.example
```

### 2.3 Dependencias principales

Todas estables y mantenidas:

- `ccxt` — datos de mercado y, en Fase 3, ejecución de órdenes.
- `pandas`, `pandas-ta` — indicadores técnicos.
- `httpx` — cliente HTTP para Ollama y CryptoPanic.
- `python-telegram-bot` — bot.
- `apscheduler` — scheduler.
- `pydantic` — modelos tipados y validación del JSON del LLM.
- `pyyaml`, `python-dotenv` — configuración.
- `chromadb` — vector store embebido (persistencia en archivo).
- `jinja2` — templates de prompts.
- `pytest`, `pytest-mock`, `respx` — testing.

## 3. Flujo de datos e interfaces

### 3.1 Anatomía de un ciclo de 15 minutos

```
1. Fetch                                                    [~5-10s]
   ├─ MarketDataSource.fetch_ohlcv(pairs, "15m", lookback=200)
   └─ NewsSource.fetch_recent(since=last_cycle)

2. Compute indicators                                       [<1s]
   └─ IndicatorEngine.compute(ohlcv) → DataFrame con RSI, MACD, EMA, BB, ATR, volumen

3. Pre-filter                                               [<1s]
   └─ Prefilter.select(pairs_with_indicators) → lista de pares "interesantes"

4. Pair memory & feedback                                   [~1-2s]
   ├─ Para cada par seleccionado:
   │   ├─ situation = Situation.from_snapshot(pair, indicators)
   │   ├─ embedding = Embeddings.embed(situation.as_text())
   │   └─ memory_hits = Memory.search(embedding, k=5)
   └─ recent_feedback = Feedback.build(last_n=20)

5. LLM reasoning                                            [~3-8s × N pares filtrados]
   └─ Para cada par filtrado:
       └─ LLMClient.analyze(par, indicadores, news, memory_hits, recent_feedback) → Signal

6. Persist & deliver                                        [<1s]
   ├─ Storage.save_cycle(cycle)
   ├─ Storage.save_signals(signals)
   ├─ Memory.add(situation, signal)
   ├─ Outcomes.schedule_measurements(signal)
   └─ Notifier.deliver(signals)

7. Background: medición de outcomes                         [pasivo]
   └─ Cada vez que vence un job: lee precio actual, calcula retorno desde la señal,
      actualiza signal_outcomes en SQLite, refresca metadata del embedding en Chroma.
```

Tiempo total por ciclo: **~20-90 segundos** según cuántos pares pasen la pre-criba (típicamente 2-6 de 15-20 candidatos).

### 3.2 Interfaces clave (puntos de extensión)

Estas son las "costuras" donde el sistema crecerá en futuras fases sin reescribirse:

```python
# data/market.py
class MarketDataSource(Protocol):
    def fetch_ohlcv(self, pair: str, timeframe: str, lookback: int) -> pd.DataFrame: ...
    def fetch_ticker(self, pair: str) -> Ticker: ...

# data/news.py
class NewsSource(Protocol):
    def fetch_recent(self, since: datetime) -> list[NewsItem]: ...

# llm/client.py
class LLMClient(Protocol):
    def analyze(self, context: AnalysisContext) -> RawLLMResponse: ...
    # Fase 4: OllamaClient → cliente fine-tuneado sin tocar nada más.

# delivery/notifier.py
class Notifier(Protocol):
    def deliver(self, signals: list[Signal]) -> None: ...
    # Fase 3: OrderExecutor implementará una interfaz análoga.

# learning/memory.py
class Memory(Protocol):
    def add(self, situation: Situation, signal: Signal) -> None: ...
    def search(self, embedding: list[float], k: int) -> list[MemoryHit]: ...
```

### 3.3 Justificación del orden de pasos

- **Pre-criba antes que LLM**: no gastar GPU en pares sin movimiento.
- **RAG y feedback antes que LLM**: el modelo ya llega con contexto histórico.
- **Outcomes después de deliver**: no bloquear la notificación con jobs diferidos.

## 4. Pre-criba determinista y razonamiento del LLM

### 4.1 Reglas de pre-criba (`analysis/prefilter.py`)

Un par **pasa al LLM** si cumple al menos una de estas condiciones:

| Disparador | Umbral por defecto (configurable) |
|---|---|
| Volumen anómalo | `volumen_15m > 1.8 × media_volumen_24h` |
| RSI en zona extrema | `RSI < 30` o `RSI > 70` |
| Cruce reciente de EMAs | EMA20 y EMA50 se cruzaron en las últimas 3 velas |
| Ruptura de rango | Cierre por encima del máximo o por debajo del mínimo de las últimas 20 velas |
| Divergencia MACD | Precio nuevo máximo + MACD máximo menor (o equivalente bajista) |
| Volatilidad expandida | `ATR_actual > 1.5 × ATR_medio_20` |

**Anti-spam:** si ya se emitió una señal para ese par hace menos de 60 min, se descarta. Excepción: la señal nueva sí pasa al LLM si su `action` propuesta por la pre-criba ya es de signo opuesto a la previa (BUY tras SELL o SELL tras BUY). HOLD→HOLD nunca pasa.

### 4.2 Contexto del LLM (`AnalysisContext`)

```python
@dataclass
class AnalysisContext:
    pair: str                          # "BTC/USDT"
    timeframe: str                     # "15m"
    ohlcv_summary: OHLCVSummary        # últimas 20 velas resumidas
    indicators: IndicatorSnapshot      # valores actuales + dirección
    news: list[NewsItem]               # titulares relevantes últimas 4h
    memory_hits: list[MemoryHit]       # 3-5 situaciones similares del pasado
    recent_feedback: RecentFeedback    # últimas 20 señales propias + outcomes
    portfolio_state: PortfolioState    # vacío en F1; en F3 incluye posición real
```

`ohlcv_summary` se entrega resumido (aperturas, cierres, máximos, mínimos, volúmenes de las últimas 20 velas + niveles clave), no como CSV completo. Cuanto más limpio el contexto, mejor razona el LLM y menos tokens consume.

### 4.3 Prompt (`config/prompts/analyze_pair.j2`)

**Mensaje de sistema** (fijo, breve):

> Eres un analista cuantitativo conservador. Tu objetivo es identificar oportunidades con relación riesgo/recompensa favorable. Solo emites BUY o SELL cuando los datos lo justifican; HOLD es perfectamente válido y preferible a operar con baja convicción. Respondes SIEMPRE con JSON válido según el schema proporcionado, sin texto adicional.

**Mensaje de usuario** (Jinja2), bloques claros:

```
## Par: {{ pair }} | Timeframe: {{ timeframe }} | Hora: {{ now }}

## Datos técnicos
{{ indicators_table }}

## Acción reciente del precio
{{ ohlcv_summary }}

## Noticias relevantes (últimas 4h)
{{ news_block }}

## Tu rendimiento reciente (últimas 20 señales)
- Win rate: {{ recent_feedback.win_rate }}%
- Mejor señal: {{ ... }}, peor señal: {{ ... }}
- Resumen: {{ recent_feedback.summary }}

## Situaciones pasadas similares
{% for hit in memory_hits %}
[Hace {{ hit.age }}] Indicadores parecidos: {{ hit.summary }}.
Decidiste {{ hit.action }}. Resultado a 4h: {{ hit.outcome_4h }}, a 24h: {{ hit.outcome_24h }}.
{% endfor %}

## Tu tarea
Analiza el par y responde con JSON según schema.
```

### 4.4 Output esperado y validación

```python
class Signal(BaseModel):
    action: Literal["BUY", "SELL", "HOLD"]
    confidence: int = Field(ge=0, le=100)
    reasoning: str = Field(max_length=500)
    entry_price_hint: float | None
    invalidation_level: float | None
    time_horizon: Literal["short", "medium", "long"]
    key_factors: list[str] = Field(max_items=5)
```

Flujo de validación:

1. Llamar al LLM con el prompt.
2. Parsear como JSON estricto.
3. Si falla → reintentar UNA vez con prefijo `"Tu respuesta anterior no fue JSON válido. Responde EXCLUSIVAMENTE con el JSON pedido:"`.
4. Si vuelve a fallar → loguear `LLMParseError` y descartar la señal de ese par.
5. Si pasa → aplicar umbral de confianza configurable (por defecto `confidence >= 60`). Por debajo, la señal se persiste pero **no se entrega**.

## 5. Persistencia, errores y configuración

### 5.1 SQLite (`data/crypto_farmer.db`)

```sql
cycles(
  id INTEGER PK, started_at TIMESTAMP, finished_at TIMESTAMP,
  status TEXT,                         -- ok | degraded | failed
  pairs_analyzed INT, pairs_passed_prefilter INT,
  signals_generated INT, notes TEXT
)

signals(
  id INTEGER PK, cycle_id FK, pair TEXT, timeframe TEXT,
  generated_at TIMESTAMP,
  action TEXT, confidence INT, reasoning TEXT,
  entry_price_hint REAL, invalidation_level REAL,
  time_horizon TEXT, key_factors_json TEXT,
  delivered BOOL,                       -- true cuando se envía a Telegram (no antes)
  price_at_signal REAL
)

signal_outcomes(
  id INTEGER PK, signal_id FK, horizon TEXT,    -- 1h | 4h | 24h
  measured_at TIMESTAMP, price_then REAL,
  return_pct REAL, verdict TEXT                  -- correct | incorrect | neutral
)

analysis_contexts(
  id INTEGER PK, signal_id FK,
  indicators_json TEXT, news_json TEXT,
  memory_hits_json TEXT, feedback_summary TEXT,
  prompt_rendered TEXT, raw_llm_response TEXT
)

news_items(
  id INTEGER PK, source TEXT, url TEXT UNIQUE,
  title TEXT, body TEXT, published_at TIMESTAMP,
  fetched_at TIMESTAMP, related_pairs_json TEXT
)
```

### 5.2 ChromaDB (`data/memory/`)

Colección `situations`. Cada entry:

- `embedding` (vector del texto de la `Situation`)
- Metadata: `pair`, `timeframe`, `timestamp`, `signal_id`, `action`
- Texto original
- Cuando llega el outcome, se actualiza la metadata con `return_4h` y `return_24h`. Búsqueda futura puede entonces ver no solo situaciones similares sino sus resultados reales.

Persistencia es **best-effort para Chroma, crítica para SQLite**. Si Chroma falla escribiendo, el ciclo continúa y se intenta de nuevo al inicio del siguiente. Si SQLite falla, el ciclo se marca `failed`.

### 5.3 Solape de ciclos

APScheduler se configura con `max_instances=1` y `coalesce=True` para el job del ciclo. Si un ciclo no termina antes del siguiente disparo (caso atípico: >15 min), el solapado se omite y se loguea un evento `cycle_skipped`. Esto evita ejecuciones paralelas que competirían por la GPU y por los locks de SQLite. Los jobs de medición de outcomes son independientes y sí pueden ejecutarse en paralelo con un ciclo.

### 5.4 Gestión de errores

| Subsistema | Fallo posible | Comportamiento |
|---|---|---|
| `MarketDataSource` | CCXT timeout, rate limit, exchange caído | **Abort ciclo**. Loguear y reintentar al siguiente ciclo. |
| `NewsSource` | API caída, RSS roto | Continuar sin noticias. Marcar `degraded`. |
| `IndicatorEngine` | NaN por datos insuficientes en un par | Excluir solo ese par. |
| `Prefilter` | (código puro, no debería fallar) | Si lanza, abort y marcar bug. |
| `Memory.search` | Chroma corrupto/vacío | Continuar sin memory_hits. |
| `Embeddings` | Ollama embeddings caído | Continuar sin memoria para ese ciclo. |
| `LLMClient` | Ollama caído, timeout, parseo fallido tras retry | Saltar el par. Otros pares siguen. |
| `TelegramNotifier` | API caída, token inválido | Persistir señal igual. Reintentar entrega en el próximo ciclo. |
| `Outcomes` jobs | Job vencido porque el sistema estuvo parado | Al arrancar, reprogramar jobs vencidos hasta 48h; más viejos se descartan. |

**Estados del ciclo:** `ok` / `degraded` / `failed`, persistidos y reportados en la cabecera de la notificación Telegram cuando aplica.

### 5.5 Configuración

**`config/config.yaml`** (versionable):

```yaml
scheduler:
  interval_minutes: 15
  timezone: "Europe/Madrid"

market:
  exchange: binance
  pairs: [BTC/USDT, ETH/USDT, BNB/USDT, ...]
  timeframe: "15m"
  ohlcv_lookback: 200

news:
  enabled: true
  sources: [cryptopanic]
  max_age_hours: 4

prefilter:
  rsi_oversold: 30
  rsi_overbought: 70
  volume_anomaly_factor: 1.8
  atr_expansion_factor: 1.5
  cooldown_minutes: 60

llm:
  provider: ollama
  base_url: "http://localhost:11434"
  model: "qwen2.5:7b-instruct-q4_K_M"
  embedding_model: "nomic-embed-text"
  timeout_seconds: 30
  max_retries: 1

learning:
  memory_k: 5
  feedback_lookback: 20
  outcome_horizons_hours: [1, 4, 24]

delivery:
  telegram:
    enabled: true
    min_confidence: 60

logging:
  level: INFO
  format: json
  file: "data/logs/crypto_farmer.log"
  rotation: "1 day"
  retention: "30 days"
```

**`.env`** (no versionado):

```
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
CRYPTOPANIC_API_TOKEN=...
# Fase 3: BINANCE_API_KEY / BINANCE_API_SECRET
```

`config.py` lee YAML, sustituye `${VAR}` con env vars y devuelve dataclasses tipadas. Si falta un secreto requerido, **error explícito al arrancar**.

### 5.6 Logging

- Estructurado en JSON, una línea por entrada.
- Campos: `timestamp`, `level`, `cycle_id`, `module`, `event`, `payload`.
- Rotación diaria, retención 30 días.
- En desarrollo: salida adicional a stdout en formato legible.

## 6. Testing, observabilidad y validación

### 6.1 Estrategia de testing

**Unit tests:**

- `indicators.py` sobre fixtures de OHLCV conocidos.
- `prefilter.py` cada regla por separado, incluyendo casos límite.
- `parser.py` con JSON válido/inválido/parcial/vacío.
- `prompts.py` el template renderiza con contextos mínimos y máximos.
- `feedback.py`, `situation.py` producen el texto esperado.
- `config.py` detecta secretos faltantes, valida tipos.

**Integration tests:**

- `cycle.run()` con fakes (`FakeMarketDataSource`, `FakeNewsSource`, `FakeLLMClient`, `InMemoryMemory`, `FakeNotifier`).
- `OllamaClient` contra Ollama real con modelo pequeño, opt-in mediante `RUN_LLM_TESTS=1`.
- Persistencia: tras un ciclo, las filas en SQLite y los entries en Chroma son los esperados.

**E2E smoke test:** un test que arranca el sistema, ejecuta UN ciclo manual con datos simulados, y verifica que llega notificación al chat de pruebas de Telegram. Se ejecuta a mano antes de poner el sistema 24/7.

**Lo que NO testeamos:**

- Calidad de las señales del LLM (validación en vivo, no test).
- Red real en CI (mockeada con `respx`).

### 6.2 Bot de Telegram como panel de control

| Comando | Función |
|---|---|
| `/status` | Último ciclo, próximo ciclo, ciclos OK en 24h, errores recientes |
| `/last` | Últimas 5 señales + outcomes si están medidos |
| `/stats` | Win rate, mejor/peor par, distribución BUY/SELL/HOLD últimos 7 días |
| `/pair BTC/USDT` | Resumen del par: indicadores, última señal, outcomes |
| `/pause` | Pausa el scheduler |
| `/resume` | Reanuda |
| `/health` | Comprueba Binance, CryptoPanic, Ollama, ChromaDB |
| `/config` | Config actual (sin secretos) |

### 6.3 Métricas internas (`crypto_farmer/metrics.py`)

Contadores y latencias en memoria, expuestos vía `/health`:

- Latencia por etapa (fetch, indicadores, LLM, persist).
- Tasa de éxito por subsistema.
- Tasa de parseo correcto del LLM.
- Distribución de confianza de las señales.
- Crecimiento del histórico (entries en Chroma, filas en SQLite).

En Fase 2 alimentarán el dashboard web.

### 6.4 Plan de validación antes de marcha 24/7

1. **Días 1-2 — Smoke con un solo par.** `pairs: [BTC/USDT]`. Verificación manual de cada ciclo: contexto razonable, JSON parsea, notificación llega.
2. **Días 3-4 — 5 pares.** Pre-criba reduce el trabajo como se espera (mirar `cycles.pairs_passed_prefilter`).
3. **Días 5-7 — Universo completo (15-20 pares).** Ciclo cabe holgadamente en 15 min. Inspección manual de 5-10 `memory_hits`: ¿son realmente similares?
4. **Días 8-14 — Outcomes habilitados.** Primeros outcomes a 24h. Verificación: `verdict` se calcula bien, feedback que ve el LLM tiene sentido.
5. **Antes de marcha 24/7:** backup configurado, log rotation OK, comportamiento ante caídas simuladas de Ollama / Binance / red.

Si algún paso falla, **no se promueve a 24/7** hasta arreglarlo.

### 6.5 Backup y recuperación

- Archivos críticos: `data/crypto_farmer.db` y `data/memory/`.
- Script diario que copia a `data/backups/YYYY-MM-DD/`. Retención 30 días.
- Restauración: copiar archivos a su sitio y reiniciar.
- Pérdida total = arranque con histórico vacío, idéntico al día 1.

## 7. Roadmap (fases posteriores)

Resumen de planes posteriores. Cada fase es funcional por sí misma y valida la siguiente. **No avanzar sin validar la fase actual.**

### Fase 2 — Paper trading y métricas

- Motor de paper trading: cartera virtual cash + posiciones, ejecuta cada señal contra mercado simulado.
- Modelado realista de costes: fees (0.1% Binance taker) + slippage estimado por liquidez.
- Métricas: equity curve, Sharpe ratio, max drawdown, win rate, profit factor, expectancy.
- Comparación con benchmarks: HODL BTC/ETH, DCA mensual, índice top 10 equiponderado.
- Dashboard web local (FastAPI + frontend simple).
- Reportes diarios/semanales por Telegram.

### Fase 3 — Trading real acotado

- `OrderExecutor` real vía CCXT (Binance), encaja en la interfaz `Notifier`-like.
- Reconciliación con estado real del exchange en cada ciclo.
- Position sizing: % fijo del capital con techo configurable; luego Kelly fraccional.
- Stop loss y take profit en el exchange, no solo en lógica interna.
- Kill-switch `/panic` que cierra todas las posiciones a mercado.
- Límites duros: max % por trade, max drawdown diario, max exposición total, máximo de operaciones/día.
- Modo "operativa fría" para señales con bajo score.
- Auditoría completa de cada decisión.

### Fase 4 — Aprendizaje avanzado

- Modelo ML auxiliar (XGBoost o LSTM ligera) entrenado con señales propias y outcomes; filtra/pondera al LLM.
- Fine-tune del LLM local con LoRA cuando haya 6-12 meses de histórico propio validado.
- Memoria por régimen de mercado (bull/bear/lateral/alta-vol).
- Reentrenamiento periódico automatizado con monitorización de drift.

### Fase 5 — Ampliación de inputs

- Sentimiento social: Twitter/X, Reddit, Telegram público.
- Datos on-chain: flujos a/desde exchanges, funding rates, open interest (Glassnode free, CoinGlass o nodo propio).
- Datos macro: DXY, S&P 500, tipos, calendario económico.
- Análisis de correlaciones intermercados.

### Fase 6 — Escalado de infraestructura

- Migración monolito → pipeline con cola (Redis + RQ/Celery) cuando bajen las frecuencias o se añadan estrategias paralelas.
- Multi-estrategia: varias "personalidades" de IA con sub-carteras independientes.
- Multi-exchange.
- VPS dedicado 24/7.

### Fase 7 — Más allá del trading direccional

- DCA inteligente decidido por la IA.
- Cobertura con derivados (futuros, opciones).
- DeFi yield aggregation.
- Detección de pump & dumps.

### Rama paralela — Web3 / on-chain (aprendizaje)

Camino independiente del CEX-centric (Fases 2-3) para entender web3 con el
mismo esqueleto del proyecto. Tres pasos progresivos, de menos a más
contacto con la cadena:

#### W1 — Lectura on-chain (próximo foco de aprendizaje)

- Nuevo `MarketDataSource` que en lugar de OHLCV de Binance lee:
  - Precio de un pool de Uniswap v3 (sqrtPriceX96 → precio).
  - Eventos `Swap` recientes (volumen on-chain de los últimos N bloques).
  - Liquidaciones recientes en Aave v3 (eventos `LiquidationCall`).
- Proveedor RPC: Alchemy free tier (o Infura). Chain inicial: Base o
  Arbitrum (gas barato, datos relevantes, sin el coste de un nodo full).
- La IA emite señales como en Fase 1, pero el "contexto de mercado" pasa
  a ser on-chain. Sin firmar nada, sin wallet.
- Aprendizaje: JSON-RPC, ABIs, eventos de contratos, indexers (The Graph
  como alternativa a leer eventos a pelo), diferencia AMM vs orderbook.
- Reutiliza ~80% del proyecto: scheduler, cycle, LLM, RAG, storage,
  notifier, paper trader (si quieres tradear con datos on-chain en
  paper, también vale).

#### W2 — Ejecución en testnet (futuro)

- Nuevo `DexExecutor` que firma swaps reales en Sepolia/Base-Sepolia
  con `web3.py` + wallet propio (clave en .env, tokens y ETH gratis de
  faucet).
- Aprendizaje: firmar transacciones, gas, slippage, `approve` ERC-20,
  callback de receipts, MEV básico.
- Sin riesgo económico real.

#### W3 — Mainnet L2 con cantidades mínimas (futuro)

- Mismo `DexExecutor` apuntando a Base/Arbitrum mainnet con $20-50.
- Aprendizaje: igual que W2 pero con consecuencias reales y gas
  realista en L2.
- Sólo después de validar W2 y de tener señales on-chain con win-rate
  decente en paper.

### Ideas exploratorias

- App móvil compañera (lectura).
- Chat conversacional con la IA.
- Tax reporting automático.
- Open-sourcing parcial del framework.
- Multi-tenant.

## 8. Resumen ejecutivo

`crypto-farmer` Fase 1 es un servicio Python local que cada 15 min recoge precios e indicadores de top 10-20 cripto en Binance vía CCXT + titulares de CryptoPanic, aplica una pre-criba determinista, invoca a un LLM local vía Ollama (Qwen 2.5 7B Q4 por defecto, configurable) sobre los pares filtrados con un prompt que incluye memoria selectiva (RAG con ChromaDB) y feedback in-context de señales pasadas, valida la respuesta JSON, persiste todo en SQLite, mide outcomes a 1h/4h/24h, y entrega las señales con confianza ≥ 60 al usuario por Telegram, con comandos de control desde el propio bot.

La arquitectura es monolítica modular con interfaces limpias preparadas para evolucionar a paper trading (Fase 2), trading real (Fase 3), aprendizaje avanzado (Fase 4) y ampliaciones posteriores, sin reescrituras.
