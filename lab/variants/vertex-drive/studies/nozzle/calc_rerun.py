"""Re-run the FDP-1 calculator (read-only, through convergence.solve) for V1 at nozzle efficiencies that T03 derives.
The calculator's nozzle_efficiency is used as an energy share (jet = eta x stream, ve = sqrt(2 eta b eps)), i.e. a thrust efficiency
F^2/(2 mdot P). These runs book the energy-equivalent of published momentum efficiencies. Output: results/calculator_reruns.json."""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
import convergence as CV  # noqa: E402

CASES = [  # (label, thrust efficiency booked, basis)
    ('FDP-1 as booked', 0.79, 'calculator value'),
    ('0.79 read as momentum efficiency', 0.79 ** 2, 'eta_T = eta_mom^2 (monoenergetic, elastic)'),
    ('0.863 read as momentum efficiency', 0.863 ** 2, 'Thio theoretical maximum as momentum'),
    ('0.70 read as momentum efficiency', 0.70 ** 2, 'UAH hemispherical "over 70 %"'),
    ('0.65 read as momentum efficiency', 0.65 ** 2, 'Nagamine & Nakashima 1999 3D hybrid PIC'),
    ('cliff probe 0.55', 0.55, 'between V1 cliff 0.528 and 0.60'),
    ('cliff probe 0.60', 0.60, ''),
]


RATIO = 'base.overrides.pulsed.nozzle_field_energy_ratio.value'
COUPLED = [  # (label, thrust efficiency, stored field energy per J of pulse energy, basis)
    (f'eta_T {e:.3f}, field ratio {k:g}', e, k, b)
    for e, b in ((0.79, 'as booked'), (0.745, 'Thio 0.863 as momentum'), (0.74, 'T03 thin-shell C at W/Ep 10'), (0.70, 'probe'))
    for k in (1.0, 3.0, 10.0, 30.0)
]


PTW = 'base.overrides.continuous.plume_to_hardware.value'


def t03_cases():
    """Coupled cases from the thin-shell results: thrust efficiency, stored-energy ratio and plume-strike share of the nozzle loss of
    each optimised design (results/nozzle_results.json, written by run_nozzle.py)."""
    f = HERE / 'results/nozzle_results.json'
    if not f.exists():
        return []
    d = json.loads(f.read_text())['designs']
    out = []
    for name, rec in d.items():
        if not name.startswith('C_W'):
            continue
        ts = rec['thin_shell']; eta = ts['eta_T']; k = rec['ledger']['W_over_Ep']
        ptw = min(1.0, ts['strike_share'] / max(1 - eta, 1e-9))
        out.append((f'T03 coupled {name}', eta, k, f'thin-shell model upper bound, plume strike {ptw:.3f} of the loss', ptw))
    return out


def main():
    G = CV.generations(); V1 = G['V1']['overrides']
    out = []
    jobs = [(label, eta, None, basis, None) for label, eta, basis in CASES] + [c + (None,) for c in COUPLED] + t03_cases()
    for label, eta, ratio, basis, ptw in jobs:
        t = time.time()
        kv = {CV.ETA: eta}
        if ratio is not None:
            kv[RATIO] = ratio
        if ptw is not None:
            kv[PTW] = ptw
        r = CV.solve(CV.P(V1, **kv))
        s = r['summary']
        out.append({'label': label, 'eta_T_booked': eta, 'field_energy_ratio': ratio if ratio is not None else 1.0, 'plume_to_hardware': ptw if ptw is not None else 0.02, 'basis': basis, 'converged': bool(s.get('converged')),
                    'departure_t': s.get('departure_t'), 'fusion_TW': s.get('fusion_TW'), 'warm_km2': s.get('warm_km2'),
                    'hot_GW': r.get('hot_GW'), 'solid_angle': s.get('solid_angle'), 'drive_t': s.get('drive_t'), 'secs': round(time.time() - t, 1)})
        print(out[-1], flush=True)
    (HERE / 'results/calculator_reruns.json').write_text(json.dumps({'generation': 'V1', 'cases': out}, indent=1))


if __name__ == '__main__':
    main()
