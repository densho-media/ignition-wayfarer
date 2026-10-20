"""FWD-V2 Eye placement study (Eye 45 FD-E01..E03, S&E 50 AG-004..AG-007): the four EYE wells at r = 4 m (WORKING), 16 m and 24 m (STUDY) on
the saved vehicle, rendered for comparison. Nothing is saved and no asset or source value changes.

For r 16 / 24 the linked EYE and forward-shield assemblies are hidden in memory and rebuilt from the same generators with only
forward_defense.eye_wells.centre_radius_m moved (eye_placement.variant); the skin and the disruptor layer get the wells and ports cut by a boolean
(study only: the production skin cuts wells only in the flat hub). Truss members and layer posts the wells cross are painted red; the shared EYE
mount is removed where it no longer carries a facet (support OPEN). B_array stays 8 m (WORKING).

With --alt-truss (owner answers 2026-10-13, Eye 45 FD-A01/A02, S&E 50 AG-A01/A02) the outer variants instead get the reversible alternate
truss of eye_truss_study: the replaced spokes, ring and posts are removed and the collars, branches, ring arcs, relocated posts, per-facet
frames (blue) and aft-face raceways (orange) are added; the window-cartridge service path is drawn in green. Members still crossing a well
would stay red.

    /snap/bin/blender -b --factory-startup --python src/wayfarer/studies/eye_placement_study.py -- --out runs/<stamp>-fwd-eye [--radius 16] [--size 768] [--alt-truss]
"""
from pathlib import Path
import argparse
import json
import math
import sys
import bpy
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/build'), str(ROOT/'src/wayfarer/presentation'), str(ROOT/'src/wayfarer/components')]
from common import material, line, cylinder
import eye_truss_study as ets
from spec import load
import eye_placement as ep
import forward_shield as fsh
import preview

VIEWS = ['bow', 'threequarter', 'shield_detail', 'shield_profile_detail', 'eye_facet_detail', 'crown_detail']
STATES = ['DEFENSE_ENGAGED']


class Study:
    def __init__(self, r, alt=False):
        self.r = r; self.alt = alt and not math.isclose(r, 4.0)
        self.note = (f"FWD-V2 r {r:g} m ALTERNATE TRUSS (STUDY, FD-A01/A02): blue collars, branches, ring arcs, posts, facet frames | orange raceways | "
                     f"green cartridge path | r4 + B_array 8 m stay WORKING; mass, FEA, optics OPEN" if self.alt else
                     f"FWD-V2 EYE PLACEMENT r {r:g} m: {ep.STATUS[r]} | B_array 8 m = r4 calibration only | red = truss member / layer post crossed by a well (PROTOTYPE layout finding)")

    def spec(self, s):
        self.screen = ep.screen(s, self.r)
        return ep.variant(s, self.r)

    def apply(self, s, state):
        if math.isclose(self.r, 4.0):
            return
        import recipes
        import forward
        for name in ('Assembly_EYE', 'Assembly_FORWARD_SHIELD'):
            obj = bpy.data.objects[name]; obj.hide_render = obj.hide_viewport = True
        c = bpy.data.collections.new(f'ART_STUDY_FWD_EYE_R{self.r:g}'); bpy.context.scene.collection.children.link(c)
        recipes.build_subsystem('EYE', c, s, ROOT/'assets/wayfarer')
        forward.forward_shield(c, s)
        local = [o for o in c.objects]
        get = lambda n: next(o for o in local if o.name == n or o.name.startswith(n+'.'))
        if not self.screen['structure']['support'].startswith('shared'):
            bpy.data.objects.remove(get('EYE_Shared_Mount'), do_unlink=True); local = list(c.objects)
        # Wells on the cone: cut the skin at the well radius and the layer at the derived port radius (study booleans, in memory).
        layer = fsh.disruptor_layers(s)[0]
        for target, radius in (('Shield_Skin', fsh.prototype(s)['well_diameter_m']/2), (layer['name'], fsh.eye_port_radius(s, layer))):
            obj = get(target)
            for w in fsh.wells(s):
                if fsh.in_hub(s, w):
                    continue
                bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=radius, depth=12, location=(w['x1'], w['y'], w['z']), rotation=(0, math.pi/2, 0))
                cutter = bpy.context.active_object; cutter.hide_render = True; cutter.display_type = 'WIRE'
                mod = obj.modifiers.new(f'Study_Well_{w["index"]}', 'BOOLEAN'); mod.operation = 'DIFFERENCE'; mod.object = cutter; mod.solver = 'EXACT'
        if self.alt:
            self.alternate(s, c, get)
            local = list(c.objects)
        red = material('StudyClash', (.95, .12, .08), 1.0)
        n = fsh.prototype(s)['truss_spoke_count']; crossed = set() if self.alt else set(self.screen['structure']['layer_posts_crossed'])
        spoke_ids = {k+1 for k in range(n) if any(abs(((2*math.pi*(k+.5)/n-math.atan2(w['z'], w['y'])+math.pi) % (2*math.pi))-math.pi) < 1e-6 for w in fsh.wells(s))}
        ring_ids = {i+1 for i, x in enumerate(fsh.truss(s)['rings']) if x['radius'] in self.screen['structure']['truss_rings_crossed']}
        if self.alt:
            spoke_ids, ring_ids = set(), set()
        for o in local:
            base = o.name.split('.')[0]
            if (base.startswith('Truss_Spoke_') and int(base.split('_')[2]) in spoke_ids) or (base.startswith('Truss_Ring_') and int(base.split('_')[2]) in ring_ids) \
                    or base in crossed:
                o.data.materials.clear(); o.data.materials.append(red)
        ctrl = next(o for o in c.objects if o.name.startswith('FORWARD_DEFENSE_CTRL'))
        values = fsh.display_pose(s, state) if state in s['forward_defense']['display_poses'] else fsh.configuration_state(s, state)
        for k, v in values.items():
            ctrl[k] = float(v)
        ctrl.update_tag()
        for o in local:
            o.update_tag()
        bpy.context.scene.frame_set(bpy.context.scene.frame_current)

    def alternate(self, s, c, get):
        alt = ets.alternate(s)
        for name in alt['removed']:
            obj = next(o for o in c.objects if o.name == name or o.name.startswith(name+'.'))
            bpy.data.objects.remove(obj, do_unlink=True)
        mats = {'raceway': material('StudyRaceway', (.95, .55, .10), 1.0)}
        blue = material('StudyAlternate', (.15, .45, .95), 1.0)
        for o in alt['members']:
            mat = mats.get(o['role'], blue)
            if o.get('plate'):
                (x0, y, z), (x1, _, _) = o['pts']
                cylinder(c, o['name'], (x0+x1)/2, x1-x0, o['radius'], mat, y, z)
            else:
                line(c, o['name'], o['pts'], o['radius'], mat)
        green = material('StudyServicePath', (.15, .85, .30), 1.0)
        for w in fsh.wells(s):
            if fsh.in_hub(s, w):
                continue
            acc = ets.cartridge_access(s, alt, w, alt['members']+ets._kept(s, alt))
            line(c, f'Study_Eye{w["index"]}_Cartridge_Path', acc['path'], 0.08, green)
            (x, y, z) = acc['path'][-1]
            cylinder(c, f'Study_Eye{w["index"]}_Cartridge_Out', x, 0.05, acc['window_radius_m'], green, y, z)


if __name__ == '__main__':
    a = argparse.ArgumentParser(); a.add_argument('--out', type=Path, required=True); a.add_argument('--radius', type=float, nargs='+', default=list(ep.RADII))
    a.add_argument('--size', type=int, default=768); a.add_argument('--alt-truss', action='store_true'); a.add_argument('--views', nargs='+', default=VIEWS); a.add_argument('--states', nargs='+', default=STATES)
    args = a.parse_args(sys.argv[sys.argv.index('--')+1:])
    for r in args.radius:
        study = Study(r, args.alt_truss)
        for state in args.states:
            out = args.out/f'r{r:g}'/state.lower()
            preview.render(ROOT, args.views, args.size, state, out, study=study)
        (args.out/f'r{r:g}'/'screen.json').write_text(json.dumps(study.screen, indent=1)+'\n')
        if study.alt:
            (args.out/f'r{r:g}'/'alternate.json').write_text(json.dumps(ets.screen(load(ROOT)[0], r), indent=1, default=str)+'\n')
        print(f'WF_EYE_STUDY r{r:g}', flush=True)
