class_name WfEvaOps
extends Node3D
## EVA Operations (EVA-OPS-001, docs/EVA_OPERATIONS.md): the suited astronaut and the companion drone outside Wayfarer, both live in one
## fixed-step simulation. SIMULATION_ONLY / TRAINING: FLIGHT_EVA is HOLD in the canon (45 O-07), so "operational" here means the
## operational rules are enforced, never that an EVA is cleared. Godot holds no EVA facts: masses, gas, nozzles, allocation, the Brow, the
## holds and the hazards come from the package (WfEvaPkg, data/simulations/wf_eva_ops.json); the ship frame and its modes from the rig.
##
## Switching control changes only which body reads the stick: the other keeps its position, attitude, velocities, gas and equipment and
## goes on under physics and whatever control it was explicitly given (assisted holds, a drone mode).

const LAYER_BODY := 2
const SUIT_VARIANT := "instructor"

var pkg: Dictionary
var rig: Dictionary
var world: WfEvaWorld
var field: WfFrameField
var suit: WfEvaBody
var drone: WfEvaBody
var suit_ctl: WfEvaControl
var drone_ctl: WfEvaControl
var dops: WfDroneOps
var scenario: WfEvaScenario
var hud: WfEvaHud
var cam: Camera3D
var ship: Node3D
var a_suit: WfAllocator
var a_free: WfAllocator
var a_near: WfAllocator
var a_docked: WfAllocator
var reserve: WfN2Tank
var drone_gas: WfN2Tank
var cartridges: Array = []          # every WfCartridge that has left the rack
var cartridge_seated: WfCartridge = null
var suit_vis: Node3D
var drone_vis: Node3D
var active := "suit"
var docked := false                 # start_free() captures the drone onto the suit (feeds, mass, inertia)
var training := true
var frame_mode := "DRIFT"
var cam_mode := {"suit": 0, "drone": 0}
var cam_yaw := 0.0
var cam_pitch := -0.25
var cam_dist := 4.5
var messages: Array = []
var hold_id := ""
var checkpoint := {}
var rescues := 0
var rescue_failures := 0
var hazard_now := {"suit": {}, "drone": {}}
var check                            # WfEvaCheck while a headless check runs
var t_sim := 0.0
var com_suit := Vector3.ZERO         # suit body origin in the suit frame (the suit's mass centre)
var pair_off := Vector3.ZERO         # pair mass centre from the suit mass centre (suit frame), docked
var dock_local := Transform3D.IDENTITY
var drone_com := Vector3.ZERO
var faults := 0
var walk_speed := 0.6
var stowed_cartridges := 0
var vented_kg := 0.0
var start_kind := "WALKWAY"          # LOCO-002: Explore Exterior starts on the magnetic walkway; HATCH is the classic start at the airlock hold
var suit_rig: WfCharacterRig = null
var suit_model_ok := false
var _boot_events_seen := 0
var _oneshot := ""

func _ready() -> void:
	pkg = WfEvaPkg.load_package()
	if pkg.is_empty():
		var l := Label.new()
		l.text = "EVA Operations: no package (data/simulations/wf_eva_ops.json). Run python3 src/wayfarer/eva_ops.py, then runtime-export."
		var cl := CanvasLayer.new()
		cl.add_child(l)
		add_child(cl)
		return
	rig = _json(["res://generated/wf_sim_rig.json", ProjectSettings.globalize_path("res://").path_join("../data/simulations/wf_sim_rig.json")])
	field = WfFrameField.new(rig["dynamics"], "SHIP", "EVA")
	_environment()
	_ship()
	world = WfEvaWorld.new()
	world.show_surfaces = ship == null
	world.name = "EvaWorld"
	add_child(world)
	world.build(pkg)
	walk_speed = float(pkg["rules"]["walk_speed_m_s"])
	_bodies()
	cam = Camera3D.new()
	cam.near = 0.05
	cam.far = 4000.0
	cam.fov = 70.0
	add_child(cam)
	cam.current = true
	hud = WfEvaHud.new()
	add_child(hud)
	hud.setup(self)
	scenario = WfEvaScenario.new(self)
	WfInput.context = "evaops"
	start_kind = requested_start()
	start_free(false)
	if start_kind == "WALKWAY":
		start_walkway(false)
	WfWebPage.scene("exterior")
	print("WF_EVA_OPS ready")
	if "--check-eva-ops" in OS.get_cmdline_user_args():
		check = WfEvaCheck.new()
		check.run(self)
	elif "--first-flight" in OS.get_cmdline_user_args() or WfWebPage.start_variant() == "first_flight":
		scenario.start()
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--shots="):
			_shots(a.substr(8))

## Review stills (-- --shots=<dir>, needs a rendering display): the five camera modes at the hatch, then the drone undocked.
func _shots(dir: String) -> void:
	DirAccess.make_dir_recursive_absolute(dir)
	if start_kind == "WALKWAY":
		# LOCO-002 the Explore Exterior start: standing on the boots, walking (W through the input layer), then released and drifting
		active = "suit"
		cam_mode["suit"] = 0
		for step in [["mag_1_stand", 60, ""], ["mag_2_walk", 300, "fwd"], ["mag_3_release", 150, "release"]]:
			if step[2] == "fwd":
				Input.action_press("evaops.fwd")
			elif step[2] == "release":
				Input.action_release("evaops.fwd")
				push_off()                  # Space with the boots attached: both release and the legs push off along the plate normal
			for i in step[1]:
				await get_tree().physics_frame
			await RenderingServer.frame_post_draw
			get_viewport().get_texture().get_image().save_png(dir.path_join(step[0] + ".png"))
			print("WF_EVA_OPS_SHOT ", step[0], " ", suit_rig.current if suit_model_ok else "(no model)")
		start_walkway(false)
		for i in 30:
			await get_tree().physics_frame
	var plan := [["suit", 0, "astronaut_third_person"], ["suit", 1, "astronaut_helmet"], ["undock", 0, ""], ["drone", 0, "drone_chase"],
		["drone", 1, "drone_sensor"], ["drone", 2, "drone_stabilized"], ["suit", 0, "astronaut_and_drone"]]
	for p in plan:
		if p[0] == "undock":
			undock()
			for i in 180:
				await get_tree().physics_frame
			continue
		active = p[0]
		cam_mode[active] = p[1]
		for i in 20:
			await get_tree().process_frame
		await RenderingServer.frame_post_draw
		get_viewport().get_texture().get_image().save_png(dir.path_join(p[2] + ".png"))
		print("WF_EVA_OPS_SHOT ", p[2])
	get_tree().quit()

func _json(paths: Array) -> Dictionary:
	for p in paths:
		if FileAccess.file_exists(p):
			var d = JSON.parse_string(FileAccess.get_file_as_string(p))
			if d is Dictionary:
				return d
	return {}

func _environment() -> void:
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.01, 0.012, 0.02)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.22, 0.24, 0.3)
	env.ambient_light_energy = 0.6
	var we := WorldEnvironment.new()
	we.environment = env
	add_child(we)
	var sun := DirectionalLight3D.new()
	sun.light_energy = 1.6
	sun.rotation = Vector3(-0.6, 0.9, 0.0)
	add_child(sun)
	var fill := DirectionalLight3D.new()
	fill.light_energy = 0.35
	fill.rotation = Vector3(0.5, -2.2, 0.0)
	add_child(fill)

func _ship() -> void:
	for p in ["res://generated/wayfarer_docked.glb"]:
		if ResourceLoader.exists(p):
			ship = load(p).instantiate()
			add_child(ship)
			var man := _json(["res://generated/manifest_docked.json"])
			if not man.is_empty():
				WfProductionLayer.apply(ship, man)
				WfFractalShield.apply(ship, man.get("look", {}).get("exterior", {}).get("grammar", {}).get("fractal_shield", {}))
			return

## The suit and drone visuals: the exported canonical GLBs when the package carries them, else labelled proxies of the same size.
func _visual(paths: Array) -> Node3D:
	for p in paths:
		if ResourceLoader.exists(p):
			var r = load(p)
			if r is PackedScene:
				return r.instantiate()
		var abs_p := ProjectSettings.globalize_path(p)
		if FileAccess.file_exists(abs_p):
			var doc := GLTFDocument.new()
			var st := GLTFState.new()
			if doc.append_from_file(abs_p, st) == OK:
				return doc.generate_scene(st)
	return null

func _bodies() -> void:
	var ve := float(pkg["gas"]["ve_m_s"])
	var sp: Dictionary = pkg["suit"]
	var dp: Dictionary = pkg["drone"]
	var al: Dictionary = pkg["allocation"]
	reserve = WfN2Tank.new("SUIT_RESERVE", "Suit N2 reserve", float(sp["reserve"]["n2_kg"]), float(sp["reserve"]["usable_kg"]), float(sp["reserve"]["feed_pa"]))
	drone_gas = WfN2Tank.new("DRONE_N2", "Drone N2 vessels", float(dp["vessels"]["n2_kg"]), float(dp["vessels"]["usable_kg"]), float(dp["vessels"]["feed_pa"]))
	a_suit = WfAllocator.new("suit_reserve", al["suit_reserve"], sp["nozzles"])
	a_free = WfAllocator.new("drone_free", al["drone_free"], dp["nozzles"])
	a_near = WfAllocator.new("drone_near_suit", al["drone_near_suit"], dp["nozzles"])
	a_docked = WfAllocator.new("docked", al["docked"], al["docked"]["nozzle_layout"])
	com_suit = WfEvaPkg.v(sp["com_suit_frame"])
	pair_off = WfEvaPkg.v(al["docked"]["pair_com_from_suit_com"])
	drone_com = WfEvaPkg.v(dp["com_local"])
	var B: Array = pkg["dock"]["basis_columns"]
	dock_local = Transform3D(Basis(WfEvaPkg.v(B[0]), WfEvaPkg.v(B[1]), WfEvaPkg.v(B[2])), WfEvaPkg.v(pkg["dock"]["origin"]))
	# ---- suit
	suit = WfEvaBody.new()
	suit.name = "Astronaut"
	suit.field = field
	suit.setup_eva("suit", float(sp["dry_kg"]), WfEvaPkg.v(sp["inertia_kg_m2"]), ve)
	suit.onboard = [reserve]
	suit.feeds = [reserve]
	suit.alloc = a_suit
	suit.walk_friction = float(pkg["rules"]["walk_friction"])
	suit.support_cos = float(pkg["rules"]["surface_normal_min"])
	suit.tether_len = float(pkg["rules"]["tether_length_m"])
	suit.collision_layer = LAYER_BODY
	suit.collision_mask = WfEvaWorld.LAYER_WORLD | LAYER_BODY
	var cs := CollisionShape3D.new()
	var cap := CapsuleShape3D.new()
	cap.radius = 0.32
	cap.height = 1.84
	cs.shape = cap
	cs.position = Vector3(0, 0.92, 0.06) - com_suit
	suit.add_child(cs)
	var sv := Node3D.new()
	sv.name = "SuitVisual"
	sv.position = -com_suit
	suit.add_child(sv)
	suit_vis = sv
	# LOCO-002: the Y155 suit model and its clips (WfCharacterRig strips root motion; the body's physics moves it). A missing suit is shown
	# as the labelled proxy and reported to the page (wayfarerEva.model false), never silently.
	var meta := _json(["res://generated/characters/eva_characters.json"])
	suit_rig = WfCharacterRig.new()
	suit_rig.name = "SuitRig"
	suit_model_ok = suit_rig.setup("res://generated/characters/eva_%s.glb" % SUIT_VARIANT, meta.get("variants", {}).get(SUIT_VARIANT, {}))
	if suit_model_ok:
		sv.add_child(suit_rig)
		suit_rig.play("eva_mag_stand" if suit_rig.has("eva_mag_stand") else "eva_float", 1.0, 0.0)
	else:
		push_warning("LOCO-002: the Y155 suit model is missing from this package (%s)" % suit_rig.missing)
		_proxy_suit(sv)
		var tag := Label3D.new()
		tag.text = "SUIT MODEL MISSING (proxy shown)\n%s" % suit_rig.missing
		tag.font_size = 28
		tag.pixel_size = 0.002
		tag.position = Vector3(0, 2.1, 0)
		tag.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		tag.modulate = Color(1.0, 0.35, 0.25)
		sv.add_child(tag)
	add_child(suit)
	if pkg.has("mag_boots"):
		suit.boots = WfMagBoots.new(pkg["mag_boots"], world, [Vector3.ZERO, Vector3.ZERO], Vector3.ZERO)
		_boot_points()
	suit_ctl = WfEvaControl.new(suit, pkg["assist"], 0.2)
	# ---- drone
	drone = WfEvaBody.new()
	drone.name = "Drone"
	drone.field = field
	drone.setup_eva("drone", float(dp["dry_kg"]), WfEvaPkg.v(dp["inertia_kg_m2"]), ve)
	drone.onboard = [drone_gas]
	drone.feeds = [drone_gas]
	drone.alloc = a_free
	drone.collision_layer = LAYER_BODY
	drone.collision_mask = WfEvaWorld.LAYER_WORLD
	var dc := CollisionShape3D.new()
	var bx := BoxShape3D.new()
	bx.size = Vector3(0.47, 0.20, 0.55)
	dc.shape = bx
	dc.position = Vector3(0, 0.055, 0) - drone_com
	drone.add_child(dc)
	var dv := Node3D.new()
	dv.name = "DroneVisual"
	dv.position = -drone_com
	drone.add_child(dv)
	drone_vis = dv
	var gd := _visual(["res://generated/characters/eva_drone.glb"])
	if gd != null:
		# the exported drone sits docked in the suit frame (export/eva_gltf.py keeps the system scene's placement): undo that pose so
		# the model lies in the drone's own LOCAL frame (otherwise the dock transform is applied twice and the drone floats beside the suit)
		gd.transform = dock_local.affine_inverse()
		dv.add_child(gd)
	else:
		_proxy_drone(dv)
	add_child(drone)
	drone.add_collision_exception_with(suit)        # the dock channel is not in the capsule: the approach is checked by the autopilot limits
	suit.add_collision_exception_with(drone)
	drone_ctl = WfEvaControl.new(drone, pkg["assist"], 0.5)
	dops = WfDroneOps.new(self, drone_ctl)

func _play_first(n: Node, names: Array) -> void:
	var ap := n.find_child("AnimationPlayer", true, false) as AnimationPlayer
	if ap == null:
		return
	for nm in names:
		if ap.has_animation(nm):
			ap.play(nm)
			return

## The soles in the suit body's frame (its origin is the mass centre, of the pair when docked): the suit frame's origin is the sole plane.
func _boot_points() -> void:
	if suit.boots == null:
		return
	var sole := -(com_suit + (pair_off if docked else Vector3.ZERO))
	var h := float(pkg["mag_boots"]["foot_half_spacing_m"])
	suit.boots.sole_local = sole
	suit.boots.feet_local = [sole + Vector3(h, 0, 0), sole + Vector3(-h, 0, 0)]

## LOCO-002: the suit's clip follows its physics state: on the walkway the magnetic stand / walk (at the floor speed / the clip's speed),
## the attach and release clips once at each boot event, the burn presets' surface walk, and the neutral float otherwise.
func _animate_suit() -> void:
	if not suit_model_ok:
		return
	var b := suit.boots
	if b != null and b.events.size() != _boot_events_seen:
		var ev: Dictionary = b.events[b.events.size() - 1]
		_boot_events_seen = b.events.size()
		if ev["kind"] == "release" or ev["kind"] == "break_away":
			_oneshot = "eva_mag_release"
		elif ev["kind"] == "attach" and b.count() == 2 and not suit_rig.current.begins_with("eva_mag_walk"):
			_oneshot = "eva_mag_attach"
	if _oneshot != "":
		if suit_rig.current != _oneshot:
			suit_rig.play(_oneshot, 1.0, 0.12)
		elif suit_rig.finished():
			_oneshot = ""
		else:
			return
	var n := suit.support_normal
	var v := suit.linear_velocity - n * suit.linear_velocity.dot(n)
	if b != null and b.count() > 0:
		if v.length() > 0.03:
			suit_rig.play("eva_mag_walk", suit_rig.rate_for("eva_mag_walk", v.length()), 0.2)
		else:
			suit_rig.play("eva_mag_stand", 1.0, 0.3)
	elif suit.standing and not suit.held:
		if v.length() > 0.05 and suit_rig.has("walk"):
			suit_rig.play("walk", suit_rig.rate_for("walk", v.length()), 0.25)
		else:
			suit_rig.play("eva_mag_stand", 1.0, 0.3)
	else:
		suit_rig.play("eva_float", 1.0, 0.4)

func _proxy_suit(root: Node3D) -> void:
	var white := _m(Color(0.88, 0.88, 0.84))
	var body := MeshInstance3D.new()
	var c := CapsuleMesh.new()
	c.radius = 0.28
	c.height = 1.6
	body.mesh = c
	body.position = Vector3(0, 0.85, 0)
	body.material_override = white
	root.add_child(body)
	var helm := MeshInstance3D.new()
	var s := SphereMesh.new()
	s.radius = 0.17
	s.height = 0.34
	helm.mesh = s
	helm.position = Vector3(0, 1.62, 0.04)
	helm.material_override = _m(Color(0.42, 0.56, 0.72))
	root.add_child(helm)
	var pack := MeshInstance3D.new()
	var b := BoxMesh.new()
	b.size = Vector3(0.42, 0.6, 0.30)
	pack.mesh = b
	pack.position = Vector3(0, 1.24, -0.14)
	pack.material_override = _m(Color(0.44, 0.62, 0.44))
	root.add_child(pack)
	var tag := Label3D.new()
	tag.text = "PROXY SUIT (canonical GLB not in this package)"
	tag.font_size = 22
	tag.pixel_size = 0.002
	tag.position = Vector3(0, 2.0, 0)
	tag.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	root.add_child(tag)

func _proxy_drone(root: Node3D) -> void:
	var b := MeshInstance3D.new()
	var bm := BoxMesh.new()
	bm.size = Vector3(0.45, 0.17, 0.52)
	b.mesh = bm
	b.position = Vector3(0, 0.06, 0)
	b.material_override = _m(Color(0.84, 0.84, 0.8))
	root.add_child(b)
	var nose := MeshInstance3D.new()
	var nm := BoxMesh.new()
	nm.size = Vector3(0.3, 0.06, 0.04)
	nose.mesh = nm
	nose.position = Vector3(0, 0.08, -0.27)
	nose.material_override = _m(Color(0.08, 0.85, 0.9))
	root.add_child(nose)

func _m(c: Color) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = c
	return m

# ------------------------------------------------------------------------------------------------------------------- frames and poses
## The suit frame (origin between the feet, astronaut faces +Z) in the world.
func suit_frame() -> Transform3D:
	var off := com_suit + (pair_off if docked else Vector3.ZERO)
	return suit.global_transform * Transform3D(Basis.IDENTITY, -off)

## The drone LOCAL frame in the world.
func drone_frame() -> Transform3D:
	return drone.global_transform * Transform3D(Basis.IDENTITY, -drone_com)

## Where the drone's frame sits when docked (world).
func dock_world() -> Transform3D:
	return suit_frame() * dock_local

## Drone body transform (origin at its mass centre) that puts its frame on the dock.
func drone_docked_body() -> Transform3D:
	return dock_world() * Transform3D(Basis.IDENTITY, drone_com)

func place_suit(frame: Transform3D, v := Vector3.ZERO) -> void:
	var off := com_suit + (pair_off if docked else Vector3.ZERO)
	suit.global_transform = frame * Transform3D(Basis.IDENTITY, off)
	suit.linear_velocity = v
	suit.angular_velocity = Vector3.ZERO
	PhysicsServer3D.body_set_state(suit.get_rid(), PhysicsServer3D.BODY_STATE_TRANSFORM, suit.global_transform)
	PhysicsServer3D.body_set_state(suit.get_rid(), PhysicsServer3D.BODY_STATE_LINEAR_VELOCITY, v)
	PhysicsServer3D.body_set_state(suit.get_rid(), PhysicsServer3D.BODY_STATE_ANGULAR_VELOCITY, Vector3.ZERO)

func _set_body(b: RigidBody3D, t: Transform3D, v: Vector3, w: Vector3) -> void:
	b.global_transform = t
	b.linear_velocity = v
	b.angular_velocity = w
	PhysicsServer3D.body_set_state(b.get_rid(), PhysicsServer3D.BODY_STATE_TRANSFORM, t)
	PhysicsServer3D.body_set_state(b.get_rid(), PhysicsServer3D.BODY_STATE_LINEAR_VELOCITY, v)
	PhysicsServer3D.body_set_state(b.get_rid(), PhysicsServer3D.BODY_STATE_ANGULAR_VELOCITY, w)

# ------------------------------------------------------------------------------------------------------------------------- docking
func _inertia_shift(i: Basis, m: float, d: Vector3) -> Basis:
	# parallel-axis term m (|d|^2 E - d d^T)
	var dd := d.dot(d)
	return Basis(i.x + m * (Vector3(dd, 0, 0) - d * d.x), i.y + m * (Vector3(0, dd, 0) - d * d.y), i.z + m * (Vector3(0, 0, dd) - d * d.z))

## Capture: the drone becomes part of the suit body. Momentum is conserved; the body origin moves to the pair's mass centre; the
## pair flies on the drone's live near-suit nozzles and gas (the suit reserve is isolated: one propulsion system at a time).
func capture() -> void:
	var ms := suit.total_mass()
	var md := drone.total_mass()
	var p := suit.linear_velocity * ms + drone.linear_velocity * md
	var Ls := suit.world_inertia() * suit.angular_velocity
	var Ld := drone.world_inertia() * drone.angular_velocity
	var frame := suit_frame()
	docked = true
	var t := frame * Transform3D(Basis.IDENTITY, com_suit + pair_off)
	# pair inertia (suit frame): suit about its CoM moved by -pair_off, drone (rotated into the suit frame) moved by its offset
	var dfrom: Vector3 = WfEvaPkg.v(pkg["allocation"]["docked"]["drone_com_from_suit_com"]) - pair_off
	var i_s := _inertia_shift(suit.inertia_t, ms, -pair_off)
	var rd := dock_local.basis
	var i_d := _inertia_shift(rd * drone.inertia_t * rd.transposed(), md, dfrom)
	suit.inertia_t = Basis(i_s.x + i_d.x, i_s.y + i_d.y, i_s.z + i_d.z)
	suit.carried_kg = drone.dry_kg + drone.carried_kg
	suit.onboard = [reserve, drone_gas]
	if dops.holding != null:
		suit.onboard.append(dops.holding.tank)
	suit.feeds = [drone_gas]
	suit.alloc = a_docked
	var v := p / (ms + md)
	var r := t.basis.orthonormalized()
	var w := (r * suit.inertia_t * r.transposed()).inverse() * (Ls + Ld)
	_set_body(suit, t, v, w)
	suit_vis.position = -(com_suit + pair_off)
	_drone_passenger(true)
	suit_ctl.ref_vel = Vector3.ZERO
	scenario_event("docked")

func _drone_passenger(on: bool) -> void:
	drone.passenger = on
	drone.freeze_mode = RigidBody3D.FREEZE_MODE_KINEMATIC
	drone.freeze = on
	drone.collision_layer = 0 if on else LAYER_BODY
	drone.collision_mask = 0 if on else WfEvaWorld.LAYER_WORLD
	if on:
		drone.global_transform = drone_docked_body()

## Release: the latch opens and the tongue spring pushes the drone straight off the channel at the retreat speed; the suit takes the
## opposite momentum. The suit reserve is armed again.
func undock() -> void:
	if not docked:
		return
	var frame := suit_frame()
	var v := suit.linear_velocity
	var w := suit.angular_velocity
	var md := drone.total_mass()
	docked = false
	var ms := suit.dry_kg + reserve.n2_kg + (cartridge_seated.wet_kg() if cartridge_seated != null else 0.0)
	var u: Vector3 = -frame.basis.orthonormalized().z                    # straight off the channel, behind the astronaut
	var sep := float(pkg["drone"]["near_suit"]["retreat_speed_m_s"])
	var r_s := frame * (com_suit)
	var r_d := (frame * dock_local) * drone_com
	suit.inertia_t = Basis(Vector3(WfEvaPkg.v(pkg["suit"]["inertia_kg_m2"]).x, 0, 0), Vector3(0, WfEvaPkg.v(pkg["suit"]["inertia_kg_m2"]).y, 0), Vector3(0, 0, WfEvaPkg.v(pkg["suit"]["inertia_kg_m2"]).z))
	suit.carried_kg = cartridge_seated.hardware_kg if cartridge_seated != null else 0.0
	suit.onboard = [reserve]
	suit.feeds = [reserve]
	if cartridge_seated != null:
		suit.onboard = [cartridge_seated.tank, reserve]
		suit.feeds = [cartridge_seated.tank, reserve]
	suit.alloc = a_suit
	var pc := suit.global_position
	var vs := v + w.cross(r_s - pc) - u * sep * md / (ms + md)
	var vd := v + w.cross(r_d - pc) + u * sep * ms / (ms + md)
	_set_body(suit, frame * Transform3D(Basis.IDENTITY, com_suit), vs, w)
	suit_vis.position = -com_suit
	_drone_passenger(false)
	_set_body(drone, (frame * dock_local) * Transform3D(Basis.IDENTITY, drone_com), vd, w)
	drone.alloc = a_near
	dops.set_mode(WfDroneOps.Mode.MANUAL)
	scenario_event("undocked")

# ---------------------------------------------------------------------------------------------------------------------- cartridges
## The cartridge arm B can close on: a free one, the seated one, or a fresh one from the rack. Returns a WfCartridge, a reason String,
## or null.
func cartridge_in_reach(sh: Vector3, reach: float):
	var best = null
	var bd := reach
	for c in cartridges:
		var cc: WfCartridge = c
		if cc.where == WfCartridge.Where.FREE or cc.where == WfCartridge.Where.SEATED:
			var p: Vector3 = cc.node.global_position
			var d := sh.distance_to(p)
			if d <= bd:
				var rel := (drone.linear_velocity - (cc.body.linear_velocity if cc.body != null else suit.linear_velocity)).length()
				if rel > 0.05:
					return "Too fast relative to the cartridge (%.3f m/s): match it first." % rel
				bd = d
				best = cc
	if best != null:
		if best.where == WfCartridge.Where.SEATED:
			_unseat(best)
		return best
	var rack: Vector3 = world.station["rack"]
	if sh.distance_to(rack) <= reach + 0.15:
		if int(world.station["cartridges"]) <= 0:
			return "The station rack is empty."
		if drone.linear_velocity.length() > 0.05:
			return "Hold still at the rack (%.3f m/s)." % drone.linear_velocity.length()
		world.station["cartridges"] = int(world.station["cartridges"]) - 1
		var c := WfCartridge.new("RC1-%d" % (cartridges.size() + 1), pkg["cartridge"])
		c.node = _cart_node()
		add_child(c.node)
		c.node.global_position = rack
		cartridges.append(c)
		return c
	return null

func _cart_node() -> Node3D:
	var n := Node3D.new()
	var mi := MeshInstance3D.new()
	var cm := CapsuleMesh.new()
	cm.radius = 0.052
	cm.height = 0.30
	mi.mesh = cm
	mi.rotation = Vector3(PI / 2, 0, 0)
	mi.material_override = _m(Color(0.12, 0.38, 0.95))
	n.add_child(mi)
	return n

func attach_cartridge_to_drone(c: WfCartridge) -> void:
	if c.body != null:
		c.body.queue_free()
		c.body = null
	c.where = WfCartridge.Where.HELD
	drone.carried_kg += c.hardware_kg
	drone.onboard.append(c.tank)

func release_cartridge(c: WfCartridge) -> void:
	drone.carried_kg -= c.hardware_kg
	drone.onboard.erase(c.tank)
	c.where = WfCartridge.Where.FREE
	var b := WfEvaBody.new()
	b.field = field
	b.setup_eva("cartridge", c.hardware_kg, Vector3(0.012, 0.012, 0.004), float(pkg["gas"]["ve_m_s"]))
	b.onboard = [c.tank]
	b.collision_layer = LAYER_BODY
	b.collision_mask = WfEvaWorld.LAYER_WORLD
	var cs := CollisionShape3D.new()
	var sh := CapsuleShape3D.new()
	sh.radius = 0.052
	sh.height = 0.30
	cs.shape = sh
	cs.rotation = Vector3(PI / 2, 0, 0)
	b.add_child(cs)
	add_child(b)
	b.add_collision_exception_with(drone)
	_set_body(b, c.node.global_transform, drone.linear_velocity, drone.angular_velocity)
	c.node.get_parent().remove_child(c.node)
	b.add_child(c.node)
	c.node.transform = Transform3D.IDENTITY
	c.body = b

func seat_cartridge(c: WfCartridge) -> void:
	drone.carried_kg -= c.hardware_kg
	drone.onboard.erase(c.tank)
	c.where = WfCartridge.Where.SEATED
	cartridge_seated = c
	suit.carried_kg += c.hardware_kg
	suit.onboard = [c.tank, reserve]
	suit.feeds = [c.tank, reserve]
	scenario_event("seated")

func _unseat(c: WfCartridge) -> void:
	suit.carried_kg -= c.hardware_kg
	suit.onboard.erase(c.tank)
	suit.feeds.erase(c.tank)
	cartridge_seated = null
	c.where = WfCartridge.Where.HELD

## At the rack: an empty (or used) seated cartridge goes back into its slot; the station keeps it (it is not refilled here).
func stow_cartridge() -> bool:
	if cartridge_seated == null:
		return false
	if suit.global_position.distance_to(world.station["rack"]) > 1.8:
		say("Stow the cartridge at the station rack (%.1f m away)." % suit.global_position.distance_to(world.station["rack"]), false)
		return false
	var c := cartridge_seated
	_unseat(c)
	c.where = WfCartridge.Where.STOWED
	c.node.queue_free()
	stowed_cartridges += 1
	say("Cartridge %s stowed in the rack with %.3f kg N2 left (the dock channel is free for the drone)." % [c.id, c.tank.n2_kg])
	scenario_event("stowed")
	return true

# ------------------------------------------------------------------------------------------------------------------------ simulation
func _physics_process(dt: float) -> void:
	if pkg.is_empty():
		return
	t_sim += dt
	_boot_points()
	var held_active := active
	# ---- the astronaut
	var t_in := Vector3.ZERO
	var r_in := Vector3.ZERO
	if check == null or not check.drives_input:
		t_in = Vector3(WfInput.strength("evaops.left") - WfInput.strength("evaops.right"), WfInput.strength("evaops.up") - WfInput.strength("evaops.down"),
			WfInput.strength("evaops.fwd") - WfInput.strength("evaops.back"))
		r_in = Vector3(WfInput.strength("evaops.pitch_down") - WfInput.strength("evaops.pitch_up"), WfInput.strength("evaops.yaw_left") - WfInput.strength("evaops.yaw_right"),
			WfInput.strength("evaops.roll_right") - WfInput.strength("evaops.roll_left"))
	else:
		t_in = check.t_in
		r_in = check.r_in
	var fine := WfInput.held("evaops.fine")
	var k := 0.25 if fine else 1.0
	var braking := WfInput.held("evaops.brake")
	# player stick to the active body; the other keeps its explicit control
	var scripted_suit: bool = check != null and check.suit_goal != null
	var scripted_drone: bool = check != null and check.drone_goal != null and not docked and dops.mode == WfDroneOps.Mode.MANUAL
	if scripted_suit:
		suit_ctl.step_goto(check.suit_goal, Vector3.ZERO, check.suit_face, check.suit_vmax, check.suit_up)
		if scripted_drone:
			drone_ctl.step_goto(check.drone_goal, Vector3.ZERO, check.drone_face, check.drone_vmax, check.drone_up)
		elif not docked:
			_drone_auto(dt)
	elif scripted_drone:
		_suit_auto_only()
		drone_ctl.step_goto(check.drone_goal, Vector3.ZERO, check.drone_face, check.drone_vmax, check.drone_up)
	elif held_active == "suit":
		_suit_step(t_in, r_in, k, braking)
		_suit_auto()
		if not docked:
			_drone_auto(dt)
	else:
		_suit_auto_only()
		if docked:
			pass
		elif dops.mode == WfDroneOps.Mode.MANUAL:
			drone_ctl.throttle = k
			drone_ctl.brake = braking or (check != null and check.brake)
			drone_ctl.step_player(t_in, r_in)
			dops.step(dt)
		else:
			_drone_auto(dt)
	if not docked:
		var near := drone.global_position.distance_to(suit.global_position) < float(pkg["drone"]["proximity_m"])
		var want := a_near if near else a_free
		if drone.alloc != want:
			want.failed = drone.alloc.failed
			drone.alloc = want
	else:
		drone.global_transform = drone_docked_body()
	# carried cartridges follow
	for c in cartridges:
		var cc: WfCartridge = c
		if cc.where == WfCartridge.Where.HELD and dops.holding == cc:
			var tip := dops.shoulder_b() + drone_frame().basis.orthonormalized() * Vector3(0, -0.02, -0.25)
			cc.node.global_transform = Transform3D(drone_frame().basis, tip)
		elif cc.where == WfCartridge.Where.SEATED:
			cc.node.global_transform = dock_world()
	# hazards
	var op := not training
	hazard_now["suit"] = world.hazard_at(suit.global_position, float(pkg["rules"]["hazard_margin_m"]), op)
	hazard_now["drone"] = world.hazard_at(drone.global_position, float(pkg["rules"]["hazard_margin_m"]), op) if not docked else {}
	scenario.step(dt)
	if check != null:
		check.tick(dt)

func _suit_step(t_in: Vector3, r_in: Vector3, k: float, braking: bool) -> void:
	suit_ctl.throttle = k
	suit_ctl.brake = braking or (check != null and check.brake)
	if suit.standing and not suit.held:
		# feet on the surface under apparent gravity: the stick asks the feet for a walking velocity
		var r := suit.global_transform.basis.orthonormalized()
		var n := suit.support_normal
		var fwd := (r.z - n * r.z.dot(n)).normalized()
		var right := n.cross(fwd).normalized()
		var vw := walk_speed
		if suit.mag_a > 0.0:
			vw = float(pkg["mag_boots"]["gait"]["speed_m_s"])      # the magnetic gait: one boot always down (eva_mag_walk's speed)
		suit.walk_cmd = (fwd * t_in.z - right * t_in.x) * vw * (0.4 if k < 1.0 else 1.0)
		suit.turn_rate = r_in.y * 0.8
		suit_ctl.idle()
		if t_in.y > 0.5:
			suit_ctl.step_player(Vector3(0, t_in.y, 0), Vector3.ZERO)      # an upward thruster burst: far below weight at 1.1-1.5 g
	else:
		suit.walk_cmd = Vector3.ZERO
		suit.turn_rate = 0.0
		suit_ctl.step_player(t_in, r_in)

func _suit_auto() -> void:
	pass

## The astronaut while the player flies the drone: assisted holds continue (they fire thrusters), manual means nothing fires.
func _suit_auto_only() -> void:
	suit.walk_cmd = Vector3.ZERO
	suit.turn_rate = 0.0
	if suit_ctl.mode == WfEvaControl.Mode.ASSIST:
		suit_ctl.brake = false
		suit_ctl.step_player(Vector3.ZERO, Vector3.ZERO)
	else:
		suit_ctl.idle()

func _drone_auto(dt: float) -> void:
	if dops.mode == WfDroneOps.Mode.MANUAL:
		if drone_ctl.mode == WfEvaControl.Mode.ASSIST:
			drone_ctl.brake = false
			drone_ctl.step_player(Vector3.ZERO, Vector3.ZERO)
		else:
			drone_ctl.idle()
	dops.step(dt)

var _page_t := 0.0

func _process(dt: float) -> void:
	if pkg.is_empty():
		return
	_camera()
	_animate_suit()
	hud.refresh()
	_page_t += dt
	if _page_t >= 1.0:                   # the page's state record (browser check): who is controlled, docked, held, moving
		_page_t = 0.0
		WfWebPage.publish("wayfarerEva", {"active": active, "docked": docked, "held": suit.held, "hold": hold_id,
			"v_suit": snappedf(suit.linear_velocity.length(), 0.001), "v_drone": snappedf(drone.linear_velocity.length(), 0.001),
			"scenario": scenario.running, "training": training, "t": snappedf(t_sim, 0.1), "start": start_kind, "model": suit_model_ok,
			"clip": suit_rig.current if suit_model_ok else "", "boots": suit.boots.record() if suit.boots != null else {},
			"tether": suit.tether_on, "standing": suit.standing})

# -------------------------------------------------------------------------------------------------------------------------- camera
const CAMS := {"suit": ["THIRD PERSON", "HELMET"], "drone": ["CHASE", "SENSOR", "STABILIZED INSPECTION"]}

func _camera() -> void:
	var lk := WfInput.take_look()
	cam_yaw -= lk.x
	cam_pitch = clampf(cam_pitch - lk.y, -1.4, 1.4)
	var mode: String = CAMS[active][cam_mode[active]]
	if active == "suit":
		var f := suit_frame()
		var b := f.basis.orthonormalized()
		if mode == "HELMET":
			cam.global_transform = Transform3D(b.rotated(b.y, PI) * Basis(Vector3.UP, cam_yaw * 0.5) * Basis(Vector3.RIGHT, cam_pitch * 0.5), f * Vector3(0, 1.64, 0.12))
		else:
			_orbit(f * Vector3(0, 1.1, 0), b)
	else:
		var f := drone_frame() if not docked else dock_world()
		var b := f.basis.orthonormalized()
		match mode:
			"SENSOR":
				cam.global_transform = Transform3D(b, f * Vector3(0, 0.06, -0.3))
			"STABILIZED INSPECTION":
				var p := f.origin
				cam.global_transform = Transform3D(Basis.IDENTITY, p + Vector3(-1.2, 0.8, 1.6)).looking_at(p, Vector3.UP)
			_:
				_orbit(f.origin, b, 2.0)

## Third person: an orbit about the body in its own frame (horizon independent: up is the body's up).
func _orbit(target: Vector3, b: Basis, dist := -1.0) -> void:
	var d := cam_dist if dist < 0.0 else dist
	var q := b * Basis(Vector3.UP, cam_yaw + PI) * Basis(Vector3.RIGHT, cam_pitch)
	var p := target + q * Vector3(0, 0, d)
	cam.global_transform = Transform3D(Basis.IDENTITY, p).looking_at(target, b.y)

# --------------------------------------------------------------------------------------------------------------------------- input
func _unhandled_input(e: InputEvent) -> void:
	if pkg.is_empty():
		return
	if e is InputEventMouseMotion and Input.is_mouse_button_pressed(MOUSE_BUTTON_RIGHT):
		cam_yaw -= e.relative.x * 0.005
		cam_pitch = clampf(cam_pitch - e.relative.y * 0.005, -1.4, 1.4)
	if e is InputEventMouseButton and e.pressed:
		if e.button_index == MOUSE_BUTTON_WHEEL_UP:
			cam_dist = maxf(1.5, cam_dist * 0.9)
		elif e.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			cam_dist = minf(40.0, cam_dist * 1.1)
	if not WfInput.pressed(e):
		return
	for id in ["evaops.astronaut", "evaops.drone", "evaops.camera", "evaops.assist", "evaops.att_hold", "evaops.pos_hold", "evaops.grab",
			"evaops.tether", "evaops.push", "evaops.boots", "evaops.dock", "evaops.autopilot", "evaops.arms", "evaops.gripper", "evaops.interact", "evaops.help",
			"evaops.frame", "evaops.training", "evaops.scenario", "evaops.reset", "evaops.checkpoint", "evaops.fault", "evaops.exit"]:
		if e.is_action_pressed(id):
			do_action(id)
			get_viewport().set_input_as_handled()
			return

## Every player action, by registry id (the headless check uses the same entry point).
func do_action(id: String) -> void:
	match id:
		"evaops.astronaut":
			active = "suit"
			say("Control: astronaut. The drone keeps its mode (%s)." % dops.name())
		"evaops.drone":
			active = "drone"
			say("Control: drone%s. The astronaut keeps drifting under physics%s." % [" (docked: flies the pair)" if docked else "",
				" with assisted holds" if suit_ctl.mode == WfEvaControl.Mode.ASSIST else ", nothing firing"])
			if not docked and dops.mode != WfDroneOps.Mode.MANUAL:
				dops.set_mode(WfDroneOps.Mode.MANUAL)
		"evaops.camera":
			cam_mode[active] = (cam_mode[active] + 1) % CAMS[active].size()
			say("Camera: " + CAMS[active][cam_mode[active]])
		"evaops.assist":
			var c := _ctl()
			c.mode = WfEvaControl.Mode.MANUAL if c.mode == WfEvaControl.Mode.ASSIST else WfEvaControl.Mode.ASSIST
			say(("Manual: the stick drives the valves; nothing stops you but your own counter-thrust." if c.mode == WfEvaControl.Mode.MANUAL
				else "Assisted: rate damping, attitude hold, brake (B) and position hold (P). Every correction uses gas."))
		"evaops.att_hold":
			var c := _ctl()
			c.attitude_hold = not c.attitude_hold
			say("Attitude hold " + ("on" if c.attitude_hold else "off"))
		"evaops.pos_hold":
			var c := _ctl()
			c.hold_pos = not c.hold_pos
			c.hold_point = c.body.global_position
			c.ref_vel = Vector3.ZERO
			say("Position hold " + ("on (station keeping uses gas)" if c.hold_pos else "off"))
		"evaops.grab":
			grab()
		"evaops.tether":
			tether()
		"evaops.push":
			push_off()
		"evaops.boots":
			toggle_boots()
		"evaops.dock":
			if docked:
				undock()
				say("Drone released: it backed off the channel at %.2f m/s. Suit reserve armed." % float(pkg["drone"]["near_suit"]["retreat_speed_m_s"]))
			elif frame_mode != "DRIFT":
				say("No docking approach under thrust: the drone cannot hold position against the ship's acceleration.", false)
			else:
				dops.set_mode(WfDroneOps.Mode.RETURN_ASTRONAUT)
				say("Drone: docking approach to the gate %.2f m behind the suit, then straight in." % float(pkg["assist"]["approach_gate_m"]))
		"evaops.autopilot":
			if docked:
				say("The drone is docked.", false)
				return
			var order := [WfDroneOps.Mode.MANUAL, WfDroneOps.Mode.HOLD, WfDroneOps.Mode.FOLLOW, WfDroneOps.Mode.RETURN_ASTRONAUT, WfDroneOps.Mode.RETURN_SHIP]
			var i := order.find(dops.mode)
			dops.set_mode(order[(i + 1) % order.size()])
			say("Drone mode: " + dops.name())
		"evaops.arms":
			dops.toggle_arms()
		"evaops.gripper":
			dops.toggle_gripper()
		"evaops.interact":
			interact()
		"evaops.help":
			dops.request_rescue()
		"evaops.frame":
			cycle_frame()
		"evaops.training":
			training = not training
			if not training and frame_mode != "DRIFT":
				set_frame("DRIFT")
			say("OPERATIONAL EVA RULES: drift only, ram face and keep-outs enforced, no resets. FLIGHT_EVA stays HOLD (45 O-07)." if not training
				else "TRAINING SIMULATION: drift and burn presets, safe restarts (F5, F6). The physics is the same.")
		"evaops.scenario":
			if scenario.running:
				start_free(true)
			else:
				scenario.start()
		"evaops.reset":
			training_reset()
		"evaops.checkpoint":
			to_checkpoint()
		"evaops.fault":
			if not training:
				say("Fault injection is a training tool.", false)
				return
			var a: WfAllocator = drone.alloc if not docked else a_docked
			var n := faults * 5 % a.count()
			for al in [a_free, a_near]:
				al.failed[n % al.count()] = true
			faults += 1
			say("TRAINING FAULT: drone valve %s failed closed (%d failed). Its share of every manoeuvre is lost." % [a.names[n % a.count()], faults], false)
		"evaops.exit":
			WfWebPage.scene("interior")            # the page follows (its Exit link, title and hash), so a reload keeps the walk
			get_tree().change_scene_to_file("res://scenes/excursion.tscn")

func _ctl() -> WfEvaControl:
	return suit_ctl if active == "suit" or docked else drone_ctl

func key(id: String) -> String:
	return "[" + WfInput.label(id) + "]"

var _digits := RegEx.create_from_string("[0-9.]+")

func say(t: String, ok := true) -> void:
	# a repeating status line (same words, new numbers) updates the last message instead of flooding the log
	if not messages.is_empty():
		var last: Dictionary = messages[-1]
		if _digits.sub(last["t"], "#", true) == _digits.sub(t, "#", true):
			var fresh: bool = t_sim - float(last["at"]) > 3.0
			last["t"] = t
			if not fresh:
				return
			last["at"] = t_sim
			if check != null:
				print("WF_EVA_OPS_SAY ", t)
			return
	messages.append({"t": t, "ok": ok, "at": t_sim})
	if messages.size() > 6:
		messages.pop_front()
	if check != null:
		print("WF_EVA_OPS_SAY ", t)

func scenario_event(ev: String) -> void:
	if scenario != null:
		scenario.event(ev)

# ----------------------------------------------------------------------------------------------------------------- astronaut actions
func grab() -> bool:
	if suit.held:
		suit.held = false
		hold_id = ""
		say("Released the hold. You keep the ship's velocity: zero until you push or fire.")
		return true
	var reach := float(pkg["rules"]["reach_m"])
	var h := world.hold_near(suit.global_position, reach + 0.6)
	if h.is_empty():
		say("No hold within reach (%.1f m)." % reach, false)
		return false
	var d := suit.global_position.distance_to(h["p"])
	if d > reach:
		say("%s is %.2f m away: closer." % [h["label"], d], false)
		return false
	var v := suit.linear_velocity.length()
	if v > float(pkg["rules"]["grab_speed_max_m_s"]):
		say("Too fast to hold on (%.2f m/s): brake first." % v, false)
		return false
	suit.held = true
	suit.hold_anchor = h["p"]
	hold_id = h["id"]
	_checkpoint()
	say("Holding %s." % h["label"])
	scenario_event("held:" + h["kind"] + ":" + h["id"])
	return true

## LOCO-002: V. The pads on (they attach where the soles meet the walkway) or off (both boots release at once; the suit floats with the
## velocity it has, and the EVA physics, thrusters and tether take over).
func toggle_boots() -> bool:
	if suit.boots == null:
		say("This suit has no magnetic boots in the package.", false)
		return false
	if suit.boots.armed:
		suit.boots.arm(false)
		say("Boot magnets OFF: both boots released. You float with the ship's velocity; thrusters and the tether from here.")
	else:
		suit.boots.arm(true)
		say("Boot magnets ON: they attach when your soles meet the walkway plate (within %.0f mm, closing below %.2f m/s)." %
			[float(pkg["mag_boots"]["capture_gap_m"]) * 1000.0, float(pkg["mag_boots"]["capture_speed_m_s"])])
	scenario_event("boots:" + ("on" if suit.boots.armed else "off"))
	return true

func push_off() -> bool:
	if suit.boots != null and suit.boots.count() > 0 and not suit.held:
		# release both pads, then the legs push the body off the plate along its normal (the same push the hands give at a hold)
		var n := suit.boots.normal
		suit.boots.arm(false)
		suit.add_impulse(n * float(pkg["rules"]["push_dv_m_s"]))
		say("Boots released and pushed off the walkway at %.2f m/s. Nothing slows you now except thrust, a hold or the tether." % float(pkg["rules"]["push_dv_m_s"]))
		scenario_event("boots:push")
		return true
	if not suit.held:
		say("Push off needs a grip on a hold (%s)." % key("evaops.grab"), false)
		return false
	suit.held = false
	hold_id = ""
	var dirn := -cam.global_transform.basis.z if active == "suit" else suit.global_transform.basis.z
	suit.add_impulse(dirn.normalized() * float(pkg["rules"]["push_dv_m_s"]))
	say("Pushed off at %.2f m/s. Nothing slows you now except thrust or a hold." % float(pkg["rules"]["push_dv_m_s"]))
	return true

func tether() -> bool:
	if suit.tether_on:
		suit.tether_on = false
		say("Tether unclipped.")
		return true
	var h := world.hold_near(suit.global_position, float(pkg["rules"]["reach_m"]))
	if h.is_empty() or h["kind"] == "station":
		say("Clip the tether to a rail anchor or Brow fixture in reach.", false)
		return false
	suit.tether_on = true
	suit.tether_anchor = h["p"]
	say("Tether clipped to %s (%.0f m line)." % [h["label"], suit.tether_len])
	scenario_event("tether")
	return true

func interact() -> void:
	if active == "drone" and not docked:
		if dops.holding != null:
			if dops.try_seat():
				scenario_event("seated")
			return
		var tgt := _inspect_target()
		if not tgt.is_empty():
			scenario_event("inspect:" + tgt["id"])
			say("Inspection recorded: %s." % tgt["label"])
		else:
			say("Nothing to inspect here: point the sensor nose at a Brow fixture within 2.5 m.", false)
		return
	if cartridge_seated != null and stow_cartridge():
		return
	if suit.held and hold_id.begins_with("BROW_FIX"):
		say("Fixture %s checked: post and target flange intact (visual check; no load test)." % hold_id)
		scenario_event("maintain:" + hold_id)
		return
	scenario_event("ack")

func _inspect_target() -> Dictionary:
	var f := drone_frame()
	var nose := -f.basis.orthonormalized().z
	for h in world.holds:
		if h["kind"] != "brow_fixture":
			continue
		var d: Vector3 = h["p"] - f.origin
		if d.length() < 2.5 and nose.dot(d.normalized()) > cos(deg_to_rad(20.0)):
			return h
	return {}

# ---------------------------------------------------------------------------------------------------------------------- inventory
## The astronaut's delta-v from everything the suit can burn now (docked: the pair on drone gas).
func suit_dv_available() -> float:
	return suit.dv_left()

func drone_fault_valves() -> int:
	return a_free.failed.size()

func suit_status() -> String:
	var rules: Dictionary = pkg["rules"]
	var primary: WfN2Tank = drone_gas if docked else (cartridge_seated.tank if cartridge_seated != null else null)
	if primary != null and primary.usable() > 0.0:
		return "LOW PROPELLANT" if primary.fraction() < float(rules["low_fraction"]) else "NOMINAL"
	if reserve.usable() <= 0.0:
		return "MANEUVERING UNAVAILABLE"
	if reserve.fraction() <= float(rules["emergency_floor_fraction"]):
		return "EMERGENCY ONLY"
	return "MAIN SUPPLY DEPLETED" if primary != null else "RESERVE ONLY (drone away)"

func total_gas() -> float:
	var m := reserve.n2_kg + drone_gas.n2_kg
	for c in cartridges:
		m += (c as WfCartridge).tank.n2_kg
	return m

# ---------------------------------------------------------------------------------------------------------------------- frames
func cycle_frame() -> void:
	var order := ["DRIFT", "BURN_HP", "BURNBROW_11"]
	set_frame(order[(order.find(frame_mode) + 1) % order.size()])

func set_frame(m: String) -> void:
	if m != "DRIFT" and not training:
		say("Operational rules: no EVA under thrust. Burn exists only as a training simulation (F3).", false)
		return
	frame_mode = m
	var md: Dictionary = pkg["modes"][m]
	field.set_state("SHIP", "EVA")
	field.a_ship = WfFrames.v3(float(md["accel_g"]) * float(pkg["standard_gravity_m_s2"]), 0.0, 0.0)
	if m == "DRIFT":
		say("DRIFT: drive off. Microgravity: the Brow is not a floor, only holds and thrust move you.")
	else:
		# training restart for the burn exercise: standing on the forward (ram) face, drone docked
		if not docked:
			_redock_training()
		var r := 18.0
		var x := world.face_x(r) + 0.02
		var up := Vector3.RIGHT
		var fwd := Vector3(0, 1, 0)
		var frame := Transform3D(Basis(up.cross(fwd), up, fwd), Vector3(x, r, 0.0))
		place_suit(frame)
		suit.held = false
		say("TRAINING SIMULATION %s: %.2f g toward the engines. Standing on the Brow's ram face, repositioned for the exercise. Cold gas "
			% [md["label"], float(md["accel_g"])] + "cannot lift you: %.0f N of weight against about 18 N of thrust." % (suit.total_mass() * float(md["accel_g"]) * 9.81), false)
	scenario_event("frame:" + m)

func _redock_training() -> void:
	drone.linear_velocity = suit.linear_velocity
	capture()

# ---------------------------------------------------------------------------------------------------------------- resets / checkpoint
func _checkpoint() -> void:
	checkpoint = {"suit": suit_frame(), "vs": Vector3.ZERO, "docked": docked, "drone": drone_frame(), "frame": frame_mode}

func to_checkpoint() -> void:
	if not training:
		say("Operational rules: no restarts.", false)
		return
	if checkpoint.is_empty():
		_checkpoint()
	if checkpoint["frame"] != frame_mode:
		set_frame(checkpoint["frame"])
	if checkpoint["docked"] and not docked:
		_redock_training()
	place_suit(checkpoint["suit"])
	suit.held = true
	suit.hold_anchor = suit.global_position
	if not docked:
		_set_body(drone, checkpoint["drone"] * Transform3D(Basis.IDENTITY, drone_com), Vector3.ZERO, Vector3.ZERO)
	say("TRAINING: back at the last checkpoint (positions only: gas is NOT refilled).", false)

## Training reset: every vessel full, the rack full, both at the hatch, drone docked. Counted on each tank's ledger.
func training_reset() -> void:
	if not training:
		say("Operational rules: no training reset. Resupply only through the drone or the station.", false)
		return
	reserve.training_reset()
	drone_gas.training_reset()
	world.station["cartridges"] = int(pkg["station"]["cartridges"])
	start_free(true)
	if start_kind == "WALKWAY":
		start_walkway(false)
	say("TRAINING RESET: every N2 vessel refilled and the rack restocked (not an in-world resupply; counted).", false)

func start_free(announce: bool) -> void:
	for c in cartridges:
		var cc: WfCartridge = c
		if cc.body != null:
			cc.body.queue_free()
		elif cc.node != null and is_instance_valid(cc.node):
			cc.node.queue_free()
	if cartridge_seated != null:
		_unseat(cartridge_seated)
	cartridges.clear()
	dops.holding = null
	dops.arms_deployed = false
	dops.arms_t = 0.0
	dops.set_mode(WfDroneOps.Mode.MANUAL)
	for al in [a_free, a_near, a_docked, a_suit]:
		al.failed.clear()
	faults = 0
	if frame_mode != "DRIFT":
		frame_mode = "DRIFT"
		field.a_ship = WfFrames.v3(0, 0, 0)
	if not docked:
		drone.linear_velocity = suit.linear_velocity
		capture()
	var h: Dictionary = pkg["ship"]["route"]["holds"]["airlock"]
	var up := world.rail_up
	var fwd := Vector3.RIGHT
	var frame := Transform3D(Basis(up.cross(fwd).normalized(), up, fwd), WfEvaPkg.v(h["p"]) - up * 0.35)
	place_suit(frame)
	suit.held = true
	suit.hold_anchor = WfEvaPkg.v(h["p"])
	hold_id = "HOLD_AIRLOCK"
	suit.tether_on = false
	if suit.boots != null:
		suit.boots.arm(false)
	suit_ctl.hold_pos = false
	suit_ctl.mode = WfEvaControl.Mode.ASSIST
	active = "suit"
	_checkpoint()
	if scenario != null:
		scenario.running = false
	if announce:
		say("FREE EXPLORATION: everything is open; the gas is still finite.")

## LOCO-002: where Explore Exterior begins. The EVA check, `-- --hatch` and the page's #exterior-hatch (or #eva) start at the airlock hold.
static func requested_start() -> String:
	var args := OS.get_cmdline_user_args()
	if "--check-eva-ops" in args or "--hatch" in args or "--first-flight" in args or WfWebPage.start_variant() in ["hatch", "first_flight"]:
		return "HATCH"
	return "WALKWAY"

## Explore Exterior start (LOCO-002): Wayfarer in DRIFT (no field at all), the astronaut standing on the magnetic walkway beside the rail with
## both boots attached, facing the Brow, the drone docked, the tether clipped to the nearest rail anchor. Everything after it is the EVA
## physics: release (V) or push off (Space) and the thrusters, holds, tether, drone and rescue work as from the hatch.
func start_walkway(announce: bool) -> void:
	var m: Dictionary = pkg["mag_boots"]
	var phi := float(m["start_phi_rad"])
	var up := Vector3(0, cos(phi), sin(phi))
	var fwd := Vector3.RIGHT
	var frame := Transform3D(Basis(up.cross(fwd).normalized(), up, fwd), world.walkway_point(m, float(m["start_x_m"]), phi, 0.002))
	place_suit(frame)
	suit.held = false
	hold_id = ""
	suit.boots.arm(true)
	for a in pkg["ship"]["route"]["anchors"]:
		if a["id"] == m["tether_anchor"]:
			suit.tether_on = true
			suit.tether_anchor = WfEvaPkg.v(a["p"])
	cam_yaw = 0.6
	cam_pitch = -0.3
	_checkpoint()
	say("EXPLORE EXTERIOR · magnetic walkway (PROTOTYPE, training): Wayfarer drifts, nothing pulls you down. The boot magnets hold you to the plate. "
		+ "%s/%s walk, %s/%s turn, %s boots on/off, %s push off, %s grab a hold, %s tether, %s reset." % [key("evaops.fwd"), key("evaops.back"),
		key("evaops.yaw_left"), key("evaops.yaw_right"), key("evaops.boots"), key("evaops.push"), key("evaops.grab"), key("evaops.tether"), key("evaops.reset")])
	if announce:
		scenario_event("start:walkway")

func ray(a: Vector3, b: Vector3) -> Dictionary:
	var q := PhysicsRayQueryParameters3D.create(a, b, WfEvaWorld.LAYER_WORLD)
	return get_world_3d().direct_space_state.intersect_ray(q)

## A training stage only: vent gas from the suit reserve (the scenario's "low nitrogen" setup). Counted as used, never created.
func training_vent_reserve(to_kg: float) -> void:
	var take := maxf(0.0, reserve.usable() - to_kg)
	vented_kg += reserve.draw(take)
