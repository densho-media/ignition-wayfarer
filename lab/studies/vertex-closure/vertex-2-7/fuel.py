"""Vertex 2.7: exhaust-velocity limits, fuel cycles and the isotropic-radiation floor (research, not canon).

    python3 lab/studies/vertex-closure/vertex-2-7/fuel.py        writes lab/studies/vertex-closure/vertex-2-7/fuel.json and fuel.log (a few seconds)

A  Exhaust-velocity ladder for D-3He, from the all-mass ideal (the ~0.089 c benchmark) down to the ledger's operating point: burnup and
   unburned fuel, the D:He-3 feed ratio, isotropic losses, nozzle divergence (traced kappa) and the velocity spread of a mixed-species
   exhaust (a momentum loss the 2.2-2.6 ledgers did not book). Momentum and energy are conserved per kilogram of exhaust.
B  Fuel cycles: ideal exhaust speed, neutron and photon shares from Bosch-Hale reactivities (vertex_source.sv), He-3 consumed per unit
   of fusion energy, with and without in-situ burning of the He-3 that D-D makes.
C  The isotropic floor: the 1.6B two-temperature balance (vertex_source.solve, spin-polarized S1 case) at full channelling, so the
   question "can VBC, SR-26A and SR-26F be one regime" is answered with the same solver the earlier studies used.
Standard library plus the repository's pure modules; nothing in src/ reads this file.
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT/'src'/'wayfarer'))
import spec  # noqa: E402
import vertex_source as vs  # noqa: E402

C = 299792458.0
MEV = 1.602176634e-13
AMU = 1.66053906660e-27
U_MEV = 931.49410242                      # MeV per amu
M = dict(n=1.008665, p=1.007276, D=2.013553, T=3.015501, He3=3.014932, He4=4.001506, Li6=6.013477, B11=11.006566)   # nuclear masses, amu


def ideal(Q, m_in):
    """All released energy into the kinetic energy of all the reacting mass at one speed (nonrelativistic and exact)."""
    eps = Q/(m_in*U_MEV)
    return dict(eps=eps, beta_nonrel=math.sqrt(2*eps), beta_rel=math.sqrt(1-1/(1+eps/(1-eps))**2) if eps < 1 else None)


def dispersion(species):
    """species: list of (count, mass amu, energy share weight per particle). Returns eta_disp = (impulse / impulse at one common speed)^2 for
    the same mass and the same kinetic energy. 1 = all mass at one speed."""
    Mtot = sum(n*m for n, m, _ in species); E = sum(n*w for n, _, w in species)
    imp = sum(n*math.sqrt(2*w*m) for n, m, w in species)        # p_i = sqrt(2 m_i e_i)
    ideal_imp = math.sqrt(2*E*Mtot)
    return (imp/ideal_imp)**2


def exhaust_species(b, r=1.0, mode='thermal'):
    """Exhaust per original D nucleus: unburned D and He-3, protons and alphas. Energy per particle by mode:
    'common'  every particle at one speed (energy ~ mass): the ledger's implicit assumption;
    'thermal' equal energy per particle (a fully collisional plasma expanded through the nozzle);
    'charge'  energy proportional to charge (ambipolar acceleration dominating);
    'birth'   products keep their birth energies (14.68 / 3.67 MeV), unburned fuel cold: no thermalization at all."""
    burn = b*min(1.0, r)
    s = [(1-burn, M['D'], 1), (r-burn, M['He3'], 2), (burn, M['p'], 1), (burn, M['He4'], 2)]
    s = [x for x in s if x[0] > 1e-12]
    if mode == 'common':
        return [(n, m, m) for n, m, _ in s]
    if mode == 'thermal':
        return [(n, m, 1.0) for n, m, _ in s]
    if mode == 'charge':
        return [(n, m, float(z)) for n, m, z in s]
    if mode == 'birth':
        e = {M['p']: 14.68, M['He4']: 3.67}
        return [(n, m, e.get(m, 1e-6)) for n, m, _ in s]
    raise ValueError(mode)


def ladder(nozzle_kappas, iso_today, iso_sr26a, plasma_other=0.005):
    """ve as successive physical limits are applied (D-3He, r = 1). plasma_other: leakage, conversion and driver losses (ledger C ~0.5 %)."""
    Q = 18.353; m_in = M['D']+M['He3']
    base = ideal(Q, m_in); v0 = base['beta_nonrel']
    rows = [dict(step='ideal: all fusion energy into all reacting mass at one speed (nonrelativistic)', beta=v0),
            dict(step='ideal, exact relativistic (reacting rest mass less Q/c^2 at one speed)', beta=base['beta_rel'])]
    out = dict(ideal=base, rows=rows, grid=[])
    for b in (0.8, 0.95, 0.99, 1.0):
        for iso_name, iso in (('today', iso_today), ('SR-26A', iso_sr26a)):
            for kap in nozzle_kappas:
                for mode in ('common', 'charge', 'thermal'):
                    eta_d = dispersion(exhaust_species(b, 1.0, mode))
                    eta = kap**2*(1-iso-plasma_other)*eta_d
                    out['grid'].append(dict(burnup=b, iso=iso_name, iso_share=iso, kappa=kap, spread=mode, eta_dispersion=eta_d, eta_total=eta,
                                            beta=v0*math.sqrt(b*eta)))
    return out


def sv(s, rx, T):
    return vs.sv(s, rx, T)


def cycle_mix(s, r, Ti, bT=None, bred_burn=0.0, pol_dhe=1.0, dd_supp=1.0):
    """D-3He with feed ratio r = nHe3/nD at ion temperature Ti (keV): power shares by reaction, neutron share, He-3 net consumption.
    bT: burnup of the D-D tritium (default: the source module's CONSERVATIVE value); bred_burn: share of D-D He-3 burned in the same
    pellet; pol_dhe / dd_supp: spin-polarization factors (1.5 / D-D suppression; their survival in a burning plasma is OPEN)."""
    bT = vs.burnup() if bT is None else bT
    nD = 1.0; nHe = r
    rD = nD*nHe*sv(s, 'DHe3', Ti)*pol_dhe
    rn = 0.5*nD*nD*sv(s, 'DDn', Ti)*dd_supp; rp = 0.5*nD*nD*sv(s, 'DDp', Ti)*dd_supp
    rT = rp*bT; rHb = rn*bred_burn
    P = dict(DHe3=(rD+rHb)*18.353, DDn=rn*3.269, DDp=rp*4.033, DT=rT*17.589)
    tot = sum(P.values())
    neut = rn*2.452+rT*14.068
    he3_net = rD                                   # He-3 fed and burned (bred He-3 burned in situ adds energy, not feed)
    ne = nD+2*nHe; zsum = nD+4*nHe
    brems_rel = ne*zsum/tot                        # bremsstrahlung per fusion power at fixed Te, arbitrary units
    m_feed = nD*M['D']+nHe*M['He3']
    return dict(r=r, Ti_keV=Ti, power_share={k: v/tot for k, v in P.items()}, neutron_share=neut/tot, brems_rel=brems_rel,
                he3_kg_per_J=he3_net*M['He3']*AMU/(tot*MEV), he3_mass_share_feed=nHe*M['He3']/m_feed)


def cycles(s):
    """Fuel cycles side by side at their own best temperature (ideal exhaust speed is a property of Q and mass alone)."""
    rows = []
    def add(name, Q, m_in, neutron_share, he3_share, react, note):
        i = ideal(Q, m_in)
        rows.append(dict(cycle=name, Q_MeV=Q, ideal_beta=i['beta_nonrel'], neutron_energy_share=neutron_share, he3_mass_share=he3_share,
                         relative_reactivity=react, note=note))
    peak = max(sv(s, 'DHe3', T) for T in (100, 150, 200, 300))
    ref = cycle_mix(s, 1.0, 200.0)
    add('D-3He 1:1 (reference)', 18.353, M['D']+M['He3'], ref['neutron_share'], ref['he3_mass_share_feed'], 1.0,
        'side D-D and bred D-T make the neutrons; He-3 is 60 % of the fuel mass')
    for r in (2.0, 3.0):
        x = cycle_mix(s, r, 200.0)
        add(f'D-3He He-3-rich 1:{r:g}', 18.353, M['D']+M['He3'], x['neutron_share'], x['he3_mass_share_feed'], None,
            'fewer neutrons (~1/r) but more bremsstrahlung per watt and more He-3 per kg; excess He-3 leaves unburned')
    for r in (0.5, 0.3):
        x = cycle_mix(s, r, 200.0, bred_burn=0.8)
        add(f'D-3He D-rich 1:{r:g} (bred He-3 burned in situ)', 18.353, M['D']+M['He3'], x['neutron_share'], x['he3_mass_share_feed'], None,
            'less He-3 per kg, but neutrons rise ~1/r and the excess deuterium dilutes the exhaust energy')
    add('Catalyzed D-D (no He-3 feed)', 43.25, 6*M['D'], 16.52/43.25*1.0, 0.0, sv(s, 'DDn', 200.0)/peak,
        'He-3 and T bred and burned; about 38 % of the energy leaves as neutrons (2.45 and 14.1 MeV)')
    add('D-T', 17.589, M['D']+M['T'], 14.068/17.589, 0.0, sv(s, 'DT', 60.0)/peak, '80 % neutrons; tritium supply and decay')
    add('3He-3He', 12.86, 2*M['He3'], 0.0, 1.0, 1e-3, 'aneutronic, all He-3; reactivity about 1e-3 of D-3He at reachable temperatures (LITERATURE order)')
    add('p-11B', 8.68, M['p']+M['B11'], 0.001, 0.0, 0.2, 'aneutronic; ideal exhaust 0.039 c is below the mission point; bremsstrahlung exceeds fusion in thermal plasma')
    add('D-6Li', 22.37, M['D']+M['Li6'], 0.05, 0.0, 0.02, 'branching and D-D side reactions; low reactivity (LITERATURE order)')
    return rows


def he3_scan(s):
    """He-3 consumed per unit of fusion energy across feed ratios and temperatures, against the neutron share it costs."""
    out = []
    for Ti in (100.0, 200.0, 300.0):
        for r in (0.2, 0.3, 0.5, 0.7, 1.0, 1.5, 2.0, 3.0):
            for bred in (0.0, 0.8):
                x = cycle_mix(s, r, Ti, bred_burn=bred)
                out.append(dict(Ti_keV=Ti, r=r, bred_burn=bred, neutron_share=x['neutron_share'], brems_rel=x['brems_rel'],
                                he3_kg_per_TJ=x['he3_kg_per_J']*1e12, he3_mass_share_feed=x['he3_mass_share_feed'],
                                DD_power_share=x['power_share']['DDn']+x['power_share']['DDp']+x['power_share']['DT']))
    ref = [x for x in out if x['Ti_keV'] == 200.0 and x['r'] == 1.0 and x['bred_burn'] == 0.0][0]
    for x in out:
        x['he3_vs_ref'] = x['he3_kg_per_TJ']/ref['he3_kg_per_TJ']; x['brems_vs_ref'] = x['brems_rel']/ref['brems_rel']
    return out


def isotropic_floor(s):
    """Photon and neutron shares of the spin-polarized burn (S1, optimistic bracket) with up to 100 % of the products' electron-bound
    energy channelled to ions, over Ti; plus the Compton-trapping lower bound of the dense target (vs.trapping)."""
    case = [x for x in vs.config(s)['cases'] if x['id'] == 'S1'][0]
    rows = []
    for ch in (0.9, 0.95, 0.99, 1.0):
        for Ti in (100.0, 150.0, 200.0, 250.0, 300.0, 400.0):
            o = vs.opts(s, case, vs.OPT); o['channel'] = ch
            r = vs.solve(s, Ti, o, vs.burnup())
            rows.append(dict(channel=ch, Ti_keV=Ti, Te_keV=r['Te_keV'], photon=r['photon_share'], neutron=r['neutron_share'],
                             exchange=r['exchange_share'], iso=r['photon_share']+r['neutron_share'], sustained=r['sustained']))
    best = min(rows, key=lambda x: x['iso'])
    t = vs.trapping(s)
    trapped = best['photon']*t['photon_kept_lower']+best['neutron']
    return dict(rows=rows, best=best, trapping=dict((k, v) for k, v in t.items() if k != 'note'), best_with_trapping_lower=trapped,
                note='with all product energy channelled to ions the electrons are still heated by ion-electron exchange, so Te stays at '
                     f"{best['Te_keV']:.0f} keV and bremsstrahlung balances that exchange: the photon share cannot fall below about "
                     f"{best['photon']*100:.1f} % in a thermal burn. Compton trapping in the dense pellet lowers it by at most "
                     f"{1/t['photon_kept_lower']:.1f}x (REDUCED_MODEL, sign unresolved).")


def run():
    s = spec.load(ROOT)[0]
    vbc = json.loads((ROOT/'lab'/'variants'/'halo-vertex'/'vbc.json').read_text())
    ch95 = [x for x in vbc['channel'] if x['channel'] == 0.95][0]
    iso_today = ch95['photon_share']+ch95['neutron_share']
    lad = ladder((0.883, 0.921, 0.95, 0.97, 1.0), iso_today, iso_today*0.03)
    disp = {mode: {f'b{b}': dispersion(exhaust_species(b, 1.0, mode)) for b in (0.8, 0.95, 1.0)} for mode in ('common', 'charge', 'thermal', 'birth')}
    out = dict(meta=dict(title='Vertex 2.7 exhaust-velocity limits, fuel cycles and isotropic floor (research, not canon)',
                         iso_today=iso_today, iso_sr26a=iso_today*0.03),
               ladder=lad, dispersion=disp, cycles=cycles(s), he3_scan=he3_scan(s), isotropic_floor=isotropic_floor(s))
    return out


def show(o):
    L = o['ladder']
    print(f"ideal D-3He: eps {L['ideal']['eps']:.5f}, beta {L['ideal']['beta_nonrel']:.4f} (nonrel), {L['ideal']['beta_rel']:.4f} (rel)")
    print('dispersion eta (b 0.8 / 0.95 / 1):', {k: [round(v, 3) for v in d.values()] for k, d in o['dispersion'].items()})
    for g in L['grid']:
        if g['iso'] == 'SR-26A' or g['kappa'] in (0.883,):
            print(f"  b {g['burnup']:<4} iso {g['iso']:6s} kappa {g['kappa']:<5} spread {g['spread']:7s} eta {g['eta_total']:.3f} -> ve {g['beta']:.4f} c")
    for c in o['cycles']:
        print(f"{c['cycle']:40s} Q {c['Q_MeV']:6.2f} ideal {c['ideal_beta']:.4f} c  neutrons {c['neutron_energy_share']*100:5.1f} %  He-3 {c['he3_mass_share']*100:4.0f} %  "
              f"react {c['relative_reactivity']}")
    for x in o['he3_scan']:
        if x['Ti_keV'] == 200.0:
            print(f"  Ti 200 r {x['r']:<4} bred {x['bred_burn']}: neutrons {x['neutron_share']*100:5.2f} %  He-3 x{x['he3_vs_ref']:.2f}  brems x{x['brems_vs_ref']:.2f}  DD power {x['DD_power_share']*100:.1f} %")
    f = o['isotropic_floor']
    print('floor', {k: round(v, 4) if isinstance(v, float) else v for k, v in f['best'].items()}, 'with trapping', round(f['best_with_trapping_lower'], 4))
    print(f['note'])


if __name__ == '__main__':
    o = run()
    (HERE/'fuel.json').write_text(json.dumps(o, indent=1, default=str)+'\n')
    show(o)
