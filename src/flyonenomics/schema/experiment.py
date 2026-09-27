"""Strict, resolved experiment contract from SPEC section 6."""
from __future__ import annotations

from functools import lru_cache
import hashlib
import json
import math
import warnings
from pathlib import Path
from typing import Annotated, Any, Callable, Literal, Self

import numpy as np
from pydantic import Field, PrivateAttr, ValidationInfo, field_validator, model_validator

from flyonenomics.types import LayerFlags, StrictModel, load_params

UINT32_LIMIT = 2**32
MS_PER_SECOND = 1000
SCHEMA_VERSION = "1.2"
SCHEMA_VERSION_13 = "1.3"
VERSION_DEFAULT = "v0.1"
VERSION_02 = "v0.2"
ANNOTATION_DEFAULT = "v2.1.0"
NAMED_PHASE1 = ("wild_type", "fumin", "dop1r1_null", "dopamine_depleted")
NAMED_1_3 = (
    "wild_type", "fumin", "dat_half", "dopamine_depleted", "dop1r1_null",
    "dop2r_null", "dan_autoreceptor_null", "er_dop1r1_kd", "pam_silenced",
    "cx_dan_silenced", "dfb_silenced",
)
NEW_NAMED_1_3 = frozenset(NAMED_1_3) - frozenset(NAMED_PHASE1)
INJECT_AT = ("TuBu", "ER", "photoreceptors")
_SCHEMA_12_SUBSTRATE = (
    "populations_version", "transmitters_version", "visual_version",
)
_SCHEMA_12_PROBE = {
    "buridan": ("initial_heading",),
    "open_loop_steering": ("blocks",),
    "spontaneous": ("stimulus",),
}
NAME_PATTERN = r"^[a-z0-9][a-z0-9-]{0,63}$"
CHUNK_ALIGNMENT_ABS_TOL = 1e-9
RESOLUTION_META_KEY = "_resolved_populations"
ARM_PATTERN = r"^[a-z0-9][a-z0-9-]{0,31}$"
Rate = Annotated[float, Field(ge=0, le=1000, allow_inf_nan=False)]
Factor = Annotated[float, Field(ge=0, le=10, allow_inf_nan=False)]
DEFERRED_DRUGS = frozenset(("amphetamine", "atomoxetine", "caffeine", "cocaine"))
Drug = Literal["vehicle", "methylphenidate", "3-iodotyrosine"]


@lru_cache(maxsize=None)
def parameter(key: str) -> Any:
    """Read a parameter default; units per YAML, scalar or small list."""
    return load_params().get(key)


class Substrate(StrictModel):
    """Resolved data version pins; units none, scalar strings."""
    connectome_version: Literal["630", "783", "male-cns:v1.0"] = "783"
    annotation_version: str = ANNOTATION_DEFAULT
    receptor_map_version: str = VERSION_DEFAULT
    params_version: str = VERSION_DEFAULT
    drive_version: str | None = VERSION_DEFAULT
    dopamine_version: str = VERSION_DEFAULT
    behaviour_version: str = VERSION_DEFAULT
    populations_version: str | None = None
    transmitters_version: str | None = None
    visual_version: str | None = None


class PopulationManipulation(StrictModel):
    """Population selection; units none, one name."""
    population: str


class Silence(PopulationManipulation):
    """Persistent threshold silence; units none, scalar name."""
    type: Literal["silence"]


class Disconnect(PopulationManipulation):
    """Outgoing connection removal; units none, scalar name."""
    type: Literal["disconnect"]


class Activate(PopulationManipulation):
    """Persistent extended input; rate in Hz, scalar."""
    type: Literal["activate"]
    rate_hz: Rate


class ShiftThreshold(PopulationManipulation):
    """Additive threshold change; delta in mV, scalar."""
    type: Literal["shift_threshold"]
    delta_mv: float = Field(ge=-20, le=20, allow_inf_nan=False)


class ScaleGain(PopulationManipulation):
    """Multiplicative gain; factor dimensionless, scalar."""
    type: Literal["scale_gain"]
    factor: Factor


class ScaleReceptor(PopulationManipulation):
    """Receptor scaling; dimensionless scalar, population may be all."""
    type: Literal["scale_receptor"]
    receptor: Literal["D1", "D2", "Dq"]
    factor: Factor


class ScaleDat(StrictModel):
    """DAT scaling; dimensionless scalar over named compartments or all."""
    type: Literal["scale_dat"]
    compartments: Literal["all"] | Annotated[list[str], Field(min_length=1)]
    factor: Factor


class ScaleRelease(StrictModel):
    """Release scaling; dimensionless scalar."""
    type: Literal["scale_release"]
    factor: Factor


Manipulation = Annotated[Silence | Disconnect | Activate | ShiftThreshold | ScaleGain | ScaleReceptor | ScaleDat | ScaleRelease, Field(discriminator="type")]


class Genotype(StrictModel):
    """Named genotype plus ordered manipulations; units per manipulation, lists."""
    named: Literal[
        "wild_type", "fumin", "dat_half", "dopamine_depleted", "dop1r1_null",
        "dop2r_null", "dan_autoreceptor_null", "er_dop1r1_kd", "pam_silenced",
        "cx_dan_silenced", "dfb_silenced",
    ] = "wild_type"
    manipulations: list[Manipulation] = Field(default_factory=list)

    def expanded(self) -> list[Manipulation]:
        """Return named hooks followed by explicit hooks; units per hook, list."""
        from flyonenomics.schema.named import named_manipulations
        return named_manipulations(self.named) + self.manipulations


class Input(PopulationManipulation):
    """Assay input; Hz, one population and scalar rate."""
    rate_hz: Rate = Field(default_factory=lambda: parameter("input.r_poi"))


class SugarParams(Input):
    """Sugar stimulus; rate in Hz, scalar fields."""
    population: str = "sugar_GRN_R"
    mode: Literal["upstream", "extended"] = "upstream"


class SpontaneousParams(StrictModel):
    """Optional extended input; Hz, one input or null. stimulus is schema 1.3."""
    input: Input | None = None
    stimulus: Literal["dark", "ambient"] | None = None


class Distractor(StrictModel):
    """Visual episode; degrees, Hz, seconds and dimensionless contrast, scalars."""
    azimuth: float = Field(allow_inf_nan=False)
    flicker_hz: Rate
    contrast: float = Field(ge=0, le=1, allow_inf_nan=False)
    onset_s: float = Field(ge=0, allow_inf_nan=False)
    duration_s: float = Field(gt=0, allow_inf_nan=False)


class BuridanParams(StrictModel):
    """Arena options; dimensionless flags and one episode."""
    stripes: bool = True
    encoder: Literal["on", "off"] = "on"
    distractor: Distractor | None = None
    inject_at: Literal["TuBu", "ER", "photoreceptors"] = "TuBu"
    initial_heading: Literal["random", "stripe_A"] | None = None


class OpenLoopDistractor(StrictModel):
    """Held-fly distractor; degrees, Hz, dimensionless contrast. Schema 1.3 blocks."""
    azimuth: float = Field(allow_inf_nan=False)
    flicker_hz: Rate
    contrast: float = Field(ge=0, le=1, allow_inf_nan=False)


class OpenLoopBlock(StrictModel):
    """One open-loop block; seconds, degrees, optional distractor. Schema 1.3."""
    stimulus: Literal["stripe", "ambient", "dark"]
    azimuth_deg: float | None = Field(default=None, allow_inf_nan=False)
    distractor: OpenLoopDistractor | None = None
    transition_s: float = Field(gt=0, allow_inf_nan=False)
    dwell_s: float = Field(gt=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def stripe_azimuth(self) -> Self:
        """Require azimuth_deg for stripe blocks; degrees, scalar."""
        if self.stimulus == "stripe" and self.azimuth_deg is None:
            raise ValueError("azimuth_deg is required for stripe blocks")
        if self.stimulus != "stripe" and self.azimuth_deg is not None:
            raise ValueError("azimuth_deg is only valid for stripe blocks")
        return self


class OpenLoopParams(StrictModel):
    """Open-loop azimuths or schema 1.3 blocks; degrees, optional vector."""
    azimuths: list[Annotated[float, Field(allow_inf_nan=False)]] | None = None
    blocks: list[OpenLoopBlock] | None = None
    inject_at: Literal["TuBu", "ER", "photoreceptors"] | None = None


ASSAY_PARAMS = {"sugar_reflex": SugarParams, "spontaneous": SpontaneousParams,
                "buridan": BuridanParams, "open_loop_steering": OpenLoopParams}


class Probe(StrictModel):
    """Recorded probe; duration in brain seconds, scalar options."""
    type: Literal["probe"]
    assay: Literal["buridan", "open_loop_steering", "sugar_reflex", "spontaneous"]
    duration_s: float = Field(gt=0, le=120, allow_inf_nan=False)
    label: str = Field(min_length=1)
    params: SugarParams | SpontaneousParams | BuridanParams | OpenLoopParams

    @field_validator("duration_s")
    @classmethod
    def chunk_multiple(cls, value: float) -> float:
        """Require whole engine chunks; seconds, scalar."""
        chunks = value * MS_PER_SECOND / parameter("engine.chunk_ms")
        if not math.isclose(chunks, round(chunks), rel_tol=0, abs_tol=CHUNK_ALIGNMENT_ABS_TOL):
            raise ValueError("duration_s must be a positive multiple of 0.01")
        return value

    @field_validator("params", mode="before")
    @classmethod
    def assay_params(cls, value: Any, info: ValidationInfo) -> Any:
        """Resolve the exact assay model; units per assay, scalar model."""
        assay = info.data.get("assay")
        if assay in ASSAY_PARAMS:
            return ASSAY_PARAMS[assay].model_validate(value)
        return value

    @model_validator(mode="after")
    def correct_params(self) -> Self:
        """Reject a model for a different assay; units none, scalar check."""
        if not isinstance(self.params, ASSAY_PARAMS[self.assay]):
            raise ValueError("params do not match assay")
        if isinstance(self.params, BuridanParams) and self.params.distractor:
            d = self.params.distractor
            if d.onset_s + d.duration_s > self.duration_s:
                raise ValueError("distractor episode exceeds probe duration_s")
        if isinstance(self.params, OpenLoopParams):
            if self.params.azimuths is not None and self.params.blocks is not None:
                raise ValueError("open_loop_steering takes azimuths or blocks, not both")
        return self


class DrugPhase(StrictModel):
    """Supported drug identifier; units none, one scalar name."""
    drug: Drug

    @field_validator("drug", mode="before")
    @classmethod
    def supported_drug(cls, value: Any) -> Any:
        """Name recognised but deferred drugs explicitly; units none, scalar name."""
        if isinstance(value, str) and value in DEFERRED_DRUGS:
            raise ValueError(f"NotImplementedInPhase1: {value}")
        return value


class Dose(DrugPhase):
    """Start food exposure; concentration in mM, scalar."""
    type: Literal["dose"]
    drug: Drug
    c_food_mm: float = Field(gt=0, le=100, allow_inf_nan=False)


class Washout(DrugPhase):
    """Stop food exposure; units none, one supported drug."""
    type: Literal["washout"]
    drug: Drug


class Wait(StrictModel):
    """Analytical slow-state advance; hours, scalar."""
    type: Literal["wait"]
    hours: float = Field(gt=0, le=240, allow_inf_nan=False)


SimplePhase = Annotated[Probe | Dose | Washout | Wait, Field(discriminator="type")]


class Repeat(StrictModel):
    """Non-nesting repeat; spacing in hours, body is a phase list."""
    type: Literal["repeat"]
    n: int = Field(ge=2, le=20, strict=True)
    spacing_hours: float = Field(ge=0, le=240, allow_inf_nan=False)
    body: list[SimplePhase] = Field(min_length=1)


Phase = Annotated[Probe | Dose | Washout | Wait | Repeat, Field(discriminator="type")]


class ArmLayers(StrictModel):
    """Only the two allowed ablation overrides; units none, scalar flags."""
    dopamine_A: bool | None = None
    dan_fast_synapses: Literal["retain", "disconnect"] | None = None


class Arm(StrictModel):
    """One genotype and protocol; units per phases, ordered list."""
    label: str = Field(pattern=ARM_PATTERN)
    genotype: Genotype = Field(default_factory=Genotype)
    protocol: list[Phase] = Field(min_length=1)
    layers: ArmLayers | None = None

    def expanded(self) -> list[SimplePhase]:
        """Expand repeat bodies with between-iteration waits; hours, phase list."""
        phases: list[SimplePhase] = []
        for phase in self.protocol:
            if isinstance(phase, Repeat):
                for iteration in range(phase.n):
                    if iteration and phase.spacing_hours:
                        phases.append(Wait(type="wait", hours=phase.spacing_hours))
                    phases.extend(phase.body)
            else:
                phases.append(phase)
        return phases


class Record(StrictModel):
    """Recording selection; rate bin in ms, population lists and scalar flags."""
    spikes: Literal["all"] | list[str] = Field(default_factory=list)
    rates: list[str] = Field(default_factory=list)
    dopamine: bool = True
    receptors: bool = True
    drug: bool = True
    arena: bool = True
    popcount: bool = True
    rate_bin_ms: int = Field(default_factory=lambda: parameter("rate_bin_ms"), gt=0, strict=True)
    live: bool = True

    @model_validator(mode="after")
    def bins(self) -> Self:
        """Require whole chunk bins and unique population columns; ms, lists."""
        if self.rate_bin_ms % parameter("engine.chunk_ms"):
            raise ValueError("record.rate_bin_ms must be a multiple of engine.chunk_ms")
        for names in (self.rates, self.spikes if self.spikes != "all" else []):
            if len(names) != len(set(names)):
                raise ValueError("record population names must be distinct")
        return self


def _walk_phases(phases: list[Any]) -> list[Any]:
    """Yield nested protocol dicts including repeat bodies; units none."""
    out: list[Any] = []
    for phase in phases:
        if isinstance(phase, dict) and phase.get("type") == "repeat":
            out.extend(_walk_phases(phase.get("body") or []))
        else:
            out.append(phase)
    return out


def _default_inject_at(substrate: dict[str, Any]) -> str:
    """Section 8.1 inject_at default: the pinned visual file, else the pinned params row. Units: none."""
    from flyonenomics.io import read_yaml
    from flyonenomics.types import params_path_for_version

    root = Path(__file__).resolve().parents[3]
    visual = substrate.get("visual_version")
    if visual:
        path = root / "data" / f"visual-{visual}.yaml"
        if path.is_file():
            value = (read_yaml(path) or {}).get("inject_at")
            if value is not None:
                return str(value)
    params_path = params_path_for_version(str(substrate.get("params_version")))
    if not params_path.is_file():
        raise ValueError(f"unavailable params_version: {substrate.get('params_version')}")
    return str(load_params(params_path).get("vis.inject_at"))


def _pinned_drive_has_mechanism(drive_version: str | None) -> bool:
    """Whether the pinned drive file has a mechanism on (SPEC-P2 5.1)."""
    if not drive_version:
        return False
    from flyonenomics.drive.mechanisms import engine_model_of
    from flyonenomics.io import read_yaml, unlogged

    path = Path(__file__).resolve().parents[3] / "data" / f"drive-{drive_version}.yaml"
    if not path.is_file():
        return False
    with unlogged():
        raw = read_yaml(path) or {}
    if not isinstance(raw, dict):
        return False
    section = raw.get("mechanisms") if "mechanisms" in raw else None
    return engine_model_of(section) != "lif"


def _fill_13_probe_defaults(phase: dict[str, Any], *, background: bool, inject_default: Callable[[], str]) -> None:
    """Fill schema 1.3 probe defaults; units per assay, in-place dict."""
    if phase.get("type") != "probe":
        return
    params = phase.setdefault("params", {})
    if not isinstance(params, dict):
        return
    assay = phase.get("assay")
    if assay == "buridan":
        if background:
            if "inject_at" not in params:
                params["inject_at"] = inject_default()
            params.setdefault("initial_heading", "random")
        else:
            params.setdefault("inject_at", "TuBu")
            params.setdefault("initial_heading", "stripe_A")
    elif assay == "spontaneous":
        params.setdefault("stimulus", "dark")
    elif assay == "open_loop_steering" and background:
        if "inject_at" not in params:
            params["inject_at"] = inject_default()


class Experiment(StrictModel):
    """Validated experiment; seconds/hours/Hz per fields, no neuron arrays."""
    schema_version: Literal["1.2", "1.3"] = SCHEMA_VERSION
    name: str = Field(pattern=NAME_PATTERN)
    description: str = ""
    seed: int = Field(ge=0, lt=UINT32_LIMIT, strict=True)
    seeds: list[Annotated[int, Field(ge=0, lt=UINT32_LIMIT, strict=True)]] = Field(min_length=1)
    substrate: Substrate = Field(default_factory=Substrate)
    layers: LayerFlags = Field(default_factory=LayerFlags)
    arms: list[Arm] = Field(min_length=1)
    comparison: Literal["paired", "ablation"] = "paired"
    record: Record = Field(default_factory=Record)
    meta: dict[str, Any] = Field(default_factory=dict)
    apply_scales_without_background: bool | None = None
    _warnings: list[str] = PrivateAttr(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def schema_defaults(cls, data: Any) -> Any:
        """Apply 1.3 version pins and probe defaults; units none, mapping in."""
        if not isinstance(data, dict):
            return data
        version = data.get("schema_version", SCHEMA_VERSION)
        layers = data.get("layers") or {}
        background = bool(layers.get("background", False)) if isinstance(layers, dict) else False
        substrate = dict(data.get("substrate") or {})
        if version == SCHEMA_VERSION_13:
            if background:
                pins = {
                    "params_version": VERSION_02,
                    "populations_version": VERSION_02,
                    "transmitters_version": VERSION_02,
                    "drive_version": VERSION_02,
                    "dopamine_version": VERSION_02,
                    "visual_version": VERSION_02,
                    "behaviour_version": VERSION_02,
                }
            else:
                pins = {
                    "params_version": VERSION_DEFAULT,
                    "populations_version": VERSION_DEFAULT,
                    "dopamine_version": VERSION_DEFAULT,
                    "behaviour_version": VERSION_DEFAULT,
                    "drive_version": None,
                    "transmitters_version": None,
                    "visual_version": None,
                }
            for key, value in pins.items():
                substrate.setdefault(key, value)
            data["substrate"] = substrate
            resolved_inject: list[str] = []

            def inject_default() -> str:
                if not resolved_inject:
                    resolved_inject.append(_default_inject_at(substrate))
                return resolved_inject[0]

            for arm in data.get("arms") or []:
                if not isinstance(arm, dict):
                    continue
                for phase in _walk_phases(arm.get("protocol") or []):
                    if isinstance(phase, dict):
                        _fill_13_probe_defaults(phase, background=background, inject_default=inject_default)
        return data

    @model_validator(mode="after")
    def matched(self) -> Self:
        """Validate phase matching and layer/drug domains; units per phase, lists."""
        if len(self.seeds) != len(set(self.seeds)):
            raise ValueError("seeds must be distinct")
        labels = [arm.label for arm in self.arms]
        if len(labels) != len(set(labels)):
            raise ValueError("arm labels must be distinct")
        reference: list[dict[str, Any]] | None = None
        for arm in self.arms:
            if arm.layers is not None and self.comparison != "ablation":
                raise ValueError("arm.layers requires comparison ablation")
            flags = self.arm_layers(arm)
            phases = arm.expanded()
            if not any(isinstance(p, Probe) for p in phases):
                raise ValueError(f"arm {arm.label} requires at least one probe")
            dosed: set[str] = set()
            for phase in phases:
                if isinstance(phase, Probe) and self.substrate.connectome_version == "630" and phase.assay not in ("sugar_reflex", "spontaneous"):
                    raise ValueError("connectome_version 630 supports only sugar_reflex and spontaneous")
                if isinstance(phase, Dose):
                    if not flags.transporter_C and phase.drug != "vehicle":
                        raise ValueError("dose: transporter_C layer off")
                    dosed.add(phase.drug)
                if isinstance(phase, Washout) and phase.drug not in dosed:
                    raise ValueError(f"washout {phase.drug} must follow a dose")
            for hook in arm.genotype.expanded():
                if isinstance(hook, ScaleReceptor) and not flags.dopamine_A:
                    raise ValueError("scale_receptor: dopamine_A layer off")
                if isinstance(hook, (ScaleDat, ScaleRelease)) and not flags.transporter_C:
                    raise ValueError(f"{hook.type}: transporter_C layer off")
            comparable = [p.model_dump(mode="json", exclude={"drug"}) for p in phases]
            if reference is not None:
                difference = first_difference(reference, comparable, "protocol")
                if difference:
                    raise ValueError(f"matched arms: {arm.label}.{difference}")
            reference = comparable
        self._check_schema_features()
        return self

    def _check_schema_features(self) -> None:
        """Reject 1.3-only features on 1.2 and on 1.3 bare files. Units none."""
        if self.schema_version != SCHEMA_VERSION_13:
            # A 1.2 file resolves exactly as in Phase 1. model_dump drops the
            # 1.3-only keys from the protocol hash, so any value set there
            # would change behaviour without changing the hash.
            pins = self.substrate
            if any(getattr(pins, key) is not None for key in _SCHEMA_12_SUBSTRATE):
                raise ValueError("populations_version, transmitters_version and visual_version are schema 1.3 features")
            if pins.drive_version is None:
                raise ValueError("a null drive_version is a schema 1.3 feature")
            # SPEC-P2 decision 22: the rest substrate is reachable only through 1.3.
            for key in ("params_version", "drive_version"):
                if getattr(pins, key) == VERSION_02:
                    raise ValueError(
                        f"schema 1.2 rejects a v0.2 {key} pin: schema 1.3 is the only route to the rest substrate"
                    )
            if _pinned_drive_has_mechanism(pins.drive_version):
                raise ValueError("schema 1.2 rejects a drive pin with a mechanism")
            if self.apply_scales_without_background is not None:
                raise ValueError("apply_scales_without_background is a schema 1.3 feature")
            for arm in self.arms:
                if arm.genotype.named in NEW_NAMED_1_3:
                    raise ValueError("named genotype new in 1.3")
                for phase in arm.expanded():
                    if isinstance(phase, Probe):
                        params = phase.params
                        if isinstance(params, BuridanParams) and params.inject_at == "photoreceptors":
                            raise ValueError("photoreceptor injection is a schema 1.3 feature")
                        if isinstance(params, BuridanParams) and params.initial_heading is not None:
                            raise ValueError("initial_heading is a schema 1.3 feature")
                        if isinstance(params, OpenLoopParams) and (params.blocks is not None or params.inject_at is not None):
                            raise ValueError("open_loop blocks and inject_at are schema 1.3 features")
                        if isinstance(params, SpontaneousParams) and params.stimulus is not None:
                            raise ValueError("spontaneous stimulus is a schema 1.3 feature")
            return
        if self.layers.background:
            self._check_open_loop_block_duration()
            return
        scales_exception = bool(self.apply_scales_without_background) and self.substrate.drive_version == VERSION_02
        pins = self.substrate
        v02_keys = (
            pins.params_version, pins.populations_version, pins.transmitters_version,
            pins.dopamine_version, pins.behaviour_version, pins.visual_version,
        )
        if VERSION_02 in v02_keys:
            raise ValueError("schema 1.3 with background false rejects a v0.2 pin")
        if pins.drive_version == VERSION_02 and not scales_exception:
            raise ValueError("schema 1.3 with background false rejects a v0.2 pin")
        if _pinned_drive_has_mechanism(pins.drive_version) and not scales_exception:
            raise ValueError("schema 1.3 with background false rejects a drive pin with a mechanism")
        for arm in self.arms:
            if arm.genotype.named in NEW_NAMED_1_3:
                raise ValueError("named genotype new in 1.3")
            for phase in arm.expanded():
                if not isinstance(phase, Probe):
                    continue
                params = phase.params
                if isinstance(params, BuridanParams):
                    if params.inject_at == "photoreceptors":
                        raise ValueError("photoreceptor injection is a 1.3-only feature")
                    if params.initial_heading == "random":
                        raise ValueError("random heading is a 1.3-only feature")
                elif isinstance(params, OpenLoopParams):
                    if params.blocks:
                        raise ValueError("open_loop blocks are a 1.3-only feature")
                    if params.inject_at == "photoreceptors":
                        raise ValueError("photoreceptor injection is a 1.3-only feature")
                elif isinstance(params, SpontaneousParams):
                    if params.stimulus not in (None, "dark"):
                        raise ValueError("stimulus other than dark is a 1.3-only feature")

    def _check_open_loop_block_duration(self) -> None:
        """Require duration_s to match block times; seconds, schema 1.3."""
        for arm in self.arms:
            for phase in arm.expanded():
                if not isinstance(phase, Probe) or not isinstance(phase.params, OpenLoopParams):
                    continue
                blocks = phase.params.blocks
                if not blocks:
                    continue
                total = sum(block.transition_s + block.dwell_s for block in blocks)
                if not math.isclose(phase.duration_s, total, rel_tol=0, abs_tol=CHUNK_ALIGNMENT_ABS_TOL):
                    raise ValueError("duration_s must equal the sum of transition_s + dwell_s over blocks")

    def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """Serialize; schema 1.2 omits 1.3-only keys so protocol hashes stay stable."""
        data = super().model_dump(*args, **kwargs)
        if data.get("schema_version") != SCHEMA_VERSION:
            if data.get("apply_scales_without_background") is None:
                data.pop("apply_scales_without_background", None)
            return data
        substrate = data.get("substrate") or {}
        for key in _SCHEMA_12_SUBSTRATE:
            substrate.pop(key, None)
        data["substrate"] = substrate
        data.pop("apply_scales_without_background", None)
        for arm in data.get("arms") or []:
            protocols = list(arm.get("protocol") or [])
            nested: list[Any] = []
            for phase in protocols:
                nested.append(phase)
                if isinstance(phase, dict) and phase.get("type") == "repeat":
                    nested.extend(phase.get("body") or [])
            for phase in nested:
                if not isinstance(phase, dict):
                    continue
                params = phase.get("params")
                if not isinstance(params, dict):
                    continue
                for key in _SCHEMA_12_PROBE.get(phase.get("assay"), ()):
                    params.pop(key, None)
                if phase.get("assay") == "open_loop_steering":
                    params.pop("inject_at", None)
        return data

    def arm_layers(self, arm: Arm) -> LayerFlags:
        """Resolve an arm's flags; units none, scalar flags."""
        flags = {key: getattr(self.layers, key) for key in self.layers.__dataclass_fields__}
        if arm.layers:
            flags.update(arm.layers.model_dump(exclude_none=True))
        return LayerFlags(**flags)

    def resolve(self, registry: Any) -> dict[str, list[int]]:
        """Resolve all used populations, warning on overlaps; int32 engine indices (m,)."""
        names = set(self.record.rates)
        if self.record.spikes != "all":
            names.update(self.record.spikes)
        for arm in self.arms:
            for hook in arm.genotype.expanded():
                if isinstance(hook, PopulationManipulation) and not (isinstance(hook, ScaleReceptor) and hook.population == "all"):
                    names.add(hook.population)
                if isinstance(hook, ScaleDat) and hook.compartments != "all":
                    known = {c.name for c in registry.compartments()}
                    if set(hook.compartments) - known:
                        raise ValueError("unknown scale_dat compartments")
            if self.arm_layers(arm).dan_fast_synapses == "disconnect":
                names.update(("DAN", "CX_DAN"))
            for phase in arm.expanded():
                if isinstance(phase, Probe):
                    params = phase.params
                    if isinstance(params, SugarParams):
                        names.update((params.population, "MN9"))
                    elif isinstance(params, SpontaneousParams) and params.input:
                        names.add(params.input.population)
                    elif isinstance(params, BuridanParams):
                        names.add("R1_6" if params.inject_at == "photoreceptors" else params.inject_at)
                    elif isinstance(params, OpenLoopParams) and params.inject_at:
                        names.add("R1_6" if params.inject_at == "photoreceptors" else params.inject_at)
        resolved: dict[str, list[int]] = {}
        for name in sorted(names):
            try:
                pop = registry.population(name)
            except KeyError:
                raise ValueError(f"unknown population: {name}") from None
            if not len(pop.idx):
                raise ValueError(f"population resolves to zero neurons: {name}")
            resolved[name] = [int(i) for i in pop.idx]
        self._warnings = []
        for arm in self.arms:
            active = [h for h in arm.genotype.expanded() if isinstance(h, Activate) and h.rate_hz > 0]
            for k, phase in enumerate(arm.expanded()):
                if isinstance(phase, Probe) and isinstance(phase.params, SugarParams) and phase.params.mode == "upstream" and phase.params.rate_hz > 0:
                    for hook in active:
                        if np.intersect1d(resolved[phase.params.population], resolved[hook.population]).size:
                            message = f"upstream/extended overlap: arm {arm.label} probe {k}: {phase.params.population} and {hook.population}; upstream refractory wins"
                            self._warnings.append(message)
                            warnings.warn(message, UserWarning, stacklevel=2)
        self.meta[RESOLUTION_META_KEY] = resolved
        return resolved

    def canonical_json(self) -> str:
        """Serialize resolved defaults for hashing; units per fields, JSON scalar string."""
        return json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), allow_nan=False)

    def protocol_hash(self) -> str:
        """Hash canonical validated JSON; units none, SHA-256 string."""
        return hashlib.sha256(self.canonical_json().encode()).hexdigest()


def first_difference(a: Any, b: Any, path: str) -> str | None:
    """Return the first differing field path; units none, scalar string or null."""
    if type(a) is not type(b):
        return f"{path}: {a!r} != {b!r}"
    if isinstance(a, dict):
        for key in dict.fromkeys([*a, *b]):
            if key not in a or key not in b:
                return f"{path}.{key}: missing field"
            difference = first_difference(a[key], b[key], f"{path}.{key}")
            if difference:
                return difference
    elif isinstance(a, list):
        if len(a) != len(b):
            return f"{path}.length: {len(a)} != {len(b)}"
        for i, (left, right) in enumerate(zip(a, b, strict=True)):
            difference = first_difference(left, right, f"{path}[{i}]")
            if difference:
                return difference
    elif a != b:
        return f"{path}: {a!r} != {b!r}"
    return None


def load_experiment(path: str | Path) -> Experiment:
    """Load strict JSON and resolve defaults; units per fields, one experiment."""
    from flyonenomics.io import read_text

    return Experiment.model_validate_json(read_text(path))
