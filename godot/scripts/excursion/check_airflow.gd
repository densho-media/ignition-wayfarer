class_name WfAirflowCheck
extends RefCounted
## SYS-002 check (-- --airflow --check-airflow; the browser's --await-player): ring A's air by compartment in the walk, through the
## player's own requests. The runtime model reproduces its packaged reference and a coarse step gives the same state; the model's door
## edges always equal the walk's door leaves (off the seat = open); Ops away from the bay does nothing; at the bay Ops switches the
## ventilation off and every compartment not joined by an open door is then truly isolated (a sealed, empty corridor's CO2 does not change
## by one bit); Use closes a door and the model's edge closes when the leaf seats (it is open while the leaf moves), a refused close (the
## doorway occupied) changes nothing; reopening joins two compartments gradually; Ops switches the ventilation back on and the ring is one
## group again. The ledger closes throughout. Prints one WF_GODOT_AIRFLOW line and quits.

var h: WfExcursion
var af: WfAirflow
var fails: Array = []
var notes := {}
var t0 := 0
var pl: WfCheckPlayer = null

func fail(msg: String) -> void:
	fails.append(msg)
	push_warning("AIRFLOW check: " + msg)

func _ticks(n: int) -> void:
	for i in n:
		await h.get_tree().physics_frame

func _tol(want: float) -> float:
	var t: Dictionary = af.ring.doc["tolerance"]
	return float(t["abs_kg"]) + float(t["rel"]) * absf(want)

## The model's door edges equal the walk's leaves (the one source of door state).
func _doors_agree(where: String) -> void:
	for e in af.ring.edges:
		if str(e["kind"]) != "door":
			continue
		var walk := float(h.circ_doors[e["id"]]["value"]) > 0.0
		if bool(af.ring.open[e["id"]]) != walk:
			fail("%s: model edge %s is %s, the walk's leaf %s" % [where, e["id"], af.ring.open[e["id"]], h.circ_doors[e["id"]]["value"]])

func _board_says(what: String) -> void:
	if not af.board.text.contains(what):
		fail("the bay's board does not say '%s': %s" % [what, af.board.text])

func _ui_says(label: String) -> void:
	var acts: Array = h.touch_state().get("actions", [])
	if not acts.any(func(a): return a[0] == "exc.ops" and a[1] == label):
		fail("touch: no '%s' button for exc.ops (%s)" % [label, str(acts)])
	var pr := h._prompt_text()
	if not pr.contains(h.key("exc.ops")) or not pr.contains(label.trim_prefix("Ops · ")):
		fail("prompt does not offer '%s' with the player's key: %s" % [label, pr])

func _shot(name: String) -> void:
	await pl.shot(name, pl.board_mid(af), pl.front_of(af) if af.in_reach(h.actor.global_position, h.walk_zone) else Vector3.INF, 0.9)

func run(host: WfExcursion) -> void:
	h = host
	t0 = Time.get_ticks_msec()
	await _ticks(30)
	af = h.equipment as WfAirflow
	if af == null or af.ring == null:
		fail("no air model in the walk (wf_ring_air.json missing from the package?)")
		_finish()
		return
	if not af.ring.verified:
		fail("the runtime air model does not reproduce its reference: %s" % str(af.ring.errors))
		_finish()
		return
	if af.mesh == null:
		fail("the ECLSS bay node is not in the package")
		_finish()
		return
	notes["reference_checkpoints"] = af.ring.doc["proof"]["checkpoints"].size()
	_determinism()
	var air := af.ring
	if air.vent != "ON" or af.open_doors() != 0 or air.components().size() != 1:
		fail("start: want ventilation ON, every door closed, one group; got %s, %d open, %d groups" % [air.vent, af.open_doors(), air.components().size()])
	_doors_agree("start")
	h.ops()                                                       # away from the bay: nothing
	await _ticks(2)
	if air.vent != "ON" or af.operations != 0:
		fail("Ops away from the bay switched the ventilation")
	pl = WfCheckPlayer.new(h)
	var reached := await pl.walk_until(func(): return af.in_reach(h.actor.global_position, h.walk_zone), func(): return af.centre(),
		float(af.binding["reach_m"]), "RING_A", 1.8)
	fails.append_array(pl.fails)
	pl.fails = []
	if not reached:
		fail("the ECLSS bay was not reached")
		_finish()
		return
	h.walk_override = Vector3.ZERO
	await _ticks(100)                                              # the doors opened on the way finish moving
	_doors_agree("at the bay")
	var opened: Array = []
	for e in air.edges:
		if str(e["kind"]) == "door" and bool(air.open[e["id"]]):
			opened.append(e["id"])
	notes["doors_opened_on_the_way"] = opened
	notes["input"] = "the player's own binding or touch button (await-player)" if pl.await_player else "the scene's Use and Ops handlers"
	_board_says("Ventilation ON")
	await _shot("AIR_1_connected")
	# ventilation off: only the open doors join compartments
	_ui_says("Ops · ventilation off")
	await pl.act("exc.ops", "Ops · ventilation off", h.ops, func(): return air.vent == "OFF")
	if air.vent != "OFF":
		fail("Ops at the bay did not switch the ventilation off")
	var groups := air.components()
	notes["groups_vent_off"] = groups.size()
	if groups.size() != 9 - opened.size():
		fail("ventilation off with %d doors open: %d groups, want %d" % [opened.size(), groups.size(), 9 - opened.size()])
	var sealed := -1                                               # a corridor half with no occupant, no removal and both doors shut
	for g in groups:
		if g.size() == 1 and str(air.ids[g[0]]).begins_with("AC"):
			sealed = int(g[0])
	if sealed < 0:
		fail("no sealed corridor compartment to watch")
	var m_sealed := float(air.m[sealed]) if sealed >= 0 else 0.0
	var x_before := []
	for i in air.N:
		x_before.append(air.x(i))
	await _ticks(600)                                              # 10 s real, 20 ship minutes
	if sealed >= 0 and float(air.m[sealed]) != m_sealed:
		fail("isolated %s exchanged CO2: %s -> %s kg" % [air.ids[sealed], str(m_sealed), str(air.m[sealed])])
	var r := air.readout()
	for i in air.N:
		var q: Dictionary = r["nodes"][i]
		if bool(q["isolated"]) and int(q["occupants"]) > 0 and not bool(q["removal_reaches"]) and air.x(i) <= float(x_before[i]):
			fail("isolated occupied %s did not rise (%s -> %s)" % [q["id"], str(x_before[i]), str(air.x(i))])
	_board_says("Ventilation OFF")
	_board_says("isolated")
	notes["vent_off"] = af.record()["nodes"]
	await _shot("AIR_2_isolated")
	# Use closes the nearest open door: the edge stays open while the leaf moves and closes when it seats
	var door := ""
	var bd := INF
	for id in opened:
		var dd := h.actor.global_position.distance_to((h.circ_doors[id]["collider"] as Node3D).global_position)
		if dd < bd:
			bd = dd
			door = id
	if door == "":
		fail("no open door to close")
		_finish()
		return
	notes["door"] = door
	await _to_door(door, 1.0)
	var n_hist := air.history.size()
	await pl.act("exc.use", "Use · close door", h.use, func(): return float(h.circ_doors[door]["target"]) == 0.0)
	await _ticks(1)
	if float(h.circ_doors[door]["value"]) > 0.0 and not bool(air.open[door]):
		fail("%s: the model closed the edge while the leaf is still moving" % door)
	await _ticks(120)
	_doors_agree("after closing " + door)
	if bool(air.open[door]):
		fail("%s closed in the walk but its edge is still open" % door)
	if air.components().size() != groups.size() + 1:
		fail("closing %s: %d groups, want %d" % [door, air.components().size(), groups.size() + 1])
	# reopen it: two compartments join, gradually
	var e: Dictionary = {}
	for ed in air.edges:
		if ed["id"] == door:
			e = ed
	var gap0 := absf(air.x(int(e["i"])) - air.x(int(e["j"])))
	await pl.act("exc.use", "Use · open door", h.use, func(): return float(h.circ_doors[door]["target"]) == 1.0)
	await _ticks(2)
	if not bool(air.open[door]):
		fail("%s opening in the walk but its edge is closed" % door)
	var gap1 := absf(air.x(int(e["i"])) - air.x(int(e["j"])))
	await _ticks(300)
	var gap2 := absf(air.x(int(e["i"])) - air.x(int(e["j"])))
	notes["reopen_gap"] = [gap0, gap1, gap2]
	if not (gap1 > 0.5 * gap0 and gap2 < gap1):
		fail("reopening %s: the gap %s -> %s -> %s is not a gradual approach" % [door, str(gap0), str(gap1), str(gap2)])
	# a refused close (standing in the doorway) changes neither the door nor the model
	if not pl.await_player:
		await pl.ex._walk_to((h.circ_doors[door]["collider"] as Node3D).global_position, 0.25, 20.0, 0)
		pl.ex.fails = []
		h.walk_override = Vector3.ZERO
		await _ticks(10)
		var hn := air.history.size()
		var res := h.use()
		await _ticks(5)
		notes["refused_close"] = {"result": res, "said": h.refusal}
		if float(h.circ_doors[door]["target"]) != 1.0 or not bool(air.open[door]) or air.history.size() != hn:
			fail("a refused close changed the door or the model (%s)" % res)
		await _to_door(door, 1.0)
	n_hist = air.history.size() - n_hist
	notes["model_changes_from_doors"] = n_hist
	# ventilation back on: one group again
	await _to_bay()
	_ui_says("Ops · ventilation on")
	await pl.act("exc.ops", "Ops · ventilation on", h.ops, func(): return air.vent == "ON")
	if air.components().size() != 1:
		fail("ventilation on: %d groups, want 1" % air.components().size())
	await _ticks(120)
	_board_says("1 group")
	await _shot("AIR_3_reconnected")
	if absf(air.ledger_error()) > _tol(air.m0 + air.generated + air.removed):
		fail("ledger open by %s kg" % str(air.ledger_error()))
	for i in air.N:
		if float(air.m[i]) < 0.0:
			fail("negative CO2 in %s" % air.ids[i])
	fails.append_array(pl.fails)
	notes["record"] = af.record()
	_finish()

## Stand on the bay's side of a door, about `back` metres from its leaf, facing it.
func _to_door(id: String, back: float) -> void:
	var col: Node3D = h.circ_doors[id]["collider"]
	var c := col.global_position
	var bay := af.centre()
	var away := (bay - c)
	away -= h.actor.up_now * away.dot(h.actor.up_now)
	var normal := col.global_transform.basis.z.normalized()
	var side := signf(normal.dot(away)) if absf(normal.dot(away)) > 1e-6 else 1.0
	await pl.ex._walk_to(c + normal * side * back, 0.3, 30.0, 0)
	pl.ex.fails = []
	h.walk_override = Vector3.ZERO
	pl.ex.face(c - (h.actor.global_position + h.ref_basis().y * 1.6))
	await _ticks(10)

func _to_bay() -> void:
	await pl.ex._walk_to(af.centre(), 1.8, 30.0, 0)
	pl.ex.fails = []
	h.walk_override = Vector3.ZERO
	await _ticks(10)

## Two fresh copies, the same changes at the same ship times, stepped at 10 s and at 600 s: the same state within the packaged
## tolerance (the step is exact); a repeated run is identical.
func _determinism() -> void:
	var runs := []
	for dt in [10.0, 600.0, 10.0]:
		var a := WfRingAir.load_package()
		var n := int(round(3600.0 / dt))
		for i in 4 * n:
			if i == n:
				a.set_vent(false)
			if i == 2 * n:
				a.set_edge("CIRC.A2N", true)
			a.step(dt)
		runs.append(a.m.duplicate())
	notes["determinism_A2_kg"] = [runs[0][1], runs[1][1]]
	for k in runs[0].size():
		if absf(float(runs[1][k]) - float(runs[0][k])) > _tol(float(runs[0][k])):
			fail("a 600 s step gives %s kg in %d, 10 s gives %s kg" % [str(runs[1][k]), k, str(runs[0][k])])
	if runs[2] != runs[0]:
		fail("a repeated run differs")

func _finish() -> void:
	var out := {"result": "PASS" if fails.is_empty() else "FAIL", "fails": fails, "notes": notes,
		"wall_s": snappedf((Time.get_ticks_msec() - t0) / 1000.0, 0.1), "physics_frames": Engine.get_physics_frames()}
	print("WF_GODOT_AIRFLOW " + JSON.stringify(out))
	h.get_tree().quit(0 if fails.is_empty() else 1)
