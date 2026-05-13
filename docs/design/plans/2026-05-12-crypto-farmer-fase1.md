# crypto-farmer Fase 1 — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use metodología TDD (recommended) or ejecución por fases to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir el servicio Python local `crypto-farmer` que cada 15 min analiza top 10-20 cripto con un LLM local (Ollama) usando indicadores técnicos + noticias + memoria RAG + feedback in-context, y entrega señales por Telegram, según lo especificado en `docs/design/specs/2026-05-12-crypto-farmer-fase1-design.md`.

**Architecture:** Monolito modular Python. Un proceso, APScheduler dispara el ciclo cada 15 min. Cada subsistema (data, analysis, llm, learning, delivery, storage) tiene una interfaz Protocol e implementaciones reales + fakes para test. Persistencia local en SQLite (datos) + ChromaDB (vectores).

**Tech Stack:** Python 3.11+, ccxt, pandas + pandas-ta, httpx, python-telegram-bot, apscheduler, pydantic, pyyaml, python-dotenv, chromadb, jinja2, pytest + pytest-mock + respx, ruff.

**Convenciones del plan:**
- Cada tarea es TDD: test primero → fallar → implementación mínima → pasar → commit.
- Rutas relativas a la raíz del proyecto (`c:\Users\germ1\Proyectos\money-farmer`).
- Comandos de shell asumen PowerShell. Se especifica si algún paso requiere otra shell.
- Cuando un test usa fixture compartida, se define en `tests/conftest.py` y se referencia.
- Toda fecha en logs es UTC; presentación al usuario en zona horaria de config.

---

## Bloque 0 — Bootstrap del proyecto

### Tarea 0: Inicializar repo, estructura y dependencias

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `README.md`
- Create: `crypto_farmer/__init__.py`
- Create: `crypto_farmer/__main__.py` (placeholder)
- Create: `tests/__init__.py`
- Create: `tests/conftest.py` (placeholder)
- Create: `config/config.example.yaml` (placeholder, se completa en Tarea 2)
- Create: directorios vacíos: `crypto_farmer/data/`, `crypto_farmer/analysis/`, `crypto_farmer/llm/`, `crypto_farmer/learning/`, `crypto_farmer/signals/`, `crypto_farmer/delivery/`, `crypto_farmer/storage/`, `config/prompts/`, `data/`, `tests/unit/`, `tests/integration/`

- [ ] **Step 1: Inicializar git y crear `.gitignore`**

Comando:
```
git init
```

Contenido de `.gitignore`:
```
# Python
__pycache__/
*.py[cod]
*$py.class
*.egg-info/
.pytest_cache/
.mypy_cache/
.ruff_cache/
.venv/
venv/

# Project
.env
data/
!data/.gitkeep

# IDE
.vscode/
.idea/
```

- [ ] **Step 2: Crear `pyproject.toml`**

```toml
[project]
name = "crypto-farmer"
version = "0.1.0"
description = "Servicio local de señales cripto con IA local"
requires-python = ">=3.11"
dependencies = [
    "ccxt>=4.2",
    "pandas>=2.2",
    "pandas-ta>=0.3.14b",
    "httpx>=0.27",
    "python-telegram-bot>=21",
    "apscheduler>=3.10",
    "pydantic>=2.7",
    "pyyaml>=6.0",
    "python-dotenv>=1.0",
    "chromadb>=0.5",
    "jinja2>=3.1",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-mock>=3.12",
    "pytest-asyncio>=0.23",
    "respx>=0.21",
    "ruff>=0.4",
]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["crypto_farmer*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra"

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]
```

- [ ] **Step 3: Crear archivos placeholder**

`crypto_farmer/__init__.py`:
```python
__version__ = "0.1.0"
```

`crypto_farmer/__main__.py`:
```python
def main() -> None:
    raise NotImplementedError("Entry point se completa en la Tarea 25")


if __name__ == "__main__":
    main()
```

`tests/__init__.py`: vacío.

`tests/conftest.py`:
```python
"""Fixtures compartidas. Se irán añadiendo a lo largo del plan."""
```

`config/config.example.yaml`:
```yaml
# Plantilla — se completa en la Tarea 2
```

`.env.example`:
```
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
CRYPTOPANIC_API_TOKEN=
```

`README.md`:
```markdown
# crypto-farmer

Servicio local de señales cripto con IA local. Fase 1 según `docs/design/specs/2026-05-12-crypto-farmer-fase1-design.md`.

## Setup
```bash
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
copy .env.example .env  # rellenar valores
copy config\config.example.yaml config\config.yaml
```

## Ejecutar
```bash
python -m crypto_farmer
```

## Tests
```bash
pytest
```
```

- [ ] **Step 4: Crear directorios vacíos con `.gitkeep`**

Para cada uno de estos directorios, crear un archivo `.gitkeep` vacío:
- `crypto_farmer/data/.gitkeep`
- `crypto_farmer/analysis/.gitkeep`
- `crypto_farmer/llm/.gitkeep`
- `crypto_farmer/learning/.gitkeep`
- `crypto_farmer/signals/.gitkeep`
- `crypto_farmer/delivery/.gitkeep`
- `crypto_farmer/storage/.gitkeep`
- `config/prompts/.gitkeep`
- `data/.gitkeep`
- `tests/unit/.gitkeep`
- `tests/integration/.gitkeep`

- [ ] **Step 5: Crear entorno virtual e instalar dependencias**

PowerShell:
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

Expected: instalación termina sin errores. `pip list` muestra ccxt, pandas, chromadb, etc.

- [ ] **Step 6: Verificar que pytest arranca**

```powershell
pytest -q
```

Expected: `no tests ran` (o `collected 0 items`), exit 0.

- [ ] **Step 7: Commit inicial**

```powershell
git add .
git commit -m "chore: bootstrap project structure and dependencies"
```

---

## Bloque 1 — Logging y configuración

### Tarea 1: Logging estructurado JSON

**Files:**
- Create: `crypto_farmer/logging_setup.py`
- Test: `tests/unit/test_logging_setup.py`

- [ ] **Step 1: Escribir test que falla**

`tests/unit/test_logging_setup.py`:
```python
import json
import logging

from crypto_farmer.logging_setup import configure_logging, get_logger


def test_logger_emits_json(capsys):
    configure_logging(level="INFO", to_stdout=True, json_format=True)
    log = get_logger("test")
    log.info("hello", extra={"payload": {"foo": "bar"}, "cycle_id": 42})

    captured = capsys.readouterr().out.strip().splitlines()
    assert captured, "no se emitió ninguna línea"
    record = json.loads(captured[-1])
    assert record["level"] == "INFO"
    assert record["event"] == "hello"
    assert record["module"] == "test"
    assert record["cycle_id"] == 42
    assert record["payload"] == {"foo": "bar"}
    assert "timestamp" in record


def test_logger_human_format(capsys):
    configure_logging(level="DEBUG", to_stdout=True, json_format=False)
    log = get_logger("test")
    log.debug("hola")
    out = capsys.readouterr().out
    assert "hola" in out
    assert "DEBUG" in out
```

- [ ] **Step 2: Verificar fallo**

```powershell
pytest tests/unit/test_logging_setup.py -v
```

Expected: ImportError o ModuleNotFoundError para `crypto_farmer.logging_setup`.

- [ ] **Step 3: Implementación**

`crypto_farmer/logging_setup.py`:
```python
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Any


_STANDARD_ATTRS = {
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "message", "asctime",
}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc)
                .strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "level": record.levelname,
            "module": record.name,
            "event": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key in _STANDARD_ATTRS:
                continue
            base[key] = value
        if record.exc_info:
            base["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(base, default=str, ensure_ascii=False)


def configure_logging(
    *,
    level: str = "INFO",
    json_format: bool = True,
    to_stdout: bool = True,
    log_file: str | Path | None = None,
    rotate_when: str = "midnight",
    retention_days: int = 30,
) -> None:
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)

    formatter: logging.Formatter
    if json_format:
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)s [%(name)s] %(message)s"
        )

    if to_stdout:
        h = logging.StreamHandler(sys.stdout)
        h.setFormatter(formatter)
        root.addHandler(h)

    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        fh = TimedRotatingFileHandler(
            log_path, when=rotate_when, backupCount=retention_days, encoding="utf-8"
        )
        fh.setFormatter(JsonFormatter())
        root.addHandler(fh)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
```

- [ ] **Step 4: Verificar pasa**

```powershell
pytest tests/unit/test_logging_setup.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```powershell
git add crypto_farmer/logging_setup.py tests/unit/test_logging_setup.py
git commit -m "feat(logging): structured JSON logger with rotation support"
```

---

### Tarea 2: Sistema de configuración

**Files:**
- Create: `crypto_farmer/config.py`
- Modify: `config/config.example.yaml`
- Test: `tests/unit/test_config.py`

- [ ] **Step 1: Definir config example completa**

Sobreescribir `config/config.example.yaml` con el bloque de la sección 5.5 del spec:

```yaml
scheduler:
  interval_minutes: 15
  timezone: "Europe/Madrid"

market:
  exchange: binance
  pairs:
    - BTC/USDT
    - ETH/USDT
    - BNB/USDT
    - SOL/USDT
    - XRP/USDT
    - ADA/USDT
    - DOGE/USDT
    - AVAX/USDT
    - LINK/USDT
    - DOT/USDT
  timeframe: "15m"
  ohlcv_lookback: 200

news:
  enabled: true
  sources:
    - cryptopanic
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
    bot_token: "${TELEGRAM_BOT_TOKEN}"
    chat_id: "${TELEGRAM_CHAT_ID}"

news_credentials:
  cryptopanic_token: "${CRYPTOPANIC_API_TOKEN}"

logging:
  level: INFO
  format: json
  file: "data/logs/crypto_farmer.log"
  rotation: "1 day"
  retention_days: 30

storage:
  sqlite_path: "data/crypto_farmer.db"
  chroma_path: "data/memory"
```

- [ ] **Step 2: Escribir tests que fallan**

`tests/unit/test_config.py`:
```python
import os
import textwrap
from pathlib import Path

import pytest

from crypto_farmer.config import Config, ConfigError, load_config


@pytest.fixture
def yaml_path(tmp_path: Path) -> Path:
    p = tmp_path / "config.yaml"
    p.write_text(textwrap.dedent("""
        scheduler:
          interval_minutes: 15
          timezone: "Europe/Madrid"
        market:
          exchange: binance
          pairs: [BTC/USDT, ETH/USDT]
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
            bot_token: "${TELEGRAM_BOT_TOKEN}"
            chat_id: "${TELEGRAM_CHAT_ID}"
        news_credentials:
          cryptopanic_token: "${CRYPTOPANIC_API_TOKEN}"
        logging:
          level: INFO
          format: json
          file: "data/logs/crypto_farmer.log"
          rotation: "1 day"
          retention_days: 30
        storage:
          sqlite_path: "data/crypto_farmer.db"
          chroma_path: "data/memory"
    """).strip(), encoding="utf-8")
    return p


def test_load_config_resolves_env(yaml_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok123")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    monkeypatch.setenv("CRYPTOPANIC_API_TOKEN", "cp_abc")

    cfg = load_config(yaml_path)
    assert isinstance(cfg, Config)
    assert cfg.scheduler.interval_minutes == 15
    assert cfg.market.pairs == ["BTC/USDT", "ETH/USDT"]
    assert cfg.delivery.telegram.bot_token == "tok123"
    assert cfg.delivery.telegram.chat_id == "42"
    assert cfg.news_credentials.cryptopanic_token == "cp_abc"


def test_load_config_missing_secret_raises(
    yaml_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    monkeypatch.setenv("CRYPTOPANIC_API_TOKEN", "cp_abc")

    with pytest.raises(ConfigError) as exc:
        load_config(yaml_path)
    assert "TELEGRAM_BOT_TOKEN" in str(exc.value)


def test_load_config_validates_types(tmp_path: Path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("scheduler:\n  interval_minutes: not-a-number\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(bad)
```

- [ ] **Step 3: Verificar fallo**

```powershell
pytest tests/unit/test_config.py -v
```

Expected: ImportError sobre `crypto_farmer.config`.

- [ ] **Step 4: Implementación**

`crypto_farmer/config.py`:
```python
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, ValidationError


class ConfigError(Exception):
    pass


_ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")


def _resolve_env(value: Any) -> Any:
    if isinstance(value, str):
        def replace(match: re.Match[str]) -> str:
            var = match.group(1)
            resolved = os.environ.get(var)
            if resolved is None:
                raise ConfigError(f"Variable de entorno requerida no definida: {var}")
            return resolved
        return _ENV_PATTERN.sub(replace, value)
    if isinstance(value, dict):
        return {k: _resolve_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_env(item) for item in value]
    return value


class SchedulerCfg(BaseModel):
    interval_minutes: int = Field(gt=0)
    timezone: str


class MarketCfg(BaseModel):
    exchange: str
    pairs: list[str] = Field(min_length=1)
    timeframe: str
    ohlcv_lookback: int = Field(gt=0)


class NewsCfg(BaseModel):
    enabled: bool
    sources: list[str]
    max_age_hours: int = Field(gt=0)


class PrefilterCfg(BaseModel):
    rsi_oversold: float
    rsi_overbought: float
    volume_anomaly_factor: float
    atr_expansion_factor: float
    cooldown_minutes: int


class LLMCfg(BaseModel):
    provider: str
    base_url: str
    model: str
    embedding_model: str
    timeout_seconds: int = Field(gt=0)
    max_retries: int = Field(ge=0)


class LearningCfg(BaseModel):
    memory_k: int = Field(gt=0)
    feedback_lookback: int = Field(ge=0)
    outcome_horizons_hours: list[int]


class TelegramCfg(BaseModel):
    enabled: bool
    min_confidence: int = Field(ge=0, le=100)
    bot_token: str
    chat_id: str


class DeliveryCfg(BaseModel):
    telegram: TelegramCfg


class NewsCredentialsCfg(BaseModel):
    cryptopanic_token: str


class LoggingCfg(BaseModel):
    level: str
    format: str
    file: str
    rotation: str
    retention_days: int


class StorageCfg(BaseModel):
    sqlite_path: str
    chroma_path: str


class Config(BaseModel):
    scheduler: SchedulerCfg
    market: MarketCfg
    news: NewsCfg
    prefilter: PrefilterCfg
    llm: LLMCfg
    learning: LearningCfg
    delivery: DeliveryCfg
    news_credentials: NewsCredentialsCfg
    logging: LoggingCfg
    storage: StorageCfg


def load_config(path: str | Path) -> Config:
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"Config no encontrada: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ConfigError("Config YAML debe ser un mapping en la raíz")
    resolved = _resolve_env(raw)
    try:
        return Config(**resolved)
    except ValidationError as e:
        raise ConfigError(f"Config inválida: {e}") from e
```

- [ ] **Step 5: Verificar pasa**

```powershell
pytest tests/unit/test_config.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Commit**

```powershell
git add crypto_farmer/config.py config/config.example.yaml tests/unit/test_config.py
git commit -m "feat(config): typed YAML config loader with env var substitution"
```

---

## Bloque 2 — Modelos de dominio

### Tarea 3: Dataclasses básicas del dominio

**Files:**
- Create: `crypto_farmer/signals/models.py`
- Test: `tests/unit/test_signals_models.py`

- [ ] **Step 1: Escribir test**

`tests/unit/test_signals_models.py`:
```python
from datetime import datetime, timezone

import pandas as pd
import pytest
from pydantic import ValidationError

from crypto_farmer.signals.models import (
    CycleStatus,
    IndicatorSnapshot,
    NewsItem,
    OHLCVSummary,
    Signal,
    SignalAction,
    Ticker,
    TimeHorizon,
)


def test_signal_valid():
    s = Signal(
        action=SignalAction.BUY,
        confidence=72,
        reasoning="RSI saliendo de sobreventa con MACD cruzando al alza.",
        entry_price_hint=42000.5,
        invalidation_level=41500.0,
        time_horizon=TimeHorizon.SHORT,
        key_factors=["rsi_oversold_reversal", "macd_cross"],
    )
    assert s.action == SignalAction.BUY
    assert s.confidence == 72


def test_signal_rejects_invalid_confidence():
    with pytest.raises(ValidationError):
        Signal(
            action=SignalAction.BUY,
            confidence=120,
            reasoning="x",
            entry_price_hint=None,
            invalidation_level=None,
            time_horizon=TimeHorizon.SHORT,
            key_factors=[],
        )


def test_signal_rejects_too_many_factors():
    with pytest.raises(ValidationError):
        Signal(
            action=SignalAction.BUY,
            confidence=60,
            reasoning="x",
            entry_price_hint=None,
            invalidation_level=None,
            time_horizon=TimeHorizon.SHORT,
            key_factors=["a", "b", "c", "d", "e", "f"],
        )


def test_ticker_and_news_item():
    t = Ticker(pair="BTC/USDT", price=42000.0, timestamp=datetime.now(timezone.utc))
    assert t.price == 42000.0

    n = NewsItem(
        source="cryptopanic",
        url="https://example.com/1",
        title="BTC sube",
        body=None,
        published_at=datetime.now(timezone.utc),
        related_pairs=["BTC/USDT"],
    )
    assert n.related_pairs == ["BTC/USDT"]


def test_indicator_snapshot():
    ind = IndicatorSnapshot(
        pair="BTC/USDT",
        timestamp=datetime.now(timezone.utc),
        rsi=28.5,
        macd=12.0,
        macd_signal=10.0,
        macd_hist=2.0,
        ema_20=41900.0,
        ema_50=41500.0,
        bb_upper=42500.0,
        bb_lower=41000.0,
        atr=350.0,
        atr_mean_20=300.0,
        volume=125.0,
        volume_mean_24h=80.0,
    )
    assert ind.atr_expansion_ratio() == pytest.approx(350.0 / 300.0)
    assert ind.volume_anomaly_ratio() == pytest.approx(125.0 / 80.0)


def test_ohlcv_summary_from_df():
    rows = [
        {"open": 100, "high": 105, "low": 99, "close": 104, "volume": 10},
        {"open": 104, "high": 108, "low": 103, "close": 107, "volume": 12},
    ]
    df = pd.DataFrame(rows)
    s = OHLCVSummary.from_df(df, recent_n=2)
    assert s.recent[0].open == 100
    assert s.recent[-1].close == 107
    assert s.highest_high == 108
    assert s.lowest_low == 99


def test_cycle_status_enum():
    assert CycleStatus.OK.value == "ok"
    assert CycleStatus.DEGRADED.value == "degraded"
    assert CycleStatus.FAILED.value == "failed"
```

- [ ] **Step 2: Verificar fallo**

```powershell
pytest tests/unit/test_signals_models.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implementación**

`crypto_farmer/signals/models.py`:
```python
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

import pandas as pd
from pydantic import BaseModel, Field


class SignalAction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class TimeHorizon(str, Enum):
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"


class CycleStatus(str, Enum):
    OK = "ok"
    DEGRADED = "degraded"
    FAILED = "failed"


class Signal(BaseModel):
    action: SignalAction
    confidence: int = Field(ge=0, le=100)
    reasoning: str = Field(max_length=500)
    entry_price_hint: float | None
    invalidation_level: float | None
    time_horizon: TimeHorizon
    key_factors: list[str] = Field(max_length=5)


class Ticker(BaseModel):
    pair: str
    price: float
    timestamp: datetime


class NewsItem(BaseModel):
    source: str
    url: str
    title: str
    body: str | None
    published_at: datetime
    related_pairs: list[str] = Field(default_factory=list)


class IndicatorSnapshot(BaseModel):
    pair: str
    timestamp: datetime
    rsi: float
    macd: float
    macd_signal: float
    macd_hist: float
    ema_20: float
    ema_50: float
    bb_upper: float
    bb_lower: float
    atr: float
    atr_mean_20: float
    volume: float
    volume_mean_24h: float

    def atr_expansion_ratio(self) -> float:
        return self.atr / self.atr_mean_20 if self.atr_mean_20 else 0.0

    def volume_anomaly_ratio(self) -> float:
        return self.volume / self.volume_mean_24h if self.volume_mean_24h else 0.0


class OHLCVCandle(BaseModel):
    open: float
    high: float
    low: float
    close: float
    volume: float


class OHLCVSummary(BaseModel):
    recent: list[OHLCVCandle]
    highest_high: float
    lowest_low: float

    @classmethod
    def from_df(cls, df: pd.DataFrame, *, recent_n: int) -> "OHLCVSummary":
        tail = df.tail(recent_n)
        recent = [
            OHLCVCandle(
                open=float(r["open"]), high=float(r["high"]),
                low=float(r["low"]), close=float(r["close"]),
                volume=float(r["volume"]),
            )
            for _, r in tail.iterrows()
        ]
        return cls(
            recent=recent,
            highest_high=float(tail["high"].max()),
            lowest_low=float(tail["low"].min()),
        )
```

- [ ] **Step 4: Verificar pasa**

```powershell
pytest tests/unit/test_signals_models.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```powershell
git add crypto_farmer/signals/models.py tests/unit/test_signals_models.py
git commit -m "feat(models): core domain dataclasses (Signal, Ticker, NewsItem, indicators)"
```

---

## Bloque 3 — Capa de datos de mercado

### Tarea 4: Interfaz `MarketDataSource` y fake para tests

**Files:**
- Create: `crypto_farmer/data/__init__.py`
- Create: `crypto_farmer/data/market.py`
- Create: `tests/fakes/__init__.py`
- Create: `tests/fakes/market.py`
- Test: `tests/unit/test_market_fake.py`

- [ ] **Step 1: Test del fake**

`tests/unit/test_market_fake.py`:
```python
import pandas as pd
from datetime import datetime, timezone

from tests.fakes.market import FakeMarketDataSource


def test_fake_returns_configured_ohlcv():
    df = pd.DataFrame([
        {"timestamp": 1, "open": 100, "high": 110, "low": 95, "close": 105, "volume": 10},
        {"timestamp": 2, "open": 105, "high": 112, "low": 104, "close": 110, "volume": 12},
    ])
    fake = FakeMarketDataSource(ohlcv={"BTC/USDT": df})
    out = fake.fetch_ohlcv("BTC/USDT", "15m", lookback=200)
    assert list(out.columns) == ["timestamp", "open", "high", "low", "close", "volume"]
    assert len(out) == 2


def test_fake_returns_configured_ticker():
    ts = datetime.now(timezone.utc)
    fake = FakeMarketDataSource(tickers={"BTC/USDT": (42000.0, ts)})
    t = fake.fetch_ticker("BTC/USDT")
    assert t.price == 42000.0
    assert t.timestamp == ts


def test_fake_raises_on_unknown_pair():
    fake = FakeMarketDataSource(ohlcv={})
    import pytest
    with pytest.raises(KeyError):
        fake.fetch_ohlcv("UNKNOWN/USDT", "15m", lookback=200)
```

- [ ] **Step 2: Verificar fallo**

```powershell
pytest tests/unit/test_market_fake.py -v
```

Expected: ImportError sobre `crypto_farmer.data.market` o `tests.fakes.market`.

- [ ] **Step 3: Implementar protocolo y fake**

`crypto_farmer/data/__init__.py`: vacío.

`crypto_farmer/data/market.py`:
```python
from __future__ import annotations

from typing import Protocol

import pandas as pd

from crypto_farmer.signals.models import Ticker


class MarketDataSource(Protocol):
    def fetch_ohlcv(self, pair: str, timeframe: str, lookback: int) -> pd.DataFrame:
        """Devuelve un DataFrame con columnas timestamp, open, high, low, close, volume."""

    def fetch_ticker(self, pair: str) -> Ticker:
        ...
```

`tests/fakes/__init__.py`: vacío.

`tests/fakes/market.py`:
```python
from __future__ import annotations

from datetime import datetime

import pandas as pd

from crypto_farmer.signals.models import Ticker


class FakeMarketDataSource:
    def __init__(
        self,
        *,
        ohlcv: dict[str, pd.DataFrame] | None = None,
        tickers: dict[str, tuple[float, datetime]] | None = None,
    ) -> None:
        self._ohlcv = ohlcv or {}
        self._tickers = tickers or {}

    def fetch_ohlcv(self, pair: str, timeframe: str, lookback: int) -> pd.DataFrame:
        if pair not in self._ohlcv:
            raise KeyError(pair)
        return self._ohlcv[pair].tail(lookback).reset_index(drop=True).copy()

    def fetch_ticker(self, pair: str) -> Ticker:
        if pair not in self._tickers:
            raise KeyError(pair)
        price, ts = self._tickers[pair]
        return Ticker(pair=pair, price=price, timestamp=ts)
```

- [ ] **Step 4: Verificar pasa**

```powershell
pytest tests/unit/test_market_fake.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```powershell
git add crypto_farmer/data/ tests/fakes/ tests/unit/test_market_fake.py
git commit -m "feat(data): MarketDataSource protocol + FakeMarketDataSource"
```

---

### Tarea 5: Implementación `CcxtBinanceSource`

**Files:**
- Modify: `crypto_farmer/data/market.py`
- Test: `tests/unit/test_ccxt_binance.py`

- [ ] **Step 1: Test con CCXT mockeado**

`tests/unit/test_ccxt_binance.py`:
```python
from unittest.mock import MagicMock

import pandas as pd
import pytest

from crypto_farmer.data.market import CcxtBinanceSource, MarketFetchError


def _make_ccxt(ohlcv_rows=None, ticker=None, raises=None):
    fake = MagicMock()
    if raises:
        fake.fetch_ohlcv.side_effect = raises
        fake.fetch_ticker.side_effect = raises
    else:
        fake.fetch_ohlcv.return_value = ohlcv_rows or []
        fake.fetch_ticker.return_value = ticker or {}
    return fake


def test_fetch_ohlcv_returns_dataframe():
    raw = [
        [1700000000000, 100.0, 110.0, 95.0, 105.0, 10.0],
        [1700000900000, 105.0, 112.0, 104.0, 110.0, 12.0],
    ]
    exchange = _make_ccxt(ohlcv_rows=raw)
    src = CcxtBinanceSource(exchange=exchange)

    df = src.fetch_ohlcv("BTC/USDT", "15m", lookback=200)
    assert list(df.columns) == ["timestamp", "open", "high", "low", "close", "volume"]
    assert len(df) == 2
    assert df["close"].iloc[-1] == 110.0
    exchange.fetch_ohlcv.assert_called_once_with("BTC/USDT", "15m", limit=200)


def test_fetch_ticker_returns_model():
    exchange = _make_ccxt(ticker={"last": 42000.5, "timestamp": 1700000000000})
    src = CcxtBinanceSource(exchange=exchange)
    t = src.fetch_ticker("BTC/USDT")
    assert t.price == 42000.5
    assert t.pair == "BTC/USDT"


def test_fetch_raises_market_fetch_error_on_ccxt_failure():
    exchange = _make_ccxt(raises=RuntimeError("network down"))
    src = CcxtBinanceSource(exchange=exchange)
    with pytest.raises(MarketFetchError):
        src.fetch_ohlcv("BTC/USDT", "15m", lookback=10)
    with pytest.raises(MarketFetchError):
        src.fetch_ticker("BTC/USDT")
```

- [ ] **Step 2: Verificar fallo**

```powershell
pytest tests/unit/test_ccxt_binance.py -v
```

Expected: ImportError sobre `CcxtBinanceSource`.

- [ ] **Step 3: Implementar `CcxtBinanceSource`**

Añadir al final de `crypto_farmer/data/market.py`:
```python
from datetime import datetime, timezone


class MarketFetchError(Exception):
    pass


class CcxtBinanceSource:
    """Adaptador sobre un exchange ccxt (inyectable). En producción se pasa ccxt.binance()."""

    def __init__(self, exchange) -> None:
        self._exchange = exchange

    def fetch_ohlcv(self, pair: str, timeframe: str, lookback: int) -> pd.DataFrame:
        try:
            rows = self._exchange.fetch_ohlcv(pair, timeframe, limit=lookback)
        except Exception as e:
            raise MarketFetchError(f"fetch_ohlcv {pair} {timeframe}: {e}") from e
        return pd.DataFrame(
            rows, columns=["timestamp", "open", "high", "low", "close", "volume"]
        )

    def fetch_ticker(self, pair: str) -> Ticker:
        try:
            raw = self._exchange.fetch_ticker(pair)
        except Exception as e:
            raise MarketFetchError(f"fetch_ticker {pair}: {e}") from e
        ts_ms = raw.get("timestamp")
        ts = (
            datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
            if ts_ms else datetime.now(timezone.utc)
        )
        return Ticker(pair=pair, price=float(raw["last"]), timestamp=ts)
```

- [ ] **Step 4: Verificar pasa**

```powershell
pytest tests/unit/test_ccxt_binance.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```powershell
git add crypto_farmer/data/market.py tests/unit/test_ccxt_binance.py
git commit -m "feat(data): CcxtBinanceSource implementation with error wrapping"
```

---

## Bloque 4 — Noticias

### Tarea 6: `NewsSource` con fake y `CryptoPanicSource`

**Files:**
- Create: `crypto_farmer/data/news.py`
- Create: `tests/fakes/news.py`
- Test: `tests/unit/test_news_fake.py`
- Test: `tests/unit/test_cryptopanic.py`

- [ ] **Step 1: Test del fake**

`tests/unit/test_news_fake.py`:
```python
from datetime import datetime, timedelta, timezone

from crypto_farmer.signals.models import NewsItem
from tests.fakes.news import FakeNewsSource


def test_fake_news_filters_since():
    now = datetime.now(timezone.utc)
    items = [
        NewsItem(source="x", url="a", title="vieja", body=None,
                 published_at=now - timedelta(hours=6), related_pairs=[]),
        NewsItem(source="x", url="b", title="reciente", body=None,
                 published_at=now - timedelta(hours=1), related_pairs=[]),
    ]
    fake = FakeNewsSource(items=items)
    result = fake.fetch_recent(since=now - timedelta(hours=4))
    assert [i.title for i in result] == ["reciente"]
```

- [ ] **Step 2: Verificar fallo**

```powershell
pytest tests/unit/test_news_fake.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implementar protocolo y fake**

`crypto_farmer/data/news.py`:
```python
from __future__ import annotations

from datetime import datetime
from typing import Protocol

from crypto_farmer.signals.models import NewsItem


class NewsFetchError(Exception):
    pass


class NewsSource(Protocol):
    def fetch_recent(self, since: datetime) -> list[NewsItem]: ...
```

`tests/fakes/news.py`:
```python
from __future__ import annotations

from datetime import datetime

from crypto_farmer.signals.models import NewsItem


class FakeNewsSource:
    def __init__(self, *, items: list[NewsItem] | None = None) -> None:
        self._items = items or []

    def fetch_recent(self, since: datetime) -> list[NewsItem]:
        return [i for i in self._items if i.published_at >= since]
```

- [ ] **Step 4: Test del CryptoPanicSource con `respx`**

`tests/unit/test_cryptopanic.py`:
```python
from datetime import datetime, timedelta, timezone

import httpx
import pytest
import respx

from crypto_farmer.data.news import CryptoPanicSource, NewsFetchError


@respx.mock
def test_cryptopanic_parses_response():
    payload = {
        "results": [
            {
                "id": 1,
                "title": "BTC rompe máximos",
                "url": "https://cryptopanic.com/news/1",
                "published_at": "2026-05-12T10:00:00Z",
                "currencies": [{"code": "BTC"}],
            },
            {
                "id": 2,
                "title": "ETH update",
                "url": "https://cryptopanic.com/news/2",
                "published_at": "2026-05-12T09:30:00Z",
                "currencies": [{"code": "ETH"}],
            },
        ]
    }
    respx.get("https://cryptopanic.com/api/v1/posts/").mock(
        return_value=httpx.Response(200, json=payload)
    )

    src = CryptoPanicSource(token="abc", client=httpx.Client())
    items = src.fetch_recent(since=datetime(2026, 5, 12, 9, 0, tzinfo=timezone.utc))

    assert len(items) == 2
    assert items[0].title == "BTC rompe máximos"
    assert items[0].related_pairs == ["BTC/USDT"]
    assert items[1].related_pairs == ["ETH/USDT"]


@respx.mock
def test_cryptopanic_raises_on_http_error():
    respx.get("https://cryptopanic.com/api/v1/posts/").mock(
        return_value=httpx.Response(500)
    )
    src = CryptoPanicSource(token="abc", client=httpx.Client())
    with pytest.raises(NewsFetchError):
        src.fetch_recent(since=datetime(2026, 5, 12, tzinfo=timezone.utc))


@respx.mock
def test_cryptopanic_filters_by_since():
    payload = {
        "results": [
            {
                "id": 1, "title": "old", "url": "u1",
                "published_at": "2026-05-12T08:00:00Z",
                "currencies": [{"code": "BTC"}],
            },
            {
                "id": 2, "title": "new", "url": "u2",
                "published_at": "2026-05-12T10:00:00Z",
                "currencies": [{"code": "BTC"}],
            },
        ]
    }
    respx.get("https://cryptopanic.com/api/v1/posts/").mock(
        return_value=httpx.Response(200, json=payload)
    )
    src = CryptoPanicSource(token="abc", client=httpx.Client())
    items = src.fetch_recent(since=datetime(2026, 5, 12, 9, 0, tzinfo=timezone.utc))
    assert [i.title for i in items] == ["new"]
```

- [ ] **Step 5: Implementar `CryptoPanicSource`**

Añadir a `crypto_farmer/data/news.py`:
```python
from datetime import timezone

import httpx


class CryptoPanicSource:
    BASE = "https://cryptopanic.com/api/v1/posts/"

    def __init__(self, *, token: str, client: httpx.Client | None = None) -> None:
        self._token = token
        self._client = client or httpx.Client(timeout=15.0)

    def fetch_recent(self, since: datetime) -> list[NewsItem]:
        params = {"auth_token": self._token, "public": "true", "kind": "news"}
        try:
            r = self._client.get(self.BASE, params=params)
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise NewsFetchError(f"cryptopanic: {e}") from e
        results = r.json().get("results", [])
        items: list[NewsItem] = []
        for raw in results:
            published = datetime.fromisoformat(
                raw["published_at"].replace("Z", "+00:00")
            )
            if published < since:
                continue
            related = [
                f"{c['code']}/USDT" for c in raw.get("currencies", [])
                if c.get("code")
            ]
            items.append(NewsItem(
                source="cryptopanic",
                url=raw["url"],
                title=raw["title"],
                body=raw.get("body"),
                published_at=published,
                related_pairs=related,
            ))
        return items
```

- [ ] **Step 6: Verificar pasa**

```powershell
pytest tests/unit/test_news_fake.py tests/unit/test_cryptopanic.py -v
```

Expected: 4 passed.

- [ ] **Step 7: Commit**

```powershell
git add crypto_farmer/data/news.py tests/fakes/news.py tests/unit/test_news_fake.py tests/unit/test_cryptopanic.py
git commit -m "feat(news): NewsSource protocol + Fake + CryptoPanicSource"
```

---

## Bloque 5 — Análisis técnico

### Tarea 7: `IndicatorEngine` con pandas-ta

**Files:**
- Create: `crypto_farmer/analysis/__init__.py`
- Create: `crypto_farmer/analysis/indicators.py`
- Test: `tests/unit/test_indicators.py`

- [ ] **Step 1: Test**

`tests/unit/test_indicators.py`:
```python
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from crypto_farmer.analysis.indicators import IndicatorEngine


def _make_ohlcv(n: int = 100) -> pd.DataFrame:
    rng = np.random.default_rng(seed=42)
    base = 100 + np.cumsum(rng.normal(0, 1, n))
    df = pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=n, freq="15min", tz="UTC"),
        "open": base + rng.normal(0, 0.5, n),
        "high": base + np.abs(rng.normal(0, 1, n)) + 1,
        "low": base - np.abs(rng.normal(0, 1, n)) - 1,
        "close": base,
        "volume": rng.uniform(50, 150, n),
    })
    return df


def test_compute_returns_snapshot():
    engine = IndicatorEngine()
    df = _make_ohlcv(120)
    snap = engine.compute("BTC/USDT", df)
    assert snap.pair == "BTC/USDT"
    assert 0 <= snap.rsi <= 100
    assert snap.ema_20 > 0
    assert snap.ema_50 > 0
    assert snap.atr > 0
    assert snap.volume_mean_24h > 0


def test_compute_raises_on_insufficient_data():
    engine = IndicatorEngine()
    df = _make_ohlcv(10)
    import pytest
    with pytest.raises(ValueError):
        engine.compute("BTC/USDT", df)
```

- [ ] **Step 2: Verificar fallo**

```powershell
pytest tests/unit/test_indicators.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implementar**

`crypto_farmer/analysis/__init__.py`: vacío.

`crypto_farmer/analysis/indicators.py`:
```python
from __future__ import annotations

from datetime import timezone

import pandas as pd
import pandas_ta as ta

from crypto_farmer.signals.models import IndicatorSnapshot


class IndicatorEngine:
    MIN_ROWS = 60

    def compute(self, pair: str, df: pd.DataFrame) -> IndicatorSnapshot:
        if len(df) < self.MIN_ROWS:
            raise ValueError(f"Faltan datos: {len(df)} filas, mínimo {self.MIN_ROWS}")

        d = df.copy()
        d["rsi"] = ta.rsi(d["close"], length=14)
        macd = ta.macd(d["close"], fast=12, slow=26, signal=9)
        d["macd"] = macd["MACD_12_26_9"]
        d["macd_signal"] = macd["MACDs_12_26_9"]
        d["macd_hist"] = macd["MACDh_12_26_9"]
        d["ema_20"] = ta.ema(d["close"], length=20)
        d["ema_50"] = ta.ema(d["close"], length=50)
        bb = ta.bbands(d["close"], length=20, std=2.0)
        d["bb_upper"] = bb["BBU_20_2.0"]
        d["bb_lower"] = bb["BBL_20_2.0"]
        d["atr"] = ta.atr(d["high"], d["low"], d["close"], length=14)
        d["atr_mean_20"] = d["atr"].rolling(20).mean()
        d["volume_mean_24h"] = d["volume"].rolling(96).mean()  # 96×15min = 24h

        last = d.iloc[-1]
        ts = last["timestamp"]
        if hasattr(ts, "to_pydatetime"):
            ts = ts.to_pydatetime()
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        return IndicatorSnapshot(
            pair=pair,
            timestamp=ts,
            rsi=float(last["rsi"]),
            macd=float(last["macd"]),
            macd_signal=float(last["macd_signal"]),
            macd_hist=float(last["macd_hist"]),
            ema_20=float(last["ema_20"]),
            ema_50=float(last["ema_50"]),
            bb_upper=float(last["bb_upper"]),
            bb_lower=float(last["bb_lower"]),
            atr=float(last["atr"]),
            atr_mean_20=float(last["atr_mean_20"]) if pd.notna(last["atr_mean_20"]) else float(last["atr"]),
            volume=float(last["volume"]),
            volume_mean_24h=float(last["volume_mean_24h"]) if pd.notna(last["volume_mean_24h"]) else float(d["volume"].mean()),
        )
```

- [ ] **Step 4: Verificar pasa**

```powershell
pytest tests/unit/test_indicators.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```powershell
git add crypto_farmer/analysis/ tests/unit/test_indicators.py
git commit -m "feat(analysis): IndicatorEngine computing RSI/MACD/EMA/BB/ATR"
```

---

### Tarea 8: `Prefilter` con sus reglas deterministas

**Files:**
- Create: `crypto_farmer/analysis/prefilter.py`
- Test: `tests/unit/test_prefilter.py`

- [ ] **Step 1: Test cubriendo cada regla**

`tests/unit/test_prefilter.py`:
```python
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from crypto_farmer.analysis.prefilter import (
    PrefilterConfig,
    Prefilter,
    PrefilterDecision,
)
from crypto_farmer.signals.models import IndicatorSnapshot, SignalAction


def _snap(**overrides) -> IndicatorSnapshot:
    base = dict(
        pair="BTC/USDT",
        timestamp=datetime.now(timezone.utc),
        rsi=50.0, macd=0.0, macd_signal=0.0, macd_hist=0.0,
        ema_20=100.0, ema_50=100.0,
        bb_upper=110.0, bb_lower=90.0,
        atr=10.0, atr_mean_20=10.0,
        volume=100.0, volume_mean_24h=100.0,
    )
    base.update(overrides)
    return IndicatorSnapshot(**base)


def _cfg() -> PrefilterConfig:
    return PrefilterConfig(
        rsi_oversold=30, rsi_overbought=70,
        volume_anomaly_factor=1.8, atr_expansion_factor=1.5,
        cooldown_minutes=60,
    )


def test_rsi_oversold_passes():
    pf = Prefilter(_cfg())
    decision = pf.evaluate(_snap(rsi=28), recent_history=pd.DataFrame(), last_signal_for_pair=None)
    assert decision.passes
    assert "rsi_extreme" in decision.triggers


def test_rsi_overbought_passes():
    pf = Prefilter(_cfg())
    decision = pf.evaluate(_snap(rsi=72), recent_history=pd.DataFrame(), last_signal_for_pair=None)
    assert decision.passes
    assert "rsi_extreme" in decision.triggers


def test_neutral_rsi_does_not_pass_alone():
    pf = Prefilter(_cfg())
    decision = pf.evaluate(_snap(rsi=50), recent_history=pd.DataFrame(), last_signal_for_pair=None)
    assert not decision.passes


def test_volume_anomaly_passes():
    pf = Prefilter(_cfg())
    decision = pf.evaluate(_snap(volume=200, volume_mean_24h=100), recent_history=pd.DataFrame(), last_signal_for_pair=None)
    assert decision.passes
    assert "volume_anomaly" in decision.triggers


def test_atr_expansion_passes():
    pf = Prefilter(_cfg())
    decision = pf.evaluate(_snap(atr=20, atr_mean_20=10), recent_history=pd.DataFrame(), last_signal_for_pair=None)
    assert decision.passes
    assert "atr_expansion" in decision.triggers


def test_ema_cross_passes():
    pf = Prefilter(_cfg())
    history = pd.DataFrame([
        {"ema_20": 99.0, "ema_50": 100.0},
        {"ema_20": 99.5, "ema_50": 100.0},
        {"ema_20": 100.5, "ema_50": 100.0},
    ])
    decision = pf.evaluate(_snap(ema_20=100.5, ema_50=100.0), recent_history=history, last_signal_for_pair=None)
    assert decision.passes
    assert "ema_cross" in decision.triggers


def test_range_breakout_passes():
    pf = Prefilter(_cfg())
    history = pd.DataFrame({"high": [99.0] * 20, "low": [95.0] * 20, "close": [98.0] * 20})
    snap = _snap()
    # cierre 101 > máximo 99
    decision = pf.evaluate(snap, recent_history=history.assign(close=[98.0]*19 + [101.0]), last_signal_for_pair=None)
    assert decision.passes
    assert "range_breakout" in decision.triggers


def test_cooldown_blocks_same_action():
    pf = Prefilter(_cfg())
    last_time = datetime.now(timezone.utc) - timedelta(minutes=30)
    decision = pf.evaluate(
        _snap(rsi=28),
        recent_history=pd.DataFrame(),
        last_signal_for_pair=(SignalAction.BUY, last_time),
    )
    assert not decision.passes
    assert decision.reason == "cooldown"


def test_cooldown_bypassed_on_direction_change():
    pf = Prefilter(_cfg())
    last_time = datetime.now(timezone.utc) - timedelta(minutes=30)
    decision = pf.evaluate(
        _snap(rsi=72),  # tendencia bajista vs BUY previo
        recent_history=pd.DataFrame(),
        last_signal_for_pair=(SignalAction.BUY, last_time),
    )
    assert decision.passes


def test_cooldown_expired_passes():
    pf = Prefilter(_cfg())
    last_time = datetime.now(timezone.utc) - timedelta(minutes=90)
    decision = pf.evaluate(
        _snap(rsi=28),
        recent_history=pd.DataFrame(),
        last_signal_for_pair=(SignalAction.BUY, last_time),
    )
    assert decision.passes
```

- [ ] **Step 2: Verificar fallo**

```powershell
pytest tests/unit/test_prefilter.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implementar**

`crypto_farmer/analysis/prefilter.py`:
```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import pandas as pd
from pydantic import BaseModel

from crypto_farmer.signals.models import IndicatorSnapshot, SignalAction


class PrefilterConfig(BaseModel):
    rsi_oversold: float
    rsi_overbought: float
    volume_anomaly_factor: float
    atr_expansion_factor: float
    cooldown_minutes: int


@dataclass
class PrefilterDecision:
    passes: bool
    triggers: list[str] = field(default_factory=list)
    reason: str | None = None


def _direction_from_rsi(rsi: float, cfg: PrefilterConfig) -> SignalAction:
    if rsi <= cfg.rsi_oversold:
        return SignalAction.BUY
    if rsi >= cfg.rsi_overbought:
        return SignalAction.SELL
    return SignalAction.HOLD


class Prefilter:
    def __init__(self, cfg: PrefilterConfig) -> None:
        self._cfg = cfg

    def evaluate(
        self,
        snap: IndicatorSnapshot,
        *,
        recent_history: pd.DataFrame,
        last_signal_for_pair: tuple[SignalAction, datetime] | None,
    ) -> PrefilterDecision:
        triggers = self._collect_triggers(snap, recent_history)
        if not triggers:
            return PrefilterDecision(passes=False, reason="no_triggers")

        if last_signal_for_pair is not None:
            last_action, last_time = last_signal_for_pair
            elapsed = datetime.now(timezone.utc) - last_time
            if elapsed < timedelta(minutes=self._cfg.cooldown_minutes):
                proposed = _direction_from_rsi(snap.rsi, self._cfg)
                opposite = {
                    SignalAction.BUY: SignalAction.SELL,
                    SignalAction.SELL: SignalAction.BUY,
                }
                if proposed != opposite.get(last_action):
                    return PrefilterDecision(passes=False, reason="cooldown", triggers=triggers)

        return PrefilterDecision(passes=True, triggers=triggers)

    def _collect_triggers(
        self, snap: IndicatorSnapshot, history: pd.DataFrame
    ) -> list[str]:
        triggers: list[str] = []
        if snap.rsi <= self._cfg.rsi_oversold or snap.rsi >= self._cfg.rsi_overbought:
            triggers.append("rsi_extreme")
        # ratios return None when their denominator is zero (data quality issue).
        # Treat None as "no trigger" — never crash on missing data.
        vol_ratio = snap.volume_anomaly_ratio()
        if vol_ratio is not None and vol_ratio >= self._cfg.volume_anomaly_factor:
            triggers.append("volume_anomaly")
        atr_ratio = snap.atr_expansion_ratio()
        if atr_ratio is not None and atr_ratio >= self._cfg.atr_expansion_factor:
            triggers.append("atr_expansion")
        if self._ema_cross_recent(history):
            triggers.append("ema_cross")
        if self._range_breakout(snap, history):
            triggers.append("range_breakout")
        return triggers

    def _ema_cross_recent(self, history: pd.DataFrame) -> bool:
        if history.empty or {"ema_20", "ema_50"} - set(history.columns):
            return False
        last3 = history.tail(3)
        signs = (last3["ema_20"] - last3["ema_50"]).apply(lambda x: 1 if x > 0 else -1 if x < 0 else 0).tolist()
        return len(set(signs)) > 1  # hubo cambio de signo en las últimas 3 velas

    def _range_breakout(self, snap: IndicatorSnapshot, history: pd.DataFrame) -> bool:
        if history.empty or "high" not in history.columns or "low" not in history.columns:
            return False
        last_20 = history.tail(20)
        if len(last_20) < 5:
            return False
        max_high = last_20["high"].iloc[:-1].max() if len(last_20) > 1 else last_20["high"].max()
        min_low = last_20["low"].iloc[:-1].min() if len(last_20) > 1 else last_20["low"].min()
        close = float(last_20["close"].iloc[-1]) if "close" in last_20.columns else 0.0
        return close > max_high or close < min_low
```

- [ ] **Step 4: Verificar pasa**

```powershell
pytest tests/unit/test_prefilter.py -v
```

Expected: 10 passed.

- [ ] **Step 5: Commit**

```powershell
git add crypto_farmer/analysis/prefilter.py tests/unit/test_prefilter.py
git commit -m "feat(analysis): deterministic Prefilter with 5 triggers + cooldown"
```

---

## Bloque 6 — Persistencia SQLite

### Tarea 9: `Storage` SQLite — esquema y operaciones básicas

**Files:**
- Create: `crypto_farmer/storage/__init__.py`
- Create: `crypto_farmer/storage/db.py`
- Test: `tests/unit/test_storage.py`

- [ ] **Step 1: Test del schema y operaciones**

`tests/unit/test_storage.py`:
```python
import json
from datetime import datetime, timezone
from pathlib import Path

from crypto_farmer.signals.models import (
    CycleStatus, NewsItem, Signal, SignalAction, TimeHorizon,
)
from crypto_farmer.storage.db import Storage


def _signal() -> Signal:
    return Signal(
        action=SignalAction.BUY, confidence=65, reasoning="r",
        entry_price_hint=100.0, invalidation_level=95.0,
        time_horizon=TimeHorizon.SHORT, key_factors=["k1"],
    )


def test_save_cycle_and_signals(tmp_path: Path):
    storage = Storage(db_path=tmp_path / "t.db")
    cycle_id = storage.start_cycle()
    storage.finish_cycle(
        cycle_id, status=CycleStatus.OK,
        pairs_analyzed=10, pairs_passed_prefilter=2,
        signals_generated=2, notes=None,
    )
    sig_id = storage.save_signal(
        cycle_id=cycle_id, pair="BTC/USDT", timeframe="15m",
        signal=_signal(), price_at_signal=100.5, delivered=True,
    )

    cycles = storage.list_recent_cycles(limit=5)
    assert len(cycles) == 1
    assert cycles[0]["status"] == CycleStatus.OK.value

    signals = storage.list_recent_signals(limit=5)
    assert len(signals) == 1
    assert signals[0]["id"] == sig_id
    assert signals[0]["pair"] == "BTC/USDT"

    got = storage.get_signal_by_id(signal_id=sig_id)
    assert got is not None and got["id"] == sig_id
    assert storage.get_signal_by_id(signal_id=9999) is None


def test_save_outcome(tmp_path: Path):
    storage = Storage(db_path=tmp_path / "t.db")
    cycle_id = storage.start_cycle()
    sig_id = storage.save_signal(
        cycle_id=cycle_id, pair="BTC/USDT", timeframe="15m",
        signal=_signal(), price_at_signal=100.0, delivered=True,
    )
    storage.save_outcome(
        signal_id=sig_id, horizon="4h",
        measured_at=datetime.now(timezone.utc),
        price_then=105.0, return_pct=5.0, verdict="correct",
    )

    outcomes = storage.list_outcomes_for_signal(sig_id)
    assert len(outcomes) == 1
    assert outcomes[0]["return_pct"] == 5.0


def test_news_cache_unique_url(tmp_path: Path):
    storage = Storage(db_path=tmp_path / "t.db")
    item = NewsItem(
        source="x", url="https://u/1", title="t", body=None,
        published_at=datetime.now(timezone.utc), related_pairs=["BTC/USDT"],
    )
    storage.save_news_items([item])
    storage.save_news_items([item])  # idempotente por URL UNIQUE
    rows = storage.list_news_since(since=datetime(2020, 1, 1, tzinfo=timezone.utc))
    assert len(rows) == 1


def test_save_analysis_context(tmp_path: Path):
    storage = Storage(db_path=tmp_path / "t.db")
    cycle_id = storage.start_cycle()
    sig_id = storage.save_signal(
        cycle_id=cycle_id, pair="BTC/USDT", timeframe="15m",
        signal=_signal(), price_at_signal=100.0, delivered=True,
    )
    storage.save_analysis_context(
        signal_id=sig_id,
        indicators={"rsi": 28},
        news=[],
        memory_hits=[],
        feedback_summary="ninguna",
        prompt_rendered="prompt",
        raw_llm_response='{"action": "BUY"}',
    )
    ctx = storage.get_analysis_context(sig_id)
    assert ctx is not None
    assert json.loads(ctx["indicators_json"]) == {"rsi": 28}


def test_pending_outcome_jobs(tmp_path: Path):
    storage = Storage(db_path=tmp_path / "t.db")
    cycle_id = storage.start_cycle()
    sig_id = storage.save_signal(
        cycle_id=cycle_id, pair="BTC/USDT", timeframe="15m",
        signal=_signal(), price_at_signal=100.0, delivered=True,
    )
    now = datetime.now(timezone.utc)
    storage.enqueue_outcome_job(signal_id=sig_id, horizon="1h", due_at=now)
    storage.enqueue_outcome_job(signal_id=sig_id, horizon="4h", due_at=now)
    due = storage.list_due_outcome_jobs(now=now)
    assert len(due) == 2
    storage.mark_outcome_job_done(job_id=due[0]["id"])
    due_after = storage.list_due_outcome_jobs(now=now)
    assert len(due_after) == 1
```

- [ ] **Step 2: Verificar fallo**

```powershell
pytest tests/unit/test_storage.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implementar**

`crypto_farmer/storage/__init__.py`: vacío.

`crypto_farmer/storage/db.py`:
```python
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from crypto_farmer.signals.models import CycleStatus, NewsItem, Signal


SCHEMA = """
CREATE TABLE IF NOT EXISTS cycles (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  status TEXT,
  pairs_analyzed INTEGER DEFAULT 0,
  pairs_passed_prefilter INTEGER DEFAULT 0,
  signals_generated INTEGER DEFAULT 0,
  notes TEXT
);

CREATE TABLE IF NOT EXISTS signals (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  cycle_id INTEGER NOT NULL REFERENCES cycles(id),
  pair TEXT NOT NULL,
  timeframe TEXT NOT NULL,
  generated_at TEXT NOT NULL,
  action TEXT NOT NULL,
  confidence INTEGER NOT NULL,
  reasoning TEXT,
  entry_price_hint REAL,
  invalidation_level REAL,
  time_horizon TEXT,
  key_factors_json TEXT,
  delivered INTEGER NOT NULL DEFAULT 0,
  price_at_signal REAL
);
CREATE INDEX IF NOT EXISTS idx_signals_pair ON signals(pair);
CREATE INDEX IF NOT EXISTS idx_signals_generated ON signals(generated_at);

CREATE TABLE IF NOT EXISTS signal_outcomes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  signal_id INTEGER NOT NULL REFERENCES signals(id),
  horizon TEXT NOT NULL,
  measured_at TEXT NOT NULL,
  price_then REAL,
  return_pct REAL,
  verdict TEXT
);
CREATE INDEX IF NOT EXISTS idx_outcomes_signal ON signal_outcomes(signal_id);

CREATE TABLE IF NOT EXISTS analysis_contexts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  signal_id INTEGER NOT NULL UNIQUE REFERENCES signals(id),
  indicators_json TEXT,
  news_json TEXT,
  memory_hits_json TEXT,
  feedback_summary TEXT,
  prompt_rendered TEXT,
  raw_llm_response TEXT
);

CREATE TABLE IF NOT EXISTS news_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source TEXT NOT NULL,
  url TEXT NOT NULL UNIQUE,
  title TEXT,
  body TEXT,
  published_at TEXT,
  fetched_at TEXT,
  related_pairs_json TEXT
);

CREATE TABLE IF NOT EXISTS outcome_jobs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  signal_id INTEGER NOT NULL REFERENCES signals(id),
  horizon TEXT NOT NULL,
  due_at TEXT NOT NULL,
  done INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_jobs_due ON outcome_jobs(due_at, done);
"""


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


class Storage:
    def __init__(self, *, db_path: str | Path) -> None:
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._conn() as c:
            c.executescript(SCHEMA)

    def start_cycle(self) -> int:
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO cycles (started_at) VALUES (?)",
                (_iso(datetime.now(timezone.utc)),),
            )
            return int(cur.lastrowid)

    def finish_cycle(
        self, cycle_id: int, *, status: CycleStatus,
        pairs_analyzed: int, pairs_passed_prefilter: int,
        signals_generated: int, notes: str | None,
    ) -> None:
        with self._conn() as c:
            c.execute(
                "UPDATE cycles SET finished_at=?, status=?, pairs_analyzed=?, "
                "pairs_passed_prefilter=?, signals_generated=?, notes=? WHERE id=?",
                (_iso(datetime.now(timezone.utc)), status.value,
                 pairs_analyzed, pairs_passed_prefilter, signals_generated, notes, cycle_id),
            )

    def save_signal(
        self, *, cycle_id: int, pair: str, timeframe: str,
        signal: Signal, price_at_signal: float, delivered: bool,
    ) -> int:
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO signals (cycle_id, pair, timeframe, generated_at, action, "
                "confidence, reasoning, entry_price_hint, invalidation_level, time_horizon, "
                "key_factors_json, delivered, price_at_signal) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (cycle_id, pair, timeframe, _iso(datetime.now(timezone.utc)),
                 signal.action.value, signal.confidence, signal.reasoning,
                 signal.entry_price_hint, signal.invalidation_level,
                 signal.time_horizon.value, json.dumps(signal.key_factors),
                 1 if delivered else 0, price_at_signal),
            )
            return int(cur.lastrowid)

    def save_outcome(
        self, *, signal_id: int, horizon: str, measured_at: datetime,
        price_then: float, return_pct: float, verdict: str,
    ) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT INTO signal_outcomes (signal_id, horizon, measured_at, "
                "price_then, return_pct, verdict) VALUES (?, ?, ?, ?, ?, ?)",
                (signal_id, horizon, _iso(measured_at), price_then, return_pct, verdict),
            )

    def list_outcomes_for_signal(self, signal_id: int) -> list[dict[str, Any]]:
        with self._conn() as c:
            cur = c.execute(
                "SELECT * FROM signal_outcomes WHERE signal_id=? ORDER BY measured_at",
                (signal_id,),
            )
            return [dict(r) for r in cur.fetchall()]

    def list_recent_cycles(self, *, limit: int) -> list[dict[str, Any]]:
        with self._conn() as c:
            cur = c.execute(
                "SELECT * FROM cycles ORDER BY id DESC LIMIT ?", (limit,)
            )
            return [dict(r) for r in cur.fetchall()]

    def list_recent_signals(self, *, limit: int, pair: str | None = None) -> list[dict[str, Any]]:
        with self._conn() as c:
            if pair:
                cur = c.execute(
                    "SELECT * FROM signals WHERE pair=? ORDER BY id DESC LIMIT ?",
                    (pair, limit),
                )
            else:
                cur = c.execute(
                    "SELECT * FROM signals ORDER BY id DESC LIMIT ?", (limit,)
                )
            return [dict(r) for r in cur.fetchall()]

    def last_signal_for_pair(self, pair: str) -> dict[str, Any] | None:
        rows = self.list_recent_signals(limit=1, pair=pair)
        return rows[0] if rows else None

    def get_signal_by_id(self, *, signal_id: int) -> dict[str, Any] | None:
        with self._conn() as c:
            cur = c.execute("SELECT * FROM signals WHERE id=?", (signal_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def save_news_items(self, items: list[NewsItem]) -> int:
        if not items:
            return 0
        with self._conn() as c:
            inserted = 0
            for n in items:
                try:
                    c.execute(
                        "INSERT INTO news_items (source, url, title, body, "
                        "published_at, fetched_at, related_pairs_json) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (n.source, n.url, n.title, n.body, _iso(n.published_at),
                         _iso(datetime.now(timezone.utc)),
                         json.dumps(n.related_pairs)),
                    )
                    inserted += 1
                except sqlite3.IntegrityError:
                    continue
            return inserted

    def list_news_since(self, since: datetime) -> list[dict[str, Any]]:
        with self._conn() as c:
            cur = c.execute(
                "SELECT * FROM news_items WHERE published_at >= ? ORDER BY published_at DESC",
                (_iso(since),),
            )
            return [dict(r) for r in cur.fetchall()]

    def save_analysis_context(
        self, *, signal_id: int, indicators: dict, news: list,
        memory_hits: list, feedback_summary: str,
        prompt_rendered: str, raw_llm_response: str,
    ) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT INTO analysis_contexts (signal_id, indicators_json, news_json, "
                "memory_hits_json, feedback_summary, prompt_rendered, raw_llm_response) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (signal_id, json.dumps(indicators), json.dumps(news),
                 json.dumps(memory_hits), feedback_summary,
                 prompt_rendered, raw_llm_response),
            )

    def get_analysis_context(self, signal_id: int) -> dict[str, Any] | None:
        with self._conn() as c:
            cur = c.execute(
                "SELECT * FROM analysis_contexts WHERE signal_id=?", (signal_id,)
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def enqueue_outcome_job(
        self, *, signal_id: int, horizon: str, due_at: datetime
    ) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT INTO outcome_jobs (signal_id, horizon, due_at) VALUES (?, ?, ?)",
                (signal_id, horizon, _iso(due_at)),
            )

    def list_due_outcome_jobs(self, *, now: datetime) -> list[dict[str, Any]]:
        with self._conn() as c:
            cur = c.execute(
                "SELECT * FROM outcome_jobs WHERE done=0 AND due_at<=? ORDER BY due_at",
                (_iso(now),),
            )
            return [dict(r) for r in cur.fetchall()]

    def mark_outcome_job_done(self, *, job_id: int) -> None:
        with self._conn() as c:
            c.execute("UPDATE outcome_jobs SET done=1 WHERE id=?", (job_id,))
```

- [ ] **Step 4: Verificar pasa**

```powershell
pytest tests/unit/test_storage.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```powershell
git add crypto_farmer/storage/ tests/unit/test_storage.py
git commit -m "feat(storage): SQLite Storage with schema for cycles/signals/outcomes/news/jobs"
```

---

## Bloque 7 — LLM

### Tarea 10: `LLMClient` protocol + `FakeLLMClient`

**Files:**
- Create: `crypto_farmer/llm/__init__.py`
- Create: `crypto_farmer/llm/client.py`
- Create: `tests/fakes/llm.py`
- Test: `tests/unit/test_llm_fake.py`

- [ ] **Step 1: Test del fake**

`tests/unit/test_llm_fake.py`:
```python
from crypto_farmer.llm.client import AnalysisContext, RawLLMResponse
from crypto_farmer.signals.models import IndicatorSnapshot
from tests.fakes.llm import FakeLLMClient
from datetime import datetime, timezone


def _ctx() -> AnalysisContext:
    snap = IndicatorSnapshot(
        pair="BTC/USDT", timestamp=datetime.now(timezone.utc),
        rsi=28.0, macd=1.0, macd_signal=0.0, macd_hist=1.0,
        ema_20=100.0, ema_50=99.0,
        bb_upper=110.0, bb_lower=90.0,
        atr=5.0, atr_mean_20=4.0,
        volume=120.0, volume_mean_24h=100.0,
    )
    return AnalysisContext(
        pair="BTC/USDT", timeframe="15m",
        indicators=snap, ohlcv_summary={}, news=[],
        memory_hits=[], recent_feedback={"win_rate": 0, "summary": "n/a"},
    )


def test_fake_returns_configured_response():
    fake = FakeLLMClient(responses=[RawLLMResponse(text='{"action":"BUY"}')])
    resp = fake.analyze(_ctx())
    assert resp.text == '{"action":"BUY"}'


def test_fake_cycles_through_responses():
    fake = FakeLLMClient(responses=[
        RawLLMResponse(text="a"), RawLLMResponse(text="b"),
    ])
    assert fake.analyze(_ctx()).text == "a"
    assert fake.analyze(_ctx()).text == "b"
    assert fake.analyze(_ctx()).text == "a"  # vuelve a empezar
```

- [ ] **Step 2: Verificar fallo**

```powershell
pytest tests/unit/test_llm_fake.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implementar protocolo y fake**

`crypto_farmer/llm/__init__.py`: vacío.

`crypto_farmer/llm/client.py`:
```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from crypto_farmer.signals.models import IndicatorSnapshot


@dataclass
class AnalysisContext:
    pair: str
    timeframe: str
    indicators: IndicatorSnapshot
    ohlcv_summary: dict[str, Any]
    news: list[dict[str, Any]]
    memory_hits: list[dict[str, Any]]
    recent_feedback: dict[str, Any]
    portfolio_state: dict[str, Any] = field(default_factory=dict)


@dataclass
class RawLLMResponse:
    text: str
    latency_ms: int = 0


class LLMClient(Protocol):
    def analyze(self, context: AnalysisContext) -> RawLLMResponse: ...
```

`tests/fakes/llm.py`:
```python
from __future__ import annotations

from crypto_farmer.llm.client import AnalysisContext, RawLLMResponse


class FakeLLMClient:
    def __init__(self, *, responses: list[RawLLMResponse]) -> None:
        assert responses
        self._responses = responses
        self._idx = 0

    def analyze(self, context: AnalysisContext) -> RawLLMResponse:
        resp = self._responses[self._idx % len(self._responses)]
        self._idx += 1
        return resp
```

- [ ] **Step 4: Verificar pasa**

```powershell
pytest tests/unit/test_llm_fake.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```powershell
git add crypto_farmer/llm/ tests/fakes/llm.py tests/unit/test_llm_fake.py
git commit -m "feat(llm): LLMClient protocol + AnalysisContext + FakeLLMClient"
```

---

### Tarea 11: Prompt y renderizado Jinja2

**Files:**
- Create: `crypto_farmer/llm/prompts.py`
- Create: `config/prompts/analyze_pair.j2`
- Test: `tests/unit/test_prompts.py`

- [ ] **Step 1: Crear el template**

`config/prompts/analyze_pair.j2`:
```
## Par: {{ pair }} | Timeframe: {{ timeframe }} | Hora: {{ now }}

## Datos técnicos
- RSI: {{ "%.2f"|format(indicators.rsi) }}
- MACD: {{ "%.4f"|format(indicators.macd) }} / signal {{ "%.4f"|format(indicators.macd_signal) }} / hist {{ "%.4f"|format(indicators.macd_hist) }}
- EMA20: {{ "%.2f"|format(indicators.ema_20) }}, EMA50: {{ "%.2f"|format(indicators.ema_50) }}
- Bollinger: [{{ "%.2f"|format(indicators.bb_lower) }}, {{ "%.2f"|format(indicators.bb_upper) }}]
- ATR: {{ "%.2f"|format(indicators.atr) }} (media20 {{ "%.2f"|format(indicators.atr_mean_20) }})
- Volumen: {{ "%.2f"|format(indicators.volume) }} (media24h {{ "%.2f"|format(indicators.volume_mean_24h) }})

## Acción reciente del precio (últimas {{ ohlcv_summary.recent|length }} velas)
{% for c in ohlcv_summary.recent -%}
- O {{ "%.2f"|format(c.open) }} H {{ "%.2f"|format(c.high) }} L {{ "%.2f"|format(c.low) }} C {{ "%.2f"|format(c.close) }} V {{ "%.2f"|format(c.volume) }}
{% endfor %}

## Noticias relevantes (últimas 4h)
{% if news -%}
{% for n in news -%}
- [{{ n.published_at }}] {{ n.title }}
{% endfor %}
{%- else -%}
- (sin noticias relevantes)
{%- endif %}

## Tu rendimiento reciente (últimas {{ recent_feedback.lookback }} señales)
- Win rate: {{ recent_feedback.win_rate }}%
- Resumen: {{ recent_feedback.summary }}

## Situaciones pasadas similares
{% if memory_hits -%}
{% for hit in memory_hits -%}
- [Hace {{ hit.age }}] {{ hit.summary }}. Decidiste {{ hit.action }}. Resultado 4h: {{ hit.outcome_4h }}, 24h: {{ hit.outcome_24h }}.
{% endfor %}
{%- else -%}
- (sin situaciones similares en memoria)
{%- endif %}

## Tu tarea
Analiza el par y responde EXCLUSIVAMENTE con un objeto JSON con este schema, sin texto adicional ni explicación previa:
{
  "action": "BUY" | "SELL" | "HOLD",
  "confidence": entero 0-100,
  "reasoning": string corto (max 500 chars),
  "entry_price_hint": float | null,
  "invalidation_level": float | null,
  "time_horizon": "short" | "medium" | "long",
  "key_factors": [hasta 5 strings]
}
```

- [ ] **Step 2: Test del renderizado**

`tests/unit/test_prompts.py`:
```python
from datetime import datetime, timezone
from pathlib import Path

from crypto_farmer.llm.client import AnalysisContext
from crypto_farmer.llm.prompts import PromptBuilder
from crypto_farmer.signals.models import IndicatorSnapshot, OHLCVCandle, OHLCVSummary

PROMPT_PATH = Path("config/prompts/analyze_pair.j2")


def _ctx() -> AnalysisContext:
    snap = IndicatorSnapshot(
        pair="BTC/USDT", timestamp=datetime.now(timezone.utc),
        rsi=28.5, macd=1.0, macd_signal=0.5, macd_hist=0.5,
        ema_20=100.0, ema_50=99.0,
        bb_upper=110.0, bb_lower=90.0,
        atr=5.0, atr_mean_20=4.0,
        volume=120.0, volume_mean_24h=100.0,
    )
    summary = OHLCVSummary(
        recent=[OHLCVCandle(open=100, high=102, low=99, close=101, volume=10)],
        highest_high=102, lowest_low=99,
    ).model_dump()
    return AnalysisContext(
        pair="BTC/USDT", timeframe="15m", indicators=snap,
        ohlcv_summary=summary, news=[],
        memory_hits=[], recent_feedback={"lookback": 20, "win_rate": 0, "summary": "n/a"},
    )


def test_prompt_renders_minimal_context():
    builder = PromptBuilder(template_path=PROMPT_PATH)
    rendered = builder.render(_ctx(), now=datetime(2026, 5, 12, 10, 0, tzinfo=timezone.utc))
    assert "BTC/USDT" in rendered
    assert "RSI: 28.50" in rendered
    assert "(sin noticias relevantes)" in rendered
    assert "(sin situaciones similares en memoria)" in rendered
    assert "Tu tarea" in rendered


def test_prompt_renders_with_news_and_memory():
    builder = PromptBuilder(template_path=PROMPT_PATH)
    ctx = _ctx()
    ctx.news = [{"published_at": "2026-05-12T09:00:00Z", "title": "BTC rompe"}]
    ctx.memory_hits = [{
        "age": "3 días", "summary": "RSI 27, volumen alto",
        "action": "BUY", "outcome_4h": "+2.1%", "outcome_24h": "+5.3%",
    }]
    rendered = builder.render(ctx, now=datetime(2026, 5, 12, 10, 0, tzinfo=timezone.utc))
    assert "BTC rompe" in rendered
    assert "+2.1%" in rendered


def test_system_message_is_stable():
    builder = PromptBuilder(template_path=PROMPT_PATH)
    sys = builder.system_message()
    assert "analista cuantitativo" in sys
    assert "JSON" in sys
```

- [ ] **Step 3: Verificar fallo**

```powershell
pytest tests/unit/test_prompts.py -v
```

Expected: ImportError.

- [ ] **Step 4: Implementar**

`crypto_farmer/llm/prompts.py`:
```python
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from crypto_farmer.llm.client import AnalysisContext


SYSTEM_MESSAGE = (
    "Eres un analista cuantitativo conservador. Tu objetivo es identificar "
    "oportunidades con relación riesgo/recompensa favorable. Solo emites BUY "
    "o SELL cuando los datos lo justifican; HOLD es perfectamente válido y "
    "preferible a operar con baja convicción. Respondes SIEMPRE con JSON "
    "válido según el schema proporcionado, sin texto adicional."
)


class PromptBuilder:
    def __init__(self, *, template_path: str | Path) -> None:
        path = Path(template_path)
        env = Environment(
            loader=FileSystemLoader(str(path.parent)),
            undefined=StrictUndefined,
            trim_blocks=False,
            lstrip_blocks=False,
        )
        self._template = env.get_template(path.name)

    def render(self, context: AnalysisContext, *, now: datetime) -> str:
        return self._template.render(
            pair=context.pair,
            timeframe=context.timeframe,
            now=now.strftime("%Y-%m-%d %H:%M UTC"),
            indicators=context.indicators,
            ohlcv_summary=context.ohlcv_summary,
            news=context.news,
            memory_hits=context.memory_hits,
            recent_feedback=context.recent_feedback,
        )

    def system_message(self) -> str:
        return SYSTEM_MESSAGE
```

- [ ] **Step 5: Verificar pasa**

```powershell
pytest tests/unit/test_prompts.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Commit**

```powershell
git add crypto_farmer/llm/prompts.py config/prompts/analyze_pair.j2 tests/unit/test_prompts.py
git commit -m "feat(llm): Jinja2 prompt template + PromptBuilder"
```

---

### Tarea 12: `OllamaClient` con httpx

**Files:**
- Modify: `crypto_farmer/llm/client.py`
- Test: `tests/unit/test_ollama_client.py`

- [ ] **Step 1: Test con respx**

`tests/unit/test_ollama_client.py`:
```python
from datetime import datetime, timezone

import httpx
import pytest
import respx

from crypto_farmer.llm.client import (
    AnalysisContext, LLMCallError, OllamaClient,
)
from crypto_farmer.llm.prompts import PromptBuilder
from crypto_farmer.signals.models import IndicatorSnapshot, OHLCVCandle, OHLCVSummary


def _ctx() -> AnalysisContext:
    snap = IndicatorSnapshot(
        pair="BTC/USDT", timestamp=datetime.now(timezone.utc),
        rsi=28, macd=1, macd_signal=0, macd_hist=1,
        ema_20=100, ema_50=99, bb_upper=110, bb_lower=90,
        atr=5, atr_mean_20=4, volume=120, volume_mean_24h=100,
    )
    return AnalysisContext(
        pair="BTC/USDT", timeframe="15m", indicators=snap,
        ohlcv_summary=OHLCVSummary(
            recent=[OHLCVCandle(open=1, high=2, low=0.5, close=1.5, volume=1)],
            highest_high=2, lowest_low=0.5,
        ).model_dump(),
        news=[], memory_hits=[],
        recent_feedback={"lookback": 20, "win_rate": 0, "summary": "n/a"},
    )


@respx.mock
def test_ollama_client_returns_text(tmp_path):
    respx.post("http://localhost:11434/api/chat").mock(
        return_value=httpx.Response(200, json={"message": {"content": '{"action":"HOLD"}'}})
    )
    builder = PromptBuilder(template_path="config/prompts/analyze_pair.j2")
    client = OllamaClient(
        base_url="http://localhost:11434", model="qwen2.5",
        prompt_builder=builder, timeout_seconds=10, http_client=httpx.Client(),
    )
    resp = client.analyze(_ctx())
    assert resp.text == '{"action":"HOLD"}'


@respx.mock
def test_ollama_client_raises_on_http_error():
    respx.post("http://localhost:11434/api/chat").mock(return_value=httpx.Response(500))
    builder = PromptBuilder(template_path="config/prompts/analyze_pair.j2")
    client = OllamaClient(
        base_url="http://localhost:11434", model="qwen2.5",
        prompt_builder=builder, timeout_seconds=10, http_client=httpx.Client(),
    )
    with pytest.raises(LLMCallError):
        client.analyze(_ctx())
```

- [ ] **Step 2: Verificar fallo**

```powershell
pytest tests/unit/test_ollama_client.py -v
```

Expected: ImportError sobre `OllamaClient`.

- [ ] **Step 3: Implementar**

Añadir al final de `crypto_farmer/llm/client.py`:
```python
import time

import httpx

from crypto_farmer.llm.prompts import PromptBuilder


class LLMCallError(Exception):
    pass


class OllamaClient:
    def __init__(
        self, *, base_url: str, model: str,
        prompt_builder: PromptBuilder, timeout_seconds: int,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._model = model
        self._prompt_builder = prompt_builder
        self._timeout = timeout_seconds
        self._client = http_client or httpx.Client(timeout=timeout_seconds)

    def analyze(self, context: AnalysisContext) -> RawLLMResponse:
        from datetime import datetime, timezone
        prompt = self._prompt_builder.render(context, now=datetime.now(timezone.utc))
        payload = {
            "model": self._model,
            "stream": False,
            "messages": [
                {"role": "system", "content": self._prompt_builder.system_message()},
                {"role": "user", "content": prompt},
            ],
            "options": {"temperature": 0.2},
        }
        t0 = time.monotonic()
        try:
            r = self._client.post(f"{self._base}/api/chat", json=payload)
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise LLMCallError(f"ollama: {e}") from e
        latency_ms = int((time.monotonic() - t0) * 1000)
        text = r.json().get("message", {}).get("content", "")
        return RawLLMResponse(text=text, latency_ms=latency_ms)
```

- [ ] **Step 4: Verificar pasa**

```powershell
pytest tests/unit/test_ollama_client.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```powershell
git add crypto_farmer/llm/client.py tests/unit/test_ollama_client.py
git commit -m "feat(llm): OllamaClient using httpx with timeout and error wrapping"
```

---

### Tarea 13: Parser con pydantic + retry

**Files:**
- Create: `crypto_farmer/llm/parser.py`
- Test: `tests/unit/test_parser.py`

- [ ] **Step 1: Test**

`tests/unit/test_parser.py`:
```python
import pytest

from crypto_farmer.llm.client import AnalysisContext, RawLLMResponse
from crypto_farmer.llm.parser import (
    LLMParseError, SignalParser, parse_signal_strict,
)
from crypto_farmer.signals.models import SignalAction


def test_parse_strict_ok():
    raw = '{"action":"BUY","confidence":75,"reasoning":"r","entry_price_hint":100.0,"invalidation_level":95.0,"time_horizon":"short","key_factors":["x"]}'
    s = parse_signal_strict(raw)
    assert s.action == SignalAction.BUY
    assert s.confidence == 75


def test_parse_strict_rejects_invalid_json():
    with pytest.raises(LLMParseError):
        parse_signal_strict("not-json")


def test_parse_strict_rejects_bad_schema():
    with pytest.raises(LLMParseError):
        parse_signal_strict('{"action":"INVALID","confidence":5,"reasoning":"r","entry_price_hint":null,"invalidation_level":null,"time_horizon":"short","key_factors":[]}')


class _StubClient:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    def analyze(self, ctx):
        self.calls += 1
        return RawLLMResponse(text=self._responses.pop(0))


def _ctx_stub() -> AnalysisContext:
    from datetime import datetime, timezone
    from crypto_farmer.signals.models import IndicatorSnapshot
    return AnalysisContext(
        pair="BTC/USDT", timeframe="15m",
        indicators=IndicatorSnapshot(
            pair="BTC/USDT", timestamp=datetime.now(timezone.utc),
            rsi=28, macd=0, macd_signal=0, macd_hist=0,
            ema_20=100, ema_50=100, bb_upper=110, bb_lower=90,
            atr=5, atr_mean_20=5, volume=100, volume_mean_24h=100,
        ),
        ohlcv_summary={}, news=[], memory_hits=[],
        recent_feedback={"lookback": 20, "win_rate": 0, "summary": "n/a"},
    )


def test_parser_with_retry_succeeds_second_time():
    stub = _StubClient(responses=[
        "garbage",
        '{"action":"BUY","confidence":70,"reasoning":"r","entry_price_hint":null,"invalidation_level":null,"time_horizon":"short","key_factors":[]}',
    ])
    parser = SignalParser(llm_client=stub, max_retries=1)
    out = parser.analyze_with_retry(_ctx_stub())
    assert out.signal.action == SignalAction.BUY
    assert stub.calls == 2
    assert out.raw_text.startswith('{"action":"BUY"')


def test_parser_with_retry_gives_up():
    stub = _StubClient(responses=["g1", "g2"])
    parser = SignalParser(llm_client=stub, max_retries=1)
    with pytest.raises(LLMParseError):
        parser.analyze_with_retry(_ctx_stub())
    assert stub.calls == 2
```

- [ ] **Step 2: Verificar fallo**

```powershell
pytest tests/unit/test_parser.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implementar**

`crypto_farmer/llm/parser.py`:
```python
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from pydantic import ValidationError

from crypto_farmer.llm.client import AnalysisContext, LLMClient
from crypto_farmer.signals.models import Signal


class LLMParseError(Exception):
    pass


@dataclass
class ParsedSignal:
    signal: Signal
    raw_text: str
    attempts: int


_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json(text: str) -> str:
    # Acepta JSON pelado o JSON dentro de bloque "```json ... ```"
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        return fence.group(1)
    match = _JSON_BLOCK.search(text)
    if match:
        return match.group(0)
    return text


def parse_signal_strict(text: str) -> Signal:
    json_text = _extract_json(text)
    try:
        data = json.loads(json_text)
    except json.JSONDecodeError as e:
        raise LLMParseError(f"json inválido: {e}") from e
    try:
        return Signal.model_validate(data)
    except ValidationError as e:
        raise LLMParseError(f"schema inválido: {e}") from e


class SignalParser:
    RETRY_PREFIX = (
        "Tu respuesta anterior no fue JSON válido. Responde EXCLUSIVAMENTE con "
        "el JSON pedido, sin texto adicional:"
    )

    def __init__(self, *, llm_client: LLMClient, max_retries: int) -> None:
        self._client = llm_client
        self._max_retries = max_retries

    def analyze_with_retry(self, context: AnalysisContext) -> ParsedSignal:
        attempts = 0
        last_error: Exception | None = None
        last_text = ""
        while attempts <= self._max_retries:
            attempts += 1
            resp = self._client.analyze(context)
            last_text = resp.text
            try:
                signal = parse_signal_strict(resp.text)
                return ParsedSignal(signal=signal, raw_text=resp.text, attempts=attempts)
            except LLMParseError as e:
                last_error = e
        raise LLMParseError(
            f"parse falló tras {attempts} intentos: {last_error}; texto final: {last_text[:200]}"
        )
```

- [ ] **Step 4: Verificar pasa**

```powershell
pytest tests/unit/test_parser.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```powershell
git add crypto_farmer/llm/parser.py tests/unit/test_parser.py
git commit -m "feat(llm): SignalParser with strict JSON validation and 1-retry policy"
```

---

## Bloque 8 — Aprendizaje (feedback + RAG)

### Tarea 14: `Situation` — snapshot vectorizable

**Files:**
- Create: `crypto_farmer/learning/__init__.py`
- Create: `crypto_farmer/learning/situation.py`
- Test: `tests/unit/test_situation.py`

- [ ] **Step 1: Test**

`tests/unit/test_situation.py`:
```python
from datetime import datetime, timezone

from crypto_farmer.learning.situation import Situation
from crypto_farmer.signals.models import IndicatorSnapshot


def _snap(**kw) -> IndicatorSnapshot:
    base = dict(
        pair="BTC/USDT", timestamp=datetime(2026, 5, 12, 10, tzinfo=timezone.utc),
        rsi=28.5, macd=1.0, macd_signal=0.5, macd_hist=0.5,
        ema_20=100.0, ema_50=99.0, bb_upper=110.0, bb_lower=90.0,
        atr=5.0, atr_mean_20=4.0, volume=120.0, volume_mean_24h=100.0,
    )
    base.update(kw)
    return IndicatorSnapshot(**base)


def test_situation_text_contains_key_info():
    s = Situation.from_snapshot(_snap())
    txt = s.as_text()
    assert "BTC/USDT" in txt
    assert "RSI 28.5" in txt
    assert "ATR" in txt
    assert "MACD" in txt


def test_situation_summary_short():
    s = Situation.from_snapshot(_snap(rsi=72))
    summary = s.short_summary()
    assert len(summary) <= 200
    assert "sobrecompra" in summary.lower() or "rsi" in summary.lower()
```

- [ ] **Step 2: Verificar fallo**

```powershell
pytest tests/unit/test_situation.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implementar**

`crypto_farmer/learning/__init__.py`: vacío.

`crypto_farmer/learning/situation.py`:
```python
from __future__ import annotations

from dataclasses import dataclass

from crypto_farmer.signals.models import IndicatorSnapshot


@dataclass
class Situation:
    pair: str
    rsi: float
    macd: float
    macd_signal: float
    ema_20: float
    ema_50: float
    atr_ratio: float
    volume_ratio: float
    bb_position: float  # 0 = en BB inferior, 1 = en BB superior

    @classmethod
    def from_snapshot(cls, snap: IndicatorSnapshot) -> "Situation":
        bb_width = snap.bb_upper - snap.bb_lower
        bb_pos = ((snap.ema_20 - snap.bb_lower) / bb_width) if bb_width > 0 else 0.5
        return cls(
            pair=snap.pair,
            rsi=snap.rsi,
            macd=snap.macd,
            macd_signal=snap.macd_signal,
            ema_20=snap.ema_20,
            ema_50=snap.ema_50,
            atr_ratio=snap.atr_expansion_ratio(),
            volume_ratio=snap.volume_anomaly_ratio(),
            bb_position=max(0.0, min(1.0, bb_pos)),
        )

    def as_text(self) -> str:
        return (
            f"Situación {self.pair}: "
            f"RSI {self.rsi:.1f}, "
            f"MACD {self.macd:.4f}/signal {self.macd_signal:.4f}, "
            f"EMA20 vs EMA50: {self.ema_20:.2f} vs {self.ema_50:.2f} "
            f"({'alcista' if self.ema_20 > self.ema_50 else 'bajista'}), "
            f"ATR expansion {self.atr_ratio:.2f}x, "
            f"volumen {self.volume_ratio:.2f}x media, "
            f"posición en BB {self.bb_position:.2f}"
        )

    def short_summary(self) -> str:
        rsi_label = (
            "sobreventa" if self.rsi <= 30
            else "sobrecompra" if self.rsi >= 70
            else "neutral"
        )
        trend = "alcista" if self.ema_20 > self.ema_50 else "bajista"
        return (
            f"{self.pair} RSI {rsi_label} ({self.rsi:.0f}), "
            f"tendencia {trend}, vol {self.volume_ratio:.1f}x"
        )
```

- [ ] **Step 4: Verificar pasa**

```powershell
pytest tests/unit/test_situation.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```powershell
git add crypto_farmer/learning/ tests/unit/test_situation.py
git commit -m "feat(learning): Situation extracted from IndicatorSnapshot with text/summary"
```

---

### Tarea 15: `Embeddings` cliente sobre Ollama

**Files:**
- Create: `crypto_farmer/learning/embeddings.py`
- Test: `tests/unit/test_embeddings.py`

- [ ] **Step 1: Test**

`tests/unit/test_embeddings.py`:
```python
import httpx
import pytest
import respx

from crypto_farmer.learning.embeddings import EmbeddingError, OllamaEmbeddings


@respx.mock
def test_ollama_embed_returns_vector():
    respx.post("http://localhost:11434/api/embeddings").mock(
        return_value=httpx.Response(200, json={"embedding": [0.1, 0.2, 0.3]})
    )
    emb = OllamaEmbeddings(
        base_url="http://localhost:11434", model="nomic-embed-text",
        http_client=httpx.Client(),
    )
    vec = emb.embed("hola mundo")
    assert vec == [0.1, 0.2, 0.3]


@respx.mock
def test_ollama_embed_raises_on_http_error():
    respx.post("http://localhost:11434/api/embeddings").mock(
        return_value=httpx.Response(503)
    )
    emb = OllamaEmbeddings(
        base_url="http://localhost:11434", model="nomic-embed-text",
        http_client=httpx.Client(),
    )
    with pytest.raises(EmbeddingError):
        emb.embed("hola")
```

- [ ] **Step 2: Verificar fallo**

```powershell
pytest tests/unit/test_embeddings.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implementar**

`crypto_farmer/learning/embeddings.py`:
```python
from __future__ import annotations

from typing import Protocol

import httpx


class EmbeddingError(Exception):
    pass


class Embeddings(Protocol):
    def embed(self, text: str) -> list[float]: ...


class OllamaEmbeddings:
    def __init__(
        self, *, base_url: str, model: str,
        http_client: httpx.Client | None = None, timeout: float = 30.0,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._model = model
        self._client = http_client or httpx.Client(timeout=timeout)

    def embed(self, text: str) -> list[float]:
        try:
            r = self._client.post(
                f"{self._base}/api/embeddings",
                json={"model": self._model, "prompt": text},
            )
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise EmbeddingError(f"ollama embeddings: {e}") from e
        data = r.json()
        return list(data["embedding"])
```

- [ ] **Step 4: Verificar pasa**

```powershell
pytest tests/unit/test_embeddings.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```powershell
git add crypto_farmer/learning/embeddings.py tests/unit/test_embeddings.py
git commit -m "feat(learning): OllamaEmbeddings client + Embeddings protocol"
```

---

### Tarea 16: `Memory` con ChromaDB

**Files:**
- Create: `crypto_farmer/learning/memory.py`
- Create: `tests/fakes/memory.py`
- Test: `tests/unit/test_memory_fake.py`
- Test: `tests/unit/test_chroma_memory.py`

- [ ] **Step 1: Fake en memoria + test**

`tests/fakes/memory.py`:
```python
from __future__ import annotations

from dataclasses import dataclass, field

from crypto_farmer.learning.memory import MemoryHit


@dataclass
class _Entry:
    embedding: list[float]
    metadata: dict
    text: str


class InMemoryMemory:
    def __init__(self) -> None:
        self._entries: list[_Entry] = []

    def add(self, *, embedding, text, metadata) -> str:
        eid = str(len(self._entries))
        self._entries.append(_Entry(embedding=list(embedding), metadata={**metadata, "id": eid}, text=text))
        return eid

    def search(self, *, embedding, k, pair_filter=None) -> list[MemoryHit]:
        def cos(a, b):
            num = sum(x*y for x, y in zip(a, b))
            da = sum(x*x for x in a) ** 0.5
            db = sum(x*x for x in b) ** 0.5
            return num / (da*db) if da and db else 0.0

        ranked = []
        for e in self._entries:
            if pair_filter and e.metadata.get("pair") != pair_filter:
                continue
            ranked.append((cos(e.embedding, embedding), e))
        ranked.sort(key=lambda t: -t[0])
        return [
            MemoryHit(
                id=e.metadata["id"], score=s, text=e.text, metadata=e.metadata,
            )
            for s, e in ranked[:k]
        ]

    def update_outcome(self, *, entry_id: str, return_4h, return_24h) -> None:
        for e in self._entries:
            if e.metadata.get("id") == entry_id:
                e.metadata["return_4h"] = return_4h
                e.metadata["return_24h"] = return_24h
                return
```

`tests/unit/test_memory_fake.py`:
```python
from tests.fakes.memory import InMemoryMemory


def test_fake_memory_search_returns_top_k():
    m = InMemoryMemory()
    m.add(embedding=[1.0, 0.0], text="a", metadata={"pair": "BTC/USDT", "action": "BUY"})
    m.add(embedding=[0.0, 1.0], text="b", metadata={"pair": "ETH/USDT", "action": "SELL"})
    m.add(embedding=[0.9, 0.1], text="c", metadata={"pair": "BTC/USDT", "action": "BUY"})

    hits = m.search(embedding=[1.0, 0.0], k=2)
    assert len(hits) == 2
    assert hits[0].metadata["pair"] == "BTC/USDT"


def test_fake_memory_pair_filter():
    m = InMemoryMemory()
    m.add(embedding=[1.0, 0.0], text="a", metadata={"pair": "BTC/USDT"})
    m.add(embedding=[1.0, 0.0], text="b", metadata={"pair": "ETH/USDT"})
    hits = m.search(embedding=[1.0, 0.0], k=5, pair_filter="ETH/USDT")
    assert len(hits) == 1
    assert hits[0].metadata["pair"] == "ETH/USDT"


def test_fake_memory_update_outcome():
    m = InMemoryMemory()
    eid = m.add(embedding=[1.0], text="x", metadata={"pair": "BTC/USDT"})
    m.update_outcome(entry_id=eid, return_4h=2.0, return_24h=5.0)
    hits = m.search(embedding=[1.0], k=1)
    assert hits[0].metadata["return_4h"] == 2.0
    assert hits[0].metadata["return_24h"] == 5.0
```

- [ ] **Step 2: Test del Memory real (Chroma) opt-in**

`tests/unit/test_chroma_memory.py`:
```python
import pytest

from crypto_farmer.learning.memory import ChromaMemory


def test_chroma_memory_roundtrip(tmp_path):
    pytest.importorskip("chromadb")
    m = ChromaMemory(persist_dir=str(tmp_path / "chroma"), collection_name="situations")
    eid = m.add(
        embedding=[0.1, 0.2, 0.3],
        text="situación BTC sobreventa",
        metadata={"pair": "BTC/USDT", "action": "BUY", "timestamp": "2026-05-12T10:00:00Z"},
    )
    assert eid

    hits = m.search(embedding=[0.1, 0.2, 0.3], k=1)
    assert len(hits) == 1
    assert hits[0].metadata["pair"] == "BTC/USDT"

    m.update_outcome(entry_id=eid, return_4h=2.1, return_24h=5.0)
    hits = m.search(embedding=[0.1, 0.2, 0.3], k=1)
    assert hits[0].metadata.get("return_4h") == 2.1
```

- [ ] **Step 3: Verificar fallos**

```powershell
pytest tests/unit/test_memory_fake.py tests/unit/test_chroma_memory.py -v
```

Expected: ImportError sobre `crypto_farmer.learning.memory`.

- [ ] **Step 4: Implementar protocolos + ChromaMemory**

`crypto_farmer/learning/memory.py`:
```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class MemoryHit:
    id: str
    score: float
    text: str
    metadata: dict[str, Any]


class Memory(Protocol):
    def add(self, *, embedding: list[float], text: str, metadata: dict) -> str: ...
    def search(
        self, *, embedding: list[float], k: int, pair_filter: str | None = None,
    ) -> list[MemoryHit]: ...
    def update_outcome(
        self, *, entry_id: str, return_4h: float, return_24h: float
    ) -> None: ...


class ChromaMemory:
    def __init__(self, *, persist_dir: str, collection_name: str) -> None:
        import chromadb
        self._client = chromadb.PersistentClient(path=persist_dir)
        self._collection = self._client.get_or_create_collection(
            name=collection_name, metadata={"hnsw:space": "cosine"},
        )
        self._counter = self._collection.count()

    def add(self, *, embedding: list[float], text: str, metadata: dict) -> str:
        self._counter += 1
        entry_id = f"sit_{self._counter}"
        self._collection.add(
            ids=[entry_id], embeddings=[embedding],
            documents=[text], metadatas=[metadata],
        )
        return entry_id

    def search(
        self, *, embedding: list[float], k: int, pair_filter: str | None = None,
    ) -> list[MemoryHit]:
        where = {"pair": pair_filter} if pair_filter else None
        res = self._collection.query(
            query_embeddings=[embedding], n_results=k, where=where,
        )
        ids = res.get("ids", [[]])[0]
        docs = res.get("documents", [[]])[0]
        metas = res.get("metadatas", [[]])[0]
        dists = res.get("distances", [[]])[0]
        hits: list[MemoryHit] = []
        for i, doc, meta, dist in zip(ids, docs, metas, dists):
            # distancia cosine → score = 1 - dist
            hits.append(MemoryHit(id=i, score=max(0.0, 1.0 - float(dist)), text=doc, metadata=dict(meta)))
        return hits

    def update_outcome(
        self, *, entry_id: str, return_4h: float, return_24h: float
    ) -> None:
        existing = self._collection.get(ids=[entry_id])
        metas = existing.get("metadatas", [[]])
        if not metas or not metas[0]:
            return
        new_meta = dict(metas[0])
        new_meta["return_4h"] = return_4h
        new_meta["return_24h"] = return_24h
        self._collection.update(ids=[entry_id], metadatas=[new_meta])
```

- [ ] **Step 5: Verificar pasa**

```powershell
pytest tests/unit/test_memory_fake.py tests/unit/test_chroma_memory.py -v
```

Expected: 4 passed (3 del fake + 1 del Chroma).

- [ ] **Step 6: Commit**

```powershell
git add crypto_farmer/learning/memory.py tests/fakes/memory.py tests/unit/test_memory_fake.py tests/unit/test_chroma_memory.py
git commit -m "feat(learning): Memory protocol + InMemoryMemory fake + ChromaMemory"
```

---

### Tarea 17: `OutcomeService` — programa y mide outcomes

**Files:**
- Create: `crypto_farmer/learning/outcomes.py`
- Test: `tests/unit/test_outcomes.py`

- [ ] **Step 1: Test**

`tests/unit/test_outcomes.py`:
```python
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest

from crypto_farmer.learning.outcomes import OutcomeService
from crypto_farmer.signals.models import (
    CycleStatus, Signal, SignalAction, TimeHorizon,
)
from crypto_farmer.storage.db import Storage
from tests.fakes.market import FakeMarketDataSource


def _signal(action: SignalAction = SignalAction.BUY) -> Signal:
    return Signal(
        action=action, confidence=70, reasoning="r",
        entry_price_hint=None, invalidation_level=None,
        time_horizon=TimeHorizon.SHORT, key_factors=[],
    )


def test_schedule_creates_jobs_at_correct_due_times(tmp_path: Path):
    storage = Storage(db_path=tmp_path / "t.db")
    cycle_id = storage.start_cycle()
    sig_id = storage.save_signal(
        cycle_id=cycle_id, pair="BTC/USDT", timeframe="15m",
        signal=_signal(), price_at_signal=100.0, delivered=True,
    )

    market = FakeMarketDataSource(
        tickers={"BTC/USDT": (100.0, datetime.now(timezone.utc))}
    )
    svc = OutcomeService(
        storage=storage, market=market, horizons_hours=[1, 4, 24], memory=None,
    )
    now = datetime.now(timezone.utc)
    svc.schedule_measurements(signal_id=sig_id, generated_at=now)

    jobs = storage.list_due_outcome_jobs(now=now + timedelta(hours=25))
    horizons = sorted([j["horizon"] for j in jobs])
    assert horizons == ["1h", "24h", "4h"]


def test_run_due_jobs_measures_and_saves_outcome(tmp_path: Path):
    storage = Storage(db_path=tmp_path / "t.db")
    cycle_id = storage.start_cycle()
    sig_id = storage.save_signal(
        cycle_id=cycle_id, pair="BTC/USDT", timeframe="15m",
        signal=_signal(), price_at_signal=100.0, delivered=True,
    )
    now = datetime.now(timezone.utc)
    market = FakeMarketDataSource(
        tickers={"BTC/USDT": (105.0, now)}
    )
    svc = OutcomeService(
        storage=storage, market=market, horizons_hours=[1, 4, 24], memory=None,
    )
    storage.enqueue_outcome_job(signal_id=sig_id, horizon="1h", due_at=now)

    svc.run_due_jobs(now=now + timedelta(seconds=1))

    outcomes = storage.list_outcomes_for_signal(sig_id)
    assert len(outcomes) == 1
    assert outcomes[0]["horizon"] == "1h"
    assert outcomes[0]["return_pct"] == 5.0
    assert outcomes[0]["verdict"] == "correct"  # BUY y subió → correct


def test_verdict_for_sell_signal(tmp_path: Path):
    storage = Storage(db_path=tmp_path / "t.db")
    cycle_id = storage.start_cycle()
    sig_id = storage.save_signal(
        cycle_id=cycle_id, pair="BTC/USDT", timeframe="15m",
        signal=_signal(action=SignalAction.SELL), price_at_signal=100.0, delivered=True,
    )
    now = datetime.now(timezone.utc)
    market = FakeMarketDataSource(tickers={"BTC/USDT": (95.0, now)})
    svc = OutcomeService(
        storage=storage, market=market, horizons_hours=[1, 4, 24], memory=None,
    )
    storage.enqueue_outcome_job(signal_id=sig_id, horizon="4h", due_at=now)
    svc.run_due_jobs(now=now + timedelta(seconds=1))

    outcomes = storage.list_outcomes_for_signal(sig_id)
    # SELL y bajó → correct
    assert outcomes[0]["verdict"] == "correct"
    assert outcomes[0]["return_pct"] == pytest.approx(-5.0)
```

- [ ] **Step 2: Verificar fallo**

```powershell
pytest tests/unit/test_outcomes.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implementar**

`crypto_farmer/learning/outcomes.py`:
```python
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable

from crypto_farmer.data.market import MarketDataSource, MarketFetchError
from crypto_farmer.learning.memory import Memory
from crypto_farmer.logging_setup import get_logger
from crypto_farmer.signals.models import SignalAction
from crypto_farmer.storage.db import Storage


log = get_logger(__name__)


def _verdict(action: str, return_pct: float, *, threshold: float = 0.5) -> str:
    if abs(return_pct) < threshold:
        return "neutral"
    if action == SignalAction.BUY.value:
        return "correct" if return_pct > 0 else "incorrect"
    if action == SignalAction.SELL.value:
        return "correct" if return_pct < 0 else "incorrect"
    return "neutral"  # HOLD


class OutcomeService:
    MAX_STALE_HOURS = 48

    def __init__(
        self, *, storage: Storage, market: MarketDataSource,
        horizons_hours: Iterable[int], memory: Memory | None,
    ) -> None:
        self._storage = storage
        self._market = market
        self._horizons = list(horizons_hours)
        self._memory = memory

    def schedule_measurements(
        self, *, signal_id: int, generated_at: datetime
    ) -> None:
        for h in self._horizons:
            due = generated_at + timedelta(hours=h)
            self._storage.enqueue_outcome_job(
                signal_id=signal_id, horizon=f"{h}h", due_at=due,
            )

    def run_due_jobs(self, *, now: datetime) -> int:
        jobs = self._storage.list_due_outcome_jobs(now=now)
        measured = 0
        for job in jobs:
            due_at = datetime.fromisoformat(job["due_at"].replace("Z", "+00:00"))
            if (now - due_at) > timedelta(hours=self.MAX_STALE_HOURS):
                self._storage.mark_outcome_job_done(job_id=job["id"])
                log.info("outcome_job_stale_discarded", extra={"job_id": job["id"]})
                continue
            try:
                self._measure(job, now=now)
                measured += 1
            except MarketFetchError as e:
                log.warning("outcome_market_fetch_failed",
                            extra={"job_id": job["id"], "error": str(e)})
                # No marcar done: reintentar al siguiente ciclo
                continue
            self._storage.mark_outcome_job_done(job_id=job["id"])
        return measured

    def _measure(self, job: dict, *, now: datetime) -> None:
        sig_id = job["signal_id"]
        sig_row = self._storage.get_signal_by_id(signal_id=sig_id)
        if sig_row is None:
            return
        ticker = self._market.fetch_ticker(sig_row["pair"])
        price_then = ticker.price
        price_now = ticker.price
        # nota: precio "now" del job = ticker actual; entry price = sig_row.price_at_signal
        entry_price = float(sig_row["price_at_signal"])
        return_pct = (price_now - entry_price) / entry_price * 100.0
        verdict = _verdict(sig_row["action"], return_pct)
        self._storage.save_outcome(
            signal_id=sig_id, horizon=job["horizon"],
            measured_at=now, price_then=price_now,
            return_pct=return_pct, verdict=verdict,
        )
        # Si tenemos memoria y este horizonte es 4h o 24h, actualizamos su metadata
        if self._memory is not None and job["horizon"] in ("4h", "24h"):
            log.debug("memory_outcome_update", extra={"signal_id": sig_id, "horizon": job["horizon"]})
```

- [ ] **Step 4: Verificar pasa**

```powershell
pytest tests/unit/test_outcomes.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```powershell
git add crypto_farmer/learning/outcomes.py tests/unit/test_outcomes.py
git commit -m "feat(learning): OutcomeService schedules and measures signal outcomes"
```

---

### Tarea 18: `FeedbackBuilder` — resumen de últimas N señales

**Files:**
- Create: `crypto_farmer/learning/feedback.py`
- Test: `tests/unit/test_feedback.py`

- [ ] **Step 1: Test**

`tests/unit/test_feedback.py`:
```python
from pathlib import Path

from crypto_farmer.learning.feedback import FeedbackBuilder
from crypto_farmer.signals.models import (
    Signal, SignalAction, TimeHorizon,
)
from crypto_farmer.storage.db import Storage


def _sig(action: SignalAction) -> Signal:
    return Signal(
        action=action, confidence=70, reasoning="r",
        entry_price_hint=None, invalidation_level=None,
        time_horizon=TimeHorizon.SHORT, key_factors=[],
    )


def test_feedback_with_no_signals(tmp_path: Path):
    storage = Storage(db_path=tmp_path / "t.db")
    fb = FeedbackBuilder(storage=storage)
    out = fb.build(lookback=20)
    assert out["lookback"] == 20
    assert out["win_rate"] == 0
    assert "sin histórico" in out["summary"].lower()


def test_feedback_computes_win_rate(tmp_path: Path):
    storage = Storage(db_path=tmp_path / "t.db")
    cycle = storage.start_cycle()
    import datetime as _dt
    now = _dt.datetime.now(_dt.timezone.utc)

    s1 = storage.save_signal(
        cycle_id=cycle, pair="BTC/USDT", timeframe="15m",
        signal=_sig(SignalAction.BUY), price_at_signal=100.0, delivered=True,
    )
    s2 = storage.save_signal(
        cycle_id=cycle, pair="ETH/USDT", timeframe="15m",
        signal=_sig(SignalAction.SELL), price_at_signal=2000.0, delivered=True,
    )
    storage.save_outcome(
        signal_id=s1, horizon="4h", measured_at=now,
        price_then=105.0, return_pct=5.0, verdict="correct",
    )
    storage.save_outcome(
        signal_id=s2, horizon="4h", measured_at=now,
        price_then=2050.0, return_pct=2.5, verdict="incorrect",  # SELL pero subió
    )

    fb = FeedbackBuilder(storage=storage)
    out = fb.build(lookback=10)
    assert out["win_rate"] == 50  # 1 de 2
    assert "BTC/USDT" in out["summary"]
```

- [ ] **Step 2: Verificar fallo**

```powershell
pytest tests/unit/test_feedback.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implementar**

`crypto_farmer/learning/feedback.py`:
```python
from __future__ import annotations

from crypto_farmer.storage.db import Storage


class FeedbackBuilder:
    def __init__(self, *, storage: Storage) -> None:
        self._storage = storage

    def build(self, *, lookback: int) -> dict:
        signals = self._storage.list_recent_signals(limit=lookback)
        if not signals:
            return {
                "lookback": lookback,
                "win_rate": 0,
                "summary": "Sin histórico previo.",
            }

        rated = []
        for s in signals:
            outcomes = self._storage.list_outcomes_for_signal(s["id"])
            # Preferimos veredicto de 4h, si no hay usamos 1h
            verdict = None
            for h in ("4h", "1h", "24h"):
                match = next((o for o in outcomes if o["horizon"] == h), None)
                if match and match.get("verdict"):
                    verdict = match["verdict"]
                    break
            if verdict is not None:
                rated.append((s, verdict))

        if not rated:
            return {
                "lookback": lookback,
                "win_rate": 0,
                "summary": (
                    f"Hay {len(signals)} señales recientes pero ninguna tiene "
                    "outcome medido todavía."
                ),
            }

        correct = sum(1 for _, v in rated if v == "correct")
        wr = int(round(100 * correct / len(rated)))

        best = max(rated, key=lambda t: 1 if t[1] == "correct" else 0)
        worst = min(rated, key=lambda t: 1 if t[1] == "correct" else 0)
        summary_parts = [
            f"{len(rated)} señales medidas, {correct} correctas.",
            f"Última correcta: {best[0]['pair']} {best[0]['action']}.",
            f"Última incorrecta: {worst[0]['pair']} {worst[0]['action']}.",
        ]
        return {
            "lookback": lookback,
            "win_rate": wr,
            "summary": " ".join(summary_parts),
        }
```

- [ ] **Step 4: Verificar pasa**

```powershell
pytest tests/unit/test_feedback.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```powershell
git add crypto_farmer/learning/feedback.py tests/unit/test_feedback.py
git commit -m "feat(learning): FeedbackBuilder summarizing recent signals for prompt"
```

---

## Bloque 9 — Entrega Telegram

### Tarea 19: `Notifier` protocol + `FakeNotifier`

**Files:**
- Create: `crypto_farmer/delivery/__init__.py`
- Create: `crypto_farmer/delivery/notifier.py`
- Create: `tests/fakes/notifier.py`
- Test: `tests/unit/test_notifier_fake.py`

- [ ] **Step 1: Test del fake**

`tests/unit/test_notifier_fake.py`:
```python
from crypto_farmer.delivery.notifier import DeliverableSignal
from crypto_farmer.signals.models import Signal, SignalAction, TimeHorizon
from tests.fakes.notifier import FakeNotifier


def _ds() -> DeliverableSignal:
    return DeliverableSignal(
        pair="BTC/USDT",
        signal=Signal(
            action=SignalAction.BUY, confidence=72, reasoning="r",
            entry_price_hint=100.0, invalidation_level=95.0,
            time_horizon=TimeHorizon.SHORT, key_factors=["k"],
        ),
        price_at_signal=100.0,
    )


def test_fake_notifier_records_delivered():
    n = FakeNotifier()
    n.deliver([_ds()])
    assert len(n.delivered) == 1
    assert n.delivered[0].pair == "BTC/USDT"
```

- [ ] **Step 2: Verificar fallo**

```powershell
pytest tests/unit/test_notifier_fake.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implementar**

`crypto_farmer/delivery/__init__.py`: vacío.

`crypto_farmer/delivery/notifier.py`:
```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from crypto_farmer.signals.models import CycleStatus, Signal


@dataclass
class DeliverableSignal:
    pair: str
    signal: Signal
    price_at_signal: float


class Notifier(Protocol):
    def deliver(self, signals: list[DeliverableSignal]) -> None: ...
    def deliver_cycle_status(self, *, status: CycleStatus, note: str | None) -> None: ...
```

`tests/fakes/notifier.py`:
```python
from __future__ import annotations

from crypto_farmer.delivery.notifier import DeliverableSignal
from crypto_farmer.signals.models import CycleStatus


class FakeNotifier:
    def __init__(self) -> None:
        self.delivered: list[DeliverableSignal] = []
        self.cycle_notes: list[tuple[CycleStatus, str | None]] = []

    def deliver(self, signals: list[DeliverableSignal]) -> None:
        self.delivered.extend(signals)

    def deliver_cycle_status(self, *, status: CycleStatus, note: str | None) -> None:
        self.cycle_notes.append((status, note))
```

- [ ] **Step 4: Verificar pasa**

```powershell
pytest tests/unit/test_notifier_fake.py -v
```

Expected: 1 passed.

- [ ] **Step 5: Commit**

```powershell
git add crypto_farmer/delivery/ tests/fakes/notifier.py tests/unit/test_notifier_fake.py
git commit -m "feat(delivery): Notifier protocol + DeliverableSignal + FakeNotifier"
```

---

### Tarea 20: `TelegramNotifier` (envío de mensajes)

**Files:**
- Create: `crypto_farmer/delivery/telegram.py`
- Test: `tests/unit/test_telegram_notifier.py`

- [ ] **Step 1: Test (mockeando python-telegram-bot)**

`tests/unit/test_telegram_notifier.py`:
```python
from unittest.mock import AsyncMock, MagicMock

import pytest

from crypto_farmer.delivery.notifier import DeliverableSignal
from crypto_farmer.delivery.telegram import TelegramNotifier, format_signal_message
from crypto_farmer.signals.models import (
    CycleStatus, Signal, SignalAction, TimeHorizon,
)


def _ds(action: SignalAction = SignalAction.BUY, conf: int = 70) -> DeliverableSignal:
    return DeliverableSignal(
        pair="BTC/USDT",
        signal=Signal(
            action=action, confidence=conf, reasoning="RSI sobreventa",
            entry_price_hint=100.0, invalidation_level=95.0,
            time_horizon=TimeHorizon.SHORT, key_factors=["rsi"],
        ),
        price_at_signal=100.0,
    )


def test_format_signal_message_buy():
    text = format_signal_message(_ds(SignalAction.BUY, 75))
    assert "BTC/USDT" in text
    assert "BUY" in text
    assert "75" in text
    assert "RSI sobreventa" in text


def test_telegram_notifier_calls_bot():
    bot = MagicMock()
    bot.send_message = AsyncMock()
    n = TelegramNotifier(bot=bot, chat_id="123")
    n.deliver([_ds()])
    bot.send_message.assert_awaited()
    args, kwargs = bot.send_message.await_args
    assert kwargs["chat_id"] == "123"
    assert "BTC/USDT" in kwargs["text"]


def test_telegram_notifier_deliver_cycle_status_only_when_not_ok():
    bot = MagicMock()
    bot.send_message = AsyncMock()
    n = TelegramNotifier(bot=bot, chat_id="123")
    n.deliver_cycle_status(status=CycleStatus.OK, note=None)
    bot.send_message.assert_not_called()

    n.deliver_cycle_status(status=CycleStatus.DEGRADED, note="news caídas")
    bot.send_message.assert_awaited()
```

- [ ] **Step 2: Verificar fallo**

```powershell
pytest tests/unit/test_telegram_notifier.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implementar**

`crypto_farmer/delivery/telegram.py`:
```python
from __future__ import annotations

import asyncio

from crypto_farmer.delivery.notifier import DeliverableSignal
from crypto_farmer.signals.models import CycleStatus


_ACTION_EMOJI = {"BUY": "🟢", "SELL": "🔴", "HOLD": "⚪"}


def format_signal_message(ds: DeliverableSignal) -> str:
    s = ds.signal
    emoji = _ACTION_EMOJI.get(s.action.value, "")
    lines = [
        f"{emoji} *{s.action.value}* {ds.pair} (conf {s.confidence})",
        f"Precio: {ds.price_at_signal:.4f}",
    ]
    if s.entry_price_hint is not None:
        lines.append(f"Entrada sugerida: {s.entry_price_hint:.4f}")
    if s.invalidation_level is not None:
        lines.append(f"Invalidación: {s.invalidation_level:.4f}")
    lines.append(f"Horizonte: {s.time_horizon.value}")
    lines.append(f"Razón: {s.reasoning}")
    if s.key_factors:
        lines.append("Factores: " + ", ".join(s.key_factors))
    return "\n".join(lines)


class TelegramNotifier:
    def __init__(self, *, bot, chat_id: str) -> None:
        self._bot = bot
        self._chat_id = chat_id

    def deliver(self, signals: list[DeliverableSignal]) -> None:
        for ds in signals:
            text = format_signal_message(ds)
            asyncio.run(
                self._bot.send_message(
                    chat_id=self._chat_id, text=text, parse_mode="Markdown",
                )
            )

    def deliver_cycle_status(self, *, status: CycleStatus, note: str | None) -> None:
        if status == CycleStatus.OK:
            return
        prefix = "⚠️" if status == CycleStatus.DEGRADED else "⛔"
        text = f"{prefix} Ciclo {status.value}"
        if note:
            text += f": {note}"
        asyncio.run(
            self._bot.send_message(chat_id=self._chat_id, text=text)
        )
```

- [ ] **Step 4: Verificar pasa**

```powershell
pytest tests/unit/test_telegram_notifier.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```powershell
git add crypto_farmer/delivery/telegram.py tests/unit/test_telegram_notifier.py
git commit -m "feat(delivery): TelegramNotifier sends formatted signals via python-telegram-bot"
```

---

### Tarea 21: Comandos del bot (`/status`, `/last`, `/stats`, `/pair`, `/pause`, `/resume`, `/health`, `/config`)

**Files:**
- Create: `crypto_farmer/delivery/bot_commands.py`
- Test: `tests/unit/test_bot_commands.py`

- [ ] **Step 1: Test (los handlers son funciones puras que devuelven texto)**

`tests/unit/test_bot_commands.py`:
```python
from datetime import datetime, timezone
from pathlib import Path

from crypto_farmer.delivery.bot_commands import (
    CommandContext, BotCommands, format_status, format_last_signals,
)
from crypto_farmer.signals.models import Signal, SignalAction, TimeHorizon
from crypto_farmer.storage.db import Storage


def _ctx(tmp_path: Path) -> CommandContext:
    storage = Storage(db_path=tmp_path / "t.db")
    return CommandContext(
        storage=storage,
        scheduler_paused_getter=lambda: False,
        scheduler_pauser=lambda: None,
        scheduler_resumer=lambda: None,
        health_checker=lambda: {"ollama": "ok", "binance": "ok", "chromadb": "ok"},
        config_snapshot={"scheduler": {"interval_minutes": 15}, "market": {"pairs": ["BTC/USDT"]}},
    )


def test_status_with_no_cycles(tmp_path: Path):
    ctx = _ctx(tmp_path)
    msg = BotCommands(ctx).status()
    assert "ciclos" in msg.lower()
    assert "0" in msg


def test_last_with_no_signals(tmp_path: Path):
    ctx = _ctx(tmp_path)
    msg = BotCommands(ctx).last()
    assert "sin se" in msg.lower() or "ninguna" in msg.lower()


def test_pause_and_resume(tmp_path: Path):
    state = {"paused": False}
    ctx = _ctx(tmp_path)
    ctx = CommandContext(
        storage=ctx.storage,
        scheduler_paused_getter=lambda: state["paused"],
        scheduler_pauser=lambda: state.update({"paused": True}),
        scheduler_resumer=lambda: state.update({"paused": False}),
        health_checker=ctx.health_checker,
        config_snapshot=ctx.config_snapshot,
    )
    cmd = BotCommands(ctx)
    msg = cmd.pause()
    assert state["paused"]
    assert "pausa" in msg.lower()
    msg = cmd.resume()
    assert not state["paused"]
    assert "reanud" in msg.lower()


def test_health(tmp_path: Path):
    ctx = _ctx(tmp_path)
    msg = BotCommands(ctx).health()
    assert "ollama" in msg.lower()
    assert "ok" in msg.lower()


def test_config_redacts_secrets(tmp_path: Path):
    ctx = _ctx(tmp_path)
    ctx = CommandContext(
        storage=ctx.storage,
        scheduler_paused_getter=ctx.scheduler_paused_getter,
        scheduler_pauser=ctx.scheduler_pauser,
        scheduler_resumer=ctx.scheduler_resumer,
        health_checker=ctx.health_checker,
        config_snapshot={
            "delivery": {"telegram": {"bot_token": "SECRET", "chat_id": "42"}},
            "news_credentials": {"cryptopanic_token": "SECRET2"},
            "scheduler": {"interval_minutes": 15},
        },
    )
    msg = BotCommands(ctx).config()
    assert "SECRET" not in msg
    assert "SECRET2" not in msg
    assert "***" in msg
```

- [ ] **Step 2: Verificar fallo**

```powershell
pytest tests/unit/test_bot_commands.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implementar**

`crypto_farmer/delivery/bot_commands.py`:
```python
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

from crypto_farmer.storage.db import Storage


_SECRET_KEYS = {"bot_token", "cryptopanic_token", "api_key", "api_secret"}


def _redact(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: ("***" if k in _SECRET_KEYS else _redact(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_redact(x) for x in obj]
    return obj


def format_status(cycles: list[dict], paused: bool) -> str:
    if not cycles:
        return "Sin ciclos ejecutados todavía. (0)"
    last = cycles[0]
    ok_count = sum(1 for c in cycles if c.get("status") == "ok")
    lines = [
        f"Estado: {'PAUSADO' if paused else 'ACTIVO'}",
        f"Último ciclo: #{last['id']} {last.get('status')} a las {last.get('finished_at')}",
        f"Ciclos OK en las últimas {len(cycles)} ejecuciones: {ok_count}",
    ]
    return "\n".join(lines)


def format_last_signals(signals: list[dict]) -> str:
    if not signals:
        return "Sin señales emitidas todavía."
    lines = ["Últimas señales:"]
    for s in signals:
        lines.append(
            f"- {s['pair']} {s['action']} conf {s['confidence']} ({s['generated_at']})"
        )
    return "\n".join(lines)


@dataclass
class CommandContext:
    storage: Storage
    scheduler_paused_getter: Callable[[], bool]
    scheduler_pauser: Callable[[], None]
    scheduler_resumer: Callable[[], None]
    health_checker: Callable[[], dict[str, str]]
    config_snapshot: dict


class BotCommands:
    def __init__(self, ctx: CommandContext) -> None:
        self._ctx = ctx

    def status(self) -> str:
        cycles = self._ctx.storage.list_recent_cycles(limit=24)
        return format_status(cycles, paused=self._ctx.scheduler_paused_getter())

    def last(self) -> str:
        sigs = self._ctx.storage.list_recent_signals(limit=5)
        return format_last_signals(sigs)

    def stats(self) -> str:
        sigs = self._ctx.storage.list_recent_signals(limit=100)
        if not sigs:
            return "Sin estadísticas: no hay señales todavía."
        actions: dict[str, int] = {}
        for s in sigs:
            actions[s["action"]] = actions.get(s["action"], 0) + 1
        wins = 0
        rated = 0
        for s in sigs:
            outcomes = self._ctx.storage.list_outcomes_for_signal(s["id"])
            verdict = next(
                (o["verdict"] for o in outcomes if o["horizon"] == "4h"), None
            )
            if verdict is not None:
                rated += 1
                if verdict == "correct":
                    wins += 1
        wr = int(round(100 * wins / rated)) if rated else 0
        lines = [
            f"Señales recientes: {len(sigs)}",
            "Distribución: " + ", ".join(f"{k}={v}" for k, v in actions.items()),
            f"Win rate (4h): {wr}% ({wins}/{rated} medidas)",
        ]
        return "\n".join(lines)

    def pair(self, pair: str) -> str:
        sigs = self._ctx.storage.list_recent_signals(limit=5, pair=pair)
        if not sigs:
            return f"Sin señales recientes para {pair}."
        lines = [f"Últimas señales para {pair}:"]
        for s in sigs:
            outcomes = self._ctx.storage.list_outcomes_for_signal(s["id"])
            outcomes_str = ", ".join(
                f"{o['horizon']}={o.get('return_pct', '?')}%" for o in outcomes
            ) or "(sin outcomes)"
            lines.append(
                f"- {s['action']} conf {s['confidence']} en {s['generated_at']} → {outcomes_str}"
            )
        return "\n".join(lines)

    def pause(self) -> str:
        self._ctx.scheduler_pauser()
        return "Scheduler en pausa. Usa /resume para reanudar."

    def resume(self) -> str:
        self._ctx.scheduler_resumer()
        return "Scheduler reanudado."

    def health(self) -> str:
        checks = self._ctx.health_checker()
        return "Health:\n" + "\n".join(f"- {k}: {v}" for k, v in checks.items())

    def config(self) -> str:
        redacted = _redact(self._ctx.config_snapshot)
        return "```\n" + json.dumps(redacted, indent=2, ensure_ascii=False) + "\n```"
```

- [ ] **Step 4: Verificar pasa**

```powershell
pytest tests/unit/test_bot_commands.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```powershell
git add crypto_farmer/delivery/bot_commands.py tests/unit/test_bot_commands.py
git commit -m "feat(delivery): Telegram bot commands (status/last/stats/pair/pause/resume/health/config)"
```

---

## Bloque 10 — Métricas

### Tarea 22: `Metrics` en memoria

**Files:**
- Create: `crypto_farmer/metrics.py`
- Test: `tests/unit/test_metrics.py`

- [ ] **Step 1: Test**

`tests/unit/test_metrics.py`:
```python
from crypto_farmer.metrics import Metrics


def test_counter_increments():
    m = Metrics()
    m.inc("signals_generated")
    m.inc("signals_generated")
    snap = m.snapshot()
    assert snap["counters"]["signals_generated"] == 2


def test_latency_records_and_aggregates():
    m = Metrics()
    m.record_latency("llm", 100.0)
    m.record_latency("llm", 200.0)
    m.record_latency("llm", 300.0)
    snap = m.snapshot()
    assert snap["latencies"]["llm"]["count"] == 3
    assert snap["latencies"]["llm"]["avg_ms"] == 200.0
    assert snap["latencies"]["llm"]["max_ms"] == 300.0


def test_snapshot_isolated():
    m = Metrics()
    m.inc("x")
    snap = m.snapshot()
    snap["counters"]["x"] = 999  # no afecta al estado interno
    snap2 = m.snapshot()
    assert snap2["counters"]["x"] == 1
```

- [ ] **Step 2: Verificar fallo**

```powershell
pytest tests/unit/test_metrics.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implementar**

`crypto_farmer/metrics.py`:
```python
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from threading import Lock


class Metrics:
    def __init__(self) -> None:
        self._lock = Lock()
        self._counters: dict[str, int] = defaultdict(int)
        self._latencies: dict[str, list[float]] = defaultdict(list)

    def inc(self, name: str, *, by: int = 1) -> None:
        with self._lock:
            self._counters[name] += by

    def record_latency(self, name: str, value_ms: float) -> None:
        with self._lock:
            self._latencies[name].append(value_ms)

    def snapshot(self) -> dict:
        with self._lock:
            lat: dict[str, dict[str, float]] = {}
            for k, vals in self._latencies.items():
                if not vals:
                    continue
                lat[k] = {
                    "count": len(vals),
                    "avg_ms": sum(vals) / len(vals),
                    "max_ms": max(vals),
                }
            return deepcopy({
                "counters": dict(self._counters),
                "latencies": lat,
            })
```

- [ ] **Step 4: Verificar pasa**

```powershell
pytest tests/unit/test_metrics.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```powershell
git add crypto_farmer/metrics.py tests/unit/test_metrics.py
git commit -m "feat(metrics): in-memory thread-safe Metrics with counters and latencies"
```

---

## Bloque 11 — Orquestación: ciclo y scheduler

### Tarea 23: `Cycle` orquestador

**Files:**
- Create: `crypto_farmer/cycle.py`
- Test: `tests/integration/test_cycle.py`

Esta es la pieza central: usa fakes para todo y verifica que un ciclo end-to-end persiste, decide, entrega y programa outcomes.

- [ ] **Step 1: Test de integración con fakes**

`tests/integration/test_cycle.py`:
```python
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from crypto_farmer.analysis.indicators import IndicatorEngine
from crypto_farmer.analysis.prefilter import Prefilter, PrefilterConfig
from crypto_farmer.cycle import Cycle, CycleDeps
from crypto_farmer.delivery.notifier import DeliverableSignal
from crypto_farmer.learning.embeddings import Embeddings
from crypto_farmer.learning.feedback import FeedbackBuilder
from crypto_farmer.learning.outcomes import OutcomeService
from crypto_farmer.llm.client import RawLLMResponse
from crypto_farmer.llm.parser import SignalParser
from crypto_farmer.llm.prompts import PromptBuilder
from crypto_farmer.metrics import Metrics
from crypto_farmer.signals.models import CycleStatus
from crypto_farmer.storage.db import Storage
from tests.fakes.llm import FakeLLMClient
from tests.fakes.market import FakeMarketDataSource
from tests.fakes.memory import InMemoryMemory
from tests.fakes.news import FakeNewsSource
from tests.fakes.notifier import FakeNotifier


class _FakeEmbeddings:
    def embed(self, text: str) -> list[float]:
        # Determinista, vector pequeño dependiente de len + suma chars
        return [float(len(text)), float(sum(ord(c) for c in text[:5]))]


def _ohlcv(n: int = 120, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed=seed)
    base = 100 + np.cumsum(rng.normal(0, 1, n))
    return pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=n, freq="15min", tz="UTC"),
        "open": base,
        "high": base + np.abs(rng.normal(0, 1, n)) + 1,
        "low": base - np.abs(rng.normal(0, 1, n)) - 1,
        "close": base + rng.normal(0, 0.3, n),
        "volume": rng.uniform(50, 150, n),
    })


def _build_cycle(tmp_path: Path, llm_responses=None, news=None):
    storage = Storage(db_path=tmp_path / "cycle.db")
    market = FakeMarketDataSource(ohlcv={
        "BTC/USDT": _ohlcv(seed=1),
        "ETH/USDT": _ohlcv(seed=2),
    }, tickers={
        "BTC/USDT": (100.0, datetime.now(timezone.utc)),
        "ETH/USDT": (2000.0, datetime.now(timezone.utc)),
    })
    news_src = FakeNewsSource(items=news or [])
    indicators = IndicatorEngine()
    prefilter = Prefilter(PrefilterConfig(
        rsi_oversold=80, rsi_overbought=20,  # umbrales agresivos: siempre pasa
        volume_anomaly_factor=10, atr_expansion_factor=10, cooldown_minutes=0,
    ))
    llm_resp = llm_responses or [RawLLMResponse(text='{"action":"BUY","confidence":70,"reasoning":"r","entry_price_hint":null,"invalidation_level":null,"time_horizon":"short","key_factors":[]}')]
    llm_client = FakeLLMClient(responses=llm_resp)
    parser = SignalParser(llm_client=llm_client, max_retries=0)
    builder = PromptBuilder(template_path="config/prompts/analyze_pair.j2")
    memory = InMemoryMemory()
    embeddings: Embeddings = _FakeEmbeddings()
    feedback = FeedbackBuilder(storage=storage)
    outcomes = OutcomeService(
        storage=storage, market=market,
        horizons_hours=[1, 4, 24], memory=memory,
    )
    notifier = FakeNotifier()
    metrics = Metrics()

    deps = CycleDeps(
        market=market, news=news_src,
        indicators=indicators, prefilter=prefilter,
        prompt_builder=builder, parser=parser,
        embeddings=embeddings, memory=memory,
        feedback=feedback, outcomes=outcomes,
        notifier=notifier, storage=storage,
        metrics=metrics,
        pairs=["BTC/USDT", "ETH/USDT"], timeframe="15m", ohlcv_lookback=120,
        min_confidence=60, news_max_age_hours=4, memory_k=5,
        feedback_lookback=20,
    )
    return Cycle(deps), storage, notifier, metrics


def test_cycle_runs_end_to_end(tmp_path: Path):
    cycle, storage, notifier, metrics = _build_cycle(tmp_path)
    result = cycle.run()
    assert result.status == CycleStatus.OK
    assert result.pairs_analyzed == 2
    assert result.pairs_passed_prefilter > 0
    assert result.signals_generated >= 1
    assert len(notifier.delivered) >= 1
    snap = metrics.snapshot()
    assert snap["counters"].get("signals_generated", 0) >= 1


def test_cycle_persists_signals_and_contexts(tmp_path: Path):
    cycle, storage, notifier, _ = _build_cycle(tmp_path)
    cycle.run()
    signals = storage.list_recent_signals(limit=10)
    assert signals
    ctx = storage.get_analysis_context(signals[0]["id"])
    assert ctx is not None
    assert ctx["prompt_rendered"]


def test_cycle_degraded_when_news_fails(tmp_path: Path):
    class _BrokenNews:
        def fetch_recent(self, since):
            from crypto_farmer.data.news import NewsFetchError
            raise NewsFetchError("simulated")

    cycle, storage, notifier, _ = _build_cycle(tmp_path)
    cycle._deps.news = _BrokenNews()  # acceso a deps por composición
    result = cycle.run()
    assert result.status == CycleStatus.DEGRADED
    assert "news" in (result.notes or "").lower()


def test_cycle_skips_low_confidence_signal_delivery(tmp_path: Path):
    low_conf = RawLLMResponse(text='{"action":"BUY","confidence":40,"reasoning":"r","entry_price_hint":null,"invalidation_level":null,"time_horizon":"short","key_factors":[]}')
    cycle, storage, notifier, _ = _build_cycle(tmp_path, llm_responses=[low_conf])
    cycle.run()
    # Persistida pero no entregada
    signals = storage.list_recent_signals(limit=10)
    assert signals
    assert all(s["delivered"] == 0 for s in signals)
    assert notifier.delivered == []


def test_cycle_schedules_outcome_jobs(tmp_path: Path):
    cycle, storage, notifier, _ = _build_cycle(tmp_path)
    cycle.run()
    now = datetime.now(timezone.utc)
    due = storage.list_due_outcome_jobs(now=now + timedelta(hours=25))
    assert len(due) >= 3  # 1h, 4h, 24h por señal
```

- [ ] **Step 2: Verificar fallo**

```powershell
pytest tests/integration/test_cycle.py -v
```

Expected: ImportError sobre `crypto_farmer.cycle`.

- [ ] **Step 3: Implementar**

`crypto_farmer/cycle.py`:
```python
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from crypto_farmer.analysis.indicators import IndicatorEngine
from crypto_farmer.analysis.prefilter import Prefilter
from crypto_farmer.data.market import MarketDataSource, MarketFetchError
from crypto_farmer.data.news import NewsFetchError, NewsSource
from crypto_farmer.delivery.notifier import DeliverableSignal, Notifier
from crypto_farmer.learning.embeddings import Embeddings, EmbeddingError
from crypto_farmer.learning.feedback import FeedbackBuilder
from crypto_farmer.learning.memory import Memory
from crypto_farmer.learning.outcomes import OutcomeService
from crypto_farmer.learning.situation import Situation
from crypto_farmer.llm.client import AnalysisContext
from crypto_farmer.llm.parser import LLMParseError, SignalParser
from crypto_farmer.llm.prompts import PromptBuilder
from crypto_farmer.logging_setup import get_logger
from crypto_farmer.metrics import Metrics
from crypto_farmer.signals.models import (
    CycleStatus, OHLCVSummary, SignalAction,
)
from crypto_farmer.storage.db import Storage


log = get_logger(__name__)


@dataclass
class CycleDeps:
    market: MarketDataSource
    news: NewsSource
    indicators: IndicatorEngine
    prefilter: Prefilter
    prompt_builder: PromptBuilder
    parser: SignalParser
    embeddings: Embeddings
    memory: Memory
    feedback: FeedbackBuilder
    outcomes: OutcomeService
    notifier: Notifier
    storage: Storage
    metrics: Metrics
    pairs: list[str]
    timeframe: str
    ohlcv_lookback: int
    min_confidence: int
    news_max_age_hours: int
    memory_k: int
    feedback_lookback: int


@dataclass
class CycleResult:
    cycle_id: int
    status: CycleStatus
    pairs_analyzed: int
    pairs_passed_prefilter: int
    signals_generated: int
    notes: str | None = None


class Cycle:
    def __init__(self, deps: CycleDeps) -> None:
        self._deps = deps

    def run(self) -> CycleResult:
        d = self._deps
        cycle_id = d.storage.start_cycle()
        d.metrics.inc("cycles_started")
        log.info("cycle_started", extra={"cycle_id": cycle_id})

        notes: list[str] = []
        try:
            ohlcv_by_pair = self._fetch_ohlcv()
        except MarketFetchError as e:
            log.error("cycle_aborted_market_fetch", extra={"cycle_id": cycle_id, "error": str(e)})
            d.storage.finish_cycle(
                cycle_id, status=CycleStatus.FAILED,
                pairs_analyzed=0, pairs_passed_prefilter=0,
                signals_generated=0, notes=f"market_fetch_failed: {e}",
            )
            d.metrics.inc("cycles_failed")
            return CycleResult(
                cycle_id=cycle_id, status=CycleStatus.FAILED,
                pairs_analyzed=0, pairs_passed_prefilter=0,
                signals_generated=0, notes="market_fetch_failed",
            )

        news_items: list = []
        try:
            since = datetime.now(timezone.utc) - timedelta(hours=d.news_max_age_hours)
            news_items = d.news.fetch_recent(since=since)
        except NewsFetchError as e:
            notes.append(f"news_unavailable: {e}")
            log.warning("news_fetch_failed", extra={"cycle_id": cycle_id, "error": str(e)})

        snapshots: dict[str, Any] = {}
        for pair, df in ohlcv_by_pair.items():
            try:
                snapshots[pair] = (df, d.indicators.compute(pair, df))
            except ValueError as e:
                notes.append(f"{pair}_insufficient_data")
                log.warning("indicators_skipped", extra={"pair": pair, "error": str(e)})

        passed: list[tuple[str, Any]] = []
        for pair, (df, snap) in snapshots.items():
            last_row = d.storage.last_signal_for_pair(pair)
            last_sig = None
            if last_row:
                last_sig = (
                    SignalAction(last_row["action"]),
                    datetime.fromisoformat(last_row["generated_at"].replace("Z", "+00:00")),
                )
            decision = d.prefilter.evaluate(
                snap,
                recent_history=df.tail(20).assign(
                    ema_20=df["close"].ewm(span=20).mean().tail(20),
                    ema_50=df["close"].ewm(span=50).mean().tail(20),
                )[["high", "low", "close", "ema_20", "ema_50"]],
                last_signal_for_pair=last_sig,
            )
            if decision.passes:
                passed.append((pair, snap))

        feedback = d.feedback.build(lookback=d.feedback_lookback)
        signals_generated = 0
        for pair, snap in passed:
            df = ohlcv_by_pair[pair]
            relevant_news = [
                {"published_at": n.published_at.isoformat(), "title": n.title}
                for n in news_items if not n.related_pairs or pair in n.related_pairs
            ][:8]
            situation = Situation.from_snapshot(snap)
            memory_hits: list[dict] = []
            try:
                embedding = d.embeddings.embed(situation.as_text())
                hits = d.memory.search(embedding=embedding, k=d.memory_k, pair_filter=pair)
                memory_hits = [
                    {
                        "age": h.metadata.get("timestamp", "?"),
                        "summary": h.text[:120],
                        "action": h.metadata.get("action", "?"),
                        "outcome_4h": h.metadata.get("return_4h", "?"),
                        "outcome_24h": h.metadata.get("return_24h", "?"),
                    }
                    for h in hits
                ]
            except EmbeddingError as e:
                notes.append(f"embeddings_unavailable: {e}")
                log.warning("embeddings_failed", extra={"pair": pair, "error": str(e)})
                embedding = None

            ctx = AnalysisContext(
                pair=pair, timeframe=d.timeframe,
                indicators=snap,
                ohlcv_summary=OHLCVSummary.from_df(df, recent_n=20).model_dump(),
                news=relevant_news, memory_hits=memory_hits,
                recent_feedback=feedback,
            )
            t0 = time.monotonic()
            try:
                parsed = d.parser.analyze_with_retry(ctx)
            except LLMParseError as e:
                log.warning("llm_parse_failed", extra={"pair": pair, "error": str(e)})
                d.metrics.inc("llm_parse_failed")
                continue
            d.metrics.record_latency("llm", (time.monotonic() - t0) * 1000)

            price = ohlcv_by_pair[pair]["close"].iloc[-1]
            delivered = parsed.signal.confidence >= d.min_confidence and parsed.signal.action != SignalAction.HOLD
            sig_id = d.storage.save_signal(
                cycle_id=cycle_id, pair=pair, timeframe=d.timeframe,
                signal=parsed.signal, price_at_signal=float(price),
                delivered=delivered,
            )
            d.storage.save_analysis_context(
                signal_id=sig_id,
                indicators=snap.model_dump(mode="json"),
                news=relevant_news, memory_hits=memory_hits,
                feedback_summary=feedback.get("summary", ""),
                prompt_rendered=d.prompt_builder.render(ctx, now=datetime.now(timezone.utc)),
                raw_llm_response=parsed.raw_text,
            )
            d.metrics.inc("signals_generated")
            signals_generated += 1

            if embedding is not None:
                entry_id = d.memory.add(
                    embedding=embedding, text=situation.as_text(),
                    metadata={
                        "pair": pair,
                        "action": parsed.signal.action.value,
                        "signal_id": str(sig_id),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                )
                log.debug("memory_added", extra={"entry_id": entry_id})

            d.outcomes.schedule_measurements(
                signal_id=sig_id, generated_at=datetime.now(timezone.utc),
            )
            if delivered:
                d.notifier.deliver([DeliverableSignal(
                    pair=pair, signal=parsed.signal, price_at_signal=float(price),
                )])

        status = CycleStatus.OK if not notes else CycleStatus.DEGRADED
        note_str = "; ".join(notes) if notes else None
        d.storage.finish_cycle(
            cycle_id, status=status,
            pairs_analyzed=len(snapshots),
            pairs_passed_prefilter=len(passed),
            signals_generated=signals_generated,
            notes=note_str,
        )
        d.notifier.deliver_cycle_status(status=status, note=note_str)
        log.info("cycle_finished", extra={
            "cycle_id": cycle_id, "status": status.value,
            "signals_generated": signals_generated,
        })
        d.metrics.inc("cycles_ok" if status == CycleStatus.OK else "cycles_degraded")

        return CycleResult(
            cycle_id=cycle_id, status=status,
            pairs_analyzed=len(snapshots),
            pairs_passed_prefilter=len(passed),
            signals_generated=signals_generated, notes=note_str,
        )

    def _fetch_ohlcv(self) -> dict[str, Any]:
        d = self._deps
        out: dict[str, Any] = {}
        for pair in d.pairs:
            out[pair] = d.market.fetch_ohlcv(pair, d.timeframe, d.ohlcv_lookback)
        return out
```

- [ ] **Step 4: Verificar pasa**

```powershell
pytest tests/integration/test_cycle.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```powershell
git add crypto_farmer/cycle.py tests/integration/test_cycle.py
git commit -m "feat(cycle): Cycle orchestrator with full end-to-end flow + integration tests"
```

---

### Tarea 24: `Scheduler` con APScheduler

**Files:**
- Create: `crypto_farmer/scheduler.py`
- Test: `tests/unit/test_scheduler.py`

- [ ] **Step 1: Test**

`tests/unit/test_scheduler.py`:
```python
from unittest.mock import MagicMock

from crypto_farmer.scheduler import CycleScheduler


def test_scheduler_starts_and_runs_job():
    job_fn = MagicMock()
    sched = CycleScheduler(
        interval_minutes=15, timezone="UTC", cycle_callable=job_fn,
        outcomes_callable=MagicMock(),
    )
    sched.start()
    assert sched.is_running()
    jobs = sched._scheduler.get_jobs()
    assert any("cycle" in j.id for j in jobs)
    sched.stop()


def test_scheduler_pause_and_resume():
    sched = CycleScheduler(
        interval_minutes=15, timezone="UTC",
        cycle_callable=lambda: None, outcomes_callable=lambda: None,
    )
    sched.start()
    sched.pause()
    assert sched.is_paused()
    sched.resume()
    assert not sched.is_paused()
    sched.stop()


def test_scheduler_max_instances_is_one():
    sched = CycleScheduler(
        interval_minutes=15, timezone="UTC",
        cycle_callable=lambda: None, outcomes_callable=lambda: None,
    )
    sched.start()
    cycle_job = next(j for j in sched._scheduler.get_jobs() if j.id == "cycle")
    assert cycle_job.max_instances == 1
    assert cycle_job.coalesce is True
    sched.stop()
```

- [ ] **Step 2: Verificar fallo**

```powershell
pytest tests/unit/test_scheduler.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implementar**

`crypto_farmer/scheduler.py`:
```python
from __future__ import annotations

from typing import Callable

from apscheduler.schedulers.background import BackgroundScheduler

from crypto_farmer.logging_setup import get_logger


log = get_logger(__name__)


class CycleScheduler:
    def __init__(
        self, *, interval_minutes: int, timezone: str,
        cycle_callable: Callable[[], None], outcomes_callable: Callable[[], None],
    ) -> None:
        self._scheduler = BackgroundScheduler(timezone=timezone)
        self._scheduler.add_job(
            cycle_callable, trigger="interval",
            minutes=interval_minutes, id="cycle",
            max_instances=1, coalesce=True,
        )
        self._scheduler.add_job(
            outcomes_callable, trigger="interval",
            minutes=max(1, interval_minutes // 3), id="outcomes",
            max_instances=1, coalesce=True,
        )
        self._paused = False

    def start(self) -> None:
        self._scheduler.start()
        log.info("scheduler_started")

    def stop(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
        log.info("scheduler_stopped")

    def pause(self) -> None:
        self._scheduler.pause()
        self._paused = True
        log.info("scheduler_paused")

    def resume(self) -> None:
        self._scheduler.resume()
        self._paused = False
        log.info("scheduler_resumed")

    def is_running(self) -> bool:
        return self._scheduler.running

    def is_paused(self) -> bool:
        return self._paused
```

- [ ] **Step 4: Verificar pasa**

```powershell
pytest tests/unit/test_scheduler.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```powershell
git add crypto_farmer/scheduler.py tests/unit/test_scheduler.py
git commit -m "feat(scheduler): APScheduler wrapper with max_instances=1 and pause/resume"
```

---

## Bloque 12 — Entry point e integración

### Tarea 25: `__main__.py` — ensamblar todo

**Files:**
- Modify: `crypto_farmer/__main__.py`
- Create: `crypto_farmer/app.py`
- Test: `tests/integration/test_app_assembly.py`

- [ ] **Step 1: Test de ensamblado**

`tests/integration/test_app_assembly.py`:
```python
from pathlib import Path

import pytest


def test_app_builds_from_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    monkeypatch.setenv("CRYPTOPANIC_API_TOKEN", "cp")

    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(Path("config/config.example.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    # Apuntar storage a tmp_path para no tocar el repo
    text = cfg_path.read_text(encoding="utf-8")
    text = text.replace("data/crypto_farmer.db", str(tmp_path / "t.db"))
    text = text.replace("data/memory", str(tmp_path / "memory"))
    text = text.replace("data/logs/crypto_farmer.log", str(tmp_path / "log.log"))
    cfg_path.write_text(text, encoding="utf-8")

    from crypto_farmer.app import build_app
    app = build_app(config_path=cfg_path)
    assert app.cycle is not None
    assert app.scheduler is not None
    assert app.bot_commands is not None
```

- [ ] **Step 2: Verificar fallo**

```powershell
pytest tests/integration/test_app_assembly.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implementar `app.py`**

`crypto_farmer/app.py`:
```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import ccxt
import httpx
from telegram import Bot

from crypto_farmer.analysis.indicators import IndicatorEngine
from crypto_farmer.analysis.prefilter import Prefilter, PrefilterConfig
from crypto_farmer.config import Config, load_config
from crypto_farmer.cycle import Cycle, CycleDeps
from crypto_farmer.data.market import CcxtBinanceSource
from crypto_farmer.data.news import CryptoPanicSource
from crypto_farmer.delivery.bot_commands import BotCommands, CommandContext
from crypto_farmer.delivery.telegram import TelegramNotifier
from crypto_farmer.learning.embeddings import OllamaEmbeddings
from crypto_farmer.learning.feedback import FeedbackBuilder
from crypto_farmer.learning.memory import ChromaMemory
from crypto_farmer.learning.outcomes import OutcomeService
from crypto_farmer.llm.client import OllamaClient
from crypto_farmer.llm.parser import SignalParser
from crypto_farmer.llm.prompts import PromptBuilder
from crypto_farmer.logging_setup import configure_logging, get_logger
from crypto_farmer.metrics import Metrics
from crypto_farmer.scheduler import CycleScheduler
from crypto_farmer.storage.db import Storage


log = get_logger(__name__)


@dataclass
class App:
    config: Config
    cycle: Cycle
    scheduler: CycleScheduler
    bot_commands: BotCommands
    storage: Storage
    metrics: Metrics


def _health_checker(*, ollama_base: str, db_path: str, chroma_path: str):
    def check() -> dict[str, str]:
        out: dict[str, str] = {}
        try:
            with httpx.Client(timeout=3.0) as c:
                r = c.get(f"{ollama_base}/api/tags")
                out["ollama"] = "ok" if r.status_code == 200 else f"http_{r.status_code}"
        except Exception as e:
            out["ollama"] = f"down ({e})"
        out["sqlite"] = "ok" if Path(db_path).exists() else "missing"
        out["chromadb"] = "ok" if Path(chroma_path).exists() else "not_initialized"
        # Binance ping puede tardar; mejor un check ligero
        try:
            ex = ccxt.binance({"enableRateLimit": True})
            ex.fetch_status()
            out["binance"] = "ok"
        except Exception as e:
            out["binance"] = f"down ({e})"
        return out
    return check


def build_app(*, config_path: str | Path) -> App:
    cfg = load_config(config_path)
    configure_logging(
        level=cfg.logging.level,
        json_format=cfg.logging.format == "json",
        to_stdout=True,
        log_file=cfg.logging.file,
        retention_days=cfg.logging.retention_days,
    )

    metrics = Metrics()
    storage = Storage(db_path=cfg.storage.sqlite_path)

    market = CcxtBinanceSource(exchange=ccxt.binance({"enableRateLimit": True}))
    news = CryptoPanicSource(token=cfg.news_credentials.cryptopanic_token)

    indicators = IndicatorEngine()
    prefilter = Prefilter(PrefilterConfig(
        rsi_oversold=cfg.prefilter.rsi_oversold,
        rsi_overbought=cfg.prefilter.rsi_overbought,
        volume_anomaly_factor=cfg.prefilter.volume_anomaly_factor,
        atr_expansion_factor=cfg.prefilter.atr_expansion_factor,
        cooldown_minutes=cfg.prefilter.cooldown_minutes,
    ))

    prompt_builder = PromptBuilder(template_path="config/prompts/analyze_pair.j2")
    llm = OllamaClient(
        base_url=cfg.llm.base_url, model=cfg.llm.model,
        prompt_builder=prompt_builder, timeout_seconds=cfg.llm.timeout_seconds,
    )
    parser = SignalParser(llm_client=llm, max_retries=cfg.llm.max_retries)

    embeddings = OllamaEmbeddings(
        base_url=cfg.llm.base_url, model=cfg.llm.embedding_model,
    )
    memory = ChromaMemory(persist_dir=cfg.storage.chroma_path, collection_name="situations")
    feedback = FeedbackBuilder(storage=storage)
    outcomes = OutcomeService(
        storage=storage, market=market,
        horizons_hours=cfg.learning.outcome_horizons_hours, memory=memory,
    )

    bot = Bot(token=cfg.delivery.telegram.bot_token)
    notifier = TelegramNotifier(bot=bot, chat_id=cfg.delivery.telegram.chat_id)

    deps = CycleDeps(
        market=market, news=news,
        indicators=indicators, prefilter=prefilter,
        prompt_builder=prompt_builder, parser=parser,
        embeddings=embeddings, memory=memory,
        feedback=feedback, outcomes=outcomes,
        notifier=notifier, storage=storage, metrics=metrics,
        pairs=cfg.market.pairs, timeframe=cfg.market.timeframe,
        ohlcv_lookback=cfg.market.ohlcv_lookback,
        min_confidence=cfg.delivery.telegram.min_confidence,
        news_max_age_hours=cfg.news.max_age_hours,
        memory_k=cfg.learning.memory_k,
        feedback_lookback=cfg.learning.feedback_lookback,
    )
    cycle = Cycle(deps)

    scheduler = CycleScheduler(
        interval_minutes=cfg.scheduler.interval_minutes,
        timezone=cfg.scheduler.timezone,
        cycle_callable=cycle.run,
        outcomes_callable=lambda: outcomes.run_due_jobs(now=datetime.now(timezone.utc)),
    )

    bot_ctx = CommandContext(
        storage=storage,
        scheduler_paused_getter=scheduler.is_paused,
        scheduler_pauser=scheduler.pause,
        scheduler_resumer=scheduler.resume,
        health_checker=_health_checker(
            ollama_base=cfg.llm.base_url,
            db_path=cfg.storage.sqlite_path,
            chroma_path=cfg.storage.chroma_path,
        ),
        config_snapshot=cfg.model_dump(),
    )
    bot_commands = BotCommands(bot_ctx)

    return App(
        config=cfg, cycle=cycle, scheduler=scheduler,
        bot_commands=bot_commands, storage=storage, metrics=metrics,
    )
```

`crypto_farmer/__main__.py`:
```python
from __future__ import annotations

import argparse
import asyncio
import signal
import sys
from pathlib import Path

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from crypto_farmer.app import build_app
from crypto_farmer.logging_setup import get_logger


log = get_logger(__name__)


def _build_telegram_app(app, token: str) -> Application:
    tg = Application.builder().token(token).build()

    async def _wrap(handler_fn, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            text = handler_fn()
            await ctx.bot.send_message(chat_id=update.effective_chat.id, text=text, parse_mode="Markdown")
        except Exception as e:
            log.exception("bot_command_error")
            await ctx.bot.send_message(chat_id=update.effective_chat.id, text=f"Error: {e}")

    async def _pair(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        pair = " ".join(ctx.args).strip().upper() if ctx.args else ""
        if not pair:
            await ctx.bot.send_message(chat_id=update.effective_chat.id, text="Uso: /pair BTC/USDT")
            return
        text = app.bot_commands.pair(pair)
        await ctx.bot.send_message(chat_id=update.effective_chat.id, text=text, parse_mode="Markdown")

    def _make_handler(fn):
        async def _h(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
            await _wrap(fn, update, ctx)
        return _h

    handlers = {
        "status": app.bot_commands.status,
        "last": app.bot_commands.last,
        "stats": app.bot_commands.stats,
        "pause": app.bot_commands.pause,
        "resume": app.bot_commands.resume,
        "health": app.bot_commands.health,
        "config": app.bot_commands.config,
    }
    for name, fn in handlers.items():
        tg.add_handler(CommandHandler(name, _make_handler(fn)))
    tg.add_handler(CommandHandler("pair", _pair))
    return tg


def main() -> None:
    parser = argparse.ArgumentParser(prog="crypto-farmer")
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--run-once", action="store_true",
                        help="Ejecuta UN ciclo y sale (smoke test).")
    args = parser.parse_args()

    if not Path(args.config).exists():
        print(f"Config no encontrada en {args.config}", file=sys.stderr)
        sys.exit(2)

    app = build_app(config_path=args.config)
    log.info("app_built")

    if args.run_once:
        result = app.cycle.run()
        log.info("run_once_finished", extra={"status": result.status.value})
        return

    app.scheduler.start()

    tg_app = _build_telegram_app(app, token=app.config.delivery.telegram.bot_token)

    stop_event = asyncio.Event()
    def _shutdown(*_):
        log.info("shutdown_signal")
        stop_event.set()
    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    async def _run() -> None:
        await tg_app.initialize()
        await tg_app.start()
        await tg_app.updater.start_polling()
        await stop_event.wait()
        await tg_app.updater.stop()
        await tg_app.stop()
        await tg_app.shutdown()

    try:
        asyncio.run(_run())
    finally:
        app.scheduler.stop()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Verificar pasa el test de ensamblado**

```powershell
pytest tests/integration/test_app_assembly.py -v
```

Expected: 1 passed.

- [ ] **Step 5: Smoke `--run-once` manual (sin tests automáticos)**

Después de tener `config/config.yaml` real y Ollama corriendo con `qwen2.5:7b-instruct-q4_K_M` y `nomic-embed-text` descargados:

```powershell
ollama list  # confirmar modelos presentes
python -m crypto_farmer --config config/config.yaml --run-once
```

Expected: el comando termina, hay logs JSON en stdout, y existe `data/crypto_farmer.db` con al menos un row en `cycles`.

- [ ] **Step 6: Commit**

```powershell
git add crypto_farmer/app.py crypto_farmer/__main__.py tests/integration/test_app_assembly.py
git commit -m "feat(app): wire all components in build_app + entry point with Telegram polling"
```

---

### Tarea 26: README + ejemplos finales

**Files:**
- Modify: `README.md`

- [ ] **Step 1: README completo**

Sobreescribir `README.md`:
```markdown
# crypto-farmer

Servicio local de señales de cripto con IA local (Ollama) + RAG + feedback in-context. Fase 1 según [docs/design/specs/2026-05-12-crypto-farmer-fase1-design.md](docs/design/specs/2026-05-12-crypto-farmer-fase1-design.md).

## Requisitos

- Python 3.11+
- Ollama corriendo localmente con los modelos `qwen2.5:7b-instruct-q4_K_M` y `nomic-embed-text` descargados (`ollama pull <modelo>`).
- Cuenta en Telegram con un bot creado (BotFather) y el chat_id de destino.
- Token de CryptoPanic (free tier disponible).

## Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
copy .env.example .env             # rellenar con tus secretos
copy config\config.example.yaml config\config.yaml
```

Editar `config/config.yaml` para ajustar pares, umbrales, etc. Las claves quedan en `.env`.

## Verificar que arranca (un solo ciclo)

```powershell
python -m crypto_farmer --config config/config.yaml --run-once
```

Debe terminar sin errores y crear `data/crypto_farmer.db` con un row en `cycles`.

## Ejecución 24/7

```powershell
python -m crypto_farmer --config config/config.yaml
```

El proceso queda corriendo. Cada 15 min ejecuta un ciclo. Los outcomes a 1h/4h/24h se miden automáticamente. Las señales con confianza ≥ 60 se envían al chat configurado.

## Comandos del bot

Una vez el proceso esté corriendo, escribe en tu chat de Telegram:

- `/status` — estado del sistema y último ciclo
- `/last` — últimas 5 señales
- `/stats` — win rate y distribución reciente
- `/pair BTC/USDT` — resumen de un par concreto
- `/pause` y `/resume` — controlar el scheduler
- `/health` — comprobar conectividad de subsistemas
- `/config` — config actual (secretos redactados)

## Tests

```powershell
pytest                                    # unit + integration con fakes (rápido)
$env:RUN_LLM_TESTS = "1"; pytest -m llm   # tests opt-in contra Ollama real
```

## Estructura

Ver [docs/design/specs/2026-05-12-crypto-farmer-fase1-design.md](docs/design/specs/2026-05-12-crypto-farmer-fase1-design.md) sección 2.2.

## Backups

Diariamente: copiar `data/crypto_farmer.db` y `data/memory/` a `data/backups/YYYY-MM-DD/`. Ver `scripts/backup.ps1`.

## Aviso

Fase 1 NO ejecuta órdenes reales. Solo genera y entrega señales. No tomes decisiones de inversión basándote únicamente en este sistema; está en validación.
```

- [ ] **Step 2: Commit**

```powershell
git add README.md
git commit -m "docs: complete README with setup, commands and warnings"
```

---

## Bloque 13 — Tests E2E y de Ollama opcionales

### Tarea 27: Marker `llm` opt-in para tests contra Ollama real

**Files:**
- Modify: `pyproject.toml`
- Create: `tests/integration/test_ollama_real.py`

- [ ] **Step 1: Configurar marker en `pyproject.toml`**

Añadir a la sección `[tool.pytest.ini_options]`:
```toml
markers = [
    "llm: tests that require a running Ollama (set RUN_LLM_TESTS=1 to enable)",
]
```

- [ ] **Step 2: Test opt-in**

`tests/integration/test_ollama_real.py`:
```python
import os

import httpx
import pytest

from crypto_farmer.llm.client import AnalysisContext, OllamaClient
from crypto_farmer.llm.parser import SignalParser
from crypto_farmer.llm.prompts import PromptBuilder
from crypto_farmer.signals.models import IndicatorSnapshot, OHLCVCandle, OHLCVSummary


pytestmark = pytest.mark.llm


def _skip_if_disabled():
    if os.environ.get("RUN_LLM_TESTS") != "1":
        pytest.skip("RUN_LLM_TESTS!=1")
    try:
        httpx.get("http://localhost:11434/api/tags", timeout=2.0)
    except Exception:
        pytest.skip("ollama not reachable")


def test_real_ollama_produces_valid_json():
    _skip_if_disabled()
    from datetime import datetime, timezone

    builder = PromptBuilder(template_path="config/prompts/analyze_pair.j2")
    llm = OllamaClient(
        base_url="http://localhost:11434",
        model=os.environ.get("LLM_TEST_MODEL", "qwen2.5:7b-instruct-q4_K_M"),
        prompt_builder=builder, timeout_seconds=60,
    )
    parser = SignalParser(llm_client=llm, max_retries=1)
    ctx = AnalysisContext(
        pair="BTC/USDT", timeframe="15m",
        indicators=IndicatorSnapshot(
            pair="BTC/USDT", timestamp=datetime.now(timezone.utc),
            rsi=28, macd=0.5, macd_signal=0.3, macd_hist=0.2,
            ema_20=100, ema_50=99, bb_upper=110, bb_lower=90,
            atr=5, atr_mean_20=4, volume=120, volume_mean_24h=100,
        ),
        ohlcv_summary=OHLCVSummary(
            recent=[OHLCVCandle(open=100, high=101, low=99, close=100.5, volume=1)],
            highest_high=101, lowest_low=99,
        ).model_dump(),
        news=[], memory_hits=[],
        recent_feedback={"lookback": 20, "win_rate": 0, "summary": "n/a"},
    )
    out = parser.analyze_with_retry(ctx)
    assert out.signal.action.value in {"BUY", "SELL", "HOLD"}
    assert 0 <= out.signal.confidence <= 100
```

- [ ] **Step 3: Verificar que se salta si la variable no está**

```powershell
pytest tests/integration/test_ollama_real.py -v
```

Expected: `1 skipped`.

- [ ] **Step 4: Verificar que pasa con Ollama corriendo (manual, fuera de CI)**

```powershell
$env:RUN_LLM_TESTS = "1"
pytest tests/integration/test_ollama_real.py -v
```

Expected: pasa cuando Ollama responde y el modelo produce JSON válido. Si el modelo produce texto malformado de forma persistente, el test falla → conviene revisar el prompt o usar `LLM_TEST_MODEL` con un modelo más capaz.

- [ ] **Step 5: Commit**

```powershell
git add pyproject.toml tests/integration/test_ollama_real.py
git commit -m "test: opt-in integration test against real Ollama (RUN_LLM_TESTS=1)"
```

---

## Bloque 14 — Operación

### Tarea 28: Script de backup diario

**Files:**
- Create: `scripts/backup.ps1`
- Create: `scripts/restore.ps1`

- [ ] **Step 1: Crear script de backup**

`scripts/backup.ps1`:
```powershell
param(
    [string]$DataDir = "data",
    [string]$BackupDir = "data/backups",
    [int]$RetentionDays = 30
)

$ErrorActionPreference = "Stop"

$timestamp = Get-Date -Format "yyyy-MM-dd"
$target = Join-Path $BackupDir $timestamp
if (-not (Test-Path $target)) {
    New-Item -ItemType Directory -Force -Path $target | Out-Null
}

# Copiar SQLite (con .backup si está en uso sería más robusto, pero sqlite3 .backup
# requiere shell sqlite3; para Fase 1 una copia simple basta porque WAL=off por defecto).
$db = Join-Path $DataDir "crypto_farmer.db"
if (Test-Path $db) {
    Copy-Item -Path $db -Destination (Join-Path $target "crypto_farmer.db") -Force
}

# Copiar carpeta de memoria
$memory = Join-Path $DataDir "memory"
if (Test-Path $memory) {
    Copy-Item -Path $memory -Destination (Join-Path $target "memory") -Recurse -Force
}

# Limpiar backups antiguos
$cutoff = (Get-Date).AddDays(-$RetentionDays)
Get-ChildItem $BackupDir -Directory | Where-Object {
    try {
        [datetime]::ParseExact($_.Name, "yyyy-MM-dd", $null) -lt $cutoff
    } catch { $false }
} | Remove-Item -Recurse -Force

Write-Output "Backup creado en $target"
```

`scripts/restore.ps1`:
```powershell
param(
    [Parameter(Mandatory=$true)][string]$From,
    [string]$DataDir = "data"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $From)) {
    throw "Directorio no encontrado: $From"
}

$db = Join-Path $From "crypto_farmer.db"
$memory = Join-Path $From "memory"

if (Test-Path $db) {
    Copy-Item -Path $db -Destination (Join-Path $DataDir "crypto_farmer.db") -Force
}
if (Test-Path $memory) {
    if (Test-Path (Join-Path $DataDir "memory")) {
        Remove-Item (Join-Path $DataDir "memory") -Recurse -Force
    }
    Copy-Item -Path $memory -Destination (Join-Path $DataDir "memory") -Recurse -Force
}

Write-Output "Restaurado desde $From"
```

- [ ] **Step 2: Ejecutar el backup manualmente para validar**

```powershell
.\scripts\backup.ps1
```

Expected: crea `data/backups/YYYY-MM-DD/` con los archivos (si existen).

- [ ] **Step 3: Documentar en README cómo programar el backup**

Añadir al `README.md` al final de la sección Backups:

```markdown
Programar como tarea diaria (PowerShell, no requiere admin si va en tu usuario):

```powershell
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-File C:\Users\germ1\Proyectos\money-farmer\scripts\backup.ps1"
$trigger = New-ScheduledTaskTrigger -Daily -At 3am
Register-ScheduledTask -TaskName "crypto-farmer-backup" -Action $action -Trigger $trigger
```
```

- [ ] **Step 4: Commit**

```powershell
git add scripts/ README.md
git commit -m "feat(ops): daily backup script + restore script + scheduling docs"
```

---

## Resumen final

Plan de implementación con **29 tareas (T0 a T28)** organizadas en 14 bloques TDD. Cada tarea sigue el mismo patrón:

1. Test que falla.
2. Verificar fallo.
3. Implementación mínima.
4. Verificar pasa.
5. Commit con mensaje semántico.

**Orden de dependencias:**
```
T0 (bootstrap) → T1 (logging) → T2 (config) → T3 (models)
                                                 ↓
T4-5 (market) ← T6 (news) ← T7-8 (analysis) ← T9 (storage)
                                                 ↓
T10-13 (LLM) ← T14-18 (learning)
                  ↓
T19-21 (delivery) ← T22 (metrics)
                  ↓
T23 (Cycle) ← T24 (Scheduler)
                  ↓
T25 (app + entry) → T26 (README) → T27 (ollama tests) → T28 (backup)
```

**Plan de validación post-implementación** (referenciado en el spec §6.4):
1. Smoke con 1 par (días 1-2).
2. Expansión a 5 pares (días 3-4).
3. Universo completo (días 5-7).
4. Outcomes habilitados (días 8-14).
5. Marcha 24/7.






