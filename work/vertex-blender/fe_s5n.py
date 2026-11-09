"""S5N stretch structure as a 3D frame finite-element model (feasibility gate, Phase 5).

Run from the project root: python3 work/vertex-blender/fe_s5n.py  ->  work/vertex-blender/fe_s5n.json
Needs numpy and scipy. NON-CANON, research only.

What it is: Euler-Bernoulli 3D frame elements (12 DOF) for every drawn S5N member class (spine, three sector keels, nine nested
longerons, gap-plane lacing, keel rings, outer rings, spokes, hub spokes, tank girders) plus each tank as a stiff beam between its
polar-boss saddles with half its mass at each boss, the 300 t PROTOTYPE bow mass at the J3 frame, and J1 as the root. It is a frame FE
model, not a shell or joint FE: joints are rigid, saddles are rigid (T00's 10-30 Hz isolation sits far above the modes of interest),
buckling is member Euler buckling between frames only. CFRP as in FDP-1: E 120 GPa, G 46 GPa, 1,700 kg/m3, 600 MPa, safety factor 2.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as sla

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parents[1]/'lab/variants/vertex-drive'), str(HERE.parents[1]/'lab/variants/fdp1')]
import screen  # noqa: E402

E, G, RHO, SIG, SF = 120e9, 46e9, 1700.0, 600e6, 2.0
g0 = 9.80665
REV3 = json.loads((HERE/'rev3.json').read_text()); REV4 = json.loads((HERE/'rev4.json').read_text())
ST3 = REV3['stretch']; CASE = REV4['structure']['cases']['S5_N9_T00']
KEEL = REV3['options_operational']['S2_CANON_SECTORS']['keel']
x0, x1 = ST3['x_m']; PITCH = ST3['bay_pitch_m']
RS_SPINE, T_SPINE = 0.95, 0.006                    # canon spine continuation as drawn (r 0.95 m, 6 mm wall)


def tube(r, t):
    A = 2*math.pi*r*t; I = math.pi*r**3*t
    return {'A': A, 'I': I, 'J': 2*I, 'r': r, 't': t}


SEC = {
    'spine': tube(RS_SPINE, T_SPINE), 'keel': tube(KEEL['r_m'], KEEL['t_m']),
    'longeron': tube(CASE['tube_r_m'], CASE['tube_r_m']*CASE['t_over_r']),
    'lacing': tube(math.sqrt(0.25*CASE['area_m2_each']/(2*math.pi*CASE['t_over_r'])), math.sqrt(0.25*CASE['area_m2_each']/(2*math.pi*CASE['t_over_r']))*CASE['t_over_r']),
    'keel_ring': tube(0.3, 0.03), 'outer_ring': tube(0.32, 0.032), 'spoke': tube(0.2, 0.02), 'hub_spoke': tube(0.2, 0.02), 'girder': dict(tube(0.22, 0.022), I=2*tube(0.22, 0.022)['A']*0.9**2, J=2*2*tube(0.22, 0.022)['A']*0.9**2),   # drawn: two-chord girder 1.8 m deep
    'vessel': tube(6.45, 0.02),                    # tank shell as a stiff beam between its saddles (PROTOTYPE wall)
}


def pol(x, r, az):
    t = math.radians(az)
    return (x, r*math.cos(t), r*math.sin(t))


def build(mass_scale_prop=1.0, mass_scale_tank=1.0, bow_kg=None):
    nodes, elems, pm = [], [], {}
    def node(p):
        nodes.append(tuple(p)); return len(nodes)-1
    def el(a, b, kind):
        elems.append((a, b, kind))
    frames = []; x = x0-1.0
    while x <= x1+0.1:
        frames.append(x); x += PITCH
    rl = CASE['longeron_r_m']; laz = CASE['longeron_az_deg']; kaz = [30.0, 150.0, 270.0]
    ring_az = sorted(set([round(a, 3) for a in laz]+kaz))
    F = []
    for i, xf in enumerate(frames):
        f = {'spine': node((xf, 0, 0)), 'kr': {a: node(pol(xf, 5.0, a)) for a in ring_az}, 'lo': {a: node(pol(xf, rl, a)) for a in laz}}
        F.append(f)
        for a in kaz:
            el(f['spine'], f['kr'][a], 'hub_spoke')
        for j, a in enumerate(ring_az):
            el(f['kr'][a], f['kr'][ring_az[(j+1) % len(ring_az)]], 'keel_ring')
        for j, a in enumerate(laz):
            el(f['lo'][a], f['lo'][laz[(j+1) % len(laz)]], 'outer_ring'); el(f['kr'][round(a, 3)], f['lo'][a], 'spoke')
    for i in range(len(frames)-1):                 # continuous members, two elements per bay (mid nodes)
        A, B = F[i], F[i+1]; xm = (frames[i]+frames[i+1])/2
        m = node((xm, 0, 0)); el(A['spine'], m, 'spine'); el(m, B['spine'], 'spine')
        for a in kaz:
            m = node(pol(xm, 5.0, a)); el(A['kr'][a], m, 'keel'); el(m, B['kr'][a], 'keel')
        for a in laz:
            m = node(pol(xm, rl, a)); el(A['lo'][a], m, 'longeron'); el(m, B['lo'][a], 'longeron')
            if i % 2 == 0:
                el(A['lo'][a], B['kr'][round(a, 3)], 'lacing')
            else:
                el(B['lo'][a], A['kr'][round(a, 3)], 'lacing')
    # tanks: vessel beam between saddles at the frames nearest its ends, half mass at each boss, girders to the keel ring
    R = screen.solve('V4'); vessels = R['tanks']['options']['T-B']['vessels']
    tot = ST3['propellant_kg']*mass_scale_prop+ST3['tank_kg']*mass_scale_tank
    vol = sum(v['liquid_m3'] for v in vessels)
    for v in vessels:
        mv = tot*v['liquid_m3']/vol
        az = math.degrees(math.atan2(v['z'], v['y'])) % 360
        fa = min(range(len(frames)), key=lambda k: abs(frames[k]-v['x0'])); fb = min(range(len(frames)), key=lambda k: abs(frames[k]-v['x1']))
        ka = min(ring_az, key=lambda a: abs(((a-az)+180) % 360-180))
        pa = node((frames[fa], v['y'], v['z'])); pb = node((frames[fb], v['y'], v['z']))
        el(pa, pb, 'vessel'); el(F[fa]['kr'][ka], pa, 'girder'); el(F[fb]['kr'][ka], pb, 'girder')
        pm[pa] = pm.get(pa, 0)+mv/2; pm[pb] = pm.get(pb, 0)+mv/2
    bow = ST3['bow_kg_PROTOTYPE'] if bow_kg is None else bow_kg
    last = F[-1]; tips = [last['spine']]+list(last['lo'].values())
    for n in tips:
        pm[n] = pm.get(n, 0)+bow/len(tips)
    return np.array(nodes), elems, pm, F, frames


def k_local(L, s):
    A, I, J = s['A'], s['I'], s['J']; k = np.zeros((12, 12))
    def put(i, j, v):
        k[i, j] += v
    ea = E*A/L; gj = G*J/L
    for (a, b, v) in ((0, 0, ea), (0, 6, -ea), (6, 6, ea), (3, 3, gj), (3, 9, -gj), (9, 9, gj)):
        put(a, b, v)
    for (u, th, sg) in ((1, 5, 1), (2, 4, -1)):     # bending in local y (rot z) and local z (rot y)
        c = E*I
        put(u, u, 12*c/L**3); put(u, th, sg*6*c/L**2); put(u, u+6, -12*c/L**3); put(u, th+6, sg*6*c/L**2)
        put(th, th, 4*c/L); put(th, u+6, -sg*6*c/L**2); put(th, th+6, 2*c/L)
        put(u+6, u+6, 12*c/L**3); put(u+6, th+6, -sg*6*c/L**2)
        put(th+6, th+6, 4*c/L)
    return np.triu(k)+np.triu(k, 1).T


def rot(p, q):
    ex = (q-p)/np.linalg.norm(q-p); ref = np.array([0, 0, 1.0]) if abs(ex[2]) < 0.9 else np.array([0, 1.0, 0])
    ey = np.cross(ref, ex); ey /= np.linalg.norm(ey); ez = np.cross(ex, ey)
    r3 = np.vstack([ex, ey, ez]); T = np.zeros((12, 12))
    for b in range(4):
        T[3*b:3*b+3, 3*b:3*b+3] = r3
    return T


def assemble(nodes, elems, pm):
    n = len(nodes); rows, cols, vals = [], [], []; mdiag = np.zeros(6*n); member_mass = {}
    for a, b, kind in elems:
        s = SEC[kind]; p, q = nodes[a], nodes[b]; L = float(np.linalg.norm(q-p)); T = rot(p, q)
        kg = T.T @ k_local(L, s) @ T; dofs = list(range(6*a, 6*a+6))+list(range(6*b, 6*b+6))
        for i in range(12):
            for j in range(12):
                if kg[i, j] != 0.0:
                    rows.append(dofs[i]); cols.append(dofs[j]); vals.append(kg[i, j])
        m = (RHO*s['A']*L) if kind != 'vessel' else 0.0                     # vessel shell mass is in the tank mass
        member_mass[kind] = member_mass.get(kind, 0.0)+m
        for nd in (a, b):
            mdiag[6*nd:6*nd+3] += m/2; mdiag[6*nd+3:6*nd+6] += m/2*L**2/12.0+1e-3
    for nd, m in pm.items():
        mdiag[6*nd:6*nd+3] += m; mdiag[6*nd+3:6*nd+6] += 1e-3
    K = sp.coo_matrix((vals, (rows, cols)), shape=(6*n, 6*n)).tocsc()
    return K, mdiag, member_mass


def modes(K, mdiag, fixed, k=8):
    free = np.setdiff1d(np.arange(K.shape[0]), fixed)
    Kf = K[free][:, free]; Mf = sp.diags(mdiag[free])
    w2, v = sla.eigsh(Kf, k=k, M=Mf, sigma=-1e-4, which='LM')
    o = np.argsort(w2); w2 = w2[o]; v = v[:, o]
    return np.sqrt(np.clip(w2, 0, None))/(2*math.pi), v, free


def classify(vec, free, nodes, n, mdiag=None, tank_nodes=()):
    full = np.zeros(6*n); full[free] = vec; u = full.reshape(n, 6)[:, :3]; m = mdiag.reshape(n, 6)[:, :3]
    ke = (m*u**2); tot = ke.sum()+1e-30; tk = ke[list(tank_nodes)].sum()/tot if tank_nodes else 0.0
    gam = [(m[:, d]*u[:, d]).sum() for d in range(3)]; mt = m[:, 0].sum()
    meff = [g_**2/((m*u**2).sum())/mt for g_ in gam]
    return {'ke_x': ke[:, 0].sum()/tot, 'ke_y': ke[:, 1].sum()/tot, 'ke_z': ke[:, 2].sum()/tot, 'tank_node_ke_share': tk,
            'eff_mass_frac_x': meff[0], 'eff_mass_frac_y': meff[1], 'eff_mass_frac_z': meff[2]}


def static(K, mdiag, fixed, nodes, elems, acc):
    n = len(nodes); f = np.zeros(6*n)
    for d in range(3):
        f[d::6] = mdiag[d::6]*acc[d]
    free = np.setdiff1d(np.arange(6*n), fixed)
    u = np.zeros(6*n); u[free] = sla.spsolve(K[free][:, free], f[free])
    react = (K @ u)-f
    out = {}
    for a, b, kind in elems:
        p, q = nodes[a], nodes[b]; L = float(np.linalg.norm(q-p)); T = rot(p, q)
        ue = np.concatenate([u[6*a:6*a+6], u[6*b:6*b+6]]); fl = k_local(L, SEC[kind]) @ (T @ ue)
        N = -fl[0]; My, Mz = fl[4], fl[5]; My2, Mz2 = fl[10], fl[11]
        s = SEC[kind]; M = max(math.hypot(My, Mz), math.hypot(My2, Mz2)); sig = abs(N)/s['A']+M*s['r']/s['I']
        Pcr = math.pi**2*E*s['I']/L**2
        r = out.setdefault(kind, {'max_stress_MPa': 0.0, 'max_compression_N': 0.0, 'min_buckling_ratio': 1e9})
        r['max_stress_MPa'] = max(r['max_stress_MPa'], sig/1e6)
        if N < 0:
            r['max_compression_N'] = max(r['max_compression_N'], -N); r['min_buckling_ratio'] = min(r['min_buckling_ratio'], Pcr/(-N))
    return u, react, out


def run(name, **kw):
    nodes, elems, pm, F, frames = build(**kw); n = len(nodes)
    K, mdiag, mm = assemble(nodes, elems, pm)
    root = [F[0]['spine']]+list(F[0]['kr'].values())+list(F[0]['lo'].values())
    fixed = np.array([6*r_+d for r_ in root for d in range(6)])
    tn = set(pm)
    f_c, v_c, free_c = modes(K, mdiag, fixed, k=40)
    f_ff, v_ff, free_ff = modes(K, mdiag, np.array([], dtype=int), k=46)
    ffm = [(f, classify(v_ff[:, i], free_ff, nodes, n, mdiag, tn)) for i, f in enumerate(f_ff) if f > 1e-3]
    cm = [(f, classify(v_c[:, i], free_c, nodes, n, mdiag, tn)) for i, f in enumerate(f_c)]
    # global bending: the first cantilever mode with >= 20 % effective lateral mass; local modes: tank masses swinging on the frames
    first_bend_c = next((f for f, c in cm if max(c['eff_mass_frac_y'], c['eff_mass_frac_z']) >= 0.2), None)
    first_bend_ff = next((f for f, c in ffm if c['tank_node_ke_share'] < 0.97 and c['ke_y']+c['ke_z'] > 0.5), None)
    local = [f for f, c in cm if max(c['eff_mass_frac_y'], c['eff_mass_frac_z']) < 0.05]
    total_mass = mdiag[0::6].sum()
    acc_ax = 3.75e6/total_mass                         # axial design load at J1 (rev3 joints: 3.75 MN) as a body acceleration
    _, rea_l, mem_l = static(K, mdiag, fixed, nodes, elems, (0.0, 0.01*g0, 0.0))
    _, rea_a, mem_a = static(K, mdiag, fixed, nodes, elems, (-acc_ax, 0.0, 0.0))
    rp = np.array([nodes[r_] for r_ in root]); Fy = np.array([rea_l[6*r_+1] for r_ in root]); Mz_root = float(np.sum(-(rp[:, 0]-rp[0, 0])*Fy*0)+0)
    # root bending moment from the lateral load: sum of applied forces x lever arm to the root frame
    lever = nodes[:, 0]-nodes[root[0], 0]; M_root = float(np.sum(mdiag[1::6]*0.01*g0*lever))
    combo = {k: {'max_stress_MPa': mem_l[k]['max_stress_MPa']+mem_a[k]['max_stress_MPa'],
                 'utilisation_vs_300MPa': (mem_l[k]['max_stress_MPa']+mem_a[k]['max_stress_MPa'])/(SIG/SF/1e6),
                 'min_buckling_ratio_axial_case': mem_a[k]['min_buckling_ratio']} for k in mem_l}
    return {'case': name, 'nodes': n, 'elements': len(elems), 'structure_kg': sum(mm.values()), 'member_kg': mm,
            'tank_and_bow_kg': sum(pm.values()), 'total_kg': float(total_mass),
            'cantilever_Hz': [round(float(f), 4) for f, _ in cm][:12], 'cantilever_first_bending_Hz': first_bend_c,
            'cantilever_modes': [{'Hz': round(float(f), 4), **{k_: round(float(v_), 3) for k_, v_ in c.items()}} for f, c in cm[:16]],
            'local_modes_below_first_bending': len([f for f in local if first_bend_c and f < first_bend_c]),
            'free_free_Hz': [round(float(f), 4) for f, _ in ffm[:8]], 'free_free_first_bending_Hz': first_bend_ff,
            'root_moment_0p01g_MN_m': M_root/1e6, 'axial_design_N': 3.75e6, 'members_combined_0p01g_lateral_plus_axial': combo}


def main():
    out = {'study': 'S5N frame FE (feasibility gate Phase 5, T05)', 'status': 'MODEL, research only, NON-CANON',
           'method': 'Euler-Bernoulli 3D frame FE, rigid joints and saddles, lumped mass; NOT shell or joint FE',
           'beam_model_reference': {'f1_cantilever_Hz': CASE['f1_full_Hz'], 'f1_free_free_Hz': CASE['f1_free_free_Hz'], 'structure_kg': CASE['structure_kg'],
                                    'J1_moment_0p01g_MN_m': CASE['joints']['J1']['moment_0.01g_MN_m']},
           'sections': SEC, 'cases': []}
    out['cases'].append(run('V4_full_tanks'))
    out['cases'].append(run('V4_dry_tanks', mass_scale_prop=0.0))
    # coupled propellant (T00 gate 117 kt case: 74.0 kt propellant, 6.94 kt tanks) loaded onto the V4 S5N geometry: does 2 kt still suffice?
    gate = json.loads((HERE/'t00_gate_handoff.json').read_text())['coupled_ship']['summary']
    out['cases'].append(run('coupled_117kt_mass_on_V4_geometry', mass_scale_prop=gate['propellant_t']*1e3/ST3['propellant_kg'],
                            mass_scale_tank=gate['tank_t']*1e3/ST3['tank_kg']))
    # sensitivity (V4 full tanks): which members govern the gap to the beam model's 0.2 Hz
    base = {k: dict(v) for k, v in SEC.items()}
    for label, scl in (('rings_spokes_x4_area', {'keel_ring': 4, 'spoke': 4, 'hub_spoke': 4, 'outer_ring': 4}),
                       ('lacing_x4_area', {'lacing': 4}), ('longerons_x2_area', {'longeron': 2}),
                       ('rings_spokes_lacing_x4', {'keel_ring': 4, 'spoke': 4, 'hub_spoke': 4, 'outer_ring': 4, 'lacing': 4})):
        for k, f in scl.items():
            SEC[k] = {kk: vv*(f if kk in ('A', 'I', 'J') else 1.0) for kk, vv in base[k].items()}
        c = run('sensitivity_'+label); c['scaled_sections'] = scl
        out['cases'].append({k: c[k] for k in ('case', 'scaled_sections', 'structure_kg', 'cantilever_first_bending_Hz', 'free_free_first_bending_Hz', 'cantilever_Hz')})
        SEC.update({k: dict(v) for k, v in base.items()})
    (HERE/'fe_s5n.json').write_text(json.dumps(out, indent=1, default=float))
    for c in out['cases']:
        if c['case'].startswith('sensitivity'):
            print(c['case'], '%.0f t' % (c['structure_kg']/1e3), 'bend', c['cantilever_first_bending_Hz'], c['cantilever_Hz'][:3]); continue
        print(c['case'], 'struct %.0f t' % (c['structure_kg']/1e3), 'total %.1f kt' % (c['total_kg']/1e6), 'cant', c['cantilever_Hz'][:4], 'ff', c['free_free_Hz'][:4],
              'bend c/ff', c['cantilever_first_bending_Hz'], c['free_free_first_bending_Hz'], 'Mroot %.0f MN m' % c['root_moment_0p01g_MN_m'])
        for k, v in c['members_combined_0p01g_lateral_plus_axial'].items():
            print('   ', k, {kk: round(vv, 3) for kk, vv in v.items()})


if __name__ == '__main__':
    main()
