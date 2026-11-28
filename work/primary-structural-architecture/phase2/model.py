"""PSA Phase II global 3D structural model: geometry generator, mass attachment, load cases and member sizing.

One generator builds every concept from a small set of choices (the vertebral grammar):
  rails      3 single rails (30/150/270 deg) or 6 rails in three paired sectors (each pair +-pair_deg about the sector azimuth)
  materials  per member family (rail, frame, module frame, diagonal, spine, collar, keel, deck, ring, pickup)
  module     frames every 4 m; every `module_bays` bays a deep module frame (H/HC vertebra joint); 0 = no module frames
  rotor bay  'bypass' (production Q45 collar: radial aft spoke to r 33-35 m, two-chord girders, keel ties) or 'hub' (research: the
             rails converge on the stationary hub core through the rotor bay; the collar is kept as a light secondary path)
  pickup     axial offset of the nozzle pickups from the thrust ring (production 0.58 m = 78.7 deg; re-angled options)
  radius     structural radius of the midbody rails (production 5.0 m; research variants)
Coordinates: metres, +X bow, azimuth theta measured from +Y toward +Z (y = r cos theta, z = r sin theta), as the production code.
Geometry follows production stations at main 11f1e94 (thrust ring X -135.25, cage end X 93.60, collar 94.27..105.90, keels to the Brow).
"""
import math
import tomllib
from pathlib import Path

import numpy as np

import fe

H = Path(__file__).resolve().parent
ALLOW = tomllib.loads((H / 'allowables.toml').read_text())
META = ALLOW['meta']
MATS = {m['id']: m for m in ALLOW['material']}

X_RING, X_TRANS, X_CAGE_END = -135.25, -127.25, 93.59936
X_COLLAR_AFT, X_COLLAR_MID, X_COLLAR_FWD = 94.27436, 100.29936, 105.89936
X_SPINE0, X_SPINE1 = -89.8, 118.5
R_RING, R_RAIL, R_COLLAR_IN, R_COLLAR_OUT, R_SPINE = 5.5, 5.0, 33.0, 35.0, 0.95
X_DECK = 108.05
RING_X = (97.3, 103.3)
NOZ_R = 2.6


def mat(mid, which='nom', T=350.0):
    m = MATS[mid]; i = {'low': 0, 'nom': 1, 'high': 2}[which]
    g = lambda v: v[i] if isinstance(v, list) else v
    kT = m.get('k_T_350K', 1.0) if T >= 340 else 1.0
    return dict(id=mid, E=g(m['E'])*1e9, G=m['G']*1e9, rho=m['rho'], alpha=m['alpha']*1e-6, Ft=g(m['Ftu'])*1e6*kT, Fy=g(m['Fty'])*1e6*kT,
                Fc=min(g(m['Fcy']), g(m['Fty']) if m['id'] not in ('ALAL2O3F', 'CFPEEK', 'SICSIC', 'CC') else g(m['Fcy']))*1e6*kT,
                tmin=m['min_gauge_mm']*1e-3)


CONCEPTS = {
    # name: rails, family -> material, module_bays, rotor bay
    'A':  dict(rails=3, mats=dict(rail='AL6061', frame='AL6061', modframe='AL6061', diag='AL6061', spine='AL6061', collar='AL6061', keel='AL6061', deck='AL6061', ring='AL6061', pickup='AL6061', trans='AL6061'), module_bays=0),
    'A6': dict(rails=6, mats=dict(rail='AL6061', frame='AL6061', modframe='AL6061', diag='AL6061', spine='AL6061', collar='AL6061', keel='AL6061', deck='AL6061', ring='AL6061', pickup='AL6061', trans='AL6061'), module_bays=0),
    'C':  dict(rails=3, mats=dict(rail='CFPEEK', frame='AL6061', modframe='AL6061', diag='CFPEEK', spine='TI64', collar='CFPEEK', keel='CFPEEK', deck='AL6061', ring='TI64', pickup='TI64', trans='TI64'), module_bays=0),
    'H':  dict(rails=6, mats=dict(rail='AL6061', frame='AL5083', modframe='AL6061', diag='AL6061', spine='AL6061', collar='AL6061', keel='AL6061', deck='AL6061', ring='TI64', pickup='TI64', trans='TI64'), module_bays=2),
    'H3': dict(rails=3, mats=dict(rail='AL6061', frame='AL5083', modframe='AL6061', diag='AL6061', spine='AL6061', collar='AL6061', keel='AL6061', deck='AL6061', ring='TI64', pickup='TI64', trans='TI64'), module_bays=2),
    'HC': dict(rails=6, mats=dict(rail='ALAL2O3F', frame='AL6061', modframe='AL6061', diag='CFPEEK', spine='TI64', collar='CFPEEK', keel='CFPEEK', deck='AL6061', ring='TI64', pickup='TI64', trans='TI64'), module_bays=2),
}


def tube_for(r, t):
    return fe.tube(r, t)


class Build:
    """Generated structure: fe.Model plus member metadata (family, zone, design group, section design)."""

    def __init__(self, concept, cfg, rotor='bypass', pickup_dx=0.58, radius=R_RAIL, pair_deg=8.6, spine_coupled='datum', bay=4.0,
                 module_bays=None, zone_len=16.0, mats=None):
        c = CONCEPTS[concept]
        self.concept, self.cfg, self.rotor = concept, cfg, rotor
        self.rails = c['rails']; self.mats = dict(c['mats']); self.mats.update(mats or {})
        self.module_bays = c['module_bays'] if module_bays is None else module_bays
        self.pickup_dx, self.R, self.pair_deg, self.spine_coupled, self.bay, self.zone_len = pickup_dx, radius, pair_deg, spine_coupled, bay, zone_len
        self.m = fe.Model(); self.meta = []            # per element: dict(family, group, design)
        self.sec = {}                                  # group -> dict(r, t, mat)
        self.station_nodes = {}                        # x -> {az: node}
        self.build()

    # ---------- geometry ----------------------------------------------------------------------------------------------------------
    def rail_az(self):
        if self.rails == 3:
            return [30.0, 150.0, 270.0]
        d = self.pair_deg
        return sorted([(a+s) % 360 for a in (30.0, 150.0, 270.0) for s in (-d, d)])

    def poly_az(self):
        base = [0, 60, 90, 120, 180, 210, 240, 300, 330] if self.rails == 6 else [0, 60, 90, 120, 180, 210, 240, 300, 330]
        return sorted(set([float(a) for a in base] + self.rail_az()))

    @staticmethod
    def p(x, r, az):
        t = math.radians(az); return (x, r*math.cos(t), r*math.sin(t))

    def r_at(self, x):
        if x <= X_TRANS:
            return R_RING+(self.R-R_RING)*(x-X_RING)/(X_TRANS-X_RING)
        return self.R

    def group(self, fam, x=None, extra=''):
        if fam in ('spine', 'hub', 'ring', 'pickup', 'iface', 'cone', 'hubcone'):
            return fam+extra
        if x is None:
            x = self._xm
        z = int(math.floor((x-X_RING)/self.zone_len)); return f'{fam}:{z:02d}{extra}'

    def add(self, a, b, fam, x=None, extra='', kind='beam'):
        if np.linalg.norm(self.m.X[a]-self.m.X[b]) < 1e-6:
            raise ValueError(f'zero-length {fam} member {a}-{b}')
        self._xm = 0.5*(self.m.X[a][0]+self.m.X[b][0])
        g = self.group(fam, x, extra)
        if fam == 'iface':
            # interface ring owned by another system (Brow truss, forward defense): stiff, massless, not sized by PSA
            e = self.m.beam(a, b, fe.tube(0.6, 0.06), dict(E=2e11, G=8e10, rho=0.0, alpha=0.0), kind=kind, group=g)
            self.meta.append(dict(fam=fam, group=g)); return e
        if g not in self.sec:
            m = self.mats.get(fam) or self.mats[{'cone': 'trans', 'hubcone': 'trans'}.get(fam, 'frame')]
            r0 = dict(rail=0.25, frame=0.12, modframe=0.18, diag=0.08, spine=R_SPINE, collar=0.3, keel=0.2, deck=0.15, ring=0.35, pickup=0.25, trans=0.25,
                      tie=0.1, brow=0.3, hub=R_SPINE, cone=0.25, hubcone=0.3).get(fam, 0.1)
            self.sec[g] = dict(r=r0, t=max(mat(m)['tmin'], 0.004), mat=m, fam=fam, rmax=dict(rail=0.6, frame=0.35, modframe=0.45, diag=0.25, cone=0.6, hubcone=0.8, spine=R_SPINE,
                               collar=1.0, keel=0.5, deck=0.5, ring=0.5, pickup=0.5, trans=0.6, tie=0.3, brow=0.5, hub=R_SPINE).get(fam, 0.2))
        s = self.sec[g]
        e = self.m.beam(a, b, fe.tube(s['r'], s['t']), mat(s['mat']), kind=kind, group=g)
        self.meta.append(dict(fam=fam, group=g))
        return e

    def stations(self):
        xs = [X_RING, X_RING+2.0, X_RING+5.0, X_TRANS]
        x = X_TRANS
        while x+self.bay < X_CAGE_END-0.5:
            x += self.bay; xs.append(round(x, 4))
        xs.append(X_CAGE_END)
        return xs

    def build(self):
        m = self.m; az = self.poly_az(); rails = self.rail_az()
        xs = self.stations(); self.xs = xs
        prev = None
        for k, x in enumerate(xs):
            r = self.r_at(x); ring = {a: m.node(self.p(x, r, a)) for a in az}
            self.station_nodes[x] = ring
            fam = 'ring' if k == 0 else ('modframe' if (self.module_bays and k >= 3 and (k-3) % self.module_bays == 0) or k == len(xs)-1 else 'frame')
            for i, a in enumerate(az):
                self.add(ring[a], ring[az[(i+1) % len(az)]], fam)
            if prev is not None:
                px, pr = prev
                for i, a in enumerate(az):
                    if a in rails:
                        self.add(pr[a], ring[a], 'trans' if x <= X_TRANS else 'rail', px)
                    b = az[(i+1) % len(az)] if k % 2 else az[i-1]
                    self.add(pr[a], ring[b], 'trans' if x <= X_TRANS else 'diag', px)
            prev = (x, ring)
        # nozzles and pickups (drive interface): 4 nozzle nodes at r 2.6 m, three struts each to the ring
        ring0 = self.station_nodes[X_RING]; self.noz = []
        for a in (0.0, 90.0, 180.0, 270.0):
            n = m.node(self.p(X_RING-self.pickup_dx, NOZ_R, a)); self.noz.append(n)
            for b in (a-30.0, a, a+30.0):
                bb = min(ring0, key=lambda q: abs((q-b+180) % 360-180))
                self.add(n, ring0[bb], 'pickup')
        # nozzle-to-nozzle hoop (the drive's own cage holds the nozzles together laterally; modelled stiff)
        for i in range(4):
            self.add(self.noz[i], self.noz[(i+1) % 4], 'pickup')
        # spine
        sx = [x for x in xs if X_SPINE0 <= x <= X_CAGE_END] + [X_COLLAR_AFT, RING_X[0], X_COLLAR_MID, RING_X[1], X_COLLAR_FWD, X_DECK, X_SPINE1]
        sx = sorted(set(round(v, 4) for v in sx)); self.spine = {}
        for x in sx:
            self.spine[x] = m.node((x, 0.0, 0.0))
        for a, b in zip(sx, sx[1:]):
            self.add(self.spine[a], self.spine[b], 'hub' if (self.rotor == 'hub' and X_CAGE_END-8 <= a < X_COLLAR_FWD+8) else 'spine')
        tie_az = [90.0, 210.0, 330.0]   # ties stay out of the rail sectors: the MRU lane (az 270, r 3.6) and the NaK lanes
        for x in sx:
            if x in self.station_nodes:
                for a in tie_az:
                    q = self.station_nodes[x][a]
                    self.tie(self.spine[x], q, a)
        if self.spine_coupled != True and self.rotor != 'hub':
            # axial datum of the spine: a cone at the cage end from the spine to the rails one bay aft (the rotor bay's hub masses
            # reach the cage here; everywhere else the spine slides)
            xa = self.xs[-2]
            for a in tie_az:
                self.add(self.sp(X_CAGE_END), self.station_nodes[xa][a], 'cone')
        self.forward()

    def forward(self):
        m = self.m; cfg = self.cfg; rails = self.rail_az(); sect = [30.0, 150.0, 270.0]
        brow0 = cfg['brow'][0]; keel_end = brow0+2.5; chord_end = brow0+0.6
        cage = self.station_nodes[X_CAGE_END]
        # keels (forward rails) from the collar forward station to the Brow, with frames
        kx = [X_COLLAR_FWD]
        while kx[-1]+self.bay < keel_end-0.5:
            kx.append(round(kx[-1]+self.bay, 4))
        if X_DECK not in kx:
            kx = sorted(set(kx+[X_DECK]))
        kx.append(keel_end); self.kx = kx
        prev = None; self.keel_nodes = {}
        for x in kx:
            ring = {a: m.node(self.p(x, self.R, a)) for a in rails}
            self.keel_nodes[x] = ring
            ra = sorted(ring)
            for i, a in enumerate(ra):
                self.add(ring[a], ring[ra[(i+1) % len(ra)]], 'frame')
            if x in self.spine:
                for a in ra[::(2 if self.rails == 6 else 1)]:
                    self.tie(self.spine[x], ring[a], a)
            if prev is not None:
                for i, a in enumerate(ra):
                    self.add(prev[a], ring[a], 'keel', x)
                    self.add(prev[a], ring[ra[(i+1) % len(ra)]], 'diag', x)
            prev = ring
        # collar: inner/outer chords per sector from the aft spoke station to the chord end
        cx = [X_COLLAR_AFT, X_COLLAR_MID, X_COLLAR_FWD]
        x = X_COLLAR_FWD
        while x+4.5 < chord_end:
            x += 4.5; cx.append(round(x, 4))
        if X_DECK not in cx:
            cx = sorted(set(cx+[X_DECK]))
        cx.append(chord_end); cx = sorted(cx); self.cx = cx
        self.chord = {}
        for a in sect:
            ci = [m.node(self.p(x, R_COLLAR_IN, a)) for x in cx]; co = [m.node(self.p(x, R_COLLAR_OUT, a)) for x in cx]
            self.chord[a] = (ci, co)
            w = 1.0 if self.rotor == 'bypass' else 0.35
            for i in range(len(cx)):
                self.add(ci[i], co[i], 'collar')
                if i:
                    self.add(ci[i-1], ci[i], 'collar'); self.add(co[i-1], co[i], 'collar'); self.add(ci[i-1], co[i], 'collar')
        # hoops at r 35 m (aft, mid, fwd)
        for x in (X_COLLAR_AFT, X_COLLAR_MID, X_COLLAR_FWD):
            j = cx.index(x)
            pts = [self.chord[a][1][j] if a in sect else m.node(self.p(x, R_COLLAR_OUT, a)) for a in [float(v) for v in range(0, 360, 30)]]
            for i in range(12):
                self.add(pts[i], pts[(i+1) % 12], 'collar')
        # aft spokes (rail extension at the cage end to the inner chord) and keel ties
        for a in sect:
            for b in [r for r in rails if abs(((r-a+180) % 360)-180) < 20]:
                self.add(cage[b], self.chord[a][0][0], 'collar')
                self.add(self.keel_nodes[kx[0]][b], self.chord[a][0][cx.index(X_COLLAR_FWD)], 'collar')
        if self.rotor == 'hub':
            # rails converge on the stationary hub core: cone members from the cage end rails to the spine at the collar aft station,
            # and from the spine at the collar forward station out to the keels
            for b in rails:
                self.add(cage[b], self.sp(X_COLLAR_AFT), 'hubcone')
                self.add(self.sp(X_COLLAR_FWD), self.keel_nodes[kx[1]][b], 'hubcone')
            for b in rails:
                prevx = self.xs[-2]
                self.add(self.station_nodes[prevx][b], self.sp(X_CAGE_END), 'hubcone')
        # tank deck at X_DECK: radial members from the spine through the keel ring to the inner chords; the farm's aft fixity
        # deep deck (correction: a thrust deck is loaded out of plane, so it is a two-layer space truss): forward layer at X_DECK
        # carries the farm, aft layer at the collar forward station, verticals and diagonals between them
        self.deck_nodes = []
        layers = {}
        for xl in (X_DECK, X_COLLAR_FWD):
            kk = self.keel_nodes[min(kx, key=lambda q: abs(q-xl))]; j = min(range(len(cx)), key=lambda i: abs(cx[i]-xl)); mids_all = {}
            for a in sect:
                for b in [r for r in rails if abs(((r-a+180) % 360)-180) < 20]:
                    self.add(kk[b], self.chord[a][0][j], 'deck')
                mids = [m.node(self.p(xl, rr, a+60.0)) for rr in (12.0, 22.0, 32.0)]; mids_all[a] = mids
                near = [r for r in rails if abs(((r-(a+60)+180) % 360)-180) < 70]
                for b in near:
                    self.add(kk[b], mids[0], 'deck')
                self.add(mids[0], mids[1], 'deck'); self.add(mids[1], mids[2], 'deck')
                for aa in (a, (a+120) % 360):
                    self.add(mids[2], self.chord[aa][0][j], 'deck')
            layers[xl] = (kk, j, mids_all)
        (kf, jf, mf), (ka, ja, ma) = layers[X_DECK], layers[X_COLLAR_FWD]
        for a in sect:
            for q in range(3):
                self.add(mf[a][q], ma[a][q], 'deck')
                if q:
                    self.add(mf[a][q], ma[a][q-1], 'deck')
            self.add(mf[a][0], ka[min(ka, key=lambda r: abs(((r-(a+60)+180) % 360)-180))], 'deck')
            self.add(self.chord[a][0][jf], ma[a][2], 'deck'); self.add(self.chord[(a+120) % 360][0][jf], ma[a][2], 'deck')
            self.deck_nodes += mf[a]
        dk = kf
        self.deck_nodes += [dk[b] for b in rails]
        for a in sect:
            self.deck_nodes += [self.chord[a][0][jf]]
        # Brow ring: keel ends and chord ends joined by a stiff ring (the Brow truss itself is forward-defense owned)
        bn = [self.keel_nodes[keel_end][b] for b in rails] + [self.chord[a][1][-1] for a in sect] + [self.chord[a][0][-1] for a in sect]
        ang = lambda n: math.degrees(math.atan2(self.m.X[n][2], self.m.X[n][1])) % 360
        self.brow_nodes = bn
        for a in sect:
            ks = [self.keel_nodes[keel_end][b] for b in rails if abs(((b-a+180) % 360)-180) < 20]
            for k in ks:
                self.add(k, self.chord[a][0][-1], 'iface'); self.add(k, self.chord[a][1][-1], 'iface')
        ordered = sorted([self.chord[a][1][-1] for a in sect], key=ang)
        for i in range(3):
            self.add(ordered[i], ordered[(i+1) % 3], 'iface')

    def tie(self, sn, q, a):
        """Spine-to-structure tie. Datum scheme: an axial slide (thermal and strain compliance in X) with lateral and rotational
        fixity (correction 3.5); fully coupled when spine_coupled is True."""
        if self.spine_coupled is True:
            self.add(sn, q, 'tie'); return
        x = self.m.X[sn][0]; mid = self.m.node(self.p(x, 0.5, a)); self.add(mid, q, 'tie')
        self.m.spring(sn, mid, [1.0, 1e10, 1e10, 1e9, 1e9, 1e9], group='slide')
        self.meta.append(dict(fam='slide', group='slide'))

    def sp(self, x):
        return self.spine[min(self.spine, key=lambda q: abs(q-x))]

    # ---------- masses --------------------------------------------------------------------------------------------------------
    def nodes_near(self, x, kind='frame'):
        """Nodes that carry a mass at X: cage frame nodes, keel/deck nodes forward, spine nodes in the rotor bay, Brow nodes."""
        if x < X_RING:
            return self.noz
        if x <= X_CAGE_END+0.5:
            xs = self.xs; k = min(range(len(xs)), key=lambda i: abs(xs[i]-x))
            return [self.station_nodes[xs[k]][a] for a in self.rail_az()]   # equipment mounts on the rail nodes (hard-points)
        return None

    def attach(self, parts):
        """Spread every placed part's mass over the structure along its X range. Rings, refuge and hub items hang on the spine; the
        farm (propellant and tankage) on the deck (aft fixity, forward links slide); the Brow on the Brow nodes; aft of the thrust ring
        on the nozzle nodes (the drive)."""
        m = self.m; farm = self.cfg['farm']; brow = self.cfg['brow']
        for nd in list(m.pm):
            m.pm[nd] = 0.0
        unplaced = 0.0
        for p in parts:
            x0, x1 = p['x']; M = p['m']
            if (p['owner'] in ('propellant', 'tankage') and x0 >= farm[0]-1.0) or 'cryocooler' in p['name']:
                for n in self.deck_nodes:
                    m.mass(n, M/len(self.deck_nodes))
                continue
            if x0 >= brow[0]-1.0:
                for n in self.brow_nodes:
                    m.mass(n, M/len(self.brow_nodes))
                continue
            n = max(2, int((x1-x0)/2.0)+1)
            for i in range(n):
                x = x0+(x1-x0)*(i+0.5)/n; dm = M/n
                if x < X_RING-0.5:
                    for q in self.noz:
                        m.mass(q, dm/4)
                elif x <= X_CAGE_END+0.3:
                    ns = self.nodes_near(x)
                    for q in ns:
                        m.mass(q, dm/len(ns))
                elif x <= X_COLLAR_FWD+3.5 or x <= farm[0]:
                    sx = min(self.spine, key=lambda q: abs(q-x)); m.mass(self.spine[sx], dm)
                elif x < brow[0]:
                    kk = min(self.kx, key=lambda q: abs(q-x)); ns = list(self.keel_nodes[kk].values())
                    for q in ns:
                        m.mass(q, dm/len(ns))
                else:
                    for q in self.brow_nodes:
                        m.mass(q, dm/len(self.brow_nodes))
        return unplaced

    def structure_mass(self):
        tot = 0.0; by = {}
        for e, md in zip(self.m.el, self.meta):
            if e['kind'] == 'spring' or not e['on'] or md['fam'] == 'iface':
                continue
            L, _, _ = self.m.frame(e); w = e['mat']['rho']*e['sec']['A']*L
            tot += w; by[md['fam']] = by.get(md['fam'], 0.0)+w
        return tot, by

    def update_sections(self):
        for e, md in zip(self.m.el, self.meta):
            if e['kind'] == 'spring' or md['fam'] == 'iface':
                continue
            s = self.sec[md['group']]; e['sec'] = fe.tube(s['r'], s['t']); e['mat'] = mat(s['mat'])

    def apply_thrust(self, T, follower=True, out=None, lateral=None):
        self.m.loads = {}; self.m.follow = {}
        share = [T/4]*4
        if out is not None:
            share[out] = 0.0
        for n, f in zip(self.noz, share):
            if f:
                self.m.thrust(n, (f, 0.0, 0.0), follower=follower)
        if lateral:
            for n in self.noz:
                self.m.load(n, lateral)
