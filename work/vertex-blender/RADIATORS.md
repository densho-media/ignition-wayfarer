# Radiator architectures for Vertex V4 (T05 Stage A review)

NON-CANON. Numbers: `screen.py` → `screen.json` (`V4_radiator_alternatives`, `V4_hot_band_mitigations`, `V4_wing_loads`), unless a
row names a `results/convergence.json` case. Labels as in `planning/HANDOFF.md` (MODEL, EXTRAPOLATION, TARGET, UNKNOWN).

## 1. What the radiator has to do

V4 rejects 78.6 GW of warm heat at an equivalent 628 K (T01 circuit ledger, TARGET components) and 495 GW of hot heat at 1,800 K.
At emissivity 0.9, two-sided, that is 4.95 km² of warm planform and 0.462 km² of hot band (`ResultArithmetic` checks both sides).
The calculator's layout, W2, puts both on two half-planes at azimuth 0° and 180°, chord X −178.75 to +88.0 m (266.75 m), so each
wing runs from r 10 m to a **10,128 m tip** (1,800 K band r 10-847 m, then the 628 K field). The span is 20.3 km, 70 times the
canonical ship's length. Stage B draws exactly this; nothing below shrinks the area.

## 2. Two geometric rules that decide every option

1. **Edge-on to the burn.** Every surface outside the 5.5° hardware cone must contain rays from the burn point, or it sits in the
   burn's sky (X-rays, 412 GW escaping). Half-planes through the ship axis satisfy this; so does any cone with its apex at the burn.
   A disc or ring radiator square to the axis does not.
2. **Edge-on to the dust.** At 0.016 c the dust arrives along the axis (bow-first in coast and acceleration, engine-first in braking,
   T02). A half-plane presents only its leading edge: about 202 m² per centimetre of edge thickness for the two V4 wings. A cone
   presents its whole annulus.

Only half-planes satisfy both. That is why the calculator's W2 form is right in kind, and why the alternatives below vary the
number of planes, their chord, the surface technology and the heat load, rather than the shape.

## 3. Alternatives screened

| ID | Architecture | Warm planform | Tip radius | Leading edge (m² per cm) | Verdict | Label |
| --- | --- | --- | --- | --- | --- | --- |
| R0 | W2 flat wings, tin droplet sheet 0.5 kg/m² (V4 as calculated) | 4.95 km² | 10,128 m | 202 | baseline, drawn | MODEL |
| R1-W3 | three wings between the canon blades, view-factor penalty ×1.15 | 5.72 km² | 7,712 m | 231 | shorter by 24 %; mass not re-closed | MODEL (layout) |
| R1-W6 | six wings, penalty ×2.00 | 9.90 km² | 6,476 m | 388 | area doubles for −36 % span: poor | MODEL (layout) |
| R2 | tandem W2: aft wing plus a second wing on the T-B stretch (X 142.9-413.3 m, 270 m chord) | 4.95 km² | 5,456 m | 218 | halves the span with no new physics; needs the T-B stretch and a second manifold set | EXTRAPOLATION (geometry) |
| R3 | equivalent warm temperature 670 K (`V4_warm_band`) | — | 6,700 m | 134 | 35,949 t; needs hotter cores (T01) | MODEL |
| R4 | driver efficiency 0.45 (`V4_driver_band`) | — | 3,400 m | 68 | 25,319 t; the strongest lever, and it is not a radiator | MODEL |
| R5 | heat pump lifting the warm loop to 1,000 K | 1.23 km² | 3,146 m | 63 | needs 47 GW extra electric at the Carnot limit (about 90 GW real) against 110 GW of driver input: rejected | EXTRAPOLATION |
| R6 | coaxial cone with its apex at the burn, 15° / 30° | — | mouth r 904 / 1,256 m | frontal 2.6 / 5.0 km² | edge-on to the burn, but a dust scoop: rejected | EXTRAPOLATION |
| R7 | propellant as heat sink | — | — | — | 0.15 kg/s absorbs about 1.3 MW against 78.6 GW: rejected | EXTRAPOLATION |

Surface technology (T01 §3.6, same planform in every case):

| Technology | kg/m² | Band | Dust (T02) | Retraction | For V4 |
| --- | --- | --- | --- | --- | --- |
| Tin droplet sheet (VTX-07B) | 0.5-0.6 with generator and collector | 520-1,000 K | most tolerant: a grain punctures a liquid; about 1 kg lost per burn | stop the flow | the V4 mass basis (TARGET, D-05). Drops fly along −X, so thrust changes their speed, not their path |
| 1.5 kg/m² panels | 1.5 (TARGET) | to about 700 K | punctures isolate one pipe; bumpers on edges | fold | +3 % on T01's planning ship; drawn as an alternate skin |
| Today's panels | 3-6 | by band | as above | fold | 123.5 kt (`V4_warm_band` panels): does not belong in V4 |
| Liquid belt radiator | about 1-2 (EXTRAPOLATION, 1980s-90s NASA concept) | 300-1,000 K | belt tolerates small punctures; rollers exposed | roll up | CONCEPTUAL: a retractable cousin of the sheet; no Wayfarer number |
| Electrostatically held dust or Curie-point droplet cloud | UNKNOWN | UNKNOWN | UNKNOWN | collapse the field | CONCEPTUAL_ILLUSTRATION overlay only |

T02 found that retracting the warm wings during braking does not help, because the driver loss (75-95 % of the warm heat) cannot
wait during a burn, and the burns fill 5.69 of the 6.35 mission years. Retraction is therefore a maintenance and coast feature, not
a dust defence. The droplet sheet's dust tolerance is the stronger argument.

## 4. What the hot band does to its neighbours (new, Stage A screen)

The calculator places the 1,800 K band along the whole chord at the wing root, so its forward edge (X 88.0 m) stands 7.2 m from ring
A's aft sweep face (X 95.15 m), and its aft edge 9.6 m forward of closure coil C1 (X −188.3 m, r 22.1 m, where C1 crosses the wing
plane inside the band's radius). Diffuse irradiance from the band, by numeric view-factor integration (ε 0.9, worst point):

| Receiver | Calculated layout | Hot band aft of X 48.9 m (same area, r 10-991 m) | Also 20 m clear of C1 (X −163.5 to 48.9, r 10-1,061 m) |
| --- | --- | --- | --- |
| Ring A aft face | 173 kW/m² | 57 kW/m² | 56 kW/m² |
| C1 envelope, facing the wing | 91 kW/m² | 90 kW/m² | 30 kW/m² |

For scale, the same integration gives the canonical 1,800 K blades about 65 kW/m² on ring A's aft face (three blades, each at its
worst angle: an upper bound), and sunlight at 1 AU is 1.36 kW/m². Canon already moved its hot blades 44.5 m away from the rings (Graded
Thermal Blade). **Recommendation for Stage B:** draw the calculated layout and beside it the chordwise-graded layout (hot band only aft
of RADIATOR_FRONT, X 48.9 m, as canon; 20 m clear of C1; cooler circuit bands, capacitors at 550 K, in the forward root corner by the
rings). The area does not change, so neither does the mass. Thermal loads on ring A and C1 go to T01 and T03 as T05-ISS-001 and -002.

## 5. Structure (screen)

A V4 wing (sheet 0.5 kg/m², hot band 1.5 kg/m², two 12.5 kg/m spars) is about 1,826 t. At peak acceleration (0.0187 g) the load is in
the wing's own plane: 0.34 MN, root moment 1.7e9 N m, a 6.4 MN couple across the 267 m chord. A free-flying droplet sheet does not load
the spars this way (its drops are not attached), so the real load is lower. Deployment, slewing, vibration and the 10 km compression
spar's buckling are not modelled (EXTRAPOLATION, T05-ISS-005).

## 6. Recommendations

1. Keep W2 half-planes as the V4 form, drawn at full area. They are the only form edge-on to both the burn and the dust.
2. Draw the droplet-sheet frame (generator bar on the forward edge, collector on the aft edge, perimeter truss, sheet as a translucent
   CONCEPTUAL overlay) as the main skin, and 1.5 kg/m² panels as the alternate.
3. Adopt chordwise grading as a Stage B requirement (section 4).
4. Show R1-W3 and R2 (tandem) as outline alternatives in one camera: they are the two geometric ways to shorten the span without new
   physics. R2 is the more attractive (−46 % span at equal area) but only exists with the T-B stretch.
5. Show the load levers as ghost tip circles on the span camera: 670 K (6.7 km), driver 0.45 (3.4 km), and the warm band's 6.7-14.5 km
   bracket from T05_HANDOFF. They say more about the design than any radiator shape: the driver is the radiator problem.
6. Do not draw R5-R7 as geometry. Record them as negative results.
