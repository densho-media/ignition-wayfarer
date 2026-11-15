class_name WfShipOps
extends RefCounted
## Deadship ship operations (Phases 2C and 3): DS-2C "Borrowed Air" (`#interior-borrowed-air` / `-- --borrowed-air`) and DS-3 "Dark Bus"
## (`#interior-dark-bus` / `-- --dark-bus`), unscored trainings on the walk's ring start (simulated COAST). The scenario layer only, the
## runtime copy of src/wayfarer/ship_ops.py: it reads its definition and reference cases from the package (wf_deadship_ds2c.json,
## wf_deadship_ds3.json), drives the ring services model (WfRingServices, SYS-003) through its public operations and owns no physical law.
## The machine on its fixed step is the module's, in the same order: the due actions, the trainee's work, the pairs' errands, the
## occupants, the model's step, each person's limit-hours. Before anyone sees it, the model's proof and a packaged reference case must
## replay here to the packaged checkpoints.
##
## Interaction (no new action, the player's own bindings and touch buttons): Use at ring A's sector 3 ECLSS bay opens its page (the
## machines, their parts and the parts shelf), Use at the sector 2 ops console opens the electrical overview and the load switching; on a
## page Use moves down it and Ops does the selected line. Ops anywhere else on ring A opens the intercom (orders to the pairs, the crew
## report, the watch). After the run Use pages through the debrief and Ops replays.

const H := 3600.0
const EPS := 1e-6
const MAX_STEPS := 40
const MAX_PROJECTION := 20
const DEB_PAGES := 4
const BAY_MACHINES := ["CO2", "CHX", "P1", "P2", "HP"]
const BAY_SLOTS := ["CO2.FAN", "CHX.FAN", "P1.PUMP", "P2.PUMP"]
const POWER_ITEMS := ["BUS.A", "BUS.B", "BC-A", "BC-B", "BATTERY", "PACKS", "TIE"]
const VALID_ABOVE_LIMIT_K := 8.0   # the model's valid cabin range (as ship_ops.py): T_min - 8 K .. T_max + 8 K
const VALID_BELOW_LIMIT_K := 8.0
const FILES := {"ds2c": "res://generated/wf_deadship_ds2c.json", "ds3": "res://generated/wf_deadship_ds3.json"}
const TITLES := {"CO2": "CO2 unit", "CHX": "heat exchanger fan", "P1": "coolant pump 1", "P2": "coolant pump 2", "HP": "heat pump",
	"TCC": "trace-contaminant control", "VENT": "ventilation fans", "AV": "avionics, comms", "LIGHT": "cabin lights", "GALLEY": "galley",
	"LAB": "lab and workshop", "GARDEN": "Garden lights"}

var key := "ds2c"
var doc := {}
var sc := {}
var host: Node = null
var eq: WfEquipment = null
var rs: WfRingServices = null
var p := {}
var verified := false
var errors: Array = []
var notes := {}

# ---- the run (ship_ops.Run) ---------------------------------------------------------------------------------------------------------------
var st := {}
var dtv := 10.0
var wdt := 60.0
var pdt := 300.0
var people: Array = []
var extra := {"A": 0, "B": 0}
var later_faults: Array = []
var restart_s = null
var restart = null
var job = null
var hands = null
var phase := "LIVE"
var watch := {}
var log: Array = []
var inspected := {}
var alerted := false
var first_cross := {}
var after24 := {}
var peak := {}
var range_exit = null   # where people live: the first step outside the valid range, with the last valid state
var last_valid := {}
var shed_J := 0.0
var start_parts := {}

# ---- the play -------------------------------------------------------------------------------------------------------------------------------
var acc := 0.0
var real_s := 0.0
var runs := 0
var page := ""                         # "", bay, console, intercom, report, debrief
var sel := 0
var view_ring := "A"
var deb_page := 0
var flags := {}
var debrief_cache := {}
var frame_cost := {"live_us": 0, "watch_us": 0, "projection_us": 0, "max_frame_us": 0}
var panel := PanelContainer.new()
var text := RichTextLabel.new()
var rendered_compact := false

func _init(which: String, by_name: Dictionary, manifest: Dictionary, owner: Node, ui_layer: CanvasLayer) -> void:
	key = which
	host = owner
	var f: String = FILES[key]
	if not FileAccess.file_exists(f):
		errors = ["%s is not in the package; run runtime-export" % f]
		return
	doc = JSON.parse_string(FileAccess.get_file_as_string(f))
	sc = doc["scenario"]
	rs = WfRingServices.load_package()
	if rs == null or not rs.verified:
		errors = ["the ring services model is missing or does not reproduce its proof: %s" % (str(rs.errors.slice(0, 2)) if rs != null else "no package")]
		return
	if int(doc["model"]["version"]) != int(rs.doc["version"]) or str(doc["model"]["schema"]) != str(rs.doc["schema"]):
		errors = ["scenario built for model %s v%s, package has %s v%s" % [doc["model"]["schema"], doc["model"]["version"], rs.doc["schema"], rs.doc["version"]]]
		return
	p = rs.p
	notes["model_verify_ms"] = rs.doc.get("verify_ms", 0.0)
	eq = WfEquipment.new(by_name, manifest, owner)
	if eq.mesh == null:
		errors = ["the ECLSS bay node is not in the package"]
		return
	var pl: Dictionary = sc["places"]
	if not eq.add_point("console", str(pl["console"]["node"]), float(pl["console"]["reach_m"]), "RING_A"):
		errors = ["the ops console node %s is not in the package" % pl["console"]["node"]]
		return
	eq.points["bay"]["reach"] = float(pl["bay"]["reach_m"])
	dtv = float(sc["time"]["dt_s"])
	wdt = float(sc["time"]["watch_dt_s"])
	pdt = float(sc["time"]["projection_dt_s"])
	var t0 := Time.get_ticks_usec()
	errors = verify_at_load()
	notes["verify_ms"] = (Time.get_ticks_usec() - t0) / 1000.0
	verified = errors.is_empty()
	_build_ui(ui_layer)
	if verified:
		begin()

# =========================================================================================================================================
# The machine (src/wayfarer/ship_ops.py Run, line for line)
# =========================================================================================================================================

func begin_run() -> void:
	var pr: Dictionary = sc["premise"]
	people = []
	for pair in sc["crew"]["pairs"]:
		for k in [1, 2]:
			people.append({"id": "%s-%d" % [pair[0], k], "pair": str(pair[0]), "ring": "A", "node": str(pair[1]), "task": null, "crossings": 0,
				"co2_s": 0.0, "hot_s": 0.0, "wet_s": 0.0, "cold_s": 0.0, "band_s": 0.0, "target_s": 0.0})
	var occ := {"A": int(pr["occupants"]["A"]), "B": int(pr["occupants"]["B"])}
	st = rs.start(occ, bool(pr["fusion"]))
	for r in rs.RINGS:
		extra[r] = int(occ[r]) - people.filter(func(q): return str(q["ring"]) == r).size()
	if pr.has("setback"):
		var sb: Dictionary = pr["setback"]
		var r := str(sb["ring"])
		var rr: Dictionary = st["ring"][r]
		rr["T"] = float(sb["T_K"])
		rr["m_w"] = rs.m_w_at(float(rr["T"]), float(sb["rh"]))
		rr["m_c"] = rs.m_c_at(float(rr["T"]), 0.0004)
		st["init"][r] = {"T": rr["T"], "m_w": rr["m_w"], "m_c": rr["m_c"]}
		for e in sb["off"]:
			rr["on"][str(e)] = false
	for f in pr["faults"]:
		if float(f[1]) <= 0.0:
			rs.fail_part(st, str(f[0]))
	later_faults = []
	for f in pr["faults"]:
		if float(f[1]) > 0.0:
			later_faults.append([float(f[1]), str(f[0])])
	later_faults.sort_custom(func(a, b): return float(a[0]) < float(b[0]))
	restart_s = float(pr["restart_h"]) * H if pr.has("restart_h") else null
	restart = null
	job = null
	hands = null
	phase = "LIVE"
	watch = {}
	log = []
	inspected = {}
	alerted = false
	first_cross = {"co2": null, "hot": null, "wet": null, "cold": null}
	after24 = {"co2": null, "hot": null, "wet": null, "cold": null}
	peak = {"co2": 0.0, "T": 0.0, "rh": 0.0}
	range_exit = null
	last_valid = {"A": null, "B": null}
	shed_J = 0.0
	start_parts = {}
	for k in st["parts"]:
		start_parts[k] = str(st["parts"][k]["at"])
	_occupy()

func t() -> float:
	return float(st["t_s"])

func trainee() -> Dictionary:
	return people[0]

func _occupy() -> void:
	var occ := {}
	for r in rs.RINGS:
		occ[r] = int(extra[r]) + people.filter(func(q): return str(q["ring"]) == r).size()
	if int(occ["A"]) != int(st["occ"]["A"]) or int(occ["B"]) != int(st["occ"]["B"]):
		rs.set_occupants(st, occ)

func living(r: String) -> int:
	return int(extra[r]) + people.filter(func(q): return str(q["ring"]) == r and q["task"] == null).size()

func at(place: String) -> bool:
	if not sc["places"].has(place):
		return false
	return str(trainee()["ring"]) == "A" and str(trainee()["node"]) == str(sc["places"][place]["compartment"])

func pair_members(pair: String, what := "") -> Array:
	var ms := people.filter(func(q): return str(q["pair"]) == pair)
	return ms if (pair != "A" or what == "move") else ms.slice(1)

func idle(pair: String) -> bool:
	return pair_members(pair).all(func(q): return q["task"] == null)

static func equipment_of(slot: String) -> String:
	return slot.get_slice(".", 0)

func act(kind: String, a: Array = []) -> String:
	var why := _act(kind, a)
	log.append([t(), kind, a.duplicate(), why])
	return why

func _part_at(place: String):
	for k in st["parts"]:
		if str(st["parts"][k]["at"]) == place:
			return k
	return null

func _act(kind: String, a: Array) -> String:
	if phase != "LIVE" and kind != "trainee":
		return "the watch is running: nothing can be changed now"
	match kind:
		"trainee":
			trainee()["node"] = str(a[0])
			return ""
		"inspect":
			if str(a[0]) in POWER_ITEMS:
				if not at("console"):
					return "the electrical overview is at the ops console in sector 2"
			elif not at("bay"):
				return "the machines are in the ECLSS bay in sector 3: you have to be there"
			if not inspected.has(str(a[0])):
				inspected[str(a[0])] = t()
			return ""
		"isolate":
			if not at("bay"):
				return "isolation is done at the machine, in the ECLSS bay in sector 3"
			if not str(a[0]) in sc["places"]["bay"]["holds"]:
				return "%s is not in the bay" % a[0]
			if job != null and equipment_of(str(job["slot"]).trim_prefix("A.")) == str(a[0]) and not bool(a[1]):
				return "you are working on it: finish or put the part down first"
			rs.set_isolated(st, "A", str(a[0]), bool(a[1]))
			return ""
		"remove", "install":
			if not at("bay"):
				return "parts are changed at the machine, in the ECLSS bay in sector 3"
			var slot := str(a[0])
			var full := "A." + slot
			var e := equipment_of(slot)
			if not slot in BAY_SLOTS:
				return "%s is not a slot in the bay" % slot
			if not bool(st["ring"]["A"]["isolated"][e]):
				return "the %s is not isolated: isolate it before you work on it" % e
			if job != null:
				return "you are already working on a part"
			var here = _part_at(full)
			if kind == "remove":
				if hands != null:
					return "your hands are full: stow the part first"
				if here == null:
					return "%s is empty" % slot
				job = {"kind": "remove", "slot": full, "part": here, "done_s": 0.0, "need_s": float(sc["work"]["remove_s"])}
				return ""
			if hands == null:
				return "you have no part in hand"
			if here != null:
				return "%s already holds a part: remove it first" % slot
			var fam := str(rs.slots[slot])
			if str(st["parts"][hands]["lru"]) != fam:
				return "that part does not fit: %s against %s" % [rs.lru[st["parts"][hands]["lru"]]["title"], rs.lru[fam]["title"]]
			job = {"kind": "install", "slot": full, "part": hands, "done_s": 0.0, "need_s": float(sc["work"]["install_s"])}
			return ""
		"take":
			if not at("bay"):
				return "the parts shelf is in the ECLSS bay"
			if hands != null:
				return "your hands are full"
			if not st["parts"].has(str(a[0])) or str(st["parts"][str(a[0])]["at"]) != "A.SHELF":
				return "%s is not on the shelf" % a[0]
			rs.move_part(st, str(a[0]), "CARRY.T")
			hands = str(a[0])
			return ""
		"stow":
			if not at("bay"):
				return "the parts shelf is in the ECLSS bay"
			if hands == null:
				return "your hands are empty"
			if job != null and str(job["part"]) == str(hands):
				return "you are installing it"
			rs.move_part(st, str(hands), "A.SHELF")
			hands = null
			return ""
		"switch", "tie", "reset", "converter", "economy":
			if not at("console"):
				return "switching is done at the ops console in sector 2"
			match kind:
				"switch":
					if not st["ring"][str(a[0])]["on"].has(str(a[1])):
						return "no load %s" % a[1]
					rs.set_on(st, str(a[0]), str(a[1]), bool(a[2]))
				"tie":
					rs.set_tie(st, bool(a[0]))
				"reset":
					rs.reset_breaker(st, str(a[0]))
				"economy":
					rs.set_economy(st, str(a[0]), bool(a[1]))
				_:
					rs.set_converter(st, str(a[0]), bool(a[1]))
			return ""
		"order":
			var pair := str(a[0])
			var what := str(a[1])
			var names: Array = sc["crew"]["pairs"].map(func(x): return str(x[0]))
			if not pair in names:
				return "no pair %s" % pair
			if not idle(pair):
				return "pair %s is busy" % pair
			var ms := pair_members(pair, what)
			if what == "move" and pair == "A" and (job != null or hands != null):
				return "finish the work in hand and stow the part before you leave"
			var T := float(sc["crew"]["transfer_s"])
			var W := float(sc["crew"]["fetch_work_s"])
			var ring := str(ms[0]["ring"])
			var plan := []
			if what == "fetch":
				var part := str(a[2])
				if not st["parts"].has(part) or not str(st["parts"][part]["at"]).begins_with("B."):
					return "%s is not installed in ring B" % part
				if ring != "A":
					return "pair %s is not in ring A" % pair
				plan = [["cross", T, "B"], ["isolate", W, part], ["cross", T, "A"], ["deliver", 0.0, part]]
			elif what == "move":
				var to := str(a[2])
				if to == ring:
					return "pair %s is already in ring %s" % [pair, to]
				plan = [["cross", T, to]]
			else:
				return "no order %s" % what
			for i in ms.size():
				ms[i]["task"] = {"plan": plan.duplicate(true), "k": 0, "left": float(plan[0][1]), "lead": i == 0}
				_begin_task(ms[i])
			return ""
		"watch":
			if job != null:
				return "finish the work in hand first"
			_start_watch()
			return ""
	return "unknown action %s" % kind

func _begin_task(q: Dictionary) -> void:
	var ph: Array = q["task"]["plan"][int(q["task"]["k"])]
	if str(ph[0]) == "cross":
		q["ring"] = "X"
		q["crossings"] = int(q["crossings"]) + 1
	elif str(ph[0]) == "isolate" and bool(q["task"]["lead"]):
		rs.set_isolated(st, "B", str(ph[2]).get_slice(".", 1), true)

func _finish_task(q: Dictionary) -> void:
	var ph: Array = q["task"]["plan"][int(q["task"]["k"])]
	var lead := bool(q["task"]["lead"])
	match str(ph[0]):
		"cross":
			q["ring"] = str(ph[2])
			q["node"] = "A3" if str(ph[2]) == "A" else "B2"
		"isolate":
			if lead:
				rs.move_part(st, str(ph[2]), "CARRY." + str(q["pair"]))
		"deliver":
			if lead:
				rs.move_part(st, str(ph[2]), str(sc["crew"]["deliver_to"]))

func _tasks(dt: float) -> void:
	for q in people:
		var d := dt
		while q["task"] != null:
			var tk: Dictionary = q["task"]
			if float(tk["left"]) > d - EPS and float(tk["left"]) > EPS:
				tk["left"] = float(tk["left"]) - d
				if float(tk["left"]) > EPS:
					break
			_finish_task(q)
			tk["k"] = int(tk["k"]) + 1
			if int(tk["k"]) >= (tk["plan"] as Array).size():
				q["task"] = null
				log.append([t(), "arrived", [q["id"], q["ring"]], ""])
				break
			tk["left"] = float(tk["plan"][int(tk["k"])][1])
			_begin_task(q)
			if float(tk["left"]) > EPS:
				break
			d = 0.0
		_occupy()

func _work(dt: float) -> void:
	if job == null or not at("bay"):
		return
	job["done_s"] = float(job["done_s"]) + dt
	if float(job["done_s"]) < float(job["need_s"]) - EPS:
		return
	if str(job["kind"]) == "remove":
		rs.move_part(st, str(job["part"]), "CARRY.T")
		hands = str(job["part"])
	else:
		rs.move_part(st, str(job["part"]), str(job["slot"]))
		hands = null
	log.append([t(), "removed" if str(job["kind"]) == "remove" else "installed", [job["slot"], job["part"]], ""])
	job = null

func tick(dt := -1.0) -> void:
	if dt < 0.0:
		dt = dtv
	while not later_faults.is_empty() and float(later_faults[0][0]) <= t() + EPS:
		rs.fail_part(st, str(later_faults.pop_front()[1]))
	if restart_s != null and restart == null and t() >= float(restart_s) - EPS:
		var E := float(st["E"])
		var ok := rs.charge_pulse(st)
		if ok:
			rs.set_fusion(st, true)
		restart = {"ok": ok, "battery_kWh": E / 3.6e6, "t_s": t()}
		log.append([t(), "restart", [ok, E / 3.6e6], ""])
	_work(dt)
	_tasks(dt)
	_occupy()
	var before := [(st["ring"]["A"]["on"] as Dictionary).duplicate(), (st["ring"]["B"]["on"] as Dictionary).duplicate()]
	rs.step(st, dt)
	if not alerted and t() >= float(sc["time"]["alert_s"]) - EPS:
		alerted = true
		_on_alert()
	for kr in 2:
		var r: String = rs.RINGS[kr]
		if living(r) == 0:
			continue
		for e in rs.equipment:
			if bool(e["shed"]) and not bool(before[kr][e["id"]]):
				shed_J += float(e["W"]) * dt
	_account(dt)

func _account(dt: float) -> void:
	for r in rs.RINGS:
		var rr: Dictionary = st["ring"][r]
		var T := float(rr["T"])
		var x := rs.x_co2(T, float(rr["m_c"]))
		var h := rs.rh(T, float(rr["m_w"]))
		var ppl := people.filter(func(q): return str(q["ring"]) == r and q["task"] == null)
		if ppl.is_empty() and int(extra[r]) == 0:
			continue
		var fl := {"co2": x > float(p["co2_max"]), "hot": T > float(p["T_max"]), "wet": h > float(p["rh_limit"]), "cold": T < float(p["T_min"])}
		for q in ppl:
			q["co2_s"] = float(q["co2_s"]) + (dt if fl["co2"] else 0.0)
			q["hot_s"] = float(q["hot_s"]) + (dt if fl["hot"] else 0.0)
			q["wet_s"] = float(q["wet_s"]) + (dt if fl["wet"] else 0.0)
			q["cold_s"] = float(q["cold_s"]) + (dt if fl["cold"] else 0.0)
			q["band_s"] = float(q["band_s"]) + (dt if h > float(p["rh_max"]) else 0.0)
			q["target_s"] = float(q["target_s"]) + (dt if x > float(p["co2_target"]) else 0.0)
		if not ppl.is_empty() and phase in ["LIVE", "WATCH", "PROJECTION"]:
			var out: bool = T > float(p["T_max"]) + VALID_ABOVE_LIMIT_K or T < float(p["T_min"]) - VALID_BELOW_LIMIT_K
			if not out:
				last_valid[r] = {"t_h": t() / H, "T_C": T - 273.15, "rh": h, "co2_pct": 100.0 * x}
			elif range_exit == null:
				range_exit = {"t_h": t() / H, "ring": r, "phase": phase, "high": T > float(p["T_max"]), "last": last_valid[r]}
			for k in ["co2", "hot", "wet", "cold"]:
				if fl[k]:
					if phase != "PROJECTION" and first_cross[k] == null:
						first_cross[k] = t()
					if phase == "PROJECTION" and after24[k] == null:
						after24[k] = t()
			if phase != "PROJECTION" and not out:
				peak["co2"] = maxf(float(peak["co2"]), x)
				peak["T"] = maxf(float(peak["T"]), T)
				peak["rh"] = maxf(float(peak["rh"]), h)

func _start_watch() -> void:
	phase = "WATCH"
	watch = {"t0": t(), "config": config()}
	log.append([t(), "watch_start", [], ""])

func watch_end_s() -> float:
	return maxf(float(sc["watch"]["ship_h"]) * H, float(watch["t0"]) + float(sc["watch"]["min_h"]) * H)

func watch_step() -> bool:
	var end := watch_end_s()
	if t() >= end - EPS:
		return false
	tick(wdt if end - t() >= wdt - EPS else end - t())
	return true

func begin_projection() -> void:
	watch["end_config"] = config()
	watch["verdict24"] = verdict(true)
	phase = "PROJECTION"

func projection_step() -> bool:
	if t() >= float(sc["watch"]["projection_h"]) * H - EPS:
		phase = "DONE"
		watch["verdict"] = verdict()
		return false
	tick(pdt)
	return true

func finish_watch() -> void:
	begin_projection()
	while projection_step():
		pass

static func _sorted_true(d: Dictionary, want: bool) -> Array:
	var out := []
	for k in d:
		if bool(d[k]) == want:
			out.append(str(k))
	out.sort()
	return out

func config() -> Dictionary:
	var parts := {}
	for k in st["parts"]:
		parts[k] = str(st["parts"][k]["at"])
	var iso := {}
	var off := {}
	for r in rs.RINGS:
		iso[r] = _sorted_true(st["ring"][r]["isolated"], true)
		off[r] = _sorted_true(st["ring"][r]["on"], false)
	return {"occ": (st["occ"] as Dictionary).duplicate(), "parts": parts, "isolated": iso, "off": off, "tie": st["tie"],
		"breaker": (st["breaker"] as Dictionary).duplicate(), "fusion": st["fusion"]}

func hostable(r: String) -> bool:
	var ok := func(e: String) -> bool: return rs.equipment_ready(st, r, rs.eq(e))
	return ok.call("CO2") and ok.call("CHX") and (ok.call("P1") or ok.call("P2")) and ok.call("HP")

func dark(r: String) -> bool:
	var on: Dictionary = st["ring"][r]["on"]
	for e in rs.equipment:
		if bool(e["survival"]) and bool(on[e["id"]]):
			return false
	return true

func family() -> String:
	if key == "ds3":
		return family_ds3()
	var borrowed := []
	var in_co2 = null
	for k in st["parts"]:
		var at_ := str(st["parts"][k]["at"])
		if str(k).begins_with("B.") and at_.begins_with("A."):
			borrowed.append(str(k))
		if at_ == "A.CO2.FAN" and in_co2 == null:
			in_co2 = str(k)
	if int(st["occ"]["B"]) >= maxi(1, int(st["occ"]["A"]) + 1):
		return "RELOCATE"
	if in_co2 == "A.CHX.FAN":
		return "CANNIBALIZE"
	if "B.CO2.FAN" in borrowed and borrowed.any(func(k): return str(k).ends_with("PUMP")):
		return "BORROW_FAN_PUMP"
	if "B.CO2.FAN" in borrowed:
		return "BORROW_FAN"
	return "NO_REPAIR"

func family_ds3() -> String:
	var c: Dictionary = watch.get("config", {}) if not watch.get("config", {}).is_empty() else config()
	if not bool(c["tie"]):
		return "PACKS_ONLY"
	if not "GARDEN" in c["off"]["A"]:
		return "KEEP_GARDEN"
	if dark("B"):
		return "SHED_DARK_B"
	if bool(st["ring"]["A"]["economy"]):
		return "SHED_ECONOMY"
	return "SHED_GARDEN"

func verdict(limit_only := false) -> Dictionary:
	var fc := first_cross
	var failed_restart: bool = restart != null and not bool(restart["ok"])
	var first = null
	for k in ["co2", "hot", "wet", "cold"]:
		if fc[k] != null and (first == null or float(fc[k]) < float(first)):
			first = fc[k]
	var res := "STABLE"
	if failed_restart and (first == null or float(first) >= float(restart["t_s"]) - EPS):
		res = "RESTART_FAILED"
	elif fc["co2"] != null:
		res = "CO2_LIMIT"
	elif fc["hot"] != null:
		res = "HEAT_LIMIT"
	elif fc["wet"] != null:
		res = "HUMIDITY_LIMIT"
	elif fc["cold"] != null:
		res = "COLD_LIMIT"
	elif not limit_only and after24.values().any(func(v): return v != null):
		res = "TEMPORARY"
	var ch := func(k: String) -> float:
		var s := 0.0
		for q in people:
			s += float(q[k])
		return s / H
	var degraded: bool = res == "STABLE" and (float(ch.call("band_s")) > 0.0 or float(ch.call("target_s")) > 0.0)
	var ex = range_exit if range_exit != null and (not limit_only or str(range_exit["phase"]) != "PROJECTION") else null
	var fch := {}
	var aw := {}
	for k in ["co2", "hot", "wet", "cold"]:
		fch[k] = null if fc[k] == null else float(fc[k]) / H
		aw[k] = null if after24[k] == null else float(after24[k]) / H
	return {"result": res, "degraded": degraded, "first_cross_h": fch, "after_watch_h": aw,
		"crew_h": {"co2_limit": ch.call("co2_s"), "heat_limit": ch.call("hot_s"), "humidity_limit": ch.call("wet_s"), "cold_limit": ch.call("cold_s"),
			"humidity_band": ch.call("band_s"), "co2_target": ch.call("target_s")},
		"peak": {"co2_pct": 100.0 * float(peak["co2"]), "T_C": float(peak["T"]) - 273.15, "rh": peak["rh"], "beyond_validity": ex != null},
		"range_exit": ex, "valid_range_C": [float(p["T_min"]) - VALID_BELOW_LIMIT_K - 273.15, float(p["T_max"]) + VALID_ABOVE_LIMIT_K - 273.15]}

func metrics() -> Dictionary:
	var moved := []
	for k in st["parts"]:
		if str(st["parts"][k]["at"]) != str(start_parts.get(k, "")):
			moved.append(str(k))
	moved.sort()
	var from_b := moved.filter(func(k): return str(k).begins_with("B."))
	var unresolved := []
	for r in rs.RINGS:
		for e in rs.equipment:
			if not (e["slots"] as Array).is_empty() and not rs.equipment_ready(st, r, e):
				unresolved.append("%s.%s" % [r, e["id"]])
	unresolved.sort()
	var first_inspect = null
	for v in inspected.values():
		if first_inspect == null or float(v) < float(first_inspect):
			first_inspect = v
	var acts := log.filter(func(e): return str(e[3]) == "" and not str(e[1]) in ["trainee", "arrived", "watch_start", "inspect"])
	var trips := []
	for tr in st["trips"]:
		trips.append([float(tr[0]) / H, str(tr[1])])
	var crossings := 0
	for q in people:
		crossings += int(q["crossings"])
	return {"parts_moved": moved, "parts_from_ring_b": from_b, "hostable": {"A": hostable("A"), "B": hostable("B")}, "unresolved": unresolved,
		"crossings": crossings, "shed_kWh": shed_J / 3.6e6, "battery_kWh": float(st["E"]) / 3.6e6,
		"battery_used_kWh": (float(st["E0"]) - float(st["E"])) / 3.6e6, "packs_kWh": {"A": float(st["pack"]["A"]) / 3.6e6, "B": float(st["pack"]["B"]) / 3.6e6},
		"first_inspect_h": null if first_inspect == null else float(first_inspect) / H, "last_action_h": float(acts[-1][0]) / H if not acts.is_empty() else null,
		"watch_declared_h": float(watch["t0"]) / H if not watch.is_empty() else null, "refusals": log.filter(func(e): return str(e[3]) != "").size(),
		"restart": restart, "trips": trips, "dark_rings": rs.RINGS.filter(func(r): return dark(r)),
		"economy": rs.RINGS.filter(func(r): return bool(st["ring"][r]["economy"]))}

func decisions() -> Array:
	var keep := ["isolate", "removed", "installed", "take", "stow", "switch", "tie", "reset", "converter", "economy", "order", "watch", "restart"]
	var out := []
	for e in log:
		if str(e[1]) in keep and str(e[3]) == "":
			out.append([float(e[0]) / H, e[1], e[2]])
	return out

func debrief() -> Dictionary:
	var rings := {}
	for r in rs.RINGS:
		var rr: Dictionary = st["ring"][r]
		rings[r] = {"T_C": float(rr["T"]) - 273.15, "rh": rs.rh(float(rr["T"]), float(rr["m_w"])), "co2_pct": 100.0 * rs.x_co2(float(rr["T"]), float(rr["m_c"])),
			"occupants": st["occ"][r]}
	return {"watch": {"family": family(), "verdict": watch["verdict"] if watch.has("verdict") else verdict(), "verdict24": watch.get("verdict24")},
		"metrics": metrics(), "decisions": decisions(), "rings": rings, "ledgers": rs.ledgers(st)}

func checkpoint() -> Dictionary:
	var T := {}
	var mw := {}
	var mc := {}
	var parts := {}
	for r in rs.RINGS:
		T[r] = st["ring"][r]["T"]; mw[r] = st["ring"][r]["m_w"]; mc[r] = st["ring"][r]["m_c"]
	for k in st["parts"]:
		parts[k] = str(st["parts"][k]["at"])
	return {"t_s": t(), "phase": phase, "T": T, "m_w": mw, "m_c": mc, "E": st["E"], "pack": (st["pack"] as Dictionary).duplicate(),
		"occ": (st["occ"] as Dictionary).duplicate(), "parts": parts}

## A reference script to the end of the projection, or to `until_s` of the live part (ship_ops.play).
func play(actions: Array, until_s := -1.0) -> Array:
	begin_run()
	var acts := []
	for i in actions.size():
		acts.append([float(actions[i][0]), i, actions[i]])
	acts.sort_custom(func(a, b): return a[0] < b[0] or (a[0] == b[0] and a[1] < b[1]))
	var i := 0
	var cps := []
	while phase == "LIVE":
		while i < acts.size() and float(acts[i][0]) <= t() + EPS:
			var a: Array = acts[i][2]
			act(str(a[1]), a.slice(2))
			i += 1
			if phase != "LIVE":
				break
		if phase != "LIVE":
			break
		if absf(fmod(t(), 1800.0)) < EPS:
			cps.append(checkpoint())
		if until_s >= 0.0 and t() >= until_s - EPS:
			return cps
		tick()
		if t() > 30.0 * H:
			push_error("SHIP OPS: a script never declared the watch")
			return cps
	while i < acts.size():
		var a: Array = acts[i][2]
		act(str(a[1]), a.slice(2))
		i += 1
	while watch_step_cp(cps):
		if until_s >= 0.0 and t() > until_s + EPS:
			return cps
	finish_watch()
	cps.append(checkpoint())
	return cps

func watch_step_cp(cps: Array) -> bool:
	if t() >= watch_end_s() - EPS:
		return false
	if absf(fmod(t(), 1800.0)) < EPS:
		cps.append(checkpoint())
	return watch_step()

func case_named(name: String) -> Dictionary:
	for c in doc["references"]:
		if str(c["name"]) == name:
			return c
	return {}

static func _close(a: float, b: float, tol: Dictionary) -> bool:
	return absf(a - b) <= float(tol["abs"]) + float(tol["rel"]) * maxf(absf(a), absf(b))

func compare(got: Array, want: Array, label: String) -> Array:
	var tol: Dictionary = rs.doc["tolerance"]
	var bad := []
	var n := mini(got.size(), want.size())
	if got.size() < want.size() and not (want.size() > got.size() and got.size() > 0):
		bad.append("%s: %d checkpoints, the module %d" % [label, got.size(), want.size()])
	for i in n:
		var g: Dictionary = got[i]
		var w: Dictionary = want[i]
		if not _close(float(g["t_s"]), float(w["t_s"]), tol) or str(g["phase"]) != str(w["phase"]):
			bad.append("%s cp %d: t %.1f %s, the module %.1f %s" % [label, i, float(g["t_s"]), g["phase"], float(w["t_s"]), w["phase"]])
			break
		var pairs := [["E", float(g["E"]), float(w["E"])]]
		for r in rs.RINGS:
			pairs.append(["T." + r, float(g["T"][r]), float(w["T"][r])])
			pairs.append(["m_w." + r, float(g["m_w"][r]), float(w["m_w"][r])])
			pairs.append(["m_c." + r, float(g["m_c"][r]), float(w["m_c"][r])])
			pairs.append(["pack." + r, float(g["pack"][r]), float(w["pack"][r])])
			if int(g["occ"][r]) != int(w["occ"][r]):
				bad.append("%s t %.0f: occupants %s %d, the module %d" % [label, float(g["t_s"]), r, int(g["occ"][r]), int(w["occ"][r])])
		for pq in pairs:
			if not _close(float(pq[1]), float(pq[2]), tol):
				bad.append("%s t %.0f: %s %s, the module %s" % [label, float(g["t_s"]), pq[0], float(pq[1]), float(pq[2])])
		for k in w["parts"]:
			if str(g["parts"].get(k, "")) != str(w["parts"][k]):
				bad.append("%s t %.0f: %s at %s, the module %s" % [label, float(g["t_s"]), k, g["parts"].get(k, ""), w["parts"][k]])
		if bad.size() > 6:
			break
	return bad

## The debrief's numbers against the module's (the check plays every case to the end).
func compare_debrief(got: Dictionary, want: Dictionary, label: String) -> Array:
	var tol := {"rel": 1e-7, "abs": 1e-7}
	var bad := []
	if str(got["watch"]["family"]) != str(want["watch"]["family"]):
		bad.append("%s: family %s, the module %s" % [label, got["watch"]["family"], want["watch"]["family"]])
	var gv: Dictionary = got["watch"]["verdict"]
	var wv: Dictionary = want["watch"]["verdict"]
	if str(gv["result"]) != str(wv["result"]) or bool(gv["degraded"]) != bool(wv["degraded"]):
		bad.append("%s: verdict %s%s, the module %s%s" % [label, gv["result"], " degraded" if gv["degraded"] else "", wv["result"], " degraded" if wv["degraded"] else ""])
	for k in wv["crew_h"]:
		if not _close(float(gv["crew_h"][k]), float(wv["crew_h"][k]), tol):
			bad.append("%s: crew_h.%s %s, the module %s" % [label, k, float(gv["crew_h"][k]), float(wv["crew_h"][k])])
	for k in ["co2_pct", "T_C", "rh"]:
		if not _close(float(gv["peak"][k]), float(wv["peak"][k]), tol):
			bad.append("%s: peak.%s %s, the module %s" % [label, k, float(gv["peak"][k]), float(wv["peak"][k])])
	if (gv.get("range_exit") == null) != (wv.get("range_exit") == null) or (wv.get("range_exit") != null and (not _close(float(gv["range_exit"]["t_h"]), float(wv["range_exit"]["t_h"]), tol) or str(gv["range_exit"]["ring"]) != str(wv["range_exit"]["ring"]))):
		bad.append("%s: left the valid range %s, the module %s" % [label, str(gv.get("range_exit")), str(wv.get("range_exit"))])
	var gm: Dictionary = got["metrics"]
	var wm: Dictionary = want["metrics"]
	for k in ["shed_kWh", "battery_kWh", "battery_used_kWh"]:
		if not _close(float(gm[k]), float(wm[k]), tol):
			bad.append("%s: %s %s, the module %s" % [label, k, float(gm[k]), float(wm[k])])
	for k in ["crossings", "refusals"]:
		if int(gm[k]) != int(wm[k]):
			bad.append("%s: %s %d, the module %d" % [label, k, int(gm[k]), int(wm[k])])
	for k in ["parts_moved", "parts_from_ring_b", "unresolved", "dark_rings", "economy"]:
		if str(gm[k]) != str(wm[k]):
			bad.append("%s: %s %s, the module %s" % [label, k, str(gm[k]), str(wm[k])])
	for r in rs.RINGS:
		if bool(gm["hostable"][r]) != bool(wm["hostable"][r]):
			bad.append("%s: hostable %s %s, the module %s" % [label, r, gm["hostable"][r], wm["hostable"][r]])
	if (gm["trips"] as Array).size() != (wm["trips"] as Array).size():
		bad.append("%s: %d trips, the module %d" % [label, (gm["trips"] as Array).size(), (wm["trips"] as Array).size()])
	if (gm["restart"] == null) != (wm["restart"] == null) or (gm["restart"] != null and bool(gm["restart"]["ok"]) != bool(wm["restart"]["ok"])):
		bad.append("%s: restart %s, the module %s" % [label, str(gm["restart"]), str(wm["restart"])])
	return bad

func verify_at_load() -> Array:
	var c := case_named(str(doc["verify_at_load"]))
	if c.is_empty():
		return ["no reference case %s in the package" % doc["verify_at_load"]]
	var quiet := host
	host = null                                     # no alert text while verifying
	var got := play(c["actions"], float(doc["verify_until_s"]))
	host = quiet
	var want := (c["checkpoints"] as Array).filter(func(w): return float(w["t_s"]) <= float(doc["verify_until_s"]) + EPS)
	var bad := compare(got, want, str(c["name"]))
	if got.size() != want.size():
		bad.append("%s: %d checkpoints to %.0f s, the module %d" % [c["name"], want.size(), float(doc["verify_until_s"]), got.size()])
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
	view_ring = "A"
	deb_page = 0
	flags = {}
	debrief_cache = {}
	_close_page()
	_event("start")

func _event(what: String) -> void:
	if host != null and host.has_method("_log"):
		host.call("_log", "ship_ops", {"what": what, "ship_s": snappedf(t(), 0.01), "phase": phase, "scenario": sc["scenario"]["id"]})

func _say(s: String) -> void:
	if host != null:
		host.call("say", s)

func _on_alert() -> void:
	if host == null:
		return
	_say(str(sc["alert"]["text"]))
	_event("alert")

func on_ring_a() -> bool:
	return host.get("move") == "WALK" and str(host.get("walk_zone")) == "RING_A"

func _at() -> String:
	if host.get("move") != "WALK":
		return ""
	return eq.point_in_reach((host.get("actor") as Node3D).global_position, str(host.get("walk_zone")))

## The trainee's place for the machine: the bay's compartment in the bay's reach, the console's at the console, elsewhere on ring A "A0".
func _body_node() -> String:
	var a := _at()
	if a == "bay":
		return str(sc["places"]["bay"]["compartment"])
	if a == "console":
		return str(sc["places"]["console"]["compartment"])
	return "A0"

func _pause_now() -> bool:
	if phase == "DONE" or (page != "" and page != "debrief") or not on_ring_a():
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
	if phase == "LIVE" and on_ring_a() and str(trainee()["ring"]) == "A" and trainee()["task"] == null:
		var n := _body_node()
		if n != str(trainee()["node"]):
			act("trainee", [n])
	if page in ["bay", "console"] and _at() != page:
		_close_page()                              # a station page closes when the trainee walks away
	eq.paused = _pause_now()
	var kind := "live_us"
	if phase == "PROJECTION":
		kind = "projection_us"
		for i in MAX_PROJECTION:
			if not projection_step():
				_finish()
				break
			if Time.get_ticks_usec() - t0 > 6000:
				break
	elif not eq.paused or (phase == "WATCH" and page in ["", "report", "intercom"]):
		if phase == "WATCH":
			kind = "watch_us"
			acc += dt * scale()
			var n := 0
			while acc >= wdt and n < MAX_STEPS:
				if not watch_step():
					_end_watch()
					break
				acc -= wdt
				n += 1
			if n == MAX_STEPS:
				acc = 0.0
		elif not eq.paused:
			acc += dt * scale()
			var n := 0
			var log_n := log.size()
			var had_job = job
			while acc >= dtv and n < MAX_STEPS and phase == "LIVE":
				tick()
				acc -= dtv
				n += 1
			if n == MAX_STEPS:
				acc = 0.0
			_crew_news(log_n)
			if had_job != null and job == null:
				_render()
	var us := Time.get_ticks_usec() - t0
	frame_cost[kind] = maxi(int(frame_cost[kind]), us)
	frame_cost["max_frame_us"] = maxi(int(frame_cost["max_frame_us"]), us)

func _crew_news(log_n: int) -> void:
	for e in log.slice(log_n):
		match str(e[1]):
			"arrived":
				var who := str(e[2][0])
				if who in ["A-1", "B-1", "C-1"] or (who == "A-2" and people[0]["task"] == null):
					_say("Intercom: %s %s in ring %s." % [_who(who), "are" if who == "A-1" else "arrived", e[2][1]])
			"removed", "installed":
				_say("Bay: %s %s %s." % [_part_name(str(e[2][1])), "removed from" if str(e[1]) == "removed" else "installed in", str(e[2][0]).trim_prefix("A.")])
			"restart":
				_say("Plant restart window: %s (battery %.0f kWh)." % ["restart fired from the pulse bank" if e[2][0] else "the battery holds less than the pulse bank needs: NO RESTART", float(e[2][1])])
	for tr in st["trips"]:
		if not flags.has("trip_%s_%s" % [tr[0], tr[1]]):
			flags["trip_%s_%s" % [tr[0], tr[1]]] = true
			_say("ELECTRICAL: bus %s breaker TRIPPED: demand %.1f kW over %.1f kW of supply." % [tr[1], float(tr[2]) / 1000.0, float(tr[3]) / 1000.0])

func _who(id: String) -> String:
	if id == "A-1":
		return "you"
	if id.begins_with("A"):
		return "your partner"
	return "pair " + id.get_slice("-", 0)

func _part_name(part: String) -> String:
	if not st["parts"].has(part):
		return part
	var fam := str(st["parts"][part]["lru"])
	var short: String = {"FAN_ECLSS": "fan", "PUMP_ITCS": "pump", "CONVERTER": "converter"}.get(fam, fam)
	return "%s %s (from %s)" % [part.get_slice(".", 0) if part.begins_with("A.") or part.begins_with("B.") else "", short, part]

func _start_watch_now() -> String:
	var r := act("watch")
	if r != "":
		return r
	acc = 0.0
	_close_page()
	_event("watch start")
	_say("STABILITY WATCH: the model runs on from the ship exactly as it is now to %d h (x%d), then the 7-day projection. Nothing changes on its own." % [
		int(watch_end_s() / H), int(sc["time"]["watch_scale"])])
	return ""

func _end_watch() -> void:
	begin_projection()
	_event("watch end " + str(watch["verdict24"]["result"]))
	_say("Watch complete at %d h: %s. The 7-day projection runs now." % [int(t() / H), _verdict_text(str(watch["verdict24"]["result"]))])

func _finish() -> void:
	debrief_cache = debrief()
	_event("debrief")
	_say("7-day projection complete: %s. The debrief shows what held and what it cost." % _verdict_text(str(watch["verdict"]["result"])))
	page = "debrief"
	deb_page = 0
	_render()

func ended() -> bool:
	return phase == "DONE"

# ---- Use and Ops ------------------------------------------------------------------------------------------------------------------------

func _door_first() -> bool:
	if page != "":
		return false
	var w := str(host.call("_walk_target"))
	if w == "":
		return false
	var at_ := _at()
	if at_ == "":
		return true
	var eye: Vector3 = (host.get("actor") as Node3D).global_position
	var fwd: Vector3 = -(host.call("look_basis") as Basis).z
	var to_point := eq.centre(at_) - eye
	var to_door: Vector3 = (host.get("lines")["ACCESS_A"].p[-1] if w == "ladder" else (host.get("circ_doors")[w]["collider"] as Node3D).global_position) - eye
	return fwd.angle_to(to_door) < fwd.angle_to(to_point)

func use() -> String:
	if not verified:
		return ""
	if page == "debrief":
		deb_page += 1
		if deb_page > DEB_PAGES - 1:
			_close_page()
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
	if page in ["bay", "console", "intercom"]:
		var n := _items().size()
		sel = (sel + 1) % n
		_render()
		return "select %d" % sel
	if _door_first() or _learning_first():
		return ""
	var a := _at()
	if a == "bay" or a == "console":
		_open(a)
		return a
	return ""

## A learning station in reach keeps Use when it is open or the trainee looks more towards it than towards the bay or console.
func _learning_first() -> bool:
	var L = host.get("learning")
	if page != "" or L == null:
		return false
	var i := int(host.call("_learning_in_reach"))
	if i < 0:
		return false
	if int(L.open) == i:
		return true
	var a := _at()
	if a == "":
		return true
	var eye: Vector3 = (host.get("actor") as Node3D).global_position
	var fwd: Vector3 = -(host.call("look_basis") as Basis).z
	return fwd.angle_to(L.centre(i) - eye) < fwd.angle_to(eq.centre(a) - eye)

func ops() -> String:
	if not verified or not on_ring_a():
		return ""
	if ended():
		_replay()
		return "replay"
	if page == "debrief":
		_close_page()
		return "close"
	if page == "report":
		_open("intercom")
		return "intercom"
	if page in ["bay", "console", "intercom"]:
		return _activate(_items()[sel])
	var a := _at()
	if a == "bay" or a == "console":
		_open(a)
		return a
	_open("intercom")
	return "intercom"

func _replay() -> void:
	begin()
	if host.has_method("training_reset"):
		host.call("training_reset")
	_say("%s restarted from the same start: %s" % [sc["scenario"]["name"], fill(str(sc["stages"][0]["objective"]))])

func _open(pg: String) -> void:
	page = pg
	sel = 0
	if alerted:
		flags["looked"] = true
	if pg == "console" and phase == "LIVE":
		for it in ["BUS.A", "BUS.B", "BATTERY", "PACKS"]:
			act("inspect", [it])
		if alerted:
			flags["assessed"] = flags.has("inspected")
	if pg == "intercom" and flags.has("inspected"):
		flags["assessed"] = true
	_render()

func _close_page() -> void:
	page = ""
	panel.visible = false

# ---- the pages' lines ---------------------------------------------------------------------------------------------------------------------

func _state_of(r: String, e: String) -> String:
	var rr: Dictionary = st["ring"][r]
	var plan: Dictionary = st.get("plan", {})
	var s = plan["run"][r][e] if not plan.is_empty() else null
	if bool(rr["isolated"][e]):
		return "ISOLATED"
	if not bool(rr["on"][e]):
		return "OFF"
	var e_d := rs.eq(e)
	for sl in e_d["slots"]:
		var full := "%s.%s" % [r, sl]
		if _part_at(full) == null:
			return "NO PART"
		if not rs.slot_ok(st, full):
			return "FAULT"
	return {"BUS": "RUN", "PACK": "RUN (packs)", "DARK": "NO POWER"}.get(s, "-")

func _items() -> Array:
	var out := []
	match page:
		"bay":
			for e in BAY_MACHINES:
				var e_d := rs.eq(e)
				if phase == "LIVE" and not inspected.has(e):
					out.append(["inspect", "Inspect the %s" % TITLES[e], e])
				var iso := bool(st["ring"]["A"]["isolated"][e])
				out.append(["isolate", "%s: %s -> %s" % [(str(TITLES[e]).left(1).to_upper() + str(TITLES[e]).substr(1)), "isolated" if iso else "in service", "return to service" if iso else "isolate"], e, not iso])
				for sl in e_d["slots"]:
					var here = _part_at("A." + sl)
					if here != null:
						out.append(["remove", "Remove the %s's part (%s, %s)" % [TITLES[e], here, "whole" if st["parts"][here]["ok"] else "FAILED"], sl])
					else:
						out.append(["install", "Install the part in hand in the %s%s" % [TITLES[e], "" if hands == null else " (%s)" % hands], sl])
			for k in st["parts"]:
				if str(st["parts"][k]["at"]) == "A.SHELF":
					out.append(["take", "Take %s from the shelf (%s)" % [k, "whole" if st["parts"][k]["ok"] else "FAILED"], k])
			if hands != null:
				out.append(["stow", "Put %s on the shelf" % hands])
		"console":
			out.append(["view", "Loads shown: ring %s -> ring %s" % [view_ring, "B" if view_ring == "A" else "A"]])
			for e in rs.equipment:
				var on := bool(st["ring"][view_ring]["on"][e["id"]])
				out.append(["switch", "Ring %s %s (%.1f kW, bus %s): %s -> %s" % [view_ring, TITLES[e["id"]], float(e["W"]) / 1000.0 if str(e["id"]) != "HP" else rs.coil_now(st, view_ring)["W_hp"] / 1000.0,
					e["bus"], "on" if on else "off", "off" if on else "on"], view_ring, e["id"], not on])
			var eco := bool(st["ring"][view_ring]["economy"])
			out.append(["economy", "Ring %s heat pump setpoint: %s -> %s" % [view_ring, "economy (12 C)" if eco else "normal (4 C)", "normal" if eco else "economy"], view_ring, not eco])
			out.append(["tie", "Bus tie: %s -> %s" % ["closed" if st["tie"] else "open", "open" if st["tie"] else "close"], not bool(st["tie"])])
			for b in rs.BUSES:
				if not bool(st["breaker"][b]):
					out.append(["reset", "Reset bus %s's breaker (tripped)" % b, b])
		"intercom":
			if phase == "LIVE":
				for pr in ["A", "B", "C"]:
					var ms := pair_members(pr)
					var who: String = "your partner" if pr == "A" else "pair " + str(pr)
					if not idle(pr):
						continue
					if str(ms[0]["ring"]) == "A":
						for sl in BAY_SLOTS:
							var part: String = "B." + str(sl)
							if st["parts"].has(part) and str(st["parts"][part]["at"]) == part:
								out.append(["order", "Send %s to fetch ring B's %s" % [who, _slot_title(sl)], pr, "fetch", part])
					if pr != "A":
						out.append(["order", "Move %s to ring %s" % [who, "B" if str(ms[0]["ring"]) == "A" else "A"], pr, "move", "B" if str(ms[0]["ring"]) == "A" else "A"])
				if idle("A") and idle("B") and idle("C") and str(trainee()["ring"]) == "A":
					out.append(["everyone", "Move everyone, you too, to ring B"])
			out.append(["report", "Crew and ring report"])
			if phase == "LIVE" and alerted:
				out.append(["watch", "Declare the ship set: start the stability watch"])
	if page in ["bay", "console"]:
		out.append(["intercom", "Intercom (orders, report, the watch)"])
	out.append(["close", "Close"])
	return out

func _slot_title(sl: String) -> String:
	return {"CO2.FAN": "CO2-unit fan", "CHX.FAN": "heat exchanger fan", "P1.PUMP": "coolant pump 1", "P2.PUMP": "coolant pump 2"}.get(sl, sl)

func _activate(it: Array) -> String:
	var kind := str(it[0])
	var r := ""
	match kind:
		"close":
			_close_page()
			return "close"
		"intercom":
			_open("intercom")
			return "intercom"
		"report":
			page = "report"
			_render()
			return "report"
		"view":
			view_ring = "B" if view_ring == "A" else "A"
			_render()
			return "view " + view_ring
		"watch":
			r = _start_watch_now()
		"everyone":
			for pr in ["B", "C", "A"]:
				r = act("order", [pr, "move", "B"])
				if r != "":
					break
			if r == "":
				_say("Intercom: everyone, you too, is crossing to ring B (%d min). The walk stays on ring A's deck: from here you can only use the intercom." % int(float(sc["crew"]["transfer_s"]) / 60.0))
		"order":
			r = act("order", it.slice(2))
			if r == "":
				var who: String = "your partner" if str(it[2]) == "A" else "pair " + str(it[2])
				if str(it[3]) == "fetch":
					_say("Intercom: %s crosses to ring B (%d min), isolates the machine there, removes the part (%d min) and brings it to the shelf here." % [
						who, int(float(sc["crew"]["transfer_s"]) / 60.0), int(float(sc["crew"]["fetch_work_s"]) / 60.0)])
				else:
					_say("Intercom: %s crosses to ring %s (%d min)." % [who, it[4], int(float(sc["crew"]["transfer_s"]) / 60.0)])
		"inspect":
			r = act("inspect", [it[2]])
			if r == "":
				flags["inspected"] = true
				_say("Bay: " + _inspect_text(str(it[2])))
		_:
			r = act(kind, it.slice(2))
			if r == "" and kind in ["remove", "install"]:
				_say("Bay: %s started, %d ship min; stay at the bay." % [kind, int(float(sc["work"][kind + "_s"]) / 60.0)])
	if r != "":
		_say("Refused: %s." % r)
		_event("refused " + kind)
	else:
		_event(kind)
		if kind in ["isolate", "remove", "install", "take", "stow", "switch", "tie", "reset", "economy", "order", "everyone"]:
			flags["acted"] = true
	var n := _items().size()
	sel = mini(sel, n - 1)
	if page != "":
		_render()
	return kind if r == "" else "refused " + kind

func _inspect_text(e: String) -> String:
	var s := _state_of("A", e)
	var e_d := rs.eq(e)
	var parts := []
	for sl in e_d["slots"]:
		var here = _part_at("A." + sl)
		parts.append("%s %s" % [sl, "empty" if here == null else ("%s %s" % [here, "whole" if st["parts"][here]["ok"] else "FAILED: no flow with power on"])])
	return "%s %s%s." % [TITLES[e], s, "" if parts.is_empty() else " · " + ", ".join(parts)]

func fill(s: String) -> String:
	var use_k: String = host.call("key", "exc.use") if host != null else "Use"
	var ops_k: String = host.call("key", "exc.ops") if host != null else "Ops"
	var map_k: String = host.call("key", "exc.map") if host != null else "Map"
	return s.format({"use": use_k, "ops": ops_k, "map": map_k})

func stage() -> int:
	if phase == "DONE":
		return 6
	if phase != "LIVE":
		return 5
	if not alerted or not flags.get("looked", false):
		return 0
	if not flags.has("inspected") and inspected.is_empty():
		return 1
	if not flags.get("assessed", false):
		return 2
	if not flags.get("acted", false):
		return 3
	return 4

func _verdict_text(v: String) -> String:
	return {"STABLE": "stable under the stated assumptions (CO2, temperature and humidity hold where people live)",
		"TEMPORARY": "temporary: it held through the watch but a limit is passed later in the week",
		"CO2_LIMIT": "the CO2 control limit (0.5 %) was passed where people live", "HEAT_LIMIT": "the cabin passed its 27 C habitability limit where people live",
		"HUMIDITY_LIMIT": "the cabin passed 75 % relative humidity where people live", "COLD_LIMIT": "people lived in a cabin below 18 C",
		"RESTART_FAILED": "the battery held less than the pulse bank needs at the restart window: the plant could not restart"}.get(v, v)

func _hm(s: float) -> String:
	var mins := int(floor(s / 60.0))
	return "%d:%02d" % [mins / 60, mins % 60]

func _clock() -> String:
	return "ship T+%s (x%d%s) · real %s" % [_hm(t()), int(scale()), ", paused" if paused() and phase != "DONE" else "", _hm(real_s)]

func goal_text() -> String:
	if not verified:
		return "DEADSHIP TRAINING unavailable: " + (str(errors[0]) if not errors.is_empty() else "")
	var head := "DEADSHIP TRAINING · %s %s (simulation, unscored)" % [sc["scenario"]["id"], sc["scenario"]["name"]]
	var sg: Dictionary = sc["stages"][stage()]
	if phase == "WATCH":
		return "%s · Verify: stability watch, ship T+%s of %d h (x%d) · real %s" % [head, _hm(t()), int(watch_end_s() / H), int(scale()), _hm(real_s)]
	if phase == "PROJECTION":
		return "%s · Verify: 7-day projection, computed ahead, ship T+%.0f of %d h · real %s" % [head, t() / H, int(sc["watch"]["projection_h"]), _hm(real_s)]
	if phase == "DONE":
		return "%s · Debrief: %s · %s replays" % [head, _verdict_text(str(watch["verdict"]["result"])), host.call("key", "exc.ops")]
	var work := ""
	if job != null:
		work = " · %s %d/%d min" % [job["kind"], int(float(job["done_s"]) / 60.0), int(float(job["need_s"]) / 60.0)]
	if hands != null:
		work += " · in hand: %s" % hands
	if str(trainee()["ring"]) != "A":
		work += " · you are %s" % ("crossing to ring B" if str(trainee()["ring"]) == "X" else "in ring B (intercom only)")
	return "%s · Stage %d of 7 · %s: %s%s · %s" % [head, stage() + 1, sg["title"], fill(str(sg["objective"])), work, _clock()]

func lines() -> Array:
	var out := []
	for i in 7:
		var sg: Dictionary = sc["stages"][i]
		out.append("%s %d %s" % ["[x]" if i < stage() else ("[>]" if i == stage() else "[ ]"), i + 1, sg["title"]])
	out.append(_ring_line("A") + "  ·  " + _ring_line("B"))
	out.append(_power_line())
	if alerted and phase == "LIVE":
		out.append("Hint: " + fill(str(sc["stages"][stage()]["hint"])))
	return out

## A cabin temperature and humidity as shown: outside the model's valid range only the bound, never the extrapolated number.
func _th_text(T_C: float, rh_: float) -> String:
	var hi := float(p["T_max"]) + VALID_ABOVE_LIMIT_K - 273.15
	var lo := float(p["T_min"]) - VALID_BELOW_LIMIT_K - 273.15
	if T_C > hi:
		return "above %.0f C (outside the model)" % hi
	if T_C < lo:
		return "below %.0f C (outside the model)" % lo
	return "%.1f C RH %d%%" % [T_C, int(round(100.0 * rh_))]

func _ring_line(r: String) -> String:
	var rr: Dictionary = st["ring"][r]
	return "Ring %s (%d) %s CO2 %.2f%%" % [r, int(st["occ"][r]), _th_text(float(rr["T"]) - 273.15, rs.rh(float(rr["T"]), float(rr["m_w"]))),
		100.0 * rs.x_co2(float(rr["T"]), float(rr["m_c"]))]

func _power_line() -> String:
	var plan: Dictionary = st.get("plan", {})
	var live := []
	for b in rs.BUSES:
		var ok: bool = not plan.is_empty() and bool(plan["live"][b])
		live.append("bus %s %s" % [b, "LIVE" if ok else ("TRIPPED" if not bool(st["breaker"][b]) else "DEAD")])
	return "%s · tie %s · battery %.0f kWh · packs %.1f/%.1f kWh · fusion %s" % [" ".join(live), "closed" if st["tie"] else "open", float(st["E"]) / 3.6e6,
		float(st["pack"]["A"]) / 3.6e6, float(st["pack"]["B"]) / 3.6e6, "on" if st["fusion"] else "off"]

func prompt() -> String:
	var a := _at()
	if a == "bay":
		return "%s ECLSS bay" % host.call("key", "exc.use")
	if a == "console":
		return "%s ops console" % host.call("key", "exc.use")
	return ""

func use_label() -> String:
	if not verified:
		return ""
	if page == "debrief":
		return "Use · next page" if deb_page < DEB_PAGES - 1 else "Use · close"
	if ended():
		return "Use · debrief"
	if page in ["bay", "console", "intercom"]:
		return "Use · next item"
	if page == "report":
		return "Use · back"
	if _door_first() or _learning_first():
		return ""
	var a := _at()
	if a == "bay":
		return "Use · ECLSS bay"
	if a == "console":
		return "Use · ops console"
	return ""

## A run that left the model's valid cabin range: the limit crossing, the exit, the last valid state; no extrapolated temperature.
func _range_exit_line(v: Dictionary, ex: Dictionary, lim: Array) -> String:
	var rng: Array = v["valid_range_C"]
	var fc: Dictionary = v["first_cross_h"]
	var cross := ""
	for k in ["hot", "cold", "co2", "wet"]:
		if fc[k] != null:
			cross = "%s limit passed at T+%s; " % [{"hot": "Temperature", "cold": "Cold", "co2": "CO2", "wet": "Humidity"}[k], _hm(float(fc[k]) * H)]
			break
	var last = ex["last"]
	var lv := "" if last == null else " Last valid state (T+%s): %.1f C, RH %d %%, CO2 %.2f %%." % [_hm(float(last["t_h"]) * H), float(last["T_C"]),
		int(round(100.0 * float(last["rh"]))), float(last["co2_pct"])]
	return "Where people lived: %sat T+%s ring %s left the model's valid range (%s %.0f C).%s Later temperatures, and the humidity that follows them, are outside the model (no hull exchange, cabin heaters or equipment cutouts are modelled) and are not shown.%s" % [
		cross, _hm(float(ex["t_h"]) * H), ex["ring"], "above" if bool(ex["high"]) else "below", float(rng[1]) if bool(ex["high"]) else float(rng[0]), lv,
		"" if lim.is_empty() else " Over a limit: " + ", ".join(lim) + "."]

func ops_label() -> String:
	if not verified or not on_ring_a():
		return ""
	if ended():
		return "Ops · replay"
	if page == "debrief":
		return "Ops · close"
	if page == "report":
		return "Ops · back"
	if page in ["bay", "console", "intercom"]:
		var it: Array = _items()[sel]
		return "Ops · " + ("close" if it[0] == "close" else str(it[1]).get_slice(":", 0).left(34))
	var a := _at()
	if a == "bay":
		return "Ops · ECLSS bay"
	if a == "console":
		return "Ops · ops console"
	return "Ops · intercom"

func board_text() -> String:
	if not verified:
		return "RING SERVICES\nUNAVAILABLE\n" + (str(errors[0]).left(40) if not errors.is_empty() else "")
	var rr: Dictionary = st["ring"]["A"]
	var c := rs.coil_now(st, "A") if st.has("plan") else {"Q_s": 0.0, "cond": 0.0}
	var m := []
	for e in ["CO2", "CHX", "P1", "P2", "HP"]:
		m.append("%s %s" % [e, _state_of("A", e)])
	return "RING A SERVICES · SIM x%d%s\n%s · dew %.1f C\nCO2 %.2f %% · %d aboard\ncoil %.1f kW · %.2f kg/h water\n%s\n%s" % [
		int(scale()), " (paused)" if paused() else "", _th_text(float(rr["T"]) - 273.15, rs.rh(float(rr["T"]), float(rr["m_w"]))),
		rs.dew_point(float(rr["T"]), float(rr["m_w"])) - 273.15, 100.0 * rs.x_co2(float(rr["T"]), float(rr["m_c"])), int(st["occ"]["A"]),
		float(c["Q_s"]) / 1000.0, float(c["cond"]) * 3600.0, " · ".join(m.slice(0, 3)), " · ".join(m.slice(3))]

# ---- pages ---------------------------------------------------------------------------------------------------------------------------------

func _build_ui(ui_layer: CanvasLayer) -> void:
	var back := StyleBoxFlat.new()
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

func _render() -> void:
	if page == "":
		panel.visible = false
		return
	var small := WfInput.compact()
	var out := []
	var head := "[b]%s · %s[/b]" % [str(sc["scenario"]["name"]).to_upper(), {"bay": "ring A ECLSS bay", "console": "ops console", "intercom": "intercom",
		"report": "crew and ring report", "debrief": "debrief %d of %d" % [deb_page + 1, DEB_PAGES]}[page]]
	out.append(head + ("" if small else "  [color=#9fb4d0](simulation, unscored · %s)[/color]" % _clock()))
	match page:
		"bay":
			out.append(_ring_line("A"))
			var c := rs.coil_now(st, "A") if st.has("plan") else {"Q_s": 0.0, "cond": 0.0, "T_coil": 0.0}
			var ms := []
			for e in BAY_MACHINES:
				ms.append("%s %s" % [e, _state_of("A", e)])
			out.append(" · ".join(ms))
			out.append("Coil %.1f kW, %.2f kg/h condensed, surface %.1f C · in hand: %s%s" % [float(c["Q_s"]) / 1000.0, float(c["cond"]) * 3600.0,
				float(c["T_coil"]) - 273.15, "nothing" if hands == null else hands,
				"" if job == null else " · %s %d/%d min" % [job["kind"], int(float(job["done_s"]) / 60.0), int(float(job["need_s"]) / 60.0)]])
			if not small:
				out.append("[color=#9fb4d0][font_size=12]Isolate a machine before you work on it. The CO2 unit's fan and the heat exchanger's fan are one family; so are the pumps.[/font_size][/color]")
		"console":
			out.append(_power_line())
			var dem := rs.demand_now(st)
			out.append("Demand if all ready loads run: bus A %.1f kW, bus B %.1f kW · each converter carries %.0f kW, each generator %.0f kW" % [
				float(dem["A"]) / 1000.0, float(dem["B"]) / 1000.0, float(p["conv_W"]) / 1000.0, float(p["gen_W"]) / 1000.0])
			var conv := []
			for b in rs.BUSES:
				conv.append("BC-%s %s" % [b, "OK" if rs.slot_ok(st, "BC-" + b) else "FAULT"])
			out.append("%s · %s · %s%s" % [" · ".join(conv), _ring_line("A"), _ring_line("B"),
				"" if restart_s == null else " · restart window T+%d h, needs %.0f kWh" % [int(float(restart_s) / H), float(p["pulse_Wh"]) / 1000.0]])
		"intercom":
			out.append("Crew: " + "  ".join(_pair_lines()))
		"report":
			out.append_array(_report_lines(small))
		"debrief":
			out.append_array(_debrief_lines(small))
	if page in ["bay", "console", "intercom"]:
		var items := _items()
		var lo := 0
		var hi := items.size()
		var cap := 9 if small else 16
		if hi > cap:
			lo = clampi(sel - cap / 2, 0, hi - cap)
			hi = lo + cap
		for k in range(lo, hi):
			out.append(("[b][color=#ffd27a]> %s[/color][/b]" if k == sel else "[color=#b8c4d8]  %s[/color]") % str(items[k][1]))
		out.append("[color=#9fb4d0]%s next · %s do it%s[/color]" % [host.call("key", "exc.use"), host.call("key", "exc.ops"),
			"" if items.size() <= cap else " · %d of %d" % [sel + 1, items.size()]])
	if not small:
		out.append("[font_size=12][color=#8090a0]Engineering model: both rings' cabin heat, humidity and CO2, the cooling chain, buses and stores (src/wayfarer/ring_services.py, SYS-003, PROTOTYPE). Scenario %s (%s): the premise, crew, timing and criteria are training values.[/color][/font_size]" % [sc["scenario"]["id"], sc["scenario"]["status"]])
	text.text = "\n".join(out)
	rendered_compact = small
	panel.visible = true
	panel.reset_size()

func _pair_lines() -> Array:
	var out := []
	for pr in ["A", "B", "C"]:
		var ms := people.filter(func(q): return str(q["pair"]) == pr)
		var s: String = str(pr) + " "
		var where := []
		for q in ms:
			var w := "ring %s" % q["ring"] if str(q["ring"]) != "X" else "crossing"
			if q["task"] != null:
				var ph: Array = q["task"]["plan"][int(q["task"]["k"])]
				w = {"cross": "crossing to ring %s" % ph[2], "isolate": "working in ring B", "deliver": "delivering"}.get(str(ph[0]), w)
			where.append(("you " if str(q["id"]) == "A-1" else "") + w)
		s += " / ".join(where)
		out.append(s)
	return out

func _report_lines(small: bool) -> Array:
	var out := []
	for r in rs.RINGS:
		var rr: Dictionary = st["ring"][r]
		var ms := []
		for e in rs.equipment:
			var s := _state_of(r, str(e["id"]))
			if s != "RUN":
				ms.append("%s %s" % [e["id"], s])
		out.append("%s · dew %.1f C · %s" % [_ring_line(r), rs.dew_point(float(rr["T"]), float(rr["m_w"])) - 273.15,
			"all machines running" if ms.is_empty() else ", ".join(ms)])
	out.append(_power_line())
	out.append("Crew: " + "  ".join(_pair_lines()))
	var moved := []
	for k in st["parts"]:
		if str(st["parts"][k]["at"]) != str(start_parts[k]):
			moved.append("%s at %s" % [k, st["parts"][k]["at"]])
	out.append("Parts moved: " + (", ".join(moved) if not moved.is_empty() else "none"))
	out.append("[color=#9fb4d0]Limits where people live: 18-27 C, under 75 % RH (band 40-50 %), CO2 under 0.5 % (target 0.3 %). %s back.[/color]" % host.call("key", "exc.ops"))
	return out

func _family_text(f: String) -> String:
	var fams: Array = sc["debrief"]["families"]
	var idx := {"BORROW_FAN": 0, "BORROW_FAN_PUMP": 1, "RELOCATE": 2, "CANNIBALIZE": 3, "NO_REPAIR": 4, "SHED_GARDEN": 0, "SHED_DARK_B": 1,
		"SHED_ECONOMY": 2, "KEEP_GARDEN": 3, "PACKS_ONLY": 4}
	return str(fams[idx[f]]) if idx.has(f) and int(idx[f]) < fams.size() else f

func _debrief_lines(small: bool) -> Array:
	var d := debrief_cache
	if d.is_empty():
		return ["(the projection is still running)"]
	var out := []
	var v: Dictionary = d["watch"]["verdict"]
	var m: Dictionary = d["metrics"]
	var res := str(v["result"])
	if deb_page == 0:
		var head: String = {"STABLE": "Stable", "TEMPORARY": "Temporary", "CO2_LIMIT": "Operational failure: CO2", "HEAT_LIMIT": "Operational failure: heat",
			"HUMIDITY_LIMIT": "Operational failure: humidity", "COLD_LIMIT": "Operational failure: cold", "RESTART_FAILED": "Operational failure: no restart"}.get(res, res)
		if bool(v["degraded"]):
			head += ", degraded (humidity above its band or CO2 above its target for a time)"
		out.append("[b]%s.[/b] %s." % [head, _verdict_text(res)])
		out.append("What happened: %s" % str(sc["premise"]["basis"]).get_slice(". ", 0) + ".")
		var did := []
		for e in d["decisions"]:
			did.append("T+%s %s" % [_hm(float(e[0]) * H), _decision_text(str(e[1]), e[2])])
		out.append("What you did: " + (" · ".join(did) if not did.is_empty() else "nothing"))
		out.append("What you chose: " + _family_text(str(d["watch"]["family"])))
		var cost := []
		if not (m["parts_from_ring_b"] as Array).is_empty():
			cost.append("parts taken from ring B: " + ", ".join(m["parts_from_ring_b"]))
		if float(m["shed_kWh"]) > 0.5:
			cost.append("%.0f kWh of service switched off where people live" % float(m["shed_kWh"]))
		if not (m["dark_rings"] as Array).is_empty():
			cost.append("ring %s left dark" % ", ".join(m["dark_rings"]))
		if not (m["economy"] as Array).is_empty():
			cost.append("heat pump on economy in ring %s" % ", ".join(m["economy"]))
		var host_l := []
		for r in rs.RINGS:
			if bool(m["hostable"][r]):
				host_l.append(r)
		cost.append("rings able to host the crew afterwards: %s" % (", ".join(host_l) if not host_l.is_empty() else "none"))
		out.append("What it cost: " + "; ".join(cost) + ".")
		var lim := []
		for k in ["co2_limit", "heat_limit", "humidity_limit", "cold_limit"]:
			if float(v["crew_h"][k]) > 0.0:
				lim.append("%s %.0f crew-h" % [k.replace("_limit", ""), float(v["crew_h"][k])])
		var ex = v.get("range_exit")
		if ex == null:
			out.append("Where people lived: peak CO2 %.2f %%, peak %.1f C, peak RH %d %%%s." % [float(v["peak"]["co2_pct"]), float(v["peak"]["T_C"]),
				int(round(100.0 * float(v["peak"]["rh"]))), "" if lim.is_empty() else " · over a limit: " + ", ".join(lim)])
		else:
			out.append(_range_exit_line(v, ex, lim))
	elif deb_page == 1:
		out.append("[b]The ship at 7 days[/b]")
		for r in rs.RINGS:
			var q: Dictionary = d["rings"][r]
			out.append("Ring %s: %d aboard, %s, CO2 %.2f %%" % [r, int(q["occupants"]), _th_text(float(q["T_C"]), float(q["rh"])), float(q["co2_pct"])])
		out.append("Battery %.0f kWh (used %.0f) · packs %.1f / %.1f kWh%s%s" % [float(m["battery_kWh"]), float(m["battery_used_kWh"]), float(m["packs_kWh"]["A"]),
			float(m["packs_kWh"]["B"]), "" if m["restart"] == null else " · restart window: battery %.0f kWh, %s" % [float(m["restart"]["battery_kWh"]), "fired" if m["restart"]["ok"] else "NOT ENOUGH"],
			"" if (m["trips"] as Array).is_empty() else " · trips: " + ", ".join((m["trips"] as Array).map(func(x): return "bus %s at T+%s" % [x[1], _hm(float(x[0]) * H)]))])
		out.append("Unresolved machines: %s · crossings %d · refused requests %d" % [", ".join(m["unresolved"]) if not (m["unresolved"] as Array).is_empty() else "none",
			int(m["crossings"]), int(m["refusals"])])
		var led := 0.0
		for k in d["ledgers"]:
			led = maxf(led, absf(float(d["ledgers"][k])))
		out.append("[color=#9fb4d0]Every inventory closes (water, CO2, cabin heat, coolant, battery, packs, energy served, parts): largest error %s.[/color]" % String.num_scientific(snappedf(led, 1e-15)))
	elif deb_page == 2:
		out.append("[b]Crew limit-hours (where each person lived; habitability limits, not injury thresholds)[/b]")
		var vv: Dictionary = d["watch"]["verdict"]
		for k in vv["crew_h"]:
			out.append("%s: %.1f crew-hours" % [str(k).replace("_", " "), float(vv["crew_h"][k])])
		out.append("First limit crossings: %s" % ", ".join(vv["first_cross_h"].keys().filter(func(k): return vv["first_cross_h"][k] != null).map(func(k): return "%s T+%.1f h" % [k, float(vv["first_cross_h"][k])])) if vv["first_cross_h"].values().any(func(x): return x != null) else "First limit crossings: none")
	else:
		out.append("[b]The same model, the reference strategies (computed, not graded)[/b]")
		for c in doc["references"]:
			if str(c["name"]).begins_with("replay") or str(c["name"]) == "refused":
				continue
			var cd: Dictionary = c["debrief"]
			var cm: Dictionary = cd["metrics"]
			var cv: Dictionary = cd["watch"]["verdict"]
			out.append("· %s: %s%s · from ring B %d · shed %.0f kWh%s%s" % [c["name"], cv["result"], " (degraded)" if cv["degraded"] else "",
				(cm["parts_from_ring_b"] as Array).size(), float(cm["shed_kWh"]), "" if cm["restart"] == null else " · restart battery %.0f kWh" % float(cm["restart"]["battery_kWh"]),
				"" if small else " · " + str(c["description"]).left(90)])
		out.append("[color=#9fb4d0]%s Replay (%s) to try another way.[/color]" % [sc["debrief"]["notes"], host.call("key", "exc.ops")])
	return out

func _decision_text(k: String, a: Array) -> String:
	match k:
		"isolate": return "%s %s" % [a[0], "isolated" if a[1] else "returned to service"]
		"removed": return "part %s removed" % a[1]
		"installed": return "%s installed in %s" % [a[1], str(a[0]).trim_prefix("A.")]
		"take": return "took %s" % a[0]
		"stow": return "part to the shelf"
		"switch": return "ring %s %s %s" % [a[0], a[1], "on" if a[2] else "off"]
		"tie": return "tie %s" % ("closed" if a[0] else "opened")
		"reset": return "bus %s reset" % a[0]
		"economy": return "ring %s heat pump %s" % [a[0], "economy" if a[1] else "normal"]
		"order": return "%s %s %s" % ["partner" if str(a[0]) == "A" else "pair " + str(a[0]), a[1], a[2]]
		"watch": return "watch declared"
		"restart": return "restart %s" % ("fired" if a[0] else "FAILED")
	return k

func update_panel(size: Vector2) -> void:
	if not verified:
		return
	eq.board.text = board_text()
	eq.fit_display()
	if panel.visible and WfInput.compact() != rendered_compact:
		_render()
	WfPagePanel.place(panel, text, size, 560.0)

func record() -> Dictionary:
	if not verified:
		return {"verified": false, "errors": errors.slice(0, 2)}
	var ppl := []
	for q in people:
		ppl.append({"id": q["id"], "ring": q["ring"], "node": q["node"], "task": q["task"] != null})
	var rings := {}
	for r in rs.RINGS:
		var rr: Dictionary = st["ring"][r]
		rings[r] = {"T_C": snappedf(float(rr["T"]) - 273.15, 1e-4), "rh": snappedf(rs.rh(float(rr["T"]), float(rr["m_w"])), 1e-5),
			"co2_pct": snappedf(100.0 * rs.x_co2(float(rr["T"]), float(rr["m_c"])), 1e-5), "occ": st["occ"][r]}
	return {"verified": true, "scenario": sc["scenario"]["id"], "phase": phase, "stage": sc["stages"][stage()]["id"], "t_s": snappedf(t(), 0.01),
		"real_s": snappedf(real_s, 0.01), "paused": paused(), "scale": scale(), "page": page, "sel": sel, "runs": runs, "people": ppl, "rings": rings,
		"hands": hands, "job": job, "tie": st["tie"], "breaker": st["breaker"], "E_kWh": snappedf(float(st["E"]) / 3.6e6, 1e-3), "log": log.slice(-12),
		"notes": notes, "frame_cost_us": frame_cost, "verdict": watch.get("verdict", {}), "family": family() if phase == "DONE" else "",
		"items": _items().map(func(it): return str(it[1])) if page in ["bay", "console", "intercom"] else [], "board": eq.board.text}
