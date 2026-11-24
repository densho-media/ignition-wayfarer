<!-- lab entry -->
| Lab entry | |
| --- | --- |
| Kind | Study (with variant blockouts) |
| Status | ACTIVE (research, not canon; awaiting owner review) |
| Question | Which Vertex nozzle architecture is thermally viable and mass-efficient, and what does it cost the whole ship? |
| Model base | 250a756; production geometry, data and canon unchanged |
| Branch | claude/project-thread-1p6mtu, 2026-11-22 |
| Open owner questions | Q-RON-1 path when no nozzle meets 4,426 t; Q-RON-2 adopt B (ring R 50 m, ship 800 m) with E as upgrade; Q-RON-3 future tape as planning assumption; Q-RON-4 ship-hit criterion and continuous optimisation next |
| Review | Claude Doc https://claude.ai/artifact/8EpMa1LufTfyHQHhdaqHcy; REVIEW_RON.blend and RON_<variant>.blend (local, not in Git); renders/ |

# vertex-ron: notes

**Function.** A nozzle for the four Vertex engines that keeps hardware heat out of the ship's hot loop (10.80 GW drive share), steers
the charged exhaust aft, and costs the least whole-ship mass for the canon mission.

**Fixed constraints.** Canon operating point (references/p1_operating_point.json): 65.3 TW fusion and 5.44 MN per engine, four burns of
4,797 km/s, departure 4,426 t, dry 1,629 t, 250 t drive package. Radiation shares from Vertex 1.6B (V2 reference, V3 parallel). Physics
(class A) is never relaxed; the mission (class B) is held fixed and every change is reported as a whole-ship delta; allocations (class C:
the 250 t package, 2,000 K nose and 2,300 K plug limits) are traded.

**Unknowns (OPEN).** Plasma-coupled capture (test particles in a vacuum field only); coupled neutron-gamma transport for the noses;
pulsed structural dynamics of 800 m booms and blades; dust exposure; the canon reference directed fraction (0.946 inferred).

**Design freedom.** Ring radius, burn distance (kappa), ship distance D, engine spacing S, current multiple, pulse rate, tape current
density, plug grazing angle, fins, mirror coil share. All PROTOTYPE.

**Decisions.** Heat closes for every deployed architecture (0.0-0.1 GW piped); mass does not (best 11.5 kt departure). B at D 800 is the
recommended working point, E's shadowed forward mirror the upgrade path (lightest with future tape). Compact engines fail on physics.
RON 0.2 fixed a hoop-radius error of 0.1 (conductor, cryostat, nose used the burn distance). MPN errata: per-engine thrust 4x, F load path.

**Files.** `ron.py` (standard library, about 5 min, `python3 lab/studies/vertex-compact-engine/vertex-ron/ron.py [--quick] [variant prefixes]`) writes results/ron.json,
results/ron.log and geometry/<variant>.json; `tables.py` writes results/tables.md, results/variants.csv and figures/pareto.svg;
`blender_ron.py` (`/snap/bin/blender -b --factory-startup --python lab/studies/vertex-compact-engine/vertex-ron/blender_ron.py -- [--no-render]`) builds the
WORK_RON_<variant> collections, REVIEW_RON.blend, one RON_<variant>.blend per prototype and the renders (Eevee perspective, Workbench
orthographic). The ship in the blockouts is a proxy cylinder; the approved ship assets were not built in the cloud container.
