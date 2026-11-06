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

Each entry's `NOTES.md` opens with the same table: kind, status, question, model base, the branch it came from, open owner
questions and where its review file is.

## Rules

- Nothing in `src/`, `tests/`, `tools/`, `godot/`, `web/` or CI reads `lab/`, except `tools/story.py`, which publishes this index,
  each entry's NOTES header and body, its REPORT.md summary, its committed figures (SVG, or PNG without an SVG twin, up to 1.5 MB) and
  a problem map's `site.py --json` as the website's Engineering pages. Everything here is public: write it for outside engineers.
  Lab code may read `data/` and `src/`.
- Run lab scripts from the repository root (`python3 lab/variants/fdp1/run.py`). Their tests are not part of the pipeline:
  `python3 lab/variants/fdp1/tests/test_fdp1.py`, `python3 lab/studies/four-burn-mission/tests/test_fourburn.py`.
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
