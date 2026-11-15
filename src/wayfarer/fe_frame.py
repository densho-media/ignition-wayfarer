"""Small 3D frame finite-element solver for first-order structural screens (Vertex Engine 1.2). Pure, standard library only.

Euler-Bernoulli beam elements (12 DOF: three translations and three rotations per node), optional rigid end offsets (an element end can
hang on a master node at a fixed offset, which models a rigid hub or engine body as one node), linear springs to ground, and fixed nodes.
The global stiffness is assembled sparsely, nodes are ordered by reverse Cuthill-McKee and solved by a skyline (profile) Cholesky
factorisation. Results: nodal displacements, support reactions and element end forces in the element frame.

It is a screening tool: linear, small displacement, no shear deformation, no joint flexibility, no buckling or contact. Its answers are
checked against closed forms in tests/test_vertex_structure.py (cantilever, ring under equal radial loads) before they size anything.
"""
import math


def tube(r_out, solid_fraction):
    """Thin-walled tube section with the outer radius r_out and a cross-section equal to solid_fraction of the full circle (the engine's
    mass model uses the same fraction): A, Iy = Iz, J and the outer radius."""
    ri = r_out*math.sqrt(max(0.0, 1.0-solid_fraction))
    A = math.pi*(r_out**2-ri**2); I = math.pi/4*(r_out**4-ri**4)
    return dict(A=A, Iy=I, Iz=I, J=2*I, c=r_out, r_out=r_out, r_in=ri)


def rigid():
    return dict(A=1.0, Iy=1.0, Iz=1.0, J=1.0, c=1.0, rigid=True)


def _sub(a, b): return [a[i]-b[i] for i in range(3)]
def _dot(a, b): return sum(a[i]*b[i] for i in range(3))
def _cross(a, b): return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]
def _unit(a):
    L = math.sqrt(_dot(a, a)); return [v/L for v in a]


class Frame:
    def __init__(self):
        self.nodes = []            # [x, y, z]
        self.elements = []         # dict(n1, n2, o1, o2, sec, E, G, ref, name)
        self.springs = []          # (node, dof, k)
        self.fixed = set()         # nodes with all six DOF fixed
        self.loads = {}            # node -> [Fx, Fy, Fz, Mx, My, Mz]

    def node(self, p):
        self.nodes.append([float(v) for v in p]); return len(self.nodes)-1

    def beam(self, n1, n2, sec, E, G, name='', o1=None, o2=None, ref=None):
        """Element from node n1 (+ offset o1) to node n2 (+ offset o2); the offsets are rigid arms from the nodes."""
        self.elements.append(dict(n1=n1, n2=n2, o1=list(o1 or (0, 0, 0)), o2=list(o2 or (0, 0, 0)), sec=sec, E=E, G=G, ref=ref, name=name))
        return len(self.elements)-1

    def spring(self, n, dof, k):
        self.springs.append((n, dof, k))

    def fix(self, n):
        self.fixed.add(n)

    def load(self, n, F=(0, 0, 0), M=(0, 0, 0)):
        L = self.loads.setdefault(n, [0.0]*6)
        for i in range(3):
            L[i] += F[i]; L[3+i] += M[i]

    # ---------- element matrices --------------------------------------------------------------------------------------------------
    def _geometry(self, e):
        a = [self.nodes[e['n1']][i]+e['o1'][i] for i in range(3)]
        b = [self.nodes[e['n2']][i]+e['o2'][i] for i in range(3)]
        d = _sub(b, a); L = math.sqrt(_dot(d, d)); ex = [v/L for v in d]
        ref = e['ref'] or ([0.0, 0.0, 1.0] if abs(ex[2]) < 0.9 else [0.0, 1.0, 0.0])
        ey = _unit(_cross(ref, ex)); ez = _cross(ex, ey)
        return L, [ex, ey, ez]

    @staticmethod
    def _local(L, sec, E, G):
        A, Iy, Iz, J = sec['A'], sec['Iy'], sec['Iz'], sec['J']
        k = [[0.0]*12 for _ in range(12)]
        def put(i, j, v):
            k[i][j] += v
            if i != j:
                k[j][i] += v
        ea, gj = E*A/L, G*J/L
        put(0, 0, ea); put(6, 6, ea); put(0, 6, -ea)
        put(3, 3, gj); put(9, 9, gj); put(3, 9, -gj)
        for (v, th, I, s) in ((1, 5, Iz, 1), (2, 4, Iy, -1)):        # bending about local z (v, rz) and about local y (w, ry)
            a12, a6, a4, a2 = 12*E*I/L**3, 6*E*I/L**2, 4*E*I/L, 2*E*I/L
            put(v, v, a12); put(v+6, v+6, a12); put(v, v+6, -a12)
            put(v, th, s*a6); put(v, th+6, s*a6); put(v+6, th, -s*a6); put(v+6, th+6, -s*a6)
            put(th, th, a4); put(th+6, th+6, a4); put(th, th+6, a2)
        return k

    def _transform(self, e, R):
        """12 x 12 map from the two master nodes' global DOF to the element's local end DOF (rotation and rigid offsets)."""
        T = [[0.0]*12 for _ in range(12)]
        for end, o in ((0, e['o1']), (1, e['o2'])):
            # end translation = u_master + theta_master x o  ->  u_end = u - o x theta
            sk = [[0.0, -o[2], o[1]], [o[2], 0.0, -o[0]], [-o[1], o[0], 0.0]]     # skew(o): skew(o) theta = o x theta
            for i in range(3):
                for j in range(3):
                    T[6*end+i][6*end+j] = R[i][j]
                    T[6*end+3+i][6*end+3+j] = R[i][j]
                    T[6*end+i][6*end+3+j] = -sum(R[i][k]*sk[k][j] for k in range(3))
        return T

    def _element(self, e):
        L, R = self._geometry(e)
        sec = e['sec']; E, G = e['E'], e['G']
        if sec.get('rigid'):
            E, G, sec = 1e15, 4e14, dict(A=1.0, Iy=1.0, Iz=1.0, J=1.0)
        kl = self._local(L, sec, E, G); T = self._transform(e, R)
        KT = [[sum(kl[i][m]*T[m][j] for m in range(12)) for j in range(12)] for i in range(12)]
        Kg = [[sum(T[m][i]*KT[m][j] for m in range(12)) for j in range(12)] for i in range(12)]
        return L, R, kl, T, Kg

    # ---------- solve -------------------------------------------------------------------------------------------------------------
    def _order(self):
        free = [n for n in range(len(self.nodes)) if n not in self.fixed]
        adj = {n: set() for n in free}
        for e in self.elements:
            a, b = e['n1'], e['n2']
            if a in adj and b in adj and a != b:
                adj[a].add(b); adj[b].add(a)
        # reverse Cuthill-McKee per component, highest-degree hubs last
        order, seen = [], set()
        for start in sorted(free, key=lambda n: len(adj[n])):
            if start in seen:
                continue
            q = [start]; seen.add(start); comp = []
            while q:
                n = q.pop(0); comp.append(n)
                for m in sorted(adj[n] - seen, key=lambda m: len(adj[m])):
                    seen.add(m); q.append(m)
            order += comp
        order.reverse()
        hubs = [n for n in order if len(adj[n]) > 12]
        return [n for n in order if n not in hubs]+hubs

    def solve(self):
        order = self._order(); index = {n: i for i, n in enumerate(order)}
        N = 6*len(order)
        rows = [dict() for _ in range(N)]             # lower triangle, rows[i][j] with j <= i
        def add(i, j, v):
            if j > i:
                i, j = j, i
            rows[i][j] = rows[i].get(j, 0.0)+v
        cache = []
        for e in self.elements:
            L, R, kl, T, Kg = self._element(e); cache.append((L, R, kl, T))
            dofs = []
            for n in (e['n1'], e['n2']):
                dofs += [6*index[n]+d if n in index else None for d in range(6)]
            for i in range(12):
                if dofs[i] is None:
                    continue
                for j in range(12):
                    if dofs[j] is not None and dofs[j] <= dofs[i] and Kg[i][j] != 0.0:
                        add(dofs[i], dofs[j], Kg[i][j])
        for n, d, k in self.springs:
            if n in index:
                add(6*index[n]+d, 6*index[n]+d, k)
        F = [0.0]*N
        for n, L_ in self.loads.items():
            if n in index:
                for d in range(6):
                    F[6*index[n]+d] += L_[d]
        # skyline Cholesky
        first = [min(r) if r else i for i, r in enumerate(rows)]
        Lm = [None]*N
        for i in range(N):
            f = first[i]; row = [0.0]*(i-f+1)
            for j, v in rows[i].items():
                row[j-f] = v
            for j in range(f, i+1):
                s = row[j-f]
                Lj, fj = (Lm[j], first[j]) if j < i else (row, f)
                lo = max(f, fj)
                for k in range(lo, j):
                    s -= row[k-f]*Lj[k-fj]
                if j == i:
                    if s <= 0.0:
                        raise ValueError('stiffness matrix is not positive definite (mechanism or unsupported rigid-body mode)')
                    row[j-f] = math.sqrt(s)
                else:
                    row[j-f] = s/Lm[j][j-first[j]]
            Lm[i] = row
        y = [0.0]*N
        for i in range(N):
            f = first[i]; s = F[i]
            for k in range(f, i):
                s -= Lm[i][k-f]*y[k]
            y[i] = s/Lm[i][i-f]
        x = y[:]
        for i in range(N-1, -1, -1):
            f = first[i]; x[i] /= Lm[i][i-f]
            for k in range(f, i):
                x[k] -= Lm[i][k-f]*x[i]
        u = {n: x[6*index[n]:6*index[n]+6] if n in index else [0.0]*6 for n in range(len(self.nodes))}
        # element forces (local frame, at both ends) and reactions at fixed nodes
        forces, reactions = [], {n: [0.0]*6 for n in self.fixed}
        for e, (L, R, kl, T) in zip(self.elements, cache):
            ue = u[e['n1']]+u[e['n2']]
            ul = [sum(T[i][j]*ue[j] for j in range(12)) for i in range(12)]
            fl = [sum(kl[i][j]*ul[j] for j in range(12)) for i in range(12)]
            forces.append(dict(name=e['name'], L=L, N=fl[6], Vy=fl[7], Vz=fl[8], T=fl[9],
                               My=max(abs(fl[4]), abs(fl[10])), Mz=max(abs(fl[5]), abs(fl[11]))))
            if e['n1'] in reactions or e['n2'] in reactions:
                fg = [sum(T[m][i]*fl[m] for m in range(12)) for i in range(12)]
                for end, n in ((0, e['n1']), (1, e['n2'])):
                    if n in reactions:
                        for d in range(6):
                            reactions[n][d] += fg[6*end+d]
        return dict(u=u, forces=forces, reactions=reactions, dof=N)


def stress(f, sec):
    """Peak combined normal stress of an element (axial plus resultant bending at the outer fibre), signed by the axial force, Pa."""
    sb = math.hypot(f['My'], f['Mz'])*sec['c']/sec['Iy']
    return abs(f['N'])/sec['A']+sb
