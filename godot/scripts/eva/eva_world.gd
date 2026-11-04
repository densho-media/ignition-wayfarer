class_name WfEvaWorld
extends Node3D
## The EVA world of EVA Operations (EVA-OPS-001): colliders, holds, hazards and the equipment station, built from the package only
## (forward_shield.py and eva_route.py shared formulas, rig proxies), never from the visual mesh. Godot axes: ship axis +X, a point at
## radius r and angle phi about it is (x, r cos phi, r sin phi). Everything here is static in the ship frame.

const LAYER_WORLD := 1
const SEG := 64

var pkg: Dictionary
var face_prof: Array = []           # [r, x_face, x_skin_aft]
var holds: Array = []               # {id, p: Vector3, kind, label}
var hazards: Array = []
var station := {}                   # rack: p, cartridges left; socket p
var hatch := Vector3.ZERO
var rail_up := Vector3.UP
var shield_r := 45.0
var _mat_rail: StandardMaterial3D
var _mat_hold: StandardMaterial3D
var show_surfaces := false          # no ship GLB in the package: draw the colliders themselves (grey proxies) so there is something to see
var _mat_proxy: StandardMaterial3D

func build(p: Dictionary) -> void:
	pkg = p
	var sh: Dictionary = pkg["ship"]
	var s: Dictionary = sh["shield"]
	var rt: Dictionary = sh["route"]
	face_prof = s["face_profile_r_xface_xskinaft"]
	shield_r = float(s["radius_m"])
	_mat_rail = _mat(Color(0.95, 0.78, 0.15))
	_mat_hold = _mat(Color(1.0, 0.85, 0.2))
	# ---- the hull collar (eva_route.collider: radius samples of the shared hull formulas) and the hub up to the Brow skin
	var col: Dictionary = rt["collider"]
	var prof: Array = []
	for smp in col["samples"]:
		prof.append(Vector2(float(smp[0]), float(smp[1])))
	var hub_x0: float = prof[prof.size() - 1].x
	prof.append(Vector2(hub_x0 + 0.001, float(s["hub_r"])))
	prof.append(Vector2(float(face_prof[0][2]), float(s["hub_r"])))
	_static("HULL_COLLAR", _lathe_x(prof, false))
	# ---- the Brow: front (ram) face, aft skin face, rim band
	var front: Array = []
	var aft: Array = []
	for row in face_prof:
		front.append(Vector2(float(row[1]), float(row[0])))
		aft.append(Vector2(float(row[2]), float(row[0])))
	_static("BROW_FRONT", _disc_x(front))
	_static("BROW_AFT", _disc_x(aft))
	var last: Array = face_prof[face_prof.size() - 1]
	_static("BROW_RIM", _lathe_x([Vector2(float(last[2]), shield_r), Vector2(float(last[1]), shield_r)], false))
	# ---- truss members behind the skin (capsules on the member centre lines)
	var tr := StaticBody3D.new()
	tr.name = "BROW_TRUSS"
	tr.collision_layer = LAYER_WORLD
	tr.collision_mask = 0
	var mr := float(s["truss_member_radius_m"])
	for sg in s["truss_segments"]:
		var a := WfEvaPkg.v(sg[0])
		var b := WfEvaPkg.v(sg[1])
		var L := a.distance_to(b)
		if L < 0.05:
			continue
		var cs := CollisionShape3D.new()
		var cap := CapsuleShape3D.new()
		cap.radius = mr
		cap.height = L + 2.0 * mr
		cs.shape = cap
		var y := (b - a) / L
		var x := y.cross(Vector3.RIGHT if absf(y.x) < 0.9 else Vector3.UP).normalized()
		cs.transform = Transform3D(Basis(x, y, x.cross(y)), (a + b) * 0.5)
		tr.add_child(cs)
		if show_surfaces:
			var mi := MeshInstance3D.new()
			var cm := CylinderMesh.new()
			cm.top_radius = mr
			cm.bottom_radius = mr
			cm.height = L
			cm.radial_segments = 6
			cm.rings = 1
			mi.mesh = cm
			mi.material_override = _proxy_mat()
			mi.transform = cs.transform
			tr.add_child(mi)
	add_child(tr)
	# ---- the Dust Lance (keep-out, but solid)
	var L_: Dictionary = s["lance"]
	_static("DUST_LANCE", _lathe_x([Vector2(float(L_["x0"]), float(L_["r0"])), Vector2(float(L_["x1"]), float(L_["r1"]))], true))
	# ---- the airlock fitting and the route rail with its anchors
	hatch = WfEvaPkg.v(rt["hatch"])
	rail_up = WfEvaPkg.v(rt["rail_up"]).normalized()
	var fit: Dictionary = col["fitting"]
	var fs := CylinderShape3D.new()
	fs.radius = float(fit["radius_m"])
	fs.height = float(fit["r_outer"]) - float(fit["r_inner"])
	var fb := StaticBody3D.new()
	fb.name = "AIRLOCK_EVA_FITTING"
	fb.collision_layer = LAYER_WORLD
	fb.collision_mask = 0
	var fc := CollisionShape3D.new()
	fc.shape = fs
	var c := Vector3(float(fit["x"]), 0, 0) + rail_up * (float(fit["r_inner"]) + float(fit["r_outer"])) * 0.5
	fc.transform = Transform3D(_basis_y(rail_up), c)
	fb.add_child(fc)
	if show_surfaces:
		var fm := MeshInstance3D.new()
		var cy := CylinderMesh.new()
		cy.top_radius = fs.radius
		cy.bottom_radius = fs.radius
		cy.height = fs.height
		fm.mesh = cy
		fm.material_override = _mat(Color(0.55, 0.5, 0.35))
		fm.transform = fc.transform
		fb.add_child(fm)
	add_child(fb)
	var rr := float(rt["rail_radius_m"])
	for run in rt["runs"]:
		var ab: Array = rt["runs"][run]
		_rail(Vector3(float(ab[0]), 0, 0) + rail_up * rr, Vector3(float(ab[1]), 0, 0) + rail_up * rr)
	for a in rt["anchors"]:
		holds.append({"id": a["id"], "p": WfEvaPkg.v(a["p"]), "kind": "rail", "label": "Rail anchor " + str(a["id"])})
	for k in rt["holds"]:
		holds.append({"id": "HOLD_" + String(k).to_upper(), "p": WfEvaPkg.v(rt["holds"][k]["p"]), "kind": "rail",
			"label": {"airlock": "EVA hatch handhold", "rail_mid": "Rail handhold (mid)", "aft_hold": "Aft rail handhold", "forward_hold": "Forward rail handhold"}.get(k, k)})
	for i in s["fixtures"].size():
		holds.append({"id": "BROW_FIX_%03d" % i, "p": WfEvaPkg.v(s["fixtures"][i]), "kind": "brow_fixture",
			"label": "Brow panel fixture %d (aft face)" % i})
	for h in holds:
		_marker(h["p"], 0.05 if h["kind"] == "brow_fixture" else 0.07)
	# ---- the EVA equipment station beside the hatch: cartridge rack and drone service socket
	var st: Dictionary = pkg["station"]
	var off := WfEvaPkg.v(st["offset_from_hatch_m"])
	var around := Vector3.RIGHT.cross(rail_up).normalized()
	var rack := hatch + Vector3.RIGHT * off.x + around * off.y + rail_up * off.z
	station = {"rack": rack, "cartridges": int(st["cartridges"]), "socket": rack + Vector3.RIGHT * 0.9 + rail_up * 0.1, "out": rail_up}
	var rb := StaticBody3D.new()
	rb.name = "EVA_STATION_RACK"
	rb.collision_layer = LAYER_WORLD
	rb.collision_mask = 0
	var rcs := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = Vector3(0.8, 0.12, 0.5)
	rcs.shape = box
	rcs.transform = Transform3D(_basis_y(rail_up), rack - rail_up * 0.25)
	rb.add_child(rcs)
	var mi := MeshInstance3D.new()
	var bm := BoxMesh.new()
	bm.size = box.size
	mi.mesh = bm
	mi.material_override = _mat(Color(0.25, 0.3, 0.38))
	mi.transform = rcs.transform
	rb.add_child(mi)
	add_child(rb)
	holds.append({"id": "STATION_RACK", "p": rack + rail_up * 0.05, "kind": "station", "label": "EVA equipment station"})
	hazards = pkg["hazards"]

## X of the Brow's ram face at radius r (linear between profile rows).
func face_x(r: float) -> float:
	for i in range(1, face_prof.size()):
		var r0 := float(face_prof[i - 1][0])
		var r1 := float(face_prof[i][0])
		if r <= r1:
			var t := (r - r0) / maxf(r1 - r0, 1e-6)
			return lerpf(float(face_prof[i - 1][1]), float(face_prof[i][1]), clampf(t, 0.0, 1.0))
	return float(face_prof[face_prof.size() - 1][1])

func radius_of(p: Vector3) -> float:
	return Vector2(p.y, p.z).length()

## The hazard a point is in or near (within `margin`), or {}: {id, label, inside, distance}.
func hazard_at(p: Vector3, margin: float, operational: bool) -> Dictionary:
	var best := {}
	for h in hazards:
		var d := _hz_dist(h, p, operational)
		if d <= margin and (best.is_empty() or d < float(best["distance"])):
			best = {"id": h["id"], "label": h["label"], "inside": d <= 0.0, "distance": d}
	return best

func _hz_dist(h: Dictionary, p: Vector3, operational: bool) -> float:
	match h["kind"]:
		"box":
			var c := WfEvaPkg.v(h["centre"])
			var q := p - c
			var sz: Array = h["size"]
			var ex := absf(q.dot(WfEvaPkg.v(h["axis"]))) - float(sz[0]) * 0.5
			var ey := absf(q.dot(WfEvaPkg.v(h["side"]))) - float(sz[1]) * 0.5
			var ez := absf(q.dot(WfEvaPkg.v(h["up"]))) - float(sz[2]) * 0.5
			return maxf(ex, maxf(ey, ez))
		"annulus":
			var r := radius_of(p)
			return maxf(maxf(float(h["x0"]) - p.x, p.x - float(h["x1"])), maxf(float(h["r_in"]) - r, r - float(h["r_out"])))
		"sphere":
			return p.distance_to(WfEvaPkg.v(h["centre"])) - float(h["r"])
		"cylinder_x":
			return maxf(maxf(float(h["x0"]) - p.x, p.x - float(h["x1"])), radius_of(p) - float(h["r"]))
		"ahead_of_face":
			if not operational:
				return INF            # training simulation: the ram face is open to practice
			var r2 := radius_of(p)
			return maxf(face_x(r2) - p.x, r2 - shield_r - 2.0)
		"behind_x":
			return p.x - float(h["x"])
	return INF

## The nearest hold within `reach` of p, or {}.
func hold_near(p: Vector3, reach: float) -> Dictionary:
	var best := {}
	var bd := reach
	for h in holds:
		var d := p.distance_to(h["p"])
		if d <= bd:
			bd = d
			best = h
	return best

# ---------------------------------------------------------------------------------------------------------------------------- meshes
func _static(nm: String, faces: PackedVector3Array) -> void:
	var b := StaticBody3D.new()
	b.name = nm
	b.collision_layer = LAYER_WORLD
	b.collision_mask = 0
	var cs := CollisionShape3D.new()
	var sh := ConcavePolygonShape3D.new()
	sh.backface_collision = true
	sh.set_faces(faces)
	cs.shape = sh
	b.add_child(cs)
	if show_surfaces:
		var am := ArrayMesh.new()
		var arr := []
		arr.resize(Mesh.ARRAY_MAX)
		arr[Mesh.ARRAY_VERTEX] = faces
		am.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arr)
		var mi := MeshInstance3D.new()
		mi.mesh = am
		mi.material_override = _proxy_mat()
		b.add_child(mi)
	add_child(b)

func _proxy_mat() -> StandardMaterial3D:
	if _mat_proxy == null:
		_mat_proxy = StandardMaterial3D.new()
		_mat_proxy.albedo_color = Color(0.42, 0.44, 0.47)
		_mat_proxy.cull_mode = BaseMaterial3D.CULL_DISABLED
		_mat_proxy.roughness = 0.8
	return _mat_proxy

## Surface of revolution about +X through profile points (x, r).
func _lathe_x(prof: Array, cap_end: bool) -> PackedVector3Array:
	var f := PackedVector3Array()
	for i in range(1, prof.size()):
		var a: Vector2 = prof[i - 1]
		var b: Vector2 = prof[i]
		for k in SEG:
			var p0 := TAU * k / SEG
			var p1 := TAU * (k + 1) / SEG
			var A0 := Vector3(a.x, a.y * cos(p0), a.y * sin(p0))
			var A1 := Vector3(a.x, a.y * cos(p1), a.y * sin(p1))
			var B0 := Vector3(b.x, b.y * cos(p0), b.y * sin(p0))
			var B1 := Vector3(b.x, b.y * cos(p1), b.y * sin(p1))
			f.append_array([A0, B0, B1, A0, B1, A1])
	if cap_end:
		var e: Vector2 = prof[prof.size() - 1]
		for k in SEG:
			var p0 := TAU * k / SEG
			var p1 := TAU * (k + 1) / SEG
			f.append_array([Vector3(e.x, 0, 0), Vector3(e.x, e.y * cos(p0), e.y * sin(p0)), Vector3(e.x, e.y * cos(p1), e.y * sin(p1))])
	return f

## A face made of rings (x, r) from the centre outward: the Brow's conical faces.
func _disc_x(rings: Array) -> PackedVector3Array:
	var f := PackedVector3Array()
	var c: Vector2 = rings[0]
	for k in SEG:
		var p0 := TAU * k / SEG
		var p1 := TAU * (k + 1) / SEG
		var b: Vector2 = rings[1]
		f.append_array([Vector3(c.x, 0, 0), Vector3(b.x, b.y * cos(p0), b.y * sin(p0)), Vector3(b.x, b.y * cos(p1), b.y * sin(p1))])
	f.append_array(_lathe_x(rings.slice(1), false))
	return f

func _basis_y(up: Vector3) -> Basis:
	var y := up.normalized()
	var x := Vector3.RIGHT if absf(y.x) < 0.9 else Vector3.FORWARD
	x = (x - y * x.dot(y)).normalized()
	return Basis(x, y, x.cross(y))

func _rail(a: Vector3, b: Vector3) -> void:
	var mi := MeshInstance3D.new()
	var cm := CylinderMesh.new()
	cm.top_radius = 0.02
	cm.bottom_radius = 0.02
	cm.height = a.distance_to(b)
	mi.mesh = cm
	mi.material_override = _mat_rail
	var y := (b - a).normalized()
	var x := y.cross(Vector3.UP if absf(y.y) < 0.9 else Vector3.RIGHT).normalized()
	mi.transform = Transform3D(Basis(x, y, x.cross(y)), (a + b) * 0.5)
	add_child(mi)

func _marker(p: Vector3, r: float) -> void:
	var mi := MeshInstance3D.new()
	var sm := SphereMesh.new()
	sm.radius = r
	sm.height = 2 * r
	sm.radial_segments = 8
	sm.rings = 4
	mi.mesh = sm
	mi.material_override = _mat_hold
	mi.position = p
	add_child(mi)

func _mat(c: Color) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = c
	m.emission_enabled = true
	m.emission = c * 0.4
	return m
