"""SERV-002-2026-10-10 (S&E 15!A123, 98!A89, 09 OD-022/030, 12A SP-46/49/52, 42 FAB-030): NONCANON forward service-district mock-ups,
screened in memory against the saved vehicle (nothing is saved, no generator reads this).

The owner prefers the forward stationary region X ~100.4-108.9 m for a first packaging study (the aft X 70-81.2 m stays the fallback) and
lets Claude PROPOSE, not commit, a pressure-isolated access beyond the trunk's forward end: a shared structural district with separate
containment for (1) a clean crewed workshop, (2) a sealed hot/dirty manufacturing cell and (3) the stationary ~450 K SP-52 warm machinery
(15!C123, G123). No approved port, room volume, mass allocation, radiator capacity or machine catalogue (15!H123); hot work never in open
crew air (98!D89). Two access options, the same three containments:

- A, trunk extension: the 1.6 m trunk continues forward in the spine bore past its end (X 102.45 m) behind a new district hatch, and the
  workshop opens off it through a 0.90 m radial port (the refuge port's size), as SP-45 does off the trunk;
- B, external corridor: a 1.2 m corridor leaves the trunk through a new 0.90 m radial port in the trunk's last free metre, rises clear of
  the spine and runs forward outside it to the workshop; the spine bore forward of the trunk stays untouched.

In both, the sealed cell sits radially outboard of the workshop behind its own wall (a pass-through, no crew entry while it runs, its own
exhaust to space), and the warm module sits on the opposite side of the spine in its own non-habitable containment (robot or EVA service),
its feed and return running radially to the nearest Q38 candidate warm panel. Every dimension is PROTOTYPE. The screen: each envelope at
mechanical_clearance_m against every stationary mesh and every rotating sweep and inside the hull (storeroom_survey.Obstacles); the suited
(0.70 m) and robot (0.60 m cube) envelopes through each opening; the thrust ladder's reach under 1.5 g aft-down; shell area and a PROTOTYPE
shell mass (inside the existing 60 t service/cargo category, 42 G34, never added to the root budget).

    /snap/bin/blender -b --python src/wayfarer/studies/serv002_district.py -- --out runs/<stamp>-serv002
"""
from pathlib import Path
import argparse
import json
import math
import sys
import bpy
from mathutils import Matrix, Vector
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/build'), str(ROOT/'src/wayfarer/studies')]
from spec import load
import crew_transfer as ct
import human_entry as he
import hull_geometry
import layout
import warm_panels
import storeroom_survey as sv

WORKSHOP = (4.0, 2.5, 2.4)       # tangential, radial, axial clear (the machine-bay envelope, SERVICE_HOST_SURVEY.md)
CELL = (1.6, 1.2, 1.4)           # sealed hot/dirty cell, clear (one enclosed machine and its exhaust; FAB-030)
WARM = (2.0, 1.5, 1.5)           # SP-52 warm utility module (pumps, exchanger, buffer; TH-SP52)
PORT_CLEAR = 0.90                # radial ports (the refuge port's size)
CORRIDOR_CLEAR = 1.20            # option B corridor
SUITED, ROBOT = 0.70, 0.60
SHELL_KG_M2 = 20.0               # PROTOTYPE pressure-shell areal mass (shell, frames, seals; no MMOD, inside the hull)
PHI_SCAN = range(0, 360, 10)


def envelope(x0, x1, phi, u0, u1, half_t, grow=0.0):
    return sv.box(x0, x1, phi, u0, u1, half_t, grow)


def shell_area(dx, du, dt):
    return 2*(dx*du+dx*dt+du*dt)


def screen(s, obs, b, ignore=()):
    c = s['prototype']['mechanical_clearance_m']
    g = envelope(b['x'][0], b['x'][1], b['phi'], b['u'][0], b['u'][1], b['t'][1], c)
    return dict(hits=sorted(obs.hits(g, ignore=ignore)), inside_hull=sv.inside_hull(s, g))


def rooms(s, x0, phi, d):
    """Workshop, sealed cell and warm module boxes (walls included) for a workshop floor at X x0, angle phi, inner face d."""
    w = s['human_entry']['chamber_wall_m']
    W = envelope(x0, x0+WORKSHOP[2]+2*w, phi, d, d+WORKSHOP[1]+2*w, WORKSHOP[0]/2+w)
    u1 = W['u'][1]
    C = envelope(x0, x0+CELL[2]+2*w, phi, u1, u1+CELL[1]+2*w, CELL[0]/2+w)
    M = envelope(x0+.4, x0+.4+WARM[2]+2*w, phi+math.pi, d, d+WARM[1]+2*w, WARM[0]/2+w)
    return dict(workshop=W, cell=C, warm=M)


def warm_feed(s, M):
    """Straight-line feed length from the warm module's outer face centre to the nearest candidate warm panel corner (routing OPEN)."""
    xm = sum(M['x'])/2; um = M['u'][1]; p = Vector((xm, um*math.cos(M['phi']), um*math.sin(M['phi'])))
    best = min(((Vector(c)-p).length, q['name']) for q in warm_panels.panels(s) for c in q['corners'])
    return dict(length_m=round(best[0], 2), panel=best[1])


def option_a(s, obs, phi):
    c, w = s['crew_transfer'], s['human_entry']['chamber_wall_m']; tr = c['trunk_clear_radius_m']; x_end = ct.stationary(s)[0]['points'][1][0]
    x0 = 103.6; d = layout.spine_radius_at(s, x0)+s['prototype']['mechanical_clearance_m']
    R = rooms(s, x0, phi, d); W = R['workshop']
    xport = W['x'][0]+w+PORT_CLEAR/2; ext_end = xport+PORT_CLEAR/2+c['passage_wall_m']+0.3
    ext = dict(x=(x_end, ext_end), radius=tr+c['passage_wall_m'])
    port = envelope(xport-PORT_CLEAR/2-c['passage_wall_m'], xport+PORT_CLEAR/2+c['passage_wall_m'], phi, tr, d, PORT_CLEAR/2+c['passage_wall_m'])
    out = dict(option='A trunk extension', phi_deg=round(math.degrees(phi)), workshop_floor_x=x0, inner_face_d=round(d, 3),
               extension=dict(x0=round(x_end, 3), x1=round(ext_end, 3), clear_m=2*tr, length_m=round(ext_end-x_end, 3),
                              spine_clear=ext_end < 108.5-s['prototype']['mechanical_clearance_m'],
                              note='inside the spine bore; the bore forward of the trunk is assumed hollow to the shield column (108.5 m)'),
               port=dict(x=round(xport, 3), clear_m=PORT_CLEAR, run=screen(s, obs, port, ignore=('Structural_Spine', 'Crew_Trunk'))),
               new_pressure_interfaces=['district hatch at the trunk end (seats from the trunk side)', 'workshop port hatch',
                                        'cell pass-through (sealed)', 'warm-module service hatch (non-habitable)'])
    return out, R, [port], ext


def option_b(s, obs, phi):
    c, w = s['crew_transfer'], s['human_entry']['chamber_wall_m']; tr = c['trunk_clear_radius_m']; x_end = ct.stationary(s)[0]['points'][1][0]
    clr = s['prototype']['mechanical_clearance_m']; rc = CORRIDOR_CLEAR/2+c['passage_wall_m']
    xp = x_end-c['passage_wall_m']-PORT_CLEAR/2-0.10                      # the new port in the trunk's last free metre
    bad = [n for n, x, th, r in he.openings(s) if math.cos(ct.angle_diff(phi, th)) > 0 and abs(x-xp) < r+PORT_CLEAR/2+c['passage_wall_m']+s['human_entry']['opening_margin_m']
           and tr*abs(math.sin(ct.angle_diff(phi, th))) < r+PORT_CLEAR/2+c['passage_wall_m']+s['human_entry']['opening_margin_m']]
    rise = envelope(xp-PORT_CLEAR/2-c['passage_wall_m'], xp+PORT_CLEAR/2+c['passage_wall_m'], phi, tr, layout.spine_radius_at(s, xp)+clr+2*rc, PORT_CLEAR/2+c['passage_wall_m'])
    uc = layout.spine_radius_at(s, xp)+clr+rc                               # corridor axis radius
    x0 = 103.6; corr = envelope(xp-rc, x0, phi, uc-rc, uc+rc, rc)
    d = uc+rc                                                              # the workshop stands on the corridor's outer face
    R = rooms(s, x0, phi, layout.spine_radius_at(s, x0)+clr)
    out = dict(option='B external corridor', phi_deg=round(math.degrees(phi)), workshop_floor_x=x0, inner_face_d=round(R['workshop']['u'][0], 3),
               trunk_port=dict(x=round(xp, 3), clear_m=PORT_CLEAR, opening_conflicts=bad, run=screen(s, obs, rise, ignore=('Structural_Spine', 'Crew_Trunk'))),
               corridor=dict(clear_m=CORRIDOR_CLEAR, axis_r=round(uc, 3), x=[round(xp-rc, 3), round(x0, 3)], length_m=round(x0-xp+rc, 3),
                             screen=screen(s, obs, corr, ignore=('Structural_Spine',)), shell_m2=round(2*math.pi*rc*(x0-xp+rc), 1)),
               new_pressure_interfaces=['trunk port hatch (seats from the trunk side)', 'workshop end hatch', 'cell pass-through (sealed)',
                                        'warm-module service hatch (non-habitable)'])
    return out, R, [rise, corr], None


def assess(s, obs, R):
    out = {}
    for k, b in R.items():
        sc = screen(s, obs, b); dx, du, dt = b['x'][1]-b['x'][0], b['u'][1]-b['u'][0], b['t'][1]-b['t'][0]
        out[k] = dict(**sc, x=[round(v, 3) for v in b['x']], u=[round(v, 3) for v in b['u']], phi_deg=round(math.degrees(b['phi'])) % 360,
                      clear_volume_m3=round({'workshop': math.prod(WORKSHOP), 'cell': math.prod(CELL), 'warm': math.prod(WARM)}[k], 2),
                      shell_m2=round(shell_area(dx, du, dt), 1), shell_mass_t=round(shell_area(dx, du, dt)*SHELL_KG_M2/1e3, 2))
    out['warm']['feed_to_nearest_candidate_panel'] = warm_feed(s, R['warm'])
    return out


def render(s, boxes, ext, out, tag):
    made = []
    cols = dict(workshop=(.25, .55, 1.0, 1), cell=(1.0, .2, .15, 1), warm=(1.0, .6, .05, 1), passage=(.2, .85, .3, 1))
    for k, b in boxes:
        me = bpy.data.meshes.new(f'ART_SERV002_{k}'); me.from_pydata([tuple(v) for v in b['corners']], [], sv.FACES)
        ob = bpy.data.objects.new(f'ART_SERV002_{k}', me); bpy.context.scene.collection.objects.link(ob)
        mat = bpy.data.materials.new(f'ART_SERV002_{k}'); mat.diffuse_color = cols['passage' if k.startswith('passage') else k]; me.materials.append(mat); made.append(ob)
    if ext:
        bpy.ops.mesh.primitive_cylinder_add(radius=ext['radius'], depth=ext['x'][1]-ext['x'][0], location=((ext['x'][0]+ext['x'][1])/2, 0, 0), rotation=(0, math.pi/2, 0))
        ob = bpy.context.active_object; ob.name = 'ART_SERV002_extension'; mat = bpy.data.materials.new('ART_SERV002_ext'); mat.diffuse_color = cols['passage']
        ob.data.materials.append(mat); made.append(ob)
    hidden = [o for o in bpy.data.objects if o.name.startswith(('Hull_', 'Blade_', 'Radiator', 'Coolant', 'Forward_Leading', 'Shield_', 'Brow_', 'Crown', 'Disruptor', 'Ring_', 'Sector_', 'Crew_Tube', 'Ring', 'EYE', 'Dust_Lance', 'Bypass_', 'Warm_Panel'))]
    for o in hidden:
        o.hide_render = True
    sc = bpy.context.scene; cam = bpy.data.objects.new('CAM_SERV002', bpy.data.cameras.new('CAM_SERV002')); sc.collection.objects.link(cam); sc.camera = cam
    sc.render.engine = 'BLENDER_WORKBENCH'; sc.display.shading.light = 'STUDIO'; sc.display.shading.color_type = 'MATERIAL'; sc.display.shading.show_cavity = True
    sc.render.resolution_x, sc.render.resolution_y = 1400, 900
    phi = boxes[0][1]['phi']; t = Vector((0.0, -math.sin(phi), math.cos(phi))); u = Vector((0.0, math.cos(phi), math.sin(phi))); c = Vector((104.5, 0, 0))
    paths = []
    for view, loc, look, up, scale, ortho in (('side', c+t*30.0, -t, u, 18.0, True), ('section', Vector((106.0, 0, 0)), Vector((-1, 0, 0)), u, 16.0, True),
                                              ('three_quarter', c+t*10+u*8-Vector((9, 0, 0)), None, Vector((1, 0, 0)), None, False)):
        if look is None:
            look = (c-loc).normalized()
        z = -look.normalized(); x = up.cross(z).normalized(); y = z.cross(x)
        cam.location = loc; cam.rotation_euler = Matrix((x, y, z)).transposed().to_euler()
        cam.data.type = 'ORTHO' if ortho else 'PERSP'
        if ortho:
            cam.data.ortho_scale = scale
        else:
            cam.data.lens = 24
        cam.data.clip_start = 0.1 if view != 'section' else 0.0; cam.data.clip_end = 80.0 if view != 'section' else 3.4
        p = out/f'serv002_{tag}_{view}.png'; sc.render.filepath = str(p); bpy.ops.render.render(write_still=True); paths.append(p.name)
    for o in hidden:
        o.hide_render = False
    for o in made:
        bpy.data.objects.remove(o)
    bpy.data.objects.remove(cam)
    return paths


def main(out):
    s = load(ROOT)[0]; out.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/wayfarer'/(s['vehicle']['asset']+'.blend'))); bpy.context.scene.frame_set(1); obs = sv.Obstacles()
    L = he.trunk_ladder(s); result = dict(study='SERV-002-2026-10-10 forward service district mock-ups (NONCANON)', ladder_top_x=round(L['top'], 3),
                                          trunk_end_x=round(ct.stationary(s)[0]['points'][1][0], 3), shell_kg_m2=SHELL_KG_M2, options={})
    for name, fn in (('A', option_a), ('B', option_b)):
        found = []
        for deg in PHI_SCAN:
            phi = math.radians(deg); o, R, extra, ext = fn(s, obs, phi); a = assess(s, obs, R)
            clean = all(not q['hits'] and q['inside_hull'] for q in a.values())
            runs = [o.get('port', {}).get('run'), o.get('trunk_port', {}).get('run'), o.get('corridor', {}).get('screen')]
            clean = clean and all(not r['hits'] for r in runs if r) and not o.get('trunk_port', {}).get('opening_conflicts')
            if clean:
                found.append((deg, o, R, extra, ext, a))
        if not found:
            result['options'][name] = dict(result='NO CLEAR ANGLE', scanned_deg=list(PHI_SCAN)); continue
        deg, o, R, extra, ext, a = min(found, key=lambda f: f[5]['warm']['feed_to_nearest_candidate_panel']['length_m'])
        w = s['human_entry']['chamber_wall_m']; sill = o['workshop_floor_x']+w
        o.update(clear_angles_deg=[f[0] for f in found], rooms=a,
                 thrust_access=dict(sill_x=round(sill, 3), ladder_top_x=round(L['top'], 3), ladder_extension_m=round(sill-L['top'], 2)),
                 suited_through_ports=PORT_CLEAR-SUITED, robot_through_ports=PORT_CLEAR-ROBOT*math.sqrt(2),
                 total_new_shell_m2=round(sum(q['shell_m2'] for q in a.values())+(o.get('corridor', {}).get('shell_m2') or 0)+
                                          (2*math.pi*ext['radius']*(ext['x'][1]-ext['x'][0]) if ext else 0), 1))
        o['total_shell_mass_t'] = round(o['total_new_shell_m2']*SHELL_KG_M2/1e3, 2)
        o['renders'] = render(s, [(k, R[k]) for k in ('workshop', 'cell', 'warm')]+[(f'passage_{i}', b) for i, b in enumerate(extra)], ext, out, name)
        result['options'][name] = o
        print('WF_SERV002', name, deg, json.dumps({k: (v['hits'], v['inside_hull']) for k, v in a.items()}), flush=True)
    (out/'serv002.json').write_text(json.dumps(result, indent=1, default=str)+'\n')
    print('WF_SERV002 done', out, flush=True)


if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    ap = argparse.ArgumentParser(); ap.add_argument('--out', type=Path, required=True); a = ap.parse_args(argv)
    main(a.out if a.out.is_absolute() else ROOT/a.out)
