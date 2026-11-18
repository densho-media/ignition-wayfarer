# Vertex 2.10: forward-stream management and alternative magnetic nozzle architecture

| Field | Value |
| --- | --- |
| Kind | study (numbers only, no geometry) |
| Status | ACTIVE, research, not canon |
| Question | Can a different forward-stream architecture make the 0.016 c reference mission work without relying on SR-26F (<= 1 % of each pulse in the single-ion regime)? |
| Model base | Vertex 2.8 ledger (work/vertex-2-8, mission28.py on 2.7/2.6) and nozzle tracer; B2d as the comparison baseline; 2.9 hybrid kept as exploratory diagnostics only |
| Owner brief | 2026-11-18 07:23Z (O1 option B, O2 keep min-cosine screen, O3 He-3 item approved for author review) |
| Open owner questions | P1-P3 below |

Nothing here changes Blender geometry, canonical parameters, workbooks or lore. No Drive writes, no squash, no deployment.

## Result in one paragraph

No candidate significantly improves the integrated budget: every closing design sits at 5.9-7.0 kt, against 6.15 kt for B2d with SR-26F,
and none meets the canonical 4.6 kt. What one candidate does improve is robustness. The **Stern Mirror** (B, an electrostatic ion
reflector on the stern disk) tolerates a single-ion share of 10 % of each pulse at 6.4 kt (6.3-6.5 kt across its loss range) and 30 %
marginally (7.0 kt), where a plate or a collector needs <= 3 %; so it relaxes SR-26F about tenfold. It replaces part of a plasma-physics
assumption with an engineering extrapolation (multi-MV vacuum reflector at tens of GW), and it does not touch VBC, isotropic suppression
or burnup. Magnetic plugs (A) cannot close the loss cone; a forward collector (C) helps only at <= 3 %; propellant coupling (C) fails by
orders of magnitude.

## Method

- Nozzle screen (O2): kappa = min(collective cavity c 1.0, single-ion Boris trace) from the 2.8 tools; forward stream from the trace,
  scaled by f_tail. f_tail swept 1 (no SR-26F), 0.3 and 0.1 (the span of the 2.9 exploratory diagnostics, not evidence), 0.03, 0.01.
- Ledger (`mission210.py`): the 2.8 ledger unchanged plus a 5 % delta-v reserve on every case and one new gate: the forward beam's
  average flux on the r 45 m stern disk joins the isotropic flux against 10 MW/m^2 (2.6-2.9 checked only the isotropic part, so the
  2.8 "tail 0.1 + beam dump" closure at 7.6 kt would fail it).
- Correction to the 2.9 wording: "a forward beam dump does not rescue it" was tested only on the raw, energy-loss-depressed 2.9 cosines.

## A: closed forward magnetic plug (`forward.py`, forward_explore / forward_final)

| Config | E_B GJ | Plug force MN | TP kappa | Coll kappa | Credit | Forward on ship (single ion) |
| --- | --- | --- | --- | --- | --- | --- |
| B2d (plug 5 T R3 z-6, main 1.5 T, burn 9) | 20.1 | 88 | 0.961 | 0.906 | 0.906 | 2.88 % |
| B2d coils, burn 12 (A1) | 20.1 | 88 | 0.968 | 0.908 | 0.908 | 1.75 % |
| B2d coils, burn 15 | 20.1 | 88 | 0.963 | 0.847 | 0.847 | 1.12 % |
| mirror plug 10 T (A2) | 30.5 | 177 | 0.975 | 0.912 | 0.912 | 1.62 % |
| mirror 10 T, burn 12 | 30.5 | 177 | 0.977 | 0.879 | 0.879 | 1.00 % |
| mirror 20 T, burn 12 | 71.0 | 353 | 0.982 | 0.785 | 0.785 | 0.62 % |
| double plug (5 T + reversed 3 T R5 z-14) | 25.7 | 160 / -143 / -17 | 0.954 | 0.908 | 0.908 | 2.10 % (2.82 % forward) |
| cusp only (reversed 3 T R3 z-12) | 17.2 | -23 | 0.826 | 0.905 | 0.826 | 4.32 % (10.6 % forward) |

- The single-ion forward share follows the loss cone, about 1/(4 R_m): halving it costs doubling the mirror ratio. Reaching the 0.03 %
  that SR-26F implies needs R_m of several hundred (2.8: a 681 T plug). Stronger or more distant plugs raise stored energy and coil
  force and lower the collective cosine; cusps and field nulls scatter ions into the loss cone and make it worse. No static magnetic
  topology closes the forward loss cone without trapping the exhaust.
- Best A: burn moved 3 m aft (A1, no hardware change), forward x0.61 at the same cosine.

## B: electromagnetic recovery: the Stern Mirror (`recover.py`, `mission210.py`)

Operating principle: an electrostatic barrier reflects ions independent of pitch angle (no loss cone). A suppressor grid (-0.05 to -1.5 MV)
turns the stream's electrons back; a ~10 MV stack of decelerating ribbon grids over the stern disk reverses every ion with E/q <= 10 MV
(the traced stream is 4.1 MV alphas and He-3, 8.25 MV protons and D); a direct-conversion stage behind it would take any higher tail.
Facets tilted 10 deg outward send 94.9 % of the reflected ions aft past the cluster at cosine 0.94; 5.1 % strike the engines' front
bulkheads (flat: 55 %, 3 deg: 22 %, 6 deg: 50 %). The reflected momentum is real thrust but is not credited (min rule).

| Check | tail 1 | tail 0.3 | tail 0.1 |
| --- | --- | --- | --- |
| Forward stream per engine | 131 GW | 41 GW | 13 GW |
| Child-Langmuir gap at the peak current (5 % duty) | 2.5 m | 4.6 m | 8.0 m |
| Vacuum breakdown limit (Cranberg, C 1e13 V^2/m) vs 8.25 MV | 0.61 | 0.82 | 1.09 |
| Ledger (h_B 5 %, 2-15 %) | no closure (stern 46 MW/m^2) | 6,981 t (6,822 t; fails at 15 %) | 6,380 t (6,335-6,535 t) |

Precedents: electrostatic reflection and venetian-blind direct conversion are established (LLNL bench two-stage ~65 % at 0.3-1 keV,
48 % net on the TMX end wall); 25 MV electrostatic accelerators exist. Nothing has been run at MV ion energies and tens of GW: the
Stern Mirror is SR-210B, an engineering extrapolation, not a new physical principle. Recovered energy: reflection returns it as aft
exhaust, so there is little left to convert; the intercepted current self-biases the stack, and a small converter could power the A+
dynamos and plasma calibration (MW class), which does not move the ledger.

## C: forward collector and propellant coupling (`recover.py`, `mission210.py`)

- Hot collector (>= 1800 K, liquid-metal cooled, +10 kg/m^2 on the stern face): its heat skips the heat pump (x2.28 saved), but the
  full stream is still heat and the face takes the beam. Closes at tail <= 0.03 (6,222 t at 0.03, 5,894 t at 0.01), not at 0.1
  (stern 10.4 MW/m^2). A solid face would get a helium dose of ~6e26 /m^2 (blistering ~1e21): it must be liquid or above ~2000 K.
- Propellant coupling fails: stopping an 8.25 MeV proton takes 0.037 g/cm^2 of hydrogen, so even a 10 m^2 target throws away 4 kg of
  gas per pulse at 56 kHz (209 t/s) at under 1 km/s. Absorbed energy cannot become useful thrust this way.

## Ledger summary (5 % reserve; departure t)

| Candidate | tail 1 | 0.3 | 0.1 | 0.03 | 0.01 |
| --- | --- | --- | --- | --- | --- |
| B2d, plate | no | no | no | 7,834 | 6,154 |
| A1 burn 12, plate | no | no | no | 6,718 | 5,881 |
| A2 mirror plug 10 T, plate | no | no | no | 6,800 | 6,021 |
| C collector (A1 nozzle) | no | no | no | 6,222 | 5,894 |
| B Stern Mirror (A1 nozzle) | no | 6,981 | 6,380 | 6,193 | 6,142 |
| B Stern Mirror on B2d | no | no | 6,588 | 6,267 | 6,181 |

He-3 2.0-2.36 kt in every closing case (canon 1,094 t). Fusion 28.6-34 TW. None meets 4.6 kt.

## Assumption sets (smallest coherent set per candidate)

| Candidate | VBC | SR-26A x0.01 | Burnup 0.99 | Forward requirement | Pulse symmetry (flutes) | New item |
| --- | --- | --- | --- | --- | --- | --- |
| B2d / A / C | yes | yes | yes | SR-26F <= 1-3 % | tight (flutes raise the forward share) | none |
| B Stern Mirror | yes | yes | yes | <= 10 % (30 % marginal) | relaxed: up to 10-30 % in the single-ion regime is tolerated | SR-210B engineering |

## Validation plan before any viability claim

1. Stern Mirror gap: 2D electrostatic PIC of suppressor + decelerating stack with the traced spectrum, space charge, secondaries and grid
   heat (small; can run here). Pass: reflection >= 95 %, h_B <= 5 %, gradient within breakdown data.
2. Nozzle f_tail with an established hybrid code (WarpX kinetic-fluid hybrid, dHybridR for relativistic ions, Hybrid-VPIC): benchmark the
   published 3D hybrid results (Nagamine & Nakashima 65 %, Matsuda 67 %, Sakaguchi ~75 % with a rear coil, Inatomi 2023 energy scaling),
   then B2d_z12 in 2D. The question is now only whether f_tail < 0.1-0.3, much cheaper to settle than < 0.01.
3. Pass criteria for any hybrid run: energy and momentum closure <= 2 %, kappa and forward share changing < 0.01 and < 10 % between grid
   refinements and x4 particles, no cutoff dependence above that, benchmarks within 5 points of the published values and peak angle.
4. 3D only after 2D passes, for the selected candidate (~1e4 core-h, off this machine).

## Engine operation and look (no geometry this phase)

The Stern Mirror adds a visible and functional stage to the A+ start-up: mechanical preparation, nozzle extension, magnetic alignment,
dynamo field-up, **mirror charge** (the faceted ribbon disk under the stern plate charges to ~10 MV, suppressor first), AI facet trim from
the plasma calibration pulses (return paths kept off the engine fronts), ignition, Vertex Lock, sustained thrust.

## Owner questions

- P1 Carry "A1 + B" (burn 3 m aft + Stern Mirror) as the 2.10 comparison candidate next to B2d?
- P2 Next step: the Stern Mirror gap PIC here (small) and a 2D external hybrid of B2d_z12 bounding f_tail; no 3D yet?
- P3 The He-3 storage queue item (`SE_QUEUE_HE3_STORAGE.md`): post it to the request Doc (S&E queue) now?

## Files

`forward.py` (A traces, `forward_*.json/.log`), `recover.py` (B/C physics, `recover.json/.log`), `mission210.py` (ledger,
`mission210.json/.log`), `SE_QUEUE_HE3_STORAGE.md` (draft queue item).
