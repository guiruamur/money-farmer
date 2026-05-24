# Diseño — Web3 W1: lectura de precio on-chain

**Fecha:** 2026-05-24
**Estado:** aprobado en brainstorming, pendiente de plan de implementación
**Relacionado:** `2026-05-12-crypto-farmer-fase1-design.md` (sección "Rama paralela — Web3 / on-chain")

## 1. Contexto y objetivo

`crypto-farmer` lee hoy precios de Binance (CEX) vía CCXT. La **rama web3** es
un camino paralelo para aprender a operar on-chain, en tres pasos: **W1**
(leer on-chain, sin firmar nada), W2 (ejecutar en testnet), W3 (mainnet L2).

Este documento especifica **W1, fase a: leer el precio de un pool de Uniswap
directamente de la cadena por RPC, convertirlo en velas, y generar señales con
el mismo cerebro (Cycle) que el bot CEX** — en un modo aislado que no toca la
operativa en vivo. La fase b (métricas on-chain nativas: volumen de swaps,
liquidez, liquidaciones) se especificará aparte cuando W1-a funcione.

Decisiones de diseño tomadas (brainstorming 2026-05-24):

- **Camino incremental:** primero precio→velas (esta fase), luego métricas nativas.
- **Modo on-chain aparte**, como el backtest: no se mezcla con el bot CEX.
  web3 crece como carril independiente (W1→W2→W3) sin enredarse con Binance.
- **Lectura directa por RPC** (no un indexer/subgraph de terceros): se toca la
  cadena de verdad (RPC, ABIs, eventos), que es el objetivo de aprendizaje.

## 2. Alcance

**Incluye:**

- Un cliente RPC mínimo (JSON-RPC sobre HTTP) para `eth_call` y `eth_getLogs`.
- Una `MarketDataSource` on-chain que lee un pool de Uniswap v3:
  - precio actual desde `slot0` (`sqrtPriceX96` → precio),
  - velas OHLCV de 15m reconstruidas de los eventos `Swap`.
- Un comando `python -m crypto_farmer onchain` que corre el `Cycle` existente
  con esa fuente, con datos aislados en `data/onchain/`.
- Configuración del pool (chain, dirección, decimales) y URL RPC desde `.env`.

**No incluye (YAGNI, se hará después):**

- Firmar o ejecutar transacciones (eso es W2/W3).
- Métricas on-chain nativas (volumen de swaps, liquidez, liquidaciones) — fase b.
- Backtesting on-chain (el motor existe; se conectará más adelante).
- Múltiples pools/pares a la vez (W1-a usa uno).
- Dashboard.

## 3. Arquitectura y componentes

Piezas nuevas en `crypto_farmer/onchain/`:

| Componente | Responsabilidad | Depende de |
|---|---|---|
| `RpcClient` | JSON-RPC sobre HTTP: `eth_call`, `eth_getLogs`, `eth_blockNumber` | httpx, URL RPC |
| `price_math` | `sqrtPriceX96` + decimales → precio legible | — |
| `UniswapPoolSource` | `MarketDataSource`: `fetch_ticker` (slot0) y `fetch_ohlcv` (eventos Swap → velas) | `RpcClient`, `price_math` |
| `OnchainConfig` | chain, dirección del pool, decimales token0/token1, RPC URL, bloques de lookback | `.env`, config |
| builder + comando | construir el `Cycle` con la fuente on-chain y datos aislados; CLI `onchain` | todo lo anterior + `Cycle` |

Se reutilizan **sin cambios**: `Cycle`, `IndicatorEngine`, `Prefilter`,
`PromptBuilder`, `SignalParser`, `Storage`, `ChromaMemory`, `OutcomeService`,
`NullNotifier`/`TelegramNotifier`, y el `Clock` (en vivo, `SystemClock`).

## 4. Cliente RPC

`RpcClient` habla JSON-RPC 2.0 contra la URL del endpoint (Alchemy/Infura):

- `call(to, data) -> hex` — `eth_call` para leer funciones de contrato (p.ej. `slot0()`).
- `get_logs(address, topics, from_block, to_block) -> list` — `eth_getLogs` para eventos `Swap`.
- `block_number() -> int` — `eth_blockNumber`.

Codifica/decodifica el ABI mínimo necesario a mano o con una utilidad ligera
(no hace falta `web3.py` entero para W1-a; basta `eth_abi` para decodificar, o
decodificación manual de los campos fijos). Errores de red/HTTP → excepción
propia `RpcError`.

## 5. Lectura del pool (UniswapPoolSource)

Implementa la interfaz `MarketDataSource` (igual que `CcxtBinanceSource`):

- **`fetch_ticker(pair)`**: `eth_call` a `slot0()` del pool → `sqrtPriceX96` →
  `price_math` lo convierte a precio (token1/token0 ajustado por decimales).
  Devuelve un `Ticker(pair, price, timestamp=now)`.
- **`fetch_ohlcv(pair, timeframe, lookback)`**: 
  1. `block_number()` para el bloque actual.
  2. Estima el rango de bloques que cubre `lookback × 15m` (con el tiempo de
     bloque de la chain; en Base ~2 s/bloque).
  3. `get_logs` de los eventos `Swap` del pool en ese rango (paginando por
     sub-rangos si el proveedor limita el nº de logs por llamada).
  4. Cada `Swap` lleva `sqrtPriceX96` posterior al swap → precio en ese bloque
     (timestamp del bloque). Agrega los precios en velas de 15m (open/high/low/
     close por intervalo; volumen = suma de `amount` de los swaps del intervalo).
  5. Devuelve un DataFrame con columnas `timestamp, open, high, low, close,
     volume`, igual que la fuente de Binance.

Si el histórico reconstruido tiene menos velas que el `lookback`, devuelve las
que haya; el `Cycle` ya tolera "datos insuficientes" por par (salta el par y lo
anota), así que al principio puede haber pocos análisis hasta acumular rango.

## 6. Conversión de precio (price_math)

`price_from_sqrt(sqrt_price_x96, decimals0, decimals1) -> float`:

```
price = (sqrt_price_x96 / 2**96) ** 2          # token1 por token0, en unidades crudas
price_ajustado = price * 10**(decimals0 - decimals1)
```

Para WETH/USDC (decimals 18 y 6) da el precio de ETH en USDC. Función pura,
fácil de testear con vectores conocidos.

## 7. Integración: el modo on-chain

Un comando nuevo, paralelo a `backtest`:

```
python -m crypto_farmer onchain [--once] [--config config/config.yaml]
```

- Construye el `Cycle` con `UniswapPoolSource` en lugar de `CcxtBinanceSource`.
- `Storage` en `data/onchain/crypto_farmer.db`, `ChromaMemory` en
  `data/onchain/chroma/` — **aislados del bot CEX**.
- `pairs = ["ETH/USDC"]` (el único pool de W1-a; etiqueta lógica del par).
- `NoopNewsSource` (sin noticias, como el backtest).
- `--once`: un ciclo y salir (smoke). Sin `--once`: scheduler periódico como el
  bot normal.
- Notificaciones: `NullNotifier` por defecto (no spamear Telegram); opción de
  Telegram más adelante si se quiere seguimiento.
- Paper trader: opcional, desde `config.paper` (puede operar en paper sobre el
  precio on-chain, igual que el bot CEX).

## 8. Configuración

`OnchainConfig` (sección nueva `onchain:` en `config.yaml`, o un bloque propio):

- `chain`: p.ej. `base`.
- `pool_address`: dirección del pool Uniswap v3 WETH/USDC en Base.
- `token0_decimals`, `token1_decimals`: 18 (WETH) y 6 (USDC) — y qué token es
  el base para orientar el precio.
- `pair_label`: `ETH/USDC` (etiqueta para señales/almacenamiento).
- `block_time_seconds`: ~2 (Base) para estimar rangos de bloques.
- `rpc_url`: desde `.env` (`ALCHEMY_URL` o `ONCHAIN_RPC_URL`), nunca en el repo.

**Prerequisito del usuario:** cuenta gratuita en Alchemy (o Infura), crear una
app en la red Base, y poner la URL RPC en `.env`. El agente no maneja la clave.

## 9. Errores

- RPC inalcanzable / HTTP error → `RpcError`, que `UniswapPoolSource` traduce a
  `MarketFetchError`. El `Cycle` ya aborta o degrada el ciclo limpiamente.
- `eth_getLogs` con demasiados resultados → paginar por sub-rangos de bloques.
- Pool/decimales mal configurados → precio absurdo; el smoke test manual lo
  detecta comparando con el precio real de ETH.

## 10. Testing

- `price_math`: vectores `sqrtPriceX96` conocidos → precio esperado (incl. WETH/USDC).
- `RpcClient`: mock HTTP (respx) de `eth_call`/`eth_getLogs`/`eth_blockNumber`;
  verifica el encode de la petición y el decode de la respuesta.
- `UniswapPoolSource.fetch_ticker`: con un `slot0` mockeado, devuelve el precio correcto.
- `UniswapPoolSource.fetch_ohlcv`: con logs `Swap` sintéticos, reconstruye las
  velas esperadas (agregación 15m, OHLC correctos, nunca velas futuras).
- Builder/CLI: `python -m crypto_farmer onchain --once` parsea y enruta bien
  (con fuente mockeada en test; el run real contra Alchemy es smoke manual).
- Smoke manual: un ciclo real contra Base, comprobando que el precio de ETH es
  realista y que se genera (o no) una señal sin errores.

## 11. Decisiones y notas

- **Chain inicial: Base** (L2 barato, líquido, bien soportado por Alchemy).
- **Pool inicial: Uniswap v3 WETH/USDC** en Base.
- Lectura directa por RPC; sin `web3.py` completo para W1-a (httpx + decode mínimo).
- Datos aislados en `data/onchain/`; cero impacto en el bot CEX.
- Solo señales (no ejecución) en W1, como Fase 1.
- El histórico inicial es modesto (reconstruido de swaps recientes) y crece con
  el tiempo; es aceptable para empezar.
