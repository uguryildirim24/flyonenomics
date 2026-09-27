"""Virtual Buridan platform and neural steering readout."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from flyonenomics.behaviour.encoder import VisualEncoder
from flyonenomics.behaviour.metrics import Geometry, score, wrap
from flyonenomics.schema.experiment import BuridanParams, OpenLoopParams, Probe
from flyonenomics.types import Params

STIMULUS_NAMES = ("A", "B", "distractor")  # SPEC section 11 item 23.
FLICKER_DUTY = 0.5  # SPEC section 3.5: 50 percent duty cycle.


def _point(azimuth_deg: float, radius_mm: float) -> NDArray[np.float64]:
    az = np.deg2rad(azimuth_deg)
    return radius_mm * np.array([np.sin(az), np.cos(az)])


def stripe_view(position_mm: NDArray[np.float64], heading_deg: float, azimuth_deg: float,
                width_deg: float, wall_radius_mm: float, contrast: float, name: str) -> dict[str, float | str]:
    """Return exact bar centre/edge geometry, mm position (2,), degrees angles, unitless contrast."""
    centre = _point(azimuth_deg, wall_radius_mm) - position_mm
    edge1 = _point(azimuth_deg - width_deg / 2, wall_radius_mm) - position_mm
    edge2 = _point(azimuth_deg + width_deg / 2, wall_radius_mm) - position_mm
    centre_az = float(np.rad2deg(np.arctan2(centre[0], centre[1])))
    e1 = float(np.rad2deg(np.arctan2(edge1[0], edge1[1])))
    e2 = float(np.rad2deg(np.arctan2(edge2[0], edge2[1])))
    return {"name": name, "az_arena": float(wrap(centre_az)), "az_fly": float(wrap(centre_az - heading_deg)),
            "width": float(abs(wrap(e2 - e1))), "contrast": contrast}


class Behaviour:
    """Probe-local arena; mm position, degrees heading, Hz filtered steering rates."""

    def __init__(self, plan: Any, registry: Any, params: Params, probe: Probe, *, v_fwd: float,
                 sign_steer: int, K_steer: float, r_vis_max: float, sigma_vis: float,
                 bias_hz: float = 0.0) -> None:
        """Bind a probe and extended indices; speeds mm/s, gain degrees/s/Hz, vision Hz/degrees."""
        self.params = params
        self.probe = probe
        self.v_fwd = v_fwd
        self.sign_steer = sign_steer
        self.K_steer = K_steer
        self.bias_hz = float(bias_hz)
        self.left_idx = registry.population("steering_L").idx
        self.right_idx = registry.population("steering_R").idx
        if not len(self.left_idx) or not len(self.right_idx):
            raise ValueError("steering_L and steering_R must both resolve non-empty populations")
        if isinstance(probe.params, BuridanParams):
            injection = probe.params.inject_at
        elif isinstance(probe.params, OpenLoopParams) and probe.params.inject_at:
            injection = probe.params.inject_at
        else:
            injection = params.get("vis.inject_at")
        mapped = "R1_6" if injection == "photoreceptors" else injection
        if mapped not in ("TuBu", "ER", "R1_6"):
            raise ValueError("inject_at must be TuBu, ER, or photoreceptors")
        from flyonenomics.behaviour import encoder_class_for
        self.inject_at = injection
        self.encoder = encoder_class_for(injection)(registry, plan.topology.extended_idx, params, mapped)
        self.r_vis_max = r_vis_max
        self.sigma_vis = sigma_vis
        self.stream: np.random.Generator | None = None
        self.t_s = 0.0
        self.trajectory: list[dict[str, float | int]] = []
        self.x = self.y = self.h = self.omega = self.r_L = self.r_R = 0.0

    @property
    def encoder_stream(self) -> np.random.Generator | None:
        """Return ENCODER generator; unitless stream, scalar."""
        return self.encoder.stream

    @encoder_stream.setter
    def encoder_stream(self, value: np.random.Generator) -> None:
        self.encoder.stream = value
        self.encoder._permutations = None

    def permutation(self, k: int) -> None:
        """Apply preferred-azimuth permutation index k; degrees vector (n_injection,)."""
        self.encoder.permutation(k)

    def reset(self, stream: np.random.Generator) -> None:
        """Hold p=(0,0) mm and draw heading from the BEHAVIOUR stream when random."""
        self.stream = stream
        self.t_s = 0.0
        self.trajectory = []
        self.x = self.y = self.omega = self.r_L = self.r_R = 0.0
        heading = "stripe_A"
        if isinstance(self.probe.params, BuridanParams) and self.probe.params.initial_heading:
            heading = self.probe.params.initial_heading
        if heading == "random":
            draw = float(stream.random())
            self.h = 180.0 - draw * 360.0
        else:
            self.h = 0.0

    def _block(self) -> tuple[Any, float] | None:
        """Current open-loop block and its start time, or None; seconds."""
        if not isinstance(self.probe.params, OpenLoopParams) or not self.probe.params.blocks:
            return None
        elapsed = 0.0
        blocks = self.probe.params.blocks
        for block in blocks:
            length = block.transition_s + block.dwell_s
            if self.t_s < elapsed + length:
                return block, elapsed
            elapsed += length
        return blocks[-1], elapsed - (blocks[-1].transition_s + blocks[-1].dwell_s)

    def lit(self) -> bool:
        """False only inside a `dark` block; the bright wall is L = 1 otherwise (section 3.2)."""
        current = self._block()
        return current is None or current[0].stimulus != "dark"

    def _stimuli(self) -> list[dict[str, float | str]]:
        p = np.array([self.x, self.y])
        width = self.params.get("arena.stripe_width")
        wall = self.params.get("arena.R_wall")
        if isinstance(self.probe.params, OpenLoopParams):
            current = self._block()
            if current is not None:
                chosen, elapsed = current
                # Ambient is the bare bright wall and dark has no wall: neither has a bar.
                if chosen.stimulus in ("dark", "ambient"):
                    return []
                stimuli = [stripe_view(p, self.h, float(chosen.azimuth_deg), width, wall, 1.0, "A")]
                distractor = chosen.distractor
                if distractor is not None:
                    in_block = self.t_s - elapsed
                    on = in_block >= chosen.transition_s and (in_block * distractor.flicker_hz) % 1 < FLICKER_DUTY
                    stimuli.append(stripe_view(p, self.h, distractor.azimuth, width, wall,
                                               distractor.contrast if on else 0.0, "distractor"))
                return stimuli
            azimuths = self.probe.params.azimuths or self.params.get("openloop.azimuths")
            period = self.params.get("openloop.transition_s") + self.params.get("openloop.dwell_s")
            index = min(int(self.t_s / period), len(azimuths) - 1)
            return [stripe_view(p, self.h, float(azimuths[index]), width, wall, 1.0, "A")]
        options = self.probe.params
        assert isinstance(options, BuridanParams)
        stimuli: list[dict[str, float | str]] = []
        if options.stripes:
            for name, azimuth in zip(("A", "B"), self.params.get("arena.stripe_azimuths"), strict=True):
                stimuli.append(stripe_view(p, self.h, azimuth, width, wall, 1.0, name))
        distractor = options.distractor
        if distractor is not None:
            elapsed = self.t_s - distractor.onset_s
            on = 0 <= elapsed < distractor.duration_s and (elapsed * distractor.flicker_hz) % 1 < FLICKER_DUTY
            stimuli.append(stripe_view(p, self.h, distractor.azimuth, width, wall,
                                       distractor.contrast if on else 0.0, "distractor"))
        return stimuli

    def view(self) -> dict[str, Any]:
        """Render current stripe view; angles/width degrees, contrasts unitless, stimuli list (0..3)."""
        return {"stimuli": self._stimuli()}

    def rates(self, view: dict[str, Any], t: float) -> NDArray[np.float64]:
        """Return extended visual rates (Hz, n_extended) at recording time t seconds."""
        del view
        self.t_s = t
        enabled = not isinstance(self.probe.params, BuridanParams) or self.probe.params.encoder == "on"
        # Candidate overrides are probe-local; the shared Params object is not mutated.
        if self.inject_at == "photoreceptors":
            # The photoreceptor encoder (WP18) also needs the wall state: dark blocks set L = 0.
            return self.encoder.rates(
                self._stimuli(), enabled=enabled, r_light=self.r_vis_max, lit=self.lit(),
            )
        return self.encoder.rates(self._stimuli(), enabled=enabled,
                                  maximum_hz=self.r_vis_max, sigma_deg=self.sigma_vis)

    def step(self, counts: NDArray[np.int32], dt_s: float) -> None:
        """Advance neural filter and closed-loop arena by dt_s seconds; counts (n_engine,), mm/degrees/Hz state."""
        tau_s = self.params.get("steer.tau_rate") / 1000
        alpha = 1 - np.exp(-dt_s / tau_s)
        left = float(np.mean(counts[self.left_idx]) / dt_s) if len(self.left_idx) else 0.0
        right = float(np.mean(counts[self.right_idx]) / dt_s) if len(self.right_idx) else 0.0
        self.r_L += alpha * (left - self.r_L)
        self.r_R += alpha * (right - self.r_R)
        self.omega = self.sign_steer * self.K_steer * ((self.r_R - self.r_L) - self.bias_hz)
        if not isinstance(self.probe.params, OpenLoopParams):
            if self.stream is None:
                raise ValueError("reset before step")
            self.h = float(wrap(self.h + self.omega * dt_s + self.params.get("arena.sigma_h") * np.sqrt(dt_s) * self.stream.normal()))
            self.x += self.v_fwd * dt_s * np.sin(np.deg2rad(self.h))
            self.y += self.v_fwd * dt_s * np.cos(np.deg2rad(self.h))
            radius = float(np.hypot(self.x, self.y))
            limit = self.params.get("arena.R_platform") - self.params.get("arena.edge_margin")
            if radius >= limit:
                self.x *= limit / radius
                self.y *= limit / radius
                self.h = float(wrap(self.h + 180 + self.params.get("arena.sigma_edge") * self.stream.normal()))
        # rates() owns recording time. Keep the presented stimulus on the
        # chunk's start clock, including the last chunk before a transition.
        if isinstance(self.probe.params, BuridanParams):
            self.trajectory.append({"t_s": self.t_s, "x_mm": self.x, "y_mm": self.y, "segment": 0})

    def metrics(self) -> dict[str, Any]:
        """Score this probe in window mode, including distractor episodes; fractions/degrees/counts."""
        if not isinstance(self.probe.params, BuridanParams):
            return {}
        episodes = None
        distractor = self.probe.params.distractor
        if distractor is not None:
            episodes = pd.DataFrame([{"onset_s": distractor.onset_s, "azimuth_deg": distractor.azimuth}])
        table = pd.DataFrame(self.trajectory, columns=["t_s", "x_mm", "y_mm", "segment"])
        return score(table, Geometry.from_params(self.params), self.params, episodes=episodes)

    def state(self) -> dict[str, float]:
        """Return arena and stimulus columns; mm x/y, degrees h/az/width, degrees/s omega, Hz rates."""
        state = {"x": self.x, "y": self.y, "h": self.h, "omega": self.omega, "r_L": self.r_L, "r_R": self.r_R}
        for item in self._stimuli():
            name = str(item["name"])
            for field in ("az_arena", "az_fly", "width", "contrast"):
                state[f"{field}_{name}"] = float(item[field])
        return state
