#!/usr/bin/env python3
"""Compact integrated Vertex cluster: engineering evaluation of variants C1-C4 (research, not canon; standard library only).

Owner direction 2026-11-23: keep the compact ship and its aft four-engine cluster; move it aft only locally; document what does not close.
The engine physics reuses lab/studies/vertex-compact-engine/vertex-ron/ron.py (capture current, test-particle pushes, sky and heat ledger, magnet masses, ship model)
and lab/studies/vertex-compact-engine/vertex-ampn (ripple, dust faces) and lab/studies/dust-impacts (environment and damage rules), all read-only.

Variants (all PROTOTYPE choices; the production cluster is the base, data/wayfarer_3d.toml [vertex_engine], [propulsion_cluster]):
  C1  production cluster as drawn: four engines on a 24 m pitch, burn 6 m aft of the shadow shield, round loop cryostats.
  C2  C1 moved 25 m aft on a longer thrust truss, and a 6 m nozzle extension (burn 12 m aft of the shield): local, not remote.
  C3  C2 with edge-on ribbon loops and cluster shadow shields sized to shadow the whole hull from every burn.
  C4  C3 plus the compact braking protection package: shields sized for a 15 m screen zone, three stern screens, engine-face and hub armour,
      service trunks inside the hub shadow.
`python3 lab/studies/vertex-compact-engine/vertex-compact/compact.py [--quick]` writes results/compact.json, results/compact.log and results/compact.md.
"""
import json
import math
import random
import sys
from multiprocessing import Pool
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / 'vertex-ron')); sys.path.insert(0, str(HERE.parent / 'vertex-ampn'))
sys.path.insert(0, str(HERE.parent / 'vertex-hims'))
import ron  # noqa: E402
import dust  # noqa: E402
import hims  # noqa: E402

QUICK = '--quick' in sys.argv
N = 48 if QUICK else 160
P = dust.P
SIGMA = 5.670374e-8
R_SHIP = 45.0
CANT = 2.0                      # [propulsion_cluster] cant_deg
PITCH = 24.0                    # [propulsion_cluster] pitch_radius_m
ENGINE_FWD_M = 19.0             # burn point to the cartridge nose at standoff 6 m (shield 8.2 + cartridge 9.2 + nose 1.2, rounded)
LIH_RHO, W_FACE_KG_M2 = 780.0, 0.05 * 12000.0    # LiH body and a 5 cm W/B4C burn face (shield materials, [vertex_engine.engineering])
SHIP_LIT_LIMIT_W = 1.0e8        # direct burn power the ship may take (the AMPN ship-side neutron target, applied to photons too)
ENGINE_T = 1243.7               # production engine 1.2 drawn-volume estimate (references/evidence/vertex_structure.json)


# Measured from the built approved ship (assets/wayfarer/WF_WAYFARER_001.blend, build of 2026-11-23, geometry diff 0 to the baseline):
# ship X of the parts nearest the cluster (m, +X bow). Radiator blade azimuths 30/150/270 deg, engines 45/135/225/315 deg.
SHIP = dict(x_burn=-153.4, cluster_front=-134.6, thrust_ring=(-136.4, 6.5), blades=dict(x0=-133.25, x1=-133.25 + 182.15, r0=6.5, r1=37.0,
            az=(30.0, 150.0, 270.0), truss_m=3.0), spine=(-136.4, -100.0, 6.5), tank=(-100.0, 90.0, 19.7))


def geometry():
    return dict(D_tank_m=SHIP['tank'][0] - SHIP['x_burn'], source='measured on the built approved ship (2026-11-23)')


def variant(name, D, standoff, cryo, shield_tan=None, mult=1.0):
    base = dict(ron.variants()['A_compact'])
    s0 = standoff
    rings = [(s0 - 1.0, 2.5, -3.19), (s0 - 3.0, 4.2, -5.36), (2.3, 6.4, 7.47), (0.0, 7.6, 8.87), (-5.6, 8.9, 10.39), (-12.4, 9.9, 11.56)]
    t = 2.2
    if shield_tan is None:
        r_aft, r_fwd = 5.4, 4.4
    else:
        r_fwd = shield_tan * (s0 + t); r_aft = shield_tan * s0
    p = dict(base, label=name, D_m=D, rings=rings, plug_x_m=s0, shield_disc=(s0, r_fwd, r_aft, t), cryo_m=cryo)
    return p, dict(r_aft=r_aft, r_fwd=r_fwd, t=t, x0=s0, mult=mult)


def shadow_tan(sh):
    return min(sh['r_aft'] / sh['x0'], sh['r_fwd'] / (sh['x0'] + sh['t']))


def ship_targets(rnd, n):
    """Sample points (x_ship, y, z, normal, weight, part) on the ship surfaces that face the cluster: radiator blades (both faces), spine,
    tank aft dome (as a disc) and the tank flank."""
    bl, sp, tk = SHIP['blades'], SHIP['spine'], SHIP['tank']
    parts = []
    for az in bl['az']:
        a = math.radians(az); u = (math.cos(a), math.sin(a)); nrm = (-math.sin(a), math.cos(a))
        A = (bl['x1'] - bl['x0']) * (bl['r1'] - bl['r0'])
        for sg in (1, -1):
            parts.append(('BLADES', A, lambda a=a, u=u, nrm=nrm, sg=sg: ((bl['x0'] + (bl['x1'] - bl['x0']) * rnd.random()),
                                                                          (bl['r0'] + (bl['r1'] - bl['r0']) * rnd.random()), u, (0.0, sg * nrm[0], sg * nrm[1]))))
    out = []
    tot = sum(p[1] for p in parts)
    for _ in range(n):
        x, r, u, nr = parts[rnd.randrange(len(parts))][2]()
        out.append(((x, r * u[0], r * u[1]), nr, tot / n, 'BLADES'))
    for _ in range(n // 2):
        ph = 2 * math.pi * rnd.random(); x = sp[0] + (sp[1] - sp[0]) * rnd.random()
        out.append(((x, sp[2] * math.cos(ph), sp[2] * math.sin(ph)), (0.0, math.cos(ph), math.sin(ph)), 2 * math.pi * sp[2] * (sp[1] - sp[0]) / (n // 2), 'SPINE'))
    for _ in range(n // 2):
        r = tk[2] * math.sqrt(rnd.random()); ph = 2 * math.pi * rnd.random()
        out.append(((tk[0], r * math.cos(ph), r * math.sin(ph)), (-1.0, 0.0, 0.0), math.pi * tk[2] ** 2 / (n // 2), 'TANK_AFT'))
    for _ in range(n // 2):
        ph = 2 * math.pi * rnd.random(); x = tk[0] + (tk[1] - tk[0]) * rnd.random()
        out.append(((x, tk[2] * math.cos(ph), tk[2] * math.sin(ph)), (0.0, math.cos(ph), math.sin(ph)), 2 * math.pi * tk[2] * (tk[1] - tk[0]) / (n // 2), 'TANK_FLANK'))
    return out


def ship_lit(x_burn, sh, src, n=24000, seed=1):
    """Direct burn power (photons + neutrons) on the ship from the four canted burns, outside each engine's shadow cone (the shield's
    binding rim). No ship self-occlusion (conservative for the blades behind the tank). Returns total W and W per part."""
    rnd = random.Random(seed); tan_c = shadow_tan(sh)
    P_dir = src['P_brems_W'] + src['P_sync_W'] + src['P_n_W']
    burns = []
    for phi in (45, 135, 225, 315):
        a = math.radians(phi); cy, cz = math.cos(a), math.sin(a)
        ax = (math.cos(math.radians(CANT)), -math.sin(math.radians(CANT)) * cy, -math.sin(math.radians(CANT)) * cz)
        burns.append(((x_burn, PITCH * cy, PITCH * cz), ax))
    per = {}; pts = []
    for pt, nrm, w, part in ship_targets(rnd, n):
        q_pt = 0.0
        for b, ax in burns:
            d = [pt[j] - b[j] for j in range(3)]; L = math.sqrt(sum(c * c for c in d)); u = [c / L for c in d]
            cosi = -sum(u[j] * nrm[j] for j in range(3))
            if cosi <= 0:
                continue
            cosa = sum(u[j] * ax[j] for j in range(3))
            if cosa > 0 and math.sqrt(max(0.0, 1 - cosa * cosa)) / cosa <= tan_c:
                continue
            q = P_dir / (4 * math.pi * L * L) * cosi
            per[part] = per.get(part, 0.0) + q * w; q_pt += q
        if q_pt > 0 and len(pts) < 1500:
            pts.append([round(c, 2) for c in pt] + [q_pt])
    ship_lit.points = pts
    return sum(per.values()), per


def exposed_tank_area(n=20000, seed=2):
    """Tank aft dome area not behind an engine envelope (r 11.5 m about each engine axis) or the hub (r 5.6 m): what braking dust reaches."""
    rnd = random.Random(seed); R = SHIP['tank'][2]; hit = 0
    eng = [(PITCH * math.cos(math.radians(a)), PITCH * math.sin(math.radians(a))) for a in (45, 135, 225, 315)]
    for _ in range(n):
        r = R * math.sqrt(rnd.random()); ph = 2 * math.pi * rnd.random(); y, z = r * math.cos(ph), r * math.sin(ph)
        if r < 5.6 or any(math.hypot(y - ey, z - ez) < 11.5 for ey, ez in eng):
            continue
        hit += 1
    return math.pi * R * R * hit / n


def shield_mass_t(sh):
    rf, ra, t = sh['r_fwd'], sh['r_aft'], sh['t']
    vol = math.pi * t / 3 * (rf * rf + rf * ra + ra * ra)
    return (vol * LIH_RHO + math.pi * ra * ra * W_FACE_KG_M2) / 1e3


def ripple(v, cap, src):
    """AMPN ripple rule (eps_c 0.3): eddy heat in a Mo shield on each loop, per engine."""
    E = src['P_charged_W'] / v['f_pulse_Hz']; sig = 1.9e6; f = v['f_pulse_Hz']; delta = 1 / math.sqrt(math.pi * f * 4e-7 * math.pi * sig)
    W = 0.0; dBB = 0.3 * E / (2 * cap['W_J'])
    for c in v['coils']:
        I = abs(c['I']) * cap['k']; Bw = 4e-7 * math.pi * I / (2 * c['depth']); A = 2 * c['depth'] * 2 * math.pi * ron.hoop_r(c)
        H = dBB * Bw / (4e-7 * math.pi); W += H * H / (2 * sig * delta) * A
    return dict(dB_over_B=dBB, eddy_W=W)


def winding_fluence(src, k, rho, armour_m):
    """Neutron fluence on a winding at distance rho behind armour_m of W-B4C (lambda 0.08 m), scattered floor 1e-4 (MPN rule)."""
    flu = src['neutrons_per_s'] / (4 * math.pi * rho * rho) * k['burn_s']
    return flu * (math.exp(-armour_m / 0.08) + 1e-4)


def dust_faces(name, sh, screens, standoff):
    eng = 4
    loops = eng * sum(2 * math.pi * r * 1.2 for r in (6.4, 7.6, 8.9, 9.9))
    shield = eng * math.pi * sh['r_aft'] ** 2
    hub = math.pi * 5.6 ** 2 + eng * 2 * math.pi * 6.8 * 1.4
    bl = SHIP['blades']
    edges = len(bl['az']) * (bl['r1'] - bl['r0']) * bl['truss_m']
    return [dict(name='loop aft faces (in the exhaust)', area=loops, standoff=0.0, screens=1),
            dict(name='shield aft faces (burn view)', area=shield, standoff=0.0, screens=1),
            dict(name='hub and cradles', area=hub, standoff=0.0, screens=1),
            dict(name='radiator blade aft edges', area=edges, standoff=0.0, screens=1),
            dict(name='tank aft dome not behind an engine', area=exposed_tank_area(), standoff=standoff, screens=screens)]


def protect(faces, segs, case):
    rows = []; total = 0.0
    cp = hims.CASES[case]
    for f in faces:
        it = dict(P.lead_item(f['name'], f['area']), leads='ENGINE_FIRST')
        arm = P.armour_thickness(it, segs, case)
        ero = P.K_CRATER[case] * P.energy_fluence(it, segs, case)
        arm_t = (arm['mass_t'] or math.inf) + f['area'] * ero * P.RHO_BUMPER / 1e3 if arm['t_m'] else math.inf
        row = dict(face=f['name'], area_m2=f['area'], standoff_m=f['standoff'], armour_m=arm['t_m'], armour_t=arm_t)
        best = ('armour', arm_t)
        if f['standoff'] > 0:
            n = f['screens']
            gain = (lambda S, E: E / (cp['pass_screen'] ** (n - 1)))
            E_def = gain(f['standoff'], P.bumper_defeat_energy(f['standoff'], case))
            ev = P.events(it, segs, E_def, case)
            sb, sw = hims._bumper_from_E(E_def, case)
            scr_t = f['area'] * (n * (sb + hims.FRAME_KG_M2) + sw) / 1e3
            row.update(screen_events=ev, screen_t=scr_t, screen_closes=ev <= P.TARGET)
            if ev <= P.TARGET and scr_t < best[1]:
                best = (f'{n} screens', scr_t)
            S_need = hims.required(segs, case, gain)
            row['standoff_needed_m'] = S_need
        row.update(kind=best[0], mass_t=best[1])
        total += best[1]; rows.append(row)
    return rows, total


def main():
    k = ron.canon(); g = geometry(); log = []
    def say(s=''):
        print(s, flush=True); log.append(s)
    xb1 = SHIP['x_burn']; xb2 = xb1 - 30.0; xb3 = xb2 - 6.0          # C2: cluster 30 m aft; C3/C4: engines a further 6 m aft on a spool
    D1, D2, D3 = (SHIP['tank'][0] - x for x in (xb1, xb2, xb3))
    say(f'Compact cluster base: burn at x {xb1} m, tank aft dome {D1:.1f} m forward of the burn ({g["source"]}); pitch {PITCH} m, cant {CANT} deg')
    segs = hims.segs()
    def tan_for(D):
        return math.tan(math.atan((PITCH + SHIP['tank'][2]) / D) + math.radians(CANT)) * 1.05
    V = dict(C1=(variant('C1 production cluster as drawn', D1, 6.0, 0.62), xb1),
             C2=(variant('C2 cluster 30 m aft on a longer thrust truss', D2, 6.0, 0.62), xb2),
             C3=(variant('C3 C2 + 6 m spool (burn 12 m aft of the shield), ribbon loops, tank-shadowing shields', D3, 12.0, 0.013,
                         shield_tan=tan_for(D3)), xb3),
             C4=(variant('C4 C3 + braking protection package (15 m screen zone)', D3, 12.0, 0.013, shield_tan=tan_for(D3 - 15.0)), xb3))
    out = dict(meta=dict(base=g, pitch_m=PITCH, cant_deg=CANT, quick=QUICK, n=N), variants={})
    with Pool(4) as pool:
        for key, ((p, sh), xb) in V.items():
            v, src, E, cap = ron.configure(p, k)
            best = None
            for mlt in (1.0, 2.0, 4.0):
                r = ron.evaluate(v, k, src, E, cap, mlt, pool, N)
                if best is None or r['ledger']['B01_W'] < best['ledger']['B01_W']:
                    best = r
            r = best
            led = r['ledger']
            Pl, lit = ship_lit(xb, sh, src)
            rp = ripple(v, r['capture'], src)
            arm = 0.22                                                    # [vertex_engine.geometry] armour_minor_m
            flu = winding_fluence(src, k, 7.6, arm)
            sh_t = shield_mass_t(sh)
            screens, so = (3, 15.0) if key == 'C4' else (1, 0.0)
            dn, dn_t = protect(dust_faces(key, sh, screens, so), segs, 'NOMINAL')
            dj, dj_t = protect(dust_faces(key, sh, screens, so), segs, 'JUSTIFIED')
            base_t = r['engine_t'] if math.isfinite(r['engine_t']) else ENGINE_T     # ron's nose rule has no finite nose at 2-10 m
            eng_t = base_t + (sh_t - shield_mass_t(dict(r_fwd=4.4, r_aft=5.4, t=2.2))) + (30.0 * 1.0 if key in ('C2', 'C3', 'C4') else 0.0)
            piped4 = 4 * led['B01_W']
            sh_nom = ron.ship(k, eng_t + dn_t / 4, piped4, max(0.05, r['particles']['axial_efficiency']), cant_deg=CANT)
            sh_noheat = ron.ship(k, eng_t + dn_t / 4, k['drive_W'], max(0.05, r['particles']['axial_efficiency']), cant_deg=CANT)
            row = dict(label=p['label'], D_m=v['D_m'], standoff_m=sh['x0'], shield=sh, shield_t=sh_t, mult=r['mult'],
                       eta=r['particles']['axial_efficiency'], hit_share=r['particles']['hit_energy_share'],
                       piped_four_W=piped4, piped_over_budget=piped4 / k['drive_W'], self_four_W=4 * led['self_W'],
                       sky=led['sky_total'], ship_lit_W=Pl, ship_lit_over_limit=Pl / SHIP_LIT_LIMIT_W, ship_lit_parts=lit, x_burn=xb, lit_points=ship_lit.points,
                       ripple=rp, winding_fluence=flu, winding_over_limit=flu / 3e22, field_ratio=r['capture']['field_ratio'],
                       engine_t=eng_t, magnet=r['mass_t'], dust_nominal=dn, dust_nominal_t=dn_t, dust_justified=dj, dust_justified_t=dj_t,
                       departure_with_radiators_t=sh_nom['departure_t'], extra_radiator_t=sh_nom['extra_radiator_t'],
                       radiator_area_m2=max(0.0, piped4 - k['drive_W']) / (2 * 0.85 * SIGMA * 1800.0 ** 4),
                       departure_if_heat_closed_t=sh_noheat['departure_t'])
            out['variants'][key] = row
            say(f'\n== {key}: {p["label"]}')
            say(f'  D {v["D_m"]:.0f} m, burn {sh["x0"]:.0f} m aft of the shield, shield r {sh["r_aft"]:.1f}/{sh["r_fwd"]:.1f} m ({sh_t:.0f} t), field x{r["mult"]:.0f}')
            say(f'  axial efficiency {row["eta"]:.3f}, charged hit share {row["hit_share"]:.3f}, hardware sky {row["sky"]:.3f}')
            say(f'  piped heat (4 engines) {piped4 / 1e9:,.0f} GW = {row["piped_over_budget"]:,.0f} x the 10.8 GW drive radiators '
                f'({row["radiator_area_m2"] / 1e6:,.1f} km2 extra at 1,800 K)')
            say(f'  direct burn on the ship {Pl / 1e9:,.1f} GW ({row["ship_lit_over_limit"]:,.0f} x the 0.1 GW limit): ' + ', '.join(f'{kk} {vv / 1e9:,.1f} GW' for kk, vv in sorted(lit.items())))
            say(f'  ripple dB/B {rp["dB_over_B"]:.3f}, eddy heat {rp["eddy_W"] / 1e6:,.1f} MW per engine; winding fluence '
                f'{flu:.2e} n/m2 = {row["winding_over_limit"]:,.0f} x limit behind {arm} m armour')
            say(f'  dust NOMINAL {dn_t:,.0f} t, JUSTIFIED {dj_t:,.0f} t; engine {eng_t:,.0f} t; departure if heat closed {row["departure_if_heat_closed_t"]:,.0f} t '
                f'(with radiators for the piped heat {row["departure_with_radiators_t"]:,.0f} t)')
            for f in dn:
                say(f'    {f["face"]:36s} {f["area_m2"]:8.0f} m2  {f["kind"]:9s} {f["mass_t"]:8.1f} t  armour {f["armour_m"] or 0:.3f} m'
                    + (f'  screens: {f["screen_events"]:.2g} events, needs {f.get("standoff_needed_m") or 0:.0f} m' if f['standoff_m'] > 0 else ''))
    (HERE / 'results').mkdir(exist_ok=True)
    (HERE / 'results' / 'compact.json').write_text(json.dumps(out, indent=1, default=str))
    (HERE / 'results' / 'compact.log').write_text('\n'.join(log) + '\n')
    L = ['| Variant | burn x m | eta | piped heat / budget | ship direct burn / limit | blades GW | winding fluence / limit | eddy MW/engine | dust t (NOM / JUST) | departure t (heat closed) |',
         '| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |']
    for key, r in out['variants'].items():
        L.append(f"| {key} | {r['x_burn']:.0f} | {r['eta']:.2f} | {r['piped_over_budget']:,.0f} | {r['ship_lit_over_limit']:,.0f} | {r['ship_lit_parts'].get('BLADES', 0) / 1e9:,.0f} | "
                 f"{r['winding_over_limit']:,.0f} | {r['ripple']['eddy_W'] / 1e6:,.1f} | {r['dust_nominal_t']:,.0f} / {r['dust_justified_t']:,.0f} | {r['departure_if_heat_closed_t']:,.0f} |")
    (HERE / 'results' / 'compact.md').write_text('\n'.join(L) + '\n')
    print('\n'.join(L))


if __name__ == '__main__':
    main()
