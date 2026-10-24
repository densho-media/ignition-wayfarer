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
var ui_list: ItemList
var ui_actions: ItemList
var ui_info: RichTextLabel
var ui_loop: CheckBox
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
	for e in entries:
		ui_list.add_item("%s   %s" % [e["id"], e["title"]])
	var args := OS.get_cmdline_user_args()
	if "--check" in args:
		_check()
		return
	if "--shots" in args:
		_shots(args[args.find("--shots") + 1])
		return
	ui_list.select(0)
	_select(0)


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
	var layer := CanvasLayer.new()
	add_child(layer)
	var banner := Label.new()
	banner.text = BANNER
	banner.add_theme_font_size_override("font_size", 13)
	banner.add_theme_color_override("font_color", Color(0.95, 0.75, 0.4))
	banner.position = Vector2(12, 8)
	layer.add_child(banner)
	var panel := PanelContainer.new()
	panel.position = Vector2(12, 34)
	panel.custom_minimum_size = Vector2(380, 0)
	layer.add_child(panel)
	var box := VBoxContainer.new()
	panel.add_child(box)
	box.add_child(_heading("Designs and scenes"))
	ui_list = ItemList.new()
	ui_list.custom_minimum_size = Vector2(370, 230)
	ui_list.item_selected.connect(_select)
	box.add_child(ui_list)
	box.add_child(_heading("Actions (SIMULATION_ONLY display motions)"))
	ui_actions = ItemList.new()
	ui_actions.custom_minimum_size = Vector2(370, 120)
	ui_actions.item_selected.connect(_play)
	box.add_child(ui_actions)
	var row := HBoxContainer.new()
	box.add_child(row)
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
	ui_info = RichTextLabel.new()
	ui_info.custom_minimum_size = Vector2(370, 330)
	ui_info.bbcode_enabled = true
	ui_info.scroll_active = true
	box.add_child(ui_info)


func _heading(t: String) -> Label:
	var l := Label.new()
	l.text = t
	l.add_theme_color_override("font_color", Color(0.6, 0.75, 0.9))
	return l


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
	if current == null:
		ui_info.text = "[color=#ff8060]Cannot load %s[/color]" % e["glb"]
		return
	add_child(current)
	var players := current.find_children("*", "AnimationPlayer", true, false)
	anim = players[0] if players.size() > 0 else null
	for a in e.get("actions", []):
		var k := ui_actions.add_item("%s   [%s]" % [a["name"], a["status"]])
		if a["status"] == LOCKED:
			ui_actions.set_item_disabled(k, true)          # inherited unsuited actions never play as suited EVA operations
			ui_actions.set_item_custom_fg_color(k, Color(0.6, 0.45, 0.4))
	_info(e, null)
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
		ui_info.text += "\n[color=#ff8060]%s is LOCKED: %s. Not a suited EVA operation; it does not play.[/color]" % [a["name"], a["job"]]
		return false
	var n := _anim_name(a["name"])
	if n == "":
		ui_info.text += "\n[color=#ff8060]animation %s not in the GLB[/color]" % a["name"]
		return false
	anim.get_animation(n).loop_mode = Animation.LOOP_LINEAR if ui_loop.button_pressed else Animation.LOOP_NONE
	anim.play(n)
	_info(e, a)
	return true


func _stow() -> void:
	if anim:
		anim.stop()
		var n := _anim_name(entries[selected]["actions"][0]["name"]) if entries[selected].get("actions", []).size() > 0 else ""
		if n != "":
			anim.play(n)
			anim.seek(0.0, true)
			anim.pause()


func _info(e: Dictionary, a) -> void:
	var t := "[b]%s[/b]  %s\n" % [e["id"], e["title"]]
	for line in e.get("facts", []):
		t += "• %s\n" % line
	if a != null:
		t += "\n[b]Action %s[/b] — %s\n[color=#f0c070]%s: display motion; speeds, forces, torques and durations are OPEN.[/color]\n" % [a["name"], a["job"], a["status"]]
	t += "\n[color=#9aa]%s[/color]" % e.get("gates", "")
	ui_info.text = t
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
	dist = max(b.size.length() * 1.6, 0.8)
	tag.position = Vector3(focus.x, b.end.y + 0.08, focus.z)
	tag.pixel_size = dist * 0.0004
	var y0 := b.position.y - 0.002                       # the floor and the scale post stand under the model (scenes reach below 0)
	floor_node.position.y = y0
	post.position = Vector3(b.position.x - 0.35, y0 + 0.89, focus.z)
	post_label.position = post.position + Vector3(0, 0.97, 0)
	_orbit()


func _orbit() -> void:
	cam.position = focus + Vector3(cos(pitch) * sin(yaw), sin(pitch), cos(pitch) * cos(yaw)) * dist
	cam.look_at(focus, Vector3.UP)


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
			if a["status"] == LOCKED:                          # listed, disabled and refused: never played as a suited operation
				locked += 1
				if anim:
					anim.stop()
				if not ui_actions.is_item_disabled(j) or _play(j) or (anim and anim.is_playing()):
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
		ui_list.select(i)
		_select(i)
		var main: String = e.get("main", ["", 0.0])[0]
		var k := -1
		for j in e.get("actions", []).size():
			if e["actions"][j]["name"] == main:
				k = j
		if k >= 0:
			ui_actions.select(k)
			_play(k)
			anim.seek(float(e["main"][1]), true)
			anim.pause()
		var shows_locked := false
		for j in range(e.get("actions", []).size() - 1, -1, -1):   # an entry with locked actions: show the list end and the refusal
			if e["actions"][j]["status"] == LOCKED:
				_play(j)
				shows_locked = true
				break
		await get_tree().process_frame
		if shows_locked:
			ui_actions.get_v_scroll_bar().value = ui_actions.get_v_scroll_bar().max_value
			ui_info.scroll_to_line(ui_info.get_line_count() - 1)
		_frame()                                             # frame the working pose, not the stowed one
		for _f in 3:
			await get_tree().process_frame
		var img := get_viewport().get_texture().get_image()
		img.save_png("%s/viewer_%s.png" % [dir, e["id"]])
		print("WF_ACC_VIEWER shot ", e["id"])
	get_tree().quit(0)
