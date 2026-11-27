# Ship Systems Architecture (ISSA) — work notes

| Kind | Status | Question | Model base | Owner questions |
| --- | --- | --- | --- | --- |
| study + proposal | ACTIVE (owner review) | Which ship systems are missing, how much power and space they need, and where they could go without changing canon, silhouette or budgets | main at branch start, built locally (assets/wayfarer) | DR-01 … DR-13 |

**Function.** Systems-engineering review of G.U. WAYFARER 001: inventory (`systems.toml`, 56 assemblies, 13 families, one owner
each), electric load model over 15 conditions and a source screen (`eps_study.py`), a voxel survey of the built vehicle
(`survey_blender.py`, `districts.py`, `figures.py`), a review file (`make_review.py`) and the proposal page (`build_report.py` +
`report_template.html` → `results/issa.html`, published as https://claude.ai/artifact/7oSfK7TWrd2RSctscycsDA).

**Fixed constraints (brief 2026-11-27).** No canon, production geometry, silhouette, dimension, mass-allowance or Drive change; no final
power technology; no squash, no deploy; parked propulsion research touched at interfaces only.

**Key results (all NONCANON, PROTOTYPE/STUDY).**
- Coast demand: 0.8 MW ship service, 3.6 MW with proactive defense, 26 MW with the normal active band. Defense duty sizes the plant (DR-01).
- Candidate A (main drive in hotel mode) not credible. Direction D: L1 drive-derived burn power, L2 two fission-Brayton plants (working
  baseline; auxiliary fusion as a speculative alternative), L3 isolated survival source + batteries.
- The 50 t power/computers/steering/comms item already holds ~31.5 t (19–51); ~18.5 t left. Two ship-service plants ~24 t before shields.
- Coast plants can reject to the dark blades (119 MW at 550 K); no new radiator.
- Casing interior 31,319 m³; usable blocks 1,230 m³; aft bay 75 m³ usable; dry store 3,800 m³ is the reserve (repurpose M1–M4, M8–M9).
- Inconsistencies: crew-5/6 life-support sizing vs crew 12; stale G01 evidence; unrated Brayton proxies in the run-tank zone; Deadship
  generator assumes A; no budget line for drive-off or burn generation; food ~48 t vs 10 t.

**Decisions.** See the proposal page, section J (DR-01 … DR-13). First task K: EPS-A power-load module, no geometry.

**Run.**
```
python3 work/ship-systems-architecture/eps_study.py
/snap/bin/blender -b assets/wayfarer/WF_WAYFARER_001.blend --python work/ship-systems-architecture/survey_blender.py
python3 work/ship-systems-architecture/districts.py && python3 work/ship-systems-architecture/figures.py
/snap/bin/blender -b assets/wayfarer/WF_WAYFARER_001.blend --python work/ship-systems-architecture/make_review.py -- --render
python3 work/ship-systems-architecture/build_report.py
```
Review file (not in Git): `work/ship-systems-architecture/REVIEW_SHIP_SYSTEMS_ARCHITECTURE.blend`, copy in the project files `review/`.
