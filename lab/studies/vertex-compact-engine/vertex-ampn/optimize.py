"""AMPN Phase 2: continuous optimisation of the B and E nozzles with the audited physics (work, noncanonical; standard library only).

  python3 lab/studies/vertex-compact-engine/vertex-ampn/optimize.py [--quick]      writes results/optimize.json and results/optimize.log

Objective: departure mass for the canon mission (four burns, fixed delta-v and jet power). Engine mass = RON 0.2 parts + the audit's
additions: LiH shadow slug at the plug base (ship neutron target 100 MW for four engines), 3-skin-depth Mo eddy shield on both faces
of each ring (20 kHz field ripple), nose neutron deposition 0.9 (fins), quench energy dump, 20 K refrigerator and its warm radiator,
cryogenic and power lines along the boom. Cant from the spacecraft-interception criterion (audit.py), not the RON cone rule.
Variables: ring radius R, burn distance kappa = x_burn/R, ship distance D, engine spacing S, current multiple; E adds the mirror coil's
current share. Nelder-Mead on log-scaled variables with bounds by clipping.
"""
import json
import math
import sys
import time
from multiprocessing import Pool
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent/'vertex-ron')); sys.path.insert(0, str(HERE))
import ron  # noqa: E402
import audit  # noqa: E402
import dust  # noqa: E402

SIGMA = 5.670374e-8
QUICK = '--quick' in sys.argv
N_PART = 160 if QUICK else 320
SHIP_NEUTRON_TARGET_W = 1e8
EPS_C = 0.3                                     # field-ripple coupling at the winding (nominal of 0.1-1, audit.py)
MATERIALS = {   # engineering current density (A/m2) and the limits that come with it (9.2): stabiliser for quench, manufacturing class
    'today': dict(Je=1.53e8, label='REBCO today (baseline)', cls='established'),
    'advanced': dict(Je=3e8, label='advanced REBCO, thinner substrate (advanced)', cls='advanced'),
    'speculative': dict(Je=6e8, label='future conductor (speculative)', cls='speculative'),
}


def design(fam, x):
    """Variant parameters from the optimisation vector."""
    R, kap, D, S = x[0], x[1], x[2], x[3]
    base = dict(ron.variants()['B_D800'])
    p = dict(base, label=f'{fam} R {R:.0f} kappa {kap:.2f} D {D:.0f} S {S:.0f}', family='hybrid' if fam == 'E' else 'intermediate',
             D_m=D, S_m=S, rings=[(kap*R, R, 10.0)], plug_x_m=(kap+1)*R, boom=True)
    if fam == 'E':
        p['plug_coil'] = (0.6, x[5])
    return p


def additions(v, k, src, r, Je):
    """Mass (t) and heat (W) the audit adds to one engine."""
    led = r['ledger']; Pn = src['P_n_W']; cap = r['capture']; E = src['P_charged_W']/v['f_pulse_Hz']
    add, heat = {}, {}
    # neutron shadow slug at the plug base
    sky_ship = (1-math.cos(math.atan(v['r_ship_m']/v['D_m'])))/2
    P_ship = 4*sky_ship*Pn*0.995
    ef = max(0.0, math.log(P_ship/SHIP_NEUTRON_TARGET_W))
    add['neutron_slug_t'] = math.pi*v['plug_r_m']**2*(ef/0.13/100*780)*1.15/1e3
    heat['slug_self_W'] = P_ship/4*(1-math.exp(-ef))
    # nose neutron deposition 0.9 instead of 0.3: extra fins at 2,000 K
    q20 = 0.85*SIGMA*2000.0**4
    extra = sum(r_['sky']*0.6*Pn for r_ in led['rows'] if r_['part'].startswith('RING'))
    add['nose_fins_extra_t'] = extra/(0.7*q20)/2*5.0/1e3
    heat['nose_extra_W'] = extra
    # eddy shield (Mo, 3 skin depths, both faces) and its ripple heat
    sig = 1.9e6; f = v['f_pulse_Hz']; delta = 1/math.sqrt(math.pi*f*4e-7*math.pi*sig)
    sh_t = 0.0; sh_W = 0.0
    for c in [c for c in v['coils'] if not c.get('shadowed')]:
        I = abs(c['I'])*cap['k']; Bw = 4e-7*math.pi*I/(2*c['depth']); A = 2*c['depth']*2*math.pi*ron.hoop_r(c)
        dB = EPS_C*E/(2*cap['W_J'])*Bw; H = dB/(4e-7*math.pi)
        sh_t += A*3*delta*10200/1e3; sh_W += H*H/(2*sig*delta)*A
    add['eddy_shield_t'] = sh_t; heat['eddy_shield_W'] = sh_W
    # quench energy dump: absorb the stored energy in a radiating refractory resistor (7.5e5 J/kg over 1,500 K)
    add['quench_dump_t'] = cap['W_J']/7.5e5/1e3
    # refrigeration: neutrons + static (1 W/m2) + residual ripple (~1.3 kW nominal) at 20 K; 1 kg/W_cold (PROTOTYPE, large future plant)
    cold = led['cold_W']+sum(2*(c['depth']+c['thick'])*2*math.pi*ron.hoop_r(c) for c in v['coils'])*1.0+1.3e3
    elec = cold*(k['cold_cost']-1)
    add['refrigerator_t'] = cold*1.0/1e3
    add['warm_radiator_t'] = (cold+elec)/(2*0.9*SIGMA*400.0**4)*5.0/1e3
    heat['refrigerator_rejected_W'] = cold+elec
    # boom services: cryogenic supply/return and 10 kV power, plus coolant for nothing else (plug and noses radiate passively)
    L = v['D_m']-v['plug_x_m']
    add['boom_services_t'] = L*(2*8.0+3.0)/1e3                         # two vacuum-jacketed lines 8 kg/m, cable 3 kg/m
    # dust (Phase 3, dust.py): passive protection of the whole ship booked per engine (NOMINAL environment)
    ring_R = max(ron.hoop_r(c) for c in v['coils'] if not c.get('shadowed'))
    add['dust_protection_t'] = dust.dust_mass_t(ring_R, v['plug_r_m'], v['S_m'], v['D_m'])[0]/4
    return add, heat


def evaluate(fam, x, k, pool, Je=1.53e8, n=N_PART, full=False):
    p = design(fam, x)
    try:
        v, src, E, cap = ron.configure(p, k, Je=Je)
        r = ron.evaluate(v, k, src, E, cap, x[4], pool, n, Je=Je)
    except Exception as ex:                                            # degenerate geometry
        return dict(departure_t=1e9, error=str(ex))
    add, heat = additions(v, k, src, r, Je)
    eng = r['engine_t']+sum(add.values())
    cd, _ = audit.min_cant(v, r['particles']['forward_exits'], src['P_charged_W'], n_phi=90)
    cd = 30.0 if cd is None else cd
    sh = ron.ship(k, eng, 4*r['ledger']['B01_W'], max(0.05, r['particles']['axial_efficiency']), cant_deg=cd)
    out = dict(fam=fam, x=list(x), departure_t=sh['departure_t'], engine_t=eng, ron_engine_t=r['engine_t'], add_t=add, heat_W=heat,
               cant_deg=cd, eta=r['particles']['axial_efficiency'], fwd=r['particles']['forward_energy_share'], ship=sh,
               field_ratio=r['capture']['field_ratio'], mass_t=r['mass_t'], self_W=r['ledger']['self_W'], piped_W=r['ledger']['B01_W'],
               plug_x_m=v['plug_x_m'], plug_r_m=v['plug_r_m'], Je=Je)
    if full:
        out['geometry'] = ron.export(v, r['capture'], src); out['geometry']['paths'] = r['particles']['paths']
        out['geometry']['cant_deg'] = cd
    return out


BOUNDS = {'B': [(15, 120), (1.0, 4.0), (300, 3000), (100, 1500), (1.0, 4.0)],
          'E': [(15, 120), (1.0, 4.0), (300, 3000), (100, 1500), (1.0, 4.0), (0.5, 8.0)]}


def clip(fam, x):
    return [min(max(a, lo), hi) for a, (lo, hi) in zip(x, BOUNDS[fam])]


def nelder_mead(fam, x0, k, pool, Je, iters, lines):
    """Nelder-Mead in log space (positive variables), clipped to the bounds."""
    f_cache = {}

    def f(lx):
        x = clip(fam, [math.exp(a) for a in lx]); key = tuple(round(a, 3) for a in x)
        if key not in f_cache:
            f_cache[key] = evaluate(fam, x, k, pool, Je)
        return f_cache[key]['departure_t'], f_cache[key]
    n = len(x0); s0 = [math.log(a) for a in x0]
    simplex = [s0]+[[a+(0.25 if i == j else 0.0) for j, a in enumerate(s0)] for i in range(n)]
    vals = [f(s) for s in simplex]
    for it in range(iters):
        order = sorted(range(n+1), key=lambda i: vals[i][0]); simplex = [simplex[i] for i in order]; vals = [vals[i] for i in order]
        if it % 5 == 0:
            b = vals[0][1]
            log(lines, f"  {fam} it {it:3d} best {b['departure_t']:8.0f} t engine {b['engine_t']:5.0f} t eta {b['eta']:.3f} cant {b['cant_deg']:4.1f} | "
                       + ' '.join(f'{a:.2f}' for a in b['x']))
        cen = [sum(s[j] for s in simplex[:-1])/n for j in range(n)]
        xr = [cen[j]+(cen[j]-simplex[-1][j]) for j in range(n)]; fr = f(xr)
        if fr[0] < vals[0][0]:
            xe = [cen[j]+2*(cen[j]-simplex[-1][j]) for j in range(n)]; fe = f(xe)
            simplex[-1], vals[-1] = (xe, fe) if fe[0] < fr[0] else (xr, fr)
        elif fr[0] < vals[-2][0]:
            simplex[-1], vals[-1] = xr, fr
        else:
            xc = [cen[j]+0.5*(simplex[-1][j]-cen[j]) for j in range(n)]; fc = f(xc)
            if fc[0] < vals[-1][0]:
                simplex[-1], vals[-1] = xc, fc
            else:
                for i in range(1, n+1):
                    simplex[i] = [simplex[0][j]+0.5*(simplex[i][j]-simplex[0][j]) for j in range(n)]; vals[i] = f(simplex[i])
    best = min(vals, key=lambda a: a[0])[1]
    return best, list(f_cache.values())


def log(lines, s):
    print(s, flush=True); lines.append(s)


def main():
    t0 = time.time(); lines = []; k = ron.canon(); out = {}
    (HERE/'results').mkdir(exist_ok=True); (HERE/'geometry').mkdir(exist_ok=True)
    starts = {'B': [50.0, 2.0, 800.0, 400.0, 1.6], 'E': [50.0, 2.0, 800.0, 400.0, 1.6, 4.0]}
    iters = 12 if QUICK else 40
    with Pool(4) as pool:
        for fam in ('B', 'E'):
            ref = evaluate(fam, starts[fam], k, pool)
            log(lines, f"{fam} start (RON point, audited): departure {ref['departure_t']:,.0f} t, engine {ref['engine_t']:.0f} t "
                       f"(RON parts {ref['ron_engine_t']:.0f} + additions {sum(ref['add_t'].values()):.0f}), cant {ref['cant_deg']}")
            out[f'{fam}_start'] = ref
            for mat, m in MATERIALS.items():
                x0 = starts[fam] if mat == 'today' else out[f'{fam}_today']['x']
                best, cloud = nelder_mead(fam, x0, k, pool, m['Je'], iters if mat == 'today' else iters//2, lines)
                best = evaluate(fam, best['x'], k, pool, m['Je'], n=1280, full=True)            # confirm at higher sampling
                (HERE/'geometry'/f'{fam}_{mat}.json').write_text(json.dumps(best.pop('geometry')))
                out[f'{fam}_{mat}'] = best
                out[f'{fam}_{mat}_cloud'] = [dict(x=c['x'], departure_t=c['departure_t'], engine_t=c.get('engine_t'), D=c['x'][2] if 'x' in c else None)
                                             for c in cloud if 'x' in c]
                a = best['add_t']
                log(lines, f"{fam} {mat:11s} OPT: departure {best['departure_t']:,.0f} t | engine {best['engine_t']:.0f} t (parts {best['ron_engine_t']:.0f}, "
                           f"slug {a['neutron_slug_t']:.0f}, eddy {a['eddy_shield_t']:.0f}, dump {a['quench_dump_t']:.0f}, fridge+rad "
                           f"{a['refrigerator_t']+a['warm_radiator_t']:.0f}, dust {a['dust_protection_t']:.0f}) | eta {best['eta']:.3f} cant {best['cant_deg']} | R {best['x'][0]:.0f} kappa "
                           f"{best['x'][1]:.2f} D {best['x'][2]:.0f} S {best['x'][3]:.0f} x{best['x'][4]:.2f}"
                           + (f" mirror {best['x'][5]:.2f}" if fam == 'E' else ''))
    out['wall_s'] = time.time()-t0
    (HERE/'results'/'optimize.json').write_text(json.dumps(out, indent=1, default=str))
    (HERE/'results'/'optimize.log').write_text('\n'.join(lines)+'\n')


if __name__ == '__main__':
    main()
