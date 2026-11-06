# Integrated Fiji Drive (v3): propulsion, radiation and thermal architecture

Research and conceptual design only. Nothing in canon, `data/`, `src/` or the production Blender model changed. Every number comes from
`integrated.py` (written to `results/integrated.json`). Each claim marked *(src n)* has a source in section 10. Status labels follow the
Fiji workbook: LOCKED / WORKING / OPEN canon, and PROTOTYPE for my own choices.

**Bottom line.** No configuration closes the coupled numbers. About 10–33 % of D–³He fusion power leaves the plasma as neutral radiation
(bremsstrahlung plus D–D neutrons). No magnetic field, mirror or absorber can steer, reflect or recover it. Whatever hardware the plasma can see
takes a share of it. The first-wall flux limit therefore caps fusion power at P ≤ 2πR·L·q / f_neutral. The best physically coherent drive, IFD-1
(one open-cage core placed aft of the hull), reaches **~0.15 TW (0.09–0.29 TW) and 0.23 mg (0.11–0.49 mg)**. Today's model assumes 261 TW, and
1.1–1.5 g needs 739–1,008 TW: a gap of 3.5–4 orders of magnitude. The Wayfarer heat problem is **not solved**. It is reduced from impossible-in-hull
to a well-posed limit, and that limit rules out the current mission profile under D–³He.

## 1. Forensic audit of the three figures

| Figure | Formula (reproduced) | What it really is | Verdict |
|---|---|---|---|
| **45 TW** absorbed | 261.3 TW × 0.209 neutral × 0.819 intercepted = 44.7 TW | v2 Monte Carlo of the in-hull core: 82 % of isotropic rays hit coils, limiters, frames or lattice before reaching space | Correct for that geometry. The 82 % is geometry, not physics: a core inside the hull sees mostly hull |
| **645 GW** shield floor | 261.3 TW × 0.209 × (1 − cos 12.5°)/2 = 0.0118 → 647 GW | Only the solid angle of the thermal-bulkhead rim (r 37 m at X 48.9) seen from the core at X −118 | A lower bound for one shield. It assumes a perfect shield and counts nothing else |
| **10.8 GW** hot loop | hot_share 0.75 × 26,882 m² × 0.9 × σ × 1800⁴ = 0.75 × 14.4 GW | The drive's share of the existing 1800 K blades (`operating_point.py`, `wayfarer_3d.toml`) | A budget, not a mechanism |
| B01 **4 × 10⁻⁵** absorbed fraction | 10.8 GW / 261 TW | A requirement back-solved from the radiator budget. Fiji's own 1 × 10⁻⁴ is labelled "DIAGNOSTIC / UNVALIDATED" (15_ENERGY_FLOW), and P1 is "OPEN FUNDAMENTAL" (04_ROOT_TRUTHS) | Unsupported. No mechanism in canon or literature delivers it |
| Canon **η 0.8** | — | It exceeds the charged share: 1 − 0.21 neutral − 0.10 synchrotron = 0.69 before nozzle losses, 0.62 after | Inconsistent; 0.62 is used here |

The 20 % radiation fraction was **derived, not assumed**. A Maxwellian D–³He reactivity, relativistic bremsstrahlung (Z_eff from the fuel mix) and the
D–D side branch give 0.195 at Ti = Te = 100 keV and 1:1. That matches the NASA DFD share of 0.205 *(src 2)*. The fraction rises to 0.336 at
the WORKING canon ratio 2.5:1 He3:D (more He-3 means more electrons per reaction) and falls to 0.10 only in an unproven hot-ion mode *(src 7)*.

## 2. Integrated energy flow

See `diagrams/energy_flow.png`. Below is the closed ledger at IFD-1 (central case, 154 GW fusion). It sums to 1.000 and counts every joule once.

| Channel | Share | GW | Where it goes |
|---|---|---|---|
| Directed exhaust (charged products + H2 mass loading) | 0.620 | 95.7 | thrust 10.0 kN at ve 19,201 km/s |
| Nozzle divergence / detachment loss | 0.085 | 13.0 | aft plume, not ship heat |
| Synchrotron to space (net of 0.98 coil-face reflection) | 0.100 | 15.4 | coil gaps |
| Bremsstrahlung to space | 0.133 | 20.6 | coil gaps, aft cone |
| Neutrons to space | 0.007 | 1.1 | coil gaps, aft cone |
| Neutral radiation into coil armour | 0.049 | 7.6 | Li heat pipes → 1800 K hot loop → blades |
| Neutral radiation into the shadow shield | 0.006 | 0.9 | hot loop |
| Into blades and hull | 0.000 | 0 | shadowed |

Hot-loop load: 8.45 GW of the 10.8 GW budget (78 %). Charged products are the only channel the Fiji field acts on. Photons and neutrons travel in
straight lines from the moment of emission, so the architecture's job is to give them a clear view of space.

## 3. Recommended concept: IFD-1, aft open-cage drive

One integrated drive, not a menu:

1. **One D–³He core, aft of the hull, on the thrust axis.** Plasma r 5 m × 60 m at X −199…−139. The coil face is at R 8 m, the coil outer at 9.8 m.
   Taking the core out of the hull drops the hardware-intercepted share of neutral radiation from 0.82 to 0.28. That is the single largest gain available.
2. **Open-cage field coils.** 16 sparse REBCO coils covering 25 % of the solid angle seen by the plasma. 72 % of neutral radiation leaves through
   the gaps. Field B ≈ 7.8 T (central); the Fiji lattice runs at roughly 1.5× seed amplification, far below its 30× ceiling. The wall flux, not the
   field, sets the limit.
3. **Plasma-facing armour:** nanostructured W on Li heat pipes at ~1850 K, at the 10 MW/m² limit *(src 3)*. It feeds the existing 1800 K hot
   loop through three trunks in the blade planes, with no new radiator. Coil faces are polished to reflect far-infrared synchrotron (R ≈ 0.98).
4. **Neutron shield per coil, 1.27–1.4 m** (W / B4C / hydride). The mission fluence is ~1–3 × 10²⁴ n/cm² whatever the power (fixed mission
   energy); REBCO tolerates ~3 × 10¹⁸ *(src 4)*. That requires 13–14 e-folds.
5. **Layered shadow shield** at X −136.5, r 7.2 m: W | B4C | LiH | steel. It protects the hull end, tanks and blades. The propellant tanks act
   as additional shadow mass.
6. **One axial magnetic nozzle**: 6 coils with 4 Fiji trim sectors for thrust vectoring. H2 mass loading at the forward gas box and the nozzle ring
   (charged-channel only).
7. **Interfaces** (`diagrams/interfaces.png`): thrust path nozzle → strongbacks → shield ring frame → hull primary frames. H2, D and He-3 feeds run
   inside shield sleeves. The power bus seeds 5 T before lattice activation. Startup, shutdown and fault isolation are listed in the diagram.

Performance, central case: 154 GW fusion, 10.0 kN, **0.23 mg**. First burn takes ~60 years; total mission burn time is ~240 years.
Drive mass is ~4,400 t (armour and coil shields 3,444 t). That is about the whole ship's current departure mass (4,426 t), and it is not yet in
the mass budget.

## 4. Inclusion / exclusion register

| Status | Element | Reason |
|---|---|---|
| INCLUDED | Aft open geometry (core out of the hull) | Hardware share 0.82 → 0.28. The biggest lever by far |
| INCLUDED | Open-cage sparse coils (25 % coverage) | Neutral radiation escapes through the gaps; coverage trades against field quality (OPEN) |
| INCLUDED | Nanostructured W armour on Li heat pipes → 1800 K hot loop | 10 MW/m² at a temperature the existing blades can reject *(src 3)* |
| INCLUDED | FIR-reflective coil faces | Synchrotron is far-infrared; metals reflect ~98 % |
| INCLUDED | Layered shadow shield + BNNT/hydride neutron layers | Neutron moderation and capture *(src 8)*; protects tanks, blades and hull |
| INCLUDED | Propellant tanks as shadow mass | LH2 mean free path ~0.09 m for 2.45 MeV neutrons. Useful only as stationary shielding |
| INCLUDED | H2 gas-box edge mass loading | Charged channel only; it is how DFD raises thrust *(src 2)* |
| INCLUDED (minor) | H2 regenerative nozzle cooling | 0.05 GW capacity at today's flow: real but negligible |
| INCLUDED (minor) | Nanostructured high-ε radiator coating | ε 0.90 → 0.95 gives +5 % rejection. No other "nanotech" gain is available |
| INCLUDED | REBCO flux pinning, Fiji lattice field law (canon) | Unchanged |
| CONDITIONAL | Flowing liquid Sn (20 MW/m², 1300 K) or Li (50 MW/m², 800 K) armour | Doubles or quintuples power, but needs 14,000–330,000 m² of **new** low-temperature radiator *(src 3)*. Li at 50 MW/m² is a projection (~10 demonstrated) |
| CONDITIONAL | Liquid-droplet radiator (1300 K) | Lightest per GW (62 t / 10 GW) but only works at milli-g; droplets fail at 1.5 g *(src 6)* |
| CONDITIONAL | Hot-ion mode (Te ≈ Ti/2), D-rich fuel | Halves the neutral share, but unproven for D–³He. Fusion products heat electrons |
| REJECTED | X-ray mirrors / grazing optics | Deflection ≤ 2θc ≈ 0.1–1° at 10–50 keV *(src 5)*. Cannot turn isotropic emission away |
| REJECTED | Expendable X-ray absorber or propellant routing to exhaust | One e-fold at 100 keV needs 5 (W) to 526 (Li) kg/m². Held in place at exhaust energy, it would carry 10¹⁵–10¹⁷ Pa against the 9 × 10⁹ Pa of a 150 T field *(src 9)* |
| REJECTED | Ablating liquid metal or propellant | 10⁴–10⁶ kg/s per TW absorbed. Propellant would be gone in hours |
| REJECTED | Pulsed liner (FDR-like) at this ve | At 19,200 km/s it implies ~17 kt TNT-class pulses at ~3.6 Hz. That is a different drive class *(src 1)* |
| REJECTED | Direct X-ray or neutron steering by Fiji | Not physics; forbidden by the brief |
| REJECTED | 6×6 and 8×8 module rings | Plasma radius < 0.25 m after the 1.8 m coil-and-shield build |

## 5. Quantitative budgets with uncertainty

Maximum fusion power and acceleration within the aft cluster envelope (L 30 m, R_out 6.5 m), for every case × armour combination:

| Case | Armour | F5 1×1 | F0 1×4 aft | F1 2×4 | F2 4×4 | F3 6×6 | F4 8×8 |
|---|---|---|---|---|---|---|---|
| optimistic | W / Li heat pipe 1800 K | 77 GW / 0.13 mg | 77 GW / 0.13 mg | 53 GW / 0.09 mg | 65 GW / 0.11 mg | infeasible | infeasible |
| optimistic | flowing Sn 1300 K | 154 GW / 0.26 mg | 154 GW / 0.26 mg | 106 GW / 0.18 mg | 131 GW / 0.22 mg | infeasible | infeasible |
| optimistic | flowing Li (projection) | 385 GW / 0.65 mg | 385 GW / 0.65 mg | 266 GW / 0.45 mg | 327 GW / 0.55 mg | infeasible | infeasible |
| central | W / Li heat pipe 1800 K | 40 GW / 0.06 mg | 40 GW / 0.06 mg | 28 GW / 0.04 mg | 34 GW / 0.05 mg | infeasible | infeasible |
| central | flowing Sn 1300 K | 81 GW / 0.12 mg | 81 GW / 0.12 mg | 56 GW / 0.08 mg | 69 GW / 0.10 mg | infeasible | infeasible |
| central | flowing Li (projection) | 202 GW / 0.30 mg | 202 GW / 0.30 mg | 140 GW / 0.21 mg | 172 GW / 0.26 mg | infeasible | infeasible |
| canon 2.5:1 | W / Li heat pipe 1800 K | 24 GW / 0.03 mg | 24 GW / 0.03 mg | 16 GW / 0.02 mg | 20 GW / 0.02 mg | infeasible | infeasible |
| canon 2.5:1 | flowing Sn 1300 K | 47 GW / 0.06 mg | 47 GW / 0.06 mg | 33 GW / 0.04 mg | 40 GW / 0.05 mg | infeasible | infeasible |
| canon 2.5:1 | flowing Li (projection) | 118 GW / 0.14 mg | 118 GW / 0.14 mg | 81 GW / 0.10 mg | 100 GW / 0.12 mg | infeasible | infeasible |

IFD-1 (R 8 m, L 60 m, W armour):

| Case | Fusion power | Thrust | Acceleration | Burn 1 | Gap to 1.1 g |
|---|---|---|---|---|---|
| optimistic | 293 GW | 21.4 kN | 0.49 mg | 28 y | 2,500× |
| central | 154 GW | 10.0 kN | 0.23 mg | 60 y | 4,800× |
| canon 2.5:1 | 90 GW | 4.6 kN | 0.11 mg | 128 y | 8,200× |

Reference points:
- **Status quo** (in-hull v2 core, R 3.37 m, L 7 m): wall-limited to 4–14 GW, heat-limited to 39–128 GW.
- **Sensitivity extreme** (L 120 m, R 15 m, flowing Li at 50 MW/m²): 2.9 TW / 4.3 mg central, 5.5 TW / 9.3 mg optimistic. This needs a
  ~140 m drive section and ~10⁵ m² of new 800 K radiator. Even this is ~90× short of today's 261 TW.
- **Requirement:** 1.1 g needs 47.7 MN and ~739 TW of fusion at η 0.62. 1.5 g needs 65 MN and ~1,008 TW.

Main uncertainties: electron temperature and fuel ratio (×3 on the neutral share); the wall limit (10–50 MW/m², ×5); coil coverage
(0.15–0.35); and the REBCO fluence limit, where in-situ data suggest it is lower *(src 4)*.

## 6. Topology sensitivity study

Monte Carlo with 200,000 rays per topology. Line sources are traced against their own coils, neighbouring modules, the shadow shield, the
hull and the three blades. Results for the central case with W armour:

| Topology | Plasma r (m) | Own | Neighbour | Shield | Escape | P_fus | Hot load | Drive mass | One module out |
|---|---|---|---|---|---|---|---|---|---|
| F5 1×1 | 3.70 | 0.251 | — | 0.052 | 0.697 | 40 GW | 2.4 GW | 1,425 t | thrust 0 |
| F0 1×4 aft (canon topology) | 3.70 | 0.251 | — | 0.052 | 0.697 | 40 GW | 3.2 GW (manifold +35 %) | 1,485 t | thrust 0 |
| F1 2×4 | 0.95 | 0.251 | 0.050 | 0.095 | 0.603 | 28 GW | 2.7 GW | 2,366 t | 50 % left, 1.2° trim |
| F2 4×4 | 0.39 | 0.250 | 0.131 | 0.091 | 0.527 | 34 GW | 3.2 GW | 3,010 t | 75 % left, 0.5° trim |
| F3 6×6 | < 0.25 | infeasible | | | | | | | |
| F4 8×8 | < 0.25 | infeasible | | | | | | | |

Ranking: **1×1 ≈ 1×4 > 4×4 > 2×4 ≫ 6×6, 8×8.**

- Splitting the power into modules shrinks each plasma inside a fixed envelope.
- Each 1.8 m radiation build eats the radius.
- Neighbours irradiate each other (5–19 %), and the shield grows to cover the cluster.

Reactor count and nozzle count are independent:
- Extra nozzles on one core (1×4) cost +35 % heat in the manifold and buy no power.
- Extra cores buy redundancy but lose power and gain mass.

No topology changes the order of magnitude.

## 7. Conceptual Blender package

`CONCEPT_FIJI_V3.blend` (packed; it opens on the side overlay) uses the Nov-1 functional colours (`functional_colors.py`): MAIN_PROPULSION
magenta, HOT_RADIATOR red, HYDROGEN blue, DEUTERIUM teal, HELIUM3 violet, POWER indigo, structure grey.

| Scene / camera | Shows |
|---|---|
| IFD1_INTEGRATED · CAM_V3_SIDE_OVERLAY | Axial layout with overlays: plasma, protected-zone cone, escape bands through the coil gaps, aft escape cone, shield zones, coolant trunks, exhaust |
| CAM_V3_WHOLE | IFD-1 behind the truncated hull and blades: real proportion |
| CAM_V3_AFT | Mid-plasma aft section: coil ring, armour, plasma, H2 ring, fueller, trunks |
| IFD1_CUTAWAY · CAM_V3_CUTAWAY | 180° cutaway of coils, armour and shield layers, plus the nozzle |
| TOPOLOGY_LAYOUTS · CAM_V3_TOPOLOGIES | F5, F0, F1, F2 (longitudinal and aft) and F3/F4 packing sketches marked INFEASIBLE, labelled from `integrated.json` |

The renders are PNGs beside the .blend. Diagrams: `energy_flow.png` and `interfaces.png`.

## 8. Recommendation and blockers

**(a) Reactor count: one.** It gives the most power within any envelope, the smallest shield and the lowest mass. Redundancy is better bought with
spare coil sectors and trim than with extra cores.

**(b) Nozzle count: one axial magnetic nozzle with 4 Fiji trim sectors.** This keeps the canon's four-way vectoring function without the manifold.
The canon "1 core → 1 manifold → 4 nozzles" (LOCKED) still works as a fallback at +35 % hot-loop heat and the same power. Changing it needs your
approval.

**(c) Aft placement and shielding:**
- The core sits fully aft of the hull, in an open cage, behind a layered W/B4C/LiH/steel shadow shield at the hull end.
- Each coil carries 1.3–1.4 m of neutron shield and W armour on Li heat pipes feeding the existing 1800 K loop.
- This lengthens the ship by ~60–75 m (core + nozzle). That is an enlargement I have **not** applied; it needs your approval.

**(d) Unresolved blockers:**
1. **Wall flux.** P ≤ 2πR·L·q / f_neutral holds for any D–³He geometry. Closing 261 TW would take ~10⁵ m² of first wall at 50 MW/m² inside
   the plasma's view.
2. **Mission.** At ~0.2 mg, 0.016 c takes centuries of burn. The 1.1–1.5 g acceleration targets and today's 261 TW are infeasible with
   D–³He + Fiji as defined.
3. **Mass.** Armour and shields of ~3.4 kt are not in B01.
4. **Fiji P1 and the 1 × 10⁻⁴ diagnostic remain OPEN** in canon.
5. **REBCO fluence** under mixed neutron/gamma loads is uncertain.

**(e) Does any configuration substantially reduce the absorbed neutral burden?** Yes per TW, no in total. Moving the core aft and opening the cage
cuts the hardware share from 0.82 to 0.28 (~3×) and raises the power ceiling 5–20× over the in-hull status quo. Multi-module clusters make it
worse. Nothing gets within three orders of magnitude of the 4 × 10⁻⁵ requirement at the required power.

**Owner decisions needed before any canon or production change:**
- Accept the wall-flux limit and redefine the mission (a power-limited milli-g drive: accept centuries, or change ve/mass).
- Allow a canon topology change (1 core → 1 axial nozzle).
- Allow the ship to lengthen by ~60–75 m aft.
- Or reopen a different fuel cycle or drive class (p–¹¹B is worse on bremsstrahlung; pulsed/inertial is a different drive).

## 9. Component / interface table

| Component | Function | Interfaces | Key numbers | Status |
|---|---|---|---|---|
| Reaction zone | D–³He burn | fueller, coils, nozzle | 154 GW, r 5 × 60 m | PROTOTYPE |
| Field coils (16) | confinement, Fiji lattice | power bus, armour, strongbacks | 7.8 T, 25 % coverage | PROTOTYPE (lattice law canon) |
| W armour + Li heat pipes | first wall | coils, hot trunks | 10 MW/m², ~1850 K, 7.6 GW | PROTOTYPE |
| Coil neutron shield | REBCO fluence | coil, armour | 1.3–1.4 m | PROTOTYPE |
| Shadow shield | protect hull, tanks, blades | hull end frame, hot loop | r 7.2 m, ~410 t, 0.9 GW | PROTOTYPE |
| Hot trunks (3) | carry heat to blades | armour, shield, blade roots | 8.45 GW of 10.8 | PROTOTYPE |
| Axial nozzle + 4 trim sectors | thrust, vectoring | strongbacks, H2 ring | η 0.62, 10 kN | PROTOTYPE |
| H2 feed / gas box / nozzle ring | mass loading | tank farm | 0.52 g/s | PROTOTYPE |
| D, He-3 feeds + axial fueller | fuelling | tank farm, shield sleeves | 1:1 (canon 2.5:1 WORKING) | PROTOTYPE |
| Power bus + 4 units | seed field, control | Brayton A/B, pulse bank | 5 T seed | canon seed |

## 10. Sources

1. NASA NIAC Fusion-Driven Rocket, Slough et al.: https://ntrs.nasa.gov/citations/20190001178
2. Direct Fusion Drive radiation and thrust model, Thomas, Paluszek et al.: https://arxiv.org/abs/2002.12686
3. Liquid lithium / PFC heat-flux limits (PPPL): https://www.osti.gov/biblio/1756723 ; NSTX liquid-lithium results (Maingi)
4. REBCO neutron fluence limit, ARC design (Sorbom et al.): https://arxiv.org/abs/1809.10555 ; Oxford in-situ irradiation studies
5. Grazing-incidence X-ray optics critical angle: https://arxiv.org/abs/astro-ph/0403449
6. Liquid-droplet radiators, Mattick & Hertzberg: https://ntrs.nasa.gov/citations/19810062992
7. D–³He bremsstrahlung and the hot-ion mode, Wisconsin FTI: https://fti.neep.wisc.edu/fti.neep.wisc.edu/research/fdm
8. Boron nitride nanotube radiation shielding (NASA): https://ntrs.nasa.gov/citations/20160010096
9. Photon attenuation coefficients, NIST: https://physics.nist.gov/PhysRefData/XrayMassCoef/
10. Fiji canon (IGNITION — Fiji / Lattice Drive Science Model): 04_ROOT_TRUTHS (P1, P6), 15_ENERGY_FLOW (DFD split, 1 × 10⁻⁴ diagnostic),
    30_DRIVE_THERMAL ("non-thrust energy must escape"), topology and lattice-temperature rows.
