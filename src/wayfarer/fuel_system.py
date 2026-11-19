"""Fuel & Propellant System (FPS, owner brief 2026-11-18), Version 0. Pure, standard library only.

Two independently supplied materials, from the ship's storage to the four Vertex engines:
- fusion fuel: deuterium (V0), with helium-3 as the canon second fuel. Each leaves its feed run tank through an outlet valve, a metering
  and conditioning unit (flow metering, pressure and temperature trim, filter, isotopic/purity sampling) and a fail-closed emergency
  isolation valve, crosses the reactor shadow shield in its own stepped sleeve and ends on the forward face of the cluster's power and
  conditioning bay (IF_FPS_FUEL_BAY_*), where the engine workstream's target fabrication fills the D-3He or D-only targets. The two fuels
  are metered separately and meet only in the target (propulsion.injection.fusion_fuel); the blend is a setpoint (he3_per_d_molar).
- reaction mass: hydrogen. Each of its two run tanks feeds a boost pump and a conditioning skid (vaporiser/heater, flow controller,
  filter), an isolation valve and its sleeve, then a trunk aft in the cage-to-skin corridor, inside the thrust ring and on to a header ring
  forward of the cluster hub; one branch per engine runs to a seventh slot on that engine's service panel (IF_FPS_H2_ENGINE_0n). Hydrogen
  never enters the fuel path (propulsion.inventories).
- safety and service: a relief valve on every run tank venting through a tee outlet (non-propulsive) on the hull, a helium purge store
  for the hydrogen lines, pressure/temperature/flow sensor sleeves on every line, supports to the primary frames, and a refuelling
  receptacle on the farm deck with one fill line and valve to each species' ring main.

Flows, regimes, the fuel-cycle and reaction-mass trades and the feedstock chain are computed here from physics.operating_point and the
[fuel_system] constants, so the browser's operating states read the same numbers as the documents. Every dimension is PROTOTYPE.

    python3 src/wayfarer/fuel_system.py            # flows, regimes, trades and the fit screen
    python3 src/wayfarer/fuel_system.py --json     # the same as JSON (the web export reads report())
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import drive_hot_section as hsec
import drive_manifold as dm
import fuel_storage as fst
import layout
import vertex_cluster as vc
import vertex_engine as ve

MEV_J = 1.602176634e-13
U_KG = 1.66053906660e-27
G0 = 9.80665
SPECIES = ('deuterium', 'helium-3', 'hydrogen')
TAG = {'deuterium': 'D2', 'helium-3': 'He3', 'hydrogen': 'H2'}
ROLE = {'deuterium': 'fusion fuel', 'helium-3': 'fusion fuel (second, canon)', 'hydrogen': 'reaction mass'}


def cfg(s):
    return s['fuel_system']


def feed_cfg(s):
    return cfg(s)['feed']


def active(s):
    """The FPS aft feed train is the shown ship's: built only with the Vertex cluster (the Fiji representation keeps drive.cryo_feed)."""
    return vc.active(s) == vc.VERTEX


# ---------- flows -------------------------------------------------------------------------------------------------------------------

def flows(s):
    """Peak mass flow per species (kg/s), whole ship and per engine, from the B01 burn's proportions (operating_point.burn): the reacted
    D and He-3 plus the unrecovered feed, the rest hydrogen. Liquid volume flow, run-tank endurance and the mission totals with it."""
    import operating_point as op
    b = op.burn(s); m = b['peak_mass_flow_kg_s']; e = b['expelled_kg']
    q = op.p(s); fed = b['reacted_dhe3_kg']/q['burnup']        # fuel fed to the burn (the recovered remainder recirculates)
    share = {'helium-3': b['reacted_he3_kg']/e, 'deuterium': b['reacted_d_kg']/e}
    share['hydrogen'] = b['hydrogen_expelled_kg']/e
    rho = fst.cfg(s)['density_kg_m3']; key = fst.INV_KEY; n = vc.config(s)['engine_count']
    rt = {t['name']: math.pi*t['radius']**2*(t['x1']-t['x0']) for t in fst.run_tanks(s)}
    fam = s['drive_hot_section']['tank_families']; inv = fst.inventory(s); out = {}
    for sp in SPECIES:
        kg_s = m*share[sp]; vol = sum(v for (nm, v), f in zip(rt.items(), fam) if f == sp)
        out[sp] = dict(role=ROLE[sp], kg_s=kg_s, per_engine_kg_s=kg_s/n, liquid_L_s=kg_s/rho[key[sp]]*1e3,
                       run_tank_m3=vol, run_tank_hours=vol*rho[key[sp]]/kg_s/3600, mission_t=inv[key[sp]]/1e3,
                       first_burn_t=share[sp]*e/1e3)
    out['total'] = dict(kg_s=m, fuel_fed_kg_s=fed/b['duration_s'], recovered_kg_s=(fed-b['reacted_dhe3_kg'])/b['duration_s']*q['recovery'],
                        thrust_N=b['peak_thrust_N'], ve_m_s=b['exhaust_velocity_m_s'], jet_W=b['peak_jet_power_W'],
                        fusion_W=b['peak_fusion_power_W'], burn_days=b['duration_d'])
    return out


def bore_m(kg_s, rho, v=2.0):
    """Liquid bore diameter for a flow at velocity v (m/s): the first-order line size."""
    return 2*math.sqrt(kg_s/rho/v/math.pi)


def regimes(s, factors=(0.0, 0.5, 1.0, 1.5, 2.0, 3.0)):
    """Thrust/exhaust-velocity regimes at the drive's fixed jet power: the fuel flow is set by the fusion power, the hydrogen flow is the
    throttle (factor x the operating point's). F = sqrt(2 P m), ve = 2 P / F. Assumes the jet keeps the operating point's directed
    efficiency with any hydrogen load: the energy transfer from fusion products to cold hydrogen is SPECULATIVE (engine side)."""
    f = flows(s); P = f['total']['jet_W']; fuel = f['total']['kg_s']-f['hydrogen']['kg_s']; out = []
    for k in factors:
        m = fuel+k*f['hydrogen']['kg_s']; F = math.sqrt(2*P*m)
        out.append(dict(h2_factor=k, h2_kg_s=k*f['hydrogen']['kg_s'], mass_flow_kg_s=m, thrust_MN=F/1e6, ve_km_s=2*P/F/1e3,
                        ve_c=2*P/F/299792458.0))
    return out


def heads(s):
    """Hydrostatic head of each species from the farm (aft deck) to the feed run tanks at the first burn's accelerations: under thrust
    the transfer runs downhill (the farm is forward), so the run tanks see this extra pressure; in the coast it is zero and transfer needs
    tank pressurisation and propellant management devices (OPEN)."""
    import operating_point as op
    b = op.burn(s); dk = fst.deck(s); rt = fst.run_tanks(s); h = dk['x0']-rt[0]['x1']; rho = fst.cfg(s)['density_kg_m3']
    return {sp: dict(height_m=h, kPa=[rho[fst.INV_KEY[sp]]*a*G0*h/1e3 for a in b['accel_g']]) for sp in SPECIES}


def conditioning(s):
    """Heat to take liquid hydrogen at storage to injection gas at 300 K (latent + sensible, first order, para-H2), and the power at the
    peak flow; it is a heat sink for the warm loop, not a heat source. Ionising it outside the engine would cost ~15.8 eV per atom."""
    f = flows(s)['hydrogen']['kg_s']; latent = 4.46e5; cp = 14.3e3; dT = 300.0-20.0
    ion = 15.8*1.602176634e-19/(1.00794*U_KG)
    return dict(J_kg=latent+cp*dT, W=f*(latent+cp*dT), ionisation_J_kg=ion, ionisation_W=f*ion,
                pump_W_per_MPa=f*1e6/fst.cfg(s)['density_kg_m3']['hydrogen'])


# ---------- trades ------------------------------------------------------------------------------------------------------------------

def fuel_cycles(s):
    """Fusion-fuel trade at the operating point's peak fusion power: specific energy, fuel flow, neutron share and neutron power, and the
    mission fuel at the same fusion energy. D-3He neutrons are its D-D side reactions (side_neutron_share)."""
    import operating_point as op
    b = op.burn(s); P = b['peak_fusion_power_W']; mission_J = b['fusion_energy_J']*op.mission(s)['propellant_kg']/b['expelled_kg']
    out = {}
    for k, r in cfg(s)['reactions'].items():
        eps = r['q_mev']*MEV_J/(r['mass_u']*U_KG); nshare = r['neutron_mev']/r['q_mev'] or r.get('side_neutron_share', 0.0)
        out[k] = dict(specific_energy_J_kg=eps, fuel_kg_s=P/eps, neutron_share=nshare, neutron_W=P*nshare, mission_fuel_t=mission_J/eps/1e3,
                      confidence=r['confidence'])
    return out


def feedstock(s):
    """What the refinery processes to supply one mission: water for the deuterium (Earth-ocean and comet D/H, at the recovery), the
    hydrogen's electrolysis and liquefaction energy, and the helium-3 source scale (lunar regolith or giant-planet atmosphere gas)."""
    f = cfg(s)['feedstock']; inv = fst.inventory(s)
    d = inv['deuterium']; h2 = inv['hydrogen']; he3 = inv['helium_3']
    h_frac = 2*1.00794/18.015                                     # hydrogen mass fraction of water
    def water_for_d(dh):
        d_per_kg_water = h_frac/1.00794*dh*2.0141                 # kg D per kg water
        return d/(d_per_kg_water*f['recovery'])
    he_regolith = he3/(f['he3_lunar_ppb']*1e-9)
    he_gas = he3/(f['he3_uranus_he_mass_fraction']*f['he3_per_he4']*3.016/4.0026)
    return dict(d_t=d/1e3, water_for_d_Mt=dict(ocean=water_for_d(f['d_per_h_vsmow'])/1e9, comet=water_for_d(f['d_per_h_comet'])/1e9),
                h2_t=h2/1e3, water_for_h2_kt=h2/h_frac/1e6,
                h2_energy_GWh=h2*(f['electrolysis_kwh_per_kg_h2']+f['liquefaction_kwh_per_kg_h2'])/1e6,
                he3_t=he3/1e3, he3_regolith_Gt=he_regolith/1e12, he3_atmosphere_gas_Mt=he_gas/1e9,
                note='The D refinery processes ~40-100x more hydrogen than the ship carries as reaction mass: the H2 propellant is a '
                     'by-product stream of the deuterium enrichment, which sets the refinery size.')


def reaction_masses(s):
    """Reaction-mass trade for the mission's hydrogen mass (same jet power and ve, so the same mass): stored volume and first-order tank
    mass. Species barely changes the energy budget at ve ~0.064 c (ionisation is ~1e-5 of the jet energy per kg); storage and what the
    heavier nuclei do in the exhaust and on hardware decide it."""
    m = fst.inventory(s)['hydrogen']; out = {}
    for k, r in cfg(s)['reaction_masses'].items():
        out[k] = dict(volume_m3=m/r['density_kg_m3'], tank_t=m*r['tank_fraction']/1e3, storage_K=r['storage_K'], z=r['z'], note=r['note'])
    return out


# ---------- geometry ----------------------------------------------------------------------------------------------------------------

def _unit(y, z):
    r = math.hypot(y, z)
    return y/r, z/r


def stations(s):
    st = dm.stations(s); cs = vc.stations(s); p = s['prototype']
    rt = fst.run_tanks(s); ring = dm.stations(s)['ring']
    return dict(cap=rt[0]['x0'], shield_fwd=st['shield_fwd'], shield_aft=st['shield_aft'], bay_fwd=cs['bay']+cs['bay_length']/2,
                bay_aft=cs['bay']-cs['bay_length']/2, bay_r=cs['bay_radius'], hub_fwd=cs['hub_fwd'], ring=ring,
                ring_fwd=ring+p['thrust_ring_depth_m']/2 if 'thrust_ring_depth_m' in p else ring+1.0)


def _sleeves(s):
    """The canon stepped shield sleeves (drive_hot_section.cryo_feed): each line's points from the tank cap to the shield's aft jog plane."""
    st = dm.stations(s); xa = st['shield_aft']+s['drive_hot_section']['cryo_feed_sleeve_jog_inset_m']; out = {}
    for l in hsec.cryo_feed(s):
        pts = []
        for q in l['points']:
            pts.append(q)
            if abs(q[0]-xa) < 1e-9 and (l['terminus'] == 'core' or math.hypot(q[1], q[2]) >= s['drive_hot_section']['h2_corridor_radius_m']-1e-9):
                break
        out[l['index']] = dict(points=pts, family=l['family'], shield_point=l['shield_point'], tank=l['tank'], index=l['index'])
    return out


def feed_lines(s):
    """The four run-tank lines and the H2 branches: name, species, polyline and the equipment stations along it."""
    f = feed_cfg(s); st = stations(s); sl = _sleeves(s); out = []
    hx = header(s)['x']; x_step = st['ring_fwd']+f['h2_step_fwd_of_ring_m']
    letter = {3: 'A', 4: 'B'}
    for j, l in sl.items():
        sp = l['family']; pts = list(l['points'])
        if sp == 'hydrogen':
            y, z = pts[-1][1:]; uy, uz = _unit(y, z); ri = f['h2_inner_radius_m']
            pts += [(x_step, y, z), (x_step-0.6, uy*ri, uz*ri), (hx, uy*ri, uz*ri)]
            name = f'FPS_Feed_H2_{letter[j]}'
        else:
            pts += [(st['bay_fwd'], *pts[-1][1:])]
            name = f'FPS_Feed_{TAG[sp]}'
        out.append(dict(name=name, species=sp, index=j, tank=l['tank'], points=pts, radius=f['line_radius_m'], shield_point=l['shield_point']))
    return out


def _along(pts, x):
    """Point of an X-monotone polyline at station x (first segment spanning it)."""
    for a, b in zip(pts, pts[1:]):
        if (a[0]-x)*(b[0]-x) <= 0 and abs(a[0]-b[0]) > 1e-9:
            t = (x-a[0])/(b[0]-a[0]); return tuple(a[i]+t*(b[i]-a[i]) for i in range(3))
    raise ValueError(x)


def equipment(s):
    """Boxes and cylinders on the lines: outlet valve, metering unit or pump + skid, isolation valve; centre, size and kind."""
    f = feed_cfg(s); st = stations(s); out = []
    for ln in feed_lines(s):
        a = ln['points'][0]; y, z = a[1:]; tag = ln['name'].split('_', 2)[2]; sp = ln['species']
        ov = f['outlet_valve']; out.append(dict(name=f'FPS_Outlet_Valve_{tag}', kind='fps_valve', species=sp, line=ln['name'], shape='box',
                                                at=(a[0]-ov['offset_m'], y, z), size=(ov['size_m'],)*3,
                                                function='run-tank outlet isolation valve on the aft-apex sump (remote-operated, fail-closed)'))
        if sp == 'hydrogen':
            p = f['pump']; out.append(dict(name=f'FPS_Boost_Pump_{tag}', kind='fps_pump', species=sp, line=ln['name'], shape='cyl',
                                           at=(a[0]-p['gap_m'], y, z), length=p['length_m'], radius=p['radius_m'],
                                           function='LH2 boost pump: raises the run-tank liquid to the feed pressure (canned-motor centrifugal, ~6 kW/MPa at the peak flow)'))
            k = f['h2_skid']; out.append(dict(name=f'FPS_H2_Conditioner_{tag}', kind='fps_conditioner', species=sp, line=ln['name'], shape='box',
                                              at=(a[0]-k['gap_m']-k['length_m']/2, y, z), size=(k['length_m'], k['width_m'], k['height_m']),
                                              function='H2 conditioning skid: filter, vaporiser/heater on the warm loop, mass-flow controller (the propellant throttle)'))
        else:
            u = f['fuel_unit']; out.append(dict(name=f'FPS_Fuel_Meter_{tag}', kind='fps_conditioner', species=sp, line=ln['name'], shape='box',
                                                at=(a[0]-u['gap_m']-u['length_m']/2, y, z), size=(u['length_m'], u['width_m'], u['height_m']),
                                                function=f'{TAG[sp]} metering and conditioning unit: filter, purity sampling, pressure/temperature trim, metering valve to the target fill'))
        iv = f['isolation_valve']; x = st['shield_fwd']+iv['fwd_of_shield_m']
        out.append(dict(name=f'FPS_Isolation_Valve_{tag}', kind='fps_valve', species=sp, line=ln['name'], shape='box', at=_along(ln['points'], x),
                        size=(iv['size_m'],)*3, function='emergency isolation valve ahead of the shadow shield (fail-closed on leak, fire or reactor trip)'))
    return out


def header(s):
    f = feed_cfg(s)
    return dict(name='FPS_H2_Header', species='hydrogen', x=dm.stations(s)['ring']-f['header']['aft_of_ring_m'], r=f['header']['radius_m'], tube=f['header']['tube_m'])


def branches(s):
    """One H2 branch per engine: from the header in the engine's azimuth plane radially out between the cluster's thrust struts (forward of
    the hub and spokes) to inlet_standoff_m inboard of the engine collar, then aft along the engine axis to the H2 inlet
    inlet_fwd_of_collar_m forward of the cradle plane, beside the quick-disconnect panel (whose six services take the collar plane)."""
    f = feed_cfg(s); h = header(s); g = ve.config(s)['geometry']; est = ve.stations(s)
    mid = (est['collar_fwd']+est['collar_aft'])/2; out = []
    for pl in vc.placements(s):
        a = math.radians(pl['azimuth_deg']); t = (0.0, -math.sin(a), math.cos(a))
        start = dm.radial(h['x'], h['r'], a)
        rin = g['collar_outer_radius_m']+f['inlet_standoff_m']; xf = mid+f['inlet_fwd_of_collar_m']
        inlet = vc.to_ship(pl, (xf, -rin, 0.0)); X = pl['axes'][0]
        corner = vc.to_ship(pl, (xf+(h['x']-inlet[0])/X[0], -rin, 0.0))
        start = dm.radial(h['x'], h['r'], a); points = [start, corner, inlet]
        out.append(dict(name=f"FPS_H2_Branch_N{pl['n']}", engine=pl['n'], species='hydrogen', points=points, radius=f['line_radius_m'],
                        interface=f"IF_FPS_H2_ENGINE_{pl['n']:02}"))
    return out


def sensors(s):
    """Pressure/temperature/flow sensor sleeves: after the outlet, after the conditioning, before the shield; on every branch at the panel."""
    f = feed_cfg(s); st = stations(s); out = []
    for ln in feed_lines(s):
        x0 = ln['points'][0][0]; xs = [x0-0.75, st['shield_fwd']+0.95, st['shield_aft']-0.25]
        if ln['species'] != 'hydrogen':
            xs[1] = x0-f['fuel_unit']['gap_m']-f['fuel_unit']['length_m']-0.35
        else:
            xs[1] = x0-f['h2_skid']['gap_m']-f['h2_skid']['length_m']-0.35
        out.append(dict(name=f"FPS_Sensors_{ln['name'].split('_', 2)[2]}", species=ln['species'], line=ln['name'],
                        points=[_along(ln['points'], x) for x in xs]))
    for b in branches(s):
        p, q = b['points'][-2], b['points'][-1]; m = tuple(p[i]+0.7*(q[i]-p[i]) for i in range(3))
        out.append(dict(name=f"FPS_Sensors_{b['name'].split('_')[-1]}", species='hydrogen', line=b['name'], points=[m]))
    return out


def supports(s):
    """Line clamps: a short strut from each H2 trunk to the primary frame ring at every primary-frame station it passes in the corridor."""
    f = feed_cfg(s); out = []
    frames = sorted(x for x in _frame_stations(s))
    for ln in feed_lines(s):
        if ln['species'] != 'hydrogen':
            continue
        pts = ln['points']; seg = [(a, b) for a, b in zip(pts, pts[1:]) if abs(a[1]-b[1]) < 1e-9 and abs(a[2]-b[2]) < 1e-9 and abs(a[0]-b[0]) > 2]
        for a, b in seg:
            lo, hi = sorted((a[0], b[0])); y, z = a[1:]; r = math.hypot(y, z); uy, uz = _unit(y, z)
            for x in frames:
                if lo+0.5 < x < hi-0.5:
                    rr = f['support']['frame_r_m']
                    out.append(dict(line=ln['name'], species='hydrogen', a=(x, uy*(r+(f['line_radius_m'] if rr > r else -f['line_radius_m'])), uz*(r+(f['line_radius_m'] if rr > r else -f['line_radius_m']))),
                                    b=(x, uy*rr, uz*rr), radius=f['support']['radius_m']))
    return out


def _frame_stations(s):
    """X of the aft primary frames (components/revision.py builds Primary_Frame_nn at these): the cage's frame pitch from the hub."""
    p = s['prototype']; xs = []
    import hull_geometry
    try:
        return [x for x in hull_geometry.frame_stations(s)]
    except Exception:
        pass
    x0 = dm.stations(s)['ring']
    return [x0+2.0+4.0*k for k in range(8)]


def relief(s):
    """A relief valve on each run tank's forward head (top of the barrel) venting through a short line straight out to a tee outlet
    beyond the hull skin: two opposite nozzles, so venting makes no net thrust."""
    f = feed_cfg(s)['relief']; out = []
    for t in fst.run_tanks(s):
        uy, uz = _unit(t['y'], t['z']); r0 = math.hypot(t['y'], t['z'])+t['radius']; x = t['x1']-0.6
        v = (x, uy*(r0+f['size_m']/2), uz*(r0+f['size_m']/2)); a = math.atan2(t['z'], t['y'])+math.radians(f['exit_offset_deg'])
        k = dm.radial(x, f['turn_r_m'], a); e = dm.radial(x, f['outlet_r_m'], a)
        tee = [(x+f['tee_m']/2, e[1], e[2]), (x-f['tee_m']/2, e[1], e[2])]
        out.append(dict(tank=t['name'], species=dict(zip([q['name'] for q in fst.run_tanks(s)], s['drive_hot_section']['tank_families']))[t['name']],
                        valve=v, vent=[(x, uy*(r0+f['size_m']), uz*(r0+f['size_m'])), k, e], tee=tee, radius=f['vent_radius_m'], size=f['size_m'],
                        hull_point=dm.radial(x, 6.0, a)))
    return out


def purge(s):
    """Two helium purge bottles between the H2 skids (He stays gas at 20 K): they inert the hydrogen lines before maintenance and after a
    trip; one purge line from each bottle to its line's isolation valve."""
    f = feed_cfg(s)['purge']; eq = {e['name']: e for e in equipment(s)}; out = []
    for tag in ('A', 'B'):
        v = eq[f'FPS_Isolation_Valve_H2_{tag}']; y, z = v['at'][1:]; uy, uz = _unit(y, z)
        r = math.hypot(y, z); tg = (-uz, uy); c = (v['at'][0]+f['fwd_of_valve_m'], uy*r+tg[0]*f['offset_m'], uz*r+tg[1]*f['offset_m'])
        out.append(dict(name=f'FPS_Purge_He_{tag}', at=c, length=f['length_m'], radius=f['radius_m'], line_radius=f['line_radius_m'],
                        line=[(c[0]-f['length_m']/2, c[1], c[2]), (v['at'][0], c[1], c[2]), v['at']]))
    return out


def refuel(s):
    """Refuelling receptacle on the farm deck's rim between two outer vessels (azimuth refuel.azimuth_deg): a panel with one dry-break
    coupling per species, and one fill line with an isolation valve radially in along the deck's forward face to each species' ring
    main (outer H2 and He-3 mains, inner D2 main)."""
    f = feed_cfg(s)['refuel']; a = math.radians(f['azimuth_deg']); mains = fst.ring_mains(s); out = []; seen = set()
    panel_x = sum(m['x'] for m in mains)/len(mains)
    for m in sorted(mains, key=lambda q: q['x']):
        if m['species'] in seen:
            continue
        own = [q for q in mains if q['species'] == m['species']]; main = max(own, key=lambda q: q['r']) if m['species'] != 'deuterium' else own[0]
        seen.add(m['species'])
        c = dm.radial(main['x'], f['r_m']-0.4, a); p0 = dm.radial(main['x'], f['r_m']-0.4, a); p1 = dm.radial(main['x'], main['r'], a)
        out.append(dict(name=f"FPS_Refuel_Line_{TAG[m['species']]}", species=m['species'], main=main['name'], points=[p0, p1], radius=f['line_radius_m'],
                        coupling=c, valve=dm.radial(main['x'], (f['r_m']+main['r'])/2, a)))
    return dict(panel=dict(name='FPS_Refuel_Panel', at=dm.radial(panel_x, f['r_m'], a), size=f['panel'], azimuth=a), lines=out,
                coupling_radius=f['coupling_radius_m'])


def interfaces(s):
    """The FPS's declared interfaces with the engine workstream and the ship."""
    out = []
    for ln in feed_lines(s):
        if ln['species'] != 'hydrogen':
            out.append(dict(name=f"IF_FPS_FUEL_BAY_{TAG[ln['species']].upper()}", at=ln['points'][-1], species=ln['species'],
                            note=f"{TAG[ln['species']]} delivery into the cluster power and conditioning bay: target fabrication inlet (engine side). Liquid at ~20 K (D2) or gas/liquid at ~3 K (He-3), metered; flow, purity and pressure per docs/FUEL_SYSTEM.md 'Interfaces'"))
    for b in branches(s):
        out.append(dict(name=b['interface'], at=b['points'][-1], species='hydrogen',
                        note=f"H2 reaction-mass inlet on engine N{b['engine']}'s collar beside its service panel: gas at ~300 K, mass-flow controlled; the engine's injection manifold and its energy coupling are engine side (SPECULATIVE)"))
    h = header(s); out.append(dict(name='IF_FPS_H2_HEADER', at=(h['x'], 0.0, 0.0), species='hydrogen', note='H2 header ring centre (two trunks in, four branches out)'))
    rf = refuel(s); out.append(dict(name='IF_FPS_REFUEL', at=rf['panel']['at'], species='none', note='Refuelling receptacle: tanker umbilical (D2, He-3, H2 dry-break couplings, bonding); standard OPEN'))
    for r in relief(s):
        out.append(dict(name=f"IF_FPS_VENT_{r['tank'][-2:]}", at=r['hull_point'], species=r['species'], note='Hull penetration of the run-tank vent line (OPEN)'))
    return out+v1_interfaces(s)+v11_interfaces(s)


# ---------- V1: the connections that close the chain (owner brief 2026-11-19) ------------------------------------------------------

def v1_cfg(s):
    return cfg(s).get('v1', {})


def v1(s):
    """V1 is built when its table is present (it only adds connections; V0 stays as it was)."""
    return bool(v1_cfg(s))


def _radial_unit(p):
    r = math.hypot(p[1], p[2]); return (0.0, p[1]/r, p[2]/r)


def feedthroughs(s):
    """One hull feedthrough per transfer trunk at its penetration (fuel_storage.transfer_lines): a jacketed sleeve along the local radial
    through the aft hull skin, bridging the exterior leg's end and the interior leg's start, with a flange on each side of the skin."""
    q = v1_cfg(s)['feedthrough']; out = []
    ext = {l['name'][:-4]: l for l in fst.transfer_lines(s) if l['leg'] == 'exterior'}
    for l in fst.transfer_lines(s):
        if l['leg'] != 'interior':
            continue
        hp = l['hull_penetration']; u = _radial_unit(hp); a = ext[l['name']]['points'][-1]; b = l['points'][0]
        h = q['length_m']/2
        out.append(dict(name=f"FPS_Feedthrough_{l['name'].split('_', 2)[2]}", species=l['species'], trunk=l['name'], at=hp, axis=u,
                        a=tuple(hp[i]+u[i]*h for i in range(3)), b=tuple(hp[i]-u[i]*h for i in range(3)), radius=q['radius_m'],
                        flanges=[tuple(hp[i]+u[i]*k for i in range(3)) for k in (h-q['flange_m']/2, -h+q['flange_m']/2)],
                        flange_radius=q['flange_radius_m'], flange_m=q['flange_m'], bridge=[a, b], line_radius=l['radius'],
                        interface=f"IF_FPS_HULL_{l['name'].split('_', 2)[2].upper()}"))
    return out


def tank_inlets(s):
    """One fill nozzle per run tank: from the tee on the tank axis tee_fwd_m forward of its forward cap (where its transfer trunks end,
    fuel_storage.transfer_lines) axially into the cap, with an inlet isolation valve on it; each trunk gets a check valve on its jog to the
    tee, so either trunk fills the tank and neither back-feeds the other."""
    q = v1_cfg(s)['tank_inlet']; out = []
    by_tank = {}
    for l in fst.transfer_lines(s):
        if l['leg'] == 'interior':
            by_tank.setdefault(l['tank'], []).append(l)
    for t in fst.run_tanks(s):
        ls = by_tank.get(t['name'], [])
        if not ls:
            continue
        tee = ls[0]['points'][-1]; tip = (t['x1']-q['nozzle_into_m'], t['y'], t['z'])
        checks = [dict(trunk=l['name'], at=tuple((l['points'][-2][i]+l['points'][-1][i])/2 for i in range(3)), tag=l['name'].split('_', 2)[2]) for l in ls]
        out.append(dict(name=f"FPS_Tank_Inlet_{t['name'][-2:]}", species=ls[0]['species'], tank=t['name'], trunks=[l['name'] for l in ls],
                        nozzle=[tee, tip], radius=q['nozzle_radius_m'], valve=((tee[0]+t['x1'])/2, t['y'], t['z']), valve_size=q['valve_size_m'],
                        checks=checks, check_size=q['check_valve_m']))
    return out


def h2_crossover(s):
    """The inner H2 ring main (inner vessels I2, I4) to the outer one, from which both H2 trunks leave: one radial line on the deck's
    forward face at an azimuth clear of every vessel, with an isolation valve at its middle."""
    q = v1_cfg(s)['h2_crossover']; mains = {(m['species'], m['ring']): m for m in fst.ring_mains(s)}
    i, o = mains[('hydrogen', 'inner')], mains[('hydrogen', 'outer')]; a = math.radians(q['azimuth_deg']); x = i['x']
    return dict(name='FPS_H2_Crossover', species='hydrogen', points=[dm.radial(x, i['r'], a), dm.radial(x, o['r'], a)], radius=q['radius_m'],
                valve=dm.radial(x, (i['r']+o['r'])/2, a), valve_size=q['valve_size_m'], mains=[i['name'], o['name']], azimuth=a)


def _engine_poly(pl, pts):
    return [vc.to_ship(pl, p) for p in pts]


def target_feeds(s):
    """Per engine: the target feed from the service panel's TARGET_FEED slot (the cluster's CL_Nj_Line_TARGET_FEED ends on the panel's hub
    face) forward along the collar clear of the lithium manifold and cryogen header, radially in beside the hub-side pulse pod, forward
    outside the cartridge shell and in through it to the target magazine (engine frame points; CANDIDATE for the engine workstream)."""
    q = v1_cfg(s)['target_feed']; sp = ve.service_panel(s); z = sp['slots']['TARGET_FEED']; out = []
    r_in = q['inner_r_m']; k = q['magazine_r_m']/math.hypot(r_in, z)
    local = [(sp['x_fwd'], -sp['r'], z), (q['x_turn_m'], -sp['r'], z), (q['x_turn_m'], -r_in, z), (q['x_magazine_m'], -r_in, z),
             (q['x_magazine_m'], -r_in*k, z*k)]
    for pl in vc.placements(s):
        out.append(dict(name=f"FPS_N{pl['n']}_Target_Feed", engine=pl['n'], species='target', local=local, points=_engine_poly(pl, local),
                        radius=q['radius_m'], interface=f"IF_FPS_TARGET_N{pl['n']}"))
    return out


def h2_injection(s):
    """Per engine: from the H2 inlet (fuel_system.branches) a short line with the injection control valve to a manifold ring forward of the
    thrust collar, and eight injector ports from the ring aft through drilled galleries in the collar, across to the shadow shield and
    dog-legged through it (axial, radially in, axial) to the burn face, at azimuths between the tie rods and the cage longerons, each with
    its own fast valve. The dog-leg leaves no straight line of sight from the burn through a port. SPECULATIVE function: gas puffed ahead
    of each pulse is ionised by its X-rays and swept up by the expanding charged debris, which shares momentum with it before loops L1-L4
    turn the mix into the exhaust."""
    q = v1_cfg(s)['h2_injection']; f = feed_cfg(s); g = ve.config(s)['geometry']; est = ve.stations(s)
    mid = (est['collar_fwd']+est['collar_aft'])/2; xf = mid+f['inlet_fwd_of_collar_m']; rin = g['collar_outer_radius_m']+f['inlet_standoff_m']
    R = q['manifold_r_m']; mx = q['manifold_x_m']; tube = q['manifold_tube_m']; out = []
    line_local = [(xf, -rin, 0.0), (mx, -rin, 0.0), (mx, -(R+tube), 0.0)]
    ports, pvalves = [], []
    tx, tr = q['port_tip']
    for az in q['port_az_deg']:
        a = math.radians(az)
        def P(xx, rr): return (xx, rr*math.cos(a), rr*math.sin(a))
        ports.append([P(mx, R), P(q['port_bend_x_m'], R), P(q['port_in_x_m'], tr), P(tx, tr)])
        pvalves.append(P(q['port_valve_x_m'], R))
    for pl in vc.placements(s):
        j = pl['n']
        out.append(dict(engine=j, species='hydrogen', line_name=f'FPS_N{j}_H2_Injection_Line', line_local=line_local,
                        line=_engine_poly(pl, line_local), line_radius=q['line_radius_m'],
                        valve_name=f'FPS_N{j}_H2_Control_Valve', valve=vc.to_ship(pl, (mx, -(rin+R+tube)/2, 0.0)), valve_size=q['valve_size_m'], axes=pl['axes'],
                        manifold_name=f'FPS_N{j}_H2_Manifold', manifold=dict(x=mx, R=R, tube=tube), placement=pl,
                        ports_name=f'FPS_N{j}_H2_Injectors', ports=[_engine_poly(pl, p) for p in ports], ports_local=ports, port_radius=q['port_radius_m'],
                        port_valves=[vc.to_ship(pl, p) for p in pvalves], port_valve_m=q['port_valve_m'], interface=f'IF_FPS_H2_INJECT_N{j}'))
    return out


def pipe_spec(s):
    """The line classes: bore from the per-line mass flow at the class velocity, wall from Barlow (t = p D / 2 S E) plus a 1 mm allowance,
    with the allowable stress of 316L at the class temperature (PROTOTYPE 140 MPa, weld efficiency 0.85, 4x the design pressure for
    surge and cool-down). Gas density from the ideal gas law. The drawn line radius is the vacuum jacket's outer radius."""
    f = flows(s); rho_l = fst.cfg(s)['density_kg_m3']; out = []
    M = {'hydrogen': 2.016e-3, 'deuterium': 4.028e-3, 'helium-3': 3.016e-3}
    per_line = {'LH2-TRUNK': f['hydrogen']['kg_s']/2, 'LD2-TRUNK': f['deuterium']['kg_s'], 'LHE3-TRUNK': f['helium-3']['kg_s'],
                'GH2-INJECT': f['hydrogen']['per_engine_kg_s'], 'TARGET-FEED': f['deuterium']['per_engine_kg_s']+f['helium-3']['per_engine_kg_s']}
    for c in v1_cfg(s)['pipe']:
        sp = c['species']
        rho = c['p_MPa']*1e6*M[sp]/(8.314462618*c['T_K']) if c['phase'] == 'gas' else (rho_l[fst.INV_KEY[sp]] if c['phase'] == 'liquid' else 1.0)
        kg = per_line[c['id']]
        bore = bore_m(kg, rho, c['v_m_s']) if c['phase'] in ('gas', 'liquid') else 0.025
        p = 4*c['p_MPa']*1e6; wall = p*bore/(2*140e6*0.85)+1e-3
        out.append(dict(c, kg_s=kg, density_kg_m3=rho, bore_mm=bore*1e3, wall_mm=wall*1e3, od_mm=(bore+2*wall)*1e3,
                        note='TARGET-FEED carries finished targets (bore set by the capsule, PROTOTYPE 25 mm), not a fluid' if c['phase'].startswith('solid') else ''))
    return out


def energy_ledger(s):
    """Where the fusion power goes at the operating point, against B01 (directed_efficiency is the canon jet share), with the reaction
    products' split from the engine workstream's burn model (vertex_radiation.sources) and the engine's own pulse point (vertex_magnet.plasma).
    Shares of the fusion power; nothing here is tuned to agree."""
    import vertex_magnet as vm
    import vertex_radiation as vr
    f = flows(s); P = f['total']['fusion_W']; J = f['total']['jet_W']
    src = vr.sources(s)['cases']; pz = vm.plasma(s); n = vc.config(s)['engine_count']
    cases = {}
    for k, c in src.items():
        led = c['ledger']; Y = led['total_J']
        sh = dict(photon=led['photon_J']/Y, neutron=led['neutron_J']/Y, gamma=led['gamma_J']/Y, charged=led['charged_J']/Y)
        cases[k] = dict(shares=sh, jet_canon=J/P, charged_minus_jet=sh['charged']-J/P,
                        W=dict(photon=sh['photon']*P, neutron=sh['neutron']*P, charged_not_jet=(sh['charged']-J/P)*P), closes=sh['charged'] >= J/P)
    eng = dict(fusion_W=pz['yield_J']*pz['pulse_Hz'], jet_W=pz['energy_J']['design']*pz['pulse_Hz'], exhaust_kg_s=pz['mass_kg']*pz['pulse_Hz'],
               ve_m_s=pz['exhaust_m_s'], pulse_Hz=pz['pulse_Hz'], pulse_mass_mg=pz['mass_kg']*1e6)
    cluster = dict(fusion_W=n*eng['fusion_W'], jet_W=n*eng['jet_W'], exhaust_kg_s=n*eng['exhaust_kg_s'], thrust_N=n*eng['exhaust_kg_s']*eng['ve_m_s'])
    fps = dict(fusion_W=P, jet_W=J, fed_kg_s=f['total']['fuel_fed_kg_s'], fuel_per_engine_kg_s=f['deuterium']['per_engine_kg_s']+f['helium-3']['per_engine_kg_s'],
               exhaust_kg_s=f['total']['kg_s'], thrust_N=f['total']['thrust_N'])
    return dict(cases=cases, engine_point=eng, cluster_point=cluster, ship_point=fps,
                ratio=dict(fusion=P/cluster['fusion_W'], jet=J/cluster['jet_W'], exhaust_mass=fps['exhaust_kg_s']/cluster['exhaust_kg_s'],
                           thrust=fps['thrust_N']/cluster['thrust_N']),
                verdict=('OPEN: the engine point (pulse yield x rate x 4) carries 1/{:.1f} of the ship operating point; the 38 vs 185 g/s gap is that '
                         'factor, not a feed shortfall. Neither side is changed here.').format(P/cluster['fusion_W']))


def v1_polylines(s):
    """V1 pipes as (name, species, points, radius): the transfer chain (exterior leg, feedthrough, interior leg, inlet nozzle), the H2
    crossover, each engine's target feed and H2 injection line."""
    if not v1(s):
        return []
    out = [(ft['name'], ft['species'], ft['bridge'], ft['line_radius']) for ft in feedthroughs(s)]
    out += [(ti['name'], ti['species'], ti['nozzle'], ti['radius']) for ti in tank_inlets(s)]
    c = h2_crossover(s); out.append((c['name'], 'hydrogen', c['points'], c['radius']))
    out += [(t['name'], 'target', t['points'], t['radius']) for t in target_feeds(s)]
    out += [(h['line_name'], 'hydrogen', h['line'], h['line_radius']) for h in h2_injection(s)]
    if v11(s):
        out += [(l['name'], l['species'], l['points'], l['radius']) for l in target_fabrication(s)['lines']]
    return out


def v11_interfaces(s):
    if not v11(s):
        return []
    tf = target_fabrication(s); eq = {e['name']: e for e in tf['equipment']}; f = eq['FPS_Fab_Fill_Station']
    x = (f['a'][0]+f['b'][0])/2; xf = next(l for l in tf['lines'] if l['name'] == 'FPS_Target_Transfer_Bay')['points'][-1]
    return [dict(name='IF_FPS_FAB_FILL', at=(x, 0.0, f['radius']), species='target',
                 note='Target shell fill and cryogenic layering (SPECULATIVE): the D-He-3 target recipe, shell material, layer uniformity and throughput (~5.7 kHz per engine) are not designed'),
            dict(name='IF_FPS_FAB_TRUNK', at=xf, species='target', note='Cold-target handoff from the fabrication line to the cluster target trunk (CL_Trunk_TARGET_FEED) on the bay aft face')]


def v1_interfaces(s):
    if not v1(s):
        return []
    out = [dict(name=ft['interface'], at=ft['at'], species=ft['species'], note=f"Hull feedthrough of {ft['trunk']}: jacketed sleeve with bellows, flanged both sides (PROTOTYPE)")
           for ft in feedthroughs(s)]
    out += [dict(name=t['interface'], at=t['points'][-1], species='target',
                 note=f"N{t['engine']} target feed into the target magazine (engine side: magazine, transfer, launcher). CANDIDATE for the engine workstream")
            for t in target_feeds(s)]
    out += [dict(name=h['interface'], at=h['ports'][0][-1], species='hydrogen',
                 note=f"N{h['engine']} injector tips on the burn face: H2 gas puff ahead of each pulse; energy coupling SPECULATIVE (docs/FUEL_SYSTEM.md 'Energy')")
            for h in h2_injection(s)]
    return out


# ---------- V1.1: the missing components (owner brief 2026-11-19 09:23Z) ------------------------------------------------------------

def v11_cfg(s):
    return cfg(s).get('v11', {})


def v11(s):
    return v1(s) and bool(v11_cfg(s))


def _ring_pts(center, axis, R, n=16):
    """Closed polyline of a ring of radius R round `axis` (unit) at `center`."""
    ax = axis; ref = (1.0, 0.0, 0.0) if abs(ax[0]) < 0.9 else (0.0, 1.0, 0.0)
    u = (ax[1]*ref[2]-ax[2]*ref[1], ax[2]*ref[0]-ax[0]*ref[2], ax[0]*ref[1]-ax[1]*ref[0]); L = math.sqrt(sum(c*c for c in u)); u = tuple(c/L for c in u)
    v = (ax[1]*u[2]-ax[2]*u[1], ax[2]*u[0]-ax[0]*u[2], ax[0]*u[1]-ax[1]*u[0])
    return [tuple(center[i]+R*(math.cos(2*math.pi*k/n)*u[i]+math.sin(2*math.pi*k/n)*v[i]) for i in range(3)) for k in range(n+1)]


def _at_dist(pts, d):
    """Point and unit direction at distance d along a polyline (negative d: from the end)."""
    segs = list(zip(pts, pts[1:])) if d >= 0 else [(b, a) for a, b in reversed(list(zip(pts, pts[1:])))]
    d = abs(d)
    for a, b in segs:
        L = math.dist(a, b)
        if d <= L or (a, b) == segs[-1]:
            u = tuple((b[i]-a[i])/L for i in range(3)); t = min(d, L)
            return tuple(a[i]+u[i]*t for i in range(3)), u
        d -= L


def bay_frame(s):
    st = vc.stations(s); c = vc.config(s)
    return dict(x0=st['bay']+st['bay_length']/2, x1=st['bay']-st['bay_length']/2, r_core=c['bay_core_radius_m'], r_out=st['bay_radius'])


def target_fabrication(s):
    """Target fabrication in the cluster bay core (SPECULATIVE process, PROTOTYPE layout), fore to aft on the axis: the D2 and He-3 legs
    from the bay fore face radially in to their receiver dewars, a purifier/blend unit, the shell fill and cryogenic layering station, an
    inspection station with its reject chute and a buffer magazine; the transfer leg takes cold targets to CL_Trunk_TARGET_FEED on the bay
    aft face. Equipment as (name, shape, geometry, function); lines as (name, species, points, radius)."""
    q = v11_cfg(s); b = bay_frame(s); x0 = b['x0']; eq = []; lines = []
    feeds = {ln['species']: ln for ln in feed_lines(s) if ln['species'] != 'hydrogen'}
    rc = q['fab_receiver']
    for sp in ('deuterium', 'helium-3'):
        end = feeds[sp]['points'][-1]; a = math.atan2(end[2], end[1]); tg = TAG[sp]
        xr0, xr1 = x0-rc['x_m'], x0-rc['x_m']-rc['length_m']; xm = (xr0+xr1)/2
        eq.append(dict(name=f'FPS_Fab_Receiver_{tg}', species=sp, shape='cyl', a=dm.radial(xr0, rc['r_m'], a), b=dm.radial(xr1, rc['r_m'], a), radius=rc['radius_m'],
                       function=f'{tg} receiver dewar: buffers the metered {tg} feed at the bay inlet (boil-off back to the cryoplant)'))
        lines.append(dict(name=f'FPS_Bay_Target_Fabrication_{tg}', species=sp, radius=q['fab_leg']['radius_m'],
                          points=[end, (x0-q['fab_leg']['x_in_m'], end[1], end[2]), dm.radial(x0-q['fab_leg']['x_in_m'], rc['r_m']+rc['radius_m'], a)]))
        lines.append(dict(name=f'FPS_Fab_Link_{tg}', species=sp, radius=q['fab_link_radius_m'],
                          points=[dm.radial(xr1, rc['r_m'], a), dm.radial(xr1-0.1, 0.35, a)]))
    def box(name, x_m, size, fn, sp='target'):
        eq.append(dict(name=name, species=sp, shape='box', at=(x0-x_m, 0.0, 0.0), size=tuple(size), function=fn))
    def cyl(name, x_m, r, L, fn, sp='target'):
        eq.append(dict(name=name, species=sp, shape='cyl', a=(x0-x_m+L/2, 0.0, 0.0), b=(x0-x_m-L/2, 0.0, 0.0), radius=r, function=fn))
    bl, fi, ins, bu = q['fab_blend'], q['fab_fill'], q['fab_inspect'], q['fab_buffer']
    box('FPS_Fab_Blend_Unit', bl['x_m'], bl['size_m'], 'purifier and blend unit: removes He-4, H and tritium traces, mixes D and He-3 1:1 by moles (SPECULATIVE target recipe)', 'deuterium')
    cyl('FPS_Fab_Fill_Station', fi['x_m'], fi['radius_m'], fi['length_m'], 'shell fill and cryogenic layering station: fills the target shells with the D/He-3 blend and freezes a uniform layer (SPECULATIVE)')
    box('FPS_Fab_Inspection', ins['x_m'], ins['size_m'], 'target inspection (optical and X-ray layer metrology), reject chute back to recovery')
    cyl('FPS_Fab_Buffer_Magazine', bu['x_m'], bu['radius_m'], bu['length_m'], 'buffer magazine: cold finished targets awaiting transfer to the engines (one burn-minute of stock, PROTOTYPE)')
    # the conveyor through the line: blend aft face -> fill -> inspection -> buffer (on the axis)
    ends = [(x0-bl['x_m']-bl['size_m'][0]/2, x0-fi['x_m']+fi['length_m']/2), (x0-fi['x_m']-fi['length_m']/2, x0-ins['x_m']+ins['size_m'][0]/2),
            (x0-ins['x_m']-ins['size_m'][0]/2, x0-bu['x_m']+bu['length_m']/2)]
    for k, (xa, xb) in enumerate(ends, 1):
        lines.append(dict(name=f'FPS_Fab_Conveyor_{k}', species='target', radius=q['fab_link_radius_m'], points=[(xa+0.05, 0.0, 0.0), (xb-0.05, 0.0, 0.0)]))
    t = q['transfer']; a = math.radians(t['trunk_az_deg']); xbuf = x0-bu['x_m']-bu['length_m']/2
    lines.append(dict(name='FPS_Target_Transfer_Bay', species='target', radius=t['radius_m'],
                      points=[dm.radial(xbuf+0.05, 0.4, a), dm.radial(xbuf-0.3, t['trunk_r_m'], a), dm.radial(b['x1'], t['trunk_r_m'], a)]))
    return dict(equipment=eq, lines=lines, frame=b)


def shield_galleries(s):
    """Per engine: a sleeve round every injector port where it crosses the thrust collar and the shadow shield (engine frame x ranges in
    v11.gallery); the port's dog-leg inside the shield leaves no straight streaming path. Ship-frame tube segments."""
    g = v11_cfg(s)['gallery']; q = v1_cfg(s)['h2_injection']; R = q['manifold_r_m']; out = []
    for pl in vc.placements(s):
        segs = []
        for az in q['port_az_deg']:
            for xa, xb in (g['collar'], g['shield']):
                segs.append(_engine_poly(pl, [ve.pol(xa, R, az), ve.pol(xb, R, az)]))
        out.append(dict(name=f"FPS_N{pl['n']}_Shield_Galleries", engine=pl['n'], segments=segs, radius=g['radius_m']))
    return out


def cryo_supports(s):
    """Clamps (ring + standoff strut) on the engine target feeds' inner run to the cartridge shell. Ship frame."""
    q = v11_cfg(s); cl = q['clamp']; out = []
    feeds = target_feeds(s); r_shell = ve.config(s)['geometry']['cartridge_radius_m']
    for t in feeds:
        pl = vc.placements(s)[t['engine']-1]; z = t['local'][2][2]; rin = -t['local'][2][1]
        for x in q['target_feed_clamps_x']:
            c = (x, -rin, z); rr = math.hypot(rin, z); u = (0.0, -rin/rr, z/rr)
            a = tuple(c[i]-u[i]*(t['radius']+cl['ring_gap_m']) for i in range(3)); b = tuple(c[i]*r_shell/rr if i else c[i] for i in range(3))
            ax = vc.to_ship(pl, (1, 0, 0)); o = vc.to_ship(pl, (0, 0, 0)); ax = tuple(ax[i]-o[i] for i in range(3))
            out.append(dict(name=f"FPS_N{t['engine']}_Target_Clamp", engine=t['engine'], ring=_ring_pts(vc.to_ship(pl, c), ax, t['radius']+cl['ring_gap_m']),
                            strut=[vc.to_ship(pl, a), vc.to_ship(pl, b)]))
    return dict(clamps=out, ring_tube=cl['ring_tube_m'], strut_radius=cl['strut_radius_m'])


def thermal_intercepts(s):
    """Cold-strap collars where a cryogenic line crosses a warm/cold boundary: each V0 feed line at its shadow-shield sleeve, each hull
    feedthrough's interior end, the D2/He-3 legs at the bay fore face, each engine's target feed and H2 injection line where they leave
    the panel side. Ship frame rings (center, axis, ring radius)."""
    q = v11_cfg(s)['intercept']; out = []
    for ln in feed_lines(s):
        p = ln['shield_point']; seg = min(zip(ln['points'], ln['points'][1:]), key=lambda ab: _seg_d(p, *ab)); u = _dir3(*seg)
        out.append(dict(where=f"{ln['name']} at the shield sleeve", center=p, axis=u, R=ln['radius']+q['gap_m']))
    for ft in feedthroughs(s):
        out.append(dict(where=f"{ft['name']} interior end", center=ft['b'], axis=ft['axis'], R=ft['line_radius']+q['gap_m']))
    for ln in target_fabrication(s)['lines']:
        if ln['name'].startswith('FPS_Bay_Target_Fabrication'):
            p, u = _at_dist(ln['points'], 0.15); out.append(dict(where=f"{ln['name']} at the bay fore face", center=p, axis=u, R=ln['radius']+q['gap_m']))
    for t in target_feeds(s):
        # on the radial-in leg, 0.3 m inside the turn: at the panel's own radius the collar would stand proud of the removal passage
        d = math.dist(t['local'][0], t['local'][1])+0.3
        p, u = _at_dist(t['points'], d); out.append(dict(where=f"{t['name']} inside the panel turn", center=p, axis=u, R=t['radius']+q['gap_m'], engine=t['engine']))
    for h in h2_injection(s):
        d = math.dist(h['line_local'][0], h['line_local'][1])+0.3          # on the radial-in leg, inside the removal passage
        p, u = _at_dist(h['line'], d); out.append(dict(where=f"{h['line_name']} inside the inlet turn", center=p, axis=u, R=h['line_radius']+q['gap_m'], engine=h['engine']))
    return dict(rings=out, tube=q['tube_m'])


def _dir3(a, b):
    L = math.dist(a, b); return tuple((b[i]-a[i])/L for i in range(3))


def pmds(s):
    """Propellant management devices for transfer during coast (no settling thrust): in every run tank and farm vessel, gallery vanes
    along the barrel (surface tension keeps a liquid path along them to the outlet) and a sponge of radial plates at the aft outlet.
    Oriented boxes (center, size along X/radial/tangential, radial unit, tangential unit); inset from the inner wall."""
    q = v11_cfg(s)['pmd']; out = []
    def plates(name, cx, cy, cz, xa, xb, ra, rb, n, phase):
        L = []
        for k in range(n):
            a = math.radians(phase+360*k/n); ur = (0.0, math.cos(a), math.sin(a)); ut = (0.0, -math.sin(a), math.cos(a)); rm = (ra+rb)/2
            L.append(dict(center=((xa+xb)/2, cy+ur[1]*rm, cz+ur[2]*rm), size=(abs(xb-xa), rb-ra, q['vane_t_m']), ur=ur, ut=ut))
        return L
    for t in fst.run_tanks(s):
        v = plates('', 0, t['y'], t['z'], t['x0']+0.15, t['x1']-0.15, *q['run_vane'], q['vanes'], q['vane_phase_deg'])
        sp = plates('', 0, t['y'], t['z'], t['x0']+q['sponge_x0_m'][0], t['x0']+q['sponge_x0_m'][0]+q['run_sponge_l_m'], 0.02, q['run_sponge_r_m'], q['sponge_plates'], 22.5)
        out.append(dict(name=f"FPS_PMD_{t['name'].split('_')[-1]}", tank=t['name'], species=None, vanes=v, sponge=sp))
    for t in fst.tanks(s):
        h = t['head']+(t['a_env']-t['a']); ya, yf = t['x0']+h, t['x1']-h
        v = plates('', 0, t['y'], t['z'], ya+0.2, yf-0.2, t['a']-q['farm_vane_inset_m'][0], t['a']-q['farm_vane_inset_m'][1], q['vanes'], q['vane_phase_deg'])
        x0 = t['x0']+q['sponge_x0_m'][1]
        sp = plates('', 0, t['y'], t['z'], x0, x0+q['farm_sponge_l_m'], 0.02, q['farm_sponge_share']*t['a'], q['sponge_plates'], 22.5)
        out.append(dict(name=f"FPS_PMD_{t['id']}", tank=t['name'], species=t['species'], vanes=v, sponge=sp))
    return out


def equipment_detail(s):
    """Pump, regulator and conditioning sub-blockouts on each V0 feed line: the boost pump's motor beside it, the conditioner's heat
    exchanger shell beside it, a pressure regulator and a flow-meter spool on the line just aft of the conditioning unit. Per line:
    cylinders (a, b, radius) and boxes (center, size, radial axis, tangential axis)."""
    q = v11_cfg(s)['detail']; by = {}
    lines = {l['name']: l for l in feed_lines(s)}
    for e in equipment(s):
        L = by.setdefault(e['line'], dict(line=e['line'], species=e['species'], cyl=[], box=[]))
        x, y, z = e['at']; r = math.hypot(y, z); ur = (0.0, y/r, z/r); ut = (0.0, -z/r, y/r)
        if e['kind'] == 'fps_pump':
            off = e['radius']+q['motor_radius_m']+0.05; c = tuple(e['at'][i]+ut[i]*off for i in range(3))
            L['cyl'].append(dict(what='pump motor', a=(c[0]+q['motor_length_m']/2, c[1], c[2]), b=(c[0]-q['motor_length_m']/2, c[1], c[2]), radius=q['motor_radius_m']))
        if e['kind'] == 'fps_conditioner':
            off = e['size'][2]/2+q['hx_radius_m']+0.05; c = tuple(e['at'][i]+ut[i]*off for i in range(3)); Lx = e['size'][0]*0.8
            L['cyl'].append(dict(what='heat-exchanger shell', a=(c[0]+Lx/2, c[1], c[2]), b=(c[0]-Lx/2, c[1], c[2]), radius=q['hx_radius_m']))
            xa = x-e['size'][0]/2-0.35
            p, u = _point_on_line(lines[e['line']]['points'], xa)
            L['box'].append(dict(what='pressure regulator', center=p, size=(q['regulator_m'],)*3, ur=ur, ut=ut))
            p2, u2 = _point_on_line(lines[e['line']]['points'], xa-0.45)
            L['cyl'].append(dict(what='flow-meter spool', a=tuple(p2[i]+u2[i]*0.2 for i in range(3)), b=tuple(p2[i]-u2[i]*0.2 for i in range(3)), radius=q['spool_radius_m']))
    return [dict(name=f"FPS_Equipment_Detail_{k.split('_', 2)[2]}", **v) for k, v in by.items()]


def _point_on_line(pts, x):
    """The point of a polyline at station x (first segment spanning x) and its direction."""
    for a, b in zip(pts, pts[1:]):
        if min(a[0], b[0])-1e-9 <= x <= max(a[0], b[0])+1e-9 and abs(a[0]-b[0]) > 1e-9:
            t = (x-a[0])/(b[0]-a[0]); return tuple(a[i]+(b[i]-a[i])*t for i in range(3)), _dir3(a, b)
    raise ValueError(x)


def removal_check(s):
    """Engine removal (V1.1): vertex_cluster.removal_sweep with the FPS parts every engine carries (engine frame)."""
    ex = []
    for t in target_feeds(s):
        if t['engine'] == 1:
            ex.append((t['name'], t['local'], t['radius']))
    h = h2_injection(s)[0]; ex.append((h['line_name'], h['line_local'], h['line_radius']))
    q = v1_cfg(s)['h2_injection']
    ex.append(('FPS_N1_H2_Manifold', [ve.pol(q['manifold_x_m'], q['manifold_r_m'], 360*k/48) for k in range(49)], q['manifold_tube_m']))
    for k, pts in enumerate(h['ports_local']):
        ex.append((f"{h['ports_name']}_{k+1}", pts, h['port_radius']))
    # V1.1 parts the engine carries (FPS_N1_Supports): the target-feed clamps and the cold-strap collars on its lines
    pl = vc.placements(s)[0]; X, Y, Z = pl['axes']; o = pl['origin']
    loc = lambda p: tuple(sum((p[i]-o[i])*A[i] for i in range(3)) for A in (X, Y, Z))
    cs = cryo_supports(s)
    for k, c in enumerate(q for q in cs['clamps'] if q['engine'] == 1):
        ex.append((f'FPS_N1_Target_Clamp_{k+1}', [loc(p) for p in c['ring']], cs['ring_tube']))
        ex.append((f'FPS_N1_Target_Clamp_Strut_{k+1}', [loc(p) for p in c['strut']], cs['strut_radius']))
    ti = thermal_intercepts(s)
    for k, r in enumerate(q for q in ti['rings'] if q.get('engine') == 1):
        ex.append((f'FPS_N1_Intercept_{k+1}', [loc(p) for p in _ring_pts(r['center'], r['axis'], r['R'])], ti['tube']))
    return vc.removal_sweep(s, ex)

# FPS V1.1 performance reconciliation (one shared energy account; nothing is tuned to agree)
def rate_reconciliation(s):
    """Why the V1 fuel-rate gap read ~4.9x while the power gap is ~7.3x, from one energy and mass account of the ship operating point
    (flows) and the engine's pulse point (vertex_magnet.plasma).

    The ship rates in flows() are REACTED fuel (fed = reacted / burnup); the engine's pulse mass is not a fuel mass but the mass that
    carries the pulse's jet energy at the exhaust speed (m = 2 E_jet / v_e^2). V1 compared ship reacted D+He-3 per engine with engine
    exhaust mass per engine, two different quantities. Like for like:
      power   : ship fusion / (n * yield * rate)
      exhaust : ship exhaust / (n * pulse mass * rate) = power gap * (ship jet share / engine jet share)
      fuel    : ship reacted fuel / (n * reacted fuel per pulse * rate), where the engine's reacted fuel per pulse follows from its yield at
                the same specific fusion energy
    The fuel and exhaust gaps equal the power gap within the jet-share difference: the only real mismatch is the engine's fusion power
    (yield x rate). 4.9 = exhaust gap / (ship exhaust per reacted fuel)."""
    import vertex_magnet as vm
    f = flows(s); pz = vm.plasma(s); n = vc.config(s)['engine_count']; t = f['total']
    P = t['fusion_W']; J = t['jet_W']; reacted = f['deuterium']['kg_s']+f['helium-3']['kg_s']; exhaust = t['kg_s']
    e_spec_ship = P/reacted                                                   # J per kg reacted (D-He3 full burn of what reacts)
    Y, rate, m_pulse = pz['yield_J'], pz['pulse_Hz'], pz['mass_kg']
    eng_P = n*Y*rate; eng_J = n*pz['energy_J']['design']*rate; eng_exhaust = n*m_pulse*rate
    m_react_pulse = Y/e_spec_ship                                             # reacted fuel per pulse at the ship's specific energy
    import operating_point as op
    m_fed_pulse = m_react_pulse/op.p(s)['burnup']
    gaps = dict(power=P/eng_P, jet=J/eng_J, exhaust=exhaust/eng_exhaust, fuel_like_for_like=reacted/(n*m_react_pulse*rate),
                v1_quoted=(reacted/n)/(m_pulse*rate))
    reg = v1_cfg(s)['energy']['regime']; ch = energy_ledger(s)['cases'][reg]['shares']['charged']
    current = dict(regime=reg, charged_share=ch, jet_ceiling_W=ch*P, fusion_needed_W=J/ch,
                   note=(f'Current result: {reg} puts {ch:.1%} of the fusion power in charged debris, the ceiling of any directed jet before '
                         f'conversion losses. The 80 % B01 jet share (and the engine model\'s 78 %) is not claimed: no conversion mechanism above '
                         f'the charged share is shown. At {reg} the jet the ship needs takes {J/ch/1e12:.0f} TW of fusion, not {P/1e12:.0f} TW.'))
    return dict(
        current=current,
        ship=dict(fusion_W=P, jet_W=J, jet_share=J/P, reacted_kg_s=reacted, fed_kg_s=t['fuel_fed_kg_s'], exhaust_kg_s=exhaust,
                  exhaust_per_reacted=exhaust/reacted, specific_energy_J_kg=e_spec_ship),
        engine=dict(yield_J=Y, pulse_Hz=rate, jet_share=pz['energy_J']['design']/Y, pulse_exhaust_mg=m_pulse*1e6,
                    pulse_reacted_mg=m_react_pulse*1e6, pulse_fed_mg=m_fed_pulse*1e6, exhaust_per_reacted=m_pulse/m_react_pulse,
                    yield_per_exhaust_J_kg=Y/m_pulse),
        gaps=gaps,
        closing=dict(rate_Hz_at_yield=rate*gaps['power'], yield_J_at_rate=Y*gaps['power'], engines_at_point=n*gaps['power']),
        verdict=('One gap, not two: the engine point gives 1/{p:.2f} of the ship fusion power. The V1 4.9x set ship REACTED D+He-3 ({r:.0f} g/s '
                 'per engine) against the engine pulse EXHAUST mass ({e:.1f} g/s per engine); like for like (the engine reacted fuel per pulse at the same D-He-3 specific energy, {sp:.2e} J/kg) the fuel gap is the power gap, '
                 '{fl:.2f}x, and the exhaust gap {ex:.2f}x (jet shares {js:.3f} ship vs {je:.3f} engine). OPEN for the engine workstream: yield x rate.').format(
                     p=gaps['power'], r=reacted/n*1e3, e=m_pulse*rate*1e3, fl=gaps['fuel_like_for_like'], ex=gaps['exhaust'], js=J/P, sp=e_spec_ship,
                     je=pz['energy_J']['design']/Y))


# ---------- fit screen --------------------------------------------------------------------------------------------------------------

def _seg_d(p, a, b):
    ab = [b[i]-a[i] for i in range(3)]; ap = [p[i]-a[i] for i in range(3)]; L = sum(x*x for x in ab)
    t = 0.0 if L == 0 else max(0.0, min(1.0, sum(ab[i]*ap[i] for i in range(3))/L))
    return math.dist(p, [a[i]+t*ab[i] for i in range(3)])


def polylines(s):
    """Every FPS pipe as (name, species, points, radius)."""
    out = [(l['name'], l['species'], l['points'], l['radius']) for l in feed_lines(s)]
    out += [(b['name'], 'hydrogen', b['points'], b['radius']) for b in branches(s)]
    out += [(f"FPS_Vent_{r['tank'][-2:]}", r['species'], r['vent'], r['radius']) for r in relief(s)]
    out += [(l['name'], l['species'], l['points'], l['radius']) for l in refuel(s)['lines']]
    out += [(p['name']+'_Line', 'helium', p['line'], feed_cfg(s)['purge']['line_radius_m']) for p in purge(s)]
    return out+v1_polylines(s)


def check(s):
    """First-order fit screen (the built geometry gets the mesh screen in work/fuel-propellant/probe.py): every species has a complete
    path, the H2 lines clear the cluster bay and pass inside the thrust ring, the branches end on their panels, lines of different
    species never touch, and the fuel lines stay inside the bay radius."""
    f = feed_cfg(s); st = stations(s); fails = []
    lines = feed_lines(s); sp = {l['species'] for l in lines}
    if sp != set(SPECIES):
        fails.append(f'species with a feed line: {sorted(sp)}')
    for l in lines:
        for a, b in zip(l['points'], l['points'][1:]):
            for k in range(11):
                p = [a[i]+(b[i]-a[i])*k/10 for i in range(3)]; r = math.hypot(p[1], p[2])
                if l['species'] == 'hydrogen' and st['bay_aft'] <= p[0] <= st['bay_fwd'] and r-l['radius'] < st['bay_r']+0.3:
                    fails.append(f"{l['name']} inside the bay clearance at X {p[0]:.2f}")
                if l['species'] == 'hydrogen' and abs(p[0]-dm.stations(s)['ring']) < 1.25 and r+l['radius'] > 4.0:
                    fails.append(f"{l['name']} meets the thrust ring at X {p[0]:.2f} r {r:.2f}")
                if r+l['radius'] > 5.95:
                    fails.append(f"{l['name']} outside the hull at X {p[0]:.2f}")
    pl = polylines(s); gap = 1e9
    for i, (n1, s1, p1, r1) in enumerate(pl):
        for n2, s2, p2, r2 in pl[i+1:]:
            if s1 == s2:
                continue
            for a, b in zip(p2, p2[1:]):
                for q in p1:
                    d = _seg_d(q, a, b)-r1-r2; gap = min(gap, d)
                    if d < 0.05:
                        fails.append(f'{n1} touches {n2}')
    return dict(result='PASS' if not fails else 'FAIL', fails=sorted(set(fails))[:40], min_species_gap_m=gap)


def report(s):
    f = flows(s); rho = fst.cfg(s)['density_kg_m3']
    return dict(id=cfg(s)['id'], version=cfg(s)['version'], baseline=cfg(s)['baseline'], status=cfg(s)['status'], flows=f,
                bores_mm={sp: bore_m(f[sp]['per_engine_kg_s'], rho[fst.INV_KEY[sp]])*1e3 for sp in SPECIES},
                regimes=regimes(s), heads=heads(s), conditioning=conditioning(s), fuel_cycles=fuel_cycles(s), feedstock=feedstock(s),
                reaction_masses=reaction_masses(s), interfaces=interfaces(s), check=check(s) if active(s) else 'SKIPPED (Fiji representation)')


# ---------- browser payload ---------------------------------------------------------------------------------------------------------

def _rt(p):
    """Blender (x, y, z) to the viewer's runtime axes (x, z, -y), rounded to a millimetre."""
    return [round(p[0], 3), round(p[2], 3), round(-p[1], 3)]


def objects(s):
    """Every FPS object the generator builds, by name: species ('helium' for the purge, 'service' for the panel and supports) and kind."""
    out = {l['name']: dict(species=l['species'], kind='fps_feed_line') for l in feed_lines(s)}
    out.update({e['name']: dict(species=e['species'], kind=e['kind']) for e in equipment(s)})
    out[header(s)['name']] = dict(species='hydrogen', kind='fps_feed_line')
    out.update({b['name']: dict(species='hydrogen', kind='fps_feed_line') for b in branches(s)})
    out.update({q['name']: dict(species=q['species'], kind='fps_sensor') for q in sensors(s)})
    for r in relief(s):
        t = r['tank'][-2:]
        out[f'FPS_Relief_Valve_{t}'] = dict(species=r['species'], kind='fps_valve')
        out[f'FPS_Vent_{t}'] = dict(species=r['species'], kind='fps_vent')
    for p in purge(s):
        out[p['name']] = dict(species='helium', kind='fps_purge'); out[p['name']+'_Line'] = dict(species='helium', kind='fps_purge')
    rf = refuel(s); out[rf['panel']['name']] = dict(species='service', kind='fps_refuel')
    for l in rf['lines']:
        out[l['name']] = dict(species=l['species'], kind='fps_refuel')
    if v1(s):
        out.update(v1_objects(s))
    for n, o in out.items():
        o.setdefault('group', _group(n))
    return out


def v1_objects(s):
    """V1 FPS objects, the farm hardware the chain runs through (vessels, ring mains, outlets and their valves, transfer trunks) and the
    cluster's target-feed lines, by name: species, kind, group and owner (the viewer's views and component list)."""
    out = {}
    for ft in feedthroughs(s):
        out[ft['name']] = dict(species=ft['species'], kind='fps_feedthrough'); out[ft['name']+'_Line'] = dict(species=ft['species'], kind='fps_feedthrough')
    for ti in tank_inlets(s):
        out[ti['name']] = dict(species=ti['species'], kind='fps_tank_inlet'); out[ti['name']+'_Valve'] = dict(species=ti['species'], kind='fps_valve')
        for c in ti['checks']:
            out[f"FPS_Check_Valve_{c['tag']}"] = dict(species=ti['species'], kind='fps_valve')
    out['FPS_H2_Crossover'] = dict(species='hydrogen', kind='fps_feed_line'); out['FPS_H2_Crossover_Valve'] = dict(species='hydrogen', kind='fps_valve')
    out['FPS_Farm_Flanges'] = dict(species='service', kind='fps_flange')
    for t in target_feeds(s):
        out[t['name']] = dict(species='target', kind='fps_target_feed', owner='ENGINE (candidate)')
    for h in h2_injection(s):
        j = h['engine']
        for n, k in ((h['line_name'], 'fps_feed_line'), (h['valve_name'], 'fps_valve'), (h['manifold_name'], 'fps_injector'), (h['ports_name'], 'fps_injector')):
            out[n] = dict(species='hydrogen', kind=k, owner='ENGINE (candidate)')
        out[f'FPS_N{j}_Instruments'] = dict(species='service', kind='fps_sensor', owner='ENGINE (candidate)')
        out[f'FPS_N{j}_Flanges'] = dict(species='service', kind='fps_flange', owner='ENGINE (candidate)')
    if v11(s):
        tf = target_fabrication(s)
        for e in tf['equipment']:
            out[e['name']] = dict(species=e['species'] if e['name'].startswith('FPS_Fab_Receiver') else 'target', kind='fps_fabrication')
        out['FPS_Fab_Links'] = dict(species='target', kind='fps_fabrication')
        for l in tf['lines']:
            if not l['name'].startswith(('FPS_Fab_Link', 'FPS_Fab_Conveyor')):
                out[l['name']] = dict(species=l['species'], kind='fps_fabrication' if l['name'].startswith('FPS_Bay') else 'fps_target_feed')
        for j in range(1, vc.config(s)['engine_count']+1):
            out[f'FPS_N{j}_Supports'] = dict(species='service', kind='fps_support', owner='ENGINE (candidate)')
        out['FPS_Thermal_Intercepts'] = dict(species='service', kind='fps_intercept')
        out['FPS_PMD_Run_Tanks'] = dict(species='service', kind='fps_pmd'); out['FPS_PMD_Farm'] = dict(species='service', kind='fps_pmd', owner='STORAGE')
        for d in equipment_detail(s):
            out[d['name']] = dict(species=d['species'], kind='fps_conditioner')
    for t in fst.tanks(s):
        out[t['name']] = dict(species=t['species'], kind='farm_vessel', owner='STORAGE')
    for m in fst.ring_mains(s):
        out[m['name']] = dict(species=m['species'], kind='farm_ring_main', owner='STORAGE')
    for o in fst.outlets(s):
        out[o['name']] = dict(species=o['species'], kind='farm_outlet', owner='STORAGE'); out[o['valve']['name']] = dict(species=o['species'], kind='fps_valve', owner='STORAGE')
    for l in fst.transfer_lines(s):
        out[l['name']] = dict(species=l['species'], kind='farm_transfer', owner='STORAGE')
    # the cluster's own target-feed lines are merged by category in the export (no node of their own): they carry dots, not tints
    return out


def _cluster_target_lines(s):
    return [p for p in vc.distribution(s) if p['name'] == 'CL_Trunk_TARGET_FEED' or (p['name'].startswith('CL_N') and p['name'].endswith('_Line_TARGET_FEED'))]


def _group(name):
    if name.startswith(('Fuel_Tank', 'Fuel_Ring', 'Fuel_Outlet', 'FPS_H2_Crossover', 'FPS_Refuel', 'FPS_PMD_Farm')):
        return 'farm'
    if name.startswith(('Fuel_Transfer', 'FPS_Feedthrough', 'FPS_Tank_Inlet')):
        return 'transfer'
    if name.startswith(('CL_', 'FPS_Bay', 'FPS_Fab', 'FPS_Target_Transfer')):
        return 'cluster'
    if name.startswith('FPS_N'):
        return 'engine'
    return 'aft'


def chain_lines(s):
    """The rest of the modeled topology the flows run on (V1): every farm outlet, ring main (a loop) and transfer trunk, the cluster's
    target-feed trunk and engine lines, each engine's injector ports, and the one CONCEPTUAL leg: through the cluster bay, where target
    fabrication is not modeled (modeled=False; the viewer draws it dashed and says so)."""
    L = []
    def add(name, sp, pts, r, loop=False, modeled=True):
        L.append(dict(name=name, species=sp, path=_path(name), radius=r, points=[_rt(q) for q in pts], group=_group(name), modeled=modeled, loop=loop))
    for o in fst.outlets(s):
        add(o['name'], o['species'], o['points'], o['radius'])
    for m in fst.ring_mains(s):
        add(m['name'], m['species'], [dm.radial(m['x'], m['r'], 2*math.pi*k/96) for k in range(97)], m['radius'], loop=True)
    for l in fst.transfer_lines(s):
        add(l['name'], l['species'], l['points'], l['radius'])
    tl = _cluster_target_lines(s); trunk = next(p for p in tl if p['name'] == 'CL_Trunk_TARGET_FEED')
    if v11(s):        # V1.1: the bay is modeled (legs -> receivers -> blend -> fill -> inspection -> buffer -> transfer to the trunk)
        for l in target_fabrication(s)['lines']:
            add(l['name'], l['species'], l['points'], l['radius'])
    else:
        for ln in feed_lines(s):
            if ln['species'] != 'hydrogen':
                a = ln['points'][-1]; b = trunk['points'][0]
                add(f"FPS_Bay_Target_Fabrication_{TAG[ln['species']]}", ln['species'], [a, ((a[0]+b[0])/2, a[1]/3, a[2]/3), b], 0.05, modeled=False)
    for p in tl:
        add(p['name'], 'target', p['points'], p['radius'])
    for h in h2_injection(s):
        for k, pts in enumerate(h['ports']):
            add(f"{h['ports_name']}_{k+1}", 'hydrogen', pts, h['port_radius'])
    return L


def open_ends(s):
    """Where a modeled flow stops at an unresolved interface: the bay's fuel inlets (target fabrication not modeled), each engine's
    magazine (engine side) and injector tips (the energy coupling is SPECULATIVE), and the refuelling receptacle (tanker standard OPEN)."""
    I = {i['name']: i for i in interfaces(s)}; out = []
    for n, i in I.items():
        if n.startswith(('IF_FPS_FAB_FILL',) if v11(s) else ('IF_FPS_FUEL_BAY_',)) or n.startswith(('IF_FPS_TARGET_N', 'IF_FPS_H2_INJECT_N', 'IF_FPS_REFUEL')):
            out.append(dict(name=n, at=i['at'], species=i['species'], note=i['note']))
    return out


def _energy_web(s):
    e = energy_ledger(s); reg = v1_cfg(s)['energy']['regime']; c = e['cases'][reg]
    return dict(regime=reg, shares=c['shares'], jet_canon=c['jet_canon'], closes=c['closes'], charged_minus_jet=c['charged_minus_jet'],
                cases={k: dict(photon=v['shares']['photon'], neutron=v['shares']['neutron'], charged=v['shares']['charged'], closes=v['closes']) for k, v in e['cases'].items()},
                fusion_TW=e['ship_point']['fusion_W']/1e12, jet_TW=e['ship_point']['jet_W']/1e12, cluster_fusion_TW=e['cluster_point']['fusion_W']/1e12,
                cluster_jet_TW=e['cluster_point']['jet_W']/1e12, engine_pulse_Hz=e['engine_point']['pulse_Hz'], engine_pulse_mg=e['engine_point']['pulse_mass_mg'],
                engine_kg_s=e['engine_point']['exhaust_kg_s'], ship_fuel_per_engine_kg_s=e['ship_point']['fuel_per_engine_kg_s'], ratio=e['ratio']['fusion'],
                verdict=e['verdict'],
                reconciliation=_rec_web(s) if v11(s) else None)


def _rec_web(s):
    r = rate_reconciliation(s)
    return dict(power_gap=r['gaps']['power'], exhaust_gap=r['gaps']['exhaust'], v1_quoted=r['gaps']['v1_quoted'], specific_energy_J_kg=r['ship']['specific_energy_J_kg'],
                pulse_reacted_mg=r['engine']['pulse_reacted_mg'], pulse_exhaust_mg=r['engine']['pulse_exhaust_mg'], charged_share=r['current']['charged_share'],
                fusion_needed_TW=r['current']['fusion_needed_W']/1e12, closing_rate_kHz=r['closing']['rate_Hz_at_yield']/1e3, verdict=r['verdict'], note=r['current']['note'])


def _path(name):
    for key, path in (('FPS_Refuel', 'refuel'), ('FPS_Purge', 'purge'), ('FPS_Vent', 'vent')):
        if name.startswith(key):
            return path
    return 'h2' if '_H2' in name else 'fuel'


def web(s):
    """The Explore Ship Fuel panel's data: every pipe as a runtime polyline with its species and flow path, the operating states with the
    flows, thrust and exhaust velocity each implies (CONCEPTUAL: fractions of the operating point, jet power in proportion to the fuel
    fraction), the throttle regimes, and the headline numbers. The viewer draws and animates these; it computes no spacecraft facts."""
    import functional_colors as fc
    d = cfg(s)['display']; f = flows(s); P = f['total']['jet_W']; h2 = f['hydrogen']['kg_s']; fuel = f['total']['kg_s']-h2
    color = {sp: list(fc.PALETTE[fc.SPECIES[sp]][1][:3]) for sp in SPECIES}
    color['helium'] = list(fc.PALETTE['SERVICE'][1][:3]); color['service'] = color['helium']
    color['target'] = [(a+b)/2 for a, b in zip(color['deuterium'], color['helium-3'])]
    color['structure'] = list(fc.PALETTE['STRUCTURE'][1][:3]) if 'STRUCTURE' in fc.PALETTE else [0.45, 0.40, 0.34]; color['engine'] = color['structure']
    lines = [dict(name=n, species=sp, path=_path(n), radius=r, points=[_rt(q) for q in pts], group=_group(n), modeled=True) for n, sp, pts, r in polylines(s)]
    h = header(s)
    ring = [_rt(dm.radial(h['x'], h['r'], 2*math.pi*k/64)) for k in range(65)]
    lines.append(dict(name=h['name'], species='hydrogen', path='h2', radius=h['tube'], points=ring, loop=True, group='aft', modeled=True))
    if v1(s):
        lines += chain_lines(s)

    def state(st, k=None):
        k = st['h2'] if k is None else k; m = st['fuel']*fuel+k*h2; Pj = st['fuel']*P; F = math.sqrt(2*Pj*m)
        return dict(id=st['id'], label=st['label'], text=st['text'], drive=st.get('drive'), flow=dict(fuel=st['fuel'], h2=k, purge=st['purge'], refuel=st['refuel'], vent=0.0),
                    deuterium_kg_s=st['fuel']*f['deuterium']['kg_s'], he3_kg_s=st['fuel']*f['helium-3']['kg_s'], h2_kg_s=k*h2,
                    thrust_MN=F/1e6, ve_km_s=2*Pj/F/1e3 if F else None, jet_TW=Pj/1e12)
    states = [state(st) for st in d['states']]
    throttle = next(st for st in d['states'] if st['id'] == 'THROTTLE')
    regimes_ = [state(throttle, k) for k in d['throttle_h2_factors']]
    rho = fst.cfg(s)['density_kg_m3']
    return dict(contract='WF_FPS_WEB', id=cfg(s)['id'], version=v11_cfg(s)['version'] if v11(s) else v1_cfg(s)['version'] if v1(s) else cfg(s)['version'], baseline='V1.1' if v11(s) else 'V1' if v1(s) else cfg(s)['baseline'], status=d['status'],
                engineering_status=cfg(s)['status'], colors=color, objects=objects(s), lines=lines, states=states, throttle=regimes_,
                display=dict(dot_speed_m_s=d['dot_speed_m_s'], dot_spacing_m=d['dot_spacing_m'], dot_radius_m=d['dot_radius_m']),
                numbers=dict(mission_t={sp: f[sp]['mission_t'] for sp in SPECIES}, peak_kg_s={sp: f[sp]['kg_s'] for sp in SPECIES},
                             per_engine_kg_s={sp: f[sp]['per_engine_kg_s'] for sp in SPECIES},
                             bores_mm={sp: bore_m(f[sp]['per_engine_kg_s'], rho[fst.INV_KEY[sp]])*1e3 for sp in SPECIES},
                             run_tank_hours={sp: f[sp]['run_tank_hours'] for sp in SPECIES}, conditioning_MW=conditioning(s)['W']/1e6,
                             thrust_MN=f['total']['thrust_N']/1e6, ve_km_s=f['total']['ve_m_s']/1e3, he3_per_d_molar=cfg(s)['he3_per_d_molar']),
                interfaces=[dict(name=i['name'], species=i['species'], at=_rt(i['at']), note=i.get('note', '')) for i in interfaces(s)],
                open_ends=[dict(name=e['name'], at=_rt(e['at']), species=e['species'], note=e['note']) for e in open_ends(s)] if v1(s) else [],
                views=d.get('views', []), energy=_energy_web(s) if v1(s) else None, pipe=pipe_spec(s) if v1(s) else [],
                assembly=dict(structure_prefix='CL_', engine_prefix='VTX_') if v11(s) else None)


if __name__ == '__main__':
    import spec
    s = spec.load()[0]; r = report(s)
    if '--json' in sys.argv:
        print(json.dumps(r, indent=1, default=str)); raise SystemExit
    print(json.dumps({k: r[k] for k in ('flows', 'bores_mm', 'regimes', 'heads', 'conditioning', 'fuel_cycles', 'feedstock', 'reaction_masses', 'check')}, indent=1, default=str))
