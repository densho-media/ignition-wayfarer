# Deadship integration: research and design (DS-000)

| Field | Value |
| --- | --- |
| Kind | Design study (documentation only; no geometry, data, code or deployment change) |
| Status | ACTIVE, awaiting owner review |
| Question | How should Deadship become part of the interactive Wayfarer so that it is enjoyable, teaches the ship's real systems and leaves a reusable systems foundation for the story? |
| Model base | `main` at c77026d (LOCO-003), branch `claude/project-thread-dfyyv7` |
| Report | [DEADSHIP_DESIGN.md](DEADSHIP_DESIGN.md) |
| Owner questions | DS-Q1 to DS-Q8 in the report, section 12 |

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
