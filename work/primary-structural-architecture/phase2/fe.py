"""PSA Phase II 3D frame finite-element solver (study code; numpy + scipy). Not imported by src/, tests/ or CI.

Capabilities, each verified in bench.py against a closed form:
  * Euler-Bernoulli 3D beam (12 DOF) and axial-only truss elements; rigid links; 6-DOF connector springs for joint compliance.
  * Linear static: supported or free-free with inertia relief (rigid-body acceleration from the applied loads, d'Alembert loads
    from the consistent mass matrix, a statically determinate 3-2-1 support whose reactions must vanish: the equilibrium check).
  * Thermal loads (uniform and through-section gradient) as equivalent nodal forces; thermal stresses recovered in the element.
  * Consistent mass matrix and lumped point masses; modal analysis (rigid-body modes separated from elastic modes).
  * Geometric (initial-stress) stiffness: linear buckling eigenvalues for fixed-direction (conservative) loads.
  * Follower-load stiffness (non-symmetric): divergence and flutter of nonconservative thrust by the eigenvalues of
    M q'' + (K + lam (Kg + Kf)) q = 0 as lam grows (Beck and Beal problems as benchmarks).
  * Element removal for failure cases.

Limits (stated, not hidden): small displacements and linear material; no shear deformation (members are slender, L/r > 20 checked
in the model); no contact or progressive plasticity (progressive collapse is a sequence of linear solves with members removed when
they exceed their capacity); anisotropy is represented through effective section properties only.
"""
import math
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla
import scipy.linalg as sla


def tube(r_out, t):
    ri = max(r_out - t, 0.0)
    A = math.pi*(r_out**2 - ri**2); I = math.pi/4*(r_out**4 - ri**4)
    return dict(A=A, Iy=I, Iz=I, J=2*I, c=r_out, r=r_out, t=t)


def box(b, h, t):
    A = b*h - (b-2*t)*(h-2*t)
    Iy = (b*h**3 - (b-2*t)*(h-2*t)**3)/12; Iz = (h*b**3 - (h-2*t)*(b-2*t)**3)/12
    J = 2*t*((b-t)*(h-t))**2/((b-t)+(h-t))
    return dict(A=A, Iy=Iy, Iz=Iz, J=J, c=max(b, h)/2, b=b, h=h, t=t)


class Model:
    def __init__(self):
        self.X = []                 # node coordinates
        self.el = []                # element dicts
        self.pm = {}                # node -> point mass (kg)
        self.pi = {}                # node -> 3x3 rotary inertia about the node (kg m2), global axes (remote rigid bodies, Phase III)
        self.loads = {}             # node -> 6 force vector
        self.follow = {}            # node -> (force vector, follower?) for nonconservative thrust
        self.fixed = {}             # node -> list of fixed dofs

    # ---------- building --------------------------------------------------------------------------------------------------------
    def node(self, p):
        self.X.append(np.array(p, float)); return len(self.X)-1

    def beam(self, a, b, sec, mat, kind='beam', group='', ref=None, dT=0.0, dTy=0.0, dTz=0.0):
        self.el.append(dict(a=a, b=b, sec=sec, mat=mat, kind=kind, group=group, ref=ref, on=True, dT=dT, dTy=dTy, dTz=dTz))
        return len(self.el)-1

    def truss(self, a, b, sec, mat, group=''):
        return self.beam(a, b, sec, mat, kind='truss', group=group)

    def spring(self, a, b, k6, group='joint'):
        """Connector between two (usually coincident) nodes with six stiffnesses (N/m, N m/rad) in global axes."""
        self.el.append(dict(a=a, b=b, k6=list(k6), kind='spring', group=group, on=True, sec=None, mat=None))
        return len(self.el)-1

    def mass(self, n, m):
        self.pm[n] = self.pm.get(n, 0.0)+m

    def inertia(self, n, J):
        J0 = self.pi.get(n); self.pi[n] = np.array(J, float) if J0 is None else J0+np.array(J, float)

    def load(self, n, F=(0, 0, 0), M=(0, 0, 0)):
        v = self.loads.setdefault(n, np.zeros(6)); v[:3] += F; v[3:] += M

    def thrust(self, n, F, follower=True):
        """A thrust force at node n: applied as a load and, when follower=True, rotating with the node (nonconservative)."""
        self.load(n, F); self.follow[n] = (np.array(F, float), follower)

    def fix(self, n, dofs=range(6)):
        self.fixed.setdefault(n, []); self.fixed[n] = sorted(set(self.fixed[n]) | set(dofs))

    @property
    def ndof(self):
        return 6*len(self.X)

    # ---------- element matrices ------------------------------------------------------------------------------------------------
    def frame(self, e):
        a, b = self.X[e['a']], self.X[e['b']]
        d = b-a; L = float(np.linalg.norm(d)); ex = d/L
        ref = np.array(e['ref']) if e.get('ref') is not None else (np.array([0., 0., 1.]) if abs(ex[2]) < 0.9 else np.array([0., 1., 0.]))
        ey = np.cross(ref, ex); ey /= np.linalg.norm(ey); ez = np.cross(ex, ey)
        R = np.vstack([ex, ey, ez])
        T = np.zeros((12, 12))
        for i in range(4):
            T[3*i:3*i+3, 3*i:3*i+3] = R
        return L, R, T

    @staticmethod
    def k_local(L, sec, mat, kind):
        E, G = mat['E'], mat['G']; A = sec['A']
        k = np.zeros((12, 12))
        ea = E*A/L
        k[0, 0] = k[6, 6] = ea; k[0, 6] = k[6, 0] = -ea
        if kind == 'truss':
            return k
        Iy, Iz, J = sec['Iy'], sec['Iz'], sec['J']
        gj = G*J/L
        k[3, 3] = k[9, 9] = gj; k[3, 9] = k[9, 3] = -gj
        for (v, th, I, s) in ((1, 5, Iz, 1.0), (2, 4, Iy, -1.0)):
            a12, a6, a4, a2 = 12*E*I/L**3, 6*E*I/L**2, 4*E*I/L, 2*E*I/L
            idx = [(v, v, a12), (v+6, v+6, a12), (v, v+6, -a12), (v, th, s*a6), (v, th+6, s*a6), (v+6, th, -s*a6), (v+6, th+6, -s*a6),
                   (th, th, a4), (th+6, th+6, a4), (th, th+6, a2)]
            for i, j, val in idx:
                k[i, j] += val
                if i != j:
                    k[j, i] += val
        return k

    @staticmethod
    def kg_local(L, N):
        """Geometric stiffness of a beam with axial force N (tension positive), lateral DOFs only (standard cubic shape functions)."""
        k = np.zeros((12, 12)); c = N/(30*L)
        for (v, th, s) in ((1, 5, 1.0), (2, 4, -1.0)):
            vals = [(v, v, 36), (v+6, v+6, 36), (v, v+6, -36), (v, th, s*3*L), (v, th+6, s*3*L), (v+6, th, -s*3*L), (v+6, th+6, -s*3*L),
                    (th, th, 4*L*L), (th+6, th+6, 4*L*L), (th, th+6, -L*L)]
            for i, j, val in vals:
                k[i, j] += c*val
                if i != j:
                    k[j, i] += c*val
        return k

    @staticmethod
    def m_local(L, sec, mat):
        m = mat['rho']*sec['A']*L
        M = np.zeros((12, 12))
        for i, j in ((0, 6),):
            M[i, i] = M[j, j] = m/3; M[i, j] = M[j, i] = m/6
        Jp = (sec.get('Iy', 0)+sec.get('Iz', 0))/max(sec['A'], 1e-12)
        M[3, 3] = M[9, 9] = m*Jp/3; M[3, 9] = M[9, 3] = m*Jp/6
        c = m/420
        for (v, th, s) in ((1, 5, 1.0), (2, 4, -1.0)):
            vals = [(v, v, 156), (v+6, v+6, 156), (v, v+6, 54), (v, th, s*22*L), (v, th+6, -s*13*L), (v+6, th, s*13*L), (v+6, th+6, -s*22*L),
                    (th, th, 4*L*L), (th+6, th+6, 4*L*L), (th, th+6, -3*L*L)]
            for i, j, val in vals:
                M[i, j] += c*val
                if i != j:
                    M[j, i] += c*val
        return M

    def _dofs(self, e):
        return np.r_[6*e['a']:6*e['a']+6, 6*e['b']:6*e['b']+6]

    def assemble(self, which='K', N=None):
        rows, cols, vals = [], [], []
        for i, e in enumerate(self.el):
            if not e['on']:
                continue
            d = self._dofs(e)
            if e['kind'] == 'spring':
                if which != 'K':
                    continue
                k = np.zeros((12, 12))
                for j, kk in enumerate(e['k6']):
                    k[j, j] = k[j+6, j+6] = kk; k[j, j+6] = k[j+6, j] = -kk
                g = k
            else:
                L, R, T = self.frame(e)
                if which == 'K':
                    kl = self.k_local(L, e['sec'], e['mat'], e['kind'])
                elif which == 'M':
                    kl = self.m_local(L, e['sec'], e['mat']) if e['kind'] != 'rigid' else np.zeros((12, 12))
                elif which == 'G':
                    if N is None:
                        kl = np.zeros((12, 12))
                    elif e['kind'] == 'truss':
                        kl = np.zeros((12, 12)); c = N[i]/L
                        for j in (1, 2):
                            kl[j, j] = kl[j+6, j+6] = c; kl[j, j+6] = kl[j+6, j] = -c
                    else:
                        kl = self.kg_local(L, N[i])
                g = T.T @ kl @ T
            r, c = np.meshgrid(d, d, indexing='ij')
            rows.append(r.ravel()); cols.append(c.ravel()); vals.append(g.ravel())
        n = self.ndof
        Kx = sp.coo_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(n, n)).tocsr() if rows else sp.csr_matrix((n, n))
        if which == 'K':
            # nodes reached only by trusses or springs have no rotational stiffness: a tiny ground spring removes the null space
            d = Kx.diagonal(); z = np.where(np.abs(d) < 1e-12)[0]
            if len(z):
                Kx = Kx + sp.coo_matrix((np.full(len(z), 1e-3*max(1.0, np.abs(d).max()*1e-12)), (z, z)), shape=(n, n)).tocsr()
        if which == 'M':
            d = Kx.diagonal(); z = np.where(np.abs(d) < 1e-15)[0]
            if len(z):
                Kx = Kx + sp.coo_matrix((np.full(len(z), 1e-6), (z, z)), shape=(n, n)).tocsr()
        if which == 'M' and self.pm:
            d = np.zeros(n)
            for nd, m in self.pm.items():
                d[6*nd:6*nd+3] += m
            Kx = Kx + sp.diags(d)
        if which == 'M' and self.pi:
            rows, cols, vals = [], [], []
            for nd, J in self.pi.items():
                for a in range(3):
                    for c in range(3):
                        if J[a][c]:
                            rows.append(6*nd+3+a); cols.append(6*nd+3+c); vals.append(J[a][c])
            Kx = Kx + sp.coo_matrix((vals, (rows, cols)), shape=(n, n)).tocsr()
        return Kx

    def follower_stiffness(self):
        """Load-stiffness of follower forces: the force rotates with the node, dF = theta x F, so dF = -[F]x theta (non-symmetric)."""
        n = self.ndof; rows, cols, vals = [], [], []
        for nd, (F, fol) in self.follow.items():
            if not fol:
                continue
            Fx = np.array([[0, -F[2], F[1]], [F[2], 0, -F[0]], [-F[1], F[0], 0]])
            # dF = theta x F = -F x theta = -[F]x theta  -> stiffness contribution K_L = +[F]x (moves to the left side as -dF)
            for i in range(3):
                for j in range(3):
                    if Fx[i, j] != 0:
                        rows.append(6*nd+i); cols.append(6*nd+3+j); vals.append(Fx[i, j])
        return sp.coo_matrix((vals, (rows, cols)), shape=(n, n)).tocsr()

    def load_vector(self, extra=None):
        F = np.zeros(self.ndof)
        for nd, v in self.loads.items():
            F[6*nd:6*nd+6] += v
        if extra is not None:
            F += extra
        return F

    def thermal_vector(self):
        F = np.zeros(self.ndof)
        for e in self.el:
            if not e['on'] or e['kind'] == 'spring' or not (e.get('dT') or e.get('dTy') or e.get('dTz')):
                continue
            L, R, T = self.frame(e); m, s = e['mat'], e['sec']
            fl = np.zeros(12)
            P = m['E']*s['A']*m['alpha']*e['dT']
            fl[0], fl[6] = -P, P
            if e['kind'] != 'truss':
                # gradient dTy across local y (depth 2c): curvature alpha*dTy/(2c) -> fixed-end moment E Iz kappa about local z
                for (dTg, I, th, sgn) in ((e.get('dTy', 0.0), s['Iz'], 5, 1.0), (e.get('dTz', 0.0), s['Iy'], 4, -1.0)):
                    if dTg:
                        Mth = m['E']*I*m['alpha']*dTg/(2*s['c'])
                        fl[th] += -sgn*Mth; fl[th+6] += sgn*Mth
            F[self._dofs(e)] += T.T @ fl
        return F

    # ---------- solution --------------------------------------------------------------------------------------------------------
    def free_mask(self):
        m = np.ones(self.ndof, bool)
        for nd, ds in self.fixed.items():
            for d in ds:
                m[6*nd+d] = False
        return m

    def rigid_modes(self, M=None):
        """Six rigid-body modes about the mass centre (translations and small rotations), columns of an ndof x 6 matrix."""
        Xs = np.array(self.X); M = self.assemble('M') if M is None else M; diag = M.diagonal()
        mt = np.array([diag[6*i] for i in range(len(self.X))])
        c = (Xs*mt[:, None]).sum(0)/max(mt.sum(), 1e-9)
        Phi = np.zeros((self.ndof, 6))
        for i, p in enumerate(Xs):
            r = p-c
            for k in range(3):
                Phi[6*i+k, k] = 1.0
            # rotation about axis k: u = e_k x r, theta = e_k
            for k in range(3):
                ek = np.zeros(3); ek[k] = 1.0
                Phi[6*i:6*i+3, 3+k] = np.cross(ek, r); Phi[6*i+3+k, 3+k] = 1.0
        return Phi, c

    def solve_static(self, F=None, inertia_relief=False, thermal=False, K=None, M=None, cache=None):
        """cache: a dict kept by the caller while K and M are unchanged; it stores the factorised free-free system."""
        K = self.assemble('K') if K is None else K; M = self.assemble('M') if M is None else M
        Fv = self.load_vector() if F is None else F.copy()
        if thermal:
            Fv = Fv + self.thermal_vector()
        accel = None
        if inertia_relief:
            if cache is not None and 'Phi' in cache:
                Phi, c = cache['Phi']
            else:
                Phi, c = self.rigid_modes(M)
                if cache is not None:
                    cache['Phi'] = (Phi, c)
            Mr = Phi.T @ (M @ Phi)
            q = np.linalg.solve(Mr, Phi.T @ Fv)           # rigid-body acceleration (3 linear, 3 angular about the mass centre)
            Fv = Fv - M @ (Phi @ q)
            accel = dict(lin=q[:3], ang=q[3:], cm=c)
        free = self.free_mask()
        u = np.zeros(self.ndof)
        if inertia_relief and not self.fixed:
            # free-free: deformation measured from the mean rigid motion, constraint Phi^T M u = 0 by Lagrange multipliers;
            # the multipliers equal the residual unbalanced load and must vanish (equilibrium check)
            if cache is not None and 'lu' in cache:
                lu = cache['lu']
            else:
                C = sp.csr_matrix(M @ Phi)
                lu = spla.splu(sp.bmat([[K, C], [C.T, None]]).tocsc())
                if cache is not None:
                    cache['lu'] = lu
            sol = lu.solve(np.r_[Fv, np.zeros(6)])
            u = sol[:self.ndof]; accel['multiplier_residual'] = float(np.abs(sol[self.ndof:]).max())
        else:
            Kff = K[free][:, free]
            u[free] = spla.spsolve(Kff.tocsc(), Fv[free])
        R = K @ u - Fv
        react = {nd: R[6*nd:6*nd+6] for nd in self.fixed}
        return dict(u=u, reactions=react, accel=accel, F=Fv, residual_free=float(np.abs(R[free]).max()) if free.any() else 0.0)

    def element_forces(self, u):
        out = []
        for e in self.el:
            if not e['on'] or e['kind'] == 'spring':
                out.append(None); continue
            L, R, T = self.frame(e)
            ul = T @ u[self._dofs(e)]
            f = self.k_local(L, e['sec'], e['mat'], e['kind']) @ ul
            if e.get('dT') or e.get('dTy') or e.get('dTz'):
                m, s = e['mat'], e['sec']; P = m['E']*s['A']*m['alpha']*e['dT']
                f[0] += P; f[6] -= P
                if e['kind'] != 'truss':
                    for (dTg, I, th, sgn) in ((e.get('dTy', 0.0), s['Iz'], 5, 1.0), (e.get('dTz', 0.0), s['Iy'], 4, -1.0)):
                        if dTg:
                            Mth = m['E']*I*m['alpha']*dTg/(2*s['c']); f[th] += sgn*Mth; f[th+6] -= sgn*Mth
            out.append(dict(L=L, N=f[6], Vy=f[7], Vz=f[8], T=f[9], My=max(abs(f[4]), abs(f[10])), Mz=max(abs(f[5]), abs(f[11]))))
        return out

    def modes(self, k=12, sigma=None):
        K = self.assemble('K'); M = self.assemble('M'); free = self.free_mask()
        Kf, Mf = K[free][:, free].tocsc(), M[free][:, free].tocsc()
        n = Kf.shape[0]
        if n <= 1500:
            w2, V = sla.eigh(Kf.toarray(), Mf.toarray())
            w2, V = w2[:k], V[:, :k]
        else:
            s = -1.0 if sigma is None else sigma
            w2, V = spla.eigsh(Kf, M=Mf, k=k, sigma=s, which='LM')
            o = np.argsort(w2); w2, V = w2[o], V[:, o]
        f = np.sqrt(np.clip(w2, 0, None))/(2*math.pi)
        Vfull = np.zeros((self.ndof, V.shape[1])); Vfull[free] = V
        return f, Vfull, w2

    def buckling(self, N, k=6):
        """Conservative linear buckling: (K + lam Kg(N)) phi = 0; returns the smallest positive load factors."""
        K = self.assemble('K'); G = self.assemble('G', N=N); free = self.free_mask()
        Kf, Gf = K[free][:, free].toarray(), G[free][:, free].toarray()
        lam = sla.eigvals(Kf, -Gf)
        lam = np.real(lam[np.isfinite(lam) & (np.abs(np.imag(lam)) < 1e-6*np.abs(lam)+1e-9)])
        return np.sort(lam[lam > 1e-9])[:k]

    def stability_sweep(self, N, lams, follower=True, nmodes=10):
        """Eigenvalues of M q'' + (K + lam (Kg + Kf)) q = 0 for each load factor lam: the first lam where an eigenvalue
        omega^2 turns complex (flutter) or crosses zero (divergence) bounds the nonconservative stability."""
        K = self.assemble('K'); M = self.assemble('M'); G = self.assemble('G', N=N); Fk = self.follower_stiffness() if follower else 0*K
        free = self.free_mask()
        Kf, Mf, Gf = (A[free][:, free].toarray() for A in (K, M, G))
        Lf = Fk[free][:, free].toarray() if follower else 0*Kf
        out = []
        for lam in lams:
            A = Kf + lam*(Gf + Lf)
            w2 = sla.eigvals(A, Mf)
            w2 = w2[np.isfinite(w2)]
            w2 = w2[np.argsort(np.abs(w2))]
            el = w2[np.abs(w2) > 1e-6*max(1.0, np.abs(w2).max())][:nmodes]
            out.append(dict(lam=float(lam), min_real=float(np.min(np.real(el))) if len(el) else float('nan'),
                            max_imag=float(np.max(np.abs(np.imag(el)))) if len(el) else 0.0, w2=el))
        return out


def _status(w2, thr):
    el = w2[np.abs(w2) > thr]
    if not len(el):
        return 'stable'
    if np.any(np.abs(np.imag(el)) > 1e-4*np.abs(el)):
        return 'flutter'
    if np.any(np.real(el) < -thr):
        return 'divergence'
    return 'stable'


def critical(model, N, lo, hi, follower=True, n=40, iters=30):
    """First load factor in [lo, hi] at which an elastic eigenvalue becomes complex (flutter) or negative (divergence); rigid-body
    eigenvalues (|omega^2| below 1e-3 of the first elastic value at zero load) are excluded. Coarse sweep, then bisection."""
    K = model.assemble('K'); M = model.assemble('M'); G = model.assemble('G', N=N)
    Fk = model.follower_stiffness() if follower else None
    free = model.free_mask()
    Kf, Mf, Gf = (A[free][:, free].toarray() for A in (K, M, G))
    Lf = Fk[free][:, free].toarray() if follower else 0*Kf
    w0 = np.real(sla.eigvals(Kf, Mf)); w0 = np.sort(np.abs(w0[np.isfinite(w0)]))
    thr = 1e-3*w0[w0 > 1e-6*w0.max()][0]
    P = None
    if not model.fixed:
        Phi, _ = model.rigid_modes(); P = Phi[free]; MP = Mf @ P; PMP = np.linalg.inv(P.T @ MP)
    def st(lam):
        w2, V = sla.eig(Kf+lam*(Gf+Lf), Mf); ok = np.isfinite(w2); w2, V = w2[ok], V[:, ok]
        if P is not None:
            # exclude eigenvectors that are (almost) pure rigid-body motion: mass-weighted projection > 0.99. Under follower thrust the
            # rigid rotation couples to lateral drift (negative omega^2 that grows with load): a trajectory, not a structural, mode
            proj = MP.T @ V; num = np.real(np.einsum('ij,ij->j', np.conj(proj), PMP @ proj)); den = np.real(np.einsum('ij,ij->j', np.conj(V), Mf @ V))
            w2 = w2[num/den < 0.99]
        return _status(w2, thr)
    grid = np.linspace(lo, hi, n+1); prev = grid[0]
    if st(prev) != 'stable':
        return dict(lam=None, kind='unstable_at_lo')
    for g in grid[1:]:
        k = st(g)
        if k != 'stable':
            a, b = prev, g
            for _ in range(iters):
                c = 0.5*(a+b)
                if st(c) == 'stable':
                    a = c
                else:
                    b = c
            return dict(lam=float(b), kind=st(b))
        prev = g
    return dict(lam=None, kind='stable_to_hi')


def stress_util(f, sec, allow_t, allow_c):
    """Peak combined normal stress at the outer fibre over the allowable (tension or compression)."""
    if f is None:
        return 0.0
    sb = math.hypot(f['My']/sec['Iy'], f['Mz']/sec['Iz'])*sec['c'] if sec.get('Iy') else 0.0
    sa = f['N']/sec['A']
    return max((sa+sb)/allow_t if sa+sb > 0 else 0.0, (-(sa-sb))/allow_c if sa-sb < 0 else 0.0)
