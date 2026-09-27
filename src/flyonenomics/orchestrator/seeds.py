"""Arm-independent component streams, exactly SPEC section 3.6."""
import numpy as np
from flyonenomics.types import ENGINE, BEHAVIOUR, ENCODER, JITTER, LIVE, ANALYSIS, SeedSpec

__all__ = ["stream", "brian_seed", "ENGINE", "BEHAVIOUR", "ENCODER", "JITTER", "LIVE", "ANALYSIS"]


def stream(S: int, s: int, k: int, component: int) -> np.random.Generator:
    """Derive one component RNG; units none, scalar uint32 seeds and probe index."""
    SeedSpec(S=S, s=s, k=k)
    if component not in (ENGINE, BEHAVIOUR, ENCODER, JITTER, LIVE, ANALYSIS):
        raise ValueError("unknown component id")
    return np.random.default_rng(np.random.SeedSequence(S, spawn_key=(s, k, component)))


def brian_seed(S: int, s: int, k: int) -> int:
    """Derive the Brian2 uint32 seed; units none, scalar seeds and probe index."""
    SeedSpec(S=S, s=s, k=k)
    return int(np.random.SeedSequence(S, spawn_key=(s, k, ENGINE)).generate_state(1, dtype=np.uint32)[0])
