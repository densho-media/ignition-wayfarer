#!/usr/bin/env python3
"""ENG-062: early extraction and field topology against hardware interception in the compact Vertex nozzle (research, not canon).

Owner brief 2026-11-24 09:49Z ("Fusion Engineering: From Nucleus to Engine"): continue ENG-062 (energy taken from the X-rays strikes the
nozzle instead) with early extraction, field topology, interception and plasma coupling, keeping energy, mass, momentum and particle
accounting consistent.

What it does (standard library only; the physics is lab/studies/vertex-compact-engine/vertex-ron/ron.py, read-only):
  1. Geometry: the drawn C1 engine (vertex-compact compact.variant, the coupled page's nozzle 'C1|1'), varied in three ways that keep the
     compact silhouette: the reaction position (the burn moved dz metres aft of its drawn point, the hardware fixed), the closure topology
     (forward closure rings at x1, x2, x4 their drawn current share, and a widened aft throat), and the overall field (x1, x2, x4 the
     capture current, as the page's field multiple).
  2. Species-resolved test particles (ron._push, relativistic Boris push in the exact loop field, vacuum field): 14.7 MeV protons and
     3.67 MeV alphas (products that leave the target early), and D and 3He debris at the coupled pulse's own speed (from the ledger:
     sqrt(2 E_plasma / m), equal speeds). Each species gives its hit share and its mean axial cosine (hits count zero).
  3. Momentum-consistent engine ledger: impulse is the sum of p cos over the particles that leave; particles that strike stay in the engine
     (their mass is deposited, their energy is heat). The fast products carry energy but almost no momentum (p = sqrt(2 m E) per particle),
     so early extraction cuts the X-rays and heat but does not raise thrust unless their energy reaches the propellant mass, which no model
     here couples (OPEN, labelled).
  4. Every source lever of vertex-source (results/source.json) through every geometry: X-rays, hardware heat over its radiator share,
     thrust, exhaust speed, deposited mass, and the frontier.

    python3 lab/studies/vertex-compact-engine/vertex-extraction/extraction.py [--quick]     writes results/extraction.json and .log

Classes: SAMPLED (test particles, statistical error from the direction count), CALCULATED (ledger arithmetic), PROTOTYPE (geometry
choices), OPEN (plasma response: diamagnetic expansion, detachment, collective effects; vacuum test particles are an upper-bound picture
of magnetisation for the debris and a fair one for the fast products).
"""
import json
import math
import sys
import time
from multiprocessing import Pool
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
QUICK = '--quick' in sys.argv
sys.path.insert(0, str(HERE.parent / 'vertex-compact'))
_argv = list(sys.argv); sys.argv.append('--quick')            # compact.py reads --quick at import; only its N changes, not used here
import compact as Cmp  # noqa: E402
sys.argv = _argv
ron = Cmp.ron
AMU, MEV, C = ron.AMU, ron.MEV, ron.C

FI = ROOT / 'lab/studies/fusion-ignition/results/fusion_ignition.json'
SRC = HERE.parent / 'vertex-source/results/source.json'
N_DIR = 16 if QUICK else 24                       # equal-solid-angle polar directions per species (on-axis point source)
DZ = (0.0,) if QUICK else (-1.0, 0.0, 2.0, 4.0)   # burn moved aft of its drawn point, m (PROTOTYPE; the hardware is fixed)
TOPO = {                                          # closure-ring current factor, aft-ring radius factor (PROTOTYPE)
    'drawn': (1.0, 1.0, 'as drawn (C1)'),
    'mirror2': (2.0, 1.0, 'closure rings at twice their drawn current share'),
    'mirror4': (4.0, 1.0, 'closure rings at four times their drawn current share'),
    'throat': (2.0, 1.25, 'closure x2 and the aft rings 25 % wider'),
}
MULTS = (1.0,) if QUICK else (1.0, 4.0)


def geometry(topo, dz):
    xb1 = Cmp.SHIP['x_burn']; D1 = Cmp.SHIP['tank'][0] - xb1
    p, sh = Cmp.variant('C1 production cluster as drawn', D1, 6.0, 0.62)
    fc, fr, _ = TOPO[topo]
    rings = []
    for (x, r, s) in p['rings']:
        if x > 0.5:                                # forward of the burn: closure rings (the two shield-side loops and C1/C2)
            s = s * fc
        else:
            r = r * fr
        rings.append((x + dz, r, s))
    x0, r0, r1, t = p['shield_disc']
    return dict(p, label=f'C1 {topo} dz {dz:+g} m', rings=rings, plug_x_m=p['plug_x_m'] + dz, shield_disc=(x0 + dz, r0, r1, t))


def species(v_debris):
    return [dict(id='p14.7', m=1.00728 * AMU, Z=1, E=14.68 * MEV, fast=True),
            dict(id='a3.6', m=4.00151 * AMU, Z=2, E=3.67 * MEV, fast=True),
            dict(id='D', m=2.01410 * AMU, Z=1, v=v_debris, fast=False),
            dict(id='He3', m=3.01603 * AMU, Z=2, v=v_debris, fast=False)]


def run_config(pool, k, topo, dz, mults, sps, ref_sp=None):
    p = geometry(topo, dz)
    v, src, E, cap = ron.configure(p, k)
    out = []
    for m in mults:
        kk = cap['k'] * m
        for c in v['coils']:
            c['thick'] = max(0.01, abs(c['I']) * kk / 1.53e8 / c['depth'])
        for e in v['elements']:
            if e['role'] == 'coil':
                c = next(c for c in v['coils'] if c['name'] == e['name']); e['h'] = c['thick'] / 2 + v['cryo_m']
        cp = dict(cap, k=kk, W_J=ron.stored_energy(ron.filaments(v['coils']), kk))
        dirs = ron.fib_dirs(N_DIR)
        todo = list(sps) + ([ref_sp] if ref_sp and m == 1.0 else [])
        tasks = [(v, kk, sp, d, False) for sp in todo for d in dirs]
        res = pool.map(ron._push, tasks, chunksize=2)
        S = {}
        for j, sp in enumerate(todo):
            rr = res[j * N_DIR:(j + 1) * N_DIR]
            hit = sum(r['out'] == 'HIT' for r in rr) / N_DIR
            parts = {}
            for r in rr:
                if r['out'] == 'HIT':
                    parts[r['part']] = parts.get(r['part'], 0) + 1
            S[sp['id']] = dict(hit=hit, aft=sum(r['out'] == 'AFT' for r in rr) / N_DIR, forward=sum(r['out'] == 'FORWARD' for r in rr) / N_DIR,
                               trapped=sum(r['out'] == 'TRAPPED' for r in rr) / N_DIR,
                               cos=sum(r['cos'] for r in rr if r['out'] in ('AFT', 'FORWARD', 'RADIAL')) / N_DIR,
                               err=math.sqrt(max(hit * (1 - hit), 1.0 / N_DIR) / N_DIR), parts=parts)
        ms = ron.masses(v, k, cp, src)
        coil_t = ms['conductor_t'] + ms['coil_structure_t'] + ms['cryostat_t']
        out.append(dict(topo=topo, dz=dz, mult=m, k=kk, stored_J=cp['W_J'], coil_t=coil_t, species=S,
                        B_burn_T=math.hypot(*ron.field(ron.filaments(v['coils']), 0.0, 1e-6, kk)),
                        rings=[(round(x, 2), round(r, 2), round(s, 3)) for x, r, s in p['rings']]))
        print(f'{topo:8s} dz {dz:+4.1f} x{m:g}: ' + ' '.join(f'{s} hit {S[s]["hit"]:.2f} cos {S[s]["cos"]:+.2f}' for s in S) + f'  coils {coil_t:.0f} t', flush=True)
    return out


# ---------- the momentum-consistent engine ledger ----------------------------------------------------------------------------------

def engine(row, g, led, pickup, budget_W, Hz, xray_J=None, extra_mass=0.0, extra_plasma_J=0.0):
    """One pulse of a source case through geometry g. Debris (the thermal plasma, equal speeds) leaves with its species' mean axial cosine;
    the fraction that strikes stays in the engine. Fast products (escaped from the target) are booked per particle. Returns the same
    fields as the fusion-ignition ledger, plus the deposited mass and the fast-product share of the impulse."""
    F = row['fusion_J']; X = F * row['xray_share'] if xray_J is None else xray_J; N_ = F * row['neutron_share']
    Pd = F * row['plasma_share'] + extra_plasma_J; Pf = F * row.get('escaped_share', 0.0)
    md = row['mass_kg'] - F / C ** 2 + extra_mass                       # debris mass (fuel left after the mass defect, plus any tamper)
    S = g['species']
    # debris: D and 3He by energy at equal speed (1:1 by atoms -> energy shares 2/5 and 3/5 by mass)
    wD, wH = 2 / 5, 3 / 5
    hit_d = wD * S['D']['hit'] + wH * S['He3']['hit']; cos_d = wD * S['D']['cos'] + wH * S['He3']['cos']
    I_d = cos_d * math.sqrt(2 * md * Pd)
    m_out = (1 - hit_d) * md
    # fast products: 14.68 MeV protons and 3.67 MeV alphas, energy 4:1
    I_f = 0.0; hit_f_E = 0.0; m_f = 0.0
    for sid, Ep, mp, share in (('p14.7', 14.68 * MEV, 1.00728 * AMU, 14.68 / 18.35), ('a3.6', 3.67 * MEV, 4.00151 * AMU, 3.67 / 18.35)):
        Pi = Pf * share; Ni = Pi / Ep; mi = Ni * mp
        I_f += S[sid]['cos'] * math.sqrt(2 * mi * Pi)
        hit_f_E += S[sid]['hit'] * Pi; m_f += (1 - S[sid]['hit']) * mi
    hit_J = hit_d * Pd + hit_f_E
    I = I_d + I_f; mx = m_out + m_f
    jet = I * I / (2 * mx) if mx > 0 else 0.0
    heat = pickup * (X + N_) + hit_J
    return dict(impulse_Ns=I, fast_impulse_share=I_f / I if I else 0.0, thrust_N=I * Hz, exhaust_m_s=I / mx if mx else 0.0,
                exhaust_mass_kg=mx, deposited_kg=hit_d * md, deposited_kg_s=hit_d * md * Hz, jet_J=jet, jet_share=jet / F,
                hit_J=hit_J, hit_share_plasma=hit_J / max(Pd + Pf, 1e-30), heat_W=heat * Hz, heat_over=heat * Hz / budget_W,
                xray_heat_share=pickup * X / heat, hit_heat_share=hit_J / heat, xray_share=X / F)


def main():
    t0 = time.time()
    fi = json.loads(FI.read_text()); src = json.loads(SRC.read_text())
    L = fi['ledger']; nz = L['nozzle']['C1|1']; Hz = L['pulse']['Hz']; budget = nz['budget_W']; pickup = nz['pickup']
    base = next(r for r in src['levers'] if r['lever'] == 'base')
    m_d = base['mass_kg'] - base['fusion_J'] / C ** 2
    v_deb = math.sqrt(2 * base['fusion_J'] * base['plasma_share'] / m_d)
    k = ron.canon()
    sps = species(v_deb)
    ref = dict(id='D_ref', m=2.01410 * AMU, Z=1, v=0.0677 * C, fast=False)     # the compact study's debris speed (reconciles 'C1|1')
    G = []
    with Pool(4) as pool:
        for topo in TOPO:
            for dz in DZ:
                if QUICK and topo not in ('drawn', 'mirror4'):
                    continue
                G += run_config(pool, k, topo, dz, MULTS, sps, ref if (topo == 'drawn' and dz == 0.0) else None)
    drawn = next(g for g in G if g['topo'] == 'drawn' and g['dz'] == 0.0 and g['mult'] == 1.0)
    # every source lever through every geometry
    cases = [r for r in src['levers']]
    best_t = src['best']
    rows = []
    for g in G:
        for r in cases:
            e = engine(r, g, L, pickup, budget, Hz)
            rows.append(dict(geo=f"{g['topo']}|{g['dz']:g}|{g['mult']:g}", lever=r['label'], cls=r['cls'], **e))
    # the old ledger arithmetic on the drawn geometry (energy share as if every ion left), for the record
    def old(r):
        Pp = r['extract_J']; jet = nz['eta'] * Pp; m = r['mass_kg'] - r['fusion_J'] / C ** 2
        return dict(thrust_N=math.sqrt(2 * m * jet) * Hz, exhaust_m_s=math.sqrt(2 * jet / m))
    recon = dict(ledger_C1=dict(eta=nz['eta'], hit=nz['hit']), drawn_ref_debris=drawn['species'].get('D_ref'),
                 debris_speed_m_s=v_deb, ref_speed_m_s=0.0677 * C,
                 note='The page ledger used the nozzle\'s mean axial cosine eta as an energy share (jet = eta P) and let every ion leave; '
                      'momentum conservation gives I = eta sqrt(2 m P) for equal-speed debris and leaves the struck share in the engine.')
    base_rows = {rw['geo']: rw for rw in rows if rw['lever'] == base['label']}
    best = min((rw for rw in rows), key=lambda x: x['heat_over'])
    frontier = []
    for rw in sorted(rows, key=lambda x: x['heat_over']):
        if not frontier or rw['thrust_N'] > frontier[-1]['thrust_N']:
            frontier.append(rw)
    out = dict(cls='SAMPLED', study='vertex-extraction', source='lab/studies/vertex-compact-engine/vertex-extraction/extraction.py',
               quick=QUICK, n_dir=N_DIR, topologies={k_: v_[2] for k_, v_ in TOPO.items()}, dz=list(DZ), mults=list(MULTS),
               debris_speed_m_s=v_deb, geometries=G, rows=rows, reconcile=recon,
               old_vs_new=[dict(lever=r['label'], old=old(r), new={kk: engine(r, drawn, L, pickup, budget, Hz)[kk] for kk in ('thrust_N', 'exhaust_m_s', 'heat_over', 'fast_impulse_share')}) for r in cases],
               base_by_geo={kk: {q: vv[q] for q in ('thrust_N', 'exhaust_m_s', 'heat_over', 'deposited_kg_s', 'hit_share_plasma')} for kk, vv in base_rows.items()},
               best_heat=best, frontier=frontier[:12], runtime_s=time.time() - t0)
    (HERE / 'results' / 'extraction.json').write_text(json.dumps(out, indent=1))
    print(f'done in {time.time() - t0:.0f} s; best heat {best["geo"]} {best["lever"]}: heat x{best["heat_over"]:.0f}, thrust {4 * best["thrust_N"] / 1e6:.2f} MN')


if __name__ == '__main__':
    main()
