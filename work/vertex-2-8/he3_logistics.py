"""Vertex 2.8 (D3): can the He-3 beyond the canon 1,094 t load be supplied inside IGNITION's established industry? (research, not canon)

    python3 work/vertex-2-8/he3_logistics.py     writes work/vertex-2-8/he3_logistics.json and prints a table (standard library, instant)

The fuel is still carried aboard; this only sizes the supply chain behind the tanks. Drive context read 2026-11-17 (main conversation):
- Technology 43_SPACE_MANUFACTURING ISM-29..32: Luna Lift, Luna Harbor -> Luna Yard cargo chain and the Luna Yard fabrication lattice are
  ESTABLISHED at Y155 (numerics OPEN); ISM-07 regolith processing is ground research in 2026; ISM-16/21: no arbitrary matter replication.
- Technology 40_ENERGY_PROPULSION: fusion "remains difficult engineering" (Non-Fiji Fusion workbook owns it); no He-3 supply row.
- Economy & Currency 30_SCARCITY_VALUE / 42_SPACE_ECONOMY: energy, mass and delta-v stay scarce; no He-3 market or mining row exists.
So no canon He-3 source exists today; three physical routes are sized here with literature ranges (all LITERATURE secondary, ranges kept).
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
MEV = 1.602176634e-13; NA = 6.02214076e23; YR = 3.15576e7
M_HE3 = 3.016e-3           # kg/mol

CANON_T = 1094.0
CASES = {'canon load': 1094.0, '2.7 levers (+338 t)': 1432.0, '2.7 point in JUSTIFIED': 2113.0}


def lunar(t, ppb, recovery=0.8, depth_m=3.0, bulk_t_m3=1.5, cp_kJ_kgK=0.8, dT=700.0, heat_recovery=0.0):
    """Mare regolith: He-3 by mass at `ppb` (Apollo/remote-sensing estimates 1-20 ppb, Ti-rich mare highest; Fa & Jin 2007, Johnson et al.
    1999), released by heating to ~700 C (75-85 % recovery, Wisconsin FTI studies)."""
    reg_t = t/(ppb*1e-9*recovery)
    area_km2 = reg_t/(depth_m*bulk_t_m3*1e6)
    heat_J = reg_t*1e3*cp_kJ_kgK*1e3*dT*(1-heat_recovery)
    return dict(regolith_t=reg_t, area_km2=area_km2, heating_J=heat_J)


def fusion_energy(t):
    """D-3He fusion energy of t tonnes of He-3 (18.35 MeV per reaction)."""
    return t*1e3/M_HE3*NA*18.35*MEV


def dd_breeding(t):
    """He-3 bred by D-D fusion: each D-D reaction yields one He-3 (50 % branch) or one T that decays to He-3 (t1/2 12.32 yr), so about one
    reaction per He-3; mean 3.65 MeV released per reaction, half the reactions emit a 2.45 MeV neutron."""
    n = t*1e3/M_HE3*NA
    return dict(dd_energy_J=n*3.65*MEV, TW_years=n*3.65*MEV/YR/1e12, tritium_t=0.5*n*3.016e-3/NA/1e3,
                years_to_90pct_T_decay=12.32*3.3219)


def run():
    out = dict(meta=dict(note=__doc__.strip().splitlines()[0], canon_t=CANON_T), cases={})
    print(f"{'case':28s} {'He-3 t':>7s} | lunar 5 ppb: regolith t, km2 | 15 ppb: regolith t, km2 | heat/fusion (15 ppb) | D-D TW-yr")
    for k, t in CASES.items():
        lo = lunar(t, 5.0); hi = lunar(t, 15.0); ef = fusion_energy(t); dd = dd_breeding(t)
        out['cases'][k] = dict(he3_t=t, over_canon_t=t-CANON_T, lunar_5ppb=lo, lunar_15ppb=hi, fusion_J=ef, dd=dd,
                               heat_over_fusion_15ppb=hi['heating_J']/ef)
        print(f"{k:28s} {t:7.0f} | {lo['regolith_t']:.2e} {lo['area_km2']:8.0f} | {hi['regolith_t']:.2e} {hi['area_km2']:8.0f} | "
              f"{hi['heating_J']/ef:6.3f} | {dd['TW_years']:5.2f}")
    inc = 338.0
    out['increment'] = dict(he3_t=inc, lunar_15ppb=lunar(inc, 15.0), dd=dd_breeding(inc),
                            share_of_canon=inc/CANON_T,
                            reading='The increment is +31 % of a supply chain that already has to exist for the canon 1,094 t: the base, not the '
                                    'increment, is the logistics problem. Lunar strip-mining of order 10^10-10^11 t regolith (thousands to tens of '
                                    'thousands of km^2) over decades, or a ~1-2 TW-year D-D fusion economy with decades of tritium decay, or '
                                    'gas-giant atmosphere extraction (outside the Y155 canon read here). None is canon; all are OWNER/Economy '
                                    'decisions. Engineering does not depend on the answer: the ship carries the fuel.')
    print('increment 338 t:', {k: (f'{v:.3g}' if isinstance(v, float) else v) for k, v in out['increment']['lunar_15ppb'].items()},
          f"D-D {out['increment']['dd']['TW_years']:.2f} TW-yr")
    return out


if __name__ == '__main__':
    o = run()
    (HERE/'he3_logistics.json').write_text(json.dumps(o, indent=1)+'\n')
