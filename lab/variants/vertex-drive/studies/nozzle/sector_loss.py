"""T02 request: nozzle performance with one loop sector lost (dust strike or quench, sector at zero current), on the C design at
10 E_p and the A* design at 10 E_p. First-order thin-shell perturbation (perturb.surface_effect); a lost 85 deg sector is a large
perturbation, so the numbers are indicative (MODEL, beyond first order near that sector). Lateral momentum share x thrust gives the
side force; its moment about the ship centre of mass is left to T00/T05 (the lever arm is the burn-point distance to the CoM).
Run from the repo root after run_nozzle.py: python3 lab/variants/vertex-drive/studies/nozzle/sector_loss.py  (about 2 min)."""
import json
import sys
import warnings
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import configs as C   # noqa: E402
import perturb as PT  # noqa: E402
import pulse          # noqa: E402
import shell          # noqa: E402

warnings.filterwarnings('ignore')


def main():
    p = pulse.v1(); Ep = p['E_plasma_J']
    res = json.loads((HERE / 'results/nozzle_results.json').read_text())
    out = {}
    for name in ('C_W10', 'Astar_W10'):
        rec = res['designs'][name]
        geom = [{'name': l['name'], 'alpha_deg': l['polar_deg'], 'd': l['distance_m'], 'R': l['radius_m'], 'z': l['z_m']} for l in rec['loops']]
        L = C.with_currents(geom, [l['current_MA'] * 1e6 for l in rec['loops']])
        hw = shell.hardware_set(p, 0.5) + [{'kind': 'loop', 'name': q['name'], 'R': q['R'], 'z': q['z'], 'tube': 0.5}
                                           for q in L if not q['name'].startswith('L')]
        T = shell.WorkTable(L, n_th=121, n_rho=600); o = shell.reflect(T, 1.0, Ep, hw)
        base = PT.surface_effect(p, L, T, o['R'], [], Ep, n_phi=72, hardware=hw, base=o)
        rows = {'intact': base}
        for q in L:
            r = PT.surface_effect(p, L, T, o['R'], PT.lost_sector_paths(q, 0), Ep, n_phi=72, hardware=hw, base=o)
            r['side_force_N'] = r['lateral_momentum_share'] * p['thrust_N'] / max(base['eta_mom_total'], 1e-9)
            rows[f'{q["name"]} one sector lost'] = r
            print(name, q['name'], f"eta {r['eta_mom_total']:.3f} (intact {base['eta_mom_total']:.3f}) strike {r['strike_share']:.4f} "
                  f"lateral {r['lateral_momentum_share']:.4f} side force {r['side_force_N']/1e3:.1f} kN", flush=True)
        out[name] = rows
    (HERE / 'results/sector_loss.json').write_text(json.dumps(out, indent=1, default=float))


if __name__ == '__main__':
    main()
