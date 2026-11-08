extends SceneTree
var out := "/tmp/claude-0/-home-user-ignition-wayfarer/c1d73e6c-30fe-567d-9ac0-a0caecc180e3/scratchpad/shots"
func _initialize() -> void:
	_run.call_deferred()
func snap(n: String) -> void:
	for i in 4:
		await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(out.path_join(n + ".png"))
func k(code: int, phys := false, down := true) -> InputEventKey:
	var e := InputEventKey.new(); e.keycode = code; e.physical_keycode = code if phys else KEY_NONE; e.pressed = down; return e
func _run() -> void:
	DirAccess.make_dir_recursive_absolute(out)
	DirAccess.remove_absolute(ProjectSettings.globalize_path("user://shots.cfg"))
	var bg := ColorRect.new(); bg.color = Color(0.03, 0.045, 0.06); bg.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var cl := CanvasLayer.new(); cl.add_child(bg); root.add_child(cl)
	var I: Node = load("res://scripts/controls/wf_input.gd").new()
	I.profile_path = "user://shots.cfg"; I.force_prompts = true
	root.add_child(I)
	await process_frame
	I.context = "excursion"
	I.begin("interior")
	await snap("1_setup_move_forward")
	var ov = I.overlay
	for c in [KEY_UP, KEY_DOWN, KEY_LEFT]:
		ov.armed = true; ov.handle(k(c, true))
	await snap("2_setup_move_right")
	ov.armed = true; ov.handle(k(KEY_UP, true))
	await snap("3_setup_conflict")
	ov._resolve("cancel"); ov.armed = true; ov.handle(k(KEY_RIGHT, true))
	ov.armed = true; ov.handle(k(KEY_SPACE)); ov.armed = true; ov.handle(k(KEY_SHIFT, true)); ov.handle(k(KEY_SHIFT, true, false))
	await snap("4_after_setup_toast")
	ov.open_codex()
	await snap("5_controls_menu_interior")
	ov._leave_modal()
	I.context = "evaops"
	I.begin("exterior")
	await snap("6_setup_exterior_turn")
	quit()
