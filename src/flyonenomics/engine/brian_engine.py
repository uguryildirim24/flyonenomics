"""Brian2 implementation of the engine interface (SPEC section 3.1, WP1).

Units and array shapes are stated in every public docstring.
Brian2 is seeded only through Engine.seed. Bank switching goes through
the public active flag. No private Brian2 field is touched.

Construction mirrors the clone's create_model line for line (same object
order, same connectivity, same initial state) except for unique object
names per build (only one built engine is supported per process), the two
per-neuron state variables v_th_i and gain_i in the equations, the
threshold string v > v_th_i, and the synapse update g += w * gain_i_post
(which equals the clone's g += w while every gain is 1). The
upstream-exact input mode calls the clone's poi once per declared bank.
"""

from __future__ import annotations

import atexit
import gc
import importlib.util
import itertools
import os
import pickle
import shutil
import weakref
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

import brian2 as b
from brian2 import Hz, ms, mV, second

from flyonenomics.connectome_arrays import (
    base_weight_memmap,
    cache_dir,
    load_connectome_arrays,
)
from flyonenomics.io import load_npy
from flyonenomics.types import ChunkResult, ConnectomeFiles, Params, SpikeTable
from flyonenomics.engine.base import Engine, InputTopology, MechanismTraceTable, TraceTable, UpstreamBank
from flyonenomics.engine.models import (
    CBI_METHOD,
    LIF_METHOD,
    LIF_MODEL,
    LIF_RESET,
    LIF_THRESHOLD,
    Adaptation,
    ConductanceInhibition,
    Depression,
    Mechanisms,
    cbi_strings,
    lif_strings,
    resolve_engine_model,
    sfa_strings,
    std_strings,
)


# Delay of the extended-mode and spike-list synapses in ms. Section 3.1
# states on_pre and w_in but no delay; zero matches the delay-free
# upstream PoissonInput. Single module-level name so it can move.
EXTENDED_SYNAPSE_DELAY_MS = 0.0

# Largest trace set the engine accepts (SPEC section 3.1).
# The 774-cell plain-LIF census is the largest set measured in one build.
# At dt 0.1 ms its 20 s raw voltage monitor holds about 1.24 GB per worker;
# monitor memory also grows with duration and the number of model variables,
# so this count is not a general memory budget (measured 2026-09-20, t-0029).
TRACE_MAX = 774

_BUILD_COUNTER = itertools.count()


def repo_root() -> Path:
    """Return the repository root of this worktree.

    Units: none. Shapes: a single path.
    """
    return Path(__file__).resolve().parents[3]


def _configure_codegen() -> Path:
    """Point Brian2 Cython code generation at this lane's build cache.

    Units: none. Shapes: a single path.
    """
    target = cache_dir() / "cython" / repo_root().name
    target.mkdir(parents=True, exist_ok=True)
    b.prefs.codegen.target = "cython"
    b.prefs.codegen.runtime.cython.cache_dir = str(target)
    return target


CYTHON_CACHE_DIR = _configure_codegen()


def shiu_clone_dir() -> Path:
    """Return the pinned Shiu clone directory.

    Units: none. Shapes: a single path.
    """
    return cache_dir() / "Drosophila_brain_model"


def load_shiu_model() -> object:
    """Import the clone's model.py from the pinned path without editing it.

    Units: none. Shapes: the imported module. The engine calls only
    default_params and poi; model.py also imports joblib for its
    parallel runner, which is not a pinned dependency here, so a
    minimal placeholder stands in for that import only (deviation D1).
    """
    path = shiu_clone_dir() / "model.py"
    if not path.is_file():
        raise FileNotFoundError(f"Shiu clone model.py is absent: {path}")
    try:
        import joblib  # noqa: F401
    except ModuleNotFoundError:
        import sys
        import types

        stub = types.ModuleType("joblib")

        def _unavailable(*args: object, **kwargs: object) -> None:
            raise RuntimeError("joblib is not a pinned dependency of this project")

        stub.Parallel = _unavailable  # type: ignore[attr-defined]
        stub.delayed = _unavailable  # type: ignore[attr-defined]
        stub.parallel_backend = _unavailable  # type: ignore[attr-defined]
        sys.modules.setdefault("joblib", stub)
    spec = importlib.util.spec_from_file_location("shiu_model_pinned", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot import Shiu model.py from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def resolve_connectome_path(path: Path) -> Path:
    """Resolve a connectome file path to an existing file.

    Units: none. Shapes: one path in, one path out. Absolute paths
    are used as given; relative paths resolve against the repository
    root and then against the shared cache directory.
    """
    candidate = Path(path)
    if candidate.is_absolute():
        if candidate.is_file():
            return candidate
        raise FileNotFoundError(f"connectome file is absent: {candidate}")
    for base in (repo_root(), cache_dir()):
        resolved = base / candidate
        if resolved.is_file():
            return resolved
    raise FileNotFoundError(f"connectome file is absent: {path}")



_ENGINE_STORE_OWNED: list[Path] = []


def _pid_alive(pid: int) -> bool:
    """Return whether pid exists on this machine. Units: none. Shapes: scalar."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _remove_files(paths: list[Path]) -> None:
    """Delete snapshot files an engine wrote. Units: none. Shapes: none."""
    for path in paths:
        path.unlink(missing_ok=True)


def sweep_engine_store(root: Path) -> list[Path]:
    """Remove engine-store directories of processes that no longer exist.

    Units: none. Shapes: returns removed directories. A killed worker never
    runs its exit handler, so the next process that stores sweeps for it.
    """
    removed: list[Path] = []
    if not root.is_dir():
        return removed
    for child in root.iterdir():
        if child.is_dir() and child.name.isdigit() and int(child.name) != os.getpid() and not _pid_alive(int(child.name)):
            shutil.rmtree(child, ignore_errors=True)
            removed.append(child)
    return removed


def engine_store_dir() -> Path:
    """Return this process's snapshot directory, creating it once. Units: none.

    Shapes: one path. The first call sweeps dead processes' directories and
    registers removal of this one at interpreter exit.
    """
    root = cache_dir() / "engine-store"
    directory = root / str(os.getpid())
    if directory not in _ENGINE_STORE_OWNED:
        sweep_engine_store(root)
        atexit.register(shutil.rmtree, directory, True)
        _ENGINE_STORE_OWNED.append(directory)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


class BrianEngine:
    """Whole-brain engine on the Brian2 Cython backend.

    Units: thresholds in mV, rates in Hz, refractory periods in ms,
    weights in mV, ticks in engine ticks. Shapes: per-neuron arrays
    have shape (n,); per-connection arrays have shape (n_syn,).
    One active engine per process: builds share Brian2's default clock
    (the orchestrator holds one built network per worker process).
    """

    n: int
    n_syn: int
    root_ids: NDArray[np.int64]
    dt_ms: float
    ticks_per_ms: int

    def __init__(self) -> None:
        """Create an unbuilt engine. Units: none. Shapes: scalars only."""
        self.n = 0
        self.n_syn = 0
        self.root_ids = np.zeros(0, dtype=np.int64)
        self.dt_ms = 0.0
        self.ticks_per_ms = 0
        self.background_path = "unbuilt"
        self._built = False
        self._net: b.Network | None = None
        self._neu: b.NeuronGroup | None = None
        self._syn: b.Synapses | None = None
        self._spk: b.SpikeMonitor | None = None
        self._mon: b.StateMonitor | None = None
        self._bank_pois: list[list[b.PoissonInput]] = []
        self._bank_idx: list[NDArray[np.int32]] = []
        self._bank_active: list[bool] = []
        self._ext: b.PoissonGroup | None = None
        self._ext_idx: NDArray[np.int32] = np.zeros(0, dtype=np.int32)
        self._gen: b.SpikeGeneratorGroup | None = None
        self._gen_idx: NDArray[np.int32] = np.zeros(0, dtype=np.int32)
        self._trace_idx: NDArray[np.int32] = np.zeros(0, dtype=np.int32)
        self._rfc_base_ms: NDArray[np.float64] = np.zeros(0, dtype=np.float64)
        self._base_w_mv: NDArray[np.float64] = np.zeros(0, dtype=np.float64)
        self._t0_tick: int = 0
        self._store_t0: dict[str, int] = {}
        self._store_rfc_base: dict[str, NDArray[np.float64]] = {}
        self._store_files: dict[str, Path] = {}
        self._store_paths: list[Path] = []
        self._engine_model_name = ""
        self._method_name = ""
        self._passed_model_strings: tuple[str, str, str, str] | None = None
        self._U_std: NDArray[np.float64] = np.zeros(0, dtype=np.float64)
        self._t_dly_ms: float = 0.0

    # -- construction -------------------------------------------------

    def build(
        self,
        connectome: ConnectomeFiles,
        params: Params,
        topology: InputTopology,
        mechanisms: Mechanisms | None = None,
    ) -> None:
        """Build the network in SPEC construction order and store("initial").

        Units: params carry their own units; bank rates in Hz. Shapes:
        no arrays; topology index arrays are validated as int32.
        The variant is chosen from mechanisms before any Brian2 object
        exists. None, an omitted argument, or all-null blocks build lif.
        Bare path (no extended, spikelist, background, or trace objects):
        seed state comes from the prior seed() call, then NeuronGroup,
        Synapses, SpikeMonitor in the clone's order, v_th_i and gain_i
        initialised, poi per bank in declaration order, Network, store.
        Extended path: the bare objects first in the same order, then
        the background PoissonInput, the extended PoissonGroup and its
        Synapses, the SpikeGeneratorGroup and its Synapses, the
        StateMonitor, Network with every object, store.
        """
        if self._built:
            raise RuntimeError("engine is already built")
        model_name = resolve_engine_model(mechanisms)
        if model_name == "lif":
            self._passed_model_strings = lif_strings()
            self._method_name = LIF_METHOD
        elif model_name == "lif+sfa":
            self._passed_model_strings = sfa_strings()
            self._method_name = LIF_METHOD
        elif model_name == "lif+std":
            self._passed_model_strings = std_strings()
            self._method_name = LIF_METHOD
        elif model_name == "lif+cbi":
            self._passed_model_strings = cbi_strings()
            self._method_name = CBI_METHOD
        else:
            raise ValueError(f"unsupported engine model {model_name}")
        self._engine_model_name = model_name
        self._check_topology(topology)
        tag = f"e{next(_BUILD_COUNTER)}"
        dt_ms = float(params.get("lif.dt"))
        if not np.isfinite(dt_ms) or dt_ms <= 0:
            raise ValueError(f"lif.dt must be positive, got {dt_ms}")
        if not np.isclose(round(1.0 / dt_ms) * dt_ms, 1.0, rtol=0, atol=1e-12):
            raise ValueError("lif.dt must divide 1 ms exactly")
        b.defaultclock.dt = dt_ms * ms
        self.dt_ms = dt_ms
        self.ticks_per_ms = int(round(1.0 / dt_ms))

        comp_path = resolve_connectome_path(connectome.completeness)
        con_path = resolve_connectome_path(connectome.connectivity)
        root_ids, i_pre, j_post, w_exc = load_connectome_arrays(comp_path, con_path)
        self.root_ids = np.asarray(root_ids, dtype=np.int64)
        self.n = int(self.root_ids.shape[0])
        for idx in [bank.idx for bank in topology.upstream_banks] + [
            topology.extended_idx, topology.spikelist_idx, topology.trace_idx
        ]:
            if idx.size and idx.max() >= self.n:
                raise ValueError("topology index outside the connectome")

        shiu = load_shiu_model()
        model_params = self._model_params(params, shiu)
        if self._passed_model_strings is None:
            raise RuntimeError("engine strings missing")
        model_str, thresh, reset, on_pre = self._passed_model_strings
        b_sfa_mv: NDArray[np.float64] | None = None
        tau_sfa_ms: NDArray[np.float64] | None = None
        u_std: NDArray[np.float64] | None = None
        tau_std_ms: NDArray[np.float64] | None = None
        e_inh_mv: float | None = None
        if model_name == "lif+sfa":
            if mechanisms is None or not isinstance(mechanisms.adaptation, Adaptation):
                raise TypeError("lif+sfa requires Mechanisms.adaptation")
            b_sfa_mv = np.asarray(mechanisms.adaptation.b_mv, dtype=np.float64)
            tau_sfa_ms = np.asarray(mechanisms.adaptation.tau_ms, dtype=np.float64)
            if b_sfa_mv.shape != (self.n,) or tau_sfa_ms.shape != (self.n,):
                raise ValueError("adaptation arrays must have shape (n,)")
            if (
                not np.all(np.isfinite(b_sfa_mv))
                or not np.all(np.isfinite(tau_sfa_ms))
                or np.any(tau_sfa_ms <= 0)
            ):
                raise ValueError("adaptation arrays must be finite with tau_ms > 0")
        if model_name == "lif+std":
            if mechanisms is None or not isinstance(mechanisms.depression, Depression):
                raise TypeError("lif+std requires Mechanisms.depression")
            u_std = np.asarray(mechanisms.depression.U, dtype=np.float64)
            tau_std_ms = np.asarray(mechanisms.depression.tau_ms, dtype=np.float64)
            if u_std.shape != (self.n,) or tau_std_ms.shape != (self.n,):
                raise ValueError("depression arrays must have shape (n,)")
            if (
                not np.all(np.isfinite(u_std))
                or not np.all(np.isfinite(tau_std_ms))
                or np.any(tau_std_ms <= 0)
                or np.any(u_std < 0)
            ):
                raise ValueError("depression arrays must be finite with tau_ms > 0 and U >= 0")
        if model_name == "lif+cbi":
            if mechanisms is None or not isinstance(
                mechanisms.conductance_inhibition, ConductanceInhibition
            ):
                raise TypeError("lif+cbi requires Mechanisms.conductance_inhibition")
            e_inh_mv = float(mechanisms.conductance_inhibition.E_inh_mv)
            if not np.isfinite(e_inh_mv):
                raise ValueError("E_inh_mv must be finite")
        namespace = dict(model_params)
        if e_inh_mv is not None:
            e_inh = e_inh_mv * mV
            namespace["E_inh"] = e_inh
            namespace["dV_inh"] = model_params["v_0"] - e_inh
        neu = b.NeuronGroup(
            N=self.n,
            model=model_str,
            method=self._method_name,
            threshold=thresh,
            reset=reset,
            refractory="rfc",
            name=f"neurons_{tag}",
            namespace=namespace,
        )
        neu.v = model_params["v_0"]
        neu.g = 0 * mV
        neu.rfc = model_params["t_rfc"]
        neu.v_th_i = model_params["v_th"]
        neu.gain_i = 1.0
        neu.w_bg_i = 0.0 * mV
        if b_sfa_mv is not None and tau_sfa_ms is not None:
            neu.a_sfa = 0 * mV
            neu.b_sfa_i = b_sfa_mv * mV
            neu.tau_sfa_i = tau_sfa_ms * ms
        self._t_dly_ms = float(model_params["t_dly"] / ms)
        self._U_std = np.zeros(self.n, dtype=np.float64)
        if u_std is not None and tau_std_ms is not None:
            neu.x_std = 1.0
            neu.xr_std = 1.0
            neu.U_std_i = u_std
            neu.tau_std_i = tau_std_ms * ms
            self._U_std = u_std.copy()
        if e_inh_mv is not None:
            neu.h_inh = 0.0

        syn_kwargs = {}
        if e_inh_mv is not None:
            syn_kwargs["namespace"] = {
                "E_inh": namespace["E_inh"],
                "dV_inh": namespace["dV_inh"],
            }
        syn = b.Synapses(
            neu,
            neu,
            "w : volt",
            on_pre=on_pre,
            delay=model_params["t_dly"],
            name=f"synapses_{tag}",
            **syn_kwargs,
        )
        syn.connect(i=np.asarray(i_pre, dtype=np.int32), j=np.asarray(j_post, dtype=np.int32))
        w_syn_mv = float(model_params["w_syn"] / mV)
        self._base_w_mv = base_weight_memmap(w_exc, w_syn_mv, comp_path, con_path)
        syn.w = np.asarray(self._base_w_mv, dtype=np.float64) * mV
        del i_pre, j_post, w_exc, root_ids
        spk = b.SpikeMonitor(neu, name=f"spikes_{tag}")

        self.n_syn = int(self._base_w_mv.shape[0])
        self._rfc_base_ms = np.full(
            self.n, float(model_params["t_rfc"] / ms), dtype=np.float64
        )

        bank_pois: list[list[b.PoissonInput]] = []
        bank_idx: list[NDArray[np.int32]] = []
        for bank in topology.upstream_banks:
            per_bank = dict(model_params)
            per_bank["r_poi"] = float(bank.rate_hz) * Hz
            pois, neu = shiu.poi(neu, [int(i) for i in bank.idx], [], per_bank)
            bank_pois.append(list(pois))
            bank_idx.append(bank.idx.copy())
        self._bank_pois = bank_pois
        self._bank_idx = bank_idx
        self._bank_active = [True] * len(bank_pois)

        extra: list[b.BrianObject] = []
        if topology.background:
            bg = b.PoissonInput(
                target=neu,
                target_var="g",
                N=int(params.get("bg.n_bg")),
                rate=float(params.get("bg.r_bg")) * Hz,
                weight="w_bg_i",
            )
            extra.append(bg)
            self.background_path = "per-neuron-string"
        else:
            self.background_path = "absent"

        self._ext_idx = np.array(topology.extended_idx, dtype=np.int32, copy=True)
        if self._ext_idx.shape[0]:
            w_in = model_params["w_syn"] * model_params["f_poi"]
            ext = b.PoissonGroup(
                self._ext_idx.shape[0],
                rates=np.zeros(self._ext_idx.shape[0]) * Hz,
                name=f"extended_{tag}",
            )
            ext_syn = b.Synapses(
                ext,
                neu,
                on_pre="g += w_in",
                delay=EXTENDED_SYNAPSE_DELAY_MS * ms,
                namespace={"w_in": w_in},
                name=f"extended_syn_{tag}",
            )
            ext_syn.connect(
                i=np.arange(self._ext_idx.shape[0], dtype=np.int32), j=self._ext_idx
            )
            extra.extend([ext, ext_syn])
            self._ext = ext

        self._gen_idx = np.array(topology.spikelist_idx, dtype=np.int32, copy=True)
        if self._gen_idx.shape[0]:
            w_in = model_params["w_syn"] * model_params["f_poi"]
            gen = b.SpikeGeneratorGroup(
                self._gen_idx.shape[0],
                indices=np.zeros(0, dtype=np.int32),
                times=np.zeros(0) * ms,
                name=f"spikelist_{tag}",
            )
            gen_syn = b.Synapses(
                gen,
                neu,
                on_pre="g += w_in",
                delay=EXTENDED_SYNAPSE_DELAY_MS * ms,
                namespace={"w_in": w_in},
                name=f"spikelist_syn_{tag}",
            )
            gen_syn.connect(
                i=np.arange(self._gen_idx.shape[0], dtype=np.int32), j=self._gen_idx
            )
            extra.extend([gen, gen_syn])
            self._gen = gen

        self._trace_idx = np.array(topology.trace_idx, dtype=np.int32, copy=True)
        if self._trace_idx.shape[0]:
            recorded: str | list[str] = "v"
            if model_name == "lif+sfa":
                recorded = ["v", "a_sfa"]
            elif model_name == "lif+std":
                recorded = ["v", "x_std", "xr_std"]
            elif model_name == "lif+cbi":
                recorded = ["v", "h_inh"]
            mon = b.StateMonitor(
                neu, recorded, record=self._trace_idx, name=f"traces_{tag}"
            )
            extra.append(mon)
            self._mon = mon

        objects: list[b.BrianObject] = [neu, syn, spk]
        for pois in bank_pois:
            objects.extend(pois)
        objects.extend(extra)
        self._neu = neu
        self._syn = syn
        self._spk = spk
        self._net = b.Network(*objects)
        self._built = True
        self.store("initial")
        gc.collect()

    def _model_params(self, params: Params, shiu: object) -> dict:
        """Translate the Params store into Brian2 quantities.

        Units: mV, ms, Hz as in section 5. Shapes: scalars only.
        Cross-checks the shared LIF values against the clone's
        default_params and raises on drift.
        """
        get = params.get
        model_params: dict = {
            "v_0": float(get("lif.v_0")) * mV,
            "v_rst": float(get("lif.v_rst")) * mV,
            "v_th": float(get("lif.v_th")) * mV,
            "t_mbr": float(get("lif.t_mbr")) * ms,
            "tau": float(get("lif.tau")) * ms,
            "t_rfc": float(get("lif.t_rfc")) * ms,
            "t_dly": float(get("lif.t_dly")) * ms,
            "w_syn": float(get("lif.w_syn")) * mV,
            "f_poi": float(get("input.f_poi")),
            "eqs": LIF_MODEL,
            "eq_th": LIF_THRESHOLD,
            "eq_rst": LIF_RESET,
        }
        defaults = shiu.default_params  # type: ignore[attr-defined]
        for key, unit in (
            ("v_0", mV),
            ("v_rst", mV),
            ("v_th", mV),
            ("t_mbr", ms),
            ("tau", ms),
            ("t_rfc", ms),
            ("t_dly", ms),
            ("w_syn", mV),
            ("f_poi", 1),
        ):
            if float(defaults[key] / unit) != float(model_params[key] / unit):
                raise ValueError(f"params drift against the Shiu defaults: lif/{key}")
        if float(defaults["r_poi"] / Hz) != float(get("input.r_poi")):
            raise ValueError("params drift against the Shiu defaults: input/r_poi")
        return model_params

    def _check_topology(self, topology: InputTopology) -> None:
        """Validate bank orders, index ranges, and the trace cap.

        Units: none. Shapes: index arrays as declared in base.py.
        Bank index order is never sorted here; extended, spikelist,
        arrays must already be sorted with unique entries; trace order is preserved.
        """
        for bank in topology.upstream_banks:
            if not isinstance(bank, UpstreamBank):
                raise ValueError("upstream_banks must contain UpstreamBank values")
        for name in ("extended_idx", "spikelist_idx", "trace_idx"):
            arr = getattr(topology, name)
            if not isinstance(arr, np.ndarray) or arr.ndim != 1 or arr.dtype != np.int32:
                raise ValueError(f"{name} must be one-dimensional int32")
            if np.any(arr < 0) or len(np.unique(arr)) != len(arr):
                raise ValueError(f"{name} must be nonnegative with unique entries")
            if name != "trace_idx" and np.any(np.diff(arr.astype(np.int64)) <= 0):
                raise ValueError(f"{name} must be sorted")
        if topology.trace_idx.shape[0] > TRACE_MAX:
            raise ValueError(f"trace_idx holds at most {TRACE_MAX} neurons")

    # -- seeding and input -------------------------------------------------

    def seed(self, seed: int) -> None:
        """Seed Brian2 with a uint32 seed. Units: none. Shapes: scalar."""
        if not isinstance(seed, (int, np.integer)) or not 0 <= int(seed) < 2**32:
            raise ValueError(f"seed must be a uint32 integer, got {seed}")
        b.seed(int(seed))

    def set_upstream_active(self, bank: int, active: bool) -> None:
        """Switch one bank through the public active flag.

        Units: none. Shapes: two scalars. The flag is remembered and
        reapplied after every restore.
        """
        self._require_built()
        if not 0 <= bank < len(self._bank_pois):
            raise ValueError(f"unknown bank {bank}")
        for poi in self._bank_pois[bank]:
            poi.active = bool(active)
        self._bank_active[bank] = bool(active)

    def set_input_rates(self, rate_hz: NDArray[np.floating]) -> None:
        """Write extended-mode rates. Units: Hz. Shapes: float array with shape (len(extended_idx),)."""
        self._require_built()
        rates = np.asarray(rate_hz, dtype=np.float64)
        if rates.shape != (self._ext_idx.shape[0],):
            raise ValueError(
                f"rate_hz must have shape ({self._ext_idx.shape[0]},), got {rates.shape}"
            )
        if np.any(rates < 0) or not np.all(np.isfinite(rates)):
            raise ValueError("extended rates must be finite and >= 0")
        if self._ext is None:
            return  # The full rate vector for an absent extended group is empty.
        self._ext.rates = rates * Hz

    def set_spike_list(
        self, idx: NDArray[np.int32], tick: NDArray[np.int64]
    ) -> None:
        """Write deterministic spike lists. Units: engine ticks. Shapes:
        idx int32 with shape (n_events,) subset of spikelist_idx;
        tick int64 with shape (n_events,)."""
        self._require_built()
        if self._gen is None:
            raise RuntimeError("topology declares no spikelist_idx")
        if not isinstance(idx, np.ndarray) or idx.ndim != 1 or idx.dtype != np.int32:
            raise ValueError("idx must be one-dimensional int32")
        idx_a = idx
        if not isinstance(tick, np.ndarray) or tick.ndim != 1 or tick.dtype != np.int64:
            raise ValueError("tick must be one-dimensional int64")
        tick_a = tick
        if idx_a.shape != tick_a.shape or idx_a.ndim != 1:
            raise ValueError("idx and tick must share one shape")
        if idx_a.shape[0] == 0:
            self._gen.set_spikes(np.zeros(0, dtype=np.int32), np.zeros(0) * ms)
            return
        position = {int(v): k for k, v in enumerate(self._gen_idx)}
        try:
            local = np.array([position[int(v)] for v in idx_a], dtype=np.int32)
        except KeyError as exc:
            raise ValueError(f"spike-list index outside spikelist_idx: {exc}") from exc
        if np.any(tick_a < 0):
            raise ValueError("spike-list ticks must be >= 0")
        order = np.argsort(tick_a, kind="stable")
        times = (tick_a[order].astype(np.float64) * self.dt_ms) * ms + self._t0_tick * self.dt_ms * ms
        self._gen.set_spikes(local[order], times)

    # -- parameter writes -------------------------------------------------

    def set_threshold(self, v_th_mv: NDArray[np.floating]) -> None:
        """Write per-neuron thresholds. Units: mV. Shapes: float array with shape (n,)."""
        self._require_built()
        values = np.asarray(v_th_mv, dtype=np.float64)
        if values.shape != (self.n,):
            raise ValueError(f"v_th_mv must have shape ({self.n},), got {values.shape}")
        if not np.all(np.isfinite(values)):
            raise ValueError("thresholds must be finite")
        assert self._neu is not None
        self._neu.v_th_i = values * mV

    def set_gain(self, gain: NDArray[np.floating]) -> None:
        """Write per-neuron gains. Units: dimensionless. Shapes: float array with shape (n,)."""
        self._require_built()
        values = np.asarray(gain, dtype=np.float64)
        if values.shape != (self.n,):
            raise ValueError(f"gain must have shape ({self.n},), got {values.shape}")
        if not np.all(np.isfinite(values)):
            raise ValueError("gains must be finite")
        assert self._neu is not None
        self._neu.gain_i = values

    def set_background(self, w_bg_mv: NDArray[np.floating]) -> None:
        """Write per-neuron background weights. Units: mV. Shapes: float array with shape (n,)."""
        self._require_built()
        values = np.asarray(w_bg_mv, dtype=np.float64)
        if values.shape != (self.n,):
            raise ValueError(f"w_bg_mv must have shape ({self.n},), got {values.shape}")
        if not np.all(np.isfinite(values)):
            raise ValueError("background weights must be finite")
        assert self._neu is not None
        self._neu.w_bg_i = values * mV

    def set_refractory(
        self, idx: NDArray[np.int32], rfc_ms: NDArray[np.floating]
    ) -> None:
        """Write refractory periods of indexed neurons. Units: ms. Shapes:
        idx int32 with shape (k,); rfc_ms float with shape (k,). The base
        array is updated so compose_refractory keeps the values for
        neurons outside active banks."""
        self._require_built()
        if not isinstance(idx, np.ndarray) or idx.ndim != 1 or idx.dtype != np.int32:
            raise ValueError("idx must be one-dimensional int32")
        idx_a = idx
        rfc_a = np.asarray(rfc_ms, dtype=np.float64)
        if idx_a.shape != rfc_a.shape or idx_a.ndim != 1:
            raise ValueError("idx and rfc_ms must share one shape")
        if idx_a.shape[0] and (idx_a.min() < 0 or idx_a.max() >= self.n):
            raise ValueError("refractory indices are out of range")
        if np.any(rfc_a < 0) or not np.all(np.isfinite(rfc_a)):
            raise ValueError("refractory periods must be finite and >= 0")
        proposed = self._rfc_base_ms.copy()
        proposed[idx_a] = rfc_a
        self._guard_depression_latch(proposed)
        self._rfc_base_ms[idx_a] = rfc_a
        assert self._neu is not None
        self._neu.rfc[idx_a] = rfc_a * ms

    def compose_refractory(self) -> None:
        """Write rfc_base everywhere and 0 on active bank targets.

        Units: ms. Shapes: none. A neuron targeted by an active bank
        gets 0 even when it also carries extended or spike-list input.
        """
        self._require_built()
        assert self._neu is not None
        proposed = self._rfc_base_ms.copy()
        for active, idx in zip(self._bank_active, self._bank_idx):
            if active and idx.shape[0]:
                proposed[idx] = 0.0
        self._guard_depression_latch(proposed)
        self._neu.rfc = self._rfc_base_ms * ms
        for active, idx in zip(self._bank_active, self._bank_idx):
            if active and idx.shape[0]:
                self._neu.rfc[idx] = 0.0 * ms

    def disconnect(self, idx: NDArray[np.int32]) -> None:
        """Zero all outgoing weights of indexed neurons. Units: none.
        Shapes: idx int32 with shape (k,). Exposes the upstream silence
        operation under its own name."""
        self._require_built()
        if not isinstance(idx, np.ndarray) or idx.ndim != 1 or idx.dtype != np.int32:
            raise ValueError("idx must be one-dimensional int32")
        idx_a = idx
        if idx_a.ndim != 1:
            raise ValueError("idx must be one-dimensional")
        if idx_a.shape[0] == 0:
            return
        if idx_a.min() < 0 or idx_a.max() >= self.n:
            raise ValueError("disconnect indices are out of range")
        assert self._syn is not None
        pre = np.asarray(self._syn.i[:], dtype=np.int32)
        rows = np.where(np.isin(pre, idx_a))[0]
        self._syn.w[rows] = 0.0 * mV

    def set_weight_scale(self, scale: NDArray[np.floating]) -> None:
        """Scale every connection weight from its base value. Units:
        dimensionless, 1 is unchanged. Shapes: float32 array with shape
        (n_syn,) in connection file order."""
        self._require_built()
        factors = np.asarray(scale, dtype=np.float32)
        if factors.shape != (self.n_syn,):
            raise ValueError(
                f"scale must have shape ({self.n_syn},), got {factors.shape}"
            )
        if not np.all(np.isfinite(factors)):
            raise ValueError("weight scales must be finite")
        assert self._syn is not None
        self._syn.w = (self._base_w_mv * factors.astype(np.float64)) * mV

    # -- inspection helpers (read-only; tests and suites use these) --------

    def thresholds_mv(self) -> NDArray[np.float64]:
        """Return the thresholds the engine holds. Units: mV. Shapes: float array with shape (n,)."""
        self._require_built()
        assert self._neu is not None
        return np.asarray(self._neu.v_th_i[:] / mV, dtype=np.float64)

    def gains(self) -> NDArray[np.float64]:
        """Return the gains the engine holds. Units: dimensionless. Shapes: float array with shape (n,)."""
        self._require_built()
        assert self._neu is not None
        return np.array(self._neu.gain_i[:], dtype=np.float64, copy=True)

    def refractory_ms(self) -> NDArray[np.float64]:
        """Return the refractory periods the engine holds. Units: ms. Shapes: float array with shape (n,)."""
        self._require_built()
        assert self._neu is not None
        return np.asarray(self._neu.rfc[:] / ms, dtype=np.float64)

    def bank_active_flags(self) -> list[bool]:
        """Return one activity flag per bank. Units: none. Shapes: list of length n_banks."""
        self._require_built()
        return list(self._bank_active)

    # -- stepping, state, and record --------------------------------------

    def run_chunk(self, ms: float) -> ChunkResult:
        """Advance the network and return per-chunk counts. Units: ms in,
        counts in spikes. Shapes: ChunkResult with counts shape (n,) and
        hist_1ms shape ((tick1-tick0)//ticks_per_ms,). Chunk boundaries
        must fall on 1 ms boundaries."""
        self._require_built()
        duration_ms = float(ms)
        if duration_ms <= 0 or not np.isfinite(duration_ms):
            raise ValueError(f"chunk duration must be positive, got {ms}")
        ticks = int(round(duration_ms / self.dt_ms))
        if abs(ticks * self.dt_ms - duration_ms) > 1e-9:
            raise ValueError(f"chunk duration must be a multiple of dt, got {ms}")
        if ticks % self.ticks_per_ms != 0:
            raise ValueError(f"chunk boundaries must fall on 1 ms boundaries, got {ms}")
        assert self._net is not None and self._spk is not None
        count_before = np.asarray(self._spk.count[:], dtype=np.int64).copy()
        total_before = int(count_before.sum())
        tick0 = self.tick()
        self._net.run(duration_ms * b.ms)
        tick1 = self.tick()
        count_after = np.asarray(self._spk.count[:], dtype=np.int64)
        counts = (count_after - count_before).astype(np.int32)
        new_total = int(count_after.sum()) - total_before
        # Slice before unit conversion: reading the entire growing monitor on
        # every chunk makes recording cost quadratic in probe duration.
        new_t = np.asarray(self._spk.t[total_before:] / second, dtype=np.float64)
        new_ticks = np.rint(new_t * 1000.0 / self.dt_ms).astype(np.int64) - self._t0_tick
        width = (tick1 - tick0) // self.ticks_per_ms
        hist = np.zeros(width, dtype=np.int32)
        if new_total:
            bins = (new_ticks - tick0) // self.ticks_per_ms
            if np.any(bins < 0) or np.any(bins >= width):
                raise RuntimeError("spike ticks fall outside the chunk window")
            hist = np.bincount(bins, minlength=width).astype(np.int32)
        h_max = None
        if self._engine_model_name == "lif+cbi":
            assert self._neu is not None
            h_max = float(np.max(np.asarray(self._neu.h_inh[:], dtype=np.float64)))
        return ChunkResult(
            tick0=tick0, tick1=tick1, counts=counts, hist_1ms=hist, h_max=h_max
        )

    def tick(self) -> int:
        """Return engine ticks since the last build or restore. Units: ticks. Shapes: scalar."""
        self._require_built()
        assert self._net is not None
        now_s = float(self._net.t / second)
        return int(round(now_s * 1000.0 / self.dt_ms)) - self._t0_tick

    def _snapshot_path(self, key: str) -> Path:
        """Return the file-backed Brian2 snapshot path for one key.

        Units: none. Shapes: one path under the cache dir, unique per process.
        """
        directory = engine_store_dir()
        return directory / f"{id(self)}_{key}.pkl"

    def _snapshot_weight_path(self, key: str) -> Path:
        """Return the npy path for synapse weights of one snapshot key."""
        return self._snapshot_path(key).with_name(f"{id(self)}_{key}_w.npy")

    def store(self, key: str) -> None:
        """File-back network state; synapse i/j stay live (they do not change).

        Units: none. Shapes: scalar key; refractory base has shape (n,).
        Synapse weights go to a sidecar npy so pickle does not copy 121 MB.
        """
        self._require_built()
        assert self._net is not None
        from brian2.core.network import _get_all_objects
        from brian2.devices.device import get_device

        clocks = {obj.clock for obj in _get_all_objects(self._net.objects)}
        for clock in clocks:
            clock._set_t_update_dt(target_t=self._net.t)
        state = self._net._full_state()
        state["_random_generator_state"] = get_device().get_random_state()
        path = self._snapshot_path(key)
        weight_path = self._snapshot_weight_path(key)
        if self._syn is not None:
            payload = state.get(self._syn.name)
            if isinstance(payload, dict):
                for name in ("i", "j", "_synaptic_pre", "_synaptic_post"):
                    payload.pop(name, None)
                w_entry = payload.pop("w", None)
                if w_entry is not None:
                    values, _size = w_entry
                    temporary_w = weight_path.with_suffix(weight_path.suffix + ".tmp")
                    with temporary_w.open("wb") as handle:
                        np.save(handle, np.ascontiguousarray(values, dtype=np.float64))
                    temporary_w.replace(weight_path)
                    del values
        temporary = path.with_suffix(path.suffix + ".tmp")
        with temporary.open("wb") as handle:
            pickle.dump({key: state}, handle, protocol=pickle.HIGHEST_PROTOCOL)
        temporary.replace(path)
        del state
        self._net._stored_state.pop(key, None)
        if not self._store_files:
            weakref.finalize(self, _remove_files, self._store_paths)
        self._store_paths.extend(p for p in (path, weight_path) if p not in self._store_paths)
        self._store_files[key] = path
        self._store_t0[key] = int(round(float(self._net.t / second) * 1000.0 / self.dt_ms))
        self._store_rfc_base[key] = self._rfc_base_ms.copy()
        gc.collect()

    def restore(self, key: str) -> None:
        """Restore state and refractory base, then reapply bank activity.
        Units: none. Shapes: scalar key; refractory base has shape (n,)."""
        self._require_built()
        if key not in self._store_t0 or key not in self._store_files:
            raise ValueError(f"unknown store key: {key}")
        assert self._net is not None
        self._net.restore(key, filename=str(self._store_files[key]), restore_random_state=True)
        weight_path = self._snapshot_weight_path(key)
        if weight_path.is_file() and self._syn is not None:
            self._syn.variables["w"].set_value(load_npy(weight_path))
        self._t0_tick = self._store_t0[key]
        self._rfc_base_ms = self._store_rfc_base[key].copy()
        for active, pois in zip(self._bank_active, self._bank_pois):
            for poi in pois:
                poi.active = bool(active)

    def spikes(self, since_tick: int) -> SpikeTable:
        """Return all spikes at engine ticks >= since_tick. Units: engine
        ticks. Shapes: SpikeTable with idx shape (n_spikes,) and tick
        shape (n_spikes,)."""
        self._require_built()
        assert self._spk is not None
        idx = np.asarray(self._spk.i[:], dtype=np.int32)
        t_s = np.asarray(self._spk.t[:] / second, dtype=np.float64)
        ticks = np.rint(t_s * 1000.0 / self.dt_ms).astype(np.int64) - self._t0_tick
        keep = ticks >= int(since_tick)
        return SpikeTable(idx=idx[keep], tick=ticks[keep])

    def traces(self, since_tick: int) -> TraceTable:
        """Return membrane traces at engine ticks >= since_tick. Units: mV
        and engine ticks. Shapes: TraceTable with idx shape (m,), tick
        shape (n_time,), v_mv shape (m, n_time)."""
        ticks, keep = self._trace_keep(since_tick)
        assert self._mon is not None
        values = np.asarray(self._mon.v[:, keep] / mV, dtype=np.float64)
        return TraceTable(
            idx=self._trace_idx.copy(), tick=ticks, v_mv=values
        )

    def engine_model(self) -> str:
        """Return the built variant name. Units: none. Shapes: one of lif, lif+sfa, lif+std, lif+cbi."""
        self._require_built()
        return self._engine_model_name

    def model_strings(self) -> tuple[str, str, str, str]:
        """Return the model, threshold, reset and on_pre strings passed to Brian2.

        Units: none. Shapes: four strings.
        """
        self._require_built()
        if self._passed_model_strings is None:
            raise RuntimeError("engine is not built")
        return self._passed_model_strings

    def method(self) -> str:
        """Return the Brian2 integration method. Units: none. Shapes: linear or rk4."""
        self._require_built()
        return self._method_name

    def mechanism_traces(self, since_tick: int) -> MechanismTraceTable:
        """Return mechanism traces on the tick grid of traces(since_tick).

        Units: as MechanismTraceTable. Shapes: columns (len(trace_idx), n_ticks).
        Under lif the table has no columns and no mechanism monitor exists.
        """
        self._require_built()
        ticks, keep = self._trace_keep(since_tick)
        idx = self._trace_idx.copy()
        if self._engine_model_name == "lif":
            return MechanismTraceTable(idx=idx, tick=ticks)
        if self._engine_model_name == "lif+sfa":
            assert self._mon is not None
            values = np.asarray(self._mon.a_sfa[:, keep] / mV, dtype=np.float64)
            return MechanismTraceTable(idx=idx, tick=ticks, a_sfa_mv=values)
        if self._engine_model_name == "lif+std":
            assert self._mon is not None
            x_std = np.asarray(self._mon.x_std[:, keep], dtype=np.float64)
            xr_std = np.asarray(self._mon.xr_std[:, keep], dtype=np.float64)
            return MechanismTraceTable(idx=idx, tick=ticks, x_std=x_std, xr_std=xr_std)
        if self._engine_model_name == "lif+cbi":
            assert self._mon is not None
            values = np.asarray(self._mon.h_inh[:, keep], dtype=np.float64)
            return MechanismTraceTable(idx=idx, tick=ticks, h_inh=values)
        raise ValueError(f"mechanism traces are not implemented for {self._engine_model_name}")

    def _guard_depression_latch(self, rfc_ms: NDArray[np.float64]) -> None:
        """Raise when a depressed neuron would have rfc below lif.t_dly."""
        if self._engine_model_name != "lif+std" or self._U_std.shape[0] != rfc_ms.shape[0]:
            return
        if np.any((self._U_std > 0.0) & (rfc_ms < self._t_dly_ms)):
            raise ValueError("depression latch: refractory period below lif.t_dly")

    def _trace_keep(self, since_tick: int) -> tuple[NDArray[np.int64], NDArray[np.bool_]]:
        """Return monitor ticks at or after since_tick, and the keep mask."""
        self._require_built()
        if self._mon is None:
            raise RuntimeError("topology declares no trace_idx")
        t_s = np.asarray(self._mon.t[:] / second, dtype=np.float64)
        ticks = np.rint(t_s * 1000.0 / self.dt_ms).astype(np.int64) - self._t0_tick
        keep = ticks >= int(since_tick)
        return ticks[keep], keep

    # -- internals ---------------------------------------------------------

    def _require_built(self) -> None:
        """Raise when the engine is used before build. Units: none. Shapes: none."""
        if not self._built:
            raise RuntimeError("engine is not built")
