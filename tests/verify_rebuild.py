"""Exercise rebuild/preservation/relocation in temporary copies, never production."""
from pathlib import Path
import hashlib
import json
import shutil
import argparse
import os
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]


def details_on(*hosts):
    """Detail asset files anchored on these hosts (docs/MODULES.md): a host target rebuilds them with the host."""
    import sys
    sys.path.insert(0,str(ROOT/'src/wayfarer'))
    import modules
    return {f'{asset}.blend' for asset,host in modules.detail_hosts(ROOT).items() if host in hosts}
BLENDER=os.environ.get('WAYFARER_BLENDER','/snap/bin/blender')
BUILD=ROOT/'src/wayfarer/build/build.py'
INSPECT=ROOT/'src/wayfarer/validation/inspect.py'


def run(*args, success=True):
    command=[BLENDER,'--background','--factory-startup','--python-exit-code','1',*map(str,args)]
    result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,timeout=int(os.environ.get('WAYFARER_STEP_TIMEOUT',900)))
    if (result.returncode==0)!=success:
        raise RuntimeError(result.stdout[-3000:]+result.stderr[-3000:])
    return result


def checksum(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(root,target='all'):
    run('--python',BUILD,'--','--root',root,'--target',target)


def inspect(root,out):
    run('--python',INSPECT,'--','--root',root,'--output',out)
    return json.loads(out.read_text())


DUMMY='''import bpy
bpy.ops.wm.read_factory_settings(use_empty=True)
scene=bpy.context.scene;scene['wf_asset']={stem!r}
root=bpy.data.collections.new({stem!r});scene.collection.children.link(root)
gen=bpy.data.collections.new('GEN_'+{stem!r});art=bpy.data.collections.new('ART_'+{stem!r});root.children.link(gen);root.children.link(art)
obj=bpy.data.objects.new('Generated_Marker',None);obj['wf_owner']='wayfarer.p0';obj['component_id']='DUMMY';gen.objects.link(obj)
if {art!r}:
    hand=bpy.data.objects.new('Hand_Made_Art',None);hand['artist_note']='keep';art.objects.link(hand)
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath={path!r})
'''


def main(report_path=ROOT/'references/p1_regression.json'):
    with tempfile.TemporaryDirectory(prefix='wayfarer-regression-') as temp:
        fixture=Path(temp)/'fixture'
        for folder in ['data','assets','simulations']:
            shutil.copytree(ROOT/folder,fixture/folder,ignore=shutil.ignore_patterns('milestones'))
        assets=fixture/'assets/wayfarer'
        baseline=inspect(fixture,Path(temp)/'baseline.json')
        habitat=assets/'subsystems/WF_HABITAT.blend'
        expression=f'''import bpy
bpy.ops.wm.open_mainfile(filepath={str(habitat)!r})
for collection_name,object_name in [('ART_WF_HABITAT','Manual_Art_Sentinel'),('GEN_WF_HABITAT','Unowned_GEN_Sentinel')]:
    obj=bpy.data.objects.new(object_name,None)
    obj.location=(1.25,2.5,3.75)
    obj['artist_note']='preserve exactly'
    bpy.data.collections[collection_name].objects.link(obj)
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
'''
        run('--python-expr',expression)
        before_backup=checksum(habitat)
        build(fixture)
        first=inspect(fixture,Path(temp)/'first.json')
        assert baseline['assets']==first['assets'],'Generated semantic structure changed on rebuild'
        backups=list((habitat.parent/'milestones').glob('WF_HABITAT_*.blend'))
        assert any(checksum(p)==before_backup for p in backups),'Original asset not backed up exactly'
        print('PASS full rebuild, stable generated IDs, exact milestone backup',flush=True)
        build(fixture)
        second=inspect(fixture,Path(temp)/'second.json')
        assert first['assets']==second['assets'],'Duplicate accumulation on second identical build'
        expression=f'''import bpy
bpy.ops.wm.open_mainfile(filepath={str(habitat)!r})
for name in ['Manual_Art_Sentinel','Unowned_GEN_Sentinel']:
    obj=bpy.data.objects[name]
    assert tuple(obj.location)==(1.25,2.5,3.75)
    assert obj['artist_note']=='preserve exactly'
    assert obj.name in bpy.data.collections['ART_WF_HABITAT'].objects
'''
        run('--python-expr',expression)
        print('PASS repeated build and preserved ART/unowned GEN content',flush=True)
        excluded={'WF_RADIATOR.blend','WF_THERMAL.blend','WF_WAYFARER_001.blend',*details_on('WF_RADIATOR','WF_THERMAL')}
        unchanged={p:checksum(p) for p in assets.rglob('*.blend') if 'milestones' not in p.parts and p.name not in excluded}
        build(fixture,'RADIATOR')
        assert all(checksum(p)==h for p,h in unchanged.items()),'Targeted build modified unrelated assets'
        targeted=inspect(fixture,Path(temp)/'targeted.json')
        assert second['assets']==targeted['assets']
        print('PASS targeted radiator rebuild; unrelated assets byte-identical',flush=True)
        excluded={'WF_HULL.blend','WF_WAYFARER_001.blend',*details_on('WF_HULL')}
        unchanged={p:checksum(p) for p in assets.rglob('*.blend') if 'milestones' not in p.parts and p.name not in excluded}
        build(fixture,'HULL')
        assert all(checksum(p)==h for p,h in unchanged.items()),'Targeted hull build modified unrelated assets'
        assert inspect(fixture,Path(temp)/'hull.json')['assets']==targeted['assets']
        print('PASS targeted hull rebuild; unrelated assets byte-identical',flush=True)
        excluded={'WF_INTERIOR_GARDEN.blend','WF_HABITAT.blend','WF_WAYFARER_001.blend',*details_on('WF_INTERIOR_GARDEN','WF_HABITAT')}
        unchanged={p:checksum(p) for p in assets.rglob('*.blend') if 'milestones' not in p.parts and p.name not in excluded}
        build(fixture,'INTERIOR_GARDEN')
        assert all(checksum(p)==h for p,h in unchanged.items()),'Targeted interior build modified unrelated assets'
        assert inspect(fixture,Path(temp)/'interior.json')['assets']==targeted['assets']
        print('PASS targeted Garden interior rebuild; unrelated assets byte-identical',flush=True)
        # Modular detail (docs/MODULES.md): a detail target rewrites only its own file; the host and vehicle see it through their links.
        excluded={'WF_DETAIL_M7_RA1.blend'}
        unchanged={p:checksum(p) for p in assets.rglob('*.blend') if 'milestones' not in p.parts and p.name not in excluded}
        build(fixture,'DETAIL_M7_RA1')
        assert all(checksum(p)==h for p,h in unchanged.items()),'Detail build modified other assets'
        assert inspect(fixture,Path(temp)/'detail.json')['assets']==targeted['assets']
        print('PASS detail-only rebuild; every other asset byte-identical',flush=True)
        # A pack with two assemblies on moving anchors (the despun drum and the rotor): one joined target, its two files only.
        excluded={'WF_DETAIL_M7_XFR.blend','WF_DETAIL_M7_SPK.blend'}
        unchanged={p:checksum(p) for p in assets.rglob('*.blend') if 'milestones' not in p.parts and p.name not in excluded}
        build(fixture,'DETAIL_M7_SPK+DETAIL_M7_XFR')
        assert all(checksum(p)==h for p,h in unchanged.items()),'Joined detail build modified other assets'
        assert inspect(fixture,Path(temp)/'detail_ring.json')['assets']==targeted['assets']
        print('PASS joined detail rebuild on moving anchors; every other asset byte-identical',flush=True)
        relocated=Path(temp)/'relocated'
        shutil.copytree(fixture,relocated,ignore=shutil.ignore_patterns('milestones'))
        moved=inspect(relocated,Path(temp)/'moved.json')
        assert targeted['assets']==moved['assets'],'Relocation changed dependency structure'
        print('PASS relocated project loads all relative nested libraries',flush=True)
        # Retirement (FGR-002): a full build moves a RETIRED file that is a clean generated asset into its milestones/ folder, and
        # refuses, listing the content, one that holds anything hand-made.
        retired=assets/'subsystems/WF_ROTOR_BAY_DOORS.blend'
        assert not retired.exists(),'Retired files must already be gone from a built project'
        run('--python-expr',DUMMY.format(path=str(retired),stem='WF_ROTOR_BAY_DOORS',art=False))
        result=run('--python',BUILD,'--','--root',fixture)
        assert not retired.exists() and 'WF_RETIRED subsystems/WF_ROTOR_BAY_DOORS.blend' in result.stdout,'Clean retired file was not moved'
        moved_files=list((retired.parent/'milestones').glob('WF_ROTOR_BAY_DOORS_RETIRED_*.blend'))
        assert len(moved_files)==1,moved_files
        assert inspect(fixture,Path(temp)/'retired.json')['assets']==targeted['assets'],'Retirement changed production assets'
        print('PASS full build moves a clean retired file into milestones/ (never deletes)',flush=True)
        guarded=assets/'WF_WAYFARER_001_BURN.blend'
        run('--python-expr',DUMMY.format(path=str(guarded),stem='WF_WAYFARER_001_BURN',art=True))
        before_guard=checksum(guarded)
        refused=run('--python',BUILD,'--','--root',fixture,success=False)
        assert 'WF_RETIRE_BLOCKED' in refused.stdout+refused.stderr and 'ART_WF_WAYFARER_001_BURN' in refused.stdout+refused.stderr,'Retirement did not list the hand-made content'
        assert guarded.exists() and checksum(guarded)==before_guard,'A blocked retirement changed the file'
        assert not list(assets.glob('milestones/WF_WAYFARER_001_BURN_RETIRED_*'))
        guarded.unlink()
        print('PASS retirement is refused, listing the content, when a retired file holds ART content',flush=True)
        spec=fixture/'data/wayfarer_3d.toml'
        spec.write_text(spec.read_text().replace('value = 225.0','value = 245.0',1))
        asset_hashes={p:checksum(p) for p in assets.rglob('*.blend') if 'milestones' not in p.parts}
        run('--python',BUILD,'--','--root',fixture,success=False)
        assert all(checksum(p)==h for p,h in asset_hashes.items()),'Invalid inputs wrote asset files'
        print('PASS invalid input propagates nonzero exit before any asset mutation',flush=True)
    report={'result':'PASS','tests':[f'save/reopen all {len(targeted["assets"])} production assets; the one vehicle file','simulation rig contract regenerated and checked','two identical-input builds','unique stable generated IDs','preserve ART and unowned GEN sentinels','exact backup of overwritten asset','targeted radiator rebuild leaves unrelated assets byte-identical','targeted hull rebuild leaves unrelated assets byte-identical','targeted Garden interior rebuild leaves unrelated assets byte-identical','relocated nested relative links','snapshot and source-map hashes','invalid spec fails CLI before asset writes','retired file (generated, empty ART) is moved to milestones by a full build','retired file holding an ART object aborts the build and stays byte-identical'],'production_assets_modified_by_tests':False}
    report_path.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--report',type=Path,default=ROOT/'references/p1_regression.json')
    main(p.parse_args().report)
