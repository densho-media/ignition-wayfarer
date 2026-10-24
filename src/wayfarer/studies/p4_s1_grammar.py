"""Phase 4 S1 (owner P4-EXP, 2026-10-24): NONCANON exterior grammar experiment on Aegis Crown bay 1 with its 30 deg Brow aft sector,
plus a transfer probe on one ring A 15 deg exterior segment. Built in memory as ART_P4_* objects on the saved vehicle; nothing is saved and
no generator reads this. Matched cameras, sun and exposure across the variants (docs/PHASE4_PLAN.md S1).

Function: decide which construction language makes the bow and the rings read, at whole-ship distance and at 1.8 m human scale, before
any grammar is codified (S2). The owner's leading hypothesis is an expressive functional hybrid (P4-ART): GU civic shells on pressure
volumes and Brow protection, exposed construction where parts articulate, attach, carry load or need service, thermal drama only where
the thermal design explains it. It is a hypothesis; the owner selects the grammar at the S1 review.
Fixed (read, never changed): every forward_shield and habitat_ring dimension; the Crown housing, windows, shutters, carriages, emitters,
launchers and their travel; the sunward skin; the EYE wells; the crawler lane; the ring frame envelope (r 24.5-30 m, |u| <= 2.0 m, the
2.15 m sweep half-depth) and the sector pressure envelopes; radiator cells, area and the 1800 K emission. M8.1 stays untouched as V0.
Unknown and not modelled: Crown carriage service path and hatch mechanism (OD-021 OPEN), shield thickness and stack, ring frame section
and load path (OD-016), any shielding or mass credit, coatings and emissivity (S&E 15 OWN-P4-LOCKED: depiction only).
Design freedom (PROTOTYPE judgment): cladding extent and module size, which structure is exposed, utility trays on the lane edges (power
and data to the Crown bay, routing PROTOTYPE), skin-back stiffeners, joint covers, the value ladder of each material family, marking
size and placement (text only: sector IDs, service and handling stencils; Art Style Spacecraft rows 17-18).

Variants (V0 control, then four grammars; V0T isolates the authorized COAST thermal depiction):
  V0   M8.1 as built, hero look (proxy grey + M4 functional marks), ring as generated
  V0T  V0 with only the dark high-emissivity-looking COAST blade surface (OWN-P4-LOCKED (a)); nothing else changed
  VA   civic: enclosed large calm cladding fields, flush service covers, truss wrapped, big wayfinding IDs
  VB   open machine: cladding removed to the frames; skin-back stiffeners, lane utility trays and node plates exposed
  VC   restrained hybrid: shells on the Brow back and pressure faces, machinery exposed at the lane, Crown hatch and ring joints
  VCP  expressive hybrid: VC geometry, stronger value contrast, GU deep-blue wayfinding accent, bolder IDs
Whole-ship views repeat each variant's bay and segment modules on all twelve bays and all 48 ring segments in memory, only so the
whole-ship read can be judged; S1 rolls nothing out.

    /snap/bin/blender -b --python src/wayfarer/studies/p4_s1_grammar.py -- --out runs/<stamp>-p4-s1 [--variants ...] [--views ...]
                                                                          [--size 1280] [--samples 24] [--screen-only]
"""
from pathlib import Path
import argparse
import itertools
import json
import math
import sys
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/build'), str(ROOT/'src/wayfarer/presentation')]
from spec import load
import production_detail as pd
import forward_shield as fsh
import habitat_ring as hr

M8 = sys.modules['pack_m8_forward']
VARIANTS = ('V0', 'V0T', 'VA', 'VB', 'VC', 'VCP')
TITLE = {'V0': 'V0 — M8.1 as built (control)', 'V0T': 'V0T — V0 + dark COAST blade depiction only',
         'VA': 'VA — civic (enclosed GU construction)', 'VB': 'VB — open machine (exposed structure and services)',
         'VC': 'VC — restrained hybrid', 'VCP': 'VC+ — expressive hybrid'}
SEG_DEG = 15.0           # ring assembly segment pitch (M4 frames, 24 per ring), PROTOTYPE

# Material families, [r, g, b, roughness, metallic] in Blender linear colour (P4-MAT: depiction-only PROTOTYPE library; value separation
# light shell / middle structure / graphite machinery / dark thermal, ochre service and amber occupancy accents, GU blue only as a
# restrained wayfinding accent, tested in VC+ alone). Physical light unchanged; the 1800 K emission is applied by the hero look in IGNITION.
FAMILIES = {
    'VA': dict(shell=[.70, .69, .66, .60, 0], structure=[.62, .61, .58, .70, 0], machinery=[.32, .33, .35, .55, .1], thermal=[.035, .036, .04, .45, 0],
               service=[.66, .65, .62, .60, 0], amber=[.80, .42, .08, .60, 0], joint=[.30, .30, .31, .80, 0], mark=[.035, .037, .04, .70, 0],
               mark_light=[.80, .80, .77, .65, 0], blue=[.035, .037, .04, .70, 0], root=[.62, .61, .58, .70, 0]),
    'VB': dict(shell=[.50, .50, .48, .60, 0], structure=[.28, .29, .30, .55, .15], machinery=[.06, .065, .07, .50, .35], thermal=[.035, .036, .04, .45, 0],
               service=[.78, .60, .24, .58, 0], amber=[.80, .42, .08, .60, 0], joint=[.035, .035, .04, .85, 0], mark=[.80, .80, .77, .65, 0],
               mark_light=[.80, .80, .77, .65, 0], blue=[.80, .80, .77, .65, 0], root=[.28, .29, .30, .55, .15]),
    'VC': dict(shell=[.62, .61, .58, .60, 0], structure=[.30, .31, .32, .55, .1], machinery=[.075, .08, .085, .50, .3], thermal=[.035, .036, .04, .45, 0],
               service=[.78, .60, .24, .58, 0], amber=[.80, .42, .08, .60, 0], joint=[.04, .04, .045, .85, 0], mark=[.035, .037, .04, .70, 0],
               mark_light=[.80, .80, .77, .65, 0], blue=[.035, .037, .04, .70, 0], root=[.60, .59, .55, .65, 0]),
    'VCP': dict(shell=[.78, .77, .73, .55, 0], structure=[.22, .23, .24, .50, .15], machinery=[.03, .032, .035, .45, .4], thermal=[.02, .021, .024, .42, 0],
                service=[.82, .58, .18, .55, 0], amber=[.86, .38, .05, .55, 0], joint=[.025, .025, .03, .85, 0], mark=[.025, .027, .03, .70, 0],
                mark_light=[.88, .88, .85, .60, 0], blue=[.02, .07, .30, .55, 0], root=[.74, .73, .69, .60, 0]),
}
FAMILIES['V0T'] = dict(thermal=FAMILIES['VC']['thermal'])

# Ship-wide family of each generated material (WF_MAT_<name>), first matching prefix wins; a material not matched keeps the hero look.
# Read from the saved vehicle's material inventory (runs/<stamp>-p4-s1/materials.json lists every name and the family it got).
SHIP_RULES = [
    (('RadiatorA', 'RadiatorB'), 'thermal'),
    (('RadiatorRoot', 'RootBoot', 'CasingBoot'), 'root'),
    (('RingPressureBand',), 'amber'),
    (('RingServiceCover', 'CrownServiceHatch', 'Casing_Access_Panel'), 'service'),
    (('RingJoint', 'BrowPanelJoint', 'Casing_Strap', 'CrownRib'), 'joint'),
    (('Drive_Plasma', 'Plasma', 'Debug', 'Radiator'), None),               # display emitters and diagnostic layers keep their own look
    (('RootSteel', 'Structure', 'SectorKeel', 'ExpansionJoint', 'MountSlide', 'MountDatum', 'Truss', 'Spoke', 'Frame', 'Gusset', 'Keel', 'Tie'),
     'structure'),
    (('Crown', 'Carriage', 'Shutter', 'Emitter', 'Launcher', 'Drive', 'Nozzle', 'Thrust', 'Coil', 'Manifold', 'Rotor', 'Hub', 'Bearing',
      'Ext_RCS', 'Ext_Antenna', 'Ext_Sensor', 'Antenna', 'Mast', 'Drone', 'EyeHousing', 'EyeShutter', 'OpticsHardware', 'ServiceFitting',
      'CoolantChase', 'Locks'), 'machinery'),
    (('Shield', 'Brow', 'Forward', 'Lance', 'Habitat', 'Ring', 'Hull', 'Casing', 'Spine', 'Body', 'Collar', 'Dock', 'Ext_Dock'), 'shell'),
]


def ship_family(name):
    for prefixes, fam in SHIP_RULES:
        if name.startswith(prefixes):
            return fam
    return None


# ---------- pure geometry ------------------------------------------------------------------------------------------------------------

def el(name, fam, cls, function, vs, fs, bevel=0.0, **meta):
    q = dict(name=name, family=fam, surface_class=cls, function=function, vs=[tuple(map(float, v)) for v in vs], fs=pd.outward(vs, fs), bevel=bevel)
    q.update(meta)
    return q


def text(name, fam, function, body, centre, right, up, height, **meta):
    q = dict(name=name, family=fam, surface_class='ARTISTIC', function=function, text=body, centre=tuple(centre), right=tuple(right), up=tuple(up),
             height=height, vs=[], fs=[])
    q.update(meta)
    return q


def m8_params(s, **brow):
    """A copy of the spec with m8_forward's [params.brow] overridden (the pack functions read the spec)."""
    import copy
    t = copy.deepcopy(s)
    t['detail_packs']['m8_forward']['params']['brow'].update(brow)
    return t


def m8_crown(s, **crown):
    import copy
    t = copy.deepcopy(s)
    t['detail_packs']['m8_forward']['params']['crown'].update(crown)
    return t


M8_FAMILY = {'ext_cladding': 'shell', 'ext_service': 'structure', 'ext_protected': 'machinery', 'ext_doubler': 'machinery', 'ext_fastener': 'structure',
             'ext_cap': 'service', 'ext_amber': 'amber', 'ext_stencil': 'mark', 'ext_stencil_light': 'mark_light', 'ext_gasket': 'joint',
             # M8.2 (S3) emits the shared exterior families; the study reproduces S1 exactly only at 88ab15a (M8.1)
             'xf_shell': 'shell', 'xf_structure': 'structure', 'xf_machinery': 'machinery', 'xf_fastener': 'structure', 'xf_service': 'service',
             'xf_amber': 'amber', 'xf_mark': 'mark', 'xf_mark_light': 'mark_light', 'xf_joint': 'joint', 'xf_wayfinding': 'blue'}


def from_m8(q, fam=None, **meta):
    """An M8.1 element re-labelled into a study family (geometry unchanged)."""
    out = dict(q, family=fam or M8_FAMILY[q['material']]); out.update(meta)
    return out


def lane_edges(s, f, b, r0, r1):
    """Angular positions (deg) of the service lane's two edges at radius r (Crown bay azimuth b deg)."""
    q = pd.params(s, 'm8_forward')['brow']; h = q['lane_half_deg']; seam = q['seam_m']
    jg = lambda r: math.degrees((f['joint_w']/2+seam/2)/r)
    return (lambda r: b-h+jg(r)), (lambda r: b+h-jg(r))


def lane_trays(s, f, b, j, tag, r0=11.6, r1=40.2, fam='machinery'):
    """Exposed utility trays along both lane edges on the skin's aft face (power and data to Crown bay j; routing PROTOTYPE), with stand-offs
    every 2.5 m; they run between the skin's aft face and the truss, outside the forward-chord keep-outs (screened)."""
    out = []; lo, hi = lane_edges(s, f, b, r0, r1); w, h, off = .30, .14, .03
    runs = [(r0, r1)]
    for R in f['rings']:                     # break the trays at the forward ring chords' keep-outs
        cut = (R-f['keep']-.12, R+f['keep']+.12)
        runs = [p for a, c in runs for p in ((a, min(c, cut[0])), (max(a, cut[1]), c)) if p[1]-p[0] > .6]
    for side, edge in (('L', lambda r: math.radians(lo(r))+(w/2+.05)/r), ('R', lambda r: math.radians(hi(r))-(w/2+.05)/r)):
        for k, (a, c) in enumerate(runs):
            n = max(2, int((c-a)/1.0)+1); rs = [a+(c-a)*i/(n-1) for i in range(n)]
            vs = []
            for r in rs:
                phi = edge(r); t_, s_, n_ = M8.brow_axes(f, r, phi); p = M8.brow_point(f, r, off, phi)
                for dt, dn in ((-w/2, 0), (w/2, 0), (w/2, h), (-w/2, h)):
                    vs.append(tuple(p[i]+t_[i]*dt+n_[i]*dn for i in range(3)))
            fs = [(4*i+m, 4*i+(m+1) % 4, 4*(i+1)+(m+1) % 4, 4*(i+1)+m) for i in range(n-1) for m in range(4)]+[(3, 2, 1, 0), (4*(n-1), 4*(n-1)+1, 4*(n-1)+2, 4*(n-1)+3)]
            out.append(el(f'ART_P4_{tag}_LaneTray_{j:02}_{side}{k}', fam, 'ENGINEERING_FLEXIBLE',
                          'exposed utility tray, power/data to the Crown bay (routing PROTOTYPE, no rating)', vs, fs))
    return out


def skin_stiffeners(s, f, b, j, tag, fam='structure'):
    """Radial T-stiffeners on the skin's aft face between the lane and the spoke chords (VB: exposed skin-back stiffening, PROTOTYPE)."""
    out = []; lo, hi = lane_edges(s, f, b, 0, 0); keep = f['keep']
    for side in (-1, 1):
        for k in range(1, 4):
            for r0, r1 in M8.brow_bands(s, f):
                rr = [r0+.2, r1-.2]
                if rr[1]-rr[0] < .8:
                    continue
                phi = lambda r: math.radians(b+side*(5.0+2.5*k)) if abs(r*math.sin(math.radians(15.0-5.0-2.5*k))) > keep+.3 else None
                if phi(rr[0]) is None:
                    continue
                vs = []
                for r in rr:
                    p_ = phi(r); t_, s_, n_ = M8.brow_axes(f, r, p_); c = M8.brow_point(f, r, .008, p_)
                    for dt, dn in ((-.03, 0), (.03, 0), (.03, .16), (-.03, .16)):
                        vs.append(tuple(c[i]+t_[i]*dt+n_[i]*dn for i in range(3)))
                fs = [(m, (m+1) % 4, 4+(m+1) % 4, 4+m) for m in range(4)]+[(3, 2, 1, 0), (4, 5, 6, 7)]
                out.append(el(f'ART_P4_{tag}_Stiffener_{j:02}_{side:+d}_{k}_{r0:.0f}', fam, 'ENGINEERING_FLEXIBLE',
                              'skin-back radial stiffener (exposed; section PROTOTYPE, not a structural claim)', vs, fs))
    return out


def crown_plate_grid(s, j, tag, fam='structure'):
    """VB: a stiffener grid on the Crown housing's aft plate either side of the hatch (exposed plate stiffening, PROTOTYPE)."""
    f = M8.crown_frame(s); q = pd.params(s, 'm8_forward')['crown']; out = []; x0 = f['x0']; b = f['bays'][j]; B = math.degrees(b); half = 180.0/f['n']
    plate = lambda r, off, phi: (x0-off, r*math.cos(phi), r*math.sin(phi))
    h0, h1 = f['hatch_r']; U = f['hatch_half']+q['frame_gap_m']+q['frame_width_m']
    p0, p1 = q['panel_r_m']
    for side in (-1, 1):
        a = math.degrees((U+.1)/p0); e = half-math.degrees((f['rib_half']+q['rib_keep_m'])/p0)
        for r in (p0+.1, (p0+p1)/2, p1-.1):                         # hoop stiffeners
            q0, q1 = (B+a, B+e) if side > 0 else (B-e, B-a)
            vs, fs = pd.bent(plate, r-.04, r+.04, .004, .12, q0, q1, step_deg=1.0)
            out.append(el(f'ART_P4_{tag}_PlateHoop_{j:02}_{side:+d}_{r:.1f}', fam, 'ENGINEERING_FLEXIBLE', 'aft-plate hoop stiffener (PROTOTYPE)', vs, fs))
        for k in range(1, 4):                                       # radial stiffeners
            d = a+(e-a)*k/4; ph = math.radians(B+side*d); t = (0, -math.sin(ph), math.cos(ph))
            c = plate((p0+p1)/2, .062, ph)
            vs, fs = pd.box(c, ((1.0, 0, 0), (0, math.cos(ph), math.sin(ph)), t), (.116, p1-p0, .07))
            out.append(el(f'ART_P4_{tag}_PlateRib_{j:02}_{side:+d}_{k}', fam, 'ENGINEERING_FLEXIBLE', 'aft-plate radial stiffener (PROTOTYPE)', vs, fs))
    return out


def crown_flush_covers(s, j, tag, fam='shell'):
    """VA: one flush cover each side of the hatch over the whole bay plate (enclosed, few seams)."""
    f = M8.crown_frame(s); q = pd.params(s, 'm8_forward')['crown']; out = []; x0 = f['x0']; b = f['bays'][j]; B = math.degrees(b); half = 180.0/f['n']
    plate = lambda r, off, phi: (x0-off, r*math.cos(phi), r*math.sin(phi))
    U = f['hatch_half']+.06; p0, p1 = f['r_in']+.2, f['r_out']-.25
    for side in (-1, 1):
        a = math.degrees(U/p1); e = half-math.degrees((f['rib_half']+q['rib_keep_m'])/p0)
        q0, q1 = (B+a, B+e) if side > 0 else (B-e, B-a)
        vs, fs = pd.bent(plate, p0, p1, .004, .03, q0, q1, step_deg=1.0)
        out.append(el(f'ART_P4_{tag}_FlushCover_{j:02}_{side:+d}', fam, 'ENGINEERING_FLEXIBLE', 'flush bay cover (civic enclosure; access OPEN)', vs, fs, .01))
    return out


def lane_lines(s, f, b, j, tag, fam, width=.12):
    """A thin film line along each lane edge on the cladding side (wayfinding accent in VC+, dark closeout in VC)."""
    out = []; lo, hi = lane_edges(s, f, b, 0, 0); off = pd.params(s, 'm8_forward')['brow']['standoff_m']+pd.params(s, 'm8_forward')['brow']['thickness_m']+.003
    for side, edge in (('L', lambda r: math.radians(lo(r))-(.07+width/2)/r), ('R', lambda r: math.radians(hi(r))+(.07+width/2)/r)):
        for r0, r1 in M8.brow_bands(s, f):
            if r1 < 11.4 or r1-r0 < .8:
                continue
            r0 = max(r0, 11.4)
            vs = []
            for r in (r0+.1, r1-.1):
                p_ = edge(r); t_, s_, n_ = M8.brow_axes(f, r, p_); c = M8.brow_point(f, r, off, p_)
                for dt, dn in ((-width/2, 0), (width/2, 0), (width/2, .004), (-width/2, .004)):
                    vs.append(tuple(c[i]+t_[i]*dt+n_[i]*dn for i in range(3)))
            fs = [(m, (m+1) % 4, 4+(m+1) % 4, 4+m) for m in range(4)]+[(3, 2, 1, 0), (4, 5, 6, 7)]
            out.append(el(f'ART_P4_{tag}_LaneLine_{j:02}_{side}_{r0:.0f}', fam, 'ARTISTIC', 'lane-edge line (wayfinding / closeout marking)', vs, fs, film=True))
    return out


def resize_text(q, h):
    return dict(q, height=h)


def forward_elements(s, v):
    """Every study element of variant v on the Brow aft face and the Crown rim, all twelve bays (ship frame). V0/V0T: none (M8.1 shows)."""
    if v in ('V0', 'V0T'):
        return []
    f = M8.brow_frame(s); out = []; cr = fsh.crown(s)
    if v == 'VA':
        t = m8_params(s, panel_max_m=6.5, panel_max_width_m=9.5, seam_m=.05)
        for q in M8.brow_aft_elements(t):
            if q['family'] in ('fasteners', 'caps'):
                continue
            if 'text' in q:
                out.append(from_m8(resize_text(q, 1.2 if q['text'].startswith('S') else .40), 'mark'))
            elif q['family'] == 'boundary':
                out.append(from_m8(q, 'amber'))
            else:
                out.append(from_m8(q, 'shell'))
        for q in M8.crown_rim_elements(s):
            if q['family'] in ('frames', 'fasteners', 'panels'):
                continue
            if 'text' in q:
                out.append(from_m8(resize_text(q, 1.6 if 'Numeral' in q['name'] else .35), 'mark'))
            else:
                out.append(from_m8(q))
        for bay in cr['bays']:
            out += crown_flush_covers(s, bay['index'], 'VA')
        return out
    if v == 'VB':
        for q in M8.brow_aft_elements(s):
            if q['family'] == 'panels' and q['material'] != 'ext_protected' or q['family'] == 'caps':
                continue
            if q['family'] == 'fasteners' and q['material'] == 'ext_fastener' and 'Panel' in q['name']:
                continue
            if 'text' in q and 'SERVICE LANE' in q['text']:
                continue                                         # its lane panel is gone
            out.append(from_m8(q, 'mark' if 'text' in q else None))
        for bay in cr['bays']:
            b = math.degrees(bay['azimuth']); j = bay['index']
            out += lane_trays(s, f, b, j, 'VB') + skin_stiffeners(s, f, b, j, 'VB') + crown_plate_grid(s, j, 'VB')
        for q in M8.crown_rim_elements(s):
            if q['family'] == 'panels' or q['family'] == 'fasteners' and 'PanelBolt' in q['name']:
                continue
            out.append(from_m8(q, 'mark' if 'text' in q else None))
        return out
    # VC and VCP: M8.1 cladding kept as the civic shell, the lane opened to its trays, the Crown access panels in shell value against the
    # graphite doubler and the ochre hatch; markings re-sized for their reading distance.
    big = v == 'VCP'
    for q in M8.brow_aft_elements(s):
        if q['family'] == 'panels' and q['material'] == 'ext_service':
            continue                                             # the lane: opened
        if q['family'] == 'fasteners':
            continue                                             # fasteners: below the reading scale, no longer modelled here
        if 'text' in q and 'SERVICE LANE' in q['text']:
            continue                                             # its lane panel is opened; the trays and edge lines identify the lane
        if 'text' in q:
            out.append(from_m8(resize_text(q, (1.1 if big else .9) if q['text'].startswith('S') else (.36 if big else .32)), 'mark_light' if q['text'].startswith('S') else 'mark'))
        else:
            out.append(from_m8(q))
    tc = m8_crown(s, stripe_half_m=.28 if big else .20, hatch_stencil_m=.45 if big else .35, numeral_m=1.6 if big else 1.4)
    for q in M8.crown_rim_elements(tc):
        if q['family'] == 'fasteners':
            continue
        if q['family'] == 'panels':
            out.append(from_m8(q, 'shell'))
        else:
            out.append(from_m8(q, 'mark' if 'text' in q else None))
    for bay in cr['bays']:
        b = math.degrees(bay['azimuth']); j = bay['index']
        out += lane_trays(s, f, b, j, v)
        out += lane_lines(s, f, b, j, v, 'blue' if big else 'joint', .12 if big else .08)
    return out


def forward_screen(s, els):
    """The pack screens of M8.1 (aft-face zone between skin and truss, chord keep-outs; Crown plate, ribs, hatch, rim and beacons)."""
    brow = [q for q in els if (q['centre'] if 'text' in q else q['vs'][0])[0] > fsh.stations(s)['housing'][1]]
    crown = [q for q in els if q not in brow]
    return M8.brow_aft_check(s, brow)+M8.crown_rim_check(s, crown)


# Ring segments: ring-local (u, r cos t, r sin t), u along the ring axis, the same frame habitat_ring builds the frame in.
def ring_frame(s):
    r = s['habitat_ring']
    return dict(R0=r['frame_inner_radius_m'], RS0=r['sector_inner_radius_m'], RS1=r['sector_outer_radius_m'], RO=hr.outer(s),
                H=r['frame_axial_m']/2, HS=r['sector_axial_m']/2, half=hr.sector_arc(s)/2, sweep=hr.sweep_half(s))


def solid(name, fam, cls, function, u0, u1, r0, r1, t0, t1, n=None, **meta):
    k = n or max(2, math.ceil(abs(t1-t0)/math.radians(1.5)))
    vs, fs = hr.ring_solid(u0, u1, r0, r1, t0, t1, k)
    return el(name, fam, cls, function, vs, fs, t0=t0, t1=t1, **meta)


def ring_segment(s, v, ring, k, sectors, spokes):
    """Study elements of segment k (centre 15k deg) of one ring for variant v; `sectors` the sector centre angles of this ring,
    `spokes` the structural spoke angles."""
    g = ring_frame(s); c = math.radians(SEG_DEG*k); a, b = c-math.radians(SEG_DEG/2), c+math.radians(SEG_DEG/2)
    pressure = any(abs(math.remainder(c-x, math.tau)) < 1e-6 for x in sectors)
    node = next((x for x in spokes if abs(math.remainder(c-x, math.tau)) < 1e-6), None)
    sid = next((i+1 for i, x in enumerate(sectors) if abs(math.remainder(c-x, math.tau)) < 1e-6), None)
    tag = f'ART_P4_{v}_R{ring}_S{k:02}'; R0, RS0, RS1, RO, H = g['R0'], g['RS0'], g['RS1'], g['RO'], g['H']
    out = []; gap = lambda m, r: m/2/r
    flank = lambda sgn, d0, d1: tuple(sorted((sgn*(H+d0), sgn*(H+d1))))
    names = 'A' if ring == 1 else 'B'
    if v == 'VA':
        for sgn in (-1, 1):
            u0, u1 = flank(sgn, .04, .08)
            for r0, r1 in ((R0+.05, (RS0+RS1)/2-.03), ((RS0+RS1)/2+.03, RO-.05)):
                lo, hi = a+gap(.05, r1), b-gap(.05, r1)
                if pressure and r0 < RS1 and r1 > RS0:              # over the recess: a calm cover spans the sector face at the frame plane
                    pass
                out.append(solid(f'{tag}_Clad_{sgn:+d}_{r0:.0f}', 'shell', 'ENGINEERING_FLEXIBLE', 'flank cladding panel (civic enclosure)', u0, u1, r0, r1, lo, hi))
            if pressure:
                u0, u1 = flank(sgn, .08, .085)
                out.append(solid(f'{tag}_Band_{sgn:+d}', 'amber', 'ARTISTIC', 'occupancy band over the pressurized sector', u0, u1, RO-1.0, RO-.45, a+gap(.05, RO), b-gap(.05, RO)))
        out.append(solid(f'{tag}_Rim', 'shell', 'ARTISTIC', 'rim cladding film', -H+.05, H-.05, RO-.012, RO, a+gap(.05, RO), b-gap(.05, RO)))
    elif v == 'VB':
        for sgn in (-1, 1):
            for t in (a, b):
                u0, u1 = flank(sgn, 0, .12)
                out.append(solid(f'{tag}_Web_{sgn:+d}_{t:.2f}', 'structure', 'ENGINEERING_FLEXIBLE', 'segment joint web frame (exposed)', u0, u1, R0, RO-.02, t-gap(.30, RS0), t+gap(.30, RS0), n=1))
            for f_ in (1/3, 2/3):
                t = a+(b-a)*f_
                if pressure and abs(math.remainder(t-c, math.tau)) < g['half']+gap(.2, RS0):
                    rr = ((R0, RS0), (RS1, RO-.02))
                else:
                    rr = ((R0, RO-.02),)
                for r0, r1 in rr:
                    u0, u1 = flank(sgn, 0, .08)
                    out.append(solid(f'{tag}_Rib_{sgn:+d}_{f_:.2f}_{r0:.0f}', 'structure', 'ENGINEERING_FLEXIBLE', 'intermediate radial stiffener (exposed)', u0, u1, r0, r1, t-gap(.12, RS0), t+gap(.12, RS0), n=1))
            for r in (R0+.25, RO-.65):
                u0, u1 = flank(sgn, 0, .07)
                out.append(solid(f'{tag}_Stringer_{sgn:+d}_{r:.0f}', 'structure', 'ENGINEERING_FLEXIBLE', 'circumferential stringer (exposed)', u0, u1, r-.06, r+.06, a+gap(.32, r), b-gap(.32, r)))
            u0, u1 = flank(sgn, .07, .13)
            for r in (R0+.55, RO-.95):
                out.append(solid(f'{tag}_Conduit_{sgn:+d}_{r:.0f}', 'machinery', 'ENGINEERING_FLEXIBLE', 'utility conduit run (routing PROTOTYPE)', u0, u1, r-.05, r+.05, a+gap(.4, r), b-gap(.4, r)))
        out.append(solid(f'{tag}_Groove', 'joint', 'ARTISTIC', 'rim joint groove', -H+.03, H-.03, RO-.01, RO, b-gap(.10, RO), b+gap(.10, RO), n=1))
    else:                                                        # VC / VCP
        big = v == 'VCP'
        for sgn in (-1, 1):
            u0, u1 = flank(sgn, .02, .06)
            spans = [(R0+.05, RS0-.02), (RS1+.02, RO-.05)] if pressure else [(R0+.05, RO-.05)]
            for r0, r1 in spans:
                lo, hi = a+gap(.36, r1), b-gap(.36, r1)
                if node is not None and r0 < RS0+1.5:
                    pieces = [(lo, node-math.radians(2.6)), (node+math.radians(2.6), hi)]
                else:
                    pieces = [(lo, hi)]
                for i, (p0, p1) in enumerate(pieces):
                    out.append(solid(f'{tag}_Cassette_{sgn:+d}_{r0:.0f}_{i}', 'shell', 'ENGINEERING_FLEXIBLE', 'flank cladding cassette (replaceable shell module)', u0, u1, r0, r1, p0, p1))
            if pressure:                                        # the pressure face in its recess: one calm shell panel per side
                u0, u1 = flank(sgn, -(H-g['HS'])+.01, -(H-g['HS'])+.035)
                out.append(solid(f'{tag}_Pressure_{sgn:+d}', 'shell', 'ENGINEERING_FLEXIBLE', 'pressure-sector face cladding (no shielding claim)', u0, u1, RS0+.15, RS1-.15, c-g['half']+gap(.3, RS0), c+g['half']-gap(.3, RS0)))
                u0, u1 = flank(sgn, .06, .065)
                out.append(solid(f'{tag}_Band_{sgn:+d}', 'amber', 'ARTISTIC', 'occupancy band over the pressurized sector', u0, u1, RO-1.05, RO-.45, a+gap(.4, RO), b-gap(.4, RO)))
            for t in (a, b):                                   # exposed joint frames: a mid-value web cap with a dark joint gap
                u0, u1 = flank(sgn, 0, .11)
                out.append(solid(f'{tag}_JointCap_{sgn:+d}_{t:.2f}', 'structure', 'ENGINEERING_FLEXIBLE', 'segment joint web cap (exposed frame)', u0, u1, R0, RO-.02, t-gap(.26, RS0), t-gap(.04, RS0), n=1))
                out.append(solid(f'{tag}_JointCap2_{sgn:+d}_{t:.2f}', 'structure', 'ENGINEERING_FLEXIBLE', 'segment joint web cap (exposed frame)', u0, u1, R0, RO-.02, t+gap(.04, RS0), t+gap(.26, RS0), n=1))
                u0, u1 = flank(sgn, 0, .03)
                out.append(solid(f'{tag}_JointGap_{sgn:+d}_{t:.2f}', 'joint', 'ARTISTIC', 'joint gap', u0, u1, R0, RO-.02, t-gap(.04, RS0), t+gap(.04, RS0), n=1))
            if node is not None:                               # structural spoke node: exposed machinery housing + ochre service cover
                u0, u1 = flank(sgn, 0, .12)
                out.append(solid(f'{tag}_Node_{sgn:+d}', 'machinery', 'ENGINEERING_FLEXIBLE', 'spoke node housing (exposed; contents OPEN)', u0, u1, R0, RS0+1.4, node-math.radians(2.5), node+math.radians(2.5)))
                u0, u1 = flank(sgn, .12, .135)
                out.append(solid(f'{tag}_NodeCover_{sgn:+d}', 'service', 'ENGINEERING_FLEXIBLE', 'node service cover (ochre)', u0, u1, R0+.3, RS0+1.1, node-math.radians(1.6), node+math.radians(1.6)))
        out.append(solid(f'{tag}_Groove', 'joint', 'ARTISTIC', 'rim joint groove', -H+.03, H-.03, RO-.012, RO, b-gap(.14, RO), b+gap(.14, RO), n=1))
        if pressure and big:
            out.append(solid(f'{tag}_Wayfinding', 'blue', 'ARTISTIC', 'GU deep-blue wayfinding stripe over the pressurized sector (restrained accent)', -.25, .25, RO-.012, RO, a+gap(.6, RO), b-gap(.6, RO)))
    if sid is not None and v != 'VB':                         # text-only sector ID on both flanks, over the outer hoop
        h = {'VA': 1.3, 'VC': .9, 'VCP': 1.1}[v]
        for sgn in (-1, 1):
            u = sgn*(H+(.0865 if v == 'VA' else .0625)); r = (RS1+RO)/2-.05 if v != 'VA' else (R0+RS0)/2+1.4
            pos = (u, r*math.cos(c), r*math.sin(c)); tang = (0, -math.sin(c), math.cos(c)); rad = (0, math.cos(c), math.sin(c))
            right = tang if sgn < 0 else tuple(-x for x in tang)        # tangent x radial = -u: the text reads from outside each flank
            out.append(text(f'{tag}_ID_{sgn:+d}', 'mark', 'ring sector ID (text only)', f'{names}{sid}', pos, right, rad, h))
    for q in out:
        q['local'] = True
    return out


def ring_elements(s, v):
    """{ring: [elements]} for variant v: all 24 segments of both rings (V0/V0T: none)."""
    if v in ('V0', 'V0T'):
        return {}
    out = {}
    for ring in range(1, hr.ring_count(s)+1):
        sectors = [q['angle'] for q in hr.sectors(s) if q['ring'] == ring]
        spokes = sorted({q['angle'] for q in hr.spokes(s) if q['ring'] == ring and not q['crew']})
        out[ring] = [q for k in range(int(360/SEG_DEG)) for q in ring_segment(s, v, ring, k, sectors, spokes)]
    return out


def ring_screen(s, els):
    """Every vertex inside the frame envelope widened to the sweep (r 24.5-30 m, |u| <= 2.15 m) and no part inside a sector envelope."""
    g = ring_frame(s); eps = 1e-6; fails = []
    secs = [q['angle'] for q in hr.sectors(s) if q['ring'] == 1]
    for q in els:
        if 'text' in q:
            u, y, z = q['centre']; pts = [q['centre']]
        else:
            pts = q['vs']
        for u, y, z in pts:
            rr = math.hypot(y, z)
            if abs(u) > g['sweep']+eps or rr < g['R0']-eps or rr > g['RO']+eps:
                fails.append(f"{q['name']}: outside the frame/sweep envelope at u {u:.3f}, r {rr:.3f}"); break
        if 'text' in q:
            continue
        us = [p[0] for p in pts]; rs = [math.hypot(p[1], p[2]) for p in pts]; ts = [math.atan2(p[2], p[1]) for p in pts]
        for c in secs:
            d = [math.remainder(t-c, math.tau) for t in ts]
            if min(d) < g['half']-eps and max(d) > -g['half']+eps and min(us) < g['HS']-eps and max(us) > -g['HS']+eps \
                    and min(rs) < g['RS1']-eps and max(rs) > g['RS0']+eps:
                fails.append(f"{q['name']}: enters a sector pressure envelope"); break
    return fails


def summary(s):
    out = {}
    for v in VARIANTS:
        fe = forward_elements(s, v); re_ = ring_elements(s, v)
        fam = {}
        for q in fe+[q for r in re_.values() for q in r]:
            fam[q['family']] = fam.get(q['family'], 0)+1
        out[v] = dict(title=TITLE[v], forward_elements=len(fe), ring_elements={str(k): len(x) for k, x in re_.items()}, families=fam,
                      forward_screen=forward_screen(s, fe) or 'PASS', ring_screen=sum((ring_screen(s, x) for x in re_.values()), []) or 'PASS')
    return out


# ---------- Blender ------------------------------------------------------------------------------------------------------------------

def blender_material(name, rgba):
    import bpy
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True; n = next(q for q in m.node_tree.nodes if q.type == 'BSDF_PRINCIPLED')
    n.inputs['Base Color'].default_value = (*rgba[:3], 1); n.inputs['Roughness'].default_value = rgba[3]; n.inputs['Metallic'].default_value = rgba[4]
    m.diffuse_color = (*rgba[:3], 1)
    return m


def build_objects(s, v, els, mats, world=None, col=None):
    """Join the elements of one family into one object (like the production generator), text as converted curves."""
    import bpy
    from mathutils import Matrix, Vector
    by = {}
    for q in els:
        by.setdefault(q['family'], []).append(q)
    made = []
    for fam, qs in by.items():
        vs, fs = [], []
        for q in qs:
            if 'text' in q:
                continue
            o = len(vs); vs += q['vs']; fs += [tuple(i+o for i in f) for f in q['fs']]
        if vs:
            me = bpy.data.meshes.new(f'ART_P4_{v}_{fam}'); me.from_pydata(vs, [], fs); me.update(); me.materials.append(mats[fam])
            ob = bpy.data.objects.new(me.name, me); col.objects.link(ob); made.append(ob)
            if world is not None:
                ob.matrix_world = world
            ob['study'] = 'p4_s1_grammar'; ob['geometry_status'] = 'PROTOTYPE'; ob['variant'] = v
        for q in (x for x in qs if 'text' in x):
            cu = bpy.data.curves.new(q['name'], 'FONT'); cu.body = q['text']; cu.size = q['height']*1.35; cu.align_x = 'CENTER'; cu.align_y = 'CENTER'
            cu.materials.append(mats[fam])
            ob = bpy.data.objects.new(q['name'], cu); col.objects.link(ob); made.append(ob)
            rx, up = Vector(q['right']).normalized(), Vector(q['up']).normalized(); nz = rx.cross(up).normalized()
            m = Matrix((rx, up, nz)).transposed().to_4x4(); m.translation = Vector(q['centre'])
            ob.matrix_world = (world @ m) if world is not None else m
            ob['study'] = 'p4_s1_grammar'; ob['variant'] = v
    return made


def figure(s, mat, at, axis, facing, col):
    """Non-diegetic 1.8 m scale reference (capsule + head), standing along `axis`; not an EVA position (flight EVA HOLD)."""
    import bpy
    from mathutils import Vector, Matrix
    h = s['prototype']['human_height_m']; parts = []
    me = bpy.data.meshes.new('ART_P4_Figure')
    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=.19, radius2=.17, depth=h*.80, matrix=Matrix.Translation((0, 0, h*.40)))
    bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=8, radius=.13, matrix=Matrix.Translation((0, 0, h-.13)))
    bm.to_mesh(me); bm.free(); me.materials.append(mat)
    ob = bpy.data.objects.new('ART_P4_Figure', me); col.objects.link(ob); ob['kind'] = 'scale_reference_study'
    z = Vector(axis).normalized(); x = Vector(facing).cross(z).normalized(); y = z.cross(x)
    m = Matrix((x, y, z)).transposed().to_4x4(); m.translation = Vector(at); ob.matrix_world = m
    return ob


def rotor_world(ring):
    """World matrix of a ring's rotor at the posed frame (ring-local frame of habitat_ring)."""
    import bpy
    rot = bpy.data.objects.get(f'Rotor_{ring}')
    return rot.matrix_world.copy()


def frames(s):
    """Matched cameras: (focus, direction-or-eye, corners or None, lens). Shared stations, never fixed numbers."""
    from mathutils import Vector
    import drive_manifold
    st = fsh.stations(s); cr = fsh.crown(s); R = st['shield_r']; b = cr['bays'][0]['azimuth']
    u = Vector((0, math.cos(b), math.sin(b))); t = Vector((0, -math.sin(b), math.cos(b)))
    box = lambda x0, x1, r: [Vector(p) for p in itertools.product((x0, x1), (-r, r), (-r, r))]
    dm = drive_manifold.stations(s); xa, xb = hr.centers(s)
    out = {}
    out['ship_34'] = (Vector(((dm['exit']+st['lance_tip'])/2, 0, 0)), Vector((-.55, 0, 0))+u*.75-t*.55, box(dm['exit']-6, st['lance_tip'], R), 40.0)
    out['ship_side'] = (Vector(((dm['exit']+st['lance_tip'])/2, 0, 0)), Vector((-.08, 0, 0))+u*1.0-t*.10, box(dm['exit']-6, st['lance_tip'], R), 50.0)
    # Between two blades on the sun side (the bisector nearest the sun azimuth, -20 deg), from aft and outboard: both ring flanks against
    # the Brow's aft face, with no blade in front of them.
    ph = s['prototype']['radiator_phase_deg']
    beta = min((math.radians(ph+60+120*k) for k in range(3)), key=lambda a_: abs(math.remainder(a_-math.radians(-20.0), math.tau)))
    out['rings_34'] = (Vector((xa+3, 18*math.cos(beta), 18*math.sin(beta))), Vector((xa-30, 72*math.cos(beta), 72*math.sin(beta))), None, 24.0)
    tgt = Vector((fsh.skin_aft_at(s, 22.0), 0, 0))+u*22.0+t*1.5
    out['brow_sector'] = (tgt, tgt+Vector((-17.0, 0, 0))+u*9.0-t*9.0, None, 24.0)
    tgt = Vector((cr['x0']-.3, 0, 0))+u*43.6
    out['crown_bay'] = (tgt, tgt+Vector((-13.0, 0, 0))+u*9.0-t*7.0, None, 30.0)
    tgt = Vector((cr['x0']-.4, 0, 0))+u*42.7+t*2.2
    out['human_crown'] = (tgt, tgt+Vector((-6.5, 0, 0))+u*2.6-t*4.2, None, 28.0)
    return out


def ring_cameras(s, tc=0.0):
    """Cameras on ring A's pressure segment at local angle tc (deg), in ring-local coordinates mapped through the rotor at render time:
    (eye, target, lens). +u = aft here; run() flips it with ring_aft_sign()."""
    from mathutils import Vector
    g = ring_frame(s); H = g['H']
    loc = lambda u, r, deg: Vector((u, r*math.cos(math.radians(tc+deg)), r*math.sin(math.radians(tc+deg))))
    return {'ring_segment': (loc(21, 44, 9), loc(H, 27.4, 0), 40.0),
            'human_ring': (loc(6.5, 31.5, 10), loc(H, 26.6, 3.5), 30.0)}


def clear_sector(s, w):
    """Local angle (deg) of the ring A pressure segment whose posed world azimuth lies farthest from the three blades, so the probe
    views look between them (every segment carries the same module)."""
    from mathutils import Vector
    blades = [math.radians(s['prototype']['radiator_phase_deg']+120*k) for k in range(3)]
    best = None
    for q in (x for x in hr.sectors(s) if x['ring'] == 1):
        p = w.to_3x3() @ Vector((0, math.cos(q['angle']), math.sin(q['angle']))); az = math.atan2(p.z, p.y)
        d = min(abs(math.remainder(az-b, math.tau)) for b in blades)
        if best is None or d > best[0]:
            best = (d, math.degrees(q['angle']))
    return best[1]


def ring_aft_sign():
    """+1 if ring-local +u points aft (-X world) for ring A, else -1 (the cameras look at the aft flank)."""
    w = rotor_world(1)
    return 1 if (w.to_3x3() @ __import__('mathutils').Vector((1, 0, 0))).x < 0 else -1


def run(out, variants, views, size, samples):
    import bpy
    from mathutils import Vector, Matrix
    from common import pose_configuration
    import hero_preview as hp
    s = load(ROOT)[0]
    out.mkdir(parents=True, exist_ok=True)
    report = dict(summary=summary(s), views={}, materials={})
    (out/'p4_s1_summary.json').write_text(json.dumps(report['summary'], indent=1))
    for v in variants:
        for state in (['COAST', 'IGNITION'] if v in ('V0', 'VC', 'VCP') else ['COAST']):
            bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/wayfarer'/(s['vehicle']['asset']+'.blend')))
            scene = bpy.context.scene
            pose_configuration(s, 'COAST' if state == 'COAST' else 'HIGH_POWER'); scene.frame_set(scene.frame_current)
            keep = {}
            for m in bpy.data.materials:
                if m.name.startswith('WF_MAT_Prod_') and m.use_nodes:
                    n = next(q for q in m.node_tree.nodes if q.type == 'BSDF_PRINCIPLED')
                    keep[m] = {k: (tuple(n.inputs[k].default_value) if k == 'Base Color' else n.inputs[k].default_value) for k in ('Base Color', 'Roughness', 'Metallic')}
            hp.dress(s, functional=True, emit=(state == 'IGNITION')); x = s['look']['exterior']
            for m, vals in keep.items():
                n = next(q for q in m.node_tree.nodes if q.type == 'BSDF_PRINCIPLED')
                for k, val in vals.items():
                    n.inputs[k].default_value = val
            fam = FAMILIES.get(v, {})
            mats = {k: blender_material(f'ART_P4_{v}_{k}', val) for k, val in fam.items()}
            inventory = {}
            for m in bpy.data.materials:                        # ship-wide families (base colour only; emission left as the look set it)
                if not m.name.startswith('WF_MAT_') or m.name.startswith('WF_MAT_Prod_') or not m.use_nodes:
                    continue
                base = m.name[7:].split('.')[0]; f_ = ship_family(base); inventory[base] = f_
                if f_ in fam:
                    n = next((q for q in m.node_tree.nodes if q.type == 'BSDF_PRINCIPLED'), None)
                    if n is not None:
                        val = fam[f_]; n.inputs['Base Color'].default_value = (*val[:3], 1); n.inputs['Roughness'].default_value = val[3]
                        n.inputs['Metallic'].default_value = val[4]
            report['materials'][v] = inventory
            col = bpy.data.collections.new(f'ART_P4_{v}'); scene.collection.children.link(col)
            fe = forward_elements(s, v)
            if fe:
                for o in bpy.data.objects:                      # the variant replaces the M8.1 layer (V0/V0T keep it)
                    if o.get('kind') == 'production_detail' and str(o.get('m7_assembly', '')).startswith('M8.'):
                        o.hide_render = True
                build_objects(s, v, fe, mats, None, col)
            for ring, els in ring_elements(s, v).items():
                build_objects(s, v, els, mats, rotor_world(ring), col)
            # scale references (non-diegetic): one at the Crown bay 1 hatch, one at ring A segment 0's aft flank
            red = blender_material('ART_P4_Figure', [1.0, .45, .10, .6, 0])
            cr = fsh.crown(s); b = cr['bays'][0]['azimuth']; uu = Vector((0, math.cos(b), math.sin(b))); tt = Vector((0, -math.sin(b), math.cos(b)))
            figure(s, red, Vector((cr['x0']-.35, 0, 0))+uu*41.9+tt*1.9, uu, Vector((-1, 0, 0)), col)
            w = rotor_world(1); sg = ring_aft_sign(); g = ring_frame(s); tc = clear_sector(s, w); ft = math.radians(tc+4)
            figure(s, red, w @ Vector((sg*(g['H']+.55), 26.4*math.cos(ft), 26.4*math.sin(ft))),
                   (w.to_3x3() @ Vector((0, math.cos(ft), math.sin(ft)))), (w.to_3x3() @ Vector((sg, 0, 0))), col)
            # render setup (m8_exterior / hero look: one physical sun from the aft hemisphere, no fill)
            scene.render.engine = 'CYCLES'; scene.cycles.samples = samples; scene.cycles.use_denoising = True; scene.cycles.seed = 0
            scene.cycles.device = 'CPU'
            scene.render.resolution_x = size; scene.render.resolution_y = round(size*9/16); scene.render.image_settings.file_format = 'PNG'
            aspect = 16/9
            scene.world.use_nodes = True; bg = next(n for n in scene.world.node_tree.nodes if n.type == 'BACKGROUND')
            bg.inputs['Color'].default_value = (0, 0, 0, 1); bg.inputs['Strength'].default_value = 0.0
            from m8_exterior import sun_vector
            sv = sun_vector(40.0, -20.0)
            sun = bpy.data.lights.new('P4_Sun', 'SUN'); sun.energy = x['sun_strength']; sun.angle = math.radians(x['sun_angular_deg'])
            so = bpy.data.objects.new(sun.name, sun); scene.collection.objects.link(so); so.rotation_euler = (-sv).to_track_quat('-Z', 'Y').to_euler()
            scene.view_settings.view_transform = 'AgX'; scene.view_settings.look = 'None'
            cd = bpy.data.cameras.new('P4_Camera'); cam = bpy.data.objects.new(cd.name, cd); scene.collection.objects.link(cam); scene.camera = cam
            fr = frames(s); rc = ring_cameras(s, tc)
            todo = [vw for vw in views if (vw in fr or vw in rc) and vw != 'function_map']+(['function_map'] if 'function_map' in views else [])
            if state == 'IGNITION':
                todo = [vw for vw in ('ship_34', 'rings_34') if vw in views]
                exposures = [('matched', 0.0)]
            elif v in ('V0', 'VC', 'VCP'):
                exposures = [('editorial', 2.0)]
            else:
                exposures = [('editorial', 2.0)]
            for vw in todo:
                if vw == 'function_map':
                    function_map(s, scene, cam, cd, v, out, size, report)
                    continue
                for ex_name, ev in exposures + ([('matched', 0.0)] if state == 'COAST' and v in ('V0', 'VC', 'VCP') and vw in ('ship_34', 'rings_34') else []):
                    scene.view_settings.exposure = x['exposure_ev']+ev
                    if vw in fr:
                        a, b2, corners, lens = fr[vw]
                        quat, dist = hp.place(cam, a, b2, corners, lens, aspect)
                        cd.clip_start = .1 if corners is None else .5
                    else:
                        eye, tgt, lens = rc[vw]
                        sgn = ring_aft_sign(); eye = Vector((eye.x*sgn, eye.y, eye.z)); tgt = Vector((tgt.x*sgn, tgt.y, tgt.z))
                        e, tg = w @ eye, w @ tgt
                        quat, dist = hp.place(cam, tg, e, None, lens, aspect); cd.clip_start = .1
                    label = (f"{'COAST' if state == 'COAST' else 'FIRST IGNITION (HIGH_POWER, 1800 K emission unchanged)'} — "
                             + (f"+{ev:g} EV editorial exposure, not comparable brightness" if ev else 'matched exposure (comparison truth, 15!A222)'))
                    lines = [f'P4 S1 {TITLE[v]} / {vw.upper()} / {label}',
                             'NONCANON study (ART_P4, in memory): Crown bay + Brow aft sector + ring segment modules repeated on all bays/segments for the whole-ship read only',
                             'depiction-only PROTOTYPE materials (S&E 15 OWN-P4-LOCKED); no geometry, mechanism, protection or coating claim; orange figure = 1.8 m scale reference, not an EVA position',
                             'physical light: one sun 40 deg from aft, azimuth -20 deg (presentation choice; pointing OPEN); no fill | owner S1 review pending']
                    labels = hp.caption(scene, cam, quat, dist, lines, aspect)
                    tagname = f'{v}_{vw}' + ('' if state == 'COAST' and ex_name == 'editorial' else f'_{state.lower()}_{ex_name}')
                    path = out/f'{tagname}.png'; scene.render.filepath = str(path)
                    bpy.ops.render.render(write_still=True)
                    for o in labels:
                        bpy.data.objects.remove(o, do_unlink=True)
                    report['views'][tagname] = dict(variant=v, view=vw, state=state, exposure=ex_name, ev=scene.view_settings.exposure,
                                                    camera=dict(location=list(cam.location), lens=cd.lens))
                    print('WF_P4_S1', tagname, flush=True)
                    (out/'p4_s1.json').write_text(json.dumps(report, indent=1))
    return report


DIAGRAM = dict(shell=(.92, .92, .90), structure=(.20, .42, .72), machinery=(.03, .03, .035), service=(.85, .60, .15), amber=(.95, .45, .05),
               joint=(.55, .08, .08), mark=(.03, .03, .035), mark_light=(.92, .92, .90), blue=(.05, .25, .85), root=(.92, .92, .90))


def function_map(s, scene, cam, cd, v, out, size, report):
    """Functional cutaway as a function map (the m8_exterior / m7_section x-ray convention): the engineering geometry in neutral clay, the
    study layer (or, for V0/V0T, the M8.1 layer) coloured by role: shell white, exposed structure blue, machinery black, service ochre,
    occupancy amber, joints red, wayfinding blue. Bay 1 from aft and outboard with a labelled analysis headlamp at the camera. Rendered last
    (it recolours every material in memory)."""
    import bpy
    from mathutils import Vector
    for m in bpy.data.materials:
        if not m.use_nodes or m.name == 'ART_P4_Figure' or m.name.startswith('Hero_Caption'):
            continue
        n = next((q for q in m.node_tree.nodes if q.type == 'BSDF_PRINCIPLED'), None)
        if n is None:
            continue
        fam = (m.name[len(f'ART_P4_{v}_'):] if m.name.startswith(f'ART_P4_{v}_') else
               M8_FAMILY.get(m.name[len('WF_MAT_Prod_'):].split('.')[0]) if m.name.startswith('WF_MAT_Prod_ext_') else None)
        rgb = DIAGRAM.get(fam, (.26, .27, .29))
        n.inputs['Base Color'].default_value = (*rgb, 1); n.inputs['Roughness'].default_value = .6; n.inputs['Metallic'].default_value = 0.0
        n.inputs['Emission Strength'].default_value = 0.0
    cr = fsh.crown(s); b = cr['bays'][0]['azimuth']; u = Vector((0, math.cos(b), math.sin(b))); tv = Vector((0, -math.sin(b), math.cos(b)))
    tgt = Vector((fsh.skin_aft_at(s, 34.0)-1.5, 0, 0))+u*35.0; eye = tgt+Vector((-26.0, 0, 0))+u*14.0-tv*15.0
    import hero_preview as hp
    quat, dist = hp.place(cam, tgt, eye, None, 26.0, 16/9); cd.clip_start = .1; scene.view_settings.exposure = s['look']['exterior']['exposure_ev']+1.0
    li = bpy.data.lights.new('P4_Headlamp', 'SUN'); li.energy = 1.5; li.angle = math.radians(10)
    lo = bpy.data.objects.new(li.name, li); scene.collection.objects.link(lo); lo.rotation_euler = quat.to_euler()
    path = out/f'{v}_function_map.png'; scene.render.filepath = str(path); bpy.ops.render.render(write_still=True)
    report['views'][f'{v}_function_map'] = dict(variant=v, view='function_map', state='COAST', exposure='editorial +2 EV, analysis headlamp',
                                                ev=scene.view_settings.exposure, camera=dict(location=list(cam.location), lens=cd.lens))
    print('WF_P4_S1', f'{v}_function_map', flush=True)


VIEWS = ('ship_34', 'ship_side', 'rings_34', 'brow_sector', 'crown_bay', 'human_crown', 'function_map', 'ring_segment', 'human_ring')

if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    ap = argparse.ArgumentParser(); ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--variants', nargs='+', default=list(VARIANTS), choices=VARIANTS); ap.add_argument('--views', nargs='+', default=list(VIEWS))
    ap.add_argument('--size', type=int, default=1280); ap.add_argument('--samples', type=int, default=24); ap.add_argument('--screen-only', action='store_true')
    a = ap.parse_args(argv)
    o = a.out if a.out.is_absolute() else ROOT/a.out
    if a.screen_only:
        o.mkdir(parents=True, exist_ok=True); r = summary(load(ROOT)[0]); (o/'p4_s1_summary.json').write_text(json.dumps(r, indent=1)); print(json.dumps(r, indent=1))
    else:
        run(o, a.variants, a.views, a.size, a.samples)
