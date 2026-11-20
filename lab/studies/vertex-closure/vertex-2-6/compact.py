"""Vertex 2.6: compact four-engine candidates on the same mission ledger as Vertex 2.2-2.5, with dust protection and the protected
flight envelope as new gates.

    python3 lab/studies/vertex-closure/vertex-2-6/compact.py        writes lab/studies/vertex-closure/vertex-2-6/compact.json (needs protect.json; about 1-2 min)

Research, not canon. Reuses the archived Halo Vertex ledger (lab/variants/halo-vertex: ledger.py shared assumptions and energy
bookkeeping, ledger2.py fuel and VBC source model, traced ring-nozzle options) so every candidate is closed against the same mission,
fuel, materials, radiator and envelope numbers. What changes is the engine: four engines at the ship's stern (A+ cluster, radius 24 m)
instead of four rings 2 km aft, so the burns sit tens of metres from the coils, from each other and from the ship.

Candidates (one engine model, different inputs):
  A  Optimized Compact Vertex: A+ geometry, established pulsed D-3He source (ledger 2.0 candidate C source, gain 50), no VBC.
  B  Compact Burn-Channeling Vertex: A+ geometry with the VBC chain-ignited source (ledger 2.2 source model).
  C  Protected Adaptive Vertex: B's source, the engine group on a telescoping spine (extended 200 m aft only for burns) behind a
     stern annulus carried on the spine, so the ship sits far from the burns and the annulus has its bumper stand-off.
  D  Rosette Vertex: B's source split into seven sub-nozzles per engine (different scaling: coil standoff ~1/sqrt(n), magnet ~sqrt(n)).
Each is closed by the same fixed point (end mass -> propellant -> power -> engine, shields, radiators, protection -> end mass) and
then checked against gates G1-G16. Where the heat-flux gates fail, the script finds the smallest single speculative improvement
that would pass them (isotropic radiation share, or the wall heat-flux limit) and closes the mission again with it.
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
HALO = ROOT/'lab'/'variants'/'halo-vertex'
sys.path.insert(0, str(HALO))
sys.path.insert(0, str(ROOT/'src'/'wayfarer'))
import spec  # noqa: E402
import vertex_source as vs  # noqa: E402
import ledger as L  # noqa: E402
import ledger2 as L2  # noqa: E402
import halo  # noqa: E402

C = L.C; MU0 = L.MU0; YR = L.YR; DAY = L.DAY
CLUSTER_A = 24.0             # A+ cluster radius (vertex_adaptive audit), m
ENGINE_LEN = 31.93           # A+ engine envelope length; the stern face is at the engines' forward end
R_COIL = 10.0                # A+ main coil radius inside the 11.44 m engine envelope (PROTOTYPE reading)
MECH_KG = 47.6e3             # A+ adaptive machinery per engine (carriage, rails, dynamos, petals; Vertex 1.8 EVIDENCE)
PLATE_KG_M2 = 20.0           # stern radiation plate: cooled W-faced C/C panel (PROTOTYPE)
SHIP_R = 45.0                # the ship's silhouette behind the stern plate
F_FWD = 0.024                # forward-escaping charged share of the exhaust, traced single ring (Vertex 2.2 trace, lowest case)


def geometry(name, z0, n_sub=1, ext=0.0):
    """Coil radius, burn positions and the distances that set heat flux. Burns sit z0 R aft of each coil plane."""
    R = R_COIL if n_sub == 1 else R_COIL/3.0
    rb = math.sqrt(1+z0*z0)*R
    # irradiance factor at the worst coil point: sum over burns of 1/d^2 (own burn at rb, the other three engines' burns at the cluster
    # spacing, the six rosette neighbours at 2.2 R in the same plane)
    d_eng = [math.hypot(CLUSTER_A*math.sqrt(2), z0*R), math.hypot(CLUSTER_A*math.sqrt(2), z0*R), math.hypot(2*CLUSTER_A, z0*R)]
    inv = 1/rb**2+sum(n_sub/d**2 for d in d_eng)
    if n_sub > 1:
        inv += sum(1/math.hypot(2.2*R, z0*R)**2 for _ in range(6))
    Ls = ENGINE_LEN+z0*R+ext                       # burn plane to the stern face
    om = 2*math.pi*(1-Ls/math.hypot(Ls, SHIP_R))    # solid angle of the ship's r 45 m silhouette from one burn
    return dict(name=name, R=R, z0=z0, rb=rb, n_sub=n_sub, ext=ext, inv_d2=inv, Ls=Ls, ship_sky=om/(4*math.pi))


def engine(S, s, d, nz, Pe, Tb, F_e, g, dust_t):
    """One compact engine at fusion power Pe (n_sub sub-nozzles share it)."""
    c = d['c']; sh = L.shares(c); n = g['n_sub']; Ps = Pe/n
    Pn = c['f_n']*Ps; Pph = c['f_ph']*Ps
    plasma = (sh['jet']+sh['leak']+sh['plume'])*Pe
    R = g['R']; B = nz['BR']/R; I = 2*R*B/MU0; ln = 2*math.pi*R
    Ac = I/(S['J_e']*d['Je_factor']); cond = n*S['rho_cond']*Ac*ln
    rb = g['rb']
    w = max(math.sqrt(Ac), 0.03)+0.04; frac = w/(2*R)*R/rb
    fin = L.shield(S, Pn*(1+rb**2*(g['inv_d2']-1/rb**2)), Tb, rb, 0.0)     # own burn plus the neighbours, as one fluence at rb
    fin_kg = n*S['rho_sh']*fin['t_m']*w*ln; cold = n*frac*Pn*S['dep_n']*math.exp(-fin['t_m']/S['lam'])
    a_c = math.sqrt(Ac/math.pi); Lind = MU0*R*(math.log(8*R/a_c)-1.75); EB = 0.5*Lind*I*I
    sig, rho, _ = S['materials']['cnt']
    struct = n*S['k_virial']*rho*EB/sig; armour = n*19300.0*0.005*w*ln
    # the ship: neutron shadow shield for the habitat (ledger rule) and the stern plate that takes this burn's share of the ship's sky
    Ls = g['Ls']; phi_h = Pn*n*S['n_per_J']*Tb/(4*math.pi*(Ls+S['ship_aft_m'])**2)
    t_ship = S['lam']*math.log(max(phi_h/(S['phi_ship']/4), 1.0))
    s_d = min(Ls, max(rb, math.sqrt((c['f_ph']+c['f_n'])*4*Pe/(4*math.pi*S['q_max']))))   # as close to the burn as the heat flux allows
    A_ship = S['A_front']*(s_d/(Ls+S['ship_aft_m']))**2
    ship_sh = S['rho_sh']*t_ship*A_ship
    plate = PLATE_KG_M2*math.pi*SHIP_R**2/4                                   # a quarter of the stern plate per engine
    fwd = d['f_fwd']*plasma
    drv = c['a']/c['eta_d']*Pe*d['driver_kg_W']
    light = d.get('light_J', 0.0)/d.get('pulse_J_kg', 300.0)
    spine = 0.0
    if g['ext'] > 0:
        spine = halo.boom(4*F_e, g['ext'], 0.0, 6, r_truss=3.0)['boom_kg']/4      # one central spine in compression, shared
    heat = [('isotropic radiation on coil armour', n*L.iso_deposit(c, frac)*Ps, S['T_armour']), ('charged leakage on coils', d['leak_mc']*plasma, S['T_armour']),
            ('isotropic radiation on the stern plate', L.iso_deposit(c, g['ship_sky'])*Pe, S['T_armour']),
            ('forward charged stream on the stern plate', fwd, S['T_armour']),
            ('direct conversion loss', sh['conv_loss']*Pe, S['T_loss']), ('driver loss', sh['drv_loss']*Pe, S['T_loss']),
            ('neutrons through the fin into the coils', cold, S['T_cold'])]
    mass = dict(coil_conductor=cond, coil_structure=struct, coil_armour=armour, coil_neutron_fin=fin_kg, ship_shadow_shield=ship_sh,
                stern_plate=plate, driver=drv, lighting_driver=light, injector_and_feed=0.02*(cond+struct), burn_station=S['station_kg'],
                adaptive_machinery=MECH_KG, spine=spine, dust_protection=dust_t*1e3/4)
    iso_coil = (c['f_ph']+c['f_n'])*Ps/(4*math.pi)*g['inv_d2']
    iso_plate = 4*(c['f_ph']+c['f_n'])*Pe/(4*math.pi*Ls**2)                    # four burns at about the same distance
    detail = dict(R_m=R, n_sub=n, B0_T=B, I_MA=I/1e6, BR_Tm=nz['BR'], z0_R=g['z0'], burn_to_coil_m=rb, coil_sky=frac, fin_t_m=fin['t_m'],
                  fluence_n_m2=fin['fluence'], Ls_m=Ls, ship_shield_at_m=s_d, ship_sky=g['ship_sky'], ship_shield_t_m=t_ship, ext_m=g['ext'],
                  forward_stream_W=fwd, iso_coil_W_m2=iso_coil, iso_plate_W_m2=iso_plate)
    return dict(mass=mass, heat=heat, detail=detail)


def close(S, s, d, nz, ve, Tb, g, dust_t, iters=300):
    c = dict(d['c'], eta_noz=nz['kappa']**2); dd = dict(d, c=c)
    sh = L.shares(c)
    if sh is None:
        return None
    eta = sh['jet']; et = L2.e_tank(d['r'], d['b'])
    if ve**2/2 > eta*et:
        return None
    Rb = math.exp(S['dv']/ve); X = Rb**S['burns']-1; m_end = S['canon']['end_kg']
    for _ in range(iters):
        prop = X*m_end; Pjet = prop*ve*ve/(2*Tb); Pf = Pjet/eta; Pe = Pf/4; F = 2*Pjet/ve
        e = engine(S, s, dd, nz, Pe, Tb, F/4, g, dust_t)
        rad_W = sum(W*vs.cost(s, T) for _, W, T in e['heat']); rad_kg = rad_W/S['rad_flux']*S['rad_kg_m2']
        eng = sum(e['mass'].values()); start = S['start_J']/S['start_J_kg']
        struct = 3*F*30.0*S['materials']['cnt'][1]/1.5e9*10
        sys_kg = 4*(eng+rad_kg)+start+struct
        new = S['core_kg']+sys_kg+S['f_tank']*prop
        if new > L2.CAP_KG:
            return dict(closes=False, reason='diverges above 50 kt')
        if abs(new-m_end) < 1.0:
            m_end = new; break
        m_end = 0.5*(m_end+new)
    else:
        return dict(closes=False, reason='no fixed point')
    prop = X*m_end; Pjet = prop*ve*ve/(2*Tb); Pf = Pjet/eta
    fuel = Pf*Tb/et; he3 = fuel*L2.he3_mass_share(d['r'])
    energy = 1.0-(sh['jet']+sh['leak']+sh['plume']+sh['iso']+sh['conv_loss']+sh['drv_loss'])
    return dict(closes=True, ve_c=ve/C, Tb_d=Tb/DAY, trip_extra_yr=(Tb-S['Tb0_s'])/2/YR, end_t=m_end/1e3, departure_t=(m_end+prop)/1e3,
                propellant_t=prop/1e3, fuel_t=fuel/1e3, he3_t=he3/1e3, jet_TW=Pjet/1e12, fusion_TW=Pf/1e12, thrust_MN=2*Pjet/ve/1e6,
                system_t=sys_kg/1e3, engine_t={k: v/1e3 for k, v in e['mass'].items()}, radiator_t_engine=rad_kg/1e3,
                radiator_load_engine_GW=rad_W/1e9, heat_engine_GW={k: W/1e9 for k, W, _ in e['heat']}, detail=e['detail'],
                useful_share=eta, fuel_share=fuel/prop, energy_error=energy, impulse_error=(2*Pjet/ve)*Tb/(prop*ve)-1,
                iso_coil_MW_m2=e['detail']['iso_coil_W_m2']/1e6, iso_plate_MW_m2=e['detail']['iso_plate_W_m2']/1e6)


VE = (0.05, 0.055, 0.06, 0.064, 0.068, 0.072)
NTB = 4


def best(S, s, d, noz, gfun, dust_t, trip_yr=0.6, prefer_flux=True):
    Tb0 = S['Tb0_s']; Tmax = Tb0+2*trip_yr*YR; rows = []
    for i in range(NTB):
        Tb = Tb0*(Tmax/Tb0)**(i/(NTB-1))
        for vc in VE:
            for nz in noz:
                g = gfun(nz['z0'])
                r = close(S, s, d, nz, vc*C, Tb, g, dust_t)
                if r and r.get('closes'):
                    r['nozzle'] = dict(BR=nz['BR'], z0=nz['z0'], kappa=nz['kappa'])
                    rows.append(r)
    if not rows:
        return dict(closes=False)
    return min(rows, key=lambda x: (max(x['iso_coil_MW_m2'], x['iso_plate_MW_m2']) > S['q_max']/1e6*(1+1e-9) if prefer_flux else 0,
                                    x['departure_t']))


def gates(r, S, d, cand):
    if not r.get('closes'):
        return dict(G1_closes=False)
    q = S['q_max']/1e6*(1+1e-9)
    return dict(G1_closes=True, G2_departure_4p6kt=r['departure_t'] <= S['dep_upper']/1e3, G2b_research_7kt=r['departure_t'] <= 7000.0,
                G3_propellant=r['propellant_t'] <= S['prop_upper']/1e3, G4_trip_time=r['trip_extra_yr'] <= 0.6+1e-9,
                G5_coil_heat_flux=r['iso_coil_MW_m2'] <= q, G5b_stern_heat_flux=r['iso_plate_MW_m2'] <= q,
                G7_conservation=abs(r['energy_error']) < 1e-9 and abs(r['impulse_error']) < 1e-9 and r['fuel_share'] <= 1.0,
                G8_speculative_count=len(d['speculative']) <= 1, G10_he3_supply=r['he3_t']*1e3 <= S['he3_canon_kg']*(1+1e-9),
                G13_dust_nominal=cand['dust']['NOMINAL'] < 1e9, G13b_dust_high=cand['dust']['HIGH'] < 1e3,
                G14_protected_geometry=cand['protected'], G15_compact_stowed=cand['compact'])


def design(kind, vbc, S, r=1.0, b=0.8, channel=0.9, Je_factor=1.0, f_fwd=F_FWD/10, iso_scale=1.0, driver_kg_W=1.0e-3, lk=None):
    if kind == 'established':
        c = dict(L.candidates()['C'])
        spec_ = []
    else:
        src = L2.source(r, vbc, channel)
        c = dict(L.candidates()['E'], f_ph=src['f_ph'], f_n=src['f_n'], a=1e-6)
        spec_ = ['VBC']
    c = dict(c, f_ph=c['f_ph']*iso_scale, f_n=c['f_n']*iso_scale)
    if iso_scale < 1.0:
        spec_ = spec_+['SR-26 isotropic suppression']
    return dict(c=c, r=r, b=b, channel=channel, Je_factor=Je_factor, f_fwd=f_fwd, driver_kg_W=driver_kg_W, speculative=spec_,
                leak_mc=(lk['upper95'] if lk else 3.3e-5), light_J=1.0e6 if kind != 'established' else 0.0, pulse_J_kg=300.0)


def run():
    s = spec.load(ROOT)[0]; S = L.shared(s)
    vbc = json.loads((HALO/'vbc.json').read_text()); lk = L2.leakage(json.loads((HALO/'leak.json').read_text()))
    noz = [z for z in L2.nozzles(json.loads((HALO/'trace.json').read_text())) if z['z0'] >= 1.5 and z['BR'] >= 6.0]
    P = json.loads((HERE/'protect.json').read_text())['missions']['vertex_467d']['design']
    dust = {a: {c: P[c][a]['total_t'] for c in P} for a in ('APLUS', 'C_EXT', 'HALO')}
    cands = {
        'A': dict(title='A. Optimized Compact Vertex (established source, no VBC)', kind='established', geo=lambda z0: geometry('A', z0),
                  dust=dust['APLUS'], protected=True, compact=True),
        'B': dict(title='B. Compact Burn-Channeling Vertex (VBC source in the A+ cluster)', kind='vbc', geo=lambda z0: geometry('B', z0),
                  dust=dust['APLUS'], protected=True, compact=True),
        'C': dict(title='C. Protected Adaptive Vertex (VBC, 200 m telescoping spine, stern annulus on the spine)', kind='vbc',
                  geo=lambda z0: geometry('C', z0, ext=200.0), dust=dust['C_EXT'], protected=True, compact=True),
        'D': dict(title='D. Rosette Vertex (VBC, seven sub-nozzles per engine)', kind='vbc', geo=lambda z0: geometry('D', z0, n_sub=7),
                  dust=dust['APLUS'], protected=True, compact=True),
    }
    levers = {'base': dict(), 'stretch': dict(b=0.95, channel=0.95, Je_factor=3.0)}
    out = dict(meta=dict(title='Vertex 2.6 compact candidates on the Vertex mission ledger (research, not canon)', q_max_MW_m2=S['q_max']/1e6,
                         dep_upper_t=S['dep_upper']/1e3, research_envelope_t=7000.0, f_fwd_nominal=F_FWD/10,
                         dust_t=dust, notes='dust protection masses from protect.json (vertex_467d path, NOMINAL); HALO shown for reference'),
               candidates={}, requirements={}, sensitivity={})
    for key, cd in cands.items():
        for lev, kw in levers.items():
            d = design(cd['kind'], vbc, S, lk=lk, **kw)
            Sx = dict(S, phi_lim=1e23, phi_ship=S['phi_ship']*math.exp(2)) if lev == 'stretch' else S
            r = best(Sx, s, d, noz, cd['geo'], cd['dust']['NOMINAL'])
            g = gates(r, Sx, d, cd)
            out['candidates'][f'{key}_{lev}'] = dict(title=cd['title'], levers=lev, result=r, gates=g, speculative=d['speculative'])
            print(f"{key}_{lev:8s} " + (f"dep {r['departure_t']:8.0f} t  sys {r['system_t']:7.0f} t  fusion {r['fusion_TW']:5.1f} TW  ve {r['ve_c']:.3f} c  "
                                        f"coil {r['iso_coil_MW_m2']:8.1f}  plate {r['iso_plate_MW_m2']:7.1f} MW/m2  rad/eng {r['radiator_t_engine']:7.0f} t"
                                        if r.get('closes') else 'no closure') + '  fails: ' + ','.join(k for k, v in g.items() if not v), flush=True)
    # requirement map: which combinations of (isotropic share reaching hardware, forward charged stream, wall heat-flux limit, driver
    # specific mass) pass the heat-flux gates and close the mission inside the envelopes. Each axis is one candidate speculative principle.
    def one(key, kind, iso=1.0, fwd=F_FWD/10, q=None, drv=1.0e-3, lev='base', gain=None):
        cd = cands[key]; kw = levers[lev]
        Sx = dict(S, phi_lim=1e23, phi_ship=S['phi_ship']*math.exp(2)) if lev == 'stretch' else dict(S)
        if q:
            Sx['q_max'] = q*1e6
        d = design(kind, vbc, Sx, lk=lk, iso_scale=iso, f_fwd=fwd, driver_kg_W=drv, **kw)
        if gain:
            d['c'] = dict(d['c'], a=1.0/gain)
            if gain > 50:
                d['speculative'] = d['speculative']+[f'driver gain {gain:g}']
        if fwd < F_FWD/10:
            d['speculative'] = d['speculative']+['SR-26F forward-stream rejection']
        if q and q > 20:
            d['speculative'] = d['speculative']+['SR-26Q wall heat flux']
        r = best(Sx, s, d, noz, cd['geo'], cd['dust']['NOMINAL'])
        g = gates(r, Sx, d, cd)
        heat_ok = r.get('closes') and g['G5_coil_heat_flux'] and g['G5b_stern_heat_flux']
        return dict(key=key, lev=lev, gain=gain, iso_scale=iso, f_fwd=fwd, q_max_MW_m2=q or S['q_max']/1e6, driver_kg_W=drv,
                    iso_share=d['c']['f_ph']+d['c']['f_n'], speculative=d['speculative'],
                    departure_t=r.get('departure_t'), system_t=r.get('system_t'), fusion_TW=r.get('fusion_TW'), he3_t=r.get('he3_t'),
                    coil_MW_m2=r.get('iso_coil_MW_m2'), plate_MW_m2=r.get('iso_plate_MW_m2'), heat_ok=bool(heat_ok),
                    fails=[k for k, v in g.items() if not v], result=r)
    grid = []
    for key in ('B', 'C', 'D'):
        for lev in ('base', 'stretch'):
            for fwd in (F_FWD/10, F_FWD/100, F_FWD/1000):
                for iso in (1.0, 0.3, 0.1, 0.05, 0.03, 0.02, 0.01):
                    grid.append(one(key, 'vbc', iso, fwd, lev=lev))
            for q in (30.0, 100.0, 300.0):
                grid.append(one(key, 'vbc', 1.0, F_FWD/100, q=q, lev=lev))
    for gain in (50.0, 500.0, 5000.0, 50000.0):
        for iso in (1.0, 0.03):
            x = one('A', 'established', iso, F_FWD/100, gain=gain)
            grid.append(x)
    out['requirements'] = [dict((k, v) for k, v in x.items() if k != 'result') for x in grid]
    keep = [x for x in grid if x['departure_t'] and x['heat_ok']]
    def lightest(cond):
        xs = [x for x in keep if cond(x)]
        return min(xs, key=lambda x: x['departure_t']) if xs else None
    out['minimum_sets'] = {}
    for key in ('A', 'B', 'C', 'D'):
        for env, lim in (('research_7kt', 7000.0), ('canon_4p6kt', 4600.0)):
            xs = [x for x in keep if x['key'] == key and x['departure_t'] <= lim]
            # fewest speculative items, then the mildest (largest iso, largest fwd, lowest q), then the lightest
            b = min(xs, key=lambda x: (len(x['speculative']), -x['iso_scale'], -x['f_fwd'], x['q_max_MW_m2'], x['departure_t'])) if xs else None
            out['minimum_sets'][f'{key}_{env}'] = dict((k, v) for k, v in b.items() if k != 'result') if b else None
            if b:
                out['minimum_sets'][f'{key}_{env}']['detail'] = b['result']
            print(f"MIN {key} {env:12s} " + (f"{b['lev']:7s} iso x{b['iso_scale']:g} ({b['iso_share']*100:.2f} %), fwd {b['f_fwd']:.1e}, q {b['q_max_MW_m2']:g}, drv {b['driver_kg_W']:g}: "
                                            f"dep {b['departure_t']:.0f} t, fusion {b['fusion_TW']:.1f} TW, He-3 {b['he3_t']:.0f} t; spec {b['speculative']}; fails {b['fails']}" if b else 'none'))
    for x in grid:
        print(f"  {x['key']} {x['lev']:7s} gain {x['gain']} iso x{x['iso_scale']:<5g} fwd {x['f_fwd']:.1e} q {x['q_max_MW_m2']:<4g} drv {x['driver_kg_W']:<6g} "
              + (f"dep {x['departure_t']:8.0f} coil {x['coil_MW_m2']:7.1f} plate {x['plate_MW_m2']:6.1f} heat_ok {x['heat_ok']}" if x['departure_t'] else 'no closure'))
    # sensitivity for C at its research-envelope set: spine length and dust case
    m7 = out['minimum_sets'].get('C_research_7kt')
    if m7:
        for name, ext, dust_case in (('ext_100', 100.0, 'NOMINAL'), ('ext_400', 400.0, 'NOMINAL'), ('dust_LOW', 200.0, 'LOW'), ('dust_HIGH', 200.0, 'HIGH'),
                                     ('dust_out_of_ecliptic', 200.0, 'NOMINAL_HILAT')):
            Sx = dict(S, phi_lim=1e23, phi_ship=S['phi_ship']*math.exp(2)) if m7['lev'] == 'stretch' else S
            d = design('vbc', vbc, Sx, lk=lk, iso_scale=m7['iso_scale'], f_fwd=m7['f_fwd'], **levers[m7['lev']])
            r = best(Sx, s, d, noz, lambda z0, e=ext: geometry('C', z0, ext=e), cands['C']['dust'][dust_case])
            out['sensitivity'][f'C_{name}'] = dict(departure_t=r.get('departure_t'), coil=r.get('iso_coil_MW_m2'), plate=r.get('iso_plate_MW_m2'),
                                                   gates=gates(r, Sx, d, cands['C']))
            print(f"SENS C_{name:10s} " + (f"dep {r['departure_t']:.0f} t, coil {r['iso_coil_MW_m2']:.1f}, plate {r['iso_plate_MW_m2']:.1f}" if r.get('closes') else 'no closure'))
    return out


if __name__ == '__main__':
    o = run()
    (HERE/'compact.json').write_text(json.dumps(o, indent=1, default=str)+'\n')
