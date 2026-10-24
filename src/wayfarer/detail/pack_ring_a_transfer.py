"""Detail pack ring_a_transfer (docs/MODULES.md): ring A's spin transfer, module WF-RING-A. M7.XFR, the lining of the despun transfer drum,
on the anchor WF-RING-A.DRUM.1 (Drum_1: despun at the index angle, turning with the ring only while drum_sync is 1), and M7.SPK, the
sector-1 crew tube's radial run, on WF-RING-A.ROTOR.1 (Rotor_1: turns with the ring). Each detail asset is built in its anchor object's local
frame and its instance inherits that motion, so the drum lining stays despun and the tube cladding spins.

Owned with data/detail/ring_a_transfer.toml (manifest, [params.drum] and [params.tube]) and the generated assets
assets/wayfarer/detail/WF_DETAIL_M7_XFR.blend and WF_DETAIL_M7_SPK.blend, which WF_HABITAT links. Accepted by the owner on 2026-10-20 with
the M7 section (L4_VISUAL_ACCEPTED, scope M7); migrated unchanged from production_detail.py (MOD phase 2). Since Phase 4 S8a the
definitions are the shared m7_route module (WF-HABITAT), which ring B's pack also uses; the output is unchanged (geometry fingerprint).
Closures, seals, bearings and interfaces stay physics-locked proxies.
"""
import m7_route as mr
import production_detail as pd

PACK = 'ring_a_transfer'


@pd.builder('M7.XFR')
def drum_elements(s):
    return mr.drum_elements(s, s['induction']['ring'], 'M7.XFR', pd.params(s, PACK)['drum'], 'XFR')


@pd.builder('M7.SPK')
def tube_elements(s):
    return mr.tube_elements(s, s['induction']['ring'], 1, 'M7.SPK', pd.params(s, PACK)['tube'], 'SPK')


pd.CHECKS['M7.XFR'] = lambda s, els: mr.drum_check(s, s['induction']['ring'], els, pd.params(s, PACK)['drum'])
pd.CHECKS['M7.SPK'] = lambda s, els: mr.tube_check(s, s['induction']['ring'], 1, els, pd.params(s, PACK)['tube'])
