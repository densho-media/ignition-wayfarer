"""B01 support (owner 2026-10-17, S&E 15!A200 OWN-SCI, 98!A114): measure the model's tank-bay volumes and centroids (feedback only).

The owner releases no wet mass, reaction mass or fusion fuel; only source-tagged parametric envelopes (default UNKNOWN) and measurements of
the model's tank bays are allowed. This study measures, in the saved COAST vehicle, the free interior between the structural spine and the
nearest stationary hardware inside the hull body (X -101..82 m, aft thrust ring to ring A's vestibule), and what three tank patterns would
hold there. Nothing is saved, sized or released: no tank, inventory, mass, ullage, insulation, wall or support is chosen.

Method: every stationary object of the evaluated scene (instances included) is sampled along its edges (<= SAMPLE_M) into axial bins of BIN_M;
per bin the spine's outer radius is the inner limit and the smallest radius of any other hardware the outer limit, each with the model's
mechanical clearance. Skipped: the hull skin (the outer limit is the hardware inside it), display / field / plasma / beam envelopes, scale
references, and the four schematic Tank_Volume cylinders (the subject; their own envelope is reported separately). Rotating parts lie
outside the body forward of X 81 m and are not in range. A bay is a run of bins whose free annulus is at least MIN_ANNULUS_M deep.

Patterns per bay (PROTOTYPE geometry, the owner's tank architecture is OPEN): ANNULAR (the gross envelope volume, an upper bound),
FOUR (four cylinders around the spine as the built schematic tanks) and SIX (six), each at the bay's narrowest section (constant radius).

    /snap/bin/blender -b assets/wayfarer/WF_WAYFARER_001.blend --python src/wayfarer/studies/tank_bay_survey.py -- --out runs/<stamp>-tank-bays
    -> <out>/bays.json, <out>/elevation.svg; references/TANK_BAY_SURVEY_2026-10-17.md and p1_tank_bays.json
"""
from pathlib import Path
import argparse
import json
import math
import sys
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer')]

X0, X1 = -101.0, 82.0                 # thrust ring forward face .. ring A vestibule (hull body); bays start forward of the engineering envelope
BIN_M = 0.25
SAMPLE_M = 0.20
MIN_ANNULUS_M = 1.0                   # PROTOTYPE: a bay narrower than this is not counted
SKIP_KINDS = {'plasma', 'optical_beam', 'magnetic_field', 'hull_envelope', 'scale_reference', 'entry_camera'}
SKIP_PREFIX = ('Hull_', 'Body_Envelope_Reference', 'MagneticNozzle_FieldEnvelope', 'Human_', 'Magnetic_Flow_Domain', 'PLASMA_', 'OPTICAL_BEAM',
               'Tank_Volume')
SPINE = 'Structural_Spine'
LH2_KG_M3 = 70.85                     # REFERENCE PHYSICS: saturated liquid parahydrogen at its normal boiling point (20.3 K), scale only
OUT_MD = ROOT/'references/TANK_BAY_SURVEY_2026-10-17.md'
OUT_JSON = ROOT/'references/p1_tank_bays.json'


def sample(scene_objects):
    """Per bin: spine outer radius, least other-hardware radius and the object that sets it."""
    import bpy
    n = int(round((X1-X0)/BIN_M)); spine = [0.0]*n; lim = [math.inf]*n; who = ['']*n
    dg = bpy.context.evaluated_depsgraph_get()
    for inst in dg.object_instances:
        ob = inst.object; name = ob.original.name if ob.original else ob.name
        if ob.type not in {'MESH', 'CURVE'} or name.startswith(SKIP_PREFIX) or ob.original.get('kind', '') in SKIP_KINDS:
            continue
        m = inst.matrix_world
        try:
            me = ob.to_mesh()
        except RuntimeError:
            continue
        vs = [m @ v.co for v in me.vertices]
        segs = [(vs[e.vertices[0]], vs[e.vertices[1]]) for e in me.edges] or [(v, v) for v in vs]
        ob.to_mesh_clear()
        for a, b in segs:
            k = max(1, int((a-b).length/SAMPLE_M))
            for i in range(k+1):
                p = a.lerp(b, i/k); j = int((p.x-X0)/BIN_M)
                if 0 <= j < n:
                    r = math.hypot(p.y, p.z)
                    if name == SPINE:
                        spine[j] = max(spine[j], r)
                    elif r < lim[j]:
                        lim[j] = r; who[j] = name
    return spine, lim, who


def start_x(s):
    """Forward face of the engineering envelope + clearance: aft of it are the drive, the core, the shadow shield (tanks stay forward of the
    shield, no direct core-to-tank line, 15!A69) and the reserved engineering bay (HR-001 candidate A)."""
    import layout
    p = s['prototype']
    return layout.at(s, p['engineering_center_x'])+p['engineering_length_m']/2+p['mechanical_clearance_m']


def bays(s, spine, lim, who):
    clr = s['prototype']['mechanical_clearance_m']; out = []; cur = None; xs = start_x(s)
    for j in range(len(spine)):
        x = X0+(j+0.5)*BIN_M; ri = spine[j]+clr; ro = lim[j]-clr
        if x-BIN_M/2 >= xs-1e-9 and ro-ri >= MIN_ANNULUS_M:
            if cur is None:
                cur = dict(x0=X0+j*BIN_M, bins=[])
            cur['bins'].append((x, ri, ro, who[j]))
        elif cur is not None:
            out.append(cur); cur = None
    if cur is not None:
        out.append(cur)
    rows = []
    for b in out:
        bins = b['bins']; L = len(bins)*BIN_M
        if L < 2.0:
            continue
        vol = sum(math.pi*(ro*ro-ri*ri)*BIN_M for _, ri, ro, _ in bins)
        cx = sum(x*math.pi*(ro*ro-ri*ri)*BIN_M for x, ri, ro, _ in bins)/vol
        ri = max(q[1] for q in bins); ro = min(q[2] for q in bins)
        lim_obj = min(bins, key=lambda q: q[2])[3]
        pats = {}
        for name, k in (('ANNULAR', 0), ('FOUR', 4), ('SIX', 6)):
            if k == 0:
                v = math.pi*(ro*ro-ri*ri)*L; rt = None
            else:
                d = (ri+ro)/2; rt = min((ro-ri)/2, d*math.sin(math.pi/k)); v = k*math.pi*rt*rt*L
            pats[name] = dict(tank_radius_m=None if rt is None else round(rt, 3), volume_m3=round(v, 1), lh2_t_at_nbp=round(v*LH2_KG_M3/1000, 1))
        rows.append(dict(x0_m=round(b['x0'], 2), x1_m=round(b['x0']+L, 2), length_m=round(L, 2), centroid_x_m=round(cx, 2),
                         envelope_m3=round(vol, 1), envelope_lh2_t_at_nbp=round(vol*LH2_KG_M3/1000, 1),
                         narrowest=dict(r_in_m=round(ri, 3), r_out_m=round(ro, 3), limited_by=lim_obj), patterns=pats))
    return rows


def built_tanks(s):
    p = s['prototype']; import layout
    c = layout.at(s, p['tank_center_x']); v = 4*math.pi*p['tank_radius_m']**2*p['tank_length_m']
    return dict(x0_m=round(c-p['tank_length_m']/2, 2), x1_m=round(c+p['tank_length_m']/2, 2), count=4, radius_m=p['tank_radius_m'],
                length_m=p['tank_length_m'], volume_m3=round(v, 1), centroid_x_m=round(c, 2), lh2_t_at_nbp=round(v*LH2_KG_M3/1000, 1),
                status=s['physics']['fuel_tanks']['dimensions_status'])


def svg(spine, lim, rows, tanks, clr):
    W, H, sx, sr, ox, oy = 1500, 330, 7.8, 42.0, 60, 290
    X = lambda x: ox+(x-X0)*sx; R = lambda r: oy-r*sr
    pts = lambda f: ' '.join(f'{X(X0+(j+0.5)*BIN_M):.1f},{R(min(f(j), 6.4)):.1f}' for j in range(len(spine)))
    g = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="sans-serif" font-size="11">',
         f'<rect width="{W}" height="{H}" fill="#fafaf8"/>']
    for b in rows:
        g.append(f'<rect x="{X(b["x0_m"]):.1f}" y="{R(b["narrowest"]["r_out_m"]):.1f}" width="{(b["x1_m"]-b["x0_m"])*sx:.1f}" '
                 f'height="{(b["narrowest"]["r_out_m"]-b["narrowest"]["r_in_m"])*sr:.1f}" fill="#9fe1cb" opacity="0.55"/>')
        g.append(f'<text x="{X((b["x0_m"]+b["x1_m"])/2):.1f}" y="{R(b["narrowest"]["r_out_m"])-6:.1f}" text-anchor="middle" fill="#085041">'
                 f'{b["envelope_m3"]:.0f} m³</text>')
    g.append(f'<polyline points="{pts(lambda j: lim[j]-clr)}" fill="none" stroke="#a32d2d" stroke-width="1.2"/>')
    g.append(f'<polyline points="{pts(lambda j: spine[j]+clr)}" fill="none" stroke="#444441" stroke-width="1.2"/>')
    g.append(f'<rect x="{X(tanks["x0_m"]):.1f}" y="{R(1.4*2+2.6*math.sqrt(2)-1.4):.1f}" width="{tanks["length_m"]*sx:.1f}" height="{2.8*sr:.1f}" '
             'fill="none" stroke="#185fa5" stroke-dasharray="4 3"/>')
    for x in range(-100, 81, 20):
        g.append(f'<line x1="{X(x):.1f}" y1="{oy}" x2="{X(x):.1f}" y2="{oy+5}" stroke="#888"/><text x="{X(x):.1f}" y="{oy+17}" text-anchor="middle" fill="#555">X {x}</text>')
    for r in range(0, 7):
        g.append(f'<text x="{ox-8}" y="{R(r)+4:.1f}" text-anchor="end" fill="#555">r {r}</text>')
    g.append(f'<text x="{ox}" y="16" fill="#222">Tank bays: free interior between the spine (grey) and the nearest stationary hardware (red), '
             f'{clr} m clearance; green = bay at its narrowest section; dashed blue = the four built schematic tanks (one shown). MEASUREMENT, not a release.</text>')
    g.append('</svg>')
    return '\n'.join(g)


def md(d):
    t = d['built_tanks']
    L = ['# Tank-bay survey (B01 measurement, owner 2026-10-17 S&E 15!A200)', '',
         'MEASUREMENT / DIAGNOSTIC feedback only. No wet mass, reaction mass, fusion fuel, tank architecture, ullage, insulation, wall or support',
         'is released or chosen here; flight playback stays SIMULATION_ONLY. Code `src/wayfarer/studies/tank_bay_survey.py`, data '
         '`references/p1_tank_bays.json`, elevation `' + d['svg'] + '`.', '',
         d['method'], '',
         f"Built schematic tanks (`physics.fuel_tanks`, dimensions {t['status']}): {t['count']} x r {t['radius_m']} m x {t['length_m']} m at X "
         f"{t['x0_m']}..{t['x1_m']} m = **{t['volume_m3']} m³**, centroid X {t['centroid_x_m']} m (≈ {t['lh2_t_at_nbp']} t LH2 at its normal-boiling-point "
         'density, no ullage).', '',
         '| Bay X (m) | Length m | Centroid X m | Envelope m³ (≈ t LH2) | Narrowest r in–out m (limited by) | FOUR r / m³ | SIX r / m³ |',
         '| --- | --- | --- | --- | --- | --- | --- |']
    for b in d['bays']:
        n = b['narrowest']; p = b['patterns']
        L.append(f"| {b['x0_m']}..{b['x1_m']} | {b['length_m']} | {b['centroid_x_m']} | {b['envelope_m3']} ({b['envelope_lh2_t_at_nbp']}) | "
                 f"{n['r_in_m']}–{n['r_out_m']} ({n['limited_by']}) | {p['FOUR']['tank_radius_m']} / {p['FOUR']['volume_m3']} | "
                 f"{p['SIX']['tank_radius_m']} / {p['SIX']['volume_m3']} |")
    tot = d['totals']
    L += ['', f"Total envelope {tot['envelope_m3']} m³ (≈ {tot['envelope_lh2_t_at_nbp']} t LH2), centroid X {tot['centroid_x_m']} m; "
          f"constant-section FOUR {tot['four_m3']} m³, SIX {tot['six_m3']} m³.", '', d['findings']]
    return '\n'.join(L)+'\n'


FINDINGS = """## Findings (Claude, from the tables)

1. **The model already has a large unallocated interior.** Between the battery / pulse bank and ring A's vestibule the hull body holds only
   the spine near the axis; the free annulus runs from the spine to just inside the cage, the drone and crawler rails and the radiator root
   chases. Its gross envelope is the total above, many times the 4 schematic tanks.
2. **What limits it** is the hardware on the cage line (rails, stays, root posts, chases), not the hull skin: the narrowest sections are
   named per bay. A tank pattern at a constant section loses the bulges; FOUR / SIX cylinders keep a service gap between them.
3. **Consequences the owner should weigh** (none decided here): a tank bay over the whole body moves the reaction-mass centroid to about
   the envelope centroid (far forward of the drive), lengthens the cryogenic feed and the stepped shield penetrations, and fills the only
   axial path aft of the crew trunk (no internal crew route aft exists in the model; an aft service corridor is OPEN and would reduce
   every figure). The interior hot-loop route from the drive to the radiator root chases (OPEN, HR-001) would cross it as well.
   Geometric shadowing behind the shield slab is not a dose result (OD-026).
4. **LH2 tonnes are a scale only** (liquid parahydrogen at 20.3 K, no ullage, insulation, wall, structure, boil-off or D / He-3 split)."""


def main():
    import bpy
    from spec import load
    a = argparse.ArgumentParser(); a.add_argument('--out', required=True)
    args = a.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    out = (ROOT/args.out).resolve() if not Path(args.out).is_absolute() else Path(args.out); out.mkdir(parents=True, exist_ok=True)
    s = load(ROOT)[0]
    spine, lim, who = sample(bpy.data.objects)
    rows = bays(s, spine, lim, who); tanks = built_tanks(s); clr = s['prototype']['mechanical_clearance_m']
    vol = sum(b['envelope_m3'] for b in rows)
    d = dict(study='Tank-bay survey (B01 measurement; owner 2026-10-17 S&E 15!A200 OWN-SCI, 98!A114)',
             status='MEASUREMENT / DIAGNOSTIC; no tank, inventory or mass released or chosen',
             method=f'Saved COAST vehicle, every stationary object sampled along its edges (<= {SAMPLE_M} m) into {BIN_M} m axial bins over X {X0}..{X1} m; '
                    f'inner limit = spine outer radius + {clr} m, outer limit = least radius of other hardware - {clr} m (hull skin, envelopes, '
                    f'display objects and the schematic tanks skipped); bays start forward of the engineering envelope (X {start_x(s):.2f} m) and are runs with >= {MIN_ANNULUS_M} m free annulus. Patterns at the bay\'s '
                    'narrowest section: ANNULAR, FOUR / SIX cylinders around the spine (PROTOTYPE geometry).',
             reference_density=dict(lh2_kg_m3=LH2_KG_M3, status='REFERENCE PHYSICS (scale only)'),
             built_tanks=tanks, bays=rows, svg=str((out/'elevation.svg').relative_to(ROOT)),
             totals=dict(envelope_m3=round(vol, 1), envelope_lh2_t_at_nbp=round(vol*LH2_KG_M3/1000, 1),
                         centroid_x_m=round(sum(b['centroid_x_m']*b['envelope_m3'] for b in rows)/vol, 2) if vol else None,
                         four_m3=round(sum(b['patterns']['FOUR']['volume_m3'] for b in rows), 1),
                         six_m3=round(sum(b['patterns']['SIX']['volume_m3'] for b in rows), 1)),
             findings=FINDINGS)
    (out/'bays.json').write_text(json.dumps(d, indent=1)+'\n'); (out/'elevation.svg').write_text(svg(spine, lim, rows, tanks, clr))
    (out/'profile.json').write_text(json.dumps(dict(x0=X0, bin_m=BIN_M, spine_r=spine, hardware_r=[None if math.isinf(v) else v for v in lim], limited_by=who)))
    OUT_JSON.write_text(json.dumps(d, indent=1)+'\n'); OUT_MD.write_text(md(d))
    print('WF_TANK_BAYS', json.dumps(d['totals']))


if __name__ == '__main__':
    main()
