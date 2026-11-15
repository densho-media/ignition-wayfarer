"""Vertex Engine 1.3: magnetic design closure. Pure, standard library only.

What the field of C1, C2 and L1-L4 has to do (MF-01..07), how well each current set and coil geometry does it, and what it costs in
current, conductor field, stored energy and force. vertex_structure carries the forces into the members; this module decides which
currents those forces come from.

Levels of evidence (never merged into one PASS):
  VACUUM_FIELD_SOLVED            exact circular-loop fields (elliptic integrals), finite windings near conductors; validated in tests
  PARTICLE_TRAJECTORY_SCREENED   test particles (Boris push) in the prescribed vacuum field: no self-consistent plasma response
  REDUCED_PLASMA_MODEL           energy-balance stopping of the expanding pulse (magnetic bubble) and a flux-conserving coil response
  PLASMA_COUPLING_OPEN, DETACHMENT_OPEN, PROPULSION_FEASIBILITY_BLOCKED  what none of the above can establish

Contents
  coil_set / field / field_cluster / finite-winding field / conductor peak field
  forces (Lorentz and energy-gradient), hoop and case stress, inductance, stored energy, dipole moment
  plasma(s)          the pulse: energy, mass, speed, species, Larmor radii, beta and Alfven Mach number
  capture            per-direction magnetic stopping distance against the distance to hardware (MF-01/02)
  field_line, nulls  topology (MF-03/06)
  particles          test-particle screen: interception, aft escape, axial momentum, divergence (MF-02..05)
  flux_compression   superconducting coils' current response to the diamagnetic pulse (replaces the 1.2 EXTREME factor as a model)
  candidates         M0 (1.2 NOMINAL / CONSERVATIVE / EXTREME), M1 currents, M2 geometry, M3 load-balanced, M4 speculative yield
  structure(s, cand) the candidate's currents and coils through vertex_structure (same rules as 1.2)

python3 src/wayfarer/vertex_magnet.py [--optimise]  prints the comparison (and re-runs the optimiser that set the stored candidates).
"""
import copy
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vertex_engine as ve
import vertex_cluster as vc
import vertex_structure as vs

MU0 = vs.MU0
E_CHARGE = 1.602176634e-19
AMU = 1.66053906660e-27
EVIDENCE = ('VACUUM_FIELD_SOLVED', 'PARTICLE_TRAJECTORY_SCREENED', 'REDUCED_PLASMA_MODEL', 'PLASMA_COUPLING_OPEN', 'DETACHMENT_OPEN',
            'PROPULSION_FEASIBILITY_BLOCKED')
HISTORICAL = ('NOMINAL', 'CONSERVATIVE', 'EXTREME')


def config(s):
    return s['vertex_engine']['magnet']


# ---------- coils and fields ---------------------------------------------------------------------------------------------------

def coil_set(s, geometry=None):
    """The six coils (vertex_structure.coils) with optional per-coil overrides {name: {x, r, a}} (candidate geometry, not the ship)."""
    cs = [dict(c) for c in vs.coils(s)]
    for c in cs:
        c.update((geometry or {}).get(c['name'], {}))
    return cs


def field(cs, I, x, rho):
    """(B_rho, B_x) of the coil set at engine station x and radius rho (thin filaments)."""
    br = bx = 0.0
    for c, i in zip(cs, I):
        if i:
            a, b = vs.loop_field(c['r'], i, rho, x-c['x']); br += a; bx += b
    return br, bx


def field3(cs, I, p):
    """Cartesian field (engine frame: x axial) at p = (x, y, z)."""
    rho = math.hypot(p[1], p[2]); br, bx = field(cs, I, p[0], rho)
    if rho < 1e-12:
        return (bx, 0.0, 0.0)
    return (bx, br*p[1]/rho, br*p[2]/rho)


def filaments(c, n=4):
    """A round winding of minor radius a as n rings x 4n filaments of equal area (current shares), (x, r, share)."""
    out = []
    for k in range(n):
        rr = c['a']*math.sqrt((k+0.5)/n)
        for j in range(4*n):
            ph = 2*math.pi*(j+0.5)/(4*n)
            out.append((c['x']+rr*math.cos(ph), c['r']+rr*math.sin(ph), 1.0/(4*n*n)))
    return out


def field_finite(c, I, x, rho, n=4):
    """Field of one coil with its finite round cross-section (filament bundle): valid at and inside the winding surface."""
    br = bx = 0.0
    for fx, fr, w in filaments(c, n):
        a, b = vs.loop_field(fr, I*w, rho, x-fx); br += a; bx += b
    return br, bx


def conductor_field(cs, I, n=4, m=16):
    """Peak |B| on each winding's surface (own coil as a filament bundle, the others as thin loops): the field the conductor sees."""
    out = []
    for j, c in enumerate(cs):
        peak = 0.0
        for k in range(m):
            ph = 2*math.pi*k/m; x = c['x']+c['a']*math.cos(ph); r = c['r']+c['a']*math.sin(ph)
            a, b = field_finite(c, I[j], x, r, n)
            o = field([q for i, q in enumerate(cs) if i != j], [v for i, v in enumerate(I) if i != j], x, r)
            peak = max(peak, math.hypot(a+o[0], b+o[1]))
        out.append(peak)
    return out


def engine_sources(s, cs, I, off=()):
    """(origin, axis, radius, signed current) of every coil of every energised engine in the ship frame (polarity applied)."""
    out = []
    for pl in vc.placements(s):
        if pl['n'] in off:
            continue
        for c, i in zip(cs, I):
            out.append((vc.to_ship(pl, (c['x'], 0, 0)), pl['axes'][0], c['r'], i*pl['polarity']))
    return out


def field_cluster(srcs, p):
    return vs._B(p, srcs)


# ---------- forces, energy, inductance -------------------------------------------------------------------------------------------

def inductance(cs):
    """Self and mutual inductance matrix per turn pair (ampere-turn form)."""
    return [[vs.self_inductance(ci['r'], ci['a']) if i == j else vs.mutual(ci['r'], cj['r'], ci['x']-cj['x']) for j, cj in enumerate(cs)]
            for i, ci in enumerate(cs)]


def stored_energy(cs, I):
    L = inductance(cs)
    return 0.5*sum(I[i]*L[i][j]*I[j] for i in range(len(cs)) for j in range(len(cs)))


def axial_forces(cs, I):
    """Axial Lorentz force on each coil from the others, F = -I 2 pi r B_rho (N, +x forward)."""
    out = []
    for j, cj in enumerate(cs):
        f = 0.0
        for i, ci in enumerate(cs):
            if i != j and I[i] and I[j]:
                f += -I[j]*2*math.pi*cj['r']*vs.loop_field(ci['r'], I[i], cj['r'], cj['x']-ci['x'])[0]
        out.append(f)
    return out


def energy_forces(cs, I, h=1e-4):
    """The same forces from the energy gradient at constant current, F_j = I_j sum_i I_i dM_ij/dx_j (independent check)."""
    out = []
    for j, cj in enumerate(cs):
        f = 0.0
        for i, ci in enumerate(cs):
            if i != j:
                dM = (vs.mutual(ci['r'], cj['r'], cj['x']+h-ci['x'])-vs.mutual(ci['r'], cj['r'], cj['x']-h-ci['x']))/(2*h)
                f += I[i]*I[j]*dM
        out.append(f)
    return out


def hoop(cs, I, s):
    """Hoop tension (self + other coils' axial field at the winding) and the winding-case stress at the 1.2 case fraction and allowable."""
    sc = vs.config(s); allow = vs.coil_case_allowable(s)['allowable']; out = []
    for j, c in enumerate(cs):
        bz = field([q for i, q in enumerate(cs) if i != j], [v for i, v in enumerate(I) if i != j], c['x'], c['r'])[1]
        T = MU0*I[j]**2/(4*math.pi)*(math.log(8*c['r']/c['a'])-0.75)+I[j]*bz*c['r']
        st = T/(math.pi*c['a']**2*sc['coil_case_fraction'])
        out.append(dict(name=c['name'], hoop_N=T, stress_Pa=st, u=st/allow))
    return out


def dipole_moment(cs, I):
    return sum(i*math.pi*c['r']**2 for c, i in zip(cs, I))


# ---------- the pulse (MF-01 inputs) ----------------------------------------------------------------------------------------------

def plasma(s, ys=1.0):
    """Energy, mass and speed of one pulse's charged products and debris, by bounded scenarios; Larmor radii of each species at a field."""
    c = config(s); r = s['vertex_research']; calc = {q['id']: q for q in ve.calculations(s)}
    Y = calc['C-02']['compact']*ve.TNT_J*ys; f = calc['C-04']['compact']/ys      # ys: M4 yield share per pulse (rate rises to keep power)
    share = r['jet_TW']/r['fusion_TW']                       # research jet (charged, directed) share of fusion power
    v = r['exhaust_velocity_km_s']*1e3
    E = {'design': Y*share, 'upper': Y*c['upper_energy_share']}
    m = 2*E['design']/v**2                                   # mass per pulse that carries the jet power at the research exhaust speed
    return dict(yield_J=Y, pulse_Hz=f, charged_share=share, energy_J=E, exhaust_m_s=v, mass_kg=m, species=c['species'], period_s=1/f)


def larmor(sp, B, v=None):
    """Larmor radius (m) of a species dict(mass_amu, charge, energy_MeV or speed) at |B|."""
    m = sp['mass_amu']*AMU; q = sp['charge']*E_CHARGE
    if v is None:
        v = speed(sp)
    return m*v/(q*abs(B)) if B else math.inf


def speed(sp, v_bulk=None):
    if sp.get('energy_MeV'):
        E = sp['energy_MeV']*1e6*E_CHARGE; m = sp['mass_amu']*AMU
        g = 1+E/(m*299792458.0**2); return 299792458.0*math.sqrt(1-1/g**2)
    return v_bulk


# ---------- capture: magnetic stopping against hardware (MF-01, MF-02; REDUCED_PLASMA_MODEL) -------------------------------------

def hardware(s, cs):
    """Plasma-facing obstacles in the (x, rho) half-plane: coil cryostats (tori), the shield aft face (disc) and the cage (longeron line)."""
    st = ve.stations(s); g = ve.config(s)['geometry']
    lon = next(p for p in ve.parts(s) if p['name'] == 'VTX_Cage_Longeron_1')
    cage = [(q[0], math.hypot(q[1], q[2])-lon['radius']) for q in lon['points']]
    return dict(tori=[(c['name'], c['x'], c['r'], c['cryostat']) for c in cs], shield=(st['shield_aft'], g['shield_aft_radius_m']), cage=cage,
                exit=st['exit'])


def _cage_r(cage, x):
    for (x0, r0), (x1, r1) in zip(cage, cage[1:]):
        if min(x0, x1) <= x <= max(x0, x1):
            return r0+(r1-r0)*(x-x0)/(x1-x0)
    return None


def obstacle(hw, x, rho):
    """Name of the obstacle containing (x, rho), else None."""
    for n, cx, cr, ca in hw['tori']:
        if (x-cx)**2+(rho-cr)**2 <= ca*ca:
            return n
    sx, sr = hw['shield']
    if x >= sx and rho <= sr:
        return 'SHIELD'
    rc = _cage_r(hw['cage'], x)
    if rc is not None and rho >= rc:
        return 'CAGE'
    return None


def ray_hardware(s, hw, th, step=0.02, rmax=30.0):
    """First obstacle along a ray from the burn point at angle th from +x (forward); (distance, name) or (None, None) when it leaves aft."""
    x0 = ve.stations(s)['burn']; t = 0.0
    while t < rmax:
        t += step; x = x0+t*math.cos(th); rho = t*math.sin(th)
        if x < hw['exit']:
            return None, None
        n = obstacle(hw, x, rho)
        if n:
            return t, n
    return None, None


def stopping(cs, I, x0, th, E, dr=0.05, rmax=40.0):
    """Distance at which the field energy swept by the pulse's cone in direction th equals the cone's share of E (isotropic):
    integral_0^R B^2 r^2 dr = mu0 E / (2 pi). None when the field cannot stop it within rmax."""
    need = MU0*E/(2*math.pi); acc = 0.0; r = 0.0; prev = 0.0
    while r < rmax:
        r += dr; br, bx = field(cs, I, x0+r*math.cos(th), r*math.sin(th))
        cur = (br*br+bx*bx)*r*r; acc += 0.5*(prev+cur)*dr; prev = cur
        if acc >= need:
            return r
    return None


_HW = {}


def hardware_rays(s, cs, rays):
    """(deg, distance, obstacle) per ray, cached per coil geometry (the hardware does not depend on the currents)."""
    key = (tuple((c['x'], c['r'], c['cryostat']) for c in cs), tuple(rays))
    if key not in _HW:
        hw = hardware(s, cs); _HW[key] = [(deg,)+ray_hardware(s, hw, math.radians(deg)) for deg in rays]
    return _HW[key]


def capture(s, cs, I, E, rays=None, protect=None):
    """Per direction: stopping distance, distance to the first obstacle, margin = obstacle / stopping (>= the required margin passes;
    a pulse not stopped within twice the obstacle distance has margin 0). protect: obstacle names that must not be reached ('COILS' for
    every cryostat; default config protect_strict)."""
    c = config(s); x0 = ve.stations(s)['burn']; names = {q['name'] for q in cs}
    protect = set(protect or c['protect_strict']); rows = []
    for deg, d, n in hardware_rays(s, cs, list(rays or range(0, 181, c['ray_step_deg']))):
        if d is None:
            rows.append(dict(deg=deg, obstacle=None, d=None, stop=None, margin=None, protected=False)); continue
        R = stopping(cs, I, x0, math.radians(deg), E, rmax=2*d)
        rows.append(dict(deg=deg, obstacle=n, d=d, stop=R, margin=(d/R if R else 0.0),
                         protected=(n in protect or (n in names and 'COILS' in protect))))
    worst = min((r['margin'] for r in rows if r['protected']), default=None)
    return dict(rows=rows, worst=worst)


# ---------- topology: field lines and nulls (MF-03, MF-06) -----------------------------------------------------------------------

def field_line(cs, I, x, rho, ds=0.05, n=1200, sign=1.0, box=(-60.0, 5.0, 25.0)):
    """Field line through (x, rho) by RK4 along B/|B| (sign -1 traces against B); stops at the box or a null."""
    pts = [(x, rho)]
    def d(px, pr):
        br, bx = field(cs, I, px, max(pr, 0.0)); b = math.hypot(br, bx)
        return (sign*bx/b, sign*br/b) if b > 1e-9 else (0.0, 0.0)
    for _ in range(n):
        k1 = d(x, rho); k2 = d(x+ds/2*k1[0], rho+ds/2*k1[1]); k3 = d(x+ds/2*k2[0], rho+ds/2*k2[1]); k4 = d(x+ds*k3[0], rho+ds*k3[1])
        dx = ds/6*(k1[0]+2*k2[0]+2*k3[0]+k4[0]); dr = ds/6*(k1[1]+2*k2[1]+2*k3[1]+k4[1])
        if dx == dr == 0.0:
            break
        x += dx; rho = abs(rho+dr); pts.append((x, rho))
        if not (box[0] < x < box[1] and rho < box[2]):
            break
    return pts


def axis_profile(cs, I, x0, x1, n=200):
    return [(x0+(x1-x0)*k/n, field(cs, I, x0+(x1-x0)*k/n, 0.0)[1]) for k in range(n+1)]


def nulls(cs, I, x0, x1, n=400):
    """Axial-field sign changes on the axis between x0 and x1 (field nulls; with B_rho = 0 on axis they are true nulls)."""
    prof = axis_profile(cs, I, x0, x1, n); out = []
    for (xa, ba), (xb, bb) in zip(prof, prof[1:]):
        if ba == 0.0 or ba*bb < 0:
            out.append(xa+(xb-xa)*ba/(ba-bb) if ba != bb else xa)
    return out


def mirror_ratio(cs, I, s):
    """Axial-field ratio between the field maximum forward of the burn point and the burn-point field (> 1: a reflecting mirror forward)."""
    st = ve.stations(s); b0 = abs(field(cs, I, st['burn'], 0.0)[1])
    fwd = max(abs(b) for _, b in axis_profile(cs, I, st['burn'], st['shield_aft'], 60))
    return fwd/b0 if b0 else math.inf


# ---------- test particles (PARTICLE_TRAJECTORY_SCREENED) ------------------------------------------------------------------------

def _dirs(n):
    """n deterministic, near-uniform unit directions (Fibonacci sphere)."""
    g = math.pi*(3-math.sqrt(5)); out = []
    for k in range(n):
        z = 1-2*(k+0.5)/n; r = math.sqrt(1-z*z); out.append((z, r*math.cos(g*k), r*math.sin(g*k)))
    return out


def push(s, cs, I, sp, v, d, hw, dt_gyro=40, tmax=None):
    """Boris push of one particle (species sp at speed v, direction d) from the burn point until it hits an obstacle, leaves aft past
    the exit by its exit margin, or leaves radially. Returns the outcome, final velocity and energy error."""
    st = ve.stations(s); c = config(s)
    m = sp['mass_amu']*AMU; q = sp['charge']*E_CHARGE
    x = [st['burn'], 0.0, 0.0]; u = [v*d[0], v*d[1], v*d[2]]
    Bref = max(abs(field(cs, I, st['burn'], 0.0)[1]), 0.05)
    dt = min(2*math.pi*m/(q*Bref)/dt_gyro, 0.02/v)
    tmax = tmax or 6*abs(st['exit']-st['burn']-c['exit_margin_m'])/v+4*c['radial_limit_m']/v
    t = 0.0; v0 = math.sqrt(sum(a*a for a in u))
    while t < tmax:
        B = field3(cs, I, x)
        b = math.sqrt(sum(a*a for a in B)); h = q*dt/(2*m)
        tv = [h*a for a in B]; t2 = sum(a*a for a in tv); sv = [2*a/(1+t2) for a in tv]
        up = [u[0]+(u[1]*tv[2]-u[2]*tv[1]), u[1]+(u[2]*tv[0]-u[0]*tv[2]), u[2]+(u[0]*tv[1]-u[1]*tv[0])]
        u = [u[0]+(up[1]*sv[2]-up[2]*sv[1]), u[1]+(up[2]*sv[0]-up[0]*sv[2]), u[2]+(up[0]*sv[1]-up[1]*sv[0])]
        step = dt if b == 0 else min(dt, 2*math.pi*m/(q*b)/dt_gyro)
        x = [x[k]+u[k]*step for k in range(3)]; t += step
        rho = math.hypot(x[1], x[2]); n = obstacle(hw, x[0], rho)
        if n:
            return dict(outcome='HIT', obstacle=n, u=u, x=x, err=abs(math.sqrt(sum(a*a for a in u))/v0-1))
        if x[0] < st['exit']-c['exit_margin_m']:
            return dict(outcome='AFT', u=u, x=x, err=abs(math.sqrt(sum(a*a for a in u))/v0-1))
        if rho > c['radial_limit_m'] or x[0] > st['front']:
            return dict(outcome='OUT', u=u, x=x, err=abs(math.sqrt(sum(a*a for a in u))/v0-1))
    return dict(outcome='TRAPPED', u=u, x=x, err=abs(math.sqrt(sum(a*a for a in u))/v0-1))


def particles(s, cs, I, n=None, species=None):
    """Test-particle screen per species: shares hitting hardware (by obstacle), leaving aft, leaving otherwise, trapped; the aft
    particles' axial momentum fraction (sum v_x / sum |v|) and 90th-percentile divergence half-angle. Prescribed vacuum field only."""
    c = config(s); pz = plasma(s); hw = hardware(s, cs); n = n or c['particles_per_species']; out = {}
    for sp in (species or c['species']):
        v = speed(sp, pz['exhaust_m_s']*sp.get('bulk_speed_factor', 1.0))
        res = [push(s, cs, I, sp, v, d, hw) for d in _dirs(n)]
        aft = [r for r in res if r['outcome'] == 'AFT']
        hits = {}
        for r in res:
            if r['outcome'] == 'HIT':
                hits[r['obstacle']] = hits.get(r['obstacle'], 0)+1
        ang = sorted(math.degrees(math.acos(max(-1.0, min(1.0, -r['u'][0]/math.sqrt(sum(a*a for a in r['u'])))))) for r in aft)
        out[sp['id']] = dict(n=n, speed_m_s=v, aft=len(aft)/n, hit=sum(hits.values())/n, hits={k: v_/n for k, v_ in sorted(hits.items())},
                             out=sum(r['outcome'] == 'OUT' for r in res)/n, trapped=sum(r['outcome'] == 'TRAPPED' for r in res)/n,
                             axial_fraction=(sum(-r['u'][0] for r in aft)/sum(math.sqrt(sum(a*a for a in r['u'])) for r in aft)) if aft else 0.0,
                             divergence_p90_deg=ang[int(0.9*(len(ang)-1))] if ang else None, max_energy_error=max(r['err'] for r in res))
    return out


# ---------- detachment screen (MF-05) ----------------------------------------------------------------------------------------------

def detachment(s, cs, I, ys=1.0):
    """Along the axis aft of the exit: ion magnetisation r_L / L_B (L_B = B / |dB/dx|) for each species, the station where it passes 1
    (ion demagnetisation), electron magnetisation at the exit, and the pulse's Alfven Mach number and beta at the exit plane."""
    st = ve.stations(s); pz = plasma(s, ys); c = config(s); out = {}
    prof = axis_profile(cs, I, st['exit'], st['exit']-c['detach_scan_m'], 200)
    for sp in c['species']:
        v = speed(sp, pz['exhaust_m_s']*sp.get('bulk_speed_factor', 1.0)); where = None
        for (xa, ba), (xb, bb) in zip(prof, prof[1:]):
            dB = abs(bb-ba)/abs(xb-xa); LB = abs(ba)/dB if dB > 0 else math.inf
            if larmor(sp, ba, v)/LB >= 1.0:
                where = st['exit']-xa; break
        out[sp['id']] = dict(demagnetised_beyond_exit_m=where, rl_exit_m=larmor(sp, prof[0][1], v))
    B = abs(prof[0][1]); Rexit = next(cc['r'] for cc in cs if cc['name'] == 'L4')
    V = math.pi*Rexit**2*abs(st['exit']-st['burn'])        # the pulse spread over the nozzle volume (order of magnitude)
    rho_m = pz['mass_kg']/V; vA = B/math.sqrt(MU0*rho_m) if B else 0.0
    me = 9.1093837e-31; rle = me*pz['exhaust_m_s']/(E_CHARGE*B) if B else math.inf
    return dict(species=out, B_exit_T=B, alfven_m_s=vA, alfven_mach=pz['exhaust_m_s']/vA if vA else math.inf,
                beta_exit=(pz['energy_J']['design']/V)/(B*B/(2*MU0)) if B else math.inf, electron_larmor_exit_m=rle,
                verdict='DETACHMENT_OPEN')


# ---------- flux compression (REDUCED_PLASMA_MODEL) -------------------------------------------------------------------------------

def flux_compression(s, cs, I, ys=1.0):
    """The pulse as a diamagnetic sphere of the stopping radius at the burn point (moment -2 pi R^3 B0 / mu0). Flux-conserving
    superconducting coils answer with dI = -L^-1 dPhi; the result is each coil's current, force and hoop change per pulse."""
    st = ve.stations(s); pz = plasma(s, ys); E = pz['energy_J']['design']
    B0 = abs(field(cs, I, st['burn'], 0.0)[1])
    if B0 == 0:
        return None
    R = (3*MU0*E/(2*math.pi*B0*B0))**(1/3)
    m = -2*math.pi*R**3*B0/MU0*math.copysign(1.0, field(cs, I, st['burn'], 0.0)[1])
    dphi = [MU0*m*c['r']**2/(2*(c['r']**2+(c['x']-st['burn'])**2)**1.5) for c in cs]
    L = inductance(cs); n = len(cs)
    A = [row[:]+[-dphi[i]] for i, row in enumerate(L)]
    for i in range(n):                                  # Gauss elimination
        p = max(range(i, n), key=lambda k: abs(A[k][i])); A[i], A[p] = A[p], A[i]
        for k in range(i+1, n):
            f = A[k][i]/A[i][i]
            for j in range(i, n+1):
                A[k][j] -= f*A[i][j]
    dI = [0.0]*n
    for i in range(n-1, -1, -1):
        dI[i] = (A[i][n]-sum(A[i][j]*dI[j] for j in range(i+1, n)))/A[i][i]
    I2 = [a+b for a, b in zip(I, dI)]
    F0, F1 = axial_forces(cs, I), axial_forces(cs, I2)
    reach = min(math.hypot(c['x']-st['burn'], c['r'])-c['cryostat'] for c in cs)
    return dict(radius_m=R, valid=R < 0.8*reach, nearest_cryostat_m=reach, B0_T=B0, moment_Am2=m, dI_At=dI, dI_rel=[d/i if i else 0.0 for d, i in zip(dI, I)],
                dF_N=[b-a for a, b in zip(F0, F1)], energy_J=stored_energy(cs, I2)-stored_energy(cs, I),
                note='Point-dipole bubble at the stopping radius; flux-conserving coils without cryostat eddy shielding (an upper bound on the '
                     'coil response; the microsecond pulse is screened by the cryostat walls, which then carry the eddy heating instead). '
                     'Not valid (valid = false) when the bubble reaches within 0.8 of the nearest cryostat: then the coils sit inside the '
                     'compressed field and only a coupled plasma model can give their load.')


# ---------- one candidate: the full screen (cheap) ---------------------------------------------------------------------------------

def evaluate(s, cs, I, upper=None, with_particles=False, ys=1.0):
    """Every cheap metric of a current set on a coil set: capture margins (design energy; upper energy when its currents are given),
    topology, forces (two methods), hoop and case stress, conductor field, stored energy, dipole moment, stray field, cluster forces."""
    c = config(s); st = ve.stations(s); pz = plasma(s, ys)
    cap = capture(s, cs, I, pz['energy_J']['design'])
    cap_relax = capture(s, cs, I, pz['energy_J']['design'], protect=c['protect_relaxed'])
    F = axial_forces(cs, I); Fe = energy_forces(cs, I)
    hp = hoop(cs, I, s); Bc = conductor_field(cs, I)
    out = dict(currents_At=list(I), capture=cap, capture_relaxed=cap_relax, forces_N=F,
               force_check=max(abs(a-b) for a, b in zip(F, Fe))/max(1.0, max(abs(a) for a in F)),
               peak_force_N=max(abs(f) for f in F), hoop=hp, peak_case_u=max(h['u'] for h in hp), conductor_T=Bc, peak_conductor_T=max(Bc),
               energy_J=stored_energy(cs, I), dipole_Am2=dipole_moment(cs, I),
               B_burn_T=field(cs, I, st['burn'], 0.0)[1], B_shield_T=field(cs, I, st['shield_aft'], 0.0)[1],
               B_collar_T=math.hypot(*field(cs, I, st['collar_fwd'], ve.config(s)['geometry']['collar_outer_radius_m'])),
               nulls=nulls(cs, I, st['shield_aft'], st['exit']), mirror_ratio=mirror_ratio(cs, I, s),
               peak_current_At=max(abs(i) for i in I), turns=[abs(i)/vs.config(s)['conductor_current_A'] for i in I],
               current_density_A_m2=[abs(i)/(math.pi*q['a']**2) for q, i in zip(cs, I)])
    if upper is not None:
        out['capture_upper'] = capture(s, cs, upper, pz['energy_J']['upper'])
    if with_particles:
        out['particles'] = particles(s, cs, I)
    return out


def checks(s, ev):
    """Hard requirements of one evaluated candidate: dict(id -> (passed, value, limit)). Functional first, then hardware limits."""
    c = config(s)
    w = ev['capture']['worst']; wr = ev['capture_relaxed']['worst']
    extra = {}
    if 'particles' in ev:                 # MF-02 by test particles: the worst species' share reaching protected hardware
        hit = max(p['hit'] for p in ev['particles'].values())   # every obstacle (shield, cryostats, cage) is protected hardware
        extra['MF-02 test particles to protected hardware'] = (hit <= c['particle_hit_limit'], hit, c['particle_hit_limit'])
    return {**extra, 
        'MF-01/02 capture, shield protected': (w is not None and w >= c['capture_margin'], w, c['capture_margin']),
        'MF-01/02 capture, burn face as armour': (wr is not None and wr >= c['capture_margin'], wr, c['capture_margin']),
        'Winding case stress': (ev['peak_case_u'] <= 1.0, ev['peak_case_u'], 1.0),
        'Field at the conductor': (ev['peak_conductor_T'] <= c['conductor_field_limit_T'], ev['peak_conductor_T'], c['conductor_field_limit_T']),
        'Winding current density': (max(ev['current_density_A_m2']) <= c['winding_current_density_A_m2'], max(ev['current_density_A_m2']),
                                    c['winding_current_density_A_m2']),
    }


# ---------- optimisation -----------------------------------------------------------------------------------------------------------

def nelder_mead(f, x0, step, iters=400, tol=1e-9):
    """Deterministic Nelder-Mead (standard coefficients); returns (x, f(x), evaluations)."""
    n = len(x0); pts = [list(x0)]+[[x0[j]+(step[j] if j == i else 0.0) for j in range(n)] for i in range(n)]
    vals = [f(p) for p in pts]; ev = n+1
    for _ in range(iters):
        o = sorted(range(n+1), key=lambda k: vals[k]); pts = [pts[k] for k in o]; vals = [vals[k] for k in o]
        if abs(vals[-1]-vals[0]) <= tol*max(1.0, abs(vals[0])):
            break
        cen = [sum(p[j] for p in pts[:-1])/n for j in range(n)]
        xr = [cen[j]+(cen[j]-pts[-1][j]) for j in range(n)]; fr = f(xr); ev += 1
        if fr < vals[0]:
            xe = [cen[j]+2*(cen[j]-pts[-1][j]) for j in range(n)]; fe = f(xe); ev += 1
            pts[-1], vals[-1] = (xe, fe) if fe < fr else (xr, fr)
        elif fr < vals[-2]:
            pts[-1], vals[-1] = xr, fr
        else:
            xc = [cen[j]+0.5*(pts[-1][j]-cen[j]) for j in range(n)]; fc = f(xc); ev += 1
            if fc < vals[-1]:
                pts[-1], vals[-1] = xc, fc
            else:
                pts = [pts[0]]+[[pts[0][j]+0.5*(p[j]-pts[0][j]) for j in range(n)] for p in pts[1:]]
                vals = [vals[0]]+[f(p) for p in pts[1:]]; ev += n
    k = min(range(n+1), key=lambda k: vals[k])
    return pts[k], vals[k], ev


def _fast_capture(s, cs, I, E, protect, rays):
    """Worst protected capture margin on a coarse ray set (optimiser inner loop)."""
    return capture(s, cs, I, E, rays=rays, protect=protect)['worst'] or 0.0


def objective(s, cs, I, E, protect, rays, mode='force', margin=None, conductor=True):
    """Penalised objective of the optimiser: capture margin, case stress, conductor field and current density are constraints; the
    objective is the peak axial coil force (MN) or, in mode 'balanced', peak force plus the inter-engine dipole term."""
    c = config(s); margin = c['capture_margin'] if margin is None else margin
    w = _fast_capture(s, cs, I, E, protect, rays)
    hp = hoop(cs, I, s); u = max(h['u'] for h in hp)
    jd = max(abs(i)/(math.pi*q['a']**2) for q, i in zip(cs, I))/c['winding_current_density_A_m2']
    bc = max(conductor_field(cs, I, n=2, m=8))/c['conductor_field_limit_T'] if conductor else 0.0
    F = max(abs(f) for f in axial_forces(cs, I))/1e6
    val = F
    if mode == 'balanced':
        m0 = abs(dipole_moment(coil_set(s), currentsof(s, 'NOMINAL')))
        val = F+c['dipole_weight_MN']*abs(dipole_moment(cs, I))/m0
    pen = 1e5*max(0.0, margin+c['optimiser_margin_buffer']-w)+1e5*max(0.0, u-0.995)+1e4*max(0.0, jd-1.0)+1e4*max(0.0, bc-1.0)
    return val+pen


def currentsof(s, case):
    return vs.currents(s, case)


def optimise(s, name, margin=None, spec=None):
    """Re-run the stored candidate's optimisation from its recorded start (deterministic): returns (geometry, currents). margin overrides
    the required capture margin (Pareto sweep)."""
    c = config(s); spec = spec or next(k for k in c['candidates'] if k['id'] == name)
    pz = plasma(s); E = pz['energy_J']['design']; rays = list(range(0, 181, c['optimiser_ray_step_deg']))
    protect = c['protect_strict'] if spec['protect'] == 'strict' else c['protect_relaxed']
    base = coil_set(s); start = [v*1e6 for v in spec['start_MAt']]
    geo_keys = [tuple(k.split('.')) for k in spec.get('geometry_free', [])]
    def unpack(x):
        I = [v*1e6 for v in x[:6]]; geo = {}
        for (cn, key), v in zip(geo_keys, x[6:]):
            geo.setdefault(cn, {})[key] = v
        return I, geo
    def f(x):
        I, geo = unpack(x); cs = coil_set(s, geo)
        if geo and not geometry_ok(s, cs, spec):
            return 1e9
        return objective(s, cs, I, E, protect, rays, mode=spec['mode'], margin=margin)
    x0 = [v/1e6 for v in start]+[next(cc for cc in base if cc['name'] == cn)[key] for cn, key in geo_keys]
    step = [2.0]*6+[(0.05 if key == 'a' else 0.5) for _, key in geo_keys]
    best = None
    for rnd in range(spec.get('restarts', 3)):
        x, v, _ = nelder_mead(f, x0, step, iters=c['optimiser_iterations'])
        if best is None or v < best[1]:
            best = (x, v)
        x0 = x; step = [st_*0.5 for st_ in step]
    I, geo = unpack(best[0])
    return geo, I


def geometry_ok(s, cs, spec):
    """Candidate geometry bounds: within the drawn envelope radius (cryostat outside), coils' cryostats apart by the cage clearance,
    stations between the shield aft face and the exit, each change inside the candidate's bounds."""
    g = ve.config(s)['geometry']; st = ve.stations(s); base = {c['name']: c for c in coil_set(s)}; ring = ve.ring_station(s)[0]
    for c in cs:
        if c['r']+c['cryostat'] > g['max_radius_m']-g['cage_clearance_m']-g['cage_longeron_radius_m']:
            return False
        if not (st['exit']-1e-9 <= c['x'] <= st['shield_aft']-c['cryostat']):
            return False
        b = base[c['name']]
        if c['group'] == 'closure' and ring-c['x'] < spec.get('min_strut_rake', 0.7)*(ring-b['x']):   # struts to the reaction ring keep most of their rake
            return False
        if not (b['a']-1e-9 <= c['a'] <= c['cryostat']-spec.get('cryostat_gap_m', 0.15)):   # thicker windings only, inside the drawn cryostat
            return False
        if abs(c['x']-b['x']) > spec.get('max_shift_m', 1.0) or abs(c['r']/b['r']-1) > spec.get('max_radius_change', 0.1):
            return False
    for i, a in enumerate(cs):
        for b in cs[i+1:]:
            if math.hypot(a['x']-b['x'], a['r']-b['r']) < a['cryostat']+b['cryostat']+0.2:
                return False
    return True


# ---------- candidates ----------------------------------------------------------------------------------------------------------

def candidate(s, name):
    """A candidate's coil set, design currents and upper-bound currents. Historical cases come from vertex_structure; the others from
    [vertex_engine.magnet.candidates] (the optimiser's stored result; tests re-check it meets its requirements). The upper set scales
    the design currents by sqrt(E_upper / E_design) (capture scales as B^2 at fixed geometry). M4 scales the pulse yield."""
    c = config(s); pz = plasma(s); k_up = math.sqrt(pz['energy_J']['upper']/pz['energy_J']['design'])
    if name in HISTORICAL:
        I = vs.currents(s, name)
        return dict(id=f'M0-{name}', name=name, cs=coil_set(s), I=I, upper=vs.currents(s, 'CONSERVATIVE'), status='HISTORICAL',
                    evidence='1.2 rule', compression=vs.compression_factor(s, name), yield_share=1.0)
    spec = next(k for k in c['candidates'] if k['id'] == name)
    cs = coil_set(s, {k: dict(v) for k, v in spec.get('geometry', {}).items()})
    y = spec.get('yield_share', 1.0)
    src = next(k for k in c['candidates'] if k['id'] == spec['from']) if spec.get('from') else spec
    if spec.get('from'):
        cs = coil_set(s, {k: dict(v) for k, v in src.get('geometry', {}).items()})
    I = [v*1e6*math.sqrt(y) for v in src['currents_MAt']]
    return dict(id=name, name=spec['name'], cs=cs, I=I, upper=[i*k_up for i in I], status=spec['status'], evidence=spec['evidence'],
                note=spec['note'], compression=1.0, yield_share=y, spec=spec)


def candidate_ids(s):
    return ['NOMINAL', 'CONSERVATIVE', 'EXTREME']+[k['id'] for k in config(s)['candidates']]


def scaled_spec(s, cand):
    """A copy of the spec in which the candidate is the engine: its coil geometry in the stations, its design currents as NOMINAL and
    its upper-bound currents as CONSERVATIVE (vertex_structure.currents reads explicit sets), the yield share applied to the pulse."""
    t = copy.deepcopy(s); g = t['vertex_engine']['geometry']
    by = {c['name']: c for c in cand['cs']}
    st0 = ve.stations(s)
    for c in g['closure_coils']:
        b = by[c['name']]; c['r_m'] = b['r']; c['winding_minor_m'] = b['a']
        c['dx_from_shield_m'] = c['dx_from_shield_m']+(b['x']-next(q for q in st0['coils'] if q['name'] == c['name'])['x'])
    for l in g['loops']:
        b = by[l['name']]; l['r_m'] = b['r']; l['winding_minor_m'] = b['a']
        l['dx_from_burn_m'] = l['dx_from_burn_m']+(b['x']-next(q for q in st0['loops'] if q['name'] == l['name'])['x'])
    t['vertex_engine']['structure']['explicit_currents'] = {'NOMINAL': list(cand['I']), 'CONSERVATIVE': list(cand['upper']),
                                                            'EXTREME': list(cand['upper'])}
    return t


def structure(s, name):
    """The candidate through the 1.2 structural screen with the 1.2 member sizes and rules: engine member utilisation (design and upper
    currents), winding case, inter-engine force, cluster frame (design sets) and mass of members resized to carry the design case."""
    cand = candidate(s, name)
    if name in HISTORICAL:
        t = s; dn, up = name, ('CONSERVATIVE' if name == 'NOMINAL' else name)
    else:
        t = scaled_spec(s, cand); dn, up = 'NOMINAL', 'CONSERVATIVE'
    em, eu = vs.engine_members(t, dn), vs.engine_members(t, up)
    grp = list(vs.ENGINE_KEYS)+['winding']
    ie = vs.inter_engine(t, dn)
    return dict(u_design={k: em[k]['u'] for k in grp}, u_upper={k: eu[k]['u'] for k in grp}, peak_u_design=max(em[k]['u'] for k in grp),
                peak_u_upper=max(eu[k]['u'] for k in grp), inter_engine_N=abs(ie[0]['radial_N']), inter_torque_Nm=math.sqrt(vc.dot(ie[0]['torque_Nm'], ie[0]['torque_Nm'])),
                collar_N=em['collar']['closure_in_N'])


def resized_mass(s, name):
    """Members resized (vertex_structure.iterate_sizes, the 1.2 design loop) to carry the candidate's design currents: the radii, engine and
    frame mass, and whether the resized engine still fits the drawn envelope radius. A report, never applied to the ship."""
    if name in HISTORICAL and name != 'NOMINAL':
        return None
    cand = candidate(s, name)
    t = s if name in HISTORICAL else scaled_spec(s, cand)
    t2, hist = vs.iterate_sizes(t)
    fit = ve.fit_screen(t2)
    g0, g1 = s['vertex_engine']['geometry'], t2['vertex_engine']['geometry']
    xr, Rr = ve.ring_station(t2); ar = g1['reaction_ring_minor_m']
    ring_gap = min(math.hypot(c['x']-xr, c['r']-Rr)-ar-c['cryostat'] for c in cand['cs'])
    return dict(engine_kg=ve.mass_estimate(t2)['total_kg'], frame_kg=vs.frame_mass(t2), rounds=len(hist), ring_to_cryostat_m=ring_gap,
                engine_radii={k: (g0[k], g1[k]) for k in vs.ENGINE_KEYS.values()},
                cluster_radii={k: (s['propulsion_cluster'][k], t2['propulsion_cluster'][k]) for k in hist[-1][1]},
                max_radius_m=fit['envelope']['max_radius'], max_radius_limit_m=fit['max_radius_limit'],
                fits=fit['envelope']['max_radius'] <= fit['max_radius_limit']+1e-9)


def comparison(s, with_particles=True, with_structure=True):
    """The decision table: every candidate's functional checks, hardware limits, loads and (optionally) particles and structure."""
    rows = []
    for name in candidate_ids(s):
        cand = candidate(s, name)
        ev = evaluate(s, cand['cs'], cand['I'], upper=cand['upper'], with_particles=with_particles, ys=cand['yield_share'])
        row = dict(id=cand['id'], name=cand['name'], status=cand['status'], evidence=cand['evidence'], yield_share=cand['yield_share'],
                   eval=ev, checks=checks(s, ev), compression=cand['compression'])
        if with_structure:
            row['structure'] = structure(s, name)
        rows.append(row)
    return rows


def degraded(s, cs, I, ys=1.0):
    """MF-06 degraded modes: each coil off in turn (a quenched or dumped coil, the others held): capture margin, peak force, the largest
    change of any coil's force, and whether a field null opens between the shield and the exit."""
    E = plasma(s, ys)['energy_J']['design']; st = ve.stations(s); F0 = axial_forces(cs, I); out = []
    for k, c in enumerate(cs):
        J = [0.0 if i == k else v for i, v in enumerate(I)]; F = axial_forces(cs, J)
        out.append(dict(off=c['name'], margin=capture(s, cs, J, E)['worst'], peak_force_N=max(abs(f) for f in F),
                        max_change_N=max(abs(a-b) for a, b in zip(F, F0)), nulls=len(nulls(cs, J, st['shield_aft'], st['exit']))))
    return out


def sensitivity(s, cs, I, d=0.05, ys=1.0):
    """MF-06 sensitivity: the capture margin with each coil's current d high and d low (the others held)."""
    E = plasma(s, ys)['energy_J']['design']; out = []
    for k, c in enumerate(cs):
        row = dict(coil=c['name'])
        for sg, key in ((1, 'up'), (-1, 'down')):
            J = [v*(1+sg*d) if i == k else v for i, v in enumerate(I)]
            row[key] = capture(s, cs, J, E)['worst']
        out.append(row)
    return out


def magnet_engineering(s, cs, I, ys=1.0):
    """Section 7 of the brief: turns, inductance, stored energy, dump voltage and ramp time at the lead current, and what the pulse train does
    to the cold mass (bounded by the flux-conserving response; screened by the cryostat wall's skin depth)."""
    c = config(s); sc = vs.config(s); I0 = sc['conductor_current_A']; L = inductance(cs); n = len(cs)
    W = stored_energy(cs, I); pz = plasma(s, ys); fc = flux_compression(s, cs, I, ys)
    rows = []
    for k, q in enumerate(cs):
        N = abs(I[k])/I0; wk = 0.5*I[k]*sum(L[k][j]*I[j] for j in range(n))
        rows.append(dict(name=q['name'], turns=N, self_H=L[k][k]*N*N, energy_J=wk, dump_voltage_V=2*abs(wk)/(I0*sc['quench_dump_time_s']),
                         ramp_s=2*abs(wk)/(I0*c['ramp_supply_V'])))
    w = 2*math.pi*pz['pulse_Hz']; delta = math.sqrt(2*c['cryostat_wall_resistivity_ohm_m']/(w*MU0))
    return dict(rows=rows, energy_J=W, lead_current_A=I0, ramp_supply_V=c['ramp_supply_V'],
                pulse=dict(rate_Hz=pz['pulse_Hz'], skin_depth_m=delta, wall_m=c['cryostat_wall_m'], screened=c['cryostat_wall_m'] > 3*delta,
                           charged_power_W=pz['energy_J']['design']*pz['pulse_Hz'],
                           heat_per_permille_W=1e-3*pz['energy_J']['design']*pz['pulse_Hz'],
                           compression_valid=bool(fc and fc['valid']),
                           max_current_swing=max(abs(x) for x in fc['dI_rel']) if fc else None))


def input_hash(s):
    """Hash of everything the magnetic results depend on (magnet config, coils, pulse, structure inputs, cluster placements)."""
    import hashlib, json
    blob = dict(magnet=config(s), coils=vs.coils(s), plasma={k: v for k, v in plasma(s).items() if k != 'species'}, structure=vs.config(s),
                geometry=ve.config(s)['geometry'], placements=vc.placements(s))
    return hashlib.sha256(json.dumps(blob, sort_keys=True, default=str).encode()).hexdigest()[:16]


def _pareto_point(s, m):
    spec = next(k for k in config(s)['candidates'] if k['id'] == 'M1')
    return optimise(s, 'M1', margin=m, spec=spec)


def pareto(s, margins=None):
    """Margin against cost: the currents-only optimum (M1 rules) for each required capture margin, with peak force, stored energy and
    peak case utilisation. Slow (minutes); its result is recorded in references/evidence/vertex_magnet.json and re-checked by the tests."""
    from concurrent.futures import ProcessPoolExecutor
    c = config(s); ms = list(margins or c['pareto_margins']); out = []
    with ProcessPoolExecutor(max_workers=len(ms)) as ex:
        res = list(ex.map(_pareto_point, [s]*len(ms), ms))
    for m, (geo, I) in zip(ms, res):
        cs = coil_set(s, geo); ev = evaluate(s, cs, I)
        out.append(dict(margin_required=m, currents_MAt=[round(i/1e6, 4) for i in I], margin=ev['capture']['worst'], peak_force_MN=ev['peak_force_N']/1e6,
                        energy_GJ=ev['energy_J']/1e9, case_u=ev['peak_case_u'], conductor_T=ev['peak_conductor_T'], dipole_MAm2=ev['dipole_Am2']/1e6))
    return out


def overlay(s, ids=None, seeds=12, ds=0.1):
    """Vacuum field lines of each candidate for Explore Ship's optional overlay: seeds on the burn plane from the axis to L2, traced both
    ways, as (x, rho) polylines in the engine frame at 1 cm steps. The viewer revolves them about the engine axis. Not plasma, not light."""
    st = ve.stations(s); out = {}
    for name in (ids or [config(s)['selected'], config(s)['overlay_compare']]):
        cand = candidate(s, name.removeprefix('M0-')); lines = []
        for k in range(seeds):
            rho = 0.4+(next(c['r'] for c in cand['cs'] if c['name'] == 'L2')-1.0)*k/(seeds-1)
            for sg in (1.0, -1.0):
                pts = field_line(cand['cs'], cand['I'], st['burn'], rho, ds=ds, n=700, sign=sg, box=(st['exit']-30.0, st['shield_aft'], 16.0))
                lines.append([round(v, 2) for p in pts[::3] for v in p])
        out[cand['id']] = dict(name=cand['name'], lines=lines, B_burn_T=round(field(cand['cs'], cand['I'], st['burn'], 0.0)[1], 3))
    return out


def inspection(s):
    """The magnet block of the engine inspection manifest (vertex_inspect): per coil and for the active configuration and the compared
    candidate, current, axial force, conductor field, case utilisation and turns; each candidate's verdict line. Field lines are not
    here: web_export writes overlay(s) to its own file, which the viewer fetches only when the field overlay is switched on."""
    c = config(s); out = dict(disclaimer='Vacuum magnetic field computed from the coil currents (vertex_magnet, exact loop fields). It is '
                              'not visible light and not plasma: no self-consistent plasma response, detachment unproven.',
                              active=c['selected'], compare=c['overlay_compare'], verdict=c['verdict'], configs={})
    for name in (c['selected'], c['overlay_compare']):
        cand = candidate(s, name.removeprefix('M0-')); ev = evaluate(s, cand['cs'], cand['I'], ys=cand['yield_share'])
        ev['particles'] = particles(s, cand['cs'], cand['I'], species=c['species'][:1])   # every species gives the same shares (magnetised)
        ch = checks(s, ev)
        out['configs'][cand['id']] = dict(
            name=cand['name'], status=cand['status'], passed=all(ok for ok, _, _ in ch.values()),
            failed=[k for k, (ok, _, _) in ch.items() if not ok], capture_margin=None if ev['capture']['worst'] is None else round(ev['capture']['worst'], 3),
            B_burn_T=round(ev['B_burn_T'], 3), B_shield_T=round(ev['B_shield_T'], 3),
            coils={q['name']: [round(i/1e6, 3), round(f/1e6, 1), round(b, 2), round(h['u'], 3), round(abs(i)/vs.config(s)['conductor_current_A'])]
                   for q, i, f, b, h in zip(cand['cs'], cand['I'], ev['forces_N'], ev['conductor_T'], ev['hoop'])})
    out['coil_fields'] = ['MA-turns', 'axial force MN (+ forward)', 'peak field at the conductor T', 'winding case utilisation', 'turns at the lead current']
    return out


def report(s, with_particles=True):
    """Everything the engineering page, the inspection manifest and the evidence file read."""
    pz = plasma(s); nom = candidate(s, 'NOMINAL')
    st = ve.stations(s)
    B = abs(field(nom['cs'], nom['I'], st['burn'], 0.0)[1])
    sp = [dict(sp, larmor_at_burn_m=larmor(sp, B, speed(sp, pz['exhaust_m_s']*sp.get('bulk_speed_factor', 1.0))),
               speed_m_s=speed(sp, pz['exhaust_m_s']*sp.get('bulk_speed_factor', 1.0))) for sp in config(s)['species']]
    rows = comparison(s, with_particles=with_particles)
    for r in rows:
        cand = candidate(s, r['name'] if r['name'] in HISTORICAL else r['id'])
        r['resized'] = resized_mass(s, r['name'] if r['name'] in HISTORICAL else r['id'])
        r['degraded'] = degraded(s, cand['cs'], cand['I'], cand['yield_share'])
        r['sensitivity'] = sensitivity(s, cand['cs'], cand['I'], ys=cand['yield_share'])
        r['magnet'] = magnet_engineering(s, cand['cs'], cand['I'], cand['yield_share'])
        r['coils'] = [dict(name=q['name'], x=q['x'], r=q['r'], a=q['a'], cryostat=q['cryostat']) for q in cand['cs']]
        r['detachment'] = detachment(s, cand['cs'], cand['I'], cand['yield_share'])
        r['flux_compression'] = flux_compression(s, cand['cs'], cand['I'], cand['yield_share'])
    return dict(version=config(s)['version'], input_hash=input_hash(s), stations={k: v for k, v in st.items() if not isinstance(v, list)}, plasma=pz, species=sp, candidates=rows, selected=config(s)['selected'],
                verdict=config(s)['verdict'], overlay=overlay(s, seeds=8, ds=0.15))


def evidence(s, path, with_pareto=True):
    """Write the full report (and the Pareto sweep) as the evidence file the engineering page reads; checks are JSON-safe."""
    import json
    R = report(s)
    for r in R['candidates']:
        r['checks'] = {k: dict(passed=ok, value=v, limit=lim) for k, (ok, v, lim) in r['checks'].items()}
        r['eval']['capture'].pop('rows_fine', None)
    if with_pareto:
        R['pareto'] = pareto(s)
    elif Path(path).exists():
        R['pareto'] = json.loads(Path(path).read_text()).get('pareto')
    Path(path).write_text(json.dumps(R, indent=1, default=str)+'\n')
    return R


if __name__ == '__main__':
    import json
    from spec import load
    S = load(Path(__file__).resolve().parents[2])[0]
    if '--evidence' in sys.argv:
        evidence(S, Path(__file__).resolve().parents[2]/'references/evidence/vertex_magnet.json', with_pareto='--no-pareto' not in sys.argv)
        sys.exit(0)
    if '--optimise' in sys.argv:
        for k in config(S)['candidates']:
            if k.get('optimised'):
                geo, I = optimise(S, k['id'])
                print(k['id'], 'currents_MAt =', [round(i/1e6, 3) for i in I], 'geometry =', {n: {q: round(v, 3) for q, v in d.items()} for n, d in geo.items()})
        sys.exit(0)
    for row in comparison(S, with_particles='--particles' in sys.argv, with_structure='--structure' in sys.argv):
        ev = row['eval']
        print(f"{row['id']:<16} I[MAt] {[round(i/1e6, 2) for i in ev['currents_At']]}  B_burn {ev['B_burn_T']:+.2f} T  B_shield {ev['B_shield_T']:+.2f}"
              f"  Fpk {ev['peak_force_N']/1e6:7.1f} MN  W {ev['energy_J']/1e9:6.2f} GJ  Bc {ev['peak_conductor_T']:.1f} T  m {ev['dipole_Am2']/1e6:+.0f} MA m2")
        for k, (ok, v, lim) in row['checks'].items():
            print(f"    {'PASS' if ok else 'FAIL'} {k}: {v if v is None else round(v, 3)} (limit {lim:g})")
        if 'particles' in ev:
            for k, p in ev['particles'].items():
                print(f"    particles {k}: aft {p['aft']:.2f} hit {p['hit']:.2f} {p['hits']} out {p['out']:.2f} trapped {p['trapped']:.2f} axial {p['axial_fraction']:.2f} div90 {p['divergence_p90_deg']}")
        if 'structure' in row:
            print(f"    structure u design {row['structure']['peak_u_design']:.2f} upper {row['structure']['peak_u_upper']:.2f}  inter-engine {row['structure']['inter_engine_N']/1e6:.1f} MN")
