"""S01/F01 fuel storage (FUEL-SPLIT, WORKING, owner-delegated 2026-10-29; S&E 15 OWN-FUEL-SPLIT-2026-10-29, 98 row 128).

Function: hold the propulsion inventory of the owner screens (S&E 62/64/67 scenario A: 600 t, 420 t expelled in First Ignition, 180 t
reserve) as three separated cryogens and bring each to the drive's feed run tanks.
- Helium-3 (3 K, the hardest cryogen) fills the nine BODY-C3 stations: 9 modules x 3 lobes between the keel lanes of the 13 m body.
- Hydrogen reaction mass and deuterium (both 20 K) sit in a segmented torus in the Brow's shadow between ring B and the shield truss,
  three vessels with ellipsoidal heads, the gaps on the two docking corridors and the EVA airlock; deuterium in one cell at the end of
  each vessel behind an insulated common bulkhead, so both species can be loaded and drawn with no lateral moment (B02, mass_model). Two bipod supports per vessel stand on the forward hull collar (F01).
- Transfer: the D2 and H2 lines leave the torus aft face, run aft outside the ring sweeps, come down the bypass collar's aft spoke in
  the slot between the radiator blade front and ring A, and run aft in a keel lane to the run tanks. The helium-3 header runs in the
  150 deg lane. The four Feed_Run_Tank_0n ahead of the shadow shield buffer the transfer and condition the feed (the former schematic
  tanks; the drive feed lines start on their aft caps unchanged).

Fixed: the owner screens' inventories and densities, the built hull, rings, collar, docking corridors and airlock. Every dimension here is
PROTOTYPE ([fuel_storage]); wall, insulation, support loads, boil-off, cryocoolers, CG and inertia are OPEN.

    python3 src/wayfarer/fuel_storage.py      # fit screen: capacity against need, clearances
"""
import json
import math
import layout

TAU = 2*math.pi


def cfg(s):
    return s['fuel_storage']


def need_m3(s):
    """Liquid volume each species needs with its ullage: kg / (kg/m3) * (1 + ullage)."""
    f = cfg(s); inv, rho, u = f['inventory_kg'], f['density_kg_m3'], f['ullage']
    return dict(helium_3=inv['helium_3']/rho['helium_3']*(1+u), deuterium=inv['deuterium']/rho['deuterium']*(1+u),
                hydrogen=(inv['hydrogen_first_ignition']+inv['hydrogen_reserve'])/rho['hydrogen']*(1+u))


# ---------- body: helium-3 stations ---------------------------------------------------------------------------------

def body_modules(s):
    b = cfg(s)['body']; x0 = layout.at(s, b['bay_aft_x'])
    return [dict(index=m, x0=x0+o, x1=x0+o+b['module_length_m']) for m, o in enumerate(b['module_offsets_m'])]


def body_lobes(s):
    """27 lobe vessels: one per module and keel sector, an annular sector r_in..r_out spanning span_deg about the sector middle (keel + 60).
    Liquid volume is the sector less the wall on every face."""
    b = cfg(s)['body']; w = b['wall_m']; out = []
    for m in body_modules(s):
        for k, keel in enumerate(b['keel_lanes_deg']):
            mid = keel+60.0; a0, a1 = math.radians(mid-b['span_deg']/2), math.radians(mid+b['span_deg']/2)
            ri, ro, L = b['r_in_m']+w, b['r_out_m']-w, m['x1']-m['x0']-2*w
            arc = (a1-a0)-2*w/((ri+ro)/2)
            out.append(dict(name=f"Fuel_He3_Station_{m['index']+1}_{k+1}", module=m['index']+1, lobe=k+1, species='helium-3',
                            x0=m['x0'], x1=m['x1'], r_in=b['r_in_m'], r_out=b['r_out_m'], a0=a0, a1=a1,
                            liquid_m3=max(0.0, arc/2*(ro**2-ri**2)*L)))
    return out


def utility_frames(s):
    """The two 3 m refrigeration/utility frames between modules (the wider module gaps): their centre X."""
    mods = body_modules(s); return [(a['x1']+b['x0'])/2 for a, b in zip(mods, mods[1:]) if b['x0']-a['x1'] > 2.0]


def cryocoolers(s):
    """S04 equipment mounts: one cryocooler cold-box per keel lane on each utility frame, above the lane lines and under the keel rail."""
    b = cfg(s)['body']; cc = b['cryocooler']; out = []
    for i, x in enumerate(utility_frames(s), 1):
        for k, lane in enumerate(b['keel_lanes_deg'], 1):
            out.append(dict(name=f'Fuel_Cryocooler_{i}_{k}', x=x, azimuth=math.radians(lane), r0=cc['r0_m'], r1=cc['r1_m'],
                            width=cc['width_m'], length=cc['length_m']))
    return out


def lobe_hangers(s):
    """S04 lobe mounts: each lobe hangs from the two keel rails beside it by a strut at each end of the module, from the lobe's outer
    corner to the rail (sector_radius_m less the rail radius)."""
    b = cfg(s)['body']; h = b['hanger']; rail = s['structure']['sector_radius_m']-s['prototype']['structural_rail_radius_m']; out = []
    for lb in body_lobes(s):
        struts = []
        for x in (lb['x0']+h['inset_m'], lb['x1']-h['inset_m']):
            for a, lane in ((lb['a0'], lb['a0']-math.radians(10.0)), (lb['a1'], lb['a1']+math.radians(10.0))):
                struts.append(((x, lb['r_out']*math.cos(a), lb['r_out']*math.sin(a)), (x, rail*math.cos(lane), rail*math.sin(lane))))
        out.append(dict(name=lb['name'].replace('Station', 'Hangers'), struts=struts, radius=h['radius_m']))
    return out


def lane_point(x, r, deg):
    a = math.radians(deg)
    return (x, r*math.cos(a), r*math.sin(a))


# ---------- forward torus: hydrogen and deuterium -------------------------------------------------------------------

def torus(s):
    """Torus frame (centre X, major radius R, outer minor radius a, liquid radius) and its vessels. Each gap is the clear distance
    between the head apexes at R; a vessel's cylindrical arc ends a head depth (head_ratio * a) inside it."""
    t = cfg(s)['torus']; R, a = t['major_radius_m'], t['minor_radius_m']; a_in = a-t['wall_m']; h = t['head_ratio']*a
    xc = layout.at(s, t['center_x'])
    gaps = sorted(t['gap_centers_deg']); half = [(t['gap_m']/2+h)/R for _ in gaps]
    vessels = []
    for j, g in enumerate(gaps):
        a0 = math.radians(g)+half[j]; nxt = gaps[(j+1) % len(gaps)]+(360 if j == len(gaps)-1 else 0)
        a1 = math.radians(nxt)-half[(j+1) % len(gaps)]
        vessels.append(dict(a0=a0, a1=a1))
    out = []
    d2s = {d['vessel']: d for d in (t['deuterium'] if isinstance(t['deuterium'], list) else [t['deuterium']])}
    for j, v in enumerate(vessels, 1):
        cells = [(v['a0'], v['a1'], 'hydrogen')]
        if j in d2s:
            d2 = d2s[j]
            cut = v['a1']-math.radians(d2['arc_deg']) if d2['end'] == 'a1' else v['a0']+math.radians(d2['arc_deg'])
            cells = [(v['a0'], cut, 'hydrogen'), (cut, v['a1'], 'deuterium')] if d2['end'] == 'a1' else [(v['a0'], cut, 'deuterium'), (cut, v['a1'], 'hydrogen')]
        for k, (c0, c1, sp) in enumerate(cells):
            heads = [c0 == v['a0'], c1 == v['a1']]               # ellipsoidal heads at the vessel ends; the common bulkhead is flat
            vol = math.pi*a_in**2*R*(c1-c0)+sum(heads)*(2/3)*math.pi*a_in**2*(t['head_ratio']*a_in)
            name = f'Fuel_Torus_{"D2" if sp == "deuterium" else "H2"}_{j}' + (f'_{k+1}' if len(cells) > 1 and sp == 'hydrogen' else '')
            out.append(dict(name=name, vessel=j, species=sp, a0=c0, a1=c1, heads=heads, liquid_m3=vol))
    return dict(x=xc, R=R, a=a, a_in=a_in, head=h, cells=out, vessels=vessels)


def torus_struts(s):
    """Two supports per vessel at 1/4 and 3/4 of its arc. Each support is a bipod in its azimuth's X-r plane (F01, 2026-10-31): both legs meet
    at the torus inner face and stand on the forward hull collar skin (frame stations under them), one leg raked aft, one forward, so the
    torus's inertial load under thrust runs along the legs instead of bending a radial strut."""
    import hull_geometry
    t = cfg(s)['torus']; tor = torus(s); out = []
    for j, v in enumerate(tor['vessels'], 1):
        for k, f in enumerate((.25, .75), 1):
            a = v['a0']+(v['a1']-v['a0'])*f; apex = (tor['x'], (tor['R']-tor['a'])*math.cos(a), (tor['R']-tor['a'])*math.sin(a))
            for side, dx in (('Aft', t['strut_aft_dx_m']), ('Fwd', t['strut_fwd_dx_m'])):
                x = tor['x']+dx; root = hull_geometry.radius_at(s, x)+t['strut_root_standoff_m']
                out.append(dict(name=f'Fuel_Torus_Strut_{j}_{k}_{side}', a=(x, root*math.cos(a), root*math.sin(a)), b=apex,
                                radius=t['strut_radius_m'], azimuth=a, vessel=j, side=side))
    return out


# ---------- transfer lines and run tanks ----------------------------------------------------------------------------

def run_tanks(s):
    """The four feed run tanks ahead of the shadow shield (prototype.tank_*), quadrant order of drive_hot_section.TANK_QUADRANTS."""
    p = s['prototype']; c = layout.at(s, p['tank_center_x']); o = p['tank_offset_m']; out = []
    for j, (yy, zz) in enumerate([(1, 1), (-1, 1), (-1, -1), (1, -1)], 1):
        out.append(dict(name=f'Feed_Run_Tank_{j:02}', x0=c-p['tank_length_m']/2, x1=c+p['tank_length_m']/2, y=yy*o, z=zz*o, radius=p['tank_radius_m']))
    return out


def transfer_lines(s):
    """D2 and H2 from the torus to their run tanks, and the helium-3 header from the forward station to its run tank. A torus line is two
    objects. The exterior leg leaves the torus's outer equator, runs out to bypass_r_m (outside both rings' swept radius, inside the bypass
    collar's inner chord), aft along the collar to its aft frame, down beside the aft spoke in the slot between the radiator blade front
    and ring A, aft over the hull skin to the penetration station (aft of the rotor bay's crew tubes) and stops hull_clearance_m off the
    skin. The interior leg starts the same distance inside it; the hull penetration between them is an OPEN interface. The lane leg runs
    at lane_r_m on the lane azimuth plus the line's offset, past the pulse bank and battery, and ends standoff_m off its run tank."""
    import eva_route
    import forward_shield
    f = cfg(s); tl = f['transfer']; tor = torus(s); tanks = {t['name']: t for t in run_tanks(s)}
    col = forward_shield.bypass_collar(s); x_slot = col['stations']['aft']+tl['slot_offset_m']; x_pen = x_slot+tl['penetration_offset_m']
    mods = body_modules(s); x_station_fwd = mods[-1]['x1']
    hull_r = eva_route.body_radius(s, x_pen); clr = tl['hull_clearance_m']; run_r = hull_r+tl['hull_run_m']
    out = []
    for ln in tl['lines']:
        deg = ln['lane_deg']+ln['offset_deg']; tank = tanks[ln['tank']]; lane_r = tl['lane_r_m']
        x_end = tank['x1']-tl['tank_overlap_m']
        lane_end = lane_point(x_end, lane_r, deg)
        ty, tz = lane_end[1]-tank['y'], lane_end[2]-tank['z']; d = math.hypot(ty, tz); k = (tank['radius']+tl['standoff_m'])/d
        tail = [lane_end, (x_end, tank['y']+ty*k, tank['z']+tz*k)]
        base = dict(species=ln['species'], source=ln['source'], tank=ln['tank'], radius=tl['line_radius_m'])
        if ln['source'] == 'torus':
            ext = [lane_point(tor['x'], tor['R']+tor['a']+clr, deg), lane_point(tor['x'], tl['bypass_r_m'], deg), lane_point(x_slot, tl['bypass_r_m'], deg),
                   lane_point(x_slot, run_r, deg), lane_point(x_pen, run_r, deg), lane_point(x_pen, hull_r+clr, deg)]
            out.append(dict(base, name=ln['name']+'_Ext', points=ext, leg='exterior'))
            out.append(dict(base, name=ln['name'], points=[lane_point(x_pen, hull_r-clr, deg), lane_point(x_pen, lane_r, deg)]+tail, leg='interior',
                            hull_penetration=lane_point(x_pen, hull_r, deg)))
        else:
            out.append(dict(base, name=ln['name'], points=[lane_point(x_station_fwd, lane_r, deg)]+tail, leg='interior'))
    return out


# ---------- fit screen ------------------------------------------------------------------------------------------------

def screen(s):
    n = need_m3(s); lobes = body_lobes(s); tor = torus(s)
    cap = dict(helium_3=sum(l['liquid_m3'] for l in lobes),
               deuterium=sum(c['liquid_m3'] for c in tor['cells'] if c['species'] == 'deuterium'),
               hydrogen=sum(c['liquid_m3'] for c in tor['cells'] if c['species'] == 'hydrogen'))
    t = cfg(s)['torus']; hull = s['ship']['body_diameter']['value']/2
    gaps = {}
    for g in t['gap_centers_deg']:
        gaps[str(g)] = round(t['gap_m'], 2)
    r_out = tor['R']+tor['a']
    import habitat_ring
    ring_front = max(habitat_ring.centers(s))+habitat_ring.sweep_half(s)
    return dict(
        status='PROTOTYPE fit screen (FUEL-SPLIT WORKING, owner-delegated 2026-10-29); wall, supports, boil-off and mass OPEN',
        need_m3={k: round(v, 1) for k, v in n.items()}, capacity_m3={k: round(v, 1) for k, v in cap.items()},
        margin_m3={k: round(cap[k]-n[k], 1) for k in n}, lobes=len(lobes), torus_cells=[c['name'] for c in tor['cells']],
        torus=dict(x=round(tor['x'], 2), r=[tor['R']-tor['a'], r_out], x_range=[round(tor['x']-tor['a'], 2), round(tor['x']+tor['a'], 2)],
                   gap_apex_clear_m=gaps, ring_b_sweep_clear_m=round(tor['x']-tor['a']-ring_front, 2),
                   collar_clear_m=round(tor['R']-tor['a']-__import__('hull_geometry').radius_at(s, tor['x']), 2)),
        body=dict(hull_radius_m=hull, lobe_r=[cfg(s)['body']['r_in_m'], cfg(s)['body']['r_out_m']]),
        transfer=[dict(name=l['name'], length_m=round(sum(math.dist(a, b) for a, b in zip(l['points'], l['points'][1:])), 1)) for l in transfer_lines(s)])


def check(s):
    """Physical invariants: each species fits its vessels, the torus clears ring B's sweep, every gap clears the docking keep-out."""
    r = screen(s); t = cfg(s)['torus']; errs = []
    for k, m in r['margin_m3'].items():
        if m < 0:
            errs.append(f'{k}: capacity short by {-m:.0f} m3')
    if r['torus']['ring_b_sweep_clear_m'] < s['habitat']['ring_service_clearance']['min_m']:
        errs.append('torus inside ring B service clearance')
    aft = min(st['a'][0] for st in torus_struts(s)); import habitat_ring
    if aft-(max(habitat_ring.centers(s))+habitat_ring.sweep_half(s)) < s['habitat']['ring_service_clearance']['min_m']:
        errs.append('torus strut foot inside ring B service clearance')
    if t['gap_m'] < t['corridor_keepout_m']:
        errs.append('torus gap narrower than the docking keep-out')
    return errs


if __name__ == '__main__':
    import spec
    s = spec.load()[0]
    print(json.dumps(screen(s), indent=1)); e = check(s); print('check', e or 'PASS')
