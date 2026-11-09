# Vertex Blender blockout (T05): Stage A notes

| | |
| --- | --- |
| Kind | work in progress (experimental variant geometry, NON-CANON) |
| Status | Stage A delivered 2026-11-09; Stage B (D-10) not authorised |
| Branch | `claude/project-thread-ctwplp`, from `a1c8246` (T00 Phase 4, branch `claude/project-thread-9rsgog`) |
| Inputs | `lab/variants/vertex-drive/planning/T05_HANDOFF.md` (authoritative configuration list), `planning/T05-BLENDER.md` (workflow), `planning/INTEGRATION_REPORT_PHASE4.md`, `results/convergence.json`, `READINESS.md`, thread studies T01-T04 |
| Owner direction | ApeDevil, 2026-11-09 (thread message): V4 principal, canon unchanged, V0 historical, V5 ideal-limit only, true scale, radiator alternatives, no canon/Drive/production change, no squash |

Files in this folder:

| File | Holds |
| --- | --- |
| `NOTES.md` | this page: function, fixed constraints, unknowns, design freedom, decisions, owner questions |
| `GEOMETRY_SPEC.md` | every component per generation: envelope, position, source, evidence status, who may change it; record coverage; interfaces |
| `RADIATORS.md` | the radiator-architecture review the owner asked for (point 4) |
| `COLLECTIONS.md` | collection tree, colours, overlay rules, custom-property schema |
| `CAMERAS.md` | camera and render plan |
| `PARAMETERS.md` | what each generation needs, from which file |
| `WORKFLOW.md` | the non-destructive build workflow for Stage B |
| `ISSUES.md` | engineering issues found by the Stage A screen (T05-ISS-001 ...) |
| `HANDOFF.md` | standard handoff A-J |
| `screen.py`, `screen.json` | the Stage A screening calculation (pure Python, about 12 s) |

## Function

A reproducible, non-destructive Blender comparison, at one true scale, of:

1. the canonical Wayfarer as built on `main` (four-nozzle Fiji drive), appended unchanged;
2. **Vertex V4**, the corrected research target and the principal experimental configuration (42,916 t);
3. **V0 (FDP-1)** as the historical comparison (20,760 t, HISTORICAL_CONDITIONAL: it needs a compression coupling of 2.1);
4. **V5** as an ideal-limit ghost only (19,442 t at coupling 1.0), never drawn as a target.

It shows what the calculation supports, places parametric placeholders where only an envelope exists, and keeps speculative
visualisations as labelled overlays. Its purpose is to find interferences and scale problems, not to make the ship attractive.

## Fixed constraints

- **Canon keep-outs** (values from `data/wayfarer_3d.toml` through `src/wayfarer/layout.py`, `screen.json` → `canon`):
  body X −144.75 to +144.75 m; habitat rings A and B at X 97.30 and 103.30 m, outer radius 30 m, sweep ±2.15 m; primary dock
  X 131.65 m at azimuth 195°, service dock az 315°, EVA airlock X 134.10 m az 50°; tank farm X 109.25-137.85 m; hot blades
  X −133.25 to +48.90 m, r 6.5-37 m, az 30/150/270°, 1,800 K; forward shield r 45 m. The FDP-1 notes and `T05-BLENDER.md` give the
  dock at X 99.40 m; that is the pre-pass-7 position (T05-ISS-006).
- **The canonical ship is never altered.** It is appended with its `GEN_*` collections, numbered groups and properties. Comparison
  scenes hide superseded parts (four-nozzle drive, idle H2 vessels in V4); they are never deleted.
- **True scale.** Every Vertex dimension is the calculator's (`results/convergence.json` plus a fresh FDP-1 solve with the same
  overrides). The radiators are drawn at their full calculated area: V4's warm wings reach a 10,128 m tip radius (20.3 km span).
  Physical area is never reduced for view factor or appearance (AGENTS.md).
- **V4 envelope** (`screen.json` → `generations.V4`): burn point X −249.1 m (stand-off 64.7 m aft of the shield aft face at
  X −184.4 m); loops r 56.0 / 97.0 / 168.1 m at X −216.8 / −249.1 / −346.2 m; hardware cone 5.50°, crew cone 4.98°; closure coils
  C1 X −188.3 m r 22.1 m and C2 X −199.6 m r 41.6 m; W2 wings at az 0/180°, X −178.75 to +88.0 m, 1,800 K band r 10-847 m, 628 K
  field r 847-10,128 m; drivers r 4.5 m; T-B tank stretch 275.4 m (110 vessels), so the bow assembly moves forward 275.4 m in the V4
  scene only. Whole V4 length X −346.2 to +420.1 m (766 m), against the canonical 289.5 m.
- **Rules from Phase 4:** no helix (show a sector clock), no half-size dense-compression nozzle, every V4 mass a lower bound (closure-coil
  structure 855-1,281 t, skirt, launcher, tritium store unbooked), dust protection drawn as alternatives, D-08 not approved.

## Unknowns (OPEN)

| Quantity | Why unknown | What Stage B draws |
| --- | --- | --- |
| Target-launcher length | 12-15 km/s cryogenic launcher does not exist; 10-20 m at 1e5 g (T01) | PROTOTYPE barrel 20 m on the bore axis, labelled UNKNOWN length |
| Fast-ignitor beam-line volume | no design (T04) | PROTOTYPE 1 m tube beside the target path |
| Closure-coil structure | virial bound only, 855-1,281 t, GN hoop and inter-coil loads (T03) | coil tori at T03 positions; struts drawn, unsized |
| Tritium store | 43-144 kg per mission, no containment design (T04) | PROTOTYPE 2 m sphere in the equipment module, CONCEPTUAL |
| Wing deployment and dynamics at 10 km | no structural model; screen: 6.4 MN chord couple at peak acceleration | wing in its deployed state only, stowed state as an outline |
| Hot-band placement versus rings and C1 | the calculator books area only | T05-ISS-001/002: Stage B draws the calculated layout plus the chordwise-graded alternative |
| Destination and heading | D-15, D-17 | all three dust options side by side |

## Design freedom (PROTOTYPE)

Where the hot band sits along the chord (area fixed); wing azimuth pair (0/180° is the calculator's, 90/270° conflicts with the 270°
blade); split of the warm field into circuit bands (proportions from T01 `ledger.json`); strut and spar topology; closure-coil strut
topology; launcher, ignitor and tritium-store placement inside the equipment module; replaceable-sector split lines (six per loop,
T02) and the sector clock (45° loop to loop); skirt cone extent inside the T02 envelope.

## Decisions (Stage A, recommendations only)

1. V4 is drawn from a live FDP-1 solve with the V4 overrides, never from figures typed into the build (as `convergence.py` does).
2. Tank layout T-B (the calculator's choice) is the default for V4; T-A (stretch aft) is an outline alternative.
3. Hot-band placement: draw the calculated layout and, beside it, the chordwise-graded layout of `RADIATORS.md` §4 (same area),
   because the calculated one puts 1,800 K hardware 7 m from ring A (T05-ISS-001).
4. The V4 wing is drawn as a tin droplet sheet frame (the V4 mass basis, 0.5 kg/m², D-05), with a panel version as an alternate.
5. Nothing V1 or V2 is drawn (historical conditional, energy-inconsistent).

## Open owner questions

- **D-10 Stage B:** start the Blender blockout on this plan? (owner)
- **Hot band:** accept chordwise grading (hot band aft of X 48.9 m, as canon's blades) as a Stage B requirement? (owner, with T01)
- **Review form:** the review `.blend` plus PNG renders; a GitHub Pages compare view would need a `tools/story.py` change outside T05 (T00).
