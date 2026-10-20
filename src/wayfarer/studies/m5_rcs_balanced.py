"""M5 RCS-B: an ALTERNATE balanced opposed-jet RCS beside the as-built S02 jets (owner 2026-10-18, S&E 15!A212 OWN-S02-Q3, 98!A116:
"Build an ALTERNATE balanced pitch/yaw/roll opposed-jet candidate with true force-free couples and plume/torque/swept-volume checks;
preserve as-built S02 geometry for compare"; "Return measured per-axis torque, parasitic translation and mass/thermal usage").
LOW POWER CANDIDATE / PERFORMANCE OPEN: nothing in the vehicle changes and nothing is retrofitted.

Function: give pitch, yaw and roll couples whose jet forces cancel exactly, so a manoeuvre adds no translation and its torque does not
depend on the centre of mass (which moves with the OPEN fuel placement). Fixed: the built vehicle (saved COAST asset), the shield rim
and Crown bays, the blades at 30/150/270 deg and their aft edge, the thrust ring and comms booms, the as-built jets (exterior_hardware),
the CAD inertia (references/m5_attitude.json, M5 slice 2). Unknown (OPEN, never chosen): thrust class, Isp, the hydrogen buffer and its
conditioning, valve technology, dry mass (15!A212 H: no assumed 100 N class or 200 s Isp). Design freedom (PROTOTYPE, this file): pod
stations and azimuths, the outward cant of the roll nozzles, the screen cone angles.

Candidate: three forward pods on the shield rim's aft face at 105/225/345 deg (between Crown bays, 120 deg apart) and three aft pods on the
hull skin at X -92 between the blades (90/210/330 deg, 60 deg from each blade plane). Every pod has one radial-outward nozzle with no
cant; the forward pods add two tangential roll nozzles canted outward (not aft). Three inward pushes 120 deg apart span the plane, so
forward and aft sets give any lateral force pair; equal and opposite pairs are pure pitch/yaw couples, and three equal tangential
pushes are a pure roll couple. Forces are per a 100 N REFERENCE unit only: torques, impulses and propellant scale with the real thrust.

    /snap/bin/blender -b --factory-startup --python-exit-code 1 --python src/wayfarer/studies/m5_rcs_balanced.py   # screens, solve,
        references/m5_rcs_balanced.json, study asset assets/wayfarer/studies/WF_STUDY_RCS_BALANCED.blend
"""
from pathlib import Path
import json
import math
import sys
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/build'), str(ROOT/'src/wayfarer/studies'), str(ROOT/'src/wayfarer/shots'),
                str(ROOT/'src/wayfarer/components')]

OUT_JSON = ROOT/'references/m5_rcs_balanced.json'
ASSET = ROOT/'assets/wayfarer/studies/WF_STUDY_RCS_BALANCED.blend'
COLLECTION = 'WF_STUDY_RCS_BALANCED'
FWD_DEG = (105.0, 225.0, 345.0)     # B1: rim pods between Crown bays (bays every 30 deg from 0), 120 deg apart
FWD_DEG_B2 = (75.0, 165.0, 255.0, 345.0)   # B2: the four as-built rim pod bays, roll nozzles recanted outward (no aft cant)
AFT_DEG = (90.0, 210.0, 330.0)      # hull faces between the blades (30/150/270): 60 deg from each blade plane
AFT_X = -92.0                       # on the skin, forward of the aft drive-service zone (DS-14 cassettes X -99.5, DS-16 arm base X -97)
ROLL_CANT_DEG = 40.0                # roll nozzles canted outward (radially) so their cone leaves the rim edge; no aft cant (no axial force)
F_REF = 100.0                       # REFERENCE force unit (15!A212 H: no assumed thruster class); everything below scales with it
ISP_REF = 300.0                     # REFERENCE Isp for kg figures (the S02 table's lower bound); propellant scales as 1/Isp
G0 = 9.80665
H2_CONDITION_J_KG = 4.4e6           # ~ latent 0.45 MJ/kg + warming 20 -> 300 K ~3.9 MJ/kg (normal H2, order of magnitude; DERIVED approx.)
VALVE_W = 30.0                      # PROTOTYPE open-valve coil power per nozzle (order of magnitude)
CONES_DEG = (15.0, 30.0)            # plume screen half-angles: nominal core and a wide sensitivity
CONE_RANGE_M = 80.0
SLEW_DEG_S = 0.05                   # reference low-hazard slew rate (15!A211 LOW_HAZARD_SLEW): start and stop
AFT_FAN_DEG = 30.0                  # B1F: two aft nozzles per pod canted +-30 deg tangentially in the radial plane (no aft cant): the six aft
                                    # force directions sit 60 deg apart instead of three at 120 deg (recovers the pitch+ / yaw lever)


def candidate(s, fwd_deg=FWD_DEG, tag='RCSB', aft_fan_deg=None):
    """Pods and nozzles of a balanced candidate as exterior_hardware dicts (box / tube, nozzles with jet and exit): forward rim pods at
    fwd_deg, the aft triad at AFT_DEG (one radial nozzle per pod, or with aft_fan_deg two nozzles canted +-aft_fan_deg tangentially)."""
    import exterior_hardware as eh
    import forward_shield as fs
    import hull_geometry as hg
    q = eh.table(s); L, W, D = q['rcs_pod_m']; nr, nl = q['rcs_nozzle_radius_m'], q['rcs_nozzle_length_m']; out = []
    st = fs.stations(s); R = st['shield_r']; x = st['rim'][0]-L/2; rc = R-0.3-D/2; cr = math.radians(ROLL_CANT_DEG)
    for k, deg in enumerate(fwd_deg, 1):
        a = math.radians(deg); c = eh.radial(x, rc, a); t = (0.0, -math.sin(a), math.cos(a)); u = (0.0, math.cos(a), math.sin(a))
        out.append(eh.box(f'Study_{tag}_Fwd_{k}', 'rcs_balanced_pod', 'balanced candidate rim pod (STUDY): valves and nozzles fed from the '
                          'isolated metered H2 buffer', c, a, (L, W, D), rcs=True, station='forward', deg=deg))
        b0 = eh.radial(x, rc+D/2, a); b1 = eh.radial(x, min(rc+D/2+nl, R-0.02), a)
        out.append(eh.disc(f'Study_{tag}_Fwd_{k}_Radial', 'rcs_balanced_nozzle', 'radial-outward nozzle, no cant (pitch / yaw pairs)', b0, b1, nr,
                           jet=u, exit=b1, station='forward', deg=deg))
        for side, sg in (('Pos', 1), ('Neg', -1)):
            j = tuple(sg*t[i]*math.cos(cr)+u[i]*math.sin(cr) for i in range(3))
            p0 = tuple(c[i]+sg*t[i]*W/2+(-L/2+0.15 if i == 0 else 0.0) for i in range(3)); p1 = tuple(p0[i]+j[i]*nl for i in range(3))
            out.append(eh.disc(f'Study_{tag}_Fwd_{k}_Roll_{side}', 'rcs_balanced_nozzle', f'tangential roll nozzle canted {ROLL_CANT_DEG:.0f} deg '
                               'outward, no aft cant (roll triple)', p0, p1, nr, jet=j, exit=p1, station='forward', deg=deg))
    rh = hg.radius_at(s, AFT_X)
    for k, deg in enumerate(AFT_DEG, 1):
        a = math.radians(deg); u = (0.0, math.cos(a), math.sin(a)); c = eh.radial(AFT_X, rh+D/2, a)
        out.append(eh.box(f'Study_{tag}_Aft_{k}', 'rcs_balanced_pod', 'balanced candidate aft pod on the hull face between blades (STUDY)',
                          c, a, (L, W, D), rcs=True, station='aft', deg=deg))
        b0 = eh.radial(AFT_X, rh+D, a); b1 = eh.radial(AFT_X, rh+D+nl, a)
        if aft_fan_deg is None:
            out.append(eh.disc(f'Study_{tag}_Aft_{k}_Radial', 'rcs_balanced_nozzle', 'radial-outward nozzle, no cant (pitch / yaw pairs)', b0, b1,
                               nr, jet=u, exit=b1, station='aft', deg=deg))
            continue
        t = (0.0, -math.sin(a), math.cos(a)); cf = math.radians(aft_fan_deg)
        for side, sg in (('Pos', 1), ('Neg', -1)):
            j = tuple(u[i]*math.cos(cf)+sg*t[i]*math.sin(cf) for i in range(3))
            p0 = tuple(b0[i]+sg*t[i]*W/4 for i in range(3)); p1 = tuple(p0[i]+j[i]*nl for i in range(3))
            out.append(eh.disc(f'Study_{tag}_Aft_{k}_Fan_{side}', 'rcs_balanced_nozzle', f'aft fan nozzle canted {aft_fan_deg:.0f} deg '
                               'tangentially, no aft cant (pitch / yaw / roll)', p0, p1, nr, jet=j, exit=p1, station='aft', deg=deg))
    return out


def rows_of(nozzles, cm, f=F_REF):
    import m5_attitude as ma
    out = []
    for p in nozzles:
        F = tuple(-f*v for v in p['jet']); r = tuple(p['exit'][i]-cm[i] for i in range(3))
        out.append(dict(name=p['name'], at=p['exit'], exhaust=p['jet'], force=F, torque=ma.cross(r, F), station=p.get('station', '')))
    return out


def as_built(s):
    import exterior_hardware as eh
    return [dict(p, station='aft' if '_Aft_' in p['name'] else 'forward') for p in eh.rcs_aft(s)+eh.rcs_rim(s) if 'jet' in p]


def strict_couple(rows, axis, sign):
    """Duty-cycled jets (0..1): the largest torque about one axis with ALL three force components and both cross torques zero."""
    import m5_attitude as ma
    others = [i for i in range(3) if i != axis]
    A = [[r['force'][i] for r in rows] for i in range(3)]+[[r['torque'][i] for r in rows] for i in others]
    u = ma.lp_max([sign*r['torque'][axis] for r in rows], A, len(rows))
    T = [sum(u[k]*rows[k]['torque'][i] for k in range(len(rows))) for i in range(3)]; Fv = [sum(u[k]*rows[k]['force'][i] for k in range(len(rows))) for i in range(3)]
    return dict(torque_N_m=round(sign*T[axis]), duty={rows[k]['name']: round(u[k], 3) for k in range(len(rows)) if u[k] > 1e-4},
                sum_duty=round(sum(u), 3), net_force_N=round(math.hypot(*Fv), 3), cross_torque_N_m=round(math.hypot(*[T[i] for i in others]), 2))


def efficient_couple(rows, axis, sign, strict):
    """The jet pattern with the most torque per unit total thrust (lever efficiency, m): max torque with sum(duty) <= 1, the same force
    and cross-torque constraints (strict: all three force components; else lateral only, the slice 2 rule for the canted S02 jets)."""
    import m5_attitude as ma
    n = len(rows); others = [i for i in range(3) if i != axis]
    A = [[r['force'][i] for r in rows]+[0.0] for i in ((0, 1, 2) if strict else (1, 2))]+[[r['torque'][i] for r in rows]+[0.0] for i in others]
    A.append([1.0]*n+[-1.0])
    u = ma.lp_max([sign*r['torque'][axis] for r in rows]+[0.0], A, n+1)[:n]
    tot = sum(u)
    if tot < 1e-9:
        return None
    T = sign*sum(u[k]*rows[k]['torque'][axis] for k in range(n))
    return dict(lever_m=round(T/(tot*F_REF), 1), jets={rows[k]['name']: round(u[k]/max(u), 3) for k in range(n) if u[k] > 1e-6})


def axis_table(s, rows, cases, strict):
    """Per axis: the couple (strict: force-free in all three components; else the M5 slice 2 rule, lateral-free with the axial force left
    free), its torque per unit total thrust (lever efficiency), parasitic force and dv, propellant, conditioning heat and the ideal 180 deg
    time (15!A211: SENSITIVITY ONLY, no flip is permitted)."""
    import m5_attitude as ma
    c = cases['burnout_1100t']; out = {}
    for name, (ax, sg) in ma.AXES.items():
        b = strict_couple(rows, ax, sg) if strict else ma.throttled_couple(rows, ax, sg)
        if b['torque_N_m'] <= 0:
            out[name] = dict(couple=None); continue
        thrust = b['sum_duty']*F_REF
        Fpar = b['net_force_N'] if strict else math.hypot(b['axial_force_N'], b['lateral_force_N'])
        Iax = c['roll_stationary_only_kg_m2'] if ax == 0 else c['I_kg_m2'][ax][ax]
        dh = 2*Iax*math.radians(SLEW_DEG_S)                       # start + stop at the reference slew rate
        t_slew = dh/b['torque_N_m']; m_slew = thrust*t_slew/(ISP_REF*G0)
        T180 = math.sqrt(4*math.pi*Iax/b['torque_N_m']); m180 = thrust*T180/(ISP_REF*G0)
        mdot = thrust/(ISP_REF*G0)
        eff = efficient_couple(rows, ax, sg, strict)
        if eff:                                                   # slews use the efficient pattern (propellant), authority the max one
            m_slew = dh/(eff['lever_m']*ISP_REF*G0)        # impulse / lever, independent of how fast it is fired
        out[name] = dict(torque_N_m=b['torque_N_m'], efficient=eff, jets_firing=sum(1 for v in b['duty'].values() if v > 1e-3), sum_duty=b['sum_duty'],
                         lever_efficiency_m=round(b['torque_N_m']/thrust, 1), parasitic_force_N=round(Fpar, 1),
                         parasitic_dv_m_s_per_slew=round(Fpar*t_slew/(c['mass_t']*1e3), 5),
                         slew_start_stop=dict(rate_deg_s=SLEW_DEG_S, burn_s=round(t_slew, 1), h2_kg=round(m_slew, 2),
                                              conditioning_MJ=round(m_slew*H2_CONDITION_J_KG/1e6, 1)),
                         firing=dict(h2_kg_s=round(mdot, 4), conditioning_kW_if_live=round(mdot*H2_CONDITION_J_KG/1e3, 1),
                                     valve_W=round(VALVE_W*sum(1 for v in b['duty'].values() if v > 1e-3))),
                         sensitivity_only_180=dict(minutes=round(T180/60, 1), h2_kg=round(m180, 1)), duty=b['duty'],
                         cross_torque_N_m=b['cross_torque_N_m'])
    return out


def com_independence(rows_fn, cases, strict):
    """Couple torque about the burnout CoM and about the CoM with the housed fusion fuel: a force-free couple does not change."""
    import m5_attitude as ma
    res = {}
    for name, (ax, sg) in ma.AXES.items():
        vals = []
        for key in ('burnout_1100t', 'burnout_plus_housed_fusion_fuel_C'):
            rows = rows_fn(cases[key]['com_m'])
            vals.append((strict_couple(rows, ax, sg) if strict else ma.throttled_couple(rows, ax, sg))['torque_N_m'])
        # the burnout duty pattern applied about the fuelled CoM: what an unchanged firing table would actually do
        rows0 = rows_fn(cases['burnout_1100t']['com_m']); rows1 = rows_fn(cases['burnout_plus_housed_fusion_fuel_C']['com_m'])
        b0 = strict_couple(rows0, ax, sg) if strict else ma.throttled_couple(rows0, ax, sg)
        u = [b0['duty'].get(r['name'], 0.0) for r in rows1]
        T1 = [sum(u[k]*rows1[k]['torque'][i] for k in range(len(rows1))) for i in range(3)]
        res[name] = dict(best_burnout=vals[0], best_fuelled=vals[1], same_table_fuelled_axis=round(sg*T1[ax]),
                         same_table_fuelled_cross=round(math.hypot(*[T1[i] for i in range(3) if i != ax]), 1))
    return res


# ---------------------------------------------------------------- Blender: screens against the saved vehicle, study asset

def vehicle_bvh():
    import bpy
    from mathutils.bvhtree import BVHTree
    import shot_tools
    src = {'asset': 'WF_WAYFARER_001.blend', 'collection': 'WF_WAYFARER_001', 'group': 'assembly'}
    vs, fs, names = [], [], []
    skip = ('scale_reference', 'plasma', 'magnetic_field', 'optical_beam', 'hull_envelope')
    for it in shot_tools.gather(shot_tools.link_source(ROOT, src), src):
        ob = it['obj']
        if ob.type != 'MESH' or it['kind'] in skip or it['name'].startswith(('Engineering_Envelope', 'Tank_Volume', 'MagneticNozzle_FieldEnvelope')):
            continue
        W = it['matrix']; b = len(vs); vs += [W@v.co for v in ob.data.vertices]
        for poly in ob.data.polygons:
            fs.append(tuple(b+i for i in poly.vertices)); names.append(it['name'])
    return BVHTree.FromPolygons(vs, fs), names


def cone_screen(bvh, names, nozzles, own_prefix):
    """Rays from each nozzle exit along its axis and on cones of CONES_DEG half-angle (16 around); first vehicle hit within CONE_RANGE_M.
    Hits on the nozzle's own pod are ignored (the ray starts at its exit)."""
    from mathutils import Vector
    res = {}
    for p in nozzles:
        e = Vector(p['jet']).normalized(); o = Vector(p['exit'])+e*0.05
        h = Vector((0, 0, 1)) if abs(e.z) < 0.9 else Vector((1, 0, 0)); n1 = e.cross(h).normalized(); n2 = e.cross(n1)
        out = {}
        for half in (0.0,)+CONES_DEG:
            best = None
            for k in range(1 if half == 0 else 16):
                a = 2*math.pi*k/16; th = math.radians(half)
                d = (e*math.cos(th)+(n1*math.cos(a)+n2*math.sin(a))*math.sin(th)).normalized()
                hit = bvh.ray_cast(o, d, CONE_RANGE_M)
                if hit[0] is not None and not names[hit[2]].startswith(own_prefix) and (best is None or hit[3] < best[0]):
                    best = (hit[3], names[hit[2]])
            out[f'{half:.0f}deg'] = None if best is None else dict(distance_m=round(best[0], 2), object=best[1])
        res[p['name']] = out
    return res


def clearance(bvh, names, parts):
    """Every candidate pod / nozzle against the vehicle: overlapping vehicle objects (contacts are the mounting surface)."""
    from mathutils.bvhtree import BVHTree
    import human_entry as he
    import exterior as ex
    from common import cylinder_mesh
    res = {}
    for q in parts:
        if q['shape'] == 'tube':
            vs, fs = cylinder_mesh(q['a'], q['b'], q['r1'], 16)
        else:
            vs, fs = he.box_corners(None, q), ex.FACES
        b = BVHTree.FromPolygons([tuple(v) for v in vs], fs)
        hits = sorted({names[j] for _, j in b.overlap(bvh)})
        res[q['name']] = hits
    return res


def ring_sweep(s, parts):
    """Distance from each pod to the rings' swept envelope (x, half width, outer radius) and to the shield shadow cylinder (r < 45)."""
    import exterior_hardware as eh
    o = eh.obstacles(s); out = {}
    for q in parts:
        if q['shape'] != 'box':
            continue
        x, y, z = q['world_centre']; r = math.hypot(y, z)+max(q['size'][1:])/2
        gaps = [max(abs(x-cx)-half-q['size'][0]/2, 0.0) if r > 0 else None for cx, half, outer in o['rings']]
        out[q['name']] = dict(r_out_m=round(r, 2), shield_r_m=o['shield'][1], inside_shadow=r < o['shield'][1],
                              axial_gap_to_ring_sweep_m=round(min(gaps), 1))
    return out


def build_asset(s, parts, built_nozzles):
    import bpy
    from mathutils import Vector
    from common import material, mesh
    import exterior as ex
    bpy.ops.wm.read_factory_settings(use_empty=True)
    root = bpy.data.collections.new(COLLECTION); bpy.context.scene.collection.children.link(root)
    root['study'] = 'm5_rcs_balanced'; root['status'] = 'LOW POWER CANDIDATE / PERFORMANCE OPEN (15!A212): alternate, not a retrofit'
    pods = bpy.data.collections.new(f'{COLLECTION}_Pods'); root.children.link(pods)
    cones = bpy.data.collections.new(f'{COLLECTION}_Plumes'); root.children.link(cones)
    made = ex.build(pods, parts)
    amber, dark = material('STUDY_RCSB_Pod', (.94, .62, .15)), material('STUDY_RCSB_Nozzle', (.16, .19, .22))
    for ob in made:
        ob.data.materials.clear(); ob.data.materials.append(dark if 'jet_direction' in ob else amber)
        ob['geometry_status'] = 'PROTOTYPE'; ob['canon_status'] = 'STUDY: LOW POWER CANDIDATE / PERFORMANCE OPEN (15!A212)'
        ob['study'] = 'm5_rcs_balanced'; ob['component_id'] = f'WF.STUDY.RCSB.{ob.name}'
    # 15 deg plume cones, 12 m (display): alternate in cyan, as-built in red for comparison
    for group, nozzles, col, kind in (('Alt', [p for p in parts if 'jet' in p], (.20, .75, .95), 'rcs_plume_cone'),
                                      ('Built', built_nozzles, (.95, .30, .22), 'rcs_plume_cone_asbuilt')):
        mat = material(f'STUDY_RCSB_Plume_{group}', col, emission=0.6)
        for p in nozzles:
            e = Vector(p['jet']).normalized(); o = Vector(p['exit']); h = Vector((0, 0, 1)) if abs(e.z) < 0.9 else Vector((1, 0, 0))
            n1 = e.cross(h).normalized(); n2 = e.cross(n1); Lc = 12.0; rr = Lc*math.tan(math.radians(15.0)); n = 24
            vs = [tuple(o)]+[tuple(o+e*Lc+(n1*math.cos(2*math.pi*k/n)+n2*math.sin(2*math.pi*k/n))*rr) for k in range(n)]
            fs = [(0, 1+k, 1+(k+1) % n) for k in range(n)]
            ob = mesh(cones, f'Study_RCSB_Plume_{group}_{p["name"]}', vs, fs, mat, kind=kind)
            ob['study'] = 'm5_rcs_balanced'; ob['geometry_status'] = 'DISPLAY: 15 deg plume core, 12 m, not a flow field'
    ASSET.parent.mkdir(parents=True, exist_ok=True); bpy.ops.wm.save_as_mainfile(filepath=str(ASSET), compress=True)


def main():
    import bpy
    from spec import load
    s = load(ROOT)[0]
    att = json.loads((ROOT/'references/m5_attitude.json').read_text()); cases = att['cases']
    variants = {'B1': candidate(s), 'B2': candidate(s, FWD_DEG_B2, 'RCSB2'), 'B1F': candidate(s, tag='RCSBF', aft_fan_deg=AFT_FAN_DEG)}
    # asset: B1, plus the B1F aft fan nozzles beside its radial ones (pods shared)
    parts = variants['B1']+[p for p in variants['B1F'] if 'jet' in p and p.get('station') == 'aft']; built = as_built(s)
    cm = cases['burnout_1100t']['com_m']
    res = dict(status='LOW POWER CANDIDATE / PERFORMANCE OPEN (S&E 15!A212, 98!A116): alternates beside the as-built S02 jets; no retrofit',
               reference=dict(force_N=F_REF, isp_s=ISP_REF, note='REFERENCE units only (15!A212 H: no assumed 100 N class, no assumed Isp); '
                              'torque and propellant scale with force and 1/Isp; inertia from references/m5_attitude.json (CAD screen, OPEN)'),
               layout=dict(B1=dict(forward_deg=FWD_DEG, note='three new rim pods between Crown bays (asset)'),
                           B2=dict(forward_deg=FWD_DEG_B2, note='the four as-built rim pod bays, roll nozzles recanted outward'),
                           B1F=dict(forward_deg=FWD_DEG, aft_fan_deg=AFT_FAN_DEG, note='B1 with a two-nozzle fan per aft pod in place of '
                                    'the radial nozzle (asset: fan nozzles beside the B1 radial ones)'),
                           aft_deg=AFT_DEG, aft_x_m=AFT_X, roll_cant_outward_deg=ROLL_CANT_DEG,
                           nozzles={k: sum('jet' in p for p in v) for k, v in variants.items()}, as_built_nozzles=len(built)),
               conditioning=dict(J_per_kg=H2_CONDITION_J_KG, note='LH2 at 20 K to warm gas at ~300 K (order of magnitude); a buffer conditioned '
                                 'off-line from waste heat avoids the live load'),
               variants={k: axis_table(s, rows_of([p for p in v if 'jet' in p], cm), cases, strict=True) for k, v in variants.items()},
               as_built=axis_table(s, rows_of(built, cm), cases, strict=False),
               as_built_force_free=axis_table(s, rows_of(built, cm), cases, strict=True),
               com_shift=dict({k: com_independence(lambda c, v=v: rows_of([p for p in v if 'jet' in p], c), cases, True) for k, v in variants.items()},
                              as_built=com_independence(lambda c: rows_of(built, c), cases, False)))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bvh, names = vehicle_bvh()
    res['plume_screen'] = dict(cones_deg=CONES_DEG, range_m=CONE_RANGE_M, as_built=cone_screen(bvh, names, built, 'Ext_RCS'),
                               **{k: cone_screen(bvh, names, [p for p in v if 'jet' in p], 'Study_RCSB') for k, v in variants.items()})
    res['clearance'] = {k: clearance(bvh, names, v) for k, v in variants.items()}
    res['swept_volume'] = {k: ring_sweep(s, v) for k, v in variants.items()}
    OUT_JSON.write_text(json.dumps(res, indent=1)+'\n')
    build_asset(s, parts, built)
    for k, t in list(res['variants'].items())+[('as_built', res['as_built'])]:
        print(k, {a: (v.get('torque_N_m'), (v.get('efficient') or {}).get('lever_m'), v.get('parasitic_force_N')) for a, v in t.items()})
    for k in ('B1', 'B2', 'B1F', 'as_built'):
        hits = {n: {c: (h or {}).get('object') for c, h in v.items()} for n, v in res['plume_screen'][k].items()}
        print(k, 'plume hits', {n: h for n, h in hits.items() if any(h.values())})
    print('clearance', {k: {n: h for n, h in c.items() if h} for k, c in res['clearance'].items()})
    print('shadow', {k: min(v['shield_r_m']-v['r_out_m'] for v in w.values()) for k, w in res['swept_volume'].items()})


if __name__ == '__main__':
    main()
