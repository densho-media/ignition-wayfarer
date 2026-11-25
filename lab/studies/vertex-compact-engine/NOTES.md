<!-- lab entry -->
| Lab entry | |
| --- | --- |
| Kind | Study |
| Status | PARKED (phase closed by the owner 2026-11-25: milestone accepted; research behind the live Fusion Engineering page; not canon) |
| Question | Can the compact Vertex engine reject its heat and reach the mission exhaust speed, and which nozzle, protection, cooling and source choices move it closest? |
| Model base | main d016d5d; Vertex engine as built (`vertex_engine`), R2-B target burn of lab/studies/fusion-ignition |
| Branch | claude/project-thread-1p6mtu, 2026-11-22 to 2026-11-25 |
| Open owner questions | ENG-062 scanned (vertex-extraction): burn 4 m aft with closure x4 is the best interception; blade structural dynamics (ENG-058); Q-CMP-2 blade aft ends; R1 engine sized for the V4 ship |
| Review | `vertex-*/REVIEW_*.blend` (local; final reference `vertex-pulse/REVIEW_PULSE.blend`) and the renders in the project files; the public view is `engineering/fusion-ignition/`; register `PROBLEMS.md` |

# vertex-compact-engine: notes

The Vertex engine studies of one thread (2026-11-22 to 2026-11-25), moved here from `work/` at the squash. The subfolders import each
other as siblings; run scripts from the repository root, for example `python3 lab/studies/vertex-compact-engine/vertex-thermal/thermal.py`.
Each subfolder keeps its own `NOTES.md` (except `vertex-source`, described below), scripts, results and problem registers.

| Folder | Question | Outcome |
| --- | --- | --- |
| `magneto-photonic-nozzle` | Can grazing mirrors and a magnetic nozzle steer the burn's photons? | Limited for hard X-rays, none for neutrons |
| `vertex-ron` | Remote and distributed engine layouts (A-E) | Remote layouts archived as comparison |
| `vertex-ampn` | Adaptive magneto-plasma nozzle | Fixed B beats adaptive; exhaust dust shield rejected |
| `vertex-hims` | Hybrid impact and magnetic shielding | Passive screen lightest; ENG-001..021 |
| `vertex-compact` | Compact engine C1-C4 on the approved ship | C4 best, not closed (heat 10,800x); ENG-030..038 |
| `vertex-thermal` | Supermirrors, cooling mesh, per-part heat; owner decisions 2026-11-24 | B edge-on blades adopted, thin blanket optional, full blanket archived; 1,575x the radiator share remains; ENG-040..060 |
| `vertex-extraction` | ENG-062: early extraction, closure topology, burn position and field strength against nozzle interception | Topology and burn position set the struck share, field strength alone does not; best 0.94 MN at 1,967x; extraction is a heat lever (300x at 0.34 MN); nothing closes |
| `vertex-optimize` | Burn 4 m aft with closure coils x4 (research geometry), combined with extraction; coil engineering; plasma cavity; momentum balance | 0.94 MN at 1,155x (pickup re-traced), mostly through the field; with 80 % extraction 0.36 MN at 228x, not multiplied; capture needs 286 GJ and 30 T at the windings; nothing closes |
| `vertex-pulse` | Pulse size, coil current distribution, extraction and energy transfer on the research geometry (working model 2026-11-25); integrated hardware round the coils | Pulse size moves the rate, not the heat (8,448x at every size); no size fits face and injector together; ring currents cut capture 286 to 83 GJ and 60 to 25 T; the jet must carry 80 % of the fusion power and carries 5.1 %; 87 parts, 0 clashes; nothing closes |
| `vertex-source` | Where the burn puts its energy and which levers move it | 85 % X-rays at the design point; early extraction and a tungsten tamper move energy to plasma, heat moves to strikes; ENG-061..063 |

**vertex-source.** `source.py` (about 15 s) writes `results/source.json`: product slowing-down (Sivukhin ion share, Spitzer times and
ranges), bremsstrahlung ratios, every target lever through the R2-B burn and the coupled C1 engine, an X-ray trapping tamper (cold
opacity, an upper bound), the 63.1 % against 54.6 % pickup audit and a technology table. Its PROTOTYPE choices are in `params`.
`vertex-thermal/export.py` copies both results into `lab/studies/fusion-ignition/imports/`.

Nothing here is canon and nothing writes to `data/`.

## Phase close (owner 2026-11-25 14:37Z)

The owner accepted the Vertex Drive design and the Fusion Engineering simulation as the completed milestone of this phase; the engine
geometry is the visual development reference. No further research, optimisation or modelling iteration until a new phase. Nothing here
is promoted to canon: every performance figure stays a model result, every unsourced choice stays PROTOTYPE.

**Working configuration (research geometry, the visual reference).** The compact Vertex engine of the approved ship (four engines, the
compact cluster envelope kept), with the burn about 4 m aft of its drawn point and the closure coils C1, C2 and L1 at four times their
drawn ampere-turns (`mirror4|4`, vertex-optimize), every ribbon re-aimed edge-on at the moved burn, the research nozzle `R|1`, B edge-on
thermal blades (thin 248 t blanket optional), and the integrated hardware round the coils (vertex-pulse `frames.py`: re-aimed tungsten
lips, twin-bore lithium headers, 20 K and warm rings, warm manifold, supermirror strips, trays and supports; 87 parts, 0 clashes, every
network connected). The original geometry stays as the comparison (page switch Original / Research). Final Blender reference:
`vertex-pulse/REVIEW_PULSE.blend` (scene INTEGRATED; scene SECTION, the C1 meridian section), built by `vertex-pulse/blender_pulse.py`
from `vertex-optimize/REVIEW_OPTIMIZE.blend`; `.blend` files are local, the scripts rebuild them.

**Where the models leave it (not canon).** Coupled C1: 0.41 MN for four engines at 2,200x the radiator share, exhaust 8,772 of
19,201 km/s. Research geometry: 0.94 MN at 1,155x; with 80 % early extraction 0.36 MN at 228x (the levers compete). At mission power
(65.3 TW per engine) every pulse size gives 1.73 MN per engine at 8,448x. Need: 21.8 MN, 19,201 km/s, 1x. The jet carries 5.1 % of the
fusion power and must carry 80 %.

**Limitations of the models.** Vacuum test particles and a diamagnetic-cavity picture, no coupled plasma expansion (PIC/MHD); 0-D target
burns (R2-B) scaled per pulse; two charged-energy bases that are not reconciled (ENG-075); cold-matter opacity for every shell and face;
the optimised ring currents not re-traced for steering (ENG-076); impact rules above 100 km/s extrapolated; parametric hardware placed by
search with clearance checks, not structural or thermal analysis; no blade or root dynamics (ENG-058).

**Recommended directions for the next phase** (each answers a consequential decision; order by the register's severity):
1. One reconciled source model for capture and thrust (ENG-075), then a coupled plasma expansion in the research geometry (ENG-070, ENG-003).
2. Burn physics: a photon share near 10 % together with a low-loss nozzle, the only route the jet-share condition leaves open (ENG-078).
3. A plasma-facing concept that survives the per-pulse X-ray load at the face distance, or a protected injection path (ENG-074, ENG-044).
4. Steering re-trace with the optimised ring currents, then conductor, quench and structure at that distribution (ENG-076, ENG-077).
5. Thermal study re-run for the moved burn, armour covers for exposed lines, blade dynamics and edge-strip life (ENG-070, ENG-079, ENG-058, ENG-057).
6. Driver at the pulse rate and the gain it needs (ENG-080); R1 engine sized for the V4 ship.

**Register.** `PROBLEMS.md` (generated by `register.py` from the page results and `vertex-hims/PROBLEMS.md`) consolidates ENG-001..080 and
the set-aside concepts; all OPEN items stay open.
