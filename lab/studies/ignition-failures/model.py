"""Ignition failures: what breaks when the drawn Vertex cluster is switched on at the mission point (study, DIAGNOSTIC, not canon).

  python3 lab/studies/ignition-failures/model.py          # writes results/ignition.json (about 15 s: the engine part meshes)

Pure standard-library Python. It invents no physics: every power, heat, life and energy comes from the Vertex research records
(imports/vertex_<commit>.json, copied from the unsquashed engine branch, and references/evidence/vertex_radiation.json on main). What
this file adds is (1) one lever model, written once here and mirrored line by line in web/engineering/ignition.js, that scales those
recorded values with five visitor levers, and (2) the per-part display allocation the page needs to show where the heat lands.
PROTOTYPE display choices are named in PROTO and on the page.

Lever model (per engine; all four engines alike, as in the 1.7 ledger):
  P   = tau * Pf                                    fusion power at throttle tau (power-limited burn: thrust and power scale together)
  Hpn = tau * PN * src                              photons and neutrons absorbed behind the drawn shadow shield, times the source factor
  Hl  = tau * L * leak / leak0                      charged plasma reaching hardware (1.6B: 18.3 % of the stream)
  Hd  = tau * D100 * 100 / G                        driver recirculation rejected as heat (1.7: Pf/(G eta), eta 0.5, conversion 0.9)
  H   = Hpn + Hl + tau * loss + Hd                  heat the radiators must carry
  Q   = rho * cap                                   radiator capacity (canon drive share 2.70 GW per engine, times rho)
  ratio = H / Q ; melt time = E1000 / (H - Q) when H > Q (engine heat capacity for +1000 K, 1.5 T3)
  coil life (per coil) = life_unshielded * (Pf_n / P) * att / src ; the run the coils must survive = 4 burns of burn_d / tau
  driver power Pd = P / (G eta) ; the only budgeted source, the 50 MW pulse bank, empties in bank_J / Pd
  added mass = radiators (rho - 1) * area * areal mass * 4 + coil shields (per coil: shield_kg * ln(att) / ln(att_needed)) * 4
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'src' / 'wayfarer'))

PROTO = {
    'cp_J_kgK': 500.0,               # 1.5 T3 estimate, used for the per-part display temperatures
    'cold_enthalpy_J_kg': 20000.0,   # winding pack 20 K -> 90 K (copper/steel order of magnitude): the coil quench display time
    'start_K': {'coil': 20.0, 'cryostat': 80.0, 'cryo': 30.0},   # cold parts start cold; everything else at 300 K
    'melt_K': {'structure': 1930.0, 'coil': 1358.0, 'cryostat': 1700.0, 'shield': 961.0, 'armour': 3290.0, 'hot': 2900.0,
               'cryo': 1700.0, 'power': 1358.0, 'fuel': 1700.0, 'service': 933.0, 'sensor': 1700.0, 'lamp': 1700.0},
    'quench_kinetic_share': 0.1,     # share of the 9.7 GJ quench energy shown as cryostat fragment motion (display)
    'cascade_s': 0.004,              # display spread between the first and the following engines' quench (one engine off: LC-06)
    'radiator_areal_kg_m2': 10.0,    # 1.6B mission rows: radiator_added_kg / radiator_added_m2
    'radiator_W_m2': 535727.9,       # 1.5 thermal per_m2_W (14.4 GW over the as-built area)
    'trip_allowance_yr': 0.3,        # 2.0 gate G3: extra trip time the mission tolerates (PROTOTYPE there too)
}


def imports():
    f = sorted((HERE / 'imports').glob('vertex_*.json'))[-1]
    return json.loads(f.read_text()), f.name


def radiation():
    return json.loads((ROOT / 'references/evidence/vertex_radiation.json').read_text())


def levers():
    """The five visitor levers: range, default (the drawn design), log scale, what it stands for."""
    return [
        dict(id='rho', label='Radiator capacity', unit='x today', min=1, max=1e5, value=1, log=True,
             what='More radiator area per engine. Canon gives each engine 2.70 GW (75 % of the 14.4 GW radiator, four engines).'),
        dict(id='att', label='Coil neutron shielding', unit='x attenuation', min=1, max=1e7, value=1, log=True,
             what='Shielding wrapped round each coil (1.6B). It protects the superconductor; it does not remove heat, it absorbs it.'),
        dict(id='leak', label='Plasma leaking onto hardware', unit='% of the stream', min=0, max=0.3, value=0.182996, log=False, pct=True,
             what='Charged exhaust that the magnetic nozzle fails to send aft (1.6B computed 18.3 %).'),
        dict(id='src', label='Photon and neutron output', unit='x today', min=1e-7, max=1, value=1, log=True,
             what='A cleaner burn: less X-ray and neutron energy per joule of fusion. It also slows the neutron damage to the coils.'),
        dict(id='G', label='Target gain', unit='fusion / driver energy', min=10, max=1e7, value=100, log=True,
             what='How much fusion energy each joule of driver energy buys. The driver power comes back as heat.'),
        dict(id='tau', label='Power throttle', unit='of mission power', min=1e-6, max=1, value=1, log=True,
             what='Run the drive gentler. The burn gets longer in proportion (power-limited).'),
    ]


def constants(I):
    L = I['ledger']; R = L['reference']; N = I['neutrons']; S = I['startup']
    return dict(
        Pf=R['Pf_W'], PN=R['photon_neutron_W'], PN_unshielded=L['unshielded']['photon_neutron_W'], L=R['leak_W'], loss=R['loss_W'],
        cap=R['capacity_W'], leak0=I['leak']['hardware_fraction'], D100=L['driver']['reject_W'], eta=L['driver']['efficiency'],
        E1000=None, Pf_n=N['Pf_W'], coils=N['coils'], bank_J=S['pulse_bank_GJ'] * 1e9, bank_W=S['pulse_bank_MW'] * 1e6,
        burn_d=I['mission']['burn_d'], burns=4, margin_kg=N['mass_margin_kg'],
        cold_allowed_W=next(a['allowed_W'] for a in I['leak']['allowable'] if a['cls'] == 'CRYOGENIC_SUPERCONDUCTOR'),
        quench_J=I['quench']['F-QUENCH']['energy_J'], area_m2=R['capacity_W'] / PROTO['radiator_W_m2'],
        areal_kg=PROTO['radiator_areal_kg_m2'], allowance_s=PROTO['trip_allowance_yr'] * 365.25 * 86400)


def evaluate(K, v):
    """The lever model (module docstring). v: lever values by id. Returns the readouts and the failures, earliest first."""
    tau, rho, att, leak, src, G = (v[k] for k in ('tau', 'rho', 'att', 'leak', 'src', 'G'))
    P = tau * K['Pf']
    Hpn = tau * K['PN'] * src
    Hl = tau * K['L'] * leak / K['leak0']
    Hd = tau * K['D100'] * 100.0 / G
    H = Hpn + Hl + tau * K['loss'] + Hd
    Q = rho * K['cap']
    burn_s = K['burn_d'] * 86400.0 / tau
    run_s = K['burns'] * burn_s
    lives = [dict(coil=c['coil'], life_s=c['life_unshielded_s'] * (K['Pf_n'] / P) * att / src,
                  shield_kg=c['shield_kg'] * (math.log(att) / math.log(c['attenuation_needed']) if att > 1 else 0.0)) for c in K['coils']]
    first = min(lives, key=lambda c: c['life_s'])
    shield_kg = 4 * sum(c['shield_kg'] for c in lives)
    rad_kg = 4 * (rho - 1) * K['area_m2'] * K['areal_kg']
    Pd = P / (G * K['eta'])
    out = dict(P_W=P, heat_W=H, burn_heat_W=Hpn + Hl + tau * K['loss'], driver_heat_W=Hd, capacity_W=Q, ratio=H / Q,
               burn_ratio=(Hpn + Hl + tau * K['loss']) / Q, driver_W=Pd, bank_ratio=Pd / K['bank_W'], burn_s=burn_s, run_s=run_s,
               coil=first['coil'], coil_life_s=first['life_s'], added_kg=shield_kg + rad_kg, shield_kg=shield_kg, radiator_kg=rad_kg,
               melt_s=(K['E1000'] / (H - Q)) if H > Q else None, extra_trip_s=K['burns'] * (burn_s - K['burn_d'] * 86400.0))
    fails = []
    if Pd > K['bank_W']:
        fails.append(dict(id='POWER', t=K['bank_J'] / Pd, what=f'the driver needs {Pd / 1e6:,.4g} MW; the 50 MW pulse bank, the only budgeted source, is empty'))
    if H > Q:
        fails.append(dict(id='MELT', t=out['melt_s'], what=f'{H / Q:,.4g}x more heat than the radiators carry: the engine is +1000 K'))
    if first['life_s'] < run_s:
        fails.append(dict(id='QUENCH', t=first['life_s'], what=f'neutrons end the {first["coil"]} superconductor, it quenches and releases its stored energy'))
    if out['added_kg'] > K['margin_kg']:
        fails.append(dict(id='MASS', t=None, what=f'{out["added_kg"] / 1e3:,.4g} t added against the {K["margin_kg"] / 1e3:.0f} t departure margin'))
    if out['extra_trip_s'] > K['allowance_s']:
        fails.append(dict(id='SLOW', t=None, what=f'four burns of {burn_s / 86400:,.4g} d: the trip grows beyond its {PROTO["trip_allowance_yr"]} yr allowance'))
    fails.sort(key=lambda f: (f['t'] is None, f['t'] or 0))
    out['fails'] = fails
    return out


def parts(spec, R):
    """Per part: the 1.5 radiation group, the drawn mass, the heat share inside its group (area over distance squared to the burn point,
    a display allocation of the group's recorded heat), the start and melt temperatures."""
    import vertex_engine as ve
    import vertex_inspect as vi
    import vertex_radiation as vr
    burn = ve.stations(spec)['burn']
    recs = {r['name']: r for r in vi.records(spec)}
    rows = []
    for p in ve.parts(spec):
        vs, fs = ve.mesh_of(p)[:2]
        w = 0.0
        for f in fs:
            for j in range(1, len(f) - 1):
                a, b, c = vs[f[0]], vs[f[j]], vs[f[j + 1]]
                u = [b[i] - a[i] for i in range(3)]; t = [c[i] - a[i] for i in range(3)]
                cr = (u[1]*t[2]-u[2]*t[1], u[2]*t[0]-u[0]*t[2], u[0]*t[1]-u[1]*t[0])
                area = 0.5 * math.sqrt(sum(x * x for x in cr))
                m = [(a[i] + b[i] + c[i]) / 3 for i in range(3)]
                d2 = (m[0] - burn) ** 2 + m[1] ** 2 + m[2] ** 2
                w += area / max(d2, 1.0)
        rows.append(dict(name=p['name'], group=vr.group_of(p['name']), material=p['material'], mass_kg=recs[p['name']]['mass_kg'], w=w))
    groups = {}
    for r in rows:
        groups.setdefault(r['group'], 0.0)
        groups[r['group']] += r['w']
    # the recorded heat of each group (1.5 components, NOMINAL source: photons low bound + neutron upper bound + charged, aft closure)
    C = R['components']
    gheat = {g: C[g]['photon']['NOMINAL']['low'] + C[g]['neutron_upper']['NOMINAL'] + C[g].get('charged_W', {}).get('low', 0.0) for g in C}
    gpn = {g: C[g]['photon']['NOMINAL']['low'] + C[g]['neutron_upper']['NOMINAL'] for g in C}
    gch = {g: C[g].get('charged_W', {}).get('low', 0.0) for g in C}
    tpn, tch = sum(gpn.values()), sum(gch.values())
    out = []
    for r in rows:
        g = r['group']; f = r['w'] / groups[g] if groups[g] else 0.0
        out.append(dict(name=r['name'], group=g, material=r['material'], mass_kg=round(r['mass_kg'], 1),
                        pn=round(f * gpn.get(g, 0.0) / tpn, 8), ch=round(f * gch.get(g, 0.0) / tch, 8) if tch else 0.0,
                        start_K=PROTO['start_K'].get(r['material'], 300.0), melt_K=PROTO['melt_K'].get(r['material'], 1700.0)))
    return out, {g: round(v / sum(gheat.values()), 5) for g, v in gheat.items()}


def scenarios(K, base):
    """The two isolated failures, each with what it assumes away, and the events on its physical clock."""
    ref = evaluate(K, base)
    heat_only = evaluate(K, dict(base, G=1e12, att=1e12))     # driver free, coils immortal: only the heat is left
    energy_only = evaluate(K, dict(base, rho=1e12))            # radiators infinite: only the energy is left
    q = ref['coil_life_s']
    tread_s = 0.01206                                          # 1.7 F-TREAD: lit armour tiles reach their limit
    return [
        dict(id='overload', title='Overload', subtitle='The energy has nowhere to go',
             assumes='Heat removed perfectly (infinite radiators), so only the energy problems are left.',
             clock=[0.0, q * 1.08], events=[
                 dict(t=0.0, id='IGNITE', title='Ignition at the mission point',
                      text=f'{K["Pf"] / 1e12:.1f} TW of fusion per engine. The budget expects 80 % to leave as exhaust and 4e-5 to be absorbed.'),
                 dict(t=K['bank_J'] / energy_only['driver_W'], id='POWER', title='The pulse bank is empty',
                      text=f'The driver needs {energy_only["driver_W"] / 1e12:.2f} TW per engine ({energy_only["bank_ratio"]:,.0f}x the 50 MW bank). '
                           'Nothing in the ship budget feeds it after the bank (1.7, 1.8 F: driver power was never budgeted).'),
                 dict(t=0.001, id='OVERLOAD', title='Every pulse squeezes the coils',
                      text='Each pulse compresses the coil flux up to 1.86x (1.3), beyond the coil rating: case stress beyond allowable (1.7 F-OVERLOAD).'),
                 dict(t=q, id='QUENCH', title=f'{ref["coil"]} quenches',
                      text=f'Neutrons end the nearest superconductor after {q:.2f} s (1.6B, unshielded). It turns resistive and dumps '
                           f'{K["quench_J"] / 1e9:.1f} GJ, about {K["quench_J"] / 4.184e9:.1f} t of TNT, into the cold mass (1.7 F-QUENCH).'),
                 dict(t=q + PROTO['cascade_s'], id='CASCADE', title='The neighbours follow',
                      text='One engine without field leaves unbalanced forces of about 14 MN on its neighbours (1.2); their coils quench in turn.'),
             ]),
        dict(id='meltdown', title='Meltdown', subtitle='The heat has nowhere to go',
             assumes='Driver powered from somewhere and coils that never wear out, so only the heat is left.',
             clock=[0.0, 3.5 * heat_only['melt_s']], events=[
                 dict(t=0.0, id='IGNITE', title='Ignition at the mission point',
                      text=f'{heat_only["heat_W"] / 1e12:.1f} TW of heat reaches each engine; its radiators carry {K["cap"] / 1e9:.2f} GW.'),
                 dict(t=1e-4, id='COLD', title='The coils lose their cold',
                      text=f'The 20 K circuit can lift {K["cold_allowed_W"] / 1e6:.0f} MW per engine (1.6B); the windings receive thousands of times more.'),
                 dict(t=tread_s, id='ARMOUR', title='The armour faces reach their limit',
                      text='About 1.2e9 W/m2 on the lit tiles: their limit in about 12 ms (1.7 F-TREAD).'),
                 dict(t=heat_only['melt_s'], id='MELT', title='The whole engine is 1000 K hotter',
                      text=f'Heat capacity of 1,244 t for +1000 K is used up in {heat_only["melt_s"] * 1e3:.0f} ms (1.5 T3). '
                           f'{heat_only["ratio"]:,.0f}x more heat arrives than the radiators carry.'),
                 dict(t=1.6 * heat_only['melt_s'], id='SLUMP', title='Parts soften and flow aft',
                      text='Under the thrust the softened structure slumps aft along the axis; the lithium hydride shield goes first (961 K).'),
             ]),
    ], ref


def build():
    I, name = imports(); R = radiation()
    from spec import load
    spec = load(ROOT)[0]
    K = constants(I)
    K['E1000'] = R['treg']['T3']['energy_J']
    base = {l['id']: l['value'] for l in levers()}
    P, gshare = parts(spec, R)
    sc, ref = scenarios(K, base)
    checks = []
    for label, v in (('as drawn', base), ('no driver', dict(base, G=1e12)), ('perfect capture', dict(base, leak=0.0)),
                     ('gentle', dict(base, tau=1e-4)), ('shielded', dict(base, att=3e6)), ('big radiators', dict(base, rho=1e4)),
                     ('what holding takes', dict(base, src=1e-7, leak=0.0, G=3e6)),
                     ('best the studies found', dict(base, att=1e5, src=0.67))):
        o = evaluate(K, v)
        checks.append(dict(label=label, levers=v, ratio=o['ratio'], burn_ratio=o['burn_ratio'], melt_s=o['melt_s'], coil_life_s=o['coil_life_s'],
                           added_kg=o['added_kg'], fails=[f['id'] for f in o['fails']]))
    import importlib.util
    spec_ = importlib.util.spec_from_file_location('ignition_site', HERE / 'site.py')
    entry_site = importlib.util.module_from_spec(spec_); spec_.loader.exec_module(entry_site)
    doc = dict(study='ignition-failures', evidence='DIAGNOSTIC', canon=False, imports=name, inputs_hash=entry_site.inputs_hash(), provenance=I['provenance'],
               sources={k: I[k]['source'] for k in ('ledger', 'leak', 'neutrons', 'quench', 'startup', 'power', 'mission')},
               constants={k: v for k, v in K.items() if k != 'coils'}, coils=K['coils'], proto=PROTO, levers=levers(),
               reference={k: v for k, v in ref.items()}, scenarios=sc, checks=checks, group_heat_share=gshare, parts=P,
               canon_absorbed_fraction=I['power']['canon_absorbed_fraction'],
               requirement=I['ledger']['requirement'], hybrid_with_driver=I['ledger']['driver']['hybrid_with_driver'])
    return doc


if __name__ == '__main__':
    d = build()
    (HERE / 'results').mkdir(exist_ok=True)
    (HERE / 'results/ignition.json').write_text(json.dumps(d, indent=1) + '\n')
    r = d['reference']
    print(f'ratio {r["ratio"]:,.0f}x (burn only {r["burn_ratio"]:,.0f}x), melt {r["melt_s"] * 1e3:.1f} ms, {r["coil"]} life {r["coil_life_s"]:.2f} s, '
          f'driver {r["driver_W"] / 1e12:.2f} TW ({r["bank_ratio"]:,.0f}x bank)')
    for f in r['fails']:
        print(' ', f['id'], f['t'], f['what'])
    for c in d['checks']:
        print(f'  {c["label"]:<16} ratio {c["ratio"]:>12,.2f}  fails {c["fails"]}')
