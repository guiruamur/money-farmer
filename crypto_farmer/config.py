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
