# Figure sources in the current manuscript

The build includes already-reviewed static art, without new renders or simulation. None of these panels shows vision or a closed-loop body.

| Figure | Source | Meaning and limits |
|---|---|---|
| Anatomy | `figures/3d/male-cns-anatomy-paper.png`; selection, counts and scale bars in `docs/3d-model.md:87-93,118-128` | Native MaleCNS anatomy, sampled Kenyon cells, no recorded activity. |
| Chemical knockout | `figures/tour/knockout-overview.png`; `docs/tour-figures.md:15,21-41` | Samples of model rate changes under injected input, common signed colour scale, not images of a live fly. |
| Courtship route | `figures/tour/courtship-path.png`; `docs/tour-figures.md:16,21-41` | High P1 drive and selected anatomical pathways; not song or behaviour. |
| GABA curve | `figures/3d/gaba-dose/curves.svg`; `docs/gaba-dose-results.md:15-23` | Matched differences in outside-sensory model firing with uncertainty intervals. The PDF is a vector conversion of the same SVG; no new inference. |

Dopamine findings are bound to reviewed pilot and confirmation JSONs by `paper/result-bindings.json` and stated in prose. The old generated dopamine plots and design graphic are no longer included in this manuscript: their labels contained internal run identifiers. The courtship-body video remains separate from the static figures; its numbers come from `docs/courtship-body.md`.
