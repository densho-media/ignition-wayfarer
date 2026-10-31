# CIRC-001 ring corridors: trade-off and prototype decision (2026-10-31)

Decision by Claude under the owner's delegation of 2026-10-31 ("if you base your decisions on research and science, you can decide it
yourself"). PROTOTYPE: it settles the model's direction; the owner workbooks (12_HABITAT_LAYOUT A13, the 400-460 m3 envelope, the
330 t rotating allowance) are not edited and keep reporting the conflict until the owner canonizes or replaces it.

## Question

Keep the pressurized walking corridors between the sectors of each ring (CIRC-001, owner design direction 2026-10-26), or go back to
the BASELINE rule that pressurized rooms occupy only the sectors?

## Numbers (ring_circulation.budget, both rings)

| Quantity | Sectors only | With corridors |
|---|---|---|
| Gross pressurized volume | 434 m3 | 1111 m3 (2.42x the 460 m3 maximum) |
| Added cabin gas (80 kPa, 295 K) | - | 641 kg |
| Added rotating mass (liner 32.0 t, decks 2.9 t, 18 doors 2.2 t, fit-out 3.2 t) | - | 40.2 t (12.2 % of the 330 t allowance) |
| Spoke axial load | - | +49 kN (+12 %) |
| Fill volume used by the tunnels, per ring | - | 507 of 2249 m3 (23 %) |
| Ways out of a sector | 1 (the overhead hatch, a 2.9 m ladder to the crew tube) | 3 (hatch and both side doors) |
| Nonambulant transfer between sectors (D02, 24 states) | ring B 0/24 transfers; hatch route FAIL -0.44 m | 24/24 PASS (corridor, 0.75 x 2.00 m doors) |
| Walking between sectors at 0.5 g | up the ladder, through the hub at 0.05 g, down again | level walk, about 53 m a sector |

## Reading

- **Safety (decisive).** Every sector today has one exit, a vertical ladder into a tube that crosses near-zero gravity at the hub. A fire,
  smoke or a stuck hatch in that path traps the crew of the sector. Two independent exits per occupied compartment is the basic rule of
  crewed-vehicle and building fire safety (NFPA 101 means of egress; the ISS keeps two hatches on most modules for the same reason). The
  corridors give every sector two level exits plus the hatch, and the D02 casualty route through them now passes in every state the
  owner asked for, where the hatch route failed. No other change found in the D02 studies reaches that result.
- **Mass (acceptable, budgeted as a risk).** 40 t is large but inside the rotating allowance's uncertainty (330 t PROVISIONAL, Q32). It
  is an internal liner shielded by the fill, so it needs no MMOD or exterior thermal layer. The 15 kg/m2 liner is the PROTOTYPE estimate;
  the sector skin's areal mass would give 301 t, which is why the corridor shell must stay an internal, low-differential liner and not a
  second hull.
- **Volume and gas (acceptable).** 641 kg of extra atmosphere is a one-time fill; leakage scales with seal length, not volume, and the 18
  doors add seal length (leak rate OPEN). Every corridor half is its own compartment (largest 56 m3), so a breach vents at most one half.
- **Shielding (no loss claimed, none credited).** The tunnels take 23 % of the fill volume; the fill's shielding credit is not sourced,
  so nothing is lost on paper, but the radiation budget must count the tunnels if the fill is ever credited.
- **Alternatives considered.** (a) Sectors only: cheapest, keeps canon, but leaves one exit per sector and no care route. (b) Unpressurized
  crawl tunnel used only in suits: no shirt-sleeve rescue (the suited envelope already fails the 0.75 m door), so it buys nothing over the
  crew tubes. (c) A narrower corridor (0.80 m): saves about 2 t of liner, loses the litter margin. None beats the full corridor on safety.

## Decision

Keep CIRC-001 as the model's direction (PROTOTYPE). Conditions carried with it:
1. The 40 t and 641 kg are reported as an unbudgeted rotating mass and gas item (CIRC-C2/C3) until the owner rebalances the 330 t allowance.
2. The corridor shell stays an internal liner shielded by the fill (the 15 kg/m2 basis); a change to a load-bearing hull reopens the trade.
3. Leak rate, repressurization gas and ECLSS air circulation through the doors stay OPEN.
4. The frame portals stay on the hand check (116 of 200 MPa) until FEA.

Owner action: canonize CIRC-001 against 12!A13, the gross envelope and the rotating allowance, or reject it (TODO J06).
