"""FlyOnenomics Dashboard package (WP8)."""
from __future__ import annotations

from typing import Any

__all__ = [
    "CODEX_BASE_URL",
    "DA_REF",
    "DEFAULT_PORT",
    "LIVE_FORWARD_HZ",
    "LIVE_POLL_INTERVAL_S",
    "PAGE_SIZE",
    "SPIKE_CAP",
    "app",
    "create_app",
    "main",
]


def __getattr__(name: str) -> Any:
    """Lazy import dashboard attributes on demand.

    Units: none. Shapes: requested object.
    """
    import flyonenomics.dashboard.app as _app

    if hasattr(_app, name):
        return getattr(_app, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
