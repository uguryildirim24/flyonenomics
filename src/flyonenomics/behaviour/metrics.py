"""Buridan trajectory scoring, with CeTrAn v.4 geometry and freeze semantics."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from flyonenomics.types import Params, load_params


def wrap(angle: float | NDArray[np.float64]) -> Any:
    """Wrap degrees to (-180, 180]; scalar or array of any shape."""
    a = (np.asarray(angle) + 180.0) % 360.0 - 180.0
    return np.where(a <= -180.0, 180.0, a)


@dataclass(frozen=True)
class Geometry:
    """Arena geometry from CeTrAn `functions.r:create.env.vars`; radii mm, azimuths degrees (n_stripes,)."""

    platform_mm: float
    wall_mm: float
    stripe_azimuths_deg: tuple[float, ...]

    @classmethod
    def from_params(cls, params: Params | None = None) -> Geometry:
        """Read radii (mm) and stripe azimuths (degrees) from Params."""
        p = params or load_params()
        return cls(p.get("arena.R_platform"), p.get("arena.R_wall"), tuple(p.get("arena.stripe_azimuths")))


def resample(table: pd.DataFrame, hz: float) -> pd.DataFrame:
    """Interpolate each segment to Hz grid; CeTrAn `set.sampling.rate`, output t_s/x_mm/y_mm/segment (n,)."""
    rows: list[pd.DataFrame] = []
    for segment, part in table.groupby("segment", sort=False):
        t = part.t_s.to_numpy(dtype=float)
        xy = part[["x_mm", "y_mm"]].to_numpy(dtype=float)
        if len(t) < 2:
            continue
        # CeTrAn begins at the first grid tick strictly after the first sample.
        first = np.floor(t[0] * hz + 1e-9) + 1
        last = np.floor(t[-1] * hz + 1e-9)
        grid = np.arange(first, last + 1) / hz
        if len(grid) < 2:
            continue
        rows.append(pd.DataFrame({"t_s": grid, "x_mm": np.interp(grid, t, xy[:, 0]),
                                  "y_mm": np.interp(grid, t, xy[:, 1]), "segment": segment}))
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=["t_s", "x_mm", "y_mm", "segment"])


def mindistkeep3(points: NDArray[np.float64], lo: float, hi: float) -> NDArray[np.float64]:
    """Freeze mm points (n,2); literal CeTrAn v.4 `utils.r:mindistkeep3` output (n,2)."""
    p = np.asarray(points, dtype=float)
    if p.ndim != 2 or p.shape[1] != 2:
        raise ValueError("points must have shape (n, 2)")
    n = len(p)
    if n == 0:
        return p.copy()
    d = np.linalg.norm(np.diff(p, axis=0), axis=1)
    kept = np.empty(n, dtype=int)
    kept[0] = 0
    for i in range(1, n):
        if d[i - 1] < lo or d[i - 1] > hi:
            kept[i] = kept[i - 1]
            if d[i - 1] < lo and i < n - 1:
                d[i] = np.linalg.norm(p[i + 1] - p[kept[i]])
        else:
            kept[i] = i
    return p[kept]


def _walks(points: NDArray[np.float64], geometry: Geometry, fraction: float) -> int:
    """Count stripe-area traversals; CeTrAn v.4 `functions.r:c.nwalks`, mm points (n,2)."""
    az = np.deg2rad(geometry.stripe_azimuths_deg)
    directions = np.column_stack((np.sin(az), np.cos(az)))
    in_area = points @ directions.T > fraction * geometry.platform_mm
    last: int | None = None
    between = True
    count = 0
    for flags in in_area:
        if not flags.any():
            between = True
        elif between:
            candidates = np.flatnonzero(flags)
            chosen = next((int(c) for c in candidates if c != last), None)
            if chosen is not None:
                if last is not None:
                    count += 1
                last = chosen
                # CeTrAn keeps in_btw true when only the previously entered
                # (masked) area is visited again; only a new area clears it.
                between = False
    return count


def score_unit(table: pd.DataFrame, geometry: Geometry, params: Params | None = None,
               *, step_min_mm: float | None = None, episodes: pd.DataFrame | None = None) -> dict[str, Any]:
    """Score one 10-Hz observation unit (n,4); angles degrees, counts and fractions.

    Step direction and wall-centre target deviation transcribe CeTrAn v.4
    `functions.r:c.angle.dev`; per-fly median deviation follows
    `scripts/angledev.r`. Walks use `functions.r:c.nwalks` via `_walks`.
    FI, activity and switch rate are this project's additions on those steps.
    """
    p = params or load_params()
    lo = p.get("metrics.step_min_mm") if step_min_mm is None else step_min_mm
    hi = p.get("metrics.step_max_mm")
    fix = p.get("metrics.fix_angle")
    total = defined = walks = 0
    deviations: list[float] = []
    step_rows: list[tuple[float, float, float, float, float, bool]] = []
    stripe_az = np.deg2rad(geometry.stripe_azimuths_deg)
    centres = geometry.wall_mm * np.column_stack((np.sin(stripe_az), np.cos(stripe_az)))
    for _, segment in table.groupby("segment", sort=False):
        pts = mindistkeep3(segment[["x_mm", "y_mm"]].to_numpy(dtype=float), lo, hi)
        if not len(pts):
            continue
        walks += _walks(pts, geometry, p.get("metrics.walk_area_fraction"))
        delta = np.diff(pts, axis=0)
        times = segment.t_s.to_numpy(dtype=float)
        for i, step in enumerate(delta):
            total += 1
            ok = bool(np.linalg.norm(step) > 0)
            step_rows.append((times[i], pts[i, 0], pts[i, 1], step[0], step[1], ok))
            if not ok:
                continue
            defined += 1
            direction = np.rad2deg(np.arctan2(step[0], step[1]))
            targets = centres - pts[i]
            target_az = np.rad2deg(np.arctan2(targets[:, 0], targets[:, 1]))
            deviations.append(float(np.min(np.abs(wrap(direction - target_az)))))
    result: dict[str, Any] = {
        "stripe_deviation_deg": float(np.median(deviations)) if deviations else None,
        "fixation_index": float(np.mean(np.asarray(deviations) < fix)) if deviations else None,
        "angular_denominator": defined,
        "defined_steps": defined,
        "total_steps": total,
        "activity": defined / total if total else 0.0,
        "walks": walks,
        "switches": 0, "valid_switch_windows": 0, "invalid_switch_windows": 0,
        "switch_rate": None,
    }
    if episodes is not None:
        for episode in episodes.to_dict("records"):
            start = float(episode["onset_s"])
            end = start + p.get("metrics.switch_window_s")
            rows = [r for r in step_rows if start <= r[0] < end]
            valid = [r for r in rows if r[5]]
            if not rows or len(valid) < len(rows) / 2:
                result["invalid_switch_windows"] += 1
                continue
            result["valid_switch_windows"] += 1
            midpoint = start + (end - start) / 2
            halves = [[r for r in valid if (r[0] < midpoint) == first] for first in (True, False)]
            if not halves[0] or not halves[1]:
                result["invalid_switch_windows"] += 1
                result["valid_switch_windows"] -= 1
                continue
            means = [float(np.rad2deg(np.arctan2(
                sum(r[3] / np.hypot(r[3], r[4]) for r in half),
                sum(r[4] / np.hypot(r[3], r[4]) for r in half)))) for half in halves]
            onset = min(step_rows, key=lambda r: abs(r[0] - start))
            az = np.deg2rad(float(episode["azimuth_deg"]))
            target = np.rad2deg(np.arctan2(geometry.wall_mm * np.sin(az) - onset[1], geometry.wall_mm * np.cos(az) - onset[2]))
            if abs(wrap(means[0] - target)) - abs(wrap(means[1] - target)) > p.get("metrics.switch_angle"):
                result["switches"] += 1
        if result["valid_switch_windows"]:
            result["switch_rate"] = result["switches"] / result["valid_switch_windows"]
    return result


def score(table: pd.DataFrame, geometry: Geometry, params: Params | None = None, *, mode: str = "window",
          step_min_mm: float | None = None, episodes: pd.DataFrame | None = None) -> dict[str, Any]:
    """Score trajectory t_s/x_mm/y_mm/segment (n,) in full or 20-s window mode; returns per-fly medians and denominators."""
    p = params or load_params()
    sampled = resample(table, p.get("metrics.resample_hz"))
    if mode == "full":
        return score_unit(sampled, geometry, p, step_min_mm=step_min_mm, episodes=episodes)
    if mode != "window":
        raise ValueError("mode must be full or window")
    if sampled.empty:
        return {"windows": [], "valid_windows": 0, "total_windows": 0,
                "stripe_deviation_deg": None, "fixation_index": None, "walks": 0,
                "activity": 0.0, "angular_denominator": 0, "defined_steps": 0, "total_steps": 0,
                "switches": 0, "valid_switch_windows": 0, "invalid_switch_windows": 0, "switch_rate": None}
    duration = p.get("buridan.duration_s")
    origin = float(table.t_s.iloc[0])
    windows: list[dict[str, Any]] = []
    for index in range(int(np.floor((sampled.t_s.max() - origin) / duration)) + 1):
        part = sampled[(sampled.t_s >= origin + index * duration) & (sampled.t_s < origin + (index + 1) * duration)]
        if part.empty:
            continue
        unit_episodes = (episodes[(episodes.onset_s >= origin + index * duration) &
                                  (episodes.onset_s < origin + (index + 1) * duration)]
                         if episodes is not None else None)
        entry = score_unit(part, geometry, p, step_min_mm=step_min_mm, episodes=unit_episodes)
        entry["index"] = index
        entry["valid"] = bool(entry["total_steps"] and entry["activity"] >= p.get("metrics.min_window_fraction"))
        windows.append(entry)
    valid = [w for w in windows if w["valid"]]
    switches = sum(w["switches"] for w in windows)
    valid_switch_windows = sum(w["valid_switch_windows"] for w in windows)
    invalid_switch_windows = sum(w["invalid_switch_windows"] for w in windows)
    def median(key: str) -> float | None:
        values = [w[key] for w in valid if w[key] is not None]
        return float(np.median(values)) if values else None
    return {"windows": windows, "valid_windows": len(valid), "total_windows": len(windows),
            "stripe_deviation_deg": median("stripe_deviation_deg"), "fixation_index": median("fixation_index"),
            "walks": median("walks") if valid else 0, "activity": median("activity") if valid else 0.0,
            "angular_denominator": sum(w["angular_denominator"] for w in valid),
            "defined_steps": sum(w["defined_steps"] for w in valid), "total_steps": sum(w["total_steps"] for w in valid),
            "switches": switches, "valid_switch_windows": valid_switch_windows,
            "invalid_switch_windows": invalid_switch_windows,
            "switch_rate": switches / valid_switch_windows if valid_switch_windows else None}


STEER_GAIN_AZIMUTH_MAX_DEG = 60.0  # SPEC-P2 section 3.5.
BOOTSTRAP_QUANTILES = (0.025, 0.975)


def bias_corrected_delta(rate_right_hz: float, rate_left_hz: float, bias_hz: float = 0.0) -> float:
    """Return (r_R − r_L) − bias. Units: Hz. Shapes: scalars."""
    return (float(rate_right_hz) - float(rate_left_hz)) - float(bias_hz)


def steer_gain(azimuths_deg: NDArray[np.floating] | list[float],
               delta_hz: NDArray[np.floating] | list[float], *,
               bias_hz: float = 0.0, max_azimuth_deg: float = STEER_GAIN_AZIMUTH_MAX_DEG) -> float:
    """Least-squares slope of bias-corrected Δsteer against azimuth. Units: Hz per degree.

    Stripe blocks with |azimuth| > max_azimuth_deg are dropped. Shapes: (n,).
    """
    azimuth = np.asarray(azimuths_deg, dtype=float)
    delta = np.asarray(delta_hz, dtype=float) - float(bias_hz)
    if azimuth.shape != delta.shape or azimuth.ndim != 1:
        raise ValueError("azimuths and deltas must be one-dimensional and the same length")
    keep = np.abs(azimuth) <= float(max_azimuth_deg)
    azimuth = azimuth[keep]
    delta = delta[keep]
    if len(azimuth) < 2:
        raise ValueError("steer_gain needs at least two stripe blocks with |azimuth| <= 60")
    design = np.column_stack((azimuth, np.ones(len(azimuth))))
    slope, _intercept = np.linalg.lstsq(design, delta, rcond=None)[0]
    return float(slope)


def bootstrap_mean_interval(values: NDArray[np.floating] | list[float], rng: np.random.Generator,
                            n: int) -> dict[str, Any]:
    """Mean and 95 percent bootstrap interval of a seed sample. Units: per values.

    Shapes: values (n_seed,), interval of two floats. ANALYSIS supplies rng.
    """
    sample = np.asarray(values, dtype=float)
    if sample.ndim != 1 or len(sample) < 1:
        raise ValueError("bootstrap needs a one-dimensional sample")
    if n < 1:
        raise ValueError("bootstrap_n must be positive")
    mean = float(sample.mean())
    draws = rng.choice(sample, size=(n, len(sample)), replace=True).mean(axis=1)
    lo, hi = (float(x) for x in np.quantile(draws, BOOTSTRAP_QUANTILES))
    return {"mean": mean, "ci95": [lo, hi], "n": int(len(sample))}


def interval_excludes_zero(ci95: list[float] | tuple[float, float]) -> bool:
    """True when a closed interval lies entirely above or below zero. Units: per interval."""
    lo, hi = float(ci95[0]), float(ci95[1])
    if lo > hi:
        lo, hi = hi, lo
    return lo > 0.0 or hi < 0.0


def fixation_retention(table: pd.DataFrame, geometry: Geometry, params: Params | None = None, *,
                       onset_s: float, duration_s: float, step_min_mm: float | None = None) -> dict[str, Any]:
    """Window-mode FI during the distractor episode minus FI on [0, onset). Fractions.

    The pre-episode window can be shorter than buridan.duration_s. Shapes: one table (n,).
    """
    p = params or load_params()
    pre = table[table.t_s < float(onset_s)]
    during = table[(table.t_s >= float(onset_s)) & (table.t_s < float(onset_s) + float(duration_s))]
    pre_score = score(pre, geometry, p, mode="full", step_min_mm=step_min_mm)
    during_score = score(during, geometry, p, mode="full", step_min_mm=step_min_mm)
    pre_fi = pre_score["fixation_index"]
    during_fi = during_score["fixation_index"]
    retained = None if pre_fi is None or during_fi is None else float(during_fi) - float(pre_fi)
    return {"fixation_retention": retained, "pre_fixation_index": pre_fi,
            "during_fixation_index": during_fi, "pre": pre_score, "during": during_score}


def distractor_capture_hz(delta_on_hz: float, delta_off_hz: float, bias_hz: float = 0.0) -> float:
    """Bias-corrected Δsteer with the distractor on minus the same with it off. Units: Hz.

    Each block mean is (r_R − r_L) − bias_hz. The two subtractions cancel in
    the difference, and both still happen exactly once per block.
    """
    on_corrected = float(delta_on_hz) - float(bias_hz)
    off_corrected = float(delta_off_hz) - float(bias_hz)
    return on_corrected - off_corrected
