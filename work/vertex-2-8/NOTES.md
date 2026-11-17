# Vertex 2.8: high-cosine magnetic nozzle and integrated propulsion

Research only (owner brief 2026-11-17 10:13Z, decisions D1-D4 accepted). No canon, geometry, workbook, inventory or lore changes; no squash.
Report: Claude Doc "Vertex 2.8: High-Cosine Magnetic Nozzle Study" (linked in the thread).

## Function

Find out whether a traced, physically modelled magnetic nozzle (not a multiplier) can carry the protected four-engine Vertex (candidate C,
200 m spine, A+ mechanics) to the four-burn 0.016 c mission with margins, inside the JUSTIFIED dust envelope.

## Fixed constraints

- 2.7 ledger unchanged (work/vertex-2-7/mission.py on work/vertex-2-6/compact.py), corrected braking path, JUSTIFIED dust (216 t) as the
  design case, HIGH kept as a stress test, 200 m spine, +0.6 yr trip, q_max 10 MW/m^2, 4.6 kt canon departure, 7 kt research, He-3 canon
  1,094 t (D3: shortfall is logistics, fuel still carried aboard). No fifth extraordinary capability.

## Code

| File | What |
| --- | --- |
| `test_trajectory.py` | 8 regression checks: 324.33 AU turnaround, min r 1.0 AU, braking direction and length, exposure x0.365, agreement with the dust-impacts model, 2.7 results on the corrected path |
| `nozzle_core.py` | exact loop fields, relativistic Boris tracing with per-coil impulse, energy-conserving collective cavity model, sharp-wall model, detachment |
| `nozzle.py` | candidates A, B1, B2a-d, B3a-b, C (adaptive tolerance), D (mirror needed for SR-26F) -> nozzle.json/.log |
| `mission28.py` | candidates through the 2.7 ledger with extra coils, real burn position and forward stream / beam dump -> mission28.json/.log |
| `robust.py` | speculative cosine levels (D), one-at-a-time pessimistic bands, all-pessimistic, delta-v reserve -> robust.json/.log |
| `he3_logistics.py` | lunar regolith, D-D breeding and fusion-energy sizing of the He-3 supply -> he3_logistics.json |

Run from the project root with system python3 (numpy for nozzle_core). Path fix lives in work/vertex-2-6/protect.py (old function kept as
`mission_superseded_874dca7`); work/vertex-2-7/fixpath.py is now a guard that asserts the corrected path.

## Decisions (PROTOTYPE unless stated)

- Credit rule: kappa_credit = min(collective c = 1.0, single-ion); forward stream = the larger regime. Collective c = 1.5 is the optimistic bound.
- Calibration: single coil, 50 deg coil angle, E_B = 5 E_p gives collective 0.633 against hybrid PIC ~0.65 (Nagamine & Nakashima 1999).
- Forward stream restated: f_fwd = f_tail x single-ion forward share, f_tail = share of the pulse that leaves the collective regime before
  the plug (STATED requirement, swept 1 / 0.1 / 0.01 / 0.001).
- Beam dump option: 1800 K face, 30 kg/m^2, 10 MW/m^2, 50 % direct conversion, recovered power not credited.

## Results

- The 2.7 traced cosine 0.883 is a single-ion (low-beta) number. At the ledger's own pulse energy (192 MJ, E_B/E_p 35) the burn is
  high-beta and the collective cosine is 0.47-0.53: the 2.7 reference nozzle does not close at its credited value.
- Collective cosine wants the burn near a strong field with E_B/E_p 70-150; single-ion forward leakage wants a weak burn field under a
  strong plug: forward = (1 - sqrt(1 - B_burn/B_plug))/2 (traced and analytic agree: 2.88 % at mirror ratio 9.1).
- Best credited geometry B2d: plug R 3 m at z -6 m, 5 T, main R 10 m 1.5 T, burn 0.9 R aft, E_B 20.1 GJ, E_p 134 MJ: collective 0.906 /
  single-ion 0.961, forward 2.9 % (all on the ship), coil 18 % / main 79 % of the thrust reaction, d_min 13.5 m (coil flux x2.8).
- Collar/bell coils trap weak pulses (E_B/E_p >= 70: the cavity cannot open the field); B3b at r35 credits 0.915 but forward 5 %.
- Adaptive tolerance (B2d family): pulse -30/+30 % 0.909/0.867, burn +-1 m 0.900/0.873, 0.5/1.0 m off axis 0.881/0.869; retuned currents
  restore 0.891. Usable E_B/E_p window ~50-200 (trapping above ~300). Pulse rate 23-50 kHz per engine.
- SR-26F by mirror alone needs mirror ratio 1,042 (B_plug 681 T) for 2.4e-4: impossible; the nozzle cannot remove SR-26F.
- Ledger (lever set b 0.99, charge spread, SR-26A x0.01, JUSTIFIED, 200 m, +0.6 yr): no candidate closes with the traced forward stream
  (f_tail 1 or 0.1); with f_tail 0.01 B2d 5,700 t (ve 0.078 c, He-3 1,871 t), B2a 5,798, B2b 5,911, B2c 5,957, B3b 6,420 t.
  SR-26A x0.03 fails heat at every near-burn design (coil 17-23 MW/m^2). The beam dump enables f_tail 0.1 but at 7.0-8.1 kt.
- D (stated, untraced) on B2d: cosine 0.95 5,309 t, 0.97 5,143 t, 0.97 + f_tail 0.001 4,781 t (still 181 t over 4.6 kt); the near-burn
  plug costs ~200 t against the far-burn 2.7 levers point (4,568 t) at the same 0.97.
- Robustness of B2d: kappa -0.03 +251 t, iso x1.5 +129, f_tail x3 +1,361, b 0.95 +457, radiator x1.5 +355, J_e x0.7 +108, virial x1.5 +99,
  q_max 7 MW +64, tank x1.2 +338, core +5 % +148; all pessimistic together: no closure. A 5 % delta-v reserve adds 454 t (6,154 t).
- He-3: 1,871 t at B2d (+777 t over canon). Lunar regolith at 15 ppb: ~9e10 t processed and ~20,000 km^2 already for the canon load
  (+31 % for the 2.7 +338 t); D-D breeding 1.25 TW-yr per 338 t plus decades of tritium decay. No He-3 source is canon (Technology 43
  establishes the Luna Lift / Harbor / Yard chain only).

## Superseded conclusions

| Earlier claim | 2.8 status |
| --- | --- |
| 2.7 traced nozzle cosine 0.883 at the 2.7 point | single-ion value only; credited collective value 0.47 at the ledger pulse energy |
| 2.7 point 5,889 t / JUSTIFIED 6,218 t | rests on 0.883; at the credited cosine the reference nozzle does not close |
| "high-cosine nozzle could relax SR-26F" (2.7 question 4) | no: mirror physics needs 681 T; forward leakage restated as f_tail <= 0.01 |

## Open owner questions

1. Accept the two-regime credit rule (collective and single-ion) as the nozzle evidence standard?
2. Accept "<= 1 % of each pulse leaves the collective regime before the plug" as the restated SR-26F (still speculative)?
3. Credible design case: B2d at ~5.7 kt (+1.1 kt over canon, inside 7 kt research) plus a 5 % delta-v reserve (6.15 kt)?
4. He-3 at 1.9-2.1 kt: open an Economy/Technology owner row for a lunar He-3 programme, or keep it a story-later issue?
5. Next: hybrid-PIC-class check of B2d (f_tail and collective cosine), the one number every closure depends on.
