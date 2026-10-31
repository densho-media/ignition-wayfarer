"""D03 (pass 6, 2026-10-31, Claude under the owner's delegation): SP-13's independent second exit, a pressure-architecture decision.

The 2026-10-16 gallery study (owner 2026-10-17: preferred L2 topology, 15!A199) gave SP-13 a 1.20 m gallery to the stationary refuge outside
the shared trunk (az 125 deg, r 3.8 m; suited crew, litter and kit PASS, suited casualty MARGINAL +0.021 m). This study compares the two
closures the owner named for its refuge end and picks one:
  A  one shielded, stepped/offset, positively dogged closure in the refuge wall;
  B  an isolation antechamber: two pressure-seated plugs in series inside the refuge's water envelope, seating in opposite directions.
It sizes what the choice needs (closure loads at 80 kPa both ways, equalisation time, antechamber volume and mass) and runs the single
faults. Every value is PROTOTYPE; 80 kPa both ways is an analysis input, not a door rating.

    python3 work/project-thread-1ysr1f/d03_sp13_exit.py      # prints the comparison, writes d03_sp13_exit.json beside it
"""
import json
import math
from pathlib import Path

P = 80e3                     # Pa, both polarities (analysis input)
CLEAR_D = 1.20               # m, gallery and closure clear diameter (2026-10-16 study)
SEAL_D = 1.30                # m, seal line (clear + 2 x 0.05 m land)
GALLERY_L = 9.0              # m, SP-13 aft wall (X 104.95) to the refuge (X 96.95) with its two bends (study length class)
ANTE_L = 2.6                 # m, holds a 2.2 m litter + 0.4 m for the leaf swing-in (bearers outside the chamber, one each side)
DOGS = 8
VALVE_D = 0.025              # m, equalisation valve bore, operable from both sides of each leaf
SHELL_KG_M2 = 20.0           # eva_suit.toml shell_kg_m2 (SERV-002 survey value)
LEAF_KG = 140.0              # per 1.2 m dogged plug with frame (PROTOTYPE; ISS hatches ~1.0 m class are ~80-100 kg)
SP13_M3, SP12_M3, REFUGE_M3 = 25.7, 49.1, 55.0
REFUGE_G_CM2 = 20.0          # refuge water areal density (shielding.refuge)
T, R, GAMMA, CD = 293.0, 287.0, 1.4, 0.6


def choked_mdot(p0, d):
    a = math.pi*d*d/4
    return CD*a*p0*math.sqrt(GAMMA/(R*T))*(2/(GAMMA+1))**((GAMMA+1)/(2*(GAMMA-1)))


def equalise_s(volume, p_hi, d, steps=4000):
    """Fill volume from vacuum toward p_hi through one valve (choked until 0.528 p_hi, then subsonic, integrated)."""
    p, t, dt = 0.0, 0.0, 0.05
    while p < 0.99*p_hi and t < 3600:
        if p < 0.528*p_hi:
            m = choked_mdot(p_hi, d)
        else:
            r = p/p_hi; a = math.pi*d*d/4
            m = CD*a*p_hi*math.sqrt(2*GAMMA/((GAMMA-1)*R*T)*(r**(2/GAMMA)-r**((GAMMA+1)/GAMMA)))
        p += m*R*T/volume*dt; t += dt
    return t


def main():
    F = P*math.pi*SEAL_D**2/4
    gallery_v = math.pi*(CLEAR_D/2+0.05)**2*GALLERY_L; ante_v = math.pi*(CLEAR_D/2+0.10)**2*ANTE_L
    ante_area = math.pi*(CLEAR_D+0.20)*ANTE_L
    closures = dict(seal_force_N=F, dog_load_N=F/DOGS,
                    A=dict(leaf='one hinged dogged leaf, stepped/offset frame', pressure_seated='one polarity only; the other on 8 dogs',
                           leaves=1, extra_kg=LEAF_KG),
                    B=dict(leaf='two plugs in series seating in opposite directions', pressure_seated='both polarities by pressure (one leaf each); dogs only for the open-direction hold',
                           leaves=2, extra_kg=2*LEAF_KG+ante_area*SHELL_KG_M2, antechamber_m3=ante_v, antechamber_shell_m2=ante_area))
    eq = dict(antechamber_from_vacuum_s=equalise_s(ante_v, P, VALVE_D), gallery_from_vacuum_s=equalise_s(gallery_v, P, VALVE_D),
              sp13_from_vacuum_s=equalise_s(SP13_M3, P, VALVE_D))
    # single faults: does SP-13 keep a usable exit, is the refuge kept isolated, is the storm shielding kept?
    faults = [
        ('SP-12 / trunk exit jammed (-0.373 m, D04)', dict(A=('gallery', True, True), B=('gallery', True, True))),
        ('gallery refuge closure jammed shut', dict(A=('trunk', True, True), B=('trunk', True, True))),
        ('one antechamber leaf jammed open', dict(A=('n/a', None, None), B=('gallery and trunk', True, True))),
        ('SP-13 depressurised (suits on), refuge at pressure', dict(A=('trunk only: opening the refuge leaf would vent the refuge into the gallery', False, True),
                                                                    B=('gallery: cycle the antechamber, refuge never open to vacuum', True, True))),
        ('fire / toxic release in SP-13, crew escaping to the refuge', dict(A=('gallery, but smoke enters the refuge while the leaf is open', False, True),
                                                                           B=('gallery: the outer leaf closes behind them before the inner opens', True, True))),
        ('storm (SPE) warning during egress', dict(A=('gallery; an open leaf is a gap in the 20 g/cm2 wall while it stands open', True, False),
                                                   B=('gallery; one leaf and the antechamber water jacket stay closed', True, True))),
    ]
    rows = [dict(fault=f, **{k: dict(exit=v[0], refuge_isolated=v[1], shielding_kept=v[2]) for k, v in o.items()}) for f, o in faults]
    app = {k: [r for r in rows if r[k]['refuge_isolated'] is not None] for k in ('A', 'B')}
    score = {k: f"{sum(1 for r in app[k] if r[k]['refuge_isolated'] and r[k]['shielding_kept'])} of {len(app[k])}" for k in ('A', 'B')}
    out = dict(task='D03 SP-13 second exit', date='2026-10-31', status='STUDY (L2 topology; decision under the owner\'s delegation, PROTOTYPE values)',
               inputs=dict(pressure_Pa=P, clear_d_m=CLEAR_D, seal_d_m=SEAL_D, gallery_length_m=GALLERY_L, antechamber_length_m=ANTE_L,
                           volumes_m3=dict(SP13=SP13_M3, SP12=SP12_M3, refuge=REFUGE_M3, gallery=gallery_v)),
               closures=closures, equalisation=eq, faults=rows, faults_clean=score,
               decision=('B: isolation antechamber at the refuge end of the gallery. Both closures are pressure-seated in opposite directions, '
                         'so 80 kPa either way seats a leaf instead of loading dogs; each leaf has an equalisation valve and manual override '
                         'operable from both sides. It keeps the refuge sealed and its shielding closed in every studied single fault, at '
                         f"{closures['B']['extra_kg']:.0f} kg against {closures['A']['extra_kg']:.0f} kg; a jam of either leaf still leaves the trunk exit."),
               rules_1_5g='At locked 1.5 g the 9 m gallery is a shaft: ladder with protected fall arrest; a casualty is cared for in place '
                          '(15!A197) and moves only after thrust reduction, by hoist-only carrier.',
               open=['suited casualty clearance MARGINAL +0.021 m in the 1.20 m bore (keep the bore, no smaller fittings)',
                     'leaf and dog ratings, seals and the antechamber water jacket stack (pressure flight HOLD)',
                     'gallery routing past survival reserve 1 (az 78-138 deg) to be re-swept when built'])
    Path(__file__).with_name('d03_sp13_exit.json').write_text(json.dumps(out, indent=1)+'\n')
    print(json.dumps(dict(closures=closures, equalisation=eq, faults_clean=score, decision=out['decision']), indent=1, default=lambda x: round(x, 2)))


main()
