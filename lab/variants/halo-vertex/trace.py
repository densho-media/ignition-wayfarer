"""Vertex 2.3: charged-particle trajectories through the Halo Vertex ring field (research, not canon).

  python3 lab/variants/halo-vertex/trace.py        writes lab/variants/halo-vertex/trace.json and prints the tables

Test-particle model (no collective plasma effects): exact field of circular current loops (vector potential and field from complete
elliptic integrals by the arithmetic-geometric mean), relativistic Boris push in Cartesian coordinates. A particle born on the axis has
zero canonical angular momentum, so it stays in its meridional plane and only its emission polar angle matters: each case is a fine
deterministic scan of that angle, weighted by sin(theta) / 2 for an isotropic source, with every boundary between outcomes bisected, so
fractions down to about 1e-6 are resolved without random sampling. A finite burn region (born off the axis) is checked by a coarse
Monte Carlo sample at a few source radii.

Frame: +z is aft (away from the ship), the burn point is on the axis at z0 (in ring radii) from the ring plane. Outcomes:
  AFT       leaves through z > +zb with the thrust it carries (mean cos of its final direction)
  FORWARD   leaves through z < -zb, toward the ship
  RADIAL    leaves through r > rb
  RING      strikes the ring body (armour face, conductor and neutron fin cross-section)
  TRAPPED   still inside after the step limit
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
C = 299792458.0
MU0 = 4e-7*math.pi
E_CH = 1.602176634e-19
MEV = 1.602176634e-13
AMU = 1.66053906660e-27

SPECIES = {   # name: (mass kg, charge number, kinetic energy MeV, role)
    'p 14.7 MeV (D-3He product)': (1.67262192e-27, 1, 14.68, 'fusion product, unchanneled share'),
    'alpha 3.6 MeV (D-3He product)': (4.001506*AMU, 2, 3.67, 'fusion product, unchanneled share'),
    'D exhaust 0.0677 c': (2.013553*AMU, 1, None, 'bulk exhaust ion at the 80 % burnup pure-fuel limit'),
    'He-3 exhaust 0.0677 c': (3.014932*AMU, 2, None, 'bulk exhaust ion'),
}
V_EXH = 0.0677*C


def loop_field(I, R, zc, r, z):
    """Br, Bz of a loop of radius R at axial position zc (Smythe / Simpson closed form)."""
    zz = z-zc
    if r < 1e-9*R:
        Bz = MU0*I*R*R/(2*(R*R+zz*zz)**1.5)
        return 0.0, Bz
    a2 = R*R+r*r+zz*zz-2*R*r; b2 = R*R+r*r+zz*zz+2*R*r
    m = 1.0-a2/b2
    K, E = ellipke(m)
    bb = math.sqrt(b2); C0 = MU0*I/math.pi
    Bz = C0/(2*a2*bb)*((R*R-r*r-zz*zz)*E+a2*K)
    Br = C0*zz/(2*a2*bb*r)*((R*R+r*r+zz*zz)*E-a2*K)
    return Br, Bz


def ellipke(m):
    """K(m), E(m) by the AGM with the Legendre sum E = K (1 - sum_n 2^(n-1) c_n^2), c_0^2 = m."""
    a, g = 1.0, math.sqrt(max(1.0-m, 0.0)); s = 0.5*m; pw = 1.0
    for _ in range(40):
        a, g, c = (a+g)/2, math.sqrt(a*g), (a-g)/2
        s += pw*c*c; pw *= 2
        if abs(c) < 1e-16:
            break
    K = math.pi/(2*a)
    return K, K*(1-s)


def field(coils, x, y, z):
    r = math.hypot(x, y); Br = Bz = 0.0
    for I, R, zc in coils:
        br, bz = loop_field(I, R, zc, r, z); Br += br; Bz += bz
    if r > 0:
        return Br*x/r, Br*y/r, Bz
    return 0.0, 0.0, Bz


def body_hit(bodies, r, z):
    for (r0, r1, z0, z1) in bodies:
        if r0 <= r <= r1 and z0 <= z <= z1:
            return True
    return False


def push(coils, bodies, sp, theta, z0, R, r_src=0.0, phi=0.0, zb=12.0, rb=12.0, max_steps=40000):
    """One particle from (r_src, 0, z0 R) emitted at polar angle theta (from +z, aft) and azimuth phi; relativistic Boris."""
    m, Zq, Ek = SPECIES[sp][0], SPECIES[sp][1], SPECIES[sp][2]
    q = Zq*E_CH
    if Ek is None:
        v = V_EXH; g = 1/math.sqrt(1-(v/C)**2)
    else:
        g = 1+Ek*MEV/(m*C*C); v = C*math.sqrt(1-1/g**2)
    u = [g*v*math.sin(theta)*math.cos(phi), g*v*math.sin(theta)*math.sin(phi), g*v*math.cos(theta)]
    x = [r_src, 0.0, z0*R]
    Bc = abs(field(coils, 0, 0, 0)[2])+1e-30
    dt = min(0.02*R/v, 0.05*g*m/(q*max(Bc, abs(field(coils, x[0], x[1], x[2])[2]))))
    for n in range(max_steps):
        Bx, By, Bz = field(coils, *x)
        gg = math.sqrt(1+(u[0]**2+u[1]**2+u[2]**2)/C**2)
        tx, ty, tz = (q*dt/(2*gg*m))*Bx, (q*dt/(2*gg*m))*By, (q*dt/(2*gg*m))*Bz
        t2 = tx*tx+ty*ty+tz*tz; sx, sy, sz = 2*tx/(1+t2), 2*ty/(1+t2), 2*tz/(1+t2)
        up = [u[0]+(u[1]*tz-u[2]*ty), u[1]+(u[2]*tx-u[0]*tz), u[2]+(u[0]*ty-u[1]*tx)]
        u = [u[0]+(up[1]*sz-up[2]*sy), u[1]+(up[2]*sx-up[0]*sz), u[2]+(up[0]*sy-up[1]*sx)]
        gg = math.sqrt(1+(u[0]**2+u[1]**2+u[2]**2)/C**2)
        x = [x[0]+u[0]/gg*dt, x[1]+u[1]/gg*dt, x[2]+u[2]/gg*dt]
        r = math.hypot(x[0], x[1])
        if body_hit(bodies, r, x[2]):
            return 'RING', 0.0
        if x[2] > zb*R:
            return 'AFT', u[2]/math.sqrt(u[0]**2+u[1]**2+u[2]**2)
        if x[2] < -zb*R:
            return 'FORWARD', u[2]/math.sqrt(u[0]**2+u[1]**2+u[2]**2)
        if r > rb*R:
            return 'RADIAL', u[2]/math.sqrt(u[0]**2+u[1]**2+u[2]**2)
    return 'TRAPPED', 0.0


def scan(coils, bodies, sp, z0, R, n=181, refine=14):
    """Outcome fractions for an isotropic on-axis source: grid in cos(theta), boundaries bisected to 2^-refine of a cell."""
    mus = [1-2*i/(n-1) for i in range(n)]
    res = [push(coils, bodies, sp, math.acos(max(-1, min(1, mu))), z0, R) for mu in mus]
    frac = {}; thrust = 0.0

    def add(k, w, c):
        nonlocal thrust
        frac[k] = frac.get(k, 0.0)+w
        if k == 'AFT':
            thrust += w*c
    for i in range(n-1):
        a, b = mus[i], mus[i+1]; ra, rb_ = res[i], res[i+1]
        if ra[0] == rb_[0]:
            add(ra[0], (a-b)/2, (ra[1]+rb_[1])/2)
            continue
        lo, hi, rlo, rhi = a, b, ra, rb_          # bisect the boundary
        for _ in range(refine):
            mid = (lo+hi)/2; rm = push(coils, bodies, sp, math.acos(mid), z0, R)
            if rm[0] == rlo[0]:
                lo, rlo = mid, rm
            else:
                hi, rhi = mid, rm
        add(ra[0], (a-lo)/2, ra[1]); add(rb_[0], (hi-b)/2, rb_[1]); add('UNRESOLVED', (lo-hi)/2, 0.0)
    return dict(fractions=frac, aft_thrust_cos=thrust, aft=frac.get('AFT', 0.0), ring=frac.get('RING', 0.0), forward=frac.get('FORWARD', 0.0),
                radial=frac.get('RADIAL', 0.0), trapped=frac.get('TRAPPED', 0.0), unresolved=frac.get('UNRESOLVED', 0.0))


def rigidity(sp):
    m, Zq, Ek = SPECIES[sp][0], SPECIES[sp][1], SPECIES[sp][2]
    if Ek is None:
        p = m*V_EXH/math.sqrt(1-(V_EXH/C)**2)
    else:
        g = 1+Ek*MEV/(m*C*C); p = g*m*C*math.sqrt(1-1/g**2)
    return p/(Zq*E_CH)


def ring_body(R, face, depth):
    """Ring body in (r, z): the face (width `face` along z) toward the burn and the fin `depth` radially outward."""
    return [(R-0.05, R+depth, -face/2, face/2)]


def configs(R=64.0, face=0.08, depth=1.4):
    """Single ring over field and burn position; the plug-coil alternative for comparison."""
    out = []
    for B0 in (0.0075, 0.05, 0.1, 0.15, 0.2, 0.25):
        I = 2*R*B0/MU0
        for z0 in ((0.0, 0.5, 1.0, 2.0) if B0 == 0.0075 else (1.0, 1.5, 2.0, 2.5, 3.0)):
            out.append(dict(name=f'single ring B0 {B0:g} T, burn {z0:g} R aft', coils=[(I, R, 0.0)], z0=z0, B0=B0, I_MA=I/1e6, R=R,
                            bodies=ring_body(R, face, depth)))
    for B0 in (0.075, 0.25):
        I = 2*R*B0/MU0; Rp = 0.25*R; Ip = 2*Rp*(4*B0)/MU0
        out.append(dict(name=f'plug coil + halo ring, B0 {B0:g} T, burn 0.5 R aft', coils=[(Ip, Rp, -0.5*R), (I, R, 0.0)], z0=0.5, B0=B0,
                        I_MA=I/1e6, I_plug_MA=Ip/1e6, R=R, bodies=ring_body(R, face, depth)+ring_body(Rp, face*2, depth)))
    return out


def finite_source(cfg, sp, r_src, n, seed=1):
    """Monte Carlo over an isotropic source of radius r_src (uniform in a sphere about the burn point): ring-strike (leakage) fraction."""
    import random
    rnd = random.Random(seed); counts = {}; R = cfg['R']
    for _ in range(n):
        while True:
            x, y, z = (rnd.uniform(-1, 1) for _ in range(3))
            if x*x+y*y+z*z <= 1:
                break
        mu = rnd.uniform(-1, 1); ph = rnd.uniform(0, 2*math.pi)
        rr = math.hypot(x, y)*r_src; zz = cfg['z0']+z*r_src/R; ang = math.atan2(y, x)
        k, _ = push(cfg['coils'], cfg['bodies'], sp, math.acos(mu), zz, R, r_src=rr, phi=ph-ang)
        counts[k] = counts.get(k, 0)+1
    return {k: v/n for k, v in counts.items()}


def run(quick=False):
    out = dict(species={k: dict(mass_kg=v[0], Z=v[1], MeV=v[2], role=v[3], rigidity_Tm=rigidity(k)) for k, v in SPECIES.items()}, rows=[])
    cfgs = configs()
    if quick:
        cfgs = cfgs[:2]
    for cfg in cfgs:
        for sp in SPECIES:
            r = scan(cfg['coils'], cfg['bodies'], sp, cfg['z0'], cfg['R'], n=61 if quick else 121, refine=10 if quick else 12)
            row = dict(config=cfg['name'], B0_T=cfg['B0'], I_MA=cfg['I_MA'], z0_R=cfg['z0'], species=sp, larmor_over_R=rigidity(sp)/cfg['B0']/cfg['R'],
                       **{k: v for k, v in r.items() if k != 'fractions'})
            out['rows'].append(row)
            print(f"{cfg['name']:48s} {sp:30s} rL/R {row['larmor_over_R']:7.3f}  aft {r['aft']:.5f} (cos {r['aft_thrust_cos']:.3f})  ring {r['ring']:.2e}  fwd {r['forward']:.4f}  "
                  f"rad {r['radial']:.4f}  trap {r['trapped']:.4f}", flush=True)
    if not quick:
        out['finite'] = []
        for name in ('single ring B0 0.15 T, burn 2 R aft', 'single ring B0 0.25 T, burn 2 R aft'):
            cfg = next(c for c in cfgs if c['name'] == name)
            for rs in (0.05, 0.1):
                f = finite_source(cfg, 'D exhaust 0.0677 c', rs*cfg['R'], 6000)
                out['finite'].append(dict(config=name, source_radius_R=rs, species='D exhaust 0.0677 c', n=6000, fractions=f))
                print('finite', name, rs, f, flush=True)
    return out


if __name__ == '__main__':
    out = run(quick='--quick' in sys.argv)
    (HERE/'trace.json').write_text(json.dumps(out, indent=1)+'\n')
