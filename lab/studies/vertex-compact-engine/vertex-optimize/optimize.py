#!/usr/bin/env python3
"""ENG-066..072: the burn moved aft with stronger closure coils, combined with energy extraction and the source levers (research, not canon).

Owner brief 2026-11-24 12:16Z ("Fusion Energy Extraction & Magnetic Topology Optimization"): investigate the burn point about 4 m farther aft
with stronger closure coils (approved for research geometry only), combine it with early extraction using compatible physics instead of
multiplying separate gains, look past vacuum test particles where practical, verify the whole momentum balance and evaluate the coils
(stored energy, forces, conductor and structure mass, cryogenics, quench).

What it does (standard library only; the field and particle physics is vertex-ron/ron.py, the engine ledger vertex-extraction, both read-only):
  1. Geometry refinement around ENG-065's best point: burn dz {3, 4, 5, 6} m aft x closure current {x3, x4, x6}, graded closure
     (strongest next to the shield, or next to the burn), aft rings spaced x1.25, plus the drawn engine and ENG-065's best (mirror4 dz 4)
     as references. Every ribbon is re-aimed edge-on to the moved burn. Capture current (k) is re-solved for each geometry.
  2. Species test particles (relativistic Boris push in the loop field; the same integrator as ron._push, here also returning the
     momentum at the end so the balance can be booked), two plasma pictures for the debris:
       VACUUM  the debris is magnetised from the burn (ENG-062/065, an optimistic bound on capture);
       CAVITY  the debris expands as a diamagnetic bubble and is unmagnetised (straight lines) out to the radius where the field energy
               equals its energy, R_b = (3 mu0 E / (2 pi B^2))^(1/3), then a test particle in the vacuum field (a pessimistic bound:
               the real bubble also loses energy to the field and is turned earlier).
     The X-ray/neutron pickup is re-traced for each geometry (ron.sky_axisymmetric), scaled to the ledger's C1 value.
  3. Every vertex-source lever through every geometry and picture with the momentum-consistent ledger (vertex-extraction engine()),
     so extraction and topology are combined in one calculation, never by multiplying gains.
  4. Momentum balance per geometry: initial momentum (zero for an isotropic burn) = escaping + trapped + delivered to the ship, the last
     split into the share delivered through the field (coil reaction) and by particles striking hardware.
  5. Hydrogen reaction mass as two bounds (inelastic: momentum shared, impulse unchanged; ideal elastic: energy kept), coupling OPEN.
  6. Closure-coil engineering for the drawn engine as built, the drawn engine at its capture current and the optimised geometry: stored
     energy, field at the winding, hoop tension and required structure, axial forces, conductor/structure/cryostat mass, cryogenic load
     and quench energy dump.

    python3 lab/studies/vertex-compact-engine/vertex-optimize/optimize.py [--quick]     writes results/optimize.json and .log
"""
import json
import math
import sys
import time
from multiprocessing import Pool
from pathlib import Path

HERE = Path(__file__).resolve().parent
QUICK = '--quick' in sys.argv
sys.path.insert(0, str(HERE.parent / 'vertex-extraction'))
_argv = list(sys.argv)
import extraction as X  # noqa: E402
sys.argv = _argv
Cmp, ron = X.Cmp, X.ron
AMU, MEV, C = ron.AMU, ron.MEV, ron.C
MU0 = 4e-7 * math.pi
N_DIR = 12 if QUICK else 24
RESEARCH = 'mirror4|4'                            # burn 4 m aft, closure x4 (owner-approved research geometry 2026-11-24)


# ---------- geometry ------------------------------------------------------------------------------------------------------------

def geometry(key, dz, fc, grade=None, aft_space=1.0):
    """The drawn C1 engine with the burn dz m aft of its drawn point (hardware fixed, ribbons re-aimed at the burn), the three closure
    rings forward of the burn at fc times their drawn current (or a graded list, shield-side first) and the aft rings' axial spacing
    scaled by aft_space (aft ring radii unchanged)."""
    xb1 = Cmp.SHIP['x_burn']; D1 = Cmp.SHIP['tank'][0] - xb1
    p, _ = Cmp.variant('C1 production cluster as drawn', D1, 6.0, 0.62)
    rings = []; j = 0
    for (x, r, s) in sorted(p['rings'], key=lambda t: -t[0]):
        if x > 0.5:
            s = s * (grade[j] if grade else fc); j += 1
        else:
            x = x * aft_space
        rings.append((x + dz, r, s))
    x0, r0, r1, t = p['shield_disc']
    return dict(p, label=key, rings=rings, plug_x_m=p['plug_x_m'] + dz, shield_disc=(x0 + dz, r0, r1, t))


def configs():
    c = [('drawn|0', 0.0, 1.0, None, 1.0, 'drawn engine, burn at its drawn point (C1)'),
         ('mirror4|4', 4.0, 4.0, None, 1.0, 'ENG-065 best: burn 4 m aft, closure x4')]
    if QUICK:
        return c
    for dz in (3.0, 5.0, 6.0):
        c.append((f'mirror4|{dz:g}', dz, 4.0, None, 1.0, f'burn {dz:g} m aft, closure x4'))
    for dz in (3.0, 4.0, 5.0, 6.0):
        for fc in (3.0, 6.0):
            c.append((f'mirror{fc:g}|{dz:g}', dz, fc, None, 1.0, f'burn {dz:g} m aft, closure x{fc:g}'))
    for dz in (4.0, 5.0):
        c.append((f'gradeS|{dz:g}', dz, 0.0, (8.0, 4.0, 2.0), 1.0, f'burn {dz:g} m aft, closure graded x8/x4/x2 from the shield'))
        c.append((f'gradeB|{dz:g}', dz, 0.0, (2.0, 4.0, 8.0), 1.0, f'burn {dz:g} m aft, closure graded x2/x4/x8 from the shield'))
        c.append((f'space|{dz:g}', dz, 4.0, None, 1.25, f'burn {dz:g} m aft, closure x4, aft rings spaced x1.25'))
    return c


# ---------- particles -------------------------------------------------------------------------------------------------------------

def push(args):
    """ron._push with an optional unmagnetised start (straight line to radius r0) and the final momentum direction for every outcome."""
    v, k, sp, d, r0 = args
    fil = ron.filaments(v['coils']); els = [e for e in v['elements'] if e['role'] != 'plug']; L = v['scale_m']
    m, q = sp['m'], sp['Z'] * ron.E_CH
    if 'E' in sp:
        g = 1 + sp['E'] / (m * C * C); sv_ = C * math.sqrt(1 - 1 / g ** 2)
    else:
        sv_ = sp['v']; g = 1 / math.sqrt(1 - (sv_ / C) ** 2)
    x_aft, x_fwd, r_out = -v['aft_exit_m'], v['fwd_exit_m'], v['radial_exit_m']
    u = [g * sv_ * d[0], g * sv_ * d[1], g * sv_ * d[2]]; x = [0.0, 0.0, 0.0]
    if r0 > 0:                                                     # cavity: straight flight, checking the hardware in 0.05 m steps
        n = max(2, int(r0 / 0.05))
        for i in range(1, n + 1):
            a = (r0 * (i - 1) / n * d[0], r0 * (i - 1) / n * math.hypot(d[1], d[2]))
            b = (r0 * i / n * d[0], r0 * i / n * math.hypot(d[1], d[2]))
            for e in els:
                if ron._seg_hits(e, a, b):
                    return dict(out='HIT', part=e['name'], ux=d[0], cav=True)
        x = [r0 * d[0], r0 * d[1], r0 * d[2]]
    t = 0.0; tmax = 20 * (x_fwd - x_aft + r_out) / sv_
    while t < tmax:
        rho = math.hypot(x[1], x[2]); br, bx = ron.field(fil, x[0], rho, k)
        B = (bx, br * x[1] / rho, br * x[2] / rho) if rho > 1e-9 else (bx, 0.0, 0.0)
        b = math.sqrt(B[0] ** 2 + B[1] ** 2 + B[2] ** 2)
        dt = min(L / 200 / sv_, (2 * math.pi * g * m / (q * b)) / 30 if b > 0 else 1.0)
        h = q * dt / (2 * g * m); tv = [h * B[0], h * B[1], h * B[2]]; t2 = sum(a * a for a in tv); s = [2 * a / (1 + t2) for a in tv]
        up = [u[0] + (u[1] * tv[2] - u[2] * tv[1]), u[1] + (u[2] * tv[0] - u[0] * tv[2]), u[2] + (u[0] * tv[1] - u[1] * tv[0])]
        u = [u[0] + (up[1] * s[2] - up[2] * s[1]), u[1] + (up[2] * s[0] - up[0] * s[2]), u[2] + (up[0] * s[1] - up[1] * s[0])]
        x0 = list(x); x = [x[i] + u[i] / g * dt for i in range(3)]; t += dt
        rho = math.hypot(x[1], x[2]); un = math.sqrt(u[0] ** 2 + u[1] ** 2 + u[2] ** 2)
        for e in els:
            if ron._seg_hits(e, (x0[0], math.hypot(x0[1], x0[2])), (x[0], rho)):
                return dict(out='HIT', part=e['name'], ux=u[0] / un, cav=False)
        if x[0] < x_aft:
            return dict(out='AFT', ux=u[0] / un)
        if x[0] > x_fwd:
            return dict(out='FORWARD', ux=u[0] / un)
        if rho > r_out:
            return dict(out='RADIAL', ux=u[0] / un)
    un = math.sqrt(u[0] ** 2 + u[1] ** 2 + u[2] ** 2)
    return dict(out='TRAPPED', ux=u[0] / un)


def cavity_radius(E_J, B_T):
    return (3 * MU0 * E_J / (2 * math.pi * B_T ** 2)) ** (1 / 3)


def stats(rr, dirs):
    n = len(rr); hit = sum(r['out'] == 'HIT' for r in rr) / n
    parts = {}
    for r in rr:
        if r['out'] == 'HIT':
            parts[r['part']] = parts.get(r['part'], 0) + 1
    esc = [r for r in rr if r['out'] in ('AFT', 'FORWARD', 'RADIAL')]
    # momentum balance in units of the species' momentum p (all particles at equal speed): ship = initial - escaping - trapped
    p_init = sum(d[0] for d in dirs) / n
    p_esc = sum(r['ux'] for r in esc) / n
    p_trap = sum(r['ux'] for r in rr if r['out'] == 'TRAPPED') / n
    p_hard = sum(r['ux'] for r in rr if r['out'] == 'HIT') / n          # delivered to the struck hardware (momentum at impact)
    ship = p_init - p_esc - p_trap
    field = ship - p_hard                                                # delivered through the field to the coils
    return dict(hit=hit, aft=sum(r['out'] == 'AFT' for r in rr) / n, forward=sum(r['out'] == 'FORWARD' for r in rr) / n,
                trapped=sum(r['out'] == 'TRAPPED' for r in rr) / n, cos=-p_esc, err=math.sqrt(max(hit * (1 - hit), 1.0 / n) / n),
                parts=parts, cav_hits=sum(1 for r in rr if r.get('cav')) / n,
                balance=dict(p_init=p_init, p_escaping=p_esc, p_trapped=p_trap, ship=ship, via_field=field, via_hardware=p_hard,
                             closure=abs(p_init - p_esc - p_trap - ship)))


def run(pool, k, cfg, Pd, sky_ref):
    key, dz, fc, grade, sp_, label = cfg
    p = geometry(key, dz, fc, grade, sp_)
    v, src, E, cap = ron.configure(p, k)
    kk = cap['k']; fil = ron.filaments(v['coils'])
    B0 = math.hypot(*ron.field(fil, 0.0, 1e-6, kk))
    Rb = cavity_radius(Pd, B0)
    m_d = 2.01410 * AMU
    sps = X.species(X_VDEB)
    dirs = ron.fib_dirs(N_DIR)
    todo = [(sp, 0.0, sp['id']) for sp in sps] + [(sp, Rb, sp['id'] + '_cav') for sp in sps if not sp['fast']]
    res = pool.map(push, [(v, kk, sp, d, r0) for sp, r0, _ in todo for d in dirs], chunksize=2)
    S = {}
    for j, (_, _, sid) in enumerate(todo):
        S[sid] = stats(res[j * N_DIR:(j + 1) * N_DIR], dirs)
    sky = ron.sky_axisymmetric(v['elements'], n=1500)
    ms = ron.masses(v, k, cap, src)
    out = dict(key=key, label=label, dz=dz, fc=fc, grade=grade, aft_space=sp_, k=kk, B_burn_T=B0, cavity_R_m=Rb, stored_J=cap['W_J'],
               binding=cap.get('binding_part'), coil_t=ms['conductor_t'] + ms['coil_structure_t'] + ms['cryostat_t'], masses=ms,
               sky=sum(sky.values()), pickup_scale=sum(sky.values()) / sky_ref if sky_ref else 1.0, species=S,
               rings=[(round(x, 2), round(r, 2), round(s, 3)) for x, r, s in p['rings']], _v=v, _cap=cap, _src=src)
    print(f'{key:11s} k {kk:6.2f} B {B0:5.2f} T Rb {Rb:4.2f} m  ' +
          ' '.join(f'{s} {S[s]["hit"]:.2f}/{S[s]["cos"]:+.2f}' for s in ('p14.7', 'a3.6', 'D', 'He3', 'D_cav', 'He3_cav')) +
          f'  sky {out["sky"]:.3f} coils {out["coil_t"]:.0f} t', flush=True)
    return out


# ---------- coils -------------------------------------------------------------------------------------------------------------------

def coil_engineering(v, k_cur, label, minor=None, I_op=50e3, V_dump=10e3, sigma=1.5e9, h_cu=8.0e4, q_static=1.0, cop_20K=60.0):
    """Per coil and total: field at the winding, hoop tension and the structure it needs, the axial force from the other coils, stored
    energy, the conductor and its cryostat, the static heat leak to 20 K and the quench: dump time at I_op/V_dump and the copper whose
    20-300 K enthalpy (h_cu, J/kg) could absorb the whole stored energy if the dump fails.
    Self force of a ring (radius R, winding radius a, uniform current): T = mu0 I^2 (ln(8R/a) - 3/4) / (4 pi) (from dL/dR); the
    external part I B_x,ext R. a is the round winding radius from `minor` (name -> m, the 3D engine) or the geometric mean distance of
    the ribbon section, 0.2235 (depth + thick). Peak field at the winding: mu0 I / (2 pi a) plus the other coils' field."""
    fil = ron.filaments(v['coils'])
    W = ron.stored_energy(fil, k_cur)
    rows = []
    for c in v['coils']:
        others = ron.filaments([o for o in v['coils'] if o is not c])
        mx, mr = (c['p0'][0] + c['p1'][0]) / 2, (c['p0'][1] + c['p1'][1]) / 2
        br, bx = ron.field(others, mx, mr, k_cur)
        I = c['I'] * k_cur; r = ron.hoop_r(c)
        a = (minor or {}).get(c['name']) or 0.2235 * (c['depth'] + c['thick'])
        B_self = MU0 * abs(I) / (2 * math.pi * a)
        B_peak = math.hypot(br, bx) + B_self
        T_self = MU0 * I * I * (math.log(8 * r / a) - 0.75) / (4 * math.pi)
        T = max(0.0, T_self + I * bx * r)                               # hoop tension, N (the other coils' axial field adds or subtracts)
        A = T / sigma
        Fx = 2 * math.pi * r * I * br                                    # axial force on the coil, N (+ = forward)
        rows.append(dict(name=c['name'], x=round(mx, 2), r=round(r, 2), I_MA=I / 1e6, B_peak_T=B_peak, hoop_MN=T / 1e6,
                         structure_m2=A, structure_t=A * 2 * math.pi * r * 1600 / 1e3, Fx_MN=Fx / 1e6,
                         conductor_t=abs(I) / 1.53e8 * 2 * math.pi * r * 6000 / 1e3,
                         p_mag_MPa=B_peak ** 2 / (2 * MU0) / 1e6))
    area = sum(2 * (c['depth'] + max(0.01, abs(c['I']) * k_cur / 1.53e8 / c['depth'])) * 2 * math.pi * ron.hoop_r(c) for c in v['coils'])
    q_cold = q_static * area
    tau = 2 * W / (I_op * V_dump)
    return dict(label=label, k=k_cur, stored_J=W, B_burn_T=math.hypot(*ron.field(fil, 0.0, 1e-6, k_cur)), coils=rows,
                B_peak_max_T=max(r['B_peak_T'] for r in rows), hoop_total_MN=sum(r['hoop_MN'] for r in rows),
                structure_t=sum(r['structure_t'] for r in rows), conductor_t=sum(r['conductor_t'] for r in rows),
                Fx_net_MN=sum(r['Fx_MN'] for r in rows), Fx_max_MN=max(abs(r['Fx_MN']) for r in rows),
                cryostat_area_m2=area, cold_static_W=q_cold, cryo_power_W=q_cold * cop_20K,
                quench_dump_s=tau, quench_copper_t=W / h_cu / 1e3, dump_I_A=I_op, dump_V=V_dump)


# ---------- ledger -------------------------------------------------------------------------------------------------------------------

def gview(g, picture):
    """The species set engine() reads, for a plasma picture."""
    S = dict(g['species'])
    if picture == 'cavity':
        S['D'], S['He3'] = S['D_cav'], S['He3_cav']
    return dict(species=S)


def h2_bounds(e, m_h):
    """Hydrogen mass m_h per pulse added to the exhaust: inelastic (momentum shared: I unchanged, the kinetic difference becomes heat)
    and ideal elastic (the jet energy kept: I = sqrt(2 (m + m_h) E_jet)). The physical coupling is OPEN."""
    I, m, Ej = e['impulse_Ns'], e['exhaust_mass_kg'], e['jet_J']
    I_el = math.sqrt(2 * (m + m_h) * Ej)
    return dict(m_h_kg=m_h, inelastic=dict(impulse_Ns=I, exhaust_m_s=I / (m + m_h), heat_J=Ej - I * I / (2 * (m + m_h))),
                elastic=dict(impulse_Ns=I_el, exhaust_m_s=I_el / (m + m_h)))


X_VDEB = None


def main():
    global X_VDEB
    t0 = time.time()
    fi = json.loads(X.FI.read_text()); src = json.loads(X.SRC.read_text())
    L = fi['ledger']; nz = L['nozzle']['C1|1']; Hz = L['pulse']['Hz']; budget = nz['budget_W']; pickup = nz['pickup']
    base = next(r for r in src['levers'] if r['lever'] == 'base')
    m_d = base['mass_kg'] - base['fusion_J'] / C ** 2
    Pd = base['fusion_J'] * base['plasma_share']
    X_VDEB = math.sqrt(2 * Pd / m_d)
    k = ron.canon()
    # sky of the drawn engine for the pickup scale
    pd = geometry('drawn|0', 0.0, 1.0); vd, _, _, _ = ron.configure(pd, k)
    sky_ref = sum(ron.sky_axisymmetric(vd['elements'], n=1500).values())
    G = []
    with Pool(4) as pool:
        for cfg in configs():
            G.append(run(pool, k, cfg, Pd, sky_ref))
    # every lever through every geometry, both plasma pictures, the pickup re-traced
    rows = []
    for g in G:
        for pic in ('vacuum', 'cavity'):
            gv = gview(g, pic)
            for r in src['levers']:
                e = X.engine(r, gv, L, pickup * g['pickup_scale'], budget, Hz)
                rows.append(dict(geo=g['key'], picture=pic, lever=r['lever'], label=r['label'], cls=r['cls'], **e))

    def row(geo, pic, lever_label):
        return next(rw for rw in rows if rw['geo'] == geo and rw['picture'] == pic and rw['label'] == lever_label)
    ext80 = next(r for r in src['levers'] if r['label'].startswith('Early extraction: 80'))['label']
    # the research geometry: the owner-approved position (burn about 4 m aft, closure stronger); the refinement scan ranks the rest
    best = next(g for g in G if g['key'] == RESEARCH)
    drawn = G[0]
    # combination: naive product of separate gains vs the computed combination
    d_base = row('drawn|0', 'vacuum', base['label']); d_ext = row('drawn|0', 'vacuum', ext80)
    b_base = row(best['key'], 'vacuum', base['label']); b_ext = row(best['key'], 'vacuum', ext80)
    combo = dict(drawn=dict(base=d_base, ext80=d_ext), best=dict(base=b_base, ext80=b_ext),
                 naive=dict(thrust_N=b_base['thrust_N'], heat_over=d_ext['heat_over'] * b_base['heat_over'] / d_base['heat_over'],
                            note='topology thrust gain and extraction heat gain applied together, as if independent'),
                 computed=dict(thrust_N=b_ext['thrust_N'], heat_over=b_ext['heat_over'], exhaust_m_s=b_ext['exhaust_m_s']),
                 cavity=dict(base=row(best['key'], 'cavity', base['label']), ext80=row(best['key'], 'cavity', ext80)))
    # frontier per picture
    front = {}
    for pic in ('vacuum', 'cavity'):
        f = []
        for rw in sorted((r for r in rows if r['picture'] == pic), key=lambda x: x['heat_over']):
            if not f or rw['thrust_N'] > f[-1]['thrust_N']:
                f.append(rw)
        front[pic] = [dict(geo=r['geo'], label=r['label'], cls=r['cls'], thrust_N=r['thrust_N'], exhaust_m_s=r['exhaust_m_s'],
                           heat_over=r['heat_over'], deposited_kg_s=r['deposited_kg_s']) for r in f[:12]]
    # hydrogen bounds on the best geometry's base and extraction rows: 1x, 3x, 10x the debris mass
    h2 = [dict(case=c, **h2_bounds(rw, f * m_d)) for c, rw in (('base', b_base), ('ext80', b_ext)) for f in (1.0, 3.0, 10.0)]
    # coils: drawn as built (k = 1), drawn at capture, best at capture; and best as built-equivalent (k such that W = 9.7 GJ)
    coils = [coil_engineering(drawn['_v'], 1.0, 'Drawn engine as built (the field the 3D engine carries)'),
             coil_engineering(drawn['_v'], drawn['k'], 'Drawn engine at the capture current'),
             coil_engineering(best['_v'], best['k'], f'Optimised ({best["label"]}) at the capture current')]
    for g in G:
        for kx in ('_v', '_cap', '_src'):
            g.pop(kx, None)
    out = dict(cls='SAMPLED', study='vertex-optimize', source='lab/studies/vertex-compact-engine/vertex-optimize/optimize.py', quick=QUICK,
               n_dir=N_DIR, debris_speed_m_s=X_VDEB, debris_J=Pd, pickup_ref=pickup, sky_ref=sky_ref, geometries=G, rows=rows,
               best=best['key'], combination=combo, frontier=front, hydrogen=h2, coils=coils, runtime_s=time.time() - t0)
    (HERE / 'results').mkdir(exist_ok=True)
    (HERE / 'results' / ('optimize_quick.json' if QUICK else 'optimize.json')).write_text(json.dumps(out, indent=1))
    print(f'done in {time.time() - t0:.0f} s; best {best["key"]}: base {4 * b_base["thrust_N"] / 1e6:.2f} MN heat x{b_base["heat_over"]:.0f}; '
          f'ext80 {4 * b_ext["thrust_N"] / 1e6:.2f} MN heat x{b_ext["heat_over"]:.0f}')


if __name__ == '__main__':
    main()
