class_name WfLocomotionCheck
extends RefCounted
## LOCO-001 headless check (-- --check-locomotion): the Explore Interior start on ring A's deck, driven through the player's own requests
## (the walk direction, run, jump, the training reset), never by moving the body. It asserts the physical promises: the trainee stands on the
## deck at about 0.5 g from the ring's rotation alone, walks and runs at the requested speeds through the friction-limited foot contact, a jump
## is one impulse from the floor that rises about dv^2/2g and lands again (no second jump in the air), the newcomer model and every clip are
## loaded (no proxy), the clips play at the measured floor speed, the third-person camera never ends inside a collider, and nothing moves the
## body beyond its own velocity. Prints one WF_GODOT_LOCOMOTION line and quits.

var h: WfExcursion
var fails: Array = []
var notes := {}
var t0 := 0
const CLIPS := ["idle", "walk", "run", "jump", "fall", "land", "step", "climb"]

var shots := ""                       # -- --shots=<dir>: stills of the trainee (needs a display, e.g. xvfb-run)

func shot(name: String) -> void:
	if shots == "" or DisplayServer.get_name() == "headless":
		return
	for i in 3:
		await RenderingServer.frame_post_draw
	h.get_viewport().get_texture().get_image().save_png(shots.path_join(name + ".png"))

func run(host: WfExcursion) -> void:
	h = host
	t0 = Time.get_ticks_msec()
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--shots="):
			shots = a.trim_prefix("--shots=")
			DirAccess.make_dir_recursive_absolute(shots)
	await _ticks(30)
	await shot("loco_1_start")
	var L := h.loco
	if h.start_mode != "RING" or h.move != "WALK" or h.walk_zone != "RING_A":
		fail("the start is %s %s %s, not standing on ring A" % [h.start_mode, h.move, h.walk_zone])
	if h.char_rig == null or not h.char_rig.ok:
		fail("the newcomer model is missing (%s): no proxy is allowed" % ("no rig" if h.char_rig == null else h.char_rig.missing))
	else:
		var missing := CLIPS.filter(func(c): return not h.char_rig.has(c))
		if not missing.is_empty():
			fail("clips missing from the newcomer: %s" % [missing])
		notes["clip_speed_m_s"] = h.char_rig.clip_speed.duplicate()
	var g := h.actor.field_now.length() / 9.80665
	notes["g_deck"] = snappedf(g, 0.001)
	if absf(g - 0.5) > 0.05:
		fail("the deck field is %.3f g, not about 0.50 g" % g)
	if not h.actor.standing:
		fail("the trainee is not standing on the deck after 0.5 s")
	# walk forward along the heading for 3 s
	var start := h.actor.global_position
	var fwd := L.heading
	h.walk_override = fwd
	vmax = 0.0
	await _ticks(150)
	await shot("loco_2_walk")
	await _ticks(30)
	var vw := vmax
	notes["walk"] = {"speed_m_s": snappedf(vw, 0.01), "clip": vmax_clip, "rate": snappedf(h.char_rig.rate_for("walk", vw), 0.01),
		"moved_m": snappedf(h.actor.global_position.distance_to(start), 0.01)}
	if absf(vw - L.num("walk_speed_m_s", 1.0)) > 0.15:
		fail("walking at %.2f m/s, not the requested %.2f" % [vw, L.num("walk_speed_m_s", 1.0)])
	if vmax_clip != "walk":
		fail("walking shows the %s clip" % vmax_clip)
	# run (Shift with forward)
	h.run_override = true
	vmax = 0.0
	await _ticks(150)
	await shot("loco_3_run")
	await _ticks(30)
	var vr := vmax
	notes["run"] = {"speed_m_s": snappedf(vr, 0.01), "clip": vmax_clip, "rate": snappedf(h.char_rig.rate_for("run", vr), 0.01)}
	if absf(vr - L.num("run_speed_m_s", 2.4)) > 0.25:
		fail("running at %.2f m/s, not the requested %.2f" % [vr, L.num("run_speed_m_s", 2.4)])
	if vmax_clip != "run":
		fail("running shows the %s clip" % vmax_clip)
	h.run_override = false
	h.walk_override = Vector3.ZERO
	await _ticks(120)
	if L.floor_speed() > 0.08 or L.clip != "idle":
		fail("not at rest after stopping: %.2f m/s, clip %s" % [L.floor_speed(), L.clip])
	# a standing jump, and a second press in the air that must do nothing
	var j0 := L.jumps
	var p0 := h.actor.global_position
	var up0 := h.actor.up_now
	h.jump_queued = true
	var air_seen := false
	var second := false
	var landed_at := -1
	for i in 240:
		await _ticks(1)
		if L.state == WfLocomotion.S.AIR:
			air_seen = true
			if not second and L.t_state > 0.15:
				second = true
				h.jump_queued = true          # a double jump: refused, the feet have nothing to push on
		if air_seen and L.t_state > 0.25 and L.t_state < 0.27 and L.state == WfLocomotion.S.AIR:
			await shot("loco_4_jump")
		if air_seen and L.state in [WfLocomotion.S.LAND, WfLocomotion.S.GROUND] and landed_at < 0:
			landed_at = i
	var drift := (h.actor.global_position - p0)
	drift -= up0 * drift.dot(up0)
	# in the ring frame: the body keeps the deck's speed w r and adds dv toward the axis; it comes nearest the axis at r vt / |v|
	var r0 := L._radius()
	var vt := sqrt(g * 9.80665 * r0)
	var dvj := L.num("jump_dv_m_s", 1.4)
	var expect := r0 - r0 * vt / sqrt(vt * vt + dvj * dvj)
	notes["jump"] = {"rise_m": snappedf(L.max_rise, 0.001), "expected_m": snappedf(expect, 0.001), "jumps": L.jumps - j0,
		"landed_after_frames": landed_at, "land_speed_m_s": snappedf(L.land_speed, 0.01), "coriolis_drift_m": snappedf(drift.length(), 0.003)}
	if not air_seen:
		fail("the jump never left the floor")
	if L.jumps - j0 != 1:
		fail("%d jumps from one press and one press in the air (a double jump)" % (L.jumps - j0))
	if landed_at < 0:
		fail("the trainee did not land within 4 s")
	if absf(L.max_rise - expect) > 0.03:
		fail("the jump rose %.3f m; the rotating-frame ballistics give %.3f m" % [L.max_rise, expect])
	await _ticks(60)
	if not h.actor.standing:
		fail("not standing again after the landing")
	# the third-person camera: never inside a collider (a ray from the follow point to the camera is clear)
	h.view_out = true
	var worst := 0.0
	var inside := 0
	var eyes := 0
	# views along the corridor (its axis and 23 deg off it, both ways) must have room; across a 0.9 m corridor the view falls back to the eyes
	var dv := h.ref_basis().inverse() * L.heading
	var yaw0 := atan2(-dv.x, -dv.z)
	var offs := [0.0, 0.4, -0.4, PI, PI + 0.4, PI - 0.4, PI / 2.0, -PI / 2.0]
	var cross := 0
	for k in 8:
		h.yaw = yaw0 + offs[k]
		h.pitch = 0.35
		await h.get_tree().process_frame
		await h.get_tree().process_frame
		var space := h.get_world_3d().direct_space_state
		var q := PhysicsRayQueryParameters3D.create(h.cam_target, h.camera.transform.origin, WfExcursion.LAYER)
		q.exclude = [h.actor.get_rid()]
		if h.cam_close:
			if k < 6:
				eyes += 1
			else:
				cross += 1
			continue
		var hit := space.intersect_ray(q)
		if not hit.is_empty():
			inside += 1
			notes["camera_hit_%d" % k] = [str(hit["collider"].name), snappedf(h.cam_target.distance_to(hit["position"]), 0.01),
				snappedf(h.cam_target.distance_to(h.camera.transform.origin), 0.01)]
		worst = maxf(worst, h.cam_clipped)
	notes["camera"] = {"views": 8, "occluded": inside, "max_pull_in_m": snappedf(worst, 0.01), "along_corridor_eye_fallback": eyes, "across_corridor_eye_fallback": cross}
	if eyes > 0:
		fail("the third-person camera had no room in %d of 6 views along the corridor" % eyes)
	if inside > 0:
		fail("the third-person camera sat behind geometry in %d of 8 views" % inside)
	# the training reset returns to the landing, standing still
	h.walk_override = fwd
	await _ticks(90)
	h.walk_override = Vector3.ZERO
	h.training_reset()
	await _ticks(30)
	if h.actor.global_position.distance_to(h.spawn_at) > 0.15 or h.resets != 1:
		fail("the training reset left the trainee %.2f m from the landing" % h.actor.global_position.distance_to(h.spawn_at))
	h.walk_override = Vector3.INF
	# LOCO-003 doors: every door opened on the way slid its visible leaf, and the leaf of a shut door sits where its collider is
	var moved := 0
	var opened := 0
	for id in h.circ_doors:
		var d: Dictionary = h.circ_doors[id]
		if d["ring"] != 0:
			continue
		if d["node"] == null:
			fail("door %s has no visible leaf" % id)
			continue
		if d["target"] >= 1.0:
			opened += 1
			if (d["node"] as Node3D).position.distance_to(d["rest"]) > 0.5 * float(d["travel"]):
				moved += 1
	notes["doors"] = {"opened": opened, "leaf_slid": moved}
	if opened != moved:
		fail("%d doors opened but only %d leaves slid open" % [opened, moved])
	# LOCO-003 ladder: Use at the foot, then forward (the real key action) climbs; back climbs down onto the deck again
	await _ticks(30)
	var u := h.use()
	if u != "ladder":
		fail("Use at the landing did not take the ladder (%s)" % u)
	await _ticks(10)
	var s0 := h.ls
	if h.move != "LINE":
		fail("taking the ladder left the trainee on the deck")
	Input.action_press("player.move_forward")
	await _ticks(240)
	Input.action_release("player.move_forward")
	notes["ladder"] = {"climbed_m": snappedf(s0 - h.ls, 0.01), "move": h.move, "clip": h.char_rig.current}
	if h.move != "LINE" or s0 - h.ls < 1.0:
		fail("forward on the ladder climbed %.2f m in 4 s (%s)" % [s0 - h.ls, h.move])
	Input.action_press("player.move_back")
	for i in 900:
		await _ticks(1)
		if h.move == "WALK":
			break
	Input.action_release("player.move_back")
	if h.move != "WALK":
		fail("back on the ladder did not return to the deck")
	await _ticks(60)
	if h.move == "WALK" and not h.actor.standing:
		fail("not standing after climbing down")
	if h.max_jump > WfExcursionCheck.MAX_JUMP_M:
		fail("the body jumped %.3f m beyond its own motion in one step (%s)" % [h.max_jump, h.max_jump_at])
	var out := {"result": "PASS" if fails.is_empty() else "FAIL", "fails": fails, "notes": notes, "max_jump_m": snappedf(h.max_jump, 0.0001),
		"states": L.log.size(), "wall_s": snappedf((Time.get_ticks_msec() - t0) / 1000.0, 0.1), "physics_frames": Engine.get_physics_frames()}
	print("WF_GODOT_LOCOMOTION " + JSON.stringify(out))
	h.get_tree().quit(0 if fails.is_empty() else 1)

var vmax := 0.0
var vmax_clip := ""
func _ticks(n: int) -> void:
	for i in n:
		if h.walk_override != Vector3.INF and h.walk_override != Vector3.ZERO:
			var id := h._door_in_reach()
			if id != "" and h.circ_doors[id]["target"] < 1.0:
				h.walk_override = Vector3.ZERO           # a shut corridor door ahead: stop, open it (E), wait for the leaf
				h.use()
				for w in int(WfExcursion.CLOSURE_S * 60.0) + 4:
					await h.get_tree().physics_frame
			h.walk_override = h.loco.heading          # keep asking along the corridor as the deck curves away
		await h.get_tree().physics_frame
		if h.loco.floor_speed() > vmax:
			vmax = h.loco.floor_speed()
			vmax_clip = h.loco.clip

func fail(s: String) -> void:
	fails.append(s)
