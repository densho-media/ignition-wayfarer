# T05 Stage B Revision 2: Vertex layout conflicts

| | |
| --- | --- |
| Thread | T05, mechanical architecture and spacecraft geometry |
| Date | 2026-11-09 |
| Status | DONE (Revision 2); stops before detailed modelling, waiting for owner review |
| Base | `7791796` (Stage B revision 1) on `claude/project-thread-ctwplp` |
| Review file | `REVIEW_VERTEX_BLENDER.blend` (packed, opens on `COMPARE_SIDE_BY_SIDE`; not in Git); copy and renders in the project folder `review/vertex_blender_rev2_2026-11-09/` |
| Numbers | `rev2.py` → `rev2.json` (screening, standard library); `axis_survey.py` → `axis_survey.json` (ray survey of the canon axis); placements in `checks.json` `rev2` |

NON-CANON research geometry. Canon, Drive, production assets, the propulsion calculator and the T01-T04 results are unchanged.
Nothing here claims V4 is viable; the preferred options are layout choices for review, not adopted designs.

## 1. What the model now holds

- `ASM_V4`, the **preferred Rev 2 layout**: launcher B, graded wings, coil armour P2 with sized C1 struts, skirt B2, the spine
  continuation across the T-B stretch, docking and EVA routes. The canon 1,800 K blade sections are left out of V4.
- `ASM_V4_REV1_LAYOUT`: the Rev 1 layout complete, for comparison (calculated wings, the canon blades, the 20 m launcher, skirt A).
- `ASM_V0`: the historical Rev 1 layout, plus the spine continuation.
- Every alternative is its own collection, `OPT_VERTEX_V4_*`. They are all kept in the `OPTIONS_LIBRARY` scene and linked into an
  assembly or a comparison lane, so swapping one is reversible.
- New scenes: `LAUNCHER_COMPARE`, `THERMAL_COMPARE`, `COIL_COMPARE`, `SKIRT_COMPARE`, `OPTIONS_LIBRARY`.
- New cameras `CAM_VTX_20` to `31`. `VERTEX_CUTAWAY` now shows launcher B and armour P2.
- Every object carries the same tags as Rev 1, with `revision = 2`.

## 2. Launcher (ISS-009): B preferred

The governing rule is that any target on a straight line to the burn at a pulse instant is destroyed: each pulse releases
2.10 GJ of X-ray every 5.11 ms, which is 7.8 MW/m² at the shield face. A target must cross the whole open line of sight within one
pulse interval, so v ≥ open length × 195.7 Hz, and the accelerator itself must sit behind a chopper that is closed at every pulse.

| | REV1 | A axial | **B shielded snout** | C offset |
| --- | --- | --- | --- | --- |
| accelerator | 20 m | 269 m (breech X 85 to shield face) | 289 m (to snout tip) | 65 m, inclined 2.65° |
| open line of sight | 68 m | 64.7 m | 45.0 m | 64.8 m |
| exit speed | 13.39 km/s | 12.66 km/s | 8.81 km/s | 12.68 km/s |
| acceleration | 457,000 g | 30,300 g | 13,700 g | 126,700 g |
| D2 shell stress / margin* | 48 MPa / 0.06 | 3.2 MPa / 0.9-1.1 | 1.45 MPa / 2.1-2.5 | 13.4 MPa / 0.2-0.3 |
| targets in barrel | 0.6 | 8.3 | 12.9 | 2.0 |
| electric power (η 0.4) | 108 MW | 97 MW | 47 MW | 97 MW |
| mass (0.5 t/m, PROTOTYPE) | 10 t | 135 t | 145 t | 32 t |
| shield penetrations | bore | bore | bore | bore + a second one |
| conflicts | FDP-1 magazine, LiH plug | spine bore services; breech plug 4.6 m from the crew trunk | as A; snout tip is a new plasma-facing part | passes the canon thrust ring at r 4.84 m (ring r 5-6 m) |
| status | FAILED | CANDIDATE | **PREFERRED** | REJECTED |

\* Margin against the 2.75-3.3 MPa implied by bare D2 pellets fracturing at (5-6)×10⁶ m/s².

- **Several targets in the open path are rejected.** At 2, 3, 5 and 10 targets in the open, the nearest one is 32, 22, 13 and 6.5 m
  from a pulse. It absorbs 15.5, 35, 97 and 388 times the He-3 boil-off budget (about 4.6 J). The budget would only be met beyond
  about 1,270 m.
- **The breech moves to X 85 m.** That is behind the shield and the module, inside the spine, aft of the rings. The LiH bore plug now
  sits behind the breech, 4.6 m from the crew trunk (built placement).
- **B's snout.** It extends the shielded bore 19.7 m aft of the shield, so the open path shrinks to 45 m. The tip takes 16.2 MW/m²,
  2.07× the shield face, so it is a replaceable W cartridge carrying the chopper (ISS-016).
- **Snout sweep.** Moving the tip from 64.7 m to 55, 45, 35 or 25 m from the burn changes:

  | Tip distance from burn | 64.7 m | 55 m | 45 m | 35 m | 25 m |
  | --- | --- | --- | --- | --- | --- |
  | Exit speed | 12.66 km/s | 10.77 km/s | 8.81 km/s | 6.85 km/s | 4.89 km/s |
  | Acceleration | 30.3k g | 21.2k g | 13.7k g | 8.0k g | 3.9k g |
  | Tip flux | 7.8 MW/m² | 10.8 MW/m² | 16.2 MW/m² | 26.8 MW/m² | 52 MW/m² |

  45 m is chosen as the knee.
- **UNKNOWN.**
  - Target survival at 10⁴ g, even with a sabot. Published IFE injectors are designed for 100-1,000 g at 200-400 m/s; the sabot
    record is 3.8 km/s.
  - The 196 Hz chopper (neutron T0 choppers are the nearest precedent).
  - Placement accuracy at the burn point (tracker plus beam steering).
  - Sabot return, 28.8 t/day.
  - Last-flight radiant heating of about 2.7 J from the 1,800 K face (black target), which needs a reflective target.
- **Space and maintenance.**
  - The barrel takes the axis of the spine bore, which canon gives to distributed stationary services.
  - The conditioning station and breech loader sit outside the spine at X 80-86 m.
  - The tip cartridge is exchanged from the shield-face rail.

## 3. Thermal (ISS-001/002/010): graded layout, canon blades retired in V4

- **No double count in the calculator.** The V4 hot planform (461,619 m², 494.6 GW) already includes the canonical blades' 14,935 m²
  (3.2 %) as reused area plus a 446,684 m² wing extension. The Rev 1 working copy drew both, so the model double counted, not the
  calculator.
- **The blades are retired, not given a new job.** Their canonical source (the Fiji drive's 1,800 K loop) is superseded. Kept beside
  the wing, they see its hot band at 485 kW/m² against 536 kW/m² emitted, a 90 % net loss.
  - Rev 2 leaves the 115 blade objects out of the V4 working copy and moves their area into the graded wing.
  - The canon WARM and LOW zones stay. They serve habitat and house loads that are not in the T01 ledger.
- **Graded layout.**
  - The hot band runs X −163.5 to 48.9 m at r 10-1,096 m, the same 461,619 m².
  - The forward root corner (X 48.9-88 m) becomes a 550 K warm circuit, 84,964 m², counted in the warm area.
  - The tip moves to 10,218 m, so the span grows by 180 m to 20,435 m.
- **Irradiance.**
  - Ring A drops from 173 to 56 kW/m², with the hot band now 46 m from it.
  - C1 drops from 91 to 30 kW/m².
- **Structure.**
  - The 1,800 K / 628 K thermal break becomes an L: spanwise at r 1,096 m and chordwise at X 48.9 m, with a chordwise expansion joint.
  - The spars see 1,800 K over 212 m of the 267 m root chord.
- **Tandem W2** stays an outline alternative. It is not adopted for its span.

## 4. Closure coils (ISS-003/012/014)

- **The X-ray load is fixed.** What C1 and C2 intercept is set by their solid angle as seen from the burn:
  - C1: 10.5 GW on 1,335 m².
  - C2: 19.7 GW on 2,510 m².
  - Total 30.1 GW, unbooked, about 28,100 m² of extra hot radiator.

  No protection option reduces this. Only smaller or farther coils would.
- **The options.**

  | Option | What it is | Mass |
  | --- | --- | --- |
  | P0 (Rev 1) | warm screen only | — |
  | P1 | one sacrificial shoe per coil | 174 t at the loops' 45.2 kg/m² |
  | **P2 (preferred)** | 12 replaceable segments per coil on low-conductance stand-offs in front of the warm screen, handling posts for robotic exchange | the same 174 t |

  - P2 heat goes into a cooled armour circuit rather than the cryostat, and P2 matches the loop exchange units.
- **Supports.** Six CFRP struts, r 0.8 m, 14.2 m long:
  - 1.9 GN case: wall 105 mm, 72 t, buckling 1.23 GN per strut against 0.32 GN.
  - 0.2 GN case: 7.6 t.
  - They intercept about 1.07 GW.
  - The 3-7 GN hoop, the 855-1,281 t coil structure and the shield frame's reaction remain unbooked. These struts show the order of
    the problem; they are not a structural solution.

## 5. Dust and docking (ISS-004/011)

Dust arrives along −X while braking, so a skirt's shadow is a cylinder of its edge radius.

| skirt | edge X | shadow r | mass | dock/EVA penetrations | exposed while braking |
| --- | --- | --- | --- | --- | --- |
| A full | 218.3 m | 45.0 m | 22-90 t | 3 | none |
| **B2 dock-clear (preferred)** | 125.05 m | 36.0 m | 14-57 t | 0 | forward-shield back 2,285 m² |
| B short | 85.15 m | 32.2 m | 11-45 t | 0 | farm 486 m², forward-shield back 2,622 m² |
| C none | — | 7.2 m | 0 | 0 | ring A 864, farm and tanks 3,551, forward-shield back 2,622 m² |

- **B2 clears the docks.** It ends 3.6 m aft of the docking corridors.
- **B2 meets the bypass collar.** It crosses the Q45 bypass collar (r 33-35 m) between X 93.6 and 114.3 m, so it should mount there.
- **Attitude.** A 1° error loses 5.0 m of shadow at the T-B front, against a 1.5 m tank margin. That needs about 0.3° attitude hold.
- **Configurable.** Destination and heading stay inputs to `rev2.py` (dust direction is the braking axis).
- **Routes.** The docking corridors (3 m, az 195° and 315°) and the EVA airlock route are drawn and stay clear.

## 6. Scale (true scale, nothing shrunk)

- **Size.** V4 is 766 m long (X −346 to 420 m) and 20.4 km across the wings with the graded layout.
- **New: no primary structure across the T-B stretch (ISS-013).** The canonical spine ends at X 140.75 m. The bow (forward shield
  included) is shifted 275.4 m forward, so nothing carries it. Drawn: a PROTOTYPE spine continuation, three sector longerons at r 5 m
  inside the tanks' 7.75 m inner edge, and bay frames every 28.6 m.
- **New: no access to the bow (ISS-015).** The crew trunk ends at X 134.7 m, 281 m short of the bow. Drawn: a 0.8 m crawlway.
- **Other measurements.**
  - Drive galleries X −145 to 82 m; module X −181 to −145 m.
  - Launcher B breech 10 m aft of ring A's hub.
  - Docks 43.7 m forward of the wing edge.

## 7. Research needed (documented; layout work continued)

1. Cryogenic target survival at 10³-10⁴ g with a sabot, and the shell's real strength. A solid-D2 strength value was not found. A
   LANL slide quotes 120 MPa for DT; this is UNVERIFIED.
2. A 196 Hz chopper or shutter at 8-16 MW/m², and the life of the snout tip cartridge.
3. Placement accuracy over the 45 m open flight.
4. Sabot recovery and reuse at 28.8 t/day.
5. Irradiance limits for the ring faces and the C1 warm screen.
6. The coils' 30 GW: armour cooling circuit, or a coil geometry with a smaller solid angle (T03).
7. Spine continuation and forward-shield load path sizing.

Sources:
- [Petzoldt, IFE target injection (ARIES)](https://aries.pppl.gov/MEETINGS/0009/Petzoldt.pdf)
- [Target injection review](https://m.researching.cn/articles/OJ1cb2bb05029f5fa3)
- [Target injection, Laser and Particle Beams](https://www.cambridge.org/core/product/0E9A9F64F513AC576B95490D8DBFC5D3/core-reader)
- [Pellet acceleration limits (OSTI 5588343)](https://www.osti.gov/biblio/5588343)
- [Sabot pellet injection (Fusion Sci. Technol.)](https://www.ans.org/pubs/journals/fst/article-19907/)
- [OSTI 7043184](https://www.osti.gov/servlets/purl/7043184)
- [Hoffer, HAPL target slides (DT strength, unverified)](https://aries.pppl.gov/HAPL/MEETINGS/0111-HAPL/hoffer.pdf)

## 8. Review views

| view | camera |
| --- | --- |
| launcher comparison | `CAM_VTX_20`, breech `22`, snout cutaway `21` |
| graded vs calculated hot band | `CAM_VTX_23` (top), ring detail `24` (calculated) and `25` (graded) |
| coil protection and structure | `CAM_VTX_26` (P0/P1/P2), `27` (P2 in place) |
| skirts and docking | `CAM_VTX_28` (A/B2/B/C), `29` (B2 at the docks) |
| whole ship at true scale | `CAM_VTX_30`, compares `01`-`04`, spine stretch `31` |

Workbench renders show form and fit only.

## 9. Recommended next step

Before detailed modelling, two numbers decide whether this layout survives:

- **The target's tolerable acceleration (T04).** If it is under about 4,000 g, the snout must reach 25 m from the burn at 52 MW/m².
- **The coils' 30 GW (T03).**

Then size the spine continuation (ISS-013), which carries the forward shield.
