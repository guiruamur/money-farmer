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
