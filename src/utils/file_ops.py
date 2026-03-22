"""Common file operations shared by scripts."""

from __future__ import annotations

from pathlib import Path


def ensure_dir(path: str | Path) -> Path:
    """Create directory path if missing and return as Path."""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p
