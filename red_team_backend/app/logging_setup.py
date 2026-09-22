"""Central logging configuration — rotating file + console for the worker.

Called once on app import so every ``logging.getLogger(__name__)`` in the
package lands in ``${LOG_DIR}/<service>.app.log`` (rotated) as well as stdout,
which supervisord/docker already capture.
"""
from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

_configured = False

# Third-party loggers that are far too chatty at INFO for our per-job logs.
_NOISY_LOGGERS = (
    "httpx",
    "httpcore",
    "urllib3",
    "transformers",
    "openai",
    "asyncio",
)


def configure_logging(service_name: str = "worker") -> None:
    """Install a rotating file handler + stream handler on the root logger.

    Idempotent: safe to call from multiple entry points. Honors ``LOG_LEVEL``,
    ``LOG_DIR``, ``LOG_MAX_BYTES`` and ``LOG_BACKUP_COUNT`` from the environment.
    """
    global _configured
    if _configured:
        return

    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(level)

    stream = logging.StreamHandler()
    stream.setFormatter(fmt)
    root.addHandler(stream)

    log_dir = Path(os.getenv("LOG_DIR", "run"))
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        max_bytes = int(os.getenv("LOG_MAX_BYTES", str(10 * 1024 * 1024)))
        backups = int(os.getenv("LOG_BACKUP_COUNT", "5"))
        file_handler = RotatingFileHandler(
            log_dir / f"{service_name}.app.log",
            maxBytes=max_bytes,
            backupCount=backups,
            encoding="utf-8",
        )
        file_handler.setFormatter(fmt)
        root.addHandler(file_handler)
    except OSError as exc:  # pragma: no cover - fall back to stream only
        root.warning("file logging disabled (%s); logging to stream only", exc)

    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)

    _configured = True
