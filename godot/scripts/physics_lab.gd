extends Node3D
## PHYS-001 physics lab, SIMULATION_ONLY: a closed PROTOTYPE compartment with two handrails, a loose tool and a crew actor. Godot only collides;
## the field, masses, reach and push limit come from the rig's `dynamics` block (generated/wf_sim_rig.json, contract 27).
##   godot --path godot res://scenes/physics_lab.tscn [-- --check-physics]   (the check prints one WF_GODOT_PHYSICS line)
## Keys: mouse look (click to capture, Esc to release), G grab the nearest reachable handrail, Space push toward the look direction (while
## gripping), R release, T hold/release the tool, W A S D walk (floor and field only), 1 SHIP, 2 RING_A, 3 RING_B, M request the next mode (steps, ring ramp, interlock), K skip 60 s of the ring ramp, P next profile,
## E tethered EVA drill (SHIP frame, EVA mode, 2.0 m PROTOTYPE tension-only tether clipped at rail 1; impulses logged), U unclip/clip,
## V step the ring A vestibule handoff (restrain, sync drum, equalize, open the ring side, hand the occupant's (r, v) over, close), O occupants securable on/off.

const LAB := Vector3(4.0, 2.0, 2.0)        # PROTOTYPE interior: x along the ship, y up, z across (m)
const WALL := 0.1                          # PROTOTYPE wall thickness (m)
const RAIL_GAP := 2.5                      # PROTOTYPE rail spacing (m)
const RAIL_RADIUS := 0.025                 # PROTOTYPE
const MODES := ["COAST", "LOW_THRUST", "HIGH_POWER", "DOCKED", "EVA"]
const SKIP_S := 60.0                       # PROTOTYPE presentation: K skips this much ring-ramp clock (alpha unchanged; real time is 1800 s)
const PROFILES := ["human_iva", "human_suited"]

var rig: Dictionary
var dyn: Dictionary
var field: WfFrameField
var modes: WfModeController
var world: Node3D
var actor: WfCrewBody
var tool: WfTool
var rails: Array = []
var recorder: WfRecorder
var profile_name := "human_iva"
var checking := false
var camera := Camera3D.new()
var hud := Label.new()
var vest: WfVestibule
var vest_step := 0
var tether: WfTether
var shot_offset := Vector3.INF            # review stills: a third-person camera at actor + offset looking at the actor
var tether_line := MeshInstance3D.new()
var yaw := 0.0
var pitch := 0.0
var review: WfReviewGuide                 # U03: the guided vestibule drill (review menu or -- --review=vestibule)
var vview: WfVestibuleView                # U03: the drum, hatches and occupant the drill drives (display only)

func _ready() -> void:
	WfInput.context = "lab"                      # ACI-10: the guide and the Codex read this scene's actions
	var path := "res://generated/wf_sim_rig.json"
	if not FileAccess.file_exists(path):
		push_error("ERROR: generated/wf_sim_rig.json missing (copy simulations/wf_sim_rig.json there)")
		get_tree().quit(1)
		return
	rig = JSON.parse_string(FileAccess.get_file_as_string(path))
	dyn = rig["dynamics"]
	field = WfFrameField.new(dyn)
	modes = WfModeController.new(dyn, field)
	vest = WfVestibule.new(dyn, 0)
	checking = "--check-physics" in OS.get_cmdline_user_args()
	add_child(camera)
	camera.current = true
	var layer := CanvasLayer.new()
	hud.position = Vector2(12, 8)
	hud.add_theme_font_size_override("font_size", 14)
	layer.add_child(hud)
	add_child(layer)
	var env := WorldEnvironment.new()
	env.environment = Environment.new()
	env.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.environment.ambient_light_color = Color(0.8, 0.85, 0.9)
	add_child(env)
	build({})
	tether_line.mesh = ImmediateMesh.new()
	add_child(tether_line)
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--capture-lab="):
			await capture_lab(arg.trim_prefix("--capture-lab="))
			get_tree().quit(0)
			return
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--review="):
			WfReviewGuide.pending = arg.trim_prefix("--review=")
	if WfReviewGuide.pending == "vestibule":
		WfReviewGuide.pending = ""
		review = WfReviewGuide.new(WfVestibuleSession.new(self))
		add_child(review)
		build({"walls": false, "rails": false, "actor": false, "tool": false})   # the drill needs no lab box: show the drum instead
		vview = WfVestibuleView.new(self, dyn)
		add_child(vview)
		pitch = -0.35
		hud.visible = false                   # the guide carries the steps; the lab text stays its muted detail line (I)
		if "--check-review" in OS.get_cmdline_user_args():
			await check_review()
			return
		for arg in OS.get_cmdline_user_args():
			if arg.begins_with("--capture-drill="):   # stills of the drill view after each V (needs a display)
				await capture_drill(arg.trim_prefix("--capture-drill="))
				get_tree().quit(0)
				return
	if checking:
		var c := WfPhysicsCheck.new()
		add_child(c)
		var out: Dictionary = await c.run(self)
		print("WF_GODOT_PHYSICS " + JSON.stringify(out))
		get_tree().quit(0 if out["result"] == "PASS" else 1)

func ring_radius() -> float:
	return dyn["rings"][0]["floor_radius_m"]

func centre() -> Vector3:
	return Vector3(0.0, -ring_radius() + LAB.y * 0.5, 0.0) if field.ring_zone() else Vector3.ZERO

func rail(i: int) -> WfHandhold:
	return rails[i - 1]

func _box(parent: Node, pos: Vector3, size: Vector3) -> void:
	var sb := StaticBody3D.new()
	sb.position = pos
	var cs := CollisionShape3D.new()
	var bx := BoxShape3D.new()
	bx.size = size
	cs.shape = bx
	sb.add_child(cs)
	var mi := MeshInstance3D.new()
	var bm := BoxMesh.new()
	bm.size = size
	mi.mesh = bm
	sb.add_child(mi)
	var pm := PhysicsMaterial.new()
	pm.friction = 0.0
	pm.bounce = 0.0
	sb.physics_material_override = pm
	parent.add_child(sb)

## Rebuild the world. Options: zone, mode, profile, actor (bool), tool (bool), walls (bool), rails (bool), actor_pos, actor_vel, tool_pos, tool_vel.
func build(o: Dictionary) -> void:
	if world:
		remove_child(world)
		world.free()
	world = Node3D.new()
	add_child(world)
	rails = []
	actor = null
	tool = null
	recorder = null
	tether = null
	field.set_state(o.get("zone", field.zone), o.get("mode", field.mode))
	if o.has("mode"):
		modes = WfModeController.new(dyn, field, o["mode"])      # a settled mode set directly (checks, demos)
	else:
		modes.apply()
	profile_name = o.get("profile", profile_name)
	var c := centre()
	if o.get("walls", true):
		var hl := LAB * 0.5
		_box(world, c + Vector3(0, -hl.y - WALL * 0.5, 0), Vector3(LAB.x + 2 * WALL, WALL, LAB.z + 2 * WALL))
		_box(world, c + Vector3(0, hl.y + WALL * 0.5, 0), Vector3(LAB.x + 2 * WALL, WALL, LAB.z + 2 * WALL))
		for s in [-1.0, 1.0]:
			_box(world, c + Vector3(s * (hl.x + WALL * 0.5), 0, 0), Vector3(WALL, LAB.y, LAB.z + 2 * WALL))
			_box(world, c + Vector3(0, 0, s * (hl.z + WALL * 0.5)), Vector3(LAB.x + 2 * WALL, LAB.y, WALL))
	if o.get("rails", true):
		for i in 2:
			var h := WfHandhold.new()
			h.anchor_id = "LAB_RAIL_%d" % (i + 1)
			h.name = h.anchor_id
			h.position = c + Vector3((-0.5 + i) * RAIL_GAP, 0, 0)
			var cs := CollisionShape3D.new()
			var cyl := CylinderShape3D.new()
			cyl.radius = RAIL_RADIUS
			cyl.height = LAB.z - 0.1
			cs.shape = cyl
			cs.rotation = Vector3(PI * 0.5, 0, 0)
			h.add_child(cs)
			var mi := MeshInstance3D.new()
			var cm := CylinderMesh.new()
			cm.top_radius = RAIL_RADIUS
			cm.bottom_radius = RAIL_RADIUS
			cm.height = cyl.height
			mi.mesh = cm
			mi.rotation = cs.rotation
			h.add_child(mi)
			world.add_child(h)
			rails.append(h)
	if o.get("actor", true):
		actor = WfCrewBody.new()
		actor.configure(dyn, profile_name, field)
		var p: Vector3 = c + Vector3(-RAIL_GAP * 0.5 + 0.5, 0, 0)
		if field.ring_zone():
			p.y = -ring_radius() + actor.profile["height_m"] * 0.5 + 0.02
		actor.position = o.get("actor_pos", p)
		world.add_child(actor)
		actor.linear_velocity = o.get("actor_vel", Vector3.ZERO)
	if o.get("tool", true):
		tool = WfTool.new()
		tool.field = field
		tool.position = o.get("tool_pos", c + Vector3(-RAIL_GAP * 0.5 + 1.0, 0.3, 0.3))
		world.add_child(tool)
		tool.linear_velocity = o.get("tool_vel", Vector3.ZERO)

func start_recording(scenario: String) -> WfRecorder:
	recorder = WfRecorder.new()
	recorder.scenario = scenario
	recorder.field = field
	recorder.rig = rig
	recorder.scene = scene_block()
	if actor:
		recorder.bodies["actor"] = actor
		recorder.grip_of = func(): return actor.grip.anchor_id if actor.grip else ""
	if tool:
		recorder.bodies["tool"] = tool
	world.add_child(recorder)
	return recorder

func scene_block() -> Dictionary:
	var sc := {"room": {"interior_m": _a(LAB), "wall_m": WALL, "centre_m": _a(centre()), "prototype": true}, "zone": field.zone, "mode": field.mode, "handholds": [], "bodies": {}}
	var k := WfFrames.ring_index(field.zone)
	if k >= 0:
		sc["ring"] = {"name": dyn["rings"][k]["name"], "centre_x_m": dyn["rings"][k]["centre_x_m"], "floor_radius_m": dyn["rings"][k]["floor_radius_m"], "sign": dyn["rings"][k]["sign"]}
	for h in rails:
		var half := Vector3(0, 0, (LAB.z - 0.1) * 0.5)
		sc["handholds"].append({"anchor_id": h.anchor_id, "anchor_point": _a(h.anchor_point()), "rail_start": _a(h.global_position - half), "rail_end": _a(h.global_position + half), "radius_m": RAIL_RADIUS})
	if actor:
		sc["bodies"]["actor"] = {"kind": "actor", "profile": profile_name, "capsule_radius_m": actor.profile["radius_m"], "capsule_height_m": actor.profile["height_m"], "mass_kg": actor.profile["mass_kg"]}
	if tool:
		sc["bodies"]["tool"] = {"kind": "tool", "box_size_m": _a(WfTool.SIZE), "mass_kg": WfTool.MASS_KG, "prototype": true}
	return sc

static func _a(v: Vector3) -> Array:
	return [v.x, v.y, v.z]

# ---- interactive ----

func _unhandled_input(e: InputEvent) -> void:
	if checking:
		return
	if e is InputEventMouseMotion and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
		yaw -= e.relative.x * 0.003
		pitch = clampf(pitch - e.relative.y * 0.003, -1.5, 1.5)
	elif e is InputEventMouseButton and e.pressed:
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	elif WfInput.pressed(e):
		match WfInput.key_of(e, ["lab"]):              # ACI-10: player.grab/release/push and lab.* actions, ui.cancel
			KEY_ESCAPE:
				if review and Input.mouse_mode != Input.MOUSE_MODE_CAPTURED:
					get_tree().change_scene_to_file("res://scenes/review.tscn")
				Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
			KEY_G: if actor: actor.grab_nearest(rails)
			KEY_R: if actor: actor.release()
			KEY_SPACE: if actor: actor.push(look_dir())
			KEY_T:
				if actor and tool:
					if actor.held_tool: actor.release_tool()
					else: actor.grab_tool(tool)
			KEY_1: build({"zone": "SHIP"})
			KEY_2: build({"zone": "RING_A"})
			KEY_3: build({"zone": "RING_B"})
			KEY_M: modes.request(MODES[(MODES.find(modes.target if modes.busy() else modes.mode) + 1) % MODES.size()])
			KEY_K: modes.skip(SKIP_S)
			KEY_P: build({"profile": PROFILES[(PROFILES.find(profile_name) + 1) % PROFILES.size()]})
			KEY_E: build_tethered()
			KEY_U:
				if tether:
					if tether.clipped: tether.unclip()
					else: tether.clip()
			KEY_O:
				modes.occupants_securable = not modes.occupants_securable
				modes.resume()
			KEY_V: vestibule_step()

## E: the same crew actor (WfTetheredBody extends WfCrewBody) gripping rail 1, clipped to it by the training tether. Push with Space.
func build_tethered() -> void:
	build({"zone": "SHIP", "mode": "EVA", "actor": false, "tool": true})
	var b := WfTetheredBody.new()
	b.configure(dyn, profile_name, field)
	b.position = rail(1).anchor_point() + Vector3(0.3, 0, 0)
	world.add_child(b)
	actor = b
	tether = WfTether.new(rail(1).anchor_point(), 2.0, true, rail(1).anchor_id)
	b.tether = tether
	b.grab(rail(1))

## The occupant's restraint pose in ring A's drum, ship axes (Blender), ring A at the index: the hold point of the rig's access line.
func hold_pose() -> Array:
	var a: Dictionary = dyn["stages"]["access"]
	return a["line"][int(a["hold_index"])]["p"]

## V: one step of the DYN-027 handoff on ring A's vestibule. The drum cycle time is OPEN: the 4 s ramp is a labelled presentation value.
func vestibule_step() -> void:
	var w := modes.omega_now(0)
	if vest.ramping:                          # U03: a step never runs over a ramp; the drill waits for the drum to finish
		vest._entry("wait", false, "drum still changing speed: wait until it matches, then press V")
		return
	match vest_step % 7:
		0:
			vest = WfVestibule.new(dyn, 0)
			vest.restrained = true
			vest._entry("restrain", true, "occupant restrained in the drum seat; both closures closed")
		1: vest.start_sync("RING", w, 4.0)
		2:
			vest.dp_equalized = true
			vest._entry("equalize", true, "pressure shown equalized on both sides (manual gauges; threshold OPEN)")
		3:
			if not vest.open("RING", w)["ok"]:
				return                        # refused by the gate (reason in the log): stay on this step
		4:
			# J01: the occupant at the real drum restraint pose (rig dynamics.stages.access, the hold point of the access line, ring A at the index)
			var cx: float = dyn["rings"][0]["centre_x_m"]
			var r: Array = hold_pose()
			var v := WfFrames.cross(WfFrames.v3(w, 0, 0), WfFrames.v3(0, r[1], r[2]))
			var h := WfVestibule.handoff_to_ring(r, v, cx, 0.0, WfFrames.v3(w, 0, 0))
			vest._entry("handoff", true, "at the drum restraint pose (x %.2f m, %.2f m from the axis): ship v %.3f m/s -> ring-frame v %.3f m/s (r and v transformed with w x r)" % [r[0], sqrt(r[1] ** 2 + r[2] ** 2),
				sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2), sqrt(h[1][0] ** 2 + h[1][1] ** 2 + h[1][2] ** 2)])
		5: vest.close("RING")
		6: vest.start_sync("STATIONARY", w, 4.0)
	vest_step += 1

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

func _physics_process(dt: float) -> void:
	if not checking:
		modes.advance(dt)
		vest.step(dt)
	if checking or actor == null:
		return
	var b := ref_basis() * Basis.from_euler(Vector3(0, yaw, 0))
	var d := Vector3.ZERO
	d -= b.z * (WfInput.strength("player.move_forward") - WfInput.strength("player.move_back"))
	d += b.x * (WfInput.strength("player.move_right") - WfInput.strength("player.move_left"))
	actor.walk_dir = d

func _process(_dt: float) -> void:
	var im: ImmediateMesh = tether_line.mesh
	im.clear_surfaces()
	if tether and actor and tether.clipped:
		im.surface_begin(Mesh.PRIMITIVE_LINES)
		im.surface_add_vertex(tether.anchor)
		im.surface_add_vertex(actor.global_position)
		im.surface_end()
	if actor and shot_offset != Vector3.INF:
		camera.global_transform = Transform3D(Basis.IDENTITY, actor.global_position + shot_offset).looking_at(actor.global_position, Vector3.UP)
	elif actor:
		camera.global_transform = Transform3D(ref_basis() * Basis.from_euler(Vector3(pitch, yaw, 0)), actor.global_position + actor.up_now * 0.6)
	elif tool:
		camera.global_transform = Transform3D(Basis.IDENTITY, tool.global_position + Vector3(0, 0, 3))
	elif vview:                                   # orbit the drum (mouse captured: move to turn the view)
		var b := Basis.from_euler(Vector3(pitch, yaw + 0.6, 0))
		camera.global_transform = Transform3D(b, vview.position + Vector3(0, 0.6, 0) + b.z * 5.5)
	var f := actor.field_now if actor else Vector3.ZERO
	var t := "SIMULATION_ONLY - PROTOTYPE compartment %s m, rails, tool 2 kg; numbers from the rig (contract %s)\n" % [str(LAB), str(rig.get("contract_version"))]
	t += "zone %s   mode %s   profile %s (%s)\n" % [field.zone, field.mode, profile_name, dyn["profiles"][profile_name]["status"]]
	t += modes.hud_text()
	if not modes.log.is_empty() and modes.log[-1].get("refused", false):
		t += "refused: %s (SIMULATION_ONLY)\n" % modes.log[-1]["reason"]
	t += "vestibule crossing %s (%s)\n" % ["OPEN" if modes.can_cross("VESTIBULE_1") else "BLOCKED", modes.cross_reason]
	t += vest.hud_text(modes.omega_now(0))
	if tether:
		t += tether.label() + "\n"
	t += "field %.4f g  dir %s\n" % [f.length() / dyn["standard_gravity_m_s2"], str((f.normalized() * 1000.0).round() / 1000.0)]
	if actor:
		t += "velocity %s m/s   speed %.4f   grip %s   tool %s   %s\n" % [str(actor.v_solved), actor.v_solved.length(),
			actor.grip.anchor_id if actor.grip else "-", "held" if actor.held_tool else "loose", "standing" if actor.standing else "free"]
	hud.text = t

# ---- review stills (needs a display): godot --path godot res://scenes/physics_lab.tscn -- --capture-lab=<dir> ----

func _wait(n: int) -> void:
	for i in n:
		await get_tree().physics_frame

func _still(dir: String, name: String) -> void:
	for n in world.get_children():                 # cutaway for the review camera: hide the near (+z) wall's mesh, its collision stays
		if n is StaticBody3D and not (n is WfHandhold) and n.position.z > centre().z + 0.5:
			for m in n.get_children():
				if m is MeshInstance3D:
					m.visible = false
	_tint(actor, Color(0.95, 0.55, 0.2))
	_tint(tool, Color(0.95, 0.85, 0.2))
	for r in rails:
		_tint(r, Color(0.3, 0.6, 0.95))
	for i in 3:
		await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(dir.path_join(name + ".png"))

func _tint(n: Node, c: Color) -> void:
	if n == null:
		return
	var m := StandardMaterial3D.new()
	m.albedo_color = c
	for k in n.get_children():
		if k is MeshInstance3D:
			k.material_override = m

## The vertical slice on one controller: grip, off-centre push (spin), drift past a loose tool, catch; the tethered drill; the vestibule steps.
func capture_lab(dir: String) -> void:
	DirAccess.make_dir_recursive_absolute(dir)
	var key := DirectionalLight3D.new()                # review light only (presentation): shapes read against the walls
	key.rotation = Vector3(-0.9, 0.5, 0.0)
	add_child(key)
	var lm := StandardMaterial3D.new()
	lm.albedo_color = Color(0.2, 1.0, 0.4)
	lm.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	tether_line.material_override = lm
	build({"zone": "SHIP", "mode": "COAST", "profile": "human_iva", "tool_pos": Vector3(0.0, 0.6, 0.0), "tool_vel": Vector3(0.0, -0.05, 0.08)})
	shot_offset = Vector3(0.0, 0.8, 3.6)
	await _wait(5)
	actor.grab(rail(1))
	await _wait(10)
	await _still(dir, "lab_1_grip")
	actor.push(Vector3.RIGHT, -1.0, Vector3(0.0, 0.25, 0.0))     # off the centre of mass: the body turns as it drifts
	await _wait(55)
	await _still(dir, "lab_2_drift_spin")
	while not actor.can_reach(rail(2)):
		await _wait(1)
	actor.grab(rail(2))
	await _wait(20)
	await _still(dir, "lab_3_catch")
	build_tethered()
	shot_offset = Vector3(0.5, 1.2, 3.8)
	await _wait(5)
	actor.push(Vector3(1.0, 0.25, 0.0), -1.0, Vector3.ZERO)
	var guard := 0
	while tether.events == 0 and guard < 600:
		await _wait(1)
		guard += 1
	await _wait(30)
	await _still(dir, "lab_4_tether_taut")
	for i in 5:
		vestibule_step()
		vest.step(5.0)
	await _still(dir, "lab_5_vestibule_handoff")
	build({"zone": "RING_A", "mode": "COAST", "profile": "human_iva"})
	shot_offset = Vector3(0.0, 0.8, 3.6)
	await _wait(90)
	await _still(dir, "lab_6_ring_a_standing")

func capture_drill(dir: String) -> void:
	DirAccess.make_dir_recursive_absolute(dir)
	await _wait(30)
	get_viewport().get_texture().get_image().save_png(dir.path_join("drill_0.png"))
	for k in 7:
		vestibule_step()
		await _wait(330)
		get_viewport().get_texture().get_image().save_png(dir.path_join("drill_%d.png" % (k + 1)))

## U03 headless: drive the guided drill with V only, try V during the drum ramp (refused, step kept), and finish all seven steps on the
## vestibule model's own state; prints one WF_GODOT_REVIEW line.
func check_review() -> void:
	var s: WfVestibuleSession = review.session
	var refused := false
	for k in 7:
		var want := review.index + 1
		vestibule_step()
		if vest.ramping and not refused:
			var before := vest_step
			vestibule_step()
			refused = vest_step == before and vest.log[-1]["action"] == "wait" and not vest.log[-1]["ok"]
		for i in 900:
			await get_tree().physics_frame
			if review.index >= want:
				break
	var out := {"session": "vestibule", "steps": review.events, "complete": review.complete, "refusal_shown": refused,
		"labels": range(7).map(func(i): return s.labels(i)), "drum_w_end": vest.drum_w}
	out.labelled = range(7).all(func(i): return not s.labels(i).is_empty())
	out.result = "PASS" if review.complete and refused and out.labelled and absf(vest.drum_w) <= vest.tol() else "FAIL"
	print("WF_GODOT_REVIEW " + JSON.stringify(out))
	get_tree().quit(0 if out.result == "PASS" else 1)
