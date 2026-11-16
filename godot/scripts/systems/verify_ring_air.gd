extends SceneTree
## Headless check of the ring air model alone (no scene, no ship): load a package, replay both reference runs, report the largest
## deviations from the Python checkpoints and the cost of the step. Development tool:
##   godot --headless --path godot --script res://scripts/systems/verify_ring_air.gd -- <path to wf_ring_air.json>

func _init() -> void:
	var args := OS.get_cmdline_user_args()
	var path: String = args[0] if args.size() > 0 else "res://generated/wf_ring_air.json"
	var a := WfRingAir.load_package(path)
	if a == null:
		print("RING_AIR_VERIFY ", JSON.stringify({"result": "FAIL", "errors": ["no package at " + path]}))
		quit(1)
		return
	var out := {"verified": a.verified, "errors": a.errors, "version": a.doc.get("version", 0), "trace": a.doc.has("trace")}
	out["co2"] = _deviation(a, a.doc["proof"], false)
	if a.doc.has("trace"):
		out["nh3"] = _deviation(a, a.doc["trace"]["proof"], true)
	out["cost_us"] = _cost(a)
	out["result"] = "PASS" if a.verified else "FAIL"
	print("RING_AIR_VERIFY ", JSON.stringify(out))
	quit(0 if a.verified else 1)

## The largest absolute and relative deviation of every compared value over a reference run.
func _deviation(a: WfRingAir, proof: Dictionary, trace: bool) -> Dictionary:
	a.reset()
	var events: Array = (proof["events"] as Array).duplicate(true)
	var dt := float(proof["dt_s"])
	var steps := int(round(float(proof["end_s"]) / dt))
	var every := int(round(float(proof["every_s"]) / dt))
	var cps: Array = proof["checkpoints"]
	var worst_abs := 0.0
	var worst_rel := 0.0
	var ci := 0
	var ledger := 0.0
	for i in steps + 1:
		while not events.is_empty() and a.t_s >= float(events[0][0]) - 1e-9:
			a._apply(events.pop_front())
		if i % every == 0:
			var want: Dictionary = cps[ci]
			var got: Array = []
			var exp_: Array = []
			if trace:
				got = a.c.duplicate()
				got.append_array([a.S, a.released, a.nh3_removed])
				exp_ = (want["c"] as Array).duplicate()
				exp_.append_array([want["S"], want["released"], want["removed"]])
			else:
				got = a.m.duplicate()
				got.append_array([a.generated, a.removed])
				exp_ = (want["m"] as Array).duplicate()
				exp_.append_array([want["generated"], want["removed"]])
			for q in got.size():
				var d := absf(float(got[q]) - float(exp_[q]))
				worst_abs = maxf(worst_abs, d)
				if absf(float(exp_[q])) > 1e-12:
					worst_rel = maxf(worst_rel, d / absf(float(exp_[q])))
			ledger = maxf(ledger, absf(a.trace_ledger_error() if trace else a.ledger_error()))
			ci += 1
		if i < steps:
			a.step(dt)
	a.reset()
	return {"checkpoints": ci, "max_abs_kg": worst_abs, "max_rel": worst_rel, "max_ledger_kg": ledger}

## Microseconds: one CO2-only step, one step carrying NH3, and building each propagator (a topology change).
func _cost(a: WfRingAir) -> Dictionary:
	var out := {}
	a.reset()
	a.step(10.0)
	var t0 := Time.get_ticks_usec()
	for i in 200:
		a.step(10.0)
	out["step_co2_only"] = float(Time.get_ticks_usec() - t0) / 200.0
	a.set_source(a.ids[0], 0.007, 3600.0)
	a.step(10.0)
	t0 = Time.get_ticks_usec()
	for i in 200:
		a.step(10.0)
	out["step_with_nh3"] = float(Time.get_ticks_usec() - t0) / 200.0
	t0 = Time.get_ticks_usec()
	for i in 10:
		a.cache = {}
		a.propagator(10.0)
	out["build_co2_propagator"] = float(Time.get_ticks_usec() - t0) / 10.0
	t0 = Time.get_ticks_usec()
	for i in 10:
		a.tcache = {}
		a.trace_step(0.0 + 10.0)
	out["build_nh3_propagator_and_step"] = float(Time.get_ticks_usec() - t0) / 10.0
	a.reset()
	return out
