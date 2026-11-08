extends SceneTree
## CTRL-001 headless check (godot --headless --path godot --script res://scripts/check_controls.gd): the player-action registry
## (WfInput), its first-visit controls setup, the Controls menu operations, conflict handling, profile persistence, migration of an
## older profile, a corrupted profile and a failed save, each on its own isolated profile file in user://ctrl_check/ (never the
## player's). Inputs are synthetic key, joypad and action events, handed to the overlay as a player's presses would be. It needs no
## package. Prints one WF_GODOT_CONTROLS line {"result", "tests", "fails"} and quits.

const DIR := "user://ctrl_check"
var tests := {}
var fails := []
var notes := {}

func _initialize() -> void:
	_run.call_deferred()

func ok(name: String, cond: bool, detail = null) -> void:
	tests[name] = cond
	if not cond:
		fails.append({"test": name, "detail": detail})

func key(k: int, physical := false, pressed := true) -> InputEventKey:
	var e := InputEventKey.new()
	e.keycode = k
	e.physical_keycode = k if physical else KEY_NONE
	e.pressed = pressed
	return e

func path(name: String) -> String:
	return DIR.path_join(name)

func wipe() -> void:
	DirAccess.make_dir_recursive_absolute(DIR)
	var d := DirAccess.open(DIR)
	for f in d.get_files():
		d.remove(f)

## A WfInput of its own on profile p (the autoload keeps the player's profile; this one is applied last, so the InputMap is its).
func fresh(p: String) -> Node:
	var I: Node = load("res://scripts/controls/wf_input.gd").new()
	I.profile_path = p
	I.force_prompts = true
	root.add_child(I)
	await process_frame
	return I

func drop(I: Node) -> void:
	I.overlay.state = ""
	paused = false
	I.queue_free()
	await process_frame

## A player's press of k for the capture the overlay is listening to (each capture waits until the last key is released).
func press(I: Node, e: InputEvent) -> void:
	I.overlay.armed = true
	I.overlay.handle(e)

func _run() -> void:
	wipe()
	# ---- 1. a first visit: nothing configured, the setup asks Move forward first --------------------------------------------------
	var I: Node = await fresh(path("a.cfg"))
	var ids: Array = I.setup_ids("interior")
	ok("fresh_profile_needs_setup", I.setup_missing("interior") == ids and ids.size() == 6 and I.profile_note == "new", {"missing": I.setup_missing("interior")})
	ok("fresh_no_keyboard_default", not I.has_keyboard(I.bindings["player.move_forward"]) and not key(KEY_W, true).is_action("player.move_forward")
		and not key(KEY_SPACE).is_action("exc.jump") and not key(KEY_SHIFT).is_action("exc.run"))
	var jm := InputEventJoypadMotion.new()
	jm.axis = JOY_AXIS_LEFT_Y
	jm.axis_value = -1.0
	ok("fresh_controller_kept", jm.is_action("player.move_forward") and jm.is_action("evaops.fwd"))
	ok("fresh_non_essential_suggested", key(KEY_E).is_action("exc.use"), I.label_all("exc.use"))
	I.begin("interior")
	await process_frame
	var ov: Node = I.overlay
	ok("setup_opens_paused", ov.state == "listen" and ov.mode == "setup" and paused, [ov.state, ov.mode, paused])
	ok("setup_asks_move_forward_first", ov.current == "player.move_forward" and ids[0] == "player.move_forward", ov.current)
	ok("setup_question_text", "Which key would you like to use to move forward?" in ov.body.text, ov.body.text)
	# the player chooses the arrow keys, Space and Shift (a modifier alone: captured on its release)
	press(I, key(KEY_UP, true))
	ok("setup_commits_on_press", ov.current == "player.move_back" and key(KEY_UP, true).is_action("player.move_forward"), ov.current)
	press(I, key(KEY_ESCAPE))                                            # Esc goes back one step
	ok("setup_esc_back", ov.current == "player.move_forward" and ov.state == "listen", ov.current)
	press(I, key(KEY_UP, true))
	press(I, key(KEY_DOWN, true))
	press(I, key(KEY_UP, true))                                          # Move forward's key for Move back: a conflict, never silent
	ok("setup_conflict_shown", ov.state == "conflict" and ov.conflict.get("other", "") == "player.move_forward", [ov.state, ov.conflict])
	ov._resolve("replace")                                               # would leave Move forward without a key: refused
	ok("setup_replace_refused_for_essential", ov.state == "conflict" and I.has_keyboard(I.bindings["player.move_forward"]), ov.message)
	ov._resolve("cancel")
	press(I, key(KEY_LEFT, true))
	press(I, key(KEY_RIGHT, true))
	ok("setup_jump_then_run", ov.current == "exc.jump", ov.current)
	press(I, key(KEY_SPACE))
	press(I, key(KEY_SHIFT, true))
	ov.handle(key(KEY_SHIFT, true, false))
	ok("setup_modifier_alone", I.label("exc.run") == "Shift", I.label_all("exc.run"))
	ok("setup_complete", ov.state == "" and I.setup_missing("interior").is_empty() and not paused, [ov.state, I.setup_missing("interior")])
	ok("custom_key_moves", key(KEY_UP, true).is_action("player.move_forward") and key(KEY_SPACE).is_action("exc.jump") and key(KEY_SHIFT).is_action("exc.run"))
	ok("old_default_does_not_move", not key(KEY_W, true).is_action("player.move_forward") and not key(KEY_W, true).is_action("evaops.fwd"))
	Input.parse_input_event(key(KEY_UP, true))
	await process_frame
	ok("custom_key_strength", I.strength("player.move_forward") == 1.0, I.strength("player.move_forward"))
	Input.parse_input_event(key(KEY_UP, true, false))
	await process_frame
	ok("labels_follow_binding", I.keys("{player.move_forward} walks") == "↑ walks" and I.label("evaops.fwd") == "↑", [I.keys("{player.move_forward} walks"), I.label("evaops.fwd")])
	ok("exterior_shares_moves", I.setup_missing("exterior") == ["evaops.yaw_left", "evaops.yaw_right", "evaops.boots"], I.setup_missing("exterior"))
	await drop(I)

	# ---- 2. the next visit: the same profile, no setup, the exterior asks only what it adds ----------------------------------------
	I = await fresh(path("a.cfg"))
	ov = I.overlay
	ok("returning_profile_restored", I.setup_missing("interior").is_empty() and I.label("player.move_forward") == "↑" and key(KEY_UP, true).is_action("evaops.fwd"),
		[I.setup_missing("interior"), I.label_all("player.move_forward")])
	I.begin("interior")
	await process_frame
	ok("returning_no_setup", ov.state == "", ov.state)
	I.begin("exterior")
	await process_frame
	ok("exterior_setup_only_new", ov.mode == "setup" and ov.current == "evaops.yaw_left", [ov.mode, ov.current])
	press(I, key(KEY_COMMA))
	press(I, key(KEY_PERIOD))
	press(I, key(KEY_9))
	ok("exterior_setup_complete", ov.state == "" and I.setup_missing("exterior").is_empty() and key(KEY_9).is_action("evaops.boots"), I.setup_missing("exterior"))
	# ---- 3. the Controls menu ----------------------------------------------------------------------------------------------------
	I.context = "evaops"
	ov.open_codex()
	ov.codex_pick = _index(I, "evaops.boots")
	ov._rebind_pick()
	press(I, key(KEY_PERIOD))                                            # Turn right's key: both are active together
	ok("codex_conflict_detected", ov.state == "conflict" and ov.conflict.other == "evaops.yaw_right", ov.conflict)
	ov._resolve("swap")
	ok("codex_swap", key(KEY_PERIOD).is_action("evaops.boots") and key(KEY_9).is_action("evaops.yaw_right") and ov.state == "codex",
		[I.label_all("evaops.boots"), I.label_all("evaops.yaw_right"), ov.state])
	ok("cross_experience_conflict", I.conflict_of("player.move_forward", {"t": "key", "k": KEY_I, "p": true}).get("other", "") == "evaops.pitch_up",
		I.conflict_of("player.move_forward", {"t": "key", "k": KEY_I, "p": true}))
	ok("exclusive_contexts_reuse", I.conflict_of("exc.use", {"t": "key", "k": KEY_X, "p": false}).kind == "reuse")
	ov.codex_pick = _index(I, "player.move_forward")
	ov._add_pick()
	press(I, key(KEY_W, true))
	ok("codex_add_key", key(KEY_W, true).is_action("player.move_forward") and key(KEY_UP, true).is_action("player.move_forward") and ov.state == "codex", I.label_all("player.move_forward"))
	ov._remove_pick()
	ok("codex_remove_key", not key(KEY_W, true).is_action("player.move_forward") and key(KEY_UP, true).is_action("player.move_forward"), I.label_all("player.move_forward"))
	ov._remove_pick()
	ok("codex_last_essential_key_kept", key(KEY_UP, true).is_action("player.move_forward"), ov.message)
	ov.codex_pick = _index(I, "exc.map")
	ov._remove_pick()
	ok("codex_optional_unassigned", I.label_all("exc.map") == "unassigned" and I.label("exc.map") == "unassigned", I.label_all("exc.map"))
	ov.codex_pick = _index(I, "evaops.fwd")                              # changing the shared action changes the interior's too
	ov._rebind_pick()
	press(I, key(KEY_W, true))
	ok("codex_shared_rebind_immediate", key(KEY_W, true).is_action("player.move_forward") and key(KEY_W, true).is_action("evaops.fwd")
		and not key(KEY_UP, true).is_action("player.move_forward"), I.label_all("player.move_forward"))
	ov._leave_modal()
	await drop(I)
	I = await fresh(path("a.cfg"))
	ok("codex_change_persists", key(KEY_W, true).is_action("player.move_forward") and key(KEY_PERIOD).is_action("evaops.boots")
		and I.label_all("exc.map") == "unassigned" and I.setup_missing("exterior").is_empty(), [I.label_all("player.move_forward"), I.label_all("evaops.boots")])
	I.begin("interior")
	await process_frame
	I.overlay.open_codex()
	I.overlay._clear_all()
	ok("codex_clear_all_restarts_setup", I.overlay.mode == "setup" and I.overlay.current == "player.move_forward" and not key(KEY_W, true).is_action("player.move_forward"),
		[I.overlay.mode, I.overlay.current])
	I.overlay.suggest_rest()                                             # "Use suggested controls": the player's own choice
	ok("setup_use_suggested", I.overlay.state == "" and key(KEY_W, true).is_action("player.move_forward") and I.setup_missing("interior").is_empty(), I.overlay.state)
	await drop(I)

	# ---- 4. an older profile (schema 3) is migrated without losing its custom keys -----------------------------------------------
	var cf := ConfigFile.new()
	cf.set_value("meta", "schema", 3)
	cf.set_value("meta", "preference", "PERSONAL")
	cf.set_value("bindings", "ui.confirm", [{"t": "key", "k": KEY_ENTER, "p": false}])
	cf.set_value("bindings", "player.move_forward", [{"t": "key", "k": KEY_W, "p": true}])           # still the old default
	cf.set_value("bindings", "evaops.fwd", [{"t": "key", "k": KEY_T, "p": true}])                     # customised in EVA
	cf.set_value("bindings", "player.move_back", [{"t": "key", "k": KEY_K, "p": true}])               # customised
	cf.set_value("bindings", "player.move_left", "bogus")                                             # damaged entry
	cf.set_value("bindings", "player.move_right", [{"t": "key", "k": KEY_D, "p": true}])
	cf.set_value("bindings", "exc.jump", [{"t": "key", "k": KEY_SPACE, "p": false}])
	cf.set_value("touch", "look", 1.5)                                                                # exc.run did not exist yet
	cf.save(path("old.cfg"))
	I = await fresh(path("old.cfg"))
	notes["migrated_missing"] = I.setup_missing("interior")
	ok("migration_keeps_custom", key(KEY_T, true).is_action("player.move_forward") and key(KEY_T, true).is_action("evaops.fwd") and key(KEY_K, true).is_action("player.move_back")
		and I.configured("player.move_forward") and I.configured("player.move_back"), [I.label_all("player.move_forward"), I.label_all("player.move_back")])
	ok("migration_asks_unchosen", I.setup_missing("interior") == ["player.move_left", "player.move_right", "exc.jump", "exc.run"] and I.has_keyboard(I.bindings["player.move_right"])
		and not I.has_keyboard(I.bindings["exc.run"]), I.setup_missing("interior"))
	ok("migration_keeps_settings", I.preference == "PERSONAL" and absf(I.touch_look - 1.5) < 1e-6 and I.profile_note == "migrated 3", [I.preference, I.touch_look, I.profile_note])
	I.begin("interior")
	await process_frame
	ok("migration_offers_keep", I.overlay.current == "player.move_left" and "Keep" not in _button_texts(I.overlay), _button_texts(I.overlay))
	press(I, key(KEY_A, true))
	ok("migration_keep_button", _button_texts(I.overlay).any(func(t): return t == "Keep D"), _button_texts(I.overlay))
	I.overlay.use_suggested()
	ok("migration_keep_counts", I.configured("player.move_right") and I.overlay.current == "exc.jump", I.overlay.current)
	await drop(I)
	var saved := ConfigFile.new()
	saved.load(path("old.cfg"))
	ok("migration_saves_schema4", int(saved.get_value("meta", "schema", 0)) == 4 and "player.move_forward" in saved.get_value("setup", "confirmed", []))

	# ---- 5. a corrupted profile, then a save that fails ----------------------------------------------------------------------
	var f := FileAccess.open(path("bad.cfg"), FileAccess.WRITE)
	f.store_string("[[[ not a profile\nbindings = {{{")
	f.close()
	I = await fresh(path("bad.cfg"))
	ok("corrupt_profile_safe", I.profile_note == "corrupt" and FileAccess.file_exists(path("bad.cfg.bad")) and I.setup_missing("interior").size() == 6, I.profile_note)
	await drop(I)
	I = await fresh(path("no_such_dir/deeper/x.cfg"))
	var r: Dictionary = I.assign("player.move_forward", {"t": "key", "k": KEY_UP, "p": true})
	ok("storage_failure_still_plays", r.ok and not I.storage_ok and key(KEY_UP, true).is_action("player.move_forward"), [r, I.storage_ok])
	# ---- 6. semantic injection, touch and controller -------------------------------------------------------------------------
	I.set_virtual("player.move_back", 0.7)
	ok("inject_virtual_hold", absf(I.strength("player.move_back") - 0.7) < 1e-6 and not I.has_keyboard(I.bindings["player.move_back"]))
	I.set_virtual("player.move_back", 0.0)
	var ia := InputEventAction.new()
	ia.action = "exc.jump"
	ia.pressed = true
	ok("inject_action_event", I.action_of(ia, ["excursion"]) == "exc.jump" and I.trigger("exc.jump"))
	I.device = "touch"
	ok("touch_labels_kept", I.label("player.move_forward") == "stick up" and I.label("exc.jump") != "")
	I.device = "joypad"
	ok("joypad_labels_kept", I.label("player.move_forward") == "left stick up", I.label("player.move_forward"))
	I.force_prompts = false
	ok("checks_never_gated", not I.prompts_enabled() and not I.setup_needed())
	await drop(I)

	var result := "PASS" if fails.is_empty() else "FAIL"
	print("WF_GODOT_CONTROLS ", JSON.stringify({"result": result, "tests": tests, "fails": fails, "notes": notes}))
	quit(0 if fails.is_empty() else 1)

func _index(I: Node, id: String) -> int:
	for i in I.ACTIONS.size():
		if I.ACTIONS[i].id == id:
			return i
	return -1

func _button_texts(ov: Node) -> Array:
	return ov.buttons.get_children().filter(func(b): return not b.is_queued_for_deletion()).map(func(b): return b.text)
