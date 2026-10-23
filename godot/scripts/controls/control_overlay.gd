extends CanvasLayer
## ACI-03..08 (references/ACI_PLAN_2026-10-17.md): the one control UI, owned by the WfInput autoload. Modal parts (first launch,
## capture/validate, conflict choice, Control Codex) pause the scene tree so no scene consumes configuration input and nothing
## moves meanwhile; they never time out. Non-modal parts (lesson card, toast) never block play (Tale 26 NAV-TOUR-07).
## Every modal state has a pointer route (buttons) and Esc as a locked way back, so no binding can trap the player (S&E 49 NAV-019).

var I: Node                                  # the WfInput autoload (parent)
var state := ""                              # "" | listen | conflict | validate | prefs | codex
var mode := ""                               # first | discover | rebind
var queue: Array = []                        # action ids still to capture
var current := ""                            # the action being captured
var candidate := {}
var conflict := {}
var armed := false                           # the capture listens only after every input is released (ignores the opening event)
var message := ""
var message_ok := true
var lesson_now := {}
var pref_pick := 1
var codex_pick := 0                          # index into I.ACTIONS
var codex_all := false                       # false: the actions of this scene (and ui); true: every context
var codex_return := false                    # a rebind started from the Codex returns to it
var was_paused := false
var events: Array = []                          # [state, event] for the headless check

var dim := ColorRect.new()
var panel := PanelContainer.new()
var col := VBoxContainer.new()
var title := Label.new()
var body := Label.new()
var status := Label.new()
var list := VBoxContainer.new()
var scroll := ScrollContainer.new()
var detail := Label.new()
var buttons := HFlowContainer.new()
var card := PanelContainer.new()
var card_head := Label.new()
var card_body := Label.new()
var card_chips := HFlowContainer.new()
var body2 := Label.new()                      # a second text block under the hint chips (the preference question)
var hints2 := HFlowContainer.new()
var hints := HFlowContainer.new()             # the keys of the current panel as chips (keyboard route; the buttons are the pointer route)
var toast_label := Label.new()
var toast_box := PanelContainer.new()
var toast_t := 0.0
var card_done_t := 0.0
var stack := VBoxContainer.new()

func _ready() -> void:
	I = get_parent()
	layer = 120
	process_mode = Node.PROCESS_MODE_ALWAYS
	dim.color = Color(0, 0, 0, 0.55)
	dim.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	dim.mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(dim)
	panel.add_theme_stylebox_override("panel", WfReviewGuide._box(Color("17181a"), WfReviewGuide.C_NEXT, 12, 22))
	panel.set_anchors_and_offsets_preset(Control.PRESET_CENTER)
	panel.custom_minimum_size = Vector2(720, 0)
	panel.grow_horizontal = Control.GROW_DIRECTION_BOTH
	panel.grow_vertical = Control.GROW_DIRECTION_BOTH
	add_child(panel)
	col.add_theme_constant_override("separation", 10)
	panel.add_child(col)
	_style(title, 24, WfReviewGuide.C_TITLE)
	_style(body, 16, WfReviewGuide.C_BODY)
	_style(status, 15, WfReviewGuide.C_OK)
	_style(detail, 14, WfReviewGuide.C_BODY)
	for l in [title, body]:
		col.add_child(l)
	hints.add_theme_constant_override("h_separation", 14)
	hints.add_theme_constant_override("v_separation", 8)
	col.add_child(hints)
	_style(body2, 16, WfReviewGuide.C_BODY)
	col.add_child(body2)
	hints2.add_theme_constant_override("h_separation", 14)
	hints2.add_theme_constant_override("v_separation", 8)
	col.add_child(hints2)
	col.add_child(status)
	scroll.custom_minimum_size = Vector2(680, 330)
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	list.add_theme_constant_override("separation", 3)
	scroll.add_child(list)
	col.add_child(scroll)
	col.add_child(detail)
	buttons.add_theme_constant_override("h_separation", 8)
	buttons.add_theme_constant_override("v_separation", 6)
	col.add_child(buttons)
	card.add_theme_stylebox_override("panel", WfReviewGuide._box(Color(0.05, 0.05, 0.06, 0.92), WfReviewGuide.C_NEXT, 10, 14))
	card.custom_minimum_size = Vector2(420, 0)
	card.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var cc := VBoxContainer.new()
	cc.add_theme_constant_override("separation", 8)
	cc.mouse_filter = Control.MOUSE_FILTER_IGNORE
	card.add_child(cc)
	_style(card_head, 13, WfReviewGuide.C_NEXT)
	_style(card_body, 15, WfReviewGuide.C_BODY)
	card_body.custom_minimum_size = Vector2(380, 0)
	card_chips.add_theme_constant_override("h_separation", 14)
	card_chips.add_theme_constant_override("v_separation", 8)
	for c in [card_head, card_body, card_chips]:
		cc.add_child(c)
	# Lesson card and toast share one stack at the bottom centre, just above the review guide's key bar: the keys are explained
	# where the keys are shown, and the guide's step card (top left) and the scene's panels (top right) stay clear.
	stack.set_anchors_and_offsets_preset(Control.PRESET_CENTER_BOTTOM)
	stack.offset_bottom = -150
	stack.grow_horizontal = Control.GROW_DIRECTION_BOTH
	stack.grow_vertical = Control.GROW_DIRECTION_BEGIN
	stack.alignment = BoxContainer.ALIGNMENT_END
	stack.add_theme_constant_override("separation", 8)
	stack.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(stack)
	stack.add_child(card)
	_style(toast_label, 14, WfReviewGuide.C_EXPECT)
	toast_label.custom_minimum_size = Vector2(460, 0)
	toast_box.add_theme_stylebox_override("panel", WfReviewGuide._box(Color(0.05, 0.05, 0.06, 0.92), Color("5F5E5A"), 8, 10))
	toast_box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	toast_box.add_child(toast_label)
	stack.add_child(toast_box)
	I.bindings_changed.connect(_refresh)
	_show()

func _style(l: Label, size: int, c: Color) -> void:
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", c)

func is_modal() -> bool:
	return state != ""

func _enter_modal() -> void:
	if state == "":
		was_paused = get_tree().paused
	get_tree().paused = true

func _leave_modal() -> void:
	state = ""
	get_tree().paused = was_paused
	_show()

# ---- entry points ---------------------------------------------------------------------------------------------------------------------

## ACI-03: first launch. Step 1 capture Confirm, step 2 validate with a fresh press, step 3 recovery routes and preference.
func open_first_launch() -> void:
	_enter_modal()
	message = ""
	mode = "first"
	queue = ["ui.confirm"]
	_next_capture()

func open_discovery(l: Dictionary) -> void:
	_enter_modal()
	message = ""
	mode = "discover"
	lesson_now = l
	queue = l.actions.duplicate()
	_next_capture()

func open_rebind(id: String) -> void:
	_enter_modal()
	message = ""
	mode = "rebind"
	queue = [id]
	_next_capture()

func open_codex() -> void:
	_enter_modal()
	state = "codex"
	if not codex_pick in _codex_ids():
		codex_pick = _codex_ids()[0]
	message = ""
	_show()

func show_lesson(l: Dictionary) -> void:
	lesson_now = l
	card_done_t = 0.0
	_show()

func lesson_done(l: Dictionary) -> void:
	if lesson_now.get("id", "") == l.id:
		card_done_t = 3.0
	_show()

func toast(text: String) -> void:
	toast_label.text = text
	toast_t = 5.0
	_show_card()

# ---- capture pipeline -----------------------------------------------------------------------------------------------------------------

func _next_capture() -> void:
	candidate = {}
	conflict = {}
	if queue.is_empty():
		if mode == "first":
			state = "prefs"
			pref_pick = I.PREFS.find(I.preference)
			_show()
		elif mode == "discover":
			_leave_modal()
			show_lesson(lesson_now)
		elif codex_return:
			codex_return = false
			state = "codex"
			_show()
		else:
			_leave_modal()
		return
	current = queue.pop_front()
	state = "listen"
	armed = false
	_show()

## MOB-001 phone / tablet: the lesson card and toast at the top centre (the bottom belongs to the thumbs), every panel within the screen.
func _compact_layout() -> void:
	var vs := get_viewport().get_visible_rect().size
	var narrow := vs.x < 640.0
	var w := minf(400.0, vs.x - 32.0) if narrow else minf(400.0, vs.x * 0.40)
	card.custom_minimum_size.x = w
	card_body.custom_minimum_size.x = w - 30.0
	toast_label.custom_minimum_size.x = w - 20.0
	# beside the chapter text (top left) under the touch utility row (top right); centred on a narrow (upright) phone
	stack.set_anchors_and_offsets_preset(Control.PRESET_CENTER if narrow else Control.PRESET_TOP_RIGHT)
	stack.grow_horizontal = Control.GROW_DIRECTION_BOTH if narrow else Control.GROW_DIRECTION_BEGIN
	stack.grow_vertical = Control.GROW_DIRECTION_BOTH if narrow else Control.GROW_DIRECTION_END
	if not narrow:
		stack.offset_top = float(I.touch.safe[1]) + 76.0
		stack.offset_right = -(float(I.touch.safe[2]) + 12.0)
	panel.custom_minimum_size.x = minf(720.0, vs.x - 24.0)
	scroll.custom_minimum_size.x = minf(680.0, vs.x - 64.0)

func _process(dt: float) -> void:
	if I.compact():
		_compact_layout()
	if state in ["listen", "validate"] and not armed and not Input.is_anything_pressed():
		armed = true
	if toast_t > 0.0:
		toast_t -= dt
		if toast_t <= 0.0:
			toast_label.text = ""
			_show_card()
	if card_done_t > 0.0:
		card_done_t -= dt
		if card_done_t <= 0.0:
			lesson_now = {}
			_show()

func _input(e: InputEvent) -> void:
	if state == "" or e is InputEventMouseMotion or e is InputEventMouseButton and e.button_index in [MOUSE_BUTTON_LEFT, MOUSE_BUTTON_WHEEL_UP, MOUSE_BUTTON_WHEEL_DOWN]:
		return                                       # pointer clicks go to the buttons
	handle(e)
	get_viewport().set_input_as_handled()

## The modal input handler (also driven directly by the headless check).
func handle(e: InputEvent) -> void:
	match state:
		"listen": _on_listen(e)
		"conflict": _on_conflict(e)
		"validate": _on_validate(e)
		"prefs": _on_prefs(e)
		"codex": _on_codex(e)

func _key(e: InputEvent) -> int:
	return e.keycode if e is InputEventKey and e.pressed and not e.echo else KEY_NONE

func _on_listen(e: InputEvent) -> void:
	if not armed:
		if (e is InputEventKey or e is InputEventJoypadButton) and not e.pressed:
			armed = not Input.is_anything_pressed()
		events.append(["listen", "ignored before release"])
		return
	if mode != "first" and e.is_action_pressed("ui.confirm") and not e.is_echo():
		_say("Kept %s for %s." % [I.label(current, true), I.action(current).name], true)
		events.append(["listen", "kept"])
		_next_capture()
		return
	var d: Dictionary = I.capture_of(e, I.action(current).layout)
	if d.is_empty():
		return
	if d.t == "cancel":
		if mode == "first":
			_say("Esc always means Back and cannot be your Confirm. Press another key or button, or click \"Use suggested\".", false)
		else:
			_say("Cancelled: %s stays on %s." % [I.action(current).name, I.label(current, true)], true)
			if mode == "discover":
				queue = []                           # Esc skips the rest of the group: the suggested inputs stay
			_next_capture()
		events.append(["listen", "cancel"])
		return
	_take(d)

func _take(d: Dictionary) -> void:
	candidate = d
	conflict = I.conflict_of(current, d)
	events.append(["listen", "candidate " + I.describe(d) + " " + str(conflict.kind)])
	match str(conflict.kind):
		"reserved":
			_say("%s is still used for %s (%s). Choose another." % [I.describe(d), conflict.what, I.CONTEXTS[conflict.context]], false)
			candidate = {}
			armed = false
			_show()
		"conflict":
			state = "conflict"
			_show()
		_:
			if conflict.kind == "reuse":
				_say("%s also triggers %s, in a context never active at the same time; that is allowed." % [I.describe(d), I.action(conflict.other).name], true)
			else:
				message = ""
			state = "validate"
			armed = false
			_show()

func _on_conflict(e: InputEvent) -> void:
	match _key(e):
		KEY_S: _resolve("swap")
		KEY_R: _resolve("replace")
		KEY_ESCAPE, KEY_BACKSPACE: _resolve("cancel")

func _resolve(how: String) -> void:
	events.append(["conflict", how])
	if how == "cancel":
		state = "listen"
		candidate = {}
		armed = false
		_say("Not changed. Press another input.", true)
		return
	var r: Dictionary = I.conflict_of(current, candidate)
	conflict["resolution"] = how
	# Check the outcome before validating: replace must not strip a required action of its last input.
	if how == "swap" and r.get("others", []).size() > 1:
		_say("Swap works with one other action; replace clears %s from all %d." % [I.describe(candidate), r.others.size()], false)
		return
	for other in r.get("others", []):
		if how == "replace" and I.action(other).get("required", false) and not I.has_keyboard(I.bindings[other].filter(func(x): return not I.same_input(x, candidate))):
			_say("%s would be left with no keyboard input. Choose swap or another input." % I.action(other).name, false)
			return
	state = "validate"
	armed = false
	_show()

func _on_validate(e: InputEvent) -> void:
	if not armed:
		if (e is InputEventKey or e is InputEventJoypadButton) and not e.pressed:
			armed = not Input.is_anything_pressed()
		return
	var d: Dictionary = I.capture_of(e, I.action(current).layout)
	if d.is_empty():
		return
	if I.same_input(d, candidate):
		_commit()
	elif d.t == "cancel":
		state = "listen"
		candidate = {}
		armed = false
		_say("Choose again.", true)
	elif d.t == "key" and int(d.k) == KEY_BACKSPACE:
		state = "listen"
		candidate = {}
		armed = false
		_say("Choose again.", true)
	else:
		_say("That was %s. Press %s to confirm it, Backspace to choose again." % [I.describe(d), I.describe(candidate)], false)
	events.append(["validate", I.describe(d)])

func _commit() -> void:
	var r: Dictionary = I.assign(current, candidate, str(conflict.get("resolution", "")))
	events.append(["commit", current, r.ok])
	if not r.ok:
		_say(str(r.why), false)
		state = "listen"
		armed = false
		return
	_say("%s is now %s." % [I.action(current).name, I.label(current, true)], true)
	_next_capture()

func use_suggested() -> void:
	# Pointer route: the suggested (default) input for the action being captured.
	if state != "listen":
		return
	if mode == "first":
		I.bindings[current] = I.default_events(current)
		I.apply()
		_say("Confirm is %s. Click Continue or press it." % I.label(current, true), true)
		queue = []
		_next_capture()
		return
	_say("%s keeps %s." % [I.action(current).name, I.label(current, true)], true)
	_next_capture()

func _on_prefs(e: InputEvent) -> void:
	var k := _key(e)
	var jb: int = e.button_index if e is InputEventJoypadButton and e.pressed else -1
	if k in [KEY_LEFT, KEY_UP] or jb in [JOY_BUTTON_DPAD_LEFT, JOY_BUTTON_DPAD_UP]:
		pref_pick = (pref_pick + 2) % 3
		_show()
	elif k in [KEY_RIGHT, KEY_DOWN] or jb in [JOY_BUTTON_DPAD_RIGHT, JOY_BUTTON_DPAD_DOWN]:
		pref_pick = (pref_pick + 1) % 3
		_show()
	elif e.is_action_pressed("ui.confirm") and not e.is_echo():
		finish_first(I.PREFS[pref_pick])

func finish_first(pref: String) -> void:
	I.preference = pref
	I.first_launch_done = true
	I.save_profile()
	events.append(["prefs", pref])
	_leave_modal()
	toast("Controls saved. %s or the Controls button opens the Control Codex at any time." % I.label("ui.codex"))

# ---- Control Codex (ACI-08) -----------------------------------------------------------------------------------------------------------

func _codex_ids() -> Array:
	var out := []
	for i in I.ACTIONS.size():
		if codex_all or I.available(I.ACTIONS[i].id):
			out.append(i)
	return out

func _codex_step(d: int) -> void:
	var ids := _codex_ids()
	codex_pick = ids[(maxi(ids.find(codex_pick), 0) + d + ids.size()) % ids.size()]
	_show()

## Codex keys (modal, so plain keys): ↑/↓ choose, Confirm rebind, Delete restore, Tab this scene / all, H hold or toggle,
## Z text size, D stick dead zone, S stick sensitivity, Esc close. Every one is also a button.
func _on_codex(e: InputEvent) -> void:
	var k := _key(e)
	var jb: int = e.button_index if e is InputEventJoypadButton and e.pressed else -1
	if k == KEY_ESCAPE or (e.is_action_pressed("ui.cancel") and not e.is_echo()) or (e.is_action_pressed("ui.codex") and not e.is_echo()):
		_leave_modal()
	elif k == KEY_UP or jb == JOY_BUTTON_DPAD_UP:
		_codex_step(-1)
	elif k == KEY_DOWN or jb == JOY_BUTTON_DPAD_DOWN:
		_codex_step(1)
	elif k in [KEY_DELETE, KEY_BACKSPACE]:
		_restore(I.ACTIONS[codex_pick].id)
	elif k == KEY_TAB or jb == JOY_BUTTON_LEFT_SHOULDER:
		_toggle_all()
	elif k == KEY_H:
		_toggle_hold()
	elif k == KEY_Z:
		_cycle_scale()
	elif k == KEY_D:
		_cycle_deadzone()
	elif k == KEY_S:
		_cycle_sensitivity()
	elif e.is_action_pressed("ui.confirm") and not e.is_echo():
		_rebind(I.ACTIONS[codex_pick].id)

func _toggle_all() -> void:
	codex_all = not codex_all
	if not codex_pick in _codex_ids():
		codex_pick = _codex_ids()[0]
	_show()

func _toggle_hold() -> void:
	var s: Dictionary = I.ACTIONS[codex_pick]
	if s.kind != "hold":
		_say("%s is a press, not a hold." % s.name, false)
		return
	I.set_toggle(s.id, not I.toggles.has(s.id))
	_say("%s: %s." % [s.name, "one press starts it, the next stops it" if I.toggles.has(s.id) else "hold to keep it going"], true)

static func _next_of(values: Array, v: float) -> float:
	for x in values:
		if x > v + 1e-6:
			return x
	return values[0]

func _cycle_scale() -> void:
	I.ui_scale = _next_of(I.UI_SCALES, I.ui_scale)
	I.apply()
	I.save_profile()
	_say("Text and panels at %d %%." % roundi(I.ui_scale * 100.0), true)

func _cycle_deadzone() -> void:
	I.stick_deadzone = _next_of(I.DEADZONES, I.stick_deadzone)
	I.apply()
	I.save_profile()
	_say("Stick dead zone %.2f: the stick counts only past this deflection." % I.stick_deadzone, true)

func _cycle_sensitivity() -> void:
	I.stick_sensitivity = _next_of(I.SENSITIVITIES, I.stick_sensitivity)
	I.save_profile()
	_say("Stick sensitivity ×%.2f (full speed from %.0f %% deflection; a crew speed never exceeds its limit)." % [I.stick_sensitivity, 100.0 / maxf(I.stick_sensitivity, 1.0)], true)

func _rebind(id: String) -> void:
	message = ""
	codex_return = true
	mode = "rebind"
	queue = [id]
	_next_capture()

func _restore(id: String) -> void:
	var r: Dictionary = I.restore(id)
	_say("%s restored to %s." % [I.action(id).name, I.label(id, true)] if r.ok else str(r.why), r.ok)

func _cycle_pref() -> void:
	I.set_preference(I.PREFS[(I.PREFS.find(I.preference) + 1) % 3])
	_show()

# ---- drawing --------------------------------------------------------------------------------------------------------------------------

func _say(text: String, ok: bool) -> void:
	message = text
	message_ok = ok
	_show()

func _refresh() -> void:
	_show()

func _button(text: String, f: Callable, primary := false) -> Button:
	var b := Button.new()
	b.text = text
	b.focus_mode = Control.FOCUS_NONE
	b.add_theme_font_size_override("font_size", 15)
	var c := WfReviewGuide.C_NEXT if primary else Color("5F5E5A")
	for st in ["normal", "hover", "pressed"]:
		b.add_theme_stylebox_override(st, WfReviewGuide._box(Color("2C2D31") if st != "normal" else Color("232427"), c, 6, 8))
	b.pressed.connect(f)
	buttons.add_child(b)
	return b

const PREF_TEXT := {"PERSONAL": "Personal Induction: you choose the input for each new action when it first appears, then try it.",
	"SUGGESTED": "Suggested Controls (recommended): new actions use sensible defaults with a short tip; change any of them in the Codex.",
	"EXPERIENCED": "Experienced: defaults or your saved profile, no tips. The Codex stays available."}

func _hint(key: String, what: String, role := "now") -> void:
	hints.add_child(WfReviewGuide.chip(key, what, role))

func _show() -> void:
	if not is_inside_tree():
		return
	var modal := state != ""
	dim.visible = modal
	panel.visible = modal
	for c in buttons.get_children() + hints.get_children() + hints2.get_children():
		c.queue_free()
	body2.visible = state == "prefs"
	hints2.visible = state == "prefs"
	for c in list.get_children():
		c.queue_free()
	scroll.visible = state == "codex"
	detail.visible = state == "codex"
	status.text = message
	status.add_theme_color_override("font_color", WfReviewGuide.C_OK if message_ok else WfReviewGuide.C_BAD)
	status.visible = message != ""
	_show_card()
	if not modal:
		return
	var a: Dictionary = I.action(current) if current != "" else {}
	match state:
		"listen":
			if mode == "first":
				title.text = "WAYFARER — PERSONAL INTERFACE\nEstablish your primary input"
				body.text = "Choose the key or button you want to use to confirm decisions and continue.\nPress it now. Take your time: nothing is timed."
				_hint("any key or button", "becomes your Confirm", "next")
				_hint("Esc", "always Back, never Confirm", "exit")
				_button("Use suggested: %s" % I.describe(I.default_events("ui.confirm")[0]), use_suggested, true)
			else:
				var head := ("NEW ACTION DISCOVERED\n" if mode == "discover" else "REBIND\n") + str(a.name).to_upper()
				if mode == "discover" and lesson_now.actions.size() > 1:
					head += "   (%d of %d)" % [lesson_now.actions.find(current) + 1, lesson_now.actions.size()]
				title.text = head
				body.text = "%s\nPress the key or button you want for %s.  Suggested: %s" % [a.what, str(a.name).to_lower(),
					" / ".join(I.default_events(current).map(func(x): return I.describe(x)))]
				_hint("any key or button", "use it for %s" % str(a.name).to_lower(), "next")
				_hint(I.label("ui.confirm"), "keep %s" % I.label(current, true))
				_hint("Esc", "skip this lesson (suggested keys stay)" if mode == "discover" else "cancel", "exit")
				_button("Keep %s" % I.label(current), use_suggested, true)
				_button("Cancel", func(): handle(_esc()))
		"conflict":
			var names: Array = conflict.others.map(func(o): return I.action(o).name)
			var one: bool = names.size() == 1
			title.text = "%s IS ALREADY IN USE" % I.describe(candidate).to_upper()
			body.text = "%s already triggers %s, and %s can be active at the same time as %s." % [
				I.describe(candidate), ", ".join(names), "it" if one else "they", str(a.name).to_lower()]
			if one:
				_hint("S", "swap: %s takes %s" % [names[0], I.label(current, true)], "next")
			_hint("R", "replace: %s %s" % [", ".join(names) if one else "they all", ("loses " if one else "lose ") + I.describe(candidate)], "now" if one else "next")
			_hint("Esc", "cancel, change nothing", "exit")
			if one:
				_button("Swap (S)", _resolve.bind("swap"), true)
			_button("Replace (R)", _resolve.bind("replace"), not one)
			_button("Cancel (Esc)", _resolve.bind("cancel"))
		"validate":
			title.text = ("Confirm your choice" if mode == "first" else str(a.name).to_upper())
			body.text = "Press it once more, so you know it works."
			_hint(I.describe(candidate), "proceed" if mode == "first" else "confirm it for %s" % str(a.name).to_lower(), "next")
			_hint("Backspace", "choose again")
			_button("Choose again", _choose_again)
			if mode == "first":
				_button("Continue with the mouse", func(): _commit())
		"prefs":
			title.text = "WAYFARER — PERSONAL INTERFACE\nYou are always in control of your controls"
			body.text = "These keys always work, whatever you change later:"
			_hint(I.label("ui.confirm", true), "confirm")
			_hint("Esc", "back", "exit")
			_hint(I.label("ui.codex"), "Control Codex: rebind, restore, replay lessons (or the Controls button)")
			body2.text = "\nHow should new actions be introduced?\n%s" % PREF_TEXT[I.PREFS[pref_pick]]
			hints2.add_child(WfReviewGuide.chip("← →", "choose", "now"))
			hints2.add_child(WfReviewGuide.chip(I.label("ui.confirm"), "accept the highlighted one", "next"))
			for i in 3:
				var p: String = I.PREFS[i]
				_button(("▸ " if i == pref_pick else "") + p.capitalize() + (" (recommended)" if p == "SUGGESTED" else ""), finish_first.bind(p), i == pref_pick)
		"codex":
			title.text = "CONTROL CODEX"
			# the list takes what the window leaves (the visible rect is in UI units, so a larger text size gives it fewer rows)
			scroll.custom_minimum_size.y = clampf(get_viewport().get_visible_rect().size.y - 480.0, 120.0, 420.0)
			body.text = "Showing %s.   Onboarding: %s.   Device: %s." % ["every context" if codex_all else "this scene and Everywhere", I.preference.capitalize(), I.device]
			_hint("↑ ↓", "choose")
			_hint(I.label("ui.confirm"), "rebind", "next")
			_hint("Delete", "restore")
			_hint("Tab", "this scene" if codex_all else "all contexts")
			_hint("H", "hold / toggle")
			_hint("Z", "text size")
			_hint("D", "dead zone")
			_hint("S", "sensitivity")
			_hint("Esc", "close", "exit")
			var group := ""
			for i in _codex_ids():
				var g: String = I.ACTIONS[i].ctx[0]
				if codex_all and g != group:                   # a context header per group
					group = g
					var hl := Label.new()
					hl.text = I.CONTEXTS[g].to_upper()
					hl.add_theme_font_size_override("font_size", 12)
					hl.add_theme_color_override("font_color", WfReviewGuide.C_MUTED)
					list.add_child(hl)
				var r := _codex_row(i)
				list.add_child(r)
				if i == codex_pick:
					_scroll_to(r)                              # the rows no longer fit; keep the pick in view
			var s: Dictionary = I.ACTIONS[codex_pick]
			var lessons: Array = I.LESSONS.filter(func(l): return s.id in l.actions)
			var state_text := "always available" if "ui" in s.ctx else ("learned" if lessons.any(func(l): return I.learned.has(l.id)) else ("discovered" if I.discovered.has(s.id) else "not yet met"))
			detail.text = "%s — %s\nContext: %s.  %s.  %s  Input kind: %s.\n%s" % [s.name, s.what, ", ".join(s.ctx.map(func(c): return I.CONTEXTS[c])),
				"Available now" if I.available(s.id) else "Not available here", state_text[0].to_upper() + state_text.substr(1) + ".", s.kind, s.get("why", "")]
			_button("Rebind", _rebind_pick, true)
			_button("Restore this one", _restore_pick)
			if s.kind == "hold":
				_button("Hold / toggle: %s" % ("toggle" if I.toggles.has(s.id) else "hold"), _toggle_hold)
			_button("Restore all defaults", _restore_all)
			_button("Show: %s" % ("all" if codex_all else "this scene"), _toggle_all)
			_button("Onboarding: %s" % I.preference.capitalize(), _cycle_pref)
			_button("Text %d %%" % roundi(I.ui_scale * 100.0), _cycle_scale)
			_button("Dead zone %.2f" % I.stick_deadzone, _cycle_deadzone)
			_button("Sensitivity ×%.2f" % I.stick_sensitivity, _cycle_sensitivity)
			_button("Replay lessons", _replay)
			_button("Close (Esc)", _leave_modal)

func _choose_again() -> void:
	state = "listen"
	candidate = {}
	armed = false
	_show()

func _restore_all() -> void:
	I.restore_all()
	_say("All controls restored to the defaults.", true)

func _replay() -> void:
	I.replay_lessons()
	_say("Lessons will be offered again where they first appear.", true)

func _rebind_pick() -> void:
	_rebind(I.ACTIONS[codex_pick].id)

func _restore_pick() -> void:
	_restore(I.ACTIONS[codex_pick].id)

func _esc() -> InputEventKey:
	var e := InputEventKey.new()
	e.keycode = KEY_ESCAPE
	e.pressed = true
	return e

func _codex_row(i: int) -> Control:
	var s: Dictionary = I.ACTIONS[i]
	var b := Button.new()
	b.focus_mode = Control.FOCUS_NONE
	b.custom_minimum_size = Vector2(660, 32)
	var sel := i == codex_pick
	for st in ["normal", "hover", "pressed"]:
		b.add_theme_stylebox_override(st, WfReviewGuide._box(Color("2C2D31") if sel or st != "normal" else Color("1E1F22"), WfReviewGuide.C_NEXT if sel else Color("333333"), 6, 6))
	var lessons: Array = I.LESSONS.filter(func(l): return s.id in l.actions)
	var mark := "•" if "ui" in s.ctx else ("✓" if lessons.any(func(l): return I.learned.has(l.id)) else ("○" if I.discovered.has(s.id) else "·"))
	var row := HBoxContainer.new()
	row.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	row.offset_left = 10
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var name: String = s.name + ("  (toggle)" if I.toggles.has(s.id) else "")
	for c in [[mark, 22], [name, 190], [null, 280], [", ".join(s.ctx), 140]]:
		if c[0] == null:                                # the inputs as key chips, like everywhere else
			var keys := HBoxContainer.new()
			keys.custom_minimum_size = Vector2(c[1], 0)
			keys.add_theme_constant_override("separation", 6)
			keys.mouse_filter = Control.MOUSE_FILTER_IGNORE
			var evs: Array = I.bindings.get(s.id, [])
			for d in evs:
				keys.add_child(WfReviewGuide.chip(I.describe(d), "", "now"))
			if evs.is_empty():
				keys.add_child(WfReviewGuide.chip("unassigned", "", "exit"))
			for n in keys.find_children("*", "Control", true, false):
				n.mouse_filter = Control.MOUSE_FILTER_IGNORE
			row.add_child(keys)
			continue
		var l := Label.new()
		l.text = str(c[0])
		l.custom_minimum_size = Vector2(c[1], 0)
		l.clip_text = true
		l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		l.size_flags_vertical = Control.SIZE_EXPAND_FILL
		l.add_theme_font_size_override("font_size", 15)
		l.add_theme_color_override("font_color", WfReviewGuide.C_TITLE if sel else WfReviewGuide.C_BODY)
		l.mouse_filter = Control.MOUSE_FILTER_IGNORE
		row.add_child(l)
	b.add_child(row)
	b.pressed.connect(_pick.bind(i))
	return b

func _scroll_to(r: Control) -> void:
	await get_tree().process_frame                  # after the new rows have their sizes
	if is_instance_valid(r) and r.is_inside_tree():
		scroll.ensure_control_visible(r)

func _pick(i: int) -> void:
	codex_pick = i
	_show()

func _show_card() -> void:
	toast_box.visible = toast_label.text != "" and state == ""
	var l := lesson_now
	card.visible = not l.is_empty() and state == ""
	if not card.visible:
		return
	for c in card_chips.get_children():
		c.queue_free()
	if card_done_t > 0.0:
		card_head.text = "✓  LEARNED · %s" % l.title
		card_head.add_theme_color_override("font_color", WfReviewGuide.C_OK)
		card_body.visible = false
		card_chips.add_child(WfReviewGuide.chip(I.label("ui.codex"), "controls and settings" if I.device == "touch" else "change keys any time", "exit"))
		return
	card_head.text = "NEW ACTION · %s" % l.title
	card_head.add_theme_color_override("font_color", WfReviewGuide.C_NEXT)
	card_body.visible = true
	card_body.text = l.text
	# one chip per step: amber for the inputs that complete the lesson, blue for the rest, grey for the Codex
	for st in l.steps:
		var ids: Array = st[0]
		card_chips.add_child(WfReviewGuide.chip(" ".join(I.labels(ids)), st[1], "next" if ids.any(func(i): return i in l.proof) else "now"))
	card_chips.add_child(WfReviewGuide.chip(I.label("ui.codex"), "controls and settings" if I.device == "touch" else "change keys", "exit"))
