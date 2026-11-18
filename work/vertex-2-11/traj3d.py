"""Vertex 2.11 Stern Mirror: 3D electrostatic field of the faceted stack and 3D ion trajectories through the four-engine magnetic field
(research, not canon).

    python3 work/vertex-2-11/traj3d.py      writes traj3d.json/.log (~10-20 min, 4 processes)

Geometry (ship frame, metres, +z aft): stern disk r 45 m, apex of the mirror entrance at z_s = -231.93 m. Four facets, one per engine
quarter (the quarter whose engine direction n_q has the largest n_q . P), each tilted outward by alpha: entrance surface
z_e(P) = z_s + tan(alpha) max_q(n_q . P), seams on the diagonals x = +-y. Below it the 2.10 stack (D210): suppressor at depth 0.5 m
(-0.75 MV), ten 0.8 m stages to the 10 MV plate at depth 8.5 m, grids as folded parallel layers.

Field: phi = phi0 + psi. phi0 = V(delta) with delta the depth below the local facet (exact between flat parallel grids); psi is the 3D
correction where the layers fold (seams, apex), solved by finite differences on one quadrant (mirror symmetry at x = 0 and y = 0) with
psi = 0 on every grid layer, the plate, the entrance and an ideally graded rim at r 45 m; source -V'(delta) L_h(delta), which is
non-zero only where delta has its crease. Space charge is not included here (1D PIC: <= 45 % field change at 30 %).

Ions: the forward escapes of the B2d_z12 nozzle (A1, burn z 12; Vertex 2.10 forward.py / recover.py landing) arrive at the stern from
their own engine (24 m off axis), rotated over 24 azimuths, energy-weighted. They are pushed (relativistic Boris, E and B) through the
3D stack field and then aft through the static field of all four engines' coils (plug 5 T R 3 m at z -6, main 1.5 T R 10 m at z 0, per
engine). Outcomes: PLATE (E/q above the top), ENGINE strike on any housing (r 11.44 m, z -31.93 .. 0; front face or side), SPINE (an
assumed r 3 m spine envelope on the axis, PROTOTYPE), AFT (past z +60 m), RADIAL (r > 400 m), RETURN bounces (ions magnetically turned
back to the mirror are followed through it again, up to 6 bounces), TRAPPED (step limit).
"""
import json
import math
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent/'vertex-2-8')); sys.path.insert(0, str(HERE.parent/'vertex-2-10'))
import nozzle_core as N  # noqa: E402
import forward as F  # noqa: E402
import recover as RC  # noqa: E402

C = 2.99792458e8; QE = 1.602176634e-19
Z_S = -231.93; Z_FRONT = -31.93; R_DISK = 45.0; A_ENV = 11.44; R_SPINE = 3.0
ENGINES = [(24.0, 0.0), (-24.0, 0.0), (0.0, 24.0), (0.0, -24.0)]
NQ = np.array(ENGINES)/24.0
COILS = [F.coil(5.0, 3.0, -6.0, 'plug'), F.M15]

LAYERS_D = np.array([0.0, 0.5]+[0.5+0.8*k for k in range(1, 11)])
LAYERS_V = np.array([0.0, -0.75e6]+[-0.75e6+k*(10.75e6/10) for k in range(1, 11)])
D_PLATE = LAYERS_D[-1]


def V_of(d):
    return np.interp(d, LAYERS_D, LAYERS_V)


def dV_of(d):
    k = np.clip(np.searchsorted(LAYERS_D, d, side='right')-1, 0, len(LAYERS_D)-2)
    return (LAYERS_V[k+1]-LAYERS_V[k])/(LAYERS_D[k+1]-LAYERS_D[k])


def depth(x, y, z, ta):
    """delta (depth below the entrance surface along the facet normal) and the facet index."""
    dots = x[..., None]*NQ[:, 0]+y[..., None]*NQ[:, 1]
    q = np.argmax(dots, -1); mx = np.max(dots, -1)
    ca = 1/math.sqrt(1+ta*ta)
    return (Z_S+ta*mx-z)*ca, q


# ------------------------------------------------------------------ 3D correction psi on one quadrant

def solve_psi(ta, h=0.25, tol=1e-8):
    xs = np.arange(0.0, R_DISK+2*h, h); ys = xs.copy()
    zmin = Z_S+min(0.0, ta*R_DISK)-D_PLATE/math.cos(math.atan(ta))-1.0; zmax = Z_S+max(0.0, ta*R_DISK)+1.0
    zs = np.arange(zmin, zmax+h, h)
    X, Y, Zg = np.meshgrid(xs, ys, zs, indexing='ij')
    d, q = depth(X, Y, Zg, ta)
    r = np.hypot(X, Y)
    # pinned: outside the stack, rim, and nodes within h/2 of any grid layer
    near = np.min(np.abs(d[..., None]-LAYERS_D), -1) < 0.5*h
    pinned = (d <= 0.0) | (d >= D_PLATE) | (r >= R_DISK) | near
    free = ~pinned
    nx, ny, nz = X.shape
    idx = -np.ones(X.shape, np.int64); idx[free] = np.arange(free.sum())
    # source: -V'(delta_c) * L_h(delta) (only the crease of delta contributes)
    dp = np.pad(d, 1, mode='edge')
    dp[0, :, :] = dp[2, :, :]; dp[:, 0, :] = dp[:, 2, :]          # mirror symmetry at x = 0 and y = 0
    Ld = (dp[2:, 1:-1, 1:-1]+dp[:-2, 1:-1, 1:-1]+dp[1:-1, 2:, 1:-1]+dp[1:-1, :-2, 1:-1]+dp[1:-1, 1:-1, 2:]+dp[1:-1, 1:-1, :-2]-6*d)/(h*h)
    src = -dV_of(np.clip(d, 0, D_PLATE-1e-9))*Ld
    rows, cols, vals = [], [], []
    fi = np.argwhere(free)
    n = len(fi)
    rows.append(np.arange(n)); cols.append(np.arange(n)); vals.append(np.full(n, -6.0))
    for ax in range(3):
        for s in (-1, 1):
            nb = fi.copy(); nb[:, ax] += s
            if ax in (0, 1):
                nb[:, ax] = np.where(nb[:, ax] < 0, 1, nb[:, ax])
            ok = (nb[:, ax] >= 0) & (nb[:, ax] < X.shape[ax])
            j = np.full(n, -1)
            j[ok] = idx[nb[ok, 0], nb[ok, 1], nb[ok, 2]]
            m = j >= 0
            rows.append(np.arange(n)[m]); cols.append(j[m]); vals.append(np.ones(m.sum()))
    A = sp.csr_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(n, n))
    b = -src[free]*h*h
    t0 = time.time()
    sol, info = spla.cg(-A, b, rtol=tol, maxiter=5000)        # A psi = -h^2 L(phi0)
    psi = np.zeros(X.shape); psi[free] = sol
    gx, gy, gz = np.gradient(psi, h, h, h)
    E0mag = np.abs(dV_of(np.clip(d, 0, D_PLATE-1e-9)))
    inside = (d > 0) & (d < D_PLATE) & (r < R_DISK)
    rel = np.sqrt(gx*gx+gy*gy+gz*gz)/np.maximum(E0mag, 1.0)
    # distance of every node from the nearest seam (diagonal)
    dseam = np.abs(np.abs(X)-np.abs(Y))/math.sqrt(2)
    stats = dict(h=h, n_free=int(n), cg_info=int(info), seconds=time.time()-t0, psi_max_kV=float(np.abs(psi).max()/1e3),
                 rel_field_max=float(rel[inside].max()),
                 rel_field_p99=float(np.percentile(rel[inside], 99)),
                 extent_m={f'{t:g}': float(dseam[inside & (rel > t)].max()) if np.any(inside & (rel > t)) else 0.0
                           for t in (0.01, 0.05, 0.2)})
    return dict(xs=xs, ys=ys, zs=zs, gx=gx, gy=gy, gz=gz, stats=stats)


def interp3(P, g, arr):
    xs, ys, zs = g['xs'], g['ys'], g['zs']; h = xs[1]-xs[0]
    fx = np.clip(P[:, 0]/h, 0, len(xs)-1.001); fy = np.clip(P[:, 1]/h, 0, len(ys)-1.001)
    fz = np.clip((P[:, 2]-zs[0])/h, 0, len(zs)-1.001)
    i, j, k = fx.astype(int), fy.astype(int), fz.astype(int); a, b, c = fx-i, fy-j, fz-k
    out = 0.0
    for di, wa in ((0, 1-a), (1, a)):
        for dj, wb in ((0, 1-b), (1, b)):
            for dk, wc in ((0, 1-c), (1, c)):
                out = out+wa*wb*wc*arr[i+di, j+dj, k+dk]
    return out


def E_field(X, ta, g):
    d, q = depth(X[:, 0], X[:, 1], X[:, 2], ta)
    inside = (d > 0) & (d < D_PLATE) & (np.hypot(X[:, 0], X[:, 1]) < R_DISK)
    ca = 1/math.sqrt(1+ta*ta); sa = ta*ca
    grad_d = np.stack([sa*NQ[q, 0], sa*NQ[q, 1], -ca*np.ones(len(q))], 1)
    E = np.zeros_like(X)
    E[inside] = -dV_of(d[inside])[:, None]*grad_d[inside]
    if g is not None and np.any(inside):
        P = np.abs(X[inside]); P[:, 2] = X[inside, 2]
        sx = np.sign(X[inside, 0]); sy = np.sign(X[inside, 1])
        E[inside, 0] -= sx*interp3(P, g, g['gx']); E[inside, 1] -= sy*interp3(P, g, g['gy']); E[inside, 2] -= interp3(P, g, g['gz'])
    return E, d


def B_field(X):
    B = np.zeros_like(X)
    for ex, ey in ENGINES:
        dx = X[:, 0]-ex; dy = X[:, 1]-ey; r = np.hypot(dx, dy)
        Br, Bz, _ = N.field(COILS, r, X[:, 2])
        c = np.where(r > 1e-9, dx/np.maximum(r, 1e-9), 1.0); s = np.where(r > 1e-9, dy/np.maximum(r, 1e-9), 0.0)
        B[:, 0] += Br*c; B[:, 1] += Br*s; B[:, 2] += Bz
    return B


def incoming(nphi=24, max_ions=4000, seed=3):
    coils = COILS
    tr, w, fw, W0 = RC.landing(coils, 12.0)
    rng = np.random.default_rng(seed)
    X, U, M, Q, W, P_land = [], [], [], [], [], []
    for i in fw:
        x = tr['xf'][i]; u = tr['pf'][i]/np.linalg.norm(tr['pf'][i])
        if u[2] >= 0:
            continue
        s = tr['rows'][i][0]; m = s['m']; q = s['Z']*QE; E = tr['Ef'][i]
        g = 1+E/(m*C*C); uu = C*math.sqrt(g*g-1)
        for k in range(nphi):
            ph = (k+0.5)*2*math.pi/nphi; c, s_ = math.cos(ph), math.sin(ph)
            px, py = x[0]*c-x[1]*s_, x[0]*s_+x[1]*c; ux, uy = u[0]*c-u[1]*s_, u[0]*s_+u[1]*c
            t = (Z_S-x[2])/u[2]
            P = np.array([ENGINES[0][0]+px+ux*t, py+uy*t])
            if math.hypot(*P) > R_DISK:
                continue
            # start 30 m aft of the stern plane on the incoming ray
            t0 = t-30.0/abs(u[2])
            X.append([ENGINES[0][0]+px+ux*t0, py+uy*t0, x[2]+u[2]*t0]); U.append([ux*uu, uy*uu, u[2]*uu])
            M.append(m); Q.append(q); W.append(w[i]*tr['E0'][i]/nphi); P_land.append(P)
    X, U, M, Q, W, P_land = map(np.array, (X, U, M, Q, W, P_land))
    if len(X) > max_ions:
        k = rng.choice(len(X), max_ions, replace=False, p=W/W.sum())
        X, U, M, Q, P_land = X[k], U[k], M[k], Q[k], P_land[k]; W = np.full(max_ions, W.sum()/max_ions)
    # incidence angle relative to the local facet normal (alpha 10 deg) for the grid-opacity and heat checks
    return dict(X=X, U=U, M=M, Q=Q, W=W, P_land=P_land, W_landed=float(W.sum()), landed_share=float(W.sum()/W0))


def push(ion, ta, g, use_B=True, max_steps=60000, ds_in=0.04, ds_out=0.5, wc=0.15, max_bounce=6):
    X = ion['X'].copy(); U = ion['U'].copy(); M = ion['M']; Q = ion['Q']; n = len(X)
    status = np.full(n, '', dtype=object); bounce = np.zeros(n, int); was_in = np.zeros(n, bool)
    xf = np.zeros((n, 3)); uf = np.zeros((n, 3)); hit_engine = -np.ones(n, int); first_out_u = np.zeros((n, 3)); got_out = np.zeros(n, bool)
    act = np.arange(n)
    logS = {o: np.zeros(n) for o in (0.001, 0.005)}; ncross = np.zeros(n, int)
    kprev = np.searchsorted(LAYERS_D, depth(X[:, 0], X[:, 1], X[:, 2], ta)[0])
    ca = 1/math.sqrt(1+ta*ta); sa = ta*ca
    for step in range(max_steps):
        if act.size == 0:
            break
        x = X[act]; u = U[act]; m = M[act]; q = Q[act]
        E, d = E_field(x, ta, g)
        B = B_field(x) if use_B else np.zeros_like(x)
        gam = np.sqrt(1+np.sum(u*u, 1)/C**2); v = np.linalg.norm(u, axis=1)/gam
        Bm = np.linalg.norm(B, axis=1)
        dsx = np.where(d > -2.0, ds_in, ds_out)
        dt = np.minimum(dsx/np.maximum(v, 1e3), wc*gam*m/(q*np.maximum(Bm, 1e-12)))
        h = (q*dt/(2*m))[:, None]
        um = u+h*E
        gm = np.sqrt(1+np.sum(um*um, 1)/C**2)
        t = h*B/gm[:, None]; t2 = np.sum(t*t, 1)[:, None]; s_ = 2*t/(1+t2)
        up = um+np.cross(um, t); un = um+np.cross(up, s_)
        un = un+h*E
        gn = np.sqrt(1+np.sum(un*un, 1)/C**2)
        xn = x+un/gn[:, None]*dt[:, None]
        X[act] = xn; U[act] = un
        dn, qn = depth(xn[:, 0], xn[:, 1], xn[:, 2], ta)
        rs = np.hypot(xn[:, 0], xn[:, 1])
        # grid-layer crossings: wire-grid opacity seen at the crossing angle, o / cos(theta) to the local layer normal
        kn = np.searchsorted(LAYERS_D, dn)
        cr = (kn != kprev[act]) & (rs < R_DISK) & (np.minimum(kn, kprev[act]) < len(LAYERS_D))
        if np.any(cr):
            nv = np.stack([sa*NQ[qn, 0], sa*NQ[qn, 1], -ca*np.ones(len(qn))], 1)
            cth = np.abs(np.sum(un*nv, 1))/np.linalg.norm(un, axis=1)
            nk = np.abs(kn-kprev[act])
            for o in logS:
                logS[o][act[cr]] += nk[cr]*np.log(np.clip(1-o/np.maximum(cth[cr], 1e-6), 1e-9, 1))
            ncross[act[cr]] += nk[cr]
        kprev[act] = kn
        inside = (dn > 0) & (rs < R_DISK)
        # bounce bookkeeping: entering the mirror counts one pass
        newin = inside & ~was_in[act]
        bounce[act[newin]] += 1
        leaving = (~inside) & was_in[act] & (un[:, 2] > 0)
        first = leaving & ~got_out[act]
        first_out_u[act[first]] = un[first]; got_out[act[first]] = True
        was_in[act] = inside
        done = np.full(act.size, '', dtype=object)
        done = np.where((dn >= D_PLATE) & (rs < R_DISK), 'PLATE', done)
        for k, (ex, ey) in enumerate(ENGINES):
            re = np.hypot(xn[:, 0]-ex, xn[:, 1]-ey)
            hitk = (done == '') & (re < A_ENV) & (xn[:, 2] >= Z_FRONT) & (xn[:, 2] <= 0.0)
            front = hitk & (x[:, 2] < Z_FRONT)
            done = np.where(front, 'ENGINE_FRONT', np.where(hitk, 'ENGINE_SIDE', done))
            hit_engine[act[hitk]] = k
        sp_ = (done == '') & (rs < R_SPINE) & (xn[:, 2] > Z_S+5) & (xn[:, 2] < Z_FRONT)
        done = np.where(sp_, 'SPINE', done)
        done = np.where((done == '') & (xn[:, 2] > 60.0), 'AFT', done)
        done = np.where((done == '') & (np.hypot(rs, xn[:, 2]-Z_FRONT) > 400.0), 'RADIAL', done)
        # back into the ship's side or bow region outside the mirror (forward of the stern plane, outside r 45 m)
        done = np.where((done == '') & (xn[:, 2] < Z_S-1.0) & (rs >= R_DISK), 'SHIP_SIDE_REGION', done)
        done = np.where((done == '') & (bounce[act] > max_bounce), 'MULTI_BOUNCE', done)
        fin = done != ''
        if np.any(fin):
            idx = act[fin]; status[idx] = done[fin]; xf[idx] = xn[fin]; uf[idx] = un[fin]
            act = act[~fin]
    status[act] = 'TRAPPED'; xf[act] = X[act]; uf[act] = U[act]
    return dict(status=status, bounce=bounce, xf=xf, uf=uf, hit_engine=hit_engine, first_out_u=first_out_u, got_out=got_out,
                steps=step+1, logS=logS, ncross=ncross)


def summarize(ion, res, ta):
    W = ion['W']; Wt = W.sum()
    st = res['status']
    frac = {s: float(W[st == s].sum()/Wt) for s in sorted(set(st))}
    aft = st == 'AFT'
    u = res['uf'][aft]; cosw = float(np.sum(W[aft]*u[:, 2]/np.linalg.norm(u, axis=1))/max(W[aft].sum(), 1e-30))
    eng = {k: float(W[res['hit_engine'] == k].sum()/Wt) for k in range(4)}
    b = {int(k): float(W[res['bounce'] == k].sum()/Wt) for k in sorted(set(res['bounce'].tolist()))}
    # reflected direction straight out of the mirror (before the engine field acts)
    go = res['got_out']; fo = res['first_out_u'][go]
    cos_out = float(np.sum(W[go]*fo[:, 2]/np.linalg.norm(fo, axis=1))/max(W[go].sum(), 1e-30))
    # incidence angle on the local facet
    P = ion['P_land']; dots = P[:, 0, None]*NQ[:, 0]+P[:, 1, None]*NQ[:, 1]; q = np.argmax(dots, 1)
    ca = 1/math.sqrt(1+ta*ta); sa = ta*ca
    nvec = np.stack([sa*NQ[q, 0], sa*NQ[q, 1], -ca*np.ones(len(q))], 1)
    uin = ion['U']/np.linalg.norm(ion['U'], axis=1)[:, None]
    inc = np.degrees(np.arccos(np.clip(np.sum(uin*nvec, 1), -1, 1)))
    dseam = np.abs(np.abs(P[:, 0])-np.abs(P[:, 1]))/math.sqrt(2)
    # grid survival along the 3D path (first pass, angle-dependent opacity) vs the 1D model (fixed opacity per crossing)
    surv = {}
    for o, ls in res['logS'].items():
        surv[f'{o:g}'] = dict(survive_3d=float(np.sum(W*np.exp(ls))/Wt),
                              survive_1d_same_crossings=float(np.sum(W*(1-o)**res['ncross'])/Wt))
    return dict(grid_survival=surv, mean_crossings=float(np.sum(W*res['ncross'])/Wt), fractions=frac, aft_cos=cosw, cos_out_of_mirror=cos_out, engine_strikes=eng, bounces=b,
                incidence_deg=dict(p50=float(np.percentile(inc, 50)), p90=float(np.percentile(inc, 90)), p99=float(np.percentile(inc, 99)),
                                   mean_tan=float(np.mean(np.tan(np.radians(inc))))),
                near_seam_1m=float(W[dseam < 1.0].sum()/Wt), near_rim_2m=float(W[np.hypot(P[:, 0], P[:, 1]) > R_DISK-2].sum()/Wt),
                steps=res['steps'])


def job(a):
    name, alpha, use_B, use_psi, ion, g = a
    ta = math.tan(math.radians(alpha))
    t = time.time()
    res = push(ion, ta, g if use_psi else None, use_B=use_B)
    s = summarize(ion, res, ta); s['seconds'] = time.time()-t; s['name'] = name; s['alpha'] = alpha; s['B'] = use_B; s['psi'] = use_psi
    return s


def main():
    out = dict(meta=dict(Z_S=Z_S, Z_FRONT=Z_FRONT, R_DISK=R_DISK, A_ENV=A_ENV, R_SPINE=R_SPINE, layers_d=LAYERS_D.tolist(),
                         layers_V=LAYERS_V.tolist()))
    t = time.time()
    ion = incoming()
    out['incoming'] = dict(n=len(ion['X']), landed_share=ion['landed_share'])
    print(f"incoming sample: {len(ion['X'])} ions (energy-weighted), landed share of the pulse {ion['landed_share']:.4f} "
          f"({time.time()-t:.0f} s)", flush=True)
    psis = {}
    alphas = (10.0, -10.0, -20.0, -30.0)
    for alpha in alphas:
        g = solve_psi(math.tan(math.radians(alpha)))
        psis[alpha] = g
        out.setdefault('psi', {})[f'{alpha:g}'] = g['stats']
        print(f"3D field alpha {alpha:g} deg: {g['stats']}", flush=True)
    jobs = [(f'alpha{a:g}_B', a, True, True, ion, psis[a]) for a in alphas]
    jobs += [(f'alpha{a:g}_noB', a, False, True, ion, psis[a]) for a in (10.0, -10.0)]
    with Pool(4) as pool:
        for s in pool.imap(job, jobs):
            out.setdefault('cases', {})[s['name']] = s
            fr = s['fractions']
            print(f"{s['name']:18s} " + ', '.join(f'{k} {v:.3f}' for k, v in fr.items()) +
                  f" | aft cos {s['aft_cos']:.3f}, out of mirror cos {s['cos_out_of_mirror']:.3f} | engines "
                  + ' '.join(f'{v:.3f}' for v in s['engine_strikes'].values()) + f" | bounces {s['bounces']} | incidence "
                  f"p50 {s['incidence_deg']['p50']:.1f} p90 {s['incidence_deg']['p90']:.1f} deg, mean tan {s['incidence_deg']['mean_tan']:.3f}"
                  f" | survival o0.005 3D {s['grid_survival']['0.005']['survive_3d']:.3f} vs 1D {s['grid_survival']['0.005']['survive_1d_same_crossings']:.3f}, o0.001 3D {s['grid_survival']['0.001']['survive_3d']:.3f} vs {s['grid_survival']['0.001']['survive_1d_same_crossings']:.3f}"
                  f" | near seam {s['near_seam_1m']:.3f}, rim {s['near_rim_2m']:.3f} | {s['seconds']:.0f} s", flush=True)
    return out


if __name__ == '__main__':
    import contextlib, io
    buf = io.StringIO()
    class Tee(io.TextIOBase):
        def write(self, s):
            sys.__stdout__.write(s); buf.write(s); return len(s)
    with contextlib.redirect_stdout(Tee()):
        o = main()
    (HERE/'traj3d.json').write_text(json.dumps(o, indent=1, default=float)+'\n'); (HERE/'traj3d.log').write_text(buf.getvalue())
