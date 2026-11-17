"""Dust impacts at speed: the model behind the website's dust page (engineering/dust/). Standard library only. Research, not canon.

    python3 lab/studies/dust-impacts/model.py        writes results/dust.json and prints the headline numbers (about 30 s)

Two parts.

1. One grain (`impact`). What a single dust grain does to the Brow stack (sacrificial disruptor layer, stand-off, shield skin) at any speed
   from a satellite-debris strike to cruise. Energy, size, energy per atom, the physical regime and the outcome come from the Vertex
   T02 / 2.6 order-of-magnitude impact rules (crater volume proportional to energy, a bumper that turns the grain into a cloud which
   spreads over the stand-off). The page script mirrors this function; the site check compares the two at the check points.
2. The trip (`trip`) and the levers (`levers`). The Vertex 2.6 dust environment and exposure model (imports/vertex_2_6_874dca7, copied
   unchanged from claude/project-thread-6qwiwi) along the Vertex research mission: four 117-day burns at 0.072 c exhaust speed to the
   312 AU turn-around and home, flying bow first while accelerating and engine first while braking. Expected numbers of grains per
   phase and per component, in the LOW / NOMINAL / HIGH cases (literature envelopes, not probabilities), and the same numbers over a
   grid of the visitor's levers (Brow stand-off, an engine-front bumper, attitude accuracy).

Nothing here is validated at 4,797 km/s: light-gas guns reach about 10 km/s, dust accelerators about 100 km/s for sub-micron grains.
"""
import hashlib
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
IMP = HERE / 'imports' / 'vertex_2_6_874dca7'
sys.path.insert(0, str(IMP))
import protect as P  # noqa: E402  (imports t02_environment beside it)

C = 299792458.0
AMU = 1.66053907e-27
EV = 1.602176634e-19
TNT = 4.184e6                       # J/kg
V_CRUISE = 0.016 * C                # CANON mission.target_speed (LOCKED)
RHO_GRAIN = P.RHO_GRAIN             # 2,500 kg/m3 (T02)
RHO_BUMPER = P.RHO_BUMPER           # 1,800 kg/m3 C/C class (T02)

# The Brow stack as the page draws it. The 2.0 m stand-off is canon WORKING (MODEL.md Forward defense: one full-diameter sacrificial
# disruptor layer 2.0 m ahead of the shield); layer and skin thicknesses are OPEN in canon and PROTOTYPE here.
STACK = {'bumper_m': 0.005, 'standoff_m': 2.0, 'wall_m': 0.005,
         'labels': {'standoff_m': 'CANON WORKING (forward defense, disruptor layer 2.0 m ahead)', 'bumper_m': 'PROTOTYPE (layer thickness OPEN)',
                    'wall_m': 'PROTOTYPE (the 5 mm skin of Vertex 2.6, class "bare")'}}

# Physical regimes of a grain hitting a solid by impact speed (km/s). Order-of-magnitude transitions for silicate or metal grains on
# metal; sources in `REGIME_SOURCES`.
REGIMES = [
    (0.0, 'bounces and dents', 'Below about 3 km/s the grain stays mostly whole and digs a crater.'),
    (3.0, 'shatters', 'From about 3 km/s the shock breaks the grain into fragments: the speed range Whipple shields are built for.'),
    (7.0, 'melts', 'From about 7 km/s grain and bumper melt where they meet.'),
    (20.0, 'vaporises', 'From about 20 km/s they turn to vapour.'),
    (100.0, 'turns to plasma', 'From about 100 km/s the impact makes a plasma: dust detectors on spacecraft count grains by that charge.'),
    (1000.0, 'beyond any test', 'Above about 1,000 km/s each atom arrives with tens of keV: more like a burst of ion beam than a collision. '
                                'No laboratory has made such an impact with a grain.'),
]
REGIME_SOURCES = ('Whipple-shield fragmentation, melt and vapour onset near 3, 7 and 20 km/s (hypervelocity-impact literature, e.g. '
                  'Piekutowski; NASA HVIT); impact-plasma dust detectors (Galileo, Ulysses, Cassini CDA); electrostatic dust accelerators '
                  'reach about 100 km/s for sub-micron grains; the regime above 1,000 km/s is an EXTRAPOLATION')

SPEEDS = [  # (label, m/s, note)
    ('Space-station debris', 7.0e3, 'typical orbital-debris strike; Whipple shields are tested here'),
    ('Fast meteor at Earth', 72.0e3, 'the fastest a meteor from the solar system can reach Earth'),
    ('Giotto at Halley', 68.4e3, 'Giotto flew through Halley\'s dust in 1986 behind a 1 mm bumper'),
    ('Fastest lab dust', 100e3, 'electrostatic dust accelerators, sub-micron grains only'),
    ('Wayfarer, 1 % of cruise', 0.01 * V_CRUISE, 'early in a burn'),
    ('Wayfarer cruise, 0.016 c', V_CRUISE, 'canon cruise speed (LOCKED)'),
]
MASSES = [  # (label, kg)
    ('Interstellar smoke grain', 3e-16),
    ('10 µm zodiacal grain', RHO_GRAIN * math.pi / 6 * (10e-6) ** 3),
    ('Fine sand grain (1 µg)', 1e-9),
    ('Grain of salt (60 µg)', 6e-8),
    ('Coarse sand grain (1 mg)', 1e-6),
]


def regime(v):
    kms = v / 1e3
    out = REGIMES[0]
    for row in REGIMES:
        if kms >= row[0]:
            out = row
    return out


def impact(m, v, case='NOMINAL', bumper_m=STACK['bumper_m'], standoff_m=STACK['standoff_m'], wall_m=STACK['wall_m']):
    """One grain of mass m (kg) at speed v (m/s) on the Brow stack. Mirrored in web/engineering/dust.js (impact())."""
    k = P.K_CRATER[case]
    b = P.BUMPER[case]
    E = 0.5 * m * v * v
    d = (6 * m / (math.pi * RHO_GRAIN)) ** (1 / 3)
    crater_bare = (3 * k * E / (2 * math.pi)) ** (1 / 3)                 # hemispherical crater depth in a thick plate
    kms = v / 1e3
    disrupt = bumper_m > 0 and kms >= 3.0 and bumper_m >= P.T_OVER_D[case] * d
    R = standoff_m * math.tan(math.radians(b['alpha_deg']))                # cloud radius on the wall
    if disrupt:
        F = b['g'] * E / (math.pi * R * R) if R > 0 else float('inf')      # J/m2 the cloud lays on the wall
        breach = F > b['F_allow']
        outcome = 'breach' if breach else ('scorched' if F > 0.1 * b['F_allow'] else 'stopped')
        hole_bumper = min(2 * max(d, crater_bare), 2 * bumper_m + d) if bumper_m else 0.0
        wall_crater = None
    else:
        F = None
        through_bumper = bumper_m == 0 or E > P.perforation_energy(bumper_m, k)
        if not through_bumper:
            outcome, breach, hole_bumper = 'stopped', False, 0.0
            wall_crater = 0.0
        else:
            hole_bumper = 2 * max(d, crater_bare) if bumper_m else 0.0
            breach = E > P.perforation_energy(wall_m, k)
            wall_crater = crater_bare
            outcome = 'breach' if breach else 'cratered'
    return {'E_J': E, 'tnt_kg': E / TNT, 'd_m': d, 'keV_per_u': 0.5 * AMU * v * v / EV / 1e3, 'regime': regime(v)[1],
            'disrupted': disrupt, 'cloud_r_m': R if disrupt else None, 'cloud_J_m2': F, 'allow_J_m2': b['F_allow'],
            'crater_m': crater_bare, 'wall_crater_m': wall_crater, 'bumper_hole_m': hole_bumper, 'outcome': outcome, 'breach': breach,
            'defeat_E_J': P.bumper_defeat_energy(standoff_m, case) if standoff_m > 0 else 0.0}


def largest_stopped(v, case='NOMINAL', **kw):
    """Largest grain mass the stack stops at speed v (bisection on the outcome)."""
    lo, hi = 1e-21, 10.0
    if impact(lo, v, case, **kw)['breach']:
        return 0.0
    for _ in range(200):
        mid = math.sqrt(lo * hi)
        lo, hi = (lo, mid) if impact(mid, v, case, **kw)['breach'] else (mid, hi)
    return lo


# ---------- the Vertex 2.7 justified envelope ------------------------------------------------------------------------------------------------
# Vertex 2.7 (claude/project-thread-6qwiwi f9c3cc3, work/vertex-2-7/dust.py run()): every environment input at the upper end of what a
# measurement supports, with every damage input at its conservative HIGH value because no impact data exist above ~100 km/s. Registered
# here at run time exactly as dust.py add_case() does. T02 HIGH stays as the stress test: it adds the unmeasured inputs (Kuiper-belt grains
# to 1 g on a flat 0.70 index, the disputed AMOR radar flux of large interstellar grains).
JUSTIFIED_ENV = dict(ipd_scale=2.0, kb_scale=3.0, kb_alpha=0.83, kb_mmax=1e-6, isd_rho=6.2e-24, isd_tail='EXTRAPOLATED')
P.E.CASE['JUSTIFIED'] = dict(P.E.CASE['NOMINAL'], **JUSTIFIED_ENV)
for _d in ('K_CRATER', 'BUMPER', 'T_OVER_D', 'WALL_KG_M2'):
    getattr(P, _d)['JUSTIFIED'] = getattr(P, _d)['HIGH']
CASES = ('LOW', 'NOMINAL', 'JUSTIFIED', 'HIGH')
CASE_LABELS = {
    'LOW': ['Low', 'the low end of the published measurements'],
    'NOMINAL': ['Nominal', 'the published measurements at their central values'],
    'JUSTIFIED': ['Justified envelope', 'every measured input at its upper bound and every untested damage rule at its worst (Vertex 2.7; '
                  'proposed design envelope, owner decision open)'],
    'HIGH': ['Stress test', 'adds what nobody has measured: Kuiper-belt grains up to 1 g and the disputed radar flux of large interstellar '
             'grains. A conditional safety gate, not a design case'],
}


# ---------- the trip ------------------------------------------------------------------------------------------------------------------------
TB_TOTAL = 466.85 * P.DAY            # Vertex research operating point (Halo 2.5 all-lever ledger, as Vertex 2.6)
VE = 0.072 * C
PHASE_TEXT = {
    'accelerate out': 'Bow first, faster every day: out of the inner solar system and through the Kuiper belt\'s dust, where most grains get through the Brow\'s layer.',
    'flip before braking (destination)': 'A 300 s turn at full speed: for a moment the whole side of the ship faces the dust.',
    'brake at destination': 'Engines first: the four engine fronts now lead into the dust.',
    'accelerate home': 'Bow first again, in thin outer dust.',
    'flip before braking (home)': 'The second turn at full speed.',
    'brake at home': 'Engines first, braking back through the Kuiper belt into the inner solar system: the engine fronts\' worst stretch.',
}


def mission(Tb_total=None, ve=None, dest_au=None, t_flip=300.0, n=240):
    """Vertex 2.6 protect.mission() with one correction (MODEL fix, 2026-11-17): a braking burn is longer than the accelerating burn of
    the same duration (thrust is constant and the ship is heaviest at its start, so it spends more of the burn fast). protect.mission()
    places both braking burns one accelerating-burn length (155.7 AU) before their end point, so the home braking burn runs 167.6 AU
    from 156 AU to -11 AU, through the Sun, where the dust density is held at its 0.3 AU value. Here each braking burn ends where it
    should (the turn-around and 1 AU) and the turn-around moves out to 1 + accelerate + brake distance. Everything else is unchanged."""
    Tb_total = TB_TOTAL if Tb_total is None else Tb_total
    ve = VE if ve is None else ve
    tb = Tb_total / 4
    ratio = math.exp(P.DV / ve)
    prof = P.burn_profile(ratio, n)
    sa = sum(dt * f for dt, f in prof) * P.VC * tb
    sd = sum(dt * (1 - f) for dt, f in prof) * P.VC * tb
    D = max(dest_au or 0.0, 1.0 + (sa + sd) / P.AU)
    segs = []

    def burn(phase, orient, r0, sign, decel):
        x = 0.0
        for dt, f in prof:
            v = P.VC * (1 - f) if decel else P.VC * f
            ds = v * dt * tb
            segs.append(dict(phase=phase, orient=orient, r=r0 + sign * (x + ds / 2) / P.AU, v=max(v, 1.0), ds=ds, dt=dt * tb))
            x += ds

    def coast(phase, r0, r1, k=60):
        L = abs(r1 - r0) * P.AU
        for i in range(k if L > 1 else 0):
            segs.append(dict(phase=phase, orient='BOW_FIRST', r=r0 + (r1 - r0) * (i + 0.5) / k, v=P.VC, ds=L / k, dt=L / k / P.VC))

    def flip(phase, r):
        segs.append(dict(phase=phase, orient='BROADSIDE', r=r, v=P.VC, ds=P.VC * t_flip, dt=t_flip))

    burn('accelerate out', 'BOW_FIRST', 1.0, +1, False)
    coast('coast out', 1.0 + sa / P.AU, D - sd / P.AU)
    flip('flip before braking (destination)', D - sd / P.AU)
    burn('brake at destination', 'ENGINE_FIRST', D - sd / P.AU, +1, True)
    burn('accelerate home', 'BOW_FIRST', D, -1, False)
    coast('coast home', D - sa / P.AU, 1.0 + sd / P.AU)
    flip('flip before braking (home)', 1.0 + sd / P.AU)
    burn('brake at home', 'ENGINE_FIRST', 1.0 + sd / P.AU, -1, True)
    meta = dict(Tb_total_d=Tb_total / P.DAY, burn_d=tb / P.DAY, ve_c=ve / C, mass_ratio_per_burn=ratio, burn_AU=sa / P.AU, brake_AU=sd / P.AU,
                destination_AU=D, t_flip_s=t_flip, path_AU=sum(x['ds'] for x in segs) / P.AU,
                min_r_AU=min(x['r'] for x in segs))
    return segs, meta


def _components(case, attitude):
    rows = []
    for c in P.components('APLUS'):
        c = dict(c, attitude_deg=attitude)
        E_f = P.FAIL[c['fail']](P.K_CRATER[case]) if c['fail'] != 'bumper' else P.perforation_energy(0.005, P.K_CRATER[case])
        rows.append((c, E_f))
    return rows


TRIP_ITEMS = {  # page key: (component name prefix, page label)
    'blades': ('thermal blades', 'Radiator blade punctures'),
    'rings': ('habitat rings', 'Habitat ring breaches'),
    'body': ('body and tank farm', 'Body and tank breaches'),
    'engines': ('engine fronts', 'Engine-front breaches (bare 5 mm face)'),
    'optics': ('final optics', 'Driver optics hit (replaced in service)'),
}


def trip(case, n=60, attitude=0.2):
    segs, meta = mission(n=n)
    brow_item = dict(P.lead_item('Brow', math.pi * 45.0 ** 2), leads='BOW_FIRST')
    lead_eng = dict(P.lead_item('engine fronts', 4 * math.pi * 11.4358 ** 2), leads='ENGINE_FIRST')
    E_brow = P.bumper_defeat_energy(STACK['standoff_m'], case)
    comps = _components(case, attitude)
    cs = P.E.CASE[case]
    t = 0.0
    rows = []
    cum = {k: 0.0 for k in ['brow', *TRIP_ITEMS]}
    for s in segs:
        lead = 'brow' if s['orient'] == 'BOW_FIRST' else ('engines' if s['orient'] == 'ENGINE_FIRST' else 'side')
        # grains per second on the leading face, all grains above 1e-15 kg (what the face meets) and above 1 J
        area = math.pi * 45.0 ** 2 if lead == 'brow' else (lead_eng['area_m2'] if lead == 'engines' else 0.0)
        n_all = area * s['v'] * sum(P.N_pop(1e-15, s['r'], cs)[p] for p in P.POPS)
        n_1J = area * s['v'] * sum(P.N_pop(2.0 / (s['v'] ** 2 + P.VG[p] ** 2), s['r'], cs)[p] for p in P.POPS)
        flux_W = area * sum(0.5 * P._rho(p, round(s['r'], 1), case) * (s['v'] ** 2 + P.VG[p] ** 2) * s['v'] for p in P.POPS)
        cum['brow'] += P.events(brow_item, [s], E_brow, case)
        for key, (prefix, _) in TRIP_ITEMS.items():
            c, E_f = next((c, e) for c, e in comps if c['name'].startswith(prefix))
            cum[key] += P.events(c, [s], E_f, case)
        t += s['dt']
        rows.append({'phase': s['phase'], 'orient': s['orient'], 't_d': t / P.DAY, 'v': s['v'], 'r': s['r'],
                     'lead_per_s': n_all, 'lead_1J_per_s': n_1J, 'lead_W': flux_W, **{f'cum_{k}': v for k, v in cum.items()}})
    phases = []
    for r in rows:
        if not phases or phases[-1]['name'] != r['phase']:
            phases.append({'name': r['phase'], 'orient': r['orient'], 'i0': rows.index(r), 'text': PHASE_TEXT[r['phase']]})
        phases[-1]['i1'] = rows.index(r)
    return {'meta': meta, 'rows': rows, 'phases': phases, 'brow_defeat_E_J': E_brow}


# ---------- the levers -----------------------------------------------------------------------------------------------------------------------
S_GRID = [0.0, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0, 20.0, 30.0, 50.0, 75.0, 100.0, 133.0, 150.0, 200.0, 300.0]
ATT_GRID = [0.05, 0.1, 0.2, 0.5, 1.0, 1.5, 2.0, 3.0]
BROW_AREA = math.pi * 45.0 ** 2
ENG_AREA = 4 * math.pi * 11.4358 ** 2


def levers(case):
    segs, _ = mission()
    brow_item = dict(P.lead_item('Brow', BROW_AREA), leads='BOW_FIRST')
    eng_item = P.lead_item('engine fronts', ENG_AREA)
    k = P.K_CRATER[case]
    out = {'S': S_GRID, 'att': ATT_GRID, 'brow': [], 'engines': [], 'bumper_kg_m2': [], 'att_items': {}}
    for S in S_GRID:
        E_b = P.bumper_defeat_energy(S, case) if S > 0 else P.perforation_energy(0.005, k)
        out['brow'].append(P.events(brow_item, segs, E_b, case))
        out['engines'].append(P.events(eng_item, segs, E_b, case))
        out['bumper_kg_m2'].append(sum(P.bumper_kg_m2(S, case)) if S > 0 else 0.0)
    for key in ('blades', 'rings', 'body'):
        out['att_items'][key] = []
    for a in ATT_GRID:
        for c, E_f in _components(case, a):
            for key in ('blades', 'rings', 'body'):
                if c['name'].startswith(TRIP_ITEMS[key][0]):
                    out['att_items'][key].append(P.events(c, segs, E_f, case))
    out['optics'] = P.events(P.lead_item('optics', 4 * 0.5), segs, 100.0, case)
    return out


# ---------- build --------------------------------------------------------------------------------------------------------------------------
CHECKS = [(m, v) for m in (3e-16, 1e-12, 1e-9, 6e-8, 1e-6) for v in (7e3, 68.4e3, 0.01 * V_CRUISE, V_CRUISE)]


def inputs_hash():
    h = hashlib.sha256()
    for p in [HERE / 'model.py', *sorted(IMP.glob('*.py'))]:
        h.update(p.read_bytes())
    return h.hexdigest()[:16]


def _round(x):
    if isinstance(x, float):
        return float(f'{x:.5g}')
    if isinstance(x, dict):
        return {k: _round(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_round(v) for v in x]
    return x


def as_vertex_2_6():
    """The Vertex 2.6 numbers with its own mission path (protect.mission), for the comparison on the page."""
    segs, meta = P.mission(TB_TOTAL, VE, None)
    E_b = P.bumper_defeat_energy(2.0, 'NOMINAL')
    k = P.K_CRATER['NOMINAL']
    eng = P.lead_item('engine fronts', ENG_AREA)
    bh = [x for x in segs if x['phase'] == 'brake at home']
    return {'brow_breaches': P.events(dict(P.lead_item('Brow', BROW_AREA), leads='BOW_FIRST'), segs, E_b, 'NOMINAL'),
            'engine_breaches': P.events(eng, segs, P.perforation_energy(0.005, k), 'NOMINAL'),
            'engine_breaches_below_0_AU': P.events(eng, [x for x in bh if x['r'] < 0], P.perforation_energy(0.005, k), 'NOMINAL'),
            'min_r_AU': min(x['r'] for x in segs), 'destination_AU': meta['destination_AU']}


def build():
    trips = {c: trip(c) for c in CASES}
    lv = {c: levers(c) for c in CASES}
    nom = trips['NOMINAL']
    last = nom['rows'][-1]
    largest = {f'{v:.0f}': largest_stopped(v) for v in (7e3, 68.4e3, V_CRUISE)}
    d = {
        'study': 'lab/studies/dust-impacts', 'inputs_hash': inputs_hash(),
        'provenance': {'branch': 'claude/project-thread-6qwiwi', 'commit': '874dca7', 'justified_commit': 'f9c3cc3 (work/vertex-2-7/dust.py)',
                       'files': ['work/vertex-2-6/t02_environment.py', 'work/vertex-2-6/protect.py'],
                       'environment': 'T02 (claude/project-thread-uwi5pl 3c665ec), copied unchanged by Vertex 2.6'},
        'constants': {'v_cruise': V_CRUISE, 'c': C, 'rho_grain': RHO_GRAIN, 'rho_bumper': RHO_BUMPER, 'k_crater': P.K_CRATER,
                      'bumper': P.BUMPER, 't_over_d': P.T_OVER_D, 'wall_kg_m2': P.WALL_KG_M2, 'perf_ratio': P.PERF_RATIO,
                      'target_events': P.TARGET, 'amu': AMU, 'ev': EV, 'tnt': TNT, 'brow_area': BROW_AREA, 'eng_area': ENG_AREA},
        'stack': STACK, 'regimes': [list(r) for r in REGIMES], 'regime_sources': REGIME_SOURCES,
        'speeds': [list(s) for s in SPEEDS], 'masses': [list(m) for m in MASSES],
        'largest_stopped_kg': largest,
        'trip': {c: {'meta': t['meta'], 'phases': t['phases'], 'brow_defeat_E_J': t['brow_defeat_E_J'],
                     'cols': list(t['rows'][0].keys()), 'rows': [list(r.values()) for r in t['rows']]} for c, t in trips.items()},
        'trip_items': {k: v[1] for k, v in TRIP_ITEMS.items()},
        'levers': lv,
        # headline numbers at the full Vertex 2.6 resolution (240 steps per burn); the trip rows are thinned to 60 for the page
        'headline': {'brow_breaches': lv['NOMINAL']['brow'][S_GRID.index(2.0)], 'engine_breaches': lv['NOMINAL']['engines'][0],
                     'blade_punctures': lv['NOMINAL']['att_items']['blades'][ATT_GRID.index(0.2)],
                     'brow_breaches_high': lv['HIGH']['brow'][S_GRID.index(2.0)], 'brow_breaches_low': lv['LOW']['brow'][S_GRID.index(2.0)],
                     'engine_breaches_high': lv['HIGH']['engines'][0], 'trip_days': last['t_d'],
                     'brow_breaches_justified': lv['JUSTIFIED']['brow'][S_GRID.index(2.0)], 'engine_breaches_justified': lv['JUSTIFIED']['engines'][0]},
        'cases': list(CASES), 'case_labels': CASE_LABELS,
        'vertex_2_6': as_vertex_2_6(),
        'checks': [{'m': m, 'v': v, 'r': impact(m, v)} for m, v in CHECKS],
        'proto': {'stack': 'disruptor layer 5 mm C/C, skin 5 mm (thicknesses OPEN in canon)', 'trip_attitude_deg': 0.2,
                  'visual_rates': 'sparks on the page stand for many grains each; the counters are the model numbers'},
    }
    d = _round(d)
    (HERE / 'results').mkdir(exist_ok=True)
    (HERE / 'results' / 'dust.json').write_text(json.dumps(d, separators=(',', ':')) + '\n')
    return d


if __name__ == '__main__':
    d = build()
    h = d['headline']
    print(f"NOMINAL Vertex mission: Brow breaches beyond the 2 m disruptor {h['brow_breaches']:.4g} (LOW {h['brow_breaches_low']:.3g}, "
          f"HIGH {h['brow_breaches_high']:.4g}); engine-front breaches {h['engine_breaches']:.4g}; blade punctures {h['blade_punctures']:.3g}")
    print('largest grain the Brow stack stops:', {k: f'{v:.3g} kg' for k, v in d['largest_stopped_kg'].items()})
    for m, v in ((1e-9, 7e3), (1e-9, V_CRUISE), (1e-6, V_CRUISE), (3e-16, V_CRUISE)):
        r = impact(m, v)
        print(f'  {m:.0e} kg at {v / 1e3:,.0f} km/s: {r["E_J"]:.3g} J ({r["tnt_kg"] * 1e3:.3g} g TNT), {r["keV_per_u"]:.3g} keV/u, '
              f'{r["regime"]}, {r["outcome"]}')
    print('size', len((HERE / 'results' / 'dust.json').read_text()) // 1024, 'kB')
