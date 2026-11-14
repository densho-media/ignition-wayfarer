class_name WfCheckPlayer
extends RefCounted
## Shared by the systems and Deadship checks: walk the trainee as a player would (doors opened by Use), act at a point either by
## calling the scene's own Use / Ops handler (headless) or, with `--await-player`, by waiting for the real input (the browser check
## presses the player's own key or taps the touch button; the scene's input handling then calls the same handler), and take stills.
## Stills: `--shots=<dir>` natively (needs a display); in a browser a WF_SHOT line asks the page for a screenshot and waits for it.

var h: WfExcursion
var ex: WfExcursionCheck
var await_player := false
var shots := ""
var fails: Array = []
var awaited := 0

func _init(host: WfExcursion) -> void:
	h = host
	ex = WfExcursionCheck.new()
	ex.h = host
	for a in OS.get_cmdline_user_args():
		if a == "--await-player":
			await_player = true
		if a.begins_with("--shots="):
			ex.shots = a.trim_prefix("--shots=")
			DirAccess.make_dir_recursive_absolute(ex.shots)
	shots = ex.shots
	if shots != "" or (await_player and OS.has_feature("web")):
		h.get_viewport().disable_3d = true      # 3D is drawn only for the stills (software GL draws the whole ship slowly)

## Progress lines for a browser check (the page cannot see inside the engine otherwise).
func trace(msg: String) -> void:
	if OS.has_feature("web"):
		print("WF_TRACE %d %s @%s" % [Engine.get_physics_frames(), msg, str(h.actor.global_position.snapped(Vector3.ONE * 0.01))])

func fail(msg: String) -> void:
	fails.append(msg)
	push_warning("check: " + msg)

func ticks(n: int) -> void:
	for i in n:
		await h.get_tree().physics_frame

## Walk the ring circuit from the nearest point, in order, until `reached` holds; then step towards `target` if it is beside the path.
func walk_until(reached: Callable, target: Callable, reach: float, ring := "RING_A", near := -1.0) -> bool:
	if near < 0.0:
		near = reach - 0.5
	var c: Dictionary = h.stages["circuit"][ring]
	var pts: Array = []
	for q in c["circuit_m"]:
		pts.append(WfLine.g(q))
	for dir in [1, -1]:
		var i0 := 0
		for i in pts.size():
			if (pts[i] as Vector3).distance_to(h.actor.global_position) < (pts[i0] as Vector3).distance_to(h.actor.global_position):
				i0 = i
		for j in pts.size() + 1:
			if reached.call():
				return true
			trace("walk %d/%d dir %d" % [j, pts.size(), dir])
			if not await ex._walk_to(pts[posmod(i0 + dir * j, pts.size())], 0.45, 90.0, 0):
				break
			# beside the target: step straight to it
			if (target.call() as Vector3).distance_to(h.actor.global_position) < reach + 3.0:
				await ex._walk_to(target.call(), near, 30.0, 0)
				if reached.call():
					return true
		if reached.call():
			return true
	await ex._walk_to(target.call(), near, 30.0, 0)
	fails.append_array(ex.fails)
	ex.fails = []
	return reached.call()

## One player action: headless, call the scene's handler; with --await-player, publish what is awaited and wait for the real input to
## change `done` (the page presses the player's binding or taps the touch button). Returns the handler's result (or "awaited").
func act(action: String, label: String, handler: Callable, done: Callable, limit_s := 180.0) -> String:
	if not await_player:
		var r := str(handler.call())
		await ticks(2)                          # the scene's own frame then follows the action (a step completes on the next frame)
		return r
	trace("act " + label)
	awaited += 1
	var rec := {"action": action, "label": label, "n": awaited}
	WfWebPage.publish("wayfarerAwait", rec)
	print("WF_AWAIT " + JSON.stringify(rec))
	var n := 0
	while not done.call():
		await ticks(1)
		n += 1
		if n > int(limit_s * 60.0):
			fail("waited %d s for the player's %s (%s)" % [int(limit_s), action, label])
			return ""
	WfWebPage.publish("wayfarerAwait", {"action": "", "label": "", "n": awaited})
	await ticks(2)                              # as headless: the scene's frame after the action completes its step
	return "awaited"

## A still looking at a body-frame point from the trainee's eyes; with `from`, the trainee first steps to that spot (stills only).
func shot(name: String, look_at: Vector3, from := Vector3.INF, side := 0.0) -> void:
	if from != Vector3.INF and (shots != "" or (await_player and OS.has_feature("web"))):
		await ex._walk_to(from, 0.3, 20.0, 0)
		ex.face(look_at - (h.actor.global_position + h.ref_basis().y * 1.6))
		await ex._walk_to(h.actor.global_position - h.look_basis().x * side, 0.25, 10.0, 0)   # beside what stands in front of it
		ex.fails = []
		h.walk_override = Vector3.ZERO
		await ticks(20)
	ex.face(look_at - (h.actor.global_position + h.ref_basis().y * 1.6))
	var third := h.view_out
	h.view_out = false                         # the trainee's own eyes: a follow camera behind them sees the wall, not the board
	await _shot(name)
	h.view_out = third

func _shot(name: String) -> void:
	if shots != "":
		await ex.shot(name, h.yaw, h.pitch)
		return
	if not (await_player and OS.has_feature("web")):
		return
	h.get_viewport().disable_3d = false
	RenderingServer.render_loop_enabled = true     # the browser check runs with --disable-render-loop; draw only for the still
	for i in 6:
		await RenderingServer.frame_post_draw
	print("WF_SHOT " + name)
	WfWebPage.publish("wayfarerShot", {"name": name})
	var n := 0
	while n < 60 * 240:
		var got = JavaScriptBridge.eval("window.wayfarerShotDone || ''", true)
		if str(got) == name:
			break
		await h.get_tree().process_frame
		n += 1
	RenderingServer.render_loop_enabled = false     # the browser check runs without drawing between stills
	h.get_viewport().disable_3d = true

## A spot in front of an equipment point's face (along its thinnest axis, on the trainee's side), where nothing stands between the eyes
## and its board.
func front_of(eq: WfEquipment, id := "bay") -> Vector3:
	var m: MeshInstance3D = eq.points[id]["mesh"]
	var box := m.get_aabb()
	var ax := 0
	for i in 3:
		if box.size[i] < box.size[ax]:
			ax = i
	var c := eq.centre(id)
	var n := Vector3.ZERO
	n[ax] = 1.0
	var tip := eq.to_body(m.global_transform * (box.get_center() + n * 0.5), m)
	var dir := (tip - c).normalized()
	var up: Vector3 = h.actor.up_now
	dir = (dir - up * dir.dot(up)).normalized()
	var foot := h.actor.global_position
	var a := c + dir * 1.7
	var b := c - dir * 1.7
	var pick := a if a.distance_to(foot) < b.distance_to(foot) else b
	return pick + up * (foot - pick).dot(up)

## The middle of an equipment point's board text, in the walking body's frame.
func board_mid(eq: WfEquipment) -> Vector3:
	return eq.to_body(eq.board.global_transform * eq.board.get_aabb().get_center())
