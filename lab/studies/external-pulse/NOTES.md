<!-- lab entry -->
| Lab entry | |
| --- | --- |
| Kind | Study |
| Status | ACTIVE |
| Question | Is an external pulse architecture (pusher plate, magnetic pusher or remote field coupling) worth building for Wayfarer's 0.016 c four-burn mission, and does it solve the Vertex 1.5 thermal problem or only move it? |
| Model base | main eb33a44 (operating point, mission, radiators; Vertex 1.5 evidence `references/evidence/vertex_radiation.json`) |
| Branch | claude/project-thread-6qwiwi, 2026-11-15 |
| Open owner questions | The next propulsion milestone (REPORT, Recommendation); whether a directional fusion pulse or a leak-free magnetic reflection may ever be assumed (both UNVERIFIED) |
| Review | GitHub Pages /engineering/studies/external-pulse/ after a squash; the engineering brief (Claude Doc) linked from the thread |

# external-pulse (EXT-01): notes

Owner brief 2026-11-15 ("WAYFARER: Post-Vertex 1.5 Architecture Decision"): compare three external pulse concepts with documented
physics and established propulsion research, bound each one's momentum transfer, energy and momentum conservation, radiation intercepted,
heat into hardware, ablation, pulse mechanics, fatigue, exhaust velocity, mass, propellant and shielding, check them against about
0.016 c, and say whether external pulse propulsion reduces the thermal problem or only moves it. Build nothing; change nothing in the
model. Research only, NOT canon.

## Function

- `params.toml`: every bracket of the study with its status (PROTOTYPE, UNVERIFIED, the project evidence it comes from) and the
  literature precedents with their claims (PROPONENT_CLAIM, secondary sources named).
- `ext01.py`: one energy and momentum ledger per joule of pulse yield for each concept; the mission (the operating point's rocket
  equation with tank growth, thrust from the burn-time share of the LOCKED 6 y mission, the canon radiator's 10.8 GW hot budget); a
  full-factorial search over the brackets (760,000 cases, about 35 s on 4 cores); the assumption ladder; `results/ext01.json` and the
  figures. `python3 lab/studies/external-pulse/ext01.py`.
- `figures.py`: the two SVG figures. `tests/test_ext01.py`: conservation, the capture bounds, the mission reproduction, the evidence
  (`python3 lab/studies/external-pulse/tests/test_ext01.py`, not CI).

## Fixed constraints

- The mission as built: four burns of 4,797 km/s (0.016 c), protected and operational mass 1,300 t, tank dry fraction 0.15 of added
  propellant, departure envelope 4.0-4.6 kt (WORKING), 6 y (LOCKED), radiator 14.4 GW with a 10.8 GW hot budget.
- The fusion source: the photon and neutron shares of a compact D-3He burn are the Vertex 1.5 cases (photons 12.5 / 21.7 / 84.8 %,
  neutrons 4.4 / 4.8 / 2.9 %). The burn is the same physics wherever it happens.
- Nothing is carried over from Vertex's engine: thrust follows from the mission and the burn-time share, the exhaust velocity from the
  ledger, the pulse rate is a searched bracket (10, 100, 1,000 Hz), not 5.7 kHz.
- No pulse-unit or device design. The yield, its partition, its directionality and any photon conversion enter as bounded numbers.

## Unknowns

- Whether any fusion micro-pulse can be directional (UNVERIFIED; momentum balance caps any directed pulse at a forward mass share of 1/2).
- Whether matter around a burn can turn its photons into debris kinetic energy without slowing the debris (not modelled: the search
  grants it with no mass penalty, which is inconsistent at the fuel-only speed cap).
- How much captured plasma leaks along field lines onto a coil. The project's only evidence is Vertex 1.4's internal-cavity closures
  (1, 9, 28 %); 0 is the unestablished best case.
- Pulse burnup (0.05-0.8), driver repetition rate (no source), the coil's thickness as the burn sees it, field reach beyond the coil.
- Radiation transport: photons that meet hardware are taken as absorbed (the plate and a coil shield are thick); neutrons deposit
  10-100 % of the intercepted energy. No Geant4/OpenMC (deferred by the owner).

## Design freedom

Plate half-angle, restitution, stagnation share and cooling (radiator or ablation); coil reach, thickness and capture cone; pulse rate;
burn-time share (with the schedule delay it costs); magnet specific strength; shock stroke and plate velocity jump.

## Findings

- **No concept closes the mission on established physics.** With an isotropic bare pulse every concept fails: A has no solution at any
  departure mass (fastest 7,200 km/s, below the 9,420 km/s tank-growth limit), B and C reach at most 10,800 km/s against the 18,700 km/s
  the 4.6 kt envelope needs.
- **A (pusher plate) moves the thermal problem and makes it worse.** The plate sees 6.7-33 % of the sky and takes the stagnation heat:
  at least 132x the radiator at the most favourable corner (2,500x on the canon schedule), against Vertex 1.5's 854x. Cooled by
  ablation it reaches at most about 20 km/s (Isp about 2,000 s), which is where Orion's own claims sit, about 1,000x short of the mission.
- **B (magnetic pusher) does reduce the photon problem**, because a coil can see only 0.015-1.25 % of the sky against Vertex's 62 %.
  The heat moves to the plasma-field interface: with a 1 % leak (the smallest Vertex 1.4 value) B needs 222x the radiator. Only 6 of
  314,928 cases close, all at the corner where four UNVERIFIED best cases hold at once: a directional pulse at the momentum optimum,
  90 % photon conversion with no added mass, a leak-free fully elastic field reflection, and a coil 0.5 % of its radius thick, at 1 kHz.
  Without photon conversion the best case misses by 2 % (schedule); the leak it could tolerate is about 0.005 %.
- **C (remote coupling) trades heat for magnet mass.** The coil's sky share falls to 1e-6-0.25 %, but the stored field energy grows with
  the cube of the reach (dipole), so the magnet mass outgrows the ship: no case closes; best 1.07x, isotropic 14.7x, with leak 573x.
- **External placement moves heat, it does not remove it.** Heat per newton scales with exhaust velocity times the hardware's absorbed
  fraction; at 19,200 km/s the hardware may absorb about 4e-5 of the yield whatever its architecture.

## Decisions

- 2026-11-15: the search grants every UNVERIFIED best case and then removes them one by one (the assumption ladder); a concept counts
  as established only if it closes with an isotropic bare pulse.
- 2026-11-15: the canon schedule (four burns in 28.5 d, 1.3 % of the mission) is the reference; longer burns are searched but cost a
  schedule delay against the LOCKED 6 y, recorded as a gate.
- 2026-11-15: no new breakthrough record. EXT-01's requirements (directional pulse, leak below about 0.005 %) stay in this study and the
  brief; registering any of them is an owner decision.
