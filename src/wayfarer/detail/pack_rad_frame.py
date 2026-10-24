"""Detail pack rad_frame (docs/MODULES.md): RAD.FRAME, production fittings on the radiator blade's truss frames and aft edge (WF-THERMAL).

Built in the blade component's frame (components/revision.py radiator(): u along the blade from its mid-length, v across it from the root
edge, z normal to the sheet) into WF_DETAIL_RAD_FRAME.blend, which WF_RADIATOR links at its origin, so every blade carries the same mesh.
The screen keeps every footprint off the emitting cells (thermal_geometry.cell_span over the full ribbon width): the clamps and gussets sit
inside the non-emitting bay joints or beyond the blade's ends. Owned with data/detail/rad_frame.toml.
"""
import production_detail as pd

PACK = 'rad_frame'
ASM = 'RAD.FRAME'
X, Y, Z = (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)


def blade(s):
    """Blade length, ribbon width and count, gap, truss half depth and the frame stations (u) of the component."""
    from spec import derived
    d = derived(s); g = s['radiators']['geometry']; L = d['blade_length_m']
    return dict(L=L, w=d['ribbon_width_m'], n=d['ribbons'], gap=d['gap_m'], half=g['truss_depth_m']/2,
                stations=[-L/2+L*j/g['major_bays'] for j in range(g['major_bays']+1)])


def outward(u, size, b):
    """Centre of a part of length size at station u: on the station inside a bay joint, pushed outward at the blade's two ends."""
    if u <= -b['L']/2+1e-9:
        return u-size/2-1e-4
    if u >= b['L']/2-1e-9:
        return u+size/2+1e-4
    return u


@pd.builder(ASM)
def frame_elements(s):
    q = pd.params(s, PACK); b = blade(s); out = []; bev = q['bevel_m']
    for r in range(b['n']):
        v0 = r*(b['w']+b['gap']); v1 = v0+b['w']
        for j, u in enumerate(b['stations']):
            for side, z in (('T', b['half']), ('B', -b['half'])):
                uc = outward(u, q['clamp_u_m'], b)
                for k in range(1, q['clamps_per_frame']+1):
                    v = v0+b['w']*k/(q['clamps_per_frame']+1)
                    vs, fs = pd.box((uc, v, z), (X, Y, Z), (q['clamp_u_m'], q['clamp_v_m'], q['clamp_z_m']))
                    out.append(pd.element(ASM, 'Clamps', f'RAD_R{r}_S{j:02}_{side}_C{k}', 'xf_machinery', 'ENGINEERING_FLEXIBLE',
                                          'band clamp on the transverse frame tube', vs, fs, bevel=bev))
                ug = outward(u, q['gusset_u_m'], b)
                for edge, v in (('R', v0+q['gusset_v_m']/2), ('O', v1-q['gusset_v_m']/2)):
                    zc = z-q['gusset_z_m']/2 if z > 0 else z+q['gusset_z_m']/2
                    vs, fs = pd.box((ug, v, zc), (X, Y, Z), (q['gusset_u_m'], q['gusset_v_m'], q['gusset_z_m']))
                    out.append(pd.element(ASM, 'Gussets', f'RAD_R{r}_S{j:02}_{side}_{edge}', 'xf_structure', 'ENGINEERING_FLEXIBLE',
                                          'gusset plate at the truss node (frame, edge chord and depth post)', vs, fs, bevel=bev))
        u_edge = -b['L']/2-q['edge_gap_m']-q['edge_u_m']/2
        vs, fs = pd.box((u_edge, (v0+v1)/2, 0.0), (X, Y, Z), (q['edge_u_m'], b['w']-2*q['edge_inset_m'], q['edge_z_m']))
        out.append(pd.element(ASM, 'EdgeGuard', f'RAD_R{r}_Aft_Edge', 'xf_structure', 'ENGINEERING_FLEXIBLE', 'aft edge guard strip', vs, fs, bevel=bev))
    return out


def frame_check(s, els):
    """Every element's (u, v) footprint is clear of every emitting cell and its z stays within the truss depth (plus the clamp band)."""
    import thermal_geometry as tg
    b = blade(s); d = tg.blade_of(s); nx = s['prototype']['radiator_longitudinal_cells']
    cells = [tg.cell_span(s, d, j) for j in range(nx)]; fails = []
    for q in els:
        us = [p[0] for p in q['vs']]; vs_ = [p[1] for p in q['vs']]; zs = [p[2] for p in q['vs']]
        for r in range(b['n']):
            v0 = r*(b['w']+b['gap']); v1 = v0+b['w']
            if min(vs_) < v1-1e-9 and max(vs_) > v0+1e-9:
                hit = [j for j, (u0, u1) in enumerate(cells) if min(us) < u1-1e-9 and max(us) > u0+1e-9]
                if hit:
                    fails.append(f"{q['name']}: over emitting cell column(s) {hit[:3]} of ribbon {r}"); break
        if max(abs(z) for z in zs) > b['half']+pd.params(s, PACK)['clamp_z_m']/2+1e-9:
            fails.append(f"{q['name']}: outside the truss depth")
    return fails


pd.CHECKS[ASM] = frame_check
