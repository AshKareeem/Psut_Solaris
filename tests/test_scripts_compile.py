"""Every script and module compiles: a doc edit that leaked into code (it happened once, Nov 14) fails here."""
import py_compile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_every_script_and_module_compiles():
    files = sorted(p for d in ("scripts", "horizon") for p in (ROOT / d).glob("*.py"))
    assert len(files) > 30
    for p in files:
        py_compile.compile(str(p), doraise=True)
