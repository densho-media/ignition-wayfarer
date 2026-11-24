# vertex-thermal: supermirrors, cooling mesh and the heat ledger

Owner brief 2026-11-23 14:18Z ("Supermirror Integration, Cooling Mesh & Interactive Thermal Engineering"), continued by the brief of
2026-11-24 06:43Z ("Vertex Drive: Next Development & Production Release"). Research, not canon; deployed as part of the Fusion Ignition page.

**Function.** Find where supermirrors help the compact Vertex engine (C1/C4 geometry, silhouette kept), draw a hot lithium circuit and a
separate cryogenic circuit, and book every watt of the coupled pulse per component: incident, reflected, transmitted, absorbed,
secondary, final; generated, removed, radiated, pumped or refrigerated, deficits.

**Fixed constraints.** The coupled pulse of the Fusion Ignition ledger (8.93 TW fusion per engine: 7.57 TW X-rays, 256 GW neutrons,
1.01 TW charged hits, 455 GW jet; radiator budget 2.70 GW; 5,697 Hz); the R2-B X-ray spectrum; the drawn engine parts (`vertex_engine`).
Earlier results kept: supermirrors give limited benefit for hard X-rays and none for MeV neutrons (MPN, RON, AMPN, compact).

**Files.** `thermal.py` (model, about 11 s, writes `results/thermal.json`), `problems.py` (ENG-040..056, `PROBLEMS.md`),
`blender_thermal.py` (`REVIEW_THERMAL.blend` and the renders in the project files), `export.py` (copies the result into
`lab/studies/fusion-ignition/imports/thermal_<commit>.json`, which the Fusion Ignition page reads as its Heat stage).

**Method.** A sky trace in 0.02 deg polar bands from the burn point finds the nearest drawn part for each direction (tori with arc fill,
the shield face, thin members as azimuthal fill with occlusion) and its grazing angle. Geometry sky 0.631 against the ledger's pickup
0.546 (x1.16, ENG-056). Mirror reflectance from a Pt/W multilayer model with Debye-Waller roughness (0.5 nm).

## Benefit versus mass (per engine)

| Strategy | Acts on | Effect | Added mass | Verdict |
| --- | --- | --- | --- | --- |
| A coil and shield coatings | grazing X-rays, far-IR | returns 1.5e-5 of the X-rays that strike (46 MW); faces meet the rays at about 50-58 deg | 0.004 t | no benefit (coupled) |
| B edge-on blades and cones | the cage, seats, struts and lines | members' heat falls to 8.9 % (-1.57 TW) | 61 t | helps most, far from enough |
| C layered blankets | coils | moves 1.79 TW into lithium; 20 K load 25.2 -> 1.33 GW | 2,147 t | moves heat, adds mass |
| D grazing nozzle liners | the exhaust's X-rays | Pt critical angle at 1 keV is tens of mrad; the turn needed is 88-257 mrad | 0 t | no benefit (hard spectrum) |
| B+C | | | 2,208 t | not closed: 1,575x the radiator budget remains |

## Hot and cryogenic circuits

- Hot lithium (1500 -> 1800 K): face flux 96-1,250x the 20 MW/m2 limit; channel speed 7-28 km/s needed; MHD loss 2.2-48 MPa bare,
  0.09-2 MPa with SiC inserts. Drawn lines carry 0.22 GW (27,013x short); one pipe for all the heat would be r 18 m. Radiator
  1.09e7 m2 (404x the ship, about 109 kt); pumping 12.8 GW. A Brayton loop (eta 0.35) gives 2.04 TW electric but grows the radiator x10.4.
- Cryo (20 K): refrigeration 7.46 TW at 297 W/W; 80 K screens about 7 kW; quench 9.7 GJ over 10 s.
- Pulsed surface jump at the hottest point (3.39 MJ/m2 per pulse): W, Mo and SiC fail; carbon (CFC) is best and still 766 K over;
  Be and LiH melt below 1800 K. 2.1e7 cycles per hour.

## Decisions (PROTOTYPE)

All parameters in `thermal.py` `P` and `STACK` are PROTOTYPE: 20 MW/m2 face limit, lithium 1500/1800 K, flow-channel insert
conductivities, armour and blanket thicknesses, radiator 10 kg/m2, edge 30 mm, B mass factor 1.3. Nothing writes to canon.

## Owner decisions 2026-11-24

- Q-TH-1: B adopted as the working direction. Detail added: alignment budget 0.126 mrad (target miss 0.111, mount 0.05, 1 K bow 0.033,
  vibration 0.001), allowed face-to-face difference 3.3 K, first mode 35 Hz against 5,697 Hz pulses, edge strip 7.4 GW/m2 (372x the face
  limit) and +1,102 K per pulse (63 % of CFC strength), root actuators 6 t (ENG-057, ENG-058).
- Q-TH-2: the thin blanket (248 t, no W/B4C or LiH) is the optional configuration: it moves 1.79 TW into lithium, but the neutrons pass,
  so the 20 K load stays 25.2 GW (ENG-059). The full 2,147 t blanket is ARCHIVED with its results (`strategies.C`).
- Q-TH-3: the source study is `../vertex-source`. B + thin blanket (308.9 t) leave the engine 1,575x its radiator share.
- Added a warm NaK circuit (650 -> 850 K, 62.1 GW, radiator 2.47 km2, ENG-060) and the drawn network: hot supply and return rings,
  longeron feeders, jacket branches, warm ring and hoops, cryogenic headers and per-coil lines, mirror substrates, liner panels, service
  rail, exchange ports, couplings and lift lugs (395 primitives, 114 flow paths).
