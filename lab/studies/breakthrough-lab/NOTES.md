<!-- lab entry -->
| Lab entry | |
| --- | --- |
| Kind | Study |
| Status | ACTIVE |
| Question | Which declared breakthroughs, and how few, make the Vertex drive close? |
| Model base | main 279a612; T00 calculators and results at 43fac75 (claude/project-thread-9rsgog), T05 results at c45ab4a (claude/project-thread-ctwplp), as versioned read-only imports |
| Branch | claude/project-thread-oul6bx, 2026-11-10 |
| Open owner questions | Which breakthroughs to select for experiment (none is selected); the spine stiffness criterion (decides whether the coupled ship closes); D-21 (MHD) and the 1D target implosion that would replace the two largest assumptions |
| Review | GitHub Pages /engineering/breakthrough-lab/ after a squash; preview screenshots in the project files review/engineering2_2026-11-10/ |

# breakthrough-lab: notes

Owner brief 2026-11-10 ("WAYFARER: Engineering 2.0 & Breakthrough Lab"): science-grounded speculative engineering. Calculate the ship
with hard science, find what stops it, declare the smallest precisely defined breakthroughs that would remove those limits, and
recalculate their consequences with the same method. Research only: no canon, `data/`, generator, Drive, lore or production geometry
change; T00 and T05 branches are read, never written.

## Function

The engineering record behind the website's Engineering 2.0 section (tools/story.py, tools/story_lab.py):

- `registry/weakest_links.toml`: the Weakest Links register (WL-001..WL-009). Its numbers are JSON pointers into the imported results,
  so the register restates no result. Ranking by four yes/no questions (lab.py `tier`, `ranked`), no weighted score.
- `registry/breakthroughs.toml`: the breakthrough registry (BT-001..BT-007). Level A/B/C is the PMDS and Atlas scale; evidence,
  development status and canon status are separate fields. Each computed breakthrough is a bounded parameter table (`levels`) over
  calculator inputs it declares (`modifies`), with a validity `limit`.
- `registry/scenarios.toml`: Layer A, the scientific reference (Vertex V3/V4 layout with every research target at its present-evidence
  value), the grid and the named scenarios.
- `imports/`: `import_research.py` copies named result files from one pinned commit of each research branch (git show), with a
  manifest of hashes. A later push to either branch changes nothing here.
- `compute.py`: solves every combination of the grid levers with the T00 calculators at the pinned commit (FDP-1 through the Atlas
  adapter; the gate's coupled solver for closure coils and the A1 axis fix). Writes `results/scenarios.json` with provenance.
- `site.py --json`: validates everything (any error stops the site build) and gives the website its record.

## Fixed constraints

- No number is invented: every value on the pages is a calculator output or an imported result. JavaScript only looks up cases.
- A level beyond a breakthrough's limit is OUT_OF_RANGE; a value between table points is NOT_COMPUTED; a finite-launcher case whose
  unconstrained twin does not close is NOT_COMPUTED (inferred, labelled), never filled.
- The scientific reference uses FDP-1's optimistic engineering tier where no lever is declared. That is a stated leniency.
- Switching a breakthrough on in the website never changes its canon status.

## Unknowns

- D-3He ignition and the reachable compression coupling (1D implosion, gate section 7).
- Lateral plasma flow toward the moved field zero (MHD, D-21, not authorised).
- The spine stiffness criterion; with T05's 0.2 Hz cantilever basis the coupled ship diverges.
- Target survival at launch, fill at the pulse rate, the target wall as exhaust mass (outside FDP-1).

## Design freedom

Which levels to tabulate, which breakthroughs to declare (consolidated BT-006 driver hardware from the T06 package; BT-007 structure has
no lever yet), and how the website presents them.

## Findings

See REPORT.md. In short: the scientific reference does not close (loop gain 3.1 even with targets that always arrive); 9 of the 111
computed cases close, and every one needs compression coupling of at least 0.5, the ideal-model nozzle (0.791) and a launcher far
beyond any surviving target. The coupled check (coil hardware and the A1 axis fix) roughly doubles each closing ship, and with a
launcher-limited pulse rate (V4 at 12 km/s) it diverges.

## Decisions

- 2026-11-10: research imports pinned at T00 43fac75 and T05 c45ab4a (both feasibility-gate finals). Re-import on purpose only.
- 2026-11-10: grid of five levers solved as a full product at the unconstrained launcher; launcher levels only on closing cases; named
  scenarios always solved; coupled check on every closing case, a finite launcher entering as its uncoupled rate cap held fixed.
- 2026-11-10: tests stay in the lab (not CI, as the other lab entries); the site build validates the registries and fails on error.
