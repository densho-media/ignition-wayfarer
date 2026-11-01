"""Radiator temperature zoning: the Graded Thermal Blade (RAD-ZONE, GTB-2026-11-01; PROTOTYPE, Claude under the owner's delegation).

Function: the aft radiator district rejects three heat grades in three physically separate circuits that share one blade structure in
each of the three blade planes. Aft to front:
- HOT: the existing 182.149 m drive blade (thermal_geometry), unchanged, closest to the drive.
- the THERMAL BULKHEAD: one V-groove radiation shield at the hot blade front (three thin specular sheets, the aft one flat, the others
  leaning forward with radius so the gaps between them open to deep space at the rim). It stops every line of sight from the hot
  blades to the cooler sections, the habitat rings and the tank farm; the forward-leaning layers vent the heat they pick up sideways
  to space, so the last layer runs near 500 K instead of the ~900 K a flat two-layer stack reaches.
- WARM: the machinery base load of the warm loop (owner warm example, 5 MW: pumps, computers, power electronics), always on. Its aft
  edge follows the last bulkhead layer (a diagonal seam), its front meets the LOW section at a 0.5 m expansion joint.
- LOW: the lowest-temperature section at the forward end, next to ring A: the tank farm's cryocoolers and the stationary avionics.

A continuous blade outline is not a continuous thermal circuit: each section has its own root booms, feed/return trunk and isolation
valves, and no sheet or coolant crosses the bulkhead or the joint. The WARM to LOW joint needs no shield: in the same blade plane the
sections cannot see each other (coplanar), and across the 120 deg wedge the 440 K section puts under 0.1 MW on the 300 K one.

Capacities use the net factor of the band-spectral Monte Carlo study (references/evidence/graded_thermal_blade.json): net rejection
after the space view, the neighbour blades, the bulkhead, every hotter section and multiple specular/diffuse bounces, at maximum drive.
Fixed: the three blade planes, root and outer radius (6.5 / 37 m, the shield shadow), the hot blade, the 44.5 m district length
(ring A and everything forward keep their stations). Every temperature, load, coating and layer value here is PROTOTYPE.
"""
import math

SIGMA = 5.670374419e-8


def cfg(s):
    return s['radiators']['zones']


def bulkhead_cfg(s):
    return cfg(s)['bulkhead']


def emitting_height_m(s):
    """Radial height of a zone sheet: root radius plus the zone root strip, out to the outer radius."""
    r = s['radiators']
    return r['outer_radius']['value']-r['root_radius']['value']-cfg(s)['root_strip_m']


def inner_radius_m(s):
    """Bulkhead inner edge: the casing radius plus the casing gap."""
    import thermal_geometry
    return thermal_geometry.casing_radius(s)+bulkhead_cfg(s)['casing_gap_m']


def layers(s):
    """Bulkhead layers aft to front: x at the inner edge and at the rim, slope, emissivity, material (ship X from RADIATOR_FRONT)."""
    import layout
    b = bulkhead_cfg(s); x = layout.origin(s, 'RADIATOR_FRONT'); r0 = inner_radius_m(s); r1 = s['radiators']['outer_radius']['value']
    out = []
    for i, L in enumerate(b['layers']):
        t = math.tan(math.radians(L['slope_deg']))
        out.append(dict(L, name=f"Radiator_Bulkhead_Layer_{i+1}", index=i+1, x_inner=x+L['offset_m'], x_rim=x+L['offset_m']+(r1-r0)*t,
                        r0=r0, r1=r1, tan=t, area_m2=math.pi*(r1*r1-r0*r0)/math.cos(math.radians(L['slope_deg']))))
    return out


def warm_aft_x(s, r):
    """WARM aft edge at radius r: the last bulkhead layer plus the clearance (the diagonal seam)."""
    last = layers(s)[-1]
    return last['x_inner']+(r-last['r0'])*last['tan']+bulkhead_cfg(s)['clearance_m']


def capacity_per_m(s, sec):
    """Net rejection per metre of mean section length, all three blades, both faces (W/m), at maximum drive."""
    z = cfg(s)
    return 3*2*emitting_height_m(s)*z['emissivity']*SIGMA*sec['T_K']**4*sec['net_factor']


def placed(s):
    """Sections front to aft with their X spans. x0/x1 are the root-line ends; WARM's aft edge is diagonal (x0_rim at the outer radius).
    mean_length_m is the length averaged over the emitting height, the one that carries capacity."""
    z = cfg(s); r = s['radiators']; r_e0 = r['root_radius']['value']+z['root_strip_m']; r1 = r['outer_radius']['value']
    secs = {x['id']: x for x in z['sections']}; last = layers(s)[-1]
    w = secs['WARM']; l = secs['LOW']
    w_x0 = last['x_inner']+z['bulkhead']['clearance_m']; w_x1 = w_x0+w['length_m']
    w_mean = w['length_m']-((r_e0+r1)/2-last['r0'])*last['tan']
    l_x0 = w_x1+z['joint_m']; l_x1 = l_x0+l['length_m']
    out = []
    for sec, x0, x1, x0r0, x0r1, mean in ((l, l_x0, l_x1, l_x0, l_x0, l['length_m']),
                                          (w, w_x0, w_x1, warm_aft_x(s, r_e0), warm_aft_x(s, r1), w_mean)):
        per = capacity_per_m(s, sec); cap = per*mean
        out.append(dict(sec, x0=x0, x1=x1, x0_root=x0r0, x0_rim=x0r1, mean_length_m=mean, per_m_W=per, capacity_W=cap,
                        margin=cap/sec['load_W']-1, planform_m2=3*mean*emitting_height_m(s)))
    return out


def sections(s):
    return placed(s)


def total_length_m(s):
    """Length of the zone district ahead of the hot blade: bulkhead, clearance, WARM, joint, LOW."""
    z = cfg(s); last = z['bulkhead']['layers'][-1]
    return last['offset_m']+z['bulkhead']['clearance_m']+sum(x['length_m'] for x in z['sections'])+z['joint_m']


def plates(s):
    """One plate per section per blade plane: X at the root and at the rim for the aft edge, X of the front edge, radii, azimuth."""
    r = s['radiators']; p = s['prototype']; z = cfg(s); out = []
    r0 = r['root_radius']['value']+z['root_strip_m']
    for sec in placed(s):
        for k in range(3):
            a = math.radians(p['radiator_phase_deg']+120*k)
            out.append(dict(name=f"Radiator_Zone_{sec['id']}_{k+1}", section=sec['id'], blade=k+1, azimuth=a, x0=sec['x0'], x1=sec['x1'],
                            x0_root=sec['x0_root'], x0_rim=sec['x0_rim'], r_root=r['root_radius']['value'], r0=r0,
                            r1=r['outer_radius']['value'], T_K=sec['T_K'], circuit=sec['circuit'], coating=z['coating']))
    return out


def bulkhead_mass_t(s):
    """First-order bulkhead mass: each layer's sheet area x its areal mass, plus a frame per layer (three spokes along the blade
    planes and a rim tension ring). PROTOTYPE judgment, not a structural sizing."""
    b = bulkhead_cfg(s); f = b['frame']; out = []
    for L in layers(s):
        sheet = L['area_m2']*L['areal_kg_m2']/1000
        frame = (3*(L['r1']-L['r0'])*f['spoke_kg_m']+2*math.pi*L['r1']*f['rim_kg_m'])/1000
        out.append(dict(layer=L['index'], sheet_t=sheet, frame_t=frame))
    return dict(layers=out, total_t=sum(x['sheet_t']+x['frame_t'] for x in out))


def check(s):
    errs = []
    z = cfg(s); ids = [x['id'] for x in z['sections']]
    if ids != ['LOW', 'WARM']:
        errs.append('radiator zones must be LOW then WARM (front to aft), ahead of the hot blade')
    ts = [x['T_K'] for x in z['sections']]+[s['radiators']['temperature']['value']]
    if any(a >= b for a, b in zip(ts, ts[1:])):
        errs.append('radiator zone temperatures must rise from front to aft')
    for sec in placed(s):
        if sec['capacity_W'] < sec['load_W']*(1+z['min_margin']):
            errs.append(f"radiator zone {sec['id']} capacity below its load plus the {z['min_margin']:.0%} design margin")
    L = layers(s)
    if len(L) < 2:
        errs.append('the thermal bulkhead needs at least two layers')
    if any(b['slope_deg'] < a['slope_deg'] for a, b in zip(L, L[1:])) or L[0]['slope_deg'] < 0:
        errs.append('bulkhead layers must open forward (V-groove): slopes non-negative and rising from aft to front')
    if any(b['x_inner'] <= a['x_inner'] for a, b in zip(L, L[1:])):
        errs.append('bulkhead layers must be ordered aft to front')
    if z['joint_m'] <= 0 or z['bulkhead']['clearance_m'] <= 0:
        errs.append('radiator zones need a joint and a bulkhead clearance')
    return errs


def report(s):
    return dict(status='PROTOTYPE (Graded Thermal Blade, RAD-ZONE; Claude under the owner delegation, brief 2026-11-01)',
                sections=[{k: (round(v, 3) if isinstance(v, float) else v) for k, v in x.items()} for x in placed(s)],
                total_length_m=total_length_m(s), bulkhead=[{k: (round(v, 3) if isinstance(v, float) else v) for k, v in x.items()} for x in layers(s)],
                bulkhead_mass=bulkhead_mass_t(s))


if __name__ == '__main__':
    import json
    import spec
    s = spec.load()[0]
    print(json.dumps(report(s), indent=1, default=str)); print('check', check(s) or 'PASS')
