extends RefCounted
## ACI-13: headless acceptance checks of the control registry and overlay (review.tscn -- --check-controls=<json>). Drives the
## overlay's modal handler with synthetic events on a scratch profile (user://wf_controls_check.cfg); the player's profile is untouched.

var I: Node
var ov: CanvasLayer
var out: Array = []

func _ok(id: String, ok: bool, actual = null) -> void:
	out.append({"id": id, "ok": ok, "actual": actual})

static func key(k: int, down := true, echo := false, shift := false) -> InputEventKey:
	var e := InputEventKey.new()
	e.keycode = k
	e.pressed = down
	e.echo = echo
	e.shift_pressed = shift
	return e

static func joyb(b: int, down := true) -> InputEventJoypadButton:
	var e := InputEventJoypadButton.new()
	e.button_index = b
	e.pressed = down
	return e

func tap(e: InputEvent) -> void:
	ov.handle(e)
	if e is InputEventKey:
		ov.handle(key(e.keycode, false))
	elif e is InputEventJoypadButton:
		ov.handle(joyb(e.button_index, false))

func kb(id: String) -> Array:
	return I.bindings[id].filter(func(x): return str(x.t) == "key").map(func(x): return int(x.k))

func run(host: Node) -> Dictionary:
	I = WfInput
	ov = I.overlay
	I.profile_path = "user://wf_controls_check.cfg"
	DirAccess.remove_absolute(ProjectSettings.globalize_path(I.profile_path))
	I.force_prompts = true
	I.load_profile()
	await host.get_tree().process_frame

	# ---- ACI-03 first launch -----------------------------------------------------------------------------------------------------
	_ok("first_launch_needed", not I.has_profile())
	ov.open_first_launch()
	_ok("first_launch_modal_pauses", ov.state == "listen" and host.get_tree().paused)
	ov.handle(key(KEY_INSERT))                                       # still held from before the prompt: ignored
	_ok("capture_ignores_opening_event", ov.state == "listen" and ov.candidate.is_empty(), ov.events[-1])
	ov.handle(key(KEY_INSERT, false))
	tap(key(KEY_ESCAPE))
	_ok("first_launch_esc_not_confirm", ov.state == "listen" and ov.candidate.is_empty(), ov.message)
	ov.armed = true
	tap(key(KEY_1))                                             # 1 opens session 1 and selects a view or layer in eight scenes
	_ok("first_launch_conflict_listed", ov.state == "conflict" and ov.conflict.others.size() >= 5 and "menu.session_1" in ov.conflict.others,
		ov.conflict.get("others", []))
	tap(key(KEY_ESCAPE))                                        # cancel: back to listening, nothing changed
	_ok("first_launch_conflict_cancel", ov.state == "listen" and kb("ui.confirm") == [KEY_ENTER, KEY_KP_ENTER] and kb("menu.session_1") == [KEY_1])
	ov.armed = true
	ov.handle(key(KEY_INSERT))
	_ok("first_launch_candidate", ov.state == "validate" and I.describe(ov.candidate) == "Insert", ov.state)
	ov.handle(key(KEY_INSERT, true, true))                           # the same press repeating is not a validation
	_ok("validate_needs_fresh_press", ov.state == "validate")
	ov.handle(key(KEY_INSERT, false))
	tap(key(KEY_U))
	_ok("validate_wrong_key_explained", ov.state == "validate" and ov.message.begins_with("That was U"), ov.message)
	tap(key(KEY_INSERT))
	_ok("first_launch_confirm_assigned", ov.state == "prefs" and kb("ui.confirm") == [KEY_INSERT] and I.bindings["ui.confirm"].any(func(x): return str(x.t) == "joyb"),
		I.bindings["ui.confirm"])
	tap(key(KEY_RIGHT))
	tap(key(KEY_LEFT))
	tap(key(KEY_INSERT))                                             # the new Confirm accepts the highlighted preference
	_ok("first_launch_prefs_saved", ov.state == "" and I.preference == "SUGGESTED" and I.has_profile() and not host.get_tree().paused
		and FileAccess.file_exists(I.profile_path), [ov.state, I.preference])

	# ---- ACI-06 persistence ------------------------------------------------------------------------------------------------------
	I.bindings = {}
	I.load_profile()
	_ok("profile_survives_restart", kb("ui.confirm") == [KEY_INSERT] and I.preference == "SUGGESTED" and I.has_profile(), I.bindings["ui.confirm"])
	_ok("inputmap_applied", InputMap.has_action("player.grab") and InputMap.action_get_events("player.grab").size() == I.bindings["player.grab"].size()
		and InputMap.action_get_events("ui.confirm").size() == I.bindings["ui.confirm"].size())
	_ok("movement_follows_keyboard_position", I.bindings["player.move_forward"][0].get("p", false) and I.label("player.move_forward") != "unassigned",
		I.label("player.move_forward"))

	# ---- ACI-06 conflicts --------------------------------------------------------------------------------------------------------
	var space := {"t": "key", "k": KEY_SPACE, "p": false}
	_ok("conflict_detected", I.conflict_of("player.grab", space).get("other", "") == "player.push", I.conflict_of("player.grab", space))
	_ok("conflict_needs_choice", not I.assign("player.grab", space).ok and kb("player.grab") == [KEY_G])
	_ok("conflict_swap", I.assign("player.grab", space, "swap").ok and kb("player.grab") == [KEY_SPACE] and kb("player.push") == [KEY_G],
		[kb("player.grab"), kb("player.push")])
	I.restore_all()
	_ok("conflict_replace", I.assign("player.release", space, "replace").ok and kb("player.release") == [KEY_SPACE] and kb("player.push").is_empty(),
		[kb("player.release"), kb("player.push")])
	I.restore_all()
	var f10 := {"t": "key", "k": KEY_F10, "p": false}
	_ok("mandatory_keeps_keyboard_input", not I.assign("player.grab", f10, "replace").ok and kb("ui.codex") == [KEY_F10])
	_ok("mandatory_swap_allowed", I.assign("player.grab", f10, "swap").ok and kb("ui.codex") == [KEY_G], kb("ui.codex"))
	I.restore_all()
	var y := {"t": "key", "k": KEY_Y, "p": false}
	_ok("multi_conflict_no_swap", I.conflict_of("ui.confirm", y).others.size() >= 3 and not I.assign("ui.confirm", y, "swap").ok and kb("eva.tug_test") == [KEY_Y])
	_ok("multi_conflict_replace", I.assign("ui.confirm", y, "replace").ok and kb("ui.confirm") == [KEY_Y] and kb("eva.tug_test").is_empty()
		and kb("flight.scenario").is_empty() and kb("explorer.view").is_empty() and I.label("eva.tug_test") != "unassigned", [kb("ui.confirm"), I.label("eva.tug_test")])
	_ok("restore_reports_taken_input", not I.restore("eva.tug_test").ok and kb("eva.tug_test").is_empty())
	I.restore_all()
	_ok("exclusive_contexts_share", I.conflict_of("player.grab", {"t": "key", "k": KEY_5, "p": false}).kind == "reuse"
		and I.conflict_of("ui.confirm", {"t": "key", "k": KEY_5, "p": false}).kind == "conflict"
		and not I.co_active(["walk"], ["body"]) and I.co_active(["body"], ["ui"]) and not I.co_active(["eva"], ["body"]))
	_ok("esc_locked", I.assign("ui.cancel", {"t": "key", "k": KEY_F4, "p": false}).ok and kb("ui.cancel").has(KEY_ESCAPE), kb("ui.cancel"))
	I.restore_all()

	# ---- ACI-09 navigator contexts ----------------------------------------------------------------------------------------------
	var clash := []                                             # no default input collides inside the contexts that run together
	for x in I.ACTIONS:
		for d in I.default_events(x.id):
			var c: Dictionary = I.conflict_of(x.id, d)
			if c.kind in ["conflict", "reserved"]:
				clash.append([x.id, I.describe(d), c])
	_ok("defaults_conflict_free", clash.is_empty(), clash)
	var navs: Array = I.ACTIONS.filter(func(x): return x.ctx.any(func(c): return c in ["nav", "space"]))
	var unlabelled := navs.filter(func(x): return I.label(x.id) == "unassigned" or not I.CONTEXTS.has(x.ctx[0]))
	_ok("navigator_actions_labelled", navs.size() >= 20 and unlabelled.is_empty() and I.label("ship.card") == "I" and I.label("space.scale_next") == "]",
		[navs.size(), unlabelled.map(func(x): return x.id)])
	_ok("navigator_inputmap", navs.all(func(x): return InputMap.has_action(x.id) and InputMap.action_get_events(x.id).size() == I.bindings[x.id].size()))
	var key_m := {"t": "key", "k": KEY_M, "p": false}
	_ok("nav_linked_with_body", I.co_active(["nav"], ["body"]) and not I.co_active(["space"], ["body"]) and not I.co_active(["space"], ["nav"])
		and I.conflict_of("player.grab", key_m).get("other", "") == "ship.map", I.conflict_of("player.grab", key_m))
	_ok("space_shares_with_ship_and_body", I.conflict_of("space.attitude", {"t": "key", "k": KEY_G, "p": false}).kind == "reuse"
		and I.conflict_of("space.chart_mode", key_m).kind == "reuse" and I.conflict_of("space.step_next", {"t": "key", "k": KEY_J, "p": false}).get("other", "") == "ship.mode")
	_ok("navigator_subviews_are_actions", "explorer.next" in I.conflict_of("ship.map", {"t": "key", "k": KEY_X, "p": false}).get("others", [])
		and I.conflict_of("space.replay", {"t": "key", "k": KEY_4, "p": false}).get("others", []) == ["space.layer_4"]
		and "explorer.step" in I.conflict_of("ship.cutaway", {"t": "key", "k": KEY_K, "p": false}).get("others", []) and I.RESERVED.is_empty(),
		[I.conflict_of("ship.map", {"t": "key", "k": KEY_X, "p": false}), I.conflict_of("space.replay", {"t": "key", "k": KEY_4, "p": false})])
	I.context = "body"
	_ok("navigator_rebind", I.assign("ship.map", {"t": "key", "k": KEY_SEMICOLON, "p": false}).ok and I.label("ship.map") == ";"
		and I.canonical_key(key(KEY_SEMICOLON)) == KEY_M and I.restore("ship.map").ok and I.label("ship.map") == "M", I.bindings["ship.map"])
	_ok("navigator_default_back_after_rebind", I.assign("ship.card", {"t": "key", "k": KEY_F3, "p": false}).ok
		and I.assign("ship.card", {"t": "key", "k": KEY_I, "p": false}).ok and kb("ship.card") == [KEY_I], kb("ship.card"))
	I.context = "menu"
	I.restore_all()

	# ---- ACI-10 every scene ------------------------------------------------------------------------------------------------------
	var scenes := ["menu", "walk", "body", "demo", "explorer", "inspector", "flight", "thermal", "life", "lab", "eva", "holo"]
	var missing := scenes.filter(func(c): return not I.ACTIONS.any(func(x): return c in x.ctx))
	_ok("every_scene_has_actions", missing.is_empty() and I.ACTIONS.size() >= 100 and I.ACTIONS.all(func(x): return x.ctx.all(func(c): return I.CONTEXTS.has(c))),
		[missing, I.ACTIONS.size()])
	I.context = "flight"
	_ok("scene_handler_follows_rebind", I.assign("flight.play", {"t": "key", "k": KEY_P, "p": false}).ok and I.key_of(key(KEY_P), ["flight"]) == KEY_SPACE
		and I.key_of(key(KEY_SPACE), ["flight"]) == KEY_NONE and I.key_of(key(KEY_ESCAPE), ["flight"]) == KEY_ESCAPE
		and I.keys("{flight.play}: play") == "P: play", I.keys("{flight.play}: play"))
	I.context = "eva"
	I.hazard = true
	I.context = "menu"
	_ok("context_change_clears_hazard", not I.hazard)
	I.restore_all()

	# ---- ACI-10 accessibility ----------------------------------------------------------------------------------------------------
	I.context = "walk"
	I.set_toggle("player.move_forward", true)
	var w := InputEventKey.new()
	w.physical_keycode = KEY_W
	w.pressed = true
	I._input(w)
	var on_after_press: bool = I.strength("player.move_forward") == 1.0
	I._input(key(KEY_W, false))
	var still_on: bool = I.strength("player.move_forward") == 1.0
	I._input(w)
	_ok("hold_can_toggle", on_after_press and still_on and I.strength("player.move_forward") == 0.0)
	I.set_toggle("player.grab", true)
	_ok("press_actions_never_toggle", not I.toggles.has("player.grab") and I.toggles.has("player.move_forward"))
	ov.open_codex()
	ov._cycle_deadzone()
	ov._cycle_sensitivity()
	ov._cycle_scale()
	ov._leave_modal()
	_ok("stick_and_text_settings_apply", is_equal_approx(InputMap.action_get_deadzone("player.move_forward"), I.stick_deadzone) and I.stick_deadzone == 0.65
		and I.stick_sensitivity == 1.5 and is_equal_approx(host.get_tree().root.content_scale_factor, 1.25), [I.stick_deadzone, I.stick_sensitivity, I.ui_scale])
	I.load_profile()
	_ok("accessibility_saved", I.toggles.has("player.move_forward") and I.stick_deadzone == 0.65 and I.stick_sensitivity == 1.5 and I.ui_scale == 1.25)
	I.set_toggle("player.move_forward", false)
	I.stick_deadzone = I.DEADZONE
	I.stick_sensitivity = 1.0
	I.ui_scale = 1.0
	I.apply()
	I.save_profile()
	I.context = "menu"

	# ---- capture filter ----------------------------------------------------------------------------------------------------------
	var mm := InputEventMouseMotion.new()
	var left := InputEventMouseButton.new()
	left.button_index = MOUSE_BUTTON_LEFT
	left.pressed = true
	var mid := InputEventMouseButton.new()
	mid.button_index = MOUSE_BUTTON_MIDDLE
	mid.pressed = true
	var x1 := InputEventMouseButton.new()
	x1.button_index = MOUSE_BUTTON_XBUTTON1
	x1.pressed = true
	var drift := InputEventJoypadMotion.new()
	drift.axis = JOY_AXIS_LEFT_Y
	drift.axis_value = 0.3
	var stick := InputEventJoypadMotion.new()
	stick.axis = JOY_AXIS_LEFT_Y
	stick.axis_value = -0.9
	var shift_alone := key(KEY_SHIFT)
	_ok("capture_filter", I.capture_of(mm).is_empty() and I.capture_of(left).is_empty() and I.capture_of(drift).is_empty()
		and I.capture_of(key(KEY_K, false)).is_empty() and I.capture_of(key(KEY_K, true, true)).is_empty() and I.capture_of(shift_alone).is_empty()
		and I.capture_of(key(KEY_K, true, false, true)).get("shift", false) and I.capture_of(key(KEY_ESCAPE)).t == "cancel"
		and I.capture_of(mid).is_empty() and I.capture_of(x1).t == "mouse" and I.capture_of(stick).s == -1)

	# ---- controller rebind through the overlay -----------------------------------------------------------------------------------
	ov.open_rebind("player.grab")
	ov.handle(joyb(JOY_BUTTON_LEFT_SHOULDER, false))
	ov.handle(joyb(JOY_BUTTON_LEFT_SHOULDER))
	_ok("joypad_candidate", ov.state == "validate", ov.state)
	ov.handle(joyb(JOY_BUTTON_LEFT_SHOULDER, false))
	ov.handle(joyb(JOY_BUTTON_LEFT_SHOULDER))
	I.device = "joypad"
	_ok("joypad_rebind_keeps_keyboard", ov.state == "" and I.label("player.grab") == "LB" and kb("player.grab") == [KEY_G], I.bindings["player.grab"])
	I.device = "keyboard"
	_ok("prompt_follows_device", I.label("player.grab") == "G")
	ov.open_rebind("player.grab")
	ov.armed = true
	tap(key(KEY_F))
	tap(key(KEY_F))
	_ok("keyboard_rebind", kb("player.grab") == [KEY_F] and I.label("player.grab") == "F", kb("player.grab"))
	I.context = "body"
	_ok("guide_follows_rebind", I.canonical_key(key(KEY_F)) == KEY_G and I.canonical_key(key(KEY_G)) == KEY_NONE and I.canonical_key(key(KEY_T)) == KEY_T
		and I.canonical_key(key(KEY_ESCAPE)) == KEY_ESCAPE)
	I.context = "menu"
	I.restore_all()

	# ---- ACI-04/05 discovery and the three preferences ---------------------------------------------------------------------------
	I.replay_lessons()
	I.preference = "SUGGESTED"
	_ok("suggested_shows_tip", I.discover("grab") and ov.state == "" and ov.card.visible)
	_ok("lesson_not_repeated", not I.discover("grab"))
	I.performed("player.grab")
	_ok("lesson_needs_proof", not I.learned.has("grab"))
	I.performed("player.release")
	_ok("lesson_learned", I.learned.has("grab"))
	I.replay_lessons()
	I.hazard = true
	_ok("no_prompt_in_hazard", not I.discover("grab") and not I.shown.has("grab"))
	I.hazard = false
	I.preference = "PERSONAL"
	_ok("personal_captures", I.discover("move_rail") and ov.state == "listen" and ov.current == "player.move_forward" and host.get_tree().paused)
	ov.armed = true
	tap(key(KEY_ENTER))                                         # Confirm (restored to Enter above) keeps the suggested input
	_ok("personal_group_one_card", ov.state == "listen" and ov.current == "player.move_back", ov.current)
	ov.armed = true
	tap(key(KEY_ESCAPE))                                        # Esc skips the rest of the group; suggested inputs stay
	_ok("personal_skip_keeps_controls", ov.state == "" and not host.get_tree().paused and kb("player.move_back") == [KEY_S] and ov.card.visible)
	I.preference = "SUGGESTED"
	I.replay_lessons()
	_ok("inspect_and_tether_lessons", I.discover("inspect") and I.discover("tether") and I.lesson("tether").proof.size() == 3)
	I.performed("ship.card")
	_ok("inspect_learned_by_card", I.learned.has("inspect") and not I.learned.has("tether"))
	I.preference = "EXPERIENCED"
	_ok("experienced_silent", not I.discover("move_deck") and ov.state == "" and I.discovered.has("player.move_left"))
	I.preference = "SUGGESTED"

	# ---- migration from an older profile -----------------------------------------------------------------------------------------
	var cf := ConfigFile.new()
	cf.set_value("bindings", "player.grab", [{"t": "key", "k": KEY_H, "p": false}])
	cf.set_value("bindings", "ui.cancel", [{"t": "joyb", "b": JOY_BUTTON_B}])
	cf.set_value("bindings", "ui.codex", [])
	cf.set_value("bindings", "old.removed_action", [{"t": "key", "k": KEY_Z, "p": false}])
	cf.save(I.profile_path)
	I.load_profile()
	_ok("migration_keeps_and_repairs", kb("player.grab") == [KEY_H] and kb("ui.cancel").has(KEY_ESCAPE) and kb("ui.codex") == [KEY_F10]
		and kb("player.push") == [KEY_SPACE] and not I.bindings.has("old.removed_action") and I.preference == "SUGGESTED", I.bindings)

	var old := ConfigFile.new()                                 # a schema-1 profile (before ACI-10) whose Confirm is Y
	old.set_value("meta", "schema", 1)
	old.set_value("meta", "first_launch_done", true)
	old.set_value("bindings", "ui.confirm", [{"t": "key", "k": KEY_Y, "p": false}, {"t": "joyb", "b": JOY_BUTTON_A}])
	old.set_value("bindings", "player.grab", [{"t": "key", "k": KEY_G, "p": false}])
	old.save(I.profile_path)
	I.load_profile()
	_ok("migration_player_choice_wins", kb("ui.confirm") == [KEY_Y] and kb("eva.tug_test").is_empty() and kb("flight.scenario").is_empty()
		and kb("eva.clip") == [KEY_T] and I.has_profile(), [kb("eva.tug_test"), kb("flight.scenario")])
	I.restore_all()

	# ---- ACI-08 Codex ------------------------------------------------------------------------------------------------------------
	I.assign("player.grab", {"t": "key", "k": KEY_H, "p": false}, "replace")
	ov.codex_all = true
	ov.codex_pick = 0
	ov.open_codex()
	tap(key(KEY_DOWN))
	var opened: bool = ov.state == "codex" and ov.codex_pick == 1 and host.get_tree().paused
	for i in range(8):
		tap(key(KEY_DOWN))
	tap(key(KEY_DELETE))                                        # the 10th row is Grab handhold: restored from H to G
	_ok("codex_restore_one", opened and kb("player.grab") == [KEY_G], [ov.codex_pick, kb("player.grab")])
	tap(key(KEY_ESCAPE))
	_ok("codex_closes", ov.state == "" and not host.get_tree().paused)

	DirAccess.remove_absolute(ProjectSettings.globalize_path(I.profile_path))
	var failed := out.filter(func(c): return not c.ok).map(func(c): return c.id)
	return {"result": "PASS" if failed.is_empty() else "FAIL", "failed": failed, "checks": out}

func _shot(host: Node, dir: String, name: String) -> void:
	for i in 6:
		await host.get_tree().process_frame
	host.get_viewport().get_texture().get_image().save_png(dir.path_join(name + ".png"))

## Stills: first launch (choose, validate, preference), a conflict, the Codex and a lesson card.
func capture(host: Node, dir: String) -> void:
	I = WfInput
	ov = I.overlay
	DirAccess.make_dir_recursive_absolute(dir)
	I.profile_path = "user://wf_controls_capture.cfg"
	DirAccess.remove_absolute(ProjectSettings.globalize_path(I.profile_path))
	I.force_prompts = true
	I.load_profile()
	ov.open_first_launch()
	await _shot(host, dir, "controls_1_first_launch")
	ov.armed = true
	ov.handle(key(KEY_INSERT))
	await _shot(host, dir, "controls_2_validate")
	ov.handle(key(KEY_INSERT, false))
	tap(key(KEY_INSERT))
	await _shot(host, dir, "controls_3_preference")
	ov.finish_first("SUGGESTED")
	ov.open_rebind("player.grab")
	ov.armed = true
	ov.handle(key(KEY_SPACE))
	await _shot(host, dir, "controls_4_conflict")
	ov._resolve("cancel")
	ov.handle(key(KEY_ESCAPE))
	ov.codex_all = true
	ov.open_codex()
	ov.codex_pick = 9
	ov._show()
	await _shot(host, dir, "controls_5_codex")
	ov._cycle_scale()
	await _shot(host, dir, "controls_7_codex_125")
	I.ui_scale = 1.0
	I.apply()
	ov._leave_modal()
	I.replay_lessons()
	I.discover("grab")
	await _shot(host, dir, "controls_6_lesson_card")
	DirAccess.remove_absolute(ProjectSettings.globalize_path(I.profile_path))
