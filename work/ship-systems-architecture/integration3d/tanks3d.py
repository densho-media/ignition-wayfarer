"""3D integration Stage B: propellant volume for the Track F1 reference (WF-F1-P6.0). STUDY, PROTOTYPE, noncanon.

Function: hold the F1 propellant (nominal fill 1.70x the historical farm for every species, Phase VI) inside the Brow's silhouette, behind
the shield, without touching ring B's sweep, the three lanes, the girder panels or the 1.0 m access gap.
Fixed: the 13 vessel azimuths, classes and wall stack (fuel_storage, all at their packing limits), the thrust deck and ring B, densities.
Alternatives (the brief: at least two, do not just add 19 m):
  T-A  STRETCH   every vessel lengthened forward; the Brow, EYE and forward assembly translate forward by the same distance.
  T-B  TANDEM    a second, mission-modular farm segment ahead of the first on its own intermediate deck (same azimuths and classes);
                 fitted only for missions that need it (owner 2026-11-27: provision per mission).
  T-C  DENSIFY   slush hydrogen and deuterium (~50 % solid) plus re-allocation of vessels between species, then the stretch that remains.
  T-X  WIDER / MORE (screened): larger classes or more vessels; the packing is at its limits (screen numbers below).
Writes ../results/i3d_tanks.json. Pure Python (repo modules only).
"""
import copy
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent; W = HERE.parent; ROOT = W.parents[1]; R = W/'results'
sys.path.insert(0, str(ROOT/'src/wayfarer'))
import spec  # noqa: E402
import fuel_storage as fs  # noqa: E402
import mass_model as mm  # noqa: E402

DENS_SLUSH = {'hydrogen': 81.5, 'deuterium': 188.0}     # kg/m3, ~50 % solid slush (H2: NBP 70.8, triple 77.0, solid 86.5; D2 triple 174, solid 200)
DECK_GAP_M = 0.8+1.8+0.3                                 # truss clearance + intermediate deck depth + apex standoff (as the aft deck)


def cap_at(ts, dL, wall, hr, extra=None):
    """Capacity (m3) per vessel after lengthening by dL (barrel only; heads and wall unchanged)."""
    return [fs.vessel_volume(t['a_env'], t['length']+dL, wall, hr) for t in ts]


def area_at(t, dL):
    a = t['a']; return 2*math.pi*a*(t['y_ring'][1]-t['y_ring'][0]+dL)+2*1.38*math.pi*a*a


def need_F1(s):
    P = json.loads((R/'phase6.json').read_text())
    nom = next(r for r in P['tanks']['F1']['rows'] if r['case'] == 'nom'); cap = fs.capacity_m3(s)
    key = {'helium-3': 'helium_3', 'deuterium': 'deuterium', 'hydrogen': 'hydrogen'}
    return {sp: nom['fill'][sp]*cap[key[sp]] for sp in nom['fill']}, P


def solve_dL(caps_fn, need, lo=0.0, hi=80.0):
    for _ in range(60):
        m = (lo+hi)/2
        if all(c >= need[k] for k, c in caps_fn(m).items()): hi = m
        else: lo = m
    return hi


def stretch(s, ts, need, assign=None):
    f = fs.farm_cfg(s); w, hr = f['wall_m'], f['head_ratio']; assign = assign or [t['species'] for t in ts]
    def caps(dL):
        c = {}
        for t, sp, v in zip(ts, assign, cap_at(ts, dL, w, hr)): c[sp] = c.get(sp, 0.0)+v
        return c
    return solve_dL(caps, need), caps


def main():
    s = spec.load()[0]; ts = fs.tanks(s); f = fs.farm_cfg(s); w, hr = f['wall_m'], f['head_ratio']
    need, P = need_F1(s); x0, x1 = fs.span(s); L0 = x1-x0
    A0 = sum(mm.shell_area(t) for t in ts); tank_t = next(c for c in P['mass']['F1']['cases'] if c['case'] == 'nom')['tankage_t']
    prop_t = next(c for c in P['mass']['F1']['cases'] if c['case'] == 'nom')['propellant_t']
    clr = fs.clearances(s)
    out = dict(status='STUDY / PROTOTYPE (Track F1 reference WF-F1-P6.0, nominal case); noncanon; production farm unchanged',
               need_m3=need, historical_capacity_m3={t['species']: 0 for t in ts}, farm=dict(x0=x0, x1=x1, length_m=L0, vessels=len(ts)),
               packing=dict(clearances_m=clr, gap_required_m=f['gap_m'], girder_clearance_m=f['girder']['clearance_m'],
                            brow_shield_radius_m=45.0, farm_reach_m=clr['reach_m']))
    for t in ts: out['historical_capacity_m3'][t['species']] += t['liquid_m3']
    alts = []
    # T-A stretch
    dA, capsA = stretch(s, ts, need)
    areaA = sum(area_at(t, dA) for t in ts)
    alts.append(dict(id='T-A', name='Stretch', vessels=13, decks=1, added_length_m=dA, ship_length_m=289.5+dA, brow_translation_m=dA,
                     vessel_length_m=L0+dA, slenderness_LD={'L': (L0+dA)/(2*6.75), 'M': (L0+dA)/(2*5.75)}, shell_area_m2=areaA,
                     capacity_m3=capsA(dA), prop_centroid_shift_m=dA/2,
                     pros=['one vessel set, same tooling and supports', 'no new deck, outlets or ring mains', 'lowest shell area per m3'],
                     cons=[f'ship +{dA:.1f} m; Brow, EYE, lances and forward assembly move forward (every forward interface re-anchored)',
                           f'vessel L/D {(L0+dA)/13.5:.1f} (L) and {(L0+dA)/11.5:.1f} (M): forward guides and the keel rails grow; barrel buckling under '
                           'lateral loads needs a check', 'propellant centroid moves forward: pitch inertia rises'],
                     modular=False))
    # T-B tandem: forward segment of length Lb behind its own deck; same 13 azimuths
    def capsB(Lb):
        c = {}
        for t in ts: c[t['species']] = c.get(t['species'], 0.0)+t['liquid_m3']
        if Lb > 2*(w+hr*(t['a_env']-w))+0.1:
            for t in ts: c[t['species']] += fs.vessel_volume(t['a_env'], Lb, w, hr)
        return c
    Lb = solve_dL(capsB, need, lo=2*(w+hr*6.45)+0.2, hi=80.0)
    tB = [dict(t, length=Lb, y_ring=(0.0, Lb-2*w-2*hr*t['a'])) for t in ts]
    areaB = A0+sum(mm.shell_area(t) for t in tB)
    alts.append(dict(id='T-B', name='Tandem modular segment', vessels=26, decks=2, added_length_m=DECK_GAP_M+Lb, ship_length_m=289.5+DECK_GAP_M+Lb,
                     brow_translation_m=DECK_GAP_M+Lb, segment_vessel_length_m=Lb, shell_area_m2=areaB, capacity_m3=capsB(Lb),
                     prop_centroid_shift_m=(DECK_GAP_M+Lb)/2*(sum(fs.vessel_volume(t['a_env'], Lb, w, hr) for t in ts)/sum(need.values())),
                     pros=['mission-modular: the forward segment and its deck are fitted only when a mission needs the volume',
                           'short barrels (no slenderness growth); the base farm and its interfaces are unchanged',
                           'a segment is an exchangeable unit (yard-level, not LOG-G1)'],
                     cons=[f'{DECK_GAP_M+Lb:.1f} m added (longer than T-A: a second deck, 13 more heads)',
                           f'shell area +{100*(areaB/areaA-1):.0f} % over T-A: tankage and boil-off surface grow', '13 more outlets, a second ring main per species, '
                           'transfer lines through the base farm'], modular=True))
    # T-C densify + re-allocate
    need_d = {k: v*(70.8/DENS_SLUSH['hydrogen'] if k == 'hydrogen' else 175.2/DENS_SLUSH['deuterium'] if k == 'deuterium' else 1.0) for k, v in need.items()}
    dC0, _ = stretch(s, ts, need_d)
    best = None; Ls = [t for t in ts if t['tank_class'] == 'L']; Ms = [t for t in ts if t['tank_class'] == 'M']
    for he_L in range(10):
        for h_L in range(10-he_L):
            d_L = 9-he_L-h_L
            for he_M in range(5):
                for h_M in range(5-he_M):
                    d_M = 4-he_M-h_M
                    assign = {}
                    for grp, counts in ((Ls, (he_L, h_L, d_L)), (Ms, (he_M, h_M, d_M))):
                        seq = ['helium-3']*counts[0]+['hydrogen']*counts[1]+['deuterium']*counts[2]
                        for tt, sp in zip(grp, seq): assign[tt['id']] = sp
                    combo = [assign[tt['id']] for tt in ts]
                    if not all(combo.count(k) for k in need_d): continue
                    d, c = stretch(s, ts, need_d, combo)
                    if best is None or d < best[0]-1e-6: best = (d, combo, c)
    dC, assignC, capsC = best
    cnt = lambda asg: {sp: {c: sum(1 for tt, x in zip(ts, asg) if x == sp and tt['tank_class'] == c) for c in ('L', 'M')} for sp in need}
    moved = dict(before=cnt([tt['species'] for tt in ts]), after=cnt(assignC))
    alts.append(dict(id='T-C', name='Densify and re-allocate', vessels=13, decks=1, added_length_m=dC, ship_length_m=289.5+dC, brow_translation_m=dC,
                     added_length_without_reallocation_m=dC0, reallocated=moved, slush_density_kg_m3=DENS_SLUSH, need_m3=need_d,
                     capacity_m3=capsC(dC), shell_area_m2=sum(area_at(t, dC) for t in ts), prop_centroid_shift_m=dC/2,
                     pros=[f'saves {dA-dC:.1f} m against T-A', 'same vessel set'],
                     cons=['slush production, transfer and ageing (solid fraction falls with boil-off) need a register entry (FT-09 proposed)',
                           're-allocation breaks the per-species zero-moment placement: rerun the balance search (mass_model.balance)',
                           'helium-3 cannot be densified (no solid at tank pressure): it still sets most of the stretch'], modular=False,
                     register='FT-09 PROPOSED (densified hydrogen isotopes)'))
    # T-X screen
    alts.append(dict(id='T-X', name='Wider or more vessels (screened)', feasible=False,
                     reason=(f'vessel-to-vessel gap {clr["vessel_to_vessel"]:.2f} m (rule {f["gap_m"]}), lanes {min(v for k, v in clr.items() if k.startswith("lane_")):.3f} m, '
                             f'girder panels {clr["girder_panels"]:.2f} m (rule {f["girder"]["clearance_m"]}): every class is at its limit; the Brow silhouette (r 45 m) '
                             f'is not the limit (farm reach {clr["reach_m"]:.1f} m). Growth needs a new azimuth search with fewer, larger vessels; a +0.5 m envelope '
                             f'on the outer ring alone would close the gap to 0'),
                     capacity_gain_per_05m_outer=(((6.75+0.5)-w)**2/((6.75-w)**2)-1)))
    for a in alts:
        if a.get('shell_area_m2'):
            a['tankage_t'] = tank_t*a['shell_area_m2']/areaA            # surface-driven scaling, T-A = the Phase VI tankage
            a['tankage_delta_vs_A_t'] = a['tankage_t']-tank_t
    out['alternatives'] = alts
    out['recommendation'] = dict(pick='T-A (stretch) as the F1 3D reference; T-B kept as the mission-modular variant',
                                 why=(f'T-A adds {dA:.1f} m with the least shell and no new interfaces; T-B costs {alts[1]["added_length_m"]-dA:.1f} m and '
                                      f'+{alts[1]["tankage_delta_vs_A_t"]:.0f} t more but lets the farm follow the mission; T-C saves {dA-dC:.1f} m only with a new '
                                      'technology entry and a new balance search, so it stays an option'),
                                 owner_question='DR-3D-01: confirm T-A as the 3D reference, or ask for T-B (modular) or T-C (densified)')
    out['propellant_t'] = prop_t
    (R/'i3d_tanks.json').write_text(json.dumps(out, indent=1, default=float))
    for a in alts:
        print(a['id'], a['name'], {k: (round(v, 2) if isinstance(v, float) else v) for k, v in a.items() if k in ('added_length_m', 'ship_length_m', 'tankage_t', 'added_length_without_reallocation_m', 'reallocated', 'feasible')})


if __name__ == '__main__':
    main()
