extends Node3D
## Guided EVA, TRAINING SIMULATION (TODO EVA-001, docs/EVA.md; S&E 44 RUN-013..015, Tale 26_GUIDED_EVA TOUR-05..11).
## Reads generated/wf_eva.json (eva_route.py: rail, anchors, holds, hazard gates, stations, telemetry contract) and the suited pair
## (generated/characters/eva_*.glb + eva_characters.json). Godot computes no spacecraft facts: positions, gates and texts come from the
## generated data; the timings, the camera and the movement pace are display choices (RUN-016 "gameplay tuning is separate").
## Rules it enforces (fail closed): the route is SIMULATION_ONLY unless every gate PASSes, and it never does today; one airlock door at a
## time; two tethers, never zero live anchors, release only after the other is clipped and tested; the body never moves beyond the reach
## of a clipped anchor; abort reverses the protocol to the airlock. No OPEN telemetry value is shown as a number.
##   godot --path godot res://scenes/eva.tscn [-- --check-eva]   (the check runs the protocol and prints WF_GODOT_EVA JSON)

const PHASES := ["PREP", "LOCK_CHECK", "DEPRESS", "EXTERIOR", "REPRESS", "DEBRIEF"]
const REVIEW_PACE := 3.0         # Shift multiplies the display translation pace (review only)
const STATION_RADIUS := 1.2      # within this of a hold (along the rail) its station is active
const CHAMBER_S := 4.0           # display duration of a depress / repress step (the real timeline is OPEN; no clock is shown)

var eva: Dictionary
var suits: Dictionary
var ship: Node3D
var camera := Camera3D.new()
var pivots := {}
var phase := "PREP"
var u := 0.0                     # ship X of the newcomer along the rail
var anchors: Array = []          # [{id, run, x, p}]
var tethers := {"A": null, "B": null}   # {anchor: index, tested: bool}
var inner_open := true
var outer_open := false
var chamber := "PRESSURIZED"     # PRESSURIZED -> DEPRESSING -> VACUUM -> REPRESSING
var chamber_t := 0.0
var abort := false
var plan: Array = []
var plan_t := 0.0
var feed := ""
var show_stage := 0
var orbit := Vector2(0.6, 0.35)
var zoom := 4.5
var first_person := false
var dragging := false
var player: Node3D
var guide: Node3D
var players := {}
var lines := {}
var message := ""
var theta := 0.0
var station_text := Label.new()
var hud := Label.new()
var banner := Label.new()
var status := Label.new()
var hint := Label.new()
var keepout: MeshInstance3D
var sim_chamber: MeshInstance3D
var hidden_airlock: Array = []
var checking := false
var rig_dyn: Dictionary
var drift: WfEvaDrift             # 3-D tethered drift beside the rail (PHYS-001 phase 5); null while on the rail
var review: WfReviewGuide = null  # U04: the guided EVA drift session (review menu or -- --review=eva)
var ui_panels: Array = []         # the scene's own text panels, hidden while the guide runs (their text is the guide's muted detail line)

func vec(a) -> Vector3:
	return Vector3(a[0], a[1], a[2])

func ship_point(x: float, r: float) -> Vector3:
	# vehicle (x, r cos th, r sin th) in Godot axes (x, z, -y)
	return Vector3(x, r * sin(theta), -r * cos(theta))

func up_dir() -> Vector3:
	return Vector3(0.0, sin(theta), -cos(theta))

var load_ms := 0

func _ready() -> void:
	WfInput.context = "eva"                      # ACI-10: the guide and the Codex read this scene's actions
	var t_start := Time.get_ticks_msec()
	checking = "--check-eva" in OS.get_cmdline_user_args()
	var canvas := CanvasLayer.new()
	add_child(canvas)
	build_ui(canvas)
	if not FileAccess.file_exists("res://generated/wf_eva.json") or not ResourceLoader.exists("res://generated/wayfarer.glb"):
		banner.text = "Generate the runtime package first:\npython3 tools/workflow.py runtime-export"
		if checking:
			finish({"result": "FAIL", "reason": "no wf_eva.json or wayfarer.glb"})
		return
	eva = JSON.parse_string(FileAccess.get_file_as_string("res://generated/wf_eva.json"))
	theta = deg_to_rad(float(eva.rail_azimuth_deg))
	anchors = eva.anchors
	anchors.sort_custom(func(a, b): return float(a.x) < float(b.x))
	var rp := "res://generated/wf_sim_rig.json"
	rig_dyn = JSON.parse_string(FileAccess.get_file_as_string(rp))["dynamics"] if FileAccess.file_exists(rp) else {}
	load_ship()
	build_training_route()
	load_suits()
	load_ms = Time.get_ticks_msec() - t_start
	u = float(eva.holds.airlock.x)
	tethers.A = {"anchor": nearest_anchor(u), "tested": true}   # clipped to the hatch's anchor ring when the outer hatch opens (display)
	add_child(camera)
	camera.current = true
	camera.near = 0.05
	camera.far = 4000.0
	var sun := DirectionalLight3D.new()
	sun.rotation = Vector3(deg_to_rad(-40.0), deg_to_rad(-35.0), 0.0)
	sun.light_energy = 1.6
	add_child(sun)
	var env := WorldEnvironment.new()
	env.environment = Environment.new()
	env.environment.background_mode = Environment.BG_COLOR
	env.environment.background_color = Color(0.006, 0.008, 0.012)
	env.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.environment.ambient_light_color = Color(0.30, 0.34, 0.40)
	env.environment.ambient_light_energy = 0.45
	add_child(env)
	set_phase("PREP")
	var capture := ""
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--shot="):          # review stills: start in a given state (display only)
			shot(a.substr(7))
		elif a.begins_with("--capture="):     # with a window: save a still of that state and quit
			capture = a.substr(10)
	if capture != "":
		for i in (150 if "--shot=drift_push" in OS.get_cmdline_user_args() else 30):
			await get_tree().process_frame
		get_viewport().get_texture().get_image().save_png(capture)
		get_tree().quit(0)
	if checking:
		await get_tree().process_frame
		run_check()
	elif "--perf" in OS.get_cmdline_user_args():
		run_perf()
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--review="):
			WfReviewGuide.pending = a.trim_prefix("--review=")
	if WfReviewGuide.pending == "eva":
		WfReviewGuide.pending = ""
		review = WfReviewGuide.new(WfEvaSession.new(self))
		add_child(review)
		for n in ui_panels:
			n.visible = false
		if "--check-review" in OS.get_cmdline_user_args():
			await check_review()

# ---------------------------------------------------------------------------------------------------------------- scene
func load_ship() -> void:
	ship = load("res://generated/wayfarer.glb").instantiate()
	add_child(ship)
	var manifest = JSON.parse_string(FileAccess.get_file_as_string("res://generated/manifest.json"))
	var frame_of := {}
	var hide := {}
	var ext: Dictionary = manifest.get("look", {}).get("exterior", {})
	for record in manifest.nodes:
		frame_of[record.node] = record.get("frame", "")
		var src := str(record.source_name)
		if src.begins_with("Field_Zone"):           # the field is off in EVA (14!15, 11!5)
			hide[record.node] = true
		# display layers the exterior look hides (glow steps, health markers, guides, plasma): the drive is OFF and the blades are shown
		# as geometry only; their temperature in EVA is OPEN (EVA-035)
		if not ext.is_empty() and (str(record.kind) in ext.hidden_kinds or Array(ext.hidden_prefixes).any(func(p): return src.begins_with(p))):
			hide[record.node] = true
		if src.begins_with("Plasma") or src.begins_with("Drive_Plasma"):
			hide[record.node] = true
		if src == "Airlock_EVA" or src == "Crew_Connector_Airlock_EVA":
			hidden_airlock.append(record.node)
	for key in manifest.timeline.mechanisms:
		var b: Dictionary = manifest.timeline.mechanisms[key]
		var pivot := Node3D.new()
		pivot.position = vec(b.pivot_runtime_m)
		ship.add_child(pivot)
		pivots[key] = {"node": pivot, "binding": b, "angle": 0.0}
	var airlock_nodes := []
	for item in ship.find_children("*", "MeshInstance3D", true, false):
		var n := str(item.name)
		if hide.has(n):
			item.visible = false
		if n in hidden_airlock:
			airlock_nodes.append(item)
		for key in pivots:
			if frame_of.get(n, "") == key:
				item.reparent(pivots[key].node, true)
	hidden_airlock = airlock_nodes

func material(color: Color, alpha: float = 1.0, emit: float = 0.0) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = Color(color, alpha)
	if alpha < 1.0:
		m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		m.cull_mode = BaseMaterial3D.CULL_DISABLED
	if emit > 0.0:
		m.emission_enabled = true
		m.emission = color
		m.emission_energy_multiplier = emit
	return m

func cylinder(a: Vector3, b: Vector3, r: float, mat: Material) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var c := CylinderMesh.new()
	c.top_radius = r
	c.bottom_radius = r
	c.height = a.distance_to(b)
	c.radial_segments = 12
	mi.mesh = c
	mi.material_override = mat
	add_child(mi)
	var y := (b - a).normalized()
	var x := y.cross(Vector3.UP if absf(y.dot(Vector3.UP)) < 0.9 else Vector3.RIGHT).normalized()
	mi.global_transform = Transform3D(Basis(x, y, x.cross(y)), (a + b) * 0.5)
	return mi

func build_training_route() -> void:
	# PROTOTYPE rail, anchors and hold fixtures (RUN-011): drawn by the runtime, never part of the vehicle
	var sim := material(Color(0.95, 0.80, 0.20), 1.0, 0.25)
	var orange := material(Color(0.92, 0.36, 0.06), 1.0, 0.4)
	var rr := float(eva.rail_radius_m)
	for key in eva.runs:
		var run: Array = eva.runs[key]
		cylinder(ship_point(run[0], rr), ship_point(run[1], rr), 0.016, sim)
	for a in anchors:
		var t := MeshInstance3D.new()
		var tm := TorusMesh.new()
		tm.inner_radius = 0.025
		tm.outer_radius = 0.04
		t.mesh = tm
		t.material_override = orange
		add_child(t)
		t.global_position = vec(a.p)
	for key in ["rail_mid", "aft_hold", "forward_hold"]:
		var x := float(eva.holds[key].x)
		var base := ship_point(x + 0.32 * (1.0 if key != "forward_hold" else -1.0), rr - 0.15)
		cylinder(base, base + up_dir() * 1.10, 0.02, sim)
	# ring-B rotating sweep as a keep-out volume (display of SIM-02; the margin is OPEN)
	var rs: Dictionary = eva.ring_sweep
	keepout = cylinder(Vector3(rs.x0, 0, 0), Vector3(rs.x1, 0, 0), float(rs.r_outer), material(Color(1.0, 0.15, 0.1), 0.10))
	keepout.visible = false
	# SP-11: the recommended STUDY chamber of eva_access.py when present (EVA-043/044: no ship geometry), else the old simulated chamber
	var ch: Dictionary = eva.chamber
	var ax := float(ch.axis_x)
	if eva.has("access") and eva.access.has("eva3"):
		# EVA-003: the 1.20 m lead study (45 G-13), the parallel-plug inner hatch and the extension latch stations (eva_sp11.py; STUDY)
		var e3: Dictionary = eva.access.eva3
		var sc: Dictionary = e3.chamber
		sim_chamber = cylinder(ship_point(ax, float(sc.a0)), ship_point(ax, float(sc.a1)), float(sc.radius), material(Color(0.55, 0.75, 1.0), 0.16))
		build_eva3(e3)
		build_rooms()
	elif eva.has("access"):
		var sc: Dictionary = eva.access.chamber
		sim_chamber = cylinder(ship_point(ax, float(sc.a0)), ship_point(ax, float(sc.a1)), float(sc.radius), material(Color(0.55, 0.75, 1.0), 0.16))
		build_rooms()
	else:
		sim_chamber = cylinder(ship_point(ax, float(ch.r_outer) - 2.4), ship_point(ax, float(ch.r_outer) - 0.05), float(ch.fitting_radius_m) - 0.05,
			material(Color(0.55, 0.75, 1.0), 0.18))

var room_nodes: Array = []
var plug: MeshInstance3D
var plug_park := Transform3D()
var plug_seat := Transform3D()

func chamber_point(sc: Dictionary, a: float, p: float, q: float) -> Vector3:
	# the chamber frame (a outward along the airlock, p along X, q = X x a) in Godot axes, as eva_access / eva_sp11 place things
	var th := deg_to_rad(float(sc.theta_deg))
	return Vector3(float(sc.axis_x) + p, a * sin(th) + q * cos(th), -(a * cos(th) - q * sin(th)))

func build_eva3(e3: Dictionary) -> void:
	var sc: Dictionary = e3.chamber
	var c: Array = e3.inner_hatch.park_corners_chamber
	var P := func(v) -> Vector3: return chamber_point(sc, float(v[0]), float(v[1]), float(v[2]))
	var o: Vector3 = P.call(c[0])
	var ba := Basis(P.call(c[2]) - o, P.call(c[4]) - o, P.call(c[1]) - o)
	var centre := Vector3.ZERO
	for v in c:
		centre += P.call(v) / 8.0
	plug = MeshInstance3D.new()
	plug.mesh = BoxMesh.new()
	plug.material_override = material(Color(0.25, 0.75, 0.40), 0.55)
	add_child(plug)
	plug_park = Transform3D(ba, centre)
	plug_seat = Transform3D(ba, P.call(e3.inner_hatch.seat_centre_chamber))
	plug.global_transform = plug_park
	room_nodes.append(plug)
	var red := material(Color(0.95, 0.2, 0.2))
	for l in e3.latch:
		var pv: Array = l.pivot_chamber
		var rho := sqrt(float(pv[1]) * float(pv[1]) + float(pv[2]) * float(pv[2]))
		var k := float(sc.radius) / maxf(rho, 1e-6)
		var wall: Vector3 = P.call([pv[0], float(pv[1]) * k, float(pv[2]) * k])
		var top: Vector3 = P.call([l.top_a_m, float(pv[1]) * k, float(pv[2]) * k])
		for seg in [[P.call([float(pv[0]) + float(l.grip_radius_m), pv[1], pv[2]]), P.call(pv)], [P.call(pv), wall], [wall, top]]:
			room_nodes.append(cylinder(seg[0], seg[1], 0.02, red))

func room_point(x: float, az_deg: float, r: float) -> Vector3:
	var a := deg_to_rad(az_deg)
	return Vector3(x, r * sin(a), -r * cos(a))

func build_rooms() -> void:
	# SP-12 / SP-13 STUDY rooms (12A PROPOSED / PROGRAM) as a translucent floor ribbon and their fixtures, shown while inside
	for key in eva.access.rooms:
		var q: Dictionary = eva.access.rooms[key]
		var floor_mat := material(Color(0.45, 0.55, 0.65), 0.22)
		var n := 10
		for k in n:
			var a0: float = lerpf(float(q.az_deg[0]), float(q.az_deg[1]), float(k) / n)
			var a1: float = lerpf(float(q.az_deg[0]), float(q.az_deg[1]), float(k + 1) / n)
			var mi := MeshInstance3D.new()
			var b := BoxMesh.new()
			var r0 := float(q.r_m[0])
			b.size = Vector3(float(q.x_m[1]) - float(q.x_m[0]), 0.03, r0 * deg_to_rad(a1 - a0))
			mi.mesh = b
			mi.material_override = floor_mat
			add_child(mi)
			var am := (a0 + a1) * 0.5
			var up := room_point(0, am, 1.0)
			var c := room_point((float(q.x_m[0]) + float(q.x_m[1])) * 0.5, am, r0)
			mi.global_transform = Transform3D(Basis(Vector3(1, 0, 0), up, Vector3(1, 0, 0).cross(up)), c)
			room_nodes.append(mi)
		for f in q.fixtures:
			var mi := MeshInstance3D.new()
			var b := BoxMesh.new()
			b.size = Vector3(float(f.size[0]), float(f.size[2]), float(f.size[1]))
			mi.mesh = b
			mi.material_override = material(Color(0.95, 0.85, 0.3) if str(f.id).ends_with("ZONE") else Color(0.35, 0.6, 0.7), 0.35)
			add_child(mi)
			var up := room_point(0, float(f.az), 1.0)
			mi.global_transform = Transform3D(Basis(Vector3(1, 0, 0), up, Vector3(1, 0, 0).cross(up)), room_point(float(f.x), float(f.az), float(f.r0) + float(f.size[2]) * 0.5))
			room_nodes.append(mi)

func load_suits() -> void:
	var meta = JSON.parse_string(FileAccess.get_file_as_string("res://generated/characters/eva_characters.json"))
	if meta == null:
		banner.text += "\nNo suited characters: run python3 tools/workflow.py eva, then runtime-export"
		return
	suits = meta
	for key in meta.variants:
		var rec: Dictionary = meta.variants[key]
		var node: Node3D = (load("res://generated/characters/" + str(rec.glb)) as PackedScene).instantiate()
		add_child(node)
		for n in rec.cutaway:
			var hit := node.find_child(n, true, false)
			if hit:
				hit.visible = false
		var ap: AnimationPlayer = node.find_children("*", "AnimationPlayer", true, false)[0]
		players[key] = {"node": node, "player": ap, "rec": rec, "clip": ""}
		for side in ["A", "B"]:
			var im := MeshInstance3D.new()
			im.mesh = ImmediateMesh.new()
			im.material_override = material(Color(0.92, 0.36, 0.06), 1.0, 0.6)
			add_child(im)
			lines[key + side] = im
	player = players.get("newcomer", {}).get("node")
	guide = players.get("instructor", {}).get("node")

func play(key: String, clip: String) -> void:
	if not players.has(key):
		return
	var p: Dictionary = players[key]
	if p.clip == clip:
		return
	var ap: AnimationPlayer = p.player
	if ap.has_animation(clip):
		var anim := ap.get_animation(clip)
		anim.loop_mode = Animation.LOOP_LINEAR if p.rec.actions.get(clip, {}).get("loop", false) or clip.begins_with("eva_guide") or clip.begins_with("eva_tether") else Animation.LOOP_NONE
		ap.play(clip)
		p.clip = clip

func place(node: Node3D, at: Vector3, along: Vector3, up: Vector3) -> void:
	# Blender place(): local +Y(Blender) = along, +Z(Blender) = up; in Godot model axes the face (+Z) looks against `along`
	var y := up.normalized()
	var z := -along.normalized()
	var x := y.cross(z).normalized()
	node.global_transform = Transform3D(Basis(x, y, x.cross(y)), at)

# ---------------------------------------------------------------------------------------------------------------- protocol
func nearest_anchor(x: float) -> int:
	var best := 0
	for i in anchors.size():
		if absf(float(anchors[i].x) - x) < absf(float(anchors[best].x) - x):
			best = i
	return best

func live() -> Array:
	return ["A", "B"].filter(func(k): return tethers[k] != null)

func clip(which: String, index: int) -> String:
	if tethers[which] != null:
		return "tether %s is already clipped" % which
	if absf(float(anchors[index].x) - u) > float(eva.tether_reach_m):
		return "anchor %s is out of reach" % anchors[index].id
	for k in live():
		if int(tethers[k].anchor) == index:
			return "both tethers on one anchor are not independent"
	tethers[which] = {"anchor": index, "tested": false}
	return ""

func test(which: String) -> String:
	if tethers[which] == null:
		return "tether %s is not clipped" % which
	tethers[which].tested = true
	return ""

func release(which: String) -> String:
	var other := "B" if which == "A" else "A"
	if tethers[which] == null:
		return "tether %s is not clipped" % which
	if tethers[other] == null or not tethers[other].tested:
		return "release refused: tether %s must be clipped and tested first" % other
	tethers[which] = null
	return ""

func limits() -> Vector2:
	var lo := -INF
	var hi := INF
	for k in live():
		var x := float(anchors[int(tethers[k].anchor)].x)
		lo = maxf(lo, x - float(eva.tether_reach_m))
		hi = minf(hi, x + float(eva.tether_reach_m))
	var ends := route_ends()
	return Vector2(maxf(lo, ends.x), minf(hi, ends.y))

func route_ends() -> Vector2:
	return Vector2(float(eva.holds.aft_hold.x), float(eva.holds.forward_hold.x))

func move(dx: float) -> void:
	var lim := limits()
	var want := u + dx
	var to := clampf(want, lim.x, lim.y)
	if absf(to - want) > 1e-4 and dx != 0.0:
		message = "Tether reach: clip the next anchor (%s), test it (%s), then release the old one (%s)" % WfInput.labels(["eva.clip", "eva.tug_test", "eva.release_tether"])
	u = to

func free_tether() -> String:
	return "B" if tethers.A != null and tethers.B == null else ("A" if tethers.A == null else "")

func older_tether() -> String:
	# the tether to release: the one whose anchor is behind the direction of travel; the newest tested one stays
	if live().size() < 2:
		return live()[0] if live().size() == 1 else ""
	var a := float(anchors[int(tethers.A.anchor)].x)
	var b := float(anchors[int(tethers.B.anchor)].x)
	return "A" if absf(a - u) > absf(b - u) else "B"

func clip_next() -> String:
	var f := free_tether()
	if f == "":
		return "both tethers are clipped: release one first"
	var best := -1
	for i in anchors.size():
		if live().any(func(k): return int(tethers[k].anchor) == i):
			continue
		if absf(float(anchors[i].x) - u) <= float(eva.tether_reach_m) and (best < 0 or absf(float(anchors[i].x) - u) < absf(float(anchors[best].x) - u)):
			best = i
	if best < 0:
		return "no free anchor within reach"
	return clip(f, best)

func start_abort() -> void:
	# ANIM-08: stop the tour, reverse along the rail anchor by anchor to the hatch; the plan is the protocol, executed in display time
	abort = true
	feed = ""
	plan = []
	var target := float(eva.holds.airlock.x)
	var sign := 1.0 if target > u else -1.0
	var x := u
	while absf(target - x) > 0.05:
		var nx := x + sign * minf(1.4, absf(target - x))
		plan.append(["move", nx])
		plan.append(["clip", nx])
		plan.append(["test", nx])
		plan.append(["release", nx])
		x = nx
	message = "ABORT: tour stopped. Returning to the airlock on two tethers (simulation; emergency reserve and return times OPEN)."

func step_plan(delta: float) -> void:
	if plan.is_empty():
		if abort and absf(u - float(eva.holds.airlock.x)) < 0.06:
			abort = false
			set_phase("REPRESS")
		return
	var step: Array = plan[0]
	plan_t += delta
	match step[0]:
		"move":
			var speed := float(eva.mobility.abort_speed_m_s)
			var before := u
			move(signf(float(step[1]) - u) * minf(speed * delta, absf(float(step[1]) - u)))
			if absf(u - float(step[1])) < 0.01 or absf(u - before) < 1e-6:
				plan.pop_front()
		"clip":
			if plan_t > 0.8:
				var r := clip_next()
				plan.pop_front()
				plan_t = 0.0
				if r != "" and not r.begins_with("both"):
					message = r
		"test":
			if plan_t > 0.6:
				for k in live():
					test(k)
				plan.pop_front()
				plan_t = 0.0
		"release":
			if plan_t > 0.6:
				var old := older_tether()
				if live().size() == 2 and old != "":
					release(old)
				plan.pop_front()
				plan_t = 0.0

# ---------------------------------------------------------------------------------------------------------------- airlock
func set_phase(p: String) -> void:
	phase = p
	if p != "EXTERIOR":
		end_drift()
	feed = ""
	match p:
		"PREP", "LOCK_CHECK":
			inner_open = true
			outer_open = false
			chamber = "PRESSURIZED"
			show_airlock_inside(true)
		"DEPRESS":
			if inner_open:
				inner_open = false               # the inner hatch seals first: never two doors open to vacuum
			chamber = "DEPRESSING"
			chamber_t = 0.0
		"EXTERIOR":
			show_airlock_inside(false)
		"REPRESS":
			outer_open = false
			chamber = "REPRESSING"
			chamber_t = 0.0
			show_airlock_inside(true)
		"DEBRIEF":
			inner_open = true

func open_outer() -> String:
	if inner_open:
		return "interlock: the inner hatch is open"
	if chamber != "VACUUM":
		return "interlock: the chamber is not depressurized"
	outer_open = true
	return ""

func open_inner() -> String:
	if outer_open:
		return "interlock: the outer hatch is open"
	if chamber != "PRESSURIZED":
		return "interlock: the chamber is not at cabin pressure"
	inner_open = true
	return ""

func update_plug() -> void:
	if plug:
		plug.global_transform = plug_park if inner_open else plug_seat

func show_airlock_inside(on: bool) -> void:
	for n in hidden_airlock:
		n.visible = not on
	if sim_chamber:
		sim_chamber.visible = on
	for n in room_nodes:
		n.visible = on

func step_chamber(delta: float) -> void:
	if chamber == "DEPRESSING" or chamber == "REPRESSING":
		chamber_t += delta
		if chamber_t >= CHAMBER_S:
			if chamber == "DEPRESSING":
				chamber = "VACUUM"
				var r := open_outer()
				message = r if r != "" else "Outer hatch open. Tether A is on the hatch anchor ring. Exit one at a time."
				set_phase("EXTERIOR")
			else:
				chamber = "PRESSURIZED"
				var r2 := open_inner()
				message = r2 if r2 != "" else "Cabin pressure (80 kPa, BASELINE). Inner hatch open."
				set_phase("DEBRIEF")

# ---------------------------------------------------------------------------------------------------------------- frame
func _process(delta: float) -> void:
	if eva.is_empty():
		return
	# ACI-10: no binding prompt in the drift or an abort (hazard); the two-tether lesson is offered inside, before the airlock.
	WfInput.hazard = abort or (drift != null and drift.active)
	if phase == "PREP":
		WfInput.discover("tether")
	for key in pivots:
		var item: Dictionary = pivots[key]
		item.angle += float(item.binding.rad_per_unit) * 24.0 * delta    # rings ROTATING in EVA (11!5, 15 E3): one turn per 15 s
		var axis := vec(item.binding.axis_runtime)
		item.node.transform = Transform3D(Basis(axis, item.angle), item.node.position)
	step_chamber(delta)
	update_plug()
	if phase == "EXTERIOR" and drift == null:
		if abort:
			step_plan(delta)
		else:
			var dir := 0.0
			dir += WfInput.strength("player.move_back") - WfInput.strength("player.move_forward")
			if dir != 0.0:
				feed = ""
				var pace := float(eva.mobility.translation_speed_m_s) * (REVIEW_PACE if WfInput.held("player.fast") else 1.0)
				move(dir * pace * delta)
	update_bodies(delta)
	update_camera()
	update_text()

var last_u := 0.0
var moving_t := 0.0

func update_bodies(delta: float) -> void:
	if player == null:
		return
	var moving := absf(u - last_u) > 1e-5
	moving_t = 0.4 if moving else maxf(0.0, moving_t - delta)
	var along := Vector3(signf(u - last_u) if moving else -1.0, 0, 0)
	last_u = u
	var rr := float(eva.rail_radius_m)
	if phase in ["PREP", "LOCK_CHECK", "DEPRESS", "REPRESS", "DEBRIEF"]:
		var ch: Dictionary = eva.chamber
		var ax := float(ch.axis_x)
		if eva.has("access") and phase in ["PREP", "DEBRIEF"]:
			# SP-12 buddy-check zone: the visitor in the foot restraint, the instructor behind checking the pack (EVA-040, SCRIPT-05)
			var z: Dictionary = (eva.access.rooms.sp12.fixtures as Array).filter(func(f): return str(f.id).ends_with("BUDDY_ZONE"))[0]
			var up := room_point(0, float(z.az), 1.0)
			var at := room_point(float(z.x), float(z.az), float(z.r0))
			place(player, at + Vector3(-0.30, 0, 0), Vector3(-1, 0, 0), up)
			place(guide, at + Vector3(0.45, 0, 0), Vector3(-1, 0, 0), up)
			play("newcomer", "eva_suit_check" if phase == "PREP" else "idle")
			play("instructor", "eva_buddy_check" if phase == "PREP" else "idle")
		elif eva.has("access"):
			# in the SP-11 study chamber, standing as eva_access / eva_sp11 placed the routine pair (head outboard)
			var w := Vector3(0, cos(theta), sin(theta))
			var occ: Array = eva.access.eva3.chamber.occupants if eva.access.has("eva3") else eva.access.chamber.occupants
			for o in occ:
				var node: Node3D = player if str(o.variant) == "newcomer" else guide
				var at := ship_point(ax + float(o.shift_m[0]), float(o.a_top_m) - float(o.zmax_m)) + w * float(o.shift_m[1])
				place(node, at, w if absf(float(o.theta_deg)) < 90.0 else -w, up_dir())
			play("newcomer", "eva_suit_check" if phase == "LOCK_CHECK" else "eva_airlock")
			# EVA-003: the outer hatch is unlatched from the wall lever (extension linkage), never over the head (EVA-057)
			play("instructor", "eva_latch_extension" if eva.access.has("eva3") and phase in ["DEPRESS", "REPRESS"] else "eva_airlock")
		else:
			var base := ship_point(ax, float(ch.r_outer) - 2.2)
			place(player, base + Vector3(0.35, 0, 0), Vector3(1, 0, 0), up_dir())
			place(guide, base + Vector3(-0.35, 0, 0), Vector3(-1, 0, 0), up_dir())
			var clip := "eva_suit_check" if phase in ["PREP", "LOCK_CHECK"] else ("eva_airlock" if phase != "DEBRIEF" else "idle")
			play("newcomer", clip)
			play("instructor", "eva_airlock" if phase == "DEPRESS" else clip)
	else:
		var near_hatch := absf(u - float(eva.holds.airlock.x)) < 1.25
		var r := lerpf(rr, float(eva.chamber.r_outer) + 0.05, clampf(1.0 - (absf(u - float(eva.holds.airlock.x)) - 1.0) / 0.25, 0.0, 1.0)) if near_hatch else rr
		if moving_t > 0.0:
			place(player, ship_point(u, r), along, up_dir())
			play("newcomer", "eva_abort_translate" if abort else "eva_translate")
		else:
			place(player, ship_point(u, r - 0.15), Vector3(-1, 0, 0) if u < float(eva.holds.airlock.x) else Vector3(1, 0, 0), up_dir())
			play("newcomer", "eva_tool_inspect" if feed == "radiator_feed" else "idle" if false else "eva_tether_transfer" if tethers.B != null and not tethers.B.tested else "eva_guide_point" if false else "eva_tool_inspect")
		# the instructor holds 1.4 m further along the route at the next hold, facing the visitor, and explains
		var gx := clampf(u + (-1.4 if u < float(eva.holds.airlock.x) + 0.1 else 1.4), route_ends().x, route_ends().y)
		place(guide, ship_point(gx, rr - 0.15), Vector3(1, 0, 0) if gx < u else Vector3(-1, 0, 0), up_dir())
		play("instructor", "eva_guide_point" if active_station() != {} else "eva_tether_transfer")
	draw_tethers()

func socket(node: Node3D, name: String) -> Vector3:
	var s := node.find_child(name, true, false)
	return (s as Node3D).global_position if s else node.global_position

func draw_tethers() -> void:
	for side in ["A", "B"]:
		var im: MeshInstance3D = lines.get("newcomer" + side)
		if im == null:
			continue
		var m: ImmediateMesh = im.mesh
		m.clear_surfaces()
		if phase == "EXTERIOR" and tethers[side] != null:
			m.surface_begin(Mesh.PRIMITIVE_LINES)
			m.surface_add_vertex(socket(player, "SOCKET_TETHER_" + side))
			m.surface_add_vertex(vec(anchors[int(tethers[side].anchor)].p))
			m.surface_end()

func active_station() -> Dictionary:
	# the airlock's stations by phase: suit preparation in SP-12, airlock operation in SP-11, return and debrief
	if phase == "PREP":
		return station_by_hold("airlock", 0)
	if phase in ["LOCK_CHECK", "DEPRESS"]:
		return station_by_hold("airlock", 1)
	if phase in ["REPRESS", "DEBRIEF"]:
		return station_by_hold("airlock", 2)
	var best := {}
	var bd := STATION_RADIUS
	for key in ["rail_mid", "aft_hold", "forward_hold"]:
		var d := absf(float(eva.holds[key].x) - u)
		if d < bd:
			bd = d
			best = {"hold": key}
	if best.is_empty():
		return {}
	return station_by_hold(best.hold, station_index)

var station_index := 0

func station_by_hold(hold: String, index: int) -> Dictionary:
	var list := (eva.stations as Array).filter(func(s): return s.hold == hold)
	if list.is_empty():
		return {}
	return list[clampi(index, 0, list.size() - 1)]

func update_camera() -> void:
	if player == null:
		return
	if drift != null and drift.active:
		camera.fov = 62.0
		var f := drift.body.global_position
		var side := Vector3(1, 0, 0).cross(up_dir())
		var dd := (Vector3(1, 0, 0) * cos(orbit.x) + side * sin(orbit.x)) * cos(orbit.y) + up_dir() * sin(orbit.y)
		camera.look_at_from_position(f + dd * zoom, f, up_dir())
		return
	if feed != "" and eva.feeds[feed].eye != null:
		camera.fov = 45.0
		camera.look_at_from_position(vec(eva.feeds[feed].eye), vec(eva.feeds[feed].look), up_dir() if feed != "forward_feed" else Vector3.UP)
		return
	camera.fov = 62.0
	if first_person:
		var eye := socket(player, "SOCKET_HELMET_EYE")
		camera.look_at_from_position(eye, eye + player.global_transform.basis.z * 3.0, player.global_transform.basis.y)
		return
	var focus := player.global_position + up_dir() * 0.9
	var side := Vector3(1, 0, 0).cross(up_dir())
	var dir := (Vector3(1, 0, 0) * cos(orbit.x) + side * sin(orbit.x)) * cos(orbit.y) + up_dir() * sin(orbit.y)
	camera.look_at_from_position(focus + dir * zoom, focus, up_dir())

# ---------------------------------------------------------------------------------------------------------------- UI
func label(text: String, size: int = 15) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_size_override("font_size", size)
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	return l

func build_ui(canvas: CanvasLayer) -> void:
	var top := VBoxContainer.new()
	top.position = Vector2(24, 16)
	top.custom_minimum_size = Vector2(560, 0)
	top.size = Vector2(560, 0)
	canvas.add_child(top)
	top.add_child(label("WAYFARER  /  GUIDED EVA  ·  TRAINING SIMULATION", 22))
	banner.add_theme_font_size_override("font_size", 13)
	banner.custom_minimum_size = Vector2(560, 0)
	banner.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	banner.add_theme_color_override("font_color", Color(1.0, 0.75, 0.3))
	top.add_child(banner)
	var keys := label("Enter: next step   W / S: along the rail (Shift review pace)   T: clip free tether   Y: tug-test   R: release older tether\n1 / 2 / 3: What is it? / Why this design? / Show me   N: next station topic   K: ring keep-out   V: helmet view   X: ABORT   Esc: leave\nRight-drag: orbit   Wheel: zoom", 12)
	keys.custom_minimum_size = Vector2(560, 0)
	top.add_child(keys)
	ui_panels.append(top)
	var side := PanelContainer.new()
	canvas.add_child(side)
	side.set_anchors_and_offsets_preset(Control.PRESET_TOP_RIGHT)
	side.offset_left = -400
	side.offset_right = -16
	side.offset_top = 16
	var col := VBoxContainer.new()
	side.add_child(col)
	col.add_child(label("SUIT TELEMETRY  ·  EXAMPLE MODE (EVA-039)", 15))
	hud.add_theme_font_size_override("font_size", 12)
	hud.custom_minimum_size = Vector2(380, 0)
	col.add_child(hud)
	ui_panels.append(side)
	var bottom := PanelContainer.new()
	canvas.add_child(bottom)
	bottom.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_WIDE)
	bottom.offset_left = 16
	bottom.offset_right = -16
	bottom.offset_top = -250
	bottom.offset_bottom = -12
	var body := VBoxContainer.new()
	bottom.add_child(body)
	status.add_theme_font_size_override("font_size", 14)
	body.add_child(status)
	station_text.add_theme_font_size_override("font_size", 15)
	station_text.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	station_text.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	body.add_child(station_text)
	hint.add_theme_font_size_override("font_size", 13)
	hint.add_theme_color_override("font_color", Color(0.75, 0.85, 1.0))
	hint.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	body.add_child(hint)
	ui_panels.append(bottom)

var explain := "what"

func update_text() -> void:
	var st := active_station()
	var s := ""
	if not st.is_empty():
		var key := explain if st.has(explain) else "what"
		var heading: String = {"what": "WHAT IS IT?", "why": "WHY THIS DESIGN?", "show": "SHOW ME"}[key]
		s = "%s  —  %s   (Tale %s, WORKING SCRIPT)\n%s: %s" % [st.id, st.title, st.get("script", ""), heading, st.show_text if key == "show" else st[key]]
		s += "\nSafety: %s\nSources: %s" % [st.get("safety", ""), st.sources]
	station_text.text = s
	var gates := ""
	var hold := nearest_hold()
	for g in eva.holds[hold].gates:
		gates += "%s %s/%s   " % [g.id, g.status, g.get("state", "HOLD")]
	var fl: Dictionary = eva.get("flight", {"state": "HOLD", "mode": "FLIGHT_EVA"})
	banner.text = "MODE %s: %s at %s   ·   %s: %s (locked, 45 O-07)\ngates (training/flight): %s" % [eva.mode, eva.holds[hold].status, hold, fl.mode, fl.state,
		gates.strip_edges()]
	var tl := ""
	for k in ["A", "B"]:
		tl += "  tether %s: %s" % [k, "—" if tethers[k] == null else "%s%s" % [anchors[int(tethers[k].anchor)].id, " tested" if tethers[k].tested else " UNTESTED"]]
	status.text = "PHASE %s   chamber %s   inner hatch %s   outer hatch %s   X %.2f m%s%s\n%s" % [phase, chamber, "OPEN" if inner_open else "SHUT", "OPEN" if outer_open else "SHUT", u, tl,
		"   ABORT" if abort else "", "" if message == "" else "   ·  " + message]
	var t := ""
	for k in eva.telemetry:
		var f: Dictionary = eva.telemetry[k]
		var v = f.value
		t += "%s: %s %s  [%s]\n" % [k, "OPEN" if v == null else str(v), f.unit if v != null else "", f.status]
	if eva.has("reference_case"):
		var rc: Dictionary = eva.reference_case
		t += "study case (%s): %s kPa abs, O2 fraction %s; not a setpoint, no prebreathe or duration\n" % [rc.status, rc.suit_pressure_kpa, rc.suit_o2_fraction]
	t += "tethers live: %d   (never zero)" % live().size()
	if drift != null and drift.active:
		t += "\n" + drift.hud_text()
	hud.text = t
	var h := ""
	match phase:
		"PREP":
			h = "SP-12 (study room): suit check and buddy check with the instructor; no prebreathe clock (protocol OPEN). Enter: into SP-11 for the GO check."
		"LOCK_CHECK":
			h = ("SP-11 STUDY %s (1.20 m lead, no hull cut): inner hatch a sliding plug, outer latch from the wall lever. " % eva.access.eva3.id if eva.has("access") and eva.access.has("eva3") else "") + "GO check: leak check, reserve, telemetry, tethers, comms. OPEN values would stop a real EVA (ANIM-02); this run continues only as a labelled TRAINING SIMULATION. Enter: depress (no prebreathe clock: OPEN)."
		"DEPRESS":
			h = "Inner hatch sealed first. Depressurizing (display; duration OPEN)…"
		"EXTERIOR":
			h = "Feed: " + str(eva.feeds[feed].label) if feed != "" else "Outside on the stationary forward collar. Two tethers, hand over hand. Holds: rail_mid, aft_hold (rings, radiators, drive), forward_hold (Brow, EYE). Return to the hatch and press Enter to repressurize."
		"REPRESS":
			h = "Outer hatch sealed. Repressurizing to cabin (display)…"
		"DEBRIEF":
			h = "Debrief: inspection logged. The visitor and the instructor leave Wayfarer before First Ignition (S004D). " + WfInput.label("ui.cancel") + ": back to the induction."
	hint.text = h

func nearest_hold() -> String:
	var best := "airlock"
	for key in eva.holds:
		if absf(float(eva.holds[key].x) - u) < absf(float(eva.holds[best].x) - u):
			best = key
	return best

func show_me(st: Dictionary) -> void:
	explain = "show"
	match str(st.show):
		"suit_cutaway":
			show_stage = (show_stage + 1) % 4
			cutaway("instructor", show_stage)
		"ring_sweep":
			keepout.visible = true
			feed = "ring_sweep"
		"radiator_feed", "drive_cutaway", "forward_feed":
			feed = str(st.show)
		"airlock_states":
			feed = ""
			show_airlock_inside(true)
			message = "Interlock: inner %s, chamber %s, outer %s. Never both doors open while pressure must be held. Chamber drawn: %s (STUDY)." % [
				"OPEN" if inner_open else "SHUT", chamber, "OPEN" if outer_open else "SHUT", eva.access.chamber.id if eva.has("access") else "simulated"]
		"tether_handoff":
			feed = ""
			play("instructor", "eva_tether_transfer")
		_:
			feed = ""

func cutaway(key: String, stage: int) -> void:
	# 0 assembled; 1 outer layer off (bladder); 2 bladder off (cooling garment); 3 PLSS opened (internals)
	if not players.has(key):
		return
	var node: Node3D = players[key].node
	var rec: Dictionary = players[key].rec
	for n in rec.nodes:
		var hit := node.find_child(n, true, false)
		if hit == null:
			continue
		var part: String = str(rec.nodes[n].part_id).get_slice("/", 2)
		var v: bool = rec.nodes[n].show != "cutaway"
		if stage >= 1 and part == "MMOD_OUTER_SHELL":
			v = false
		if stage == 1 and part == "SUIT_PRESSURE_BLADDER":
			v = true
		if stage >= 2 and part == "LCVG_INNER":
			v = true
		if stage == 3 and part == "PLSS_PRIMARY":
			v = rec.nodes[n].show == "cutaway" or n.ends_with("Port") or n.ends_with("Display") or n.ends_with("DCM")
		if stage >= 1 and part == "SUIT_PRESSURE_HARD_TORSO":
			v = false
		hit.visible = v

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		if event.button_index == MOUSE_BUTTON_RIGHT:
			dragging = event.pressed
		elif event.button_index == MOUSE_BUTTON_WHEEL_UP:
			zoom = maxf(1.2, zoom * 0.9)
		elif event.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			zoom = minf(60.0, zoom * 1.1)
	elif event is InputEventMouseMotion and dragging:
		orbit += Vector2(-event.relative.x, event.relative.y) * 0.006
		orbit.y = clampf(orbit.y, -1.3, 1.3)
	elif WfInput.pressed(event):
		# ACI-10: eva.* actions, ui.confirm (advance) and ui.cancel, matched by their default keys; the EVA rules are unchanged.
		var ek := WfInput.key_of(event, ["eva"])
		if ek == KEY_NONE:
			return
		message = ""
		if drift != null and drift.active and ek in [KEY_T, KEY_Y, KEY_R]:
			# J01: the two-tether protocol in the drift (clip the free tether to an anchor in hand reach, tug-test, release the older)
			message = drift.clip_next() if ek == KEY_T else (drift.test_untested() if ek == KEY_Y else drift.release_older())
			if message == "":
				WfInput.performed({KEY_T: "eva.clip", KEY_Y: "eva.tug_test", KEY_R: "eva.release_tether"}[ek])
			return
		if drift != null and drift.active and ek in [KEY_X, KEY_ENTER]:
			message = "drifting: %s returns to the hatch first" % WfInput.label("eva.drift")
			return
		match ek:
			KEY_F:
				message = toggle_drift()
			KEY_H:
				if review != null and review.session.hand_over_hand(review.index):   # U04: on the rail short of the anchor
					message = ""
				elif drift != null and drift.active:
					message = "" if drift.grab() else "no handhold within reach"
			KEY_SPACE:
				if drift != null and drift.active:
					message = "" if drift.push(-camera.global_transform.basis.z) else "hold the hatch anchor (%s) to push off" % WfInput.label("eva.grab")
			KEY_G:
				if review != null and drift != null and drift.active:      # U04 review aid: the profile push, aimed at the step's target
					review.session.aimed_push(review.index)
			KEY_J:
				if drift != null and drift.active and drift.experimental_thruster:
					drift.jet(-camera.global_transform.basis.z)
			KEY_ESCAPE:
				get_tree().change_scene_to_file("res://scenes/review.tscn" if review != null else "res://scenes/boarding.tscn")
			KEY_ENTER:
				advance()
			KEY_T:
				if phase == "EXTERIOR" and not abort:
					message = clip_next()
					if message == "":
						WfInput.performed("eva.clip")
			KEY_Y:
				if phase == "EXTERIOR":
					for k in live():
						if not tethers[k].tested:
							test(k)
							message = "tether %s tug-tested" % k
							WfInput.performed("eva.tug_test")
			KEY_R:
				if phase == "EXTERIOR" and not abort:
					var old := older_tether()
					message = release(old) if old != "" else "nothing to release"
					if message == "":
						message = "tether %s released" % old
						WfInput.performed("eva.release_tether")
			KEY_1:
				explain = "what"
				feed = ""
			KEY_2:
				explain = "why"
				feed = ""
			KEY_3:
				var st := active_station()
				if not st.is_empty():
					show_me(st)
			KEY_N:
				station_index += 1
				explain = "what"
				feed = ""
			KEY_K:
				keepout.visible = not keepout.visible
			KEY_V:
				first_person = not first_person
			KEY_X:
				if phase == "EXTERIOR" and not abort:
					start_abort()

## F: step out of the hatch into the 3-D drift (EXTERIOR only), or back to the hatch anchor. Returns the refusal text, or "".
func toggle_drift() -> String:
	if drift != null and drift.active:
		end_drift()
		return ""
	if rig_dyn.is_empty():
		return "no generated/wf_sim_rig.json"
	var ks := live()
	var anchor := vec(eva.hatch)       # the tether and the first grip are on the real SP-11 outer hatch (PROTOTYPE fitting)
	drift = WfEvaDrift.new(rig_dyn)
	drift.eva = eva
	add_child(drift)
	var r := drift.egress("EXTERIOR" if phase == "EXTERIOR" and not abort else phase, anchor, up_dir(), float(eva.tether_reach_m), ks.size())
	if not r.ok:
		drift.free()
		drift = null
		return str(r.reason)
	show_rail_suits(false)
	attach_drift_suit()
	return ""

## The rail-walk suit models are hidden while the drift runs (the visible second astronaut was the instructor, `guide`, holding on the rail).
func show_rail_suits(on: bool) -> void:
	for n in [player, guide]:
		if n:
			n.visible = on

## ARTISTIC layer: another instance of the newcomer suit model on the drift body (pose only), replacing the grey capsule.
func attach_drift_suit() -> void:
	if suits.is_empty() or drift == null or not drift.active:
		return
	var rec: Dictionary = suits.variants.newcomer
	var m: Node3D = (load("res://generated/characters/" + str(rec.glb)) as PackedScene).instantiate()
	for n in rec.cutaway:
		var hit := m.find_child(n, true, false)
		if hit:
			hit.visible = false
	drift.attach_artistic(m)
	var ap := m.find_children("*", "AnimationPlayer", true, false)
	if not ap.is_empty() and (ap[0] as AnimationPlayer).has_animation("idle"):
		(ap[0] as AnimationPlayer).play("idle")

func end_drift() -> void:
	if drift != null:
		drift.end()
		drift.queue_free()
		drift = null
	show_rail_suits(true)

func advance() -> void:
	match phase:
		"PREP":
			set_phase("LOCK_CHECK")
		"LOCK_CHECK":
			set_phase("DEPRESS")
		"EXTERIOR":
			if absf(u - float(eva.holds.airlock.x)) < 0.3:
				set_phase("REPRESS")
			else:
				message = "Return to the hatch first (or %s to abort)" % WfInput.label("eva.abort")
		"DEBRIEF":
			get_tree().change_scene_to_file("res://scenes/boarding.tscn")

## Review still: push off the hatch anchor and let it drift (the capture waits about two seconds more).
func drift_push_shot() -> void:
	await get_tree().physics_frame
	if drift != null and drift.active:
		drift.push(up_dir())

func shot(name: String) -> void:
	if name == "prep":
		set_phase("PREP")
		orbit = Vector2(0.9, 0.35)
		zoom = 4.2
		return
	if name == "lock":
		set_phase("LOCK_CHECK")
		explain = "show"
		show_me(station_by_hold("airlock", 1))
		orbit = Vector2(1.57, 0.10)
		zoom = 1.6
		return
	if name == "latch":
		# EVA-003: the instructor unlatches the outer hatch from the wall lever while the chamber depressurizes (display)
		set_phase("DEPRESS")
		orbit = Vector2(2.3, 0.25)
		zoom = 2.6
		return
	if name == "cutaway":
		show_stage = 3
		cutaway("instructor", 3)
		orbit = Vector2(1.9, 0.15)
		zoom = 2.6
		return
	chamber = "VACUUM"
	inner_open = false
	outer_open = true
	set_phase("EXTERIOR")
	u = {"exterior": float(eva.holds.rail_mid.x), "aft": float(eva.holds.aft_hold.x) + 0.2, "forward": float(eva.holds.forward_hold.x) - 0.2,
		"radiator": float(eva.holds.aft_hold.x) + 0.2, "rings": float(eva.holds.aft_hold.x) + 0.2, "eye": float(eva.holds.forward_hold.x) - 0.2}.get(name, u)
	tethers = {"A": {"anchor": nearest_anchor(u), "tested": true}, "B": null}
	zoom = 6.0
	orbit = Vector2(2.4, 0.45)
	match name:
		"drift", "drift_wide", "drift_push", "drift_nofit":
			toggle_drift.call_deferred()
			if name == "drift_push":
				drift_push_shot.call_deferred()
			if name == "drift_nofit":
				for n in hidden_airlock:
					n.visible = false
			orbit = Vector2(0.9, 0.5) if name == "drift_wide" else Vector2(2.2, 0.35)
			zoom = 12.0 if name == "drift_wide" else (7.0 if name == "drift_push" else 4.5)
		"radiator":
			feed = "radiator_feed"
			station_index = 1
			explain = "show"
		"rings":
			feed = "ring_sweep"
			keepout.visible = true
		"eye":
			feed = "forward_feed"
			explain = "show"

# ---------------------------------------------------------------------------------------------------------------- performance (EXP-02)
func run_perf() -> void:
	# Frame time of representative views on this machine's GPU, VSync off, after a warm-up; draw calls and primitives per frame.
	# A measurement of the training scene, not an optimization target by itself (AGENTS.md: measure before optimizing).
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	var bare := "--no-suits" in OS.get_cmdline_user_args()     # EXP-02 baseline: the same views without the suited pair
	if bare:
		for key in players:
			players[key].node.visible = false
	var out := {"suits": not bare, "adapter": RenderingServer.get_video_adapter_name(), "api": RenderingServer.get_video_adapter_api_version(),
		"method": str(ProjectSettings.get_setting("rendering/renderer/rendering_method")), "viewport": [get_viewport().size.x, get_viewport().size.y],
		"load_ms": load_ms, "views": {}}
	for v in ["prep", "exterior", "aft", "radiator", "eye", "cutaway"]:
		if v == "prep":
			set_phase("PREP")
		else:
			shot(v)
		for i in 120:
			await get_tree().process_frame
		var times := []
		var draws := 0
		var prims := 0
		var t0 := Time.get_ticks_usec()
		for i in 600:
			await get_tree().process_frame
			var t1 := Time.get_ticks_usec()
			times.append((t1 - t0) / 1000.0)
			t0 = t1
			draws = maxi(draws, int(Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME)))
			prims = maxi(prims, int(Performance.get_monitor(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME)))
		times.sort()
		var mean := 0.0
		for x in times:
			mean += x
		mean /= times.size()
		out.views[v] = {"mean_ms": snappedf(mean, 0.01), "p50_ms": snappedf(times[times.size() / 2], 0.01), "p95_ms": snappedf(times[int(times.size() * 0.95)], 0.01),
			"p99_ms": snappedf(times[int(times.size() * 0.99)], 0.01), "fps_mean": snappedf(1000.0 / mean, 0.1), "draw_calls_max": draws, "primitives_max": prims}
	out["video_mem_mb"] = snappedf(Performance.get_monitor(Performance.RENDER_VIDEO_MEM_USED) / 1048576.0, 0.1)
	out["static_mem_mb"] = snappedf(Performance.get_monitor(Performance.MEMORY_STATIC) / 1048576.0, 0.1)
	print("WF_GODOT_EVA_PERF " + JSON.stringify(out))
	get_tree().quit(0)

# ---------------------------------------------------------------------------------------------------------------- headless check
func run_check() -> void:
	var fail := []
	var out := {"anchors": anchors.size(), "stations": eva.stations.size(), "suits": players.keys()}
	if anchors.size() < 4:
		fail.append("too few anchors")
	if eva.stations.size() != 7:
		fail.append("expected 7 stations")
	for key in eva.holds:
		if eva.holds[key].status == "GO":
			fail.append("hold %s is GO although limits are OPEN" % key)
		for g in eva.holds[key].gates:
			if g.limit == null and g.status == "PASS" and g.id != "drive":
				fail.append("gate %s passes with an OPEN limit" % g.id)
			if g.get("state", "") == "VALIDATED":
				fail.append("gate %s VALIDATED without an owner release" % g.id)
	for k in eva.telemetry:
		if eva.telemetry[k].status == "OPEN" and eva.telemetry[k].value != null:
			fail.append("OPEN telemetry %s carries a value" % k)
	# FLIGHT_EVA is a separate, locked state (EVA-049, EVA2-008): HOLD whatever this check finds
	if eva.get("flight", {}).get("state", "") != "HOLD" or eva.get("flight", {}).get("available", true):
		fail.append("FLIGHT_EVA is not HOLD / unavailable")
	out["flight"] = eva.get("flight", {}).get("state", "")
	for st in eva.stations:
		if not str(st.get("script", "")).begins_with("SCRIPT-"):
			fail.append("station %s has no Tale script" % st.id)
	if eva.has("access"):
		out["sp11_study"] = eva.access.chamber.id
		if eva.access.has("eva3"):
			out["sp11_eva3"] = eva.access.eva3.id
			if str(eva.access.eva3.inner_hatch.mechanism) != "parallel_plug_slide":
				fail.append("EVA-003 lead shown with a rejected or failing inner hatch")
	else:
		fail.append("no SP-11/12/13 study in wf_eva.json")
	for key in players:
		var p: Dictionary = players[key]
		for clip in suits.variants[key].eva_actions:
			if not (p.player as AnimationPlayer).has_animation(clip):
				fail.append("%s lacks %s" % [key, clip])
		for sock in ["SOCKET_TETHER_A", "SOCKET_TETHER_B", "SOCKET_HELMET_EYE", "SOCKET_HAND_R_GRIP"]:
			if p.node.find_child(sock, true, false) == null:
				fail.append("%s lacks %s" % [key, sock])
	if players.size() != 2:
		fail.append("suited pair not loaded")
	# airlock interlock
	set_phase("PREP")
	if open_outer() == "":
		fail.append("outer hatch opened with the inner open")
	set_phase("DEPRESS")
	if inner_open:
		fail.append("depress with the inner hatch open")
	chamber_t = CHAMBER_S
	step_chamber(0.0)
	if not outer_open or phase != "EXTERIOR":
		fail.append("depress did not open the outer hatch")
	if open_inner() == "":
		fail.append("inner hatch opened with the outer open")
	# tethers: release refused with one live; reach clamps; full handoff aft to the aft hold keeps >= 1 live
	u = float(eva.holds.airlock.x)
	tethers = {"A": {"anchor": nearest_anchor(u), "tested": true}, "B": null}
	if release("A") == "":
		fail.append("released the only tether")
	var min_live := 2
	var target := float(eva.holds.aft_hold.x)
	var guard := 0
	while absf(u - target) > 0.02 and guard < 400:
		guard += 1
		move(-0.05)
		min_live = mini(min_live, live().size())
		if absf(u - limits().x) < 1e-4 and absf(u - target) > 0.02:
			var r := clip_next()
			if r != "" and not r.begins_with("both"):
				fail.append("clip: " + r)
				break
			for k in live():
				test(k)
			var old := older_tether()
			if live().size() == 2:
				var rr := release(old)
				if rr != "":
					fail.append("release: " + rr)
					break
			min_live = mini(min_live, live().size())
	out["reached_aft_hold"] = absf(u - target) <= 0.02
	out["min_live_tethers"] = min_live
	if not out.reached_aft_hold:
		fail.append("aft hold not reached on tethers")
	if min_live < 1:
		fail.append("zero live tethers")
	# abort from the aft hold returns to the hatch on tethers and repressurizes
	start_abort()
	var t := 0.0
	while (abort or not plan.is_empty()) and t < 240.0:
		step_plan(0.05)
		min_live = mini(min_live, live().size())
		t += 0.05
	out["abort_s_display"] = snappedf(t, 0.1)
	out["abort_min_live"] = min_live
	if phase != "REPRESS":
		fail.append("abort did not reach the airlock (phase %s, X %.2f)" % [phase, u])
	if min_live < 1:
		fail.append("zero live tethers during abort")
	chamber_t = CHAMBER_S
	step_chamber(0.0)
	if not inner_open or outer_open:
		fail.append("repress did not end with inner open, outer shut")
	await check_drift(out, fail)
	out["fail"] = fail
	out["result"] = "PASS" if fail.is_empty() else "FAIL"
	finish(out)

## PHYS-001 phase 5: the 3-D tethered drift (SIMULATION_ONLY, PROTOTYPE tether length = tether_reach_m; FLIGHT_EVA stays HOLD).
func check_drift(out: Dictionary, fail: Array) -> void:
	var dr := {}
	out["drift"] = dr
	if rig_dyn.is_empty():
		fail.append("drift: no generated/wf_sim_rig.json")
		return
	var L := float(eva.tether_reach_m)
	var anchor := vec(eva.hatch)
	# egress is refused outside the EXTERIOR phase and without a live tether
	var d0 := WfEvaDrift.new(rig_dyn)
	add_child(d0)
	for ph in ["PREP", "LOCK_CHECK", "DEPRESS", "REPRESS", "DEBRIEF"]:
		if d0.egress(ph, anchor, up_dir(), L, 2).ok:
			fail.append("drift: egress allowed in phase " + ph)
	if d0.egress("EXTERIOR", anchor, up_dir(), L, 0).ok:
		fail.append("drift: egress allowed with no live tether")
	dr["egress_refused_outside_exterior"] = not d0.active
	d0.free()
	var dt0 := WfEvaDrift.new(rig_dyn)
	out["thruster_default"] = dt0.experimental_thruster
	dt0.free()
	if out["thruster_default"]:
		fail.append("drift: experimental thruster flag is on by default")
	var run_case := {}
	for clipped in [true, false]:
		set_phase("EXTERIOR")
		var d := WfEvaDrift.new(rig_dyn)
		d.eva = eva
		add_child(d)
		var r := d.egress(phase, anchor, up_dir(), L, 2)
		if not r.ok:
			fail.append("drift: egress refused at EXTERIOR: " + str(r.reason))
			d.free()
			return
		await get_tree().physics_frame
		var key := "clipped" if clipped else "unclipped"
		var rec_: WfRecorder = null
		if clipped:
			rec_ = eva_tether_recorder(d, anchor, L)
		var res := {"v_rel_at_egress": d.v_rel().length(), "field_g": d.field.g_of(d.field.eval(WfFrames.from_vec(d.body.global_position), WfFrames.from_vec(d.body.linear_velocity)))}
		if not clipped:
			d.force_unclip()
		if not d.body.push(up_dir(), -1.0, Vector3.ZERO):
			fail.append("drift: push-off refused")
		await get_tree().physics_frame
		var v0 := d.body.linear_velocity
		var p0 := d.body.global_position
		var n := up_dir()
		var worst := 0.0
		var t := 0.0
		var steps := 0
		var seen_taut := false
		var min_clear: float = d.hull_clearance()
		while t < 8.0:
			await get_tree().physics_frame
			t += 1.0 / Engine.physics_ticks_per_second
			steps += 1
			worst = maxf(worst, d.body.global_position.distance_to(anchor) - L)
			min_clear = minf(min_clear, d.hull_clearance())
			seen_taut = seen_taut or d.tether.state == WfTether.TAUT
			if clipped and seen_taut and steps > 30 and d.body.global_position.distance_to(anchor) > L - 1e-3:
				break
		await get_tree().physics_frame
		t += 1.0 / Engine.physics_ticks_per_second
		res["push_speed"] = v0.length()
		res["overshoot_m"] = worst
		res["tether_state"] = d.tether.state
		res["outward_speed_after"] = d.body.linear_velocity.dot((d.body.global_position - anchor).normalized())
		res["dist_m"] = d.body.global_position.distance_to(anchor)
		res["min_hull_clearance_m"] = min_clear
		res["dv_drift"] = (d.body.linear_velocity - v0).length()
		res["travel_err_m"] = (d.body.global_position - (p0 + v0 * t)).length() if not clipped else 0.0
		run_case[key] = res
		if rec_ != null:
			for i in 60:
				await get_tree().physics_frame      # about 1 s on the taut tether, recorded after the check values were taken
			rec_.save()
			rec_.queue_free()
		d.end()
		d.queue_free()
	# a push toward the hull from a rail anchor is stopped by contact with the collision proxy (no tunnelling)
	set_phase("EXTERIOR")
	var dh := WfEvaDrift.new(rig_dyn)
	dh.eva = eva
	add_child(dh)
	if not dh.egress(phase, anchor, up_dir(), L, 2).ok:
		fail.append("drift: egress refused for the hull push")
	else:
		dh.force_unclip()
		await get_tree().physics_frame
		# beside the rail (0.6 m round the collar from ANC_AFT_02), so the body meets the hull proxy and not the rail rod (J01)
		var a2 := dh.anchor_hold("ANC_AFT_02")
		var side := Vector3.RIGHT.cross(up_dir()).normalized()
		var hres := {"moved": a2 != null}
		if a2 != null:
			dh.move_to(a2.position + up_dir() * 0.5 + side * 0.6)
		await get_tree().physics_frame
		await get_tree().physics_frame
		var h_clear: float = dh.hull_clearance()
		hres["start_clearance_m"] = h_clear
		var h_min: float = h_clear
		dh.body.linear_velocity = -up_dir() * float(dh.body.profile["test_push_dv_m_s"])     # check set-up: the profile push speed toward the hull
		hres["pushed"] = true
		await get_tree().physics_frame
		var hv0: Vector3 = dh.body.linear_velocity
		for i in 360:
			await get_tree().physics_frame
			h_min = minf(h_min, dh.hull_clearance())
		hres["push_speed"] = hv0.length()
		hres["min_clearance_m"] = h_min
		hres["end_clearance_m"] = dh.hull_clearance()
		hres["end_inward_speed"] = maxf(0.0, -dh.body.linear_velocity.dot(up_dir()))
		hres["contact_made"] = dh.body.contact_step >= 0
		run_case["hull"] = hres
		if not hres.moved or not hres.pushed:
			fail.append("drift: hull push set-up failed (%s)" % JSON.stringify(hres))
		elif h_min < -0.01 or not hres.contact_made or hres.end_clearance_m < -0.01:
			fail.append("drift: the push toward the hull was not stopped by contact (min clearance %.4f, contact %s)" % [h_min, str(hres.contact_made)])
	dh.end()
	dh.queue_free()
	var c: Dictionary = run_case["clipped"]
	var u: Dictionary = run_case["unclipped"]
	dr["clipped"] = c
	dr["unclipped"] = u
	dr["hull_push"] = run_case.get("hull", {})
	dr["placement"] = "real hatch %s, tether anchor = hatch, collider %d radius samples + fitting cylinder (PROTOTYPE)" % [str(eva.hatch), eva.collider.samples.size()]
	if c.min_hull_clearance_m < -0.01 or u.min_hull_clearance_m < -0.01:
		fail.append("drift: body penetrated the hull proxy (clearance %.4f / %.4f)" % [c.min_hull_clearance_m, u.min_hull_clearance_m])
	dr["tether_length_m"] = L
	dr["tether_status"] = eva.tether_reach_status
	if absf(c.v_rel_at_egress) > 1e-6 or absf(u.v_rel_at_egress) > 1e-6:
		fail.append("drift: v_rel at egress not zero")
	if c.field_g > 1e-9:
		fail.append("drift: EVA field not zero")
	if absf(c.push_speed - 0.3) > 1e-3:
		fail.append("drift: push-off speed %.4f != the profile 0.3 m/s" % c.push_speed)
	if c.overshoot_m > 1e-3 or c.tether_state != WfTether.TAUT or absf(c.dist_m - L) > 1e-3:
		fail.append("drift: tether did not stop the drift at L (overshoot %.5f, state %s, dist %.4f)" % [c.overshoot_m, c.tether_state, c.dist_m])
	if c.outward_speed_after > 1e-6:
		fail.append("drift: outward speed after the stop %s" % String.num_scientific(c.outward_speed_after))
	if u.tether_state != WfTether.UNCLIPPED or u.dist_m <= L or u.dv_drift > 1e-6 or u.travel_err_m > 1e-3:
		fail.append("drift: unclipped drift was restrained or changed (state %s, dist %.3f, dv %s, travel err %s)" % [u.tether_state, u.dist_m, String.num_scientific(u.dv_drift), String.num_scientific(u.travel_err_m)])
	# J01: rail contact and the two-tether protocol in the drift
	await check_drift_protocol(dr, anchor, L, fail)
	# the thruster has no effect while its flag is off
	var dj := WfEvaDrift.new(rig_dyn)
	if dj.jet(Vector3.UP):
		fail.append("drift: jet fired with the flag off")
	dj.free()
	var fl: Dictionary = eva.get("flight", {})
	out["flight_after_drift"] = fl.get("state", "")
	if fl.get("state", "") != "HOLD" or fl.get("available", true):
		fail.append("drift: FLIGHT_EVA is not HOLD")

## J01: the rail runs are graspable rods with a collider; the two tethers follow the rail protocol in 3-D (never zero live tethers, release only
## after the other is clipped to a different anchor and tested); with both clipped the body stays inside both tether spheres.
func check_drift_protocol(dr: Dictionary, anchor: Vector3, L: float, fail: Array) -> void:
	set_phase("EXTERIOR")
	var d := WfEvaDrift.new(rig_dyn)
	d.eva = eva
	add_child(d)
	if not d.egress(phase, anchor, up_dir(), L, 2).ok:
		fail.append("drift protocol: egress refused")
		d.free()
		return
	await get_tree().physics_frame
	var res := {"rail_radius_m": d.rail_radius, "rods": d.holds.filter(func(h): return str(h.anchor_id).begins_with("EVA_RAIL_")).map(func(h): return h.anchor_id)}
	# rail contact: halfway between two aft anchors, 0.5 m out, the hand closes on the rod (not on an anchor point)
	var a0 := d.anchor_hold("ANC_AFT_00")
	var a1 := d.anchor_hold("ANC_AFT_01")
	var mid := (a0.position + a1.position) * 0.5
	d.move_to(mid + up_dir() * 0.5)
	await get_tree().physics_frame
	var grabbed := d.grab()
	var on_rod := false
	if grabbed and d.body.grip != null:
		var hp: Vector3 = d.body.grip.anchor_near(d.body.global_position)
		var run: Array = eva.runs.aft
		on_rod = str(d.body.grip.anchor_id) == "EVA_RAIL_AFT" and Vector2(hp.y - mid.y, hp.z - mid.z).length() < 1e-4 \
			and hp.x >= minf(run[0], run[1]) and hp.x <= maxf(run[0], run[1]) and minf(hp.distance_to(a0.position), hp.distance_to(a1.position)) > 0.25
	var hand: Vector3 = d.body.grip.anchor_near(d.body.global_position) if d.body.grip else Vector3.INF
	res["rail_grab"] = {"grabbed": grabbed, "grip": d.body.grip.anchor_id if d.body.grip else "", "hand_on_rod": on_rod, "hand_m": [hand.x, hand.y, hand.z], "mid_m": [mid.x, mid.y, mid.z]}
	# protocol at ANC_AFT_00 (A is on the hatch anchor)
	d.move_to(a0.position + up_dir() * 0.5)
	await get_tree().physics_frame
	var steps := []
	var never_zero := true
	for act in [["release", "A", false], ["clip", "B", true], ["clip_same", "A", false], ["release", "A", false], ["test", "B", true], ["release", "A", true],
			["release", "B", false]]:
		var why := ""
		match act[0]:
			"clip": why = d.clip(act[1], a0)
			"clip_same": why = d.clip(act[1], a0) if d.tethers.A == null else "tether A is already clipped"
			"test": why = d.test(act[1])
			"release": why = d.release(act[1])
		var ok := why == ""
		steps.append({"step": "%s %s" % [act[0], act[1]], "ok": ok, "reason": why, "live": d.live().size()})
		never_zero = never_zero and d.live().size() > 0
		if ok != act[2]:
			fail.append("drift protocol: %s %s %s (%s)" % [act[0], act[1], "allowed" if ok else "refused", why])
	res["steps"] = steps
	res["never_zero"] = never_zero
	if not never_zero:
		fail.append("drift protocol: live tethers dropped to zero")
	# a second clip to the next anchor out of hand reach is refused; within reach it is allowed
	res["far_clip_refused"] = d.clip("A", d.anchor_hold("ANC_AFT_03")) != ""
	if not res.far_clip_refused:
		fail.append("drift protocol: clip to an anchor out of hand reach allowed")
	# two tethers: A on ANC_AFT_01, B on ANC_AFT_00; push outward and the body stays inside both spheres
	d.move_to(a1.position + up_dir() * 0.5)
	await get_tree().physics_frame
	var ca := d.clip("A", a1)
	d.test("A")
	d.move_to((a0.position + a1.position) * 0.5 + up_dir() * 0.5)
	await get_tree().physics_frame
	d.grab()
	var pushed := d.push(up_dir())
	var worst := -INF
	var both_taut := false
	for i in 600:
		await get_tree().physics_frame
		worst = maxf(worst, maxf(d.body.global_position.distance_to(a0.position) - L, d.body.global_position.distance_to(a1.position) - L))
		both_taut = both_taut or (d.tethers.A.state == WfTether.TAUT and d.tethers.B.state == WfTether.TAUT)
	res["two_tether"] = {"clip_a": ca, "pushed": pushed, "overshoot_m": worst, "both_taut_seen": both_taut,
		"impulse_a_n_s": d.tethers.A.impulse_abs, "impulse_b_n_s": d.tethers.B.impulse_abs}
	if ca != "" or not pushed or worst > 1e-3:
		fail.append("drift protocol: two-tether limit (%s)" % JSON.stringify(res.two_tether))
	if not grabbed or not on_rod or res.rods.size() != eva.runs.size():
		fail.append("drift protocol: rail contact (%s)" % JSON.stringify(res.rail_grab))
	dr["protocol"] = res
	d.end()
	d.queue_free()

## Trace eva_tether (SIMULATION_ONLY, runs/physics/eva_tether.json): the clipped push-off from the hatch anchor until the tether is taut and after.
func eva_tether_recorder(d: WfEvaDrift, anchor: Vector3, L: float) -> WfRecorder:
	var r := WfRecorder.new()
	r.scenario = "eva_tether"
	r.field = d.field
	r.rig = {}
	r.bodies["actor"] = d.body
	r.grip_of = func(): return d.body.grip.anchor_id if d.body and d.body.grip else ""
	var pad := L + 0.6
	r.scene = {"room": {"interior_m": [2.0 * pad, 2.0 * pad, 2.0 * pad], "wall_m": 0.0, "centre_m": [anchor.x, anchor.y, anchor.z], "prototype": true},
		"zone": "SHIP", "mode": "EVA", "handholds": d.holds.map(func(h): return {"anchor_id": h.anchor_id, "anchor_point": [h.position.x, h.position.y, h.position.z], "radius_m": 0.025}),
		"bodies": {"actor": {"kind": "actor", "profile": "human_suited", "capsule_radius_m": d.body.profile["radius_m"], "capsule_height_m": d.body.profile["height_m"], "mass_kg": d.body.profile["mass_kg"]}},
		"tether": {"anchor_point": [anchor.x, anchor.y, anchor.z], "length_m": L, "status": "PROTOTYPE"},
		"labels": {"title": "EVA push-off on a clipped tether", "note": "tether length is the PROTOTYPE gameplay reach, stiffness and load OPEN; hard limit only; FLIGHT_EVA HOLD (SIMULATION_ONLY)"}}
	d.add_child(r)
	return r

## U04 headless: drive the guided session through real key events (the guide sees each one first), including a refused R before the
## tug test, and finish all ten steps on the scene's own state; prints one WF_GODOT_REVIEW line.
func check_review() -> void:
	var s: WfEvaSession = review.session
	var log := []
	var press := func(k: Key) -> void:
		var ev := InputEventKey.new()
		ev.keycode = k
		ev.pressed = true
		get_viewport().push_input(ev)
		var up := InputEventKey.new()
		up.keycode = k
		get_viewport().push_input(up)
	var wait_step := func(want: int, frames: int) -> bool:
		for f in frames:
			await get_tree().physics_frame
			if review.index >= want:
				return true
		return false
	var plan := [[KEY_ENTER, 1, 30], [KEY_ENTER, 2, 600], [KEY_F, 3, 30]]
	for p in plan:
		press.call(p[0])
		log.append({"key": OS.get_keycode_string(p[0]), "reached": await wait_step.call(p[1], p[2]), "index": review.index})
	await _review_shot("step_3")
	press.call(KEY_G)                                    # toward the rail anchor; grab as soon as the hand reaches something
	var grabbed := false
	for f in 900:
		await get_tree().physics_frame
		if s.can_grab():                                 # grab as early as a reviewer would, short of the anchor if need be
			press.call(KEY_H)
			grabbed = await wait_step.call(4, 5)
			break
	log.append({"key": "G,H", "reached": grabbed, "index": review.index, "grip": str(drift.body.grip.anchor_id) if drift and drift.body.grip else ""})
	var short := s.short_of_anchor()
	if short:                                            # hand over hand to the anchor (H again)
		press.call(KEY_H)
		await get_tree().physics_frame
	log.append({"key": "H (hand over hand)", "needed": short, "in_reach": not s.short_of_anchor()})
	press.call(KEY_T)
	log.append({"key": "T", "reached": await wait_step.call(5, 10), "index": review.index})
	press.call(KEY_R)                                    # refused: B is not tested yet
	await get_tree().physics_frame
	var refused := review.last_ok == false and drift.tethers.A != null and review.index == 5
	log.append({"key": "R (refused)", "refused": refused, "last": review.last_text})
	for p in [[KEY_Y, 6, 10], [KEY_R, 7, 10], [KEY_G, 8, 900], [KEY_F, 9, 10], [KEY_ENTER, 10, 600]]:
		press.call(p[0])
		log.append({"key": OS.get_keycode_string(p[0]), "reached": await wait_step.call(p[1], p[2]), "index": review.index, "last": review.last_text})
		await _review_shot("step_%d" % review.index)
	var out := {"session": "eva", "steps": review.events, "keys": log, "complete": review.complete, "refusal_shown": refused,
		"labels": range(s.steps.size()).map(func(i): return s.labels(i)), "phase_end": phase}
	out.labelled = range(s.steps.size()).all(func(i): return not s.labels(i).is_empty())
	out.result = "PASS" if review.complete and refused and out.labelled and phase == "DEBRIEF" else "FAIL"
	print("WF_GODOT_REVIEW " + JSON.stringify(out))
	get_tree().quit(0 if out.result == "PASS" else 1)

## --review-shots=<dir> with --check-review in a window: a still after the step (headless: nothing).
func _review_shot(name: String) -> void:
	var dir := ""
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--review-shots="):
			dir = a.trim_prefix("--review-shots=")
	if dir == "" or DisplayServer.get_name() == "headless":
		return
	for i in 4:
		await get_tree().process_frame
	DirAccess.make_dir_recursive_absolute(dir)
	get_viewport().get_texture().get_image().save_png(dir.path_join(name + ".png"))

func finish(out: Dictionary) -> void:
	print("WF_GODOT_EVA " + JSON.stringify(out))
	get_tree().quit(0 if out.get("result", "FAIL") == "PASS" else 1)
