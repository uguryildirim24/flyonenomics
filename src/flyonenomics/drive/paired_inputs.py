"""Opt-in common-random-number plumbing for the male history study (d-0025).

The ordinary BrianEngine/FlyWire input path is deliberately unchanged. Sampling
matches Brian2's clocked Poisson convention: Bernoulli(rate * dt) per TuBu cell
and tick; background uses the same Brian2 BinomialFunction as PoissonInput.
"""
from __future__ import annotations

from typing import Any
import numpy as np

VERSION = "segment-keyed-tubu-draw-all-background-v1"
SEGMENTS = {"settle": 0, "prefix": 1, "gap": 2, "test": 3, "response": 4}
STIMULI = {"off": 0, "A": 1, "B": 2, "AB": 3,
           "-150.0": 4, "-50.0": 5, "50.0": 6, "150.0": 7}


def segment_events(master: int, seed: int, segment: str, stimulus: str,
                   rates_hz: np.ndarray, ticks: int, dt_ms: float) -> tuple[np.ndarray, np.ndarray]:
    """Return relative ticks and local source positions, sorted by tick/cell.

    Only seed, segment and stimulus vary the stream key. No condition, history,
    process, wall time or global NumPy/Brian RNG state enters it. The fixed
    namespace/master and ID maps are versioned above. Blocks bound working RAM
    without changing the flattened uniform sequence or the per-tick law.
    """
    probability = np.asarray(rates_hz, dtype=np.float64) * (dt_ms / 1000)
    if probability.ndim != 1 or not np.all(np.isfinite(probability)) or np.any((probability < 0) | (probability > 1)):
        raise ValueError("clocked Poisson probabilities must lie in [0,1]")
    if ticks < 0 or dt_ms <= 0:
        raise ValueError("invalid event duration or time step")
    rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence(
        master, spawn_key=(25, int(seed), SEGMENTS[segment], STIMULI[stimulus]))))
    times, cells = [], []
    for start in range(0, ticks, 4096):
        hit = rng.random((min(4096, ticks-start), len(probability))) < probability
        tick, position = np.nonzero(hit)
        times.append(tick.astype(np.int64) + start)
        cells.append(position.astype(np.int32))
    return (np.concatenate(times) if times else np.empty(0, np.int64),
            np.concatenate(cells) if cells else np.empty(0, np.int32))


def trial_segments(stage: str, protocol: Any, timing: dict[str, Any]) -> list[tuple[str, str, float]]:
    if stage in ("5a", "probe"):
        return [("settle", "off", timing["settle_s"]), ("response", str(protocol), timing["5a_s"])]
    return [("settle", "off", timing["settle_s"]), ("prefix", protocol[0], timing["prefix_s"]),
            ("gap", "off", timing["gap_s"]), ("test", protocol[1], timing["test_s"])]


def trial_events(master: int, seed: int, stage: str, protocol: Any,
                 patterns: dict[str, np.ndarray], timing: dict[str, Any],
                 dt_ms: float) -> tuple[np.ndarray, np.ndarray]:
    times, cells, offset = [], [], 0
    for segment, stimulus, seconds in trial_segments(stage, protocol, timing):
        steps = seconds * 1000 / dt_ms
        count = round(steps)
        if not np.isclose(steps, count, rtol=0, atol=1e-9):
            raise ValueError("trial segment must have an integer number of engine ticks")
        tick, position = segment_events(master, seed, segment, stimulus, patterns[stimulus], count, dt_ms)
        times.append(tick + offset)
        cells.append(position)
        offset += count
    return np.concatenate(times), np.concatenate(cells)


def state_independent_background(target: Any, n: int, rate_hz: float) -> Any:
    """Same sampler/weight/gating/schedule as PoissonInput, but draw first.

    A persistent, ungated dimensionless scratch variable forces code generation
    to sample every target before the existing conditional write to `g`.
    Refractory neurons discard their sample, exactly as before. No equations,
    engine defaults, FlyWire code or reference fixtures are modified.
    """
    import brian2 as b
    from brian2.input.binomial import BinomialFunction

    if "study_bg_draw" in target.variables:
        raise ValueError("study background already installed")
    target.variables.add_array("study_bg_draw", size=len(target), dtype=np.float64)
    background = b.PoissonInput(target=target, target_var="g", N=n,
                               rate=rate_hz*b.Hz, weight="w_bg_i", when="synapses", order=0)
    samplers = [value for value in background.variables.values() if isinstance(value, BinomialFunction)]
    if len(samplers) != 1:
        raise ValueError("unexpected Brian2 PoissonInput sampler")
    # Keep the exact BinomialFunction registered by PoissonInput, its dt check,
    # scheduling slot/order, and g's existing refractory conditional_write.
    background.abstract_code = f"study_bg_draw = {samplers[0].name}()\ng += study_bg_draw * w_bg_i"
    return background
