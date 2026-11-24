#!/usr/bin/env python3
"""HIMS: Hybrid Ionization-Magnetic Shielding for the Vertex/AMPN ship in braking (research, not canon; standard library only).

Sequence per grain (owner brief 2026-11-22 13:26Z, section 4):
  A  disruption: a thin screen (or several) turns the grain into vapour and plasma; laser pre-ionisation sized for comparison.
  B  expansion: the debris cone (half-angle from the dust study's bumper rules) spreads over the stand-off.
  C  deflection: a transverse magnetic field turns the ionised part away if the cloud is magnetised (plasma beta < 1 at the field) and
     the ion gyroradius is smaller than the field depth; test-particle Boris push of a silicate ion mix through the field.
  D  residual: the wall behind takes the neutral share plus whatever the field could not hold.
Concepts: A screen + the existing Vertex ring field; B distributed screens; C screen + integrated transverse deflector (cos-theta
dipole round the stern path, conductors outside the protected disc); C2 boom bus deflector (azimuthal field of the boom power bus).
Evaluated for the stern disc of the AMPN B today ship, NOMINAL and JUSTIFIED dust (lab/studies/dust-impacts, read-only).

Classes: ESTABLISHED (rigidity, gyroradius, beta, Whipple scaling as the dust study uses it), MODELLED (cone expansion, test particles),
EXTRAPOLATED (full vaporisation and ionisation above 100 km/s, no data), SPECULATIVE (multi-screen energy split, collective deflection).
`python3 lab/studies/vertex-compact-engine/vertex-hims/hims.py` writes results/hims.json, results/hims.log and results/trajectories.json (for Blender).
"""
import json
import math
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / 'lab' / 'studies' / 'dust-impacts'))
sys.path.insert(0, str(HERE.parent / 'vertex-ampn'))
import model as M  # noqa: E402
P = M.P

C = 299792458.0
V = 0.016 * C
MU0 = 4e-7 * math.pi
AMU = 1.66053907e-27
QE = 1.602176634e-19
R_STERN = 45.0
A_STERN = math.pi * R_STERN ** 2
JE = 1.53e8                    # A/m2 engineering current density, today's REBCO (AMPN)
RHO_COND = 6000.0              # kg/m3 conductor + stabiliser
SIGMA_S, RHO_S = 1.5e9, 1600.0 # CFRP support (AMPN)
MAST_KG_M = 30.0               # stern mast, braced truss (PROTOTYPE)
FRAME_KG_M2 = 0.3              # screen tensioning frame and edge ring (PROTOTYPE)
# silicate grain: mass fractions and atomic masses (O, Mg, Si, Fe); charge states: fully stripped (EXTRAPOLATED at ~120 keV/u)
MIX = [('O', 16, 8, 0.44), ('Mg', 24, 12, 0.20), ('Si', 28, 14, 0.21), ('Fe', 56, 26, 0.15)]
CASES = {  # ionised share of the disrupted mass, multi-screen energy pass-through per extra screen
    'NOMINAL': dict(f_ion=0.9, pass_screen=0.5),
    'JUSTIFIED': dict(f_ion=0.7, pass_screen=0.7),
}
BURN = dict(Tb_d=78.0, ve=1.75e7)        # B today burns (AMPN coilpack): about 78 d over four burns, ve 17.5 km/s


def segs():
    return M.mission(Tb_total=BURN['Tb_d'] * P.DAY, ve=BURN['ve'])[0]


def stern_item():
    return dict(P.lead_item('stern disc', A_STERN), leads='ENGINE_FIRST')


def design_energy(sg, case, target=P.TARGET):
    """Grain energy whose expected count on the stern over the mission equals the target (0.1)."""
    it = stern_item(); lo, hi = 1.0, 1e14
    for _ in range(80):
        mid = math.sqrt(lo * hi)
        lo, hi = (mid, hi) if P.events(it, sg, mid, case) > target else (lo, mid)
    return hi


# ---------- stage A: disruption ------------------------------------------------------------------------------------------------------
def laser_preionisation(E_J, L=1000.0, case='NOMINAL'):
    """Continuous illumination of the whole stern path over a depth L: intensity that vaporises the design grain in its transit time."""
    m = 2 * E_J / V ** 2; a = (3 * m / (4 * math.pi * P.RHO_GRAIN)) ** (1 / 3)
    I = 4 / 3 * a * P.RHO_GRAIN * 1.3e7 * V / L                  # W/m2 (absorptivity 1)
    return dict(grain_a_m=a, intensity_W_m2=I, power_W=I * A_STERN, per_grain_J=m * 1.3e7)


def screen(E_def, case):
    sb, sw = P.bumper_kg_m2_from_E(E_def, case) if hasattr(P, 'bumper_kg_m2_from_E') else _bumper_from_E(E_def, case)
    return sb, sw


def _bumper_from_E(E_def, case):
    _, d = P.design_grain(E_def)
    return P.T_OVER_D[case] * d * P.RHO_BUMPER, P.WALL_KG_M2[case]


def erosion(sg, case, t_screen):
    """Screen damage over the mission. Grains whose crater reaches through the screen (perforation rule of the dust study) punch a
    hole about two crater depths across; smaller grains only crater (mass loss k_crater x energy fluence). Returns the holed area
    fraction and the eroded thickness (m)."""
    it = stern_item(); k = P.K_CRATER[case]; holed = 0.0
    E_perf = P.perforation_energy(t_screen, k)
    Es = [E_perf * 10 ** (j / 4) for j in range(0, 70)]
    prev = P.events(it, sg, Es[0], case)
    for E1 in Es[1:]:
        n1 = P.events(it, sg, E1, case); dn = max(0.0, prev - n1); prev = n1
        crater = (3 * k * E1 / (2 * math.pi)) ** (1 / 3)
        holed += dn * math.pi * crater ** 2                         # hole radius ~ one crater depth (dust-study scale)
    thin = k * P.energy_fluence(it, sg, case)
    return holed / A_STERN, thin


# ---------- stage C: deflection ------------------------------------------------------------------------------------------------------
def rigidity(A, q):
    return A * AMU * V / (q * QE)


def beta_energy_limit(B, R_cloud):
    """Largest grain energy whose debris cloud is magnetised (ram energy density below the field's) at cloud radius R_cloud."""
    return B * B / (2 * MU0) * (4 / 3 * math.pi * R_cloud ** 3) / 2


def boris_slab(B, L, gap, alpha_deg, charge='full', n=1500, R_t=R_STERN, seed=3, keep=0, f0=0.0):
    """Test ions from points spread over the protected disc at the screen (x=0) with the cloud's angular spread, through a uniform
    transverse field B_z over 0 < x < L, then free flight to the wall at x = L + gap. Returns the energy share that reaches the wall disc
    and a few paths. Isolated test particles: no collective effects (gated separately by beta_energy_limit)."""
    rnd = random.Random(seed); hit = 0.0; tot = 0.0; paths = []
    for i in range(n):
        name, A, Z, w = rnd.choices(MIX, weights=[m[3] for m in MIX])[0]
        q = Z if charge == 'full' else 1
        r = R_t * math.sqrt(rnd.random()); ph = 2 * math.pi * rnd.random()
        y, z = r * math.cos(ph), r * math.sin(ph)
        th = math.radians(alpha_deg) * math.sqrt(rnd.random()); ps = 2 * math.pi * rnd.random()
        v = [V * math.cos(th), V * math.sin(th) * math.cos(ps), V * math.sin(th) * math.sin(ps)]
        x = [0.0, y, z]; qm = q * QE / (A * AMU)
        rl = rigidity(A, q) / B if B > 0 else float('inf')
        dt = min(L / V / 50, 0.05 * rl / V if B > 0 else 1.0)
        pts = [tuple(x)]; t = 0.0; out = None
        while True:
            if f0 <= x[0] <= f0 + L and B > 0:
                # Boris rotation about z
                tvec = qm * B * dt / 2; s = 2 * tvec / (1 + tvec * tvec)
                vpx = v[0] + v[1] * tvec; vpy = v[1] - v[0] * tvec
                v[0] += vpy * s; v[1] -= vpx * s
                step = dt
            else:
                step = max(dt, 2.0 / V)
            x = [x[0] + v[0] * step, x[1] + v[1] * step, x[2] + v[2] * step]; t += step
            if len(pts) < 400 and (len(pts) == 0 or abs(x[0] - pts[-1][0]) + abs(x[1] - pts[-1][1]) > 0.5):
                pts.append(tuple(x))
            if x[0] >= f0 + L + gap:
                out = 'wall' if math.hypot(x[1], x[2]) <= R_t else 'missed'
                break
            if x[0] < -5.0 or abs(x[1]) > 20 * R_t or t > 50 * (f0 + L + gap) / V:
                out = 'turned'
                break
        e = w
        tot += e
        if out == 'wall':
            hit += e
        if i < keep:
            pts.append(tuple(x)); paths.append(dict(species=name, q=q, outcome=out, points=[[round(c, 2) for c in p] for p in pts[::max(1, len(pts) // 60)]]))
    return hit / tot, paths


def cos_theta_dipole(B, r, L):
    """Transverse field B over a cylinder of radius r and depth L along the dust path; conductors on the cylinder (outside the
    protected disc) plus end returns. Returns conductor, structure and cryostat mass (t) and stored energy (J)."""
    I_tot = 8 * B * r / MU0
    length = 2 * L + math.pi * r                                 # go and return along the depth plus the end arcs (mean)
    cond = I_tot / 2 * length / JE * RHO_COND                    # half the total current runs each way
    W = B * B / (2 * MU0) * math.pi * r * r * L * 1.3           # 30 % fringe
    struct = 2 * W * RHO_S / SIGMA_S
    cryo = 2 * math.pi * r * L * 0.15 * 25 / 1e3 * 0 + 2 * 2 * (L + math.pi * r) * 25.0   # two coil packs, 25 kg/m cryostat
    return dict(I_tot_A=I_tot, conductor_t=cond / 1e3, structure_t=struct / 1e3, cryostat_t=cryo / 1e3, W_J=W,
                total_t=(cond + struct + cryo) / 1e3 * 1.25)    # 25 % for supports, quench dump, leads


def ring_far_field(I=7.3e6, R=15.0, lateral=540.0):
    m = I * math.pi * R * R
    return MU0 * m / (4 * math.pi * lateral ** 3)


# ---------- stage D and the trade ----------------------------------------------------------------------------------------------------
def required(sg, case, gain_fn, S_max=2000.0):
    """Smallest stand-off S (screen to wall) for which the grain the stack can no longer defeat stays at the 0.1-event target.
    gain_fn(S, E_def) returns the defeat energy with the hybrid stage (>= E_def)."""
    it = stern_item()
    def n(S):
        return P.events(it, sg, gain_fn(S, P.bumper_defeat_energy(S, case)), case)
    lo, hi = 0.5, S_max
    if n(hi) > P.TARGET:
        return None
    for _ in range(50):
        mid = math.sqrt(lo * hi)
        lo, hi = (mid, hi) if n(mid) > P.TARGET else (lo, mid)
    return hi


def stack_mass(S, E_def, case, n_screens=1, magnet_t=0.0):
    sb, sw = _bumper_from_E(E_def, case)
    return (A_STERN * (n_screens * (sb + FRAME_KG_M2) + sw) + MAST_KG_M * S) / 1e3 + magnet_t


def main():
    log = []
    def say(s=''):
        print(s, flush=True); log.append(s)
    sg = segs(); out = dict(meta=dict(title='HIMS stage model, AMPN B today stern, braking (research, not canon)', V=V, burns=BURN,
                                      mix=MIX, cases=CASES), cases={})
    # isolated-ion deflection scan (shared by the cases)
    say('Test ions through a transverse slab (L 20 m, gap 20 m, cloud 30 deg): energy share reaching the 45 m wall disc')
    scan = []
    for B in (0.0, 1e-4, 1e-3, 0.01, 0.03, 0.1, 0.3, 1.0):
        row = dict(B_T=B)
        for ch in ('full', 'single'):
            row[ch], _ = boris_slab(B, 20.0, 20.0, 30.0, charge=ch, n=600)
        scan.append(row)
        say(f'  B {B:7.4f} T: fully stripped {row["full"]:.3f}, singly charged {row["single"]:.3f}  (Si14+ gyroradius {rigidity(28, 14) / B if B else float("inf"):.2f} m)')
    out['slab_scan'] = scan
    _, paths_C = boris_slab(0.3, 20.0, 0.5, 30.0, n=40, keep=40, f0=17.7)
    _, paths_A = boris_slab(ring_far_field(), 20.0, 0.5, 30.0, n=20, keep=20, f0=43.8)
    _, paths_N = boris_slab(0.0, 1.0, 37.2, 30.0, n=20, keep=20, f0=0.0)
    (HERE / 'results').mkdir(exist_ok=True)
    (HERE / 'results' / 'trajectories.json').write_text(json.dumps(dict(C_slab_0p3T=paths_C, A_ring_far_field=paths_A, neutral_or_unfielded=paths_N, geometry=dict(C=dict(screen=0, field=[17.7, 37.7], wall=38.2), A=dict(screen=0, wall=64.3)))))
    Bff = ring_far_field()
    say(f'Vertex ring far field on the stern path: {Bff:.2e} T (Si14+ gyroradius {rigidity(28, 14) / Bff / 1e3:.0f} km)')
    for case, cp in CASES.items():
        say(f'\n== {case} (ionised share {cp["f_ion"]}, multi-screen pass-through {cp["pass_screen"]})')
        alpha = P.BUMPER[case if case in P.BUMPER else 'HIGH']['alpha_deg']
        E_d = design_energy(sg, case)
        lz = laser_preionisation(E_d)
        say(f'  stern design grain (0.1 events): {E_d:.2e} J, a {lz["grain_a_m"] * 1e6:.0f} um; laser pre-ionisation over 1 km: '
            f'{lz["intensity_W_m2"]:.1e} W/m2, {lz["power_W"] / 1e12:.1f} TW (REJECTED)')
        res = dict(design_E_J=E_d, laser=lz, alpha_deg=alpha, options=[])
        def passive(S, E):
            return E
        def multi(n):
            return lambda S, E: E / (cp['pass_screen'] ** (n - 1))
        def magnet(B, L_f):
            def g(S, E):
                Rc = max(0.0, S - L_f) * math.tan(math.radians(alpha))     # the field sits just in front of the wall
                Emag = beta_energy_limit(B, Rc)
                eta = 1.0                                              # isolated ions all turn at B >= 0.01 T (scan above)
                hyb = E / max(1e-6, 1 - cp['f_ion'] * eta)
                return max(E, min(hyb, Emag))
            return g
        opts = [('PASSIVE stern screen (AMPN)', passive, 1, 0.0, None),
                ('A screen + Vertex ring field', lambda S, E: E, 1, 0.0, dict(B=Bff)),
                ('B two screens', multi(2), 2, 0.0, None), ('B three screens', multi(3), 3, 0.0, None)]
        for B in (0.1, 0.3, 1.0):
            mg = cos_theta_dipole(B, 50.0, 20.0)
            opts.append((f'C screen + deflector {B} T', magnet(B, 20.0), 1, mg['total_t'], dict(B=B, magnet=mg)))
        for name, fn, ns, mt, extra in opts:
            S = required(sg, case, fn)
            if S is None:
                res['options'].append(dict(name=name, closes=False)); say(f'  {name:32s} does not close below 2 km'); continue
            E_def = fn(S, P.bumper_defeat_energy(S, case))
            m = stack_mass(S, E_def, case, ns, mt)
            sb, sw = _bumper_from_E(E_def, case)
            ero, thin = erosion(sg, case, sb / P.RHO_BUMPER)
            row = dict(name=name, closes=True, standoff_m=S, defeat_E_J=E_def, screens=ns, screen_kg_m2=sb, wall_kg_m2=sw, magnet_t=mt,
                       mass_t=m, screen_holed_fraction=ero, screen_eroded_m=thin, t_transit_ms=S / V * 1e3, **(extra or {}))
            res['options'].append(row)
            say(f'  {name:32s} stand-off {S:7.1f} m ({S / V * 1e6:5.1f} us)  screen {sb:5.2f} kg/m2 x{ns}  magnet {mt:6.1f} t  TOTAL {m:7.1f} t  '
                f'screen holed {ero * 100:.4f} %, eroded {thin * 1e6:.1f} um')
        # the same stand-off as the passive answer, with the deflector: how much thinner can the wall get? (none: wall is a fixed rule)
        out['cases'][case] = res
    # boom bus deflector (C2): field 0.3 T at 2 m from a line current
    I = 0.3 * 2 * math.pi * 2.0 / MU0
    kg_m = 2 * I / JE * RHO_COND
    out['boom_bus'] = dict(I_A=I, kg_per_m=kg_m, four_booms_t=4 * 1975 * kg_m / 1e3)
    say(f'\nC2 boom bus deflector: {I / 1e6:.1f} MA go and return, {kg_m:.0f} kg/m, {4 * 1975 * kg_m / 1e3:,.0f} t over four 1.98 km booms '
        '(vs boom-duct armour 1,580 t JUSTIFIED, 23 t fences NOMINAL)')
    (HERE / 'results' / 'hims.json').write_text(json.dumps(out, indent=1, default=str))
    (HERE / 'results' / 'hims.log').write_text('\n'.join(log) + '\n')


if __name__ == '__main__':
    main()
