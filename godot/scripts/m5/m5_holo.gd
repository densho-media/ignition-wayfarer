extends Node3D
## M5 subsystem hologram (owner 2026-10-18, S&E 15!A217 / 98!A119: one functional in-scene subsystem explorer from the existing GLB),
## extended in M6 (owner 2026-10-19, 15!A220 / 15!A227, 98!A121) with the EYE / shield, habitat and radiator chapters (scripts/m6/).
## Presentation only: the published COAST ship (generated/wayfarer.glb) and the M5 study parts (generated/m5/m5_studies.glb) drawn
## in the explanatory overlay colours of generated/m5/wf_m5_holo.json. Every fact, status, number and chapter comes from that file;
## overlay colours are never ship materials and the imported materials stay untouched (instance material_override only).
## Selection, isolation, the dorsal cutaway and the study layers change visibility only: no ship, physics, route or mechanism state.

const DATA := "res://generated/m5/wf_m5_holo.json"
const GHOST_ENERGY := 0.05
const SUBJECT_ENERGY := 0.55
const SLEW_PROBE_S := 600.0                    # gnc_check: 600 s at 0.05 deg/s = 30 deg
const OVERVIEW_ENERGY := 0.16                     # the whole ship stacks many layers (radiator cells): dimmer so it does not saturate
const ROLE_ENERGY := {"hot": 1.1, "dim": 0.1, "flow": 0.45, "soft": 0.2}   # M6 chapter roles (radiator steps, damage, isolation; dense rings)
const CAMERA_EASE := 3.0                           # chapter transitions: camera eases to the new subject (1/s)

var data: Dictionary
var camera := Camera3D.new()
var focus := Vector3.ZERO
var home_focus := Vector3.ZERO
var radius := 300.0
var yaw := 0.62
var pitch := 0.42
var meshes: Array[MeshInstance3D] = []          # vehicle and study meshes, each with meta node / sub / study
var info := {}                                   # node id -> {subsystem, color, record}
var shader := Shader.new()
var materials := {}                              # "r,g,b|role" -> ShaderMaterial
var highlight := StandardMaterial3D.new()
var triangles := {}
var drag := 0.0
var selecting := false
# Scene state (read by the guided session and the headless check).
var chapter := -1                                # index into data.chapters, -1 = free overview
var selected_sub := ""                           # free mode: one subsystem, "" = all
var isolated := false
var cutaway := false
var studies_on := true
var selected_mesh: MeshInstance3D
var visited := {}                                # chapter ids opened
var picked_studies := 0
var missing := 0                                 # published or study meshes without a classification record
var review: WfReviewGuide = null
var body := Node3D.new()                         # ship + study parts; chapter 5 turns it about the centre of mass (slews)
var gnc: WfM5Gnc = null                          # chapter 5 attitude / comms simulation (m5_gnc.gd)
var _panel_clock := 0.0
var sims := {}                                   # chapter index -> WfM6Sim (M6 chapters)
var by_id := {}                                  # node id -> MeshInstance3D
var display_opacity := {}                        # node id -> current display-pose opacity (exported drivers, baked)
var display_state := "COAST"
var target_focus := Vector3.ZERO
var target_radius := 300.0
var target_yaw := 0.62
var target_pitch := 0.42
var instant_camera := false                      # checks and captures snap the camera
var gnc_hud := PanelContainer.new()
var gnc_text := RichTextLabel.new()
# UI
var chapter_list := ItemList.new()
var sub_list := ItemList.new()
var sub_ids: Array[String] = []
var details := RichTextLabel.new()
var title_label := Label.new()
var toggles := {}

func _ready() -> void:
	WfInput.context = "holo"
	var canvas := CanvasLayer.new()
	add_child(canvas)
	title_label.position = Vector2(24, 18)
	title_label.add_theme_font_size_override("font_size", 17)
	title_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	canvas.add_child(title_label)
	if not FileAccess.file_exists(DATA) or not ResourceLoader.exists("res://generated/wayfarer.glb"):
		title_label.text = "M5 SUBSYSTEM HOLOGRAM\n\nGenerate the package from the repository root:\npython3 tools/workflow.py runtime-export"
		return
	data = JSON.parse_string(FileAccess.get_file_as_string(DATA))
	shader.code = WfHoloStyle.SUBSYSTEM_SHADER          # WEB-003: one shader for this scene and the hologram toggles
	highlight.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	highlight.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	highlight.albedo_color = Color(1.0, 1.0, 1.0, 0.55)
	var manifest = JSON.parse_string(FileAccess.get_file_as_string("res://generated/manifest.json"))
	var lo: Array = manifest.bounds_runtime_m.min
	var hi: Array = manifest.bounds_runtime_m.max
	home_focus = (Vector3(lo[0], lo[1], lo[2]) + Vector3(hi[0], hi[1], hi[2])) * 0.5
	focus = home_focus
	var records := {}
	for r in manifest.nodes:
		records[r.node] = r
	add_child(body)
	var ship: Node3D = load("res://generated/wayfarer.glb").instantiate()
	body.add_child(ship)
	WfProductionLayer.apply(ship, manifest)   # M7: production detail drawn near the camera only
	for item in ship.find_children("*", "MeshInstance3D", true, false):
		var id := str(item.name)
		var r: Dictionary = records.get(id, {})
		var n: Dictionary = data.nodes.get(id, {})
		if r.is_empty() or n.is_empty():
			push_error("M5 hologram: unclassified mesh " + id)
			missing += 1
			continue
		_add(item, id, n.s, n.c, r, false)
		if r.has("display"):                       # display poses (M6): hidden at their static COAST opacity until a chapter shows a state
			item.set_meta("rest", item.transform)
			display_opacity[id] = float(r.display.static_opacity)
	var studies: Node3D = load("res://generated/m5/m5_studies.glb").instantiate()
	body.add_child(studies)
	var parts := {}
	for p in data.studies.parts:
		parts[p.node] = p
	for item in studies.find_children("*", "MeshInstance3D", true, false):
		var p: Dictionary = parts.get(str(item.name), {})
		if p.is_empty():
			push_error("M5 hologram: unknown study part " + str(item.name))
			missing += 1
			continue
		_add(item, p.node, p.subsystem, p.color, p, true)
	for id in data.subsystems:
		sub_ids.append(id)
	sub_ids.sort()
	_environment()
	for ch in data.chapters:
		if ch.has("gnc"):
			gnc = WfM5Gnc.new(self, ch.gnc, body)
			add_child(gnc)
	for i in data.chapters.size():
		var block: Dictionary = data.chapters[i].get("m6", {})
		var sim: WfM6Sim = null
		match str(block.get("kind", "")):
			"eye": sim = WfM6Eye.new(self, block)
			"habitat":
				sim = WfM6Habitat.new(self, block)
				if sim.attach(ship, by_id) == 0:
					push_error("M6 habitat: no mesh turns with a rotor binding")
			"radiator":
				sim = WfM6Radiator.new(self, block)
				sim.attach(by_id)
		if sim != null:
			ship.add_child(sim)
			sims[i] = sim
	_build_ui(canvas)
	set_chapter(0)
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--chapter="):            # story scenes open a chapter directly (by id: eye, habitat, radiator, gnc, ...)
			var want := arg.trim_prefix("--chapter=")
			for i in data.chapters.size():
				if data.chapters[i].id == want:
					set_chapter(i)
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--review="):
			WfReviewGuide.pending = arg.trim_prefix("--review=")
	if WfReviewGuide.pending == "holo":
		WfReviewGuide.pending = ""
		review = WfReviewGuide.new(WfHoloSession.new(self))
		add_child(review)
		title_label.visible = false
		if "--check-review" in OS.get_cmdline_user_args():
			await check_review()
	if "--check-holo" in OS.get_cmdline_user_args():
		await check_holo()
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--capture="):
			await capture(arg.trim_prefix("--capture="))

func _process(dt: float) -> void:
	if not data.is_empty() and not instant_camera:
		var k := 1.0 - exp(-CAMERA_EASE * dt)
		if focus.distance_to(target_focus) > 0.01 or absf(radius - target_radius) > 0.01 or absf(angle_difference(yaw, target_yaw)) > 1e-3 \
				or absf(pitch - target_pitch) > 1e-3:
			focus = focus.lerp(target_focus, k)
			radius = lerpf(radius, target_radius, k)
			yaw = lerp_angle(yaw, target_yaw, k)
			pitch = lerpf(pitch, target_pitch, k)
			update_camera()
	if (gnc != null and gnc.active) or active_sim() != null:
		_panel_clock += dt
		if _panel_clock > 0.25:
			_panel_clock = 0.0
			_refresh_ui()

func _add(item: MeshInstance3D, id: String, sub: String, color: Array, record: Dictionary, study: bool) -> void:
	item.set_meta("node", id)
	item.set_meta("sub", sub)
	item.set_meta("study", study)
	item.set_meta("hidden_default", data.hidden.has(id))
	item.set_meta("gnc_display", str(record.get("kind", "")).begins_with("rcs_plume_cone"))
	info[id] = {"sub": sub, "color": Color(color[0], color[1], color[2]), "record": record}
	item.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	meshes.append(item)
	by_id[id] = item

func _material(c: Color, role: String) -> ShaderMaterial:
	var key := "%s|%s" % [c.to_html(false), role]
	if not materials.has(key):
		var m := ShaderMaterial.new()
		m.shader = shader
		m.set_shader_parameter("tint", Color(0.55, 0.62, 0.70) if role == "ghost" else c)
		m.set_shader_parameter("energy", ROLE_ENERGY.get(role, SUBJECT_ENERGY if role == "subject" else (OVERVIEW_ENERGY if role == "overview" else GHOST_ENERGY)))
		m.set_shader_parameter("flow", 1.0 if role == "flow" or role == "hot" else 0.0)
		materials[key] = m
	var mat: ShaderMaterial = materials[key]
	mat.set_shader_parameter("cut", cutaway and role == "ghost")
	return mat

func _environment() -> void:
	add_child(camera)
	camera.current = true
	camera.near = 0.1
	camera.far = 4000.0
	camera.fov = 45.0
	var world := WorldEnvironment.new()
	world.environment = Environment.new()
	world.environment.background_mode = Environment.BG_COLOR
	world.environment.background_color = Color(0.012, 0.02, 0.035)
	world.environment.glow_enabled = true
	world.environment.glow_intensity = 0.5
	add_child(world)

## The nodes shown as subjects now: the chapter's set, the selected subsystem's, or every classified node.
func subject_ids() -> Dictionary:
	var out := {}
	if chapter >= 0:
		for id in data.chapters[chapter].nodes:
			out[id] = true
	else:
		for id in info:
			if selected_sub == "" or info[id].sub == selected_sub:
				out[id] = true
	return out

func refresh() -> void:
	var subject := subject_ids()
	var sim := active_sim()
	var sim_tint: Dictionary = sim.tints() if sim != null else {}
	for item in meshes:
		var id: String = item.get_meta("node")
		var is_subject: bool = subject.has(id)
		var shown: bool = not item.get_meta("hidden_default") and (studies_on or not item.get_meta("study"))
		if item.get_meta("gnc_display") and not gnc_chapter():
			shown = false                         # RCS plume display cones belong to chapter 5 only
		if isolated and not is_subject:
			shown = false
		if display_opacity.has(id) and display_opacity[id] <= 0.001:
			shown = false                         # a display pose not shown in the current state
		if chapter < 0 and selected_sub == "" and info[id].sub == "CTX":
			is_subject = false                    # the overview draws the unclassified casing as context
		item.visible = shown
		if shown:
			var role := "ghost"
			if is_subject:
				role = "overview" if chapter < 0 and selected_sub == "" else "subject"
			var c: Color = info[id].color
			if role == "subject" and chapter >= 0 and data.chapters[chapter].tint.has(id):
				var t: Array = data.chapters[chapter].tint[id]
				c = Color(t[0], t[1], t[2])
			if role == "subject" and sim_tint.has(id):
				c = sim_tint[id][0]
				role = sim_tint[id][1]
			item.material_override = _material(c, role)
		item.material_overlay = highlight if item == selected_mesh else null
	for m in materials.values():
		m.set_shader_parameter("cut", cutaway and m.get_shader_parameter("energy") == GHOST_ENERGY)
	_refresh_ui()

func active_sim() -> WfM6Sim:
	return sims.get(chapter, null)

## Exported display pose (Blender drivers baked per named state): opacity, runtime-local offset, scale and gimbal turn from the rest pose.
func apply_display_state(name: String) -> void:
	display_state = name
	for id in display_opacity:
		var item: MeshInstance3D = by_id[id]
		var r: Dictionary = info[id].record
		var values: Dictionary = r.display.get("states", {}).get(name, {})
		display_opacity[id] = float(values.get("opacity", r.display.static_opacity))
		var rest: Transform3D = item.get_meta("rest")
		var factor := Vector3.ONE
		for k in 3:
			var key: String = "scale_" + "xyz"[k]
			if values.has(key):
				factor[k] = maxf(values[key], 1e-4)
		var turn := Basis.IDENTITY
		if values.has("turn"):
			var t: Array = values.turn
			turn = Basis(Vector3(t[0], t[3], t[6]), Vector3(t[1], t[4], t[7]), Vector3(t[2], t[5], t[8]))
		var off: Array = values.get("offset", [0.0, 0.0, 0.0])
		item.transform = Transform3D(turn * rest.basis * Basis.from_scale(factor), rest.origin + Vector3(off[0], off[1], off[2]))
	refresh()

func gnc_chapter() -> bool:
	return chapter >= 0 and data.chapters[chapter].has("gnc")

func set_chapter(i: int) -> void:
	chapter = i
	selected_sub = ""
	selected_mesh = null
	if i >= 0:
		visited[data.chapters[i].id] = true
	if gnc != null:
		gnc.set_active(gnc_chapter())
	for k in sims:
		if sims[k].active and k != i:
			sims[k].set_active(false)
	if sims.has(i):
		sims[i].set_active(true)
	refresh()
	frame_subject()

func select_sub(id: String) -> void:
	chapter = -1
	selected_sub = id
	selected_mesh = null
	refresh()
	frame_subject()

func step_sub(d: int) -> void:
	var i := sub_ids.find(selected_sub)
	select_sub(sub_ids[posmod(i + d, sub_ids.size())] if i >= 0 else sub_ids[0 if d > 0 else sub_ids.size() - 1])

func toggle_isolate() -> void:
	isolated = not isolated
	refresh()

func toggle_cutaway() -> void:
	cutaway = not cutaway
	refresh()

func toggle_studies() -> void:
	studies_on = not studies_on
	if not studies_on and selected_mesh != null and selected_mesh.get_meta("study"):
		selected_mesh = null
	refresh()

func frame_subject() -> void:
	var subject := subject_ids()
	var box := AABB()
	var first := true
	for item in meshes:
		if item.visible and subject.has(item.get_meta("node")):
			var b: AABB = item.global_transform * item.get_aabb()
			box = b if first else box.merge(b)
			first = false
	var hint: Dictionary = active_sim().frame_hint() if active_sim() != null else {}
	target_yaw = yaw
	target_pitch = pitch
	if not hint.is_empty():                       # M6 chapters: a composed view (the shadow over the ship, the rings, the blades)
		target_focus = hint.focus
		target_radius = hint.radius
		target_yaw = hint.yaw
		target_pitch = hint.pitch
	elif first:
		target_focus = home_focus
		target_radius = 300.0
	else:
		target_focus = box.get_center()
		var view := get_viewport().get_visible_rect().size
		var aspect := maxf(0.3, (view.x - 380.0) / view.y)
		var half := atan(tan(deg_to_rad(camera.fov * 0.5)) * minf(1.0, aspect))
		target_radius = clampf(box.size.length() * 0.55 / sin(half), 4.0, 900.0)
	if instant_camera or data.is_empty():
		focus = target_focus
		radius = target_radius
		yaw = target_yaw
		pitch = target_pitch
	update_camera()

func update_camera() -> void:
	camera.position = focus + radius * Vector3(sin(yaw) * cos(pitch), sin(pitch), cos(yaw) * cos(pitch))
	camera.look_at(focus)
	camera.h_offset = radius * 0.12                  # the subject sits left of the side panel

func _unhandled_input(event: InputEvent) -> void:
	if data.is_empty():
		return
	if event is InputEventMouseButton:
		if event.button_index == MOUSE_BUTTON_LEFT:
			if event.pressed:
				drag = 0.0
				selecting = not event.shift_pressed
			elif selecting:
				if drag < 5.0:
					pick_at(event.position)
				selecting = false
		if event.pressed and event.button_index == MOUSE_BUTTON_WHEEL_UP:
			radius = maxf(2.0, radius / 1.12)
			target_radius = radius
		elif event.pressed and event.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			radius = minf(1500.0, radius * 1.12)
			target_radius = radius
	if event is InputEventMouseMotion:
		if event.button_mask & MOUSE_BUTTON_MASK_LEFT:
			drag += event.relative.length()
		if event.button_mask & MOUSE_BUTTON_MASK_MIDDLE or (event.button_mask & MOUSE_BUTTON_MASK_LEFT and event.shift_pressed):
			focus += (-camera.basis.x * event.relative.x + camera.basis.y * event.relative.y) * radius * 0.001
			target_focus = focus
		elif event.button_mask & MOUSE_BUTTON_MASK_LEFT and drag >= 5.0:
			yaw -= event.relative.x * 0.006
			pitch = clampf(pitch + event.relative.y * 0.006, -1.55, 1.55)
			target_yaw = yaw
			target_pitch = pitch
	if WfInput.pressed(event):
		var k := WfInput.key_of(event, ["holo"])
		match k:
			KEY_1, KEY_2, KEY_3, KEY_4, KEY_5, KEY_6, KEY_7, KEY_8:
				if k - KEY_1 < data.chapters.size():
					set_chapter(k - KEY_1)
			KEY_M, KEY_U, KEY_R, KEY_BRACKETLEFT, KEY_BRACKETRIGHT:
				if gnc != null and gnc_chapter():
					match k:
						KEY_M: gnc.cycle_mode()
						KEY_U: gnc.toggle_burn()
						KEY_R: gnc.cycle_range()
						KEY_BRACKETLEFT: gnc.cycle_warp(-1)
						KEY_BRACKETRIGHT: gnc.cycle_warp(1)
					_refresh_ui()
			KEY_N, KEY_X, KEY_V, KEY_K:
				var sim := active_sim()
				if sim != null:
					match k:
						KEY_N: sim.next_state()
						KEY_X: sim.event()
						KEY_V: sim.response()
						KEY_K: sim.loop()
					_refresh_ui()
			KEY_0, KEY_HOME: set_chapter(-1)
			KEY_PERIOD: step_sub(1)
			KEY_COMMA: step_sub(-1)
			KEY_I: toggle_isolate()
			KEY_C:
				if review == null or review.complete or review.index >= 2:   # the guide refuses the cutaway before step 3
					toggle_cutaway()
			KEY_B: toggle_studies()
			KEY_F: frame_subject()
			KEY_ESCAPE:
				if selected_mesh != null:
					selected_mesh = null
					refresh()
				else:
					get_tree().change_scene_to_file("res://scenes/review.tscn")
	update_camera()

func pick_at(p: Vector2) -> void:
	var origin := camera.project_ray_origin(p)
	var dir := camera.project_ray_normal(p)
	var best := INF
	var chosen: MeshInstance3D = null
	for item in meshes:
		if not item.is_visible_in_tree() or item.mesh == null:
			continue
		var inv := item.global_transform.affine_inverse()
		var lo := inv * origin
		var ld := inv.basis * dir
		if item.get_aabb().intersects_ray(lo, ld) == null:
			continue
		if not triangles.has(item.mesh):
			triangles[item.mesh] = item.mesh.generate_triangle_mesh()
		var hit: Dictionary = triangles[item.mesh].intersect_ray(lo, ld)
		if not hit.is_empty():
			var world_hit: Vector3 = item.global_transform * hit.position
			if cutaway and world_hit.y > 0.0 and not subject_ids().has(item.get_meta("node")):
				continue                           # cut away: the clipped half is not there to click
			var d := origin.distance_to(world_hit)
			if d < best:
				best = d
				chosen = item
	select_mesh(chosen)

func select_mesh(item: MeshInstance3D) -> void:
	selected_mesh = item
	if item != null and item.get_meta("study"):
		picked_studies += 1
	refresh()

# ---- UI -------------------------------------------------------------------------------------------------------------------------

func _build_ui(canvas: CanvasLayer) -> void:
	var panel := PanelContainer.new()
	canvas.add_child(panel)
	panel.set_anchors_and_offsets_preset(Control.PRESET_RIGHT_WIDE)
	panel.offset_left = -380
	panel.offset_right = -12
	panel.offset_top = 12
	panel.offset_bottom = -12
	var scroll := ScrollContainer.new()
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	panel.add_child(scroll)
	var col := VBoxContainer.new()
	col.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	col.add_theme_constant_override("separation", 6)
	scroll.add_child(col)
	col.add_child(_heading("SUBSYSTEM CHAPTERS  ·  M5 and M6"))
	chapter_list.custom_minimum_size = Vector2(340, 0)
	chapter_list.auto_height = true
	chapter_list.focus_mode = Control.FOCUS_NONE
	for i in data.chapters.size():
		chapter_list.add_item("%d  %s" % [i + 1, data.chapters[i].title])
	chapter_list.item_selected.connect(func(i: int): set_chapter(i))
	col.add_child(chapter_list)
	col.add_child(_heading("SUBSYSTEMS  ·  overlay colour, not material"))
	sub_list.custom_minimum_size = Vector2(340, 200)
	sub_list.focus_mode = Control.FOCUS_NONE
	for id in sub_ids:
		var s: Dictionary = data.subsystems[id]
		var img := Image.create(12, 12, false, Image.FORMAT_RGB8)
		img.fill(Color(s.color[0], s.color[1], s.color[2]))
		sub_list.add_item("%s  %s" % [id, s.name], ImageTexture.create_from_image(img))
	sub_list.item_selected.connect(func(i: int): select_sub(sub_ids[i]))
	col.add_child(sub_list)
	var row := HFlowContainer.new()
	col.add_child(row)
	for t in [["all", "Whole ship · 0", func(): set_chapter(-1)], ["isolate", "Isolate · I", toggle_isolate],
			["cutaway", "Dorsal cutaway · C", toggle_cutaway], ["studies", "Study parts · B", toggle_studies]]:
		var b := Button.new()
		b.text = t[1]
		b.focus_mode = Control.FOCUS_NONE
		b.toggle_mode = t[0] != "all"
		b.pressed.connect(t[2])
		row.add_child(b)
		toggles[t[0]] = b
	var back := Button.new()
	back.text = "Review sessions"
	back.focus_mode = Control.FOCUS_NONE
	back.pressed.connect(func(): get_tree().change_scene_to_file("res://scenes/review.tscn"))
	row.add_child(back)
	gnc_hud.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_LEFT)
	gnc_hud.offset_left = 16
	gnc_hud.offset_right = 16 + 780
	gnc_hud.offset_top = -300
	gnc_hud.offset_bottom = -16
	gnc_hud.mouse_filter = Control.MOUSE_FILTER_IGNORE
	gnc_text.bbcode_enabled = true
	gnc_text.fit_content = true
	gnc_text.scroll_active = false
	gnc_text.mouse_filter = Control.MOUSE_FILTER_IGNORE
	gnc_text.add_theme_font_size_override("normal_font_size", 14)
	gnc_text.add_theme_font_size_override("bold_font_size", 15)
	gnc_hud.add_child(gnc_text)
	gnc_hud.visible = false
	canvas.add_child(gnc_hud)
	details.bbcode_enabled = true
	details.fit_content = true
	details.custom_minimum_size = Vector2(340, 0)
	details.add_theme_font_size_override("normal_font_size", 13)
	col.add_child(details)

func _heading(t: String) -> Label:
	var l := Label.new()
	l.text = t
	l.add_theme_font_size_override("font_size", 13)
	l.add_theme_color_override("font_color", WfReviewGuide.C_MUTED)
	return l

static func badge_bb(status: String, text: String) -> String:
	var c: Color = WfReviewGuide.STATUS_COLORS[WfReviewGuide.status_family(status)]
	return "[color=#%s][b]%s[/b][/color] %s" % [c.to_html(false), status, text]

func _refresh_ui() -> void:
	toggles.isolate.set_pressed_no_signal(isolated)
	toggles.cutaway.set_pressed_no_signal(cutaway)
	toggles.studies.set_pressed_no_signal(studies_on)
	chapter_list.deselect_all()
	sub_list.deselect_all()
	var lines: Array[String] = []
	if chapter >= 0:
		var ch: Dictionary = data.chapters[chapter]
		chapter_list.select(chapter)
		lines.append("[b]%s[/b]" % ch.title)
		for b in ch.badges:
			lines.append(badge_bb(b[0], b[1]))
		for g in ch.legend:
			lines.append("[color=#%s]■[/color] %s" % [Color(g[0][0], g[0][1], g[0][2]).to_html(false), g[1]])
		for l in ch.lines:
			lines.append("· " + l)
	elif selected_sub != "":
		sub_list.select(sub_ids.find(selected_sub))
		var s: Dictionary = data.subsystems[selected_sub]
		lines.append("[b]%s  %s[/b]" % [selected_sub, s.name])
		lines.append(badge_bb(s.maturity.split(" ")[0], s.maturity))
		lines.append("[color=#888780]Sources: %s[/color]" % s.sources)
	else:
		lines.append("[b]Whole ship, twelve subsystems[/b]")
		lines.append(badge_bb("PROTOTYPE", "REP_PROXY geometry; colours explain function, never materials"))
	if selected_mesh != null:
		var id: String = selected_mesh.get_meta("node")
		var r: Dictionary = info[id].record
		lines.append("")
		lines.append("[b]%s[/b]  (%s)" % [r.get("source_name", r.get("name", id)), info[id].sub])
		lines.append(badge_bb(str(r.get("canon_status", "OPEN")), "source status · ref %s" % r.get("source_ref", "none")))
		lines.append(badge_bb(str(r.get("geometry_status", "PROTOTYPE")), "geometry · kind %s" % r.get("kind", "")))
		if r.has("note") and str(r.note) != "":
			lines.append("[color=#888780]%s[/color]" % r.note)
	lines.append("")
	lines.append("[color=#888780]%s · %s[/color]" % [data.status, WfInput.keys("{holo.chapter_1}-{holo.chapter_8} chapters · {holo.next}/{holo.prev} subsystems · click a part")])
	details.text = "\n".join(lines)
	var sim := active_sim()
	gnc_hud.visible = (gnc != null and gnc_chapter()) or sim != null
	if sim != null:
		var keys: Array[String] = []
		for c in sim.controls():
			keys.append("[b]%s[/b] %s" % [WfInput.label(c[0]), c[1]])
		gnc_text.text = "\n".join(sim.panel_lines()) + "\n[color=#888780]" + "  ·  ".join(keys) + "[/color]"
	elif gnc_hud.visible:
		gnc_text.text = "\n".join(gnc.panel_lines())
	var mode := "chapter %d" % (chapter + 1) if chapter >= 0 else (selected_sub if selected_sub != "" else "whole ship")
	title_label.text = "WAYFARER 001  ·  SUBSYSTEM HOLOGRAM  ·  %s%s%s%s\nDrag: orbit · Shift-drag: pan · Wheel: zoom · F: frame · Esc: back" % [mode,
		"  ·  ISOLATED" if isolated else "", "  ·  CUTAWAY" if cutaway else "", "" if studies_on else "  ·  studies hidden"]

# ---- checks ---------------------------------------------------------------------------------------------------------------------

## Headless (WF_GODOT_HOLO): every published mesh is classified, the study parts load, each chapter has subjects, isolation hides only
## non-subjects, the cutaway clips only context, studies toggle, and no imported material was replaced (instance overrides only).
func check_holo() -> void:
	await get_tree().process_frame
	var out := {"meshes": meshes.size(), "studies": meshes.filter(func(m): return m.get_meta("study")).size(), "chapters": {}}
	var visible_before := meshes.filter(func(m): return m.visible).size()
	for i in data.chapters.size():
		set_chapter(i)
		var subj := subject_ids()
		var shown := meshes.filter(func(m): return m.visible and subj.has(m.get_meta("node"))).size()
		isolated = true
		refresh()
		var leak := meshes.filter(func(m): return m.visible and not subj.has(m.get_meta("node"))).size()
		isolated = false
		refresh()
		out.chapters[data.chapters[i].id] = {"subjects": shown, "isolation_leaks": leak}
	set_chapter(1)
	cutaway = true
	refresh()
	var cut_ok := materials.values().all(func(m): return m.get_shader_parameter("cut") == (m.get_shader_parameter("energy") == GHOST_ENERGY))
	cutaway = false
	toggle_studies()
	var studies_hidden := meshes.filter(func(m): return m.get_meta("study") and m.visible).size() == 0
	toggle_studies()
	var field_hidden := meshes.filter(func(m): return m.get_meta("hidden_default") and m.visible).size() == 0
	var untouched := meshes.all(func(m): return m.mesh == null or range(m.mesh.get_surface_count()).all(func(s): return m.get_surface_override_material(s) == null))
	var gn := gnc_check() if gnc != null else {"result": "MISSING"}
	var m6 := m6_check()
	set_chapter(-1)
	out.gnc = gn
	out.m6 = m6
	out.merge({"visible_overview": visible_before, "cutaway_context_only": cut_ok, "studies_toggle": studies_hidden,
		"field_envelope_hidden": field_hidden and data.hidden.size() > 0, "imported_materials_untouched": untouched, "unclassified": missing})
	var ok: bool = missing == 0 and out.studies == data.studies.parts.size() and out.chapters.values().all(func(c): return c.subjects > 0 and c.isolation_leaks == 0) \
		and cut_ok and studies_hidden and out.field_envelope_hidden and untouched and gn.result == "PASS" and m6.result == "PASS"
	out.result = "PASS" if ok else "FAIL"
	print("WF_GODOT_HOLO " + JSON.stringify(out))
	get_tree().quit(0 if ok else 1)

## Chapter 5 on the mission clock (no frames): coast contact at 30 AU, a burn is an outage that grows the backlog, store and forward
## delivers the outage data no sooner than one light time after contact returns, slews run at the reference rate, MAINTENANCE_HOLD and a
## slew refuse a burn, the aft jets are inhibited in the hold, the B1F start / stop jets exist as cones and every rate stays null.
func gnc_check() -> Dictionary:
	var gi := -1
	for i in data.chapters.size():
		if data.chapters[i].has("gnc"):
			gi = i
	set_chapter(gi)
	var s := gnc
	s.active = false                                      # drive the clock by hand
	s.dist_i = s.g.distances_au.find(30.0)
	s.step(3600.0)
	var coast: bool = s.contact.values().any(func(v): return v)
	s.toggle_burn()
	s.step(6 * 3600.0)
	var blocked: bool = s.burning and not s.contact.values().any(func(v): return v)
	var backlog_burn: float = s.backlog_s()
	s.toggle_burn()
	s.step(600.0)
	var back_on: float = s.t
	var waited := 0.0
	while s.earth_newest < s.last_outage[1] - 1.0 and waited < 3 * 86400.0:
		s.step(600.0)
		waited += 600.0
	var delivered: bool = s.earth_newest >= s.last_outage[1] - 1.0 and s.t - back_on >= s.light_s() - 600.0
	var drained: bool = s.backlog_s() < 1200.0
	s.cycle_mode()
	s.toggle_burn()
	var slew_refuses: bool = not s.burning and s.refused != ""
	s.step(SLEW_PROBE_S)
	var rate_ok: bool = absf(s.yaw - 0.05 * SLEW_PROBE_S) < 0.01
	s.step(3000.0)
	var slewed: bool = absf(s.yaw - 90.0) < 1e-6
	s.cycle_mode()
	s.toggle_burn()
	var hold_refuses: bool = not s.burning and s.refused != ""
	s._cones()
	var aft: Array = s.cones.keys().filter(func(n): return "_Aft_" in n and n.begins_with("Study_"))
	var b1f: Array = s.g.rcs_patterns.B1F["yaw+"].jets
	var cones_ok: bool = b1f.all(func(j): return s.cones.has(str(j).replace("Study_RCSBF_Fwd_", "Study_RCSB_Fwd_")))
	var nulls: bool = s.g.scenarios.all(func(x): return x.achieved_kbps == null) and s.g.backlog.bytes == null and s.g.backlog.achieved_kbps == null
	var out := {"coast_contact_30au": coast, "burn_outage": blocked, "backlog_after_6h_burn_h": snappedf(backlog_burn / 3600.0, 0.01),
		"store_forward_delivered": delivered, "wait_after_contact_h": snappedf(waited / 3600.0, 0.1), "light_time_h": snappedf(s.light_s() / 3600.0, 0.01),
		"backlog_drained": drained, "slew_rate_ok": rate_ok, "slew_reached_90": slewed, "slew_refuses_burn": slew_refuses,
		"hold_refuses_burn": hold_refuses, "aft_cones": aft.size(), "b1f_cones": cones_ok, "rates_null": nulls, "cones": s.cones.size()}
	out.result = "PASS" if coast and blocked and backlog_burn > 5.9 * 3600.0 and delivered and drained and rate_ok and slewed \
		and slew_refuses and hold_refuses and aft.size() > 0 and cones_ok and nulls else "FAIL"
	return out

func chapter_of(kind: String) -> int:
	for i in sims:
		if sims[i].m.kind == kind:
			return i
	return -1

## M6 chapters on their own clocks (no frames). EYE: each exported pose moves or shows its own parts and COAST restores them; the shadow
## verdict follows the built-model limit; dust stops on the Brow. Habitat: the rings counter-rotate at the sourced rate, a spin-down lands
## on an index angle with no spin gravity, the crew marker reaches the ring at about the floor gravity. Radiators: the fault order damages
## distinct cells on every blade, isolation lowers the measured in-service share by those cells, a loop takes about a third, requalify
## restores it; heat rejection stays null.
func m6_check() -> Dictionary:
	var out := {}
	instant_camera = true
	# EYE
	var ei := chapter_of("eye")
	set_chapter(ei)
	var e: WfM6Eye = sims[ei]
	var shutters: Array = meshes.filter(func(x): return info[x.get_meta("node")].record.get("kind", "") == "eye_shutter")
	var damage: Array = meshes.filter(func(x): return info[x.get_meta("node")].record.get("kind", "") == "damage_cell")
	var moved := func(): return shutters.filter(func(x): return x.transform.origin.distance_to(x.get_meta("rest").origin) > 0.1).size()
	while e.state_name() != "EYE_SHUTTERS_CLOSED":
		e.next_state()
	var closed: int = moved.call()
	while e.state_name() != "SHIELD_DAMAGED":
		e.next_state()
	var damage_shown := damage.filter(func(x): return x.visible).size()
	while e.state_name() != "COAST":
		e.next_state()
	var restored: bool = moved.call() == 0 and damage.filter(func(x): return x.visible).size() == 0
	e.error_i = e.m.errors_deg.find(0.2)
	var protected_at_target := not e.exposed()
	e.error_i = e.m.errors_deg.find(3.0)
	var exposed_at_3 := e.exposed()
	e.error_i = 0
	e.event()
	for k in 400:
		e.step(0.05)
	e.event()
	out.eye = {"shutters_closed": closed, "damage_cells_shown": damage_shown, "coast_restored": restored, "protected_at_0p2": protected_at_target,
		"exposed_at_3": exposed_at_3, "worst_limit_deg": snappedf(e.worst_limit(), 0.001), "dust_absorbed": e.absorbed}
	var eye_ok: bool = closed == shutters.size() and closed > 0 and damage_shown == damage.size() and damage_shown > 0 and restored \
		and protected_at_target and exposed_at_3 and e.absorbed > 0 and e.m.unknown.field_strength == null
	# Habitat
	var hi := chapter_of("habitat")
	set_chapter(hi)
	var h: WfM6Habitat = sims[hi]
	var a0 := h.angle
	h.step(1.0)
	var turned := h.angle - a0
	var counter: bool = h.pivots[0].node.basis.is_equal_approx(Basis(h.pivots[0].axis, h.ring_angle(0))) and absf(h.ring_angle(1) + h.ring_angle(0)) < 1e-5
	h.event()
	var g_ring := 0.0
	for k in 3000:
		h.step(0.25)
		var at := h.walker()
		if at.zone == "aisle":
			g_ring = h.local_g(at)
			break
	h.next_state()
	for k in 4000:
		h.step(0.05)
		if h.locked:
			break
	var at_lock := h.walker()
	var lock_err := absf(fposmod(h.angle + 0.5 * h.lock_step(), h.lock_step()) - 0.5 * h.lock_step())
	var g_locked := h.local_g(at_lock)
	var was_locked := h.locked
	h.next_state()
	h.step(h.RAMP_S + 1.0)
	out.habitat = {"rad_per_s": snappedf(turned, 1e-4), "omega": h.omega, "counter_rotating": counter, "ring_nodes": h.pivots.map(func(p): return p.node.get_child_count()),
		"aisle_g": snappedf(g_ring, 0.001), "locked": was_locked, "lock_error_rad": snappedf(lock_err, 1e-6), "locked_g": g_locked, "respun": h.f}
	var hab_ok: bool = absf(turned - h.omega) < 1e-3 and counter and h.pivots.all(func(p): return p.node.get_child_count() > 100) \
		and g_ring > 0.4 and g_ring <= h.m.floor_gravity_g + 1e-3 and was_locked and lock_err < 1e-4 and g_locked == 0.0 and h.f == 1.0 and h.m.unknown.spin_down_s == null
	# Radiators
	var ri := chapter_of("radiator")
	set_chapter(ri)
	var r: WfM6Radiator = sims[ri]
	var steps := 0
	for k in r.m.steps.size():
		r.next_state()
		steps += 1
	var share0 := r.service_share()
	for k in 3:
		r.event()
	var damaged := r.count("DAMAGED")
	var blades := {}
	for c in r.cells:
		if r.state[c.id] == "DAMAGED":
			blades[c.blade] = true
	r.response()
	var share_iso := r.service_share()
	var iso_area := 0.0
	for c in r.cells:
		if r.state[c.id] == "ISOLATED":
			iso_area += c.area
	r.loop()
	var share_loop := r.service_share()
	r.loop()
	r.response()
	var share_back := r.service_share()
	var per_blade := {}
	for c in r.cells:
		per_blade[c.blade] = per_blade.get(c.blade, 0) + 1
	out.radiator = {"steps": steps, "damaged": damaged, "blades_hit": blades.size(), "share_isolated": snappedf(share_iso, 1e-4),
		"isolated_area_share": snappedf(iso_area / r.total_area, 1e-4), "share_loop_out": snappedf(share_loop, 1e-4), "share_restored": snappedf(share_back, 1e-6),
		"cells_per_blade": per_blade.values(), "planform_m2": snappedf(r.total_area, 0.1), "rejection_null": r.m.unknown.rejection_margin_W == null}
	var rad_ok: bool = steps == 5 and damaged == 3 * r.PER_PRESS and blades.size() == 3 and absf(1.0 - share_iso - iso_area / r.total_area) < 1e-6 \
		and share_loop < share_iso - 0.3 and share_loop > share_iso - 0.36 and absf(share_back - 1.0) < 1e-9 and per_blade.values().all(func(n): return n == 160) \
		and r.m.unknown.rejection_margin_W == null and r.m.unknown.drive_waste_heat_W == null
	instant_camera = false
	out.result = "PASS" if eye_ok and hab_ok and rad_ok else "FAIL"
	out.parts = {"eye": eye_ok, "habitat": hab_ok, "radiator": rad_ok}
	return out

## Guided session headless: chapters, isolate, cutaway, a picked study part and the load-path chapter through real key events.
func check_review() -> void:
	var s: WfHoloSession = review.session
	review.press(KEY_C)                                   # refused: cutaway before a chapter is opened by the reviewer
	await get_tree().process_frame
	var refused := not review.last_ok
	for k in [KEY_2, KEY_I, KEY_I, KEY_C, KEY_C]:
		review.press(k)
		for f in 3:
			await get_tree().process_frame
	var part: MeshInstance3D = meshes.filter(func(m): return m.get_meta("study") and m.visible and subject_ids().has(m.get_meta("node")))[0]
	select_mesh(part)                                     # the pick handler's result, as a click resolves it
	await get_tree().process_frame
	for k in [KEY_4, KEY_B, KEY_B, KEY_5, KEY_BRACKETRIGHT, KEY_BRACKETRIGHT, KEY_BRACKETRIGHT, KEY_U]:
		review.press(k)
		for f in 3:
			await get_tree().process_frame
	for f in 600:                                         # the backlog grows on the mission clock
		if review.index > 7:
			break
		await get_tree().process_frame
	review.press(KEY_U)
	for f in 900:                                         # contact returns; the outage data needs one light time to reach Earth
		if review.index > 8:
			break
		await get_tree().process_frame
	for k in [KEY_M, KEY_M]:
		review.press(k)
		for f in 3:
			await get_tree().process_frame
	for k in [KEY_6, KEY_N, KEY_X, KEY_V, KEY_V, KEY_V, KEY_V, KEY_V, KEY_7, KEY_X, KEY_N]:
		review.press(k)
		for f in 3:
			await get_tree().process_frame
	for f in 600:                                         # the spin-down lands on an index angle (the check drives the clock)
		if review.index > 12:
			break
		active_sim().step(0.25)
		await get_tree().process_frame
	for k in [KEY_8, KEY_X, KEY_V]:
		review.press(k)
		for f in 3:
			await get_tree().process_frame
	var out := {"session": "holo", "steps": review.events, "complete": review.complete, "refusal_shown": refused, "gnc_t_h": snappedf(gnc.t / 3600.0, 0.1),
		"labels": range(s.steps.size()).map(func(i): return s.labels(i))}
	out.labelled = range(s.steps.size()).all(func(i): return not s.labels(i).is_empty())
	out.result = "PASS" if review.complete and refused and out.labelled else "FAIL"
	print("WF_GODOT_REVIEW " + JSON.stringify(out))
	get_tree().quit(0 if out.result == "PASS" else 1)

func capture(dir: String) -> void:
	DirAccess.make_dir_recursive_absolute(dir)
	var only := ""
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--shots="):
			only = arg.trim_prefix("--shots=")
	instant_camera = true
	var ei := chapter_of("eye")
	var hi := chapter_of("habitat")
	var ri := chapter_of("radiator")
	var shots := [[-1, false, "overview"], [0, false, "thrust"], [1, true, "fuel_cutaway"], [2, false, "cryo"], [3, false, "loadpath"],
		[4, false, "gnc_forward"], [4, false, "gnc_burn"], [4, false, "gnc_slew"], [4, false, "gnc_hold"],
		[ei, false, "eye_watch"], [ei, false, "eye_exposed"], [ei, false, "eye_closed"], [ei, false, "eye_crown"], [ei, false, "eye_damaged"],
		[hi, false, "habitat_spin"], [hi, true, "habitat_walk"], [hi, false, "habitat_locked"],
		[ri, false, "radiator_flow"], [ri, false, "radiator_hot"], [ri, false, "radiator_isolated"]]
	for s in shots:
		if only != "" and not str(s[2]).begins_with(only):
			continue
		set_chapter(s[0])
		cutaway = s[1]
		if s[2] == "gnc_burn":
			gnc.toggle_burn()
			gnc.step(4 * 3600.0)
		elif s[2] == "gnc_slew":
			gnc.toggle_burn()
			gnc.cycle_mode()
			gnc.step(900.0)
		elif s[2] == "gnc_hold":
			gnc.cycle_mode()
			gnc.step(3600.0)
		elif s[2] == "eye_watch":
			sims[ei].event()
			for k in 60:
				sims[ei].step(0.05)
		elif s[2] == "eye_exposed":
			sims[ei].error_i = sims[ei].m.errors_deg.size() - 1
			for k in 30:
				sims[ei].step(0.05)
		elif s[2] in ["eye_closed", "eye_crown", "eye_damaged"]:
			var want: String = {"eye_closed": "EYE_SHUTTERS_CLOSED", "eye_crown": "CROWN_ENGAGED", "eye_damaged": "SHIELD_DAMAGED"}[s[2]]
			sims[ei].error_i = 0
			while sims[ei].state_name() != want:
				sims[ei].next_state()
		elif s[2] == "habitat_spin":
			sims[hi].step(2.0)
		elif s[2] == "habitat_walk":
			sims[hi].event()
			for k in 400:
				sims[hi].step(0.25)
				if sims[hi].walker().zone == "aisle":
					break
		elif s[2] == "habitat_locked":
			sims[hi].next_state()
			for k in 4000:
				sims[hi].step(0.05)
				if sims[hi].locked:
					break
		elif s[2] == "radiator_hot":
			while sims[ri].step_id() != "HIGH_POWER_REJECTION":
				sims[ri].next_state()
		elif s[2] == "radiator_isolated":
			for k in 4:
				sims[ri].event()
			sims[ri].response()
			sims[ri].event()
			sims[ri].loop()
		refresh()
		var sim := active_sim()
		if sim != null:
			sim.redraw()
		for f in 4:
			await RenderingServer.frame_post_draw
		get_viewport().get_texture().get_image().save_png(dir.path_join("holo_%s.png" % s[2]))
	get_tree().quit()
