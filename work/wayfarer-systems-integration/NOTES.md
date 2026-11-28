# WSI — Wayfarer Systems Integration (joint ISSA–PSA), Phase I

| Field | Value |
| --- | --- |
| Kind | integration study (work in progress) |
| Status | ACTIVE — CP1 shared foundation |
| Question | Does one coupled ISSA + PSA spacecraft (Track F1) converge, and which structure and propellant layout close it? |
| Model base | ISSA WF-F1-C1.1 (8b30b71, SSI-1.1, register v1.2) + PSA Phase II c3138d8 / Phase III.0 1beb693; main 11f1e94 read only |
| Owner questions | collected in CP4 |

STUDY / PROTOTYPE, Track F working configuration, noncanon. Production geometry, `data/` parameters and Drive are unchanged.

## Ownership (one integration session)
This thread owns the joint configuration `results/wsi_config.json`, the coupled loop and the propellant candidates. PSA runs its
structural analyses in `work/primary-structural-architecture/phase3/` on its own branch, reads only the WSI config, and its results
are merged here. No other session edits shared geometry, configuration or mass.

## Run order
    python3 work/wayfarer-systems-integration/wsi/foundation.py     # CP1: wsi_config.json (WSI-0.1), wsi_cp1.json

## CP1 — shared foundation
- Config WSI-0.1 holds every §5 category once: coordinates, dimensions, topology (PSA H hub, 6 paired rails), materials, propellant
  and tanks (T-A), equipment and mounts (SSI-1.1), load cases (SSI + PSA LC ids), thermal interfaces, utility routes, maintenance
  envelopes, keep-outs, technology dependencies, structure (PSA by family), mission.
- Starting points reproduced:
  - S-ISSA C1.1: 9,078.4 t, 315.0 m (exact).
  - S-PSA Phase II H:hub:F1: 12,352 t (PSA's scaled coupling on CP4 stations, no farm resize).
  - S-COMB C1.1 + PSA structure: 13,212 t, 338.3 m, propellant 8,348 t, end accel. 0.456 g. C1.1's one-pass figure was 13,193 t;
    the difference (+19 t) is cryo and radiators re-iterated for the longer farm.
- Joint ledger closes to the coupled departure (13,212.0 t both ways). Two double counts removed: the production 150 t structure
  line (replaced by PSA's 1,222.9 t) and the production tankage rows (329.5 t, inside the re-solved tankage).
- Not yet physically satisfied: PSA global stability lambda 0.71 static / 0.68 follower against 1.95 (CP2).

    python3 work/wayfarer-systems-integration/wsi/coupled.py        # CP2: wsi_cp2.json (loop, ROM, rail materials, propellant, profiles)
    python3 work/wayfarer-systems-integration/wsi/members.py        # CP3: wsi_members.json (PSA TD-A members, checks, deflections)
    /snap/bin/blender -b assets/wayfarer/WF_WAYFARER_001.blend --python work/wayfarer-systems-integration/wsi/make_review_wsi.py -- --render
    python3 work/wayfarer-systems-integration/wsi/remaining.py      # CP4: wsi_remaining.json (C-01, C-11, C-14)
    python3 work/wayfarer-systems-integration/wsi/review.py         # CP4: wsi_cp4.json (PSA closures reconverged, ledger)
    python3 work/wayfarer-systems-integration/wsi/build_page.py     # wsi.html + wsi_register.json

## CP2 — coupled architecture
- Coupling: about 3.9 t of departure per tonne of dry mass (propellant, tankage, cryo, radiators).
- PSA FE on S-COMB (TD-A, 1,157 t): lambda 0.63/1.02 (static/follower) at departure. TD-D is the lightest deck (976 t), TD-F (bypass) the stiffest.
- ROM (planar beam, f1 matched to the FE): the global beam is not the governing mode. The governing modes are local: farm walls and deck, the aft thrust structure, the hub.
- Rails in Track R CFRP-HM carry the stiffness for about 270-350 t less than Al. FT-10 (CNT) is a sensitivity only.
- Propellant: T-A stays. T-B costs +0.8 kt. G is not feasible outside the excluded zone.
- Profiles: 0.016 c 13.2 kt, 0.014 c 10.5 kt, 0.012 c 8.4 kt (ships sized for each).
- PSA audit 13:04Z: with thrust on the nozzle pickups, the lambda-closed HM designs fall to 0.72-0.80. Closure stays OPEN (runs *_noz).
  TVC spillover needs a notch filter or an IMU at the node; the 2x spin sits on the second bending pair.

## CP3 — integrated geometry
- 4,938 members checked. The hub-cone aft legs crossed the MRU lane; PSA omitted them, and the rail end stays at 92.0.
- Departure deflection: 47.8 mm radial (rule 50 mm), 619 mm axial (taken by the slides).
- REVIEW_WSI_CP3.blend has 16 view layers and is regenerated from the JSON (not in Git).

## CP4 — whole spacecraft
- C-01: dedicated 2.4 t shutdown store (Track R). The defense buffer keeps 209 MJ. The transient stays OPEN.
- C-11: He-3 at 3.0 K with the consistent density 61.6 kg/m3 and 8 % ullage allows +0.3 K. The EOS check is pending.
- C-14: LOW +350 m2 at the joint point; re-cool capped at 100 % with one loop lost.
- Full pipeline PASS, geometry diff 0 (runs/20261128T125441Z-pipeline).
- PSA nozzle-thrust closures (a43e132): bypass HM 1,275.9 t FE reaches lambda 1.95, but f1 is 0.091 Hz at departure (target 0.095). Hub HM is 1,413.5 t, f1 0.084.
  The reconverged bypass point is 13,615 t / 340.6 m, +3 % over the sizing point, so loads still have to be re-sized there. f1 closure is OPEN.
- PSA f1 continuation D_byp_ring_HM_nozf1 (a2d08ee): 1,284.9 t FE, lambda 1.95-2.01 and f1 0.0950 Hz at departure, so the structure closes.
  The reconverged point is 13,649 t / 340.8 m, +3.3 % over the sizing point. Still open: the forward end frame:14/diag:14 (local, a few t),
  a re-size at the new point, and TVC robustness (unstable with an aft IMU, 3x delay or damping 0.002).
- PSA lead D_byp_ring_HM_lead (dd6b3dd) closes the end fitting: 1,283.0 t FE, lambda >= 1.99, f1 >= 0.098 Hz, and no member is strength-short.
  The reconverged point is 13,642 t / 340.7 m. Still open: one re-size at the new point, and TVC robustness (notch or node IMU in Phase IV).
