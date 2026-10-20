"""Build small component libraries, subsystem libraries, and the one vehicle assembly."""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import shutil
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'src/wayfarer'),str(ROOT/'src/wayfarer/build'),str(ROOT/'src/wayfarer/components')]
from spec import load, buildable_configurations
from common import begin, empty, save, link_instance
from recipes import build_component, build_subsystem, entry_guides, human_reference
from rig import rig
import sim_rig
import flight_timeline

COMPONENTS=['NOZZLE','RADIATOR','RING_SECTOR','INTERIOR_HABITATION','INTERIOR_WORK','INTERIOR_GARDEN']
SUBSYSTEMS=['STRUCTURE','HABITAT','STORAGE','SHIELDING','SERVICE','POWER_STORAGE','ROTOR_INTERFACE','CREW_TRANSFER','EYE','FORWARD_SHIELD','DEBUG_MAGNETICS','DEBUG_SEPARATRICES','DEBUG_OPTICS','PROPULSION','THERMAL','HULL','DRONES']
HULL_FAMILY={'HULL'}
# P1F engineering overlays: built before PROPULSION, which links them as DRIVE_DEBUG_* instances whose hide flags follow
# the drive control's toggles (saved off). Vehicles never link them directly.
DEBUG_FAMILY=['DEBUG_MAGNETICS','DEBUG_SEPARATRICES','DEBUG_OPTICS']
# Production files that no longer exist (path under assets/wayfarer -> why). A full build moves each one that is still on disk
# into its own milestones/ folder as <stem>_RETIRED_<UTC>.blend, after checking that nothing hand-made would be lost. Never deleted.
RETIRED={'WF_WAYFARER_001_BURN.blend':'FGR-002 single vehicle; HIGH_POWER is a preset',
         'subsystems/WF_HABITAT_BURN.blend':'FGR-002 no habitat retraction (H3, MEC-011)',
         'subsystems/WF_ROTOR_BAY_DOORS.blend':'FGR-002 no rotor-bay doors (14!A5, H3)',
         'components/WF_HABITAT_POD.blend':'FGR-003 rigid rings: pods replaced by ring sectors (08!A4, H3)'}


def retirement_blockers(path):
    """Open one retired file and list content a retirement would lose; empty when it is a clean generated asset."""
    import bpy
    from common import OWNER
    stem=path.stem
    bpy.ops.wm.open_mainfile(filepath=str(path))
    blockers=[]
    if bpy.context.scene.get('wf_asset')!=stem:blockers.append(f'scene wf_asset is {bpy.context.scene.get("wf_asset")!r}, not {stem!r}')
    art=bpy.data.collections.get(f'ART_{stem}')
    if art is not None and (art.objects or art.children):blockers.append(f'ART_{stem} holds {[o.name for o in art.all_objects]+[c.name for c in art.children]}')
    foreign=[o.name for o in bpy.data.objects if o.library is None and o.get('wf_owner')!=OWNER]
    if foreign:blockers.append(f'objects not owned by {OWNER}: {foreign[:12]}')
    allowed={stem,f'GEN_{stem}',f'ART_{stem}'}
    extra=[c.name for c in bpy.data.collections if c.library is None and c.name not in allowed]
    if extra:blockers.append(f'collections other than {sorted(allowed)}: {extra[:12]}')
    owned={o.name for o in bpy.data.objects if o.library is None and o.get('wf_owner')==OWNER}
    for action in bpy.data.actions:
        if action.library is not None or action.get('wf_owner')==OWNER:continue
        # A local action must be generator-owned, or be used only by generator-owned objects.
        users=[o.name for o in bpy.data.objects if o.library is None and o.animation_data and o.animation_data.action==action and o.name not in owned]
        if users:blockers.append(f'action {action.name!r} is not generated and drives {users[:6]}')
    return blockers


def retire(assets):
    """Move every RETIRED file still present to its milestones/ folder. Aborts (nonzero) listing the content when a file holds anything
    that is not generator-owned; nothing is moved in that case."""
    import bpy
    present=[(rel,assets/rel) for rel in RETIRED if (assets/rel).is_file()]
    problems={rel:retirement_blockers(path) for rel,path in present}
    problems={rel:b for rel,b in problems.items() if b}
    if problems:
        raise SystemExit('WF_RETIRE_BLOCKED '+'; '.join(f'{rel}: {" | ".join(b)}' for rel,b in problems.items()))
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    for rel,path in present:
        # Release the open file before moving it.
        bpy.ops.wm.read_factory_settings(use_empty=True)
        directory=path.parent/'milestones';directory.mkdir(exist_ok=True)
        moved=[]
        for source,suffix in [(path,'.blend'),(path.with_name(path.name+'1'),'.blend1')]:
            if source.is_file():
                destination=directory/f'{path.stem}_RETIRED_{stamp}{suffix}'
                shutil.move(str(source),str(destination));moved.append(destination)
        print(f'WF_RETIRED {rel} -> {moved[0].relative_to(assets)}',flush=True)


def build_characters(root,s,spec_text,source_text):
    """IND-001: the induction figures and their cameras in their own asset (assets/characters/), never linked into the vehicle."""
    from figures import characters
    name=s['characters']['asset'];path=root/'assets/characters'/f'{name}.blend'
    coll,c=begin(path,name);characters(c,s);save(path,coll,spec_text,source_text)


def build(root=ROOT, target='all'):
    s,_,spec_text,source_text=load(root)
    assets=root/'assets/wayfarer'
    valid=['all','vehicle',*COMPONENTS,*SUBSYSTEMS,'CHARACTERS']
    if target not in valid:raise ValueError(f'target must be one of {valid}')
    if target=='CHARACTERS':
        build_characters(root,s,spec_text,source_text);return
    if set(s['interior']['components'].values())!={c for c in COMPONENTS if c.startswith('INTERIOR_')}:raise ValueError('interior.components must match the INTERIOR_ components')
    if target in COMPONENTS:
        dependencies={'NOZZLE':['PROPULSION'],'RADIATOR':['THERMAL'],'RING_SECTOR':['HABITAT']}
        dependencies|={c:['HABITAT'] for c in COMPONENTS if c.startswith('INTERIOR_')}
        parts=[target];systems=dependencies[target]
    elif target=='all':parts=COMPONENTS;systems=SUBSYSTEMS
    elif target=='PROPULSION':parts=[];systems=[*DEBUG_FAMILY,'PROPULSION']
    elif target in DEBUG_FAMILY:parts=[];systems=[target,'PROPULSION']
    elif target in SUBSYSTEMS:parts=[];systems=[target]
    else:parts=[];systems=[]
    for name in parts:
        path=assets/f'components/WF_{name}.blend'
        coll,c=begin(path,f'WF_{name}')
        build_component(name,c,s)
        save(path,coll,spec_text,source_text)
    for name in systems:
        path=assets/f'subsystems/WF_{name}.blend'
        coll,c=begin(path,f'WF_{name}')
        build_subsystem(name,c,s,assets)
        save(path,coll,spec_text,source_text)
    # One vehicle file: every non-debug subsystem is linked once; configurations are presets posed on its linked controls.
    asset_name=s['vehicle']['asset']
    path=assets/(asset_name+'.blend')
    coll,c=begin(path,asset_name)
    root_obj=empty(c,'WF_ROOT',ident=s['asset_id'],kind='asset_root')
    root_obj['source_spec']='data/wayfarer_3d.toml'
    root_obj['saved_preset']=s['vehicle']['saved_preset']
    root_obj['configurations']=buildable_configurations(s)
    for name in SUBSYSTEMS:
        # A disabled hull is still built (never stale) but not linked.
        if name in HULL_FAMILY and not s['hull']['enabled']:continue
        if name in DEBUG_FAMILY:continue
        obj=link_instance(c,assets/f'subsystems/WF_{name}.blend',f'WF_{name}',f'Assembly_{name}',ident=f'WF.SUBSYSTEM.{name}')
        obj.parent=root_obj
    human_reference(c,s)
    entry_guides(c,s)
    rig(c,s,root_obj)
    import bpy
    bpy.context.scene['configuration']=s['vehicle']['saved_preset']
    bpy.context.scene.render.fps=24
    bpy.context.scene.frame_end=361
    bpy.context.scene.frame_set(1)
    save(path,coll,spec_text,source_text)
    if target=='all':retire(assets)
    # The greeting staging follows the entry stations (SERVICE).
    if target in ('all','SERVICE'):build_characters(root,s,spec_text,source_text)
    # The rig contract travels with the vehicle so fixtures stay self-consistent.
    print('WF_SIM_RIG',sim_rig.write(root),flush=True)
    print('WF_FLIGHT_TIMELINE',flight_timeline.write(root),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--target',default='all')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    build(args.root.resolve(),args.target)
