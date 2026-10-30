class_name WfExcursionCheck
extends RefCounted
## EXC-001 headless check (-- --check-excursion): the whole excursion twice, ring A then ring B, through the same actions a player has (the
## line command, the walk direction, use() and ops()), never by moving the body directly. It asserts the route's physical promises: a shut
## closure stops the body, a corridor door blocks until opened, the body never jumps at a frame change or falls through a floor, both rings
## are walked all the way round, and the station is reached again without a reset. Prints one WF_GODOT_EXCURSION line and quits.

var h: WfExcursion
var fails: Array = []
var notes := {}
var t0 := 0

const MAX_JUMP_M := 0.05              # a frame change or a line handover moves the body no more than this beyond its velocity

var shots := ""                       # -- --shots=<dir>: a still at each milestone (needs a display, e.g. xvfb-run)

func run(host: WfExcursion) -> void:
	h = host
	t0 = Time.get_ticks_msec()
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--shots="):
			shots = a.trim_prefix("--shots=")
			DirAccess.make_dir_recursive_absolute(shots)
			h.get_viewport().disable_3d = true      # 3D is drawn only for the stills (software GL draws the whole ship slowly)
	await _ticks(10)
	await _excursion(0)
	await _excursion(1)
	if h.learning == null or h.learning.stations.size() != h.learning.doc.get("stations", []).size() or h.learning.stations.is_empty():
		fail("learning stations: %d of %d found in the package" % [0 if h.learning == null else h.learning.stations.size(),
			0 if h.learning == null else h.learning.doc.get("stations", []).size()])
	elif h.learning.done.size() != h.learning.stations.size():
		fail("learning stations: %d of %d reached and completed on the ring A circuit" % [h.learning.done.size(), h.learning.stations.size()])
	if h.max_jump > MAX_JUMP_M:
		fail("the body jumped %.3f m beyond its own motion in one step (%s)" % [h.max_jump, h.max_jump_at])
	var out := {"result": "PASS" if fails.is_empty() else "FAIL", "fails": fails, "notes": notes, "max_jump_m": snappedf(h.max_jump, 0.0001),
		"max_jump_at": h.max_jump_at,
		"wall_s": snappedf((Time.get_ticks_msec() - t0) / 1000.0, 0.1), "physics_frames": Engine.get_physics_frames()}
	print("WF_GODOT_EXCURSION " + JSON.stringify(out))
	h.get_tree().quit(0 if fails.is_empty() else 1)

func _ticks(n: int) -> void:
	for i in n:
		await h.get_tree().physics_frame

## A still: looking along the line (dir +1 ahead, -1 back) on a body line, or at yaw/pitch in the reference frame while walking.
func shot(name: String, yaw := 0.0, pitch := 0.0, dir := 1.0) -> void:
	if shots == "" or DisplayServer.get_name() == "headless":
		return
	var keep := [h.yaw, h.pitch]
	if h.move == "LINE":
		face(h.line.tangent(h.ls) * dir)
	else:
		h.yaw = yaw
		h.pitch = pitch
	h.get_viewport().disable_3d = false
	for i in 4:
		await RenderingServer.frame_post_draw
	h.get_viewport().get_texture().get_image().save_png(shots.path_join(name + ".png"))
	h.get_viewport().disable_3d = true
	h.yaw = keep[0]
	h.pitch = keep[1]

## A progress line (the check runs minutes of physics with no other output).
func step(msg: String) -> void:
	printerr("EXC step %s  wall %.1f s  frame %d" % [msg, (Time.get_ticks_msec() - t0) / 1000.0, Engine.get_physics_frames()])

func fail(msg: String) -> void:
	fails.append(msg)
	push_warning("EXC check: " + msg)

## Move along the current line to s (the hands' command toward it), until at rest there; false on timeout or a stop elsewhere. The view
## turns along the travel, as a player's would (use() picks the hatch the trainee faces).
func line_to(target: float, limit_s := 240.0, tol := 0.02) -> bool:
	var n := 0
	var dir := signf(target - h.ls) if absf(target - h.ls) > tol else 0.0      # already there: the view stays
	var ok := false
	while n < int(limit_s * 60.0):
		var d := target - h.ls
		h.cmd_override = signf(d) if absf(d) > tol else 0.0
		await _ticks(1)
		n += 1
		if n % 600 == 0 and OS.has_environment("EXC_DEBUG"):
			printerr("line_to %.3f: s %.3f v %.4f line %s move %s cmd %.1f" % [target, h.ls, h.lv, h.line.id, h.move, h.cmd_override])
		if (absf(h.ls - target) <= tol and absf(h.lv) < 1e-9) or h.move != "LINE":
			ok = true
			break
	h.cmd_override = 0.0
	if dir != 0.0 and h.move == "LINE":
		face(h.line.tangent(h.ls) * dir)
	return ok

## Turn the view to look along v (world direction).
func face(v: Vector3) -> void:
	var d := h.ref_basis().inverse() * v.normalized()
	h.yaw = atan2(-d.x, -d.z)
	h.pitch = asin(clampf(d.y, -1.0, 1.0))

func wait_until(cond: Callable, limit_s: float, what: String) -> bool:
	var n := 0
	while not cond.call():
		await _ticks(1)
		n += 1
		if n > int(limit_s * 60.0):
			fail("timeout: " + what)
			return false
	return true

func use_expect(prefix: String, what: String) -> bool:
	var r := h.use()
	if not r.begins_with(prefix):
		fail("%s: use() gave '%s' (want %s) at %s s=%.3f" % [what, r, prefix, h.line.id if h.move == "LINE" else h.walk_zone, h.ls])
		return false
	return true

func _excursion(k: int) -> void:
	var R := "AB"[k]
	var B: WfLine = h.lines["BOARD"]
	var gates := {}
	for g in B.gates:
		gates[g["id"]] = g["s"]
	await shot("%s_01_station_start" % R)
	# 1. the station (its hatch open while docked); Wayfarer's shut outer hatch stops the body: no push-off into the coast across it
	await wait_until(func(): return h.hatch["STATION_HATCH"]["value"] >= 1.0, 10.0, "station hatch open while docked")
	await line_to(float(gates["OUTER_HATCH"][0]) + 0.5, 60.0)
	if h.ls > float(gates["OUTER_HATCH"][0]) + 1e-6:
		fail("ring %s: the body passed the shut outer hatch (s %.3f > %.3f)" % [R, h.ls, gates["OUTER_HATCH"][0]])
	use_expect("open OUTER_HATCH", "outer hatch")
	await wait_until(func(): return h.hatch["OUTER_HATCH"]["value"] >= 1.0 and h.hatch["STATION_HATCH"]["value"] >= 1.0, 10.0, "hatches open")
	step(R + " 1 outer hatch")
	# 2. the airlock: coast in, the inner hatch refuses while the outer is open, close the outer, open the inner
	var stop := _chamber_stop(B)
	await line_to(stop)
	await shot("%s_02_airlock" % R)
	if h.hatch["INNER_HATCH"]["target"] > 0.0:
		fail("inner hatch open on arrival")
	var r := h._toggle_hatch("INNER_HATCH")
	if r != "":
		fail("airlock: the inner hatch opened with the outer one open")
	use_expect("close OUTER_HATCH", "close outer")
	await wait_until(func(): return h.hatch["OUTER_HATCH"]["value"] <= 0.0, 10.0, "outer shut")
	use_expect("open INNER_HATCH", "open inner")
	await wait_until(func(): return h.hatch["INNER_HATCH"]["value"] >= 1.0, 10.0, "inner open")
	step(R + " 2 airlock")
	# 3. into the trunk; undock and spin up (the controller holds the ramp until the body is still)
	await line_to(18.0)
	await shot("%s_03_trunk" % R)
	if h.ops() != "COAST":
		fail("ring %s: undock request refused" % R)
	await wait_until(func(): return h.ctl.mode == "COAST" and not h.ctl.busy(), 120.0, "COAST")
	notes["station_offset_%s" % R] = h.station_offset
	step(R + " 3 COAST")
	# 4. to the ring's access: ring B by the branch at its port, ring A on aft
	if k == 1:
		await line_to(float(B.marks["RING_B"]), 120.0)
		use_expect("branch RING_B", "ring B branch")
		await wait_until(func(): return h.line.id == "ACCESS_B", 20.0, "into the ring B branch")
	else:
		await line_to(B.length(), 120.0, 0.001)
		h.cmd_override = 1.0
		await _ticks(3)
		h.cmd_override = 0.0
	if h.line.id != "ACCESS_" + R:
		fail("ring %s: not on its access line (%s)" % [R, h.line.id])
		return
	var L: WfLine = h.line
	# the port gate stops the body while shut
	await line_to(float(L.marks["port"]) + 0.3, 60.0)
	if h.ls > float(L.marks["port"]) + 1e-6:
		fail("ring %s: the body passed the shut spine-port gate" % R)
	use_expect("open port gate", "port gate")
	await wait_until(func(): return h.closures[h._port_gate(k)]["value"] >= 1.0, 10.0, "port gate open")
	await line_to(float(L.marks["hold"]), 120.0, 1e-6)
	await shot("%s_04_drum_restraint" % R)
	use_expect("cycle drum to RING", "drum to ring")
	await wait_until(func(): return h.drum[k]["mode"] == "SYNCED", 60.0, "drum synced " + R)
	step(R + " 4 drum synced")
	# 5. down the crew tube to the deck
	await line_to(L.length(), 240.0)
	await wait_until(func(): return h.move == "WALK", 10.0, "standing in ring " + R)
	await _ticks(90)
	if not h.actor.standing:
		fail("ring %s: not standing on the landing deck" % R)
	notes["deck_g_%s" % R] = snappedf(h.actor.field_now.length() / 9.80665, 0.0001)
	await shot("%s_05_landing" % R)
	step(R + " 5 standing")
	# 6. out of the landing well onto the passage, the whole circuit through every sector and corridor, opening each door (the first one
	# is pushed against while shut), and back into the well
	var c: Dictionary = h.stages["circuit"]["RING_" + R]
	var exit := WfLine.g(c["landing_m"][1])
	await _walk_to(exit, 0.3, 60.0, k)
	await _walk_circuit(k)
	step(R + " 6 circuit walked")
	await _walk_to(exit, 0.3, 60.0, k)
	# 7. back to the ladder, up the tube, the drum back to the spine
	await _walk_to(L.p[-1], 0.4, 120.0, k)
	use_expect("ladder", "ladder " + R)
	await line_to(float(L.marks["hold"]), 300.0, 1e-6)
	await shot("%s_08_drum_back" % R, 0.0, 0.0, -1.0)
	use_expect("cycle drum to STATIONARY", "drum to spine")
	await wait_until(func(): return h.drum[k]["mode"] == "DESPUN", 60.0, "drum despun " + R)
	await line_to(0.0, 120.0, 0.001)
	h.cmd_override = -1.0
	await _ticks(3)
	h.cmd_override = 0.0
	if h.line.id != "BOARD":
		fail("ring %s: not back on the boarding line" % R)
		return
	step(R + " 7 back on BOARD")
	# 8. spin down, lock, dock; back through the airlock and the station hatch to the start
	await line_to(18.0)
	if h.ops() != "DOCKED":
		fail("ring %s: dock request refused" % R)
	await wait_until(func(): return h.ctl.mode == "DOCKED" and not h.ctl.busy(), 180.0, "DOCKED")
	await wait_until(func(): return h.station_offset <= 0.0, 10.0, "station docked")
	for f in h.frames:
		if f in h.ring_ids and absf(wrapf(h.frames[f]["angle"], -PI, PI)) > 1e-6:
			fail("ring %s locked away from its index (%.4f rad)" % [f, h.frames[f]["angle"]])
	await line_to(stop + 0.0)
	if h.hatch["INNER_HATCH"]["value"] < 1.0:
		fail("inner hatch not open on the way back")
	await line_to(stop)
	use_expect("close INNER_HATCH", "close inner")
	await wait_until(func(): return h.hatch["INNER_HATCH"]["value"] <= 0.0, 10.0, "inner shut")
	use_expect("open OUTER_HATCH", "open outer back")
	await wait_until(func(): return h.hatch["OUTER_HATCH"]["value"] >= 1.0 and h.hatch["STATION_HATCH"]["value"] >= 1.0, 10.0, "hatches open back")
	await line_to(0.0, 120.0)
	await shot("%s_09_station_back" % R, 0.0, 0.0, -1.0)
	if not h.progress["RING_" + R]["returned"]:
		fail("ring %s: excursion not recorded as returned" % R)
	# leave the boarding hatches shut for the next run (from the tunnel, both within the panel's reach)
	await line_to(4.5)
	use_expect("close OUTER_HATCH", "close the outer hatch for the next run")
	await wait_until(func(): return h.hatch["OUTER_HATCH"]["value"] <= 0.0, 10.0, "outer hatch shut")
	await line_to(0.0)
	step(R + " 8 station")
	notes["ring_%s" % R] = {"circuit": h.progress["RING_" + R]["circuit"], "returned": h.progress["RING_" + R]["returned"], "t_s": snappedf((Time.get_ticks_msec() - t0) / 1000.0, 0.1)}

func _chamber_stop(B: WfLine) -> float:
	for i in B.phase.size():
		if B.phase[i] == "chamber_rail":
			return float(B.s[i])
	return 9.1

## Walk to a point in the ring (index coordinates) with the walk command; opens a shut circulation door in the way.
func _walk_to(target: Vector3, tol: float, limit_s: float, k: int) -> bool:
	var n := 0
	var best := INF
	var since := 0
	while n < int(limit_s * 60.0):
		var p := h.actor.global_position
		var up: Vector3 = h.actor.up_now
		var d := target - p
		d -= up * d.dot(up)
		if d.length() < tol:
			h.walk_override = Vector3.ZERO
			return true
		h.walk_override = d.normalized()
		await _doors_ahead(k)
		await _learn_here()
		await _ticks(1)
		n += 1
		if d.length() < best - 0.05:
			best = d.length()
			since = 0
		else:
			since += 1
		if since > 60 * 12:
			fail("ring %s: stuck walking at %s toward %s" % ["AB"[k], h._vec(p), h._vec(target)])
			h.walk_override = Vector3.ZERO
			return false
	h.walk_override = Vector3.ZERO
	return false

## UJ-013: at each learning station first reached, Use steps WHAT, WHY, SHOW ME and closes, and the station counts as learned.
func _learn_here() -> void:
	var i := h._learning_in_reach()
	if i < 0 or h.learning.done.has(h.learning.stations[i]["rec"]["id"]) or h._walk_target() != "":
		return
	h.walk_override = Vector3.ZERO
	var got := []
	var id := str(h.learning.stations[i]["rec"]["id"])
	for k in 4:
		got.append(h.use())
		await _ticks(2)
		if k < 3:
			await shot("A_learn_%s_%d" % [id, k], h.yaw, h.pitch)     # the panel at WHAT, WHY and SHOW ME (with --shots)
	var want := ["learn WHAT", "learn WHY", "learn SHOW ME", "learn "]
	notes["learn_" + id] = got
	if got != want or h.learning.open != -1 or h.view_out:
		fail("learning station %s: Use gave %s, want %s, then closed" % [h.learning.stations[i]["rec"]["id"], got, want])

var pushed := false
func _doors_ahead(k: int) -> void:
	var id := h._door_in_reach()
	if id == "" or h.circ_doors[id]["target"] >= 1.0:
		return
	var col: Node3D = h.circ_doors[id]["collider"]
	if not pushed:
		# the first shut door: walk into it for 2 s; the body must stay on its side of the leaf
		pushed = true
		var side0 := signf((col.global_transform.affine_inverse() * h.actor.global_position).z)
		var d := col.global_position - h.actor.global_position
		d -= h.actor.up_now * d.dot(h.actor.up_now)
		h.walk_override = d.normalized()
		await _ticks(120)
		var side1 := signf((col.global_transform.affine_inverse() * h.actor.global_position).z)
		notes["door_block"] = {"door": id, "kept_side": side0 == side1}
		if side0 != side1:
			fail("door %s: the body passed through the shut door" % id)
	h.use()
	await _ticks(int(WfExcursion.CLOSURE_S * 60.0) + 2)

func _walk_circuit(k: int) -> void:
	var c: Dictionary = h.stages["circuit"]["RING_" + "AB"[k]]
	var pts: Array = []
	for q in c["circuit_m"]:
		pts.append(WfLine.g(q))
	# start at the circuit point nearest the body, walk the loop in order back to it
	var i0 := 0
	for i in pts.size():
		if (pts[i] as Vector3).distance_to(h.actor.global_position) < (pts[i0] as Vector3).distance_to(h.actor.global_position):
			i0 = i
	for j in pts.size() + 1:
		var q: Vector3 = pts[(i0 + j) % pts.size()]
		if not await _walk_to(q, 0.45, 90.0, k):
			return
		if j == 8:
			await _walk_shot("%s_06_corridor" % "AB"[k], q, pts[(i0 + j + 1) % pts.size()])
		if j == pts.size() / 3:
			await _walk_shot("%s_07_far_side" % "AB"[k], q, pts[(i0 + j + 1) % pts.size()])
	notes["circuit_%s_bins" % "AB"[k]] = h.progress["RING_" + "AB"[k]]["bins"].count(1)
	if not h.progress["RING_" + "AB"[k]]["circuit"]:
		fail("ring %s: circuit not complete (%d / %d bins)" % ["AB"[k], h.progress["RING_" + "AB"[k]]["bins"].count(1), WfExcursion.BINS])

## A still looking along the walk (yaw toward the next waypoint in the body's reference frame).
func _walk_shot(name: String, q: Vector3, nxt: Vector3) -> void:
	if shots == "":
		return
	h.walk_override = Vector3.ZERO
	await _ticks(20)
	var b := h.ref_basis()
	var d := b.inverse() * (nxt - q)
	await shot(name, atan2(-d.x, -d.z), -0.05)
