class_name WfCabinAir
extends RefCounted
## SYS-001 ring A cabin CO2 (src/wayfarer/cabin_air.py): the runtime copy of the engineering state. It repeats the module's exact step
## on the packaged parameters, applies the unit's operations only along the packaged transitions, and must reproduce the packaged
## checkpoints within the packaged tolerance (verify()) before anyone shows its state. Godot computes no parameter; it knows nothing of
## games, scenarios or scores. SIMULATION: PROTOTYPE values travel labelled in the package.

const M_CO2 := 0.0440095        # kg/mol, the module's constant (the check below would catch a mismatch through the checkpoints)

var doc := {}
var p := {}
var state := "RUNNING"
var t_s := 0.0
var m_kg := 0.0
var m0_kg := 0.0
var generated_kg := 0.0
var removed_kg := 0.0
var log: Array = []
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

## The steady state of a running unit (the module's start()).
func reset() -> void:
	state = "RUNNING"
	t_s = 0.0
	var G := _gen()
	m_kg = G * float(p["V_m3"]) / float(p["k_m3_s"])
	m0_kg = m_kg
	generated_kg = 0.0
	removed_kg = 0.0
	log = []

func _gen() -> float:
	return float(p["occupants"]) * float(p["per_person_kg_s"])

## The exact solution for constant generation and removal over dt (cabin_air.step).
func step(dt: float) -> void:
	var G := _gen()
	var V := float(p["V_m3"])
	var k := float(p["k_m3_s"]) if state == "RUNNING" else 0.0
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

## "" or the reason the operation is refused (state unchanged).
func operate(op: String) -> String:
	var ops: Dictionary = doc["operations"]
	if not ops.has(op):
		return "unknown operation %s" % op
	if not state in ops[op]["allowed"]:
		return "%s refused: the unit is %s" % [op, state]
	log.append([t_s, state, ops[op]["to"]])
	state = str(ops[op]["to"])
	return ""

func ledger_error() -> float:
	return m_kg - (m0_kg + generated_kg - removed_kg)

func x() -> float:
	return m_kg / M_CO2 / float(p["n_mol"])

## What a panel can show (cabin_air.readout).
func readout() -> Dictionary:
	var xx := x()
	var pp := xx * float(p["P_Pa"]) / 1000.0
	var k := float(p["k_m3_s"]) if state == "RUNNING" else 0.0
	var dxdt_h := (_gen() - k * m_kg / float(p["V_m3"])) / M_CO2 / float(p["n_mol"]) * 3600.0
	var band := "NOMINAL" if xx <= float(p["co2_target"]) else ("ABOVE_TARGET" if xx <= float(p["co2_max"]) else "CONTROL")
	for b in doc["bands"].slice(1):
		if pp >= float(b["kpa"]):
			band = str(b["id"])
	var to_max = (float(p["co2_max"]) - xx) / dxdt_h if dxdt_h > 0.0 and xx < float(p["co2_max"]) else null
	return {"x": xx, "pp_kpa": pp, "dxdt_per_h": dxdt_h, "band": band, "state": state, "hours_to_control_limit": to_max}

func band_meaning(id: String) -> String:
	for b in doc["bands"]:
		if b["id"] == id:
			return "%s: %s" % [b["kind"], b["meaning"]]
	return ""

## Replays the packaged proof run (same events, same step) and compares every checkpoint and the ledger with the packaged tolerance.
## Returns the failures (empty: the runtime copy reproduces the reference model).
func verify() -> Array:
	var bad: Array = []
	var pr: Dictionary = doc["proof"]
	var tol: Dictionary = doc["tolerance"]
	var keep := [state, t_s, m_kg, m0_kg, generated_kg, removed_kg, log]
	reset()
	var events: Array = pr["events"].duplicate(true)
	var dt := float(pr["dt_s"])
	var steps := int(round(float(pr["end_s"]) / dt))
	var every := int(round(float(pr["every_s"]) / dt))
	var cps: Array = pr["checkpoints"]
	var ci := 0
	for i in steps + 1:
		while not events.is_empty() and t_s >= float(events[0][0]) - 1e-9:
			var r := operate(str(events.pop_front()[1]))
			if r != "":
				bad.append("proof event refused: " + r)
		if i % every == 0:
			if ci >= cps.size():
				bad.append("more checkpoints than packaged")
				break
			var c: Dictionary = cps[ci]
			for key in ["m_kg", "generated_kg", "removed_kg"]:
				var want := float(c[key])
				var got: float = get(key)
				if absf(got - want) > float(tol["abs_kg"]) + float(tol["rel"]) * absf(want):
					bad.append("t %.0f s %s %s, reference %s" % [t_s, key, str(got), str(want)])
			if absf(t_s - float(c["t_s"])) > 1e-9 or state != str(c["state"]):
				bad.append("t %.0f s state %s, reference %s at %s" % [t_s, state, c["state"], c["t_s"]])
			ci += 1
		if absf(ledger_error()) > float(tol["abs_kg"]):
			bad.append("ledger open by %s kg at %.0f s" % [str(ledger_error()), t_s])
			break
		if i < steps:
			step(dt)
	if ci != cps.size():
		bad.append("%d of %d checkpoints compared" % [ci, cps.size()])
	state = keep[0]; t_s = keep[1]; m_kg = keep[2]; m0_kg = keep[3]; generated_kg = keep[4]; removed_kg = keep[5]; log = keep[6]
	return bad
