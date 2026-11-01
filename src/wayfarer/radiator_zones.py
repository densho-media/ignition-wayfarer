"""Radiator temperature zoning (RAD-ZONE, PROTOTYPE, Claude under the owner's delegation; owner brief 2026-11-01).

Function: give the aft radiator district three thermally separate circuits instead of one plate with a gradient. Front to aft:
- LOW: the lowest-temperature section at the forward end, next to the aft propellant bank. It rejects the stationary low-temperature
  loads: the cryocoolers of the propellant banks and the stationary avionics/electronics (the habitat cold loop stays on the rings,
  thermal.loops.cold fluid_rule).
- WARM: the machinery base load of the warm loop (owner warm example, 5 MW: pumps, computers, power electronics) as a dedicated
  always-on section. Defense heat keeps the F02 modes (heat-pumped into the hot loop in a burn, drain-back channels in the dark hot
  blades in the coast).
- HOT: the existing 182.149 m drive blade (thermal_geometry), unchanged, closest to the drive.

Each section is its own blade in each of the three blade planes: own root booms, own feed/return trunks, own isolation valves; a
non-emitting thermal break (open gap, no sheet, no coolant crossing) separates neighbours, and a two-layer radiation baffle annulus
at each break blocks the line of sight from a cooler section to every hotter one (without it the LOW and WARM sections would be
net-heated by the 1800 K blades in a burn; radiator_zone_study in work/ quantifies this by Monte Carlo view factors).
Section lengths are DERIVED: load / (two faces x emitting height x emissivity x sigma T^4 x space view factor x three blades), rounded up.

Fixed: the three blade planes, root and outer radius (6.5 / 37 m, the shield shadow), the hot blade. Every temperature, load and
view factor here is PROTOTYPE; the hot-section numbers stay those of thermal_budget.
"""
import math

SIGMA = 5.670374419e-8


def cfg(s):
    return s['radiators']['zones']


def emitting_height_m(s):
    r = s['radiators']
    return r['outer_radius']['value']-r['root_radius']['value']-r['root_band']['width_m']


def capacity_per_m(s, sec):
    """Net rejection per metre of section length, all three blades, both faces (W/m)."""
    z = cfg(s)
    return 3*2*emitting_height_m(s)*z['emissivity']*SIGMA*sec['T_K']**4*z['space_view_factor']*(1-z['baffle_backload_fraction'])


def sections(s):
    """Sections front to aft with derived length, X span (filled by `placed`) and capacity."""
    z = cfg(s); out = []
    for sec in z['sections']:
        per = capacity_per_m(s, sec); step = z['length_step_m']
        L = math.ceil(sec['load_W']/per/step)*step
        out.append(dict(sec, length_m=L, capacity_W=per*L, per_m_W=per, margin=per*L/sec['load_W']-1))
    return out


def total_length_m(s):
    """Length of the zone sections ahead of the hot blade, breaks included (one break aft of each section)."""
    return sum(x['length_m'] for x in sections(s))+len(cfg(s)['sections'])*cfg(s)['break_m']


def placed(s):
    """Sections with their ship-X spans: the hot blade front, a break, the WARM section, a break, the LOW section (aft to front)."""
    import layout
    x = layout.origin(s, 'RADIATOR_FRONT'); brk = cfg(s)['break_m']; out = []
    for sec in reversed(sections(s)):
        x0 = x+brk; x1 = x0+sec['length_m']
        out.append(dict(sec, x0=x0, x1=x1, break_x=(x+x0)/2)); x = x1
    return list(reversed(out))


def plates(s):
    """One plate per section per blade plane (local X span, root .. outer radius, azimuth)."""
    r = s['radiators']; p = s['prototype']; out = []
    for sec in placed(s):
        for k in range(3):
            a = math.radians(p['radiator_phase_deg']+120*k)
            out.append(dict(name=f"Radiator_Zone_{sec['id']}_{k+1}", section=sec['id'], blade=k+1, azimuth=a, x0=sec['x0'], x1=sec['x1'],
                            r0=r['root_radius']['value'], r1=r['outer_radius']['value'], T_K=sec['T_K'], circuit=sec['circuit']))
    return out


def baffles(s):
    """A two-layer radiation baffle annulus at each break (casing radius to the blade outer radius)."""
    import thermal_geometry
    z = cfg(s); r0 = thermal_geometry.casing_radius(s)+z['baffle_casing_gap_m']; r1 = s['radiators']['outer_radius']['value']
    return [dict(name=f"Radiator_Baffle_{sec['id']}", x=sec['break_x'], r0=r0, r1=r1, layers=z['baffle_layers'],
                 layer_gap_m=z['baffle_layer_gap_m'], emissivity=z['baffle_emissivity']) for sec in placed(s)]


# ---------- Monte Carlo view factors (study and screen only; not used by layout) ----------------------------------------

def _rng(seed):
    import random
    return random.Random(seed)


def view_factor(src, dst, n=20000, seed=1, block=()):
    """Diffuse view factor from one face of plate src to plate dst (both radial plates in planes through the X axis).
    src/dst: dict(x0, x1, r0, r1, azimuth); src face = +normal side (tangent +phi). Cosine-weighted rays from random points on src;
    a ray counts if it crosses dst's plate before any annulus in `block` (x, r0, r1)."""
    R = _rng(seed); hit = 0
    a, b = src['azimuth'], dst['azimuth']
    eu = (0.0, math.cos(a), math.sin(a)); en = (0.0, -math.sin(a), math.cos(a))
    du = (0.0, math.cos(b), math.sin(b)); dn = (0.0, -math.sin(b), math.cos(b))
    for _ in range(n):
        x = src['x0']+(src['x1']-src['x0'])*R.random(); r = src['r0']+(src['r1']-src['r0'])*R.random()
        o = (x, r*eu[1], r*eu[2])
        u1, u2 = R.random(), R.random(); st = math.sqrt(u1); ct = math.sqrt(1-u1); ph = 2*math.pi*u2
        t1 = (1.0, 0.0, 0.0)                          # tangent frame on src: X, radial, normal
        d = tuple(st*math.cos(ph)*t1[i]+st*math.sin(ph)*eu[i]+ct*en[i] for i in range(3))
        den = sum(d[i]*dn[i] for i in range(3))
        if abs(den) < 1e-12:
            continue
        t = -sum(o[i]*dn[i] for i in range(3))/den    # dst plane passes through the axis
        if t <= 1e-6:
            continue
        p = tuple(o[i]+t*d[i] for i in range(3)); rr = p[1]*du[1]+p[2]*du[2]
        if not (dst['x0'] <= p[0] <= dst['x1'] and dst['r0'] <= rr <= dst['r1']):
            continue
        blocked = False
        for bx, br0, br1 in block:
            if abs(d[0]) > 1e-12:
                tb = (bx-o[0])/d[0]
                if 0 < tb < t:
                    q = (bx, o[1]+tb*d[1], o[2]+tb*d[2])
                    if br0 <= math.hypot(q[1], q[2]) <= br1:
                        blocked = True; break
        if not blocked:
            hit += 1
    return hit/n


def mutual_screen(s, n=20000, baffled=True):
    """Irradiation of each cooler section by every hotter section in a burn (HIGH_POWER: hot blades at their temperature, the others at
    their own). Returns per section: emitted, absorbed from hotter sections and the baffle leak, and the net fraction it can still reject."""
    import thermal_geometry
    z = cfg(s); d = thermal_geometry.blade_of(s); r = s['radiators']; p = s['prototype']
    hot = dict(id='HOT', T_K=r['temperature']['value'], x0=d['aft_x_m'], x1=d['front_x_m'])
    secs = placed(s); levels = [hot]+list(reversed(secs))           # aft to front: HOT, WARM, LOW
    r0, r1 = r['root_radius']['value']+r['root_band']['width_m'], r['outer_radius']['value']
    eps = z['emissivity']; out = []
    block = [(b['x'], b['r0'], b['r1']) for b in baffles(s)] if baffled else []
    for i, cool in enumerate(levels[1:], 1):
        src = dict(x0=cool['x0'], x1=cool['x1'], r0=r0, r1=r1, azimuth=math.radians(p['radiator_phase_deg']))
        emitted = eps*SIGMA*cool['T_K']**4; absorbed = 0.0; rows = []
        for hotter in levels[:i]:
            for k in (1, 2):                            # the two neighbouring blades; the src face sees one of them each side
                dst = dict(x0=hotter['x0'], x1=hotter['x1'], r0=r0, r1=r1, azimuth=math.radians(p['radiator_phase_deg']+120*k))
                F = view_factor(src, dst, n, seed=7+k+10*i, block=block)
                q = F*eps*eps*SIGMA*hotter['T_K']**4      # gray-gray, one bounce ignored
                rows.append(dict(source=hotter['id'], blade=k+1, F=F, absorbed_W_m2=q)); absorbed += q
        out.append(dict(section=cool['id'], T_K=cool['T_K'], emitted_W_m2=emitted, absorbed_W_m2=absorbed,
                        net_fraction=1-absorbed/emitted, rows=rows))
    return out


def baffle_temperature(s, F_hot=0.3):
    """Steady temperature of a baffle layer facing the hot blades (gray, both faces at baffle_emissivity) and the flux its forward face
    passes on through the second layer (two-layer shield: forward leak about half of one layer's)."""
    z = cfg(s); e = z['baffle_emissivity']; Th = s['radiators']['temperature']['value']
    G = F_hot*z['emissivity']*SIGMA*Th**4
    T1 = (e*G/(2*e*SIGMA))**0.25
    leak = e*SIGMA*T1**4/(z['baffle_layers'])
    return dict(incident_W_m2=G, layer1_T_K=T1, forward_leak_W_m2=leak)


def check(s):
    errs = []
    z = cfg(s); ids = [x['id'] for x in z['sections']]
    if ids != ['LOW', 'WARM']:
        errs.append('radiator zones must be LOW then WARM (front to aft), ahead of the hot blade')
    ts = [x['T_K'] for x in z['sections']]+[s['radiators']['temperature']['value']]
    if any(a >= b for a, b in zip(ts, ts[1:])):
        errs.append('radiator zone temperatures must rise from front to aft')
    for sec in sections(s):
        if sec['capacity_W'] < sec['load_W']:
            errs.append(f"radiator zone {sec['id']} capacity below its load")
    if z['break_m'] <= 0:
        errs.append('radiator zones need a thermal break')
    return errs


def report(s):
    return dict(status='PROTOTYPE (RAD-ZONE, Claude under the owner delegation, brief 2026-11-01)',
                sections=[{k: (round(v, 3) if isinstance(v, float) else v) for k, v in x.items()} for x in placed(s)],
                total_length_m=total_length_m(s), baffles=baffles(s), baffle=baffle_temperature(s))


if __name__ == '__main__':
    import json
    import spec
    s = spec.load()[0]
    print(json.dumps(report(s), indent=1, default=str)); print('check', check(s) or 'PASS')
