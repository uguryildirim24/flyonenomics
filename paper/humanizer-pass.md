# Humanizer pass on the manuscript

One pass over the prose of `paper/manuscript.tex` (abstract, sections, key-terms box, figure captions) using the humanizer skill (v3.0.0) and nothing else. Pattern numbers (§) are the skill's numbered list. Line numbers are `paper/manuscript.tex` lines; the pass kept one paragraph per line, so no line moved.

Unchanged, checked by script against the pre-pass file: all 252 numbers, the 15 citation keys, 4 `\ref`, 4 `\label`, 9 `\result{}` slots (equal to `result-bindings.json`), 4 figure includes, 13 math spans, the title, author line and preamble, and the bibliography byte for byte. "no detected difference" occurs as often as before in every section. Every results section (dopamine, knockout tour, courtship, GABA, virtual body) still says that input is injected and the fly does not see; the introduction and methods keep theirs too.

Words (abstract through figure captions, bibliography excluded, each result slot counted as one word): 4,150 before, 4,104 after.

## Tells found, by pattern

Each instance is counted once, under the pattern its edit addressed. "Found / changed": a found tell left as it was is listed under "Left alone" below.

| § | Pattern | Found | Changed |
|---|---|---|---|
| 1 | Not X but Y, and X rather than Y | 60 | 17 |
| 2 | One-line closers and fragments | 7 | 7 |
| 3 | Sayings that sound deep | 8 | 8 |
| 4 | Staged run-up before the point | 5 | 5 |
| 5 | Arguing with no one | 2 | 2 |
| 6 | Forced triads, paragraph-scale parallels | 2 | 2 |
| 7 | Repeated sentence openings | 3 | 3 |
| 11 | Passive voice hiding the actor | 3 | 3 |
| 12 | Overused AI words | 1 | 1 |
| 13 | Inflated significance | 1 | 1 |
| 16 | Sales language | 1 | 0 |
| 19 | Bold or emphasis as decoration | 12 | 2 |
| 25 | Writing about the previous version | 1 | 1 |
| | **Total** | **106** | **52** |

None found: §8 dashes (the prose had none; see "Left alone" for the markup dashes), §9, §10 (every hyphenated pair sits before its noun), §14, §15, §17, §18, §20 to §24. The §12 hits `glutamate-gated`, `Highlighted routes` (a figure's highlighting) and the `Key terms` box label are technical or structural uses and are not counted.

The "These are ..." caveat opener recurred six times across the paper (lines 34, 38, 49, 71, 76, 100). Most of those sentences are counted under §1 above; five openers were varied and the GPU one at line 38 was kept.

## Tells found, by section

| Section | Tells (found/changed) |
|---|---|
| Abstract | §1 1/1, §4 1/1 |
| Introduction | §1 6/2 |
| Key-terms box | §1 3/0 |
| Methods in brief | §1 6/0, §2 1/1, §11 2/2 |
| Dopamine | §1 5/2, §2 2/2, §3 1/1, §7 1/1, §11 1/1 |
| Chemical knockout tour | §1 5/2, §2 1/1, §3 2/2, §4 1/1, §13 1/1 |
| Courtship circuit | §1 3/2, §2 1/1, §5 1/1, §12 1/1 |
| GABA concentration-response | §1 12/0, §2 1/1, §3 2/2, §4 1/1, §7 2/2, §19 1/1 |
| Virtual body | §1 4/2, §3 1/1, §19 1/1 |
| Discussion | §1 5/1, §3 2/2, §4 2/2, §5 1/1, §6 2/2, §16 1/0 |
| Limitations | §1 1/0 |
| Data, attribution and AI use | §1 1/0 |
| Figure captions | §1 3/0, §2 1/1, §25 1/1 |
| Whole paper | §1 5/5 (run-in label "What it means, and what it does not." ×5), §19 10/0 (bold run-in labels "Question and approach." and "What we found." ×5 each) |

## The 15 largest changes

1. Abstract, line 17 (§4). Before: "Can a simulated male fly nervous system help us ask pharmacology questions without confusing a model with an animal?" After: "We asked whether a simulated male fly nervous system can help with pharmacology questions without confusing a model with an animal."
2. Abstract, line 17 (§1, closer). Before: "The virtual body is a playback, not a behavioural outcome." After: "The virtual body only plays back recorded spikes, so it shows no behavioural outcome."
3. Introduction, line 23 (§1, closer). Before: "Anatomy supplies possible routes for an effect, not a measured dose response or a guarantee that any simulated spike predicts a living fly's response." After: "Anatomy shows possible routes for an effect. It gives no measured dose response, and it does not guarantee that any simulated spike predicts a living fly's response."
4. Methods, line 38 (§2). Before: "... They exclude network construction, startup and a closed-loop body. This checks a computational implementation, not biological validity." After: the sentence now follows the spike match it describes: "... matched Brian2 at the 0.1 ms output grid, with one network per run. That match tests the computational implementation, not biological validity."
5. Dopamine, line 41 (§3, §1, §7). Before: "If we remove that cleanup in the simulation, dopamine remains available differently, but the question is what, if anything, changes in a specified downstream neural response. We chose a history test rather than calling any increase in spikes ``attention.''" After: "Removing that cleanup in the simulation changes how dopamine remains available, and we ask what, if anything, then changes in a specified downstream neural response. We use a history test and do not call any increase in spikes ``attention.''"
6. Dopamine, lines 43 and 49 (§2, §1). Before: "Repeating a simulation with different random input is useful for estimating its noise, but it cannot stand in for collecting new animals." (line 43) and "These are repeated simulations of one network, not independent flies." (line 49). After, once at line 49: "The runs repeat one simulated network with different random input, which estimates its noise but cannot stand in for collecting new, independent flies."
7. Knockout tour, line 52 (§4). Before: "Before using a simulated brain to explore drug-like manipulations, we should ask a simpler question: does its activity react intelligibly when broad chemical pathways are removed?" After: "Before using the simulated brain for drug-like manipulations, we checked whether its activity reacts intelligibly when broad chemical pathways are removed."
8. Knockout tour, line 60 (§1, §13, §3). Before: "... are useful checks that altering the network is not merely changing a label on a plot. ... The unresolved histamine and dopamine averages deserve to stay visible. They could reflect ... The unlabelled-class result is also a reminder that gaps in transmitter annotation can have consequences." After: "... are useful checks: altering the network does change its simulated activity. ... We keep the unresolved histamine and dopamine averages in view, since they could reflect ... The unlabelled-class result shows that gaps in transmitter annotation can have consequences."
9. Courtship, line 65 (§1, §12, §5). Before: "A matched random-neuron stimulation comparison helps ask whether a downstream change is specific to the selected entry point rather than merely adding drive somewhere in the graph. ... We tracked both group firing and whether the proposed ordered chain of first spikes was actually present, rather than drawing a behavioural arrow from anatomy alone." After: "A matched comparison that stimulates random neurons instead asks whether a downstream change is specific to the selected entry point or would follow from adding drive anywhere in the graph. ... We tracked group firing and checked whether the proposed ordered chain of first spikes was present."
10. Courtship, line 71 (§1, §2). Before: "These are circuit firing changes, not singing, fighting or a visual stimulus. The playback below is a way of displaying some of these spikes; it cannot repair the missing behavioural evidence." After: "The changes are in circuit firing: there was no singing, fighting or visual stimulus. The body playback in the next section displays some of these spikes but cannot supply the missing behavioural evidence."
11. GABA, lines 86 and 88 (§2, §3). Before: "This is partial model rescue, not receptor recovery or seizure treatment." (line 86, after the GPU sentence, so "This" had no clear subject), "Raising a different inhibitory conductance can offset some extra firing without restoring the blocked GABA channel." and "The useful pharmacology lesson is to specify what concentration means, show all sampled levels and separate an observed half-change from an unstable fitted half-effect." (line 88). After, at line 88: "The GluCl result is partial model rescue, not receptor recovery or seizure treatment: raising a different inhibitory conductance can offset some extra firing without restoring the blocked GABA channel. For pharmacology, a model dose curve should state what its concentration means, show every sampled level and keep an observed half-change separate from an unstable fitted half-effect."
12. Virtual body, line 97 (§3, §16). Before: "a compelling picture can make an implemented hypothesis easier to inspect without making it biologically true." After: "they make an implemented hypothesis easier to inspect, but they do not make it biologically true."
13. Discussion, line 100 (§4, §6). Before: "Taken together, these studies show why ..." followed by five sentences each opening "The [study] ...". After: "These studies show why ..."; the five summaries keep their claims but no longer share one opening ("In the knockout tour, ...", "Courtship stimulation reached ...", "Playing spikes into the virtual body made ...", then "Together they are complementary checks ...").
14. Discussion, line 102 (§5). Before: "For a pharmacology student, the dopamine null is not a failed project to hide." After: "For a pharmacology student, the dopamine null is a result worth reporting."
15. Discussion, line 108 (§3, §1). Before: "The boundary between a claim about flies and a claim about this model lies at the unvalidated translations." and "The next step is not a more confident behavioural label for the same traces, but an independently constrained prediction that could fail when compared with a living fly." After: "Several unvalidated translations separate a claim about this model from a claim about flies." and "The next step is an independently constrained prediction that could fail when compared with a living fly."

Headings reworded, subject kept: "Chemical knockout tour: useful checks, not validation" became "Chemical knockout tour: a stress test of the model" (the text's own term at line 52; "They do not validate ..." stays at line 60). "A virtual body, not observed behaviour" became "A virtual body replaying recorded spikes" (the no-behaviour claim stays at lines 17, 93 and 97). The run-in label "What it means, and what it does not." became "What it means." in all five results sections.

## Claims merged or cut, and where each survives

- Line 43, noise-versus-new-animals sentence: merged into line 49 (item 6).
- Line 49, "Nor does the release comparison establish rescue.": joined to the sentence before it; also stated at line 45 ("no established rescue").
- Line 65, "rather than drawing a behavioural arrow from anatomy alone": cut as a rejected option nobody proposed (§5). That anatomy alone does not establish behaviour stays at line 63 ("It would not follow that a fly courts"), line 71 ("reaching a labelled cell does not prove the proposed sequence") and line 104 ("not enough to claim a motor programme").
- Line 78, "not necessarily a seizure. Neither measure alone diagnoses one.": now one sentence, "Neither measure alone diagnoses a seizure."
- Line 78, "Several terms matter before reading the curve.": cut (§4 run-up; no claim).
- Line 86, partial-rescue sentence: moved to line 88 beside the sentence that restated it (item 11).
- Line 108, the rejected "more confident behavioural label for the same traces": cut (§1 staged half). The refusal to read the traces as behaviour stays at lines 17, 49, 63, 71, 97 and 111.

## Left alone because changing it would alter a claim

These are §1 contrasts where the negative half corrects something a reader is likely to believe (a multiplier is a dose, a moving body is behaviour, a seed is an animal), or where both halves carry information. The skill keeps those. Rewording them into positive statements would have dropped the correction.

- Introduction: line 21 "A connectome is a map of cells and connections, not a living brain."; line 23 "That precedent motivates our approach but does not validate our male model's physiology." (split into its own sentence, wording kept); line 25 "... a model of hyperactivity, not an ``ADHD fly''" and "... largely uniform dopamine receptor densities rather than a measured male receptor map."
- Key-terms box, line 28: "not deletion of a living fly's neurons", "not another animal", "not equality" (the no-detected-difference definition).
- Methods: line 32 "The release multiplier is not a drug dose."; line 34 "... not drugs, vision or courtship in an animal." (opener changed from "These are"); line 36 "... not measured native-brain exposure" and "those axes are multipliers, not concentrations"; line 38 "These are single observations of GPU stepping, not speedup estimates" and "not spike-train or statistical equivalence".
- Dopamine: line 43 "... a fixed model multiplier, not a measured drug concentration or a treatment of a mutant fly."; line 47 "This is \emph{no detected difference}, not equivalence"; line 49 "it does not prove that removing the transporter can never matter."
- Knockout tour: line 52 "a deliberately blunt stress test rather than a receptor-selective drug experiment" (now joined to its reason by a colon); line 54 "not a photograph of transmitter action in an animal"; line 60 "rather than an absence of physiological function".
- Courtship: line 63 "It would not follow that a fly courts".
- GABA: line 74 "compensation within this network, not reversal of the block at its original target"; line 76 "not a measurement of how much drug reaches cells in a male fly" and "never an administered dose"; line 78 "not a counted stock of spare Rdl receptors" and "not by itself evidence for cooperative binding"; line 80 "not a measured count of spare receptors", "this is not an identified network EC50" and "not administered doses"; line 82 "not modulator doses"; line 86 "it does not make the curve more biological"; line 88 "partial model rescue, not receptor recovery or seizure treatment" and "not the arrival time of a seizure".
- Virtual body: line 97 "not a fit to observed fly motion" and "it is not evidence of learned behaviour, a courtship song or real wing kinematics".
- Discussion: line 100 "complementary checks on one constructed system, not independent biological replications"; line 104 "more like testing the controls on laboratory equipment than screening treatments" and "rather than to declare the transmitter irrelevant in flies"; line 108 "it does not bridge those biological gaps".
- Limitations: line 111 "not adult male brain exposure".
- Data, attribution and AI use: line 114 "These checks are not independent human or experimental replication." The whole section is unchanged.
- Captions: line 118 "this is not recorded activity or a simulated body"; line 126 "Highlighted routes are not evidence of movement or song."; line 130 "not administered dose".

Also left alone:

- §19: the bold run-in labels "Question and approach." and "What we found." (five each). Every results section uses the same three-part structure, and the labels are how a reader finds each part.
- §16: "one striking image" (line 100). The sentence's claim is that a striking image is not enough.
- The required statements that the fly does not see, including the one-sentence "The fly does not see." at line 21, which otherwise reads as a §2 closer.
- Short final sentences that add a fact: "The resting body's wings move too." (line 95) and "Native receptors may have quite different sensitivity." (line 80).
- Line 86, "Even if the imposed recombinant-receptor concentration mapping is precise arithmetic, ...": awkward, but not one of the skill's patterns, and rewording risked turning the concession into an assertion.
- §8 markup: `\newcommand{\paperstatus}{PREPRINT DRAFT --- HUMAN AUTHOR APPROVAL PENDING}` must stay byte-identical because `paper/fill_results.py` checks for it, and the printed banner's dash comes from that script. The `--` page ranges live in the bibliography, which this pass does not touch.

## fact-check.md

No manuscript line moved in this pass. Five references in `paper/fact-check.md` were already two lines off at the start and now point at the right lines: body angles 93 → 95, MaleCNS v1.0 and CC BY 4.0 116 → 118, static anatomy figure 115-116 → 117-118, knockout and courtship panels 119-124 → 121-126, dose curves 129-130 (was 127-128).

## Second pass

Rolf asked for two things the first pass held back: drop the bold run-in labels, and turn the remaining "X, not Y" and "X rather than Y" sentences into plain positive statements wherever the claim survives. The same locks apply. This section supersedes the first pass's "Left alone" entries for §1 and §19; the kept list below replaces them.

Unchanged, checked by script against `bfe9857` (lines 16-131 compared, preamble and bibliography byte for byte): every number, the 15 citation keys, 4 `\ref`, 4 `\label`, 9 `\result{}` slots (all present in `result-bindings.json`), 4 figure includes, 13 math spans, section headings. Per section, "no detected difference", "does not see" and "inject" occur exactly as often as before. Still 148 lines, one paragraph per line, so no manuscript line moved and `paper/fact-check.md` needed no change; its claim notes at lines 38, 47, 58, 76 and 80 still match the text.

Words, by this pass's counter (abstract through figure captions, bibliography excluded, citation, ref and label commands removed, each result slot one word): 4,403 at the start of the pass, 4,151 after (−252, of which 45 are the labels). This counter does not reproduce the first pass's absolute figures: on the pre-pass-1 file and the pass-1 file it gives 4,449 and 4,403 against the reported 4,150 and 4,104, a constant offset of 299 with the same −46 change.

| § | Pattern | Found at start of pass 2 | Changed | Kept |
|---|---|---|---|---|
| 19 | Bold run-in labels ("Question and approach.", "What we found.", "What it means." ×5 each) | 15 | 15 | 0 |
| 1 | Contrasts the first pass kept | 43 | 22 | 21 |
| 1 | Contrasts not on the first pass's list | 17 | 17 | 0 |
| | **Total** | **75** | **54** | **21** |

The 60 contrasts here are not the first pass's 60 (17 changed, 43 kept): they are its 43 kept plus 17 it did not list, about seven of them left behind by its own rewrites (lines 38, 41, 49, 71 twice, 97) and the rest original text (32, 54, 60, 86, 88, 91, 93, 102 twice, 122 twice). A denial that closes a positive sentence, or a sentence of its own that answers the one before, counts as the skill's split form of §1.

The labels went with no replacement text: each paragraph already opens on its subject (question, result or reading), and the section headings stay. After the cut, the only one-sentence paragraph is line 69 (the re-analysis result), which adds a fact.

### Contrasts rewritten, and where the denied half survives

Where a denied half was cut, it was either carried by a word in the new sentence or stated elsewhere; each cluster of repeated denials now keeps one, at the place a reader would first make the mistake.

| Line | Before | After | Denied half survives at |
|---|---|---|---|
| 21 | "a map of cells and connections, not a living brain" | "a map of cells and connections" | "map"; model versus animal at 17 |
| 25 | "assumed, largely uniform dopamine receptor densities rather than a measured male receptor map" | "dopamine receptor densities are assumed and largely uniform" | "assumed"; 102, 111 |
| 28 | knockout: "... in the simulation, not deletion of a living fly's neurons" | "removal, in the simulation, of ...; the neurons themselves are kept" | in the sentence |
| 32 | "The release multiplier is not a drug dose." | "reduction in dopamine release set by a model multiplier" | 43 |
| 32 | "was numerically unstable and is not mechanism evidence" | "was numerically unstable, which rules it out as mechanism evidence" | in the sentence; 49 |
| 34 | "disconnections and imposed electrical stimuli, not drugs, vision or courtship in an animal" | "uses only disconnections and imposed electrical stimuli" | "only"; 52, 54, 63, 104 |
| 36 | "a recombinant-receptor reference potency, not measured native-brain exposure" | "a reference potency measured at recombinant receptors" | 76 |
| 36 | "those axes are multipliers, not concentrations" | "those axes are in multiples of baseline conductance" | in the sentence; caption 130 |
| 38 | "tests the computational implementation, not biological validity" | "tests the computational implementation alone" | "alone"; 108 |
| 41 | "We use a history test and do not call any increase in spikes ``attention.''" | "We use a history test: the network receives ..." | 25, 49 |
| 49 | "... compatible with these runs; it does not prove that removing the transporter can never matter" | "... compatible with these runs, so removing the transporter could still matter" | in the sentence |
| 49 | "which estimates its noise but cannot stand in for collecting new, independent flies" | "so their spread estimates the model's own noise" | "own"; 28, 111 |
| 52 | "a deliberately blunt stress test rather than a receptor-selective drug experiment" | "a deliberately blunt stress test" | the "whereas a real antagonist" clause in the sentence; 60, 104 |
| 54 | "is injected rather than produced by visual experience; the fly does not see" | "is injected; the fly does not see" | in the sentence (injected-input statement kept) |
| 54 | "shows the anatomical context for the changes, not a photograph of transmitter action in an animal" | "draws the model's changes on the anatomy" | "the model's" |
| 60 | "can show where the model is sensitive and how it fails, but it cannot certify ... or predict ..." | "...; whether every named chemical acts as expected, and what would happen in a seeing animal, remain open questions" | in the sentence |
| 71 | "The changes are in circuit firing: there was no singing, fighting or visual stimulus." | "All of these changes are in circuit firing" | song 97 and 126, fighting 69 and 71, vision 65 |
| 71 | "displays some of these spikes but cannot supply the missing behavioural evidence" | "displays some of the same spikes" | 97, 111 |
| 74 | "compensation within this network, not reversal of the block at its original target" | "compensation within this network while the original GABA block stays in place" | in the sentence |
| 76 | "calculated from that assumption, never an administered dose" | "calculated from that assumption" | 80, caption 130 |
| 80 | "apparent functional reserve at low block, not a measured count of spare receptors" | "apparent functional reserve at low block" | 78 |
| 82 | "shallower changes than full block and not modulator doses" | "shallower changes than full block" | "times baseline" in the sentence; 36, caption 130 |
| 86 | "...; it does not make the curve more biological" | cut | 38, 108 |
| 86 | "They do not show that native Rdl receptors are abundant or dispensable." | cut | 78; "this particular network" in the sentence before |
| 88 | "answer different questions and do not identify a single abrupt transition" | "answer different questions" | 82 |
| 88 | "partial model rescue, not receptor recovery or seizure treatment: ... without restoring the blocked GABA channel" | "partial model rescue: ... while the GABA channel stays blocked" | in the sentence; treatment 106 |
| 91 | "illustrates a readout and is not a further experiment: the simulated brain does not control an animal in it" | "only illustrates a readout: the neural runs were completed ..." | in the sentence; one-way playback 108, 111 |
| 93 | "It cannot establish that the network generated an actual courtship movement." | cut | 97 |
| 97 | "a freely chosen spike-to-wing mapping, not a fit to observed fly motion" | "a freely chosen spike-to-wing mapping" | "freely chosen" |
| 97 | "easier to inspect, but they do not make it biologically true" | "which make an implemented hypothesis easier to inspect" | "the same caution" in the sentence |
| 102 | "It neither confirms the original hint nor establishes that dopamine clearance never matters." | "The original hint is unconfirmed, and dopamine clearance may still matter." | in the sentence |
| 102 | "might generate hypotheses but would not confirm this one retroactively" | "could at most generate hypotheses" | "at most" |
| 104 | "more like testing the controls on laboratory equipment than screening treatments" | "works like a test of the controls on laboratory equipment" | 104 ("None of these disconnections has the selectivity ... of a drug") |
| 104 | "..., rather than to declare the transmitter irrelevant in flies" | cut | 60 |
| 108 | "...; it does not bridge those biological gaps" | "..., and those biological gaps remain" | in the sentence |
| 111 | "recombinant homomeric receptors, not adult male brain exposure" | "recombinant homomeric receptors" | "recombinant"; 76 |
| 118 | caption: "this is not recorded activity or a simulated body" | cut | "Static anatomical context"; 21 |
| 122 | caption: "injected rather than seen" | "injected" | 54 |
| 122 | caption: "the disconnections are not lesions in an animal" | "the disconnections are made in the model" | in the sentence |

### Contrasts kept, and why

Each of these corrects something a reader would otherwise conclude at that point, and no positive wording carried the correction without adding a claim.

| Line | Kept | Reason |
|---|---|---|
| 23 | "That precedent motivates our approach but does not validate our male model's physiology." | The sentence before says Shiu's model had predictions tested in flies; a reader would carry that validation over to this model. |
| 25 | "a model of hyperactivity, not an ``ADHD fly''" | The paragraph opens on ADHD, so a reader would take *fumin* as an ADHD model. The next sentence is about this study, a different claim. |
| 28 | Seed: "not another animal" | Readers count repeats as animals. After the rewrite at 49 this and 111 carry the point. |
| 28 | "\emph{no detected difference}, not equality" | Locked definition. |
| 38 | "single observations of GPU stepping, not speedup estimates" | GPU timings are read as speedups by default; no positive wording says they are not one. |
| 38 | "agreement in the measured curve, not spike-train or statistical equivalence" | Overlapping intervals are commonly read as equivalence; the sentence exists to separate the two kinds of agreement. `fact-check.md` row 38 records this wording. |
| 43 | "a fixed model multiplier, not a measured drug concentration or a treatment of a mutant fly" | The one remaining statement that the release change is no drug and no treatment (the copy at 32 was folded in here). |
| 47 | "\emph{no detected difference}, not equivalence" | Locked term; a reader would read a null as equivalence. |
| 60 | "rather than an absence of physiological function" | A null after a knockout reads as "this transmitter does nothing"; the copy at 104 went, so this is the one statement. |
| 63 | "It would not follow that a fly courts" | Stimulating courtship neurons reads as courtship. |
| 76 | "an assumed receptor occupancy, not a measurement of how much drug reaches cells in a male fly" | A concentration-labelled axis reads as brain exposure; the copies at 36 and 111 went. |
| 78 | "the network's firing curve, not a counted stock of spare Rdl receptors" | "Receptor reserve" means spare receptors in pharmacology; the copies at 80 and 86 went. |
| 78 | "a shape parameter, not by itself evidence for cooperative binding" | A steep Hill slope is commonly read as cooperativity. |
| 80 | "this is not an identified network EC50" | A fitted slope and half-effect read as an EC50. `fact-check.md` row 80 records this wording. |
| 80 | "1.000 $\mu$M and ... 9.000 $\mu$M, not administered doses" | Kept at the numbers, where a reader turns µM into a dose; the copy at 76 went. |
| 88 | "within regions, not the arrival time of a seizure" | "Did not lead the optic lobes" at 82 reads as timing. |
| 97 | "it is not evidence of learned behaviour, a courtship song or real wing kinematics" | A moving fly reads as behaviour; the copies at 71 and 93 went, so this is the section's one statement. |
| 100 | "complementary checks on one constructed system, not independent biological replications" | Several studies pointing the same way read as replication. |
| 114 | "These checks are not independent human or experimental replication." | Attribution section; its facts are locked. |
| 126 | caption: "Highlighted routes are not evidence of movement or song." | Captions are read apart from the text. |
| 130 | caption: "not administered dose" | Captions are read apart from the text. |

Not counted as §1: plain negative claims with no positive half to swap in. The closest to the pattern, left as they are: 23 "It gives no measured dose response, and it does not guarantee that any simulated spike predicts a living fly's response" (a positive rewrite would have to prescribe a measurement, which adds a claim), 60 "They do not validate the size of any response in a living fly", 71 "reaching a labelled cell does not prove the proposed sequence", 97 "It does not reveal a calibrated motor transfer function or a working sensory-to-action loop", 108 "Shiu and colleagues' experimental precedent does not validate this particular operating point". The required "the fly does not see" statements are untouched.
