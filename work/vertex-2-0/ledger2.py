"""Vertex 2.2 / 2.3: the Halo Vertex closure rerun with every correction the owner asked for (research, not canon).

  python3 work/vertex-2-0/ledger2.py      writes work/vertex-2-0/ledger2.json (needs trace.json, leak.json and vbc.json; several minutes)

Corrections against ledger.py (2.0):
1. Driver plant: 1 kg per kW of electrical driver power (LITERATURE space power conditioning and pulsed power, 0.5-3 kg/kW bracket);
   2.0 used 0.5 kg/kW and its report text wrongly said 0.5 kg per W. In chain mode the steady drive is only pellet injection, metrology
   and wave phasing: a = 1e-6 of fusion power (PROTOTYPE, about 5 MW per engine; 2.0 kept the 1.7 ignition driver running, 5e-6).
2. Fuel: feed ratio r = nHe3/nD, burnup b, no recovery from the exhaust. Tank specific energy e = b min(1, r) Q / (m_D + r m_He3);
   pure-fuel exhaust needs ve^2 / 2 <= eta e. He-3 is the He-3 actually fed. Photon share scales with (1+4r)(1+2r)/(15 r) at fixed Te
   (bremsstrahlung n_e sum n Z^2 against n_D n_He), D-D and secondary D-T neutrons with 1/r. 2.0 mixed a 1:1 mass share with 1:3 neutrons.
3. Source: the self-consistent VBC burn (vbc.py, radiative electrons, 90 % of the products' electron-bound energy channelled to ions):
   photons 0.121 and neutrons 0.0234 at r = 1, Ti 200 keV. 2.0 used the 1.6B 'best' row (photons 0.083), whose electrons do not balance.
4. Nozzle: one ring with its burn z0 R aft; the field B0 R and z0 are chosen from the traced table (trace.py, D and He-3 exhaust ions);
   thrust efficiency is the squared mean axial cosine of all exhaust (forward escapes count negative) times cos^2 of the inward cant;
   ring strikes are the pooled Monte Carlo 95 % upper limit (leak.py), plus the geometric share of the shadow shields.
   2.0 sized the field by pressure alone (7.5 mT, 17-48 % capture).
5. VBC in chain mode: the pulse rate is set so the pulse energy inside R/2 equals the capture field's energy there.
6. Four rings: compression booms braced into one frame (not tethers), ring-ring repulsion carried by tension ties, neighbour shadow strips,
   ship shadow shield sized for a quarter of the crew limit per burn, forward stream clear of booms and ship (halo.py).
7. Trip: up to 0.6 yr longer than today (owner Q1: about 6.6 years accepted as a research variant; canon stays 6.0 years).
"""
import json
import math
import sys
from functools import lru_cache
from multiprocessing import Pool
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT/'src'/'wayfarer'))
import spec  # noqa: E402
import vertex_source as vs  # noqa: E402
import ledger as L  # noqa: E402
import halo  # noqa: E402

C = L.C; MU0 = L.MU0; YR = L.YR; DAY = L.DAY
MEV = 1.602176634e-13; AMU = 1.66053906660e-27
M_D = 2.014102*AMU; M_HE = 3.016029*AMU; Q_DHE = 18.353*MEV
CAP_KG = 5.0e7           # stop a fixed point above 50 kt: far outside any envelope


def e_tank(r, b):
    return b*min(1.0, r)*Q_DHE/(M_D+r*M_HE)


def he3_mass_share(r):
    return r*M_HE/(M_D+r*M_HE)


def source(r, vbc, channel=0.9):
    row = min(vbc['channel'], key=lambda x: abs(x['channel']-channel))
    g = (1+4*r)*(1+2*r)/(15*r)
    return dict(f_ph=row['photon_share']*g, f_n=row['neutron_share']/r, channel=row['channel'], photon_factor=g)


def nozzles(trace, R0=64.0):
    """Traced single-ring options: B0 R, burn position, thrust cosine kappa of the exhaust ions, forward and radial shares; protons too."""
    by = {}
    for row in trace['rows']:
        if not row['config'].startswith('single ring') or row['B0_T'] < 0.04:
            continue
        by.setdefault((row['B0_T'], row['z0_R']), {})[row['species']] = row
    out = []
    for (B0, z0), sp in sorted(by.items()):
        ex = [v for k, v in sp.items() if 'exhaust' in k]
        if len(ex) < 2 or z0 > 2.0:
            continue
        kappa = sum(v['aft_thrust_cos']-0.99*v['forward'] for v in ex)/len(ex)
        p = sp.get('p 14.7 MeV (D-3He product)', {})
        out.append(dict(BR=B0*R0, B0_at_64=B0, z0=z0, kappa=kappa, forward=max(v['forward'] for v in ex), radial=max(v['radial'] for v in ex),
                        ring=max(v['ring'] for v in sp.values()), proton_aft=p.get('aft'), proton_radial=p.get('radial')))
    return out


def leakage(leak):
    N = sum(c['n'] for c in leak['cases']); hits = sum(c['counts'].get('RING', 0) for c in leak['cases'])
    fwd = [x for c in leak['cases'] for x in (c['forward_cos_deciles'] or [])]
    fmin = min((c['forward_cos_min_abs'] for c in leak['cases'] if c['forward_cos_min_abs'] is not None), default=1.0)
    return dict(n=N, hits=hits, upper95=(3.0 if hits == 0 else hits+2*math.sqrt(hits))/N, per_case_upper95=max(c['ring_strike_upper95'] for c in leak['cases']),
                forward_cos=fwd+[-fmin])


@lru_cache(maxsize=None)
def _force_unit(R, a):
    return halo.forces(1.0, R, a, 240)['force_mag_N']               # scales with I^2


@lru_cache(maxsize=None)
def _cross(R, w, z0, a, Pn, Pph, n_per_J, Tb, phi_lim, lam, rho_sh, q_max):
    return halo.cross_irradiation(R, w, z0, a, Pn, Pph, n_per_J, Tb, phi_lim, lam, rho_sh, q_max, None)


def g4(x):
    return float(f'{x:.4g}')


def engine(S, s, d, nz, Pf, Tb, F, R, sep, a_cl, lk):
    """One Halo Vertex engine at fusion power Pf: ring, fin, armour, structure, booms, shields, driver, radiator heat."""
    c = d['c']; sh = L.shares(c); Pn = c['f_n']*Pf; Pph = c['f_ph']*Pf; z0 = nz['z0']
    plasma = (sh['jet']+sh['leak']+sh['plume'])*Pf
    B = nz['BR']/R; I = 2*R*B/MU0; ln = 2*math.pi*R
    u = B*B/(2*MU0); Epulse = u*4/3*math.pi*(R/2)**3; rate = plasma/Epulse
    Ac = I/(S['J_e']*d['Je_factor']); cond = S['rho_cond']*Ac*ln
    rb = math.sqrt(1+z0*z0)*R                                           # burn to ring distance
    fin = L.shield(S, Pn, Tb, rb, 0.0)
    a_c = math.sqrt(Ac/math.pi); Lind = MU0*R*(math.log(8*R/a_c)-1.75); EB = 0.5*Lind*I*I
    sig, rho, _ = S['materials']['cnt']
    w = max(math.sqrt(Ac), 0.03)+0.04; frac = w/(2*R)*R/rb               # the ring's share of the burn's sky (edge-on, at distance rb)
    fin_kg = S['rho_sh']*fin['t_m']*w*ln; cold = frac*Pn*S['dep_n']*math.exp(-fin['t_m']/S['lam'])
    struct = S['k_virial']*rho*EB/sig; armour = 19300.0*0.005*w*ln
    fo = _force_unit(g4(R), g4(a_cl))*I*I
    ties = 3.0*fo*(math.sqrt(2)*a_cl)*1600.0/5.0e9                      # CNT tension ties to the neighbours, safety 3
    bm = halo.boom(F, sep, a_cl, d['stations'])
    xi = _cross(g4(R), g4(w), z0, g4(a_cl), g4(Pn), g4(Pph), S['n_per_J'], Tb, S['phi_lim'], S['lam'], S['rho_sh'], S['q_max'])
    Ls = sep+z0*R; phi_ship = Pn*S['n_per_J']*Tb/(4*math.pi*(Ls+S['ship_aft_m'])**2)
    t_ship = S['lam']*math.log(max(phi_ship/(S['phi_ship']/4), 1.0)); s_d = xi['strip_distance_m']
    A_ship = S['A_front']*(s_d/Ls)**2+2*0.5*2*math.pi*25.0*(s_d/Ls); ship_sh = S['rho_sh']*t_ship*A_ship
    om_ship = S['A_front']/(4*math.pi*Ls**2)
    shield_sky = om_ship+xi['sky_fraction_all']                         # charged particles aimed at the shields count as leakage
    leak = lk['upper95']+shield_sky
    fs = halo.forward_stream(a_cl, sep, d['cant'], lk['forward_cos'], R)
    drv = c['a']/c['eta_d']*Pf*d['driver_kg_W']
    light = d['light_J']/d['pulse_J_kg']
    heat = [('isotropic radiation on ring armour', L.iso_deposit(c, frac)*Pf, S['T_armour']), ('charged leakage', leak*plasma, S['T_armour']),
            ('isotropic radiation on the shadow shields and strips', L.iso_deposit(c, shield_sky)*Pf, S['T_armour']),
            ('direct conversion loss', sh['conv_loss']*Pf, S['T_loss']), ('driver loss', sh['drv_loss']*Pf, S['T_loss']),
            ('neutrons through the fin into the coils', cold, S['T_cold'])]
    mass = dict(ring_conductor=cond, ring_structure=struct, ring_armour=armour, ring_neutron_fin=fin_kg, boom=bm['boom_kg'], boom_bracing=bm['bracing_kg'],
                ring_ties=ties, neighbour_strips=xi['strip_kg_per_burn'], ship_shadow_shield=ship_sh, driver=drv, lighting_driver=light,
                injector_and_feed=0.02*(cond+struct), burn_station=S['station_kg'])
    irr = (c['f_ph']+c['f_n'])*Pf/(4*math.pi*rb*rb)
    st = halo.stowage(R, Ac, w, bm['boom_kg'], struct_kg=struct)
    detail = dict(R_m=R, B0_T=B, I_MA=I/1e6, BR_Tm=nz['BR'], z0_R=z0, kappa=nz['kappa'], forward=nz['forward'], field_J=EB, pulse_J=Epulse, rate_Hz=rate,
                  burn_to_ring_m=rb, sky=frac, conductor_m2=Ac, face_m=w, fin_t_m=fin['t_m'], fluence_n_m2=fin['fluence'], separation_m=sep,
                  cluster_radius_m=a_cl, ring_force_N=fo, boom=bm, cross=dict((k, v) for k, v in xi.items() if k != 'neighbour_rows'),
                  ship_shield_t_m=t_ship, leak=leak, leak_mc=lk['upper95'], shield_sky=shield_sky, forward_stream=fs, stowage=st)
    return dict(mass=mass, heat=heat, irradiance=irr, detail=detail)


def close(S, s, d, nz, lk, ve, Tb, Rk, sep, ka, iters=300):
    c = dict(d['c'], eta_noz=(nz['kappa']*math.cos(math.radians(d['cant'])))**2); dd = dict(d, c=c)
    sh = L.shares(c); eta = sh['jet']; et = e_tank(d['r'], d['b'])
    if ve**2/2 > eta*et:
        return None
    Rb = math.exp(S['dv']/ve); X = Rb**S['burns']-1; m_end = S['canon']['end_kg']
    for _ in range(iters):
        prop = X*m_end; Pjet = prop*ve*ve/(2*Tb); Pf = Pjet/eta; Pe = Pf/S['engines']; F = 2*Pjet/ve
        R = Rk*L.r_min(c, S, Pe)/math.sqrt(1+nz['z0']**2)
        e = engine(S, s, dd, nz, Pe, Tb, F/S['engines'], R, sep, ka*R, lk)
        rad_W = sum(W*vs.cost(s, T) for _, W, T in e['heat']); rad_kg = rad_W/S['rad_flux']*S['rad_kg_m2']
        eng = sum(e['mass'].values()); start = S['start_J']/S['start_J_kg']
        struct = 3*F*30.0*S['materials']['cnt'][1]/1.5e9*10
        sys_kg = S['engines']*(eng+rad_kg)+start+struct
        new = S['core_kg']+sys_kg+S['f_tank']*prop
        if new > CAP_KG:
            return dict(closes=False)
        if abs(new-m_end) < 1.0:
            m_end = new; break
        m_end = 0.5*(m_end+new)
    else:
        return dict(closes=False)
    prop = X*m_end; Pjet = prop*ve*ve/(2*Tb); Pf = Pjet/eta
    fuel = Pf*Tb/et; he3 = fuel*he3_mass_share(d['r']); energy = 1.0-(sh['jet']+sh['leak']+sh['plume']+sh['iso']+sh['conv_loss']+sh['drv_loss'])
    return dict(closes=True, ve_c=ve/C, Tb_d=Tb/DAY, trip_extra_yr=(Tb-S['Tb0_s'])/2/YR, end_t=m_end/1e3, departure_t=(m_end+prop)/1e3,
                propellant_t=prop/1e3, fuel_t=fuel/1e3, he3_t=he3/1e3, deuterium_t=(fuel-he3)/1e3, inert_t=(prop-fuel)/1e3, fuel_share=fuel/prop,
                jet_TW=Pjet/1e12, fusion_TW=Pf/1e12, thrust_MN=2*Pjet/ve/1e6, system_t=sys_kg/1e3, engine_t={k: v/1e3 for k, v in e['mass'].items()},
                radiator_t_engine=rad_kg/1e3, radiator_load_engine_GW=rad_W/1e9, heat_engine_GW={n: W/1e9 for n, W, _ in e['heat']},
                startup_t=start/1e3, structure_t=struct/1e3, irradiance_MW_m2=e['irradiance']/1e6, detail=e['detail'], useful_share=eta,
                e_tank_J_kg=et, ve_max_c=math.sqrt(2*eta*et)/C, Rk=Rk, sep_m=sep, ka=ka, energy_error=energy,
                impulse_error=(2*Pjet/ve)*Tb/(prop*ve)-1)


def design(vbc, r=1.0, b=0.8, channel=0.9, a=1e-6, driver_kg_W=1.0e-3, Je_factor=1.0, cant=9.0, stations=8):
    src = source(r, vbc, channel)
    c = dict(L.candidates()['E'], f_ph=src['f_ph'], f_n=src['f_n'], a=a, rings=1)
    return dict(c=c, r=r, b=b, channel=channel, src=src, driver_kg_W=driver_kg_W, Je_factor=Je_factor, cant=cant, stations=stations,
                light_J=1.0e6, pulse_J_kg=300.0, a=a)


GRID = dict(ve=(0.05, 0.055, 0.06, 0.064, 0.068, 0.072, 0.075), Tb=4, Rk=(1.0, 1.5), sep=(1000.0, 2000.0, 3000.0), ka=(5.0, 8.0, 12.0))


def best(job):
    """Lightest closed mission of one design over exhaust speed, burn time, ring radius, separation, cluster radius and nozzle option."""
    name, d, noz, lk, trip_yr = job[:5]
    s = spec.load(ROOT)[0]; S = L.shared(s); S.update(job[5] if len(job) > 5 else {})
    Tb0 = S['Tb0_s']; Tmax = Tb0+2*trip_yr*YR; n = GRID['Tb']
    rows = []
    for i in range(n):
        Tb = Tb0*(Tmax/Tb0)**(i/(n-1))
        for vc in GRID['ve']:
            for nz in noz:
                for Rk in GRID['Rk']:
                    for sep in GRID['sep']:
                        for ka in GRID['ka']:
                            r = close(S, s, d, nz, lk, vc*C, Tb, Rk, sep, ka)
                            if r and r.get('closes'):
                                rows.append(r)
    if not rows:
        return name, dict(closes=False)
    ok = [x for x in rows if x['detail']['forward_stream']['ship_clear'] and x['detail']['forward_stream']['boom_clear_far']]
    return name, min(ok or rows, key=lambda x: x['departure_t'])


def gates(r, S, d):
    if not r.get('closes'):
        return dict(G1_closes=False)
    det = r['detail']
    return dict(G1_closes=True, G2_departure=r['departure_t']*1e3 <= S['dep_upper'], G3_propellant=r['propellant_t']*1e3 <= S['prop_upper'],
                G4_trip_time=r['trip_extra_yr'] <= 0.6+1e-9, G5_heat_flux=r['irradiance_MW_m2']*1e6 <= S['q_max']*(1+1e-9),
                G7_conservation=abs(r['energy_error']) < 1e-9 and abs(r['impulse_error']) < 1e-9 and r['fuel_share'] <= 1.0,
                G8_speculative_count=len(d['c']['speculative']) <= 1, G10_he3_supply=r['he3_t']*1e3 <= S['he3_canon_kg']*(1+1e-9),
                G11_leakage=det['leak'] <= 1e-4, G12_forward_stream_clear=det['forward_stream']['ship_clear'] and det['forward_stream']['boom_clear_far'])


def run(procs=4):
    s = spec.load(ROOT)[0]; S = L.shared(s)
    vbc = json.loads((HERE/'vbc.json').read_text()); lk = leakage(json.loads((HERE/'leak.json').read_text()))
    noz = nozzles(json.loads((HERE/'trace.json').read_text()))
    use = [z for z in noz if z['z0'] >= 1.5 and z['BR'] >= 6.0]
    out = dict(leakage=dict((k, v) for k, v in lk.items() if k != 'forward_cos'), nozzles=noz, fuel=[], cases={}, sensitivity={})
    for r in (0.5, 1.0, 1.5, 2.0, 3.0):
        for b in (0.5, 0.8):
            src = source(r, vbc)
            out['fuel'].append(dict(r=r, b=b, e_tank_J_kg=e_tank(r, b), he3_mass_share=he3_mass_share(r), f_ph=src['f_ph'], f_n=src['f_n'],
                                    ve_max_c=math.sqrt(2*L.shares(dict(L.candidates()['E'], f_ph=src['f_ph'], f_n=src['f_n'], a=1e-6, eta_noz=0.84))['jet']*e_tank(r, b))/C))
    jobs = []
    for r in (0.5, 1.0, 3.0):
        for b in (0.5, 0.8):
            jobs.append((f'r{r:g}_b{b:g}', design(vbc, r=r, b=b), use, lk, 0.6))
    sens = dict(driver_05=dict(driver_kg_W=0.5e-3), driver_3=dict(driver_kg_W=3e-3), a_5e6=dict(a=5e-6), Je_x2=dict(Je_factor=2.0),
                channel_066=dict(channel=0.66), channel_095=dict(channel=0.95), cant_15=dict(cant=15.0))
    for k, kw in sens.items():
        jobs.append((f'sens_{k}', design(vbc, r=1.0, b=0.8, **kw), use, lk, 0.6))
    jobs.append(('r1_b0.8_trip0.3', design(vbc, r=1.0, b=0.8), use, lk, 0.3))
    with Pool(procs) as pool:
        res = dict(pool.map(best, jobs))
    for name, d, *_ in jobs:
        x = res[name]; g = gates(x, S, d)
        row = dict(result=x, gates=g, design=dict(r=d['r'], b=d['b'], channel=d['channel'], a=d['a'], driver_kg_W=d['driver_kg_W'], Je_factor=d['Je_factor'],
                                                   cant=d['cant'], src=d['src']))
        (out['sensitivity'] if name.startswith('sens_') or 'trip' in name else out['cases'])[name] = row
        print(f"{name:18s} " + (f"dep {x['departure_t']:.0f} t, sys {x['system_t']:.0f} t, He-3 {x['he3_t']:.0f} t, ve {x['ve_c']:.3f} c, fusion {x['fusion_TW']:.1f} TW, "
                                f"trip +{x['trip_extra_yr']:.2f} yr, R {x['detail']['R_m']:.0f} m, B0R {x['detail']['BR_Tm']:.1f}, I {x['detail']['I_MA']:.1f} MA, "
                                f"sep {x['sep_m']:.0f}, a {x['detail']['cluster_radius_m']:.0f}, leak {x['detail']['leak']:.1e}" if x.get('closes') else 'no closure')
              + '  fails: ' + ','.join(k for k, v in g.items() if not v), flush=True)
    return out


if __name__ == '__main__':
    o = run()
    (HERE/'ledger2.json').write_text(json.dumps(o, indent=1, default=str)+'\n')
