<!-- lab entry -->
| Lab entry | |
| --- | --- |
| Kind | Study |
| Status | PROMOTED into main (Deadship Phases 0-3, owner-accepted 2026-11-16); kept as the design record and its gate and sensitivity studies |
| Question | How should Deadship become part of the interactive Wayfarer so that it is enjoyable, teaches the ship's real systems and leaves a reusable systems foundation for the story? |
| Model base | main c77026d |
| Salvaged from | claude/project-thread-dfyyv7 @ 58631f9, 2026-11-16 |
| Open owner questions | Phase 4 PARKED (REPORT.md §57); DS-O1, DS-O2; sourced electrical values, ring-cabin passive exchange and heaters (§51-§52) |
| Review | project files deadship_closeout_2026-11-15/ (playtest checklist REPORT.md §56) |

# Deadship integration: design, Phases 0-3 and the closeout

Full report: [REPORT.md](REPORT.md). The game code is in `src/wayfarer/` (`ship_ops.py`, `ring_services.py`, `shared_air.py`, ...),
`data/deadship/` and `godot/scripts/deadship/`. The studies here (`ds2_gate.py`, `ds2b_gate.py`, `ds2b_lens.py`, `ds2b_reconcile.py`,
`ds2c_tcc_gate.py`, `ds3_sensitivity.py`) run from the repository root and write their JSON next to themselves.

## Findings

Phases 2 (2A airflow, 2B Shared Air, 2C Borrowed Air) and 3 (Dark Bus) are technically complete and owner-accepted. The scenarios'
lessons and the ranking of their viable strategies are robust to the PROTOTYPE electrical values, but which strategies are viable
lives in narrow bands (converter >= ~37.5 kW, ship load <= ~16 kW per bus, battery and service window within ~10 % and ~6 h);
the ring cabins have no passive hull exchange or heaters yet (OPEN). Phase 4 (competitive Deadship, Hullrun) is PARKED.

**Function.** A survival-engineering game inside Explore Interior: diagnose, prioritize, cannibalize, improvise, stabilize.

**Fixed constraints.** Godot 4 Web runtime (`gl_compatibility`, Jolt), `WfInput` action registry and the browser-local profile, the
DOCKED package and rig as the only source of ship geometry, the canon statuses in `data/`, the walk's existing checks.

**Unknowns.** Whole-ship electrical load (`power.rating` OPEN), ECLSS internals and tolerances (OPEN), loop heat capacities and
Heat Debt (OPEN), degraded modes (OD-010 OPEN), the First Ignition accident's sequence (Tale).

**Design freedom.** Scenario content, the component taxonomy below the canon systems, interaction design, scoring, UI.

**Decisions taken here (proposals, reversible).** Recommend the hybrid path with Concept B first (Deadship aboard Wayfarer as a
station-run training simulation); a lumped, conserving system simulation (fidelity level 2) with canon parameters where they exist;
a Python reference stepper plus a GDScript runtime that must reproduce its checkpoints (the retired life-support simulator's
pattern); no TypeScript, WebAssembly module or backend.

**2026-11-13 (owner decisions applied).** Phase 0 built: ring A cabin CO₂ at the sector 3 ECLSS bay, Ops isolates or restores the
unit, the runtime reproduces the Python reference within a packaged tolerance. The DS-000 1.4 h clock used the usable-space allocation
(120 m³); the connected ring A gas volume is about 466 m³ (5.4 h target to control limit, six people, unit off). Three CO₂ tiers kept
apart: control limit (canon WORKING), degraded habitability and danger (PROTOTYPE references). Door-coupled compartments are the main
Phase 1 modelling step.

**2026-11-13 Phase 1 (authorized 14:09Z).** DS-1 "Scrubber" built at `#interior-deadship`: the model gained independent mode / fan /
spare fields with an operation table and refusals; the scenario lives in `data/deadship/` and owns no engineering value; a 6 h
stability watch on the same model; real-input browser checks (`web_check.py --part training`). Compartments investigated and kept as
one ventilated volume (doors normally closed, no door claim); connectivity is Phase 2's first step. Report sections 17 to 21.
