class_name WfFlightSession
extends WfReviewSession
## U05: the First Ignition timeline review in the flight scene. Every step completes on the scene's own state (frame and phase, the ring
## locks channel, the look switch, the Y155 case shown, a named state picked); nothing here changes a channel or a value.

var host: Node                               # the flight scene (flight.gd)

func _init(h: Node) -> void:
	host = h
	title = "First Ignition timeline"
	steps = [
		{"title": "Play the timeline", "goal": "Start the PROTOTYPE First Ignition timeline: induction, coast, spin-down, burn, cooldown and spin-up again.",
			"expect": "The rings turn; the frame counter in the details (I) runs. Phase order and timing are display choices."},
		{"title": "Spin-down and lock", "goal": "Let the rings slow down and lock before the drive starts (fast-forward with Shift + right arrow if you like).",
			"expect": "Both rings slow to a stop and lock: no ring spins while the drive burns."},
		{"title": "Reach the burn", "goal": "Go on to the burn phase.",
			"expect": "The drive glow and plasma display come on; the rings stay locked. The kinematics are a 1-D diagnostic route, not a mission."},
		{"title": "First Ignition look", "goal": "Switch to the physically lit exterior look: one hard sun, grey surface proxies, the radiators' hot face at 1800 K.",
			"expect": "Black sky, a hard sun; the radiators glow only while their thermal state is the hot one. Red/yellow mount colours are a legend only, not paint."},
		{"title": "Y155 radiator scenario", "goal": "Show the Y155 coating scenario on the same three blades.",
			"expect": "Uplift ×1.090, 15.703 GW ideal, a 0.297 GW deficit against the 16 GW calibration: DIAGNOSTIC. The blades do not shrink or change."},
		{"title": "A state outside the timeline", "goal": "Pick a named state from the STATES list on the right (for example SHIELD_DAMAGED or CROWN_ENGAGED).",
			"expect": "The ship shows that configuration or display pose; the details name its kind and status."},
	]

func phase_id() -> String:
	return str(host.timeline.phases[host.phase_index(host.frame)].id)

## True once the timeline is at or past phase `id` (the rings are also locked while docked at the start, before any spin-up).
func after(id: String) -> bool:
	var ids: Array = host.timeline.phases.map(func(p): return str(p.id))
	return host.phase_index(host.frame) >= ids.find(id)

func done(i: int) -> bool:
	match i:
		0: return host.frame > host.first_frame + 10.0
		1: return host.state_name == "" and after("STOP_LOCK") and host.channel("rotor.ring_locks_engaged") > 0.5
		2: return host.state_name == "" and phase_id() == "BURN"
		3: return host.look_on
		4: return host.scenario_index >= 1
		5: return host.state_name != ""
	return false

func progress(i: int) -> String:
	if i in [0, 1, 2]:
		return "%s · frame %d" % [phase_id(), int(host.frame)]
	return ""

func result(i: int) -> String:
	match i:
		1: return "Rings locked at frame %d (%s)" % [int(host.frame), phase_id()]
		4:
			var c: Dictionary = host.rig.thermal.y155_scenario.cases[host.scenario_index]
			return "%s: uplift ×%.5f, %.3f GW ideal on the same blades" % [c.id, c.uplift, c.rejection_W / 1e9]
		5: return "State %s (%s, %s)" % [host.state_name, host.states[host.state_name].kind, host.states[host.state_name].status]
	return ""

func keys(i: int) -> Array:
	var exit := [WfInput.label("ui.cancel"), "back to the review menu", "exit"]
	var look := ["Drag", "orbit · wheel zoom · %s–%s views" % [WfInput.label("flight.view_1"), WfInput.label("flight.view_6")], "now"]
	match i:
		0: return [[WfInput.label("flight.play"), "play", "next"], look, exit]
		1, 2: return [[WfInput.label("flight.play"), "pause" if host.playing else "play", "next"], ["Shift+" + WfInput.label("flight.frame_next"), "24 frames on", "now"], [WfInput.label("flight.frame_prev"), "back", "now"], exit]
		3: return [[WfInput.label("flight.look"), "First Ignition look", "next"], look, exit]
		4: return [[WfInput.label("flight.scenario"), "next radiator scenario", "next"], [WfInput.label("flight.look"), "look off" if host.look_on else "look on", "now"], exit]
		5: return [["Click", "a state in the STATES list", "next"], look, exit]
	return [exit]

func labels(i: int) -> Array:
	var t: Dictionary = host.timeline
	var k: Dictionary = t.kinematics
	var rot: Dictionary = host.rig.rotors[0]
	var sc: Dictionary = host.rig.thermal.y155_scenario
	match i:
		0: return [[str(t.status), "phase order and timing (display choices)"], ["HOLD", "P0 science: flight playback SIMULATION_ONLY"]]
		1: return [[str(rot.canon_status), "ring spin %s rpm (%s)" % [rot.rpm, rot.source_ref]], ["HOLD", "transition timing"]]
		2: return [["DIAGNOSTIC", "%s (%s)" % [k.scenario_status, k.source_ref]], ["HOLD", "absorbed drive heat, reaction mass, fusion fuel"]]
		3: return [[str(host.exterior.get("status", "PROTOTYPE")), "look: one sun, %.0f K hot face (%s)" % [float(host.exterior.get("kelvin", 0.0)), host.exterior.get("source_ref", "")]]]
		4: return [[str(sc.canon_status), "Y155 scenario inputs (%s)" % sc.source_ref], ["DIAGNOSTIC", str(sc.result_status)], ["OPEN", "actual drive heat, 1800 K qualification"]]
		5: return [["WORKING", "configurations BASELINE / WORKING"], ["PROTOTYPE", "display poses and drive actions"]]
	return []

func details() -> String:
	return host.readout.text
