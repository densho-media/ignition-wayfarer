"""WSI shared helpers: paths, the ISSA consolidation functions, the PSA models, and the mission operating point.

Everything here is STUDY / PROTOTYPE, Track F (fiction) unless a value says RESEARCH. Production geometry, data/ and canon are read only.
The ISSA functions (work/ship-systems-architecture/integration3d/consolidate.py) and the PSA models
(work/primary-structural-architecture/phase2, phase3) are imported, never copied, so one definition serves both workstreams.
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
W = HERE.parent
ROOT = W.parents[1]
R = W/'results'
ISSA = ROOT/'work/ship-systems-architecture'
PSA = ROOT/'work/primary-structural-architecture'
for p in (ROOT/'src/wayfarer', ISSA/'integration3d', PSA/'phase2', PSA/'phase3'):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import spec  # noqa: E402
import mass_model as mm  # noqa: E402
import consolidate as cs  # noqa: E402

G0 = 9.80665
THRUST_N = cs.F1_THRUST_N                    # 21.77 MN, the power-limited F1 drive (Phase VI a_g x end mass); PSA uses the same value
CIRC_KG = cs.CIRC
STRUCT_LINE_T = 150.0                        # production main_structure line, inside the protected mass; PSA structure replaces it
REFS = dict(issa='8b30b71', psa_phase2='c3138d8', psa_phase3='1beb693', main='11f1e94')


def J(path):
    return json.loads(Path(path).read_text())


_S = None


def S():
    global _S
    if _S is None:
        _S = spec.load()[0]
    return _S


def issa_c11():
    return J(ISSA/'results/i3d_consolidated.json'), J(ISSA/'results/i3d_structure_interface.json')


def psa_p2():
    return J(PSA/'results/p2_ledger.json')


def mission(extra_end_t):
    """The coupled mission operating point (four burns, 0.016 c, power-limited) with extra_end_t over the production protected mass."""
    m = mm.coupled_mission(S(), extra_end_t*1e3)
    return dict(departure_t=m['departure_mass_kg']/1e3, propellant_t=m['propellant_kg']/1e3, tankage_t=m['added_tank_kg']/1e3, end_t=m['end_mass_kg']/1e3,
                mass_ratio_per_burn=m['mass_ratio_per_burn'], burns=m['burns'])


def issa_point(structure_delta_t=0.0, iters=30, tank_fn=None):
    """ISSA C1.1 rebuilt with consolidate.py: tanks -> cryo -> radiators -> ledger, iterated to a fixed point, plus an extra structure
    mass over the 150 t line. Returns the converged pieces and the iteration history."""
    s = S(); E6 = cs.P6['reconciliation']['electrical']; hp = E6['heat_pump']
    react0 = E6['sum_R']['continuous_reactive_W']-hp['proactive_W']
    prop = cs.LD['propellant_t']; hist = []
    tank_fn = tank_fn or cs.tanks
    for k in range(iters):
        T = tank_fn(s, prop); C = cs.cryo(s, T['shell_area_m2']); RAD = cs.radiators(C, react0); MR = cs.mru(s); cs.finalize_cryo(C, RAD['preferred'])
        L = cs.ledger(s, RAD, MR, C, T['carried_t'], structure_delta_t)
        hist.append(dict(it=k+1, propellant_t=L['propellant_t'], departure_t=L['departure_t'], farm_m=T['added_length_m']))
        if abs(L['propellant_t']-prop) < 0.05:
            break
        prop = L['propellant_t']
    return dict(T=T, C=C, RAD=RAD, MR=MR, L=L, history=hist)
