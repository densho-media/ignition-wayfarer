# T02 report: dust, radiation exposure and braking protection

| | |
| --- | --- |
| Thread | T02, spacecraft protection and mission survivability |
| Date | 2026-11-09 |
| Status | Research, not canon. Nothing here changes `data/`, `src/`, production geometry or Drive. |
| Base | `8de3ffa` (Phase 1 base), branch `claude/project-thread-uwi5pl` |
| Inputs from other threads | T04 EARLY `1b85941` (emission shares), T01 EARLY `57fe625` (radiator envelopes); T03 had not published |

Every number below comes from a script in this folder; tables are generated in [`TABLES.md`](TABLES.md). Labels: PUBLISHED, MODEL,
EXTRAPOLATION, ASSUMPTION, TARGET, CANON, UNKNOWN (planning/HANDOFF.md).

```bash
python3 lab/variants/vertex-drive/studies/dust/environment.py   # ~8 s  -> environment.json
python3 lab/variants/vertex-drive/studies/dust/exposure.py      # ~45 s -> exposure.json (reproduces P11 first)
python3 lab/variants/vertex-drive/studies/dust/impacts.py       # ~1 s  -> impacts.json
python3 lab/variants/vertex-drive/studies/dust/radiation.py     # <1 s  -> radiation.json
python3 lab/variants/vertex-drive/studies/dust/tables.py        #       -> TABLES.md
```

## Answer in short

**A protection-development pathway exists for everything except the engine hardware itself, and the engine hardware needs a different
answer: damage tolerance and replacement, not shielding.**

1. The large-area problem (tanks, habitat rings, the back of the forward shield: 12,300 m² on Vertex, 4,000 m² on the canon ship when
   braking) is solved geometrically by a **shadow-cone skirt** (proposed T02-NEW-1): a thin sheet on the burn's hardware cone, edge-on to
   the burn and inside the shield's shadow, that meets every forward-moving grain at a 7.9° graze 100-300 m ahead of what it protects.
   Cost: 22-90 t on Vertex V1 (0.2-0.9 % of the 10.4 kt departure mass), 6-31 t as a flat aft annulus on the canon ship. It needs the
   braking attitude held within about 1° of the stream (canon attitude limit OD-015 is OPEN).
2. What no external shield can cover is the hardware visible through the open nozzle: the three loops, their struts and feeds, the
   shadow-shield burn face. With the skirt and 2 m local bumpers V1 still expects **~540 events per mission beyond the bumpers' capacity**
   (NOMINAL; 3.4 LOW; 17,300 HIGH), 390 of them in the final brake at home through the Kuiper belt (F5).
3. The same loops also take **3-62 times the published REBCO neutron-fluence tolerance** from the burn over the mission (both
   orientations; radiation.py). Shielding them locally (0.2-0.6 m LiH shoes, 180-260 t) would nearly double the hardware's share of the
   burn's sky. Both problems point to the same answer: **segmented, replaceable nozzle-loop sectors** (proposed T02-NEW-3), sized for a
   number of replacements per mission. That is the pathway to investigate next.
4. It does **not** close in the HIGH environment (17,300 events; a 287 m stand-off would be needed), and the canon Brow itself sees
   5,180 grains beyond its 2 m disruptor bow-first (NOMINAL). The uncertainty in the outer-solar-system large-grain population, not the
   physics, now decides survival.

Nothing here changed mission duration, speed, burn count or orientation. Owner questions are in section 12 (D-T02-1 to D-T02-4).

## 1. Exposure map, two orientations (question 1)

Frame: metres, +X bow. **Bow-first** (acceleration, coast): grains move -X relative to the ship. **Engine-first** (braking): grains move
+X. Area is the critical frontal area outside every silhouette that leads it (`exposure.py`, which imports `fdp1diag/protection.py`
read-only). Cones: 0°, 0.4° (the dust aberration envelope at 4,797 km/s: interstellar inflow 26 km/s gives at most 0.3°), 2.29° and 5°
(P11's diagnostic and prototype cones).

**P11 reproduced first:** engine maximum radius 112.55 m, 50 critical parts, 1,491.7 m² (MODEL; `exposure.json` `p11_reproduction`).

| Ship | Orientation | Protection | 0° | 0.4° | 2.29° | 5° |
| --- | --- | --- | --- | --- | --- | --- |
| V0 (FDP-1) | bow-first | canon 90 m shield | 1,492 | 1,509 | 1,853 | 2,523 |
| V1 / V2 | bow-first | canon 90 m shield | 1,492 | 1,509 | 1,853 | 2,354 |
| V0 | engine-first | engine-side shadow shield only | 12,196 | 12,260 | 12,524 | 12,701 |
| V1 / V2 | engine-first | engine-side shadow shield only | 12,175 | 12,282 | 12,572 | 12,735 |
| V0 | engine-first | with skirt T02-NEW-1 | 2,005 | 2,363 | 4,236 | 10,737 |
| V1 / V2 | engine-first | with skirt T02-NEW-1 | 2,022 | 2,281 | 4,060 | 9,194 |
| Canon ship | bow-first | canon 90 m shield | 0 | 0 | 0 | 0 |
| Canon ship | engine-first | reactor shadow shield only | 3,909 | 4,015 | 4,122 | 4,122 |
| Canon ship | engine-first | with aft annulus | 207 | 368 | 730 | 3,385 |

(m²; part counts in TABLES.md section 2, per-system breakdown in 2a, every exposed part in `exposure.json`.)

**The skirt works only with tight attitude control.** It cuts V1's braking exposure 5x at 0.4° but only 3x at 2.29° and barely at 5°,
because grains arriving off-axis slip past its rim onto the tanks. Braking burns must hold the stream within about 1° of the axis (the
natural aberration is ≤ 0.4°), which is a requirement on attitude control, not a new result for the drive. With the skirt, 681 m² of the
forward shield's back (V1) is still seen at 0.4°.

V1 engine-first at 0.4° by system: tanks 8,426 m², habitat rings 1,724, nozzle loops 1,069, struts 384, shadow shield and armour 318, feeds
185. **The back of the forward shield (6,312 m²) also faces the stream engine-first** in both ships. The canon ship has no critical part
outside its forward shield bow-first, even at 5° (consistent with MODEL "Forward defense"), but its tanks (1,923 m²), habitat rings
(1,724 m²) and four-nozzle drive (207 m²) lead in every braking burn.

## 2. Environment and fluence per leg (question 2)

`environment.py`; per-leg tables in TABLES.md section 3.

| Population | Model | Source, label |
| --- | --- | --- |
| Interplanetary dust inside ~30 AU | Grün et al. 1985 at 1 AU (constants give 9.6e-20 kg/m³), r^-1.3, cut at 30 AU | S-T02-GRUN-1985, TRANSCRIBED; radial law EXTRAPOLATION beyond 5 AU |
| Kuiper-belt dust | number density 3.5e-8 m⁻³ above 2.6e-15 kg near 42 AU; ramp from 10 AU, flat 42-60 AU, zero at 100 AU; Dohnanyi-type mass index | S-T02-SDC (New Horizons SDC, Bernardoni 2022; Doner 2024 fluxes above models to 55-60 AU), PUBLISHED (secondary); shape ASSUMPTION |
| Interstellar dust | Ulysses/Galileo power law 1e-18-1e-13 kg, mean 3e-16 kg, normalised to 2.1e-24 kg/m³ | S-ULYSSES-ISD, S-T02-KRUGER-2015 (PUBLISHED), S-T02-FRISCH-1999 (high case) |
| Interstellar large grains | NONE / EXTRAPOLATED (1e-10 m⁻²s⁻¹ above 3e-10 kg, Landgraf 2000 upper bound) / RADAR (2e-9, AMOR, disputed) | S-T02-LANDGRAF-2000, S-T02-AMOR |
| Gas | LIC H0 0.195, n_e 0.07, He 0.015 cm⁻³; solar wind 5 cm⁻³ at 1 AU as r^-2; heliopause 120 AU | S-T02-LIC (PUBLISHED), He ASSUMPTION, S-T02-VOYAGER-HP |

Cases: LOW / NOMINAL / HIGH bracket each population (Kuiper density x1/3 / x1 / x3, mass index 1.0 / 0.83 / 0.70, upper mass 1e-8 / 1e-6 /
1e-3 kg; interplanetary x0.5 / x1 / x2; interstellar tail NONE / EXTRAPOLATED / RADAR). NOMINAL_HILAT is NOMINAL with an out-of-ecliptic
path (Kuiper x0.1, interplanetary x0.3; ASSUMPTION, the heading is OPEN in canon).

**Mission path (not invented).** The canon target speed (0.016 c LOCKED) and the four-burn profile come from canon and the FDP-1 baseline;
the destination is OPEN in canon (`wf_route_v1.json` Kuiper events OPEN; Kuiper Belt 30-50 AU in `space_navigator.toml`). Ignition is
taken at 1 AU (ASSUMPTION). FDP-1/Vertex burns cover 964 / 751 / 585 / 456 AU (F1, F2, F3, F5; F4 coasts 675 AU), so its minimum stopping
point is **1,717 AU, beyond the heliopause**: it cannot stop at a Kuiper anchorage (D-T02-1). The canon ship (21.77 MN, mass ratio 1.284
per burn) burns 13.3 / 10.4 / 8.1 / 6.3 AU and is assumed to stop at 45 AU (ASSUMPTION).

NOMINAL grains above 10 kJ (about 1 µg at full speed) per m² of frontal area, per leg:

| Ship | Leg | Orientation | N(>10 kJ)/m² | N(>1 MJ)/m² | Dominant population |
| --- | --- | --- | --- | --- | --- |
| FDP-1/Vertex | F1 accelerate out | bow-first | 0.63 | 3.6e-4 | Kuiper belt at 300-1,500 km/s |
| | F2 brake at destination | engine-first | 0.040 | 2.5e-4 | interstellar tail |
| | F3 accelerate home | bow-first | 0.031 | 1.9e-4 | interstellar |
| | F4 coast home | bow-first | 0.078 | 4.9e-4 | interstellar at full speed |
| | **F5 brake at home** | **engine-first** | **1.14** | **5.1e-3** | **Kuiper belt at 1,200-2,200 km/s** |
| Canon ship | C1 / C2 / C4 / C5 | bow-first | 0.77 / 1.68 / 0.53 / 2.54 | up to 0.036 | zodiacal and Kuiper dust |
| | **C3 brake at anchorage** | **engine-first** | **0.64** | **0.011** | **Kuiper belt** |
| | C6 brake at home | engine-first | 0.70 | 4.2e-3 | zodiacal cloud |

LOW and HIGH are roughly x0.05-0.1 and x10-20 of NOMINAL for the large grains; the large-grain end is the least constrained number in this
study (no instrument has measured Kuiper-belt grains above ~1e-11 kg).

## 3. Impact physics and regimes (question 3)

`impacts.py`. At 0.016 c a grain carries 1.15e10 J/kg: 11.5 kJ per µg, 11.5 MJ per mg. That is 48 times the top speed of dust
accelerators (~100 km/s, S-T02-HIGGINS-2018) and 2,300 times their specific energy; Whipple ballistic-limit equations (S-WHIPPLE-BLE,
7-10 km/s) are **not used**.

| Regime | Grain | What happens | Label |
| --- | --- | --- | --- |
| Atomic | d < ~2 µm (m < ~1e-14 kg) | each atom arrives with ~0.3-1 MeV/u: a cluster-ion burst, µm-deep heating, explosive evaporation (Hoang et al. 2017) | PUBLISHED (S-HOANG-2017) |
| Hydrodynamic point explosion | larger | the grain and the struck material vaporise and ionise; damage follows deposited energy: crater volume V = kE, k = 1e-11 / 3e-11 / 1e-10 m³/J; perforated thickness 1.5 x crater depth | EXTRAPOLATION |
| Grazing | incidence < 0.5° (radiator planes) | normal velocity 4,797 x sin(0.4°) = 33 km/s, back inside the dust-accelerator range: a gouge, not a crater | EXTRAPOLATION (oblique scaling) |

Failure energies (NOMINAL k): an unprotected 5 mm wall is perforated above 2.6 kJ (~0.2 µg). Failure modes per component: wall
perforation and spall (tanks, hull, rings), radiator puncture and fluid loss (wings, blades), and for the nozzle loops a quench from local
heating or conductor cut (UNKNOWN threshold; any hydrodynamic hit on a conductor is assumed to fail that sector). Expected events over the
mission (TABLES.md section 4):

| Configuration | Case | Bare 5 mm wall | Beyond 2 m bumper | Beyond 10 m | Stand-off for < 0.1 events |
| --- | --- | --- | --- | --- | --- |
| V1 as drawn | NOMINAL | 49,200 | 2,290 | 11.7 | 32 m |
| V1 with skirt | LOW / NOMINAL / HIGH | 368 / 12,000 / 215,000 | 3.4 / 540 / 17,300 | 0.05 / 2.7 / 1,720 | 8 / 25 / 287 m |
| V1 with skirt | NOMINAL_HILAT | 2,420 | 89 | 1.3 | 25 m |
| Canon as drawn | NOMINAL | 17,200 | 730 | 12.6 | 52 m |
| Canon with aft annulus | LOW / NOMINAL / HIGH | 451 / 1,570 / 12,100 | 14 / 67 / 970 | 0.3 / 1.2 / 97 | 16 / 21 / 332 m |

**Uniform erosion is not the threat:** 0.04-35 µm per leg across the k band (NOMINAL environment; TABLES.md section 7). **The threat is the
rare large grain.**

Canon Brow (6,362 m², bow-first, NOMINAL): 5,180 grains beyond what its 2 m disruptor defeats, 489 above 1 MJ (each a ~3.6 cm deep crater in
monolithic metal). On the FDP-1 path (which spends less time in the Kuiper belt at speed) the Brow sees 595 and 6.7. This bears on canon
OD-014 (shield stack and mass OPEN).

## 4. Sacrificial multilayer shielding (question 4, VTX-08A)

At these speeds a bumper does not stop a grain; it converts it into an expanding plasma and the wall behind survives the spread-out
fluence. Cloud model (EXTRAPOLATION): the debris cone (half-angle α 15-45°) spreads energy E over π(S tan α)²; a wall survives a fluence
F_allow (3e3-3e4 J/m², nominal 1e4) with a share g = 0.5 of the energy reaching it. Defeated energy grows with the square of stand-off S:

| Stand-off | Defeats (nominal, band) | Largest grain at cruise |
| --- | --- | --- |
| 1 m | 21 kJ (1.4-190 kJ) | 1.8 µg |
| 2 m | 84 kJ (5-750 kJ) | 7.3 µg |
| 10 m | 2.1 MJ (0.14-19 MJ) | 0.18 mg |
| 20 m | 8.4 MJ | 0.73 mg |
| 100 m | 210 MJ (13-1,900 MJ) | 18 mg |

- **Layer count and areal density:** the first layer only needs to be thick enough to fully vaporise the grain (a few grain diameters:
  0.1-1 mm for the hazardous grains), so 0.5-2 kg/m² per layer; a second layer at the same stand-off catches the expanding plasma's
  hottest core. Two layers is the working assumption; the band above is wider than the layer-count effect.
- **Re-coverage:** each hit leaves a hole of order the debris-cone footprint in the first layer (cm to dm). NOMINAL V1 with the skirt
  takes ~12,000 hits above 2.6 kJ per mission on 2,281 + 6,200 m²: under 1 % of the area holed, if hits are uniform. Replacement between
  burns (by EVA drone) is a maintenance task, not a mass driver.
- **Mass by component (V1 with the skirt):** skirt 22-90 t; local bumpers on the bore-visible hardware (~2,300 m² frontal, ~2 m
  stand-off, 1-2 kg/m² x 2 layers) about 5-10 t plus supports (EXTRAPOLATION); guard rings for loops 2 and 3 bow-first (section 7) about
  0.8 m x 2π(64.7+112) m x 2 kg/m² ≈ 2 t each layer. **Mass is small; the burn's sky and the stand-off are what limit.**

## 5. Detection and active mitigation (question 5, VTX-08B)

A 1 J, 1.064 µm lidar pulse with a 1 m² receiver sees a 1 mm grain at ~10-100 km. At 4,797 km/s that is **0.2-21 ms of warning**
(`impacts.json` `detection`). To vaporise a 1 mm grain at 10 km takes ~0.13 MJ delivered in milliseconds onto a target 1 mm wide; pushing
it 112 m sideways in that time needs ~58 km/s of lateral velocity. Searching a 112 m radius at 100 km takes ~2.4e6 pulses per second.
**Verdict: no active clearing is feasible in the time available; the only working "clearing" is a physical screen far enough ahead.**
The Dust Lance and diversion field of the canon bow remain canon display elements; nothing here credits them.

## 6. Electromagnetic control (question 6, VTX-08C)

- **Grains:** D-12 holds. At 0.6 C/kg and 1 mT the Larmor radius is ~8e9 m. No field deflects a grain.
- **Ions:** a 120 keV proton has a 50 m Larmor radius at 1 mT; a dipole bubble of 100 m at 1 mT stores ~1.7 MJ. The nozzle field does
  deflect solar-wind and LIC ions during braking at no extra cost, but **~75 % of the LIC gas is neutral H** and passes straight through.
- **What gas does:** LIC power flux 0.03 W/m² (negligible against radiator loads); H fluence ~1e15/cm² per leg at 120 keV, below the
  1e17-1e18 H/cm² blistering range (S-T02-BLISTER, EXTRAPOLATION); sputtering well under 1 nm per leg. Gas needs no protection beyond
  what dust already demands. **Recommendation: no dedicated field.**

## 7. Geometry protection and the engine-side shield (question 7, VTX-08D)

**Shadow-cone skirt (T02-NEW-1, CONCEPTUAL_ILLUSTRATION).** A conical sheet with its apex at the burn point (x -227.54, on the axis) and
its half-angle equal to the hardware cone (V1/V2 7.94°, V0 9.60°), from the shadow-shield rim (V1: x -175.8, r 7.2) to r 45 m at x +95.1.

| Generation | Half-angle | Slant | Surface | Projected | Mass at 0.5 / 1 / 2 kg/m² |
| --- | --- | --- | --- | --- | --- |
| V0 | 9.60° | 219 m | 36,800 m² | 6,140 m² | 18 / 37 / 74 t |
| V1 / V2 | 7.94° | 274 m | 44,900 m² | 6,200 m² | 22 / 45 / 90 t |
| Canon (flat annulus, x -98 m, r 5.7-45 m) | - | - | 6,260 m² | 6,260 m² | 6 / 13 / 31 t (at 1 / 2 / 5 kg/m²) |

- The sheet contains the burn's rays (zero solid angle for a point source) and lies in the shadow shield's umbra, so it adds no hot
  load and no plume strike; finite-source size and scatter around the shield rim are UNKNOWN (T04 gives the hot-spot size; a transport
  code gives the rim scatter). It must sit just inside the cone with a penumbra margin.
- Every grain that would reach the tanks, rings or forward shield in engine-first crosses the sheet at a 7.9° graze (track length 7.2 x
  the sheet thickness), 100-300 m ahead of the protected hardware: the stand-off the bumper physics needs.
- The canon form is simpler: the canon reactor shadow shield casts a 70.7° shadow, so a flat annulus 16.8 m forward of the core covers
  r 5.7-45 m inside it.

**What cannot be shadowed.** Moving or folding the loops into the hardware cone breaks the nozzle (their radius sets the field geometry,
T03). Any shield upstream of the bore-visible hardware sits in the exhaust. The loops' only options are local bumpers (≤ ~2 m stand-off on
their burn-facing faces, which adds burn solid angle: analytic estimates +0.001-0.004 hardware share) and damage tolerance.

**Bow-first, Vertex loops 2 and 3** (outside the 45 m shield silhouette): forward guard rings at the loop radius, 20-25 m ahead (NOMINAL;
4 m LOW; 127 m HIGH), ~0.8 m wide, or the P11 option of a shield extension to r 112.5 m.

## 8. Plume interaction (question 8, a hypothesis, not a credit)

Plume column along the axis ≈ ṁ / (v_e π tan θ r_exit): 6e-11 kg/m² for V0 (ṁ 0.073 kg/s, 112 m exit), 1.9e-8 kg/m² for the canon drive
(1.134 kg/s, 5.6 m exit). Deposited energy per grain reaches vaporisation only below ~1e-15 kg (V0) or ~4e-13 kg (canon), and the
momentum transferred is below 1e-6 of the grain's. **The vapour keeps the grain's momentum and energy; the hazardous fluence (> 1 µg) is
reduced by far less than 1 %. No credit.** What would refute it: a plume many orders of magnitude denser than the burn's mass flow allows.

## 9. Radiators (question 9)

- **Edge-on in both orientations.** Planar wings and blades whose planes contain the ship axis present only planform x sin(cone) plus the
  leading edge. At 0.4°: V0 13,100 m², V1 2,260 m², V2 1,160 m² frontal bow-first (TABLES.md section 2b). For T01's planning envelope
  (split advanced at driver efficiency 0.30, ~0.59 km² planform, tip ~1.1 km) that scales to about 3,700 m² (EXTRAPOLATION).
- Planform impacts are grazing (~33 km/s normal component): within the lab-validated range, so their damage can be measured (section 13).
  Leading edges take head-on hits and need bumpers (edge thickness UNKNOWN; 1 cm of edge adds ~1 % of the edge length in m²).
- **The canon blades** are covered bow-first and fully exposed engine-first; with the aft annulus 3,226 m² of planform near the roots
  still stays outside it.
- **Retractable and sacrificial arrangements:** retracting warm wings during braking only helps if the warm heat can wait, which the
  driver loss (75-95 % of the warm heat, T01) does not allow during a burn. Not recommended. Sacrificial leading-edge strips are.
- **Droplet sheets (VTX-07B)** that exist only during burns lose ~1 kg of fluid per burn to small dust (EXTRAPOLATION): negligible. A
  large grain crossing a sheet is a harmless puncture of a liquid. Droplet sheets are the most dust-tolerant radiator in the record.

## 10. Radiation exposure (question 10)

`radiation.py`. **The burn is fixed in the ship frame, so every burn-radiation number is identical in bow-first and engine-first flight**
(checked: same source and receiver geometry, `orientation_check.identical = true`).

- **Crew:** the FDP-1 shadow shield (crew cone 5.3°, 3.59 m LiH, 10.4 neutron decades to 10 mSv/y, 430 t) already sizes the crew dose
  (MODEL, `lab/variants/fdp1` shielding record; first order: no build-up, no (n,γ), no rim scatter). Orientation does not change it.
  Galactic cosmic rays are almost isotropic (the ship's motion adds a ~7.5 % Compton-Getting anisotropy) and remain a canon habitat matter.
- **Gas stream secondaries:** 120 keV protons and 477 keV helium open no (p,n) or (α,n) channel on W, Li, C or Al; bremsstrahlung is
  below 1e-11 W/m². Negligible in both orientations.
- **Engine hardware: a new negative result.** The three nozzle loops sit in the burn's sky by design. With T04's neutron escape share
  (5.5e-6, mostly 2.45 MeV) and the Atlas fusion power:

| Generation | Loop | Distance from burn | Fast-neutron fluence per mission | x REBCO tolerance (3e18 n/cm²) | LiH shoe to reach it | Shoe mass |
| --- | --- | --- | --- | --- | --- | --- |
| V0 | 1 / 2 / 3 | 43.2 / 64.8 / 129.6 m | 1.9e20 / 8.3e19 / 2.1e19 n/cm² | 62 / 28 / 7 | 0.62 / 0.50 / 0.29 m | 68 / 95 / 96 t |
| V1 | 1 / 2 / 3 | 43.1 / 64.7 / 129.4 m | 9.4e19 / 4.2e19 / 1.0e19 n/cm² | 31 / 14 / 3.5 | 0.52 / 0.39 / 0.19 m | 57 / 75 / 61 t |
| V2 | 1 / 2 / 3 | 43.1 / 64.7 / 129.4 m | 8.3e19 / 3.7e19 / 9.3e18 n/cm² | 28 / 12 / 3.1 | 0.50 / 0.38 / 0.17 m | 55 / 72 / 56 t |

  The tolerance is the reactor-irradiation range (Fischer et al. 2018, Prokopec et al. 2015: Ic and n-value degrade from ~1-4e22 m⁻²;
  S-T02-REBCO-N, SECONDARY_VERIFIED); an in-situ 14 MeV study reported degradation starting orders of magnitude lower (PESSIMISTIC case,
  up to 3,100x for V1 loop 1). The shoes (0.6 m chord, ASSUMPTION) add **0.0127 to the burn's hardware solid-angle share**, against the
  whole V1 ship's 0.0168, and 1.3 GW of X-ray heat (V1) to the hot loop. Shielding the loops in place therefore roughly doubles the
  burn's view of hardware; the alternative is to replace loop sectors ~3-31 times per mission (V1) or to find a conductor that tolerates
  ~1e20 n/cm² (none known: a Level C need, T02-NEW-4). X-rays per pulse at loop 1 are 4e4 J/m² by design (T04's stand-off), unchanged.

## 11. Risk-ranked components

Ranked by expected failures per mission in NOMINAL with the recommended protection, then by consequence.

| Rank | Component | Orientation, leg | Why | With protection |
| --- | --- | --- | --- | --- |
| 1 | Nozzle loops 1-3 (V0-V2) | engine-first F5, F2; bow-first F1 (loops 2-3) | in the bore, cannot be shadowed; neutron fluence 3-62x REBCO tolerance | ~540 grain events beyond 2 m bumpers plus the dose: needs replaceable sectors |
| 2 | Canon Brow and forward shield face | bow-first C2, C5 (canon); F1 (FDP-1) | full-speed Kuiper crossing | 5,180 beyond the 2 m disruptor (canon); OD-014 OPEN |
| 3 | Shadow-shield burn face, struts, feeds, diagnostics | engine-first | in the bore | local bumpers; part of the 540 |
| 4 | Tanks | engine-first | 8,426 m² (V1), 1,923 m² (canon) | covered by the skirt / annulus |
| 5 | Habitat rings | engine-first | 1,724 m², crew | covered by the skirt / annulus |
| 6 | Back of the forward shield | engine-first | 6,312 m² | covered by the skirt / annulus |
| 7 | Radiator leading edges and canon blade roots | both | head-on edge hits | sacrificial edge strips; edge thickness UNKNOWN |
| 8 | Radiator planforms | both | grazing at 0.4° | lab-testable gouges |
| 9 | Everything, uniform erosion and gas | both | 0.04-35 µm, ~1e15 H/cm² | none needed |

## 12. Owner questions (proposed decisions, not made)

- **D-T02-1 (mission, canon conflict):** FDP-1/Vertex's four-burn profile needs 1,717 AU to stop, beyond the heliopause; the canon ship's
  route names a Kuiper anchorage. Which destination does the FDP-1/Vertex line assume? (This study used FDP-1's own distances.)
- **D-T02-2 (D-06 options, numbers):** (a) skirt / annulus plus local bumpers plus replaceable loop sectors (22-90 t Vertex, 6-31 t canon,
  ~540 / ~67 residual events NOMINAL); (b) as (a) plus an out-of-ecliptic heading (residual ~89 Vertex, ~12 canon; a canon route choice);
  (c) a braking-orientation or speed change (forbidden to this thread; owner only); (d) accept and study (no mass, ~2,290 / 730 events).
  Recommendation: (a), with (b) studied when the canon heading is chosen.
- **D-T02-3 (out-of-ecliptic heading):** is the departure heading free? A high-latitude path cuts the Kuiper-belt dose ~10x (ASSUMPTION).
- **D-T02-4 (nozzle conductor):** accept periodic loop-sector replacement (mass and EVA schedule to be sized by T03/T05), or require a
  conductor tolerating ~1e20 n/cm² (a proposed Level C breakthrough, T02-NEW-4)?

## 13. Unresolved physical questions

1. Damage from 0.1-10 mg grains at 1,000-5,000 km/s: no experiment exists above ~100 km/s; the crater coefficient band (x10) dominates.
2. The number of Kuiper-belt grains above 1e-9 kg: no measurement; the LOW-HIGH spread is x5,000 in events.
3. Debris-cloud spread and wall response at 1e10 J/kg (the bumper model's α and F_allow).
4. Quench and cut thresholds of a REBCO loop under a µg-class hit; REBCO under 2.45 MeV neutrons in situ at 20-50 K.
5. Finite burn-source size and rim scatter onto the skirt (needs T04's hot-spot size and a transport code).
6. Grazing-impact damage on radiator planforms at 0.4° (33 km/s normal): **lab-testable now**.

## 14. Requirements for the Blender thread (T05; nothing drawn without D-10)

- Skirt envelope V1/V2: cone apex (-227.54, 0, 0), half-angle 7.94° (V0 9.60°), r 7.2-45 m (V0 8.5-45), x -175.8 to +95.1 m. Keep-out:
  nothing pierces the sheet except along burn rays. Canon: flat annulus x -98 m, r 5.7-45 m. CONCEPTUAL_ILLUSTRATION.
- Guard rings (bow-first) 20-25 m forward of loops 2 and 3 at their radii (64.7 m, 112.0 m), ~0.8 m wide; local bumpers ≤ 2 m on the
  burn-facing and stream-facing faces of every loop, strut and feed outside r 45 m. PARAMETRIC_PLACEHOLDER.
- Loop sectors drawn as separable segments (six per loop in the FDP-1 geometry) with a replacement path. PARAMETRIC_PLACEHOLDER.
- Attitude requirement for braking: stream within ~1° of the axis for the skirt to work (5x at 0.4°, 3x at 2.29°); input to OD-015.
- Exposure overlays: `exposure.json` `cases.<ship>.<orientation>.<protection>.<cone>.parts`.

## 15. Limitations

Geometric coverage uses the P11 sampling code (first-hit silhouettes, no ejecta between parts). Grains travel in straight lines on the
axis within the cone (no gravitational focusing, no radiation-pressure size cut). Environment shapes beyond measured ranges are
ASSUMPTION. Impact damage is energy scaling, not hydrocode. Radiation is first order. Mission legs are radial with ignition at 1 AU. The
skirt's structure, deployment and thermal state are not designed.
