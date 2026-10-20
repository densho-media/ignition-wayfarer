"""Forward shield, EYE wells, Dust Lance, diversion-field and damage displays and the Aegis Dustbreak Crown (FGR-006, FWD-001). Pure geometry.

Layers stay separate. SOURCED: the shield diameter and shadow margins (spec `forward_shield`), the ~3 m crown depth, the three-sector load path, the
Crown bay/housing/engaged-radius limits and the field states (`forward_defense`), most of them WORKING, OPEN or DIAGNOSTIC. DERIVED: the stations, the
conical face, the truss, keels, ties, ports, the Crown stroke, the field zone and the study formulas below. PROTOTYPE: every dimension in
`forward_shield.prototype` (a local selection inside a sourced limit). IMPLEMENTATION: the normalized FORWARD_DEFENSE_CTRL controls, their presets and
display poses, and the translucency of the displays (`forward_shield.display`).

HSFP (98!A58): `forward_shield.design_classes` tags every object kind PHYSICS_LOCKED, ENGINEERING_FLEXIBLE or ARTISTIC. A display choice never changes an
owner value; art-driven geometry that would alter physics is a PROTOTYPE flagged for owner review.

All X positions follow the layout datums: the shield face is the FWD datum, everything else is measured from it. Standard library only; the
modules that need hull_geometry import it lazily (hull_geometry imports this module).
"""
import math
import layout
import habitat_ring

SUBSYSTEM = 'WF_FORWARD_SHIELD'
CONTROL = 'FORWARD_DEFENSE_CTRL'
PROPS = {'field_on': 'Diversion field display switch (display only; field strength and topology are OPEN, OD-018)',
         'field_strength': 'Diversion field display strength (normalized; no physical value)',
         'damage_state': 'Shield damage display, fraction of the 96 cells shown as damaged, counted from the first cell (display only; repair rates are OPEN, OD-019)',
         'repair_state': 'Shield repair display, fraction of the 96 cells restored, counted from the first cell (display only)',
         'crown_engage': 'Crown engagement: translates the carriages of the open bays forward through the skin windows and disruptor ports and slides their shutters aside (PROTOTYPE rig)',
         'crown_azimuth': 'Crown threat azimuth as a turn fraction from +Y toward +Z (PROTOTYPE rig)',
         'crown_prepare': 'Crown PREPARED: opens the armoured shutters and port covers of the facing bays with the carriages still stowed (PROTOTYPE rig, AG-008)',
         'crown_point': 'Crown head pointing: off-boresight angle toward crown_azimuth as a fraction of crown_head_max_deg, on engaged carriages only (PROTOTYPE gimbal; pointing range OPEN, OD-021)',
         'crown_fault': 'Crown DEGRADED: crown_fault x bay count selects one bay (0 none) whose shutter jams half-open and whose carriage stays stowed (PROTOTYPE rig, AVA-008)',
         **{f'eye_shutter_{j}': f'EYE facet F{j} eyelid closure: 0 open (observe), 1 closed; the two leaves part tangentially on the face (FD-E03, PROTOTYPE rig)' for j in range(1, 5)}}
# EYE eyelid closures: never in a preset row (every preset observes, all 0); closed or jammed only in display poses (FD-E03, AG-007).
EYE_SHUTTER_KEYS = tuple(f'eye_shutter_{j}' for j in range(1, 5))
# Preset rows carry only these controls; field_on and field_strength follow forward_defense.field_states (Q4).
PRESET_KEYS = ('damage_state', 'repair_state', 'crown_engage', 'crown_azimuth')
# Driver variables (short names the simple expressions use) and the control property each one reads.
VARIABLES = {'fo': 'field_on', 'fs': 'field_strength', 'dmg': 'damage_state', 'rep': 'repair_state', 'eng': 'crown_engage', 'az': 'crown_azimuth',
             'prep': 'crown_prepare', 'pt': 'crown_point', 'flt': 'crown_fault', **{f'e{j}': f'eye_shutter_{j}' for j in range(1, 5)}}
MU0 = 1.25663706212e-6        # vacuum permeability, N/A2 (real constant; 01_CONSTANTS lists none)
SPEED_OF_LIGHT = 299792458.0  # 01_CONSTANTS c (Locked)
EYE_ASSET = 'WF_EYE.blend'
ATTACHMENT_REFS = '14!H15, 15!I30'   # owner rows that leave joint sizing and the attachment to the primary structure OPEN
DESIGN_CLASSES = ('PHYSICS_LOCKED', 'ENGINEERING_FLEXIBLE', 'ARTISTIC')
SWEEP_STEPS = 96              # crown_azimuth sweep of the engaged-radius check, in turn fractions of 1/96


def prototype(s):
    """The PROTOTYPE selections plus the WORKING source values the geometry reads next to them (Q2, Q3, 2026-10-03b): the Dust Lance length,
    taper and tip cartridge (forward_defense.dust_lance), the EYE well diameter (forward_defense.eye_wells) and the ~3 m crown depth
    (forward_defense.shield_profile). One place per value."""
    d = s['forward_defense']; g = d['dust_lance']['geometry']
    return {**s['forward_shield']['prototype'], 'lance_length_m': d['dust_lance']['length']['value'], 'lance_base_radius_m': g['base_radius_m'],
            'lance_tip_radius_m': g['tip_radius_m'], 'lance_tip_cartridge_m': g['tip_cartridge_m'], 'well_diameter_m': d['eye_wells']['diameter_m'],
            'crown_depth_m': d['shield_profile']['crown_depth_m']}


def shield_radius(s):
    return s['forward_shield']['diameter']['value']/2


def body_radius(s):
    return s['ship']['body_diameter']['value']/2


def clearance(s):
    return s['prototype']['mechanical_clearance_m']


# ---------- conical face -----------------------------------------------------------------------------------------------

def cone_start_radius(s):
    """Radius where the flat hub (Lance root, wells, hub ring) ends and the conical Brow begins: the outer edge of the truss hub ring."""
    p = prototype(s)
    return p['truss_hub_opening_radius_m']+p['truss_hub_ring_width_m']


def face_x_at(s, r):
    """X of the shield face at radius r: flat at the FWD datum for r <= the cone start, then a linear cone sweeping aft by the crown depth at the shield radius."""
    face = layout.origin(s, 'FWD'); rc = cone_start_radius(s); depth = prototype(s)['crown_depth_m']
    if r <= rc:
        return face
    return face-depth*(r-rc)/(shield_radius(s)-rc)


def crown_depth_m(s):
    """Axial depth of the face from the centre to the shield radius, measured on the conical profile."""
    return face_x_at(s, 0.0)-face_x_at(s, shield_radius(s))


def skin_aft_at(s, r):
    return face_x_at(s, r)-prototype(s)['skin_thickness_m']


def truss_aft_at(s, r):
    """Aft face of the constant-depth truss behind the conical skin."""
    return skin_aft_at(s, r)-prototype(s)['truss_depth_m']


# ---------- stations -------------------------------------------------------------------------------------------------

def stations(s):
    """X stations and radii of the forward structure, all from the FWD datum and the PROTOTYPE table. `skin_aft` and `truss_aft_hub` are the flat hub
    values; `truss_aft` is the aft-most truss face (at the rim) so every consumer that needs the shield's aft limit keeps working."""
    p = prototype(s); face = layout.origin(s, 'FWD'); clr = clearance(s); R = shield_radius(s)
    skin_aft = face-p['skin_thickness_m']; truss_aft_hub = skin_aft-p['truss_depth_m']
    front = face-s['prototype']['eye_front_inset_m']               # EYE facet face; the wells are open from here to the shield face
    mount_face = front-s['prototype']['eye_module_depth_m']        # shared-mount front face (the column passes through its bore)
    hx1 = skin_aft_at(s, p['rim_inner_radius_m'])                   # Crown housing front: the skin aft face at the rim girder's inner radius
    spine_end = layout.origin(s, 'FWD')-s['prototype']['spine_forward_inset_m']      # forward end of the Momentum Spine (revision.structure)
    tip = face+p['lance_length_m']
    return dict(spine_end=spine_end, face=face, skin_aft=skin_aft, skin_aft_rim=skin_aft_at(s, R), truss_aft=truss_aft_at(s, R), truss_aft_hub=truss_aft_hub,
                front=front, mount_face=mount_face, well_depth=face-front, cone_r=cone_start_radius(s), rim_face=face_x_at(s, R),
                shield_r=R, hub_r=body_radius(s), hub_opening_r=p['truss_hub_opening_radius_m'], rim_inner_r=p['rim_inner_radius_m'],
                housing=(hx1-p['crown_axial_m'], hx1), rim=(truss_aft_at(s, R), skin_aft_at(s, R)), lance_cone_end=tip-p['lance_tip_cartridge_m'], lance_tip=tip,
                field=(face, tip), collar_end=skin_aft-clr)


def overall_length(s):
    """Aft end of the ship to the Dust Lance tip: the 220-240 m envelope INCLUDES the Lance (Q2), ~225 m body + ~12 m Lance = ~237 m."""
    return stations(s)['lance_tip']-layout.origin(s, 'AFT')


# ---------- EYE wells and the Dust Lance ----------------------------------------------------------------------------

def well_centres(s):
    """(y, z) of each well axis = its EYE facet centre, in the owner facet order (eye.facet_map), at the WORKING well centre radius (14!A28).
    The 8 m array baseline is a separate optical input: validate ties it to this radius only for the production layout (FWD-V2 study)."""
    q = s['forward_defense']['eye_wells']['centre_radius_m']/math.sqrt(2)
    return [(yy*q, zz*q) for yy, zz in s['eye']['facet_map']['quadrants']]


def in_hub(s, w):
    """True when a well lies wholly in the flat hub plate (inside the body radius), as in the production layout."""
    return math.hypot(w['y'], w['z'])+w['radius'] < body_radius(s)


def wells(s):
    """Open tubes from each facet face to the local shield face (flat hub in production; on the cone for the FWD-V2 placement study)."""
    p = prototype(s); depth = stations(s)['well_depth']; out = []
    for j, ((y, z), label) in enumerate(zip(well_centres(s), s['eye']['facet_map']['labels']), 1):
        x1 = face_x_at(s, math.hypot(y, z))
        out.append(dict(index=j, y=y, z=z, radius=p['well_diameter_m']/2, x0=x1-depth, x1=x1, label=label))
    return out


def fs_ok_bore(s):
    return prototype(s)['lance_base_radius_m'] < eye_mount_bore(s) < s['prototype']['eye_backing_radius_m']


def distance_point_segment(point, a, b):
    ax, ay = a; bx, by = b; px, py = point; dx, dy = bx-ax, by-ay
    t = max(0.0, min(1.0, ((px-ax)*dx+(py-ay)*dy)/(dx*dx+dy*dy)))
    return math.hypot(px-(ax+t*dx), py-(ay+t*dy))


def segment_distance(a0, a1, b0, b1):
    """Smallest distance between two 3-D segments (closed form, clamped); a degenerate segment is a point."""
    d1 = [b-a for a, b in zip(a0, a1)]; d2 = [b-a for a, b in zip(b0, b1)]; r = [a-b for a, b in zip(a0, b0)]
    dot = lambda u, v: sum(x*y for x, y in zip(u, v))
    a = dot(d1, d1); e = dot(d2, d2); f = dot(d2, r)
    if a <= 1e-18 and e <= 1e-18:
        return math.dist(a0, b0)
    if a <= 1e-18:
        sv = 0.0; t = max(0.0, min(1.0, f/e))
    else:
        c = dot(d1, r)
        if e <= 1e-18:
            t = 0.0; sv = max(0.0, min(1.0, -c/a))
        else:
            b = dot(d1, d2); den = a*e-b*b
            sv = max(0.0, min(1.0, (b*f-c*e)/den)) if den > 1e-18 else 0.0
            t = (b*sv+f)/e
            if t < 0.0:
                t = 0.0; sv = max(0.0, min(1.0, -c/a))
            elif t > 1.0:
                t = 1.0; sv = max(0.0, min(1.0, (b-c)/a))
    return math.dist([x+sv*d for x, d in zip(a0, d1)], [x+t*d for x, d in zip(b0, d2)])


def lance_radius_at(s, x):
    """Outer radius of the Dust Lance at X ahead of the face: a cone to the tip cartridge, then the cartridge."""
    st = stations(s); p = prototype(s)
    if x < st['face'] or x > st['lance_tip']:
        return 0.0
    if x >= st['lance_cone_end']:
        return p['lance_tip_radius_m']
    u = (x-st['face'])/(st['lance_cone_end']-st['face'])
    return p['lance_base_radius_m']+(p['lance_tip_radius_m']-p['lance_base_radius_m'])*u


def lance(s):
    st = stations(s); p = prototype(s)
    return dict(x0=st['face'], cone_end=st['lance_cone_end'], x1=st['lance_tip'], base_r=p['lance_base_radius_m'], tip_r=p['lance_tip_radius_m'],
                column=(st['spine_end'], st['face']), length=p['lance_length_m'])


def eye_mount_bore(s):
    """Radius of the bore through the EYE shared mount that lets the spine-continuation column pass with the shared clearance."""
    return prototype(s)['lance_base_radius_m']+clearance(s)


def mount_struts(s):
    """Radial shield-mount struts (PROTOTYPE) from the spine-continuation column to the truss hub ring: constant X, evenly spaced from +Y toward +Z.
    They cross the hull collar through derived openings (hull_geometry.openings). The hub path of the load path."""
    st = stations(s); p = prototype(s); n = p['shield_mount_count']; x = st['truss_aft_hub']+p['shield_mount_x_offset_m']; out = []
    for k in range(n):
        a = 2*math.pi*k/n
        out.append(dict(index=k+1, name=f'Shield_Mount_Strut_{k+1:02}', theta=a, x=x, radius=p['shield_mount_member_radius_m'], r0=p['lance_base_radius_m'], r1=st['hub_opening_r'],
                        a=(x, p['lance_base_radius_m']*math.cos(a), p['lance_base_radius_m']*math.sin(a)), b=(x, st['hub_opening_r']*math.cos(a), st['hub_opening_r']*math.sin(a))))
    return out


# ---------- truss, keels, ties, damage cells, housing ------------------------------------------------------------------

def eye_layout_active(s):
    """True when forward_defense.eye_layout selects an outer layout (spec.apply_eye_layout moved the wells): the alternate truss applies."""
    lay = s['forward_defense'].get('eye_layout')
    return bool(lay) and lay['selected'] != 'r4'


def alternate(s):
    """The FWD-V2 alternate truss of the selected outer Eye layout (eye_truss_study.alternate, names without the Study_ prefix), or None at r4."""
    if not eye_layout_active(s):
        return None
    import eye_truss_study as ets
    alt = ets.alternate(s); R = body_radius(s)+clearance(s)
    for m in alt['members']:
        m['name'] = m['name'].replace('Study_', 'Alt_', 1)
        if m['role'] == 'raceway':          # stop one clearance off the hull; the hull entry stays an OPEN interface (no derived opening)
            stop = R+m['radius']; pts = []
            for a, b in zip(m['pts'], m['pts'][1:]):
                ra, rb = math.hypot(a[1], a[2]), math.hypot(b[1], b[2])
                pts.append(a)
                if rb < stop <= ra:
                    f = (ra-stop)/(ra-rb); pts.append(tuple(a[i]+(b[i]-a[i])*f for i in range(3))); break
            else:
                pts.append(m['pts'][-1])
            m['pts'] = pts; m['hull_entry'] = 'OPEN'
    return alt


ALT_TRUSS_ROLES = ('spoke', 'branch', 'collar', 'ring_arc', 'facet_frame', 'raceway')


def truss(s, base=False):
    """Hub ring, radial spokes and circumferential rings between the hub ring and the Crown housing: a conical two-chord truss of constant axial
    depth behind the conical skin. Member centrelines stay one member radius inside the envelope so every member lies within it. With an outer
    Eye layout selected (and base False), 'removed' names the spoke members and rings the alternate truss replaces and 'alternate' lists its
    collars, branches, ring arcs, facet frames and raceways."""
    st = stations(s); p = prototype(s); m = p['truss_member_radius_m']; n = p['truss_spoke_count']
    xa = lambda r: truss_aft_at(s, r)+m
    xf = lambda r: skin_aft_at(s, r)-m
    r_in = st['hub_opening_r']+p['truss_hub_ring_width_m']; r_out = p['crown_housing_inner_radius_m']
    spokes = []
    for k in range(n):
        a = 2*math.pi*(k+.5)/n; c, sn = math.cos(a), math.sin(a)
        pt = lambda x, r: (x, r*c, r*sn)
        spokes.append(dict(index=k+1, azimuth=a, members=[('aft', [pt(xa(r_in), r_in), pt(xa(r_out), r_out)]), ('fwd', [pt(xf(r_in), r_in), pt(xf(r_out), r_out)]),
                                                         ('diagonal', [pt(xa(r_in), r_in), pt(xf(r_out), r_out)])]))
    out = dict(hub_ring=(st['truss_aft_hub'], st['skin_aft'], st['hub_opening_r']+p['truss_hub_ring_width_m'], st['hub_opening_r']), spokes=spokes,
               rings=[dict(radius=r, x=x) for r in p['truss_ring_radii_m'] for x in (xa(r), xf(r))], member_radius=m, removed=set(), alternate=[])
    alt = None if base else alternate(s)
    if alt:
        out['removed'] = {n for n in alt['removed'] if n.startswith(('Truss_Spoke_', 'Truss_Ring_'))}
        out['alternate'] = [q for q in alt['members'] if q['role'] in ALT_TRUSS_ROLES]
    return out


def rear_construction(s):
    """M4 slice 3 (forward_shield.rear_construction, PROTOTYPE): gusset plates at the truss nodes and ribs and service hatches on the Crown
    housing aft plate, all inside the truss envelope. Each part: name, kind, vertices, faces (ship frame)."""
    c = s['forward_shield']['rear_construction']; t = truss(s); m = t['member_radius']; st = stations(s); p = prototype(s); cr = crown(s)
    h, g, tg = c['gusset_half_m'], c['gusset_reach_m'], c['gusset_thickness_m']
    r_in = st['hub_opening_r']+p['truss_hub_ring_width_m']; r_out = p['crown_housing_inner_radius_m']; out = []
    faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]

    def plate(name, kind, a, quad, half_t):
        """quad: four (x, r) corners in the spoke plane at azimuth a, extruded +-half_t tangentially."""
        cs, sn = math.cos(a), math.sin(a); vs = []
        for x, r in quad:
            for w in (-half_t, half_t):
                vs.append((x, r*cs-w*sn, r*sn+w*cs))
        # corners (x, r) order: aft-in, aft-out, fwd-in, fwd-out -> vertex index 2*i + side
        vs = [vs[i] for i in (0, 2, 4, 6, 1, 3, 5, 7)]
        out.append(dict(name=name, kind=kind, vertices=vs, faces=faces))

    rings = sorted({r['radius'] for k, r in enumerate(t['rings']) if f"Truss_Ring_{k+1:02}" not in t['removed']})
    for sp in t['spokes']:
        k = sp['index']; a = sp['azimuth']
        for chord in ('aft', 'fwd'):
            if f"Truss_Spoke_{k:02}_{chord}" in t['removed']:
                continue
            for tag, r0, r1 in [('Hub', r_in, r_in+h), ('Housing', r_out-h, r_out)]+[(f'R{r:g}', r-h, r+h) for r in rings]:
                if chord == 'aft':
                    q = [(truss_aft_at(s, r0), r0), (truss_aft_at(s, r1), r1), (truss_aft_at(s, r0)+2*m+g, r0), (truss_aft_at(s, r1)+2*m+g, r1)]
                else:
                    q = [(skin_aft_at(s, r0)-2*m-g, r0), (skin_aft_at(s, r1)-2*m-g, r1), (skin_aft_at(s, r0)-.005, r0), (skin_aft_at(s, r1)-.005, r1)]
                plate(f'Truss_Node_{k:02}_{chord}_{tag}', 'truss_node', a, q, tg/2)
    n = len(cr['bays']); x0 = cr['x0']; w = c['rib_width_m']
    for b in cr['bays']:
        phi = b['azimuth']+math.pi/n
        plate(f"Crown_Housing_Rib_{b['index']:02}", 'crown_housing_rib', phi,
              [(x0-c['rib_depth_m'], cr['inner_r']), (x0-c['rib_depth_m'], cr['outer_r']), (x0, cr['inner_r']), (x0, cr['outer_r'])], w/2)
        r0, r1 = c['hatch_r_m']; half = c['hatch_tangential_m']/2; a = b['azimuth']; cs, sn = math.cos(a), math.sin(a); vs = []
        for x in (x0-c['hatch_depth_m'], x0):
            for r in (r0, r1):
                for u in (-half, half):
                    vs.append((x, r*cs-u*sn, r*sn+u*cs))
        out.append(dict(name=f"Crown_Service_Hatch_{b['index']:02}", kind='crown_service_hatch', vertices=vs, faces=faces))
    out += brow_panel_joints(s)
    return out


def brow_panel_joints(s):
    """S04 slice 2: the Brow's replaceable-panel joints as grooves on the skin's aft face (rear_construction joint_*): radial joints beside every
    spoke, hoop joints between the truss rings broken round each spoke's forward chord. Each joint is a strip of quads, closed at its ends."""
    c = s['forward_shield']['rear_construction']; t = truss(s); m = t['member_radius']; clr = clearance(s)
    w, h = c['joint_width_m'], c['joint_height_m']; r0, r1 = c['joint_r_m']; out = []

    def strip(name, pts):
        """pts: (x_face, r, a, tangent half-vector (dy, dz)) along the joint; returns a closed strip from the face to h aft of it."""
        vs = []
        for x, r, a, (dy, dz) in pts:
            y, z = r*math.cos(a), r*math.sin(a)
            for (yy, zz), d in (((y-dy, z-dz), .001), ((y+dy, z+dz), .001), ((y+dy, z+dz), h), ((y-dy, z-dz), h)):
                vs.append((skin_aft_at(s, math.hypot(yy, zz))-d, yy, zz))    # each vertex on the cone at its own radius
        fs = []
        for k in range(len(pts)-1):
            i, j = 4*k, 4*(k+1)
            fs += [(i+q, j+q, j+(q+1) % 4, i+(q+1) % 4) for q in range(4)]
        fs += [(0, 1, 2, 3), tuple(reversed(range(4*len(pts)-4, 4*len(pts))))]
        out.append(dict(name=name, kind='brow_panel_joint', vertices=vs, faces=fs))

    for sp in t['spokes']:
        for off in c['joint_deg_offsets']:
            a = sp['azimuth']+math.radians(off); n = 40
            pts = [(skin_aft_at(s, r0+(r1-r0)*k/n), r0+(r1-r0)*k/n, a, (-math.sin(a)*w/2, math.cos(a)*w/2)) for k in range(n+1)]
            strip(f"Brow_Joint_Radial_{sp['index']:02}_{'a' if off < 0 else 'b'}", pts)
    spokes = sorted(sp['azimuth'] % (2*math.pi) for sp in t['spokes'])
    for r in c['joint_hoop_r_m']:
        gap = (m+clr+w/2)/r; x = skin_aft_at(s, r)
        for k, a0 in enumerate(spokes):
            a1 = spokes[(k+1) % len(spokes)]+(2*math.pi if k == len(spokes)-1 else 0.0); lo, hi = a0+gap, a1-gap; n = 24
            pts = []
            for i in range(n+1):
                a = lo+(hi-lo)*i/n; rr = r
                pts.append((x, rr, a, (math.cos(a)*w/2, math.sin(a)*w/2)))   # half-width along the radius
            strip(f'Brow_Joint_Hoop_{r:g}_{k:02}', pts)
    return out


def rear_construction_screen(s):
    """Every part between the truss aft envelope and the skin's aft face at its own radius (sampled at the vertices)."""
    fails = []
    for q in rear_construction(s):
        for x, y, z in q['vertices']:
            r = math.hypot(y, z)
            if x < truss_aft_at(s, min(r, shield_radius(s)))-1e-6 or x > skin_aft_at(s, min(r, shield_radius(s)))+1e-6:
                fails.append(f"{q['name']} outside the truss envelope at r {r:.2f}, x {x:.3f}"); break
    return fails or 'PASS'


def sector_azimuths(s):
    """Azimuths of the three primary longitudinal structural sectors (07!A10, A13: nodes 1/5/9 of 12 at the cage phase), from +Y toward +Z."""
    st = s['structure']; phase = math.radians(s['prototype']['ring_phase_deg'])
    return [phase+n*2*math.pi/st['ring_nodes'] for n in st['sector_pickup_nodes']]


def sector_keels(s):
    """Forward continuation of the three primary sectors from ahead of ring B to the keel head behind the hub truss (PROTOTYPE, FWD-001): at the sourced
    sector radius and azimuths, rail radius = structural_rail_radius_m. The aft end follows ring B's swept front plus two shared clearances plus the rail."""
    st = stations(s); p = prototype(s); P = s['prototype']; R = s['structure']['sector_radius_m']; rail = P['structural_rail_radius_m']; clr = clearance(s)
    x0 = max(habitat_ring.centers(s))+habitat_ring.sweep_half(s)+2*clr+rail; x1 = st['truss_aft_hub']-p['sector_tie_head_inset_m']
    out = []
    for j, a in enumerate(sector_azimuths(s), 1):
        u = (math.cos(a), math.sin(a))
        out.append(dict(index=j, name=f'Shield_Sector_Keel_{j}', theta=a, r=R, x0=x0, x1=x1, radius=rail, hoop_radius=P['structural_strut_radius_m'],
                        a=(x0, R*u[0], R*u[1]), b=(x1, R*u[0], R*u[1])))
    return out


def primary_cage_end_x(s):
    """X of the aft-of-ring-A end of the primary cage (07: sector rails), from the layout datum and prototype.outer_cage_end_x."""
    return layout.at(s, s['prototype']['outer_cage_end_x'])


def bypass_collar(s):
    """Q45 (15!A99, 07!A57): the stationary external bypass collar that carries the Brow-side sector keels round the swept rotor bay into the three
    primary sectors. The principle is WORKING; every dimension is PROTOTYPE (15!G99) and derived here: the outer chord sits on the Brow's outer truss
    ring, the inner chord forward_defense.bypass_collar.depth_m inside it, both outside the ring sweep. Per sector a two-chord girder runs from the
    Brow truss aft face to an aft frame centred in the slot between the blade front and ring A's aft sweep face, with verticals and diagonal lacing;
    hoops on the outer chord at the aft frame, between the ring sweeps and at the keel aft ends; an aft spoke from the inner chord down to the sector
    rail, which continues forward from the cage end; and a keel tie from each keel aft end out to the inner chord."""
    c = s['forward_defense']['bypass_collar']; R = prototype(s)['truss_ring_radii_m'][-1]; Ri = R-c['depth_m']; m = c['member_radius_m']
    Rs = s['structure']['sector_radius_m']; rail = s['prototype']['structural_rail_radius_m']
    cen = habitat_ring.centers(s); half = habitat_ring.sweep_half(s)
    import thermal_geometry
    blade_front = thermal_geometry.blade_of(s)['front_x_m']
    xa = (blade_front+min(cen)-half)/2; xm = (cen[0]+half+cen[1]-half)/2; xf = sector_keels(s)[0]['x0']
    xt, xti = truss_aft_at(s, R)-m, truss_aft_at(s, Ri)-m
    members = []
    for j, a in enumerate(sector_azimuths(s), 1):
        u = lambda r, x: (x, r*math.cos(a), r*math.sin(a))
        members += [dict(name=f'Bypass_Chord_{j}_Outer', sector=j, role='chord', a=u(R, xa), b=u(R, xt), radius=m),
                    dict(name=f'Bypass_Chord_{j}_Inner', sector=j, role='chord', a=u(Ri, xa), b=u(Ri, xti), radius=m),
                    dict(name=f'Bypass_Aft_Spoke_{j}', sector=j, role='aft_spoke', a=u(Rs, xa), b=u(Ri, xa), radius=m),
                    dict(name=f'Bypass_Rail_Extension_{j}', sector=j, role='rail_extension', a=u(Rs, primary_cage_end_x(s)), b=u(Rs, xa), radius=rail),
                    dict(name=f'Bypass_Keel_Tie_{j}', sector=j, role='keel_tie', a=u(Rs, xf), b=u(Ri, xf), radius=m)]
        nodes = [xa, xm, xf]
        n = max(1, math.ceil((xt-xf)/c['panel_max_m'])); nodes += [xf+(xt-xf)*i/n for i in range(1, n)]
        nodes = sorted(nodes)
        for i, x in enumerate(nodes):
            members.append(dict(name=f'Bypass_Vertical_{j}_{i+1:02}', sector=j, role='vertical', a=u(Ri, x), b=u(R, x), radius=m))
        for i, (x0, x1) in enumerate(zip(nodes, nodes[1:]+[xt])):
            lo, hi = (u(Ri, x0), u(R, x1)) if i % 2 == 0 else (u(R, x0), u(Ri, min(x1, xti)))
            members.append(dict(name=f'Bypass_Diagonal_{j}_{i+1:02}', sector=j, role='diagonal', a=lo, b=hi, radius=m))
    hoops = [dict(name=f'Bypass_Hoop_{k}', x=x, r=R, radius=m) for k, x in (('Aft', xa), ('Mid', xm), ('Fwd', xf))]
    return dict(outer_r=R, inner_r=Ri, member_radius=m, stations=dict(aft=xa, mid=xm, fwd=xf, truss_aft=xt), members=members, hoops=hoops)


def sector_continuity_gap_m(s):
    """Largest open distance in each sector's chain keel aft end -> keel tie -> collar -> aft spoke -> rail extension -> primary cage end (Q1 distribution
    into the primary sectors, Q45). Zero means every keel reaches the primary cage through the bypass collar."""
    col = bypass_collar(s); keels = {k['index']: k for k in sector_keels(s)}; gaps = []
    for j, k in keels.items():
        ms = {m['role']: m for m in col['members'] if m['sector'] == j and m['role'] in ('keel_tie', 'aft_spoke', 'rail_extension')}
        if len(ms) < 3:
            gaps.append(k['x0']-primary_cage_end_x(s)); continue
        gaps += [math.dist(k['a'], ms['keel_tie']['a']), math.dist(ms['aft_spoke']['a'], ms['rail_extension']['b']),
                 abs(ms['rail_extension']['a'][0]-primary_cage_end_x(s))]
    return max(gaps)


def bypass_clearances(s):
    """Clearances of the bypass collar (m) to the ring sweeps, the blade front, the shield edge and the docking corridors; each must be >= the shared clearance."""
    import hull_geometry, thermal_geometry
    col = bypass_collar(s); m = col['member_radius']; st = col['stations']; cen = habitat_ring.centers(s); half = habitat_ring.sweep_half(s)
    front = thermal_geometry.blade_of(s)['front_x_m']
    out = {'inner_chord_to_ring_sweep': col['inner_r']-m-habitat_ring.outer(s), 'aft_frame_to_blade_front': st['aft']-m-front,
           'aft_frame_to_ring_A_sweep': min(cen)-half-(st['aft']+m), 'mid_frame_to_ring_sweeps': min(st['mid']-m-(cen[0]+half), cen[1]-half-(st['mid']+m)),
           'keel_tie_to_ring_B_sweep': st['fwd']-m-(max(cen)+half), 'outer_chord_inside_shield_edge': shield_radius(s)-(col['outer_r']+m)}
    for q in hull_geometry.dock_corridors(s):
        u = (math.cos(q['theta']), math.sin(q['theta'])); a = (q['x'], q['r0']*u[0], q['r0']*u[1]); b = (q['x'], q['r1']*u[0], q['r1']*u[1])
        out[f"{q['name']}_corridor"] = min(segment_distance(a, b, mm['a'], mm['b'])-q['radius']-mm['radius'] for mm in col['members'])
    return out


def sector_ties(s, base=False):
    """Nine ties from the three keel heads into the Brow truss: one to the aft inner corner of the hub ring and two to the aft-chord nodes of the two
    truss spokes adjacent to the sector at the first truss ring. Count and azimuths derive from the sourced sector nodes, never from a typed number."""
    st = stations(s); p = prototype(s); m = p['truss_member_radius_m']; n = p['truss_spoke_count']; r1 = p['truss_ring_radii_m'][0]; out = []
    step = 2*math.pi/n
    for k in sector_keels(s):
        head = k['b']; a = k['theta']
        lo = math.floor(a/step-.5+1e-9); spokes = [(lo+.5)*step, (lo+1.5)*step]      # the two spoke azimuths (k + .5) step on either side
        targets = [('hub', (st['truss_aft_hub']+m, (st['hub_opening_r']+m)*math.cos(a), (st['hub_opening_r']+m)*math.sin(a)))]
        for label, sa in zip('ab', spokes):
            targets.append((label, (truss_aft_at(s, r1)+m, r1*math.cos(sa), r1*math.sin(sa))))
        for label, b in targets:
            out.append(dict(name=f"Shield_Sector_Tie_{k['index']}_{label}", sector=k['index'], theta=a, radius=m, a=head, b=b, target=label))
    alt = None if base else alternate(s)
    if alt:          # ties that landed on a replaced node are rerouted to the collar (same name, new truss end)
        moved = {q['name'][len('Alt_'):]: q['pts'][1] for q in alt['members'] if q['role'] == 'sector_tie'}
        for tie in out:
            if tie['name'] in moved:
                tie['b'] = moved[tie['name']]; tie['target'] = 'collar'
    return out


def keel_hoop_points(s):
    """Keel-end hoops as (x, y, z, member radius) samples."""
    pts = []
    for k in sector_keels(s):
        for x in (k['x0'], k['x1']):
            pts += [(x, k['r']*math.cos(2*math.pi*i/64), k['r']*math.sin(2*math.pi*i/64), k['hoop_radius']) for i in range(64)]
    return pts


def keel_points(s, spacing=0.25):
    """Sampled keel rails and keel-end hoops as (x, y, z, member radius), for hull_geometry.fitting_margin."""
    pts = []
    for k in sector_keels(s):
        n = max(2, int(math.ceil((k['x1']-k['x0'])/spacing)))
        pts += [(k['x0']+(k['x1']-k['x0'])*i/n, k['b'][1], k['b'][2], k['radius']) for i in range(n+1)]
    return pts+keel_hoop_points(s)


def damage_cells(s):
    """4 x 24 display cells on the conical face between the cone start and the Crown housing; ring-major index. Cells never deform the shield."""
    st = stations(s); p = prototype(s); rings, sectors = p['damage_ring_count'], p['damage_sector_count']
    r0, r1 = st['cone_r'], p['crown_housing_inner_radius_m']; inset = p['damage_cell_inset_fraction']; lift = p['damage_cell_lift_m']; out = []
    for i in range(rings):
        for j in range(sectors):
            ra, rb = r0+(r1-r0)*i/rings, r0+(r1-r0)*(i+1)/rings; da = 2*math.pi/sectors
            ca, cb = ra+(rb-ra)*inset, rb-(rb-ra)*inset
            out.append(dict(index=i*sectors+j, ring=i+1, sector=j+1, r0=ca, r1=cb, a0=j*da+da*inset, a1=(j+1)*da-da*inset,
                            x_r0=face_x_at(s, ca)+lift, x_r1=face_x_at(s, cb)+lift, x=(face_x_at(s, ca)+face_x_at(s, cb))/2+lift))
    return out


# ---------- full-area sacrificial disruptor (FWD1) and the EYE / Crown ports ---------------------------------------------

def disruptor_layers(s):
    """Full-diameter sacrificial layers ahead of the Brow (PROTOTYPE, count = len(disruptor_standoffs_m)): each parallel to the conical face at its
    standoff, out to the shield radius. aft/front X follow face_x_at, so the layer is conical with the same flat hub."""
    p = prototype(s); out = []; R = shield_radius(s)
    for j, off in enumerate(p['disruptor_standoffs_m'], 1):
        t = p['disruptor_display_thickness_m']
        out.append(dict(index=j, name=f'Disruptor_Layer_{j:02}', standoff=off, thickness=t, outer_r=R, aft_hub=face_x_at(s, 0.0)+off,
                        front_hub=face_x_at(s, 0.0)+off+t, aft_rim=face_x_at(s, R)+off, front_rim=face_x_at(s, R)+off+t))
    return out


def layer_x(s, layer, r):
    """(aft face, front face) of a layer at radius r."""
    a = face_x_at(s, r)+layer['standoff']
    return a, a+layer['thickness']


def disruptor_layer_count(s):
    """Layers at the full shield radius that lie entirely ahead of the Brow face (derived, never typed)."""
    R = shield_radius(s); radii = [0.0, cone_start_radius(s), R/2, R]
    return sum(1 for layer in disruptor_layers(s) if math.isclose(layer['outer_r'], R, abs_tol=1e-9) and all(layer_x(s, layer, r)[0] >= face_x_at(s, r)-1e-9 for r in radii))


def eye_port_required_radius(s, layer):
    """Smallest port radius in the layer plane that adds no vignetting inside a well's own unvignetted field: the cone of rays from the facet aperture
    edge past the well lip, extended to the layer. Derived from the WORKING aperture and well; not an EYE field of view."""
    r_ap = s['eye']['aperture']['value']/2; r_w = prototype(s)['well_diameter_m']/2; depth = stations(s)['well_depth']
    return r_ap+(r_w-r_ap)*(depth+layer['standoff'])/depth


def eye_port_radius(s, layer):
    """Port radius cut in a layer coaxial with each well: the required radius times the PROTOTYPE eye_port_scale (>= 1)."""
    return prototype(s)['eye_port_scale']*eye_port_required_radius(s, layer)


def lance_hole_radius(s, layer):
    """Lance hole in a layer: the Lance radius at the layer's aft face plus the shared clearance."""
    return lance_radius_at(s, layer_x(s, layer, 0.0)[0])+clearance(s)


def crown_skin_windows(s):
    """Skin windows of the 12 Crown bays in the conical face: radial span = stowed carriage +- its radial half size and clearance, width window_w."""
    c = crown(s)
    return [dict(index=b['index'], azimuth=b['azimuth'], r0=c['window']['r0'], r1=c['window']['r1'], width=c['window_w'], half_angle=c['window']['half_angle']) for b in c['bays']]


def crown_ports(s):
    """Disruptor ports (Q44, Eye 40!A36): the smallest localized opening the engaged carriage passes, its own footprint plus the shared clearance,
    not the wider skin-window footprint. The carriages only translate forward in fixed bays (no azimuth traverse), so a fixed port stays aligned."""
    c = crown(s); car = c['carriage']; clr = clearance(s); w = car['tangential']+2*clr
    r0, r1 = c['stowed_r']-car['radial']/2-clr, c['stowed_r']+car['radial']/2+clr
    return [dict(index=b['index'], azimuth=b['azimuth'], r0=r0, r1=r1, width=w, half_angle=(w/2)/c['stowed_r']) for b in c['bays']]


def crown_port_covers(s):
    """Normally closed armoured cover behind each layer port (Q44): it overlaps the port by crown_shutter_overlap_m, lies one shared clearance aft of
    the most aft layer aft face over its span, and slides tangentially by its own width, with its bay's skin shutter, when the bay engages."""
    p = prototype(s); clr = clearance(s); sov = p['crown_shutter_overlap_m']; th = p['crown_port_cover_thickness_m']; out = []
    for q in crown_ports(s):
        rad, tan = (q['r1']-q['r0'])+2*sov, q['width']+2*sov
        x = min(layer_x(s, layer, q['r1']+sov)[0] for layer in disruptor_layers(s))-clr-th/2
        out.append(dict(index=q['index'], azimuth=q['azimuth'], r_centre=(q['r0']+q['r1'])/2, radial=rad, tangential=tan, thickness=th, x=x, slide=tan))
    return out


def eye_baselines(s, radius=None):
    """FD-A03 / AG-A03: geometric facet separations follow the placement radius; B_array stays the r4 calibration input; the coherent baseline is OPEN."""
    r = s['forward_defense']['eye_wells']['centre_radius_m'] if radius is None else radius; b = s['eye']['array_baseline']
    return {'radius_m': float(r),
            'geometric_opposite_m': {'known': True, 'value': float(2*r), 'unit': 'm', 'canon_status': 'DERIVED', 'basis': 'opposite facet centres, 2 r'},
            'geometric_adjacent_m': {'known': True, 'value': float(math.sqrt(2)*r), 'unit': 'm', 'canon_status': 'DERIVED', 'basis': 'adjacent facet centres, sqrt(2) r'},
            'b_array': {'known': True, 'value': float(b['value']), 'unit': 'm', 'canon_status': b['canon_status'], 'source_ref': b['source_ref'],
                        'basis': 'r4 calibration input only (FD-A03); not the physical separation of another placement'},
            'coherent': {'known': False, 'unit': 'm', 'canon_status': 'OPEN', 'reason': s['eye']['coherent_baseline']['reason']}}


def eye_ports(s, layer):
    return [dict(index=w['index'], y=w['y'], z=w['z'], radius=eye_port_radius(s, layer), well_radius=w['radius']) for w in wells(s)]


def disruptor_open_fraction(s, layer=None):
    """DIAGNOSTIC: share of the projected shield disc left open by the EYE ports, the Crown ports and the Lance hole."""
    layer = layer or disruptor_layers(s)[0]
    area = sum(math.pi*q['radius']**2 for q in eye_ports(s, layer))+sum(q['width']*(q['r1']-q['r0']) for q in crown_ports(s))+math.pi*lance_hole_radius(s, layer)**2
    return area/(math.pi*shield_radius(s)**2)


def disruptor_posts(s, base=False):
    """Posts carrying each layer on truss nodes: 12 azimuths (the truss-spoke azimuths) x the hub-ring mid, truss-ring and rim-girder mid radii.
    Each post runs along +X from the skin face (or the layer below) to the layer's aft face."""
    st = stations(s); p = prototype(s); n = p['truss_spoke_count']
    radii = [st['hub_opening_r']+p['truss_hub_ring_width_m']/2]+list(p['truss_ring_radii_m'])+[(p['rim_inner_radius_m']+shield_radius(s))/2]
    out = []
    layers = disruptor_layers(s)
    for li, layer in enumerate(layers, 1):
        for k in range(n):
            a = 2*math.pi*(k+.5)/n
            for i, r in enumerate(radii, 1):
                x0 = face_x_at(s, r) if li == 1 else layer_x(s, layers[li-2], r)[1]; x1 = layer_x(s, layer, r)[0]
                out.append(dict(name=f'Disruptor_Post_{li:02}_{k+1:02}_{i}', layer=li, azimuth=a, r=r, radius=p['disruptor_post_radius_m'], x0=x0, x1=x1,
                                a=(x0, r*math.cos(a), r*math.sin(a)), b=(x1, r*math.cos(a), r*math.sin(a))))
    alt = None if base else alternate(s)
    if alt:          # posts inside an outer EYE port move to the collar's radial nodes
        gone = set(alt['removed']); out = [q for q in out if q['name'] not in gone]
        for q in (q for q in alt['members'] if q['role'] == 'post'):
            (x0, y, z), (x1, _, _) = q['pts']; li = int(q['name'].split('_Post_')[1][:2])
            out.append(dict(name=q['name'], layer=li, azimuth=math.atan2(z, y), r=math.hypot(y, z), radius=q['radius'], x0=x0, x1=x1, a=q['pts'][0], b=q['pts'][1]))
    return out


def sheet_radii(s):
    """Ring radii of the conical sheets (skin and layers): every radius where something changes, so port and window quads align with rings."""
    p = prototype(s); c = crown(s)
    return sorted({body_radius(s), cone_start_radius(s), *p['truss_ring_radii_m'], p['crown_housing_inner_radius_m'], c['window']['r0'], c['window']['r1'],
                   p['rim_inner_radius_m'], shield_radius(s)})


def sheet_angles(s, segments=96):
    """Ring angles of the conical sheets: a uniform grid plus both edges of every Crown window, sorted, in [0, 2 pi)."""
    hw = crown(s)['window']['half_angle']; tau = 2*math.pi
    return sorted({round(tau*i/segments, 12) for i in range(segments)} | {round((b['azimuth']+d) % tau, 12) for b in crown(s)['bays'] for d in (-hw, hw)})


def revolved_sheet(radii, thetas, x_of_r, windows=(), flip=False):
    """One-sided surface of revolution over radii x thetas at X = x_of_r(r). Quads whose radial span lies in a window's [r0, r1] and whose middle angle
    lies within the window's half angle are omitted. Returns (vertices, faces, omitted). Winding matches common.flat_ring (normal toward +X)."""
    n = len(thetas); tau = 2*math.pi
    vs = [(x_of_r(r), r*math.cos(t), r*math.sin(t)) for r in radii for t in thetas]; faces = []; omitted = 0
    for i in range(len(radii)-1):
        ra, rb = radii[i], radii[i+1]
        for j in range(n):
            t0 = thetas[j]; t1 = thetas[(j+1) % n]+(tau if j+1 == n else 0.0); mid = (t0+t1)/2
            if any(ra >= w['r0']-1e-9 and rb <= w['r1']+1e-9 and abs(((mid-w['azimuth']+math.pi) % tau)-math.pi) < w['half_angle'] for w in windows):
                omitted += 1; continue
            q = (i*n+j, (i+1)*n+j, (i+1)*n+(j+1) % n, i*n+(j+1) % n)
            faces.append(tuple(reversed(q)) if flip else q)
    return vs, faces, omitted


def conical_plate(s, offset_aft, thickness, windows, start_r=None):
    """A conical plate (aft and front sheet plus the outer edge wall) parallel to the face: X = face_x_at(r) + offset_aft (aft) and + thickness more (front),
    from start_r to the shield radius, with the given windows cut through both sheets. Returns (vertices, faces, omitted_quads_per_sheet)."""
    radii = [r for r in sheet_radii(s) if r >= (cone_start_radius(s) if start_r is None else start_r)-1e-9]; thetas = sheet_angles(s); n = len(thetas)
    top, ft, om = revolved_sheet(radii, thetas, lambda r: face_x_at(s, r)+offset_aft+thickness, windows)
    aft, fa, _ = revolved_sheet(radii, thetas, lambda r: face_x_at(s, r)+offset_aft, windows, flip=True)
    m = len(top); last = (len(radii)-1)*n
    wall = [(last+j, last+(j+1) % n, m+last+(j+1) % n, m+last+j) for j in range(n)]
    return top+aft, ft+[tuple(m+i for i in f) for f in fa]+wall, om


def shield_skin_mesh(s):
    """The conical skin annulus from the body radius to the shield radius with the 12 Crown windows. Vertices, faces, omitted quads per sheet."""
    t = prototype(s)['skin_thickness_m']
    return conical_plate(s, -t, t, crown_skin_windows(s), start_r=body_radius(s))


def disruptor_mesh(s, layer):
    """Conical part of a layer (cone start to the shield radius) with the 12 Crown ports. The flat hub part is `disruptor_flat`."""
    return conical_plate(s, layer['standoff'], layer['thickness'], crown_ports(s))


def disruptor_flat(s, layer):
    """Flat hub disc of a layer: outer circle at the cone start (same angles as the cone sheets) and the circular holes: one port per well and the Lance
    hole. Each loop is a list of (y, z); the first is the outer boundary."""
    thetas = sheet_angles(s); rc = cone_start_radius(s)
    circle = lambda r, cy=0.0, cz=0.0, n=48: [(cy+r*math.cos(2*math.pi*i/n), cz+r*math.sin(2*math.pi*i/n)) for i in range(n)]
    loops = [[(rc*math.cos(t), rc*math.sin(t)) for t in thetas]]
    loops += [circle(q['radius'], q['y'], q['z']) for q in eye_ports(s, layer) if math.hypot(q['y'], q['z'])+q['radius'] < rc]
    loops.append(circle(lance_hole_radius(s, layer)))
    return dict(loops=loops, x_aft=layer['aft_hub'], x_front=layer['front_hub'])


def eye_shutters(s):
    """FD-E03 / AG-007 armoured eyelids (PROTOTYPE): per well, two leaves on the shield face, between the skin and the disruptor layer, that part
    tangentially by half the leaf width. Closed, they meet on the well axis and overlap the well lip by crown_shutter_overlap_m; open, each leaf lies
    beside the well. A frame at the well mouth carries them (local +X axial, +Y radial, +Z tangential, as the Crown bays). The tangential parting is
    the only direction the FWD-V2 placement screen clears at r 4, 16 and 24 m (eye_placement.shutter_travel); mechanism, drive and erosion life OPEN
    (OD-020). Also the replaceable sacrificial window cartridge inside the well, ahead of the facet (Q43: no exposed pane)."""
    p = prototype(s); ov = p['crown_shutter_overlap_m']; th = p['eye_shutter_thickness_m']; side = p['well_diameter_m']+2*ov; out = []
    # FD-B10 (Eye 45, owner 2026-10-13): an overlapping labyrinth seam, PROTOTYPE. Leaf B rides one leaf thickness forward of leaf A, and closed the
    # leaves overlap by eye_seam_overlap_m on the axis; each leaf is (side + seam)/2 wide, so the closed pair still covers exactly the well and its lip.
    seam = p['eye_seam_overlap_m']; half = (side+seam)/2; closed = (side-seam)/4; opened = side/2+half/2
    rc, R = cone_start_radius(s), shield_radius(s)
    for w in wells(s):
        az = math.atan2(w['z'], w['y'])
        # FWD-V2 study wells on the cone: the frame lies on the local face (tilt about the tangential axis, 0 in the flat hub), so the leaves keep
        # their gap to the skin instead of cutting it on the inner edge (FD-A06 collision evidence).
        tilt = math.atan(p['crown_depth_m']/(R-rc)) if math.hypot(w['y'], w['z'])-side/2 > rc else 0.0
        x = w['x1']+(p['eye_shutter_gap_m']+th/2)/math.cos(tilt)
        out.append(dict(index=w['index'], label=w['label'], azimuth=az, tilt=tilt, x=x, y=w['y'], z=w['z'], thickness=th, radial=side, tangential=half,
                        closed_t=closed, open_t=opened, travel=opened-closed, seam_overlap=seam, axial_step=th,
                        leaves=[dict(name=f"EYE_Shutter_{w['index']:02}_{k}", sign=sg, axial=ax) for k, sg, ax in (('A', 1.0, 0.0), ('B', -1.0, th))],
                        window=dict(name=f"EYE_Window_{w['index']:02}", x=w['x0']+p['eye_window_inset_m'], radius=s['eye']['aperture']['value']/2+ov,
                                    thickness=p['eye_window_thickness_m'])))
    return out


def truss_boresight_margin(s, ax, r, x0, x1):
    """Smallest (Y, Z) clearance between a boresight cylinder (axis ax, radius r, X x0..x1) and the built truss: spoke members and rings not
    replaced by the alternate truss, and its collars, branches, ring arcs and facet frames (the facet frame plate sits behind x0)."""
    t = truss(s); m = t['member_radius']; out = math.inf
    segs = [(pts, m) for sp in t['spokes'] for lab, pts in sp['members'] if f"Truss_Spoke_{sp['index']:02}_{lab}" not in t['removed']]
    segs += [(q['pts'], q['radius']) for q in t['alternate'] if not q.get('plate') and q['role'] != 'raceway']
    for pts, rad in segs:
        for a, b in zip(pts, pts[1:]):
            if max(a[0], b[0]) >= x0 and min(a[0], b[0]) <= x1:
                same = math.isclose(a[1], b[1], abs_tol=1e-12) and math.isclose(a[2], b[2], abs_tol=1e-12)     # an axial member projects to a point
                gap = math.dist(ax, (a[1], a[2])) if same else distance_point_segment(ax, (a[1], a[2]), (b[1], b[2]))
                out = min(out, gap-r-rad)
    d = math.hypot(*ax)
    for k, ring in enumerate(t['rings']):
        if f'Truss_Ring_{k+1:02}' not in t['removed'] and x0 <= ring['x'] <= x1:
            out = min(out, abs(ring['radius']-d)-r-m)
    return out


def eye_line_of_sight(s):
    """Per well: the boresight cylinder (the well's own radius, from the facet face along +X to the Lance-tip plane) against every opaque F2 solid: the
    layers (the port must contain the cylinder), the posts, the Lance and its column, the mount struts, the hub truss ring and the Crown. Margins in metres;
    the diversion-field zone is a display and exempt. Also compares each port with the derived no-vignetting radius."""
    st = stations(s); p = prototype(s); rows = []; layers = disruptor_layers(s); posts = disruptor_posts(s); struts = mount_struts(s); ln = lance(s)
    for w in wells(s):
        x0, x1 = w['x0'], st['lance_tip']; ax = (w['y'], w['z']); d_axis = math.hypot(*ax); r = w['radius']
        margins = {'lance': d_axis-r-max(ln['base_r'], p['lance_tip_radius_m'])}
        if in_hub(s, w):
            margins['hub_ring'] = st['hub_opening_r']-(d_axis+r)
        else:          # outer layout: the boresight against every built truss member (kept spokes and rings, alternate collars, branches, frames)
            margins['truss'] = truss_boresight_margin(s, ax, r, x0, x1)
        for layer in layers:
            a, f = layer_x(s, layer, 0.0)
            if f >= x0 and a <= x1:
                port = next(q for q in eye_ports(s, layer) if q['index'] == w['index'])
                margins[f"port_{layer['index']}"] = port['radius']-r
                margins[f"port_{layer['index']}_derived"] = port['radius']-eye_port_required_radius(s, layer)
                margins[f"lance_hole_{layer['index']}"] = d_axis-r-lance_hole_radius(s, layer)
        margins['posts'] = min((math.hypot(q['r']*math.cos(q['azimuth'])-ax[0], q['r']*math.sin(q['azimuth'])-ax[1])-r-q['radius'] for q in posts if q['x1'] >= x0 and q['x0'] <= x1), default=math.inf)
        margins['struts'] = min((distance_point_segment(ax, (q['a'][1], q['a'][2]), (q['b'][1], q['b'][2]))-r-q['radius'] for q in struts if x0 <= q['x'] <= x1), default=math.inf)
        margins['crown'] = p['crown_housing_inner_radius_m']-(d_axis+r)
        rows.append(dict(well=w['index'], margins=margins, min_margin=min(margins.values()), ok=all(v >= -1e-9 for v in margins.values())))
    return rows


# ---------- diversion field zone (display only) ------------------------------------------------------------------------

def field_zone(s):
    """Display zone of the diversion field: an elongated closed surface of revolution from the Brow face to the Lance tip, pinched onto the Lance (with
    the field_zone_lance_clearance_m) at both ends, widest near the middle. Outer radius = Lance radius + clearance + field_zone_max_radius_m sin(pi u).
    The 10,000 m3 study volume stays DIAGNOSTIC; the displayed volume is reported as a display metric only (ARTISTIC)."""
    st = stations(s); p = prototype(s); d = s['forward_shield']['display']; n = d['field_zone_axial_samples']; x0, x1 = st['field']
    xs = [x0+(x1-x0)*i/(n-1) for i in range(n)]
    inner = [lance_radius_at(s, x)+p['field_zone_lance_clearance_m'] for x in xs]
    outer = [r+p['field_zone_max_radius_m']*math.sin(math.pi*i/(n-1)) for i, r in enumerate(inner)]
    volume = sum(math.pi*((outer[i]**2-inner[i]**2)+(outer[i+1]**2-inner[i+1]**2))/2*(xs[i+1]-xs[i]) for i in range(n-1))
    return dict(x=xs, r_in=inner, r_out=outer, length=x1-x0, max_r=max(outer), aspect=(x1-x0)/(2*max(outer)), display_volume_m3=volume)


# ---------- Aegis Dustbreak Crown (PROTOTYPE proxy; OD-021) --------------------------------------------------------

def crown(s):
    """Housing, bays, windows, shutters and carriages. Bay k (0-based) sits at azimuth 2 pi k / bay_count, measured from +Y toward +Z; each carriage
    translates axially (+X) in the bay frame (local +X axial, +Y radial, +Z tangential). The skin window is the stowed carriage footprint plus the
    shared clearance; the shutter lies under the conical skin and slides tangentially."""
    st = stations(s); p = prototype(s); clr = clearance(s); n = p['crown_bay_count']
    x0, x1 = st['housing']; xc = (x0+x1)/2; car_axial = p['crown_carriage_axial_m']; half_r = p['crown_carriage_radial_m']/2
    w0 = p['crown_stowed_radius_m']-half_r-clr; w1 = p['crown_stowed_radius_m']+half_r+clr
    sov = p['crown_shutter_overlap_m']; sth = p['crown_shutter_thickness_m']
    return dict(x0=x0, x1=x1, xc=xc, inner_r=p['crown_housing_inner_radius_m'], outer_r=p['rim_inner_radius_m'], wall_r=p['rim_inner_radius_m'],
                window_w=p['crown_window_width_m'], window=dict(r0=w0, r1=w1, half_angle=(p['crown_window_width_m']/2)/p['crown_stowed_radius_m']),
                shutter=dict(radial=(w1-w0)+2*sov, tangential=p['crown_window_width_m']+2*sov, thickness=sth, r_centre=(w0+w1)/2,
                             x=skin_aft_at(s, w1+sov)-clr-sth/2),
                carriage=dict(axial=car_axial, radial=p['crown_carriage_radial_m'], tangential=p['crown_carriage_tangential_m']),
                carriage_x=x0+clr+car_axial/2, stowed_r=p['crown_stowed_radius_m'],
                emitter=dict(radius=p['crown_emitter_diameter_m']/2, length=p['crown_emitter_length_m'], t=-.2),
                launcher=dict(radius=p['crown_launcher_diameter_m']/2, length=p['crown_launcher_length_m'], t=.3),
                bays=[dict(index=k+1, azimuth=2*math.pi*k/n, turn=k/n) for k in range(n)])


def crown_muzzle_x(s):
    """Stowed X of the emitter and launcher muzzles (both protrude the same length)."""
    c = crown(s)
    return c['carriage_x']+c['carriage']['axial']/2+c['emitter']['length']


def layer_front_at_port(s):
    """The most forward layer front at the inner edge of the Crown port, where the conical layer is highest."""
    c = crown(s)
    return max(layer_x(s, layer, c['window']['r0'])[1] for layer in disruptor_layers(s))


def crown_stroke_m(s):
    """Axial carriage travel that puts the muzzles one shared clearance ahead of the most forward layer front at the inner edge of the port. Derived;
    radial travel is zero (Q6: mainly forward)."""
    return layer_front_at_port(s)+clearance(s)-crown_muzzle_x(s)


def z_max_r_guard(s):
    """Largest radius of the diversion-field display zone (the port covers stay outside it)."""
    return field_zone(s)['max_r']


def crown_slide(s):
    """Shutter travel along the bay tangent that fully uncovers its window."""
    return crown(s)['shutter']['tangential']


def crown_facing(s, values):
    """Per bay 1 for the bays in the half-open window (-tie, +tie] of crown_azimuth, else 0: four bays at the default 12 (the tie-break turns shift
    the window so exactly four qualify even at a bay centre)."""
    n = prototype(s)['crown_bay_count']; tie = prototype(s)['crown_tiebreak_turns']; a = values['crown_azimuth']
    return [1.0 if math.cos(2*math.pi*(a-k/n-tie)) > .5 else 0.0 for k in range(n)]


def crown_faulted(s, values):
    """Per bay 1 for the bay crown_fault selects (crown_fault x bay count = bay index, 0 = none), else 0."""
    n = prototype(s)['crown_bay_count']; f = values['crown_fault']
    return [1.0 if abs(f*n-(k+1)) < .5 else 0.0 for k in range(n)]


def crown_open_weights(s, values):
    """Per bay carriage weight in [0, 1]: crown_engage on the facing bays, 0 on a faulted bay (it stays stowed)."""
    return [values['crown_engage']*w*(1-f) for w, f in zip(crown_facing(s, values), crown_faulted(s, values))]


def crown_shutter_weights(s, values):
    """Per bay shutter/cover opening: max(prepare, engage) on the facing bays; a faulted bay jams at half that."""
    o = max(values['crown_prepare'], values['crown_engage'])
    return [o*w*(1-.5*f) for w, f in zip(crown_facing(s, values), crown_faulted(s, values))]


def crown_head_angles(s, values):
    """Per bay gimbal angles (a about the bay +Z, b about the bay +Y, Blender XYZ Euler) that turn the head boresight from +X toward the threat:
    off-boresight angle theta = crown_point x crown_head_max_deg x carriage weight toward crown_azimuth. Distant target: every head turns to the same
    direction, so cooperating sectors point in parallel (local sub-arrays, never a phased 90 m aperture, FD-E04)."""
    n = prototype(s)['crown_bay_count']; tmax = math.radians(prototype(s)['crown_head_max_deg']); out = []
    for k, w in enumerate(crown_open_weights(s, values)):
        th = tmax*values['crown_point']*w; dl = 2*math.pi*(values['crown_azimuth']-k/n)
        out.append((math.atan2(math.sin(th)*math.cos(dl), math.cos(th)), -math.asin(math.sin(th)*math.sin(dl))))
    return out


# ---------- controls, presets, display poses ---------------------------------------------------------------------

def neutral(s):
    return {k: 0.0 for k in PROPS}


def configuration_state(s, name):
    """Control values a buildable preset poses: the preset row's damage/Crown controls, with the field switched by forward_defense.field_states (Q4)."""
    d = s['forward_defense']; preset = d['presets'][name]; on = 1.0 if d['field_states'][name] else 0.0
    return {**neutral(s), 'field_on': on, 'field_strength': on, **{k: float(preset[k]) for k in PRESET_KEYS}}


def display_pose(s, name):
    """Control values of a preview-only pose: the base preset plus its overrides. Never saved, never a configuration."""
    pose = s['forward_defense']['display_poses'][name]
    return {**configuration_state(s, pose['base']), **{k: float(v) for k, v in pose.items() if k in PROPS}}


def drivers(s):
    """(object, data path, index, expression). Blender builds exactly these; display() evaluates them."""
    p = prototype(s); out = []
    for path in ('hide_viewport', 'hide_render'):
        out.append(('Field_Zone', path, -1, '(fo<=0) or (fs<=0)'))
    for axis in (1, 2):
        out.append(('Field_Zone', 'scale', axis, 'min(1,max(0,fs))'))
    n = p['damage_ring_count']*p['damage_sector_count']
    for cell in damage_cells(s):
        k = cell['index']
        # A cell shows while it is inside the damaged fraction and outside the repaired fraction (repair heals from the first cell).
        for path in ('hide_viewport', 'hide_render'):
            out.append((f"Shield_Damage_Cell_{cell['ring']:02}_{cell['sector']:02}", path, -1, f'(dmg*{n}<={k}) or (rep*{n}>{k})'))
    stroke = crown_stroke_m(s); slide = crown_slide(s); c = crown(s); count = len(c['bays'])
    tie = p['crown_tiebreak_turns']; tmax = math.radians(p['crown_head_max_deg'])
    for b in c['bays']:
        k = b['index']-1
        # Constants folded and rounded so the longest (head) expression stays inside Blender's 256-character driver limit.
        sel = f'(cos(6.283185307*az-{2*math.pi*(k/count+tie):.10g})>0.5)'; flt = f'(abs(flt*{count}-{k+1})<0.5)'
        w = f'eng*{sel}*(1-{flt})'; o = f'max(prep,eng)*{sel}*(1-0.5*{flt})'
        th = f'{tmax:.10g}*pt*{w}'; dl = f'(6.283185307*az-{2*math.pi*k/count:.10g})'
        out.append((f"Crown_Carriage_{b['index']:02}", 'location', 0, f"{c['carriage_x']!r}+{stroke!r}*{w}"))
        out.append((f"Crown_Shutter_{b['index']:02}", 'location', 2, f'{slide!r}*{o}'))
        out.append((f"Crown_Port_Cover_{b['index']:02}", 'location', 2, f"{crown_port_covers(s)[k]['slide']!r}*{o}"))
        out.append((f"Crown_Head_{b['index']:02}", 'rotation_euler', 2, f'atan2(sin({th})*cos({dl}),cos({th}))'))
        out.append((f"Crown_Head_{b['index']:02}", 'rotation_euler', 1, f'-asin(sin({th})*sin({dl}))'))
    for e in eye_shutters(s):
        j = e['index']
        for leaf in e['leaves']:
            out.append((leaf['name'], 'location', 2, f"{leaf['sign']*e['open_t']!r}-{leaf['sign']*e['travel']!r}*e{j}"))
    too_long = [f'{name}.{path}[{index}]' for name, path, index, expr in out if len(expr) > 255]
    if too_long:
        raise ValueError(f'Driver expressions over the 255-character Blender limit: {too_long}')
    return out


def expression_variables(expression):
    names = set(); token = ''
    for ch in expression+' ':
        if ch.isalnum() or ch == '_':
            token += ch
        else:
            if token in VARIABLES:
                names.add(token)
            token = ''
    return sorted(names)


def display(s, values):
    """Evaluate every driver for a control state: the exact values Blender should show."""
    env = {'min': min, 'max': max, 'abs': abs, 'cos': math.cos, 'sin': math.sin, 'atan2': math.atan2, 'asin': math.asin, '__builtins__': {}}
    env.update({var: float(values[prop]) for var, prop in VARIABLES.items()})
    return {(obj, path, index): float(eval(expr, env)) for obj, path, index, expr in drivers(s)}


def damage_visible(s, values):
    """Indices of the damage cells a control state shows (the same rule the hide drivers evaluate)."""
    n = prototype(s)['damage_ring_count']*prototype(s)['damage_sector_count']
    return [c['index'] for c in damage_cells(s) if values['damage_state']*n > c['index'] and not values['repair_state']*n > c['index']]


def crown_pose(s, values):
    """Per-bay carriage position (X and radius of the carriage and emitter), shutter travel and open flag for a control state."""
    c = crown(s); weights = crown_open_weights(s, values); stroke = crown_stroke_m(s); sw = crown_shutter_weights(s, values)
    covers = crown_port_covers(s); heads = crown_head_angles(s, values); faults = crown_faulted(s, values); facing = crown_facing(s, values)
    return [dict(index=b['index'], weight=w, carriage_r=c['stowed_r'], carriage_x=c['carriage_x']+stroke*w, shutter_travel=crown_slide(s)*o,
                 cover_travel=cv['slide']*o, open=w > 0, shutter_open=o > 0, head=h, faulted=bool(f and fc), state=sector_state(values, w, o, f*fc))
            for b, w, o, cv, h, f, fc in zip(c['bays'], weights, sw, covers, heads, faults, facing)]


def sector_state(values, w, o, fault):
    """AG-008 sector state of one bay from its weights: DEGRADED (faulted facing bay), ENGAGED (carriage fully out), RECOVERING (carriage part way
    with the shutter open), PREPARED (shutter open, carriage stowed), STOWED."""
    if fault:
        return 'DEGRADED'
    if w >= 1.0:
        return 'ENGAGED'
    if w > 0:
        return 'RECOVERING' if values['crown_prepare'] > 0 else 'ENGAGING'
    return 'PREPARED' if o > 0 else 'STOWED'


def crown_hardware_points(s, values):
    """(radius, x) of every carriage-body corner and emitter/launcher loft vertex of every bay in a control state, with the head turned about its
    pivot (bay-frame axial at the carriage front). Mirrors the generator's vertices, so inspect can compare the measured radius exactly."""
    c = crown(s); car = c['carriage']; e, l = c['emitter'], c['launcher']; out = []
    for r in crown_pose(s, values):
        a, b = r['head']; ca, sa, cb, sb = math.cos(a), math.sin(a), math.cos(b), math.sin(b)
        turn = lambda x, y, z: (ca*(cb*x+sb*z)-sa*y, sa*(cb*x+sb*z)+ca*y, -sb*x+cb*z)      # Rz(a) Ry(b)
        front = car['axial']/2; R = r['carriage_r']
        out += [(math.hypot(R+dy*car['radial']/2, dz*car['tangential']/2), r['carriage_x']+dx*car['axial']/2) for dx in (-1, 1) for dy in (-1, 1) for dz in (-1, 1)]
        for part, seg, x0, x1 in ((e, 16, 0.0, e['length']), (l, 12, e['length']-l['length'], e['length'])):
            for x in (x0, x1):
                for i in range(seg):
                    q = turn(x, part['radius']*math.cos(2*math.pi*i/seg), part['t']+part['radius']*math.sin(2*math.pi*i/seg))
                    out.append((math.hypot(R+q[1], q[2]), r['carriage_x']+front+q[0]))
    return out


def envelope_diameter(s, values):
    """Largest diameter swept by any Crown hardware part (carriage body corners, emitter, launcher) in a control state: a PROTOTYPE pose metric, not a
    fixed-envelope claim."""
    return 2*max(r for r, _ in crown_hardware_points(s, values))


def pose_states(s):
    """Every control state the Crown radius and motion checks sweep: all presets, all display poses and a crown_azimuth sweep at full engagement."""
    d = s['forward_defense']
    states = [configuration_state(s, k) for k, v in d['presets'].items() if isinstance(v, dict)]
    states += [display_pose(s, k) for k, v in d['display_poses'].items() if isinstance(v, dict)]
    states += [{**neutral(s), 'crown_engage': 1.0, 'crown_point': 1.0, 'crown_azimuth': i/SWEEP_STEPS} for i in range(SWEEP_STEPS+1)]
    return states


def engaged_hardware_radius_m(s):
    """Largest radius reached by any Crown hardware part over all presets, display poses and the azimuth sweep at full engagement."""
    return max(envelope_diameter(s, v) for v in pose_states(s))/2


def crown_radial_travel_m(s):
    """Largest radial carriage displacement from the stowed radius over every state (Q6: mainly forward means none)."""
    c = crown(s)
    return max(abs(r['carriage_r']-c['stowed_r']) for v in pose_states(s) for r in crown_pose(s, v))


def crown_axial_stroke_m(s):
    """Largest axial carriage displacement from the stowed X over every state."""
    c = crown(s)
    return max(r['carriage_x']-c['carriage_x'] for v in pose_states(s) for r in crown_pose(s, v))


def engaged_muzzle_margin_m(s):
    """Engaged muzzle X minus the most forward layer front at the port's inner edge (>= the shared clearance)."""
    c = crown(s)
    return crown_muzzle_x(s)+crown_axial_stroke_m(s)-layer_front_at_port(s)


def sector_truss_count(s):
    """Distinct primary-sector azimuths whose keel (at the sourced sector radius) is tied into the Brow truss by its hub tie and both truss-node ties."""
    R = s['structure']['sector_radius_m']; keels = {k['index']: k for k in sector_keels(s)}
    labels = {}
    for t in sector_ties(s):
        if math.isclose(keels[t['sector']]['r'], R, abs_tol=1e-9):
            labels.setdefault((t['sector'], round(t['theta'], 9)), set()).add(t['target'])
    return sum(1 for v in labels.values() if v == {'hub', 'a', 'b'})      # a sector counts only with its hub tie and both truss-node ties


def corridor_clearance_rows(s):
    """Each docking corridor against the shield structure: the truss aft surface at every radius (smallest at the rim), the Crown housing aft plate, the
    sector keels and hoops, and the ties. Gaps in metres, minimum first, with pass/fail against the shared clearance."""
    import hull_geometry
    st = stations(s); clr = clearance(s); c = crown(s); keels = sector_keels(s); ties = sector_ties(s); hoops = keel_hoop_points(s)
    out = {}
    for q in hull_geometry.dock_corridors(s):
        x1 = q['x']+q['radius']; u = (math.cos(q['theta']), math.sin(q['theta']))
        a = (q['x'], q['r0']*u[0], q['r0']*u[1]); b = (q['x'], q['r1']*u[0], q['r1']*u[1])
        gaps = {'truss_aft': min(truss_aft_at(s, r) for r in (q['r0'], q['r1']))-x1, 'rim': st['rim'][0]-x1, 'crown_housing': c['x0']-x1}
        gaps['keels'] = min(segment_distance(a, b, k['a'], k['b'])-q['radius']-k['radius'] for k in keels)
        gaps['keel_hoops'] = min(segment_distance(a, b, (h[0], h[1], h[2]), (h[0], h[1], h[2]))-q['radius']-h[3] for h in hoops)
        gaps['ties'] = min(segment_distance(a, b, t['a'], t['b'])-q['radius']-t['radius'] for t in ties)
        out[q['name']] = dict(gaps_m=gaps, min_gap_m=min(gaps.values()), passes=min(gaps.values()) >= clr-1e-9)
    return out


def design_classes(s):
    """kind -> design class (HSFP, 98!A58) from forward_shield.design_classes."""
    t = s['forward_shield']['design_classes']; out = {}
    for cls in DESIGN_CLASSES:
        for kind in t[cls]:
            out[kind] = cls
    return out


# ---------- study formulas (DIAGNOSTIC / WORKING checks of captured rows; none feeds geometry) ---------------------

def study(s):
    d = s['forward_defense']; i = d['crown_inputs']; st = i['study']; eta = s['eye']['power_inputs']['laser_wall_plug_efficiency']
    optical = i['active_sectors']*i['pulse_energy_J']*i['rep_rate_Hz']
    electrical = optical/eta
    kinetic = .5*st['interceptor_mass_kg']*st['interceptor_speed_m_s']**2
    shot_in = kinetic/st['launcher_efficiency']
    rate = 1/(s['mission']['target_speed']['value']*SPEED_OF_LIGHT)
    shield_r = shield_radius(s)
    return dict(optical_W=optical, electrical_W=electrical, heat_W=electrical-optical,
                local_store_J=10*i['active_sectors']*i['pulse_energy_J']/eta,
                interceptor_kinetic_J=kinetic, interceptor_input_J=shot_in, interceptor_loss_J=shot_in-kinetic,
                field_energy_J=st['diversion_field_T']**2*st['diversion_volume_m3']/(2*MU0),
                shadow_angle_deg=math.degrees(math.atan(d['shadow_angle']['margin_m']/d['shadow_angle']['distance_m'])),
                mass_loading_kg_m2=s['brow']['mass']['value']/(math.pi*shield_r**2),
                seconds_per_metre=rate, standoff_s=d['timing']['study_standoff_m']*rate)


def validate_budgets(s):
    """Captured study rows must reproduce from their inputs. Returns the failures; empty when consistent."""
    out = []; v = study(s); d = s['forward_defense']; pw = d['power']
    def close(a, b, tol=1e-9):
        return math.isclose(a, b, rel_tol=tol, abs_tol=1e-9)
    n = pw['crown_normal']
    for key, want in [('optical_W', v['optical_W']), ('electrical_W', v['electrical_W']), ('heat_W', v['heat_W'])]:
        if not close(n[key], want):
            out.append(f'Crown normal {key}: captured {n[key]}, inputs give {want}')
    eta = s['eye']['power_inputs']['laser_wall_plug_efficiency']
    for name in ('crown_heavy', 'crown_extreme'):
        row = pw[name]
        if not (close(row['electrical_W'], row['optical_W']/eta) and close(row['heat_W'], row['electrical_W']-row['optical_W'])):
            out.append(f'{name}: electrical must be optical/eta and heat their difference')
    if not (pw['crown_normal']['optical_W'] < pw['crown_heavy']['optical_W'] < pw['crown_extreme']['optical_W']):
        out.append('Crown modes must increase normal < heavy < extreme')
    if not close(d['crown_inputs']['local_store_J'], v['local_store_J']):
        out.append('Crown local store is ten four-sector volleys at the wall-plug efficiency')
    # The workbook prints these to 3-8 digits (14.286 MJ, 4285714.286 J, ~3.98 GJ), so compare at the printed precision.
    for key, tol in (('interceptor_kinetic_J', 1e-9), ('interceptor_input_J', 1e-4), ('interceptor_loss_J', 1e-9), ('field_energy_J', 5e-3)):
        if not close(pw['derived_checks'][key], v[key], tol):
            out.append(f"{key}: captured {pw['derived_checks'][key]}, inputs give {v[key]}")
    if not close(d['shadow_angle']['value_deg'], v['shadow_angle_deg'], 1e-8):
        out.append('Shadow angle differs from atan(margin / distance)')
    if not math.isclose(d['shadow_angle']['margin_m'], s['forward_shield']['radiator_shadow_margin']['value']):
        out.append('Shadow-angle margin must be the radiator shadow margin')
    bands = pw['bands_W']
    ordered = [bands[k] for k in ('proactive', 'normal_active', 'severe', 'extreme_burst')]
    if any(lo >= hi for lo, hi in ordered) or any(a[1] > b[0] for a, b in zip(ordered, ordered[1:])):
        out.append('Defence power bands must be ordered and non-overlapping')
    # Q8/Q9: the Crown share and its pulse banks sit INSIDE the 100 t forward-protection envelope; nothing is added to the 1,100 t burnout mass.
    cm = d['crown_mass']; items = {i['id']: i for i in s['physics']['mass_budget']['items']}; env = items.get(cm['envelope_item'])
    if env is None or cm['additive'] is not False:
        out.append('Crown mass is a non-additive suballocation of a mass-budget item')
    elif not 0 < cm['suballocation_kg'] < env['mass_kg'] or env['mass_kg'] != s['brow']['mass']['value']:
        out.append(f"Crown suballocation {cm['suballocation_kg']} kg must lie inside the {env['mass_kg']} kg forward-protection envelope (= brow.mass)")
    if cm['envelope_item'] != s['brow']['mass']['budget_item']:
        out.append('Crown envelope item must be the Brow budget item')
    pb = d['crown_pulse_banks']
    node = d
    for part in pb['energy_ref'].split('.')[1:]:
        node = node[part] if isinstance(node, dict) and part in node else None
    if node is None or not close(node, d['crown_inputs']['local_store_J']):
        out.append('Crown pulse banks take their ~20 MJ from forward_defense.crown_inputs.local_store_J')
    if pb['mass_accounted_in'] != 'forward_defense.crown_mass' or pb['double_count'] is not False or 'LOCAL_PULSE_BANKS' not in cm['covers']:
        out.append('Crown pulse-bank mass is counted once, inside the Crown suballocation')
    return out




# ---------- validation ------------------------------------------------------------------------------------------------

def validate(s):
    """Spec-level rules of the forward structure. Raises ValueError on the first failure."""
    def need(ok, message):
        if not ok:
            raise ValueError(message)
    fs = s['forward_shield']; raw = fs['prototype']; p = prototype(s); st = stations(s); clr = clearance(s); R = body_radius(s); d = s['forward_defense']
    need(fs['bow_form']['value'] == 'FIXED_SHIELD_WITH_RECESSED_EYE_WELLS', 'Bow form must be the fixed shield with recessed EYE wells')
    need(fs['stack'].get('known') is False and 'value' not in fs['stack'], 'Shield stack stays OPEN (known = false)')
    need(p['status'] == 'PROTOTYPE' and p['unit'] == 'm', 'forward_shield.prototype labelling')
    for key in ('crown_depth_m', 'lance_length_m', 'lance_base_radius_m', 'lance_tip_radius_m', 'lance_tip_cartridge_m', 'well_diameter_m'):
        need(key not in raw, f'forward_shield.prototype.{key}: a sourced value lives in its own table only (one place per value)')
    for key, value in p.items():
        if key.endswith('_m') and isinstance(value, (int, float)):
            need(math.isfinite(value) and value > 0, f'forward_shield.prototype.{key}: positive dimension')
    for key in ('truss_spoke_count', 'damage_ring_count', 'damage_sector_count', 'crown_bay_count'):
        need(type(p[key]) is int and p[key] > 0, f'forward_shield.prototype.{key}: positive integer')
    need(0 <= p['damage_cell_inset_fraction'] < .5 and p['crown_tiebreak_turns'] > 0 and p['eye_port_scale'] > 0, 'Damage inset / tie-break / port scale range')
    for key in ('field_display_radius_m', 'field_line_count', 'field_line_radius_m', 'crown_engaged_emitter_radius_m'):
        need(key not in raw, f'forward_shield.prototype.{key}: removed by FWD-001 (display lines and radial Crown travel are gone)')
    standoffs = p['disruptor_standoffs_m']
    need(isinstance(standoffs, list) and standoffs and all(isinstance(v, (int, float)) and v > 0 for v in standoffs) and standoffs == sorted(standoffs), 'Disruptor standoffs: a sorted positive list')
    # Shield, conical face and rim.
    need(st['shield_r'] > R, 'The shield is wider than the body')
    need(p['rim_inner_radius_m'] < st['shield_r'], 'Rim member must have a radial depth inside the shield radius')
    need(p['skin_thickness_m'] < p['truss_depth_m'], 'Skin thinner than the truss')
    need(st['hub_opening_r'] > R+clr, 'The truss hub opening must pass the body collar with the shared clearance')
    need(R < st['hub_opening_r'] < st['cone_r'] < p['truss_ring_radii_m'][0] < p['truss_ring_radii_m'][-1] < p['crown_housing_inner_radius_m'] < p['rim_inner_radius_m'] < st['shield_r'], 'Truss radii order')
    need(tuple(sorted(p['truss_ring_radii_m'])) == tuple(p['truss_ring_radii_m']), 'Truss rings sorted')
    need(math.isclose(crown_depth_m(s), d['shield_profile']['crown_depth_m'], abs_tol=1e-9) and d['shield_profile']['form'] == 'SHALLOW_FORWARD_CONVEX_CONICAL', 'The face is the sourced conical profile (Q3)')
    need(face_x_at(s, 0.0) == st['face'] and face_x_at(s, st['cone_r']) == st['face'] and face_x_at(s, st['shield_r']) < st['face'], 'Flat hub, cone sweeping aft')
    need(st['truss_aft'] < st['truss_aft_hub'] < st['mount_face']+p['truss_depth_m'], 'Truss aft face sweeps aft toward the rim')
    # EYE wells.
    q = s['eye']['array_baseline']['value']/(2*math.sqrt(2)); aperture = s['eye']['aperture']['value']; wr = p['well_diameter_m']/2
    need(p['well_diameter_m'] > aperture, 'Well diameter must exceed the facet aperture')
    need(st['well_depth'] > 0 and st['well_depth'] < p['skin_thickness_m']+p['truss_depth_m'], 'Wells stay recessed: depth below skin plus truss')
    need(math.hypot(q, q)+wr+clr <= R-s['hull']['shell_thickness_m'], 'Wells must fit inside the body collar')
    need(2*q-2*wr >= clr, 'Adjacent wells must clear each other')
    need(math.hypot(q, q)-wr-p['lance_base_radius_m'] >= clr, 'Wells must clear the Dust Lance')
    need(R > math.hypot(q, q)+wr+clr, 'The hub plate must surround every well')
    need(math.hypot(q, q)+wr+clr <= st['cone_r'], 'Wells sit in the flat hub, inside the cone start radius')
    # Dust Lance.
    need(p['lance_tip_radius_m'] < p['lance_base_radius_m'] and p['lance_tip_cartridge_m'] < p['lance_length_m'], 'Lance taper and cartridge')
    ln = s['ship']['length']; lance_row = d['dust_lance']['length']
    need(ln['envelope_scope'] == 'OVERALL_INCLUDING_DUST_LANCE' and ln['value_scope'] == 'BODY_AFT_TO_SHIELD_FACE' and lance_row.get('known') is True and lance_row['unit'] == 'm'
         and lance_row['canon_status'] == 'WORKING', 'The Dust Lance length is a WORKING value and counts inside the overall length (Q2)')
    need(ln['min'] <= overall_length(s) <= ln['max']+1e-9,
         'Overall length INCLUDING the Dust Lance (aft end to Lance tip) must stay inside the 220-240 m working envelope (Q2)')
    need(math.isclose(overall_length(s)-ln['value'], lance_row['value'], abs_tol=1e-9), 'Overall length is the body length plus the Lance length')
    need(st['mount_face'] < st['skin_aft'] and st['lance_cone_end'] > st['face'], 'Lance column and cone ordering')
    # Load path: column from the spine end to the hub, bore through the EYE mount, struts to the truss hub ring (hub path, the only path into the ship); keels and ties form a Brow-side sector frame whose aft ends are free (draft Q45).
    need(st['spine_end'] < st['mount_face'] and p['lance_base_radius_m'] >= layout.spine_radius_at(s, st['spine_end']), 'The column starts on the spine end, at least as thick as the spine')
    need(fs_ok_bore(s), 'The EYE mount bore must pass the column and leave the backing ring intact')
    need(p['shield_mount_count'] >= 3 and p['shield_mount_member_radius_m'] > 0, 'At least three shield-mount struts')
    m = p['shield_mount_member_radius_m']
    for strut in mount_struts(s):
        need(st['truss_aft_hub']+m <= strut['x'] <= st['skin_aft']-m, f"{strut['name']} lies inside the truss depth")
        for w in wells(s):
            dd = distance_point_segment((w['y'], w['z']), (strut['a'][1], strut['a'][2]), (strut['b'][1], strut['b'][2]))
            need(dd >= w['radius']+m+clr, f"{strut['name']} must clear the EYE wells")
    need(all(math.isclose(strut['r1'], st['hub_opening_r']) and strut['r0'] == p['lance_base_radius_m'] for strut in mount_struts(s)), 'Struts run from the column surface to the hub ring inner radius')
    lp = d['shield_load_path']
    need(len(sector_keels(s)) == lp['primary_sectors'] and sector_truss_count(s) >= lp['primary_sectors'] and len(mount_struts(s)) >= 3,
         'Brow sector frame: one keel per primary sector, each tied into the Brow truss, plus the hub path')
    bc = bypass_clearances(s)
    need(all(v >= clr-1e-9 for v in bc.values()), f'Bypass collar (Q45) clears the ring sweeps, blade front, shield edge and docking corridors: {bc}')
    backing_aft = st['mount_face']-s['prototype']['eye_backing_depth_m']; backing_r = s['prototype']['eye_backing_radius_m']
    for k in sector_keels(s):
        need(k['x0'] < k['x1'] and k['x1']+k['hoop_radius'] < st['truss_aft_hub'], f"{k['name']}: keel ahead of ring B and behind the hub truss")
        need(k['x1']+k['hoop_radius']+clr <= backing_aft, f"{k['name']}: the keel head clears the EYE backing")
    for t in sector_ties(s):
        for i in range(21):
            u = i/20; x = t['a'][0]+(t['b'][0]-t['a'][0])*u; r = math.hypot(t['a'][1]+(t['b'][1]-t['a'][1])*u, t['a'][2]+(t['b'][2]-t['a'][2])*u)
            if r < backing_r+t['radius']:
                need(x+t['radius']+clr <= backing_aft, f"{t['name']} clears the EYE backing")
    # Docking corridors against the shield structure, and ring sweeps; the hull collar must stop short of the skin.
    import hull_geometry
    rows = corridor_clearance_rows(s)
    need(all(r['passes'] for r in rows.values()), f'Docking corridors must clear the shield structure: {rows}')
    need(st['truss_aft']-(max(habitat_ring.centers(s))+habitat_ring.sweep_half(s)) >= clr, 'Truss aft face must clear the ring sweeps')
    need(st['collar_end'] > st['front'], 'Hull collar must extend past the EYE facet faces')
    # Full-area sacrificial disruptor and its ports.
    layers = disruptor_layers(s)
    need(disruptor_layer_count(s) == len(layers) >= 1, 'Every disruptor layer is full diameter and entirely ahead of the Brow (FWD1)')
    for layer in layers:
        need(layer['front_hub']+clr <= st['lance_tip'], f"{layer['name']}: the layer stays behind the Lance tip")
        need(math.isclose(layer['outer_r'], st['shield_r']) and layer['thickness'] > 0, f"{layer['name']}: full shield radius")
        ports = eye_ports(s, layer)
        need(all(q_['radius'] >= eye_port_required_radius(s, layer)-1e-9 for q_ in ports), f"{layer['name']}: every EYE port at least the no-vignetting radius")
        if not eye_layout_active(s):
            need(all(math.hypot(q_['y'], q_['z'])+q_['radius']+clr <= st['cone_r'] for q_ in ports), f"{layer['name']}: EYE ports lie in the flat hub disc")
        else:          # outer layout: the ports open the cone, clear of the Crown ports and inside the Crown housing
            need(all(math.hypot(q_['y'], q_['z'])+q_['radius']+clr <= prototype(s)['crown_housing_inner_radius_m'] for q_ in ports), f"{layer['name']}: EYE ports stay inside the Crown housing")
        need(all(math.hypot(q_['y'], q_['z'])-q_['radius']-lance_hole_radius(s, layer) >= clr for q_ in ports), f"{layer['name']}: ports clear the Lance hole")
        need(all(math.dist((a['y'], a['z']), (b['y'], b['z']))-a['radius']-b['radius'] >= clr for i, a in enumerate(ports) for b in ports[i+1:]), f"{layer['name']}: ports clear each other")
    for post in disruptor_posts(s):
        for layer in layers[:1]:
            for pt in eye_ports(s, layer):
                need(math.hypot(post['r']*math.cos(post['azimuth'])-pt['y'], post['r']*math.sin(post['azimuth'])-pt['z']) >= pt['radius']+post['radius']+clr-1e-9, f"{post['name']} stands inside an EYE port")
        for w in crown_ports(s):
            ang = abs(((post['azimuth']-w['azimuth']+math.pi) % (2*math.pi))-math.pi)
            need(not (w['r0']-post['radius'] <= post['r'] <= w['r1']+post['radius'] and ang*post['r'] < w['width']/2+post['radius']), f"{post['name']} stands inside a Crown port")
    need(all(r['ok'] for r in eye_line_of_sight(s)), f'EYE line of sight blocked: {eye_line_of_sight(s)}')
    # Diversion field zone.
    need(0 < fs['display']['field_zone_alpha'] <= 1 and 0 < fs['display']['disruptor_alpha'] <= 1 and fs['display']['kind'] == 'IMPLEMENTATION', 'forward_shield.display is an IMPLEMENTATION table with alphas in (0, 1]')
    need(type(fs['display']['field_zone_axial_samples']) is int and fs['display']['field_zone_axial_samples'] >= 9 and fs['display']['field_zone_around'] >= 12, 'Field zone sampling')
    z = field_zone(s)
    need(z['aspect'] > 1.0 and z['x'][0] >= st['face']-1e-9 and z['x'][-1] <= st['lance_tip']+1e-9, 'The field zone is elongated, between the Brow face and the Lance tip (never a bubble)')
    need(all(zi >= lance_radius_at(s, xi)+p['field_zone_lance_clearance_m']-1e-9 for xi, zi in zip(z['x'], z['r_in'])) and z['max_r'] < st['cone_r'], 'The field zone clears the Lance and stays inside the flat hub radius')
    # Crown.
    c = crown(s); n = len(c['bays']); crown_inputs = d['crown_inputs']
    need(n >= crown_inputs['active_sectors'], 'The Crown needs at least N_crown bays')
    need(n % 2 == 0 and n >= 4, 'Crown bay count must allow four open bays symmetrically')
    need(c['x0'] >= truss_aft_at(s, c['inner_r'])-1e-9 and c['x1'] <= skin_aft_at(s, c['outer_r'])+1e-9, 'Crown housing sits axially inside the conical truss depth')
    need(c['outer_r'] <= st['shield_r'] and c['inner_r'] < c['outer_r'], 'Crown housing radii inside the shield')
    car = c['carriage']; half_r = car['radial']/2; win = c['window']
    need(c['inner_r'] <= win['r0']-1e-9 and win['r1'] <= c['outer_r'] and car['axial'] > 0, 'Stowed carriage and its skin window clear of the housing walls')
    need(car['tangential']+2*clr <= c['window_w'], 'Carriage passes its window tangentially')
    need(c['stowed_r']+half_r <= c['outer_r'] and c['stowed_r']+half_r+clr <= st['shield_r'], 'Stowed Crown inside the rim radius')
    e = c['emitter']; l = c['launcher']
    need(abs(e['t'])+e['radius'] <= car['tangential']/2 and l['t']+l['radius'] <= car['tangential']/2 and (l['t']-l['radius'])-(e['t']+e['radius']) > 0,
         'Emitter and launcher fit the carriage without overlapping')
    need(l['length'] > 0 and e['length'] > 0, 'Emitter / launcher lengths')
    sh = c['shutter']
    need(crown_muzzle_x(s)+clr <= sh['x']-sh['thickness']/2, 'Stowed muzzles stay behind the shutter')
    need(sh['x']+sh['thickness']/2 <= skin_aft_at(s, c['window']['r1'])-clr+1e-9, 'Shutters lie under the skin')
    need(crown_slide(s)-sh['tangential']/2 >= c['window_w']/2, 'A slid shutter fully uncovers its window')
    need(crown_stroke_m(s) > 0 and engaged_muzzle_margin_m(s) >= clr-1e-9, 'Engaged muzzles fire ahead of the disruptor layer')
    need(all(sh['x']+sh['thickness']/2 < layer_x(s, layer, c['window']['r0'])[0] for layer in layers), 'Shutters lie behind the layer')
    # Q44: small layer ports, each behind a normally closed cover; audit against the carriage path, the shutters, the posts and the field zone.
    for q, cv in zip(crown_ports(s), crown_port_covers(s)):
        need(car['tangential']+2*clr <= q['width']+1e-9 and q['r0'] <= c['stowed_r']-half_r-clr+1e-9 and q['r1'] >= c['stowed_r']+half_r+clr-1e-9, f"Crown port {q['index']}: the engaged carriage passes it")
        need(q['width'] < c['window_w'], f"Crown port {q['index']}: smaller than the skin window (Q44)")
        need(cv['slide']-cv['tangential']/2 >= q['width']/2, f"Crown port cover {q['index']}: slid, it fully uncovers its port")
        need(cv['x']+cv['thickness']/2 <= min(layer_x(s, layer, q['r1']+prototype(s)['crown_shutter_overlap_m'])[0] for layer in layers)-clr+1e-9, f"Crown port cover {q['index']}: behind the layer")
        need(cv['x']-cv['thickness']/2 >= sh['x']+sh['thickness']/2+clr and crown_muzzle_x(s)+clr <= cv['x']-cv['thickness']/2, f"Crown port cover {q['index']}: ahead of the stowed muzzles and the skin shutter")
        need(cv['r_centre']-cv['radial']/2 > z_max_r_guard(s), f"Crown port cover {q['index']}: clear of the field zone")
        for post in disruptor_posts(s):
            ang = abs(((post['azimuth']-q['azimuth']+math.pi) % (2*math.pi))-math.pi)
            need(not (cv['r_centre']-cv['radial']/2-post['radius'] <= post['r'] <= cv['r_centre']+cv['radial']/2+post['radius'] and ang*post['r'] < cv['tangential']/2+cv['slide']+post['radius']+clr),
                 f"Crown port cover {q['index']}: its travel clears {post['name']}")
    # Presets and poses.
    presets = {k: v for k, v in d['presets'].items() if isinstance(v, dict)}
    import spec
    need(set(presets) == set(spec.buildable_configurations(s)), 'forward_defense.presets must name exactly the buildable configurations')
    names = set(PROPS)
    need(set(d['controls']['names']) == names, 'forward_defense.controls.names')
    need('open_question' not in d['presets'], 'forward_defense.presets: OQ-F3 is closed by Q4, no open question remains')
    for name, preset in presets.items():
        need(set(preset) == set(PRESET_KEYS) and all(0 <= v <= 1 for v in preset.values()), f'{name}: preset rows carry only {PRESET_KEYS}; the field follows forward_defense.field_states')
        need(preset['crown_engage'] == 0 and preset['damage_state'] == 0 and preset['repair_state'] == 0, f'{name}: Crown shutters closed, no damage in a preset')
    poses = {k: v for k, v in d['display_poses'].items() if isinstance(v, dict)}
    for name, pose in poses.items():
        need(pose['base'] in presets and name not in presets, f'{name}: display poses name a base preset and are never configurations')
        need(all(0 <= v <= 1 for k, v in display_pose(s, name).items()), f'{name}: pose values')
    for name, values in [(k, display_pose(s, k)) for k in poses]:
        rows = crown_pose(s, values); opened = [r for r in rows if r['open']]; faulted = sum(r['faulted'] for r in rows)
        need(not opened or len(opened)+faulted == crown_inputs['active_sectors'], f'{name}: exactly N_crown bays open (less a DEGRADED bay)')
        need(sum(r['shutter_open'] for r in rows) in (0, crown_inputs['active_sectors']), f'{name}: shutters open only on the N_crown facing bays')
    need(not validate_budgets(s), f'Forward defence budgets: {validate_budgets(s)}')
    for key in ('magnetic_diversion.field', 'regenerative.repair'):
        node = d
        for part in key.split('.'):
            node = node[part]
        need(node.get('known') is False, f'forward_defense.{key} stays OPEN')
    for key in ('crown.open', 'crown.effective_aperture'):
        node = d
        for part in key.split('.'):
            node = node[part]
        need(node.get('known') is False, f'forward_defense.{key} stays OPEN')
    need(d['power_thermal_closure'].get('known') is False, 'The defence thermal closure stays OPEN')
    need(d['dust_lance']['geometry']['unit'] == 'm' and d['dust_lance']['geometry']['canon_status'] == 'WORKING', 'Lance geometry is a WORKING source table')
    need(all(node.get('known') is False for node in (d['disruptor_layer']['stack'], d['dustbreak_veil']['open'])), 'Disruptor layer stack and veil details stay OPEN')
    need(math.isclose(s['prototype']['eye_front_inset_m'], d['eye_wells']['depth_m']) and
         math.isclose(s['eye']['array_baseline']['value']/2, d['eye_wells'].get('source_centre_radius_m', d['eye_wells']['centre_radius_m'])),
         'EYE wells keep the WORKING depth and the r4 source radius (Q3) behind any study layout; B_array = 2 r4 stays the r4 calibration (FD-B07)')
    port = d['eye_wells']['outer_port']
    need(math.isclose(port['diameter_m'], 2*port['radius_m']) and all(eye_port_radius(s, q) >= port['radius_m']-1e-9 for q in disruptor_layers(s)),
         'EYE outer ports: radius 2.25 m / diameter 4.50 m (FD-A04); the modelled port never shrinks below it')
    states = d['field_states']
    names = set(spec.buildable_configurations(s))
    need(names <= set(states) and all(type(states[k]) is bool for k in names), 'forward_defense.field_states gives a boolean for every buildable configuration (Q4)')
    need(states['spherical_bubble'] is False and states['threat_procedure_override'] is True, 'The field is an elongated zone, never a spherical bubble; threat procedures may switch it on in DOCKED/EVA')
    for name in names:
        need(math.isclose(configuration_state(s, name)['field_on'], 1.0 if states[name] else 0.0), f'{name}: the preset field follows the Q4 field state')
    # FD-E03 eyelids: each open leaf clears the other wells, the Lance hole and the layer posts, lies under the layer, and the closed pair covers the well.
    for e in eye_shutters(s):
        ur = (math.cos(e['azimuth']), math.sin(e['azimuth'])); ut = (-ur[1], ur[0]); others = [w for w in wells(s) if w['index'] != e['index']]
        need(2*e['closed_t']+e['tangential'] >= 2*wr+2*p['crown_shutter_overlap_m']-1e-9 and e['radial'] >= 2*wr, f"EYE eyelid {e['index']}: the closed leaves cover the well")
        need(e['x']+e['axial_step']+e['thickness']/2 < min(layer_x(s, layer, math.hypot(e['y'], e['z']))[0] for layer in disruptor_layers(s)), f"EYE eyelid {e['index']}: under the disruptor layer")
        need(e['tangential']-2*e['closed_t'] >= e['seam_overlap']-1e-9 and e['axial_step'] >= e['thickness']-1e-9, f"EYE eyelid {e['index']}: closed leaves lap at the seam (FD-B10)")
        for sg in (1, -1):
            c = (e['y']+sg*ut[0]*e['open_t'], e['z']+sg*ut[1]*e['open_t'])
            def gap(pt):
                dx, dy = pt[0]-c[0], pt[1]-c[1]; a, b = abs(dx*ur[0]+dy*ur[1]), abs(dx*ut[0]+dy*ut[1])
                return math.hypot(max(a-e['radial']/2, 0.0), max(b-e['tangential']/2, 0.0))
            obstacles = [((w['y'], w['z']), w['radius']) for w in others]+[((0.0, 0.0), lance_hole_radius(s, disruptor_layers(s)[0]))]
            obstacles += [((q['r']*math.cos(q['azimuth']), q['r']*math.sin(q['azimuth'])), q['radius']) for q in disruptor_posts(s) if q['layer'] == 1]
            need(min(gap(q)-r for q, r in obstacles) >= clr, f"EYE eyelid {e['index']}: the open leaf clears the other wells, the Lance and the layer posts")
    # HSFP design classes (98!A58): three classes, every kind listed once.
    dc = fs['design_classes']
    need(dc['status'] == 'PROTOTYPE' and dc['doctrine_ref'] == 'hsfp_design_doctrine', 'forward_shield.design_classes is a PROTOTYPE registry citing hsfp_design_doctrine')
    need(rear_construction_screen(s) == 'PASS', f'forward_shield.rear_construction leaves the truss envelope: {rear_construction_screen(s)}')
    kinds = [k for cls in DESIGN_CLASSES for k in dc[cls]]
    need(len(kinds) == len(set(kinds)) and all(type(k) is str for k in kinds), 'Every object kind has exactly one design class')
    return True


def contract(s):
    """Simulation-rig section: controls, presets, poses, structure and the sourced/DIAGNOSTIC study rows. Plain JSON types only."""
    st = stations(s); p = prototype(s); d = s['forward_defense']; v = study(s); z = field_zone(s); layers = disruptor_layers(s)
    f = lambda x: float(x)
    keels0 = sector_keels(s)[0]; cage_end_x = primary_cage_end_x(s); col = bypass_collar(s)
    presets = {k: {a: f(b) for a, b in configuration_state(s, k).items()} for k in sorted(k for k, x in d['presets'].items() if isinstance(x, dict))}
    poses = {k: {a: f(b) for a, b in display_pose(s, k).items()} for k in sorted(k for k, x in d['display_poses'].items() if isinstance(x, dict))}
    def quantity(node):
        """Open nodes keep their reason and no value; a known node (the WORKING Lance length) carries known, value and unit."""
        keys = ('canon_status', 'evidence_ref', 'source_ref', 'reason', 'unit', 'note')
        out = {'known': node.get('known') is not False, **{k: node[k] for k in keys if k in node}}
        if out['known']:
            out['value'] = float(node['value'])
        return out
    rule = lambda node: {k: node[k] for k in ('rule', 'canon_status', 'source_ref', 'evidence_ref') if k in node}
    return {
        'status': 'PROTOTYPE rig over WORKING/BASELINE forward-defence direction; geometry PROTOTYPE, values OPEN where marked',
        'control': f'{SUBSYSTEM}.blend:{CONTROL}', 'units': 'normalized 0-1; no physical rating', 'saved_state': 'NEUTRAL (all controls 0)',
        'controls': {k: PROPS[k] for k in PROPS}, 'presets': presets, 'display_poses': poses,
        'preset_status': {'canon_status': 'PROTOTYPE', 'field_source': 'forward_defense.field_states (Q4, WORKING)'},
        'structure': {'shield_radius_m': f(st['shield_r']), 'face_x_m': f(st['face']), 'skin_aft_x_m': f(st['skin_aft']), 'truss_aft_x_m': f(st['truss_aft']),
                      'truss_aft_hub_x_m': f(st['truss_aft_hub']), 'crown_depth_m': f(crown_depth_m(s)), 'flat_hub_radius_m': f(st['cone_r']),
                      'lance_tip_x_m': f(st['lance_tip']), 'overall_length_m': f(overall_length(s)), 'lance_length': quantity(d['dust_lance']['length']),
                      'overall_length_includes_lance': s['ship']['length']['envelope_scope'] == 'OVERALL_INCLUDING_DUST_LANCE', 'well_depth_m': f(st['well_depth']),
                      'well_diameter_m': f(p['well_diameter_m']), 'crown_bays': f(p['crown_bay_count']), 'geometry_status': 'PROTOTYPE',
                      'spine_end_x_m': f(st['spine_end']),
                      'load_path': ('Momentum Spine end -> Lance column (through the EYE mount bore) -> 4 radial shield-mount struts -> truss hub ring: the hub path; the spine shares loads (Q45). '
                                    f"3 forward sector keels at r 5 m (30/150/270 deg) -> 9 ties -> conical truss; the keel aft ends (X {f(keels0['x0']):g} m) and the outer truss ring tie into a stationary external "
                                    f"bypass collar (r {f(col['inner_r']):g}-{f(col['outer_r']):g} m) round both ring sweeps, whose aft frame (X {f(col['stations']['aft']):g} m) drops onto the three sector rails "
                                    f"at the primary cage end (X {f(cage_end_x):g} m): Q1 distribution into the primary sectors (Q45, 15!A99). Load split, member sizing and FEA OPEN; collar geometry PROTOTYPE"),
                      'sector_continuity': {'grounded': sector_continuity_gap_m(s) <= 1e-9, 'status': 'WORKING principle / PROTOTYPE geometry / FEA OPEN', 'source_ref': 'brow_rotor_bypass',
                                            'keel_aft_x_m': f(keels0['x0']), 'primary_cage_end_x_m': f(cage_end_x), 'gap_m': f(sector_continuity_gap_m(s))},
                      'bypass_collar': {'outer_radius_m': f(col['outer_r']), 'inner_radius_m': f(col['inner_r']), 'member_radius_m': f(col['member_radius']),
                                        'stations_x_m': {k: f(v) for k, v in col['stations'].items()}, 'members': len(col['members']), 'hoops': len(col['hoops']),
                                        'clearances_m': {k: f(v) for k, v in bypass_clearances(s).items()}, 'geometry_status': 'PROTOTYPE', 'mass': {'known': False, 'canon_status': 'OPEN'}},
                      'sector_keels': int(len(sector_keels(s))), 'sector_ties': int(len(sector_ties(s))), 'sector_ties_complete': int(sector_truss_count(s)),
                      'disruptor_layers': [{'index': int(q['index']), 'standoff_m': f(q['standoff']), 'display_thickness_m': f(q['thickness']), 'outer_radius_m': f(q['outer_r']),
                                            'aft_x_hub_m': f(q['aft_hub']), 'front_x_hub_m': f(q['front_hub']), 'canon_status': 'PROTOTYPE', 'count_status': 'OPEN'} for q in layers],
                      'disruptor_open_fraction': {'known': True, 'value': f(disruptor_open_fraction(s)), 'canon_status': 'DIAGNOSTIC',
                                                  'basis': 'EYE ports, Crown ports and the Lance hole over the projected shield disc; not a performance claim'},
                      'eye_port_radius_m': f(eye_port_radius(s, layers[0])), 'crown_stroke_m': f(crown_stroke_m(s)),
                      'eye_outer_port': {'radius_m': f(d['eye_wells']['outer_port']['radius_m']), 'diameter_m': f(d['eye_wells']['outer_port']['diameter_m']),
                                         'modelled_radius_m': f(eye_port_radius(s, layers[0])), 'canon_status': 'WORKING', 'evidence_ref': 'fwd_eye_optics',
                                         'basis': 'RADIUS 2.25 m, diameter 4.50 m (FD-A04); ray/impact field OPEN'},
                      'eye_baselines': eye_baselines(s),
                      'field_zone': {'length_m': f(z['length']), 'max_radius_m': f(z['max_r']), 'aspect': f(z['aspect']), 'display_volume_m3': f(z['display_volume_m3']),
                                     'canon_status': 'DIAGNOSTIC', 'basis': 'Display metric of the PROTOTYPE zone; the 10,000 m3 study volume is a different DIAGNOSTIC value'}},
        'stack': quantity(s['forward_shield']['stack']),
        'engagement_order': {'sequence': list(d['order']['sequence']), 'canon_status': d['order']['canon_status'], 'source_ref': d['order']['source_ref']},
        'rules': {'dust_lance': rule(d['dust_lance']), 'magnetic_diversion': rule(d['magnetic_diversion']), 'diversion_boundary': rule(d['magnetic_diversion']['boundary']),
                  'regenerative': rule(d['regenerative']), 'repair_escalation': rule(d['regenerative']['escalation']), 'crown': rule(d['crown']),
                  'crown_engagement': rule(d['crown']['engagement']), 'crown_concealment': rule(d['crown']['concealment']), 'fiji_assistance': rule(d['fiji_assistance'])},
        'open': {'diversion_field': quantity(d['magnetic_diversion']['field']),
                 'repair': quantity(d['regenerative']['repair']), 'crown': quantity(d['crown']['open']), 'crown_effective_aperture': quantity(d['crown']['effective_aperture']),
                 'power_thermal_closure': quantity(d['power_thermal_closure'])},
        'open_items': [f'OD-{j:03}' for j in (14, 15, 17, 18, 19, 20, 21, 22)],
        'crown_inputs': {'active_sectors': f(d['crown_inputs']['active_sectors']), 'pulse_energy_J': f(d['crown_inputs']['pulse_energy_J']),
                         'rep_rate_Hz': f(d['crown_inputs']['rep_rate_Hz']), 'local_store_J': f(d['crown_inputs']['local_store_J']), 'canon_status': 'WORKING', 'source_ref': 'eye_crown_inputs'},
        'derived': {k: {'known': True, 'value': f(x), 'canon_status': 'DIAGNOSTIC' if k in ('interceptor_kinetic_J', 'interceptor_input_J', 'interceptor_loss_J', 'field_energy_J', 'shadow_angle_deg', 'mass_loading_kg_m2', 'seconds_per_metre', 'standoff_s') else 'DERIVED',
                         'basis': 'Study formula over captured inputs; checks the captured row and never feeds geometry.'} for k, x in v.items()},
        'power': {k: ({a: f(b) for a, b in x.items() if isinstance(b, (int, float))} | {'canon_status': x['canon_status']}) for k, x in d['power'].items() if k.startswith('crown_')},
        'pose_metrics': {'engaged_envelope_diameter_m': f(2*engaged_hardware_radius_m(s)),
                         'basis': 'PROTOTYPE pose metric over every Crown hardware part at the stowed radius (no radial travel; the carriage corner is the outermost, about r 43.35 m); not a fixed-envelope claim.'}}
