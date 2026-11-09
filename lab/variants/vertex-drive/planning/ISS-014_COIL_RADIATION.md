# ISS-014: closure-coil radiation interception in the integrated V4 ledger (T00, 2026-11-09)

| | |
| --- | --- |
| Asked by | T05 (`claude/project-thread-ctwplp` at `7fc1da8`, `work/vertex-blender/rev2.json` key `coils`, `rev3.json` key `coil_cooling`) |
| Baseline | `a1c8246`, V4 in `results/convergence.json` |
| Status | MODEL, research only. **Unbooked** in the calculator; the load does not disappear. |

## 1. Is the coil load already in the calculator's ledger?

No. The two hot-loop terms that touch hardware are booked differently (`lab/variants/fdp1/engineering/thermal.py` `circuits`, and
`lab/studies/four-burn-mission/fourburn/architectures.py`):

| Ledger term (V4) | Value | What it is | Includes closure coils? |
| --- | --- | --- | --- |
| `plume_to_hardware` | 478.5 GW (0.0134 of fusion) | **Plasma**: the nozzle loss (1 − η_T) times the strike share 0.065 (T03, nozzle C) | No. In T03's thin-shell model the plasma stops at 25-30 m from the burn, inside both coils (C1 is 43 m from the burn), so no plasma reaches them. The strike share counts the shield and the ship forward only (`strike_by`). |
| `radiation_on_hardware` | 10.2 GW | **Radiation**: escaping X-rays (412 GW) times the geometric solid angle Ω = loops + struts + shield = 0.0248 | No. `model.py` builds Ω from `nozzle_loops`, `nozzle_struts` and `shadow_shield` only. |

Rev 2's reading is right. The coils' X-ray interception lies outside both terms, and so does their cooling.

## 2. How large is it?

T03's coil geometry (`studies/nozzle/results/nozzle_results.json`, design `C_W15`, envelope = 3 × winding minor radius, share =
sin(polar) × envelope / distance) scales to V4 by the stand-off ratio 64.70 / 43.11 = 1.5007. The share is scale-invariant if the
windings scale with the nozzle.

| Coil | Polar | Radius at V4 | z at V4 (from burn) | Current (V1) | Winding minor (V1) | Envelope share | X-ray load at V4 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| C1 | 20° | **22.13 m** | 60.8 m | 132 MA | 1.06 m | 0.0252 | **10.4 GW** |
| C2 | 40° | **41.59 m** | 49.6 m | 10.6 MA | 0.085 m | 0.0038 | **1.6 GW** |
| Total | | | | | | 0.029 | **11.9 GW** |

T05's radii (C1 r 22.1 m, C2 r 41.6 m) match T03 scaled to V4. **T05's C1 load matches (10.46 GW). T05's C2 share is about 12×
T03's.** T03's C2 is a thin 10.6 MA coil with a 0.085 m winding and a 0.25 m envelope; a share of 0.0477 needs an envelope of about 3.2 m.
On T03's geometry the total is 11.9 GW, not 30.1 GW.

The band to keep (EXTRAPOLATION):

- **Low, 11.9 GW**: T03's windings scaled geometrically.
- **High, about 15-16 GW**: the V4 pulse is 2.25× V1's energy at the same 15 E_p ratio. If C1's winding grows with the square root of
  its stored energy, C1's share rises about 1.5×.
- **T05's 30.1 GW stays an upper case** until T05 gives C2's envelope a reason (armour, screen or cryostat thickness) beyond T03's
  winding.

## 3. Cooling consequences (rescaling T05 Rev 3)

- **Flux on C1 is unchanged**, about 7.8 MW/m² on its sky-facing armour, so T05's conclusion stands: passive radiation would need
  about 3,600 K and is ruled out, and C1 needs a pumped loop.
- **C2 at T03's envelope** takes 1.6 GW. Its flux per area depends on the armour area T05 draws; it is about 7.8 MW/m² only if C2
  presents the same envelope per share.
- **Hot radiator at 1,800 K** (2εσT⁴ = 1.07 MW/m²) for 11.9 GW: about 11,100 m², 16.7 t at V4's 1.5 kg/m² hot areal (T05: 28,100 m²
  and 57 t for 30.1 GW). Pumping and loop flow scale with the load, so roughly 0.4× T05's figures: about 24 m³/s of tin and about
  24 MW. The back-face leak into the warm screens is per coil and unchanged for C1.
- **Ledger effect**: +11.9 GW is +2.4 % of V4's 495 GW hot reject, and roughly +1 % on departure mass through the hot-radiator
  elasticity (not solved). It is listed as an unbooked penalty with the coil structure (855-1,281 t), the skirt, the launcher and the
  tritium store.

## 4. Booked (PROXY) in the Vertex adapter, 2026-11-09

T05 confirmed that it has no physical reason for C2's thicker envelope; its screen script had copied C1's 4.8 m envelope across. T03
geometry is now the basis for both threads, with 30.1 GW kept only as the upper case.

FDP-1's solid-angle code is protected, so `convergence.py` books the coil heat through `coil_kv()`. It is added to
`plume_to_hardware`, which goes to the same 1,800 K hot loop and scales with fusion power:

  Δ = share × escape / ((1 − escape)(1 − η_T))

Thrust is unchanged, because the heat comes out of plume and radiation that leave the ship anyway. Case `V4_coil_booking` in
`results/convergence.json`; full rerun exit 0, every other result unchanged:

| Coil share | Basis | V4 departure | Radiators | Hot area | Wing tip r |
| --- | --- | --- | --- | --- | --- |
| 0 (V4 as integrated) | unbooked | 42,916 t | 3,572 t | 0.462 km² | 10,128 m |
| 0.029 | T03 geometry, 11.9 GW | **43,211 t (+0.7 %)** | 3,620 t | 0.476 km² | 10,218 m |
| 0.0377 | C1 grown with the V4 pulse, 15.5 GW | 43,301 t (+0.9 %) | 3,634 t | 0.480 km² | 10,246 m |
| 0.073 | T05 Rev 2 upper case, 30.1 GW | 43,668 t (+1.8 %) | 3,693 t | 0.498 km² | 10,359 m |

**Result: the coil interception is a real load of 12-16 GW but a small mass penalty, under 1 % on the expected basis.** It is not a
blocker. The penalties that still dominate are the coil structure (855-1,281 t at V1 scale, unbooked) and C1's local flux of
7.8 MW/m², which needs the pumped loop. The proxy books the heat but not the coil cooling plant's own mass or pumping (about 24 MW,
T05 Rev 3).
