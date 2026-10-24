extends Node3D
## Wayfarer accessory review viewer (docs/ACCESSORIES.md). Loads the drone body GLBs and the EVA handoff scene from res://generated/
## at run time (GLTFDocument; no editor import), lists the nine class designs and their actions, and labels every motion as a
## SIMULATION_ONLY display and every interface as unverified. Presentation only: it holds no spacecraft facts; the manifest carries them.
##   godot --path accessories/viewer                      interactive (drag: orbit, wheel: zoom, F: frame)
##   godot --headless --path accessories/viewer -- --check     load every entry and play every action, print PASS or ERROR lines
##   godot --path accessories/viewer -- --shots <dir>     one screenshot per entry at its main action (needs a display, e.g. xvfb-run)

const GEN := "res://generated/"
const LOCKED := "LOCKED_NOT_SUITED_EVA"
const BANNER := "WAYFARER ACCESSORY REVIEW  ·  PROTOTYPE design candidates, NOT INTEGRATED (DGT-017 HOLD)  ·  motions SIMULATION_ONLY  ·  GU-SIF proposed, not approved (DGT-012 HOLD)  ·  FLIGHT_EVA HOLD"
const GROUPS := [["DR-IVA-", "Interior drones (IVA)"], ["DR-EVA-", "Exterior crawlers (EVA)"], ["DR-FIX-", "Fixed service arms"],
		["WAYFARER_EVA", "EVA suit"], ["SCENE-", "Review scenes"]]
const SIDE_W := 400.0
const C_HEAD := Color(0.6, 0.75, 0.9)
const C_DIM := Color(0.6, 0.66, 0.72)
const C_SIM := Color(0.95, 0.75, 0.4)
const C_LOCK := Color(1.0, 0.5, 0.38)

var manifest := {}
var entries: Array = []
var current: Node3D
var anim: AnimationPlayer
var cam: Camera3D
var tag: Label3D
var floor_node: MeshInstance3D
var post: MeshInstance3D
var post_label: Label3D
var yaw := -0.75
var pitch := 0.32
var dist := 2.0
var focus := Vector3.ZERO
var dragging := false
var ui_designs: Tree
var ui_actions: Tree
var ui_status: RichTextLabel
var ui_info: RichTextLabel
var ui_loop: CheckBox
var ui_view: Control                                    # the free 3D area between the two columns: the camera centres the model in it
var design_items: Array = []
var action_items: Array = []
var act_line := ""                                      # status card: what the model is doing
var note_line := ""                                     # status card: the last refusal or error
var selected := -1


func _ready() -> void:
	_build_world()
	_build_ui()
	var f := FileAccess.open(GEN + "accessories.json", FileAccess.READ)
	if f == null:
		printerr("ERROR: generated/accessories.json missing: run `python3 tools/accessory_viewer.py stage` first")
		get_tree().quit(1)
		return
	manifest = JSON.parse_string(f.get_as_text())
	entries = manifest["entries"]
	_fill_designs()
	var args := OS.get_cmdline_user_args()
	if "--check" in args:
		_check()
		return
	if "--shots" in args:
		_shots(args[args.find("--shots") + 1])
		return
	_pick_design(0)


# ------------------------------------------------------------------------------------------------------------------------- world
func _build_world() -> void:
	var env := WorldEnvironment.new()
	var e := Environment.new()
	e.background_mode = Environment.BG_COLOR
	e.background_color = Color(0.025, 0.035, 0.05)
	e.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	e.ambient_light_color = Color(0.55, 0.58, 0.62)
	e.ambient_light_energy = 0.35
	e.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	env.environment = e
	add_child(env)
	for spec in [[Vector3(-50, -35, 0), 1.0, true], [Vector3(-25, 140, 0), 0.35, false]]:
		var sun := DirectionalLight3D.new()
		sun.rotation_degrees = spec[0]
		sun.light_energy = spec[1]
		sun.shadow_enabled = spec[2]
		add_child(sun)
	var floor := MeshInstance3D.new()
	floor_node = floor
	var pm := PlaneMesh.new()
	pm.size = Vector2(12, 12)
	floor.mesh = pm
	var fm := StandardMaterial3D.new()
	fm.albedo_color = Color(0.07, 0.075, 0.085)
	fm.roughness = 0.95
	floor.material_override = fm
	floor.name = "Floor"
	add_child(floor)
	# 1.78 m scale post with 0.1 m ticks (the suited instructor's stature) beside the model
	post = MeshInstance3D.new()
	var cm := CylinderMesh.new()
	cm.top_radius = 0.012
	cm.bottom_radius = 0.012
	cm.height = 1.78
	post.mesh = cm
	post.position = Vector3(-1.0, 0.89, 0.0)
	var pmat := StandardMaterial3D.new()
	pmat.albedo_color = Color(0.92, 0.36, 0.06)
	post.material_override = pmat
	post.name = "ScalePost"
	add_child(post)
	var lbl := Label3D.new()
	post_label = lbl
	lbl.text = "1.78 m"
	lbl.font_size = 28
	lbl.pixel_size = 0.002
	lbl.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	lbl.position = Vector3(-1.0, 1.86, 0.0)
	add_child(lbl)
	tag = Label3D.new()
	tag.font_size = 36
	tag.pixel_size = 0.002
	tag.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	tag.modulate = Color(0.85, 0.9, 1.0)
	add_child(tag)
	cam = Camera3D.new()
	cam.fov = 40
	add_child(cam)
	cam.make_current()


func _build_ui() -> void:
	# Layout: gate bar across the top; left column (designs, actions); free 3D view; right column (status card, details). Containers
	# only, so nothing overlaps or runs under another panel at any window size; long text wraps instead of being cut.
	var layer := CanvasLayer.new()
	add_child(layer)
	var theme := Theme.new()
	theme.default_font_size = 15
	var root := VBoxContainer.new()
	root.theme = theme
	root.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_theme_constant_override("separation", 6)
	layer.add_child(root)
	var banner := Label.new()
	banner.text = BANNER
	banner.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	banner.add_theme_font_size_override("font_size", 13)
	banner.add_theme_color_override("font_color", C_SIM)
	root.add_child(_panel(banner))
	var cols := HBoxContainer.new()
	cols.size_flags_vertical = Control.SIZE_EXPAND_FILL
	cols.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(cols)

	var left := VBoxContainer.new()
	left.custom_minimum_size = Vector2(SIDE_W, 0)
	cols.add_child(_panel(left))
	left.add_child(_heading("Designs and scenes"))
	ui_designs = Tree.new()
	ui_designs.hide_root = true
	ui_designs.columns = 2
	ui_designs.set_column_expand(1, false)
	ui_designs.set_column_custom_minimum_width(1, 76)
	ui_designs.size_flags_vertical = Control.SIZE_EXPAND_FILL
	ui_designs.size_flags_stretch_ratio = 1.3
	ui_designs.item_selected.connect(func(): _select(ui_designs.get_selected().get_metadata(0)))
	left.add_child(ui_designs)
	left.add_child(_heading("Actions"))
	ui_actions = Tree.new()
	ui_actions.hide_root = true
	ui_actions.columns = 2
	ui_actions.column_titles_visible = true
	ui_actions.set_column_title(0, "action")
	ui_actions.set_column_title(1, "status")
	ui_actions.set_column_expand(1, false)
	ui_actions.set_column_custom_minimum_width(1, 150)
	ui_actions.size_flags_vertical = Control.SIZE_EXPAND_FILL
	ui_actions.item_selected.connect(func(): _play(ui_actions.get_selected().get_metadata(0)))
	left.add_child(ui_actions)
	var row := HBoxContainer.new()
	left.add_child(row)
	var stow := Button.new()
	stow.text = "Stow (rest)"
	stow.pressed.connect(_stow)
	row.add_child(stow)
	var frame := Button.new()
	frame.text = "Frame (F)"
	frame.pressed.connect(_frame)
	row.add_child(frame)
	ui_loop = CheckBox.new()
	ui_loop.text = "loop"
	ui_loop.button_pressed = true
	row.add_child(ui_loop)

	ui_view = Control.new()
	ui_view.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	ui_view.mouse_filter = Control.MOUSE_FILTER_IGNORE
	ui_view.resized.connect(_orbit)
	cols.add_child(ui_view)

	var right := VBoxContainer.new()
	right.custom_minimum_size = Vector2(SIDE_W, 0)
	cols.add_child(_panel(right))
	right.add_child(_heading("Status"))
	ui_status = RichTextLabel.new()
	ui_status.bbcode_enabled = true
	ui_status.fit_content = true
	ui_status.scroll_active = false
	right.add_child(ui_status)
	right.add_child(HSeparator.new())
	right.add_child(_heading("Class facts and gates"))
	ui_info = RichTextLabel.new()
	ui_info.bbcode_enabled = true
	ui_info.scroll_active = true
	ui_info.size_flags_vertical = Control.SIZE_EXPAND_FILL
	right.add_child(ui_info)


func _panel(c: Control) -> PanelContainer:
	var p := PanelContainer.new()
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.05, 0.065, 0.085, 0.92)
	sb.set_content_margin_all(8)
	p.add_theme_stylebox_override("panel", sb)
	p.add_child(c)
	return p


func _heading(t: String) -> Label:
	var l := Label.new()
	l.text = t
	l.add_theme_color_override("font_color", C_HEAD)
	return l


func _readable(n: String) -> String:
	var s := n.trim_prefix("eva_").replace("_", " ")
	for w in ["oru", "eva", "iva", "ir"]:
		s = (" %s " % s).replace(" %s " % w, " %s " % w.to_upper()).strip_edges()
	return s.substr(0, 1).to_upper() + s.substr(1)


func _short_id(id: String) -> String:
	if id.begins_with("SCENE-"):
		return "scene"
	for p in ["DR-", "SCENE-", "WAYFARER_EVA_"]:
		if id.begins_with(p):
			return id.trim_prefix(p)
	return id


func _fill_designs() -> void:
	# grouped by family; the readable class name leads, the short ID follows (full ID in the tooltip and the status card)
	var top := ui_designs.create_item()
	design_items.resize(entries.size())
	for g in GROUPS:
		var head: TreeItem = null
		for i in entries.size():
			var e: Dictionary = entries[i]
			if not e["id"].begins_with(g[0]):
				continue
			if head == null:
				head = ui_designs.create_item(top)
				head.set_text(0, g[1])
				head.set_selectable(0, false)
				head.set_selectable(1, false)
				head.set_custom_color(0, C_HEAD)
			var it := ui_designs.create_item(head)
			it.set_text(0, e["title"])
			it.set_autowrap_mode(0, TextServer.AUTOWRAP_WORD_SMART)
			it.set_text(1, _short_id(e["id"]))
			it.set_custom_color(1, C_DIM)
			it.set_tooltip_text(0, e["id"])
			it.set_metadata(0, i)
			design_items[i] = it


func _pick_design(i: int) -> void:
	ui_designs.set_block_signals(true)
	design_items[i].select(0)
	ui_designs.set_block_signals(false)
	_select(i)
	await get_tree().process_frame                       # scroll once the tree has its size, so the selection is in view
	ui_designs.scroll_to_item(design_items[i], true)


func _set_act(a: Dictionary, verb: String) -> void:
	act_line = "[bgcolor=#2a3a2a] %s [/bgcolor]  [b]%s[/b]  [color=#9aa](%s)[/color]\n[color=#f0c070]%s: display motion; speeds, forces, torques and durations OPEN.[/color]\n%s" % [
			verb, _readable(a["name"]), a["name"], a["status"], a["job"]]


func _status() -> void:
	var e: Dictionary = entries[selected]
	var t := "[font_size=20][b]%s[/b][/font_size]\n[color=#9aa]%s[/color]\n\n" % [e["title"], e["id"]]
	t += act_line if act_line != "" else "[color=#9aa]No actions: a static review scene.[/color]" if e.get("actions", []).is_empty() else "[color=#9aa]At rest. Pick an action on the left.[/color]"
	if note_line != "":
		t += "\n\n" + note_line
	ui_status.text = t


# ------------------------------------------------------------------------------------------------------------------------- content
func _load(file: String) -> Node3D:
	var doc := GLTFDocument.new()
	var state := GLTFState.new()
	var err := doc.append_from_file(ProjectSettings.globalize_path(GEN + file), state)
	if err != OK:
		printerr("ERROR: cannot read ", file, " (", err, ")")
		return null
	return doc.generate_scene(state) as Node3D


func _select(i: int) -> void:
	selected = i
	if current:
		remove_child(current)
		current.free()
		current = null
	anim = null
	var e: Dictionary = entries[i]
	current = _load(e["glb"])
	ui_actions.clear()
	action_items = []
	act_line = ""
	note_line = ""
	if current == null:
		note_line = "[color=#ff8060]Cannot load %s[/color]" % e["glb"]
		_status()
		return
	add_child(current)
	var players := current.find_children("*", "AnimationPlayer", true, false)
	anim = players[0] if players.size() > 0 else null
	var top := ui_actions.create_item()
	for j in e.get("actions", []).size():
		var a: Dictionary = e["actions"][j]
		var it := ui_actions.create_item(top)
		it.set_text(0, _readable(a["name"]))
		it.set_tooltip_text(0, "%s: %s" % [a["name"], a["job"]])
		it.set_metadata(0, j)
		if a["status"] == LOCKED:                          # inherited unsuited actions never play as suited EVA operations: a click
			it.set_text(1, "LOCKED")                       # only shows the refusal and its reason in the status card
			it.set_tooltip_text(1, "not a suited EVA operation: it does not play")
			for c in 2:
				it.set_custom_color(c, C_LOCK)
		else:
			it.set_text(1, a["status"])
			it.set_custom_color(1, C_SIM)
		action_items.append(it)
	_info(e)
	_status()
	_frame()


func _anim_name(action: String) -> String:
	if anim == null:
		return ""
	for n in anim.get_animation_list():
		if n == action or n.ends_with("_" + action) or n.ends_with("|" + action):
			return n
	return ""


func _play(k: int) -> bool:
	var e: Dictionary = entries[selected]
	var a: Dictionary = e["actions"][k]
	if a["status"] == LOCKED:
		note_line = "[bgcolor=#4a2420] REFUSED [/bgcolor]  [b]%s[/b]  [color=#9aa](%s)[/color]\n[color=#ff8060]LOCKED: not a suited EVA operation; it does not play. %s.[/color]" % [
				_readable(a["name"]), a["name"], a["job"]]
		_status()
		return false
	var n := _anim_name(a["name"])
	if n == "":
		note_line = "[color=#ff8060]animation %s not in the GLB[/color]" % a["name"]
		_status()
		return false
	anim.get_animation(n).loop_mode = Animation.LOOP_LINEAR if ui_loop.button_pressed else Animation.LOOP_NONE
	anim.play(n)
	note_line = ""
	_set_act(a, "PLAYING" if ui_loop.button_pressed else "PLAYING ONCE")
	_status()
	return true


func _stow() -> void:
	if anim:
		anim.stop()
		var n := _anim_name(entries[selected]["actions"][0]["name"]) if entries[selected].get("actions", []).size() > 0 else ""
		if n != "":
			anim.play(n)
			anim.seek(0.0, true)
			anim.pause()
	act_line = ""
	_status()


func _info(e: Dictionary) -> void:
	var t := ""
	for line in e.get("facts", []):
		t += "• %s\n" % line
	t += "\n[color=#f0c070]Gates:[/color] [color=#bcc]%s[/color]" % e.get("gates", "")
	ui_info.text = t
	ui_info.scroll_to_line(0)
	tag.text = e["id"]


func _aabb(n: Node) -> AABB:
	var box := AABB()
	var first := true
	for m in n.find_children("*", "MeshInstance3D", true, false):
		var b: AABB = m.global_transform * m.get_aabb()
		if first:
			box = b
			first = false
		else:
			box = box.merge(b)
	return box


func _frame() -> void:
	if current == null:
		return
	var b := _aabb(current)
	focus = b.get_center()
	var y0 := b.position.y - 0.002                       # the floor and the scale post stand under the model (scenes reach below 0)
	floor_node.position.y = y0
	post.position = Vector3(b.position.x - 0.35, y0 + 0.89, focus.z)
	post_label.position = post.position + Vector3(0, 0.97, 0)
	# distance: the old 1.6 x diagonal, widened so the model and the post's foot fit the free view between the columns
	var reach := Vector2(b.size.x, b.size.z).length() * 0.5
	reach = max(reach, Vector2(post.position.x - focus.x, 0.0).length() + 0.05)
	var vp := get_viewport().get_visible_rect().size
	var w: float = ui_view.size.x if ui_view and ui_view.size.x > 50 else vp.x
	var half_w := tan(deg_to_rad(cam.fov * 0.5)) * w / vp.y
	dist = max(b.size.length() * 1.6, reach / half_w * 1.15, 0.8)
	tag.position = Vector3(focus.x, b.end.y + 0.08, focus.z)
	tag.pixel_size = dist * 0.0004
	_orbit()


func _orbit() -> void:
	cam.position = focus + Vector3(cos(pitch) * sin(yaw), sin(pitch), cos(pitch) * cos(yaw)) * dist
	cam.look_at(focus, Vector3.UP)
	if ui_view and ui_view.size.x > 50:                  # shift the image so the focus sits in the middle of the free view
		var vp := get_viewport().get_visible_rect().size
		var dx := ui_view.get_global_rect().get_center().x - vp.x * 0.5
		cam.h_offset = -dx / (vp.y * 0.5) * dist * tan(deg_to_rad(cam.fov * 0.5))


func _unhandled_input(ev: InputEvent) -> void:
	if ev is InputEventMouseButton:
		if ev.button_index == MOUSE_BUTTON_LEFT or ev.button_index == MOUSE_BUTTON_RIGHT:
			dragging = ev.pressed
		elif ev.button_index == MOUSE_BUTTON_WHEEL_UP and ev.pressed:
			dist *= 0.9
			_orbit()
		elif ev.button_index == MOUSE_BUTTON_WHEEL_DOWN and ev.pressed:
			dist *= 1.1
			_orbit()
	elif ev is InputEventMouseMotion and dragging:
		yaw -= ev.relative.x * 0.008
		pitch = clamp(pitch + ev.relative.y * 0.006, -1.2, 1.4)
		_orbit()
	elif ev is InputEventKey and ev.pressed and ev.keycode == KEY_F:
		_frame()


# ------------------------------------------------------------------------------------------------------------------------- checks
func _check() -> void:
	var fails: Array = []
	var gate_words := ["PROTOTYPE", "HOLD"]
	for i in entries.size():
		var e: Dictionary = entries[i]
		_select(i)
		if current == null:
			fails.append("%s: GLB did not load" % e["id"])
			continue
		var meshes := current.find_children("*", "MeshInstance3D", true, false).size()
		if meshes == 0:
			fails.append("%s: no meshes" % e["id"])
		for w in gate_words:
			if not (w in e.get("gates", "")):
				fails.append("%s: status label lacks %s" % [e["id"], w])
		var played := 0
		var locked := 0
		for j in e.get("actions", []).size():
			var a: Dictionary = e["actions"][j]
			if a["status"] == LOCKED:                          # listed and refused: never played as a suited operation
				locked += 1
				if anim:
					anim.stop()
				if _play(j) or (anim and anim.is_playing()):
					fails.append("%s/%s: LOCKED action is playable" % [e["id"], a["name"]])
				continue
			if a["status"] != "SIMULATION_ONLY":
				fails.append("%s/%s: action not labelled SIMULATION_ONLY" % [e["id"], a["name"]])
			var n := _anim_name(a["name"])
			if n == "":
				fails.append("%s: animation %s missing" % [e["id"], a["name"]])
				continue
			anim.play(n)
			anim.seek(anim.get_animation(n).length * 0.5, true)
			played += 1
		print("WF_ACC_VIEWER %s meshes=%d actions=%d/%d locked=%d" % [e["id"], meshes, played, e.get("actions", []).size() - locked, locked])
	for f in fails:
		printerr("ERROR: ", f)
	if fails.is_empty():
		print("WF_ACC_VIEWER CHECK PASS entries=%d" % entries.size())
	get_tree().quit(0 if fails.is_empty() else 1)


func _shots(dir: String) -> void:
	DirAccess.make_dir_recursive_absolute(dir)
	for i in entries.size():
		var e: Dictionary = entries[i]
		_pick_design(i)
		var main: String = e.get("main", ["", 0.0])[0]
		var k := -1
		for j in e.get("actions", []).size():
			if e["actions"][j]["name"] == main:
				k = j
		if k >= 0:
			ui_actions.set_block_signals(true)
			action_items[k].select(0)
			ui_actions.set_block_signals(false)
			_play(k)
			anim.seek(float(e["main"][1]), true)
			anim.pause()
			_set_act(e["actions"][k], "PAUSED %.1f s" % float(e["main"][1]))
			_status()
		var shows_locked := false
		for j in range(e.get("actions", []).size() - 1, -1, -1):   # an entry with locked actions: show the list end and the refusal
			if e["actions"][j]["status"] == LOCKED:
				_play(j)
				shows_locked = true
				break
		await get_tree().process_frame
		if shows_locked:
			ui_actions.scroll_to_item(action_items[action_items.size() - 1])
		_frame()                                             # frame the working pose, not the stowed one
		for _f in 3:
			await get_tree().process_frame
		var img := get_viewport().get_texture().get_image()
		img.save_png("%s/viewer_%s.png" % [dir, e["id"]])
		print("WF_ACC_VIEWER shot ", e["id"])
	get_tree().quit(0)
