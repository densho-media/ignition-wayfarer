class_name WfExcursionBuild
extends RefCounted
## Colliders and the station whitebox of the excursion (EXC-001), built from the rig's `dynamics.stages` only: every surface is a clear surface of
## the shared formulas (body_tour's approach: thin static slabs outside the free space, or a two-sided trimesh on it), never an imported mesh.
## All in index-pose coordinates, Godot axes; the host keeps the whole world in one collision layer that nothing else uses.

const SLAB := 0.2
const SIDES := 32

var world: Node3D
var layer := 1 << 9
var bodies := 0

func _init(w: Node3D, collision_layer: int) -> void:
	world = w
	layer = collision_layer

static func g(v: Array) -> Vector3:
	return Vector3(v[0], v[2], -v[1])

func body() -> StaticBody3D:
	var b := StaticBody3D.new()
	b.collision_layer = layer
	b.collision_mask = layer
	world.add_child(b)
	bodies += 1
	return b

func slab(pos: Vector3, bas: Basis, size: Vector3) -> StaticBody3D:
	var b := body()
	var cs := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = size
	cs.shape = box
	b.add_child(cs)
	b.transform = Transform3D(bas.orthonormalized(), pos)
	return b

func box(centre: Vector3, axes: Array, half: Vector3) -> StaticBody3D:
	return slab(centre, Basis(axes[0], axes[1], axes[2]), half * 2.0)

func trimesh(faces: PackedVector3Array) -> StaticBody3D:
	var b := body()
	var cs := CollisionShape3D.new()
	var sh := ConcavePolygonShape3D.new()
	sh.set_faces(faces)
	sh.backface_collision = true
	cs.shape = sh
	b.add_child(cs)
	return b

static func quad(f: PackedVector3Array, a: Vector3, b: Vector3, c: Vector3, d: Vector3) -> void:
	f.append_array([a, b, c, a, c, d])

## A cylinder about the ship axis (X) from x0 to x1, free inside: flats tangent outside r, with holes {c, n, r} cut out (body_tour._cyl_x).
func cyl_x(x0: float, x1: float, r: float, holes: Array) -> void:
	var n_flat := SIDES * 2
	var half := PI / n_flat
	for i in n_flat:
		var ang := TAU * i / n_flat
		var nrm := Vector3(0, cos(ang), sin(ang))
		var rc := r + SLAB * 0.5
		var width := 2.0 * r * tan(half) * 1.02
		var pieces := [[x0, x1]]
		for h in holes:
			var hn: Vector3 = h["n"]
			if nrm.dot(hn) <= 0.0:
				continue
			var b := r * nrm.cross(hn).length()
			if b >= float(h["r"]):
				continue
			var hw := sqrt(float(h["r"]) ** 2 - b * b)
			var lo: float = (h["c"] as Vector3).x - hw
			var hi: float = (h["c"] as Vector3).x + hw
			var next := []
			for q in pieces:
				if hi <= q[0] or lo >= q[1]:
					next.append(q)
					continue
				if lo > q[0]: next.append([q[0], lo])
				if hi < q[1]: next.append([hi, q[1]])
			pieces = next
		for q in pieces:
			if q[1] - q[0] < 1e-3:
				continue
			slab(Vector3((q[0] + q[1]) * 0.5, 0, 0) + nrm * rc, Basis(Vector3.RIGHT, nrm, Vector3.RIGHT.cross(nrm)), Vector3(q[1] - q[0], SLAB, width))

## The drum's inner wall (free outside r): flats inside r, the port hole cut out; the cut piece goes to `patch` (the closure while shut).
func cyl_x_out(x0: float, x1: float, r: float, holes: Array) -> void:
	var n_flat := SIDES * 2
	var half := PI / n_flat
	for i in n_flat:
		var ang := TAU * i / n_flat
		var nrm := Vector3(0, cos(ang), sin(ang))
		var rc := r * cos(half) - SLAB * 0.5
		var width := 2.0 * r * sin(half) * 1.02
		var pieces := [[x0, x1, null]]
		for h in holes:
			var hn: Vector3 = h["n"]
			if nrm.dot(hn) <= 0.0:
				continue
			var b := (rc + SLAB * 0.5) * nrm.cross(hn).length()
			if b >= float(h["r"]):
				continue
			var hw := sqrt(float(h["r"]) ** 2 - b * b)
			var lo: float = (h["c"] as Vector3).x - hw
			var hi: float = (h["c"] as Vector3).x + hw
			var next := []
			for q in pieces:
				if q[2] != null or hi <= q[0] or lo >= q[1]:
					next.append(q)
					continue
				if lo > q[0]: next.append([q[0], lo, null])
				next.append([maxf(lo, q[0]), minf(hi, q[1]), h["patch"]])
				if hi < q[1]: next.append([hi, q[1], null])
			pieces = next
		for q in pieces:
			if q[1] - q[0] < 1e-3:
				continue
			var sb := slab(Vector3((q[0] + q[1]) * 0.5, 0, 0) + nrm * rc, Basis(Vector3.RIGHT, nrm, Vector3.RIGHT.cross(nrm)), Vector3(q[1] - q[0], SLAB, width))
			if q[2] != null:
				(q[2] as Array).append(sb)

## A bore of radius r about the line c + n a (n not along X), its wall flats from a0(b) to a1(b), b the flat's offset across the bore.
func bore(c: Vector3, n: Vector3, r: float, a0: Callable, a1: Callable, patch = null) -> void:
	var side := n.cross(Vector3.RIGHT).normalized()
	for i in SIDES:
		var psi := TAU * i / SIDES
		var e := Vector3.RIGHT * cos(psi) + side * sin(psi)
		var b := r * sin(psi)
		var lo: float = a0.call(b, e)
		var hi: float = a1.call(b, e)
		if hi - lo < 1e-3:
			continue
		var sb := slab(c + e * (r + SLAB * 0.5) + n * (lo + hi) * 0.5, Basis(n, e, n.cross(e)), Vector3(hi - lo, SLAB, 2.0 * r * tan(PI / SIDES) * 1.02))
		if patch != null:
			(patch as Array).append(sb)

## An end wall across a bore: the annulus between r_in and r_out in the plane at c + n a, as flats (a disc when r_in is 0); on the side `side`.
func annulus(c: Vector3, n: Vector3, a: float, r_in: float, r_out: float, side: float) -> void:
	var u := n.cross(Vector3.RIGHT).normalized()
	var v := n.cross(u)
	var k := SIDES * 2
	for i in k:
		var psi := TAU * (i + 0.5) / k
		var e := u * cos(psi) + v * sin(psi)
		var t := e.cross(n)
		var w := 2.0 * r_out * tan(PI / k) * 1.04
		slab(c + n * (a + side * SLAB * 0.5) + e * (r_in + r_out) * 0.5, Basis(e, n, t), Vector3(r_out - r_in, SLAB, w))

## A closure across a bore at c + n a: one slab disc of radius r (enabled while shut).
func disc(c: Vector3, n: Vector3, a: float, r: float, thick := 0.05) -> StaticBody3D:
	var u := n.cross(Vector3.RIGHT).normalized()
	return slab(c + n * a, Basis(u, n, u.cross(n)), Vector3(2.0 * r, thick, 2.0 * r))

## Mitered tube legs from point i to i+1 (body_tour._mitered).
func mitered(pts: Array, miters: Array, r: float, first: int) -> void:
	for i in range(first, pts.size() - 1):
		var p: Vector3 = pts[i]
		var q: Vector3 = pts[i + 1]
		var d := (q - p).normalized()
		var u := d.cross(Vector3.RIGHT if absf(d.x) < 0.9 else Vector3.UP).normalized()
		var v := d.cross(u)
		for k in SIDES:
			var psi := TAU * k / SIDES
			var e := u * cos(psi) + v * sin(psi)
			var m0: Vector3 = miters[i]
			var t0 := -(e * r).dot(m0) / d.dot(m0)
			var t1 := (q - p).length()
			if i + 1 < miters.size():
				var m1: Vector3 = miters[i + 1]
				t1 = (q - p - e * r).dot(m1) / d.dot(m1)
			slab(p + e * (r + SLAB * 0.5) + d * (t0 + t1) * 0.5, Basis(d, e, d.cross(e)), Vector3(t1 - t0, SLAB, 2.0 * r * tan(PI / SIDES) * 1.02))

# ---- stages -------------------------------------------------------------------------------------------------------------------------------------

## The trunk with every branch: the open ones (`open`: the primary connector and the spine ports) are holes; the others are closed 0.6 m stubs.
func trunk(t: Dictionary, open: Array) -> void:
	var a := g(t["axis_m"][0])
	var b := g(t["axis_m"][1])
	var r: float = t["clear_radius_m"]
	var holes := []
	for o in t["openings"]:
		var th := deg_to_rad(float(o["theta_deg"]))
		var n := Vector3(0, sin(th), -cos(th))          # Blender (0, cos, sin) -> Godot (0, sin, -cos)
		var c := Vector3(float(o["x_m"]), 0, 0)
		holes.append({"c": c, "n": n, "r": float(o["radius_m"])})
		if not str(o["name"]) in open:
			var rr: float = o["radius_m"]
			bore(c, n, rr, func(bb, _e): return sqrt(maxf(r * r - bb * bb, 0.0)), func(_b, _e): return r + 0.6)
			disc(c, n, r + 0.6 + SLAB * 0.5, rr + SLAB)
	cyl_x(minf(a.x, b.x), maxf(a.x, b.x), r, holes)
	var side := 2.0 * r / cos(PI / SIDES) + 2.0 * SLAB
	for xe in [minf(a.x, b.x) - SLAB * 0.5, maxf(a.x, b.x) + SLAB * 0.5]:
		slab(Vector3(xe, 0, 0), Basis.IDENTITY, Vector3(SLAB, side, side))

## The boarding area: coaxial bores about the port axis and their end walls (station.bores), the inboard neck opening from the trunk wall.
func boarding(b: Dictionary, trunk_r: float) -> Dictionary:
	var c := g(b["axis"]["origin_m"])
	var n := g(b["axis"]["radial"]).normalized()
	for q in b["bores"]:
		var a0: float = q["a_m"][0]
		var a1: float = q["a_m"][1]
		var r: float = q["clear_radius_m"]
		if q["name"] == "inboard_neck":
			bore(c, n, r, func(bb, _e): return sqrt(maxf(trunk_r * trunk_r - bb * bb, 0.0)), func(_b, _e): return a1)
		else:
			bore(c, n, r, func(_b, _e): return a0, func(_b, _e): return a1)
	for q in b["ends"]:
		var a: float = q["a_m"]
		var inner: float = q["r_in_m"]
		var outer: float = q["r_out_m"]
		# the wall faces the larger bore: outboard ends of a room lie beyond it (+), inboard ends below it (-)
		var sgn := 1.0 if str(q["name"]).ends_with("_end") or str(q["name"]).ends_with("outboard") else -1.0
		annulus(c, n, a, inner, outer, sgn)
	var hatches := {}
	for h in b["hatches"]:
		hatches[h["id"]] = disc(c, n, float(h["a"]), 0.82)
	return hatches

## A ring's access: the spine port's bore, the drum annulus with the port gate and drum door as patches, the door's bore (or ring B's neck) and
## the mitered tube to the run's end.
func access(a: Dictionary) -> Dictionary:
	var port_patch := []
	var door_patch := []
	var tr: float = a["trunk"]["clear_radius_m"]
	var c := g(a["port"]["centre_m"])
	var n := g(a["port"]["radial"]).normalized()
	var pc: float = a["port"]["clear_radius_m"]
	var dx: Array = a["drum"]["x_m"]
	var r0: float = a["drum"]["inner_radius_m"]
	var rr: float = a["drum"]["outer_radius_m"]
	bore(c, n, pc, func(bb, _e): return sqrt(maxf(tr * tr - bb * bb, 0.0)), func(bb, _e): return sqrt(maxf(r0 * r0 - bb * bb, 0.0)))
	cyl_x_out(float(dx[0]), float(dx[1]), r0, [{"c": c, "n": n, "r": pc, "patch": port_patch}])
	var holes := [{"c": c, "n": n, "r": pc, "patch": door_patch}]
	var n_flat := SIDES * 2
	# outer wall (free inside): with the door's hole; the cut piece is the door
	for i in n_flat:
		var ang := TAU * i / n_flat
		var nrm := Vector3(0, cos(ang), sin(ang))
		var rc := rr + SLAB * 0.5
		var width := 2.0 * rr * tan(PI / n_flat) * 1.02
		var pieces := [[float(dx[0]), float(dx[1]), null]]
		for h in holes:
			if nrm.dot(h["n"]) <= 0.0:
				continue
			var bb := rr * nrm.cross(h["n"]).length()
			if bb >= float(h["r"]):
				continue
			var hw := sqrt(float(h["r"]) ** 2 - bb * bb)
			var lo: float = (h["c"] as Vector3).x - hw
			var hi: float = (h["c"] as Vector3).x + hw
			var next := []
			for q in pieces:
				if q[2] != null or hi <= q[0] or lo >= q[1]:
					next.append(q)
					continue
				if lo > q[0]: next.append([q[0], lo, null])
				next.append([maxf(lo, q[0]), minf(hi, q[1]), h["patch"]])
				if hi < q[1]: next.append([hi, q[1], null])
			pieces = next
		for q in pieces:
			if q[1] - q[0] < 1e-3:
				continue
			var sb := slab(Vector3((q[0] + q[1]) * 0.5, 0, 0) + nrm * rc, Basis(Vector3.RIGHT, nrm, Vector3.RIGHT.cross(nrm)), Vector3(q[1] - q[0], SLAB, width))
			if q[2] != null:
				(q[2] as Array).append(sb)
	for xe in [float(dx[0]) - SLAB * 0.5, float(dx[1]) + SLAB * 0.5]:
		for i in n_flat:
			var ang := TAU * i / n_flat
			var nrm := Vector3(0, cos(ang), sin(ang))
			slab(Vector3(xe, 0, 0) + nrm * (r0 + rr) * 0.5, Basis(Vector3.RIGHT, nrm, Vector3.RIGHT.cross(nrm)), Vector3(SLAB, rr - r0, 2.0 * rr * tan(PI / n_flat) * 1.02))
	var pts := []
	for q in a["tube"]["points_m"]:
		pts.append(g(q))
	var mit := []
	for m in a["tube"]["miters"]:
		mit.append(g(m))
	var rt: float = a["tube"]["clear_radius_m"]
	var j1: Vector3 = pts[1]
	var m1: Vector3 = mit[1]
	if a.has("neck"):
		# ring B: the hatch-sized neck from the drum's outer wall to the bulkhead's tube side, then the tube's bore
		var nr: float = a["neck"]["clear_radius_m"]
		var top: float = a["neck"]["top_m"]
		bore(c, n, nr, func(bb, _e): return sqrt(maxf(rr * rr - bb * bb, 0.0)), func(_b, _e): return top)
		annulus(c, n, top, nr, rt, -1.0)
		bore(c, n, rt, func(_b, _e): return top, func(_b, e): return (j1 - c - e * rt).dot(m1) / n.dot(m1))
	else:
		bore(c, n, rt, func(bb, _e): return sqrt(maxf(rr * rr - bb * bb, 0.0)), func(_b, e): return (j1 - c - e * rt).dot(m1) / n.dot(m1))
	mitered(pts, mit, rt, 1)
	return {"port": port_patch, "door": door_patch}

## A ring's circuit: the sectors' boxes (deck, overhead, bulkheads, blocks, side walls), the corridors' clear surfaces as one trimesh per fill,
## and a closed-leaf slab per door. Returns {door id: slab}.
func circuit(c: Dictionary) -> Dictionary:
	for q in c["boxes"]:
		box(g(q["centre_m"]), [g(q["axes"][0]), g(q["axes"][1]), g(q["axes"][2])], Vector3(q["half_m"][0], q["half_m"][1], q["half_m"][2]))
	var cx: float = c["centre_x_m"]
	var ph: float = c["phase_rad"]
	var step := deg_to_rad(float(c["step_deg"]))
	var P := func(u: float, r: float, t: float) -> Vector3: return Vector3(cx + u, r * sin(t + ph), -r * cos(t + ph))
	var per_fill := {}
	var segs: Array = c["segments"]
	for k in segs.size():
		var q: Dictionary = segs[k]
		var f: PackedVector3Array = per_fill.get(q["fill"], PackedVector3Array())
		var t0: float = q["t_rad"][0]
		var t1: float = q["t_rad"][1]
		var u0: float = q["u_m"][0]
		var u1: float = q["u_m"][1]
		var rt: float = q["r_m"][0]
		var rf: float = q["r_m"][1]
		var n := maxi(1, ceili((t1 - t0) / step))
		for i in n:
			var a := t0 + (t1 - t0) * i / n
			var b := t0 + (t1 - t0) * (i + 1) / n
			quad(f, P.call(u0, rf, a), P.call(u1, rf, a), P.call(u1, rf, b), P.call(u0, rf, b))
			quad(f, P.call(u0, rt, a), P.call(u1, rt, a), P.call(u1, rt, b), P.call(u0, rt, b))
			quad(f, P.call(u0, rt, a), P.call(u0, rf, a), P.call(u0, rf, b), P.call(u0, rt, b))
			quad(f, P.call(u1, rt, a), P.call(u1, rf, a), P.call(u1, rf, b), P.call(u1, rt, b))
		# step faces where this segment meets a narrower neighbour (a corridor run against a door passage)
		for nb in [k - 1, k + 1]:
			if nb < 0 or nb >= segs.size() or segs[nb]["fill"] != q["fill"]:
				continue
			var o: Dictionary = segs[nb]
			var t: float = t0 if nb == k - 1 else t1
			var ou0: float = o["u_m"][0]
			var ou1: float = o["u_m"][1]
			var ort: float = o["r_m"][0]
			if ou0 > u0 + 1e-6:
				quad(f, P.call(u0, rt, t), P.call(ou0, rt, t), P.call(ou0, rf, t), P.call(u0, rf, t))
			if ou1 < u1 - 1e-6:
				quad(f, P.call(ou1, rt, t), P.call(u1, rt, t), P.call(u1, rf, t), P.call(ou1, rf, t))
			if ort > rt + 1e-6:
				quad(f, P.call(maxf(u0, ou0), rt, t), P.call(minf(u1, ou1), rt, t), P.call(minf(u1, ou1), ort, t), P.call(maxf(u0, ou0), ort, t))
		per_fill[q["fill"]] = f
	for k in per_fill:
		trimesh(per_fill[k])
	var doors := {}
	for d in c["doors"]:
		doors[d["id"]] = box(g(d["centre_m"]), [g(d["axes"][0]), g(d["axes"][1]), g(d["axes"][2])],
			Vector3(float(d["half_m"][0]) + 0.05, float(d["half_m"][1]) + 0.05, float(d["half_m"][2])))
	return doors

static func set_enabled(b: StaticBody3D, on: bool) -> void:
	for ch in b.get_children():
		if ch is CollisionShape3D:
			ch.set_deferred("disabled", not on)
