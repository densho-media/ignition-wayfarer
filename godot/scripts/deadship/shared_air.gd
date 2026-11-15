class_name WfSharedAir
extends RefCounted
## Deadship DS-2B "Shared Air" (Phase 2B, `#interior-shared-air` / `-- --shared-air`): the second training, unscored, on the walk's ring
## start (simulated COAST). The scenario layer only, the runtime copy of src/wayfarer/shared_air.py: it reads its definition and reference
## cases from the package (wf_deadship_ds2.json), drives ring A's two-gas air model (WfRingAir, SYS-002 v2) through its public operations,
## and owns no gas equation. The walk's CIRC doors stay the only door state (the model is told what their leaves do); the ECLSS bay's
## controls, the containment at hygiene A and the crew's orders are the trainee's own requests, refused with a reason when they cannot be
## done. The machine on its fixed 10 s step is the module's, in the same order: the walks, a completed containment, the occupants, the
## model's step, each person's exposure from the model's exact integral. Before anyone sees it, a packaged reference case must replay here
## to the packaged checkpoints.
##
## Interaction (no new action, the player's own bindings and touch buttons): Ops at hygiene A starts or pauses the containment work; Use
## there inspects the store. Use at the sector 3 ECLSS bay opens its control page and moves down it; Ops operates the selected control.
## Ops anywhere else on ring A opens the intercom (map layer, orders to the pairs, the crew report, the recovery plan, the watch); Use moves
## down it. After the run Use pages through the debrief and Ops replays.

const FILE := "res://generated/wf_deadship_ds2.json"
const H := 3600.0
const EPS := 1e-6
const SECTORS := ["A1", "A2", "A3"]
const MAX_STEPS := 40                  # model steps per frame, live or watch (a long frame drops the backlog: display time only)
const MAX_PROJECTION := 20             # projection steps per frame
const BAY := ["vent", "A1P", "A1N", "AC1", "AC3", "A2N", "A2P", "A3N", "A3P", "AC2", "reconnect", "removal", "tcc", "intercom", "close"]
const DEB_PAGES := 4
const NP := 6

var doc := {}
var sc := {}
var host: Node = null
var eq: WfAirflow = null
var ring: WfRingAir = null
var verified := false
var errors: Array = []
var notes := {}

# ---- the run (shared_air.Run) -----------------------------------------------------------------------------------------------------------
var p := {}
var ids: Array = []
var N := 0
var dtv := 10.0
var pdt := 300.0
var T := 40.0
var doorway := 10.0
var reuse := 3.0
var people: Array = []
var ts := PackedFloat64Array()        # the sample times (every person samples together)
var es := PackedFloat64Array()        # each person's exposure at each sample, NP per sample (ppm s)
var contain := {}
var phase := "LIVE"                   # LIVE, WATCH, PROJECTION, DONE
var plan := "NONE"
var schedule = null                    # the declared duct reconnection: {"t_s", "done"} (shared_air.Run.schedule)
var co2_peak := 0.0                    # the highest CO2 mole fraction where anybody was (live and watch), and when
var co2_peak_t := 0.0
var watch := {}
var log: Array = []
var alerted := false
var co2_cross = null
var over_last := {}

# ---- the play ---------------------------------------------------------------------------------------------------------------------------
var acc := 0.0
var real_s := 0.0
var runs := 0
var page := ""                        # "", hygiene, bay, intercom, report, debrief
var sel := 0
var layer := "NH3"
var deb_page := 0
var flags := {}
var doors_seen := {}
var report_cache := {}
var debrief_cache := {}
var frame_cost := {"live_us": 0, "watch_us": 0, "projection_us": 0, "max_frame_us": 0}

var panel := PanelContainer.new()
var text := RichTextLabel.new()
var rendered_compact := false

func _init(by_name: Dictionary, manifest: Dictionary, owner: Node, ui_layer: CanvasLayer) -> void:
	host = owner
	if not FileAccess.file_exists(FILE):
		errors = ["%s is not in the package; run runtime-export" % FILE]
		return
	doc = JSON.parse_string(FileAccess.get_file_as_string(FILE))
	sc = doc["scenario"]
	eq = WfAirflow.new(by_name, manifest, owner)
	ring = eq.ring
	if ring == null or not eq.ready():
		errors = ["the ring A air model is missing or does not reproduce its reference: %s" % (str(ring.errors) if ring != null else "no package")]
		return
	if int(doc["model"]["version"]) != int(ring.doc["version"]) or str(doc["model"]["schema"]) != str(ring.doc["schema"]):
		errors = ["scenario built for model %s v%s, package has %s v%s" % [doc["model"]["schema"], doc["model"]["version"], ring.doc["schema"], ring.doc["version"]]]
		return
	var src: Dictionary = sc["source"]
	if not eq.add_point("hygiene", str(src["node"]), float(src["reach_m"]), str(eq.points["bay"]["ring"])):
		errors = ["the hygiene A node %s is not in the package" % src["node"]]
		return
	p = ring.p
	ids = ring.ids
	N = ring.N
	dtv = float(sc["time"]["dt_s"])
	pdt = float(sc["time"]["projection_dt_s"])
	T = float(sc["crew"]["transit_s"])
	doorway = float(sc["crew"]["doorway_s"])
	reuse = float(sc["reuse"]["ppm"])
	var t0 := Time.get_ticks_usec()
	errors = verify_at_load()
	notes["verify_ms"] = (Time.get_ticks_usec() - t0) / 1000.0
	verified = errors.is_empty()
	_build_ui(ui_layer)
	if verified:
		begin()

# =========================================================================================================================================
# The machine (src/wayfarer/shared_air.py Run, line for line)
# =========================================================================================================================================

func begin_run() -> void:
	ring.reset()
	people = []
	for pr in sc["crew"]["pairs"]:
		for k in [1, 2]:
			var h := ring.index(str(pr[1]))
			people.append({"id": "%s-%d" % [pr[0], k], "pair": str(pr[0]), "home": h, "node": h, "route": [], "next_t": 0.0,
				"places": [[0.0, h]], "E": 0.0, "mark": 0.0, "peak": 0.0, "co2_s": 0.0, "max1h": 0.0, "j": 0, "max24": 0.0, "j24": 0})
	ts = PackedFloat64Array([0.0])
	es = PackedFloat64Array()
	es.resize(NP)
	es.fill(0.0)
	contain = {"state": "NONE", "progress_s": 0.0}
	phase = "LIVE"
	plan = "NONE"
	schedule = null
	co2_peak = 0.0
	co2_peak_t = 0.0
	watch = {}
	log = []
	alerted = false
	co2_cross = null
	over_last = {}
	for k in ids:
		over_last[k] = null
	_occupy()
	var src: Dictionary = sc["source"]
	ring.set_source(str(src["compartment"]), float(src["inventory_kg"]), float(src["tau_s"]))

func t() -> float:
	return ring.t_s

func xp(i: int) -> float:
	return float(ring.I[i]) / float(p["M_NH3"]) / ring.n_mol(i) * 1e6

func _occupy() -> void:
	var occ := []
	for i in N:
		occ.append(0)
	for q in people:
		occ[int(q["node"])] += 1
	ring.set_occupants(occ)

func _place(q: Dictionary, node: int) -> void:
	if node != int(q["node"]):
		q["node"] = node
		q["places"].append([t(), node])
		q["mark"] = xp(node)

func sealed(door: String) -> bool:
	var imv := "IMV." + door.get_slice(".", 1)
	return not bool(ring.open[door]) and ring.open.has(imv) and not bool(ring.open[imv])

## The shortest door route crossing no sealed bulkhead (breadth first, the edges' own order), or [] when every way is sealed.
func route(frm: int, to: int) -> Array:
	if frm == to:
		return [frm]
	var adj := []
	for i in N:
		adj.append([])
	for e in ring.edges:
		if str(e["kind"]) == "door" and not sealed(str(e["id"])):
			adj[int(e["i"])].append(int(e["j"]))
			adj[int(e["j"])].append(int(e["i"]))
	var prev := {frm: -1}
	var qq := [frm]
	while not qq.is_empty():
		var c: int = qq.pop_front()
		for n in adj[c]:
			if not prev.has(n):
				prev[n] = c
				qq.append(n)
	if not prev.has(to):
		return []
	var path := [to]
	while int(prev[path[-1]]) != -1:
		path.append(prev[path[-1]])
	path.reverse()
	return path

func door_between(a: int, b: int) -> String:
	for e in ring.edges:
		if str(e["kind"]) == "door" and ((int(e["i"]) == a and int(e["j"]) == b) or (int(e["i"]) == b and int(e["j"]) == a)):
			return str(e["id"])
	return ""

func in_doorway(door: String) -> Array:
	var out := []
	for q in people:
		if not (q["route"] as Array).is_empty() and t() >= float(q["next_t"]) - doorway - EPS and door_between(int(q["node"]), int(q["route"][0])) == door:
			out.append(q["id"])
	return out

func members(pair: String) -> Array:
	return people.filter(func(q): return str(q["pair"]) == pair and str(q["id"]) != "A-1")

## One action now: "" when done, else the refusal (the state is then unchanged).
func act(kind: String, a: Array = []) -> String:
	var r := _act(kind, a)
	log.append([t(), kind, a.duplicate(), r])
	return r

func _act(kind: String, a: Array) -> String:
	if phase != "LIVE" and kind != "report":
		return "the watch is running: nothing can be changed now"
	match kind:
		"trainee":
			_place(people[0], ring.index(str(a[0])))
			_occupy()
			if str(contain["state"]) == "WORKING" and int(people[0]["node"]) != ring.index(str(sc["source"]["compartment"])):
				contain["state"] = "PAUSED"
			return ""
		"door":
			var id := str(a[0])
			if not bool(a[1]) and bool(ring.open[id]) and not in_doorway(id).is_empty():
				return "the doorway is occupied by %s" % ", ".join(in_doorway(id))
			ring.set_edge(id, bool(a[1]))
			return ""
		"damper":
			ring.set_edge("IMV." + str(a[0]), bool(a[1]))
			return ""
		"vent":
			ring.set_vent(bool(a[0]))
			return ""
		"tcc":
			ring.set_tcc(bool(a[0]))
			return ""
		"removal":
			ring.set_removal(bool(a[0]))
			return ""
		"order", "hold":
			var pair := str(a[0])
			var ms := members(pair)
			if ms.is_empty():
				return "no pair %s" % pair
			if kind == "hold":
				for q in ms:
					q["route"] = []
				return ""
			var dest := str(a[1])
			if not dest in SECTORS:
				return "%s is not a sector a pair can be sent to" % dest
			var d := ring.index(dest)
			if ms.all(func(q): return int(q["node"]) == d and (q["route"] as Array).is_empty()):
				return "pair %s is already in %s" % [pair, dest]
			var paths := []
			for q in ms:
				paths.append(route(int(q["node"]), d))
			if paths.any(func(pa): return (pa as Array).is_empty()):
				return "pair %s cannot reach %s: every way crosses a sealed bulkhead (door and dampers shut)" % [pair, dest]
			for k in ms.size():
				ms[k]["route"] = (paths[k] as Array).slice(1)
				ms[k]["next_t"] = t() + T
			return ""
		"contain_start":
			var s := str(ring.source["state"])
			if s != "LEAKING":
				return "there is nothing left to contain" if s == "ISOLATED" else "no leak here"
			if int(people[0]["node"]) != ring.index(str(sc["source"]["compartment"])):
				return "the store is in hygiene A: you have to be there"
			contain["state"] = "WORKING"
			return ""
		"contain_stop":
			if str(contain["state"]) == "WORKING":
				contain["state"] = "PAUSED"
			return ""
		"schedule":
			if a[0] == null:
				schedule = null
				return ""
			var tsch := float(a[0])
			if tsch <= t() + EPS:
				return "that time has passed: a reconnection is scheduled ahead of the ship clock"
			if absf(tsch / dtv - roundf(tsch / dtv)) > 1e-9:
				return "a reconnection is scheduled on the %.0f s step" % dtv
			if tsch > float(sc["watch"]["ship_h"]) * H + EPS:
				return "a reconnection is scheduled before the watch ends (%.0f h)" % float(sc["watch"]["ship_h"])
			schedule = {"t_s": tsch, "done": null}
			return ""
		"watch":
			if not str(a[0]) in sc["watch"]["plans"]:
				return "no plan %s" % a[0]
			_start_watch(str(a[0]))
			return ""
		"report":
			return ""
	push_error("shared air: unknown action " + kind)
	return "unknown action " + kind

func _walks() -> void:
	for q in people:
		while not (q["route"] as Array).is_empty() and t() >= float(q["next_t"]) - EPS:
			var door := door_between(int(q["node"]), int(q["route"][0]))
			if sealed(door):
				q["route"] = []
				log.append([t(), "stopped", [q["id"], door], ""])
				break
			_place(q, int((q["route"] as Array).pop_front()))
			q["next_t"] = float(q["next_t"]) + T

## One step: the walks, a completed containment, the occupants, the model, the exposures.
func tick(dt := -1.0) -> void:
	if dt < 0.0:
		dt = dtv
	_scheduled()
	_walks()
	var cs := str(contain["state"])
	if (cs == "WORKING" or cs == "PAUSED") and float(contain["progress_s"]) >= float(sc["containment"]["work_s"]) - EPS:
		ring.isolate_source()
		contain["state"] = "DONE"
		log.append([t(), "contained", [], ""])
	_occupy()
	ring.step(dt)
	if str(contain["state"]) == "WORKING":
		contain["progress_s"] = float(contain["progress_s"]) + dt
	if not alerted and t() >= float(sc["time"]["alert_s"]) - EPS:
		alerted = true
		_on_alert()
	var X := []
	var pp := []
	for i in N:
		X.append(xp(i))
		pp.append(ring.ppm(i))
	var target := float(p["co2_target"])
	ts.append(t())
	for k in NP:
		var q: Dictionary = people[k]
		var n := int(q["node"])
		q["E"] = float(q["E"]) + float(X[n]) - float(q["mark"])
		q["mark"] = X[n]
		q["peak"] = maxf(float(q["peak"]), float(pp[n]))
		if ring.x(n) > target:
			q["co2_s"] = float(q["co2_s"]) + dt
		es.append(float(q["E"]))
	for k in NP:
		var q: Dictionary = people[k]
		var r1 := _roll(k, H, float(q["max1h"]), int(q["j"]))
		q["max1h"] = r1[0]
		q["j"] = r1[1]
		var r24 := _roll(k, 24.0 * H, float(q["max24"]), int(q["j24"]))
		q["max24"] = r24[0]
		q["j24"] = r24[1]
	if phase == "LIVE" or phase == "WATCH":
		var xo := 0.0
		for q in people:
			xo = maxf(xo, ring.x(int(q["node"])))
		if xo > co2_peak:
			co2_peak = xo
			co2_peak_t = t()
		if co2_cross == null and xo > float(p["co2_max"]):
			co2_cross = t()
	for i in N:
		if float(pp[i]) > reuse:
			over_last[ids[i]] = t()

## The running largest mean over a window w ending at the newest sample (shared_air._roll).
func _roll(k: int, w: float, best: float, j: int) -> Array:
	var n := ts.size() - 1
	var start := ts[n] - w
	var e0 := 0.0
	if start > 0.0:
		while ts[j + 1] <= start + 1e-9:
			j += 1
		if absf(ts[j] - start) < 1e-9:
			e0 = es[j * NP + k]
		else:
			var f := (start - ts[j]) / (ts[j + 1] - ts[j])
			e0 = es[j * NP + k] + f * (es[(j + 1) * NP + k] - es[j * NP + k])
	var m := (es[n * NP + k] - e0) / w
	return [m if m > best else best, j]

## The declared duct reconnection when due (shared_air.Run._scheduled): every IMV damper pair open, the fans on; doors stay as they are.
func _scheduled() -> void:
	if schedule == null or schedule["done"] != null or t() < float(schedule["t_s"]) - EPS:
		return
	var opened := []
	for e in ring.edges:
		if str(e["kind"]) == "imv" and not bool(ring.open[e["id"]]):
			opened.append(str(e["id"]))
	for id in opened:
		ring.set_edge(id, true)
	var fans := ring.vent != "ON"
	ring.set_vent(true)
	schedule["done"] = t()
	log.append([t(), "reconnect", [opened, fans], ""])
	_event("reconnect")
	if phase == "LIVE" or phase == "WATCH":
		_say("Ship T+%s: the scheduled reconnection ran at the ECLSS bay: %s. Doors are as you left them." % [_hm(t()),
			"%d damper pair(s) opened%s" % [opened.size(), ", fans on" if fans else ""] if not opened.is_empty() or fans else "the ducts were already connected"])

func _start_watch(pl: String) -> void:
	plan = pl
	phase = "WATCH"
	if str(contain["state"]) == "WORKING":
		contain["state"] = "PAUSED"
	var end := maxf(float(sc["watch"]["ship_h"]) * H, t() + float(sc["watch"]["min_h"]) * H)
	end = ceilf(end / pdt) * pdt
	watch = {"plan": pl, "t0": t(), "end_s": end, "config": config(), "limit_crossed_at": null, "family": family(),
		"schedule": null if schedule == null else (schedule as Dictionary).duplicate()}

## The end of the watch: the verdict, the declared plan, then the projection (projection_step until DONE).
func finish_watch() -> void:
	watch["verdict"] = verdict()
	if plan == "RESTORE":
		ring.set_vent(true)
		for e in ring.edges:
			if str(e["kind"]) == "imv":
				ring.set_edge(str(e["id"]), true)          # remote equipment only: the doors stay as the trainee left them
		ring.set_tcc(true)
		ring.set_removal(true)
		log.append([t(), "restore", [], ""])
	phase = "PROJECTION"

## One projection step; false once the projection is complete (the phase is then DONE).
func projection_step() -> bool:
	var end := float(sc["watch"]["projection_h"]) * H
	if t() >= end - EPS:
		phase = "DONE"
		return false
	if plan == "RESTORE" and absf(t() / H - roundf(t() / H)) < 1e-9:
		_go_home()
	var walking := people.any(func(q): return not (q["route"] as Array).is_empty())
	var on_grid := absf(t() / pdt - roundf(t() / pdt)) < 1e-9
	tick(dtv if walking or not on_grid else pdt)
	return true

func _go_home() -> void:
	for q in people:
		var path := route(int(q["node"]), int(q["home"]))
		if path.is_empty() or int(q["node"]) == int(q["home"]) or not (q["route"] as Array).is_empty():
			continue
		if path.all(func(n): return ring.ppm(int(n)) <= reuse):
			q["route"] = path.slice(1)
			q["next_t"] = t() + T
			log.append([t(), "home", [q["id"]], ""])

func groups() -> Array:
	return ring.components()

func _group_of(gs: Array, i: int) -> Array:
	for g in gs:
		if i in g:
			return g
	return []

func config() -> Dictionary:
	var dopen := []
	var dshut := []
	for e in ring.edges:
		if str(e["kind"]) == "door" and bool(ring.open[e["id"]]):
			dopen.append(str(e["id"]))
		if str(e["kind"]) == "imv" and not bool(ring.open[e["id"]]):
			dshut.append(str(e["id"]))
	dopen.sort()
	dshut.sort()
	var places := {}
	var walking := {}
	for q in people:
		places[q["id"]] = ids[int(q["node"])]
		if not (q["route"] as Array).is_empty():
			walking[q["id"]] = ids[int(q["route"][-1])]
	return {"doors_open": dopen, "dampers_closed": dshut, "vent": ring.vent, "tcc": ring.tcc, "removal": ring.removal,
		"source": ring.source["state"], "places": places,
		"reconnect_at_s": null if schedule == null or schedule["done"] != null else schedule["t_s"], "walking": walking}

## Which of the gate's families the present configuration belongs to (a description, never a grade).
func family() -> String:
	if str(ring.source["state"]) == "LEAKING":
		return "UNCONTAINED"
	var src := ring.index(str(sc["source"]["compartment"]))
	var tcc := int(p["tcc_node"])
	var gs := groups()
	if not tcc in _group_of(gs, src) or ring.tcc != "ON":
		return "ISOLATE"
	for q in people:
		var n: int = int(q["route"][-1]) if not (q["route"] as Array).is_empty() else int(q["node"])
		if not tcc in _group_of(gs, n):
			return "SEPARATE"
	return "ROUTE"

func verdict() -> Dictionary:
	var gs := groups()
	var unbounded := []
	for g in gs:
		if not people.any(func(q): return int(q["node"]) in g):
			continue
		if not int(p["removal"]) in g or ring.removal != "ON":
			unbounded.append(g.map(func(i): return ids[i]))
	var tcc := int(p["tcc_node"])
	var away := 0.0
	var air := 0.0
	var residue := []
	for g in gs:
		for i in g:
			air += float(ring.c[i])
			if not tcc in g or ring.tcc != "ON":
				away += float(ring.c[i])
				if ring.ppm(i) > reuse:
					residue.append(ids[i])
	var result := "STABLE"
	if str(ring.source["state"]) == "LEAKING":
		result = "NOT_CONTAINED"
	elif co2_cross != null:
		result = "CO2_LIMIT"
	elif not unbounded.is_empty():
		result = "TEMPORARY"
	elif not residue.is_empty():
		result = "STABLE_RESIDUE"
	var mx := 0.0
	var co2s := 0.0
	for q in people:
		mx = maxf(mx, ring.x(int(q["node"])))
		co2s += float(q["co2_s"])
	return {"co2_peak_pct": 100.0 * co2_peak, "co2_peak_h": co2_peak_t / H, "co2_above_target_crew_h": co2s / H,
		"degraded": co2_cross == null and co2s > 0.0, "result": result, "co2_limit_crossed_at_h": null if co2_cross == null else float(co2_cross) / H, "co2_unremoved_groups": unbounded, "nh3_residue": residue,
		"nh3_airborne_g": air * 1000.0, "nh3_away_from_tcc_g": away * 1000.0, "source": ring.source["state"], "t_h": t() / H,
		"max_occupied_co2_pct": 100.0 * mx}

## What was saved and what it cost (shared_air.Run.debrief): every number from the run's own model state and exposure records.
func debrief() -> Dictionary:
	var smac: Dictionary = doc["smac"]
	var span := t()
	var i24 := 0
	for k in ts.size():
		if ts[k] <= 24.0 * H + EPS:
			i24 = k
	var out_p := []
	for k in NP:
		var q: Dictionary = people[k]
		var m24 = float(q["max24"]) if span >= 24.0 * H - EPS else null
		var m7 = float(q["E"]) / span if span >= 7.0 * 24.0 * H - EPS else null
		var over := []
		for row in [["1h", float(q["max1h"]), smac["1h"]], ["24h", m24, smac["24h"]], ["7d", m7, smac["7d"]]]:
			if row[1] != null and float(row[1]) > float(row[2]):
				over.append(row[0])
		var rt := []
		for pl in q["places"]:
			rt.append([snappedf(float(pl[0]) / H, 0.0001), ids[int(pl[1])]])
		out_p.append({"id": q["id"], "pair": q["pair"], "route": rt, "peak_ppm": q["peak"], "max_1h_ppm": q["max1h"], "max_24h_ppm": m24,
			"mean_7d_ppm": m7, "dose_24h_ppm_h": es[i24 * NP + k] / H, "dose_ppm_h": float(q["E"]) / H, "co2_above_target_h": float(q["co2_s"]) / H,
			"over": over})
	var end := ts[ts.size() - 1]
	var clear := {}
	for k in ids:
		var tl = over_last[k]
		clear[k] = 0.0 if tl == null else (null if float(tl) >= end - EPS else float(tl) / H)
	var air := 0.0
	var mx := 0.0
	var mm := 0.0
	var nn := 0.0
	for i in N:
		air += float(ring.c[i])
		mx = maxf(mx, ring.x(i))
		mm += float(ring.m[i])
		nn += ring.n_mol(i)
	var contained = null
	for e in log:
		if str(e[1]) == "contained":
			contained = float(e[0]) / H
			break
	return {"people": out_p, "released_g": ring.released * 1000.0, "retained_g": ring.S * 1000.0, "removed_g": ring.nh3_removed * 1000.0,
		"airborne_g": air * 1000.0, "inventory_g": ring.S0 * 1000.0, "co2_mean_pct": 100.0 * mm / float(p["M_CO2"]) / nn, "co2_max_pct": 100.0 * mx,
		"clear_h": clear, "watch": watch, "plan": plan, "contained_at_h": contained, "co2_peak_pct": 100.0 * co2_peak, "co2_peak_h": co2_peak_t / H,
		"schedule": schedule, "decisions": decisions(), "ledgers": ledgers()}

## What the trainee decided and what the ship did on its own account, in order (shared_air.Run.decisions).
func decisions() -> Array:
	var keep := ["contain_start", "contained", "door", "damper", "vent", "tcc", "removal", "order", "hold", "schedule", "watch", "reconnect",
		"restore", "stopped"]
	var out := []
	for e in log:
		if str(e[1]) in keep and str(e[3]) == "":
			# A reconnection time stepped through several values in a row counts once, as its last value.
			if str(e[1]) == "schedule" and not out.is_empty() and str(out[-1][1]) == "schedule":
				out.pop_back()
			out.append([float(e[0]) / H, str(e[1]), e[2]])
	return out

func release_ledger_error() -> float:
	return (ring.S0 - ring.S) - ring.released

func ledgers() -> Dictionary:
	return {"co2_kg": ring.ledger_error(), "nh3_kg": ring.trace_ledger_error(), "release_kg": release_ledger_error()}

func checkpoint() -> Dictionary:
	var E := []
	var m1 := []
	var m24 := []
	var nodes := []
	var co2 := []
	for q in people:
		E.append(q["E"])
		m1.append(q["max1h"])
		m24.append(q["max24"])
		nodes.append(ids[int(q["node"])])
		co2.append(q["co2_s"])
	return {"t_s": t(), "phase": phase, "m": ring.m.duplicate(), "c": ring.c.duplicate(), "S": ring.S, "released": ring.released,
		"removed": ring.nh3_removed, "E": E, "max1h": m1, "max24": m24, "nodes": nodes, "co2_s": co2, "contain": contain.duplicate()}

# =========================================================================================================================================
# The reference cases (shared_air.play): the same actions at the same ship times give the packaged checkpoints
# =========================================================================================================================================

## Run one packaged case here; `until_s` > 0 stops after that ship time (the load check). Returns the checkpoints taken.
func play(actions: Array, until_s := -1.0) -> Array:
	begin_run()
	var todo := []
	for k in actions.size():
		var a: Array = actions[k]
		todo.append([float(a[0]), k, str(a[1]), a.slice(2)])
	todo.sort_custom(func(u, v): return u[0] < v[0] or (u[0] == v[0] and u[1] < v[1]))     # stable, as Python's sorted
	var cps := [checkpoint()]
	var k := 0
	while phase == "LIVE":
		while k < todo.size() and float(todo[k][0]) <= t() + EPS:
			act(str(todo[k][2]), todo[k][3])
			k += 1
		if phase != "LIVE":
			break
		tick()
		if absf(t() / H - roundf(t() / H)) < 1e-9:
			cps.append(checkpoint())
		if until_s > 0.0 and t() >= until_s - EPS:
			return cps
	while t() < float(watch["end_s"]) - EPS:
		while k < todo.size() and float(todo[k][0]) <= t() + EPS:      # during the watch every action is refused and logged
			act(str(todo[k][2]), todo[k][3])
			k += 1
		tick()
		if absf(t() / H - roundf(t() / H)) < 1e-9:
			cps.append(checkpoint())
		if until_s > 0.0 and t() >= until_s - EPS:
			return cps
	cps.append(checkpoint())
	finish_watch()
	while projection_step():
		pass
	cps.append(checkpoint())
	return cps

func case_named(name: String) -> Dictionary:
	for c in doc["reference"]:
		if str(c["name"]) == name:
			return c
	return {}

## Compare checkpoints with the packaged ones (the model's tolerance on masses, the scenario's on exposures). Returns the differences.
func compare(got: Array, want: Array, label: String) -> Array:
	var bad := []
	var tol: Dictionary = doc["tolerance"]
	var close := func(a: float, b: float, absv: float) -> bool: return absf(a - b) <= absv + float(tol["rel"]) * absf(b)
	if got.size() > want.size():
		return ["%s: %d checkpoints, the package has %d" % [label, got.size(), want.size()]]
	for i in got.size():
		var g: Dictionary = got[i]
		var w: Dictionary = want[i]
		if absf(float(g["t_s"]) - float(w["t_s"])) > 1e-6 or str(g["phase"]) != str(w["phase"]) or g["nodes"] != w["nodes"] or \
				str(g["contain"]["state"]) != str(w["contain"]["state"]):
			bad.append("%s checkpoint %d: t %s %s %s %s, reference t %s %s %s %s" % [label, i, g["t_s"], g["phase"], g["nodes"], g["contain"]["state"],
				w["t_s"], w["phase"], w["nodes"], w["contain"]["state"]])
			break
		for key in ["m", "c"]:
			for j in (w[key] as Array).size():
				if not close.call(float(g[key][j]), float(w[key][j]), float(tol["abs_kg"])):
					bad.append("%s checkpoint %d (t %.0f s): %s[%d] %s, reference %s" % [label, i, float(g["t_s"]), key, j, str(g[key][j]), str(w[key][j])])
		for key in ["S", "released", "removed"]:
			if not close.call(float(g[key]), float(w[key]), float(tol["abs_kg"])):
				bad.append("%s checkpoint %d: %s %s, reference %s" % [label, i, key, str(g[key]), str(w[key])])
		for key in ["E", "max1h", "max24"]:
			for j in NP:
				if not close.call(float(g[key][j]), float(w[key][j]), float(tol["abs_ppm_s"]) / (H if key != "E" else 1.0)):
					bad.append("%s checkpoint %d: %s[%d] %s, reference %s" % [label, i, key, j, str(g[key][j]), str(w[key][j])])
		for j in NP:
			if absf(float(g["co2_s"][j]) - float(w["co2_s"][j])) > 1e-6:
				bad.append("%s checkpoint %d: CO2 time above target [%d] %s s, reference %s" % [label, i, j, g["co2_s"][j], w["co2_s"][j]])
		if bad.size() > 4:
			break
	return bad

## At load: the packaged case named verify_at_load, to its first hours (the full cases replay in the runtime check), then a fresh run.
func verify_at_load() -> Array:
	var c := case_named(str(doc["verify_at_load"]))
	if c.is_empty():
		return ["no reference case %s in the package" % doc["verify_at_load"]]
	var got := play(c["actions"], 3.0 * H)
	var bad := compare(got, c["checkpoints"], str(c["name"]))
	ring.reset()
	return bad

# =========================================================================================================================================
# The play: the walk, the clock, the trainee's requests
# =========================================================================================================================================

func begin() -> void:
	begin_run()
	acc = 0.0
	real_s = 0.0
	runs += 1
	page = ""
	sel = 0
	deb_page = 0
	flags = {}
	report_cache = {}
	debrief_cache = {}
	doors_seen = {}
	_sync_doors()
	_close()
	_event("start")
	eq.update()

func _event(what: String) -> void:
	if host != null and host.has_method("_log"):
		host.call("_log", "shared_air", {"what": what, "ship_s": snappedf(t(), 0.01), "phase": phase})

func _say(s: String) -> void:
	if host != null:
		host.call("say", s)

func _on_alert() -> void:
	_say(str(sc["alert"]["text"]))
	_event("alert")

func on_ring_a() -> bool:
	return host.get("move") == "WALK" and str(host.get("walk_zone")) == "RING_A"

## The trainee's compartment from the body: between which two bulkheads (CIRC door angles, the map's frame) the body stands.
func body_node() -> int:
	return node_at((host.get("actor") as Node3D).global_position)

## The compartment a walk-frame point stands in (the same angles as the map), -1 outside every arc.
func node_at(pos: Vector3) -> int:
	var c: Dictionary = host.get("stages")["circuit"]["RING_A"]
	var ang := {}
	for d in c["doors"]:
		var pd: Vector3 = WfLine.g(d["centre_m"]) - Vector3(c["centre_x_m"], 0, 0)
		ang[d["id"]] = atan2(pd.y, -pd.z)
	var pa: Vector3 = pos - Vector3(c["centre_x_m"], 0, 0)
	var b := atan2(pa.y, -pa.z)
	var ends := {}
	for e in ring.edges:
		if str(e["kind"]) == "door" and ang.has(e["id"]):
			for i in [int(e["i"]), int(e["j"])]:
				if not ends.has(i):
					ends[i] = []
				ends[i].append(float(ang[e["id"]]))
	for i in ends:
		if ends[i].size() != 2:
			continue
		var span := wrapf(float(ends[i][1]) - float(ends[i][0]), -PI, PI)
		var rel := wrapf(b - float(ends[i][0]), -PI, PI)
		if signf(rel) == signf(span) and absf(rel) <= absf(span):
			return int(i)
	return -1

func _at() -> String:
	if host.get("move") != "WALK":
		return ""
	return eq.point_in_reach((host.get("actor") as Node3D).global_position, str(host.get("walk_zone")))

func _hygiene_in_reach() -> bool:
	return eq.in_reach((host.get("actor") as Node3D).global_position, str(host.get("walk_zone")), "hygiene")

## The walk's door leaves -> door actions, in the order they change (the walk is the only door state).
func _sync_doors() -> void:
	var doors = host.get("circ_doors")
	for e in ring.edges:
		if str(e["kind"]) != "door" or not doors.has(e["id"]):
			continue
		var o := float(doors[e["id"]]["value"]) > 0.0
		if not doors_seen.has(e["id"]) or bool(doors_seen[e["id"]]) != o:
			var first := not doors_seen.has(e["id"])
			doors_seen[e["id"]] = o
			ring.set_edge(str(e["id"]), o)
			if not first:
				log.append([t(), "door", [e["id"], o], ""])

## The walk asks before it moves a ring A door leaf ("" allowed): during the watch nothing changes; a pair in the doorway blocks a close.
func door_refusal(id: String, opening: bool) -> String:
	if not verified or ring == null or not ring.open.has(id):
		return ""
	if phase == "WATCH" or phase == "PROJECTION":
		return "Stability watch running: the ring stays as you declared it."
	if not opening:
		var who := in_doorway(id)
		if not who.is_empty():
			return "The doorway is occupied by %s: wait until they are through." % ", ".join(who)
	return ""

func _pause_now() -> bool:
	if phase == "DONE" or page != "" or not on_ring_a():
		return true
	return WfInput.overlay != null and WfInput.overlay.is_modal()

func paused() -> bool:
	return _pause_now()

func scale() -> float:
	return float(sc["time"]["watch_scale"]) if phase == "WATCH" else float(sc["time"]["scale"])

func step(dt: float) -> void:
	if not verified:
		return
	var t0 := Time.get_ticks_usec()
	if phase != "DONE":
		real_s += dt
	_sync_doors()
	if phase == "LIVE" and on_ring_a():
		var n := body_node()
		if n >= 0 and n != int(people[0]["node"]):
			act("trainee", [ids[n]])
		if str(contain["state"]) == "WORKING" and not _hygiene_in_reach():
			act("contain_stop")
			_say("Containment paused: you stepped away from the store. %d of %d ship minutes done; the store keeps releasing until you finish." % [
				int(float(contain["progress_s"]) / 60.0), int(float(sc["containment"]["work_s"]) / 60.0)])
	if page != "" and page != "intercom" and page != "report" and page != "debrief" and _at() != page:
		_close()                                   # a station page closes when the trainee walks away
	eq.paused = _pause_now()
	var kind := "live_us"
	if phase == "PROJECTION":
		kind = "projection_us"
		if not eq.paused or page == "debrief":
			for i in MAX_PROJECTION:
				if not projection_step():
					_finish()
					break
				if Time.get_ticks_usec() - t0 > 6000:
					break                          # a frame budget: a propagator rebuild (a person arriving) costs about 6 ms
	elif not eq.paused:
		if phase == "WATCH":
			kind = "watch_us"
		acc += dt * scale()
		var n := 0
		var was := str(contain["state"])
		var moving := people.map(func(q): return not (q["route"] as Array).is_empty())
		var log_n := log.size()
		while acc >= dtv and n < MAX_STEPS:
			tick()
			acc -= dtv
			n += 1
			if phase == "WATCH" and t() >= float(watch["end_s"]) - EPS:
				_end_watch()
				break
		if n == MAX_STEPS:
			acc = 0.0
		_crew_news(moving, log_n)
		if was != "DONE" and str(contain["state"]) == "DONE":
			_say("CONTAINED: the store is bagged and sealed; it releases nothing more. %.2f g of NH3 are in ring A's air, %.2f g stay in the bag." % [
				_airborne_g(), ring.S * 1000.0])
			_event("contained")
	var us := Time.get_ticks_usec() - t0
	frame_cost[kind] = maxi(int(frame_cost[kind]), us)
	frame_cost["max_frame_us"] = maxi(int(frame_cost["max_frame_us"]), us)
	frame_cost["total_us"] = int(frame_cost.get("total_us", 0)) + us
	frame_cost["frames"] = int(frame_cost.get("frames", 0)) + 1

## Tell the trainee when an ordered pair arrives or stops at a sealed door (the map shows the same: a solid disc, no route line).
func _crew_news(moving: Array, log_n: int) -> void:
	if phase != "LIVE":
		return
	var said := {}
	for e in log.slice(log_n):
		if str(e[1]) == "stopped":
			var pr := str(e[2][0]).get_slice("-", 0)
			if not said.has(pr):
				said[pr] = true
				_say("Intercom: %s stopped in %s: the next bulkhead, %s, is sealed (door and dampers shut)." % [
					"your partner" if pr == "A" else "pair " + pr, ids[int(people.filter(func(q): return str(q["id"]) == str(e[2][0]))[0]["node"])], str(e[2][1]).trim_prefix("CIRC.")])
	for k in NP:
		var q: Dictionary = people[k]
		var pr := str(q["pair"])
		if bool(moving[k]) and (q["route"] as Array).is_empty() and not said.has(pr):
			if people.filter(func(o): return str(o["pair"]) == pr).all(func(o): return (o["route"] as Array).is_empty()):
				said[pr] = true
				_say("Intercom: %s arrived in %s." % ["your partner" if pr == "A" else "pair " + pr, ids[int(q["node"])]])

func _airborne_g() -> float:
	var s := 0.0
	for v in ring.c:
		s += float(v)
	return s * 1000.0

func _start_watch_now() -> String:
	var r := act("watch", [plan])
	if r != "":
		return r
	acc = 0.0
	_close()
	_event("watch start " + plan)
	_say("STABILITY WATCH: the same model runs on from the ring exactly as it is now to %d h after the release (x%d), then the 7-day projection. %s.%s" % [
		int(float(watch["end_s"]) / H), int(sc["time"]["watch_scale"]),
		"Nothing changes on its own" if plan == "NONE" else "At its end the restore plan you declared runs: every damper pair open, fans and both units on, doors as you left them, everyone home once their way is under %.0f ppm" % reuse,
		"" if schedule == null else " · The reconnection you scheduled runs at T+%s." % _hm(float(schedule["t_s"]))])
	return ""

func _end_watch() -> void:
	finish_watch()
	_event("watch end " + str(watch["verdict"]["result"]))
	_say("Watch complete at %d h: %s. The 7-day projection runs now." % [int(t() / H), _verdict_text(str(watch["verdict"]["result"]))])

func _finish() -> void:
	debrief_cache = debrief()
	_event("debrief")
	_say("7-day projection complete: %s. The debrief shows what was saved and what it cost." % _verdict_text(str(watch["verdict"]["result"])))
	page = "debrief"
	deb_page = 0
	_render()

func ended() -> bool:
	return phase == "DONE"

# ---- Use and Ops ------------------------------------------------------------------------------------------------------------------------

## A door (or the ladder) keeps Use when the trainee looks more towards it than towards the station in reach (as DS-1).
func _door_first() -> bool:
	if page != "":
		return false
	var w := str(host.call("_walk_target"))
	if w == "":
		return false
	var at := _at()
	if at == "":
		return true
	var eye: Vector3 = (host.get("actor") as Node3D).global_position
	var fwd: Vector3 = -(host.call("look_basis") as Basis).z
	var to_point := eq.centre(at) - eye
	var to_door: Vector3 = (host.get("lines")["ACCESS_A"].p[-1] if w == "ladder" else (host.get("circ_doors")[w]["collider"] as Node3D).global_position) - eye
	return fwd.angle_to(to_door) < fwd.angle_to(to_point)

func use() -> String:
	if not verified:
		return ""
	if page == "debrief":
		deb_page += 1
		if deb_page > DEB_PAGES - 1:
			_close()
		else:
			_render()
		return "debrief %d" % deb_page
	if ended():
		page = "debrief"
		deb_page = 0
		_render()
		return "debrief 0"
	if page == "report":
		_open("intercom")
		return "intercom"
	if page == "bay" or page == "intercom":
		var n := _items().size()
		sel = (sel + 1) % n
		_render()
		return "select %d" % sel
	if _door_first():
		return ""
	var at := _at()
	if at == "hygiene":
		if page == "hygiene":
			_close()
			return "close"
		flags["inspected"] = true
		_open("hygiene")
		_event("inspect")
		return "inspect"
	if at == "bay":
		_open("bay")
		return "bay"
	return ""

func ops() -> String:
	if not verified or not on_ring_a():
		return ""
	if ended():
		_replay()
		return "replay"
	if page == "debrief" or page == "hygiene":
		_close()
		return "close"
	if page == "report":
		_open("intercom")
		return "intercom"
	if page == "bay" or page == "intercom":
		return _activate(_items()[sel])
	var at := _at()
	if at == "hygiene" and phase == "LIVE" and str(ring.source["state"]) == "LEAKING":
		if str(contain["state"]) == "WORKING":
			act("contain_stop")
			_say("Containment paused: %d of %d ship minutes done (kept)." % [int(float(contain["progress_s"]) / 60.0), int(float(sc["containment"]["work_s"]) / 60.0)])
			return "contain_stop"
		return _contain()
	if at == "bay":
		_open("bay")
		return "bay"
	_open("intercom")
	return "intercom"

## The containment request: refused (and logged) out of the store's reach even inside A1; otherwise the model's own rule.
func _contain() -> String:
	var r := ""
	if not _hygiene_in_reach():
		r = "the store is in hygiene A: you have to be there"
		log.append([t(), "contain_start", [], r])
	else:
		r = act("contain_start")
	if r != "":
		_say("Containment refused: " + r + ".")
		_event("refused contain_start")
		return "refused contain"
	_event("contain_start")
	_say("CONTAINING: bagging the liquid and the absorbent, %d of %d ship minutes done. Stay at the store; it releases at full rate until the last bag is sealed." % [
		int(float(contain["progress_s"]) / 60.0), int(float(sc["containment"]["work_s"]) / 60.0)])
	return "contain_start"

func _replay() -> void:
	begin()
	if host.has_method("training_reset"):
		host.call("training_reset")
	_say("Shared Air restarted from the same start: " + fill(str(sc["stages"][0]["objective"])))

func _open(pg: String) -> void:
	page = pg
	sel = 0
	report_cache = {}
	if pg != "hygiene" and str(ring.source["state"]) == "ISOLATED":
		flags["assessed"] = true
	if alerted:
		flags["looked"] = true
	_render()

func _close() -> void:
	page = ""
	panel.visible = false

# ---- the bay's controls and the intercom --------------------------------------------------------------------------------------------------

func _items() -> Array:
	var out := []
	if page == "bay":
		for b in BAY:
			match b:
				"vent":
					out.append(["vent", "Fans (all intermodule ventilation): %s -> %s" % [ring.vent, "OFF" if ring.vent == "ON" else "ON"]])
				"removal":
					out.append(["removal", "CO2 unit (A3): %s -> %s" % [ring.removal, "OFF" if ring.removal == "ON" else "ON"]])
				"tcc":
					out.append(["tcc", "Trace-contaminant control (TCC, A3): %s -> %s" % [ring.tcc, "OFF" if ring.tcc == "ON" else "ON"]])
				"close":
					out.append(["close", "Close"])
				"intercom":
					out.append(["intercom", "Intercom (orders, crew report, the watch)"])
				"reconnect":
					var nx = _next_reconnect()
					out.append(["reconnect", "Scheduled reconnection: %s -> %s (at that ship time every damper pair opens and the fans run; doors stay as they are)" % [
						_sched_text(), "none" if nx == null else "T+" + _hm(float(nx))], nx])
				_:
					var o := bool(ring.open["IMV." + b])
					var door_open := bool(ring.open["CIRC." + b])
					var what := ""
					if o:
						what = "door open, so air still passes" if door_open else "door shut, so this seals %s" % b
					else:
						what = "unseals %s" % b if not door_open else "the door is open anyway"
					out.append(["damper", "Damper pair %s: %s -> %s · %s" % [b, "open" if o else "shut", "shut" if o else "open", what], b, not o])
		return out
	out.append(["layer", "Map layer: show %s" % ("CO2" if layer == "NH3" else "NH3")])
	if phase == "LIVE":
		for pr in ["A", "B", "C"]:
			var ms := members(pr)
			var at := int(ms[0]["route"][-1]) if not (ms[0]["route"] as Array).is_empty() else int(ms[0]["node"])
			var who := "your partner (A-2)" if pr == "A" else "pair %s" % pr
			for s in SECTORS:
				if ring.index(s) != at:
					out.append(["order", "Send %s to %s" % [who, s], pr, s])
			if not (ms[0]["route"] as Array).is_empty():
				out.append(["hold", "Tell %s to stop where they are" % who, pr])
		if str(ring.source["state"]) == "LEAKING":
			out.append(["contain", "Contain the spill (only at hygiene A)"])
	out.append(["report", "Crew report: places, exposures, CO2"])
	if phase == "LIVE":
		out.append(["plan", "Recovery plan for the watch: %s -> %s" % [plan, "RESTORE" if plan == "NONE" else "NONE"]])
		if alerted:
			out.append(["watch", "Declare the ring set: start the stability watch (plan %s)" % plan])
	out.append(["close", "Close"])
	return out

func _activate(it: Array) -> String:
	var kind := str(it[0])
	var r := ""
	match kind:
		"close":
			_close()
			return "close"
		"intercom":
			_open("intercom")
			return "intercom"
		"reconnect":
			r = act("schedule", [it[2]])
			_say(r if r != "" else ("ECLSS: reconnection cancelled. Sealed groups stay sealed until you change them." if schedule == null else
				"ECLSS: reconnection scheduled at ship T+%s: every damper pair opens and the fans run then, in any phase; doors are never moved remotely. A sealed group's CO2 rises until then (limit %.1f %%)." % [
				_hm(float(schedule["t_s"])), 100.0 * float(p["co2_max"])]))
		"layer":
			layer = "CO2" if layer == "NH3" else "NH3"
			if layer == "NH3" and str(ring.source["state"]) == "ISOLATED":
				flags["assessed"] = true
			_render()
			return "layer " + layer
		"report":
			page = "report"
			report_cache = {}
			flags["assessed"] = flags.get("assessed", false) or str(ring.source["state"]) == "ISOLATED"
			_render()
			return "report"
		"plan":
			plan = "RESTORE" if plan == "NONE" else "NONE"
			_say("Recovery plan: %s. %s" % [plan, "At the end of the watch every damper pair opens, the fans and both units run (doors stay as you left them), and each person walks home once their way is under %.0f ppm (checked hourly). It runs only because you declared it." % reuse
				if plan == "RESTORE" else "The watch changes nothing: the ring stays as you leave it."])
			_render()
			return "plan " + plan
		"watch":
			r = _start_watch_now()
			if r != "":
				_say("Watch refused: " + r)
			return "watch"
		"contain":
			return _contain()
		"vent":
			r = act("vent", [ring.vent != "ON"])
			_say(r if r != "" else "ECLSS: intermodule fans %s. %s" % [ring.vent, "Each bulkhead's open damper pair exchanges air again." if ring.vent == "ON" else "Only open doors join compartments now."])
		"removal":
			r = act("removal", [ring.removal != "ON"])
			_say(r if r != "" else "ECLSS: CO2 unit %s." % ring.removal)
		"tcc":
			r = act("tcc", [ring.tcc != "ON"])
			_say(r if r != "" else "ECLSS: trace-contaminant control %s. %s" % [ring.tcc, "It removes NH3 from the air that reaches sector 3." if ring.tcc == "ON" else "Nothing removes NH3 now."])
		"damper":
			r = act("damper", [it[2], it[3]])
			_say(r if r != "" else "ECLSS: damper pair %s %s.%s" % [it[2], "open" if it[3] else "shut", "  Bulkhead %s is now sealed (door and dampers shut)." % it[2] if sealed("CIRC." + str(it[2])) else ""])
		"order", "hold":
			var a := [it[2]] if kind == "hold" else [it[2], it[3]]
			r = act(kind, a)
			var who := "Your partner" if str(it[2]) == "A" else "Pair %s" % it[2]
			if r != "":
				_say("Intercom: refused, %s." % r)
			elif kind == "hold":
				_say("Intercom: %s stops and waits where they are." % who)
			else:
				var path := members(str(it[2]))[0]["route"] as Array
				_say("Intercom: %s on the way to %s, %d compartment%s (%d ship min)." % [who, it[3], path.size(), "" if path.size() == 1 else "s",
					int(ceilf(path.size() * T / 60.0))])
	if r != "":
		_event("refused " + kind)
	else:
		_event(kind + " " + str(it.slice(2)))
	sel = mini(sel, _items().size() - 1)
	_render()
	eq.update()
	return kind if r == "" else "refused " + kind

# ---- text ---------------------------------------------------------------------------------------------------------------------------------

## The next reconnection time an Ops press would set (the options after the present one and after now; null = cancel).
func _next_reconnect():
	var cur := -1.0 if schedule == null or schedule["done"] != null else float(schedule["t_s"])
	for h in sc["watch"]["reconnect_options_h"]:
		var tsch := float(h) * H
		if tsch > maxf(cur, t()) + EPS:
			return tsch
	return null

func _sched_text() -> String:
	if schedule == null:
		return "none"
	return ("ran at T+%s" if schedule["done"] != null else "T+%s") % _hm(float(schedule["t_s"]) if schedule["done"] == null else float(schedule["done"]))

func _hm(s: float) -> String:
	var mins := int(floor(s / 60.0))
	return "%d:%02d" % [mins / 60, mins % 60]

func fill(s: String) -> String:
	var use_k: String = host.call("key", "exc.use") if host != null else "Use"
	var ops_k: String = host.call("key", "exc.ops") if host != null else "Ops"
	var map_k: String = host.call("key", "exc.map") if host != null else "Map"
	return s.format({"use": use_k, "ops": ops_k, "map": map_k, "work_min": "%d" % int(float(sc["containment"]["work_s"]) / 60.0),
		"nh3_g": "%.2f" % _airborne_g(), "watch_h": "%d" % int(float(sc["watch"]["ship_h"]))})

func stage() -> int:
	if phase == "DONE":
		return 6
	if phase != "LIVE":
		return 5
	if not alerted or not flags.get("looked", false):
		return 0
	var s := str(ring.source["state"])
	if s == "LEAKING":
		return 2 if flags.get("inspected", false) else 1
	if not flags.get("assessed", false):
		return 3
	return 4

func _verdict_text(v: String) -> String:
	return {"STABLE": "stable under the stated assumptions (every occupied group has CO2 removal, the source is contained)",
		"STABLE_RESIDUE": "CO2 stable, but NH3 above the reuse criterion is held where nothing removes it (it stays until it is joined to the TCC)",
		"TEMPORARY": "temporary: an occupied group has no CO2 removal, so its CO2 keeps rising",
		"CO2_LIMIT": "the CO2 control limit was passed where people were", "NOT_CONTAINED": "not contained: the store is still releasing"}.get(v, v)

func _clock() -> String:
	return "ship T+%s (x%d%s) · real %s" % [_hm(t()), int(scale()), ", paused" if paused() and phase != "DONE" else "", _hm(real_s)]

func goal_text() -> String:
	if not verified:
		return "DEADSHIP TRAINING unavailable: " + (str(errors[0]) if not errors.is_empty() else "")
	var head := "DEADSHIP TRAINING · %s %s (simulation, unscored)" % [sc["scenario"]["id"], sc["scenario"]["name"]]
	var st: Dictionary = sc["stages"][stage()]
	if phase == "WATCH":
		return "%s · Verify: stability watch, ship T+%s of %d h (x%d), plan %s%s · real %s" % [head, _hm(t()), int(float(watch["end_s"]) / H),
			int(scale()), plan, "" if schedule == null else " · reconnection %s T+%s" % ["ran at" if schedule["done"] != null else "scheduled at", _hm(float(schedule["t_s"]))], _hm(real_s)]
	if phase == "PROJECTION":
		return "%s · Verify: 7-day projection, computed ahead, ship T+%.0f of %d h · real %s" % [head, t() / H, int(sc["watch"]["projection_h"]), _hm(real_s)]
	if phase == "DONE":
		return "%s · Debrief: %s · %s" % [head, _verdict_text(str(watch["verdict"]["result"])), fill(str(sc["debrief"]["replay"]))]
	if not alerted:
		return "%s · Routine shift in sector 1 · %s" % [head, _clock()]
	var work := ""
	if str(contain["state"]) in ["WORKING", "PAUSED"]:
		work = " · containment %s %d/%d min" % [str(contain["state"]).to_lower(), int(float(contain["progress_s"]) / 60.0), int(float(sc["containment"]["work_s"]) / 60.0)]
	return "%s · Stage %d of 7 · %s: %s%s · %s" % [head, stage() + 1, st["title"], fill(str(st["objective"])), work, _clock()]

func lines() -> Array:
	var out := []
	for i in 7:
		var st: Dictionary = sc["stages"][i]
		out.append("%s %d %s" % ["[x]" if i < stage() else ("[>]" if i == stage() else "[ ]"), i + 1, st["title"]])
	var src := str(ring.source["state"])
	out.append("Source %s · %.2f g left · %.2f g in the air" % [src, ring.S * 1000.0, _airborne_g()])
	if alerted and phase == "LIVE":
		out.append("Hint: " + fill(str(sc["stages"][stage()]["hint"])))
	return out

## The HUD prompt line at a station ("" none).
func prompt() -> String:
	var at := _at()
	if at == "hygiene":
		return "%s inspect the store  ·  %s %s" % [host.call("key", "exc.use"), host.call("key", "exc.ops"), ops_label().trim_prefix("Ops · ")]
	if at == "bay":
		return "%s ECLSS controls" % host.call("key", "exc.use")
	return ""

func use_label() -> String:
	if not verified:
		return ""
	if page == "debrief":
		return "Use · next page" if deb_page < DEB_PAGES - 1 else "Use · close"
	if ended():
		return "Use · debrief"
	if page == "bay" or page == "intercom":
		return "Use · next item"
	if page == "report":
		return "Use · back"
	if _door_first():
		return ""
	var at := _at()
	if at == "hygiene":
		return "Use · close" if page == "hygiene" else "Use · inspect store"
	if at == "bay":
		return "Use · ECLSS controls"
	return ""

func ops_label() -> String:
	if not verified or not on_ring_a():
		return ""
	if ended():
		return "Ops · replay"
	if page == "debrief" or page == "hygiene":
		return "Ops · close"
	if page == "report":
		return "Ops · back"
	if page == "bay" or page == "intercom":
		var it: Array = _items()[sel]
		return "Ops · " + ("close" if it[0] == "close" else str(it[1]).get_slice(":", 0).left(34))
	var at := _at()
	if at == "hygiene" and phase == "LIVE" and str(ring.source["state"]) == "LEAKING":
		return "Ops · pause containment" if str(contain["state"]) == "WORKING" else ("Ops · resume containment" if str(contain["state"]) == "PAUSED" else "Ops · contain spill")
	if at == "bay":
		return "Ops · ECLSS controls"
	return "Ops · intercom"

## The bay's board: a short diegetic summary of both gases and the ring's state (detail on the page).
func board_text() -> String:
	if not verified:
		return "RING A AIR\nSHARED AIR UNAVAILABLE\n" + (str(errors[0]).left(40) if not errors.is_empty() else "")
	var co2_max := 0.0
	var co2_at := ""
	var nh3_max := 0.0
	var nh3_at := ""
	for i in N:
		if ring.x(i) > co2_max:
			co2_max = ring.x(i)
			co2_at = ids[i]
		if ring.ppm(i) > nh3_max:
			nh3_max = ring.ppm(i)
			nh3_at = ids[i]
	var shut := []
	for e in ring.edges:
		if str(e["kind"]) == "imv" and not bool(ring.open[e["id"]]):
			shut.append(str(e["id"]).trim_prefix("IMV."))
	return "RING A AIR · SIM x%d%s\nCO2 max %.2f %% %s · unit %s\nNH3 max %.1f ppm %s · TCC %s\nfans %s · shut %s\nsource %s · %.1f g left\n%d group%s · doors open %d/9" % [
		int(scale()), " (paused)" if paused() else "", 100.0 * co2_max, co2_at, ring.removal, nh3_max, nh3_at, ring.tcc, ring.vent,
		" ".join(shut) if not shut.is_empty() else "none", str(ring.source["state"]), ring.S * 1000.0, groups().size(),
		"" if groups().size() == 1 else "s", eq.open_doors()]

# ---- pages ---------------------------------------------------------------------------------------------------------------------------------

func _build_ui(ui_layer: CanvasLayer) -> void:
	var back := StyleBoxFlat.new()                 # the learning stations' panel look (WfLearning, DS-1)
	back.bg_color = Color(0.02, 0.04, 0.08, 0.94)
	back.border_color = Color(0.75, 0.55, 0.25)
	back.set_border_width_all(2)
	back.set_content_margin_all(14.0)
	panel.add_theme_stylebox_override("panel", back)
	panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	text.bbcode_enabled = true
	text.fit_content = true
	text.scroll_active = false
	text.mouse_filter = Control.MOUSE_FILTER_IGNORE
	text.custom_minimum_size = Vector2(560, 0)
	text.add_theme_font_size_override("normal_font_size", 15)
	text.add_theme_font_size_override("bold_font_size", 16)
	panel.add_child(text)
	panel.visible = false
	if ui_layer != null:
		ui_layer.add_child(panel)

func _ppm_row(i: int) -> String:
	return "%s %.1f" % [ids[i], ring.ppm(i)]

func _f(v, fmt := "%.1f") -> String:
	return "-" if v == null else fmt % float(v)

func _render() -> void:
	if page == "":
		panel.visible = false
		return
	var small := WfInput.compact()
	var out := []
	var head := "[b]SHARED AIR · %s[/b]" % {"hygiene": "hygiene A", "bay": "sector 3 ECLSS bay", "intercom": "intercom", "report": "crew report",
		"debrief": "debrief %d of %d" % [deb_page + 1, DEB_PAGES]}[page]
	out.append(head + ("" if small else "  [color=#9fb4d0](simulation, unscored · %s)[/color]" % _clock()))
	match page:
		"hygiene":
			var s := str(ring.source["state"])
			out.append("Stored urine, pretreatment failed: the bag split and the hydrolysed urine gives off ammonia.")
			out.append("Store %s · %.2f g NH3 still in it · %.2f g released so far" % [s, ring.S * 1000.0, ring.released * 1000.0])
			out.append("Here (A1): NH3 %.1f ppm · CO2 %.2f %%" % [ring.ppm(ring.index("A1")), 100.0 * ring.x(ring.index("A1"))])
			if s == "LEAKING":
				out.append("Release now %.2f g/h, emptying over about %d min (first order: it never just stops)." % [
					ring.S / float(ring.source["tau_s"]) * H * 1000.0, int(float(ring.source["tau_s"]) / 60.0)])
				out.append("Containment %s · %d of %d ship min done. %s at the store bags it; work done is kept if you step away." % [
					str(contain["state"]).to_lower(), int(float(contain["progress_s"]) / 60.0), int(float(sc["containment"]["work_s"]) / 60.0), host.call("key", "exc.ops")])
			else:
				out.append("Contained: nothing more is released; what the bag holds stays in it.")
		"bay", "intercom":
			if page == "bay":
				var rr: Array = []
				for i in N:
					rr.append("%s %.2f%% %.1fppm" % [ids[i], 100.0 * ring.x(i), ring.ppm(i)])
				out.append("[font_size=12]" + ("  ".join(rr.slice(0, 3)) + "\n" + "  ".join(rr.slice(3, 6)) + "\n" + "  ".join(rr.slice(6, 9))) + "[/font_size]")
				out.append("CO2 unit %s (removes CO2) · TCC %s (removes NH3) · fans %s · %d group%s%s" % [ring.removal, ring.tcc, ring.vent, groups().size(),
					"" if groups().size() == 1 else "s", "" if schedule == null else " · reconnection " + _sched_text()])
				out.append("[color=#9fb4d0][font_size=12]Air crosses a bulkhead through its door if open and its damper pair if open (fans on). A bulkhead is sealed only when both are shut. Doors are worked where they are; dampers, fans and units from here.[/font_size][/color]")
			else:
				out.append("Ring A crew: " + "  ".join(_pair_lines()))
			var items := _items()
			for k in items.size():
				var line := str(items[k][1])
				out.append(("[b][color=#ffd27a]> %s[/color][/b]" if k == sel else "[color=#b8c4d8]  %s[/color]") % line)
			out.append("[color=#9fb4d0]%s next · %s do it[/color]" % [host.call("key", "exc.use"), host.call("key", "exc.ops")])
		"report":
			out.append_array(_report_lines(small))
		"debrief":
			out.append_array(_debrief_lines(small))
	if not small:
		out.append("[font_size=12][color=#8090a0]Engineering model: ring A air by compartment, CO2 and NH3 (src/wayfarer/ring_air.py, SYS-002 v2, PROTOTYPE). Scenario %s (%s): the source, crew, timing and criteria are training values.[/color][/font_size]" % [doc["source"], sc["scenario"]["status"]])
	text.text = "\n".join(out)
	rendered_compact = small
	panel.visible = true
	panel.reset_size()

func _pair_lines() -> Array:
	var out := []
	for pr in ["A", "B", "C"]:
		var ms := people.filter(func(q): return str(q["pair"]) == pr)
		var s := "%s %s" % [pr, ids[int(ms[0]["node"])]] if int(ms[0]["node"]) == int(ms[1]["node"]) else "%s %s/%s" % [pr, ids[int(ms[0]["node"])], ids[int(ms[1]["node"])]]
		for q in ms:
			if not (q["route"] as Array).is_empty():
				s += " -> %s" % ids[int(q["route"][-1])]
				break
		out.append(s)
	return out

## The crew report: the present value, the peak, the completed 1 h window and the running dose; the 24 h and 7 d windows only as
## incomplete or as a labelled hypothetical projection (nothing changing, everybody where they are or going).
func _report_lines(small: bool) -> Array:
	if report_cache.is_empty():
		report_cache = _hypothetical(24.0 * H)
	var smac: Dictionary = doc["smac"]
	var out := []
	var t_h := t() / H
	out.append("[b]%-5s %-10s %7s %6s %7s %8s %6s[/b]" % ["who", "place", "NH3 ppm", "peak", "max 1h", "CO2 %", "CO2>t h"] if not small else "[b]who place NH3 now/peak/1h · CO2[/b]")
	for k in NP:
		var q: Dictionary = people[k]
		var n := int(q["node"])
		var place: String = str(ids[n]) + ("->" + ids[int(q["route"][-1])] if not (q["route"] as Array).is_empty() else "")
		var one_h := "%.1f" % float(q["max1h"]) if t() >= H - EPS else "(<1h)"
		if small:
			out.append("%s %s %.1f/%.1f/%s · %.2f%%" % [q["id"], place, ring.ppm(n), float(q["peak"]), one_h, 100.0 * ring.x(n)])
		else:
			out.append("%-5s %-10s %7.1f %6.1f %7s %8.2f %6.1f" % [q["id"], place, ring.ppm(n), float(q["peak"]), one_h, 100.0 * ring.x(n), float(q["co2_s"]) / H])
	out.append("Measured: now, peak, the largest completed 1 h mean (reference %d ppm). Running dose so far: %s ppm h (ship T+%.1f h)." % [
		int(smac["1h"]), ", ".join(people.map(func(q): return "%s %.1f" % [q["id"], float(q["E"]) / H])), t_h])
	out.append("[color=#ffd27a]HYPOTHETICAL, not measured: if nothing changes for 24 h (everybody where they are or going, every door, duct and unit as now):[/color]")
	out.append("  24 h mean ahead: " + ", ".join(people.map(func(q): return "%s %.1f" % [q["id"], float(report_cache["mean"][q["id"]])])) +
		" ppm (24 h reference %d, 7 d %d)" % [int(smac["24h"]), int(smac["7d"])])
	out.append("  CO2 at 24 h where people are: up to %.2f %% (target %.1f, limit %.1f)" % [100.0 * float(report_cache["co2"]), 100.0 * float(p["co2_target"]), 100.0 * float(p["co2_max"])])
	return out

## A labelled what-if on a copy of the model: the ring held as it is for `span` seconds, each person at their place (or destination).
## Never touches the run.
func _hypothetical(span: float) -> Dictionary:
	var a := _clone()
	var dest := []
	var occ := []
	for i in N:
		occ.append(0)
	for q in people:
		var n: int = int(q["route"][-1]) if not (q["route"] as Array).is_empty() else int(q["node"])
		dest.append(n)
		occ[n] += 1
	a.set_occupants(occ)
	var x0 := []
	for i in N:
		x0.append(float(a.I[i]) / float(p["M_NH3"]) / a.n_mol(i) * 1e6)
	var steps := int(round(span / pdt))
	for k in steps:
		a.step(pdt)
	var mean := {}
	var co2 := 0.0
	for k in NP:
		var n: int = dest[k]
		mean[people[k]["id"]] = (float(a.I[n]) / float(p["M_NH3"]) / a.n_mol(n) * 1e6 - float(x0[n])) / span
		co2 = maxf(co2, a.x(n))
	return {"mean": mean, "co2": co2}

func _clone() -> WfRingAir:
	var a := WfRingAir.new()
	a.doc = ring.doc
	a.p = ring.p
	a.ids = ring.ids
	a.V = ring.V
	a.edges = ring.edges
	a.N = ring.N
	a.verified = ring.verified
	for k in ["t_s", "m0", "generated", "removed", "vent", "removal", "S", "S0", "c0", "released", "nh3_removed", "tcc"]:
		a.set(k, ring.get(k))
	a.m = ring.m.duplicate()
	a.c = ring.c.duplicate()
	a.I = ring.I.duplicate()
	a.occupants = ring.occupants.duplicate()
	a.open = ring.open.duplicate()
	a.source = ring.source.duplicate()
	return a

func _debrief_lines(small: bool) -> Array:
	var d := debrief_cache
	var out := []
	if d.is_empty():
		return ["(the projection is still running)"]
	var v: Dictionary = d["watch"]["verdict"]
	var fam := str(d["watch"]["family"])
	var smac: Dictionary = doc["smac"]
	if deb_page == 0:
		out.append_array(_summary_lines(d, small))
	elif deb_page == 1:
		out.append("[b]The ship · watch to %d h: %s[/b]" % [int(float(d["watch"]["end_s"]) / H), _verdict_text(str(v["result"]))])
		out.append("Your configuration at the watch: %s. Plan: %s%s." % [_family_text(fam), d["plan"],
			" (applied by your declaration at the end of the watch)" if str(d["plan"]) == "RESTORE" else " (nothing changed after you declared)"])
		var cfg: Dictionary = d["watch"]["config"]
		out.append("Doors open: %s · dampers shut: %s · fans %s · CO2 unit %s · TCC %s" % [", ".join(cfg["doors_open"]) if not cfg["doors_open"].is_empty() else "none",
			", ".join((cfg["dampers_closed"] as Array).map(func(s): return str(s).trim_prefix("IMV."))) if not cfg["dampers_closed"].is_empty() else "none", cfg["vent"], cfg["removal"], cfg["tcc"]])
		out.append("NH3: %.2f g in the store, %.2f g released, %.2f g still in the bag, %.2f g captured by the TCC, %.2f g still in the air at 7 days." % [
			float(d["inventory_g"]), float(d["released_g"]), float(d["retained_g"]), float(d["removed_g"]), float(d["airborne_g"])])
		out.append("Contained at %s. CO2 at 7 days: mean %.2f %%, highest %.2f %%%s." % [
			"T+%.2f h" % float(d["contained_at_h"]) if d["contained_at_h"] != null else "no time (never contained)", float(d["co2_mean_pct"]), float(d["co2_max_pct"]),
			"; the 0.5 %% limit was passed at T+%.1f h" % float(v["co2_limit_crossed_at_h"]) if v["co2_limit_crossed_at_h"] != null else ""])
		out.append("CO2 where people were, live and in the watch: highest %.2f %% at T+%s (target %.1f %%, control limit %.1f %%) · %.1f crew-hours above the target." % [
			float(d["co2_peak_pct"]), _hm(float(d["co2_peak_h"]) * H), 100.0 * float(p["co2_target"]), 100.0 * float(p["co2_max"]), float(v["co2_above_target_crew_h"])])
		var clear := []
		for k in ids:
			if str(k).length() == 2 or not small:
				var c = d["clear_h"][k]
				clear.append("%s %s" % [k, "clean" if c != null and float(c) == 0.0 else ("not within 7 d" if c == null else "%.0f h" % float(c))])
		out.append("Back under the %.0f ppm reuse criterion (a conservative training rule, not a NASA clearance): %s" % [reuse, ", ".join(clear)])
	elif deb_page == 2:
		out.append("[b]Crew exposure (NH3, ppm; the 1 h / 24 h / 7 d SMACs are %d / %d / %d, duration references, not injury thresholds)[/b]" % [int(smac["1h"]), int(smac["24h"]), int(smac["7d"])])
		for q in d["people"]:
			var rt := " ".join((q["route"] as Array).map(func(r): return str(r[1])))
			out.append("%s: peak %.1f · max 1 h %s · max 24 h %s · 7 d mean %s · %.1f ppm h · CO2 above target %.1f h%s%s" % [
				q["id"], float(q["peak_ppm"]), _f(q["max_1h_ppm"]), _f(q["max_24h_ppm"]), _f(q["mean_7d_ppm"], "%.2f"), float(q["dose_ppm_h"]),
				float(q["co2_above_target_h"]), " · over: " + ", ".join(q["over"]) if not (q["over"] as Array).is_empty() else "", "" if small else " · " + rt])
		out.append("[color=#9fb4d0]The trainee's (A-1) exposure is where your body was; during the watch and projection the model keeps you where you stood.[/color]")
	else:
		out.append("[b]The same model, the reference strategies (computed, not graded)[/b]")
		var fams: Array = sc["debrief"]["families"]
		for row in [["isolate", 0], ["purge", 1], ["separate_reconnect", 2], ["separate", 3]]:
			var c := case_named(str(row[0]))
			if c.is_empty():
				continue
			var cd: Dictionary = c["debrief"]
			var worst1 := 0.0
			var worst24 := 0.0
			var co2h := 0.0
			for q in cd["people"]:
				worst1 = maxf(worst1, float(q["max_1h_ppm"]))
				worst24 = maxf(worst24, float(q["max_24h_ppm"]) if q["max_24h_ppm"] != null else 0.0)
				co2h += float(q["co2_above_target_h"])
			var a1 = cd["clear_h"]["A1"]
			out.append("· %s" % fams[row[1]])
			out.append("   worst 1 h %.1f ppm · worst 24 h %.1f ppm · CO2 peak %.2f %%, %.0f crew-hours above target · A1 reusable %s · %s" % [worst1, worst24,
				float(cd["co2_peak_pct"]), co2h, "not within 7 d" if a1 == null else "after %.0f h" % float(a1), _verdict_text(str(cd["watch"]["verdict"]["result"])).get_slice(" (", 0)])
		var w1 := 0.0
		var co2y := 0.0
		for q in d["people"]:
			w1 = maxf(w1, float(q["max_1h_ppm"]))
			co2y += float(q["co2_above_target_h"])
		var ya1 = d["clear_h"]["A1"]
		out.append("Yours: worst 1 h %.1f ppm · CO2 peak %.2f %%, %.0f crew-hours above target · A1 reusable %s." % [w1, float(d["co2_peak_pct"]), co2y,
			"not within 7 d" if ya1 == null else "after %.0f h" % float(ya1)])
		out.append("[color=#9fb4d0]%s[/color]" % sc["debrief"]["references"])
		out.append(fill(str(sc["debrief"]["replay"])))
	return out

## Debrief page 1: what happened, what the trainee did, what was saved, what it cost, and whether it holds (numbers from the run).
func _summary_lines(d: Dictionary, small: bool) -> Array:
	var out := []
	var v: Dictionary = d["watch"]["verdict"]
	var smac: Dictionary = doc["smac"]
	var res := str(v["result"])
	var head: String = {"STABLE": "Stable", "STABLE_RESIDUE": "Stable isolation", "TEMPORARY": "Temporary", "CO2_LIMIT": "Operational failure: CO2 control limit",
		"NOT_CONTAINED": "Operational failure: not contained"}.get(res, res)
	if bool(v.get("degraded", false)):
		head += ", with degraded CO2 control"
	out.append("[b]%s.[/b] %s." % [head, _verdict_text(res)])
	if d["contained_at_h"] != null:
		out.append("What happened: hygiene A's store released %.2f g of NH3 before you had it bagged at T+%s; %.2f g stayed in the bag." % [
			float(d["released_g"]), _hm(float(d["contained_at_h"]) * H), float(d["retained_g"])])
	else:
		out.append("What happened: hygiene A's store was never contained and released all %.2f g of NH3." % float(d["released_g"]))
	var did := []
	for e in d["decisions"]:
		var k := str(e[1])
		var a: Array = e[2]
		var w := ""
		match k:
			"contain_start": w = "containment started"
			"contained": w = "contained"
			"order": w = "%s to %s" % ["partner" if str(a[0]) == "A" else "pair " + str(a[0]), a[1]]
			"hold": w = "%s held" % ("partner" if str(a[0]) == "A" else "pair " + str(a[0]))
			"damper": w = "damper %s %s" % [a[0], "open" if a[1] else "shut"]
			"vent": w = "fans %s" % ("on" if a[0] else "off")
			"tcc": w = "TCC %s" % ("on" if a[0] else "off")
			"removal": w = "CO2 unit %s" % ("on" if a[0] else "off")
			"schedule": w = "reconnection cancelled" if a[0] == null else "reconnection set for T+%s" % _hm(float(a[0]))
			"watch": w = "watch declared (plan %s)" % a[0]
			"reconnect": w = "ducts reconnected (scheduled)"
			"restore": w = "restore plan ran"
			"stopped": w = "%s stopped at a sealed door" % a[0]
		if w != "" and (k != "contain_start" or did.is_empty() or not str(did[-1]).ends_with("containment started")):
			did.append("T+%s %s" % [_hm(float(e[0]) * H), w])
	out.append("What you did: " + (" · ".join(did) if not did.is_empty() else "nothing beyond walking") + " (doors as listed on the next page).")
	var clean := []
	for k in ids:
		if d["clear_h"][k] != null and float(d["clear_h"][k]) == 0.0:
			clean.append(k)
	var w1 := 0.0
	var w24 := 0.0
	var w7 := 0.0
	var dose := 0.0
	for q in d["people"]:
		w1 = maxf(w1, float(q["max_1h_ppm"]))
		w24 = maxf(w24, float(q["max_24h_ppm"]) if q["max_24h_ppm"] != null else 0.0)
		w7 = maxf(w7, float(q["mean_7d_ppm"]) if q["mean_7d_ppm"] != null else 0.0)
		dose += float(q["dose_ppm_h"]) / float(d["people"].size())
	var inside := w1 <= float(smac["1h"]) and w24 <= float(smac["24h"]) and w7 <= float(smac["7d"])
	out.append("Saved: %s; the crew %s the NH3 references (worst 1 h %.1f of %d, 24 h %.1f of %d, 7 d %.2f of %d ppm)." % [
		"compartments never above %.0f ppm: %s" % [reuse, ", ".join(clean)] if not clean.is_empty() else "no compartment stayed under %.0f ppm (the ducts carried the NH3 everywhere before the ring was set)" % reuse,
		"stayed inside" if inside else "did not stay inside", w1, int(smac["1h"]), w24, int(smac["24h"]), w7, int(smac["7d"])])
	var a1 = d["clear_h"]["A1"]
	out.append("Sacrificed: sector 1 (A1) out of use %s · CO2 above its %.1f %% target for %.1f crew-hours, peak %.2f %%%s · a mean crew NH3 dose of %.0f ppm h over 7 days." % [
		"for the whole week" if a1 == null else "for %.0f h" % float(a1), 100.0 * float(p["co2_target"]), float(v["co2_above_target_crew_h"]), float(d["co2_peak_pct"]),
		" (over the %.1f %% limit at T+%.1f h)" % [100.0 * float(p["co2_max"]), float(v["co2_limit_crossed_at_h"])] if v["co2_limit_crossed_at_h"] != null else "", dose])
	if not small:
		out.append("[color=#9fb4d0]The 0.3 % CO2 target and 0.5 % control limit are Wayfarer's operating levels (PROTOTYPE), not injury thresholds; the NH3 references are NASA exposure-duration guidelines; the 3 ppm reuse criterion is a training rule. Next pages: the ship, the crew, the alternatives.[/color]")
	return out

func _family_text(f: String) -> String:
	return {"ISOLATE": "sector 1 kept apart from the TCC", "ROUTE": "the residue routed to the TCC through occupied air",
		"SEPARATE": "the purge path joined to the TCC with crew sealed away from it%s" % ("" if watch.get("schedule") == null else ", ducts reconnected at T+%s" % _hm(float(watch["schedule"]["t_s"]))), "UNCONTAINED": "the store still leaking"}.get(f, f)

func update_panel(size: Vector2) -> void:
	if not verified:
		return
	eq.board.text = board_text()
	eq.fit_display()
	if panel.visible and WfInput.compact() != rendered_compact:
		_render()
	WfPagePanel.place(panel, text, size, 560.0)

## The browser / headless record (window.wayfarerWalk.sharedAir).
func record() -> Dictionary:
	if not verified:
		return {"verified": false, "errors": errors.slice(0, 2)}
	var ppl := []
	for q in people:
		ppl.append({"id": q["id"], "node": ids[int(q["node"])], "to": ids[int(q["route"][-1])] if not (q["route"] as Array).is_empty() else "",
			"E_ppm_h": snappedf(float(q["E"]) / H, 1e-6), "peak": snappedf(float(q["peak"]), 1e-4), "max1h": snappedf(float(q["max1h"]), 1e-4)})
	return {"verified": true, "phase": phase, "stage": sc["stages"][stage()]["id"], "t_s": snappedf(t(), 0.01), "real_s": snappedf(real_s, 0.01),
		"paused": paused(), "scale": scale(), "source": ring.source["state"], "S_g": snappedf(ring.S * 1000.0, 1e-6), "airborne_g": snappedf(_airborne_g(), 1e-6),
		"contain": contain, "people": ppl, "page": page, "sel": sel, "layer": layer, "plan": plan, "runs": runs, "vent": ring.vent, "tcc": ring.tcc,
		"removal": ring.removal, "groups": groups().size(), "ledgers": ledgers(), "log": log.slice(-12), "notes": notes, "frame_cost_us": frame_cost,
		"verdict": watch.get("verdict", {}), "family": watch.get("family", ""), "board": eq.board.text}
