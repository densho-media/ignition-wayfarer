"""Vertex Engine 1.6A: Fiji magnetic physics, advanced material limits and architecture reconciliation (owner brief 2026-11-15 21:52Z,
`[vertex_fiji_a]`).

Research only. Engine 1.6 (`vertex_fiji`, its table and evidence) is the historical record and is read, never changed; the released engine
(four independent Compact Vertex engines, M0-NOMINAL, 1.2 geometry) is the reference. Order of work, as the brief asks:

  A  audit: what set 1.6's numbers (the 3.5 T bound, the optimal-orientation kernel, the liner geometry) and which assumptions dominate;
  B  material cases FM-1..FM-4 (2.45, 3.5, 5, 10 T): the moment per atom each needs and where it leaves established physics;
  C  the canon law B_eff = B_seed A_B(T) under three readings, and a successor law B_total(r, T) = B_coils(r) + B_Fiji(r; M(T)) that keeps
     the canon temperature shape (cold, activation, rise, saturation, degradation, collapse) and adds no field multiplier;
  D  an axisymmetric bound-current magnetostatic solver (uniform-M cells -> surface currents -> Gauss-Legendre loops, exact loop fields),
     validated against analytic cases, with two constitutive modes: SEEDED (M follows the local H, the one Fiji property) and ORIENTED
     (a fixed easy axis, which needs a coercivity the brief does not grant: reported as a requirement);
  E  geometries FG-0..FG-5 x FM-1..FM-4 x mode: field at the burn, topology, energies, forces, stresses, demagnetization, coil-current
     changes on collapse, mass; FG-3 solves the loop scale and the Fiji strength that replace the closure coils;
  F  photon, neutron and charged exposure by ray screen on the 1.5 hardware, the radiator consequence, temperatures, thermal feedback and
     collapse; an independent REBCO neutron audit with mitigations (kept OPEN);
  G  separate gates (magnetic, plasma, radiation survival, thermal closure, mission), a machine-readable matrix and its Pareto set.

Standard library only (the brief's open-source FEM tools were evaluated and cannot be installed in this environment; see `solver_choice`).
Evidence per result: MEASURED_REFERENCE, SCREENING_BOUND, SPECULATIVE, EXTREME_SPECULATIVE, LITERATURE_RANGE, ANALYTIC, PROTOTYPE,
REDUCED_MODEL, CANON_WORKING.

python3 src/wayfarer/vertex_fiji_a.py [--evidence]"""
import hashlib
import json
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import material_physics as mp  # noqa: E402
import vertex_engine as ve  # noqa: E402
import vertex_fiji as vf  # noqa: E402
import vertex_magnet as vm  # noqa: E402
import vertex_radiation as vr  # noqa: E402
import vertex_structure as vs  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_PATH = ROOT/'references'/'evidence'/'vertex_fiji_a.json'
MU0 = vs.MU0
MU_B = 9.2740100783e-24
AMU = 1.66053906660e-27
K_HALBACH = 4.0/3.0
MODES = ('SEEDED', 'ORIENTED')


def config(s):
    return s['vertex_fiji_a']


def fcfg(s):
    return vf.config(s)


# ---------- A: audit of 1.6 ---------------------------------------------------------------------------------------------------------------

def audit(s):
    """Answers to the brief's audit questions 1-8, with the numbers behind them read from the 1.6 evidence (unchanged)."""
    R = json.loads(vf.EVIDENCE_PATH.read_text()); f = fcfg(s); burn = R['field']['targets']['burn']
    case = burn['cases'][f"{f['liner_section_m'][1]:g}"]
    return [
        dict(q=1, question='Why 3.5 T?', evidence='LITERATURE_RANGE',
             answer='1.6 set mu0 Ms to the highest polarization any known material reaches: about 3.5 T, the 4f moments of Dy and Ho '
                    '(about 10 Bohr magnetons per atom at their density, measured only near 4 K). Fe65Co35 (2.45 T) is the room-temperature '
                    'record; the canon temperature shape was kept and only its magnitude was capped.'),
        dict(q=2, question='Screening limit or fundamental limit?', evidence='THEORETICAL',
             answer='A screening limit. Nothing fundamental stops more moment per atom: an atom with all d spins aligned gives 5 Bohr '
                    'magnetons (about 5 T at iron density), and aligning every electron would give about 26 T, which Pauli pairing of the core '
                    'shells forbids. 3.5 T is the edge of established materials, not of physics.'),
        dict(q=3, question='What does the amplification law define?', evidence='CANON_WORKING',
             answer=f"Fiji 05_LATTICE_LAW defines A_B(T) as a smoothstep from 1 below {f['T_activation_K']:g} K to {f['A_max']:g} at "
                    f"{f['T_saturation_K']:g} K (26.34 at 1000 K) and B_eff = B_seed A_B. 1.6 read A_B as the ratio Ms(T)/Ms(cold), a material "
                    'property; read as a field gain it has no geometry, no volume and no energy source, so it is not a field law (section C).'),
        dict(q=4, question='Did the geometry constrain the result?', evidence='REDUCED_MODEL',
             answer=f"Yes, mostly. The 0.2 m liners sit 2-8 m from the burn; their geometry factor is G = {case['G_optimal']:.2e}, so even "
                    f"the canon field would need mu0 Ms = {case['mu0Ms_for_canon_T']:.0f} T there. A 2-30 m shell (G = 4.7) still needed "
                    f"{burn['shell']['30']['mu0Ms_for_canon_T']:.0f} T. The volume close to the burn, not the material, sets the field."),
        dict(q=5, question='Is the orientation realizable?', evidence='REDUCED_MODEL',
             answer='Not with the 1.6 constitutive law alone. 1.6 used the optimal dipole orientation at every point (times a texture and a '
                    '16-segment factor) but magnetized the material with tanh(B_seed/B_align), i.e. a seeded, field-following material. A fixed '
                    'orientation against the local field needs a coercivity (anisotropy field) the brief does not grant. 1.6A computes both: '
                    'SEEDED (M along the local H, one property) and ORIENTED (a fixed easy axis, with the coercivity it would need).'),
        dict(q=6, question='Were demagnetizing fields, mutual interactions and mechanical loads included?', evidence='REDUCED_MODEL',
             answer='Partly. 1.6 integrated the dipole kernel for the field at a target outside the material (exact there) and the force from '
                    'the coil-field gradient, but no demagnetizing field, no liner-to-liner interaction, no self-consistent M, and no flux '
                    'conservation in the coils on collapse. 1.6A adds all four.'),
        dict(q=7, question='What changes outside the range of known materials?', evidence='THEORETICAL',
             answer='Field, energy and force scale with mu0 Ms (linearly at fixed geometry, forces and self-energy with its square). Above about '
                    '2.5 T the moment per atom passes the Slater-Pauling maximum of metallic alloys; above about 5 T it passes a full d shell at '
                    'iron density; 10 T needs rare-earth moments at transition-metal density. At 1000 K no known hard magnet keeps coercivity '
                    '(Nd2Fe14B, FePt and SmCo5 lose their order at about 590, 750 and 1020 K).'),
        dict(q=8, question='Which assumptions dominate the conclusions?', evidence='REDUCED_MODEL',
             answer='In order: (1) the Fiji volume and its distance from the burn (field falls as distance cubed); (2) the 1.5 photon power, '
                    'which makes every surface in line of sight thermally infeasible whatever its material; (3) the fast-neutron fluence limit '
                    'of REBCO; (4) mu0 Ms; (5) whether a fixed orientation is allowed. The radiator ratio is set by (2), not by Fiji.'),
    ]


# ---------- B: material cases ------------------------------------------------------------------------------------------------------------

def tesla_per_bohr(s):
    """mu0 n mu_B for an iron-like Fiji: the polarization (T) of one Bohr magneton per atom at the Fiji density."""
    c = config(s); n = fcfg(s)['density_kg_m3']/(c['atom_mass_amu']*AMU)
    return MU0*n*MU_B, n


def material_cases(s):
    c = config(s); f = fcfg(s); t, n = tesla_per_bohr(s); top = t*c['electrons_per_atom']; rows = []
    frac = vf.state(f, f['T_operating_K'])[0]
    for m in c['material_cases']:
        mu = m['mu0_Ms_T']/t
        rows.append(dict(m, bohr_per_atom=mu, share_of_formal_bound=m['mu0_Ms_T']/top, mu0M_operating_T=m['mu0_Ms_T']*frac,
                         self_pressure_Pa=m['mu0_Ms_T']**2/(2*MU0), energy_density_J_m3=m['mu0_Ms_T']**2/(2*MU0),
                         beyond_slater_pauling=mu > 2.5, beyond_d_shell=mu > 5.0, established=m['status'] == 'MEASURED_REFERENCE'))
    return dict(tesla_per_bohr=t, atom_density_m3=n, formal_bound_T=top, operating_fraction=frac, rows=rows,
                note='Polarization per Bohr magneton per atom at the Fiji density (iron-like). The temperature shape is the canon lattice law '
                     'for every case; only the magnitude changes (one property). No case is claimed to exist and none is a canon value.')


def ms_op(s, mu0Ms, T=None):
    f = fcfg(s); T = f['T_operating_K'] if T is None else T
    return mu0Ms/MU0*vf.state(f, T)[0]


# ---------- D: bound-current solver ------------------------------------------------------------------------------------------------------

_GL = {}


def gauss(n):
    """Gauss-Legendre nodes and weights on [-1, 1] (Newton on P_n), cached."""
    if n not in _GL:
        xs, ws = [], []
        for i in range(1, n+1):
            z = math.cos(math.pi*(i-0.25)/(n+0.5)); dp = 1.0
            for _ in range(100):
                p0, p1 = 1.0, z
                for k in range(2, n+1):
                    p0, p1 = p1, ((2*k-1)*z*p1-(k-1)*p0)/k
                dp = n*(z*p1-p0)/(z*z-1.0)
                dz = p1/dp; z -= dz
                if abs(dz) < 1e-15:
                    break
            xs.append(z); ws.append(2.0/((1.0-z*z)*dp*dp))
        _GL[n] = (xs, ws)
    return _GL[n]


def cell(x0, x1, r0, r1, ux=1.0, ur=0.0, **kw):
    return dict(kw, x0=x0, x1=x1, r0=r0, r1=r1, xc=0.5*(x0+x1), rc=0.5*(r0+r1), ux=ux, ur=ur, V=math.pi*(r1*r1-r0*r0)*(x1-x0),
                A=(x1-x0)*(r1-r0))


def sheets(c, comp):
    """Bound surface currents (K per unit M, along phi) of a uniformly magnetized ring cell. comp 'x': axial M gives K = +M on the outer
    cylinder and -M on the inner one; comp 'r': radial M gives K = -M on the face at x1 (n = +x) and +M on the face at x0. Volume
    currents vanish (curl M = 0 for uniform Mx and for Mr r-hat with constant magnitude)."""
    if comp == 'x':
        out = [('r', c['r1'], c['x0'], c['x1'], 1.0)]
        if c['r0'] > 0:
            out.append(('r', c['r0'], c['x0'], c['x1'], -1.0))
        return out
    return [('x', c['x1'], c['r0'], c['r1'], -1.0), ('x', c['x0'], c['r0'], c['r1'], 1.0)]


def _dist(kind, fixed, lo, hi, x, r):
    if kind == 'r':
        dx = 0.0 if lo <= x <= hi else min(abs(x-lo), abs(x-hi)); return math.hypot(dx, r-fixed)
    dr = 0.0 if lo <= r <= hi else min(abs(r-lo), abs(r-hi)); return math.hypot(x-fixed, dr)


def sheet_loops(kind, fixed, lo, hi, K, n):
    xs, ws = gauss(n); h = 0.5*(hi-lo); m = 0.5*(hi+lo)
    if kind == 'r':
        return [(m+h*z, fixed, K*h*w) for z, w in zip(xs, ws)]
    return [(fixed, m+h*z, K*h*w) for z, w in zip(xs, ws) if m+h*z > 0]


def loops(c, comp, n=None, M=1.0):
    """(x, radius, current A) loops that carry the cell's bound current for unit M (times M)."""
    out = []
    for kind, fixed, lo, hi, K in sheets(c, comp):
        out += [(x, a, I*M) for x, a, I in sheet_loops(kind, fixed, lo, hi, K, n or 4)]
    return out


def cell_field(c, comp, x, r):
    """(Bx, Br) at (x, r) of cell c with unit M along comp; each sheet is integrated with a node count that follows its length over the
    distance to the point (adaptive near field, exact loop fields)."""
    bx = br = 0.0
    for kind, fixed, lo, hi, K in sheets(c, comp):
        d = _dist(kind, fixed, lo, hi, x, r); L = hi-lo
        n = 3 if d > 6*L else min(128, max(6, math.ceil(8.0*L/max(d, 1e-9))))
        for xl, a, I in sheet_loops(kind, fixed, lo, hi, K, n):
            b_r, b_z = vs.loop_field(a, I, r, x-xl); bx += b_z; br += b_r
    return bx, br


def magnet_field(cells, M, x, r, skip=None):
    """(Bx, Br) of a magnetized set with per-cell (Mx, Mr) in A/m."""
    bx = br = 0.0
    for j, (c, (mx, mr)) in enumerate(zip(cells, M)):
        if j == skip:
            continue
        if mx:
            a, b = cell_field(c, 'x', x, r); bx += mx*a; br += mx*b
        if mr:
            a, b = cell_field(c, 'r', x, r); bx += mr*a; br += mr*b
    return bx, br


def coil_field(cs, I, x, r):
    bz, br = vf.coil_B(cs, I, x, r)
    return bz, br


# ---------- D: validation ------------------------------------------------------------------------------------------------------------------

def _check(name, value, reference, tol, note='', evidence='ANALYTIC'):
    err = abs(value-reference)/abs(reference) if reference else abs(value)
    return dict(case=name, value=value, reference=reference, rel_error=err, tolerance=tol, passes=err <= tol, note=note, evidence=evidence)


def sphere(N, R=1.0):
    """Uniformly axially magnetized sphere as N stacked slices (staircase): field at the centre (exact 2/3 mu0 M) and on the axis at 2R."""
    cs = []
    for i in range(N):
        x0 = -R+2*R*i/N; x1 = x0+2*R/N; xm = 0.5*(x0+x1)
        cs.append(cell(x0, x1, 0.0, math.sqrt(R*R-xm*xm)))
    M = [(1.0/MU0, 0.0)]*N
    return magnet_field(cs, M, 0.0, 0.0)[0], magnet_field(cs, M, 2*R, 0.0)[0]


def shell(h, rule, ri=1.0, ro=2.0):
    """Spherical shell ri..ro around the origin on an (x, r) grid of pitch h, each cell along `rule`: 'halbach' (direction 2 theta in the
    meridional plane: the Halbach sphere, uniform 4/3 mu0 M ln(ro/ri)) or 'optimal' (the 1.6 kernel: K ln(ro/ri), K = 1.380)."""
    cs, M = [], []
    n = int(round(2*ro/h)); m = int(round(ro/h))
    for i in range(n):
        for j in range(m):
            x0 = -ro+i*h; r0 = j*h; xc, rc = x0+h/2, r0+h/2
            # volume share of the ring cell inside the shell (8 x 8 subsamples, weighted by radius): smooths the staircase
            inside = tot = 0.0
            for p in range(8):
                for q in range(8):
                    xs, rs = x0+(p+0.5)*h/8, r0+(q+0.5)*h/8; tot += rs
                    if ri <= math.hypot(xs, rs) <= ro:
                        inside += rs
            fr = inside/tot
            if fr == 0.0:
                continue
            th = math.atan2(rc, xc)
            u = (math.cos(2*th), math.sin(2*th)) if rule == 'halbach' else vf.kernel(xc, rc, 0.0)[0]
            cs.append(cell(x0, x0+h, r0, r0+h, *u)); M.append((fr*u[0]/MU0, fr*u[1]/MU0))
    return magnet_field(cs, M, 0.0, 0.0)[0], len(cs)


def biot_savart_loop(a, I, rho, z, n=4000):
    """Independent loop field by direct Biot-Savart summation of n straight segments (checks the elliptic-integral loop)."""
    bx = bz = 0.0; p = (rho, 0.0, z)
    for k in range(n):
        t0 = 2*math.pi*k/n; t1 = 2*math.pi*(k+1)/n; tm = 0.5*(t0+t1)
        dl = (a*(math.cos(t1)-math.cos(t0)), a*(math.sin(t1)-math.sin(t0)), 0.0)
        q = (a*math.cos(tm), a*math.sin(tm), 0.0); d = (p[0]-q[0], p[1]-q[1], p[2]-q[2]); r3 = math.sqrt(d[0]**2+d[1]**2+d[2]**2)**3
        cr = (dl[1]*d[2]-dl[2]*d[1], dl[2]*d[0]-dl[0]*d[2], dl[0]*d[1]-dl[1]*d[0])
        bx += MU0*I/(4*math.pi)*cr[0]/r3; bz += MU0*I/(4*math.pi)*cr[2]/r3
    return bx, bz


def lorentz_force(c, comp, M, cs, I, n=12):
    """Force (Fx, total outward Fr) on a magnetized ring cell from coils by Lorentz force on its bound loops."""
    fx = fr = 0.0
    for x, a, Ib in loops(c, comp, n, M):
        bz, br = coil_field(cs, I, x, a); fx += -Ib*2*math.pi*a*br; fr += Ib*2*math.pi*a*bz
    return fx, fr


def validation(s):
    rows = []; M1 = 1.0/MU0
    # 1 sphere (staircase convergence)
    conv = []
    for N in (40, 80, 160):
        bc, bo = sphere(N); conv.append(dict(N=N, centre=bc, outside=bo))
    rows.append(_check('uniformly magnetized sphere, centre (2/3 mu0 M), 160 slices', conv[-1]['centre'], 2/3, 5e-3,
                       'staircase error falls about as 1/N: ' + ', '.join(f"N={c['N']}: {abs(c['centre']-2/3)/(2/3):.2e}" for c in conv)))
    rows.append(_check('sphere, axis at 2R (dipole 2/3 mu0 M R^3 / z^3)', conv[-1]['outside'], 2/3/8, 1e-2))
    # 2 solid cylinder and thick ring (exact axis formulas)
    cyl = cell(-1.0, 1.0, 0.0, 1.0)
    rows.append(_check('solid axially magnetized cylinder R=1, L=2, centre', magnet_field([cyl], [(M1, 0.0)], 0.0, 0.0)[0], 1/math.sqrt(2), 1e-9))
    f = lambda R, z: 0.5*((z+0.5)/math.hypot(z+0.5, R)-(z-0.5)/math.hypot(z-0.5, R))
    ring = cell(-0.5, 0.5, 0.5, 1.0)
    rows.append(_check('thick axially magnetized ring 0.5-1.0 m, axis 1.5 m off centre', magnet_field([ring], [(M1, 0.0)], 1.5, 0.0)[0],
                       f(1.0, 1.5)-f(0.5, 1.5), 1e-9))
    # 3 radially magnetized annulus (two flat current sheets)
    g = lambda a, z: math.log(a+math.hypot(a, z))-a/math.hypot(a, z)
    ann = cell(0.0, 0.2, 0.5, 1.0, 0.0, 1.0); z1, z0 = 1.0-0.2, 1.0
    ref = 0.5*(-(g(1.0, z1)-g(0.5, z1))+(g(1.0, z0)-g(0.5, z0)))
    rows.append(_check('radially magnetized annulus, axis (flat-sheet formula)', magnet_field([ann], [(0.0, M1)], 1.0, 0.0)[0], ref, 1e-9))
    # 4 circular coil against an independent Biot-Savart sum (off axis)
    br, bz = vs.loop_field(2.0, 1e6, 1.3, 0.7); bsr, bsz = biot_savart_loop(2.0, 1e6, 1.3, 0.7)
    rows.append(_check('circular coil off axis, B_z (elliptic vs Biot-Savart)', bz, bsz, 1e-5))
    rows.append(_check('circular coil off axis, B_rho (elliptic vs Biot-Savart)', br, bsr, 1e-5))
    # 5 solenoid: 200 discrete turns against the continuous-sheet formula
    L, R, NT, Ic = 10.0, 1.0, 200, 1e3
    b = sum(vs.loop_field(R, Ic, 0.0, -L/2+(k+0.5)*L/NT)[1] for k in range(NT))
    rows.append(_check('solenoid of 200 turns (L 10 m, R 1 m), centre (mu0 n I L / sqrt(L^2 + 4 R^2))', b, MU0*NT/L*Ic*L/math.sqrt(L*L+4*R*R), 1e-4))
    # 6 idealized Halbach and optimal shells (convergence in the grid)
    hb = [(h,)+shell(h, 'halbach') for h in (0.1, 0.05)]; op = [(h,)+shell(h, 'optimal') for h in (0.1, 0.05)]
    rows.append(_check('Halbach sphere 1-2 m (direction 2 theta), centre (4/3 ln 2)', hb[-1][1], K_HALBACH*math.log(2), 2e-3,
                       ', '.join(f'h={h}: {abs(v/(K_HALBACH*math.log(2))-1):.2e} ({n} cells)' for h, v, n in hb)))
    rows.append(_check('optimal-orientation shell 1-2 m, centre (K ln 2, K = 1.380; the 1.6 kernel bound)', op[-1][1], vf.shell_factor(1.0, 2.0), 2e-3,
                       ', '.join(f'h={h}: {abs(v/vf.shell_factor(1.0, 2.0)-1):.2e}' for h, v, n in op)))
    # 7 force: Lorentz on bound loops vs Kelvin gradient vs virtual work of the mutual energy, and Newton's third law on the coils
    cs = vs.coils(s); I = vs.currents(s, 'NOMINAL')
    c = cell(-16.0, -15.6, 2.6, 3.0, math.cos(0.6), math.sin(0.6)); Mv = 2.0e6
    fl = [lorentz_force(c, k, Mv*(c['ux'] if k == 'x' else c['ur']), cs, I) for k in ('x', 'r')]; Fx = fl[0][0]+fl[1][0]
    hh = 1e-3; grad = 0.0
    for x, r, dV in _sub(c, 8):
        bp = coil_field(cs, I, x+hh*c['ux'], r+hh*c['ur']); bm = coil_field(cs, I, x-hh*c['ux'], r-hh*c['ur'])
        grad += Mv*(bp[0]-bm[0])/(2*hh)*dV
    def Wm(dx):
        tot = 0.0
        for k in ('x', 'r'):
            for x, a, Ib in loops(dict(c, x0=c['x0']+dx, x1=c['x1']+dx), k, 12, Mv*(c['ux'] if k == 'x' else c['ur'])):
                tot += Ib*sum(Ic*vs.mutual(a, q['r'], x-q['x']) for q, Ic in zip(cs, I))
        return tot
    vw = (Wm(1e-3)-Wm(-1e-3))/2e-3
    rows.append(_check('force on a magnetized ring: Lorentz on bound loops vs Kelvin (M.grad)B', Fx, grad, 2e-3))
    rows.append(_check('force on a magnetized ring: Lorentz vs virtual work d(sum I_b Phi_coils)/dx', Fx, vw, 2e-3))
    react = 0.0; Mc = [(Mv*c['ux'], Mv*c['ur'])]
    for q, Ic in zip(cs, I):
        bx_, br_ = magnet_field([c], Mc, q['x'], q['r']); react += -Ic*2*math.pi*q['r']*br_
    rows.append(_check("Newton's third law: force on the coils from the ring = -force on the ring", -react, Fx, 2e-3))
    # 8 energy identity: sum over coils of I_c Phi_Fiji(c) equals the volume integral of M.B_coils
    lhs = 0.0
    for k in ('x', 'r'):
        for x, a, Ib in loops(c, k, 12, Mv*(c['ux'] if k == 'x' else c['ur'])):
            lhs += Ib*sum(Ic*vs.mutual(a, q['r'], x-q['x']) for q, Ic in zip(cs, I))
    rhs = 0.0
    for x, r, dV in _sub(c, 8):
        bz, br = coil_field(cs, I, x, r); rhs += Mv*(c['ux']*bz+c['ur']*br)*dV
    rows.append(_check('interaction energy: sum I_b Phi_coils (loops) = integral of M.B_coils dV', lhs, rhs, 2e-3))
    return dict(rows=rows, sphere_convergence=conv, all_pass=all(r['passes'] for r in rows))


def _sub(c, n):
    for i in range(n):
        for j in range(n):
            x = c['x0']+(i+0.5)*(c['x1']-c['x0'])/n; r = c['r0']+(j+0.5)*(c['r1']-c['r0'])/n
            yield x, r, 2*math.pi*r*(c['x1']-c['x0'])*(c['r1']-c['r0'])/(n*n)


def solver_choice():
    return dict(
        evaluated=[dict(tool='Magpylib', kind='analytic fields of magnets and currents (Python)', status='not installable here (pip denied)'),
                   dict(tool='FEMM', kind='2D/axisymmetric nonlinear magnetostatic FEM (Windows)', status='not available in the Linux container'),
                   dict(tool='GetDP + Gmsh / Elmer FEM / FEniCS', kind='general FEM', status='not installable here (no package access)'),
                   dict(tool='RADIA', kind='3D magnetostatics by integral method', status='not installable here')],
        chosen='an axisymmetric bound-current integral solver in the standard library (uniform-M ring cells -> surface currents -> '
               'Gauss-Legendre loops with exact elliptic-integral fields). For linear-recoil and seeded (tanh) materials in free space '
               'it is the integral form of what Magpylib or RADIA compute; it is validated below against closed forms. Nonlinear '
               'B-H curves inside soft iron, eddy currents and 3D (non-axisymmetric) segmentation are outside it.',
        evidence='REDUCED_MODEL')


# ---------- E: geometries --------------------------------------------------------------------------------------------------------------------

def _grid(x0, x1, r0, r1, h):
    nx = max(1, math.ceil((x1-x0)/h-1e-9)); nr = max(1, math.ceil((r1-r0)/h-1e-9)); dx = (x1-x0)/nx; dr = (r1-r0)/nr
    for i in range(nx):
        for j in range(nr):
            yield x0+i*dx, x0+(i+1)*dx, r0+j*dr, r0+(j+1)*dr


def _clear(s, x, r, half, removed=()):
    c = config(s); st = ve.stations(s); g = ve.config(s)['geometry']; hw = vm.hardware(s, vs.coils(s)); cl = c['clearance_m']
    for q in vs.coils(s):
        if q['name'] in removed:
            continue
        if math.hypot(x-q['x'], r-q['r']) < q['cryostat']+cl+half:
            return False
    if st['shield_aft']-cl-half <= x <= st['shield_fwd'] and r <= g['shield_aft_radius_m']+cl+half:
        return False
    rc = vm._cage_r(hw['cage'], x)
    return not (rc is not None and r+half+cl >= rc)


def _quant(u, N):
    a = math.atan2(u[1], u[0]); q = 2*math.pi/N; a = round(a/q)*q
    return math.cos(a), math.sin(a)


def geometries(s, h=None):
    """FG-0..FG-5 as ring cells (x0, x1, r0, r1) with an easy axis for the ORIENTED mode: the 1.6 kernel direction for the burn point,
    quantized to the orientation segments (FG-0 also keeps the continuous direction for the 1.6 cross-check); FG-3 axial; FG-4 along the
    local coil field. Cells that would cut a cryostat (with clearance), the shield or the cage are dropped."""
    c = config(s); f = fcfg(s); h = h or c['cell_m']; st = ve.stations(s); burn = st['burn']; N = c['orientation_segments']
    cs = vs.coils(s); I = vs.currents(s, 'NOMINAL'); out = {}
    def kern(x, r):
        return _quant(vf.kernel(x, r, burn)[0], N)
    def build(rects, rule, removed=(), filt=None):
        cells_ = []
        for (x0, x1, r0, r1) in rects:
            for a, b, p, q in _grid(x0, x1, r0, r1, h):
                xc, rc = 0.5*(a+b), 0.5*(p+q); half = 0.5*math.hypot(b-a, q-p)
                if filt and not filt(xc, rc):
                    continue
                if not _clear(s, xc, rc, 0.0 if rule == 'liner' else half*0.5, removed):
                    continue
                u = rule(xc, rc) if callable(rule) else kern(xc, rc)
                cells_.append(cell(a, b, p, q, *u))
        return cells_
    L0 = vf.liners(s, c['fg0_section_m'])
    out['FG-0'] = dict(name='existing Fiji liner (1.6, 0.2 m)', cells=[cell(l['x']-l['t']/2, l['x']+l['t']/2, l['R']-l['t']/2, l['R']+l['t']/2,
                                                                          *_quant(vf.kernel(l['x'], l['R'], burn)[0], N)) for l in L0],
                       removed=(), line_of_sight=True)
    b = c['fg1_block_m']
    L1 = [(q['x']-b/2, q['x']+b/2, q['r']-q['cryostat']-c['clearance_m']-b, q['r']-q['cryostat']-c['clearance_m']) for q in cs]
    out['FG-1'] = dict(name='oriented segmented lattice (0.5 m blocks inboard of each coil)', cells=build(L1, 'liner'), removed=(), line_of_sight=True)
    ri, ro = c['fg2_shell_m']; t0, t1 = (math.radians(a) for a in c['fg2_theta_deg'])
    def in_shell(x, r):
        d = math.hypot(x-burn, r); th = math.atan2(r, x-burn)
        return ri <= d <= ro and t0 <= th <= t1
    out['FG-2'] = dict(name=f'open segmented Halbach-type shell ({ri:g}-{ro:g} m, {c["fg2_theta_deg"][0]:g}-{c["fg2_theta_deg"][1]:g} deg)',
                       cells=build([(burn-ro, burn+ro, 0.0, ro)], 'kernel', filt=in_shell), removed=(), line_of_sight=True)
    blocks = []
    for q, side in zip([q for q in cs if q['group'] == 'closure'], c['fg3_block_m']):
        blocks.append((q['x']-side/2, q['x']+side/2, q['r']-side/2, q['r']+side/2))
    out['FG-3'] = dict(name='hybrid: Fiji blocks replace the closure coils C1, C2; loops L1-L4 rescaled',
                       cells=build(blocks, lambda x, r: (1.0, 0.0), removed=('C1', 'C2')), removed=('C1', 'C2'), line_of_sight=True)
    def along(x, r):
        bz, br = coil_field(cs, I, x, r); n = math.hypot(bz, br); return _quant((bz/n, br/n), N)
    out['FG-4'] = dict(name='distributed field-shaping rings along the nozzle', cells=build([(b['x'][0], b['x'][1], b['r'][0], b['r'][1]) for b in c['fg4_blocks']], along),
                       removed=(), line_of_sight=True)
    b5 = c['fg5_block']
    out['FG-5'] = dict(name='open architecture: Fiji only in the shield shadow (collar)', cells=build([(b5['x'][0], b5['x'][1], b5['r'][0], b5['r'][1])], 'kernel'),
                       removed=(), line_of_sight=False)
    for k, g in out.items():
        g['volume_m3'] = sum(q['V'] for q in g['cells']); g['mass_kg'] = g['volume_m3']*f['density_kg_m3']; g['n_cells'] = len(g['cells'])
        g['nearest_m'] = min(math.hypot(q['xc']-burn, q['rc']) for q in g['cells']) if g['cells'] else None
    return out


def active_coils(s, removed=()):
    cs = vs.coils(s); I = vs.currents(s, 'NOMINAL')
    keep = [(q, i) for q, i in zip(cs, I) if q['name'] not in removed]
    return [q for q, _ in keep], [i for _, i in keep]


def influence(s, g):
    """Unit-M influence of every cell (axial and radial components) on the axis targets, every cell centre and the centre +- h along x and r
    (gradients for the Kelvin force), and the flux each cell's bound loops put through each coil. Computed once per geometry; every
    material case and mode is a superposition."""
    st = ve.stations(s); cells_ = g['cells']; N = len(cells_); cs = vs.coils(s)
    axis = [st['shield_aft']+(st['exit']-st['shield_aft'])*k/48 for k in range(49)]
    tg = dict(burn=st['burn'], shield_aft=st['shield_aft'], exit=st['exit'])
    T = {k: [[cell_field(c, comp, x, 0.0)[0] for comp in ('x', 'r')] for c in cells_] for k, x in tg.items()}
    A = [[[cell_field(c, comp, x, 0.0)[0] for comp in ('x', 'r')] for c in cells_] for x in axis]
    hh = 0.02
    pts = lambda c: [(c['xc'], c['rc']), (c['xc']+hh, c['rc']), (c['xc']-hh, c['rc']), (c['xc'], c['rc']+hh), (c['xc'], c['rc']-hh)]
    P = [[[[cell_field(cj, comp, x, r) for comp in ('x', 'r')] for cj in cells_] for (x, r) in pts(ci)] for ci in cells_]
    flux = [[[sum(Ib*vs.mutual(a, q['r'], x-q['x']) for x, a, Ib in loops(cj, comp, 8)) for comp in ('x', 'r')] for cj in cells_] for q in cs]
    return dict(axis=axis, targets=T, axis_field=A, points=P, h=hh, flux=flux, N=N)


def _matvec(Pk, M):
    """Field (Bx, Br) at one point from all cells with M[j] = (Mx, Mr), using precomputed unit fields Pk[j][comp] = (bx, br)."""
    bx = br = 0.0
    for (fx, fr), (mx, mr) in zip(Pk, M):
        bx += mx*fx[0]+mr*fr[0]; br += mx*fx[1]+mr*fr[1]
    return bx, br


def solve(s, g, inf, mu0Ms, mode, I=None, removed=(), T=None, fill=1.0, iters=None):
    """Self-consistent magnetization. ORIENTED: M along the fixed easy axis, M = M_rem + chi H_par (linear recoil), capped at Ms; the
    reverse field H_par < 0 is reported as the coercivity the material would need. SEEDED: M = Ms(T) tanh(mu0 |H| / B_align) along the local
    H (the 1.6 constitutive law; one property), damped fixed point. H = B/mu0 - M inside each cell includes its own demagnetizing field."""
    c = config(s); f = fcfg(s); cells_ = g['cells']; N = len(cells_)
    cs_all = vs.coils(s); I = list(I) if I is not None else vs.currents(s, 'NOMINAL')
    Bc = [[coil_field(cs_all, I, x, r) for (x, r) in _pts(ci, inf['h'])] for ci in cells_]
    Mrem = ms_op(s, mu0Ms, T)*fill; Mmax = mu0Ms/MU0*fill; chi = c['recoil_chi']; Bal = f['B_align_T'][vf.NOM]
    M = [(Mrem*q['ux'], Mrem*q['ur']) for q in cells_] if mode == 'ORIENTED' else [(0.0, 0.0)]*N
    n_it = iters or (c['iterations'] if mode == 'ORIENTED' else 40)
    for it in range(n_it):
        new = []
        for i, ci in enumerate(cells_):
            bx, br = _matvec(inf['points'][i][0], M); bx += Bc[i][0][0]; br += Bc[i][0][1]
            Hx, Hr = bx/MU0-M[i][0], br/MU0-M[i][1]
            if mode == 'ORIENTED':
                Hp = Hx*ci['ux']+Hr*ci['ur']; m = min(max(Mrem+chi*Hp, 0.0), Mmax); new.append((m*ci['ux'], m*ci['ur']))
            else:
                Hn = math.hypot(Hx, Hr)
                if Hn == 0.0:
                    new.append((0.0, 0.0)); continue
                m = Mrem*math.tanh(MU0*Hn/Bal); new.append((m*Hx/Hn, m*Hr/Hn))
        M = new if mode == 'ORIENTED' else [(0.5*a[0]+0.5*b[0], 0.5*a[1]+0.5*b[1]) for a, b in zip(M, new)]
    return M, Bc


def _pts(c, hh):
    return [(c['xc'], c['rc']), (c['xc']+hh, c['rc']), (c['xc']-hh, c['rc']), (c['xc'], c['rc']+hh), (c['xc'], c['rc']-hh)]


def evaluate(s, g, inf, M, Bc, I, removed=()):
    """Fields, topology, energies, forces, stresses and the coil response of one solved magnetization."""
    c = config(s); f = fcfg(s); st = ve.stations(s); cells_ = g['cells']; cs_all = vs.coils(s)
    cs, Ia = [q for q in cs_all if q['name'] not in removed], [i for q, i in zip(cs_all, I) if q['name'] not in removed]
    hh = inf['h']; Bstop = vs.stop_field(s)
    tgt = {k: sum(mx*v[0]+mr*v[1] for v, (mx, mr) in zip(rows, M)) for k, rows in inf['targets'].items()}
    coil_t = dict(burn=vs.axis_field(cs, Ia, st['burn']), shield_aft=vs.axis_field(cs, Ia, st['shield_aft']), exit=vs.axis_field(cs, Ia, st['exit']))
    prof_c = [vs.axis_field(cs, Ia, x) for x in inf['axis']]
    prof_f = [sum(mx*v[0]+mr*v[1] for v, (mx, mr) in zip(rows, M)) for rows in inf['axis_field']]
    tot = [a+b for a, b in zip(prof_c, prof_f)]
    nulls = lambda p: sum(1 for a, b in zip(p, p[1:]) if a*b < 0)
    Hrev = []; Wx = Ws = 0.0; Fx = 0.0; sig = []; Fr_abs = 0.0
    for i, ci in enumerate(cells_):
        mx, mr = M[i]; m = math.hypot(mx, mr)
        bfx, bfr = _matvec(inf['points'][i][0], M)
        bx = Bc[i][0][0]+bfx; br = Bc[i][0][1]+bfr
        Hx, Hr = bx/MU0-mx, br/MU0-mr
        u = (ci['ux'], ci['ur']) if m == 0 else (mx/m, mr/m)
        Hrev.append(-(Hx*u[0]+Hr*u[1])*MU0)
        Wx += (mx*Bc[i][0][0]+mr*Bc[i][0][1])*ci['V']
        hd = (bfx/MU0-mx, bfr/MU0-mr); Ws += -0.5*MU0*(mx*hd[0]+mr*hd[1])*ci['V']
        # Kelvin force on cell i from the coils and the other cells: V (M.grad) B
        def Bext(k):
            P = inf['points'][i][k]; ox = sum(mxj*P[j][0][0]+mrj*P[j][1][0] for j, (mxj, mrj) in enumerate(M) if j != i)
            orr = sum(mxj*P[j][0][1]+mrj*P[j][1][1] for j, (mxj, mrj) in enumerate(M) if j != i)
            return Bc[i][k][0]+ox, Bc[i][k][1]+orr
        bxp, brp = Bext(1); bxm, brm = Bext(2); bxu, bru = Bext(3); bxd, brd = Bext(4)
        dBx_dx, dBr_dx = (bxp-bxm)/(2*hh), (brp-brm)/(2*hh); dBx_dr, dBr_dr = (bxu-bxd)/(2*hh), (bru-brd)/(2*hh)
        fx = ci['V']*(mx*dBx_dx+mr*dBx_dr); fr = ci['V']*(mx*dBr_dx+mr*dBr_dr)
        Fx += fx; Fr_abs += abs(fr)
        sig.append(fr/(2*math.pi*ci['A']))
    # coil response to a collapse: flux conservation L dI = Phi_Fiji (superconducting coils)
    idx = [k for k, q in enumerate(cs_all) if q['name'] not in removed]
    Phi = [sum(mx*inf['flux'][k][j][0]+mr*inf['flux'][k][j][1] for j, (mx, mr) in enumerate(M)) for k in idx]
    L = vm.inductance(cs); dI = _lin(L, Phi)
    W0 = vm.stored_energy(cs, Ia); W1 = vm.stored_energy(cs, [a+b for a, b in zip(Ia, dI)])
    Bpk0 = vm.conductor_field(cs, Ia); Bpk1 = vm.conductor_field(cs, [a+b for a, b in zip(Ia, dI)])
    Ms_max = max((math.hypot(*m) for m in M), default=0.0)
    p_self = MU0*Ms_max**2/2
    smax = max((abs(x) for x in sig), default=0.0)+p_self
    sy = mp.require(mp.get_property('MAT-TI6AL4V', 'yield_strength', 293.0), 'low'); rho_ti = mp.require(mp.get_property('MAT-TI6AL4V', 'density'))
    allow = fcfg(s)['strut_allowable_share']*sy
    support_area = abs(Fx)/allow; support_mass = support_area*c['support_length_m']*rho_ti
    virial = rho_ti*(abs(Wx)+abs(Ws))/allow
    strain = smax/c['young_Pa']
    Bb = coil_t['burn']+tgt['burn']
    return dict(
        B_burn_T=Bb, B_fiji_burn_T=tgt['burn'], B_coil_burn_T=coil_t['burn'], share_of_stop=tgt['burn']/Bstop, A_sys=Bb/Bstop,
        B_shield_aft_T=coil_t['shield_aft']+tgt['shield_aft'], B_exit_T=coil_t['exit']+tgt['exit'],
        bubble_radius_factor=(abs(Bb)/Bstop)**(-2/3) if Bb else None,
        axis_nulls=nulls(tot), axis_nulls_coils=nulls(prof_c), axis_min_over_burn=min(abs(x) for x in tot[len(tot)//4:])/abs(Bb) if Bb else None,
        mu0M_mean_T=MU0*sum(math.hypot(*m)*q['V'] for m, q in zip(M, cells_))/max(g['volume_m3'], 1e-12),
        reverse_field_T=max(Hrev, default=0.0), reversed_share=sum(1 for x in Hrev if x > 0)/max(len(Hrev), 1),
        anisotropy_J_m3=0.5*Ms_max*max(max(Hrev, default=0.0), 0.0),
        interaction_J=Wx, self_J=Ws, force_x_N=Fx, radial_force_abs_N=Fr_abs, hoop_max_Pa=max((abs(x) for x in sig), default=0.0),
        self_pressure_Pa=p_self, stress_max_Pa=smax, strain=strain, strain_collapse=strain > fcfg(s)['strain_limit'],
        support_mass_kg=support_mass, virial_mass_kg=virial,
        collapse=dict(dI_At=dI, dI_share=max((abs(d)/abs(i) for d, i in zip(dI, Ia)), default=0.0), stored_before_J=W0, stored_after_J=W1,
                      to_coils_J=W1-W0, heat_bound_J=abs(Wx)+abs(Ws)+abs(W1-W0),
                      heat_bound_K=(abs(Wx)+abs(Ws)+abs(W1-W0))/max(g['volume_m3']*fcfg(s)['density_kg_m3']*c['specific_heat_J_kgK'], 1e-12),
                      peak_field_before_T=max(Bpk0), peak_field_after_T=max(Bpk1),
                      conductor_limit_T=s['vertex_engine']['magnet']['conductor_field_limit_T']))


def _lin(A, b):
    n = len(b); M = [row[:]+[b[i]] for i, row in enumerate(A)]
    for k in range(n):
        p = max(range(k, n), key=lambda i: abs(M[i][k])); M[k], M[p] = M[p], M[k]
        for i in range(k+1, n):
            f = M[i][k]/M[k][k]
            for j in range(k, n+1):
                M[i][j] -= f*M[k][j]
    x = [0.0]*n
    for i in range(n-1, -1, -1):
        x[i] = (M[i][n]-sum(M[i][j]*x[j] for j in range(i+1, n)))/M[i][i]
    return x


def fg3_solve(s, g, inf):
    """FG-3 ORIENTED: the loop scale alpha (L1-L4) and the signed axial Fiji magnetization m that give the stop field at the burn and the
    null at the shield's aft face without C1 and C2 (two linear conditions, unit fields from the solver)."""
    st = ve.stations(s); cs = vs.coils(s); I = vs.currents(s, 'NOMINAL')
    Il = [0.0 if q['name'] in ('C1', 'C2') else i for q, i in zip(cs, I)]
    bL = [vs.axis_field(cs, Il, st['burn']), vs.axis_field(cs, Il, st['shield_aft'])]
    gF = [sum(r[0] for r in inf['targets']['burn']), sum(r[0] for r in inf['targets']['shield_aft'])]   # unit axial M in every cell
    B = vs.stop_field(s); det = bL[0]*gF[1]-bL[1]*gF[0]
    al = B*gF[1]/det; m = -B*bL[1]/det
    return dict(alpha=al, M_A_m=m, mu0M_T=MU0*m, I_At=[al*i for i in Il], orientation='+x' if m > 0 else '-x', B_stop_T=B)


def matrix(s, G, INF):
    """FG x FM x mode. FG-3 uses its solved currents; in ORIENTED mode its fill (Fiji share of the block) is the solved magnetization over
    the case's operating magnetization (more than 1: the blocks are too small for that material)."""
    c = config(s); rows = []; I0 = vs.currents(s, 'NOMINAL'); sol3 = fg3_solve(s, G['FG-3'], INF['FG-3'])
    for k, g in G.items():
        inf = INF[k]
        for fm in c['material_cases']:
            for mode in MODES:
                I = I0; removed = g['removed']; fill = 1.0; note = ''; fill_raw = 1.0
                gg = g
                if k == 'FG-3':
                    I = [0.0 if q['name'] in removed else i for q, i in zip(vs.coils(s), I0)]
                    note = 'closure coils removed, loops at the released currents: a seeded material cannot be told to make the null'
                    if mode == 'ORIENTED':
                        I = sol3['I_At']
                        need = abs(sol3['M_A_m']); have = ms_op(s, fm['mu0_Ms_T']); fill = need/have; fill_raw = fill
                        sgn = 1.0 if sol3['M_A_m'] > 0 else -1.0
                        gg = dict(g, cells=[dict(q, ux=sgn) for q in g['cells']])
                        note = f'fill {fill:.2f} of the blocks' + (' (blocks too small: more than 1)' if fill > 1 else '')
                        fill = min(fill, 1.0)
                M, Bc = solve(s, gg, inf, fm['mu0_Ms_T'], mode, I=I, removed=removed, fill=fill)
                e = evaluate(s, gg, inf, M, Bc, I, removed)
                closure = None
                if k == 'FG-3':
                    closure = mode == 'ORIENTED' and fill_raw <= 1.0 if mode == 'ORIENTED' else False
                rows.append(dict(id=f"{k}/{fm['id']}/{mode}", geometry=k, material=fm['id'], mode=mode, mu0_Ms_T=fm['mu0_Ms_T'], status=fm['status'],
                                 fill=fill, fill_required=fill_raw, closure_met=closure, note=note, **e))
    return rows, sol3


def convergence(s, levels=(0.5, 0.25, 0.125)):
    """B at the burn per unit mu0 Ms (ORIENTED, no recoil) against the cell size: the field integral converges as the cells shrink."""
    st = ve.stations(s); out = {}
    for h in levels:
        G = geometries(s, h)
        for k, g in G.items():
            if k == 'FG-0':
                continue
            b = sum(cell_field(q, 'x', st['burn'], 0.0)[0]*q['ux']+cell_field(q, 'r', st['burn'], 0.0)[0]*q['ur'] for q in g['cells'])/MU0
            out.setdefault(k, []).append(dict(cell_m=h, G=b, n_cells=len(g['cells']), volume_m3=g['volume_m3']))
    for k, rows in out.items():
        rows[-1]['change_from_previous'] = abs(rows[-1]['G']/rows[-2]['G']-1.0) if rows[-2]['G'] else None
    return out


# ---------- C: reconciliation of B_eff = B_seed A_B(T) ----------------------------------------------------------------------------------------

def reconcile(s, rows, G):
    f = fcfg(s); c = config(s); Bstop = vs.stop_field(s); A = vf.lattice_law(f, f['T_operating_K']); Amax = f['A_max']
    canon = f['canon_seed_T']*A; canon_max = f['canon_seed_T']*Amax
    best = {}
    for r in rows:
        if r['geometry'] == 'FG-3':
            continue
        b = best.get((r['material'], r['mode']))
        if b is None or r['B_fiji_burn_T'] > b['B_fiji_burn_T']:
            best[(r['material'], r['mode'])] = r
    G_req = dict(canon_seed=(canon-Bstop), vertex_seed=(A-1.0)*Bstop)
    interp = [
        dict(id='A', reading='magnetization ratio Ms(T)/Ms(cold) = A_B(T)', meaningful=True,
             verdict='Consistent with the one property: the canon shape becomes the temperature dependence of the material. It sets no field.'),
        dict(id='B', reading='magnetic-circuit response: B_total = B_seed A_B(T) at the reaction', meaningful=False,
             verdict=f'Needs mu0 Ms G >= (A_B - 1) B_seed: {G_req["vertex_seed"]:.1f} T for the Vertex coil seed '
                     f'({Bstop:.3f} T) and {G_req["canon_seed"]:.0f} T for the canon 5 T seed. The best open geometry here has G of order 0.1-0.5, '
                     'so the material would need hundreds of tesla: a field multiplier without a source.'),
        dict(id='C', reading='historical approximation of the LOCKED single-core Fiji drive', meaningful=True,
             verdict='Kept unchanged as the historical drive calibration (REC-3). It does not transfer to the four-engine Vertex geometry.')]
    curve = []
    ref = best.get(('FM-2', 'SEEDED'))
    for T in range(500, int(f['T_quench_K'])+51, 50):
        fr = vf.state(f, float(T))[0]/vf.state(f, f['T_operating_K'])[0]
        row = dict(T_K=T, canon_A_B=vf.lattice_law(f, T), canon_B_eff_T=f['canon_seed_T']*vf.lattice_law(f, T) if T < f['T_quench_K'] else 0.0)
        for (mat, mode), r in sorted(best.items()):
            row[f'{mat}/{mode}'] = (Bstop+r['B_fiji_burn_T']*fr)/Bstop
        curve.append(row)
    return dict(canon_B_T=canon, canon_max_T=canon_max, vertex_seed_T=Bstop, G_required=G_req, interpretations=interp,
                best=[dict(material=k[0], mode=k[1], geometry=v['geometry'], B_fiji_burn_T=v['B_fiji_burn_T'], A_sys=v['A_sys'],
                           mu0Ms_for_canon_T=(canon-v['B_coil_burn_T'])/max(v['B_fiji_burn_T']/v['mu0_Ms_T'], 1e-12),
                           mu0Ms_for_30x_T=(Amax-1.0)*Bstop/max(v['B_fiji_burn_T']/v['mu0_Ms_T'], 1e-12)) for k, v in sorted(best.items())],
                successor=dict(
                    law='B_total(r, T) = B_coils(r) + B_Fiji(r; M(r, T)),  M = Ms_max f(T) g(H) along the local H (SEEDED) or the easy axis '
                        '(ORIENTED, needs coercivity),  f(T) = the canon smoothstep from 1/A_max (activation) to 1 (saturation), linear to 0 '
                        'from degradation to quench, x (1 - cycle loss)^n, collapse above the strain limit; dM/dt = (M_eq - M)/tau',
                    A_sys='A_sys(T) = B_total(burn, T) / B_coils(burn) = 1 + (B_Fiji(burn; Ms_max) / B_coils(burn)) f(T)/f(T_op): saturates at '
                          '1 + B_Fiji/B_coils, never at A_max; it is computed from geometry and Ms, not assumed',
                    keeps=['cold', 'activation', 'rise', 'saturation', 'degradation', 'collapse', 'hysteresis (cooling branch)', 'finite response'],
                    curve=curve),
                status_150T=dict(target=False, hypothesis=True, calibration='historical single-core only', unverified_point=True,
                                 verdict='Keep 132-150 T as the UNVERIFIED historical calibration of the LOCKED single-core drive (REC-2 HOLD). '
                                         'It is not reachable as a Vertex target: no FM case and open geometry gives more than a few per cent of '
                                         'the stop field, let alone 132 T; promoting it would need a field source the constitutive law does not have.'))


# ---------- F: exposure, heat, feedback -------------------------------------------------------------------------------------------------------

_COMP = {'C1': 'CLOSURE_COILS', 'C2': 'CLOSURE_COILS', 'L1': 'NOZZLE_LOOPS', 'L2': 'NOZZLE_LOOPS', 'L3': 'NOZZLE_LOOPS', 'L4': 'NOZZLE_LOOPS',
         'SHIELD': 'SHADOW_SHIELD', 'CAGE': 'CAGE'}


def _cold(s, comp, bracket):
    c = s['vertex_radiation']; strict = [m for m in c['cold_materials'] if m != 'cryostat']
    mats = vf.r15()['components'][comp].get('material') or []
    return any(m in (strict if bracket == 'low' else c['cold_materials']) for m in mats)


def rays(s, g, step_deg=0.5, step=0.025, rmax=16.0):
    """Ray screen from the burn on the 1.5 axisymmetric hardware (vertex_magnet.hardware) with the geometry's cells added. Per ray: the
    first obstacle before and after, and the neutron path lengths through hardware and Fiji in order of travel."""
    st = ve.stations(s); cs = [q for q in vs.coils(s) if q['name'] not in g['removed']]; hw = vm.hardware(s, cs); x0 = st['burn']
    occ = {}
    for i, q in enumerate(g['cells']):
        for a in range(int(math.floor(q['x0']/step)), int(math.ceil(q['x1']/step))):
            for b in range(int(math.floor(q['r0']/step)), int(math.ceil(q['r1']/step))):
                occ[(a, b)] = i
    full = vm.hardware(s, vs.coils(s)); out = []
    for k in range(int(180/step_deg)):
        deg = (k+0.5)*step_deg; th = math.radians(deg); w = 0.5*(math.cos(math.radians(deg-step_deg/2))-math.cos(math.radians(deg+step_deg/2)))
        old = new = None; Lhw_before = 0.0; LF = 0.0; t = 0.0; old_t = None; entry = None
        while t < rmax:
            t += step; x = x0+t*math.cos(th); r = t*math.sin(th)
            ob_old = vm.obstacle(full, x, r)
            if old is None and ob_old:
                old = ob_old; old_t = t
            ob = vm.obstacle(hw, x, r); fj = occ.get((int(math.floor(x/step)), int(math.floor(r/step))))
            if new is None:
                if fj is not None:
                    new = 'FIJI'
                elif ob:
                    new = ob
            if fj is not None:
                if LF == 0.0:
                    entry = t
                LF += step
            elif ob and LF == 0.0:
                Lhw_before += step
            if x < hw['exit']-2.0:
                break
        out.append(dict(deg=deg, w=w, old=old or 'SPACE', new=new or 'SPACE', L_fiji=LF, L_hw_before=Lhw_before, entry=entry))
    return out


def exposure(s, g, R=None, T_K=None):
    """Heat the geometry takes and moves, per engine, and the radiator consequence in both 1.5 brackets. Photons: a ray now ending in Fiji
    deposits there (thick: full absorption); its old obstacle loses the same share of its 1.5 photon heat; a ray that escaped before is new
    heat. Neutrons: Fiji absorbs 1 - exp(-L/lambda) of each ray after the hardware in front (removal length per [vertex_fiji_a]). Fiji heat
    is lifted from its temperature to the 1800 K radiator; behind tungsten (1300 K) the photons stop in the armour instead."""
    c = config(s); f = fcfg(s); R = R or vf.r15(); comp = R['components']; P = R['sources']['cases']['LOW']['power_W']
    vrc = s['vertex_radiation']; Th = s['radiators']['temperature']['value']; T_K = T_K or f['T_operating_K']
    k20 = vf.cop(vrc, vrc['cold_K'], Th); kF = vf.cop(vrc, T_K, Th); kW = vf.cop(vrc, f['T_degrade_K'], Th)
    lamF = c['fiji_removal_length_m']; lamH = c['removal_length_m'][1]
    rs = rays(s, g); sky_old = {}; shadow = {}; new_ph = new_n = 0.0; shadow_n = {}; fiji_sky = 0.0
    for r in rs:
        sky_old[r['old']] = sky_old.get(r['old'], 0.0)+r['w']
        if r['new'] == 'FIJI':
            fiji_sky += r['w']
            if r['old'] == 'SPACE':
                new_ph += r['w']
            else:
                shadow[r['old']] = shadow.get(r['old'], 0.0)+r['w']
        if r['L_fiji'] > 0:
            a = math.exp(-r['L_hw_before']/lamH)*(1-math.exp(-r['L_fiji']/lamF))
            if r['old'] == 'SPACE':
                new_n += r['w']*a
            else:
                shadow_n[r['old']] = shadow_n.get(r['old'], 0.0)+r['w']*a
    # removed coils (FG-3): their whole sky now passes to whatever is behind (Fiji or space); handled by the ray screen above (old vs new)
    out = {}
    for b in ('low', 'high'):
        moved_cold = moved_hot = 0.0; moved_n_cold = moved_n_hot = 0.0
        for ob, wsh in shadow.items():
            cn = _COMP.get(ob)
            if not cn:
                continue
            share = wsh/sky_old[ob] if sky_old.get(ob) else 0.0
            # 1.5 per-component heat for this obstacle class, split by the obstacles' sky inside the class
            cls = sum(v for k, v in sky_old.items() if _COMP.get(k) == cn)
            q = comp[cn]['photon']['LOW'][b]*(sky_old[ob]/cls if cls else 0.0)*share
            if _cold(s, cn, b):
                moved_cold += q
            else:
                moved_hot += q
        if b == 'high':
            for ob, wsh in shadow_n.items():
                cn = _COMP.get(ob)
                if not cn:
                    continue
                cls = sum(v for k, v in sky_old.items() if _COMP.get(k) == cn)
                q = comp[cn]['neutron_upper']['LOW']*(sky_old[ob]/cls if cls else 0.0)*(wsh/sky_old[ob] if sky_old.get(ob) else 0.0)
                if _cold(s, cn, b):
                    moved_n_cold += q
                else:
                    moved_n_hot += q
        # removed coils lose all of their heat (FG-3): the hardware is gone; what is behind them is in the ray screen
        removed_cold = removed_hot = 0.0
        for nm in g['removed']:
            cn = _COMP[nm]; cls = sum(v for k, v in sky_old.items() if _COMP.get(k) == cn); left = sky_old.get(nm, 0.0)-shadow.get(nm, 0.0)
            q = comp[cn]['photon']['LOW'][b]*(left/cls if cls else 0.0)+(comp[cn]['neutron_upper']['LOW']*(left/cls if cls else 0.0) if b == 'high' else 0.0)
            if _cold(s, cn, b):
                removed_cold += q
            else:
                removed_hot += q
        ph_F = P['photon']*fiji_sky                      # thick Fiji: full absorption on every ray it intercepts first
        n_F = (P['neutron']*new_n+moved_n_cold+moved_n_hot) if b == 'high' else 0.0
        QF = ph_F+n_F
        dR_direct = QF*(1+1/kF)-(moved_cold+moved_n_cold+removed_cold)*(1+1/k20)-(moved_hot+moved_n_hot+removed_hot)
        dR_armour = ph_F*(1+1/kW)+n_F*(1+1/kF)-(moved_cold+moved_n_cold+removed_cold)*(1+1/k20)-(moved_hot+moved_n_hot+removed_hot)
        F0 = vf.closure(s, 'F0', 1.0, 1.0)['brackets'][b]
        out[b] = dict(fiji_photon_W=ph_F, fiji_neutron_W=n_F, new_photon_W=P['photon']*new_ph, moved_from_cold_W=moved_cold+moved_n_cold,
                      moved_from_hot_W=moved_hot+moved_n_hot, removed_W=removed_cold+removed_hot, delta_reject_W=dR_direct,
                      delta_reject_armour_W=dR_armour, ratio=(F0['four_W']+4*dR_direct)/F0['four_W']*F0['ratio'],
                      ratio_armour=(F0['four_W']+4*dR_armour)/F0['four_W']*F0['ratio'], ratio_F0=F0['ratio'])
    kF_ = f['thermal_conductivity_W_mK'][vf.NOM]
    hit = [r for r in rs if r['new'] == 'FIJI']
    peak = max((P['photon']/(4*math.pi*r['entry']**2) for r in hit), default=0.0)
    qF = kF_*(f['T_degrade_K']-(T_K-c['coolant_dT_K']))/f['armour_thickness_m']
    qn = max((P['neutron']/(4*math.pi*r['entry']**2)*math.exp(-r['L_hw_before']/lamH)/lamF for r in rs if r['entry']), default=0.0)
    t = min(min(q['x1']-q['x0'], q['r1']-q['r0']) for q in g['cells']) if g['cells'] else 0.0
    allow = 8*kF_*(f['T_degrade_K']-T_K)/(t*t) if t else None
    return dict(fiji_sky=fiji_sky, new_sky=new_ph, shadowed_sky=shadow, brackets=out, peak_photon_W_m2=peak, fiji_face_limit_W_m2=qF,
                armour_limit_W_m2=vf.armour(s)['q_max_W_m2'], face_shortfall=peak/qF if qF else None,
                neutron_W_m3=qn, cooling_pitch_m=t, allowable_W_m3=allow, volumetric_shortfall=qn/allow if allow else None,
                margin_K=(f['T_degrade_K']-T_K)*(1-qn/allow) if allow else None, cop_fiji=kF, cop_20K=k20, cop_W=kW,
                neutron_shadow=shadow_n)


def feedback(s, g, row, ex):
    """Thermal feedback at the operating point (FM case of `row`): the M-dependent heat (hysteresis at the pulse rate) against the cooling
    conductance set by the coolant temperature difference; the field change from 1000 K to saturation; the hysteresis branches; collapse."""
    c = config(s); f = fcfg(s); T = f['T_operating_K']; pz = vm.plasma(s); V = g['volume_m3']
    M = row['mu0M_mean_T']/MU0
    hyst = pz['pulse_Hz']*V*f['hysteresis_share'][vf.NOM]*M*f['ripple_T'][vf.NOM]
    dlnM = (vf.state(f, T+1)[0]-vf.state(f, T-1)[0])/2/vf.state(f, T)[0]
    Q = ex['brackets']['high']['fiji_photon_W']+ex['brackets']['high']['fiji_neutron_W']+hyst
    Gc = Q/c['coolant_dT_K'] if Q else None
    loop = hyst*dlnM/Gc if Gc else 0.0
    return dict(hysteresis_W=hyst, dlnM_dT_per_K=dlnM, heat_W=Q, conductance_W_K=Gc, loop_gain=loop, runaway=loop >= 1.0,
                field_gain_to_saturation=1.0/vf.state(f, T)[0]-1.0, cooling_branch_ratio=vf.state(f, T, 'cooling')[0]/vf.state(f, T)[0],
                collapse_T_K=f['T_quench_K'], degrade_T_K=f['T_degrade_K'], response_s=f['response_s'][vf.NOM],
                note='photon and neutron heat do not depend on M, so the only loop is hysteresis (and eddy) loss rising with M; below saturation '
                     'the loop gain is small, above degradation M falls with T (negative feedback for the loss, but the field collapses).')


def neutrons(s, G, EX):
    """Independent REBCO neutron audit (OPEN): source, spectrum, distances, attenuation, fluence and displacement brackets per coil, for the
    released coil set and with FG-3 (closure coils replaced), then mitigations with their mass, heat, magnetic and maintenance cost."""
    c = config(s); f = fcfg(s); R = vf.r15(); st = ve.stations(s); cs = vs.coils(s); I = vs.currents(s, 'NOMINAL')
    P = R['sources']['cases']['LOW']; lines = P['neutron_lines']; Pf = P['power_W']['fusion']
    n_dd = Pf*lines['DD_2_45MeV']/(2.45*vr.MEV); n_dt = Pf*lines['DT_14_1MeV']/(14.07*vr.MEV); nps = n_dd+n_dt
    lam = c['removal_length_m']; tb = f['burn_time_s']; lim = c['fluence_limit_n_m2']; sd = c['displacement_barn']; rows = []
    for q in cs:
        d = math.hypot(q['x']-st['burn'], q['r'])-q['cryostat']; phi = nps/(4*math.pi*d*d)
        att = [math.exp(-t/l) for t, l in zip(c['intervening_m'], lam)]
        fl = [phi*a*tb for a in att]
        rows.append(dict(coil=q['name'], distance_m=d, flux_n_m2s=phi, attenuation=att, burn_fluence_n_m2=fl,
                         dpa=[x*sg*1e-28 for x, sg in zip(fl, sd)], lifetime_s=[l/(phi*a) for l, a in zip(lim, att)],
                         need=[x/l for x, l in zip(fl, reversed(lim))]))
    worst = max(rows, key=lambda r: r['flux_n_m2s'])
    keep = [r for r in rows if r['coil'] not in G['FG-3']['removed']]; w3 = max(keep, key=lambda r: r['flux_n_m2s'])
    ls = c['shield_removal_length_m']; rho = c['shield_density_kg_m3']; Pn = P['power_W']['neutron']
    mit = []
    for r in (worst, w3):
        q = next(x for x in cs if x['name'] == r['coil']); need = r['burn_fluence_n_m2'][1]/lim[1]
        for l in ls:
            t = l*math.log(max(need, 1.0)); vol = 2*math.pi*q['r']*math.pi*((q['cryostat']+t)**2-q['cryostat']**2)
            z = q['x']-st['burn']; a = q['r']; kI = (a*a/(a*a+z*z)**1.5)/((a+t)**2/((a+t)**2+z*z)**1.5)
            sky = math.sin(math.atan2(a, z))*min(1.0, (q['cryostat']+t)/math.hypot(z, a))
            mit.append(dict(coil=r['coil'], measure='wrap shield (LiH / B4C / W class)', removal_length_m=l, thickness_m=t, mass_kg=vol*rho,
                            heat_W=Pn*sky, heat_note='deposited in the shield at its own temperature (must not be 20 K)',
                            current_factor=kI, maintenance='replaceable segments; replacement interval = shielded lifetime'))
    d_ratio = (worst['distance_m']/w3['distance_m'])**2
    mit.append(dict(coil=worst['coil'], measure='placement: FG-3 removes C1, C2 (the nearest REBCO)', flux_factor=d_ratio, worst_after=w3['coil'],
                    note='the Fiji blocks take the closure role hot; the nearest REBCO is then ' + w3['coil']))
    for k in ('FG-1', 'FG-2'):
        mit.append(dict(measure=f'shadowing by the {k} Fiji volume', neutron_W_absorbed=EX[k]['brackets']['high']['fiji_neutron_W'],
                        note='Fiji in line of sight absorbs part of the neutrons that reached the coils; it then carries their heat at 1000 K'))
    mit.append(dict(measure='radiation-resistant conductor', evidence='LITERATURE_RANGE',
                    note='Nb3Sn and its insulation are usually limited near 1e22-1e23 n/m2 (E > 0.1 MeV) and need 4.5 K; no conductor tolerates the '
                         'unshielded burn fluence here. Not re-verified in this session.'))
    mit.append(dict(measure='move sensitive material farther away', note='flux falls as distance squared; the coil current for the same burn field '
                    'rises as (r^2 + z^2)^1.5 / r^2 (current_factor in the shield rows), and with it the stored energy and the forces'))
    return dict(neutrons_per_s=nps, dd_per_s=n_dd, dt_per_s=n_dt, spectrum='2.45 MeV (D-D) and 14.1 MeV (D-T from bred tritium), LOW source of 1.5',
                rows=rows, worst=worst['coil'], worst_fg3=w3['coil'], mitigations=mit, burn_time_s=tb,
                limits=dict(fluence_n_m2=lim, evidence='LITERATURE_RANGE',
                            note='REBCO critical-current degradation reported from about 3e21 to 3e22 n/m2 (E > 0.1 MeV), depending on the tape '
                                 '(pinning centres, substrate), the spectrum and above all the irradiation temperature (irradiation at 20-30 K '
                                 'degrades faster than at room temperature). No universal threshold is claimed; values not re-verified here.'),
                separation='fluence (n/m2) -> displacement damage (dpa = fluence x sigma_d, sigma_d an ESTIMATE bracket) -> performance (Jc loss, '
                           'measured per conductor); only fluence is computed from the engine, the other two are brackets',
                status='OPEN')


# ---------- G: gates, Pareto ----------------------------------------------------------------------------------------------------------------

def gate_row(s, r, ex, fb):
    c = config(s); f = fcfg(s); Bstop = vs.stop_field(s)
    best_known = max(a['mu0_HA_T'] for a in c['anisotropy_reference'])
    mag_ok = r['share_of_stop'] >= c['useful_share'] if r['geometry'] != 'FG-3' else bool(r['closure_met'])
    coerc = r['mode'] == 'SEEDED' or r['reverse_field_T'] <= 0.0
    magnetic = ('PASS' if mag_ok and coerc else 'SPECULATIVE' if mag_ok else 'FAIL')
    surv = not r['strain_collapse'] and (ex['peak_photon_W_m2'] <= ex['fiji_face_limit_W_m2']) and (ex['volumetric_shortfall'] or 0.0) <= 1.0
    th = ex['brackets']['low']['ratio'] <= 1.0
    hot = [a for a in c['anisotropy_reference'] if a['curie_K'] > f['T_operating_K']]
    return dict(magnetic=magnetic, coercivity_required_T=max(r['reverse_field_T'], 0.0) if r['mode'] == 'ORIENTED' else 0.0,
                coercivity_beyond_known=r['mode'] == 'ORIENTED' and r['reverse_field_T'] > 0,
                best_known_HA_T=best_known, known_coercive_at_operating=[a['name'] for a in hot], radiation_survival='PASS' if surv else 'FAIL', thermal_closure='PASS' if th else 'FAIL',
                plasma='NOT_RUN' if not surv else 'SCREENED', runaway=fb['runaway'])


def pareto(rows):
    """Non-dominated set: more field at the burn, less radiator ratio, less added mass, more REBCO distance (worst coil)."""
    keys = [('B_fiji_burn_T', 1), ('ratio_low', -1), ('mass_four_kg', -1), ('volumetric_shortfall', -1)]
    def dom(a, b):
        ge = all(a[k]*s_ >= b[k]*s_ for k, s_ in keys); gt = any(a[k]*s_ > b[k]*s_ for k, s_ in keys)
        return ge and gt
    rows = [r for r in rows if r['closure_met'] is not False]          # FG-3 rows that cannot make the closure null are not candidates
    return [r['id'] for r in rows if not any(dom(o, r) for o in rows if o is not r)]


FIJI_WB = '13j9_XBmJvaeV3ac5bobf908dfrQqooQvxdzufSufcGI'
TECH_WB = '1TidF56oR_AcIy_fX_VVIkkQnl173pXOxxIiXh_-aeTs'


def rec_decisions(s, R):
    """The owner's 2026-11-15 REC decisions applied as research directions. Workbook changes are prepared cell by cell (current contents read
    2026-11-15) and NOT applied: the decisions are not authorization to edit canonical workbooks."""
    fg2 = next(r for r in R['matrix'] if r['id'] == 'FG-2/FM-2/ORIENTED'); nn = R['neutrons']
    return [
        dict(id='REC-1', decision='APPROVED FOR VERTEX RESEARCH', action='exact changes prepared, not applied', changes=[
            dict(workbook='IGNITION — Fiji / Lattice Drive Science Model', workbook_id=FIJI_WB, range='04_ROOT_TRUTHS!A53:D53', current='(empty row)',
                 new=['Vertex research architecture', 'Four independent Compact Vertex engines (one reusable engine definition, four placements), each '
                      'with its own fusion region and one magnetic nozzle: per ship fusion_core_count 4, nozzle_count 4. A research architecture '
                      'beside the LOCKED single-core drive topology, not a replacement.', 'RESEARCH',
                      'Lets the Vertex research models state their topology without editing the LOCKED rows (A25 drive topology, A48:D49 counts).']),
            dict(workbook='IGNITION — Fiji / Lattice Drive Science Model', workbook_id=FIJI_WB, range='04_ROOT_TRUTHS!A54:D54', current='(empty row)',
                 new=['Vertex field law (research)', 'Vertex engines compute B_total(r, T) = B_coils(r) + B_Fiji(r; M(T)) with A_B(T) read as the '
                      'lattice magnetization ratio; B_eff = B_seed x A_B (row 22) and B_sat 150 T (row 23) stay the single-core calibration.',
                      'RESEARCH', 'Keeps rows 22-23 unchanged (REC-2 HOLD); no field multiplier in Vertex models.']),
            dict(workbook='IGNITION — Wayfarer S&E', range='15_MODEL_INTERFACES, propulsion_representation row (anchor; range to be read before any write)',
                 current='not read in 1.6A', new=['note: "VERTEX_CLUSTER = research architecture per Fiji 04_ROOT_TRUTHS!A53 (REC-1); LOCKED single-core drive unchanged"'])]),
        dict(id='REC-2', decision='HOLD', action='not deleted, not promoted; investigated as a system-level effective field',
             finding=R['reconciliation']['status_150T']['verdict']),
        dict(id='REC-3', decision='PRESERVE UNCHANGED', action='no change',
             finding='1.6A keeps both LOCKED rules: the energy identity and the flux-conserving collapse account for all field energy; Fiji heat is '
                     'lifted to the radiator, never absorbed (validation rows 13-14; exposure).'),
        dict(id='REC-4', decision='APPROVED AS A RESEARCH PRINCIPLE', action='Technology changes prepared for review, not applied', changes=[
            dict(workbook='IGNITION — Technology', workbook_id=TECH_WB, range='41_MATERIALS_MANUFACTURING!A26:F26', current='(empty row)',
                 new=['Fiji lattice orientation and segmentation', 'Nanofabrication cuts and orients harvested lattice into segmented blocks with '
                      'quantized easy axes; the assembly geometry (volume near the reaction, orientation pattern) sets the field a given '
                      'polarization produces.', 'Y100+', 'Research principle (Vertex 1.6A)', 'Fiji workbook / Technology',
                      'Orientation holds only where the material keeps it: a fixed easy axis against the local field needs coercivity at '
                      f"1000 K that no known magnet has (1.6A reverse fields {min(r['reverse_field_T'] for r in R['matrix'] if r['mode'] == 'ORIENTED'):.1f}-"
                      f"{max(r['reverse_field_T'] for r in R['matrix'] if r['mode'] == 'ORIENTED'):.1f} T). Seeded (field-following) lattice follows the local field."]),
            dict(workbook='IGNITION — Technology', workbook_id=TECH_WB, range='41_MATERIALS_MANUFACTURING!F10',
                 current='Cannot simply synthesize the full Seed-grown structure industrially.',
                 new=['Cannot simply synthesize the full Seed-grown structure industrially. Orientation and segmentation: see row 26 (research principle).'])]),
        dict(id='REC-5', decision='RECORD AS OPEN ENGINEERING FINDING', action='recorded; canonical lifetimes not edited',
             finding=f"REBCO fast-neutron fluence limit reached in {min(min(r['lifetime_s']) for r in nn['rows']):.0f} s (nearest coil, worst "
                     f"bracket) to {max(max(r['lifetime_s']) for r in nn['rows']):.0f} s (farthest coil, best bracket) against a {nn['burn_time_s']/86400:.1f}-day burn; "
                     'mitigation needs about 1e5 attenuation (1.2-2.4 m of shield per coil). OPEN.'),
    ]


def input_hash(s):
    blob = json.dumps([s['vertex_fiji_a'], s['vertex_fiji'], s['vertex_radiation'], s['vertex_engine'], s['radiators']['temperature']],
                      sort_keys=True, default=str)
    here = Path(__file__).resolve().parent
    src = b''.join((here/f).read_bytes() for f in ('vertex_fiji_a.py', 'vertex_fiji.py', 'vertex_magnet.py', 'vertex_structure.py', 'material_physics.py'))
    return hashlib.sha256(blob.encode()+src+(ROOT/'data'/'materials'/'catalogue.toml').read_bytes()+vf.EVIDENCE_PATH.read_bytes()
                          +vr.EVIDENCE_PATH.read_bytes()).hexdigest()[:16]


def report(s):
    t0 = time.time(); c = config(s); f = fcfg(s)
    G = geometries(s); INF = {k: influence(s, g) for k, g in G.items()}
    rows, sol3 = matrix(s, G, INF)
    EX = {k: exposure(s, g) for k, g in G.items()}
    dep = c['departure_kg']; out_rows = []
    for r in rows:
        g = G[r['geometry']]; ex = EX[r['geometry']]
        fb = feedback(s, g, r, ex)
        mfiji = g['mass_kg']*r['fill']
        r.update(mass_engine_kg=mfiji+r['support_mass_kg']+r['virial_mass_kg'], mass_four_kg=4*(mfiji+r['support_mass_kg']+r['virial_mass_kg']),
                 departure_share=4*(mfiji+r['support_mass_kg']+r['virial_mass_kg'])/dep, ratio_low=ex['brackets']['low']['ratio'],
                 ratio_high=ex['brackets']['high']['ratio'], ratio_low_armour=ex['brackets']['low']['ratio_armour'], feedback=fb,
                 volumetric_shortfall=ex['volumetric_shortfall'] or 0.0, face_shortfall=ex['face_shortfall'] or 0.0)
        r['gates'] = gate_row(s, r, ex, fb); r['gates']['mission'] = 'PASS' if r['departure_share'] <= c['mission_share'] and r['gates']['thermal_closure'] == 'PASS' else 'FAIL'
        r['evidence'] = ('REDUCED_MODEL; material ' + r['status'] + ('; coercivity beyond known materials' if r['gates']['coercivity_beyond_known'] else ''))
        out_rows.append(r)
    geo = {k: dict(name=g['name'], n_cells=g['n_cells'], volume_m3=g['volume_m3'], mass_kg=g['mass_kg'], nearest_m=g['nearest_m'],
                   removed=list(g['removed']), line_of_sight=g['line_of_sight'],
                   cells=[dict(x0=q['x0'], x1=q['x1'], r0=q['r0'], r1=q['r1'], ux=q['ux'], ur=q['ur']) for q in g['cells']]) for k, g in G.items()}
    nn = neutrons(s, G, EX)
    rec = reconcile(s, out_rows, G)
    best = max((r for r in out_rows if r['mode'] == 'SEEDED'), key=lambda r: r['share_of_stop'])
    besto = max((r for r in out_rows if r['mode'] == 'ORIENTED' and r['geometry'] != 'FG-3'), key=lambda r: r['share_of_stop'])
    out = dict(version=c['version'], input_hash=input_hash(s), evidence=c['evidence'], audit=audit(s), materials=material_cases(s),
               solver=solver_choice(), validation=validation(s), convergence=convergence(s), geometries=geo, fg3=sol3, matrix=out_rows,
               exposure=EX, neutrons=nn, reconciliation=rec, pareto=pareto(out_rows),
               best=dict(seeded=best['id'], seeded_share=best['share_of_stop'], oriented=besto['id'], oriented_share=besto['share_of_stop']))
    out['gates'] = summary_gates(s, out)
    out['answers'] = answers(s, out)
    out['rec'] = rec_decisions(s, out)
    out['outcome'] = c['outcome']; out['cost'] = dict(seconds=time.time()-t0)
    return out


def summary_gates(s, R):
    c = config(s); rows = R['matrix']
    any_mag = [r['id'] for r in rows if r['gates']['magnetic'] == 'PASS']
    any_spec = [r['id'] for r in rows if r['gates']['magnetic'] == 'SPECULATIVE']
    surv = [r['id'] for r in rows if r['gates']['radiation_survival'] == 'PASS']
    th = [r['id'] for r in rows if r['gates']['thermal_closure'] == 'PASS']
    mi = [r['id'] for r in rows if r['gates']['mission'] == 'PASS']
    return [
        dict(id='G-MAG', name='magnetic (useful field >= {:.0%} of the stop field, realizable orientation)'.format(c['useful_share']),
             status='PASS' if any_mag else 'SPECULATIVE' if any_spec else 'FAIL', passing=any_mag, speculative=any_spec),
        dict(id='G-PLASMA', name='plasma (run only after survival)', status='NOT_RUN', passing=[],
             note='no case survives the radiation environment with a useful field, so no plasma simulation was run (brief section 11)'),
        dict(id='G-SURV', name='radiation survival (Fiji face flux, temperature margin, strain)', status='PASS' if surv else 'FAIL', passing=surv),
        dict(id='G-THERM', name='thermal closure (four engines within the radiator)', status='PASS' if th else 'FAIL', passing=th),
        dict(id='G-MISSION', name=f"mission (four engines' added mass <= {c['mission_share']:.0%} of departure, and thermal closure)",
             status='PASS' if mi else 'FAIL', passing=mi),
        dict(id='G-VALID', name='solver validation', status='PASS' if R['validation']['all_pass'] else 'FAIL', passing=[]),
        dict(id='G-NEUTRON', name='REBCO neutron damage', status='OPEN', passing=[])]


def answers(s, R):
    rows = R['matrix']; by = {r['id']: r for r in rows}; c = config(s)
    fg0 = by['FG-0/FM-2/ORIENTED']; best = by[R['best']['oriented']]; bs = by[R['best']['seeded']]
    need = [r for r in rows if r['mode'] == 'ORIENTED' and r['geometry'] not in ('FG-3',)]
    Bstop = vs.stop_field(s); per = {}
    for g in R['geometries']:
        r = by.get(f'{g}/FM-2/ORIENTED')
        if g == 'FG-3' or not r or r['B_fiji_burn_T'] <= 0:
            continue
        slope = r['B_fiji_burn_T']/r['mu0_Ms_T']           # T at the burn per T of mu0 Ms (linear to the recoil and strain limits)
        per[g] = dict(T_per_T=slope, mu0Ms_useful_T=c['useful_share']*Bstop/slope, mu0Ms_equal_T=Bstop/slope, mu0Ms_30x_T=29*Bstop/slope,
                      mu0Ms_canon_T=(fcfg(s)['canon_seed_T']*vf.lattice_law(fcfg(s), fcfg(s)['T_operating_K'])-Bstop)/slope)
    return dict(FG0_oriented_FM2_share=fg0['share_of_stop'], best_oriented=best['id'], best_oriented_share=best['share_of_stop'],
                best_seeded=bs['id'], best_seeded_share=bs['share_of_stop'], seeded_any_positive=any(r['B_fiji_burn_T'] > 0 for r in rows
                                                                                                      if r['mode'] == 'SEEDED' and r['geometry'] != 'FG-3'),
                fg3_mu0M_T=R['fg3']['mu0M_T'], fg3_alpha=R['fg3']['alpha'], required=per,
                fg2_over_fg0=by['FG-2/FM-2/ORIENTED']['B_fiji_burn_T']/fg0['B_fiji_burn_T'])


def evidence(s, path=EVIDENCE_PATH):
    R = report(s)
    path.write_text(json.dumps(R, indent=1, default=float)+'\n')
    return R


if __name__ == '__main__':
    import spec
    S = spec.load(ROOT)[0]
    R = evidence(S) if '--evidence' in sys.argv else report(S)
    for v in R['validation']['rows']:
        print(f"{'ok ' if v['passes'] else 'BAD'} {v['rel_error']:.2e}  {v['case']}")
    for g in R['gates']:
        print(f"{g['id']:10} {g['status']:12} {g['name']}")
    for r in R['matrix']:
        print(f"{r['id']:24} B_F {r['B_fiji_burn_T']:+.4f} T ({r['share_of_stop']:+.2%})  rev {r['reverse_field_T']:6.2f} T  "
              f"ratio {r['ratio_low']:8.1f}  mass4 {r['mass_four_kg']/1e3:8.0f} t  {r['gates']}")
    print(f"{R['cost']['seconds']:.1f} s")
