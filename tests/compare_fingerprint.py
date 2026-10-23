"""Compare two geometry fingerprints with float tolerance. Pure Python."""
from pathlib import Path
import argparse
import json
import math
import sys


def same(a,b,tol):
    if isinstance(a,float) or isinstance(b,float):
        return isinstance(a,(int,float)) and isinstance(b,(int,float)) and math.isclose(a,b,abs_tol=tol)
    if isinstance(a,list) and isinstance(b,list):
        return len(a)==len(b) and all(same(x,y,tol) for x,y in zip(a,b))
    if isinstance(a,dict) and isinstance(b,dict):
        return a.keys()==b.keys() and all(same(a[k],b[k],tol) for k in a)
    return a==b


def compare(before,after,allow_added=(),allow_new_files=(),tol=1e-6):
    report={'changed':[],'removed':[],'added':[],'allowed_added':[],'files_removed':[],'files_added':[],'links_changed':[]}
    for name in sorted(set(before)|set(after)):
        if name not in after:report['files_removed'].append(name);continue
        if name not in before:
            (report['allowed_added'] if name in allow_new_files else report['files_added']).append(name);continue
        b,a=before[name]['objects'],after[name]['objects']
        for obj in sorted(set(b)|set(a)):
            if obj not in a:report['removed'].append(f'{name}:{obj}')
            elif obj not in b:(report['allowed_added'] if obj.startswith(tuple(allow_added)) else report['added']).append(f'{name}:{obj}')
            elif not same(b[obj],a[obj],tol):
                keys=[k for k in set(b[obj])|set(a[obj]) if not same(b[obj].get(k),a[obj].get(k),tol)]
                report['changed'].append(f'{name}:{obj}:{sorted(keys)}')
        extra=[x for x in after[name]['direct_links'] if x not in before[name]['direct_links']]
        if [x for x in before[name]['direct_links'] if x not in after[name]['direct_links']] or [x for x in extra if not any(f in x for f in allow_new_files)]:
            report['links_changed'].append(name)
    report['result']='PASS' if not any(report[k] for k in ['changed','removed','added','files_removed','files_added','links_changed']) else 'FAIL'
    return report


IDENTITY=[[1.0,0.0,0.0,0.0],[0.0,1.0,0.0,0.0],[0.0,0.0,1.0,0.0],[0.0,0.0,0.0,1.0]]


def relocate(before,after,prefix,old_file,new_file,instance,tol=1e-6):
    """A baseline rewritten for a detail migration (docs/MODULES.md): the objects named prefix* move from old_file to new_file, where they sit
    unparented at identity, and old_file gains the collection instance that links new_file. It is accepted only if the move kept every object's
    world placement: the instance (in the host, after) sits exactly where each moved object sat (before) and under the same parent. Comparing
    the result with `after` then proves the migration changed nothing else. Raises ValueError otherwise."""
    import copy
    out=copy.deepcopy(before);old=out[old_file]['objects']
    moved={n:old.pop(n) for n in sorted(old) if n.startswith(prefix)}
    if not moved:raise ValueError(f'no {prefix}* objects in {old_file}')
    inst=after[old_file]['objects'].get(instance)
    if inst is None:raise ValueError(f'{instance} missing from {old_file}')
    for n,q in moved.items():
        if q['parent']!=inst['parent'] or not same(q['matrix_world'],inst['matrix_world'],tol):
            raise ValueError(f'{n}: was under {q["parent"]} at {q["matrix_world"]}, the instance is under {inst["parent"]} at {inst["matrix_world"]}')
        q['parent']=None;q['matrix_world']=IDENTITY
    old[instance]=inst
    out[new_file]={'objects':moved,'direct_links':[]}
    link=[x for x in after[old_file]['direct_links'] if new_file.split('/')[-1] in x]
    out[old_file]['direct_links']=sorted(out[old_file]['direct_links']+link)
    return out


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('before',type=Path);p.add_argument('after',type=Path)
    p.add_argument('--allow-added',nargs='*',default=[]);p.add_argument('--allow-new-files',nargs='*',default=[])
    p.add_argument('--relocate',nargs=4,action='append',default=[],metavar=('PREFIX','OLD_FILE','NEW_FILE','INSTANCE'),
                   help='a detail migration: rewrite the baseline for it (see relocate) before the strict comparison')
    a=p.parse_args()
    before,after=json.loads(a.before.read_text()),json.loads(a.after.read_text())
    for prefix,old_file,new_file,instance in a.relocate:before=relocate(before,after,prefix,old_file,new_file,instance)
    r=compare(before,after,a.allow_added,a.allow_new_files)
    print(json.dumps({k:(v if len(v)<=40 else v[:40]+[f'... {len(v)-40} more']) if isinstance(v,list) else v for k,v in r.items()},indent=1))
    sys.exit(r['result']!='PASS')
