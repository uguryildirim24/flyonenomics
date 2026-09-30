# Citation and source audit — 23 September 2026

The biological sources reuse the reviewed claim-checked access record in
`docs/adhd-model-research.md`; the original two additional papers were checked
as described below. Three statistical-method sources were added for this follow-up;
access limits are recorded explicitly rather than called full-text verification. This is not a claim of raw-data
reanalysis or human literature review.

The inherited source document was read at repository revision
`287ffa4275e22a07fb59d150024b941c150d47ac`. Its FT/A labels mean relevant full
text / abstract, respectively. No abstract-only source is used for an
unreported numerical result. The present lane also checked every DOI's
resolution; publisher access blocks are distinguished from an unresolved DOI.

## Reused verified literature

| Paper / research-doc source | Claim used, and checked scope | DOI check in this lane |
|---|---|---|
| Van der Voet et al. 2016 [2], FT, PMC4804182 | ADHD-associated gene manipulations and activity/sleep assays; not visual attention or impulsivity assays. | `10.1038/mp.2015.55` → Nature, HTTP 200. Crossref confirms title, 21:565–573. |
| Kume et al. 2005 [1], FT, PMC6725300 | Fumin's daily activity/sleep phenotype; activity during active periods similar, not faster movement whenever awake. | `10.1523/JNEUROSCI.2048-05.2005` → J. Neurosci. DOI lookup, HTTP 302; publisher subsequently blocks automated access (403). Crossref confirms title and author. |
| Shin & Venton 2018 [10], FT, PMC6135655 | Adult isolated-brain clearance is slower in fumin; 3-IY reduces evoked dopamine; neither establishes attention rescue or a model dose. | `10.1021/acs.analchem.8b02114` → ACS, HTTP 302, publisher 403. Crossref confirms title and authors. |
| Van Swinderen & Brembs 2010 [6], FT, PMC6633083 | MPH improved some optomotor/novelty endpoints but did not significantly correct ongoing alternation dynamics. | `10.1523/JNEUROSCI.4516-09.2010` → J. Neurosci., HTTP 302, publisher 403. Crossref was rate-limited (429); title/claim verification is inherited from the reviewed record, not falsely called a fresh FT read. |
| Sun et al. 2017 [8], A, PubMed 28604683 | Competing-stimulus suppression in TuBu and ring populations; stronger, history-dependent ring suppression. No calcium magnitudes or exact driver match asserted. | `10.1038/nn.4581` → Nature, HTTP 200; Crossref confirms Yi Sun, title, 20:1104–1113. |
| Vickrey, Xiao & Venton 2013 [9], A, PMC3656763 | Uptake constants originate in larval CNS, not adult male EB physiology. | `10.1021/cn400019q` → ACS, HTTP 302, publisher 403; Crossref title/author confirmed. |
| Frighetto et al. 2022 [16], FT, PMC9048027 | Receptor/subtype-dependent DA modulation cautions against treating one ER density rule as validated physiology. No calcium-to-spike conversion asserted. | `10.3389/fphys.2022.849142` → Frontiers full text, HTTP 200; Crossref title/author confirmed. |

A resolver redirect to the correct publisher is a resolving DOI even when that
publisher blocks automated full-text access. Reused biological claims rest on
the already reviewed access record, not on DOI metadata alone.

## Additional sources checked here

### Shiu et al. 2024

- **DOI:** <https://doi.org/10.1038/s41586-024-07763-9> resolved HTTP 200 to
  <https://www.nature.com/articles/s41586-024-07763-9> (cookie-query suffix).
- Crossref metadata endpoint for the DOI returned title, first author Philip K.
  Shiu, year, *Nature* 634:210–219 and the publisher abstract.
- The publisher article/abstract was read for the use made here: a whole-brain
  leaky integrate-and-fire model based on synaptic connectivity and transmitter
  identity, with feeding/grooming predictions and optogenetic/behavioural
  validation. The page identifies the FlyWire collection; this project's port
  record separately documents the FlyWire arrays and upstream model lineage.
- **Claim limit:** this precedent motivates connectome-constrained modelling;
  it does not validate our male dopamine layer, operating state, history assay
  or behaviour. No performance percentage is imported into the paper.

### Berg et al. 2026 / MaleCNS v1.0

- **DOI:** <https://doi.org/10.1016/j.cell.2026.08.015> resolved HTTP 200 to
  <https://linkinghub.elsevier.com/retrieve/pii/S0092867426009426>, naming
  *Sexual dimorphism in the complete Drosophila male central nervous system
  connectome*.
- Crossref confirms first author Stuart Berg, *Cell* 189:5504–5526.e15, 2026,
  and the CC BY 4.0 version-of-record licence. Crossref had no abstract.
- The Cell full-text endpoint returned 403. The anatomical claim was checked
  against the authors' official Janelia project summary:
  <https://www.janelia.org/project-team/flyem/male-cns-connectome>, HTTP 200.
  It explicitly describes the male central brain, optic lobes, ventral nerve
  cord and intact neck connective in one reconstruction.
- <https://male-cns.janelia.org/>, HTTP 200, records v1.0 release on 8 June 2026,
  paper publication on 3 September 2026, collaborators and the CC-BY dataset.
- **Claim limit:** anatomy, dataset identity and attribution only. This paper
  does not assert an experimentally validated male resting state, measured
  dopamine kinetics or functional model from Berg et al. Our retained graph
  count is the repository adapter's count, not a substituted published total.

## Statistical-method sources added for the paper

- **Holm (1979)**, *A simple sequentially rejective multiple test procedure*,
  *Scandinavian Journal of Statistics* **6**, 65–70. The original journal pp.65–70
  were read in the University of São Paulo scan
  <https://www.ime.usp.br/~abe/lista/pdf4R8xPVzCnX.pdf> during the 25 September
  second publication audit (`docs/audit/slop-audit.md`; PDF SHA-256
  `4317a0d1555dad949dc1760605d925ba20037402827741fdf99cd8ea37e80c46`).
  Section 2, pp.66–67, orders observed levels, compares them in succession
  with α/n, α/(n−1), etc., and stops at the first nonrejection; Theorem 1
  establishes familywise type-I protection. The JSTOR endpoint itself served
  a client challenge. This supports the named step-down two-test correction,
  not the project's choice of α or its number of primary tests. The follow-up
  has one primary and no Holm adjustment.
- **Efron & Tibshirani (1993)**, *An Introduction to the Bootstrap*, Chapman &
  Hall. Original-book bibliographic identity and both authors/year checked against
  publisher-registered Crossref metadata at
  <https://api.crossref.org/works/10.1007/978-1-4899-4541-9> on 25 September.
  The 25 September second publication audit read an eleven-page scan of the
  original book's front matter and opening chapters at
  <https://www.hms.harvard.edu/bss/neuro/bornlab/nb204/statistics/bootstrap.pdf>
  (PDF SHA-256 `aa54f428c64025ad8a276cfa99682a6d9f1c2813c85cce9ff853906f74f51554`).
  Its copyright page identifies the 1993 Chapman & Hall original and 1998 CRC
  reprint. Printed p.5 describes replacement resampling and an ordered-replicate
  interval, p.7 names the percentile method, and pp.12–13 describe repeated
  n-draw resampling and statistic recalculation. The complete book, including
  chapter 13, was not accessible; this supports the general percentile method,
  not the project's resample count, whole-seed pairing or axis refit.
- **Ernst (2004)**, *Permutation Methods: A Basis for Exact Inference*,
  *Statistical Science* **19**(4), DOI
  <https://doi.org/10.1214/088342304000000396>. Title, author, journal,
  volume, issue and date checked against the journal's Crossref deposit on
  25 September. The original Project Euclid article and PDF URLs served an
  automated client challenge rather than content. This is a methods reference
  for the general sign-randomisation method, not for the Monte Carlo draw
  count, fixed seed, sign-symmetry assumption or plus-one correction. Those
  procedural details come from the project's frozen design and code. During
  the second audit, Project Euclid's current and original PDF endpoints still
  served client challenges; the old academic mirror failed DNS resolution.

**Access caveat:** Holm's original article and Efron–Tibshirani's original
opening chapters were checked in the second publication audit, not the
complete bootstrap book. Ernst's original text remains inaccessible; its
method-source claim needs full-text verification before submission.

## Body model, physics engine, and supplement sources (checked 30 September 2026)

Crossref DOI work records were queried directly for metadata (not full text):

- Wang-Chen S, Stimpfling VA, Lam TKC, Özdil PG, Genoud L, Hurtak F, Ramdya P (2024), “NeuroMechFly v2: simulating embodied sensorimotor control in adult Drosophila,” *Nature Methods* **21**(12):2353–2362, [doi:10.1038/s41592-024-02497-y](https://doi.org/10.1038/s41592-024-02497-y). Crossref lists these seven authors, title, journal, issue, pages and publication date 12 November 2024. Project body lineage: `docs/courtship-body.md:18` identifies FlyGym 1.1.0's NeuroMechFly v2. The citation credits the virtual body, not any biological inference from its playback.
- Todorov E, Erez T, Tassa Y (2012), “MuJoCo: A physics engine for model-based control,” *2012 IEEE/RSJ International Conference on Intelligent Robots and Systems*, pp.5026–5033, [doi:10.1109/IROS.2012.6386109](https://doi.org/10.1109/IROS.2012.6386109). Crossref confirms all authors, title, proceedings, date October 2012 and pages. Project body documentation identifies MuJoCo as the simulator; this reference credits the engine, not neural validation.
- Nordlie E, Gewaltig M-O, Plesser HE (2009), “Towards Reproducible Descriptions of Neuronal Network Models,” *PLoS Computational Biology* **5**(8):e1000456, [doi:10.1371/journal.pcbi.1000456](https://doi.org/10.1371/journal.pcbi.1000456). Crossref confirmed authors, journal, article and publication date 7 August 2009. Cited for the supplement's model-description format.
- Zhang HG et al. (1995), “Subunit composition determines picrotoxin and bicuculline sensitivity of Drosophila gamma-aminobutyric acid receptors,” *Molecular Pharmacology* **48**(5):835–840, PMID 7476913. PubMed metadata/abstract checked in the pre-publication review t-0194: supports homomer picrotoxin sensitivity, **not** the unverified 1 µM potency or a concentration axis. The manuscript no longer makes those claims.

## Internal-method sources (not external biological claims)

The paper transcribes SPEC-P2 §10 items 149–157; `docs/malecns-port.md`,
`docs/malecns-rest.md`, `docs/3d-model.md`; and the experiment branch's
`docs/adhd-study-design.md`, `docs/adhd-study-part-a.md`,
`scripts/adhd_analysis.py` and result writer in `scripts/adhd_study.py`, inspected
at `5c39f2ecf92764c78f560267e465988484b88cd5`. Those sources were not edited.
The rest document's earlier “computed, not adopted” language is superseded by
item 157 and the port document's final adoption section, not silently treated
as the current runtime state.

Human verification is not invented. Rolf's documented choices are distinguished
from agent source checking and agent computational review in the manuscript.

## GPU software and agreement sources cited in the manuscript

These verification notes are drawn from `docs/research/software-citations.md`, which
checks publisher/Crossref metadata or the primary documentation. The agreement
wording separates the project's identical-event replay from independent-stream
experiment effects; interval overlap is descriptive, **not** a statistical
equivalence test. The two comparison-simulator papers are cited for cross-engine
method context, not to claim their benchmarks were reproduced here.

- **Stimberg, Brette & Goodman (2019), Brian 2.** *eLife* 8:e47314,
  [doi:10.7554/eLife.47314](https://doi.org/10.7554/eLife.47314).
  DOI redirects to eLife (HTTP 200); Crossref confirms title, authors, volume 8
  and article e47314. PubMed 31429824; PMCID PMC6701882. Supports the name
  of the CPU reference simulator, not the male model's biological validity.
- **Salmon, Moraes, Dror & Shaw (2011), Random123/Philox.** *SC '11*, article
  16:1–12, [doi:10.1145/2063384.2063405](https://doi.org/10.1145/2063384.2063405).
  DOI redirects to ACM; Crossref confirms authors, title, proceedings, article
  and pages. The engine's Philox4x32-10 choice was checked in kernel source in
  the software audit; the citation supports the counter-based algorithm.
- **Okuta, Unno, Nishino, Hido & Loomis (2017), CuPy.** *NIPS LearningSys
  Workshop*, paper 16, four pages. [Primary workshop PDF](http://learningsys.org/nips17/assets/papers/paper_16.pdf)
  verified HTTP 200; unindexed workshop paper with no registered Crossref DOI.
  CuPy supplies array management and the RawModule runtime interface.
- **NVIDIA Corporation (2024), NVRTC.** *NVIDIA CUDA Runtime Compilation
  (NVRTC) Library*, CUDA Toolkit Documentation v12.6,
  [official documentation](https://docs.nvidia.com/cuda/nvrtc/index.html)
  verified HTTP 200, accessed 26 September 2026. The software audit records
  the project's CUDA Toolkit 12.6.3 environment. This documents runtime
  compilation, not performance.
- **Alevi et al. (2022), Brian2CUDA.** *Frontiers in Neuroinformatics* 16:883700,
  [doi:10.3389/fninf.2022.883700](https://doi.org/10.3389/fninf.2022.883700).
  DOI redirects to Frontiers full text (HTTP 200); Crossref confirms five
  authors, title, journal, volume and article. PubMed 36389052; PMCID PMC9659850.
  A verified cross-engine comparison precedent, not a claim of general
  equivalence for our CUDA engine.
- **Knight & Nowotny (2018), GeNN comparison.** *Frontiers in Neuroscience*
  12:941, [doi:10.3389/fnins.2018.00941](https://doi.org/10.3389/fnins.2018.00941).
  DOI resolves to Frontiers; Crossref confirms title, authors, volume and
  article. PubMed 30618565; PMCID PMC6302068. Cross-platform population
  measures motivate describing stochastic runs via effects rather than aligned
  spikes; our interval overlaps alone do not meet an equivalence criterion.

A 26 September 2026 Scite and Crossref status check
covered all 28 registered DOIs in the paper's verified-source list and the
software citation audit (Shiu shared between the lists). Every checked DOI
returned a work record and neither service returned a retraction, correction
or expression of concern on that date; this is a search result, not a
permanent guarantee. CuPy, NVRTC and Holm have no registered DOI in those
lists and were not part of the DOI status check.
