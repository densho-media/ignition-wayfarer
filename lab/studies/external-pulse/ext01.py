"""EXT-01 External Pulse Propulsion Architecture: bounded comparison of three concepts (research only, NOT canon).

A  mechanical pusher plate: the pulse debris stagnates on a plate behind the burn.
B  magnetic pusher: a coil near the burn turns the debris with its field.
C  remote field coupling: the same coil with a field inflated far beyond it, so the burn is far from all hardware.

The model is one energy and momentum ledger per joule of pulse yield, then the mission (rocket equation with the operating point's
tank growth, thrust from a burn-time share of the 6 y mission, the canon radiator's hot budget). It uses documented physical
principles only: isotropic emission into a solid angle, restitution, the magnetic virial theorem, the rocket equation. It contains no
pulse-unit or device design: the yield, its energy partition and any directionality enter as bounded numbers.

    python3 lab/studies/external-pulse/ext01.py            # writes results/ext01.json and the figures (about 1 min)
    python3 lab/studies/external-pulse/ext01.py --print    # summary only
"""
import argparse
import itertools
import json
import math
import sys
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT/'src'/'wayfarer'))
import operating_point as op  # noqa: E402
import spec  # noqa: E402

C = 299792458.0
G0 = 9.80665
YEAR = 365.25*86400.0
EVIDENCE = ROOT/'references'/'evidence'/'vertex_radiation.json'
RESULTS = HERE/'results'/'ext01.json'
VD_GRID = 20                                       # debris-speed grid points per case (log-spaced up to the burnup cap)


def params():
    return tomllib.loads((HERE/'params.toml').read_text())


def reference(S=None):
    """The mission and the released Vertex 1.5 result that EXT-01 is compared with (read, never changed)."""
    S = S or spec.load(ROOT)[0]
    q = op.p(S); b = op.burn(S); m = op.mission(S); R = json.loads(EVIDENCE.read_text())
    rad = S['radiators']; T_r = rad['temperature']['value']
    cold_K = 20.0; carnot = 0.3
    try:
        import vertex_radiation as vr
        c = vr.config(S); cold_K = c['cold_K']; carnot = c['carnot_fraction']
    except Exception:                                          # noqa: BLE001 - fall back to the documented T-01 values
        pass
    cop = carnot*cold_K/(T_r-cold_K)
    src = {cid: dict(photon=x['photon_share'], neutron=x['neutron_share']) for cid, x in R['sources']['cases'].items()}
    th = R['thermal']; cap = th['capacity_W']
    vertex_four = {cid: min(v['four_W'] for v in rows.values())/cap for cid, rows in th['cases'].items()}
    import vertex_magnet as vm
    vp = vm.plasma(S)
    F_eng = vp['mass_kg']*vp['exhaust_m_s']*vp['pulse_Hz']              # the engine's own design thrust (pulse momentum x rate)
    P_eng = R['gap']['fusion_W_per_engine']
    heat_eng = {cid: P_eng*src[cid]['photon']*R['gap']['cold_shielded']['radiator_heat_per_photon_W'] for cid in src}
    ve = q['exhaust_velocity_m_s']; F_cap = op.power_cap_N(S)
    vertex_burn_s = sum(x*ve/F_cap for x in m['burn_expelled_kg'])        # the four power-limited burns of the canon schedule
    return dict(
        vertex_burn_fraction=vertex_burn_s/(S['mission']['duration']['value']*YEAR), dv_burn=b['delta_v_m_s'], burns=m['burns'], dv_total=b['delta_v_m_s']*m['burns'], cruise_c=S['mission']['target_speed']['value'],
        mission_s=S['mission']['duration']['value']*YEAR, protected_kg=q['protected_and_operational_kg'], legacy_kg=q['legacy_inventory_kg'],
        tank_fraction=S['physics']['fuel_loads']['tank_dry_fraction'], departure_upper_kg=S['physics']['departure_mass']['upper_kg'],
        departure_kg=m['departure_mass_kg'], end_kg=m['end_mass_kg'], propellant_kg=m['propellant_kg'],
        ve_ref=q['exhaust_velocity_m_s'], eps=q['dhe3_specific_energy_J_kg'], hot_budget_W=b['hot_budget_W'], reject_W=b['ideal_rejection_W'],
        cop=cop, cold_K=cold_K, carnot=carnot, radiator_K=T_r, sources=src,
        vertex=dict(outcome=R['outcome'], verdict=R['verdict'], thrust_per_engine_N=F_eng, fusion_per_engine_W=P_eng,
                    radiator_multiple_min=min(vertex_four.values()), radiator_multiple=vertex_four,
                    heat_per_N_cold_shielded={cid: h/F_eng for cid, h in heat_eng.items()},
                    photon_share_needed=R['gap']['cold_shielded']['photon_share_needed'],
                    gap=[R['gap']['cold_shielded']['factor_low'], R['gap']['cold_shielded']['factor_high']],
                    neutron_W_per_N={cid: src[cid]['neutron']*P_eng/F_eng for cid in src},
                    budget_W_per_N=b['hot_budget_W']/(4.0*F_eng), pulse_Hz=vp['pulse_Hz'], yield_J=vp['yield_J'],
                    four_engine_thrust_N=4.0*F_eng),
        mission_peak_thrust_N=b['peak_thrust_N'], mission_peak_fusion_W=b['peak_fusion_power_W'])


def mission(ref, v_eff, m_sys, burn_fraction):
    """Departure mass, propellant and thrust for four burns at v_eff with m_sys of propulsion hardware added to the protected mass.
    Same tank growth as operating_point.mission (tank dry mass grows with propellant beyond the legacy inventory). None if the
    tanks alone cannot carry it (the rocket equation with tank growth has no solution)."""
    f = ref['tank_fraction']
    if v_eff <= 0.0 or ref['dv_total']/v_eff > math.log(1.0+1.0/f):
        return None
    R = math.exp(ref['dv_total']/v_eff)
    if (R-1.0)*f >= 1.0:
        return None
    end0 = ref['protected_kg']+m_sys; p0 = ref['legacy_kg']
    P = (R-1.0)*(end0-f*p0)/(1.0-(R-1.0)*f); end = end0+f*(P-p0); m0 = end+P
    T = burn_fraction*ref['mission_s']
    return dict(mass_ratio=R, propellant_kg=P, end_kg=end, departure_kg=m0, thrust_N=P*v_eff/T, burn_s=T)


def geometry(concept, p):
    """Hardware solid-angle share g_h, captured debris share g_k and the mean cosines (normal momentum c1, normal energy c2)."""
    if concept == 'A':
        th = math.radians(p['half_angle_deg']); g_h = (1.0-math.cos(th))/2.0
        if p['directed'] == 'iso':
            return g_h, g_h, (1.0+math.cos(th))/2.0, (1.0+math.cos(th)+math.cos(th)**2)/3.0
        return g_h, max(float(p['directed']), g_h), 1.0, 1.0
    # B and C: coil of radius R, field reach k R; the burn sits on the axis at L = k R / sin(theta_b), the bubble filling a cone
    # of half-angle theta_b. The coil's conductor (thickness w) is a ring the burn sees at distance D = sqrt(L^2 + R^2):
    # sky share = sin(psi) * (w / D) / 2 with sin(psi) = R / D, i.e. (w/R) / (2 (1 + (L/R)^2)).  (L = 0: the torus band a/R.)
    th = math.radians(p['capture_deg']); LR = p['reach']/math.sin(th)
    g_h = p['thickness_over_radius']/(2.0*(1.0+LR*LR))
    if p['directed'] == 'iso':
        return g_h, (1.0-math.cos(th))/2.0, (1.0+math.cos(th))/2.0, (1.0+math.cos(th)+math.cos(th)**2)/3.0
    return g_h, float(p['directed']), 1.0, 1.0


def _mass_factor(p):
    """An isolated pulse carries no net momentum. Isotropic debris balances itself; a directed pulse sending a mass share beta
    forward at v_d must send the rest back at beta v_d / (1 - beta), so the debris mass per joule shrinks by (1 - beta) / beta
    (energy = m v_d^2 beta / (2 (1 - beta))). This is what caps any directed pulse at beta = 1/2."""
    if p['directed'] == 'iso':
        return 1.0
    b = float(p['directed']); return (1.0-b)/b


def v_cap(p):
    """Fastest captured-debris speed: the pulse mass is at least its fuel, which carries f_k of b eps per kilogram."""
    f_g = (1.0-p['photon_conversion'])*p['photon']; f_k = 1.0-f_g-p['neutron']
    return math.sqrt(2.0*f_k*p['burnup']*_EPS[0]*_mass_factor(p)) if _EPS else None


_EPS = []


def ledger(concept, p, v_d, ref):
    """Energy and momentum per joule of yield. Returns the ledger, impulse, expended mass, heat into hardware and radiator load."""
    f_g = (1.0-p['photon_conversion'])*p['photon']; f_n = p['neutron']; f_k = 1.0-f_g-f_n
    g_h, g_k, c1, c2 = geometry(concept, p)
    e = p['restitution']; lam = p.get('leak', 0.0)
    m_d = 2.0*f_k/(v_d*v_d)*_mass_factor(p)                    # debris mass per joule (f_k shared out, captured part at v_d)
    E_c = 0.5*g_k*m_d*v_d*v_d                                  # captured debris kinetic energy
    leak = lam*E_c; E_r = E_c-leak                             # leak lands on hardware; the rest meets the field or plate
    diss = (1.0-e*e)*c2*E_r                                    # normal-energy loss in the turn (restitution e)
    to_hw_diss = (p['stagnation_to_plate'] if concept == 'A' else g_h)*diss
    hw = dict(photon=f_g*g_h, neutron=f_n*g_h*p['neutron_absorbed'], debris=to_hw_diss+leak)
    Q = sum(hw.values())
    esc = dict(photon=f_g*(1.0-g_h), neutron=f_n*(1.0-g_h*p['neutron_absorbed']), debris_uncaptured=f_k-E_c,
               debris_reflected=E_r-diss, radiated=diss-to_hw_diss)
    I = m_d*v_d*g_k*c1*((1.0-lam)*(1.0+e)+lam)                  # leaked debris stops on the hardware (no rebound)
    I_debris = I
    I += f_g*g_h*c1/C                                          # photon momentum absorbed by the hardware (about 1e-3 of it or less)
    m_abl = Q/p['ablation_J_kg'] if p.get('cooling') == 'ablative' else 0.0
    if concept == 'A':
        rad = 0.0 if p.get('cooling') == 'ablative' else Q
    else:
        rad = Q*(1.0-p['cold_share'])+Q*p['cold_share']*(1.0+1.0/ref['cop'])
    m_exp = m_d+m_abl
    return dict(hw=hw, esc=esc, Q=Q, I=I, v_debris=I_debris/m_exp, m_d=m_d, m_abl=m_abl, m_exp=m_exp, v_eff=I/m_exp, rad=rad, g_h=g_h, g_k=g_k, c1=c1,
                f_k=f_k, f_g=f_g, f_n=f_n, E_c=E_c, exhaust_KE=esc['debris_uncaptured']+esc['debris_reflected'])


def evaluate(concept, p, v_d, ref, multiple=1.0):
    """One case at one debris speed: ledger, mission, pulse, hardware mass, gates. Fixed point on the hardware mass."""
    L = ledger(concept, p, v_d, ref)
    v_eff = L['v_eff']; out = dict(v_d=v_d, v_eff=v_eff, isp_s=v_eff/G0, heat_fraction=L['Q'], radiator_per_J=L['rad'],
                                   heat_per_N=L['rad']/L['I'], impulse_per_J=L['I'], g_h=L['g_h'], g_k=L['g_k'])
    if not _EPS:
        _EPS.append(ref['eps'])
    vc = v_cap(p)
    m_sys = 0.0; M = None
    for _ in range(40):
        M = mission(ref, v_eff, m_sys, p['burn_fraction'])
        if M is None or M['departure_kg'] > 1e12:
            M = None; break
        P_f = M['thrust_N']/L['I']; f = p['rate_Hz']; Y = P_f/f; I_p = L['I']*Y
        if concept == 'A':
            # plate: its per-pulse velocity change must fit the shock-absorber stroke at rate f and stay below the allowed jump
            hw = max(I_p/(2.0*math.pi*f*p['stroke_m']), I_p/p['plate_dv_m_s'])
        else:
            W_B = p['field_energy_factor']*p['reach']**3*L['E_c']*Y
            hw = W_B/p['specific_strength_J_kg']               # magnetic virial theorem
        if abs(hw-m_sys) <= 1e-6*max(hw, 1.0):
            m_sys = hw; break
        m_sys = hw
    if M is None:
        out.update(closes=False, closure=math.inf, reason='mass ratio beyond the tank-growth limit', departure_kg=math.inf)
        return out
    P_f = M['thrust_N']/L['I']; f = p['rate_Hz']; Y = P_f/f; I_p = L['I']*Y
    W_rad = P_f*L['rad']; cycles = f*M['burn_s']
    allowed = ref['departure_upper_kg']*multiple
    # Schedule: a burn at constant thrust covers half the distance a cruise at full speed would, so longer burns than the canon
    # schedule's delay the LOCKED 6 y mission by half the extra burn time (the cruise speed stays 0.016 c).
    delay = max(0.0, (p['burn_fraction']-ref['vertex_burn_fraction'])*ref['mission_s']/2.0)
    gates = dict(mass=M['departure_kg']/allowed, heat=W_rad/ref['hot_budget_W'], speed=v_d/vc,
                 fatigue=cycles/p['fatigue_cycles_limit'], schedule=(ref['mission_s']+delay)/ref['mission_s'])
    out.update(M, fusion_W=P_f, yield_J=Y, yield_t_TNT=Y/4.184e9, rate_Hz=f, pulse_impulse_Ns=I_p, hardware_kg=m_sys,
               radiator_load_W=W_rad, radiator_multiple=W_rad/ref['hot_budget_W'], cycles=cycles, gates=gates,
               closure=max(gates.values()), closes=max(gates.values()) <= 1.0+1e-12, v_cap=vc, schedule_delay_y=delay/YEAR,
               closure_without_schedule=max(v for k, v in gates.items() if k != 'schedule'),
               fuel_kg=P_f*M['burn_s']/(p['burnup']*ref['eps']), ablated_kg=L['m_abl']*P_f*M['burn_s'],
               mean_accel_g=M['thrust_N']/((M['departure_kg']+M['end_kg'])/2.0)/G0,
               neutron_W_per_N=p['neutron']/L['I'], heat_W_per_N_budget=ref['hot_budget_W']/M['thrust_N'])
    if concept == 'A':
        dv_plate = I_p/m_sys; out['plate_dv_m_s'] = dv_plate; out['plate_peak_g'] = dv_plate/p['contact_s']/G0
    else:
        out['field_energy_J'] = p['field_energy_factor']*p['reach']**3*L['E_c']*Y
    return out


def _burn_fractions(P):
    return [x for x in P['mission']['burn_fraction']]+[reference_burn_fraction()]


_RBF = []


def reference_burn_fraction():
    if not _RBF:
        _RBF.append(reference()['vertex_burn_fraction'])
    return _RBF[0]


def _axes(P, concept):
    s, A = P['source'], P[concept]
    ax = dict(case=s['cases'], burnup=s['burnup'], photon_conversion=s['photon_conversion'], directed=s['directed'],
              restitution=A['restitution'], neutron_absorbed=A['neutron_absorbed'][:1],
              rate_Hz=P['pulse']['rate_ceiling_Hz'], burn_fraction=_burn_fractions(P))
    if concept == 'A':
        ax.update(half_angle_deg=A['half_angle_deg'], stagnation_to_plate=A['stagnation_to_plate'],
                  cooling=['radiator']+[f'ablative:{h}' for h in A['ablation_J_kg']])
    else:
        ax.update(reach=A['reach'], thickness_over_radius=A['thickness_over_radius'], leak=A['leak'], capture_deg=[30.0, 60.0, 90.0])
    return ax


def _fixed(P, concept, ref):
    """Secondary levers held at their optimistic end in the search (their effect is shown by the sensitivity rows)."""
    A = P[concept]; d = dict(burn_fraction=reference_burn_fraction(), rate_Hz=P['pulse']['rate_ceiling_Hz'][0],
                             contact_s=P['pulse']['contact_s'], fatigue_cycles_limit=P['pulse']['fatigue_cycles_limit'])
    if concept == 'A':
        d.update(stroke_m=A['stroke_m'][0], ablation_J_kg=A['ablation_J_kg'][0], plate_dv_m_s=A['plate_dv_m_s'][0])
    else:
        d.update(cold_share=A['cold_share'][0], specific_strength_J_kg=A['specific_strength_J_kg'][0],
                 field_energy_factor=A['field_energy_factor'])
    return d


def case(P, concept, ref, combo):
    p = dict(_fixed(P, concept, ref)); p.update(combo)
    p.update(ref['sources'][combo['case']])
    if concept == 'A' and str(combo.get('cooling', '')).startswith('ablative:'):
        p['ablation_J_kg'] = float(combo['cooling'].split(':')[1]); p['cooling'] = 'ablative'
    return p


def best_over_vd(concept, p, ref, multiple=1.0):
    """Scan the debris speed up to the burnup cap and return the evaluation with the smallest closure factor."""
    if not _EPS:
        _EPS.append(ref['eps'])
    vc = v_cap(p)
    best = None
    for i in range(VD_GRID):
        v_d = vc*10.0**(-4.0*(VD_GRID-1-i)/(VD_GRID-1))
        r = evaluate(concept, p, v_d, ref, multiple)
        if best is None or (r['closure'], -r['v_eff']) < (best['closure'], -best['v_eff']):
            best = r
    return best


def _one(args):
    P, concept, ref, combo, multiple = args
    r = best_over_vd(concept, case(P, concept, ref, combo), ref, multiple); r['combo'] = combo
    return r


def search(P, concept, ref, multiple=1.0, jobs=4):
    """Full factorial over the concept's brackets (deterministic order; the process pool only splits the work)."""
    ax = _axes(P, concept); keys = list(ax)
    work = [(P, concept, ref, dict(zip(keys, vals)), multiple) for vals in itertools.product(*(ax[k] for k in keys))]
    if jobs <= 1:
        return [_one(w) for w in work]
    from concurrent.futures import ProcessPoolExecutor
    with ProcessPoolExecutor(jobs) as ex:
        return list(ex.map(_one, work, chunksize=512))


def summarise(rows):
    fin = [r for r in rows if math.isfinite(r['closure'])]
    best = min(rows, key=lambda r: r['closure'])
    vmax = max(rows, key=lambda r: r['v_eff'])
    cool = [r for r in fin if r['gates']['heat'] <= 1.0]
    vcool = max(cool, key=lambda r: r['v_eff']) if cool else None
    heavy = [r for r in fin if r['gates']['mass'] <= 1.0]
    hmin = min(heavy, key=lambda r: r['gates']['heat']) if heavy else None
    ladder = []
    for name, keep in LADDER:
        sub = [r for r in rows if keep(r['combo'])]
        b = min(sub, key=lambda r: r['closure'])
        ladder.append(dict(step=name, cases=len(sub), closes=sum(1 for r in sub if r['closes']), best_closure=b['closure'],
                           gates=b.get('gates'), v_eff=b['v_eff'], combo=b['combo'],
                           v_eff_max=max(r['v_eff'] for r in sub), isp_max_s=max(r['v_eff'] for r in sub)/G0))
    loose = [r for r in fin if r['closure_without_schedule'] <= 1.0+1e-12]
    canon = [r for r in fin if r['gates']['schedule'] <= 1.0+1e-12]
    return dict(cases=len(rows), closes=sum(1 for r in rows if r['closes']), closes_without_schedule=len(loose), ladder=ladder,
                best=best, best_on_canon_schedule=min(canon, key=lambda r: r['closure']) if canon else None,
                best_without_schedule=min(fin, key=lambda r: r['closure_without_schedule']) if fin else None,
                fastest=vmax, fastest_within_heat=vcool, coolest_within_mass=hmin,
                closing_counts=_counts(loose))


# The assumption ladder: each step removes one UNVERIFIED or unestablished best case and keeps the rest of the brackets.
LADDER = [
    ('all brackets, including UNVERIFIED ones', lambda c: True),
    ('no photon conversion (a bare burn: absorbing mass is not modelled, so conversion at the fuel-only speed cap is inconsistent)',
     lambda c: c['photon_conversion'] == 0.0),
    ('isotropic pulse (no directional fusion pulse is established)', lambda c: c['photon_conversion'] == 0.0 and c['directed'] == 'iso'),
    ('leak at least the 1.4 minimum (1 %), A unaffected', lambda c: c['photon_conversion'] == 0.0 and c['directed'] == 'iso'
     and c.get('leak', 1.0) >= 0.01),
]


def _counts(rows):
    """How often each bracket value appears among the cases that close (schedule aside): which assumptions closure needs."""
    out = {}
    for r in rows:
        for k, v in r['combo'].items():
            out.setdefault(k, {}); out[k][str(v)] = out[k].get(str(v), 0)+1
    return out


def sensitivity(P, concept, ref, combo):
    """From a case, move one secondary lever at a time to its nominal and pessimistic values."""
    out = []
    A = P[concept]
    levers = {}
    if concept == 'A':
        levers['stroke_m'] = A['stroke_m']; levers['plate_dv_m_s'] = A['plate_dv_m_s']
    else:
        levers.update(cold_share=A['cold_share'], specific_strength_J_kg=A['specific_strength_J_kg'])
    levers['neutron_absorbed'] = A['neutron_absorbed']
    for k, vals in levers.items():
        for v in vals:
            p = case(P, concept, ref, combo); p[k] = v
            r = best_over_vd(concept, p, ref)
            out.append(dict(lever=k, value=v, closure=r['closure'], gates=r.get('gates'), v_eff=r['v_eff']))
    return out


def requirement(ref, P):
    """Mission-level requirements independent of any concept."""
    out = {}
    for mult in P['mission']['departure_multiples']:
        lo, hi = 1e4, 1e9                                       # bisection on v_eff for departure = envelope x multiple (no hardware)
        for _ in range(100):
            mid = math.sqrt(lo*hi); M = mission(ref, mid, 0.0, P['mission']['burn_fraction'][0])
            if M is None or M['departure_kg'] > ref['departure_upper_kg']*mult:
                lo = mid
            else:
                hi = mid
        out[str(mult)] = hi
    tank_limit = ref['dv_total']/math.log(1.0+1.0/ref['tank_fraction'])
    return dict(v_eff_needed=out, tank_growth_limit_v_eff=tank_limit,
                per_burn_ratio_at={str(v): math.exp(ref['dv_burn']/v) for v in (3e4, 3e5, 3e6, ref['ve_ref'])})


def heat_law(ref, P, f_k=0.85, mu=1.0, v_eff=None):
    """Closed form behind the search: with no ablation, v_eff = mu v_d, heat per newton = kappa v_eff / (2 f_k mu^2) and the thrust
    is P v_eff / (phi T), so the radiator holds kappa <= 2 f_k mu^2 phi T H / (v_eff^2 P)."""
    v = v_eff or ref['ve_ref']; M = mission(ref, v, 0.0, ref['vertex_burn_fraction'])
    T = ref['vertex_burn_fraction']*ref['mission_s']
    return 2.0*f_k*mu*mu*T*ref['hot_budget_W']/(v*v*M['propellant_kg'])


def run():
    P = params(); S = spec.load(ROOT)[0]; ref = reference(S)
    req = requirement(ref, P)
    concepts = {}
    for c in ('A', 'B', 'C'):
        rows = search(P, c, ref)
        s = summarise(rows)
        relaxed = {}
        for mult in P['mission']['departure_multiples'][1:]:
            rr = [dict(best_over_vd(c, case(P, c, ref, r['combo']), ref, mult), combo=r['combo'])
                  for r in sorted(rows, key=lambda r: r['closure'])[:60]]
            b = min(rr, key=lambda r: r['closure'])
            relaxed[str(mult)] = dict(closure=b['closure'], gates=b.get('gates'), v_eff=b['v_eff'], combo=b['combo'], closes=b['closes'])
        nominal = {k: v[min(1, len(v)-1)] for k, v in _axes(P, c).items()}
        if c == 'A':
            nominal['cooling'] = 'radiator'
        else:
            nominal['leak'] = P[c]['leak'][1]
        pn = case(P, c, ref, nominal)
        if c == 'A':
            pn['stroke_m'] = P[c]['stroke_m'][1]; pn['plate_dv_m_s'] = P[c]['plate_dv_m_s'][1]
        else:
            pn.update(cold_share=P[c]['cold_share'][1], specific_strength_J_kg=P[c]['specific_strength_J_kg'][1])
        nom = best_over_vd(c, pn, ref); nom['combo'] = nominal
        led = ledger(c, pn, nom['v_d'], ref)
        extra = {}
        if c == 'A':
            abl = [r for r in rows if str(r['combo']['cooling']).startswith('ablative')]
            fa = max(abl, key=lambda r: r['v_eff']); extra['fastest_ablative'] = dict(v_eff=fa['v_eff'], combo=fa['combo'])
            extra['hardware_sky_range'] = [min(r['g_h'] for r in rows), max(r['g_h'] for r in rows)]
        else:
            extra['hardware_sky_range'] = [min(r['g_h'] for r in rows), max(r['g_h'] for r in rows)]
            base = s['ladder'][1]['combo']                      # best bare-burn case: the leak it could tolerate
            lo, hi = 0.0, 0.01
            for _ in range(40):
                mid = (lo+hi)/2.0; r = best_over_vd(c, case(P, c, ref, dict(base, leak=mid)), ref)
                if r['gates']['heat'] <= 1.0 if r.get('gates') else False:
                    lo = mid
                else:
                    hi = mid
            extra['leak_allowed_bare_burn'] = lo
        concepts[c] = dict(name=P[c]['name'], summary=s, derived=extra, nominal=nom, nominal_ledger=led, relaxed=relaxed,
                           sensitivity=sensitivity(P, c, ref, s['best']['combo']))
    return dict(study='EXT-01', version=P['study']['version'], status='NON_CANON', input_hash=input_hash(S), reference=ref,
                requirement=req, kappa_allowed_at_ve_ref={str(mu): heat_law(ref, P, mu=mu) for mu in (0.5, 1.0, 2.0)},
                concepts=concepts, precedents=P['precedent'], verdict=verdict(concepts, req, ref))


def verdict(concepts, req, ref):
    """Outcome from the assumption ladder: what closes with every bracket, and what closes on established physics only."""
    lad = {c: [st['closes'] for st in v['summary']['ladder']] for c, v in concepts.items()}
    optimistic = [c for c, l in lad.items() if l[0]]
    established = [c for c, l in lad.items() if l[2]]
    if established:
        outcome = 'CLOSES_ON_ESTABLISHED_PHYSICS'
        text = f"{', '.join(established)} close(s) with an isotropic bare pulse."
    elif optimistic:
        outcome = 'CONDITIONAL_ON_UNVERIFIED'
        text = (f"Only {', '.join(optimistic)} close(s), and only at the corner where every UNVERIFIED best case holds at once; with an "
                "isotropic bare pulse no concept closes the 0.016 c four-burn mission.")
    else:
        outcome = 'ALL_INFEASIBLE_AT_MISSION'
        text = 'No concept closes the 0.016 c four-burn mission, even at the optimistic corner of every bracket.'
    return dict(outcome=outcome, ladder=lad, optimistic=optimistic, established=established, text=text)


def input_hash(S):
    import hashlib
    h = hashlib.sha256()
    h.update((HERE/'params.toml').read_bytes()); h.update(Path(__file__).read_bytes()); h.update(EVIDENCE.read_bytes())
    h.update(json.dumps(op.mission(S), sort_keys=True).encode())
    return h.hexdigest()[:16]


def _clean(x):
    if isinstance(x, float):
        return x if math.isfinite(x) else None
    if isinstance(x, dict):
        return {k: _clean(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_clean(v) for v in x]
    return x


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--print', action='store_true'); a = ap.parse_args()
    R = run()
    if not a.print:
        RESULTS.parent.mkdir(exist_ok=True)
        RESULTS.write_text(json.dumps(_clean(R), indent=1, sort_keys=False)+'\n')
        import figures
        figures.write(R)
    req = R['requirement']
    print('v_eff needed (km/s) by departure multiple:', {k: round(v/1e3) for k, v in req['v_eff_needed'].items()})
    for c, v in R['concepts'].items():
        s = v['summary']; b = s['best']
        print(c, v['name'], 'closes', s['closes'], '/', s['cases'], 'best closure', f"{b['closure']:.3g}",
              'gates', {k: f'{x:.3g}' for k, x in (b.get('gates') or {}).items()}, 'v_eff km/s', round(b['v_eff']/1e3))
        bc = s['best_on_canon_schedule']; bw = s['best_without_schedule']
        print('   closes without schedule', s['closes_without_schedule'], '; best on canon schedule', f"{bc['closure']:.3g}",
              {k: f'{x:.3g}' for k, x in bc['gates'].items()}, bc['combo'])
        for st in s['ladder']:
            print('   ladder', st['step'][:40], st['closes'], '/', st['cases'], f"{st['best_closure']:.3g}",
                  {k: f'{x:.3g}' for k, x in (st['gates'] or {}).items()})
        print('   fastest', round(s['fastest']['v_eff']/1e3), 'km/s; fastest within heat',
              round(s['fastest_within_heat']['v_eff']/1e3) if s['fastest_within_heat'] else None,
              '; relaxed', {m: f"{r['closure']:.3g}" for m, r in v['relaxed'].items()})
    print(R['verdict']['outcome'])


if __name__ == '__main__':
    main()
