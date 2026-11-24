# lab/

Kept work that is not part of the approved ship. Nothing here is canon. The model is `data/`, `src/` and the current baseline in
`references/`; it changes only through an owner squash. AGENTS.md "Where things go" is the rule; this is the index.

| Kind | Answers | Folder |
| --- | --- | --- |
| Variant | "What if part of the ship were built like this?" A whole alternative form, built from its own parameters. | `variants/<name>/` |
| Study | "What do the numbers say?" Tables, figures, results; no ship geometry. | `studies/<name>/` |
| Problem map | "Where and how badly does the design fail?" Reference geometry plus overlays; never proposes a fix. | `problems/<name>/` |

Status: ACTIVE, PARKED, SUPERSEDED (by which entry) or PROMOTED (into which `main` commit).

## Entries

| Entry | Kind | Status | Question | Model base | Open owner question |
| --- | --- | --- | --- | --- | --- |
| [fdp1](variants/fdp1/NOTES.md) | Variant | ACTIVE | Pulsed D-3He drive, one Fiji nozzle, four 0.016 c burns | 92b83f0 | target gain; 6.0 y vs 6.35 y; drive topology |
| [fiji-drive](variants/fiji-drive/NOTES.md) | Variant | SUPERSEDED by fdp1 | Integrated Fiji Drive v2-v4 | 5a913f9 | none |
| [redesign-layout](variants/redesign-layout/NOTES.md) | Variant | SUPERSEDED by TANK-AXIAL (90df1a9) | 343.5 m split-storage layout | 702ff62 | none |
| [four-burn-mission](studies/four-burn-mission/NOTES.md) | Study | ACTIVE, engine of fdp1 | What drive and ship fly four 0.016 c burns, by tier | 92b83f0 | which tier to design to |
| [graded-thermal-blade](studies/graded-thermal-blade/NOTES.md) | Study | PROMOTED 1f9eba1, kept as a tool | Radiator view-factor Monte Carlo and blade concepts | 90df1a9 | none |
| [fdp1-requirements](problems/fdp1-requirements/NOTES.md) | Problem map | ACTIVE | Where FDP-1 fails: 0.016 c x4 closes, 1 g does not | e251f7c | V3 review; P11; shield mass OD-014 |
| [breakthrough-lab](studies/breakthrough-lab/NOTES.md) | Study | ACTIVE | Which declared breakthroughs, and how few, make the Vertex drive close? | 279a612 (T00 030fc14, T05 f497778 imports, Gate 2) | which breakthroughs to select for experiment; spine stiffness criterion |
| [assembly-sequence](studies/assembly-sequence/NOTES.md) | Study | ACTIVE | In what order could the approved ship be assembled in orbit, from the first structure to first ignition? | 0aa94a3 | is the order right; the assembly yard |
| [deadship](studies/deadship/NOTES.md) | Study | PROMOTED into main 2026-11-16 | How should Deadship teach the ship's real systems, and what do its gate and sensitivity studies say? | c77026d | Phase 4 PARKED; sourced power values; cabin hull exchange and heaters |
| [ignition-failures](studies/ignition-failures/NOTES.md) | Study | ACTIVE | What breaks first when the drawn Vertex cluster ignites at the mission point, and what would a visitor have to change? | bbe1d7e (Vertex b87a9c1 imports) | is the training page right; squash order with the engine studies |
| [dust-impacts](studies/dust-impacts/NOTES.md) | Study | ACTIVE | What does dust do to Wayfarer at speeds up to 0.016 c, and what would a visitor have to change? | c7cca43 (Vertex 2.6 874dca7 imports) | is the training page right; Brow layer and skin thickness; HIGH dust as residual risk or gate |
| [fuel-propellant](studies/fuel-propellant/NOTES.md) | Study | PROMOTED with the FPS V1.1 squash, kept as check tools | Does the integrated fuel and propellant system fit, connect, come apart for engine removal and stay inside the browser budget? | 3532857 + FPS V1.1 (577bff8) | drawn Vertex mass vs the 250 t drive allowance; CONSERVATIVE frame case; thrust-ring joints |
| [external-pulse](studies/external-pulse/NOTES.md) | Study | ACTIVE | EXT-01: is an external pulse drive (plate, magnetic pusher, remote field) worth building for the 0.016 c mission? | eb33a44 | next propulsion milestone; directional pulse and leak-free field stay UNVERIFIED |
| [halo-vertex](variants/halo-vertex/NOTES.md) | Variant | PARKED (rejected as baseline 2026-11-17) | Vertex 2.0-2.5: four halo rings about 2 km aft with Vertex Burn Channeling; closes at 6.9 kt at best, not 4.6 kt | f1601d4 | none; VBC stays a research hypothesis |
| [vertex-closure](studies/vertex-closure/NOTES.md) | Study | PARKED (gate failed 2026-11-18) | Vertex 1.8 Phase F and 2.6-2.11: can the Vertex cluster close the mission ledger near 4.6 kt? No; no hold-off-consistent closure below 8.1 kt | eb33a44 | R1 accept the gate; R2 broader fuel-cycle and architecture comparison; R3 keep A1 |
| [accelerator-fusion](studies/accelerator-fusion/NOTES.md) | Study | PARKED (negative result accepted 2026-11-22) | Could an accelerator-driven, selective D-3He system replace or beat the Vertex drive? No: Coulomb scattering, space charge and the heat budget block it | 3866ebf | none |
| [selective-fusion](studies/selective-fusion/NOTES.md) | Study | ACTIVE | Selective Fusion Engineering: how much cleaner can selective fuelling, spin polarisation, hot-ion operation and burn geometry make the Vertex burn, and the public Fusion engine explainer | 3866ebf + accelerator-fusion | is the explainer right; SFE-1 next; quintet suppression as a Breakthrough Lab entry; burn-geometry study |
| [fusion-ignition](studies/fusion-ignition/NOTES.md) | Study | ACTIVE | Fusion Ignition, From Nucleus to Nozzle: how is the Vertex drive built, started and ignited, what do the models predict at each step, and where does it fail? | d016d5d (compact C1-C4, thermal and source imports) | is the flagship simulation right; C4 as compact working direction; blade aft ends; ENG-030 or ENG-036 next |
| [vertex-compact-engine](studies/vertex-compact-engine/NOTES.md) | Study | ACTIVE, behind the Fusion Ignition page | Can the compact Vertex engine reject its heat and reach the mission exhaust speed? Not yet: 1,575x the radiator share with edge-on blades, 4,914 of 19,201 km/s | d016d5d | ENG-062 hit share next; blade dynamics; R1 engine sizing |

Each entry's `NOTES.md` opens with the same table: kind, status, question, model base, the branch it came from, open owner
questions and where its review file is.

## Rules

- Nothing in `src/`, `tests/`, `tools/`, `godot/`, `web/` or CI reads `lab/`, except `tools/story.py`, which publishes this index,
  each entry's NOTES header and body, its REPORT.md summary, its committed figures (SVG, or PNG without an SVG twin, up to 1.5 MB) and
  an entry's `site.py --json` (a problem map's also `--compare`, the 3D comparison's blockout and problem pairs) as the website's Engineering pages. Everything here is public: write it for outside engineers.
  Lab code may read `data/` and `src/`.
- Run lab scripts from the repository root (`python3 lab/variants/fdp1/run.py`). Their tests are not part of the pipeline:
  `python3 lab/variants/fdp1/tests/test_fdp1.py`, `python3 lab/studies/four-burn-mission/tests/test_fourburn.py`,
  `python3 lab/studies/breakthrough-lab/tests/test_breakthrough_lab.py`, `python3 lab/studies/ignition-failures/tests/test_model.py`, `python3 lab/studies/dust-impacts/tests/test_model.py`, `python3 lab/studies/external-pulse/tests/test_ext01.py`, `python3 lab/studies/fusion-ignition/tests/test_model.py`.
- A lab number reaches canon only through its Drive owner workbook and the normal loop (AGENTS.md).
- `.blend` files and renders stay out of Git; the entry's script rebuilds them, and the review copy sits in the project files
  `review/` folder or on GitHub Pages.
- In `.blend` files: the approved ship stays in `GEN_`, a variant's parts in `VAR_<name>`, problem overlays in `PROB_<name>`,
  study figures in `STUDY_<name>`. All are pink (unapproved), like `WORK_<task>`. Replaced model parts are hidden, never deleted.
- New entries come from a task: `work/<task>/` on its branch, then on the owner's verdict either into the model, into `lab/<kind>/<name>/`
  (squashed), or dropped (the branch's last commit hash goes into this index). Branches are deleted after the squash.

## Dropped

| Work | Last commit | Why |
| --- | --- | --- |
| retired `src/wayfarer/studies/` (57 scripts) | 038ae90 | cleanup 2026-10-29 |
