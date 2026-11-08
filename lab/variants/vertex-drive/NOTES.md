<!-- lab entry -->
| Lab entry | |
| --- | --- |
| Kind | Variant |
| Status | ACTIVE |
| Question | Which technologies could make a pulsed fusion Vertex Drive credible for Wayfarer, what would each need, and how far do they get the ship? |
| Model base | main 279a612 (FDP-1 calculator as on main) |
| Salvaged from | claude/project-thread-dqcppt, 2026-11-08 |
| Open owner questions | D-04 idle H2 vessels; D-05 deployable warm wings; D-06 engine-first braking through dust; D-07 open Fiji lattice parameters; D-08 Vertex vs canon drive topology; D-09 nozzle MHD study; D-10 Blender blockout; D-11 Drive record. |
| Review | REPORT.md, ATLAS.md, READINESS.md (this folder) |

# Vertex Drive Technology Atlas: notes

## Function

The Atlas is a research system, not a design. It records every candidate technology for a "Vertex" development of Wayfarer's pulsed
D-3He drive (FDP-1) as a structured record with stable ID, physics, ancestry, limitations, breakthrough needed, dependencies, materials,
three classifications (credibility, physics verdict, research and canon status) and 3D readiness. It then runs three generations of the
drive through the existing FDP-1 calculator to see how far the plausible technologies take the ship against the mission benchmarks.

## Fixed constraints

- Canon is unchanged: the LOCKED one-core, four-nozzle Fiji Drive, the production geometry, the Drive workbooks, the mission (6.0 y,
  0.016 c) and the canon Fiji properties. Vertex is non-canon; every record starts NON_CANON, except the canon Fiji capability card
  (VTX-02A), which records canon and adds nothing.
- Fiji gets exactly its canon card: amplification of an applied field up to x30, slow and temperature-set; stabilisation; no energy
  creation, no heat sink, no fast driver, no light bending. The FDP-1 calculator gives it no numeric credit, and the Atlas keeps that.
- No efficiency is raised without a technology record that would earn it, and each raised value is labelled TARGET, a requirement.
  Benefits that no model computes (collimation by magnetic shear, magnetised gain, vapour curtains) are UNKNOWN and only appear as
  sensitivity bands.
- Every earlier finding of the 2026-11-08 integration study is kept as `prior_finding` and not rewritten; the reopened mechanisms
  (VTX-03 swirl, VTX-04 liner) keep their earlier results.

## Unknowns

The largest, in order of what they would change: target gain of magnetised D-3He (the cliff of the whole design); nozzle efficiency of
a pulsed beta >> 1 magnetic nozzle, plain or shaped; the energy per target in the target factory (house load); how much of the warm
load can run above 600 K; how the ship survives dust at 0.016 c, especially during engine-first braking.

## Design freedom

Which technologies enter which generation; the record schema; the priority weights. The calculators and the canon are fixed.

## Decisions

See `registry/decisions.toml` (rendered in ATLAS.md). Technical conclusions D-01 (helical = shear only, balanced), D-02 (no tamper at
mission ve with the current target model), D-03 (fast control on the target and driver side), D-12 (no magnetic dust deflection).
Owner approvals D-04 to D-11 are open.

## Findings

See REPORT.md.
