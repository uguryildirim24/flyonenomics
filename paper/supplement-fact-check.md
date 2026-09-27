# Supplement source check

Line numbers below refer to the lane's pinned **main** source files (before this supplement), not to rendered PDF line positions. The S5 ontology cells were checked against live OLS4 and VFB responses on 2026-09-27; the evidence is in FBbt lookups below. No FBbt identifier is inferred from a type name. The table numbers S1–S5 are document labels, not biological measurements. The Nordlie, Gewaltig and Plesser 2009 model-description-table convention comes from `docs/research/comparable-preprints.md` §2.2 and the supplement brief; its year is bibliographic, not a model parameter.

## S1 and introductory text

- Graph selection (typed traced neurons, every released pair between retained endpoints, no synapse-count cutoff): `docs/cuda-methods.md:19`. MaleCNS v1.0, reference Brian2, LIF, 162,517 neurons and 25,120,209 connections: `docs/cuda-methods.md:9,19`. The supplement deliberately omits the anatomical version number and the edge total from the tables, but both appear in the source of the description.
- The twelve exclusive groups and their separation: `docs/cuda-methods.md:25-28`, `src/flyonenomics/drive/background.py:40-63,113-132`. No plasticity/learning: `paper/manuscript.tex:21`; `docs/cuda-methods.md:217` lists unimplemented adaptation/short-term depression. Fixed weights and target gain: `docs/cuda-methods.md:30,42,53`.
- Artificial TuBu stimulation and sensory background, no natural vision: `paper/manuscript.tex:21,32,34-36,41`; `docs/cuda-methods.md:15,55`. Outputs and body playback: `docs/cuda-methods.md:69`; `paper/manuscript.tex:90-97`.

## S2: every population count

The **exclusive** group sizes, in table order, come individually from `validation/records/p2/male-cuda-comparison.json:25331-25342` (the seven extra named groups at `:25343-25349` overlap these and are **not** added). The source field names map directly to the table labels:

| Table label | Source JSON key | Count | Source line |
|---|---|---:|---|
| Dopamine neurons | DAN | 367 | 25331 |
| Ellipsoid-body ring neurons | ER | 282 | 25332 |
| Kenyon cells | KC | 4,064 | 25333 |
| Ascending | ascending | 1,849 | 25334 |
| Central intrinsic | central | 39,533 | 25335 |
| Descending | descending | 1,314 | 25336 |
| Endocrine | endocrine | 87 | 25337 |
| Motor/efferent | motor | 887 | 25338 |
| Optic-lobe intrinsic | optic | 89,353 | 25339 |
| Sensory | sensory | 15,016 | 25340 |
| Visual centrifugal | visual_centrifugal | 562 | 25341 |
| Visual projection | visual_projection | 9,203 | 25342 |

The total **162,517** is direct integer addition of those twelve source values: 367 + 282 + 4,064 + 1,849 + 39,533 + 1,314 + 87 + 887 + 89,353 + 15,016 + 562 + 9,203 = 162,517; it agrees with `docs/cuda-methods.md:9` and `paper/manuscript.tex:21`. The subtraction of specialized populations from broad superclasses is implemented in `src/flyonenomics/drive/background.py:40-63,118-132`. Counts are model group sizes, not raw registry inventories; e.g. DAN includes the additional CX_DAN selection, so the registry's standalone DAN inventory is smaller.

## S3: every numeric value and class rule

- Rest/reset −52 mV, threshold −45 mV; membrane 20 ms, drive 5 ms, step 0.1 ms, refractory 2.2 ms, delay 1.8 ms: `docs/cuda-methods.md:40`. The 22/18-tick conversions appear there too; no conversions are newly inferred in S3.
- Pair base weight 0.275 mV; glutamate ×4, GABA onto Kenyon cells ×6, other specified inhibitory scales ×1; positive/negative transmitter lists and the **more than half** rule for unlabelled outputs: `docs/cuda-methods.md:42`. Other outputs do not receive the Kenyon-cell-specific multiplier (`:42`). A sign applies to all outputs of a source (`:42`).
- Sensory 1 mV/event, zero elsewhere; discrete Binomial(100, 0.001) multiplicity per tick, corresponding to 100 independent 10 Hz sources, not Poisson: `docs/cuda-methods.md:55`. Source restriction to 15,016 sensory cells also at `:55` (count in S2).
- Philox4x32-10 name, counter keyed by neuron and tick, realization key not batch position: `src/flyonenomics/engine/cuda_tick.cu:6-19`, `docs/cuda-methods.md:77`. The kernel takes the realization seed as its key and uses separate output words for background and extended input (`cuda_tick.cu:8-19`); the supplement prints **no seed values**. Binomial inversion: `docs/cuda-methods.md:77`, `cuda_tick.cu:69-78`.
- Pool 10 ms step, uptake 0.11 µM/s and 1.3 µM, linear loss 0.05 s⁻¹, reference/clamp 0.02 µM and compartment-dependent release: `docs/cuda-methods.md:85,92`; resting clamp also `:55`. These are nominal constants; release coefficients are in the adopted compartment table, not a uniform constant.
- D1/D2 Kd 1.0/0.05 µM, threshold coefficients 1.5/2.0 mV, gain coefficients 0.3/0.3: `docs/cuda-methods.md:94,104`. Threshold clamp [−52, −30] mV and gain [0.2, 3.0]: `docs/cuda-methods.md:96-102`. The receptor rule itself is recorded at `:94-104`; S3 lists the parameters rather than repeating those composition equations.

## S4: equations and definitions

- The two differential equations and the meaning of voltage, resting voltage, synaptic drive and decay constants: `docs/cuda-methods.md:33-38`. The displayed exact between-event equations are copied from `:44-51` (only line wrapping changes). Strict spike threshold, reset, drive clearing and refractory rejection: `:53`.
- Delayed contribution of **signed weight times target gain** is a verbal rule in `docs/cuda-methods.md:53`; the supplement writes that verbal rule as the displayed arrival equation, not as a claim that a displayed source formula exists. Delay of 1.8 ms (18 ticks) and its next-state-update schedule: `docs/cuda-methods.md:40,65-67`.
- Pool equation is copied from `docs/cuda-methods.md:85-90`, with line breaks only. Every variable in its explanatory sentence is defined at `:85`; the step is in seconds there. Receptor-defined gain in the arrival equation is described at `:94-104`.

## S5: manuscript names and actual selectors

The manuscript names TuBu (`paper/manuscript.tex:21,32,41`), P1/pIP10/dPR1/vPR6/wing motor (`:34,62-71`), pIP1 (`:69`), photoreceptors (`:54,58`), and Kenyon/dopamine/ellipsoid-body ring populations (`docs/cuda-methods.md:25,156-168`; `paper/manuscript.tex:21,38`). The courtship random control is named in `paper/manuscript.tex:65,67` and `docs/cuda-methods.md:79`. Selector references below quote source **field and label/pattern**, not guesses at external identifiers. Broad group translations are at `src/flyonenomics/drive/background.py:40-63`; separate DAN/KC/ER overrides are at `:130-132`. A name can be a subset within a broad group rather than a group itself.

| S5 row | Registry/source field and exact selection | Main file:lines |
|---|---|---|
| P1 | `hemibrain_type` regex `^pC1_` | `data/populations-male-cns-v1.0.yaml:2294-2306` |
| pIP10 | `hemibrain_type` regex `^pIP10$`; descending overlap | `data/populations-male-cns-v1.0.yaml:2320-2333` |
| dPR1 | `hemibrain_type` regex `^dPR1$` | `data/populations-male-cns-v1.0.yaml:2334-2346` |
| vPR6 | `hemibrain_type` regex `^vPR6$` | `data/populations-male-cns-v1.0.yaml:2347-2359` |
| pIP1 | **No selector** in `data/populations-male-cns-v1.0.yaml`; not used in circuit tour group list. The manuscript says the proposed route was not detected as a paired-cell response, not that a pIP1 population was measured. | `paper/manuscript.tex:69`; `scripts/circuit_tour.py:23-24,152-156` |
| TuBu | `hemibrain_type` regex `^TuBu` | `data/populations-male-cns-v1.0.yaml:964-977` |
| Wing motor | `cell_sub_class` regex `^wm$`; overlaps motor | `data/populations-male-cns-v1.0.yaml:2386-2399` |
| Kenyon cells | `cell_class` value `Kenyon_Cell` | `data/populations-male-cns-v1.0.yaml:208-222` |
| Dopamine neurons | `cell_class` value `DAN` plus CX_DAN explicit central-complex selection; group override applied to both | `data/populations-male-cns-v1.0.yaml:9-23,69-129`; `src/flyonenomics/drive/background.py:130-132` |
| Ellipsoid-body ring | `hemibrain_type` regex `^ER\d` | `data/populations-male-cns-v1.0.yaml:859-872` |
| Photoreceptors | `cell_type` values `R1-6`, `R7`, `R8` are named registry subsets, not an exhaustive definition of the sensory group | `data/populations-male-cns-v1.0.yaml:1200-1215,2007-2022,2057-2072`; `docs/SPEC-P2.md:1945` |
| Random courtship control | Explicit fixed cholinergic `cb_intrinsic` subset excluding P1 and direct presynaptic partners of pIP10; this row intentionally omits stored roots and the generator seed. It is not a biological type. | `data/populations-male-cns-v1.0.yaml:2400-2405,2554-2570`; `docs/cuda-methods.md:79` |

**Caveat:** The broad group claimed for dPR1/vPR6 and TuBu is inferred from VNC/central placement in `paper/manuscript.tex:21,62-69` and `docs/optic-lobe-silence.md:47`; their population registry entries do not themselves state the drive-group assignment. The broad group for pIP1 is deliberately not supplied. These are not separately recorded per-cell group mappings in the methods document. The ontology matches below identify *labels*, not a verified cross-specimen mapping of individual MaleCNS cells.

## FBbt lookups

Access date for **each row and URL**: 2026-09-27 (UTC). Public, read-only `curl` requests to OLS4 and Virtual Fly Brain (VFB); no account. Excerpts below are raw `response.docs` entries trimmed to `short_form`, `label`, `obo_id` and relevant matching documents. `[]` means no matching FBbt *label* in that response, not necessarily an empty search result (OLS4 also searches synonyms and fuzzy text). VFB `obo_id` is an array in its raw response. Obsolete and non-FBbt terms are excluded from assignments; no term asserts a cross-specimen identity. The long form was queried separately from the short name.

### P1 — FBbt:00110621
- OLS4 `https://www.ebi.ac.uk/ols4/api/search?q=P1&ontology=fbbt&exact=false&rows=100`: `[{"short_form":"FBbt_00110621","label":"adult fruitless P1 (male) neuron","obo_id":"FBbt:00110621"}]`
- VFB `https://solr.virtualflybrain.org/solr/ontology/select?q=label%3A%22P1%22&wt=json&rows=100`: `[{"short_form":"FBbt_00048120","label":"obsolete adult NPF P1 neuron","obo_id":["FBbt:00048120"]},{"short_form":"FBbt_00110621","label":"adult fruitless P1 (male) neuron","obo_id":["FBbt:00110621"]}]`
- OLS4 `https://www.ebi.ac.uk/ols4/api/search?q=P1%20neuron&ontology=fbbt&exact=false&rows=100`: `[{"short_form":"FBbt_00110621","label":"adult fruitless P1 (male) neuron","obo_id":"FBbt:00110621"}]`
- The only current adult male P1-neuron label; the NPF entry explicitly says obsolete.

### pIP10 — FBbt:00110854
- OLS4 `https://www.ebi.ac.uk/ols4/api/search?q=pIP10&ontology=fbbt&exact=false&rows=100`: `[{"short_form":"FBbt_00110854","label":"adult fruitless pIP10 (male) neuron","obo_id":"FBbt:00110854"}]`
- VFB `https://solr.virtualflybrain.org/solr/ontology/select?q=label%3A%22pIP10%22&wt=json&rows=100`: `[{"short_form":"FBbt_00110854","label":"adult fruitless pIP10 (male) neuron","obo_id":["FBbt:00110854"]}]`
- OLS4 `https://www.ebi.ac.uk/ols4/api/search?q=pIP10%20neuron&ontology=fbbt&exact=false&rows=100`: `[{"short_form":"FBbt_00110854","label":"adult fruitless pIP10 (male) neuron","obo_id":"FBbt:00110854"}]`
- One current FBbt adult male pIP10 label (VFB also returns separate VFB-prefixed entries, not FBbt terms).

### dPR1 — FBbt:00110856
- OLS4 `https://www.ebi.ac.uk/ols4/api/search?q=dPR1&ontology=fbbt&exact=false&rows=100`: `[{"short_form":"FBbt_00110856","label":"adult fruitless dPR1 neuron","obo_id":"FBbt:00110856"}]`
- VFB `https://solr.virtualflybrain.org/solr/ontology/select?q=label%3A%22dPR1%22&wt=json&rows=100`: `[{"short_form":"FBbt_00110856","label":"adult fruitless dPR1 neuron","obo_id":["FBbt:00110856"]}]`
- OLS4 `https://www.ebi.ac.uk/ols4/api/search?q=dPR1%20neuron&ontology=fbbt&exact=false&rows=100`: `[{"short_form":"FBbt_00110856","label":"adult fruitless dPR1 neuron","obo_id":"FBbt:00110856"}]`
- One current adult dPR1-neuron label.

### vPR6 — ambiguous
- OLS4 `https://www.ebi.ac.uk/ols4/api/search?q=vPR6&ontology=fbbt&exact=false&rows=100`: `[{"short_form":"FBbt_00052714","label":"adult fruitless vPR6 neuron","obo_id":"FBbt:00052714"},{"short_form":"FBbt_00110860","label":"adult fruitless vPR6 (male) neuron","obo_id":"FBbt:00110860"},{"short_form":"FBbt_00111150","label":"adult fruitless vPR6 (female) neuron","obo_id":"FBbt:00111150"}]`
- VFB `https://solr.virtualflybrain.org/solr/ontology/select?q=label%3A%22vPR6%22&wt=json&rows=100`: `[{"short_form":"FBbt_00052714","label":"adult fruitless vPR6 neuron","obo_id":["FBbt:00052714"]},{"short_form":"FBbt_00110860","label":"adult fruitless vPR6 (male) neuron","obo_id":["FBbt:00110860"]},{"short_form":"FBbt_00111150","label":"adult fruitless vPR6 (female) neuron","obo_id":["FBbt:00111150"]}]`
- OLS4 `https://www.ebi.ac.uk/ols4/api/search?q=vPR6%20neuron&ontology=fbbt&exact=false&rows=100`: `[{"short_form":"FBbt_00052714","label":"adult fruitless vPR6 neuron","obo_id":"FBbt:00052714"},{"short_form":"FBbt_00110860","label":"adult fruitless vPR6 (male) neuron","obo_id":"FBbt:00110860"},{"short_form":"FBbt_00111150","label":"adult fruitless vPR6 (female) neuron","obo_id":"FBbt:00111150"}]`
- Plausible candidates for an adult male population: FBbt:00052714 (sex-unspecified adult fruitless vPR6 neuron) and FBbt:00110860 (male-specific adult fruitless vPR6 neuron). The female-specific FBbt:00111150 does not match this model.

### pIP1 — not found
- OLS4 `https://www.ebi.ac.uk/ols4/api/search?q=pIP1&ontology=fbbt&exact=false&rows=100`: `[]`
- VFB `https://solr.virtualflybrain.org/solr/ontology/select?q=label%3A%22pIP1%22&wt=json&rows=100`: `[]`
- OLS4 `https://www.ebi.ac.uk/ols4/api/search?q=pIP1%20neuron&ontology=fbbt&exact=false&rows=100`: `[]`
- OLS4 returns fuzzy pIP10/pIP-a hits, not pIP1 labels; the MaleCNS registry also has no pIP1 selector.

### TuBu — FBbt:00047047
- OLS4 `https://www.ebi.ac.uk/ols4/api/search?q=TuBu&ontology=fbbt&exact=false&rows=100`: `[{"short_form":"FBbt_00047050","label":"adult tubercle-anterior bulb neuron","obo_id":"FBbt:00047050"},{"short_form":"FBbt_00047048","label":"adult tubercle-inferior bulb neuron","obo_id":"FBbt:00047048"},{"short_form":"FBbt_00047049","label":"adult tubercle-superior bulb neuron","obo_id":"FBbt:00047049"},{"short_form":"FBbt_00047047","label":"adult tubercle-bulb neuron","obo_id":"FBbt:00047047"}]`
- VFB `https://solr.virtualflybrain.org/solr/ontology/select?q=label%3A%22TuBu%22&wt=json&rows=100`: `[]`
- OLS4 `https://www.ebi.ac.uk/ols4/api/search?q=tubercle%20bulb%20neuron&ontology=fbbt&exact=false&rows=100`: `[{"short_form":"FBbt_00047050","label":"adult tubercle-anterior bulb neuron","obo_id":"FBbt:00047050"},{"short_form":"FBbt_00047047","label":"adult tubercle-bulb neuron","obo_id":"FBbt:00047047"},{"short_form":"FBbt_00047049","label":"adult tubercle-superior bulb neuron","obo_id":"FBbt:00047049"},{"short_form":"FBbt_00047048","label":"adult tubercle-inferior bulb neuron","obo_id":"FBbt:00047048"}]`
- VFB `https://solr.virtualflybrain.org/solr/ontology/select?q=label%3A%22adult%20tubercle-bulb%20neuron%22&wt=json&rows=100`: `[{"short_form":"FBbt_00047047","label":"adult tubercle-bulb neuron","obo_id":["FBbt:00047047"]}]`
- The unqualified long-form label `adult tubercle-bulb neuron` matches the paper's broad TuBu selector; the other hits specify narrower bulb regions or numbered subtypes.

### Wing motor — ambiguous
- OLS4 `https://www.ebi.ac.uk/ols4/api/search?q=wing%20motor%20neuron&ontology=fbbt&exact=false&rows=100`: `[{"short_form":"FBbt_00052010","label":"adult octopaminergic wing muscle motor neuron","obo_id":"FBbt:00052010"},{"short_form":"FBbt_00047246","label":"wing axillary muscle hg1 motor neuron","obo_id":"FBbt:00047246"},{"short_form":"FBbt_00004068","label":"wing basalar muscle b2 motor neuron","obo_id":"FBbt:00004068"},{"short_form":"FBbt_00004066","label":"wing basalar muscle b1 motor neuron","obo_id":"FBbt:00004066"}]`
- VFB `https://solr.virtualflybrain.org/solr/ontology/select?q=label%3A%22wing%20motor%20neuron%22&wt=json&rows=100`: `[]`
- OLS4 `https://www.ebi.ac.uk/ols4/api/search?q=adult%20wing%20motor%20neuron&ontology=fbbt&exact=false&rows=100`: `[{"short_form":"FBbt_00052010","label":"adult octopaminergic wing muscle motor neuron","obo_id":"FBbt:00052010"}]`
- Distinct plausible types include FBbt:00052010 (adult octopaminergic wing muscle motor neuron), FBbt:00047246 (wing axillary muscle hg1 motor neuron), FBbt:00004068 (wing basalar muscle b2 motor neuron), FBbt:00004066 (wing basalar muscle b1 motor neuron). None is a unique generic match to `wm`.

### Kenyon cells — FBbt:00049825
- OLS4 `https://www.ebi.ac.uk/ols4/api/search?q=Kenyon%20cell&ontology=fbbt&exact=false&rows=100`: `[{"short_form":"FBbt_00003686","label":"Kenyon cell","obo_id":"FBbt:00003686"},{"short_form":"FBbt_00049825","label":"adult Kenyon cell","obo_id":"FBbt:00049825"}]`
- VFB `https://solr.virtualflybrain.org/solr/ontology/select?q=label%3A%22Kenyon%20cell%22&wt=json&rows=100`: `[{"short_form":"FBbt_00003686","label":"Kenyon cell","obo_id":["FBbt:00003686"]},{"short_form":"FBbt_00049825","label":"adult Kenyon cell","obo_id":["FBbt:00049825"]}]`
- OLS4 `https://www.ebi.ac.uk/ols4/api/search?q=adult%20Kenyon%20cell&ontology=fbbt&exact=false&rows=100`: `[{"short_form":"FBbt_00049825","label":"adult Kenyon cell","obo_id":"FBbt:00049825"}]`
- Adult-restricted class label matches this adult model; the unqualified parent is not adult-specific.

### Dopamine neurons — FBbt:00058206
- OLS4 `https://www.ebi.ac.uk/ols4/api/search?q=dopaminergic%20neuron&ontology=fbbt&exact=false&rows=100`: `[{"short_form":"FBbt_00005131","label":"dopaminergic neuron","obo_id":"FBbt:00005131"},{"short_form":"FBbt_00058206","label":"adult dopaminergic neuron","obo_id":"FBbt:00058206"}]`
- VFB `https://solr.virtualflybrain.org/solr/ontology/select?q=label%3A%22dopaminergic%20neuron%22&wt=json&rows=100`: `[{"short_form":"FBbt_00005131","label":"dopaminergic neuron","obo_id":["FBbt:00005131"]},{"short_form":"FBbt_00058206","label":"adult dopaminergic neuron","obo_id":["FBbt:00058206"]}]`
- OLS4 `https://www.ebi.ac.uk/ols4/api/search?q=adult%20dopaminergic%20neuron&ontology=fbbt&exact=false&rows=100`: `[{"short_form":"FBbt_00058206","label":"adult dopaminergic neuron","obo_id":"FBbt:00058206"}]`
- The adult-restricted dopaminergic-neuron label matches the broad DAN group; the generic parent is not adult-specific.

### Ellipsoid-body ring — FBbt:00003649
- OLS4 `https://www.ebi.ac.uk/ols4/api/search?q=ellipsoid%20body%20ring%20neuron&ontology=fbbt&exact=false&rows=100`: `[{"short_form":"FBbt_00003649","label":"adult ellipsoid body ring neuron","obo_id":"FBbt:00003649"},{"short_form":"FBbt_00003651","label":"adult ellipsoid body ring neuron R2","obo_id":"FBbt:00003651"},{"short_form":"FBbt_00003650","label":"adult ellipsoid body ring neuron R1","obo_id":"FBbt:00003650"}]`
- VFB `https://solr.virtualflybrain.org/solr/ontology/select?q=label%3A%22ellipsoid%20body%20ring%20neuron%22&wt=json&rows=100`: `[{"short_form":"FBbt_00003649","label":"adult ellipsoid body ring neuron","obo_id":["FBbt:00003649"]},{"short_form":"FBbt_00003650","label":"adult ellipsoid body ring neuron R1","obo_id":["FBbt:00003650"]},{"short_form":"FBbt_00003651","label":"adult ellipsoid body ring neuron R2","obo_id":["FBbt:00003651"]}]`
- OLS4 `https://www.ebi.ac.uk/ols4/api/search?q=adult%20ellipsoid%20body%20ring%20neuron&ontology=fbbt&exact=false&rows=100`: `[{"short_form":"FBbt_00003649","label":"adult ellipsoid body ring neuron","obo_id":"FBbt:00003649"},{"short_form":"FBbt_00003650","label":"adult ellipsoid body ring neuron R1","obo_id":"FBbt:00003650"},{"short_form":"FBbt_00003651","label":"adult ellipsoid body ring neuron R2","obo_id":"FBbt:00003651"}]`
- Unique adult umbrella label for the broad ring group; R1/R2 and others are narrower types, not alternative generic terms.

### Photoreceptors — ambiguous
- OLS4 `https://www.ebi.ac.uk/ols4/api/search?q=photoreceptor%20cell&ontology=fbbt&exact=false&rows=100`: `[{"short_form":"FBbt_00004219","label":"photoreceptor cell R4","obo_id":"FBbt:00004219"},{"short_form":"FBbt_00004221","label":"photoreceptor cell R5","obo_id":"FBbt:00004221"},{"short_form":"FBbt_00004223","label":"photoreceptor cell R6","obo_id":"FBbt:00004223"},{"short_form":"FBbt_00004217","label":"photoreceptor cell R3","obo_id":"FBbt:00004217"},{"short_form":"FBbt_00004215","label":"photoreceptor cell R2","obo_id":"FBbt:00004215"},{"short_form":"FBbt_00004213","label":"photoreceptor cell R1","obo_id":"FBbt:00004213"},{"short_form":"FBbt_00004225","label":"photoreceptor cell R7","obo_id":"FBbt:00004225"},{"short_form":"FBbt_00006009","label":"eye photoreceptor cell","obo_id":"FBbt:00006009"},{"short_form":"FBbt_00004227","label":"photoreceptor cell R8","obo_id":"FBbt:00004227"}]`
- VFB `https://solr.virtualflybrain.org/solr/ontology/select?q=label%3A%22photoreceptor%20cell%22&wt=json&rows=100`: `[{"short_form":"FBbt_00006009","label":"eye photoreceptor cell","obo_id":["FBbt:00006009"]},{"short_form":"FBbt_00004213","label":"photoreceptor cell R1","obo_id":["FBbt:00004213"]},{"short_form":"FBbt_00004215","label":"photoreceptor cell R2","obo_id":["FBbt:00004215"]},{"short_form":"FBbt_00004217","label":"photoreceptor cell R3","obo_id":["FBbt:00004217"]},{"short_form":"FBbt_00004219","label":"photoreceptor cell R4","obo_id":["FBbt:00004219"]},{"short_form":"FBbt_00004221","label":"photoreceptor cell R5","obo_id":["FBbt:00004221"]},{"short_form":"FBbt_00004223","label":"photoreceptor cell R6","obo_id":["FBbt:00004223"]},{"short_form":"FBbt_00004225","label":"photoreceptor cell R7","obo_id":["FBbt:00004225"]},{"short_form":"FBbt_00004227","label":"photoreceptor cell R8","obo_id":["FBbt:00004227"]}]`
- OLS4 `https://www.ebi.ac.uk/ols4/api/search?q=photoreceptor%20cell%20R7&ontology=fbbt&exact=false&rows=100`: `[{"short_form":"FBbt_00004225","label":"photoreceptor cell R7","obo_id":"FBbt:00004225"}]`
- The selector spans R1–R8, not one subtype: candidates FBbt:00004213 (R1), FBbt:00004215 (R2), FBbt:00004217 (R3), FBbt:00004219 (R4), FBbt:00004221 (R5), FBbt:00004223 (R6), FBbt:00004225 (R7), FBbt:00004227 (R8); FBbt:00006009 (`eye photoreceptor cell`) is a broader umbrella, not an exact match to the listed subsets.

### Random courtship control — not found
- OLS4 `https://www.ebi.ac.uk/ols4/api/search?q=random%20courtship%20control&ontology=fbbt&exact=false&rows=100`: `[]`
- VFB `https://solr.virtualflybrain.org/solr/ontology/select?q=label%3A%22random%20courtship%20control%22&wt=json&rows=100`: `[]`
- OLS4 `https://www.ebi.ac.uk/ols4/api/search?q=courtship%20control%20neuron&ontology=fbbt&exact=false&rows=100`: `[]`
- Algorithmically selected control, not an anatomical neuron type.
