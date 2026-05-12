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
    "processName", "process", "message", "asctime", "taskName",
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
        # File handler always emits JSON regardless of json_format,
        # so on-disk logs remain machine-parseable for post-mortem.
        fh.setFormatter(JsonFormatter())
        root.addHandler(fh)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
