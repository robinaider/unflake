"""Entry point. Works as `python -m unflake` AND as `python path/to/__main__.py`
(the latter is how the npx wrapper invokes the vendored core)."""

try:
    from .cli import main
except ImportError:  # pragma: no cover - path-invoked fallback
    import os
    import sys

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from unflake.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
