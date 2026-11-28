"""III.3 driver: closed-loop TVC criteria C2-C6 per depletion state for a closure result.   python3 dyn_run.py <closure json> <out json>"""
import sys, json; sys.path.insert(0,'.'); sys.path.insert(0,'../phase2')
import run3, model3 as m3, dyn3
d=json.load(open(sys.argv[1])); hs=run3.hist(3,'wsi')
b=m3.Build3(d['concept'],hs[0]['cfg'],deck=d['deck'],rotor=d['rotor'],guide_ring=d['guide_ring'],mats=d['mats'])
for g,s in d['sections'].items():
    if g in b.sec: b.sec[g].update(s)
b.update_sections(); out=[]
for s in hs:
    r,B=dyn3.evaluate(b,s['cfg']['bodies'],label=f"left {s['left']}")
    imu=b.sp(min(b.spine,key=lambda x:abs(x-40.0)))
    r['ramp']=[dyn3.ramp_down(b,B,imu,t) for t in (2.0,30.0)]
    out.append(r); print(json.dumps(r,default=float)[:1500],flush=True)
json.dump(out,open(sys.argv[2],'w'),indent=1,default=float)
