"""Vertex 2.3: the four Halo Vertex rings together (research, not canon).

  python3 lab/variants/halo-vertex/halo.py        prints the four-ring checks for the default design (ledger2.py calls these functions)

The ship pushes on four magnetic nozzles, each a single superconducting ring with its burn 2 R aft of the ring plane, about 2 km aft of the
ship. Checked here, with stated assumptions:
- magnetic interaction: exact Biot-Savart forces and torques between the four rings, and the stray field at each burn;
- cross-irradiation: neutrons and photons from each burn reach the three other rings from the side, past their own neutron fins; the
  remedy is a small shadow strip near each burn (at the armour-limited distance) that hides the other rings' conductors;
- structure: the nozzle thrust pushes each ring TOWARD the ship, so the link is a compression boom, not a tether. Four booms braced
  together by tension cables form one space frame; the booms are sized for Euler buckling between bracing stations;
- the forward-escaping stream (about 2.4 % of the exhaust, collimated within about 12 degrees of the ring axis, leak.py) must miss the
  booms and the ship: rings canted inward so the forward stream leans outward;
- deployment and stowage: conductor, structure and boom packed inside the four existing engine housings.
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import trace as tr  # noqa: E402

MU0 = tr.MU0
C = tr.C


def loop_points(R, n, cx=0.0, cy=0.0):
    return [(cx+R*math.cos(2*math.pi*k/n), cy+R*math.sin(2*math.pi*k/n), 0.0, -math.sin(2*math.pi*k/n), math.cos(2*math.pi*k/n)) for k in range(n)]


def field_at(loops, x, y, z):
    """Field of coplanar loops (I, R, cx, cy) with axes along +z."""
    B = [0.0, 0.0, 0.0]
    for I, R, cx, cy in loops:
        b = tr.field([(I, R, 0.0)], x-cx, y-cy, z)
        B = [B[0]+b[0], B[1]+b[1], B[2]+b[2]]
    return B


def forces(I, R, a, n=720):
    """Net force and torque on the ring at (a, 0) from the rings at (-a, 0), (0, a), (0, -a); cluster radius a, all coplanar and parallel."""
    others = [(I, R, -a, 0.0), (I, R, 0.0, a), (I, R, 0.0, -a)]
    F = [0.0, 0.0, 0.0]; T = [0.0, 0.0, 0.0]; dl = 2*math.pi*R/n
    for x, y, z, tx, ty in loop_points(R, n, a, 0.0):
        Bx, By, Bz = field_at(others, x, y, z)
        # dF = I dl x B with dl = (tx, ty, 0) dl
        fx, fy, fz = I*dl*(ty*Bz), I*dl*(-tx*Bz), I*dl*(tx*By-ty*Bx)
        F = [F[0]+fx, F[1]+fy, F[2]+fz]
        rx, ry, rz = x-a, y, z
        T = [T[0]+ry*fz-rz*fy, T[1]+rz*fx-rx*fz, T[2]+rx*fy-ry*fx]
    m = I*math.pi*R*R
    pair_dipole = 3*MU0*m*m/(4*math.pi*(2**0.5*a)**4)
    hoop = MU0*I*I/(4*math.pi*R)*(math.log(8*R/0.114)-0.5)       # self hoop force per unit length scale (comparison, thin ring)
    return dict(force_N=F, force_mag_N=math.sqrt(sum(f*f for f in F)), torque_Nm=T, torque_mag_Nm=math.sqrt(sum(t*t for t in T)),
                nearest_pair_dipole_N=pair_dipole, self_hoop_N_per_m=hoop)


def stray_at_burn(I, R, a, z0):
    """Field of the three other rings at this ring's burn point (2 R aft on its axis) against its own field there."""
    own = tr.field([(I, R, 0.0)], 0.0, 0.0, z0*R)
    oth = field_at([(I, R, -a-a, 0.0), (I, R, -a, a), (I, R, -a, -a)], 0.0, 0.0, z0*R)
    o = math.sqrt(sum(b*b for b in own)); s = math.sqrt(sum(b*b for b in oth))
    return dict(own_T=o, others_T=s, ratio=s/o)


def cross_irradiation(R, w, z0, a, Pn, Pph, n_per_J, Tb, phi_lim, lam, rho_sh, q_max, Pfus, sources=None):
    """Neutron fluence and photon power on one ring's conductor from the three other burns (side illumination past the ring's own fin),
    and the shadow strips near each burn that hide the other rings. The strip sits at distance s from its burn where the armour heat flux
    limit holds (s = sqrt(iso power / 4 pi q_max)); its area is the conductor's projected area scaled by (s/d)^2, plus a 0.1 m alignment
    margin per side at the conductor, scaled likewise (neutrons and photons come from the millimetre pellet)."""
    centres = sources or [(-2*a, 0.0), (-a, a), (-a, -a)]      # other burns relative to this ring's centre at (a,0) -> shift
    n = 720; dl = 2*math.pi*R/n
    tot_frac = 0.0; rows = []
    for (cx, cy) in centres:
        frac = 0.0; dsum = 0.0
        for x, y, _, tx, ty in loop_points(R, n):
            sx, sy, sz = x-cx, y-cy, -z0*R
            d = math.sqrt(sx*sx+sy*sy+sz*sz); ux, uy, uz = sx/d, sy/d, sz/d
            er = (x/R, y/R)
            A = dl*w*abs(uz)+dl*w*abs(ux*er[0]+uy*er[1])+w*w*abs(ux*tx+uy*ty)   # projected area of a w x w conductor element
            frac += A/(4*math.pi*d*d); dsum += d/n
        rows.append(dict(source=(cx, cy), mean_distance_m=dsum, sky_fraction=frac)); tot_frac += frac
    d_mean = sum(r['mean_distance_m'] for r in rows)/len(rows)
    fluence = Pn*n_per_J*Tb*tot_frac/(2*math.pi*R*w)              # per m2 of conductor face, all three neighbours
    photon_W = Pph*tot_frac
    s = math.sqrt((Pn+Pph)/(4*math.pi*q_max)); att = max(fluence/phi_lim, 1.0); t = lam*math.log(att)*1.0
    # strip area for one neighbour ring seen from one burn: conductor projected area (sky fraction x 4 pi s^2) plus a penumbra margin
    strips = []
    for r in rows:
        area = r['sky_fraction']*4*math.pi*s*s+2*0.1*(2*math.pi*R)*(s/r['mean_distance_m'])
        strips.append(area)
    strip_kg_per_burn = rho_sh*t*sum(strips)
    return dict(neighbour_rows=rows, sky_fraction_all=tot_frac, conductor_fluence_unshielded=fluence, photon_W_unshielded=photon_W,
                strip_distance_m=s, strip_thickness_m=t, strip_area_m2_per_burn=sum(strips), strip_kg_per_burn=strip_kg_per_burn,
                strip_intercepted_W=(Pn+Pph)*tot_frac, mean_neighbour_distance_m=d_mean)


def boom(F, L, a, stations, r_truss=4.0, E=3.0e11, sigma=1.5e9, rho=1600.0, k=3.0, overhead=1.5):
    """Compression boom from the ship to one ring: thin-walled truss of radius r_truss, Euler buckling between bracing stations (effective
    length L / stations) with safety k, overhead for battens and diagonals; plus the tension bracing cables between the four booms
    (each station carries 2 % of the boom load laterally, LITERATURE bracing rule). High-modulus CFRP class E 300 GPa (LITERATURE)."""
    Le = L/stations
    A = max(2*k*F*Le*Le/(math.pi**2*E*r_truss**2), k*F/sigma)
    m_boom = A*L*rho*overhead
    cable_len = math.sqrt(2)*a                                    # per boom: one side of the square of cables at each station
    m_cable = stations*(0.02*k*F/5.0e9)*1600.0*cable_len          # CNT cables, 5 GPa
    return dict(load_N=F, effective_length_m=Le, area_m2=A, boom_kg=m_boom, bracing_kg=m_cable, total_kg=m_boom+m_cable, stations=stations,
                truss_radius_m=r_truss)


def forward_stream(a, L, cant_deg, fwd_cos, R, ship_r=25.0, boom_offset=None):
    """The forward-escaping stream leaves along the ring axis toward the ship. With the ring canted inward by `cant` its axis leans outward.
    Returns the half-angle that holds every traced forward particle, the angle of the ship and of the boom from the stream axis, and the
    clearance margins."""
    half = max(math.degrees(math.acos(min(1.0, abs(c)))) for c in fwd_cos) if fwd_cos else 0.0
    ship_ang = math.degrees(math.atan((a-ship_r)/L))+cant_deg
    boom_ang = math.degrees(math.atan((a-ship_r-R)/L))+cant_deg     # boom from the inner rim of the ring to the ship's aft rim
    return dict(stream_half_angle_deg=half, ship_edge_angle_deg=ship_ang, boom_angle_deg=boom_ang,
                ship_clear=ship_ang > half, boom_clear_far=boom_ang+math.degrees(math.atan(R/L)) > half,
                cosine_loss=1-math.cos(math.radians(cant_deg)))


def stowage(R, Ac, w, boom_kg, rho_boom=1600.0, struct_kg=0.0, housing_m3=None):
    """Packed volumes per engine: the ring conductor coiled (packing 0.5), its CNT structure (packing 0.3), the folded boom (articulated
    truss, packing 0.02 of its swept volume is too optimistic for 2 km; use solid volume / 0.05)."""
    cond = 2*math.pi*R*Ac/0.5; struct = struct_kg/1600.0/0.3; bm = boom_kg/rho_boom/0.05
    return dict(conductor_m3=cond, structure_m3=struct, boom_m3=bm, total_m3=cond+struct+bm, housing_m3=housing_m3,
                fits=(housing_m3 is None) or (cond+struct+bm <= housing_m3))


def run():
    I = 2*64.0*0.2/MU0; R = 64.0
    out = dict()
    for a in (250.0, 350.0, 500.0, 1000.0):
        out[f'a{int(a)}'] = dict(forces=forces(I, R, a, 360), stray=stray_at_burn(I, R, a, 2.0))
    return out


if __name__ == '__main__':
    o = run()
    for k, v in o.items():
        f = v['forces']
        print(k, f"force {f['force_mag_N']:.3g} N (dipole pair {f['nearest_pair_dipole_N']:.3g}), torque {f['torque_mag_Nm']:.3g} N m, "
                 f"stray at burn {v['stray']['ratio']:.2e} of own")
