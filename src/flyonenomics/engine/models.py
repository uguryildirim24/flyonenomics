"""Engine model-variant strings and the Mechanisms object (SPEC-P2 2.2.4).

The lif strings are the bytes recorded in tests/fixtures/wp24-off-reference.json.
The SPEC-P2 listing of lif documents them and takes no part in any test.
The lif+sfa, lif+std and lif+cbi strings are the SPEC-P2 2.2.4 listings, joined as specified.
"""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np
from numpy.typing import NDArray


LIF_MODEL = (
    "dv/dt = (v_0 - v + g) / t_mbr : volt (unless refractory)\n"
    "dg/dt = -g / tau : volt (unless refractory)\n"
    "rfc : second\n"
    "v_th_i : volt\n"
    "gain_i : 1\n"
    "w_bg_i : volt\n"
)
LIF_THRESHOLD = "v > v_th_i"
LIF_RESET = "v = v_rst; w = 0; g = 0 * mV"
LIF_ON_PRE = "g += w * gain_i_post"
LIF_METHOD = "linear"

SFA_MODEL = (
    "dv/dt = (v_0 - v + g - a_sfa) / t_mbr : volt (unless refractory)\n"
    "dg/dt = -g / tau : volt (unless refractory)\n"
    "da_sfa/dt = -a_sfa / tau_sfa_i : volt (unless refractory)\n"
    "rfc : second\n"
    "v_th_i : volt\n"
    "gain_i : 1\n"
    "w_bg_i : volt\n"
    "b_sfa_i : volt (constant)\n"
    "tau_sfa_i : second (constant)\n"
)
SFA_RESET = "v = v_rst; w = 0; g = 0 * mV; a_sfa += b_sfa_i"
SFA_THRESHOLD = LIF_THRESHOLD
SFA_ON_PRE = LIF_ON_PRE
SFA_METHOD = LIF_METHOD

STD_MODEL = (
    "dv/dt = (v_0 - v + g) / t_mbr : volt (unless refractory)\n"
    "dg/dt = -g / tau : volt (unless refractory)\n"
    "dx_std/dt = (1 - x_std) / tau_std_i : 1\n"
    "rfc : second\n"
    "v_th_i : volt\n"
    "gain_i : 1\n"
    "w_bg_i : volt\n"
    "xr_std : 1\n"
    "U_std_i : 1 (constant)\n"
    "tau_std_i : second (constant)\n"
)
STD_RESET = "v = v_rst; w = 0; g = 0 * mV; xr_std = x_std; x_std = xr_std * (1 - U_std_i)"
STD_THRESHOLD = LIF_THRESHOLD
STD_ON_PRE = "g += w * gain_i_post * xr_std_pre"
STD_METHOD = LIF_METHOD

CBI_MODEL = (
    "dv/dt = (v_0 - v + g + h_inh * (E_inh - v)) / t_mbr : volt (unless refractory)\n"
    "dg/dt = -g / tau : volt (unless refractory)\n"
    "dh_inh/dt = -h_inh / tau : 1 (unless refractory)\n"
    "rfc : second\n"
    "v_th_i : volt\n"
    "gain_i : 1\n"
    "w_bg_i : volt\n"
)
CBI_RESET = "v = v_rst; w = 0; g = 0 * mV; h_inh = 0"
CBI_THRESHOLD = LIF_THRESHOLD
CBI_ON_PRE = "g += w * gain_i_post * int(w > 0 * mV); h_inh += -w * gain_i_post * int(w < 0 * mV) / dV_inh"
CBI_METHOD = "rk4"


@dataclass(frozen=True, slots=True)
class Adaptation:
    """Per-neuron spike-frequency adaptation arrays (SPEC-P2 2.2.4).

    Units: b_mv in mV, tau_ms in ms. Shapes: both (n,) float64.
    """

    b_mv: NDArray[np.float64]
    tau_ms: NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class Depression:
    """Per-neuron short-term depression arrays (SPEC-P2 2.2.4).

    Units: U dimensionless, tau_ms in ms. Shapes: both (n,) float64.
    """

    U: NDArray[np.float64]
    tau_ms: NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class ConductanceInhibition:
    """Conductance-based inhibition reversal (SPEC-P2 2.2.4).

    Units: E_inh_mv in mV. Shapes: scalar.
    """

    E_inh_mv: float


@dataclass(frozen=True, slots=True)
class Mechanisms:
    """Resolved mechanism blocks passed to Engine.build (SPEC-P2 2.2.4).

    Units: per-neuron arrays live on a non-null block when that variant
    is built. Shapes: an absent Mechanisms, or every block None, is
    variant lif. At most one block may be non-null.
    """

    adaptation: Adaptation | None = None
    depression: Depression | None = None
    conductance_inhibition: ConductanceInhibition | None = None


def resolve_engine_model(mechanisms: Mechanisms | None) -> str:
    """Name the engine variant from a Mechanisms object or None.

    Units: none. Shapes: one of lif, lif+sfa, lif+std, lif+cbi.
    """
    if mechanisms is None:
        return "lif"
    if not isinstance(mechanisms, Mechanisms):
        raise TypeError("mechanisms must be Mechanisms or None")
    n_on = sum(
        block is not None
        for block in (
            mechanisms.adaptation,
            mechanisms.depression,
            mechanisms.conductance_inhibition,
        )
    )
    if n_on == 0:
        return "lif"
    if n_on > 1:
        raise ValueError("at most one mechanism block may be non-null")
    if mechanisms.adaptation is not None:
        if not isinstance(mechanisms.adaptation, Adaptation):
            raise TypeError("adaptation must be Adaptation")
        return "lif+sfa"
    if mechanisms.depression is not None:
        if not isinstance(mechanisms.depression, Depression):
            raise TypeError("depression must be Depression")
        return "lif+std"
    if mechanisms.conductance_inhibition is not None:
        if not isinstance(mechanisms.conductance_inhibition, ConductanceInhibition):
            raise TypeError("conductance_inhibition must be ConductanceInhibition")
        return "lif+cbi"
    raise ValueError("unresolved mechanisms variant")


def lif_strings() -> tuple[str, str, str, str]:
    """Return the lif model, threshold, reset and on_pre strings.

    Units: none. Shapes: four strings, the same bytes passed to Brian2.
    """
    return (LIF_MODEL, LIF_THRESHOLD, LIF_RESET, LIF_ON_PRE)


def sfa_strings() -> tuple[str, str, str, str]:
    """Return the lif+sfa model, threshold, reset and on_pre strings.

    Units: none. Shapes: four strings, the same bytes passed to Brian2.
    """
    return (SFA_MODEL, SFA_THRESHOLD, SFA_RESET, SFA_ON_PRE)


def std_strings() -> tuple[str, str, str, str]:
    """Return the lif+std model, threshold, reset and on_pre strings.

    Units: none. Shapes: four strings, the same bytes passed to Brian2.
    """
    return (STD_MODEL, STD_THRESHOLD, STD_RESET, STD_ON_PRE)


def cbi_strings() -> tuple[str, str, str, str]:
    """Return the lif+cbi model, threshold, reset and on_pre strings.

    Units: none. Shapes: four strings, the same bytes passed to Brian2.
    """
    return (CBI_MODEL, CBI_THRESHOLD, CBI_RESET, CBI_ON_PRE)
