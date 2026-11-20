"""Vertex 2.8: the nozzle candidates propagated through the four-burn 0.016 c mission ledger (research, not canon).

    python3 lab/studies/vertex-closure/vertex-2-8/mission28.py        writes lab/studies/vertex-closure/vertex-2-8/mission28.json and mission28.log (needs nozzle.json; about 5-10 min)

The ledger is Vertex 2.7's, unchanged (lab/studies/vertex-closure/vertex-2-7/mission.py on lab/studies/vertex-closure/vertex-2-6/compact.py, corrected braking path, JUSTIFIED dust
on the 200 m spine as the design case). What 2.8 changes per candidate, all from nozzle.json:
1. the credited nozzle efficiency kappa_credit (min of the collective and single-ion regimes) times sqrt(eta_dispersion);
2. the burn position (z0 = zb / R) and main-coil field, so the coil heat flux, fin and ship distances follow the real geometry;
3. the extra coils (plug, collar): conductor, virial structure for the added stored energy, armour, fin, and their radiation heat;
4. the forward stream: f_fwd = f_tail x the single-ion forward share landing on the ship (+ the collective forward share), where
   f_tail is the share of the pulse that leaves the collective regime before the plug (STATED requirement, swept), and either onto the
   stern plate at 1300 K (2.7 rule) or into a forward beam dump with direct conversion (PROTOTYPE engineering option, swept).
Gates: 4.6 kt canon departure, 7 kt research, +0.6 yr trip, q_max 10 MW/m^2 on coils and stern, He-3 canon 1,094 t (reported, D3 logistics).
"""
import copy
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
V27 = HERE.parent/'vertex-2-7'
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(V27))
import mission as MI  # noqa: E402  (pulls in compact, protect, the corrected path and the shared ledger)
import fuel as FU  # noqa: E402
import dust as DU  # noqa: E402
import protect as PR  # noqa: E402

CP = MI.CP; L = MI.L; C = MI.C; DAY = MI.DAY; YR = MI.YR; MU0 = 4e-7*math.pi
_ENGINE = CP.engine
T_DUMP = 1800.0               # forward beam dump face at the radiator temperature (C/C, PROTOTYPE), so its heat needs no heat pump
DUMP_KG_M2 = 30.0             # cooled dump / converter panel incl. manifolds (PROTOTYPE)
Q_DUMP = 10e6                 # same steady wall limit as the armour (ITER-class), W/m^2


def engine(S, s, d, nz, Pe, Tb, F_e, g, dust_t):
    """CP.engine plus the 2.8 extra coils and the forward beam dump."""
    e = _ENGINE(S, s, d, nz, Pe, Tb, F_e, g, dust_t)
    c = d['c']; sh = L.shares(c); plasma = (sh['jet']+sh['leak']+sh['plume'])*Pe
    sig, rho, _ = S['materials']['cnt']
    for x in nz.get('extra', []):
        Ac = x['I']/(S['J_e']*d['Je_factor']); ln = 2*math.pi*x['R']; w = max(math.sqrt(Ac), 0.03)+0.04
        frac = w/(2*x['R'])*x['R']/x['d']
        fin = L.shield(S, c['f_n']*Pe, Tb, x['d'], 0.0)
        e['mass'][f"{x['name']}_conductor"] = S['rho_cond']*Ac*ln
        e['mass'][f"{x['name']}_structure"] = S['k_virial']*rho*x['E_J']/sig
        e['mass'][f"{x['name']}_armour"] = 19300.0*0.005*w*ln
        e['mass'][f"{x['name']}_neutron_fin"] = S['rho_sh']*fin['t_m']*w*ln
        e['heat'].append((f"isotropic radiation on {x['name']} armour", L.iso_deposit(c, frac)*Pe, S['T_armour']))
        e['heat'].append((f"neutrons through the fin into the {x['name']}", frac*c['f_n']*Pe*S['dep_n']*math.exp(-fin['t_m']/S['lam']), S['T_cold']))
        e['detail'][f"iso_{x['name']}_W_m2"] = (c['f_ph']+c['f_n'])*Pe/(4*math.pi*x['d']**2)
    if d.get('dump'):
        fwd = d['f_fwd']*plasma
        e['heat'] = [h for h in e['heat'] if not h[0].startswith('forward charged stream')]
        e['heat'].append(('forward beam dump (after direct conversion)', (1-d['eta_dc'])*fwd, T_DUMP))
        e['mass']['forward_beam_dump'] = fwd/Q_DUMP*DUMP_KG_M2
        e['detail']['dump_area_m2'] = fwd/Q_DUMP
    e['detail']['forward_stream_W'] = d['f_fwd']*plasma
    return e


CP.engine = engine


def dust_justified(ext=200.0):
    just_env = dict(ipd_scale=2.0, kb_scale=3.0, kb_alpha=0.83, kb_mmax=1e-6, isd_rho=6.2e-24, isd_tail='EXTRAPOLATED')
    if 'JUSTIFIED' not in DU.E.CASE:
        DU.add_case('JUSTIFIED', just_env, damage_from='HIGH')
    segs, _ = PR.mission(466.85*DAY, 0.072*C, None)
    m = DU.protection('JUSTIFIED', segs, ext-50.0)['total_t']
    MI._DUST[(ext, 'NOMINAL')] = m
    return m


def nozzle_of(row, kappa=None, eta_disp=1.0):
    """Ledger nozzle dict from a nozzle.json row: main coil BR and burn z0, credited kappa, the extra coils."""
    mainc = [c for c in row['coils'] if c['name'] == 'main'][0]
    k = row['kappa_credit'] if kappa is None else kappa
    extra = []
    E_main = 0.5*MU0*mainc['R_m']*(math.log(8*mainc['R_m']/0.15)-1.75)*(mainc['I_MA']*1e6)**2
    E_extra = max(row['E_B_GJ']*1e9-E_main, 0.0)
    others = [c for c in row['coils'] if c['name'] != 'main']
    tot_I = sum(c['I_MA']*c['R_m'] for c in others) or 1.0
    for c in others:
        extra.append(dict(name=c['name'], I=c['I_MA']*1e6, R=c['R_m'], d=math.hypot(c['R_m'], c['z_m']-row['zb_m']),
                          E_J=E_extra*c['I_MA']*c['R_m']/tot_I))
    return dict(BR=mainc['B_centre_T']*mainc['R_m'], z0=row['zb_m']/mainc['R_m'], kappa=k*math.sqrt(eta_disp), kappa_geom=k, extra=extra,
                key=row['key'])


def case(Sx, s, vbc, lk, row, f_tail=1.0, dump=False, eta_dc=0.5, iso=0.01, b=0.99, mode='charge', kappa=None, trip=0.6, ext=200.0,
         extra_spec=()):
    fwd = f_tail*row['forward_credit_tp']+row['forward_coll']
    d = MI.design(vbc, Sx, lk, iso=iso, fwd=max(fwd, 1e-12), b=b)
    d['speculative'] = [x for x in d['speculative'] if x != 'SR-26F forward-stream rejection']
    if f_tail < 1.0:
        d['speculative'].append(f'SR-26F restated: <= {f_tail:g} of the pulse leaves the collective regime before the plug')
    d['speculative'] += list(extra_spec)
    d['dump'] = dump; d['eta_dc'] = eta_dc
    nz = nozzle_of(row, kappa, FU.dispersion(FU.exhaust_species(b, 1.0, mode)))
    r = MI.solve(Sx, s, d, [nz], ext, MI.VE_GRID, trip)
    x = r.get('best')
    res = dict(inputs=dict(nozzle=row['key'], f_tail=f_tail, f_fwd=fwd, dump=dump, eta_dc=eta_dc, iso=iso, b=b, mode=mode,
                           kappa_credit=nz['kappa_geom'], kappa_eff=nz['kappa'], trip=trip, ext=ext, speculative=d['speculative']),
               best=x, lightest_any=r.get('lightest_any'), heat_ok=r.get('heat_ok', False), closes=r.get('closes', False))
    if x:
        X = math.exp(Sx['burns']*Sx['dv']/(x['ve_c']*C))-1
        res['margin_4p6_t'] = Sx['dep_upper']/1e3-x['departure_t']
        res['he3_over_canon_t'] = x['he3_t']-Sx['he3_canon_kg']/1e3
        res['mass_ratio_total'] = 1+X
    return res


def short(res):
    x = res['best']; i = res['inputs']
    head = f"{i['nozzle']:4s} k {i['kappa_credit']:.3f} tail {i['f_tail']:<6g} fwd {i['f_fwd']:.1e} dump {'Y' if i['dump'] else 'n'} iso x{i['iso']:<5g} b {i['b']} {i['mode']:7s}"
    if not x:
        la = res.get('lightest_any')
        extra = f" (lightest heat-failing: dep {la['departure_t']:.0f} t coil {la['iso_coil_MW_m2']:.1f} plate {la['iso_plate_MW_m2']:.2f})" if la else ''
        return head+' | no heat-passing closure'+extra
    return head+f" | {MI.short(x)} | margin {res['margin_4p6_t']:+.0f} t, He-3 +{res['he3_over_canon_t']:.0f} t"


def run():
    s, S, Sx, vbc, lk, noz = MI.setup()
    dj = dust_justified(200.0)
    nzj = json.loads((HERE/'nozzle.json').read_text())
    rows = {r['key']: r for r in nzj['rows']}
    for r in list(rows.values())+nzj['adaptive']:
        r['forward_credit_tp'] = r['test_particle']['forward_on_ship']
        r['forward_coll'] = r['collective']['c1']['fractions']['FORWARD']
    out = dict(meta=dict(title='Vertex 2.8 ledger (research, not canon)', dust_case='JUSTIFIED', dust_t=dj, spine_m=200.0,
                         dep_canon_t=S['dep_upper']/1e3, he3_canon_t=S['he3_canon_kg']/1e3, T_dump=T_DUMP, dump_kg_m2=DUMP_KG_M2), cases={})
    C_ = out['cases']

    def go(name, row, **kw):
        res = case(Sx, s, vbc, lk, row, **kw); C_[name] = res
        print(f"{name:34s} {short(res)}", flush=True)
        return res
    # 0. reproduce 2.7 inside JUSTIFIED with its own (single-ion) nozzle credit, then the same nozzle at its credited collective value
    A = rows['A']
    go('A_2.7_levers_TPcredit', A, kappa=0.97, f_tail=0.0, iso=0.01)
    go('A_2.7_point_TPcredit', A, kappa=A['test_particle']['kappa'], f_tail=0.0, iso=0.03, b=0.95, mode='thermal')
    go('A_credited_levers', A, f_tail=0.0, iso=0.01)
    go('A_credited_point', A, f_tail=0.0, iso=0.03, b=0.95, mode='thermal')
    # 1. every candidate on the lever set (b 0.99, charge spread, SR-26A x0.01), forward stream as traced (f_tail 1) and restated
    for k in ('A', 'B1', 'B2a', 'B2b', 'B2c', 'B2d', 'B3a', 'B3b'):
        if k not in rows or rows[k]['kappa_credit'] <= 0:
            continue
        r = rows[k]
        for tail in (1.0, 0.1, 0.01):
            go(f'{k}_tail{tail:g}', r, f_tail=tail)
        go(f'{k}_tail0.1_dump', r, f_tail=0.1, dump=True)
        go(f'{k}_tail1_dump', r, f_tail=1.0, dump=True)
        go(f'{k}_tail0.01_iso0.03', r, f_tail=0.01, iso=0.03)
        go(f'{k}_tail0.01_b0.95_thermal', r, f_tail=0.01, b=0.95, mode='thermal')
    return out


if __name__ == '__main__':
    import contextlib, io
    buf = io.StringIO()

    class Tee(io.TextIOBase):
        def write(self, s):
            sys.__stdout__.write(s); buf.write(s); return len(s)
    with contextlib.redirect_stdout(Tee()):
        o = run()
    (HERE/'mission28.json').write_text(json.dumps(o, indent=1, default=str)+'\n')
    (HERE/'mission28.log').write_text(buf.getvalue())
