extends Node3D
## Authored wrapper; imported geometry is disposable and remains unedited.

var camera := Camera3D.new()
var focus := Vector3.ZERO
var home_focus := Vector3.ZERO
var radius := 280.0
var yaw := 0.62
var pitch := 0.48
var model: Node3D
var groups := {}
var records := {}
var meshes: Array[MeshInstance3D] = []
var triangles := {}
var selected_group := ""
var selected_mesh: MeshInstance3D
var highlight := StandardMaterial3D.new()
var group_list := ItemList.new()
var details := Label.new()
var hull_toggle := CheckButton.new()
var focus_button := Button.new()
var hide_button := Button.new()
var isolate_button := Button.new()
var isolated := false
var saved_visibility := {}
var drag_distance := 0.0
var selecting := false
var group_names: Array[String] = []
# OWN-M4 m2 (S&E 15!A202): red = the blade's fixed axial datum, yellow = sliding mounts; a non-diegetic REVIEW LEGEND drawn over the
# grey hardware, never the ship's paint. Matched by exported material name (Runtime_WF_MAT_MountDatum / MountSlide).
const LEGEND := {"MountDatum": Color(0.90, 0.12, 0.12), "MountSlide": Color(0.97, 0.86, 0.10)}
var legend_on := false
var legend_meshes := 0
var legend_label := Label.new()
var review: WfReviewGuide = null    # U05: the guided inspector session (review menu or -- --review=inspector)
var header_label: Label
const TITLES = {
	"Assembly_CREW_TRANSFER": "Crew transfer", "Assembly_EYE": "EYE",
	"Assembly_FORWARD_SHIELD": "Forward shield", "Assembly_HABITAT": "Habitat rings",
	"Assembly_HULL": "Hull", "Assembly_POWER_STORAGE": "Power storage",
	"Assembly_PROPULSION": "Propulsion", "Assembly_ROTOR_INTERFACE": "Rotor interfaces",
	"Assembly_SERVICE": "Service", "Assembly_SHIELDING": "Shielding",
	"Assembly_STORAGE": "Storage", "Assembly_STRUCTURE": "Structure",
	"Assembly_THERMAL": "Radiators & thermal"
}

func _ready() -> void:
	WfInput.context = "inspector"                      # ACI-10: the guide and the Codex read this scene's actions
	var label := Label.new()
	label.position = Vector2(24, 20)
	label.add_theme_font_size_override("font_size", 18)
	label.text = "WAYFARER 001  /  COAST · STATIC REP_PROXY\nClick: select   Double-click / F: focus   Drag: orbit\nShift-drag / middle: pan   Wheel: zoom   1 / 2 / 3: views   Home: reset   L: radiator mount review legend"
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	header_label = label
	var canvas := CanvasLayer.new()
	add_child(canvas)
	canvas.add_child(label)
	legend_label.position = Vector2(24, 104)
	legend_label.add_theme_color_override("font_color", Color(0.97, 0.86, 0.10))
	legend_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	canvas.add_child(legend_label)
	if not ResourceLoader.exists("res://generated/wayfarer.glb"):
		label.text += "\n\nGenerate the ship from the repository root:\npython3 tools/workflow.py runtime-export"
		return
	var manifest = JSON.parse_string(FileAccess.get_file_as_string("res://generated/manifest.json"))
	var lo: Array = manifest.bounds_runtime_m.min
	var hi: Array = manifest.bounds_runtime_m.max
	home_focus = (Vector3(lo[0], lo[1], lo[2]) + Vector3(hi[0], hi[1], hi[2])) * 0.5
	focus = home_focus
	model = load("res://generated/wayfarer.glb").instantiate()
	add_child(model)
	WfProductionLayer.apply(model, manifest)   # M7: production detail drawn near the camera only
	for record in manifest.nodes:
		records[record.node] = record
	# Resolve each freshly imported mesh through its manifest, then bind controls
	# to semantic assembly names. Blender may suffix exported group node names.
	for item in model.find_children("*", "MeshInstance3D", true, false):
		var record: Dictionary = records.get(str(item.name), {})
		if record.is_empty():
			push_error("Missing mesh provenance: " + str(item.name))
			return
		var group_name: String = record.lineage[0]
		var group: Node3D = item.get_parent()
		while group.get_parent() != model:
			group = group.get_parent()
		groups[group_name] = group
		item.set_meta("subsystem", group_name)
		meshes.append(item)
		# RT-003 timeline display objects: show them as the export pose (the saved preset) has them.
		if record.has("display"):
			item.visible = record.display.static_opacity > 0.001
			item.transparency = clampf(1.0 - record.display.static_opacity, 0.0, 1.0)
	for group_name in manifest.groups:
		if not groups.has(group_name):
			push_error("Missing subsystem: " + group_name)
			return
		group_names.append(group_name)
	highlight.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	highlight.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	highlight.albedo_color = Color(0.12, 0.75, 1.0, 0.32)
	highlight.no_depth_test = false
	build_inspection_ui(canvas)
	add_child(camera)
	camera.current = true
	camera.near = 0.1
	camera.far = 3000.0
	camera.fov = 50.0
	var world := WorldEnvironment.new()
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
	update_camera()
	# Optional visual review: -- --capture=/absolute/path (three standard views).
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--capture="):
			capture_views(arg.trim_prefix("--capture="))
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--review="):
			WfReviewGuide.pending = arg.trim_prefix("--review=")
	if WfReviewGuide.pending == "inspector":
		WfReviewGuide.pending = ""
		review = WfReviewGuide.new(WfInspectorSession.new(self))
		add_child(review)
		header_label.visible = false               # the guide carries the keys; the side panel keeps the part's source status
		legend_label.position.y = 20
		legend_label.position.x = 480
		if "--check-review" in OS.get_cmdline_user_args():
			await check_review()
	if "--check-legend" in OS.get_cmdline_user_args():
		# OWN-M4 m2: the mounts are grey by default, the legend marks them red/yellow and L again restores the exported materials.
		var n_on := set_legend(true)
		var n_off := set_legend(false)
		var cleared := meshes.all(func(item): return item.mesh == null or range(item.mesh.get_surface_count()).all(func(i): return item.get_surface_override_material(i) == null))
		print("WF_GODOT_LEGEND ", JSON.stringify({"result": "PASS" if n_on > 0 and n_on == n_off and cleared else "FAIL", "surfaces": n_on, "cleared": cleared}))
		get_tree().quit()

func update_camera() -> void:
	camera.position = focus + radius * Vector3(sin(yaw) * cos(pitch), sin(pitch), cos(yaw) * cos(pitch))
	camera.look_at(focus)
	camera.h_offset = radius * 0.18

func set_view(index: int) -> void:
	focus = home_focus
	radius = 280.0
	if index == 1:
		yaw = 0.0
		pitch = 0.0
	elif index == 2:
		yaw = 0.0
		pitch = PI / 2.0 - 0.001
	else:
		yaw = 0.62
		pitch = 0.48
	update_camera()

func _unhandled_input(event: InputEvent) -> void:
	if model == null:
		return
	if event is InputEventMouseButton:
		if event.button_index == MOUSE_BUTTON_LEFT:
			if event.pressed:
				drag_distance = 0.0
				selecting = not event.shift_pressed
				if event.double_click and selecting:
					pick_at(event.position)
					focus_selection()
					selecting = false
			elif selecting:
				if drag_distance < 5.0:
					pick_at(event.position)
				selecting = false
		if event.pressed and event.button_index == MOUSE_BUTTON_WHEEL_UP:
			radius = maxf(2.0, radius / 1.12)
		elif event.pressed and event.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			radius = minf(1500.0, radius * 1.12)
	if event is InputEventMouseMotion:
		if event.button_mask & MOUSE_BUTTON_MASK_LEFT:
			drag_distance += event.relative.length()
		if event.button_mask & MOUSE_BUTTON_MASK_MIDDLE or (event.button_mask & MOUSE_BUTTON_MASK_LEFT and event.shift_pressed):
			focus += (-camera.basis.x * event.relative.x + camera.basis.y * event.relative.y) * radius * 0.001
		elif event.button_mask & MOUSE_BUTTON_MASK_LEFT and drag_distance >= 5.0:
			yaw -= event.relative.x * 0.006
			pitch = clampf(pitch + event.relative.y * 0.006, -1.55, 1.55)
	if WfInput.pressed(event):
		match WfInput.key_of(event, ["inspector"]):    # ACI-10: insp.* actions and ui.cancel
			KEY_1: set_view(1)
			KEY_2: set_view(2)
			KEY_3: set_view(3)
			KEY_F: focus_selection()
			KEY_H: toggle_selected()
			KEY_I: toggle_isolate()
			KEY_L: set_legend(not legend_on)
			KEY_ESCAPE:
				if review != null and selected_group == "":
					get_tree().change_scene_to_file("res://scenes/review.tscn")
				else:
					select_group("")
	update_camera()

## U05 headless: 1 2 3, a selection (the list's handler), F, I, I, L through real key events; one WF_GODOT_REVIEW line.
func check_review() -> void:
	var s: WfInspectorSession = review.session
	for k in [KEY_1, KEY_2, KEY_3]:
		review.press(k)
		await get_tree().process_frame
	review.press(KEY_F)                                    # refused: nothing selected
	await get_tree().process_frame
	var refused := not review.last_ok
	select_group("Assembly_THERMAL")
	await get_tree().process_frame
	for k in [KEY_F, KEY_I, KEY_I, KEY_L]:
		review.press(k)
		for f in 3:
			await get_tree().process_frame
	var out := {"session": "inspector", "steps": review.events, "complete": review.complete, "refusal_shown": refused,
		"labels": range(s.steps.size()).map(func(i): return s.labels(i)), "legend_surfaces": legend_meshes}
	out.labelled = range(s.steps.size()).all(func(i): return not s.labels(i).is_empty())
	out.result = "PASS" if review.complete and refused and out.labelled else "FAIL"
	set_legend(false)                                      # restore the exported materials before quitting (as --check-legend does)
	select_group("")
	print("WF_GODOT_REVIEW " + JSON.stringify(out))
	get_tree().quit(0 if out.result == "PASS" else 1)

func build_inspection_ui(canvas: CanvasLayer) -> void:
	var panel := PanelContainer.new()
	canvas.add_child(panel)
	panel.set_anchors_and_offsets_preset(Control.PRESET_RIGHT_WIDE)
	panel.offset_left = -296
	panel.offset_right = -16
	panel.offset_top = 126
	panel.offset_bottom = -16
	var scroll := ScrollContainer.new()
	panel.add_child(scroll)
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	var column := VBoxContainer.new()
	column.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	column.add_theme_constant_override("separation", 8)
	scroll.add_child(column)
	var heading := Label.new()
	heading.text = "  SUBSYSTEMS"
	heading.add_theme_font_size_override("font_size", 18)
	column.add_child(heading)
	var sessions := Button.new()                    # U01: back to the review menu
	sessions.text = "Review sessions (guided)"
	sessions.focus_mode = Control.FOCUS_NONE
	sessions.pressed.connect(func(): get_tree().change_scene_to_file("res://scenes/review.tscn"))
	column.add_child(sessions)
	var boarding := Button.new()
	boarding.text = "Board Wayfarer · guided arrival"
	boarding.focus_mode = Control.FOCUS_NONE
	boarding.pressed.connect(func(): get_tree().change_scene_to_file("res://scenes/boarding.tscn"))
	column.add_child(boarding)
	var flight := Button.new()
	flight.text = "First Ignition · timeline"
	flight.focus_mode = Control.FOCUS_NONE
	flight.pressed.connect(func(): get_tree().change_scene_to_file("res://scenes/flight.tscn"))
	column.add_child(flight)
	group_list.custom_minimum_size = Vector2(260, 300)
	group_list.focus_mode = Control.FOCUS_NONE
	column.add_child(group_list)
	for group_name in group_names:
		group_list.add_item(TITLES.get(group_name, group_name.trim_prefix("Assembly_").capitalize()))
	group_list.item_selected.connect(func(index: int): select_group(group_names[index]))
	group_list.item_activated.connect(func(index: int):
		select_group(group_names[index])
		focus_selection())
	var row := HBoxContainer.new()
	column.add_child(row)
	for button in [focus_button, hide_button, isolate_button]:
		row.add_child(button)
		button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		button.focus_mode = Control.FOCUS_NONE
	focus_button.text = "Focus · F"
	focus_button.pressed.connect(focus_selection)
	hide_button.pressed.connect(toggle_selected)
	isolate_button.pressed.connect(toggle_isolate)
	var show_all := Button.new()
	show_all.text = "Show all subsystems"
	show_all.focus_mode = Control.FOCUS_NONE
	show_all.pressed.connect(restore_all)
	column.add_child(show_all)
	hull_toggle.text = "Hull visible"
	hull_toggle.focus_mode = Control.FOCUS_NONE
	hull_toggle.toggled.connect(func(value: bool):
		end_isolation()
		if groups.has("Assembly_HULL"):
			groups["Assembly_HULL"].visible = value
		refresh_controls())
	column.add_child(hull_toggle)
	details.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	details.custom_minimum_size.x = 260
	details.mouse_filter = Control.MOUSE_FILTER_IGNORE
	column.add_child(details)
	select_group("")

func select_group(group_name: String, mesh: MeshInstance3D = null) -> void:
	# Only stable assembly names carry behavior; mesh IDs are resolved per package.
	if isolated and group_name != selected_group:
		end_isolation()
	selected_group = group_name
	selected_mesh = mesh
	for item in meshes:
		item.material_overlay = highlight if item.get_meta("subsystem") == group_name else null
	group_list.deselect_all()
	if group_name.is_empty():
		details.text = WfInput.keys("Select a subsystem in the list or click the ship.\n\nDouble-click to focus.\n{insp.hide}: hide/show · {insp.isolate}: isolate/restore\n{ui.cancel}: clear selection")
	else:
		group_list.select(group_names.find(group_name))
		var title: String = TITLES.get(group_name, group_name)
		if mesh != null:
			var record: Dictionary = records.get(str(mesh.name), {})
			details.text = "%s\n%s\n\nGeometry: %s\nSource status: %s\nSource ref: %s" % [title,
				record.get("source_name", "Unnamed part"), record.get("geometry_status", "Unknown"),
				record.get("canon_status", "Unknown"), record.get("source_ref", "Unavailable")]
		else:
			var statuses := {}
			var refs := {}
			var count := 0
			for item in meshes:
				if item.get_meta("subsystem") == group_name:
					count += 1
					var record: Dictionary = records.get(str(item.name), {})
					statuses[record.get("geometry_status", "Unknown")] = true
					refs[record.get("source_ref", "Unavailable")] = true
			details.text = "%s\n%d parts · static COAST\n\nGeometry: %s\n%d source references\nClick a visible part for its source status and reference." % [title, count, ", ".join(statuses.keys()), refs.size()]
	refresh_controls()

func refresh_controls() -> void:
	var empty := selected_group.is_empty()
	focus_button.disabled = empty
	hide_button.disabled = empty
	isolate_button.disabled = empty
	hide_button.text = "Show · H" if not empty and not groups[selected_group].visible else "Hide · H"
	isolate_button.text = "Restore · I" if isolated else "Isolate · I"
	hull_toggle.disabled = not groups.has("Assembly_HULL")
	hull_toggle.set_pressed_no_signal(groups.has("Assembly_HULL") and groups["Assembly_HULL"].visible)
	for index in range(group_names.size()):
		var group_name := group_names[index]
		var title: String = TITLES.get(group_name, group_name)
		group_list.set_item_text(index, title if groups[group_name].visible else title + " (hidden)")

func end_isolation() -> void:
	if isolated:
		for group_name in saved_visibility:
			groups[group_name].visible = saved_visibility[group_name]
	isolated = false
	saved_visibility.clear()

func toggle_isolate() -> void:
	if selected_group.is_empty():
		return
	if isolated:
		end_isolation()
	else:
		for group_name in groups:
			saved_visibility[group_name] = groups[group_name].visible
			groups[group_name].visible = group_name == selected_group
		isolated = true
	refresh_controls()

func toggle_selected() -> void:
	if selected_group.is_empty():
		return
	end_isolation()
	groups[selected_group].visible = not groups[selected_group].visible
	refresh_controls()

func restore_all() -> void:
	end_isolation()
	for group_name in groups:
		groups[group_name].visible = true
	refresh_controls()

func focus_selection() -> void:
	if selected_group.is_empty():
		return
	var bounds := AABB()
	var first := true
	for item in meshes:
		if item.get_meta("subsystem") == selected_group:
			var box: AABB = item.global_transform * item.get_aabb()
			bounds = box if first else bounds.merge(box)
			first = false
	if first:
		return
	groups[selected_group].visible = true
	focus = bounds.get_center()
	# Fit the bounding sphere in the uncovered part of the viewport.
	var viewport := get_viewport().get_visible_rect().size
	var aspect := maxf(0.3, (viewport.x - 320.0) / viewport.y)
	var half_angle := atan(tan(deg_to_rad(camera.fov * 0.5)) * minf(1.0, aspect))
	radius = maxf(2.0, bounds.size.length() * 0.55 / sin(half_angle))
	refresh_controls()
	update_camera()

func pick_at(screen_position: Vector2) -> void:
	var origin := camera.project_ray_origin(screen_position)
	var direction := camera.project_ray_normal(screen_position)
	var nearest := INF
	var chosen: MeshInstance3D
	for item in meshes:
		if not item.is_visible_in_tree():
			continue
		var inverse := item.global_transform.affine_inverse()
		var local_origin := inverse * origin
		var local_direction := inverse.basis * direction
		if item.get_aabb().intersects_ray(local_origin, local_direction) == null:
			continue
		if not triangles.has(item.mesh):
			triangles[item.mesh] = item.mesh.generate_triangle_mesh()
		var hit: Dictionary = triangles[item.mesh].intersect_ray(local_origin, local_direction)
		if not hit.is_empty():
			var distance := origin.distance_to(item.global_transform * hit.position)
			if distance < nearest:
				nearest = distance
				chosen = item
	if chosen == null:
		select_group("")
	else:
		select_group(chosen.get_meta("subsystem"), chosen)

func capture_views(directory: String) -> void:
	DirAccess.make_dir_recursive_absolute(directory)
	for index in [1, 2, 3]:
		set_view(index)
		await RenderingServer.frame_post_draw
		await RenderingServer.frame_post_draw
		get_viewport().get_texture().get_image().save_png(directory.path_join("view_%d.png" % index))
	get_tree().quit()

func set_legend(on: bool) -> int:
	legend_on = on
	legend_meshes = 0
	for item in meshes:
		if item.mesh == null:
			continue
		for i in item.mesh.get_surface_count():
			var m := item.mesh.surface_get_material(i)
			var key := ""
			for k in LEGEND:
				if m != null and m.resource_name.contains(k):
					key = k
			if key == "":
				continue
			var mark: StandardMaterial3D = null
			if on:
				mark = StandardMaterial3D.new()
				mark.albedo_color = LEGEND[key]
				mark.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
			item.set_surface_override_material(i, mark)
			legend_meshes += 1
	legend_label.text = "REVIEW LEGEND (non-diegetic, not paint): red = fixed axial datum, yellow = sliding mount · %d surfaces · L hides" % legend_meshes if on else ""
	return legend_meshes
