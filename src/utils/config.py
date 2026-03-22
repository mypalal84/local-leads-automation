"""Shared environment config helpers for pipeline scripts."""

from __future__ import annotations

import os
from typing import Optional


def get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    """Return environment variable value or default when unset."""
    return os.environ.get(name, default)


def get_bool(name: str, default: bool = False) -> bool:
    """Parse common boolean env values."""
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
