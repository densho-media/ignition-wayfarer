extends Control
## U01: the review menu, the project's start scene (a development review tool, not the game's menu). It lists the review sessions so
## no command line or key has to be remembered: a guided session opens its scene with the step-by-step guide (review_guide.gd);
## sessions whose guide is not built yet open the scene as it is and say so.
##   godot --path godot                      (opens this menu)
##   godot --path godot res://scenes/boarding.tscn -- --review=ring_b      (one session directly)

const SESSIONS := [
	{"key": "ring_b", "title": "Ring B in body mode", "what": "Walk the ring B rooms as a physics body and drop a tool to see the Coriolis effect.",
		"scene": "res://scenes/boarding.tscn", "guided": true, "minutes": 3},
	{"key": "vestibule", "title": "Vestibule drill", "what": "The seven-step handoff from the still spine into spinning ring A, one V press per step.",
		"scene": "res://scenes/physics_lab.tscn", "guided": true, "minutes": 2},
	{"key": "eva", "title": "EVA drift and two tethers", "what": "Out of the airlock, push to the rail, swap tethers with the two-tether protocol, push off and get caught.",
		"scene": "res://scenes/eva.tscn", "guided": true, "minutes": 4},
	{"key": "walk", "title": "Induction walk", "what": "The camera walk from the entry chamber through the spine and the drum into ring A, stop by stop.",
		"scene": "res://scenes/boarding.tscn", "guided": true, "minutes": 5},
	{"key": "demo01", "title": "Integrated Demonstrator 01", "what": "Seven chapters from the docked exterior to walking in ring A, in one physics world.",
		"scene": "res://scenes/demo01.tscn", "guided": true, "minutes": 8},
	{"key": "inspector", "title": "Ship inspector", "what": "The whole ship and its subsystems with each part's source status; L shows the radiator mount review legend.",
		"scene": "res://scenes/inspector.tscn", "guided": true, "minutes": 2},
	{"key": "flight", "title": "First Ignition timeline", "what": "Spin-down, lock and burn playback, the physically lit ignition look and the Y155 radiator scenarios (DIAGNOSTIC).",
		"scene": "res://scenes/flight.tscn", "guided": true, "minutes": 3},
	{"key": "holo", "title": "Subsystem hologram (M5 / M6)", "what": "The ship as a functional hologram: thrust chain, fuel against packaging, cryogenics, the nozzle load path, attitude and comms (modes, antenna contact, light time, store and forward), then the EYE and shield (eyelids, Crown, dust and the protected shadow), the counter-rotating habitat (spin gravity, lock, a crew walk) and the radiators (operating steps, damage and isolation), with isolation, cutaway and each part's source status.",
		"scene": "res://scenes/m5_holo.tscn", "guided": true, "minutes": 9},
]

# Owner 2026-10-17 (S&E 15!A200 OWN-SCI, 98!A114): the P0 science release gate, shown on the start screen so no scene reads as flight truth.
const P0_GATE := [["HOLD", "P0 science: wet mass, reaction mass, fusion fuel and absorbed drive heat are not released; flight playback is SIMULATION_ONLY"],
	["DIAGNOSTIC", "16 GW drive heat, 16.18 MN, 1e-4 and the radiator scenarios are diagnostics, not engine inputs"]]

func _ready() -> void:
	var bg := ColorRect.new()
	bg.color = Color("17181a")
	bg.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(bg)
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var scroll := ScrollContainer.new()               # a short window scrolls instead of clipping the list
	scroll.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	add_child(scroll)
	var center := CenterContainer.new()
	center.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	center.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.add_child(center)
	var col := VBoxContainer.new()
	col.custom_minimum_size = Vector2(760, 0)
	col.add_theme_constant_override("separation", 10)
	center.add_child(col)
	col.add_child(_spacer(16))
	col.add_child(_label("Wayfarer review sessions", 28, WfReviewGuide.C_TITLE))
	col.add_child(_label("Development review build. Pick a session: the guided ones walk you through each step, show the keys that work right now and say what you should see.", 15, WfReviewGuide.C_BODY))
	var how := HFlowContainer.new()                     # the menu's keys as chips (ACI-07), the same style as the guide bar
	how.add_theme_constant_override("h_separation", 14)
	how.add_child(WfReviewGuide.chip("%s–%s" % [WfInput.label("menu.session_1"), WfInput.label("menu.session_%d" % SESSIONS.size())], "or click: open a session", "next"))
	how.add_child(WfReviewGuide.chip(WfInput.label("ui.codex"), "your controls", "now"))
	how.add_child(WfReviewGuide.chip(WfInput.label("ui.cancel"), "quit", "exit"))
	col.add_child(how)
	if WfReviewGuide.study_label() != "":              # H03: a STUDY package (runtime-export --eye-layout) is never shown as the ship
		col.add_child(_gate_row("STUDY", WfReviewGuide.study_label()))
	for g in P0_GATE:                                  # above the list, so the release gate is on screen in any window
		col.add_child(_gate_row(g[0], g[1]))
	col.add_child(_spacer(8))
	for i in SESSIONS.size():
		col.add_child(_row(i, SESSIONS[i]))
	col.add_child(_spacer(8))
	col.add_child(_label("Badges: CANON / DERIVED owner values · WORKING · PROTOTYPE placeholder · DIAGNOSTIC measurement · OPEN unknown · HOLD gated · STUDY not canon.",
		12, WfReviewGuide.C_MUTED))
	var controls := Button.new()                       # ACI-08: the pointer route to the Control Codex (also F10 / the codex action anywhere)
	controls.text = "Controls  (%s)" % WfInput.label("ui.codex")
	controls.focus_mode = Control.FOCUS_NONE
	controls.add_theme_font_size_override("font_size", 15)
	controls.pressed.connect(WfInput.overlay.open_codex)
	col.add_child(controls)
	col.add_child(_spacer(16))
	WfInput.context = "menu"
	if not WfInput.has_profile() and WfInput.prompts_enabled():
		WfInput.overlay.open_first_launch()             # ACI-03: first launch establishes Confirm before anything else
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--capture-controls="):          # stills of the control screens (needs a display; scratch profile)
			await load("res://scripts/controls/check_controls.gd").new().capture(self, arg.trim_prefix("--capture-controls="))
			get_tree().quit()
			return
		if arg == "--check-controls":                     # ACI-13 (headless); the full result is the printed line
			var out: Dictionary = await load("res://scripts/controls/check_controls.gd").new().run(self)
			print("WF_GODOT_CONTROLS " + JSON.stringify(out))
			get_tree().quit(0 if out.result == "PASS" else 1)
			return
		if arg.begins_with("--capture-menu="):            # a still of the menu (needs a display)
			for i in 10:
				await get_tree().process_frame
			get_viewport().get_texture().get_image().save_png(arg.trim_prefix("--capture-menu="))
			get_tree().quit()

func _label(text: String, size: int, color: Color) -> Label:
	var l := Label.new()
	l.text = text
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", color)
	return l

func _gate_row(status: String, text: String) -> Control:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 8)
	var c: Color = WfReviewGuide.STATUS_COLORS[status]
	var cap := PanelContainer.new()
	var sb := WfReviewGuide._box(Color(0, 0, 0, 0), c, 4, 0)
	sb.content_margin_left = 6
	sb.content_margin_right = 6
	cap.add_theme_stylebox_override("panel", sb)
	cap.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
	var tag := _label(status, 11, c)
	tag.autowrap_mode = TextServer.AUTOWRAP_OFF           # a wrapping label in a shrinking container wraps after every letter
	cap.add_child(tag)
	row.add_child(cap)
	var l := _label(text, 13, WfReviewGuide.C_BODY)
	l.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(l)
	return row

func _spacer(h: int) -> Control:
	var c := Control.new()
	c.custom_minimum_size = Vector2(0, h)
	return c

func _row(i: int, s: Dictionary) -> Control:
	var b := Button.new()
	b.focus_mode = Control.FOCUS_NONE
	b.custom_minimum_size = Vector2(760, 64)
	var guided: bool = s.guided
	var border := WfReviewGuide.C_NEXT if guided else Color("444441")
	for st in ["normal", "hover", "pressed"]:
		var sb := WfReviewGuide._box(Color("232427") if st == "normal" else Color("2C2D31"), border, 10, 12)
		b.add_theme_stylebox_override(st, sb)
	b.pressed.connect(open.bind(i))
	var row := HBoxContainer.new()
	row.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	row.offset_left = 14
	row.offset_right = -14
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.add_theme_constant_override("separation", 14)
	b.add_child(row)
	# A Button does not size to its children: grow it to the row, whose height follows the wrapped description.
	row.minimum_size_changed.connect(func(): b.custom_minimum_size.y = maxf(64.0, row.get_combined_minimum_size().y + 20.0))
	var num := PanelContainer.new()
	var sbn := WfReviewGuide._box(WfReviewGuide.C_NEXT if guided else WfReviewGuide.C_EXIT, WfReviewGuide.C_NEXT if guided else WfReviewGuide.C_EXIT, 6, 6)
	num.add_theme_stylebox_override("panel", sbn)
	num.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	num.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var nl := _label(WfInput.label("menu.session_%d" % (i + 1)), 18, WfReviewGuide.C_NEXT_TEXT if guided else WfReviewGuide.C_EXIT_TEXT)
	nl.custom_minimum_size = Vector2(18, 0)
	nl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	num.add_child(nl)
	row.add_child(num)
	var text := VBoxContainer.new()
	text.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	text.alignment = BoxContainer.ALIGNMENT_CENTER
	text.mouse_filter = Control.MOUSE_FILTER_IGNORE
	text.add_child(_label(s.title, 18, WfReviewGuide.C_TITLE))
	text.add_child(_label(s.what, 13, WfReviewGuide.C_BODY))
	row.add_child(text)
	var tag := _label("GUIDED · about %d min" % s.minutes if guided else "no guide yet (%s)" % s.todo, 13, WfReviewGuide.C_NEXT if guided else WfReviewGuide.C_MUTED)
	tag.autowrap_mode = TextServer.AUTOWRAP_OFF
	tag.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	row.add_child(tag)
	for l in text.get_children() + [nl, tag]:
		l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return b

func open(i: int) -> void:
	var s: Dictionary = SESSIONS[i]
	WfReviewGuide.pending = s.key
	get_tree().change_scene_to_file(s.scene)

func _unhandled_input(e: InputEvent) -> void:
	if WfInput.pressed(e):
		var k := WfInput.key_of(e, ["menu"])            # ACI-10: menu.session_N and ui.cancel (Esc is locked on Back)
		if k == KEY_ESCAPE:
			get_tree().quit()
		elif k >= KEY_1 and k < KEY_1 + SESSIONS.size():
			open(k - KEY_1)
