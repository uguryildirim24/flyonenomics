"""Drive `mechanisms` section: load, masks, engine_model_of, substrate_id_for.

SPEC-P2 2.2.4 and 2.5. File reads go through flyonenomics.io.
"""

from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from flyonenomics.io import hash_file, read_yaml
from flyonenomics.types import load_params

MappingOrNone = dict[str, Any] | None

MECH_BLOCKS = ("adaptation", "depression", "conductance_inhibition")
ADAPTATION_KEYS = frozenset({"b_mv", "tau_ms", "scope", "mask_sha256"})
DEPRESSION_KEYS = frozenset({"U", "tau_ms", "scope", "mask_sha256"})
CBI_KEYS = frozenset({"E_inh_mv", "scope"})
ADAPTATION_SCOPES = frozenset({"non_sensory"})
DEPRESSION_SCOPES = frozenset({"non_sensory_excitatory", "non_sensory"})
CBI_SCOPES = frozenset({"all"})
MODEL_OF_BLOCK = {
    "adaptation": "lif+sfa",
    "depression": "lif+std",
    "conductance_inhibition": "lif+cbi",
}
TAG_OF_MODEL = {"lif+sfa": "sfa", "lif+std": "std", "lif+cbi": "cbi"}
BLOCK_OF_MODEL = {
    "lif+sfa": "adaptation",
    "lif+std": "depression",
    "lif+cbi": "conductance_inhibition",
}


def _finite(name: str, value: Any) -> float:
    """Require a finite numeric value. Units: per caller. Shapes: scalar."""
    if isinstance(value, bool) or value is None:
        raise ValueError(f"mechanism {name} must be a finite number")
    number = float(value)
    if not np.isfinite(number):
        raise ValueError(f"mechanism {name} must be a finite number")
    return number


def engine_model_of(section: MappingOrNone) -> str:
    """Name the variant from a mechanisms section or null (SPEC-P2 2.2.4).

    Units: none. Shapes: one of lif, lif+sfa, lif+std, lif+cbi.
    """
    if section is None:
        return "lif"
    if not isinstance(section, dict):
        raise ValueError("mechanisms section must be a mapping or null")
    unknown = [key for key in section if key not in MECH_BLOCKS]
    if unknown:
        raise ValueError(f"unknown mechanisms key: {unknown[0]}")
    on = [key for key in MECH_BLOCKS if section.get(key) is not None]
    if len(on) > 1:
        raise ValueError("at most one mechanism block may be non-null")
    if not on:
        return "lif"
    return MODEL_OF_BLOCK[on[0]]


def mask_sha256(mask: NDArray[np.uint8]) -> str:
    """SHA-256 of a uint8 scope mask's bytes. Units: none. Shapes: one hex."""
    array = np.asarray(mask, dtype=np.uint8)
    if array.ndim != 1:
        raise ValueError("scope mask must be one-dimensional")
    return hashlib.sha256(np.ascontiguousarray(array).tobytes()).hexdigest()


def scope_mask(
    scope: str,
    *,
    super_class: NDArray[np.str_] | NDArray[np.object_],
    s_cur: NDArray[np.floating] | None = None,
) -> NDArray[np.uint8]:
    """Build a uint8 in-scope mask in engine / root_ids order.

    Units: none. Shapes: (n,) uint8. Sensory is super_class sensory.
    """
    groups = np.asarray(super_class, dtype=str)
    n = int(groups.shape[0])
    sensory = groups == "sensory"
    if scope == "non_sensory":
        return np.where(~sensory, np.uint8(1), np.uint8(0))
    if scope == "non_sensory_excitatory":
        if s_cur is None:
            raise ValueError("non_sensory_excitatory needs s_cur")
        signs = np.asarray(s_cur, dtype=np.float64)
        if signs.shape != (n,):
            raise ValueError("s_cur must match super_class")
        return np.where((~sensory) & (signs == 1.0), np.uint8(1), np.uint8(0))
    if scope == "all":
        raise ValueError("scope all has no mask")
    raise ValueError(f"scope outside its list: {scope}")


def neuron_s_cur(classes: NDArray[np.str_], signs: NDArray[np.floating]) -> NDArray[np.float64]:
    """Per-neuron s_cur (SPEC-P2 2.2.1). Units: dimensionless ±1. Shapes: (n,)."""
    from flyonenomics.substrate.scales import EXCITATORY_CLASSES, INHIBITORY_CLASSES

    labels = np.asarray(classes, dtype=str)
    connection = np.asarray(signs, dtype=np.float64)
    if labels.shape != connection.shape:
        raise ValueError("classes and signs must match")
    s_cur = np.empty(labels.shape[0], dtype=np.float64)
    s_cur[np.isin(labels, tuple(INHIBITORY_CLASSES))] = -1.0
    s_cur[np.isin(labels, tuple(EXCITATORY_CLASSES))] = 1.0
    unknown = labels == "unk"
    s_cur[unknown] = np.sign(connection[unknown])
    return s_cur


@lru_cache(maxsize=1)
def _engine_scope_inputs() -> tuple[NDArray[np.str_], NDArray[np.float64], int]:
    """super_class, s_cur, n in v783 engine order. Units: none. Shapes: (n,)."""
    from flyonenomics.substrate.transmitters import (
        annotations_in_engine,
        classify_engine,
        engine_signs,
        load_connection_columns,
        presynaptic_signs,
    )

    classes, frame, _census = classify_engine()
    super_class = frame["super_class"].fillna("").to_numpy(dtype=str)
    table = load_connection_columns(("Presynaptic_ID", "Excitatory"))
    unique, _mixed = presynaptic_signs(
        table.column("Presynaptic_ID").to_numpy(),
        table.column("Excitatory").to_numpy(),
    )
    _frame, engine_order = annotations_in_engine()
    signs = engine_signs(engine_order, unique, frame["top_nt"].to_numpy())
    return super_class, neuron_s_cur(classes, signs), int(super_class.shape[0])


def real_scope_mask(scope: str) -> NDArray[np.uint8]:
    """Scope mask on the real v783 annotations. Units: none. Shapes: (engine.n,)."""
    super_class, s_cur, _n = _engine_scope_inputs()
    return scope_mask(scope, super_class=super_class, s_cur=s_cur)


def _v0() -> float:
    """lif.v_0 in mV from the pinned params file."""
    return float(load_params().get("lif.v_0"))


def _adaptation_tau_floor_ms() -> float:
    """2 × max(lif.t_mbr, lif.tau) in ms from the pinned params (SPEC-P2 8.2)."""
    params = load_params()
    return 2.0 * max(float(params.get("lif.t_mbr")), float(params.get("lif.tau")))


def parse_mechanisms_section(section: Any) -> dict[str, Any] | None:
    """Validate a mechanisms section and return it, or None when absent.

    Units: b_mv mV, tau_ms ms, E_inh_mv mV, U dimensionless.
    """
    if section is None:
        return None
    if not isinstance(section, dict):
        raise ValueError("mechanisms section must be a mapping or null")
    record = dict(section)
    unknown = [key for key in record if key not in MECH_BLOCKS]
    if unknown:
        raise ValueError(f"unknown mechanisms key: {unknown[0]}")
    on = [key for key in MECH_BLOCKS if record.get(key) is not None]
    if len(on) > 1:
        raise ValueError("at most one mechanism block may be non-null")
    if not on:
        return {key: None for key in MECH_BLOCKS}
    name = on[0]
    block = record[name]
    if not isinstance(block, dict):
        raise ValueError(f"{name} must be a mapping or null")
    if name == "adaptation":
        extra = [key for key in block if key not in ADAPTATION_KEYS]
        if extra:
            raise ValueError(f"unknown key in adaptation: {extra[0]}")
        needed = ADAPTATION_KEYS - set(block)
        if needed:
            raise ValueError(f"adaptation misses {sorted(needed)[0]}")
        b_mv = _finite("adaptation.b_mv", block["b_mv"])
        tau_ms = _finite("adaptation.tau_ms", block["tau_ms"])
        if b_mv == 0:
            raise ValueError("adaptation at zero strength; write the block as null")
        floor = _adaptation_tau_floor_ms()
        if tau_ms < floor:
            raise ValueError(f"adaptation tau_ms must be at least {floor:g}")
        if block.get("scope") not in ADAPTATION_SCOPES:
            raise ValueError("adaptation scope must be non_sensory")
        if not isinstance(block.get("mask_sha256"), str) or not block["mask_sha256"]:
            raise ValueError("adaptation mask_sha256 is required")
    elif name == "depression":
        extra = [key for key in block if key not in DEPRESSION_KEYS]
        if extra:
            raise ValueError(f"unknown key in depression: {extra[0]}")
        needed = DEPRESSION_KEYS - set(block)
        if needed:
            raise ValueError(f"depression misses {sorted(needed)[0]}")
        u_val = _finite("depression.U", block["U"])
        tau_ms = _finite("depression.tau_ms", block["tau_ms"])
        if u_val == 0:
            raise ValueError("depression at zero strength; write the block as null")
        if not 0 < u_val <= 1:
            raise ValueError("depression U must be in (0, 1]")
        if tau_ms < 10:
            raise ValueError("depression tau_ms must be at least 10")
        if block.get("scope") not in DEPRESSION_SCOPES:
            raise ValueError("depression scope must be non_sensory_excitatory or non_sensory")
        if not isinstance(block.get("mask_sha256"), str) or not block["mask_sha256"]:
            raise ValueError("depression mask_sha256 is required")
    else:
        extra = [key for key in block if key not in CBI_KEYS]
        if extra:
            raise ValueError(f"unknown key in conductance_inhibition: {extra[0]}")
        needed = CBI_KEYS - set(block)
        if needed:
            raise ValueError(f"conductance_inhibition misses {sorted(needed)[0]}")
        e_inh = _finite("conductance_inhibition.E_inh_mv", block["E_inh_mv"])
        if e_inh > _v0() - 1:
            raise ValueError("E_inh_mv must be at least 1 mV below lif.v_0")
        if block.get("scope") not in CBI_SCOPES:
            raise ValueError("conductance_inhibition scope must be all")
    return {key: record.get(key) for key in MECH_BLOCKS}


def _require_mask(block: dict[str, Any], mask: NDArray[np.uint8], n: int, name: str) -> None:
    """Reject a mask_sha256 that differs from the resolved mask."""
    if mask.shape != (n,):
        raise ValueError(f"{name} mask length must equal engine.n")
    if mask_sha256(mask) != block["mask_sha256"]:
        raise ValueError(f"{name} mask_sha256 differs from the resolved mask")


def _adaptation_from_block(block: dict[str, Any], n: int, mask: NDArray[np.uint8]):
    """Per-neuron adaptation arrays. Units: mV and ms. Shapes: (n,)."""
    from flyonenomics.engine.models import Adaptation

    _require_mask(block, mask, n, "adaptation")
    b = np.zeros(n, dtype=np.float64)
    b[mask == 1] = float(block["b_mv"])
    tau = np.full(n, float(block["tau_ms"]), dtype=np.float64)
    return Adaptation(b_mv=b, tau_ms=tau)


def _depression_from_block(block: dict[str, Any], n: int, mask: NDArray[np.uint8]):
    """Per-neuron depression arrays. Units: U dimensionless, tau_ms ms. Shapes: (n,)."""
    from flyonenomics.engine.models import Depression

    _require_mask(block, mask, n, "depression")
    u_arr = np.zeros(n, dtype=np.float64)
    u_arr[mask == 1] = float(block["U"])
    tau = np.full(n, float(block["tau_ms"]), dtype=np.float64)
    return Depression(U=u_arr, tau_ms=tau)


def mechanisms_from_section(
    section: dict[str, Any] | None,
    *,
    n: int,
    super_class: NDArray[np.str_] | NDArray[np.object_] | None = None,
    s_cur: NDArray[np.floating] | None = None,
):
    """Resolve a validated section into Mechanisms. Units: per block. Shapes: (n,)."""
    from flyonenomics.engine.models import ConductanceInhibition, Mechanisms

    parsed = parse_mechanisms_section(section)
    if parsed is None or engine_model_of(parsed) == "lif":
        return None
    if super_class is None:
        super_class, s_cur, n = _engine_scope_inputs()
    if parsed["adaptation"] is not None:
        mask = scope_mask(
            parsed["adaptation"]["scope"], super_class=super_class, s_cur=s_cur
        )
        return Mechanisms(adaptation=_adaptation_from_block(parsed["adaptation"], n, mask))
    if parsed["depression"] is not None:
        mask = scope_mask(
            parsed["depression"]["scope"], super_class=super_class, s_cur=s_cur
        )
        return Mechanisms(depression=_depression_from_block(parsed["depression"], n, mask))
    return Mechanisms(
        conductance_inhibition=ConductanceInhibition(
            E_inh_mv=float(parsed["conductance_inhibition"]["E_inh_mv"])
        )
    )


def mechanisms_from_drive(
    drive: dict[str, Any],
    *,
    n: int | None = None,
    registry: Any = None,
) -> Any:
    """Resolve drive['mechanisms'] against the registry. Units: per block."""
    if "mechanisms" not in drive:
        raise ValueError("drive mapping must state mechanisms")
    section = drive["mechanisms"]
    if registry is not None:
        n = int(registry.n)
    if n is None:
        _super, _s_cur, n = _engine_scope_inputs()
    return mechanisms_from_section(section, n=n)


def mechanisms_section(row: dict[str, Any]) -> dict[str, Any] | None:
    """Drive-file mechanisms section of a ranked-list row. Units: per block."""
    if "mechanisms" not in row and "engine_model" not in row:
        return None
    section = row.get("mechanisms")
    parsed = parse_mechanisms_section(section)
    expected = engine_model_of(parsed)
    named = row.get("engine_model", "lif")
    if named != expected:
        raise ValueError(f"row engine_model {named} is not engine_model_of its section")
    return parsed


def mechanisms_from_unit(
    row: dict[str, Any],
    *,
    n: int | None = None,
    registry: Any = None,
    super_class: NDArray[np.str_] | NDArray[np.object_] | None = None,
    s_cur: NDArray[np.floating] | None = None,
) -> Any:
    """Resolved Mechanisms for a ranked-list row. Units: per block."""
    section = mechanisms_section(row)
    if registry is not None:
        n = int(registry.n)
    if n is None and super_class is None:
        super_class, s_cur, n = _engine_scope_inputs()
    if n is None:
        n = int(np.asarray(super_class).shape[0])
    return mechanisms_from_section(section, n=n, super_class=super_class, s_cur=s_cur)


def resolved_block(section: dict[str, Any] | None) -> dict[str, Any] | None:
    """The non-null block of a section, or null. Units: per block."""
    parsed = parse_mechanisms_section(section)
    if parsed is None or engine_model_of(parsed) == "lif":
        return None
    name = BLOCK_OF_MODEL[engine_model_of(parsed)]
    block = parsed[name]
    return dict(block) if isinstance(block, dict) else None


def substrate_id_for(path: str | Path) -> str:
    """rest: or rest-<tag>: plus 16 hex of the drive file SHA-256 (SPEC-P2 2.5).

    Units: none. Shapes: one identifier.
    """
    file_path = Path(path)
    digest = hash_file(file_path)
    raw = read_yaml(file_path)
    if not isinstance(raw, dict):
        raise ValueError("drive configuration must be a mapping")
    section = raw.get("mechanisms") if "mechanisms" in raw else None
    if "mechanisms" in raw:
        parse_mechanisms_section(section)
    model = engine_model_of(section)
    if model == "lif":
        return "rest:" + digest[:16]
    return f"rest-{TAG_OF_MODEL[model]}:" + digest[:16]


def substrate_engine_agree(substrate_id: str, engine_model: str) -> bool:
    """Whether a substrate_id tag agrees with engine_model (SPEC-P2 5.1)."""
    model = engine_model or "lif"
    if substrate_id == "bare" or substrate_id.startswith("rest:"):
        return model == "lif"
    if substrate_id.startswith("rest-sfa:"):
        return model == "lif+sfa"
    if substrate_id.startswith("rest-std:"):
        return model == "lif+std"
    if substrate_id.startswith("rest-cbi:"):
        return model == "lif+cbi"
    return False
