"""Vertex Engine 1.4: coupled plasma response (bounded D-21) and the architecture decision. Pure, standard library only.

Engine 1.3 (vertex_magnet) solved the vacuum field exactly and screened the pulse with test particles and an energy balance. This module
asks whether the plasma's own response changes that verdict, how robust the 1.3 particle numbers are, where the energy that is not
exhaust goes, and which architecture change is the smallest defensible one. It never changes the engine: the 1.2 geometry and currents
(M0-NOMINAL) stay the active configuration, M0 to M4 stay reproducible research records.

Levels of evidence (each reported separately, never merged into one PASS):
  PARTICLE_AUDIT               the 1.3 test-particle screen re-run with convergence, timestep, origin and energy ladders, energy weights
                               and a loss-cone map, checked against the adiabatic mirror loss cone
  REGIME_SCREENED              dimensionless parameters of the pulse (beta, Larmor and skin depth against size, collisionality, Alfven
                               Mach) that decide which plasma model applies (MHD, Hall, two-fluid, hybrid, full PIC)
  COUPLED_CAVITY_MODEL         the reduced self-consistent model (D21-B): a perfectly diamagnetic sharp-boundary cavity (field 0 inside,
                               flux function 0 on its surface) whose sheet current and the six flux-conserving coils are solved together
                               every step; sector (thin-shell) markers carry the energy; conservation ledger for energy and momentum
  KINETIC_MARGIN_SCREENED      Larmor penetration of each species through the compressed boundary field near hardware (D21-C screen)
  NOT_EXECUTED                 hybrid-PIC and 3D runs: their cost is estimated (gate D21-D), not run without separate approval

python3 src/wayfarer/vertex_plasma.py [--evidence]  prints the summary (or writes references/evidence/vertex_plasma.json).
"""
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vertex_engine as ve
import vertex_magnet as vm
import vertex_structure as vs

MU0 = vm.MU0
QE = vm.E_CHARGE
AMU = vm.AMU
ME = 9.1093837015e-31
EPS0 = 8.8541878128e-12
CLIGHT = 299792458.0
SIGMA_SB = 5.670374419e-8
EVIDENCE = ('PARTICLE_AUDIT', 'REGIME_SCREENED', 'COUPLED_CAVITY_MODEL', 'KINETIC_MARGIN_SCREENED', 'NOT_EXECUTED')
EVIDENCE_PATH = Path(__file__).resolve().parents[2]/'references'/'evidence'/'vertex_plasma.json'


def config(s):
    return s['vertex_engine']['plasma']


def _cand(s, cid):
    return vm.candidate(s, cid)


def label(cid):
    return 'M0-NOMINAL' if cid in vm.HISTORICAL else cid


# ---------- the pulse: populations and energy weights ------------------------------------------------------------------------------

def populations(s, f_fast=None):
    """Energy share of the charged pulse per species: escaping fusion products (share f_fast, split 14.7 : 3.6 between p and alpha) and
    burn debris (the rest; D and 3He at the same speed, so their energy splits by mass at the configured atom ratio)."""
    c = config(s); f = c['fast_product_share'][1] if f_fast is None else f_fast
    sp = {q['id']: q for q in vm.config(s)['species']}
    mD, mH = sp['D_debris']['mass_amu'], sp['He3_debris']['mass_amu']; r = c['debris_atom_ratio_D_He3']
    wD = r*mD/(r*mD+mH)
    return {'D_debris': (1-f)*wD, 'He3_debris': (1-f)*(1-wD), 'p_14.7MeV': f*14.7/18.3, 'alpha_3.6MeV': f*3.6/18.3}


def species_speed(s, sp, vfac=1.0):
    pz = vm.plasma(s)
    return vm.speed(sp, pz['exhaust_m_s']*sp.get('bulk_speed_factor', 1.0))*vfac


# ---------- 3. the particle audit ---------------------------------------------------------------------------------------------------

_S = {}


def _particle_task(args):
    cid, spid, n, dt_gyro, origin, vfac = args
    s = _S['s']; cand = _cand(s, cid); cs, I = cand['cs'], cand['I']; hw = vm.hardware(s, cs)
    sp = next(q for q in vm.config(s)['species'] if q['id'] == spid); v = species_speed(s, sp, vfac)
    burn = ve.stations(s)['burn']; rows = []; t0 = time.process_time()
    for d in vm._dirs(n):
        r = vm.push(s, cs, I, sp, v, d, hw, dt_gyro=dt_gyro, origin=origin)
        um = math.sqrt(sum(a*a for a in r['u']))
        rows.append(dict(th=math.degrees(math.acos(max(-1.0, min(1.0, d[0])))), outcome=r['outcome'], obstacle=r.get('obstacle'),
                         returned=r['xmin'] < burn-0.5, ux=r['u'][0]/um, err=r['err']))
    return args, rows, time.process_time()-t0


def summarise(rows):
    """Shares of one particle set by outcome and obstacle, its binomial standard error on the shield share, the aft axial fraction and
    divergence, and the loss-cone map (shield share per 10 degree bin of launch angle from +x, forward)."""
    n = len(rows); hits = {}
    for r in rows:
        if r['outcome'] == 'HIT':
            hits[r['obstacle']] = hits.get(r['obstacle'], 0)+1
    aft = [r for r in rows if r['outcome'] == 'AFT']; sh = hits.get('SHIELD', 0)/n
    ret = sum(1 for r in rows if r['outcome'] == 'HIT' and r['obstacle'] == 'SHIELD' and r['returned'])
    bins = []
    for b in range(18):
        inb = [r for r in rows if b*10 <= r['th'] < (b+1)*10]
        if inb:
            bins.append(dict(deg=b*10, n=len(inb), shield=sum(1 for r in inb if r['obstacle'] == 'SHIELD')/len(inb),
                             hit=sum(1 for r in inb if r['outcome'] == 'HIT')/len(inb), aft=sum(1 for r in inb if r['outcome'] == 'AFT')/len(inb)))
    ang = sorted(math.degrees(math.acos(max(-1.0, min(1.0, -r['ux'])))) for r in aft)
    return dict(n=n, shield=sh, shield_se=math.sqrt(max(sh*(1-sh), 1.0/n)/n), hits={k: v/n for k, v in sorted(hits.items())},
                hit=sum(hits.values())/n, aft=len(aft)/n, out=sum(r['outcome'] == 'OUT' for r in rows)/n,
                trapped=sum(r['outcome'] == 'TRAPPED' for r in rows)/n,
                shield_returned=(ret/hits['SHIELD']) if hits.get('SHIELD') else 0.0,
                axial_fraction=(sum(-r['ux'] for r in aft)/len(aft)) if aft else 0.0,
                divergence_p90_deg=ang[int(0.9*(len(ang)-1))] if ang else None, max_energy_error=max(r['err'] for r in rows), loss_cone=bins)


def mirror_loss_cone(s, cid):
    """Adiabatic mirror prediction of the forward loss: an isotropic source at field B0 between a forward maximum Bm loses the share
    (1 - sqrt(1 - B0/Bm)) / 2 forward; with Bm <= B0 (a cusp or null forward) the whole forward hemisphere (0.5) is unconfined."""
    cand = _cand(s, cid); R = vm.mirror_ratio(cand['cs'], cand['I'], s)
    f = 0.5 if R <= 1.0 else (1-math.sqrt(1-1/R))/2
    return dict(mirror_ratio=R, forward_loss=f, half_angle_deg=90.0 if R <= 1.0 else math.degrees(math.asin(math.sqrt(1/R))))


def audit_tasks(s, quick=False):
    c = config(s); sps = [q['id'] for q in vm.config(s)['species']]; ns = c['audit_directions'][:2] if quick else c['audit_directions']
    t = []
    for cid in c['candidates']:
        for sp in sps:
            for n in ns:
                t.append((cid, sp, n, 40, (0.0, 0.0, 0.0), 1.0))
        for g in c['audit_dt_gyro']:
            if g != 40:
                t.append((cid, 'D_debris', 200, g, (0.0, 0.0, 0.0), 1.0))
        o = c['audit_origin_m']
        for org in ((o, 0.0, 0.0), (-o, 0.0, 0.0), (0.0, o, 0.0)):
            t.append((cid, 'D_debris', 200, 40, org, 1.0))
        for f in c['audit_speed_factors']:
            if f != 1.0:
                t.append((cid, 'D_debris', 200, 40, (0.0, 0.0, 0.0), f))
    return t


def run_tasks(s, tasks, workers=None):
    """Run particle tasks in parallel (fork shares the loaded spec); returns {task: (rows, cpu_s)}."""
    import multiprocessing as mp
    _S['s'] = s
    if workers == 1:
        res = [_particle_task(t) for t in tasks]
    else:
        with mp.get_context('fork').Pool(workers) as pool:
            res = pool.map(_particle_task, tasks, chunksize=1)
    return {a: (rows, cpu) for a, rows, cpu in res}


def audit(s, quick=False, workers=None):
    """3.1-3.4: convergence of the shield share with the number of directions per species, timestep, origin and speed sensitivity, count-,
    energy-, mass- and momentum-weighted interception, the loss-cone map and direct against returned shield hits; the mirror check."""
    c = config(s); tasks = audit_tasks(s, quick); t0 = time.time(); R = run_tasks(s, tasks, workers)
    cpu = sum(v[1] for v in R.values()); out = dict(cpu_s=cpu, wall_s=time.time()-t0, candidates={})
    sps = [q['id'] for q in vm.config(s)['species']]; pz = vm.plasma(s)
    for cid in c['candidates']:
        ns = sorted({t[2] for t in tasks if t[0] == cid and t[3] == 40 and t[4] == (0.0, 0.0, 0.0) and t[5] == 1.0 and t[1] == 'D_debris'})
        conv = {sp: [dict(n=n, **{k: v for k, v in summarise(R[(cid, sp, n, 40, (0.0, 0.0, 0.0), 1.0)][0]).items() if k in ('shield', 'shield_se', 'hit', 'aft')})
                     for n in ns] for sp in sps}
        best = {sp: summarise(R[(cid, sp, ns[-1], 40, (0.0, 0.0, 0.0), 1.0)][0]) for sp in sps}
        dt = [dict(dt_gyro=g, shield=summarise(R[(cid, 'D_debris', 200, g, (0.0, 0.0, 0.0), 1.0)][0])['shield']) for g in c['audit_dt_gyro']]
        o = c['audit_origin_m']
        org = [dict(origin_m=list(p), shield=summarise(R[(cid, 'D_debris', 200, 40, p, 1.0)][0])['shield'])
               for p in ((0.0, 0.0, 0.0), (o, 0.0, 0.0), (-o, 0.0, 0.0), (0.0, o, 0.0))]
        spd = [dict(speed_factor=f, shield=summarise(R[(cid, 'D_debris', 200, 40, (0.0, 0.0, 0.0), f)][0])['shield']) for f in c['audit_speed_factors']]
        weights = {}
        for f in c['fast_product_share']:
            w = populations(s, f)
            weights[str(f)] = dict(energy=sum(w[sp]*best[sp]['shield'] for sp in sps),
                                   hardware_energy=sum(w[sp]*best[sp]['hit'] for sp in sps),
                                   aft_energy=sum(w[sp]*best[sp]['aft'] for sp in sps))
            ms = {}
            for q in vm.config(s)['species']:
                v = species_speed(s, q); ms[q['id']] = w[q['id']]*2/v**2      # mass share ~ energy / v^2
            tot = sum(ms.values()); weights[str(f)]['mass'] = sum(ms[sp]/tot*best[sp]['shield'] for sp in sps)
            mom = {sp: ms[sp]*species_speed(s, next(q for q in vm.config(s)['species'] if q['id'] == sp)) for sp in sps}
            tm = sum(mom.values()); weights[str(f)]['momentum'] = sum(mom[sp]/tm*best[sp]['shield'] for sp in sps)
        count = sum(best[sp]['shield'] for sp in sps)/len(sps)
        spread = max(best[sp]['shield'] for sp in sps)-min(best[sp]['shield'] for sp in sps)
        se = max(best[sp]['shield_se'] for sp in sps)
        sens = max([abs(d['shield']-dt[1]['shield']) for d in dt]+[abs(d['shield']-org[0]['shield']) for d in org]+
                   [abs(d['shield']-spd[1]['shield']) for d in spd])
        out['candidates'][label(cid)] = dict(convergence=conv, best=best, timestep=dt, origin=org, speed=spd, weights=weights, count_weighted=count,
                                             species_spread=spread, uncertainty=math.sqrt(se**2+sens**2+(spread/2)**2), mirror=mirror_loss_cone(s, cid))
    return out


# ---------- 4.2 the regime: which plasma model applies ------------------------------------------------------------------------------

def coulomb_mfp(n, W_eV, Z=1, lnL=20.0):
    """Order-of-magnitude 90-degree Coulomb mean free path (m) of an ion of energy W in a plasma of ion density n."""
    b0 = Z*Z*QE*QE/(4*math.pi*EPS0*2*W_eV*QE)
    return 1.0/(8*math.pi*n*b0*b0*lnL)


def regime(s, cid, cav=None):
    """Dimensionless parameters of the pulse at its cavity size: beta at the burn point, ion Larmor radius and ion skin depth against the
    cavity radius, the Coulomb mean free path, the Alfven Mach number, the electron Larmor radius, the interaction radius of the escaping
    fusion products against the hardware distance; then the verdict of each model family against them."""
    cand = _cand(s, cid); cs, I = cand['cs'], cand['I']; pz = vm.plasma(s, cand['yield_share']); st = ve.stations(s)
    E = pz['energy_J']['design']; v0 = pz['exhaust_m_s']; B0 = abs(vm.field(cs, I, st['burn'], 0.0)[1])
    R = (3*MU0*E/(2*math.pi*B0*B0))**(1/3)          # 1.3 energy-balance radius (field energy of a sphere at B0 = pulse energy)
    if cav:
        R = cav['mean_stop_m'] or R
    sp = {q['id']: q for q in vm.config(s)['species']}
    w = populations(s); md = (w['D_debris']+w['He3_debris'])*E*2/v0**2
    mi = (sp['D_debris']['mass_amu']+sp['He3_debris']['mass_amu'])/2*AMU; Ni = md/mi
    V = 4/3*math.pi*R**3; n = Ni/V
    Bb = math.sqrt(2*MU0*cav['peak_pressure_Pa']) if cav and cav.get('peak_pressure_Pa') else 1.5*B0
    wpi = math.sqrt(n*QE*QE/(EPS0*sp['D_debris']['mass_amu']*AMU)); di = CLIGHT/wpi
    W_D = 0.5*sp['D_debris']['mass_amu']*AMU*v0**2/QE
    lam = coulomb_mfp(n, W_D)
    larm = {k: vm.larmor(q, Bb, species_speed(s, q)) for k, q in sp.items()}
    beta0 = (E/V)/(B0*B0/(2*MU0))
    vA = Bb/math.sqrt(MU0*n*mi); rle = ME*v0/(QE*Bb)
    dist = min(d for _, d, o in vm.hardware_rays(s, cs, list(range(0, 181, 5))) if d)
    fast = {}
    for f in config(s)['fast_product_share']:
        Rf = (3*MU0*f*E/(2*math.pi*B0*B0))**(1/3)
        fast[str(f)] = dict(interaction_radius_m=Rf, collective=Rf < dist, note='forms its own diamagnetic front before the hardware' if Rf < dist else
                            'reaches hardware before its pressure falls to the field: vacuum-field test particles (1.3) apply')
    p = dict(radius_m=R, density_m3=n, beta_burn=beta0, B_boundary_T=Bb, ion_skin_m=di, skin_over_R=di/R,
             larmor_over_R={k: v/R for k, v in larm.items()}, larmor_m=larm, mfp_m=lam, mfp_over_R=lam/R, alfven_mach=v0/vA,
             electron_larmor_m=rle, electron_larmor_over_R=rle/R, nearest_hardware_m=dist, fast_products=fast,
             expansion_time_s=R/v0, ion_gyro_s=2*math.pi*sp['D_debris']['mass_amu']*AMU/(QE*Bb))
    big_rl = max(p['larmor_over_R'].values())
    models = [
        dict(id='IDEAL_MHD', fits=False, why=f"collisionless (mfp/R {lam/R:.1e}) and finite ion Larmor radius (r_L/R up to {big_rl:.2f}): no "
             'collisional closure; ideal MHD gives the cavity shape only as a limit and misses kinetic loss-cone physics'),
        dict(id='RESISTIVE_MHD', fits=False, why='the plasma is collisionless; a Spitzer resistivity would be fictitious'),
        dict(id='HALL_TWO_FLUID', fits=di/R < 0.2, why=f'ion skin depth {di:.2f} m against {R:.1f} m: Hall terms matter in the boundary layer only; '
             'no kinetic ion distribution'),
        dict(id='SHARP_BOUNDARY_CAVITY', fits=di/R < 0.1 and beta0 > 1, why=f'beta {beta0:.0f} at the burn point, skin depth and debris Larmor radius '
             f'small against R: the plasma excludes the field (B = 0 inside) behind a thin sheet; selected for D21-B with explicit limits'),
        dict(id='HYBRID_PIC', fits=True, why='kinetic ions, fluid electrons: the right model for loss cone, Larmor penetration and flutes; '
             'PHARE (GPL-3.0, Cartesian AMR, CPU/MPI) or WarpX hybrid (BSD-3-Clause-LBNL); cost in gate D21-D, not executed'),
        dict(id='FULL_PIC', fits=False, why=f'electron scales (r_Le {rle:.1e} m, Debye length far smaller) against a {R:.0f} m domain: '
             'only with artificial mass ratio and density; useful later for electron detachment (Kyushu University laser-fusion-rocket PIC)'),
    ]
    p['models'] = models; p['selected'] = 'SHARP_BOUNDARY_CAVITY'
    return p


def hybrid_cost(s, reg, t_end_s=1.0e-6, ppc=100, ns_per_push=1.0e-6, bytes_per_particle=72):
    """Gate D21-D: cost of a hybrid-PIC run that resolves the ion skin depth (cell d_i / 2) over the engine (30 m x 20 m radius) for the
    pulse (1 microsecond), in 2D (RZ or slab) and 3D. CFL on the fastest ion and the whistler limit dt < dx^2 / (pi d_i^2 Omega_ci)."""
    dx = reg['ion_skin_m']/2; Lx, Lr = 30.0, 20.0; vmax = 5.3e7
    Om = 2*math.pi/reg['ion_gyro_s']
    dt = min(0.5*dx/vmax, dx*dx/(math.pi*reg['ion_skin_m']**2*Om))
    steps = t_end_s/dt; out = {}
    for name, cells in (('2D', (Lx/dx)*(Lr/dx)), ('3D', (Lx/dx)*(2*Lr/dx)**2)):
        npart = cells*ppc; cpu = npart*steps*ns_per_push
        out[name] = dict(cells=cells, particles=npart, steps=steps, core_hours=cpu/3600, memory_GB=npart*bytes_per_particle/1e9)
    out['assumptions'] = f'dx = d_i/2 = {dx:.3f} m, {ppc} particles per cell, about 1 microsecond per particle push per core, 72 bytes per particle'
    return out


# ---------- 4.4 D21-B: the coupled cavity ------------------------------------------------------------------------------------------

def _M(a, rho, z):
    """Mutual inductance (H) between a loop of radius a and a coaxial circle of radius rho at axial offset z: the flux through the
    circle per ampere in the loop (2 pi times the flux function)."""
    if a <= 0.0 or rho <= 0.0:
        return 0.0
    return vs.mutual(a, rho, z)


def _solve(A, b):
    n = len(b); M = [row[:]+[b[i]] for i, row in enumerate(A)]
    for i in range(n):
        p = max(range(i, n), key=lambda k: abs(M[k][i])); M[i], M[p] = M[p], M[i]
        piv = M[i][i]
        for k in range(i+1, n):
            f = M[k][i]/piv
            if f:
                rk, ri = M[k], M[i]
                for j in range(i, n+1):
                    rk[j] -= f*ri[j]
    x = [0.0]*n
    for i in range(n-1, -1, -1):
        x[i] = (M[i][n]-sum(M[i][j]*x[j] for j in range(i+1, n)))/M[i][i]
    return x


def sheet(cs, I0, pts, rings, L=None, flux=True):
    """Sheet currents J (one ring per surface point, inside the surface) and coil current changes dI so that the flux through every
    surface circle is zero (field excluded) and, when flux is True, each coil's flux linkage is unchanged (superconducting). Returns
    (J, dI); dI is zero for flux False (coils at fixed current)."""
    n = len(pts); m = len(cs) if flux else 0; A = []; b = []
    for (xj, rj) in pts:
        row = [_M(ri, rj, xj-xi) for (xi, ri) in rings]
        if flux:
            row += [_M(c['r'], rj, xj-c['x']) for c in cs]
        A.append(row); b.append(-sum(_M(c['r'], rj, xj-c['x'])*i for c, i in zip(cs, I0)))
    if flux:
        for k, c in enumerate(cs):
            A.append([_M(ri, c['r'], c['x']-xi) for (xi, ri) in rings]+[L[k][l] for l in range(m)]); b.append(0.0)
    x = _solve(A, b)
    return x[:n], (x[n:] if flux else [0.0]*len(cs))


def surface_field(cs, I1, rings, J, pts):
    """|B| at each surface point from the coils (currents I1) and the sheet rings: the field just outside the cavity (zero inside)."""
    out = []
    for (x, r) in pts:
        br = bx = 0.0
        for (xi, ri), j in zip(rings, J):
            a, b = vs.loop_field(ri, j, r, x-xi); br += a; bx += b
        for c, i in zip(cs, I1):
            a, b = vs.loop_field(c['r'], i, r, x-c['x']); br += a; bx += b
        out.append(math.hypot(br, bx))
    return out


def _geometry(xb, th, edges, r, off):
    """Surface points of a polar shape r(theta) from xb (used by the sphere check)."""
    X = [xb+r[i]*math.cos(th[i]) for i in range(len(th))]; P = [r[i]*math.sin(th[i]) for i in range(len(th))]
    pts, rings, arc, nrm = _surface(X, P, off)
    return pts, rings, arc


def _surface(X, P, off):
    """A cavity surface through markers (X, P) ordered from the forward to the aft pole: segment edges (the poles on the axis below the
    end markers, midpoints between markers), arc length and outward unit normal of each marker's segment, and its sheet ring placed
    off x arc inside along the normal (kept off the axis)."""
    n = len(X)
    ep = [(X[0], 0.0)]+[((X[i]+X[i+1])/2, (P[i]+P[i+1])/2) for i in range(n-1)]+[(X[-1], 0.0)]
    pts = list(zip(X, P)); arc = []; nrm = []; rings = []
    for i in range(n):
        tx = ep[i+1][0]-ep[i][0]; tr = ep[i+1][1]-ep[i][1]; a = math.hypot(tx, tr) or 1e-9
        nx, nr = tr/a, -tx/a; arc.append(a); nrm.append((nx, nr))
        rings.append((X[i]-off*a*nx, max(P[i]-off*a*nr, 0.2*P[i])))
    return pts, rings, arc, nrm


def sphere_check(n=48, a=1.0, B0=1.0):
    """Validation: a perfectly diamagnetic sphere of radius a in a uniform field B0 (a Helmholtz pair 300 m across) carries the sheet field
    B_t = 1.5 B0 sin(theta). Returns the worst relative error of the surface field against it between 20 and 160 degrees, and B_n / B_t
    just outside (1.02 a)."""
    R = 300.0; I = B0*R/(MU0*0.8**1.5); cs = [dict(x=R/2, r=R, a=1.0), dict(x=-R/2, r=R, a=1.0)]
    edges = [math.pi*k/n for k in range(n+1)]; th = [(edges[k]+edges[k+1])/2 for k in range(n)]
    pts, rings, arc = _geometry(0.0, th, edges, [a]*n, config_default_offset())
    J, _ = sheet(cs, [I, I], pts, rings, flux=False); Bs = surface_field(cs, [I, I], rings, J, pts)
    err = 0.0; rows = []
    for i in range(n):
        Bt = Bs[i]; ex = 1.5*B0*math.sin(th[i]); rows.append((math.degrees(th[i]), Bt, ex))
        if 20 <= math.degrees(th[i]) <= 160:
            err = max(err, abs(abs(Bt)/ex-1))
    # B_n just outside the surface (1.02 a): rings plus coils
    bn = 0.0
    for i in range(0, n, max(1, n//12)):
        x, r = 1.02*a*math.cos(th[i]), 1.02*a*math.sin(th[i]); br = bx = 0.0
        for (xi, ri), j in zip(rings, J):
            p, q = vs.loop_field(ri, j, r, x-xi); br += p; bx += q
        for c in cs:
            p, q = vs.loop_field(c['r'], I, r, x-c['x']); br += p; bx += q
        nx, nr = math.cos(th[i]), math.sin(th[i]); Bn = bx*nx+br*nr; Bt = -bx*nr+br*nx
        if 20 <= math.degrees(th[i]) <= 160:
            bn = max(bn, abs(Bn)/max(abs(Bt), 1e-12))
    return dict(n=n, max_error=err, bn_over_bt=bn, rows=rows)


def config_default_offset():
    return 1.0


def cavity(s, cid, n=None, ds=None, downstream=None, E=None, burn_shift=0.0, flux=True, keep_shape=True):
    """D21-B. The pulse as a perfectly diamagnetic sharp-boundary cavity from the burn point. n Lagrangian surface markers (launched at
    polar angles from +x) carry the pulse's energy and mass isotropically; each takes the normal magnetic pressure force -p dA n of its
    surface segment (p = B^2 / 2 mu0 just outside the sheet, dA = 2 pi rho x arc). Every step solves the sheet currents and the six coils'
    flux conservation together. A marker stagnates when its velocity away from the burn point reaches zero (its residual, tangential
    motion is kept: it is the start of the flow along the surface), hits hardware (its kinetic energy and momentum go to that part), or
    escapes aft past the escape plane or radially. Ledgers: energy (kinetic + deposited + escaped + residual + field change = pulse) and
    momentum: the force of the field on the sheet against the force on the coils every step (Newton's third law; momentum_error is its
    90th-percentile mismatch over the steps, momentum_error_max the worst), and the impulse the frozen, stagnated plasma takes from the field while the rest finishes (held_impulse: an artefact
    of the first-pass freeze, returned in reality, which is why the thrust comes from the closures, not from the coil impulse). Coil
    response (current change, force, field energy) is recorded until plasma first touches a coil cryostat (coil_contact): after that
    the sheet wraps a winding and the response is outside the model."""
    c = config(s); mc = vm.config(s); st = ve.stations(s); t_cpu = time.process_time()
    n = n or c['cavity_markers']; ds = ds or c['cavity_step_m']
    cand = _cand(s, cid); cs = cand['cs']; I0 = list(cand['I']); pz = vm.plasma(s, cand['yield_share'])
    E = E or pz['energy_J']['design']; v0 = pz['exhaust_m_s']; Mtot = 2*E/v0**2
    xb = st['burn']+burn_shift; hw = vm.hardware(s, cs)
    xesc = st['exit']-(mc['exit_margin_m'] if downstream is None else downstream)
    edges = [math.pi*k/n for k in range(n+1)]; th = [(edges[k]+edges[k+1])/2 for k in range(n)]
    dOm = [2*math.pi*(math.cos(edges[k])-math.cos(edges[k+1])) for k in range(n)]
    m = [Mtot*w/(4*math.pi) for w in dOm]; r0 = c['cavity_start_m']
    X = [xb+r0*math.cos(a) for a in th]; P = [r0*math.sin(a) for a in th]
    VX = [v0*math.cos(a) for a in th]; VR = [v0*math.sin(a) for a in th]
    state = ['FREE']*n; where = [None]*n; Ein = [0.0]*n; Pax = [0.0]*n; pstop = [0.0]*n
    L = vm.inductance(cs); Phi0 = [sum(L[k][l]*I0[l] for l in range(len(cs))) for k in range(len(cs))]
    W0 = 0.5*sum(i*p for i, p in zip(I0, Phi0)); F0 = vm.axial_forces(cs, I0)
    t = 0.0; steps = 0; imp = [0.0]*len(cs); imp_pl = 0.0; dImax = [0.0]*len(cs); Fmax = [abs(f) for f in F0]; Wpeak = W0; pmax = 0.0
    t_peak = 0.0; n3 = 0.0; dI = [0.0]*len(cs); names = {q['name'] for q in cs}; contact = None; e_contact = None; n3_log = []
    rho_floor = 0.05; unstable = None
    while any(q == 'FREE' for q in state) and steps < 20000:
        pts, rings, arc, nrm = _surface(X, P, c['ring_offset'])
        # markers squeezed onto the axis (the pole flow pinched into a jet) carry no flux and would make the solve singular: they
        # leave the sheet constraint and coast in the axis field
        act = [i for i in range(n) if P[i] > rho_floor]
        pa = [pts[i] for i in act]; ra = [rings[i] for i in act]
        if contact is None:
            Ja, dI = sheet(cs, I0, pa, ra, L, flux)
        else:                                   # after contact: coils held at their last current (the response is outside the model)
            Ja, _ = sheet(cs, [a+b for a, b in zip(I0, dI)], pa, ra, L, False)
        I1 = [a+b for a, b in zip(I0, dI)]
        if max(abs(d) for d in dI) > 3*max(abs(i) for i in I0):
            unstable = unstable or dict(step=steps, t_s=t)
        rings, J = ra, Ja
        p = [b*b/(2*MU0) for b in surface_field(cs, I1, rings, J, pts)]
        vf = max(math.hypot(VX[i], VR[i]) for i in range(n) if state[i] == 'FREE')
        dt = ds/max(vf, 1e-3*v0)
        Fc = 0.0; live = contact is None
        for k, ck in enumerate(cs):
            br = 0.0
            for l, cl in enumerate(cs):
                if l != k:
                    br += vs.loop_field(cl['r'], I1[l], ck['r'], ck['x']-cl['x'])[0]
            for (xi, ri), j in zip(rings, J):
                br += vs.loop_field(ri, j, ck['r'], ck['x']-xi)[0]
            F = -I1[k]*2*math.pi*ck['r']*br; imp[k] += (F-F0[k])*dt; Fc += F-F0[k]
            if live:
                Fmax[k] = max(Fmax[k], abs(F))
        Fp = sum(-p[i]*2*math.pi*P[i]*arc[i]*nrm[i][0] for i in range(n))
        if live:
            e3 = abs(Fp+Fc)/max(abs(Fp), abs(Fc), 1.0); n3_log.append(e3)
            for k in range(len(cs)):
                if abs(dI[k]) > abs(dImax[k]):
                    dImax[k] = dI[k]
            W = 0.5*sum(i*ph for i, ph in zip(I1, Phi0))
            if W > Wpeak:
                Wpeak = W; t_peak = t
        imp_pl += Fp*dt
        for i in range(n):
            if state[i] != 'FREE':
                continue
            pmax = max(pmax, p[i]); f = p[i]*2*math.pi*P[i]*arc[i]/m[i]
            VX[i] -= f*nrm[i][0]*dt; VR[i] -= f*nrm[i][1]*dt
            dx, dr = X[i]-xb, P[i]; rr = math.hypot(dx, dr)
            if (VX[i]*dx+VR[i]*dr)/rr <= 0.0:
                state[i] = 'STOP'; where[i] = 'STOPPED'; pstop[i] = p[i]
                Ein[i] = 0.5*m[i]*(VX[i]**2+VR[i]**2); Pax[i] = m[i]*VX[i]; continue
            X[i] += VX[i]*dt; P[i] = abs(P[i]+VR[i]*dt)
            o = vm.obstacle(hw, X[i], P[i])
            if o or X[i] < xesc or P[i] > mc['radial_limit_m'] or X[i] > st['front']:
                state[i] = 'HIT' if o else 'ESC'; where[i] = o or ('AFT' if X[i] < xesc else 'OUT')
                Ein[i] = 0.5*m[i]*(VX[i]**2+VR[i]**2); Pax[i] = m[i]*VX[i]
                if o in names and contact is None:
                    contact = dict(coil=o, t_s=t)
                    e_contact = (sum(Ein)+sum(0.5*m[k]*(VX[k]**2+VR[k]**2) for k in range(n) if state[k] == 'FREE')+
                                 0.5*sum(a*ph for a, ph in zip(I1, Phi0))-W0-E)/E
        t += dt; steps += 1
    W1 = 0.5*sum((a+b)*ph for a, b, ph in zip(I0, dI, Phi0))
    part = {}; partE = {}; resid = {'forward': 0.0, 'aft': 0.0}
    for i in range(n):
        part[where[i]] = part.get(where[i], 0.0)+m[i]/Mtot          # mass (solid-angle) shares: the field returns what it stores
        if where[i] == 'STOPPED':
            resid['forward' if Pax[i] > 0 else 'aft'] += m[i]
        else:
            partE[where[i]] = partE.get(where[i], 0.0)+Ein[i]/E       # energy on arrival (the rest was in the field at that moment)
    e_err = (sum(Ein)+(W1-W0)-E)/E if contact is None else e_contact
    n3s = sorted(n3_log[5:]) or [0.0]; n3 = n3s[int(0.9*(len(n3s)-1))]; n3max = n3s[-1]
    p_hard = sum(Pax[i] for i in range(n) if state[i] == 'HIT'); p_esc = sum(Pax[i] for i in range(n) if state[i] == 'ESC')
    p_res = sum(Pax[i] for i in range(n) if state[i] == 'STOP')
    stopped = [i for i in range(n) if where[i] == 'STOPPED']
    istar = max(stopped, key=lambda i: pstop[i]) if stopped else n//2
    out = dict(id=label(cid), n=n, ds_m=ds, steps=steps, cpu_s=time.process_time()-t_cpu, t_end_s=t, energy_J=E, mass_kg=Mtot, speed_m_s=v0,
               flux_conserving=flux, burn_shift_m=burn_shift, escape_plane_x=xesc,
               first_pass=dict(sorted(part.items())), first_pass_energy=dict(sorted(partE.items())), energy_error=e_err, momentum_error=n3, momentum_error_max=n3max, coil_contact=contact, unstable=unstable,
               coil_impulse_Ns=imp, held_impulse_Ns=imp_pl-(p_hard+p_esc+p_res), hardware_impulse_Ns=p_hard, escaped_impulse_Ns=p_esc, residual_impulse_Ns=p_res,
               residual_mass_share={k: v_/Mtot for k, v_ in resid.items()},
               W0_J=W0, W_end_J=W1, W_peak_J=Wpeak, t_peak_s=t_peak, dI_peak_At=dImax, dI_rel=[d/i if i else 0.0 for d, i in zip(dImax, I0)],
               F_static_N=F0, F_peak_N=Fmax, peak_pressure_Pa=pmax, theta_star_deg=math.degrees(th[istar]),
               mean_stop_m=(sum(math.hypot(X[i]-xb, P[i])*dOm[i] for i in stopped)/sum(dOm[i] for i in stopped)) if stopped else None,
               forward_leak_deg=max([math.degrees(th[i]) for i in range(n) if where[i] == 'SHIELD'], default=0.0),
               markers=[dict(deg=math.degrees(th[i]), x=X[i], rho=P[i], r=math.hypot(X[i]-xb, P[i]), outcome=where[i], p=pstop[i], dOm=dOm[i],
                             vx_res=(Pax[i]/m[i] if where[i] == 'STOPPED' else None)) for i in range(n)] if keep_shape else None)
    out['closures'] = closures(out)
    return out


def closures(cv):
    """What happens to the stopped energy after stagnation (the field gives it back): three closures that bracket the outcome.
    aft: the nozzle sends all of it aft (optimistic); isotropic: it re-expands like the first pass (mixing); channelled: it streams along
    the surface the way it was already moving at stagnation (the sign of its residual axial velocity), forward to the forward pole and
    the shield or aft to the exit: the pessimistic case for the shield."""
    fp = cv['first_pass']; st = fp.get('STOPPED', 0.0); rest = {k: v for k, v in fp.items() if k != 'STOPPED'}
    out = {}
    a = dict(rest); a['AFT'] = a.get('AFT', 0.0)+st; out['aft'] = a
    out['isotropic'] = {k: v/(1-st) for k, v in rest.items()} if st < 1 else dict(rest)
    fwd_out = 'SHIELD'; aft_out = 'AFT'
    ef = cv['residual_mass_share']['forward']; ea = st-ef
    ch = dict(rest); ch[fwd_out] = ch.get(fwd_out, 0.0)+ef; ch[aft_out] = ch.get(aft_out, 0.0)+ea; out['channelled'] = ch
    return out


def ledger(cv, axial=(1.0, None)):
    """Energy and momentum accounting of one cavity run per closure: shares of the pulse energy on hardware, aft, radially out; the impulse
    per pulse when the aft share leaves with the nozzle's axial fraction (1.0 = perfectly collimated)."""
    out = {}
    for k, part in cv['closures'].items():
        aft = part.get('AFT', 0.0); hard = sum(v for q, v in part.items() if q not in ('AFT', 'OUT'))
        out[k] = dict(aft=aft, hardware=hard, out=part.get('OUT', 0.0), shield=part.get('SHIELD', 0.0),
                      impulse_Ns=aft*cv['mass_kg']*cv['speed_m_s'])            # same specific energy: aft mass share = aft energy share
    return out


# ---------- 7. detachment ----------------------------------------------------------------------------------------------------------

def field_energy_beyond(cs, I, x0, xlen=400.0, rmax=120.0):
    """Vacuum field energy aft of the plane x0 (J): what a plume that drags the field lines away would have to pay at most (stretched,
    flux-conserving field), on a grid that coarsens with distance."""
    W = 0.0; x = x0; hx = 0.25
    while x > x0-xlen:
        r = 0.0; hr = 0.25
        while r < rmax:
            rm = r+hr/2; b = vm.field(cs, I, x-hx/2, rm); W += (b[0]**2+b[1]**2)/(2*MU0)*2*math.pi*rm*hr*hx
            r += hr; hr = min(0.25+0.08*r, 8.0)
        x -= hx; hx = min(0.25+0.08*(x0-x), 8.0)
    return W


def detachment(s, cid, cavities):
    """Detachment evidence (never a proof): the aft share against the escape-plane distance (a share that keeps falling with a longer
    domain is plasma the draped field still turns back), the field energy left behind at the end (stretched flux, not returned), the
    interaction parameter downstream (aft plume energy over the vacuum field energy aft of each plane: much more than 1 means the plume
    can carry the field lines away at a small energy cost, at most 1 / interaction), ion demagnetisation (1.3 screen) and electron
    magnetisation."""
    cand = _cand(s, cid); cs, I = cand['cs'], cand['I']; st = ve.stations(s); pz = vm.plasma(s, cand['yield_share'])
    ext = [dict(downstream_m=d, aft_first_pass=cv['first_pass'].get('AFT', 0.0), stopped=cv['first_pass'].get('STOPPED', 0.0),
                field_left_J=cv['W_end_J']-cv['W0_J']) for d, cv in cavities]
    rows = []; E = pz['energy_J']['design']; base = cavities[0][1]['closures']
    for dx in (0.0, 10.0, 30.0, 60.0):
        Wb = field_energy_beyond(cs, I, st['exit']-dx)
        rows.append(dict(downstream_m=dx, field_energy_J=Wb, interaction={k: (v.get('AFT', 0.0)*E/Wb if Wb else math.inf) for k, v in base.items()},
                         B_axis_T=abs(vm.field(cs, I, st['exit']-dx, 0.0)[1])))
    d13 = vm.detachment(s, cs, I, cand['yield_share'])
    conv = len(ext) > 1 and abs(ext[-1]['aft_first_pass']-ext[-2]['aft_first_pass']) < 0.02
    return dict(domain_extension=ext, converged=conv, plume=rows, ion_demagnetisation_1_3=d13['species'],
                electron_larmor_exit_m=d13['electron_larmor_exit_m'], verdict='DETACHMENT_OPEN',
                reading='Inside the cavity the field is zero, so the bulk plasma is not tied to field lines; the aft pole of the cavity leaves '
                        'through the exit with beta far above 1 and the aft share converges with the domain length. The draped field lines '
                        'still have to reconnect or stretch away behind it, and electrons stay magnetised in the boundary layer (r_Le/L about '
                        '1e-5): neither is modelled, so detachment is plausible in the ideal sharp-boundary limit and not demonstrated.')


# ---------- 9. thermal and radiation ------------------------------------------------------------------------------------------------

def sky_fractions(s, cid, step_deg=1):
    """Share of the isotropic sky (from the burn point) covered by each obstacle: what X-rays and neutrons (no field acts on them) hit."""
    cand = _cand(s, cid); rows = vm.hardware_rays(s, cand['cs'], [k+0.5*step_deg for k in range(0, 180, step_deg)]); out = {}
    for deg, d, o in rows:
        w = 0.5*(math.cos(math.radians(deg-0.5*step_deg))-math.cos(math.radians(deg+0.5*step_deg)))
        k = o or 'SPACE'; out[k] = out.get(k, 0.0)+w
    return out


def eddy(s, cid, cv):
    """Cryostat-wall heating from the pulse's field swing (9.3). The wall's diffusion time mu0 d^2 / resistivity (about 1 ms for 20 mm of
    316LN at 20 K) is far longer than the pulse (microseconds) and than the pulse period (0.18 ms): the wall screens the whole swing, so
    each coil's current change dI flows in its wall, not its winding, for the duration of the pulse and is released with it. Heat per
    pulse = dI^2 R t_on with the wall's toroidal resistance R = resistivity r / (b h) carried in a layer h between the skin depth at the
    pulse frequency (upper bound) and the full wall (lower bound), t_on = twice the first-pass time (compression and release); never
    more than L_leak dI^2 (the whole hand-over energy, L_leak = mu0 r ln(b/a)). Refrigeration at 20 K multiplies it by 1 / COP."""
    c = config(s); mc = vm.config(s); cand = _cand(s, cid); cs = cand['cs']; pz = vm.plasma(s, cand['yield_share'])
    rho_e = mc['cryostat_wall_resistivity_ohm_m']; d = mc['cryostat_wall_m']
    tau = MU0*d*d/rho_e; t_on = 2*cv['t_end_s']; om = 2*math.pi/max(2*cv['t_peak_s'], 1e-9)
    skin = math.sqrt(2*rho_e/(MU0*om)); rows = []; lo = hi = 0.0
    for q, dI in zip(cs, cv['dI_peak_At']):
        Ll = MU0*q['r']*math.log(q['cryostat']/q['a']); cap = Ll*dI*dI
        e_lo = min(dI*dI*rho_e*q['r']/(q['cryostat']*d)*t_on, cap); e_hi = min(dI*dI*rho_e*q['r']/(q['cryostat']*min(d, skin))*t_on, cap)
        mw = 2*math.pi*q['r']*2*math.pi*q['cryostat']*d*c['wall_density_kg_m3']
        rows.append(dict(name=q['name'], dI_At=dI, L_leak_H=Ll, energy_J=[e_lo, e_hi], wall_mass_kg=mw,
                         dT_per_pulse_K=[e_lo/(mw*c['wall_cp_20K_J_kgK']), e_hi/(mw*c['wall_cp_20K_J_kgK'])]))
        lo += e_lo; hi += e_hi
    f = pz['pulse_Hz']
    return dict(wall_diffusion_s=tau, pulse_on_s=t_on, period_s=1/f, skin_depth_m=skin, screened=tau > 1/f, coils=rows, energy_J=[lo, hi],
                pulse_fraction=[lo/cv['energy_J'], hi/cv['energy_J']], power_W=[lo*f, hi*f],
                refrigeration_W=[lo*f/c['cryo_cop_20K'], hi*f/c['cryo_cop_20K']],
                note='The wall, not the winding, carries the pulse: the windings see an almost steady field (good for AC loss and quench), and '
                     'the wall takes the transient force and the heat. Bound from the coupled coil response; the real eddy pattern, the 80 K '
                     'screen and the wall temperature (which sets its resistivity) are not modelled.')


def thermal(s, cid, cv, aud=None):
    """Energy that is not exhaust (9.1, 9.2): charged deposition per obstacle per pulse and as average power (cavity closures and the
    energy-weighted particle screen), the shield-face heat flux against the tungsten PFC class, neutral radiation by sky fraction, and the
    ship's 1800 K radiator rejection for scale."""
    c = config(s); cand = _cand(s, cid); pz = vm.plasma(s, cand['yield_share']); g = ve.config(s)['geometry']
    Y = pz['yield_J']; f = pz['pulse_Hz']; Ech = pz['energy_J']['design']; Enc = Y-Ech
    A_face = math.pi*g['shield_aft_radius_m']**2
    led = ledger(cv); dep = {}
    for k, part in cv['closures'].items():
        dep[k] = {q: dict(J=v*Ech, W=v*Ech*f) for q, v in part.items() if q not in ('AFT', 'OUT')}
    shield_W = {k: part.get('SHIELD', 0.0)*Ech*f for k, part in cv['closures'].items()}
    sky = sky_fractions(s, cid); hw_sky = sum(v for k, v in sky.items() if k != 'SPACE')
    neu = [x*Y for x in c['neutron_share_of_fusion']]
    rad = s['radiators']; ship = SIGMA_SB*rad['emissivity']['value']*rad['temperature']['value']**4*rad['effective_area']['value']
    xr = Enc-neu[1]
    out = dict(pulse_J=Y, charged_J=Ech, noncharged_J=Enc, pulse_Hz=f, deposition=dep, ledger=led,
               shield_face_m2=A_face, shield_heat_flux_W_m2={k: v/A_face for k, v in shield_W.items()},
               pfc_heat_flux_W_m2=c['pfc_heat_flux_W_m2'], sky=sky, hardware_sky=hw_sky,
               xray_absorbed_W=xr*f*hw_sky, neutron_W=[x*f for x in neu], neutron_absorbed_W=[x*f*hw_sky for x in neu],
               xray_shield_flux_W_m2=xr*f*sky.get('SHIELD', 0.0)/A_face, ship_radiator_W=ship)
    if aud:
        w = aud['candidates'][label(cid)]['weights'][str(c['fast_product_share'][1])]
        out['particle_energy_weighted'] = dict(shield=w['energy'], hardware=w['hardware_energy'], shield_W=w['energy']*Ech*f)
    return out


def treg(s, th):
    """T-REG (10): what heat recovery into a working fluid can do. T0 radiators for the absorbed heat; T1 hydrogen through a lithium heat
    exchanger and out of a nozzle (heat leaves with propellant); T2 Brayton conversion of the lithium heat. The propellant flow the
    engine already has is the jet mass flow at the research exhaust speed."""
    c = config(s); rad = s['radiators']; T = rad['temperature']['value']; eps = rad['emissivity']['value']
    pz = vm.plasma(s); mdot = pz['mass_kg']*pz['pulse_Hz']; vex = pz['exhaust_m_s']
    Qc = th['deposition']['isotropic']; Q = sum(v['W'] for v in Qc.values())+th['xray_absorbed_W']+th['neutron_absorbed_W'][1]
    q_area = SIGMA_SB*eps*T**4
    sc = s['vertex_engine']['structure']; mdot_li = Q/(sc['lithium_cp_J_kgK']*sc['lithium_delta_T_K'])
    pump = mdot_li*sc['lithium_design_pressure_Pa']/sc['lithium_density_kg_m3']
    h = c['treg_enthalpy_J_kg']; vT = math.sqrt(2*c['treg_nozzle_efficiency']*h); mH = Q/h
    eta = c['treg_brayton_efficiency']; Tc = 0.5*T
    return dict(absorbed_W=Q, T0=dict(radiator_m2=Q/q_area, ship_radiator_m2=rad['effective_area']['value'], ratio=Q/q_area/rad['effective_area']['value'],
                                      lithium_flow_kg_s=mdot_li, pump_W=pump),
                T1=dict(hydrogen_kg_s=mH, exhaust_m_s=vT, thrust_N=mH*vT, engine_propellant_kg_s=mdot, flow_ratio=mH/mdot,
                        exhaust_ratio=vT/vex, recovered_at_matched_flow_W=mdot*h,
                        verdict='The heat leaves with the hydrogen, but at a thermal exhaust speed about 1/3000 of the fusion exhaust: carrying the '
                                'absorbed heat needs a hydrogen flow millions of times the engine propellant flow, which the mission mass cannot pay. '
                                'At a hydrogen flow equal to the engine flow it recovers kilowatts. Radiator demand is unchanged.'),
                T2=dict(electric_W=eta*Q, rejected_W=(1-eta)*Q, cold_side_K=Tc, radiator_m2=(1-eta)*Q/(SIGMA_SB*eps*Tc**4),
                        verdict='Conversion makes driver power but rejects the rest at a lower temperature: more radiator area, not less.'),
                verdict='WORSENS_OR_UNCHANGED', blocked_unchanged=['1800 K lithium material limit', 'local pulse heating', 'X-ray and neutron load',
                                                                 'cryostat thermal protection', 'magnet quench', 'target-injection survival'])


# ---------- 8. alternative architectures ------------------------------------------------------------------------------------------

def free_gaps(s, cid, step_deg=1):
    """Polar-angle intervals (deg from +x) whose rays from the burn point reach no hardware, and the obstacle intervals."""
    cand = _cand(s, cid); rows = vm.hardware_rays(s, cand['cs'], [k+0.5*step_deg for k in range(0, 180, step_deg)])
    out = []; cur = None
    for deg, d, o in rows:
        k = o or 'FREE'
        if cur and cur[0] == k:
            cur[2] = deg+0.5*step_deg
        else:
            cur = [k, deg-0.5*step_deg, deg+0.5*step_deg]; out.append(cur)
    return [dict(what=a, from_deg=b, to_deg=c_) for a, b, c_ in out]


def alternatives(s, cv_m2, runs):
    """A1-A4 bounded screens. runs: extra cavity runs {name: cavity} (burn shift, quarter yield)."""
    c = config(s); cand = _cand(s, 'M2'); cs, I = cand['cs'], cand['I']; st = ve.stations(s); pz = vm.plasma(s)
    led = ledger(cv_m2); sh = {k: v['shield'] for k, v in led.items()}
    B = abs(vm.field(cs, I, st['burn'], 0.0)[1]); Rsh = abs(st['shield_aft']-st['burn'])
    WT = B*B/(2*MU0)*4/3*math.pi*Rsh**3
    gaps = free_gaps(s, 'M2'); psi = cv_m2['forward_leak_deg']
    side = [g for g in gaps if g['what'] == 'FREE' and g['to_deg'] < 150 and g['to_deg']-g['from_deg'] >= 2*max(psi, 1.0)]
    A1 = dict(id='A1', name='Non-axisymmetric magnetic nozzle', evidence='ANALYTICAL_SCREEN',
              topology='The tangential field on a closed diamagnetic cavity is the surface gradient of a potential: it has at least two zeros '
                       '(a maximum and a minimum, hairy-ball theorem). Every closed cavity leaks at two or more points; an axisymmetric field '
                       'must put them on the axis, one facing the shield. Sector coils can move the zeros, not remove them.',
              forward_leak_half_angle_deg=psi, gaps=gaps, side_gaps_wide_enough=side,
              transverse_field_T=B, transverse_energy_J=WT, candidate_energy_J=vm.stored_energy(cs, I),
              result=('A free side gap is wide enough for a steered leak cone' if side else
                      'No free side gap: every ray between the shield cone and the exit meets a cryostat or the cage, so a steered leak lands on '
                      'hardware (a dedicated dump) instead of the shield'),
              cost='A transverse field comparable to the burn-point field over the shield stand-off stores about '
                   f'{WT/1e9:.1f} GJ more and puts net torques and unbalanced pulse loads on sector coils; thrust stays symmetric only for paired leaks.',
              status='PROMISING_NOT_DEMONSTRATED', needs='a 3D cavity or hybrid model (gate D21-D)')
    A2 = dict(id='A2', name='Revised pulse source', evidence='COUPLED_CAVITY_MODEL',
              runs={k: dict(burn_shift_m=v['burn_shift_m'], energy_J=v['energy_J'], shield={q: l['shield'] for q, l in ledger(v).items()},
                            aft={q: l['aft'] for q, l in ledger(v).items()}) for k, v in runs.items()},
              directivity_needed={k: (c_lim/v if v > 0 else None) for k, v in sh.items() for c_lim in [vm.config(s)['particle_hit_limit']]},
              plate=[dict(mass_ratio=k, exhaust_m_s=pz['exhaust_m_s']/math.sqrt(k), mass_ratio_mission=math.exp(4*0.016*CLIGHT/(pz['exhaust_m_s']/math.sqrt(k))))
                     for k in (1.0, 10.0, 100.0)],
              reading='Moving the burn point aft or shrinking the pulse changes the shield share only through the ratio of stopping to hardware '
                      'distance; the forward pole stays. Only a source that sends less energy into the forward pole (an anisotropic target) cuts '
                      'it by the factor shown. Loading the pulse with inert propellant to direct it (the Orion pulse-unit precedent) lowers the '
                      'exhaust speed by sqrt(mass ratio); four 0.016 c burns then cost the mission mass ratio shown.')
    v_need = 4*0.016*CLIGHT
    A3 = dict(id='A3', name='Other fusion-propulsion families', evidence='LITERATURE_SCREEN', delta_v_m_s=v_need,
              rows=[dict(id='ICF_MICROPULSE', name='Pulsed inertial D-3He micro-pulses in a magnetic nozzle (the Vertex)', exhaust_m_s=pz['exhaust_m_s'],
                         maturity='target gain and kHz delivery undemonstrated (WL-001, WL-004)', nozzle='open cavity, two poles, pulse loads',
                         mission='the only family here with exhaust of order 1e7 m/s'),
                    dict(id='MIF_LINER', name='Magneto-inertial: liner-compressed FRC (Fusion Driven Rocket, NASA NIAC 2012-2015)', exhaust_m_s=3.0e4,
                         maturity='subscale liner tests; gain not shown', nozzle='liner plasma as propellant and shield; heavy, slow exhaust',
                         mission=f'mass ratio exp({v_need/3.0e4:.0f}): excluded'),
                    dict(id='FRC_STEADY', name='Steady FRC with scrape-off-layer propellant (Direct Fusion Drive, PFRC)', exhaust_m_s=2.0e5,
                         maturity='laboratory FRC, no fusion gain; MW-class units', nozzle='steady magnetic nozzle, no pulse loads, cool exhaust',
                         mission=f'mass ratio exp({v_need/2.0e5:.0f}) and 6 orders below the power: excluded'),
                    dict(id='DIRECTED_PULSE', name='Directed pulse unit: target with a propellant/channel layer that turns X-rays and debris into an aft jet',
                         exhaust_m_s=pz['exhaust_m_s']/math.sqrt(10.0), maturity='Orion pulse-unit physics (fission scale); never at micro-pulse scale',
                         nozzle='forward pole starved; X-ray share becomes thrust', mission='exhaust falls with the added mass: see A2 plate rows')],
              reading='The mission needs an exhaust of order 1e7 m/s. Families that thermalise propellant (liner, scrape-off layer) are two to three '
                      'orders slower and fail the mass ratio; the source change worth studying keeps the fusion products as exhaust and makes the '
                      'pulse anisotropic without heavy loading.')
    flux = {k: v for k, v in sh.items()}
    A4 = dict(id='A4', name='Bounded speculative capability (NON_CANON, not adopted)', evidence='SPECULATIVE_REQUIREMENT',
              proposal='VTX-S6 forward-pole dump: a renewable lithium-film first wall on the shield face that takes the forward-pole plasma and '
                       'the X-ray load at the heat flux below, every pulse, for the mission. Extends VTX-S3; no field, momentum or energy is created: '
                       'the energy it takes becomes heat for the lithium loop and radiators.',
              shield_share=flux, magnitude='see thermal shield_heat_flux and xray_shield_flux against the 10-20 MW/m2 tungsten class',
              limits=['heat still has to be radiated at 1800 K (ship radiators are about 14 GW)', 'momentum of the dumped plasma pushes the ship forward '
                      '(no thrust loss beyond the missing exhaust)', 'magnets, structure and detachment unchanged'], status='NON_CANON')
    return dict(A1=A1, A2=A2, A3=A3, A4=A4)


# ---------- 11. gates and the decision ----------------------------------------------------------------------------------------------

def gates(s, R):
    c = config(s); mc = vm.config(s); M2 = R['coupled']['M2']; m2l = ledger(M2)
    v = R['validation']; conv = R['convergence']['M2']
    shield_lo = min(x['shield'] for x in m2l.values()); shield_hi = max(x['shield'] for x in m2l.values())
    hard_hi = max(x['hardware'] for x in m2l.values())
    g = []
    ok0 = v['sphere']['max_error'] < 0.05 and abs(M2['energy_error']) < 0.02 and conv['spread'] < 0.05 and M2.get('unstable') is None
    g.append(dict(id='D21-0', name='Model readiness', status='PASS_WITH_LIMITS' if ok0 else 'FAIL',
                  value=f"sphere error {v['sphere']['max_error']:.3f}, energy error {M2['energy_error']:+.4f}, momentum error {M2['momentum_error']:+.3f}, "
                        f"shield share spread over n and step {conv['spread']:.3f}",
                  note='sharp-boundary Lagrangian thin-shell model (markers pinched onto the axis leave the sheet); flutes, mixing and kinetic boundary physics are outside it'))
    g.append(dict(id='D21-1', name='Capture and protection', status='FAIL' if shield_lo > mc['particle_hit_limit'] else 'OPEN',
                  value=f'M2 shield energy share {shield_lo:.3f}-{shield_hi:.3f} across closures (limit {mc["particle_hit_limit"]}); hardware up to {hard_hi:.2f}',
                  note='the forward pole of the cavity is topological; plasma coupling moves the loss, it does not close it'))
    g.append(dict(id='D21-2', name='Detachment', status='OPEN', value=R['detachment']['M2']['reading'][:160]+'...', note='DETACHMENT_OPEN'))
    eg = R['thermal']['M2']['eddy']
    g.append(dict(id='D21-3', name='Magnetic hardware', status='FAIL',
                  value=f"peak coil force {max(M2['F_peak_N'])/1e6:.0f} MN in the pulse (static {max(abs(x) for x in M2['F_static_N'])/1e6:.0f} MN); "
                        f"cryostat eddy heat {eg['power_W'][0]/1e9:.1f}-{eg['power_W'][1]/1e9:.0f} GW at 20 K per engine",
                  note='REBCO critical current at the transient field OPEN (OD-024); the 20 K heat alone exceeds any cryoplant'))
    imp = [x['impulse_Ns'] for x in m2l.values()]
    need = vm.plasma(s)['mass_kg']*vm.plasma(s)['exhaust_m_s']
    g.append(dict(id='D21-4', name='Energy and momentum closure', status='PARTIAL',
                  value=f'energy closes to {abs(M2["energy_error"]):.1%}; impulse per pulse {min(imp):.0f}-{max(imp):.0f} N s against {need:.0f} N s assumed',
                  note='THRUST_UNPROVEN: the sector model leaves a momentum residual and no detachment'))
    g.append(dict(id='D21-5', name='Architecture decision', status=c['outcome'], value='No feasible architecture demonstrated',
                  note='research direction: keep fusion-product exhaust; steer the poles (A1) and make the source anisotropic without heavy loading (A2)'))
    return g


# ---------- the report and the evidence --------------------------------------------------------------------------------------------

def input_hash(s):
    import hashlib, json
    blob = json.dumps([s['vertex_engine'], s['vertex_research'], s['radiators']['temperature'], s['radiators']['emissivity'],
                       s['radiators']['effective_area']], sort_keys=True, default=str)
    src = b''.join((Path(__file__).resolve().parent/f).read_bytes() for f in ('vertex_plasma.py', 'vertex_magnet.py', 'vertex_structure.py'))
    return hashlib.sha256(blob.encode()+src).hexdigest()[:16]


def baseline_1_3(s):
    """The 1.3 reference rows reproduced from vertex_magnet (capture, force, energy) and its evidence file (particles, structure)."""
    import json
    ev = json.loads((Path(__file__).resolve().parents[2]/'references'/'evidence'/'vertex_magnet.json').read_text())
    out = {}
    for cid in config(s)['candidates']:
        cand = _cand(s, cid); e = vm.evaluate(s, cand['cs'], cand['I'])
        row = next(r for r in ev['candidates'] if r['id'] == label(cid))
        pt = row['eval'].get('particles', {}); sp = pt.get('D_debris', {})
        out[label(cid)] = dict(capture_margin=e['capture']['worst'], peak_force_N=e['peak_force_N'], stored_energy_J=e['energy_J'],
                               shield_particles=sp.get('hits', {}).get('SHIELD'), axial_fraction=sp.get('axial_fraction'),
                               divergence_p90_deg=sp.get('divergence_p90_deg'),
                               evidence_capture=row['eval']['capture']['worst'], evidence_force_N=row['eval']['peak_force_N'])
    return out


def report(s, quick=False, workers=None):
    c = config(s); t0 = time.time()
    R = dict(version=c['version'], input_hash=input_hash(s), baseline_1_3=baseline_1_3(s))
    R['validation'] = dict(sphere=sphere_check(48 if not quick else 24))
    R['validation']['sphere'].pop('rows', None)
    R['audit'] = audit(s, quick=quick, workers=workers)
    R['coupled'] = {}; R['convergence'] = {}; R['regime'] = {}; R['detachment'] = {}; R['thermal'] = {}
    for cid in c['candidates']:
        k = label(cid) if cid in vm.HISTORICAL else cid
        cv = cavity(s, cid, n=24 if quick else None); R['coupled'][k] = cv
        rows = []
        ladder = [(24, c['cavity_step_m']), (48, c['cavity_step_m'])] if quick else \
            [(n, c['cavity_step_m']) for n in c['cavity_markers_convergence']]+[(c['cavity_markers'], d) for d in c['cavity_step_convergence_m'] if d != c['cavity_step_m']]
        for n, d in ladder:
            x = cv if (n == cv['n'] and d == cv['ds_m']) else cavity(s, cid, n=n, ds=d, keep_shape=False)
            rows.append(dict(n=n, ds_m=d, shield_first=x['first_pass'].get('SHIELD', 0.0), stopped=x['first_pass'].get('STOPPED', 0.0),
                             aft_first=x['first_pass'].get('AFT', 0.0),
                             hardware_first=sum(v_ for k_, v_ in x['first_pass'].items() if k_ not in ('AFT', 'OUT', 'STOPPED')), energy_error=x['energy_error'], momentum_error=x['momentum_error'], cpu_s=x['cpu_s']))
        sh = [r_['shield_first'] for r_ in rows]
        hw_ = [r_['hardware_first'] for r_ in rows if r_['ds_m'] == c['cavity_step_m']]
        R['convergence'][k] = dict(rows=rows, spread=max(sh)-min(sh), hardware_spread=max(hw_)-min(hw_),
                                   finest_change=abs(hw_[-1]-hw_[-2]) if len(hw_) > 1 else 0.0)   # the two finest marker counts
        ext = [(d, cavity(s, cid, n=24 if quick else 32, downstream=d, keep_shape=False)) for d in (c['downstream_m'][:2] if quick else c['downstream_m'])]
        R['detachment'][k] = detachment(s, cid, ext)
        R['regime'][k] = regime(s, cid, cv)
        th = thermal(s, cid, cv, R['audit']); th['eddy'] = eddy(s, cid, cv); R['thermal'][k] = th
        R['coupled'][k]['ledger'] = ledger(cv); R['coupled'][k]['kinetic'] = kinetic_margin(s, cid, cv)
        cand = _cand(s, cid); I1 = [a+b for a, b in zip(cand['I'], cv['dI_peak_At'])]
        R['coupled'][k]['conductor_peak_T'] = max(vm.conductor_field(cand['cs'], I1, n=3, m=12))
        R['coupled'][k]['conductor_static_T'] = max(vm.conductor_field(cand['cs'], cand['I'], n=3, m=12))
    R['hybrid_cost'] = hybrid_cost(s, R['regime']['M2'])
    runs = {'burn_aft_2m': cavity(s, 'M2', n=24 if quick else 32, burn_shift=-2.0, keep_shape=False),
            'quarter_pulse': cavity(s, 'M2', n=24 if quick else 32, E=0.25*vm.plasma(s)['energy_J']['design'], keep_shape=False)}
    R['alternatives'] = alternatives(s, R['coupled']['M2'], runs)
    R['treg'] = treg(s, R['thermal']['M2'])
    R['gates'] = gates(s, R)
    R['decision'] = dict(outcome=c['outcome'], verdict=c['verdict'], thrust=c['thrust'], detachment=c['detachment'], selected=vm.config(s)['selected'],
                         direction='Keep the fusion products as exhaust (the only family fast enough for the mission); study pole steering (A1) and an '
                                   'anisotropic source without heavy loading (A2) in a 3D cavity or hybrid model; solve the 20 K eddy heat and the '
                                   'X-ray sky fraction before any coil work.')
    R['wall_s'] = time.time()-t0
    return R


def kinetic_margin(s, cid, cv):
    """D21-C screen: for each stagnated marker, the gap from its stagnation point to the first hardware along its direction from the burn
    point against twice each species' Larmor radius in the local boundary field (B = sqrt(2 mu0 p)): the mass share of the pulse where a
    species of that rigidity would reach hardware through the sheet."""
    cand = _cand(s, cid); xb = ve.stations(s)['burn']+cv['burn_shift_m']; w = sum(q['dOm'] for q in cv['markers'])
    st = [q for q in cv['markers'] if q['outcome'] == 'STOPPED' and q['p'] > 0]
    degs = [round(math.degrees(math.atan2(q['rho'], q['x']-xb)), 1) for q in st]
    rays = {round(d, 1): dist for d, dist, o in vm.hardware_rays(s, cand['cs'], sorted(set(degs)))}
    out = {}
    for sp in vm.config(s)['species']:
        v = species_speed(s, sp); touch = 0.0
        for q, dg in zip(st, degs):
            d = rays.get(dg)
            if d and d-q['r'] < 2*vm.larmor(sp, math.sqrt(2*MU0*q['p']), v):
                touch += q['dOm']
        out[sp['id']] = touch/w
    return out


def evidence(s, path=EVIDENCE_PATH, quick=False):
    import json
    R = report(s, quick=quick)
    Path(path).write_text(json.dumps(R, indent=1, default=str)+'\n')
    return R


def summary(R):
    print(f"Vertex 1.4 coupled plasma  ({R['wall_s']:.0f} s)  sphere check {R['validation']['sphere']['max_error']:.3f}")
    for k, cv in R['coupled'].items():
        print(f"{k}: first pass {{{', '.join(f'{a}: {b:.3f}' for a, b in cv['first_pass'].items())}}}  dE {cv['energy_error']:+.4f}  dP {cv['momentum_error']:+.3f}")
        for q, l in cv['ledger'].items():
            print(f"   {q:<10} shield {l['shield']:.3f} hardware {l['hardware']:.3f} aft {l['aft']:.3f} impulse {l['impulse_Ns']:.0f} N s")
        print(f"   dI_rel {[round(x, 2) for x in cv['dI_rel']]}  F peak {max(cv['F_peak_N'])/1e6:.0f} MN  Bc {cv['conductor_peak_T']:.1f} T  "
              f"eddy {[round(x/1e9, 1) for x in R['thermal'][k]['eddy']['power_W']]} GW  conv spread {R['convergence'][k]['spread']:.3f}")
        a = R['audit']['candidates'][k]
        print(f"   particles shield count {a['count_weighted']:.3f} +- {a['uncertainty']:.3f}  energy {a['weights']['0.3']['energy']:.3f}  mirror {a['mirror']['forward_loss']:.3f}")
    for g in R['gates']:
        print(f"  {g['id']} {g['status']}: {g['value']}")


if __name__ == '__main__':
    from spec import load
    S = load(Path(__file__).resolve().parents[2])[0]
    if '--evidence' in sys.argv:
        summary(evidence(S, quick='--quick' in sys.argv))
    else:
        summary(report(S, quick='--quick' in sys.argv))
