extends RefCounted
## MOB-001: headless acceptance check of the touch controls in Demonstrator 01 (demo01.tscn -- --check-touch; needs --fixed-fps 60).
## Real InputEventScreenTouch / ScreenDrag events go through Input as a browser's would (with Godot's mouse emulation of the first
## finger) on a scratch profile, at a phone-sized compact layout: the touch welcome by tapping, Skip / Next, Pause, the rail stick
## and look at once, weightless (no stick, look, Push off, a refused Grab), the transfer line, walking on ring A and Drop, help as a
## modal that releases the stick, focus loss, and a key press handing the prompts back to the keyboard. One WF_GODOT_TOUCH line.

var I: Node
var T: CanvasLayer
var host: Node
var demo: Node
var out: Array = []

func _ok(id: String, ok: bool, actual = null) -> void:
	out.append({"id": id, "ok": ok, "actual": actual})

func frames(n := 2) -> void:
	for k in n:
		await host.get_tree().process_frame

func physics(n: int) -> void:
	for k in n:
		await host.get_tree().physics_frame

## UI position -> window position (the events enter before the content scale, as from the browser).
func win(p: Vector2) -> Vector2:
	return p * host.get_tree().root.content_scale_factor

func touch(i: int, p: Vector2, down: bool) -> void:
	var e := InputEventScreenTouch.new()
	e.index = i
	e.position = win(p)
	e.pressed = down
	Input.parse_input_event(e)

func drag(i: int, p: Vector2, rel: Vector2) -> void:
	var e := InputEventScreenDrag.new()
	e.index = i
	e.position = win(p)
	e.relative = rel * host.get_tree().root.content_scale_factor
	Input.parse_input_event(e)

func centre(id: String) -> Vector2:
	for b in T.buttons:
		if str(b.id) == id:
			var r: Rect2 = (b.node as Control).get_global_rect()
			return r.get_center()
	return Vector2.INF

func has_button(id: String) -> bool:
	return centre(id) != Vector2.INF

func tap_button(id: String) -> bool:
	var p := centre(id)
	if p == Vector2.INF:
		return false
	touch(0, p, true)
	await frames(2)
	touch(0, p, false)
	await frames(3)
	return true

func panel_button(prefix: String) -> Button:
	for b in T.panel_buttons.get_children():
		if b is Button and b.text.begins_with(prefix) and not b.is_queued_for_deletion():
			return b
	return null

func chapter() -> String:
	return demo.CHAPTERS[demo.chapter]

func skip_to(name: String) -> void:
	var guard := 0
	while chapter() != name and guard < 12:
		guard += 1
		await tap_button("ui.confirm")
		await frames(4)

func run(h: Node) -> Dictionary:
	host = h
	demo = h.demo
	I = WfInput
	T = I.touch
	I.profile_path = "user://wf_controls_check_touch.cfg"
	DirAccess.remove_absolute(ProjectSettings.globalize_path(I.profile_path))
	I.force_prompts = true
	I.load_profile()
	host.get_window().size = Vector2i(1280, 592)          # the headless window starts at 64 x 64; 844 x 390 UI px, a phone held sideways
	T.primary = true                                     # a touch-first device; the UI density gives a phone-sized layout
	T.dpr = 1280.0 / 844.0
	I.set_device("touch")
	I.apply()
	T._start_quality()
	await frames(6)
	var vs: Vector2 = host.get_viewport().get_visible_rect().size
	_ok("compact_layout", I.compact() and absf(vs.x - 844.0) < 2.0 and not host.side_panel.visible and not host.top_box.visible, vs)
	_ok("mobile_3d_scale", absf(host.get_tree().root.scaling_3d_scale - T.scale_cap) < 1e-6 and T.scale_cap < 1.0, host.get_tree().root.scaling_3d_scale)

	# ---- touch welcome: modal, by tapping (no key), tips preference ------------------------------------------------------------------
	_ok("welcome_opens_modal", T.mode == "welcome" and I.modal() and host.get_tree().paused, T.mode)
	var start := panel_button("Start with tips")
	var at: Vector2 = start.get_global_rect().get_center() if start else Vector2.ZERO
	touch(0, at, true)
	await frames(2)
	touch(0, at, false)
	await frames(4)
	_ok("welcome_done_by_tap", T.mode == "" and not host.get_tree().paused and I.touch_intro_done and I.preference == "SUGGESTED", [T.mode, I.preference])
	var cf := ConfigFile.new()
	_ok("welcome_saved_profile", cf.load(I.profile_path) == OK and bool(cf.get_value("touch", "intro_done", false)) and int(cf.get_value("meta", "schema", 0)) == I.SCHEMA)

	# ---- EXTERIOR: guided; no stick, no look; Pause and Skip ---------------------------------------------------------------------
	_ok("exterior_guided_controls", chapter() == "EXTERIOR" and str(T.state.get("move", "")) == "" and has_button("demo.pause") and has_button("ui.confirm")
		and not has_button("player.grab"), T.buttons.map(func(b): return b.id))
	await tap_button("demo.pause")
	_ok("pause_by_button", demo.paused and "demo.pause" in I.triggered, demo.paused)
	await tap_button("demo.pause")
	await skip_to("ENTRY")
	_ok("skip_by_button", chapter() == "ENTRY", chapter())

	# ---- ENTRY: the rail stick and the look at the same time; release stops ---------------------------------------------------------
	await tap_button("demo.pause")                       # hold the guided camera: only the stick moves along the rail
	var p0: float = host.progress
	var lo0: Vector2 = host.look_offset
	var base := Vector2(110.0, vs.y - 110.0)
	touch(0, base, true)
	touch(1, Vector2(vs.x * 0.7, vs.y * 0.5), true)
	await frames(2)
	drag(0, base + Vector2(0, -50), Vector2(0, -50))
	for k in 6:
		drag(1, Vector2(vs.x * 0.7 + 10.0 * (k + 1), vs.y * 0.5), Vector2(10, 0))
		await frames(1)
	await frames(30)
	var held: float = I.strength("player.move_forward")
	_ok("stick_holds_forward", held > 0.5 and T.claims.size() == 2, held)
	_ok("stick_moves_rail", host.progress > p0 + 0.05, [p0, host.progress])
	_ok("look_with_stick_at_once", absf(host.look_offset.x - lo0.x) > 0.05, [lo0, host.look_offset])
	touch(0, base + Vector2(0, -50), false)
	await frames(3)
	var p1: float = host.progress
	await frames(20)
	_ok("release_stops", I.virtual.is_empty() and absf(host.progress - p1) < 1e-6 and I.strength("player.move_forward") == 0.0, [p1, host.progress])
	touch(1, Vector2(vs.x * 0.7 + 60.0, vs.y * 0.5), false)
	await frames(2)
	_ok("no_emulated_mouse_to_scene", not host.dragging and T.claims.is_empty(), host.dragging)
	await tap_button("demo.pause")

	# ---- MICROGRAVITY: weightless; the stick is not offered and adds nothing; look aims; Push off; a refused Grab ---------------------
	await skip_to("MICROGRAVITY")
	await physics(20)
	var tour: WfBodyTour = host.body_tour
	for wait in 300:
		if tour.actor != null and tour.actor.grip != null:
			break
		await physics(1)
	var a: WfCrewBody = tour.actor
	_ok("micro_body_ready", chapter() == "MICROGRAVITY" and a != null, [chapter(), a != null])
	if a == null:
		return {"result": "FAIL", "checks": out, "fail": ["micro_body_ready"], "log": T.log.slice(-20)}
	_ok("micro_no_stick", str(T.state.get("move", "x")) == "" and has_button("player.push") and has_button("player.release") and not has_button("player.grab"),
		T.buttons.map(func(b): return b.id))
	touch(0, base, true)
	drag(0, base + Vector2(0, -60), Vector2(0, -60))
	await physics(30)
	_ok("micro_stick_no_force", I.virtual.is_empty() and a.linear_velocity.length() < 1e-6 and a.grip != null, a.linear_velocity.length())
	touch(0, base + Vector2(0, -60), false)
	var yaw0: float = tour.yaw
	var lp := Vector2(vs.x * 0.75, vs.y * 0.5)
	touch(2, lp, true)
	for k in 4:
		drag(2, lp + Vector2(15.0 * (k + 1), 0), Vector2(15, 0))
		await frames(1)
	touch(2, lp + Vector2(60, 0), false)
	await frames(3)
	_ok("micro_look_turns_body_view", absf(tour.yaw - yaw0) > 0.05, [yaw0, tour.yaw])
	tour.yaw = yaw0
	await tap_button("player.push")
	await physics(10)
	_ok("micro_push_by_button", a.grip == null and a.linear_velocity.length() > 0.01 and "player.push" in I.triggered, a.linear_velocity.length())
	await frames(3)
	_ok("micro_buttons_follow_grip", has_button("player.grab") and not has_button("player.push"), T.buttons.map(func(b): return b.id))
	var far := false
	for wait in 600:                                     # drift on until no rail is within hand reach
		far = tour.rails.filter(func(r): return a.can_reach(r)).is_empty()
		if far:
			break
		await physics(1)
	var v_before := a.linear_velocity
	await tap_button("player.grab")
	await physics(5)
	_ok("micro_grab_refused_out_of_reach", far and a.grip == null and a.linear_velocity.distance_to(v_before) < 1e-6, [far, a.grip != null])

	# ---- TRANSFER: the line with the 1-D stick (autoplay is the visitor's choice, off here) ------------------------------------------
	await skip_to("TRANSFER")
	await physics(30)
	_ok("transfer_1d_stick", str(T.state.get("move", "")) == "1d", T.state.get("move", ""))

	# ---- GRAVITY: walking on ring A with the 2-D stick; Drop object; help is modal and releases the stick ---------------------------
	await skip_to("GRAVITY")
	await physics(90)
	a = host.body_tour.actor
	_ok("gravity_2d_stick", str(T.state.get("move", "")) == "2d" and has_button("body.drop_tool"), T.state.get("move", ""))
	var pos0 := a.global_position
	touch(0, base, true)
	drag(0, base + Vector2(0, -55), Vector2(0, -55))
	await physics(60)
	var walked := a.global_position.distance_to(pos0)
	_ok("gravity_walk_by_stick", walked > 0.2 and a.standing, walked)
	var drops: int = host.body_tour.drops
	touch(3, centre("body.drop_tool"), true)              # a second finger on a button while the stick is held
	await frames(2)
	touch(3, centre("body.drop_tool"), false)
	await frames(3)
	_ok("button_while_stick_held", host.body_tour.drops == drops + 1 and I.strength("player.move_forward") > 0.5, host.body_tour.drops)
	await tap_button("touch.help")
	_ok("help_modal_releases_stick", T.mode == "help" and host.get_tree().paused and I.virtual.is_empty() and T.claims.size() <= 1, [T.mode, I.virtual])
	await frames(2)
	var screen := Rect2(Vector2.ZERO, host.get_viewport().get_visible_rect().size)
	var off: Array = T.panel_buttons.get_children().filter(func(b): return b is Button and not screen.encloses(b.get_global_rect())).map(func(b): return b.text)
	_ok("help_buttons_on_screen", off.is_empty(), off)
	var close := panel_button("Close")
	at = close.get_global_rect().get_center() if close else Vector2.ZERO
	touch(4, at, true)
	await frames(2)
	touch(4, at, false)
	await frames(3)
	touch(0, base + Vector2(0, -55), false)
	await frames(2)
	_ok("help_closed", T.mode == "" and not host.get_tree().paused, T.mode)
	touch(0, base, true)
	drag(0, base + Vector2(40, 0), Vector2(40, 0))
	await frames(3)
	I._notification(Node.NOTIFICATION_WM_WINDOW_FOCUS_OUT)
	await physics(30)
	var v_after := a.v_solved.length() if "v_solved" in a else 0.0
	_ok("focus_loss_releases", I.virtual.is_empty() and T.stick_touch < 0, [I.virtual, v_after])
	touch(0, base + Vector2(40, 0), false)

	# ---- desktop input still works beside touch; a key hands the prompts back -------------------------------------------------------
	var k := InputEventKey.new()
	k.keycode = KEY_P
	k.physical_keycode = KEY_P
	k.pressed = true
	Input.parse_input_event(k)
	await frames(2)
	k = k.duplicate()
	k.pressed = false
	Input.parse_input_event(k)
	await frames(3)
	_ok("key_switches_device", I.device == "keyboard" and not T.shown and demo.paused and I.label("demo.pause") == "P", [I.device, I.label("demo.pause")])
	I.set_device("touch")
	_ok("touch_labels", I.label("player.grab") == "Grab" and I.label("ship.map") == "Map", I.label("player.grab"))
	DirAccess.remove_absolute(ProjectSettings.globalize_path(I.profile_path))
	var fail := out.filter(func(c): return not c.ok).map(func(c): return c.id)
	return {"result": "PASS" if fail.is_empty() else "FAIL", "checks": out, "fail": fail, "log": T.log.slice(-20)}
