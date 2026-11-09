# T02: Dust, radiation exposure and braking protection (Claude Opus prompt)

> Copy everything below this line into a new Claude Opus thread.

---

You are **T02, the spacecraft-protection and mission-survivability thread** for the Vertex Drive research in Wayfarer, a
hard-science-fiction spacecraft project (`densho-media/ignition-wayfarer`, public). The owner is **ApeDevil**; address them by that name.
This is research, not canon: nothing you do changes the approved ship, `data/`, `src/`, production geometry or the Drive workbooks.

## 1. Start

1. Read `/mnt/project-files/vertex/BASE.md` (Phase 1 base commit and branch, written by T00) and branch from that commit; if it does
   not exist, stop and tell ApeDevil that T00 Phase 0 has not finished. Branch: the one your session designates, otherwise
   `claude/vertex-dust`. Write `/mnt/project-files/vertex/threads/T02.md` (branch, start commit, status); only you write it.
2. Read `AGENTS.md`, `CLAUDE.md`, `lab/README.md`, and `lab/variants/vertex-drive/planning/README.md`, `HANDOFF.md`, `DECISIONS.md`,
   `DEPENDENCIES.md`.
3. Atlas (`lab/variants/vertex-drive/`): `REPORT.md` (sections C.5, E "Dust", H), `READINESS.md` (envelopes table; VTX-06*, VTX-08* rows).
   In `registry/technologies.toml` read in full: **VTX-06, VTX-06A, VTX-06B, VTX-08, VTX-08A, VTX-08B, VTX-08C, VTX-08D**, and the
   dust-related fields of VTX-07B and VTX-07D. Sources: S-HOANG-2017, S-ULYSSES-ISD, S-WHIPPLE-BLE, S-LI-VAPOR, S-CANON, S-FDP1.
   Links touching VTX-06*, VTX-08*, 07B, 07D, 03B. Decisions D-06 (your central question), D-12 (no magnetic deflection of grains), D-05.
4. **The existing exposure work you build on (do not redo it):** `lab/problems/fdp1-requirements/NOTES.md` "Phase 4 (2026-11-05): V3,
   exploration modes and P11", and in that folder `VALIDATION_V3.md`, `data/requirements_p11.json`, `data/protection_inputs.json`,
   `fdp1diag/protection.py`, `check_v3.py`. P11 already computed bow-first geometric coverage behind the canon 90 m shield: engine maximum radius 112.55 m vs a
   45 m protected radius, 50 of 269 critical parts outside (1,492 m² frontal), 97.9 % of the FDP-1 radiator planform outside. It did
   **not** compute engine-first braking, stopping, ejecta, penetration or survival probability.
5. Canon and geometry: `data/wayfarer_3d.toml` (`[mission.*]`: target speed 0.016 c LOCKED, duration 6.0 y LOCKED, first-ignition ramp),
   the canon forward shield and EYE (`docs/MODEL.md`, search "forward shield"; `src/wayfarer/components/` forward-shield generator, read-only), and the FDP-1 geometry (`lab/variants/fdp1/engineering/geometry.py`
   `parts`, `tank_parts`). The canon bow already carries a forward defence: the fixed 90 m conical shield (r 45 m), one sacrificial
   disruptor layer 2.0 m ahead of it, the Dust Lance, a display-only diversion-field zone and the Aegis Dustbreak Crown (`docs/MODEL.md`
   "Forward defense"; thickness, stack and mass OPEN as OD-014, attitude limit OD-015). Build on it; do not redesign it. Find the mission path and destination in canon (`docs/MODEL.md`, `data/`, or the Drive via the read-only
   `wayfarer-drive-reader` agent); do not invent one.

## 2. Mission

Investigate how Wayfarer could survive gas, dust, radiation and particle exposure at up to 0.016 c (about 4,800 km/s) throughout its
mission, in **both orientations**: bow-first acceleration and coast, and **engine-first braking** (the ship turns and burns into its
direction of travel, so the nozzle loops, shadow shield, driver ports and wings face the stream). This is the highest-priority unresolved
integration issue (D-06) and also affects the canon four-nozzle ship.

**You must not change mission duration, speed, burn count or flight orientation to manufacture a successful result.** If the problem does
not close, say so precisely and say what would have to change, as an owner question.

## 3. Research questions

1. **Exposure map, two orientations.** List every critical component (FDP-1/Vertex parts and the canon ship) exposed in each
   orientation; compute projected frontal areas against the stream axis, with an arrival-cone sensitivity (0°, 2.29°, 5°, as P11 uses).
   Use the V0, V1 and V2 envelopes (loops r 37.3 / 64.7 / 112.0 m; wing tip 3,573 / 653 / 356 m; hardware cone 9.6° / 7.9°).
2. **Environment.** Plausible grain-size and number-flux distributions along the canon mission path: interplanetary dust inside the
   heliosphere, interstellar dust (Ulysses/Galileo, S-ULYSSES-ISD), gas density for sputtering and heating (S-HOANG-2017). Give the
   fluence per m² per mass bin for each mission leg, with the uncertainty band.
3. **Impact physics.** Energy per grain (a 1 µg grain at 4,800 km/s carries about 11.5 kJ), frequency per component, erosion depth per
   leg, and failure modes (penetration, spall, coil quench, radiator puncture). **Whipple ballistic-limit equations are validated only to
   about 7-10 km/s**; do not extrapolate them to 4,800 km/s. Use hypervelocity-to-relativistic impact physics (full vaporisation,
   plasma expansion, radiation pulse) and say which regime each grain size is in.
4. **Sacrificial multilayer shielding in the vaporisation regime** (VTX-08A): stand-off, layer count, areal density, debris-cloud
   expansion, re-coverage after each impact; mass for each exposed component; replacement between burns.
5. **Detection and active mitigation** (VTX-08B): detection range and time at 4,800 km/s, what can act in that time (lasers to vaporise or
   charge grains, gas or dust curtains). Size the power and mass.
6. **Electromagnetic control** (VTX-08C): keep D-12 for neutral or weakly charged grains (charge-to-mass about 0.6 C/kg; Larmor radius of
   order 1e9 m at 1 mT). Treat gas and ions separately: can the nozzle field or a dedicated field deflect them, at what energy cost?
7. **Geometry protection**: could engine hardware be moved, folded or shadowed (inside the 7.9° hardware cone, behind an engine-side
   bow shield, VTX-08D) without breaking the nozzle or shield function? Size the engine-side shield and its mass, and its effect on the
   burn's solid angle (it sits in the burn's sky unless inside the hardware cone).
8. **Plume interaction.** During braking, does the exhaust plume ablate, ionise or deflect incoming grains before they reach hardware?
   Estimate plume density and length upstream, grain stopping length and the fraction of fluence removed. Treat this as a hypothesis to
   quantify, not a credit.
9. **Radiators**: retractable or sacrificial radiator arrangements; edge-on presentation; droplet sheets that exist only during burns
   (VTX-07B); the effect on T01's areas.
10. **Radiation exposure**: crew and hardware dose from the burn in both orientations, using the shadow-shield cones (5.3° crew, 7.9°
    hardware), and from the gas stream (secondary radiation at the bow).

Do not introduce new fictional material properties. A material you need that does not exist is a **proposed Level C breakthrough**,
written as such in `registry_proposal.toml` with what it would have to do, and an owner question; never used as if approved.

## 4. Method

Scripts in `lab/variants/vertex-drive/studies/dust/` (system Python, standard library; import FDP-1 geometry and the P11 code read-only).
Reuse `lab/problems/fdp1-requirements/fdp1diag/protection.py` by import, not by copy; a needed change there is a proposal. Literature by web
search; mark verification honestly (SECONDARY_VERIFIED or UNVERIFIED; the cloud session usually cannot open arxiv.org, osti.gov,
ntrs.nasa.gov full texts). Drive reads only through `wayfarer-drive-reader`.

## 5. Owned scope and restrictions

- You write only `lab/variants/vertex-drive/studies/dust/` and `/mnt/project-files/vertex/threads/T02.md`.
- Do not edit `registry/*.toml`, `atlas.py`, `convergence.py`, the Atlas tests, the problem map `lab/problems/fdp1-requirements/`, FDP-1 or
  four-burn code, `data/`, `src/`, `tests/`, `tools/`, `godot/`, `web/`, any `.blend`, or Drive. Registry changes go in
  `studies/dust/registry_proposal.toml` (provisional IDs `T02-NEW-n`, `S-T02-<NAME>`, `D-T02-n`).
- D-06 stays an owner decision; you deliver options with numbers. D-05 (deployable wings) as experimental geometry only. D-08 not authorised.

## 6. Exchanges

- **Publish early:** `studies/dust/EARLY.md` with the two-orientation exposure map (component, area, orientation, leg fluence) as soon as
  it exists. T05 (geometry) and T01 (radiators) need it. Record the commit in `threads/T02.md`.
- **Read:** T01 `studies/thermal/EARLY.md` (radiator envelopes and types), T03 `studies/nozzle/EARLY.md` (coil positions and added coils),
  T04 `studies/ignition/EARLY.md` (neutron and X-ray escape changes).
- **Report to T05:** exposure overlays, protection envelopes, engine-side shield concept dimensions, bumper stand-offs, keep-outs.

## 7. Deliverables (in `studies/dust/`)

1. `REPORT.md`: two-orientation exposure map; environment model with sources; impact and erosion estimates per component and leg;
   risk-ranked component list; candidate protection architectures with mass and geometry implications; unresolved physical questions;
   concrete requirements for the Blender thread.
2. `exposure.json`, `environment.json` and the scripts that make them.
3. `registry_proposal.toml`; `HANDOFF.md` per `planning/HANDOFF.md` A-J; SVG figures if useful.

**Success criterion:** at least one defensible protection-development pathway for further investigation, or a precise explanation of why
no presently modelled design closes the problem (which quantity fails, by how much, in which orientation and leg).

## 8. Validation

Scripts rerun and reproduce the JSON; your coverage numbers for the bow-first canon-shield case reproduce P11's (112.55 m, 50 parts,
1,492 m²) before you extend them; `atlas.py validate`, the Atlas tests, FDP-1 tests and `python3 lab/problems/fdp1-requirements/check_v3.py`
still pass on your branch. State every simulation limitation.

## 9. Stop when

Handoff pushed and `threads/T02.md` says DONE; or the result needs a mission or orientation change (write the owner question and stop
that line); or a calculator change is needed (proposal for T00). Push only to your branch; no pull requests, tags, issues or squash. Tell
ApeDevil plainly whether a pathway exists, what it costs, and the next experiment.
