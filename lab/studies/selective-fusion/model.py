"""Selective Fusion Engineering: the energy-channel model behind the Fusion engine explainer (engineering/fusion/).

A zero-dimensional power split of a D-3He burn, per watt of fusion power, over the explainer's controls: fuel mix (D share of the
fuel ions), ion temperature, operating mode (thermal Te = Ti, or hot-ion Te = 0.7 Ti held by ion-heating injectors) and spin
polarisation (none; D and 3He polarised; polarised with an ASSUMED D-D suppression). Reactivities are Bosch-Hale, bremsstrahlung is the
relativistic form, the e-i exchange is the NRL rate; all through src/wayfarer/vertex_radiation.py and vertex_source.py, the same code
as the Vertex 1.5/1.6B studies. It is not a reactor solver: no synchrotron, no transport, no burn dynamics. The web page only looks
values up in results/fusion.json and does the linear ledger (exposure, nozzle, Wayfarer scale) the same way as ledger() below.

    python3 lab/studies/selective-fusion/model.py        # writes results/fusion.json (under a second)
"""
import hashlib
import json
import math
import sys
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT/'src'/'wayfarer'))
import vertex_radiation as vr  # noqa: E402
import vertex_source as vs  # noqa: E402

MEV = vr.MEV; KEV = vr.KEV; AMU = vr.AMU; ME = 9.1093837015e-31
mD, mHe3 = vr.M_ION['D']*AMU, vr.M_ION['He3']*AMU
E_DHE3 = vr.Q['DHe3']*MEV            # 18.35 MeV, all charged (p 14.68, alpha 3.67)
E_DDN_N, E_DDN_HE3 = 2.45*MEV, 0.82*MEV
E_DDP = 4.03*MEV                     # T 1.01 + p 3.02, all charged
E_DT_N, E_DT_A = 14.07*MEV, 3.52*MEV

# Grid of the explainer's controls (the page snaps its sliders to these values).
D_SHARES = [round(0.10+0.05*i, 2) for i in range(13)]          # 0.10 .. 0.70 of the fuel ions
TI_KEV = [40.0, 60.0, 80.0, 100.0, 130.0, 160.0, 200.0]
MODES = {'thermal': 1.0, 'hot-ion': 0.7}                     # Te / Ti
POL = {
    'none': dict(dhe3=1.0, dd=1.0, label='Unpolarised fuel', cls='ESTABLISHED'),
    'polarised': dict(dhe3=1.5, dd=1.0, label='D and 3He spins aligned: D-3He rate x1.5', cls='MODEL-BASED'),
    'polarised-dd': dict(dhe3=1.5, dd=0.25, label='Aligned, and D-D assumed suppressed x0.25', cls='SPECULATIVE'),
}
T_BURN = 0.5                         # share of D-D tritons that burn with D before leaving (ASSUMED; depends on confinement)
REF = dict(d_share=0.5, Ti=100.0, mode='thermal', pol='none')    # the Vertex-like reference point the page marks

# Ledger constants. SPEC values are read from the parameters; ENGINEERING values are the Vertex studies' own results.
NEUTRON_ABSORBED = 0.87              # Engine 1.4: share of neutron power absorbed by engine hardware
PHOTON_EXPOSURE_REF = 0.62           # Vertex 1.5: share of photons that hit the real engine meshes
INJECTOR_EFF = 0.9*0.85              # ion-heating injector chain, electricity from direct conversion (advanced-technology assumption)


def canon():
    s = tomllib.loads((ROOT/'data'/'wayfarer_3d.toml').read_text())
    op = s['physics']['operating_point']
    return dict(directed_efficiency=op['directed_efficiency'], absorbed_fraction=op['absorbed_fraction'], hot_share=op['hot_share'],
                exhaust_velocity_m_s=op['exhaust_velocity_m_s'], jet_W=209e12, fusion_W=261.2e12, hot_radiator_W=14.4e9,
                ship_body_m=s['ship']['length']['value'], engines=4,
                sources=dict(directed_efficiency='physics.operating_point.directed_efficiency (WORKING)',
                             absorbed_fraction='physics.operating_point.absorbed_fraction (B01, WORKING requirement)',
                             jet_W='docs/FUEL_SYSTEM.md 3: 209 TW jet at the operating point',
                             fusion_W='docs/FUEL_SYSTEM.md 10.3: 4 x 65.3 TW',
                             hot_radiator_W='MODEL.md B01 note: 14.4 GW ideal hot rejection at 1800 K'))


def point(d_share, Ti, mode, pol):
    """Power channels per watt of fusion power at one control setting, plus the relative fusion power at fixed plasma pressure."""
    p = POL[pol]; Te = Ti*MODES[mode]
    nD, nH = d_share, 1.0-d_share                    # per unit fuel-ion density
    ne = nD+2*nH; zeff = (nD+4*nH)/ne
    n0 = 1e21                                         # absolute density cancels in every share (all rates scale as n^2)
    sDH = vr.sigma_v('DHe3', Ti)*p['dhe3']
    sDDn, sDDp = vr.sigma_v('DDn', Ti)*p['dd'], vr.sigma_v('DDp', Ti)*p['dd']
    r_dhe = nD*nH*sDH*n0*n0
    r_ddn = 0.5*nD*nD*sDDn*n0*n0
    r_ddp = 0.5*nD*nD*sDDp*n0*n0
    r_dt = r_ddp*T_BURN
    P = dict(dhe3=r_dhe*E_DHE3, ddn=r_ddn*(E_DDN_N+E_DDN_HE3), ddp=r_ddp*E_DDP, dt=r_dt*(E_DT_N+E_DT_A))
    Pf = sum(P.values())
    neutron = (r_ddn*E_DDN_N+r_dt*E_DT_N)/Pf
    photon = vr.brems_W_m3(ne*n0, Te, zeff)/Pf
    ei = 0.0
    if Te < Ti:
        lnL = vr.lnlambda(ne*n0, Te)
        for nb, Zb, mb in ((nD*n0, 1, mD), (nH*n0, 2, mHe3)):
            ei += 1.5*ne*n0*(Ti-Te)*KEV/vs.tau_ex(ne*n0, 1, ME, Te, nb, Zb, mb, Ti, lnL)
        ei /= Pf
    # fusion power at fixed pressure (ne Te + n_i Ti fixed): density scales as 1 / (ne Te + (nD + nH) Ti), power as its square
    pressure = ne*Te+(nD+nH)*Ti
    rel = Pf/(n0*n0)/pressure**2
    return dict(reactions={k: v/Pf for k, v in P.items()}, rates=dict(dhe3=r_dhe, ddn=r_ddn, ddp=r_ddp, dt=r_dt),
                charged=1.0-neutron, neutron=neutron, photon=photon, ei=ei, rel_power=rel, Te=Te)


def ledger(pt, exposure, k):
    """The page's ledger, per watt of fusion: what becomes thrust, what is lost, what heats hardware. Closes to 1 by construction."""
    loss = pt['ei']*(1/INJECTOR_EFF-1)                 # injector chain losses, paid from the charged power
    plasma = pt['charged']-pt['photon']-loss            # what the charged products leave in the plasma for the nozzle
    sustains = plasma > 0
    plasma = max(plasma, 0.0)
    thrust = plasma*k['directed_efficiency']
    spread = plasma-thrust
    heat = pt['photon']*exposure+pt['neutron']*NEUTRON_ABSORBED+loss
    escape = pt['photon']*(1-exposure)+pt['neutron']*(1-NEUTRON_ABSORBED)
    P_needed = k['jet_W']/thrust if thrust > 0 else None
    heat_W = heat*P_needed if P_needed else None
    budget = k['hot_radiator_W']*k['hot_share']
    return dict(thrust=thrust, spread=spread, photon=pt['photon'], neutron=pt['neutron'], injector_loss=loss, heat=heat, escape=escape,
                sustains=sustains, fusion_needed_W=P_needed, heat_W=heat_W, radiator_multiple=heat_W/budget if heat_W else None,
                closure=thrust+spread+pt['photon']+pt['neutron']+loss if sustains else None)


def inputs_hash():
    h = hashlib.sha256()
    for p in (HERE/'model.py', ROOT/'src/wayfarer/vertex_radiation.py', ROOT/'src/wayfarer/vertex_source.py', ROOT/'data/wayfarer_3d.toml'):
        h.update(p.read_bytes())
    return h.hexdigest()[:16]


def main():
    k = canon()
    grid = {}
    for pol in POL:
        for mode in MODES:
            for Ti in TI_KEV:
                for d in D_SHARES:
                    pt = point(d, Ti, mode, pol)
                    grid[f'{pol}|{mode}|{Ti:g}|{d:.2f}'] = [round(pt['charged'], 6), round(pt['neutron'], 6), round(pt['photon'], 6),
                                                             round(pt['ei'], 6), pt['rel_power'],
                                                             round(pt['reactions']['dhe3'], 6), round(pt['reactions']['ddn']+pt['reactions']['ddp'], 6),
                                                             round(pt['reactions']['dt'], 6)]
    best = max(v[4] for v in grid.values())
    for v in grid.values():
        v[4] = round(v[4]/best, 5)
    ref = point(REF['d_share'], REF['Ti'], REF['mode'], REF['pol'])
    checks = []
    for (d, Ti, mode, pol, ex) in ((0.5, 100.0, 'thermal', 'none', 0.62), (0.3, 100.0, 'thermal', 'none', 0.62),
                                   (0.5, 150.0 if 150.0 in TI_KEV else 160.0, 'hot-ion', 'polarised', 0.2), (0.2, 60.0, 'thermal', 'none', 0.62),
                                   (0.4, 100.0, 'thermal', 'polarised-dd', 0.05)):
        pt = point(d, Ti, mode, pol); lg = ledger(pt, ex, k)
        checks.append(dict(key=f'{pol}|{mode}|{Ti:g}|{d:.2f}', exposure=ex, ledger=lg))
    out = dict(contract='WF_SELECTIVE_FUSION', inputs_hash=inputs_hash(), canon=k,
               axes=dict(d_share=D_SHARES, Ti=TI_KEV, modes=MODES, pol={p: {kk: vv for kk, vv in v.items()} for p, v in POL.items()}),
               fields=['charged', 'neutron', 'photon', 'ei', 'rel_power', 'share_dhe3', 'share_dd', 'share_dt'], grid=grid, reference=REF,
               reference_point=dict(charged=ref['charged'], neutron=ref['neutron'], photon=ref['photon']),
               reference_ledger=ledger(ref, PHOTON_EXPOSURE_REF, k),
               constants=dict(neutron_absorbed=NEUTRON_ABSORBED, photon_exposure_ref=PHOTON_EXPOSURE_REF, injector_eff=INJECTOR_EFF,
                              t_burn=T_BURN, te_over_ti_hot=MODES['hot-ion'],
                              energies_MeV=dict(dhe3=18.35, alpha=3.67, proton=14.68, ddn_n=2.45, ddn_he3=0.82, ddp_t=1.01, ddp_p=3.02,
                                                dt_n=14.07, dt_alpha=3.52)),
               checks=checks)
    (HERE/'results').mkdir(exist_ok=True)
    (HERE/'results'/'fusion.json').write_text(json.dumps(out, separators=(',', ':')))
    return out


if __name__ == '__main__':
    o = main()
    for c in o['checks']:
        lg = c['ledger']
        print(c['key'], f"exp {c['exposure']}", {k: (round(v, 4) if isinstance(v, float) else v) for k, v in lg.items() if k not in ('fusion_needed_W', 'heat_W')},
              f"x{lg['radiator_multiple']:.0f}" if lg['radiator_multiple'] else 'no burn')
    print('grid points', len(o['grid']), 'bytes', (HERE/'results'/'fusion.json').stat().st_size)
