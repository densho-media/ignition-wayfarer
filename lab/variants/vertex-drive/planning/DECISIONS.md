# Vertex threads: owner approvals and blockers

Only ApeDevil approves. A thread or the coordinator may recommend; a recommendation, a passing test or a study result is never an
approval. Decision texts are in `../registry/decisions.toml`; this page says how the threads treat each one.

## Owner rulings, 2026-11-09 (ApeDevil, T00 launch message)

| Decision | Ruling | Effect on the threads |
| --- | --- | --- |
| D-T00-1 | **Approved.** Lab tests stay outside ordinary CI; the complete relevant lab validation is required before any integration | T00 runs `atlas.py validate`, the Atlas, FDP-1 and four-burn tests at every integration and records them in `MERGE_READINESS.md` |
| D-PLAN-1 | **Approved.** T03 may run analytical, vacuum-field, field-line and test-particle studies without D-09 | T03 proceeds on those methods |
| D-09 | **Not approved** (full MHD/PIC) | no self-consistent MHD or PIC run; T03 may write the study plan only |
| D-10 | **Approved in principle**, strictly non-destructive and only in isolated experimental files; modelling starts only after T00's baseline exists and T05 has reviewed its initial geometry requirements | T05 Stage A (requirements review) first; Stage B only in `work/vertex-blender/` files, never in `assets/` or a generator; the registry entry stays OPEN until Stage B starts |
| D-11 | **Not approved** | no Google Drive changes by any thread; Drive reads only |
| D-08 | **Not approved** | no canonical engine replacement; the canon four-nozzle Fiji Drive stays |

The registry (`registry/decisions.toml`) keeps D-08 to D-11 `OPEN`; T00 records these rulings there at Phase 4 integration, with the
date, so the generated Atlas pages change once.

## Owner decisions carried from the Atlas

| Decision | Question (short) | Handling in this plan | Threads | Blocks |
| --- | --- | --- | --- | --- |
| D-04 | Keep the three idle canon H2 vessels and the hydrogen low gear? | Preserve both options; T01 reports V1 with and without; T04 argues which mission phase (if any) needs the low gear | T01, T04 | nothing in research |
| D-05 | Allow deployable warm radiator wings? | Research and draw as experimental geometry only (`VAR_VERTEX_*`) | T01, T02, T05 | adoption into any design |
| D-06 | How does Wayfarer survive engine-first braking at 0.016 c (also the canon ship)? | **Highest-priority unresolved integration issue.** T02 delivers options with numbers; no mission, speed or orientation change to make it close | T02 (lead), T01, T03, T05 | any Vertex adoption (D-08) |
| D-07 | Which open Fiji lattice parameters does canon fix? | Do not invent or lock values; any added Fiji property is a labelled Level C proposal | T03, T04, T06 | Fiji-credited results |
| D-08 | Adopt Vertex instead of the canon four-nozzle Fiji Drive? | **Not authorised.** No thread proposes adoption; canon ship unchanged | all | canon change |
| D-09 | Authorise a pulsed-plasma MHD or hybrid-PIC nozzle study? | T03 prepares the study plan and runs only vacuum-field, test-particle and analytic work; a self-consistent MHD/PIC run needs approval | T03 | resolving VTX-03's sign |
| D-10 | Authorise the Vertex Blender blockout in `work/`? | T05 Stage A (specs) proceeds; Stage B (any Blender geometry) only after approval | T05 | all 3D work |
| D-11 | Record Vertex in the Drive workbooks as a non-canon line? | No Drive writes; Drive reads only through `wayfarer-drive-reader` | all | Drive records |

Technical conclusions D-01 (helical = magnetic shear only, balanced), D-02 (no tamper at mission ve with the current target model),
D-03 (fast control on the target/driver side), D-12 (no magnetic deflection of grains) stand unless a thread challenges one with
evidence in its `registry_proposal.toml` (T03: D-01, D-03; T04: D-02; T02: D-12).

## Process approvals

| Gate | Needed before | Note |
| --- | --- | --- |
| Launch of T00 | any thread starts | the project coordinator launches threads; this package launches nothing |
| Launch of T01-T06 | Phase 1 | after T00 publishes `/mnt/project-files/vertex/BASE.md` |
| "squash" for a named branch | anything reaches `main` | per branch; "looks good" is not a squash |
| Shared calculator change | editing FDP-1, four-burn or `convergence.py` physics | written integration proposal, then ApeDevil |

## Proposed for the owner by this plan (both approved 2026-11-09, see above)

| ID | Question | Recommendation | Why |
| --- | --- | --- | --- |
| D-T00-1 | Should lab tests (Atlas, FDP-1) run in CI? | No; keep them the manual T00 integration gate | AGENTS.md and `lab/README.md` keep CI from reading `lab/`; T00 raises it only with a concrete failure CI would have caught |
| D-PLAN-1 | Is the D-09 boundary right: vacuum-field, test-particle and analytic nozzle work allowed without D-09, self-consistent MHD/PIC only with it? | Yes | Lets T03 answer the brief's analytical questions without pretending to a high-fidelity simulation |

## What must be decided before implementation

- **Before any Blender geometry:** D-10.
- **Before any high-fidelity nozzle simulation:** D-09.
- **Before any Vertex hardware is treated as part of a design (not a comparison):** D-05 (wings), D-06 (braking dust), D-04 (H2 vessels),
  then D-08 (topology).
- **Before any Drive record:** D-11.
- **Before anything reaches `main`:** ApeDevil's "squash" for that branch.
