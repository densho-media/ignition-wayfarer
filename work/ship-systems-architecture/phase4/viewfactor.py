"""ISSA Phase IV-D: Monte Carlo view factor from a radiator section on one blade to the 1800 K hot region of the other two blades.
Three planar radial blades at 120 deg (x along the ship axis, radius r_in..r_out), a central casing cylinder that blocks rays, cosine-
weighted rays from both faces of the receiving section. Pure Python, deterministic seed. STUDY: no rings, trusses, tanks or the plume;
hot region at one uniform temperature (conservative where the real blade is graded)."""
import math
import random

R_IN, R_OUT, CASING_R = 6.1, 36.1, 5.6
AZ = (90.0, 210.0, 330.0)


def _blocked_by_casing(P, d, t_hit):
    # segment P + t d, t in (0, t_hit): does it pass inside the casing cylinder (|yz| < CASING_R)?
    py, pz = P[1], P[2]; dy, dz = d[1], d[2]
    a = dy*dy+dz*dz
    if a < 1e-15: return math.hypot(py, pz) < CASING_R
    tm = -(py*dy+pz*dz)/a
    tm = min(max(tm, 0.0), t_hit)
    return math.hypot(py+tm*dy, pz+tm*dz) < CASING_R


def view_factor(x0, x1, hot_x0, hot_x1, n=20000, seed=7, r_in=R_IN, r_out=R_OUT, recv_r=None, baffle=None):
    """Mean (over both faces and the section area) view factor from the section x0..x1 on blade 0 to the hot region hot_x0..hot_x1 on
    blades 1 and 2. recv_r: (r0, r1) radial extent of the receiving section (default the full blade). baffle: (x_b, R_b) an opaque annular
    disk across the three wedges at station x_b out to radius R_b (rays crossing it inside R_b are blocked)."""
    rnd = random.Random(seed); r0, r1 = recv_r or (r_in, r_out)
    a0 = math.radians(AZ[0]); u0 = (math.cos(a0), math.sin(a0)); m0 = (-math.sin(a0), math.cos(a0))
    others = []
    for az in AZ[1:]:
        a = math.radians(az); others.append(((math.cos(a), math.sin(a)), (-math.sin(a), math.cos(a))))
    hits = 0
    for k in range(n):
        x = x0+(x1-x0)*rnd.random(); r = r0+(r1-r0)*rnd.random()
        P = (x, r*u0[0], r*u0[1])
        sgn = 1.0 if k % 2 == 0 else -1.0
        nrm = (0.0, sgn*m0[0], sgn*m0[1]); t1 = (1.0, 0.0, 0.0); t2 = (0.0, u0[0], u0[1])
        # cosine-weighted hemisphere
        u1, u2 = rnd.random(), rnd.random(); rr = math.sqrt(u1); ph = 2*math.pi*u2
        cx, cy, cz = rr*math.cos(ph), rr*math.sin(ph), math.sqrt(max(0.0, 1-u1))
        d = tuple(cx*t1[i]+cy*t2[i]+cz*nrm[i] for i in range(3))
        best = None
        for (u, m) in others:
            dm = d[1]*m[0]+d[2]*m[1]; pm = P[1]*m[0]+P[2]*m[1]
            if abs(dm) < 1e-12: continue
            t = -pm/dm
            if t <= 1e-9: continue
            H = (P[0]+t*d[0], P[1]+t*d[1], P[2]+t*d[2]); rho = H[1]*u[0]+H[2]*u[1]
            if r_in <= rho <= r_out and (best is None or t < best[0]):
                best = (t, H)
        if best is None: continue
        t, H = best
        if _blocked_by_casing(P, d, t): continue
        if baffle and d[0] != 0.0:
            tb = (baffle[0]-P[0])/d[0]
            if 0.0 < tb < t and math.hypot(P[1]+tb*d[1], P[2]+tb*d[2]) < baffle[1]: continue
        if hot_x0 <= H[0] <= hot_x1: hits += 1
    F = hits/n
    return F, math.sqrt(F*(1-F)/n)


if __name__ == '__main__':
    for name, a, b in (('WARM 50.4-72.9', 50.4, 72.9), ('LOW 73.4-93.4', 73.4, 93.4), ('550 K at 21.4-50.4', 21.4, 50.4)):
        print(name, view_factor(a, b, -111.6, 50.4 if a > 50 else a))
    for Rb in (20.0, 30.0, 36.1, 45.0, 60.0):
        print('WARM baffle', Rb, view_factor(50.4, 72.9, -111.6, 50.4, baffle=(50.2, Rb)), 'LOW', view_factor(73.4, 93.4, -111.6, 50.4, baffle=(50.2, Rb)))
