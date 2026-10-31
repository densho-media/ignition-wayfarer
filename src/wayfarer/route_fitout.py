"""IND-001 cultural fit-out of the boarding route (ARCHITECTURE layer, PROTOTYPE, standard library only).

The owner's request Doc section 13 adds a cultural architecture pass after a zone's whitebox has passed its eye-level review: Culture
31_ARCHITECTURE gives the meaning (sources.cultural_architecture), the Art Style Bible the depiction and the silhouette test
(sources.architecture_depiction). Spacer culture is the primary grammar (Contain), with Great Union (Order) and Robocracy / Bolt-Sworn
(Systemize / Humanize). HSFP (98!A58) still applies: every element here has a job the route already needs (structure and panel mounting,
ventilation, orientation, wayfinding, the standard hatch interface, service access, emergency equipment, handholds), and the culture decides
how it looks. Nothing here changes a pressure boundary, an interface or the clear route: elements sit on the walls outside the parked
leaves and the existing fixtures, and check() keeps them out of the passage.

Elements are in the dock-local frame of human_entry (a along the port's outward radial, rho and phi across it; phi 180 deg is aft, the deck
when the ship thrusts). Shapes: 'arc' (a0..a1, rho0..rho1, phi0..phi1 in degrees: a curved wall element), 'box' (human_entry's box: centre
(a, rho, phi) and size along u, tangential, radial), 'ring' (an (a, rho) profile revolved about the port axis), 'rod' (vehicle-frame points
and a radius) and 'cyl' (vehicle-frame end points and a radius). Every element carries its grammar, function, HSFP design class, a paint
key for the depiction and whether it is signage (removed for the silhouette test).

The parameters are `[route_fitout]` (the scheme the user picked in study 1.1); studies/induction_entry.py keeps the other variants and passes
them as `scheme`. `python3 src/wayfarer/route_fitout.py` prints the element count and the check.
"""
import json
import math
from pathlib import Path
import crew_transfer as ct
import habitat_ring
import human_entry as he

ZONES = ('chamber', 'node')
TEXT = {'outer': 'D1 OUTER HATCH\nDOCK PRIMARY', 'inner': 'D1 INNER HATCH\nTO TRUNK',
        'route': 'TRUNK, AFT\nREFUGE  RING B  RING A', 'locker': 'EMERGENCY\nO2  FIRE  LEAK'}

def extents(s, f):
    """Wall radius and axial range of the entry chamber and the trunk node."""
    st = he.stations(s, f)
    return {'chamber': (st['chamber_r'], st['a_in'], st['a_out']), 'node': (st['node_r'], st['node_in'], st['bottom'])}


def blocked(s, f):
    """(zone, a0, a1, phi0, phi1) wall windows already taken: the parked leaves (their swing too), the light strips and the panels."""
    h = s['human_entry']; st = he.stations(s, f); R = st['chamber_r']
    half = math.degrees(math.atan2(st['r_leaf'], st['r_hinge']))+5.0          # the parked leaf's tangential half-width seen from the axis
    lw = math.degrees(h['light_size_m'][1]/2/R)+3.0; pw = math.degrees(h['panel_size_m'][1]/2/R)+3.0; la = h['light_size_m'][0]/2
    out = [('chamber', st['a_in'], st['a_out'], h['outer_hinge_deg']-half, h['outer_hinge_deg']+half),
           ('node', st['node_in'], st['bottom'], h['inner_hinge_deg']-half, h['inner_hinge_deg']+half)]
    mid = (st['a_in']+st['a_out'])/2; nmid = (st['node_in']+st['bottom'])/2
    out += [('chamber', mid-la, mid+la, d-lw, d+lw) for d in h['light_deg']]+[('node', nmid-la, nmid+la, d-lw, d+lw) for d in h['node_light_deg']]
    pa = h['panel_size_m'][0]
    out += [('chamber', st['a_in']+.2, st['a_in']+.2+pa, h['panel_deg']-pw, h['panel_deg']+pw),
            ('node', st['bottom']-.2-pa, st['bottom']-.2, h['node_panel_deg']-pw, h['node_panel_deg']+pw)]
    return out


def norm(d):
    return d % 360.0


def overlaps(p, q):
    """Do two angle intervals (degrees, any wrap) overlap?"""
    def parts(lo, hi):
        lo, hi = norm(lo), norm(hi)
        return [(lo, hi)] if lo <= hi else [(lo, 360.0), (0.0, hi)]
    return any(a < d and c < b for a, b in parts(*p) for c, d in parts(*q))


def free_arcs(windows, gap=0.0):
    """Complement on [0, 360) of the given angle windows, widened by gap."""
    cuts = []
    for lo, hi in windows:
        lo, hi = norm(lo-gap), norm(hi+gap)
        cuts += [(lo, hi)] if lo <= hi else [(lo, 360.0), (0.0, hi)]
    cuts.sort(); out = []; at = 0.0
    for lo, hi in cuts:
        if lo > at+1e-6:
            out.append((at, lo))
        at = max(at, hi)
    if at < 360.0-1e-6:
        out.append((at, 360.0))
    if len(out) > 1 and out[0][0] == 0.0 and out[-1][1] == 360.0:      # join the arc across 0 deg
        out = [(out[-1][0]-360.0, out[0][1])]+out[1:-1]
    return out


def element(name, grammar, function, cls, paint, shape, signage=False, **geo):
    return dict(name=name, layer='ARCHITECTURE', grammar=grammar, function=function, design_class=cls, paint=paint, shape=shape,
                signage=signage, geometry_status='PROTOTYPE', **geo)


def elements(s, f, scheme=None):
    """Fit-out elements of the entry chamber and the trunk node: [route_fitout], or a study scheme."""
    p = scheme or s['route_fitout']; st = he.stations(s, f); n = f['name']; ext = extents(s, f); win = blocked(s, f); out = []
    h = s['human_entry']; R = st['chamber_r']
    taken = lambda zone, a: [(lo, hi) for z, a0, a1, lo, hi in win if z == zone and a0-.05 <= a <= a1+.05]
    def mounted(zone, a):
        fps = [footprint(s, f, q) for q in out if q['shape'] in ('arc', 'box') and 'Deck_Band' not in q['name']]
        return [(fp[3], fp[4]) for fp in fps if fp and fp[0] == zone and fp[1]-.05 <= a <= fp[2]+.05]
    if p['stringer_depth_m'] > 0:
        r, a0, a1 = ext['chamber']
        for d in (60.0, 300.0):
            out.append(element(f'{n}_Fit_Chamber_Stringer_{int(d)}', 'SPACER', 'stringer between panel bays', 'ENGINEERING_FLEXIBLE', 'frame', 'arc',
                               a=(a0+.02, a1-.02), rho=(r-p['stringer_depth_m'], r), phi=(d-1.5, d+1.5)))
    # Spacer, Contain (aft = down, Culture 42!A3): the aft quadrant is the deck once the ship thrusts; a darker band keeps that orientation
    # legible in the microgravity spine. Great Union, Order: the same band is the route's orientation code.
    if p['deck_band']:
        for zone in ZONES:
            r, a0, a1 = ext[zone]
            out.append(element(f'{n}_Fit_{zone.title()}_Deck_Band', 'SPACER', 'orientation band: the aft side is the deck under thrust',
                               'ARTISTIC', 'band', 'arc', signage=True, a=(a0+.01, a1-.01), rho=(r-.004, r), phi=(160.0, 200.0)))
    # Ventilation: supply in the chamber, return in the node, so air crosses the route (no stagnant pockets in microgravity).
    if p['vents']:
        r, a0, a1 = ext['chamber']
        out.append(element(f'{n}_Fit_Supply_Diffuser', 'SPACER', 'ventilation supply diffuser', 'ENGINEERING_FLEXIBLE', 'grille', 'arc',
                           a=(a1-.65, a1-.20), rho=(r-.03, r), phi=(245.0, 262.0)))
        r, a0, a1 = ext['node']
        out.append(element(f'{n}_Fit_Return_Grille', 'SPACER', 'ventilation return grille', 'ENGINEERING_FLEXIBLE', 'grille', 'arc',
                           a=(a0+.20, a0+.60), rho=(r-.03, r), phi=(100.0, 125.0)))
    # Great Union, Order: hatch identity and route signs on the bulkhead faces crew look at as they come through, fore (ship +X) up, in one
    # standard placard design: the inner hatch and the route down the neck face outboard (arriving), the outer hatch faces inboard (leaving).
    plate = {'full': (.44, .14), 'plates': (.26, .09), 'minimal': (.34, .11)}[p['placards']]   # width, height
    rho = (st['r_hinge']+R)/2
    def placard(key, a, deg, facing):
        return element(f'{n}_Fit_Placard_{key.title()}', 'GREAT_UNION', f'{key} placard', 'ARTISTIC', 'placard', 'box', signage=True,
                       mount='bulkhead', facing=facing, centre=(a, rho, math.radians(deg)), size=(.012, plate[0], plate[1]), text=TEXT[key])
    out += [placard('outer', st['a_out']-.006, 180.0, 'inboard'), placard('inner', st['a_in']+.006, 0.0, 'outboard'),
            placard('route', st['node_in']+.006, 0.0, 'outboard')]
    # Great Union, Order: the standard hatch interface, one bezel and two guarded handles (equalize, release) beside each panel.
    pa, pt, pr = h['panel_size_m']
    for zone, a, deg in (('chamber', st['a_in']+.2+pa/2, h['panel_deg']), ('node', st['bottom']-.2-pa/2, h['node_panel_deg'])):
        r = ext[zone][0]
        out.append(element(f'{n}_Fit_{zone.title()}_Panel_Bezel', 'GREAT_UNION', 'standard hatch-interface bezel', 'ENGINEERING_FLEXIBLE', 'bezel', 'box',
                           centre=(a, r-.012, math.radians(deg)), size=(pa+.08, pt+.08, .024)))
        side = 1.0 if zone == 'chamber' else -1.0
        for k, dphi in enumerate((-7.0, 7.0), 1):
            b = a+side*(pa/2+.10)
            out.append(element(f'{n}_Fit_{zone.title()}_Panel_Handle_{k}', 'GREAT_UNION', ('equalize', 'hatch release')[k-1]+' handle, guarded',
                               'ENGINEERING_FLEXIBLE', 'handle', 'rod', radius=.012,
                               points=[he.world(f, b-.05, r, math.radians(deg+dphi)), he.world(f, b-.05, r-.06, math.radians(deg+dphi)),
                                       he.world(f, b+.05, r-.06, math.radians(deg+dphi)), he.world(f, b+.05, r, math.radians(deg+dphi))]))
    # Robocracy / Bolt-Sworn, Systemize: the service chase between the equalization valves, closed behind a cover or open behind guards.
    r, a0, a1 = ext['chamber']; chase = (202.0, 215.0)
    if p['chase'] == 'closed':
        out.append(element(f'{n}_Fit_Chase_Cover', 'BOLT_SWORN', 'service chase cover (valve lines, power, data), quarter-turn fasteners',
                           'ENGINEERING_FLEXIBLE', 'cover', 'arc', a=(a0+.10, a1-.10), rho=(r-.05, r), phi=chase))
    else:
        out.append(element(f'{n}_Fit_Chase_Back', 'BOLT_SWORN', 'open service chase', 'ENGINEERING_FLEXIBLE', 'chase', 'arc',
                           a=(a0+.10, a1-.10), rho=(r-.008, r), phi=chase))
        for k, (deg, paint) in enumerate(((204.5, 'pipe_air'), (208.5, 'pipe_water'), (212.5, 'pipe_power')), 1):
            out.append(element(f'{n}_Fit_Chase_Line_{k}', 'BOLT_SWORN', ('equalization air line', 'condensate line', 'power and data conduit')[k-1],
                               'ENGINEERING_FLEXIBLE', paint, 'rod', radius=.013,
                               points=[he.world(f, a0+.12, r-.03, math.radians(deg)), he.world(f, a1-.12, r-.03, math.radians(deg))]))
        for k, a in enumerate((a0+.6, a1-.6), 1):
            out.append(element(f'{n}_Fit_Chase_Tag_{k}', 'BOLT_SWORN', 'service tag', 'ARTISTIC', 'tag', 'box', signage=True,
                               centre=(a, r-.055, math.radians(208.5)), size=(.06, .10, .004)))
    # Emergency equipment station (12A SP-21) on the ship side of the inner hatch, reachable from the trunk and the chamber.
    r, a0, a1 = ext['node']; la = (a0+.35, a0+1.05); lp = (282.0, 308.0)
    if p['locker'] == 'closed':
        out.append(element(f'{n}_Fit_Emergency_Locker', 'SPACER', 'emergency locker: portable O2, extinguisher, leak kit, masks (SP-21)',
                           'ENGINEERING_FLEXIBLE', 'locker', 'arc', a=la, rho=(r-.15, r), phi=lp))
        out.append(element(f'{n}_Fit_Emergency_Mark', 'GREAT_UNION', 'emergency locker label', 'ARTISTIC', 'safety', 'box', signage=True,
                           centre=(sum(la)/2, r-.152, math.radians(sum(lp)/2)), size=(.12, .40, .004), text=TEXT['locker']))
    else:
        out.append(element(f'{n}_Fit_Emergency_Rack', 'BOLT_SWORN', 'open emergency rack (SP-21)', 'ENGINEERING_FLEXIBLE', 'chase', 'arc',
                           a=la, rho=(r-.03, r), phi=lp))
        for k, (deg, radius, paint) in enumerate(((287.5, .07, 'bottle_o2'), (295.0, .07, 'bottle_o2'), (302.5, .06, 'extinguisher')), 1):
            out.append(element(f'{n}_Fit_Emergency_Bottle_{k}', 'BOLT_SWORN', ('portable O2', 'portable O2', 'extinguisher')[k-1],
                               'ENGINEERING_FLEXIBLE', paint, 'cyl', radius=radius,
                               a=he.world(f, la[0]+.06, r-.03-radius, math.radians(deg)), b=he.world(f, la[1]-.06, r-.03-radius, math.radians(deg))))
    # Robocracy / Bolt-Sworn, Humanize: handholds beside each hatch to pull through in microgravity.
    if p['handholds']:
        for zone, a, degs in (('chamber', st['a_out']-.17, (127.0, 233.0)), ('chamber', st['a_in']+.15, (127.0, 233.0)), ('node', st['bottom']-.15, (112.0, 248.0))):
            r = ext[zone][0]
            for deg in degs:
                k = len([q for q in out if '_Handhold_' in q['name']])+1; half = math.degrees(.12/r)
                out.append(element(f'{n}_Fit_Handhold_{k}', 'BOLT_SWORN', 'handhold to pull through the hatch', 'ENGINEERING_FLEXIBLE', 'handle', 'rod',
                                   radius=.014, points=[he.world(f, a, r, math.radians(deg-half)), he.world(f, a, r-.07, math.radians(deg-half)),
                                                        he.world(f, a, r-.07, math.radians(deg+half)), he.world(f, a, r, math.radians(deg+half))]))
    # Spacer: a foot restraint across the deck band, so crew stand anchored and hands-free (the greeting's instructor stands in it).
    if p.get('foot_restraint'):
        r, a0, a1 = ext['chamber']; a = a0+.62*(a1-a0); half = math.degrees(.20/r)
        out.append(element(f'{n}_Fit_Foot_Restraint', 'SPACER', 'foot restraint on the deck band', 'ENGINEERING_FLEXIBLE', 'handle', 'rod', radius=.012,
                           points=[he.world(f, a, r, math.radians(180.0-half)), he.world(f, a, r-.06, math.radians(180.0-half)),
                                   he.world(f, a, r-.06, math.radians(180.0+half)), he.world(f, a, r, math.radians(180.0+half))]))
    # Spacer safety marks on the bulkhead faces round each hatch.
    if p['hatch_marks']:
        out.append(element(f'{n}_Fit_Outer_Hatch_Mark', 'SPACER', 'hatch rim safety mark', 'ARTISTIC', 'safety', 'ring', signage=True,
                           profile=[(st['a_out']-.006, st['r_hinge']), (st['a_out']-.006, st['r_hinge']+.10), (st['a_out'], st['r_hinge']+.10), (st['a_out'], st['r_hinge'])]))
        out.append(element(f'{n}_Fit_Inner_Hatch_Mark', 'SPACER', 'hatch rim safety mark', 'ARTISTIC', 'safety', 'ring', signage=True,
                           profile=[(st['a_in'], st['clear']), (st['a_in'], st['clear']+.12), (st['a_in']+.006, st['clear']+.12), (st['a_in']+.006, st['clear'])]))
    # Spacer, Contain: ring frames (last, so they break round the other wall elements) and stringers carry the replaceable wall panels (print, seal, replace) in a repeat grid of bays.
    if p['frame_depth_m'] > 0:
        for zone in ZONES:
            r, a0, a1 = ext[zone]
            for k in (1, 2):
                a = a0+(a1-a0)*k/3; w = p['frame_width_m']
                for j, (lo, hi) in enumerate(free_arcs(taken(zone, a)+mounted(zone, a), 2.0), 1):
                    out.append(element(f'{n}_Fit_{zone.title()}_Frame_{k}_{j}', 'SPACER', 'ring frame carrying the replaceable wall panels',
                                       'ENGINEERING_FLEXIBLE', 'frame', 'arc', a=(a-w/2, a+w/2), rho=(r-p['frame_depth_m'], r), phi=(lo, hi)))
    return out


def footprint(s, f, q):
    """(zone, a0, a1, phi0, phi1, inner rho) of a wall element, or None for rods, cylinders and rings."""
    ext = extents(s, f)
    if q.get('mount') == 'bulkhead':
        return None
    if q['shape'] == 'arc':
        a0, a1 = q['a']; lo, hi = q['phi']; inner = q['rho'][0]
    elif q['shape'] == 'box':
        a, rho, phi = q['centre']; la, lt, lr = q['size']; a0, a1 = a-la/2, a+la/2
        half = math.degrees(lt/2/rho); lo, hi = math.degrees(phi)-half, math.degrees(phi)+half; inner = rho-lr/2
    else:
        return None
    zone = next(z for z, (r, b0, b1) in ext.items() if b0-.01 <= (a0+a1)/2 <= b1+.01)
    return zone, a0, a1, lo, hi, inner


def check(s, f, scheme=None):
    """Failures: an element inside the passage (closer to the axis than the valves already are), across a parked leaf, light strip or panel
    window, or on the same patch of wall as another element (bands lie under the rest and are exempt)."""
    st = he.stations(s, f); h = s['human_entry']; floor = h['valve_rho_m']; fails = []
    els = elements(s, f, scheme); win = blocked(s, f)
    pts = lambda q: q['points'] if q['shape'] == 'rod' else [q['a'], q['b']] if q['shape'] == 'cyl' else []
    for q in els:
        if q['shape'] in ('rod', 'cyl'):
            rho = min(he.local(f, v)[1] for v in pts(q))-q['radius']
            if rho < floor:
                fails.append(f"{q['name']}: {rho:.3f} m from the passage axis, inside the valves' {floor:.2f} m")
            continue
        if q.get('mount') == 'bulkhead':
            rho = q['centre'][1]; lo, hi = rho-q['size'][2]/2, rho+q['size'][2]/2
            if lo < st['r_hinge']+.02 or hi > st['chamber_r']-.02:
                fails.append(f"{q['name']}: not between the hatch frame and the wall")
            continue
        fp = footprint(s, f, q)
        if fp is None:
            continue
        zone, a0, a1, lo, hi, inner = fp
        if inner < floor:
            fails.append(f"{q['name']}: inner face {inner:.3f} m from the axis, inside the valves' {floor:.2f} m")
        if any(k in q['name'] for k in ('Deck_Band', '_Frame_', 'Stringer', 'Panel_Bezel')):
            continue
        for z, b0, b1, wlo, whi in win:
            if z == zone and a0 < b1 and b0 < a1 and overlaps((lo, hi), (wlo, whi)):
                fails.append(f"{q['name']}: on a taken window ({z} a {b0:.2f}-{b1:.2f}, phi {wlo:.0f}-{whi:.0f})")
    walls = [(q['name'], footprint(s, f, q)) for q in els if q['shape'] in ('arc', 'box') and 'Deck_Band' not in q['name'] and q.get('mount') != 'bulkhead']
    for i, (na, pa) in enumerate(walls):
        for nb, pb in walls[i+1:]:
            if pa[0] == pb[0] and pa[1] < pb[2] and pb[1] < pa[2] and overlaps(pa[3:5], pb[3:5]) and not ('Frame' in na and 'Frame' in nb):
                # Labels sit on their locker or panel face, and frames cross stringers by design.
                if {na.split('_Fit_')[1], nb.split('_Fit_')[1]} in ({'Emergency_Mark', 'Emergency_Locker'}, ) or \
                        ('Chase_Back' in na+nb and 'Chase_Tag' in na+nb):
                    continue
                if ('Frame' in na or 'Stringer' in na) and ('Frame' in nb or 'Stringer' in nb):
                    continue
                fails.append(f'{na} and {nb} overlap')
    return fails


# 3.1: scheme D carried along the trunk and onto the sector landing. Trunk elements are in the vehicle frame about the ship axis ('xarc': x0..x1,
# rho0..rho1, phi0..phi1 in degrees, angle measured as crew_transfer.radial); landing elements in the sector frame of human_entry.landing
# (origin on the centreline at the deck, +X axial, +Y radially outward, +Z tangential), shared by every sector. 'wbox' is a box with a
# centre, three unit axes and a size along them (a placard's text lies on the face along its third axis, upright along its second);
# 'ring' an (a, rho) profile revolved about the line from base to tip.
BRANCH_TEXT = {'Crew_Connector_Airlock_EVA': 'EVA AIRLOCK', 'Crew_Connector_Dock_Primary': 'D1 DOCK PRIMARY', 'Crew_Connector_Dock_Service': 'D2 SERVICE DOCK',
               'Crew_Refuge_Port': 'STORM REFUGE', 'Crew_Store_Port': 'SP-45 STORE', 'Crew_Port_1_1': 'RING A', 'Crew_Port_2_2': 'RING B'}
SECTOR_TEXT = {'HABITATION': 'HABITATION', 'WORK_MEDICAL_OPS': 'WORK  MEDICAL  OPS', 'LIFE_SUPPORT_GARDEN_COMMON': 'GARDEN  LIFE SUPPORT'}


def trunk_extent(s):
    import crew_transfer
    c = s['crew_transfer']; trunk = crew_transfer.stationary(s)[0]
    return c['trunk_clear_radius_m'], trunk['points'][0][0]+c['passage_wall_m'], trunk['points'][1][0]-c['passage_wall_m']


def trunk_windows(s):
    """Angle windows (degrees) along the whole trunk that the fit-out keeps off: the handrails and their brackets, the light strips and the
    ladder with its brackets and arrest rail; plus (x0, x1, phi0, phi1) windows of the refuge port's rails."""
    h = s['human_entry']; tr, _, _ = trunk_extent(s); L = he.trunk_ladder(s); deg = math.degrees
    out = [(d-deg(.05/tr)-2.0, d+deg(.05/tr)+2.0) for d in h['trunk_handrail_deg']]
    out += [(d-deg(h['light_size_m'][1]/2/tr)-2.0, d+deg(h['light_size_m'][1]/2/tr)+2.0) for d in h['trunk_light_deg']]
    out += [(deg(L['th']-L['phi'])-5.0, deg(L['th']+L['phi'])+5.0)]
    local = []
    for x, th, r in he.port_rail_stations(s):
        g = r+h['opening_margin_m']+h['refuge_port_rail_m']+.10; d = deg(th)
        local.append((x-g, x+g, d-deg(.05/tr)-2.0, d+deg(.05/tr)+2.0))
    return out, local


def trunk_elements(s, scheme=None):
    """3.1: the trunk under scheme D. Spacer: ring frames every trunk_frame_pitch_m carrying the wall panels, broken round the fixtures and
    clear of every branch opening. Great Union: a route stripe at route_stripe_deg the length of the trunk (it breaks at the openings) with a
    placard on it at each branch (the open side's nearest clear stretch when the branch cuts the stripe) and orange chevrons every
    chevron_pitch_m pointing to the storm refuge, the emergency destination. Spacer: a supply diffuser at the aft (floor) end, so the air sweeps
    forward to the node's return."""
    p = scheme or s['route_fitout']; tr, x0, x1 = trunk_extent(s); win, local = trunk_windows(s); out = []
    clear = lambda x, d, m=.10: any(a <= x <= b for a, b in he.clear_spans(s, tr, math.radians(d), x0, x1, margin=m))
    S, half = p['route_stripe_deg'], p['route_stripe_width_deg']/2; pw, ph = p['trunk_placard_m']; phw = math.degrees(pw/2/tr)
    spans = [(a, b) for a, b in he.clear_spans(s, tr, math.radians(S-half), x0, x1) if b-a > .3]
    spans = [(max(a, c), min(b, d)) for a, b in spans for c, d in he.clear_spans(s, tr, math.radians(S+half), x0, x1) if min(b, d)-max(a, c) > .3]
    for k, (a, b) in enumerate(spans, 1):
        out.append(element(f'Trunk_Fit_Route_Stripe_{k}', 'GREAT_UNION', 'route stripe: the way along the trunk, its branches and the refuge', 'ARTISTIC',
                           'band', 'xarc', signage=True, x=(a, b), rho=(tr-.004, tr), phi=(S-half, S+half)))
    placed = []
    for n, x, th, r in he.openings(s):
        if n not in BRANCH_TEXT:
            continue
        inside = [(a, b) for a, b in spans if a+ph/2+.05 <= x <= b-ph/2-.05]
        if inside:
            xc = x
        else:   # the branch cuts the stripe: on the nearest stretch's end toward it
            a, b = min(spans, key=lambda q: min(abs(q[0]-x), abs(q[1]-x)))
            xc = a+ph/2+.10 if abs(a-x) < abs(b-x) else b-ph/2-.10
        while any(abs(xc-q) < ph+.05 for q in placed):     # two branches at one station: the next placard one step away from them
            xc += math.copysign(ph+.05, xc-x)
        placed.append(xc)
        tag = 'Store_Port' if n == 'Crew_Store_Port' else n.split("_", 2)[-1]       # the refuge port's placard keeps its name 'Port'
        out.append(element(f'Trunk_Fit_Placard_{tag}', 'GREAT_UNION', f'branch placard: {BRANCH_TEXT[n].lower()}', 'ARTISTIC', 'placard', 'wbox',
                           signage=True, centre=crew_transfer_radial(xc, tr-.006, S), axes=trunk_axes(S), size=(ph, pw, .012), text=BRANCH_TEXT[n]))
    ref = he.refuge_station(s)['x']; dphi = math.degrees(.05/tr); k = 0
    for a, b in spans:
        for i in range(int((b-a-.4)/p['chevron_pitch_m'])+1):
            x = a+.2+i*p['chevron_pitch_m']; d = math.copysign(1.0, ref-x)
            if abs(ref-x) < .8 or any(abs(x-q) < ph/2+.20 for q in placed) or not a+.1 <= x+d*.06 <= b-.1:
                continue
            k += 1
            out.append(element(f'Trunk_Fit_Refuge_Chevron_{k}', 'GREAT_UNION', 'chevron toward the storm refuge', 'ARTISTIC', 'safety', 'rod', signage=True,
                               radius=.008, points=[crew_transfer_radial(x-d*.03, tr-.009, S-dphi), crew_transfer_radial(x+d*.03, tr-.009, S),
                                                    crew_transfer_radial(x-d*.03, tr-.009, S+dphi)]))
    # The supply diffuser: on the wall opposite the ladder at the floor end, where the trunk ends aft.
    da, db = p['trunk_diffuser_deg']; xa, xb = x0+.25, x0+.70
    if all(clear(x, d) for x in (xa, xb) for d in (da, db)):
        out.append(element('Trunk_Fit_Supply_Diffuser', 'SPACER', 'ventilation supply diffuser: air sweeps forward to the node return',
                           'ENGINEERING_FLEXIBLE', 'grille', 'xarc', x=(xa, xb), rho=(tr-.03, tr), phi=(da, db)))
    taken = win
    if 'Trunk_Fit_Supply_Diffuser' in [q['name'] for q in out]:
        diffuser = (xa-.1, xb+.1, da-2.0, db+2.0)
    else:
        diffuser = None
    w = p['frame_width_m']; n = int((x1-x0)/p['trunk_frame_pitch_m'])
    for i in range(1, n+1):
        x = x0+i*(x1-x0)/(n+1); cuts = list(taken)
        cuts += [(lo, hi) for a, b, lo, hi in local+([diffuser] if diffuser else []) if a <= x <= b]
        cuts += [(S-phw-2.0, S+phw+2.0) for q in placed if abs(x-q) < ph/2+w/2+.05]     # frames cross the stripe, not its placards
        free = [d for d in range(0, 360, 2) if clear(x-w/2, d, .15) and clear(x+w/2, d, .15)]
        cuts += [(d, d+2) for d in range(0, 360, 2) if d not in free]
        for j, (lo, hi) in enumerate(free_arcs(cuts, 1.0), 1):
            if hi-lo >= 15.0:
                out.append(element(f'Trunk_Fit_Frame_{i}_{j}', 'SPACER', 'ring frame carrying the replaceable trunk wall panels', 'ENGINEERING_FLEXIBLE',
                                   'frame', 'xarc', x=(x-w/2, x+w/2), rho=(tr-p['frame_depth_m'], tr), phi=(lo, hi)))
    return out


def crew_transfer_radial(x, r, deg):
    return (x, r*math.cos(math.radians(deg)), r*math.sin(math.radians(deg)))


def trunk_axes(deg):
    """A trunk-wall placard's axes: along X (fore, its text's up... second axis), tangential and toward the axis (its face)."""
    a = math.radians(deg)
    return ((0.0, -math.sin(a), math.cos(a)), (1.0, 0.0, 0.0), (0.0, -math.cos(a), -math.sin(a)))


def landing_elements(s, scheme=None):
    """3.1: the landing under scheme D, in the shared sector frame. Great Union: the standard hatch-interface bezel behind the landing's hatch
    panel with its guarded equalize and release handles below it, and a route placard above it (up the ladder: the tube, the refuge, the docks).
    Spacer: an orange safety mark round the hatch frame under the overhead. Bolt-Sworn: service tags on the chase. The sector's identity
    placard is the interior's (sector_sign), since every sector shares this landing."""
    h = s['human_entry']; L = he.landing(s); side = L['side']; zc = L['chase_face']; n = (0.0, 0.0, -side)
    pw, ph, pd = h['landing_panel_size_m']; xp = L['x']-h['landing_well_width_m']/2+.04+pw/2; yp = -h['landing_panel_height_m']
    ax = ((1.0, 0.0, 0.0), (0.0, -1.0, 0.0), n); on = lambda d: zc-side*d       # a point d off the chase face, into the well
    out = [element('Landing_Fit_Panel_Bezel', 'GREAT_UNION', 'standard hatch-interface bezel', 'ENGINEERING_FLEXIBLE', 'bezel', 'wbox',
                   centre=(xp, yp, on(.012)), axes=ax, size=(pw+.08, ph+.08, .024))]
    yh = yp+ph/2+.09
    for k, dx in enumerate((-.07, .07), 1):
        x = xp+dx
        out.append(element(f'Landing_Fit_Panel_Handle_{k}', 'GREAT_UNION', ('equalize', 'hatch release')[k-1]+' handle, guarded', 'ENGINEERING_FLEXIBLE',
                           'handle', 'rod', radius=.012, points=[(x-.045, yh, zc), (x-.045, yh, on(.06)), (x+.045, yh, on(.06)), (x+.045, yh, zc)]))
    out.append(element('Landing_Fit_Placard_Route', 'GREAT_UNION', 'route placard', 'ARTISTIC', 'placard', 'wbox', signage=True,
                       centre=(xp, yp-ph/2-.37, on(.006)), axes=ax, size=(.26, .12, .012), text='UP: CREW TUBE\nREFUGE  DOCKS'))
    rf, y = L['frame_r'], L['ceiling']
    out.append(element('Landing_Fit_Hatch_Mark', 'SPACER', 'hatch rim safety mark', 'ARTISTIC', 'safety', 'ring', signage=True,
                       base=(L['x'], 0.0, L['z']), tip=(L['x'], -1.0, L['z']), profile=[(-y-.005, rf), (-y-.005, rf+.10), (-y, rf+.10), (-y, rf)]))
    for k, yt in enumerate((-.60, -2.60), 1):
        out.append(element(f'Landing_Fit_Chase_Tag_{k}', 'BOLT_SWORN', 'service tag: leaf drive, equalization, power and data', 'ARTISTIC', 'tag', 'wbox',
                           signage=True, centre=(L['x']+.29, yt, on(.002)), axes=ax, size=(.06, .10, .004)))
    return out


def sector_sign(s, function):
    """3.1: the sector's identity placard (Great Union wayfinding) on the landing chase above the route placard, built with the function's
    interior: the sector number follows from habitat_ring.sector_functions, the same on both rings (the ring letter stays at the vestibule)."""
    L = he.landing(s); side = L['side']; h = s['human_entry']; pw, ph, _ = h['landing_panel_size_m']
    xp = L['x']-h['landing_well_width_m']/2+.04+pw/2; yp = -h['landing_panel_height_m']-ph/2-.67; k = s['habitat_ring']['sector_functions'].index(function)+1
    return [element('Sector_Fit_Placard', 'GREAT_UNION', 'sector identity placard', 'ARTISTIC', 'placard', 'wbox', signage=True,
                    centre=(xp, yp, L['chase_face']-side*.006), axes=((1.0, 0.0, 0.0), (0.0, -1.0, 0.0), (0.0, 0.0, -side)), size=(.26, .14, .012),
                    text=f'SECTOR {k}\n{SECTOR_TEXT[function]}')]



# 3.1 (since Q46): scheme D in the despun transfer drum and at both ends of every crew tube, rotor-local at the index (the drum's elements ride
# on Drum_j, the tubes' on Rotor_j). 'tarc' is a curved wall element about a tube segment's axis: from origin along d by t0..t1, rho0..rho1,
# phi0..phi1 in degrees from n1 toward n2.
def on_wall(r, half, depth):
    """Distance from the axis of a flat plate's centre that lies on a cylindrical wall of radius r with its edges (half-width half) touching it."""
    return r-(r-math.sqrt(r*r-half*half))-depth/2


def drum_axes(th):
    """A drum outer-wall plate's axes at angle th: tangential (its width), along X (fore, its text's up) and toward the axis (its face)."""
    return ((0.0, -math.sin(th), math.cos(th)), (1.0, 0.0, 0.0), (0.0, -math.cos(th), -math.sin(th)))


def sector_label(s, k):
    return SECTOR_TEXT[s['habitat_ring']['sector_functions'][k-1]]


def drum_elements(s, j):
    """3.1: drum j under scheme D. Great Union: beside each crew-tube opening, toward its handrail, a placard with the ring letter, the sector
    and its function (the ring letter lives here, the sector number is the same on both rings), with a Bolt-Sworn service tag for the drum
    door's drive and seal below it; the aft end wall, the floor under thrust, is the deck band. Spacer: an orange moving-edge mark on both end
    walls' inner rims, where the despun drum turns past the stationary spine; axial frames on the outer wall every drum_rib_pitch_deg, clear of
    the openings and fixtures, above the crawl rail. Great Union: the standard bezel behind the transfer panel."""
    p = s['route_fitout']; h = s['human_entry']; rot, v, la = he.vestibule_station(s, j); L = 'AB'[j-1]; n = f'Crew_Vestibule_{j}_Fit'
    R, w, r0 = v['clear'], h['chamber_wall_m'], v['r0']; a0, a1 = v['cu0']+w, v['cu1']-w; deg, rad = math.degrees, math.radians; out = []
    pw, ph = p['drum_placard_m']; off = p['drum_placard_deg']; uc = a0+h['crawl_rail_height_m']; m = .10
    out.append(element(f'{n}_Deck_Band', 'SPACER', 'orientation band: the aft end wall is the deck under thrust', 'ARTISTIC', 'band', 'ring', signage=True,
                       base=(a0, 0.0, 0.0), tip=(a0+1.0, 0.0, 0.0), profile=[(0.0, r0+m), (.004, r0+m), (.004, R-.03), (0.0, R-.03)]))
    for k, (u, e) in enumerate(((a0, 1.0), (a1, -1.0)), 1):
        out.append(element(f'{n}_Edge_Mark_{k}', 'SPACER', 'moving-edge mark: the drum turns past the stationary spine', 'ARTISTIC', 'safety', 'ring',
                           signage=True, base=(u, 0.0, 0.0), tip=(u+e, 0.0, 0.0), profile=[(0.0, r0), (.005, r0), (.005, r0+m), (0.0, r0+m)]))
    uf = v['hatch_u']+min(.35, (a1-a0)/2-ph/2-.15); taken = []
    for k, a in la.items():
        th = a+rad(off)
        out.append(element(f'{n}_Placard_{k}', 'GREAT_UNION', f'drum opening placard: ring {L} sector {k}', 'ARTISTIC', 'placard', 'wbox', signage=True,
                           centre=ct.radial(uf, on_wall(R, pw/2, .012), th), axes=drum_axes(th), size=(pw, ph, .012),
                           text=f'RING {L}  SECTOR {k}\n{sector_label(s, k)}'))
        out.append(element(f'{n}_Door_Tag_{k}', 'BOLT_SWORN', 'service tag: drum door drive and seal', 'ARTISTIC', 'tag', 'wbox', signage=True,
                           centre=ct.radial(uf-ph/2-.10, on_wall(R, .03, .004), th), axes=drum_axes(th), size=(.06, .10, .004)))
        taken.append((off-deg(pw/2/R)-2.0+deg(a), off+deg(pw/2/R)+2.0+deg(a)))
    pa, pt, pr = h['panel_size_m']; th = la[v['ports'][0]]+rad(h['vestibule_handrail_offset_deg']+h['vestibule_panel_offset_deg'])
    out.append(element(f'{n}_Panel_Bezel', 'GREAT_UNION', 'standard hatch-interface bezel: the transfer panel', 'ENGINEERING_FLEXIBLE', 'bezel', 'wbox',
                       centre=ct.radial((a0+a1)/2, on_wall(R, pt/2+.04, .024), th), axes=drum_axes(th), size=(pt+.08, pa+.08, .024)))
    taken.append((deg(th)-deg(pt/2/R)-4.0, deg(th)+deg(pt/2/R)+4.0))
    for a in la.values():
        taken += [(deg(a)+d-4.0, deg(a)+d+4.0) for d in (h['vestibule_handrail_offset_deg'],)]
        taken += [(deg(a)+h['vestibule_light_offset_deg']-deg(h['light_size_m'][1]/2/R)-3.0, deg(a)+h['vestibule_light_offset_deg']+deg(h['light_size_m'][1]/2/R)+3.0)]
    edge = v['port_clear']+h['hatch_frame_width_m']+.05; fw = p['frame_width_m']; k = 0
    for i in range(int(360/p['drum_rib_pitch_deg'])):
        d = (i+.5)*p['drum_rib_pitch_deg']
        if any(abs((d-deg(a)+180) % 360-180) < 90 and R*math.sin(rad(abs((d-deg(a)+180) % 360-180))) < edge+fw/2 for a in la.values()):
            continue
        if any(overlaps((d-deg(fw/2/R), d+deg(fw/2/R)), q) for q in taken):
            continue
        k += 1
        out.append(element(f'{n}_Frame_{k}', 'SPACER', 'axial frame carrying the replaceable drum wall panels', 'ENGINEERING_FLEXIBLE', 'frame', 'xarc',
                           x=(uc+h['handrail_radius_m']+.04, a1-.02), rho=(R-p['frame_depth_m'], R), phi=(d-deg(fw/2/R), d+deg(fw/2/R))))
    return out


def tube_end_elements(s, j):
    """3.1: both ends of rotor j's crew tubes under scheme D, on the run beside the ladder at the tube-side hatch panel's angle. Great Union: at
    the sector end the standard bezel behind the hatch panel, its guarded equalize and release handles below it (outboard, down in spin) and a
    placard above it (DOWN: the sector and its function); at the top of the run a placard back up (the ring's drum, the spine, the refuge and
    the docks). Spacer: a deck band along the run's aft wall, the floor when the ship thrusts (Q47: the run is level and walked on it)."""
    p = s['route_fitout']; h = s['human_entry']; rot, v, la, frames = he.spoke_station(s, j); L = 'AB'[j-1]; rc = ct.tube_radii(s, j)[1]
    P, R_ = ct.tube_point, he.RUN; floor = habitat_ring.floor(s); pw_, ph_, pd_ = h['landing_panel_size_m']; out = []
    th = math.pi-math.radians(h['spoke_hatch_panel_deg']); bw = p['tube_band_width_deg']/2
    for k, fr in frames.items():
        n = f'Crew_Tube_{j}_{k}_Fit'; d, n1, n2 = fr['d'][R_], fr['n1'][R_], fr['n2'][R_]; t0, t1 = he.run_span(s, fr)
        rad = tuple(math.cos(th)*a+math.sin(th)*b for a, b in zip(n1, n2)); tan = tuple(-math.sin(th)*a+math.cos(th)*b for a, b in zip(n1, n2))
        ax = (tan, tuple(-x for x in d), tuple(-x for x in rad))
        base = floor-ct.dot(fr['points'][R_], d); ys = he.rung_heights(s, t0+h['handrail_radius_m']-base, t1-h['handrail_radius_m']-base)
        tp = max(ys)-h['landing_panel_height_m']+base           # the hatch panel's centre, as spoke_fixtures places it
        out.append(element(f'{n}_Panel_Bezel', 'GREAT_UNION', 'standard hatch-interface bezel: the sector hatch, tube side', 'ENGINEERING_FLEXIBLE', 'bezel',
                           'wbox', centre=P(fr, R_, on_wall(rc, pw_/2+.04, .024), th, tp), axes=ax, size=(pw_+.08, ph_+.08, .024)))
        th_h = tp+ph_/2+.09
        for i, dx in enumerate((-.07, .07), 1):
            a = lambda e: th+(dx+e)/rc
            out.append(element(f'{n}_Panel_Handle_{i}', 'GREAT_UNION', ('equalize', 'hatch release')[i-1]+' handle, guarded', 'ENGINEERING_FLEXIBLE',
                               'handle', 'rod', radius=.012, points=[P(fr, R_, rc, a(-.045), th_h), P(fr, R_, rc-.06, a(-.045), th_h),
                                                                     P(fr, R_, rc-.06, a(.045), th_h), P(fr, R_, rc, a(.045), th_h)]))
        pw, ph = p['tube_placard_m']
        for key, t, text in (('Down', tp-ph_/2-.05-ph/2, f'DOWN: SECTOR {k}\n{sector_label(s, k)}'),
                             ('Up', t0+.60, f'UP: RING {L} DRUM\nSPINE  REFUGE  DOCKS')):
            out.append(element(f'{n}_Placard_{key}', 'GREAT_UNION', f'tube placard: {text.splitlines()[0].lower()}', 'ARTISTIC', 'placard', 'wbox',
                               signage=True, centre=P(fr, R_, on_wall(rc, pw/2, .012), th, t), axes=ax, size=(pw, ph, .012), text=text))
        psi = math.degrees(math.atan2(-n2[0], -n1[0]))     # the run's aft-down floor line (-X; floor_ladders' psi on a level leg)
        out.append(element(f'{n}_Deck_Band', 'SPACER', 'orientation band: the run\'s aft wall is the floor under thrust', 'ARTISTIC', 'band', 'tarc',
                           signage=True, origin=fr['points'][R_], d=d, n1=n1, n2=n2, t=(t0+.40, t1-.20), rho=(rc-.004, rc), phi=(psi-bw, psi+bw)))
    return out

# 3.2: the sector fit-out in the shared sector frame, per function, built with the function's interior (both rings). The defaults are the
# picks of studies/induction_sector_fitout.py ([route_fitout] sector_*, seraph_*): scheme A "Layered" and Seraph's work post; the study passes
# its other variants (B's exposed utility spine, Seraph's berth) as arguments. Nothing enters the swept aisle or landing well: placards on an
# aisle face sit flush in it, and the service block's open face is recessed by SERVICE_RECESS_M with its lines inside (sector_check).
ROOM_TEXT = {'HABITATION': [('Hygiene', 'inner', 'HYGIENE', -1.80), ('Bunk_2', 'aft', 'BERTHS 1-6', -1.75)],
             'WORK_MEDICAL_OPS': [('Medical_Couch', 'aft', 'MEDICAL', -0.95), ('Ops_Stations', 'aft', 'OPERATIONS', -1.45),
                                  ('Lab_Bench', 'inner', 'LAB', -1.85), ('Workbench', 'inner', 'WORKSHOP', -1.85)],
             'LIFE_SUPPORT_GARDEN_COMMON': [('Garden_Rack_1', 'aft', 'GARDEN', -1.75), ('ECLSS_Bay', 'aft', 'LIFE SUPPORT', -1.95)]}
SERVICE_RECESS_M = 0.06
SERVICE_DROP = {'HABITATION': 'Hygiene', 'WORK_MEDICAL_OPS': 'Workbench', 'LIFE_SUPPORT_GARDEN_COMMON': 'ECLSS_Bay'}


def face_frame(b, face):
    """Centre line and axes of a block's face: (point on the face at mid-span, axes (along the face, up, outward normal))."""
    import sector_whitebox
    n = {'inner': (0.0, 0.0, -b['side']), 'aft': (-1.0, 0.0, 0.0), 'fore': (1.0, 0.0, 0.0), 'outer': (0.0, 0.0, b['side'])}[face]
    c = [(b['min'][k]+b['max'][k])/2 for k in range(3)]
    k = 0 if n[0] else 2; c[k] = b['max'][k] if n[k] > 0 else b['min'][k]
    along = (0.0, 0.0, 1.0) if n[0] else (1.0, 0.0, 0.0)
    return c, (along, (0.0, -1.0, 0.0), n)


def sector_elements(s, function, scheme=None):
    """3.2: the sector's fit-out (sector frame); scheme defaults to the pick, A. Spacer: overhead frames carrying the replaceable overhead panels, broken
    round the hatch's safety mark and the aisle lights, a supply diffuser in the overhead and a return grille on the aft bulkhead above the aisle
    (air crosses the sector over the people). Great Union: a route band on the overhead along the aisle's well side, with chevrons pointing to
    the landing, and a placard on each room. Bolt-Sworn: the service block forward on side -1 (hygiene, workbench, life-support bay) shows its
    lines on its face with service tags; a tool rail on the workshop's tool wall. 'spine': an exposed utility spine (duct, cable tray, two
    lines) along the overhead over side +1's aisle edge, crossing over at the service block. Seraph (SP-31): see seraph_elements."""
    import habitat_interior
    h = s['human_entry']; L = he.landing(s); sec = habitat_interior.section(s); c = sec['ceiling_y_m']; i = s['interior']
    xl = sec['length_m']/2-i['end_allowance_m']; wall = habitat_interior.wall_half_width(s, c)-i['wall_allowance_m']; aisle = i['aisle_m']/2
    blocks = {b['name']: b for b in habitat_interior.zones(s, function)}; out = []; side = L['side']
    scheme = scheme or dict(frame_pitch_m=s['route_fitout']['sector_frame_pitch_m'])
    def box(name, grammar, function_, cls, paint, lo, hi, signage=False, **kw):
        ctr = tuple((lo[k]+hi[k])/2 for k in range(3)); size = tuple(abs(hi[k]-lo[k]) for k in range(3))
        out.append(element(name, grammar, function_, cls, paint, 'wbox', signage, centre=ctr, axes=((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)), size=size, **kw))
    mark = L['frame_r']+.10+.05                      # the hatch's rim mark and a margin, about the hatch axis
    lights = [(xa-h['light_size_m'][0]/2, xa+h['light_size_m'][0]/2) for xa in h['landing_aisle_light_x_m']]
    spine_z = (aisle-.15, aisle+.65) if scheme.get('spine') else None
    p = scheme.get('frame_pitch_m', 0.0)
    if p:
        n = int(2*xl/p)
        for k in range(n+1):
            x = -xl+k*2*xl/n; cuts = []
            if abs(x-L['x']) < mark:
                d = math.sqrt(mark**2-(x-L['x'])**2); cuts.append((L['z']-d, L['z']+d))
            if any(a-.05 <= x <= b+.05 for a, b in lights):
                cuts.append((-.08, .08))
            if spine_z:
                cuts.append(spine_z)
            pieces = [(-wall, wall)]
            for a, b in cuts:
                pieces = [q for lo, hi in pieces for q in ((lo, min(hi, a)), (max(lo, b), hi)) if q[1]-q[0] > .15]
            for j, (lo, hi) in enumerate(pieces, 1):
                box(f'Sector_Fit_Frame_{k}_{j}', 'SPACER', 'overhead frame carrying the replaceable overhead panels', 'ENGINEERING_FLEXIBLE', 'frame',
                    (x-.03, c, lo), (x+.03, c+.035, hi))
    if scheme.get('vents', True):
        box('Sector_Fit_Supply_Diffuser', 'SPACER', 'ventilation supply diffuser over side +1', 'ENGINEERING_FLEXIBLE', 'grille', (.60, c, 1.55), (1.20, c+.03, 1.95))
        box('Sector_Fit_Return_Grille', 'SPACER', 'ventilation return grille on the aft bulkhead above the aisle', 'ENGINEERING_FLEXIBLE', 'grille',
            (-xl-.10, -2.60, -.35), (-xl-.07, -2.30, .35))
    if scheme.get('route_band', True):
        z0, z1 = sorted((side*aisle, side*(aisle-.12))); dz = math.sqrt(max(mark**2-(L['z']-z0)**2, 0.0))
        for k, (a, b) in enumerate(((-xl, L['x']-dz), (L['x']+dz, xl)), 1):
            box(f'Sector_Fit_Route_Band_{k}', 'GREAT_UNION', 'route band: the way to the landing and the refuge', 'ARTISTIC', 'band', (a, c, z0), (b, c+.004, z1), signage=True)
            d = 1.0 if k == 1 else -1.0; zm = (z0+z1)/2
            for j in range(int((b-a-.2)/.45)+1):
                x = (a+.15+j*.45) if k == 1 else (b-.15-j*.45)
                out.append(element(f'Sector_Fit_Route_Chevron_{k}_{j+1}', 'GREAT_UNION', 'chevron toward the landing', 'ARTISTIC', 'safety', 'rod', True, radius=.008,
                                   points=[(x-d*.03, c+.009, zm-.04), (x+d*.03, c+.009, zm), (x-d*.03, c+.009, zm+.04)]))
    if scheme.get('placards', True):
        for name, face, text, y in ROOM_TEXT[function]:
            ctr, ax = face_frame(blocks[name], face); n = ax[2]
            inset = -SERVICE_RECESS_M if name == SERVICE_DROP[function] and blocks[name]['zone'] != 'workshop' else 0.0
            d = inset+(-.006 if face == 'inner' and blocks[name]['open'] == 'aisle' or inset else .006)     # flush on an aisle face
            out.append(element(f'Sector_Fit_Room_{name}', 'GREAT_UNION', f'room placard: {text.lower()}', 'ARTISTIC', 'placard', 'wbox', True,
                               centre=(ctr[0]+n[0]*d, y, ctr[2]+n[2]*d), axes=ax, size=(.30, .09, .012), text=text))
    # Bolt-Sworn: the service block's lines (air, water, power) and tags in its recessed open face (service_recess); at the workshop they run
    # along the tool wall above the bench top instead, out of the way of the work.
    b = blocks[SERVICE_DROP[function]]; lines = ('air line', 'water line', 'power and data conduit'); paints = ('pipe_air', 'pipe_water', 'pipe_power')
    if b['zone'] == 'workshop':
        zt = b['min'][2]+.05; y0 = -s['sector_whitebox']['bench_height_m']-.18; top = y0; drop_at = (b['max'][0]-.10, zt)
        ax = ((1.0, 0.0, 0.0), (0.0, -1.0, 0.0), (0.0, 0.0, 1.0))
        for k in range(3):
            out.append(element(f'Sector_Fit_Service_Line_{k+1}', 'BOLT_SWORN', lines[k], 'ENGINEERING_FLEXIBLE', paints[k], 'rod', radius=.014,
                               points=[(b['min'][0]+.05, y0-.08*k, zt), (b['max'][0]-.05, y0-.08*k, zt)]))
        tags = [(b['min'][0]+.25, y0+.10, zt-.03), (b['max'][0]-.30, y0+.10, zt-.03)]
    else:
        face = 'aft' if b['open'] == 'aft' else 'inner'; ctr, ax = face_frame(b, face); n = ax[2]; al = ax[0]
        span = (b['max'][2]-b['min'][2]) if face == 'aft' else (b['max'][0]-b['min'][0]); top = b['min'][1]+.10
        for k, off in enumerate((-.25, 0.0, .25)):
            q = tuple(ctr[j]+al[j]*off*span*.6-n[j]*(SERVICE_RECESS_M-.025) for j in range(3))
            out.append(element(f'Sector_Fit_Service_Line_{k+1}', 'BOLT_SWORN', lines[k], 'ENGINEERING_FLEXIBLE', paints[k], 'rod', radius=.014,
                               points=[(q[0], s['route_fitout'].get('service_line_end_y_m', {}).get(function, -.10), q[2]), (q[0], top, q[2])]))
        q = tuple(ctr[j]-n[j]*(SERVICE_RECESS_M-.025) for j in range(3)); drop_at = (q[0], q[2])
        tags = [tuple(ctr[j]+al[j]*.40*span*.6-n[j]*(SERVICE_RECESS_M-.002) for j in range(3)) for _ in (0, 1)]
        tags = [(tags[0][0], -.60, tags[0][2]), (tags[1][0], -1.40, tags[1][2])]
    for k, q in enumerate(tags, 1):
        out.append(element(f'Sector_Fit_Service_Tag_{k}', 'BOLT_SWORN', 'service tag', 'ARTISTIC', 'tag', 'wbox', True, centre=q, axes=ax, size=(.06, .10, .004)))
    if function == 'WORK_MEDICAL_OPS':
        w = blocks['Workbench']; zr = w['min'][2]+.06
        out.append(element('Sector_Fit_Tool_Rail', 'BOLT_SWORN', 'tool rail on the workshop tool wall', 'ENGINEERING_FLEXIBLE', 'handle', 'rod', radius=.012,
                           points=[(w['min'][0]+.10, -1.45, zr), (w['max'][0]-.10, -1.45, zr)]))
    out += garden_elements(s, function)
    import survival_fit
    out += survival_fit.sector(s, function)          # SP-46 / SP-47 / SP-50 / SP-54 envelopes (PROTOTYPE)
    import drone_fleet
    out += drone_fleet.sector(s, function)           # DRONE-001 ring rover / duct cassettes (PROTOTYPE, S&E 52 DS-05..08)
    if spine_z:
        z0, z1 = spine_z; zs = (z0+z1)/2
        box('Sector_Fit_Spine_Duct', 'ROBOCRACY', 'exposed supply duct along the overhead (the diffuser\'s feed)', 'ENGINEERING_FLEXIBLE', 'cover', (-xl, c, z1-.24), (xl, c+.14, z1))
        box('Sector_Fit_Spine_Tray', 'ROBOCRACY', 'exposed cable tray along the overhead', 'ENGINEERING_FLEXIBLE', 'chase', (-xl, c, z0), (xl, c+.08, z0+.20))
        for k, (dz, paint) in enumerate(((.26, 'pipe_water'), (.33, 'pipe_power')), 1):
            out.append(element(f'Sector_Fit_Spine_Line_{k}', 'ROBOCRACY', ('water line', 'power main')[k-1], 'ENGINEERING_FLEXIBLE', paint, 'rod', radius=.02,
                               points=[(-xl, c+.05, z0+dz), (xl, c+.05, z0+dz)]))
        # The cross-over to the service block over the overhead zone, clear of the hatch's mark, and down inside the block's envelope.
        xd, zd = drop_at if b['zone'] == 'workshop' or b['open'] != 'aft' else (b['min'][0]+SERVICE_RECESS_M-.025, b['max'][2]-.10)
        xc = max(xd, L['x']+mark+.05) if b['open'] != 'aft' else xd
        out.append(element('Sector_Fit_Spine_Drop', 'ROBOCRACY', 'service drop to the service block', 'ENGINEERING_FLEXIBLE', 'pipe_water', 'rod', radius=.02,
                           points=[(xc, c+.05, z0+.26), (xc, c+.05, zd), (xd, c+.05, zd), (xd, top, zd)]))
    return out


GARDEN_EXPANSION = 'GARDEN_EXPANSION'


def garden_elements(s, function):
    """Q50 (15!A105, 12!A28): pull-out slides on every tray of the function's Garden racks (two rails along the pull, inside the end panels, and
    a handle recessed behind the rack front; garden_pull_m of travel toward the aisle when pulled, saved in), and, in the work sector, the
    optional later expansion state: garden_expansion_tiers tray tiers with grow lights on the lab bench, between the bench top and the shelf,
    each element carrying state GARDEN_EXPANSION (built hidden; GARDEN_EXPANSION_CTRL shows it). Spare lab space only: no berth, couch or
    common room is converted (15!H105, 15!G106). Display only; no growing area is credited (the built 8 m2 is 12!A28)."""
    import habitat_interior
    import sector_whitebox as sw
    w = s['sector_whitebox']; p = s['route_fitout']; out = []; t = w['panel_m']
    for b in habitat_interior.zones(s, function):
        (x0, y0, z0), (x1, y1, z1) = b['min'], b['max']
        if b['zone'] == 'garden':
            n = sw.facing(b); k = 2 if n[2] else 0; front = b['max'][k] if n[k] > 0 else b['min'][k]; back = b['min'][k] if n[k] > 0 else b['max'][k]
            inward = -1.0 if n[k] > 0 else 1.0; other = 2-k
            lo_o, hi_o = b['min'][other]+t+.012, b['max'][other]-t-.012
            for j, h in enumerate(sw.garden_tiers(s, b)):
                y = y1-h+.02
                for side, o in ((1, lo_o), (2, hi_o)):
                    a, c = [0.0, y, 0.0], [0.0, y, 0.0]; a[other] = c[other] = o; a[k] = front+inward*.03; c[k] = back-inward*(t+.01)
                    out.append(element(f'Garden_Pull_Rail_{b["name"]}_{j}_{side}', 'SPACER', f'tray slide (pull-out {p["garden_pull_m"]:.2f} m toward the aisle)',
                                       'ENGINEERING_FLEXIBLE', 'frame', 'rod', radius=.008, points=[tuple(a), tuple(c)]))
                a, c = [0.0, y1-h-.03, 0.0], [0.0, y1-h-.03, 0.0]; a[other], c[other] = lo_o+.12, hi_o-.12; a[k] = c[k] = front+inward*.02
                out.append(element(f'Garden_Pull_Handle_{b["name"]}_{j}', 'SPACER', 'tray pull handle', 'ENGINEERING_FLEXIBLE', 'handle', 'rod', radius=.01,
                                   points=[tuple(a), tuple(c)]))
        if b['zone'] == 'laboratory' and function == 'WORK_MEDICAL_OPS':
            n = sw.facing(b); k = 2 if n[2] else 0; front = b['max'][k] if n[k] > 0 else b['min'][k]; back = b['min'][k] if n[k] > 0 else b['max'][k]
            inward = -1.0 if n[k] > 0 else 1.0; other = 2-k; top = y1-w['bench_height_m']; pitch = (.60-.04)/p['garden_expansion_tiers']
            def span(lo_k, hi_k, ya, yb):
                lo, hi_ = [0.0, ya, 0.0], [0.0, yb, 0.0]; lo[other], hi_[other] = b['min'][other]+.05, b['max'][other]-.05; lo[k], hi_[k] = sorted((lo_k, hi_k))
                return tuple(lo), tuple(hi_)
            for j in range(p['garden_expansion_tiers']):
                yb = top-j*pitch
                for part, paint, (ya, yc), fn in (('Tray', 'tray', (yb-.04, yb), 'expansion growing tray'), ('Crop', 'crop', (yb-.20, yb-.04), 'expansion crop (illustrative)'),
                                                  ('Light', 'bezel', (yb-pitch+.01, yb-pitch+.03), 'grow light')):
                    lo, hi_ = span(back-inward*.04, front+inward*.05, ya, yc)
                    out.append(element(f'Garden_Expansion_Lab_{j+1}_{part}', 'SPACER', fn, 'ENGINEERING_FLEXIBLE', paint, 'wbox', state=GARDEN_EXPANSION,
                                       centre=tuple((lo[i]+hi_[i])/2 for i in range(3)), axes=((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
                                       size=tuple(hi_[i]-lo[i] for i in range(3)), area_m2=(hi_[other]-lo[other])*(hi_[k]-lo[k]) if part == 'Tray' else 0.0))
            for i, (o, d) in enumerate(((b['min'][other]+.03, back-inward*.03), (b['max'][other]-.03, back-inward*.03),
                                        (b['min'][other]+.03, front+inward*.04), (b['max'][other]-.03, front+inward*.04)), 1):
                ctr = [0.0, top-.29, 0.0]; ctr[other] = o; ctr[k] = d; size = [.024, .58, .024]          # boxes, not rods: a hidden curve has no mesh
                out.append(element(f'Garden_Expansion_Lab_Upright_{i}', 'SPACER', 'expansion tray frame upright', 'ENGINEERING_FLEXIBLE', 'frame', 'wbox',
                                   state=GARDEN_EXPANSION, centre=tuple(ctr), axes=((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)), size=tuple(size)))
    return out


def service_recess(s, function):
    """The service block's name and its open face's recessed plane: (axis, coordinate) the block's drawn shape stops at."""
    import habitat_interior
    b = next(b for b in habitat_interior.zones(s, function) if b['name'] == SERVICE_DROP[function])
    if b['zone'] == 'workshop':
        return None
    ctr, ax = face_frame(b, 'aft' if b['open'] == 'aft' else 'inner'); k = 0 if ax[2][0] else 2
    return b['name'], k, ctr[k]-ax[2][k]*SERVICE_RECESS_M, ax[2][k] > 0


def seraph_elements(s, function, where=None):
    """3.2, Seraph's space (SP-31, BASELINE: pressurized, no human consumables; charging, maintenance and private space OPEN). Robocracy
    grammar (ring, spine, articulated frame): a dock frame (two posts, a spine rail and a docking ring at shoulder height) and a charging and
    data rail. 'post' in WORK_MEDICAL_OPS: the first operations station's chair gives way to a standing dock, Seraph working at the console;
    'berth' in HABITATION: the outer column's lowest berth (Bunk_4) holds a cradle rail and a ring at the head, with a privacy panel half drawn.
    'niche' in HABITATION (Q51, 15!A106): Seraph's private dock and maintenance niche by the berths, in the slot seraph_niche_x_m between the
    couch-2 lockers and the landing well, from the lockers' inner face to the wall: a partition on the well side, a lid, the same dock (posts,
    spine, a ring at shoulder height, a charging rail), a service shelf, a privacy panel half drawn across its mouth and a placard.
    where defaults to the pick for the function ([route_fitout] seraph_spaces; the post at station seraph_station). Returns (elements, meta):
    meta names the whitebox parts the space replaces ('drop') and Seraph's stance."""
    import habitat_interior
    blocks = {b['name']: b for b in habitat_interior.zones(s, function)}; w = s['sector_whitebox']; out = []
    p = s['route_fitout']; where = where or p['seraph_spaces'].get(function); j = p['seraph_station']
    rod = lambda name, fn, pts, r=.022, paint='frame': out.append(element(name, 'ROBOCRACY', fn, 'ENGINEERING_FLEXIBLE', paint, 'rod', radius=r, points=pts))
    if where == 'post' and function == 'WORK_MEDICAL_OPS':
        b = blocks['Ops_Stations']; x0 = b['min'][0]+(j-1)*w['station_width_m']; xm = x0+w['station_width_m']/2; zb = b['min'][2]+.06; zc = b['max'][2]-w['console_depth_m']-.35
        for k, x in enumerate((x0+.06, x0+w['station_width_m']-.06), 1):
            rod(f'Seraph_Dock_Post_{k}', 'dock post', [(x, -.01, zb), (x, -1.55, zb)])
        rod('Seraph_Dock_Spine', 'dock spine rail', [(x0+.06, -1.55, zb), (x0+w['station_width_m']-.06, -1.55, zb)])
        ring = [(xm+.24*math.cos(a), -1.30, zc+.24*math.sin(a)) for a in (2*math.pi*j/16 for j in range(17))]
        rod('Seraph_Dock_Ring', 'docking ring at shoulder height', ring, .018, 'safety')
        rod('Seraph_Charge_Rail', 'charging and data rail', [(xm, -1.30, zb), (xm, -1.30, zc-.24)], .015, 'pipe_power')
        return out, dict(stand=(xm, 0.0, zc), face=(0.0, 0.0, 1.0), block='Ops_Stations', drop=[f'Chair_{j}', f'Chair_Back_{j}'])
    if where == 'niche' and function == 'HABITATION':
        lk = blocks['Couch_Lockers_2']; (x0, x1), H = p['seraph_niche_x_m'], p['seraph_niche_height_m']; xm = (x0+x1)/2
        zi, zo = (lk['max'][2], lk['min'][2]) if lk['side'] < 0 else (lk['min'][2], lk['max'][2]); n = 1.0 if zi > zo else -1.0   # n: toward the aisle
        zr = zo+n*.40                                                        # Seraph's axis, 0.40 m off the wall
        box = lambda name, grammar, fn, paint, lo, hi, **kw: out.append(element(name, grammar, fn, 'ENGINEERING_FLEXIBLE', paint, 'wbox', centre=tuple((lo[k]+hi[k])/2 for k in range(3)),
                                                                                axes=((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)), size=tuple(abs(hi[k]-lo[k]) for k in range(3)), **kw))
        box('Seraph_Niche_Partition', 'SPACER', 'niche partition on the landing-well side', 'cover', (x1-.02, -H, min(zi, zo)), (x1, 0.0, max(zi, zo)))
        box('Seraph_Niche_Lid', 'SPACER', 'niche lid', 'cover', (x0, -H, min(zi, zo)), (x1-.02, -H+.03, max(zi, zo)))
        box('Seraph_Niche_Service_Shelf', 'BOLT_SWORN', 'self-maintenance shelf: tools and spare modules', 'locker', (x0+.02, -1.98, min(zo, zo+n*.14)), (x1-.04, -1.95, max(zo, zo+n*.14)))
        for k, x in enumerate((x0+.06, x1-.08), 1):
            rod(f'Seraph_Niche_Dock_Post_{k}', 'dock post', [(x, -.01, zo+n*.06), (x, -1.55, zo+n*.06)])
        rod('Seraph_Niche_Dock_Spine', 'dock spine rail', [(x0+.06, -1.55, zo+n*.06), (x1-.08, -1.55, zo+n*.06)])
        rm = min(.24, (x1-x0)/2-.05)
        rod('Seraph_Niche_Dock_Ring', 'docking ring at shoulder height', [(xm-.01+rm*math.cos(a), -1.30, zr+rm*math.sin(a)) for a in (2*math.pi*k/16 for k in range(17))], .018, 'safety')
        rod('Seraph_Niche_Charge_Rail', 'charging and data rail', [(xm-.01, -1.30, zo+n*.06), (xm-.01, -1.30, zr-n*rm)], .015, 'pipe_power')
        box('Seraph_Niche_Privacy_Panel', 'SPACER', 'privacy panel, half drawn across the niche mouth', 'cover', (x0, -H+.05, min(zi, zi-n*.02)), (xm, -.05, max(zi, zi-n*.02)))
        out.append(element('Seraph_Niche_Placard', 'GREAT_UNION', 'placard: Seraph (private)', 'ARTISTIC', 'placard', 'wbox', True,
                           centre=(xm+.12, -1.85, zi+n*.008), axes=((1.0, 0.0, 0.0), (0.0, -1.0, 0.0), (0.0, 0.0, n)), size=(.24, .08, .012), text='SERAPH'))
        return out, dict(stand=(xm, 0.0, zr), face=(0.0, 0.0, n), block=None, drop=[])
    if where == 'berth' and function == 'HABITATION':
        b = blocks['Bunk_4']; y = b['max'][1]-w['platform_m']; zm = (b['min'][2]+b['max'][2])/2
        rod('Seraph_Cradle_Rail_1', 'cradle rail', [(b['min'][0]+.10, y-.04, zm-.18), (b['max'][0]-.10, y-.04, zm-.18)])
        rod('Seraph_Cradle_Rail_2', 'cradle rail', [(b['min'][0]+.10, y-.04, zm+.18), (b['max'][0]-.10, y-.04, zm+.18)])
        xh = b['max'][0]-.25; ring = [(xh, y-.30+.24*math.sin(a), zm+.24*math.cos(a)) for a in (2*math.pi*j/16 for j in range(17))]
        rod('Seraph_Dock_Ring', 'docking ring at the head', ring, .018, 'safety')
        rod('Seraph_Charge_Rail', 'charging and data rail', [(xh, b['min'][1]+.06, zm), (xh, y-.54, zm)], .015, 'pipe_power')
        out.append(element('Seraph_Privacy_Panel', 'SPACER', 'privacy panel, half drawn across the open aft end (outer half)', 'ENGINEERING_FLEXIBLE', 'cover', 'wbox',
                           centre=(b['min'][0]+.015, (b['min'][1]+b['max'][1])/2, b['min'][2]+(b['max'][2]-b['min'][2])*.75),
                           axes=((0.0, 0.0, 1.0), (0.0, 1.0, 0.0), (1.0, 0.0, 0.0)), size=((b['max'][2]-b['min'][2])*.5, b['max'][1]-b['min'][1]-.05, .02)))
        return out, dict(lie=((b['min'][0]+.15, y-.13, zm), (1.0, 0.0, 0.0)), block='Bunk_4', drop=[])
    return [], {}


def interior_contract(s):
    """Rig section (v24) for Q50 and Q51, in each sector's frame (habitat_interior): Seraph's operations post and private niche with its stance,
    the service path to the workshop (a route key, human_entry.route) and the Garden expansion state with its control. PROTOTYPE geometry;
    the owner statuses are 15!A105:A106."""
    import habitat_interior
    secs = s['habitat']['layout']['functions']; k1, k2 = s['route_fitout']['seraph_service_sectors']; ring = 'AB'[s['induction']['ring']-1]
    path = he.route(s)[f'{ring}{k1}-{ring}{k2}']['path']
    spaces = {}
    for fn, where in s['route_fitout']['seraph_spaces'].items():
        els, meta = seraph_elements(s, fn)
        spaces[where] = {'function': fn, 'sector': secs.index(fn)+1, 'stance_m': list(meta.get('stand', meta.get('lie', ((0, 0, 0),))[0])),
                         'face': list(meta.get('face', (0.0, 0.0, 0.0))), 'objects': [q['name'] for q in els]}      # lists: the rig is compared as JSON
    later = [q for q in garden_elements(s, 'WORK_MEDICAL_OPS') if q.get('state') == GARDEN_EXPANSION]
    return {'frame': 'sector (habitat_interior): +X axial, +Y radially outward (down in coast), +Z tangential; metres',
            'seraph': {'sp': 'SP-31', 'owner_status': 'ACCEPTED Q51 (15!A106); footprint, posture, charging and service OPEN (12A I34)', 'human_berth': False,
                       'spaces': spaces, 'service_path': {'route': f'{ring}{k1}-{ring}{k2}', 'ring': ring, 'from_sector': k1, 'to_sector': k2,
                                                          'length_m': sum(math.dist(a[1], b[1]) for a, b in zip(path, path[1:])),
                                                          'ends': 'at the work sector landing, beside the workbench strip (shirt-sleeve access)'},
                       'geometry_status': 'PROTOTYPE'},
            'garden_expansion': {'owner_status': 'ACCEPTED Q50 (15!A105, 12!A28): optional later state; food balance OPEN', 'control': 'GARDEN_EXPANSION_CTRL',
                                 'property': 'expansion', 'saved': 0.0, 'function': 'WORK_MEDICAL_OPS', 'host': 'Lab_Bench', 'tiers': s['route_fitout']['garden_expansion_tiers'],
                                 'tray_area_m2': sum(q['area_m2'] for q in later if 'area_m2' in q), 'credited': False, 'objects': [q['name'] for q in later],
                                 'pull_out_m': s['route_fitout']['garden_pull_m'], 'geometry_status': 'PROTOTYPE'}}


def wbox_corners(q):
    c, ax, size = q['centre'], q['axes'], q['size']
    return [tuple(c[i]+sx*size[0]/2*ax[0][i]+sy*size[1]/2*ax[1][i]+sz*size[2]/2*ax[2][i] for i in range(3)) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]


def sector_check(s, function, els=None):
    """3.2 screen: elements below overhead_zone_m that enter the swept aisle or the landing well at all, or reach more than 0.04 m into an
    access strip or a couch's free strip (shirt-sleeve space). A lifted block's strip (stowage over the stations) is not a floor strip."""
    import habitat_interior
    import sector_whitebox as sw
    w = s['sector_whitebox']; L = he.landing(s); a = s['interior']['aisle_m']/2; keep = []
    if els is None:
        els = sector_elements(s, function)+sector_sign(s, function)+seraph_elements(s, function)[0]
    for b in habitat_interior.zones(s, function):
        st = sw.access_strip(s, b)
        if st and b['max'][1] > -.01:
            keep.append((b['name']+' strip', st['min'], st['max'], .04))
        if b['zone'] == 'burn_couch':
            keep.append((b['name']+' free strip', (b['max'][0], -9, b['min'][2]), (b['max'][0]+w['couch_front_clear_m'], 9, b['max'][2]), .04))
    keep += [('aisle', (-9, -9, -a), (9, 9, a), 1e-4), ('landing well', (L['well_x'][0], -9, L['well_z'][0]), (L['well_x'][1], 9, L['well_z'][1]), 1e-4)]
    if 'ring_circulation' in s:
        x0, x1 = s['ring_circulation']['passage_x_m']
        keep.append(('through-passage', (x0, -9, -9), (x1, 9, 9), .015))     # CIRC-001: walked end to end; a 12 mm placard may face it
    fails = []
    for q in els:
        parts = [list(seg) for seg in zip(q['points'], q['points'][1:])] if q['shape'] == 'rod' else [wbox_corners(q)]
        r = q.get('radius', 0.0)
        for pts in parts:
            lo = [min(p[k] for p in pts)-r for k in range(3)]; hi = [max(p[k] for p in pts)+r for k in range(3)]
            if hi[1] < -s['route_fitout']['overhead_zone_m']:
                continue
            for name, kl, kh, tol in keep:
                into = [min(hi[k], kh[k])-max(lo[k], kl[k]) for k in range(3)]
                if into[0] > tol and into[2] > tol and into[1] > 0:
                    fails.append(f"{q['name']} enters the {name} by {min(into[0], into[2]):.3f} m")
    return sorted(set(fails))


if __name__ == '__main__':
    from spec import load
    s = load()[0]; f = he.ports(s)[0]
    p = s['route_fitout']
    print(json.dumps(dict(title=p['title'], elements=len(elements(s, f)), failures=check(s, f), trunk=len(trunk_elements(s)),
                          landing=len(landing_elements(s)), drums={j: len(drum_elements(s, j)) for j in s['human_entry']['vestibule_rotors']},
                          tube_ends={j: len(tube_end_elements(s, j)) for j in s['human_entry']['tube_rotors']},
                          sectors={fn: dict(elements=len(sector_elements(s, fn))+len(seraph_elements(s, fn)[0]), failures=sector_check(s, fn))
                                   for fn in s['sector_whitebox']['functions']}), indent=1))
