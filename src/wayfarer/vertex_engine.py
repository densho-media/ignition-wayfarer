"""Vertex propulsion family, engine level (owner brief 2026-11-14). Pure, standard library only.

Two engines share one vocabulary of parts (shape, functional category, physical material, evidence class):

  research_parts(s)  Asset A, the Vertex Research Demonstrator (V4, [vertex_research]): the full-scale reference whose Feasibility Gate 2
                     verdict stays BLOCKED. Values come from the pinned research imports; drawn for reference, never linked into the ship.
  parts(s)           Asset B, the Compact Vertex Engine ([vertex_engine]): the one authoritative definition of the installed module. The
                     cluster (vertex_cluster.py) links its Blender asset four times; nothing else draws engine hardware.

Engine frame: +X forward (toward the ship), origin at the engine's forward face; the engine lies along -X; azimuth from +Y toward +Z.
Geometry, engineering and speculative performance stay in separate tables. calculations(s) states, for each scaling the compact engine
implies, the formula and the CALCULATED ratio against the research demonstrator; it never turns a smaller coil into more thrust.

`python3 src/wayfarer/vertex_engine.py` prints the engine's fit screen (stations, envelope, mass estimate, calculations).
"""
import math
from functional_colors import VERTEX_CATEGORY

MU0 = 4e-7*math.pi
TNT_J = 4.184e9                      # one tonne of TNT

# Functional categories (owner brief section 9): Blender sub-collection name and functional colour key (functional_colors.PALETTE).
CATEGORIES = {cat: (f'VTX_{cat}', fkey) for cat, fkey in VERTEX_CATEGORY.items()}
# Physical appearance per material key (RGB, roughness, metallic, emission): separate from the functional review colours.
MATERIALS = {
    'structure': ((0.20, 0.21, 0.23), 0.45, 0.85, 0.0),     # dark titanium and CFRP
    'coil': ((0.62, 0.40, 0.22), 0.35, 0.9, 0.0),           # copper-toned winding (seen in the cutaway)
    'cryostat': ((0.72, 0.73, 0.74), 0.30, 0.7, 0.0),       # bright MLI-wrapped cryostat skin
    'shield': ((0.30, 0.28, 0.26), 0.70, 0.2, 0.0),         # LiH body, dark ceramic face
    'armour': ((0.11, 0.11, 0.12), 0.55, 0.9, 0.0),         # tungsten/B4C tiles
    'hot': ((0.52, 0.34, 0.24), 0.40, 0.9, 0.0),            # lithium-loop pipework (bronze-toned refractory alloy)
    'cryo': ((0.86, 0.88, 0.90), 0.50, 0.1, 0.0),           # white-insulated cold lines
    'power': ((0.70, 0.46, 0.20), 0.35, 0.9, 0.0),          # copper bus
    'fuel': ((0.46, 0.38, 0.62), 0.40, 0.5, 0.0),           # target magazine housing
    'service': ((0.80, 0.70, 0.30), 0.50, 0.6, 0.0),        # service interfaces, safety yellow
    'sensor': ((0.18, 0.40, 0.46), 0.30, 0.6, 0.0),
    'lamp': ((0.55, 0.85, 1.00), 0.30, 0.0, 6.0),           # instrumentation indicator (deliberately lit)
}
# Effect layers (owner brief section 11): magnetic fields stay invisible; plasma, hot materials and instrumentation are separate layers.
EFFECT_COLORS = {
    'burn': (0.80, 0.62, 1.00),        # plasma violet
    'flash': (0.82, 0.90, 1.00),       # brief blue-white ignition highlight
    'plume': (0.96, 0.72, 0.92),       # pale pink plume
    'hot': (1.00, 0.45, 0.12),         # orange-hot hardware
    'driver': (0.70, 0.86, 1.00),      # driver beam paths (pulse-only)
    'ready': (0.40, 0.85, 1.00),       # coil-ready indicators (instrumentation)
}
EVIDENCE = ('CALCULATED', 'ENGINEERING_PROTOTYPE', 'SPECULATIVE')


def pol(x, r, az_deg):
    a = math.radians(az_deg)
    return (x, r*math.cos(a), r*math.sin(a))


def part(name, category, shape, material, evidence='ENGINEERING_PROTOTYPE', note='', **geo):
    assert category in CATEGORIES and evidence in EVIDENCE+('RESEARCH',), (name, category, evidence)
    return dict(name=name, category=category, shape=shape, material=material, evidence=evidence, note=note, **geo)


# ---------- the compact engine -------------------------------------------------------------------------------------------------------

def config(s):
    return s['vertex_engine']


def stations(s, scale=1.0):
    """Axial stations of the compact engine (engine frame). `scale` is the study's module-size factor (vertex_cluster.study); the built
    engine uses 1."""
    g = config(s)['geometry']
    collar_f = g['collar_x_m']*scale
    collar_a = collar_f-g['collar_length_m']*scale
    shield_a = collar_a-g['shield_thickness_m']*scale
    burn = shield_a-g['standoff_m']*scale
    coils = [dict(c, x=shield_a+c['dx_from_shield_m']*scale, r=c['r_m']*scale) for c in g['closure_coils']]
    loops = [dict(l, x=burn+l['dx_from_burn_m']*scale, r=l['r_m']*scale) for l in g['loops']]
    return dict(front=0.0, nose=-g['nose_length_m']*scale, cartridge_aft=-g['cartridge_length_m']*scale, collar_fwd=collar_f, collar_aft=collar_a,
                shield_fwd=collar_a, shield_aft=shield_a, burn=burn, coils=coils, loops=loops, exit=loops[-1]['x'])


def cage_points(s, scale=1.0):
    """(x, r) path of one nozzle-cage longeron: collar, shield rim, then outside each loop's cryostat."""
    g = config(s)['geometry']; st = stations(s, scale); c = g['cage_clearance_m']
    pts = [(st['collar_aft'], g['collar_outer_radius_m']*scale-0.3)]
    pts += [(l['x'], l['r']+l['cryostat_minor_m']*scale+c) for l in st['loops']]
    return pts


def parts(s, scale=1.0):
    """Every drawn part of the compact engine (engine frame). Category, physical material and evidence travel with each part."""
    g = config(s)['geometry']; st = stations(s, scale); k = scale; out = []
    R = lambda v: v*k
    cr = g['cartridge_radius_m']*k
    # --- structure: cartridge shell, nose, thrust collar, cage, coil struts, reaction ring ---
    out.append(part('VTX_Cartridge_Shell', 'STRUCTURE', 'revolve', 'structure',
                    note='Drive cartridge pressure-free shell: pulse conditioning, target magazine and launcher breech inside',
                    profile=[(st['nose'], cr), (st['cartridge_aft'], cr)], closed=False, n=32))
    out.append(part('VTX_Nose', 'STRUCTURE', 'revolve', 'structure', note='Forward service nose (cartridge access hatch on the axis)',
                    profile=[(st['front'], cr*0.45), (st['front']-R(0.35), cr*0.82), (st['nose'], cr)], closed=False, cap_front=True, n=32))
    out.append(part('VTX_Thrust_Collar', 'STRUCTURE', 'revolve', 'structure',
                    note='Thrust collar: cage longerons and the four trunnions meet here; all engine loads leave through it',
                    profile=[(st['collar_fwd'], cr), (st['collar_fwd'], R(g['collar_outer_radius_m'])), (st['collar_aft'], R(g['collar_outer_radius_m'])),
                             (st['collar_aft'], cr*0.9)], closed=True, n=48))
    for j in range(g['cage_longerons']):
        az = 22.5+j*360/g['cage_longerons']
        out.append(part(f'VTX_Cage_Longeron_{j+1}', 'STRUCTURE', 'tube', 'structure',
                        note='Nozzle cage longeron: loop thrust and hoop-support loads to the collar',
                        points=[pol(x, r, az) for x, r in cage_points(s, scale)], radius=R(g['cage_longeron_radius_m'])))
    for i, l in enumerate(st['loops']):
        rr = l['r']+l['cryostat_minor_m']*k+g['cage_clearance_m']
        out.append(part(f'VTX_Cage_Hoop_{l["name"]}', 'STRUCTURE', 'torus', 'structure', note=f'Cage hoop at {l["name"]}: carries the loop seats',
                        x=l['x'], R=rr, a=R(0.12), nu=48, nv=6))
        for j in range(g['cage_longerons']):
            az = 22.5+j*360/g['cage_longerons']
            out.append(part(f'VTX_Loop_Seat_{l["name"]}_{j+1}', 'STRUCTURE', 'tube', 'structure', note=f'{l["name"]} cryostat seat (cold-mass support behind)',
                            points=[pol(l['x'], l['r']+l['cryostat_minor_m']*k, az), pol(l['x'], rr, az)], radius=R(0.10), n=6))
    ring_r = R(g['shield_aft_radius_m'])-R(0.45)
    out.append(part('VTX_Coil_Reaction_Ring', 'STRUCTURE', 'torus', 'structure', note='Reaction ring on the shield aft face: C1/C2 axial force into the collar (research ISS-003)',
                    x=st['shield_aft']-R(0.15), R=ring_r, a=R(0.15), nu=48, nv=6))
    for c in st['coils']:
        for j in range(g['coil_struts_per_coil']):
            az = 30+j*360/g['coil_struts_per_coil']+(0 if c['name'] == 'C1' else 30)
            out.append(part(f'VTX_{c["name"]}_Strut_{j+1}', 'STRUCTURE', 'tube', 'structure',
                            note=f'{c["name"]} -> shield reaction ring compression strut (inter-coil attraction); unsized',
                            points=[pol(c['x'], c['r'], az), pol(st['shield_aft']-R(0.15), ring_r, az)], radius=R(g['coil_strut_radius_m'])))
    # --- shielding: conical shadow shield, burn face, armour shoes ---
    out.append(part('VTX_Shadow_Shield', 'SHIELDING', 'revolve', 'shield', note='Conical LiH shadow shield; everything forward sits in its shadow cone',
                    profile=[(st['shield_fwd'], 0.0), (st['shield_fwd'], R(g['shield_forward_radius_m'])), (st['shield_aft'], R(g['shield_aft_radius_m'])), (st['shield_aft'], 0.0)],
                    closed=True, n=48))
    out.append(part('VTX_Shield_Burn_Face', 'SHIELDING', 'revolve', 'armour', note='W/B4C burn face (renewable tiles)',
                    profile=[(st['shield_aft']+R(0.02), 0.0), (st['shield_aft']+R(0.02), R(g['shield_aft_radius_m'])-R(0.05)), (st['shield_aft']-R(0.12), R(g['shield_aft_radius_m'])-R(0.15)), (st['shield_aft']-R(0.12), 0.0)],
                    closed=True, n=48))
    bx, n = st['burn'], g['segments_per_loop']
    for i, l in enumerate(st['loops']):
        clock = 22.5*i; gap = g['segment_gap_deg']
        phi = math.atan2(l['r'], l['x']-bx)          # direction from the burn point in the (x, r) plane, measured from +x
        off = l['cryostat_minor_m']*k+R(g['armour_offset_m'])+R(g['armour_minor_m'])
        sx, sr = l['x']-off*math.cos(phi), l['r']-off*math.sin(phi)
        for j in range(n):
            a0 = clock+360*j/n+gap/2; a1 = a0+360/n-gap
            out.append(part(f'VTX_{l["name"]}_Armour_{j+1:02}', 'SHIELDING', 'torus', 'armour',
                            note=f'{l["name"]} burn-facing armour shoe, exchange unit {j+1}/{n}', x=sx, R=sr, a=R(g['armour_minor_m']), arc=(a0, a1), nu=10, nv=8))
    for c in st['coils']:
        phi = math.atan2(c['r'], c['x']-bx); off = c['cryostat_minor_m']*k+R(0.12)
        out.append(part(f'VTX_{c["name"]}_LiH_Nose', 'SHIELDING', 'torus', 'shield', note=f'{c["name"]} burn-facing LiH neutron screen (research ISS-014)',
                        x=c['x']-off*math.cos(phi), R=c['r']-off*math.sin(phi), a=R(0.16), nu=48, nv=8))
    # --- magnetic coils (closure set) and nozzle loops ---
    for c in st['coils']:
        out.append(part(f'VTX_{c["name"]}_Winding', 'MAGNETIC_COILS', 'torus', 'coil', note=f'Closure coil {c["name"]} winding pack (REBCO, inside its cryostat)',
                        x=c['x'], R=c['r'], a=R(c['winding_minor_m']), nu=48, nv=8))
        out.append(part(f'VTX_{c["name"]}_Cryostat', 'MAGNETIC_COILS', 'torus', 'cryostat', note=f'Closure coil {c["name"]} cryostat and warm eddy screen',
                        x=c['x'], R=c['r'], a=R(c['cryostat_minor_m']), nu=48, nv=10, hollow=True))
    for i, l in enumerate(st['loops']):
        clock = 22.5*i; gap = g['segment_gap_deg']
        out.append(part(f'VTX_{l["name"]}_Winding', 'MAGNETIC_NOZZLE', 'torus', 'coil', note=f'Nozzle loop {l["name"]} winding pack',
                        x=l['x'], R=l['r'], a=R(l['winding_minor_m']), nu=48, nv=8))
        for j in range(n):
            a0 = clock+360*j/n+gap/2; a1 = a0+360/n-gap
            out.append(part(f'VTX_{l["name"]}_Segment_{j+1:02}', 'MAGNETIC_NOZZLE', 'torus', 'cryostat',
                            note=f'{l["name"]} replaceable cryostat segment {j+1}/{n}; joints clocked {clock:g} deg',
                            x=l['x'], R=l['r'], a=R(l['cryostat_minor_m']), arc=(a0, a1), nu=10, nv=10))
        for j in range(n):
            az = clock+360*j/n
            out.append(part(f'VTX_{l["name"]}_Joint_{j+1:02}', 'MAGNETIC_NOZZLE', 'torus_section', 'structure',
                            note=f'{l["name"]} segment joint flange (exchange split)', x=l['x'], R=l['r'], a=R(l['cryostat_minor_m'])+R(0.07), az=az, width=R(0.18), nv=12))
    # --- fusion reaction and target injection ---
    out.append(part('VTX_Burn_Chamber_Marker', 'FUSION_REACTION', 'sphere', 'sensor', evidence='ENGINEERING_PROTOTYPE',
                    note='Burn point fiducial (no hardware here: the burn happens in the open field)', center=(bx, 0, 0), radius=R(0.12), n=8))
    lx0, lx1 = [v*k for v in g['launcher_x_m']]
    out.append(part('VTX_Target_Launcher', 'TARGET_INJECTION', 'tube', 'structure', note='Target launcher barrel on the engine axis (research VTX-01H)',
                    points=[(lx0, 0, 0), (lx1, 0, 0)], radius=R(g['launcher_radius_m'])))
    out.append(part('VTX_Target_Bore', 'TARGET_INJECTION', 'tube', 'armour', note='Target bore through the shadow shield (streaming path, plugged between pulses)',
                    points=[(st['shield_fwd'], 0, 0), (st['shield_aft']-R(0.02), 0, 0)], radius=R(g['bore_radius_m'])))
    out.append(part('VTX_Sabot_Catcher', 'TARGET_INJECTION', 'torus', 'armour', note='Annular sabot trap at the bore exit',
                    x=st['shield_aft']-R(0.2), R=R(0.55), a=R(0.13), nu=24, nv=6))
    out.append(part('VTX_Driver_Final_Stage', 'TARGET_INJECTION', 'revolve', 'power', note='Driver final amplifier ring around the breech (pulse energy into the six beam lines)',
                    profile=[(st['cartridge_aft']+R(1.6), R(1.0)), (st['cartridge_aft']+R(1.6), R(2.9)), (st['cartridge_aft']+R(0.2), R(2.9)), (st['cartridge_aft']+R(0.2), R(1.0))], closed=True, n=32))
    for j in range(g['driver_ports']):
        az = 60*j
        port_aft = pol(st['shield_aft'], R(g['driver_port_radius_m']), az)
        port_fwd = pol(st['shield_fwd'], R(g['driver_port_radius_m'])*1.05, az)
        out.append(part(f'VTX_Driver_Port_{j+1}', 'TARGET_INJECTION', 'tube', 'armour', note='Final-focus beam port through the shield, aimed at the burn point',
                        points=[port_fwd, port_aft], radius=R(g['driver_port_tube_m'])))
        out.append(part(f'VTX_Driver_Optic_{j+1}', 'TARGET_INJECTION', 'disc', 'sensor', note='Sacrificial final optic (renewed with the burn face)',
                        center=(st['shield_aft']-R(0.04), port_aft[1], port_aft[2]), radius=R(0.32), depth=R(0.06), n=12))
    # --- fuel: magazine and feed ---
    out.append(part('VTX_Target_Magazine', 'FUEL', 'revolve', 'fuel', note='D-3He target magazine around the launcher breech',
                    profile=[(R(-2.2), R(0.5)), (R(-2.2), R(1.7)), (R(-5.6), R(1.7)), (R(-5.6), R(0.5))], closed=True, n=32))
    # --- electrical: pulse pods, coil current leads ---
    px, pr, pt = [v*k for v in g['pulse_pod_size_m']]
    for j in range(g['pulse_pods']):
        az = 90*j
        out.append(part(f'VTX_Pulse_Pod_{j+1}', 'ELECTRICAL', 'box', 'power', note='Pulsed-power pod: one pulse train of driver energy',
                        center=pol(st['cartridge_aft']+R(0.7)+px/2, cr+pr/2, az), size=(px, pr, pt), az=az))
    # --- service: trunnions, panel, handling posts, hatch, rails ---
    for j, az in enumerate(g['trunnion_azimuths_deg']):
        out.append(part(f'VTX_Trunnion_{j+1}', 'SERVICE', 'box', 'service', note='Trunnion lug: pinned to the cluster cradle; released for engine exchange',
                        center=pol((st['collar_fwd']+st['collar_aft'])/2, R(g['collar_outer_radius_m'])+R(0.35), az), size=(R(1.0), R(0.7), R(0.9)), az=az))
    paz = g['service_panel_azimuth_deg']
    out.append(part('VTX_Service_Panel', 'SERVICE', 'box', 'service', note='Quick-disconnect panel: target feed, lithium supply/return, cryogen, power bus, data',
                    center=pol((st['collar_fwd']+st['collar_aft'])/2, R(g['collar_outer_radius_m'])+R(0.25), paz), size=(R(1.2), R(0.5), R(2.4)), az=paz))
    out.append(part('VTX_Nose_Hatch', 'SERVICE', 'disc', 'service', note='Cartridge access hatch', center=(st['front']+R(0.02), 0, 0), radius=cr*0.42, depth=R(0.08)))
    for j in range(4):
        az = 45+90*j
        out.append(part(f'VTX_Handling_Post_{j+1}', 'SERVICE', 'tube', 'service', note='Handling post for the exchange fixture',
                        points=[pol(st['nose']+R(0.3), cr, az), pol(st['nose']+R(0.3), cr+R(0.6), az)], radius=R(0.12)))
    for j in (3, 7):
        az = 22.5+j*360/g['cage_longerons']
        pts = [(x, r+R(0.38)) for x, r in cage_points(s, scale)]
        out.append(part(f'VTX_Exchange_Rail_{j+1}', 'SERVICE', 'tube', 'service', note='Segment exchange rail on the cage (crawler path between burns)',
                        points=[pol(x, r, az+3.0) for x, r in pts], radius=R(0.07)))
    # --- hot thermal: lithium manifold and armour feeders ---
    hx = st['shield_fwd']-R(0.8); hr = R(g['collar_outer_radius_m'])+R(0.15)
    out.append(part('VTX_Lithium_Manifold', 'HOT_THERMAL', 'torus', 'hot', note='Lithium loop ring manifold (armour, shield face and coil noses)',
                    x=hx, R=hr, a=R(0.20), nu=48, nv=8))
    for j, tag in ((0, 'Supply'), (4, 'Return')):
        az = 22.5+j*360/g['cage_longerons']
        pts = [(x, r-R(0.42)) for x, r in cage_points(s, scale)]
        out.append(part(f'VTX_Lithium_{tag}', 'HOT_THERMAL', 'tube', 'hot', note=f'Lithium {tag.lower()} feeder along the cage to every armour ring',
                        points=[pol(hx, hr, az)]+[pol(x, r, az) for x, r in pts], radius=R(0.11)))
    for tag, dz in (('Supply', -0.5), ('Return', 0.5)):
        out.append(part(f'VTX_Lithium_Panel_{tag}', 'HOT_THERMAL', 'tube', 'hot', note=f'Lithium {tag.lower()} between the manifold and the service panel',
                        points=[(hx, -hr, R(dz)), (st['collar_aft']+R(0.1), -hr, R(dz)), (st['collar_aft']+R(0.1), -R(g['collar_outer_radius_m'])-R(0.3), R(dz))], radius=R(0.12)))
    # --- cryogenic: header and coil feeds ---
    cx = st['collar_aft']-R(0.35); crr = R(g['collar_outer_radius_m'])+R(0.55)
    out.append(part('VTX_Cryo_Header', 'CRYOGENIC', 'torus', 'cryo', note='Coil cryogen header (separate cold loop)', x=cx, R=crr, a=R(0.10), nu=48, nv=6))
    for j in (2, 6):
        az = 22.5+j*360/g['cage_longerons']
        pts = [(x, r-R(0.32)) for x, r in cage_points(s, scale)]
        out.append(part(f'VTX_Cryo_Feed_{j+1}', 'CRYOGENIC', 'tube', 'cryo', note='Cryogen feed to the loop cryostats',
                        points=[pol(cx, crr, az)]+[pol(x, r, az) for x, r in pts], radius=R(0.07)))
    for c in st['coils']:
        out.append(part(f'VTX_Cryo_Feed_{c["name"]}', 'CRYOGENIC', 'tube', 'cryo', note=f'Cryogen feed to {c["name"]} along its strut',
                        points=[pol(cx, crr, 270), pol(st['shield_aft']-R(0.3), R(g['shield_aft_radius_m'])+R(0.15), 270), pol(c['x'], c['r']+c['cryostat_minor_m']*k, 270)], radius=R(0.06)))
    # --- electrical: coil current leads ---
    az = 22.5+1*360/g['cage_longerons']
    pts = [(x, r-R(0.42)) for x, r in cage_points(s, scale)]
    out.append(part('VTX_Coil_Current_Leads', 'ELECTRICAL', 'tube', 'power', note='Coil current leads (HTS) from the panel along the cage',
                    points=[pol(st['collar_aft'], R(g['collar_outer_radius_m']), az)]+[pol(x, r, az) for x, r in pts], radius=R(0.09)))
    out.append(part('VTX_Power_Bus', 'ELECTRICAL', 'tube', 'power', note='Driver and pulse-pod bus from the service panel',
                    points=[(st['collar_fwd']+R(0.1), -R(g['collar_outer_radius_m'])-R(0.3), R(1.0)), (st['collar_fwd']+R(0.4), -cr-R(0.5), R(1.0)), (st['cartridge_aft']+R(6.0), -cr-R(0.5), R(1.0))], radius=R(0.12)))
    # --- instrumentation: diagnostics and indicator lamps ---
    l1 = st['loops'][0]
    for j in range(4):
        az = 45+90*j
        out.append(part(f'VTX_Diagnostic_Head_{j+1}', 'INSTRUMENTATION', 'box', 'sensor', note='Burn diagnostics head on L1 (X-ray, neutron, field probes)',
                        center=pol(l1['x']+R(0.6), l1['r']+l1['cryostat_minor_m']*k+R(0.3), az), size=(R(0.6), R(0.5), R(0.5)), az=az))
    for j in range(4):
        az = 90*j
        out.append(part(f'VTX_Status_Lamp_{j+1}', 'INSTRUMENTATION', 'sphere', 'lamp', note='Status indicator (deliberately lit instrumentation)',
                        center=pol(st['collar_fwd']+R(0.05), R(g['collar_outer_radius_m'])-R(0.25), az), radius=R(0.14), n=6))
    out += refinements(s, scale)
    return out


def refinements(s, scale=1.0):
    """Vertex Engine 1.1 (owner brief 2026-11-14, mechanical register ME-01..ME-04): parts that close a load path, a circuit or the target
    path the 1.0 engine left open. Every part joins an existing (category, material) family, so the built asset keeps its object count.
    All ENGINEERING_PROTOTYPE and unsized: the shapes say where things connect, not how strong or how large they must be."""
    g = config(s)['geometry']; st = stations(s, scale); k = scale; out = []
    R = lambda v: v*k
    sa, sf = st['shield_aft'], st['shield_fwd']
    # ME-01 shield tie rods: the coil reaction ring's load goes round the LiH shield (not structural) to the thrust collar.
    ring_r = R(g['shield_aft_radius_m'])-R(0.45)
    for j in range(8):
        az = 11.25+45*j
        out.append(part(f'VTX_Shield_Tie_Rod_{j+1}', 'STRUCTURE', 'tube', 'structure',
                        note='Shield tie rod: C1/C2 reaction-ring load around the LiH shield into the thrust collar (the shield carries no coil load)',
                        points=[pol(sa-R(0.15), ring_r, az), pol(sa+R(0.15), R(g['shield_aft_radius_m'])+R(0.22), az),
                                pol(sf, R(g['shield_forward_radius_m'])+R(0.22), az)], radius=R(0.12), n=6))
    # ME-02 lead and cryogen turrets: every coil gets its current leads and its cryogen at one turret on the cryostat.
    cx = st['collar_aft']-R(0.35); crr = R(g['collar_outer_radius_m'])+R(0.55)
    for c in st['coils']:
        rt = c['r']+c['cryostat_minor_m']*k
        out.append(part(f'VTX_{c["name"]}_Lead_Turret', 'ELECTRICAL', 'box', 'power',
                        note=f'{c["name"]} lead turret: HTS current leads and the cryogen port enter the cryostat here (vacuum break, 80 K intercept)',
                        center=pol(c['x'], rt+R(0.2), 270), size=(R(0.7), R(0.45), R(0.8)), az=270))
        out.append(part(f'VTX_{c["name"]}_Lead_Branch', 'ELECTRICAL', 'tube', 'power', note=f'{c["name"]} current-lead pair from the collar to its turret',
                        points=[pol(st['collar_aft'], R(g['collar_outer_radius_m'])-R(0.4), 263), pol(sa-R(0.3), R(g['shield_aft_radius_m'])+R(0.15), 263),
                                pol(c['x']+R(0.25), rt+R(0.3), 265)], radius=R(0.06), n=6))
    for l in st['loops']:
        cm = l['cryostat_minor_m']*k; rt = l['r']+cm
        out.append(part(f'VTX_{l["name"]}_Lead_Turret', 'ELECTRICAL', 'box', 'power',
                        note=f'{l["name"]} lead turret: current leads and cryogen enter the loop cryostat between two seats',
                        center=pol(l['x'], rt+R(0.2), 90.0), size=(R(0.9), R(0.45), R(0.7)), az=90.0))
        out.append(part(f'VTX_{l["name"]}_Lead_Branch', 'ELECTRICAL', 'tube', 'power', note=f'{l["name"]} leads from the cage lead line to its turret',
                        points=[pol(l['x']-R(0.25), rt+R(0.12), a) for a in (67.5, 75.0, 82.5, 88.0)], radius=R(0.06), n=6))
        out.append(part(f'VTX_{l["name"]}_Cryo_Branch', 'CRYOGENIC', 'tube', 'cryo', note=f'{l["name"]} cryogen branch from the cage feed to its turret',
                        points=[pol(l['x']+R(0.25), rt+R(0.12), a) for a in (112.5, 105.0, 97.5, 92.0)], radius=R(0.06), n=6))
    # ME-03 armour coolant headers: the lithium supply and return reach every armour ring, so the hot circuit closes.
    bx = st['burn']
    for l in st['loops']:
        cm = l['cryostat_minor_m']*k
        phi = math.atan2(l['r'], l['x']-bx); off = cm+R(g['armour_offset_m'])+R(g['armour_minor_m'])
        sx, sr = l['x']-off*math.cos(phi), l['r']-off*math.sin(phi)
        t = (-math.sin(phi), math.cos(phi)) if math.cos(phi) >= 0 else (math.sin(phi), -math.cos(phi))
        d = R(g['armour_minor_m'])+R(0.1)
        hx_, hr_ = sx+d*t[0], sr+d*t[1]
        out.append(part(f'VTX_{l["name"]}_Armour_Header', 'HOT_THERMAL', 'torus', 'hot',
                        note=f'{l["name"]} armour coolant header: lithium to and from every shoe of the ring (hot circuit, about 1800 K class)',
                        x=hx_, R=hr_, a=R(0.08), nu=32, nv=4))
        # jumper: around the cryostat section, never through it
        th0 = math.pi/2; th1 = math.atan2(hr_-l['r'], hx_-l['x'])
        if th1 < -math.pi/2:
            th1 += 2*math.pi
        rad = cm+R(0.16)
        arc = [(l['x']+rad*math.cos(th0+(th1-th0)*i/4), l['r']+rad*math.sin(th0+(th1-th0)*i/4)) for i in range(5)]
        for tag, az in (('Supply', 22.5), ('Return', 202.5)):
            out.append(part(f'VTX_{l["name"]}_Lithium_{tag}_Jumper', 'HOT_THERMAL', 'tube', 'hot',
                            note=f'{l["name"]} lithium {tag.lower()} jumper from the cage feeder to the armour header',
                            points=[pol(l['x'], l['r']+cm+R(0.03), az)]+[pol(x, r, az+4.0) for x, r in arc]+[pol(hx_, hr_, az+4.0)], radius=R(0.07), n=6))
    # ME-04 target path: magazine -> transfer -> breech; the launcher is aligned at its muzzle; the bore closes between pulses.
    out.append(part('VTX_Target_Transfer', 'FUEL', 'tube', 'fuel', note='Target transfer: the magazine indexes one target into the launcher breech',
                    points=[pol(R(-2.2), R(1.1), 0), pol(R(-1.95), R(1.1), 0), pol(R(-1.75), R(0.45), 0)], radius=R(0.12), n=6))
    lx = R(-7.2)
    out.append(part('VTX_Launcher_Alignment_Ring', 'TARGET_INJECTION', 'torus', 'structure',
                    note='Launcher alignment ring at the muzzle: three actuators trim the barrel onto the bore axis between bursts',
                    x=lx, R=R(0.62), a=R(0.08), nu=24, nv=4))
    for j in range(3):
        az = 90+120*j
        out.append(part(f'VTX_Launcher_Actuator_{j+1}', 'TARGET_INJECTION', 'tube', 'structure', note='Alignment actuator (muzzle ring to the cartridge frame)',
                        points=[pol(lx, R(0.62), az), pol(lx+R(0.8), R(1.55), az)], radius=R(0.06), n=6))
    out.append(part('VTX_Bore_Shutter', 'TARGET_INJECTION', 'disc', 'armour', note='Bore shutter on the burn face: closes the target bore between pulses',
                    center=(sa-R(0.17), 0, 0), radius=R(0.38), depth=R(0.05), n=16))
    return out


def interfaces(s, scale=1.0):
    """Named interface points of the engine (engine frame): mounts, the panel's five services, the thrust line and the removal axis."""
    g = config(s)['geometry']; st = stations(s, scale); k = scale
    mid = (st['collar_fwd']+st['collar_aft'])/2; ro = g['collar_outer_radius_m']*k
    out = [dict(name=f'IF_VTX_TRUNNION_{j+1}', at=pol(mid, ro+0.7*k, az), kind='mount', note='Trunnion pin seat: thrust and magnetic loads to the cradle')
           for j, az in enumerate(g['trunnion_azimuths_deg'])]
    paz = g['service_panel_azimuth_deg']
    for j, svc in enumerate(('TARGET_FEED', 'LITHIUM_SUPPLY', 'LITHIUM_RETURN', 'CRYOGEN', 'POWER', 'DATA')):
        p = pol(mid, ro+0.5*k, paz)
        out.append(dict(name=f'IF_VTX_{svc}', at=(p[0], p[1], p[2]+(j-2.5)*0.36*k), kind='service', note=f'{svc.replace("_", " ").lower()} at the quick-disconnect panel'))
    out += [dict(name='IF_VTX_BURN_POINT', at=(st['burn'], 0, 0), kind='reaction', note='Target burn point (open field, no hardware)'),
            dict(name='IF_VTX_THRUST_LINE', at=(st['burn'], 0, 0), kind='thrust', note='Thrust acts along the engine axis (+X on the ship)'),
            dict(name='IF_VTX_REMOVAL_AXIS', at=(st['exit'], 0, 0), kind='service', note='Engine leaves aft along its axis once the trunnions and the panel are released'),
            dict(name='IF_VTX_EXIT', at=(st['exit'], 0, 0), kind='thrust', note='Collimation loop L4: the plume leaves here')]
    return out


def effects(s, scale=1.0):
    """The one shared effect definition (engine frame): every engine instance draws these and drives them from its own channel
    (vertex_cluster.drivers). Plasma colours are an artistic display, not a measured or simulated spectrum."""
    g = config(s)['geometry']; st = stations(s, scale); k = scale; bx = st['burn']; L = st['loops']
    plume_len = 55.0*k
    out = [dict(name='FX_BURN_CORE', layer='plasma', channel='burn', shape='sphere', center=(bx, 0, 0), radius=0.7*k, color=EFFECT_COLORS['burn'], strength=12.0,
                note='Burn core: plasma emission at the target (display)'),
           dict(name='FX_PLASMA_SHELL', layer='plasma', channel='burn', shape='sphere', center=(bx, 0, 0), radius=0.62*g['standoff_m']*k, color=EFFECT_COLORS['burn'],
                strength=1.2, alpha=0.18, note='Expanding plasma shell turned by the loop field (display; magnetic field itself invisible)'),
           dict(name='FX_IGNITION_FLASH', layer='plasma', channel='flash', shape='sphere', center=(bx, 0, 0), radius=1.8*k, color=EFFECT_COLORS['flash'], strength=20.0,
                note='Brief blue-white highlight while the burn starts and stops (display)'),
           dict(name='FX_PLUME', layer='plasma', channel='plume', shape='plume', origin=(L[-1]['x'], 0, 0),
                profile=[(L[1]['x']-L[-1]['x'], 2.2*k), (L[2]['x']-L[-1]['x'], 3.6*k), (0.0, 5.2*k), (-plume_len*0.35, 8.0*k), (-plume_len, 12.5*k)],
                color=EFFECT_COLORS['plume'], strength=2.0, alpha=0.32, note='Detached exhaust plume; length follows the display throttle'),
           dict(name='FX_DRIVER_BEAMS', layer='plasma', channel='driver', shape='beams',
                beams=[(pol(st['shield_aft'], g['driver_port_radius_m']*k, 60*j), (bx, 0, 0)) for j in range(g['driver_ports'])], radius=0.05*k,
                color=EFFECT_COLORS['driver'], strength=6.0, note='Driver pulses to the target (display, pulse-only)')]
    for l in L:
        phi = math.atan2(l['r'], l['x']-bx); off = l['cryostat_minor_m']*k+g['armour_offset_m']*k+g['armour_minor_m']*k
        out.append(dict(name=f'FX_HOT_{l["name"]}', layer='hot', channel='hot', shape='torus', x=l['x']-off*math.cos(phi), R=l['r']-off*math.sin(phi),
                        a=g['armour_minor_m']*k*1.08, color=EFFECT_COLORS['hot'], strength=3.0, note=f'{l["name"]} armour glowing hot (temperature emission, decays after shutdown)'))
    out.append(dict(name='FX_HOT_SHIELD_FACE', layer='hot', channel='hot', shape='disc', center=(st['shield_aft']-0.14*k, 0, 0), radius=g['shield_aft_radius_m']*k-0.2*k,
                    depth=0.04*k, color=EFFECT_COLORS['hot'], strength=2.0, note='Shield burn face glowing hot'))
    for l in L:
        out.append(dict(name=f'FX_READY_{l["name"]}', layer='instrumentation', channel='ready', shape='markers', x=l['x'], r=l['r']+l['cryostat_minor_m']*k+0.05*k,
                        count=4, size=0.16*k, color=EFFECT_COLORS['ready'], strength=8.0, note=f'{l["name"]} field-ready indicators (coils energised)'))
    return out


# ---------- the research demonstrator ------------------------------------------------------------------------------------------------

def research_parts(s):
    """Asset A, V4 (engine frame: origin on the equipment module's forward face, which is Wayfarer's aft datum). The drawn subset: module,
    shield, closure coils C1/C2 with their research envelopes, three loops in 12 replaceable segments, loop struts, launcher, galleries,
    the X-ray stand-off sphere and the burn point. Warm wings, tank farm and skirt are ship-level research items and stay on the branches."""
    r = s['vertex_research']; out = []
    sf, sa = -r['module_length_m'], -r['module_length_m']-r['shield_thickness_m']; bx = r['burn_x_local_m']
    out.append(part('VRD_Equipment_Module', 'STRUCTURE', 'revolve', 'structure', 'RESEARCH', note='Equipment module X -180.75 to -144.75 (research 01C)',
                    profile=[(0.0, r['module_radius_m']), (sf, r['module_radius_m'])], closed=False, n=48))
    out.append(part('VRD_Shadow_Shield', 'SHIELDING', 'revolve', 'shield', 'RESEARCH', note=f'Shadow shield r {r["shield_radius_m"]} m, {r["shield_t"]:.0f} t (research 06A)',
                    profile=[(sf, 0.0), (sf, r['shield_radius_m']), (sa, r['shield_radius_m']), (sa, 0.0)], closed=True, n=48))
    for c in r['closure_coils']:
        out.append(part(f'VRD_{c["name"]}_Winding', 'MAGNETIC_COILS', 'torus', 'coil', 'RESEARCH', note=f'Closure coil {c["name"]} (research VTX-03D, T03 C_W15)',
                        x=c['x_local_m'], R=c['r_m'], a=max(c['winding_minor_m'], 0.3), nu=96, nv=10))
        out.append(part(f'VRD_{c["name"]}_Envelope', 'MAGNETIC_COILS', 'torus', 'cryostat', 'RESEARCH', note='Research cryostat and screen envelope',
                        x=c['x_local_m'], R=c['r_m'], a=c['envelope_m'][1], nu=96, nv=12, hollow=True))
    for i, l in enumerate(r['loops']):
        clock = 45.0*i; n = r['replaceable_segments_per_loop']
        for j in range(n):
            a0 = clock+360*j/n+0.3; a1 = a0+360/n-0.6
            out.append(part(f'VRD_{l["name"]}_Segment_{j+1:02}', 'MAGNETIC_NOZZLE', 'torus', 'cryostat', 'RESEARCH',
                            note=f'{l["name"]} segment {j+1}/{n} (research VTX-03E)', x=l['x_local_m'], R=l['r_m'], a=max(l['envelope_m'], 0.6)*1.6, arc=(a0, a1), nu=16, nv=10))
        for j in range(r['loop_struts_per_loop']):
            az = 360*j/r['loop_struts_per_loop']+15*i
            out.append(part(f'VRD_{l["name"]}_Strut_{j+1}', 'STRUCTURE', 'tube', 'structure', 'RESEARCH', note='Loop strut to the shield frame (research 02D, unbooked GN loads)',
                            points=[pol(l['x_local_m'], l['r_m'], az), pol(sa, r['shield_radius_m'], az)], radius=0.43))
    out.append(part('VRD_Target_Launcher', 'TARGET_INJECTION', 'tube', 'structure', 'RESEARCH', note='Launcher barrel 20 m PR (research 01H)',
                    points=[(sf+r['launcher_barrel_m'], 0, 0), (sf+0.2, 0, 0)], radius=0.6))
    for az in r['driver_galleries_deg']:
        out.append(part(f'VRD_Driver_Gallery_{az:g}', 'ELECTRICAL', 'tube', 'power', 'RESEARCH', note='Driver gallery (research 01B)',
                        points=[pol(0.0, 4.5, az), pol(sf, 4.5, az)], radius=1.0))
    out.append(part('VRD_Burn_Point', 'FUSION_REACTION', 'sphere', 'sensor', 'RESEARCH', note='Burn point', center=(bx, 0, 0), radius=1.5, n=12))
    out.append(part('VRD_Standoff_Sphere', 'FUSION_REACTION', 'sphere', 'cryostat', 'RESEARCH', note=f'X-ray stand-off R_s {sa-bx:.1f} m (research 01, 06)',
                    center=(bx, 0, 0), radius=sa-bx, n=32, ghost=True))
    return out


# ---------- meshes (pure: vertices and faces in the engine frame) ---------------------------------------------------------------------

def _revolve(profile, n, closed, arc=None):
    a0, a1 = (0.0, 360.0) if arc is None else arc
    full = arc is None
    cols = n if full else max(2, int(n*(a1-a0)/360)+1)
    angs = [math.radians(a0+(a1-a0)*j/(cols if full else cols-1)) for j in range(cols)]
    vs = [(x, r*math.cos(a), r*math.sin(a)) for x, r in profile for a in angs]
    m = len(angs); rows = len(profile); fs = []
    for i in range(rows-1+(1 if closed else 0)):
        i2 = (i+1) % rows
        for j in range(m if full else m-1):
            j2 = (j+1) % m
            fs.append((i*m+j, i*m+j2, i2*m+j2, i2*m+j))
    return vs, fs


def torus_mesh(x, R, a, arc=None, nu=48, nv=8):
    prof = [(x+a*math.cos(2*math.pi*k/nv), R+a*math.sin(2*math.pi*k/nv)) for k in range(nv)]
    vs, fs = _revolve(prof, nu, True, arc)
    if arc is not None:                                    # cap both cut ends
        m = len(vs)//nv
        fs.append(tuple(k*m for k in reversed(range(nv))))
        fs.append(tuple(k*m+m-1 for k in range(nv)))
    return vs, fs


def families(parts_, prefix='VTX'):
    """Objects of the built asset. The closure coils and their cryostats (MAGNETIC_COILS, the parts that set the field) stay one object
    each; every other part joins one object per (category, material, evidence), named <prefix>_<category>_<material> (VTX in the engine, CL in the cluster frame), so four placed engines
    stay within the web play budget (each exported node costs about 0.43 kB in the play package). The part list (mass, evidence, notes)
    stays per part; the object carries the part names in wf_parts."""
    out = {}
    for p in parts_:
        key = p['name'] if p['category'] in KEEP_SEPARATE else f'{prefix}_{p["category"]}_{p["material"]}'
        out.setdefault((key, p['category'], p['material'], p['evidence']), []).append(p)
    return [(k[0], ps) for k, ps in out.items()]


KEEP_SEPARATE = {'MAGNETIC_COILS'}


def tube_mesh(points, radius, n=8):
    """Polyline sweep with mitred frames and caps."""
    P = [tuple(map(float, p)) for p in points]
    def sub(a, b): return (a[0]-b[0], a[1]-b[1], a[2]-b[2])
    def norm(v):
        L = math.sqrt(sum(c*c for c in v)) or 1.0
        return (v[0]/L, v[1]/L, v[2]/L)
    def cross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
    dirs = [norm(sub(P[i+1], P[i])) for i in range(len(P)-1)]
    vs = []
    ref = (1.0, 0.0, 0.0) if abs(dirs[0][0]) < 0.9 else (0.0, 1.0, 0.0)
    u = norm(cross(dirs[0], ref))
    for i, p in enumerate(P):
        d = dirs[min(i, len(dirs)-1)] if i in (0, len(P)-1) else norm(tuple(a+b for a, b in zip(dirs[i-1], dirs[i])))
        u = norm(cross(cross(d, u), d)) if i else u
        u = norm(tuple(c for c in u))
        w = cross(d, u)
        for k in range(n):
            t = 2*math.pi*k/n
            vs.append(tuple(p[c]+radius*(math.cos(t)*u[c]+math.sin(t)*w[c]) for c in range(3)))
    fs = [(i*n+k, i*n+(k+1) % n, (i+1)*n+(k+1) % n, (i+1)*n+k) for i in range(len(P)-1) for k in range(n)]
    fs += [tuple(reversed(range(n))), tuple((len(P)-1)*n+k for k in range(n))]
    return vs, fs


def sphere_mesh(center, r, n=12):
    vs = [(center[0]+r*math.sin(math.pi*i/n)*0+r*math.cos(math.pi*i/n), center[1]+r*math.sin(math.pi*i/n)*math.cos(2*math.pi*j/(2*n)),
           center[2]+r*math.sin(math.pi*i/n)*math.sin(2*math.pi*j/(2*n))) for i in range(1, n) for j in range(2*n)]
    m = 2*n; fs = [(i*m+j, i*m+(j+1) % m, (i+1)*m+(j+1) % m, (i+1)*m+j) for i in range(n-2) for j in range(m)]
    vs += [(center[0]+r, center[1], center[2]), (center[0]-r, center[1], center[2])]
    top, bot = len(vs)-2, len(vs)-1
    fs += [(top, (j+1) % m, j) for j in range(m)]+[(bot, (n-2)*m+j, (n-2)*m+(j+1) % m) for j in range(m)]
    return vs, fs


def box_mesh(center, size, az):
    """Box in the local cylindrical frame at azimuth az: size = (along x, radial, tangential)."""
    a = math.radians(az); ru = (0.0, math.cos(a), math.sin(a)); tu = (0.0, -math.sin(a), math.cos(a))
    vs = []
    for i in (-1, 1):
        for j in (-1, 1):
            for k in (-1, 1):
                vs.append(tuple(center[c]+(i*size[0]/2 if c == 0 else 0)+j*size[1]/2*ru[c]+k*size[2]/2*tu[c] for c in range(3)))
    fs = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    return vs, fs


def disc_mesh(center, radius, depth, n=24):
    x = center[0]
    vs, fs = _revolve([(x+depth/2, 0.0), (x+depth/2, radius), (x-depth/2, radius), (x-depth/2, 0.0)], n, False)
    return [(v[0], v[1]+center[1], v[2]+center[2]) for v in vs], fs


def mesh_of(p):
    """(vertices, faces) of one part or effect (engine frame)."""
    sh = p['shape']
    if sh == 'revolve':
        vs, fs = _revolve(p['profile'], p.get('n', 32), p.get('closed', False))
        if p.get('cap_front'):
            m = p.get('n', 32); fs.append(tuple(reversed(range(m))))
        return vs, fs
    if sh == 'torus':
        return torus_mesh(p['x'], p['R'], p['a'], p.get('arc'), p.get('nu', 48), p.get('nv', 8))
    if sh == 'torus_section':
        half = math.degrees(p['width']/(2*p['R']))
        return torus_mesh(p['x'], p['R'], p['a'], (p['az']-half, p['az']+half), 3, p.get('nv', 8))
    if sh == 'tube':
        return tube_mesh(p['points'], p['radius'], p.get('n', 8))
    if sh == 'sphere':
        return sphere_mesh(p['center'], p['radius'], p.get('n', 12))
    if sh == 'box':
        return box_mesh(p['center'], p['size'], p['az'])
    if sh == 'disc':
        return disc_mesh(p['center'], p['radius'], p['depth'], p.get('n', 24))
    if sh == 'plume':
        o = p['origin']; vs, fs = _revolve([(o[0]+dx, r) for dx, r in p['profile']], 32, False)
        return vs, fs
    if sh == 'beams':
        vs, fs = [], []
        for a, b in p['beams']:
            v, f = tube_mesh([a, b], p['radius'], 6); base = len(vs)
            vs += v; fs += [tuple(base+i for i in face) for face in f]
        return vs, fs
    if sh == 'markers':
        vs, fs = [], []
        for j in range(p['count']):
            v, f = box_mesh(pol(p['x'], p['r'], 90*j), (p['size'], p['size'], p['size']), 90*j); base = len(vs)
            vs += v; fs += [tuple(base+i for i in face) for face in f]
        return vs, fs
    raise ValueError(sh)


def envelope(s, scale=1.0, with_effects=False):
    """Drawn extent of the engine: x range and maximum radius over every part's vertices."""
    xs, rr = [], 0.0
    for p in parts(s, scale):
        for v in mesh_of(p)[0]:
            xs.append(v[0]); rr = max(rr, math.hypot(v[1], v[2]))
    return dict(x0=min(xs), x1=max(xs), max_radius=rr, length=max(xs)-min(xs))


# ---------- engineering estimates ------------------------------------------------------------------------------------------------------

def _volume(p):
    """Solid volume of a part's drawn shape (analytic where the shape allows; hollow shells counted as their solid envelope)."""
    sh = p['shape']
    if sh in ('torus', 'torus_section'):
        span = (p['arc'][1]-p['arc'][0]) if sh == 'torus' and p.get('arc') else (math.degrees(p['width']/p['R']) if sh == 'torus_section' else 360.0)
        return 2*math.pi**2*p['R']*p['a']**2*span/360.0
    if sh == 'tube':
        pts = p['points']
        return math.pi*p['radius']**2*sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))
    if sh == 'sphere':
        return 4/3*math.pi*p['radius']**3
    if sh == 'box':
        return p['size'][0]*p['size'][1]*p['size'][2]
    if sh == 'disc':
        return math.pi*p['radius']**2*p['depth']
    if sh == 'revolve':
        prof = p['profile']
        if not p.get('closed'):                           # open shells: a 0.05 m skin
            return sum(math.pi*(r0+r1)*math.dist((x0, r0), (x1, r1))*0.05 for (x0, r0), (x1, r1) in zip(prof, prof[1:]))
        # Pappus: area x 2 pi x centroid radius of the closed (x, r) polygon
        A = Cr = 0.0
        for (x0, r0), (x1, r1) in zip(prof, prof[1:]+prof[:1]):
            c = x0*r1-x1*r0; A += c; Cr += (r0+r1)*c
        A /= 2
        return abs(2*math.pi*(Cr/(6*A))*A) if A else 0.0
    return 0.0


def mass_estimate(s, scale=1.0):
    """ENGINEERING_PROTOTYPE mass of the drawn engine: volume x density x solid fraction per material, summed per category."""
    mt = config(s)['materials']; by_cat, by_mat = {}, {}
    for p in parts(s, scale):
        key = p['material'] if p['material'] in mt['density_kg_m3'] else 'sensor'
        m = _volume(p)*mt['density_kg_m3'][key]*mt['solid_fraction'][key]
        by_cat[p['category']] = by_cat.get(p['category'], 0.0)+m; by_mat[key] = by_mat.get(key, 0.0)+m
    return dict(total_kg=sum(by_cat.values()), by_category=by_cat, by_material=by_mat, evidence='ENGINEERING_PROTOTYPE',
                basis=config(s)['engineering']['mass_basis'])


def calculations(s):
    """CALCULATED consequences of the compact geometry against the research demonstrator, each with its formula and validity. Inputs: the
    research V4 summary ([vertex_research]) and the compact drawn sizes ([vertex_engine.geometry]); the speculative design power share
    ([vertex_engine.speculative]) only sets which design point the SPECULATIVE rows describe."""
    r = s['vertex_research']; g = config(s)['geometry']; sp = config(s)['speculative']; st = stations(s)
    Rs_r = (-r['module_length_m']-r['shield_thickness_m'])-r['burn_x_local_m']; Rs_c = g['standoff_m']
    Y_r = r['yield_t_TNT']*TNT_J; f_r = r['pulse_rate_Hz']; P_r = r['fusion_TW']*1e12
    Y_c = Y_r*(Rs_c/Rs_r)**2                               # equal armour fluence: Y / (4 pi R^2) constant
    P_c = P_r*sp['design_power_share']
    f_c = P_c/Y_c
    flux_ratio = (P_c/Rs_c**2)/(P_r/Rs_r**2)              # areal heat load on the stand-off sphere
    P_equal_flux = P_r*(Rs_c/Rs_r)**2
    L2_r = next(l for l in r['loops'] if l['name'] == 'L2')['r_m']; L2_c = next(l for l in st['loops'] if l['name'] == 'L2')['r']
    B_r = math.sqrt(2*MU0*Y_r/(4/3*math.pi*L2_r**3)); B_c = math.sqrt(2*MU0*Y_c/(4/3*math.pi*L2_c**3))
    flight_c = st['burn']-st['shield_fwd']               # bore entry to burn point
    v_one = abs(flight_c)*f_c
    cone = math.degrees(math.atan2(g['shield_aft_radius_m'], Rs_c)); cone_r = math.degrees(math.atan2(r['shield_radius_m'], Rs_r))
    thrust_per_jet = r['thrust_MN']/r['jet_TW']
    rows = [
        dict(id='C-01', quantity='X-ray stand-off R_s', research=Rs_r, compact=Rs_c, unit='m', evidence='ENGINEERING_PROTOTYPE',
             formula='drawn: burn point to the shield aft face', validity='geometry'),
        dict(id='C-02', quantity='Yield per pulse at the research armour fluence', research=Y_r/TNT_J, compact=Y_c/TNT_J, unit='t TNT', evidence='CALCULATED',
             formula='Y_c = Y_V4 (R_s,c / R_s,V4)^2 (fluence Y/4 pi R^2 held at the research value)', validity='same spectrum, same armour; point source'),
        dict(id='C-03', quantity='Fusion power at the research pulse rate', research=P_r/1e12, compact=Y_c*f_r/1e12, unit='TW', evidence='CALCULATED',
             formula='P = Y f with f = f_V4', validity='no change in rate'),
        dict(id='C-04', quantity='Pulse rate for the design power', research=f_r, compact=f_c, unit='Hz', evidence='SPECULATIVE',
             formula=f'f_c = {sp["design_power_share"]:g} P_V4 / Y_c', validity='needs VTX-S1 and VTX-S2'),
        dict(id='C-05', quantity='Areal heat load on the stand-off sphere at the design power', research=1.0, compact=flux_ratio, unit='x research', evidence='CALCULATED',
             formula='(P_c / R_s,c^2) / (P_V4 / R_s,V4^2)', validity='same X-ray fraction and spectrum; the excess is VTX-S3'),
        dict(id='C-06', quantity='Fusion power per engine at the research areal heat load', research=P_r/1e12, compact=P_equal_flux/1e12, unit='TW', evidence='CALCULATED',
             formula='P = P_V4 (R_s,c / R_s,V4)^2', validity='hard-science ceiling of the compact geometry without VTX-S3'),
        dict(id='C-07', quantity='Field to stop one pulse at loop L2', research=B_r, compact=B_c, unit='T', evidence='CALCULATED',
             formula='B = sqrt(2 mu0 Y / (4/3 pi R_L2^3)) (magnetic energy in the loop volume equals the yield)', validity='order of magnitude; ignores coupling efficiency and geometry factors'),
        dict(id='C-08', quantity='Launcher speed for one target in flight', research=None, compact=v_one/1e3, unit='km/s', evidence='CALCULATED',
             formula='v = (bore entry to burn) x f_c', validity='research rule of one target in flight; a protected target train (VTX-S2) relaxes it'),
        dict(id='C-09', quantity='Shield shadow half-angle', research=cone_r, compact=cone, unit='deg', evidence='CALCULATED',
             formula='atan(r_shield / R_s)', validity='point burn; the wider compact cone shadows more of the cluster frame'),
        dict(id='C-10', quantity='Thrust per engine at the design power (research thrust/jet ratio)', research=r['thrust_MN'], compact=thrust_per_jet*r['jet_TW']*sp['design_power_share'],
             unit='MN', evidence='SPECULATIVE', formula='T = (T_V4 / P_jet,V4) x share x P_jet,V4', validity='research exhaust velocity and nozzle efficiency carried over (VTX-S4); not a canon thrust'),
    ]
    return rows


def fit_screen(s):
    env = envelope(s); st = stations(s); m = mass_estimate(s)
    g = config(s)['geometry']
    return dict(engine=config(s)['id'], version=config(s)['version'], stations={k: v for k, v in st.items() if not isinstance(v, list)},
                envelope=env, envelope_within_limit=env['max_radius'] <= g['max_radius_m']+1e-9, max_radius_limit=g['max_radius_m'],
                parts=len(parts(s)), mass_kg=round(m['total_kg']), mass_by_category={k: round(v) for k, v in sorted(m['by_category'].items())},
                calculations=[{k: (round(v, 4) if isinstance(v, float) else v) for k, v in row.items()} for row in calculations(s)])


if __name__ == '__main__':
    import json, sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from spec import load
    print(json.dumps(fit_screen(load(Path(__file__).resolve().parents[2])[0]), indent=1))
