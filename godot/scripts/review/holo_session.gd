class_name WfHoloSession
extends WfReviewSession
## M5 (S&E 15!A217): the guided subsystem hologram review. Every step completes on the scene's own state (chapter, isolation,
## cutaway, the picked part, the study layer, then chapter 5's mode, burn and store-and-forward state); the badges are the chapter's owner-row statuses from generated/m5/wf_m5_holo.json.
## M6 (15!A220): then the EYE / shield (eyelids, the shadow test), the habitat (crew walk, stop and lock) and the radiators (damage, isolate).

var host: Node                               # the hologram scene (m5/m5_holo.gd)
var isolated_once := false
var cut_once := false
var studies_off_once := false

func _init(h: Node) -> void:
	host = h
	title = "Subsystem hologram (M5 / M6)"
	steps = [
		{"title": "Fuel against packaging", "goal": "Open chapter 2: the fuel and reaction mass against the BODY-C study packaging.",
			"expect": "He-3 and D2 cryostats and the H2 envelopes in their overlay colours; the panel lists the volume deficits, which stay OPEN."},
		{"title": "Isolate", "goal": "Show only the chapter's parts, then bring the ship back as a faint context.",
			"expect": "Everything else disappears, then returns as a ghost."},
		{"title": "Dorsal cutaway", "goal": "Cut the context away above the spine and restore it.",
			"expect": "The hull and rings lose their dorsal half; the chapter's parts stay whole."},
		{"title": "Inspect a part", "goal": "Click a study part (a cryostat, jacket or shortfall block).",
			"expect": "It turns white; the panel shows its source status (STUDY / NONCANON), its source reference and its note."},
		{"title": "Nozzle load path", "goal": "Open chapter 4: the as-built pickup against the axial bipod study.",
			"expect": "Nozzles, coils, yokes, pickups and the comparison struts; 37.7 MN as built against 1.9 MN per bipod strut."},
		{"title": "Study layer", "goal": "Hide the study parts and show them again.",
			"expect": "The bipods, cryostats and BODY-C envelopes vanish: what stays is the vehicle as built."},
		{"title": "Attitude and comms", "goal": "Open chapter 5: FORWARD_PROTECTED cruise at 30 AU with the aft antennas in contact.",
			"expect": "The white velocity line inside the green 0.2 deg target and the red 2.2 deg shield-shadow limit; green Earth lines from the gimbals."},
		{"title": "Outage", "goal": "Start a burn and let the backlog grow (] speeds the clock).",
			"expect": "Every Earth line turns red: Earth is behind the plume, a planned outage. The on-board backlog counts up; rates stay null."},
		{"title": "Store and forward", "goal": "End the burn and watch the stored data reach Earth one light time later.",
			"expect": "Lines turn green, packets ride the beam, the backlog drains (ILLUSTRATIVE ratio) and Earth receives the outage data after the light time."},
		{"title": "Slew and hold", "goal": "Press the mode key twice: LOW_HAZARD_SLEW, then MAINTENANCE_HOLD.",
			"expect": "The ship turns at 0.05 deg/s with the B1F start / stop jets lit, then returns; in the hold the aft jets show red (inhibited)."},
		{"title": "EYE and shield", "goal": "Open chapter 6 and step the defence poses until the eyelids close.",
			"expect": "The camera moves to the Brow; the eight eyelid leaves slide shut over the four EYE windows (IMPLEMENTATION display pose)."},
		{"title": "Protected shadow", "goal": "Start the dust stream and raise the alignment error until the ship leaves the shadow.",
			"expect": "Dust stops on the Brow; past 2.22 deg the shadow lines turn red: radiator blade 1 is EXPOSED (built-model rays). 0.2 deg is the TARGET."},
		{"title": "Habitat rings", "goal": "Open chapter 7, start the crew walk, then stop and lock the rings.",
			"expect": "The rings counter-rotate at 4 rpm; the marker gains spin gravity in the ring (~0.5 g at the floor); locked, it is 0 g."},
		{"title": "Radiators", "goal": "Open chapter 8, damage cells and isolate them.",
			"expect": "Red cells scatter over all three blades; isolated they go dark and the in-service share drops; heat rejection stays UNKNOWN."},
	]

func done(i: int) -> bool:
	match i:
		0: return host.chapter == 1
		1:
			isolated_once = isolated_once or host.isolated
			return isolated_once and not host.isolated
		2:
			cut_once = cut_once or host.cutaway
			return cut_once and not host.cutaway
		3: return host.selected_mesh != null and host.selected_mesh.get_meta("study")
		4: return host.chapter == 3
		5:
			studies_off_once = studies_off_once or not host.studies_on
			return studies_off_once and host.studies_on
		6: return host.gnc_chapter()
		7: return host.gnc != null and host.gnc.burning and host.gnc.backlog_s() > 3600.0
		8: return host.gnc != null and not host.gnc.burning and host.gnc.last_outage[1] > 0.0 and host.gnc.earth_newest >= host.gnc.last_outage[1] - 1.0
		9: return host.gnc != null and host.gnc.mode == 2
		10: return sim("eye") != null and sim("eye").state_name() == "EYE_SHUTTERS_CLOSED"
		11: return sim("eye") != null and sim("eye").dust_on and sim("eye").exposed()
		12: return sim("habitat") != null and sim("habitat").locked and sim("habitat").walk_m > 0.0
		13: return sim("radiator") != null and sim("radiator").count("ISOLATED") > 0
	return false

## The open M6 chapter's sim when it is of this kind (the step needs its chapter open).
func sim(kind: String) -> WfM6Sim:
	var s: WfM6Sim = host.active_sim()
	return s if s != null and s.m.kind == kind else null

func result(i: int) -> String:
	if i == 8 and host.gnc != null:
		return "Outage data delivered: light time %s, Earth received %s" % [WfM5Gnc.hours(host.gnc.light_s()), WfM5Gnc.hours(host.gnc.received_s)]
	if i == 13 and sim("radiator") != null:
		return "In service %.1f %% of the cell planform (CAD readback); rejection UNKNOWN" % (sim("radiator").service_share() * 100.0)
	if i == 12 and sim("habitat") != null:
		return "Rings locked at an index angle; spin gravity 0 g"
	if i == 3 and host.selected_mesh != null:
		var r: Dictionary = host.info[host.selected_mesh.get_meta("node")].record
		return "Picked %s (%s)" % [r.get("name", "?"), r.get("kind", "?")]
	return ""

func on_key(keycode: int, i: int) -> Array:
	if keycode == KEY_C and i < 2:
		return ["Open a chapter and isolate it first: the cutaway is step 3.", false]
	return []

func keys(i: int) -> Array:
	var exit := [WfInput.label("ui.cancel"), "back to the review menu", "exit"]
	var look := ["Drag", "orbit · shift-drag pan · wheel zoom", "now"]
	match i:
		0: return [[WfInput.label("holo.chapter_2"), "fuel chapter", "next"], [WfInput.label("holo.chapter_1"), "thrust chain", "now"], look, exit]
		1: return [[WfInput.label("holo.isolate"), "isolate / restore", "next"], look, exit]
		2: return [[WfInput.label("holo.cutaway"), "cutaway on / off", "next"], look, exit]
		3: return [["Click", "a study part", "next"], look, exit]
		4: return [[WfInput.label("holo.chapter_4"), "load-path chapter", "next"], look, exit]
		5: return [[WfInput.label("holo.studies"), "study parts off / on", "next"], exit]
		6: return [[WfInput.label("holo.chapter_5"), "attitude and comms", "next"], look, exit]
		7: return [[WfInput.label("holo.burn"), "start a burn", "next"], [WfInput.label("holo.warp_up"), "faster clock", "now"], look, exit]
		8: return [[WfInput.label("holo.burn"), "end the burn", "next"], [WfInput.label("holo.warp_up"), "faster clock", "now"], [WfInput.label("holo.range"), "distance", "now"], exit]
		9: return [[WfInput.label("holo.mode"), "next attitude mode", "next"], [WfInput.label("holo.warp_up"), "faster clock", "now"], exit]
		10: return [[WfInput.label("holo.chapter_6"), "EYE and shield", "now"], [WfInput.label("holo.state"), "next defence pose", "next"], look, exit]
		11: return [[WfInput.label("holo.event"), "dust stream", "now"], [WfInput.label("holo.response"), "alignment error", "next"], look, exit]
		12: return [[WfInput.label("holo.chapter_7"), "habitat", "now"], [WfInput.label("holo.event"), "crew walk", "now"], [WfInput.label("holo.state"), "stop and lock", "next"], exit]
		13: return [[WfInput.label("holo.chapter_8"), "radiators", "now"], [WfInput.label("holo.event"), "damage cells", "now"], [WfInput.label("holo.response"), "isolate", "next"], exit]
	return [exit]

func labels(i: int) -> Array:
	if host.selected_mesh != null and i == 3:
		var r: Dictionary = host.info[host.selected_mesh.get_meta("node")].record
		return [["STUDY", "selected part: %s" % r.get("source_ref", "no source ref")], [str(r.get("geometry_status", "PROTOTYPE")), "its geometry"]]
	if host.chapter >= 0:
		return host.data.chapters[host.chapter].badges.slice(0, 4)
	return [["PROTOTYPE", "REP_PROXY geometry; overlay colours are not materials"]]
