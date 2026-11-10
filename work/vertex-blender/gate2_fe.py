"""Parametric frame FE of tank-farm stretch sections (Vertex feasibility gate 2, Task C, T05). NON-CANON, research only.

Run from the project root: python3 work/vertex-blender/gate2_fe.py  ->  work/vertex-blender/gate2_fe.json  (numpy, scipy; minutes)

Same element, material and solver as fe_s5n.py (Euler-Bernoulli 3D frame, rigid joints and saddles, lumped mass, CFRP 120 GPa,
600 MPa at SF 2), on a generated section instead of the drawn V4 one, so a farm radius, stretch length, frame pitch, longeron count
and saddle topology can be varied. Calibration: the generator rebuilt with the V4 S5N parameters is compared with fe_s5n.py's drawn
model (case CAL_V4_*); both are reported.

Two boundary conditions:
  cantilever   J1 frame fixed (the T05 Rev 4 basis; a lower bound)
  free-free    the aft ship (drive, coils, radiators, habitat rings, aft spine) as one rigid body hung on J1 through a stiff link at
               its centroid, with its translational mass and a PROTOTYPE rotary inertia; the physically right condition for a free
               ship, but an upper bound for the aft section, whose own spine flexibility is not modelled.
Screens (not requirements): f1 >= 3x the slosh band top (0.040 Hz -> 0.12 Hz), f1 clear by 15 % of the habitat-ring spin (4 rpm =
0.0667 Hz) and its 2x harmonic (0.133 Hz), and the Rev 4 / T00 target 0.2 Hz.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fe_s5n as FE  # noqa: E402

g0 = 9.80665
GATE = json.loads((HERE/'t00_gate_handoff.json').read_text())
CS = GATE['coupled_ship']['summary']
ST3 = FE.ST3; CASE = FE.CASE
V4_PROP, V4_TANK = ST3['propellant_kg'], ST3['tank_kg']          # V4 stretch: 25.07 kt propellant, 2.39 kt tanks in 275.4 m
V4_FARM_R = 34.5; V4_LON_R = 31.0; PITCH = ST3['bay_pitch_m']; TANK_R = 6.45
SPIN_HZ = 4.0/60.0
SLOSH_BAND = (0.022, 0.040)

# aft ship lumped on J1 (PROTOTYPE positions, ship X): drive -200, radiators -70, habitat/payload +100, other -100; J1 at the stretch root
J1_X = ST3['x_m'][0]
AFT_ITEMS_COUPLED = {'drive': (CS['drive_t'], -200.0), 'radiators': (CS['radiator_t'], -70.0), 'payload_rings': (CS['payload_t'], 100.0)}


def aft_body(departure_t, stretch_t, bow_t, scale_from_coupled=True):
    items = dict(AFT_ITEMS_COUPLED)
    known = sum(m for m, _ in items.values())
    other = max(departure_t-stretch_t-bow_t-known, 0.0)
    items['other'] = (other, -100.0)
    if not scale_from_coupled:
        pass
    m = sum(v[0] for v in items.values())
    if departure_t-stretch_t-bow_t < known:                  # a lighter ship (V4): scale the coupled aft items down to fit
        k = (departure_t-stretch_t-bow_t)/known
        items = {n: (v[0]*k, v[1]) for n, v in items.items() if n != 'other'}; m = sum(v[0] for v in items.values())
    xc = sum(v[0]*v[1] for v in items.values())/m
    I = sum(v[0]*(v[1]-xc)**2 for v in items.values())*1e3      # kg m^2 (t -> kg), about its own centroid, lateral axes
    return {'mass_kg': m*1e3, 'centroid_x_m': xc, 'lever_from_J1_m': J1_X-xc, 'I_lateral_kg_m2': I, 'items_t': {n: v[0] for n, v in items.items()}}


def tank_layout(a, b, n_target):
    """Tank saddle positions per bay: concentric rings between the keel hub and the farm edge (ellipse a x b), count ~ n_target."""
    rings = []
    r = 5.0+TANK_R+0.5
    while r <= min(a, b)-TANK_R+1e-6 or not rings:
        rings.append(r); r += 2*TANK_R+0.6
    circ = [2*math.pi*r for r in rings]; tot = sum(circ)
    out = []
    for r, c in zip(rings, circ):
        k = max(3, int(round(n_target*c/tot)))
        for j in range(k):
            t = 2*math.pi*(j+0.5)/k
            out.append((r*(a/min(a, b))*math.cos(t), r*(b/min(a, b))*math.sin(t)))
    return out


def build(farm_a=V4_FARM_R, farm_b=None, length_m=275.4, prop_kg=V4_PROP, tank_kg=V4_TANK, bow_kg=300e3, n_lon=9,
          lon_r_m=None, lon_tube=None, frame_pitch=PITCH, tie_saddles_to_longerons=False, sec_scale=None, tanks_per_bay=None):
    farm_b = farm_a if farm_b is None else farm_b
    la, lb = (lon_r_m or V4_LON_R*farm_a/V4_FARM_R), (lon_r_m or V4_LON_R*farm_b/V4_FARM_R)
    if lon_r_m and farm_b != farm_a:
        lb = lon_r_m*farm_b/farm_a
    SEC = {k: dict(v) for k, v in FE.SEC.items()}
    if lon_tube:
        SEC['longeron'] = FE.tube(lon_tube[0], lon_tube[0]*lon_tube[1])
    for k, f in (sec_scale or {}).items():
        SEC[k] = {kk: vv*(f if kk in ('A', 'I', 'J') else 1.0) for kk, vv in SEC[k].items()}
    nodes, elems, pm = [], [], {}
    def node(p):
        nodes.append(tuple(p)); return len(nodes)-1
    def el(i, j, kind):
        elems.append((i, j, kind))
    x0 = J1_X; nb = max(1, int(round(length_m/frame_pitch)))
    frames = [x0-1.0+i*length_m/nb for i in range(nb+1)]
    laz = [360.0*(k+0.5)/n_lon for k in range(n_lon)]; kaz = [30.0, 150.0, 270.0]
    ring_az = sorted(set([round(a, 3) for a in laz]+kaz))
    def lon_xy(az):
        t = math.radians(az); return la*math.cos(t), lb*math.sin(t)
    F = []
    for xf in frames:
        f = {'spine': node((xf, 0, 0)), 'kr': {a: node(FE.pol(xf, 5.0, a)) for a in ring_az},
             'lo': {a: node((xf,)+lon_xy(a)) for a in laz}}
        F.append(f)
        for a in kaz:
            el(f['spine'], f['kr'][a], 'hub_spoke')
        for j, a in enumerate(ring_az):
            el(f['kr'][a], f['kr'][ring_az[(j+1) % len(ring_az)]], 'keel_ring')
        for j, a in enumerate(laz):
            el(f['lo'][a], f['lo'][laz[(j+1) % len(laz)]], 'outer_ring'); el(f['kr'][round(a, 3)], f['lo'][a], 'spoke')
    for i in range(len(frames)-1):
        A, B = F[i], F[i+1]; xm = (frames[i]+frames[i+1])/2
        m = node((xm, 0, 0)); el(A['spine'], m, 'spine'); el(m, B['spine'], 'spine')
        for a in kaz:
            m = node(FE.pol(xm, 5.0, a)); el(A['kr'][a], m, 'keel'); el(m, B['kr'][a], 'keel')
        for a in laz:
            m = node((xm,)+lon_xy(a)); el(A['lo'][a], m, 'longeron'); el(m, B['lo'][a], 'longeron')
            if i % 2 == 0:
                el(A['lo'][a], B['kr'][round(a, 3)], 'lacing')
            else:
                el(B['lo'][a], A['kr'][round(a, 3)], 'lacing')
    # tanks: one vessel per bay slot between the two frames that bound its bay (drawn V4 tanks span a 30.6 m bay)
    nbay_tanks = max(1, int(round(length_m/PITCH)))
    per_bay = tanks_per_bay or max(3, int(round(110/9*((farm_a*farm_b)-25)/(V4_FARM_R**2-25))))
    slots = tank_layout(farm_a, farm_b, per_bay)
    mv = (prop_kg+tank_kg)/(nbay_tanks*len(slots))
    for ib in range(nbay_tanks):
        xa, xb = x0-1.0+ib*length_m/nbay_tanks, x0-1.0+(ib+1)*length_m/nbay_tanks
        fa = min(range(len(frames)), key=lambda k: abs(frames[k]-xa)); fb = min(range(len(frames)), key=lambda k: abs(frames[k]-xb))
        if fb == fa:
            fb = min(fa+1, len(frames)-1)
        for (y, z) in slots:
            az = math.degrees(math.atan2(z, y)) % 360
            ka = min(ring_az, key=lambda a: abs(((a-az)+180) % 360-180))
            pa = node((frames[fa], y, z)); pb = node((frames[fb], y, z))
            el(pa, pb, 'vessel'); el(F[fa]['kr'][ka], pa, 'girder'); el(F[fb]['kr'][ka], pb, 'girder')
            if tie_saddles_to_longerons:                  # saddle shear tie to the nearest longeron node (a deep frame / shear wall)
                lo = min(laz, key=lambda a: abs(((a-az)+180) % 360-180))
                el(F[fa]['lo'][lo], pa, 'girder'); el(F[fb]['lo'][lo], pb, 'girder')
            pm[pa] = pm.get(pa, 0)+mv/2; pm[pb] = pm.get(pb, 0)+mv/2
    tips = [F[-1]['spine']]+list(F[-1]['lo'].values())
    for n_ in tips:
        pm[n_] = pm.get(n_, 0)+bow_kg/len(tips)
    return np.array(nodes), elems, pm, F, frames, SEC, len(slots)*nbay_tanks


def _assemble(nodes, elems, pm, SEC):
    old = FE.SEC; FE.SEC = SEC
    try:
        return FE.assemble(nodes, elems, pm)
    finally:
        FE.SEC = old


def bending(freqs, vecs, free, nodes, mdiag, tn, thresh=0.2):
    n = len(nodes)
    for i, f in enumerate(freqs):
        if f < 1e-3:
            continue
        c = FE.classify(vecs[:, i], free, nodes, n, mdiag, tn)
        if max(c['eff_mass_frac_y'], c['eff_mass_frac_z']) >= thresh:
            return float(f), c
    return None, None


def run(name, aft=None, k=24, **kw):
    nodes, elems, pm, F, frames, SEC, ntank = build(**kw)
    K, mdiag, mm = _assemble(nodes, elems, pm, SEC)
    root = [F[0]['spine']]+list(F[0]['kr'].values())+list(F[0]['lo'].values())
    fixed = np.array([6*r_+d for r_ in root for d in range(6)])
    tn = set(pm)
    fc, vc, frc = FE.modes(K, mdiag, fixed, k=k)
    bc, cc = bending(fc, vc, frc, nodes, mdiag, tn)
    out = {'case': name, 'nodes': len(nodes), 'elements': len(elems), 'tanks': ntank, 'structure_t': sum(mm.values())/1e3,
           'member_t': {k_: v/1e3 for k_, v in mm.items()}, 'stretch_mass_t': (sum(pm.values()))/1e3,
           'cantilever_Hz': [round(float(f), 4) for f in fc[:10]], 'cantilever_first_bending_Hz': bc,
           'cantilever_lowest_Hz': float(fc[0])}
    if aft:
        # aft body: one node at its centroid, stiff links to every J1 root node, its mass and rotary inertia lumped there
        import scipy.sparse as sp
        nodes2 = np.vstack([nodes, [[aft['centroid_x_m'], 0.0, 0.0]]]); ia = len(nodes2)-1
        link = FE.tube(3.0, 0.3)
        elems2 = list(elems)+[(ia, r_, 'aft_link') for r_ in root]
        SEC2 = dict(SEC); SEC2['aft_link'] = {kk: vv*50 if kk in ('A', 'I', 'J') else vv for kk, vv in link.items()}
        K2, md2, _ = _assemble(nodes2, elems2, pm, SEC2)
        # remove link self-mass, add the aft body
        Lk = abs(aft['lever_from_J1_m'])
        mlink = FE.RHO*SEC2['aft_link']['A']*Lk*len(root)
        md2[6*ia:6*ia+3] += aft['mass_kg']-mlink/2; md2[6*ia+3:6*ia+6] += aft['I_lateral_kg_m2']
        for r_ in root:
            md2[6*r_:6*r_+3] -= FE.RHO*SEC2['aft_link']['A']*Lk/2
        md2 = np.clip(md2, 1e-3, None)
        ff, vf, frf = FE.modes(K2, md2, np.array([], dtype=int), k=k+6)
        flex = [(float(f), i) for i, f in enumerate(ff) if f > 1e-3]
        bf, cf = bending([f for f, _ in flex], vf[:, [i for _, i in flex]], frf, nodes2, md2, tn | {ia}, thresh=0.0)
        # first flexible mode with lateral kinetic energy dominant
        first_lat = None; ff_modes = []
        for f, i in flex[:12]:
            c = FE.classify(vf[:, i], frf, nodes2, len(nodes2), md2, tn)
            full = np.zeros(6*len(nodes2)); full[frf] = vf[:, i]; u = full.reshape(-1, 6)[:, :3]; m = md2.reshape(-1, 6)[:, :3]
            ke = (m*u**2); tot = ke.sum()
            aft_share = float(ke[ia].sum()/tot)
            # lateral KE share of the stretch's own structure nodes (not tanks, not the aft body): global frame bending vs tank swing
            lat = float((ke[:, 1]+ke[:, 2]).sum()/tot)
            ff_modes.append({'Hz': round(f, 4), 'aft_body_ke_share': round(aft_share, 4), 'lateral_ke_share': round(lat, 3),
                             'tank_node_ke_share': round(c['tank_node_ke_share'], 3), 'ke_x': round(c['ke_x'], 3)})
            if first_lat is None and lat > 0.5 and aft_share >= 0.01:
                first_lat = (f, c)
        out.update({'aft_body': aft, 'free_free_flexible_Hz': [round(f, 4) for f, _ in flex[:10]],
                    'free_free_first_global_bending_Hz': first_lat[0] if first_lat else None, 'free_free_first_lateral_Hz': first_lat[0] if first_lat else None, 'free_free_modes': ff_modes,
                    'free_free_lowest_flexible_Hz': flex[0][0] if flex else None})
    f_screen = out.get('free_free_first_lateral_Hz') or out['cantilever_first_bending_Hz']
    low = min(out['cantilever_lowest_Hz'], out.get('free_free_lowest_flexible_Hz') or 9)
    out['screens'] = {
        'basis_Hz': f_screen,
        'above_3x_slosh_0p12': bool(f_screen and f_screen >= 3*SLOSH_BAND[1]),
        'clear_of_spin_1x_2x': bool(f_screen and all(abs(f_screen-h)/h > 0.15 for h in (SPIN_HZ, 2*SPIN_HZ))),
        'meets_0p2': bool(f_screen and f_screen >= 0.2),
        'lowest_mode_Hz': low, 'lowest_mode_in_slosh_band': bool(SLOSH_BAND[0]*0.85 <= low <= SLOSH_BAND[1]*1.15),
        'lowest_mode_near_spin': bool(abs(low-SPIN_HZ)/SPIN_HZ < 0.15)}
    return out


def variants():
    # lam (T00): whole-ship propellant ratio coupled / Rev 4 = (57.0/34.5)^2 = 2.728; stretch propellant and tanks scale with it
    lam = (GATE['coupled_ship']['spine']['shield']['farm_radius_m']/V4_FARM_R)**2
    P, T = V4_PROP*lam, V4_TANK*lam
    L_of = lambda R: 275.4*lam/((R/V4_FARM_R)**2)
    return lam, P, T, L_of


def main():
    lam, P, T, L_of = variants()
    dep_c = CS['departure_t']
    aft_c = lambda L, R: aft_body(dep_c, (P+T)/1e3, 300.0)
    aft_v4 = aft_body(42.9e3, (V4_PROP+V4_TANK)/1e3, 300.0)
    cases = []
    # calibration: the generator with the drawn V4 S5N parameters vs fe_s5n.py's drawn model
    cases.append(run('CAL_V4_generator_full', aft=aft_v4, lon_tube=(CASE['tube_r_m'], CASE['t_over_r'])))
    plan = [
        ('F0_V4_farm_r34.5_275m_V4_mass', dict(farm_a=34.5, length_m=275.4, prop_kg=V4_PROP, tank_kg=V4_TANK), aft_v4),
        ('F1_wide_r57_275m_coupled', dict(farm_a=57.0, length_m=275.4, prop_kg=P, tank_kg=T), aft_c(275.4, 57)),
        ('F2_r41.7_%.0fm_coupled_7.5deg' % L_of(41.7), dict(farm_a=41.7, length_m=L_of(41.7), prop_kg=P, tank_kg=T), aft_c(0, 0)),
        ('F2x_r44_%.0fm_coupled_dust_limit' % L_of(44), dict(farm_a=44.0, length_m=L_of(44), prop_kg=P, tank_kg=T), aft_c(0, 0)),
        ('F3_long_r34.5_%.0fm_coupled' % L_of(34.5), dict(farm_a=34.5, length_m=L_of(34.5), prop_kg=P, tank_kg=T), aft_c(L_of(34.5), 34.5)),
        ('F5_ellipse_44x73.8_275m_coupled', dict(farm_a=73.8, farm_b=44.0, length_m=275.4, prop_kg=P, tank_kg=T), aft_c(275.4, 57)),
    ]
    for name, kw, aft in plan:
        cases.append(run(name, aft=aft, lon_tube=(CASE['tube_r_m'], CASE['t_over_r']), **kw))
    # frame-geometry levers on F2 (r 41.7 m: inside the r 45 dust shield and FDP-1's 7.5 deg rim rule with the farm end at X 109.25)
    base = dict(farm_a=41.7, length_m=L_of(41.7), prop_kg=P, tank_kg=T, lon_tube=(CASE['tube_r_m'], CASE['t_over_r']))
    levers = [
        ('F2a_frames_every_7.65m', dict(frame_pitch=7.65)),
        ('F2b_saddles_tied_to_longerons', dict(tie_saddles_to_longerons=True)),
        ('F2c_tied_+_7.65m_frames', dict(tie_saddles_to_longerons=True, frame_pitch=7.65)),
        ('F2d_tied_+_7.65m_+_rings_spokes_x4', dict(tie_saddles_to_longerons=True, frame_pitch=7.65,
                                                    sec_scale={'keel_ring': 4, 'spoke': 4, 'hub_spoke': 4, 'outer_ring': 4})),
        ('F2e_tied_+_7.65m_+_18_longerons_r0.8', dict(tie_saddles_to_longerons=True, frame_pitch=7.65, n_lon=18, lon_tube=(0.8, 0.1))),
        ('F2x_tied_r44_462m', dict(tie_saddles_to_longerons=True, farm_a=44.0, length_m=L_of(44))),
        ('F2x_tied_r44_462m_+_18_longerons_r0.8', dict(tie_saddles_to_longerons=True, farm_a=44.0, length_m=L_of(44), n_lon=18, lon_tube=(0.8, 0.1))),
        ('F2f_tied_+_18_longerons_r0.8', dict(tie_saddles_to_longerons=True, n_lon=18, lon_tube=(0.8, 0.1))),
        ('F2g_tied_+_9_longerons_r1.2', dict(tie_saddles_to_longerons=True, lon_tube=(1.2, 0.1))),
        ('F2h_tied_+_18_longerons_r1.0', dict(tie_saddles_to_longerons=True, n_lon=18, lon_tube=(1.0, 0.1))),
        ('F2i_tied_+_18_longerons_r1.2', dict(tie_saddles_to_longerons=True, n_lon=18, lon_tube=(1.2, 0.1))),
    ]
    for name, kw in levers:
        k2 = dict(base); k2.update(kw)
        cases.append(run(name, aft=aft_c(0, 0), **k2))
    ref = json.loads((HERE/'fe_s5n.json').read_text())['cases'][0]
    out = {'study': 'parametric stretch frame FE (Vertex gate 2, Task C, T05)', 'status': 'MODEL, research only, NON-CANON',
           'method': 'fe_s5n.py elements on a generated section; cantilever (J1 fixed) and free-free with the aft ship as a rigid body on J1',
           'calibration': {'fe_s5n_drawn_V4_cantilever_first_bending_Hz': ref['cantilever_first_bending_Hz'],
                           'generator_V4_cantilever_first_bending_Hz': cases[0]['cantilever_first_bending_Hz']},
           'scaling': {'lam_propellant_coupled_over_rev4': lam, 'stretch_propellant_t': P/1e3, 'stretch_tank_t': T/1e3,
                       'length_by_farm_radius_m': {str(R): L_of(R) for R in (34.5, 41.7, 44.0, 57.0)}},
           'screens': {'slosh_band_Hz': SLOSH_BAND, 'ring_spin_Hz': SPIN_HZ, 'f1_min_3x_slosh_Hz': 3*SLOSH_BAND[1], 'target_Hz': 0.2},
           'cases': cases}
    (HERE/'gate2_fe.json').write_text(json.dumps(out, indent=1, default=float))
    for c in cases:
        print('%-42s struct %6.0f t tanks %4d  cant bend %s low %.4f | ff lat %s low %s | %s' % (
            c['case'], c['structure_t'], c['tanks'], c['cantilever_first_bending_Hz'] and round(c['cantilever_first_bending_Hz'], 4),
            c['cantilever_lowest_Hz'], c.get('free_free_first_lateral_Hz') and round(c['free_free_first_lateral_Hz'], 4),
            c.get('free_free_lowest_flexible_Hz') and round(c['free_free_lowest_flexible_Hz'], 4),
            {k: v for k, v in c['screens'].items() if isinstance(v, bool) and v}))


if __name__ == '__main__':
    main()
