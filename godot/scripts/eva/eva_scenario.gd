class_name WfEvaScenario
extends RefCounted
## "EVA — First Flight" (EVA-OPS-001): eight guided stages over the same bodies, gas and controls as free exploration. A stage moves on
## only when the scene's real state says it is done (events from the scene, or a polled condition), never on a timer. The one staged
## intervention, stage 7, vents the suit reserve to its emergency level and says so (counted as used gas, never created).

var ops
var running := false
var stage := 0
var done_flags := {}
var gas0 := 0.0
var t_stage := 0.0
var finished := false

const STAGES := [
	{"title": "1 PREPARATION", "goal": "You are at the EVA hatch, holding the rail. The drone is docked on your back: docked, the pair flies on its gas and the suit reserve is isolated. Read both gas panels, then press %s."},
	{"title": "2 SURFACE", "goal": "Clip your tether (%s) and move hand over hand along the rail: release (%s), drift a little with a light thrust or push, and grip the next anchor. Reach the forward hold."},
	{"title": "3 FREE FLIGHT", "goal": "Push off or thrust towards the Brow's aft face, brake (%s, assisted) and grip a Brow panel fixture. Whatever speed you build you must take off again with gas."},
	{"title": "4 DRONE DEPLOYMENT", "goal": "Release the drone (%s): its tongue spring pushes it off your back. Your own 16 nozzles and reserve take over."},
	{"title": "5 DRONE FLIGHT", "goal": "Take the drone (%s), fly to a Brow fixture and inspect it: sensor nose on it within 2.5 m, then %s."},
	{"title": "6 PROPELLANT", "goal": "Bring the drone back to within 3 m of the astronaut and stop relative to it, on less than 0.20 kg of gas for this stage. Every metre per second you build you pay for twice."},
	{"title": "7 RESUPPLY", "goal": "TRAINING: the suit reserve has been vented to its emergency level. Ask the drone for nitrogen (%s), or fly it yourself: arms (%s), take an RC-1 at the station rack (%s), bring it behind the astronaut and seat it (%s)."},
	{"title": "8 RETURN", "goal": "Return to the EVA hatch. Stow the cartridge at the rack (%s) if one is seated, dock the drone (%s) and grip the hatch hold (%s)."},
]

func _init(o) -> void:
	ops = o

func start() -> void:
	if not ops.training:
		ops.training = true
	ops.training_reset()
	running = true
	finished = false
	stage = 0
	done_flags = {}
	t_stage = 0.0
	ops.say("FIRST FLIGHT: a guided training EVA. Gas is finite; the reset (%s) is labelled training." % WfInput.label("evaops.reset"))

func card() -> String:
	if not running:
		return "FREE EXPLORATION · %s starts EVA — First Flight" % ops.key("evaops.scenario") if not finished else "FIRST FLIGHT COMPLETE · %s to fly it again" % ops.key("evaops.scenario")
	var s: Dictionary = STAGES[stage]
	var k = func(id): return ops.key(id)
	var g: String = s["goal"]
	match stage:
		0: g = g % k.call("evaops.interact")
		1: g = g % [k.call("evaops.tether"), k.call("evaops.grab")]
		2: g = g % k.call("evaops.brake")
		3: g = g % k.call("evaops.dock")
		4: g = g % [k.call("evaops.drone"), k.call("evaops.interact")]
		5: g = g + "  (stage gas %.3f kg)" % (gas0 - ops.drone_gas.n2_kg)
		6: g = g % [k.call("evaops.help"), k.call("evaops.arms"), k.call("evaops.gripper"), k.call("evaops.interact")]
		7: g = g % [k.call("evaops.interact"), k.call("evaops.dock"), k.call("evaops.grab")]
	return "EVA — FIRST FLIGHT · %s\n%s" % [s["title"], g]

func event(ev: String) -> void:
	if not running:
		return
	done_flags[ev] = true
	if ev.begins_with("held:"):
		done_flags["held_kind:" + ev.split(":")[1]] = true

func _next() -> void:
	stage += 1
	t_stage = 0.0
	done_flags = {}
	gas0 = ops.drone_gas.n2_kg
	if stage >= STAGES.size():
		running = false
		finished = true
		ops.say("FIRST FLIGHT COMPLETE: astronaut and drone back at the hatch, docked. Gas used: reserve %.3f kg, drone %.3f kg, cartridges %d."
			% [ops.reserve.used_kg, ops.drone_gas.used_kg, ops.cartridges.size()])
		return
	if stage == 6:
		var floor_kg: float = ops.reserve.usable_full() * float(ops.pkg["rules"]["emergency_floor_fraction"])
		ops.training_vent_reserve(floor_kg * 0.6)
		ops.say("TRAINING: suit reserve vented to %.3f kg usable (below the emergency floor). Vented gas counts as used." % ops.reserve.usable(), false)
	ops.say("Stage " + STAGES[stage]["title"])

func step(dt: float) -> void:
	if not running:
		return
	t_stage += dt
	var s: WfEvaBody = ops.suit
	var d: WfEvaBody = ops.drone
	match stage:
		0:
			if done_flags.has("ack"):
				_next()
		1:
			var fh: Vector3 = WfEvaPkg.v(ops.pkg["ship"]["route"]["holds"]["forward_hold"]["p"])
			if done_flags.has("tether") and s.held and (ops.hold_id.begins_with("ANC_FORWARD") or ops.hold_id == "HOLD_FORWARD_HOLD") and s.global_position.distance_to(fh) < 2.0:
				_next()
		2:
			if s.held and ops.hold_id.begins_with("BROW_FIX"):
				_next()
		3:
			if not ops.docked and d.global_position.distance_to(s.global_position) > 1.0:
				_next()
		4:
			if done_flags.keys().any(func(x): return String(x).begins_with("inspect:")):
				_next()
		5:
			if not ops.docked and d.global_position.distance_to(s.global_position) < 3.0 and (d.linear_velocity - s.linear_velocity).length() < 0.05:
				if gas0 - ops.drone_gas.n2_kg <= 0.20:
					_next()
				elif t_stage > 1.0 and not done_flags.has("over"):
					done_flags["over"] = true
					ops.say("Stage 6 used %.3f kg of drone gas (limit 0.20): fly it again slower (F6 checkpoint), or carry on in free mode." % (gas0 - ops.drone_gas.n2_kg), false)
		6:
			if ops.rescues > 0 or (done_flags.has("seated") and ops.suit_dv_available() > 0.5):
				_next()
		7:
			var hatch: Vector3 = WfEvaPkg.v(ops.pkg["ship"]["route"]["holds"]["airlock"]["p"])
			if ops.docked and s.held and s.global_position.distance_to(hatch) < 2.0:
				_next()
