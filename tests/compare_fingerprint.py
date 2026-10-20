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


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('before',type=Path);p.add_argument('after',type=Path)
    p.add_argument('--allow-added',nargs='*',default=[]);p.add_argument('--allow-new-files',nargs='*',default=[])
    a=p.parse_args()
    r=compare(json.loads(a.before.read_text()),json.loads(a.after.read_text()),a.allow_added,a.allow_new_files)
    print(json.dumps({k:(v if len(v)<=40 else v[:40]+[f'... {len(v)-40} more']) if isinstance(v,list) else v for k,v in r.items()},indent=1))
    sys.exit(r['result']!='PASS')
