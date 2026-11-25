<!-- lab entry -->
| Lab entry | |
| --- | --- |
| Kind | Study |
| Status | PARKED (live RESEARCH page; six chapters, 24 stages; accepted as the phase milestone by the owner 2026-11-25) |
| Question | Fusion Engineering, From Nucleus to Engine: how is the Vertex drive built, started and ignited, what do the models predict at each step, and where does it fail? |
| Model base | main c169a9f with the compact C1-C4, thermal, source and extraction imports of lab/studies/vertex-compact-engine; Vertex modules vertex_engine, vertex_magnet, vertex_radiation; ignition-failures and selective-fusion results |
| Branch | claude/project-thread-1p6mtu, owner brief 2026-11-23 10:08Z |
| Open owner questions | Review of the live page; Q-CMP-2 blade aft ends; ENG-062 scanned (burn aft + closure x4 best, a geometry change); R1 engine sized for the V4 ship. Q-TH-1..3 answered 2026-11-24 (B adopted, thin blanket optional, source first) |
| Review | engineering/fusion-ignition/ on the live site |

# fusion-ignition: notes

**2026-11-24 09:49Z brief (Fusion Engineering: From Nucleus to Engine).** The page became one journey of six chapters and 24 stages
(`chapters.py` adds the data of the new stages; `tools/story_ignite.py` STAGES; the viewer's SEGS map each stage onto the page's
existing 3-D and 2-D scenes, so there is still one engine model and one ledger). New: matter and gyroradii, unwanted reactions,
fuel mix (steady and pulsed kept apart), the rejected accelerator, spin polarisation, an optimizer that labels unmodelled lever
combinations, the ENG-062 extraction scan, radiation types, an interactive supermirror (energy and angle against R and absorption,
visible light and neutrons for contrast), member shapes with alignment, vibration and edge loads, assembly in dependency order (reverse,
isolate), start-up, the operating engine with independent layers, the engine in the ship, and a concept comparison with maturity levels.
The register gained cause, component, intended solution, deficit, future improvements and maturity, ENG-064 (struck plasma stays in the
engine) and ENG-065 (topology, not field strength), and a list of failed or rejected concepts. The pulse ledger is now momentum-consistent
(coupled C1: 0.41 MN, 8,772 km/s, heat 2,200x).

Owner brief 2026-11-23 10:08Z ("Fusion Ignition: Interactive Engineering Simulation"). The flagship simulation of the Vertex drive, from
the need for an engine to a single D-3He reaction and back out to thrust, with the modeled failures kept visible. Not canon. No
deployment, squash or geometry change is authorised.

**Function.** `model.py` writes one data file (`results/fusion_ignition.json`) that `tools/story.py` publishes with the page
`engineering/fusion-ignition/`; `web/engineering/fusion-ignition.js` draws it. The page computes no new spacecraft facts: it looks values up
and interpolates the precomputed grids.

**What is calculated, sampled, imported or illustrative** (every block of the data names its class, and the page shows it as a chip):

| Stage | Content | Class |
| --- | --- | --- |
| 0 need | departure mass, delta-v, exhaust speed, thrust, jet and fusion power (`operating_point.report`) | SPEC (WORKING) |
| 1 hardware | the 264 inspection parts in 12 categories (Explore Ship's engine file) | MODEL geometry |
| 2 startup | coil currents and stored field energy (`vertex_magnet`, NOMINAL); pulse bank and driver power (ignition-failures) | CALCULATED; charging power ILLUSTRATIVE (100 MW) |
| 3 fuel | burned D-3He per pulse (`vertex_radiation.implied_target`), hydrogen per pulse (FPS flow) | CALCULATED; hydrogen coupling SPECULATIVE |
| 4 nucleus | Coulomb barrier, Gamow energy and peak, Bosch-Hale cross section, products 14.7 / 3.7 MeV | CALCULATED; the nuclei pictures ILLUSTRATIVE |
| 5 many | fusion per Coulomb collision (cross-section ratio), reactivities | CALCULATED |
| 6 ignition | thermal Lawson curve (1:1, brems only); the Vertex target burn `vertex_radiation.burn` (R2-B) over areal density and start temperature | CALCULATED; the compression to the design areal density is OPEN |
| 7 nozzle | charged-particle paths in the NOMINAL vacuum field (Boris push, vertex_magnet's field and obstacles), x1 and x4 | SAMPLED |
| 8 losses | per-engine energy channels and the problems ENG-030..038 for C1-C4 | IMPORTED (lab/studies/vertex-compact-engine/vertex-compact) |
| 9 heat | six steps: source energy transfer (burn levers and tamper through the ledger), supermirrors A and D, edge-on blades B (adopted), thin and archived blankets, hot lithium and warm NaK circuits, 20 K circuit, service interfaces and the path from fusion to space; 395 drawn parts with an inspector each; problems ENG-040..063 | IMPORTED (lab/studies/vertex-compact-engine/vertex-thermal and vertex-source, `imports/thermal_*.json`, `imports/source_*.json`); every parameter PROTOTYPE |
| lab | fuel mix, temperature, hot-ion, polarisation (selective-fusion grid); field multiple (compact scan); coil armour (MPN rule); grazing-incidence mirrors | CALCULATED / SAMPLED / MODEL-BASED |

**Findings worth keeping.** At the design areal density (96.7 g/cm2, about 100 times what laser-driven D-T has shown) the target burn reaches
the engine's yield with a gain of 23, but 85 % of the fusion energy leaves the target as X-rays: the photon heat in ENG-030 is born in the
burn itself. At 10 g/cm2 the gain is 6-13 and the burn fraction 0.31. Thermal 1:1 D-3He needs n tau about 6e20 m^-3 s at 100 keV (4 times
D-T) and cannot ignite below about 35 keV because bremsstrahlung exceeds the fusion heating. In the vacuum field 64 % of the 14 directions
hit hardware for every species, and four times the field does not change that (C1): the products that miss the nozzle strike the shield
and loops before the field turns them. One D-3He collision in about 260 (at the Gamow peak) to 10,000 (at 100 keV) fuses; the rest scatter.

**Files.** `model.py` (data), `site.py` (page contract `WF_FUSION_IGNITION`, refuses stale results), `tests/test_model.py` (physical
invariants, outside CI), `imports/compact_aebbb0d.json` (copied once by `lab/studies/vertex-compact-engine/vertex-compact/export_flagship.py`).

**Unified ledger (owner brief 2026-11-23 13:11Z).** `ledger.py` reruns the R2-B burn with full energy and particle bookkeeping (tests require
identical results to `vertex_radiation.burn`), over areal density x start temperature x D:3He mix, and carries one pulse through the nozzle to
thrust and engine heat. Four model states stay separate: MISSION (operating_point), DESIGN (vertex_engine pulse point, 0.78 jet assumed),
COUPLED (this ledger) and STEADY (compact study source, a non-sustaining steady plasma at n_e 1e21). Reconciliation R1-R4 is in the results
and on the page. Experiment mode evaluates the same pulse function in the browser (checked equal to the Python value).

**Preview without Blender.** `preview_viewer.py runs/<site>` adds `viewer/build.json`, the engine inspection files, the field file and
vendored three.js to a `tools/wos.py --out runs/<site>` build, so the 3D view runs without a Blender build. Serve the site with
`python3 -m http.server`.
