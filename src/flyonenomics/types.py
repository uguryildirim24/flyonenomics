"""Shared dataclasses and the Params loader (WP0, WP15 Params v0.2).

Units and array shapes are stated in every public docstring.
Pydantic models forbid unknown fields.
Model parameters come from data/params-v0.1.yaml or data/params-v0.2.yaml;
stream IDs follow section 3.6. DRIVE is the rest-substrate stream (SPEC-P2).
"""

from __future__ import annotations

from dataclasses import field
import json
import os
from pydantic.dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Self

import numpy as np
from numpy.typing import NDArray

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    """Forbid unknown fields. Units: per field. Shapes: per model."""

    model_config = ConfigDict(extra="forbid")


@dataclass(frozen=True, config=ConfigDict(extra="forbid", arbitrary_types_allowed=True))
class ConnectomeFiles:
    """Paths to one connectome build.

    Units: none. Shapes: paths only, no arrays.
    """

    completeness: Path
    connectivity: Path
    version: Literal["630", "783", "male-cns:v1.0"] = "783"


@dataclass(frozen=True, config=ConfigDict(extra="forbid", arbitrary_types_allowed=True))
class LayerFlags:
    """Layer flags of one run (SPEC section 3.4).

    Units: none. Shapes: scalars only.
    """

    background: bool = False
    dopamine_A: bool = True
    transporter_C: bool = True
    dan_fast_synapses: Literal["retain", "disconnect"] = "retain"
    receptor_kinetics_B: Literal[False] = False
    learning_D: Literal[False] = False


@dataclass(frozen=True, config=ConfigDict(extra="forbid", arbitrary_types_allowed=True))
class SeedSpec:
    """Experiment seed derivation inputs (SPEC section 3.6).

    Units: none. Shapes: scalars only. S is the experiment seed,
    s is one entry of seeds, k is the expanded probe index.
    """

    S: int = Field(ge=0, lt=2**32)
    s: int = Field(ge=0, lt=2**32)
    k: int = Field(ge=0)


ENGINE: int = 1
BEHAVIOUR: int = 2
ENCODER: int = 3
JITTER: int = 4
LIVE: int = 5
ANALYSIS: int = 6
DRIVE: int = 7


@dataclass(frozen=True, config=ConfigDict(extra="forbid", arbitrary_types_allowed=True))
class SpikeTable:
    """All-neuron spike record with engine ticks.

    Units: tick is an integer engine tick (not recording-relative).
    Shapes: idx is int32 with shape (n_spikes,), tick is int64
    with shape (n_spikes,).
    """

    idx: NDArray[np.int32]
    tick: NDArray[np.int64]

    def __post_init__(self) -> None:
        _array(self.idx, np.dtype("int32"))
        _array(self.tick, np.dtype("int64"))
        if self.idx.shape != self.tick.shape:
            raise ValueError("idx and tick must have the same shape")


@dataclass(frozen=True, config=ConfigDict(extra="forbid", arbitrary_types_allowed=True))
class ChunkResult:
    """Per-chunk engine output (SPEC section 3.1, SPEC-P2 2.2.4).

    Units: ticks are engine ticks; counts are spikes per neuron.
    Shapes: counts is int32 with shape (n,); hist_1ms is int32
    with shape ((tick1 - tick0) // ticks_per_ms,).
    h_max is the largest h_inh at the chunk end under lif+cbi,
    otherwise None.
    """

    tick0: int
    tick1: int
    counts: NDArray[np.int32]
    hist_1ms: NDArray[np.int32]
    h_max: float | None = None

    def __post_init__(self) -> None:
        _array(self.counts, np.dtype("int32"))
        _array(self.hist_1ms, np.dtype("int32"))
        if self.tick0 < 0 or self.tick1 < self.tick0:
            raise ValueError("chunk ticks must be nonnegative and ordered")
        if self.h_max is not None and (not np.isfinite(self.h_max) or self.h_max < 0):
            raise ValueError("h_max must be None or a finite value >= 0")


@dataclass(frozen=True, config=ConfigDict(extra="forbid", arbitrary_types_allowed=True))
class ComposedParams:
    """Composed per-neuron parameter state (SPEC section 3.4).

    Units: v_th in mV, gain dimensionless.
    Shapes: v_th and gain are float arrays with shape (n,).
    """

    v_th: NDArray[np.floating]
    gain: NDArray[np.floating]
    layers: LayerFlags

    def __post_init__(self) -> None:
        _array(self.v_th)
        _array(self.gain)
        if self.v_th.shape != self.gain.shape:
            raise ValueError("threshold and gain must have the same shape")


@dataclass(frozen=True, config=ConfigDict(extra="forbid", arbitrary_types_allowed=True))
class SettleRecord:
    """Settle outcome of one probe (SPEC section 3.4).

    Units: settle_s in brain seconds; final_da_c in uM;
    final_rates_hz in Hz. Shapes: fixed_point_da_c is float
    with shape (n_comp,); final_da_c has the same shape,
    final_rates_hz has shape (n_recorded_populations,). record_start_tick
    is the integer engine tick at recording start. The optional
    upstream_extended_overlap_idx is int32 (n_overlap,) in engine order.
    """

    converged: bool
    settle_s: float
    fixed_point_da_c: NDArray[np.floating]
    final_da_c: NDArray[np.floating]
    final_rates_hz: NDArray[np.floating]
    record_start_tick: int = Field(ge=0)
    upstream_extended_overlap_idx: NDArray[np.int32] = field(
        default_factory=lambda: np.zeros(0, dtype=np.int32)
    )
    # Schema 1.3 settle rule only (SPEC-P2 section 2.4); None keeps Phase 1 records unchanged.
    unresolved: list[str] | None = None
    da_gap_um: list[float] | None = None

    def __post_init__(self) -> None:
        _array(self.upstream_extended_overlap_idx, np.dtype("int32"))
        if np.any(self.upstream_extended_overlap_idx < 0) or not np.array_equal(
            self.upstream_extended_overlap_idx, np.unique(self.upstream_extended_overlap_idx)
        ):
            raise ValueError("overlap indices must be unique and in engine order")
        for values in (self.fixed_point_da_c, self.final_da_c, self.final_rates_hz):
            _array(values)
        if self.fixed_point_da_c.shape != self.final_da_c.shape or self.settle_s < 0:
            raise ValueError("invalid settle duration or compartment shapes")


@dataclass(eq=False, config=ConfigDict(extra="forbid", arbitrary_types_allowed=True))
class TraceTable:
    """Membrane traces of the trace_idx neurons (SPEC section 3.8).

    Units: tick is an integer engine tick; v_mv is in mV.
    Shapes: idx is int32 with shape (m,); tick is int64 with
    shape (n_time,); v_mv is float64 with shape (m, n_time).
    """

    idx: NDArray[np.int32]
    tick: NDArray[np.int64]
    v_mv: NDArray[np.float64]

    def __post_init__(self) -> None:
        """Check dtypes and shapes. Units: mV and ticks. Shapes: (m,), (T,), (m, T)."""
        if self.idx.dtype != np.dtype("int32"):
            raise ValueError("idx must have dtype int32")
        if self.tick.dtype != np.dtype("int64"):
            raise ValueError("tick must have dtype int64")
        if self.v_mv.dtype != np.dtype("float64"):
            raise ValueError("v_mv must have dtype float64")
        if self.v_mv.shape != (self.idx.shape[0], self.tick.shape[0]):
            raise ValueError("v_mv must have shape (len(idx), len(tick))")


class ProvenanceRecord(StrictModel):
    """One external file entry of data/provenance.json.

    Units: bytes is an integer byte count; sizes of remote
    files are integers where known. Shapes: scalars only.
    """

    item: str
    version: str
    source: str
    license: str
    used_for: str
    status: Literal["fetched", "not fetched"] = "fetched"
    bytes: int | None = Field(default=None, ge=0)
    sha256: str | None = None
    md5: str | None = None
    commit: str | None = None
    url: str | None = None
    date: str | None = None
    note: str | None = None
    path: str | None = None
    inventory: dict[str, int] | None = None

    @model_validator(mode="after")
    def check_status(self) -> Self:
        """Require evidence for fetched bytes or absence. Units: bytes. Shapes: scalars."""
        if self.status == "fetched" and (self.bytes is None or not self.sha256 or not self.path):
            raise ValueError("fetched records require bytes, sha256, and canonical path")
        if self.status == "not fetched" and (not self.url or not self.note):
            raise ValueError("not fetched records require URL and reason")
        return self


class ManifestValidationRef(StrictModel):
    """One validation entry quoted in a run manifest (SPEC section 7).

    Units: none. Shapes: scalars only. binding names the
    validity outcome under the compatibility rule.
    """

    test_id: str
    identity_hash: str
    binding: Literal["valid", "stale"] = "valid"


@dataclass(config=ConfigDict(extra="forbid"))
class Params:
    """Nested parameter store loaded from a params YAML file.

    Units: per key, as stated in the YAML row. Shapes: scalars
    or small lists only; no neuron-length arrays.
    Use get("a.b.c") with dot keys. Values are read from the
    YAML file and never hard-coded here. Default file is
    params-v0.1.yaml; schema 1.3 with background on pins v0.2.
    """

    version: str = "v0.1"
    data: dict[str, Any] = field(default_factory=dict)
    vis_r_max_hz: float = 300.0  # SPEC item 63: class default until the behaviour freeze.

    def get(self, key: str) -> Any:
        """Return the value at dot key (for example "lif.v_th").

        Units: as stated in the YAML row. Shapes: scalar or list.
        """
        if key == "vis.r_max":
            return self.vis_r_max_hz
        node: Any = self.data
        for part in key.split("."):
            if not isinstance(node, dict) or part not in node:
                raise KeyError(f"unknown params key: {key}")
            node = node[part]
        if isinstance(node, dict) and "value" in node:
            return node["value"]
        return node

    def row(self, key: str) -> dict[str, Any]:
        """Return the full row (value, unit, source, range, level).

        Units: as stated in the YAML row. Shapes: scalar or list value.
        """
        node: Any = self.data
        for part in key.split("."):
            if not isinstance(node, dict) or part not in node:
                raise KeyError(f"unknown params key: {key}")
            node = node[part]
        if not isinstance(node, dict) or "value" not in node:
            raise KeyError(f"params key has no value row: {key}")
        return dict(node)


def is_rest_drive(version: str | None) -> bool:
    """Return whether a drive pin is a rest-substrate configuration (SPEC-P2). Units: none."""
    return version not in (None, "v0.1", "dev")


def default_params_path() -> Path:
    """Return the repo-relative path of the Phase 1 params file.

    Units: none. Shapes: a single path.
    """
    return params_path_for_version("v0.1")


def params_path_for_version(version: str) -> Path:
    """Return data/params-<version>.yaml. Units: none. Shapes: one path."""
    return Path(__file__).resolve().parents[2] / "data" / f"params-{version}.yaml"


def load_params(path: str | Path | None = None) -> Params:
    """Load the params YAML into a Params store.

    Units: per key, as stated in the YAML rows. Shapes: scalars
    or small lists only.
    """
    from flyonenomics.io import read_yaml

    resolved: Path = Path(path) if path is not None else default_params_path()
    raw = read_yaml(resolved)
    if not isinstance(raw, dict) or not isinstance(raw.get("version"), str):
        raise ValueError("params must be a mapping with an explicit version")
    version = raw.pop("version")
    if path is None:
        for key, value in isolated_param_overrides().items():
            node: Any = raw
            for part in key.split("."):
                if not isinstance(node, dict) or part not in node:
                    raise ValueError(f"unknown isolated parameter override: {key}")
                node = node[part]
            if not isinstance(node, dict) or not isinstance(node.get("value"), (int, float)):
                raise ValueError(f"isolated override needs a numeric parameter row: {key}")
            bounds = str(node.get("range", "")).split(" to ")
            if len(bounds) != 2 or not float(bounds[0]) <= value <= float(bounds[1]):
                raise ValueError(f"isolated override outside declared range: {key}")
            node["value"] = value
    _validate_rows(raw)
    return Params(version=version, data=raw)


def isolated_param_overrides() -> dict[str, float]:
    """Read one process-local sensitivity setting; source units per parameter key."""
    encoded = os.environ.get("FLYONENOMICS_PARAM_OVERRIDES_JSON")
    if not encoded:
        return {}
    document = json.loads(encoded)
    if not isinstance(document, dict) or not document:
        raise ValueError("isolated parameter overrides must be a nonempty mapping")
    result: dict[str, float] = {}
    for key, value in document.items():
        if not isinstance(key, str) or isinstance(value, bool) or not isinstance(value, (int, float)) or not np.isfinite(value):
            raise ValueError("isolated parameter overrides require finite numeric keys and values")
        result[key] = float(value)
    return result


def _array(values: np.ndarray, dtype: np.dtype | None = None) -> None:
    if values.ndim != 1:
        raise ValueError("arrays must be one-dimensional")
    if dtype is not None and values.dtype != dtype:
        raise ValueError(f"array must have dtype {dtype}")
    if dtype is None and not np.issubdtype(values.dtype, np.floating):
        raise ValueError("array must have floating dtype")


def _validate_rows(node: dict[str, Any]) -> None:
    for name, child in node.items():
        if not isinstance(child, dict) or not child:
            raise ValueError(f"invalid params row: {name}")
        if "value" in child:
            if set(child) != {"value", "unit", "source", "range", "level"}:
                raise ValueError(f"incomplete or unknown params metadata: {name}")
        else:
            _validate_rows(child)
