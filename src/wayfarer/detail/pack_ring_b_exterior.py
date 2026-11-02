"""Detail pack ring_b_exterior (docs/MODULES.md): ring B's exterior in the selected Phase 4 grammar (slice S4), assemblies RB.EXT.FWD and
RB.EXT.AFT (the +u and -u flanks) on the anchor WF-RING-B.ROTOR.2 (Rotor_2, rotor frame). The segment module is the shared
ring_exterior.elements (WF-HABITAT); this file only binds it to ring 2 with this pack's parameters. Owned with
data/detail/ring_b_exterior.toml.
"""
import production_detail as pd
import ring_exterior

PACK = 'ring_b_exterior'


@pd.builder('RB.EXT.FWD')
def forward_flank(s):
    return ring_exterior.elements(s, pd.params(s, PACK), 2, 'RB.EXT.FWD', 1)


@pd.builder('RB.EXT.AFT')
def aft_flank(s):
    return ring_exterior.elements(s, pd.params(s, PACK), 2, 'RB.EXT.AFT', -1)


def ring_check(s, els):
    return ring_exterior.check(s, els, 2)


def _tray(deg, part):
    a = 'RB.EXT.TRAY%03d.%s' % (deg, part)
    pd.builder(a)(lambda s: ring_exterior.spoke_trays(s, pd.params(s, PACK), 2, a, deg, part))
    pd.CHECKS[a] = lambda s, els: ring_exterior.check_hub(s, els, 2)


def _blanket(side, sgn):
    a = 'RB.EXT.BLANKET.'+side
    pd.builder(a)(lambda s: ring_exterior.blankets(s, pd.params(s, PACK), 2, a, sgn))
    pd.CHECKS[a] = lambda s, els: ring_exterior.check_hub(s, els, 2)


for _deg in (60, 180, 300):
    for _part in ('IN', 'OUT'):
        _tray(_deg, _part)
_blanket('FWD', 1)
_blanket('AFT', -1)
pd.CHECKS['RB.EXT.FWD'] = ring_check
pd.CHECKS['RB.EXT.AFT'] = ring_check
