extends CanvasLayer
## MOB-001 (docs/wayfarer-mobile-controls-plan.md): the touch controls, owned by the WfInput autoload beside the control overlay.
## Every finger is tracked by its touch index and belongs to the one control it landed on: the movement stick (left part of the screen,
## while the scene can move the body), the look area (right part, while a scene takes the look), a contextual action button or the
## scene's own interface (stop list, map, cards), which keeps getting Godot's mouse emulation of that finger. A finger claimed here
## never reaches the scene as a mouse event too.
## The stick sets hold actions through WfInput.set_virtual (the physics reads WfInput.strength, so it never moves a body that has no
## floor or rail to act on); a button sends WfInput.trigger(id), which reaches the same scene handler as the bound key with the same
## checks; looking goes through WfInput.add_look to the scene that takes it. The scene says what can be used now through
## WfInput.touch_provider ({move: "" | "1d" | "2d", actions: [[id, label, role]], utility: [[id, label]], look: bool}).
## On a touch-first device (coarse pointer, no fine pointer, or -- --touch) the 2-D interface is scaled to CSS pixels, a mobile 3-D
## resolution is chosen and adapted to the frame rate, and a touch welcome replaces the keyboard first launch. Desktop is unchanged.

const STICK_R := 58.0          # UI px (CSS px on a phone): stick travel at full strength
const KNOB_R := 26.0
const DEAD := 0.14             # fraction of the travel that reads zero
const ZONE := 0.42             # the left fraction of the screen where a finger starts the stick
const LOOK_RAD := 2.6          # radians of view turn for a drag across the screen's short side at look speed 1.0
const TARGET := 52.0           # button height, UI px (Apple HIG 44 pt, Material 48 dp minimum touch targets)
const GAP := 10.0
const EDGE := 12.0             # margin inside the safe area
const TAP_SLOP := 14.0         # a button press slid farther than this off the button is cancelled (navigation buttons)
const MOUSE_AFTER_TOUCH_MS := 700   # a real mouse click this soon after a touch at the same place is the browser's echo of it
# Mobile 3-D resolution (PROTOTYPE display budget, docs/wayfarer-mobile-controls-plan.md §8): rendered pixels per CSS pixel, the
# bounds of the adaptive scale and the frame-rate band it keeps. Rendering only: no geometry, material or simulation input changes.
const RENDER_DENSITY := 1.25
const SCALE_MIN := 0.35
const FPS_LOW := 24.0
const FPS_HIGH := 45.0

var I: Node
var primary := false           # touch-first device: compact layout, CSS-pixel UI, mobile 3-D resolution
var dpr := 1.0
var safe := [0.0, 0.0, 0.0, 0.0]    # left, top, right, bottom insets in UI px (CSS env(safe-area-inset-*), from the web shell)
var claims := {}               # touch index -> {kind: stick | look | button | gui | none, id, at, start, node}
var emulated := ""             # classification of the finger Godot emulates the mouse from: its mouse events are swallowed unless gui
var last_touch_ms := -100000
var last_touch_at := Vector2.INF
var state := {}                # the provider's answer this frame
var shown := false
var mode := ""                 # "" | welcome | help (modal panels)
var was_paused := false
var stick := Vector2.ZERO      # -1..1 after the dead zone (x right, y down)
var stick_base := Vector2.ZERO
var stick_touch := -1
var looked := false            # the look hint disappears after the first look drag
var scale_3d := 1.0
var scale_cap := 1.0
var fps_t := 0.0
var fps_n := 0
var warm := 0.0
var probe := false             # -- --touch-probe: publish the touch state to the page (window.wayfarerTouch) for the browser check
var probe_t := 0.0
var log: Array = []            # [kind, detail] for the checks

var root := Control.new()
var pad := Control.new()       # draws the stick and the look hint
var actions_box := Control.new()
var util_box := Control.new()
var buttons: Array = []        # [{node, id, role, label}]
var signature := ""
var panel := PanelContainer.new()
var dim := ColorRect.new()
var panel_col := VBoxContainer.new()
var panel_title := Label.new()
var panel_body := Label.new()
var panel_buttons := HFlowContainer.new()
var hint := Label.new()

func _ready() -> void:
	I = get_parent()
	layer = 110                                  # over the scenes' HUDs, under the control overlay's modal panels (120)
	process_mode = Node.PROCESS_MODE_ALWAYS
	var args := OS.get_cmdline_user_args()
	probe = "--touch-probe" in args
	if "--touch" in args:
		primary = true
	elif "--no-touch" in args:
		primary = false
	elif OS.has_feature("web"):
		primary = bool(_js("matchMedia('(pointer: coarse)').matches && !matchMedia('(any-pointer: fine)').matches", false))
	if primary:
		I.set_device("touch")
		dpr = float(_js("window.devicePixelRatio || 1", DisplayServer.screen_get_scale()))
		dpr = clampf(dpr, 1.0, 4.0)
	root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(root)
	pad.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	pad.mouse_filter = Control.MOUSE_FILTER_IGNORE
	pad.draw.connect(_draw_pad)
	root.add_child(pad)
	for b in [actions_box, util_box]:
		b.mouse_filter = Control.MOUSE_FILTER_IGNORE
		root.add_child(b)
	hint.add_theme_font_size_override("font_size", 13)
	hint.add_theme_color_override("font_color", Color(1, 1, 1, 0.55))
	hint.add_theme_color_override("font_outline_color", Color.BLACK)
	hint.add_theme_constant_override("outline_size", 3)
	hint.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(hint)
	_build_panel()
	get_viewport().size_changed.connect(_on_resize)
	_read_safe()
	I.apply()                                    # the content scale now includes the touch density
	if primary:
		_start_quality()

func _js(code: String, fallback):
	if not OS.has_feature("web") or not Engine.has_singleton("JavaScriptBridge"):
		return fallback
	var v = JavaScriptBridge.eval(code, true)
	return fallback if v == null else v

## The 2-D content scale on a touch-first device: one UI pixel per CSS pixel (text and touch targets keep their physical size).
func ui_density() -> float:
	return dpr if primary else 1.0

func _read_safe() -> void:
	var s = _js("JSON.stringify(window.wayfarerSafe || [0, 0, 0, 0])", "[0,0,0,0]")
	var a = JSON.parse_string(str(s))
	if a is Array and a.size() == 4:
		# CSS px; UI px are CSS px on a touch-first device, device px otherwise
		safe = a.map(func(x): return float(x) * (1.0 if primary else dpr))

func _on_resize() -> void:
	release_all()                                # rotation or a browser bar: every finger starts again (no stuck stick)
	_read_safe()
	signature = ""

func is_modal() -> bool:
	return mode != ""

func visible_controls() -> bool:
	if I.touch_controls == "off" or is_modal() or I.overlay.is_modal():
		return false
	return I.touch_controls == "on" or I.device == "touch"

# ---- input -------------------------------------------------------------------------------------------------------------------------

func _input(e: InputEvent) -> void:
	if e is InputEventScreenTouch:
		if e.pressed:
			_down(e.index, e.position)
		else:
			_up(e.index, e.position, e.canceled)
		_handled_unless_gui(e.index)
		if not e.pressed:
			claims.erase(e.index)
	elif e is InputEventScreenDrag:
		_drag(e.index, e.position, e.relative)
		_handled_unless_gui(e.index)
	elif e is InputEventMouse and e.device == InputEvent.DEVICE_ID_EMULATION:
		# Godot's mouse made from the first finger arrives before that finger's touch event: classify it the same way.
		if e is InputEventMouseButton and e.pressed and e.button_index == MOUSE_BUTTON_LEFT:
			emulated = _classify(e.position)
		if emulated != "" and emulated != "gui":
			get_viewport().set_input_as_handled()
		if e is InputEventMouseButton and not e.pressed:
			emulated = ""
	elif e is InputEventMouseButton and e.button_index == MOUSE_BUTTON_LEFT and visible_controls():
		# A real mouse (or the browser's compatibility click after a touch) on a touch button.
		if Time.get_ticks_msec() - last_touch_ms < MOUSE_AFTER_TOUCH_MS and e.position.distance_to(last_touch_at) < 24.0:
			get_viewport().set_input_as_handled()      # the echo of a touch already handled
			return
		var b := _button_at(e.position)
		if not b.is_empty():
			if not e.pressed:
				_fire(b)
			get_viewport().set_input_as_handled()

func _handled_unless_gui(index: int) -> void:
	if claims.get(index, {}).get("kind", "gui") != "gui":
		get_viewport().set_input_as_handled()

## What a finger landing at p belongs to: a touch button, the scene's own interface, the stick, the look area or nothing.
func _classify(p: Vector2) -> String:
	if is_modal() or I.overlay.is_modal() or I.touch_controls == "off":
		return "gui"
	if I.touch_controls == "auto" and I.device != "touch":
		I.set_device("touch")                    # the first touch on a hybrid device shows the controls at once
		_refresh(true)
	if not _button_at(p).is_empty():
		return "button"
	if _gui_at(p):
		return "gui"
	var vs := _size()
	if str(state.get("move", "")) != "" and p.x < vs.x * ZONE and p.y > vs.y * 0.18:
		return "stick"
	if bool(state.get("look", I.look_wanted())) and I.look_wanted() and p.x >= vs.x * ZONE:
		return "look"
	return "none"

func _down(index: int, p: Vector2) -> void:
	last_touch_ms = Time.get_ticks_msec()
	last_touch_at = p
	var kind := _classify(p)
	var c := {"kind": kind, "at": p, "start": p}
	match kind:
		"button":
			var b := _button_at(p)
			c["button"] = b
			_press_look(b, true)
			if b.role in ["game", "primary_game"]:
				_fire(b)                              # game actions act on touch down (no tap delay)
				c["fired"] = true
		"stick":
			if stick_touch >= 0:
				c["kind"] = "none"                    # one stick: a second left finger does nothing
			else:
				stick_touch = index
				stick_base = _fixed_base() if I.touch_stick == "fixed" else _clamp_base(p)
				_stick_to(p)
		"look":
			looked = true
	claims[index] = c
	log.append(["down", kind])

func _drag(index: int, p: Vector2, rel: Vector2) -> void:
	var c: Dictionary = claims.get(index, {})
	if c.is_empty():
		return
	# The Web platform keeps the previous drag position per changed-touch slot, not per finger, so with two fingers down the event's
	# relative can belong to the other finger: the delta is taken from this finger's own last position.
	rel = p - (c.at as Vector2)
	c["at"] = p
	match str(c.kind):
		"stick":
			_stick_to(p)
		"look":
			var ref := minf(_size().x, _size().y)
			I.add_look(rel / maxf(ref, 1.0) * LOOK_RAD * I.touch_look)
		"button":
			var b: Dictionary = c.button
			if not c.get("fired", false) and not _rect(b).grow(TAP_SLOP).has_point(p):
				_press_look(b, false)
				c["kind"] = "none"                    # slid off a navigation button: cancelled

func _up(index: int, p: Vector2, canceled: bool) -> void:
	var c: Dictionary = claims.get(index, {})
	last_touch_ms = Time.get_ticks_msec()
	last_touch_at = p
	if c.is_empty():
		return
	match str(c.kind):
		"stick":
			_stick_release()
		"button":
			var b: Dictionary = c.button
			_press_look(b, false)
			if not canceled and not c.get("fired", false) and _rect(b).grow(TAP_SLOP).has_point(p):
				_fire(b)
	log.append(["up", c.kind, canceled])

## Every finger released: the stick returns to zero, buttons unpressed (focus loss, resize, a modal panel, a scene change).
func release_all() -> void:
	for index in claims:
		var c: Dictionary = claims[index]
		if str(c.kind) == "button":
			_press_look(c.button, false)
	claims = {}
	emulated = ""
	_stick_release()

func _stick_to(p: Vector2) -> void:
	var d := p - stick_base
	var r := d.length()
	if I.touch_stick == "floating" and r > STICK_R * 1.6:
		stick_base = p - d / r * STICK_R * 1.6     # the base follows a thumb that runs far past the ring
		d = p - stick_base
		r = d.length()
	var v := d / STICK_R
	if v.length() > 1.0:
		v = v.normalized()
	var m := v.length()
	v = Vector2.ZERO if m < DEAD else v / m * ((m - DEAD) / (1.0 - DEAD))
	if str(state.get("move", "")) == "1d":
		v.x = 0.0
	stick = v
	_apply_stick()

func _stick_release() -> void:
	stick_touch = -1
	stick = Vector2.ZERO
	_apply_stick()

func _apply_stick() -> void:
	I.set_virtual("player.move_forward", maxf(0.0, -stick.y))
	I.set_virtual("player.move_back", maxf(0.0, stick.y))
	I.set_virtual("player.move_right", maxf(0.0, stick.x))
	I.set_virtual("player.move_left", maxf(0.0, -stick.x))
	pad.queue_redraw()

func _fixed_base() -> Vector2:
	var vs := _size()
	return Vector2(safe[0] + EDGE + STICK_R * 1.4, vs.y - safe[3] - EDGE - STICK_R * 1.4)

func _clamp_base(p: Vector2) -> Vector2:
	var vs := _size()
	return Vector2(clampf(p.x, safe[0] + STICK_R + 4.0, vs.x * ZONE), clampf(p.y, STICK_R + 4.0, vs.y - safe[3] - STICK_R - 4.0))

func _size() -> Vector2:
	return get_viewport().get_visible_rect().size

func _button_at(p: Vector2) -> Dictionary:
	if not shown:
		return {}
	for b in buttons:
		if (b.node as Control).is_visible_in_tree() and _rect(b).has_point(p):
			return b
	return {}

func _rect(b: Dictionary) -> Rect2:
	return (b.node as Control).get_global_rect()

## An interactive control of a scene (a button, list, slider, scroll area or map view) under p: that finger stays the scene's.
func _gui_at(p: Vector2) -> bool:
	for c in _controls(get_tree().root):
		if c.mouse_filter != Control.MOUSE_FILTER_IGNORE and c.is_visible_in_tree() and c.get_global_rect().has_point(p) \
				and (c is BaseButton or c is ItemList or c is Range or c is ScrollContainer or c is SubViewportContainer or c is LineEdit):
			return true
	return false

func _controls(n: Node) -> Array:
	var out := []
	for c in n.get_children():
		if c == self or c is Node3D or c == I.overlay:
			continue
		if c is Control:
			out.append(c)
		if c.get_child_count() > 0 and not c is SubViewport:
			out += _controls(c)
	return out

func _fire(b: Dictionary) -> void:
	var id := str(b.id)
	log.append(["fire", id])
	if id == "touch.help":
		open_help()
	elif state.get("local", {}).has(id):
		(state.local[id] as Callable).call()          # a display toggle of the scene (not a registry action: no simulation effect)
	else:
		I.trigger(id)

func _press_look(b: Dictionary, down: bool) -> void:
	if b.has("node") and is_instance_valid(b.node):
		(b.node as Button).modulate = Color(1.25, 1.25, 1.25) if down else Color.WHITE

# ---- layout ------------------------------------------------------------------------------------------------------------------------

func _process(dt: float) -> void:
	var p = I.touch_provider
	state = p.call() if p is Callable and p.is_valid() else {}
	if state.is_empty() and stick_touch >= 0:
		_stick_release()
	if str(state.get("move", "")) == "" and stick_touch >= 0:
		_stick_release()                             # the scene can no longer move the body: release at once
	if mode != "":
		_layout_panel()                              # flow rows settle a frame after the width; a rotation re-fits the panel
	if welcome_due() and not state.is_empty():
		open_welcome()                               # once the scene's controls exist, before the visitor needs them
	_refresh(false)
	_quality(dt)
	if probe:
		probe_t += dt
		if probe_t > 0.25:
			probe_t = 0.0
			_publish()

func _refresh(force: bool) -> void:
	var want := visible_controls()
	var sig := "%s|%s|%s|%s|%s" % [want, state.get("actions", []), state.get("utility", []), _size(), safe]
	if sig == signature and not force:
		pad.queue_redraw()
		return
	signature = sig
	shown = want
	for b in buttons:
		(b.node as Node).queue_free()
	buttons = []
	if want:
		var vs := _size()
		# utility row: top right, right to left (Help always last on the right)
		var x: float = vs.x - safe[2] - EDGE
		var util: Array = state.get("utility", []) + [["touch.help", "?", "util"]]
		util.reverse()
		for u in util:
			var bn := _make_button(str(u[1]), "util")
			bn.position = Vector2(x - bn.size.x, safe[1] + EDGE)
			x -= bn.size.x + GAP
			buttons.append({"node": bn, "id": u[0], "role": "util", "label": u[1]})
		# actions: bottom right, a column of rows from the bottom up; the primary action largest and nearest the thumb
		var acts: Array = state.get("actions", [])
		var y: float = vs.y - safe[3] - EDGE
		var row_x: float = vs.x - safe[2] - EDGE
		var row_h := 0.0
		var max_w := vs.x * (1.0 - ZONE) - EDGE
		for a in acts:
			var role := str(a[2]) if a.size() > 2 else "game"
			var bn := _make_button(str(a[1]), role)
			if vs.x - safe[2] - EDGE - row_x + bn.size.x > max_w and row_h > 0.0:
				y -= row_h + GAP
				row_x = vs.x - safe[2] - EDGE
				row_h = 0.0
			bn.position = Vector2(row_x - bn.size.x, y - bn.size.y)
			row_x -= bn.size.x + GAP
			row_h = maxf(row_h, bn.size.y)
			buttons.append({"node": bn, "id": a[0], "role": role, "label": a[1]})
	pad.queue_redraw()

func _make_button(text: String, role: String) -> Button:
	var bn := Button.new()
	bn.text = text
	bn.focus_mode = Control.FOCUS_NONE
	bn.mouse_filter = Control.MOUSE_FILTER_IGNORE     # fingers are hit-tested here by touch index (multitouch), never by mouse emulation
	var big := role in ["primary", "primary_game"]
	bn.add_theme_font_size_override("font_size", 17 if big else 15)
	var c: Color = WfReviewGuide.C_NEXT if big else (Color("5F5E5A") if role == "util" else WfReviewGuide.C_NOW)
	var bg := Color(0.07, 0.08, 0.09, 0.78)
	for st in ["normal", "hover", "pressed", "disabled"]:
		bn.add_theme_stylebox_override(st, WfReviewGuide._box(bg, c, 10, 12))
	bn.add_theme_color_override("font_color", WfReviewGuide.C_TITLE)
	bn.add_theme_color_override("font_hover_color", WfReviewGuide.C_TITLE)
	root.add_child(bn)
	var h := TARGET + (8.0 if big else 0.0)
	bn.size = Vector2(maxf(bn.get_combined_minimum_size().x + 8.0, TARGET if role == "util" else 76.0), h)
	return bn

func _draw_pad() -> void:
	hint.visible = false
	if not shown:
		return
	var vs := _size()
	var move := str(state.get("move", ""))
	if move != "":
		var base := stick_base if stick_touch >= 0 else _fixed_base()      # idle: where the thumb rests (floating starts anywhere left)
		var a := 0.30 if stick_touch >= 0 else 0.14
		pad.draw_circle(base, STICK_R, Color(1, 1, 1, a * 0.45))
		pad.draw_arc(base, STICK_R, 0, TAU, 48, Color(1, 1, 1, a + 0.15), 2.0, true)
		if move == "1d":
			pad.draw_line(base + Vector2(0, -STICK_R), base + Vector2(0, STICK_R), Color(1, 1, 1, a), 2.0, true)
		pad.draw_circle(base + stick * STICK_R, KNOB_R, Color(0.94, 0.62, 0.15, 0.55 if stick_touch >= 0 else 0.25))
		if stick_touch < 0:
			hint.visible = true
			hint.text = "move" if move == "2d" else "up / down"
			hint.position = base + Vector2(-hint.get_combined_minimum_size().x / 2.0, STICK_R + 6.0)
	if I.look_wanted() and bool(state.get("look", true)) and not looked:
		pad.draw_string(ThemeDB.fallback_font, Vector2(vs.x * 0.62, vs.y * 0.55), "drag to look",
			HORIZONTAL_ALIGNMENT_LEFT, -1, 14, Color(1, 1, 1, 0.45))

# ---- modal panels: touch welcome and help ------------------------------------------------------------------------------------------

func _build_panel() -> void:
	dim.color = Color(0, 0, 0, 0.55)
	dim.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	dim.mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(dim)
	panel.add_theme_stylebox_override("panel", WfReviewGuide._box(Color("17181a"), WfReviewGuide.C_NEXT, 12, 18))
	add_child(panel)
	# title, the text (scrolls on a short screen) and the buttons (always on screen: Close never scrolls away)
	panel_col.add_theme_constant_override("separation", 10)
	panel.add_child(panel_col)
	panel_col.add_child(panel_title)
	var scroll := ScrollContainer.new()
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	scroll.name = "scroll"
	panel_col.add_child(scroll)
	scroll.add_child(panel_body)
	for l in [panel_title, panel_body]:
		l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	panel_title.add_theme_font_size_override("font_size", 20)
	panel_title.add_theme_color_override("font_color", WfReviewGuide.C_TITLE)
	panel_body.add_theme_font_size_override("font_size", 15)
	panel_body.add_theme_color_override("font_color", WfReviewGuide.C_BODY)
	panel_buttons.add_theme_constant_override("h_separation", 8)
	panel_buttons.add_theme_constant_override("v_separation", 8)
	panel_col.add_child(panel_buttons)
	dim.visible = false
	panel.visible = false

func _layout_panel() -> void:
	var vs := _size()
	var w := minf(640.0, vs.x - safe[0] - safe[2] - 2.0 * EDGE)
	for c in [panel_title, panel_body, panel_buttons]:
		c.custom_minimum_size.x = w - 40.0
	var scroll: ScrollContainer = panel_col.get_node("scroll")
	var top: float = safe[1] + (60.0 if primary else EDGE)      # under the page's Exit and Full screen buttons
	var room: float = vs.y - top - safe[3] - EDGE - 36.0 - 20.0 - panel_title.get_combined_minimum_size().y - panel_buttons.get_combined_minimum_size().y
	scroll.custom_minimum_size = Vector2(w - 36.0, clampf(panel_body.get_combined_minimum_size().y, 0.0, maxf(room, 40.0)))
	panel.size = Vector2(w, 0)
	panel.size = panel.get_combined_minimum_size()
	panel.position = Vector2((vs.x - panel.size.x) / 2.0, maxf(top, (vs.y - panel.size.y - safe[3]) / 2.0))

func _panel_button(text: String, f: Callable, primary_role := false) -> void:
	var b := Button.new()
	b.text = text
	b.focus_mode = Control.FOCUS_NONE
	b.custom_minimum_size = Vector2(0, 46.0)                  # ≥ 44 pt
	b.add_theme_font_size_override("font_size", 15)
	var c := WfReviewGuide.C_NEXT if primary_role else Color("5F5E5A")
	for st in ["normal", "hover", "pressed"]:
		b.add_theme_stylebox_override(st, WfReviewGuide._box(Color("2C2D31") if st != "normal" else Color("232427"), c, 8, 12))
	b.pressed.connect(f)
	panel_buttons.add_child(b)

func _open(m: String) -> void:
	if mode == "":
		was_paused = get_tree().paused
	mode = m
	I.release_touch()
	get_tree().paused = true
	_show_panel()

func close_panel() -> void:
	mode = ""
	get_tree().paused = was_paused
	dim.visible = false
	panel.visible = false
	signature = ""
	log.append(["close", ""])

## The touch welcome (first launch on a touch-first device): what the thumbs do and the tips preference, all by tapping. It replaces
## the keyboard first launch, which needs a key press; the keyboard and controller bindings stay as they are.
func open_welcome() -> void:
	_open("welcome")

func open_help() -> void:
	_open("help")

func welcome_due() -> bool:
	return primary and not I.touch_intro_done and I.prompts_enabled() and not is_modal() and not I.overlay.is_modal()

func finish_welcome(pref: String) -> void:
	I.preference = pref
	I.touch_intro_done = true
	I.first_launch_done = true
	I.save_profile()
	close_panel()

func _show_panel() -> void:
	for c in panel_buttons.get_children():
		c.queue_free()
	dim.visible = true
	panel.visible = true
	match mode:
		"welcome":
			panel_title.text = "WAYFARER — TOUCH CONTROLS"
			panel_body.text = ("Left thumb: drag on the left half to walk or climb, where your body can.\n"
				+ "Right thumb: drag on the right half to look around.\n"
				+ "Buttons appear only when their action can be used: Grab, Push off, Release, Next …\n"
				+ "Weightless, the stick does nothing: only a hand on a rail changes your motion.\n"
				+ "? opens this help at any time. Turn the phone sideways for the widest view.\n\n"
				+ "Show a short tip when a new action first appears?")
			_panel_button("Start with tips (recommended)", finish_welcome.bind("SUGGESTED"), true)
			_panel_button("Start without tips", finish_welcome.bind("EXPERIENCED"))
		"help":
			panel_title.text = "CONTROLS"
			var lines := []
			var move := str(state.get("move", ""))
			if move == "2d":
				lines.append("Left thumb: stick — walk on the deck (spin gravity presses you onto it).")
			elif move == "1d":
				lines.append("Left thumb: stick up / down — along the line or the rungs.")
			else:
				lines.append("No stick here: weightless or guided, only rails and the chapter move you.")
			if I.look_wanted():
				lines.append("Right thumb: drag to look; your view also aims a push-off.")
			for a in state.get("actions", []):
				var what: String = I.action(str(a[0])).get("what", "")
				lines.append("%s — %s" % [a[1], what])
			for u in state.get("utility", []):
				lines.append("%s — %s" % [u[1], I.action(str(u[0])).get("what", "")])
			lines.append("\nLook speed ×%.2f · stick %s · touch controls %s · tips %s." % [I.touch_look, I.touch_stick, I.touch_controls,
				"on" if I.preference != "EXPERIENCED" else "off"])
			panel_body.text = "\n".join(lines)
			_panel_button("Close", close_panel, true)
			_panel_button("Look speed ×%.2f" % I.touch_look, _cycle_look)
			_panel_button("Stick: %s" % I.touch_stick, _cycle_stick)
			_panel_button("Tips: %s" % ("on" if I.preference != "EXPERIENCED" else "off"), _cycle_tips)
			_panel_button("Touch controls: %s" % I.touch_controls, _cycle_controls)
			_panel_button("Replay lessons", func(): I.replay_lessons(); _show_panel())
			_panel_button("Keyboard / controller keys", func(): close_panel(); I.overlay.open_codex())
	_layout_panel.call_deferred()

func _cycle_look() -> void:
	var i: int = I.TOUCH_LOOKS.find(I.touch_look)
	I.touch_look = I.TOUCH_LOOKS[(i + 1) % I.TOUCH_LOOKS.size()]
	I.save_profile()
	_show_panel()

func _cycle_stick() -> void:
	I.touch_stick = "fixed" if I.touch_stick == "floating" else "floating"
	I.save_profile()
	_show_panel()

func _cycle_tips() -> void:
	I.set_preference("EXPERIENCED" if I.preference != "EXPERIENCED" else "SUGGESTED")
	_show_panel()

func _cycle_controls() -> void:
	var order := ["auto", "on", "off"]
	I.touch_controls = order[(order.find(I.touch_controls) + 1) % 3]
	I.save_profile()
	_show_panel()

# ---- mobile 3-D resolution ---------------------------------------------------------------------------------------------------------

func _start_quality() -> void:
	scale_cap = clampf(RENDER_DENSITY / dpr, SCALE_MIN, 1.0)
	scale_3d = scale_cap
	_set_scale(scale_3d)

func _set_scale(s: float) -> void:
	var vp := get_tree().root
	vp.scaling_3d_mode = Viewport.SCALING_3D_MODE_BILINEAR
	vp.scaling_3d_scale = s

## Keeps the frame rate in a band by the 3-D resolution only (2-D text stays sharp): below FPS_LOW for 2 s it drops a step, above
## FPS_HIGH it climbs back toward the cap. Paused scenes and the first seconds (loading) do not count.
func _quality(dt: float) -> void:
	if not primary or get_tree().paused:
		return
	warm += dt
	if warm < 6.0:
		return
	fps_t += dt
	fps_n += 1
	if fps_t < 2.0:
		return
	var fps := fps_n / fps_t
	fps_t = 0.0
	fps_n = 0
	var before := scale_3d
	if fps < FPS_LOW and scale_3d > SCALE_MIN + 1e-3:
		scale_3d = maxf(SCALE_MIN, scale_3d * 0.85)
	elif fps > FPS_HIGH and scale_3d < scale_cap - 1e-3:
		scale_3d = minf(scale_cap, scale_3d / 0.9)
	if scale_3d != before:
		_set_scale(scale_3d)
		log.append(["scale", snappedf(scale_3d, 0.01), snappedf(fps, 0.1)])

# ---- check probe ---------------------------------------------------------------------------------------------------------------------

func snapshot() -> Dictionary:
	var out := {"device": I.device, "primary": primary, "shown": shown, "dpr": dpr, "density": ui_density(), "ui": [_size().x, _size().y],
		"safe": safe, "scale_3d": snappedf(scale_3d, 0.01), "modal": I.modal(), "mode": mode, "move": state.get("move", ""),
		"look": I.look_wanted(), "stick": [snappedf(stick.x, 0.01), snappedf(stick.y, 0.01)], "claims": claims.size(),
		"virtual": I.virtual, "fps": Engine.get_frames_per_second(), "triggered": I.triggered.slice(-12),
		"buttons": buttons.map(func(b): var r := _rect(b); return [b.id, b.label, [r.position.x, r.position.y, r.size.x, r.size.y]]),
		"preference": I.preference, "intro_done": I.touch_intro_done, "paused": get_tree().paused,
		"panel": panel_buttons.get_children().filter(func(b): return b is Button and not b.is_queued_for_deletion() and b.is_visible_in_tree()).map(
			func(b): var r: Rect2 = b.get_global_rect(); return [b.text, [r.position.x, r.position.y, r.size.x, r.size.y]]),
		"lesson": I.overlay.lesson_now.get("id", "") if I.overlay.card.visible else ""}
	var extra = state.get("probe", null)
	if extra is Callable:
		out["scene"] = extra.call()
	return out

func _publish() -> void:
	if OS.has_feature("web"):
		JavaScriptBridge.eval("window.wayfarerTouch = " + JSON.stringify(snapshot()) + ";", true)
