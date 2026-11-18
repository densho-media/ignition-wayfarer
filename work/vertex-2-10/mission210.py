"""Vertex 2.10 shared mission ledger for the forward-stream candidates (research, not canon).

    python3 work/vertex-2-10/mission210.py      writes work/vertex-2-10/mission210.json and .log (needs forward_final.json; ~10 min)

The 2.8/2.9 ledger unchanged (work/vertex-2-8/mission28.py on 2.7 mission.py / 2.6 compact.py: four burns, 0.016 c, JUSTIFIED dust,
200 m spine, lever set b 0.99 + charge spread + SR-26A x0.01, VBC, +0.6 yr trip), with the 5 % delta-v reserve on every case (Q3).
What 2.10 adds:
1. The nozzle per candidate from forward_final.json, credited by the kept min-cosine screen (O2).
2. f_tail = the share of each pulse that behaves as single ions (the SR-26F quantity). The forward stream is f_tail x the traced single-ion
   share on the ship. Swept 1 (no SR-26F at all), 0.3 and 0.1 (the span of the 2.9 exploratory diagnostics), 0.03, 0.01 (SR-26F).
3. A new gate on the stern: the forward beam's average flux on the r 45 m stern disk (four engines) joins the isotropic flux, against
   q_max 10 MW/m^2 for a plate or collector face. 2.6-2.9 checked only the isotropic flux there.
4. How the forward stream is handled (mode):
   plate      B2d practice: absorbed by the stern plate at 1300 K (heat-pumped to the 1800 K radiator, cost x2.28).
   collector  C: a hot (>= 1800 K) liquid-metal-cooled collector replacing the plate face, +10 kg/m^2; heat at radiator temperature.
   mirror     B: the Stern Mirror, an electrostatic ion reflector (suppressor + decelerating ribbon grids, ~10 MV) over the stern disk.
              Reflected ions leave aft past the cluster; only the grid interception and secondary-electron loss h_B (5 %, swept 2-15 %)
              is heat at 1800 K; ribbons at grazing incidence take a 30 MW/m^2 beam (10 MW/m^2 on the ribbon face); 25 kg/m^2 grids
              and insulators + 5 t high-voltage system per engine. Facets tilted 10 deg outward send 94.9 % of the reflected ions aft
              past the cluster (aft cosine 0.94); 5.1 % strike the engines' front bulkheads at 1300 K (recover.py B1).
   The reflected momentum is not credited to kappa (the min rule keeps the collective cosine); it is reported separately.
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent/'vertex-2-8'))
import mission28 as LG  # noqa: E402

MI = LG.MI; CP = MI.CP; FU = LG.FU
A_STERN = math.pi*45.0**2          # stern disk, four engines share it
Q_PLATE = 10e6; Q_MIRROR = 30e6
COLLECTOR_EXTRA_KG_M2 = 10.0; MIRROR_KG_M2 = 25.0; MIRROR_HV_KG = 5e3
T_HOT = 1800.0
S_B = 0.051                # recover.py B1, facet tilt 10 deg
_eng = CP.engine            # mission28's engine (extra coils, dump)


def engine(S, s, d, nz, Pe, Tb, F_e, g, dust_t):
    e = _eng(S, s, d, nz, Pe, Tb, F_e, g, dust_t)
    mode = d.get('fwd_mode', 'plate'); fwd = e['detail']['forward_stream_W']
    beam = 4*fwd/A_STERN
    e['detail']['stern_beam_W_m2'] = beam
    if mode == 'plate':
        e['detail']['iso_plate_W_m2'] += beam
    elif mode == 'collector':
        e['heat'] = [h for h in e['heat'] if not h[0].startswith('forward charged stream')]
        e['heat'].append(('forward collector (hot face)', fwd, T_HOT))
        e['mass']['collector_face'] = COLLECTOR_EXTRA_KG_M2*A_STERN/4
        e['detail']['iso_plate_W_m2'] += beam
    elif mode == 'mirror':
        h = d['h_B']
        e['heat'] = [x for x in e['heat'] if not x[0].startswith('forward charged stream')]
        e['heat'].append(('Stern Mirror grid interception and secondaries', h*fwd, T_HOT))
        # facets tilted 10 deg outward: 5.1 % of the reflected stream still strikes the engines' front bulkheads (recover.py B1)
        e['heat'].append(('reflected ions striking engine fronts', S_B*(1-h)*fwd, S['T_armour']))
        e['mass']['stern_mirror_grids'] = MIRROR_KG_M2*A_STERN/4
        e['mass']['stern_mirror_hv'] = MIRROR_HV_KG
        e['detail']['iso_plate_W_m2'] += beam*Q_PLATE/Q_MIRROR       # ribbons at grazing incidence: 30 MW/m^2 beam = 10 on the face
    return e


CP.engine = engine


def row_of(fr):
    r = dict(fr)
    r['kappa_credit'] = fr['kappa_credit']
    r['forward_credit_tp'] = fr['test_particle']['forward_on_ship']
    r['forward_coll'] = fr.get('forward_coll', 0.0)
    return r


def case(Sx, s, vbc, lk, row, f_tail, mode='plate', h_B=0.05, extra_spec=()):
    fwd = f_tail*row['forward_credit_tp']+row['forward_coll']
    d = MI.design(vbc, Sx, lk, iso=0.01, fwd=max(fwd, 1e-12), b=0.99)
    d['speculative'] = [x for x in d['speculative'] if x != 'SR-26F forward-stream rejection']
    if f_tail < 0.3:
        d['speculative'].append(f'SR-26F (<= {f_tail:g} of each pulse in the single-ion regime)')
    d['speculative'] += list(extra_spec)
    d['dump'] = False; d['fwd_mode'] = mode; d['h_B'] = h_B
    nz = LG.nozzle_of(row, None, FU.dispersion(FU.exhaust_species(0.99, 1.0, 'charge')))
    r = MI.solve(Sx, s, d, [nz], 200.0, MI.VE_GRID, 0.6)
    x = r.get('best')
    res = dict(inputs=dict(nozzle=row['key'], mode=mode, f_tail=f_tail, f_fwd=fwd, h_B=h_B if mode == 'mirror' else None,
                           kappa_credit=row['kappa_credit'], speculative=d['speculative']),
               best=x, lightest_any=r.get('lightest_any'), heat_ok=r.get('heat_ok', False))
    if x:
        res['margin_4p6_t'] = Sx['dep_upper']/1e3-x['departure_t']
        res['he3_t'] = x['he3_t']
    return res


def short(res):
    i = res['inputs']; x = res['best']
    head = f"{i['nozzle']:8s} {i['mode']:9s} tail {i['f_tail']:<5g} fwd {i['f_fwd']:.1e} k {i['kappa_credit']:.3f} spec {len(i['speculative'])}"
    if not x:
        la = res.get('lightest_any')
        return head+' | no heat-passing closure'+(f" (lightest failing {la['departure_t']:.0f} t, coil {la['iso_coil_MW_m2']:.1f} stern {la['iso_plate_MW_m2']:.1f} MW/m2)" if la else '')
    return head+f" | dep {x['departure_t']:.0f} t, ve {x['ve_c']:.3f} c, fusion {x['fusion_TW']:.1f} TW, He-3 {x['he3_t']:.0f} t, rad/eng {x['radiator_t_engine']:.0f} t, stern {x['iso_plate_MW_m2']:.1f} MW/m2"


TAILS = (1.0, 0.3, 0.1, 0.03, 0.01)


def main():
    s, S, Sx, vbc, lk, noz = MI.setup()
    LG.dust_justified(200.0)
    Sx = dict(Sx, dv=Sx['dv']*1.05)
    rows = {r['key']: row_of(r) for r in json.loads((HERE/'forward_final.json').read_text())['rows']}
    out = dict(meta=dict(title='Vertex 2.10 forward-stream ledger (research, not canon)', tails=TAILS, reserve='delta-v x1.05',
                         A_stern_m2=A_STERN, q_plate=Q_PLATE, q_mirror=Q_MIRROR), cases={})

    def go(name, *a, **kw):
        res = case(Sx, s, vbc, lk, *a, **kw); out['cases'][name] = res
        print(f"{name:34s} {short(res)}", flush=True)
    plans = [('B2d', 'B2d', 'plate'), ('A1_burn12', 'B2d_z12', 'plate'), ('A2_mirror10', 'M10', 'plate'),
             ('C_collector', 'B2d_z12', 'collector'), ('B_mirror', 'B2d_z12', 'mirror'), ('B_mirror_on_B2d', 'B2d', 'mirror')]
    spec_of = {'mirror': ('SR-210B Stern Mirror: ~10 MV electrostatic reflector at GW beam power (engineering extrapolation)',),
               'collector': (), 'plate': ()}
    for name, key, mode in plans:
        for t in TAILS:
            go(f'{name}_tail{t:g}', rows[key], t, mode=mode, extra_spec=spec_of[mode])
    for h in (0.02, 0.15):
        for t in (1.0, 0.3, 0.1):
            go(f'B_mirror_hB{h:g}_tail{t:g}', rows['B2d_z12'], t, mode='mirror', h_B=h, extra_spec=spec_of['mirror'])
    return out


if __name__ == '__main__':
    import contextlib, io
    buf = io.StringIO()

    class Tee(io.TextIOBase):
        def write(self, s):
            sys.__stdout__.write(s); buf.write(s); return len(s)
    with contextlib.redirect_stdout(Tee()):
        o = main()
    (HERE/'mission210.json').write_text(json.dumps(o, indent=1, default=float)+'\n')
    (HERE/'mission210.log').write_text(buf.getvalue())
