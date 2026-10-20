"""M5 Godot subsystem hologram package (owner 2026-10-18: S&E 15!A217 OWN-M5-PRODUCTION, 98!A119 "build one functional Godot
subsystem scene from existing GLB"). Presentation data over the published runtime package; no geometry is rebuilt or duplicated:

  m5/wf_m5_holo.json    every node of the published wayfarer.glb classified into the twelve M5 subsystems by shots/m5_subsystems.toml
                        (the table the Blender holograms use), the study parts' records, and the propulsion/fuel chapters with their
                        owner rows, statuses and the numbers read from the M5 study references (no value is typed here).
  m5/m5_studies.glb     the saved M5 study assets WF_STUDY_BODY_C, WF_STUDY_DRIVE_SUPPORT and WF_STUDY_RCS_BALANCED as they are (STUDY / NONCANON; meshes
                        and transforms unchanged, materials dropped: Godot draws the overlay colour), in the runtime frame (x,z,-y).

The overlay colours are explanatory, never ship materials. Unsolved systems are not marked functional (15!A217 H): each chapter
carries its OPEN/HOLD badges and deficits from the owner rows. Run by runtime-export after the COAST export (needs its manifest):

    blender -b --factory-startup --python-exit-code 1 --python src/wayfarer/export/m5_hologram.py -- --out <godot/generated>
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer')]
import representation as rp
sys.path[:0] = [str(ROOT/'src/wayfarer/export')]
import m6_holo

STUDIES = (('WF_STUDY_BODY_C', 'BODY-C fuel/reaction-mass packaging study (S&E 15!A207 WORKING STUDY CHOICE; 98!A115)'),
           ('WF_STUDY_DRIVE_SUPPORT', 'magnetic-nozzle support study: cryostats, cold-mass supports, cooling, quench, axial bipod '
                                      'comparison frame (15!A214/A215; 98!A118)'),
           ('WF_STUDY_RCS_BALANCED', 'balanced RCS study B1 / B1F pods and 15 deg plume-core display cones, as-built cores for comparison '
                                     '(15!A212 LOW POWER CANDIDATE; 98!A116)'))
# Shown faint and never by default: the field envelope is a display surface that reads as a solid bell (M5 slice 4; 15!A217 G "no
# misleading field/nozzle animations").
HIDDEN = {'MagneticNozzle_FieldEnvelope*': 'magnetic field display surface: drawn as a solid bell it misreads as an exhaust tube'}


def item_of(record):
    """The shot-item fields the subsystem selectors read, from a runtime manifest record."""
    return dict(key=record['node'], component_id=record['component_id'], name=record['source_name'], kind=record['kind'],
                group=record['lineage'][0], source=record.get('source_ref', ''))


def chapters(root):
    """The propulsion/fuel walk: established physics, prototype engineering and unresolved capacity, each with its owner rows."""
    body = json.loads((root/'references/m5_body_c.json').read_text())
    drive = json.loads((root/'references/m5_drive_support.json').read_text())
    noz = json.loads((root/'references/m5_nozzle_mounts.json').read_text())
    gnc = json.loads((root/'references/m5_gnc_comms.json').read_text())
    fp, rs = gnc['modes']['FORWARD_PROTECTED'], gnc['modes']['rcs_reference']['sets']
    c, s62, mass = body['conventions']['C'], body['s62'], body['mass_t']
    pick, frame = drive['built_pickup'][0], drive['thrust_frame']
    sup, bore = drive['cold_mass_supports'], {b['coil']: b for b in drive['cryostat']['bore']}
    need = drive['cryostat']['plasma_clearance_needed_m']
    angles = [f['angle_from_axis_deg'] for f in frame]
    return [
        dict(id='thrust', title='Thrust chain: reactor, magnetic manifold, four nozzles', show=['S10'],
             select=['subsystem:S10', 'name:Thrust_Ring*', 'kind:thrust_node*', 'name:Nozzle_Pickup*'],
             badges=[['CANON', 'LOCKED: four magnetic nozzles off one manifold (28)'], ['HOLD', 'P0 drive physics not released (15!A200)'],
                     ['PROTOTYPE', 'rigged geometry; no solid exhaust tube: the field envelope stays hidden']],
             lines=[f"Proof load {drive['loads']['design_N_per_nozzle']/1e6:.2f} MN per nozzle is a STRUCTURAL PROOF value, not operating "
                    f"thrust (15!A214); flight {drive['loads']['flight_N_per_nozzle']/1e6:.2f} MN per nozzle is DIAGNOSTIC.",
                    'The plasma is shown as its static COAST pose (off). No field, plasma or cryogenic animation is implied.']),
        dict(id='fuel', title='Fuel and reaction mass: ideal need against BODY-C packaging', show=['S05', 'S06'],
             select=['subsystem:S05', 'subsystem:S06', 'kind:shortfall_scale', 'kind:refrigeration_frame', 'kind:transfer_pump_frame',
                     'kind:vent_frame', 'kind:transfer_manifold'],
             colors=[['kind:shortfall_scale', [0.95, 0.25, 0.25], 'unhoused volume, scale comparison only (not a tank)']],
             badges=[['DERIVED', 'He-3 and D: ideal reacted lower bounds only (15!A208)'], ['HOLD', 'inventory, recycle and return OPEN'],
                     ['STUDY', 'BODY-C keel lane, reversible (15!A207); not installed tanks'], ['OPEN', 'capacity deficits stay visible']],
             lines=[f"Ideal lower bounds: He-3 {mass['HE3']:.0f} t at {body['temperature_K']['HE3']} K, D2 {mass['D2']:.0f} t and H2 at "
                    f"{body['temperature_K']['D2']:.0f} K.",
                    f"BODY-C holds {c['net_liquid_m3']:,} m3 net liquid. First-ignition liquid needs {s62['first_ignition_liquid_m3']:,} m3: "
                    f"DEFICIT {c['first_ignition_liquid_margin_m3']:,} m3. Full load {s62['liquid_total_m3']:,} m3: DEFICIT "
                    f"{c['liquid_margin_m3']:,} m3.",
                    'The shortfall blocks are scale comparisons, not tank locations. Inventory is not trimmed and the hull is not '
                    'resized to hide the gap (15!A207).']),
        dict(id='cryo', title='Coil cryogenics: cryostats, supports, cooling and quench', show=['S07', 'S08'],
             select=['kind:cryo_coil_*', 'kind:cryo_cooler', 'kind:cryo_coolant_line', 'kind:drive_power_lead', 'kind:drive_quench_dump',
                     'name:Nozzle_Coil*', 'name:Nozzle_Yoke*'],
             colors=[['kind:cryo_coil_support', [0.95, 0.56, 0.17], 'cold-mass supports (direct, 0.015 m to the yoke)'],
                     ['kind:cryo_cooler', [0.98, 0.80, 0.30], 'cryocoolers'], ['kind:cryo_coolant_line', [0.40, 0.80, 0.95], 'helium lines'],
                     ['kind:drive_quench_dump', [0.35, 0.80, 0.35], 'quench dump and current leads'],
                     ['kind:drive_power_lead', [0.35, 0.80, 0.35], ''], ['name:Nozzle_Yoke*', [0.55, 0.55, 0.58], 'warm yokes (as built)']],
             badges=[['PROTOTYPE', 'cryostat, support, cooler and quench envelopes (STUDY parts)'], ['OPEN', 'heat loads, cooler power, stored energy'],
                     ['HOLD', 'coil temperature, current, quench (OD-024/025, 15!A215)']],
             lines=[f"Cold-mass supports, support term only: {sup['direct']['heat_leak_W_per_nozzle']:.0f} W per nozzle direct "
                    f"against {sup['reentrant']['heat_leak_W_per_nozzle']:.0f} W re-entrant (proxy at "
                    f"{drive['prototype']['coil_K']:.0f} K). The re-entrant mount needs a larger yoke standoff.",
                    'REBCO-class HTS at 20-30 K is a research envelope; 20 K is a comparison point, not a qualified operating '
                    'temperature (15!A215). Nuclear and radiative coil loads are OPEN.']),
        dict(id='loadpath', title='Nozzle load path: as-built pickup against the axial bipod study', show=['S10'],
             select=['name:Nozzle_*', 'name:Thrust_Ring*', 'kind:thrust_node*', 'kind:drive_thrust_strut', 'kind:cryo_coil_*'],
             colors=[['name:Nozzle_Pickup*', [0.95, 0.28, 0.22], 'as-built pickup (78.7 deg off axis)'],
                     ['kind:drive_thrust_strut', [0.94, 0.70, 0.15], 'outboard bipod struts (slice 4 STUDY; F8 adds an inboard pair)'],
                     ['kind:thrust_node*', [0.55, 0.75, 0.95], 'thrust ring nodes']],
             badges=[['PROTOTYPE', 'as-built pickup, unchanged until architecture release (15!A214)'],
                     ['STUDY', 'symmetric axial frame F8: preferred comparison (NOZ-2)'], ['OPEN', 'FEA, real ring section, hub/spine share']],
             lines=[f"As built: pickup {pick['angle_from_axis_deg']} deg off axis carries {pick['strut_force_MN']} MN and pushes "
                    f"{pick['in_plane_ring_load_MN']} MN into the ring plane per nozzle.",
                    f"Outboard bipods alone (slice 4, drawn): {min(angles)}-{max(angles)} deg off axis but not in moment equilibrium: "
                    f"{noz['frames'][0]['F4']['unbalanced_moment_MN_m']['proof_axial']} MN m per nozzle left over.",
                    f"Symmetric frame F8 (NOZ-2: plus inboard bipods to the central hub, not drawn here): <= "
                    f"{max(m['max_compression_MN'] for f in noz['frames'] for m in f['F8']['members'])} MN per member over the proof, vector "
                    f"and member-loss cases; {noz['ring']['F8']['in_plane']['max_node_load_MN']} MN in-plane per ring node against "
                    f"{noz['ring']['as_built']['in_plane']['max_node_load_MN']} MN as built.",
                    f"Throat bore with cryostat and strike module: {bore['Nozzle_Coil_02']['strike_on_jacket_gap_m']} m and "
                    f"{bore['Nozzle_Coil_03']['strike_on_jacket_gap_m']} m against the >= {need} m study constraint: FAIL."]),
        dict(id='gnc', title='Attitude and comms: modes, contact, light time, store and forward', show=['S11'],
             select=['subsystem:S11', 'kind:rcs_balanced_*', 'kind:rcs_plume_cone*', 'name:Shield_Rim*'],
             colors=[['kind:rcs_balanced_*', [0.94, 0.62, 0.15], 'balanced RCS study pods B1 / B1F (STUDY, not a retrofit)'],
                     ['kind:comms_antenna', [0.09, 0.75, 0.81], 'HGA dishes, gimbals and optical terminal (aft, COAST pose)']],
             badges=[['TARGET', 'L2 TARGET ONLY: <= 0.2 deg 3-sigma hold, not a certified cap (15!A211)'],
                     ['HOLD', 'high-speed 180 deg flip FORBIDDEN; 21 min ideal flip is sensitivity only'],
                     ['OPEN', 'link budget and achieved rate null; disturbances, dust limit, momentum storage OPEN (15!A210)'],
                     ['ILLUSTRATIVE', gnc['backlog']['display_note']]],
             lines=[f"Shield shadow: geometric limit {fp['geometric_limit_deg']:.2f} deg at {fp['geometric_limit_azimuth_deg']:.0f} deg "
                    f"({fp['binding_part']}); the 0.2 deg target uses {fp['target_over_limit']:.0%} of it, with no margin for dust or plasma.",
                    f"RCS per 100 N / 300 s REFERENCE: as-built yaw {rs['as_built']['yaw+']['torque_N_m']/1e3:.1f} kN m with "
                    f"{rs['as_built']['yaw+']['parasitic_force_N']:.0f} N drift; B1F yaw {rs['B1F']['yaw+']['torque_N_m']/1e3:.1f} kN m, force-free.",
                    'Earth by antenna gimbal only. Burns need no Earth line of sight: every burn is a planned outage behind the plume '
                    '(15!C210). Contact is geometry from the built model; bytes and kb/s are null for GROUND_34M and Y155_RELAY.'],
             gnc={k: gnc[k] for k in ('modes', 'light_time', 'scenarios', 'contacts', 'backlog', 'sky', 'rcs_patterns', 'shadow', 'com_m',
                                      'year_s', 'au_light_s', 'distances_au', 'plume_deg', 'status')}),
    ]


def package(root, out):
    """wf_m5_holo.json: subsystem table, node classification and chapters over the published COAST manifest."""
    manifest = json.loads((out/'manifest.json').read_text())
    subs = rp.load_subsystems(root, 'm5_subsystems.toml')
    table = {s['id']: dict(name=s['name'], color=list(s['color']), sources=s['sources'], maturity=s['maturity']) for s in subs}
    table['CTX'] = dict(name=rp.CONTEXT['name'], color=list(rp.CONTEXT['color']), sources=rp.CONTEXT['sources'],
                        maturity=rp.CONTEXT['maturity'])
    nodes, items = {}, []
    for r in manifest['nodes']:
        item = item_of(r)
        item['subsystem'] = rp.classify(item, subs)['id']
        items.append(item)
        nodes[r['node']] = dict(s=item['subsystem'], c=[round(v, 3) for v in rp.subsystem_color(item, subs)])
    studies = json.loads((out/'m5'/'m5_studies.json').read_text())
    for p in studies:
        item = dict(key=p['node'], component_id=p['component_id'], name=p['name'], kind=p['kind'], group='STUDY', source=p['source_ref'])
        item['subsystem'] = rp.classify(item, subs)['id']
        p.update(subsystem=item['subsystem'], color=[round(v, 3) for v in rp.subsystem_color(item, subs)])
        items.append(item)
    chs = chapters(root)+m6_holo.chapters(root, out)   # M6 (15!A220, 15!A227): EYE / shield, habitat, radiators
    for ch in chs:
        ch['nodes'] = sorted(rp.select(items, ch['select']))
        # Chapter emphasis colours (explanatory, like the subsystem overlay) and their legend; the first matching selector wins.
        ch['tint'] = {}
        for sel, rgb, _ in ch.get('colors', []):
            for key in sorted(rp.select(items, sel) & set(ch['nodes'])):
                ch['tint'].setdefault(key, rgb)
        ch['legend'] = [[rgb, text] for _, rgb, text in ch.pop('colors', []) if text]
    hidden = {i['key']: why for i in items for pat, why in HIDDEN.items() if rp.matches(i, 'name:'+pat)}
    data = dict(schema=1, contract='WF_M5_HOLO',
                status='APPROVED REVERSIBLE L3 PROTOTYPE / NO FLIGHT GO (S&E 15!A217, 15!A220, 98!A119, 98!A121)',
                rule='Overlay colours explain function and are never ship materials. Vehicle nodes are the published COAST package; '
                     'study parts (m5_studies.glb) are STUDY / NONCANON. Nothing here marks an unsolved system functional.',
                manifest_sha256=__import__('hashlib').sha256((out/'manifest.json').read_bytes()).hexdigest(),
                subsystems=table, nodes=nodes, studies=dict(files=['m5_studies.glb'], collections=[dict(name=n, what=w) for n, w in STUDIES],
                parts=studies), hidden=hidden, chapters=chs)
    (out/'m5'/'wf_m5_holo.json').write_text(json.dumps(data, indent=0)+'\n')
    counts = {}
    for n in nodes.values():
        counts[n['s']] = counts.get(n['s'], 0)+1
    return dict(nodes=len(nodes), study_parts=len(studies), by_subsystem=dict(sorted(counts.items())), hidden=len(hidden),
                chapters={c['id']: len(c['nodes']) for c in chs})


def export_studies(root, out):
    """The saved study assets as one GLB, object names replaced by stable ids (records keep the source names)."""
    import bpy
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    records = []
    for name, _ in STUDIES:
        path = root/'assets/wayfarer/studies'/f'{name}.blend'
        with bpy.data.libraries.load(str(path), link=False) as (src, dst):
            dst.collections = [name]
        col = dst.collections[0]
        for ob in sorted(col.all_objects, key=lambda o: o.name):
            if ob.type != 'MESH':
                continue
            node = f'M5S_{len(records):04d}'
            records.append(dict(node=node, name=ob.name, study=name, kind=ob.get('kind', 'geometry'),
                                component_id=ob.get('component_id', ob.name), geometry_status=ob.get('geometry_status', 'PROTOTYPE'),
                                canon_status='STUDY / NONCANON', source_ref=ob.get('source_ref', ''), note=ob.get('note', '')))
            copy = bpy.data.objects.new(node, ob.data)
            copy.matrix_world = ob.matrix_world.copy()
            scene.collection.objects.link(copy)
    (out/'m5').mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=str(out/'m5'/'m5_studies.glb'), export_format='GLB', use_active_scene=True,
                              export_materials='NONE', export_animations=False, export_cameras=False, export_lights=False, export_yup=True)
    (out/'m5'/'m5_studies.json').write_text(json.dumps(records, indent=0)+'\n')
    return len(records)


def main():
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=Path, default=ROOT/'godot/generated', help='the package directory holding manifest.json')
    ap.add_argument('--root', type=Path, default=ROOT, help='repository root (shots/, references/, study assets)')
    args = ap.parse_args(argv)
    export_studies(args.root, args.out)
    print('WF_M5_HOLO', json.dumps(package(args.root, args.out)))


if __name__ == '__main__':
    main()
