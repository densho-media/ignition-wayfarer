"""3D integration live mass ledger (Track F1). Starts from the Phase VI F1 nominal items (i3d_masterplan.json), adds every stage's
`ledger_add` rows (i3d_*.json), and re-solves propellant and tankage with mass_model.coupled_mission (the Phase V/VI coupling). Items that wait
for an owner decision are listed with their effect but not added. Writes ../results/i3d_ledger.json. Pure Python.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent; W = HERE.parent; ROOT = W.parents[1]; R = W/'results'
sys.path.insert(0, str(ROOT/'src/wayfarer'))
import spec  # noqa: E402
import mass_model as mm  # noqa: E402

CIRC = 40.2e3
STAGES = [('i3d_radiators.json', 'E'), ('i3d_electrical.json', 'F'), ('i3d_eclss.json', 'G'), ('i3d_logistics.json', 'H'), ('i3d_remaining.json', 'I')]


def pending():
    out = []
    f = R/'i3d_radiators.json'
    if f.exists():
        d = json.loads(f.read_text())
        out.append(dict(id='DR-3D-04', item='HOT forward-pointing fins (double manifolds)', t=d['hot_fins']['manifold_walls_extra_t']))
        out.append(dict(id='DR-3D-03', item='L2 sections aft beside the district (transport run ~20 m)', t=-d['nak']['transport']['mass_t_per_loop']*3*(1-20/d['nak']['run_m'])))
    for fn in ('i3d_logistics.json', 'i3d_remaining.json'):
        f = R/fn
        if f.exists(): out += json.loads(f.read_text()).get('pending', [])
    return out


def main():
    s = spec.load()[0]; M = json.loads((R/'i3d_masterplan.json').read_text())['ledger']
    rows = [dict(item=r['item'], t=r['t'], cls=r['cls'], stage='Phase VI') for r in M['items']]
    for fn, st in STAGES:
        f = R/fn
        if f.exists():
            for r in json.loads(f.read_text()).get('ledger_add', []):
                rows.append(dict(item=r['item'], t=r['t'], cls=r['cls'], stage=st))
    dry = sum(r['t'] for r in rows); m = mm.coupled_mission(s, CIRC+dry*1e3)
    base = M['departure_t']; per_t = (m['departure_mass_kg']/1e3-base)/max(1e-9, dry-M['dry_added_t'])
    P = pending()
    for p in P: p['departure_t'] = p['t']*per_t
    out = dict(config=M['config'], items=rows, dry_added_t=dry, departure_t=m['departure_mass_kg']/1e3, propellant_t=m['propellant_kg']/1e3,
               tankage_t=m['added_tank_kg']/1e3, end_t=m['end_mass_kg']/1e3, phase6_departure_t=base, change_t=m['departure_mass_kg']/1e3-base,
               coupling_t_per_t=per_t, pending=P,
               note='nominal case; H6a kept at the Phase VI line (the shorter hot length lowers it slightly); pending items wait for owner decisions')
    (R/'i3d_ledger.json').write_text(json.dumps(out, indent=1))
    print(f'dry {dry:.1f} t, departure {out["departure_t"]:.0f} t ({out["change_t"]:+.0f} t vs Phase VI), coupling {per_t:.2f} t/t')
    for p in P: print(' pending', p['id'], f'{p["t"]:+.1f} t dry, {p["departure_t"]:+.0f} t departure')


if __name__ == '__main__':
    main()
