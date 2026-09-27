# Publication-quality and fact audit — 25 September 2026

## Verdict

**Not publication-ready yet.** The first-study numerical reporting is accurate and appropriately inconclusive. The biological claims used in the paper are supported by the accessible sources; I found no fabricated biological result or incorrect biological DOI in that bibliography. However, public parameter provenance still contains false source claims, reproduction instructions omit a required dependency, the paper omits important parts of its actual model, and the front page contradicts the results. These are repairable without changing the experiment or fitting anything to its outcomes.

Fix the blockers and the substantive Methods/reproduction gaps below, then inspect the integrated manuscript and figures. This audit is not approval of the pending confirmation text, final PDF, public snapshot, or submission. In particular, full-text verification of the three statistical references remains incomplete because the original endpoints were inaccessible.

## Scope and evidence boundary

- Main/code snapshot: `fa697f96f2305bc29e6768eb31fed832cb0fd1c3`.
- Paper branch `hp/flyonenomics/t-0096-paper-prepare-the-confirmation-section-a`: scaffold `25a9d13712b47269aa6b6aafb9b25213ab10ee2e`, then its humanizer draft. During audit close-out that draft landed as `91cd90105d81a6ff3847d993e82f2e380f99a3c9`; the resulting manuscript SHA-256 is `a4ca01e990db911a9a18e425d286a204f96d6b073fce710d829496570fc2643d`. References marked **rewrite** below use this final commit. The removed adjacent duplicate substrate sentence was not retained as an open finding; the other cited repetitions remain.
- Portfolio branch `hp/flyonenomics/t-0098-portfolio-kit-for-rolf`: `190fd0c2827004996f7135acdf85fdc365b7e063`; all six portfolio documents read.
- Follow-up design cross-check: `docs/adhd-confirm-design.md` on t-0095 at `f97516f`. No claim here about the follow-up's numerical outcome; the inspected paper still has confirmation tokens.
- Inspected engine construction/equations, dopamine chemistry/receptor/state/drug code, resting-drive loaders/group assignment, paired input generation, study runner and analysis; male tables, population/compartment policies and all three `docs/malecns-*.md` documents; research audit, README, REPRODUCE, figure sources and committed anatomy/four-panel PNGs.
- Numerical checks were read-only calculations on committed JSON/CSV, not a model rerun. No raw bootstrap rerun, fresh source-table conversion, full gate, new browser session or final PDF build. The full gate belongs to the review round. No production files were changed.

## Findings

### F01 — blocker — false pharmacology provenance remains in shipped parameters

**Owner:** model code (parameter tables).

**Locations:** `data/params-v0.2.yaml:85,88,94`; also the inherited counterparts in `data/params-v0.1.yaml` should receive the same provenance disposition. `docs/adhd-model-research.md:33` already identifies this problem.

**Evidence:** The source label says “Kume 2005 fed 3-IY at milligrams per millilitre.” Kume's accessible full text (PMC6725300, Methods/Results) supplies no such administration experiment. Shin & Venton instead tested **100 µM bath exposure for 20 min**, not this model's EC50. The MPH default claims “Qu 2024, van der Voet 2016 range 0.1 to 1.0 mM.” Van der Voet's full-text Methods specify **1 mg/mL food**, after initially comparing 0.5 and 1 mg/mL, not that mM range. The reviewed research audit records Qu's 1.5 mg/mL choice. The kappa source repeats an unverified food-to-brain conversion from L2 while admitting no fly source. Calling the first number a placeholder does not make the appended factual assertion true. These drug/PK values are not used by the direct release-scaling experiment, so this does **not** invalidate its reported contrasts.

**Exact proposed fix:** Replace the source descriptions with:
- EC50: “Declared model placeholder; no measured adult-fly concentration–response calibration. Not inferred from Kume 2005 or the single bath concentration in Shin & Venton 2018.”
- kappa: “Declared food-to-brain conversion assumption; no verified fly measurement.”
- MPH default: “Declared model dose setting, not a dose or concentration range established by Qu 2024 or van der Voet 2016.”

Keep the numerical values unchanged. Because these bytes are frozen inputs, preserve the executed versions/hashes as historical evidence and make the correction an explicit versioned provenance change or prominently bound erratum; do not silently replace the old hashes or rerun outcomes. Do not export the disproved L2 claims as current scientific evidence.

### F02 — blocker — current result status is factually stale

**Owner:** docs.

**Locations:** `README.md:43–47`; `REPRODUCE.md:3–5,286–293`.

**Evidence:** They say the first male perturbation experiment is in progress/has no reported outcome. The same tree contains `docs/adhd-study-results.md`, the filled-paper bindings and the reviewed ten-seed result record. This conflicts with both paper and portfolio. Confirmation pending is a different status from first-study results pending.

**Exact proposed fix:** Replace the first-study status with: “The first ten-seed study is complete: the vehicle genotype contrast was nominal only (Holm p=0.0703125), and the release interaction had no detected difference. See the results and reproduction records.” Link `docs/adhd-study-results.md` and `paper/README.md`. Give the independently frozen confirmation its own dated status, updated only from its reviewed record. Replace REPRODUCE §7's instructions to add future commands with the already recorded analysis/descriptive commands and raw-access boundary.

### F03 — major — the male reproduction recipe omits a mandatory Shiu code checkout

**Owner:** docs.

**Locations:** `REPRODUCE.md:24–39,50–53,141–173`; `src/flyonenomics/engine/brian_engine.py:105–117,327,550–588`; `docs/data.md:47–58,152–153`.

**Evidence:** REPRODUCE's setup installs the Python environment and male tables, treating the FlyWire setup as historical. Every `BrianEngine.build`, including MaleCNS, unconditionally calls `load_shiu_model()`. It raises if `$FLYONENOMICS_CACHE_DIR/Drosophila_brain_model/model.py` is absent. `uv sync` and the male manifest downloader do not create that checkout. This is established by the call path, not a failed full-brain run.

**Exact proposed fix:** Add the existing pinned code-only setup before numerical commands:

```sh
git clone https://github.com/philshiu/Drosophila_brain_model "$FLYONENOMICS_CACHE_DIR/Drosophila_brain_model"
git -C "$FLYONENOMICS_CACHE_DIR/Drosophila_brain_model" checkout --detach 91bdd1e7dcf193f3e7ca5a8933497fcef63b7960
```

Explain that the male engine still imports upstream defaults; distinguish this dependency from female-connectome outcome data. Carry its licence/provenance into the release recipe. Do not tell readers to fetch unrelated multi-GB historical result archives merely to obtain this module.

### F04 — major — the central dopamine-to-spike mapping is not specified in the paper

**Owner:** paper.

**Locations:** `paper/manuscript.tex:47–53` (rewrite `:64–70`); `src/flyonenomics/neuromod/receptors.py:15–20`; `data/params-v0.2.yaml:61–78`; `src/flyonenomics/neuromod/state.py:301–313`.

**Evidence:** The paper gives clearance and ring receptor densities but omits occupancy affinities, threshold/gain equations, coefficients, clipping and the provenance of the reference concentration/non-transporter clearance. Those assumptions determine the perturbation's neural action. “Declared constants” and “placeholder densities” do not distinguish all of these from measured fly physiology. The code uses absolute occupancy, not change from WT occupancy.

**Exact proposed fix:** Add a compact Methods equation/table:
`D_i=(W D)_i`, `o1=D_i/(D_i+1.0 µM)`, `o2=D_i/(D_i+0.05 µM)` on exposed cells;
`Δv=-1.5 mV·r1·o1+2.0 mV·r2·o2`;
`gain=1+0.3·r1·o1−0.3·r2·o2`;
threshold clipped to `[−52,−30] mV`, gain to `[0.2,3]`.
State that occupancies and dopamine-induced threshold/gain changes are zero on unexposed cells (unmodified gain is one), that the reference 0.02 µM, 0.05/s non-transporter clearance, affinities and coupling coefficients are assumptions rather than measured adult-male fits, and that the three-seed calibration derives release coefficients, not receptor physiology. Cite the exact parameter table/code version. Do not recalibrate them.

### F05 — major — artificial-input amplitude and the limit of “incoming-event gain” are omitted

**Owner:** paper.

**Locations:** `paper/manuscript.tex:53,66` (rewrite `:70,83`); `src/flyonenomics/engine/brian_engine.py:485–500`; `src/flyonenomics/engine/models.py:25`; `src/flyonenomics/drive/paired_inputs.py:87–88`; `data/params-v0.2.yaml:22–25`.

**Evidence:** TuBu input is not specified by Hz alone. Each artificial event adds `w_syn*f_poi = 0.275*250 = 68.75 mV` to the model's synaptic state `g`, with zero added input delay. It is not a 68.75 mV instantaneous membrane-voltage step. Unlike recurrent `g += w*gain_i_post`, spike-list input uses `g += w_in`; background also has no dopamine gain multiplier. The phrase “incoming-event gain” can reasonably be read as affecting all incoming events.

**Exact proposed fix:** Add: “Each injected event increments the voltage-valued synaptic state g by 68.75 mV (250 times the base anatomical synapse weight), with zero external-input delay; membrane voltage follows the LIF equation. Dopamine gain multiplies recurrent graph events of either sign, not injected TuBu or background events.” Identify the inherited input-amplitude convention, without implying physiological stimulation strength. Keep the 1.8 ms delay explicitly as the recurrent-edge delay.

### F06 — major — the paper hides the fast positive action assigned to dopamine neurons

**Owner:** paper.

**Locations:** `paper/manuscript.tex:40–42,53,118`; `docs/malecns-port.md:109–116`; `scripts/adhd_study.py:117–119`; `src/flyonenomics/engine/models.py:25`; `src/flyonenomics/neuromod/state.py:220–222`.

**Evidence:** The run explicitly retains DAN fast synapses. The graph polarity convention assigns dopamine and other named monoamines a positive fast edge sign, while DAN spikes also drive the compartment chemistry. The paper's “named transmitter classes determine signs” does not disclose this substantive dual-action assumption. The research audit correctly explains that DAN activation changes ordinary synaptic events as well as release.

**Exact proposed fix:** Add: “We retain the inherited positive, fast graph-event convention for dopamine and other named monoaminergic outputs. Dopamine-neuron spikes therefore contribute both graph events and pool release; this is a modelling convention, not evidence for fast excitatory dopamine transmission at each such connection.” Include this in limitations and identify `dan_fast_synapses='retain'` in the methods supplement.

### F07 — major — the frozen decoder description does not match its distance calculation

**Owner:** paper (with design-document clarification).

**Locations:** `docs/adhd-study-design.md:41–43`; `scripts/adhd_analysis.py:24–38`; `paper/manuscript.tex:68` (rewrite `:85`).

**Evidence:** The design says “Euclidean distance” and defines margins from those distances. The code takes the **mean squared standardized difference across cells**, then wrong-minus-correct distance. Nearest-centroid class labels are unchanged by a monotone square/root transformation, but the margin magnitudes and their bootstrap intervals are not generally invariant. The paper does not state the distance formula, so the discrepancy is not resolved there.

**Exact proposed fix:** State the executed formula explicitly: `D_k=mean_i[((x_i−centroid_ki)/scale_i)^2]`, margin `D_wrong−D_correct`. Add a dated clarification beside the original frozen wording explaining that this was the implemented squared-distance rule already committed before outcomes. Keep the original freeze and selected pair intact; do not silently change code or recompute selection after outcomes.

### F08 — major on main; partly addressed in rewrite — qualify the exact sign test

**Owner:** paper.

**Locations:** `paper/manuscript.tex:88`; rewrite `:116`; `docs/adhd-study-results.md:19`; `paper/study-guide.md:110`; `scripts/adhd_analysis.py:102–107`.

**Evidence:** Main calls the test exact conditional on the axis but omits the sign-exchangeability null already stated in the results document/study guide. Enumerating all signs is computationally exact; independence of seed draws or a zero mean alone does not establish equiprobable signs under an arbitrary skewed difference distribution. The rewrite improves this by saying “if each seed's difference could equally have either sign.”

**Exact proposed fix:** Retain that explanation and add: “Exactness is conditional on the fitted axis and the independent sign-exchangeability/symmetry null; it is not an assumption-free test of a zero mean. The sign-test p values do not integrate template uncertainty.” Keep the frozen p values and Holm result unchanged. Apply the same scope to the follow-up's Monte Carlo version.

### F09 — major — a private prospective freeze is being presented as preregistration without its access status

**Owner:** paper (portfolio terminology should follow).

**Locations:** committed t-0096 `paper/manuscript.tex:95–96`; rewrite `:50,122–123,158`; `docs/adhd-confirm-design.md:1–9` on t-0095.

**Evidence:** The evidence supplied is a prospectively committed private Git design/plan, and the paper's availability section still calls the repository private. No registration repository, accession or independently accessible pre-outcome registration is identified. The rewrite defines “preregistration” merely as fixing the analysis before seeing outcomes, eliding the distinction between a prospective plan and its registration. This is not evidence that the freeze was retrospective.

**Exact proposed fix:** Use “prospectively frozen follow-up” and “design and analysis committed before follow-up outcomes in the then-private repository.” Give the freeze commit, dated execution record and eventual archive location. If an actual pre-outcome registration exists, cite its identifier and access/embargo status instead. Do not create a new registration now and call it pre-outcome.

### F10 — major — model-history pages mix superseded and current runtime state

**Owner:** docs.

**Locations:** `docs/malecns-rest.md:30–32,108–126,256–258`; `docs/malecns-port.md:434–443,616–637`; `docs/malecns-feasibility.md:5–27`; `docs/adhd-model-research.md:19,88`.

**Evidence:** The rest document says the dopamine table “remains null” and the chain is “computed, not adopted”; the port document repeats null-state assertions before eventually describing adoption. Current YAML has all 37 R/alpha/S/mode entries filled, and the paper uses the adopted male substrate. The research report does date its old snapshot, but a reader following README's current-model links must reconstruct several decisions to learn what actually runs. Feasibility still opens with “today” and the old 6.1M-edge-era situation.

**Exact proposed fix:** Add a short current-status banner to each historical page: “Historical measurement/port stage at [recorded date]. Runtime now uses rest:ed9b0a469d7a6b77 and the adopted tables; see [port adoption section] and [study design].” Change old-state descriptions to explicitly historical tense, preserving the measured numbers and frozen records. In the research report add a status note that its recommended affine primary became a secondary in the final frozen design. Do not rewrite history to imply the later tables were inputs to their own calibration.

### F11 — major — the anatomy figure is a UI screenshot, not a finished paper panel

**Owner:** figures.

**Locations:** `paper/manuscript.tex:134–136`; `figures/3d/male-cns-atlas.png`; `scripts/malecns_3d/viewer.html:23–45`; `scripts/render_malecns_3d.py:306`.

**Evidence:** The actual included PNG contains “Drag to rotate,” Save view/Reset view, checkboxes, Play/slider, a large DUMMY DATA banner and web-page statistics. The caption explains them honestly, but that does not make them useful scientific annotations. The 1600-CSS-pixel-wide page is rasterized at 2× and squeezed to a manuscript text width; 12-CSS-pixel labels become roughly 3.5 points at a 468-point width. This is a source-geometry estimate, not a final-PDF render claim.

**Exact proposed fix:** Export a dedicated static anatomy figure: brain/CNS panels, meaningful population key, scale bars, count/sample explanation and source attribution, with no interactive controls or synthetic-data UI. Preserve the full interactive atlas separately. Check the actual paper-width PDF after the figures lane integrates it. The 282 displayed versus 245 analysed ER distinction is correct and must remain.

### F12 — major — the humanizer pass has duplicated explanations and provenance rather than removing clutter

**Owner:** paper.

**Locations:** **rewrite** `paper/manuscript.tex:24,34,38–52,158–163`.

**Evidence:** Connectome/spiking-model definitions appear in the abstract, introduction and boxed glossary. The reproducibility paragraph repeats master/bootstrap seeds and pair hash twice, and the first-design commit twice; the next subsection repeats the substrate ID, run IDs and filenames yet again. It calls this a “reproducibility appendix” in references although it is an ordinary section. These are concrete duplication artifacts, not objections to plain language. The new endpoint explanation at rewrite `:99` also says **each trial** starts with A/B and receives AB, contradicting the eight-protocol table.

**Exact proposed fix:** Keep one short definition of each term in the introduction or glossary, not both. Replace the repeated provenance paragraphs with one compact table of experiment, seeds, executed revision, plan/pair/result hashes and command link. Put full commands in a clearly labelled supplement or actual appendix. Change the endpoint explanation to “For the paired-input history comparison, we compare A→AB and B→AB, with their corresponding A→off and B→off controls; the other trials provide calibration/control responses.” Retain all scientific bindings and input/vision caveats, but stop repeating the same inventory.

### F13 — minor — confirmation placeholders request the wrong statistical interpretation

**Owner:** portfolio.

**Locations:** t-0098 `docs/portfolio/summary.md:11,13`; `docs/portfolio/linkedin-posts.md:7`.

**Evidence:** They request confirmation “contrasts” and “corrected-test interpretation.” The frozen follow-up has **one primary**, no Holm adjustment, and confirms only with negative estimate plus two-sided Monte Carlo sign p<0.05. Its interval is descriptive for the decision. The placeholder could carry the pilot's two-test rule into the follow-up.

**Exact proposed fix:** Replace those phrases with “the vehicle genotype estimate, nominal interval, two-sided Monte Carlo sign p value, and the frozen negative-estimate/p<0.05 decision; one primary, no multiplicity adjustment.” Keep the hold on posting until records and approval exist.

### F14 — minor — demo narration misdescribes the visual encoding and its editing instructions conflict

**Owner:** portfolio.

**Locations:** t-0098 `docs/portfolio/demo-video.md:3,8,10`; `scripts/malecns_3d/viewer.html:116,128`.

**Evidence:** The narration says “colours and opacity ... show recorded model activity.” For recorded ER/TuBu cells hue identifies population; **opacity** encodes rate. Grey denotes anatomy-only, not low measured activity. The same document prohibits splicing the 73-second GIF, then calls for cutting to the statistical figure. These are correctable narration/instruction errors, not false raw activity data.

**Exact proposed fix:** Say “Population colours identify the cells; opacity shows their recorded spike rates. Grey cells are anatomy-only.” Specify that the source GIF remains unchanged and that title/result/end cards are separate editorial shots with disclosed added duration, or use overlays without changing its timing. Choose one instruction, not both.

### F15 — minor — engine documentation claims it never touches private Brian fields

**Owner:** model code.

**Locations:** `src/flyonenomics/engine/brian_engine.py:5,867–897`.

**Evidence:** The module header says “No private Brian2 field is touched.” Snapshotting imports `_get_all_objects`, invokes `clock._set_t_update_dt`, `Network._full_state`, and edits `_stored_state`. This is a documentation contradiction, not evidence that the pinned Brian runtime fails.

**Exact proposed fix:** Replace the sentence with: “Bank switching uses the public active flag. File-backed snapshots use Brian2 internals and are tied to the pinned Brian2 version.” No numerical change is needed. Because this module is source-hashed, route even this comment change through the source-binding/release workflow rather than altering an executed pin silently.

### F16 — minor — ambiguous claim of a manual literature review

**Owner:** docs.

**Location:** `REPRODUCE.md:230–232`.

**Evidence:** “This is a manual literature review” can imply a human review, while the paper and portfolio explicitly distinguish agent source checking from human verification. The intended contrast is with an algorithmic regeneration command.

**Exact proposed fix:** Use “This is an AI-assisted, source-checked research document, not an algorithm with a regeneration command; it is not represented as an independent human literature review.”

## Source-by-source paper claim check

Fresh requests were made to publisher/Crossref/Europe PMC/PMC endpoints on 25 September. HTTP 200 challenge pages were **not** counted as article access. Full text below means the relevant Methods/Results paragraphs were read, not that raw data were reanalysed.

| Paper / DOI | Claims checked and source evidence | Disposition |
|---|---|---|
| Van der Voet et al. 2016, `10.1038/mp.2015.55` | Europe PMC full-text XML, PMC4804182: Methods measure infrared activity and define sleep by five minutes of inactivity; pan-neuronal DAT/Cirl/Nf1 manipulations. Introduction supports the broad ADHD definition. Journal issue 21:565–573; 2015 online date does not make 2016 issue citation wrong. | Paper's locomotion/sleep-not-attention scope supported. Also establishes F01's dose-unit error in the parameter file. |
| Kume et al. 2005, `10.1523/JNEUROSCI.2048-05.2005` | Crossref title/authors/year, J Neurosci 25(32):7377–7384; PMC6725300 Methods and Fig. 1 Results: similar activity index per active period, more daily activity, less rest, DAT mutation/rescue. | Paper's phenotype distinction supported. No attention-deficit claim is established; no Kume 3-IY feeding experiment supports the parameter annotation. |
| Shin & Venton 2018, `10.1021/acs.analchem.8b02114` | PMC6135655 full text and Europe PMC abstract: isolated adult brain; fumin clearance slower; Results 68±15 s versus 16±3.7 s (abstract says 67); 100 µM synthesis inhibitor for 20 min reduces evoked DA. | Paper makes only the supported qualitative claims, not a dose, rescue or adult-compartment kinetic fit. Crossref attempt rate-limited; accessible article supplies bibliographic identity. |
| van Swinderen & Brembs 2010, `10.1523/JNEUROSCI.4516-09.2010` | PMC6633083 full text, “MPH effects”: improved optomotor/novelty selection and suppression; “did not significantly change the ongoing attention span defect,” random alternations retained. | Narrow manuscript rescue description supported. No wholesale attention-rescue claim. |
| Sun et al. 2017, `10.1038/nn.4581` | Crossref metadata, Europe PMC abstract, publisher preview/figure and supplement captions. Abstract says contralateral suppression occurs in both populations and history dependence is stronger in ring neurons; publisher captions identify upstream TB inputs. | Paper's qualitative motivation supported. Subscription full body unavailable; no numerical calcium magnitude, exact driver correspondence or fumin prediction is imported. “Depended more on earlier input” in the rewrite is more precise than implying history dependence exists only in ring cells. |
| Shiu et al. 2024, `10.1038/s41586-024-07763-9` | Crossref/publisher abstract and Europe PMC record PMC11446845: whole-brain LIF using connectivity and predicted transmitter identity; feeding/grooming predictions with experimental tests. Nature 634:210–219. | Paper's precedent and explicit nonvalidation of this dopamine layer are supported. A later PMC full-text request returned a challenge, not fresh full-text access. |
| Berg et al. 2026, `10.1016/j.cell.2026.08.015` | Crossref: Stuart Berg, title as cited, Cell 189:5504–5526.e15; CC BY 4.0 version-of-record licence. Europe PMC abstract describes entire brain/nerve cord, 166,700 neurons in the published reconstruction. Official `https://male-cns.janelia.org/` confirms v1.0 release 8 June 2026, paper news 3 September and collaborators. | Dataset identity/anatomical scope supported; manuscript appropriately uses adapter counts rather than calling 162,517 the release total. No wrong year/DOI found. |
| Vickrey, Xiao & Venton 2013, `10.1021/cn400019q` | Crossref and Europe PMC abstract: larval CNS, diffusion-corrected Vmax 0.11±0.02 µM/s and Km 1.3±0.6 µM. ACS Chem Neurosci 4(5):832–837. | Uptake provenance and adult-transfer limitation correct. The source does not validate the 0.05/s first-order placeholder. Full-text requests failed/challenged. |
| Frighetto et al. 2022, `10.3389/fphys.2022.849142` | Europe PMC full-text XML PMC9048027: DA enhances nicotine-evoked R2 response, reduces picrotoxin-evoked R5 response; R2 Dop1R1 RNAi removes enhancement; E-PG effects depend on receptor/timing. | Subtype caution supported. The paper does not claim a measured spike gain, D2 knockdown proof or matching subtype census. |
| Holm 1979 | Original JSTOR identity `https://www.jstor.org/stable/4615733`; article/PDF requests returned JavaScript challenges. Citation is Scandinavian Journal of Statistics 6:65–70, as in the existing audit. Code implements ordered step-down cumulative maximum, not Bonferroni-only or FDR. | Added on t-0096, absent on main. **Original full-text check remains open**; do not describe it as freshly full-text verified. |
| Efron & Tibshirani 1993, `10.1007/978-1-4899-4541-9` | Crossref confirms both authors, title and 1993. Springer US deposit represents the book; original Chapman & Hall imprint is not by itself an error. Available source audit records failed publisher access; alternative book PDF request also failed. Analysis uses whole-seed percentile quantiles, not BCa or a t interval. | General bootstrap attribution plausible and bibliographic identity verified; **original chapter check remains open**. No claim that the book chose these seeds/resample count/refitting scheme. |
| Ernst 2004, `10.1214/088342304000000396` | Crossref confirms Michael D. Ernst, title, Statistical Science 19(4), November 2004. Original Project Euclid endpoint returned an Incapsula challenge. | Sign-randomisation reference added on t-0096; **original method/plus-one coverage not verified**. Keep plus-one as the explicitly frozen algorithm, not a newly verified quotation from Ernst. |

The internal result/replay/repair/audit/execution citations identify the committed records, not external publications. The rewrite's anonymous “repository provenance” bibliography entries are less immediately locatable than the main file paths; F12's single provenance table should give each an unambiguous key.

**Remaining source work:** obtain readable originals for Holm, Efron–Tibshirani and Ernst and record the relevant sections/pages before claiming complete citation verification. I did not invent access or infer support from a resolving DOI. This is a verification limitation, not evidence those sources are wrong. The old research report's additional 14 biological sources were inspected as a reviewed source ledger, not all independently re-read in this pass; no exhaustive new literature review of those peripheral claims is claimed.

## Numerical and implementation ledger

### First-study results: no numerical discrepancy found

- All **27 named bindings** in `paper/result-bindings.json` resolve and format from the committed result using the actual filler, without running a model. All 10 CSV seed identifiers and all 70 numerical CSV cells exactly match their JSON counterparts.
- Independently enumerating the 1,024 signs from the committed differences gives 36 and 450 extreme assignments. The p values are respectively 0.03515625 and 0.439453125; Holm gives 0.0703125 and 0.439453125. No primary is multiplicity-supported.
- Vehicle genotype estimate −0.08515599493299299, interval [−0.1539537186226844, −0.020967576230697532]. Interaction +0.04587666888044713, interval [−0.05983270161072185, +0.15804000834263546]. Release gap −0.039279326052545846: smaller point magnitude, same sign, not evidence of rescue.
- Primary H means round to 0.0813094, −0.00384662, 0.0798973, 0.040618. Each displayed min/max is a seed range, correctly not a confidence interval.
- Affine mean −1.576517924498512×10^12; interval [−4.6755934442666445×10^13, +1.8148186381946543×10^13]. Unresolved cell counts 115,120,121,118,121,121,116,117,116,121. Its numerical failure is disclosed; no post-outcome repair is smuggled into the reported result. This is not meaningful evidence for/against an affine mechanism.
- 10,000 bootstrap draws; zero invalid fits; independent calibration-axis refit includes template uncertainty, not pair-selection uncertainty. These flags agree with the implementation. Intervals were checked against the recorded endpoints, **not recomputed from raw arrays**.
- Full-test H means recomputed from descriptive seed rows: 0.01851712, 0.00086088, −0.01384524, −0.00291613, matching all four hard-coded manuscript roundings.
- Mean EB end-settle values recomputed from committed drift rows: WT vehicle 0.020740929318076747 µM; fumin vehicle 0.050907316463883724 µM. Manuscript starts/end roundings match. The text correctly refuses to call two seconds equilibrium.
- All six output-file SHA-256 values in `adhd-study-analysis-execution.json` match the actual committed files (results, both descriptive records, secondaries, CSV, audit). Result hash is `47c6fc6e9ef83b13bdacc3af1b89b96f6b3b8d6f25c0bd1dd577d42326c0657e`; pair hash is `b941a440714244811e9ce305a45e678d5f9e5ea25a4a8f2ed638c0f630eff4dc`. Plan/executed-source identifiers agree with the audit and manuscript.

### Fixed numbers and methods

| Claim family | Checked against | Finding |
|---|---|---|
| 162,517 neurons, 25,120,209 pairs, 122,181,879 synapses; no extra weight cut; per-neuron unknown signs | Male port/substrate records, adapter conversion policy and transmitter/drive tables | Consistent. I did not regenerate the 24 GB source-table conversion. |
| LIF −52/−45 mV, 20/5/2.2/1.8 ms, 0.275 mV, dt 0.1 ms; 10 ms chemistry | Parameter rows, Brian construction, plain `lif` equations, study chunk loop | Numbers match. Methods completeness defects are F04–F06. In code g is voltage-valued, not a conductance in this substrate; refractory gating freezes the specified state equations and discards gated incoming writes. |
| Background 100 × 10 Hz, sensory 1 mV; other groups zero; GABA/Glu/His = 1/4/1, GABA→KC = 6; no threshold spread/mechanism | Male drive YAML, loaders, group overrides, explicit scale binding | Consistent. Frozen source convention is inherited, not tuned to this study's H. |
| 37 pools; 8 derived/29 source; R_min=0.5; three calibration seeds | Male dopamine YAML, K2r/port records, `Q=D_ref*(Vmax/(Km+D_ref)+k_ns)` | Recomputing `alpha=Q/max(R,0.5)` and `S=max(0,Q−alpha*R)` gives exactly the stored arrays (maximum residual zero). |
| f=0.37499999999999994; four initial concentrations; PB held at reference | Plan chemistry and `fixed_point`/`euler_step`/mask code | Match. Tiny last-bit differences exist across some compartments; the quoted representative values/“approximately” are appropriate. Units are µM and µM/s, with alpha per weighted spike. |
| 156 TuBu, 245 readout cells, four imposed positions, sigma 20°, cap 70 Hz, selection order, 1 Hz scale floor | Frozen plan/encoder/analysis | Counts/constants match; pair is (−50,+50). Preferred positions are not measured retinotopy. F07 corrects the distance definition. |
| 101–110 calibration, 201–210 main; 20 s calibration, 2/5/1/14 s trial, primary first 2 s, 100 ms descriptive bins; 8 × 4 arms | Plan, runner constants/protocols, analysis/descriptive code | Consistent; 320 main arms. The rewrite's universal trial description needs F12. |
| H, two contrasts, pairing, independently resampled calibration, cross-fitted affine secondary, duplicate held IDs excluded, unconstrained mixtures/J | `adhd_analysis.py`, design, record | Formula and implementation agree apart from decoder-description issue. Whole seeds, not cells/time bins, are inferential units. |
| 60 void partial arms; two replayed seeds reproduce ten NPZs but fail corrected RNG audit; remaining eight replays skipped; repaired main audit passes ten seeds | Replay, input-repair and exact-audit records | Honest manuscript account. I inspected receipts; did not independently replay those brains or certify raw bytes anew. |
| 40 follow-up seeds 301–340, one primary, 1,000,000 Monte Carlo draws, 10,000 bootstrap, RNG seeds 14620260926/14620260925 | t-0095 frozen design; t-0096 scaffold and rewrite | Methods numbers match. No follow-up numerical token was filled in the inspected draft. No Holm on this one-primary follow-up. |
| Figure populations 282/156/27/332/155-of-4,064 | Anatomy build receipt and actual PNG | Match. The activity exporter uses all 282 ER presynaptic-count columns and cross-checks the 245 trace subset; this is **not** a fabricated 37-cell extension. |
| README/REPRODUCE 24.38 GB, 165 MB geometry, 701 brain-s, 8,626.29 wall-s, 8 workers, about 94 GiB RAM | Manifest/build/rest receipts | Rounded values consistent. Main open problem is stale scope and incomplete dependency setup, not these costs. |

### Visual/claim-ceiling checks that passed

The four-panel PNG explicitly names seed 210, vehicle, matched final A+B input, 100 ms bin boundaries and the fixed 0–90 Hz opacity scale. CX dopamine is labelled group-total spikes/s, not per-cell; MB dopamine/KC are anatomy-only, not fabricated zeros. It does not show a drug rescue. The paper's design/history captions correctly separate nominal intervals from Holm tests, matched-seed lines from time courses, and anatomical context from functional evidence. Portfolio result prose does not turn a null-containing interval into equivalence. Static source/PNG inspection cannot certify the final paper's typography or browser/video behaviour.

## Already addressed or deliberately not called findings

- Main lacks Holm/bootstrap/randomisation citations; the committed t-0096 scaffold adds them. Do not open a duplicate “missing citations” fix; finish the access checks above.
- Main author line says Rolf, but the inspected rewrite already uses **Hasan “Rolf” Yildirim** in the author/contribution text. Verify citation metadata, README citation and the clean snapshot's author identity during integration, rather than treating the unmerged name change as absent work.
- Private code/raw hosting and human approval are openly pending, not falsely advertised as available. They remain release decisions; local box paths are not a public data-access solution.
- The affine secondary is a disclosed numerical failure. Preserve its historical result; neither a new clamp nor more flattering significance wording is a publication fix.
- A model with placeholder physiology can be published as a conditional computational experiment. This audit does not invent biological pass lines or require a positive effect.
- The requested source-module scan found no TODO/FIXME/HACK/breakpoint debris in `src/flyonenomics`; observed calibration progress prints were operational reporting, not stray debug output. I found no demonstrated new runtime defect in the inspected study path. This is not a whole-package correctness certification.

## Changes and handoff

**Trivial fixes applied:** none. Only this audit is committed; frozen/model/paper/portfolio/figure inputs are untouched.

Route F01/F15 to model/release provenance; F02/F03/F10/F16 to docs; F04–F09/F12 to paper; F11 to figures; F13/F14 to portfolio. Preserve executed hashes while correcting descriptions. The second paper pass should use the integrated immutable rewrite and reviewed confirmation bindings, including changes after `91cd901`, not the intermediate draft. Full gate and final rendered-PDF inspection remain with the review round.

## Second pass — 25 September 2026

### Scope and updated verdict

Checked the committed fixes, not their summaries: paper **`02a17fb`**, including `1466e5b`; docs/portfolio **`3016952`**; erratum/history banners **`ddafd3a`**. All file:line references below are at the named revision. These are separate branch tips, **not a tested integrated tree**. The paper was read end-to-end again, including the appendix, captions and bibliography. Its SHA-256 is `903f82127e3ec8aae24c105034ea2ddb206ac7dd181f3b8c63577d91d91ffc5a`.

**14 findings closed, one partly closed (F14), one open (F11).** Both original blockers have adequate committed corrections. The paper's Methods now disclose the substantive model assumptions and the conditional statistical interpretation. Remaining work is the anatomy figure, the small follow-on issues below, integration, and final confirmation/author review—not a new experiment or outcome-driven model change.

The first-study result JSON, analysis module and receptor implementation remain byte-identical to the first audit; all **27 original binding definitions are unchanged**. The binding file adds 13 confirmation fields, which this pass does not approve. No confirmation estimates, intervals, p values or generated conclusion text were checked. Pending-review figures/numbers in the study guide and portfolio are not promoted to reviewed evidence here.

### Closure ledger

| Finding | Status | Evidence and remaining action |
|---|---|---|
| **F01** false parameter provenance | **Closed, by erratum** | `ddafd3a:docs/errata.md:3,7–9,12` supplies the corrected EC50, food-to-brain and MPH provenance and says the old annotations are unreliable. `README.md:31`, `REPRODUCE.md:8`, and `docs/adhd-model-research.md:35` link it. Both parameter versions are byte-identical to the audited executed inputs. `3016952:release/public-export.toml:2–5` includes `docs/**` without excluding the erratum; actual integrated export still needs checking. Preserve those links when merging the independently edited front pages. |
| **F02** stale first-study status | **Closed** | `3016952:README.md:18–22,50–62` and `REPRODUCE.md:3–10,309–435` distinguish the completed ten-seed study from the under-review follow-up, retain Holm p=0.0703125, and provide the actual study commands/access limits. |
| **F03** missing Shiu checkout | **Closed** | `3016952:REPRODUCE.md:47–61` adds the mandatory code-only clone and pinned `91bdd1e…` checkout, explains the male engine's dependency, states the code/data licences separately and excludes unrelated historical archives. Closure is of the missing setup instruction, not certification of a full clean numerical reproduction. |
| **F04** missing dopamine-to-spike mapping | **Closed** | `02a17fb:paper/manuscript.tex:70–85,190` specifies exposure, absolute occupancies, affinities, threshold/gain equations and clipping, unexposed-cell behaviour, placeholder status and exact source locations. Values and signs agree with the inspected implementation for these study conditions. |
| **F05** input amplitude/gain scope | **Closed** | `02a17fb:paper/manuscript.tex:59,98` distinguishes the recurrent 1.8 ms delay from zero external-input delay, gives the 68.75 mV increment to **g**, denies an instantaneous membrane-voltage step, and excludes injected/background events from dopamine gain. |
| **F06** retained fast DAN action | **Closed** | `02a17fb:paper/manuscript.tex:57,170,190` explicitly calls the dual graph-event/pool action an inherited convention, repeats its physiological limitation, and records `dan_fast_synapses='retain'` in the appendix. |
| **F07** squared decoder distance | **Closed** | `02a17fb:paper/manuscript.tex:100` gives the executed mean-squared standardized distance and wrong-minus-correct margin. `docs/adhd-study-design.md:43` adds a clearly **post-outcome** dated clarification without removing the original Euclidean wording or changing the selected pair/code. |
| **F08** sign-randomisation assumptions | **Closed** | `02a17fb:paper/manuscript.tex:131,138` conditions inference on the fitted axis, independently drawn paired seeds and sign symmetry, excludes template uncertainty from the p value, and distinguishes enumeration from Monte Carlo. The original Ernst source-access check remains separately unresolved below; that is not a remaining misdescription of this null. |
| **F09** private freeze called preregistration | **Closed** | `02a17fb:paper/manuscript.tex:24,50,137–138,154,185,220` consistently uses a prospective freeze, discloses the then-private repository and gives freeze date/commit with archive pending. `3016952:README.md:58–62`, `REPRODUCE.md:432–435`, `docs/portfolio/summary.md:9` and `docs/portfolio/linkedin-posts.md:7` do likewise. No `preregis…` wording remains in those public copy files or the paper/guide/confirmation plotter inspected here. |
| **F10** historical status presented as current | **Closed** | `ddafd3a:docs/malecns-rest.md:3,30–33,123–129,259–261`, `docs/malecns-port.md:3–11,435–446`, `docs/malecns-feasibility.md:3,9–13,26–29`, and `docs/adhd-model-research.md:3,19,90` date the older states and link adoption/frozen studies. The research banner also says the recommended affine primary became an unstable secondary. The newly stale reproduction checksum is S02 below, not a change to scientific results. |
| **F11** anatomy screenshot unsuitable for paper | **Open** | `02a17fb:paper/manuscript.tex:205–206` still includes the old `male-cns-atlas.png`; `:194` still mentions dummy controls. At inspection t-0101's committed tip remained `fa697f9`, with its replacement figure uncommitted. Do not call unfinished rendering work a failed fix; inspect the integrated replacement, caption/counts and paper-width readability when it lands. |
| **F12** rewrite repetition and universal trial error | **Closed** | `02a17fb:paper/manuscript.tex:30,34,39–50` removes the duplicated explanatory passages while retaining the glossary. `:114` correctly restricts the endpoint to the four matched-history/control protocols. `:172–194` moves IDs/commands into an actual appendix and removes the duplicated seed/hash/run inventory identified earlier. Some reader-facing polish remains below, but the original concrete errors are fixed. |
| **F13** wrong follow-up multiplicity instruction | **Closed** | `3016952:docs/portfolio/summary.md:9` and `docs/portfolio/linkedin-posts.md:7` specify one primary, no multiplicity adjustment, and negative estimate plus two-sided Monte Carlo p<0.05. Pending-review numerical copy is explicitly labelled; its accuracy is deferred to the requested final check. |
| **F14** encoding and contradictory video edits | **Partly closed** | `3016952:docs/portfolio/demo-video.md:3,8–11` correctly assigns population to colour and rate to opacity, and consistently prescribes overlays on unchanged playback. However the latest “corrected” statistical-figure link at `:10` is broken (S01). Fix it and recheck against the eventual visual-lane timeline before closing the whole demo handoff. |
| **F15** false no-private-Brian-fields claim | **Closed, by erratum** | `ddafd3a:docs/errata.md:3,10,12` names the private snapshot APIs, limits the public-API claim to bank switching, and ties snapshots to the Brian pin. The engine source is byte-identical to the first audit; README/REPRODUCE links make the correction discoverable without invalidating frozen source hashes. |
| **F16** “manual” literature review | **Closed** | `3016952:REPRODUCE.md:250–254` says AI-assisted, source-checked, not an algorithmic regeneration and not independent human literature review. |

### Follow-on findings and whole-paper reading

**S01 — minor; portfolio; open — wrong relative figure path introduced in the fix.**
`3016952:docs/portfolio/demo-video.md:10` links `../../figures/adhd-study/primary-contrasts.svg`. From `docs/portfolio/` this resolves to repository-root `figures/adhd-study/`, which does not exist. The committed file is **`docs/figures/adhd-study/primary-contrasts.svg`**. Exact fix: use `../figures/adhd-study/primary-contrasts.svg`, or point to a verified replacement after the visuals merge. This is a filesystem-checked broken link, not an inference from naming.

**S02 — major; docs; open at integration — banner edits invalidate the advertised research-document hash.**
`3016952:REPRODUCE.md:248–249` and `ddafd3a:REPRODUCE.md:230–231` still promise `2d90766…` for `shasum -a 256 docs/adhd-model-research.md`. The new file in `ddafd3a` hashes to **`5b3f8e99ba01b23460c1b2fa9344ed54ddd14caa7e313ef269f8ae614d252687`**. The docs branch's own pre-banner hash is correct; simply merging both changes makes the recipe's current-file expectation wrong. Exact fix: label the old digest as the historical 22 September reviewed text and give the new digest for the banner/erratum version, or recompute the current-file digest after all integration edits. Do not replace frozen simulation hashes; this is only a documentation checksum. Recheck the figure hashes separately after t-0101 lands.

**S03 — minor; paper; open — the glossary misses the terms on which an undergraduate must rely.**
`02a17fb:paper/manuscript.tex:24,39–50,124–131` repeatedly uses **seed** and **vehicle**, but never defines either; even the bootstrap definition depends on “simulation seeds.” `:152` introduces **EB** without expansion. Exact fix: add “A seed labels one stochastic repeat; matched conditions share prescribed random input streams, not a different fly”; define “vehicle” on first use as **unreduced release (f=1), a control label, not an administered solvent**; write “ellipsoid-body (EB) dopamine concentration” on first use. These are explanatory edits, not new assumptions. In `:135`, replace the categorical “coefficients do not sum to one” with the precise “coefficients are **not constrained** to sum to one.”

**S04 — minor; paper; open — appendix font-size change escapes its intended scope.**
`02a17fb:paper/manuscript.tex:175–177` issues an ungrouped `\small`; there is no `\normalsize` or group close before data/code availability (`:196`), author disclosure (`:199`) or bibliography (`:228`). Thus the smaller text declaration is not limited to the technical appendix. Exact fix: group the appendix's small-type block, or restore normal size before the back matter. This is a TeX-source scope finding; no final-render typography approval is claimed. The existing intermediate build log had one underfull-box warning and no overfull-box warning; that is not a reason to invent a table-overflow defect.

**Developer identifiers and prose:** a scan and manual reading found **no SPEC-P2 IDs, decision IDs, run IDs, substrate hashes, source hashes, host names or local paths in the scientific text before `\appendix`**. The two large RNG initialization integers remain in Methods `:138`; move them to the provenance table if Rolf wants all execution-only identifiers out of the narrative. Sample sizes, 101–110/201–210/301–340 seed labels and scientific constants are not themselves stray development task IDs. The availability paragraph `:197`, although placed after the appendix declaration, still contains `compute host`, local paths and run labels; keep those in a clearly bounded technical provenance subsection, and make the reader-facing availability statement simply describe private access/public hosting status.

The repeated provenance paragraph and incorrect all-trials explanation are gone. No new biological or treatment overclaim was found in the unfilled manuscript. The first result remains nominal-only, the interaction remains “no detected difference,” and the affine failure is not rehabilitated as mechanistic evidence. For readability, replace unexplained “No optic exemption” (`:59`) with “The transmitter multipliers also apply to optic-lobe edges,” and either explain or move the unrelated sugar-reflex availability sentence (`:61`) to the technical limitations. The short “what this can and cannot tell us” paragraph largely repeats the abstract/discussion limits; trimming it is optional, not a reopened blocker. Keep the explicit TuBu/no-vision limit. The detailed source strings and 16-digit floating-point constants belong in the appendix if the main Methods still feel overloaded; their recorded values must not change.

### Renewed original-source access

Fresh direct HTTP requests on 25 September 2026 distinguished real PDF bytes/text from HTTP-200 challenge pages. Readable copies were parsed locally with macOS PDFKit; no browser session, challenge circumvention, package installation or paid access was used. Only access metadata and claim checks are committed, not copyrighted articles.

| Source | What was accessible this time | Claim check / remaining boundary |
|---|---|---|
| **Holm 1979** | JSTOR article and PDF endpoints (`https://www.jstor.org/stable/4615733`, `https://www.jstor.org/stable/pdf/4615733.pdf`) again returned the same 3,038-byte client-challenge HTML, not an article. A scholarly-indexed University of São Paulo mirror, **`https://www.ime.usp.br/~abe/lista/pdf4R8xPVzCnX.pdf`**, returned a readable seven-page PDF: JSTOR cover plus original journal pp.65–70. The scan identifies Sture Holm, *Scandinavian Journal of Statistics* 6(2), 1979. | **Original-method check now satisfied for the paper's use.** Read §2, pp.66–67: ascending observed levels, thresholds α/n, α/(n−1), …, stop at the first nonrejection; Theorem 1 gives familywise type-I protection. The two-test implementation and “nominal but not Holm-supported” interpretation agree. This source does not select the experiment's α or number of primaries. PDF SHA-256 `4317a0d1555dad949dc1760605d925ba20037402827741fdf99cd8ea37e80c46`. |
| **Efron & Tibshirani 1993** | The old Springer book endpoint `https://link.springer.com/book/10.1007/978-1-4899-4541-9` still returned 404. Taylor & Francis's `10.1201/9780429246593` book landing page was reachable; a request to `https://www.tandfonline.com/doi/pdf/10.1201/9780429246593` returned 403 rather than book text. **`https://www.hms.harvard.edu/bss/neuro/bornlab/nb204/statistics/bootstrap.pdf`** returned an eleven-page scan of the original book's front matter and opening chapters, not the complete book. The copyright page identifies the 1993 Chapman & Hall original and 1998 CRC reprint, ISBN 0-412-04231-2. | **Original support for the narrow bootstrap description now obtained.** Printed p.5 describes resampling with replacement and taking the 25th/975th ordered replicates out of 1,000 for a rough 95% interval; p.7 explicitly identifies the percentile method and distinguishes BCa; pp.12–13 describe n draws with replacement and recalculating the statistic. These support the manuscript's generic resampling/percentile explanation. **Chapter 13 and a complete original-book read remain unavailable**, so no claim of having verified its detailed coverage theory, this study's whole-seed hierarchy or calibration-axis refitting is made. PDF SHA-256 `aa54f428c64025ad8a276cfa99682a6d9f1c2813c85cce9ff853906f74f51554`. |
| **Ernst 2004** | DOI resolution, modern Project Euclid `.full` and `.pdf` endpoints for `10.1214/088342304000000396`, and the original Crossref-linked `https://projecteuclid.org/download/pdfview_1/euclid.ss/1113832732` all returned roughly 1.2 KB of Incapsula challenge HTML. Crossref again confirmed the bibliographic identity. OpenAlex pointed back to the same publisher PDF and an old academic mirror, `https://statweb.calpoly.edu/bchance/csi/ernst-2004.pdf`; the latter failed DNS resolution. | **Original text still inaccessible; method-source check remains open.** No sign-symmetry or plus-one paragraph from Ernst was read. The code/design establish what this project did, not what Ernst wrote. Keep the honest access limitation in `paper/references-verified.md`; obtain a readable original before calling that citation full-text checked. In the meantime, attach the Ernst citation to the general sign-randomisation method, not specifically to an unverified plus-one attribution at manuscript `:138`. |

**Handoff:** update `paper/references-verified.md` with the new Holm and limited Efron–Tibshirani access record; do not leave its blanket “none accessible” statement as the latest project-level verification status. Preserve the remaining Ernst limitation. Merge the independent docs/erratum fixes without losing status text or erratum links, correct S01/S02, finish F11 and make the small paper edits. This pass changed only the audit/report, ran no simulations or full gate, and did not fill or approve confirmation outcomes. Final integrated PDF/figure and confirmation checks remain pending.

### Test-policy update — 25 September 2026

Rolf's new rule supersedes the earlier full-gate handoff for this paper/docs/figure work: no new tests and no test suites. Check changes by inspection or, for the paper, the LaTeX build. This lane added **no tests** and ran **no test suites**; no test removal was needed. Its only tracked addition is this audit. The policy update was checked by reading the diff, without a build or test run.
