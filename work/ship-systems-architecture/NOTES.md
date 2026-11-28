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

## 3D Systems Integration, Track F1 (owner brief 2026-11-28 07:03Z)

**Function.** Build the F1 reference (WF-F1-P6.0, FT-03 1500 K approved as fiction) in 3D, stage by stage (A masterplan .. I remaining),
maturity M0-M4 (most systems to M2, selected M3), checkpoints 1-4 committed separately; F0 and Track R stay comparisons; production unchanged.
Code and config in `integration3d/` (`f1_integration.toml` = registry and zones). Run order after Phase VI: `integration3d/tanks3d.py`, `power_unit.py`, `radiators3d.py`, `h6a3d.py`, `radiators3d.py` again, `electrical3d.py`, `systems3d.py`, `consolidate.py`,
`integration3d/masterplan.py`, `ledger3d.py`, then `/snap/bin/blender -b assets/wayfarer/WF_WAYFARER_001.blend --python integration3d/make_review_i3d.py -- --render`,
then `build_report.py`.
**Checkpoint 1 (A + B + registry).** Masterplan: production zones from the pure modules, F1 zones from `phase6.json`, keep-outs, live ledger
(`results/i3d_masterplan.json`, side/farm/maturity SVGs). Tanks: all 13 vessels are at their packing limits, so volume comes from length or
density: T-A stretch +18.2 m (exact; supersedes Phase VI's 20.1 m linear estimate), T-B tandem modular segment +23.9 m (+64 t tankage,
mission-modular), T-C slush H2/D2 + re-allocation +16.4 m (FT-09 proposed, new balance search). Recommended T-A as reference (DR-3D-01).
**Checkpoint 2 (C + D).** `power_unit.py`: one reusable L2 unit (M3; 12.1 m, 97 t, shield 25 t from its geometry, all conversion parts inside
the shadow boundary, recuperator/gas cooler/PMAD split under the 3 t ORU limit; TAC 7.9 t and reactor/IHX need a heavy carriage, a new MRU
requirement), placed three times with shared mesh data; district clearances screened, L1 bus moved to its own slot (az 30), district displaces
body-bay module 1 (6 dry-store containers). `h6a3d.py`: four trunks per blade (Phase VI drew one per path), outside the hull flanking the blade
root (a 1990 K line inside would heat the bay), valves 34 and bellows 30 per blade = model, EM pumps 7.5 t each (MRU). Review file
`REVIEW_I3D.blend` (built by `make_review_i3d.py`, CP1-CP4 layers; all 19 registry systems at their target level).
**Checkpoint 3 (E + F).** `radiators3d.py`: the Carnot-fraction FT-03 figure is not a cycle; a recuperated He-Xe Brayton at 1500 K gives
eta 0.154 only with a 793 K (contemporary components) or 872 K (advanced, proposed as FT-03 amendment DR-3D-02) compressor inlet, so the L2
radiator runs at an emission-equivalent 896 K and the section grows to 9.38 m (x 41.02-50.4, -173 MW HOT headroom). L2 section at M3:
NaK loops (D 223 mm, casing-hull annulus at +-20 deg from the bus azimuths), header serpentines at the aft edge of two chord bays, 2192 K
heat pipes per blade with AFT evaporators (burns drain the condensate to them; a forward evaporator dries out; a wickless thermosyphon floods),
worst limit margin 1.59; header biasing 67/33 after a unit trip. Phase VI counted only the headers: +74 t dry. HOT Li fins: aft-pointing halves
lose 5.6 % (0.77 GW) at 0.74 g -> forward-pointing fins (DR-3D-04, +18 t); trunk shading bound 0.47 GW; HOT reserve 0.39 GW with the fin
change, -0.39 GW without. WARM/LOW interleaved A/B pumped panels (79 % / 86 % after a loop loss). L2 placement aft is DR-3D-03.
`electrical3d.py` (M2): three 3 kV sectors, normally-open ties at x -78/14/98, 10 kV L1, 6 kV defense bus, 270 V refuge bus on L3; 4.9 t of
conductors within the 8 t line; 7 of 8 single faults ride through (district loss is the refuge case); L1/bus-1 0.93 m needs a barrier.
`h6a3d.py` now reads the L2 length and puts trunk supports at <= 8 m (PSA HO-01: 4 per section, one anchor, 155 kN per section at 0.74 g).
`ledger3d.py`: live departure 8,478 t (+287 t vs Phase VI, 3.66 t/t); pending DR-3D-04 +65 t, DR-3D-03 -132 t.
**Checkpoint 4 (G + H + I).** `systems3d.py`: hub ECLSS unit at M3 as 8 ORUs (all <= 0.70 m, two levels, 990 kg + 210 kg frame, 3.4 kW) with
D 0.28 m ducts through both transfer drums (24 Pa); ring units M2; 5/5 Phase V cases pass. LOG-G1 M3: `container(gross_t)` (3 t: 2.05 m,
0.60 t tare, 4 grapples, 8 latches; shared meshes in the hub store). The six displaced dry-store containers move to body-bay module 10
(x 22.25-33.25), defense buffers +3 m, closest data/bus clearance 0.69 m, +4 t racks. MRU heavy carriage on keel lane az 270 (rated 24.7 t,
186 m rail, coast only, parks for burns); robots + rail 10.6 t. Cryocoolers at T-A area (1.60x) + OpenMC nuclear heating: 264 W at 3 K, 5.86 kW
at 20 K, 934 kW input, 11.2 t, 13 stations; LOW short 76 kW, WARM short 496 kW (Phase VI 370 + NaK leak 99 + bus 27) -> pending +2.7 m
WARM / +0.8 m LOW. GNC/CDH M1 placeholders; structure envelope only (mass is PSA's). Ledger 8,573 t (+381 t vs Phase VI).

## Phase VI (owner brief 2026-11-28 06:33Z): dual-baseline integration (Track R / Track F)

**Function.** Make the Track R / Track F split permanent (AGENTS.md "Dual development"), reconcile Phase V (C6-01..09), write one
machine-readable configuration per baseline (`results/phase6_config_R.json` WF-R-P6.0; `results/phase6_config_F.json` WF-F0-P6.0 and the
F1 reference WF-F1-P6.0), start the fictional technology register (`data/technology_register.toml`, FT-00..08, noncanon), integrate the
Track F systems in isolation (power district, H6a, R5-A + the 1500 K FT-03 section, electrical, ECLSS 7 vs 8, logistics), re-couple mass,
tanks, CoM and acceleration, and continue OpenMC in Track R (void verification n/γ, deep-penetration benchmark, side scatter, transmission
with weight windows, species heating).
Run order after Phase V: `phase6/rad6.py [particles]` (OpenMC env; RAD_RUNS for the statepoints), `phase6/study6.py`, then
`/snap/bin/blender -b assets/wayfarer/WF_WAYFARER_001.blend --python make_review6.py -- --render`, then `build_report.py`.
**Fixed constraints.** Production geometry, canon and Drive unchanged; the 20 % HOT rule; Track R calculations are never softened; the
900 K L1 rejection is not closed by choosing direct conversion (it moves the losses into the hot loop, ledgered).
**Findings.** The two Phase V fictional figures were two configurations (42 t apart). Continuous L1 in a proactive burn is ~14 MW, not 271.5;
the 210 MW heat-pump rating stays installed. F1 frees ~13 m of hot length (950 K reject) and lifts HOT headroom from 58 MW to ~1 GW, which
is what lets reactive defense with direct conversion fit. ECLSS: 7 units pass 9 of 10 cases (8 pass all). Preheat is hours, not days.
Fictional F1 departs ~8.2 kt nominal and still needs ~20 m more tank length (alternatives go to the 3D integration stage B).
**Open.** DR6-01..06 on the page; shielding, crew dose and installed cryocooler rating (DR5-08); hot-loop boundary in Track R.

## Phase V (owner brief 2026-11-27 13:53Z): thermal network optimisation and convergence

**Function.** Fix one configuration (N2-R4a-P5.0, `results/phase5_config.json`), correct Phase IV (C5-01..10), study the hot loop as a
sectionalized network (H6) with pressure- and creep-based walls, radiator zoning (R5-A..E), electrical transient, 3-D OpenMC in the ship
frame, coupled mass (CIRC-001 through `mass_model.coupled_mission(s, extra_end_kg)`, production operating_point unchanged), ECLSS-G1, LOG-G1, allocation,
missions; keep a RESEARCH and a FICTIONAL baseline apart (owner rule 2026-11-27, dual philosophy).
Run order after Phase IV: `phase5/rad3d.py` (OpenMC env, optional; ~2 min for 3 M particles), `phase5/study5.py`, then
`/snap/bin/blender -b assets/wayfarer/WF_WAYFARER_001.blend --python make_review5.py -- --render`, then `build_report.py`.
**Fixed constraints.** 20 % HOT rule kept; production geometry, canon and Drive unchanged; Li a study coolant; no core design.
**Findings.** Hot loop is a structural problem: ~1990 K inlet for an 1800 K mean surface, ~2 MPa at the aft end of a 1.36 g burn, walls
dominate (H6a ~2.3 kt nominal at 15 MPa allowable; ~0.55 kt with a 100 MPa composite boundary, the fictional assumption). Only 750 K
cross-strapped L2 sections keep the HOT rule (R5-A); R5-C (bulkhead emitter) irradiates the He-3 tanks; R5-B conflicts with the fixed
aft edge. 3-D OpenMC: frame verified (void kernel ratio 1.01); structure scatter around the shadow cone delivers ~19 % of the unshielded
tank heating (~160 W for three units vs 118 W lift). Research baseline departs ~14 kt nominal and overfills the tanks x2; fictional ~7.9 kt.
**Open.** DR5-01..08 on the page; L1 900 K reject (incl. the canon burn heat pumps) still has no radiator.

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


## Consolidation WF-F1-C1.0 (2026-11-28)

Owner brief 2026-11-28 09:15Z: the 19 systems are the working fictional architecture; consolidate instead of researching. `integration3d/consolidate.py`
iterates dry mass, coupled propellant, the T-A stretch, cryo and radiators to one configuration (`results/i3d_consolidated.json`) and writes the
systems-to-structure interface SSI-1.0 (`results/i3d_structure_interface.json`) for PSA. Departure 8,655 t (CP4 8,573; the owner's
~8,671 t is a reference, not a target), propellant 5,468 t, T-A +20.70 m (CP1 18.21), ship 310.2 m.
DR-3D-01..04 implemented (FT-03 and FT-06 in the register v1.1, FT-07 MRU rating and provisional EXT-TA arm). WARM closes at 451 K on
its existing area; LOW gets forward tip extensions x 93.4-106.5, r 31.5-37 (the ring sweep limits them to 13 m) and runs at
316 K; HOT is not spent (aft shift would leave -0.54 GW at the reactive peak). The brief's LOW +76 kW was understated: CP4 mixed the cryo
input bases (934 kW installed vs 776 kW mixed); corrected need is 1.2 x (avionics + cryo reject). MRU: in-flight route r 2.9 clears everything
for the TAC; the reactor/IHX is a shipyard job after unbolting the sector-3 ride-through units and switchgear; twin rails az 255/285. Module 10
cannot slide forward past the retained buffers (yard extraction aft, or DR-C-05). Review view layers C1-C8 in `REVIEW_I3D.blend`; page
sections c0-c6. Owner questions DR-C-01..05; problems C-01..C-10; SSI disagreements SSI-D1..D3 stay with PSA.

## Closeout WF-F1-C1.1 and SSI-1.1 (2026-11-28)

Owner brief 2026-11-28 10:51Z: C1.0 (ec7c7a3) accepted as the working fictional architecture; DR-C-01..05 approved; bounded closeout, no new
research phase. `consolidate.py` now writes C1.1. Correction: C1.0 vessel masses summed to 5,378 t vs 5,468 t (bare-liquid need scaled, D2
162.4 instead of 175.2 kg/m3). C1.1 splits the mission propellant in the production B01 proportions, loads residual 1.5 % and boil-off reserve
0.5 % (carried unburned to the end mass) and sizes capacity with 3 % ullage (2 % expansion + 1 % vapour cushion): mission 5,736 t,
loaded 5,851 t, departure 9,078 t, T-A +25.45 m, ship 315.0 m; the larger farm raises
the cryo input, so LOW settles at 320 K (owner said ~316). He-3 at 3 K expands ~20 %/K (C-11). Shield 25.3 t is yard-only (C-13). EXT-TA
is a reusable aft rail + arm (FT-07); FT-09 (new) covers 451 K WARM machinery. Pickup-fault transfer: L2 tie >= 3 MW, transfer < 50 ms, buffer
bridge 82 MJ. SSI-1.1 adds the shared block (coordinates, dimensions, tanks, load cases LC-ENV/C11/CMB, keep-outs),
EXT-TA mounts, MRU rail end x 92.0, L2 station x 41.0 (owner), joint items J-01..03. With PSA Phase II H:hub:F1 (c3138d8, provisional +1,073 t)
the point moves to 13,193 t, +48.7 m, 338 m, 0.46 g: T-A holds it, but it does not
converge without the joint iteration I-01. Page section k0.
