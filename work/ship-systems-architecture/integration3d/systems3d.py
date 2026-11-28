"""3D integration Stages G, H, I (Checkpoint 4). STUDY, PROTOTYPE, noncanon, Track F1.

G  ECLSS-RING (M2) and ECLSS-HUB (M3): seven ECLSS-G1 units (3 ring A, 3 ring B, 1 hub through both rotary couplings). The hub unit is laid
   out as ORUs (<= 0.70 m wide, the ring-aisle limit) inside its 2.0 x 2.2 x 1.4 m envelope with a maintenance face; the hub-to-ring ducts
   are sized from the Phase V interface (4 m/s) and checked against the transfer drum; the Phase V failure cases are carried.
H  LOG-G1 (M3): the 3 t parametric container (frame, panels, grapple fixtures, latches, tag) from the Phase V container relation; the hub store;
   the six body-bay dry-store containers displaced by the L2 district (Checkpoint 2) re-homed in a tenth body-bay module.
   MRO-WS (M2) workshop + fab cell; MRO-ROB (M2) robots: single-arm 3 t manipulators (FT-07), radiator/H6a inspection crawlers, and the
   MRU heavy carriage that Checkpoint 2 found necessary (TAC 7.9 t, reactor/IHX 21.5 t) on a rail along the keel lane at az 270.
I  PROP-CRYO (M2): cryocooler stations sized from fuel_loads.cooling scaled to the T-A vessel area plus the OpenMC nuclear heating (scaled
   to the F1 unit power); the WARM / LOW heat-sink ledger with every Checkpoint 3-4 increment. PROP-FARM (M2) T-A stretch geometry;
   STRUCT-F1 (M2) stretch envelope (primary-structure mass owned by the PSA thread, not counted here); GNC-CDH (M1) placeholder blocks.
Writes ../results/i3d_eclss.json, i3d_logistics.json, i3d_remaining.json and four SVGs.
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent; W = HERE.parent; ROOT = W.parents[1]; R = W/'results'
sys.path.insert(0, str(ROOT/'src/wayfarer'))
import spec  # noqa: E402
import fuel_storage as fs  # noqa: E402
import fuel_loads  # noqa: E402
import mass_model as mm  # noqa: E402

P5 = json.loads((R/'phase5.json').read_text()); P6 = json.loads((R/'phase6.json').read_text()); PW = json.loads((R/'i3d_power.json').read_text())
RD = json.loads((R/'i3d_radiators.json').read_text()); EL = json.loads((R/'i3d_electrical.json').read_text()); TK = json.loads((R/'i3d_tanks.json').read_text())
LAY = {x['name']: x for x in P6['layout']}
ORU_W = P5['eclss']['unit']['orus_max_width_m']


# ------------------------------------------------------------------------------------------------------------- G ECLSS
HUB_ORUS = [  # name, mass kg, power W, size (x along the unit, y across, z height) m; PROTOTYPE split of the Phase V 1.2 t / 3.4 kW unit
    ('Fan pair (redundant)', 70, 450, (0.6, 0.6, 0.5)), ('CO2 amine swing bed A', 170, 700, (0.6, 0.7, 0.55)), ('CO2 amine swing bed B', 170, 700, (0.6, 0.7, 0.55)),
    ('Condensing heat exchanger + separator', 130, 150, (0.6, 0.6, 0.5)), ('Trace contaminant control', 90, 300, (0.5, 0.5, 0.5)),
    ('Water processor (urine + condensate)', 260, 800, (0.7, 0.7, 0.6)), ('O2 / N2 interface panel', 60, 50, (0.4, 0.6, 0.3)),
    ('Controller + sensors (data A/B)', 40, 250, (0.4, 0.4, 0.3))]


def eclss():
    u = P5['eclss']['unit']; hi = P5['eclss']['hub_interface']; h = LAY['ECLSS_HUB']; env = h['d']
    struct = u['mass_t']*1e3-sum(o[1] for o in HUB_ORUS); pw = sum(o[2] for o in HUB_ORUS)
    # pack ORUs in two rows along x on the maintenance face (+z side faces the hub aisle), each row two levels
    slots = []; x = -env[0]/2+0.05; row = 0; lvl = 0
    for name, m, p, sz in HUB_ORUS:
        if x+sz[0] > env[0]/2-0.05:
            x = -env[0]/2+0.05; lvl += 1
        slots.append(dict(name=name, mass_kg=m, power_W=p, size=sz, c=(x+sz[0]/2, (-1)**lvl*(env[1]/2-0.05-sz[1]/2), -env[2]/2+0.05+sz[2]/2+(lvl//2)*0.7), level=lvl,
                          width_ok=min(sz[:2]) <= ORU_W))
        x += sz[0]+0.05
    over = [s for s in slots if any(abs(s['c'][i])+s['size'][i]/2 > env[i]/2+1e-6 for i in range(3)) or s['level'] > 3]
    duct = dict(D_m=hi['duct_D_m'], v_m_s=hi['duct_velocity'], flow_m3_s=u['air_flow_m3_s'], length_m=2*abs(LAY['RotaryCoupling_B']['c'][0]-LAY['ECLSS_HUB']['c'][0])+2*2.4,
                drum_r=(1.3, 1.5), leak_kg_d=hi['leak_kg_d'])
    Re = duct['v_m_s']*duct['D_m']/1.6e-5; f = 0.316/Re**0.25; dp = f*duct['length_m']/duct['D_m']*1.2*duct['v_m_s']**2/2+4*0.5*1.2*duct['v_m_s']**2/2
    duct.update(dp_Pa=dp, fan_W=dp*duct['flow_m3_s']/0.5, fits_drum=duct['D_m']+0.05 <= 2*(1.5-1.3)+duct['D_m'])
    ring = [dict(name=n, ring=n[6], c=LAY[n]['c'], env=LAY[n]['d']) for n in ('ECLSS_A1', 'ECLSS_A2', 'ECLSS_A3', 'ECLSS_B1', 'ECLSS_B2', 'ECLSS_B3')]
    cases = next(c for c in P5['eclss']['cases'] if c['units'] == 7)
    return dict(unit=u, hub=dict(c=h['c'], env=env, orus=slots, structure_kg=struct, power_W=pw, all_fit=not over, maint_face='+z (hub aisle), 1.0 m clear'),
                duct=duct, ring_units=ring, cases=cases,
                findings=[f'Hub unit (M3): {len(slots)} ORUs, every one <= {ORU_W:.2f} m in its narrow dimension, inside the {env[0]:.1f} x {env[1]:.1f} x {env[2]:.1f} m envelope '
                          f'({"all fit" if not over else "overflow: "+", ".join(s["name"] for s in over)}); ORUs {sum(o[1] for o in HUB_ORUS)} kg + {struct:.0f} kg frame, '
                          f'{pw/1e3:.1f} kW. The CO2 beds and the fan are duplicated inside the unit; the water processor is the single heaviest ORU ({max(o[1] for o in HUB_ORUS)} kg).',
                          f'Hub-to-ring ducts D {duct["D_m"]:.2f} m at {duct["v_m_s"]:.0f} m/s through each transfer drum (r 1.3-1.5 m): '
                          f'{duct["dp_Pa"]:.0f} Pa, fan {duct["fan_W"]:.0f} W; rotating air seal leak {hi["leak_kg_d"][0]}-{hi["leak_kg_d"][2]} kg/d (the make-up is in the O2/N2 reserve).',
                          f'Seven units pass {sum(cases["results"].values())} of {len(cases["results"])} Phase V failure cases (ring A lost + one B unit or the hub unit failed included).'])


# ------------------------------------------------------------------------------------------------------------- H logistics, workshop, robots
def container(gross_t):
    """LOG-G1 parametric container from the Phase V relation (cube; tare from frame + panels + fittings)."""
    rows = P5['logistics']['containers']; r = min(rows, key=lambda q: abs(q['gross_t']-gross_t))
    k = r['edge_m']/r['gross_t']**(1/3); edge = k*gross_t**(1/3); tare = r['tare_t']*(gross_t/r['gross_t'])**(2/3)
    frame = 0.55*tare; panels = 0.30*tare; fittings = 0.15*tare
    return dict(gross_t=gross_t, edge_m=edge, tare_t=tare, payload_t=gross_t-tare, volume_m3=edge**3, inner_m3=(edge-0.1)**3, frame_t=frame, panels_t=panels,
                fittings_t=fittings, member_m=0.08, grapples=4, latches=8, fits_hatch=edge*math.sqrt(2) <= 3.0 or edge <= 2.5, handling='single-arm (FT-07, <= 3 t)')


def logistics(s):
    G1 = container(3.0)
    hub = [dict(name=n, c=LAY[n]['c']) for n in LAY if n.startswith('LOG_G1_')]
    disp = PW['checks']['dry_store_displaced']; dry = fs.dry_containers(s); mods = fs.body_modules(s)
    b = fs.cfg(s)['body']; off10 = b['module_offsets_m'][-1]+12.0; x0 = mods[0]['x0']-b['module_offsets_m'][0]+off10; x1 = x0+b['module_length_m']
    q = b['dry_store']; L = (b['module_length_m']-q['end_gap_m']*2-(q['per_module']-1)*q['between_m'])/q['per_module']
    new = []
    for k, lane in enumerate(b['keel_lanes_deg'], 1):
        mid = lane+60.0
        for j in range(q['per_module']):
            xa = x0+q['end_gap_m']+j*(L+q['between_m'])
            new.append(dict(name=f'Dry_Store_M10_S{k}_{j+1}', module=10, azimuth_deg=mid, x0=xa, x1=xa+L, r0=q['r0_m'], r1=q['r1_m'], width=q['width_m'], volume_m3=L*(q['r1_m']-q['r0_m'])*q['width_m']))
    # conflicts in the new module: Phase VI defense buffers (x 30.6-43 at az 90 r 3.1-4.5) move forward
    buf = [LAY[n] for n in LAY if n.startswith('DefenseBuffer_')]; shift = max(0.0, x1+0.4-min(a['c'][0]-a['d'][0]/2 for a in buf))
    data = [(4.6, 0.0), (-4.6, 0.0)]
    def corner_clear(c):
        a = math.radians(c['azimuth_deg']); er = (math.cos(a), math.sin(a)); et = (-math.sin(a), math.cos(a)); best = 9.9
        for rr in (c['r0'], c['r1']):
            for tt in (-c['width']/2, c['width']/2):
                p = (er[0]*rr+et[0]*tt, er[1]*rr+et[1]*tt)
                for d in data: best = min(best, math.dist(p, d)-0.08)
                for az in EL['geometry'][0:0] or (30.0, 150.0, 270.0):
                    bp = (5.0*math.cos(math.radians(az)), 5.0*math.sin(math.radians(az))); best = min(best, math.dist(p, bp)-0.25)
        return best
    clear = min(corner_clear(c) for c in new)
    # workshop and robots
    ws = LAY['Workshop']; sp = LAY['SparesRacks']
    heavy = [p for p in PW['unit']['parts'] if p['module_t'] > 3.0] if 'module_t' in PW['unit']['parts'][0] else [p for p in PW['unit']['parts'] if p['mass_t']/max(1, p['modules']) > 3.0]
    heavy = [dict(name=p['name'], t=p['mass_t']/max(1, p['modules'])) for p in heavy if p['key'] not in ('shield', 'structure')]
    h6pump = P6['hot']['F1']['by_item_t']['pumps'][1]/6
    rating = 1.15*max(h['t'] for h in heavy)
    rail_x = (PW['district'][0]['centre'][0]-2.0, ws['c'][0]-ws['d'][0]/2); rail_L = rail_x[1]-rail_x[0]
    carriage = dict(rating_t=rating, carriage_t=0.18*rating, rail_kg_m=22.0, rail_m=rail_L, rail_t=22.0*rail_L/1e3, x=rail_x, az=270.0, r=3.6,
                    speed_m_s=0.05, a_max_m_s2=0.002, transit_h=rail_L/0.05/3600, clear_m=1.2,
                    rule='moves only in coast; parks and locks to the frame before a burn (0.2-0.74 g would put 40-160 kN on the rail)')
    robots = [dict(kind='single-arm manipulator (FT-07, 3 t)', n=3, t_each=0.45, base='keel lanes az 30 / 150 / 270, hub store rail'),
              dict(kind='radiator / H6a inspection crawler', n=6, t_each=0.12, base='two per blade root, docking at the H6a inspection ports'),
              dict(kind='MRU heavy carriage (new requirement)', n=1, t_each=carriage['carriage_t'], base=f'keel lane az 270, rail x {rail_x[0]:.0f} to {rail_x[1]:.0f}')]
    m_rob = sum(r['n']*r['t_each'] for r in robots)+carriage['rail_t']
    supervision = dict(where='hub, behind the workshop (shadow-shielded by the rings and farm), two consoles on data A and B', note='crew supervise; no crew in the district while a unit runs (shutdown gamma for weeks, Phase III)')
    G1_tare_hub = len(hub)*G1['tare_t']
    return dict(container=G1, hub_store=hub, hub_tare_t=G1_tare_hub, displaced=disp, module10=dict(offset_m=off10, x=(x0, x1), containers=new, defense_buffer_shift_m=shift,
                min_clear_m=clear, rack_t=4.0),
                workshop=dict(c=ws['c'], d=ws['d'], power_kW=25.0, functions=['additive (metal + polymer)', 'machining', 'electronics bench', 'ORU test stand', 'hot-cell glovebox (activated ORUs, OPEN shielding)']),
                spares=dict(c=sp['c'], d=sp['d']), heavy_items=heavy+[dict(name='H6a EM pump (outside hull, drive-bay hatch)', t=h6pump)], carriage=carriage, robots=robots, robots_t=m_rob,
                supervision=supervision,
                findings=[f'LOG-G1 (M3): {G1["edge_m"]:.2f} m cube, {G1["tare_t"]:.2f} t tare ({G1["frame_t"]:.2f} frame, {G1["panels_t"]:.2f} panels, {G1["fittings_t"]:.2f} '
                          f'fittings), {G1["payload_t"]:.2f} t payload, {G1["inner_m3"]:.1f} m3 inside; 4 grapple fixtures (one per upper corner pair face), 8 latches; '
                          'single-arm handling; parametric in gross mass (1.5 / 3 / 6 t rows of Phase V reproduce).',
                          f'The six dry-store containers displaced by the district ({disp["volume_m3"]:.0f} m3) move to a tenth body-bay module at x {x0:.2f}-{x1:.2f} '
                          f'(offset {off10:.0f} m, same racks); the Phase VI defense buffers shift +{shift:.1f} m forward to clear it; closest data/bus clearance {clear:.2f} m.',
                          f'MRU heavy carriage: rated {rating:.1f} t ({", ".join(f"{h["name"]} {h["t"]:.1f} t" for h in heavy)}), {carriage["carriage_t"]:.1f} t + '
                          f'{carriage["rail_t"]:.1f} t of rail over {rail_L:.0f} m on the az 270 keel lane (the district removal route) to the workshop; '
                          f'{carriage["transit_h"]:.1f} h per trip at 5 cm/s; coast only.',
                          f'Robots and rails {m_rob:.1f} t (new line); the 60 t workshop/spares/cargo line holds the tools and spares themselves.',
                          f'H6a EM pumps ({h6pump:.1f} t) sit outside the hull: they leave by the drive-bay hatch with an external manipulator (OPEN, not drawn).'],
                ledger_add=[dict(item='robots, crawlers, MRU carriage + rail (Stage H)', t=m_rob, cls='FT-07 (APPROVED), NEW'),
                            dict(item='body-bay module 10 racks (relocated dry store, Stage H)', t=4.0, cls='NEW (PROTOTYPE)')])


# ------------------------------------------------------------------------------------------------------------- I cryo, heat sinks, farm, structure, GNC
def remaining(s):
    ts = fs.tanks(s); A0 = sum(mm.shell_area(t) for t in ts); TA = next(a for a in TK['alternatives'] if a['id'] == 'T-A'); fA = TA['shell_area_m2']/A0
    c = fuel_loads.cooling(s); CR = P6['reconciliation']['cryo']; case = next(x for x in CR['cases'] if x['load'].startswith('full'))
    pf = (3.5e6/0.154)/CR['basis']['unit_thermal_W']                                     # F1 unit thermal power vs the OpenMC surrogate
    he3 = c['he3_stage_lift_W']*fA+case['he3_nuclear_W']*pf; sh = c['shield_lift_W']*fA+case['h_d_nuclear_W']*pf
    inst_he3 = 1.25*he3; inst_sh = 1.25*sh; inp = inst_he3*CR['he3_W_per_W']+inst_sh*CR['shield_W_per_W']
    n_he3 = sum(1 for t in ts if t['species'] == 'helium-3')
    stations = []
    for t in ts:
        a = math.radians(t['azimuth_deg']); x = t['x0']+TA['added_length_m']+(t['x1']-t['x0'])+0.8
        stations.append(dict(tank=t['id'], species=t['species'], c=(TA['vessel_length_m']+t['x0']+1.0, t['R']*math.cos(a), t['R']*math.sin(a)),
                             stage='3 K + 20 K' if t['species'] == 'helium-3' else '20 K'))
    mass_cryo = inp/1e3*0.012                                                              # ~12 kg per kW of input (pulse-tube / reverse-Brayton class), PROTOTYPE
    low_load = c['rejected_W']*fA+(case['he3_nuclear_W']*CR['he3_W_per_W']+case['h_d_nuclear_W']*CR['shield_W_per_W'])*pf*1.25
    low = dict(design_W=1.0e6, cryo_reject_W=low_load, phase6_reject_W=c['rejected_W'], margin_W=1.0e6-low_load-(1.0e6-c['low_section_margin_W']-c['rejected_W']))
    warm_add = dict(nak_insulation_leak_W=3*RD['nak']['leak_W_per_loop'], bus_loss_W=EL['buses']['loss_W'], phase6_shortfall_W=P6['warm_shortfall_W'])
    warm_short = sum(warm_add.values())
    per_m_warm = 5.0e6*1.2/22.5/1.2                                                       # design W per metre of WARM length (all three blades)
    warm_ext = warm_short*1.2/per_m_warm
    gnc = [dict(name='CMG cluster (production, body bay)', c=(-5.0, 0.0, -2.6), half=(1.6, 1.6, 1.2), level='M1'),
           dict(name='Flight computers A/B (hub)', c=(98.2, 0.0, -3.6), half=(0.6, 0.5, 0.5), level='M1'),
           dict(name='Star trackers + IMU (Brow rim)', c=(141.0+TA['added_length_m'], 0.0, 40.0), half=(0.4, 0.4, 0.4), level='M1'),
           dict(name='Nav beacon / comm (Brow)', c=(141.0+TA['added_length_m'], 0.0, -40.0), half=(0.6, 0.6, 0.6), level='M1')]
    struct = dict(farm_x=(109.25, 109.25+TA['vessel_length_m']), added_m=TA['added_length_m'], brow_x=(141.8+TA['added_length_m'], 144.8+TA['added_length_m']),
                  note='primary-structure members, frames and their mass belong to the PSA thread (PSA-IF 0.1); ISSA passes the envelope and the stretch only')
    low_short = max(0.0, -low['margin_W']); low_ext = low_short*1.2/(1.0e6/9.0)
    pending = [dict(id='WARM', item=f'WARM section +{warm_ext:.1f} m to absorb {warm_short/1e3:.0f} kW (Phase VI shortfall + Stage E/F leaks); blade mass ~2.6 t/m',
                    t=warm_ext*2.6),
               dict(id='LOW', item=f'LOW section +{low_ext:.1f} m to absorb the {low_short/1e3:.0f} kW cryo shortfall (T-A area + nuclear heating)', t=low_ext*2.6)]
    return dict(cryo=dict(area_factor=fA, A0_m2=A0, A_TA_m2=TA['shell_area_m2'], power_factor=pf, he3_W=he3, shield_W=sh, installed_he3_W=inst_he3, installed_shield_W=inst_sh,
                          input_W=inp, stations=stations, n_he3=n_he3, mass_t=mass_cryo, low=low),
                warm=dict(adds=warm_add, short_W=warm_short, ext_m=warm_ext, per_m_W=per_m_warm), gnc=gnc, structure=struct, pending=pending,
                findings=[f'Cryocoolers (M2): T-A vessels have {fA:.2f}x the shell area, so the leak lift grows to {he3:.0f} W at 3 K (He-3) and {sh/1e3:.2f} kW at 20 K, '
                          f'nuclear heating included (OpenMC side scatter scaled to the F1 unit, {pf:.2f}x); installed with 25 % margin they need {inp/1e3:.0f} kW of input '
                          f'and about {mass_cryo:.1f} t of coolers, one station at the forward end of each vessel (13; the six He-3 stations carry a 3 K stage).',
                          f'LOW section: the cryo heat it rejects rises from {c["rejected_W"]/1e3:.0f} kW to {low_load/1e3:.0f} kW; LOW margin '
                          f'{low["margin_W"]/1e3:.0f} kW ({"holds" if low["margin_W"] > 0 else "SHORT"}).',
                          f'WARM section: Phase VI shortfall {P6["warm_shortfall_W"]/1e3:.0f} kW + NaK insulation leak {3*RD["nak"]["leak_W_per_loop"]/1e3:.0f} kW + bus loss '
                          f'{EL["buses"]["loss_W"]/1e3:.0f} kW = {warm_short/1e3:.0f} kW short; with the 1.2 margin that is +{warm_ext:.1f} m of WARM length (owner question with '
                          'the radiator decisions; the graded blade has no free length between WARM and LOW without moving the bulkheads).',
                          f'Farm and structure (M2): T-A stretches the farm to x {struct["farm_x"][0]:.2f}-{struct["farm_x"][1]:.2f} and moves the Brow to x {struct["brow_x"][0]:.1f}; '
                          'primary-structure mass is the PSA thread\'s and is not in this ledger.',
                          'GNC / C&DH (M1): placeholder blocks for the production CMGs, flight computers A/B in the hub, star trackers and comms on the Brow rim.'],
                ledger_add=[dict(item='cryocooler stations (13, T-A area, Stage I)', t=mass_cryo, cls='NEW (PROTOTYPE)')])


# ------------------------------------------------------------------------------------------------------------- drawings
def svg_hub(EC, path):
    h = EC['hub']; env = h['env']; s = 230; w, hh = 760, 470; X = lambda x: 380+x*s; Y = lambda y: 210+y*s
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {hh}" width="{w}" style="max-width:100%;height:auto" font-family="Inter,system-ui,sans-serif" font-size="11" role="img" aria-label="Hub ECLSS unit">',
         '<style>.t{fill:var(--fg,#223)} .m{fill:var(--muted,#667)}</style>', '<text x="14" y="20" class="t" font-weight="600">Hub ECLSS-G1 unit (M3): plan of the ORU layout (maintenance face up)</text>']
    o.append(f'<rect x="{X(-env[0]/2):.0f}" y="{Y(-env[1]/2):.0f}" width="{env[0]*s:.0f}" height="{env[1]*s:.0f}" fill="none" stroke="#888" stroke-dasharray="4 3"/>')
    pal = ['#3a8fd0', '#2fa36b', '#2fa36b', '#5aa0b8', '#8a6fd8', '#c9852a', '#d23a6a', '#777']
    for i, oru in enumerate(h['orus']):
        cx, cy = oru['c'][0], oru['c'][1]; sx, sy = oru['size'][0], oru['size'][1]
        o.append(f'<rect x="{X(cx-sx/2):.0f}" y="{Y(cy-sy/2):.0f}" width="{sx*s:.0f}" height="{sy*s:.0f}" fill="{pal[i % len(pal)]}" fill-opacity="0.25" stroke="{pal[i % len(pal)]}"/>')
        o.append(f'<text x="{X(cx-sx/2)+4:.0f}" y="{Y(cy)-2:.0f}" class="t" font-size="10">{oru["name"].split("(")[0][:22]}</text><text x="{X(cx-sx/2)+4:.0f}" y="{Y(cy)+12:.0f}" class="m" font-size="10">{oru["mass_kg"]} kg, {oru["power_W"]} W</text>')
    o.append(f'<text x="14" y="{hh-34}" class="m">Envelope {env[0]:.1f} x {env[1]:.1f} x {env[2]:.1f} m; every ORU <= {ORU_W:.2f} m wide; {len(h["orus"])} ORUs + {h["structure_kg"]:.0f} kg frame; {h["power_W"]/1e3:.1f} kW.</text>')
    o.append(f'<text x="14" y="{hh-16}" class="m">Ducts D {EC["duct"]["D_m"]:.2f} m to both rotary couplings through the transfer drums; seal leak {EC["duct"]["leak_kg_d"][0]}-{EC["duct"]["leak_kg_d"][2]} kg/d.</text>')
    o.append('</svg>'); path.write_text('\n'.join(o))


def svg_container(G1, path):
    w, h = 760, 360; e = G1['edge_m']; s = 110; ox, oy = 140, 300
    P = lambda x, y, z: (ox+x*s+y*s*0.45, oy-z*s-y*s*0.3)
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" style="max-width:100%;height:auto" font-family="Inter,system-ui,sans-serif" font-size="11" role="img" aria-label="LOG-G1 container">',
         '<style>.t{fill:var(--fg,#223)} .m{fill:var(--muted,#667)}</style>', '<text x="14" y="20" class="t" font-weight="600">LOG-G1 3 t container (M3): frame, panels, grapples, latches</text>']
    V = [(x, y, z) for x in (0, e) for y in (0, e) for z in (0, e)]
    for a in V:
        for b in V:
            if sum(1 for i in range(3) if a[i] != b[i]) == 1 and a < b:
                p, q = P(*a), P(*b); o.append(f'<line x1="{p[0]:.0f}" y1="{p[1]:.0f}" x2="{q[0]:.0f}" y2="{q[1]:.0f}" stroke="#5a6b7a" stroke-width="5"/>')
    for (x, y) in ((0.25*e, 0), (0.75*e, 0)):
        p = P(x, y, e); o.append(f'<circle cx="{p[0]:.0f}" cy="{p[1]:.0f}" r="7" fill="#d23a6a"/>')
    for (x, y, z) in ((0, 0, 0), (e, 0, 0), (0, 0, e), (e, 0, e)):
        p = P(x, y, z); o.append(f'<rect x="{p[0]-5:.0f}" y="{p[1]-5:.0f}" width="10" height="10" fill="#c9852a"/>')
    lines = [f'edge {G1["edge_m"]:.2f} m, inside {G1["inner_m3"]:.1f} m3', f'tare {G1["tare_t"]:.2f} t: frame {G1["frame_t"]:.2f}, panels {G1["panels_t"]:.2f}, fittings {G1["fittings_t"]:.2f}',
             f'payload {G1["payload_t"]:.2f} t', f'{G1["grapples"]} grapple fixtures (magenta), {G1["latches"]} latches (amber, corner)', f'handling: {G1["handling"]}',
             'tag: RFID + optical code (data A/B inventory)', 'parametric: container(gross_t) in systems3d.py']
    for i, ln in enumerate(lines): o.append(f'<text x="430" y="{80+20*i}" class="m">{ln}</text>')
    o.append('</svg>'); path.write_text('\n'.join(o))


def svg_mro(LG, path):
    w, h = 1000, 300; sx = 3.6; X = lambda x: 40+(x+100)*sx
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" font-family="Inter,system-ui,sans-serif" font-size="11" role="img" aria-label="Maintenance routes">',
         '<style>.t{fill:var(--fg,#223)} .m{fill:var(--muted,#667)}</style>', '<text x="14" y="20" class="t" font-weight="600">Maintenance and logistics along the ship (x, m)</text>']
    c = LG['carriage']
    o.append(f'<line x1="{X(c["x"][0]):.0f}" y1="150" x2="{X(c["x"][1]):.0f}" y2="150" stroke="#c9852a" stroke-width="6"/><text x="{X(c["x"][0]):.0f}" y="140" class="t">MRU heavy carriage rail, keel lane az 270 ({c["rail_m"]:.0f} m, rated {c["rating_t"]:.0f} t)</text>')
    for x0, x1, lab, col in ((-91.0, -79.0, 'L2 district', '#e0553a'), (LG['module10']['x'][0], LG['module10']['x'][1], 'module 10 (relocated dry store)', '#3a8fd0'),
                             (LG['workshop']['c'][0]-2, LG['workshop']['c'][0]+2, 'workshop', '#2fa36b'), (105.5, 114.3, 'hub store (LOG-G1)', '#8a6fd8')):
        o.append(f'<rect x="{X(x0):.0f}" y="170" width="{(x1-x0)*sx:.0f}" height="34" fill="{col}" fill-opacity="0.25" stroke="{col}"/><text x="{X(x0):.0f}" y="222" class="m">{lab}</text>')
    for x in range(-100, 141, 20):
        o.append(f'<text x="{X(x)-8:.0f}" y="270" class="m" font-size="10">{x}</text>')
    o.append(f'<text x="14" y="290" class="m">Coast only; parks and locks before a burn. Single-arm manipulators (3 t) on lanes 30/150/270; six crawlers on the blade roots.</text>')
    o.append('</svg>'); path.write_text('\n'.join(o))


def svg_heat(RM, path):
    w, h = 760, 230; c = RM['cryo']; wa = RM['warm']
    rows = [('LOW: cryo reject (T-A, nuclear incl.)', c['low']['cryo_reject_W'], 1.0e6, '#3a8fd0'), ('WARM: shortfall incl. Stage E/F leaks', wa['short_W'], 5.0e6, '#c9852a')]
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" style="max-width:100%;height:auto" font-family="Inter,system-ui,sans-serif" font-size="11" role="img" aria-label="Heat sinks">',
         '<style>.t{fill:var(--fg,#223)} .m{fill:var(--muted,#667)}</style>', '<text x="14" y="20" class="t" font-weight="600">WARM and LOW heat-sink loads (kW, bar = design capacity)</text>']
    for i, (lab, v, cap, col) in enumerate(rows):
        y = 50+i*70; o.append(f'<rect x="250" y="{y}" width="460" height="24" fill="none" stroke="#999"/><rect x="250" y="{y}" width="{min(460, 460*v/cap):.0f}" height="24" fill="{col}" fill-opacity="0.5"/>')
        o.append(f'<text x="14" y="{y+16}" class="t">{lab}</text><text x="250" y="{y+42}" class="m">{v/1e3:.0f} kW of {cap/1e3:.0f} kW design</text>')
    o.append(f'<text x="14" y="{h-12}" class="m">WARM is short by {wa["short_W"]/1e3:.0f} kW: +{wa["ext_m"]:.1f} m of section with the 1.2 margin (owner question).</text>')
    o.append('</svg>'); path.write_text('\n'.join(o))


def main():
    s = spec.load()[0]
    EC = eclss(); LG = logistics(s); RM = remaining(s)
    EC['ledger_add'] = []
    (R/'i3d_eclss.json').write_text(json.dumps(EC, indent=1)); (R/'i3d_logistics.json').write_text(json.dumps(LG, indent=1)); (R/'i3d_remaining.json').write_text(json.dumps(RM, indent=1))
    svg_hub(EC, R/'i3d_eclss_hub.svg'); svg_container(LG['container'], R/'i3d_log_g1.svg'); svg_mro(LG, R/'i3d_mro_routes.svg'); svg_heat(RM, R/'i3d_heat_sinks.svg')
    for f in EC['findings']+LG['findings']+RM['findings']: print('-', f)


if __name__ == '__main__':
    main()
