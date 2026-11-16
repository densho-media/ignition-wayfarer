class_name WfShipOpsCheck
extends RefCounted
## Deadship DS-2C "Borrowed Air" / DS-3 "Dark Bus" check (-- --borrowed-air|--dark-bus --check-ship-ops [--strategy=<name>]; the browser's
## --await-player). First every packaged reference case replays in this runtime to the packaged checkpoints and debrief (the browser: a
## few). Then one strategy is played through the trainee's own requests, walking between ring A's sector 3 ECLSS bay and the sector 2 ops
## console: a page pauses the clock; work on a running machine and a switch away from the console are refused and change nothing; parts
## move only by the trainee's work at the bay (which takes its time and pauses while a page is open) or a pair's errand (which takes the
## crossings); the watch holds the ship as declared, runs the same model and the 7-day projection; the debrief's numbers are the run's own
## and every ledger closes. The run ends with a replay from the exact start. Prints one WF_GODOT_SHIP_OPS line and quits.

const PARITY_WEB := {"ds2c": ["borrow_fan_shed", "relocate"], "ds3": ["shed_garden", "keep_garden"]}
const DEFAULT := {"ds2c": "borrow_fan_shed", "ds3": "shed_garden"}
const WANT := {
	"borrow_fan_shed": ["BORROW_FAN", "STABLE"], "borrow_fan_pump": ["BORROW_FAN_PUMP", "STABLE"], "relocate": ["RELOCATE", "STABLE"],
	"cannibalize": ["CANNIBALIZE", "HEAT_LIMIT"],
	"shed_garden": ["SHED_GARDEN", "STABLE"], "shed_dark_b": ["SHED_DARK_B", "STABLE"], "shed_economy": ["SHED_ECONOMY", "STABLE"],
	"keep_garden": ["KEEP_GARDEN", "CO2_LIMIT"], "short_reserve": ["SHED_GARDEN", "RESTART_FAILED"]}

var h: WfExcursion
var so: WfShipOps
var pl: WfCheckPlayer
var fails: Array = []
var notes := {}
var t0 := 0
var strategy := ""

func fail(msg: String) -> void:
	fails.append(msg)
	push_warning("SHIP OPS check: " + msg)

func _ticks(n: int) -> void:
	for i in n:
		await h.get_tree().physics_frame

func _wait(cond: Callable, limit_s: float, what: String) -> bool:
	var n := 0
	while not cond.call():
		await _ticks(1)
		n += 1
		if n > int(limit_s * 60.0):
			fail("waited %d s for %s" % [int(limit_s), what])
			return false
	return true

func _trace(m: String) -> void:
	print("SO_TRACE %.1f s real, ship %.0f s, %s: %s" % [(Time.get_ticks_msec() - t0) / 1000.0, so.t(), so.phase, m])

func run(host: WfExcursion) -> void:
	h = host
	t0 = Time.get_ticks_msec()
	await _ticks(30)
	so = h.ship_ops
	if so == null or not so.verified:
		fail("the training is unavailable: %s" % (str(so.errors) if so != null else "not created"))
		_finish()
		return
	strategy = DEFAULT[so.key]
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--strategy="):
			strategy = a.trim_prefix("--strategy=")
	notes["scenario"] = so.sc["scenario"]["id"]
	notes["strategy"] = strategy
	notes["verify_at_load_ms"] = so.notes.get("verify_ms", -1)
	notes["model_verify_ms"] = so.notes.get("model_verify_ms", -1)
	pl = WfCheckPlayer.new(h)
	# learning stations stay as they are; mark them seen so walking past them does not stop the check (as check_deadship)
	if h.learning != null:
		for st in h.learning.stations:
			h.learning.done[st["rec"]["id"]] = true
	_parity()
	so.begin()
	await _ticks(5)
	await _play()
	_finish()

# ---- parity ---------------------------------------------------------------------------------------------------------------------------------

func _parity() -> void:
	var timing := {}
	var only: Array = PARITY_WEB[so.key] if OS.has_feature("web") else []
	var saved_host := so.host
	so.host = null
	for c in so.doc["references"]:
		if not only.is_empty() and not str(c["name"]) in only:
			continue
		var t := Time.get_ticks_usec()
		var got := so.play(c["actions"])
		timing[c["name"]] = snappedf((Time.get_ticks_usec() - t) / 1e6, 0.01)
		var bad := so.compare(got, c["checkpoints"], str(c["name"]))
		if got.size() != (c["checkpoints"] as Array).size():
			bad.append("%s: %d checkpoints, the package has %d" % [c["name"], got.size(), (c["checkpoints"] as Array).size()])
		bad.append_array(so.compare_debrief(so.debrief(), c["debrief"], str(c["name"])))
		for b in bad.slice(0, 3):
			fail("parity " + str(b))
	so.host = saved_host
	notes["parity_cases"] = timing.size()
	notes["parity_s"] = timing

# ---- the player's requests -------------------------------------------------------------------------------------------------------------------

func _ui_says(action: String, label: String) -> void:
	var acts: Array = h.touch_state().get("actions", [])
	if not acts.any(func(a): return a[0] == action and a[1] == label):
		fail("touch: no '%s' button for %s (%s)" % [label, action, str(acts)])

func _use(label: String, done: Callable) -> void:
	await pl.act("exc.use", label, h.use, done)

func _ops(label: String, done: Callable) -> void:
	_ui_says("exc.ops", label)
	await pl.act("exc.ops", label, h.ops, done)

func _select(kind: String, args: Array = []) -> bool:
	var items := so._items()
	var want := -1
	for i in items.size():
		if str(items[i][0]) == kind and (args.is_empty() or items[i].slice(2, 2 + args.size()) == args):
			want = i
			break
	if want < 0:
		fail("no %s %s item on the %s page: %s" % [kind, str(args), so.page, str(items.map(func(it): return it[1]))])
		return false
	var guard := 0
	while so.sel != want and guard < 40:
		var nxt := (so.sel + 1) % so._items().size()
		await _use("Use · next item", func(): return so.sel == nxt)
		guard += 1
	return so.sel == want

func _do(kind: String, args: Array, done: Callable) -> void:
	if await _select(kind, args):
		await _ops(so.ops_label(), done)

func _close_page() -> void:
	if so.page == "":
		return
	if so.page in ["bay", "console", "intercom"]:
		await _do("close", [], func(): return so.page == "")
	elif so.page == "report":
		await _ops("Ops · back", func(): return so.page == "intercom")
		await _do("close", [], func(): return so.page == "")
	else:
		await _ops(so.ops_label(), func(): return so.page == "")

func _walk_to(id: String) -> bool:
	if so.eq.in_reach(h.actor.global_position, h.walk_zone, id):
		return true
	_trace("walk to " + id)
	var ok := await pl.walk_until(func(): return so.eq.in_reach(h.actor.global_position, h.walk_zone, id), func(): return so.eq.centre(id),
		float(so.eq.points[id]["reach"]), "RING_A", float(so.eq.points[id]["reach"]) - 0.6)
	fails.append_array(pl.fails)
	pl.fails = []
	h.walk_override = Vector3.ZERO
	await _ticks(10)
	if not ok:
		fail("the %s was not reached" % id)
	return ok

func _open(id: String) -> void:
	if so.page == id:
		return
	await _close_page()
	await _walk_to(id)
	await _use("Use · %s" % ("ECLSS bay" if id == "bay" else "ops console"), func(): return so.page == id)

func _intercom() -> void:
	if so.page == "intercom":
		return
	if so.page in ["bay", "console"]:
		await _do("intercom", [], func(): return so.page == "intercom")
		if so.page != "intercom":
			fail("the intercom did not open from the %s page (sel %d of %d, ops label %s, on ring A %s)" % [so.page, so.sel, so._items().size(), so.ops_label(), so.on_ring_a()])
	else:
		await _close_page()
		await _ops(so.ops_label(), func(): return so.page != "")
		if so.page in ["bay", "console"]:            # at a bay or the console, Ops opens it: the intercom is its last item
			await _do("intercom", [], func(): return so.page == "intercom")
		if so.page != "intercom":
			fail("the intercom did not open (page %s)" % so.page)

## Let ship time run with no page open (the clock runs only then) until `cond`.
func _let_run(cond: Callable, limit_s: float, what: String) -> void:
	await _close_page()
	await _wait(cond, limit_s, what)

func _still(name: String, id: String) -> void:
	await pl.shot(name, so.eq.centre(id))

# ---- the play -------------------------------------------------------------------------------------------------------------------------------

func _play() -> void:
	if so.phase != "LIVE" or so.t() != 0.0:
		fail("start: want LIVE at t 0, got %s %s" % [so.phase, so.t()])
	notes["start_config"] = so.config()
	await _wait(func(): return so.alerted, 30.0, "the alert")
	# a page pauses the clock
	await _intercom()
	var tp := so.t()
	await _ticks(60)
	if so.t() != tp:
		fail("the clock ran with a page open (%.0f -> %.0f s)" % [tp, so.t()])
	await _close_page()
	if so.key == "ds2c":
		await _borrowed_air()
	else:
		await _dark_bus()
	if not fails.is_empty() and so.phase == "LIVE":
		return
	await _watch()
	await _debrief()
	await _replay()

func _refusals_ds2c() -> void:
	# work on a running machine is refused and changes nothing
	await _open("bay")
	var cfg := so.config()
	await _do("remove", ["CO2.FAN"], func(): return so.log[-1][1] == "remove")
	if str(so.log[-1][3]) == "" or so.config() != cfg or so.job != null:
		fail("removing a running unit's fan was not refused: %s" % str(so.log[-1]))
	notes["refusal_running"] = so.log[-1][3]
	# switching is refused away from the console (the request reaches the model's own rule)
	var r := so.act("switch", ["A", "GARDEN", false])
	if r == "" or so.config() != cfg:
		fail("switching at the bay was not refused")
	notes["refusal_switch_at_bay"] = r

func _inspect_bay(machines: Array) -> void:
	await _open("bay")
	for e in machines:
		await _do("inspect", [e], func(): return so.inspected.has(e))
	await _still("SO_%s_1_bay" % so.key, "bay")

func _bay_job(kind: String, slot: String) -> void:
	await _open("bay")
	await _do(kind, [slot], func(): return so.job != null or str(so.log[-1][3]) != "")
	if so.job == null:
		fail("%s %s did not start: %s" % [kind, slot, so.log[-1][3]])
		return
	var tp := so.t()
	await _ticks(30)
	if so.t() != tp:
		fail("work progressed with the page open")
	await _let_run(func(): return so.job == null, 120.0, "%s %s" % [kind, slot])

func _fit(slot: String, part: String, machine: String) -> void:
	await _open("bay")
	await _do("isolate", [machine, true], func(): return bool(so.st["ring"]["A"]["isolated"][machine]))
	await _bay_job("remove", slot)
	await _open("bay")
	await _do("stow", [], func(): return so.hands == null)
	await _do("take", [part], func(): return so.hands == part)
	await _bay_job("install", slot)
	await _open("bay")
	await _do("isolate", [machine, false], func(): return not bool(so.st["ring"]["A"]["isolated"][machine]))
	if str(so.st["parts"][part]["at"]) != "A." + slot:
		fail("%s is at %s, not in %s" % [part, so.st["parts"][part]["at"], slot])

func _borrowed_air() -> void:
	await _inspect_bay(["CO2", "P1", "CHX"])
	await _refusals_ds2c()
	match strategy:
		"borrow_fan_shed", "borrow_fan_pump":
			await _intercom()
			await _do("order", ["B", "fetch", "B.CO2.FAN"], func(): return so.people[2]["task"] != null)
			if strategy == "borrow_fan_pump":
				await _do("order", ["C", "fetch", "B.P1.PUMP"], func(): return so.people[4]["task"] != null)
			var t_order := so.t()
			if strategy == "borrow_fan_shed":
				await _open("console")
				for e in ["GARDEN", "LAB"]:
					await _do("switch", ["A", e, false], func(): return not bool(so.st["ring"]["A"]["on"][e]))
				await _still("SO_ds2c_2_console", "console")
			await _walk_to("bay")
			await _let_run(func(): return str(so.st["parts"]["B.CO2.FAN"]["at"]) == "A.SHELF", 300.0, "ring B's fan on the shelf")
			var took := so.t() - t_order
			notes["fetch_ship_s"] = took
			var want := 2.0 * float(so.sc["crew"]["transfer_s"]) + float(so.sc["crew"]["fetch_work_s"])
			if took < want - 1e-6:
				fail("the fetch took %.0f s of ship time, less than its %.0f s" % [took, want])
			if not bool(so.st["ring"]["B"]["isolated"]["CO2"]) or so.hostable("B"):
				fail("ring B still has its CO2 unit after the fetch")
			await _fit("CO2.FAN", "B.CO2.FAN", "CO2")
			if strategy == "borrow_fan_pump":
				await _let_run(func(): return str(so.st["parts"]["B.P1.PUMP"]["at"]) == "A.SHELF", 300.0, "ring B's pump on the shelf")
				await _fit("P1.PUMP", "B.P1.PUMP", "P1")
		"relocate":
			await _open("console")
			if so.view_ring != "B":
				await _do("view", [], func(): return so.view_ring == "B")
			for e in ["CO2", "GARDEN", "LIGHT"]:
				await _do("switch", ["B", e, true], func(): return bool(so.st["ring"]["B"]["on"][e]))
			await _do("switch", ["B", "HP", false], func(): return not bool(so.st["ring"]["B"]["on"]["HP"]))
			await _let_run(func(): return float(so.st["ring"]["B"]["T"]) > float(so.p["T_min"]) + 1.5, 300.0, "ring B to warm")
			await _open("console")
			if so.view_ring != "B":
				await _do("view", [], func(): return so.view_ring == "B")
			for e in ["HP", "GALLEY", "LAB"]:
				await _do("switch", ["B", e, true], func(): return bool(so.st["ring"]["B"]["on"][e]))
			await _intercom()
			await _do("everyone", [], func(): return so.people[0]["task"] != null)
			await _let_run(func(): return so.people.all(func(q): return str(q["ring"]) == "B" and q["task"] == null), 300.0, "everyone in ring B")
			if int(so.st["occ"]["B"]) != 6 or int(so.st["occ"]["A"]) != 0:
				fail("relocation left %s" % str(so.st["occ"]))
			var r := so.act("isolate", ["CO2", true])
			if r == "":
				fail("the trainee in ring B could still work at ring A's bay")
		"cannibalize":
			await _open("bay")
			await _do("isolate", ["CO2", true], func(): return bool(so.st["ring"]["A"]["isolated"]["CO2"]))
			await _bay_job("remove", "CO2.FAN")
			await _open("bay")
			await _do("stow", [], func(): return so.hands == null)
			await _do("isolate", ["CHX", true], func(): return bool(so.st["ring"]["A"]["isolated"]["CHX"]))
			await _bay_job("remove", "CHX.FAN")
			await _bay_job("install", "CO2.FAN")
			await _open("bay")
			await _do("isolate", ["CO2", false], func(): return not bool(so.st["ring"]["A"]["isolated"]["CO2"]))
		_:
			fail("no strategy %s for DS-2C" % strategy)

func _dark_bus() -> void:
	await _open("console")
	await _still("SO_ds3_1_console", "console")
	if not so.inspected.has("BUS.B"):
		fail("opening the console did not read the overview")
	# the tie with everything on asks BC-A for more than its rating: it trips (only in a scratch copy of the run: the model's own rule)
	var probe := so.st.duplicate(true)
	so.rs.set_tie(probe, true)
	so.rs.step(probe, 10.0)
	notes["tie_with_everything_trips"] = not bool(probe["breaker"]["A"])
	if bool(probe["breaker"]["A"]):
		fail("closing the tie with every load on did not trip")
	var shed: Array = {"shed_garden": ["GARDEN", "GALLEY", "LAB"], "shed_dark_b": ["GARDEN", "GALLEY"], "shed_economy": ["GARDEN", "GALLEY", "LAB"],
		"keep_garden": ["LAB", "GALLEY", "LIGHT"], "short_reserve": ["GARDEN", "GALLEY"]}.get(strategy, [])
	if shed.is_empty():
		fail("no strategy %s for DS-3" % strategy)
		return
	for e in shed:
		await _do("switch", ["A", e, false], func(): return not bool(so.st["ring"]["A"]["on"][e]))
	if strategy in ["shed_dark_b", "keep_garden"]:
		await _do("view", [], func(): return so.view_ring == "B")
		for e in ["CHX", "P1", "P2", "HP", "TCC", "VENT", "AV"]:
			await _do("switch", ["B", e, false], func(): return not bool(so.st["ring"]["B"]["on"][e]))
		await _do("view", [], func(): return so.view_ring == "A")
	if strategy in ["shed_economy", "keep_garden"]:
		await _do("economy", ["A", true], func(): return bool(so.st["ring"]["A"]["economy"]))
	await _do("tie", [true], func(): return bool(so.st["tie"]))
	await _let_run(func(): return so.st.has("plan") and bool(so.st["plan"]["live"]["B"]), 30.0, "bus B live on the tie")
	await _still("SO_ds3_2_tie", "console")

func _watch() -> void:
	_trace("watch")
	var cfg := so.config()
	notes["family_declared"] = so.family()
	await _intercom()
	await _do("watch", [], func(): return so.phase == "WATCH")
	if so.phase != "WATCH":
		fail("the watch did not start")
		return
	if so.watch["config"] != cfg:
		fail("starting the watch changed the configuration")
	var r := so.act("switch", ["A", "GARDEN", true])
	if r == "":
		fail("a switch was accepted during the watch")
	var t_real := Time.get_ticks_msec()
	await _wait(func(): return so.phase == "PROJECTION" or so.phase == "DONE", 300.0, "the watch to end")
	notes["watch_real_s"] = snappedf((Time.get_ticks_msec() - t_real) / 1000.0, 0.1)
	var t2 := Time.get_ticks_msec()
	await _wait(func(): return so.phase == "DONE" and so.page == "debrief", 180.0, "the projection and the debrief")
	notes["projection_real_s"] = snappedf((Time.get_ticks_msec() - t2) / 1000.0, 0.1)
	var post := so.log.filter(func(e): return float(e[0]) > float(so.watch["t0"]) + 1e-6 and str(e[3]) == "" and not str(e[1]) in ["restart", "arrived"])
	if not post.is_empty():
		fail("the watch ran operations: %s" % str(post.slice(0, 3)))

func _debrief() -> void:
	var d := so.debrief_cache
	if d.is_empty():
		fail("no debrief")
		return
	var v: Dictionary = d["watch"]["verdict"]
	notes["verdict"] = v["result"]
	notes["degraded"] = v["degraded"]
	notes["family"] = d["watch"]["family"]
	notes["metrics"] = d["metrics"]
	if WANT.has(strategy) and (str(d["watch"]["family"]) != str(WANT[strategy][0]) or str(v["result"]) != str(WANT[strategy][1])):
		fail("strategy %s gave %s %s, want %s" % [strategy, d["watch"]["family"], v["result"], WANT[strategy]])
	for k in d["ledgers"]:
		var lim := 1e3 if str(k).ends_with("_J") else 1e-9
		if absf(float(d["ledgers"][k])) > lim:
			fail("ledger %s open: %s" % [k, d["ledgers"][k]])
	var places := {}
	for k in so.st["parts"]:
		var a := str(so.st["parts"][k]["at"])
		if a != "A.SHELF" and places.has(a):
			fail("two parts at %s" % a)
		places[a] = true
	notes["frame_cost_us"] = so.frame_cost
	for k in so.DEB_PAGES:
		var pg := so.deb_page
		await _still("SO_%s_%d_debrief_%d" % [so.key, 3 + k, k + 1], "bay")
		await _use("Use · next page" if pg < so.DEB_PAGES - 1 else "Use · close", func(): return so.deb_page != pg)
	if so.page != "":
		fail("the debrief did not close after its last page")

func _replay() -> void:
	var runs := so.runs
	await _ops("Ops · replay", func(): return so.runs > runs)
	await _ticks(5)
	if so.phase != "LIVE" or so.t() > 60.0 or so.config() != notes["start_config"]:
		fail("replay did not restart from the start: %s t %s" % [so.phase, so.t()])
	notes["replay"] = {"runs": so.runs, "t_s": so.t()}

func _finish() -> void:
	fails.append_array(pl.fails)
	if so != null and so.verified:
		notes["record"] = so.record()
	var out := {"result": "PASS" if fails.is_empty() else "FAIL", "fails": fails, "notes": notes,
		"wall_s": snappedf((Time.get_ticks_msec() - t0) / 1000.0, 0.1), "physics_frames": Engine.get_physics_frames()}
	print("WF_GODOT_SHIP_OPS " + JSON.stringify(out))
	h.get_tree().quit(0 if fails.is_empty() else 1)
