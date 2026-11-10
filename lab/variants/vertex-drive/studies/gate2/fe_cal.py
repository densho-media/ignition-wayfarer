"""Gate 2: beam-model f1 of T05's Gate 2 FE sections, for the FE/beam knockdown (T00, research only, NON-CANON).

  python3 lab/variants/vertex-drive/studies/gate2/fe_cal.py     # writes results/fe_cal.json (seconds)

Same loads as T05's gate2_fe.py: lam 2.73 stretch propellant (68.5 kt) and 6.5 kt tanks (V4 bays scaled), N9 tube r 0.611 m, t/r 0.1,
ring 31 R/34.5 m, bow 300 t; free-free with the aft ship (35.9 kt) lumped at J1 (point mass: no rotary inertia, unlike T05).
"""
import copy

import g2
import spine as SP

LAM = 2.73
T05_FE = {'34.5x275': (0.165, 0.118), '41.7x514': (0.084, 0.053), '44x462': (0.096, 0.061), '34.5x751': (0.049, 0.028)}


def section(d0, Rf, length):
    a = (Rf / 34.5) ** 2
    d = copy.deepcopy(d0); st = d['stretch']; bays = st['bay_masses']; pitch = st['bay_pitch_m']
    full = max(b['propellant_kg'] for b in bays); tk = max(b['tank_kg'] for b in bays)
    total = LAM * sum(b['propellant_kg'] for b in bays) if Rf > 34.6 or length > 300 else sum(b['propellant_kg'] for b in bays)
    tank_total = 6.5e6 if total > 1.1 * sum(b['propellant_kg'] for b in bays) else sum(b['tank_kg'] for b in bays)
    n = max(len(bays), round(length / pitch))
    per = total / n
    new = [dict(bays[0], x_m=bays[0]['x_m'] + pitch * i, propellant_kg=per, tank_kg=tank_total / n) for i in range(n)]
    st['bay_masses'] = new; st['x_m'] = [st['x_m'][0], st['x_m'][0] + length]
    for q in d['loads']['root_axial_by_burn']:
        q['ship_kg'] = sum(b['propellant_kg'] + b['tank_kg'] for b in new) + 300e3 + 35.9e6
    SP.GEOMS['_c'] = (9, 31.0 * Rf / 34.5, 0.611)
    try:
        r = SP.analyse(d, '_c', 300e3, aft_kg=35.9e6)
    finally:
        del SP.GEOMS['_c']
    return r


def main():
    d0 = SP.t05(); out = {}
    for key, Rf, L in (('34.5x275', 34.5, 275.4), ('41.7x514', 41.7, 514.0), ('44x462', 44.0, 462.0), ('34.5x751', 34.5, 751.0)):
        r = section(d0, Rf, L)
        fe_ff, fe_c = T05_FE[key]
        out[key] = {'beam_cantilever_Hz': r['f_cantilever_Hz'][0], 'beam_free_free_Hz': r['f1_Hz'], 'T05_FE_free_free_Hz': fe_ff,
                    'T05_FE_cantilever_Hz': fe_c, 'FE_over_beam_cantilever': fe_c / r['f_cantilever_Hz'][0], 'FE_ff_over_beam_ff': fe_ff / r['f1_Hz']}
        print(key, {k: round(x, 3) for k, x in out[key].items()})
    g2.write('fe_cal.json', out)


if __name__ == '__main__':
    main()
