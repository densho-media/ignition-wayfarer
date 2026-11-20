"""Vertex 2.7: exhaust velocity, fuel cycle, He-3 and spine length on the Vertex 2.6 candidate C ledger (research, not canon).

    python3 lab/studies/vertex-closure/vertex-2-7/mission.py      writes lab/studies/vertex-closure/vertex-2-7/mission.json and mission.log (needs fuel.json and ../vertex-2-6; ~3-5 min)

Reuses lab/studies/vertex-closure/vertex-2-6/compact.py unchanged (engine, close, geometry, design) and its protect.py for the dust protection mass, so every
number here sits on the same coupled mass, power, radiator, shielding and propellant ledger as Vertex 2.6. What 2.7 adds:
1. the exhaust's velocity spread as a momentum loss (fuel.py): the effective nozzle efficiency is kappa^2 x eta_dispersion; 2.6 booked
   eta_dispersion = 1 (all exhaust at one speed);
2. exhaust speeds up to the physical ceiling (grid to 0.088 c), burnup to 0.99, nozzle divergence beyond the traced options as stated
   requirement levels (kappa 0.95 / 0.97, PROTOTYPE extrapolations, not traced);
3. He-3 consumed per mission and the speed that minimizes it;
4. the spine length the heat-flux gates need for each isotropic share, with the dust protection recomputed for each length;
5. the smallest remaining gaps to the canon 4.6 kt departure envelope.
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
V26 = HERE.parent/'vertex-2-6'
HALO = ROOT/'lab'/'variants'/'halo-vertex'
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(V26)); sys.path.insert(0, str(HALO)); sys.path.insert(0, str(ROOT/'src'/'wayfarer'))
import spec  # noqa: E402
import ledger as L  # noqa: E402
import ledger2 as L2  # noqa: E402
import compact as CP  # noqa: E402
import protect as PR  # noqa: E402
import fixpath  # noqa: E402,F401  (corrected braking path)
import fuel as FU  # noqa: E402

C = L.C; YR = L.YR; DAY = L.DAY
VE_GRID = tuple(round(0.060+0.002*i, 3) for i in range(15))          # 0.060 ... 0.088 c
F_FWD_MIN = CP.F_FWD/100                                               # SR-26F level of the 2.6 minimum set (2.4e-4)


def setup():
    s = spec.load(ROOT)[0]; S = L.shared(s)
    vbc = json.loads((HALO/'vbc.json').read_text()); lk = L2.leakage(json.loads((HALO/'leak.json').read_text()))
    noz = [z for z in L2.nozzles(json.loads((HALO/'trace.json').read_text())) if z['z0'] >= 1.5 and z['BR'] >= 6.0]
    Sx = dict(S, phi_lim=1e23, phi_ship=S['phi_ship']*math.exp(2))     # 2.6 stretch levers
    return s, S, Sx, vbc, lk, noz


def nozzle_set(noz, kappa_req=None, eta_disp=1.0):
    """Traced options, or the best traced option (BR 16, z0 2) with its axial cosine raised to a requirement level. The velocity spread
    enters as kappa_eff = kappa sqrt(eta_dispersion), so eta_noz = kappa^2 eta_dispersion inside the 2.6 ledger."""
    base = noz if kappa_req is None else [dict(max(noz, key=lambda z: z['kappa']), kappa=kappa_req)]
    return [dict(z, kappa=z['kappa']*math.sqrt(eta_disp), kappa_geom=z['kappa']) for z in base]


_DUST = {}


def dust_mass(ext, case='NOMINAL'):
    """C dust protection (t) for a spine of length ext: the stern annulus bumper has ext - 50 m of stand-off (2.6 rule: 150 m at 200 m)."""
    key = (ext, case)
    if key not in _DUST:
        segs, _ = PR.mission(466.85*DAY, 0.072*C, None)
        old = PR.S_AVAIL['stern']['C_EXT']; PR.S_AVAIL['stern']['C_EXT'] = max(ext-50.0, 0.0)
        try:
            _DUST[key] = PR.protection_design('C_EXT', segs, case)['total_t']
        finally:
            PR.S_AVAIL['stern']['C_EXT'] = old
    return _DUST[key]


def solve(Sx, s, d, nozs, ext, ve_grid=VE_GRID, trip_yr=0.6, ntb=4, dust_case='NOMINAL'):
    """Every (ve, burn time, nozzle) closure; returns the lightest heat-passing one, the lightest overall and the per-ve curve."""
    g = lambda z0: CP.geometry('C', z0, ext=ext)
    dust_t = dust_mass(ext, dust_case)
    Tb0 = Sx['Tb0_s']; Tmax = Tb0+2*trip_yr*YR
    q = Sx['q_max']/1e6*(1+1e-9); rows = []
    tbs = [Tb0*(Tmax/Tb0)**(i/(ntb-1)) for i in range(ntb)] if trip_yr > 0 else [Tb0]
    for Tb in tbs:
        for vc in ve_grid:
            for nz in nozs:
                r = CP.close(Sx, s, d, nz, vc*C, Tb, g(nz['z0']), dust_t)
                if r and r.get('closes'):
                    r['heat_ok'] = r['iso_coil_MW_m2'] <= q and r['iso_plate_MW_m2'] <= q
                    r['nozzle'] = dict(BR=nz['BR'], z0=nz['z0'], kappa_eff=nz['kappa'], kappa_geom=nz.get('kappa_geom'))
                    rows.append(r)
    if not rows:
        return dict(closes=False)
    ok = [x for x in rows if x['heat_ok']]
    curve = {}
    for x in ok:
        k = round(x['ve_c'], 3)
        if k not in curve or x['departure_t'] < curve[k]['departure_t']:
            curve[k] = x
    pick = lambda x: dict((k, x[k]) for k in ('ve_c', 'Tb_d', 'trip_extra_yr', 'departure_t', 'end_t', 'propellant_t', 'fuel_t', 'he3_t',
                                               'fuel_share', 'fusion_TW', 'jet_TW', 'thrust_MN', 'system_t', 'radiator_t_engine',
                                               'iso_coil_MW_m2', 'iso_plate_MW_m2', 'useful_share', 'heat_ok', 'nozzle', 'engine_t'))
    best = min(ok, key=lambda x: x['departure_t']) if ok else None
    he3min = min(ok, key=lambda x: x['he3_t']) if ok else None
    return dict(closes=True, heat_ok=bool(ok), dust_t=dust_t, best=pick(best) if best else None, he3_min=pick(he3min) if he3min else None,
                lightest_any=pick(min(rows, key=lambda x: x['departure_t'])),
                curve=[pick(curve[k]) for k in sorted(curve)])


def design(vbc, Sx, lk, iso=0.03, fwd=F_FWD_MIN, b=0.95, r=1.0):
    d = CP.design('vbc', vbc, Sx, r=r, b=b, channel=0.95, Je_factor=3.0, f_fwd=fwd, iso_scale=iso, lk=lk)
    if fwd < CP.F_FWD/10:
        d['speculative'] = d['speculative']+['SR-26F forward-stream rejection']
    return d


def short(x):
    if not x:
        return 'none'
    return (f"ve {x['ve_c']:.3f} c, Tb {x['Tb_d']:.0f} d (+{x['trip_extra_yr']:.2f} yr), dep {x['departure_t']:.0f} t, end {x['end_t']:.0f} t, "
            f"prop {x['propellant_t']:.0f} t, He-3 {x['he3_t']:.0f} t, fusion {x['fusion_TW']:.1f} TW, sys {x['system_t']:.0f} t, "
            f"coil {x['iso_coil_MW_m2']:.1f} plate {x['iso_plate_MW_m2']:.2f} MW/m2, kappa_eff {x['nozzle']['kappa_eff']:.3f}")


def run():
    s, S, Sx, vbc, lk, noz = setup()
    disp = {m: {b: FU.dispersion(FU.exhaust_species(b, 1.0, m)) for b in (0.8, 0.95, 0.99)} for m in ('common', 'charge', 'thermal')}
    out = dict(meta=dict(title='Vertex 2.7 mission ledger on candidate C (research, not canon)', ve_grid=VE_GRID, dispersion=disp,
                         dep_canon_t=S['dep_upper']/1e3, research_t=7000.0, he3_canon_t=S['he3_canon_kg']/1e3,
                         core_t=S['core_kg']/1e3, f_tank=S['f_tank'], dv_c=S['dv']/C, burns=S['burns']), cases={})
    def case(name, iso=0.03, fwd=F_FWD_MIN, b=0.95, r=1.0, kappa=None, mode='common', ext=200.0, trip=0.6, dust='NOMINAL', grid=VE_GRID):
        d = design(vbc, Sx, lk, iso=iso, fwd=fwd, b=b, r=r)
        nz = nozzle_set(noz, kappa, disp[mode][b] if b in disp[mode] else FU.dispersion(FU.exhaust_species(b, 1.0, mode)))
        res = solve(Sx, s, d, nz, ext, grid, trip, dust_case=dust)
        res['inputs'] = dict(iso=iso, fwd=fwd, b=b, r=r, kappa=kappa or 'traced', spread=mode, ext=ext, trip_yr=trip, dust=dust,
                             speculative=d['speculative'], iso_share=d['c']['f_ph']+d['c']['f_n'])
        out['cases'][name] = res
        print(f"{name:34s} {short(res.get('best'))}", flush=True)
        return res
    # 1. the 2.6 reference, then the velocity-spread correction, then the levers one at a time and together
    case('ref_2.6_common')
    case('spread_charge', mode='charge')
    case('spread_thermal', mode='thermal')
    for mode in ('common', 'thermal'):
        case(f'b099_{mode}', b=0.99, mode=mode)
        case(f'kappa095_{mode}', kappa=0.95, mode=mode)
        case(f'kappa097_{mode}', kappa=0.97, mode=mode)
        case(f'all_levers_{mode}', b=0.99, kappa=0.97, mode=mode)
    # 2. trip duration (extra years over today's 6.0) at the 2.7 operating point (thermal spread, traced nozzle) and at all levers
    for trip in (0.0, 0.3, 1.0, 2.0):
        case(f'trip_{trip:g}_thermal', mode='thermal', trip=trip)
        case(f'trip_{trip:g}_all_levers', b=0.99, kappa=0.97, mode='thermal', trip=trip)
    # 3. feed ratio (ledger scaling: photons x (1+4r)(1+2r)/(15r), neutrons x 1/r)
    for r in (0.5, 0.7, 1.5, 2.0):
        case(f'feed_r{r:g}_thermal', r=r, mode='thermal')
    # 4. spine length against the isotropic share and the forward stream (heat-flux gates and dust both follow the spine)
    out['spine'] = []
    for ext in (25.0, 50.0, 75.0, 100.0, 150.0, 200.0):
        for iso in (0.1, 0.05, 0.03, 0.02, 0.01, 0.005):
            for fwd in (F_FWD_MIN, F_FWD_MIN/10):
                d = design(vbc, Sx, lk, iso=iso, fwd=fwd, b=0.95)
                res = solve(Sx, s, d, nozzle_set(noz, None, disp['thermal'][0.95]), ext, (0.064, 0.068, 0.070, 0.072, 0.074), 0.6)
                bx = res.get('best')
                out['spine'].append(dict(ext=ext, iso=iso, fwd=fwd, dust_t=dust_mass(ext), heat_ok=res.get('heat_ok', False),
                                         departure_t=bx['departure_t'] if bx else None, coil=bx['iso_coil_MW_m2'] if bx else None,
                                         plate=bx['iso_plate_MW_m2'] if bx else None, he3_t=bx['he3_t'] if bx else None))
                print(f"spine {ext:5.0f} iso x{iso:<6g} fwd {fwd:.1e} dust {dust_mass(ext):7.0f} t: "
                      + (f"dep {bx['departure_t']:.0f} t coil {bx['iso_coil_MW_m2']:.1f} plate {bx['iso_plate_MW_m2']:.2f}" if bx else 'no heat-passing closure'), flush=True)
    # 5. the 4.6 kt gap: the lightest configuration on every lever, and what it still misses
    for name, kw in (('gap_all_levers_thermal', dict(b=0.99, kappa=0.97, mode='thermal', iso=0.01, fwd=F_FWD_MIN/10, trip=1.0)),
                     ('gap_all_levers_charge', dict(b=0.99, kappa=0.97, mode='charge', iso=0.01, fwd=F_FWD_MIN/10, trip=1.0)),
                     ('gap_ideal_nozzle', dict(b=0.99, kappa=1.0, mode='charge', iso=0.01, fwd=F_FWD_MIN/10, trip=1.0))):
        case(name, **kw)
    # dust cases on the 2.7 operating point
    for dc in ('LOW', 'HIGH', 'NOMINAL_HILAT'):
        case(f'dust_{dc}_thermal', mode='thermal', dust=dc)
    # end mass the canon envelope allows at each exhaust speed, against the ship core and the tankage rule
    out['envelope'] = []
    for vc in VE_GRID:
        X = math.exp(S['burns']*S['dv']/(vc*C))-1
        m_end = S['dep_upper']/(1+X)
        out['envelope'].append(dict(ve_c=vc, mass_ratio=1+X, end_allowed_t=m_end/1e3, system_allowed_t=(m_end-S['core_kg']-S['f_tank']*X*m_end)/1e3))
    return out


if __name__ == '__main__':
    o = run()
    (HERE/'mission.json').write_text(json.dumps(o, indent=1, default=str)+'\n')
    for e in o['envelope']:
        print(f"envelope ve {e['ve_c']:.3f}: mass ratio {e['mass_ratio']:.3f}, end <= {e['end_allowed_t']:.0f} t, propulsion system <= {e['system_allowed_t']:.0f} t")
