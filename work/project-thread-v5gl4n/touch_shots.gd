extends SceneTree
## MOB-002 study (work/ only): opens Explore Exterior as a touch-first phone (-- --touch), taps through the welcome, drives the two
## sticks and a hold button with synthetic touches and saves phone-size stills. Prints WF_TOUCH_SHOTS {checks}.
##   godot --path godot --resolution 844x390 --script <abs>/touch_shots.gd -- --touch --shots-out=<dir>

var out := "/tmp"
var t := 0.0
var step := 0
var ops
var checks := {}
var pos0 := Vector3.ZERO
var yaw0 := 0.0

func _initialize() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--shots-out="):
			out = a.substr(12)
	change_scene_to_file.call_deferred("res://scenes/eva_ops.tscn")

func _touch(i: int, p: Vector2, down: bool) -> void:
	var e := InputEventScreenTouch.new()
	e.index = i
	e.position = p
	e.pressed = down
	Input.parse_input_event(e)

func _drag(i: int, p: Vector2, rel: Vector2) -> void:
	var e := InputEventScreenDrag.new()
	e.index = i
	e.position = p
	e.relative = rel
	Input.parse_input_event(e)

func _shot(name: String) -> void:
	var img := root.get_texture().get_image()
	img.save_png(out.path_join(name + ".png"))

func _touch_layer():
	return root.get_node("WfInput").touch

func _button(id: String) -> Dictionary:
	for b in _touch_layer().buttons:
		if b.id == id:
			return b
	return {}

func _centre(b: Dictionary) -> Vector2:
	return (b.node as Control).get_global_rect().get_center()

func _process(dt: float) -> bool:
	t += dt
	var T = _touch_layer()
	if ops == null:
		ops = current_scene if current_scene != null and current_scene.has_method("touch_state") else null
		return false
	var vs: Vector2 = root.get_visible_rect().size
	match step:
		0:
			if t > 3.0:
				_shot("eva_touch_0_welcome")
				if T.mode == "welcome":
					T.finish_welcome("SUGGESTED")
				step = 1; t = 0.0
		1:
			if t > 1.5:
				_shot("eva_touch_1_walkway")
				checks["buttons"] = T.buttons.map(func(b): return b.id)
				pos0 = ops.suit.global_position
				_touch(1, Vector2(vs.x * 0.15, vs.y * 0.75), true)
				_drag(1, Vector2(vs.x * 0.15, vs.y * 0.75 - 60), Vector2(0, -60))
				step = 2; t = 0.0
		2:
			if t > 0.4 and t - dt <= 0.4:
				_touch(2, T.rstick_rest, true)
				_drag(2, T.rstick_rest + Vector2(50, 0), Vector2(50, 0))
			if t > 1.0 and not checks.has("sticks_shot"):
				checks["sticks_shot"] = true
				_shot("eva_touch_2_sticks")
			if t > 4.0:
				_touch(1, Vector2(vs.x * 0.15, vs.y * 0.75 - 60), false)
				_touch(2, T.rstick_rest + Vector2(50, 0), false)
				checks["walked_m"] = ops.suit.global_position.distance_to(pos0)
				step = 3; t = 0.0
		3:
			if t > 0.5:
				var b := _button("evaops.boots")
				checks["boots_before"] = ops.suit.boots.armed
				if not b.is_empty():
					_touch(3, _centre(b), true)
					_touch(3, _centre(b), false)
				step = 4; t = 0.0
		4:
			if t > 1.0:
				checks["boots_after"] = ops.suit.boots.armed
				_shot("eva_touch_3_floating")
				checks["buttons_floating"] = T.buttons.map(func(b): return b.id)
				var u := _button("evaops.up")
				pos0 = ops.suit.global_position
				if not u.is_empty():
					_touch(4, _centre(u), true)
				step = 5; t = 0.0
		5:
			if t > 1.5:
				var u := _button("evaops.up")
				if not u.is_empty():
					_touch(4, _centre(u), false)
				checks["up_moved_m"] = ops.suit.global_position.distance_to(pos0)
				var m := _button("touch.menu")
				if not m.is_empty():
					_touch(5, _centre(m), true)
					_touch(5, _centre(m), false)
				step = 6; t = 0.0
		6:
			if t > 1.0:
				checks["menu_open"] = T.mode == "menu"
				_shot("eva_touch_4_more")
				T.close_panel()
				step = 7; t = 0.0
		7:
			if t > 0.3 and t - dt <= 0.3:
				var h := _button("touch.help")
				_touch(6, _centre(h), true)
				_touch(6, _centre(h), false)
			if t > 1.2:
				checks["help_open"] = T.mode == "help"
				_shot("eva_touch_5_help")
				T.close_panel()
				step = 8; t = 0.0
		8:
			if t > 0.3 and t - dt <= 0.3:
				var d := _button("evaops.drone")
				_touch(7, _centre(d), true)
				_touch(7, _centre(d), false)
			if t > 1.5:
				checks["drone_active"] = ops.active == "drone"
				_shot("eva_touch_6_drone")
				var u := _button("evaops.dock")
				_touch(8, _centre(u), true)
				_touch(8, _centre(u), false)
				step = 9; t = 0.0
		9:
			if t > 3.0:
				checks["undocked"] = not ops.docked
				checks["buttons_drone"] = T.buttons.map(func(b): return b.id)
				_shot("eva_touch_7_drone_undocked")
				ops.do_action("evaops.astronaut")
				ops.do_action("evaops.scenario")
				step = 10; t = 0.0
		10:
			if t > 2.0:
				_shot("eva_touch_8_first_flight")
				print("WF_TOUCH_SHOTS ", JSON.stringify(checks))
				quit()
	return false
