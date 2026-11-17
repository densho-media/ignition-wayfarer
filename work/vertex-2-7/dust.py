"""Vertex 2.7: what drives the HIGH dust case, a justified environmental envelope, and the survivable mission inside it (research, not canon).

    python3 work/vertex-2-7/dust.py      writes work/vertex-2-7/dust.json and dust.log (needs ../vertex-2-6; about a minute)

Uses the Vertex 2.6 impact model (work/vertex-2-6/protect.py) and its copy of the T02 environment unchanged. New cases are added at run
time only:
  1. one-at-a-time: NOMINAL with exactly one HIGH input (six environment, four damage), so the 44 kt HIGH result is decomposed;
  2. JUSTIFIED: every environment input at the upper end of what a measurement supports (Grun x2, SDC density x3 and Doner 2024 trend,
     Frisch 1999 interstellar mass density, the Landgraf 2000 extrapolation bound for large interstellar grains, Dohnanyi cascade index
     and a 1 ug grain ceiling) with every damage input at its conservative HIGH value, because no impact data exist above ~100 km/s;
  3. STRESS = T02 HIGH: adds the unmeasured inputs (Kuiper-belt grains to 1 g on a flat 0.70 index, the disputed AMOR radar interstellar flux);
  4. route variants of JUSTIFIED: out of the ecliptic, a 1,000 AU destination, and braking attitude from 0.1 to 2 deg.
Every case is an envelope of the literature, not a probability.
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
V26 = ROOT/'work'/'vertex-2-6'
sys.path.insert(0, str(V26))
import protect as PR  # noqa: E402
import t02_environment as E  # noqa: E402

DAY = 86400.0; C = 299792458.0
ENV_HIGH = dict(ipd_scale=2.0, kb_scale=3.0, kb_alpha=0.70, kb_mmax=1e-3, isd_rho=6.2e-24, isd_tail='RADAR')
DMG = ('K_CRATER', 'BUMPER', 'T_OVER_D', 'WALL_KG_M2')
EVIDENCE = {
    'ipd_scale': ('MEASURED-MODEL', 'Grun et al. 1985 interplanetary flux model, stated accuracy about a factor 2; x2 is its own bound'),
    'kb_scale': ('MEASURED', 'New Horizons SDC (Bernardoni 2022; Doner 2024: fluxes above models out to 55-60 AU); x3 covers the excess'),
    'kb_alpha': ('UNMEASURED', 'SDC counts grains above ~0.6 um only; the index above ~10 um is a collisional-cascade assumption '
                               '(Dohnanyi 0.83); a flat 0.70 index has no measurement behind it'),
    'kb_mmax': ('UNMEASURED', 'no detector has sampled Kuiper-belt dust heavier than ~1e-11 kg; a 1 g ceiling is a stress assumption'),
    'isd_rho': ('MEASURED-MODEL', 'interstellar dust mass density 2.1e-24 (Kruger & Strub 2015, Ulysses) to 6.2e-24 kg/m3 '
                                  '(Frisch et al. 1999 from gas depletion); the upper value is literature'),
    'isd_tail': ('DISPUTED', 'EXTRAPOLATED = the Landgraf 2000 upper bound of the in-situ distribution; RADAR = the AMOR hyperbolic-meteor '
                             'flux (Baggaley 2000), which later radar surveys (CMOR, Musci 2012; review Hajdukova 2019) did not confirm'),
    'K_CRATER': ('EXTRAPOLATION', 'cratering coefficient carried from <=70 km/s laboratory data to 4,800 km/s: no data at all; '
                                  'the HIGH value is kept in every justified case'),
    'BUMPER': ('EXTRAPOLATION', 'debris-cloud spread behind a bumper at impact speeds 100x beyond test ranges: kept conservative'),
    'T_OVER_D': ('PROTOTYPE', 'bumper thickness per design-grain diameter: kept conservative'),
    'WALL_KG_M2': ('PROTOTYPE', 'wall behind the bumper: kept conservative'),
}


def add_case(name, env, damage_from='NOMINAL', damage=None):
    """Register a case: environment dict over NOMINAL, damage inputs copied from a T02 case or overridden one by one."""
    E.CASE[name] = dict(E.CASE['NOMINAL'], **env)
    for d in DMG:
        getattr(PR, d)[name] = getattr(PR, d)[damage_from]
    for d, v in (damage or {}).items():
        getattr(PR, d)[name] = v


def protection(case, segs, ext_avail=150.0):
    old = PR.S_AVAIL['stern']['C_EXT']; PR.S_AVAIL['stern']['C_EXT'] = ext_avail
    try:
        p = PR.protection_design('C_EXT', segs, case)
    finally:
        PR.S_AVAIL['stern']['C_EXT'] = old
    blades = [r for r in PR.assess('C_EXT', segs, True, case, 1.0) if r['name'].startswith('thermal blades')][0]
    fl = PR.flips(segs, case)
    return dict(total_t=p['total_t'], faces=[dict(face=f['face'], kind=f['kind'], mass_t=f['mass_t'], standoff_needed_m=f['standoff_needed_m'],
                                                  armour_t_m=f['armour_t_m']) for f in p['faces']],
                brow_standoff_needed_m=p['brow_standoff_needed_m'], brow_upgrade_t=p['brow_upgrade_t'], optics_replacements=p['optics_replacements'],
                blade_punctures_1deg=blades['events_unprotected'],
                flip_blade_punctures=sum(v['radiator_faces']['events'] for v in fl.values()),
                brow=PR.brow(segs, case)['events_beyond_disruptor_2m'])


def attitude(case, segs):
    out = {}
    for a in (0.1, 0.5, 1.0, 1.5, 2.0):
        rows = PR.assess('C_EXT', segs, True, case, a)
        out[f'{a:g}'] = {r['name']: r['events_unprotected'] for r in rows if r['name'].startswith(('thermal blades', 'habitat', 'ring', 'body', 'ship'))}
    return out


def run():
    segs, meta = PR.mission(466.85*DAY, 0.072*C, None)
    segs1000, meta1000 = PR.mission(466.85*DAY, 0.072*C, 1000.0)
    out = dict(meta=dict(title='Vertex 2.7 dust envelope (research, not canon)', path=meta, evidence=EVIDENCE, env_high=ENV_HIGH), cases={})
    # 1. one at a time
    for k, v in ENV_HIGH.items():
        add_case(f'N+{k}', {k: v})
    for d in DMG:
        add_case(f'N+{d}', {}, damage={d: getattr(PR, d)['HIGH']})
    # 2-3. envelopes
    just_env = dict(ipd_scale=2.0, kb_scale=3.0, kb_alpha=0.83, kb_mmax=1e-6, isd_rho=6.2e-24, isd_tail='EXTRAPOLATED')
    add_case('JUSTIFIED', just_env, damage_from='HIGH')
    add_case('JUSTIFIED_ENV_NOMINAL_DAMAGE', just_env, damage_from='NOMINAL')
    add_case('JUSTIFIED+kb_alpha', dict(just_env, kb_alpha=0.70), damage_from='HIGH')
    add_case('JUSTIFIED+kb_mmax', dict(just_env, kb_mmax=1e-3), damage_from='HIGH')
    add_case('JUSTIFIED+radar', dict(just_env, isd_tail='RADAR'), damage_from='HIGH')
    add_case('JUSTIFIED_HILAT', dict(just_env, ipd_scale=2.0*0.3, kb_scale=3.0*0.1), damage_from='HIGH')
    order = ['LOW', 'NOMINAL'] + [f'N+{k}' for k in ENV_HIGH] + [f'N+{d}' for d in DMG] + \
            ['JUSTIFIED_ENV_NOMINAL_DAMAGE', 'JUSTIFIED', 'JUSTIFIED+kb_alpha', 'JUSTIFIED+kb_mmax', 'JUSTIFIED+radar', 'JUSTIFIED_HILAT', 'HIGH']
    for c in order:
        out['cases'][c] = protection(c, segs)
        x = out['cases'][c]
        print(f"{c:30s} protection {x['total_t']:9.0f} t | " + '; '.join(f"{f['face'][:22]} {f['kind']} {f['mass_t']:.0f}" for f in x['faces'])
              + f" | blades@1deg {x['blade_punctures_1deg']:.3g}, flips {x['flip_blade_punctures']:.3g}, optics {x['optics_replacements']:.0f}, Brow beyond 2 m {x['brow']:.3g}",
              flush=True)
    # route: destination 1000 AU, and the stern stand-off the JUSTIFIED case needs for a bumper (spine length)
    out['route'] = {}
    for c in ('NOMINAL', 'JUSTIFIED', 'HIGH'):
        out['route'][f'{c}_dest1000'] = protection(c, segs1000)
        print(f"{c:10s} dest 1000 AU: {out['route'][f'{c}_dest1000']['total_t']:.0f} t", flush=True)
    out['standoff'] = {}
    for c in ('NOMINAL', 'JUSTIFIED', 'HIGH'):
        item = dict(PR.lead_item('stern annulus', math.pi*45.0**2-4*math.pi*11.4358**2))
        S = PR.required_standoff(item, segs, c)
        out['standoff'][c] = S
        for avail in (25.0, 50.0, 100.0, 150.0, 250.0, 400.0):
            out['standoff'][f'{c}_avail{avail:g}'] = protection(c, segs, avail)['total_t']
        print(f"{c:10s} stern annulus bumper needs {S} m; protection by available stand-off: "
              + ', '.join(f"{a:g} m {out['standoff'][f'{c}_avail{a:g}']:.0f} t" for a in (25.0, 50.0, 100.0, 150.0, 250.0, 400.0)), flush=True)
    out['attitude'] = {c: attitude(c, segs) for c in ('NOMINAL', 'JUSTIFIED', 'HIGH')}
    for c, a in out['attitude'].items():
        print(c, {k: {n[:14]: round(v, 3) for n, v in d.items()} for k, d in a.items()})
    return out


if __name__ == '__main__':
    o = run()
    (HERE/'dust.json').write_text(json.dumps(o, indent=1, default=str)+'\n')
