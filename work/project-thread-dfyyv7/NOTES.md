# Deadship integration: design and Phase 0 (DS-000, DS-P0)

| Field | Value |
| --- | --- |
| Kind | Design study plus the authorized Phase 0 systems proof (no geometry, canon, Drive or deployment change) |
| Status | ACTIVE: Phase 0 and Phase 1 (DS-1 Scrubber tutorial) built and validated (2026-11-13), awaiting owner review; Phase 2 not authorized |
| Question | How should Deadship become part of the interactive Wayfarer so that it is enjoyable, teaches the ship's real systems and leaves a reusable systems foundation for the story? |
| Model base | `main` at c77026d (LOCO-003), branch `claude/project-thread-dfyyv7` |
| Report | [DEADSHIP_DESIGN.md](DEADSHIP_DESIGN.md) |
| Owner questions | DS-Q1 to DS-Q8 decided 2026-11-13; open items DS-O1 to DS-O6 in the report, section 12 |

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
