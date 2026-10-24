# Accessory owner review and handoff register (2026-10-24)

Scope: the accessory prototypes (EVA suit look, the nine drone-class bodies, the compact PLSS study, the standalone viewer) as reviewed by
the owner on 2026-10-24 and promoted to `main` as a standalone design-review capability. Everything here is **PROTOTYPE**. Being on `main`
neither installs the bodies in the ship, releases an engineering gate nor approves spacecraft hardware. Detail and evidence are in
docs/ACCESSORIES.md, and the images are indexed in this folder's README.

The register has three parts. **A** lists visual choices the owner can accept or reject in chat now; they need no Drive work and change
no engineering value. **B** lists engineering decisions that belong in the canonical Drive workbooks, where this repository only reads
the owner rows. **C** lists ship-session items: the accessory work only requests them.

## A. Visual decisions: approvable now

Owner decision 2026-10-24: the overall direction (GU drone family identity, distinct exterior crawler equipment, the GU suit look and
material hierarchy, the removable PLSS concept, the standalone viewer, playable EVA vs locked unsuited actions) is retained as **design
candidates, provisionally**; no item below is final. The glove grasp is acceptable as a display prototype. Accepting an item makes it the
visual direction for that accessory (`L4_VISUAL_CANDIDATE` accepted for look). It doesn't replace an L2 proxy, settle a size or rate any
part.

| # | Decision | Evidence | Note |
| --- | --- | --- | --- |
| A1 | GU drone family grammar: white vault, captive rail trucks, GU-SIF ends, GU stripe and plate | 01, 02-10 | the shape of GU-SIF is visual only; the standard is B2 |
| A2 | Functional identity of DR-EVA-01 (ORU guide frame, Brow inspection head), DR-EVA-02 (deflector, silvered faces, IR turret) and DR-EVA-03 (tool magazine, crew rail, tether anchor) | 21, 05-07 | sizes are unchanged and every body stays inside its envelope class; equipment ratings OPEN |
| A3 | Docking cradle look on review stands (pedestal, V-guides, umbilical, lamp, orange release) | 24 | review fixtures, not ship stations; ratings are B2/B5 |
| A4 | Suit fidelity: boot shells and toe cap, knee and elbow covers, layer finishes (textile, hard shells, removable PLSS modules, grips), touch-point wear | 20, 11, 12 | wear is a soft vertex colour, not a texture |
| A5 | PROTOTYPE lettering as placeholders: "GREAT UNION", the role line, "WF-Y155-EVA PROTOTYPE", "O2 / CO2 · SERVICE / COOL" | 20, 11 | text only, no emblem; owner Art / Fashion markings replace it |
| A6 | Glove grasp as a display pose and its close-up view | 22, 16 | the middle of the handle stays hidden inside the glove; grip force and glove torque OPEN |
| A7 | Viewer presentation: suit EVA actions playable, inherited crawl / climb / idle / walk / sit shown LOCKED and refused | 23, 25 | a labelling decision, not an approval of the suit's mobility; FLIGHT_EVA stays HOLD |
| A8 | Viewer layout (grouped class names, action / status table, status card) | 25, 18, 19 | presentation only |

## B. Engineering decisions: canonical Drive work

Nothing in the accessory work changes these. Each one needs an owner row (or its answer) in the named workbook before any value moves into
`data/` or a reference.

| # | Item | State | What the owner decides | Where |
| --- | --- | --- | --- | --- |
| B1 | **DGT-017** L2 interface gate before detailed meshes | HOLD. The bodies are isolated studies; the ship keeps its L2 proxies | release the gate for one class at a time, after B3 and B5 | S&E 54_DRONE_VALIDATION DGT-017 |
| B2 | **DGT-012** GU-SIF / cartridge standard | proposed visual interface | approve or replace it. Needs: latch preload under 1.5 g thrust (F_axial = m × 1.5 g0, m OPEN), contact rating for HIGH_POWER charge, mate / demate life, keying, gloved manual-release force, power-loss state, tests (docs/ACCESSORIES.md "GU-SIF") | S&E 54 DGT-012 and DGT-SRC rows |
| B3 | **Drone / placeholder clearance** (corrected) | stowed body over its L2 proxy in height: DR-EVA-01 **+0.12 m** (0.48 vs 0.36), DR-EVA-02 **+0.03 m** (0.39 vs 0.36), DR-EVA-03 **+0.04 m** (0.46 vs 0.42), DR-EVA-04 +0.11 m (0.35 vs 0.24). All inside the S&E 51 envelope classes; interior classes fit | either grow the proxies after a placement and keep-out study or cap the body height; no automatic proxy change | S&E 51_DRONE_FLEET col G (classes); placement study by the ship session (C2) |
| B4 | **Rail section** | the candidate truck needs Ø60 mm rail, a 32 mm web corridor to 75 mm below the rail centre and a Ø206 mm swept envelope (rail_section.svg) | rail section, web spacing, mount pattern; loads and ratings OPEN | owner interface row via the TOC (S&E 15_MODEL_INTERFACES); ship geometry by the ship session (C3) |
| B5 | **Docking stations** | cradles exist only on review stands. Ship stations stay where the ship model puts them (DS-10 Brow docks, DS-11 SP-51 HOME docks, DS-13 spine track with operations HOLD, DS-14 aft cradles) | dock design: latch, charge and alignment ratings, cradle form at each DS position | S&E 53 (DOP-12 power OPEN) / 54 (DGT-012); positions by the ship session |
| B6 | **Suit-reference readbacks** | torso width, depth, circle, access classes, sweep and EVA coverage are identical to the committed references. Moved: height 1.921 / 1.835 m (+3 / +2 mm, boot shell standoff); EVA_SUITED projected area max 1.280 / 1.182 m² (+0.002 / −0.001), min 0.473 / 0.439 m² (side rescue handles). Inherited crawl / climb coverage FAIL unchanged and not suppressed | accept the readbacks (then the owner's `workflow.py eva` step refreshes the references) or reject the boot standoff; the projected area feeds the thermal case | S&E 44_EVA_SUIT_BLENDER (ASSET-08 boots), 45_EVA_ENGINEERING_CASES H-06 |
| B7 | Compact PLSS (ASSET-10) | **parked**. Baseline pack unchanged; every subsystem size is OPEN; the 0.90 m ring-B port is not an owner-required suited route (EVA-040) | nothing until EVA-051's calculation releases masses, capacities and energy | S&E 43 EVA-051, 44 ASSET-10 |
| B8 | All physics | OPEN: drone mass, power, speed, reach, payload, latch strength, thermal endurance; suit life support, glove torque, grip | values in owner rows; until then the tests keep them OPEN | S&E 51 / 53 / 54, 43 / 45 |
| B9 | FLIGHT_EVA | HOLD; every EVA scene is a training simulation | not opened by an animation or collision check | S&E 43 / 44 QA |

## C. Ship-session handoff (requests only; the ship session owns the geometry)

| # | Request | Evidence |
| --- | --- | --- |
| C1 | habitat rover deck-guide path near the DS-05/07 floor cassettes (the 40 mm review channel is provisional) | 17 |
| C2 | external drone placement and keep-out study with the corrected heights (B3) | 01, 21, B3 table |
| C3 | rail section, web spacing and mount pattern from the ship side (B4) | rail_section.svg |
| C4 | source map: add S&E `56_DRONE_TECH_ANCESTRY!A1:I9` next to `[sources.drone_fleet]` (shared source routing) | docs/ACCESSORIES.md request 4 |
| C5 | integration of an accepted class (after B1): its GLB, export bindings and dock anchors | not started; the accessory work edits no ship file |

State: no accepted reference, shared parameter, module registry or ship-runtime file was edited; the ship keeps its L2 drone proxies.
Before promotion the scoped quick pipeline reported 0 ship geometry changes against the accepted baseline.
