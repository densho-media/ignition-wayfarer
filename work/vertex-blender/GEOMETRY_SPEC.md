# Vertex geometry specification (T05 Stage A)

NON-CANON. Frame: metres, +X bow, +Z dorsal, azimuth measured from +Y toward +Z (FDP-1 `geometry.pol`). Values are from a fresh FDP-1
solve with each generation's overrides (`screen.json`, `a1c8246`) and agree with `results/convergence.json`. Stage B reads them from
the solve, never from this page. Status: **ES** ENGINEERING_SUPPORTED, **PP** PARAMETRIC_PLACEHOLDER, **CI** CONCEPTUAL_ILLUSTRATION
(overlay only), **PR** a PROTOTYPE size chosen by T05 judgment where no thread gives one. "May change" names the thread whose result
replaces the number.

## 1. Components by generation

| Component (VTX) | V4 (principal) | V0 (historical) | V5 (ghost) | Source | Status | May change |
| --- | --- | --- | --- | --- | --- | --- |
| Burn point, X-ray stand-off sphere (01, 06) | X −249.1, R_s 64.7 | X −227.5, R_s 43.2 | X −227.4, R_s 43.0 | layout.x_burn, R_s | ES | T04 (density) |
| Density band on stand-off (01E) | 43-65 m (1,000-3,000 g/cm³ scan) | — | — | `V4_density_scan` | ES (ghost spheres) | T04 |
| Shadow shield (06A) | X −184.4 to −180.75, r 7.23; 514 t | r 8.30; 430 t | r 7.00; 359 t | shield.* | ES | T04, T03 |
| Hardware / crew cone (06) | 5.50° / 4.98° | 9.60° / 5.31° | 7.94° / 5.31° | shield half angles | ES (overlay) | T03 (coils ×2.4-3.0 solid angle) |
| Loops L1-L3 (02, 02B) | r 56.0 / 97.0 / 168.1 at X −216.8 / −249.1 / −346.2; envelope 0.72 | r 37.4 / 64.8 / 112.2; 0.21 | r 37.3 / 64.5 / 111.8; 0.58 | nozzle.loops | ES position, PP envelope | T03 |
| Closure coils C1, C2 (03D) | C1 X −188.3 r 22.1, C2 X −199.6 r 41.6; envelope r 3.0-4.8 | C1 −187.0 / 14.8, C2 −194.5 / 27.8; 2.0-3.2 | as V0 | T03 C_W15 polar 20°/40° on R_s | PP | T03, D-21 |
| Loop struts (02D) | 6 per loop, radius 0.43 / 0.35 / 0.42 m | 0.28 / 0.24 / 0.29 m | 0.28 / 0.24 / 0.28 m | structure.struts | PP (unbooked GN coil loads) | T03 |
| Trim sectors and clock (03A) | 4 per loop, joints clocked 45° loop to loop | same | — | fdp1.toml trim_sectors | PP | T03 |
| Replaceable sectors (03E) | 12 mechanical splits per loop at 30°, aligned to the trim joints; exchange units of 60° (T02) or 90° (one trim sector) | same | — | T02 E; T05 reconciliation (ISS-007) | PP | T02, T03 |
| Lattice carriers, armour shoes (02A, 06B) | outer 70° band; W/B4C shoe on burn face | same | — | FDP-1 geometry | PP | T03 |
| Guard rings (08F) | 0.8 m wide, 20-25 m forward of L2 and L3 at r 97.0 / 168.1 | r 64.8 / 112.2 | — | T02 E, scaled to loop radii | PP | T02 |
| Local bumpers (08A, 08F) | ≤ 2 m stand-off on every loop, strut, feed outside r 45 | same | — | T02 E | PP | T02 |
| Skirt (08E) | cone apex X −249.1, half-angle 5.50°, r 7.2-45 m, X −184.4 to +218 (slotted at the wing planes) | apex −227.5, 9.60° | — | T02 E, re-apexed to V4 (ISS-004) | CI (hardware drawn translucent) | T02 |
| Equipment module (01C) | X −180.75 to −144.75, r 6.5 | same | same | layout | PP | T01, T04 |
| Target launcher and sabot catcher (01H) | bore axis, muzzle at the shield face; barrel PR 20 m (UNKNOWN 10-20 m); ≥ 13.4 km/s for one target in flight (68.4 m path × 196 Hz) | 9.9 km/s, 46.8 m | 9.4 km/s, 46.6 m | injection.path × pulse rate; T01 | PP | T01, T04 |
| Injection path ghost (01H) | 68.4 m; 82.7 m at a 12 km/s launcher | 46.8 m | 46.6 m | `V4_launcher_sweep` | PP | T01 |
| Fast-ignitor beam line (01G) | PR 1 m tube beside the bore axis, shield face to module | — | — | T04 (volume UNKNOWN) | PP | T04 |
| Tritium store (01G) | PR 2 m sphere in the module, 43-144 kg | — | — | T04 | CI | T04 |
| Driver galleries (01B) | 3 at az 90 / 225 / 315, r 4.5, X −144.75 to +81.9 | r 12 | r 4.5 | drivers.* | PP (mass per W unresolved) | T01 |
| Beam lines, final focus, ports (01B) | 9 beams through the shield | same | same | FDP-1 geometry | PP | T01 |
| Pulse storage, power conditioning (02C) | module banks; 1,402 t | 151 t | — | drivers.storage_mass | PP | T01 |
| Warm wings (07, 07D, 07E) | W2 az 0/180, X −178.75 to +88.0, 628 K field r 847-10,128 m (4.95 km²) | 600 K, r 117-3,573 (1.84 km²) | 628 K, r 375-3,267 (1.54 km²) | thermal.layouts.W2 | PP | T01 |
| Warm circuit bands (07E) | 1,000 / 740 / 700 / 640 / 550 K bands outward, areas from T01 `ledger.json` | — | same split | T01 | PP | T01 |
| Hot band (07F) | 1,800 K, r 10-847 (0.462 km²); graded alternative aft of X 48.9 m, r 10-991 | r 10-117 | r 10-375 | thermal.layouts.W2.hot_band | PP | T01 |
| Wing bracket ghosts | tip 6.7 km (670 K), 3.4 km (driver 0.45), 14.5 km (12 km/s launcher) | — | — | V4 bands in convergence.json | PP (outline) | T01 |
| Droplet generator, collector, sheet (07B) | bar on the forward edge, collector on the aft edge, sheet as overlay | — | — | T01 §5 | CI | T01 |
| Low loop panels | 4,027 m² of 300 K panels on the module | 1,794 m² | 1,661 m² | thermal.low_loop | PP | T01 |
| Propellant tanks (T-B) | 110 vessels r 6.75 in 9 bays; 275.4 m stretch ahead of the farm; bow assembly +275.4 m | 49, 122.4 m | 46, 122.4 m | tanks.options.T-B | ES count and volume, PP layout | T00 |
| Tank alternative T-A | the same 9 bays aft of the hull, drive moves aft | 4 bays | — | tanks.options.T-A | PP (outline) | T00 |
| Idle H2 vessels (04B) | hidden in V4 (owner), kept in canon | kept | hidden | `keep_idle_hydrogen_vessels` | ES | owner (D-04) |
| Diagnostics, trackers (05, 05A, 05B) | loop-1 ring, shield-rim ports, module racks | same | — | FDP-1 geometry | PP | T04 |
| Enriched shield layers (04D) | inside the shield | same | — | — | PP (no separate object; property on the shield) | T04 |
| Maintenance (rails, hatches, crawler) | module hatches, shield-face exchange rail, strut crawler, gallery walkway, sector exchange path | same | — | FDP-1 geometry | PP | T05 |

Whole V4 extent: X −346.2 m (L3) to +420.1 m (bow after the stretch), 766 m; span 20,255 m. V0: X −292.3 to +267.1 m, span 7,146 m.
V5: X −291.9 to +267.1 m, span 6,534 m.

## 2. Interfaces (owner point 7)

| Interface | Finding at V4 | Requirement for Stage B | Issue |
| --- | --- | --- | --- |
| Closure coils ↔ shield, wing, struts | C1 sits 3.9 m aft of the shield aft face and crosses the wing plane at r 22.1, 9.6 m aft of the 1,800 K band edge (91 kW/m² on its envelope). GN hoop and inter-coil loads have no drawn load path. | Draw C1/C2 with their T03 envelopes; draw coil-to-shield-frame struts as unsized PP; measure the C1-wing gap; draw the graded wing alternative 20 m clear of C1 | ISS-002, ISS-003 |
| Sacrificial dust shielding ↔ wings, docks | A V4 skirt on the 5.5° cone reaches r 45 m only at X +218 m. It meets the wing roots (needs two slots along the wing planes, which are burn rays, so allowed) and passes r 36.6 m at the docks (X 131.65 m): the primary and service docking corridors would pierce it. | Draw the skirt in three extents: to r 45 (slotted, with dock apertures), ending aft of ring A, and the guard-ring/local-bumper alternative with no skirt | ISS-004 |
| Replaceable sectors ↔ trim sectors | T02 says six per loop, T03 keeps four trim sectors; FDP-1 has four sectors and six struts. | 12 split lines per loop at 30° aligned to each loop's trim joints; exchange units of 2 or 3 segments; draw the exchange path from L1 along a strut to the shield-face rail | ISS-007 |
| Target launcher ↔ shield, ignitor | One target in flight needs ≥ 13.4 km/s at 196 Hz over 68.4 m; the barrel and catcher sit on the bore axis behind the LiH plug, beside the ignitor line; recoil and sabot handling UNKNOWN. | PR barrel 20 m, catcher behind the shield face, both labelled UNKNOWN; reserve a 2 m bore corridor | ISS-008 |
| Docking ↔ wings, skirt, stretch | Docks X 131.65 m (az 195° and 315°) lie 43.7 m forward of the wing's forward edge and 15°/45° from the wing planes; V4's T-B stretch keeps them in place and moves the bow 275.4 m forward. The tandem wing option (R2) starts 5 m ahead of the farm front to keep the docks clear. | Docking clearance camera with the visiting-vehicle corridor; measure the corridor against the wing and skirt | ISS-004 |
| Habitat rings ↔ hot band | 1,800 K band edge 7.2 m from ring A: 173 kW/m² on its aft face (canon blades: about 65 kW/m² by the same method). | Graded alternative (hot band aft of X 48.9 m): 57 kW/m² | ISS-001 |
| Maintenance | No access to loops, coils or wings while pulsing (shadow cone only). Sector exchange and armour renewal between burns; wing generator/collector modules from the root. | Maintenance camera with a 1.75 m human figure at the shield-face rail and at a wing root crossing | — |

## 3. Atlas record coverage (39 records with geometry status other than NONE)

Drawn as hardware (ES/PP): VTX-01, 01B, 01C, 01G, 01H, 02, 02A, 02B, 02C, 02D, 03A, 03D, 03E, 04D (property on the shield), 05, 05A,
05B, 06, 06A, 06B, 07, 07A (circuit bands), 07D, 07E, 07F, 08A, 08F; VTX-04B (canon vessels, hidden in V4).
Drawn as labelled overlays (CI): VTX-03 (sector clock, not a helix), 03C (counter-helicity arrow pair, VISUALIZATION), 07B (droplet
sheet), 08 (bumper set index), 08D and 08E (braking shadow and skirt), 01G tritium store.
Deferred, with reason: VTX-01A (target-formation coil: "not supportable yet"), 03B (non-planar shaping coils: "not supportable"),
04 and 04C (vapour curtains: no envelope), 08B (engine-side sensor heads: small; one marker on the shield rim if time allows).
The eight NONE records (01D, 01E, 01F, 01I, 03F, 04A, 07C, 08C) have no geometry; 01E appears only as the density ghost spheres.
