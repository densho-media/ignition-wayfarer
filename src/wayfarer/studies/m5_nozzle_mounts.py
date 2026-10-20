"""M5 NOZ-2: the axial bipod thrust frame for all four nozzles, the thrust-ring screen and REBCO re-entrant coil mounts (owner
2026-10-18, S&E 15!A214 OWN-NOZ-Q1 / 15!A215 OWN-NOZ-Q2, 98!A118). L2 PREFERRED STUDY / OD-024 OD-025 HOLD: the vehicle and the
as-built pickups stay unchanged; nothing here is a primary load rating, a qualified coil temperature or a final bore.

Function: (1) carry each nozzle's coil reaction into the thrust ring along the axis (two bipods per nozzle, WF_STUDY_DRIVE_SUPPORT
struts) and compare forces, member mass and the ring loads with the as-built pickup, over the four-nozzle manifold and its failure
cases; (2) give the coils room to be thermally isolated: re-entrant supports with an 80 K intercept in a larger yoke standoff, the
20-30 K REBCO-class research envelope, and the throat-coil bore that the >= 0.05 m clearance needs. Fixed: the built nozzles, coils,
yokes, pickups and thrust ring (drive_manifold, structure), the 7.355 MN per-nozzle STRUCTURAL PROOF load (15!A214: not operating
thrust), the +-5 deg rig vector limit, the slice 4 bipod geometry and screens (m5_drive_support). Unknown (OPEN): coil current, field,
quench margin, nuclear and radiative heat loads, the force split between coil stations, the ring material and its sharing with the
hub webs and keels, FEA (15!A214/A215 H). Design freedom (PROTOTYPE, this file): load cases, the intercept temperature, the standoff
increase, the material approximations.

    python3 src/wayfarer/studies/m5_nozzle_mounts.py                     # screens -> references/m5_nozzle_mounts.json
    /snap/bin/blender -b --factory-startup --python-exit-code 1 --python src/wayfarer/studies/m5_nozzle_mounts.py -- --asset   # + variant
        mount asset assets/wayfarer/studies/WF_STUDY_NOZZLE_MOUNTS.blend and its overlap screen against the vehicle and the slice 4 study
"""
from pathlib import Path
import argparse
import json
import math
import sys
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/build'), str(ROOT/'src/wayfarer/studies'), str(ROOT/'src/wayfarer/shots')]
import drive_manifold as dm
import m5_drive_support as ds

OUT_JSON = ROOT/'references/m5_nozzle_mounts.json'
ASSET = ROOT/'assets/wayfarer/studies/WF_STUDY_NOZZLE_MOUNTS.blend'
COLLECTION = 'WF_STUDY_NOZZLE_MOUNTS'

# PROTOTYPE judgment (this file).
VECTOR_DEG = 5.0              # rig vector limit (+-5 deg), used as a lateral load case only (no vector authority is assumed)
RHO_TI = 4430.0               # kg/m3, Ti-6Al-4V
STANDOFF_ADD = 0.20           # m: yoke moved out so a 0.40 m re-entrant support folds into the gap (two 0.20 m legs)
INTERCEPT_K = 80.0            # thermal intercept on the re-entrant support (LN2-class stage of the cryocooler)
TEMPS_K = (20.0, 25.0, 30.0)  # 15!A215: REBCO-class 20-30 K research envelope; 20 K a comparison point only
STRIKE_T = 0.02               # strike module thickness (slice 4 screen)
HUB_SPREAD_DEG = 25.0         # inboard struts land on the hub rim this far either side of the nozzle azimuth
HUB_HALF = 0.8                # half the central thrust hub's axial length (structure: annulus 1.6 m at the ring plane)


def k_integral(t0, t1):
    """G-10 class conductivity integral (W/m) between t0 and t1: k(T) ~ 0.07 + 0.0018 T, scaled so 20-300 K equals the slice 4 value."""
    raw = lambda a, b: 0.07*(b-a)+0.0009*(b*b-a*a)
    return ds.G10_KINT*raw(t0, t1)/raw(20.0, 300.0)


def cop(t):
    return ds.CARNOT_FRACTION*t/(300.0-t)


# ---------------------------------------------------------------- (1) bipod frame statics, failure cases, mass

def lin_solve(M, b):
    """Gaussian elimination with partial pivoting (small dense systems)."""
    n = len(M); A = [list(M[i])+[b[i]] for i in range(n)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(A[r][c])); A[c], A[p] = A[p], A[c]
        for r in range(n):
            if r != c and abs(A[r][c]) > 0:
                f = A[r][c]/A[c][c]; A[r] = [x-f*y for x, y in zip(A[r], A[c])]
    return [A[i][n]/A[i][i] for i in range(n)]


def min_norm(cols, rhs):
    """Member forces t (tension +) with sum t_k cols_k = rhs, minimum norm (A^T (A A^T)^-1 rhs); cols are the members' 6-vectors."""
    m = len(rhs); G = [[sum(c[i]*c[j] for c in cols) for j in range(m)] for i in range(m)]
    lam = lin_solve(G, rhs)
    return [sum(c[i]*lam[i] for i in range(m)) for c in cols]


def cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def inboard_struts(s, f):
    """Symmetric half of the frame: from the inner faces of yoke rings 1 and 2 to the central thrust hub's aft rim, 25 deg either side
    of the nozzle azimuth, so the coil reaction is carried on both sides of the nozzle axis (15!A214 G: symmetric axial struts)."""
    p, st = s['prototype'], s['structure']; import layout
    xring = layout.at(s, p['thrust_ring_x']); rh = st['hub_diameter_m']/2; ay, az = f['axis']; out = []
    for side, dphi in (('A', -HUB_SPREAD_DEG), ('B', HUB_SPREAD_DEG)):
        phi = math.radians(f['azimuth_deg']+dphi); h = (xring-HUB_HALF, rh*math.cos(phi), rh*math.sin(phi))
        u = ds.unit((h[1]-ay, h[2]-az))
        for k in (1, 2):
            r = f['yokes'][k]
            out.append(dict(name=f'Study_Thrust_Strut_In_{f["nozzle"]}_{side}_{k}', a=(r['x'], ay+(r['r_out']+.20)*u[0], az+(r['r_out']+.20)*u[1]),
                            b=h, node=f'hub_{side}', yoke=k))
    return out


def frame_cases(s):
    """Per nozzle, two frames under the proof load, the +-5 deg vector cases and each single-member loss, in full force AND moment
    equilibrium about the nozzle axis (the thrust acts on the axis): F4 the slice 4 outboard bipods alone, F8 symmetric (outboard bipods
    to the ring nodes + inboard bipods to the central hub). Members are pin-ended (axial force only)."""
    pr = s['propulsion']; P = pr['design_thrust']['value']*1e6/pr['nozzle_count']
    out = []
    for f in ds.nozzle_frames(s):
        ay, az = f['axis']; o = (sum(r['x'] for r in f['yokes'])/4, ay, az)
        ra = math.radians(f['azimuth_deg']); rad = (0.0, math.cos(ra), math.sin(ra)); tan = (0.0, -math.sin(ra), math.cos(ra))
        lat = P*math.sin(math.radians(VECTOR_DEG)); ax = P*math.cos(math.radians(VECTOR_DEG))
        cases = {'proof_axial': (P, 0.0, 0.0)}
        for name, v in (('vector_radial+', rad), ('vector_radial-', tuple(-c for c in rad)), ('vector_tangential+', tan), ('vector_tangential-', tuple(-c for c in tan))):
            cases[name] = (ax, lat*v[1], lat*v[2])
        res_f = {}
        for fname, members in (('F4', ds.thrust_struts(s, f)), ('F8', ds.thrust_struts(s, f)+inboard_struts(s, f))):
            cols = []; L = []
            for t in members:
                d = tuple(b-a for a, b in zip(t['a'], t['b'])); n = math.sqrt(sum(c*c for c in d)); u = tuple(c/n for c in d); L.append(n)
                cols.append(u+cross(tuple(t['a'][i]-o[i] for i in range(3)), u))
            res = {}; resid = {}
            for name, T in cases.items():
                rhs = tuple(-c for c in T)+(0.0, 0.0, 0.0)
                if fname == 'F4':                              # 4 members cannot meet 6 equations: forces only, report the moment left over
                    t = min_norm([c[:3] for c in cols], rhs[:3])
                    Mv = [sum(t[k]*cols[k][3+i] for k in range(len(cols))) for i in range(3)]; resid[name] = round(math.hypot(*Mv)/1e6, 2)
                else:
                    t = min_norm(cols, rhs)
                res[name] = [round(v/1e6, 3) for v in t]
            if fname == 'F8':
                for k in range(len(members)):                 # one member lost
                    keep = [i for i in range(len(members)) if i != k]; t7 = min_norm([cols[i] for i in keep], tuple(-c for c in cases['proof_axial'])+(0.0, 0.0, 0.0))
                    full = [0.0]*len(members)
                    for i, v in zip(keep, t7):
                        full[i] = v
                    res[f'member_{k}_lost'] = [round(v/1e6, 3) for v in full]
            mem = []
            for i, t in enumerate(members):
                comp = max(-v[i] for v in res.values())*1e6; tens = max(v[i] for v in res.values())*1e6
                size = ds.tube_size(max(comp, 1.0), L[i]); size_t = math.sqrt(max(tens, 0.0)*ds.D_OVER_T/(math.pi*ds.STRESS_FRACTION*ds.TI_YIELD))
                od = max(size['od_m'], size_t); area = math.pi*od*od/ds.D_OVER_T
                mem.append(dict(name=t['name'], to=t['node'], yoke=t['yoke'], length_m=round(L[i], 3),
                                angle_from_axis_deg=round(math.degrees(math.acos(abs(cols[i][0]))), 1),
                                max_compression_MN=round(comp/1e6, 2), max_tension_MN=round(max(tens, 0.0)/1e6, 2),
                                ti_tube_od_m=round(od, 3), mass_kg=round(area*L[i]*RHO_TI)))
            node_loads = {}
            for i, t in enumerate(members):
                ti = res['proof_axial'][i]*1e6; nl = node_loads.setdefault(str(t['node']), [0.0, 0.0, 0.0])
                for j in range(3):
                    nl[j] += -ti*cols[i][j]
            res_f[fname] = dict(cases_MN=res, members=mem, mass_kg=sum(m['mass_kg'] for m in mem),
                                node_loads_MN={n: [round(c/1e6, 3) for c in v] for n, v in node_loads.items()},
                                **({'unbalanced_moment_MN_m': resid} if fname == 'F4' else {}))
        out.append(dict(nozzle=f['nozzle'], azimuth_deg=round(f['azimuth_deg'], 1), moment_point=o, **res_f))
    return P, out


def pickup_compare(s, P):
    """The as-built pickups: force, the solid Ti rod they would need and their node loads, for the same proof load."""
    out = []
    for q in dm.nozzle_pickups(s):
        d = tuple(b-a for a, b in zip(q['a'], q['b'])); L = math.sqrt(sum(c*c for c in d)); u = tuple(c/L for c in d)
        F = P/abs(u[0]); area = F/(ds.STRESS_FRACTION*ds.TI_YIELD); r_need = math.sqrt(area/math.pi)
        out.append(dict(name=q['name'], force_MN=round(F/1e6, 1), solid_rod_r_needed_m=round(r_need, 3), built_r_m=q['radius'],
                        mass_kg_at_needed=round(area*L*RHO_TI)))
    return out


def nozzle_out(s, P):
    """One nozzle off at proof load: the yaw/pitch moment of the other three about the ship axis (the CoM lies on it within 0.2 m)."""
    off = math.hypot(*ds.nozzle_frames(s)[0]['axis'])
    return dict(nozzle_axis_offset_m=round(off, 2), moment_MN_m=round(P*off/1e6, 1),
                note='the remaining three nozzles push off-axis; the RCS couples are ~2e-5 of this, so a nozzle-out case means shutting the '
                     'opposite nozzle (two-nozzle thrust) or vectoring within the +-5 deg rig limit (authority OPEN). Applies to either frame.')


# ---------------------------------------------------------------- (2) thrust ring screen (ring-only path, Ti, screening)

def ring_section(s):
    st = s['structure']; p = s['prototype']; r = p['structural_strut_radius_m']; outer = st['ring_od_m']/2; inner = outer-st['ring_radial_depth_m']
    A = math.pi*r*r; d_rad = (outer-r)-(inner+r); d_ax = st['ring_depth_m']-2*r
    return dict(chord_r_m=r, chords=4, A_chord_m2=round(A, 5), I_in_plane_m4=round(4*A*(d_rad/2)**2, 6), I_out_of_plane_m4=round(4*A*(d_ax/2)**2, 6),
                c_in_m=d_rad/2, c_out_m=d_ax/2, R_m=st['ring_node_radius_m'], nodes=st['ring_nodes'])


def ring_screen(s, node_loads_in, node_axial):
    """In-plane: hoop force and bending of a ring under n equal radial node loads (largest in-plane node load, n = loaded nodes),
    elastic in-plane buckling against the equivalent uniform load (3EI/R^3). Out-of-plane: the node axial loads carried as straight
    simply-supported spans between the sector pickup nodes (1, 5, 9). Chord stress against Ti working stress. Ring-only bound."""
    st = s['structure']; sec = ring_section(s); R = sec['R_m']; n = len(node_loads_in); E = ds.TI_E; allow = ds.STRESS_FRACTION*ds.TI_YIELD
    P = max(node_loads_in.values()) if node_loads_in else 0.0; n = max(n, 3); a = math.pi/n
    N = P/(2*math.tan(a)); M = P*R/2*(1/math.sin(a)-1/a)
    s_hoop = N/(sec['chords']*sec['A_chord_m2']); s_bend = M*sec['c_in_m']/sec['I_in_plane_m4']
    q = n*P/(2*math.pi*R); q_cr = 3*E*sec['I_in_plane_m4']/R**3
    seg = 2*math.pi*R/st['ring_nodes']; Pe = math.pi**2*E*(math.pi*sec['chord_r_m']**4/4)/seg**2
    supports = st['sector_pickup_nodes']; arc = 2*math.pi*R/st['ring_nodes']; Mmax = 0.0
    for i, a0 in enumerate(supports):
        b0 = supports[(i+1) % len(supports)]; span = ((b0-a0) % st['ring_nodes'])*arc
        loads = [(((n_-a0) % st['ring_nodes'])*arc, abs(F)) for n_, F in node_axial.items() if 0 < (n_-a0) % st['ring_nodes'] < (b0-a0) % st['ring_nodes']]
        for xk in [span*k/200 for k in range(201)]:
            m = sum(F*(xk*(span-x)/span if xk <= x else x*(span-xk)/span) for x, F in loads); Mmax = max(Mmax, m)
    s_out = Mmax*sec['c_out_m']/sec['I_out_of_plane_m4']
    return dict(in_plane=dict(loaded_nodes=n, max_node_load_MN=round(P/1e6, 2), hoop_force_MN=round(N/1e6, 2), bending_MN_m=round(M/1e6, 2),
                              chord_stress_MPa=round((s_hoop+s_bend)/1e6), buckling_ratio_q_over_qcr=round(q/q_cr, 3),
                              chord_load_MN=round(N/sec['chords']/1e6, 2), chord_euler_between_nodes_MN=round(Pe/1e6, 1)),
                out_of_plane=dict(supports=supports, max_span_moment_MN_m=round(Mmax/1e6, 1), chord_stress_MPa=round(s_out/1e6)),
                allowable_MPa=round(allow/1e6), section=sec,
                note='Ring-only screening bound (Ti-6Al-4V assumed, ring material OPEN): the diagonals, node diaphragms, hub webs and keels '
                     'share these loads; FEA and ring buckling with the real section stay OPEN (15!A214).')


# ---------------------------------------------------------------- (3) REBCO re-entrant mounts, intercept, bore

def cryo_table(s, P):
    """Support conduction per nozzle and the cryocooler input, for 20/25/30 K: direct (built 0.05 m standoff), re-entrant 0.40 m and
    re-entrant with an 80 K intercept at mid-length. Support term only."""
    area = P/ds.G10_ALLOW; h = s['drive_hot_section']; out = {}
    for T in TEMPS_K:
        row = {}
        for name, L in (('direct', h['yoke_standoff_m']), ('reentrant', ds.REENTRANT_L)):
            q = area*k_integral(T, 300.0)/L; row[name] = dict(cold_W=round(q, 1), cooler_input_kW=round(q/cop(T)/1e3, 2))
        Lh = ds.REENTRANT_L/2; qc = area*k_integral(T, INTERCEPT_K)/Lh; qw = area*k_integral(INTERCEPT_K, 300.0)/Lh
        row['reentrant_80K_intercept'] = dict(cold_W=round(qc, 1), intercept_W=round(qw-qc, 1),
                                              cooler_input_kW=round((qc/cop(T)+(qw-qc)/cop(INTERCEPT_K))/1e3, 2))
        out[f'{T:.0f}K'] = dict(per_nozzle=row, ship_cooler_input_kW={k: round(4*v['cooler_input_kW'], 1) for k, v in row.items()},
                                specific_power_W_per_W=round(1/cop(T), 1))
    return dict(area_m2_per_nozzle=round(area, 4), intercept_K=INTERCEPT_K, by_temperature=out,
                basis='G-10 class supports at 200 MPa working sized for the 7.355 MN PROOF load (15!A214), k(T) ~ linear scaled to the slice 4 '
                      '20-300 K integral; cooler 15 % of Carnot. Support term only: nuclear, radiative and plasma heat on the coils OPEN; '
                      'none of these is a qualified cooler load (15!A215 H).')


def bore_variant(s):
    """Throat coils: the bore increase that gives >= 0.05 m between the plasma and a strike module on the cryostat, and the coil
    current increase that keeps the on-axis field of a loop of that radius (B ~ I / r): a field-design consequence, OPEN."""
    scr = ds.screen(s)['cryostat']; need = scr['plasma_clearance_needed_m']; coils = {c['name']: c for c in dm.nozzle_coils(s)}; out = []
    for b in scr['bore']:
        gap = b['strike_on_jacket_gap_m'] if b['strike_module'] else b['jacket_gap_m']
        add = max(0.0, need-gap); c = coils[b['coil']]
        out.append(dict(coil=b['coil'], gap_now_m=gap, bore_add_m=round(add, 3), inner_r_now_m=c['inner'], inner_r_variant_m=round(c['inner']+add, 3),
                        current_increase_pct=round(100*add/c['ring_radius'], 1), passes=gap >= need))
    return dict(clearance_needed_m=need, coils=out)


def yoke_variant(s):
    """Yoke rings moved out by STANDOFF_ADD for the re-entrant supports: envelope growth and the gap between neighbouring nozzles."""
    ys = dm.nozzle_yokes(s); off = math.hypot(*ys[0]['axis']); pitch = 2*off*math.sin(math.pi/4)        # neighbours 90 deg apart
    rmax = max(r['r_out'] for r in ys[0]['rings'])
    return dict(standoff_now_m=s['drive_hot_section']['yoke_standoff_m'], standoff_variant_m=round(s['drive_hot_section']['yoke_standoff_m']+STANDOFF_ADD, 3),
                yoke_r_out_max_now_m=round(rmax, 3), yoke_r_out_max_variant_m=round(rmax+STANDOFF_ADD, 3),
                neighbour_axis_spacing_m=round(pitch, 2), neighbour_gap_now_m=round(pitch-2*rmax, 2), neighbour_gap_variant_m=round(pitch-2*(rmax+STANDOFF_ADD), 2),
                note='an outer-geometry change of the nozzle hardware (15!A214 H): study only; the vehicle keeps the 0.05 m standoff')


def branch_clearance(s):
    """Inboard struts against the plasma branches (centreline polylines, conservative maximum radius) and the 0.05 m hardware clearance:
    the branch plasma meshes are display objects with no size in the static pose, so this is analytic."""
    g = dm.geometry(s); rmax = s['drive_manifold']['plasma_branch_max_radius_m']; need = s['drive_manifold']['plasma_hardware_clearance_m']
    pts = [p for br in g['branches'] for p in br]; worst = None
    for f in ds.nozzle_frames(s):
        for t in inboard_struts(s, f):
            a, b = t['a'], t['b']; d = tuple(y-x for x, y in zip(a, b)); L2 = sum(c*c for c in d)
            for p in pts:
                u = max(0.0, min(1.0, sum((p[i]-a[i])*d[i] for i in range(3))/L2)); q = tuple(a[i]+u*d[i] for i in range(3))
                gap = math.dist(p, q)-rmax
                if worst is None or gap < worst[0]:
                    worst = (gap, t['name'])
    return dict(min_gap_to_branch_envelope_m=round(worst[0], 2), strut=worst[1], needed_m=need, passes=worst[0] >= need,
                basis=f'branch centrelines, radius {rmax} m everywhere (conservative); strut centreline (its radius <= 0.16 m not subtracted)')


def screen(s):
    P, frames = frame_cases(s); pick = pickup_compare(s, P)
    built_in = {}; built_ax = {}
    for q, f in zip(dm.nozzle_pickups(s), pick):
        node = s['structure']['nozzle_pickup_nodes'][int(q['name'].split('_')[-1])]
        d = tuple(b-a for a, b in zip(q['a'], q['b'])); L = math.sqrt(sum(c*c for c in d)); u = tuple(c/L for c in d); F = P/abs(u[0])
        built_in[node] = F*math.hypot(u[1], u[2]); built_ax[node] = F*abs(u[0])
    ring = dict(as_built=ring_screen(s, built_in, built_ax))
    for fn in ('F4', 'F8'):
        bin_, bax = {}, {}; hub = [0.0, 0.0, 0.0]
        for f in frames:
            for n, v in f[fn]['node_loads_MN'].items():
                if n.startswith('hub'):
                    hub = [h+abs(c) for h, c in zip(hub, v)]; continue
                bin_[int(n)] = bin_.get(int(n), 0.0)+math.hypot(v[1], v[2])*1e6; bax[int(n)] = bax.get(int(n), 0.0)+abs(v[0])*1e6
        ring[fn] = ring_screen(s, bin_, bax)
        ring[fn]['hub_abs_sum_MN'] = [round(c, 2) for c in hub]
    return dict(status='L2 PREFERRED STUDY / AS-BUILT UNCHANGED / OD-024 OD-025 HOLD (S&E 15!A214, 15!A215, 98!A118)',
                proof_load_N_per_nozzle=round(P), proof_note='7.355 MN per nozzle is a STRUCTURAL PROOF value, not operating thrust (15!A214)',
                frames=frames, frame_mass_kg={fn: sum(f[fn]['mass_kg'] for f in frames) for fn in ('F4', 'F8')},
                as_built_pickups=pick, as_built_pickup_mass_kg_at_needed=sum(p['mass_kg_at_needed'] for p in pick),
                nozzle_out=nozzle_out(s, P),
                ring=ring,
                branch_clearance=branch_clearance(s), cryo=cryo_table(s, P), bore=bore_variant(s), yoke=yoke_variant(s),
                prototype=dict(vector_deg=VECTOR_DEG, standoff_add_m=STANDOFF_ADD, intercept_K=INTERCEPT_K, temps_K=TEMPS_K, rho_ti=RHO_TI))


# ---------------------------------------------------------------- study asset (Blender): variant mounts for all four nozzles

COLOR = dict(drive_thrust_strut_inboard=(.94, .70, .15), nozzle_mount_yoke=(.62, .64, .66), cryo_reentrant_support=(.95, .56, .17), cryo_intercept=(.40, .80, .95), cryo_coil_jacket_bore=(.86, .84, .74))


def parts(s):
    out = []; bore = {c['coil']: c for c in bore_variant(s)['coils']}
    _, frames = frame_cases(s); od = {m['name']: m['ti_tube_od_m'] for fr in frames for m in fr['F8']['members']}
    for f in ds.nozzle_frames(s):
        j = f['nozzle']; ay, az = f['axis']
        for t in inboard_struts(s, f):
            out.append(dict(name=t['name'], kind='drive_thrust_strut_inboard', shape='tube', radius=od[t['name']]/2, points=[t['a'], t['b']],
                            note=f'symmetric frame F8: inboard strut yoke ring {t["yoke"]} -> central thrust hub (Ti OD {od[t["name"]]:.2f} m, '
                                 'sized for the proof, vector and member-loss cases)'))
        for c, yk in zip(f['coils'], f['yokes']):
            add = bore[c['name']]['bore_add_m']; r_in_c = c['inner']+add; r_out_c = c['outer']+add
            jo = r_out_c+ds.JACKET; y0 = yk['r_in']+add+STANDOFF_ADD; y1 = yk['r_out']+add+STANDOFF_ADD
            out.append(dict(name=f'Study_Mount_Yoke_{j}_{c["index"]}', kind='nozzle_mount_yoke', shape='revolve', axis=(ay, az),
                            x0=yk['x0'], x1=yk['x1'], r0=y0, r1=y1, note=f'variant warm yoke, standoff {0.05+STANDOFF_ADD:.2f} m (as built 0.05 m)'))
            if add > 0:
                out.append(dict(name=f'Study_Mount_Bore_Cryostat_{j}_{c["index"]}', kind='cryo_coil_jacket_bore', shape='revolve', axis=(ay, az),
                                x0=c['x_ship']-c['tube']-ds.JACKET, x1=c['x_ship']+c['tube']+ds.JACKET, r0=r_in_c-ds.JACKET, r1=jo,
                                note=f'coil {c["index"]} bore +{add:.3f} m so the strike module on the cryostat clears the plasma by >= 0.05 m'))
            rmid = (jo+y0)/2
            out.append(dict(name=f'Study_Mount_Intercept_{j}_{c["index"]}', kind='cryo_intercept', shape='revolve', axis=(ay, az),
                            x0=c['x_ship']-c['tube']-ds.JACKET-0.02, x1=c['x_ship']+c['tube']+ds.JACKET+0.02, r0=rmid-0.006, r1=rmid+0.006,
                            note=f'{INTERCEPT_K:.0f} K thermal intercept shield / ring at mid-length of the re-entrant supports'))
            for m in range(ds.SUPPORTS_PER_COIL):
                t = math.tau*(m+.5)/ds.SUPPORTS_PER_COIL; u = (math.cos(t), math.sin(t))
                for leg, (ra, rb, rr, dx) in enumerate(((jo+.002, y0-.002, .022, -.03), (y0-.03, jo+.03, .022, .03))):
                    out.append(dict(name=f'Study_Mount_Support_{j}_{c["index"]}_{m}_{leg}', kind='cryo_reentrant_support', shape='tube', radius=rr,
                                    points=[(c['x_ship']+dx, ay+ra*u[0], az+ra*u[1]), (c['x_ship']+dx, ay+rb*u[0], az+rb*u[1])],
                                    note='re-entrant (folded) cold-mass support leg: 0.40 m conduction path in a 0.25 m gap'))
    return out


def build_asset(s):
    import bpy
    from common import material
    from m5_eva_l2 import tube_mesh
    bpy.ops.wm.read_factory_settings(use_empty=True)
    col = bpy.data.collections.new(COLLECTION); bpy.context.scene.collection.children.link(col)
    col['study'] = 'm5_nozzle_mounts'; col['status'] = 'L2 PREFERRED STUDY / OD-024 OD-025 HOLD: variant mounts; the vehicle is unchanged'
    mats = {k: material(f'STUDY_{k}', c) for k, c in COLOR.items()}
    for p in parts(s):
        ob = ds.revolve(p['name'], p['axis'], p['x0'], p['x1'], p['r0'], p['r1']) if p['shape'] == 'revolve' else tube_mesh(p['name'], p['points'], p['radius'], 10)
        col.objects.link(ob); ob.data.materials.append(mats[p['kind']])
        ob['kind'] = p['kind']; ob['note'] = p['note']; ob['geometry_status'] = 'PROTOTYPE'; ob['study'] = 'm5_nozzle_mounts'
        ob['canon_status'] = 'STUDY / NONCANON (15!A215)'; ob['component_id'] = f'WF.STUDY.NOZZLE_MOUNTS.{p["name"]}'
    ASSET.parent.mkdir(parents=True, exist_ok=True); bpy.ops.wm.save_as_mainfile(filepath=str(ASSET), compress=True)


def measure():
    """Variant parts against the vehicle and the slice 4 study, excluding the as-built yokes, coils, straps and slice 4 cryostats and
    supports they replace: anything else they touch."""
    import bpy
    from mathutils.bvhtree import BVHTree
    import shot_tools
    replaced = ('Nozzle_Yoke', 'Nozzle_Coil', 'Study_Coil_Cryostat', 'Study_Coil_Support', 'PFC_NOZZLE_STRIKE', 'MagneticNozzle_FieldEnvelope',
                'Study_Cryo_Stub', 'Study_Lead_Stub', 'Study_Thrust_Strut', 'Study_Cryo_Line', 'Study_Current_Lead', 'Nozzle_Pickup', 'PLASMA_')
    vs, fs, names = [], [], []
    for src in ({'asset': 'WF_WAYFARER_001.blend', 'collection': 'WF_WAYFARER_001', 'group': 'assembly'},
                {'asset': 'studies/WF_STUDY_DRIVE_SUPPORT.blend', 'collection': 'WF_STUDY_DRIVE_SUPPORT', 'group': 'fixed'}):
        for it in shot_tools.gather(shot_tools.link_source(ROOT, src), src):
            ob = it['obj']
            if ob.type != 'MESH' or it['center'][0] > -95 or it['name'].startswith(replaced) or it['kind'] in ('scale_reference', 'plasma', 'magnetic_field'):
                continue
            W = it['matrix']; b = len(vs); vs += [W@v.co for v in ob.data.vertices]
            for poly in ob.data.polygons:
                fs.append(tuple(b+i for i in poly.vertices)); names.append(it['name'])
    other = BVHTree.FromPolygons(vs, fs); hits = {}
    pv, pf, pn = [], [], []                                  # plasma channels and the manifold: a strut must never cross them
    src0 = {'asset': 'WF_WAYFARER_001.blend', 'collection': 'WF_WAYFARER_001', 'group': 'assembly'}
    for it in shot_tools.gather(shot_tools.link_source(ROOT, src0), src0):
        ob = it['obj']
        if ob.type == 'MESH' and (it['kind'] == 'plasma' or it['name'].startswith(('Magnetic_Manifold', 'Common_Plasma', 'LATTICE', 'PLASMA_'))):
            W = it['matrix']; b = len(pv); pv += [W@v.co for v in ob.data.vertices]
            for poly in ob.data.polygons:
                pf.append(tuple(b+i for i in poly.vertices)); pn.append(it['name'])
    plasma = BVHTree.FromPolygons(pv, pf); plasma_hits = {}
    src = {'asset': 'studies/WF_STUDY_NOZZLE_MOUNTS.blend', 'collection': COLLECTION, 'group': 'fixed'}
    for it in shot_tools.gather(shot_tools.link_source(ROOT, src), src):
        ob = it['obj']; W = it['matrix']
        b = BVHTree.FromPolygons([W@v.co for v in ob.data.vertices], [tuple(p.vertices) for p in ob.data.polygons])
        h = sorted({names[j] for _, j in b.overlap(other)})
        if h:
            hits[it['name']] = h
        hp = sorted({pn[j] for _, j in b.overlap(plasma)})
        if hp:
            plasma_hits[it['name']] = hp
    return dict(overlaps=hits, plasma_or_manifold=plasma_hits)


def main(asset=False):
    from spec import load
    s = load(ROOT)[0]; res = screen(s)
    if asset:
        build_asset(s)
        import bpy
        bpy.ops.wm.read_factory_settings(use_empty=True)
        res['measured'] = measure(); res['measured']['parts'] = len(parts(s))
    elif OUT_JSON.exists() and 'measured' in json.loads(OUT_JSON.read_text()):
        res['measured'] = json.loads(OUT_JSON.read_text())['measured']
    OUT_JSON.write_text(json.dumps(res, indent=1)+'\n')
    f0 = res['frames'][0]
    print('proof', res['proof_load_N_per_nozzle'], 'frame mass', res['frame_mass_kg'], 'pickup mass at need', res['as_built_pickup_mass_kg_at_needed'])
    print('F4 unbalanced moment', f0['F4']['unbalanced_moment_MN_m'])
    for m in f0['F8']['members']:
        print(' F8 member', m)
    print(' F8 proof', f0['F8']['cases_MN']['proof_axial'])
    print(' F8 node loads', f0['F8']['node_loads_MN'])
    print('pickups', res['as_built_pickups'][0])
    print('nozzle out', res['nozzle_out'])
    for k, v in res['ring'].items():
        print('ring', k, v['in_plane'], v['out_of_plane'])
    print('cryo', json.dumps(res['cryo']['by_temperature'], indent=0)[:1600])
    print('bore', res['bore']); print('yoke', res['yoke'])
    if 'measured' in res:
        print('measured', json.dumps(res['measured'])[:1500])
    return res


if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser(); ap.add_argument('--asset', action='store_true')
    main(ap.parse_args(argv).asset)
