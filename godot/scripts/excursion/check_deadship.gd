class_name WfDeadshipCheck
extends RefCounted
## Deadship DS-1 check (-- --deadship --check-deadship [--await-player] [--shots=<dir>]): the Scrubber tutorial played through the
## trainee's own actions. The scenario's reference replay agrees with the packaged Python reference; the trainee walks ring A to the
## sector 3 ECLSS bay, inspects the unit and pages through the evidence (the model's clock stops while a page is open), isolates the unit
## (a restore with the failed fan is refused and changes nothing), walks to the sector 2 workbench through the CIRC doors and takes the
## spare, carries it back and installs it, restores the unit (CO2 then falls exactly as the closed form says), runs the stability watch
## (the same model, ship time only: the rings keep real time) and gets the debrief; Ops replays the run, and a run left alone past the
## control limit ends as an operational failure, not an injury. Prints one WF_GODOT_DEADSHIP line and quits.
## With --await-player every Use and Ops is the player's real input (the browser check presses the bound key or taps the touch button).

var h: WfExcursion
var d: WfDeadship
var pl: WfCheckPlayer
var fails: Array = []
var notes := {}
var t0 := 0

func fail(msg: String) -> void:
	fails.append(msg)
	push_warning("DS check: " + msg)

func _ticks(n: int) -> void:
	for i in n:
		await h.get_tree().physics_frame

func _close(got: float, want: float, tol: Dictionary) -> bool:
	return absf(got - want) <= float(tol["abs_kg"]) + float(tol["rel"]) * absf(want)

func _at(id: String) -> bool:
	return d.eq.in_reach(h.actor.global_position, h.walk_zone, id)

func _need(ok: bool, msg: String) -> bool:
	if not ok:
		fail(msg)
	return ok

## The touch button for an action and the prompt line both name what the scene would do now.
func _ui(action: String, label: String) -> void:
	var acts: Array = h.touch_state().get("actions", [])
	if not acts.any(func(a): return a[0] == action and a[1] == label):
		fail("touch: no '%s' button for %s (%s)" % [label, action, str(acts)])
	var pr := h._prompt_text()
	if not pr.contains(h.key(action)) or not pr.contains(label.get_slice(" · ", 1)):
		fail("prompt does not offer '%s' with the player's key: %s" % [label, pr])

func _walk_to(id: String) -> bool:
	h.walk_override = Vector3.ZERO
	var ok := await pl.walk_until(func(): return _at(id), func(): return d.eq.centre(id), float(d.eq.points[id]["reach"]), "RING_A",
		1.8 if id == "bay" else -1.0)                       # up to the bay's face, where the board is in view
	fails.append_array(pl.fails)
	pl.fails = []
	h.walk_override = Vector3.ZERO
	pl.ex.face(d.eq.centre(id) - h.actor.global_position)     # a player looks at what they are about to use
	await _ticks(10)
	return _need(ok, "the %s was not reached (%.2f m away)" % [id, h.actor.global_position.distance_to(d.eq.centre(id))])

func _shot(name: String, at: Vector3) -> void:
	await pl.shot(name, at, _front() if _at("bay") else Vector3.INF, 0.9)     # left of the sector 3 ladder

## A spot in front of the bay's face (along its thinnest axis, on the open side), where nothing stands between the eyes and the board.
func _front() -> Vector3:
	var m: MeshInstance3D = d.eq.points["bay"]["mesh"]
	var box := m.get_aabb()
	var ax := 0
	for i in 3:
		if box.size[i] < box.size[ax]:
			ax = i
	var c := d.eq.centre("bay")
	var n := Vector3.ZERO
	n[ax] = 1.0
	var tip := d.eq.to_body(m.global_transform * (box.get_center() + n * 0.5), m)
	var dir := (tip - c).normalized()
	var up: Vector3 = h.actor.up_now
	dir = (dir - up * dir.dot(up)).normalized()
	var foot := h.actor.global_position
	var a := c + dir * 1.7
	var b := c - dir * 1.7
	var pick := a if a.distance_to(foot) < b.distance_to(foot) else b
	return pick + up * (foot - pick).dot(up)

func _board() -> Vector3:
	return d.eq.to_body(d.eq.board.global_transform * d.eq.board.get_aabb().get_center())   # the text's middle

func run(host: WfExcursion) -> void:
	h = host
	t0 = Time.get_ticks_msec()
	if OS.has_feature("web"):
		print("WF_TRACE %d deadship check waits 30 physics frames" % Engine.get_physics_frames())
	await _ticks(30)
	d = h.deadship
	if d == null or not d.verified:
		fail("no Deadship training in the walk: %s" % (str(d.errors) if d != null else "not created"))
		_finish()
		return
	pl = WfCheckPlayer.new(h)
	pl.trace("deadship check started")
	notes["input"] = "the player's own binding or touch button (await-player)" if pl.await_player else "the scene's Use and Ops handlers"
	var air := d.air
	var p := air.p
	var tol: Dictionary = air.doc["tolerance"]
	var ref: Dictionary = d.doc["reference"]
	notes["reference_events"] = ref["events"].size()
	# the trainee meets the model's own result: the reference start, a running unit that removes nothing, the warning band
	var r0 := air.readout()
	notes["start"] = {"x": r0["x"], "status": r0["status"], "band": r0["band"], "hours_to_limit": r0["hours_to_control_limit"]}
	var G := float(p["occupants"]) * float(p["per_person_kg_s"])
	var m_start := air.m_kg - G * (air.t_s - d.t0_ship)          # the unit removes nothing: the mass at the trainee's start
	_need(_close(m_start, float(ref["start_m_kg"]), tol), "start CO2 %s kg, reference %s" % [str(m_start), str(ref["start_m_kg"])])
	_need(r0["status"] == "RUNNING_NOT_REMOVING" and r0["band"] == "ABOVE_TARGET" and r0["hours_to_control_limit"] != null,
		"the start is not a running unit that removes nothing, above target: %s" % str(r0))
	_need(d.current()["id"] == "recognize" and d.goal_text().contains("Step 1 of 8"), "the run does not open at step 1: %s" % d.goal_text())
	await _shot("DS_1_warning", h.actor.global_position + (-h.look_basis().z) * 4.0)
	# Ops away from any point leaves the unit alone (the walk's own Ops answers)
	var before := [air.mode, air.fan, air.spare]
	h.ops()
	_need([air.mode, air.fan, air.spare] == before, "Ops away from the bay changed the unit")
	# learning stations stay as they are; mark them seen so walking past them does not stop the check
	for st in h.learning.stations:
		h.learning.done[st["rec"]["id"]] = true
	# 1 Recognize: walk to the bay
	if not await _walk_to("bay"):
		_finish()
		return
	_need(d.index == 1, "arriving at the bay did not complete Recognize (step %d)" % d.index)
	_ui("exc.use", "Use · inspect")
	_ui("exc.ops", "Ops · isolate unit")
	# 2 Inspect, 3 Diagnose: Use opens the overview, then each evidence page; the model's clock stops while a page is open
	await pl.act("exc.use", "Use · inspect", h.use, func(): return d.page == 0)
	var t_page := air.t_s
	await _ticks(60)
	_need(air.t_s == t_page and d.eq.paused, "the model's clock ran while the inspection page was open")
	_need(d.index == 2, "inspecting did not complete Inspect (step %d)" % d.index)
	var n_ev: int = d.sc["evidence"].size()
	for k in n_ev:
		await pl.act("exc.use", "Use · next reading", h.use, func(): return d.page == k + 1)
		if k == 1:
			_need(d.text.text.contains("speed 0 %") and d.text.text.contains("commanded ON"), "the fan evidence does not show a powered, still fan: %s" % d.text.text)
	_need(d.flags.has("diagnosed") and d.index == 3, "the evidence did not complete Diagnose (step %d)" % d.index)
	await _shot("DS_2_diagnosis", _board())
	await pl.act("exc.use", "Use · close", h.use, func(): return d.page == -1)
	# 4 Isolate (a restore with the failed fan is then refused with its reason and changes nothing)
	_ui("exc.ops", "Ops · isolate unit")
	await pl.act("exc.ops", "Ops · isolate unit", h.ops, func(): return air.mode == "ISOLATED")
	_need(d.index == 4 and air.status() == "ISOLATED_FAULT", "isolating did not complete Isolate (%s, step %d)" % [air.status(), d.index])
	before = [air.mode, air.fan, air.spare]
	await pl.act("exc.ops", "Ops · restore unit", h.ops, func(): return str(d.events[-1][2]) == "refused restore")
	_need([air.mode, air.fan, air.spare] == before and str(h.refusal).contains("Replace the fan"),
		"a restore with the failed fan was not refused with its reason: %s" % h.refusal)
	await _shot("DS_3_isolated", _board())
	# 5 Navigate and retrieve: to the sector 2 workbench through the doors, take the spare, back to the bay
	var doors_before := 0
	for id in h.circ_doors:
		doors_before += 1 if h.circ_doors[id]["target"] > 0.0 else 0
	if not await _walk_to("bench"):
		_finish()
		return
	_ui("exc.use", "Use · take spare fan")
	await pl.act("exc.use", "Use · take spare fan", h.use, func(): return air.spare == "CARRIED")
	await _ticks(2)
	_need(air.spare == "CARRIED" and d.carried.visible and not d.on_bench.visible, "the spare was not taken (%s)" % air.spare)
	var doors_open := 0
	for id in h.circ_doors:
		doors_open += 1 if h.circ_doors[id]["target"] > 0.0 else 0
	notes["doors_opened_on_the_way"] = doors_open - doors_before
	if not await _walk_to("bay"):
		_finish()
		return
	_need(d.index == 5, "carrying the spare to the bay did not complete Retrieve (step %d)" % d.index)
	# 6 Repair: the model takes the spare only because the unit is isolated
	_ui("exc.use", "Use · install spare fan")
	await pl.act("exc.use", "Use · install spare fan", h.use, func(): return air.fan == "OK")
	_need(air.status() == "ISOLATED_READY" and air.spare == "INSTALLED" and not air.removing() and d.index == 6,
		"installing did not leave a repaired, still isolated unit (%s, step %d)" % [air.status(), d.index])
	# 7 Restore: removal starts again and the CO2 falls along the model's exponential
	_ui("exc.ops", "Ops · restore unit")
	await pl.act("exc.ops", "Ops · restore unit", h.ops, func(): return air.mode == "RUNNING")
	var t_b := air.t_s
	var m_b := air.m_kg
	await _ticks(300)
	var V := float(p["V_m3"])
	var k := float(p["k_m3_s"])
	var m_ss := G * V / k
	var want := m_ss + (m_b - m_ss) * exp(-k * (air.t_s - t_b) / V)
	notes["restored"] = {"ship_s": snappedf(air.t_s - t_b, 0.01), "m_kg": air.m_kg, "want_kg": want, "x": air.x()}
	_need(_close(air.m_kg, want, tol), "restored: m %s kg, closed form %s kg" % [str(air.m_kg), str(want)])
	_need(float(air.readout()["dxdt_per_h"]) < 0.0 and d.index == 7, "restoring did not start removal (step %d)" % d.index)
	await _shot("DS_4_restored", _board())
	# 8 Verify: the stability watch runs the same model in ship time only (the rings keep turning at their real rate)
	_ui("exc.ops", "Ops · stability watch")
	await pl.act("exc.ops", "Ops · stability watch", h.ops, func(): return d.watching or d.ended())
	var t_w := air.t_s
	var ring: Dictionary = h.frames[h.ring_ids[0]]
	var a0 := float(ring["angle"])
	await _ticks(60)
	var turned := absf(wrapf(float(ring["angle"]) - a0, -PI, PI))
	notes["ring_turn_in_1s_rad"] = {"got": turned, "rate": float(ring["rate"])}
	_need(absf(turned - absf(float(ring["rate"]))) < 0.02 * absf(float(ring["rate"])) + 1e-6 or not d.watching,
		"the watch's time scale reached the rings: %s rad in 1 s at %s rad/s" % [str(turned), str(ring["rate"])])
	var n := 0
	while not d.ended() and n < 60 * 60:
		await _ticks(1)
		n += 1
	var w: Dictionary = d.watch_result
	var want_w := m_ss + (m_b - m_ss) * exp(-k * (air.t_s - t_b) / V)      # removing all along since the restore
	notes["watch"] = {"result": d.result, "x_end": w.get("x_end"), "want_x_end": want_w / WfCabinAir.M_CO2 / float(p["n_mol"]),
		"ship_h": snappedf((air.t_s - t_w) / 3600.0, 1e-6), "real_s": snappedf(n / 60.0, 0.01)}
	_need(d.result == "PASS" and d.flags.has("watch_passed") and d.page == 100, "the watch did not pass: %s" % str(w))
	_need(_close(air.m_kg, want_w, tol), "watch end m %s kg, closed form %s kg" % [str(air.m_kg), str(want_w)])
	_need(absf(air.t_s - d.watch_t0 - float(d.sc["watch"]["ship_h"]) * 3600.0) < 1e-6, "the watch ran %s ship s" % str(air.t_s - d.watch_t0))
	_need(d.text.text.contains("What failed") and d.text.text.contains("Why it is stable"), "the debrief is missing: %s" % d.text.text)
	_need(absf(air.ledger_error()) <= float(tol["abs_kg"]), "ledger open by %s kg" % str(air.ledger_error()))
	await _shot("DS_5_stable", _board())
	notes["run"] = d.record()
	# replay: Ops at the bay starts the training again from the same model state
	await pl.act("exc.ops", "Ops · replay training", h.ops, func(): return d.runs == 2)
	_need(d.index <= 1 and d.flags.is_empty() and d.result == ""   # at the bay, Recognize completes on the next frame
		 and _close(air.m_kg - G * (air.t_s - d.t0_ship), float(ref["start_m_kg"]), tol) and air.spare == "BENCH" and d.on_bench.visible,
		"replay did not restart the training from its start (%s)" % str(d.record()))
	# an unrepaired run left alone ends as an operational failure (the model's own time, skipped here instead of waited for)
	if not pl.await_player:
		air.step((float(air.readout()["hours_to_control_limit"]) + 0.05) * 3600.0)
		await _ticks(3)
		_need(d.result == "FAIL" and d.page == 100 and d.text.text.contains("not that the crew is harmed") and d.text.text.contains("degraded-habitability"),
			"passing the control limit did not end the run as an operational failure: %s" % d.text.text)
		notes["failure"] = {"result": d.result, "x": air.x(), "band": air.readout()["band"]}
	_finish()

func _finish() -> void:
	var out := {"result": "PASS" if fails.is_empty() else "FAIL", "fails": fails, "notes": notes,
		"wall_s": snappedf((Time.get_ticks_msec() - t0) / 1000.0, 0.1), "physics_frames": Engine.get_physics_frames()}
	print("WF_GODOT_DEADSHIP " + JSON.stringify(out))
	h.get_tree().quit(0 if fails.is_empty() else 1)
