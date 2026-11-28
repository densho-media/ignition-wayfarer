# PSA Phase II report: owner review gate

Study, not canon. Branch `claude/cloud/primary-structural-architecture`. Interactive report: artifact
E63AiD7jSqGbNNAamn7ReD (Phase I linked inside). Review file: `REVIEW_PSA_PHASE2.blend` (H and HC on the hub path, F1,
with ISSA envelopes; 12 view collections per concept).

## 1. Answer in brief

- **Most promising:** H on the hub path, six rails in three paired sectors, F1, with a partial aft H2 reaction mass (G)
  studied jointly with ISSA. HC is the carbon hybrid (4x less thermal bow, 3x the carbon imports).
- **Mass:** primary structure 1,176 t (H hub F1; 1,108 t with G; HC 1,135 t), 1,223 t with casing and rotating
  structure. The 150 t line is not reachable. Coupled departure mass +3.5 to +3.8 kt at F1 (coupling 3.52).
- **Governing problem:** global stability under thrust. λ = 0.15 to 0.82 of limit thrust in every variant against a
  target of 1.87; basis converged; analytic bounds agree. Stiffness alone does not cure it.
- **Rails:** six rails are 134 t lighter than three intact; fail-safe resizing for a rail-bay loss at nominal thrust
  costs +134 t (six) against +426 t and still failing (three). Rail joints need twin-lug fail-safe fittings.
- **Hub path beats bypass collar** in every concept by 290 to 830 t.

## 2. Classes of result

Analytical: load reconciliation, coupling, Euler/Beck/Beal bounds, backbone trade. Numerical screening: FE sizing,
stability, damage, thermal, interface. Physically supported: solver benchmarks. Fictional/PROTOTYPE: allowables
beyond established, repair cassettes, district names. Open: stability closure, deck, joints, MRU lane.

## 3. Loads (D01)

Operational x DLF 1.04, limit envelope (shutdown reversal, engine-out, differential, TVC, ACS), ultimate 1.4, proof 1.10,
accidental 1.0. 63.5 MN = 1.5 g x 4,316 t without structure; 64.5 MN = section forward of the thrust ring with
structure; 65.7 MN = whole ship with structure. 1.5 g is a separate envelope, not a sizing case.

## 4. Variants (primary structure t, follower λ)

| Variant | t | λ | Variant | t | λ |
| --- | --- | --- | --- | --- | --- |
| H bypass F1 | 2,004 | 0.54 | H hub F1 | 1,176 | 0.68 |
| HC bypass F1 | 1,422 | 0.53 | HC hub F1 | 1,135 | 0.41 |
| A bypass F1 | 1,931 | 0.33 | A hub F1 | 1,318 | 0.34 |
| C bypass F1 | 1,480 | 0.19 | C hub F1 | 1,054 | 0.25 |
| H3 hub F1 | 1,310 | 0.38 | H hub P / R | 1,163 / 1,267 | 0.58 / 0.77 |
| H hub r 7 / r 9 | 1,199 / 1,019 | 0.42 / 0.15 | H / HC hub F1 + G | 1,108 / 1,019 | 0.82 / 0.47 |

## 5. Other results

- Pickup: three pin struts 3.61 T per strut (Phase I reproduced); beam struts 0.70 T (used).
- Thermal: spine datum + slides cut spine-tie thermal util 0.46 to 0.01; hot-sector Brow bow 189 mm (H) / 55 mm (HC).
- Backbone: hybrid D 6.2 t per three planes recommended; C/C 4.0 t as the advance to test.
- ISSA: MRU lane clashes with hub cones at X 93 to 94 (0.5 to 1.2 m); hot-loop anchors 75 / 174 kN ultimate;
  structure shortening 32 to 39 mm per section; end-of-burn 0.56 g (ISSA 0.736 g).
- Imports (F1, lunar first / Earth-preferred): H 37 / 186 t, HC 111 / 315 t.
- Hierarchy: 40 to 44 cassette types; standardisation penalty 20 to 36 %, mostly the deck.

## 6. Problem register

PSA-P2-01 CRITICAL stability; 02 CRITICAL mass vs line; 03 MAJOR joint loss COAST-ONLY; 04 MAJOR shared sector node
common mode; 05 MAJOR 634 t deck; 06 MAJOR MRU lane clash; 07 MAJOR thermal bow; 08 MINOR standardisation;
09 MINOR rebase on SSI-1.0.

## 7. Phase III roadmap

III.1 stability closure (nonlinear time domain, GNC, slosh, damping, G with ISSA); III.2 fail-safe joints and X-braced
bays; III.3 deck and tankage; III.4 SSI-1.0 rebase, MRU lane, per-frame reactions; III.5 local joint and hub-cone FE,
thermal transient.

## 8. Owner decisions requested

- P2-D1 H hub, six paired rails, F1 (HC hybrid) as the Phase III baseline.
- P2-D2 retire the 150 t line or keep it as a stretch target.
- P2-D3 joint G study with ISSA.
- P2-D4 Phase III stability target: passive 1.87, or lower with certified active control.
- P2-D5 fail-safe joints as a requirement (+134 t class penalty for six rails).
