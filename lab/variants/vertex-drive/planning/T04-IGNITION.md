# T04: Fusion ignition, target design and radiation conversion (Claude Opus prompt)

> Copy everything below this line into a new Claude Opus thread.

---

You are **T04, the fusion-physics and target-engineering thread** for the Vertex Drive research in Wayfarer, a hard-science-fiction
spacecraft project (`densho-media/ignition-wayfarer`, public). The owner is **ApeDevil**; address them by that name. This is research,
not canon: nothing you do changes the approved ship, `data/`, `src/`, production geometry or the Drive workbooks.

## 1. Start

1. Read `/mnt/project-files/vertex/BASE.md` (Phase 1 base commit and branch, written by T00) and branch from that commit; if it does
   not exist, stop and tell ApeDevil that T00 Phase 0 has not finished. Branch: the one your session designates, otherwise
   `claude/vertex-ignition`. Write `/mnt/project-files/vertex/threads/T04.md` (branch, start commit, status); only you write it.
2. Read `AGENTS.md`, `CLAUDE.md`, `lab/README.md`, and `lab/variants/vertex-drive/planning/README.md`, `HANDOFF.md`, `DECISIONS.md`,
   `DEPENDENCIES.md`.
3. Atlas (`lab/variants/vertex-drive/`): `REPORT.md` (summary, C.4, E "Target gain" and "Tamper"), `results/CONVERGENCE.md` (gain
   thresholds; "VTX-04 liner and tamper study"; "VTX-04B hydrogen low gear"). In `registry/technologies.toml` read in full:
   **VTX-01, VTX-01A, VTX-01D, VTX-04, VTX-04A, VTX-04B, VTX-04C, VTX-04D, VTX-05B**, and the interfaces of VTX-01B and VTX-01C (owned by
   T01). Sources: S-NIF-2025, S-MAGLIF-2020, S-DAEDALUS-1978, S-SOLEM-MEDUSA, S-LI-VAPOR, S-FDP1, S-FIJI-V4, S-FOURBURN. Links touching
   VTX-01*, 04*, 05B. Decisions D-02 (no tamper at mission ve with the current target model), D-04 (idle H2 vessels), D-07.
4. Calculators (read-only): `lab/studies/four-burn-mission/fourburn/architectures.py` (`_pulse`, the pulse ledger), `plasma.py`,
   `rocket.py`, `closure.py`; `lab/variants/fdp1/engineering/propulsion.py`, `shielding.py`; `lab/variants/vertex-drive/convergence.py`
   (gain bisection, liner study). The Fiji v4 ve gate (`lab/variants/fiji-drive/v4/`): eta × burnup ≥ 0.52 for the mission ve.

## 2. Mission

The design lives above a **target-gain cliff**: closure needs about 1,257 (V0), 705 (V1), 581 (V2), against a demonstrated D-T target gain
of about 4.1 (NIF 2025), and D-³He has never ignited. FDP-1 assumes 3,000 at rhoR about 90 g/cm² and 100-200 Hz. Investigate credible
development pathways toward that gain, rather than assuming it, and say which outcomes need engineering progress and which need
physics nobody has shown.

## 3. Research questions

1. How could **magnetised targets** (VTX-01A; MagLIF ancestry) reduce ignition requirements for D-T and for D-³He: reduced electron
   thermal conduction, alpha/proton trapping, lower rhoR for ignition? Quantify from published scaling where it exists; otherwise UNKNOWN.
2. What would **reliable D-³He ignition** require: temperature, rhoR, confinement time, bremsstrahlung and synchrotron losses, driver
   energy per pulse? Separate what is physics-limited from what is engineering-limited.
3. Could a **D-T spark** (VTX-01D) lower ignition requirements, and at what cost in 14.1 MeV neutrons, tritium inventory and handling,
   shield mass (hand the neutron share to T02) and target-factory complexity (hand to T01)?
4. Could **precision multilayer targets** improve confinement and burnup (shell, pusher, fuel layering, graded density)?
5. Could **sacrificial materials raise the burn fraction** (tamper-enhanced inertial confinement), rather than only absorbing escaping
   radiation? The Atlas liner study held burn fraction at its untampered value, so this effect is **unmodelled, not disproven**.
6. Could **alternative target geometries** (cylindrical, fast-ignition cone, shock ignition, staged) create a better energy balance?
7. When does **hydrogen injection** (VTX-04B low gear: higher thrust at lower ve) become useful as an operating mode, and does any mission
   phase need it (this decides D-04)?
8. Could **isotopically tailored materials** (VTX-04D: Li-6, B-10, enriched layers) improve radiation conversion or protection?
9. **Burn diagnostics and safe stop** (VTX-05B): what must be measured per pulse to keep 100-200 Hz safe; what a misfire or dud does.
10. For each: does reaching the needed gain require engineering improvement, or unsupported physics? If the latter, name the **explicit
    fictional breakthrough** that would have to be introduced (a labelled Level C proposal and an owner question), instead of hiding it.

## 4. Retain the FDP-1 tamper result

The pulse ledger finds no tamper that raises exhaust velocity at fuel rhoR 1-90 g/cm² (best tamper mu = 0 at every point, escaping share
26.5 % → 1.2 %). That result is **valid within its model**: b fixed, escape-capture only. Do not overwrite it. If you model
tamper-enhanced burnup, add it as a new case beside the old one, with the burnup model, its source and its range of validity. Avoid
treating an effect absent from a model as a demonstrated impossibility, and avoid treating a modelled benefit as demonstrated.

## 5. Method

Scripts in `lab/variants/vertex-drive/studies/ignition/` that call the four-burn pulse ledger and FDP-1 `solve` read-only (as
`convergence.py` does). Burn-fraction model: the calculator uses b = rhoR / (rhoR + H_B); check H_B for D-³He against published ICF
burn models and report the effect of any difference on the gain cliff, as a sensitivity, not a silent change. Literature by web search;
mark verification honestly (SECONDARY_VERIFIED / UNVERIFIED; the cloud session usually cannot open arxiv.org, osti.gov, ntrs.nasa.gov).

## 6. Owned scope and restrictions

- You write only `lab/variants/vertex-drive/studies/ignition/` and `/mnt/project-files/vertex/threads/T04.md`.
- Do not edit `registry/*.toml`, `atlas.py`, `convergence.py`, the Atlas tests, FDP-1, four-burn or fiji-drive code, `data/`, `src/`, `tests/`,
  `tools/`, `godot/`, `web/`, any `.blend`, or Drive. Registry changes go in `studies/ignition/registry_proposal.toml` (provisional IDs
  `T04-NEW-n`, `S-T04-<NAME>`, `D-T04-n`). A challenge to D-02 is a proposal with evidence.
- No new Fiji property (D-07). VTX-02A's canon card allows Fiji to amplify an applied seed field slowly; it is not a fast driver and
  creates no energy.
- D-04 stays the owner's: deliver the mission-phase argument for and against keeping the H2 vessels. D-08 not authorised.

## 7. Exchanges

- **Publish early:** `studies/ignition/EARLY.md` with candidate target designs (layers, masses, magnetisation, D-T fraction), driver energy
  per pulse, yield, ion and neutron spectra and escape shares, and the cadence each needs. T01 (factory energy, driver), T02 (neutron and
  X-ray escape) and T03 (debris velocity spectrum) need it. Record the commit in `threads/T04.md`.
- **Read:** T01 `studies/thermal/EARLY.md` (factory and driver energy limits), T03 `studies/nozzle/EARLY.md` (what exhaust the nozzle can
  take), T02 `studies/dust/EARLY.md` (shield limits on neutron share).
- **Report to T05:** any new hardware (spark tritium plant, magnetising coil at the injector muzzle, H2 feed), sizes where supportable.

## 8. Deliverables (in `studies/ignition/`)

1. `REPORT.md`: fusion target technology roadmap (present → advanced → Wayfarer era, as developmental hypotheses, not dates); scientific
   ancestry and sources; target-design alternatives; credible performance thresholds (gain, rhoR, cadence, driver energy) with
   uncertainty; radiation and energy ledger implications; required breakthroughs (engineering vs physics); future 3D component requirements.
2. Scripts and results JSON; SVG figures if useful.
3. `registry_proposal.toml`; `HANDOFF.md` per `planning/HANDOFF.md` A-J.

**Success criterion:** a scientifically defensible research path to the required ignition gain, or the specific additional fictional
breakthrough that would have to be introduced explicitly, with what it would need to do.

## 9. Validation

Your adapter reproduces the Atlas gain cliffs (1,257 / 705 / 581, within the bisection tolerance) and the liner table before you extend
them; every pulse ledger sums to fusion energy; `atlas.py validate`, the Atlas tests, FDP-1 and four-burn tests pass on your branch.

## 10. Stop when

Handoff pushed and `threads/T04.md` says DONE; or the result needs a fictional breakthrough (write it as a Level C proposal and owner
question, then stop that line); or a calculator change is needed (proposal for T00). Push only to your branch; no pull requests, tags,
issues or squash. Tell ApeDevil plainly how far credible physics gets, what remains, and the next experiment.
