#!/usr/bin/env python3
"""Vendor the Python core into npm/unflake_core/ + pin package.json version.

Single source of truth: src/unflake/__init__.py (__version__).
Runs automatically on `npm pack`/`npm publish` (prepack) and in tests.
Idempotent; output dir is gitignored (generated, never committed).
"""

import json
import re
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SRC = ROOT / "src" / "unflake"
DEST = HERE / "unflake_core" / "unflake"
PKG = HERE / "package.json"


def read_version() -> str:
    text = (SRC / "__init__.py").read_text(encoding="utf-8")
    m = re.search(r'__version__\s*=\s*"([^"]+)"', text)
    if not m:
        raise SystemExit("sync: __version__ not found in src/unflake/__init__.py")
    return m.group(1)


def main() -> int:
    version = read_version()
    if DEST.exists():
        shutil.rmtree(DEST)
    shutil.copytree(SRC, DEST, ignore=shutil.ignore_patterns("__pycache__"))
    (HERE / "unflake_core" / "VERSION").write_text(version + "\n", encoding="utf-8")
    data = json.loads(PKG.read_text(encoding="utf-8"))
    if data.get("version") != version:
        data["version"] = version
        PKG.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        print(f"sync: package.json version -> {version}")
    n = sum(1 for _ in DEST.rglob("*.py"))
    print(f"sync: vendored {n} core files, version {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
