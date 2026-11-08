extends CanvasLayer
## ACI-03..08 (references/ACI_PLAN_2026-10-17.md): the one control UI, owned by the WfInput autoload. Modal parts (the controls
## setup, capture, conflict choice, Control Codex) pause the scene tree so no scene consumes configuration input and nothing
## moves meanwhile; they never time out. Non-modal parts (lesson card, toast, the Controls button) never block play (Tale 26 NAV-TOUR-07).
## Every modal state has a pointer route (buttons) and Esc as a locked way back, so no binding can trap the player (S&E 49 NAV-019).
## CTRL-001: the setup asks the essential actions of the experience one by one, Move forward first ("Which key would you like to use
## to move forward?"), and commits each key on its press; Codex changes commit at once too. Only lesson discovery asks for a second
## press to confirm.

var I: Node                                  # the WfInput autoload (parent)
var state := ""                              # "" | listen | conflict | validate | codex
var mode := ""                               # setup | discover | rebind | add
var queue: Array = []                        # action ids still to capture
var current := ""                            # the action being captured
var candidate := {}
var conflict := {}
var armed := false                           # the capture listens only after every input is released (ignores the opening event)
var message := ""
var message_ok := true
var lesson_now := {}
var setup_exp := ""                          # the experience the setup configures
var setup_done: Array = []                   # the setup's answered actions, for Back
var pending_mod: InputEventKey = null        # a modifier pressed alone: captured on its release (Run on Shift)
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
var controls_button := Button.new()          # CTRL-001: the pointer route to the Control Codex in every experience

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
	controls_button.focus_mode = Control.FOCUS_NONE
	controls_button.add_theme_font_size_override("font_size", 13)
	for st in ["normal", "hover", "pressed"]:
		controls_button.add_theme_stylebox_override(st, WfReviewGuide._box(Color(0.05, 0.06, 0.08, 0.86) if st == "normal" else Color("2C2D31"),
			WfReviewGuide.C_NEXT if st != "normal" else Color("3a4652"), 4, 6))
	controls_button.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_LEFT)
	controls_button.offset_left = 84                 # beside the page's Exit link (web/play/shell.html, bottom left)
	controls_button.offset_bottom = -8
	controls_button.grow_vertical = Control.GROW_DIRECTION_BEGIN
	controls_button.tooltip_text = "Show and change your controls"
	controls_button.pressed.connect(open_codex)
	add_child(controls_button)
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
	mode = ""
	current = ""
	get_tree().paused = was_paused
	_show()
	if I.setup_needed():                             # a Codex change (Clear all, Set up again) left the experience unconfigured
		open_setup(I.experience)

# ---- entry points ---------------------------------------------------------------------------------------------------------------------

## CTRL-001: the controls setup of an experience: its essential actions not configured yet, in setup order (Move forward first).
func open_setup(exp: String) -> void:
	if I.setup_missing(exp).is_empty() or state != "":
		return
	_enter_modal()
	message = ""
	mode = "setup"
	setup_exp = exp
	setup_done = []
	queue = I.setup_missing(exp)
	_next_capture()

func open_discovery(l: Dictionary) -> void:
	_enter_modal()
	message = ""
	mode = "discover"
	lesson_now = l
	queue = l.actions.duplicate()
	_next_capture()

func open_rebind(id: String, add := false) -> void:
	_enter_modal()
	message = ""
	mode = "add" if add else "rebind"
	queue = [id]
	_next_capture()

func open_codex() -> void:
	if state in ["listen", "conflict", "validate"]:
		return                                       # a capture in progress finishes first (its own buttons lead back)
	_enter_modal()
	state = "codex"
	codex_pick = _codex_ids()[0]                     # the first row: what the running experience needs to move
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
	pending_mod = null
	if queue.is_empty():
		if mode == "setup":
			_finish_setup()
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

## Every essential action has a key: save, apply (assign already did), close and start. A key lost meanwhile is asked again.
func _finish_setup() -> void:
	var missing: Array = I.setup_missing(setup_exp)
	if not missing.is_empty():
		queue = missing
		_next_capture()
		return
	I.save_profile()
	events.append(["setup", "done", setup_exp])
	_leave_modal()
	var keys: Array = I.setup_ids(setup_exp).map(func(i): return "%s %s" % [I.action(i).name, I.label(i, true)])
	toast("Controls saved%s: %s. Change them any time with the Controls button or %s." % [
		"" if I.persistent() and I.storage_ok else " for this visit", ", ".join(keys), I.label("ui.codex")])

## MOB-001 phone / tablet: the lesson card and toast at the top centre (the bottom belongs to the thumbs), every panel within the screen.
func _compact_layout() -> void:
	var vs := get_viewport().get_visible_rect().size
	var narrow := vs.x < 640.0
	var w := minf(400.0, vs.x - 32.0) if narrow else minf(400.0, vs.x * 0.40)
	card.custom_minimum_size.x = w
	card_body.custom_minimum_size.x = w - 30.0
	toast_label.custom_minimum_size.x = w - 20.0
	# the first free place: the right column, then the centre, then the left; never over a panel or a touch control. With no
	# room (a phone held sideways with the systems card and the map open) the card waits, hidden, until a panel closes.
	stack.set_anchors_preset(Control.PRESET_TOP_LEFT)
	stack.size = Vector2.ZERO
	var at := _free_spot(stack.get_combined_minimum_size(), vs, narrow)
	stack.modulate.a = 0.0 if at == Vector2.INF else 1.0
	if at != Vector2.INF:
		stack.position = at
	panel.custom_minimum_size.x = minf(720.0, vs.x - 24.0)
	scroll.custom_minimum_size.x = minf(680.0, vs.x - 64.0)

## Slides a box of size down each column from the top until it clears every occupied rect; INF if no place is free.
func _free_spot(size: Vector2, vs: Vector2, narrow: bool) -> Vector2:
	var safe: Array = I.touch.safe
	var taken: Array = I.touch.occupied()
	var bottom := vs.y - float(safe[3]) - 8.0
	var right := vs.x - float(safe[2]) - 12.0 - size.x
	var xs := [(vs.x - size.x) * 0.5] if narrow else [right, (vs.x - size.x) * 0.5, float(safe[0]) + 12.0]
	for x in xs:
		var y := float(safe[1]) + 12.0
		while y + size.y <= bottom:
			var r := Rect2(Vector2(x, y), size).grow(4.0)
			var hit := -1.0
			for o in taken:
				if r.intersects(o):
					hit = maxf(hit, (o as Rect2).end.y)
			if hit < 0.0:
				return Vector2(x, y)
			y = hit + 8.0
	return Vector2.INF

## The lesson card is on screen (not waiting for room).
func card_shown() -> bool:
	return card.visible and stack.modulate.a > 0.0

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
	if state == "" or e is InputEventMouseMotion or e is InputEventScreenTouch or e is InputEventScreenDrag \
			or e is InputEventMouseButton and e.button_index in [MOUSE_BUTTON_LEFT, MOUSE_BUTTON_WHEEL_UP, MOUSE_BUTTON_WHEEL_DOWN]:
		return                                       # pointer clicks go to the buttons
	handle(e)
	get_viewport().set_input_as_handled()

## The modal input handler (also driven directly by the headless check).
func handle(e: InputEvent) -> void:
	match state:
		"listen": _on_listen(e)
		"conflict": _on_conflict(e)
		"validate": _on_validate(e)
		"codex": _on_codex(e)

func _key(e: InputEvent) -> int:
	return e.keycode if e is InputEventKey and e.pressed and not e.echo else KEY_NONE

func _on_listen(e: InputEvent) -> void:
	if not armed:
		if (e is InputEventKey or e is InputEventJoypadButton) and not e.pressed:
			armed = not Input.is_anything_pressed()
		events.append(["listen", "ignored before release"])
		return
	if mode == "discover" and e.is_action_pressed("ui.confirm") and not e.is_echo():
		_say("Kept %s for %s." % [I.label(current, true), I.action(current).name], true)
		events.append(["listen", "kept"])
		_next_capture()
		return
	var layout: String = I.action(current).layout
	if e is InputEventKey and (e.keycode in MODIFIERS or e.physical_keycode in MODIFIERS):
		if e.pressed and not e.echo:
			pending_mod = e                          # alone it is the key (Shift for Run); with another key it is a modifier
		elif not e.pressed and pending_mod != null:
			var m := pending_mod
			pending_mod = null
			_take(I.capture_modifier(m, layout))
		return
	var d: Dictionary = I.capture_of(e, layout)
	if d.is_empty():
		return
	pending_mod = null
	if d.t == "cancel":
		events.append(["listen", "cancel"])
		if mode == "setup":
			_setup_back()
		else:
			_say("Cancelled: %s stays on %s." % [I.action(current).name, I.label(current, true)], true)
			if mode == "discover":
				queue = []                           # Esc skips the rest of the group: the suggested inputs stay
			_next_capture()
		return
	_take(d)

const MODIFIERS := [KEY_SHIFT, KEY_CTRL, KEY_ALT, KEY_META]

## Setup: Esc or the Back button goes back one step (that action keeps its key and is asked again).
func _setup_back() -> void:
	if setup_done.is_empty():
		_say("Esc goes back a step. Choose a key for %s, or use the buttons below." % str(I.action(current).name).to_lower(), false)
		return
	queue.push_front(current)
	current = setup_done.pop_back()
	state = "listen"
	armed = false
	message = ""
	_show()

## A shared action's keyboard input is its source's: the capture names the source (Move forward, for EVA forward thrust).
func _target(id: String) -> String:
	return I.source_of(id)

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
			message = ""
			_show()
		_:
			if conflict.kind == "reuse":
				_say("%s also triggers %s, in a context never active at the same time; that is allowed." % [I.describe(d), I.action(conflict.other).name], true)
			else:
				message = ""
			if mode == "discover":
				state = "validate"
				armed = false
				_show()
			else:
				_commit()                            # setup and Codex changes take the key on its first press

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
		if how == "replace" and I.essential(other) and I.has_keyboard(I.bindings[other]) and not I.has_keyboard(I.bindings[other].filter(func(x): return not I.same_input(x, candidate))):
			_say("%s would be left with no key. Choose swap or another key." % I.action(other).name, false)
			return
	if mode == "discover":
		state = "validate"
		armed = false
		_show()
	else:
		_commit()

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
	var r: Dictionary = I.assign(current, candidate, str(conflict.get("resolution", "")), mode == "add")
	events.append(["commit", current, r.ok])
	if not r.ok:
		_say(str(r.why), false)
		state = "listen"
		candidate = {}
		armed = false
		_show()
		return
	_say("%s is now %s." % [I.action(_target(current)).name, I.label(current, true)], true)
	if mode == "setup":
		setup_done.append(current)
	_next_capture()

## Pointer route: keep the input the action has now (setup: a saved key from an earlier visit; discovery: the suggested one).
func use_suggested() -> void:
	if state != "listen":
		return
	if mode == "setup":
		if not I.has_keyboard(I.bindings.get(current, [])):
			return
		I.confirmed[current] = true
		I.save_profile()
		setup_done.append(current)
		_say("%s keeps %s." % [I.action(current).name, I.label(current, true)], true)
		_next_capture()
		return
	_say("%s keeps %s." % [I.action(current).name, I.label(current, true)], true)
	_next_capture()

## Setup: "Use suggested controls" for every essential action still to choose (the player's conscious choice, never a silent default).
func suggest_rest() -> void:
	if mode != "setup":
		return
	var refused: Array = I.suggest_missing(setup_exp)
	events.append(["setup", "suggested", refused])
	if not refused.is_empty():
		_say("Not suggested, the key is already yours elsewhere: %s. Choose a key for it." % ", ".join(refused.map(func(i): return I.action(i).name)), false)
	queue = []
	_next_capture()

## Setup with a controller: play this visit on its inputs (nothing is saved; the keyboard setup returns on the next visit).
func controller_only() -> void:
	I.setup_skipped[setup_exp] = true
	events.append(["setup", "controller"])
	_leave_modal()
	toast("Playing with the controller. The keyboard setup opens on your next visit, or from Controls.")

func _suggested_text() -> String:
	return " ".join(I.setup_missing(setup_exp).map(func(i): return " / ".join(I.default_events(i).filter(func(x): return I._kind(x) == "keyboard").map(func(x): return I.describe(x)))))

# ---- Control Codex (ACI-08) -----------------------------------------------------------------------------------------------------------

## CTRL-001: the Codex rows in groups: this scene shows what its experience needs to start, then the scene's other actions, then
## Everywhere; "all contexts" shows every context in turn. Each group is [title, action indices].
func _codex_groups() -> Array:
	var groups := []
	if codex_all:
		for c in I.CONTEXTS:
			var ids := []
			for i in I.ACTIONS.size():
				if I.ACTIONS[i].ctx[0] == c:
					ids.append(i)
			if not ids.is_empty():
				groups.append([str(I.CONTEXTS[c]).to_upper(), ids])
		return groups
	var exp: String = I.experience
	var ess := []
	var rest := []
	var ui := []
	for i in I.ACTIONS.size():
		var a: Dictionary = I.ACTIONS[i]
		if not I.available(a.id):
			continue
		if "ui" in a.ctx:
			ui.append(i)
		elif exp != "" and exp in a.get("setup", []):
			ess.append(i)
		else:
			rest.append(i)
	if not ess.is_empty():
		groups.append(["NEEDED TO MOVE · " + str(I.EXPERIENCES[exp].name).to_upper(), ess])
	if not rest.is_empty():
		groups.append([str(I.CONTEXTS.get(I.context, I.context)).to_upper(), rest])
	groups.append(["EVERYWHERE", ui])
	return groups

func _codex_ids() -> Array:
	var out := []
	for g in _codex_groups():
		out.append_array(g[1])
	return out

## The action the Codex has selected ("" when closed), for the page state.
func codex_id() -> String:
	return str(I.ACTIONS[codex_pick].id) if state == "codex" and codex_pick < I.ACTIONS.size() else ""

func _codex_step(d: int) -> void:
	var ids := _codex_ids()
	codex_pick = ids[(maxi(ids.find(codex_pick), 0) + d + ids.size()) % ids.size()]
	_show()

## Codex keys (modal, so plain keys): ↑/↓ choose, Confirm change, Insert add a key, Delete remove a key, Backspace suggested key,
## Tab this scene / all, H hold or toggle, Z text size, D stick dead zone, S stick sensitivity, Esc close. Every one is also a button.
func _on_codex(e: InputEvent) -> void:
	var k := _key(e)
	var jb: int = e.button_index if e is InputEventJoypadButton and e.pressed else -1
	if k == KEY_ESCAPE or (e.is_action_pressed("ui.cancel") and not e.is_echo()) or (e.is_action_pressed("ui.codex") and not e.is_echo()):
		_leave_modal()
	elif k == KEY_UP or jb == JOY_BUTTON_DPAD_UP:
		_codex_step(-1)
	elif k == KEY_DOWN or jb == JOY_BUTTON_DPAD_DOWN:
		_codex_step(1)
	elif k == KEY_BACKSPACE:
		_restore(I.ACTIONS[codex_pick].id)
	elif k == KEY_DELETE:
		_remove_pick()
	elif k == KEY_INSERT:
		_add_pick()
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

func _rebind(id: String, add := false) -> void:
	message = ""
	codex_return = true
	mode = "add" if add else "rebind"
	queue = [id]
	_next_capture()

func _add_pick() -> void:
	_rebind(I.ACTIONS[codex_pick].id, true)

## Remove the last keyboard input of the selected action (its controller inputs stay); refused where a key is needed.
func _remove_pick() -> void:
	var id: String = I.ACTIONS[codex_pick].id
	var evs: Array = I.events_of(id)
	var at := -1
	for i in evs.size():
		if I._kind(evs[i]) == "keyboard":
			at = i
	if at < 0:
		_say("%s has no key to remove." % I.action(id).name, false)
		return
	var gone: String = I.describe(evs[at])
	var r: Dictionary = I.remove_input(id, at)
	_say("%s no longer on %s." % [I.action(id).name, gone] if r.ok else str(r.why), r.ok)

func _setup_again() -> void:
	if I.experience == "":
		return
	I.reconfigure(I.experience)
	_leave_modal()                                   # reopens the setup: its actions are no longer configured

func _clear_all() -> void:
	I.clear_all()
	events.append(["codex", "clear all"])
	_leave_modal()                                   # reopens the setup of the running experience
	_say("All your controls are cleared. Choose them again.", true)

func _restore(id: String) -> void:
	var r: Dictionary = I.restore(id)
	_say("%s is on its suggested input: %s." % [I.action(id).name, I.label(id, true)] if r.ok else str(r.why), r.ok)

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
	controls_button.visible = not modal and I.experience != "" and not I.compact()
	controls_button.text = "Controls  %s" % I.label("ui.codex")
	for c in buttons.get_children() + hints.get_children() + hints2.get_children():
		c.queue_free()
	body2.visible = false
	hints2.visible = false
	for c in list.get_children():
		c.queue_free()
	scroll.visible = state == "codex"
	detail.visible = state == "codex"
	status.text = message
	status.add_theme_color_override("font_color", WfReviewGuide.C_OK if message_ok else WfReviewGuide.C_BAD)
	status.visible = message != ""
	_show_card()
	I.publish_state()
	if not modal:
		return
	var a: Dictionary = I.action(_target(current)) if current != "" else {}
	match state:
		"listen":
			if mode == "setup":
				_show_setup(a)
			else:
				var head := ("NEW ACTION DISCOVERED\n" if mode == "discover" else ("ADD A KEY\n" if mode == "add" else "CHANGE\n")) + str(a.name).to_upper()
				if mode == "discover" and lesson_now.actions.size() > 1:
					head += "   (%d of %d)" % [lesson_now.actions.find(current) + 1, lesson_now.actions.size()]
				title.text = head
				var shared: Array = I.sharers_of(a.id).map(func(x): return str(I.CONTEXTS[I.action(x).ctx[0]]))
				body.text = "%s\nPress the key or button you want for %s.  Now: %s.%s" % [a.what, str(a.name).to_lower(), I.label_all(current),
					("\nShared: the same key also works in %s." % ", ".join(shared)) if not shared.is_empty() else ""]
				_hint("any key or button", ("add it to %s" if mode == "add" else "use it for %s") % str(a.name).to_lower(), "next")
				if mode == "discover":
					_hint(I.label("ui.confirm"), "keep %s" % I.label(current, true))
				_hint("Esc", "skip this lesson (suggested keys stay)" if mode == "discover" else "cancel", "exit")
				if mode == "discover":
					_button("Keep %s" % I.label(current), use_suggested, true)
				_button("Cancel", func(): handle(_esc()))
		"conflict":
			var names: Array = conflict.others.map(func(o): return I.action(o).name)
			var one: bool = names.size() == 1
			var can_swap: bool = one and I.has_keyboard(I.bindings.get(_target(current), [])) if I._kind(candidate) == "keyboard" else one
			title.text = "%s IS ALREADY IN USE" % I.describe(candidate).to_upper()
			body.text = "%s already does %s, and %s can be needed at the same time as %s." % [
				I.describe(candidate), ", ".join(names), "it" if one else "they", str(a.name).to_lower()]
			if can_swap:
				_hint("S", "swap: %s takes %s" % [names[0], I.label(current, true)], "next")
			_hint("R", "replace: %s %s" % [", ".join(names) if one else "they all", ("loses " if one else "lose ") + I.describe(candidate)], "now" if can_swap else "next")
			_hint("Esc", "cancel, choose another key", "exit")
			if can_swap:
				_button("Swap (S)", _resolve.bind("swap"), true)
			_button("Replace (R)", _resolve.bind("replace"), not can_swap)
			_button("Choose another key (Esc)", _resolve.bind("cancel"))
		"validate":
			title.text = str(a.name).to_upper()
			body.text = "Press it once more, so you know it works."
			_hint(I.describe(candidate), "confirm it for %s" % str(a.name).to_lower(), "next")
			_hint("Backspace", "choose again")
			_button("Choose again", _choose_again)
		"codex":
			_show_codex()

## CTRL-001 setup panel: one question per essential action, Move forward first.
func _show_setup(a: Dictionary) -> void:
	title.text = "CONFIGURE YOUR CONTROLS\n%s · %d of %d" % [I.EXPERIENCES[setup_exp].name, setup_done.size() + 1, setup_done.size() + queue.size() + 1]
	var have: bool = I.has_keyboard(I.bindings.get(current, []))
	body.text = "Which key would you like to use to %s?\n%s%s\nPress it now; nothing is timed.%s" % [a.get("ask", str(a.name).to_lower()), a.what,
		"\nThe same key works in both experiences." if not I.sharers_of(current).is_empty() else "",
		("\nYour saved key from an earlier visit: %s." % I.label(current, true)) if have else ""]
	if not I.persistent() or not I.storage_ok:
		body2.visible = true
		body2.text = I.storage_text()
	_hint("any key", "becomes %s" % str(a.name).to_lower(), "next")
	_hint("Esc", "back one step" if not setup_done.is_empty() else "never a game key", "exit")
	if have:
		_button("Keep %s" % I.label(current, true), use_suggested, true)
	if not setup_done.is_empty():
		_button("Back", _setup_back)
	var sug := _suggested_text()
	_button("Use suggested controls (%s)" % sug if sug.strip_edges() != "" else "Use suggested controls", suggest_rest)
	if not Input.get_connected_joypads().is_empty() and I.setup_ids(setup_exp).all(func(i): return I.events_of(i).any(func(x): return I._kind(x) == "joypad")):
		_button("Play with the controller", controller_only)

func _show_codex() -> void:
	title.text = "CONTROLS"
	# the list takes what the window leaves (the visible rect is in UI units, so a larger text size gives it fewer rows)
	scroll.custom_minimum_size.y = clampf(get_viewport().get_visible_rect().size.y - 480.0, 120.0, 420.0)
	body.text = "Showing %s.   Saved in this browser%s.   Device: %s." % ["every context" if codex_all else "this experience",
		"" if I.persistent() and I.storage_ok else " for this visit only", I.device]
	_hint("↑ ↓", "choose")
	_hint(I.label("ui.confirm"), "change", "next")
	_hint("Insert", "add a key")
	_hint("Delete", "remove a key")
	_hint("Backspace", "suggested")
	_hint("Tab", "this experience" if codex_all else "all contexts")
	_hint("H", "hold / toggle")
	_hint("Esc", "close", "exit")
	for g in _codex_groups():
		var hl := Label.new()
		hl.text = g[0]
		hl.add_theme_font_size_override("font_size", 12)
		hl.add_theme_color_override("font_color", WfReviewGuide.C_MUTED)
		list.add_child(hl)
		for i in g[1]:
			var r := _codex_row(i)
			list.add_child(r)
			if i == codex_pick:
				_scroll_to(r)                              # the rows no longer fit; keep the pick in view
	var s: Dictionary = I.ACTIONS[codex_pick]
	var lessons: Array = I.LESSONS.filter(func(l): return s.id in l.actions)
	var state_text := "always available" if "ui" in s.ctx else ("learned" if lessons.any(func(l): return I.learned.has(l.id)) else ("discovered" if I.discovered.has(s.id) else "not yet met"))
	var share_text := ""
	if s.has("share"):
		share_text = "Shares its key with %s (%s): changing one changes both.  " % [I.action(s.share).name, ", ".join(I.action(s.share).ctx.map(func(c): return I.CONTEXTS[c]))]
	elif not I.sharers_of(s.id).is_empty():
		share_text = "Its key also works as %s.  " % ", ".join(I.sharers_of(s.id).map(func(x): return "%s (%s)" % [I.action(x).name, I.CONTEXTS[I.action(x).ctx[0]]]))
	detail.text = "%s — %s\nContext: %s.  %s.  %s  Input kind: %s.  %s%s\n%s" % [s.name, s.what, ", ".join(s.ctx.map(func(c): return I.CONTEXTS[c])),
		"Available now" if I.available(s.id) else "Not available here", state_text[0].to_upper() + state_text.substr(1) + ".", s.kind,
		"Needed to move. " if I.essential(I.source_of(s.id)) and not "ui" in s.ctx else "", share_text, s.get("why", "")]
	_button("Change key", _rebind_pick, true)
	_button("Add a key", _add_pick)
	_button("Remove a key", _remove_pick)
	_button("Suggested key", _restore_pick)
	if s.kind == "hold":
		_button("Hold / toggle: %s" % ("toggle" if I.toggles.has(s.id) else "hold"), _toggle_hold)
	if I.experience != "":
		_button("Set up %s again" % I.EXPERIENCES[I.experience].name, _setup_again)
	_button("Use suggested for all", _restore_all)
	_button("Clear all my controls", _clear_all)
	_button("Show: %s" % ("all" if codex_all else "this experience"), _toggle_all)
	_button("Lessons: %s" % I.preference.capitalize(), _cycle_pref)
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
	_say("Every action is on its suggested input now.", true)

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
	var where: String = ("shared · " + str(I.action(s.share).name)) if s.has("share") else ", ".join(s.ctx)
	for c in [[mark, 22], [name, 190], [null, 280], [where, 140]]:
		if c[0] == null:                                # the inputs as key chips, like everywhere else
			var keys := HBoxContainer.new()
			keys.custom_minimum_size = Vector2(c[1], 0)
			keys.add_theme_constant_override("separation", 6)
			keys.mouse_filter = Control.MOUSE_FILTER_IGNORE
			var evs: Array = I.events_of(s.id)
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
	var compact: bool = I.compact()
	card_chips.visible = not compact
	if card_done_t > 0.0:
		card_head.text = ("LEARNED · %s" if compact else "✓  LEARNED · %s") % l.title      # the web font has no ✓ (P05)
		card_head.add_theme_color_override("font_color", WfReviewGuide.C_OK)
		card_body.visible = false
		card_chips.add_child(WfReviewGuide.chip(I.label("ui.codex"), "controls and settings" if I.device == "touch" else "change keys any time", "exit"))
		return
	card_head.text = "NEW ACTION · %s" % l.title
	card_head.add_theme_color_override("font_color", WfReviewGuide.C_NEXT)
	card_body.visible = true
	card_body.text = l.text
	if compact:
		card_body.text = I.lesson_try(l)              # MOB-001: one short line on a phone; the buttons it names are on screen
		return
	# one chip per step: amber for the inputs that complete the lesson, blue for the rest, grey for the Codex
	for st in l.steps:
		var ids: Array = st[0]
		card_chips.add_child(WfReviewGuide.chip(" ".join(I.labels(ids)), st[1], "next" if ids.any(func(i): return i in l.proof) else "now"))
	card_chips.add_child(WfReviewGuide.chip(I.label("ui.codex"), "controls and settings" if I.device == "touch" else "change keys", "exit"))
