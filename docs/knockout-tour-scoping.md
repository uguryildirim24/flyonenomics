# Scoping the Chemical Knockout Tour: What Switching Off Each Chemical System Means in the Model and in Real Flies

## Plain Summary

This document scopes a proposed "chemical knockout tour" for the simulated adult male fruit fly (*Drosophila melanogaster*) central nervous system (`male-cns:v1.0`).

In the tour, we plan to switch off one neurotransmitter system at a time in the simulated brain, step the whole network in resting conditions, and observe what happens in 3D. Before any outcome simulations are run, this document establishes:
1. **The chemical classes** present in the 162,517 simulated neurons, their numbers, confidence ratings, and where they sit.
2. **What "switch it off" means** in the computer model (synaptic disconnection vs conductance zeroing vs modulatory pool elimination), and whether current software can run it today.
3. **What real fruit flies show** when each chemical system is blocked by drugs or removed by genetic mutations, cited from primary experimental literature.
4. **The starting state and readouts** (resting parameters, background noise, firing rates, runaway seizure metrics, and the 3D viewer).
5. **The computational cost** per knockout per seed on local and remote hardware, taken strictly from existing benchmark records.
6. **The structural limits** of the model (point neurons, absence of synaptic plasticity, placeholder receptor maps, and the fact that the virtual fly does not see).

---

## 1. Chemical Classes in the Simulated Brain

### Definitions
- **Neurotransmitter:** A chemical messenger released by a presynaptic neuron to excite, inhibit, or modulate a postsynaptic target cell.
- **Connectome:** A comprehensive wiring map of all neurons and their chemical synapses in a nervous system.
- **Substrate (`male-cns:v1.0`):** The adult male fruit fly central nervous system dataset (Janelia Research Campus, Google Research, University of Cambridge; Berg et al., 2026), containing the brain, both optic lobes, and the ventral nerve cord (VNC).
- **Consensus Transmitter:** The official neurotransmitter assignment agreed upon by the connectome consortium based on automated machine-learning predictions across all release sites (T-bars) and curated ground-truth literature.
- **Ground-Truth Label:** An experimentally verified neurotransmitter assignment documented in published literature for that specific neuron or cell type.

### Neuron Census by Chemical Class

The simulation models exactly **162,517** traced and typed neurons. Across this active neuron set, the consensus neurotransmitter labels and model engine classes break down as follows:

| Chemical Class | Consensus Count | % of Brain | Ground-Truth Count (% GT) | Mean ML Confidence | Engine Class Code | Engine Count |
|---|---:|---:|---:|---:|---|---:|
| **Acetylcholine** | 102,576 | 63.12% | 52,778 (51.5%) | 0.933 | `ACh` (`A`) | 102,576 |
| **Glutamate** | 29,104 | 17.91% | 14,395 (49.5%) | 0.787 | `Glu` (`G`) | 29,104 |
| **GABA** | 21,868 | 13.46% | 13,149 (60.1%) | 0.812 | `GABA` (`B`) | 21,868 |
| **Histamine** | 5,899 | 3.63% | 2,699 (45.8%) | 0.888 | `His` (`H`) / `unk` | 4,028 (`His`) + 1,871 (`unk`) |
| **Dopamine** | 392 | 0.24% | 380 (96.9%) | 0.855 | `mod` (`M`) | 392 |
| **Octopamine** | 101 | 0.06% | 51 (50.5%) | 0.659 | `mod` (`M`) | 101 |
| **Serotonin** | 48 | 0.03% | 44 (91.7%) | 0.749 | `mod` (`M`) | 48 |
| **Tyramine** | 0 | 0.00% | 0 (—) | — | `mod` (`M`) | 0 |
| **Unclear / Missing** | 2,529 | 1.56% | 0 (0.0%) | 0.532 | `unk` (`U`) | 2,529 |
| **Total** | **162,517** | **100.00%** | **83,496 (51.4%)** | **0.883** | — | **162,517** |

*Note on Histamine in the Engine:* In the underlying data, 5,899 neurons have histamine consensus. In the runtime engine (`data/transmitters-male-cns-v1.0.yaml`), only the 4,028 photoreceptor-related cells are assigned to engine class `His`. The remaining 1,871 histamine-consensus cells (including 1,777 T1 lamina/medulla intrinsic cells, 87 untyped cells, and 7 Hofbauer-Buchner eyelet cells) fall through the classical classifier into `unk` because the legacy classifier rule only mapped photoreceptor cell types (`R1-6`, `R7`, `R8`) and curated annotations to `His`.

### Label Confidence Breakdown

Label confidence is classified into three tiers:
1. **High Confidence / Ground-Truth Verified:** 83,496 neurons (51.4%) have direct experimental literature support in published *Drosophila* studies (`ground_truth`). Dopamine (96.9%) and Serotonin (91.7%) are almost entirely grounded in known anatomical clusters. Acetylcholine (51.5%), GABA (60.1%), and Glutamate (49.5%) have ground-truth annotations for roughly half their populations.
2. **Consensus Prediction (High ML Confidence, $\ge 0.80$):** Of the remaining neurons without literature ground-truth, the machine-learning classifier (based on electron-microscopy synapse features) exhibits high confidence ($\ge 0.80$) for 92.3% of Acetylcholine neurons, 73.5% of GABA neurons, 55.3% of Glutamate neurons, and 70.3% of Histamine neurons.
3. **Low Confidence / Unclear / Missing:** 2,469 neurons have an official consensus status of `unclear` (mean ML confidence 0.532; 45.9% scoring below 0.50). An additional 60 neurons have missing (`NaN`) consensus. Together, these 2,529 neurons have zero ground-truth labels and represent genuine connectomic uncertainty.

### Anatomical Localization

Where do neurons of each chemical class sit in the fly nervous system?

- **Acetylcholine (102,576 cells):** The dominant fast transmitter across the brain.
  - Sits primarily in the **optic lobes** (56.3% optic intrinsic, e.g., Tm3, T3, T2a, L5) and **central brain** (18.3% central intrinsic, 7.7% visual projection).
  - Includes all 4,064 mushroom body Kenyon cells (KCs, responsible for associative olfactory memory), major antennal lobe projection neurons (ALPNs, sensory relay), and wide arrays of central complex ring and columnar neurons.
- **Glutamate (29,104 cells):** The second largest class.
  - Sits predominantly in the **optic lobes** (65.4% optic intrinsic, e.g., lamina monopolar cells L1, medulla intrinsic cells Mi9, TmY5a, Dm3a) and **central brain** (22.5% central intrinsic).
  - Also supplies 302 motor neurons in the ventral nerve cord (VNC), representing peripheral motor output, as well as mushroom body output neurons (MBONs) and antennal lobe local interneurons (ALLNs).
- **GABA (21,868 cells):** The primary inhibitory infrastructure.
  - Sits in the **optic lobes** (49.3% optic intrinsic, e.g., C3, Mi4, C2, Dm10), **ventral nerve cord** (24.1% VNC intrinsic local interneurons), and **central brain** (22.1% central intrinsic).
  - Includes key recurrent feedback inhibitors such as the giant anterior paired lateral (APL) neuron of the mushroom body, antennal lobe inhibitory local interneurons (ALLNs), and central complex inhibitory loops.
- **Histamine (5,899 consensus cells; 4,028 engine `His`):**
  - Strongly localized to the **visual periphery**: 4,114 sensory photoreceptors (outer photoreceptors R1–R6, inner photoreceptors R7 and R8) in the retina/lamina, plus 1,777 T1 intrinsic interneurons connecting the lamina and medulla, and 7 Hofbauer-Buchner extraocular eyelet cells.
- **Dopamine (392 cells):**
  - Strictly localized: **98.0% sit in the central brain** (384 cells) and 2.0% in visual centrifugal pathways (8 cells).
  - Comprises classic stereotyped clusters: the paired anterior medial (PAM) cluster (~150 neurons innervating mushroom body horizontal lobes), paired posterior lateral 1 (PPL1, vertical lobes), PPL2 (calyx), paired posterior medial (PPM2/PPM3, central complex and fan-shaped body), and 27 central complex dopamine neurons (`CX_DAN`).
- **Octopamine (101 cells):**
  - Distributed across **VNC efferents** (48.5%, 49 cells innervating peripheral muscles/organs), **central brain intrinsic** (34.7%, 35 cells), and **visual centrifugal** fibers (15.8%, 16 cells).
  - Includes central complex ellipsoid body neurons (18 EL neurons) and antennal lobe modulatory neurons (OA-AL2i2, OA-AL2i3).
- **Serotonin (48 cells):**
  - Very sparse, widely projecting: 45.8% central brain (22 cells), 35.4% VNC sensory (17 cells), 8.3% efferent descending (4 cells).
  - Innervates the dorsal fan-shaped body (dFSB), lateral protocerebrum, antennal lobes, and subesophageal zone.
- **Tyramine (0 consensus cells):**
  - No consensus neuron in `male-cns:v1.0` carries a pure tyramine label. (In real flies, tyraminergic cells exist as a small subset of TDC2-expressing neurons lacking TβH).
- **Unclear / Missing (2,529 consensus cells; 4,400 engine `unk`):**
  - Distributed across the central brain (742 cells), visual projection pathways (481 cells), VNC motor neurons (381 cells), and peripheral gustatory/mechanosensory inputs (e.g. 58 Johnston's organ cells).

---

## 2. What "Switch It Off" Means in This Model

### Engine Mechanisms: How Chemical Classes Produce Effects

The simulation uses a leaky integrate-and-fire (LIF) network implemented in Brian2 with Cython code generation (`src/flyonenomics/engine/brian_engine.py`).

1. **Fast Synaptic Transmission (Sign and Conductance):**
   - Each presynaptic spike causes a step change in postsynaptic membrane potential:
     $$\Delta V_{\text{post}} = w_{\text{syn}} \cdot \text{scale}_k$$
     where $w_{\text{syn}} = 0.275\text{ mV}$, and $\text{scale}_k$ is computed per directed edge $k$ in `src/flyonenomics/substrate/scales.py:scale_array`:
     $$\text{scale}_k = \left(\frac{s_{\text{cur}}(j)}{s_{pq}[k]}\right) \cdot g(c(j))$$
   - $s_{pq}[k] \in \{-1, +1\}$ is the raw connection sign in the connectivity table.
   - $s_{\text{cur}}(j)$ is the curated biological sign of presynaptic neuron $j$:
     - $+1$ (excitatory) for `ACh` and `mod` (DA, 5-HT, OA, TA).
     - $-1$ (inhibitory) for `Glu`, `GABA`, and `His`.
     - $s_{pq}$ for `unk`.
   - $g(c(j))$ is the class conductance scale factor:
     - $g(\text{Glu}) = g_{\text{glu}} = 4.0$
     - $g(\text{GABA}) = g_{\text{gaba}} = 1.0$ (multiplied by $g_{\text{gaba\_kc}} = 6.0$ on connections targeting Kenyon cells)
     - $g(\text{His}) = g_{\text{his}} = 1.0$
     - $g(\text{ACh}) = 1.0$ (hardcoded)
     - $g(\text{mod}) = 1.0$ (hardcoded)
     - $g(\text{unk}) = 1.0$ if $s_{pq} > 0$ else $g_{\text{gaba}}$

2. **Slow Neuromodulatory Dynamics (Dopamine Only):**
   - Dopamine is the **only** transmitter with an active modulatory layer in this codebase (`src/flyonenomics/neuromod/`).
   - Every 1 ms chunk (`on_chunk` in `state.py`), spikes from 367 dopaminergic neurons (DANs and CX_DANs) release dopamine into 37 discrete anatomical compartments (mushroom body lobes and central complex neuropils) through innervation matrix $M$.
   - Compartment dopamine concentration ($DA_c$) undergoes Michaelis-Menten reuptake via the dopamine transporter (DAT: $V_{\max} = 0.11\ \mu\text{M/s}$, $K_m = 1.3\ \mu\text{M}$) and non-specific clearance ($k_{\text{ns}} = 0.05\text{ s}^{-1}$).
   - The exposure matrix $W$ maps compartment concentrations onto postsynaptic neurons. Postsynaptic Dop1R1 (D1) receptor activation shifts the spike threshold ($V_{\text{th}} \leftarrow V_{\text{th}} + d_v$, depolarization), while Dop2R (D2) receptor activation scales synaptic gain ($g_{\text{da}}$, gain modulation).
   - In contrast, Serotonin, Octopamine, and Tyramine **have no modulatory compartments, no pool equations, and no receptor matrices**. They act strictly as fast excitatory inputs ($+1$ sign, scale 1.0).

---

### Knockout Definitions: Three Distinct Meanings

In this computational model, "switching off" a chemical system can mean three fundamentally different operations:

| Knockout Type | Computational Implementation | Biological Analogue |
|---|---|---|
| **Mode 1: Presynaptic Output Disconnection** | Set synaptic weight $w = 0$ on all outgoing connections from presynaptic neurons of that class (`engine.disconnect(idx)`). Neurons still receive inputs and spike, but their spikes evoke zero postsynaptic response. | Tetanus toxin (TeTx) or botulinum toxin block of vesicular exocytosis; genetic knockout of vesicular neurotransmitter transporter (e.g. *VGlut*, *VAChT*). |
| **Mode 2: Presynaptic Electrical Silencing** | Clamp membrane potential or raise spike threshold to an unreachable ceiling ($V_{\text{th}} = +100\text{ mV}$ via `Silence(population)`). The neurons never spike. | Overexpression of inward-rectifier potassium channels (Kir2.1); temperature-sensitive dynamin (*shibire*$^{ts}$); sodium channel blockers (tetrodotoxin, TTX). |
| **Mode 3: Postsynaptic Receptor / Conductance Zeroing** | Set the global conductance gain $g(\text{class}) = 0.0$ in `scale_array`. Presynaptic neurons spike and release normally, but postsynaptic channels produce zero conductance change. | Bath application of saturating receptor antagonists (e.g., picrotoxin for GABA$_A$/GluCl; methyllycaconitine for nAChR; SCH-23390 for Dop1R1). |
| **Mode 4: Modulatory Layer Knockout (Dopamine only)** | Disable the modulatory layer (`layers.dopamine_A = False`), zero compartment release ($\alpha_c = 0$), or scale receptor densities to zero (`ScaleReceptor(receptor="all", factor=0)`). | Tyrosine hydroxylase inhibition (3-IY); complete D1/D2 receptor antagonist cocktail without touching fast co-transmission. |

---

### Capabilities of Current Code vs Required Changes

Can the existing software execute these knockouts today without code modifications?

| Transmitter Class | Can Current Code Do It Today? | Mechanism Available Today | Required Code Change if Not Available |
|---|---|---|---|
| **Acetylcholine** | **Partially** | Mode 1 (Disconnection) can be run by finding all ACh neuron indices from annotations and calling `engine.disconnect(idx)`. Mode 2 (Silencing) works if an index list is passed. | To run Mode 3 (conductance zeroing), `scale_array` in `src/flyonenomics/substrate/scales.py` must be edited: currently ACh gain is hardcoded to 1.0 (no `g_ach` parameter exists in `drive.yaml` or `scale_array`). |
| **GABA** | **Partially** | Mode 1 (Disconnection) works via `engine.disconnect(gaba_idx)`. | Mode 3 cannot be set via `drive.yaml` because `src/flyonenomics/substrate/scales.py:70` has a strict guard: `if not np.isfinite(value) or value <= 0: raise ValueError(...)`. Setting `g_gaba = 0` triggers an exception. Smallest change: change guard in `scales.py` to `value < 0` to permit `0.0`. |
| **Glutamate** | **Partially** | Mode 1 (Disconnection) works via `engine.disconnect(glu_idx)`. | Mode 3 blocked by the same `value <= 0` guard on `g_glu` in `scales.py:70`. Smallest change: allow `g_glu = 0.0` in `scales.py`. |
| **Histamine** | **Partially** | Mode 1 (Disconnection) works via `engine.disconnect(his_idx)`. | Mode 3 blocked by `value <= 0` guard on `g_his` in `scales.py:70`. Also, 1,871 histamine cells are classified as `unk`; changing `step3_class` in `transmitters.py` would be needed to classify non-photoreceptor histamine cells as `His`. |
| **Dopamine** | **YES** | **Full native support:**<br>1. Fast synaptic disconnection via `layers.dan_fast_synapses="disconnect"`.<br>2. Modulatory layer knockout via `layers.dopamine_A = False`.<br>3. Receptor knockout via `ScaleReceptor(factor=0)`.<br>4. Release blockade via `ScaleRelease(factor=0)`. | None. Dopamine is fully parameterized across both fast and slow layers. |
| **Octopamine** | **Partially** | Mode 1 (Disconnection) works via `engine.disconnect(oa_idx)`. | Cannot do Mode 3 (conductance) because octopamine is merged into `mod` (`M`) alongside dopamine and serotonin. Smallest change: split `mod` in `transmitters.py` into distinct classes (`DA`, `5HT`, `OA`, `TA`) and add individual gains in `scales.py`. |
| **Serotonin** | **Partially** | Mode 1 (Disconnection) works via `engine.disconnect(sero_idx)`. | Same as Octopamine: merged into `mod`. Requires class splitting in `transmitters.py` and `scales.py` for conductance-level knockout. |
| **Tyramine** | **N/A (0 cells)** | Connectome has 0 consensus tyramine cells. | No neurons to disconnect. |
| **Unknown (`unk`)**| **Partially** | Mode 1 (Disconnection) works via `engine.disconnect(unk_idx)`. | Mode 3 blocked because positive `unk` is hardcoded to 1.0 and negative `unk` uses `g_gaba`. |

**Conclusion on Engine Mechanics:**
Every chemical class can be knocked out **today via Mode 1 (presynaptic output disconnection)** by calling `engine.disconnect(class_indices)`. If the tour coordinator prefers Mode 3 (receptor conductance zeroing), two tiny changes in `src/flyonenomics/substrate/scales.py` are required: (1) permit `value == 0.0` in the scale validator, and (2) expose `g_ach` and `g_mod` arguments.

---

## 3. What Real Flies Show

To establish grounded expectations for each knockout, we examine published experimental findings where that chemical system was genetically ablated, silenced, or blocked with pharmacology in living *Drosophila*.

*Evidence Standard:* In accordance with project instructions, every cited source below was directly opened, fetched, and inspected. Full-text PMC XML/HTML access is marked **[FT]**; PubMed verified abstract access is marked **[A]**. Unverified claims from older project documents (`L2-biology.md`) are explicitly rejected.

```
====================================================================================================
TRANSMITTER       REAL-FLY EXPERIMENTAL INTERVENTION AND PHENOTYPE                     SOURCE
====================================================================================================
Acetylcholine     Paralysis within minutes; complete loss of evoked CNS potentials.   Greenspan 1980 [A]
                  Blockade of fast inward EPSCs in central projection neurons.        Lee & O'Dowd 1999 [FT]
----------------------------------------------------------------------------------------------------
GABA              Picrotoxin causes paroxysmal runaway excitation and loss of         Wilson & Laurent 2005 [FT]
                  contrast/tuning. Gad1 mutants show embryonic death/hyperexcitability. Featherstone 2000 [FT]
----------------------------------------------------------------------------------------------------
Glutamate         GluClα channel mediates fast synaptic inhibition in antennal lobe;  Liu & Wilson 2013 [FT]
                  ivermectin/PTX blocks it. Essential for circadian gating.          McCarthy 2011 [FT]
----------------------------------------------------------------------------------------------------
Dopamine          TH null in CNS (pale rescue): severe hypoactivity, sleep increase,  Riemensperger 2011 [FT]
                  intact basic visual tracking. fumin (DAT null): 2-3x hyperactivity. Kume 2005 [FT]
----------------------------------------------------------------------------------------------------
Serotonin         Genetic loss (Trh RNAi) or 5-HT1A null reduces sleep and increases  Yuan 2006 [FT]
                  arousal. Elevation of 5-HT increases sleep and aggression.          Dierick 2007 [FT]
----------------------------------------------------------------------------------------------------
Octopamine        Tbh null (complete lack of OA): reduced wakefulness / excessive     Crocker & Sehgal 2008 [FT]
                  sleep, flight initiation failure, loss of appetitive learning.     Monastirioti 1996 [FT]
----------------------------------------------------------------------------------------------------
Histamine         Hdc and ort (HisCl1) null mutants are completely blind (loss of     Burg 1993 [FT]
                  ERG transients); altered circadian wakefulness/sleep regulation.     Gengs 2002 [FT], Oh 2013 [FT]
----------------------------------------------------------------------------------------------------
Tyramine          Tbh mutants (elevated TA, zero OA) show severe flight suppression.  Saraswati 2004 [FT]
                  TA and OA act as antagonistic push-pull motor regulators.           Brembs 2007 [FT], Roeder 2005 [FT]
====================================================================================================
```

### Detailed Review by Transmitter Class

#### 1. Acetylcholine (ACh)
- **Biological Role:** Primary excitatory neurotransmitter in the insect central nervous system. Sensory afferents (visual, olfactory, mechanosensory) and local/projection interneurons release acetylcholine onto nicotinic acetylcholine receptors (nAChRs, ligand-gated cation channels) and muscarinic receptors (mAChRs).
- **Genetic Loss:**
  - *Choline acetyltransferase (ChAT) mutants:* Temperature-sensitive alleles (*Cha-ts1*, *Cha-ts2*) synthesize a thermolabile ChAT enzyme. When adult flies are shifted from permissive (18–22°C) to restrictive temperature (30–37°C), acetylcholine synthesis rapidly halts. Flies display rapid, completely reversible behavioral paralysis within 2 to 5 minutes (**Greenspan, 1980 [A]**; **Kitamoto, 2001 [FT]**). Evoked synaptic responses throughout the central nervous system, including the giant fiber escape circuit and antennal lobe, fail completely.
  - *Acetylcholinesterase (AChE / Ace) loss:* Null mutations in *Ace* prevent acetylcholine degradation, causing lethal accumulation of synaptic ACh, massive uncoordinated firing, continuous convulsions, and death.
- **Pharmacology:**
  - Nicotinic antagonists (α-bungarotoxin, methyllycaconitine [MLA], curare, mecamylamine): Application of α-bungarotoxin or MLA to isolated *Drosophila* brains blocks fast inward excitatory postsynaptic currents (EPSCs) in central neurons and projection neurons (**Lee & O'Dowd, 1999 [FT]**; **Su & O'Dowd, 2003 [FT]**).
- **Expected Real-Fly Direction:** Switching off acetylcholine eliminates the primary drive of the central nervous system. The real brain falls silent and motor output ceases.

#### 2. GABA ($\gamma$-Aminobutyric Acid)
- **Biological Role:** Primary fast inhibitory neurotransmitter throughout the insect brain and ventral nerve cord. Acts through ionotropic GABA$_A$ receptors (ligand-gated chloride channels encoded by *Rdl*, *Gcl*, and *Grd*) and metabotropic GABA$_B$ receptors (G-protein coupled).
- **Pharmacology:**
  - *Picrotoxin (PTX):* Picrotoxin binds and blocks the chloride pore of ionotropic GABA$_A$ receptors (*Rdl*). In *Drosophila* antennal lobe projection neurons, bath application of picrotoxin abolishes fast hyperpolarizing inhibitory postsynaptic currents (IPSCs), produces prolonged depolarizations, broadens odor tuning curves, and triggers high-frequency paroxysmal seizure-like bursts (**Wilson & Laurent, 2005 [FT]**).
  - *Resistance to Dieldrin (Rdl):* The *Rdl* locus encodes the GABA$_A$ receptor; the canonical *Rdl*$^{A302S}$ point mutation confers profound resistance to both cyclodiene insecticides and picrotoxin (**ffrench-Constant et al., 1991, 1994 [FT]**).
- **Genetic Loss:**
  - *Glutamic acid decarboxylase (Gad1) mutants:* *Gad1* encodes the enzyme synthesizing GABA from glutamate. *Gad1* null mutants are embryonic lethal. Temperature-sensitive alleles (*Gad1-ts*) or targeted RNAi knockdown cause severe loss of coordination, hyperexcitability, heat-induced seizures, and paralysis (**Featherstone et al., 2000 [FT]**).
- **Expected Real-Fly Direction:** Removing GABA removes the primary brake on recurrent excitation. The real brain suffers unconstrained runaway excitation, widespread synchronization, and seizure discharge.

#### 3. Glutamate (Glu)
- **Biological Role:** Dual function in *Drosophila*:
  1. *Peripheral Neuromuscular Junction (NMJ):* Glutamate is the fast **excitatory** transmitter released by motor neurons onto muscle fibers (acting on GluRIIA–E cation channels).
  2. *Central Nervous System:* Glutamate acts primarily as a fast **inhibitory** neurotransmitter via the glutamate-gated chloride channel ($\text{GluCl}\alpha$), while also acting on excitatory NMDA/AMPA-like receptors and metabotropic mGluR.
- **In Vivo Evidence:**
  - *Fast Central Inhibition:* **Liu & Wilson (2013) [FT]** demonstrated using in vivo patch-clamp recordings that glutamate released by antennal lobe local interneurons hyperpolarizes postsynaptic projection neurons. This inhibition has a reversal potential matching chloride ($-65\text{ mV}$) and is completely blocked by picrotoxin or RNAi against $\text{GluCl}\alpha$.
  - *Circadian Gating:* **McCarthy et al. (2011) [FT]** showed that $\text{GluCl}\alpha$ expression in pacemaker clock neurons mediates daily rhythmic synaptic inhibition; loss of $\text{GluCl}\alpha$ disrupts behavioral circadian synchronization.
  - *Channel Pharmacology:* **Cully et al. (1996) [FT]** cloned Drosophila $\text{GluCl}\alpha$, showing it forms homomeric chloride channels opened by glutamate and irreversibly locked open by avermectins (e.g. ivermectin), producing flaccid paralysis.
- **Expected Real-Fly Direction:** In the central brain, blocking $\text{GluCl}\alpha$ causes disinhibition, loss of sensory contrast, and hyperexcitability (**Liu & Wilson, 2013 [FT]**). At the neuromuscular junction, blocking glutamate transmission produces complete flaccid muscular paralysis.

#### 4. Dopamine (DA)
- **Biological Role:** Modulates arousal, sleep/wake states, locomotor initiation, associative learning (valence encoding in mushroom bodies), courtship, and visual attention.
- **Genetic Loss & Pharmacology:**
  - *Dopamine synthesis deficiency:* Complete loss of tyrosine hydroxylase (TH, *pale*) is lethal. **Riemensperger et al. (2011) [FT]** constructed flies with TH rescued in the hypoderm (cuticle) but absent in the nervous system. These dopamine-deficient flies show severe daytime hypoactivity, extended sleep, and complete loss of aversive olfactory learning. Remarkably, optomotor visual tracking and spatial orientation memory remain largely intact, demonstrating that dopamine is not required for primary sensory throughput.
  - *Dopamine depletion by 3-iodotyrosine (3-IY):* Feeding adult flies 3-IY (a competitive TH inhibitor) depletes brain dopamine by 40–70%, decreases locomotor activity, and extends sleep (**Kume et al., 2005 [FT]**; **Shin & Venton, 2018 [FT]**).
  - *Transporter loss (fumin / dDAT null):* Mutants lacking the dopamine transporter (*fmn*) have 4-fold slower clearance of released dopamine (**Shin & Venton, 2018 [FT]**), resulting in persistent extracellular dopamine accumulation, extreme daytime and nighttime hyperactivity (2- to 3-fold higher daily activity), reduced sleep (<150 min/day vs ~1000 min in control), and absence of sleep rebound (**Kume et al., 2005 [FT]**).
- **Expected Real-Fly Direction:** Removing dopamine does *not* silence or seize the brain. It causes profound behavioral hypoactivity, increased sleep duration, and failure of associative reinforcement, while leaving baseline sensory and motor circuits functional (**Riemensperger et al., 2011 [FT]**).

#### 5. Serotonin (5-HT)
- **Biological Role:** Modulates sleep homeostasis, circadian rhythms, aggressive behavior, feeding, and visual place memory.
- **In Vivo Evidence:**
  - *Sleep Regulation:* **Yuan et al. (2006) [FT]** demonstrated that serotonin promotes sleep in *Drosophila*. Feeding 5-HT or its precursor 5-HTP increases total sleep and shortens sleep latency. Conversely, genetic depletion of serotonin (via tryptophan hydroxylase [*Trh*] mutation or RNAi) or null mutation of the 5-HT1A receptor significantly decreases sleep and increases wakefulness.
  - *Aggression:* **Dierick & Greenspan (2007) [FT]** showed that acutely elevating serotonin increases fighting frequency and aggressive escalation in male flies, whereas decreasing serotonin reduces aggression without altering general locomotion.
- **Expected Real-Fly Direction:** Removing serotonin produces hyperarousal, fragmented sleep, reduced aggressive motivation, and impaired behavioral flexibility, but preserves basic sensory-motor function (**Yuan et al., 2006 [FT]**; **Dierick & Greenspan, 2007 [FT]**).

#### 6. Octopamine (OA)
- **Biological Role:** The invertebrate functional analogue of vertebrate norepinephrine. Mobilizes the fly for energy-demanding behaviors: promotes wakefulness, elevates locomotor velocity, initiates flight motor programs, and mediates appetitive olfactory reinforcement.
- **Genetic Loss:**
  - *Tyramine $\beta$-hydroxylase (Tbh) null mutants:* **Monastirioti et al. (1996) [FT]** isolated the *Tbh*$^{nM18}$ null mutant, which completely lacks octopamine due to inability to convert tyramine to octopamine. Females are completely sterile due to oviposition block (inability to release eggs from the ovary).
  - *Sleep and Locomotion:* **Crocker & Sehgal (2008) [FT]** demonstrated that *Tbh* mutants show significantly increased sleep and blunted response to mechanical arousal. Activating octopaminergic neurons or feeding octopamine agonists (chlordimeform) suppresses sleep and drives hyperactivity.
  - *Flight Deficits:* **Brembs et al. (2007) [FT]** found that *Tbh* mutants exhibit severe deficits in initiating and sustaining flight, as well as impaired appetitive memory.
- **Expected Real-Fly Direction:** Removing octopamine produces lethargy, excessive sleep, failure of flight maintenance, and blunted appetitive learning (**Crocker & Sehgal, 2008 [FT]**; **Brembs et al., 2007 [FT]**).

#### 7. Histamine (His)
- **Biological Role:** The dedicated neurotransmitter of arthropod photoreceptors and extraocular eyelet cells, acting through histamine-gated chloride channels (*ort* / HisCl1 and HisCl2). Also acts in a small number of central brain neurons regulating wakefulness.
- **In Vivo Evidence:**
  - *Visual Synaptic Transmission:* Photoreceptors R1–R8 release histamine into the lamina and medulla. Mutants lacking histidine decarboxylase (*Hdc*$^{jk910}$, *Hdc*$^{P118}$) cannot synthesize histamine and display completely flat electroretinograms lacking on- and off-transients (**Burg et al., 1993 [FT]**; **Melzig et al., 1996 [FT]**).
  - *HisCl1 Receptor Null (ort):* **Gengs et al. (2002) [FT]** showed that the visual pathway mutant *ort* encodes the HisCl1 subunit. *ort* mutants are completely blind in phototaxis and optomotor assays.
  - *Sleep Regulation:* **Oh et al. (2013) [FT]** found that histamine in central circuits promotes wakefulness via HisCl1. *Hdc* mutants sleep significantly more than wild-type flies.
- **Expected Real-Fly Direction:** Removing histamine causes immediate and total blindness at the first visual synapse (**Burg et al., 1993 [FT]**; **Gengs et al., 2002 [FT]**), with mild increases in daytime sleep (**Oh et al., 2013 [FT]**).

#### 8. Tyramine (TA)
- **Biological Role:** Both the metabolic biosynthetic intermediate for octopamine (Tyrosine $\rightarrow$ Tyramine $\rightarrow$ Octopamine via TDC and T$\beta$H) and an independent signaling molecule acting on dedicated G-protein coupled tyramine receptors (TyrR, TyrRII).
- **In Vivo Evidence:**
  - *Push-Pull Motor Regulation:* **Saraswati et al. (2004) [FT]** and **Brembs et al. (2007) [FT]** demonstrated that tyramine and octopamine exert opposing actions on locomotion and flight. In *Tbh* mutants where octopamine is zero, tyramine accumulates to **8- to 10-fold higher than normal levels**. This excessive tyramine suppresses locomotion and causes flight arrest. Reducing tyramine levels (by feeding tyramine receptor antagonists or genetic reduction of TDC) rescues the flight and motor defects.
  - **Roeder (2005) [FT]** reviewed physiological evidence that octopamine activates motor behavior while tyramine acts as a deceleration brake.
- **Expected Real-Fly Direction:** Pure tyramine loss cannot be cleanly studied without affecting octopamine in simple TDC mutants, but elevating tyramine stops flight and slows locomotion (**Saraswati et al., 2004 [FT]**; **Brembs et al., 2007 [FT]**).

#### 9. Unknown / Unannotated Neurons (`unk`)
- **Biological Status:** This category does not correspond to any single neurotransmitter system in living flies. It is a mixture of neuropeptidergic neurons, uncharacterized interneurons, and cells with ambiguous electron microscopy prediction scores.
- **Expected Real-Fly Direction:** **No clear real-fly answer exists.** Silencing 4,400 heterogeneous neurons simultaneously is a modeling artifact, not a biologically coherent experiment.

---

## 4. Starting State and Readouts

### Starting Substrate and Input Protocol

Any chemical knockout experiment must start from the validated male resting baseline established in SPEC-P2 item 155 and port step 6 (`docs/malecns-port.md:617–648`; `docs/malecns-rest.md`):

- **Substrate Identifier:** `rest:ed9b0a469d7a6b77` (`male-cns:v1.0`).
- **Baseline Engine Settings:**
  - Brian2 Cython backend, integration time step $dt = 0.1\text{ ms}$.
  - Membrane time constant $t_{\text{mbr}} = 20\text{ ms}$, synaptic decay $\tau = 5\text{ ms}$.
  - Resting potential $v_0 = -52\text{ mV}$, reset potential $v_{\text{rst}} = -52\text{ mV}$, spike threshold $v_{\text{th}} = -45\text{ mV}$.
  - Refractory period $t_{\text{rfc}} = 2.2\text{ ms}$, conduction delay $t_{\text{dly}} = 1.8\text{ ms}$.
  - Base unitary synaptic weight $w_{\text{syn}} = 0.275\text{ mV}$.
  - Baseline conductance scales: $g_{\text{gaba}} = 1.0$, $g_{\text{glu}} = 4.0$, $g_{\text{his}} = 1.0$, $g_{\text{gaba\_kc}} = 6.0$. No optic exemption.
  - Threshold spread: none ($\sigma_{\text{th}} = 0$). Mechanisms: plain LIF (no adaptation `sfa`, no depression `std`, no conductance inhibition `cbi`).
- **Input Protocol:**
  - **Dark Rest Protocol:** 100 independent Poisson inputs at 10 Hz applied with sensory-only background weight $w_{\text{bg}} = 1.0\text{ mV}$ onto the 15,016 sensory neurons (`sensory` drive group). All other 11 drive groups receive $w_{\text{bg}} = 0.0\text{ mV}$. No visual patterns or current injections are applied.
  - **Window Timing:** 2.0 s unrecorded settle window, followed by a 10.0 s measurement window (12.0 s total per seed).
- **Dopamine State:**
  - Clamped at $DA_{\text{ref}} = 0.02\ \mu\text{M}$ for fast-network screening, or free-running with the 37 adopted compartment release constants ($R_c, \alpha_c, S_c$).

---

### Candidate Readouts

How can the network effect of each chemical knockout be quantified and visualized?

1. **Per-Region and Per-Drive-Group Firing Rates:**
   - Measure mean spike rates (Hz) across the 12 canonical functional drive groups:
     - `sensory` (15,016 cells)
     - `optic` (89,353 cells)
     - `central` (39,533 cells)
     - `ascending` (1,849 cells)
     - `descending` (1,314 cells)
     - `motor` (887 cells)
     - `KC` (Kenyon cells, 4,064 cells)
     - `DAN` (Dopaminergic cells, 367 cells)
     - `ER` (Ring neurons, 282 cells)
     - `visual_projection` (9,203 cells)
     - `visual_centrifugal` (562 cells)
     - `endocrine` (87 cells)
   - Readout value: Detects whether a knockout selectively silences a pathway (e.g. optic vs central) or triggers regional hyperexcitability.

2. **Network Stability and Runaway / Seizure Detection:**
   - **Fano Factor ($F$):** Evaluated over 1 ms spike counts across all simulated neurons. An intact resting brain maintains $F \approx 2.5–3.2$. Synchronous epileptic bursts drive $F > 6–40$.
   - **Largest 1 ms Spike Fraction ($b$):** The fraction of total brain spikes occurring in a single 1 ms time bin. Normal rest maintains $b < 0.003$; paroxysmal seizure avalanches drive $b > 0.05$.
   - **Central Ignition Floor:** Any 1 s rolling window where central brain firing exceeds $3\times$ baseline or exceeds $8.0\text{ Hz}$.
   - **Silence Detection:** Any condition where whole-brain or regional firing collapses to $0.000\text{ Hz}$ (the "bistability wall").
   - **Temporal Drift Ratio:** Ratio of first-1 s to last-1 s mean central rate (normal interval $[0.5, 2.0]$).

3. **3D Anatomical Render Path:**
   - The repository contains a complete, working 3D browser visualization pipeline (`scripts/render_malecns_3d.py`; documentation in `docs/3d-model.md`).
   - Skeletons of 952 representative neurons across all key neuropils (central complex, mushroom body, optic lobes, antennal lobe, and VNC) are aligned in native MaleCNS EM space with Three.js.
   - The render path can project per-neuron firing rates or rate differences ($\Delta \text{Hz} = \text{Rate}_{\text{knockout}} - \text{Rate}_{\text{wildtype}}$) as a dynamic color map onto the 3D anatomical structures. This directly fulfills Rolf's requirement for a 3D visualization of whole-brain changes.

---

## 5. Computational Cost

*Source of Truth:* All execution timings and memory footprints below are taken directly from committed benchmark records in the repository (`docs/malecns-port.md:216–237, 658–662`; `docs/malecns-rest.md:138–163, 300–305`; `docs/SPEC-P2.md:1955`). No new benchmarks or test simulations were executed.

### Historical Measured Benchmarks for `male-cns:v1.0` (25.1M Edges)

| Environment | Benchmark Task | Engine Build Wall Time | Run Wall Time per Brain-Second | Peak RSS Memory | Reference Path |
|---|---|---:|---:|---:|---|
| **Apple Mac (arm64 macOS)** | 1.0 s dark run (unconfigured) | 3.34 s | 8.42 s | 1.95 GiB (2,048 MB) | `docs/malecns-port.md:226` |
| **Apple Mac (arm64 macOS)** | 1.0 s configured rest (seed 20260921) | ~32.0 s (total prep) | 28.56 s | 6.67 GiB (7,167 MB) | `docs/malecns-port.md:660` |
| **Oracle Cloud Box (`compute host`, arm64)** | Single-process cost probe (1 s run) | 77.72 s | 113.35 s | 6.78 GiB (7,283 MB) | `docs/malecns-rest.md:144` |
| **Oracle Cloud Box (`compute host`, arm64)** | Concurrent 8 workers (701 brain-s) | ~80 s | **91.31 s** (range 87.9–93.2 s) | 7.26 GiB per worker (58.0 GiB total) | `docs/malecns-rest.md:302` |

### Projected Cost per Knockout Condition

For a standard resting-state evaluation of **12 brain-seconds** per seed (2.0 s unrecorded settle + 10.0 s measurement):

- **Local Mac (Single Seed):**
  - Engine build & array allocation: ~30 s
  - 12 brain-seconds at 28.56 s/brain-s: ~343 s (5.7 minutes)
  - **Total per seed on Mac:** **~6.2 minutes wall time**, peak memory ~6.7 GiB.
- **Oracle Cloud Box (Single Worker):**
  - Engine build & array allocation: ~78 s
  - 12 brain-seconds at 91.31 s/brain-s: ~1,096 s (18.3 minutes)
  - **Total per seed on Box:** **~19.6 minutes wall time**, peak memory ~7.3 GiB.
- **Oracle Cloud Box (10 Seeds in Parallel on 8 Workers):**
  - Total work: $10 \times 12\text{ brain-seconds} = 120\text{ brain-seconds}$.
  - Concurrent throughput: $120 \times 91.31\text{ s} / 8\text{ workers} \approx 1,370\text{ wall seconds}$ (**~22.8 minutes**).
  - Total RAM utilized across 8 workers: ~58.1 GiB (comfortably below the box's 94 GiB physical limit).

### Full Tour Projected Cost (8 Chemical Knockouts + 1 Wild-Type Control)

If the complete chemical knockout tour runs 9 experimental arms (Wild-Type, -ACh, -GABA, -Glu, -DA, -5HT, -OA, -His, and -Unk) over 10 seeds each:
- **Total Brain-Seconds:** $9 \times 120 = 1,080\text{ brain-seconds}$.
- **Box Wall Time (8 Workers):** $\approx 12,325\text{ seconds}$ (**~3.4 hours** total computation).
- **Cost:** Well within the existing Oracle Cloud trial credits, requiring zero additional cloud spend.

---

## 6. Structural Limits of the Model

When interpreting any outcome from the chemical knockout tour, six fundamental structural constraints of the model must be explicitly stated to prevent over-interpreting computer outputs as biological facts:

1. **Absence of Synaptic Plasticity:**
   - Real fruit flies compensate for chronic neurotransmitter loss through homeostatic synaptic scaling, receptor up/down-regulation, and changes in intrinsic membrane excitability.
   - The simulation has zero plasticity: all synaptic weights ($w_{\text{syn}}$) are fixed point numbers. Knockouts in this model measure only **immediate, uncompensated circuit dynamics**.
2. **Point-Neuron LIF Abstraction (All-or-Nothing Spikes):**
   - The simulation forces every one of the 162,517 neurons to obey point leaky integrate-and-fire equations.
   - In real flies, major classes of interneurons (including all lamina monopolar cells L1–L5, local interneurons in the antennal lobe, and the giant APL neuron) **do not fire spikes**; they release neurotransmitter continuously via graded, analog subthreshold membrane potentials. Forcing graded inhibitory interneurons into digital thresholding promotes artificial network bursting.
3. **Uniform Inhibitory Assignment for Glutamate:**
   - In the connectome model, every central glutamate synapse is assigned a negative conductance sign ($g_{\text{glu}} = 4.0$).
   - In real flies, glutamate is the excitatory transmitter at all neuromuscular junctions and excites certain central circuits via NMDA/AMPA-like receptors. Knocking out glutamate in this model acts purely as removing an inhibitory brake, whereas in real flies it also paralyzes muscles.
4. **Placeholder Receptor Maps and Modulatory Parameters:**
   - In the dopamine layer, receptor densities ($r_1, r_2$) are uniform placeholders ($r_1=1.0, r_2=0.5$ on all ring neurons; arbitrary allocations across mushroom body compartments).
   - Occupancy affinities ($K_d$), threshold shift amplitudes ($\Delta V$), and gain slopes ($\gamma$) are uncalibrated literature placeholders.
   - Serotonin, octopamine, and tyramine have **no receptor models whatsoever**.
5. **Histamine and Vision ("The Fly Does Not See"):**
   - Histamine accounts for 5,899 neurons in the connectome, but 99.8% sit in the visual periphery (photoreceptors and T1 lamina interneurons).
   - The simulation receives no light or functional phototransduction, but its resting background drives 4,022 R1–R8 photoreceptors with injected noise. Input is not exclusively downstream of the eye.
   - An optic-lobe effect is therefore possible even at dark rest. A null or near-null measured effect says nothing about histamine's role in real vision.
6. **Heterogeneity of the "Unknown" Cohort:**
   - The 4,400 neurons in engine class `unk` have edge signs determined by T-bar site majority rule, not identified chemical biology. Knocking them out is an assessment of connectome annotation sensitivity, not a test of any real neurotransmitter.

---

## 7. Plain Summary for Tour Design

To guide the coordinator's upcoming tour design, the core scoping findings are synthesized below:

```
========================================================================================================================
CLASS           NEURONS    CURRENT CODE STATUS                  PRIMARY REAL-FLY PHENOTYPE
========================================================================================================================
Acetylcholine   102,576    Can disconnect output today.         Rapid flaccid paralysis; complete loss of evoked CNS
                           Conductance zeroing needs g_ach.     potentials (Greenspan 1980 [A]; Lee & O'Dowd 1999 [FT]).
------------------------------------------------------------------------------------------------------------------------
GABA             21,868    Can disconnect output today.         Severe runaway hyperexcitability, seizure bursts, and
                           Conductance zeroing needs guard fix. broadened tuning (Wilson & Laurent 2005 [FT]).
------------------------------------------------------------------------------------------------------------------------
Glutamate        29,104    Can disconnect output today.         Loss of fast central inhibition (Liu & Wilson 2013 [FT]);
                           Conductance zeroing needs guard fix. complete flaccid muscular paralysis at the NMJ.
------------------------------------------------------------------------------------------------------------------------
Dopamine            392    FULLY READY TODAY                    Profound hypoactivity and sleep increase, but intact
                           (Fast disconnect & modulatory off).  basic visual tracking (Riemensperger et al. 2011 [FT]).
------------------------------------------------------------------------------------------------------------------------
Serotonin            48    Can disconnect output today.         Fragmented sleep, reduced sleep duration, and altered
                           Conductance zeroing needs split.     aggressive escalation (Yuan 2006 [FT]; Dierick 2007 [FT]).
------------------------------------------------------------------------------------------------------------------------
Octopamine          101    Can disconnect output today.         Excessive sleep, failure to initiate/maintain flight,
                           Conductance zeroing needs split.     and loss of appetitive learning (Crocker 2008; Brembs 2007).
------------------------------------------------------------------------------------------------------------------------
Histamine         5,899    Can disconnect output today.         Total loss of visual transmission / blind (Burg 1993 [FT]);
                           Conductance zeroing needs guard fix. injected input reaches photoreceptors; no visual scenes.
------------------------------------------------------------------------------------------------------------------------
Tyramine              0    No consensus cells in connectome.    N/A (Antagonistic deceleration brake in real flies).
------------------------------------------------------------------------------------------------------------------------
Unknown           4,400    Can disconnect output today.         No biological equivalent (connectome annotation gaps).
========================================================================================================================
```

- **Which knockouts current code can do today:** All 8 classes can be knocked out **today** using presynaptic output disconnection (`engine.disconnect(class_indices)`). Dopamine has full native support across both fast synaptic and slow modulatory layers.
- **Which knockouts need a code change:** Zeroing receiving conductances via `scale_array` requires allowing `0.0` in the scale validator for GABA, Glutamate, and Histamine, adding `g_ach`, and splitting `mod` into individual amine classes.
- **Which knockouts have a clear real-fly answer to test against:**
  - Acetylcholine (silence / paralysis)
  - GABA (runaway excitation / seizure)
  - Glutamate (central disinhibition + peripheral paralysis)
  - Dopamine (hypoactivity, intact visual tracking)
  - Serotonin (sleep fragmentation / hyperactivity)
  - Octopamine (lethargy / flight failure)
  - Histamine (blindness in real flies; possible optic-local model effect from injected photoreceptor input)
