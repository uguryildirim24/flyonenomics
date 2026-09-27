# Transmitter census (WP14)

Pinned annotation v2.1.0, connectome v783. Scope `brain`. No engine process.

## Classes in engine order

| class | n |
| --- | ---: |
| ACh | 85371 |
| Glu | 22792 |
| GABA | 16150 |
| His | 10587 |
| mod | 1992 |
| unk | 1747 |

`n_engine` = 138,639. `classes_sha256` = `097100ec1abdc1a57b64da8e782ba4fcfef2dc85acf58906fd5cff023066698e`.
Mixed-sign presynaptic neurons: 0.

## Curated `known_nt` sign vs `top_nt` sign (all annotations)

SPEC-P2 section 2.2.1 table:

| Change | sensory | optic | central | visual_projection | descending | total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| predicted excitatory, curated inhibitory | 809 | 533 | 8 | 0 | 0 | 1,350 |
| predicted inhibitory, curated excitatory | 5 | 492 | 41 | 2 | 2 | 542 |

Measured:

| Change | sensory | optic | central | visual_projection | descending | total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| predicted excitatory, curated inhibitory | 809 | 533 | 11 | 0 | 0 | 1,353 |
| predicted inhibitory, curated excitatory | 5 | 492 | 41 | 2 | 2 | 542 |

Engine-only recomputation: see `curated_vs_top_nt_engine` in the report.

Neurons whose connection-file sign `s_pq` differs from the Shiu rule on `top_nt`: 6,024.

## Photoreceptors, L1, L2, Mi1, Tm3

| Cell type | Annotation count | In engine | top_nt counts | known_nt | Class |
| --- | ---: | ---: | ---: | ---: | ---: |
| R1-6 | 8452 | 7932 | acetylcholine 5,343, glutamate 1,675, gaba 530, serotonin 397, empty 393, octopamine 89 | none | His |
| R7 | 1343 | 1337 | glutamate 731, acetylcholine 319, gaba 269, serotonin 8, octopamine 8, empty 6 | none | His |
| R8 | 1324 | 1314 | acetylcholine 786, glutamate 431, gaba 75, serotonin 10, empty 9, octopamine 7 | histamine 1324 | His |
| L1 | 1579 | 1579 | glutamate 1,043, gaba 512, acetylcholine 24 | glutamate 1579 | Glu |
| L2 | 1554 | 1554 | acetylcholine 1,542, glutamate 7, gaba 5 | acetylcholine 1554 | ACh |
| Mi1 | 1580 | 1580 | acetylcholine 1,569, glutamate 11 | acetylcholine 1580 | ACh |
| Tm3 | 1746 | 1746 | acetylcholine 1,746 | acetylcholine 1746 | ACh |

## Synapse counts (in-engine roots)

SPEC-P2 claims:

| Connection | Measured synapses | SPEC-P2 | match |
| --- | ---: | ---: | ---: |
| L1->Mi1 | 121,693 | 121,693 | yes |
| L1->Tm3 | 80,600 | 80,600 | yes |
| R1_6->L1 | 63,344 | 63,344 | yes |
| R1_6->L2 | 62,051 | 62,051 | yes |

All measured pairs, including L2 targets the census must report:

| Connection | Pairs | Synapses |
| --- | ---: | ---: |
| R1_6->L1 | 5867 | 63344 |
| R1_6->L2 | 5727 | 62051 |
| L1->Mi1 | 1743 | 121693 |
| L1->Tm3 | 8829 | 80600 |
| L2->Tm1 | 1876 | 169915 |
| L2->Tm2 | 2526 | 146073 |
| L2->Tm4 | 7974 | 82158 |
| L2->Tm9 | 135 | 193 |

## Disagreements with SPEC-P2 tables

- predicted excitatory, curated inhibitory / central: measured 11, SPEC-P2 8
- predicted excitatory, curated inhibitory / total: measured 1,353, SPEC-P2 1,350
- The three extra central predicted-excitatory / curated-inhibitory neurons are two PPL203 (`known_nt` `dopamine, gaba`, first classical token GABA) and one DN1a (`CCHa1, Dh44, glutamate`). The rule takes the first listed classical transmitter. Scope stays `brain`.

## Question 4: central correction concentration

Central curated sign corrections: 52 neurons across 26 types. Rolf's reading for question 4 is whole-brain scope (`brain`). Corrections are not concentrated in a few types with doubtful labels. Scope stays `brain`.

Counts by `cell_type`:

- 5-HTPLP01: 4
- LHAV2m1: 4
- LHAV7a1a: 4
- PPM1204,PS139: 4
- LHAV7a1b: 3
- LHAV7a1c: 3
- AVLP560: 2
- CB.FB6E2: 2
- CB.FB7E2: 2
- CB0627: 2
- DPM: 2
- LHPV6o1: 2
- P1-9: 2
- PPL203: 2
- TuBu08: 2
- v2LN36: 2
- AVLP026: 1
- CB.FB3,4A21: 1
- DN1a: 1
- Delta7: 1
- ER3a: 1
- KCg-m: 1
- LPsP: 1
- MBON05: 1
- PAM02: 1
- il3LN6: 1

## Stage retinotopy: median column spread (deg)

A type gets column subsets when median spread ≤ 20.0°.
R1-6 neurons are ranked by `pos_z` per eye; `pos_z` is an integer section index, and tied neurons take
the mean of their ranks. Types are assigned one after another in the listed order, so a later type in
the same stage can use an earlier one's azimuths. Column subsets use only the neurons with an azimuth:
`n_with_azimuth` of `n` is the coverage (LC10 397 of 816, SPEC-P2 section 10 question 17).

| Type | n | n_with_azimuth | median_spread_deg | column_subsets | source |
| --- | ---: | ---: | ---: | ---: | ---: |
| R1_6 | 7932 | 7932 | 0.000 | yes | rank |
| L1 | 1579 | 1247 | 3.124 | yes | propagated |
| L2 | 1554 | 1249 | 2.983 | yes | propagated |
| L3 | 1406 | 1149 | 3.215 | yes | propagated |
| L4 | 1398 | 1080 | 2.395 | yes | propagated |
| L5 | 1606 | 1258 | 0.454 | yes | propagated |
| Mi1 | 1580 | 1296 | 1.397 | yes | propagated |
| Mi4 | 1528 | 1260 | 3.600 | yes | propagated |
| Mi9 | 1568 | 1298 | 1.672 | yes | propagated |
| Tm1 | 1544 | 1290 | 0.624 | yes | propagated |
| Tm2 | 1528 | 1286 | 1.897 | yes | propagated |
| Tm3 | 1746 | 1479 | 4.603 | yes | propagated |
| Tm4 | 1489 | 1281 | 4.645 | yes | propagated |
| Tm9 | 1506 | 1265 | 1.858 | yes | propagated |
| T4 | 6240 | 5374 | 4.668 | yes | propagated |
| T5 | 5998 | 5304 | 4.764 | yes | propagated |
| LC10 | 816 | 397 | 3.614 | yes | propagated |

L2 propagated azimuth vs rank rule on L2 `pos_z`: Spearman ρ left = 0.6727929181835998, right = 0.6761695021887776.
R1-6 retinotopy SHA-256 = `8e490ec14ee72376b026663f25386fb1d31aac8e0c8cece0743d83aa74f419fd`.
