"""Vertex 2.9 mission ledger on the reduced-hybrid B2d bounds (research, not canon).

    python3 work/vertex-2-9/mission29.py       writes work/vertex-2-9/mission29.json and mission29.log (needs scan_conv.json)

Each hybrid run's (kappa, forward energy on the ship) pair replaces the 2.8 credited cosine and the restated SR-26F forward share
(f_tail 0 here: the run's own forward stream is used, f_fwd = forward_on_ship). Every case carries the 5 % delta-v reserve (Q3) unless
named 'noreserve'. Same JUSTIFIED dust, 200 m spine, lever set (b 0.99, charge spread, SR-26A x0.01) and +0.6 yr trip as 2.8.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent/'vertex-2-8'))
import mission28 as LG  # noqa: E402

MI = LG.MI


def main():
    s, S, Sx, vbc, lk, noz = MI.setup()
    LG.dust_justified(200.0)
    nzj = json.loads((HERE.parent/'vertex-2-8'/'nozzle.json').read_text())
    ref = {r['key']: r for r in nzj['rows']}['B2d']
    res_ = Sx_r = dict(Sx, dv=Sx['dv']*1.05)
    out = dict(cases={})

    def go(name, kappa, fwd, Sxx=Sx_r, dump=False):
        row = dict(ref, forward_credit_tp=0.0, forward_coll=fwd)
        r = LG.case(Sxx, s, vbc, lk, row, f_tail=0.0, kappa=kappa, dump=dump); r['inputs']['f_fwd'] = fwd
        out['cases'][name] = r
        print(f"{name:34s} {LG.short(r)}", flush=True)
        return r
    go('2.8_reference_reserve', ref['kappa_credit'], 0.01*ref['test_particle']['forward_on_ship'])
    runs = {}
    for f in ('scan_conv.json', 'scan_all2.json'):
        p = HERE/f
        if p.exists():
            runs.update(json.loads(p.read_text()))
    for name, r in runs.items():
        if not name.startswith('B2d') or 'lowbeta' in name:
            continue
        go(f'hyb_{name}', r['kappa'], r['forward_on_ship'])
    # envelope: the spread of the converged-in-nothing cutoff family, then the requirement corner
    ks = [r['kappa'] for n, r in runs.items() if n.startswith('B2d_nc')]
    fs = [r['forward_on_ship'] for n, r in runs.items() if n.startswith('B2d_nc')]
    go('envelope_best', max(ks), min(fs)); go('envelope_worst', min(ks), max(fs))
    go('best_kappa_noreserve', max(ks), min(fs), Sxx=Sx)
    # loss-corrected pairs: rescale each run to the energy it actually delivered to space (kappa / sqrt(E_space), forward / E_space),
    # i.e. assume the numerically lost energy would have left with the same angular distribution (optimistic for the cosine)
    for name in ('B2d_nc3e16', 'B2d_nc1e17', 'B2d_nc1e18'):
        if name in runs:
            r = runs[name]; Es = sum(r['fractions'][k] for k in ('AFT', 'FORWARD', 'RADIAL'))
            go(f'losscorr_{name}', min(r['kappa']/Es**0.5, 0.999), r['forward_on_ship']/Es)
    # engineering alternative for the forward stream: the 2.8 forward beam dump (C/C face at 1800 K) on the hybrid pairs
    for name in ('B2d_nc1e17', 'B2d_nc1e18', 'B2d_burn_z11_nc1e18', 'B2d_comp_b0.99'):
        if name in runs:
            go(f'dump_{name}', runs[name]['kappa'], runs[name]['forward_on_ship'], dump=True)
    for k in (0.80, 0.85, 0.906):
        for fw in (1e-4, 2.9e-4, 1e-3, 3e-3):
            go(f'grid_k{k}_fwd{fw:g}', k, fw)
    return out


if __name__ == '__main__':
    import contextlib, io
    buf = io.StringIO()

    class Tee(io.TextIOBase):
        def write(self, s):
            sys.__stdout__.write(s); buf.write(s); return len(s)
    with contextlib.redirect_stdout(Tee()):
        o = main()
    (HERE/'mission29.json').write_text(json.dumps(o, indent=1, default=float)+'\n')
    (HERE/'mission29.log').write_text(buf.getvalue())
