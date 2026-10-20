extends Node3D
## RT-003: plays the generated First Ignition timeline on the static COAST package.
## Values come from the timeline's keys and the manifest's mechanism bindings; this script computes no spacecraft facts.
## The rings turn about their exported pivots by the binding's rate times its channel; display objects (drive glow and plasma,
## field, radiator thermal steps) replay the opacity and scale tracks the export baked from their Blender drivers.
## A named state (each configuration, and the Crown, shield-damage and radiator-cell display poses the timeline never reaches)
## shows the values the export baked for it, with the rings spinning at the state's spin fraction.
## X switches to the First Ignition exterior look (manifest look.exterior, FUT-003 step 2): one hard sun, every surface proxy grey, the
## radiators' hot face lit while the timeline's radiator thermal state is the hot one. Presentation only; nothing here is computed.

var camera := Camera3D.new()
var focus := Vector3.ZERO
var home_focus := Vector3.ZERO
var ring_focus := Vector3.ZERO
var radius := 280.0
var yaw := 0.62
var pitch := 0.48
var timeline: Dictionary
var rig: Dictionary
var pivots := {}
var displays: Array = []
var frame := 1.0
var first_frame := 1.0
var last_frame := 1.0
var playing := false
var speed := 1.0
var readout := Label.new()
var review: WfReviewGuide = null    # U05: the guided timeline session (review menu or -- --review=flight)
var header := Label.new()
var side_panel: PanelContainer
var play_bar: HBoxContainer
var slider := HSlider.new()
var play_button := Button.new()
var speed_button := Button.new()
var phase_list := ItemList.new()
var mark_list := ItemList.new()
var mark_names: Array = []
var states: Dictionary = {}
var state_name := ""
var state_turned := 0.0
var state_list := ItemList.new()
var bow_focus := Vector3.ZERO
var aft_focus := Vector3.ZERO
const SPEEDS = [0.25, 1.0, 4.0, 16.0]
var exterior: Dictionary = {}
var look_on := false
var surfaces: Array = []
var look_hidden := {}
var fills: Array = []
var world := WorldEnvironment.new()
var sun := DirectionalLight3D.new()
var grey_material := StandardMaterial3D.new()
var hot_material := StandardMaterial3D.new()
var thermal_value := 0.0
var scenario_index := 0     # OWN-RAD-Y155: which rig thermal.y155_scenario case the readout compares (0 = root baseline); display only
# PHYS-001 phase 9: the imported route as a rebased ship state (ship at the origin; the ignition origin marker moves aft on a named log display scale).
var route_state := WfRouteState.new()
var thermal := WfThermalExplorer.new()   # Milestone B (MECH-002): T opens the heat balance of the fixed blades; display only
var route_note := ""
var origin_marker := MeshInstance3D.new()
const ORIGIN_DISPLAY_UNIT_M := 12.0   # display metres per decade of distance beyond 1 km (WfRouteState.display_offset_m), presentation only

func _ready() -> void:
	WfInput.context = "flight"                      # ACI-10: the guide and the Codex read this scene's actions
	var canvas := CanvasLayer.new()
	add_child(canvas)
	header.position = Vector2(24, 20)
	header.add_theme_font_size_override("font_size", 18)
	header.mouse_filter = Control.MOUSE_FILTER_IGNORE
	header.text = header_text()
	WfInput.bindings_changed.connect(func(): header.text = header_text())
	canvas.add_child(header)
	if not ResourceLoader.exists("res://generated/wayfarer.glb"):
		header.text += "\n\nGenerate the ship from the repository root:\npython3 tools/workflow.py runtime-export"
		return
	var manifest = JSON.parse_string(FileAccess.get_file_as_string("res://generated/manifest.json"))
	rig = JSON.parse_string(FileAccess.get_file_as_string("res://generated/wf_sim_rig.json"))
	if not manifest.has("timeline"):
		header.text += "\n\nThis package has no timeline; rerun python3 tools/workflow.py runtime-export"
		return
	timeline = JSON.parse_string(FileAccess.get_file_as_string("res://generated/" + manifest.timeline.file))
	route_note = route_state.load_file("res://generated/wf_route_v1.json", rig)
	first_frame = timeline.frame_range[0]
	last_frame = timeline.frame_range[1]
	frame = first_frame
	var lo: Array = manifest.bounds_runtime_m.min
	var hi: Array = manifest.bounds_runtime_m.max
	home_focus = (Vector3(lo[0], lo[1], lo[2]) + Vector3(hi[0], hi[1], hi[2])) * 0.5
	bow_focus = Vector3(hi[0] - 20.0, home_focus.y, home_focus.z)
	aft_focus = Vector3(lo[0] + 25.0, home_focus.y, home_focus.z)
	states = manifest.timeline.get("states", {})
	focus = home_focus
	var model: Node3D = load("res://generated/wayfarer.glb").instantiate()
	add_child(model)
	WfProductionLayer.apply(model, manifest)   # M7: production detail drawn near the camera only
	var frame_of := {}
	var tracks := {}
	exterior = manifest.get("look", {}).get("exterior", {})
	for record in manifest.nodes:
		frame_of[record.node] = record.get("frame", "")
		if not exterior.is_empty() and (record.kind in exterior.hidden_kinds
				or Array(exterior.hidden_prefixes).any(func(prefix): return str(record.source_name).begins_with(prefix))):
			look_hidden[record.node] = true
		if record.has("display"):
			tracks[record.node] = record.display
	# One pivot per exported binding; the meshes it carries (node `frame`, found by turning the ring in Blender, so the sector shells and
	# their interiors too) keep their global placement when reparented.
	for key in manifest.timeline.mechanisms:
		var binding: Dictionary = manifest.timeline.mechanisms[key]
		var p: Array = binding.pivot_runtime_m
		var pivot := Node3D.new()
		pivot.name = key
		pivot.position = Vector3(p[0], p[1], p[2])
		model.add_child(pivot)
		ring_focus += pivot.position / manifest.timeline.mechanisms.size()
		pivots[key] = {"node": pivot, "binding": binding, "origin": pivot.position}
	var moved := 0
	for item in model.find_children("*", "MeshInstance3D", true, false):
		surfaces.append(item)
		if tracks.has(str(item.name)):
			displays.append({"node": item, "track": tracks[str(item.name)], "basis": item.transform.basis, "position": item.position})
		for key in pivots:
			if frame_of.get(str(item.name), "") == key:
				item.reparent(pivots[key].node, true)
				moved += 1
	if moved == 0:
		push_error("No mesh turns with a mechanism binding")
		return
	build_ui(canvas)
	thermal.setup(rig, route_state.route.model.burn_endpoint_s.value if route_state.ok() else null)
	add_child(thermal)
	add_child(camera)
	camera.current = true
	camera.near = 0.1
	camera.far = 3000.0
	camera.fov = 50.0
	world.environment = Environment.new()
	world.environment.background_mode = Environment.BG_COLOR
	world.environment.background_color = Color(0.025, 0.035, 0.05)
	world.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	world.environment.ambient_light_color = Color(0.65, 0.75, 0.85)
	world.environment.ambient_light_energy = 0.65
	add_child(world)
	for direction in [Vector3(-0.5, -0.8, -0.4), Vector3(0.5, 0.3, 0.8)]:
		var light := DirectionalLight3D.new()
		add_child(light)
		light.look_at(direction)
		light.light_energy = 1.2
		fills.append(light)
	var sphere := SphereMesh.new()
	sphere.radius = 3.0
	sphere.height = 6.0
	origin_marker.mesh = sphere
	origin_marker.visible = route_state.ok()
	add_child(origin_marker)
	build_look()
	set_view(4)
	set_frame(first_frame)
	# Optional visual review: -- --capture=/absolute/path saves a ring view and a side view per timeline mark.
	if "--exterior" in OS.get_cmdline_user_args():
		set_look(true)
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--capture="):
			capture_marks(arg.trim_prefix("--capture="))
		if arg.begins_with("--capture-states="):
			capture_states(arg.trim_prefix("--capture-states="))
	if "--check-y155" in OS.get_cmdline_user_args():
		check_y155()
	if "--check-thermal" in OS.get_cmdline_user_args():
		check_thermal()
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--capture-thermal="):
			capture_thermal(arg.trim_prefix("--capture-thermal="))
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--review="):
			WfReviewGuide.pending = arg.trim_prefix("--review=")
	if WfReviewGuide.pending == "flight":
		WfReviewGuide.pending = ""
		start_review()

## U05: the guide carries the steps and keys; the readout becomes its muted detail line (I), the play bar moves to the top.
func start_review() -> void:
	review = WfReviewGuide.new(WfFlightSession.new(self))
	add_child(review)
	header.visible = false
	readout.visible = false
	play_bar.offset_left = 480
	play_bar.offset_right = -392
	play_bar.offset_top = 20
	play_bar.offset_bottom = 60
	side_panel.offset_top = 20
	side_panel.offset_bottom = -200
	if "--check-review" in OS.get_cmdline_user_args():
		await check_review()

## U05 headless: Space, Shift+right until the locks and the burn, X, Y, then a named state (the list's click handler); one WF_GODOT_REVIEW line.
func check_review() -> void:
	var s: WfFlightSession = review.session
	var log := []
	review.press(KEY_SPACE)
	for f in 60:
		await get_tree().process_frame
	review.press(KEY_SPACE)                                   # pause, then fast-forward by keys
	for want in [2, 3]:
		var n := 0
		while review.index < want and n < 400:
			review.press(KEY_RIGHT, true)
			await get_tree().process_frame
			n += 1
		log.append({"want": want, "index": review.index, "phase": s.phase_id(), "frame": frame})
	review.press(KEY_X)
	await get_tree().process_frame
	review.press(KEY_Y)
	await get_tree().process_frame
	state_list.select(states.keys().find("SHIELD_DAMAGED"))
	state_list.item_selected.emit(states.keys().find("SHIELD_DAMAGED"))
	for f in 3:
		await get_tree().process_frame
	var out := {"session": "flight", "steps": review.events, "log": log, "complete": review.complete,
		"labels": range(s.steps.size()).map(func(i): return s.labels(i)), "readout_hidden": not readout.visible, "details": s.details().length()}
	out.labelled = range(s.steps.size()).all(func(i): return not s.labels(i).is_empty())
	out.result = "PASS" if review.complete and out.labelled and out.details > 0 else "FAIL"
	print("WF_GODOT_REVIEW " + JSON.stringify(out))
	get_tree().quit(0 if out.result == "PASS" else 1)

func check_y155() -> void:
	# Headless: every Y155 case shows its id, owner status and DIAGNOSTIC label, the blades stay the root geometry, and the readout's
	# uplift is the rig's (no number is computed here).
	var sc: Dictionary = rig.thermal.y155_scenario
	var rows := []
	var ok: bool = sc.cases.size() == 3 and sc.cases[0].id == "BASELINE"
	for i in sc.cases.size():
		scenario_index = i
		set_frame(frame)
		var line := scenario_line()
		var c: Dictionary = sc.cases[i]
		var shown: bool = readout.text.contains(c.id) and line.contains(c.status) and line.contains("182.149 m")
		if i > 0:
			shown = shown and line.contains(sc.result_status) and line.contains("NO SHRINK") and line.contains("%.5f" % c.uplift)
		ok = ok and shown
		rows.append({"id": c.id, "uplift": c.uplift, "shown": shown})
	print("WF_GODOT_Y155 ", JSON.stringify({"result": "PASS" if ok else "FAIL", "cases": rows}))
	get_tree().quit()

## Everything the thermal explorer could plausibly touch: display meshes, ring pivots, the hot face, the frame, state and scenario.
func scene_snapshot() -> Dictionary:
	var out := {"frame": frame, "state": state_name, "scenario": scenario_index, "hot": hot_material.emission_enabled, "look": look_on}
	for d in displays:
		out[str(d.node.name)] = [d.node.transform, d.node.visible]
	for key in pivots:
		out[key] = pivots[key].node.transform
	return out

func check_thermal() -> void:
	var rows: Array = thermal.checks(scene_snapshot)
	var ok: bool = rows.all(func(r): return r.ok)
	print("WF_GODOT_THERMAL ", JSON.stringify({"result": "PASS" if ok else "FAIL", "checks": rows}))
	get_tree().quit(0 if ok else 1)

## Stills of the explorer: the default calibration case, a hypothetical 20 GW, 35 % of the cells isolated, Y155 at 1800 K.
func capture_thermal(directory: String) -> void:
	DirAccess.make_dir_recursive_absolute(directory)
	set_view(3)
	thermal.toggle()
	for shot in [["default", 0, 0], ["hypothetical_20gw", 0, 8], ["cells_35pct_isolated", 3, -7], ["y155_study", 1, 1]]:
		thermal.reset()
		thermal.row = shot[1]
		for n in absi(shot[2]):
			thermal.change(signi(shot[2]))
		thermal.update_now()
		for n in 3:
			await get_tree().process_frame
		get_viewport().get_texture().get_image().save_png(directory.path_join("thermal_%s.png" % shot[0]))
	get_tree().quit()

func material_name(material: Material) -> String:
	# Runtime_WF_MAT_<name>_<index> from the export.
	var name := material.resource_name.trim_prefix("Runtime_WF_MAT_") if material else ""
	var cut := name.rfind("_")
	return name.substr(0, cut) if cut > 0 and name.substr(cut + 1).is_valid_int() else name

func build_look() -> void:
	if exterior.is_empty():
		return
	var g: Array = exterior.grey
	for material in [grey_material, hot_material]:
		material.albedo_color = Color(g[0], g[1], g[2]).linear_to_srgb()
		material.roughness = exterior.roughness
	var c: Array = exterior.hot_color
	# The Compatibility renderer scales the sRGB emission colour by the multiplier before linearizing it, so the energy goes into the
	# linear colour and the multiplier stays 1 (measured; it renders the Cycles strength in either renderer).
	hot_material.emission = (Color(c[0], c[1], c[2]) * float(exterior.hot_energy)).linear_to_srgb()
	hot_material.emission_energy_multiplier = 1.0
	var s: Array = exterior.sun_runtime
	add_child(sun)
	sun.look_at(-Vector3(s[0], s[1], s[2]))
	sun.light_energy = exterior.sun_energy
	sun.light_angular_distance = exterior.sun_angular_deg
	sun.shadow_enabled = true
	sun.directional_shadow_max_distance = 900.0
	sun.visible = false

func set_look(on: bool) -> void:
	if exterior.is_empty():
		return
	look_on = on
	for item in surfaces:
		var mesh: MeshInstance3D = item
		for index in mesh.get_surface_override_material_count():
			var name := material_name(mesh.mesh.surface_get_material(index))
			var material: Material = null
			if on and name not in exterior.display_emitters:
				material = hot_material if name in exterior.hot_face else grey_material
			mesh.set_surface_override_material(index, material)
		if look_hidden.has(str(mesh.name)):
			mesh.visible = not on and displays.all(func(d): return d.node != mesh)
	for light in fills:
		light.visible = not on
	sun.visible = on
	var environment: Environment = world.environment
	environment.background_color = Color.BLACK if on else Color(0.025, 0.035, 0.05)
	environment.ambient_light_energy = 0.0 if on else 0.65
	environment.tonemap_mode = Environment.TONE_MAPPER_AGX if on else Environment.TONE_MAPPER_LINEAR
	environment.tonemap_exposure = exterior.exposure if on else 1.0
	if state_name != "":
		set_state(state_name)
	else:
		set_frame(frame)

func show_hot(value: float) -> void:
	thermal_value = value
	hot_material.emission_enabled = look_on and is_equal_approx(value, exterior.get("hot_thermal_state", -1.0))

func look_line() -> String:
	if not look_on:
		return ""
	return "LOOK  First Ignition exterior (%s): one sun, proxy grey; hot face %d K at emissivity %.2f %s (%.1f× a sunlit hull); plume not drawn" % [
		exterior.status, exterior.kelvin, exterior.emissivity, "lit" if hot_material.emission_enabled else "unlit at this thermal state (temperature OPEN)", exterior.sunlit_ratio]

func scenario_line() -> String:
	# OWN-RAD-Y155 (S&E 40!A110:F123): the radiator material/view scenarios, compared on the same three 182.149 m blades at 1800 K. The
	# rig computes every number (thermal_budget.y155); nothing here resizes, recolours or dims a blade.
	var sc: Dictionary = rig.get("thermal", {}).get("y155_scenario", {})
	if sc.is_empty():
		return ""
	var c: Dictionary = sc.cases[scenario_index]
	var lines := ["RADIATOR SCENARIO %d/%d  (%s cycles)  %s  ·  %s" % [scenario_index + 1, sc.cases.size(), WfInput.label("flight.scenario"), c.id, c.status],
		"emissivity %.2f  view factor %.2f  ·  geometry unchanged: 3 fixed blades, 182.149 m, 1800 K" % [c.emissivity, c.view_factor]]
	if scenario_index == 0:
		lines.append("root baseline ideal rejection %.3f GW; vs 16 GW calibration %s %.3f GW (%s)" % [
			c.rejection_W / 1e9, "deficit" if c.residual_W > 0.0 else "ideal spare", absf(c.residual_W) / 1e9, sc.result_status])
	else:
		lines.append("%s: uplift ×%.5f per area · ideal %.3f GW on the same blades · equal-load area −%.1f %% (theoretical, NO SHRINK) · vs 16 GW %s %.3f GW" % [
			sc.result_status, c.uplift, c.rejection_W / 1e9, c.area_reduction * 100.0, "deficit" if c.residual_W > 0.0 else "ideal spare (not a margin)", absf(c.residual_W) / 1e9])
	lines.append("actual drive heat, other loads and 1800 K material qualification OPEN · source %s" % sc.source_ref)
	return "\n".join(lines)

func value_at(keys: Array, at: float):
	# Same rule as flight_timeline.value_at: a key's interpolation applies until the next key.
	var lo := 0
	var hi := keys.size()
	while lo < hi:
		var mid := (lo + hi) / 2
		if keys[mid][0] <= at:
			lo = mid + 1
		else:
			hi = mid
	var i := lo - 1
	if i < 0:
		return null
	var key: Array = keys[i]
	if key[2] == "LINEAR" and i + 1 < keys.size():
		var next: Array = keys[i + 1]
		return key[1] + (next[1] - key[1]) * (at - key[0]) / (next[0] - key[0])
	return key[1]

func channel(id: String):
	return value_at(timeline.channels[id].keys, frame)

func phase_index(at: float) -> int:
	for index in range(timeline.phases.size()):
		if timeline.phases[index].frame_start <= at and at < timeline.phases[index].frame_end:
			return index
	return timeline.phases.size() - 1

func radiator_step(value: float) -> String:
	for step in rig.radiator_health.steps:
		if is_equal_approx(rig.radiator_health.steps[step].value, value):
			return step
	return "%.2f" % value

func turn_rings(turned: float) -> void:
	for key in pivots:
		var item: Dictionary = pivots[key]
		var axis: Array = item.binding.axis_runtime
		var angle: float = item.binding.rad_per_unit * turned
		item.node.transform = Transform3D(Basis(Vector3(axis[0], axis[1], axis[2]), angle), item.origin)

func show_display(item: Dictionary, opacity: float, factor: Vector3, offset: Vector3, turn: Basis = Basis.IDENTITY) -> void:
	var node: MeshInstance3D = item.node
	node.visible = opacity > 0.001 and not (look_on and look_hidden.has(str(node.name)))
	node.transparency = clampf(1.0 - opacity, 0.0, 1.0)
	node.basis = turn * item.basis * Basis.from_scale(factor)
	node.position = item.position + offset

func set_frame(at: float) -> void:
	frame = clampf(at, first_frame, last_frame)
	if state_name != "":
		state_name = ""
		state_list.deselect_all()
	turn_rings(channel("rotor.spin_turned"))
	for item in displays:
		var track: Dictionary = item.track
		var factor := Vector3.ONE
		for axis in ["x", "y", "z"]:
			if track.has("scale_" + axis):
				factor[["x", "y", "z"].find(axis)] = maxf(value_at(track["scale_" + axis], frame), 1e-4)
		show_display(item, value_at(track.opacity, frame) if track.has("opacity") else 1.0, factor, Vector3.ZERO)
	slider.set_value_no_signal(frame)
	show_hot(channel("radiator.thermal_state"))
	var index := phase_index(frame)
	var phase: Dictionary = timeline.phases[index]
	phase_list.select(index)
	var k: Dictionary = timeline.kinematics
	var where: String = phase.get("configuration", "%s -> %s" % [phase.get("from", "?"), phase.get("to", "?")])
	var elapsed: float = channel("kinematics.burn_elapsed_s")
	var bound := ">= " if elapsed >= k.burn_time_s and phase.id != "BURN" else ""
	var rings := "stopped and locked" if channel("rotor.ring_locks_engaged") > 0.5 else "spin %.2f of %s rpm" % [channel("rotor.spin_fraction"), rig.rotors[0].rpm]
	readout.text = "\n".join([
		"frame %d of %d  ·  %s  ·  %s" % [int(frame), int(last_frame), phase.id, where],
		phase.title,
		phase.label,
		"",
		"KINEMATICS (SOURCED %s, %s: traveled displacement, not heliocentric)" % [k.source_ref, k.scenario_status],
		"burn time %.4f d   a %.3f g   v %.5f c   x %s%.4f AU" % [elapsed / 86400.0, channel("kinematics.acceleration_g"), channel("kinematics.speed_c"), bound, channel("kinematics.distance_AU")],
		"",
		"SHOWN STATES (PRESENTATION)",
		"configuration %s" % channel("configuration"),
		"rings %s" % rings,
		"drive %.2f   display throttle %.2f (a / %s g)" % [channel("drive.drive_active"), channel("drive.thrust_level"), k.max_accel_g],
		"radiators %s   EYE %s" % [radiator_step(channel("radiator.thermal_state")), channel("eye.mode")],
		"",
		"Timeline %s: phase order and timing are display choices; unscaled phases carry no seconds." % timeline.status,
		"Moving: the rings, and %d display objects replaying their Blender drivers (static colours). Unknown: %d inputs (centre of mass, mass history, drive outputs, ...)." % [displays.size(), timeline.unknown.size()],
		look_line(),
		scenario_line(),
		route_line(elapsed),
	])
	play_button.text = ("Pause · " if playing else "Play · ") + WfInput.label("flight.play")

func route_line(elapsed: float) -> String:
	# DYN-001/021, C-013: the ship stays at the local origin; the ignition origin marker sits aft by the log display transform of x. Values are
	# the sheet's rows (linear in mission time between them); attitude is independent of velocity and OPEN.
	if not route_state.ok():
		origin_marker.visible = false
		return "ROUTE  %s" % route_note
	var s := route_state.sample(elapsed)
	if s.is_empty():
		origin_marker.visible = false
		return "ROUTE  no released row at this time"
	origin_marker.visible = true
	origin_marker.position = Vector3(aft_focus.x - 60.0 - WfRouteState.display_offset_m(s.local_x_m, ORIGIN_DISPLAY_UNIT_M), home_focus.y, home_focus.z)
	return "ROUTE (REBASED: ship at origin, %s %s) x %s m  v %.1f m/s  a %.4f m/s2 · marker: ignition origin, log display (%.0f m/decade) · attitude OPEN · open checks: %s" % [
		s.frame_id, s.status, String.num_scientific(s.local_x_m), s.vx_mps, s.ax_mps2, ORIGIN_DISPLAY_UNIT_M, ", ".join(PackedStringArray(s.open_checks))]

func set_state(name: String) -> void:
	# A named state replaces the timeline pose; the rings start from where the timeline left them.
	if state_name == "":
		state_turned = channel("rotor.spin_turned")
	playing = false
	state_name = name
	var state: Dictionary = states[name]
	turn_rings(state_turned)
	for item in displays:
		var values: Dictionary = item.track.get("states", {}).get(name, {})
		var factor := Vector3.ONE
		for axis in ["x", "y", "z"]:
			if values.has("scale_" + axis):
				factor[["x", "y", "z"].find(axis)] = maxf(values["scale_" + axis], 1e-4)
		var offset: Array = values.get("offset", [0.0, 0.0, 0.0])
		var turn := Basis.IDENTITY
		if values.has("turn"):     # FWD-V2 gimbal: runtime-axis turn, row-major, pre-multiplying the rest basis
			var m: Array = values.turn
			turn = Basis(Vector3(m[0], m[3], m[6]), Vector3(m[1], m[4], m[7]), Vector3(m[2], m[5], m[8]))
		show_display(item, values.get("opacity", 1.0), factor, Vector3(offset[0], offset[1], offset[2]), turn)
	var controls: Dictionary = state.controls
	var drive: Dictionary = controls.DRIVE_MANIFOLD_CTRL
	var forward: Dictionary = controls.FORWARD_DEFENSE_CTRL
	var thermal: Dictionary = controls.RADIATOR_HEALTH_CTRL
	var rings := "spinning at %.2f of %s rpm" % [state.spin_fraction, rig.rotors[0].rpm] if state.spin_fraction > 0.0 else "stopped and locked"
	show_hot(thermal.thermal_state)
	var shown := displays.filter(func(item): return item.track.get("states", {}).get(name, {}).get("opacity", 1.0) > 0.001).size()
	readout.text = "\n".join([
		"STATE %s  ·  %s  ·  %s" % [name, state.kind.replace("_", " "), state.status],
		"configuration %s%s" % [state.base, {"configuration": "", "display_pose": " with a preview display pose (never saved, never a configuration)", "drive_action": " with a drive action settled at its last key"}[state.kind]],
		state.get("description", ""),
		"",
		"SHOWN STATES (PRESENTATION)",
		"rings %s" % rings,
		"drive %.2f   display throttle %.2f   plasma %.2f" % [drive.drive_active, drive.thrust_level, drive.plasma_visibility],
		"radiators %s   cell isolation %.2f   resurfaced %.2f   requalified %.2f" % [radiator_step(thermal.thermal_state), thermal.cell_isolation, thermal.cell_resurface, thermal.get("cell_requalify", 0.0)],
		"field %s   Crown engage %.2f at azimuth %.3f turn" % ["on" if forward.field_on > 0.0 else "off", forward.crown_engage, forward.crown_azimuth],
		"shield damage %.2f   repair %.2f (fractions of the 96 cells)" % [forward.damage_state, forward.repair_state],
		"",
		"Values baked from the Blender drivers at this state; %d of %d driven objects show. The timeline keeps these displays at COAST." % [shown, displays.size()],
		"Pick a phase, a mark or the slider to return to the timeline.",
		look_line(),
		scenario_line(),
	])
	play_button.text = "Play · " + WfInput.label("flight.play")

func _process(delta: float) -> void:
	if state_name != "" and states[state_name].spin_fraction > 0.0:
		state_turned += delta * timeline.fps * states[state_name].spin_fraction
		turn_rings(state_turned)
	if playing:
		var next: float = frame + delta * timeline.fps * speed
		if next >= last_frame:
			next = last_frame
			playing = false
		set_frame(next)

func build_ui(canvas: CanvasLayer) -> void:
	var panel := PanelContainer.new()
	side_panel = panel
	canvas.add_child(panel)
	panel.set_anchors_and_offsets_preset(Control.PRESET_RIGHT_WIDE)
	panel.offset_left = -376
	panel.offset_right = -16
	panel.offset_top = 96
	panel.offset_bottom = -110
	var scroll := ScrollContainer.new()
	panel.add_child(scroll)
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	var column := VBoxContainer.new()
	column.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	column.add_theme_constant_override("separation", 8)
	scroll.add_child(column)
	readout.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	readout.custom_minimum_size.x = 340
	readout.mouse_filter = Control.MOUSE_FILTER_IGNORE
	column.add_child(readout)
	var heading := Label.new()
	heading.text = "PHASES"
	column.add_child(heading)
	phase_list.custom_minimum_size = Vector2(340, 260)
	phase_list.focus_mode = Control.FOCUS_NONE
	for phase in timeline.phases:
		phase_list.add_item("%s  ·  %d–%d" % [phase.id, phase.frame_start, phase.frame_end])
	phase_list.item_selected.connect(func(index: int): set_frame(timeline.phases[index].frame_start))
	column.add_child(phase_list)
	heading = Label.new()
	heading.text = "MARKS"
	column.add_child(heading)
	mark_list.custom_minimum_size = Vector2(340, 150)
	mark_list.focus_mode = Control.FOCUS_NONE
	mark_names = timeline.marks.keys()
	for mark in mark_names:
		mark_list.add_item("%s  ·  frame %d" % [mark, timeline.marks[mark].frame])
	mark_list.item_selected.connect(func(index: int):
		playing = false
		set_frame(timeline.marks[mark_names[index]].frame))
	column.add_child(mark_list)
	heading = Label.new()
	heading.text = "STATES (outside the timeline)"
	column.add_child(heading)
	state_list.custom_minimum_size = Vector2(340, 200)
	state_list.focus_mode = Control.FOCUS_NONE
	for name in states:
		state_list.add_item("%s  ·  %s" % [name, states[name].kind.replace("_", " ")])
	state_list.item_selected.connect(func(index: int): set_state(states.keys()[index]))
	column.add_child(state_list)
	var back := Button.new()
	back.text = "Back to the inspector · Esc"
	back.focus_mode = Control.FOCUS_NONE
	back.pressed.connect(func(): get_tree().change_scene_to_file("res://scenes/inspector.tscn"))
	column.add_child(back)
	var bar := HBoxContainer.new()
	play_bar = bar
	canvas.add_child(bar)
	bar.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_WIDE)
	bar.offset_left = 24
	bar.offset_right = -24
	bar.offset_top = -80
	bar.offset_bottom = -40
	for button in [play_button, speed_button]:
		button.focus_mode = Control.FOCUS_NONE
		button.custom_minimum_size.x = 130
		bar.add_child(button)
	play_button.pressed.connect(toggle_play)
	speed_button.text = "Speed ×1"
	speed_button.pressed.connect(func():
		speed = SPEEDS[(SPEEDS.find(speed) + 1) % SPEEDS.size()]
		speed_button.text = "Speed ×%s" % speed)
	slider.min_value = first_frame
	slider.max_value = last_frame
	slider.step = 1.0
	slider.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	slider.focus_mode = Control.FOCUS_NONE
	slider.value_changed.connect(func(value: float): set_frame(value))
	bar.add_child(slider)

func toggle_play() -> void:
	if frame >= last_frame:
		frame = first_frame
	playing = not playing
	set_frame(frame)

func update_camera() -> void:
	camera.position = focus + radius * Vector3(sin(yaw) * cos(pitch), sin(pitch), cos(yaw) * cos(pitch))
	camera.look_at(focus)
	camera.h_offset = radius * 0.2

func set_view(index: int) -> void:
	# 1-3 match the inspector's whole-ship views; 4 looks at the rings from aft and outboard, 5 at the shield face from ahead,
	# 6 at the nozzles from aft.
	focus = [home_focus, home_focus, home_focus, ring_focus, bow_focus, aft_focus][index - 1]
	radius = [280.0, 280.0, 280.0, 120.0, 140.0, 90.0][index - 1]
	yaw = [0.0, 0.0, 0.62, -2.5, 1.15, -2.2][index - 1]
	pitch = [0.0, PI / 2.0 - 0.001, 0.48, -0.15, 0.3, 0.3][index - 1]
	update_camera()

func _unhandled_input(event: InputEvent) -> void:
	if timeline.is_empty():
		return
	if event is InputEventMouseButton and event.pressed:
		if event.button_index == MOUSE_BUTTON_WHEEL_UP:
			radius = maxf(2.0, radius / 1.12)
		elif event.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			radius = minf(1500.0, radius * 1.12)
	if event is InputEventMouseMotion:
		if event.button_mask & MOUSE_BUTTON_MASK_MIDDLE or (event.button_mask & MOUSE_BUTTON_MASK_LEFT and event.shift_pressed):
			focus += (-camera.basis.x * event.relative.x + camera.basis.y * event.relative.y) * radius * 0.001
		elif event.button_mask & MOUSE_BUTTON_MASK_LEFT:
			yaw -= event.relative.x * 0.006
			pitch = clampf(pitch + event.relative.y * 0.006, -1.55, 1.55)
	if WfInput.pressed(event, true) and thermal.handle_key(event):
		get_viewport().set_input_as_handled()
		return
	if WfInput.pressed(event, true):
		match WfInput.key_of(event, ["flight"]):        # ACI-10: flight.* actions and ui.cancel
			KEY_SPACE:
				if not event.is_echo():
					toggle_play()
			KEY_RIGHT: set_frame(frame + (24.0 if WfInput.shifted(event) else 1.0))
			KEY_LEFT: set_frame(frame - (24.0 if WfInput.shifted(event) else 1.0))
			KEY_1: set_view(1)
			KEY_2: set_view(2)
			KEY_3: set_view(3)
			KEY_4: set_view(4)
			KEY_5: set_view(5)
			KEY_6: set_view(6)
			KEY_X: set_look(not look_on)
			KEY_Y:
				scenario_index = (scenario_index + 1) % maxi(1, rig.get("thermal", {}).get("y155_scenario", {}).get("cases", []).size())
				if state_name != "":
					set_state(state_name)
				else:
					set_frame(frame)
			KEY_ESCAPE: get_tree().change_scene_to_file("res://scenes/review.tscn" if review != null else "res://scenes/inspector.tscn")
	update_camera()

func header_text() -> String:
	return WfInput.keys("WAYFARER 001  /  FIRST IGNITION TIMELINE · STATIC REP_PROXY\n{flight.play}: play/pause   {flight.frame_prev} {flight.frame_next}: step (Shift ×24)   Drag: orbit   Wheel: zoom   {flight.view_1}–{flight.view_3}: ship views   {flight.view_4}: rings   {flight.view_5}: shield face   {flight.view_6}: nozzles   {flight.look}: First Ignition look   {flight.scenario}: radiator scenario   {thermal.toggle}: thermal explorer   {ui.cancel}: inspector")

func capture_marks(directory: String) -> void:
	DirAccess.make_dir_recursive_absolute(directory)
	for mark in mark_names:
		set_frame(timeline.marks[mark].frame)
		for view in [4, 1]:
			set_view(view)
			await RenderingServer.frame_post_draw
			await RenderingServer.frame_post_draw
			get_viewport().get_texture().get_image().save_png(directory.path_join("%s%s.png" % [mark, "" if view == 4 else "_side"]))
	get_tree().quit()

func capture_states(directory: String) -> void:
	DirAccess.make_dir_recursive_absolute(directory)
	for name in states:
		set_state(name)
		for view in [3, 5, 6]:
			set_view(view)
			await RenderingServer.frame_post_draw
			await RenderingServer.frame_post_draw
			get_viewport().get_texture().get_image().save_png(directory.path_join("%s_%d.png" % [name, view]))
	get_tree().quit()
