"""Vertex 2.9: reduced axisymmetric hybrid model of a pulsed plasma in a magnetic nozzle (research, not canon; numpy + scipy + numba).

Model (what it is and is not):
- Ions are kinetic: macro-particle rings in (r, z) carrying (v_r, v_theta, v_z), relativistic Boris push in E + v x B, per species
  (p, alpha, D, He-3 at the operating exhaust speed, the 2.8 species set).
- Electrons are a massless, quasi-neutral fluid (n_e = sum Z n_i): generalized Ohm's law E = -u_e x B - grad(p_e)/(e n_e) + eta J with
  u_e = (J_i - J)/(e n_e). The Hall term enters the poloidal E that pushes the ions (it carries J x B to them).
- The magnetic field is poloidal: psi = r A_theta, B_r = -(1/r) dpsi/dz, B_z = (1/r) dpsi/dr. Coil flux psi_c is the exact vacuum
  loop field; the plasma flux psi_p obeys d psi_p/dt + u_e . grad psi = (eta/mu0) Delta* psi_p (frozen in the electron fluid where the
  plasma is dense, relaxed to vacuum (Laplace) where n_e < n_c: eta_vac very large, solved implicitly). Delta* is symmetric after
  division by r, so each step is one sparse SPD solve.
- NOT included: the toroidal field B_theta that the Hall term generates (no whistler / Hall-quadrupole dynamics), electron inertia,
  radiation, collisions, 3D modes (flutes, Rayleigh-Taylor), coil current change during the pulse (superconducting flux conservation:
  dI/I ~ E_p/E_B). These are listed in the report as open items, not as results.
Frame: metres, seconds, +z aft; the coils of a candidate as in lab/studies/vertex-closure/vertex-2-8/nozzle.py; outer boundary psi_p = 0.
After a particle leaves the grid it is continued as a test particle in the exact coil field to a 150 m box (detachment and late
deflection), then classified AFT / FORWARD / RADIAL / COIL / TRAPPED.
"""
import math
import sys
import time
from pathlib import Path

import numpy as np
import numba as nb
import scipy.sparse as sp
import scipy.sparse.linalg as spl

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent/'vertex-2-8'))
import nozzle_core as NC  # noqa: E402

MU0 = NC.MU0; C = NC.C; QE = NC.E_CH


# ---------------------------------------------------------------- exact coil field for the test-particle continuation (numba)
@nb.njit(cache=True)
def _ellipke(m):
    if m > 1.0-1e-15:
        m = 1.0-1e-15
    a = 1.0; g = math.sqrt(1.0-m); s = 0.5*m; pw = 1.0
    for _ in range(40):
        an = 0.5*(a+g); gn = math.sqrt(a*g); c = 0.5*(a-g)
        a = an; g = gn; s += pw*c*c; pw *= 2.0
        if abs(c) < 1e-15:
            break
    K = math.pi/(2.0*a)
    return K, K*(1.0-s)


@nb.njit(cache=True)
def coil_B(cI, cR, cz, r, z):
    Br = 0.0; Bz = 0.0
    for k in range(cI.shape[0]):
        I = cI[k]; R = cR[k]; zz = z-cz[k]
        if r < 1e-9*R:
            Bz += MU0*I*R*R/(2.0*(R*R+zz*zz)**1.5)
            continue
        a2 = R*R+r*r+zz*zz-2*R*r; b2 = R*R+r*r+zz*zz+2*R*r
        if a2 < 1e-12*R*R:
            a2 = 1e-12*R*R
        K, E = _ellipke(1.0-a2/b2)
        bb = math.sqrt(b2); C0 = MU0*I/math.pi
        Bz += C0/(2*a2*bb)*((R*R-r*r-zz*zz)*E+a2*K)
        Br += C0*zz/(2*a2*bb*r)*((R*R+r*r+zz*zz)*E-a2*K)
    return Br, Bz


@nb.njit(cache=True)
def _loop_psi(R, zc, r, z):
    """psi = r A_phi of a unit-current loop (radius R at zc) at (r, z)."""
    if r < 1e-9:
        return 0.0
    zz = z-zc
    b2 = R*R+r*r+zz*zz+2*R*r
    k2 = 4*R*r/b2
    K, E = _ellipke(k2)
    k = math.sqrt(k2)
    return r*MU0/(math.pi*k)*math.sqrt(R/r)*((1-k2/2)*K-E)


@nb.njit(cache=True, parallel=True)
def boundary_psi(JdA, Rs, Zs, rb, zb):
    """Free-space flux on the boundary nodes (rb, zb) from ring currents JdA at (Rs, Zs)."""
    out = np.zeros(rb.shape[0])
    for b in nb.prange(rb.shape[0]):
        s = 0.0
        for c in range(Rs.shape[0]):
            s += JdA[c]*_loop_psi(Rs[c], Zs[c], rb[b], zb[b])
        out[b] = s
    return out


@nb.njit(cache=True)
def _on_body(cR, cz, ca, cf, r, z):
    for k in range(cR.shape[0]):
        if (r-cR[k])**2+(z-cz[k])**2 < ca[k]**2:
            return k
        if abs(z-cz[k]) < ca[k] and r > cR[k] and r < cR[k]+cf[k]:
            return k
    return -1


@nb.njit(cache=True)
def _boris(ur, ut, uz, Er, Et, Ez, Br, Bz, qm, dt):
    """Relativistic Boris on u = gamma v in the local (r, theta, z) frame (B_theta = 0)."""
    h = 0.5*qm*dt
    ur += h*Er; ut += h*Et; uz += h*Ez
    g = math.sqrt(1.0+(ur*ur+ut*ut+uz*uz)/(C*C))
    tr = h*Br/g; tz = h*Bz/g; t2 = tr*tr+tz*tz
    # u' = u + u x t  (t = (tr, 0, tz))
    pr = ur+(ut*tz); pt = ut+(uz*tr-ur*tz); pz = uz+(-ut*tr)
    sr = 2*tr/(1+t2); sz = 2*tz/(1+t2)
    ur = ur+(pt*sz); ut = ut+(pz*sr-pr*sz); uz = uz+(-pt*sr)
    ur += h*Er; ut += h*Et; uz += h*Ez
    return ur, ut, uz


@nb.njit(cache=True)
def _move(r, z, ur, ut, uz, dt):
    g = math.sqrt(1.0+(ur*ur+ut*ut+uz*uz)/(C*C))
    x = r+ur/g*dt; y = ut/g*dt; zn = z+uz/g*dt
    rn = math.sqrt(x*x+y*y)
    if rn > 0:
        c = x/rn; s = y/rn
        urn = ur*c+ut*s; utn = -ur*s+ut*c
    else:
        urn = ur; utn = ut
    return rn, zn, urn, utn


# ---------------------------------------------------------------- grid interpolation / deposition (numba)
@nb.njit(cache=True)
def _interp(F, r, z, dr, dz, z0):
    fi = r/dr; fj = (z-z0)/dz
    i = int(fi); j = int(fj)
    if i < 0 or j < 0 or i >= F.shape[0]-1 or j >= F.shape[1]-1:
        return 0.0
    a = fi-i; b = fj-j
    return (F[i, j]*(1-a)*(1-b)+F[i+1, j]*a*(1-b)+F[i, j+1]*(1-a)*b+F[i+1, j+1]*a*b)


@nb.njit(cache=True)
def push_grid(st, r, z, ur, ut, uz, qm, sp_, w, Er, Et, Ez, Br, Bz, dr, dz, z0, rmax, z1, dt, cR, cz, ca, cf, hitE, hitP, m_sp):
    """Push live particles one step on the grid fields; status 0 live, 1 left the grid, 2 struck a coil."""
    n = r.shape[0]
    for p in range(n):
        if st[p] != 0:
            continue
        er = _interp(Er, r[p], z[p], dr, dz, z0); et = _interp(Et, r[p], z[p], dr, dz, z0); ez = _interp(Ez, r[p], z[p], dr, dz, z0)
        br = _interp(Br, r[p], z[p], dr, dz, z0); bz = _interp(Bz, r[p], z[p], dr, dz, z0)
        a, b, c = _boris(ur[p], ut[p], uz[p], er, et, ez, br, bz, qm[sp_[p]], dt)
        rn, zn, urn, utn = _move(r[p], z[p], a, b, c, dt)
        r[p] = rn; z[p] = zn; ur[p] = urn; ut[p] = utn; uz[p] = c
        k = _on_body(cR, cz, ca, cf, rn, zn)
        if k >= 0:
            st[p] = 2
            g = math.sqrt(1.0+(urn*urn+utn*utn+c*c)/(C*C))
            hitE[k] += w[p]*(g-1.0)*m_sp[sp_[p]]*C*C
            hitP[k] += w[p]*m_sp[sp_[p]]*c
        elif rn >= rmax-dr or zn <= z0+dz or zn >= z1-dz:
            st[p] = 1


@nb.njit(cache=True)
def deposit(st, r, z, ur, ut, uz, sp_, w, Zs, ms, dr, dz, z0, Nr, Nz):
    """Charge density (e n_e), ion current (J_r, J_theta, J_z) and mass density on nodes, volume-weighted rings."""
    rho = np.zeros((Nr, Nz)); Jr = np.zeros((Nr, Nz)); Jt = np.zeros((Nr, Nz)); Jz = np.zeros((Nr, Nz)); rm = np.zeros((Nr, Nz))
    for p in range(r.shape[0]):
        if st[p] != 0:
            continue
        fi = r[p]/dr; fj = (z[p]-z0)/dz; i = int(fi); j = int(fj)
        if i < 0 or j < 0 or i >= Nr-1 or j >= Nz-1:
            continue
        a = fi-i; b = fj-j
        s = sp_[p]; g = math.sqrt(1.0+(ur[p]**2+ut[p]**2+uz[p]**2)/(C*C))
        q = w[p]*Zs[s]*QE; m = w[p]*ms[s]
        vr = ur[p]/g; vt = ut[p]/g; vz = uz[p]/g
        for (ii, jj, f) in ((i, j, (1-a)*(1-b)), (i+1, j, a*(1-b)), (i, j+1, (1-a)*b), (i+1, j+1, a*b)):
            rho[ii, jj] += q*f; Jr[ii, jj] += q*vr*f; Jt[ii, jj] += q*vt*f; Jz[ii, jj] += q*vz*f; rm[ii, jj] += m*f
    return rho, Jr, Jt, Jz, rm


@nb.njit(cache=True)
def continue_tp(st, r, z, ur, ut, uz, qm, sp_, cI, cR, cz, ca, cf, zb, box, ds, max_steps):
    """Test-particle continuation of particles that left the grid, in the exact vacuum coil field. Status: 1 -> 3 AFT, 4 FORWARD,
    5 RADIAL, 6 COIL, 7 TRAPPED (did not reach the box)."""
    for p in range(r.shape[0]):
        if st[p] != 1:
            continue
        rr = r[p]; zz = z[p]; a = ur[p]; b = ut[p]; c = uz[p]; done = 7
        for _ in range(max_steps):
            br, bz = coil_B(cI, cR, cz, rr, zz)
            g = math.sqrt(1.0+(a*a+b*b+c*c)/(C*C)); v = math.sqrt(a*a+b*b+c*c)/g
            Bm = math.sqrt(br*br+bz*bz)
            dt = ds/v
            if Bm > 0:
                dtc = 0.15*g/(abs(qm[sp_[p]])*Bm)
                if dtc < dt:
                    dt = dtc
            a, b, c = _boris(a, b, c, 0.0, 0.0, 0.0, br, bz, qm[sp_[p]], dt)
            rr, zz, a, b = _move(rr, zz, a, b, c, dt)
            if _on_body(cR, cz, ca, cf, rr, zz) >= 0:
                done = 6; break
            if zz-zb > box:
                done = 3; break
            if zz-zb < -box:
                done = 4; break
            if rr > box:
                done = 5; break
        st[p] = done; r[p] = rr; z[p] = zz; ur[p] = a; ut[p] = b; uz[p] = c


# ---------------------------------------------------------------- field solver
class Grid:
    def __init__(self, rmax, z0, z1, dx):
        self.dr = self.dz = dx; self.z0 = z0; self.z1 = z1; self.rmax = rmax
        self.Nr = int(round(rmax/dx))+1; self.Nz = int(round((z1-z0)/dx))+1
        self.r = np.arange(self.Nr)*dx; self.z = z0+np.arange(self.Nz)*dx
        self.R, self.Z = np.meshgrid(self.r, self.z, indexing='ij')
        V = 2*np.pi*self.r*dx*dx; V[0] = np.pi*(dx/2)**2*dx
        self.V = np.repeat(V[:, None], self.Nz, 1)
        # interior unknowns i = 1..Nr-2, j = 1..Nz-2
        self.ni = self.Nr-2; self.nj = self.Nz-2
        self.idx = lambda i, j: (i-1)*self.nj+(j-1)
        rows = []; cols = []; vals = []; diag = np.zeros(self.ni*self.nj)
        dr = dx; dz = dx
        for i in range(1, self.Nr-1):
            rp = (i+0.5)*dr; rm = (i-0.5)*dr; ri = i*dr
            for j in range(1, self.Nz-1):
                k = self.idx(i, j)
                cpp = 1/(rp*dr*dr); cmm = 1/(rm*dr*dr); czz = 1/(ri*dz*dz)
                diag[k] = cpp+cmm+2*czz
                if i+1 <= self.Nr-2:
                    rows.append(k); cols.append(self.idx(i+1, j)); vals.append(-cpp)
                if i-1 >= 1:
                    rows.append(k); cols.append(self.idx(i-1, j)); vals.append(-cmm)
                if j+1 <= self.Nz-2:
                    rows.append(k); cols.append(self.idx(i, j+1)); vals.append(-czz)
                if j-1 >= 1:
                    rows.append(k); cols.append(self.idx(i, j-1)); vals.append(-czz)
        self.Loff = sp.csc_matrix((vals, (rows, cols)), shape=(self.ni*self.nj,)*2)
        self.Ldiag = diag
        self.rin = self.R[1:-1, 1:-1].ravel()
        bm = np.zeros((self.Nr, self.Nz), bool); bm[-1, :] = True; bm[:, 0] = True; bm[:, -1] = True
        self.bmask = bm; self.rb = self.R[bm]; self.zb = self.Z[bm]

    def bc_vec(self, psib):
        """Right-hand-side contribution of boundary values psib (full grid, nonzero only on the boundary)."""
        dr = self.dr; dz = self.dz; out = np.zeros((self.ni, self.nj))
        r = self.r[1:-1, None]
        out[-1, :] += psib[-1, 1:-1]/((r[-1]+0.5*dr)*dr*dr)
        out[:, 0] += psib[1:-1, 0]/(r[:, 0]*dz*dz)
        out[:, -1] += psib[1:-1, -1]/(r[:, 0]*dz*dz)
        return out.ravel()

    def free_boundary_coarse(self, J, f=4):
        """As free_boundary, with the currents summed into f x f blocks at their current-weighted centroids (far boundary)."""
        Nr = (self.Nr//f)*f; Nz = (self.Nz//f)*f
        JdA = (J*self.dr*self.dz)[:Nr, :Nz].reshape(Nr//f, f, Nz//f, f)
        S = JdA.sum((1, 3)); A = np.abs(JdA).sum((1, 3))
        Rc = (np.abs(JdA)*self.R[:Nr, :Nz].reshape(Nr//f, f, Nz//f, f)).sum((1, 3))/np.maximum(A, 1e-300)
        Zc = (np.abs(JdA)*self.Z[:Nr, :Nz].reshape(Nr//f, f, Nz//f, f)).sum((1, 3))/np.maximum(A, 1e-300)
        sel = A > 1e-6*max(A.max(), 1e-300)
        psib = np.zeros((self.Nr, self.Nz))
        if sel.any():
            psib[self.bmask] = boundary_psi(S[sel], Rc[sel], Zc[sel], self.rb, self.zb)
        return psib

    def free_boundary(self, J):
        """psi on the outer boundary from the plasma current J (free space, Green's function)."""
        sel = np.abs(J) > 1e-6*max(np.abs(J).max(), 1e-300)
        psib = np.zeros((self.Nr, self.Nz))
        if sel.any():
            Jd = (J*self.dr*self.dz)[sel]
            psib[self.bmask] = boundary_psi(Jd, self.R[sel], self.Z[sel], self.rb, self.zb)
        return psib

    def lap_over_r(self, psi):
        """(1/r) Delta* psi on interior nodes (zero elsewhere)."""
        out = np.zeros_like(psi); dr = self.dr; dz = self.dz
        r = self.r[1:-1, None]; rp = r+0.5*dr; rm = r-0.5*dr
        out[1:-1, 1:-1] = ((psi[2:, 1:-1]-psi[1:-1, 1:-1])/rp-(psi[1:-1, 1:-1]-psi[:-2, 1:-1])/rm)/dr**2 + \
            (psi[1:-1, 2:]-2*psi[1:-1, 1:-1]+psi[1:-1, :-2])/(r*dz*dz)
        return out

    def solve(self, rhs_psi, Ddt, psib=None):
        """Solve (1/(r D dt)) psi - (1/r) Delta* psi = rhs_psi/(r D dt) on the interior; psi = psib (default 0) on the boundary."""
        dd = 1.0/(self.rin*Ddt[1:-1, 1:-1].ravel())
        A = self.Loff+sp.diags(self.Ldiag+dd, format='csc')
        b = rhs_psi[1:-1, 1:-1].ravel()*dd
        if psib is not None:
            b = b+self.bc_vec(psib)
        x = spl.splu(A).solve(b)
        out = np.zeros((self.Nr, self.Nz)) if psib is None else psib.copy(); out[1:-1, 1:-1] = x.reshape(self.ni, self.nj)
        return out

    def poisson(self, J, free=True):
        """psi from a prescribed J_theta: -(1/r) Delta* psi = mu0 J; boundary free-space (Green's function) or 0."""
        psib = self.free_boundary(J) if free else np.zeros((self.Nr, self.Nz))
        A = self.Loff+sp.diags(self.Ldiag, format='csc')
        x = spl.splu(A).solve(MU0*J[1:-1, 1:-1].ravel()+self.bc_vec(psib))
        out = psib.copy(); out[1:-1, 1:-1] = x.reshape(self.ni, self.nj)
        return out

    def solve_dirichlet(self, fixed_mask, fixed_val):
        """Laplace (Delta* psi = 0) with psi fixed on fixed_mask nodes (and 0 on the boundary)."""
        n = self.ni*self.nj; fm = fixed_mask[1:-1, 1:-1].ravel(); fv = fixed_val[1:-1, 1:-1].ravel()
        big = 1e30
        A = self.Loff+sp.diags(self.Ldiag+np.where(fm, big, 0.0), format='csc')
        b = np.where(fm, big*fv, 0.0)
        x = spl.splu(A).solve(b)
        out = np.zeros((self.Nr, self.Nz)); out[1:-1, 1:-1] = x.reshape(self.ni, self.nj)
        return out

    def B_of(self, psi):
        dr = self.dr; dz = self.dz
        Br = np.zeros_like(psi); Bz = np.zeros_like(psi)
        r = self.r[:, None]
        Br[1:, 1:-1] = -(psi[1:, 2:]-psi[1:, :-2])/(2*dz)/r[1:]
        Bz[1:-1, :] = (psi[2:, :]-psi[:-2, :])/(2*dr)/r[1:-1]
        Bz[0, :] = 2*psi[1, :]/dr**2
        Bz[-1, :] = Bz[-2, :]
        return Br, Bz


def smooth(F, passes=1):
    for _ in range(passes):
        G = F.copy()
        G[1:-1, :] = 0.25*F[:-2, :]+0.5*F[1:-1, :]+0.25*F[2:, :]
        H = G.copy()
        H[:, 1:-1] = 0.25*G[:, :-2]+0.5*G[:, 1:-1]+0.25*G[:, 2:]
        F = H
    return F


# ---------------------------------------------------------------- run

def _minmod(a, b):
    return np.where(a*b > 0, np.sign(a)*np.minimum(np.abs(a), np.abs(b)), 0.0)


def _grad_up2(f, u, dx, axis):
    """Second-order upwind derivative with a minmod limiter (monotone near the flux-pile-up front)."""
    D = np.diff(f, axis=axis)/dx  # D[i] = (f[i+1]-f[i])/dx
    pad = [(0, 0), (0, 0)]; pad[axis] = (1, 1)
    Dp = np.pad(D, pad, mode='edge')  # Dp[i] = backward difference at i (D[i-1]); Dp[i+1] = forward difference at i
    sl = [slice(None)]*2
    def take(a, b):
        sl2 = list(sl); sl2[axis] = slice(a, b); return Dp[tuple(sl2)]
    n = f.shape[axis]
    back = take(0, n); fwd = take(1, n+1)
    back2 = np.roll(back, 1, axis=axis); fwd2 = np.roll(fwd, -1, axis=axis)
    gm = back+0.5*_minmod(back-back2, fwd-back)
    gp = fwd-0.5*_minmod(fwd2-fwd, fwd-back)
    return np.where(u > 0, gm, gp)


def _adv2(psi, ur, uz, dx):
    return ur*_grad_up2(psi, ur, dx, 0)+uz*_grad_up2(psi, uz, dx, 1)

def run(coils, zb, Ep, species, n_part=200_000, dx=0.25, rmax=40.0, zlo=-30.0, zhi=60.0, r0=1.0, n_c=1e15, Te_keV=0.0,
        D_plasma=1e3, t_max=6e-6, seed=1, dt_force=None, box=150.0, verbose=False, uniform_B=None, record=False, tp_only=False, ship=None, boris=False, bnd_every=2, ideal_et=True, adv_order=2):
    """One pulse. Returns a dict of results. uniform_B: replace the coils by a uniform axial field (cavity benchmark)."""
    t0 = time.time()
    rng = np.random.default_rng(seed)
    g = Grid(rmax, zlo, zhi, dx)
    cI = np.array([c['I'] for c in coils], float); cR = np.array([c['R'] for c in coils], float)
    cz = np.array([c['z'] for c in coils], float); ca = np.array([c['a'] for c in coils], float); cf = np.array([c.get('fin', 0.0) for c in coils], float)
    if uniform_B is not None:
        psi_c = 0.5*uniform_B*g.R**2; Brc = np.zeros_like(psi_c); Bzc = np.full_like(psi_c, uniform_B)
        cI = np.zeros(0); cR = np.zeros(0); cz = np.zeros(0); ca = np.zeros(0); cf = np.zeros(0)
    else:
        Brc, Bzc, Ac = NC.field(coils, g.R, g.Z); psi_c = g.R*Ac
        cap = 30.0; Bm = np.hypot(Brc, Bzc); f = np.minimum(1.0, cap/np.maximum(Bm, 1e-30)); Brc = Brc*f; Bzc = Bzc*f
    # species: mass, charge, number share; energy per species from the set
    ms = np.array([s['m'] for s in species]); Zs = np.array([s['Z'] for s in species], float)
    nshare = np.array([s['n'] for s in species]); nshare = nshare/nshare.sum()
    Es = np.array([s['E'] for s in species])
    Eion_mean = float(np.sum(nshare*Es)); N_ions = Ep/Eion_mean
    spn = rng.choice(len(species), size=n_part, p=nshare).astype(np.int64)
    w = np.full(n_part, N_ions/n_part)
    # positions uniform in a sphere of radius r0 at (0, zb); isotropic directions
    u3 = rng.normal(size=(n_part, 3)); u3 /= np.linalg.norm(u3, axis=1)[:, None]; rad = r0*rng.random(n_part)**(1/3)
    x = u3*rad[:, None]
    d3 = rng.normal(size=(n_part, 3)); d3 /= np.linalg.norm(d3, axis=1)[:, None]
    gam = 1+Es[spn]/(ms[spn]*C*C); umag = C*np.sqrt(1-1/gam**2)*gam
    v3 = d3*umag[:, None]
    rp = np.hypot(x[:, 0], x[:, 1]); ph = np.arctan2(x[:, 1], x[:, 0])
    ur = v3[:, 0]*np.cos(ph)+v3[:, 1]*np.sin(ph); ut = -v3[:, 0]*np.sin(ph)+v3[:, 1]*np.cos(ph); uz = v3[:, 2].copy()
    r = rp.copy(); z = zb+x[:, 2]
    qm = Zs*QE/ms
    st = np.zeros(n_part, np.int64)
    p0z = np.sum(w*ms[spn]*uz); p0 = np.sum(w*ms[spn]*np.sqrt(ur**2+ut**2+uz**2)); E0 = np.sum(w*(gam-1)*ms[spn]*C*C)
    # initial plasma flux: the dense burn region excludes the field (psi_total = 0 inside r0)
    inside = np.hypot(g.R, g.Z-zb) <= r0
    psi_p = g.solve_dirichlet(inside, -psi_c)
    psib = np.zeros_like(psi_p)
    vmax = float(umag.max()/gam[np.argmax(umag)])
    dt = min(0.4*dx/vmax, 1.2e-9, 0.5*dx/C) if dt_force is None else dt_force
    c_lim = min(C, 0.5*dx/dt)
    hitE = np.zeros(max(len(cR), 1)); hitP = np.zeros(max(len(cR), 1))
    coil_imp = np.zeros(max(len(cR), 1))
    Ddt_vac = 1e4*dx*dx
    hist = []
    nsteps = int(t_max/dt); W0 = None; Wion = 0.0; Wfld = 0.0; Wcomp = np.zeros(4)
    for step in range(nsteps):
        if tp_only:
            break
        rho, Jir, Jit, Jiz, rm = deposit(st, r, z, ur, ut, uz, spn, w, Zs, ms, g.dr, g.dz, g.z0, g.Nr, g.Nz)
        rho /= g.V; Jir /= g.V; Jit /= g.V; Jiz /= g.V
        rho = smooth(rho); Jir = smooth(Jir); Jit = smooth(Jit); Jiz = smooth(Jiz); rm = smooth(rm)
        ne = rho/QE
        dense = ne >= n_c
        fw = np.clip((ne-n_c)/n_c, 0.0, 1.0)
        neff = np.maximum(ne, n_c)
        uer = np.where(dense, Jir/(QE*neff), 0.0)*fw; uez = np.where(dense, Jiz/(QE*neff), 0.0)*fw
        psi = psi_c+psi_p
        # upwind advection of total flux by the electron poloidal velocity
        if adv_order == 2:
            adv = _adv2(psi, uer, uez, dx)
        else:
            dpr_m = np.zeros_like(psi); dpr_p = np.zeros_like(psi); dpz_m = np.zeros_like(psi); dpz_p = np.zeros_like(psi)
            dpr_m[1:, :] = (psi[1:, :]-psi[:-1, :])/dx; dpr_p[:-1, :] = (psi[1:, :]-psi[:-1, :])/dx
            dpz_m[:, 1:] = (psi[:, 1:]-psi[:, :-1])/dx; dpz_p[:, :-1] = (psi[:, 1:]-psi[:, :-1])/dx
            adv = np.where(uer > 0, uer*dpr_m, uer*dpr_p)+np.where(uez > 0, uez*dpz_m, uez*dpz_p)
        rhs = psi_p-dt*adv
        Ddt = np.where(dense, D_plasma*dt, Ddt_vac)
        if step % bnd_every == 0 and step > 0:
            psib = g.free_boundary_coarse(Jt_last)
        psi_new = g.solve(rhs, Ddt, psib)
        Et = np.zeros_like(psi); Et[1:, :] = -(psi_new[1:, :]-psi_p[1:, :])/(g.R[1:, :]*dt)
        # energy-consistent coupling: ions feel the inductive E_theta only where the field is frozen into them (the same cells whose
        # advection moved the flux); outside, they are test particles in the instantaneous field and receive no work from it
        Et *= fw
        psi_p = psi_new
        Brp, Bzp = g.B_of(psi_p)
        Br = Brc+Brp; Bz = Bzc+Bzp
        Jt = np.zeros_like(psi); Jt[1:, :] = -g.lap_over_r(psi_p)[1:, :]/MU0
        Jt = smooth(Jt); Jt_last = Jt
        uet = np.where(dense, (Jit-Jt)/(QE*neff), 0.0)
        # Boris (displacement-current) correction: the J x B push is reduced by 1/(1 + vA^2/c_lim^2), c_lim = min(c, 0.5 dx/dt). It only
        # acts where the Alfven speed exceeds c_lim (tenuous plasma, where ions are close to test particles anyway); it keeps the explicit
        # ion-field coupling stable.
        vA2 = (Br**2+Bz**2)/(MU0*np.maximum(rm/g.V, 1e-30))
        fB = 1.0/(1.0+vA2/c_lim**2) if boris else 1.0
        uet_h = np.where(dense, -Jt/(QE*neff), 0.0)*fB+np.where(dense, Jit/(QE*neff), 0.0)
        uet = uet_h
        Er = -uet*Bz; Ez = uet*Br
        if ideal_et:
            # ion push uses the local ideal Ohm's law E_theta = ue_r B_z - ue_z B_r (ue_pol = ui_pol): the ion magnetization-current terms
            # J_ir E_r and J_itheta E_theta then cancel exactly, cell by cell, as they do analytically
            Et = np.where(dense, uer*Bz-uez*Br, 0.0)
        if Te_keV > 0:
            pe = ne*Te_keV*1e3*QE  # isothermal electrons (upper bound on the electron push)
            gr = np.zeros_like(pe); gz = np.zeros_like(pe)
            gr[1:-1, :] = (pe[2:, :]-pe[:-2, :])/(2*dx); gz[:, 1:-1] = (pe[:, 2:]-pe[:, :-2])/(2*dx)
            Er = Er-np.where(dense, gr/(QE*neff), 0.0); Ez = Ez-np.where(dense, gz/(QE*neff), 0.0)
        Er *= fw; Ez *= fw
        # reaction on the coils from the plasma field (fixed currents)
        for k in range(len(cR)):
            brp = float(_interp(Brp, cR[k], cz[k], g.dr, g.dz, g.z0))
            coil_imp[k] += -2*math.pi*cR[k]*cI[k]*brp*dt
        Wcomp += dt*np.array([np.sum(Jir*Er*g.V), np.sum(Jiz*Ez*g.V), np.sum(Jit*Et*g.V), np.sum(Jt*Bz*fw*g.V*(Jir/np.maximum(rho,1e-30)))])
        Wion += dt*float(np.sum((Jir*Er+Jit*Et+Jiz*Ez)*g.V)); Wfld += dt*float(np.sum(Jt*Et*g.V))
        push_grid(st, r, z, ur, ut, uz, qm, spn, w, Er, Et, Ez, Br, Bz, g.dr, g.dz, g.z0, g.rmax, g.z1, dt, cR, cz, ca, cf, hitE, hitP, ms)
        if step % 25 == 0 or step == nsteps-1:
            live = st == 0
            gl = np.sqrt(1+(ur**2+ut**2+uz**2)/C**2)
            KE = float(np.sum(w[live]*(gl[live]-1)*ms[spn[live]]*C*C))
            Wp = float(np.sum((Brp**2+Bzp**2)/(2*MU0)*g.V))
            if W0 is None:
                W0 = Wp
            out_E = float(np.sum(w[~live & (st != 2)]*(gl[~live & (st != 2)]-1)*ms[spn[~live & (st != 2)]]*C*C))
            pz_all = float(np.sum(w[st != 2]*ms[spn[st != 2]]*uz[st != 2]))+float(hitP.sum())
            # cavity radius: largest distance from the burn of a node with B_total < 0.3 B_coil
            Bt = np.hypot(Br, Bz); Bc = np.hypot(Brc, Bzc)
            cav = (Bt < 0.3*Bc) & (np.hypot(g.R, g.Z-zb) < 60)
            cavR = float(np.max(np.hypot(g.R, g.Z-zb)[cav])) if cav.any() else 0.0
            hist.append(dict(t=step*dt, live=float(live.mean()), KE=KE/E0, Wp=(Wp-W0)/E0, out=out_E/E0, coilhit=float(hitE.sum())/E0,
                             energy=(KE+Wp-W0+out_E+hitE.sum())/E0-1.0, pz_ion=pz_all/p0, coil_imp=float(coil_imp.sum())/p0,
                             momentum=(pz_all+coil_imp.sum()-p0z)/p0, cavity_R=cavR, Wion=Wion/E0, Wfld=Wfld/E0, Bmax_comp=float(np.max(Bt[(np.hypot(g.R, g.Z-zb) < 40) & (Bc > 0)]/np.maximum(Bc[(np.hypot(g.R, g.Z-zb) < 40) & (Bc > 0)], 1e-9)))))
            if verbose:
                h = hist[-1]
                print(f"  t {h['t']*1e6:5.2f} us live {h['live']:.3f} KE {h['KE']:.3f} Wp {h['Wp']:+.3f} out {h['out']:.3f} dE {h['energy']:+.4f} "
                      f"pz {h['pz_ion']:+.3f} coil {h['coil_imp']:+.3f} dP {h['momentum']:+.4f} cav {h['cavity_R']:.1f} m Wion {h['Wion']:+.3f} JtEt {h['Wfld']:+.3f} comp {np.round(Wcomp/E0,3)}", flush=True)
            if live.mean() < 0.002:
                break
    # particles still on the grid: continue them as test particles too (their plasma has thinned out)
    still = st == 0
    E_grid_end = float(np.sum(w[still]*(np.sqrt(1+(ur[still]**2+ut[still]**2+uz[still]**2)/C**2)-1)*ms[spn[still]]*C*C))/E0
    st[still] = 1
    if len(cR):
        continue_tp(st, r, z, ur, ut, uz, qm, spn, cI, cR, cz, ca, cf, float(zb), box, 0.25, 400000)
    else:
        st[st == 1] = np.where(uz[st == 1] > 0, 3, 4)
    gF = np.sqrt(1+(ur**2+ut**2+uz**2)/C**2)
    EF = w*(gF-1)*ms[spn]*C*C; PZ = w*ms[spn]*uz; PM = w*ms[spn]*np.sqrt(ur**2+ut**2+uz**2)
    fr = dict(AFT=float(EF[st == 3].sum()/E0), FORWARD=float(EF[st == 4].sum()/E0), RADIAL=float(EF[st == 5].sum()/E0),
              COIL=float(hitE.sum()/E0)+float(EF[st == 6].sum()/E0), TRAPPED=float(EF[st == 7].sum()/E0))
    space = (st == 3) | (st == 4) | (st == 5)
    ship_frac = np.zeros(n_part)
    if ship is not None:
        fwd = np.where(st == 4)[0]
        for i_ in fwd:
            # straight line from the box exit to the stern plane, azimuth-averaged chance of landing on the offset disk
            vz_ = uz[i_]; vr_ = ur[i_]
            if vz_ >= 0:
                continue
            tpl = (ship['z_face']-z[i_])/vz_*1.0
            rho_ = abs(r[i_]+vr_*tpl); a_ = ship['offset']; Rs = ship['R']
            if rho_+a_ <= Rs:
                f_ = 1.0
            elif rho_ == 0 or abs(rho_-a_) >= Rs:
                f_ = 0.0
            else:
                f_ = math.acos(max(-1.0, min(1.0, (rho_*rho_+a_*a_-Rs*Rs)/(2*a_*rho_))))/math.pi
            ship_frac[i_] = f_
    leave = np.where(space, 1.0-ship_frac, 0.0)
    kappa = float(np.sum(leave*PZ)/p0)
    aft = st == 3
    out = dict(kappa=kappa, fractions=fr, forward_energy=fr['FORWARD'], forward_on_ship=float(np.sum(ship_frac*EF)/E0),
               forward_number=float(w[st == 4].sum()/w.sum()), aft_cos=float(PZ[aft].sum()/max(PM[aft].sum(), 1e-30)),
               coil_impulse_grid=(coil_imp/p0).tolist(), coil_hit_E=(hitE/E0).tolist(), E_on_grid_at_end=E_grid_end,
               max_energy_error=float(max(abs(h['energy']) for h in hist)) if hist else 0.0,
               max_momentum_error=float(max(abs(h['momentum']) for h in hist)) if hist else 0.0,
               cavity_R_max=float(max(h['cavity_R'] for h in hist)) if hist else 0.0, steps=len(hist)*25, dt=dt, dx=dx, n_part=n_part,
               n_c=n_c, Ep=Ep, seconds=time.time()-t0, hist=hist if record else None,
               spectrum=_spectrum(EF/w, spn, st, species, w))
    return out


def _spectrum(Eion, spn, st, species, w):
    """Energy per ion (MeV) of the aft exhaust, per species: mean and 10/50/90 % quantiles."""
    res = {}
    for k, s in enumerate(species):
        sel = (spn == k) & (st == 3)
        if sel.sum() < 5:
            continue
        e = Eion[sel]/NC.MEV
        res[s['name']] = dict(mean=float(e.mean()), q10=float(np.quantile(e, 0.1)), q50=float(np.quantile(e, 0.5)), q90=float(np.quantile(e, 0.9)),
                              born=float(s['E']/NC.MEV))
    return res
