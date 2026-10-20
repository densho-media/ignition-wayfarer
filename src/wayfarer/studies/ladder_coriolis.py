"""MEC-RINGB-2026-10-10 (15!A118, 98!A86): ring-ladder ergonomics with the shared ring A/B layout kept. The owner asks for push/pull at
realistic climb and rescue speeds, suited load and carried equipment, both ring directions and aft-down 1.5 g, because the 0.016 g example
(human_entry.ladder_push at 0.5 m/s) is not a certification.

For each tube rotor and each spin sense (as built, and reversed), at each speed along the ladder run: the across-ladder acceleration
(spin lean toward the ladder wall and the Coriolis push 2 omega v), whether it presses the climber onto the rungs or pulls them off, and the
force the hands and the arrest link must hold for each load case. A fall from rest at the top of the run is integrated in the ring frame
(centrifugal and Coriolis, no friction) until the body's envelope reaches the tube wall: time, travel and speed at contact, the case the
fall-arrest rail exists for. At 1.5 g aft-down the rings are stopped and locked: the trunk ladder is vertical and the tube runs horizontal.
Every mass is PROTOTYPE (no owner value); the result is DIAGNOSTIC, not a qualification. Pure standard library.

    python3 src/wayfarer/studies/ladder_coriolis.py
"""
from pathlib import Path
import json
import math
import sys
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer')]
from spec import load
import habitat_ring
import human_entry as he

TORSO_HALF_M = 0.20                             # PROTOTYPE torso half depth
SPEEDS_M_S = (0.3, 0.5, 0.8, 1.0)             # PROTOTYPE climb / descent speeds along the run (0.5 m/s is the review speed)
LOADS_KG = {                                    # PROTOTYPE masses moving on the ladder
    'shirt-sleeve crew': 80.0,
    'IVA-suited crew': 95.0,
    'suited crew + 20 kg equipment': 115.0,
    'rescuer lowering a casualty on a line (rescuer, patient, carrier)': 80.0+80.0+15.0,
}


def fall(s, j, sense):
    """Free fall from rest at the run top, the body hugging the ladder (spoke_body_offset_m off the tube axis toward the ladder wall):
    integrate the ring-frame motion in the ring plane (x radial out along the run, y across it, + toward the ladder wall),
    a = w^2 r - 2 w x v, until the torso (TORSO_HALF_M) reaches either side wall of the tube or the body the tube tip."""
    w = habitat_ring.omega(s); lp = he.ladder_push(s, j); r0 = lp['radius_m']['run_top']
    off = s['human_entry']['mannequin']['spoke_body_offset_m']; rc = he.landing(s)['clear_r']
    # Moving out, the Coriolis push is antispinward: toward the ladder wall where that wall is antispinward (k = +1), else away from it.
    k = 1 if (lp['ladder_wall'] == 'antispinward') == (sense == 1) else -1
    x, y, vx, vy, t, dt = r0, 0.0, 0.0, 0.0, 0.0, 1e-3                  # y from the start, + toward the ladder wall
    while t < 30.0:
        ax = w*w*x-2*k*w*vy; ay = 2*k*w*vx+lp['lean_toward_ladder_g']*habitat_ring.G0   # the lean w^2 z, constant over this small offset
        vx += ax*dt; vy += ay*dt; x += vx*dt; y += vy*dt; t += dt
        if y >= rc-off-TORSO_HALF_M or -y >= rc+off-TORSO_HALF_M or x >= lp['radius_m']['tube_tip']:
            break
    side = 'the ladder wall' if y > 0 and abs(y) >= rc-off-TORSO_HALF_M-1e-6 else ('the open wall' if y < 0 else 'the tube tip')
    return dict(time_s=round(t, 2), radial_travel_m=round(x-r0, 3), across_travel_m=round(y, 3), speed_m_s=round(math.hypot(vx, vy), 2),
                radial_speed_m_s=round(vx, 2), hits=side)


def study(s):
    g = habitat_ring.G0; w = habitat_ring.omega(s); out = {}
    for j in s['human_entry']['tube_rotors']:
        lp = he.ladder_push(s, j); lean = lp['lean_toward_ladder_g']; rows = []
        for sense, label in ((1, 'as built'), (-1, 'reversed')):
            built_off = lp['pulled_off_when']; off = built_off if sense == 1 else ('climbing' if built_off == 'descending' else 'descending')
            for v in SPEEDS_M_S:
                cor = 2*w*v/g
                for direction in ('climbing', 'descending'):
                    a = (lean-cor) if direction == off else (lean+cor)      # + presses toward the ladder wall, - pulls off it
                    rows.append(dict(spin=label, speed_m_s=v, direction=direction, across_g=round(a, 4),
                                     effect='pressed onto the rungs' if a > 0 else 'pulled off the rungs',
                                     force_N={k: round(m*a*g, 1) for k, m in LOADS_KG.items()}))
            out_fall = fall(s, j, sense)
            rows.append(dict(spin=label, fall_from_run_top=out_fall))
        out['AB'[j-1]] = dict(ladder_wall=lp['ladder_wall'], built_pulled_off_when=lp['pulled_off_when'], neutral_speed_m_s=round(lp['neutral_speed_m_s'], 3),
                             spin_gravity_g=lp['spin_gravity_g'], unobstructed_fall_speed_m_s=round(lp['fall_speed_m_s'], 2), cases=rows)
    out['aft_down_1_5g'] = dict(note='rings stopped and locked (MEC-011, 08!A47): the trunk ladder is vertical and carries the full weight; the '
                                     'tube runs lie horizontal (a crawl along the tube floor) and the sector hatch ladders become walls',
                                static_load_N={k: round(m*1.5*g, 1) for k, m in LOADS_KG.items()},
                                trunk_fall_1m_speed_m_s=round(math.sqrt(2*1.5*g*1.0), 2))
    return out


if __name__ == '__main__':
    print(json.dumps(study(load(ROOT)[0]), indent=1))
