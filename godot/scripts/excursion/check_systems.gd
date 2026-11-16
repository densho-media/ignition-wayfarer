class_name WfSystemsCheck
extends RefCounted
## SYS-001 headless check (-- --systems --check-systems): the Phase 0 systems proof through the player's own requests. The runtime CO2
## model reproduces its packaged reference within the packaged tolerance; Ops away from the bay changes nothing; the trainee walks the
## ring A circuit (doors opened by Use, as a player would) to the sector 3 ECLSS bay; Ops there isolates the unit and the model's CO2 then
## rises exactly as the closed-form solution says, the board and the touch button follow the state, Ops again restores it and the CO2
## falls back along the exponential; the ledger closes and a coarse step gives the same state. Prints one WF_GODOT_SYSTEMS line and quits.

var h: WfExcursion
var fails: Array = []
var notes := {}
var t0 := 0
var pl: WfCheckPlayer = null              # walking, the player's actions (--await-player) and stills (--shots=<dir>, or the browser's)

## A still looking at the bay's board (no-op headless without --shots).
func _shot(name: String) -> void:
	await pl.shot(name, h.equipment.to_body(h.equipment.board.global_position))

func _increasing(v: Array) -> bool:
	for i in range(1, v.size()):
		if float(v[i]) <= float(v[i - 1]):
			return false
	return true

func fail(msg: String) -> void:
	fails.append(msg)
	push_warning("SYS check: " + msg)

func _ticks(n: int) -> void:
	for i in n:
		await h.get_tree().physics_frame

func _close(got: float, want: float, tol: Dictionary) -> bool:
	return absf(got - want) <= float(tol["abs_kg"]) + float(tol["rel"]) * absf(want)

func run(host: WfExcursion) -> void:
	h = host
	t0 = Time.get_ticks_msec()
	await _ticks(30)
	var eq := h.equipment
	if eq == null or eq.air == null:
		fail("no systems proof in the walk (wf_cabin_air.json missing from the package?)")
		_finish()
		return
	if not eq.air.verified:
		fail("the runtime model does not reproduce its reference: %s" % str(eq.air.errors))
		_finish()
		return
	if eq.mesh == null:
		fail("the ECLSS bay node %s is not in the package" % eq.binding["node"])
		_finish()
		return
	notes["reference_checkpoints"] = eq.air.doc["proof"]["checkpoints"].size()
	var tol: Dictionary = eq.air.doc["tolerance"]
	_determinism(tol)
	# Ops away from the bay operates nothing
	var s0 := eq.air.mode
	h.ops()
	if eq.air.mode != s0 or eq.operations != 0:
		fail("Ops away from the bay changed the unit (%s -> %s)" % [s0, eq.air.mode])
	# walk the ring A circuit, as a player, until the bay is in reach
	pl = WfCheckPlayer.new(h)
	var reached := await pl.walk_until(func(): return eq.in_reach(h.actor.global_position, h.walk_zone), func(): return eq.centre(),
		float(eq.binding["reach_m"]))
	fails.append_array(pl.fails)
	pl.fails = []
	notes["walked_m_bins"] = h.progress["RING_A"]["bins"].count(1)
	if not reached:
		fail("the ECLSS bay was not reached on the ring A circuit (%.2f m away)" % h.actor.global_position.distance_to(eq.centre()))
		_finish()
		return
	notes["reach_distance_m"] = snappedf(h.actor.global_position.distance_to(eq.centre()), 0.01)
	notes["input"] = "the player's own binding or touch button (await-player)" if pl.await_player else "the scene's Ops handler"
	h.walk_override = Vector3.ZERO
	await _ticks(10)
	await _shot("SYS_1_running")
	_ui_says("Ops · isolate CO2 unit")
	# isolate: the model's state changes and CO2 rises linearly at the generation rate (from the steady state the running unit held)
	var p: Dictionary = eq.air.p
	var G := float(p["occupants"]) * float(p["per_person_kg_s"])
	var m_a := eq.air.m_kg
	await pl.act("exc.ops", "Ops · isolate CO2 unit", h.ops, func(): return eq.air.mode == "ISOLATED")
	var t_a: float = eq.air.history[-1][0] if not eq.air.history.is_empty() else eq.air.t_s
	if eq.air.mode != "ISOLATED":
		fail("Ops at the bay did not isolate the unit (state %s)" % eq.air.mode)
	await _ticks(2)
	if not eq.board.text.contains("ISOLATED"):
		fail("the bay's board does not show ISOLATED: %s" % eq.board.text)
	_ui_says("Ops · restore CO2 unit")
	var x_seen := [eq.air.x()]
	for i in 6:
		await _ticks(100)
		x_seen.append(eq.air.x())
	notes["board_x_rising"] = x_seen
	if not _increasing(x_seen):
		fail("isolated: the CO2 the board shows does not rise: %s" % str(x_seen))
	await _shot("SYS_2_isolated")
	var want_iso := m_a + G * (eq.air.t_s - t_a)
	notes["isolated"] = {"ship_s": snappedf(eq.air.t_s - t_a, 0.01), "x_from": eq.air.readout()["x"], "m_kg": eq.air.m_kg, "want_kg": want_iso}
	if not _close(eq.air.m_kg, want_iso, tol):
		fail("isolated: m %s kg, closed form %s kg" % [str(eq.air.m_kg), str(want_iso)])
	if float(eq.air.readout()["dxdt_per_h"]) <= 0.0:
		fail("isolated: the CO2 trend is not rising")
	# restore: back to the exponential approach to the steady state
	await pl.act("exc.ops", "Ops · restore CO2 unit", h.ops, func(): return eq.air.mode == "RUNNING")
	var t_b: float = eq.air.history[-1][0]
	var m_b := m_a + G * (t_b - t_a)
	if eq.air.mode != "RUNNING":
		fail("Ops at the bay did not restore the unit (state %s)" % eq.air.mode)
	await _ticks(600)
	var V := float(p["V_m3"])
	var k := float(p["k_m3_s"])
	var m_ss := G * V / k
	var want_run := m_ss + (m_b - m_ss) * exp(-k * (eq.air.t_s - t_b) / V)
	if not _close(eq.air.m_kg, want_run, tol):
		fail("restored: m %s kg, closed form %s kg" % [str(eq.air.m_kg), str(want_run)])
	if float(eq.air.readout()["dxdt_per_h"]) >= 0.0:
		fail("restored: the CO2 trend is not falling")
	if absf(eq.air.ledger_error()) > float(tol["abs_kg"]):
		fail("ledger open by %s kg" % str(eq.air.ledger_error()))
	if eq.air.history.size() != 2:
		fail("the unit's transition log has %d entries, want 2" % eq.air.history.size())
	await _shot("SYS_3_restored")
	fails.append_array(pl.fails)
	notes["board"] = eq.board.text
	notes["record"] = eq.record()
	_finish()

## The touch button and the prompt both name the operation the model would apply, with the player's binding.
func _ui_says(label: String) -> void:
	var acts: Array = h.touch_state().get("actions", [])
	if not acts.any(func(a): return a[0] == "exc.ops" and a[1] == label):
		fail("touch: no '%s' button for exc.ops (%s)" % [label, str(acts)])
	var pr := h._prompt_text()
	if not pr.contains(h.key("exc.ops")) or not pr.contains(label.trim_prefix("Ops · ")):
		fail("prompt does not offer '%s' with the player's key: %s" % [label, pr])

## Two fresh copies of the model, the same operations at the same ship times, stepped at 1 s and at 60 s: the same state within the
## packaged tolerance (the step is the exact solution), and a repeated run is identical.
func _determinism(tol: Dictionary) -> void:
	var runs := []
	for dt in [1.0, 60.0, 1.0]:
		var a := WfCabinAir.load_package()
		var n := int(round(3600.0 / dt))
		for i in 4 * n:
			if i == n:
				a.operate("isolate")
			if i == 3 * n:
				a.operate("restore")
			a.step(dt)
		runs.append(a.m_kg)
	notes["determinism_m_kg"] = runs
	if not _close(runs[1], runs[0], tol):
		fail("a 60 s step gives %s kg, 1 s gives %s kg" % [str(runs[1]), str(runs[0])])
	if runs[2] != runs[0]:
		fail("a repeated run differs: %s vs %s" % [str(runs[2]), str(runs[0])])

func _finish() -> void:
	var out := {"result": "PASS" if fails.is_empty() else "FAIL", "fails": fails, "notes": notes,
		"wall_s": snappedf((Time.get_ticks_msec() - t0) / 1000.0, 0.1), "physics_frames": Engine.get_physics_frames()}
	print("WF_GODOT_SYSTEMS " + JSON.stringify(out))
	h.get_tree().quit(0 if fails.is_empty() else 1)
