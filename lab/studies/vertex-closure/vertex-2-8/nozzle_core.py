"""Vertex 2.8 magnetic-nozzle physics core (research, not canon). Uses numpy (work/ study code; the pure modules stay standard library).

Frame: one engine, metres, +z aft (away from the ship). Coils are coaxial circular loops dict(I [A], R [m], z [m], a [m] winding-pack
half-size, fin [m] radial neutron fin, name). The burn point is on the axis at z = zb.

Three independent physical models, kept apart on purpose because they answer different questions:

1. trace(): test-particle ions (relativistic Boris push in the exact loop fields), low-beta limit. It conserves nothing by assumption: the
   magnetic moment, adiabaticity, mirror reflection, loss cones, demagnetization and detachment of single ions come out of the orbits.
   It records, for every ion, where it ends (AFT, FORWARD to space, FORWARD onto the ship, RADIAL, COIL strike, TRAPPED), its final
   momentum and energy, and the impulse each coil receives from it (minus the integral of q v x B_coil dt), so the reaction force on
   the hardware is measured, not inferred from the exhaust.
2. reflect(): the high-beta pulsed regime. A pulse of plasma energy Ep expands from the burn point; it is reflected where the field
   energy density first exceeds the shell's energy density 3 Ep / (4 pi d^3) (magnetic piston / reflection chamber picture). Rays reflect
   with a normal restitution e (e = 1 specular, elastic; e < 1 loses normal energy to instabilities and heating). The impulse delivered
   to the field at each reflection is recorded. e is calibrated against the published hybrid-PIC momentum efficiency of a single-coil
   magnetic thrust chamber (Nagamine & Nakashima 1999: about 65 % at a coil angle near 50 deg).
3. detachment(): the fluid limit for the exhaust leaving the nozzle (Arefiev & Breizman 2005): the flow detaches where the field energy
   density falls below the plasma's kinetic energy density; the field-line angle of the exhaust's boundary flux surface at that point
   bounds the plume divergence.
"""
import math

import numpy as np

MU0 = 4e-7*math.pi
C = 299792458.0
E_CH = 1.602176634e-19
MEV = 1.602176634e-13
AMU = 1.66053906660e-27
M_P = 1.007276*AMU
M_A = 4.001506*AMU
M_D = 2.013553*AMU
M_H3 = 3.014932*AMU


def ellipke(m):
    """K(m), E(m) for an array m in [0, 1) by the arithmetic-geometric mean."""
    m = np.clip(m, 0.0, 1.0-1e-15)
    a = np.ones_like(m); g = np.sqrt(1.0-m); s = 0.5*m; pw = 1.0
    for _ in range(30):
        a, g, c = (a+g)/2, np.sqrt(a*g), (a-g)/2
        s = s+pw*c*c; pw *= 2
        if np.all(np.abs(c) < 1e-15):
            break
    K = np.pi/(2*a)
    return K, K*(1-s)


def loop(I, R, zc, r, z):
    """Br, Bz and A_phi of one loop on arrays r >= 0, z (Smythe closed form; the axis handled by its limit)."""
    r = np.asarray(r, float); z = np.asarray(z, float); zz = z-zc
    rr = np.maximum(r, 1e-9*R)
    a2 = R*R+rr*rr+zz*zz-2*R*rr; b2 = R*R+rr*rr+zz*zz+2*R*rr
    a2 = np.maximum(a2, 1e-12*R*R)
    m = 1.0-a2/b2
    K, E = ellipke(m)
    bb = np.sqrt(b2); C0 = MU0*I/np.pi
    Bz = C0/(2*a2*bb)*((R*R-rr*rr-zz*zz)*E+a2*K)
    Br = C0*zz/(2*a2*bb*rr)*((R*R+rr*rr+zz*zz)*E-a2*K)
    k2 = 4*R*rr/b2; k = np.sqrt(np.maximum(k2, 1e-30))
    A = MU0*I/(np.pi*k)*np.sqrt(R/rr)*((1-k2/2)*K-E)
    axis = r < 1e-6*R
    if np.any(axis):
        Bz = np.where(axis, MU0*I*R*R/(2*(R*R+zz*zz)**1.5), Bz)
        Br = np.where(axis, 0.0, Br)
        A = np.where(axis, MU0*I*R*R*r/(4*(R*R+zz*zz)**1.5), A)
    return Br, Bz, A


def field(coils, r, z, per_coil=False):
    r = np.asarray(r, float); z = np.asarray(z, float)
    Br = np.zeros(np.broadcast(r, z).shape); Bz = np.zeros_like(Br); A = np.zeros_like(Br); parts = []
    for c in coils:
        br, bz, a = loop(c['I'], c['R'], c['z'], r, z)
        Br = Br+br; Bz = Bz+bz; A = A+a
        if per_coil:
            parts.append((br, bz))
    return (Br, Bz, A, parts) if per_coil else (Br, Bz, A)


def u_B(coils, r, z):
    Br, Bz, _ = field(coils, r, z)
    return (Br*Br+Bz*Bz)/(2*MU0)


def stored_energy(coils):
    """W = 1/2 sum_i I_i Phi_i; the self flux of each loop from its winding-pack radius a (round-section estimate)."""
    W = 0.0
    for i, ci in enumerate(coils):
        a = max(ci['a'], 1e-3)
        Ls = MU0*ci['R']*(math.log(8*ci['R']/a)-1.75)
        W += 0.5*Ls*ci['I']**2
        for j, cj in enumerate(coils):
            if j > i:
                _, _, A = loop(cj['I'], cj['R'], cj['z'], np.array([ci['R']]), np.array([ci['z']]))
                W += ci['I']*2*math.pi*ci['R']*float(A[0])          # mutual term counted once: I_i M_ij I_j
    return W


def coil_force_z(coils):
    """Static axial magnetic force on each coil from the others (N, +z aft): F = I 2 pi R Br_others(R, z)."""
    out = []
    for i, ci in enumerate(coils):
        others = [c for j, c in enumerate(coils) if j != i]
        if not others:
            out.append(0.0); continue
        Br, _, _ = field(others, np.array([ci['R']]), np.array([ci['z']]))
        out.append(float(ci['I']*2*math.pi*ci['R']*Br[0]))   # dF = I dl x B: for a loop, F_z = -I 2 pi R Br sign handled by I sign
    return [-f for f in out]


def on_body(coils, r, z):
    """Index of the coil body a point lies in (winding pack of half-size a, neutron fin of depth `fin` radially outward), else -1."""
    hit = np.full(np.shape(r), -1)
    for k, c in enumerate(coils):
        inpack = (r-c['R'])**2+(z-c['z'])**2 < c['a']**2
        infin = (np.abs(z-c['z']) < c['a']) & (r > c['R']) & (r < c['R']+c.get('fin', 0.0))
        hit = np.where((hit < 0) & (inpack | infin), k, hit)
    return hit


# ---------- 1. test-particle ions -------------------------------------------------------------------------------------------------------
def species_set(ve_c, mode='thermal', b=0.95, tail=0.0):
    """Exhaust ions at one operating point, mono-energetic per species as in Vertex 2.7 fuel.exhaust_species: products p and alpha
    (burned share b) and unburned D and He-3, energies such that the mass-averaged jet energy per kg is ve^2 / (2 eta_dispersion);
    'thermal' = equal energy per ion, 'charge' = equal energy per unit charge. Optional unchanneled 14.7 MeV proton tail share."""
    sp = [('p', M_P, 1, b), ('alpha', M_A, 2, b), ('D', M_D, 1, 1-b), ('He3', M_H3, 2, 1-b)]
    w = [(n, m, Z, (Z if mode == 'charge' else 1.0)) for _, m, Z, n in sp]
    # pick E0 so that the momentum-weighted exhaust speed equals ve (momentum thrust per unit mass flow)
    def ve_of(E0):
        mom = sum(n*math.sqrt(2*m*E0*f) for n, m, Z, f in w); mass = sum(n*m for n, m, Z, f in w)
        return mom/mass
    lo, hi = 1e-16, 1e-10
    for _ in range(200):
        mid = math.sqrt(lo*hi)
        lo, hi = (mid, hi) if ve_of(mid) < ve_c*C else (lo, mid)
    E0 = lo
    out = [dict(name=nm, m=m, Z=Z, n=n, E=E0*(Z if mode == 'charge' else 1.0)) for nm, m, Z, n in sp if n > 0]
    if tail > 0:
        out.append(dict(name='p 14.7 MeV tail', m=M_P, Z=1, n=tail, E=14.68*MEV))
    return out


def _gamma_u(m, E):
    g = 1+E/(m*C*C); return g, C*math.sqrt(1-1/g**2)*g


def trace(coils, zb, species, mus, src_r=0.0, ship=None, box=200.0, ds=0.25, wc=0.15, max_steps=200000):
    """Push every (species, mu) ion from (src_r, 0, zb) with direction cos(theta) = mu in the x-z plane (on-axis sources are axisymmetric;
    an off-axis source adds an azimuth scan through `mus` given as (mu, phi) pairs). Returns per-ion arrays."""
    rows = []
    for s in species:
        for mu in mus:
            if isinstance(mu, tuple):
                mu, ph = mu
            else:
                ph = 0.0
            rows.append((s, mu, ph))
    N = len(rows)
    m = np.array([s['m'] for s, _, _ in rows]); q = np.array([s['Z']*E_CH for s, _, _ in rows])
    gu = np.array([_gamma_u(s['m'], s['E'])[1] for s, _, _ in rows])
    mu_ = np.array([x for _, x, _ in rows]); ph_ = np.array([x for _, _, x in rows]); st = np.sqrt(np.maximum(1-mu_*mu_, 0.0))
    u = np.stack([gu*st*np.cos(ph_), gu*st*np.sin(ph_), gu*mu_], 1)
    x = np.stack([np.full(N, src_r), np.zeros(N), np.full(N, float(zb))], 1)
    u0 = u.copy()
    nc = len(coils); J = np.zeros((N, nc, 3)); status = np.full(N, 'ACTIVE', dtype=object); act = np.arange(N)
    xf = np.zeros((N, 3)); uf = np.zeros((N, 3)); hitc = np.full(N, -1)
    steps = 0
    while act.size and steps < max_steps:
        steps += 1
        xa = x[act]; ua = u[act]; ma = m[act]; qa = q[act]
        r = np.hypot(xa[:, 0], xa[:, 1])
        Br, Bz, _, parts = field(coils, r, xa[:, 2], per_coil=True)
        cph = np.where(r > 0, xa[:, 0]/np.maximum(r, 1e-30), 1.0); sph = np.where(r > 0, xa[:, 1]/np.maximum(r, 1e-30), 0.0)
        B = np.stack([Br*cph, Br*sph, Bz], 1)
        Bm = np.linalg.norm(B, axis=1)
        g = np.sqrt(1+np.sum(ua*ua, 1)/C**2); v = np.linalg.norm(ua, axis=1)/g
        dt = np.minimum(ds/v, wc*g*ma/(qa*np.maximum(Bm, 1e-12)))
        # Boris rotation (no electric field)
        t = (qa*dt/(2*g*ma))[:, None]*B; t2 = np.sum(t*t, 1)[:, None]; s_ = 2*t/(1+t2)
        up = ua+np.cross(ua, t); un = ua+np.cross(up, s_)
        gn = np.sqrt(1+np.sum(un*un, 1)/C**2)
        vmid = 0.5*(ua/g[:, None]+un/gn[:, None])
        for k, (br, bz) in enumerate(parts):                  # impulse on coil k = - integral q v x B_k dt
            Bk = np.stack([br*cph, br*sph, bz], 1)
            J[act, k] -= (qa*dt)[:, None]*np.cross(vmid, Bk)
        xn = xa+un/gn[:, None]*dt[:, None]
        u[act] = un; x[act] = xn
        rn = np.hypot(xn[:, 0], xn[:, 1]); zr = xn[:, 2]-zb
        body = on_body(coils, rn, xn[:, 2])
        done = np.full(act.size, '', dtype=object)
        done = np.where(body >= 0, 'COIL', done)
        done = np.where((done == '') & (zr > box), 'AFT', done)
        done = np.where((done == '') & (zr < -box), 'FORWARD', done)
        done = np.where((done == '') & (rn > box), 'RADIAL', done)
        fin = done != ''
        if np.any(fin):
            idx = act[fin]
            status[idx] = done[fin]; xf[idx] = xn[fin]; uf[idx] = un[fin]; hitc[idx] = body[fin]
            act = act[~fin]
    status[act] = 'TRAPPED'; xf[act] = x[act]; uf[act] = u[act]
    # forward escapes: do they reach the ship? straight line to the stern face plane, ship disk offset from the engine axis
    on_ship = np.zeros(N, bool); ship_frac = np.zeros(N)
    if ship:
        fw = np.where(status == 'FORWARD')[0]
        for i in fw:
            d = uf[i]/np.linalg.norm(uf[i])
            if d[2] >= 0:
                continue
            tpl = (ship['z_face']-xf[i, 2])/d[2]
            p = xf[i]+tpl*d; rho = math.hypot(p[0], p[1])
            # azimuthally averaged chance the point falls inside the ship disk of radius Rs centred at offset a
            a = ship['offset']; Rs = ship['R']
            if rho+a <= Rs:
                f = 1.0
            elif rho == 0 or abs(rho-a) >= Rs:
                f = 0.0
            else:
                f = math.acos(max(-1.0, min(1.0, (rho*rho+a*a-Rs*Rs)/(2*a*rho))))/math.pi
            ship_frac[i] = f
    E0 = np.array([s['E'] for s, _, _ in rows])
    gF = np.sqrt(1+np.sum(uf*uf, 1)/C**2)
    Ef = (gF-1)*m*C*C
    return dict(rows=rows, status=status, u0=u0*m[:, None], pf=uf*m[:, None], E0=E0, Ef=Ef, J=J*1.0, hit_coil=hitc, ship_frac=ship_frac,
                steps=steps, xf=xf)


def summarize(tr, coils, weights=None):
    """Isotropic-source weights (equal per mu cell unless given), species weighted by their number share n. Fractions of energy and
    momentum, the net axial thrust fraction, and where the reaction lands."""
    rows = tr['rows']; N = len(rows)
    nsp = {}
    for s, _, _ in rows:
        nsp[s['name']] = nsp.get(s['name'], 0)+1
    w = np.array([s['n']/nsp[s['name']] for s, _, _ in rows]) if weights is None else weights
    p0 = np.linalg.norm(tr['u0'], axis=1); E0 = tr['E0']; st = tr['status']; pf = tr['pf']
    P0 = np.sum(w*p0); W0 = np.sum(w*E0)
    space = (st == 'AFT') | (st == 'RADIAL') | ((st == 'FORWARD'))
    sf = np.where(st == 'FORWARD', tr['ship_frac'], 0.0)       # share of a forward escape that lands on the ship
    leave = np.where(space, 1.0-sf, 0.0)
    thrust = np.sum(w*leave*pf[:, 2])                           # momentum carried to space, +z aft = thrust on the ship (bow-ward)
    frac = {}
    for k in ('AFT', 'FORWARD', 'RADIAL', 'COIL', 'TRAPPED'):
        sel = st == k
        frac[k] = float(np.sum(w[sel]*E0[sel])/W0)
    fwd_ship = float(np.sum(w*sf*E0)/W0)
    aft = st == 'AFT'
    cos_aft = float(np.sum(w[aft]*pf[aft, 2])/max(np.sum(w[aft]*np.linalg.norm(pf[aft], axis=1)), 1e-30))
    Jz = np.sum(w[:, None]*tr['J'][:, :, 2], 0)                 # impulse on each coil (+z = toward the exhaust)
    # the ship's impulse is -(momentum to space) = -thrust; the coils carry -sum(Jz) of it ... reported as shares of the thrust
    coil_share = [float(-j/thrust) if thrust else 0.0 for j in Jz]
    # momentum deposited by ions that strike the coils or land on the ship
    struck = (st == 'COIL') | (st == 'TRAPPED')
    struct = float(np.sum(w[struck]*pf[struck, 2])+np.sum(w*sf*pf[:, 2]))
    Wf_aft = float(np.sum(w[aft]*tr['Ef'][aft])/W0)
    return dict(kappa=float(thrust/P0), capture_energy=frac['AFT'], aft_cos=cos_aft, fractions=frac, forward_on_ship=fwd_ship,
                forward_to_space=frac['FORWARD']-fwd_ship, coil_impulse_share=coil_share, structure_impulse_share=float(-struct/thrust) if thrust else 0.0,
                closure=float((-np.sum(Jz)-struct)/thrust-1.0) if thrust else 0.0, aft_energy_kept=Wf_aft)


# ---------- 2. high-beta reflection -----------------------------------------------------------------------------------------------------
def reflect(coils, zb, Ep, e=1.0, n=721, ds=0.05, dmax=400.0, max_steps=40000, src_r=0.0):
    """Rays of an isotropic pulse in the meridional plane, reflected where u_B >= 3 Ep / (4 pi d^3) (d = distance from the burn).
    Returns kappa (axial momentum to space / initial momentum), forward and coil-strike shares, the energy lost at reflections and the
    impulse delivered to the field."""
    th = (np.arange(n)+0.5)*np.pi/n
    w = np.sin(th)*np.pi/n/2                                      # isotropic weight of each ray (sums to 1)
    x = np.stack([np.full(n, src_r), np.full(n, float(zb))], 1)    # (r, z)
    v = np.stack([np.sin(th), np.cos(th)], 1)                      # unit speed; |v| falls only through inelastic reflections
    k3 = 3*Ep/(4*np.pi)

    def g(p):
        d = np.maximum(np.hypot(p[:, 0]-src_r, p[:, 1]-zb), 1e-3)
        return u_B(coils, np.abs(p[:, 0]), p[:, 1])-k3/d**3

    act = np.arange(n); status = np.full(n, 'ACTIVE', dtype=object); J = np.zeros(n); nref = np.zeros(n, int); vf = v.copy()
    loss = np.zeros(n)
    steps = 0
    while act.size and steps < max_steps:
        steps += 1
        xa = x[act]; va = v[act]
        sp = np.linalg.norm(va, axis=1)
        d = np.hypot(xa[:, 0]-src_r, xa[:, 1]-zb)
        h = np.clip(ds*np.maximum(d, 1.0)/4.0, ds, 2.0)[:, None]  # step grows with distance
        xn = xa+h*va/np.maximum(sp, 1e-12)[:, None]
        # the axis: an axisymmetric ray crossing r = 0 continues on the other side (mirror in the meridional plane)
        neg = xn[:, 0] < 0
        xn[neg, 0] *= -1; va[neg, 0] *= -1
        crossing = g(xn) >= 0
        if np.any(crossing):
            i = np.where(crossing)[0]; p = xn[i]; eps = 0.02
            gx = (g(p+[eps, 0])-g(p-[eps, 0]))/(2*eps); gz = (g(p+[0, eps])-g(p-[0, eps]))/(2*eps)
            nn = np.stack([gx, gz], 1); nn /= np.maximum(np.linalg.norm(nn, axis=1), 1e-30)[:, None]
            vn = np.sum(va[i]*nn, 1)
            into = vn > 0
            dv = np.where(into, -(1+e)*vn, 0.0)[:, None]*nn
            vnew = va[i]+dv
            loss[act[i]] += np.where(into, (1-e*e)*vn*vn, 0.0)
            J[act[i]] -= dv[:, 1]                                 # axial impulse given to the field (its coils)
            nref[act[i]] += into
            va[i] = vnew; xn[i] = xa[i]                           # stay inside, new direction
        x[act] = xn; v[act] = va
        r = xn[:, 0]; z = xn[:, 1]
        body = on_body(coils, r, z)
        dn = np.hypot(r-src_r, z-zb)
        done = np.full(act.size, '', dtype=object)
        done = np.where(body >= 0, 'COIL', done)
        far = (done == '') & (dn > dmax)
        done = np.where(far & (va[:, 1] > 0), 'AFT', done)
        done = np.where(far & (va[:, 1] <= 0) & (z < zb), 'FORWARD', done)
        done = np.where((done == '') & far, 'RADIAL', done)
        fin = done != ''
        if np.any(fin):
            idx = act[fin]; status[idx] = done[fin]; vf[idx] = va[fin]; act = act[~fin]
    status[act] = 'TRAPPED'; vf[act] = v[act]
    space = (status == 'AFT') | (status == 'FORWARD') | (status == 'RADIAL')
    kappa = float(np.sum(w*np.where(space, vf[:, 1], 0.0)))
    frac = {k: float(np.sum(w[status == k])) for k in ('AFT', 'FORWARD', 'RADIAL', 'COIL', 'TRAPPED')}
    return dict(kappa=kappa, fractions=frac, energy_lost=float(np.sum(w*loss)), field_impulse=float(np.sum(w*J)),
                reflections=float(np.sum(w*nref)), aft_cos=float(np.sum(w[status == 'AFT']*vf[status == 'AFT', 1]
                                                                    /np.maximum(np.linalg.norm(vf[status == 'AFT'], axis=1), 1e-12))
                                                             / max(frac['AFT'], 1e-30)))


def shell(coils, zb, Ep, n=361, compress=1.5, dmax=400.0, dstep=0.02, max_steps=30000, src_r=0.0):
    """High-beta pulse as a diamagnetic cavity (magnetic piston), energy-conserving form. The pulse energy Ep leaves the burn as an
    isotropic radial expansion; each solid-angle sector i (mass share dm_i) must push the field out of its share of the cavity volume,
    V_i = dm_i 4/3 pi d^3, at the cost U_i = c u_B(x) V_i (c = 1.5: a perfectly diamagnetic sphere; flux compression, PROTOTYPE). The
    sector moves in that potential: F = -c dm (4 pi / 3) (3 d^2 u_B r_hat + d^3 grad u_B), the field pressure on its band of the cavity
    wall plus the push out of strong field. Elastic by construction (no instability, diffusion or heating losses), so it is the
    optimistic collective bound; it turns where u_B = 3 Ep / (4 pi c d^3), the same threshold as the sharp wall of reflect(). Only Ep
    and the field geometry matter. Returns kappa, shares, the impulse taken by the field and the energy check."""
    th = (np.arange(n)+0.5)*np.pi/n
    dm = np.sin(th)*np.pi/n/2                                      # sector share (sums to 1)
    M = 2*Ep                                                       # units: v0 = 1
    x = np.stack([np.full(n, src_r)+1e-3*np.sin(th), np.full(n, float(zb))+1e-3*np.cos(th)], 1)
    v = np.stack([np.sin(th), np.cos(th)], 1)
    kfac = compress*4*np.pi/3/M

    def acc(p):
        rr = np.abs(p[:, 0]); zz = p[:, 1]
        dvec = p-[src_r, zb]; d = np.maximum(np.linalg.norm(dvec, axis=1), 1e-6)
        u = u_B(coils, rr, zz); eps = 0.01
        gr = (u_B(coils, rr+eps, zz)-u_B(coils, np.abs(rr-eps), zz))/(2*eps)
        gz = (u_B(coils, rr, zz+eps)-u_B(coils, rr, zz-eps))/(2*eps)
        gr = np.where(p[:, 0] < 0, -gr, gr)
        a = -kfac*(3*d*d*u)[:, None]*dvec/d[:, None]-kfac*(d**3)[:, None]*np.stack([gr, gz], 1)
        return a, kfac*u*d**3*M                                    # potential energy per unit sector mass x M ... (U_i / dm_i)
    status = np.full(n, 'ACTIVE', dtype=object); J = 0.0
    alive = np.ones(n, bool); steps = 0
    a, _ = acc(x)
    while alive.any() and steps < max_steps:
        steps += 1
        d = np.hypot(x[:, 0]-src_r, x[:, 1]-zb)
        amag = np.linalg.norm(a, axis=1)
        # sectors are independent in a static potential, so each keeps its own step (no common clock is needed)
        dt = np.minimum(dstep*np.maximum(d, 0.5), np.sqrt(dstep*np.maximum(d, 0.5)/np.maximum(amag, 1e-30)))[:, None]
        vh = v+0.5*dt*a
        xn = x+dt*vh*alive[:, None]
        an, _ = acc(xn)
        vn = vh+0.5*dt*an
        J -= float(np.sum(dm*M*alive*(vn[:, 1]-v[:, 1])))          # axial momentum the field takes
        x = np.where(alive[:, None], xn, x); v = np.where(alive[:, None], vn, v); a = an
        neg = x[:, 0] < 0
        x[neg, 0] *= -1; v[neg, 0] *= -1; a[neg, 0] *= -1
        body = on_body(coils, x[:, 0], x[:, 1])
        hitb = alive & (body >= 0)
        status[hitb] = 'COIL'; alive &= ~hitb
        dn = np.hypot(x[:, 0]-src_r, x[:, 1]-zb)
        far = alive & (dn > dmax)
        status[far & (v[:, 1] > 0)] = 'AFT'
        status[far & (v[:, 1] <= 0) & (x[:, 1] < zb)] = 'FORWARD'
        status[far & (status == 'ACTIVE')] = 'RADIAL'
        alive &= ~far
    status[alive] = 'TRAPPED'
    space = (status == 'AFT') | (status == 'FORWARD') | (status == 'RADIAL')
    sp = np.linalg.norm(v, axis=1)
    _, Ue = acc(x)
    kappa = float(np.sum(dm*np.where(space, v[:, 1], 0.0)))
    frac = {k: float(np.sum(dm[status == k])) for k in ('AFT', 'FORWARD', 'RADIAL', 'COIL', 'TRAPPED')}
    ek = float(np.sum(dm*sp*sp))
    return dict(kappa=kappa, fractions=frac, energy_check=ek+float(np.sum(dm*Ue))/Ep-1.0, field_impulse=J/M, steps=steps,
                aft_cos=float(np.sum(dm[status == 'AFT']*v[status == 'AFT', 1]/np.maximum(sp[status == 'AFT'], 1e-12))/max(frac['AFT'], 1e-30)))


# ---------- 3. detachment ---------------------------------------------------------------------------------------------------------------
def field_line(coils, r0, z0, dz=0.25, zmax=400.0):
    """Follow the field line through (r0, z0) aft by integrating dr/dz = Br/Bz; returns arrays z, r, the line angle and u_B."""
    zs = [z0]; rs = [r0]
    r, z = r0, z0
    while z < zmax:
        Br, Bz, _ = field(coils, np.array([r]), np.array([z]))
        if abs(Bz[0]) < 1e-12:
            break
        slope = Br[0]/Bz[0]
        r = max(r+slope*dz, 0.0); z = z+dz
        rs.append(r); zs.append(z)
        if abs(slope) > 50:
            break
    zs = np.array(zs); rs = np.array(rs)
    Br, Bz, _ = field(coils, rs, zs)
    return zs, rs, np.degrees(np.arctan2(np.abs(Br), np.abs(Bz))), (Br*Br+Bz*Bz)/(2*MU0)


def detachment(coils, zb, mdot, v, r_mouth, peak=1.0):
    """Arefiev-Breizman: the exhaust detaches where u_B drops below rho v^2 / 2 on its boundary flux surface (the line from the
    mouth radius at the burn plane). rho = mdot / (v pi r^2) time-averaged, times `peak` for the pulse shell. Returns the detachment
    point, the field-line angle there and the conical thrust factor (1 + cos a) / 2."""
    zs, rs, ang, uB = field_line(coils, r_mouth, zb)
    rho = peak*mdot/(v*np.pi*np.maximum(rs, 1e-3)**2)
    kin = 0.5*rho*v*v
    i = np.argmax(uB < kin) if np.any(uB < kin) else len(zs)-1
    a = float(ang[i])
    return dict(z_det=float(zs[i]), r_det=float(rs[i]), angle_deg=a, cone_factor=(1+math.cos(math.radians(a)))/2, beta_at_burn=float(kin[0]/uB[0]),
                MA_at_burn=float(math.sqrt(kin[0]/uB[0])))
