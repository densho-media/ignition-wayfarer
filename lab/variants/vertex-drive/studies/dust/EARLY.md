# T02 EARLY: two-orientation exposure map and leg fluence

| | |
| --- | --- |
| Thread | T02, dust, radiation and braking protection |
| Date | 2026-11-09 |
| Status | EARLY (exposure map, environment, first impact estimates). Final numbers come with `REPORT.md` and `HANDOFF.md`. |
| Base | `8de3ffa` (Phase 1 base), branch `claude/project-thread-uwi5pl` |
| Readers | T05 (geometry overlays, keep-outs), T01 (radiator exposure), T03 (coil exposure), T06 |

Research, not canon. Every table is generated (`TABLES.md`, from `environment.json`, `exposure.json`, `impacts.json`); rerun:

```bash
python3 lab/variants/vertex-drive/studies/dust/environment.py   # ~8 s
python3 lab/variants/vertex-drive/studies/dust/exposure.py      # ~45 s
python3 lab/variants/vertex-drive/studies/dust/impacts.py       # ~1 s
python3 lab/variants/vertex-drive/studies/dust/tables.py
```

## What the stream sees

**Bow-first (acceleration, coast).** The P11 result reproduces exactly (engine radius 112.55 m, 50 critical parts, 1,492 m²). V1 and V2
are the same: loops 2 and 3 (r 64.7 / 112.0 m), their armour, struts and feeds stay outside the r 45 m shield silhouette (1,509 m² at the
0.4° aberration envelope, 2,354 m² at 5°). The canon four-nozzle ship has **no** critical part outside its shield even at 5° (MODEL).

**Engine-first (braking).** The ship turns, so the leading silhouette is the engine-side shadow shield (FDP-1/Vertex r 8.5 m in V0,
about 7.2 m in V1/V2; canon reactor shadow shield r 5.7 m). Everything outside that radius is in the stream:

| Ship | Critical frontal area exposed (0.4°) | What | Plus the back of the forward shield |
| --- | --- | --- | --- |
| V1 / V2 | 12,282 m², 193 parts | tanks 8,426 m², habitat rings 1,724 m², nozzle loops 1,069 m², struts 384 m², shadow shield and armour 318 m², feeds 185 m² | 6,312 m² |
| V0 | 12,260 m², 210 parts | as V1 plus the r 12-14 m driver galleries | 6,267 m² |
| Canon ship | 4,015 m², 30 parts | canon tanks 1,923 m², habitat rings 1,724 m², four-nozzle drive 207 m², hull 55 m² | 6,312 m² |

This also affects the canon ship: its habitat rings and tanks face the stream in every braking burn.

## Which legs matter (NOMINAL environment)

The path: ignition at 1 AU (ASSUMPTION; canon position OPEN), radial. FDP-1/Vertex burns are 964 / 751 / 585 / 456 AU long, so the ship
cannot stop inside the Kuiper belt; its destination is at least 1,716 AU (beyond the heliopause at ~120 AU). The canon ship burns
13.3-6.3 AU and is assumed to stop at a Kuiper anchorage at 45 AU (canon position OPEN).

| Leg | Orientation | Grains above 10 kJ per m² | Where the danger comes from |
| --- | --- | --- | --- |
| FDP-1 F1 accelerate out | bow-first | 0.63 | Kuiper-belt dust at 300-1,500 km/s |
| FDP-1 F2 brake at destination | engine-first | 0.040 | interstellar dust, large-grain tail |
| FDP-1 F3 accelerate home | bow-first | 0.031 | interstellar dust |
| FDP-1 F4 coast home | bow-first | 0.078 | interstellar dust at full speed |
| **FDP-1 F5 brake at home** | **engine-first** | **1.14** | **Kuiper belt crossed at 1,200-2,200 km/s, engine first** |
| Canon C2 / C5 coast | bow-first | 1.7 / 2.5 | Kuiper belt at full speed, behind the shield |
| **Canon C3 brake at anchorage** | **engine-first** | **0.64** | **Kuiper belt, engine first** |
| Canon C6 brake at home | engine-first | 0.70 | zodiacal cloud |

LOW and HIGH bracket these by about x0.1 and x10-20 (`TABLES.md` section 3). Uniform erosion is small: 0.1-35 µm per leg; gas implants
~1e15 H/cm² at 120 keV and sputters well under 1 nm. **The threat is the rare large grain, not erosion.** A 1 µg grain at 0.016 c carries
11.5 kJ (2.7 g of TNT), a 1 mg grain 11.5 MJ.

## First protection results

- An unprotected 5 mm wall is perforated above ~2.6 kJ (about 0.2 µg at cruise). Bumpers defeat more with stand-off, because the grain's
  plasma spreads before it reaches the wall: about 21 kJ at 1 m, 84 kJ at 2 m, 2 MJ at 10 m, 200 MJ at 100 m (cloud model; band x0.1-x10).
- **Shadow-cone skirt (proposed T02-NEW-1).** A thin conical sheet whose apex is the burn point and whose half-angle is the hardware cone
  (7.9° in V1/V2): from the shadow-shield rim (x -175.8 m, r 7.2 m) to r 45 m at x +95 m; 44,900 m² surface, 6,200 m² projected, 22-90 t
  at 0.5-2 kg/m². It contains the burn's rays (edge-on) and lies in the shadow shield's umbra, yet every grain travelling forward along the
  ship meets it at a 7.9° grazing angle (7x the sheet's thickness along the track) 100-300 m ahead of the tanks, rings and forward shield.
  It cuts V1's engine-first exposure from 12,282 to 2,281 m².
- **Canon aft skirt (same idea, canon form).** A flat annulus at x -98 m, r 5.7-45 m, inside the canon reactor shield's 70° shadow:
  6,260 m², 6-31 t. It cuts the canon engine-first exposure from 4,015 m² to the drive itself, 368 m².
- **What no external shield can cover:** in engine-first, the hardware seen through the open nozzle bore (loops 1-3, the shadow-shield
  burn face, diagnostics, struts) leads the ship; any shield upstream of it would sit in the exhaust. Only local bumpers (≤ ~2 m stand-off)
  are possible there. With the skirt and 2 m local bumpers, V1 still expects ~540 events beyond the bumpers' capacity per mission
  (NOMINAL: F5 390, F1 125; LOW 3.4; HIGH 17,300), mostly in the Kuiper belt. A high-ecliptic-latitude path (heading OPEN in canon) cuts
  that to ~89 (F5 45; ASSUMPTION x0.1 on Kuiper dust). The canon ship with its aft skirt expects ~67 (NOMINAL).
- Bow-first, Vertex loops 2 and 3 need forward guard rings at ~22 m stand-off (NOMINAL; 4 m LOW; 127 m HIGH) or the P11 shield extension
  to r 112.5 m.
- Magnetic deflection stays impossible for grains (Larmor radius ~8e9 m at 1 mT; D-12 holds). Lidar warning time is milliseconds, and no
  beam can vaporise or deflect a 0.1-10 mm grain in that time. The braking plume vaporises only grains below ~1e-15 kg and removes far
  under 1 % of the hazardous fluence: no credit.

## For T05 (geometry; nothing drawn without D-10)

- Exposure overlays: `exposure.json` lists every exposed part per ship, orientation and cone (first 12 per system at non-zero cones).
- Skirt envelope V1/V2: cone apex (-227.54, 0, 0), half-angle 7.94°, from r 7.2 m to r 45 m (x -175.8 to +95.1 m); V0: 9.60°, r 8.5-45 m.
  Keep-out: nothing may pierce the sheet between those stations except along burn rays (the sheet must stay edge-on). Canon form: flat
  annulus x -98 m, r 5.7-45 m.
- Guard rings (bow-first, Vertex loops 2 and 3): ~0.8 m wide bands 20-25 m forward of each loop at the loop radius; local bumpers ≤ 2 m
  on both faces of every loop, strut and feed outside r 45 m.
- Status: CONCEPTUAL_ILLUSTRATION for both skirts; PARAMETRIC_PLACEHOLDER for local bumpers.

## For T01 (radiators)

Planar wings and blades whose planes contain the ship axis are edge-on to both orientations. At the 0.4° aberration envelope the exposed
frontal area is planform x sin 0.4° (V0 13,100 m²; V1 2,260 m²; V2 1,160 m² bow-first), plus the leading edge (edge thickness UNKNOWN).
Grazing impacts at < 0.5° are treated as low-damage gouges (EXTRAPOLATION, outside every validated model); leading edges take head-on hits
and need bumpers. The canon blades are covered bow-first and fully exposed engine-first unless the aft skirt is fitted (then 3,200 m² of
planform near the roots stays outside it).

## For T03 (coils)

Every nozzle loop is exposed in both orientations (loops 2-3 bow-first, all three engine-first). Local bumpers on the loop faces add burn
solid angle on loop 1's aft face and loop 3's forward face (~+0.001-0.004 hardware share, EXTRAPOLATION). Question for T03: what plasma
fraction reaches x more than 38 m forward of the burn at 40-60° from the axis (a forward guard-ring zone)?

## Not yet done

Radiation dose in both orientations, retractable/droplet radiators, the final skirt solid-angle bound (needs T04's source size), the
registry proposal, the full report and the handoff.
