"""PSA Phase III structural model on WF-F1-C1.1 (SSI-1.1): the Phase II vertebral cage plus

  * physical mass representation (owner 3.1): every body keeps its mass, centre and inertia; vessels are rigid bodies on their aft
    skirts (anchor) and forward guide rings (radial only); rings sit on the hub bearings free in roll; lines and blades are sliced at
    their true radius and azimuth and tied to the nearest frame by massless rigid arms. Conservation is checked (mass_check).
  * tank-specific deck reactions (owner 3.2): the deck has a node under every skirt attachment point of every vessel.
  * deck concepts (owner 4): TD-A corrected reference, TD-B deep 3D deck, TD-C distributed tank thrust structures, TD-D longitudinally
    integrated supports, TD-E integral tank frames, TD-F reconfigured habitat interface (see build_deck()).
  * the rotor-bay keep-out K-RING (x 93.65..106.95, r <= 31.5) is respected by every primary member (the Phase II deck aft layer and
    hub cones crossed it; corrected here).
"""
import math
import sys
from pathlib import Path

import numpy as np
from scipy.spatial import Delaunay

H = Path(__file__).resolve().parent
sys.path.insert(0, str(H.parent / 'phase2'))
import fe  # noqa: E402
import model as mdl  # noqa: E402
from model import X_RING, X_TRANS, X_CAGE_END, R_SPINE, NOZ_R  # noqa: E402

K_RING = (93.65, 106.95, 31.5)
RING_X = (97.29936, 103.29936)
R_HOOP_IN, R_HOOP_OUT = 35.0, 37.0          # outer farm chords (outside the 34.2 m outer vessel envelope)
SKIRT_PTS = 6
K_SKIRT = [2.0e9, 2.0e9, 2.0e9, 1.0e7, 1.0e7, 1.0e7]          # per skirt point, global axes (PROTOTYPE: skirt EA/L ~ 1.4e10 N/m total)
K_GUIDE = [1.0e3, 1.0e9, 1.0e9, 1.0e3, 1.0e3, 1.0e3]          # forward guide ring: radial only, axial slide (cryogenic contraction)
K_BEARING = [5.0e10, 5.0e10, 5.0e10, 1.0e3, 5.0e11, 5.0e11]  # hub bearing pair: free in roll (spin), stiff in tilt (PROTOTYPE)
K_ANCHOR = [5.0e9]*3 + [5.0e8]*3
K_SLIDE = [1.0e3, 5.0e9, 5.0e9, 1.0e3, 1.0e3, 1.0e3]
K_SADDLE = [2.0e8, 1.0e9, 1.0e9, 1.0e3, 1.0e3, 1.0e3]     # TD-D intermediate saddle: axial shear flexure (contraction), radial/tangential stiff (PROTO)
K_FWD_E = [5.0e8, 1.0e9, 1.0e9, 1.0e7, 1.0e7, 1.0e7]      # TD-E forward end: tank wall continuous with the guide plane, axial flexure (PROTO)
TANKWALL_CREDIT = 0.5                                      # TD-E: share of the tankage mass that is pressure shell, credited to the wall (PROTO)
STRINGER_PITCH = 8.0


def wrap(a):
    return (a+180.0) % 360.0-180.0


class Build3(mdl.Build):
    def __init__(self, concept, cfg, deck='A', rotor='hub', deck_depth=None, slice_m=4.0, **kw):
        self.deck_kind = deck; self.slice_m = slice_m; self.deck_depth = deck_depth
        self.farm = cfg['farm']; self.brow = cfg['brow']
        cfg = dict(cfg); cfg['parts'] = cfg['bodies']
        if deck == 'F':
            rotor = 'bypass'      # TD-F: habitat interface on the outer collar path; the hub path stops being primary
        super().__init__(concept, cfg, rotor=rotor, **kw)
        self.place(cfg['bodies'])

    # ---------- primary structure ------------------------------------------------------------------------------------------------
    def build(self):
        m = self.m; az = self.poly_az(); rails = self.rail_az()
        xs = self.stations(); self.xs = xs; prev = None
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
        ring0 = self.station_nodes[X_RING]; self.noz = []
        for a in (0.0, 90.0, 180.0, 270.0):
            n = m.node(self.p(X_RING-self.pickup_dx, NOZ_R, a)); self.noz.append(n)
            for b in (a-30.0, a, a+30.0):
                bb = min(ring0, key=lambda q: abs((q-b+180) % 360-180))
                self.add(n, ring0[bb], 'pickup')
        for i in range(4):
            self.add(self.noz[i], self.noz[(i+1) % 4], 'pickup')
        # deck planes (TD-A: aft layer at the keep-out end, forward layer on the skirt plane)
        self.x_skirt = self.farm[0]; self.x_deck_aft = K_RING[1]+0.05
        self.x_guide = self.farm[1]
        sx = [x for x in xs if mdl.X_SPINE0 <= x <= X_CAGE_END] + list(RING_X) + [0.5*(RING_X[0]+RING_X[1]), self.x_deck_aft, self.x_skirt, 118.5]
        sx = sorted(set(round(v, 4) for v in sx)); self.spine = {}
        for x in sx:
            self.spine[x] = m.node((x, 0.0, 0.0))
        for a, b in zip(sx, sx[1:]):
            self.add(self.spine[a], self.spine[b], 'hub' if (self.rotor == 'hub' and X_CAGE_END-8 <= a < self.x_deck_aft+8) else 'spine')
        for x in sx:
            if x in self.station_nodes:
                for a in (90.0, 210.0, 330.0):
                    self.tie(self.spine[x], self.station_nodes[x][a], a)
        if self.rotor != 'hub':
            xa = self.xs[-2]
            for a in (90.0, 210.0, 330.0):
                self.add(self.sp(X_CAGE_END), self.station_nodes[xa][a], 'cone')
        self.forward()

    def forward(self):
        m = self.m; rails = self.rail_az(); sect = [30.0, 150.0, 270.0]
        brow0 = self.brow[0]; keel_end = brow0+2.5; chord_end = brow0+0.6
        # keels at the sector radius from the deck aft layer to the Brow (frames every bay, stations on the deck and guide planes)
        kx = [self.x_deck_aft, self.x_skirt]
        while kx[-1]+self.bay < keel_end-0.5:
            kx.append(round(kx[-1]+self.bay, 4))
        kx = sorted(set(kx+[self.x_guide, keel_end])); self.kx = kx
        prev = None; self.keel_nodes = {}
        for x in kx:
            ring = {a: m.node(self.p(x, self.R, a)) for a in rails}; self.keel_nodes[x] = ring; ra = sorted(ring)
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
        # outer farm chords (inner r 35 / outer r 37) per sector from the deck aft layer to the Brow, with hoops at the deck and guide planes
        cx = sorted(set([self.x_deck_aft, self.x_skirt, self.x_guide, chord_end] + [x for x in kx if self.x_skirt < x < chord_end and (x-self.x_skirt) % 8.0 < 1e-6]))
        self.cx = cx; self.chord = {}
        for a in sect:
            ci = [m.node(self.p(x, R_HOOP_IN, a)) for x in cx]; co = [m.node(self.p(x, R_HOOP_OUT, a)) for x in cx]
            self.chord[a] = (ci, co)
            for i in range(len(cx)):
                self.add(ci[i], co[i], 'collar')
                if i:
                    self.add(ci[i-1], ci[i], 'collar'); self.add(co[i-1], co[i], 'collar'); self.add(ci[i-1], co[i], 'collar')
        # rotor bay: hub path (spine through the bearings, cones outside the rotor keep-out) or bypass collar (r 33-35 round the rings)
        cage = self.station_nodes[X_CAGE_END]
        if self.rotor == 'hub':
            prevx = self.xs[-2]
            for b in rails:
                self.add(self.station_nodes[prevx][b], self.sp(X_CAGE_END), 'hubcone')
                self.add(cage[b], self.sp(X_CAGE_END-4.0), 'hubcone')
                self.add(self.sp(self.x_deck_aft), self.keel_nodes[kx[2]][b], 'hubcone')
                self.add(self.sp(self.x_skirt), self.keel_nodes[kx[3]][b], 'hubcone')
        else:
            for a in sect:
                ci, co = self.chord[a]
                xa = [X_CAGE_END, 0.5*(K_RING[0]+K_RING[1])]
                na = [m.node(self.p(x, R_HOOP_IN, a)) for x in xa]; nb = [m.node(self.p(x, R_HOOP_OUT, a)) for x in xa]
                for i in range(2):
                    self.add(na[i], nb[i], 'collar')
                self.add(na[0], na[1], 'collar'); self.add(nb[0], nb[1], 'collar'); self.add(na[0], nb[1], 'collar')
                self.add(na[1], ci[0], 'collar'); self.add(nb[1], co[0], 'collar'); self.add(na[1], co[0], 'collar')
                for b in [r for r in rails if abs(wrap(r-a)) < 20]:
                    self.add(cage[b], na[0], 'collar'); self.add(self.station_nodes[self.xs[-2]][b], na[0], 'collar')
        self.build_deck()
        self.build_guide()
        if self.deck_kind == 'D':
            self.stringers_to_guide()
        bn = [self.keel_nodes[keel_end][b] for b in rails] + [self.chord[a][1][-1] for a in sect] + [self.chord[a][0][-1] for a in sect]
        self.brow_nodes = bn
        for a in sect:
            for k in [self.keel_nodes[keel_end][b] for b in rails if abs(wrap(b-a)) < 20]:
                self.add(k, self.chord[a][0][-1], 'iface'); self.add(k, self.chord[a][1][-1], 'iface')
        ang = lambda n: math.degrees(math.atan2(self.m.X[n][2], self.m.X[n][1])) % 360
        o = sorted([self.chord[a][1][-1] for a in sect], key=ang)
        for i in range(3):
            self.add(o[i], o[(i+1) % 3], 'iface')

    # ---------- deck concepts --------------------------------------------------------------------------------------------------------
    def vessels(self):
        return [b for b in self.cfg['bodies'] if b['kind'] == 'vessel' and b['owner'] == 'tankage']

    def skirt_points(self, v, n=SKIRT_PTS):
        c = np.array(self.p(0, v['R'], v['az']))[1:]; return [c + v['a']*np.array([math.cos(2*math.pi*k/n), math.sin(2*math.pi*k/n)]) for k in range(n)]

    def struct_pts(self, x):
        """Existing primary nodes in a deck plane: keels, chords (inner), spine."""
        pts = []
        if x in self.keel_nodes:
            pts += list(self.keel_nodes[x].values())
        j = self.cx.index(x) if x in self.cx else None
        if j is not None:
            pts += [self.chord[a][0][j] for a in self.chord] + [self.chord[a][1][j] for a in self.chord]
        if x in self.spine:
            pts.append(self.spine[x])
        return pts

    def plate(self, x, extra_yz, fam, tag, lmax=16.0, nodes=None):
        """Triangulated plane of members at X through the existing primary nodes and new points extra_yz. Returns {key: node}."""
        base = self.struct_pts(x); yz = [self.m.X[n][1:] for n in base] + list(extra_yz)
        ids = list(base) + [None]*len(extra_yz)
        if nodes is not None:
            for i, n in enumerate(nodes):
                ids[len(base)+i] = n
        for i in range(len(ids)):
            if ids[i] is None:
                ids[i] = self.m.node((x, yz[i][0], yz[i][1]))
        tri = Delaunay(np.array(yz)); edges = set()
        for s in tri.simplices:
            for a, b in ((s[0], s[1]), (s[1], s[2]), (s[0], s[2])):
                edges.add((min(a, b), max(a, b)))
        out = []
        for a, b in sorted(edges):
            L = np.linalg.norm(np.array(yz[a])-np.array(yz[b]))
            if L > lmax or L < 0.3:
                continue
            rm = np.linalg.norm(0.5*(np.array(yz[a])+np.array(yz[b]))); band = int(rm//8)
            self.add(ids[a], ids[b], fam, x, extra=f'-{tag}{band}'); out.append((a, b))
        return ids, yz, out

    def build_deck(self):
        """Common thrust deck under the vessel skirts. TD-A corrected reference: two triangulated layers (aft at the keep-out end,
        forward on the skirt plane) with verticals and diagonals; every skirt point is a deck node."""
        vs = self.vessels(); pts = []; self.skirt_nodes = {}
        for v in vs:
            for k, q in enumerate(self.skirt_points(v)):
                pts.append(q); self.skirt_nodes.setdefault(v['vid'], []).append(len(pts)-1)
        kind = {'E': 'A', 'F': 'A'}.get(self.deck_kind, self.deck_kind)
        if kind == 'D':
            self.build_stringers()
            kind = 'A'
        if kind in ('A', 'B'):
            xf, xa = self.x_skirt, self.x_deck_aft
            idf, yzf, ef = self.plate(xf, pts, 'deck', 't')
            nb = len(self.struct_pts(xf))
            if kind == 'B':
                # TD-B: deep deck. A forward apex layer between the vessels (r 8..34) rises to x_skirt + depth: struts run from the
                # aft layer through the skirt plane up to apex nodes placed in the gaps between vessels, turning the plate into a
                # shallow cone-truss carrying load mostly axially
                depth = self.deck_depth or 8.0
                gaps = self.gap_points()
                apex = [self.m.node((xf+depth, y, z)) for y, z in gaps]; self.apex = apex
                ida, yza, ea = self.plate(xa, pts, 'deck', 'b')
            else:
                ida, yza, ea = self.plate(xa, pts, 'deck', 'b')
            nba = len(self.struct_pts(xa))
            # verticals and diagonals between the layers at the skirt points (structure nodes are joined by the keels / chords)
            for i in range(len(pts)):
                self.add(ida[nba+i], idf[nb+i], 'deck', xf, extra='-v')
            for a, b in ef:
                if a >= nb and b >= nb:
                    self.add(ida[a-nb+nba], idf[b], 'deck', xf, extra='-d')
            # aft layer joins the structure nodes of the forward layer by diagonals as well
            for a, b in ef:
                if (a < nb) != (b < nb):
                    s, p = (a, b) if a < nb else (b, a)
                    self.add(idf[s], ida[p-nb+nba], 'deck', xf, extra='-d')
            if kind == 'B':
                gaps = self.gap_points()
                for g, n in zip(gaps, self.apex):
                    near = sorted(range(len(pts)), key=lambda i: np.linalg.norm(np.array(pts[i])-np.array(g)))[:4]
                    for i in near:
                        self.add(n, ida[nba+i], 'deck', xf, extra='-c')   # long compression struts: apex to aft layer
                        self.add(n, idf[nb+i], 'deck', xf, extra='-c')
                    xk = min(self.kx, key=lambda q: abs(q-(xf+(self.deck_depth or 8.0))))
                    k = min(self.keel_nodes[xk].values(), key=lambda q: np.linalg.norm(self.m.X[q][1:]-np.array(g)))
                    self.add(n, k, 'deck', xf, extra='-c')
            self.skirt_struct = {v['vid']: [idf[nb+i] for i in self.skirt_nodes[v['vid']]] for v in vs}
        elif kind == 'C':
            # TD-C: no common deck. Each vessel's skirt carries its own thrust cone: six struts from the skirt points converge aft to
            # two nodes on the nearest primary members (keel pair or chord) at the keep-out plane, plus a skirt ring
            self.skirt_struct = {}
            for v in vs:
                ns = [self.m.node((self.x_skirt, q[0], q[1])) for q in self.skirt_points(v)]
                for i in range(len(ns)):
                    self.add(ns[i], ns[(i+1) % len(ns)], 'deck', self.x_skirt, extra='-ring')
                targets = self.nearest_primary(v, self.x_deck_aft, 2)
                for n in ns:
                    for t in targets:
                        self.add(n, t, 'deck', self.x_skirt, extra='-cone')
                self.skirt_struct[v['vid']] = ns
            # the keels and chords still need a light tie plane at the deck aft layer (radial struts) to share the sector loads
            self.plate(self.x_deck_aft, [], 'deck', 'tie')
        else:
            raise ValueError(kind)

    def build_stringers(self):
        """TD-D longitudinally integrated supports: stringers in the gaps between vessels from the skirt plane to the guide plane, with
        frame struts every STRINGER_PITCH to the keels / chords; each vessel also bears on the stringers through two intermediate
        saddles (axial shear flexures), so part of its thrust load enters the farm structure along its length instead of all at the deck."""
        gaps = self.gap_points(); xs = [self.x_skirt]
        while xs[-1]+STRINGER_PITCH < self.x_guide-2.0:
            xs.append(round(xs[-1]+STRINGER_PITCH, 4))
        self.str_x = xs; self.str_nodes = {x: [self.m.node((x, g[0], g[1])) for g in gaps] for x in xs}
        pool_k = lambda x: list(self.keel_nodes[min(self.kx, key=lambda q: abs(q-x))].values())
        for i, x in enumerate(xs):
            row = self.str_nodes[x]
            if i:
                for a, b in zip(self.str_nodes[xs[i-1]], row):
                    self.add(a, b, 'deck', x, extra='-s')
            if i == 0:
                continue
            for n in row:
                y = self.m.X[n]
                near = sorted([q for q in row if q != n], key=lambda q: np.linalg.norm(self.m.X[q]-y))[:2]
                for q in near:
                    if q > n:
                        self.add(n, q, 'deck', x, extra='-sf')
                k = min(pool_k(x), key=lambda q: np.linalg.norm(self.m.X[q][1:]-y[1:]))
                if np.linalg.norm(self.m.X[k]-y) > 0.3:
                    self.add(n, k, 'deck', x, extra='-sf')
        self.saddle_pts = {}
        for v in self.vessels():
            c = np.array(self.p(0, v['R'], v['az']))[1:]; L = v['x1']-v['x0']
            for f in (1/3, 2/3):
                x = min(xs[1:], key=lambda q: abs(q-(v['x0']+f*L)))
                near = sorted(self.str_nodes[x], key=lambda q: np.linalg.norm(self.m.X[q][1:]-c))[:3]
                self.saddle_pts.setdefault(v['vid'], []).append((f, near))

    def stringers_to_guide(self):
        """Stringer roots on the deck forward layer and tips on the guide plane (nearest three plane nodes each)."""
        root = self.str_nodes[self.str_x[0]]; tip = self.str_nodes[self.str_x[-1]]
        fwd = [n for n in range(len(self.m.X)) if abs(self.m.X[n][0]-self.x_skirt) < 1e-6 and n not in root]
        gp = [n for n in range(len(self.m.X)) if abs(self.m.X[n][0]-self.x_guide) < 1e-6]
        for n in root:
            for q in sorted(fwd, key=lambda q: np.linalg.norm(self.m.X[q]-self.m.X[n]))[:3]:
                self.add(n, q, 'deck', self.x_skirt, extra='-sr')
        for n in tip:
            for q in sorted(gp, key=lambda q: np.linalg.norm(self.m.X[q]-self.m.X[n]))[:3]:
                if np.linalg.norm(self.m.X[q]-self.m.X[n]) > 0.3:
                    self.add(n, q, 'guide', self.x_guide, extra='-st')

    def tank_credit_t(self):
        """TD-E: mass of the credited pressure-shell share already in the tankage ledger (subtracted from the PSA increment)."""
        return sum(c['m_kg'] for c in getattr(self, 'tw_credit', {}).values())/1e3

    def keepout_violations(self):
        """Primary members entering the rotor keep-out K-RING (x 93.65..106.95, r <= 31.5), except the hub path inside the
        stationary spine (r <= R_SPINE)."""
        bad = []
        for e, md in zip(self.m.el, self.meta):
            if e['kind'] == 'spring' or md['fam'] in ('iface', 'mount', 'spine', 'hub', 'tie', 'slide'):
                continue
            a, b = self.m.X[e['a']], self.m.X[e['b']]
            for t in np.linspace(0, 1, 11):
                q = a+(b-a)*t; r = math.hypot(q[1], q[2])
                if K_RING[0]+0.01 < q[0] < K_RING[1]-0.01 and R_SPINE+0.05 < r < K_RING[2]:
                    bad.append((md['group'], round(float(q[0]), 2), round(r, 2))); break
        return bad

    def gap_points(self):
        vs = self.vessels(); g = []
        for ring_r, n in ((20.6, 9), (8.0, 6)):
            for k in range(n):
                azk = 360.0*k/n+20.0; q = np.array(self.p(0, ring_r, azk))[1:]
                if all(np.linalg.norm(q-np.array(self.p(0, v['R'], v['az']))[1:]) > v['a']+0.8 for v in vs):
                    g.append(q)
        return g

    def nearest_primary(self, v, x, n):
        c = np.array(self.p(0, v['R'], v['az']))[1:]; cand = self.struct_pts(x)
        return sorted(cand, key=lambda q: np.linalg.norm(self.m.X[q][1:]-c))[:n]

    def build_guide(self):
        """Forward guide plane on the guide station: a light triangulated hoop-deck carrying the radial guide loads of the vessels."""
        pts = []; self.guide_idx = {}
        for v in self.vessels():
            c = np.array(self.p(0, v['R'], v['az']))[1:]; u = c/np.linalg.norm(c); t = np.array([-u[1], u[0]])
            for d in (u, -u, t, -t):
                pts.append(c+v['a']*d); self.guide_idx.setdefault(v['vid'], []).append(len(pts)-1)
        ids, yz, e = self.plate(self.x_guide, pts, 'guide', 'g')
        nb = len(self.struct_pts(self.x_guide))
        self.guide_struct = {k: [ids[nb+i] for i in idx] for k, idx in self.guide_idx.items()}

    # ---------- bodies --------------------------------------------------------------------------------------------------------------
    def group(self, fam, x=None, extra=''):
        if fam == 'tankwall':
            return fam+extra
        return super().group(fam, x, extra)

    def tie(self, sn, q, a):
        """Spine tie with the axial slide at the spine node (zero-length, global axes). Phase II put the slide between the spine node and a
        node 0.5 m off axis, which resisted rigid roll (3.6e11 J/rad^2 of fictitious energy, a spurious 0.01 Hz roll mode)."""
        if self.spine_coupled is True:
            self.add(sn, q, 'tie'); return
        mid = self.m.node(self.m.X[sn]); self.add(mid, q, 'tie')
        self.m.spring(sn, mid, [1.0, 1e10, 1e10, 1e9, 1e9, 1e9], group='slide')
        self.meta.append(dict(fam='slide', group='slide'))

    def link(self, a, b):
        d = np.linalg.norm(self.m.X[a]-self.m.X[b])
        if d > 0.01:
            self.add(a, b, 'iface')
        elif d > 1e-9 or a != b:
            # near-coincident nodes: a rigid 6-dof spring, not a 40-micron beam (its 12EI/L^3 ~ 1e24 wrecked the conditioning)
            self.m.spring(a, b, [1.0e12]*6, group='iface'); self.meta.append(dict(fam='iface', group='iface'))

    def connect(self, body_node, struct_node, k6, tag):
        """Body-side node coincident with the structure node, rigid arm from the body node, spring with the mount's releases."""
        q = self.m.node(self.m.X[struct_node]); self.link(body_node, q)
        self.m.spring(q, struct_node, k6, group=tag); self.meta.append(dict(fam='mount', group=tag))
        return q

    def place(self, bodies):
        """Create the body nodes once (topology is fixed through the depletion history; attach() only changes masses)."""
        self.bnodes = {}; self.vchain = {}
        for b in bodies:
            k = b['kind']
            if k == 'vessel':
                vid = b['vid']
                if vid in self.vchain:
                    continue
                n = 8; L = b['x1']-b['x0']; xs = [b['x0']+L*(i+0.5)/n for i in range(n)]
                ch = [self.m.node(self.p(x, b['R'], b['az'])) for x in xs]
                aft = self.m.node(self.p(b['x0'], b['R'], b['az'])); fwd = self.m.node(self.p(b['x1'], b['R'], b['az']))
                chain = [aft]+ch+[fwd]
                if self.deck_kind == 'E':
                    # TD-E integral tank: the vessel wall is a structural tube (r = a), thickness >= the credited pressure-shell share
                    g = self.group('tankwall', None, f'-{vid[0]}')
                    mt = next(q['m'] for q in bodies if q['kind'] == 'vessel' and q['vid'] == vid and q['owner'] == 'tankage')
                    rho = mdl.mat('AL6061')['rho']; tc = TANKWALL_CREDIT*mt/(rho*2*math.pi*b['a']*L)
                    self.tw_credit = getattr(self, 'tw_credit', {}); self.tw_credit[vid] = dict(t=tc, m_kg=TANKWALL_CREDIT*mt)
                    if g not in self.sec:
                        self.sec[g] = dict(r=b['a'], t=max(tc, 0.004), mat='AL6061', fam='tankwall', rmax=b['a'], tmin=tc)
                    for i in range(len(chain)-1):
                        self.add(chain[i], chain[i+1], 'tankwall', extra=f'-{vid[0]}')
                else:
                    for i in range(len(chain)-1):
                        self.link(chain[i], chain[i+1])
                for s in self.skirt_struct[vid]:
                    self.connect(aft, s, K_SKIRT, 'skirt')
                for g in self.guide_struct[vid]:
                    self.connect(fwd, g, K_FWD_E if self.deck_kind == 'E' else K_GUIDE, 'guide')
                if self.deck_kind == 'D':
                    for f, near in self.saddle_pts[vid]:
                        nd = ch[min(range(n), key=lambda i: abs(xs[i]-(b['x0']+f*L)))]
                        for q in near:
                            self.connect(nd, q, K_SADDLE, 'saddle')
                self.vchain[vid] = dict(nodes=ch, xs=xs, L=L)
            elif k == 'rotor':
                tag = b['ring']
                if ('rotor', tag) in self.bnodes:
                    continue
                xc = RING_X[0] if tag == 'A' else RING_X[1]
                n = self.m.node((xc, 0.0, 0.0)); self.connect(n, self.sp(xc), K_BEARING, 'bearing'); self.bnodes[('rotor', tag)] = n
            elif k == 'unit':
                n = self.m.node(b['c']); self.bnodes[b['name']] = n
                for mt in b.get('mounts', []):
                    s = self.nearest_node(np.array(self.p(mt['x'], mt.get('r', 3.0), mt.get('az', 0.0))))
                    self.connect(n, s, K_ANCHOR if mt['type'] == 'anchor' else K_SLIDE, mt['type'])
            elif k in ('brow',):
                n = self.m.node(b['c']); self.bnodes[b['name']] = n
                for s in self.brow_nodes:
                    self.link(n, s)
            elif k == 'drive':
                n = self.m.node(b['c']); self.bnodes[b['name']] = n
                for s in self.noz:
                    self.link(n, s)
            elif k in ('blade', 'blade1', 'line', 'lump', 'aftvessel'):
                self.bnodes[b['name']] = self.slices(b)

    def nearest_node(self, q, pool=None):
        pool = pool if pool is not None else [n for ring in self.station_nodes.values() for n in ring.values()] + \
            [n for ring in self.keel_nodes.values() for n in ring.values()]
        return min(pool, key=lambda n: np.linalg.norm(self.m.X[n]-q))

    def slices(self, b):
        """Slice a distributed body along X at its radius and azimuths; each slice is a lump on a rigid arm to the nearest frame node
        at the same azimuth (cage) or keel node (forward). Axisymmetric lines sit on the frame ring (rack hard-points)."""
        k = b['kind']
        if k in ('lump', 'blade1'):
            x = b.get('x', (b['c'][0], b['c'][0])); segs = [(0.5*(x[0]+x[1]), [tuple(b['c'][1:])])]
        else:
            x0, x1 = b['x']; n = max(1, int(math.ceil((x1-x0)/self.slice_m)))
            xs = [x0+(x1-x0)*(i+0.5)/n for i in range(n)]
            if k in ('blade', 'aftvessel'):
                azs = b['az'] if isinstance(b['az'], (list, tuple)) else (b['az'],)
                segs = [(x, [tuple(np.array(self.p(0, b['r'], a))[1:]) for a in azs]) for x in xs]
            else:
                segs = [(x, None) for x in xs]
        out = []
        for x, yz in segs:
            if yz is None:
                ns = self.frame_ring(x); out.append(('ring', x, ns))
                continue
            row = []
            for y, z in yz:
                q = np.array([x, y, z]); n = self.m.node(q); s = self.nearest_node(q, self.attach_pool(x)); self.link(n, s); row.append(n)
            out.append(('lumps', x, row))
        return out

    def attach_pool(self, x):
        if x < X_RING:
            return self.noz
        if x <= X_CAGE_END+0.5:
            k = min(self.xs, key=lambda q: abs(q-x)); return list(self.station_nodes[k].values())
        if x < self.x_deck_aft:
            return [self.sp(x)]
        k = min(self.kx, key=lambda q: abs(q-x)); return list(self.keel_nodes[k].values())

    def frame_ring(self, x):
        if x < X_RING:
            return self.noz
        if x <= X_CAGE_END+0.5:
            k = min(self.xs, key=lambda q: abs(q-x)); return [self.station_nodes[k][a] for a in self.rail_az()]
        if x < self.x_deck_aft:
            return [self.sp(x)]
        k = min(self.kx, key=lambda q: abs(q-x)); return list(self.keel_nodes[k].values())

    def attach(self, bodies):
        """Assign every body's mass and inertia to its nodes (masses only; topology from place())."""
        m = self.m; m.pm = {}; m.pi = {}
        for b in bodies:
            k = b['kind']
            if k == 'vessel':
                ch = self.vchain[b['vid']]; n = len(ch['nodes']); dx = ch['L']/n
                if b['owner'] == 'tankage':
                    # TD-E: the credited wall share is carried by the tankwall members' own mass, not twice
                    f = 1.0-(self.tw_credit[b['vid']]['m_kg']/b['m'] if self.deck_kind == 'E' else 0.0)
                    for nd in ch['nodes']:
                        self._put(nd, f*b['m']/n, f*b['I']/n, slice_L=0.0)
                else:
                    Lq = b.get('level_m', ch['L']); full = Lq/dx; rest = b['m']
                    for i, nd in enumerate(ch['nodes']):
                        f = min(1.0, max(0.0, full-i))
                        if f <= 0:
                            break
                        mi = b['m']*f*dx/max(Lq, 1e-9); rest -= mi
                        a = b['a']; Ii = np.diag([mi*a*a/2, mi*(a*a/4+(f*dx)**2/12), mi*(a*a/4+(f*dx)**2/12)])
                        # slice centre offset inside a partly filled slice is carried by the lumped node (half-slice error, reported)
                        self._put(nd, mi, Ii)
            elif k == 'rotor':
                self._put(self.bnodes[('rotor', b['ring'])], b['m'], b['I'])
            elif k in ('unit', 'brow', 'drive'):
                self._put(self.bnodes[b['name']], b['m'], b['I'])
            else:
                segs = self.bnodes[b['name']]; ns = sum(len(s[2]) if s[0] == 'lumps' else 1 for s in segs); mm = b['m']/ns
                for typ, x, nodes in segs:
                    if typ == 'lumps':
                        for nd in nodes:
                            self._put(nd, mm, b['I']*mm/max(b['m'], 1e-9) if k in ('lump', 'blade1') else np.zeros((3, 3)))
                    else:
                        for nd in nodes:
                            self._put(nd, mm/len(nodes), np.zeros((3, 3)))
        return 0.0

    def _put(self, n, mass, J, slice_L=None):
        if mass <= 0:
            return
        self.m.mass(n, mass)
        if J is not None and np.any(J):
            self.m.inertia(n, J)

    def mass_check(self, bodies):
        """Mass, centre and inertia tensor of the FE representation (point masses + rotary inertia of the body nodes, structure
        excluded) against the source bodies."""
        import c11
        M0, c0, J0 = c11.totals(bodies)
        X = np.array(self.m.X); mt = np.zeros(len(X))
        for n, v in self.m.pm.items():
            mt[n] = v
        M1 = mt.sum(); c1 = (X*mt[:, None]).sum(0)/M1; J1 = np.zeros((3, 3))
        for n in np.where(mt > 0)[0]:
            d = X[n]-c1; J1 += mt[n]*(np.dot(d, d)*np.eye(3)-np.outer(d, d))
        for n, J in self.m.pi.items():
            J1 += J
        return dict(mass_t=(M0/1e3, M1/1e3), cg=(c0.tolist(), c1.tolist()), dcg_m=float(np.linalg.norm(c1-c0)),
                    J_src=J0.diagonal().tolist(), J_fe=J1.diagonal().tolist(), dJ_rel=(np.abs(J1-J0).max()/np.abs(J0).max()))
