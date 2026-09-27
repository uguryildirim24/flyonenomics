"""Results store and SQLite index public entry points."""
from flyonenomics.store.results import ResultsStore

__all__ = ["ResultsStore", "RunIndex", "rebuild", "validate_run"]


def __getattr__(name: str):
    """Load the index module only when a caller asks for it. Units: none."""
    if name in {"RunIndex", "rebuild", "validate_run"}:
        from flyonenomics.store.index import RunIndex, rebuild, validate_run
        return {"RunIndex": RunIndex, "rebuild": rebuild, "validate_run": validate_run}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

