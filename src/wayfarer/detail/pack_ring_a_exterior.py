"""Detail pack ring_a_exterior (docs/MODULES.md): ring A's exterior in the selected Phase 4 grammar (slice S4), assemblies RA.EXT.FWD and
RA.EXT.AFT (the +u and -u flanks) and RA.EXT.TRAYddd.IN/OUT (spoke service trays, hub and rim halves), RA.EXT.BLANKET.FWD/AFT (inner-face blankets) on the anchor WF-RING-A.ROTOR.1 (Rotor_1, rotor frame). The segment module is the shared
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


def _tray(deg, part):
    a = 'RA.EXT.TRAY%03d.%s' % (deg, part)
    pd.builder(a)(lambda s: ring_exterior.spoke_trays(s, pd.params(s, PACK), 1, a, deg, part))
    pd.CHECKS[a] = lambda s, els: ring_exterior.check_hub(s, els, 1)


def _blanket(side, sgn):
    a = 'RA.EXT.BLANKET.'+side
    pd.builder(a)(lambda s: ring_exterior.blankets(s, pd.params(s, PACK), 1, a, sgn))
    pd.CHECKS[a] = lambda s, els: ring_exterior.check_hub(s, els, 1)


for _deg in (60, 180, 300):
    for _part in ('IN', 'OUT'):
        _tray(_deg, _part)
_blanket('FWD', 1)
_blanket('AFT', -1)
pd.CHECKS['RA.EXT.FWD'] = ring_check
pd.CHECKS['RA.EXT.AFT'] = ring_check
