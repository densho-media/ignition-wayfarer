class_name WfModeController
extends RefCounted
## Operating-mode controller (PHYS-001, SIMULATION_ONLY). It walks the ordered steps of rig `dynamics.transitions["A>B"]`
## (crew_dynamics.transition) in the owner's sequence (46 DYN-026, 15 CREW-MODE-004, WORKING scenario / flight event OPEN):
## main propulsion OFF -> occupants secured -> both rings decelerate -> rings locked -> HIGH_POWER permissible, and the reverse.
## Every step is untimed; only the ring ramp has a duration, the rig's `spin_ramp.study_value_s` (08 spin_time 1800 s, WORKING), at
## constant angular acceleration alpha = omega_full / T. A ramp never starts with the drive on (the concurrent <= 0.1 g case is
## unreleased) or with the occupants not secured: the transition then holds, fail closed. The field gets signed omega and alpha, so the
## Euler term -alpha x r acts (translation only). No First Ignition event time. Nothing here defines a physical constant.

const INSTANT := ["UNDOCK", "DOCK", "DRIVE_ON", "DRIVE_OFF", "OCCUPANTS_SECURED", "RINGS_LOCKED", "RINGS_UNLOCKED"]
const RAMPS := {"RINGS_SPIN_DOWN": "SPINNING_DOWN", "RINGS_SPIN_UP": "SPINNING_UP"}

var dyn: Dictionary
var field: WfFrameField
var mode := "COAST"                 # the settled mode, or the mode being left while a transition runs
var target := ""                    # non-empty while a transition runs
var steps_all: Array = []
var queue: Array = []               # steps still to run (the first one is current)
var done_steps: Array = []
var ring_state := "ROTATING"        # ROTATING / SPINNING_DOWN / STOPPED (unlocked) / STOPPED_LOCKED / SPINNING_UP
var occupants_secured := false      # set by the OCCUPANTS_SECURED step; released when the transition settles
var occupants_securable := true     # PROTOTYPE input: false = someone is not secured, the sequence holds before the ramp
var hold_reason := ""               # non-empty while the running transition is held (fail closed)
var spin_frac := 1.0                # omega / omega_full of the rings
var ramp_t := 0.0                   # seconds into the current ramp (simulation clock)
var drive_on := false
var drive_mode := "COAST"           # the mode whose ship acceleration applies while the drive is on
var docked := false
var damaged: Array = []             # modes marked DAMAGED are refused as source or target
var drum_synced := [true, true]     # PROTOTYPE interlock input per ring: drum synchronized with its ring (DYN-009)
var log: Array = []

func _init(d: Dictionary, f: WfFrameField, start_mode := "COAST") -> void:
	dyn = d
	field = f
	mode = start_mode
	spin_frac = float(d["modes"][mode]["ring_spin"])
	ring_state = "ROTATING" if spin_frac > 0.0 else "STOPPED_LOCKED"
	drive_on = d["modes"][mode]["drive"] == "ACTIVE"
	drive_mode = mode
	docked = mode == "DOCKED"
	apply()

func busy() -> bool:
	return target != ""

func ramp_s() -> float:
	return float(dyn["spin_ramp"]["study_value_s"])

func ramp_label() -> String:
	return "ring ramp %.0f s, constant alpha (%s, timing OPEN)" % [ramp_s(), dyn["spin_ramp"]["status"]]

func omega_full(k: int) -> float:
	return dyn["rings"][k]["sign"] * float(dyn["rings"][k]["omega_rad_s"])      # signed, about +X

func omega_now(k: int) -> float:
	return omega_full(k) * spin_frac

## Signed angular acceleration of ring k (rad/s2 about +X): -omega_full/T while spinning down, +omega_full/T while spinning up.
func alpha_now(k: int) -> float:
	match ring_state:
		"SPINNING_DOWN": return -omega_full(k) / ramp_s()
		"SPINNING_UP": return omega_full(k) / ramp_s()
	return 0.0

func ship_accel_g() -> float:
	return float(dyn["modes"][drive_mode]["demo_ship_accel_g"]) if drive_on else 0.0

func ship_accel_label() -> String:
	if not drive_on:
		return "drive off, 0 g (known)"
	var sa: Dictionary = dyn["modes"][drive_mode]["ship_accel"]
	return "%.2f g" % ship_accel_g() + (" (known)" if sa["known"] else " (envelope bound, not a flight value)")

func ship_accel_label_for(to: String) -> String:
	var sa: Dictionary = dyn["modes"][to]["ship_accel"]
	return "%.2f g" % float(dyn["modes"][to]["demo_ship_accel_g"]) + (" (known)" if sa["known"] else " (envelope bound, not a flight value)")

## Write the current omega, alpha and ship acceleration into the field (the field's own ring decides which ring applies).
func apply() -> void:
	var k := WfFrames.ring_index(field.zone)
	field.mode = mode
	field.w = WfFrames.v3(omega_now(k), 0.0, 0.0) if k >= 0 else WfFrames.v3(0.0, 0.0, 0.0)
	field.alpha = WfFrames.v3(alpha_now(k), 0.0, 0.0) if k >= 0 else WfFrames.v3(0.0, 0.0, 0.0)
	field.a_ship = WfFrames.v3(ship_accel_g() * dyn["standard_gravity_m_s2"], 0.0, 0.0)

func _refuse(to: String, reason: String) -> Dictionary:
	var e := {"status": "SIMULATION_ONLY", "refused": true, "from": mode, "to": to, "reason": reason}
	log.append(e)
	return e

## Ask for a mode. The result is the log entry: {status: "SIMULATION_ONLY", refused, from, to, steps, timed: false}.
func request(to: String) -> Dictionary:
	if busy():
		if to == "LOW_THRUST" and ring_state in ["SPINNING_DOWN", "SPINNING_UP"]:
			return _refuse(to, "LOW_THRUST during a ring speed change is not released (DYN-026)")
		return _refuse(to, "a transition %s -> %s is still running" % [mode, target])
	if not dyn["modes"].has(to):
		return _refuse(to, "%s is not a known operating mode" % to)
	if mode in damaged or to in damaged:
		return _refuse(to, "DAMAGED state: no transition is defined (DYN-020 stays HOLD)")
	if to == mode:
		var same := {"status": "SIMULATION_ONLY", "refused": false, "from": mode, "to": to, "steps": [], "timed": false}
		log.append(same)
		return same
	var tr: Variant = dyn["transitions"].get("%s>%s" % [mode, to])
	if tr == null or not tr["allowed"]:
		return _refuse(to, "%s>%s is not in the rig transition table" % [mode, to])
	target = to
	steps_all = (tr["steps"] as Array).duplicate()
	queue = steps_all.duplicate()
	done_steps = []
	var e := {"status": "SIMULATION_ONLY", "refused": false, "from": mode, "to": to, "steps": steps_all.duplicate(), "timed": false, "ramp": tr["ramp"]}
	log.append(e)
	_run()
	return e

## Gate of a ring ramp (mirror of crew_dynamics.ramp_allowed).
func ramp_allowed() -> Dictionary:
	if drive_on:
		return {"allowed": false, "reason": "drive on: a ring ramp under thrust (<= 0.1 g concurrent case) is not released (DYN-026)"}
	if not occupants_secured:
		return {"allowed": false, "reason": "occupants not secured"}
	return {"allowed": true, "reason": "drive off, occupants secured"}

func _hold(s: String, reason: String) -> void:
	if hold_reason != reason:
		hold_reason = reason
		log.append({"status": "SIMULATION_ONLY", "step": s, "held": true, "reason": reason})

func _run() -> void:
	while not queue.is_empty():
		var s: String = queue[0]
		if RAMPS.has(s):
			if ring_state != RAMPS[s]:
				var g := ramp_allowed()
				if not g["allowed"]:
					_hold(s, g["reason"])
					break
				ring_state = RAMPS[s]
				ramp_t = 0.0
				hold_reason = ""
				log.append({"status": "SIMULATION_ONLY", "step": s, "timed": false, "ramp_s": ramp_s()})
			break
		match s:
			"UNDOCK": docked = false
			"DOCK": docked = true
			"DRIVE_ON":
				if ring_state != "STOPPED_LOCKED" and dyn["modes"][target]["habitat"] == "STOPPED_LOCKED":
					_hold(s, "rings not locked: HIGH_POWER not permissible")
					break
				drive_on = true
				drive_mode = target
			"DRIVE_OFF": drive_on = false
			"OCCUPANTS_SECURED":
				if not occupants_securable:
					_hold(s, "an occupant is not secured")
					break
				occupants_secured = true
			"RINGS_LOCKED":
				if absf(spin_frac) > 0.0:
					_hold(s, "rings still turning")
					break
				ring_state = "STOPPED_LOCKED"
			"RINGS_UNLOCKED": ring_state = "STOPPED"
		hold_reason = ""
		log.append({"status": "SIMULATION_ONLY", "step": s, "timed": false})
		done_steps.append(queue.pop_front())
	if queue.is_empty() and busy():
		mode = target
		target = ""
		occupants_secured = false
		log.append({"status": "SIMULATION_ONLY", "settled": mode})
	apply()

## Re-try a held transition after its input changed (e.g. occupants_securable set true).
func resume() -> void:
	if busy():
		_run()

## Advance the ring ramp by `seconds` of simulation time. alpha is the true omega_full / T; a demo that wants the ramp quickly calls
## skip() with the elapsed seconds (PROTOTYPE presentation shortcut: the state at each instant is the real-time one, the bodies in between
## are not integrated). Real time: advance(delta) from _physics_process.
func skip(seconds: float) -> void:
	var left := seconds
	while left > 0.0 and RAMPS.has(queue[0] if not queue.is_empty() else "") and ring_state in ["SPINNING_DOWN", "SPINNING_UP"]:
		var take := minf(left, ramp_s() - ramp_t)
		ramp_t += take
		left -= take
		spin_frac = 1.0 - ramp_t / ramp_s() if ring_state == "SPINNING_DOWN" else ramp_t / ramp_s()
		if ramp_t >= ramp_s() - 1e-9:
			spin_frac = 0.0 if ring_state == "SPINNING_DOWN" else 1.0
			ring_state = "STOPPED" if ring_state == "SPINNING_DOWN" else "ROTATING"
			done_steps.append(queue.pop_front())
			_run()
	apply()

func advance(dt: float) -> void:
	skip(dt)

func ring_edges() -> Array:
	return dyn["nav"]["edges"]

func find_edge(a: String, b := "") -> Dictionary:
	for e in ring_edges():
		if (e["from"] == a and (b == "" or e["to"] == b)) or (b == "" and e["to"] == a):
			return e
	return {}

## Nav gate semantics (DYN-009, PORT_GATE): a rotating interface is crossable only with its drum synchronized to the ring or both
## stopped and locked, both closures behind the crosser closed, and no ring ramp running or still to come in the current transition.
## `iface` is a nav edge or a node name. The reason of the last call is in `cross_reason`.
var cross_reason := ""

func can_cross(iface, closed_behind := true) -> bool:
	var e: Dictionary = iface if iface is Dictionary else find_edge(str(iface))
	if e.is_empty():
		cross_reason = "no such nav edge"
		return false
	if not (mode in e["modes"]):
		cross_reason = "edge not open in mode %s" % mode
		return false
	if not e["rotating_interface"]:
		cross_reason = "open"
		return true
	var k := 0
	for n in [e["from"], e["to"]]:
		if str(n).begins_with("VESTIBULE_"):
			k = int(str(n).split("_")[1]) - 1
	if ring_state in ["SPINNING_DOWN", "SPINNING_UP", "STOPPED"]:
		cross_reason = "ring %s is ramping (%s)" % [dyn["rings"][k]["name"], ring_state]
		return false
	if busy() and steps_all.any(func(s): return RAMPS.has(s)):
		cross_reason = "a ring ramp belongs to the running transition"
		return false
	if not drum_synced[k]:
		cross_reason = "drum not synchronized with %s" % dyn["rings"][k]["name"]
		return false
	if not closed_behind:
		cross_reason = "closures behind the crosser are not both closed"
		return false
	cross_reason = "synchronized or stopped at the index"
	return true

## HUD text: mode, step list with a marker on the current step, ramp, ship acceleration, and the SIMULATION_ONLY labels.
func hud_text() -> String:
	var t := "MODE %s%s   SIMULATION_ONLY, untimed steps   rings %s (spin %.3f)\n" % [mode, " -> " + target if busy() else "", ring_state, spin_frac]
	if busy():
		var parts: Array = []
		for s in done_steps:
			parts.append("[x] " + s)
		for i in queue.size():
			parts.append(("[>] " if i == 0 else "[ ] ") + queue[i])
		t += "steps: " + "  ".join(parts) + "\n"
		if hold_reason != "":
			t += "HELD (fail closed): %s\n" % hold_reason
	t += "%s   alpha(A) %s rad/s2   omega(A) %.4f rad/s\n" % [ramp_label(), String.num_scientific(alpha_now(0)), omega_now(0)]
	t += "ship accel %s\n" % ship_accel_label()
	return t
