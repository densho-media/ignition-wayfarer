<!-- lab entry -->
| Lab entry | |
| --- | --- |
| Kind | Study |
| Status | ACTIVE (behind the Fusion Engineering page; not canon) |
| Question | On the research geometry (burn about 4 m aft, closure x4), which pulse size, coil current distribution and energy-transfer route bring the engine closest to the mission, and what hardware does it need around the coils? |
| Model base | main 45a8801; research geometry `mirror4|4` (vertex-optimize), R2-B target burn (fusion-ignition `src.run`), ron.py capture |
| Branch | claude/project-thread-1p6mtu, 2026-11-25 |
| Open owner questions | Reconcile the two charged shares (ENG-075); re-trace steering with the optimised ring currents (ENG-076); a renewable or vapour-shielded face, or a protected injection path (ENG-074); nothing closes (ENG-078) |
| Review | `engineering/fusion-ignition/` Pulse buttons (8 stages) and pulse tables; `REVIEW_PULSE.blend` (local) and the renders in the project files (fusion-pulse) |

# vertex-pulse: notes

Owner brief 2026-11-25 08:55Z, "Integrated Vertex Drive: Pulse Architecture & Magnetic Optimization". The burn about 4 m aft is the primary
experimental design direction and working model; the original geometry stays as the comparison. That approves the geometric direction, not
the physical performance figures. Mission parameters and approved ship specifications are unchanged. Nothing here is canon.

- `pulse.py` (about 1 min): the R2-B design target scaled in mass (x1/64 to x16) at the design areal density, plus areal density, tamper,
  D:3He mix, polarisation (SPECULATIVE) and early-extraction levers, each burned by `src.run` and fired at the rate that holds the mission
  power (65.3 TW per engine) through the research nozzle; capture energy on both charged-energy bases (burn ledger and operating point,
  never mixed), plasma cavity in the drawn coils, surface spike on the nearest cryostat face, injection speed; the window, the
  compromise and the equal-thrust comparison.
- `magnets.py` (about 3 min): ENG-067/068/069. W/E of every scanned topology, per-ring current distribution by coordinate descent at
  constant capture, conductor and structure scenarios (today and named assumed properties, none credited), loads, quench modules.
- `transfer.py` (seconds): extraction at equal thrust; the mission jet-share condition; Bethe ranges, X-ray absorption columns and shells
  as requirements an upstream energy transfer would have to meet. No transfer mechanism is invented.
- `frames.py`: integrated hardware round the research coils placed by search: re-aimed tungsten lips, twin-bore lithium headers, 20 K and
  warm rings, warm manifold, supermirror strips, trays and supports; clash, connectivity, span and burn-exposure checks.
- `findings.py`: findings, future-technology needs as measurable properties, assembly steps; page import
  `lab/studies/fusion-ignition/imports/pulse.json` (ENG-073..080 in `chapters.py`).
- `blender_pulse.py`: `REVIEW_PULSE.blend` from `vertex-optimize/REVIEW_OPTIMIZE.blend` (scene INTEGRATED with the `WORK_INT_*`
  collections, scene SECTION with a C1 meridian section) and the renders.

## Findings (2026-11-25)

- **Pulse size moves the rate, not the averages.** At mission power thrust stays 1.73 MN per engine and heat 8,448x the radiator share
  from x1/64 to x16. Smaller pulses do not reduce the average waste heat. Best equal-thrust lever: areal density x0.5, 5,248x.
- **Per pulse everything scales.** Capture energy is 27.7x the charged energy in this topology: x1 at 42 kHz needs 7.1 GJ (burn basis),
  inside the 27 GJ the drawn coils hold; the face spike is 6,491 K at x1 and 101 K at x1/64.
- **No window.** The face (spike under 117 K) needs mass at most x0.018; the injector (under 20 km/s) needs at least x18; gap 989. Keeping
  x1 needs the face 55 m from the burn.
- **Basis.** Burn ledger 7.1 GJ against operating point 39 GJ at the same rate (286 GJ at the design rate): the two source models are not
  reconciled (ENG-075).
- **Magnets.** Field strength is not the lever: ring currents x0.49/0.2/0.58/1.85/1.61/0.34 cut 286 to 83 GJ and 60 to 25 T at the
  windings; best topology W/E 14 against the floor 1. Conductor and structure 342 t today, 85 t only with assumed 4x Je and 6 GPa fibre.
  Forces close inside the coil set (16.1 GN on one coil, net 54 MN). Quench in 34 modules within 10 s. Not re-traced for steering (ENG-076).
- **Extraction at equal thrust:** 605x against 1,155x heat but 2.7x the fusion power and 0.15 of the exhaust speed.
- **Transfer:** the jet must carry 80 % of the fusion power and carries 5.1 %. Products already heat the fuel (rhoR 893x the proton range);
  outside hydrogen only lowers the exhaust speed. A low-Z X-ray shell at the target (25 g/cm2) gives 0.62 of the need as a cold-opacity
  upper bound.
- **Geometry:** 87 parts, 0 clashes, all networks connected (hot 36/36, 20 K 18/18, warm 21/21, electrical 6/6), longest run 2.8 m;
  1 header and 29 runs in the burn's view need covers (ENG-079).
- Nothing closes the engine.
