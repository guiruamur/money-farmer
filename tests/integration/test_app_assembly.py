from pathlib import Path

import pytest


def test_app_builds_from_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    monkeypatch.setenv("CRYPTOPANIC_API_TOKEN", "cp")

    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(Path("config/config.example.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    text = cfg_path.read_text(encoding="utf-8")
    # Use forward slashes to avoid YAML escape-sequence issues on Windows
    text = text.replace("data/crypto_farmer.db", (tmp_path / "t.db").as_posix())
    text = text.replace("data/memory", (tmp_path / "memory").as_posix())
    text = text.replace("data/logs/crypto_farmer.log", (tmp_path / "log.log").as_posix())
    cfg_path.write_text(text, encoding="utf-8")

    from crypto_farmer.app import build_app
    app = build_app(config_path=cfg_path)
    assert app.cycle is not None
    assert app.scheduler is not None
    assert app.bot_commands is not None
    assert app.notifier is not None
