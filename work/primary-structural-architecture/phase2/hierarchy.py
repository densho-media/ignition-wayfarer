"""Sections 4 and 9: vertebral hierarchy (L1 components, L2 bays, L3 manufacturing modules, L4 districts) and a standardised
cassette family with a common connection interface; reports the standardisation mass penalty per variant.

Writes results/p2_hierarchy.json.
"""
import json
import math
import sys
from pathlib import Path

H = Path(__file__).resolve().parent
sys.path.insert(0, str(H))
import model as mdl  # noqa: E402

OUT = H.parent / 'results'
R_CAT = [0.06, 0.075, 0.09, 0.11, 0.14, 0.18, 0.22, 0.28, 0.35, 0.45, 0.55, 0.70, 0.85, 0.95, 1.00, 1.20]   # ~1.25 ratio steps
T_CAT = [0.002, 0.0025, 0.003, 0.004, 0.005, 0.006, 0.008, 0.010, 0.012, 0.016, 0.020, 0.025, 0.032, 0.040, 0.050, 0.060, 0.080, 0.100]
END_CLASS = [('C1', 1.0), ('C2', 4.0), ('C3', 12.0), ('C4', 40.0)]   # ultimate axial capacity of the end fitting (MN)

L2_BAY = dict(length_m=4.0, alternatives=[
    dict(name='Warren bay (production)', diagonals_per_face=1, note='one diagonal per face, alternating; lightest, single shear path'),
    dict(name='X-braced bay', diagonals_per_face=2, note='two crossing tension diagonals; fail-safe in shear, +diag mass'),
    dict(name='Portal bay (open)', diagonals_per_face=0, note='rigid frames, no diagonals; open for equipment removal, frame bending governs'),
])
L3 = dict(length_m=(8.0, 12.0), joint='module frame (deep, Ti nodes), 15 (6 rails) or 12 (3 rails) splice points',
          alignment='three kinematic cones per module frame (one per sector) set the datum; splice plates take the rails; laser tracker + FBG',
          transport='8 m module: 10-12 m diameter, 15-35 t; launch from the lunar yard by mass driver or tug as one piece',
          orbital_joining='friction-stir or bolted splice per rail (6 or 3), frames bolted; 1 splice pair per rail per 8 m')
DISTRICTS = [
    ('propulsion', -145.0, -113.0, 'thrust ring, pickups, transition; Ti nodes; magnetic exclusion (no ferritic steel)'),
    ('power', -113.0, -80.0, 'L1/L2 units 3 x 96.9 t on module frames; stiffness and spectra OPEN'),
    ('hot loop', -111.6, 41.0, 'H6a trunks on 6.4 m saddles; anchor per 25.4 m; bulkhead at X ~40.8'),
    ('equipment', -80.0, 22.0, 'racks and ORUs on rail hard-points; MRU lane az 270'),
    ('workshop', 22.0, 50.0, 'module 10 dry store, workshop; portal bays for removal'),
    ('radiator', -133.0, 93.6, 'blade roots at az 90/210/330 frame lugs (backbone trade 3.6)'),
    ('rotating habitat', 93.6, 106.0, 'rotor bay: collar (bypass) or hub path; ring keep-out r 31.5 m'),
    ('cryo', 106.0, 160.0, 'tank farm on the common thrust deck; cryocoolers forward'),
    ('forward shielding', 160.0, 166.0, 'Brow interface ring; forward defense owns the Brow truss'),
]


def tube(r, t):
    ri = r-t; return math.pi*(r*r-ri*ri), math.pi/4*(r**4-ri**4)


def standardise(sizing):
    pen = 0.0; base = 0.0; used = set(); fits = {}
    for g, s in sizing.items():
        A, I = tube(s['r'], s['t']); rho = mdl.MATS[s['mat']]['rho']; L = s['L_m']
        best = None
        for r in R_CAT:
            if g.startswith(('spine', 'hub')) and abs(r-0.95) > 1e-6:
                continue                                     # the spine keeps its 1.9 m bore
            for t in T_CAT:
                if t > r/4:
                    continue
                a, i = tube(r, t)
                if a >= A*0.999 and i >= I*0.999 and r/t <= s['r']/s['t']*1.0001:
                    if best is None or a < best[0]:
                        best = (a, r, t)
        if best is None:
            best = (A, s['r'], s['t'])
        base += rho*A*L/1e3; pen += rho*(best[0]-A)*L/1e3; used.add((best[1], best[2], s['mat']))
        F = max(s['Nc_MN'], s['Nt_MN'])*1.4
        fits[g] = dict(cassette=f"{s['mat']}-R{int(best[1]*1000)}-T{best[2]*1000:g}", end_class=next(c for c, cap in END_CLASS if F <= cap or c == 'C4'))
    return dict(members_t=base, penalty_t=pen, penalty_pct=100*pen/max(base, 1e-9), distinct_cassettes=len(used), groups=fits)


def main():
    V = json.loads((OUT / 'p2_variants.json').read_text())
    res = dict(L2=L2_BAY, L3=L3, L4=[dict(name=n, x=(a, b), note=t) for n, a, b, t in DISTRICTS], end_classes=END_CLASS,
               interface='common end fitting: Ti-6Al-4V spigot with two-flange bolt circle per class, FBG fibre pass-through and an alignment key; any cassette of a class fits any node socket of that class', variants={})
    for k, v in V.items():
        res['variants'][k] = standardise(v['sizing'])
        s = res['variants'][k]; print(f"{k:<16} distinct cassettes {s['distinct_cassettes']:3d}  standardisation penalty {s['penalty_t']:6.1f} t ({s['penalty_pct']:.1f} %)")
    (OUT / 'p2_hierarchy.json').write_text(json.dumps(res, indent=1, default=float))


if __name__ == '__main__':
    main()
