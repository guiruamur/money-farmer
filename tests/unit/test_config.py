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
