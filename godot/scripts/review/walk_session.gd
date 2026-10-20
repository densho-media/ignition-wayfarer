class_name WfWalkSession
extends WfReviewSession
## U05: the induction walk review in the boarding scene. One step per stop group; each completes when the review camera has reached that
## stop on the route rail (the walk's own progress); nothing here moves the camera.

const STOPS := {
	"arrival": "The instructor greets the newcomer in the entry chamber, inside the outer hatch; rings stopped and locked (DOCKED).",
	"spine": "The stationary trunk, weightless; the storm refuge opens off it. The airlock closures cycle as you pass.",
	"transfer": "Ring A's despun transfer drum: it spins up to meet the crew tubes and syncs with the ring before its door opens.",
	"habitat": "The ring A habitat in spin gravity: quarters, hygiene and burn couches; the deck is \"down\".",
	"garden": "Life support and the Garden further round the ring.",
	"burn_station": "The medical station, the operations stations and the aft burn couches with the burn-go consoles.",
}

var host: Node                               # the boarding scene (boarding.gd)
var keys_of: Array = []                      # the stop key per step

func _init(h: Node) -> void:
	host = h
	title = "Induction walk"
	for s in host.route.stops:
		if STOPS.has(s.key):
			keys_of.append(s.key)
			steps.append({"title": str(s.title).get_slice(":", 0), "goal": "Walk on to: %s." % str(s.title).get_slice(":", 1).strip_edges() if ":" in str(s.title) else str(s.title),
				"expect": STOPS[s.key]})

func stop_m(i: int) -> float:
	for s in host.route.stops:
		if s.key == keys_of[i]:
			return float(s.rail_m)
	return INF

func done(i: int) -> bool:
	return host.progress >= stop_m(i) - 0.3 and host.stop_view < 0

func progress(i: int) -> String:
	return "%.1f / %.1f m" % [host.progress, stop_m(i)]

func keys(i: int) -> Array:
	var exit := [WfInput.label("ui.cancel"), "back to the review menu", "exit"]
	if host.stop_view >= 0:
		return [[WfInput.label("player.move_forward"), "back onto the route rail", "next"], [WfInput.label("walk.reset_view"), "reset the view", "now"], exit]
	return [[WfInput.label("player.move_forward"), "hold to walk on", "next"], [WfInput.label("player.move_back"), "back", "now"], ["Right-drag", "look", "now"], [WfInput.label("walk.body_pace"), "body pace" if not host.body_mode else "camera pace", "now"],
		[WfInput.label("walk.light"), "inspection light / S004 look", "now"], exit]

func labels(i: int) -> Array:
	var r: Dictionary = host.route
	var out := [["CANON" if str(r.sequence_status).begins_with("BASELINE") else "WORKING", "operating sequence: %s" % r.sequence_status],
		["PROTOTYPE", "camera study (%s), timings and stop staging" % r.geometry_status]]
	if keys_of[i] in ["transfer", "habitat", "garden"]:
		out.append(["HOLD", "transition timing; drum sync time OPEN (MEC-019)"])
	return out

func details() -> String:
	return "\n".join([host.header.text, host.station.text, host.guide.text, host.passing.text, host.transfer.text, host.body_label.text]).strip_edges()
