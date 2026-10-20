extends Node3D
## Guided induction walk on the exported route graph (rig `induction_route`, IND-001 5.1-5.2).
## Presentation camera only: Godot reads the graph and computes no spacecraft facts or physics.
## RT-004: the rings turn in the COAST part of the walk, the camera rides the frame of the zone it is in (stationary trunk, transfer drum,
## ring), the drum despins and synchronizes with ring A, the rings spin up and down to their index, and the airlock hatches, the Q46
## closures and the sector leaves open and close as the camera passes. B switches the body pace: the review speed, rung by rung on the
## ladders, with the spin gravity and Coriolis push the moving body feels in the ring frame. The axes, pivots, rates and closure travels
## come from the export manifest (`induction.mechanisms`), the body data from the rig (`induction_route.body`); the timings and the
## sequence are display choices, not a transfer procedure, an interlock design or a body simulation.

const APPROACH_M := 3.0        # a closure opens when the camera is this close to its opening along the rail (display)
const CLOSURE_S := 2.0         # display travel time of a closure, closed to open
const SYNC_S := 4.0            # display spin-up / spin-down time of the drum (sync cycle OPEN, MEC-019)
const INSIDE_M := 0.8          # past the spine port by this much along the rail, the camera is inside the drum
const PACE := 1.5              # camera review pace, m/s; not a sourced crew transfer speed
const RING_RAMP_S := 20.0      # display spin-up / spin-down time of the rings (the real durations are OPEN, S4/S6/S7)

var camera := Camera3D.new()
var holder := Node3D.new()
var route: Dictionary
var manifest: Dictionary
var ship: Node3D
var points: Array[Vector3] = []
var ups: Array = []
var zones: Array[String] = []
var distances: Array[float] = []
var progress := 0.0
var look_offset := Vector2.ZERO
var stop_view := -1
var characters := {}
var manifest_ids := {}       # CHARACTER node -> its manifest component_id (the proxy part names)
var header := Label.new()
var station := Label.new()
var guide := Label.new()
var passing := Label.new()
var transfer := Label.new()
var distance_label := Label.new()
var slider := HSlider.new()
var stop_list := ItemList.new()
var dragging := false
var held_direction := 0.0
var free_flight := false
var collision := true
# RT-004 mechanisms: frame id -> {node, rest, axis, angle}; closure name -> {node, binding, value, target}; route openings with closures.
var frames := {}
var closures := {}
var openings: Array = []
var ring_id := ""
var drum_id := ""
var omega := 0.0
var drum_mode := "DESPUN"
var drum_t := 0.0
var drum_from := 0.0
var gate_rail := 0.0
var camera_frame := "STATIONARY"
var rings := {}                # rotor id -> {mode STOPPED / SPIN_UP / RUNNING / WAIT_DOWN / SPIN_DOWN, f (speed fraction), t, from}
var airlock_mid := 0.0
var body_mode := false
var rig_all: Dictionary
@export var demo_on_start := false   # Integrated Demonstrator 01 (scenes/demo01.tscn): start the chapter run (demo01.gd)
var demo: WfDemo01 = null
var help_label: Label = null
var bottom_panel: PanelContainer = null
var body_tour: WfBodyTour = null     # PHYS-001 phase 8: the crew-physics body (key N / --check-body); body_mode above is the review pace
var body_data: Dictionary
var ladders: Array = []
var body_label := Label.new()
var note_label: Label = null
var top_box: VBoxContainer = null
var side_panel: PanelContainer = null
var review: WfReviewGuide = null    # U01/U02: the development review guide, when a review session runs in this scene
var last_local := Vector3.ZERO
var last_angles := {}
var velocity := Vector3.ZERO
# RT-006: the induction ring's sector clear volumes (rig induction_route.rooms): oriented boxes at the index pose, in the ring frame.
var rooms: Array = []
const ROOM_MARGIN := 0.10       # the eye stays this far inside a clear volume (display choice)
# FUT-003 S004 look: a point light on each emitting surface of a light class (manifest records with `light`); only the nearest LAMP_MAX
# within LAMP_REACH_M of the camera are on (the Compatibility renderer lights each mesh with a few lights). L switches to the inspection light.
const LAMP_REACH_M := 14.0
const LAMP_MAX := 16
# M7.1 interior lighting: the 16 nearest unshadowed lamps washed the interiors toward white and flattened the production layer's value steps;
# each lamp's manifest energy is scaled by lamp_scale, 0.65 chosen from 1.0 / 0.65 / 0.45 captures (display exposure, not a lighting design;
# -- --lamp-energy=<f> overrides it; light count, range and draw calls unchanged). Lamp
# shadows were tried and rejected: in the Compatibility renderer they blew out and cast hard dual-paraboloid wedges, at +1.6-2.0 ms.
var lamp_scale := 0.65
const LAMP_PUSH_M := 6.0        # a light within this of the route rail is pushed toward it by its offset (into the passage it lights)
var lamps: Array = []
var look_lights := true
var lamp_t := 0.0
var inspection_light := OmniLight3D.new()
var world := WorldEnvironment.new()
const STANDING := ["aisle", "landing", "access strip", "couch strip", "niche"]

func vector(value: Array) -> Vector3:
	return Vector3(value[0], value[2], -value[1])

func _ready() -> void:
	var canvas := CanvasLayer.new()
	add_child(canvas)
	if not FileAccess.file_exists("res://generated/manifest_docked.json"):
		var missing := Label.new()
		missing.text = "Generate boarding data from the repository root:\npython3 tools/workflow.py runtime-export"
		missing.position = Vector2(32, 32)
		canvas.add_child(missing)
		return
	manifest = JSON.parse_string(FileAccess.get_file_as_string("res://generated/manifest_docked.json"))
	var rig = JSON.parse_string(FileAccess.get_file_as_string("res://generated/wf_sim_rig.json"))
	if manifest.preset != "DOCKED" or rig == null or not rig.has("induction_route") or not manifest.induction.has("mechanisms"):
		push_error("Boarding requires the DOCKED package with its mechanisms and the rig's induction route")
		return
	rig_all = rig
	route = rig.induction_route
	ship = load("res://generated/wayfarer_docked.glb").instantiate()
	add_child(ship)
	WfProductionLayer.apply(ship, manifest)   # M7: production detail drawn near the camera only
	var by_name := {}
	collect(ship, by_name)
	for record in manifest.nodes:
		if record.get("layer", "") == "CHARACTER" and by_name.has(record.node):
			characters[by_name[record.node]] = record.scene
			manifest_ids[by_name[record.node]] = record.get("component_id", "")
	build_mechanisms(by_name)
	swap_characters()
	body_data = route.body
	for leg in route.legs:
		ladders += leg.ladders
	for box in route.get("rooms", {}).get("boxes", []):
		rooms.append({"id": box.id, "kind": box.kind, "suited": box.suited_access, "c": vector(box.centre_m), "deck": vector(box.deck_m), "up": vector(box.up),
			"ax": [vector(box.axes[0]), vector(box.axes[1]), vector(box.axes[2])], "h": Vector3(box.half_m[0], box.half_m[1], box.half_m[2])})
	for waypoint in route.rail:
		points.append(vector(waypoint.position_m))
		distances.append(float(waypoint.rail_m))
		zones.append(str(waypoint.zone))
		ups.append(vector(waypoint.up) if waypoint.has("up") else null)
	add_child(holder)
	holder.add_child(camera)
	camera.current = true
	camera.near = 0.025
	camera.far = 1000.0
	# Inspection illumination, not an engineered light or power allocation.
	inspection_light.omni_range = 10.0
	camera.add_child(inspection_light)
	world.environment = Environment.new()
	world.environment.background_mode = Environment.BG_COLOR
	world.environment.background_color = Color("09121a")
	world.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	world.environment.ambient_light_color = Color("b6c8dc")
	add_child(world)
	build_lights(by_name)
	set_look(not manifest.has("look") or not lamps.is_empty())
	build_ui(canvas)
	go_to_stop(0)
	var demo_args := Array(OS.get_cmdline_user_args()).filter(func(a): return a in ["--demo", "--check-demo", "--autoplay"] or a.begins_with("--capture-demo="))
	if demo_on_start or not demo_args.is_empty():
		start_demo()
		demo.autoplay = "--autoplay" in demo_args       # replay: the chapters and the body actions run by themselves
	for arg in OS.get_cmdline_user_args():
		if arg == "--check-demo":
			check_demo()
		elif arg.begins_with("--capture-demo="):
			capture_demo(arg.trim_prefix("--capture-demo="))
		elif arg == "--inspection-light":
			set_look(false)
		elif arg.begins_with("--capture="):
			capture_stops(arg.trim_prefix("--capture="))
		elif arg == "--check-transfer":
			check_transfer()
		elif arg == "--check-body":
			check_body()
		elif arg == "--check-controls-body":
			check_controls_body()
		elif arg.begins_with("--capture-lesson="):
			capture_lesson(arg.trim_prefix("--capture-lesson="))
		elif arg.begins_with("--capture-body="):
			capture_body(arg.trim_prefix("--capture-body="))
		elif arg.begins_with("--capture-transfer="):
			capture_transfer(arg.trim_prefix("--capture-transfer="))
		elif arg.begins_with("--review="):
			WfReviewGuide.pending = arg.trim_prefix("--review=")
		elif arg.begins_with("--review-shots="):
			review_shots = arg.trim_prefix("--review-shots=")
	var review_name := WfReviewGuide.pending
	WfReviewGuide.pending = ""
	if "--check-review" in OS.get_cmdline_user_args():
		match review_name:
			"walk": check_walk_review()
			"demo01": check_demo_review()
			_: check_review()
	elif review_name != "":
		start_review(review_name)

func swap_characters() -> void:
	# CHAR-001: the MPFB induction pair (generated/characters, docs/CHARACTERS.md) replaces its proxies at each stage Blender staged it
	# (S004A greeting for both, S004B couch for the newcomer): the proxy's parts are hidden for good, the posed body joins the proxy's parent
	# at the exported vehicle-frame placement, so it rides the same ring frame and shows at the same stops. Without the export the proxies stay.
	var path := "res://generated/characters/characters.json"
	if not FileAccess.file_exists(path):
		return
	var records: Dictionary = (JSON.parse_string(FileAccess.get_file_as_string(path)) as Dictionary)["characters"]
	var swapped := {}
	for w in records:
		var rec: Dictionary = records[w]
		if not rec.has("stages"):
			continue
		for scene in rec["stages"]:
			var stage: Dictionary = rec["stages"][scene]
			var words := str(stage["proxy"]).split("_")         # instructor -> Instructor_*, S004B_newcomer -> S004B_Newcomer_*
			words[-1] = words[-1].capitalize()
			var prefix := "_".join(words) + "_"
			var parent: Node3D = null
			var hidden := 0
			for node in characters.keys():
				var id := str(manifest_ids.get(node, ""))
				if id.begins_with(prefix) and characters[node] == scene:
					parent = node.get_parent()
					node.visible = false
					characters.erase(node)
					hidden += 1
			if hidden == 0:
				push_error("CHAR-001: no %s* proxy parts for %s %s in the DOCKED export" % [prefix, w, scene])
				continue
			var body: Node3D = (load("res://generated/characters/" + str(rec["glb"])) as PackedScene).instantiate()
			parent.add_child(body)
			var pl: Dictionary = stage["placement_godot"]
			var c: Array = pl["basis_columns"]
			body.global_transform = Transform3D(Basis(Vector3(c[0][0], c[0][1], c[0][2]), Vector3(c[1][0], c[1][1], c[1][2]),
				Vector3(c[2][0], c[2][1], c[2][2])), Vector3(pl["origin"][0], pl["origin"][1], pl["origin"][2]))
			var player: AnimationPlayer = body.find_children("*", "AnimationPlayer", true, false)[0]
			player.play(stage["action"])
			player.seek(0.0, true)
			player.pause()
			characters[body] = scene
			swapped["%s %s" % [w, scene]] = hidden
	print("WF_BOARDING_CHARACTERS ", JSON.stringify(swapped))

func collect(node: Node, out: Dictionary) -> void:
	out[str(node.name)] = node
	for child in node.get_children():
		collect(child, out)

func build_mechanisms(by_name: Dictionary) -> void:
	# One pivot per ring and drum at its exported pivot; the meshes it carries (node `frame`) keep their placement when reparented.
	var mech: Dictionary = manifest.induction.mechanisms
	for group in ["rotors", "drums"]:
		for id in mech[group]:
			var b: Dictionary = mech[group][id]
			var pivot := Node3D.new()
			pivot.name = id
			pivot.position = Vector3(b.pivot_runtime_m[0], b.pivot_runtime_m[1], b.pivot_runtime_m[2])
			ship.add_child(pivot)
			var axis := Vector3(b.axis_runtime[0], b.axis_runtime[1], b.axis_runtime[2]).normalized()
			frames[id] = {"node": pivot, "rest": pivot.position, "axis": axis, "angle": 0.0, "rate": float(b.get("rad_per_s", 0.0))}
	frames["STATIONARY"] = {"node": ship, "rest": Vector3.ZERO, "axis": Vector3.RIGHT, "angle": 0.0, "rate": 0.0}
	var members := {}
	for record in manifest.nodes:
		if record.has("frame") and by_name.has(record.node):
			by_name[record.node].reparent(frames[record.frame].node, true)
		if record.has("closure"):
			members[record.closure] = members.get(record.closure, []) + [record.node]
	# A closure (its nodes, `closure`) turns about its own pivot and axis or slides, inside its frame; the snapshot shows it open.
	for name in mech.closures:
		var b: Dictionary = mech.closures[name]
		var f: Dictionary = frames[b.frame]
		var pivot := Node3D.new()
		pivot.name = name + "_Pivot"
		f.node.add_child(pivot)
		var base := Vector3.ZERO
		var axis := Vector3.ZERO
		if b.kind == "turn":
			base = Vector3(b.pivot_runtime_m[0], b.pivot_runtime_m[1], b.pivot_runtime_m[2]) - f.rest
			axis = Vector3(b.axis_runtime[0], b.axis_runtime[1], b.axis_runtime[2]).normalized()
		pivot.position = base
		for node_name in members.get(name, []):
			by_name[node_name].reparent(pivot, true)
		closures[name] = {"node": pivot, "binding": b, "axis": axis, "base": base, "value": 1.0, "target": 1.0}
	for id in mech.rotors:
		rings[id] = {"mode": "STOPPED", "f": 0.0, "t": 0.0, "from": 0.0}
	ring_id = route.frames.RING
	drum_id = route.frames.DRUM
	omega = frames[ring_id].rate
	var lock := []
	for leg in route.legs:
		for opening in leg.openings:
			if not opening.closures.is_empty():
				openings.append(opening)
				if opening.kind == "PORT_GATE":
					gate_rail = float(opening.rail_m)
				elif opening.kind.begins_with("AIRLOCK"):
					lock.append(float(opening.rail_m))
	airlock_mid = (lock.min() + lock.max()) / 2.0 if not lock.is_empty() else -1.0

func label(text: String, size: int = 16) -> Label:
	var out := Label.new()
	out.text = text
	out.add_theme_font_size_override("font_size", size)
	out.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return out

func button(text: String, action: Callable) -> Button:
	var out := Button.new()
	out.text = text
	out.focus_mode = Control.FOCUS_NONE
	out.pressed.connect(action)
	return out

func build_ui(canvas: CanvasLayer) -> void:
	var top := VBoxContainer.new()
	top_box = top
	top.position = Vector2(28, 20)
	canvas.add_child(top)
	top.add_child(label("WAYFARER  /  INDUCTION, RING A", 23))
	header.add_theme_font_size_override("font_size", 15)
	top.add_child(header)
	help_label = label("W / S: along the route   Stop list: stop view   Right-drag: look   R: reset view   Esc: inspector\nF: free flight (WASD, Q / E down / up, Shift faster, C: route envelope on / off; the rail, a stop or R returns)   B: body pace   N: physics body (PROTOTYPE stage)   L: S004 look / inspection light", 14)
	top.add_child(help_label)
	var side := PanelContainer.new()
	side_panel = side
	canvas.add_child(side)
	side.set_anchors_and_offsets_preset(Control.PRESET_TOP_RIGHT)
	side.offset_left = -330
	side.offset_right = -24
	side.offset_top = 20
	side.custom_minimum_size = Vector2(306, 0)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 10)
	side.add_child(column)
	column.add_child(label("  INDUCTION STOPS", 18))
	stop_list.custom_minimum_size = Vector2(306, 250)
	stop_list.focus_mode = Control.FOCUS_NONE
	for i in range(route.stops.size()):
		stop_list.add_item("%02d  %s" % [i + 1, route.stops[i].title.get_slice(":", 0)])
	stop_list.item_selected.connect(go_to_stop)
	column.add_child(stop_list)
	column.add_child(button("Return to ship inspector", leave))
	column.add_child(button("Integrated Demonstrator 01", func(): get_tree().change_scene_to_file("res://scenes/demo01.tscn")))
	# EVA-001: the guided exterior EVA, a labelled training simulation (godot/scripts/eva.gd)
	column.add_child(button("Guided EVA (training simulation)", func(): get_tree().change_scene_to_file("res://scenes/eva.tscn")))
	note_label = label("", 14)
	column.add_child(note_label)
	set_note()
	var panel := PanelContainer.new()
	bottom_panel = panel
	canvas.add_child(panel)
	panel.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_WIDE)
	panel.offset_left = 24
	panel.offset_right = -24
	panel.offset_top = -292
	panel.offset_bottom = -20
	var margin := MarginContainer.new()
	for edge in ["left", "top", "right", "bottom"]:
		margin.add_theme_constant_override("margin_" + edge, 14)
	panel.add_child(margin)
	var body := VBoxContainer.new()
	body.add_theme_constant_override("separation", 6)
	margin.add_child(body)
	station.add_theme_font_size_override("font_size", 20)
	body.add_child(station)
	guide.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	guide.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	body.add_child(guide)
	passing.add_theme_font_size_override("font_size", 14)
	body.add_child(passing)
	transfer.add_theme_font_size_override("font_size", 14)
	body.add_child(transfer)
	body_label.add_theme_font_size_override("font_size", 14)
	body.add_child(body_label)
	var row := HBoxContainer.new()
	body.add_child(row)
	for direction in [-1.0, 1.0]:
		var control := Button.new()
		control.text = "Hold to move back" if direction < 0 else "Hold to move forward"
		control.focus_mode = Control.FOCUS_NONE
		control.button_down.connect(func(): held_direction = direction)
		control.button_up.connect(func(): held_direction = 0.0)
		row.add_child(control)
	slider.min_value = 0
	slider.max_value = distances[-1]
	slider.step = 0.01
	slider.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	slider.focus_mode = Control.FOCUS_NONE
	slider.value_changed.connect(func(value: float): progress = value; stop_view = -1; settle(); update_camera())
	row.add_child(slider)
	row.add_child(distance_label)
	var sources := label("Sources: %s · %s, sequence %s · %s" % [", ".join(route.sources), route.geometry_status, route.sequence_status, route.limits], 12)
	sources.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	body.add_child(sources)

func go_to_stop(index: int) -> void:
	progress = float(route.stops[index].rail_m)
	stop_view = index
	look_offset = Vector2.ZERO
	settle()
	update_camera()

func leave() -> void:
	get_tree().change_scene_to_file("res://scenes/review.tscn" if review != null else "res://scenes/inspector.tscn")

## U01/U02: run a guided review session over this scene. The walk's own panels (help, stops, stop text, body HUD) are hidden while it
## runs; their engineering text stays reachable as the guide's muted detail line (I).
func start_review(name: String) -> void:
	if review != null or not name in ["ring_b", "walk", "demo01"]:
		return
	var s: WfReviewSession = {"ring_b": WfRingBSession, "walk": WfWalkSession, "demo01": WfDemoSession}[name].new(self)
	if name == "demo01" and demo == null:
		start_demo()
	review = WfReviewGuide.new(s)
	add_child(review)
	# The walk keeps its stop list (a control the reviewer may click); the help, stop text and body HUD become the detail line.
	for c in [top_box, bottom_panel] + ([] if name == "walk" else [side_panel]):
		if c != null:
			c.visible = false
	if demo != null:
		demo.hud.visible = false
		demo.auto_next = false                     # A autoplays the body actions only; the reviewer moves on with Enter
	ensure_body_tour().hud.visible = false

## U05 headless: walk the rail stop by stop (the walk's own move_along, as W does) until every step is done; one WF_GODOT_REVIEW line.
func check_walk_review() -> void:
	start_review("walk")
	var s: WfWalkSession = review.session
	var frames := 0
	while not review.complete and frames < 60 * 600:
		move_along(1.0 / 60.0 * PACE * 4.0)
		await get_tree().process_frame
		frames += 1
	_print_review("walk", s, {"progress_m": progress, "frames": frames})

## U05 headless: the demonstrator in autoplay; Enter is pressed (through the guide) whenever a chapter's goal is reached.
func check_demo_review() -> void:
	start_review("demo01")
	var s: WfDemoSession = review.session
	demo.autoplay = true
	var frames := 0
	var log := []
	while not review.complete and frames < 60 * 900:
		await get_tree().physics_frame
		frames += 1
		if demo.goal_done and demo.chapter < WfDemo01.CHAPTERS.size() - 1 and demo.t > 1.0:
			log.append({"chapter": WfDemo01.CHAPTERS[demo.chapter], "frames": frames})
			review.press(KEY_ENTER)                # the reviewer, not the autoplay, moves the chapter on
			await get_tree().physics_frame
			if host_body_chapter():
				body_tour.auto_descend = WfDemo01.CHAPTERS[demo.chapter] in ["TRANSFER", "DESCENT"]
	_print_review("demo01", s, {"chapters": log, "frames": frames})

func host_body_chapter() -> bool:
	return body_tour != null and body_tour.active

func _print_review(name: String, s: WfReviewSession, extra: Dictionary) -> void:
	var out := {"session": name, "steps": review.events, "complete": review.complete,
		"labels": range(s.steps.size()).map(func(i): return s.labels(i)), "details": s.details().length()}
	out.merge(extra)
	out.labelled = range(s.steps.size()).all(func(i): return not s.labels(i).is_empty())
	out.result = "PASS" if review.complete and out.labelled and out.details > 0 else "FAIL"
	print("WF_GODOT_REVIEW " + JSON.stringify(out))
	get_tree().quit(0 if out.result == "PASS" else 1)

## Headless (needs --fixed-fps 60): drives the Ring B session's steps through the scene's own controls and checks that the guide advances
## on each real event; prints one WF_GODOT_REVIEW line.
func check_review() -> void:
	start_review("ring_b")
	var s: WfRingBSession = review.session
	var out := {"session": "ring_b", "steps": []}
	var ok := true
	await _review_shot("step_0")
	toggle_body_tour()
	ok = ok and await _await_step(1, 120)
	body_tour.build_ring("RING_B", true, false)
	ok = ok and await _await_step(2, 120)
	var dirs := [Vector3.RIGHT, Vector3.LEFT]
	var turn := 0
	var stuck := 0
	var best := 0.0
	body_tour.auto_walk = dirs[0]
	for i in 1200:
		await get_tree().physics_frame
		if review.index >= 3:
			break
		stuck = 0 if s.walked > best + 1e-3 else stuck + 1
		best = maxf(best, s.walked)
		if stuck > 90:                         # a wall: turn round
			turn += 1
			body_tour.auto_walk = dirs[turn % 2]
			stuck = 0
	body_tour.auto_walk = Vector3.ZERO
	ok = ok and review.index >= 3
	await get_tree().physics_frame
	var refused := s.on_key(KEY_1, review.index)
	body_tour.drop_tool()
	ok = ok and await _await_step(4, 300)
	toggle_body_tour()
	ok = ok and await _await_step(5, 60)
	out.steps = review.events
	out.walked_m = s.walked
	out.deflection_m = s.landed
	out.refusal_shown = not refused.is_empty() and refused[1] == false
	out.complete = review.complete
	# every content step names the source status of what it shows, each a known status family (CANON .. HOLD)
	var labelled := true
	out.labels = []
	for i in 4:
		var lb := s.labels(i)
		out.labels.append(lb)
		labelled = labelled and not lb.is_empty() and lb.all(func(l): return WfReviewGuide.STATUS_COLORS.keys().any(func(k): return str(l[0]).to_upper().begins_with(k)))
	out.labelled = labelled
	out.result = "PASS" if ok and review.complete and out.refusal_shown and labelled and absf(s.landed) > 0.01 else "FAIL"
	print("WF_GODOT_REVIEW " + JSON.stringify(out))
	get_tree().quit(0 if out.result == "PASS" else 1)

func _await_step(want: int, frames_max: int) -> bool:
	for i in frames_max:
		await get_tree().process_frame
		if review.index >= want:
			await _review_shot("step_%d" % want)
			return true
	return false

var review_shots := ""                     # --review-shots=<dir> with --check-review in a window: a still after each completed step
func _review_shot(name: String) -> void:
	if review_shots == "" or DisplayServer.get_name() == "headless":
		return
	DirAccess.make_dir_recursive_absolute(review_shots)
	for i in 20:
		await get_tree().process_frame
	get_viewport().get_texture().get_image().save_png(review_shots.path_join(name + ".png"))

func _notification(what: int) -> void:
	if what == NOTIFICATION_APPLICATION_FOCUS_OUT:
		dragging = false
		held_direction = 0.0

func _unhandled_input(event: InputEvent) -> void:
	if points.is_empty():
		return
	# ACI-10: every key here is a registry action (walk.*, tour.body_mode, ui.cancel), matched through WfInput.key_of.
	var in_body := body_tour != null and body_tour.active
	var k := WfInput.key_of(event, ["body"] if in_body else ["walk"]) if WfInput.pressed(event) else KEY_NONE
	if in_body:
		if k == KEY_N:
			toggle_body_tour()
		elif k != KEY_ESCAPE and body_tour.handle_input(event):
			get_viewport().set_input_as_handled()
			return
		elif k != KEY_ESCAPE:
			return
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_RIGHT:
		dragging = event.pressed
	if event is InputEventMouseMotion and dragging and free_flight:
		camera.rotate_object_local(Vector3.UP, -event.relative.x * 0.004)
		camera.rotate_object_local(Vector3.RIGHT, -event.relative.y * 0.004)
	elif event is InputEventMouseMotion and dragging:
		look_offset.x -= event.relative.x * 0.004
		look_offset.y = clampf(look_offset.y - event.relative.y * 0.004, -1.4, 1.4)
		update_camera()
	if k != KEY_NONE:
		if k == KEY_ESCAPE:
			leave()
		elif k == KEY_R:
			look_offset = Vector2.ZERO
			update_camera()
		elif k == KEY_F and not free_flight:
			enter_free_flight()
		elif k == KEY_B:
			body_mode = not body_mode
			update_camera()
		elif k == KEY_N and not free_flight:
			toggle_body_tour()
		elif k == KEY_C and free_flight:
			collision = not collision
			enter_free_flight()
		elif k == KEY_L and not lamps.is_empty():
			set_look(not look_lights)

func _process(delta: float) -> void:
	if points.is_empty():
		return
	step_mechanisms(delta)
	if note_label != null:
		set_note()
	lamp_t += delta
	if lamp_t > 0.25:
		update_lamps()
	if not get_window().has_focus() or (body_tour != null and body_tour.active):
		return
	if free_flight:
		fly(delta)
		return
	# ACI-04: the rail walk reads the registry actions (WfInput; keyboard position W/S by default, left stick); the pace is unchanged.
	WfInput.context = "walk"
	if demo == null or not demo.autoplay:
		WfInput.discover("move_rail")
	var direction := held_direction + WfInput.strength("player.move_forward") - WfInput.strength("player.move_back")
	if direction != 0:
		var before := progress
		move_along(direction * delta * (float(body_data.review_speed_m_s) if body_mode else PACE))
		if progress > before and WfInput.strength("player.move_forward") > 0.0:
			WfInput.performed("player.move_forward")

func move_along(step: float) -> void:
	# The camera stops short of an opening whose closures are not fully open (by the envelope radius) until they are.
	var target := clampf(progress + step, 0.0, distances[-1])
	var margin := float(route.envelope.radius_m)
	for opening in openings:
		var at := float(opening.rail_m)
		if opening_open(opening) >= 0.999:
			continue
		if step > 0 and progress <= at - margin + 1e-6 and target > at - margin:
			target = maxf(progress, at - margin)
		elif step < 0 and progress >= at + margin - 1e-6 and target < at + margin:
			target = minf(progress, at + margin)
	progress = target
	stop_view = -1
	update_camera()

func opening_open(opening: Dictionary) -> float:
	var out := 1.0
	for name in opening.closures:
		out = minf(out, closures[name].value)
	return out

func stop_at(at: float) -> Dictionary:
	# The stop the camera is at or heading to: its operating state sets whether the rings turn.
	for stop in route.stops:
		if float(stop.rail_m) >= at - 0.01:
			return stop
	return route.stops[-1]

func rotating() -> bool:
	# The rings' target: turning when the stop the camera is at or heading to is in a rotating state.
	return stop_at(progress).state.habitat == "ROTATING"

func running() -> bool:
	return rings[ring_id].mode == "RUNNING"

func want_sync() -> bool:
	return rotating() and progress > gate_rail + INSIDE_M

func wrap_angle(angle: float) -> float:
	return fposmod(angle + PI, TAU) - PI

func drum_aligned() -> bool:
	# The drum's openings face ring A's tubes: synchronized with the ring at full speed, or both at rest at the index.
	var together := absf(wrap_angle(frames[drum_id].angle - frames[ring_id].angle)) < 1e-3
	return together and ((drum_mode == "SYNCED" and running()) or (rings[ring_id].mode == "STOPPED" and drum_mode == "DESPUN"))

func closed(kind: String) -> bool:
	for opening in openings:
		if opening.kind == kind and opening_open(opening) > 0.0:
			return false
	return true

func safe(opening: Dictionary) -> bool:
	# What a closure may never break: the port gate only with the drum despun at rest at the index, a drum door and its tube hatch only
	# with the drum lined up with ring A, the airlock's hatches never both open. A sector leaf has no condition here.
	match str(opening.kind):
		"PORT_GATE":
			return drum_mode == "DESPUN" and absf(wrap_angle(frames[drum_id].angle)) < 1e-6
		"DRUM_DOOR_TUBE_HATCH":
			return drum_aligned()
		"AIRLOCK_OUTER":
			return closed("AIRLOCK_INNER")
		"AIRLOCK_INNER":
			return closed("AIRLOCK_OUTER")
	return true

func allowed(opening: Dictionary) -> bool:
	# Safe, and the sequence: the gate only until the camera is inside the drum, a door and hatch not while the drum is to despin for the
	# way back to the spine, the airlock's outer hatch from the outer half of the chamber and its inner hatch from the inner half.
	if not safe(opening):
		return false
	if demo != null and not demo.vestibule_allows(opening):
		return false
	match str(opening.kind):
		"PORT_GATE":
			return progress <= gate_rail + INSIDE_M
		"DRUM_DOOR_TUBE_HATCH":
			return want_sync() or not rotating()
		"AIRLOCK_OUTER":
			return progress < airlock_mid
		"AIRLOCK_INNER":
			return progress >= airlock_mid
	return true

func closure_targets() -> void:
	for name in closures:
		closures[name].target = 0.0
	for opening in openings:
		if absf(progress - float(opening.rail_m)) <= APPROACH_M and allowed(opening):
			for name in opening.closures:
				closures[name].target = 1.0

func settle() -> void:
	# After a jump (stop list, slider): the mechanisms take their steady state for the new place at once (no ramps or waits).
	for id in rings:
		if demo != null:
			break
		var r: Dictionary = rings[id]
		r.mode = "RUNNING" if rotating() else "STOPPED"
		r.f = 1.0 if rotating() else 0.0
		if not rotating():
			frames[id].angle = 0.0
	drum_mode = "SYNCED" if want_sync() else "DESPUN"
	frames[drum_id].angle = frames[ring_id].angle if drum_mode == "SYNCED" else 0.0
	for pass_ in range(2):          # the airlock's second hatch may open only once the first is shut
		closure_targets()
		for name in closures:
			closures[name].value = closures[name].target
	apply_mechanisms()

func crossed(before: float, after: float) -> bool:
	# A ramp may start when the angle plus half the ramp's turn passes a whole revolution: a constant-rate ramp then ends exactly at the
	# index (spin-down) or, for the drum, meets the tubes at full speed (spin-up).
	return floor(before / TAU) != floor(after / TAU)

func step_rings(delta: float) -> void:
	# The rings spin up to their exported rate and spin down to rest at their index, each in RING_RAMP_S (display).
	for id in rings:
		var r: Dictionary = rings[id]
		var f: Dictionary = frames[id]
		var w: float = f.rate
		if demo != null:
			# Demonstrator 01: the rings follow the operating-mode controller (DOCKED stopped and locked; DOCKED -> COAST ramp), not the stop.
			r.f = demo.ring_frac()
			r.mode = "RUNNING" if r.f >= 1.0 else ("STOPPED" if r.f <= 0.0 else "SPIN_UP")
			if r.mode != "STOPPED":
				f.angle = fposmod(f.angle + w * r.f * delta, TAU)
			continue
		match str(r.mode):
			"STOPPED":
				if rotating():
					r.mode = "SPIN_UP"
					r.t = 0.0
			"SPIN_UP":
				r.t += delta
				r.f = minf(r.t / RING_RAMP_S, 1.0)
				if r.f >= 1.0:
					r.mode = "RUNNING"
			"RUNNING":
				if not rotating():
					r.mode = "WAIT_DOWN"
			"WAIT_DOWN":
				if rotating():
					r.mode = "RUNNING"
				elif crossed(f.angle + w * RING_RAMP_S / 2.0, f.angle + w * delta + w * RING_RAMP_S / 2.0):
					r.mode = "SPIN_DOWN"
					r.t = 0.0
					r.from = f.angle
		if r.mode == "SPIN_DOWN":
			r.t += delta
			var tt := minf(r.t, RING_RAMP_S)
			f.angle = r.from + w * tt - 0.5 * w / RING_RAMP_S * tt * tt
			r.f = 1.0 - tt / RING_RAMP_S
			if r.t >= RING_RAMP_S:
				r.mode = "STOPPED"
				r.f = 0.0
				f.angle = 0.0
		elif r.mode != "STOPPED":
			f.angle = fposmod(f.angle + w * r.f * delta, TAU)

func step_mechanisms(delta: float) -> void:
	var ring: Dictionary = frames[ring_id]
	var before: float = ring.angle + omega * SYNC_S / 2.0
	var full := running()
	step_rings(delta)
	var after: float = before + (omega * delta if full else 0.0)
	var drum: Dictionary = frames[drum_id]
	var closed_ring := closures_closed(drum_id) and closures_closed(ring_id)
	match drum_mode:
		"DESPUN":
			if want_sync() and closed("PORT_GATE"):
				drum_mode = "WAIT_UP"
		"WAIT_UP":
			if not want_sync():
				drum_mode = "DESPUN"
			elif full and running() and crossed(before, after) and (demo == null or demo.vestibule_sync("RING")):
				drum_mode = "SPIN_UP"
				drum_t = 0.0
		"SPIN_UP":
			drum_t += delta
			drum.angle = 0.5 * omega / SYNC_S * minf(drum_t, SYNC_S) ** 2
			if drum_t >= SYNC_S:
				drum_mode = "SYNCED"
		"SYNCED":
			if not want_sync() and closed_ring:
				drum_mode = "WAIT_DOWN"
		"WAIT_DOWN":
			if want_sync():
				drum_mode = "SYNCED"
			elif full and crossed(before, after) and (demo == null or demo.vestibule_sync("STATIONARY")):
				drum_mode = "SPIN_DOWN"
				drum_t = 0.0
				drum_from = ring.angle
		"SPIN_DOWN":
			drum_t += delta
			var t := minf(drum_t, SYNC_S)
			drum.angle = drum_from + omega * t - 0.5 * omega / SYNC_S * t * t
			if drum_t >= SYNC_S:
				drum_mode = "DESPUN"
				drum.angle = 0.0
	if drum_mode in ["SYNCED", "WAIT_DOWN"]:
		drum.angle = ring.angle
	closure_targets()
	for name in closures:
		var c: Dictionary = closures[name]
		c.value = move_toward(c.value, c.target, delta / CLOSURE_S)
	if demo != null:
		demo.vestibule_follow(delta)
	apply_mechanisms()
	# The camera's velocity in its frame (index-pose coordinates) for the body readout.
	if delta > 0.0:
		velocity = (camera.position - last_local) / delta
		for id in frames:
			frames[id]["spin"] = wrap_angle(frames[id].angle - last_angles.get(id, frames[id].angle)) / delta
	last_local = camera.position
	for id in frames:
		last_angles[id] = frames[id].angle
	transfer.text = transfer_text()
	body_label.text = body_text()

func closures_closed(frame: String) -> bool:
	for name in closures:
		if closures[name].binding.frame == frame and closures[name].value > 0.0:
			return false
	return true

func apply_mechanisms() -> void:
	for id in frames:
		if id != "STATIONARY":
			frames[id].node.basis = Basis(frames[id].axis, frames[id].angle)
	for name in closures:
		var c: Dictionary = closures[name]
		var b: Dictionary = c.binding
		if b.kind == "slide":
			var d: Array = b.closed_offset_runtime_m
			c.node.position = c.base + Vector3(d[0], d[1], d[2]) * (1.0 - c.value)
		else:
			c.node.basis = Basis(c.axis, float(b.closed_angle_rad) * (1.0 - c.value))
	# The camera holder sits in the frame of the camera's zone, offset so that it carries the rail's index-pose coordinates.
	var f: Dictionary = frames[camera_frame]
	if holder.get_parent() != f.node:
		holder.reparent(f.node, false)
	holder.transform = Transform3D(Basis.IDENTITY, -f.rest)

func ladder_at(at: float) -> Dictionary:
	for ladder in ladders:
		if at >= float(ladder.rail_m[0]) - 1e-6 and at <= float(ladder.rail_m[1]) + 1e-6:
			return ladder
	return {}

func body_state(at: Vector3, v: Vector3) -> Dictionary:
	# What a body moving at v (m/s, index-pose coordinates) feels at `at` in the camera's frame: spin gravity w^2 r away from the axis and
	# the Coriolis acceleration -2 w x v, in g, and their components toward the ladder on a crew-tube ladder. Kinematics of the exported
	# spin, shown for presentation.
	var f: Dictionary = frames[camera_frame]
	var g0 := float(body_data.standard_gravity_m_s2)
	var axis: Vector3 = f.axis
	var rest: Vector3 = f.rest
	var w: Vector3 = axis * float(f.get("spin", 0.0)) if camera_frame != "STATIONARY" else Vector3.ZERO
	var ladder := ladder_at(progress)
	var n := vector(ladder.toward_ladder) if ladder.has("toward_ladder") else Vector3.ZERO
	var r := at + n * float(body_data.climber_offset_m) - rest       # on a ladder, the climber's body beside the rail
	var radial := r - axis * r.dot(axis)
	var spin: Vector3 = radial * w.length_squared() / g0
	var coriolis: Vector3 = -2.0 * w.cross(v) / g0
	var out := {"spin_g": spin.length(), "coriolis_g": coriolis.length(), "spin": spin, "coriolis": coriolis}
	if ladder.has("toward_ladder"):
		out["lean_g"] = spin.dot(n)
		out["coriolis_across_g"] = coriolis.dot(n)
	return out

func set_note() -> void:
	var tour_on := body_tour != null and body_tour.active
	note_label.text = "Camera study · %s\nRings, drum and closures: display sequence\n%s" % [route.geometry_status,
		"Physics body mode active\n(SIMULATION_ONLY)" if tour_on else "No movement physics"]

func body_text() -> String:
	if body_tour != null and body_tour.active:
		return "Body: physics body mode active (SIMULATION_ONLY), the review camera and pace are off · N returns to the review rail"
	var s: Dictionary = body_state(camera.position, velocity)
	var speed := velocity.length()
	var pace := ("body pace %.2f m/s, rung by rung on the ladders" % float(body_data.review_speed_m_s)) if body_mode else "camera pace (B: body pace)"
	if camera_frame == "STATIONARY" or s.spin_g < 1e-4:
		return "Body: weightless in a frame that does not turn · %s" % pace
	var text := "Body: spin gravity %.3f g, away from the axis · moving %.2f m/s: Coriolis %.3f g" % [s.spin_g, speed, s.coriolis_g]
	if s.has("lean_g"):
		var across: float = s.lean_g + s.coriolis_across_g
		text += " · across the ladder %s %.3f g (lean %.3f, Coriolis %+.3f)" % ["onto the rungs" if across >= 0.0 else "off the rungs", absf(across), s.lean_g, s.coriolis_across_g]
	return text + " · " + pace

func transfer_text() -> String:
	var ring: Dictionary = frames[ring_id]
	var spin: String = {"STOPPED": "rings stopped and locked at the index", "SPIN_UP": "rings spinning up (%.0f%% of full speed)" % (100.0 * rings[ring_id].f),
		"RUNNING": "ring A turning at %.1f rpm, %.0f° from the index" % [absf(omega) * 60.0 / TAU, rad_to_deg(fposmod(ring.angle, TAU))],
		"WAIT_DOWN": "rings at speed, waiting to spin down onto the index", "SPIN_DOWN": "rings spinning down onto the index (%.0f%%)" % (100.0 * rings[ring_id].f)}[rings[ring_id].mode]
	var drum: String = {"DESPUN": "despun at the index", "WAIT_UP": "despun, waiting for ring A at speed and for tube 1 to come round",
		"SPIN_UP": "spinning up to meet the tubes", "SYNCED": "synchronized with ring A",
		"WAIT_DOWN": "synchronized, waiting to despin onto the spine port", "SPIN_DOWN": "despinning onto the spine port"}[drum_mode]
	var shut: Array[String] = []
	for opening in openings:
		if absf(progress - float(opening.rail_m)) <= APPROACH_M + 1.0:
			var v := opening_open(opening)
			var what: String = {"AIRLOCK_OUTER": "outer hatch", "AIRLOCK_INNER": "inner hatch", "PORT_GATE": "spine-port gate",
				"DRUM_DOOR_TUBE_HATCH": "drum door and tube hatch %s" % str(opening.id).get_slice(".", 2),
				"SECTOR_LEAF": "sector hatch leaf %s" % str(opening.id).get_slice(".", 2)}[str(opening.kind)]
			shut.append("%s %s" % [what, "open" if v >= 0.999 else ("closed" if v <= 0.001 else "moving")])
	return "Mechanisms (display sequence): %s · drum: %s%s" % [spin, drum, (" · " + ", ".join(shut)) if not shut.is_empty() else ""]

func current_stop() -> int:
	var index := 0
	for i in range(route.stops.size()):
		if progress >= float(route.stops[i].rail_m) - 0.01:
			index = i
	return index

func segment_at(at: float) -> int:
	var segment := 1
	while segment < distances.size() - 1 and distances[segment] <= at:
		segment += 1
	return segment

func frame_of(zone: String) -> String:
	var kind: String = route.frames.zones[zone]
	return "STATIONARY" if kind == "STATIONARY" else str(route.frames[kind])

func coincide(a: String, b: String) -> bool:
	return absf(wrap_angle(frames[a].angle - frames[b].angle)) < 1e-4

func enter_free_flight() -> void:
	# RT-004: free flight in the DOCKED snapshot from the current view. With the route envelope on, the camera stays within the rig's
	# envelope radius of the rail (the suited sweep the route checks keep clear), so it passes every opening the route passes; while the
	# frames are apart (the rings turning), only along the rail of its own frame.
	free_flight = true
	camera.keep_aspect = Camera3D.KEEP_HEIGHT
	camera.fov = 75.0
	header.text = "FREE FLIGHT · %s" % ("rings turning; the camera rides the %s frame" % camera_frame if rotating() else "rings stopped at the index angle")
	if collision:
		guide.text = "Free flight inside the route envelope: the camera stays within %.2f m of the rail, the suited body's swept envelope (%s), or, in a sector, inside its clear volumes (aisle, strips, berths, Seraph's niche; B holds the eye at eye height over the deck). C turns it off. No pressure. Choose a stop, move the rail or press R to return to the route." % [route.envelope.radius_m, route.envelope.status]
	else:
		guide.text = "Free flight without the envelope: the camera passes through walls and closed volumes. C turns the route envelope back on. Choose a stop, move the rail or press R to return to the route."
	passing.text = ""

func room_at(at: Vector3) -> int:
	# RT-006: the clear volume holding a point (ROOM_MARGIN inside its walls), or -1; only while the camera rides the ring frame or the frames coincide.
	if rooms.is_empty() or not coincide(str(route.frames.RING), camera_frame):
		return -1
	for i in range(rooms.size()):
		var r: Dictionary = rooms[i]
		var d: Vector3 = at - r.c
		var h: Vector3 = r.h
		if absf(d.dot(r.ax[0])) <= h.x - ROOM_MARGIN and absf(d.dot(r.ax[1])) <= h.y - ROOM_MARGIN and absf(d.dot(r.ax[2])) <= h.z - ROOM_MARGIN:
			return i
	return -1

func held(at: Vector3) -> Vector3:
	# RT-006, body pace in a room: the walking body's eye at eye height over the deck of the standing volume it is in (a berth holds no standing body).
	var i := room_at(at)
	if i < 0 or not body_mode or not str(rooms[i].kind) in STANDING:
		return at
	var r: Dictionary = rooms[i]
	var up: Vector3 = r.up
	return at - up * ((at - r.deck).dot(up) - float(route.rooms.eye_height_m))

func move_free(step: Vector3) -> void:
	var target: Vector3 = camera.position + step
	if collision and room_at(camera.position) >= 0 or collision and room_at(target) >= 0:
		# RT-006: off the rail in a sector, the eye moves within the union of the clear volumes and the route envelope, never through a wall.
		var on_rail := target.distance_to(nearest_on_rail(target)) <= float(route.envelope.radius_m)
		var t2 := held(target)
		if room_at(t2) >= 0 or on_rail:
			camera.position = t2 if room_at(t2) >= 0 else target
		return
	if collision:
		# Slide on the envelope: never farther from the rail than its radius, or than a stop view that starts outside it.
		var limit := maxf(float(route.envelope.radius_m), camera.position.distance_to(nearest_on_rail(camera.position)))
		var c := nearest_on_rail(target)
		if target.distance_to(c) > limit:
			target = c + (target - c).normalized() * limit
	camera.position = target

func nearest_on_rail(at: Vector3) -> Vector3:
	# Only rail segments whose frame lies where the camera's frame lies (all of them with the rings stopped).
	var best := points[0]
	var best_distance := INF
	for i in range(1, points.size()):
		if not coincide(frame_of(zones[i]), camera_frame):
			continue
		var a: Vector3 = points[i - 1]
		var ab: Vector3 = points[i] - a
		var t := clampf((at - a).dot(ab) / maxf(ab.length_squared(), 1e-9), 0.0, 1.0)
		var c := a + ab * t
		if at.distance_squared_to(c) < best_distance:
			best_distance = at.distance_squared_to(c)
			best = c
	return best

func fly(delta: float) -> void:
	if held_direction != 0.0:
		update_camera()
		return
	var move := Vector3.ZERO
	move.z -= WfInput.strength("player.move_forward") - WfInput.strength("player.move_back")
	move.x += WfInput.strength("player.move_right") - WfInput.strength("player.move_left")
	move.y += WfInput.strength("walk.fly_up") - WfInput.strength("walk.fly_down")
	if move != Vector3.ZERO:
		# Camera review pace (the rail's), ×8 with Shift to cross the ship; not a crew or EVA speed.
		var pace := PACE * (8.0 if WfInput.held("player.fast") else 1.0)
		move_free(camera.basis * move.normalized() * pace * delta)
		distance_label.text = "free · X %.1f  Y %.1f  Z %.1f m" % [camera.position.x, -camera.position.z, camera.position.y]

func shown_progress() -> float:
	# Body pace on a ladder: the eye rises or sinks rung by rung (one rung pitch per step, eased), pausing between steps.
	var ladder := ladder_at(progress)
	if not body_mode or ladder.is_empty():
		return progress
	var pitch := float(body_data.rung_pitch_m)
	var start := float(ladder.rail_m[0])
	var u := (progress - start) / pitch
	return minf(start + pitch * (floor(u) + smoothstep(0.3, 0.7, u - floor(u))), float(ladder.rail_m[1]))

func place(eye: Vector3, forward: Vector3, up: Vector3) -> void:
	# The camera's pose in index-pose coordinates, local to its holder (which carries it with its frame).
	camera.transform = Transform3D(Basis.looking_at(forward, up), eye)

func update_camera() -> void:
	free_flight = false
	camera_frame = frame_of(zones[segment_at(float(route.stops[stop_view].rail_m) if stop_view >= 0 else progress)])
	apply_mechanisms()
	if stop_view >= 0:
		# The stop's eye-level view, as in the Blender stills (horizontal field of view).
		var view: Dictionary = route.stops[stop_view].view
		camera.keep_aspect = Camera3D.KEEP_WIDTH
		camera.fov = float(view.horizontal_fov_deg)
		place(vector(view.eye_m), vector(view.look), vector(view.up))
	else:
		var shown := shown_progress()
		var segment := segment_at(shown)
		var span := maxf(distances[segment] - distances[segment - 1], 1e-6)
		var t := clampf((shown - distances[segment - 1]) / span, 0.0, 1.0)
		camera.keep_aspect = Camera3D.KEEP_HEIGHT
		camera.fov = 75.0
		var forward := (points[segment] - points[segment - 1]).normalized()
		var up: Vector3 = ups[segment] if ups[segment] != null else (Vector3.RIGHT if absf(forward.dot(Vector3.UP)) > 0.9 else Vector3.UP)
		if absf(forward.dot(up)) > 0.98:
			up = Vector3.RIGHT if absf(forward.dot(Vector3.RIGHT)) < 0.9 else Vector3.UP
		place(points[segment - 1].lerp(points[segment], t), forward, up)
	camera.rotate_object_local(Vector3.UP, look_offset.x)
	camera.rotate_object_local(Vector3.RIGHT, look_offset.y)
	update_lamps()
	var index := stop_view if stop_view >= 0 else current_stop()
	var stop: Dictionary = route.stops[index]
	stop_list.select(index)
	for node in characters:
		node.visible = characters[node] in stop.scenes
	var state: Dictionary = stop_at(progress).state
	var spin := ("rings rotating at %.0f rpm, %.2f g at the deck" % [state.ring_rpm, state.spin_g]
		if state.habitat == "ROTATING" else "rings stopped and locked, microgravity")
	header.text = "%s · %s" % [state.configuration, spin]
	station.text = "%02d  %s  (%s)" % [index + 1, stop.title, ", ".join(stop.scenes)]
	var step := ""
	for item in route.sequence:
		if item.id == state.step:
			step = item.title
	guide.text = "Operating state %s: %s.\nView: %s." % [state.configuration, step, stop.view.role if stop_view >= 0 else "on the route rail"]
	passing.text = passing_text()
	slider.set_value_no_signal(progress)
	distance_label.text = "%05.1f / %.1f m" % [progress, distances[-1]]

func passing_text() -> String:
	# Ladders and openings of the route graph at the camera's rail position (exported spans, no geometry here).
	var out: Array[String] = []
	for leg in route.legs:
		if progress < float(leg.rail_m[0]) - 0.01 or progress > float(leg.rail_m[1]) + 0.01:
			continue
		for ladder in leg.ladders:
			if progress >= float(ladder.rail_m[0]) - 0.01 and progress <= float(ladder.rail_m[1]) + 0.01:
				out.append("%s: %s, %d rungs" % [ladder.id, ladder.kind, int(ladder.rungs)])
		for opening in leg.openings:
			if absf(progress - float(opening.rail_m)) < 1.0:
				out.append("%s: %s" % [opening.id, opening.closure])
		return "Leg %s (%s to %s)%s" % [leg.id, leg.from, leg.to, (" · " + " · ".join(out)) if not out.is_empty() else ""]
	return ""

func check_transfer() -> void:
	# RT-004 validation, headless: walk the whole rail from the outer hatch to the burn station and back at the camera pace in fixed steps and
	# require that the camera is never inside an opening's band (the envelope radius either side) unless its closures are fully open, that no
	# closure is open outside its safe state (safe()), that the camera changes frame only where the two frames coincide, and that both walks
	# finish; then that the rings come to rest at their index. Then the body readout on ring A's first tube ladder against the rig's
	# ladder_push (human_entry.ladder_push): the lean toward the ladder, the Coriolis push per m/s and the direction that pulls a climber off.
	var dt := 1.0 / 30.0
	var margin := float(route.envelope.radius_m)
	go_to_stop(0)
	progress = 0.0
	stop_view = -1
	settle()
	update_camera()          # from the rail, not the stop's eye view
	var report := []
	for direction in [1.0, -1.0]:
		var goal := distances[-1] if direction > 0 else 0.0
		var time := 0.0
		var waited := 0.0
		var frame := camera_frame
		var last := camera.position
		while absf(progress - goal) > 1e-6:
			step_mechanisms(dt)
			var before := progress
			move_along(direction * dt * PACE)
			time += dt
			if absf(progress - before) < dt * PACE * 0.5:
				waited += dt
			for opening in openings:
				var v := opening_open(opening)
				if absf(progress - float(opening.rail_m)) < margin - 1e-6 and v < 0.999:
					return fail_check("inside %s at %.2f m while it is %.2f open" % [opening.id, progress, v])
				if v > 0.0 and not safe(opening):
					return fail_check("%s open (%.2f) at %.2f m outside its safe state (drum %s, rings %s)" % [opening.id, v, progress, drum_mode, rings[ring_id].mode])
			if camera_frame != frame:
				if not coincide(frame, camera_frame):
					return fail_check("frame change %s -> %s at %.2f m while they are apart" % [frame, camera_frame, progress])
				frame = camera_frame
			elif camera.position.distance_to(last) > dt * PACE * 1.5 + 0.02:
				return fail_check("camera jumped %.3f m at %.2f m" % [camera.position.distance_to(last), progress])
			last = camera.position
			if time > 900.0:
				return fail_check("the walk did not finish in 900 s (at %.2f m, drum %s, rings %s)" % [progress, drum_mode, rings[ring_id].mode])
		report.append("%s %.1f s (waited %.1f s)" % ["forward" if direction > 0 else "back", time, waited])
	var rest := 0.0
	while rings.values().any(func(r): return r.mode != "STOPPED") and rest < 120.0:
		step_mechanisms(dt)
		rest += dt
	for id in rings:
		if rings[id].mode != "STOPPED" or absf(wrap_angle(frames[id].angle)) > 1e-6:
			return fail_check("%s did not come to rest at its index (%s, %.4f rad)" % [id, rings[id].mode, frames[id].angle])
	# Body readout on the first crew-tube ladder of the route, ring A at full speed, at the rig's review speed both ways along the run.
	var ladder: Dictionary = ladders.filter(func(l): return l.has("toward_ladder"))[0]
	progress = (float(ladder.rail_m[0]) + float(ladder.rail_m[1])) / 2.0
	settle()
	update_camera()
	step_mechanisms(dt)
	step_mechanisms(dt)
	var segment := segment_at(progress)
	var along := (points[segment] - points[segment - 1]).normalized()
	var f: Dictionary = frames[camera_frame]
	var axis: Vector3 = f.axis
	var rest_point: Vector3 = f.rest
	var out_from_axis := (points[segment] - rest_point) - axis * (points[segment] - rest_point).dot(axis)
	var inward := -along if along.dot(out_from_axis) > 0.0 else along
	var push: Dictionary = body_data.ladder_push
	var speed := float(push.review_speed_m_s)
	var climb: Dictionary = body_state(camera.position, inward * speed)
	var descend: Dictionary = body_state(camera.position, -inward * speed)
	var per := absf(climb.coriolis_across_g) / speed
	if absf(per / float(push.coriolis_g_per_m_s) - 1.0) > 0.02:
		return fail_check("Coriolis push %.4f g per m/s, the rig says %.4f" % [per, push.coriolis_g_per_m_s])
	if absf(climb.lean_g / float(push.lean_toward_ladder_g) - 1.0) > 0.10:
		return fail_check("lean toward the ladder %.4f g, the rig says %.4f" % [climb.lean_g, push.lean_toward_ladder_g])
	var off := "climbing" if climb.lean_g + climb.coriolis_across_g < descend.lean_g + descend.coriolis_across_g else "descending"
	if off != str(push.pulled_off_when):
		return fail_check("the push pulls a climber off when %s, the rig says %s" % [off, push.pulled_off_when])
	report.append("rings at rest after %.1f s" % rest)
	# RT-006: with the rings at their index, each room's centre is held (free flight), a step down through its deck and one out through its
	# side walls are refused, and with the body the eye stands at eye height over a standing room's deck.
	var held_rooms := 0
	var was := body_mode
	for r in rooms:
		camera_frame = str(route.frames.RING)
		body_mode = false
		camera.position = r.c
		if room_at(r.c) < 0:
			return fail_check("room %s centre is not inside its clear volume" % r.id)
		for out in [-r.up * (r.h.y + 0.3), r.ax[2] * (r.h.z + 0.3), -r.ax[2] * (r.h.z + 0.3)]:
			camera.position = r.c
			move_free(out)
			if room_at(camera.position) < 0 and camera.position.distance_to(nearest_on_rail(camera.position)) > float(route.envelope.radius_m) + 1e-6:
				return fail_check("room %s let the eye out to %s" % [r.id, camera.position])
		if str(r.kind) in STANDING and float(route.rooms.eye_height_m) + ROOM_MARGIN <= 2.0 * r.h.y:
			body_mode = true
			camera.position = r.c
			move_free(Vector3.ZERO)
			var height: float = (camera.position - r.deck).dot(r.up)
			if room_at(camera.position) >= 0 and absf(height - float(route.rooms.eye_height_m)) > 1e-3:
				return fail_check("room %s body eye at %.3f m over the deck" % [r.id, height])
		held_rooms += 1
	body_mode = was
	report.append("rooms %d held" % held_rooms)
	report.append("ladder %s: lean %.3f g, Coriolis %.4f g per m/s, pulled off when %s" % [ladder.id, climb.lean_g, per, off])
	print("WF_TRANSFER_CHECK PASS rail=%.1f m %s closures=%d frames=%d" % [distances[-1], ", ".join(report), closures.size(), frames.size()])
	get_tree().quit(0)

func start_demo() -> void:
	# Integrated Demonstrator 01: the chapter run over the walk, the body tour and the mode controller (demo01.gd).
	if demo == null:
		demo = WfDemo01.new()
		add_child(demo)
		demo.setup(self)
		demo.begin(demo.first_chapter())

func check_demo() -> void:
	# Headless (needs --fixed-fps 60): all six chapters in autoplay; prints one WF_GODOT_DEMO line.
	var out: Dictionary = await demo.run_check()
	print("WF_GODOT_DEMO " + JSON.stringify(out))
	get_tree().quit(0 if out.result == "PASS" else 1)

func capture_demo(directory: String) -> void:
	await demo.capture(directory)
	get_tree().quit()

func ensure_body_tour() -> WfBodyTour:
	if body_tour == null:
		body_tour = WfBodyTour.new()
		add_child(body_tour)
		body_tour.setup(rig_all)
		body_tour.hud.position = Vector2(12, 142)
		body_tour.ring_pivot = frames[ring_id].node
		if frames.has("WF.ROTOR.2"):
			body_tour.ring_pivots["RING_B"] = frames["WF.ROTOR.2"].node     # J01: the ring B beat's proxy turns with ring B
		body_tour.ring_angle_fn = func(): return float(frames[ring_id].angle)
		body_tour.ring_rate_fn = func(): return float(frames[ring_id].rate)
		body_tour.beat_changed.connect(tour_beat)
		body_tour.lamp.light_energy = inspection_light.light_energy
	return body_tour

func tour_beat(key: String) -> void:
	# The body tour's beat puts the review state to the matching stop: the spine stop (DOCKED, rings stopped and locked at the index) or the
	# habitat stop (COAST, rings at full speed at once: the physics field of the ring beat has no ramp). The ship stays visible around the body.
	for index in range(route.stops.size()):
		if route.stops[index].key == key:
			go_to_stop(index)
			return

func toggle_body_tour() -> void:
	# Body mode: the visitor / instructor body moves by the crew physics on the real trunk and A1 aisle (rig dynamics.stages) in the visible
	# ship. It is separate from the review camera (B: body pace, F: free flight), which stays a review tool and not a crew capability.
	var tour := ensure_body_tour()
	if tour.active:
		tour.leave()
		camera.current = true
		go_to_stop(0)
	else:
		tour.enter()
	set_note()

func check_body() -> void:
	# PHYS-001 phase 8, headless: the S004 spine push-off in the real trunk, the A1 aisle walk and the Coriolis drop (body_tour.gd); needs physics frames (--fixed-fps 60).
	var out: Dictionary = await ensure_body_tour().run_check()
	print("WF_GODOT_BODY " + JSON.stringify(out))
	get_tree().quit(0 if out.result == "PASS" else 1)

func check_controls_body() -> void:
	# ACI-04/05/13, headless: the walk and grab lessons in the real scene, and a rebind driving the unchanged crew physics.
	var I := WfInput
	I.profile_path = "user://wf_controls_check_body.cfg"
	DirAccess.remove_absolute(ProjectSettings.globalize_path(I.profile_path))
	I.force_prompts = true
	I.load_profile()
	var out := []
	for i in 5:
		await get_tree().process_frame
	out.append({"id": "walk_lesson_offered", "ok": I.shown.has("move_rail") and I.overlay.card.visible and not I.overlay.is_modal()})
	var start := progress
	Input.action_press("player.move_forward")
	for i in 30:
		await get_tree().process_frame
	Input.action_release("player.move_forward")
	out.append({"id": "walk_by_action", "ok": progress > start and I.learned.has("move_rail"), "actual": [start, progress]})
	var tour := ensure_body_tour()
	toggle_body_tour()
	for i in 30:
		await get_tree().physics_frame
	out.append({"id": "grab_lesson_offered", "ok": I.context == "body" and I.shown.has("grab") and tour.actor.grip != null})
	var tap := func(k: Key) -> void:
		for down in [true, false]:
			var ev := InputEventKey.new()
			ev.keycode = k
			ev.pressed = down
			get_viewport().push_input(ev)
		for j in 10:
			await get_tree().physics_frame
	await tap.call(KEY_R)
	var released: bool = tour.actor.grip == null
	await tap.call(KEY_G)
	out.append({"id": "grab_release_by_action", "ok": released and tour.actor.grip != null and I.learned.has("grab")})
	I.assign("player.grab", {"t": "key", "k": KEY_F, "p": false})
	await tap.call(KEY_R)
	await tap.call(KEY_G)
	var old_key_dead: bool = tour.actor.grip == null
	await tap.call(KEY_F)
	out.append({"id": "rebind_drives_physics", "ok": old_key_dead and tour.actor.grip != null, "actual": I.label("player.grab")})
	DirAccess.remove_absolute(ProjectSettings.globalize_path(I.profile_path))
	var failed := out.filter(func(c): return not c.ok).map(func(c): return c.id)
	print("WF_GODOT_CONTROLS_BODY " + JSON.stringify({"result": "PASS" if failed.is_empty() else "FAIL", "failed": failed, "checks": out}))
	get_tree().quit(0 if failed.is_empty() else 1)

func capture_lesson(path: String) -> void:
	# A still of the MOVE lesson card beside the review guide (needs a display; scratch profile).
	WfInput.profile_path = "user://wf_controls_capture.cfg"
	DirAccess.remove_absolute(ProjectSettings.globalize_path(WfInput.profile_path))
	WfInput.force_prompts = true
	WfInput.load_profile()
	for i in 30:
		await get_tree().process_frame
	get_viewport().get_texture().get_image().save_png(path)
	DirAccess.remove_absolute(ProjectSettings.globalize_path(WfInput.profile_path))
	get_tree().quit()

func capture_body(directory: String) -> void:
	# Stills of the body tour in the visible ship (needs a display): spine grip, drift, catch, aisle, aisle walk, aisle eye view.
	await ensure_body_tour().capture(directory)
	get_tree().quit()

func fail_check(message: String) -> void:
	push_error("WF_TRANSFER_CHECK FAIL " + message)
	get_tree().quit(1)

func capture_transfer(directory: String) -> void:
	# Stills of the mechanisms: the airlock from its outer half, the drum (approaching the open gate, inside with the gate closed and looking
	# back at it, the door open, in the tube), body pace on the crew-tube ladder, and the sector leaf below.
	DirAccess.make_dir_recursive_absolute(directory)
	var dt := 1.0 / 30.0
	var sector: float = openings.filter(func(o): return o.kind == "SECTOR_LEAF")[0].rail_m
	var shots := [["0_airlock", 1.0], ["1_gate_open", gate_rail - 1.0], ["2_gate_closed", gate_rail + 1.2], ["3_door_open", gate_rail + 2.0],
		["4_in_tube", gate_rail + 3.5], ["5_body_on_ladder", (gate_rail + sector) / 2.0], ["6_sector_leaf", sector - 1.2]]
	progress = 0.0
	stop_view = -1
	settle()
	update_camera()
	for shot in shots:
		var guard := 0
		body_mode = shot[0] == "5_body_on_ladder"
		while progress < shot[1] - 1e-3 and guard < 30 * 300:
			step_mechanisms(dt)
			move_along(dt * (float(body_data.review_speed_m_s) if body_mode else PACE))
			guard += 1
		look_offset = Vector2.ZERO
		if shot[0] == "2_gate_closed":
			# Synchronized, looking back at the closed port gate in the stationary spine.
			while drum_mode != "SYNCED" and guard < 30 * 300:
				step_mechanisms(dt)
				guard += 1
			look_offset = Vector2(PI, 0.0)
		elif shot[0] == "6_sector_leaf":
			while opening_open(openings.filter(func(o): return o.kind == "SECTOR_LEAF")[0]) < 0.999 and guard < 30 * 300:
				step_mechanisms(dt)
				guard += 1
		update_camera()
		await RenderingServer.frame_post_draw
		await RenderingServer.frame_post_draw
		get_viewport().get_texture().get_image().save_png(directory.path_join("transfer_%s.png" % shot[0]))
	get_tree().quit()

func capture_stops(directory: String) -> void:
	DirAccess.make_dir_recursive_absolute(directory)
	for index in range(route.stops.size()):
		go_to_stop(index)
		await RenderingServer.frame_post_draw
		await RenderingServer.frame_post_draw
		get_viewport().get_texture().get_image().save_png(directory.path_join("induction_%d_%s.png" % [index + 1, route.stops[index].key]))
	# The rail camera halfway along each leg.
	for leg in route.legs:
		progress = (float(leg.rail_m[0]) + float(leg.rail_m[1])) / 2.0
		stop_view = -1
		look_offset = Vector2.ZERO
		settle()
		update_camera()
		await RenderingServer.frame_post_draw
		await RenderingServer.frame_post_draw
		get_viewport().get_texture().get_image().save_png(directory.path_join("rail_%s.png" % leg.route_key.replace("-", "_")))
	get_tree().quit()

func build_lights(by_name: Dictionary) -> void:
	# FUT-003: each emitter's light at the centre of its emitting faces (node frame), pushed toward the nearest route rail point when the rail
	# passes close, so a wall strip lights the passage in front of it. Presentation only: no lighting design, power or heat.
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--lamp-energy="):
			lamp_scale = float(arg.trim_prefix("--lamp-energy="))
	for record in manifest.nodes:
		if not record.has("light") or not by_name.has(record.node):
			continue
		var q: Dictionary = record.light
		var lamp := OmniLight3D.new()
		lamp.light_color = Color(q.color[0], q.color[1], q.color[2]).linear_to_srgb()
		lamp.light_energy = float(q.energy) * lamp_scale
		lamp.omni_range = float(q.range_m)
		lamp.shadow_enabled = false
		lamp.visible = false
		var node: Node3D = by_name[record.node]
		node.add_child(lamp)
		var c: Array = q.centre_local_runtime_m
		lamp.position = Vector3(c[0], c[1], c[2])
		var at := lamp.global_position
		var near := nearest_rail_point(at)
		var d := near - at
		if d.length() < LAMP_PUSH_M and d.length() > 0.01:
			lamp.global_position = at + d.normalized() * minf(float(q.offset_m), d.length() * 0.5)
		lamps.append(lamp)

func nearest_rail_point(at: Vector3) -> Vector3:
	var best := points[0]
	for p in points:
		if p.distance_squared_to(at) < best.distance_squared_to(at):
			best = p
	return best

func set_look(on: bool) -> void:
	# The S004 look: the emitters' lights, a dim ambient and AgX tone mapping; off: the camera's inspection light and the flat ambient.
	look_lights = on and not lamps.is_empty()
	inspection_light.light_energy = 0.06 if look_lights else 0.65
	if body_tour != null:
		body_tour.lamp.light_energy = inspection_light.light_energy
	world.environment.ambient_light_energy = 0.12 if look_lights else 0.65
	world.environment.tonemap_mode = Environment.TONE_MAPPER_AGX if look_lights else Environment.TONE_MAPPER_LINEAR
	update_lamps()

func update_lamps() -> void:
	lamp_t = 0.0
	var eye := (body_tour.camera if body_tour != null and body_tour.active else camera).global_position
	var near: Array = []
	for lamp in lamps:
		lamp.visible = false
		var d: float = lamp.global_position.distance_to(eye)
		if look_lights and d < LAMP_REACH_M:
			near.append([d, lamp])
	near.sort_custom(func(a, b): return a[0] < b[0])
	for i in range(mini(near.size(), LAMP_MAX)):
		near[i][1].visible = true
