"""Shared configuration helpers for pipeline scripts.

Configuration resolution order for `get_config*` helpers:
1) Explicit environment variable (when provided)
2) Value from config YAML (`config/config.yaml`)
3) Fallback default
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Optional

try:
    import yaml
except Exception:  # pragma: no cover - graceful fallback if PyYAML is unavailable.
    yaml = None


_CONFIG_CACHE: dict[str, Any] | None = None
_ENV_REF_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _default_config_path() -> Path:
    # src/utils/config.py -> repo root /config/config.yaml
    return Path(__file__).resolve().parents[2] / "config" / "config.yaml"


def _resolve_env_refs(value: Any) -> Any:
    if isinstance(value, str):
        return _ENV_REF_RE.sub(lambda m: os.getenv(m.group(1), ""), value)
    if isinstance(value, dict):
        return {k: _resolve_env_refs(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_env_refs(v) for v in value]
    return value


def load_config(path: str | None = None) -> dict[str, Any]:
    """Load and cache YAML config from disk."""
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None:
        return _CONFIG_CACHE

    if yaml is None:
        _CONFIG_CACHE = {}
        return _CONFIG_CACHE

    cfg_path = Path(path) if path else _default_config_path()
    if not cfg_path.exists():
        _CONFIG_CACHE = {}
        return _CONFIG_CACHE

    with cfg_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    _CONFIG_CACHE = _resolve_env_refs(data)
    return _CONFIG_CACHE


def _lookup_path(config: dict[str, Any], key_path: str) -> Any:
    cur: Any = config
    for part in key_path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def get_config(key_path: str, default: Any = None, env_var: str | None = None) -> Any:
    """Resolve a config value from env first, then YAML, then default."""
    if env_var and env_var in os.environ:
        return os.environ[env_var]

    data = load_config()
    value = _lookup_path(data, key_path)
    return default if value is None else value


def get_config_int(key_path: str, default: int, env_var: str | None = None) -> int:
    value = get_config(key_path, default=default, env_var=env_var)
    try:
        return int(value)
    except Exception:
        return default


def get_config_float(key_path: str, default: float, env_var: str | None = None) -> float:
    value = get_config(key_path, default=default, env_var=env_var)
    try:
        return float(value)
    except Exception:
        return default


def get_config_bool(key_path: str, default: bool = False, env_var: str | None = None) -> bool:
    value = get_config(key_path, default=default, env_var=env_var)
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def get_config_str(key_path: str, default: str = "", env_var: str | None = None) -> str:
    value = get_config(key_path, default=default, env_var=env_var)
    if value is None:
        return default
    return str(value)


def get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    """Return environment variable value or default when unset."""
    return os.environ.get(name, default)


def get_bool(name: str, default: bool = False) -> bool:
    """Parse common boolean env values."""
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
