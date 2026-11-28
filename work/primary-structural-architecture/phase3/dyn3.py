"""PSA Phase III.3 flexible-body dynamics with active thrust-vector control (owner P2-D4: passive and active stability are separate
tracks, each with its own acceptance criterion).

Model (linear, about steady thrust lambda x T, in a modal basis):
  basis     two rigid attitude rotations about the mass centre (pitch about y, yaw about z) + the lowest NB elastic free-free modes
  structure m q'' + c q' + (k + lambda (g + lf)) q = B delta       (rigidly mounted gimbals: thrust follows the nozzle mount, lf, plus
            the gimbal angle delta; g from the inertia-relief axial field; c = 2 zeta w m per elastic mode, zeta 0.005 PROTOTYPE)
  sensor    attitude and rate at an IMU node (rotation dofs ry, rz), first-order sensor filter tau_s
  actuator  gimbal command through a first-order lag tau_a and a first-order Pade delay tau_d
  control   PD on the IMU attitude, delta = -(Kp theta + Kd theta'), tuned on the rigid body for bandwidth w_c and damping 0.7
Criteria (PROTOTYPE values, owner to confirm):
  C1 passive         static and follower lambda >= 1.95 (from the stability sweep; reported, not computed here)
  C2 closed loop     all closed-loop poles stable at lambda = 1 with damping >= 0.002 margin, gain margin >= 6 dB (x2), delay margin
                     >= 2 x tau_d, and closed-loop lambda_cl >= 1.95
  C3 uncertainty     C2 holds with elastic frequencies x0.85 and x1.15, mass x0.9 / x1.1, damping 0.002
  C4 degradation     with one of four gimbals failed (75 % authority), loop gain x0.5, delay x3, or the IMU moved to the aft cage
                     (non-collocated): stable at lambda = 1, or detected and shut down before the response exceeds the limit
  C5 emergency       thrust ramp-down from 1 to 0 in 2 s and 30 s with a 0.5 deg gimbal hard-over at t = 0: peak elastic response and
                     member force increment bounded (no divergence while lambda > lambda_cl of the degraded loop)
  C6 post-shutdown   lambda = 0: every mode stable; ring spin (1x and 2x) separated from the elastic modes by >= 15 % or damped
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
import scipy.linalg as sla
import scipy.sparse.linalg as spla

H = Path(__file__).resolve().parent
sys.path.insert(0, str(H)); sys.path.insert(0, str(H.parent / 'phase2'))
import analysis as an  # noqa: E402

ZETA = 0.005
NB = 40
TAU_A, TAU_D = 0.5, 0.2                       # gimbal lag, transport delay (s), PROTOTYPE
TAU_S = 1/(2*math.pi*0.03)                    # sensor / structural filter, corner 0.03 Hz (below f1 ~0.087 Hz; rigid loop 0.008 Hz)
WC, ZC = 2*math.pi*0.008, 0.7                 # rigid attitude loop bandwidth 0.008 Hz (about 6x below the first elastic mode), damping
RING_RPM = 4.0


def thrust_field(b, lam=1.0):
    T = b.cfg['thrust']*lam; ring = list(b.station_nodes[b.xs[0]].values())
    b.m.loads = {}; b.m.follow = {}
    for n in ring:
        b.m.thrust(n, (T/len(ring), 0.0, 0.0), follower=True)
    r = b.m.solve_static(inertia_relief=True); fs = b.m.element_forces(r['u'])
    N = [f['N'] if f else 0.0 for f in fs]; Lf = b.m.follower_stiffness()
    return N, Lf, ring


def basis(b, N, Lf, nb=NB):
    """Rigid pitch / yaw about the mass centre + nb elastic modes, mass-orthonormal."""
    K = b.m.assemble('K'); M = b.m.assemble('M'); G = b.m.assemble('G', N=N); free = b.m.free_mask()
    Kf, Mf, Gf, Lff = (A[free][:, free].tocsc() for A in (K, M, G, Lf))
    w2, V = spla.eigsh(Kf, M=Mf, k=nb+10, sigma=-0.5, which='LM'); o = np.argsort(w2); w2, V = w2[o], V[:, o]
    keep = w2 > 1e-4*w2.max(); Ve = V[:, keep][:, :nb]; we = np.sqrt(w2[keep][:nb])
    X = np.array(b.m.X); diag = M.diagonal(); mt = np.array([diag[6*i] for i in range(len(X))]); c = (X*mt[:, None]).sum(0)/mt.sum()
    R = np.zeros((b.m.ndof, 2))
    for j, ax in enumerate((1, 2)):
        w = np.zeros(3); w[ax] = 1.0
        for i in range(len(X)):
            R[6*i:6*i+3, j] = np.cross(w, X[i]-c); R[6*i+3+ax, j] = 1.0
    Rf = R[free]
    Rf = Rf - Ve @ (Ve.T @ (Mf @ Rf))                       # M-orthogonal to the elastic modes
    Lr = np.linalg.cholesky(Rf.T @ (Mf @ Rf)); Rf = Rf @ np.linalg.inv(Lr).T
    Phi = np.hstack([Rf, Ve]); w = np.concatenate([[0.0, 0.0], we])
    k = Phi.T @ (Kf @ Phi); m = Phi.T @ (Mf @ Phi); g = Phi.T @ (Gf @ Phi); lf = Phi.T @ (Lff @ Phi)
    return dict(Phi=Phi, w=w, k=0.5*(k+k.T), m=0.5*(m+m.T), g=g, lf=lf, free=free, c=c, Mf=Mf)


def influence(b, B, nodes, dof):
    """Modal input / output vectors: unit lateral force (dof 1 = y, 2 = z) at nodes, or rotation dof (4 = ry, 5 = rz) at a node."""
    fidx = np.where(B['free'])[0]; pos = {d: i for i, d in enumerate(fidx)}; v = np.zeros(len(fidx))
    for n in nodes:
        v[pos[6*n+dof]] += 1.0/len(nodes) if dof >= 3 else 1.0
    return B['Phi'].T @ v


def plant(b, B, lam, imu, plane='both', authority=1.0, kscale=1.0, mscale=1.0, zeta=ZETA, gain=1.0):
    """Closed-loop state matrix with two TVC channels (pitch about y: z force, ry sensor; yaw about z: y force, rz sensor).
    x = [q, q', then per channel: delta, pade, filtered theta, filtered rate]. 'plane' is kept for the call signature (both always)."""
    n = B['k'].shape[0]; T = b.cfg['thrust']*lam
    w = B['w']*math.sqrt(kscale/mscale)
    m = B['m']*mscale; k = np.diag(w**2)*mscale; k[:2, :2] = 0.0
    k = k + lam*(B['g'] + B['lf'])
    c = np.diag(2*zeta*w)*mscale
    X = np.array(b.m.X); l = abs(B['c'][0] - X[b.noz[0]][0]); Tn = max(b.cfg['thrust'], 1.0)
    mi = np.linalg.inv(m); N = 2*n+8; A = np.zeros((N, N))
    A[:n, n:2*n] = np.eye(n); A[n:2*n, :n] = -mi @ k; A[n:2*n, n:2*n] = -mi @ c
    gains = {}
    for j, (pl, fdof, rdof, sgn) in enumerate((('pitch', 2, 4, 1.0), ('yaw', 1, 5, -1.0))):
        o = 2*n+4*j; dl, pd, th, rt = o, o+1, o+2, o+3
        # lateral nozzle force per rad of gimbal; sign so that +delta produces +rotation about the channel axis
        bu = sgn*influence(b, B, b.noz, fdof)*T*authority
        cy = influence(b, B, [imu], rdof)
        J = rigid_inertia(b, B, pl)*mscale
        Kp = gain*J*WC**2/(Tn*l); Kd = gain*2*ZC*WC*J/(Tn*l); gains[pl] = dict(Kp=Kp, Kd=Kd, l=l, J=J)
        A[n:2*n, dl] = mi @ bu
        u_row = np.zeros(N); u_row[th] = -Kp; u_row[rt] = -Kd
        A[pd, :] = (2.0/TAU_D)*u_row; A[pd, pd] -= 2.0/TAU_D
        ud = 2*np.eye(N)[pd] - u_row
        A[dl, :] = ud/TAU_A; A[dl, dl] -= 1.0/TAU_A
        A[th, :n] = cy/TAU_S; A[th, th] -= 1.0/TAU_S
        A[rt, n:2*n] = cy/TAU_S; A[rt, rt] -= 1.0/TAU_S
    return A, gains


def rigid_inertia(b, B, plane):
    M = b.m.assemble('M'); X = np.array(b.m.X); c = B['c']; ax = 1 if plane == 'pitch' else 2
    v = np.zeros(b.m.ndof); w = np.zeros(3); w[ax] = 1.0
    for i in range(len(X)):
        v[6*i:6*i+3] = np.cross(w, X[i]-c); v[6*i+3+ax] = 1.0
    return float(v @ (M @ v))


def margins(A):
    e = np.linalg.eigvals(A); sig = e.real.max()
    wn = np.abs(e); z = -e.real/np.maximum(wn, 1e-12)
    return dict(max_real=float(sig), stable=bool(sig < 1e-6), min_damping=float(z[wn > 1e-4].min()) if (wn > 1e-4).any() else None)


def evaluate(b, state_bodies, imu=None, label='', lam_hi=4.0):
    b.attach(state_bodies); N, Lf, ring = thrust_field(b, 1.0); B = basis(b, N, Lf)
    imu = imu if imu is not None else b.sp(min(b.spine, key=lambda x: abs(x-40.0)))
    out = dict(label=label, f_elastic_Hz=[float(x/(2*math.pi)) for x in B['w'][2:8]])
    # rigid / follower consistency check: generalised thrust stiffness on the rigid rotations (should be ~0 for a follower thrust)
    out['rigid_follower_residual'] = float(np.abs((B['g']+B['lf'])[:2, :2]).max()/max(np.abs(B['k'][2:, 2:]).max(), 1e-9))
    A, gains = plant(b, B, 1.0, imu); base = margins(A)
    gm = None
    for f in (1.5, 2.0, 3.0, 4.0, 6.0):
        if not margins(plant(b, B, 1.0, imu, gain=f)[0])['stable']:
            gm = f; break
    lam_cl = None
    for lam in np.linspace(1.0, lam_hi, 31):
        if not margins(plant(b, B, lam, imu)[0])['stable']:
            lam_cl = float(lam); break
    dm = None
    global TAU_D
    t0 = TAU_D
    for f in (1.5, 2.0, 3.0, 5.0):
        TAU_D = t0*f
        if not margins(plant(b, B, 1.0, imu)[0])['stable']:
            dm = f; break
    TAU_D = t0
    c3 = {nm: margins(plant(b, B, 1.0, imu, **kw)[0]) for nm, kw in (('k0.85', dict(kscale=0.85)), ('k1.15', dict(kscale=1.15)),
          ('m0.9', dict(mscale=0.9)), ('m1.1', dict(mscale=1.1)), ('zeta0.002', dict(zeta=0.002)))}
    aft_imu = b.sp(min(b.spine, key=lambda x: abs(x-(-80.0))))
    c4 = dict(gimbal_out=margins(plant(b, B, 1.0, imu, authority=0.75)[0]), gain_x0_5=margins(plant(b, B, 1.0, imu, gain=0.5)[0]),
              imu_aft=margins(plant(b, B, 1.0, aft_imu)[0]))
    TAU_D = t0*3; c4['delay_x3'] = margins(plant(b, B, 1.0, imu)[0]); TAU_D = t0
    res = dict(gains=gains, nominal=base, gain_margin_x=gm, delay_margin_x=dm, lam_closed_loop=lam_cl, uncertainty=c3, degradation=c4)
    out['planes'] = res
    # C6 post-shutdown: ring spin against elastic modes at lambda 0
    b.apply_thrust(b.cfg['thrust'])
    f_spin = RING_RPM/60.0; fe = np.array(out['f_elastic_Hz'])
    out['ring_spin'] = dict(f_spin_Hz=f_spin, nearest_1x=float(fe[np.argmin(np.abs(fe-f_spin))]), sep_1x=float(np.min(np.abs(fe/f_spin-1))),
                            nearest_2x=float(fe[np.argmin(np.abs(fe-2*f_spin))]), sep_2x=float(np.min(np.abs(fe/(2*f_spin)-1))))
    return out, B


def scale_gain(A, f, B):
    """Scale the PD gains in the Pade input row and the actuator feed-through of a closed-loop matrix by f."""
    A = A.copy(); n = B['k'].shape[0]; th, rt = 2*n+2, 2*n+3
    for row in (2*n+1, 2*n):
        A[row, th] *= f; A[row, rt] *= f
    return A


def ramp_down(b, B, imu, t_ramp, hardover_deg=0.5, plane='both', t_end=None, dt=0.05):
    """C5: thrust 1 -> 0 over t_ramp with a gimbal hard-over at t = 0 that is cleared at shutdown. Linear time-varying modal
    integration (implicit trapezoid). Returns peak elastic modal amplitude ratio against the steady 2 % TVC case."""
    t_end = t_end or max(3*t_ramp, 60.0); n = B['k'].shape[0]
    steps = int(t_end/dt); NS = 2*n+8; x = np.zeros(NS); peak = 0.0
    A1, _ = plant(b, B, 1.0, imu); A0, _ = plant(b, B, 0.0, imu)
    for i in range(steps):
        t = i*dt; lam = max(0.0, 1.0-t/t_ramp)
        A = A0 + lam*(A1-A0)        # every lambda term in the plant is linear in lambda
        u = np.zeros(NS)
        if lam > 0:
            u[2*n] = math.radians(hardover_deg)/TAU_A
        M = np.eye(NS)-0.5*dt*A; x = np.linalg.solve(M, (np.eye(NS)+0.5*dt*A) @ x + dt*u)
        if i % 4 == 0:
            u_phys = B['Phi'][:, 2:] @ x[2:n]; peak = max(peak, float(np.abs(u_phys).max()))
    return dict(t_ramp=t_ramp, hardover_deg=hardover_deg, peak_elastic_disp_m=peak, final_state_norm=float(np.abs(x[:n]).max()))
