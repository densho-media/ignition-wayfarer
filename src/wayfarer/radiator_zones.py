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


def membrane(s):
    """Foil thickness per layer from its areal mass and density (the modelled sheets have no thickness; this is the one they stand for)."""
    b = bulkhead_cfg(s)
    return [dict(layer=i+1, metal=f['metal'], thickness_um=L['areal_kg_m2']/f['density']*1e6) for i, (L, f) in enumerate(zip(b['layers'], b['foil']))]


def seam_angles(s, index):
    """Azimuths (rad) of the gore seams of layer `index` (1-based), from the first blade plane."""
    b = bulkhead_cfg(s); n = b['gores']; ph = math.radians(s['prototype']['radiator_phase_deg'])
    return [ph+2*math.pi*(k+b['gore_phase'][index-1])/n for k in range(n)]


def x_on(L, r):
    """Ship X of layer L at radius r (the cone through its inner edge)."""
    return L['x_inner']+(r-L['r0'])*L['tan']


def panels(s):
    """Replaceable panels, per layer per gore: radial spans between the hub, the anti-flutter hoops and the rim, azimuth span including
    the labyrinth overlap. Gores alternate high/low by the shingle step so each seam is a stepped overlap, never a straight gap."""
    b = bulkhead_cfg(s); n = b['gores']; out = []
    for L in layers(s):
        a = seam_angles(s, L['index']); edges = [L['r0']]+[r for r in b['panel_hoops_r_m'] if L['r0'] < r < L['r1']]+[L['r1']]
        for k in range(n):
            a0 = a[k]; a1 = a0+2*math.pi/n
            for m, (r0, r1) in enumerate(zip(edges, edges[1:])):
                out.append(dict(layer=L['index'], gore=k+1, panel=m+1, a0=a0, a1=a1, r0=r0, r1=r1, step=b['shingle_step_m']*(k % 2),
                                overlap_rad_r1=b['overlap_m']/r1, overlap_rad_r0=b['overlap_m']/r0, high=k % 2 == 1))
    return out


def trusses(s):
    """Radial trusses in the layer 1-2 gap along the blade planes: chord lines (aft on layer 1, forward on layer 2, less the clearance)
    sampled at the bay stations, so the depth grows from about 0.2 m at the casing to about 2.9 m at the rim."""
    b = bulkhead_cfg(s); tr = b['truss']; L1, L2 = layers(s)[:2]; out = []
    nb = max(2, round((L1['r1']-L1['r0'])/tr['bay_m']))
    rs = [L1['r0']+0.15+(L1['r1']-0.1-L1['r0']-0.15)*i/nb for i in range(nb+1)]
    for k in range(tr['count']):
        az = math.radians(s['prototype']['radiator_phase_deg']+120*k)
        aft = [(x_on(L1, r)+tr['clearance_m'], r) for r in rs]; fwd = [(x_on(L2, r)-tr['clearance_m'], r) for r in rs]
        out.append(dict(name=f"Radiator_Bulkhead_Truss_{k+1}", azimuth=az, aft=aft, fwd=fwd, depth_hub=fwd[0][0]-aft[0][0], depth_rim=fwd[-1][0]-aft[-1][0]))
    return out


def gates(s):
    """One gate per blade plane per layer at the casing, centred on the SP-51 crawler rail line (offset tangentially from the blade plane):
    azimuth span, radial span and the slid-open position of its door (radially outward, on the layer)."""
    b = bulkhead_cfg(s); g = b['gate']; out = []
    for L in layers(s):
        r0 = L['r0']+b['hub']['radius_m']*2; r1 = r0+g['radial_m']; rm = (r0+r1)/2
        for k in range(3):
            az = math.radians(s['prototype']['radiator_phase_deg']+120*k)+g['offset_m']/rm; da = g['tangential_m']/2/rm
            out.append(dict(name=f"Radiator_Bulkhead_Gate_{L['index']}_{k+1}", layer=L['index'], blade=k+1, a0=az-da, a1=az+da, az=az, r0=r0, r1=r1,
                            open_r0=r1+0.1, open_r1=r1+0.1+g['radial_m']))
    return out


def construction(s):
    """Checks of the construction that the drawn geometry has to respect (PROTOTYPE judgment values, first order):
    - thermal growth of each layer from 300 K over its radial span against the hub slide and rim joint travel;
    - seam leakage: a ray passes a shingled overlap only within atan(step/overlap) of grazing; the slot aperture per layer and the
      fraction of diffuse hot radiation arriving that close to grazing bound the leak as a fraction of the flux on the layer. Any ray
      that does pass enters the vented V-gap (it is part of the inter-layer exchange the Monte Carlo already solved) and the next
      layer's seams are staggered, so a straight leak needs two coincident slots;
    - support conduction between layers through the standoffs (truss path), against the layers' radiated power;
    - gate fit for the passing envelope."""
    b = bulkhead_cfg(s); L = layers(s); out = dict(layers=[])
    for Li, f in zip(L, b['foil']):
        dT = f['T_K']-300.0; span = Li['r1']-Li['r0']
        growth = f['cte']*dT*span; ring = 2*math.pi*Li['r1']*f['cte']*dT/b['rim']['segments']
        out['layers'].append(dict(layer=Li['index'], growth_m=growth, slide_needed_m=growth*b['slide_margin'], rim_joint_growth_m=ring,
                                  rim_joint_needed_m=ring*b['slide_margin']))
    # seams
    n = b['gores']; ang = math.atan(b['shingle_step_m']/b['overlap_m'])
    seam_len = []
    for Li in L:
        hoops = [r for r in b['panel_hoops_r_m'] if Li['r0'] < r < Li['r1']]
        seam_len.append(n*(Li['r1']-Li['r0'])+sum(2*math.pi*r for r in hoops))
    area = [Li['area_m2'] for Li in L]
    slot_frac = [sl*b['shingle_step_m']/a for sl, a in zip(seam_len, area)]
    graze = math.sin(ang)**2
    out['seams'] = dict(pass_angle_deg=math.degrees(ang), seam_length_m=seam_len, slot_aperture_fraction=slot_frac,
                        grazing_fraction_diffuse=graze, leak_bound_fraction=[f*graze for f in slot_frac])
    # conduction
    st = b['standoff']; G = st['k_W_mK']*st['area_m2']/st['length_m']; nstd = st['per_truss_layer']*b['truss']['count']
    T = [f['T_K'] for f in b['foil']]
    q12 = nstd*G*(T[0]-T[1])/2      # two standoffs in series per path (layer 1 -> truss -> layer 2)
    rad = [Li['emissivity']*SIGMA*f['T_K']**4*Li['area_m2'] for Li, f in zip(L, b['foil'])]
    out['conduction'] = dict(standoff_G_W_K=G, paths=nstd, layer1_to_2_W=q12, layer1_radiated_one_face_W=rad[0], fraction=q12/rad[0])
    g = b['gate']; u = b['gate_user_m']; m = b['gate_margin_m']
    out['gate'] = dict(clear_w_m=g['tangential_m']-u[0]-2*m, clear_d_m=g['radial_m']-u[1]-2*m)
    return out


def bulkhead_mass_t(s):
    """First-order bulkhead mass (PROTOTYPE judgment, not a structural sizing): per layer the foil (gross area incl. the labyrinth
    overlaps x areal mass), seam battens, anti-flutter hoops, rim, hub ring and brackets, gates; the three shared trusses (chords and
    web), standoffs and the layer 3 hangers."""
    b = bulkhead_cfg(s); out = []; c = construction(s)
    for Li, sl in zip(layers(s), c['seams']['seam_length_m']):
        gross = Li['area_m2']+sl*b['overlap_m']
        sheet = gross*Li['areal_kg_m2']/1000
        span = Li['r1']-Li['r0']; hoops = [r for r in b['panel_hoops_r_m'] if Li['r0'] < r < Li['r1']]
        frame = (b['gores']*span*b['tendon']['kg_m']+sum(2*math.pi*r for r in hoops)*b['hoop']['kg_m']+2*math.pi*Li['r1']*b['rim']['kg_m']
                 + 2*math.pi*Li['r0']*b['hub']['kg_m']+3*b['gate']['frame_kg'])/1000
        out.append(dict(layer=Li['index'], gross_area_m2=gross, sheet_t=sheet, frame_t=frame))
    tr = b['truss']; L1 = layers(s)[0]; span = L1['r1']-L1['r0']
    web = sum(math.hypot(r2-r1, (f2-a1)) for t in trusses(s) for (a1, r1), (f2, r2) in zip(t['aft'], t['fwd'][1:]))
    truss_t = (tr['count']*2*span*tr['chord_kg_m']+web*tr['web_kg_m']+sum(len(t['aft'])*(t['fwd'][0][0]-t['aft'][0][0]+0.5) for t in trusses(s))*tr['web_kg_m'])/1000
    hang_t = 3*round(span/b['hanger']['pitch_m'])*b['hanger']['kg']/1000
    return dict(layers=out, trusses_t=truss_t, hangers_t=hang_t, total_t=sum(x['sheet_t']+x['frame_t'] for x in out)+truss_t+hang_t)


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
    b = z['bulkhead']; c = construction(s)
    for x in c['layers']:
        if b['hub']['slide_m'] < x['slide_needed_m']:
            errs.append(f"bulkhead layer {x['layer']}: hub slide below {b['slide_margin']} x its thermal growth")
        if b['rim']['joint_travel_m'] < x['rim_joint_needed_m']:
            errs.append(f"bulkhead layer {x['layer']}: rim joint travel below {b['slide_margin']} x its segment growth")
    if min(c['gate']['clear_w_m'], c['gate']['clear_d_m']) < 0:
        errs.append('bulkhead gate smaller than the passing envelope plus margins')
    if min(t['depth_hub'] for t in trusses(s)) <= 0:
        errs.append('bulkhead truss has no depth in the layer 1-2 gap')
    if b['gore_phase'][1] == b['gore_phase'][0]:
        errs.append('layer 2 seams must be staggered against layer 1')
    if z['joint_m'] <= 0 or z['bulkhead']['clearance_m'] <= 0:
        errs.append('radiator zones need a joint and a bulkhead clearance')
    return errs


def report(s):
    return dict(status='PROTOTYPE (Graded Thermal Blade, RAD-ZONE; Claude under the owner delegation, brief 2026-11-01)',
                sections=[{k: (round(v, 3) if isinstance(v, float) else v) for k, v in x.items()} for x in placed(s)],
                total_length_m=total_length_m(s), bulkhead=[{k: (round(v, 3) if isinstance(v, float) else v) for k, v in x.items()} for x in layers(s)],
                bulkhead_mass=bulkhead_mass_t(s), membrane=membrane(s), construction=construction(s))


if __name__ == '__main__':
    import json
    import spec
    s = spec.load()[0]
    print(json.dumps(report(s), indent=1, default=str)); print('check', check(s) or 'PASS')
