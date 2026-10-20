"""M5 slice 4: magnetic-nozzle support assemblies (owner directive 2026-10-18 §6: "Magnetic nozzles do not require solid exhaust
tubes. Detail their real support assemblies, field-generating coils, mounting structures, cooling and protection instead"). STUDY /
NONCANON: a reversible study asset over the unchanged vehicle; nothing here enters WF_PROPULSION.

Function: show what holds, cools, feeds and protects the four nozzle coil sets, and screen the two consequences the built PROTOTYPE
geometry implies. (1) In a magnetic nozzle the thrust reaction acts on the coil currents, so the coils' cold-mass supports carry the
whole nozzle thrust from the cryogenic winding to the warm yoke; their length sets the conduction heat leak. (2) The built pickup
(Nozzle_Pickup_*) runs almost in the thrust-ring plane, so it turns the axial thrust into a large strut force and an in-plane ring load.
Fixed: the built nozzles (8 m, exit r 1.75, throat r 0.85, axes 2.6 m off in Y and Z), the four Nozzle_Coil stations (tube 0.08 m),
the warm yokes 0.05 m outside the coils (0.08 x 0.30 m, four straps), the strike modules on coils 2-3 (Q40), the pickups to ring nodes
0/3/9/6, the thrust ring (r 5.0-6.0, X -104..-102, 12 nodes), the 29.42 MN structural design load (DERIVED; 1.5 g at 2,000 t) and the
16.18 MN flight thrust (DERIVED). Unknown (OPEN, never chosen here): coil temperature, current density, stress, quench energy and
radiation life (OD-024); the force split between coil stations; nozzle heat loads (radiation, neutrons, plasma contact: the dominant
cryogenic term, not screened); yoke section; the vector authority (+-5 deg rig limit only).
Design freedom (PROTOTYPE judgment, this file): cryostat jacket build-up, support count and length, strut layout and material allowable,
cooler / dump / lead placement and size, the material property approximations below.

    python3 src/wayfarer/studies/m5_drive_support.py                                    # screens -> references/m5_drive_support.json
    /snap/bin/blender -b --factory-startup --python src/wayfarer/studies/m5_drive_support.py -- --asset   # + study asset
        assets/wayfarer/studies/WF_STUDY_DRIVE_SUPPORT.blend and the measured clearance / overlap screen against the saved vehicle
"""
from pathlib import Path
import argparse
import json
import math
import sys
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/build'), str(ROOT/'src/wayfarer/studies'), str(ROOT/'src/wayfarer/shots')]
import drive_manifold as dm
import layout

OUT_JSON = ROOT/'references/m5_drive_support.json'
ASSET = ROOT/'assets/wayfarer/studies/WF_STUDY_DRIVE_SUPPORT.blend'
COLLECTION = 'WF_STUDY_DRIVE_SUPPORT'

# PROTOTYPE judgment (this file).
JACKET = 0.035             # cryostat build-up around the winding: 0.005 wall + 0.02 vacuum gap + 0.01 MLI
SUPPORTS_PER_COIL = 8
REENTRANT_L = 0.40         # re-entrant (folded) support conduction length that a larger standoff would allow
COLD_K = 20.0              # screening coil temperature (OD-024 OPEN); HTS may run warmer, which only shrinks the figures
CARNOT_FRACTION = 0.15     # cryocooler efficiency as a fraction of Carnot at 20 K
# Approximate material properties (handbook-class values, screening only).
G10_ALLOW = 200e6          # Pa, G-10 class glass-epoxy support, working compressive allowable at cryogenic temperature
G10_KINT = 150.0           # W/m, thermal-conductivity integral of G-10 class laminate, 20-300 K
TI_YIELD, TI_E = 880e6, 114e9   # Ti-6Al-4V
STRESS_FRACTION = 0.67     # working stress / yield on the structural design load
BUCKLE_KNOCKDOWN = 0.8     # on the Euler load of a tube
D_OVER_T = 30.0


def unit(v):
    n = math.sqrt(sum(c*c for c in v)); return tuple(c/n for c in v)


def tube_size(force, length):
    """Smallest Ti tube (D/t 30) whose working stress and knocked-down Euler load carry `force` over `length`."""
    d_stress = math.sqrt(force*D_OVER_T/(math.pi*STRESS_FRACTION*TI_YIELD))
    d_buckle = (force*240*length**2/(BUCKLE_KNOCKDOWN*math.pi**3*TI_E))**0.25
    d = max(d_stress, d_buckle)
    return dict(od_m=round(d, 3), wall_m=round(d/D_OVER_T, 4), governs='buckling' if d_buckle > d_stress else 'stress',
                area_m2=round(math.pi*d*d/D_OVER_T, 5))


def nozzle_frames(s):
    """Per nozzle: axis, azimuth, coils and yokes in the ship frame, the two ring nodes flanking it."""
    p, st = s['prototype'], s['structure']; L = s['ship']['length']['value']
    xring = layout.at(s, p['thrust_ring_x']); half = st['ring_depth_m']/2; phase = math.radians(p['ring_phase_deg'])
    coils = dm.nozzle_coils(s); out = []
    for y in dm.nozzle_yokes(s):
        ay, az = y['axis']; azim = math.degrees(math.atan2(az, ay)) % 360
        nodes = sorted(range(st['ring_nodes']), key=lambda n: abs(((phase*180/math.pi+n*360/st['ring_nodes'])-azim+180) % 360-180))[:2]
        out.append(dict(nozzle=y['nozzle'], axis=(ay, az), azimuth_deg=azim, yokes=y['rings'], straps=y['straps'],
                        coils=[dict(c, x_ship=-L/2+c['x']) for c in coils],
                        nodes=[dict(index=n, point=dm.radial(xring-half, st['ring_node_radius_m'], phase+n*math.tau/st['ring_nodes'])) for n in sorted(nodes)],
                        ring_aft_x=xring-half))
    return out


def thrust_struts(s, f):
    """Comparison thrust frame: from the outer faces of yoke rings 1 and 2 to each flanking ring node, so the coil reaction reaches the
    thrust ring nearly along the axis (two bipods per nozzle)."""
    out = []; ay, az = f['axis']
    for nd in f['nodes']:
        u = unit((nd['point'][1]-ay, nd['point'][2]-az))
        for k in (1, 2):
            r = f['yokes'][k]
            a = (r['x'], ay+(r['r_out']+.20)*u[0], az+(r['r_out']+.20)*u[1])   # strut tube (r 0.20) seated on the yoke's outer face
            out.append(dict(name=f'Study_Thrust_Strut_{f["nozzle"]}_{nd["index"]:02}_{k}', a=a, b=nd['point'], node=nd['index'], yoke=k))
    return out


def screen(s):
    pr = s['propulsion']
    F_design = pr['design_thrust']['value']*1e6/pr['nozzle_count']; F_flight = pr['flight_thrust']['value']*1e6/pr['nozzle_count']
    frames = nozzle_frames(s)
    # (1) built pickup
    pick = []
    for q in dm.nozzle_pickups(s):
        d = tuple(b-a for a, b in zip(q['a'], q['b'])); L = math.sqrt(sum(c*c for c in d)); cos = abs(d[0])/L
        P = F_design/cos; area = math.pi*q['radius']**2
        pick.append(dict(name=q['name'], length_m=round(L, 3), angle_from_axis_deg=round(math.degrees(math.acos(cos)), 1), axial_cosine=round(cos, 3),
                         strut_force_MN=round(P/1e6, 1), in_plane_ring_load_MN=round(P*math.sqrt(1-cos*cos)/1e6, 1),
                         rod_stress_MPa=round(P/area/1e6), rod_radius_m=q['radius']))
    # straps: the coil reaction from coils 0-2 reaches the pickup yoke (3) through the four straps
    h = s['drive_hot_section']; strap_area = h['yoke_strap_count']*math.pi*h['yoke_strap_radius_m']**2
    straps = dict(count=h['yoke_strap_count'], radius_m=h['yoke_strap_radius_m'], stress_at_full_design_load_MPa=round(F_design/strap_area/1e6),
                  note='upper bound: the force split between coil stations is OPEN; whatever coils 0-2 carry crosses these straps')
    # (2) comparison thrust frame
    frame = []
    for f in frames:
        st_ = thrust_struts(s, f); cs = []
        for t in st_:
            d = tuple(b-a for a, b in zip(t['a'], t['b'])); L = math.sqrt(sum(c*c for c in d)); cs.append((t, L, abs(d[0])/L))
        sumcos = sum(c for _, _, c in cs)
        for t, L, c in cs:
            P = F_design/sumcos
            frame.append(dict(name=t['name'], nozzle=f['nozzle'], node=t['node'], yoke=t['yoke'], length_m=round(L, 3),
                              angle_from_axis_deg=round(math.degrees(math.acos(c)), 1), force_equal_share_MN=round(P/1e6, 2),
                              in_plane_ring_load_MN=round(P*math.sqrt(1-c*c)/1e6, 2), ti_tube=tube_size(P, L)))
    # (3) cold-mass supports: the coils carry the thrust reaction into the warm yoke
    area = F_design/G10_ALLOW; cop = CARNOT_FRACTION*COLD_K/(300-COLD_K)
    def leak(L):
        q = area*G10_KINT/L
        return dict(conduction_length_m=L, heat_leak_W_per_nozzle=round(q, 1), heat_leak_W_ship=round(4*q, 1),
                    cooler_input_kW_per_nozzle=round(q/cop/1e3, 2), cooler_input_kW_ship=round(4*q/cop/1e3, 1))
    standoff = h['yoke_standoff_m']
    supports = dict(load_N_per_nozzle=round(F_design), support_area_m2_per_nozzle=round(area, 4),
                    per_support_area_cm2=round(area/(SUPPORTS_PER_COIL*4)*1e4, 1),
                    direct=leak(standoff), reentrant=leak(REENTRANT_L),
                    specific_power_W_per_W=round(1/cop, 1),
                    basis=f'G-10 class supports at {G10_ALLOW/1e6:.0f} MPa working, conductivity integral {G10_KINT:g} W/m (20-300 K), coil {COLD_K:g} K, '
                          f'cooler {CARNOT_FRACTION:.0%} of Carnot; support term only (nuclear, radiative and plasma loads on the coils OPEN)')
    # bore side: the exhaust plasma (largest branch envelope) against the coil face, the jacket face and a strike module moved onto the jacket
    g = dm.geometry(s); st = g['stations']; ex = g['exhausts'][0]; rmax = s['drive_manifold']['plasma_branch_max_radius_m']
    need = s['drive_manifold']['plasma_hardware_clearance_m']; bore = []
    for c in dm.nozzle_coils(s):
        span = c['tube']+JACKET
        L_n = s['prototype']['nozzle_length_m']
        rp = max(rmax*dm.exhaust_factor(ex, st, min(L_n, max(0.0, c['x']-span+2*span*k/40))) for k in range(41))   # plasma inside the nozzle only
        strike = c['index'] in h['nozzle_strike_module_coils']
        bore.append(dict(coil=c['name'], plasma_r_m=round(rp, 3), coil_gap_m=round(c['inner']-rp, 3), jacket_gap_m=round(c['inner']-JACKET-rp, 3),
                         strike_module=strike, strike_on_jacket_gap_m=round(c['inner']-JACKET-.02-rp, 3) if strike else None))
    jacket = dict(build_up_m=JACKET, yoke_gap_before_m=standoff, yoke_gap_after_m=round(standoff-JACKET, 3), plasma_clearance_needed_m=need, bore=bore,
                  note='the 0.05 m warm-yoke standoff leaves 0.015 m outside a minimal cryostat: room for direct supports only. The built strike '
                       'modules (coils 2-3) sit on the coil inner face, i.e. inside where the cryostat wall must be')
    hw = []
    for f in frames:
        hw.append(dict(nozzle=f['nozzle'], azimuth_deg=round(f['azimuth_deg'], 1), flank_nodes=[n['index'] for n in f['nodes']]))
    return dict(status='STUDY / NONCANON: PROTOTYPE support assemblies over the unchanged vehicle',
                loads=dict(design_N_per_nozzle=round(F_design), flight_N_per_nozzle=round(F_flight),
                           note='design = structural proof load 29.42 MN / 4 (DERIVED, not flight thrust); equal share between nozzles'),
                built_pickup=pick, yoke_straps=straps, thrust_frame=frame, cold_mass_supports=supports, cryostat=jacket, nozzles=hw,
                prototype=dict(jacket_m=JACKET, supports_per_coil=SUPPORTS_PER_COIL, reentrant_length_m=REENTRANT_L, coil_K=COLD_K,
                               carnot_fraction=CARNOT_FRACTION, g10_allowable_Pa=G10_ALLOW, g10_k_integral_W_m=G10_KINT,
                               ti_yield_Pa=TI_YIELD, ti_E_Pa=TI_E, stress_fraction=STRESS_FRACTION, buckling_knockdown=BUCKLE_KNOCKDOWN, d_over_t=D_OVER_T))


# ---------- study asset (Blender) ----------------------------------------------------------------------------------------------------

COLOR = dict(cryo_coil_jacket=(.86, .84, .74), cryo_coil_support=(.35, .30, .22), cryo_cooler=(.62, .68, .74), cryo_coolant_line=(.50, .78, .92),
             drive_power_lead=(.85, .55, .20), drive_quench_dump=(.70, .25, .20), drive_thrust_strut=(.42, .44, .46))


def revolve(name, axis, x0, x1, r0, r1, n=48):
    """Rectangular section x0..x1, r0..r1 revolved about a line parallel to X through `axis` (closed annulus)."""
    import bpy
    ay, az = axis; vs, fs = [], []
    for k in range(n):
        t = math.tau*k/n; c, sn = math.cos(t), math.sin(t)
        vs += [(x, ay+r*c, az+r*sn) for x, r in ((x0, r0), (x1, r0), (x1, r1), (x0, r1))]
    for k in range(n):
        a, b = 4*k, 4*((k+1) % n)
        for e in range(4):
            fs.append((a+e, a+(e+1) % 4, b+(e+1) % 4, b+e))
    me = bpy.data.meshes.new(name); me.from_pydata(vs, [], fs); me.update()
    return bpy.data.objects.new(name, me)


def oriented_box(name, centre, radial_dir, size):
    """Box with its local axes X (ship), radial (in YZ) and tangential; size = (axial, radial, tangential)."""
    import bpy
    ux, ur = (1, 0, 0), (0, *radial_dir); ut = (0, -radial_dir[1], radial_dir[0])
    vs = []
    for sx in (-1, 1):
        for sr in (-1, 1):
            for stg in (-1, 1):
                vs.append(tuple(centre[i]+sx*size[0]/2*ux[i]+sr*size[1]/2*ur[i]+stg*size[2]/2*ut[i] for i in range(3)))
    fs = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    me = bpy.data.meshes.new(name); me.from_pydata(vs, [], fs); me.update()
    return bpy.data.objects.new(name, me)


def parts(s):
    """Every study part as a plain description (name, kind, shape, note), so the asset and the screen share one list."""
    out = []; struts = {t['name']: t for f in nozzle_frames(s) for t in thrust_struts(s, f)}
    for f in nozzle_frames(s):
        j = f['nozzle']; ay, az = f['axis']; ra = math.radians(f['azimuth_deg']); out_dir = (math.cos(ra), math.sin(ra))
        for c, yk in zip(f['coils'], f['yokes']):
            out.append(dict(name=f'Study_Coil_Cryostat_{j}_{c["index"]}', kind='cryo_coil_jacket', shape='revolve', axis=(ay, az),
                            x0=c['x_ship']-c['tube']-JACKET, x1=c['x_ship']+c['tube']+JACKET, r0=c['inner']-JACKET, r1=c['outer']+JACKET,
                            note=f'vacuum jacket + MLI around {c["name"]} ({JACKET} m build-up, PROTOTYPE); coil temperature OPEN (OD-024)'))
            for m in range(SUPPORTS_PER_COIL):
                t = math.tau*(m+.5)/SUPPORTS_PER_COIL; u = (math.cos(t), math.sin(t)); r0, r1 = c['outer']+JACKET+.002, yk['r_in']-.002
                out.append(dict(name=f'Study_Coil_Support_{j}_{c["index"]}_{m}', kind='cryo_coil_support', shape='tube', radius=.025,
                                points=[(c['x_ship'], ay+r0*u[0], az+r0*u[1]), (c['x_ship'], ay+r1*u[0], az+r1*u[1])],
                                note='cold-mass support: carries the coil share of the thrust reaction into the warm yoke; 0.015 m long here (direct), '
                                     'thermally a short circuit (see heat-leak screen)'))
        # cryocooler and quench dump on the thrust-ring aft face, either side of the nozzle azimuth
        rx = f['ring_aft_x']
        for kind, dz, size, label in (('cryo_cooler', -5.5, (0.8, 0.8, 0.55), 'cryocooler / cold-head module: re-cools the coil helium loop; '
                                       'input power scales with the coil heat load (support term screened; nuclear/radiative OPEN)'),
                                      ('drive_quench_dump', 5.5, (0.6, 0.6, 0.45), 'quench protection: dump resistor and switch for the nozzle coil set; '
                                       'stored energy and dump heat OPEN (OD-024)')):
            a = ra+math.radians(dz); rd = (math.cos(a), math.sin(a)); rc = 5.5
            unit = 'Cryocooler' if kind == 'cryo_cooler' else 'Quench_Dump'
            out.append(dict(name=f'Study_{unit}_{j}', kind=kind, shape='box',
                            centre=(rx-size[0]/2-.03, rc*rd[0], rc*rd[1]), radial=rd, size=size, note=label))
            # the ring is a node-and-chord truss: the unit hangs from a bracket on the nearer flanking node's aft face
            nd = min(f['nodes'], key=lambda n: abs(math.atan2(n['point'][2], n['point'][1])-a))
            edge = a+math.copysign(size[2]/2/rc, math.atan2(nd['point'][2], nd['point'][1])-a)
            out.append(dict(name=f'Study_{unit}_Bracket_{j}', kind=kind, shape='tube', radius=.08,
                            points=[(rx-size[0]/2-.03, rc*math.cos(edge), rc*math.sin(edge)), (rx-.10, nd['point'][1], nd['point'][2]), (rx+.02, nd['point'][1], nd['point'][2])],
                            note=f'mount bracket to thrust node {nd["index"]} (PROTOTYPE)'))
            # line from the module along the yokes to every coil, on the outward side of the nozzle, +-25 deg off its azimuth
            phi = ra+math.radians(-25 if kind == 'cryo_cooler' else 25); v = (math.cos(phi), math.sin(phi)); pts = []
            start = (rx-size[0]-.05, (rc-size[1]/2)*rd[0], (rc-size[1]/2)*rd[1])
            pts.append(start)
            for c, yk in sorted(zip(f['coils'], f['yokes']), key=lambda q: -q[0]['x_ship']):
                rr = yk['r_out']+.15; pts.append((yk['x'], ay+rr*v[0], az+rr*v[1]))
            kind_l = 'cryo_coolant_line' if kind == 'cryo_cooler' else 'drive_power_lead'
            out.append(dict(name=f'Study_{"Cryo_Line" if kind == "cryo_cooler" else "Current_Lead"}_{j}', kind=kind_l, shape='tube', radius=.05, points=pts,
                            note='helium supply/return pair to each coil cryostat (PROTOTYPE route outside the yokes)' if kind == 'cryo_cooler'
                                 else 'coil current leads / bus from the power bus and quench unit (HTS leads; current OPEN, OD-024)'))
            for c, yk in zip(f['coils'], f['yokes']):
                side = 1 if c['index'] <= 1 else -1; xs = c['x_ship']+side*(.15+.08); rr = yk['r_out']+.15
                out.append(dict(name=f'Study_{"Cryo_Stub" if kind == "cryo_cooler" else "Lead_Stub"}_{j}_{c["index"]}', kind=kind_l, shape='tube', radius=.03,
                                points=[(yk['x'], ay+rr*v[0], az+rr*v[1]), (xs, ay+rr*v[0], az+rr*v[1]), (xs, ay+c['ring_radius']*v[0], az+c['ring_radius']*v[1]),
                                        (c['x_ship']+side*(c['tube']+JACKET+.005), ay+c['ring_radius']*v[0], az+c['ring_radius']*v[1])],
                                note='feedthrough beside the yoke band into the cryostat (PROTOTYPE)'))
        for t in [t for t in struts.values() if t['name'].startswith(f'Study_Thrust_Strut_{j}_')]:
            out.append(dict(name=t['name'], kind='drive_thrust_strut', shape='tube', radius=.20, points=[t['a'], t['b']],
                            note=f'COMPARISON thrust frame: yoke ring {t["yoke"]} -> ring node {t["node"]}; replaces nothing in the vehicle'))
    return out


def build_asset(s):
    import bpy
    from common import material
    from m5_eva_l2 import tube_mesh
    bpy.ops.wm.read_factory_settings(use_empty=True)
    col = bpy.data.collections.new(COLLECTION); bpy.context.scene.collection.children.link(col)
    col['study'] = 'm5_drive_support'; col['status'] = 'STUDY / NONCANON: PROTOTYPE nozzle support assemblies; the vehicle is unchanged'
    mats = {k: material(f'STUDY_{k}', c) for k, c in COLOR.items()}
    for p in parts(s):
        if p['shape'] == 'revolve':
            ob = revolve(p['name'], p['axis'], p['x0'], p['x1'], p['r0'], p['r1'])
        elif p['shape'] == 'box':
            ob = oriented_box(p['name'], p['centre'], p['radial'], p['size'])
        else:
            ob = tube_mesh(p['name'], p['points'], p['radius'], 12)
        col.objects.link(ob); ob.data.materials.append(mats[p['kind']])
        ob['kind'] = p['kind']; ob['note'] = p['note']; ob['geometry_status'] = 'PROTOTYPE'; ob['study'] = 'm5_drive_support'
        ob['component_id'] = f'WF.STUDY.DRIVE_SUPPORT.{p["name"]}'; ob['source_ref'] = 'M5 directive §6; drive_manifold nozzle_coils/yokes/pickups'
    ASSET.parent.mkdir(parents=True, exist_ok=True); bpy.ops.wm.save_as_mainfile(filepath=str(ASSET), compress=True)


def measure(s):
    """Each study part against the saved vehicle's meshes aft of X -95: intersecting objects (BVH overlap) and the nearest distance. The
    plasma and field envelopes are measured separately: the bore side of the cryostat faces the exhaust plasma."""
    import bpy
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    import shot_tools
    bpy.ops.wm.read_factory_settings(use_empty=True)
    veh = []
    for src in ({'asset': 'WF_WAYFARER_001.blend', 'collection': 'WF_WAYFARER_001', 'group': 'assembly'},):
        veh += shot_tools.gather(shot_tools.link_source(ROOT, src), src)
    study_src = {'asset': 'studies/WF_STUDY_DRIVE_SUPPORT.blend', 'collection': COLLECTION, 'group': 'fixed'}
    study = shot_tools.gather(shot_tools.link_source(ROOT, study_src), study_src)

    def bvh(it):
        ob = it['obj']
        if ob.type != 'MESH' or not len(ob.data.polygons):
            return None
        W = it['matrix']; vs = [W@v.co for v in ob.data.vertices]
        return BVHTree.FromPolygons(vs, [tuple(p.vertices) for p in ob.data.polygons]), vs
    skip = ('scale_reference', 'magnetic_field', 'optical_beam', 'hull_envelope')
    near = [it for it in veh if it['center'][0]-it['radius'] < -95 and it['kind'] not in skip and not it['name'].startswith('Engineering_Envelope')]
    trees = [(it, bvh(it)) for it in near]; trees = [(it, t) for it, t in trees if t]
    res = {}
    for it in study:
        t = bvh(it)
        if not t:
            continue
        tree, vs = t; hits, dmin, dobj, plasma = [], 1e9, None, 1e9
        for v_it, (vt, vvs) in trees:
            if (Vector(v_it['center'])-Vector(it['center'])).length > v_it['radius']+it['radius']+1.0:
                continue
            if tree.overlap(vt):
                hits.append(v_it['name'])
            for v in vs[::max(1, len(vs)//64)]:
                n = vt.find_nearest(v)
                if n[0] is not None:
                    if v_it['kind'] == 'plasma':
                        plasma = min(plasma, n[3])
                    elif n[3] < dmin:
                        dmin, dobj = n[3], v_it['name']
        res[it['name']] = dict(kind=it['kind'], intersects=sorted(set(hits)), nearest_m=round(dmin, 3), nearest=dobj,
                               plasma_m=None if plasma > 1e8 else round(plasma, 3))
    return res


def summarize(meas):
    """Group the measured intersections into expected contacts (a part ending on what it serves) and conflicts."""
    expected = {'cryo_cooler': ('Thrust_Node',), 'drive_quench_dump': ('Thrust_Node',), 'cryo_coil_jacket': ('Nozzle_Coil', 'PFC_NOZZLE_STRIKE', 'MagneticNozzle_FieldEnvelope', 'Nozzle_Yoke'),
                'cryo_coil_support': ('Nozzle_Yoke',), 'cryo_coolant_line': ('Nozzle_Yoke',), 'drive_power_lead': ('Nozzle_Yoke',),
                'drive_thrust_strut': ('Nozzle_Yoke', 'Thrust_Ring', 'Thrust_Node', 'Hub_Web')}
    contacts, conflicts, display = {}, {}, {}
    for name, m in meas.items():
        for h in m['intersects']:
            if h.startswith('MagneticNozzle_FieldEnvelope'):   # display surface of the field, not hardware: feeds to the coils must cross it
                display.setdefault(name, []).append(h); continue
            ok = any(h.startswith(e) for e in expected.get(m['kind'], ()))
            (contacts if ok else conflicts).setdefault(name, []).append(h)
    by_kind = {}
    for name, m in meas.items():
        k = by_kind.setdefault(m['kind'], dict(parts=0, min_nearest_m=1e9, min_plasma_m=None))
        k['parts'] += 1; k['min_nearest_m'] = min(k['min_nearest_m'], m['nearest_m'])
        if m['plasma_m'] is not None:
            k['min_plasma_m'] = m['plasma_m'] if k['min_plasma_m'] is None else min(k['min_plasma_m'], m['plasma_m'])
    return dict(by_kind=by_kind, contacts=contacts, conflicts=conflicts, field_envelope_crossings=sorted(display))


def legend(src, dst):
    import m5_cutaway
    r = json.loads(OUT_JSON.read_text()); pk = r['built_pickup'][0]; fr = r['thrust_frame']; sp = r['cold_mass_supports']; cr = r['cryostat']
    b2 = next(b for b in cr['bore'] if b['coil'] == 'Nozzle_Coil_02')
    lines = [f'Built pickup (grey, to ring nodes 0/3/6/9): {pk["angle_from_axis_deg"]} deg off the thrust axis -> {pk["strut_force_MN"]} MN strut force and '
             f'{pk["in_plane_ring_load_MN"]} MN pushed into the ring plane per nozzle at the 29.42 MN design load.',
             f'Comparison thrust frame (grey bipods to the flanking nodes): {min(f["angle_from_axis_deg"] for f in fr)}-{max(f["angle_from_axis_deg"] for f in fr)} deg off axis, '
             f'{fr[0]["force_equal_share_MN"]} MN per strut (equal share), Ti tube OD {min(f["ti_tube"]["od_m"] for f in fr)}-{max(f["ti_tube"]["od_m"] for f in fr)} m.',
             f'Coil cryostats (cream) leave {cr["yoke_gap_after_m"]} m to the warm yoke: direct cold-mass supports leak {sp["direct"]["heat_leak_W_per_nozzle"]} W/nozzle '
             f'({sp["direct"]["cooler_input_kW_ship"]} kW cooler input, ship) vs {sp["reentrant"]["heat_leak_W_per_nozzle"]} W re-entrant (support term only).',
             f'Throat-side coil 2: plasma gap {b2["coil_gap_m"]} m at the coil, {b2["jacket_gap_m"]} m with a cryostat, {b2["strike_on_jacket_gap_m"]} m with the strike '
             f'module on it (needed {cr["plasma_clearance_needed_m"]} m).']
    m5_cutaway.legend(src, dst, 'M5 slice 4: nozzle support assemblies (STUDY, vehicle unchanged)', lines=lines,
                      note='Overlay colours are explanatory, never ship materials. Orange S07: cryocooler + helium lines; green S08: current leads + quench dump; '
                           'grey S02: load paths. Coil temperature, stored energy, heat loads and force split OPEN (OD-024).')


def _blender():
    try:
        import bpy  # noqa: F401
        return True
    except ImportError:
        return False


def main(asset=False):
    from spec import load
    s = load(ROOT)[0]; res = screen(s)
    if asset and _blender():
        build_asset(s); meas = measure(s); res['measured'] = dict(summary=summarize(meas), parts=meas)
    elif OUT_JSON.exists() and 'measured' in json.loads(OUT_JSON.read_text()):
        res['measured'] = json.loads(OUT_JSON.read_text())['measured']
    OUT_JSON.write_text(json.dumps(res, indent=1)+'\n')
    for p in res['built_pickup']:
        print('pickup', p)
    print('straps', res['yoke_straps'])
    for f in res['thrust_frame'][:4]:
        print('strut', f)
    print('supports', json.dumps(res['cold_mass_supports'], indent=1))
    if 'measured' in res:
        sm = res['measured']['summary']; print(json.dumps(sm['by_kind'], indent=1))
        print('conflicts', json.dumps(sm['conflicts'], indent=1))
    return res


if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser(); ap.add_argument('--asset', action='store_true')
    ap.add_argument('--legend', nargs=2, metavar=('SRC', 'DST'), help='annotate a shot render with the subsystem legend and the findings')
    a = ap.parse_args(argv)
    if a.legend:
        legend(Path(a.legend[0]), Path(a.legend[1]))
    else:
        main(a.asset)
