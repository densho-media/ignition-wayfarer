<!-- lab entry -->
| Lab entry | |
| --- | --- |
| Kind | Variant |
| Status | SUPERSEDED by TANK-AXIAL (main 90df1a9) |
| Question | 343.5 m layout with split forward/aft storage, radiator zoning, RCS pods and functional colours. |
| Model base | main 702ff62 |
| Salvaged from | claude/project-thread-pw21o2 @ 741c38d, 2026-11-06 |
| Open owner questions | None. Its radiator zones, RCS and colours were ported to main; only NOTES and the study are kept, not its generator edits (git show 741c38d). |
| Review | project files review/redesign_2026-11-01/ |

# redesign_layout: layout, storage split, radiator zoning, RCS and functional colours

Owner brief 2026-11-01 07:13Z (ApeDevil). Branch `claude/project-thread-pw21o2`, based on main 702ff62 (pass 7, full return).
Numbers: `python3 lab/variants/redesign-layout/study.py` writes `study_results.json` next to this file. Everything here is PROTOTYPE
screening by Claude under the owner's delegation (2026-10-31: science decisions from research, HSFP rules); none of it is
flight qualification.

## Function

Front to aft: Shield/EYE, forward service district (Brow, forward H2 torus, docking, refuge, airlock, bypass collar), the two
habitat rings, aft storage district (four single-species tori), the radiator district (LOW 300 K, WARM 440 K, HOT 1800 K
blades) and the drive. The crew district reads open: the Q38 warm panels round the rings are gone (`candidate_panels.enabled
= false`); the three blades now start 54 m aft of the rings.

## Fixed constraints (kept)

- Full-return inventory and species (pass 7): He-3 1,094 t, D 731 t, H2 972 t; nothing reduced.
- One core/manifold, four nozzles; blades 182.149 x 30.5 m between r 6.5 and 37 m, three planes; shield 90 m; rings 30 m.
- High-speed attitude rule: shield axis on the velocity vector; RCS trims only.

## Decisions

1. **Ship 245 -> 343.5 m** (355.5 m with the Lance; envelope max raised 260 -> 360 m). Datums: AFT -171.75, hot blade
   -160.25..21.90, zones to 66.40, aft storage to 120.40, ring A 124.30, FWD 171.75.
2. **Storage split: small forward, large aft (adopted).** Forward torus H2 325 t (R 20.5, a 4.5, X 159.85, 78 % fill);
   aft He-3 A/B 547 t each (X 111.9 / 98.4), D2 731 t (X 86.8), H2 647 t (X 75.2), 83-87 % fill. One species per torus, three
   vessels per torus, separate cryocooler per torus gap, two relief vents per vessel (radial, between the blade planes).
   Allowance 6 % on the liquid (ullage 4, residual 1.5, boil-off reserve 0.5). He-3 (coldest) is the forward-most aft torus,
   H2 next to the LOW section.
   Balanced split (both He-3 tori ahead of the rings) compared: forward spine compression aft of ring A 10.5 MN vs 4.2 MN,
   CG travel 53.8 vs 45.6 m, rings 74 m behind the shield instead of 47 m (longer docking-to-ring path, worse ring shadow
   margin), I_pitch similar. Rejected.
3. **Radiator zoning.** LOW 300 K, 1.0 MW (cryocoolers + stationary avionics), 19.5 m; WARM 440 K, 5 MW machinery base load,
   21 m; HOT unchanged. Own booms, trunks, valves per section and blade; 2 m non-emitting breaks; a two-layer baffle annulus
   (eps 0.08, 0.10 m casing gap) at each break. Without baffles the cooler sections absorb 6-9x what they emit in a burn;
   with them WARM keeps 96 %, LOW 99.9 %. The crawler passes the baffle through a gate opened only in the coast.
   F02 reconciled: the WARM section carries the always-on machinery base load; defense heat keeps the F02 modes (heat-pumped
   into HOT in a burn, drain-back channels in the dark blades in the coast); the habitat cold loop stays on the rings. The
   radiating warm casing stays along the hot blades only; the casing beside LOW/WARM is MLI-wrapped.
   Heat pumps: optional comparison only (1 MW LOW pumped to 440 K: ~1.3 MW work, +10 m WARM, -19.5 m LOW); not adopted.
4. **RCS.** Existing 3 aft pods (radial + 2 tangential) and 4 rim pods behind the shield kept; added an axial aft jet per aft
   pod (+X, 20 deg cant) and a forward-outboard jet per rim pod (-X, 50 deg cant) for translation and docking. All jet cones
   clear rings, blades, zones, tori, shield, hull and comms sweeps (`exterior_hardware.jets`).
5. **Functional colours** (`functional_colors.py`, applied in `common.save`): every generator-owned object's viewport colour,
   STORAGE and THERMAL functional sub-collections, asset collection tags, legend text in every file. Production materials untouched.

## Results (study_results.json)

- Mass: departure 4,466 t, CG X 72.6 m, I_pitch 2.97e10 (pass 7 1.59e10); after the four burns 3,488 / 2,726 / 2,132 /
  1,670 t, CG 65.0 / 55.2 / 42.8 / 27.0 m. Lateral CG 0 by design (equal vessels; forward torus balanced per vessel).
- Drawdown order (first burn): aft-first keeps the CG 2.4 m further forward than proportional; forward-first 5.6 m further aft.
  Proportional kept (no transfer needed); order is a free operational lever.
- Spine: 20.4 MN at the drive, 17.9 MN at the zone front, 4.3 MN at ring A (pass 7: 15.2 MN), 2.2 MN at the forward collar.
- Bipods: forward torus buckling margin +47 %, aft tori +450 % to +2,700 %.
- Aft-bank heating: LOW plates put ~100 W/m2 on the aft H2 torus face (view factor 0.11), MLI leak ~0.3 W/m2, ~0.47 kW
  more cryocooler load. Drive neutrons (1 % of 261 TW): 3.7 MW/m2 unshielded at the aft bank (pass 7 return torus 5.0 MW/m2),
  so the shadow shield needs 6.6 decades either way; the aft bank is farther from the plasma than the pass-7 return torus.
- Shield shadow (geometric): limit is the hot blade aft edge, 8 m margin over 332 m: 1.38 deg (pass 7: 1.99 deg). Zones and
  baffles 3.1 deg, aft tori 9.5 deg, rings 16.8 deg. Not ejecta or secondary-radiation protection.
- RCS: 180 deg flip 58 min at departure, 50 min depleted, 82 min with one end pod out; 236 kg per flip at 300 s.
  Translation 0.06 mm/s2 either way at departure (0.1 m/s in ~29 min): station-keeping only; visiting craft close.
- Added dry mass (not in canon): plates ~20 t, baffles ~20 t, 98.5 m spine ~50 t, vents and cryocoolers ~7 t: ~98 t, which
  would need ~167 t more propellant (+6 %) for the same delta-v. Inventory kept as is; budget OPEN.

## Isolation benefits and new failure paths (honest)

Benefits: a vessel leak or rupture loses one vessel of one species (max 243 t D, 216 t H2, 182 t He-3) instead of a mixed
vessel; species never meet in a common volume; a cryocooler failure warms one torus; the crew rings have only 325 t H2 ahead
and no tank aft within 4.75 m of ring A's sweep.
New paths: 15 vessels, 30 vents, 12 cryocoolers and longer feed lines (forward H2 line 244 m) mean more joints and valves;
the aft bank sits 3.3 m from the LOW section (heat leak above); the spine between the banks carries the aft bank's inertia;
baffle damage re-exposes LOW/WARM to the hot blades (net heating within seconds of a burn: interlock the burn on baffle health).
Splitting does not make the ship safer by itself; it trades one large failure for more, smaller ones.

## Unknowns (OPEN)

Reactor shadow-shield mass and cone; baffle structure and crawler gate; vessel wall, MLI and cryocooler capacity; ejecta
cone model; added dry mass in the canon budget; LOW/WARM loads beyond the PROTOTYPE 1 / 5 MW; D04 larger airlock (still a
study); C01/K01 reviews.
