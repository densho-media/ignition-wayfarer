"""HUM-002 study (SP-45, 33!B93 "Survey available 5x2.5x2.4m room ... hatch opening and 1.5g access; no unapproved model revision"):
where the compact walk-in storeroom fits in the saved vehicle, in memory (nothing is saved).

A candidate is the owner's clear cuboid (33!C85:C87) inside walls of human_entry.chamber_wall_m, standing with its 2.4 m height along +X:
under thrust aft is down, so its aft wall is the floor (as in the refuge). In the cross-section its 5 m side is tangential and its 2.5 m side
radial, from an inner face at d from the ship axis. It is screened at mechanical_clearance_m against every stationary hardware mesh at the
saved COAST pose (surface overlap and vertices inside), against the swept annulus of every rotating part and inside the hull's inner radius.
For each free placement the study asks what access exists without revising the model: a radial port (the refuge port's 0.90 m clear) off
the crew trunk with its sill on the room's floor, clear of the trunk's existing branch openings and of everything between the spine and the
room, and whether the trunk ladder (human_entry.trunk_ladder) reaches that sill with aft down (1.5 g). Placements below the trunk's aft end
are listed separately: they can only be reached through the trunk floor. Workbench renders of representative placements.

--room L W H and --label survey another envelope the same way (WK-HYBRID-2026-10-10 stationary machine bay, TH-SP52 warm machinery module,
15!A114:A115): an envelope candidate only, never a new pressure room (15!H115, 42 FAB-019, FAB-024).

    /snap/bin/blender -b --python src/wayfarer/studies/storeroom_survey.py -- --out runs/<stamp>-sp45 [--room 4.0 2.5 2.4 --label machine_bay]
"""
from pathlib import Path
import argparse
import json
import math
import sys
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/build')]
from spec import load
import crew_transfer as ct
import human_entry as he
import hull_geometry
import layout

ROOM = (5.0, 2.5, 2.4)                    # 33!C85:C87 compact clear length, width, height (PROTOTYPE, DIMENSIONS PROVISIONAL)
ROTATING = {'WF_HABITAT', 'WF_HABITAT_A', 'WF_HABITAT_B', 'WF_RING_SECTOR', 'WF_INTERIOR_HABITATION', 'WF_INTERIOR_WORK', 'WF_INTERIOR_GARDEN'}
SKIP_KINDS = {'plasma', 'optical_beam', 'magnetic_field', 'hull_envelope', 'scale_reference', 'entry_camera'}
SKIP_NAMES = ('MagneticNozzle_FieldEnvelope', 'Body_Envelope_Reference', 'Human_')
FACES = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
ZONES = {'FWD': (93.35, 110.0, 0.05), 'AFT': (70.0, 81.35, 0.10)}     # x0 scan ranges and steps (the forward collar; the body aft of the trunk)
PHI_STEP = 5.0
D_STEPS = (0.0, 0.25, 0.5, 1.0, 1.5)    # inner-face offsets beyond the spine clearance
PORT_CLEAR = 0.90                       # the refuge port's clear size (human_entry.refuge_port_clear_m)


class Obstacles:
    """Stationary meshes (per object: BVH, vertices, bounds) and rotating swept annuli at the saved pose."""
    def __init__(self):
        self.objs, self.annuli = [], []
        for inst in bpy.context.evaluated_depsgraph_get().object_instances:
            obj = inst.object
            if obj.type not in {'MESH', 'CURVE'} or obj.get('kind') in SKIP_KINDS or obj.name.startswith(SKIP_NAMES):
                continue
            data = obj.to_mesh(); m = inst.matrix_world; vs = [m@v.co for v in data.vertices]; fs = [tuple(p.vertices) for p in data.polygons]
            obj.to_mesh_clear()
            if not vs or not fs:
                continue
            lib = obj.original.library; sub = Path(lib.filepath).stem if lib else 'WF_WAYFARER_001'
            if sub in ROTATING:
                rs = [math.hypot(v.y, v.z) for v in vs]
                self.annuli.append((min(v.x for v in vs), max(v.x for v in vs), min(rs), max(rs), obj.name)); continue
            a = np.array([tuple(v) for v in vs])
            self.objs.append(dict(name=obj.name, kind=obj.get('kind') or '', tree=BVHTree.FromPolygons(vs, fs), v=a, lo=a.min(0), hi=a.max(0)))
        self.lo = np.array([o['lo'] for o in self.objs]); self.hi = np.array([o['hi'] for o in self.objs])

    def hits(self, b, ignore=()):
        """Names of what the box b (box()) meets: surface overlap or a vertex inside."""
        vs = b['corners']; lo = np.array([tuple(v) for v in vs]).min(0); hi = np.array([tuple(v) for v in vs]).max(0)
        near = np.nonzero(np.all(self.lo <= hi, 1) & np.all(self.hi >= lo, 1))[0]
        out = set(); tree = None; cu, su = math.cos(b['phi']), math.sin(b['phi'])
        for i in near:
            o = self.objs[i]
            if o['name'].startswith(ignore):
                continue
            v = o['v']; u = v[:, 1]*cu+v[:, 2]*su; t = -v[:, 1]*su+v[:, 2]*cu
            if np.any((v[:, 0] > b['x'][0]) & (v[:, 0] < b['x'][1]) & (u > b['u'][0]) & (u < b['u'][1]) & (t > b['t'][0]) & (t < b['t'][1])):
                out.add(o['name']); continue
            tree = tree or BVHTree.FromPolygons(vs, FACES)
            if o['tree'].overlap(tree):
                out.add(o['name'])
        rlo, rhi = max(b['u'][0], 0.0), max(math.hypot(v.y, v.z) for v in vs)
        out |= {n for a0, a1, r0, r1, n in self.annuli if a0 < b['x'][1] and a1 > b['x'][0] and r0 < rhi and r1 > rlo}
        return out


def box(x0, x1, phi, u0, u1, half_t, grow=0.0):
    u = Vector((0.0, math.cos(phi), math.sin(phi))); t = Vector((0.0, -math.sin(phi), math.cos(phi)))
    xs, us, ts = (x0-grow, x1+grow), (u0-grow, u1+grow), (-half_t-grow, half_t+grow)
    return dict(corners=[Vector((x, 0.0, 0.0))+u*a+t*c for x in xs for a in us for c in ts], x=xs, u=us, t=ts, phi=phi)


def room(s, x0, phi, d, grow=0.0):
    """The room's outer box (walls included): X [x0, x0+H], radial [d, d+W], tangential +-L/2."""
    w = s['human_entry']['chamber_wall_m']; L, W, H = (v+2*w for v in ROOM)
    return box(x0, x0+H, phi, d, d+W, L/2, grow)


def inside_hull(s, b):
    return all(math.hypot(v.y, v.z) <= hull_geometry.inner_radius_at(s, v.x) for v in b['corners'])


def access(s, obs, x0, phi, d):
    """Trunk port check for a free room: the port's sill on the room's clear floor; its opening clear of the trunk's existing branches
    (opening_margin_m), its run from the spine to the room clear of hardware; and the thrust ladder's reach."""
    h, c, w = s['human_entry'], s['crew_transfer'], s['human_entry']['chamber_wall_m']; clr = s['prototype']['mechanical_clearance_m']
    trunk = ct.stationary(s)[0]; floor, top = trunk['points'][0][0]+c['passage_wall_m'], trunk['points'][1][0]-c['passage_wall_m']
    rc = PORT_CLEAR/2; ro = rc+c['passage_wall_m']; xc = x0+w+rc
    out = dict(port_x=xc, sill_x=x0+w)
    if not (floor <= xc-ro and xc+ro <= top):
        out['trunk'] = f'port X {xc-ro:.2f}-{xc+ro:.2f} m outside the trunk ({floor:.2f}-{top:.2f} m)'; return out
    tr = c['trunk_clear_radius_m']; bad = []
    for name, x, th, r in he.openings(s):
        dth = ct.angle_diff(phi, th)
        if math.cos(dth) > 0 and abs(x-xc) < r+ro+h['opening_margin_m'] and tr*abs(math.sin(dth)) < r+ro+h['opening_margin_m']:
            bad.append(name)
    run = obs.hits(box(xc-ro, xc+ro, phi, layout.spine_radius_at(s, xc), d, ro, clr), ignore=('Structural_Spine', 'Crew_Trunk'))
    out['trunk'] = 'clear' if not bad and not run else f"conflicts: {sorted(set(bad)|run)}"
    L = he.trunk_ladder(s); out['ladder_top_x'] = L['top']
    out['thrust_access'] = L['floor'] <= x0+w <= L['top']
    return out


def survey(s, obs):
    c = s['prototype']['mechanical_clearance_m']; free = []
    for zone, (a, b, step) in ZONES.items():
        for i in range(int(round((b-a)/step))+1):
            x0 = a+i*step; H = ROOM[2]+2*s['human_entry']['chamber_wall_m']
            dmin = max(layout.spine_radius_at(s, x0), layout.spine_radius_at(s, x0+H))+c
            for k in range(int(360/PHI_STEP)):
                phi = math.radians(k*PHI_STEP)
                for dd in D_STEPS:
                    d = dmin+dd; b = room(s, x0, phi, d, c)
                    if not inside_hull(s, b):
                        break
                    if not obs.hits(b):
                        free.append(dict(zone=zone, x0=round(x0, 3), phi_deg=k*PHI_STEP, d=round(d, 3))); break
    return free


def families(s, obs, free):
    """Contiguous x0 runs per zone with the free angles, and the access screen of each run's middle placement at each free angle band."""
    out = []
    for zone in ZONES:
        rows = sorted((f for f in free if f['zone'] == zone), key=lambda f: f['x0']); runs = []
        for f in rows:
            if runs and f['x0']-runs[-1][-1]['x0'] <= ZONES[zone][2]+1e-6:
                runs[-1].append(f)
            elif not runs or f['x0'] != runs[-1][-1]['x0']:
                runs.append([f])
        for run in runs:
            xs = sorted({f['x0'] for f in run}); phis = sorted({f['phi_deg'] for f in run}); mid = xs[len(xs)//2]
            picks = [f for f in run if f['x0'] == mid]
            acc = [dict(f, **access(s, obs, f['x0'], math.radians(f['phi_deg']), f['d'])) for f in picks]
            out.append(dict(zone=zone, x0_range=[xs[0], xs[-1]], room_x_range=[xs[0], xs[-1]+ROOM[2]+2*s['human_entry']['chamber_wall_m']],
                            free_angles_deg=phis, placements=len(run), access_at_mid=acc))
    return out


LABEL = 'sp45'


def render(s, pick, out, size, tag):
    """A translucent room at the pick, the hull and radiators hidden; a side view square on the room and an axial section looking aft."""
    vs = room(s, pick['x0'], math.radians(pick['phi_deg']), pick['d'])['corners']
    me = bpy.data.meshes.new(f'ART_SP45_{tag}'); me.from_pydata([tuple(v) for v in vs], [], FACES); ob = bpy.data.objects.new(f'ART_SP45_{tag}', me)
    bpy.context.scene.collection.objects.link(ob); mat = bpy.data.materials.new('ART_SP45'); mat.diffuse_color = (1.0, .25, .55, 1.0); me.materials.append(mat)
    hidden = [o for o in bpy.data.objects if o.name.startswith(('Hull_', 'Blade_', 'Radiator', 'Coolant', 'Forward_Leading', 'Shield_', 'Brow_', 'Crown', 'Disruptor', 'Bypass_', 'EYE', 'Dust_Lance', 'Ring_', 'Sector_', 'Crew_Tube', 'Ring'))]
    for o in hidden:
        o.hide_render = True
    sc = bpy.context.scene; cam = bpy.data.objects.new(f'CAM_SP45_{tag}', bpy.data.cameras.new(f'CAM_SP45_{tag}')); sc.collection.objects.link(cam); sc.camera = cam
    sc.render.engine = 'BLENDER_WORKBENCH'; sc.display.shading.light = 'STUDIO'; sc.display.shading.color_type = 'MATERIAL'; sc.display.shading.show_cavity = True
    sc.render.resolution_x = sc.render.resolution_y = size; cam.data.type = 'ORTHO'
    phi = math.radians(pick['phi_deg']); xm = pick['x0']+1.25; centre = Vector((xm, 0.0, 0.0))
    t = Vector((0.0, -math.sin(phi), math.cos(phi)))
    paths = []
    for view, loc, look, up, scale in (('side', centre+t*30.0, -t, Vector((0, math.cos(phi), math.sin(phi))), 26.0),
                                       ('section', Vector((xm+1.40, 0.0, 0.0)), Vector((-1.0, 0.0, 0.0)), Vector((0, math.cos(phi), math.sin(phi))), 15.0)):
        z = -look.normalized(); x = up.cross(z).normalized(); y = z.cross(x)
        cam.location = loc; cam.rotation_euler = Matrix((x, y, z)).transposed().to_euler()
        cam.data.ortho_scale = scale; cam.data.clip_start = 0.1 if view == 'side' else 0.0; cam.data.clip_end = 80.0 if view == 'side' else 2.6
        p = out/f'{LABEL}_{tag}_{view}.png'; sc.render.filepath = str(p); bpy.ops.render.render(write_still=True); paths.append(p.name)
    for o in hidden:
        o.hide_render = False
    bpy.data.objects.remove(ob); bpy.data.objects.remove(cam)
    return paths


def main(out, size):
    s = load(ROOT)[0]; out.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/wayfarer'/(s['vehicle']['asset']+'.blend')))
    bpy.context.scene.frame_set(1); obs = Obstacles()
    free = survey(s, obs); fam = families(s, obs, free)
    result = dict(room_clear_m=ROOM, wall_m=s['human_entry']['chamber_wall_m'], clearance_m=s['prototype']['mechanical_clearance_m'],
                  trunk_x=[p[0] for p in ct.stationary(s)[0]['points']], ladder_top_x=he.trunk_ladder(s)['top'], families=fam, free=free)
    renders = {}
    for f in fam:
        best = next((a for a in f['access_at_mid'] if a.get('trunk') == 'clear'), f['access_at_mid'][0] if f['access_at_mid'] else None)
        if best:
            tag = f"{f['zone']}_{best['x0']:.2f}_{int(best['phi_deg'])}"
            renders[tag] = render(s, best, out, size, tag)
    result['renders'] = renders
    (out/'survey.json').write_text(json.dumps(result, indent=1))
    print('WF_SURVEY', LABEL, json.dumps({k: v for k, v in result.items() if k != 'free'}, indent=1), flush=True)


if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    ap = argparse.ArgumentParser(); ap.add_argument('--out', type=Path, required=True); ap.add_argument('--size', type=int, default=900)
    ap.add_argument('--room', type=float, nargs=3, metavar=('L', 'W', 'H')); ap.add_argument('--label', default='sp45')
    a = ap.parse_args(argv); LABEL = a.label
    if a.room:
        ROOM = tuple(a.room)
    main(a.out if a.out.is_absolute() else ROOT/a.out, a.size)
