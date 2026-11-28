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
