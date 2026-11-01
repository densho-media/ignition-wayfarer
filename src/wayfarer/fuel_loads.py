"""Tank-farm loads, first-order sizing and heat leak (TANK-AXIAL, 2026-11-01, WORKING by Claude under the owner's delegation; PROTOTYPE
geometry from fuel_storage). Standard library only.

The thirteen axial vessels (fuel_storage.tanks) are fixed aft on insulating skirt struts standing on the thrust deck, and slide forward on
V-links, so thrust and the 1.5 g design case load the skirts and the deck; the forward links take lateral loads and cold contraction.

- schedule(s): each vessel's load along the burn (mass_model.balance per species); every vessel only drains (metered outlets, no
  transfers between vessels).
- vessels(s): first-order Al-Li pressure shell (MEOP plus the 1.5 g liquid head at the aft apex, weld factor, minimum gauge), its mass,
  MLI mass and the barrel's axial stress and unpressurised buckling margin (NASA SP-8007 knockdown) at 1.5 g.
- skirts(s): each vessel's skirt struts in compression at the flight peak and at 1.5 g full: stress and Euler margins, conducted heat.
- deck(s): each radial deck truss as a cantilever from the collar: root moment, chord force over the deck depth, the Ti chord and
  diagonal areas that carry it at the ultimate factor, and the resulting deck mass; the collar's axial and moment loads.
- heat(s): MLI radiation plus skirt conduction per species, the uncooled boil-off and the cryocooler lift a zero-boil-off store needs.
- contraction(s): axial shrink of each vessel between its aft fixity and forward links against the links' slide travel.
- dry_mass(s): first-order shells + MLI + skirts + deck + guides against the tankage budget (tank_dry_fraction x capacity).
- spine(s): axial load at stations, the mass forward of each station times the acceleration.

    python3 src/wayfarer/fuel_loads.py      # prints the result and writes references/p1_fuel_loads.json
"""
import json
import math
from pathlib import Path

import fuel_storage
import mass_model

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT/'references/p1_fuel_loads.json'
G0 = 9.80665
DAY = 86400.0


def q(s):
    return s['physics']['fuel_loads']


def design_accel(s):
    return q(s)['design_accel_g']*G0


def _tank_loads(s, left):
    st = mass_model.stores_at(s, left); out = {}
    for sp, key in (('helium-3', 'he3'), ('deuterium', 'd2'), ('hydrogen', 'h2')):
        rows, _ = mass_model.balance(s, sp, st[key])
        out.update({r['name']: r['kg'] for r in rows})
    return out


def schedule(s, steps=10):
    """Burn states: time, acceleration, and each vessel's propellant (kg)."""
    return [dict(t_s=st['t_s'], accel_m_s2=st['thrust_N']/st['mass_kg'], mass_kg=st['mass_kg'], left=st['mission_left'],
                 tanks=_tank_loads(s, st['mission_left'])) for st in mass_model.burn_states(s, steps)]


def _tube(r, w):
    return dict(A=2*math.pi*r*w, I=math.pi*r**3*w)


def vessels(s):
    """First-order shell and MLI of every vessel (see module doc)."""
    p = q(s); sh = p['shell']; rho = fuel_storage.cfg(s)['density_kg_m3']; a_d = design_accel(s); FS = p['ultimate_factor']; out = []
    for t in mass_model.tank_capacity(s):
        a = t['a']; head = rho[fuel_storage.INV_KEY[t['species']]]*a_d*(t['x_shell'][1]-t['x_shell'][0])*fuel_storage.fill_max(s)
        pr = sh['meop_Pa']+head
        th = max(sh['min_gauge_m'], pr*a*FS/(sh['yield_Pa']*sh['weld_factor']))
        A = mass_model.shell_area(t); m_shell = A*th*sh['density_kg_m3']
        a_env = t['a_env']; A_env = 2*math.pi*a_env*(t['y_ring'][1]-t['y_ring'][0])+2*1.38*math.pi*a_env*a_env
        m_mli = A_env*p['mli']['areal_kg_m2']
        # barrel axial stress at 1.5 g from the barrel and forward head pressing aft on the aft Y-ring (vessel fixed aft)
        m_fwd = m_shell*(1-1.38*math.pi*a*a/A)+m_mli/2
        s_in = m_fwd*a_d/(2*math.pi*a*th); s_p = sh['meop_Pa']*a/(2*th)
        phi = math.sqrt(a/th)/16; gam = 1-0.901*(1-math.exp(-phi))
        s_cr = 0.605*sh['E_Pa']*th/a*gam
        out.append(dict(name=t['name'], species=t['species'], cap_kg=t['cap_kg'], liquid_m3=t['liquid_m3'], design_pressure_Pa=pr,
                        thickness_m=th, shell_area_m2=A, envelope_area_m2=A_env, shell_kg=m_shell, mli_kg=m_mli,
                        barrel_axial_inertial_Pa=s_in, barrel_axial_pressure_Pa=s_p,
                        unpressurised_buckling_margin=s_cr/(s_in*FS)-1))
    return out


def _vessel_mass(s):
    """Loaded propellant at departure (flight), capacity at fill_max (design) and the first-order dry vessel (shell + MLI + skirt)."""
    dep = schedule(s, 1)[0]['tanks']; v = {r['name']: r for r in vessels(s)}; sk = skirt_mass(s)
    return {t['name']: dict(flight=dep[t['name']], design=t['cap_kg']*fuel_storage.fill_max(s),
                            dry=v[t['name']]['shell_kg']+v[t['name']]['mli_kg']+sk[t['name']]) for t in mass_model.tank_capacity(s)}


def _struts(s, t):
    out = []
    for st in fuel_storage.skirt_struts(s, t):
        d = [st['b'][k]-st['a'][k] for k in range(3)]; L = math.sqrt(sum(c*c for c in d)); out.append(dict(L=L, ux=d[0]/L, r=st['radius']))
    return out


def skirt_mass(s):
    k = fuel_storage.farm_cfg(s)['skirt']; p = q(s)['skirt']; tb = _tube(k['radius_m'], k['wall_m'])
    return {t['name']: sum(st['L'] for st in _struts(s, t))*tb['A']*p['density_kg_m3'] for t in fuel_storage.tanks(s)}


def skirts(s):
    """Skirt strut compression at the flight peak (the burn's highest acceleration with that vessel's load) and at 1.5 g full."""
    pq = q(s); k = fuel_storage.farm_cfg(s)['skirt']; p = pq['skirt']; tb = _tube(k['radius_m'], k['wall_m']); FS = pq['ultimate_factor']
    sch = schedule(s); vm = _vessel_mass(s); out = []
    for t in fuel_storage.tanks(s):
        st = _struts(s, t); ux = sum(abs(c['ux']) for c in st); L = max(c['L'] for c in st); m = vm[t['name']]
        flight = max((row['tanks'][t['name']]+m['dry'])*row['accel_m_s2'] for row in sch)
        design = (m['design']+m['dry'])*design_accel(s)
        F = design/ux; Pcr = math.pi**2*p['E_Pa']*tb['I']/L**2/pq['buckling_knockdown']
        out.append(dict(name=t['name'], struts=len(st), length_m=L, flight_load_N=flight, design_load_N=design, strut_force_N=F,
                        stress_margin=p['strength_Pa']/(F*FS/tb['A'])-1, buckling_margin=Pcr/(F*FS)-1,
                        heat_W=len(st)*tb['A']/L*p['conductivity_integral_W_m']))
    return out


def _strut_wall(F, L, r, pq):
    """Wall of a Ti tube of radius r that carries compression F (ultimate factor) in yield and in Euler buckling (knockdown)."""
    FS = pq['ultimate_factor']
    return max(F*FS/(pq['strut_yield_Pa']*2*math.pi*r), F*FS*pq['buckling_knockdown']*L*L/(math.pi**2*pq['strut_E_Pa']*math.pi*r**3))


def _span_moments(L, loads):
    """Simply supported span of length L with point loads (position, P): end reactions, peak moment and peak shear."""
    Rb = sum(P*x for x, P in loads)/L; Ra = sum(P for _, P in loads)-Rb
    pts = sorted(loads); M = 0.0; V = Ra; Mmax = 0.0; Vmax = abs(Ra); x0 = 0.0
    for x, P in pts:
        M += V*(x-x0); Mmax = max(Mmax, abs(M)); V -= P; Vmax = max(Vmax, abs(V)); x0 = x
    return Ra, Rb, Mmax, Vmax


def deck(s):
    """The thrust deck at 1.5 g full (and the flight peak). Inner trusses cantilever from the collar; outer trusses span collar -> tip, the tip
    tied to the bypass collar's forward hoop (owner pick 2026-11-01). Chords and diagonals of each truss, the tip ties, and the ring girder
    (the bypass collar's mid and forward hoops laced together) are sized to their loads; the ring spans between the three bypass girders as
    simply supported 120 deg arcs (continuity and torsion ignored: first order). Returns the sizes, mass and the interface loads."""
    import forward_shield
    pq = q(s); FS = pq['ultimate_factor']; sy = pq['strut_yield_Pa']; rho = pq['strut_density_kg_m3']; E = pq['strut_E_Pa']
    dk = fuel_storage.deck(s); h = dk['xf']-dk['xa']; vm = _vessel_mass(s); sch = schedule(s); rows = []; tot = 0.0
    panel = fuel_storage.farm_cfg(s)['deck']['panel_m']; rc = dk['chord_radius']
    ties = {c['truss']: c for c in fuel_storage.collar_ties(s)}; tie_rows = []; tips = []
    for tr in dk['trusses']:
        m = vm[tr['tank']]; arm = tr['R']-tr['root']; Ltr = tr['tip']-tr['root']
        W = (m['design']+m['dry'])*design_accel(s); Wf = max((row['tanks'][tr['tank']]+m['dry'])*row['accel_m_s2'] for row in sch)
        if tr['name'] in ties:
            b_ = tr['tip']-tr['R']; Rroot, Rtip = W*b_/Ltr, W*arm/Ltr; M = W*arm*b_/Ltr; V = max(Rroot, Rtip); Mroot = 0.0
            Mf = Wf*arm*b_/Ltr; tips.append((tr['azimuth_deg'], Rtip, Wf*arm/Ltr))
        else:
            Rroot, Rtip, M, V, Mroot, Mf = W, 0.0, W*arm, W, W*arm, Wf*arm
        F = M/h; A = F*FS/sy
        r_need = math.sqrt(2*F*FS*panel**2*pq['buckling_knockdown']/(math.pi**2*E*A))
        diag = math.hypot(h, panel); Ad = V*diag/h*FS/sy
        mass = 2*Ltr*A*rho+(Ltr/panel)*(diag*Ad+h*Ad*h/diag)*rho
        tot += mass
        rows.append(dict(name=tr['name'], tank=tr['tank'], tied=tr['name'] in ties, arm_m=arm, depth_m=h, flight_load_N=Wf, design_load_N=W,
                         root_reaction_N=Rroot, tip_reaction_N=Rtip, root_moment_N_m=Mroot, peak_moment_N_m=M, chord_force_N=F, chord_area_m2=A,
                         chord_wall_at_display_radius_m=A/(2*math.pi*rc), chord_radius_needed_m=r_need, flight_chord_force_N=Mf/h, mass_kg=mass))
        if tr['name'] in ties:
            c = ties[tr['name']]; t_mass = 0.0; worst = 0.0
            for a_, b2 in c['members']:
                L = math.dist(a_, b2); ux = abs(a_[0]-b2[0])/L; Ft = Rtip/(2*ux)
                w = _strut_wall(Ft, L, c['radius'], pq); t_mass += 2*math.pi*c['radius']*w*L*rho; worst = max(worst, Ft)
            tot += t_mass
            tie_rows.append(dict(name=c['name'], force_N=worst, wall_m=w, mass_kg=t_mass))
    hoop = sum(2*math.pi*hp['r']*_tube(hp['radius'], 0.01)['A']*rho for hp in dk['hoops'])
    # ring girder on the bypass hoops: tip reactions at the truss azimuths, supported at the girders
    lac = fuel_storage.ring_lacing(s); Rr = lac['r']; hr_ = lac['depth']; g = sorted(forward_shield.sector_azimuths(s))
    gdeg = [math.degrees(a) % 360 for a in g]; spans = []; girder = {round(d, 3): dict(design_N=0.0, flight_N=0.0) for d in gdeg}
    for i, d0 in enumerate(gdeg):
        d1 = gdeg[(i+1) % len(gdeg)]; span = (d1-d0) % 360; L = math.radians(span)*Rr
        on = [((az-d0) % 360, P, Pf) for az, P, Pf in tips if 0 < (az-d0) % 360 < span]
        Ra, Rb, Mm, Vm = _span_moments(L, [(math.radians(x)*Rr, P) for x, P, _ in on])
        Raf, Rbf, Mmf, _ = _span_moments(L, [(math.radians(x)*Rr, Pf) for x, _, Pf in on])
        girder[round(d0, 3)]['design_N'] += Ra; girder[round(d1, 3)]['design_N'] += Rb
        girder[round(d0, 3)]['flight_N'] += Raf; girder[round(d1, 3)]['flight_N'] += Rbf
        spans.append(dict(from_deg=d0, to_deg=d1, length_m=L, loads=len(on), peak_moment_N_m=Mm, peak_shear_N=Vm, flight_peak_moment_N_m=Mmf))
    Mr = max(sp['peak_moment_N_m'] for sp in spans); Vr = max(sp['peak_shear_N'] for sp in spans)
    Fc = Mr/hr_; Ac = Fc*FS/sy; ring_chords = 2*2*math.pi*Rr*Ac*rho
    p_arc = 2*math.pi*Rr/lac['panels']; dl = math.hypot(p_arc, hr_); Fd = Vr*dl/hr_
    wd = _strut_wall(Fd, dl, lac['radius'], pq); lacing = lac['panels']*2*math.pi*lac['radius']*wd*dl*rho
    ring = dict(radius_m=Rr, depth_m=hr_, spans=spans, chord_force_N=Fc, chord_area_m2=Ac, chord_kg=ring_chords, lacing_force_N=Fd,
                lacing_wall_m=wd, lacing_kg=lacing, girder_interface=girder,
                note='chord area is the requirement on the bypass mid/forward hoops (unsized, Q45); counted as new tankage, conservatively')
    collar = dict(axial_N=sum(r['root_reaction_N'] for r in rows), peak_root_moment_N_m=max(r['root_moment_N_m'] for r in rows),
                  bypass_collar_N=sum(v['design_N'] for v in girder.values()))
    return dict(depth_m=h, trusses=rows, ties=tie_rows, ring=ring, hoop_kg=hoop, collar=collar,
                trusses_kg=sum(r['mass_kg'] for r in rows), ties_kg=sum(r['mass_kg'] for r in tie_rows),
                mass_kg=tot+hoop+ring_chords+lacing)


def guides_mass(s):
    """Keel rails, forward hoop, ties and links as Ti tubes at their display radius and a 0.01 m wall (first order)."""
    rho = q(s)['strut_density_kg_m3']; L = lambda a, b: math.dist(a, b); m = 0.0
    for r in fuel_storage.keel_rails(s):
        m += L(r['a'], r['b'])*_tube(r['radius'], 0.01)['A']*rho
    h = fuel_storage.forward_hoop(s); m += 2*math.pi*h['r']*_tube(h['radius'], 0.01)['A']*rho
    m += sum(L(t['a'], t['b'])*_tube(t['radius'], 0.01)['A']*rho for t in h['ties'])
    for t in fuel_storage.tanks(s):
        m += sum(L(k['a'], k['b'])*_tube(k['radius'], 0.008)['A']*rho for k in fuel_storage.forward_links(s, t))
    return m


def heat(s):
    """Heat leak per species: MLI radiation on the envelope plus skirt conduction; uncooled boil-off; lift a zero-boil-off store needs."""
    p = q(s); v = vessels(s); sk = {r['name']: r['heat_W'] for r in skirts(s)}; out = {}
    for r in v:
        key = fuel_storage.INV_KEY[r['species']]; o = out.setdefault(key, dict(envelope_area_m2=0.0, mli_W=0.0, skirt_W=0.0))
        o['envelope_area_m2'] += r['envelope_area_m2']; o['mli_W'] += r['envelope_area_m2']*p['mli']['heat_flux_W_m2']; o['skirt_W'] += sk[r['name']]
    inv = fuel_storage.inventory(s)
    for key, o in out.items():
        o['total_W'] = o['mli_W']+o['skirt_W']; o['storage_K'] = p['storage_K'][key]
        o['uncooled_boiloff_kg_day'] = o['total_W']/p['latent_J_kg'][key]*DAY
        o['uncooled_boiloff_fraction_per_year'] = o['uncooled_boiloff_kg_day']*365.25/inv[key]
        o['carnot_input_W_at_300K'] = o['total_W']*(300.0-o['storage_K'])/o['storage_K']
    return out


def cooling(s):
    """Zero-boil-off concept: a ~20 K cooled shield round every vessel plus a 3 K stage for helium-3 (physics.fuel_loads.cooling). Lift, input
    power (= heat rejected, near ambient) and the LOW radiator section's margin after the stationary avionics."""
    c = q(s)['cooling']; h = heat(s); area = sum(o['envelope_area_m2'] for o in h.values()); he3 = h['helium_3']['envelope_area_m2']
    lift20 = area*c['shield_flux_W_m2']*c['support_factor']; lift3 = he3*c['he3_stage_flux_W_m2']*c['support_factor']
    rej = lift20*c['shield_W_per_W']+lift3*c['he3_W_per_W']
    low = next((x for x in s['radiators'].get('zones', {}).get('sections', []) if x['id'] == 'LOW'), None)
    return dict(shield_lift_W=lift20, he3_stage_lift_W=lift3, rejected_W=rej, low_section_load_W=low['load_W'] if low else None,
                low_section_margin_W=(low['load_W']-c['avionics_W']-rej) if low else None)


def contraction(s):
    g = fuel_storage.farm_cfg(s)['guides']; c = q(s)['thermal_contraction']
    rows = [dict(name=t['name'], axial_m=c*(t['y_ring'][1]-t['y_ring'][0]), radial_m=c*t['a']) for t in fuel_storage.tanks(s)]
    worst = max(r['axial_m'] for r in rows)
    return dict(worst_axial_m=worst, slide_travel_m=g['slide_travel_m'], margin_m=g['slide_travel_m']-worst, rows=rows)


def dry_mass(s):
    v = vessels(s); sk = skirt_mass(s); dk = deck(s)
    parts = dict(shells_kg=sum(r['shell_kg'] for r in v), mli_kg=sum(r['mli_kg'] for r in v), skirts_kg=sum(sk.values()),
                 deck_kg=dk['mass_kg'], guides_kg=guides_mass(s))
    cap = sum(t['cap_kg'] for t in mass_model.tank_capacity(s)); budget = q(s)['tank_dry_fraction']*cap
    return dict(parts, total_kg=sum(parts.values()), budget_kg=budget, capacity_kg=cap, margin_kg=budget-sum(parts.values()))


def spine(s, stations=(-113.25, -32.25, 95.15, 128.35)):   # drive, amidships, ring A, forward collar
    """Axial load at stations: the mass forward of each station times the acceleration, at departure and at burnout (peak)."""
    out = []
    for st in (mass_model.burn_states(s, 10)[i] for i in (0, -1)):
        a = st['thrust_N']/st['mass_kg']; sto = mass_model.stores_at(s, st['mission_left'])
        parts = mass_model.dry_parts(s)+mass_model.propellant_parts(s, sto['he3'], sto['d2'], sto['h2'])
        row = dict(t_s=st['t_s'], accel_m_s2=a, thrust_N=st['thrust_N'], stations={})
        for xs in stations:
            m = sum(pt['m']*min(1.0, max(0.0, (pt['x'][1]-xs)/(pt['x'][1]-pt['x'][0]))) if pt['x'][1] > pt['x'][0] else (pt['m'] if pt['x'][0] > xs else 0.0)
                    for pt in parts)
            row['stations'][str(xs)] = dict(mass_forward_kg=m, axial_N=m*a)
        out.append(row)
    return out


def report(s):
    sch = schedule(s); names = sorted(sch[0]['tanks'])
    drains = {n: all(b['tanks'][n] <= a['tanks'][n]+1e-6 for a, b in zip(sch, sch[1:])) for n in names}
    v = vessels(s); sk = skirts(s); dk = deck(s); ct = contraction(s); dm = dry_mass(s); fails = []
    if not all(drains.values()):
        fails.append('a vessel must be refilled during the burn (crossfeed needed): '+', '.join(n for n, ok in drains.items() if not ok))
    for r in sk:
        if min(r['stress_margin'], r['buckling_margin']) < 0:
            fails.append(f"{r['name']} skirt strut margin {min(r['stress_margin'], r['buckling_margin']):.2f} < 0 at {q(s)['design_accel_g']} g")
    if ct['margin_m'] < 0:
        fails.append(f"forward link slide {ct['slide_travel_m']} m < cold contraction {ct['worst_axial_m']:.3f} m")
    findings = []
    cl = cooling(s)
    if cl['low_section_margin_W'] is not None and cl['low_section_margin_W'] < 0:
        fails.append(f"cryocooler rejection {cl['rejected_W']/1e6:.2f} MW + avionics exceeds the LOW radiator section {cl['low_section_load_W']/1e6:.1f} MW")
    if dm['margin_kg'] < 0:     # OPEN, not a failure: the budget sets the mission's dry mass, which this pass may not change
        findings.append(f"first-order tankage {dm['total_kg']/1e3:.0f} t exceeds the tank_dry_fraction budget {dm['budget_kg']/1e3:.0f} t "
                        f"(deck {dm['deck_kg']/1e3:.0f} t at {q(s)['design_accel_g']} g)")
    return dict(status='WORKING', basis='first order; PROTOTYPE geometry (fuel_storage), materials and fluxes in physics.fuel_loads',
                draw=dict(tanks_drain_only=drains, departure={n: sch[0]['tanks'][n] for n in names}, burnout={n: sch[-1]['tanks'][n] for n in names},
                          peak_accel_m_s2=max(r['accel_m_s2'] for r in sch)),
                vessels=v, skirts=sk, deck=dk, heat=heat(s), cooling=cooling(s), contraction=ct, dry_mass=dm, spine=spine(s), open_findings=findings, failures=fails)


def check(s):
    return report(s)['failures']


if __name__ == '__main__':
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from spec import load
    s = load()[0]; r = report(s)
    OUTPUT.write_text(json.dumps(r, indent=1, default=float)+'\n')
    rd = lambda x: round(x, 3) if isinstance(x, float) else x
    print(json.dumps(dict(dry_mass=r['dry_mass'], heat=r['heat'], cooling=r['cooling'], contraction={k: v for k, v in r['contraction'].items() if k != 'rows'},
                          deck=dict(depth=r['deck']['depth_m'], mass=r['deck']['mass_kg'], trusses=r['deck']['trusses_kg'], ties=r['deck']['ties_kg'],
                                    hoops=r['deck']['hoop_kg'], collar=r['deck']['collar'], ring={k: v for k, v in r['deck']['ring'].items() if k != 'spans'},
                                    worst=max(r['deck']['trusses'], key=lambda t: t['chord_force_N']), tie=max(r['deck']['ties'], key=lambda t: t['force_N'])),
                          skirt_worst=min(r['skirts'], key=lambda t: min(t['stress_margin'], t['buckling_margin'])),
                          shell_worst=max(r['vessels'], key=lambda t: t['thickness_m']), peak=r['draw']['peak_accel_m_s2'],
                          open_findings=r['open_findings'], failures=r['failures']), indent=1, default=rd))
