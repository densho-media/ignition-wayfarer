# PSA: Primary Structural Architecture (Phases I to III)

| Field | Value |
| --- | --- |
| Kind | study (architecture exploration; no geometry change) |
| Status | ACTIVE, Phase I accepted, Phase II accepted as numerical screening (2026-11-28 11:27Z), Phase III in progress |
| Question | What physically credible, space-manufacturable, multi-material primary structure can carry Wayfarer's loads, and how does it develop together with ISSA? |
| Model base | main `11f1e94f1c36a6e53835343c3ad645ff7da8f2d5`; ISSA `claude/cloud/ship-systems-architecture` @ `5eae7016c1c31631c9437b2d7d06aa30b740a374` (Phase VI) |
| Branch | `claude/cloud/primary-structural-architecture` |
| Owner questions | PSA-D01..D08 answered 2026-11-28; Phase II P2-D1..D5 open (REPORT_PHASE2.md) |

## Function

The primary structure carries the drive's thrust to every mass ahead of it, keeps the ship aligned and stiff enough for
control, holds every subsystem at defined hard-points, isolates hot and cryogenic systems, survives the loss of a member,
and can be built at Luna Yard from mostly lunar material and repaired in flight.

## Fixed constraints (not changed by this study)

- Production geometry, `data/wayfarer_3d.toml`, the production mass budget and PMDS are read only.
- Drive canon read only (S&E 07 A1:H70, S&E 10 A1:H25, Technology 41 and 43, Culture 31, Economy 42; read 2026-11-28 08:05Z).
- ISSA files are read through `git show 5eae701:<path>`; nothing on the ISSA branch is written or merged.
- Configurations stay apart: P (production), F1 (ISSA Track F reference), R (ISSA Track R), alternative propulsion, fictional.
- Fiji is not a structural material (X-FIJI EXCLUDED). No matter replication, no unlimited industry.

## Data classes

- **CANON**: Drive rows quoted by id (e.g. `07!A2`).
- **CALCULATED**: this study's first-order numbers (`results/psa_phase1.json`).
- **ESTIMATE / UNVERIFIED**: handbook ranges in `data/materials.toml`, `data/resources.toml` (not PMDS-verified).
- **PROTOTYPE**: unsourced choices (DLF 1.3, D/t 40, frame bay 4 m, knockdowns).
- **F track**: fictional bridging advances (`F-*` materials), never mixed into R-track masses.
- **OPEN**: unknown; never zero.

## Files

| File | Holds |
| --- | --- |
| `psa_study.py` | the screening study (pure Python, standard library + repo `spec`/`mass_model`); writes `results/psa_phase1.json` |
| `build_report.py` | figures (SVG) and the interactive HTML report `results/psa.html` |
| `data/resources.toml` | 11 deposits, 9 production chains |
| `data/materials.toml` | 26 R-track, 7 F-track, 1 excluded material; design factors |
| `data/processes.toml` | 26 manufacturing processes |
| `data/joints.toml` | 32 material-pair ratings, 13 connection types |
| `data/interface.toml` | PSA-IF 0.1: hard-point classes, 10 mounting zones, 15 equipment entries, 5 handoffs |
| `data/load_cases.toml` | LC-01..LC-23 + LC-02b |
| `data/mass_ownership.toml` | 14 ownership rows and the allocation proposal |
| `data/concepts.toml` | 9 concepts, criteria, 3 weight sets, 4 material mixes |
| `data/problems.toml` | PSA-P01..P20 |
| `data/roadmap.toml` | Phases II-V |
| `REPORT.md` | the owner review gate |
| `HANDOFF_ISSA.md` | interface handoff to the ISSA thread |

Run order: `python3 work/primary-structural-architecture/psa_study.py` then `python3 work/primary-structural-architecture/build_report.py`.
The study ends with `checks: []` (no zero masses, unknown processes or load-case ids).

## Decisions taken in Phase I (study-level, reversible)

1. Size members to the thrust-bounded load (power-limited 21.77 MN), carry the canon 1.5 g envelope as a comparison case.
2. Member bodies use parent properties; joint knockdowns go into node and assembly factors.
3. Concept scoring uses normalised criteria and three documented weight sets; the mass score is the computed mass factor.
4. H and HC were proposed and scored by PSA: flagged for independent re-scoring in Phase II.
5. No Blender geometry in Phase I (optional deliverable deferred until a morphology is chosen).

## Owner questions

- **PSA-D01** Design load rule: keep 1.5 g on the full ship (63.5 MN, x2.4-2.7 structure mass) or a thrust-bounded design load with DLF/proof factors?
- **PSA-D02** Main-structure line: hold 150 t (needs imported fibre or a tank-aft layout) or resize the line (A ~240 t, H ~200 t, HC ~160 t)?
- **PSA-D03** Rails: 3 single or 6 paired (07!A33 OPEN). PSA recommends 6 paired.
- **PSA-D04** Tank shells: inside the 150 t (owner note 2026-10-18) or in their own tankage line (mass model, 458 t)?
- **PSA-D05** Momentum Spine structural shell: power line or structure line?
- **PSA-D06** Phase II candidates: PSA proposes H and HC (lunar-first and mass-first), with G as a layout question for ISSA.
- **PSA-D07** Carbon imports: acceptable mass fraction for CF/PEEK cassettes (HC ~25-40 % of longeron mass)?
- **PSA-D08** Go for Phase II.

## Phase II (2026-11-28)

Owner brief 2026-11-28 09:16Z with decisions D01 to D08. Code in `phase2/`, results in `results/p2_*.json`, report
`results/psa_phase2.html` (artifact E63AiD7jSqGbNNAamn7ReD), review `REVIEW_PSA_PHASE2.blend` (not in Git), summary
`REPORT_PHASE2.md`. Reproduce: `python3 phase2/study.py --part i/4` then `--merge`, `failsafe.py`, `thermal.py`,
`interface.py`, `ledger.py`, `hierarchy.py`, `post.py`, `build_report_p2.py`; the review file with
`/snap/bin/blender -b assets/wayfarer/WF_WAYFARER_001.blend --python work/primary-structural-architecture/phase2/make_review_p2.py`.

PROTOTYPE choices: 30 s thrust ramp, 2 % TVC, 10 % differential thrust, 2e5 N ACS pair, joint compliance 0.7, Ti node
fitting rule, rmax per family, G = 30 % of the H2 share at X -70..-20, cassette catalogue. No canon, production
geometry or owner workbook changed.

## Phase III (2026-11-28, in progress)

Owner brief 2026-11-28 11:27Z (P2-D1..D5 decided; no squash, deploy, production geometry or canon change). Integration runs
through WSI (`claude/cloud/wayfarer-systems-integration`): PSA reads `wsi_config.json` + `wsi_cp1.json` only, never edits shared
config, mass or geometry, and hands WSI code and results (commit + path). Code in `phase3/`, results `results/p3_runs/` (deck
comparison) and `results/p3_closure/` (stiffening to the lambda target).

- `c11.py` C1.1 rigid bodies (ISSA 8b30b71); `wsi_bodies.py` WSI-0.1 bodies (reproduces 11,989.1 t without structure).
- `model3.py` Build3: bodies on physical supports (vessels on skirts + guide rings, rings on hub bearings free in roll), decks
  TD-A..F, K-RING keep-out, guide tie ring option. `analysis3.py` full member check. `run3.py` evaluate() (WSI entry point),
  `stab3.py` stability on saved sizing, `closure3.py` sensitivity stiffening.
- FE faults found and fixed in III.0 (they made every earlier Phase III lambda meaningless): bodies on coincident nodes floated
  (links skipped below 1e-6 m) and 40 micron links reached 1e24 N/m; the Phase II spine slide spring sat 0.5 m off axis and
  resisted rigid roll (fake 0.01 Hz roll mode); the flutter test flagged every degenerate pair split by the follower load (now
  growth above structural damping, zeta 0.005 PROTOTYPE); vessel chains had a generic 0.6 m tube instead of their own wall.
  Phase II results were computed with the spine-slide fault; its effect on the Phase II lambda is OPEN (to be rerun).
- PROTOTYPE choices: zeta 0.005; tank-wall credit 0.5 x tankage; vessel wall Al-Li E 70 GPa; saddle, forward-end, skirt, guide
  and bearing stiffnesses (model3 constants); CFRP-HM E 260 GPa / Fc 450 MPa (Track R); FCNT Track F sensitivity only.
