class_name WfEvaSession
extends WfReviewSession
## U04: the EVA drift review in the EVA scene. Every step completes on the scene's own state (airlock phase and hatches, the 3-D drift body,
## its grip and the two tethers, the tether state after a push); nothing here moves the body. G is a review aid only: it aims the same
## profile push (DYN-024 test value) that Space gives along the view, at the step's target, so nobody has to aim by mouse.

var host: Node                               # the EVA scene (eva.gd)
var rail_anchor := "ANC_AFT_00"              # the first rail anchor aft of the hatch (eva_route); the session's rail target
var pushed_out := false
var caught := false
var refusal_seen := false

func _init(h: Node) -> void:
	host = h
	title = "EVA drift and two tethers"
	steps = [
		{"title": "Suit and buddy check", "goal": "In the study room SP-12 the instructor checks your suit. Move into the airlock SP-11 for the GO check.",
			"expect": "The phase changes to LOCK_CHECK. OPEN values (prebreathe, reserve) would stop a real EVA; this run goes on only as a training simulation."},
		{"title": "Depressurize and open", "goal": "Seal the inner hatch, pump the chamber down and open the outer hatch.",
			"expect": "The inner hatch shuts first (never two doors open to vacuum); after a few seconds the outer hatch opens. Tether A is on the hatch anchor ring."},
		{"title": "Step out", "goal": "Leave the hatch into free drift, holding the hatch anchor.",
			"expect": "You hang outside the forward collar, weightless and at rest relative to the ship; the yellow line is tether A to the hatch."},
		{"title": "Reach the rail", "goal": "Push off along the collar toward the first rail anchor aft of the hatch and grab the rail when it is in reach.",
			"expect": "You drift slowly (0.3 m/s) and never speed up or brake. The H key appears only while a rail anchor or rod is within hand reach."},
		{"title": "Clip tether B", "goal": "Clip your free tether B to the rail anchor next to your hand.",
			"expect": "A second yellow line runs to the rail anchor. Tether B is clipped but UNTESTED."},
		{"title": "Tug-test tether B", "goal": "Tug-test the new tether before you trust it. Try releasing tether A first if you like: it is refused, with the reason.",
			"expect": "Tether B shows tested. Releasing A before the test is refused: \"tether B must be clipped and tested first\"."},
		{"title": "Release tether A", "goal": "Unclip the older tether from the hatch anchor. You are now held only by tether B on the rail.",
			"expect": "The line to the hatch disappears; the live tether count stays at 1, never zero."},
		{"title": "Push off and get caught", "goal": "Push straight out from the rail and let tether B stop you.",
			"expect": "You drift outward until the tether is taut (2.0 m, a PROTOTYPE length), then stop with no outward speed and no rebound."},
		{"title": "Back to the hatch", "goal": "Return to the hatch. Hauling yourself back along the tether is not simulated: this resets to the hatch anchor.",
			"expect": "The drift ends; you are on the rail at the airlock again with tether A on the hatch ring."},
		{"title": "Repressurize", "goal": "Close the outer hatch and bring the chamber back to cabin pressure.",
			"expect": "Outer hatch shut, repressurization, then the inner hatch opens: DEBRIEF."},
	]

func drift() -> WfEvaDrift:
	return host.drift if host.drift != null and host.drift.active else null

func anchor_node() -> WfHandhold:
	var d := drift()
	return d.anchor_hold(rail_anchor) if d != null else null

## The aim of the G push for step i (world direction), or ZERO when G does nothing now.
func aim(i: int) -> Vector3:
	var d := drift()
	if d == null or d.body.grip == null:
		return Vector3.ZERO
	if i == 3:
		var a := anchor_node()
		return Vector3.ZERO if a == null else (a.position + d.out_dir * 0.5) - d.body.global_position
	if i == 7:
		return d.out_dir
	return Vector3.ZERO

func on_rail() -> bool:
	var d := drift()
	return d != null and d.body.grip != null and str(d.body.grip.anchor_id) != "EVA_HATCH_ANCHOR"

func anchor_dist() -> float:
	var d := drift()
	var a := anchor_node()
	return INF if d == null or a == null else d.body.global_position.distance_to(a.anchor_point())

## Holding the rail but the anchor is beyond hand reach (the rail rod was grabbed short of it).
func short_of_anchor() -> bool:
	var d := drift()
	return d != null and d.body.grip != null and on_rail() and anchor_dist() > d.body.reach()

## H on the rail, step 5, short of the anchor: hand over hand along the rail to the anchor. PROTOTYPE: the body is moved to the anchor and
## grips the rail there; the translation itself is not simulated. Returns true when it moved.
func hand_over_hand(i: int) -> bool:
	if i != 4 or not short_of_anchor():
		return false
	var d := drift()
	d.body.release()
	d.body.global_position = anchor_node().anchor_point() + d.out_dir * 0.45
	d.body.linear_velocity = Vector3.ZERO
	d.body.angular_velocity = Vector3.ZERO
	return d.grab()

func can_grab() -> bool:
	var d := drift()
	if d == null or d.body.grip != null:
		return false
	var h := d.body.nearest_reachable(d.holds)
	return h != null and str(h.anchor_id) != "EVA_HATCH_ANCHOR"     # just after the push the hatch is still in reach: that is not the rail

func tick(_dt: float) -> void:
	var d := drift()
	if d == null or not pushed_out or caught:
		return
	var t: WfTether = d.tethers.B
	if t != null and t.state == WfTether.TAUT:
		var out := (d.body.global_position - t.anchor).normalized()
		caught = d.body.linear_velocity.dot(out) <= 1e-3

func done(i: int) -> bool:
	var d := drift()
	match i:
		0: return host.phase != "PREP"
		1: return host.phase == "EXTERIOR" and host.outer_open and not host.inner_open
		2: return d != null
		3: return on_rail()
		4: return d != null and d.tethers.B != null and d.tethers.B.anchor_id != "EVA_HATCH_ANCHOR"
		5: return d != null and d.tethers.B != null and d.tested.B
		6: return d != null and d.tethers.A == null and d.tethers.B != null and d.tested.B
		7: return caught
		8: return d == null and host.phase == "EXTERIOR"
		9: return host.phase == "DEBRIEF"
	return false

func progress(i: int) -> String:
	var d := drift()
	match i:
		1: return "chamber %s" % host.chamber
		3:
			if d != null and d.body.grip == null:
				return "%s %.2f m (hand reach %.1f m)" % [rail_anchor, anchor_dist(), d.body.reach()]
		7:
			if d != null and d.tethers.B != null and pushed_out:
				return "%.2f / %.1f m from the anchor, %s" % [d.body.global_position.distance_to(d.tethers.B.anchor), d.tethers.B.length, d.tethers.B.state]
	return ""

func result(i: int) -> String:
	var d := drift()
	match i:
		3: return "Holding %s; tether A still on the hatch anchor" % d.body.grip.anchor_id if d != null and d.body.grip != null else ""
		4: return "Tether B on %s, UNTESTED; two tethers live" % d.tethers.B.anchor_id if d != null else ""
		6: return "Tether A released; tether B tested on %s, one live tether" % d.tethers.B.anchor_id if d != null else ""
		7:
			if d != null and d.tethers.B != null:
				return "Caught at %.2f m by tether B; outward speed %.3f m/s" % [d.body.global_position.distance_to(d.tethers.B.anchor),
					maxf(0.0, d.body.linear_velocity.dot((d.body.global_position - d.tethers.B.anchor).normalized()))]
	return ""

func keys(i: int) -> Array:
	var exit := [WfInput.label("ui.cancel"), "back to the review menu", "exit"]
	var d := drift()
	match i:
		0: return [[WfInput.label("ui.confirm"), "into the airlock for the GO check", "next"], ["Mouse", "right-drag to look, wheel to zoom", "now"], exit]
		1:
			if host.chamber == "DEPRESSING":
				return [["(wait)", "the chamber is pumping down", "now"], exit]
			return [[WfInput.label("ui.confirm"), "depressurize", "next"], exit]
		2: return [[WfInput.label("eva.drift"), "step out of the hatch", "next"], ["Mouse", "right-drag to look", "now"], exit]
		3:
			if d != null and d.body.grip != null:
				return [[WfInput.label("eva.aimed_push"), "push off toward rail anchor %s" % rail_anchor, "next"], [WfInput.label("eva.drift"), "back to the hatch", "now"], exit]
			if can_grab():
				return [[WfInput.label("eva.grab"), "grab the rail", "next"], exit]
			return [["(drift)", "wait until the rail is in reach", "now"], [WfInput.label("eva.drift"), "back to the hatch", "now"], exit]
		4:
			if short_of_anchor():
				return [[WfInput.label("eva.grab"), "hand over hand to %s (%.2f m away)" % [rail_anchor, anchor_dist()], "next"], exit]
			return [[WfInput.label("eva.clip"), "clip tether B to the rail anchor", "next"], exit]
		5: return [[WfInput.label("eva.tug_test"), "tug-test tether B", "next"], [WfInput.label("eva.release_tether"), "try to release tether A (refused)", "now"], exit]
		6: return [[WfInput.label("eva.release_tether"), "release tether A", "next"], exit]
		7:
			if d != null and d.body.grip != null:
				return [[WfInput.label("eva.aimed_push"), "push straight out from the rail", "next"], exit]
			return [["(drift)", "tether B will stop you", "now"], exit]
		8: return [[WfInput.label("eva.drift"), "back to the hatch", "next"], exit]
		9:
			if host.chamber == "REPRESSING":
				return [["(wait)", "the chamber is filling", "now"], exit]
			return [[WfInput.label("ui.confirm"), "repressurize", "next"], exit]
	return [exit]

func on_key(keycode: int, i: int) -> Array:
	var d := drift()
	if keycode == KEY_R and d != null:
		var old := d.older_tether()
		if old == "":
			return ["R refused: only one tether is clipped. Clip the other first (T).", false]
		var other := "B" if old == "A" else "A"
		if not d.tested[other]:
			refusal_seen = true
			return ["R refused: tether %s is not tug-tested. Press Y first." % other, false]
	if keycode == KEY_T and d != null and d.free_tether() != "" and i == 4 and anchor_dist() > d.body.reach():
		return ["T refused: no rail anchor within hand reach (%s is %.2f m away, reach %.1f m). Press H to go hand over hand to it." % [rail_anchor, anchor_dist(), d.body.reach()], false]
	if keycode == KEY_H and short_of_anchor() and i == 4:
		return ["Hand over hand along the rail to %s: now in reach, press T. (PROTOTYPE: moved there; the translation is not simulated.)" % rail_anchor, true]
	if keycode == KEY_H and d != null and d.body.grip == null and not can_grab():
		return ["H: nothing within hand reach yet.", false]
	if keycode == KEY_G and i in [3, 7] and d != null and d.body.grip == null:
		return ["G: you are drifting; push only works while holding something.", false]
	if keycode == KEY_ENTER and i == 8:
		return ["Enter refused: you are still outside. F returns to the hatch first.", false]
	return []

## G (review aid): push along the step's aim. Returns true when it pushed.
func aimed_push(i: int) -> bool:
	var dir := aim(i)
	var d := drift()
	if d == null or dir.length() < 1e-6:
		return false
	var ok := d.push(dir.normalized())
	if ok and i == 7:
		pushed_out = true
	return ok

func labels(i: int) -> Array:
	var e: Dictionary = host.eva
	var fl: Dictionary = e.get("flight", {})
	var prof: Dictionary = host.rig_dyn["profiles"]["human_suited"]
	match i:
		0: return [["HOLD", "FLIGHT_EVA %s (%s)" % [fl.get("state", "HOLD"), fl.get("lock", "")]], ["OPEN", "prebreathe, reserve and GO values"]]
		1: return [["OPEN", "depress / repress duration (4 s display)"], ["WORKING", "one door at a time interlock"]]
		2: return [["HOLD", "%s: drift at rest relative to the ship (SHIP frame, field 0)" % e.status.airlock], [str(prof.status), "suited body %s kg (suit mass OPEN)" % prof.mass_kg]]
		3: return [["PROTOTYPE", "push %.1f m/s (DYN-024 test value), hand reach %.1f m" % [prof.test_push_dv_m_s, prof.reach_m]], ["PROTOTYPE", "rail rod section (no exterior rail released, 44!51)"]]
		4, 5, 6: return [["WORKING", "two-tether protocol EVA-014: never zero live tethers"], ["HOLD", "anchor and tether ratings"]]
		7: return [["PROTOTYPE", e.tether_reach_status], ["OPEN", "tether stiffness, damping and loads"]]
		8: return [["PROTOTYPE", "haul-in along the tether not simulated (reset)"]]
		9: return [["OPEN", "repress duration"], ["CANON", "cabin 80 kPa (BASELINE)"]]
	return []

func details() -> String:
	return (host.banner.text + "\n" + host.status.text + "\n" + host.hud.text).strip_edges()
