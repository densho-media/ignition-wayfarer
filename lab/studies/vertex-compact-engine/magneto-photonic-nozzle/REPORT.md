# WAYFARER — Magneto-Photonic Nozzle (MPN): research report

Research study, not canon. Branch `claude/project-thread-1p6mtu`, model base 3866ebf, 2026-11-22. Every number comes from `mpn.py`
(results/mpn.json, results/mpn.log; 17 of 17 validation checks pass) unless a source is named. Figures in `figures/`; charts are
calculated values, fig6 is a schematic.

**Budget being tested.** The canon operating point holds: 261.3 TW fusion, 209.0 TW jet, four engines. The hot radiator rejects 14.40 GW,
of which the drive share is 10.80 GW (0.75). Hardware may therefore take 4.13e-5 of the fusion power. A single-bounce mirror that has to
handle the 32.4 TW the brief names as managed would need 99.967 % reflectivity. 52.2 TW of perfectly collimated photons would give 174 kN.

**Sources** (per engine; brems = bremsstrahlung, sync = synchrotron):

| Source | What it is | Brems | Sync | Neutrons | Te |
| --- | --- | --- | --- | --- | --- |
| V0 | the Vertex 1.5 LOW reference | 8.16 TW | 0 | 2.89 TW | 55 keV |
| V1 | 1.6B S1, spin-polarized | 6.59 TW | 0 | 3.24 TW | 57 keV |
| V2 | 1.6B S5: polarization, selective He-3 heating, channeling | 4.12 TW | 1.44 TW | 0.83 TW | 46 keV |
| V3 | V2 with neutrons ×0.25 (declared low-neutron burn) | 4.12 TW | 1.44 TW | 0.21 TW | 46 keV |

The bremsstrahlung spectrum is about 40 % below 30 keV, 45 % at 30–100 keV and 10–15 % above 100 keV. The exp(−E/Te) model matches the
Vertex 1.5 spectral bins to within 2 %.

## 1. Executive assessment

The MPN is scientifically meaningful as an **integrated radiation-management architecture**, but not as a photonic nozzle. Two different
outcomes:

- **Thermal viability can be reached on paper, by geometry and fuel rather than by mirrors.** Candidate F is an edge-on remote ribbon ring
  on the V2 fuel route. It puts 9.34 GW into hardware on four engines, which fits the 10.80 GW drive share: 3.31 GW is piped to the hot
  loop, and 6.03 GW is radiated by hot parts that radiate their own heat. It does not close the mass: about 779 t per engine, driven by
  the magnet. The charged leakage is still OPEN.
- **Photonics is a narrow tool.** It is useful for the leading edges of edge-on members and for far-IR synchrotron light (97–99.8 %
  reflection). It cannot be the thermal closure:
  - MeV neutrons cannot be reflected.
  - Hard X-rays reflect broadband only at ultra-grazing angles, about 0.4–2.9 mrad at 30–100 keV.
  - Coatings on the compact drawn engine reflect nothing, because its surfaces are hit at a median 53° and 5 % of hits are below 14°.
- **Photon thrust is negligible.** Even if every photon left aft without loss, V2 would add 74 kN, 0.085 % of thrust. A real collimator
  adds 0.006–0.01 % of thrust for 2.5–5.4 TW of new heat.

Worth pursuing: the **Prevent → Release** half of the chain (fuel that makes fewer photons and neutrons, and geometry that lets them escape).
Not worth pursuing: the **Reflect** half as a heat solution.

## 2. Scientific foundations (established)

- **Total external reflection.** X-rays see n = 1 − δ + iβ, and reflect below the critical angle θc = √(2δ).
  - θc (mrad) at 30 and 100 keV: diamond 1.27 and 0.38; Pt 2.80 and 0.84.
  - θc falls as 1/E, so a fixed mirror loses the hard end of the spectrum first (fig2).
  - Checked against the literature values at 8 keV for Si, Ni, Au and Pt.
- **Steering cost.** Turning a beam by φ keeps exp(−gφ), however many bounces it is split into, with g = 2β/θc³ in the grazing limit
  (validated against Fresnel to within 0.2 %).
  - g per radian at 30 keV: diamond 0.25, Be 0.30, Pt 16. At 100 keV: diamond 1.8, Pt 35.
  - Compton scattering sets a floor that no surface beats: 1.85 per radian at 100 keV and 79 at 1 MeV for diamond's electron density (fig1).
- **Multilayers (Parratt, Névot–Croce roughness).**
  - W/Si and Pt/C reach 0.88–0.98 at a single Bragg peak, with a bandwidth of 0.3–2 %.
  - Depth-graded supermirrors on the broadband 55 keV continuum absorb 0.50–0.52, against 0.46 for the best plain coating. Broadband
    makes them worse, not better.
- **Crystals (Bragg, Laue).**
  - Perfect crystals: intrinsic bandwidth about 1e-4 (Si(111) is 1.31e-4, matching the literature). Broadband efficiency is 2e-5 to 1e-4.
  - Mosaic crystals: 2e-3 to 8e-3. Graded or bent crystals: about 1e-2.
- **Neutron optics.** θc(Ni) is 3.2e-7 rad at 2.45 MeV and 1.3e-7 rad at 14.1 MeV; the best m = 10 supermirror is ten times that.
  - Hiding a 3 cm edge from a D-D neutron needs 9.5 km of supermirror, or 328 m at a lattice-scale (Bragg) angle.
  - Neutrons are released, never reflected.
- **Far-IR (cyclotron and synchrotron) light.** Metals reflect it at 97–99.8 % (Hagen–Rubens): Cu at 300 K is 0.9985 at 0.3 THz, and
  W at 1,800 K is 0.974–0.992.

## 3. Future technology assessment (three maturity levels)

| Topic | A: established | B: advanced extrapolation | C: speculative, and its physical boundary |
| --- | --- | --- | --- |
| X-ray mirrors | Grazing Wolter optics and NuSTAR-class multilayers (≤ 80 keV) | Diamond or Be skimmers kilometres long at sub-mrad figure | A broadband mirror at large angles. **Bounded:** β/δ and the Compton floor fix g whatever the structure is. |
| Gamma optics | Laue lenses, bandwidth about 1e-2 | Graded and bent crystal stacks | High-efficiency gamma reflection. **Bounded:** δ ∝ 1/E², so θc is µrad at MeV. |
| Neutron optics | m = 6–7 supermirrors for cold and thermal neutrons | m = 10–20 | Reflection of MeV neutrons. **Bounded:** θc ≈ 1e-7 rad. |
| Metamaterials | Photonic crystals for IR and optical light | Structured far-IR walls | An X-ray index set by structure. **Bounded:** at keV the wavelength is below the atomic spacing, and the index follows electron density alone. |
| Plasma mirrors | Relativistic plasma mirrors for optical lasers | Dense plasma reflecting far-IR synchrotron light | A plasma X-ray mirror. **Bounded:** reflecting 30 keV needs n_e ≈ 6.5e35 m⁻³, about 1e6 times solid density. |
| Self-healing and adaptive structures | Lithium and liquid-metal walls, re-deposited coatings | Surfaces that re-polish themselves under ablation | Roughness held below 0.2 nm under pulsed flux. Roughness, not the material, is then the limit. |

Fiji: the canon capability card amplifies and stabilises an applied field only. No photon or neutron property is assigned to it
(BT-008 rule kept).

## 4. Material candidates

The figure of merit is β/δ, which sets g, plus the Compton floor. Values at 30 and 100 keV, from xraylib:

| Material | θc 30 keV (mrad) | g 30 keV (/rad) | θc 100 keV (mrad) | g 100 keV (/rad) | Role |
| --- | --- | --- | --- | --- | --- |
| Diamond (C) | 1.27 | 0.25 | 0.38 | 1.84 | lowest loss per radian above 20 keV; long skimmers |
| Be | 0.87 | 0.30 | 0.26 | 2.69 | low loss, toxic and soft |
| SiC | 1.22 | 1.16 | 0.36 | 2.12 | structural option |
| Ni | 1.99 | 7.46 | 0.59 | 3.36 | neutron-mirror heritage |
| W, Ir, Os, Pt, Au | 2.7–2.9 | 14–18 | 0.80–0.86 | 32–38 | widest angle and shortest wedge (Pt and Os are best per metre, fig3); highest loss per radian |
| cBN, LiH | in data/optics.json | | | | dielectric and neutron-moderator options |

Eddy screen, inside the magnetic region (field swing 0.33 T in 10 µs, duty 0.2):

| Nose or film | Eddy heating per engine |
| --- | --- |
| Bulk W nose | 535 GW |
| W nose laminated at 1 mm | 0.28 GW |
| B4C nose | 3 GW |
| BN or diamond nose | negligible |
| 50 nm Pt film, tiled at 1 mm | 3e-5 GW |
| 50 nm Pt film, untiled | 0.31 GW |

**Rule:** magnetic-region parts are dielectric or laminated, and films are tiled.

## 5. Alternative architectures

| Candidate | Idea | Result |
| --- | --- | --- |
| A, reflective skeletal nozzle | best coatings on the drawn compact engine | reflects 0.0000: only 0.02 % of hits are below 1° (fig7) |
| B, grazing-incidence photonic nozzle | nested diamond collimator outside a 25° plume cone | absorbs 15–17 % of the photons it catches: +2.5 to +5.4 TW of heat for +0.006 to +0.01 % thrust |
| C, selective deflection | grazing fairings on the drawn engine | reflects 1.8–2.1 %; photon heat stays 10–20 TW on four engines, and neutrons up to 7.1 TW |
| D, Halo MPN | Halo 2.5 ring (R 51 m, burn 114 m away) plus knife-edge skimmers | 20–69 m skimmers save 7–20 t of radiator, weigh 41–140 t and add 3,200–11,000 m² of broadside: net negative |
| E, integrated Fiji | Fiji as a field amplifier for the ring | no photon or neutron effect is allowed by canon. It reduces the conductor only through the field-energy ratio (see 9). |
| F, hybrid | edge-on remote ribbon ring, edge-on tapes, self-radiating plug and strips, spine in the plug's shadow, V2 or V3 fuel | **fits the heat budget** (9.34 GW on V2, 8.88 GW on V3); mass about 750–780 t per engine |

The **edge-on principle** is that a planar member whose plane contains the burn shows only its thickness. It cuts the ring's sky from
4.3e-4 (a Halo-like 0.24 m face) to 1.1e-4 (a 7 cm ribbon). Tension tapes cut their sky from 1.3e-4 (round cables) to 1.6e-5.

## 6. Quantitative radiation ledger

Four engines, V2 source, heat into hardware (fig5).

| Candidate | Photons | Neutrons | Charged | Total | Fits 10.8 GW |
| --- | --- | --- | --- | --- | --- |
| Drawn engine, bare | 10,161 GW | ≤ 2,037 GW | — | > 10 TW | no |
| A coatings | 10,161 GW | ≤ 2,037 GW | — | > 10 TW | no |
| C fairings | 9,947 GW | ≤ 2,037 GW | — | > 10 TW | no |
| B collimator (added) | 2,468 GW | — | — | +2.5 TW | no |
| D Halo 2.5 ledger (its own source) | ring armour 5.1 GW | small | 3.3 GW | 8.8 GW | yes, but 1.7× on the V2 map at the same sky |
| F thick face, round cables | | | | 19.1 GW | no |
| F edge-on ribbon and tapes (R 62 m) | | | | 11.6 GW | no |
| **F recommended (R 90 m, burn 180 m aft, 2 km spacing)** | | | 3.3 GW (bound) | **9.34 GW** | **yes** |
| F recommended + 20 m Pt skimmer | | | | 16.6 GW | no (cross-irradiation) |

Per-member ledger of F (per engine) in results/mpn.log, section "F". The hardware sky that fits with full absorption is 6.6e-4 (V2,
photons only) and 3.3e-4 (V0). Neutrons alone allow 6.5e-3 (V2) to 2.6e-2 (V3). Feasibility map: fig4.

## 7. Thermal feasibility

- The compact drawn engine is out by about 1,000×. No optic changes that, because it sees 62 % of the sky at steep angles.
- Remote rings fit only when they are edge-on and widely spaced.

Sensitivity of F (four engines):

| Change | Heat into hardware | Fits |
| --- | --- | --- |
| None (recommended) | 9.34 GW | yes |
| V0 source | 13.9 GW | no |
| Engine spacing 1,000 m | 18.9 GW | no |
| Ship 1,000 m away | 14.7 GW | no |
| Round cables | 10.68 GW | yes, barely |
| V3 source | 8.88 GW | yes |
| Charged leakage ×0.1 | 6.40 GW | yes |

- The nose runs at 1,702 K and radiates its own heat; it is W-B4C, 0.46 m long, sized to the fluence limit of 3e22.
- The cold ribbon behind it takes 0.012 GW per engine of scattered-in neutrons. That costs about 300× at 20 K, and is booked in B01.
- Optimiser, 600 points per source:
  - V0 has no point where all heat fits.
  - V2 has 4 such points and V3 has 6, all without skimmers.
  - Skimmers appear only in the lightest points that fit the piped (B01) heat alone, where they let a smaller ring keep its nose cool.

## 8. Propulsion assessment

- Jet thrust per watt is 31× photon thrust per watt (2/ve against 1/c), so every watt left in the jet is worth 31 watts of photons.
- Ideal, loss-free, all-aft photons give 109 kN on V0 and 74 kN on V2. That is 0.125 % and 0.085 % of thrust.
- Real collimator: +0.006 to +0.01 %, bought with 2.5–5.4 TW of heat. Photon thrust is not a reason to build anything.
- Effect on the magnetic exhaust:
  - Members laid along the rays stay outside the plume cone.
  - Dielectric noses and tiled films keep the eddy coupling negligible.
  - Reflected far-IR synchrotron light leaves the hardware and returns no momentum worth counting.

## 9. Ship integration

Mass of F at the recommended point, about 779 t per engine:

| Item | Mass per engine |
| --- | --- |
| REBCO conductor | 239 t |
| Structure (virial ×2) | 348 t |
| Nose | 125 t |
| Spine | 54 t |
| Plug, strips, tapes | about 13 t |

The yardsticks are the Halo 2.5 ring (320 t) and an 85 t compact engine, so the mass fails. The levers:

| Lever | Mass per engine |
| --- | --- |
| Field-energy ratio 10 instead of 50 | 367 t |
| REBCO current density ×2 | 631 t |
| Halo 2.5 pulse rate of 6.8 kHz | 1,674 t |

The field ratio is the one lever that matters, and it needs a charged-leakage model to justify it (Q-MPN-3, Q-MPN-4).

Structure and operations: like the Halo Vertex, F places rings and a spine about 2 km from the ship. That is the geometry the owner rejected
as a baseline on 2026-11-17 (dust exposure, compression booms, deployment, silhouette). Edge alignment must hold to a few mrad. The heat
goes to the hot loop (3.3 GW) and to self-radiating hot parts at 1,200–1,900 K, which need no radiator area.

## 10. Conceptual visualizations

| File | Shows |
| --- | --- |
| fig1_steering_cost.svg | loss per radian against energy, with the Compton floors |
| fig2_reflectivity.svg | reflectivity against grazing angle |
| fig3_skimmer_law.svg | absorbed share against wedge L/a |
| fig4_feasibility_map.svg | hardware sky × absorbed share, with the candidates marked |
| fig5_ledger.svg | candidate heat against the 10.8 GW line |
| fig6_concept_F.svg | schematic of F, not to scale; rays are illustrative |
| fig7_drawn_engine_incidence.svg | why coatings fail on the compact engine |

No Blender review file: the study changes no geometry.

## 11. Recommended architecture

**F at V2 (or V3):**

- edge-on REBCO ribbon ring, R 90 m, 4.4 cm thick, burn 180 m aft of it, 21 MA;
- dielectric or laminated W-B4C hot nose;
- edge-on tension tapes;
- self-radiating shadow plug, spine in its shadow;
- engines and ship 2 km apart;
- no skimmer;
- synchrotron light reflected by metal walls, X-rays and neutrons released to space.

Chain: **Prevent** (V2/V3 fuel) → **Direct** (magnetic, charged) → **Reflect** (far-IR, and grazing at leading edges only) → **Release**
(edge-on, remote) → **Recover** (none worth booking) → **Dissipate** (self-radiating hot parts and B01).

It fits the heat budget. It does not close the mass, and it brings back the remote geometry the owner rejected. It is a research
direction, not a candidate baseline.

## 12. Breakthrough requirements

| ID | Name | Status | What it needs |
| --- | --- | --- | --- |
| BT-009 | grazing knife-edge photon skimmer | Level B, CALCULATED, PROPOSED, NON_CANON | net negative in both cases computed; useful only for nose temperature |
| BT-010 | edge-on remote ribbon ring | Level B, CALCULATED, PROPOSED, NON_CANON | a charged-leakage model, alignment, and a mass lever |
| BT-008 (SR-1, existing) | photon thrust or thermal closure gap | unchanged | MPN shows that the gap closes by geometry plus V2 fuel, not by photon suppression |

Plausibility: no new physics is required. The mass needs either a lower field-energy ratio (physics to be shown by Monte Carlo) or an
advanced superconductor current density.

## 13. Validation roadmap

1. Charged-particle Monte Carlo of the edge-on ring's leakage and the field-energy ratio it allows (Q-MPN-4).
2. Photon transport through the four-engine cluster with reflections followed to their next hit; OpenMC or Geant4 for neutrons, if the
   owner allows a transport code.
3. Alignment tolerance and structural dynamics of the ring, tapes and 2 km spine.
4. Ablation and roughness life of noses and films under pulsed 30–100 keV flux.
5. Only if Q-MPN-2 is yes: a `WORK_MPN` Blender collection with the F geometry for a review file.

## Owner questions

- **Q-MPN-1.** Accept that photonics is a narrow tool (leading edges, far-IR) and not the thermal closure?
- **Q-MPN-2.** Pursue edge-on remote geometry (F), knowing it brings back the 2 km structure rejected for the Halo Vertex?
- **Q-MPN-3.** Which magnet mass lever to study: field-energy ratio, current density, or pulse rate?
- **Q-MPN-4.** Run the charged-leakage Monte Carlo (workstation-scale compute)?
- **Q-MPN-5.** Adopt V2 or V3 (the 1.6B fuel route) as the reference source for drive thermal studies? Coordinate with the accelerator
  selective-fusion study.

## Sources

- xraylib 4.3.0 (Schoonjans et al., Spectrochimica Acta B 66, 2011): photoabsorption, scattering, optical constants.
- Névot and Croce (1980): roughness.
- Parratt (1954): multilayer recursion.
- Klein–Nishina: Compton cross section.
- Darwin widths: xraylib crystal module.
- Neutron scattering lengths: Sears (1992).
- Hagen–Rubens: far-IR metal reflectivity.
- Project models: Vertex 1.5 (references/evidence/vertex_radiation.json, src/wayfarer/vertex_radiation.py), 1.6B
  (vertex_source.json), Halo Vertex 2.0–2.5 (lab/variants/halo-vertex), canon operating point (references/p1_operating_point.json).
