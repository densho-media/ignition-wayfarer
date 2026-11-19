"""Vertex Engine 1.2 structural validation (owner brief 2026-11-14). Pure, standard library only.

The engine geometry stays in vertex_engine (one model); this module derives the loads that geometry has to carry and sizes its load-bearing
members against PMDS material data. Nothing here is propulsion evidence: the drive's feasibility gate (Gate 2) stays BLOCKED, and a member
that is sized here carries a force that only exists if the speculative drive works.

  Field model     exact circular-loop field (complete elliptic integrals by the arithmetic-geometric mean) for the six coils C1, C2, L1-L4
  currents(case)  NOMINAL / CONSERVATIVE / EXTREME ampere-turn sets ([vertex_engine.structure])
  coil_forces     axial force, hoop tension and winding-case stress of every coil; cut forces through the cage
  inter_engine    exact force and torque between the four engines' coil sets (each target coil discretised), against the dipole estimate
  load_cases      the LC-01 .. LC-06 register
  sizing          members of ME-01 .. ME-05 and the cluster frame, with utilisation per case and a status per component
  fe_*            frame finite-element screens (reaction ring, cluster frame), validated against closed forms and checked for convergence

    python3 src/wayfarer/vertex_structure.py      # fit screen: forces, member table, statuses, mass rollup
"""
import copy
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fe_frame as fe
import material_physics as mp
import vertex_cluster as vc
import vertex_engine as ve

MU0 = 4e-7*math.pi
STATUSES = ('ANALYTICALLY_SIZED', 'CONDITIONALLY_SIZED', 'FEA_SCREENED', 'UNSIZED', 'BLOCKED', 'SPECULATIVE')

# Engine 1.1 member sizes (historical record of the drawn values before this sizing; the 1.2 values live in data/wayfarer_3d.toml)
ENGINE_1_1 = dict(tie_rod_radius_m=0.12, reaction_ring_minor_m=0.15, cage_hoop_minor_m=0.12, loop_seat_radius_m=0.10, cage_longeron_radius_m=0.22,
                  coil_strut_radius_m=0.16, loop_seat_offset_m=[0.0, 0.0, 0.0, 0.0])
CLUSTER_1_1 = dict(member_radius_m=0.42, thrust_strut_radius_m=0.36)


def config(s):
    return s['vertex_engine']['structure']


# ---------- field model ---------------------------------------------------------------------------------------------------------

def ellipke(m):
    """Complete elliptic integrals K(m), E(m) (parameter m = k^2) by the arithmetic-geometric mean."""
    a, b = 1.0, math.sqrt(1.0-m); s, p = 0.5*m, 0.5
    while abs(a-b) > 1e-15*a:
        a, b, c = (a+b)/2, math.sqrt(a*b), (a-b)/2
        p *= 2; s += p*c*c
    K = math.pi/(2*a)
    return K, K*(1.0-s)


def loop_field(a, I, rho, z):
    """(B_rho, B_z) in tesla of a circular loop of radius a carrying I (ampere-turns), at radius rho and axial offset z from its centre."""
    q = (a+rho)**2+z*z; d = (a-rho)**2+z*z
    K, E = ellipke(4*a*rho/q); c = MU0*I/(2*math.pi*math.sqrt(q))
    Bz = c*(K+(a*a-rho*rho-z*z)/d*E)
    Br = 0.0 if rho < 1e-12 else c*z/rho*(-K+(a*a+rho*rho+z*z)/d*E)
    return Br, Bz


def mutual(a1, a2, z):
    """Mutual inductance (H per turn pair) of two coaxial loops."""
    k2 = 4*a1*a2/((a1+a2)**2+z*z); k = math.sqrt(k2); K, E = ellipke(k2)
    return MU0*math.sqrt(a1*a2)*((2/k-k)*K-2/k*E)


def self_inductance(R, a):
    """Self inductance (H per turn squared) of a thin round ring with uniform current over a minor radius a: mu0 R (ln(8R/a) - 7/4)."""
    return MU0*R*(math.log(8*R/a)-1.75)


def coils(s):
    """The six coils in the engine frame: name, group, station x, radius r, winding minor radius a, cryostat minor radius."""
    st = ve.stations(s)
    return ([dict(name=c['name'], group='closure', x=c['x'], r=c['r'], a=c['winding_minor_m'], cryostat=c['cryostat_minor_m']) for c in st['coils']] +
            [dict(name=l['name'], group='loop', x=l['x'], r=l['r'], a=l['winding_minor_m'], cryostat=l['cryostat_minor_m']) for l in st['loops']])


def axis_field(cs, I, x):
    return sum(loop_field(c['r'], i, 0.0, x-c['x'])[1] for c, i in zip(cs, I))


def stop_field(s):
    return next(r['compact'] for r in ve.calculations(s) if r['id'] == 'C-07')


def currents(s, case):
    """Ampere-turns of C1, C2, L1-L4 (closure coils opposed). I is proportional to r inside each group (equal own-centre field)."""
    ex = config(s).get('explicit_currents', {})
    if case in ex:                       # 1.3: a magnetic candidate's own current set (vertex_magnet.scaled_spec), never set in the data
        return list(ex[case])
    cs = coils(s); st = ve.stations(s); B = stop_field(s)
    shape = [(-1.0 if c['group'] == 'closure' else 1.0)*2*B*c['r']/MU0 for c in cs]
    loops = [v if c['group'] == 'loop' else 0.0 for c, v in zip(cs, shape)]
    clos = [v if c['group'] == 'closure' else 0.0 for c, v in zip(cs, shape)]
    f = lambda al, be: [al*l+be*c for l, c in zip(loops, clos)]
    if case == 'NOMINAL':
        A = [[axis_field(cs, f(1, 0), st['burn']), axis_field(cs, f(0, 1), st['burn'])],
             [axis_field(cs, f(1, 0), st['shield_aft']), axis_field(cs, f(0, 1), st['shield_aft'])]]
        det = A[0][0]*A[1][1]-A[0][1]*A[1][0]
        al, be = B*A[1][1]/det, -B*A[1][0]/det
    elif case in ('CONSERVATIVE', 'EXTREME'):
        al = 1.0
        b0, b1 = axis_field(cs, f(1, 0), st['shield_aft']), axis_field(cs, f(0, 1), st['shield_aft'])
        be = -b0/b1
    else:
        raise KeyError(case)
    return f(al, be)


def compression_factor(s, case):
    """Force multiplier of a case on the windings: EXTREME raises the field by 1/(1 - f^2) (flux compression), the force by its square."""
    if case != 'EXTREME':
        return 1.0
    fr = config(s)['compression_radius_fraction']
    return (1.0/(1.0-fr*fr))**2


def coil_forces(s, case):
    """Per coil: current, axial force on it from the other five (N, +x forward), external B_z at the winding, hoop tension (self + external),
    winding-case stress at the case fraction, and the conductor turns at the lead current."""
    c = config(s); cs = coils(s); I = currents(s, case); k = compression_factor(s, case); out = []
    for j, cj in enumerate(cs):
        Fz = Bz = 0.0
        for i, ci in enumerate(cs):
            if i == j:
                continue
            br, bz = loop_field(ci['r'], I[i], cj['r'], cj['x']-ci['x'])
            Fz += -I[j]*2*math.pi*cj['r']*br; Bz += bz
        T_self = MU0*I[j]**2/(4*math.pi)*(math.log(8*cj['r']/cj['a'])-0.75)
        T = (T_self+I[j]*Bz*cj['r'])*k
        area = math.pi*cj['a']**2*c['coil_case_fraction']
        out.append(dict(cj, current_At=I[j], Fz_N=Fz*k, Bz_ext_T=Bz, hoop_N=T, hoop_self_N=T_self*k, case_area_m2=area, case_stress_Pa=T/area,
                        turns=abs(I[j])/c['conductor_current_A']))
    return out


def cut_forces(s, case):
    """Axial force carried through the cage between neighbouring stations (+ tension), from the loop forces aft of each cut."""
    f = [c for c in coil_forces(s, case) if c['group'] == 'loop']
    names = ['collar']+[c['name'] for c in f]
    return [dict(cut=f'{names[i]}|{names[i+1]}', tension_N=-sum(c['Fz_N'] for c in f[i:])) for i in range(len(f))]


def stored_energy(s, case):
    """Magnetic energy of one engine's six coils (J), from self and mutual inductances in ampere-turn form; and per coil (half its flux linkage)."""
    cs = coils(s); I = currents(s, case); W = 0.0; per = []
    for i, ci in enumerate(cs):
        lk = 0.0
        for j, cj in enumerate(cs):
            Mij = self_inductance(ci['r'], ci['a']) if i == j else mutual(ci['r'], cj['r'], ci['x']-cj['x'])
            lk += Mij*I[j]
        per.append(0.5*I[i]*lk); W += 0.5*I[i]*lk
    return W, per


def axial_stiffness(s, case, h=0.005):
    """Magnetic axial stiffness of each coil against the other five (N/m, k_z = -dF_z/dz) and the radial (decentring) stiffness that follows
    for a rigid loop in a source-free field (k_x + k_y + k_z = 0, so k_r = -k_z/2): negative k means an unstable direction."""
    cs = coils(s); I = currents(s, case); out = []
    for j, cj in enumerate(cs):
        F = []
        for dz in (-h, h):
            f = 0.0
            for i, ci in enumerate(cs):
                if i != j:
                    f += -I[j]*2*math.pi*cj['r']*loop_field(ci['r'], I[i], cj['r'], cj['x']+dz-ci['x'])[0]
            F.append(f)
        kz = -(F[1]-F[0])/(2*h)
        out.append(dict(name=cj['name'], kz_N_m=kz, kr_N_m=-kz/2))
    return out


# ---------- inter-engine magnetics (LC-03) --------------------------------------------------------------------------------------

def _cross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def _sources(s, case, pls, off=()):
    cs = coils(s); I = currents(s, case); out = []
    for pl in pls:
        if pl['n'] in off:
            continue
        for c, i in zip(cs, I):
            out.append((vc.to_ship(pl, (c['x'], 0, 0)), pl['axes'][0], c['r'], i*pl['polarity']))
    return out


def _B(p, srcs):
    B = [0.0, 0.0, 0.0]
    for c, ax, r, I in srcs:
        rel = vc.sub(p, c); z = vc.dot(rel, ax); rv = vc.sub(rel, vc.mul(ax, z)); rho = math.sqrt(vc.dot(rv, rv))
        br, bz = loop_field(r, I, rho, z)
        rh = vc.mul(rv, 1/rho) if rho > 1e-9 else (0.0, 0.0, 0.0)
        for i in range(3):
            B[i] += bz*ax[i]+br*rh[i]
    return B


def inter_engine(s, case='NOMINAL', N=24, off=(), pitch=None):
    """Force (N) and torque (N m, about the engine's collar centre) on every energised engine from the other engines' coils, ship frame.
    off: engines whose coils are de-energised. Each target coil is cut into N segments (F = I dl x B)."""
    pls = vc.placements(s, pitch=pitch); cs = coils(s); I = currents(s, case); est = ve.stations(s); out = []
    mid = (est['collar_fwd']+est['collar_aft'])/2
    for pl in pls:
        if pl['n'] in off:
            continue
        srcs = _sources(s, case, [p for p in pls if p['n'] != pl['n']], off)
        F = [0.0]*3; M = [0.0]*3; O = vc.to_ship(pl, (mid, 0, 0)); X, Y, Z = pl['axes']
        for c, i in zip(cs, I):
            i *= pl['polarity']
            for k in range(N):
                ph = 2*math.pi*(k+0.5)/N
                p = vc.to_ship(pl, (c['x'], c['r']*math.cos(ph), c['r']*math.sin(ph)))
                t = (-math.sin(ph), math.cos(ph))
                dl = tuple((Y[q]*t[0]+Z[q]*t[1])*c['r']*2*math.pi/N for q in range(3))
                dF = tuple(i*v for v in _cross(dl, _B(p, srcs)))
                dM = _cross(vc.sub(p, O), dF)
                for q in range(3):
                    F[q] += dF[q]; M[q] += dM[q]
        u = vc.norm((0.0, O[1], O[2]))
        out.append(dict(engine=pl['n'], force_N=F, torque_Nm=M, radial_N=vc.dot(F, u), axial_N=F[0], at=O))
    return out


def dipole_estimate(s, case='NOMINAL'):
    """Point-dipole force between adjacent and diagonal engines (side by side, moments along x): F = 3 mu0 m^2 / (4 pi d^4)."""
    cs = coils(s); I = currents(s, case); m = sum(i*math.pi*c['r']**2 for c, i in zip(cs, I))
    p = vc.config(s)['pitch_radius_m']
    adj, diag = p*math.sqrt(2), 2*p
    return dict(moment_Am2=m, adjacent_N=3*MU0*m*m/(4*math.pi*adj**4), diagonal_N=3*MU0*m*m/(4*math.pi*diag**4), adjacent_m=adj, diagonal_m=diag)


# ---------- materials (PMDS) ----------------------------------------------------------------------------------------------------

MEMBER_MATERIALS = ('MAT-TI6AL4V', 'MAT-INCONEL-718', 'MAT-CFRP')


def material(s, mid, T=293.0):
    """Design values of a structural candidate from the catalogue (never typed here). Metals: allowable = yield / yield SF. CFRP: strength x
    knockdown / ultimate SF, and the knocked-down modulus for buckling. Unknown properties raise material_physics.UnknownProperty."""
    c = config(s); q = lambda p: mp.get_property(mid, p, T)
    rho = mp.require(q('density'), 'high' if q('density')['value'] is None else 'value')
    if mid == 'MAT-CFRP':
        E = mp.require(q('elastic_modulus'))*c['composite_knockdown']
        tens = mp.require(q('ultimate_strength'))*c['composite_knockdown']/c['ultimate_safety_factor']
        comp = mp.require(q('compressive_strength'))*c['composite_knockdown']/c['ultimate_safety_factor']
        rule = f"strength x {c['composite_knockdown']} / {c['ultimate_safety_factor']} (UD datasheet, knocked down)"
    else:
        E = mp.require(q('elastic_modulus'))
        ys = q('yield_strength'); y = mp.require(ys, 'low' if ys['value'] is None else 'value')
        tens = comp = y/c['yield_safety_factor']; rule = f"yield / {c['yield_safety_factor']}"
    G = E/2.6
    src = {p: q(p)['source'] for p in ('density', 'elastic_modulus')}
    return dict(id=mid, density=rho, E=E, G=G, allow_tension=tens, allow_compression=comp, rule=rule, temperature_K=T, sources=src)


def coil_case_allowable(s):
    """Winding-case allowable at the cold-mass temperature: 2/3 of the low end of 316LN's 4.2 K proof stress (coil_case_rule)."""
    q = mp.get_property('MAT-SS-316LN', 'yield_strength', config(s)['cold_mass_temperature_K'])
    return dict(material='MAT-SS-316LN', yield_low=mp.require(q, 'low'), allowable=2/3*mp.require(q, 'low'), source=q['source'], status=q['status'],
                note=q['note'])


def material_table(s):
    """Every property the sizing reads, with its PMDS status, for the report and the inspection panel."""
    rows = []
    for mid, props, T in (('MAT-TI6AL4V', ('density', 'elastic_modulus', 'yield_strength', 'ultimate_strength', 'thermal_expansion', 'max_service_temperature'), 293.0),
                          ('MAT-INCONEL-718', ('density', 'elastic_modulus', 'yield_strength', 'thermal_expansion', 'max_service_temperature'), 293.0),
                          ('MAT-CFRP', ('density', 'elastic_modulus', 'ultimate_strength', 'compressive_strength'), 293.0),
                          ('MAT-SS-316LN', ('density', 'yield_strength', 'elastic_modulus'), 20.0),
                          ('MAT-LIH', ('density', 'thermal_expansion', 'melting_point'), 293.0),
                          ('MAT-NB1ZR', ('max_service_temperature', 'yield_strength', 'thermal_expansion'), None),
                          ('MAT-TZM', ('yield_strength', 'max_service_temperature'), None),
                          ('MAT-MORE', ('yield_strength', 'max_service_temperature'), None),
                          ('MAT-W', ('elastic_modulus', 'max_service_temperature', 'ductile_brittle_transition'), 293.0)):
        for p in props:
            q = mp.get_property(mid, p, T)
            rows.append(dict(material=mid, property=p, status=q['status'], value=q['value'], low=q['low'], high=q['high'], unit=q['unit'],
                             at_K=q['temperature_K'], basis=q['basis'], confidence=q['confidence'], source=q['source'], level=q['level']))
    return rows


# ---------- member checks ---------------------------------------------------------------------------------------------------------

def tube_section(r, s):
    return fe.tube(r, ve.config(s)['materials']['solid_fraction']['structure'])


def check_tube(N, r, L, m, s, K=1.0, M=0.0):
    """Utilisation of a tube member (outer radius r, structure solid fraction) under axial force N (+ tension) and bending M over length L:
    strength (axial + bending against the allowable) and, in compression, Euler buckling against buckling_safety_factor."""
    sec = tube_section(r, s); c = config(s)
    sig = abs(N)/sec['A']+M*sec['c']/sec['Iy']
    allow = m['allow_tension'] if N >= 0 else m['allow_compression']
    u_str = sig/allow
    Pcr = math.pi**2*m['E']*sec['Iy']/(K*L)**2
    u_buck = (max(0.0, -N)*c['buckling_safety_factor']/Pcr) if N < 0 else 0.0
    return dict(N=N, M=M, L=L, r=r, stress=sig, allowable=allow, u_strength=u_str, u_buckling=u_buck, u=max(u_str, u_buck), Pcr=Pcr,
                governs='buckling' if u_buck > u_str else 'strength')


def size_tube(N, L, m, s, K=1.0, M=0.0, step=0.01, r0=0.02):
    """Smallest outer radius (on a step grid) with utilisation <= 1."""
    r = r0
    while check_tube(N, r, L, m, s, K, M)['u'] > 1.0:
        r = round(r+step, 6)
        if r > 3.0:
            return None
    return r


def _len(pts):
    return sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))


def _group(parts, stem):
    return [p for p in parts if p['name'].startswith(stem)]


def engine_members(s, case='NOMINAL'):
    """Engine members with their loads for one current case: cage longerons (cut forces), loop seats, cage hoops, closure struts, reaction
    ring and tie rods (frame FE), coil windings (hoop), collar. Returns a dict by member group."""
    g = ve.config(s)['geometry']; parts = ve.parts(s); m = material(s, 'MAT-TI6AL4V'); out = {}
    cf = {c['name']: c for c in coil_forces(s, case)}; n_l = g['cage_longerons']
    # --- cage longerons: each cut's force shared by n longerons, along the longeron's own direction; buckling between hoops
    lon = _group(parts, 'VTX_Cage_Longeron_')[0]; pts = lon['points']
    cuts = cut_forces(s, case); rows = []
    for i, ct in enumerate(cuts):
        a, b = pts[i], pts[i+1]; L = math.dist(a, b); cosx = abs(a[0]-b[0])/L
        N = ct['tension_N']/n_l/cosx
        rows.append(dict(check_tube(N, lon['radius'], L, m, s), segment=ct['cut']))
    out['longeron'] = dict(rows=rows, u=max(r['u'] for r in rows), radius=lon['radius'], count=n_l)
    # --- loop seats: each loop's axial force over n seats; a seat inclined by its axial offset carries it as a strut, a radial seat as a
    # cantilever (bending over its length)
    seats = []
    for l in [c for c in coils(s) if c['group'] == 'loop']:
        sp = _group(parts, f'VTX_Loop_Seat_{l["name"]}_')[0]; a, b = sp['points'][0], sp['points'][-1]
        L = math.dist(a, b); dx = b[0]-a[0]; Fa = cf[l['name']]['Fz_N']/n_l
        if abs(dx) > 1e-6:
            N = -Fa*L/dx                                  # strut force: its axial component balances the loop's share
            radial = N*math.hypot(b[1]-a[1], b[2]-a[2])/L  # radial component into the hoop (per seat)
            row = check_tube(N, sp['radius'], L, m, s, K=1.0)
        else:
            N, radial = 0.0, 0.0
            row = check_tube(0.0, sp['radius'], L, m, s, M=abs(Fa)*L)
        seats.append(dict(row, loop=l['name'], axial_share_N=Fa, radial_N=radial, inclined=abs(dx) > 1e-6))
    out['seat'] = dict(rows=seats, u=max(r['u'] for r in seats), radius=seats[0]['r'], count=n_l*4)
    # --- cage hoops: n equal radial point loads from the seats (closed-form ring bending, P R/2 (1/alpha - cot alpha) at a load)
    hoops = []
    for l, st in zip([c for c in coils(s) if c['group'] == 'loop'], seats):
        hp = _group(parts, f'VTX_Cage_Hoop_{l["name"]}')[0]; R, a = hp['R'], hp['a']; P = abs(st['radial_N'])
        al = math.pi/n_l; Mb = P*R/2*(1/al-1/math.tan(al)); Nh = P/(2*math.sin(al))
        row = check_tube(Nh, a, 2*math.pi*R/n_l, m, s, M=Mb)
        hoops.append(dict(row, loop=l['name'], R=R, point_load_N=P))
    out['hoop'] = dict(rows=hoops, u=max(r['u'] for r in hoops), radius=hoops[0]['r'], count=4)
    # --- closure struts: axial force of C1 / C2 over their struts, along each strut
    struts = []
    for c in [c for c in coils(s) if c['group'] == 'closure']:
        sp = _group(parts, f'VTX_{c["name"]}_Strut_')[0]; a, b = sp['points']; L = math.dist(a, b)
        dx = b[0]-a[0]; Fa = cf[c['name']]['Fz_N']/g['coil_struts_per_coil']
        N = -Fa*L/dx
        struts.append(dict(check_tube(N, sp['radius'], L, m, s), coil=c['name'], axial_share_N=Fa))
    out['strut'] = dict(rows=struts, u=max(r['u'] for r in struts), radius=struts[0]['r'], count=2*g['coil_struts_per_coil'])
    # --- reaction ring and tie rods: frame FE
    ring = fe_reaction_ring(s, case)
    out['ring'] = dict(rows=[ring['ring']], u=ring['ring']['u'], radius=ring['ring']['r'], count=1, fe=ring['fe'])
    out['tie_rod'] = dict(rows=[ring['tie']], u=ring['tie']['u'], radius=ring['tie']['r'], count=len(_group(parts, 'VTX_Shield_Tie_Rod_')), fe=ring['fe'])
    # --- windings: hoop stress in the case share
    allow = coil_case_allowable(s)['allowable']
    out['winding'] = dict(rows=[dict(name=c['name'], stress=c['case_stress_Pa'], allowable=allow, u=c['case_stress_Pa']/allow, hoop_N=c['hoop_N'],
                                     current_At=c['current_At'], Fz_N=c['Fz_N'], a=c['a']) for c in cf.values()], count=6)
    out['winding']['u'] = max(r['u'] for r in out['winding']['rows'])
    # --- collar: the balance point of the two load paths (closure-coil compression in, cage tension out)
    clos = sum(cf[n]['Fz_N'] for n in ('C1', 'C2')); loops = sum(c['Fz_N'] for c in cf.values() if c['group'] == 'loop')
    out['collar'] = dict(closure_in_N=clos, cage_out_N=loops, net_N=clos+loops, count=1)
    return out


def fe_reaction_ring(s, case='NOMINAL', per_strut_deg=3.75, tie_split=2):
    """Frame FE of the coil reaction ring: the ring as beam elements on a grid of per_strut_deg, the twelve closure struts' forces applied
    at their seats (full 3D strut force), and the shield tie rods as beam chains to fixed collar points. Returns ring and tie-rod checks."""
    g = ve.config(s)['geometry']; parts = ve.parts(s); m = material(s, 'MAT-TI6AL4V'); cf = {c['name']: c for c in coil_forces(s, case)}
    rp = _group(parts, 'VTX_Coil_Reaction_Ring')[0]; R, a, x = rp['R'], rp['a'], rp['x']
    n = int(round(360/per_strut_deg)); f = fe.Frame(); sec = tube_section(a, s)
    ring = [f.node((x, R*math.cos(2*math.pi*k/n), R*math.sin(2*math.pi*k/n))) for k in range(n)]
    for k in range(n):
        f.beam(ring[k], ring[(k+1) % n], sec, m['E'], m['G'], name='ring', ref=(1.0, 0.0, 0.0))
    def nearest(p):
        az = math.degrees(math.atan2(p[2], p[1])) % 360
        return ring[int(round(az/per_strut_deg)) % n]
    for c in ('C1', 'C2'):
        Fa = cf[c]['Fz_N']/g['coil_struts_per_coil']
        for sp in _group(parts, f'VTX_{c}_Strut_'):
            a_, b_ = sp['points']; d = vc.sub(b_, a_); L = math.sqrt(vc.dot(d, d)); Nst = -Fa*L/d[0]
            # strut in compression pushes on the ring along its own direction (coil -> ring)
            f.load(nearest(b_), F=vc.mul(d, -Nst/L))
    ties = _group(parts, 'VTX_Shield_Tie_Rod_'); tsec = tube_section(ties[0]['radius'], s)
    for tp in ties:
        pts = tp['points']; prev = nearest(pts[0])
        for q in range(1, len(pts)):
            for k in range(1, tie_split+1):
                p = vc.add(pts[q-1], vc.mul(vc.sub(pts[q], pts[q-1]), k/tie_split))
                nd = f.node(p); f.beam(prev, nd, tsec, m['E'], m['G'], name=tp['name']); prev = nd
        f.fix(prev)
    res = f.solve()
    rf = [e for e in res['forces'] if e['name'] == 'ring']; tf = [e for e in res['forces'] if e['name'] != 'ring']
    rr = max(rf, key=lambda e: fe.stress(e, sec)); tt = max(tf, key=lambda e: fe.stress(e, tsec))
    ring_chk = check_tube(rr['N'], a, rr['L'], m, s, M=math.hypot(rr['My'], rr['Mz']))
    ring_chk['u_buckling'] = 0.0; ring_chk['u'] = ring_chk['u_strength']        # a closed ring under in-plane load: strength governs here
    tie_len = _len(ties[0]['points'])
    Nt = min(e['N'] for e in tf); Mt = max(math.hypot(e['My'], e['Mz']) for e in tf)
    tie_chk = check_tube(Nt, ties[0]['radius'], tie_len, m, s, M=Mt)
    tie_chk['peak_stress_fe'] = fe.stress(tt, tsec)
    react = [sum(r[i] for r in res['reactions'].values()) for i in range(3)]
    applied = [sum(L_[i] for L_ in f.loads.values()) for i in range(3)]
    return dict(ring=ring_chk, tie=tie_chk, fe=dict(nodes=len(f.nodes), elements=len(f.elements), dof=res['dof'], grid_deg=per_strut_deg,
                                                       ring_peak_M=math.hypot(rr['My'], rr['Mz']), ring_peak_N=rr['N'], tie_N=Nt, tie_M=Mt,
                                                       reaction_sum_N=react, applied_sum_N=applied))


def fe_ring_convergence(s, case='NOMINAL'):
    """Ring-model mesh study: 7.5, 3.75 and 1.875 degree grids (48, 96 and 192 ring elements)."""
    out = []
    for d in (7.5, 3.75, 1.875):
        r = fe_reaction_ring(s, case, per_strut_deg=d)
        out.append(dict(grid_deg=d, elements=r['fe']['elements'], ring_peak_M=r['fe']['ring_peak_M'], tie_N=r['fe']['tie_N'], tie_M=r['fe']['tie_M']))
    return out


# ---------- cluster frame (LC-01, LC-03, LC-06) -----------------------------------------------------------------------------------

def fe_cluster(s, loads, unit=None):
    """Frame FE of the cluster: every vertex_cluster.frame tube member as one element (hub and engines rigid: members hang on a hub node and
    on each engine's collar-centre node through rigid offsets), thrust-ring nodes fixed. loads: {engine n: (force, moment)} at the collar centre.
    Returns the solve with per-member checks (Ti-6Al-4V)."""
    c = vc.config(s); st = vc.stations(s); pls = vc.placements(s); est = ve.stations(s); m = material(s, 'MAT-TI6AL4V')
    mid = (est['collar_fwd']+est['collar_aft'])/2
    f = fe.Frame(); hub = f.node((st['collar'], 0.0, 0.0)); eng = {pl['n']: f.node(vc.to_ship(pl, (mid, 0, 0))) for pl in pls}
    rings = {}
    for k, nd in enumerate(vc.ring_nodes(s)):
        rings[k] = f.node(nd); f.fix(rings[k])
    cr = c['cradle_radius_m']
    def owner(p, name):
        """The master node a member end hangs on: a thrust-ring node, the hub (within its radius) or the nearest engine's cradle."""
        for k, nd in rings.items():
            if math.dist(p, f.nodes[nd]) < 1.0:                              # a strut foot (vertex_cluster.strut_foot) on this node
                return nd, None
        if abs(p[0]-st['collar']) < c['hub_length_m'] and math.hypot(p[1], p[2]) <= c['hub_radius_m']+0.05:
            return hub, vc.sub(p, f.nodes[hub])
        j = min(eng, key=lambda n: math.dist(p, f.nodes[eng[n]]))
        return eng[j], vc.sub(p, f.nodes[eng[j]])
    members = []
    for p in vc.frame(s):
        if p['shape'] != 'tube':
            continue
        a, b = p['points'][0], p['points'][-1]
        if 'Trunnion_Pin' in p['name']:
            continue
        (na, oa), (nb, ob) = owner(a, p['name']), owner(b, p['name'])
        if na == nb:
            continue
        sec = tube_section(p['radius'], s)
        f.beam(na, nb, sec, m['E'], m['G'], name=p['name'], o1=oa, o2=ob)
        members.append((p['name'], p['radius'], math.dist(a, b)))
    for n, (F, M) in loads.items():
        f.load(eng[n], F=F, M=M)
    res = f.solve(); rows = []
    for (name, r, L), e in zip(members, res['forces']):
        sec = tube_section(r, s); Mb = math.hypot(e['My'], e['Mz'])
        rows.append(dict(check_tube(e['N'], r, L, m, s, M=Mb), name=name, group=_cluster_group(name)))
    return dict(rows=rows, u=res['u'], engine_nodes=eng, hub=hub, dof=res['dof'], elements=len(f.elements), reactions=res['reactions'])


def _cluster_group(name):
    for key, g in (('Hub_Thrust_Strut', 'hub_thrust_strut'), ('Thrust_Strut', 'engine_thrust_strut'), ('Spoke', 'spoke'), ('Chord', 'chord'),
                   ('Flank_Tie', 'flank_tie')):
        if key in name:
            return g
    return 'other'


def cluster_load_sets(s):
    """LC-01/03/06 load sets on the four engines (ship frame, at each collar centre): thrust along each engine's +x and the exact
    inter-engine force and torque."""
    pls = vc.placements(s); T = next(r['compact'] for r in ve.calculations(s) if r['id'] == 'C-10')*1e6
    thrust = {pl['n']: vc.mul(pl['axes'][0], T) for pl in pls}
    def mag(case, off=()):
        return {r['engine']: (r['force_N'], r['torque_Nm']) for r in inter_engine(s, case, off=off)}
    nom, cons = mag('NOMINAL'), mag('CONSERVATIVE'); one_off = mag('NOMINAL', off=(2,))
    add = lambda a, b: tuple(x+y for x, y in zip(a, b))
    sets = {
        'LC01_THRUST_ALL': {n: (thrust[n], (0, 0, 0)) for n in thrust},
        'LC03_FIELD_NOMINAL+THRUST': {n: (add(thrust[n], nom[n][0]), nom[n][1]) for n in thrust},
        'LC03_FIELD_CONSERVATIVE+THRUST': {n: (add(thrust[n], cons[n][0]), cons[n][1]) for n in thrust},
        'LC06_N2_COILS_OFF': {n: (add(thrust[n], one_off[n][0]), one_off[n][1]) for n in one_off},
        'LC06_SINGLE_ENGINE_N1': {1: (thrust[1], (0, 0, 0))},
    }
    return sets, dict(nominal=nom, conservative=cons, n2_off=one_off, thrust_N=T)


def cluster_members(s):
    """Cluster frame checks per load set; per group the governing utilisation; engine-mount stiffness and the frame's lowest engine-rocking
    frequency estimate; magnetic negative stiffness between engines against it."""
    sets, mags = cluster_load_sets(s); out = {}
    for name, loads in sets.items():
        r = fe_cluster(s, loads)
        groups = {}
        for row in r['rows']:
            gr = groups.setdefault(row['group'], dict(u=0.0, row=None, count=0))
            gr['count'] += 1
            if row['u'] > gr['u']:
                gr['u'], gr['row'] = row['u'], row
        out[name] = dict(groups=groups, dof=r['dof'], elements=r['elements'])
    # stiffness: unit loads on N1 radial and lateral
    pls = vc.placements(s); pl = pls[0]; u_rad = vc.norm((0.0, pl['origin'][1], pl['origin'][2]))
    stiff = {}
    for key, d in (('radial', u_rad), ('axial', (1.0, 0.0, 0.0)), ('tangential', vc.norm(_cross((1.0, 0.0, 0.0), u_rad)))):
        P = 1.0e6; r = fe_cluster(s, {1: (vc.mul(d, P), (0, 0, 0))})
        stiff[key] = P/abs(vc.dot(r['u'][r['engine_nodes'][1]][:3], d))
    mass = ve_mass(s)
    freq = {k: math.sqrt(v/mass)/(2*math.pi) for k, v in stiff.items()}
    # magnetic stiffness between engines: change of the inward force with pitch (negative = destabilising)
    p0 = vc.config(s)['pitch_radius_m']; h = 0.05
    Fp = inter_engine(s, 'NOMINAL', pitch=p0+h)[0]['radial_N']; Fm = inter_engine(s, 'NOMINAL', pitch=p0-h)[0]['radial_N']
    k_mag = (Fp-Fm)/(2*h)              # dF_radial/dr; F_radial < 0 is inward; k_mag > 0 means the pull grows as the engine moves in
    return dict(cases=out, stiffness_N_m=stiff, engine_mass_kg=mass, frequency_Hz=freq, magnetic_stiffness_N_m=k_mag,
                magnetic_margin=stiff['radial']/abs(k_mag) if k_mag else None, magnetics=mags)


def ve_mass(s):
    return ve.mass_estimate(s)['total_kg']


def trunnion_check(s, cl):
    """Trunnion pins: the worst engine reaction (thrust + field, conservative) shared by the four pins in single shear (solid Ti-6Al-4V pin)."""
    m = material(s, 'MAT-TI6AL4V'); worst = 0.0
    for key in ('LC03_FIELD_NOMINAL+THRUST', 'LC03_FIELD_CONSERVATIVE+THRUST', 'LC06_N2_COILS_OFF'):
        for n, (F, M) in cluster_load_sets(s)[0][key].items():
            worst = max(worst, math.sqrt(vc.dot(F, F)))
    r = 0.22; A = math.pi*r*r; tau = worst/4/A; allow = m['allow_tension']/math.sqrt(3)
    return dict(load_N=worst, radius=r, shear=tau, allowable=allow, u=tau/allow)


# ---------- ME-03 electrical, ME-04 lithium, ME-05 target injection --------------------------------------------------------------

def electrical(s, case='NOMINAL'):
    """Lead and quench screen per coil: turns at the lead current, stored energy share, dump voltage for the dump time, go/return pair force
    and the force on a lead in the coil's own field (the lead pair cancels it as a couple)."""
    c = config(s); W, per = stored_energy(s, case); I0 = c['conductor_current_A']; rows = []
    for cf, w in zip(coil_forces(s, case), per):
        B = abs(cf['current_At'])*MU0/(2*cf['r'])
        rows.append(dict(name=cf['name'], turns=cf['turns'], energy_J=w, dump_voltage_V=2*abs(w)/(I0*c['quench_dump_time_s']),
                         pair_force_N_m=MU0*I0*I0/(2*math.pi*c['lead_pair_spacing_m']), field_force_N_m=I0*B, field_T=B,
                         couple_Nm_m=I0*B*c['lead_pair_spacing_m']))
    return dict(rows=rows, energy_J=W, lead_current_A=I0)


def lithium(s):
    """Hot-circuit screen: capacity of the drawn supply line, the fusion-power fraction it can carry, line hoop stress at the design pressure,
    and the 1800 K material verdict from the catalogue (no extrapolation)."""
    c = config(s); parts = ve.parts(s); sup = _group(parts, 'VTX_Lithium_Supply')[0]
    ri = sup['radius']-c['hot_line_wall_m']; A = math.pi*ri*ri
    Q = c['lithium_density_kg_m3']*c['lithium_max_velocity_m_s']*A*c['lithium_cp_J_kgK']*c['lithium_delta_T_K']
    P_fus = 0.25*next(r['research'] for r in ve.calculations(s) if r['id'] == 'C-03')*1e12
    sig = c['lithium_design_pressure_Pa']*ri/c['hot_line_wall_m']; T = c['hot_circuit_temperature_K']
    mats = {}
    for mid in ('MAT-NB1ZR', 'MAT-TZM', 'MAT-MORE', 'MAT-W'):
        q = mp.get_property(mid, 'max_service_temperature')
        mats[mid] = dict(status=q['status'], low=q['low'], high=q['high'],
                         verdict='OPEN' if not q['known'] else ('BELOW_1800K' if (q['high'] or 0) < T else 'RANGE_REACHES_1800K'))
    return dict(line_inner_radius_m=ri, capacity_W=Q, fusion_power_W=P_fus, capacity_fraction=Q/P_fus, hoop_stress_Pa=sig, temperature_K=T,
                materials=mats)


def target_injection(s):
    """Launcher pointing, time of flight, recoil per gram of target, and the bore shutter as a rotating chopper."""
    c = config(s); st = ve.stations(s); g = ve.config(s)['geometry']; parts = ve.parts(s)
    calc = {r['id']: r for r in ve.calculations(s)}
    f = calc['C-04']['compact']; v = calc['C-08']['compact']*1e3; muzzle = g['launcher_x_m'][1]
    flight = abs(st['burn']-muzzle); tof = flight/v
    sh = _group(parts, 'VTX_Bore_Shutter')[0]; rev = f/c['shutter_slots']; rim = 2*math.pi*sh['radius']*rev
    out = dict(pulse_Hz=f, speed_m_s=v, flight_m=flight, time_of_flight_s=tof, pointing_rad=c['target_miss_tolerance_m']/flight,
               recoil_N_per_g=v*1e-3*f, shutter_rev_s=rev, shutter_rim_m_s=rim, rim_limit_m_s=c['chopper_rim_speed_limit_m_s'],
               cycles_per_hour=f*3600, cycles_basis=f*3600*c['cycles_basis_h'])
    # rotating shutter in its drawn material: rim hoop stress ~ rho v^2 against the material's strength (OPEN for tungsten)
    q = mp.get_property('MAT-W', 'density', 293.0); out['shutter_rim_stress_W_Pa'] = mp.require(q)*rim*rim
    out['shutter_w_strength'] = mp.get_property('MAT-W', 'ultimate_strength', 293.0)['status']
    cf = material(s, 'MAT-CFRP'); out['shutter_rim_stress_cfrp_Pa'] = cf['density']*rim*rim; out['cfrp_allowable_Pa'] = cf['allow_tension']
    return out


def thermal(s):
    """Thermal movements the joints must take: cold-mass contraction of each coil (radial), LiH shield against titanium structure per 100 K,
    and the lithium headers' growth at the hot-circuit temperature (no catalogue expansion at 1800 K: bounded by an ESTIMATE range)."""
    c = config(s); out = dict(coil_contraction_m={})
    for cl in coils(s):
        out['coil_contraction_m'][cl['name']] = cl['r']*c['contraction_steel_293_20']
    a_lih = mp.require(mp.get_property('MAT-LIH', 'thermal_expansion', 293.0)); a_ti = mp.require(mp.get_property('MAT-TI6AL4V', 'thermal_expansion', 293.0))
    R = ve.config(s)['geometry']['shield_aft_radius_m']
    out['shield_vs_titanium_per_100K_m'] = R*(a_lih-a_ti)*100
    hdr = [p for p in ve.parts(s) if p['name'].endswith('_Armour_Header')]
    dT = c['hot_circuit_temperature_K']-c['structure_temperature_K']
    out['header_growth_m'] = {p['name']: (p['R']*5e-6*dT, p['R']*9e-6*dT) for p in hdr}
    out['header_alpha_basis'] = 'ESTIMATE 5-9e-6 /K (refractory alloys near 1800 K; not in the catalogue: every candidate\'s expansion is OPEN there)'
    return out


def dynamics(s, cl):
    """LC-04: pulse cycles, the frame's engine modes against the pulse rate, and the ripple a quasi-static mount transmits."""
    c = config(s); ti = target_injection(s); f = ti['pulse_Hz']
    fr = cl['frequency_Hz']; fmin = min(fr.values())
    trans = (fmin/f)**2/(1-(fmin/f)**2)
    hoop = {}
    m316 = mp.get_property('MAT-SS-316LN', 'density', 293.0)
    for cf in coils(s):
        # breathing mode of a ring: f = c / (2 pi R), c = sqrt(E / rho); 316LN modulus is OPEN in the catalogue, so Ti-6Al-4V's is not used:
        hoop[cf['name']] = None
    return dict(pulse_Hz=f, cycles_per_hour=ti['cycles_per_hour'], cycles_basis=ti['cycles_basis'], basis_h=c['cycles_basis_h'],
                lowest_mount_Hz=fmin, ratio=f/fmin, transmissibility=abs(trans), winding_breathing_Hz=hoop,
                winding_note='316LN cryogenic modulus is OPEN in the catalogue, so the winding breathing modes are not computed; the windings take the '
                             'pulse field change directly, so mount isolation does not protect them')


# ---------- the register --------------------------------------------------------------------------------------------------------

def load_cases(s):
    """LC-01 .. LC-06: what each load is, its size per case, where it enters and how this module treats it."""
    calc = {r['id']: r for r in ve.calculations(s)}; T = calc['C-10']['compact']*1e6
    cf = {k: {c['name']: c for c in coil_forces(s, k)} for k in config(s)['current_cases']}
    ie = {k: inter_engine(s, k) for k in ('NOMINAL', 'CONSERVATIVE')}
    dip = dipole_estimate(s)
    peak = lambda k: max(abs(c['Fz_N']) for c in cf[k].values())
    return [
        dict(id='LC-01', title='Thrust', evidence=calc['C-10']['evidence'], value_N=T, size=[('thrust per engine', T/1e6, 'MN')],
             path='burn -> field -> loops -> cage -> collar -> trunnions -> cradle -> struts -> thrust ring',
             note='C-10 thrust per engine; SPECULATIVE (research exhaust velocity carried over). It acts on the loops as part of their field load.'),
        dict(id='LC-02', title='Coil forces (steady, coils energised)', evidence='CALCULATED', value_N=peak('NOMINAL'),
             size=[(f'largest coil force {k}', peak(k)/1e6, 'MN') for k in cf], path='C1/C2 -> struts -> reaction ring -> tie rods -> collar; L1-L4 -> seats -> hoops -> longerons -> collar',
             note='Exact loop-to-loop forces of the six coils (no third closure coil). Internal to one engine: they sum to zero, but every member between '
                  'the coils carries them. They exceed the thrust by about 300 times.'),
        dict(id='LC-03', title='Inter-engine field force (steady)', evidence='CALCULATED', value_N=abs(ie['NOMINAL'][0]['radial_N']),
             size=[(f'pull on each engine {k}', abs(v[0]['radial_N'])/1e6, 'MN') for k, v in ie.items()], path='coils -> engine -> trunnions -> cradle -> spokes / chords -> hub',
             note=f'Exact coil-set forces: each engine is pulled toward the axis (neighbours of opposite polarity attract side by side). '
                  f'The 1.1 cluster note called it repulsion and a pulse transient; it is attraction and steady while the coils are energised. '
                  f'Point-dipole pair estimate {dip["adjacent_N"]/1e6:.1f} MN adjacent. Net external force zero by symmetry; internal frame loads remain.'),
        dict(id='LC-04', title='Pulse loads at 5.7 kHz', evidence=calc['C-04']['evidence'], value_N=T/calc['C-04']['compact'],
             size=[('impulse per pulse', T/calc['C-04']['compact'], 'N s'), ('pulse rate', calc['C-04']['compact'], 'Hz')], path='field compression on the windings each pulse; mount transmits the ripple',
             note='Each pulse delivers thrust/f of impulse. Cycle count per firing hour exceeds measured S-N data for every catalogue structural alloy; '
                  'the pulse field change on the windings (EXTREME case) is a fatigue load with an OPEN pulse shape.'),
        dict(id='LC-05', title='Thermal', evidence=calc['C-05']['evidence'], value_N=None, size=[('heat flux against research', calc['C-05']['compact'], 'x')],
             path='armour -> lithium headers -> manifold -> service panel -> cluster heat exchanger',
             note='The design areal heat load is 29 times the research armour value (VTX-S3). Cold-mass contraction, hot headers and the LiH shield '
                  'each need sliding or flexible joints.'),
        dict(id='LC-06', title='Operations: single engine, coil loss, maintenance', evidence='CALCULATED', value_N=T*vc.config(s)['pitch_radius_m'],
             size=[('one engine\'s thrust moment', T*vc.config(s)['pitch_radius_m']/1e6, 'MN m')], path='cluster frame; ship attitude control',
             note='One engine firing gives a thrust moment about the ship axis; one engine\'s coils off unbalances the field forces on its neighbours.'),
    ]


# ---------- sizing summary, statuses, mass ---------------------------------------------------------------------------------------

def sizing(s):
    """The whole screen: engine members per current case, cluster frame, trunnions, electrical, lithium, target injection, thermal, dynamics."""
    cases = config(s)['current_cases']
    eng = {k: engine_members(s, k) for k in cases}
    cl = cluster_members(s)
    return dict(engine=eng, cluster=cl, trunnion=trunnion_check(s, cl), electrical=electrical(s), lithium=lithium(s), target=target_injection(s),
                thermal=thermal(s), dynamics=dynamics(s, cl), stiffness=axial_stiffness(s, config(s)['design_case']))


# ---------- design iteration (used to set the 1.2 parameters; the build reads data/wayfarer_3d.toml only) ----------------------------

ENGINE_KEYS = dict(longeron='cage_longeron_radius_m', seat='loop_seat_radius_m', hoop='cage_hoop_minor_m', strut='coil_strut_radius_m',
                   ring='reaction_ring_minor_m', tie_rod='tie_rod_radius_m')
CLUSTER_KEYS = dict(spoke=('member_radius_m', 1.0), chord=('member_radius_m', 1.0), flank_tie=('member_radius_m', 0.8),
                    hub_thrust_strut=('thrust_strut_radius_m', 1.0), engine_thrust_strut=('thrust_strut_radius_m', 1.2))
DESIGN_SETS = ('LC01_THRUST_ALL', 'LC03_FIELD_NOMINAL+THRUST', 'LC06_N2_COILS_OFF', 'LC06_SINGLE_ENGINE_N1')
BASE_CLEARANCE = (0.45, 0.22)        # 1.1 cage clearance at the 1.1 longeron radius: the gap from cryostat to longeron surface is kept


def cage_clearance(g):
    """Cage clearance that keeps the 1.1 cryostat-to-longeron gap and room for the cage lines inside the hoops (vertex_engine.service_offsets)."""
    return round(max(BASE_CLEARANCE[0]+g['cage_longeron_radius_m']-BASE_CLEARANCE[1], g['cage_hoop_minor_m']+0.28), 6)


def with_sizes(s, engine=None, cluster=None):
    """A copy of the spec with engine geometry and cluster member sizes replaced (the cage clearance follows the longeron radius)."""
    t = copy.deepcopy(s); g = t['vertex_engine']['geometry']
    for k, v in (engine or {}).items():
        g[k] = v
    g['cage_clearance_m'] = cage_clearance(g)
    for k, v in (cluster or {}).items():
        t['propulsion_cluster'][k] = v
    return t


def required_sizes(s, step=0.01):
    """Smallest radii (step grid) that bring every member group to utilisation <= 1 in the design case, for the geometry of s."""
    m = material(s, 'MAT-TI6AL4V'); em = engine_members(s, config(s)['design_case']); eng = {}
    for grp, key in ENGINE_KEYS.items():
        r = 0.0
        for row in em[grp]['rows']:
            if grp == 'ring':
                sec_r = row['r']
                while check_tube(row['N'], sec_r, row['L'], m, s, M=row['M'])['u_strength'] > 1.0:
                    sec_r = round(sec_r+step, 6)
                r = max(r, sec_r)
            else:
                r = max(r, size_tube(row['N'], row['L'], m, s, M=row.get('M', 0.0), step=step))
        eng[key] = r
    cl = cluster_members(s); clus = {}
    for name in DESIGN_SETS:
        for grp, d in cl['cases'][name]['groups'].items():
            if grp not in CLUSTER_KEYS or not d['row']:
                continue
            key, f = CLUSTER_KEYS[grp]; row = d['row']
            r = size_tube(row['N'], row['L'], m, s, M=row['M'], step=step)/f
            clus[key] = max(clus.get(key, 0.0), math.ceil(r/step-1e-9)*step)
    return eng, clus


def iterate_sizes(s, rounds=6):
    """Resize until the radii stop changing (member forces depend on the member stiffness through the FE screens). Radii only grow."""
    t = s; hist = []
    for _ in range(rounds):
        eng, clus = required_sizes(t)
        g = t['vertex_engine']['geometry']; c = t['propulsion_cluster']
        eng = {k: round(max(v, g[k] if k in g else 0.0), 6) for k, v in eng.items()}
        clus = {k: round(max(v, c[k]), 6) for k, v in clus.items()}
        hist.append((eng, clus))
        if all(abs(g[k]-v) < 1e-9 for k, v in eng.items()) and all(abs(c[k]-v) < 1e-9 for k, v in clus.items()):
            break
        t = with_sizes(t, eng, clus)
    return t, hist


# ---------- statuses, per-part engineering records, mass, clearances --------------------------------------------------------------

GROUP_STATUS = dict(longeron='ANALYTICALLY_SIZED', hoop='ANALYTICALLY_SIZED', seat='CONDITIONALLY_SIZED', strut='ANALYTICALLY_SIZED',
                    ring='FEA_SCREENED', tie_rod='FEA_SCREENED', winding='CONDITIONALLY_SIZED')
GROUP_TITLES = dict(longeron='Cage longerons', hoop='Cage hoops', seat='Loop seats', strut='Closure-coil struts', ring='Coil reaction ring',
                    tie_rod='Shield tie rods', winding='Coil windings (case)')
GROUP_OF = (('VTX_Cage_Longeron_', 'longeron'), ('VTX_Cage_Hoop_', 'hoop'), ('VTX_Loop_Seat_', 'seat'), ('VTX_C1_Strut_', 'strut'),
            ('VTX_C2_Strut_', 'strut'), ('VTX_Coil_Reaction_Ring', 'ring'), ('VTX_Shield_Tie_Rod_', 'tie_rod'), ('_Winding', 'winding'))
# Non-member parts: (name test, status, note key). First match wins.
OTHER_STATUS = (
    ('HOT_THERMAL', 'BLOCKED', 'lithium'), ('VTX_Thrust_Collar', 'UNSIZED', 'collar'), ('VTX_Trunnion_', 'ANALYTICALLY_SIZED', 'trunnion'),
    ('VTX_Shadow_Shield', 'UNSIZED', 'shield'), ('VTX_Shield_Burn_Face', 'SPECULATIVE', 'heat'), ('_Armour_', 'SPECULATIVE', 'heat'),
    ('_LiH_Nose', 'SPECULATIVE', 'heat'), ('_Cryostat', 'UNSIZED', 'cryostat'), ('_Segment_', 'UNSIZED', 'cryostat'), ('_Joint_', 'UNSIZED', 'joint'),
    ('VTX_Burn_Chamber_Marker', 'SPECULATIVE', 'burn'), ('VTX_Target_Launcher', 'SPECULATIVE', 'launcher'), ('VTX_Bore_Shutter', 'BLOCKED', 'shutter'),
    ('VTX_Launcher_', 'CONDITIONALLY_SIZED', 'alignment'), ('VTX_Driver_', 'SPECULATIVE', 'driver'), ('VTX_Pulse_Pod_', 'SPECULATIVE', 'pulsed'),
    ('_Lead_', 'CONDITIONALLY_SIZED', 'leads'), ('VTX_Coil_Current_Leads', 'CONDITIONALLY_SIZED', 'leads'),
    ('CRYOGENIC', 'UNSIZED', 'cryo'), ('', 'UNSIZED', 'nonstructural'),
)


def notes(s, sz):
    """Short engineering notes per status reason, with the numbers of this spec (shared by the report, the pages and the viewer)."""
    em = sz['engine']['NOMINAL']; li = sz['lithium']; ti = sz['target']; tr = sz['trunnion']; el = sz['electrical']
    cl = em['collar']['closure_in_N']
    return dict(
        longeron='Compression and Euler buckling between hoops under the loop forces; NOMINAL coils.',
        hoop='Ring bending under the eight seats\' radial share (closed form P R/2 (1/a - cot a)).',
        seat='Inclined strut carrying its loop\'s axial share. The cold-mass support behind it carries the same force; its heat leak is OPEN.',
        strut='Compression and buckling: the closure coil is pushed forward by the loops.',
        ring='Frame FE (ring + tie rods, converged on 3.75 deg): twelve strut seats, eight tie rods.',
        tie_rod='Frame FE: the kink round the shield rim puts the rods in bending as well as compression.',
        winding='Hoop tension in the steel case share (316LN, 2/3 of the 4.2 K proof stress); sized for NOMINAL only.',
        collar=f'Balance point: {cl / 1e6:.0f} MN in from the closure struts, the same out through the cage. Flange and lug design OPEN.',
        trunnion=f'Pin shear: worst engine reaction {tr["load_N"] / 1e6:.0f} MN over four pins, utilisation {tr["u"]:.2f}.',
        shield='Carries no coil load by design (tie rods go round it). LiH grows {:.0f} mm more than titanium per 100 K at the rim: sliding seats.'.format(
            1000*sz['thermal']['shield_vs_titanium_per_100K_m']),
        heat='Design heat flux 29x the research armour load (VTX-S3): no material in the catalogue covers it.',
        cryostat='Vacuum vessel; the cold-mass supports inside carry the coil forces (OPEN).',
        joint='Segment split flange; the winding inside is continuous, so the joint carries no hoop load. Local design OPEN.',
        burn='No hardware: the burn is in the open field.',
        launcher=f'{ti["speed_m_s"] / 1e3:.1f} km/s at {ti["pulse_Hz"]:.0f} Hz (VTX-S2); recoil {ti["recoil_N_per_g"] / 1e3:.0f} kN per gram of target (target mass OPEN).',
        shutter=f'As a {config(s)["shutter_slots"]}-slot tungsten chopper the rim runs {ti["shutter_rim_m_s"]:.0f} m/s: rho v^2 = {ti["shutter_rim_stress_W_Pa"] / 1e9:.1f} GPa, '
                f'tungsten strength OPEN. A CFRP rotor would see {ti["shutter_rim_stress_cfrp_Pa"] / 1e6:.0f} MPa (allowable {ti["cfrp_allowable_Pa"] / 1e6:.0f}), radiation tolerance OPEN.',
        alignment=f'Pointing {ti["pointing_rad"] * 1e6:.0f} microrad holds a {config(s)["target_miss_tolerance_m"] * 1e3:.0f} mm miss over {ti["flight_m"]:.1f} m; actuator loads OPEN (target mass).',
        driver='Driver and final optics: SPECULATIVE (VTX-S1).', pulsed='Pulsed power at the design rate: SPECULATIVE.',
        leads=f'{el["lead_current_A"] / 1e3:.0f} kA leads; {el["energy_J"] / 1e9:.1f} GJ stored per engine; go/return pair force '
              f'{el["rows"][0]["pair_force_N_m"] / 1e3:.1f} kN/m (clamped pair).',
        lithium=f'At {li["temperature_K"]:.0f} K no catalogue alloy has a service rating (Nb-1Zr stops near 1400 K); one supply line carries '
                f'{100 * li["capacity_fraction"]:.4f} % of the fusion power (VTX-S3).',
        cryo='Cryogen flow and the cold heat budget are OPEN.', nonstructural='Not on a primary load path; not sized.')


def status_of(part, sz):
    """(status, member group or None, note key, NOMINAL utilisation, CONSERVATIVE utilisation) of one engine part."""
    name = part['name']
    for key, grp in GROUP_OF:
        if key in name:
            rows = lambda case: sz['engine'][case][grp]['rows']
            pick = lambda rs: [r for r in rs if r.get('loop', r.get('coil', r.get('name'))) and r.get('loop', r.get('coil', r.get('name'))) in name] or rs
            un = max(r['u'] for r in pick(rows('NOMINAL'))); uc = max(r['u'] for r in pick(rows('CONSERVATIVE')))
            st = GROUP_STATUS[grp] if un <= 1.0 else 'BLOCKED'
            return st, grp, grp, un, uc
    for key, st, note in OTHER_STATUS:
        if key in name or key == part['category']:
            if note == 'trunnion':
                return st, None, note, sz['trunnion']['u'], None
            return st, None, note, None, None
    raise AssertionError(name)


def part_engineering(s, sz=None):
    """Engineering record of every engine part (vertex_engine.parts order): status, member group, note key, utilisation per case."""
    sz = sz or sizing(s)
    out = []
    for p in ve.parts(s):
        st, grp, note, un, uc = status_of(p, sz)
        out.append(dict(name=p['name'], status=st, group=grp, note=note, u_nominal=un, u_conservative=uc))
    return out


def _with_1_1(s):
    t = with_sizes(s, {k: v for k, v in ENGINE_1_1.items() if k != 'loop_seat_offset_m'}, CLUSTER_1_1)
    t['vertex_engine']['geometry']['cage_clearance_m'] = BASE_CLEARANCE[0]
    for l in t['vertex_engine']['geometry']['loops']:
        l['seat_offset_m'] = 0.0
    return t


def frame_mass(s):
    mt = ve.config(s)['materials']
    return sum(ve._volume(p)*mt['density_kg_m3']['structure']*mt['solid_fraction']['structure'] for p in vc.frame(s) if p['material'] == 'structure')


def mass_rollup(s):
    """Engine mass by category and cluster frame mass, 1.1 drawn sizes against 1.2 sized ones (ENGINEERING_PROTOTYPE estimates; the ship's
    mass budget does not read them)."""
    old = _with_1_1(s); a, b = ve.mass_estimate(old), ve.mass_estimate(s)
    return dict(engine_1_1_kg=a['total_kg'], engine_1_2_kg=b['total_kg'], by_category_1_1=a['by_category'], by_category_1_2=b['by_category'],
                frame_1_1_kg=frame_mass(old), frame_1_2_kg=frame_mass(s), engines=vc.config(s)['engine_count'])


def _samples(p, step=0.1):
    if p['shape'] == 'tube':
        out = []
        for a, b in zip(p['points'], p['points'][1:]):
            n = max(1, int(math.dist(a, b)/step))
            out += [vc.add(a, vc.mul(vc.sub(b, a), i/n)) for i in range(n+1)]
        return out, p['radius']
    if p['shape'] in ('torus',):
        lo, hi = p.get('arc', (0.0, 360.0)); n = max(8, int(math.radians(hi-lo)*p['R']/step))
        return [ve.pol(p['x'], p['R'], lo+(hi-lo)*i/n) for i in range(n+1)], p['a']
    return None, None


def clearances(s, stems=('VTX_Cage_Longeron_1', 'VTX_Loop_Seat_L1_2', 'VTX_C2_Strut_1', 'VTX_Shield_Tie_Rod_1', 'VTX_Coil_Reaction_Ring'), ends=0.9):
    """Smallest surface gap (m) between each sized member and every non-structural tube or torus part (feeders, leads, cryogen lines,
    cryostats, armour), ignoring ends+radius near the member's own end points where it seats by design. Negative = interference."""
    parts = ve.parts(s); out = {}
    others = [p for p in parts if p['category'] not in ('STRUCTURE',) and p['shape'] in ('tube', 'torus')]
    cache = {p['name']: _samples(p) for p in others}
    for name in stems:
        p = next(q for q in parts if q['name'] == name); pts, r = _samples(p)
        ends_ = [p['points'][0], p['points'][-1]] if p['shape'] == 'tube' else []
        best = (1e9, None); tag = next((w for w in name.split('_') if w in ('C1', 'C2', 'L1', 'L2', 'L3', 'L4')), None)
        for q in others:
            if tag and f'_{tag}_' in q['name']+'_' and any(k in q['name']+'_' for k in ('_Cryostat_', '_Segment_', '_Joint_', '_Winding_')):
                continue
            qs, rq = cache[q['name']]
            for a in pts:
                if any(math.dist(a, e) < ends+r for e in ends_):
                    continue
                d = min(math.dist(a, b) for b in qs)-r-rq
                if d < best[0]:
                    best = (d, q['name'])
        out[name] = dict(gap_m=best[0], against=best[1])
    return out


def report(s):
    """Everything the release report, the engineering page and the inspection manifest read."""
    sz = sizing(s)
    return dict(version=config(s)['version'], load_cases=load_cases(s), sizing=sz, parts=part_engineering(s, sz), notes=notes(s, sz),
                mass=mass_rollup(s), materials=material_table(s), ring_convergence=fe_ring_convergence(s), case_allowable=coil_case_allowable(s),
                dipole=dipole_estimate(s))


if __name__ == '__main__':
    from spec import load
    S = load(Path(__file__).resolve().parents[2])[0]
    R = report(S); sz = R['sizing']
    print(f"Vertex structure {R['version']}: load cases")
    for lc in R['load_cases']:
        print(f"  {lc['id']} {lc['title']:<44} {lc['evidence']:<12} " + '; '.join(f'{a} {v:,.4g} {u}' for a, v, u in lc['size']))
    print('Coil forces (NOMINAL):')
    for c in coil_forces(S, 'NOMINAL'):
        print(f"  {c['name']} {c['current_At'] / 1e6:7.2f} MA-turn  Fz {c['Fz_N'] / 1e6:8.1f} MN  hoop {c['hoop_N'] / 1e6:6.1f} MN  case {c['case_stress_Pa'] / 1e6:5.0f} MPa")
    print('Engine members (utilisation NOMINAL / CONSERVATIVE / EXTREME):')
    for grp in ENGINE_KEYS:
        us = [sz['engine'][k][grp]['u'] for k in config(S)['current_cases']]
        print(f"  {GROUP_TITLES[grp]:<22} r {sz['engine']['NOMINAL'][grp]['radius']:.2f} m  " + ' / '.join(f'{u:.2f}' for u in us))
    print('  Coil windings           ' + ' / '.join(f"{sz['engine'][k]['winding']['u']:.2f}" for k in config(S)['current_cases']))
    print('Cluster frame (governing utilisation per load set):')
    for name, case in sz['cluster']['cases'].items():
        print(f"  {name:<32} " + '  '.join(f"{g} {d['u']:.2f}" for g, d in case['groups'].items() if g != 'other'))
    print(f"  mount frequencies {', '.join(f'{k} {v:.2f} Hz' for k, v in sz['cluster']['frequency_Hz'].items())}; magnetic margin {sz['cluster']['magnetic_margin']:.0f}")
    m = R['mass']
    print(f"Mass per engine {m['engine_1_1_kg'] / 1e3:,.0f} t (1.1) -> {m['engine_1_2_kg'] / 1e3:,.0f} t (1.2); frame {m['frame_1_1_kg'] / 1e3:,.0f} -> {m['frame_1_2_kg'] / 1e3:,.0f} t")
    counts = {}
    for p in R['parts']:
        counts[p['status']] = counts.get(p['status'], 0)+1
    print('Statuses:', ', '.join(f'{k} {v}' for k, v in sorted(counts.items())))


# ---------- inspection (Explore Ship engineering overlay) -------------------------------------------------------------------------

STATUS_STYLE = {      # overlay colours for the engineering overlay (review colours, named in text beside every swatch)
    'ANALYTICALLY_SIZED': ('Sized by calculation', (0.18, 0.62, 0.36)),
    'CONDITIONALLY_SIZED': ('Sized under stated conditions', (0.85, 0.65, 0.13)),
    'FEA_SCREENED': ('Frame FE screen', (0.13, 0.55, 0.72)),
    'UNSIZED': ('Not sized', (0.55, 0.57, 0.60)),
    'BLOCKED': ('Blocked', (0.82, 0.22, 0.20)),
    'SPECULATIVE': ('Speculative', (0.58, 0.40, 0.75)),
}


def inspection(s, sz=None):
    """The engineering block of the Explore Ship inspection manifest and one compact record per part (vertex_engine.parts order): every
    number the viewer shows comes from here, never typed into the viewer."""
    sz = sz or sizing(s); cases = config(s)['current_cases']; nt = notes(s, sz)
    groups = {}
    for grp in ENGINE_KEYS.keys() | {'winding'}:
        rows = sz['engine']['NOMINAL'][grp]['rows']
        top = max(rows, key=lambda r: r['u'])
        groups[grp] = dict(title=GROUP_TITLES[grp], status=GROUP_STATUS[grp] if top['u'] <= 1 else 'BLOCKED', count=sz['engine']['NOMINAL'][grp]['count'],
                           material='MAT-SS-316LN' if grp == 'winding' else 'MAT-TI6AL4V',
                           radius_m=None if grp == 'winding' else round(sz['engine']['NOMINAL'][grp]['radius'], 3),
                           u={k: round(sz['engine'][k][grp]['u'], 3) for k in cases}, governs=top.get('governs', 'hoop stress'),
                           force_MN=round((top.get('N') if 'N' in top else top['hoop_N'])/1e6, 2), note=nt[grp])
    recs = [[p['status'], p['note'], None if p['u_nominal'] is None else round(p['u_nominal'], 3),
             None if p['u_conservative'] is None else round(p['u_conservative'], 3), p['group']] for p in part_engineering(s, sz)]
    lc = [dict(id=x['id'], title=x['title'], evidence=x['evidence'], size=[[a, round(v, 4), u] for a, v, u in x['size']], note=x['note'])
          for x in load_cases(s)]
    m = mass_rollup(s)
    return dict(version=config(s)['version'], design_case=config(s)['design_case'], cases=cases,
                disclaimer='Engineering overlay: sizing status and member utilisation from a screening calculation (vertex_structure), not a certified '
                           'stress analysis. Colours mark status only; no field or stress is drawn. Structural plausibility is not propulsion '
                           'evidence: the drive itself stays SPECULATIVE and the research Gate 2 stays BLOCKED.',
                statuses=[dict(id=k, label=v[0], color=list(v[1])) for k, v in STATUS_STYLE.items()], notes=nt, groups=groups, load_cases=lc,
                mass=dict(engine_1_1_t=round(m['engine_1_1_kg']/1e3, 1), engine_1_2_t=round(m['engine_1_2_kg']/1e3, 1),
                          frame_1_1_t=round(m['frame_1_1_kg']/1e3, 1), frame_1_2_t=round(m['frame_1_2_kg']/1e3, 1)),
                record='[status, note key, utilisation NOMINAL, utilisation CONSERVATIVE, member group]'), recs
