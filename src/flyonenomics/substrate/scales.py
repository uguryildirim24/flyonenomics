"""Per-row synaptic scales for the rest substrate (SPEC-P2 section 2.2.1)."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

CLASS_NAMES: tuple[str, ...] = ("ACh", "Glu", "GABA", "His", "mod", "unk")
INHIBITORY_CLASSES: frozenset[str] = frozenset({"Glu", "GABA", "His"})
EXCITATORY_CLASSES: frozenset[str] = frozenset({"ACh", "mod"})


def scale_array(
    classes: NDArray[np.str_],
    s_pq: NDArray[np.floating],
    pre: NDArray[np.integer],
    g_glu: float,
    g_gaba: float,
    *,
    g_his: float = 1.0,
    optic_exemption: bool = False,
    super_class: NDArray[np.str_] | None = None,
    g_gaba_kc: float = 1.0,
    post: NDArray[np.integer] | None = None,
    kc_mask: NDArray[np.integer] | None = None,
) -> NDArray[np.float32]:
    """Compose per-row synaptic scales for Engine.set_weight_scale.

    Units: classes and super_class are transmitter and annotation
    labels; s_pq is the connection-file sign (the Excitatory column,
    ±1, dimensionless); g_glu, g_gaba, g_his, and g_gaba_kc are
    dimensionless ratios; the return is dimensionless float32. Shapes:
    classes (n,) in engine order; s_pq (n_syn,) and pre (n_syn,) in
    connection-file order, with pre[k] the engine index of the
    presynaptic neuron of row k; post (n_syn,) the postsynaptic engine
    index when g_gaba_kc is not 1; kc_mask (n,) uint8, 1 on Kenyon
    cells; super_class (n,) in engine order when optic_exemption is
    true; return float32 (n_syn,) in connection-file order, the order
    set_weight_scale takes.

    For row k with presynaptic neuron j = pre[k]:

        scale_k = (s_cur(j) / s_pq[k]) * g(c(j))

    s_cur is −1 for Glu, GABA, and His, +1 for ACh and mod, and the
    connection-file sign for unk. g(Glu) = g_glu, g(GABA) = g_gaba,
    g(His) = g_his (default 1), g(ACh) = g(mod) = 1, and g(unk) is 1
    when s_pq[k] > 0 else g_gaba. After that, g_gaba_kc multiplies GABA
    rows whose postsynaptic neuron is a KC (SPEC-P2 2.2.4 3d). Engine
    weights become `_base_w_mv × scale`. When optic_exemption is true,
    g_gaba and g_glu do not apply to presynaptic super_class optic
    rows; curated signs still apply. g_gaba_kc 1 is byte-identical to
    omitting the factor.
    """
    class_of = np.asarray(classes)
    signs = np.asarray(s_pq, dtype=np.float64)
    pre_idx = np.asarray(pre)
    if class_of.ndim != 1 or signs.ndim != 1 or pre_idx.ndim != 1:
        raise ValueError("classes, s_pq, and pre must be one-dimensional")
    if pre_idx.shape != signs.shape:
        raise ValueError("s_pq and pre must have the same length")
    if not np.issubdtype(signs.dtype, np.number) or not np.all(np.isfinite(signs)):
        raise ValueError("s_pq must be a finite numeric vector")
    if np.any(signs == 0):
        raise ValueError("s_pq must be nonzero")
    if np.any(np.abs(signs) != 1):
        raise ValueError("s_pq must be ±1")
    for name, value in (("g_glu", g_glu), ("g_gaba", g_gaba), ("g_his", g_his)):
        if not np.isfinite(value) or value < 0:
            raise ValueError(f"{name} must be finite and nonnegative")
    if not np.isfinite(g_gaba_kc) or g_gaba_kc < 1:
        raise ValueError("g_gaba_kc must be finite and at least 1")
    n_syn = int(signs.shape[0])
    n = int(class_of.shape[0])
    if n_syn and (int(pre_idx.min(initial=0)) < 0 or int(pre_idx.max(initial=0)) >= n):
        raise ValueError("pre indices are out of range")
    labels = np.asarray(class_of[pre_idx], dtype=str)
    inhibitory = np.isin(labels, tuple(INHIBITORY_CLASSES))
    excitatory = np.isin(labels, tuple(EXCITATORY_CLASSES))
    unknown = labels == "unk"
    if not np.all(inhibitory | excitatory | unknown):
        raise ValueError("classes must be ACh, Glu, GABA, His, mod, or unk")
    s_cur = np.empty(n_syn, dtype=np.float64)
    s_cur[inhibitory] = -1.0
    s_cur[excitatory] = 1.0
    s_cur[unknown] = signs[unknown]
    gain = np.ones(n_syn, dtype=np.float64)
    gain[labels == "Glu"] = float(g_glu)
    gain[labels == "GABA"] = float(g_gaba)
    gain[labels == "His"] = float(g_his)
    gain[unknown & (signs < 0)] = float(g_gaba)
    if optic_exemption:
        if super_class is None:
            raise ValueError("optic_exemption requires super_class")
        groups = np.asarray(super_class)
        if groups.shape != class_of.shape:
            raise ValueError("super_class must match classes")
        optic = np.asarray(groups[pre_idx], dtype=str) == "optic"
        gain[optic & np.isin(labels, ("Glu", "GABA"))] = 1.0
        gain[optic & unknown & (signs < 0)] = 1.0
    if float(g_gaba_kc) != 1.0:
        if post is None or kc_mask is None:
            raise ValueError("g_gaba_kc other than 1 requires post and kc_mask")
        post_idx = np.asarray(post)
        mask = np.asarray(kc_mask)
        if post_idx.ndim != 1 or post_idx.shape != signs.shape:
            raise ValueError("post must match s_pq")
        if mask.ndim != 1 or int(mask.shape[0]) != n:
            raise ValueError("kc_mask must match classes")
        if n_syn and (int(post_idx.min(initial=0)) < 0 or int(post_idx.max(initial=0)) >= n):
            raise ValueError("post indices are out of range")
        gaba_to_kc = (labels == "GABA") & (np.asarray(mask[post_idx]) != 0)
        gain[gaba_to_kc] *= float(g_gaba_kc)
    return np.asarray((s_cur / signs) * gain, dtype=np.float32)
