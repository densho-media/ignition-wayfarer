"""Detail pack m7_ra1 (docs/MODULES.md): the M7.RA1 production layer of ring A sector 1 (HABITATION), module WF-RING-A.

Owned with data/detail/m7_ra1.toml (manifest and [params]) and the generated asset assets/wayfarer/detail/WF_DETAIL_M7_RA1.blend, which
WF_HABITAT links at the anchor WF-RING-A.SECTOR.1.1 (the sector instance). Accepted by the owner on 2026-10-20 with the M7 section
(L4_VISUAL_ACCEPTED, scope M7); migrated unchanged from production_detail.py. Since Phase 4 S8a the definition is the shared m7_route module
(WF-HABITAT), which ring B's pack also uses; the output is unchanged (geometry fingerprint).
"""
import m7_route as mr
import production_detail as pd

PACK = 'm7_ra1'


@pd.builder('M7.RA1')
def sector_elements(s):
    return mr.sector_elements(s, 'HABITATION', 'M7.RA1', pd.params(s, PACK), 'RA1')


pd.CHECKS['M7.RA1'] = lambda s, els: mr.sector_check(s, els, pd.params(s, PACK))
