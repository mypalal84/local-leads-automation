"""Minimal logger factory used by utility scripts."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any


def get_logger(name: str) -> logging.Logger:
    """Return a configured stream logger by name."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("[%(asctime)s] %(levelname)s %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


def emit_structured_event(event: str, enabled: bool = True, **fields: Any) -> str:
    """Emit a JSON-lines log event to stdout and return the serialized line."""
    payload = {
        "time": datetime.now(timezone.utc).isoformat(),
        "event": event,
    }
    payload.update(fields)
    line = json.dumps(payload, sort_keys=True)
    if enabled:
        print(line)
    return line
