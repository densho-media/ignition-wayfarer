class_name WfExcursion
extends Node3D
## EXC-001 (owner direction 2026-10-26): one continuous, player-controlled excursion from the development station into Wayfarer, round a whole
## habitat ring and back, for either ring, without a reset. SIMULATION_ONLY; Godot holds no spacecraft facts: geometry, lines, doors, frames and
## modes come from the DOCKED package and the rig (`dynamics.stages`: boarding, trunk, access / access_b, tube / tube_b, circuit; `transitions`).
##
## How the trainee moves (the technique follows the field, never a key that adds force, DYN-016):
##   weightless (station, airlock, trunk, drum, crew tube) - hand over hand along the body lines of the rig (the M2 line technique): W/S pull the
##     body along the rails toward the view; where no rail is in reach it coasts at the speed it pushed off with and cannot stop or turn back;
##   spin gravity (a ring's sectors and corridors) - walking on the deck, a friction-limited foot contact, WASD and the mouse;
##   the crew-tube and landing-well ladders - the same line technique, rung by rung, with the spin load carried by the hands.
## E operates what is in reach (a hatch, a corridor or sector door, the drum's transfer cycle at the restraint pose, the ladder, a branch of the
## trunk); O asks the ship for its operating change at a trunk panel (DOCKED -> COAST: undock, spin up; COAST -> DOCKED: spin down, lock, dock),
## in the owner's step order (46 DYN-026) with the 1800 s study ramp time-lapsed x90 (PROTOTYPE display). Docked, the rings are stopped and
## locked (14_HULL_SERVICE!A8), so a ring walk always begins with an undock and ends with a dock before the station can be reached again.
## Closed hatches and doors are colliders across their openings and stop the line; an open one is open in both the collider and the mesh.

const LAYER := 1 << 9
const TIMELAPSE := 90.0          # PROTOTYPE display: simulated seconds of the ring ramp per real second (the 1800 s study ramp in 20 s)
const SYNC_S := 4.0              # PROTOTYPE display: the drum's synchronization ramp (MEC-019 cycle OPEN)
const CLOSURE_S := 1.5           # PROTOTYPE display: a hatch, gate or door from closed to open
const USE_REACH_S := 2.6         # PROTOTYPE: a hatch on the line is worked from its panel at the nearest rail stop, this far along the line
const BRANCH_REACH_S := 0.8       # the ring B branch is taken from this far along the trunk (the hands carry the body to it)
const USE_REACH_M := 1.4         # a corridor door or the ladder foot from this far
const LOOK_SENS := 0.0035
const EYE_UP := 0.62             # eye above the body centre, along the body axis (display)
const STATION_MOVE_S := 4.0      # PROTOTYPE display: the station's stand-off move at undock / dock

var manifest: Dictionary
var rig: Dictionary
var dyn: Dictionary
var stages: Dictionary
var ship: Node3D
var frames := {}                  # pivot id -> {node, rest, axis, angle, rate}
var closures := {}                # manifest closure name -> {node, binding, axis, base, value, target}
var ring_ids := ["", ""]          # rotor id of ring A, ring B
var drum_ids := ["", ""]
var check: WfExcursionCheck = null
var circ_doors := {}              # CIRC door id -> {node, rest, travel, value, target, collider, rec, ring}
var world := Node3D.new()
var builder: WfExcursionBuild
var hatch_colliders := {}         # STATION_HATCH / OUTER_HATCH / INNER_HATCH -> slab
var hatch := {}                   # id -> {value, target, gate: [s0, s1], kind}
var access_patch := [{}, {}]      # per ring: {port: [...], door: [...]}
var lines := {}
var actor: WfCrewBody
var field: WfFrameField
var ctl: WfModeController
var vest: Array = []              # WfVestibule per ring
var drum := [{}, {}]              # per ring: {mode: DESPUN / CLOSING / WAIT / RAMP / OPENING / SYNCED, to: side, t, from}
var station_root := Node3D.new()
var station_leaf: Node3D = null
var station_offset := 0.0         # 0 docked .. 1 at the stand-off
var station_target := 0.0
var view_root := Node3D.new()
var body_vis := Node3D.new()
var camera := Camera3D.new()
var lamp := OmniLight3D.new()
var lamps: Array = []
var world_env := WorldEnvironment.new()

# the trainee
var move := "LINE"                # LINE or WALK
var line: WfLine = null
var ls := 0.0
var lv := 0.0                     # the hands' speed along the line (m/s, + toward increasing s)
var coasting := false
var walk_zone := ""
var yaw := 0.0
var pitch := 0.0
var view_out := false
var prompt := ""
var refusal := ""
var refusal_t := 0.0
var cmd_override := INF           # check: the line command instead of the keys
var walk_override := Vector3.INF  # check: the walk direction instead of the keys
var log: Array = []

# the excursion's own record (what the HUD's checklist shows)
var visits := {"RING_A": {}, "RING_B": {}}
var progress := {}                # ring -> {boarded, entered, bins: PackedByteArray, circuit, back_in_ring, returned}
const BINS := 72

# HUD
var layer := CanvasLayer.new()
var hud_goal := Label.new()
var hud_prompt := Label.new()
var hud_status := Label.new()
var hud_check := Label.new()
var ring_map: Control = null

func _ready() -> void:
	if not FileAccess.file_exists("res://generated/manifest_docked.json"):
		var missing := Label.new()
		missing.text = "Generate the runtime package from the repository root:\npython3 tools/workflow.py runtime-export"
		missing.position = Vector2(32, 32)
		layer.add_child(missing)
		add_child(layer)
		return
	manifest = JSON.parse_string(FileAccess.get_file_as_string("res://generated/manifest_docked.json"))
	rig = JSON.parse_string(FileAccess.get_file_as_string("res://generated/wf_sim_rig.json"))
	dyn = rig["dynamics"]
	stages = dyn["stages"]
	if not stages.has("boarding") or not stages.has("circuit") or not stages.has("access_b"):
		push_error("EXC-001: the rig carries no excursion stages (contract 43); run runtime-export")
		return
	ship = load("res://generated/wayfarer_docked.glb").instantiate()
	add_child(ship)
	WfProductionLayer.apply(ship, manifest)
	WfFractalShield.apply(ship, manifest.get("look", {}).get("exterior", {}).get("grammar", {}).get("fractal_shield", {}))
	var by_name := {}
	_collect(ship, by_name)
	_mechanisms(by_name)
	_circ_doors(by_name)
	_door_signs()
	add_child(world)
	builder = WfExcursionBuild.new(world, LAYER)
	_build_world()
	_build_station()
	_build_lines()
	_environment(by_name)
	field = WfFrameField.new(dyn, "SHIP", "DOCKED")
	ctl = WfModeController.new(dyn, WfFrameField.new(dyn, "SHIP", "DOCKED"), "DOCKED")
	for k in 2:
		var v := WfVestibule.new(dyn, k)
		v.dp_equalized = true             # PROTOTYPE display input: the threshold is OPEN (PRESS-004)
		vest.append(v)
		drum[k] = {"mode": "DESPUN", "to": "", "t": 0.0, "from": 0.0}
	for r in ["RING_A", "RING_B"]:
		var bins := PackedByteArray()
		bins.resize(BINS)
		progress[r] = {"boarded": false, "entered": false, "bins": bins, "circuit": false, "back": false, "returned": false}
	_spawn()
	_hud()
	WfInput.context = "excursion"
	WfInput.touch_provider = touch_state            # MOB-001: the stick, the look drag and the contextual buttons on a touch device
	tree_exiting.connect(func(): WfInput.touch_provider = Callable(); WfInput.release_touch())
	print("WF_EXCURSION ready")                      # the web check waits for this line
	if "--check-excursion" in OS.get_cmdline_user_args():
		check = WfExcursionCheck.new()       # held: a RefCounted nobody holds is freed at its first await
		check.run(self)

# ---- package ---------------------------------------------------------------------------------------------------------------------------------

func _collect(node: Node, out: Dictionary) -> void:
	out[str(node.name)] = node
	for child in node.get_children():
		_collect(child, out)

func _mechanisms(by_name: Dictionary) -> void:
	# One pivot per ring and drum at its exported pivot (boarding.gd): the meshes each carries keep their placement when reparented.
	var mech: Dictionary = manifest["induction"]["mechanisms"]
	for group in ["rotors", "drums"]:
		for id in mech[group]:
			var b: Dictionary = mech[group][id]
			var pivot := Node3D.new()
			pivot.name = id
			pivot.position = Vector3(b["pivot_runtime_m"][0], b["pivot_runtime_m"][1], b["pivot_runtime_m"][2])
			ship.add_child(pivot)
			var axis := Vector3(b["axis_runtime"][0], b["axis_runtime"][1], b["axis_runtime"][2]).normalized()
			frames[id] = {"node": pivot, "rest": pivot.position, "axis": axis, "angle": 0.0, "rate": float(b.get("rad_per_s", 0.0))}
	frames["STATIONARY"] = {"node": ship, "rest": Vector3.ZERO, "axis": Vector3.RIGHT, "angle": 0.0, "rate": 0.0}
	for k in 2:
		var cx: float = dyn["rings"][k]["centre_x_m"]
		for id in mech["rotors"]:
			if absf(float(mech["rotors"][id]["pivot_runtime_m"][0]) - cx) < 0.01:
				ring_ids[k] = id
		for id in mech["drums"]:
			if str(mech["drums"][id].get("rotor", "")) == ring_ids[k]:
				drum_ids[k] = id
	var members := {}
	for record in manifest["nodes"]:
		if record.has("frame") and by_name.has(record["node"]):
			by_name[record["node"]].reparent(frames[record["frame"]]["node"], true)
		if record.has("closure"):
			members[record["closure"]] = members.get(record["closure"], []) + [record["node"]]
	for name in mech["closures"]:
		var b: Dictionary = mech["closures"][name]
		var f: Dictionary = frames[b["frame"]]
		var pivot := Node3D.new()
		pivot.name = name + "_Pivot"
		f["node"].add_child(pivot)
		var base := Vector3.ZERO
		var axis := Vector3.ZERO
		if b["kind"] == "turn":
			base = Vector3(b["pivot_runtime_m"][0], b["pivot_runtime_m"][1], b["pivot_runtime_m"][2]) - f["rest"]
			axis = Vector3(b["axis_runtime"][0], b["axis_runtime"][1], b["axis_runtime"][2]).normalized()
		pivot.position = base
		for node_name in members.get(name, []):
			by_name[node_name].reparent(pivot, true)
		# the snapshot shows every closure open; the excursion starts with them shut (normally closed)
		closures[name] = {"node": pivot, "binding": b, "axis": axis, "base": base, "value": 0.0, "target": 0.0}
	_apply_mechanisms()

func _circ_doors(by_name: Dictionary) -> void:
	for k in 2:
		var c: Dictionary = stages["circuit"]["RING_" + "AB"[k]]
		for d in c["doors"]:
			var node: Node3D = by_name.get(str(d["name"]))
			circ_doors[d["id"]] = {"node": node, "rest": node.position if node != null else Vector3.ZERO, "travel": float(d["travel_m"]),
				"value": 0.0, "target": 0.0, "collider": null, "rec": d, "ring": k}

## A sign over each circulation door, on both faces, naming the compartments it joins (the face's own side first). Carried by the ring.
func _door_signs() -> void:
	for id in circ_doors:
		var rec: Dictionary = circ_doors[id]["rec"]
		var f: Dictionary = frames[ring_ids[int(circ_doors[id]["ring"])]]
		var c := WfLine.g(rec["centre_m"])
		var up := Vector3(0.0, c.y - f["rest"].y, c.z - f["rest"].z).normalized() * -1.0
		var n := WfLine.g(rec["axes"][2]).normalized()
		var top := c + up * (float(rec["half_m"][1]) + 0.14)
		var pair: Array = rec["between"]
		for sgn in [1.0, -1.0]:
			var label := Label3D.new()
			# read from the compartment the face looks into, "here > beyond"; between is in ring order, between[0] on the -n side
			label.text = "%s  >  %s" % ([pair[1], pair[0]] if sgn > 0.0 else [pair[0], pair[1]])
			label.font_size = 40
			label.pixel_size = 0.0025
			label.modulate = Color(0.95, 0.96, 0.97)
			label.outline_modulate = Color(0.92, 0.40, 0.08)
			label.outline_size = 6
			var z: Vector3 = n * sgn
			label.transform = Transform3D(Basis(up.cross(z), up, z).orthonormalized(), top + z * 0.08 - f["rest"])
			f["node"].add_child(label)

func _apply_mechanisms() -> void:
	for id in frames:
		if id != "STATIONARY":
			frames[id]["node"].basis = Basis(frames[id]["axis"], frames[id]["angle"])
	for name in closures:
		var c: Dictionary = closures[name]
		var b: Dictionary = c["binding"]
		if b["kind"] == "slide":
			var d: Array = b["closed_offset_runtime_m"]
			c["node"].position = c["base"] + Vector3(d[0], d[1], d[2]) * (1.0 - c["value"])
		else:
			c["node"].basis = Basis(c["axis"], float(b["closed_angle_rad"]) * (1.0 - c["value"]))
	for id in circ_doors:
		var d: Dictionary = circ_doors[id]
		if d["node"] != null:
			d["node"].position = d["rest"] + Vector3(-d["travel"] * d["value"], 0, 0)

# ---- colliders ------------------------------------------------------------------------------------------------------------------------------

func _build_world() -> void:
	var open := ["Crew_Connector_Dock_Primary"]
	for k in 2:
		open.append("Crew_Port_%d_%d" % [k + 1, int(stages["circuit"]["RING_" + "AB"[k]]["landing_sector"])])
	builder.trunk(stages["trunk"], open)
	hatch_colliders = builder.boarding(stages["boarding"], float(stages["trunk"]["clear_radius_m"]))
	for h in stages["boarding"]["hatches"]:
		hatch[h["id"]] = {"value": 0.0, "target": 0.0, "gate": [float(h["s"][0]), float(h["s"][1])], "kind": h["kind"]}
	access_patch[0] = builder.access(stages["access"])
	access_patch[1] = builder.access(stages["access_b"])
	for k in 2:
		var doors := builder.circuit(stages["circuit"]["RING_" + "AB"[k]])
		for id in doors:
			circ_doors[id]["collider"] = doors[id]
	_closure_colliders()

## Colliders follow the closures: shut (any part not fully open) blocks.
func _closure_colliders() -> void:
	for id in hatch:
		WfExcursionBuild.set_enabled(hatch_colliders[id], hatch[id]["value"] < 0.999)
	for k in 2:
		var v: WfVestibule = vest[k] if vest.size() > k else null
		var port_open: bool = closures.get(_port_gate(k), {"value": 0.0})["value"] >= 0.999
		var door_open: bool = closures.get(_drum_door(k), {"value": 0.0})["value"] >= 0.999 and closures.get(_tube_hatch(k), {"value": 0.0})["value"] >= 0.999
		for b in access_patch[k]["port"]:
			WfExcursionBuild.set_enabled(b, not port_open)
		for b in access_patch[k]["door"]:
			WfExcursionBuild.set_enabled(b, not door_open)
	for id in circ_doors:
		var d: Dictionary = circ_doors[id]
		if d["collider"] != null:
			WfExcursionBuild.set_enabled(d["collider"], d["value"] < 0.999)

func _sector(k: int) -> int:
	return int(stages["circuit"]["RING_" + "AB"[k]]["landing_sector"])

func _port_gate(k: int) -> String:
	return "Crew_Port_%d_%d_Gate" % [k + 1, _sector(k)]

func _drum_door(k: int) -> String:
	return "Crew_Vestibule_%d_Door_%d" % [k + 1, _sector(k)]

func _tube_hatch(k: int) -> String:
	return "Crew_Tube_%d_%d_Hatch" % [k + 1, _sector(k)]

func _sector_leaf(k: int) -> String:
	return "Sector_Hatch_Leaf_%d_%d" % [k + 1, _sector(k)]

# ---- lines ------------------------------------------------------------------------------------------------------------------------------------

func _build_lines() -> void:
	var dt := 1.0 / Engine.physics_ticks_per_second
	var b: Dictionary = stages["boarding"]
	var L := WfLine.new()
	L.id = "BOARD"
	for q in b["line"]:
		L.add(WfLine.g(q["p"]), WfLine.g(q["up"]), str(q["phase"]), float(q["s_m"]))
		if q.has("junction"):
			L.marks[q["junction"]] = float(q["s_m"])
	for c in b["coasts_s_m"]:
		L.coasts.append([float(c[0]), float(c[1])])
	for h in b["hatches"]:
		L.gates.append({"id": h["id"], "s": [float(h["s"][0]), float(h["s"][1])]})
	L.finish(dt)
	lines["BOARD"] = L
	for k in 2:
		lines["ACCESS_" + "AB"[k]] = _access_line(k, dt)

func _access_line(k: int, dt: float) -> WfLine:
	var a: Dictionary = stages["access" if k == 0 else "access_b"]
	var t: Dictionary = stages["tube" if k == 0 else "tube_b"]
	var L := WfLine.new()
	L.id = "ACCESS_" + "AB"[k]
	L.zone = "RING_" + "AB"[k]
	for q in a["line"]:
		L.add(WfLine.g(q["p"]), WfLine.g(q["up"]), str(q["phase"]), float(q["s_m"]))
	for c in a.get("coasts_s_m", []):
		L.coasts.append([float(c[0]), float(c[1])])
	L.marks["port"] = float(a["port_s_m"])
	L.marks["hold"] = float(a["hold_s_m"])
	L.marks["run"] = float(a["run_s_m"])
	# the tube's radial run down to the landing well's deck (body_tour.build_tube): the climber line from the run top to standing on the deck
	var top: Vector3 = L.p[-1]
	var axis0 := WfLine.g(t["axis_m"][0])
	var axis1 := WfLine.g(t["axis_m"][1])
	var out := (axis1 - axis0).normalized()
	var cx: float = dyn["rings"][k]["centre_x_m"]
	var centre := Vector3(cx, 0, 0)
	var floor_r: float = dyn["rings"][k]["floor_radius_m"]
	var prof: Dictionary = dyn["profiles"]["human_iva"]
	var bottom: Vector3 = top + out * ((floor_r - float(prof["height_m"]) * 0.5 - 0.01) - (top - centre).dot(out))
	L.add(bottom, -out, "run", float(L.s[-1]) + (bottom - top).length())
	L.marks["deck"] = L.length()
	L.finish(dt)
	return L

# ---- the trainee --------------------------------------------------------------------------------------------------------------------------------

func _spawn() -> void:
	actor = WfCrewBody.new()
	actor.configure(dyn, "human_iva", field)
	actor.collision_layer = LAYER
	actor.collision_mask = LAYER
	world.add_child(actor)
	for ch in actor.get_children():
		if ch is MeshInstance3D:
			ch.visible = false
	add_child(view_root)
	view_root.add_child(camera)
	camera.near = 0.03
	camera.far = 2000.0
	camera.current = true
	lamp.omni_range = 9.0
	lamp.light_energy = 0.35
	camera.add_child(lamp)
	var cap := CapsuleMesh.new()
	cap.radius = actor.profile["radius_m"]
	cap.height = actor.profile["height_m"]
	var mi := MeshInstance3D.new()
	mi.mesh = cap
	var m := StandardMaterial3D.new()
	m.albedo_color = Color(0.95, 0.5, 0.1)
	mi.material_override = m
	body_vis.add_child(mi)
	view_root.add_child(body_vis)
	enter_line("BOARD", 0.0)
	# start looking down the boarding line (toward the tunnel and Wayfarer)
	var d := ref_basis().inverse() * line.tangent(0.0)
	yaw = atan2(-d.x, -d.z)
	pitch = asin(clampf(d.y, -1.0, 1.0))

## snap: the body is already at the line's pose there (a line handover); otherwise (the ladder taken from the deck) the hands draw it onto
## the line at no more than the line's pace (_step_line), never by a jump.
func enter_line(id: String, s0: float, snap := true) -> void:
	line = lines[id]
	move = "LINE"
	ls = clampf(s0, 0.0, line.length())
	lv = 0.0
	coasting = false
	var at := line.at(ls)
	if snap:
		actor.global_position = at[0]
	actor.linear_velocity = Vector3.ZERO
	actor.angular_velocity = Vector3.ZERO
	actor.walk_dir = Vector3.ZERO
	actor.on_ladder(Vector3.ZERO)
	actor.ladder_up = at[1]
	_set_body_height(id)
	_field_for_line()
	_log("line", {"line": id, "s": snappedf(ls, 0.001)})

## Ring B's access is the tucked technique (excursion.tuck): the proxy capsule takes the line's body length there and unfolds on the run.
func _set_body_height(id: String) -> void:
	var h: float = actor.profile["height_m"]
	if id == "ACCESS_B" and stages["access_b"].get("tucked", false) and ls < float(lines[id].marks["run"]) - 1e-6:
		h = float(stages["access_b"]["body_height_m"])
	for ch in actor.get_children():
		if ch is CollisionShape3D and ch.shape is CapsuleShape3D and absf((ch.shape as CapsuleShape3D).height - h) > 1e-6:
			(ch.shape as CapsuleShape3D).height = h

func tucked() -> bool:
	for ch in actor.get_children():
		if ch is CollisionShape3D and ch.shape is CapsuleShape3D:
			return (ch.shape as CapsuleShape3D).height < float(actor.profile["height_m"]) - 1e-6
	return false

func enter_walk(zone: String) -> void:
	move = "WALK"
	walk_zone = zone
	actor.off_ladder()
	_set_body_height("")
	field.set_state(zone, "COAST")
	field.alpha = PackedFloat64Array([0.0, 0.0, 0.0])
	_log("walk", {"zone": zone, "pos": _vec(actor.global_position)})

func ring_index() -> int:
	if move == "WALK":
		return WfFrames.ring_index(walk_zone)
	return WfFrames.ring_index(line.zone)

## The field the line's body feels: the SHIP frame (zero in DOCKED and COAST), or on an access line the drum frame (the drum's fraction of the
## ring's spin, with its Euler term), which is the ring's own frame once synchronized.
func _field_for_line() -> void:
	if line.zone == "SHIP":
		field.set_state("SHIP", ctl.mode if ctl != null else "DOCKED")
		return
	var k := WfFrames.ring_index(line.zone)
	field.set_state(line.zone, "COAST")
	var w0 := WfFrames.ring_omega(dyn, k, "COAST")
	var rw: float = w0[0]
	var v: WfVestibule = vest[k] if vest.size() > k else null
	var frac := 0.0 if v == null or absf(rw) < 1e-12 else v.drum_w / rw
	var dfrac := 0.0 if v == null or absf(rw) < 1e-12 else v.alpha() / rw
	if ls > float(line.marks["hold"]) + 1e-6 and drum[k]["mode"] == "SYNCED":
		frac = 1.0
	field.w = WfFrames.mul(w0, frac)
	field.alpha = WfFrames.mul(w0, dfrac)

# ---- input ---------------------------------------------------------------------------------------------------------------------------------------

func _unhandled_input(e: InputEvent) -> void:
	if actor == null:
		return
	if e is InputEventMouseButton and e.pressed and e.button_index == MOUSE_BUTTON_LEFT and Input.mouse_mode != Input.MOUSE_MODE_CAPTURED:
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
		return
	if e is InputEventMouseMotion and (Input.mouse_mode == Input.MOUSE_MODE_CAPTURED or e.button_mask & MOUSE_BUTTON_MASK_RIGHT):
		yaw -= e.relative.x * LOOK_SENS
		pitch = clampf(pitch - e.relative.y * LOOK_SENS, -1.45, 1.45)
		return
	if e.is_action_pressed("ui.cancel") and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
		Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
		get_viewport().set_input_as_handled()
		return
	if not WfInput.pressed(e):
		return
	match WfInput.key_of(e, ["excursion"]):
		KEY_E: use()
		KEY_O: ops()
		KEY_V: view_out = not view_out
		KEY_M:
			if ring_map != null:
				ring_map.visible = not ring_map.visible
		_: return
	get_viewport().set_input_as_handled()

func say(text: String) -> void:
	refusal = text
	refusal_t = 6.0
	_log("say", {"text": text})

## The reference frame of the view: up is the body's up (the field's, on a deck; the line's head direction, weightless); forward the ship axis
## projected on the plane across it, so the view never flips as the ring turns or the body pivots.
func ref_basis() -> Basis:
	var up: Vector3 = actor.up_now if move == "WALK" else (line.at(ls)[1] as Vector3)
	var fwd := Vector3.RIGHT - up * Vector3.RIGHT.dot(up)
	if fwd.length() < 0.2:
		fwd = Vector3.BACK - up * Vector3.BACK.dot(up)
	return Basis.looking_at(fwd.normalized(), up)

func look_basis() -> Basis:
	return ref_basis() * Basis.from_euler(Vector3(pitch, yaw, 0))

# ---- the step ---------------------------------------------------------------------------------------------------------------------------------

func _physics_process(dt: float) -> void:
	if actor == null:
		return
	_step_modes(dt)
	_step_drums(dt)
	_step_closures(dt)
	if move == "LINE":
		_step_line(dt)
	else:
		_step_walk(dt)
	_record()

func _step_modes(dt: float) -> void:
	# The operating change runs in the owner's step order; a ring ramp waits for the occupant to be secured (holding still on a rail in
	# the SHIP frame) and, spinning down, for the ring to reach the phase from which the ramp ends at its index (the lock).
	ctl.occupants_securable = move == "LINE" and line.zone == "SHIP" and not coasting and absf(lv) < 1e-6
	if ctl.hold_reason != "":
		ctl.resume()
	if ctl.busy():
		var step: String = ctl.queue[0] if not ctl.queue.is_empty() else ""
		if step == "RINGS_SPIN_DOWN" and ctl.ramp_t <= 0.0 and not _ring_phase_ready(dt):
			pass
		else:
			ctl.advance(dt * TIMELAPSE)
	# the station stands off while Wayfarer is undocked (the controller's UNDOCK / DOCK steps), a display move of STATION_MOVE_S
	var want := 0.0 if ctl.docked else 1.0
	if want != station_target:
		station_target = want
		_log("station", {"standoff": want})
	# the station's own hatch: open while Wayfarer is docked at rest, shut by the station before it separates (the station's procedure)
	var in_span: bool = move == "LINE" and line.id == "BOARD" and ls > float(hatch["STATION_HATCH"]["gate"][0]) and ls < float(hatch["STATION_HATCH"]["gate"][1])
	if not in_span:
		hatch["STATION_HATCH"]["target"] = 1.0 if ctl.docked and station_offset <= 0.0 and not ctl.busy() else 0.0
	if hatch["STATION_HATCH"]["value"] <= 0.0:
		station_offset = move_toward(station_offset, station_target, dt / STATION_MOVE_S)
	var u := WfLine.g(stages["boarding"]["axis"]["radial"]).normalized()
	station_root.position = u * float(stages["boarding"]["station"]["standoff_m"]) * smoothstep(0.0, 1.0, station_offset)
	for k in 2:
		var f: Dictionary = frames[ring_ids[k]]
		var w: float = f["rate"] * ctl.spin_frac
		f["angle"] = fposmod(f["angle"] + w * dt, TAU) if ctl.spin_frac > 0.0 else 0.0

func _ring_phase_ready(dt: float) -> bool:
	# both rings: the angle plus half the display ramp's turn crosses a whole turn now (boarding.gd crossed), so the ramp ends at the index
	var T := ctl.ramp_s() / TIMELAPSE
	var ok := true
	for k in 2:
		var f: Dictionary = frames[ring_ids[k]]
		var w: float = f["rate"]
		var a: float = f["angle"] + w * T / 2.0
		ok = ok and floor(a / TAU) != floor((a + w * dt) / TAU)
	return ok or _ring_wait_t(dt)

var _wait_t := 0.0
func _ring_wait_t(dt: float) -> bool:
	# the two rings turn opposite ways and meet their phase at different moments: after one ring has waited a full turn, take the other's
	_wait_t += dt
	if _wait_t > 60.0 / 4.0 + 1.0:
		_wait_t = 0.0
		return true
	return false

## Display drum cycles (the DYN-027 interlock gates every change, WfVestibule): close the open side, wait for the ring's phase so the
## constant-rate ramp meets the tube (spin-up) or ends at the index (spin-down), ramp in SYNC_S, open the matched side.
func _step_drums(dt: float) -> void:
	for k in 2:
		var d: Dictionary = drum[k]
		var v: WfVestibule = vest[k]
		var ring: Dictionary = frames[ring_ids[k]]
		var df: Dictionary = frames[drum_ids[k]]
		var w: float = ring["rate"] * ctl.spin_frac
		v.restrained = move == "LINE" and line.zone == "RING_" + "AB"[k] and absf(ls - float(line.marks["hold"])) < 1e-6 and absf(lv) < 1e-9
		v.step(dt)
		match str(d["mode"]):
			"CLOSING":
				var names := [_port_gate(k)] if d["to"] == "RING" else [_drum_door(k), _tube_hatch(k), _sector_leaf(k)]
				var shut := true
				for n in names:
					if closures.has(n):
						closures[n]["target"] = 0.0
						shut = shut and closures[n]["value"] <= 0.0
				if shut:
					v.close("STATIONARY" if d["to"] == "RING" else "RING")
					d["mode"] = "WAIT"
			"WAIT":
				var before: float = ring["angle"] + w * SYNC_S / 2.0
				if floor(before / TAU) != floor((before + w * dt) / TAU) or absf(w) < 1e-9:
					var e := v.start_sync(d["to"], w, SYNC_S)
					_log("vestibule", e)
					if e["ok"]:
						d["mode"] = "RAMP"
						d["t"] = 0.0
						d["from"] = ring["angle"]
					else:
						say("Transfer drum: " + str(e["reason"]))
						d["mode"] = "DESPUN" if d["to"] == "RING" else "SYNCED"
			"RAMP":
				d["t"] = minf(float(d["t"]) + dt, SYNC_S)
				var t: float = d["t"]
				var wf: float = ring["rate"]
				if d["to"] == "RING":
					df["angle"] = 0.5 * wf / SYNC_S * t * t
				else:
					df["angle"] = float(d["from"]) + wf * t - 0.5 * wf / SYNC_S * t * t
				if t >= SYNC_S and not v.ramping:
					var side: String = d["to"]
					var e := v.open(side, w)
					_log("vestibule", e)
					if e["ok"]:
						d["mode"] = "OPENING"
					else:
						say("Transfer drum: " + str(e["reason"]))
			"OPENING":
				var names := [_port_gate(k)] if d["to"] == "STATIONARY" else [_drum_door(k), _tube_hatch(k), _sector_leaf(k)]
				var open := true
				for n in names:
					if closures.has(n):
						closures[n]["target"] = 1.0
						open = open and closures[n]["value"] >= 1.0
				if open:
					d["mode"] = "SYNCED" if d["to"] == "RING" else "DESPUN"
					_log("drum", {"ring": k, "mode": d["mode"]})
		# the drum's display angle: at rest at the index while despun or leaving it, the ring's while synchronized or leaving the ring
		var m: String = d["mode"]
		if m == "DESPUN" or (m in ["CLOSING", "WAIT"] and d["to"] == "RING") or (m == "OPENING" and d["to"] == "STATIONARY"):
			df["angle"] = 0.0
		elif m == "SYNCED" or (m in ["CLOSING", "WAIT"] and d["to"] == "STATIONARY") or (m == "OPENING" and d["to"] == "RING"):
			df["angle"] = ring["angle"]

func _step_closures(dt: float) -> void:
	for name in closures:
		var c: Dictionary = closures[name]
		c["value"] = move_toward(c["value"], c["target"], dt / CLOSURE_S)
	for id in hatch:
		var h: Dictionary = hatch[id]
		h["value"] = move_toward(h["value"], h["target"], dt / CLOSURE_S)
	# the airlock's visible leaves follow the boarding hatches
	if closures.has("Dock_Primary_Outer_Hatch"):
		closures["Dock_Primary_Outer_Hatch"]["value"] = hatch["OUTER_HATCH"]["value"]
		closures["Dock_Primary_Outer_Hatch"]["target"] = hatch["OUTER_HATCH"]["target"]
	if closures.has("Dock_Primary_Inner_Hatch"):
		closures["Dock_Primary_Inner_Hatch"]["value"] = hatch["INNER_HATCH"]["value"]
		closures["Dock_Primary_Inner_Hatch"]["target"] = hatch["INNER_HATCH"]["target"]
	for id in circ_doors:
		var d: Dictionary = circ_doors[id]
		d["value"] = move_toward(d["value"], d["target"], dt / CLOSURE_S)
	if station_leaf != null:
		station_leaf.position = Vector3(0, 0, 0) + station_leaf.get_meta("slide") * hatch["STATION_HATCH"]["value"]
	_closure_colliders()
	_apply_mechanisms()

## The line command: W/S toward the view along the line (the hands pull the body the way it looks), or the check's command.
func _line_cmd() -> float:
	if branch_to >= 0.0:
		return signf(branch_to - ls)
	if cmd_override != INF:
		return cmd_override
	var fwd := WfInput.strength("player.move_forward") - WfInput.strength("player.move_back")
	if absf(fwd) < 1e-6:
		return 0.0
	var t := line.tangent(ls)
	var lk := -look_basis().z
	var sgn := signf(t.dot(lk))
	if sgn == 0.0:
		sgn = 1.0
	return fwd * sgn

## The furthest s the closures allow from here (a shut gate stops the body before it; an access line's hold pose is a stop both ways).
func _limits() -> Array:
	var lo := 0.0
	var hi := line.length()
	for gate in line.gates:
		var h: Dictionary = hatch[gate["id"]]
		if h["value"] < 0.999:
			var s0: float = gate["s"][0]
			var s1: float = gate["s"][1]
			if ls <= s0 + 1e-9:
				hi = minf(hi, s0)
			elif ls >= s1 - 1e-9:
				lo = maxf(lo, s1)
	if line.zone != "SHIP":
		var k := WfFrames.ring_index(line.zone)
		var hold: float = line.marks["hold"]
		var port: float = line.marks["port"]
		var port_open: bool = closures[_port_gate(k)]["value"] >= 0.999
		var door_open: bool = closures[_drum_door(k)]["value"] >= 0.999 and closures[_tube_hatch(k)]["value"] >= 0.999
		if ls <= port + 1e-9 and not port_open:
			hi = minf(hi, port)
		if ls <= hold + 1e-9 and not door_open:
			hi = minf(hi, hold)
		if ls >= hold - 1e-9 and not port_open:
			lo = maxf(lo, hold)
		if ls < hold - 1e-9:
			hi = minf(hi, hold)             # the restraint pose is a stop on the way in: the hands hold there for the drum's cycle
		elif ls > hold + 1e-9:
			lo = maxf(lo, hold)             # and on the way out
	if branch_to >= 0.0:
		if ls <= branch_to + 1e-9:
			hi = minf(hi, branch_to)
		else:
			lo = maxf(lo, branch_to)
	# a stop is only possible where a grip is in reach: before a coast, not in it
	for c in line.coasts:
		if ls <= float(c[0]) + 1e-9 and hi > float(c[0]) and hi < float(c[1]):
			hi = float(c[0])
		if ls >= float(c[1]) - 1e-9 and lo < float(c[1]) and lo > float(c[0]):
			lo = float(c[1])
	return [lo, hi]

func _brake(v_end: float, gap: float, dt: float) -> float:
	var ad := line.accel * dt
	return maxf(0.0, -ad + sqrt(ad * ad + v_end * v_end + 2.0 * line.accel * maxf(gap, 0.0)))

func _step_line(dt: float) -> void:
	# body_tour._step_ladder, both ways: the hands carry the body at the review pace toward the command, braked to rest at the closures'
	# limits and slowed before each turn so the velocity never changes faster than the line's accel; across a coast the speed holds.
	_field_for_line()
	var pace: float = stages["tube"]["review_speed_m_s"]
	var cmd := _line_cmd()
	var lim := _limits()
	var lo: float = lim[0]
	var hi: float = lim[1]
	var dir := signf(lv) if absf(lv) > 1e-9 else signf(cmd)
	coasting = absf(lv) > 1e-9 and not line.coast_at(ls, signf(lv)).is_empty()
	if not coasting:
		var room := hi - ls if cmd > 0.0 else ls - lo
		var speed := minf(absf(cmd) * pace, _brake(0.0, room, dt))
		var ahead := pace * pace / (2.0 * line.accel) + pace * dt
		for c in line.coasts:
			ahead += float(c[1]) - float(c[0])
		for k in range(line.s.size()):
			var gap: float = (float(line.s[k]) - ls) * signf(cmd)
			if gap > 1e-9 and gap <= ahead:
				speed = minf(speed, _brake(float(line.vmax[k]), line.held_length(ls, float(line.s[k])), dt))
		var target := signf(cmd) * speed
		# pushing off into a coast: refused while a shut closure lies inside the coast ahead (the body could not stop before it)
		var next_coast := line.coast_at(ls + signf(target) * 1e-4, signf(target)) if absf(target) > 1e-9 else []
		if not next_coast.is_empty():
			var far: float = next_coast[1] if target > 0.0 else next_coast[0]
			if (target > 0.0 and far > hi + 1e-6) or (target < 0.0 and far < lo - 1e-6):
				target = 0.0
				if absf(cmd) > 0.0:
					prompt = "No rail in reach ahead and a closure is shut on the way: open it first, then push off."
		# a push-off at the coast's edge: the arms bring the body to the speed before letting go (the last grip is behind the hands)
		lv = target if not next_coast.is_empty() and absf(target) > absf(lv) else move_toward(lv, target, line.accel * dt)
	var next := clampf(ls + lv * dt, minf(lo, ls), maxf(hi, ls))
	if not coasting and absf(next - (hi if lv > 0.0 else lo)) < 2e-3 and absf(lv) < line.accel * dt * 1.01:
		next = hi if lv > 0.0 else lo
		lv = 0.0
	if coasting and (next >= hi - 1e-9 or next <= lo + 1e-9):
		lv = 0.0                             # a coast never ends at a shut closure (refused above); this guards the line's ends
	var here := line.at(ls)
	var there := line.at(next)
	var v: Vector3 = ((there[0] as Vector3) - (here[0] as Vector3)) / dt
	if coasting:
		actor.ladder_v = v
	else:
		actor.ladder_v = v + (((there[0] as Vector3) - (actor.global_position + v * dt)) / dt * 0.1).limit_length(pace)
	actor.ladder_up = there[1]
	ls = next
	_set_body_height(line.id)
	_line_transitions(cmd)

## The line graph: the boarding line runs on into ring A's access at its aft end; an access line runs back into the boarding line at its start
## (its junction) and onto the deck at its end.
func _line_transitions(cmd: float) -> void:
	if line.id == "BOARD" and branch_to >= 0.0:
		if absf(ls - branch_to) < 1e-6 and absf(lv) < 1e-9:
			branch_to = -1.0
			enter_line("ACCESS_B", 0.0)
		return
	if line.id == "BOARD":
		if ls >= line.length() - 1e-6 and cmd > 0.0:
			enter_line("ACCESS_A", 0.0)
			return
		if ls < float(line.gates[0]["s"][0]) and ctl.mode == "DOCKED" and not ctl.busy():
			for r in progress:
				if progress[r]["back"] and not progress[r]["returned"]:
					progress[r]["returned"] = true
					_log("returned", {"ring": r})
					say("Back aboard the station: the %s excursion is complete." % ("Ring A" if r == "RING_A" else "Ring B"))
	else:
		var k := WfFrames.ring_index(line.zone)
		if ls > float(line.marks["hold"]):
			progress[line.zone]["boarded"] = true
		if ls <= 1e-6 and cmd < 0.0:
			if progress[line.zone]["circuit"]:
				progress[line.zone]["back"] = true
			enter_line("BOARD", float(lines["BOARD"].marks["RING_" + "AB"[k]]))
			lv = 0.0
			return
		if ls >= line.length() - 1e-6:
			enter_walk(line.zone)

func _step_walk(dt: float) -> void:
	var b := ref_basis() * Basis.from_euler(Vector3(0, yaw, 0))
	var d := Vector3.ZERO
	if walk_override != Vector3.INF:
		d = walk_override
	else:
		d -= b.z * (WfInput.strength("player.move_forward") - WfInput.strength("player.move_back"))
		d += b.x * (WfInput.strength("player.move_right") - WfInput.strength("player.move_left"))
	actor.walk_dir = d
	# the circuit record: the ring angle the body has covered
	var k := WfFrames.ring_index(walk_zone)
	var cx: float = dyn["rings"][k]["centre_x_m"]
	var p := actor.global_position - Vector3(cx, 0, 0)
	var ang := fposmod(atan2(p.y, -p.z), TAU)        # Godot (y, z) = (z, -y): the vehicle angle from +Y about +X
	var rec: Dictionary = progress[walk_zone]
	rec["entered"] = true
	var bin := int(ang / TAU * BINS) % BINS
	rec["bins"][bin] = 1
	if not rec["circuit"] and rec["bins"].count(1) == BINS:
		rec["circuit"] = true
		_log("circuit", {"ring": walk_zone})
		say("Full circuit of %s walked. Return to the landing well and climb back to the trunk." % ("Ring A" if k == 0 else "Ring B"))

# ---- actions --------------------------------------------------------------------------------------------------------------------------------

## E: the nearest thing in reach, in this order: the drum's transfer cycle at the restraint pose; a line closure ahead (or the airlock's other
## hatch, when the rule needs it shut first); the trunk's ring B branch; a corridor or sector door; the ladder foot in a landing well.
func use() -> String:
	if move == "LINE":
		if line.zone != "SHIP" and absf(ls - float(line.marks["hold"])) < 1e-6 and absf(lv) < 1e-9:
			return _cycle_drum(WfFrames.ring_index(line.zone))
		var h := _hatch_in_reach()
		if h != "":
			return _toggle_hatch(h)
		if line.id == "BOARD" and absf(ls - float(line.marks["RING_B"])) < BRANCH_REACH_S and absf(lv) < 1e-9:
			branch_to = float(line.marks["RING_B"])     # the hands carry the body to the opening (_step_line), then it turns in
			return "branch RING_B"
		if line.zone != "SHIP" and ls < float(line.marks["port"]) + 1e-6:
			var k := WfFrames.ring_index(line.zone)
			if float(line.marks["port"]) - ls < USE_REACH_S:
				return _open_port_gate(k)
		say("Nothing in reach to operate here.")
		return ""
	var w := _walk_target()
	if w == "ladder":
		var L: WfLine = lines["ACCESS_" + "AB"[WfFrames.ring_index(walk_zone)]]
		enter_line(L.id, L.length(), false)
		return "ladder"
	if w != "":
		return _toggle_door(w)
	say("Nothing in reach to operate here.")
	return ""

func _hatch_in_reach() -> String:
	var best := ""
	var bd := INF
	var look_t := signf(line.tangent(ls).dot(-look_basis().z))
	for gate in line.gates:
		if gate["id"] == "STATION_HATCH":
			continue                         # the station works its own hatch
		var s0: float = gate["s"][0]
		var s1: float = gate["s"][1]
		var d := s0 - ls if ls <= s0 else (ls - s1 if ls >= s1 else 0.0)
		if d > USE_REACH_S:
			continue
		var ahead := 1.0 if ls <= s0 else -1.0
		var score := d + (0.0 if ahead == look_t else 0.8)
		if score < bd:
			bd = score
			best = gate["id"]
	# the airlock rule: to open a hatch whose partner is open, shut the partner first (if it is in reach too)
	if best in ["OUTER_HATCH", "INNER_HATCH"] and hatch[best]["target"] < 1.0:
		var other := "INNER_HATCH" if best == "OUTER_HATCH" else "OUTER_HATCH"
		if hatch[other]["target"] > 0.0:
			for gate in line.gates:
				if gate["id"] == other:
					var d2 := float(gate["s"][0]) - ls if ls <= float(gate["s"][0]) else ls - float(gate["s"][1])
					if d2 <= USE_REACH_S:
						return other
	return best

func _toggle_hatch(id: String) -> String:
	var h: Dictionary = hatch[id]
	var opening: bool = h["target"] < 1.0
	if opening:
		if id == "OUTER_HATCH" and (ctl.mode != "DOCKED" or ctl.busy()):
			say("Outer hatch: Wayfarer is not docked; it stays shut until the dock is complete.")
			return ""
		var other: String = {"OUTER_HATCH": "INNER_HATCH", "INNER_HATCH": "OUTER_HATCH"}.get(id, "")
		if other != "" and hatch[other]["value"] > 0.0:
			say("Airlock: the %s hatch is open. The two hatches are never open together: shut it first." % ("inner" if other == "INNER_HATCH" else "outer"))
			return ""
		h["target"] = 1.0
		_log("hatch", {"id": id, "open": true})
		return "open " + id
	var gs: Array = []
	for gate in line.gates:
		if gate["id"] == id:
			gs = gate["s"]
	if ls > float(gs[0]) and ls < float(gs[1]):
		say("You are in the hatchway: move clear before it closes.")
		return ""
	h["target"] = 0.0
	_log("hatch", {"id": id, "open": false})
	return "close " + id

func _open_port_gate(k: int) -> String:
	var d: Dictionary = drum[k]
	if d["mode"] != "DESPUN" or absf(wrapf(frames[drum_ids[k]]["angle"], -PI, PI)) > 1e-6:
		say("Spine-port gate: the drum is not despun at the index.")
		return ""
	var v: WfVestibule = vest[k]
	if not v.closures["STATIONARY"]:
		return ""
	var e := v.open("STATIONARY", frames[ring_ids[k]]["rate"] * ctl.spin_frac)
	_log("vestibule", e)
	if not e["ok"]:
		say("Spine-port gate: " + str(e["reason"]))
		return ""
	closures[_port_gate(k)]["target"] = 1.0
	return "open port gate"

func _cycle_drum(k: int) -> String:
	var d: Dictionary = drum[k]
	if d["mode"] == "DESPUN":
		if ctl.mode != "COAST" or ctl.busy():
			say("The rings are stopped and locked: request ring spin-up at a trunk panel first (O).")
			return ""
		d["to"] = "RING"
	elif d["mode"] == "SYNCED":
		d["to"] = "STATIONARY"
	else:
		say("The transfer drum is already cycling.")
		return ""
	d["mode"] = "CLOSING"
	_log("drum", {"ring": k, "cycle": d["to"]})
	return "cycle drum to " + str(d["to"])

## Walking: what E works, a circulation door id or "ladder" (the ladder foot): the nearest in reach, one the trainee faces before one behind.
func _walk_target() -> String:
	var best := ""
	var bd := INF
	var fwd := -look_basis().z
	var cand := {}
	var dd := _door_in_reach()
	if dd != "":
		cand[dd] = (circ_doors[dd]["collider"] as Node3D).global_position
	var L: WfLine = lines["ACCESS_" + "AB"[WfFrames.ring_index(walk_zone)]]
	if actor.global_position.distance_to(L.p[-1]) < USE_REACH_M:
		cand["ladder"] = L.p[-1]
	for id in cand:
		var to: Vector3 = (cand[id] as Vector3) - actor.global_position
		var score := to.length() + (0.0 if to.dot(fwd) > 0.0 or to.length() < 0.6 else 0.8)     # within 0.6 m: at hand whichever way
		if score < bd:
			bd = score
			best = id
	return best

func _door_in_reach() -> String:
	var best := ""
	var bd := USE_REACH_M
	var k := WfFrames.ring_index(walk_zone)
	for id in circ_doors:
		var d: Dictionary = circ_doors[id]
		if d["ring"] != k or d["collider"] == null:
			continue
		var c: Vector3 = (d["collider"] as Node3D).global_position
		var dist := actor.global_position.distance_to(c)
		if dist < bd:
			bd = dist
			best = id
	return best

func _toggle_door(id: String) -> String:
	var d: Dictionary = circ_doors[id]
	if d["target"] < 1.0:
		d["target"] = 1.0
		_log("door", {"id": id, "open": true})
		return "open " + id
	# never close on the body: the doorway (the leaf's slab and a body radius round it) must be clear
	var col: Node3D = d["collider"]
	var loc := col.global_transform.affine_inverse() * actor.global_position
	var half: Vector3 = ((col.get_child(0) as CollisionShape3D).shape as BoxShape3D).size * 0.5
	if absf(loc.z) < half.z + float(actor.profile["radius_m"]) + 0.05 and absf(loc.x) < half.x + 0.3:
		say("The doorway is occupied: step through before closing the door.")
		return ""
	d["target"] = 0.0
	_log("door", {"id": id, "open": false})
	return "close " + id

## O: the ship's operating change, asked at a trunk panel (the trainee holding still on a rail inside Wayfarer, in the SHIP frame).
func ops() -> String:
	if not (move == "LINE" and line.id == "BOARD" and ls > float(hatch["OUTER_HATCH"]["gate"][1])):
		say("Operations: ask from a panel inside Wayfarer's trunk (past the airlock).")
		return ""
	if ctl.busy():
		say("Operations: %s in progress." % ctl.target)
		return ""
	if ctl.mode == "DOCKED":
		if hatch["OUTER_HATCH"]["value"] > 0.0:
			say("Undock refused: Wayfarer's outer hatch is open.")
			return ""
		var e := ctl.request("COAST")
		_log("mode", e)
		if e.get("refused", false):
			say("Operations: " + str(e["reason"]))
			return ""
		say("Undocking, then the rings unlock and spin up (1800 s study ramp, x90). Hold still on the rail.")
		return "COAST"
	if ctl.mode == "COAST":
		for k in 2:
			if drum[k]["mode"] != "DESPUN":
				say("Spin-down refused: ring %s's transfer drum is not despun." % "AB"[k])
				return ""
		var e := ctl.request("DOCKED")
		_log("mode", e)
		if e.get("refused", false):
			say("Operations: " + str(e["reason"]))
			return ""
		say("The rings spin down and lock, then Wayfarer docks. Hold still on the rail.")
		return "DOCKED"
	return ""

# ---- display ---------------------------------------------------------------------------------------------------------------------------------

func _frame_pivot() -> Dictionary:
	if move == "WALK":
		return frames[ring_ids[WfFrames.ring_index(walk_zone)]]
	if line.zone == "SHIP":
		return frames["STATIONARY"]
	var k := WfFrames.ring_index(line.zone)
	if ls > float(line.marks["hold"]) + 1e-6 and drum[k]["mode"] == "SYNCED":
		# past the open door: drum and ring at the same angle, so the ring's frame carries the body (no jump)
		return frames[ring_ids[k]]
	if ls >= float(line.marks["port"]) - 1e-6 or drum[k]["mode"] != "DESPUN":
		return frames[drum_ids[k]]
	return frames["STATIONARY"]

func _process(dt: float) -> void:
	if actor == null:
		return
	var f := _frame_pivot()
	if view_root.get_parent() != f["node"]:
		view_root.reparent(f["node"], false)
	view_root.transform = Transform3D(Basis.IDENTITY, -f["rest"])
	var lk := WfInput.take_look()
	yaw -= lk.x
	pitch = clampf(pitch - lk.y, -1.45, 1.45)
	body_vis.transform = actor.global_transform
	var look := look_basis()
	var up: Vector3 = actor.up_now if move == "WALK" else (line.at(ls)[1] as Vector3)
	var eye := actor.global_position + up * (EYE_UP if not tucked() else 0.2)
	var local := Transform3D(look, eye)
	if view_out:
		local = Transform3D(look, eye - look.z * 2.2 + up * 0.25)
	body_vis.visible = view_out
	camera.transform = local
	refusal_t = maxf(refusal_t - dt, 0.0)
	_update_lamps()
	_update_hud()

# ---- record ----------------------------------------------------------------------------------------------------------------------------------

var _last_pos := Vector3.ZERO
var max_jump := 0.0
var branch_to := -1.0             # s of the ring B junction while the hands carry the body to it
var max_jump_at := ""
func _record() -> void:
	# a frame change never moves the body: the step from the last physics position (the check reads max_jump)
	var p := actor.global_position
	if _last_pos != Vector3.ZERO:
		var j := (p - _last_pos).length() - actor.linear_velocity.length() / Engine.physics_ticks_per_second
		if j > max_jump:
			max_jump = j
			max_jump_at = "%s %s s=%.3f frame %d" % [move, line.id if move == "LINE" else walk_zone, ls, Engine.get_physics_frames()]
	_last_pos = p

func _log(kind: String, data: Dictionary) -> void:
	var e := {"t": snappedf(Time.get_ticks_msec() / 1000.0, 0.01), "kind": kind}
	e.merge(data)
	log.append(e)

static func _vec(v: Vector3) -> Array:
	return [snappedf(v.x, 0.001), snappedf(v.y, 0.001), snappedf(v.z, 0.001)]

# ---- the station whitebox (display: from the rig's boarding stage) ------------------------------------------------------------------------

func _mat(c: Color, emit := 0.0, double := true) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = c
	m.roughness = 0.7
	if emit > 0.0:
		m.emission_enabled = true
		m.emission = c
		m.emission_energy_multiplier = emit
	if double:
		m.cull_mode = BaseMaterial3D.CULL_DISABLED
	return m

## A tube surface of radius r about c + n a from a0 to a1 (seen from both sides).
func _tube(c: Vector3, n: Vector3, r: float, a0: float, a1: float, mat: Material, sides := 48) -> MeshInstance3D:
	var u := n.cross(Vector3.RIGHT).normalized()
	var v := n.cross(u)
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for i in sides:
		var p0 := TAU * i / sides
		var p1 := TAU * (i + 1) / sides
		var e0 := u * cos(p0) + v * sin(p0)
		var e1 := u * cos(p1) + v * sin(p1)
		var q := [c + n * a0 + e0 * r, c + n * a1 + e0 * r, c + n * a1 + e1 * r, c + n * a0 + e1 * r]
		for idx in [0, 1, 2, 0, 2, 3]:
			var e := e0 if idx in [0, 1] else e1
			st.set_normal(-e)
			st.add_vertex(q[idx])
	var mi := MeshInstance3D.new()
	mi.mesh = st.commit()
	mi.material_override = mat
	station_root.add_child(mi)
	return mi

func _ring_disc(c: Vector3, n: Vector3, a: float, r0: float, r1: float, mat: Material, sides := 48) -> MeshInstance3D:
	var u := n.cross(Vector3.RIGHT).normalized()
	var v := n.cross(u)
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for i in sides:
		var p0 := TAU * i / sides
		var p1 := TAU * (i + 1) / sides
		var e0 := u * cos(p0) + v * sin(p0)
		var e1 := u * cos(p1) + v * sin(p1)
		var q := [c + n * a + e0 * r0, c + n * a + e0 * r1, c + n * a + e1 * r1, c + n * a + e1 * r0]
		for idx in [0, 1, 2, 0, 2, 3]:
			st.set_normal(n)
			st.add_vertex(q[idx])
	var mi := MeshInstance3D.new()
	mi.mesh = st.commit()
	mi.material_override = mat
	station_root.add_child(mi)
	return mi

func _rod(a: Vector3, b: Vector3, r: float, mat: Material, parent: Node3D = null) -> MeshInstance3D:
	var cm := CylinderMesh.new()
	cm.top_radius = r
	cm.bottom_radius = r
	cm.height = a.distance_to(b)
	cm.radial_segments = 10
	var mi := MeshInstance3D.new()
	mi.mesh = cm
	mi.material_override = mat
	var d := (b - a).normalized()
	var side := d.cross(Vector3.RIGHT if absf(d.x) < 0.9 else Vector3.UP).normalized()
	mi.transform = Transform3D(Basis(side, d, side.cross(d)), (a + b) * 0.5)
	(parent if parent != null else station_root).add_child(mi)
	return mi

func _build_station() -> void:
	ship.add_child(station_root)
	station_root.name = "STATION_BOARDING_AREA"
	var b: Dictionary = stages["boarding"]
	var st: Dictionary = b["station"]
	var c := WfLine.g(b["axis"]["origin_m"])
	var n := WfLine.g(b["axis"]["radial"]).normalized()
	var t := WfLine.g(b["axis"]["tangent"]).normalized()
	var wall := _mat(Color(0.80, 0.81, 0.79))
	var tunnel := _mat(Color(0.70, 0.72, 0.74))
	var deck := _mat(Color(0.30, 0.34, 0.42))
	var rail := _mat(Color(0.92, 0.78, 0.22))
	var trim := _mat(Color(0.38, 0.40, 0.43))
	var nr: float = st["node_clear_radius_m"]
	var node: Array = st["node_a_m"]
	var tun: Array = st["tunnel_a_m"]
	_tube(c, n, nr, float(node[0]), float(node[1]), wall)
	_tube(c, n, nr + float(st["wall_m"]), float(node[0]), float(node[1]), _mat(Color(0.55, 0.57, 0.58)))
	_tube(c, n, 0.8, float(tun[0]), float(tun[1]), tunnel)
	_tube(c, n, 0.86, float(tun[0]), float(tun[1]), _mat(Color(0.55, 0.57, 0.58)))
	var face: float = float(b["bores"][3]["a_m"][1])       # the docking face (station_adapter starts there)
	for q in b["bores"]:
		if q["name"] == "station_adapter":
			face = float(q["a_m"][0])
			_tube(c, n, 0.8, float(q["a_m"][0]), float(q["a_m"][1]), trim)
	_ring_disc(c, n, face + 0.02, 0.8, 1.4, trim)                     # the station half of the soft-capture ring, mated
	_ring_disc(c, n, float(node[1]), 0.0, nr, wall)
	_ring_disc(c, n, float(node[0]), 0.8, nr, wall)
	# the painted deck band: an orientation convention on the node's wall (no gravity: nothing stands on it)
	# dock-local angles (human_entry.world): phi from the ship's +X toward the port's tangent
	var u := Vector3.RIGHT
	var v := t
	for q in b["fixtures"]:
		match str(q["shape"]):
			"rod":
				_rod(WfLine.g(q["points"][0]), WfLine.g(q["points"][1]), float(q["radius"]), rail)
			"box":
				var e := u * cos(float(q["phi"])) + v * sin(float(q["phi"]))
				var bm := BoxMesh.new()
				bm.size = Vector3(q["size"][0], q["size"][1], q["size"][2])
				var mi := MeshInstance3D.new()
				mi.mesh = bm
				var emit := 6.0 if str(q["role"]) == "light strip" else 0.0
				mi.material_override = _mat(Color(1.0, 0.95, 0.85) if emit > 0.0 else Color(0.18, 0.22, 0.30), emit)
				mi.transform = Transform3D(Basis(n, e.cross(n), e), c + n * float(q["a"]) + e * float(q["rho"]))
				station_root.add_child(mi)
				if emit > 0.0:
					var l := OmniLight3D.new()
					l.light_color = Color(1.0, 0.95, 0.88)
					l.light_energy = 1.0
					l.omni_range = 4.5
					l.position = c + n * float(q["a"]) + e * (float(q["rho"]) - 0.3)
					station_root.add_child(l)
			"window":
				var e := u * cos(float(q["phi"])) + v * sin(float(q["phi"]))
				var cyl := CylinderMesh.new()
				cyl.top_radius = q["radius"]
				cyl.bottom_radius = q["radius"]
				cyl.height = 0.03
				var mi := MeshInstance3D.new()
				mi.mesh = cyl
				var glass := _mat(Color(0.05, 0.12, 0.22))
				glass.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
				glass.albedo_color.a = 0.35
				mi.material_override = glass
				mi.transform = Transform3D(Basis(e, n, e.cross(n)), c + n * (float(q["a"]) + 0.01) + e * float(q["rho"]))
				station_root.add_child(mi)
			"disc":
				var cyl := CylinderMesh.new()
				cyl.top_radius = q["radius"]
				cyl.bottom_radius = q["radius"]
				cyl.height = 0.06
				var mi := MeshInstance3D.new()
				mi.mesh = cyl
				mi.material_override = _mat(Color(0.45, 0.50, 0.56))
				mi.transform = Transform3D(Basis(u, n, u.cross(n)), c + n * float(q["a"]))
				station_root.add_child(mi)
	# a deck band down the node opposite the panel (an orientation convention only)
	var pa := deg_to_rad(195.0 + 180.0)
	var e2 := u * cos(pa) + v * sin(pa)
	var band := BoxMesh.new()
	band.size = Vector3(float(node[1]) - float(node[0]) - 0.2, 0.01, 0.9)
	var bmi := MeshInstance3D.new()
	bmi.mesh = band
	bmi.material_override = deck
	bmi.transform = Transform3D(Basis(n, e2, n.cross(e2)), c + n * (float(node[0]) + float(node[1])) * 0.5 + e2 * (nr - 0.01))
	station_root.add_child(bmi)
	# the station's own hatch: a disc leaf in the adapter that slides sideways (along the port's tangent) into the collar
	for h in b["hatches"]:
		if h["id"] == "STATION_HATCH":
			var leaf := MeshInstance3D.new()
			var cyl := CylinderMesh.new()
			cyl.top_radius = 0.85
			cyl.bottom_radius = 0.85
			cyl.height = 0.05
			leaf.mesh = cyl
			leaf.material_override = _mat(Color(0.25, 0.42, 0.62))
			var holder := Node3D.new()
			holder.position = c + n * float(h["a"])
			station_root.add_child(holder)
			leaf.transform = Transform3D(Basis(u, n, u.cross(n)), Vector3.ZERO)
			holder.add_child(leaf)
			station_leaf = holder
			holder.set_meta("rest", holder.position)
			holder.set_meta("slide", t * 1.75)
	# signage: what this place is and where the ship is
	var sign := Label3D.new()
	sign.text = "DEVELOPMENT STATION · BOARDING NODE\nTO WAYFARER 001: tunnel, hatch, airlock"
	sign.font_size = 48
	sign.pixel_size = 0.004
	sign.modulate = Color(0.85, 0.9, 1.0)
	var pe := u * cos(deg_to_rad(195.0)) + v * sin(deg_to_rad(195.0))
	# facing into the node (-pe), right-handed so the text does not read mirrored
	sign.transform = Transform3D(Basis(pe.cross(n), n, -pe).orthonormalized(), c + n * (float(node[1]) - 0.4) + pe * (nr - 0.05))
	sign.billboard = BaseMaterial3D.BILLBOARD_DISABLED
	station_root.add_child(sign)

# ---- lights ------------------------------------------------------------------------------------------------------------------------------------

func _environment(by_name: Dictionary) -> void:
	world_env.environment = Environment.new()
	var env := world_env.environment
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color("05080d")
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color("b6c8dc")
	env.ambient_light_energy = 0.18
	env.tonemap_mode = Environment.TONE_MAPPER_AGX
	add_child(world_env)
	# FUT-003 (boarding.gd): each emitting surface of a light class carries a point light; only the nearest are on
	for record in manifest["nodes"]:
		if not record.has("light") or not by_name.has(record["node"]):
			continue
		var q: Dictionary = record["light"]
		var l := OmniLight3D.new()
		l.light_color = Color(q["color"][0], q["color"][1], q["color"][2]).linear_to_srgb()
		l.light_energy = float(q["energy"]) * 0.65
		l.omni_range = float(q["range_m"])
		l.visible = false
		var nd: Node3D = by_name[record["node"]]
		nd.add_child(l)
		var cc: Array = q["centre_local_runtime_m"]
		l.position = Vector3(cc[0], cc[1], cc[2])
		lamps.append(l)
	var sun := DirectionalLight3D.new()                # a dim inspection key light on the exterior (display only, no sourced sun)
	sun.rotation = Vector3(-0.6, 0.8, 0.0)
	sun.light_energy = 0.35
	add_child(sun)

var _lamp_t := 0.0
func _update_lamps() -> void:
	_lamp_t += get_process_delta_time()
	if _lamp_t < 0.25:
		return
	_lamp_t = 0.0
	var eye := camera.global_position
	var near: Array = []
	for l in lamps:
		l.visible = false
		var d: float = l.global_position.distance_to(eye)
		if d < 14.0:
			near.append([d, l])
	near.sort_custom(func(a, b): return a[0] < b[0])
	for i in range(mini(near.size(), 16)):
		near[i][1].visible = true

# ---- HUD ---------------------------------------------------------------------------------------------------------------------------------------

func _label(l: Label, size: int, pos: Vector2) -> void:
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_outline_color", Color.BLACK)
	l.add_theme_constant_override("outline_size", 4)
	l.position = pos
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	var back := StyleBoxFlat.new()
	back.bg_color = Color(0, 0, 0, 0.42)
	back.set_content_margin_all(6.0)
	l.add_theme_stylebox_override("normal", back)
	layer.add_child(l)

func _hud() -> void:
	add_child(layer)
	_label(hud_goal, 16, Vector2(18, 14))
	hud_goal.custom_minimum_size = Vector2(560, 0)
	_label(hud_check, 13, Vector2(18, 150))
	hud_check.custom_minimum_size = Vector2(300, 0)
	_label(hud_prompt, 17, Vector2(18, 640))
	hud_prompt.custom_minimum_size = Vector2(900, 0)
	_label(hud_status, 12, Vector2(18, 720))
	hud_status.custom_minimum_size = Vector2(1100, 0)
	ring_map = WfExcursionMap.new()
	ring_map.host = self
	ring_map.position = Vector2(1280 - 250, 12)
	ring_map.size = Vector2(238, 238)
	layer.add_child(ring_map)
	get_viewport().size_changed.connect(_layout)
	_layout()

func _layout() -> void:
	var sz := get_viewport().get_visible_rect().size
	if WfInput.compact():
		# phone or tablet (MOB-001): the goal and prompt under the page's Exit row on the left, the map under the touch utility row on
		# the right; the stick and the action buttons keep the lower corners; the checklist and status line give way (the map shows %)
		var w := minf(sz.x * 0.5, 420.0)
		hud_goal.add_theme_font_size_override("font_size", 13)
		hud_goal.position = Vector2(12, 66)
		hud_goal.custom_minimum_size.x = w
		hud_goal.size.x = w
		hud_prompt.add_theme_font_size_override("font_size", 13)
		hud_prompt.position = Vector2(12, 66 + hud_goal.get_combined_minimum_size().y + 6)
		hud_prompt.custom_minimum_size.x = w
		hud_prompt.size.x = w
		hud_check.visible = false
		hud_status.visible = false
		ring_map.size = Vector2(150, 150)
		ring_map.position = Vector2(sz.x - 162, 74)
		return
	hud_prompt.position = Vector2(18, sz.y - 150)
	hud_prompt.custom_minimum_size.x = minf(900.0, sz.x - 36.0)
	hud_status.position = Vector2(18, sz.y - 66)
	hud_status.custom_minimum_size.x = sz.x - 36.0
	ring_map.position = Vector2(sz.x - 250, 12)

func key(id: String) -> String:
	return "[" + WfInput.label(id) + "]"

func where() -> String:
	if move == "WALK":
		return "ring " + walk_zone.right(1)
	if line.id == "BOARD":
		var s1: float = hatch["STATION_HATCH"]["gate"][0]
		if ls < s1:
			return "station"
		if ls < float(hatch["INNER_HATCH"]["gate"][1]):
			return "airlock"
		return "trunk"
	var k := WfFrames.ring_index(line.zone)
	if ls < float(line.marks["port"]):
		return "trunk"
	if ls <= float(line.marks["hold"]) + 1e-6:
		return "drum " + "AB"[k]
	if ls < float(line.marks["run"]):
		return "drum door / tube elbows " + "AB"[k]
	return "crew tube " + "AB"[k]

func _goal_text() -> String:
	var w := where()
	var mv := "%s/%s" % [key("player.move_forward"), key("player.move_back")]
	if w == "station":
		if ctl.mode == "DOCKED" and not ctl.busy():
			return "STATION (microgravity, no floor: hold the rails). Float down the boarding tunnel: hold %s toward it (the view chooses the way). Open Wayfarer's outer hatch with %s." % [mv, key("exc.use")]
		return "STATION. Wayfarer is undocked; the station hatch stays shut until it docks again."
	if w == "airlock":
		return "AIRLOCK. The two hatches are never open together: close the outer hatch behind you, open the inner hatch (%s), then float on into the trunk." % key("exc.use")
	if ctl.busy():
		return "OPERATIONS %s -> %s: %s. Hold still on the rail (you are an occupant to be secured)." % [ctl.mode, ctl.target, ", ".join(ctl.queue)]
	if move == "WALK":
		var rec: Dictionary = progress[walk_zone]
		if rec["circuit"]:
			return "CIRCUIT COMPLETE. Walk back to the landing well, face the ladder and press %s, then climb (%s, look up)." % [key("exc.use"), mv]
		return "RING %s (spin gravity %.2f g). Walk the whole circumference through every sector and corridor: %d %% covered. Doors: %s." % [walk_zone.right(1),
			actor.field_now.length() / 9.80665, int(100.0 * rec["bins"].count(1) / BINS), key("exc.use")]
	if w == "trunk" and line.id == "BOARD":
		if ctl.mode == "DOCKED":
			for r in progress:
				if progress[r]["back"] and not progress[r]["returned"]:
					return "TRUNK. Docked again: float back through the airlock (inner, then outer hatch) and the station hatch to the boarding node."
			return "TRUNK (Wayfarer docked, rings stopped and locked). Press %s: Wayfarer undocks and spins its rings up. Hold still on the rail." % key("exc.ops")
		for r in progress:
			if progress[r]["back"] and not progress[r]["returned"]:
				return "TRUNK. To return to the station press %s: the rings spin down and lock, and Wayfarer docks." % key("exc.ops")
		if absf(ls - float(line.marks["RING_B"])) < 0.05:
			return "TRUNK at ring B's spine port. %s: take the ring B branch. %s on: continue aft to ring A's port." % [key("exc.use"), key("player.move_forward")]
		return "TRUNK (rings at 4 rpm). Float aft (%s): ring B's spine port comes first (stop there and press %s), ring A's is at the aft end." % [mv, key("exc.use")]
	var k := WfFrames.ring_index(line.zone)
	if w == "trunk":
		return "SPINE PORT %s. Open the gate (%s) and float into the drum: the drum is despun, the ring turns beyond it." % ["AB"[k], key("exc.use")]
	if w.begins_with("drum "):
		if absf(ls - float(line.marks["hold"])) < 1e-6:
			var m: String = drum[k]["mode"]
			if m == "DESPUN":
				return "RESTRAINED in the transfer drum. %s: the drum shuts the port gate, synchronizes with ring %s and opens to the crew tube." % [key("exc.use"), "AB"[k]]
			if m == "SYNCED":
				return "RESTRAINED in the synchronized drum. %s: it shuts the tube door, despins to the spine and opens the port gate. Or go on out to the ring." % key("exc.use")
			return "Transfer drum cycling (%s): stay restrained." % m
		return "TRANSFER DRUM %s. Pull yourself to the restraint station (%s)%s." % ["AB"[k], mv, " - tucked: ring B's 0.9 m port" if tucked() else ""]
	return "CREW TUBE %s. Climb the ladder rung by rung (%s; look down to descend, up to climb). Spin gravity grows toward the ring." % ["AB"[k], mv]

## The short label of what E (the Use button) works now, "" when nothing is in reach (the same order as use()).
func use_label() -> String:
	if move == "LINE":
		if line.zone != "SHIP" and absf(ls - float(line.marks["hold"])) < 1e-6 and absf(lv) < 1e-9:
			return "Use · cycle drum"
		var h := _hatch_in_reach()
		if h != "":
			return "Use · %s %s hatch" % ["close" if hatch[h]["target"] > 0.0 else "open", "outer" if h == "OUTER_HATCH" else "inner"]
		if line.id == "BOARD" and absf(ls - float(line.marks["RING_B"])) < BRANCH_REACH_S:
			return "Use · ring B branch"
		if line.zone != "SHIP" and ls < float(line.marks["port"]) + 1e-6 and float(line.marks["port"]) - ls < USE_REACH_S \
				and closures[_port_gate(WfFrames.ring_index(line.zone))]["value"] < 0.999:
			return "Use · open gate"
		return ""
	var w := _walk_target()
	if w == "ladder":
		return "Use · ladder"
	if w != "":
		return "Use · %s door" % ("close" if circ_doors[w]["target"] > 0.0 else "open")
	return ""

## MOB-001 touch controls now: the stick along the line (1d) or on the deck (2d), the look drag, Use when something is in reach, Ops at
## a trunk panel, View and the ring map (wf_touch.gd draws and routes them; the buttons send the same actions as the keys).
func touch_state() -> Dictionary:
	if actor == null:
		return {}
	var acts := []
	var u := use_label()
	if u != "":
		acts.append(["exc.use", u, "primary_game"])
	if move == "LINE" and line.id == "BOARD" and ls > float(hatch["OUTER_HATCH"]["gate"][1]) and not ctl.busy():
		acts.append(["exc.ops", "Ops · undock" if ctl.mode == "DOCKED" else "Ops · dock", "game"])
	acts.append(["exc.view", "View", "nav"])
	return {"move": "1d" if move == "LINE" else "2d", "look": true, "actions": acts, "utility": [["exc.map", "Map"]],
		"probe": touch_probe, "panels": [hud_goal, hud_prompt, ring_map]}

## The excursion state a browser check reads (-- --touch-probe).
func touch_probe() -> Dictionary:
	return {"scene": "excursion", "move": move, "line": line.id if move == "LINE" else "", "s": snappedf(ls, 0.001), "zone": walk_zone,
		"mode": ctl.mode, "use": use_label(), "yaw": snappedf(yaw, 0.001), "pitch": snappedf(pitch, 0.001),
		"pos": [snappedf(actor.global_position.x, 0.001), snappedf(actor.global_position.y, 0.001), snappedf(actor.global_position.z, 0.001)]}

func _prompt_text() -> String:
	var out: Array = []
	if move == "LINE":
		var h := _hatch_in_reach()
		if h != "":
			out.append("%s %s %s" % [key("exc.use"), "close" if hatch[h]["target"] > 0.0 else "open", {"STATION_HATCH": "the station hatch", "OUTER_HATCH": "Wayfarer's outer hatch", "INNER_HATCH": "the inner hatch"}[h]])
		if line.id == "BOARD" and absf(ls - float(line.marks["RING_B"])) < BRANCH_REACH_S:
			out.append("%s take the ring B branch" % key("exc.use"))
		if use_label() == "Use · open gate":
			out.append("%s open the spine-port gate" % key("exc.use"))
		if line.zone != "SHIP" and absf(ls - float(line.marks["hold"])) < 1e-6:
			out.append("%s cycle the transfer drum" % key("exc.use"))
		if coasting:
			out.append("coasting %.2f m/s (no rail in reach)" % absf(lv))
	else:
		var d := _walk_target()
		if d == "ladder":
			out.append("%s take the ladder" % key("exc.use"))
		elif d != "":
			out.append("%s %s door %s" % [key("exc.use"), "close" if circ_doors[d]["target"] > 0.0 else "open", str(d).trim_prefix("CIRC.")])
	out.append("%s view" % key("exc.view"))
	var t := "  ·  ".join(out)
	if prompt != "":
		t = prompt + "\n" + t
		prompt = ""
	if refusal_t > 0.0:
		t = refusal + "\n" + t
	return t

func _update_hud() -> void:
	hud_goal.text = _goal_text()
	var lines_out: Array = []
	for r in ["RING_A", "RING_B"]:
		var rec: Dictionary = progress[r]
		lines_out.append("%s  %s board  %s circuit (%d%%)  %s back aboard the station" % [("Ring A" if r == "RING_A" else "Ring B"),
			"[x]" if rec["boarded"] else "[ ]", "[x]" if rec["circuit"] else "[ ]", int(100.0 * rec["bins"].count(1) / BINS), "[x]" if rec["returned"] else "[ ]"])     # ASCII: the web font has no ballot boxes
	hud_check.text = "\n".join(lines_out)
	hud_prompt.text = _prompt_text()
	if WfInput.compact():
		hud_prompt.position.y = hud_goal.position.y + hud_goal.size.y + 6.0     # the goal's height follows its text
	var g := actor.field_now.length() / 9.80665
	var rings := "rings %s %.0f %%" % [ctl.ring_state, 100.0 * ctl.spin_frac]
	var drums := "drums A %s, B %s" % [drum[0]["mode"], drum[1]["mode"]]
	hud_status.text = "SIMULATION_ONLY · PROTOTYPE geometry · %s · %s · field %.3f g · mode %s · %s · %s · %s%s" % [where(),
		"walking" if move == "WALK" else ("coasting" if coasting else "hand over hand"), g, ctl.mode, rings, drums,
		"station docked" if ctl.docked else "station stand-off (display)", " · ramp x%d time-lapse" % int(TIMELAPSE) if ctl.busy() else ""]
