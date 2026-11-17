"""Vertex 2.7 corrected-path shim (research, not canon).

Until 2026-11-17 (2.7 commit 5e1f559) this module replaced protect.mission at run time with the corrected braking path. Vertex 2.8
folded that correction into work/vertex-2-6/protect.py itself (mission() is now the corrected path, the old one is kept as
mission_superseded_874dca7()), so this shim no longer patches anything: it only checks that the shared model is the corrected one, so
the 2.7 scripts keep their import and fail loudly if they ever meet the superseded path again.
"""
import protect as P

ORIGINAL = getattr(P, 'mission_superseded_874dca7')
_segs, _meta = P.mission(466.85*P.DAY, 0.072*P.C, None)
assert _meta['min_r_AU'] >= 1.0 and abs(_meta['destination_AU']-324.33) < 0.05, 'protect.mission is not the corrected braking path'
mission = P.mission
