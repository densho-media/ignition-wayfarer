class_name WfDemoSession
extends WfReviewSession
## U05: Integrated Demonstrator 01 as a guided review, one step per chapter. A step completes when its chapter's own goal is reached
## (demo01.gd step()) and the run has moved on; the last when its goal is reached. Nothing here moves the body or the camera.

const EXPECT := {
	"EXTERIOR": "The DOCKED ship from outside, slowly orbiting; inspection light, not a sourced sun or attitude.",
	"ENTRY": "The camera rides the review rail through the outer hatch and the airlock into the stationary spine; closures open as it passes.",
	"MICROGRAVITY": "You hold a trunk handrail, weightless. A push sends you drifting at constant speed; you catch the next rail. No thrust, no braking.",
	"MODE": "DOCKED -> COAST in the owner's step order; the rings unlock and spin up (time-lapse ×90). O shows that the sequence holds for an unsecured occupant.",
	"TRANSFER": "Through the spine port into the despun drum, restrained while it syncs with ring A, feet first out through the door to the tube top.",
	"DESCENT": "Hand over hand down the crew tube rungs; the pull grows as you go outward, then you stand on the landing-well deck.",
	"GRAVITY": "Walk into ring A's aisle in spin gravity and drop the object: it lands to one side of straight down (Coriolis).",
	"ARRIVAL": "The camera stands at ring A sector 1's habitat stop with the instructor and newcomer: the end of the M7 production section.",
	"INSPECT": "The production layer switches off and on over the same engineering geometry; the panel lists its six assemblies.",
}
const GOAL := {
	"EXTERIOR": "Look at the docked ship from outside.", "ENTRY": "Ride in through the airlock to the stationary spine.",
	"MICROGRAVITY": "Push off the handrail and catch the next one.", "MODE": "Change the operating mode from DOCKED to COAST.",
	"TRANSFER": "Transfer from the spine into ring A's crew tube through the vestibule drum.", "DESCENT": "Climb down the crew tube to the landing well.",
	"GRAVITY": "Walk in ring A and drop an object.",
	"ARRIVAL": "Arrive in ring A sector 1 (HABITATION).", "INSPECT": "Compare the section with and without its production layer.",
}

var host: Node                               # the boarding scene; host.demo is the chapter run

func _init(h: Node) -> void:
	host = h
	title = "Integrated Demonstrator 01"
	for c in WfDemo01.CHAPTERS:
		steps.append({"title": c.capitalize(), "goal": GOAL[c], "expect": EXPECT[c]})

func demo() -> WfDemo01:
	return host.demo

func done(i: int) -> bool:
	var d := demo()
	return d.chapter > i or (i == WfDemo01.CHAPTERS.size() - 1 and d.chapter == i and d.goal_done)

func progress(i: int) -> String:
	return "goal reached: Enter" if demo().chapter == i and demo().goal_done else ""

func keys(i: int) -> Array:
	var d := demo()
	var exit := [WfInput.label("ui.cancel"), "back to the review menu", "exit"]
	var last := i == WfDemo01.CHAPTERS.size() - 1
	var enter := [WfInput.label("ui.confirm"), "next chapter" if d.goal_done else "skip to the next chapter", "next" if d.goal_done else "now"]
	var auto := [WfInput.label("demo.autoplay"), "autoplay off" if d.autoplay else "autoplay the body actions", "now"]
	var own: Array = []
	match WfDemo01.CHAPTERS[i]:
		"EXTERIOR", "ENTRY": own = [[WfInput.label("demo.pause"), "pause the camera", "now"]]
		"MICROGRAVITY": own = [[WfInput.label("player.grab"), "grab", "now"], [WfInput.label("player.push"), "push off (aim with right-drag)", "now"], auto, [WfInput.label("body.view"), "body view", "now"]]
		"MODE": own = [[WfInput.label("demo.occupants"), "mark an occupant not secured", "now"], [WfInput.label("demo.pause"), "pause", "now"]]
		"TRANSFER": own = [["%s / %s" % WfInput.labels(["player.move_back", "player.move_forward"]), "move along the line", "now"], auto, [WfInput.label("body.view"), "body view", "now"]]
		"DESCENT": own = [["%s / %s" % WfInput.labels(["player.move_back", "player.move_forward"]), "down / up the rungs", "now"], auto, [WfInput.label("body.view"), "body view", "now"]]
		"ARRIVAL": own = [[WfInput.label("demo.pause"), "pause", "now"]]
		"INSPECT": own = [[WfInput.label("demo.pause"), "hold the production layer on", "now"], [WfInput.label("ui.cancel"), "inspector for picking", "now"]]
		"GRAVITY": own = [[" ".join(WfInput.labels(["player.move_forward", "player.move_left", "player.move_back", "player.move_right"])), "walk", "now"], [WfInput.label("body.drop_tool"), "drop the object", "next" if not d.goal_done else "now"], auto]
	return ([] if last else [enter]) + own + [["%s / %s" % WfInput.labels(["ship.map", "ship.card"]), "ship navigator: map / systems card", "now"], exit]

func labels(i: int) -> Array:
	var dyn: Dictionary = host.rig_all.get("dynamics", {})
	var rot: Dictionary = host.rig_all.rotors[0]
	match WfDemo01.CHAPTERS[i]:
		"EXTERIOR": return [["WORKING", "DOCKED configuration"], ["PROTOTYPE", "inspection light and camera orbit"]]
		"ENTRY": return [["CANON", "closure order (Q46, owner 2026-10-07)"], ["PROTOTYPE", "closure display timing"]]
		"MICROGRAVITY": return [["PROTOTYPE", "crew body, push %.1f m/s (DYN-024 test value)" % float(dyn.profiles.human_iva.test_push_dv_m_s)]]
		"MODE": return [[str(dyn.get("canon_status", "WORKING")), "DOCKED -> COAST step order (46 DYN-026)"], ["WORKING", "ramp study value"], ["HOLD", "transition timing"]]
		"TRANSFER": return [[str(dyn.get("canon_status", "WORKING")), "vestibule interlock (46 DYN-027)"], ["OPEN", "drum sync time (MEC-019), pressure threshold"]]
		"DESCENT": return [["PROTOTYPE", "ladder technique and review pace"], ["OPEN", "hand-load limit (measured only)"]]
		"GRAVITY": return [[str(rot.canon_status), "ring spin %s rpm" % rot.rpm], ["DIAGNOSTIC", "Coriolis drop (measured)"]]
		"ARRIVAL": return [["PROTOTYPE", "training route; ring A no certified rescue route (15!A221)"], ["PROTOTYPE", "MPFB pair, not casting (K01)"]]
		"INSPECT": return [["L4_VISUAL_ACCEPTED", "production layer (S&E 48!A23; owner 2026-10-20), not engineering GO"], ["OPEN", "transfer closures (I5/Q46)"]]
	return []

func details() -> String:
	var t: String = demo().hud.text
	var bt: WfBodyTour = host.body_tour
	return (t + ("\n" + bt.hud.text if bt != null and bt.active else "")).strip_edges()
