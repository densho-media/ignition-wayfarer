# Ship Systems Architecture (ISSA) — work notes

| Kind | Status | Question | Model base | Owner questions |
| --- | --- | --- | --- | --- |
| study + proposal | ACTIVE (Phase II, owner review) | Which ship systems are missing, how much power and space they need, and where they could go without changing canon, silhouette or budgets | main at branch start, built locally (assets/wayfarer) | DR-01 … DR-15 |

**Function.** Systems-engineering review of G.U. WAYFARER 001: inventory (`systems.toml`, 56 assemblies, 13 families, one owner
each), electric load model over 15 conditions and a source screen (`eps_study.py`), a voxel survey of the built vehicle
(`survey_blender.py`, `districts.py`, `figures.py`), a review file (`make_review.py`) and the proposal page (`build_report.py` +
`report_template.html` → `results/issa.html`, published as https://claude.ai/artifact/7oSfK7TWrd2RSctscycsDA).

**Fixed constraints (brief 2026-11-27).** No canon, production geometry, silhouette, dimension, mass-allowance or Drive change; no final
power technology; no squash, no deploy; parked propulsion research touched at interfaces only.

**Key results (all NONCANON, PROTOTYPE/STUDY).**
- Coast demand: 0.8 MW ship service, 3.6 MW with proactive defense, 26 MW with the normal active band. Defense duty sizes the plant (DR-01).
- Candidate A (main drive in hotel mode) not credible. Direction D: L1 drive-derived burn power, L2 two fission-Brayton plants (working
  baseline; auxiliary fusion as a speculative alternative), L3 isolated survival source + batteries.
- The 50 t power/computers/steering/comms item already holds ~31.5 t (19–51); ~18.5 t left. Two ship-service plants ~24 t before shields.
- Coast plants can reject to the dark blades (119 MW at 550 K); no new radiator.
- Casing interior 31,319 m³; usable blocks 1,230 m³; aft bay 75 m³ usable; dry store 3,800 m³ is the reserve (repurpose M1–M4, M8–M9).
- Inconsistencies: crew-5/6 life-support sizing vs crew 12; stale G01 evidence; unrated Brayton proxies in the run-tank zone; Deadship
  generator assumes A; no budget line for drive-off or burn generation; food ~48 t vs 10 t.

**Decisions.** See the proposal page, section J (DR-01 … DR-13). First task K: EPS-A power-load module, no geometry.

**Run.**
```
python3 work/ship-systems-architecture/eps_study.py
/snap/bin/blender -b assets/wayfarer/WF_WAYFARER_001.blend --python work/ship-systems-architecture/survey_blender.py
python3 work/ship-systems-architecture/districts.py && python3 work/ship-systems-architecture/figures.py
/snap/bin/blender -b assets/wayfarer/WF_WAYFARER_001.blend --python work/ship-systems-architecture/make_review.py -- --render
python3 work/ship-systems-architecture/build_report.py
```
Review file (not in Git): `work/ship-systems-architecture/REVIEW_SHIP_SYSTEMS_ARCHITECTURE.blend`, copy in the project files `review/`.

## Phase II (owner brief 2026-11-27 11:08Z, clarification 11:36Z)

**Function.** EPS-A in the repository (`src/wayfarer/power_loads.py`, `[power.loads]`, `data/systems.toml` + `src/wayfarer/systems.py`,
`references/p1_power_loads.json`, `tests/test_power_loads.py`); studies in `phase2/`, run in this order:
`eps_b.py` (generation A–F, lean sizing, duty, L1, L3, thermal, transitions, cryo) → `placement.py` (assembly envelopes, five layouts,
dose screen with blade scatter) → `mission.py` (destinations at 0.016 c, provisioning 6 months–10 years for 6 and 12, logistics
containers, narrative, service life, L2 reliability by duration) → `eclss_mass.py` (strings, resource ledger, shield water, RCS,
integrated mass) → `fmea.py` (12 scenarios) → `build_report.py` (page, Phase II from `phase2/report2.py`). `make_review.py` adds the
layouts as `WORK_ISSA_6x_LAYOUT_*` (L-E visible).

**Decisions taken here (STUDY, owner review).** Phase I numbers superseded: coast 3.2 MW known (+ OPEN bands), burn heat-pump running work
~82 MW (not 210), battery pack 2.5 t (no second packaging factor), ride-through ~10 min after the protected black-start reserve. Working
architecture: L2 4 × 1.75 MWe fission-Brayton (3+1) in layout L-E (M1–M2, aft of all crew spaces), shadow shield + blade-facing scatter
band (~28 t per unit), L1 from the drive hot loop, L3 10–40 kWe crew-only for 30 d, dedicated defense buffer. Six years is narrative
(owner): provisioning per mission; 12-month standard load for 12 is ~20 t in 4 of 54 containers.

**Unknowns.** Defense engagement frequency at 0.016 c; drive standby/restart energy; scatter dose (needs a transport calculation);
reactor/Brayton reliability; mass (~600 t beyond today's lines, three PROPOSED lines); the M1–M2 allocation (DR-12/DR-15).

## Phase III (owner brief 2026-11-27 12:00Z): architecture optimisation and parametric equipment modelling

**Function.** Correct Phase II, couple power, heat, storage, shielding, redundancy and mass, model one parametric L2 unit (EPS-G1) and
district variants in review geometry, compare complete candidates on coupled propellant. Run order after Phase II:
`python3 src/wayfarer/power_loads.py` → `phase2/{eps_b,placement,mission,eclss_mass,fmea}.py` (corrected) → `phase3/eps_g1.py`
(unit envelopes, four districts, survey-grid conflict screen, thermal-machinery envelopes) → `PYTHONPATH=work/ship-systems-architecture/phase3
python3 work/ship-systems-architecture/phase3/study.py` (III-A/B/D/E → `results/phase3.json`) → `/snap/bin/blender -b
assets/wayfarer/WF_WAYFARER_001.blend --python work/ship-systems-architecture/make_review3.py -- --render` (REVIEW_ISSA_PHASE3.blend, three
stills) → `build_report.py` (page; Phase III from `phase3/report3.py`, Phases II and I kept).

**Fixed constraints.** No canon, Drive, production-geometry or final mass-budget change (owner boundaries). Production radiators stay the
baseline (DR-03); the 550 K section is an isolated research variant. Dry-store repurposing only in review geometry (DR-12).

**Decisions taken here (STUDY).** Working doctrine DR-01 in burns removes the burn heat pumps; EPS-A gains state HIGH_THRUST_PROACTIVE.
Shield mass = envelope volume × 1.9 t/m³. Recommended research direction N2: 2+1 × 2.66 MWe, one unit per blade, running through burns
on a 550 K section; L1 reduced to drive-specific loads with heat-pipe hot blades; R1 black start. ~283 t dry (+1,035 t at departure), not closed.

**Unknowns / blockers.** Radiation transport (BLOCKER: no MCNP/OpenMC here); L1 900 K rejection; LOW margin at the high band; He-3 tank
shadow; hot-loop pumps; channel refill time; unit restart energy; Brayton degradation; engagement frequency.

## Phase IV (owner brief 2026-11-27 12:55Z): physical closure and infrastructure

**Function.** Resolve the physical assumptions behind N2 rather than reduce mass: reconcile Phase III, build a radiation-transport
capability, derive hot-loop transport, check radiator view factors in burns, size L2/storage/district/cryo heating/ECLSS/logistics, run
missions on one hardware set, converge. Run order after Phase III: `radiation/` (README: install, `fetch_data.py`, `bench.py`,
`wayfarer_rt.py`; OpenMC env, data outside Git) → `python3 work/ship-systems-architecture/phase4/study4.py` (`results/phase4.json`;
`phase4/viewfactor.py` is the Monte Carlo) → `/snap/bin/blender -b assets/wayfarer/WF_WAYFARER_001.blend --python
work/ship-systems-architecture/make_review4.py -- --render` (REVIEW_ISSA_PHASE4.blend, two stills) → `build_report.py` (Phase IV from
`phase4/report4.py`; III, II, I kept).

**Fixed constraints.** As Phase III; owner directions DR3-01..09 (N2 leading research architecture, not final). No canon, Drive or
production-geometry change; radiator and district work is review geometry only.

**Findings (STUDY / TRANSPORT-INFORMED).** The production graded bulkhead already shadows WARM and LOW from the other blades' hot faces
(F ~2e-4; without it 0.025 / 0.008); the Phase III 550 K section sits aft of it and is exposed (F 0.02), so N2-R4a moves the bulkhead aft
of a 700 K section (24 m, 2.1 GW of hot capacity: inside the 3.95 GW ideal margin, outside the 20 % rule). Phase III read the tank x as a
span: the He-3 tanks are ~195 m forward, inside the 12.5 deg shadow cone, so the direct path closes; scatter needs 3-D transport. Hot
transport is ~5-30 MW of pump work and ~150-700 t of lithium hardware (H5 zones + heat-pipe fins recommended). L2 optimum ~3.1 MWe per
unit nominal (4.9 at the high band): study basis 3 x 3.5 MWe, strategy C. CIRC-001 (40.2 t) is not in the operating-point end mass
(reference departure ~4,573 t coupled). ECLSS needs 7 units for ring loss + unit failure. N2-R4a ~855 t dry (~360 t without transport),
+3.1 kt departure; the 283 t Phase III figure is withdrawn. Owner: DR4-01..09.

