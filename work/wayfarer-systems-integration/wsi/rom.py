"""WSI reduced-order global stability model (ROM): the free-free ship as a planar Euler-Bernoulli beam under its own thrust.

Used for the CP2 trades while the PSA Phase III FE stability is being repaired (see NOTES: penalty conditioning). It is NOT a substitute
for the FE: it has no local modes (thrust ring, deck), no shear lag, no joint flexibility. One calibration factor ties its follower
load factor to the PSA Phase II FE value on the same configuration class; trends (ratios between candidates) are what it is used for.

Physics
  axial field: inertia relief, N(x) = -lambda T m_ahead(x)/M (compression), thrust at the thrust-ring station
  geometric stiffness: consistent beam Kg(N); follower: thrust turns with the slope at the ring (partial p = 0 fixed, 1 follower)
  eigen sweep: (K + lambda (Kg - p Lf)) q = w^2 M q in the elastic modal basis; divergence (w^2 < 0) or flutter (complex) = critical
  mass: every rigid body of c11.config spread over its x range, its pitch inertia (about its own centre) on the rotation dofs
  EI(x): cage from the rails (six rails on r_rail, I = n A r^2 / 2) and the longitudinal family masses; farm and Brow stretch from keels
         and vessel shells (FARM_EI_FACTOR x cage, PROTOTYPE); hub bay with the hub cones.
"""
import math

import numpy as np
import scipy.linalg as sla

import common  # noqa: F401
import c11
import model as mdl
from structure import use_point

X_RING = mdl.X_RING
CAL = dict(factor=None, note='set by calibrate(): ROM follower lambda = PSA Phase II FE follower 0.68 (H:hub:F1, CP4 class)')
FARM_EI_FACTOR = 4.0          # PROTOTYPE: farm (13 vessels tied by keels, decks and guides) bending stiffness / cage stiffness


def cage_EI(rail_t, n_rails=6, r=mdl.R_RAIL, E=68.9e9, rho=2700.0, L=mdl.X_CAGE_END-X_RING):
    A = rail_t*1e3/(rho*L*n_rails)
    return E*n_rails*A*r*r/2


def mesh(P, h2_aft=None, dx=2.0, rail_t=170.0, E=68.9e9, rho=2700.0, r_rail=mdl.R_RAIL, farm_factor=FARM_EI_FACTOR, struct_t=1222.9, extra=None):
    use_point(P); cfg = c11.config(1.0, True, h2_aft); bodies = cfg['bodies']
    x_aft = X_RING-6.0; x_fwd = cfg['brow'][1]+1.0
    xs = np.arange(x_aft, x_fwd+1e-9, dx); n = len(xs); m = np.zeros(n); J = np.zeros(n)
    def put(mass, x0, x1, Iyy=0.0):
        x0, x1 = max(x0, x_aft), min(x1, x_fwd)
        if x1-x0 < dx:
            i = int(round((0.5*(x0+x1)-x_aft)/dx)); i = min(max(i, 0), n-1); m[i] += mass; J[i] += Iyy; return
        idx = [i for i in range(n) if x0 <= xs[i] <= x1] or [int(round((0.5*(x0+x1)-x_aft)/dx))]
        for i in idx:
            m[i] += mass/len(idx)
        # inertia of a spread body is mostly carried by the spread; keep only the cross-section part (Iyy - m L^2/12) on the nodes
        Ls = x1-x0; rest = max(Iyy-mass*Ls*Ls/12, 0.0)
        for i in idx:
            J[i] += rest/len(idx)
    for b in bodies:
        x = b.get('x') or ((b['x0'], b['x1']) if 'x0' in b else None)
        if b['kind'] == 'vessel' and b['owner'] == 'propellant':
            x = (b['x0'], b['x0']+b.get('level_m', b['x1']-b['x0']))
        Iyy = float(b['I'][1, 1]) + b['m']*(b['c'][2]**2)          # pitch about the ship axis: own + offset (z)
        if x is None:
            put(b['m'], b['c'][0], b['c'][0], Iyy)
        else:
            put(b['m'], x[0], x[1], Iyy)
    # the structure itself: cage members along the cage, deck at the deck, keels/guides over the farm
    put(struct_t*1e3*0.40, X_RING, mdl.X_CAGE_END); put(struct_t*1e3*0.50, mdl.X_CAGE_END+13.0, cfg['farm'][0]+1.0); put(struct_t*1e3*0.10, cfg['farm'][0], cfg['farm'][1])
    if extra:
        for (mass, x0, x1) in extra:
            put(mass, x0, x1)
    EIc = cage_EI(rail_t, r=r_rail, E=E, rho=rho)
    EI = np.where(xs < mdl.X_CAGE_END, EIc, np.where(xs < cfg['farm'][0], 2.0*EIc, farm_factor*EIc))
    return dict(xs=xs, m=m, J=J, EI=EI, M=m.sum(), T=cfg['thrust'], farm=cfg['farm'], brow=cfg['brow'], EIc=EIc)


def _beam(xs, EI, m, J):
    n = len(xs); nd = 2*n; K = np.zeros((nd, nd)); M = np.zeros((nd, nd))
    for e in range(n-1):
        L = xs[e+1]-xs[e]; k = 0.5*(EI[e]+EI[e+1])/L**3*np.array([[12, 6*L, -12, 6*L], [6*L, 4*L*L, -6*L, 2*L*L], [-12, -6*L, 12, -6*L], [6*L, 2*L*L, -6*L, 4*L*L]])
        d = [2*e, 2*e+1, 2*e+2, 2*e+3]; K[np.ix_(d, d)] += k
    for i in range(n):
        M[2*i, 2*i] = m[i]+10.0; M[2*i+1, 2*i+1] = J[i]+1e-3*m[i]+10.0
    return K, M


def _kg(xs, N):
    n = len(xs); nd = 2*n; G = np.zeros((nd, nd))
    for e in range(n-1):
        L = xs[e+1]-xs[e]; Ne = N[e]
        g = Ne/(30*L)*np.array([[36, 3*L, -36, 3*L], [3*L, 4*L*L, -3*L, -L*L], [-36, -3*L, 36, -3*L], [3*L, -L*L, -3*L, 4*L*L]])
        d = [2*e, 2*e+1, 2*e+2, 2*e+3]; G[np.ix_(d, d)] += g
    return G


def stability(ms, partial=1.0, lam_hi=12.0, nbasis=40, cal=True):
    xs, m, J, EI, T = ms['xs'], ms['m'], ms['J'], ms['EI'], ms['T']
    if cal and CAL['factor']:
        EI = EI*CAL['factor']
    K, M = _beam(xs, EI, m, J)
    i_ring = int(np.argmin(np.abs(xs-X_RING)))
    ahead = np.array([m[i+1:].sum() for i in range(len(xs)-1)])           # mass forward of each element
    N = -T*(ahead+0.0)/m.sum(); N[:i_ring] = 0.0                            # compression forward of the thrust station
    G = _kg(xs, N); Lf = np.zeros_like(K); Lf[2*i_ring, 2*i_ring+1] = T     # lateral thrust component T * slope at the ring
    w2, V = sla.eigh(K, M); keep = w2 > (2*math.pi*0.003)**2; V = V[:, keep][:, :nbasis]
    k = V.T @ K @ V; mm_ = V.T @ M @ V; g = V.T @ G @ V; lf = V.T @ Lf @ V
    def status(lam):
        e = sla.eigvals(k + lam*(g - partial*lf), mm_)
        if np.any(np.abs(e.imag) > 1e-7*np.abs(e)):
            return 'flutter'
        return 'divergence' if np.any(e.real < 0) else 'stable'
    prev = 0.0
    for lam in np.linspace(0, lam_hi, 121)[1:]:
        s = status(lam)
        if s != 'stable':
            a, c = prev, lam
            for _ in range(30):
                mid = 0.5*(a+c)
                (a, c) = (mid, c) if status(mid) == 'stable' else (a, mid)
            return dict(lam=c, kind=status(c), f1_Hz=float(math.sqrt(w2[keep][0])/(2*math.pi)))
        prev = lam
    return dict(lam=None, kind=f'stable_to_{lam_hi}', f1_Hz=float(math.sqrt(w2[keep][0])/(2*math.pi)))


def calibrate(P, target=0.68, **kw):
    CAL['factor'] = None
    raw = stability(mesh(P, **kw), 1.0, lam_hi=40.0, cal=False)['lam']
    CAL['factor'] = target/raw
    CAL['raw_lambda'] = raw
    return CAL
