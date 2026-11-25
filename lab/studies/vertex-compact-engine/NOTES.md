<!-- lab entry -->
| Lab entry | |
| --- | --- |
| Kind | Study |
| Status | ACTIVE (research behind the deployed Fusion Ignition page; not canon) |
| Question | Can the compact Vertex engine reject its heat and reach the mission exhaust speed, and which nozzle, protection, cooling and source choices move it closest? |
| Model base | main d016d5d; Vertex engine as built (`vertex_engine`), R2-B target burn of lab/studies/fusion-ignition |
| Branch | claude/project-thread-1p6mtu, 2026-11-22 to 2026-11-25 |
| Open owner questions | ENG-062 scanned (vertex-extraction): burn 4 m aft with closure x4 is the best interception; blade structural dynamics (ENG-058); Q-CMP-2 blade aft ends; R1 engine sized for the V4 ship |
| Review | `vertex-*/REVIEW_*.blend` (local) and the renders in the project files; the public view is `engineering/fusion-ignition/` |

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
