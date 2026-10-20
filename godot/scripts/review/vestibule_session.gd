class_name WfVestibuleSession
extends WfReviewSession
## U03: the ring A vestibule drill (DYN-027 handoff) in the physics lab. Every step completes on the vestibule model's own state
## (WfVestibule: restraint, drum speed against the ring, pressure flag, closures, the handoff log entry); V is the only key that moves it.

var host: Node                               # the physics lab (physics_lab.gd)

func _init(h: Node) -> void:
	host = h
	title = "Ring A vestibule drill"
	steps = [
		{"title": "Restrain the occupant", "goal": "Strap the occupant into the drum seat with both closures shut. The drum only changes speed with someone restrained.",
			"expect": "The detail line reports \"restrain\": occupant restrained, both closures closed."},
		{"title": "Spin the drum up to the ring", "goal": "Match the drum's spin to ring A's, so that its ring-side hatch stops moving relative to the ring.",
			"expect": "The drum ramps up for about 4 s (a labelled presentation time, the real cycle is OPEN) and holds at the ring's speed."},
		{"title": "Equalize pressure", "goal": "Show the pressure as equal on both sides of the ring-side hatch.",
			"expect": "\"Pressure shown equalized\": a flag only. The allowed imbalance and flow are OPEN."},
		{"title": "Open the ring side", "goal": "Open the ring-side hatch. It opens only when the drum matches the ring, the pressure is equal and the other hatch is shut.",
			"expect": "The ring-side closure opens; the stationary side stays closed (never both open)."},
		{"title": "Hand the occupant over", "goal": "Move the occupant from the drum into the ring's frame at the real drum restraint pose.",
			"expect": "Their position and velocity are converted with w x r: the ship-frame speed becomes the ring-frame speed."},
		{"title": "Close the ring side", "goal": "Shut the ring-side hatch again.", "expect": "Both closures closed."},
		{"title": "Spin the drum back down", "goal": "Bring the drum back to the stationary spine's speed for the next passage.",
			"expect": "The drum ramps down to 0 rad/s and holds."},
	]

func vest() -> WfVestibule:
	return host.vest

func ring_w() -> float:
	return host.modes.omega_now(0)

func _did(action: String) -> bool:
	return vest().log.any(func(e): return e["action"] == action and e["ok"])

func done(i: int) -> bool:
	var v := vest()
	match i:
		0: return v.restrained and _did("restrain")
		1: return not v.ramping and _did("sync to RING") and absf(v.drum_w - ring_w()) <= v.tol()
		2: return v.dp_equalized == true
		3: return not v.closures["RING"]
		4: return _did("handoff")
		5: return v.closures["RING"] and v.closures["STATIONARY"] and _did("handoff")
		6: return not v.ramping and _did("sync to STATIONARY") and absf(v.drum_w) <= v.tol()
	return false

func progress(i: int) -> String:
	var v := vest()
	if (i == 1 or i == 6) and v.ramping:
		return "drum %.3f rad/s" % v.drum_w
	return ""

func result(i: int) -> String:
	var v := vest()
	match i:
		1: return "Drum at %.4f rad/s, ring A at %.4f rad/s (match within %.4f)" % [v.drum_w, ring_w(), v.tol()]
		3: return "Ring side open; stationary side closed"
		4:
			var why := str(v.log.filter(func(e): return e["action"] == "handoff")[-1]["reason"])
			return (why.left(1).to_upper() + why.substr(1)).left(150)
		6: return "Drum back at %.4f rad/s; ready for the next passage" % v.drum_w
	return ""

func keys(i: int) -> Array:
	var v := vest()
	if v.ramping:
		return [["(wait)", "the drum is changing speed", "now"], [WfInput.label("ui.cancel"), "release the mouse, again for the menu", "exit"]]
	var what := ["restrain", "start the drum sync", "equalize pressure", "open the ring side", "hand over", "close the ring side", "sync back to stationary"]
	return [[WfInput.label("lab.vestibule"), what[i], "next"], ["Mouse", "look around (click to capture)", "now"], [WfInput.label("ui.cancel"), "release the mouse, again for the menu", "exit"]]

func on_key(keycode: int, i: int) -> Array:
	if keycode == KEY_V and vest().ramping:
		return ["The drum is still changing speed: wait until it matches, then press V.", false]
	if keycode == KEY_V and i == 3:
		var g := vest().gate("RING", ring_w())
		if not g["open"]:
			return ["Ring side stays shut: %s." % g["reason"], false]
	return []

func labels(i: int) -> Array:
	var d: Dictionary = host.dyn
	var vb: Dictionary = d["vestibule"]
	match i:
		0: return [[d["canon_status"], "handoff rules (%s)" % d["source_ref"]], ["PROTOTYPE", "drum seat pose from the rig's access line"]]
		1: return [["OPEN", vb["sync_cycle"]["reason"]], ["PROTOTYPE", "4 s presentation ramp"], ["DERIVED", "match tolerance %s rpm" % vb["match_tol_rpm"]]]
		2: return [["OPEN", vb["dp_threshold"]["reason"]]]
		3: return [[d["canon_status"], "never both open; open only the matched side"]]
		4: return [[d["canon_status"], "frame transform w x r (DYN-027)"], ["PROTOTYPE", "restraint pose (rig access line)"]]
		5: return [[d["canon_status"], "both closures closed before any ramp"]]
		6: return [["OPEN", vb["sync_cycle"]["reason"]], ["PROTOTYPE", "4 s presentation ramp"]]
	return []

func details() -> String:
	return host.hud.text.strip_edges()
