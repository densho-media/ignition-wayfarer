class_name WfBodyTour
extends Node3D
## PHYS-001 phase 8: the boarding body mode (SIMULATION_ONLY). The visitor / instructor body (profile human_iva, no survivor identity, STG-001)
## moves with the crew physics on the real route geometry; the ship stays visible around it. Two beats, both from the rig `dynamics.stages`:
##  SPINE (stop WF.STOP.IND.SPINE, DOCKED, SHIP frame, zero field): the trunk as a hollow cylinder of `clear_radius_m` along `axis_m` (thin
##    static boxes generated from those numbers, closed ends) and the nine real Crew_Trunk_* rails as rod handholds. The body grips
##    Crew_Trunk_Refuge_Rail_1, pushes off aft (|dv| <= profile test_push_dv), drifts and catches Crew_Trunk_Handrail_2_1. No thrust, no braking.
##  RING (stop WF.STOP.IND.HABITAT, COAST, RING_A or RING_B frame): the sector-1 aisle and landing boxes of that ring (A1 from the induction
##    route's rooms, B1 from `ring_rooms.rings.RING_B`; floor at deck_m, walls and ceiling from half_m/axes), walk on the real deck (r 28 m)
##    and a dropped object whose Coriolis deflection has the sign of the rig fixture.
## Collision shapes come from the rig numbers only, never from the imported meshes. Display: the physics runs in its own collision layer
## (TOUR_LAYER) in a world node that never moves; a visual proxy of the body (and tool) hangs under `view_root`. SPINE: view_root is a child
## of this node (ship frame). RING: view_root is a child of that ring's pivot at the ring centre, so the proxy and the camera turn with the real
## ring meshes while the physics geometry stays static in the ring frame (the rotation is shown, never added to the physics).
## Keys (interactive): 1 spine beat, 2 ring A beat, 3 ring B beat, G grab the nearest rail, Space push (look direction, while gripping), R release,
## W A S D walk (floor and field only), T drop the object (ring beat), V first person / outside view, K show colliders, N back to the review rail.

signal beat_changed(stop_key: String)    # the host puts the review state (rings, drum, closures) to this stop's state

const TOUR_LAYER := 1 << 9                   # collision layer and mask of everything here; the ship and the review tools never use it
const SLAB := 0.2                            # PROTOTYPE thickness of a collider slab (m); the surface is the sourced plane, the slab lies outside it
const TRUNK_SIDES := 32                      # PROTOTYPE number of flats that form the trunk cylinder (flats tangent to clear_radius_m, so the free circle is kept)
const BRANCH_STUB := 0.6                     # PROTOTYPE depth of a trunk branch bore beyond the trunk wall, closed at its end (the hatch / connector beyond)
const START_RAIL := "Crew_Trunk_Refuge_Rail_1"    # PROTOTYPE tour choice: the grip near the SPINE stop (x 95.55)
const CATCH_RAIL := "Crew_Trunk_Handrail_2_1"     # PROTOTYPE tour choice: the real rail several metres aft that the drift ends on
const PUSH_DIR := Vector3.LEFT                    # aft is -X (ship +X is the bow)
const DROP_HEIGHT := 1.0                     # PROTOTYPE height of the dropped object over the deck (m)
const NOT_COMFORT := "a display of the sourced spin (DYN-003), not a comfort limit"

var rig: Dictionary
var dyn: Dictionary
var stages: Dictionary
var field: WfFrameField
var world: Node3D
var view_root := Node3D.new()
var ring_pivot: Node3D = null               # set by the host: ring A's pivot (it carries the ring meshes)
var ring_pivots := {}                       # host, optional: zone -> that ring's pivot (RING_B); without it ring B's proxy hangs still at its centre
var ring_angle_fn := Callable()             # host: -> display angle of ring A (rad)
var ring_rate_fn := Callable()              # host: -> display rate of ring A (rad/s)
var actor: WfCrewBody
var tool: WfTool
var rails: Array = []
var debug_meshes: Array = []
var body_vis := Node3D.new()
var tool_vis := MeshInstance3D.new()
var camera := Camera3D.new()
var lamp := OmniLight3D.new()
var hud := Label.new()
var layer := CanvasLayer.new()
var active := false
var beat := "SPINE"
var yaw := 0.0
var pitch := 0.0
var view_out := false
var ext_offset := Vector3.INF               # captures: camera at body + this (view_root axes), looking at the body
var dbg_mat := StandardMaterial3D.new()
var auto_walk := Vector3.ZERO              # Demonstrator 01 autoplay: a held walk direction instead of the keys
var model: Node3D = null                    # ARTISTIC layer: the newcomer MPFB character on the proxy (pose only, never moves the body)
var anim: AnimationPlayer = null
var anim_now := ""
var capsule_vis: Array = []                 # the capsule proxy meshes; shown without the model or with K
var drops := 0                              # U02: T presses that dropped the object, and where it started (ring-frame tangential z)
var drop_z0 := 0.0
const MODEL_PATH := "res://generated/characters/newcomer.glb"

func setup(r: Dictionary) -> void:
	rig = r
	dyn = r["dynamics"]
	stages = dyn["stages"]
	field = WfFrameField.new(dyn)
	add_child(camera)
	lamp.omni_range = 12.0
	camera.add_child(lamp)
	hud.position = Vector2(12, 8)
	hud.add_theme_font_size_override("font_size", 14)
	layer.add_child(hud)
	layer.visible = false
	add_child(layer)
	add_child(view_root)
	dbg_mat.albedo_color = Color(0.2, 0.8, 1.0, 0.25)
	dbg_mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	dbg_mat.cull_mode = BaseMaterial3D.CULL_DISABLED
	var cap := CapsuleMesh.new()
	var prof: Dictionary = dyn["profiles"]["human_iva"]
	cap.radius = prof["radius_m"]
	cap.height = prof["height_m"]
	var body_mi := MeshInstance3D.new()
	body_mi.mesh = cap
	body_mi.material_override = _flat(Color(0.95, 0.5, 0.1))
	body_vis.add_child(body_mi)
	capsule_vis.append(body_mi)
	var head := MeshInstance3D.new()                                   # the head end (+y of the capsule)
	var sph := SphereMesh.new()
	sph.radius = prof["radius_m"] * 0.8
	sph.height = sph.radius * 2.0
	head.mesh = sph
	head.position = Vector3(0, prof["height_m"] * 0.5 + 0.02, 0)
	head.material_override = _flat(Color(0.95, 0.85, 0.7))
	body_vis.add_child(head)
	capsule_vis.append(head)
	var bm := BoxMesh.new()
	bm.size = WfTool.SIZE
	tool_vis.mesh = bm
	tool_vis.material_override = _flat(Color(0.2, 0.9, 0.3))
	if ResourceLoader.exists(MODEL_PATH):
		model = (load(MODEL_PATH) as PackedScene).instantiate()
		model.name = "ARTISTIC_Newcomer"
		model.set_meta("layer", "ARTISTIC: presentation only, follows the physics capsule; poses, never moves the body")
		var stature := 1.7
		model.transform = Transform3D(Basis(Vector3.UP, PI), Vector3(0, -stature * 0.5, 0))   # feet at the capsule's lower end; glTF front +Z turned to the capsule's -Z (walk direction)
		body_vis.add_child(model)
		var ap := model.find_children("*", "AnimationPlayer", true, false)
		if not ap.is_empty():
			anim = ap[0]
			for n in ["idle", "walk"]:
				if anim.has_animation(n):
					anim.get_animation(n).loop_mode = Animation.LOOP_LINEAR
		for c in capsule_vis:
			c.visible = false
	view_root.add_child(body_vis)
	view_root.add_child(tool_vis)
	body_vis.visible = false
	tool_vis.visible = false

static func _flat(c: Color) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = c
	return m

## Blender / ship axes (+X bow, +Z dorsal) to Godot (x, z, -y).
static func g(v: Array) -> Vector3:
	return Vector3(v[0], v[2], -v[1])

func ring_centre_x(k := 0) -> float:
	return dyn["rings"][k]["centre_x_m"]

func fixture(id: String) -> Dictionary:
	for f in dyn["fixtures"]:
		if f["id"] == id:
			return f
	return {}

func _isolate(b: CollisionObject3D) -> void:
	b.collision_layer = TOUR_LAYER
	b.collision_mask = TOUR_LAYER

func _slab(pos: Vector3, bas: Basis, size: Vector3) -> StaticBody3D:
	var sb := StaticBody3D.new()
	sb.transform = Transform3D(bas, pos)
	var cs := CollisionShape3D.new()
	var bx := BoxShape3D.new()
	bx.size = size
	cs.shape = bx
	sb.add_child(cs)
	var mi := MeshInstance3D.new()                 # collider outline for review, hidden unless K
	var bm := BoxMesh.new()
	bm.size = size
	mi.mesh = bm
	mi.material_override = dbg_mat
	mi.visible = false
	sb.add_child(mi)
	debug_meshes.append(mi)
	var pm := PhysicsMaterial.new()
	pm.friction = 0.0
	pm.bounce = 0.0
	sb.physics_material_override = pm
	_isolate(sb)
	world.add_child(sb)
	return sb

func _clear() -> void:
	if world:
		remove_child(world)
		world.free()
	world = Node3D.new()
	add_child(world)
	rails = []
	debug_meshes = []
	actor = null
	tool = null
	drops = 0
	body_vis.visible = false
	tool_vis.visible = false

func _place_view(parent: Node3D, offset: Vector3) -> void:
	if view_root.get_parent() != parent:
		view_root.get_parent().remove_child(view_root)
		parent.add_child(view_root)
	view_root.transform = Transform3D(Basis.IDENTITY, offset)

func _spawn_actor(pos: Vector3, bas := Basis.IDENTITY) -> void:
	actor = WfCrewBody.new()
	actor.configure(dyn, "human_iva", field)
	actor.transform = Transform3D(bas, pos)
	for c in actor.get_children():
		if c is MeshInstance3D:
			c.visible = false                  # the visual proxy under view_root shows the body
	_isolate(actor)
	world.add_child(actor)
	body_vis.visible = true

func _spawn_tool(pos: Vector3) -> void:
	tool = WfTool.new()
	tool.field = field
	tool.position = pos
	for c in tool.get_children():
		if c is MeshInstance3D:
			c.visible = false
	_isolate(tool)
	world.add_child(tool)
	tool_vis.visible = true

# ---- SPINE beat: the real trunk -------------------------------------------------------------------------------------------------------------

func _build_trunk(t: Dictionary, shift := Vector3.ZERO, caps := [true, true]) -> void:
	var a := g(t["axis_m"][0]) + shift
	var b := g(t["axis_m"][1]) + shift
	var axis := (b - a).normalized()
	var r: float = t["clear_radius_m"]
	var u := axis.cross(Vector3.UP)
	if u.length() < 0.1:
		u = axis.cross(Vector3.RIGHT)
	u = u.normalized()
	# The trunk wall with the rig's branch openings cut out (the trunk lies on the ship axis, Godot X). Each opening gets a short bore
	# closed at its far end: the closed hatch or connector beyond, so the body can reach into a branch but never leaves the volume.
	var holes := []
	for o in t.get("openings", []):
		var th := deg_to_rad(float(o["theta_deg"]))
		holes.append({"c": Vector3(float(o["x_m"]), 0, 0) + shift, "n": g([0.0, cos(th), sin(th)]).normalized(), "r": float(o["radius_m"]), "patch": null})
	_cyl_x(minf(a.x, b.x), maxf(a.x, b.x), r, true, holes)
	for h in holes:
		var hn: Vector3 = h["n"]
		var hr: float = h["r"]
		var hc: Vector3 = h["c"]
		_radial_bore(hc, hn, hr, func(bb, _e): return sqrt(maxf(r * r - bb * bb, 0.0)), func(_bb, _e): return r + BRANCH_STUB)
		var hs := hn.cross(Vector3.RIGHT).normalized()
		_slab(hc + hn * (r + BRANCH_STUB + SLAB * 0.5), Basis(hn, hs, hn.cross(hs)), Vector3(SLAB, 2.0 * hr + 2.0 * SLAB, 2.0 * hr + 2.0 * SLAB))
	var side := 2.0 * r / cos(PI / TRUNK_SIDES) + 2.0 * SLAB
	for s in [-1.0, 1.0]:                          # PROTOTYPE closed ends of the trunk volume
		if not caps[0 if s < 0.0 else 1]:
			continue
		var n: Vector3 = axis * s
		_slab((a if s < 0.0 else b) + n * SLAB * 0.5, Basis(n, u, n.cross(u)), Vector3(SLAB, side, side))

func _rail(h: Dictionary, shift := Vector3.ZERO, solid := true) -> WfHandhold:
	var pa := g(h["rail_start"]) + shift
	var pb := g(h["rail_end"]) + shift
	var rail := WfHandhold.new()
	rail.anchor_id = h["anchor_id"]
	rail.name = rail.anchor_id
	var d := (pb - pa).normalized()
	rail.transform = Transform3D(Basis(Quaternion(Vector3.UP, d)), (pa + pb) * 0.5)
	rail.seg_a = Vector3(0, -(pb - pa).length() * 0.5, 0)
	rail.seg_b = Vector3(0, (pb - pa).length() * 0.5, 0)
	var cs := CollisionShape3D.new()
	var cyl := CylinderShape3D.new()
	cyl.radius = h["radius_m"]
	cyl.height = (pb - pa).length()
	cs.shape = cyl
	cs.disabled = not solid
	rail.add_child(cs)
	_isolate(rail)
	return rail

func rail_by_id(id: String) -> WfHandhold:
	for r in rails:
		if r.anchor_id == id:
			return r
	return null

## The S004 spine in the SHIP frame at DOCKED (field zero). The body lies along the trunk (PROTOTYPE pose) on the axis at the start rail.
func build_spine(grip := true) -> void:
	_clear()
	beat = "SPINE"
	field.set_state("SHIP", "DOCKED")
	_place_view(self, Vector3.ZERO)
	var t: Dictionary = stages["trunk"]
	_build_trunk(t)
	for h in t["handholds"]:
		var rail := _rail(h)
		world.add_child(rail)
		rails.append(rail)
	var start := rail_by_id(START_RAIL)
	var a := g(t["axis_m"][0])
	var axis := (g(t["axis_m"][1]) - a).normalized()
	var mid: Vector3 = start.global_position
	var on_axis := a + axis * (mid - a).dot(axis)          # the body centre on the trunk axis at the rail's mid x
	_spawn_actor(on_axis, Basis(Vector3.BACK, PI * 0.5))   # long axis along the trunk
	yaw = 0.0
	pitch = 0.0
	beat_changed.emit("spine")
	if grip:
		_start_grip()

func _start_grip() -> void:
	await ticks(2)
	if actor and rails.size() > 0 and actor.grip == null and beat == "SPINE":
		actor.grab(rail_by_id(START_RAIL))

# ---- RING beat: the real A1 aisle and landing ----------------------------------------------------------------------------------------------

## A room box of the rig in ring-centre-relative Godot axes: centre, half sizes, the axis index and sign of "up" (away from the deck).
func _room(box: Dictionary, ring := 0) -> Dictionary:
	var ax: Array = box["axes"]
	var hb := Vector3.ZERO
	for i in 3:
		hb += Vector3(absf(ax[i][0]), absf(ax[i][1]), absf(ax[i][2])) * float(box["half_m"][i])
	var c := g(box["centre_m"]) - Vector3(ring_centre_x(ring), 0, 0)
	var up := g(box["up"])
	var k := 0
	for i in 3:
		if absf(up[i]) > absf(up[k]):
			k = i
	return {"id": box["id"], "c": c, "h": Vector3(hb.x, hb.z, hb.y), "k": k, "s": signf(up[k])}

## The sector-1 aisle and landing of a ring: ring A from the induction route's rooms, ring B from `ring_rooms.rings.RING_B` (same clear
## volumes on ring B's rotor, J01).
func ring_rooms(zone := "RING_A") -> Array:
	var out := []
	var k := WfFrames.ring_index(zone)
	var boxes: Array = rig["induction_route"]["rooms"]["boxes"] if k == 0 else stages["ring_rooms"]["rings"][zone]["boxes"]
	for box in boxes:
		if str(box["id"]).begins_with("WF.ROOM.%s1." % "AB"[k]) and box["kind"] in ["aisle", "landing"]:
			out.append(_room(box, k))
	return out

func _build_rooms(rooms: Array, open_top := []) -> void:
	for r in rooms:
		var c: Vector3 = r.c
		var h: Vector3 = r.h
		var k: int = r.k
		var s: float = r.s
		var full := h * 2.0
		for dir in [-1.0, 1.0]:                    # deck (dir -1: opposite to up) and ceiling
			if dir > 0.0 and r.id in open_top:     # the crew tube opens into it (M2 tube beat)
				continue
			var pos := c
			pos[k] = c[k] + dir * s * (h[k] + SLAB * 0.5)
			var size := full
			size[k] = SLAB
			_slab(pos, Basis.IDENTITY, size)
		for j in 3:
			if j == k:
				continue
			var m := 3 - j - k
			for sg in [-1.0, 1.0]:
				var p: float = c[j] + sg * h[j]
				var lo: float = c[m] - h[m]
				var hi: float = c[m] + h[m]
				var pieces := [[lo, hi]]
				for o in rooms:
					if o == r or o.k != k:
						continue
					if absf(o.c[j] - sg * o.h[j] - p) > 1e-3:
						continue
					var a: float = maxf(lo, o.c[m] - o.h[m])        # open where the neighbouring room touches this face
					var b: float = minf(hi, o.c[m] + o.h[m])
					if b <= a:
						continue
					var next := []
					for q in pieces:
						if a > q[0]:
							next.append([q[0], minf(a, q[1])])
						if b < q[1]:
							next.append([maxf(b, q[0]), q[1]])
					pieces = next
				for q in pieces:
					if q[1] - q[0] < 1e-3:
						continue
					var pos := c
					pos[j] = p + sg * SLAB * 0.5
					pos[m] = (q[0] + q[1]) * 0.5
					var size := Vector3.ZERO
					size[j] = SLAB
					size[k] = full[k]
					size[m] = q[1] - q[0]
					_slab(pos, Basis.IDENTITY, size)

func deck_y(zone := "RING_A") -> float:
	var r: Dictionary = ring_rooms(zone)[0]
	return r.c[r.k] - r.s * r.h[r.k]

## The A1 aisle in the ring frame (r from the ring centre, the deck at the floor radius, geometry static); the actor stands, the object (optional) is at rest.
## `drop`: the tool starts 1 m up and falls at once (run_check's drop); otherwise it is held still there (frozen, a display hold) until T drops it.
func build_ring(zone: String, with_tool := false, drop := true) -> void:
	_clear()
	beat = "RING"
	field.set_state(zone, "COAST")
	var k := WfFrames.ring_index(zone)
	var cx := ring_centre_x(k)
	var pivot: Node3D = ring_pivots.get(zone, ring_pivot if k == 0 else null)
	if pivot != null:
		_place_view(pivot, Vector3(cx, 0, 0) - pivot.position)
	else:
		_place_view(self, Vector3(cx, 0, 0))
	var rooms := ring_rooms(zone)
	_build_rooms(rooms)
	var y := deck_y(zone)
	var prof: Dictionary = dyn["profiles"]["human_iva"]
	var up_dir := Vector3(0, -1, 0) if rooms[0].s < 0.0 else Vector3(0, 1, 0)        # toward the axis; the deck is at the far end
	var x0 := -0.9 if with_tool else -1.0
	_spawn_actor(Vector3(x0, y, 0.0) + up_dir * (prof["height_m"] * 0.5 + 0.02), Basis(Vector3.RIGHT, PI) if up_dir.y < 0.0 else Basis.IDENTITY)
	if with_tool:
		_spawn_tool(Vector3(0.9, y, 0.0) + up_dir * DROP_HEIGHT)
		tool.freeze = not drop
	yaw = 0.0
	pitch = 0.0
	beat_changed.emit("habitat")

# ---- TUBE beat (M2): the induction crew tube's radial run and its landing well, RING frame ----------------------------------------------------

var tube_rungs: Array = []                  # the rungs, outward along the run
var tube_axis := [Vector3.ZERO, Vector3.ZERO]   # run axis, ring-centre-relative Godot axes: top (bend) and the hatch seat
var tube_out := Vector3.ZERO                # unit vector outward along the run
var tube_toward := Vector3.ZERO             # unit vector from the axis toward the ladder
var tube_line := [Vector3.ZERO, Vector3.ZERO]   # the climber's body-centre line: start under the first rung, end standing on the well's deck
var tube_s := 0.0                           # body position along tube_line (m)
var climb_cmd := 0.0                        # -1 inward (climb), 0 hold, +1 outward (descend), times the review pace
var auto_descend := false
var arrived := false
var climb_v := 0.0                          # the hands' current speed along the run (m/s, + outward)
const LADDER_ACCEL := 0.5                   # PROTOTYPE: how fast the hands change the climbing speed (m/s2); no sourced value
var hand_log: Array = []                    # per step: {s, r, hand (N, Godot axes), v}
# M2 access (rig dynamics.stages.access): one body line from the trunk through the spine port, the drum and the elbows to the run top, then
# down the run (tube_line). line_s is the rig's parameter (centre or end travel); the hands move the body along it at the review pace.
var line_p: Array = []
var line_up: Array = []
var line_s: Array = []
var line_phase: Array = []
var line_vmax: Array = []                   # per pose: the largest line speed at which the turn there changes the body's velocity by at most LADDER_ACCEL in a step
var from_access := false
var s_port := 0.0                           # the body leaves the trunk bore here: the port gate must be fully open
var s_hold := 0.0                           # the restraint pose in the drum (both closures shut)
var s_run := 0.0                            # the run top (tube_line[0]); DESCENT starts here
var s_stop := INF                           # the host's chapter end: the hands bring the body to rest here
var gate_fn := Callable()                   # host: -> {"STATIONARY": fully open, "RING": fully open} of the vestibule openings
var frame_fn := Callable()                  # host: -> [drum fraction of ring A's spin, its rate of change 1/s]; empty = ring A COAST
var drum_pivot: Node3D = null               # host: the drum's pivot (the access world is the drum frame until the sync)
var port_patch: Array = []                  # colliders that close the port gate's bore / the drum door's bore while shut
var door_patch: Array = []
var access_grips: Array = []
var coasts: Array = []                      # [s0, s1] before the sync with no grip in reach: the body coasts, the hands neither push nor brake
var restrained := false
var drum_frac := 0.0

## The run and its landing well (rooms of the A1 aisle and landing, the well open to the tube), the rungs as grab anchors (not colliders,
## PROTOTYPE: the climber's body is not collided with its own ladder), the body on the climber line under the first rung, holding.
func build_tube(with_tool := true, access := false) -> void:
	_clear()
	beat = "TUBE"
	arrived = false
	hand_log = []
	from_access = access
	field.set_state("RING_A", "COAST")
	var cx := ring_centre_x()
	var pivot: Node3D = drum_pivot if access and drum_pivot != null else ring_pivot
	if pivot != null:
		_place_view(pivot, Vector3(cx, 0, 0) - pivot.position)
	var t: Dictionary = stages["tube"]
	var shift := Vector3(-cx, 0, 0)
	tube_axis = [g(t["axis_m"][0]) + shift, g(t["axis_m"][1]) + shift]
	tube_out = (tube_axis[1] - tube_axis[0]).normalized()
	tube_toward = g(t["toward_ladder"])
	_build_access(stages["access"], shift)          # trunk, port, drum, door, elbows and the run, open into the landing well
	var rooms := ring_rooms()
	_build_rooms(rooms, [t["landing_room"]])
	tube_rungs = []
	for h in t["rungs"]:
		var rung := _rail(h, shift, false)
		rung.collision_layer = 0                 # a grab anchor only: the climber is not collided with its own ladder (PROTOTYPE)
		rung.collision_mask = 0
		world.add_child(rung)
		rails.append(rung)
		tube_rungs.append(rung)
	var prof: Dictionary = dyn["profiles"]["human_iva"]
	var off: Vector3 = tube_toward * float(t["climber_offset_m"])
	var top: Vector3 = tube_axis[0] + tube_out * (prof["height_m"] * 0.5 + 0.05) + off     # the head just under the run's top (the bend is not a stage)
	var deck := deck_y()
	var bottom: Vector3 = top + tube_out * ((absf(deck) - prof["height_m"] * 0.5 - 0.01) - absf(top.y))
	tube_line = [top, bottom]
	var a: Dictionary = stages["access"]
	line_p = []
	line_up = []
	line_s = []
	line_phase = []
	for q in a["line"]:
		line_p.append(g(q["p"]) + shift)
		line_up.append(g(q["up"]))
		line_s.append(float(q["s_m"]))
		line_phase.append(str(q["phase"]))
	line_p[-1] = top                                  # the same point (tube_stage), exact in Godot axes
	line_p.append(bottom)
	line_up.append(-tube_out)
	line_s.append(float(line_s[-1]) + (bottom - top).length())
	line_phase.append("run")
	line_vmax = [0.0]
	var dt := 1.0 / Engine.physics_ticks_per_second
	for k in range(1, line_p.size() - 1):
		var d1: Vector3 = ((line_p[k] as Vector3) - (line_p[k - 1] as Vector3)) / maxf(float(line_s[k]) - float(line_s[k - 1]), 1e-9)
		var d2: Vector3 = ((line_p[k + 1] as Vector3) - (line_p[k] as Vector3)) / maxf(float(line_s[k + 1]) - float(line_s[k]), 1e-9)
		var dv := (d2 - d1).length()
		line_vmax.append(LADDER_ACCEL * dt / dv if dv > 1e-9 else INF)
	line_vmax.append(0.0)
	coasts = []
	for c in a.get("coasts_s_m", []):
		coasts.append([float(c[0]), float(c[1])])
	s_port = a["port_s_m"]
	s_hold = a["hold_s_m"]
	s_run = a["run_s_m"]
	s_stop = INF
	tube_s = 0.0 if access else s_run
	climb_v = 0.0
	restrained = false
	drum_frac = 0.0 if access else 1.0
	_apply_frame()
	var at := line_at(tube_s)
	_spawn_actor(at[0], Basis.looking_at(Vector3.FORWARD if absf((at[1] as Vector3).dot(Vector3.FORWARD)) < 0.9 else Vector3.UP, at[1]) if access
		else (Basis(Vector3.RIGHT, PI) if tube_out.y > 0.0 else Basis.IDENTITY))
	actor.on_ladder(Vector3.ZERO)
	actor.ladder_up = at[1]
	set_closures(not access, access)                # the port gate shut once past it; the drum door shut until the sync
	if with_tool:
		_spawn_tool(Vector3(0.9, deck, 0.0) - tube_out * DROP_HEIGHT)
	yaw = 0.0
	pitch = 0.0
	if not access:                                  # on the access the demonstrator drives the review state (no jump to the stop)
		beat_changed.emit("transfer")

func tube_length() -> float:
	return float(line_s[-1])

## Body centre and head direction at line parameter s (centre lerp, axis nlerp between the rig's poses).
func line_at(s: float) -> Array:
	var i := 0
	while i < line_s.size() - 2 and s > float(line_s[i + 1]):
		i += 1
	var span: float = float(line_s[i + 1]) - float(line_s[i])
	var f := clampf((s - float(line_s[i])) / span, 0.0, 1.0) if span > 1e-9 else 1.0
	return [(line_p[i] as Vector3).lerp(line_p[i + 1], f), (line_up[i] as Vector3).lerp(line_up[i + 1], f).normalized(), line_phase[i + 1]]

## The drum frame (the access world) turns with the drum: field of ring A's spin times the drum's fraction, with its Euler term.
func _apply_frame() -> void:
	var w0 := WfFrames.ring_omega(dyn, 0, "COAST")
	var df := 0.0
	if frame_fn.is_valid():
		var fr: Array = frame_fn.call()
		drum_frac = fr[0]
		df = fr[1]
	field.w = WfFrames.mul(w0, drum_frac)
	field.alpha = WfFrames.mul(w0, df)

## Port gate (STATIONARY) and drum door (RING) as colliders across their bores, PROTOTYPE shape (the clear surface; seals OPEN).
func set_closures(port_shut: bool, door_shut: bool) -> void:
	for b in port_patch:
		for c in b.get_children():
			if c is CollisionShape3D:
				c.disabled = not port_shut
	for b in door_patch:
		for c in b.get_children():
			if c is CollisionShape3D:
				c.disabled = not door_shut

func grips_in_reach() -> int:
	var n := 0
	for r in access_grips:
		if actor.can_reach(r):
			n += 1
	return n

# ---- access colliders: flats outside the clear surfaces (never inside the free space) ----------------------------------------------------------

## A cylinder about the ship axis (Godot X) from x0 to x1: free inside (wall flats tangent outside r) or free outside (flats inside r, their
## edges on it). Each hole {c (axis point), n (radial), r, patch} is cut out of the flats it crosses; the cut-out pieces go to `patch`.
func _cyl_x(x0: float, x1: float, r: float, free_inside: bool, holes: Array) -> void:
	var n_flat := TRUNK_SIDES * 2
	var half := PI / n_flat
	for i in n_flat:
		var ang := TAU * i / n_flat
		var nrm := Vector3(0, cos(ang), sin(ang))
		var rc := r + SLAB * 0.5 if free_inside else r * cos(half) - SLAB * 0.5
		var width := (2.0 * r * tan(half) if free_inside else 2.0 * r * sin(half)) * 1.02
		var pieces := [[x0, x1, null]]
		for h in holes:
			var hn: Vector3 = h["n"]
			if nrm.dot(hn) <= 0.0:
				continue
			var b := (rc - SLAB * 0.5) * nrm.cross(hn).length()      # the slab's inboard face: its least offset from the hole's radial
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
				if h["patch"] != null:                 # the closure's piece; an open hole (patch null) has none
					next.append([maxf(lo, q[0]), minf(hi, q[1]), h["patch"]])
				if hi < q[1]: next.append([hi, q[1], null])
			pieces = next
		for q in pieces:
			if q[1] - q[0] < 1e-3:
				continue
			var sb := _slab(Vector3((q[0] + q[1]) * 0.5, 0, 0) + nrm * rc, Basis(Vector3.RIGHT, nrm, Vector3.RIGHT.cross(nrm)), Vector3(q[1] - q[0], SLAB, width))
			if q[2] != null:
				(q[2] as Array).append(sb)

## A bore of radius r about the line c + n a (n radial from the ship axis), its wall flats from a0(b) to a1(b) (b the flat's offset across
## the bore, sideways of X).
func _radial_bore(c: Vector3, n: Vector3, r: float, a0: Callable, a1: Callable) -> void:
	var side := n.cross(Vector3.RIGHT).normalized()
	for i in TRUNK_SIDES:
		var psi := TAU * i / TRUNK_SIDES
		var e := Vector3.RIGHT * cos(psi) + side * sin(psi)
		var b := r * sin(psi)
		var lo: float = a0.call(b, e)
		var hi: float = a1.call(b, e)
		if hi - lo < 1e-3:
			continue
		_slab(c + e * (r + SLAB * 0.5) + n * (lo + hi) * 0.5, Basis(n, e, n.cross(e)), Vector3(hi - lo, SLAB, 2.0 * r * tan(PI / TRUNK_SIDES) * 1.02))

## Mitered tube legs from point i to i+1 (miter planes through the joints; the last leg ends flat, open).
func _mitered(pts: Array, miters: Array, r: float, first: int) -> void:
	for i in range(first, pts.size() - 1):
		var p: Vector3 = pts[i]
		var q: Vector3 = pts[i + 1]
		var d := (q - p).normalized()
		var u := d.cross(Vector3.RIGHT if absf(d.x) < 0.9 else Vector3.UP).normalized()
		var v := d.cross(u)
		for k in TRUNK_SIDES:
			var psi := TAU * k / TRUNK_SIDES
			var e := u * cos(psi) + v * sin(psi)
			var m0: Vector3 = miters[i]
			var t0 := -(e * r).dot(m0) / d.dot(m0)
			var t1 := (q - p).length()
			if i + 1 < miters.size():
				var m1: Vector3 = miters[i + 1]
				t1 = (q - p - e * r).dot(m1) / d.dot(m1)
			_slab(p + e * (r + SLAB * 0.5) + d * (t0 + t1) * 0.5, Basis(d, e, d.cross(e)), Vector3(t1 - t0, SLAB, 2.0 * r * tan(PI / TRUNK_SIDES) * 1.02))

func _build_access(a: Dictionary, shift: Vector3) -> void:
	port_patch = []
	door_patch = []
	var tr: float = a["trunk"]["clear_radius_m"]
	var c := g(a["port"]["centre_m"]) + shift
	var n := g(a["port"]["radial"]).normalized()
	var pc: float = a["port"]["clear_radius_m"]
	var dx: Array = a["drum"]["x_m"]
	var r0: float = a["drum"]["inner_radius_m"]
	var rr: float = a["drum"]["outer_radius_m"]
	# the trunk round the port (closed ends: its aft end and the stage boundary forward), the port's bore cut out
	var x0: float = float(a["trunk"]["x_m"][0]) + shift.x
	var x1: float = float(a["trunk"]["x_m"][1]) + shift.x
	_cyl_x(x0, x1, tr, true, [{"c": c, "n": n, "r": pc, "patch": null}])
	var side := 2.0 * tr / cos(PI / TRUNK_SIDES) + 2.0 * SLAB
	for xe in [x0 - SLAB * 0.5, x1 + SLAB * 0.5]:
		_slab(Vector3(xe, 0, 0), Basis.IDENTITY, Vector3(SLAB, side, side))
	# the port's bore from the trunk wall to the drum's inner wall
	_radial_bore(c, n, pc, func(b, _e): return sqrt(maxf(tr * tr - b * b, 0.0)), func(b, _e): return sqrt(maxf(r0 * r0 - b * b, 0.0)))
	# the drum: inner wall (port gate across its hole), outer wall (drum door across its hole), end walls
	_cyl_x(float(dx[0]) + shift.x, float(dx[1]) + shift.x, r0, false, [{"c": c, "n": n, "r": pc, "patch": port_patch}])
	_cyl_x(float(dx[0]) + shift.x, float(dx[1]) + shift.x, rr, true, [{"c": c, "n": n, "r": pc, "patch": door_patch}])
	var nw := TRUNK_SIDES * 2
	for xe in [float(dx[0]) + shift.x - SLAB * 0.5, float(dx[1]) + shift.x + SLAB * 0.5]:
		for i in nw:
			var ang := TAU * i / nw
			var nrm := Vector3(0, cos(ang), sin(ang))
			_slab(Vector3(xe, 0, 0) + nrm * (r0 + rr) * 0.5, Basis(Vector3.RIGHT, nrm, Vector3.RIGHT.cross(nrm)), Vector3(SLAB, rr - r0, 2.0 * rr * tan(PI / nw) * 1.02))
	# the drum door's bore through the running gap and the tube's first leg to the first miter, then the mitered legs and the run
	var pts := []
	for p in a["tube"]["points_m"]:
		pts.append(g(p) + shift)
	var mit := []
	for m in a["tube"]["miters"]:
		mit.append(g(m))
	var rt: float = a["tube"]["clear_radius_m"]
	var j1: Vector3 = pts[1]
	var m1: Vector3 = mit[1]
	_radial_bore(c, n, rt, func(b, _e): return sqrt(maxf(rr * rr - b * b, 0.0)), func(_b, e): return (j1 - c - e * rt).dot(m1) / n.dot(m1))
	_mitered(pts, mit, rt, 1)
	# grip anchors on the way (not colliders): the trunk's rails and the drum's and tube's rails and stiles
	access_grips = []
	for h in stages["trunk"]["handholds"] + a["grips"]:
		var rail := _rail(h, shift, false)
		rail.collision_layer = 0
		rail.collision_mask = 0
		world.add_child(rail)
		access_grips.append(rail)

## The rungs within the hand's reach of the body centre.
func rungs_in_reach() -> int:
	var n := 0
	for r in tube_rungs:
		if actor.can_reach(r):
			n += 1
	return n

## The furthest line parameter the closures allow: past the port only with the gate fully open, out of the restraint pose only with the drum
## door fully open (DYN-027 gate in the host), never past the host's chapter end; back up the run no further than the run top.
func line_limits() -> Array:
	var hi := minf(tube_length(), s_stop)
	var lo := s_run if not from_access else 0.0
	if from_access and gate_fn.is_valid():
		var open: Dictionary = gate_fn.call()
		if tube_s <= s_port + 1e-9 and not open["STATIONARY"]:
			hi = minf(hi, s_port)
		if tube_s <= s_hold + 1e-9 and not open["RING"]:
			hi = minf(hi, s_hold)
	if tube_s >= s_hold - 1e-9:
		lo = maxf(lo, s_hold)                  # no way back through a shut port gate (the way back is not a stage)
	for c in coasts:                         # a stop can only be where a grip is in reach: before a coast, not in it
		if tube_s <= float(c[0]) + 1e-9 and hi > float(c[0]) and hi < float(c[1]):
			hi = float(c[0])
	return [lo, hi]                         # doubles (a Vector2 would round the restraint pose)

## The coast in progress at s (moving forward), or [].
func coast_at(s: float) -> Array:
	for c in coasts:
		if s >= float(c[0]) - 1e-9 and s < float(c[1]):
			return c
	return []

## Line length between s0 and s1 on which the hands can act (outside the coasts).
func _held_length(s0: float, s1: float) -> float:
	var d := absf(s1 - s0)
	for c in coasts:
		d -= maxf(0.0, minf(maxf(s0, s1), float(c[1])) - maxf(minf(s0, s1), float(c[0])))
	return maxf(d, 0.0)

## The largest speed for this step from which the hands can still slow to `v_end` within `gap` in whole steps of LADDER_ACCEL.
func _brake(v_end: float, gap: float, dt: float) -> float:
	var ad := LADDER_ACCEL * dt
	return maxf(0.0, -ad + sqrt(ad * ad + v_end * v_end + 2.0 * LADDER_ACCEL * maxf(gap, 0.0)))

func _step_ladder(dt: float) -> void:
	if beat != "TUBE" or actor == null or arrived:
		return
	_apply_frame()
	if from_access and gate_fn.is_valid():
		var open: Dictionary = gate_fn.call()
		set_closures(not open["STATIONARY"], not open["RING"])
	var pace: float = stages["tube"]["review_speed_m_s"]
	var cmd := 1.0 if auto_descend else climb_cmd
	var lim := line_limits()
	var lo: float = lim[0]
	var hi: float = lim[1]
	# the requested pace, braked so the body comes to rest at either limit
	var room := hi - tube_s if cmd > 0.0 else tube_s - lo
	var speed := minf(absf(cmd) * pace, _brake(0.0, room, dt))
	# and slowed before each pose where the line turns, so the hands never change the body's velocity faster than LADDER_ACCEL
	# (the braking room ahead counts only where a grip is in reach: across a coast the speed cannot change)
	var ahead := pace * pace / (2.0 * LADDER_ACCEL) + pace * dt
	for c in coasts:
		ahead += float(c[1]) - float(c[0])
	for k in range(line_s.size()):
		var gap: float = (float(line_s[k]) - tube_s) * signf(cmd)
		if gap > 1e-9 and gap <= ahead:
			speed = minf(speed, _brake(float(line_vmax[k]), _held_length(tube_s, float(line_s[k])), dt))
	var target := signf(cmd) * speed
	var coasting := from_access and climb_v > 0.0 and not coast_at(tube_s).is_empty()
	if not coasting:
		climb_v = move_toward(climb_v, target, LADDER_ACCEL * dt)
	var next := clampf(tube_s + climb_v * dt, minf(lo, tube_s), maxf(hi, tube_s))
	if room < 2e-3 and absf(climb_v) < LADDER_ACCEL * dt * 1.01:
		next = clampf(hi if cmd > 0.0 else lo, minf(lo, tube_s), maxf(hi, tube_s))
		climb_v = 0.0
	var here := line_at(tube_s)
	var there := line_at(next)
	var v: Vector3 = ((there[0] as Vector3) - (here[0] as Vector3)) / dt
	# the hands keep the body on the line: the commanded speed plus a gentle correction of any drift, and its axis along the pose
	var want: Vector3 = there[0]
	if coasting:                                   # the body keeps the velocity of the push-off (the hands are off)
		pass
	elif from_access and not coast_at(next).is_empty():
		actor.ladder_v = v                         # the push-off: exactly the line's velocity (a correction would grow into drift across the coast)
	else:
		actor.ladder_v = v + (want - (actor.global_position + v * dt)) / dt * 0.1
	actor.ladder_up = there[1]
	tube_s = next
	restrained = from_access and absf(tube_s - s_hold) < 1e-9 and climb_v == 0.0
	hand_log.append({"s": tube_s, "r": absf(actor.global_position.y), "p": actor.global_position, "hand_n": actor.hand_impulse / dt, "v": actor.ladder_v,
		"reach": rungs_in_reach(), "grips": grips_in_reach() if tube_s < s_run else -1, "contacts": actor.contacts, "cv": climb_v, "phase": there[2],
		"frac": drum_frac, "field": field.accel(actor.global_position, Vector3.ZERO), "restrained": restrained, "coast": coasting})
	if tube_s >= tube_length() - 1e-6:
		actor.off_ladder()                        # the feet are 1 cm over the well's deck: the body steps off and stands
		arrived = true

func ticks(n: int) -> void:
	for i in n:
		await get_tree().physics_frame

func _radial(p: Vector3) -> float:
	var t: Dictionary = stages["trunk"]
	var a := g(t["axis_m"][0])
	var axis := (g(t["axis_m"][1]) - a).normalized()
	return (p - a).cross(axis).length()

## Everything the check measures, in one coroutine. Returns the WF_GODOT_BODY dictionary.
func run_check() -> Dictionary:
	var checks := []
	var fail := []
	var prof: Dictionary = dyn["profiles"]["human_iva"]
	var vmax: float = prof["test_push_dv_m_s"]
	var tol_dv := 1e-3
	var trunk: Dictionary = stages["trunk"]
	var clear: float = trunk["clear_radius_m"]
	# ---- SPINE: grab, push, drift, catch on the real rails ----------------------------------------------------------------------------------------
	build_spine(false)
	await ticks(2)
	var a := actor
	var start := rail_by_id(START_RAIL)
	var target := rail_by_id(CATCH_RAIL)
	var x_start := a.global_position.x
	var p_start := a.global_position
	var grabbed: bool = a.grab(start)
	await ticks(5)
	var pushed: bool = a.push(PUSH_DIR, -1.0, Vector3.ZERO)       # the full profile impulse m * test_push_dv, through the centre (PROTOTYPE hand line)
	a.walk_dir = PUSH_DIR                                          # a held key: with no floor and no field it does nothing
	await ticks(2)
	var dv := a.linear_velocity.length()
	var drift := 0
	var vmin := dv
	var vmaxd := dv
	var rad_max := _radial(a.global_position)
	var lateral := 0.0
	while not a.can_reach(target) and drift < 1200:
		await ticks(1)
		drift += 1
		vmin = minf(vmin, a.linear_velocity.length())
		vmaxd = maxf(vmaxd, a.linear_velocity.length())
		rad_max = maxf(rad_max, _radial(a.global_position))
		var d := a.global_position - p_start
		lateral = maxf(lateral, Vector2(d.y, d.z).length())
	var caught: bool = a.grab(target)
	var stop := -1
	for i in 30:
		await ticks(1)
		if stop < 0 and a.linear_velocity.length() < 1e-2:
			stop = i + 1
	var real_ids: Array = trunk["handholds"].map(func(h): return h["anchor_id"])
	var caught_id: String = a.grip.anchor_id if a.grip else ""
	var travelled := x_start - a.global_position.x
	checks.append({"id": "spine_grab_push_catch", "ok": grabbed and pushed and caught, "actual": [grabbed, pushed, caught]})
	checks.append({"id": "spine_push_dv_within_profile", "ok": dv <= vmax + tol_dv and dv > 0.5 * vmax, "actual": dv, "limit": vmax})
	checks.append({"id": "spine_no_thrust_no_braking", "ok": vmaxd - vmin < 1e-6, "actual": vmaxd - vmin, "tol": 1e-6, "note": "speed constant between release and catch with a movement key held"})
	checks.append({"id": "spine_drift_straight", "ok": lateral < 1e-4 and travelled > 3.0, "actual": lateral, "tol_m": 1e-4, "travelled_m": travelled, "note": "no field in DOCKED"})
	checks.append({"id": "spine_catch_stops", "ok": stop > 0 and stop <= 30 and a.linear_velocity.length() < 1e-2, "actual": a.linear_velocity.length(), "ticks": stop, "limit_s": 0.5})
	checks.append({"id": "spine_catch_real_rail", "ok": caught_id.begins_with("Crew_Trunk_") and caught_id in real_ids and caught_id != START_RAIL, "actual": caught_id})
	checks.append({"id": "spine_inside_clear_radius", "ok": rad_max + prof["radius_m"] <= clear, "actual": rad_max + prof["radius_m"], "limit_m": clear, "max_radial_m": rad_max})
	# branch openings: from the axis at each rig opening a ray outward passes the trunk wall and stops at the closed end of its bore; at a
	# plain wall angle it stops at the wall
	var space := get_world_3d().direct_space_state
	var ray_hit := func(from: Vector3, dir: Vector3) -> float:
		var q := PhysicsRayQueryParameters3D.create(from, from + dir * (clear + BRANCH_STUB + 1.0), TOUR_LAYER, [a.get_rid()])
		var hit := space.intersect_ray(q)
		return (hit["position"] - from).length() if hit else INF
	var branch_rows := []
	var branches_ok := true
	for o in trunk.get("openings", []):
		var th := deg_to_rad(float(o["theta_deg"]))
		var n := g([0.0, cos(th), sin(th)]).normalized()
		var hit_d: float = ray_hit.call(Vector3(float(o["x_m"]), 0, 0), n)
		var ok := absf(hit_d - (clear + BRANCH_STUB)) < 0.05
		branches_ok = branches_ok and ok
		branch_rows.append({"name": o["name"], "hit_m": hit_d, "ok": ok})
	var wall_d: float = ray_hit.call(Vector3(93.0, 0, 0), g([0.0, cos(deg_to_rad(120.0)), sin(deg_to_rad(120.0))]).normalized())
	checks.append({"id": "spine_branch_openings", "ok": branches_ok and branch_rows.size() > 0 and absf(wall_d - clear) < 0.05,
		"actual": branch_rows, "wall_hit_m": wall_d, "expect_m": [clear + BRANCH_STUB, clear], "note": "PROTOTYPE closed branch stubs"})
	var spine := {"push_dv_m_s": dv, "limit_m_s": vmax, "drift_ticks": drift, "travelled_m": travelled, "catch_stop_ticks": stop, "start_rail": START_RAIL, "catch_rail": caught_id,
		"max_radial_m": rad_max, "clear_radius_m": clear, "branch_openings": branch_rows.size()}
	# ---- RING A: walk the A1 aisle on the real deck -----------------------------------------------------------------------------------------------
	var floor_fx := fixture("RING_A_FLOOR")
	build_ring("RING_A")
	a = actor
	await ticks(180)
	var angle0: float = ring_angle_fn.call() if ring_angle_fn.is_valid() else 0.0
	a.walk_dir = Vector3.RIGHT
	var gmin := INF
	var gmax := -INF
	var always := true
	for i in 90:
		await ticks(1)
		var foot: Vector3 = a.global_position - a.up_now * (prof["height_m"] * 0.5)
		var gg := field.g_of(field.eval(WfFrames.from_vec(foot), WfFrames.from_vec(a.v_solved)))
		gmin = minf(gmin, gg)
		gmax = maxf(gmax, gg)
		always = always and a.standing
	var walk_v := a.v_solved.x
	var foot_r: float = Vector2(a.global_position.y, a.global_position.z).length() + prof["height_m"] * 0.5
	checks.append({"id": "ring_walk_floor_contact", "ok": always, "actual": always})
	checks.append({"id": "ring_walk_floor_g", "ok": absf(gmin - floor_fx["expect_g"]) < 1e-3 and absf(gmax - floor_fx["expect_g"]) < 1e-3, "actual": [gmin, gmax], "expected": floor_fx["expect_g"], "tol": 1e-3})
	checks.append({"id": "ring_walk_pace", "ok": absf(walk_v - vmax) < 0.02, "actual": walk_v, "expected": vmax})
	checks.append({"id": "ring_walk_on_deck_radius", "ok": absf(foot_r - float(dyn["rings"][0]["floor_radius_m"])) < 0.05, "actual": foot_r, "expected": dyn["rings"][0]["floor_radius_m"]})
	# the display: the proxy turns with ring A's pivot and matches WfFrames.to_ship of the physics position (standing still, so the copy is current)
	a.walk_dir = Vector3.ZERO
	await ticks(60)
	await get_tree().process_frame
	await get_tree().process_frame
	if ring_pivot != null and ring_angle_fn.is_valid():
		var ang: float = ring_angle_fn.call()
		var rate: float = ring_rate_fn.call()
		var w_x: float = WfFrames.ring_omega(dyn, 0, "COAST")[0]
		var ship_pos = WfFrames.to_ship(WfFrames.from_vec(a.global_position), WfFrames.v3(0, 0, 0), ring_centre_x(), ang, WfFrames.v3(w_x, 0, 0))[0]
		var err := (body_vis.global_position - WfFrames.to_vec(ship_pos)).length()
		checks.append({"id": "ring_display_turns_with_ring", "ok": err < 2e-3 and view_root.get_parent() == ring_pivot and absf(ang - angle0) > 0.05, "actual": err, "tol_m": 2e-3,
			"ring_angle_rad": ang, "angle_advanced_rad": ang - angle0})
		checks.append({"id": "ring_display_sense", "ok": signf(rate) == signf(w_x), "actual": rate, "expected_sign": signf(w_x)})
	# ---- Coriolis beat: a dropped object in each ring's sector-1 aisle, on that ring's own boxes ---------------------------------------------------
	var deflection := {}
	for zone in ["RING_A", "RING_B"]:
		var k := WfFrames.ring_index(zone)
		var fx := fixture("RING_%s_CORIOLIS_RADIAL" % "AB"[k])
		build_ring(zone, true)
		var t := tool
		var z0 := t.position.z
		for i in 240:
			await ticks(1)
			if t.contact_step >= 0:
				break
		await ticks(5)
		var defl := -(t.contact_pos.z - z0)                  # ring-frame tangential offset, Blender +Y (= -Godot z)
		# the fall at the A1 deck is toward Blender +Z, the fixture's velocity direction, so the deflection has the sign of the fixture's Y
		var want_sign := signf(fx["expect"][1])
		deflection[zone] = defl
		checks.append({"id": "coriolis_drop_%s" % zone, "ok": t.contact_step >= 0 and signf(defl) == want_sign and absf(defl) > 0.01 and absf(defl) < 0.3, "actual": defl, "expected_sign": want_sign,
			"fixture": fx["id"], "fixture_g_per_m_s": fx["expect_g"], "geometry": "%s1 aisle and landing boxes" % "AB"[k]})
	checks.append({"id": "coriolis_rings_opposite", "ok": signf(deflection["RING_A"]) != signf(deflection["RING_B"]), "actual": deflection})
	var text := coriolis_text("RING_A", deflection["RING_A"])
	checks.append({"id": "coriolis_text_not_comfort", "ok": text.contains("not a comfort limit"), "actual": text})
	for c in checks:
		if not c["ok"]:
			fail.append(c["id"])
	return {"result": "PASS" if fail.is_empty() else "FAIL", "status": "SIMULATION_ONLY", "profile": "human_iva", "survivor_identity": null, "geometry": "rig dynamics.stages (trunk, ring_rooms A1 and B1 aisle + landing)", "spine": spine,
		"ring": {"floor_g_min": gmin, "floor_g_max": gmax, "expect_g": floor_fx["expect_g"], "walk_m_s": walk_v}, "coriolis_deflection_m": deflection,
		"text": text, "checks": checks, "fail": fail}

func coriolis_text(zone: String, defl: float) -> String:
	var fx := fixture("RING_%s_CORIOLIS_TANGENTIAL" % ("A" if zone == "RING_A" else "B"))
	# the deck point moves at w x r: Blender Y of that velocity is -w_x * z_deck (the A1 deck is at +Z), the spinward side of the deflection
	var w_x: float = WfFrames.ring_omega(dyn, WfFrames.ring_index(zone), "COAST")[0]
	var spinward_y := -signf(w_x) * signf(deck_y(zone))
	return "Coriolis %.4f g at 1 m/s (DYN-003); the dropped object lands %.0f cm %s: %s." % [fx["expect_g"], absf(defl) * 100.0,
		"spinward" if signf(defl) == spinward_y else "antispinward", NOT_COMFORT]

# ---- interactive -------------------------------------------------------------------------------------------------------------------------------

func enter(build := true) -> void:
	active = true
	layer.visible = true
	camera.current = true
	if build:
		build_spine()

func leave() -> void:
	active = false
	layer.visible = false
	body_vis.visible = false
	tool_vis.visible = false
	if actor:
		actor.walk_dir = Vector3.ZERO
	_place_view(self, Vector3.ZERO)

func ref_basis() -> Basis:
	var up := Vector3.UP
	if actor and actor.field_now.length() > WfCrewBody.GRIP_FIELD_G * actor.g0:
		up = actor.up_now
	var fwd := Vector3.RIGHT - up * Vector3.RIGHT.dot(up)
	if fwd.length() < 0.1:
		fwd = Vector3.BACK - up * Vector3.BACK.dot(up)
	return Basis.looking_at(fwd.normalized(), up)

func look_dir() -> Vector3:
	return -(ref_basis() * Basis.from_euler(Vector3(pitch, yaw, 0))).z

func handle_input(e: InputEvent) -> bool:
	if not active:
		return false
	if e is InputEventMouseMotion and e.button_mask & MOUSE_BUTTON_MASK_RIGHT:
		yaw -= e.relative.x * 0.004
		pitch = clampf(pitch - e.relative.y * 0.004, -1.5, 1.5)
		return true
	# ACI-05: grab, release and push are registry actions (WfInput); the crew physics behind them is unchanged.
	if e.is_action_pressed("player.grab") and not e.is_echo():
		if actor and actor.grab_nearest(rails):
			WfInput.performed("player.grab")
		return true
	if e.is_action_pressed("player.release") and not e.is_echo():
		if actor and actor.grip != null:
			actor.release()
			WfInput.performed("player.release")
		return true
	if e.is_action_pressed("player.push") and not e.is_echo():
		if actor and actor.push(look_dir(), -1.0, Vector3.ZERO):
			WfInput.performed("player.push")
		return true
	if WfInput.pressed(e):
		match WfInput.key_of(e, ["body"]):            # ACI-10: body.* actions, matched by their default keys
			KEY_1: build_spine()
			KEY_2: build_ring("RING_A", true, false)
			KEY_3: build_ring("RING_B", true, false)
			KEY_V: view_out = not view_out
			KEY_K:
				for m in debug_meshes:
					m.visible = not m.visible
				for c in capsule_vis:
					c.visible = not c.visible
			KEY_T: drop_tool()
			_: return false
		return true
	return false

func drop_tool() -> void:
	if tool and actor:
		tool.freeze = false
		var dx := 1.0 if actor.position.x < 0.0 else -1.0
		tool.position = Vector3(clampf(actor.position.x + dx, -1.2, 1.2), actor.position.y, 0.0) + actor.up_now * DROP_HEIGHT
		tool.linear_velocity = Vector3.ZERO
		tool.contact_step = -1
		drop_z0 = tool.position.z
		drops += 1

## U02: the last T drop's landing offset (ring-frame tangential, Blender +Y, m), or NAN while it falls or before any drop.
func drop_deflection() -> float:
	if drops == 0 or tool == null or tool.contact_step < 0:
		return NAN
	return -(tool.contact_pos.z - drop_z0)

func _physics_process(_dt: float) -> void:
	if beat == "TUBE" and actor != null and not arrived:
		climb_cmd = WfInput.strength("player.move_back") - WfInput.strength("player.move_forward") if active else 0.0
		_step_ladder(_dt)
		return
	if not active or actor == null:
		return
	var b := ref_basis() * Basis.from_euler(Vector3(0, yaw, 0))
	var d := Vector3.ZERO
	d -= b.z * (WfInput.strength("player.move_forward") - WfInput.strength("player.move_back"))
	d += b.x * (WfInput.strength("player.move_right") - WfInput.strength("player.move_left"))
	actor.walk_dir = d if auto_walk == Vector3.ZERO else auto_walk
	if d != Vector3.ZERO and actor.standing and actor.v_solved.length() > 0.2:
		WfInput.performed("player.move_forward")      # walked on the deck (the move_deck lesson's proof)

func _process(_dt: float) -> void:
	if actor == null:
		return
	body_vis.transform = actor.global_transform
	if beat == "TUBE" and from_access and tube_s > s_hold and ring_pivot != null and view_root.get_parent() != ring_pivot:
		_place_view(ring_pivot, Vector3(ring_centre_x(), 0, 0) - ring_pivot.position)      # past the open door: drum synced, same angle as the ring
	if tool != null:
		tool_vis.transform = tool.global_transform
	if not active:
		return
	WfInput.context = "body"
	var lk := WfInput.take_look()                   # MOB-001: the touch look turns the body's view as a right-drag does
	yaw -= lk.x
	pitch = clampf(pitch - lk.y, -1.5, 1.5)
	if beat == "SPINE" and actor.grip != null:
		WfInput.discover("grab")                    # ACI-05: weightless, holding a rail: the safe moment (Tale 27 STG-001)
	elif actor.standing and field.ring_zone():
		WfInput.discover("move_deck")
	if model != null:
		model.visible = view_out or ext_offset != Vector3.INF         # first person: the camera is at the head
		if anim != null:
			var want := "walk" if actor.standing and actor.v_solved.length() > 0.1 and anim.has_animation("walk") else "idle"
			if want != anim_now and anim.has_animation(want):
				anim_now = want
				anim.play(want)
	hud.custom_minimum_size.x = maxf(300.0, get_viewport().get_visible_rect().size.x - 360.0)       # stays left of the stops panel
	hud.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	var strong := actor.field_now.length() > WfCrewBody.GRIP_FIELD_G * actor.g0
	var look := ref_basis() * Basis.from_euler(Vector3(pitch, yaw, 0))
	var local: Transform3D
	if ext_offset != Vector3.INF:
		var pos: Vector3 = actor.global_position + ext_offset
		var up: Vector3 = actor.up_now if strong else Vector3.UP
		local = Transform3D(Basis.looking_at(actor.global_position - pos, up), pos)
	elif view_out:
		var back := 2.4 if beat == "SPINE" else 1.5
		local = Transform3D(look, actor.global_position - look.z * back + actor.up_now * 0.3 * (1.0 if strong else 0.0) + (Vector3.UP * 0.3 if not strong else Vector3.ZERO))
	else:
		local = Transform3D(look, actor.global_position + (actor.up_now * 0.6 if strong else Vector3.UP * 0.25))
	camera.global_transform = view_root.global_transform * local
	var f := actor.field_now
	var t := "BODY MODE - SIMULATION_ONLY (human_iva, no survivor identity), real trunk and A1 aisle; PROTOTYPE: trunk branch openings end in closed 0.6 m stubs, hand line\n"
	t += "beat %s  zone %s  mode %s  field %.4f g  speed %.3f m/s  grip %s  %s\n" % [beat, field.zone, field.mode, f.length() / dyn["standard_gravity_m_s2"], actor.v_solved.length(),
		actor.grip.anchor_id if actor.grip else "-", "standing" if actor.standing else "free"]
	var m: Array = WfInput.labels(["player.grab", "player.push", "player.release", "player.move_forward", "player.move_left", "player.move_back", "player.move_right",
		"body.spine", "body.ring_a", "body.drop_tool", "body.view", "body.colliders", "tour.body_mode"])
	t += "%s grab · %s push (max %.2f m/s) · %s release · %s%s%s%s walk (floor) · %s spine · %s aisle · %s drop · %s view · %s colliders · %s review rail\n" % [m[0], m[1],
		actor.profile["test_push_dv_m_s"], m[2], m[3], m[4], m[5], m[6], m[7], m[8], m[9], m[10], m[11], m[12]]
	if field.ring_zone():
		var k := WfFrames.ring_index(field.zone)
		var fx := fixture("RING_%s_CORIOLIS_TANGENTIAL" % "AB"[k])
		t += "Coriolis %.4f g per 1 m/s (DYN-003): %s.\n" % [fx["expect_g"], NOT_COMFORT]
	hud.text = t

## Stills for review (needs a display): the spine start, mid-drift and catch; the aisle walk and the dropped object. `dir` is created.
func capture(dir: String) -> void:
	DirAccess.make_dir_recursive_absolute(dir)
	enter()
	await ticks(10)
	await _shot(dir, "body_1_spine_grip", Vector3(-2.6, 0.45, -0.3))
	actor.push(PUSH_DIR, -1.0, Vector3.ZERO)
	await ticks(150)
	await _shot(dir, "body_2_spine_drift", Vector3(2.6, 0.45, -0.3))
	var target := rail_by_id(CATCH_RAIL)
	while not actor.can_reach(target):
		await ticks(1)
	actor.grab(target)
	await ticks(40)
	await _shot(dir, "body_3_spine_catch", Vector3(2.6, 0.45, -0.3))
	build_ring("RING_A", true)
	await ticks(240)
	await _shot(dir, "body_4_aisle", Vector3(0.7, -0.6, -1.3))
	actor.walk_dir = Vector3.RIGHT
	await ticks(60)
	await _shot(dir, "body_5_aisle_walk", Vector3(0.9, -0.5, -1.8))
	ext_offset = Vector3.INF
	view_out = false
	await _shot(dir, "body_6_aisle_eye", Vector3.INF)
	ext_offset = Vector3.INF

func _shot(dir: String, name: String, off: Vector3) -> void:
	ext_offset = off
	for i in 3:
		await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(dir.path_join(name + ".png"))
