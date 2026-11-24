"""Radiation-Optimized Nozzle (RON): one parametric model for every architecture (research, not canon). Standard library only.

    python3 lab/studies/vertex-compact-engine/vertex-ron/ron.py [--quick]      writes results/ron.json, results/ron.log and geometry/<variant>.json (Blender input)

One description per variant (`variants()`) feeds every calculation and the Blender blockouts (geometry/*.json -> blender_ron.py), so the
numbers and the drawn engine are the same configuration. Engine frame: burn point at the origin, +x forward (toward the ship), rho radial;
every burn-facing part is a capsule (a segment with a half-thickness) in the meridional (x, rho) plane, revolved about the engine axis.

Physics hierarchy (each level labelled; none is a plasma simulation):
  L1 VACUUM_FIELD     exact circular-loop fields (vertex_structure.loop_field); conical ribbon coils as filament rows.
  L2 CAPTURE          energy-balance stopping of the charged pulse per direction (the Vertex 1.3 sector rule, vertex_magnet.stopping):
                      the current is scaled until every protected direction stops the pulse 1.25x short of the first hardware. This replaces
                      the MPN's assumed field-energy ratio by a computed one.
  L3 TEST_PARTICLES   relativistic Boris push of fusion products and burn debris in the L2 field: hits, forward stream, aft momentum.
  L4 FLUX_RESPONSE    the coil's stored energy rises by up to the pulse's charged energy while the bubble compresses the field (upper
                      bound used for the structure), not a coupled cavity model (vertex_plasma.cavity is the next fidelity step).
  OPEN                detachment, instabilities, kinetic boundary physics, collective forward-pole loss (Vertex 1.4 D21-1/2).
Radiation: exact axisymmetric sky fractions with occlusion; non-axisymmetric members by line integrals (mpn.segment_sky). Heat sinks:
  SELF  a hot part that radiates its own heat to space (area, temperature, mass booked); B01 piped to the ship's 1800 K hot loop
  (budget 10.8 GW for four engines); COLD neutron heat reaching 20 K windings, booked into B01 at the refrigeration multiplier.
"""
import json
import math
import sys
import time
from multiprocessing import Pool
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT/'src'/'wayfarer'))
sys.path.insert(0, str(HERE.parent/'magneto-photonic-nozzle'))
sys.path.insert(0, str(ROOT/'lab'/'variants'/'halo-vertex'))
import vertex_structure as vs  # noqa: E402  (pure: loop_field, self_inductance, mutual)
import mpn  # noqa: E402  (MPN study: sources, sky of thin members, Hagen-Rubens wall)
import halo  # noqa: E402  (Halo 2.3: braced compression boom)

MU0 = 4e-7*math.pi
C = 2.99792458e8
SIGMA = 5.670374419e-8
E_CH = 1.602176634e-19
AMU = 1.66053906660e-27
MEV = 1.602176634e-13


# ===================================================================================================================================
# 0. Canon and sources (verified against the files; the MPN's per-engine thrust is corrected here, see report section 1)
# ===================================================================================================================================

def canon():
    k = mpn.canon()
    p1 = json.loads((ROOT/'references'/'p1_operating_point.json').read_text())
    op, mi = p1['operating_point'], p1['mission']
    k.update(thrust_N=op['peak_thrust_N'], thrust_per_engine_N=op['peak_thrust_N']/4,       # 21.77 MN is the whole ship (MPN read it as one engine)
             ve_eff=op['exhaust_velocity_m_s'], dv_burn=op['delta_v_m_s'], burns=mi['burns'], departure_kg=mi['departure_mass_kg'],
             dry_kg=mi['end_mass_kg'], mdot=op['peak_mass_flow_kg_s'], drive_package_kg=250000.0,
             eta_ref=op['exhaust_velocity_m_s']/(0.0677*C),     # canon effective velocity / research exhaust speed (Halo/1.4 debris speed)
             t_per_GW_rad=1e9/(2*0.85*SIGMA*1800.0**4)*10.0/1e3*1.5)   # 1800 K two-sided, 10 kg/m2, x1.5 loop and pumps (PROTOTYPE)
    return k


def source(k, key):
    src, _ = mpn.sources(k)
    v = dict(src[key])
    v['P_charged_W'] = k['fusion_per_engine_W']-v['P_brems_W']-v['P_sync_W']-v['P_n_W']
    return v


# ===================================================================================================================================
# 1. Geometry primitives: capsules in the meridional plane
# ===================================================================================================================================

def capsule(name, p0, p1, h, role, **kw):
    return dict(name=name, p0=tuple(p0), p1=tuple(p1), h=h, role=role, **kw)


def ray_capsule(th, c, rmax=1e6):
    """Smallest t > 0 where the ray (cos th, sin th) from the origin enters capsule c, else None."""
    d = (math.cos(th), math.sin(th)); best = None
    for (cx, cy) in (c['p0'], c['p1']):               # end circles
        b = d[0]*cx+d[1]*cy; q = cx*cx+cy*cy-c['h']**2; disc = b*b-q
        if disc >= 0:
            t = b-math.sqrt(disc)
            if t > 0 and (best is None or t < best):
                best = t
    ex, ey = c['p1'][0]-c['p0'][0], c['p1'][1]-c['p0'][1]; L = math.hypot(ex, ey)
    if L > 0:                                          # the two long sides
        ux, uy = ex/L, ey/L; nx, ny = -uy, ux
        for s in (1, -1):
            ox, oy = c['p0'][0]+s*c['h']*nx, c['p0'][1]+s*c['h']*ny
            den = d[0]*uy-d[1]*ux
            if abs(den) < 1e-15:
                continue
            # solve t d = o + u w
            t = (ox*uy-oy*ux)/den; w = (t*d[0]-ox)*ux+(t*d[1]-oy)*uy
            if t > 0 and 0 <= w <= L and (best is None or t < best):
                best = t
    return best if best is not None and best < rmax else None


def angular_interval(c):
    """Polar-angle interval [a, b] of directions from the origin that meet the capsule (convex hull of its end circles)."""
    lo, hi = math.pi, 0.0
    for (cx, cy) in (c['p0'], c['p1']):
        rho = math.hypot(cx, cy); phi = math.atan2(cy, cx); dl = math.asin(min(1.0, c['h']/rho))
        lo, hi = min(lo, phi-dl), max(hi, phi+dl)
    return max(0.0, lo), min(math.pi, hi)


def sky_axisymmetric(elements, n=4000):
    """Visible sky fraction of each revolved capsule from the burn, with occlusion by nearer parts: each element's interval is sampled
    finely (n points) and a direction counts for the first element it meets."""
    out = {e['name']: 0.0 for e in elements}
    for e in elements:
        a, b = angular_interval(e)
        if b <= a:
            continue
        for i in range(n):
            th = a+(i+0.5)*(b-a)/n
            t = ray_capsule(th, e)
            if t is None:
                continue
            nearer = any((o is not e) and (ray_capsule(th, o) or 1e99) < t for o in elements)
            if not nearer:
                out[e['name']] += math.sin(th)/2*(b-a)/n
    return out


# ===================================================================================================================================
# 2. Fields (L1) and capture (L2)
# ===================================================================================================================================

def filaments(coils):
    """Conical ribbon coils as filament rows along their section: (x, r, share of the coil current)."""
    out = []
    for c in coils:
        n = c.get('filaments', 3)
        for j in range(n):
            f = (j+0.5)/n
            out.append((c['p0'][0]+f*(c['p1'][0]-c['p0'][0]), c['p0'][1]+f*(c['p1'][1]-c['p0'][1]), c['I']/n))
    return out


def field(fil, x, rho, k=1.0):
    br = bx = 0.0
    for fx, fr, i in fil:
        a, b = vs.loop_field(fr, k*i, rho, x-fx); br += a; bx += b
    return br, bx


def stored_energy(fil, k=1.0, a_min=0.02):
    W = 0.0
    for i, (xi, ri, Ii) in enumerate(fil):
        for j, (xj, rj, Ij) in enumerate(fil):
            M = vs.self_inductance(ri, a_min) if i == j else vs.mutual(ri, rj, xi-xj)
            W += 0.5*k*k*Ii*Ij*M
    return W


def ray_obstacle(th, elements):
    best = None
    for e in elements:
        a, b = angular_interval(e)
        if a-1e-9 <= th <= b+1e-9:
            t = ray_capsule(th, e)
            if t is not None and (best is None or t < best[0]):
                best = (t, e['name'])
    return best


def capture(v, E, margin=1.25, step_deg=0.5, dr_frac=0.002):
    """Current scale k so that in every direction toward hardware the field stops the pulse's charged energy E (isotropic) 1.25x short of
    the first part: k^2 int_0^(d/margin) B1^2 r^2 dr >= mu0 E / (2 pi). Returns k, the binding direction and the field-energy ratio."""
    fil = filaments(v['coils']); need = MU0*E/(2*math.pi); worst = (0.0, None, None, None)
    th = 0.0
    rays = []
    while th <= 180.0:
        rays.append(th); th += step_deg
    for e in v['elements']:                            # refine near every part (thin edge-on parts would fall between rays)
        a, b = angular_interval(e)
        for f in (0.0, 0.25, 0.5, 0.75, 1.0):
            rays.append(math.degrees(a+f*(b-a)))
    for deg in rays:
        ob = ray_obstacle(math.radians(deg), v['elements'])
        if not ob:
            continue
        d, name = ob; R = d/margin; dr = max(R*dr_frac, 1e-3); acc = 0.0; prev = 0.0; r = 0.0
        while r < R:
            r += dr; br, bx = field(fil, r*math.cos(math.radians(deg)), r*math.sin(math.radians(deg)))
            cur = (br*br+bx*bx)*r*r; acc += 0.5*(prev+cur)*dr; prev = cur
        k2 = need/acc if acc > 0 else math.inf
        if k2 > worst[0]:
            worst = (k2, deg, name, d)
    k = math.sqrt(worst[0]); W = stored_energy(fil, k)
    return dict(k=k, binding_deg=worst[1], binding_part=worst[2], binding_distance_m=worst[3], W_J=W, field_ratio=W/E, E_J=E)


# ===================================================================================================================================
# 3. Test particles (L3)
# ===================================================================================================================================

def species(f_fast=0.3):
    """Charged energy shares: fast products (14.7 MeV p : 3.6 MeV alpha by energy) and debris at the exhaust speed (D : He-3 one to one by
    atoms, energy by mass); Vertex 1.4 populations (fast_product_share design 0.3)."""
    v_ex = 0.0677*C
    return [dict(id='p14.7', m=1.00728*AMU, Z=1, E=14.68*MEV, share=f_fast*14.7/18.3),
            dict(id='a3.6', m=4.00151*AMU, Z=2, E=3.67*MEV, share=f_fast*3.6/18.3),
            dict(id='D_debris', m=2.01410*AMU, Z=1, v=v_ex, share=(1-f_fast)*2/5),
            dict(id='He3_debris', m=3.01603*AMU, Z=2, v=v_ex, share=(1-f_fast)*3/5)]


def fib_dirs(n):
    """Directions for an on-axis point source: its canonical angular momentum is zero, so only the polar angle matters (Halo 2.3 trace).
    Equal steps in cos(theta) carry equal solid angle; (x, y, z) with x axial."""
    out = []
    for i in range(n):
        mu = 1-2*(i+0.5)/n; out.append((mu, math.sqrt(1-mu*mu), 0.0))
    return out


def _push(args):
    v, k, sp, d, keep = args
    fil = filaments(v['coils']); els = v['elements']; L = v['scale_m']
    m, q = sp['m'], sp['Z']*E_CH
    if 'E' in sp:
        g = 1+sp['E']/(m*C*C); sp_v = C*math.sqrt(1-1/g**2)
    else:
        sp_v = sp['v']; g = 1/math.sqrt(1-(sp_v/C)**2)
    u = [g*sp_v*d[0], g*sp_v*d[1], g*sp_v*d[2]]; x = [0.0, 0.0, 0.0]; path = [(0.0, 0.0, 0.0)]
    x_aft, x_fwd, r_out = -v['aft_exit_m'], v['fwd_exit_m'], v['radial_exit_m']
    sp_v_ = sp_v
    t = 0.0; tmax = 20*(x_fwd-x_aft+r_out)/sp_v; nstep = 0
    while t < tmax:
        rho = math.hypot(x[1], x[2]); br, bx = field(fil, x[0], rho, k)
        B = (bx, br*x[1]/rho, br*x[2]/rho) if rho > 1e-9 else (bx, 0.0, 0.0)
        b = math.sqrt(B[0]**2+B[1]**2+B[2]**2)
        dt = min(L/200/sp_v, (2*math.pi*g*m/(q*b))/30 if b > 0 else 1.0)
        h = q*dt/(2*g*m); tv = [h*B[0], h*B[1], h*B[2]]; t2 = sum(a*a for a in tv); sv = [2*a/(1+t2) for a in tv]
        up = [u[0]+(u[1]*tv[2]-u[2]*tv[1]), u[1]+(u[2]*tv[0]-u[0]*tv[2]), u[2]+(u[0]*tv[1]-u[1]*tv[0])]
        u = [u[0]+(up[1]*sv[2]-up[2]*sv[1]), u[1]+(up[2]*sv[0]-up[0]*sv[2]), u[2]+(up[0]*sv[1]-up[1]*sv[0])]
        x0 = list(x); x = [x[i]+u[i]/g*dt for i in range(3)]; t += dt; nstep += 1
        if keep and nstep % 8 == 0:
            path.append(tuple(round(a, 3) for a in x))
        rho = math.hypot(x[1], x[2])
        for e in els:                                  # segment test against each capsule, in the meridional plane
            if e['role'] == 'plug':
                continue                               # the forward stream and the plug are handled with the cant (particles())
            if _seg_hits(e, (x0[0], math.hypot(x0[1], x0[2])), (x[0], rho)):
                return dict(out='HIT', part=e['name'], cos=0.0, path=path if keep else None)
        un = math.sqrt(u[0]**2+u[1]**2+u[2]**2)
        if x[0] < x_aft:
            return dict(out='AFT', cos=-u[0]/un, path=path+[tuple(x)] if keep else None)
        if x[0] > x_fwd:
            return dict(out='FORWARD', cos=-u[0]/un, theta_deg=math.degrees(math.acos(max(-1, min(1, u[0]/un)))), path=path+[tuple(x)] if keep else None,
                        x_exit=tuple(x), u_exit=tuple(a/un for a in u))
        if rho > r_out:
            return dict(out='RADIAL', cos=-u[0]/un, path=path+[tuple(x)] if keep else None)
    return dict(out='TRAPPED', cos=0.0, path=path if keep else None)


def _seg_hits(c, a, b):
    """Does the meridional step a -> b end inside capsule c (distance to its axis segment below h)?"""
    px, py = b
    ex, ey = c['p1'][0]-c['p0'][0], c['p1'][1]-c['p0'][1]; L2 = ex*ex+ey*ey
    w = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px-c['p0'][0])*ex+(py-c['p0'][1])*ey)/L2))
    qx, qy = c['p0'][0]+w*ex, c['p0'][1]+w*ey
    return (px-qx)**2+(py-qy)**2 <= c['h']**2


def particles(v, k, n=120, pool=None, keep_paths=6):
    sps = species(); tasks = []
    dirs = fib_dirs(n)
    for sp in sps:
        for i, d in enumerate(dirs):
            tasks.append((v, k, sp, d, bool(keep_paths) and i % max(1, n//max(1, keep_paths)) == 0 and sp['id'] in ('p14.7', 'D_debris')))
    res = (pool.map(_push, tasks, chunksize=4) if pool else list(map(_push, tasks)))
    out = {}; paths = []; exits = []
    hit_E = fwd_E = 0.0; thrust = 0.0; fwd_th = []
    # momentum weight of each species per unit charged energy: p / E = 2 / v (non-relativistic share; the fast products carry less thrust
    # per watt than debris, a fuel-cycle property that is NOT credited to the nozzle: eta below is normalised per species)
    pw = [sp['share'] for sp in sps]; pw = [w/sum(pw) for w in pw]
    for j, sp in enumerate(sps):
        rr = res[j*n:(j+1)*n]; cnt = {}
        for r in rr:
            key = r['out'] if r['out'] != 'HIT' else 'HIT:'+r['part']
            cnt[key] = cnt.get(key, 0)+1
            if r.get('path'):
                paths.append(dict(species=sp['id'], outcome=r['out'], points=r['path']))
            if r['out'] == 'FORWARD':
                fwd_th.append(r['theta_deg'])
                exits.append(dict(species=sp['id'], w=sp['share']/n, x=r['x_exit'], u=r['u_exit']))
        hits = sum(c for kk, c in cnt.items() if kk.startswith('HIT'))/n; fwd = cnt.get('FORWARD', 0)/n
        cos_net = sum(r['cos'] for r in rr if r['out'] in ('AFT', 'FORWARD', 'RADIAL'))/n
        out[sp['id']] = dict(n=n, counts=cnt, hit=hits, forward=fwd, net_axial_cos=cos_net,
                             hit_upper95=(3.0 if hits == 0 else hits*n+2*math.sqrt(hits*n))/n)
        hit_E += sp['share']*hits; fwd_E += sp['share']*fwd; thrust += pw[j]*cos_net
    fwd_th.sort()
    return dict(species=out, hit_energy_share=hit_E, forward_energy_share=fwd_E, axial_efficiency=thrust,
                forward_cone_p95_deg=fwd_th[int(0.95*(len(fwd_th)-1))] if fwd_th else None, paths=paths, forward_exits=exits)


# ===================================================================================================================================
# 4. Variants: one generator family (compact edge-on, intermediate, remote F, distributed) and the drawn Vertex 1.2 reference
# ===================================================================================================================================

def hoop_r(c):
    """Mean hoop radius of a coil (its circumference is 2 pi r; RON 0.1 used the burn distance here, fixed in 0.2)."""
    return 0.5*(c['p0'][1]+c['p1'][1])


def ribbon_coil(name, x, r, depth, thick, I):
    """A conical ribbon laid along the ray from the burn through (x, r): seen edge-on (half-thickness), depth along the ray."""
    rho = math.hypot(x, r); ux, uy = x/rho, r/rho
    p0 = (x-ux*depth/2, r-uy*depth/2); p1 = (x+ux*depth/2, r+uy*depth/2)
    return dict(name=name, p0=p0, p1=p1, I=I, depth=depth, thick=thick, rho=rho)


def build(p):
    """A variant from its parameters. Coils: rings at (x_i, r_i) with current shares; plug: grazing cone on the axis at x_plug shading the
    ship (radius r_ship at D); blades: edge-on compression members ring rim -> plug node; boom: plug -> ship in the plug's shadow."""
    v = dict(p)
    coils = []
    for i, (x, r, share) in enumerate(p['rings']):
        coils.append(ribbon_coil(f'RING_{i+1}', x, r, p['ring_depth_m'], p['ring_thick_m'], share*1e6))
    v['coils'] = coils
    els = []
    for c in coils:                       # each coil: hot nose leading the ribbon (the burn-facing capsule) and the cold ribbon behind it
        els.append(capsule(c['name'], c['p0'], c['p1'], c['thick']/2+p['cryo_m'], 'coil', rho=c['rho']))
    xp = p['plug_x_m']
    if p.get('plug_auto'):                # the plug far enough from the burn that its grazing face radiates the flux at <= 2300 K
        q_ok = 0.85*SIGMA*2300.0**4/math.sin(math.radians(p['plug_graze_deg']))
        xp = max(xp, math.sqrt(p['P_rad_W']/(4*math.pi*q_ok)))
    v['plug_x_m'] = xp
    rp = p['r_ship_m']*xp/p['D_m']*1.1      # 10 % margin over the ship's angular radius
    v['plug_r_m'] = rp
    els.append(capsule('PLUG', (xp, 0.0), (xp, rp), 0.05, 'plug'))
    if p.get('shield_disc'):              # compact: the drawn conical shadow shield (Vertex 1.2 dimensions)
        x0, r0, r1, t = p['shield_disc']
        els.append(capsule('SHIELD', (x0+t/2, 0.0), (x0+t/2, r1), t/2, 'shield'))
    if p.get('plug_coil'):                # hybrid: a forward mirror coil inside the plug's shadow (no sky), closing the ring's loss cone
        fr, share = p['plug_coil']
        pc = dict(name='PLUG_COIL', p0=(xp+2.0, fr*rp), p1=(xp+2.0+p['ring_depth_m'], fr*rp), I=share*1e6, depth=p['ring_depth_m'],
                  thick=p['ring_thick_m'], rho=math.hypot(xp+2.0, fr*rp), shadowed=True)
        coils.append(pc)
        els.append(capsule('PLUG_COIL', pc['p0'], pc['p1'], pc['thick']/2+p['cryo_m'], 'coil', rho=pc['rho'], shadowed=True))
    v['elements'] = els
    v['scale_m'] = max(max(c['rho'] for c in coils), xp)
    v['aft_exit_m'] = 3*v['scale_m']; v['fwd_exit_m'] = max([xp]+[c['p1'][0] for c in coils if c.get('shadowed')])+5.0; v['radial_exit_m'] = 4*v['scale_m']
    return v


def variants():
    """Parameters per variant (PROTOTYPE design choices; all lengths in m, ring currents in MA as relative shares before capture scaling)."""
    base = dict(r_ship_m=45.0, ring_depth_m=2.0, plug_graze_deg=5.0, ring_thick_m=0.05, cryo_m=0.013, engines=4, blades=6, f_pulse_Hz=2.0e4, cant_deg=0.0,
                fuel='V2', nose_T_max_K=2000.0, vf_space=1.0, plug_auto=True)
    V = {}
    # A: compact edge-on Vertex. The 1.2 loop stations and radii (L1-L4 about the burn, C1-C2 ahead) as edge-on ribbons; the drawn conical
    # shadow shield at 6 m stays because the ship (45 m radius) is about 60 m forward of the burn in the drawn cluster. Self-radiating
    # noses inside the nozzle see each other: a third of their emission reaches space (vf_space, PROTOTYPE view factor).
    V['A_compact'] = dict(base, label='A Compact edge-on Vertex', family='compact', D_m=60.0, S_m=25.5, plug_x_m=6.0,
                          rings=[(5.0, 2.5, -3.19), (3.0, 4.2, -5.36), (2.3, 6.4, 7.47), (0.0, 7.6, 8.87), (-5.6, 8.9, 10.39), (-12.4, 9.9, 11.56)],
                          ring_depth_m=1.0, shield_disc=(6.0, 4.4, 5.4, 2.2), vf_space=0.33, boom=False, f_pulse_Hz=5697.0,
                          plug_auto=False)
    # B: intermediate-distance family: one ring, burn kappa R aft of it, plug a little ahead of the ring, ship D forward.
    for D in (300.0, 500.0, 800.0, 1200.0):
        R = {300.0: 45.0, 500.0: 45.0, 800.0: 50.0, 1200.0: 60.0}[D]      # ring at >= ~100 m from the burn: the V2 nose-temperature limit
        V[f'B_D{int(D)}'] = dict(base, label=f'B Intermediate ring, ship {int(D)} m', family='intermediate', D_m=D, S_m=0.5*D,
                                 rings=[(2*R, R, 10.0)], plug_x_m=3*R, boom=True)
    for R in (65.0, 80.0):                # D 800 with larger rings: cooler noses at the corrected (hoop-radius) radiating area
        V[f'B_D800_R{int(R)}'] = dict(base, label=f'B Intermediate ring R {R:.0f} m, ship 800 m', family='intermediate', D_m=800.0, S_m=400.0,
                                      rings=[(2*R, R, 10.0)], plug_x_m=3*R, boom=True)
    for kap in (3.0, 4.0):                # same ~110 m standoff, smaller ring further ahead of the burn: higher mirror ratio, less conductor
        R = 110.0/math.sqrt(1+kap*kap)
        V[f'B_D800_k{int(kap)}'] = dict(base, label=f'B Intermediate ring, ship 800 m, burn {kap:.0f} R aft', family='intermediate', D_m=800.0,
                                        S_m=400.0, rings=[(kap*R, R, 10.0)], plug_x_m=kap*R+10.0, boom=True)
    # E: hybrid: the intermediate ring plus a forward mirror coil hidden in the plug's shadow (closes the loss cone toward the ship)
    for share, S in ((2.0, 250.0), (4.0, 250.0), (4.0, 400.0)):
        V[f'E_hybrid_{share:.0f}_S{S:.0f}'] = dict(base, label=f'E Hybrid ring + shadowed forward mirror coil ({share:.0f}/10 of ring current), spacing {S:.0f} m', family='hybrid',
                                          D_m=800.0, S_m=S, rings=[(100.0, 50.0, 10.0)], plug_x_m=150.0, boom=True, plug_coil=(0.6, share))
    # C: remote edge-on ring (MPN candidate F geometry on the corrected load path: plug node FORWARD of the ring, blades in compression)
    V['C_remote_F'] = dict(base, label='C Remote edge-on ring (MPN F)', family='remote', D_m=2000.0, S_m=2000.0,
                           rings=[(180.0, 90.0, 10.0)], plug_x_m=180.0+15.0, boom=True)
    # D: distributed: three coaxial ribbon rings on one cone (same half-angle as the single ring), sharing the current
    V['D_distributed'] = dict(base, label='D Distributed three-ring cone', family='distributed', D_m=800.0, S_m=400.0,
                              rings=[(60.0, 30.0, 3.3), (90.0, 45.0, 3.3), (120.0, 60.0, 3.3)], plug_x_m=135.0, boom=True)
    return V


# ===================================================================================================================================
# 5. Radiation and heat ledger
# ===================================================================================================================================

def nose(v, k, src, rho):
    """Hot leading edge sized by the 20 K winding fluence limit (MPN rule: W-B4C, lambda 0.08 m, limit 3e22 n/m2, scattered floor 1e-4)."""
    flu = src['neutrons_per_s']/(4*math.pi*rho*rho)*k['burn_s']; room = 3e22/2-flu*1e-4
    L = max(0.2, 0.08*math.log(flu/room)) if room > 0 else math.inf
    return L, flu


def fin_area(T, area, T_max, eff=0.7):
    """Edge-on radiating fins (carbon-carbon plates lying in the burn's ray planes, so they add no sky): the two-sided fin area that
    brings a part from T to T_max at fin efficiency eff. PROTOTYPE."""
    if not math.isfinite(T) or T <= T_max:
        return 0.0
    return area*((T/T_max)**4-1)/eff


def ledger(v, k, src):
    Pb, Ps, Pn = src['P_brems_W'], src['P_sync_W'], src['P_n_W']; Prad = Pb+Ps
    A_sync = 1-mpn.far_ir_wall(2.0e6, 1e12)
    sky = sky_axisymmetric(v['elements'])
    rows = []
    for e in v['elements']:
        rho = math.hypot(*e['p0'])
        q_face = Prad/(4*math.pi*rho*rho)
        if e['role'] == 'coil':
            c = next(c for c in v['coils'] if c['name'] == e['name'])
            Ln, flu = nose(v, k, src, c['rho']) if not c.get('shadowed') else (0.0, 1.0)
            absorbed = sky[e['name']]*(Pb+Ps*A_sync+0.3*Pn)
            area = 2*Ln*2*math.pi*hoop_r(c)*1.0                      # both flanks of the nose wedge
            sin_a = (c['thick']/2+v['cryo_m'])/Ln if (math.isfinite(Ln) and Ln > 0) else 1.0
            T = (absorbed*v['vf_space']/(0.85*SIGMA*area))**0.25 if area > 0 else math.inf
            fin = fin_area(T, area, v['nose_T_max_K']) if v['family'] != 'compact' else 0.0
            T = min(T, v['nose_T_max_K']) if fin else T
            to_b01 = absorbed*(1-v['vf_space'])                       # emission that lands on other hardware (compact nozzle)
            cold = sky[e['name']]*0.3*Pn*(math.exp(-Ln/0.08)+1e-4)*k['cold_cost']
            rows.append(dict(part=e['name'], sky=sky[e['name']], absorbed_W=absorbed, self_W=absorbed*v['vf_space'], B01_W=to_b01+cold,
                             cold_W=cold/k['cold_cost'], nose_m=Ln, fin_m2=fin, T_K=T, q_face_W_m2=q_face, q_surface_W_m2=q_face*sin_a,
                             ok=T <= v['nose_T_max_K']))
        elif e['role'] == 'plug':
            absorbed = sky['PLUG']*(Prad+0.9*Pn); sin_a = math.sin(math.radians(v['plug_graze_deg']))
            area = math.pi*v['plug_r_m']**2/sin_a                     # grazing cone, radiating from its outer face
            T = (absorbed/(0.85*SIGMA*area))**0.25
            fin = fin_area(T, area, 2300.0); T = min(T, 2300.0) if fin else T
            rows.append(dict(part='PLUG', sky=sky['PLUG'], absorbed_W=absorbed, self_W=absorbed, B01_W=0.0, cold_W=0.0, T_K=T, fin_m2=fin,
                             area_m2=area, q_face_W_m2=q_face, q_surface_W_m2=q_face*sin_a, ok=T <= 2300.0))
        else:                                                          # compact shadow shield: lithium-cooled face, piped heat
            absorbed = sky[e['name']]*(Prad+0.9*Pn)
            rows.append(dict(part=e['name'], sky=sky[e['name']], absorbed_W=absorbed, self_W=0.0, B01_W=absorbed, cold_W=0.0,
                             q_face_W_m2=q_face, q_surface_W_m2=q_face, ok=q_face <= 2.0e7))
    # blades: edge-on compression members from each ring rim to the plug node (their plane contains the burn: thickness only)
    for c in [c for c in v['coils'] if not c.get('shadowed')] if v.get('boom') else []:
        rim = (c['p1'][0], c['p1'][1], 0.0); node = (v['plug_x_m'], 0.0, 0.0)
        f = v['blades']*mpn.segment_sky(rim, node, v.get('blade_t_m', 0.02))
        rows.append(dict(part=f"BLADES_{c['name']}", sky=f, absorbed_W=f*(Prad+0.3*Pn), self_W=f*(Prad+0.3*Pn), B01_W=0.0, cold_W=0.0, ok=True))
    # neighbours: the three other engines' rings, noses and plugs seen broadside at spacing S (mean |cos| 0.5)
    broad = sum(2*math.pi*hoop_r(c)*(c['depth']+0.5)*0.5 for c in v['coils'])+math.pi*v['plug_r_m']**2*0.5
    if v['family'] == 'compact':
        broad = 2*11.5*31.0                                           # whole drawn engine side area (envelope radius 11.5 m x 31 m)
    f_x = 3*broad/(4*math.pi*v['S_m']**2)
    xb = f_x*(Prad+0.5*Pn)
    rows.append(dict(part='NEIGHBOURS', sky=f_x, absorbed_W=xb, self_W=0.0 if v['family'] == 'compact' else xb, B01_W=xb if v['family'] == 'compact' else 0.0,
                     cold_W=0.0, ok=True, note='self-radiating shadow strips (MPN) for remote families; piped in the compact cluster'))
    tot = lambda key: sum(r[key] for r in rows)
    return dict(rows=rows, absorbed_W=tot('absorbed_W'), self_W=tot('self_W'), B01_W=tot('B01_W'), cold_W=tot('cold_W'),
                sky_total=sum(r['sky'] for r in rows))


# ===================================================================================================================================
# 6. Mass
# ===================================================================================================================================

def masses(v, k, cap, src, Je=1.53e8, sigma_s=1.5e9, rho_s=1600.0, rho_c=6000.0, flux_up=1.0):
    kk = cap['k']; out = {}
    cond = sum(abs(c['I'])*kk/Je*2*math.pi*hoop_r(c)*rho_c for c in v['coils'])
    Wpk = cap['W_J']+flux_up*cap['E_J']
    out['conductor_t'] = cond/1e3
    out['coil_structure_t'] = 2*Wpk*rho_s/sigma_s/1e3                 # virial minimum x2 (all-tension winding support)
    out['cryostat_t'] = sum(2*(c['depth']+c['thick'])*2*math.pi*hoop_r(c)*25.0 for c in v['coils'])/1e3
    nose_t = 0.0
    for c in v['coils']:
        if c.get('shadowed'):
            continue
        Ln, _ = nose(v, k, src, c['rho']); nose_t += (c['thick']+2*v['cryo_m'])*Ln*2*math.pi*hoop_r(c)*10.9
    out['nose_t'] = nose_t
    out['plug_t'] = math.pi*v['plug_r_m']**2/math.sin(math.radians(v['plug_graze_deg']))*15.0/1e3
    if v.get('fins_m2'):
        out['fins_t'] = v['fins_m2']/2*5.0/1e3                       # C-C plates 2.8 mm, both faces radiate
    F = k['thrust_per_engine_N']
    if v.get('boom'):
        L = v['D_m']-v['plug_x_m']
        b = halo.boom(F, L, a=v['S_m']/2, stations=max(4, int(L/50)))
        out['boom_t'] = b['total_kg']/1e3
        bl = 0.0
        for c in [c for c in v['coils'] if not c.get('shadowed')]:     # blades: yield and weak-axis buckling with bracing every 10 m
            Ls = math.dist((c['p1'][0], c['p1'][1]), (v['plug_x_m'], 0.0)); phi = math.atan2(v['plug_x_m']-c['p1'][0], c['p1'][1])     # blade angle from radial
            Fb = F/(v['blades']*max(math.sin(phi), 0.05))/len([q for q in v['coils'] if not q.get('shadowed')])
            t = (12*Fb*10.0**2/(20*math.pi**2*3e11))**0.25; A = max(20*t*t, Fb/sigma_s)
            bl += v['blades']*A*Ls*rho_s
        out['blades_t'] = bl/1e3
    else:
        out['cage_and_shield_t'] = 120.0                               # PROTOTYPE: drawn 1.2 cage, collar, LiH shield share (see report)
    return out


# ===================================================================================================================================
# 7. Whole ship
# ===================================================================================================================================

def ship(k, eng_t, B01_four_W, eta_dir, eta_ref=None, cant_deg=0.0):
    """Departure mass for the canon mission (fixed delta-v per burn, fixed jet power) with the new drive: the dry mass loses the 250 t
    drive package and gains four engine systems plus any hot radiator beyond the 10.8 GW drive share; the effective exhaust velocity
    scales with the computed directed fraction against the reference the canon velocity is taken to include (eta_ref, PROTOTYPE)."""
    eta_ref = eta_ref or k['eta_ref']
    extra_rad = max(0.0, B01_four_W-k['drive_W'])/1e9*k['t_per_GW_rad']
    dry = k['dry_kg']/1e3-k['drive_package_kg']/1e3+4*eng_t+extra_rad
    ve = k['ve_eff']*eta_dir*math.cos(math.radians(cant_deg))/eta_ref
    R = math.exp(k['burns']*k['dv_burn']/ve)
    dep = dry*R
    prop = dep-dry
    thrust = k['thrust_N']*eta_dir*math.cos(math.radians(cant_deg))/eta_ref
    return dict(dry_t=dry, extra_radiator_t=extra_rad, ve_eff_m_s=ve, mass_ratio=R, departure_t=dep, propellant_t=prop,
                thrust_N=thrust, accel_g_departure=thrust/(dep*1e3)/9.80665, burn1_days=(dep-dep/R**0.25)*1e3/k['mdot']/86400,
                delta_departure_t=dep-k['departure_kg']/1e3)


# ===================================================================================================================================
# 8. Run
# ===================================================================================================================================

def configure(p, k, fuel=None, f_pulse=None, Je=1.53e8):
    """Build a variant at its captured current: size the ribbons for the current, re-check capture with the sized parts."""
    src = source(k, fuel or p['fuel'])
    p = dict(p, P_rad_W=src['P_brems_W']+src['P_sync_W'], fuel=fuel or p['fuel'], f_pulse_Hz=f_pulse or p['f_pulse_Hz'])
    v = build(p); E = src['P_charged_W']/p['f_pulse_Hz']
    cap = capture(v, E)
    for _ in range(2):
        for c in v['coils']:
            c['thick'] = max(0.01, abs(c['I'])*cap['k']/Je/c['depth'])
        for e in v['elements']:
            if e['role'] == 'coil':
                c = next(c for c in v['coils'] if c['name'] == e['name']); e['h'] = c['thick']/2+p['cryo_m']
        cap = capture(v, E)
    return v, src, E, cap


def evaluate(v, k, src, E, cap, mult, pool, n, Je=1.53e8, keep=False):
    """One operating point: current = mult x the capture current (more field steers the exhaust better and costs magnet mass)."""
    kk = cap['k']*mult
    for c in v['coils']:
        c['thick'] = max(0.01, abs(c['I'])*kk/Je/c['depth'])
    for e in v['elements']:
        if e['role'] == 'coil':
            c = next(c for c in v['coils'] if c['name'] == e['name']); e['h'] = c['thick']/2+v['cryo_m']
    cp = dict(cap, k=kk, W_J=stored_energy(filaments(v['coils']), kk)); cp['field_ratio'] = cp['W_J']/E
    part = particles(v, kk, n=n, pool=pool, keep_paths=6 if keep else 0)
    led = ledger(v, k, src)
    v['fins_m2'] = sum(r.get('fin_m2', 0.0) for r in led['rows'])
    # forward stream: through the ring bore along the axis; the engine is canted so that it passes the plug and the ship (Halo 2.3 rule)
    th_plug = math.degrees(math.atan(v['plug_r_m']/v['plug_x_m']))
    cone = part['forward_cone_p95_deg'] or 0.0
    # four engines on a square of side S, axes parallel to flight: the ship sits off each engine's axis by theta_s, the plug on the
    # burn-ship line. The forward stream (along the axis) misses ship and plug if its cone stays inside theta_s - theta_plug; otherwise
    # the engine is canted (cosine loss). The hybrid's forward mirror coil sits on the axis; its engines are
    # parallel too: the mirror coil has its own small on-axis shadow disc (sky ~ (r/x)^2/4, booked with the plug), the ship plug sits on
    # the burn-ship line as for B; the mirror only shrinks the forward residual that the ship offset must clear.
    theta_s = math.degrees(math.atan(v['S_m']/math.sqrt(2)/v['D_m'])) if v['family'] != 'compact' else 0.0
    toe = 0.0
    if v['family'] == 'compact' or part['forward_energy_share'] == 0:
        cant = 0.0
    else:
        cant = min(30.0, max(0.0, cone+th_plug+1.0-theta_s))
    ch_hit = part['hit_energy_share']*src['P_charged_W']
    fwd_on_plug = part['forward_energy_share']*src['P_charged_W'] if v['family'] == 'compact' else 0.0
    led['charged_hit_W'] = ch_hit; led['forward_on_plug_W'] = fwd_on_plug
    led['B01_W'] += ch_hit+fwd_on_plug                    # charged strikes on armour or coils go to the hot loop (Halo 2.2 rule)
    m = masses(v, k, cp, src, Je=Je)
    eng = sum(m.values())
    sh = ship(k, eng, 4*led['B01_W'], max(0.05, part['axial_efficiency']), cant_deg=math.degrees(math.acos(math.cos(math.radians(cant))*math.cos(math.radians(toe)))))
    return dict(mult=mult, capture=cp, particles=part, ledger=led, mass_t=m, engine_t=eng, cant_deg=cant, toe_deg=toe, ship_offset_deg=theta_s, ship=sh)


def run_variant(name, p, k, pool, quick=False, fuel=None, f_pulse=None, Je=1.53e8, mults=(1.0, 1.6, 2.5, 4.0), final=True):
    v, src, E, cap = configure(p, k, fuel, f_pulse, Je)
    n_scan = 24 if quick else 48
    scan = []
    for mlt in (mults if v['family'] != 'compact' else (1.0,)):
        r = evaluate(v, k, src, E, cap, mlt, pool, n_scan, Je)
        scan.append(dict(mult=mlt, k=r['capture']['k'], field_ratio=r['capture']['field_ratio'], eta=r['particles']['axial_efficiency'],
                         hit=r['particles']['hit_energy_share'], fwd=r['particles']['forward_energy_share'], engine_t=r['engine_t'],
                         departure_t=r['ship']['departure_t'], B01_four_GW=4*r['ledger']['B01_W']/1e9))
    best = min(scan, key=lambda x: x['departure_t'])
    r = evaluate(v, k, src, E, cap, best['mult'], pool, (40 if quick else 160) if final else n_scan, Je, keep=final)
    paths = r['particles'].pop('paths')
    out = dict(name=name, label=p['label'], family=p['family'], fuel=src_key(p, fuel), f_pulse_Hz=f_pulse or p['f_pulse_Hz'], Je=Je,
               params={kk: vv for kk, vv in v.items() if kk in ('D_m', 'S_m', 'plug_x_m', 'plug_r_m', 'rings', 'ring_depth_m', 'blades', 'r_ship_m')},
               pulse_J=E, capture_1x=cap, scan=scan, **r)
    if final:
        g = export(v, r['capture'], src); g['paths'] = paths; g['cant_deg'] = r['cant_deg']
        out['geometry'] = g
    return out


def src_key(p, fuel):
    return fuel or p['fuel']


def export(v, cap, src):
    """Blender input: the same parts in engine coordinates (x forward), with the captured current and computed field lines."""
    fil = filaments(v['coils']); lines = []
    for c in v['coils']:
        xm, rm = (c['p0'][0]+c['p1'][0])/2, (c['p0'][1]+c['p1'][1])/2
        for f in (0.2, 0.45, 0.7, 0.9, 1.08):
            lines.append(field_line(fil, cap['k'], (xm, f*rm), v['scale_m']))
    return dict(coils=[dict(name=c['name'], p0=c['p0'], p1=c['p1'], thick=c['thick'], I_MA=c['I']*cap['k']/1e6) for c in v['coils']],
                elements=[dict(name=e['name'], role=e['role'], p0=e['p0'], p1=e['p1'], h=e['h']) for e in v['elements']],
                plug=dict(x=v['plug_x_m'], r=v['plug_r_m']), D=v['D_m'], S=v['S_m'], r_ship=v['r_ship_m'], blades=v['blades'],
                boom=bool(v.get('boom')), field_lines=lines, family=v['family'])


def field_line(fil, k, p, L, ds_frac=0.004, n=900):
    out = []
    for sgn in (1, -1):
        x, r = p; pts = []
        for _ in range(n):
            br, bx = field(fil, x, r, k); b = math.hypot(br, bx)
            if b == 0:
                break
            ds = L*ds_frac; x += sgn*bx/b*ds; r += sgn*br/b*ds
            if r < 0 or abs(x) > 3*L or r > 2.5*L:
                break
            pts.append((round(x, 2), round(r, 2)))
        out = (pts[::-1] if sgn == 1 else out)+([p] if sgn == 1 else [])+(pts if sgn == -1 else [])
    return out


def summary_line(r):
    c, L, s_ = r['capture'], r['ledger'], r['ship']
    return (f"{r['name']:16s} {r['fuel']} {r['f_pulse_Hz']/1e3:4.1f} kHz Je {r['Je']:.2g} | pulse {r['pulse_J']/1e9:5.2f} GJ | x{r['mult']:.1f} capture, W/E {c['field_ratio']:5.1f} "
            f"| hit {r['particles']['hit_energy_share']:.3f} fwd {r['particles']['forward_energy_share']:.3f} eta {r['particles']['axial_efficiency']:.3f} cant {r['cant_deg']:.1f} "
            f"| x4 B01 {4*L['B01_W']/1e9:8.1f} self {4*L['self_W']/1e9:8.1f} GW | engine {r['engine_t']:7.0f} t | dep {s_['departure_t']:7.0f} t ({s_['delta_departure_t']:+.0f})")


def main(quick=False):
    t0 = time.time(); k = canon(); V = variants(); res = {}; log = []
    (HERE/'results').mkdir(exist_ok=True); (HERE/'geometry').mkdir(exist_ok=True)
    with Pool(4) as pool:
        only = [a for a in sys.argv[1:] if not a.startswith('--')]
        for name, p in V.items():
            if only and not any(name.startswith(o) for o in only):
                continue
            r = run_variant(name, p, k, pool, quick)
            (HERE/'geometry'/f'{name}.json').write_text(json.dumps(r.pop('geometry')))
            res[name] = r; line = summary_line(r); print(line, flush=True); log.append(line)
        sens = {}
        if not only or '--sens' in sys.argv:
            cases = [('ref V2 20 kHz Je 1.5e8', {}), ('V3 fuel (credited to fuel, not nozzle)', dict(fuel='V3')),
                     ('10 kHz pulses', dict(f_pulse=10e3)), ('40 kHz pulses', dict(f_pulse=40e3)),
                     ('Je 3e8 (better tape)', dict(Je=3e8)), ('Je 6e8 (future tape, SENSITIVITY)', dict(Je=6e8)),
                     ('V3 + 40 kHz + Je 6e8 (all levers)', dict(fuel='V3', f_pulse=40e3, Je=6e8))]
            for name in ('B_D800', 'E_hybrid_4_S250', 'C_remote_F'):
                for lab, kw in cases:
                    r = run_variant(name, V[name], k, pool, True, final=False, **kw)
                    sens.setdefault(name, []).append(dict(case=lab, engine_t=r['engine_t'], departure_t=r['ship']['departure_t'], mult=r['mult'],
                                                         eta=r['particles']['axial_efficiency'], cant=r['cant_deg'], mass_t=r['mass_t'],
                                                         field_ratio=r['capture']['field_ratio'], self_W=r['ledger'].get('self_W'),
                                                         B01_W=r['ledger']['B01_W']))
                    line = f"  sens {name:12s} {lab:38s} engine {r['engine_t']:7.0f} t  dep {r['ship']['departure_t']:8.0f} t  eta {r['particles']['axial_efficiency']:.3f} cant {r['cant_deg']:4.1f}"
                    print(line, flush=True); log.append(line)
        out = dict(version='RON 0.2', sensitivity=sens, canon={kk: vv for kk, vv in k.items() if not isinstance(vv, dict)}, variants=res, wall_s=time.time()-t0)
    (HERE/'results'/'ron.json').write_text(json.dumps(out, indent=1, default=str))
    (HERE/'results'/'ron.log').write_text('\n'.join(log)+'\n')


if __name__ == '__main__':
    main(quick='--quick' in sys.argv)
