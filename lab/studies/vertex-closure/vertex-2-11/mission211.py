"""Vertex 2.11 ledger: B2d vs A1 + Stern Mirror with the PIC-derived mirror losses (research, not canon).

    python3 lab/studies/vertex-closure/vertex-2-11/mission211.py      writes mission211.json/.log (needs cases_*.json, traj3d.json; ~10 min)

Same 2.8 ledger and 5 % delta-v reserve as 2.10 (lab/studies/vertex-closure/vertex-2-10/mission210.py, mission28, 2.7 mission, 2.6 compact; JUSTIFIED dust,
200 m spine, lever set b 0.99 + charge spread + SR-26A x0.01, VBC, +0.6 yr trip). What 2.11 changes for the mirror (mode 'mirror211'):
- stack heat h_heat x forward stream (grid interception, plate, secondary electrons; PIC) at 1,800 K;
- electrical: the PIC net electrical term. A draw (secondary electrons climbing the stack) is supplied by the ship at eta 0.5 (waste heat
  at 1,800 K) and costs 1 kg/kW for supply and generation (PROTOTYPE); a surplus (ion charge collected at high potential) is dumped as
  heat at 1,800 K;
- the plate heat flux (PIC) joins the isotropic flux on the stern against 10 MW/m^2;
- the reflected stream: the share that comes back onto the ship, spine or engines (neither aft nor radially away) in the 3D trajectories (traj3d.py, all four engines' coil fields) comes back to
  the ship and engines and is heat at the armour temperature; the reflected momentum stays uncredited (min rule);
- stack mass from the stack layout: grids 0.5 kg/m^2 per layer, insulators 0.5 kg/m^2 per stage, a rear grading column of opaque
  sheets 1 kg/m^2 per stage, plate 10 kg/m^2, structure 0.2 kg/m^2 per metre of depth front and rear (PROTOTYPE).
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent/'vertex-2-10')); sys.path.insert(0, str(HERE.parent/'vertex-2-8'))
import mission210 as M10  # noqa: E402

LG = M10.LG; MI = M10.MI; CP = M10.CP
A_Q = M10.A_STERN/4
T_HOT = 1800.0; ETA_SUPPLY = 0.5; KG_PER_KW = 1.0


def stack_areal(n_layers, n_stages, depth_m):
    return 0.5*n_layers+0.5*n_stages+1.0*n_stages+10.0+0.2*2*depth_m


_eng210 = M10.engine


def engine(S, s, d, nz, Pe, Tb, F_e, g, dust_t):
    if d.get('fwd_mode') != 'mirror211':
        return _eng210(S, s, d, nz, Pe, Tb, F_e, g, dust_t)
    e = M10._eng(S, s, d, nz, Pe, Tb, F_e, g, dust_t)
    m = d['mirror']; fwd = e['detail']['forward_stream_W']
    e['heat'] = [x for x in e['heat'] if not x[0].startswith('forward charged stream')]
    e['heat'].append(('Stern Mirror stack heat (PIC)', m['h_heat']*fwd, T_HOT))
    el = m['electrical']*fwd
    if el < 0:
        e['heat'].append(('Stern Mirror supply losses', -el*(1/ETA_SUPPLY-1), T_HOT))
        e['mass']['stern_mirror_supply'] = -el/1e3*KG_PER_KW
    else:
        e['heat'].append(('Stern Mirror surplus dump', el, T_HOT))
    refl = m['reflect']*fwd
    e['heat'].append(('reflected ions not passing aft (3D)', m['not_aft']*refl, S['T_armour']))
    e['mass']['stern_mirror_stack'] = m['areal']*A_Q
    e['detail']['iso_plate_W_m2'] += m['plate_frac']*4*fwd/M10.A_STERN
    e['detail']['stern_mirror'] = dict(m)
    return e


CP.engine = engine


def case(Sx, s, vbc, lk, row, f_tail, mirror, extra_spec=()):
    fwd = f_tail*row['forward_credit_tp']+row['forward_coll']
    d = MI.design(vbc, Sx, lk, iso=0.01, fwd=max(fwd, 1e-12), b=0.99)
    d['speculative'] = [x for x in d['speculative'] if x != 'SR-26F forward-stream rejection']
    if f_tail < 0.3:
        d['speculative'].append(f'SR-26F (<= {f_tail:g} of each pulse in the single-ion regime)')
    d['speculative'] += list(extra_spec)
    d['dump'] = False
    if mirror is None:
        d['fwd_mode'] = 'plate'
    else:
        d['fwd_mode'] = 'mirror211'; d['mirror'] = mirror
    nz = LG.nozzle_of(row, None, LG.FU.dispersion(LG.FU.exhaust_species(0.99, 1.0, 'charge')))
    r = MI.solve(Sx, s, d, [nz], 200.0, MI.VE_GRID, 0.6)
    x = r.get('best')
    res = dict(inputs=dict(nozzle=row['key'], f_tail=f_tail, f_fwd=fwd, mirror=mirror, speculative=d['speculative']),
               best=x, lightest_any=r.get('lightest_any'))
    if x:
        res['margin_4p6_t'] = Sx['dep_upper']/1e3-x['departure_t']
    return res


def pic(name, file):
    rows = {r['name']: r for r in json.loads((HERE/file).read_text())}
    r = rows[name]
    S = r['P_in_W_m2']
    return dict(h_heat=r['heat'], electrical=r['electrical'], reflect=r['reflect'], plate_frac=r['electrodes'][-1]['heat_W_m2']/S,
                L_m=r['L_m'], n_layers=len(r['electrodes']), n_stages=len(r['electrodes'])-2, src=name)


def main():
    s, S, Sx, vbc, lk, noz = MI.setup()
    LG.dust_justified(200.0)
    Sx = dict(Sx, dv=Sx['dv']*1.05)
    rows = {r['key']: M10.row_of(r) for r in json.loads((HERE.parent/'vertex-2-10'/'forward_final.json').read_text())['rows']}
    tj = json.loads((HERE/'traj3d.json').read_text())['cases']
    not_aft = {k: 1-v['fractions'].get('AFT', 0.0)-v['fractions'].get('RADIAL', 0.0) for k, v in tj.items()}   # back onto ship, spine, engines
    out = dict(meta=dict(reserve='delta-v x1.05', T_hot=T_HOT, eta_supply=ETA_SUPPLY, kg_per_kW=KG_PER_KW, not_aft=not_aft), cases={})
    spec_m = ('SR-210B Stern Mirror: multi-MV electrostatic reflector at GW beam power (engineering extrapolation)',)

    def go(name, *a, **kw):
        res = case(Sx, s, vbc, lk, *a, **kw); out['cases'][name] = res
        x = res['best']
        if x:
            print(f"{name:44s} dep {x['departure_t']:6.0f} t, fusion {x['fusion_TW']:.1f} TW, He-3 {x['he3_t']:.0f} t, rad/eng "
                  f"{x['radiator_t_engine']:.0f} t, stern {x['iso_plate_MW_m2']:.1f} MW/m2", flush=True)
        else:
            la = res.get('lightest_any')
            print(f"{name:44s} no heat-passing closure" + (f" (lightest failing {la['departure_t']:.0f} t, stern "
                  f"{la['iso_plate_MW_m2']:.1f} MW/m2)" if la else ''), flush=True)
    for t in (0.3, 0.1, 0.03, 0.01):
        go(f'B2d_plate_tail{t:g}', rows['B2d'], t, None)
        go(f'A1_plate_tail{t:g}', rows['B2d_z12'], t, None)
    # mirror variants: PIC (1D) losses x 3D return share
    variants = [('D210', 'cases_main.json', 'D210_thermal_{t}'), ('D210_o1', 'cases_main.json', 'D210_o1_thermal_{t}'),
                ('DBD100', 'cases_bd100.json', 'DBD100_thermal_{t}')]
    sens = [('D210_Yp0.3', 'cases_sens.json', 'sens_D210_Yp0.3'), ('D210_Yp3', 'cases_sens.json', 'sens_D210_Yp3'),
            ('D210_fesc0.1', 'cases_sens.json', 'sens_D210_fesc0.1')]
    returns = [('facets-10_3D', not_aft['alpha-10_B']), ('facets+10_3D', not_aft['alpha10_B'])]
    for rname, na in returns:
        for vn, f, key in variants:
            for tag, t in (('10', 0.1), ('30', 0.3)):
                m = pic(key.format(t=tag), f)
                m['not_aft'] = na; m['areal'] = stack_areal(m['n_layers'], m['n_stages'], m['L_m'])
                go(f'A1+{vn}_{rname}_tail{t:g}', rows['B2d_z12'], t, m, extra_spec=spec_m)
        for vn, f, key in sens:
            m = pic(key, f); m['not_aft'] = na; m['areal'] = stack_areal(m['n_layers'], m['n_stages'], m['L_m'])
            go(f'A1+{vn}_{rname}_tail0.1', rows['B2d_z12'], 0.1, m, extra_spec=spec_m)
    # supply specific mass sensitivity (0.1 kg/kW: e.g. drive dynamos feeding the stack directly), corrected facets only
    globals()['KG_PER_KW'] = 0.1
    na = not_aft['alpha-10_B']
    for vn, f, key in variants:
        for tag, t in (('10', 0.1), ('30', 0.3)):
            m = pic(key.format(t=tag), f); m['not_aft'] = na; m['areal'] = stack_areal(m['n_layers'], m['n_stages'], m['L_m'])
            go(f'A1+{vn}_facets-10_3D_supply0.1_tail{t:g}', rows['B2d_z12'], t, m, extra_spec=spec_m)
    globals()['KG_PER_KW'] = 1.0
    return out


if __name__ == '__main__':
    import contextlib, io
    buf = io.StringIO()
    class Tee(io.TextIOBase):
        def write(self, s):
            sys.__stdout__.write(s); buf.write(s); return len(s)
    with contextlib.redirect_stdout(Tee()):
        o = main()
    (HERE/'mission211.json').write_text(json.dumps(o, indent=1, default=float)+'\n'); (HERE/'mission211.log').write_text(buf.getvalue())
