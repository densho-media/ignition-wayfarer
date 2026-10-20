class_name WfRingBSession
extends WfReviewSession
## U02: the Ring B body-mode review in the boarding scene. Every step completes on the body tour's real state: body mode on, the
## RING beat in RING_B, metres actually walked on the deck, a T drop that landed, body mode off. Nothing here moves the body.

const WALK_M := 3.0                          # review choice: enough walking to judge the deck, the walls and the room scale

var host: Node                               # the boarding scene (boarding.gd)
var walked := 0.0
var last_pos := Vector3.INF
var drops_seen := 0
var landed := NAN

func _init(h: Node) -> void:
	host = h
	title = "Ring B in body mode"
	steps = [
		{"title": "Enter body mode", "goal": "Switch from the review camera to the physics body: a crew-sized body that moves only by grabbing, pushing and walking.",
			"expect": "The view jumps into the stationary trunk, weightless, holding a handrail."},
		{"title": "Go to ring B", "goal": "Put the body on the ring B deck, in the B1 rooms. Ring B turns the opposite way to ring A.",
			"expect": "You stand on a deck. The floor is \"down\" (spin gravity) and the ring turns around you; the green box hanging in front of you is a loose tool, held still until you drop it."},
		{"title": "Walk the B1 rooms", "goal": "Walk %.0f m on the deck. Judge the room size against your eye height, and whether walls and the deck hold you." % WALK_M,
			"expect": "The deck stays under your feet, walls stop you, and the rooms read as rooms for people (eye about 1.6 m over the deck)."},
		{"title": "Drop the tool", "goal": "Drop the green tool: T puts it 1 m over the deck beside you and lets it go. Watch where it lands.",
			"expect": "It falls toward the deck and lands clearly to one side of straight down (tens of centimetres from this height): the Coriolis effect, the opposite side to ring A."},
		{"title": "Leave body mode", "goal": "Return to the review camera.",
			"expect": "The physics body disappears and the induction walk camera comes back."},
	]

func tour() -> WfBodyTour:
	return host.body_tour

func in_ring_b() -> bool:
	var t := tour()
	return t != null and t.active and t.beat == "RING" and t.field.zone == "RING_B" and t.actor != null

func tick(_dt: float) -> void:
	if in_ring_b():
		var p: Vector3 = tour().actor.global_position
		if last_pos != Vector3.INF and tour().actor.standing:
			walked += minf(p.distance_to(last_pos), 0.2)     # a rebuild teleport is not walking
		last_pos = p
	else:
		last_pos = Vector3.INF

func done(i: int) -> bool:
	var t := tour()
	match i:
		0: return t != null and t.active
		1: return in_ring_b() and t.actor.standing         # standing: the deck carries it, so the shown field is the floor's
		2: return in_ring_b() and walked >= WALK_M
		3:
			if in_ring_b() and t.drops > 0:
				landed = t.drop_deflection()
				return not is_nan(landed)
			return false
		4: return t != null and not t.active
	return false

## Weightless in the trunk with no hand on a rail: Space has pushed off (Space works only while gripping).
func drifting() -> bool:
	var t := tour()
	return t != null and t.active and t.beat == "SPINE" and t.actor != null and t.actor.grip == null

func progress(i: int) -> String:
	if i == 1 and drifting():
		return "drifting at %.2f m/s, no hand on a rail" % tour().actor.linear_velocity.length()
	if i == 2:
		return "%.1f / %.1f m" % [minf(walked, WALK_M), WALK_M]
	return ""

func result(i: int) -> String:
	match i:
		0: return "Body mode on: weightless in the trunk, gripping a handrail"
		1: return "On the ring B deck, spin gravity %.2f g" % (tour().actor.field_now.length() / float(tour().dyn["standard_gravity_m_s2"]))
		2: return "Walked %.1f m on the ring B deck" % walked
		3:
			var side := "antispinward" if tour().coriolis_text("RING_B", landed).contains("antispinward") else "spinward"
			var fx := tour().fixture("RING_B_CORIOLIS_TANGENTIAL")
			return "Landed %.0f cm %s of straight down (Coriolis %.3f g at 1 m/s, DYN-003)" % [absf(landed) * 100.0, side, fx["expect_g"]]
		4: return "Back on the review camera"
	return ""

func keys(i: int) -> Array:
	var t := tour()
	match i:
		0: return [[WfInput.label("tour.body_mode"), "enter body mode", "next"], [WfInput.label("ui.cancel"), "back to the review menu", "exit"]]
		1:
			var out := [[WfInput.label("body.ring_b"), "go to ring B", "next"], ["Right-drag", "look around", "now"]]
			if drifting():
				if t.actor.nearest_reachable(t.rails) != null:
					out.append([WfInput.label("player.grab"), "grab the rail in reach", "now"])
				out.append([WfInput.label("body.spine"), "back on the start rail", "now"])
			elif t != null and t.actor != null and t.actor.grip != null:
				out.append([WfInput.label("player.push"), "push off along your view (try it)", "now"])
			return out + [[WfInput.label("tour.body_mode"), "leave body mode", "exit"]]
		2: return [[_wasd(), "walk", "next"], ["Right-drag", "look around", "now"], [WfInput.label("body.view"), "view from outside", "now"], [WfInput.label("body.colliders"), "show colliders", "now"],
			[WfInput.label("tour.body_mode"), "leave body mode", "exit"]]
		3: return [[WfInput.label("body.drop_tool"), "drop the tool", "next"], [_wasd(), "walk", "now"], ["Right-drag", "look around", "now"], [WfInput.label("body.view"), "view from outside", "now"],
			[WfInput.label("tour.body_mode"), "leave body mode", "exit"]]
		4: return [[WfInput.label("tour.body_mode"), "leave body mode", "next"], [WfInput.label("body.drop_tool"), "drop again", "now"], [_wasd(), "walk", "now"]]
	return []

func _wasd() -> String:
	return " ".join(WfInput.labels(["player.move_forward", "player.move_left", "player.move_back", "player.move_right"]))

func on_key(keycode: int, i: int) -> Array:
	var t := tour()
	var active := t != null and t.active
	match keycode:
		KEY_SPACE:
			if active and t.beat == "SPINE":
				if t.actor.grip == null:
					return ["%s refused: you are drifting. Push needs a hand on a rail: %s grabs one in reach, 1 puts you back on the start rail." % [WfInput.label("player.push"), WfInput.label("player.grab")], false]
				return ["Pushed off along your view: you drift at constant speed until a rail is in reach (%s) or the trunk's closed end stops you. 1 resets; 3 still goes to ring B." % WfInput.label("player.grab"), true]
		KEY_G:
			if active and t.beat == "SPINE" and t.actor.grip == null:
				if t.actor.nearest_reachable(t.rails) == null:
					return ["%s: no rail within hand reach yet. Keep drifting toward one, or press 1 for the start rail." % WfInput.label("player.grab"), false]
				return ["Grabbed the rail: the drift stops.", true]
		KEY_1:
			if active and i == 1:
				return ["Back on the start rail in the trunk (weightless). Press 3 for ring B.", true]
			if active:
				return ["1 is the stationary trunk (weightless). For this review press 3 for ring B.", false]
		KEY_N:
			if i >= 2 and i < 4 and active:
				return ["Left body mode early. Press N to come back, then 3 for ring B.", false]
		KEY_3:
			if not active:
				return ["3 works only in body mode: press N first.", false]
		KEY_2:
			if active:
				return ["2 is ring A. For this review press 3 for ring B.", false]
		KEY_T:
			if not in_ring_b():
				return ["T drops the tool only on a ring deck: %s" % ("press 3 for ring B." if active else "press N, then 3."), false]
			return ["Tool dropped: watch where it lands.", true]
		KEY_W, KEY_A, KEY_S, KEY_D:
			if i == 2 and not in_ring_b():
				return ["Walking needs the ring deck: press 3 for ring B.", false]
		KEY_V:
			if active:
				return ["View: %s" % ("first person" if t.view_out else "from outside"), true]
		KEY_K:
			if active:
				return ["Colliders toggled: the cyan boxes are what the physics uses (the rig's room boxes)", true]
	return []

func labels(i: int) -> Array:
	var t := tour()
	if t == null or t.rig.is_empty():
		return []
	var rot: Dictionary = t.rig["rotors"][1]
	var rooms: String = str(t.dyn["stages"]["ring_rooms"]["status"]).split(" ")[0]
	var fx := t.fixture("RING_B_CORIOLIS_TANGENTIAL")
	match i:
		0: return [[t.dyn["canon_status"], "crew dynamics (%s)" % t.dyn["source_ref"]], [rooms, "trunk handrails and fixtures"]]
		1: return [[rot["canon_status"], "ring B spin %s rpm, deck r %.0f m" % [rot["rpm"], t.dyn["rings"][1]["floor_radius_m"]]], [rooms, "B1 room boxes"]]
		2: return [[rooms, "B1 room boxes, walls and deck"], [t.dyn["canon_status"], "walking model"]]
		3: return [[str(fx["status"]), "Coriolis expectation %s" % fx["source"]], ["DIAGNOSTIC", "measured landing offset (this run only)"]]
	return []

func details() -> String:
	var t := tour()
	if t != null and t.active:
		return t.hud.text.strip_edges()
	return "Review camera on the induction route (camera study, display sequence). %s" % host.station.text
