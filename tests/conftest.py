import pathlib
import sys


SRC_DIR = pathlib.Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

for subdir in ("discovery", "enrichment", "outreach", "utils", "pipeline"):
    path = SRC_DIR / subdir
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
