"""Detail pack ring_b_transfer (docs/MODULES.md): ring B's M7-equivalent route (Phase 4 S8a), module WF-RING-B. RB.XFR, the despun drum's
lining (anchor WF-RING-B.DRUM.2), RB.SPK, the sector-2 crew tube's radial run (WF-RING-B.ROTOR.2), and RB.SEC, sector 2's overhead layer
(WF-RING-B.SECTOR.2.2), built by the shared m7_route definitions ring A's accepted packs use. Owned with data/detail/ring_b_transfer.toml.
"""
import m7_route as mr
import production_detail as pd

PACK = 'ring_b_transfer'


@pd.builder('RB.XFR')
def drum(s):
    q = pd.params(s, PACK); return mr.drum_elements(s, q['ring'], 'RB.XFR', q['drum'], 'RBX')


@pd.builder('RB.SPK')
def tube(s):
    q = pd.params(s, PACK); return mr.tube_elements(s, q['ring'], q['route_sector'], 'RB.SPK', q['tube'], 'RBS')


@pd.builder('RB.SEC')
def overhead(s):
    q = pd.params(s, PACK); return mr.sector_elements(s, q['function'], 'RB.SEC', q['overhead'], 'RB2')


pd.CHECKS['RB.XFR'] = lambda s, els: mr.drum_check(s, pd.params(s, PACK)['ring'], els, pd.params(s, PACK)['drum'])
pd.CHECKS['RB.SPK'] = lambda s, els: mr.tube_check(s, pd.params(s, PACK)['ring'], pd.params(s, PACK)['route_sector'], els, pd.params(s, PACK)['tube'])
pd.CHECKS['RB.SEC'] = lambda s, els: mr.sector_check(s, els, pd.params(s, PACK)['overhead'])
