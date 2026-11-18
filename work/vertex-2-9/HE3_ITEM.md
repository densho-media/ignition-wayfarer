# PROPOSED Economy / Technology item: helium-3 supply for the Vertex research reference

Status: APPROVED FOR AUTHOR REVIEW (owner O3, 2026-11-18; proposed under Q4, 2026-11-17 13:26Z). No source is canonized; lunar
extraction, D-D breeding and other options stay alternatives. The storage-volume question is routed as an S&E research-queue item
(`work/vertex-2-10/SE_QUEUE_HE3_STORAGE.md`). Draft for the owner; nothing is written to the Drive workbooks (Vertex 2.9
development constraint), no canon inventory is changed and no supply chain is created. If accepted, this text is the content of a new
row in Economy & Currency (`42_SPACE_ECONOMY` or `80_OPEN_VARIABLES`) and Technology (`43_SPACE_MANUFACTURING` / `60_OPEN_VARIABLES`),
routed through the request Doc as a dated item.

## Requirement

| Case | He-3 burned per mission | vs canon load 1,094 t |
| --- | --- | --- |
| B2d conditional research reference, 5 % delta-v reserve (Vertex 2.8) | 2,084 t | +990 t |
| B2d without reserve | 1,871 t | +777 t |
| Range to plan for | 1.9-2.1 kt | +0.8-1.0 kt |

Vertex 2.9 (reduced hybrid, not validated) does not narrow this: its only closing runs need 1.9-2.3 kt (5,798-6,519 t departure), and
most runs do not close at all. The fuel is carried aboard; this item only asks where it comes from.

## What canon already says (read 2026-11-17)

- Technology `43_SPACE_MANUFACTURING` ISM-29..32: Luna Lift, Luna Harbor -> Luna Yard cargo chain and the Luna Yard fabrication lattice are
  established at Y155 (numerics open); ISM-07 regolith processing is ground research in 2026; ISM-16/21 forbid arbitrary matter replication.
- Technology `40_ENERGY_PROPULSION`: fusion stays difficult engineering; no He-3 row.
- Economy `30_SCARCITY_VALUE`: energy, mass and delta-v stay scarce. No He-3 market, mining or price row exists anywhere.
- S&E `62_FUEL_STORAGE_STUDY`: liquid He-3 58.61 kg/m^3 at 3.2 K (REFERENCE SCREEN); BODY-C3 grouped cryostat study 4,072 m^3 liquid
  capacity for all species (CLAUDE PROTOTYPE).

## Production options (literature ranges, all to be owner-chosen)

| Route | For 2.0 kt | Main constraints | IGNITION fit |
| --- | --- | --- | --- |
| Lunar mare regolith, 15 ppb (5 ppb), 80 % release at ~700 C, 3 m deep | ~1.7e11 t processed (5e11), ~37,000 km^2 (110,000) | throughput, heating ~8 % of the fuel's fusion energy, dust, volatile capture | builds on the established Luna industrial chain; scale is planetary |
| D-D fusion breeding (He-3 branch + tritium decay, t1/2 12.3 y) | ~7.4 TW-years of D-D fusion; ~1 kt tritium held for decades | neutron load, tritium inventory and safety, time | needs a large fusion economy; fusion is "difficult engineering" in canon |
| Gas-giant atmosphere extraction (Uranus/Saturn) | not sized | outer-system industry, transport delta-v | not established at Y155 |
| Mixed: lunar base + D-D top-up | | | most robust if any route is accepted |

## Transport and storage

- Transport is small by mass (2 kt) against the Luna Harbor -> Luna Yard chain; throughput numbers are open in canon.
- Storage is the hard part: 2.0 kt as liquid at 3.2 K is ~34,000 m^3, about 8x the whole 4,072 m^3 BODY-C3 study capacity. Even the canon
  1,094 t is ~18,700 m^3 (~4.6x). This is a conflict between S&E owner rows (He-3 inventory vs cryostat volume) to be resolved by the
  owner, not here. He-3 forms no hydrides and does not solidify below ~29 bar; dense storage means liquid at ~3 K with continuous
  refrigeration over a multi-year voyage (latent heat only ~8 kJ/kg).

## Questions for the owner

1. Accept a lunar He-3 programme as the canonical source (with D-D top-up), or keep supply as a later story issue?
2. Route the storage-volume conflict (He-3 inventory vs BODY-C3 capacity) to the S&E owner rows?
