class_name WfVestibuleView
extends Node3D
## U03: what the vestibule drill looks like. A schematic of ring A's transfer drum from the rig's access stage (dynamics.stages.access:
## trunk, port, drum radii and length, the crew tube root, the occupant's hold pose), driven only by the WfVestibule state of the lab:
## the drum turns at drum_w, the crew tube at the ring rate, the closures show shut (red) or open (green), the occupant rides the drum and
## after the handoff the ring. It changes no state. PROTOTYPE display: proxy shapes, the phase creep that lines the drum's hatch up with
## the tube (or the trunk port) after a speed match, and the labels. Origin: the drum centre on the ship axis; Godot X along the ship.

const PHASE_CREEP := 1.5                     # PROTOTYPE display: rad/s the drum creeps after a speed match to line its hatch up
const C_STATIC := Color(0.55, 0.57, 0.6)
const C_DRUM := Color(0.35, 0.6, 0.95)
const C_RING := Color(0.95, 0.65, 0.25)
const C_SHUT := Color(0.9, 0.25, 0.2)
const C_OPEN := Color(0.25, 0.85, 0.4)

var host: Node                               # the physics lab (vest, modes)
var a: Dictionary                            # dynamics.stages.access
var x0 := 0.0
var drum := Node3D.new()                     # turns at drum_w
var ring := Node3D.new()                     # turns at ring A's rate
var drum_angle := 0.0
var ring_angle := 0.0
var occupant: MeshInstance3D
var hatch := {}                              # side -> MeshInstance3D (closed leaf)
var frames := {}                             # side -> MeshInstance3D (the open frame)
var dp_label: Label3D
var occ_label: Label3D

func _init(h: Node, dyn: Dictionary) -> void:
	host = h
	a = dyn["stages"]["access"]
	x0 = (float(a["drum"]["x_m"][0]) + float(a["drum"]["x_m"][1])) * 0.5

## Blender vehicle point -> view local (Godot axes, origin at the drum centre).
func p(v: Array) -> Vector3:
	return Vector3(float(v[0]) - x0, float(v[2]), -float(v[1]))

func _ready() -> void:
	var r_t: float = a["trunk"]["clear_radius_m"]
	var r_in: float = a["drum"]["inner_radius_m"]
	var r_out: float = a["drum"]["outer_radius_m"]
	var r_port: float = a["port"]["clear_radius_m"]
	var dx0: float = float(a["drum"]["x_m"][0]) - x0
	var dx1: float = float(a["drum"]["x_m"][1]) - x0
	var tx0: float = float(a["trunk"]["x_m"][0]) - x0
	var tx1: float = float(a["trunk"]["x_m"][1]) - x0
	var port_x: float = float(a["port"]["centre_m"][0]) - x0
	var tube: Array = a["tube"]["points_m"]
	var r_tube: float = a["tube"]["clear_radius_m"]
	var key := DirectionalLight3D.new()          # review light only (presentation)
	key.rotation = Vector3(-0.8, 0.6, 0.0)
	add_child(key)
	# the stationary trunk (spine side): a translucent tube along the axis
	add_child(_cyl(r_t, tx1 - tx0, Vector3((tx0 + tx1) * 0.5, 0, 0), Vector3(0, 0, PI * 0.5), C_STATIC, 0.25))
	_label(self, "trunk (stationary spine)", Vector3(tx1 - 0.3, r_t + 0.25, 0), C_STATIC)
	add_child(drum)
	add_child(ring)
	# the drum: outer and inner walls, end plates as rings, and a stripe so its turning reads
	drum.add_child(_cyl(r_out, dx1 - dx0, Vector3((dx0 + dx1) * 0.5, 0, 0), Vector3(0, 0, PI * 0.5), C_DRUM, 0.18))
	drum.add_child(_cyl(r_in, dx1 - dx0, Vector3((dx0 + dx1) * 0.5, 0, 0), Vector3(0, 0, PI * 0.5), C_DRUM, 0.12))
	for i in 4:
		var th := TAU * i / 4.0 + PI * 0.25
		drum.add_child(_box(Vector3(dx1 - dx0, 0.05, 0.12), Vector3((dx0 + dx1) * 0.5, cos(th) * r_out, -sin(th) * r_out), Vector3(th, 0, 0), C_DRUM.lightened(0.3), 1.0))
	_label(drum, "transfer drum", Vector3(dx0 - 0.1, -r_out - 0.25, 0), C_DRUM)
	# the stationary-side hatch: the port from the trunk into the drum (radial, at the index +Y), on the trunk
	var port_n := p(a["port"]["radial"]) + Vector3(x0, 0, 0)
	_hatch("STATIONARY", self, Vector3(port_x, 0, 0) + port_n * (r_t + r_in) * 0.5, port_n, r_port, "stationary-side hatch")
	# the ring-side hatch: in the drum's outer wall where the crew tube starts; it turns with the drum
	var root := p(tube[0])
	var tn := root - Vector3(root.x, 0, 0)
	tn = tn.normalized()
	_hatch("RING", drum, Vector3(root.x, 0, 0) + tn * r_out, tn, r_tube, "ring-side hatch")
	# ring A's crew tube root: the first two points of the tube axis, turning with the ring
	var t1 := p(tube[1])
	var t2 := p(tube[2])
	for seg in [[root, t1], [t1, t2]]:
		var s0: Vector3 = seg[0]
		var s1: Vector3 = seg[1]
		var m := _cyl(r_tube, s0.distance_to(s1), (s0 + s1) * 0.5, Vector3.ZERO, C_RING, 0.3)
		m.basis = Basis(Quaternion(Vector3.UP, (s1 - s0).normalized()))
		ring.add_child(m)
	_label(ring, "ring A crew tube (turns with ring A)", t2 + Vector3(0, 0.4, 0), C_RING)
	# the occupant at the drum restraint pose (the access line's hold point)
	occupant = MeshInstance3D.new()
	var cap := CapsuleMesh.new()
	cap.radius = 0.22
	cap.height = 1.75
	occupant.mesh = cap
	occupant.material_override = _mat(Color(0.95, 0.85, 0.3), 1.0)
	var hold: Dictionary = a["line"][int(a["hold_index"])]
	occupant.position = p(hold["p"])
	var up := p(hold["up"]) + Vector3(x0, 0, 0)
	occupant.basis = Basis(Quaternion(Vector3.UP, up.normalized()))
	drum.add_child(occupant)
	occ_label = _label(occupant, "occupant", Vector3(0, 1.1, 0), Color(0.95, 0.85, 0.3))
	dp_label = _label(self, "", Vector3(root.x, r_out + 1.0, 0.6), Color(0.85, 0.9, 1.0))

func _process(dt: float) -> void:
	var v: WfVestibule = host.vest
	var w: float = host.modes.omega_now(0)
	ring_angle = wrapf(ring_angle + w * dt, -PI, PI)
	drum_angle = wrapf(drum_angle + v.drum_w * dt, -PI, PI)
	if not v.ramping and absf(v.drum_w - w) <= v.tol() and absf(w) > v.tol():
		drum_angle += clampf(wrapf(ring_angle - drum_angle, -PI, PI), -PHASE_CREEP * dt, PHASE_CREEP * dt)   # line the hatch up with the tube
	elif not v.ramping and absf(v.drum_w) <= v.tol():
		drum_angle += clampf(wrapf(-drum_angle, -PI, PI), -PHASE_CREEP * dt, PHASE_CREEP * dt)              # line it up with the trunk port
	drum.rotation = Vector3(drum_angle, 0, 0)
	ring.rotation = Vector3(ring_angle, 0, 0)
	for side in ["STATIONARY", "RING"]:
		var shut: bool = v.closures[side]
		hatch[side].visible = shut
		frames[side].material_override = _mat(C_SHUT if shut else C_OPEN, 1.0)
	var handed := v.log.any(func(e): return e["action"] == "handoff" and e["ok"])
	var parent: Node3D = ring if handed else drum
	if occupant.get_parent() != parent:
		var gt := occupant.global_transform
		occupant.get_parent().remove_child(occupant)
		parent.add_child(occupant)
		occupant.global_transform = gt
	occ_label.text = "occupant: %s" % ("in ring A's frame" if handed else ("restrained" if v.restrained else "not restrained"))
	var dp := "unknown" if v.dp_equalized == null else ("shown equal" if v.dp_equalized else "NOT equal")
	dp_label.text = "drum %.3f rad/s · ring A %.3f rad/s\npressure across the ring-side hatch: %s" % [v.drum_w, w, dp]

func _hatch(side: String, parent: Node3D, c: Vector3, n: Vector3, r: float, text: String) -> void:
	var q := Basis(Quaternion(Vector3.UP, n.normalized()))
	var leaf := _cyl(r, 0.04, c, Vector3.ZERO, C_SHUT, 0.85)
	leaf.basis = q
	parent.add_child(leaf)
	var fr := MeshInstance3D.new()
	var tm := TorusMesh.new()
	tm.inner_radius = r
	tm.outer_radius = r + 0.07
	fr.mesh = tm
	fr.position = c
	fr.basis = q
	parent.add_child(fr)
	hatch[side] = leaf
	frames[side] = fr
	_label(parent, text, c + n.normalized() * 0.35 + Vector3(0, 0, 0.5), Color(0.9, 0.9, 0.9))

func _mat(c: Color, alpha: float) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = Color(c, alpha)
	if alpha < 1.0:
		m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		m.cull_mode = BaseMaterial3D.CULL_DISABLED
	return m

func _cyl(r: float, h: float, pos: Vector3, rot: Vector3, c: Color, alpha: float) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var cm := CylinderMesh.new()
	cm.top_radius = r
	cm.bottom_radius = r
	cm.height = h
	cm.cap_top = false
	cm.cap_bottom = false
	if h < 0.1:
		cm.cap_top = true
		cm.cap_bottom = true
	mi.mesh = cm
	mi.position = pos
	mi.rotation = rot
	mi.material_override = _mat(c, alpha)
	return mi

func _box(size: Vector3, pos: Vector3, rot: Vector3, c: Color, alpha: float) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var bm := BoxMesh.new()
	bm.size = size
	mi.mesh = bm
	mi.position = pos
	mi.rotation = rot
	mi.material_override = _mat(c, alpha)
	return mi

func _label(parent: Node3D, text: String, pos: Vector3, c: Color) -> Label3D:
	var l := Label3D.new()
	l.text = text
	l.position = pos
	l.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	l.font_size = 40
	l.pixel_size = 0.004
	l.modulate = c
	l.outline_size = 8
	l.no_depth_test = true
	parent.add_child(l)
	return l
