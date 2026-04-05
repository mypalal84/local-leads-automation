import os
import pathlib
import sys

import pytest


SRC_DIR = pathlib.Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

for subdir in ("discovery", "enrichment", "outreach", "utils", "pipeline"):
    path = SRC_DIR / subdir
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


@pytest.fixture(autouse=True)
def allow_weekend_send(monkeypatch):
    monkeypatch.setenv("ALLOW_WEEKEND_SEND", "1")
