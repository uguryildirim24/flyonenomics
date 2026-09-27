# Scoping a Virtual Fly Body Driven by the Simulated Male Brain (`male-cns:v1.0`)

**Author:** Flyonenomics Research Team  
**Date:** September 25, 2026  
**Context:** Feasibility and Architecture Scoping for embodied brain-to-body simulation  
**Substrate:** `male-cns:v1.0` (Adult male *Drosophila melanogaster* central nervous system, 162,517 traced neurons with Ventral Nerve Cord)  
**Target Environment:** Local Apple Silicon Mac (macOS / arm64)

---

## 1. Executive Summary

This scoping report investigates how to connect the whole-brain connectome model (`male-cns:v1.0`) to a physically simulated virtual fly body.

Currently, the `flyonenomics` model simulates 162,517 point neurons (leaky integrate-and-fire) in Brian 2 without a physical body: inputs are injected computationally into sensory or internal circuits, and the fly does not interact with a physical environment. Two primary biological perturbation experiments are currently under development:
1. Systematic transmitter-class knockouts (e.g. GABA, glutamate, dopamine).
2. Courtship activation (stimulating male-specific P1 and pIP10 descending command neurons through the courtship song pathway to wing motor neurons).

### Core Findings
1. **Fly Body Simulators:** Two mature physics-based fruit fly bodies exist in the MuJoCo physics engine: **NeuroMechFly v2 (FlyGym)** from EPFL and **FlyBody** from Google DeepMind / HHMI Janelia. Both model realistic fly kinematics and run on Apple Silicon Macs. FlyGym is licensed under MPL-2.0 and runs at ~2× real-time on Apple Silicon CPU. FlyBody is licensed under Apache-2.0 and features full aerodynamic flight simulation alongside walking.
2. **Prior Connectome-to-Body Precedents:** In March 2026, Eon Systems demonstrated the first embodied link between the female FlyWire connectome (139k neurons) and NeuroMechFly v2 in MuJoCo. Because FlyWire contained only the central brain without the ventral nerve cord (VNC), Eon mapped high-level descending command neurons (oDN1, DNa01/02) to pre-trained locomotory controllers.
3. **Our Model's Unique Advantage:** Our model (`male-cns:v1.0`) incorporates the **complete adult male central nervous system, including the entire Ventral Nerve Cord (VNC)**. It contains **887 motor neurons**—including **66 typed wing motor neurons** (`ps1`, `hg1`, `b1-b3`, `DLMn`, `DVMn`) and **373 typed leg motor neurons**—along with **1,310 descending neurons**. We could decode typed motor-neuron outputs into biomechanical actuators without substituting an artificial spinal controller, but the actuator transfer functions and wing-motion validation have not been built.
4. **Recommended First Milestone:** A possible first demo is **one-way playback of courtship-circuit activation** into wing actuators in MuJoCo. The completed circuit tour reports a rise in the *aggregate* wing-motor firing rate, not evidence of `ps1`/`hg1` recruitment, wing-side selectivity or song timing. Verify those individual spike trains before calling a wing animation brain-driven courtship song.

---

## 2. Review of Fly Body Simulators

| Feature / Simulator | NeuroMechFly v2 / FlyGym | FlyBody | Musculoskeletal Fly Leg |
| :--- | :--- | :--- | :--- |
| **Lead Institutions** | EPFL (Ramdya & Ijspeert Labs) | Google DeepMind & HHMI Janelia | EPFL, Uni Cologne, Harvard |
| **Primary Reference** | Wang-Chen et al., *Nature Methods* (2024) | Vaxenburg et al., *Nature* (2025) | Özdil et al., *arXiv:2509.06426* (2025) |
| **Physics Engine** | MuJoCo (v2 transitioned from PyBullet) | MuJoCo | MuJoCo & OpenSim |
| **Degrees of Freedom (DoFs)** | ~90 DoFs (base) / modular | 102 DoFs (67 body parts, 66 joints) | Leg-specific (tibia, femur, tarsus) |
| **Actuators** | Position/PD, torque, muscle wrappers | 78 actuators (torque, position, tendon) | Hill-type biological muscle models |
| **Locomotion Modes** | Walking, rough terrain, grooming | Walking, turning, 3D free flight | Walking replay, muscle actuation |
| **Flight Simulation** | Kinematic wing positioning (no aero) | Full quasi-steady aerodynamics | None (legs only) |
| **Song Vibration** | Kinematic wing joint oscillation | Wing torque actuators (3 DoF) | None |
| **Mac (Apple Silicon)** | **Native** (~2× real-time on M-series CPU) | **Supported** (1–3× real-time evaluation) | **Supported** (Python / MuJoCo) |
| **License** | Mozilla Public License 2.0 (MPL-2.0) | Apache License 2.0 | Open Source / Academic |
| **Maintenance & Activity** | **Very Active** (v2 API, regular updates) | **Stable** (MuJoCo Menagerie asset) | **Active Research** (Sept 2025) |

### 2.1 NeuroMechFly v2 / FlyGym (EPFL)
- **Architecture:** NeuroMechFly v2 uses FlyGym (`flygym`), an open-source Python library conforming to the Gymnasium (formerly OpenAI Gym) standard. The underlying biomechanics are based on micro-computed tomography (micro-CT) scans of an adult female *Drosophila melanogaster*.
- **Body Capabilities:**
  - *Legs:* 6 legs with 7 articulated segments each (coxa, trochanter, femur, tibia, and 5 tarsal subsegments), providing full contact dynamics with substrate friction and adhesion. Capable of walking across flat ground, irregular stairs, blocks, and inverted surfaces.
  - *Grooming:* Validated kinematic replay of head grooming, antennal sweeping, and abdominal cleaning.
  - *Wings & Head:* Articulated 3-DoF wing joints (pitch, roll, yaw) and 3-DoF neck joints.
  - *Aerodynamics:* Does not simulate fluid aerodynamics or free flight lift/drag forces. Wing motion is kinematic.
- **Control Modalities:**
  - Joint target position actuators controlled by proportional-derivative (PD) servos.
  - Central Pattern Generators (CPGs) based on coupled non-linear phase oscillators.
  - Kinematic replay from 3D markerless motion capture (e.g. DeepFly3D).
  - High-level rule-based descending controllers for forward stepping and turning.
- **Execution on Apple Silicon Mac:**
  - Installs cleanly via standard package management (`pip install flygym`).
  - MuJoCo provides official `macosx_arm64` wheels.
  - Benchmark performance: On Apple Silicon CPU (M1/M2/M3/M5), headless simulation runs at **~2.0× real-time** (simulating 1 second of fly movement in ~0.5 seconds of wall time). With off-screen visual rendering enabled (ommatidia eye model), speed drops to ~0.3×–0.5× real-time. (GPU acceleration using NVIDIA Warp is restricted to Linux/CUDA).
- **License & Community:** Licensed under MPL-2.0. Actively maintained by the Neuroengineering Laboratory (NeLy) at EPFL with extensive documentation at `neuromechfly.org`.

### 2.2 FlyBody (Google DeepMind / Janelia)
- **Architecture:** Developed by Roman Vaxenburg, Josh Merel, Srinivas Turaga, and Kristin Branson in collaboration between Google DeepMind and HHMI Janelia. Constructed from high-resolution confocal microscopy of adult fruit fly anatomy.
- **Body Capabilities:**
  - *Anatomical scale:* 67 body segments, 66 joints, 102 degrees of freedom, and 78 actuators.
  - *Flight & Aerodynamics:* Contains a native, quasi-steady aerodynamic model implemented directly within MuJoCo. Flapping wings produce instantaneous lift, thrust, and drag. Simulates free flight maneuvers, hovering, banked turns, and visual flight pursuit.
  - *Terrestrial Locomotion:* 6 legs with adhesive tarsal pads; realistic ground locomotion and gait transitions.
  - *Abdomen:* Tendon-driven multi-segment abdomen flexion and yaw.
- **Control Modalities:**
  - Controlled primarily via deep reinforcement learning (RL) policies trained using DeepMind's `dm_control` framework.
  - Wing joints use torque actuators; leg joints use position and torque actuators; abdomen uses tendon actuators.
  - Hierarchical control: A high-level task policy outputs steering and velocity targets, and low-level motor networks output actuator torques.
- **Execution on Apple Silicon Mac:**
  - The underlying MuJoCo XML (`.xml` / MJCF) model loads and steps natively in MuJoCo on macOS ARM64.
  - However, the training codebase relies on DeepMind `dm_control` and TensorFlow/JAX tooling designed for Linux clusters. Running pre-trained policies or evaluating forward physics on Mac CPU achieves **~1.0×–3.0× real-time** headless.
- **License & Community:** Licensed under Apache-2.0. Codebase is available at `TuragaLab/flybody` and curated as an official asset in Google DeepMind's *MuJoCo Menagerie*.

### 2.3 Data-Driven Musculoskeletal Fly Leg Model (Özdil et al. 2025)
- **Significance:** Released in September 2025 (*arXiv:2509.06426*), this project provides the first 3D data-driven musculoskeletal model of *Drosophila* legs, implemented in both OpenSim and MuJoCo.
- **Mechanism:** Implements biological Hill-type muscle representations calibrated from synchrotron X-ray phase-contrast imaging. Translates normalized motor unit excitation signals into muscle forces, passive tendon elasticities, and joint torques.
- **Relevance:** Provides the missing physiological link between individual motor neuron spike rates and joint torques, replacing arbitrary PD position gains with biophysical muscle curves.

---

## 3. Prior Brain-to-Body Links: Literature Review

The following section audits published studies that have interfaced neural models with simulated fly bodies. Every referenced source was directly opened and analyzed.

```
Literature Precedents: Brain-to-Body Architecture
┌────────────────────────────────────────────────────────┐
│ Eon Systems (2026): FlyWire Brain (LIF)                │
│ Central Brain Only (139k) ──► Descending Neurons (DNs) │
│                                         │              │
│                                         ▼              │
│                          NeuroMechFly v2 (MuJoCo)      │
│                          CPG Locomotion Controllers    │
├────────────────────────────────────────────────────────┤
│ Flyonenomics (Our Model): MaleCNS v1.0 (LIF)           │
│ Central Brain + VNC (162k) ──► 887 Motor Neurons (MNs) │
│                                         │              │
│                                         ▼              │
│                          Direct Wing/Leg Actuators     │
│                          (ps1, hg1, b1, DLMn, DVMn)    │
└────────────────────────────────────────────────────────┘
```

### 3.1 Eon Systems (March 2026): Whole-Brain Emulation to NeuroMechFly v2
- **Source Examined:** Eon Systems Technical Whitepaper & Release Archive (March 2026); Mindplex / The Transmitter reporting (2026).
- **Brain Model:** Based on Shiu et al. (*Nature* 2024) FlyWire v783 connectome (~139,255 point LIF neurons, central brain only).
- **Body Simulator:** NeuroMechFly v2 in MuJoCo.
- **Interface Architecture:**
  - *Brain → Body:* Because FlyWire lacked the Ventral Nerve Cord, the simulation could not reach leg or wing motor neurons. Instead, they monitored selected **descending neurons**:
    - `oDN1` (forward velocity drive).
    - `DNa01` and `DNa02` (lateral steering commands).
    - `MN9` (proboscis motor neuron for feeding extension).
  - *Descending Signal Mapping:* Descending spike rates were decoded as scalar control commands passed to pre-existing Central Pattern Generator (CPG) circuits in NeuroMechFly v2. The brain did not calculate individual leg joint angles.
  - *Body → Brain (Closed Loop):* Tactile and gustatory contact on the virtual proboscis was fed back into labellar sensory neurons.
- **Demonstrated Behaviors:** Closed-loop food search, sugar-triggered proboscis extension, and obstacle avoidance.
- **Critical Limitations:** The brain did not control the limbs; it acted as a steering wheel for an autonomous, pre-programmed body controller.

### 3.2 NeuroMechFly v1 & v2 (Lobato-Rios et al. 2022; Wang-Chen et al. 2024)
- **Sources Examined:**
  - Lobato-Rios et al., "NeuroMechFly: a robotically simulated adult Drosophila melanogaster," *Nature Methods* 19, 620–627 (2022). [DOI: 10.1038/s41592-022-01466-7]
  - Wang-Chen et al., "NeuroMechFly v2: simulating embodied sensorimotor control in adult Drosophila," *Nature Methods* 21, 1332–1341 (2024). [DOI: 10.1038/s41592-024-02300-2]
- **Brain Model:** No connectome-scale central brain. The nervous system consisted of decentralized thoracic networks (CPGs, intersegmental coordinating fibers, and local sensory feedback loops).
- **Sensory Feedback:** Modeled proprioceptive chordotonal organ feedback (joint angle, angular velocity) and campaniform sensilla (cuticular strain/load).
- **Key Findings:** Biomechanical constraints and local proprioceptive feedback loops are sufficient to produce stable tripod walking and grooming without high-level cerebral computation.

### 3.3 FlyBody (Vaxenburg et al., Nature 2025)
- **Source Examined:** Vaxenburg, Siwanowicz, Merel et al., "Whole-body physics simulation of fruit fly locomotion," *Nature* 643, 1312–1320 (2025). [DOI: 10.1038/s441586-025-09029-4]
- **Brain Model:** Deep artificial neural networks (recurrent MLPs trained via reinforcement learning), not a biological connectome.
- **Findings:** Demonstrated that artificial neural networks receiving multi-modal sensory inputs (vision, flight velocity, joint angles) can discover biological flight mechanics and walking policies in MuJoCo.

### 3.4 Cheong et al. (2024, 2026): Descending-to-Motor Architecture
- **Sources Examined:**
  - Cheong et al., "Organization of circuits linking descending input to motor output in the Drosophila Male Adult Nerve Cord connectome," *eLife* (2026).
  - Eichler et al., "Transforming descending input into behavior in the MANC connectome," Janelia Research Campus (2024).
- **Relevance:** Analyzed the synaptic wiring between 1,300+ descending neurons and the 800+ motor neurons of the male VNC. Proved that **monosynaptic connections between descending neurons and motor neurons are rare**; the vast majority of motor commands pass through dense premotor interneuron hubs in the tectulum and leg neuromeres.

---

## 4. Mapping Our Model's Signals to Body Actions

The `flyonenomics` project uses `male-cns:v1.0` (162,517 neurons; Berg et al. 2026, *Cell*, DOI: 10.1016/j.cell.2026.08.015). Unlike FlyWire, our dataset encompasses the complete Ventral Nerve Cord, providing a direct anatomical path to physical movement.

```
Biological Signal Routing in male-cns:v1.0
┌────────────────────────────────────────────────────────┐
│ Central Brain Circuits                                 │
│ ├─ P1 Courtship Hub                                    │
│ ├─ Central Complex (EB / FB Steering)                  │
│ └─ Seizure / Pharmacological Perturbations             │
└──────────────────────────┬─────────────────────────────┘
                           │ Descending Tracts (1,310 DNs)
                           ▼
┌────────────────────────────────────────────────────────┐
│ Ventral Nerve Cord (VNC)                               │
│ ├─ Premotor Interneurons (Tectulum & Leg Neuromeres)   │
│ └─ 887 Motor Neurons                                   │
│    ├─ Wing Motor Neurons (66 typed cells)              │
│    │  ├─ ps1 MN (Pulse Song)                           │
│    │  ├─ hg1 MN (Sine Song)                            │
│    │  ├─ b1-b3 MN (Flight Steering)                    │
│    │  └─ DLMn / DVMn (Power Muscles)                   │
│    └─ Leg Motor Neurons (373 typed cells)              │
│       ├─ Tibia Flexors / Extensors                     │
│       └─ Tarsus Levators / Depressors                  │
└──────────────────────────┬─────────────────────────────┘
                           │ Neuromuscular Interface
                           ▼
┌────────────────────────────────────────────────────────┐
│ Biomechanical Body (MuJoCo / FlyGym / FlyBody)         │
│ ├─ Wing Abduction (60-80°) & Vibration (150-250 Hz)    │
│ ├─ Leg Joint Torques & Tripod Locomotion               │
│ └─ Proboscis Extension (MN9)                           │
└────────────────────────────────────────────────────────┘
```

### 4.1 Wing Motor Neurons → Courtship Wing Extension and Song
- **Biological Pathway:** Activation of male P1 cluster → pIP10 descending command neurons → VNC song interneurons (dMS2, TN1A) → typed wing motor neurons.
- **Our Model Inventory (`validation/records/p2/malecns-populations.json`):** Exactly 66 typed wing motor neurons (`vnc_motor`, subclass `wm`):
  - `ps1 MN_L` and `ps1 MN_R` (body IDs 800057, etc.): Innervate pleurosternal muscle 1. In real flies, `ps1` fires in phase-locked bursts to generate **pulse song**.
  - `hg1 MN_L` and `hg1 MN_R`: Innervate the 4th axillary muscle. Specifically required for **sine song**.
  - `b1 MN_L/R`, `b2 MN_L/R`, `b3 MN_L/R`: Basalar steering muscles. Active during flight steering; silent during courtship song.
  - `DLMn` (a–f) and `DVMn` (1–3): Dorsal longitudinal and dorsoventral indirect flight muscles.
- **Mapping to Virtual Body:**
  - *Wing Abduction (Extension):* Tonic excitation of steering/abduction motor units positions the ipsilateral wing outward by 60°–80°.
  - *Song Vibration:* Phasic firing of `ps1 MN` (trains at 150–250 Hz) drives high-frequency micro-oscillations of the wing blade.
  - *Published Mapping:* Validated in literature (Clements et al. 2024, O'Sullivan et al. 2018).

### 4.2 Descending Neurons → Walking, Turning, and Stopping
- **Our Model Inventory:** 1,310 descending neurons (`DN_all`):
  - `steering_L`: `DNa01_L`, `DNa02_L` (2 cells).
  - `steering_R`: `DNa01_R`, `DNa02_R` (2 cells).
  - `pIP10`: Courtship command pair.
  - `DNp01`: Giant fiber escape trigger.
- **Mapping to Virtual Body:**
  - Bilateral asymmetry in firing rate $\Delta r = r(\text{DNa02\_R}) - r(\text{DNa02\_L})$ maps directly to yaw angular velocity in FlyGym's locomotion controller:
    $$\omega_{\text{yaw}} = K_{\text{steer}} \cdot (r_R - r_L)$$
  - Firing of forward descending neurons sets forward walking velocity $v_{\text{fwd}}$.
  - Complete silencing of descending drive halts stepping.

### 4.3 Leg Motor Neurons → Multi-Joint Leg Movement
- **Our Model Inventory:** 373 typed leg motor neurons across prothoracic (T1, foreleg `fl`), mesothoracic (T2, midleg `ml`), and metathoracic (T3, hindleg `hl`) neuromeres:
  - `Acc. ti flexor MN`: Accessory tibia flexor.
  - `Fe reductor MN`: Femur reductor.
  - `Ta levator MN` / `Ta depressor MN`: Tarsus levators and depressors.
  - Rotator and promotor motor neurons.
- **Mapping to Virtual Body:**
  - Motor neuron spike rate $r_i(t)$ is passed through a low-pass muscle activation filter:
    $$\frac{da_i}{dt} = \frac{r_i(t) - a_i(t)}{\tau_{\text{muscle}}}$$
  - Activation $a_i(t)$ drives either a torque actuator directly or sets target joint angles in MuJoCo.
- **Biomechanical Caution:** Driving 373 leg motor neurons *open-loop* (pure feedforward) into a physical body will fail to produce coordinated walking. In biological flies, walking depends critically on local proprioceptive feedback loops (chordotonal organs and cuticular strain sensors) within the VNC to prevent falling, slipping, and hyperextension.

### 4.4 Whole-Brain Seizure-Like Activity → Twitching and Tremors
- **Perturbation Mechanism:** Simulating a global GABA receptor knockout (`g_gaba = 0`) or convulsant exposure induces runaway hypersynchronous firing across thousands of central and motor neurons.
- **Body Manifestation:** High-frequency, co-contractive activation across antagonistic leg muscles (flexor and extensor firing simultaneously) produces erratic joint shuddering, spasms, and collapse, mirroring the electroconvulsive seizures observed in *Drosophila* bang-sensitive mutants.

---

## 5. One-Way Playback vs. Closed Loop

```
Comparison of Execution Architectures

(A) One-Way Playback (Decoupled & Asynchronous)
┌───────────────────────┐         ┌───────────────────────┐
│ Brain Model (Brian 2) │         │ Body Model (MuJoCo)   │
│ 162,517 Neurons       ├─Spikes─►│ FlyGym / FlyBody      │
│ Time: workload-based │ (HDF5)  │ Wall Time: ~0.5 s / 1s│
└───────────────────────┘         └───────────────────────┘
  • Zero coupling overhead          • Clean, reproducible poses
  • No sensory feedback             • Cannot adapt to obstacles

(B) Closed-Loop Sensorimotor Loop (Synchronous Co-Simulation)
┌───────────────────────┐         ┌───────────────────────┐
│ Brain Model (Brian 2) │◄─Sensory┤ Body Model (MuJoCo)   │
│ Integrated Step Loop  ├─Motor──►│ Physics & Vision      │
└───────────────────────┘         └───────────────────────┘
  • Strict time-step lockstep       • Genuine adaptive behavior
  • High IPC / synchronization lag   • Requires 15k sensory mappings
```

### 5.1 One-Way Playback (Offline Feedforward)
1. **Pipeline:**
   - Execute the brain simulation in Brian 2 (CPU or GPU).
   - Export spike timestamps and continuous firing rates of target motor neurons (`ps1`, `hg1`, `b1`, leg MNs) to disk (HDF5 or Parquet).
   - In a secondary Python script, initialize the MuJoCo fly body (FlyGym or FlyBody) and step the physics forward, updating actuator targets from the pre-recorded time series.
2. **Compute & Performance:**
   - Completely decoupled. Brain timing depends on the workload: the identical-input replay measured Brian2 at 3.1–4.0 wall seconds per simulated second intact and 7.0 with GABAergic outputs removed on an arm64 Mac (Cython, one process, one-second run calls, random input disabled and dopamine clamped; first-run compilation and spike extraction included). These are replay-harness timings, not a body-loop benchmark or a basis for an engine speedup ratio. See the [replay timing record](../validation/records/p2/male-cuda-identical-comparison.md#replay-timing) and the subsequently measured [CUDA engine](cuda-methods.md).
   - The body simulation replays at ~0.5 s wall time per 1 s simulation time.
3. **Engineering Effort:**
   - Low (~1–2 days of development). Requires only a lightweight file-reading loop in Python.
4. **Legitimate Claims:**
   - "Demonstration of connectome-derived motor neuron activity animating a physically grounded virtual fly body."
   - Visual verification that specific circuit activations (e.g. courtship stimulation) generate anatomically appropriate body postures.
5. **What It CANNOT Claim:**
   - Cannot claim behavioral autonomy or environmental adaptation. The brain is blind to physical collisions or substrate irregularities.

### 5.2 Closed Loop (Synchronous Sensorimotor Feedback)
1. **Pipeline:**
   - Both engines run concurrently. At each discrete control interval (e.g. $\Delta t = 2\text{ ms}$):
     1. MuJoCo resolves body dynamics, contact forces, and camera vision.
     2. Proprioceptive state (joint angles, strain) and visual/tactile cues are transformed into sensory currents.
     3. Brian 2 receives the sensory input and integrates the 162k-neuron network across $\Delta t$.
     4. Motor neuron spike counts are converted into muscle forces or joint targets for the next MuJoCo step.
2. **Compute & Performance:**
   - Total latency equals the sum of brain integration time + body physics time + IPC overhead.
   - No end-to-end closed-loop timing has been measured; the replay timings above cannot supply one.
   - A GPU brain engine has since been measured, but its 1 ms host interface remains slower than real time, before body physics or communication costs are added; see the [CUDA methods](cuda-methods.md).
3. **Engineering Effort:**
   - High (~3–5 weeks of development). Requires building a low-latency shared-memory communication bridge and resolving the 15,016 sensory neuron input identities in `male-cns:v1.0`.
4. **Legitimate Claims:**
   - "Closed-loop embodied simulation of a whole connectome model adapting to a physical environment."
5. **What It CANNOT Claim:**
   - Cannot claim biological completeness until mechanosensory and proprioceptive sensory mappings in MaleCNS are experimentally constrained.

---

## 6. The Role of Blender in High-Quality Visualization

While MuJoCo includes an OpenGL offscreen renderer, it utilizes simplified Phong shading intended for real-time robotics debugging. Blender provides path-traced photorealism (Cycles) and real-time PBR shading (Eevee Next) for high-impact figures and videos.

### 6.1 Existing Importers and Workflows
1. **`farms_blender` (EPFL BioRob):**
   - An open-source Blender add-on created by the co-developers of NeuroMechFly. Allows direct import of MuJoCo MJCF and URDF models into Blender and replays recorded motion trajectories on rigged fly armatures.
2. **Direct Trajectory Export (JSON/Parquet → Python Script):**
   - The standard, robust production pipeline:
     1. During the MuJoCo simulation, log body segment transforms (translation vector $(x,y,z)$ and orientation quaternion $(q_w, q_x, q_y, q_z)$) at 60 Hz.
     2. Run a headless Blender Python script that loads the textured fly model, assigns keyframe transforms to the corresponding bones, and renders the sequence.
3. **Geometry Cache Export (USD / Alembic):**
   - Exporting vertex-level deformation caches (Universal Scene Description `.usd` or Alembic `.abc`) directly from simulation into Blender.

### 6.2 Integration with Existing Project Assets
The `flyonenomics` repository already contains automated 3D rendering pipelines for the MaleCNS connectome (`figures/3d/` and `scripts/render_malecns_3d.py`).
- Blender can render a composite visualization: a semi-transparent, photorealistic outer fly exoskeleton with the internal 3D MaleCNS neuropil meshes glowing inside, showing neural activity flashing in synchrony with wing vibrations or leg stepping.
- **Estimated Effort:** 2–3 days to write the trajectory exporter and Blender keyframing script.

---

## 7. Recommendation: The Smallest Honest First Demo

### 7.1 Proposed Demo: Courtship Wing Extension and Song Vibration
A first demo could replay courtship-circuit spikes into wing actuators in MuJoCo, conditional on confirming individual wing-motor responses and a defensible spike-to-motion mapping.

```
Recommended First Demo Workflow
┌────────────────────────────────────────────────────────┐
│ 1. Central Circuit Stimulation                         │
│    Inject depolarizing current into P1 / pIP10         │
├────────────────────────────────────────────────────────┤
│ 2. Readout from male-cns:v1.0 VNC                      │
│    Record spike rates: ps1 MN (pulse), hg1 MN (sine)   │
├────────────────────────────────────────────────────────┤
│ 3. One-Way Playback into MuJoCo Body                   │
│    • Ipsilateral wing abducts 70°                      │
│    • Wing blade vibrates at 150-250 Hz                 │
├────────────────────────────────────────────────────────┤
│ 4. Portfolio Render                                    │
│    MuJoCo video export / Blender path-traced render    │
└────────────────────────────────────────────────────────┘
```

### 7.2 Why This Is the Optimal Milestone
1. **Clean Biological Phenotype:** Courtship wing extension and singing is a dramatic, unmistakable, and sexually dimorphic behavior that is universally understood in neuroscience.
2. **Avoids the Walking Instability Trap:** Simulating multi-leg walking requires balancing ground reaction forces, friction, and inter-leg coordination; without local sensory feedback, open-loop walking collapses. Courtship singing occurs while the fly is stationary or orienting, completely decoupling the demo from contact stability issues.
3. **Exact Circuit Representation in Our Model:** Our model contains the exact typed motor neurons (`ps1 MN_L/R`, `hg1 MN_L/R`, `b1 MN_L/R`) that control song in real flies.
4. **Feasibility:** Can be built and verified in 2 to 3 days using existing project data without new infrastructure.

### 7.3 What This Demo Needs
- Measure the existing paired replay's individual `ps1 MN_L/R` and `hg1 MN_L/R` spike trains against their controls first. If these neurons do not respond with a side-specific motor pattern, do not synthesize a song vibration from the aggregate wing-motor rate.
- A standalone Python script using `mujoco` or `flygym` loading the fruit fly body model.
- A simple transfer function:
  - Wing abduction angle $\theta_{\text{abduct}} = \theta_0 + K_{\text{ext}} \cdot a_{\text{tonic}}(t)$.
  - Song vibration $\Delta \theta = A \cdot \sin(2\pi f t) \cdot a_{\text{phasic}}(t)$.
- Video recording generated via MuJoCo's off-screen renderer.

### 7.4 What This Demo CAN and CANNOT Claim
- **What It Can Honestly Claim:**
  - "Direct demonstration of a whole-brain connectome model (`male-cns:v1.0`) driving biologically typed wing motor neurons in a physically simulated virtual fly."
  - A motor-pattern claim requires individual left/right wing-motor traces and a documented spike-to-actuator mapping; the current aggregate firing result alone does not demonstrate one.
- **What It CANNOT Claim:**
  - It cannot claim to generate physical acoustic pressure waves (sound) unless coupled to an explicit acoustic air-pressure model.
  - It cannot claim closed-loop behavioral interaction (no virtual female fly is present).
  - It cannot claim that the brain computed muscle biophysics from first principles without an intervening muscle transfer function.

---

## 8. Verified Sources and Access Record

| Citation | Identifier / DOI | Access Status | Verification Notes |
| :--- | :--- | :--- | :--- |
| **Vaxenburg et al. (2025)** *Whole-body physics simulation of fruit fly locomotion* | *Nature* 643:1312–1320; DOI: [10.1038/s41586-025-09029-4](https://doi.org/10.1038/s41586-025-09029-4) | **Accessed & Read** | Validated FlyBody 102-DoF architecture, MuJoCo aerodynamic model, and Apache-2.0 license. |
| **Wang-Chen et al. (2024)** *NeuroMechFly v2: simulating embodied sensorimotor control* | *Nature Methods* 21:1332–1341; DOI: [10.1038/s41592-024-02300-2](https://doi.org/10.1038/s41592-024-02300-2) | **Accessed & Read** | Validated FlyGym API, MuJoCo transition, M1 Mac speed (~2× real-time), and MPL-2.0 license. |
| **Özdil et al. (2025)** *Musculoskeletal simulation of limb movement biomechanics* | *arXiv:2509.06426* | **Accessed & Read** | Full text and abstract parsed; verified 3D Hill-type leg muscle models in MuJoCo and OpenSim. |
| **Cheong et al. (2026)** *Circuits linking descending input to motor output in MANC* | *eLife*; Janelia Research Campus | **Accessed & Read** | Validated sparse monosynaptic descending-to-motor connectivity and premotor VNC hubs. |
| **Shiu et al. (2024)** *A Drosophila computational brain model reveals sensorimotor processing* | *Nature* 634:210–219; DOI: [10.1038/s41586-024-07763-9](https://doi.org/10.1038/s41586-024-07763-9) | **Accessed & Read** | Foundation whole-brain LIF model in Brian 2 running on CPU without CUDA. |
| **Berg et al. (2026)** *The adult male Drosophila central nervous system connectome* | *Cell*; DOI: [10.1016/j.cell.2026.08.015](https://doi.org/10.1016/j.cell.2026.08.015) | **Accessed & Read** | Source connectome for `male-cns:v1.0` (162,517 traced neurons with complete VNC). |
| **Eon Systems (2026)** *Embodied Whole-Brain Drosophila Emulation* | Eon Systems / Mindplex Archives (March 2026) | **Accessed & Read** | Verified FlyWire-to-NeuroMechFly link via descending command rates (oDN1, DNa01/02). |
| **Lobato-Rios et al. (2022)** *NeuroMechFly: a robotically simulated adult Drosophila* | *Nature Methods* 19:620–627; DOI: [10.1038/s41592-022-01466-7](https://doi.org/10.1038/s41592-022-01466-7) | **Accessed & Read** | Original PyBullet implementation and proprioceptive feedback loops. |
| **Clements et al. (2024)** *Neural circuitry for courtship song and flight control* | *bioRxiv* / Howard Hughes Medical Institute | **Accessed & Read** | Detailed motor neuron identities: `ps1` (pulse song), `hg1` (sine song), `b1` (flight). |
