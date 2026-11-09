# T01 early findings: radiator areas, wing envelopes, radiator types

| | |
| --- | --- |
| Thread | T01, thermal systems, electrical efficiency and mass |
| Date | 2026-11-09 |
| Base | `8de3ffa` on `claude/project-thread-93sqqi` |
| Status | EARLY: numbers are from `split.py` / `ledger.json` at this commit; final values come with `HANDOFF.md` |

Research only, not canon. Every ship number is an FDP-1 calculator result (optimistic tier, four 0.016 c burns) run through
`studies/thermal/split.py`. "Atlas" = the Atlas single warm loop. "Split" = the warm heat booked by 14 components, each on its own
circuit, collapsed into the one equivalent warm radiator the calculator can solve (same total area, same total mass).

## For T02 and T05: envelopes per case

Warm wings are the W2 layout (two half-plane wings, port/starboard, edge-on to the burn), wing length 266.75 m along x (x -178.75 to
+88.0), +X bow. Tip radius = warm root radius (10 m plus the 1,800 K hot root band) + warm span. Hot = 1,800 K heat-pipe area; the
three canon blades (14,935 m2 planform) carry part of it and the rest is the root band.

| Case | Driver eff. | Departure t | Warm GW | Warm km2 | Wing tip m | Hot km2 | Low m2 | Warm T_eq K | Label |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| V0 Atlas | 0.45 | 20,760 | 24.4 | 1.844 | 3,573 | 0.072 | 1,794 | 600 | MODEL |
| V1 Atlas | 0.45 | 10,416 | 7.89 | 0.322 | 653 | 0.036 | 751 | 700 | MODEL on TARGET inputs |
| V1 Atlas | 0.30 | 12,978 | 13.8 | 0.565 | 1,124 | 0.045 | 1,009 | 700 | MODEL on TARGET inputs |
| V1 Atlas | 0.25 | 15,219 | 19.1 | 0.777 | 1,537 | 0.053 | 1,235 | 700 | MODEL on TARGET inputs |
| V2 Atlas | 0.45 | 9,272 | 7.03 | 0.168 | 356 | 0.032 | 635 | 800 | MODEL on TARGET inputs |
| V2 Atlas | 0.30 | 10,838 | 11.6 | 0.276 | 570 | 0.037 | 793 | 800 | MODEL on TARGET inputs |
| V2 Atlas | 0.25 | 12,058 | 15.1 | 0.361 | 737 | 0.042 | 916 | 800 | MODEL on TARGET inputs |
| **Split advanced (V1 base)** | 0.45 | 9,702 | 3.53 | 0.222 | 460 | 0.033 | 679 | 628 | MODEL on TARGET components |
| **Split advanced (V1 base)** | 0.30 | 12,654 | 8.68 | 0.547 | 1,088 | 0.043 | 976 | 628 | MODEL on TARGET components |
| **Split advanced (V1 base)** | 0.25 | 15,473 | 13.6 | 0.857 | 1,688 | 0.053 | 1,261 | 628 | MODEL on TARGET components |
| Split advanced (V2 base, W armour) | 0.30 | 12,351 | 8.48 | 0.533 | 1,061 | 0.042 | 946 | 628 | MODEL on TARGET components |
| Split conservative (near-term parts) | 0.25-0.45 | **does not close** | | | | | | 489 | MODEL |
| Near-term temperatures on 1.0 kg/m2 | 0.45 | 15,675 | 6.98 | 1.194 | 2,320 | 0.053 | 1,281 | 489 | MODEL, radiator TARGET |
| Near-term temperatures on 0.5 kg/m2 | 0.45 | 11,602 | 5.15 | 0.882 | 1,710 | 0.040 | 870 | 489 | MODEL, radiator TARGET |

For T05: the planning envelope is the split-advanced case at 0.30 (tip about 1.1 km), bracketed by 0.45 (tip about 0.46 km); the
Atlas V1 653 m wing is not the planning value. Circuit areas per case are in `RESULTS.md` (Circuits).

## Radiator types still in play

| Circuit | Temperature | Type | Status |
| --- | --- | --- | --- |
| Hot (plume strike, recovery loss, radiation on loops) | 1,800 K | refractory heat pipes (canon blades + root band) | unchanged from FDP-1 |
| Induction cores | 470 K near-term, 640 K TARGET | Ti-water heat pipes (to about 520 K) / advanced panels 1.5 kg/m2 or tin droplets | the largest warm circuit, about 40 % of the area |
| Power stages, busbars, ion sources, factory electronics | 500 K near-term (250 C SiC modules shown), 740 K TARGET | Ti-water heat pipes / tin droplet sheet | |
| Pulse capacitors | 440 K near-term (200 C parts), 550 K TARGET | Ti-water heat pipes / tin droplet sheet | |
| Beam dumps and final-focus heating | 900-1,000 K | potassium heat pipes / tin droplet sheet | small |
| Cryoplant hot sides (driver magnets, factory 1.5 K, nozzle coils) | 450-700 K | with the electronics | rejecting hot costs input power (Carnot) |
| Low loop (propellant cryocooling) | 300 K | panels 2.5 kg/m2 | about 700-1,300 m2 |

Still in play: fixed hot blades + deployable warm wings (D-05), and the tin droplet sheet (VTX-07B) as the only radiator in the record
that reaches about 1 kg/m2 above 520 K. Solid panels in the 450-700 K band sit in the heat-pipe working-fluid gap (5 kg/m2 class).

## Early findings (preliminary)

1. **House load survives and grows as a saving.** Built bottom-up per pellet the house is 0.012-0.014 % of fusion (near-term, about
   10 MJ per pellet) or 0.003-0.005 % (advanced), against the Atlas 0.05 % TARGET and the 0.1 % baseline. It holds only while the yield
   per target stays near 81 GJ (fuel-only targets).
2. **The 700-800 K warm loop does not survive as booked.** With every component at its TARGET temperature the equivalent loop is 628 K,
   not 700-800 K; with near-term parts it is 489 K and the ship does not close at any driver efficiency on 3 kg/m2 radiators. FDP-1 itself
   (V0) does not close at 2.5 kg/m2 or at 500 K.
3. **The Atlas warm radiator (1.0 kg/m2 at 600-800 K) is a droplet-sheet TARGET.** On 5 kg/m2 halide or alkali heat-pipe panels V1
   grows from 10.4 kt to 50.6 kt.
4. **Driver efficiency and driver mass now dominate the warm loop.** Driver loss is 75-95 % of the warm heat once the house is booked.
   V1 at 0.1 kg/kW driver mass is 12.9 kt and at the calculator's own central 0.2 kg/kW 25.1 kt; the split-advanced ship at 0.30
   efficiency does not close at 0.2 kg/kW.
5. **New (for T04): targets in flight.** FDP-1 flies 12.5 targets at once at 400 m/s, 3.7 m apart; the next target is 3.7 m from each
   81 GJ pulse (about 5e6 J/m2 X-rays, 5e8 J/m2 plasma; about 35x what vaporises its D2 shell from the X-rays alone). With only one target
   in the open per period, the launcher needs 4.7-7.5 km/s. A 4 km/s launcher costs +6 %, 2.5 km/s +17.5 %, 1.5 km/s does not close.

Net so far: split advanced at 0.45 is 9.7 kt (V1 10.4 kt), at the planning value 0.30 is 12.7 kt (Atlas V1 at 0.30: 13.0 kt). The
house saving roughly pays for the lower warm temperature; the result rests on droplet radiators, 640 K cores and 740 K power stages.
