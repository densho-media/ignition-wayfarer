class_name WfCabinAir
extends RefCounted
## SYS-001 ring A cabin CO2 (src/wayfarer/cabin_air.py): the runtime copy of the engineering state. It repeats the module's exact step
## on the packaged parameters, applies operations only through the packaged operation table (requires / sets, with the packaged
## refusal reasons), and must reproduce the packaged checkpoints within the packaged tolerance (verify()) before anyone shows its state.
## Godot computes no parameter; it knows nothing of games, scenarios or scores. SIMULATION: PROTOTYPE values travel labelled.
##
## The unit's state has three independent fields (as in the module): mode RUNNING / ISOLATED, fan OK / FAILED, and where the spare fan
## is (NONE / BENCH / CARRIED / INSTALLED). It removes CO2 only when RUNNING with its fan OK.

const M_CO2 := 0.0440095        # kg/mol, the module's constant (the check below would catch a mismatch through the checkpoints)
const FIELDS := ["mode", "fan", "spare"]

var doc := {}
var p := {}
var mode := "RUNNING"
var fan := "OK"
var spare := "NONE"
var t_s := 0.0
var m_kg := 0.0
var m0_kg := 0.0
var generated_kg := 0.0
var removed_kg := 0.0
var history: Array = []   # [t_s, op, fields before, fields set] per accepted operation
var verified := false
var errors: Array = []

static func load_package(path := "res://generated/wf_cabin_air.json") -> WfCabinAir:
	if not FileAccess.file_exists(path):
		return null
	var a := WfCabinAir.new()
	a.doc = JSON.parse_string(FileAccess.get_file_as_string(path))
	a.p = a.doc["params"]
	a.errors = a.verify()
	a.verified = a.errors.is_empty()
	a.reset()
	return a

func removing() -> bool:
	return mode == "RUNNING" and fan == "OK"

func steady_x() -> float:
	return _gen() * float(p["V_m3"]) / float(p["k_m3_s"]) / (float(p["n_mol"]) * M_CO2)

## The module's start(): at x0, or (x0 < 0) at the steady state when removing, else at the target.
func reset(m := "RUNNING", f := "OK", s := "NONE", x0 := -1.0) -> void:
	mode = m
	fan = f
	spare = s
	t_s = 0.0
	if x0 < 0.0:
		x0 = steady_x() if removing() else float(p["co2_target"])
	m_kg = x0 * float(p["n_mol"]) * M_CO2
	m0_kg = m_kg
	generated_kg = 0.0
	removed_kg = 0.0
	history = []

func _gen() -> float:
	return float(p["occupants"]) * float(p["per_person_kg_s"])

## The exact solution for constant generation and removal over dt (cabin_air.step).
func step(dt: float) -> void:
	var G := _gen()
	var V := float(p["V_m3"])
	var k := float(p["k_m3_s"]) if removing() else 0.0
	var m_new: float
	if k > 0.0:
		var m_ss := G * V / k
		m_new = m_ss + (m_kg - m_ss) * exp(-k * dt / V)
	else:
		m_new = m_kg + G * dt
	generated_kg += G * dt
	removed_kg += G * dt - (m_new - m_kg)
	m_kg = m_new
	t_s += dt

func field(f: String) -> String:
	return str(get(f))

## "" if op is allowed now, else the field that blocks it ("op" for an unknown operation).
func blocked(op: String) -> String:
	var ops: Dictionary = doc["operations"]
	if not ops.has(op):
		return "op"
	var req: Dictionary = ops[op]["requires"]
	for f in req:
		if not field(f) in req[f]:
			return f
	return ""

## "" or the reason the operation is refused (state unchanged).
func operate(op: String) -> String:
	var f := blocked(op)
	if f == "op":
		return "unknown operation %s" % op
	if f != "":
		var why: Dictionary = doc["refusals"].get(op, {}).get(f, {})
		return str(why.get(field(f), "%s refused: %s is %s" % [op, f, field(f)]))
	var sets: Dictionary = doc["operations"][op]["sets"]
	var was := {}
	for k in sets:
		was[k] = field(k)
	history.append([t_s, op, was, sets.duplicate()])
	for k in sets:
		set(k, str(sets[k]))
	return ""

func ledger_error() -> float:
	return m_kg - (m0_kg + generated_kg - removed_kg)

func x() -> float:
	return m_kg / M_CO2 / float(p["n_mol"])

func status() -> String:
	if mode == "RUNNING":
		return "OPERATING" if fan == "OK" else "RUNNING_NOT_REMOVING"
	return "ISOLATED_READY" if fan == "OK" else "ISOLATED_FAULT"

## What a panel can show (cabin_air.readout): the time to the control limit counts from the present state at the present trend.
func readout() -> Dictionary:
	var xx := x()
	var pp := xx * float(p["P_Pa"]) / 1000.0
	var k := float(p["k_m3_s"]) if removing() else 0.0
	var dxdt_h := (_gen() - k * m_kg / float(p["V_m3"])) / M_CO2 / float(p["n_mol"]) * 3600.0
	var band := "NOMINAL" if xx <= float(p["co2_target"]) else ("ABOVE_TARGET" if xx <= float(p["co2_max"]) else "CONTROL")
	for b in doc["bands"].slice(1):
		if pp >= float(b["kpa"]):
			band = str(b["id"])
	var to_max = null
	var xm := float(p["co2_max"])
	if xx < xm and dxdt_h > 0.0:
		if k > 0.0:
			var xs := steady_x()
			if xs > xm:
				to_max = -float(p["V_m3"]) / k * log((xs - xm) / (xs - xx)) / 3600.0
		else:
			to_max = (xm - xx) / dxdt_h
	return {"x": xx, "pp_kpa": pp, "dxdt_per_h": dxdt_h, "band": band, "mode": mode, "fan": fan, "spare": spare, "status": status(),
		"removing": removing(), "hours_to_control_limit": to_max, "t_s": t_s}

## The unit's component readings (cabin_air.diagnostics).
func diagnostics() -> Dictionary:
	var on := mode == "RUNNING"
	var k := float(p["k_m3_s"]) if removing() else 0.0
	return {"supply": "ENERGIZED" if on else "ISOLATED", "controller": "SELF-TEST PASS" if on else "OFF (isolated)",
		"fan_command": "ON" if on else "OFF", "fan_speed_pct": 100.0 if removing() else 0.0, "fan_condition": fan,
		"scrubbed_flow_m3_h": k * 3600.0, "bed": "NORMAL" if on else "NORMAL (cold)", "removal_kg_h": k * m_kg / float(p["V_m3"]) * 3600.0,
		"spare": spare}

func band_meaning(id: String) -> String:
	for b in doc["bands"]:
		if b["id"] == id:
			return "%s: %s" % [b["kind"], b["meaning"]]
	return ""

func band_kpa(id: String) -> float:
	for b in doc["bands"]:
		if b["id"] == id:
			return float(b["kpa"])
	return 0.0

## Hours for the fraction to climb from x_from to x_to with no removal (cabin_air.hours_between).
func hours_between(x_from: float, x_to: float) -> float:
	return (x_to - x_from) * float(p["n_mol"]) * M_CO2 / _gen() / 3600.0

func save() -> Array:
	return [mode, fan, spare, t_s, m_kg, m0_kg, generated_kg, removed_kg, history.duplicate(true)]

func load_state(k: Array) -> void:
	mode = k[0]; fan = k[1]; spare = k[2]; t_s = k[3]; m_kg = k[4]; m0_kg = k[5]; generated_kg = k[6]; removed_kg = k[7]; history = k[8]

## Replays the packaged proof run (same start, same events with their expected outcomes, same step) and compares every checkpoint and
## the ledger with the packaged tolerance. Returns the failures (empty: the runtime copy reproduces the reference model).
func verify() -> Array:
	var bad: Array = []
	var pr: Dictionary = doc["proof"]
	var tol: Dictionary = doc["tolerance"]
	var keep := save()
	var s0: Dictionary = pr["start"]
	reset(str(s0["mode"]), str(s0["fan"]), str(s0["spare"]))
	var events: Array = pr["events"].duplicate(true)
	var dt := float(pr["dt_s"])
	var steps := int(round(float(pr["end_s"]) / dt))
	var every := int(round(float(pr["every_s"]) / dt))
	var cps: Array = pr["checkpoints"]
	var ci := 0
	for i in steps + 1:
		while not events.is_empty() and t_s >= float(events[0][0]) - 1e-9:
			var e: Array = events.pop_front()
			var want := str(e[2])
			var got := blocked(str(e[1]))
			var before := [mode, fan, spare]
			var r := operate(str(e[1]))
			if got != want:
				bad.append("proof event %s at %s s: outcome '%s', reference '%s' (%s)" % [e[1], str(e[0]), got, want, r])
			if want != "" and [mode, fan, spare] != before:
				bad.append("proof event %s at %s s was refused but changed the state" % [e[1], str(e[0])])
		if i % every == 0:
			if ci >= cps.size():
				bad.append("more checkpoints than packaged")
				break
			var c: Dictionary = cps[ci]
			for key in ["m_kg", "generated_kg", "removed_kg"]:
				var want_v := float(c[key])
				var got_v: float = get(key)
				if absf(got_v - want_v) > float(tol["abs_kg"]) + float(tol["rel"]) * absf(want_v):
					bad.append("t %.0f s %s %s, reference %s" % [t_s, key, str(got_v), str(want_v)])
			if absf(t_s - float(c["t_s"])) > 1e-9 or [mode, fan, spare] != [str(c["mode"]), str(c["fan"]), str(c["spare"])]:
				bad.append("t %.0f s state %s/%s/%s, reference %s/%s/%s at %s" % [t_s, mode, fan, spare, c["mode"], c["fan"], c["spare"], c["t_s"]])
			ci += 1
		if absf(ledger_error()) > float(tol["abs_kg"]):
			bad.append("ledger open by %s kg at %.0f s" % [str(ledger_error()), t_s])
			break
		if i < steps:
			step(dt)
	if ci != cps.size():
		bad.append("%d of %d checkpoints compared" % [ci, cps.size()])
	load_state(keep)
	return bad
