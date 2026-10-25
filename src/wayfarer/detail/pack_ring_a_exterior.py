"""Detail pack ring_a_exterior (docs/MODULES.md): ring A's exterior in the selected Phase 4 grammar (slice S4), assemblies RA.EXT.FWD and
RA.EXT.AFT (the +u and -u flanks) on the anchor WF-RING-A.ROTOR.1 (Rotor_1, rotor frame). The segment module is the shared
ring_exterior.elements (WF-HABITAT); this file only binds it to ring 1 with this pack's parameters. Owned with
data/detail/ring_a_exterior.toml.
"""
import production_detail as pd
import ring_exterior

PACK = 'ring_a_exterior'


@pd.builder('RA.EXT.FWD')
def forward_flank(s):
    return ring_exterior.elements(s, pd.params(s, PACK), 1, 'RA.EXT.FWD', 1)


@pd.builder('RA.EXT.AFT')
def aft_flank(s):
    return ring_exterior.elements(s, pd.params(s, PACK), 1, 'RA.EXT.AFT', -1)


def ring_check(s, els):
    return ring_exterior.check(s, els, 1)


pd.CHECKS['RA.EXT.FWD'] = ring_check
pd.CHECKS['RA.EXT.AFT'] = ring_check
