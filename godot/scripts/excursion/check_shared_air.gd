class_name WfSharedAirCheck
extends RefCounted
## Deadship DS-2B "Shared Air" check (-- --shared-air --check-shared-air [--strategy=isolate|purge|separate|nocontain]; the browser's
## --await-player). First every packaged reference case replays in this runtime to the packaged checkpoints and debrief (the browser: three
## of them). Then one strategy is played through the trainee's own requests: the clock pauses with a page open; containment is refused
## away from the store, takes its full work at the store, pauses when the trainee steps away and keeps its progress; the bay's controls
## and the intercom's orders act on the model and refuse what cannot be done (a sealed route, a corridor) without changing anything; a
## door close is refused while a pair stands in its doorway; the watch holds the ring (doors refused), runs the same model to 24 h and
## the 7-day projection; the debrief's numbers are the run's own and every species' ledger closes. The default strategy ends with a
## replay from the exact start. Prints one WF_GODOT_SHARED_AIR line and quits.

const PARITY_WEB := ["isolate", "doorway", "watch_restore"]

var h: WfExcursion
var sa: WfSharedAir
var pl: WfCheckPlayer
var fails: Array = []
var notes := {}
var t0 := 0
var strategy := "isolate"

func fail(msg: String) -> void:
	fails.append(msg)
	push_warning("SHARED AIR check: " + msg)

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

func run(host: WfExcursion) -> void:
	h = host
	t0 = Time.get_ticks_msec()
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--strategy="):
			strategy = a.trim_prefix("--strategy=")
	notes["strategy"] = strategy
	await _ticks(30)
	sa = h.shared_air
	if sa == null or not sa.verified:
		fail("Shared Air is unavailable: %s" % (str(sa.errors) if sa != null else "not created"))
		_finish()
		return
	notes["verify_at_load_ms"] = sa.notes.get("verify_ms", -1)
	pl = WfCheckPlayer.new(h)
	_parity()
	sa.begin()
	await _ticks(5)
	await _play()
	_finish()

# ---- parity ---------------------------------------------------------------------------------------------------------------------------------

func _parity() -> void:
	var timing := {}
	var only: Array = PARITY_WEB if OS.has_feature("web") else []
	for c in sa.doc["reference"]:
		if not only.is_empty() and not str(c["name"]) in only:
			continue
		var t := Time.get_ticks_usec()
		var got := sa.play(c["actions"])
		timing[c["name"]] = snappedf((Time.get_ticks_usec() - t) / 1e6, 0.01)
		var bad := sa.compare(got, c["checkpoints"], str(c["name"]))
		if got.size() != (c["checkpoints"] as Array).size():
			bad.append("%s: %d checkpoints, the package has %d" % [c["name"], got.size(), (c["checkpoints"] as Array).size()])
		bad.append_array(_debrief_parity(sa.debrief(), c["debrief"], str(c["name"])))
		var refused := sa.log.filter(func(e): return str(e[3]) != "").size()
		var want_refused := (c["log"] as Array).filter(func(e): return str(e[3]) != "").size()
		if refused != want_refused:
			bad.append("%s: %d refusals, the reference %d" % [c["name"], refused, want_refused])
		for b in bad.slice(0, 3):
			fail("parity " + str(b))
	notes["parity_cases"] = timing.size()
	notes["parity_s"] = timing

func _near(a, b) -> bool:
	if a == null or b == null:
		return a == b
	return absf(float(a) - float(b)) <= 1e-9 + 1e-8 * absf(float(b))

func _debrief_parity(d: Dictionary, w: Dictionary, name: String) -> Array:
	var bad := []
	for k in ["released_g", "retained_g", "removed_g", "airborne_g", "co2_max_pct", "contained_at_h"]:
		if not _near(d[k], w[k]):
			bad.append("%s debrief %s %s, reference %s" % [name, k, d[k], w[k]])
	for k in w["clear_h"]:
		if not _near(d["clear_h"][k], w["clear_h"][k]):
			bad.append("%s debrief %s reusable at %s h, reference %s" % [name, k, d["clear_h"][k], w["clear_h"][k]])
	for i in (w["people"] as Array).size():
		for k in ["peak_ppm", "max_1h_ppm", "max_24h_ppm", "mean_7d_ppm", "dose_ppm_h", "co2_above_target_h"]:
			if not _near(d["people"][i][k], w["people"][i][k]):
				bad.append("%s debrief %s %s %s, reference %s" % [name, w["people"][i]["id"], k, d["people"][i][k], w["people"][i][k]])
	if str(d["watch"]["verdict"]["result"]) != str(w["watch"]["verdict"]["result"]) or str(d["watch"]["family"]) != str(w["watch"]["family"]):
		bad.append("%s: %s %s, reference %s %s" % [name, d["watch"]["family"], d["watch"]["verdict"]["result"], w["watch"]["family"], w["watch"]["verdict"]["result"]])
	return bad

# ---- the play -------------------------------------------------------------------------------------------------------------------------------

func _ui_says(action: String, label: String) -> void:
	var acts: Array = h.touch_state().get("actions", [])
	if not acts.any(func(a): return a[0] == action and a[1] == label):
		fail("touch: no '%s' button for %s (%s)" % [label, action, str(acts)])

func _use(label: String, done: Callable) -> void:
	await pl.act("exc.use", label, h.use, done)

func _ops(label: String, done: Callable) -> void:
	_ui_says("exc.ops", label)
	await pl.act("exc.ops", label, h.ops, done)

## Move the page's selection to the first item of `kind` (matching args), Use by Use as a player does.
func _select(kind: String, args: Array = []) -> bool:
	var items := sa._items()
	var want := -1
	for i in items.size():
		if str(items[i][0]) == kind and (args.is_empty() or items[i].slice(2, 2 + args.size()) == args):
			want = i
			break
	if want < 0:
		fail("no %s %s item on the %s page: %s" % [kind, str(args), sa.page, str(items.map(func(it): return it[1]))])
		return false
	var guard := 0
	while sa.sel != want and guard < 20:
		var nxt := (sa.sel + 1) % sa._items().size()
		await _use("Use · next item", func(): return sa.sel == nxt)
		guard += 1
	return sa.sel == want

func _op_label() -> String:
	return sa.ops_label()

func _do(kind: String, args: Array, done: Callable) -> void:
	if await _select(kind, args):
		await _ops(_op_label(), done)

func _page(pg: String) -> void:
	if sa.page == pg:
		return
	if pg == "bay" and sa.page != "":
		await _close_page()
	if pg == "intercom" and sa._at() == "bay":
		await _page("bay")
		await _do("intercom", [], func(): return sa.page == "intercom")
	elif pg == "intercom":
		if sa.page != "":
			await _close_page()
		await _ops("Ops · intercom", func(): return sa.page == "intercom")
	elif pg == "bay":
		await _ops("Ops · ECLSS controls", func(): return sa.page == "bay")

func _close_page() -> void:
	if sa.page == "":
		return
	if sa.page == "bay" or sa.page == "intercom":
		await _do("close", [], func(): return sa.page == "")
	else:
		await _ops(sa.ops_label(), func(): return sa.page != "report" and sa.page != "hygiene")
		if sa.page != "":
			await _do("close", [], func(): return sa.page == "")

func _trace(m: String) -> void:
	print("SA_TRACE %.1f s real, ship %.0f s, %s: %s" % [(Time.get_ticks_msec() - t0) / 1000.0, sa.t(), sa.phase, m])

func _walk_to_point(id: String) -> bool:
	_trace("walk to " + id)
	var ok := await pl.walk_until(func(): return sa.eq.in_reach(h.actor.global_position, h.walk_zone, id), func(): return sa.eq.centre(id),
		float(sa.eq.points[id]["reach"]), "RING_A", float(sa.eq.points[id]["reach"]) - 0.6)
	fails.append_array(pl.fails)
	pl.fails = []
	h.walk_override = Vector3.ZERO
	await _ticks(10)
	if not ok:
		fail("the %s was not reached" % id)
	return ok

func _open_doors() -> Array:
	var out := []
	for e in sa.ring.edges:
		if str(e["kind"]) == "door" and float(h.circ_doors[e["id"]]["target"]) > 0.0:
			out.append(str(e["id"]))
	return out

func _node() -> int:
	return sa.node_at(h.actor.global_position)

## Close a door as the player does, standing in compartment `side` about a metre from its leaf, facing it.
func _close_door(id: String, side: int) -> void:
	var col: Node3D = h.circ_doors[id]["collider"]
	var c := col.global_position
	var normal := col.global_transform.basis.z.normalized()
	var spot := c + normal * 1.1
	if sa.node_at(spot) != side:
		spot = c - normal * 1.1
	_trace("close %s from %s" % [id, sa.ids[side]])
	await _go(spot, 0.3, 20.0)
	h.walk_override = Vector3.ZERO
	pl.ex.face(c - (h.actor.global_position + h.ref_basis().y * h.EYE_UP))
	await _ticks(10)
	await _use("Use · close door", func(): return float(h.circ_doors[id]["target"]) == 0.0)
	await _ticks(90)
	if float(h.circ_doors[id]["target"]) != 0.0:
		fail("%s did not close (%s)" % [id, h.refusal])

## The ring circuit's points, in order (the walk check's own route along the deck).
func _pts() -> Array:
	var out := []
	for q in h.stages["circuit"]["RING_A"]["circuit_m"]:
		out.append(WfLine.g(q))
	return out

## A plain walk to a point: no door is opened on the way (the route opens only the door it crosses).
func _go(target: Vector3, tol: float, limit_s: float, stop := Callable()) -> bool:
	var n := 0
	var best := INF
	var since := 0
	while n < int(limit_s * 60.0):
		if stop.is_valid() and stop.call():
			h.walk_override = Vector3.ZERO
			return true
		var up: Vector3 = h.actor.up_now
		var d := target - h.actor.global_position
		d -= up * d.dot(up)
		if d.length() < tol:
			h.walk_override = Vector3.ZERO
			return true
		h.walk_override = d.normalized()
		await _ticks(1)
		n += 1
		if d.length() < best - 0.05:
			best = d.length()
			since = 0
		else:
			since += 1
		if since > 60 * 6:
			break
	h.walk_override = Vector3.ZERO
	return false

func _door_near(id: String) -> bool:
	return h.actor.global_position.distance_to((h.circ_doors[id]["collider"] as Node3D).global_position) < 2.5

## Walk a compartment path along the circuit, opening each door the player crosses (Use, facing it) and closing it behind when asked.
func _walk_route(path: Array, close_behind: bool) -> bool:
	_trace("route %s%s" % [str(path), " closing behind" if close_behind else ""])
	var pts := _pts()
	for k in range(1, path.size()):
		var prev := sa.ring.index(str(path[k - 1]))
		var nxt := sa.ring.index(str(path[k]))
		var door := sa.door_between(prev, nxt)
		var i0 := -1                                   # the nearest circuit point in this compartment (never one back through a door)
		for i in pts.size():
			if sa.node_at(pts[i]) == prev and (i0 < 0 or (pts[i] as Vector3).distance_to(h.actor.global_position) < (pts[i0] as Vector3).distance_to(h.actor.global_position)):
				i0 = i
		if i0 < 0:
			fail("no circuit point in %s" % path[k - 1])
			return false
		var dir := 0
		for d in [1, -1]:
			for j in range(1, pts.size()):
				var n := sa.node_at(pts[posmod(i0 + d * j, pts.size())])
				if n == prev or n < 0:
					continue
				if n == nxt:
					dir = d
				break
			if dir != 0:
				break
		if dir == 0:
			fail("no circuit direction from %s to %s" % [path[k - 1], path[k]])
			return false
		var j2 := i0
		var guard := 0
		while _node() != nxt and guard < pts.size():
			j2 = posmod(j2 + dir, pts.size())
			guard += 1
			await _go(pts[j2], 0.45, 30.0, func(): return float(h.circ_doors[door]["target"]) < 1.0 and _door_near(door))
			if float(h.circ_doors[door]["target"]) < 1.0 and _door_near(door):
				var leaf := (h.circ_doors[door]["collider"] as Node3D).global_position
				await _go(leaf, 0.5, 10.0, func(): return h._door_in_reach() == door)
				pl.ex.face((h.circ_doors[door]["collider"] as Node3D).global_position - (h.actor.global_position + h.ref_basis().y * h.EYE_UP))
				await _ticks(5)
				await _use("Use · open door", func(): return float(h.circ_doors[door]["target"]) == 1.0)
				await _ticks(int(WfExcursion.CLOSURE_S * 60.0) + 2)
				j2 = posmod(j2 - dir, pts.size())
		while sa.node_at(pts[j2]) == nxt and h.actor.global_position.distance_to(pts[j2]) < 2.0 and guard < pts.size() * 2:
			j2 = posmod(j2 + dir, pts.size())         # a couple of metres in, clear of the doorway
			guard += 1
		if sa.node_at(pts[j2]) == nxt:
			await _go(pts[j2], 0.45, 20.0)
		h.walk_override = Vector3.ZERO
		if _node() != nxt:
			fail("route %s: did not reach %s (at %s; door %s target %s, %.2f m from its leaf; in reach %s; dir %d from point %d)" % [str(path), path[k],
				sa.ids[_node()] if _node() >= 0 else "?", door, h.circ_doors[door]["target"], h.actor.global_position.distance_to((h.circ_doors[door]["collider"] as Node3D).global_position),
				h._door_in_reach(), dir, i0])
			return false
		if close_behind and float(h.circ_doors[door]["target"]) > 0.0:
			await _close_door(door, nxt)
	return true

## To the bay from inside sector 3, straight.
func _to_bay() -> bool:
	await _go(sa.eq.centre("bay"), float(sa.eq.points["bay"]["reach"]) - 0.6, 30.0)
	h.walk_override = Vector3.ZERO
	await _ticks(10)
	if _at_bay():
		return true
	return await _walk_to_point("bay")

func _at_bay() -> bool:
	return sa.eq.in_reach(h.actor.global_position, h.walk_zone, "bay")

func _play() -> void:
	var src := sa.ring.index(str(sa.sc["source"]["compartment"]))
	notes["start_node"] = sa.ids[int(sa.people[0]["node"])]
	notes["body_node_at_start"] = sa.ids[sa.body_node()] if sa.body_node() >= 0 else "none"
	if sa.phase != "LIVE" or str(sa.ring.source["state"]) != "LEAKING" or sa.t() != 0.0 or sa.ring.vent != "ON" or not _open_doors().is_empty():
		fail("start: want LIVE, the source leaking, t 0, ventilation on, doors closed; got %s %s %s %s %s" % [sa.phase, sa.ring.source["state"], sa.t(), sa.ring.vent, _open_doors()])
	notes["start_in_reach_of_store"] = sa.eq.in_reach(h.actor.global_position, h.walk_zone, "hygiene")
	if sa.eq.in_reach(h.actor.global_position, h.walk_zone, "hygiene"):
		await _step_away()
	# a page pauses the clock: the intercom, and containment refused from it (nothing changes)
	await _ops("Ops · intercom", func(): return sa.page == "intercom")
	var t_paused := sa.t()
	await _ticks(60)
	if sa.t() != t_paused:
		fail("the clock ran with the intercom open (%s -> %s s)" % [t_paused, sa.t()])
	var cp0 := sa.checkpoint()
	await _do("contain", [], func(): return sa.log.size() > 0 and str(sa.log[-1][1]) == "contain_start")
	if sa.log.is_empty() or str(sa.log[-1][3]) == "" or str(sa.contain["state"]) != "NONE" or sa.checkpoint()["c"] != cp0["c"]:
		fail("containment asked from the intercom away from the store was not refused cleanly: %s" % str(sa.log.slice(-1)))
	notes["contain_refused_far"] = sa.log[-1][3] if not sa.log.is_empty() else ""
	await _close_page()
	await _wait(func(): return sa.alerted, 120.0, "the alert")
	notes["alert_ship_s"] = sa.t()
	if strategy != "nocontain":
		await _contain()
	# out of sector 1: shut any door of it the steps at the store left open, then to sector 3 by the short way (A1N, AC3, A3P);
	# isolation closes each door behind, the purge leaves the way by sector 2 open, separation leaves the short way open
	var a1 := sa.ring.index("A1")
	for id in ["CIRC.A1P", "CIRC.A1N"]:
		if float(h.circ_doors[id]["target"]) > 0.0 and _node() == a1:
			await _close_door(id, a1)
	var ok := false
	match strategy:
		"purge":
			ok = await _walk_route(["A1", "AC1a", "AC1b", "A2", "AC2a", "AC2b", "A3"], false)
		"separate":
			ok = await _walk_route(["A1", "AC3b", "AC3a", "A3"], false)
		_:
			ok = await _walk_route(["A1", "AC3b", "AC3a", "A3"], true)
	if not ok or not await _to_bay():
		fail("the bay was not reached")
		return
	notes["doors_open_at_bay"] = _open_doors()
	match strategy:
		"isolate":
			await _isolate()
		"purge":
			await _purge()
		"separate":
			await _separate()
		"nocontain":
			await _isolate()
	await _watch()
	await _debrief()
	if strategy == "isolate":
		await _replay()

func _contain() -> void:
	_trace("contain")
	await _walk_to_point("hygiene")
	await _use("Use · inspect store", func(): return sa.page == "hygiene")
	if not sa.flags.get("inspected", false):
		fail("inspecting the store did not count")
	var t_page := sa.t()
	await _ticks(30)
	if sa.t() != t_page:
		fail("the clock ran with the hygiene page open")
	await _ops("Ops · close", func(): return sa.page == "")
	if str(sa.contain["state"]) != "NONE" or str(sa.ring.source["state"]) != "LEAKING":
		fail("opening the hygiene page changed the containment (%s, %s)" % [sa.contain["state"], sa.ring.source["state"]])
	await _ops("Ops · contain spill", func(): return str(sa.contain["state"]) == "WORKING")
	var t_start := sa.t()
	notes["contain_start_s"] = t_start
	# step out of reach halfway: the work pauses and keeps its progress, the store keeps releasing
	await _wait(func(): return float(sa.contain["progress_s"]) >= 300.0, 60.0, "half the containment work")
	await _step_away()
	if sa.eq.in_reach(h.actor.global_position, h.walk_zone, "hygiene"):
		notes["step_away"] = "still in reach"
	else:
		await _wait(func(): return str(sa.contain["state"]) == "PAUSED", 5.0, "containment to pause away from the store")
		var prog := float(sa.contain["progress_s"])
		await _ticks(120)
		if float(sa.contain["progress_s"]) != prog or str(sa.ring.source["state"]) != "LEAKING":
			fail("away from the store the work went on or the source stopped (%s -> %s, %s)" % [prog, sa.contain["progress_s"], sa.ring.source["state"]])
		notes["paused_progress_s"] = prog
		await _walk_to_point("hygiene")
		await _ops("Ops · resume containment", func(): return str(sa.contain["state"]) == "WORKING")
	await _wait(func(): return str(sa.ring.source["state"]) == "ISOLATED", 120.0, "the containment to complete")
	var t_done := -1.0
	for e in sa.log:
		if str(e[1]) == "contained":
			t_done = float(e[0])
	notes["contained_ship_s"] = t_done
	var work := float(sa.sc["containment"]["work_s"])
	if t_done - t_start < work - 1e-6:
		fail("containment took %s ship s, the work is %s" % [t_done - t_start, work])
	var S0 := float(sa.sc["source"]["inventory_kg"])
	var want := S0 * (1.0 - exp(-t_done / float(sa.sc["source"]["tau_s"])))
	if absf(sa.ring.released - want) > 1e-12:
		fail("released %s kg at containment, first order gives %s" % [sa.ring.released, want])

## Out of the store's reach along the deck, away from it.
func _step_away() -> void:
	for k in 3:
		if not sa.eq.in_reach(h.actor.global_position, h.walk_zone, "hygiene"):
			break
		var d: Vector3 = h.actor.global_position - sa.eq.centre("hygiene")
		d -= h.actor.up_now * d.dot(h.actor.up_now)
		await pl.ex._walk_to(h.actor.global_position + d.normalized() * 2.0, 0.4, 20.0, 0)
		pl.ex.fails = []
		h.walk_override = Vector3.ZERO
		await _ticks(20)

func _bay_op(kind: String, args: Array, done: Callable) -> void:
	await _page("bay")
	await _do(kind, args, done)

func _intercom(kind: String, args: Array, done: Callable) -> void:
	await _page("intercom")
	await _do(kind, args, done)

func _isolate() -> void:
	_trace("isolate")
	# the partner over to sector 3 (a door route), then sector 1's dampers shut: with its doors shut, sector 1 is sealed
	await _intercom("order", ["A", "A3"], func(): return not (sa.people[1]["route"] as Array).is_empty())
	await _close_page()
	await _wait(func(): return (sa.people[1]["route"] as Array).is_empty(), 30.0, "the partner to arrive")
	notes["partner_route"] = sa.people[1]["places"].map(func(pp): return sa.ids[int(pp[1])])
	await _bay_op("damper", ["A1P"], func(): return not bool(sa.ring.open["IMV.A1P"]))
	await _bay_op("damper", ["A1N"], func(): return not bool(sa.ring.open["IMV.A1N"]))
	await _close_page()
	notes["sealed"] = {"A1P": sa.sealed("CIRC.A1P"), "A1N": sa.sealed("CIRC.A1N"), "dampers_shut": sa.config()["dampers_closed"], "doors_open": _open_doors()}
	# an order across the seal is refused and changes nothing
	var cp := sa.checkpoint()
	await _intercom("order", ["A", "A1"], func(): return str(sa.log[-1][1]) == "order")
	if str(sa.log[-1][3]) == "" or sa.checkpoint()["nodes"] != cp["nodes"] or not (sa.people[1]["route"] as Array).is_empty():
		fail("an order across sector 1's seal was not refused: %s" % str(sa.log[-1]))
	notes["sealed_order_refusal"] = sa.log[-1][3]
	await _close_page()

## A close refused while an ordered pair stands in an open door's doorway (headless: the scene's own door handler at that moment).
func _doorway_refusal(who: int) -> void:
	if pl.await_player:
		return
	var hit := ""
	var n := 0
	while hit == "" and n < 60 * 20 and not (sa.people[who]["route"] as Array).is_empty():
		for id in _open_doors():
			if not sa.in_doorway(id).is_empty():
				hit = id
		if hit == "":
			await _ticks(1)
			n += 1
	if hit == "":
		notes["doorway_refusal"] = "no pair crossed an open door"
		fail("no doorway refusal was exercised")
		return
	var hist := sa.ring.history.size()
	var r := h._toggle_door(hit)
	notes["doorway_refusal"] = {"door": hit, "result": r, "said": h.refusal}
	if r != "" or float(h.circ_doors[hit]["target"]) != 1.0 or sa.ring.history.size() != hist:
		fail("a close of %s with a pair in its doorway was not refused cleanly (%s)" % [hit, r])

func _purge() -> void:
	_trace("purge")
	await _intercom("order", ["A", "A3"], func(): return not (sa.people[1]["route"] as Array).is_empty())
	await _do("order", ["B", "A3"], func(): return not (sa.people[2]["route"] as Array).is_empty())
	await _close_page()
	await _doorway_refusal(2)
	await _wait(func(): return sa.people.all(func(q): return (q["route"] as Array).is_empty()), 30.0, "the pairs to arrive")

func _separate() -> void:
	_trace("separate")
	# the partner and pair C into sector 2 (by A1P and A3N, both shut), then those two bulkheads' dampers shut: sector 2 is sealed with
	# four people and no CO2 unit; the short way A1-A3 stays open to the TCC; the restore plan declared
	await _intercom("order", ["A", "A2"], func(): return not (sa.people[1]["route"] as Array).is_empty())
	await _do("order", ["C", "A2"], func(): return not (sa.people[4]["route"] as Array).is_empty())
	await _do("plan", [], func(): return sa.plan == "RESTORE")
	await _close_page()
	await _wait(func(): return sa.people.all(func(q): return (q["route"] as Array).is_empty()), 30.0, "the pairs to arrive")
	await _bay_op("damper", ["A1P"], func(): return not bool(sa.ring.open["IMV.A1P"]))
	await _bay_op("damper", ["A3N"], func(): return not bool(sa.ring.open["IMV.A3N"]))
	await _close_page()
	notes["sealed"] = {"A1P": sa.sealed("CIRC.A1P"), "A3N": sa.sealed("CIRC.A3N"), "doors_open": _open_doors()}

func _watch() -> void:
	_trace("watch")
	var cfg := sa.config()
	notes["family_declared"] = sa.family()
	await _intercom("watch", [], func(): return sa.phase == "WATCH")
	if sa.phase != "WATCH":
		fail("the watch did not start")
		return
	if sa.watch["config"] != cfg:
		fail("starting the watch changed the configuration")
	# a door is refused during the watch
	if not pl.await_player:
		var d := "CIRC.A3P"
		var tgt := float(h.circ_doors[d]["target"])
		h._toggle_door(d)
		if float(h.circ_doors[d]["target"]) != tgt:
			fail("a door moved during the watch")
		notes["watch_door_refusal"] = h.refusal
	var t_real := Time.get_ticks_msec()
	await _wait(func(): return sa.phase == "PROJECTION" or sa.phase == "DONE", 240.0, "the watch to end")
	notes["watch_real_s"] = snappedf((Time.get_ticks_msec() - t_real) / 1000.0, 0.1)
	notes["watch_end_h"] = float(sa.watch["end_s"]) / 3600.0
	var t2 := Time.get_ticks_msec()
	await _wait(func(): return sa.phase == "DONE" and sa.page == "debrief", 120.0, "the projection and the debrief")
	notes["projection_real_s"] = snappedf((Time.get_ticks_msec() - t2) / 1000.0, 0.1)
	var post := sa.log.filter(func(e): return float(e[0]) > float(sa.watch["t0"]) + 1e-6)
	var kinds := {}
	for e in post:
		kinds[str(e[1])] = true
	notes["after_watch"] = kinds.keys()
	if sa.plan == "NONE" and not kinds.is_empty():
		fail("with no plan the watch changed the run: %s" % str(post.slice(0, 3)))
	if sa.plan == "RESTORE" and not kinds.has("restore"):
		fail("the declared restore plan did not run")

func _debrief() -> void:
	_trace("debrief")
	var d := sa.debrief_cache
	if d.is_empty():
		fail("no debrief")
		return
	notes["verdict"] = d["watch"]["verdict"]["result"]
	notes["family"] = d["watch"]["family"]
	var want_family: String = {"isolate": "ISOLATE", "purge": "ROUTE", "separate": "SEPARATE", "nocontain": "UNCONTAINED"}[strategy]
	if str(d["watch"]["family"]) != want_family:
		fail("strategy %s gave family %s" % [strategy, d["watch"]["family"]])
	var L: Dictionary = d["ledgers"]
	var scale := 1e-15 + 1e-10 * sa.ring.S0
	if absf(float(L["nh3_kg"])) > scale or absf(float(L["release_kg"])) > scale or absf(float(L["co2_kg"])) > 1e-9:
		fail("a ledger is open: %s" % str(L))
	if not _near(float(d["released_g"]) + float(d["retained_g"]), float(d["inventory_g"])) or \
			absf(float(d["airborne_g"]) + float(d["removed_g"]) - float(d["released_g"])) > 1e-9:
		fail("the debrief's NH3 does not add up: %s" % str([d["inventory_g"], d["released_g"], d["retained_g"], d["removed_g"], d["airborne_g"]]))
	for q in d["people"]:
		if q["max_24h_ppm"] == null or q["mean_7d_ppm"] == null:
			fail("%s: a completed window shown as missing" % q["id"])
	notes["debrief"] = {"released_g": d["released_g"], "removed_g": d["removed_g"], "airborne_g": d["airborne_g"], "clear_h": d["clear_h"],
		"worst_1h": d["people"].map(func(q): return snappedf(float(q["max_1h_ppm"]), 0.01)), "co2_h": d["people"].map(func(q): return snappedf(float(q["co2_above_target_h"]), 0.01))}
	notes["frame_cost_us"] = sa.frame_cost
	for k in 3:
		var pg := sa.deb_page
		await _use("Use · next page" if pg < 2 else "Use · close", func(): return sa.deb_page != pg)
	if sa.page != "":
		fail("the debrief did not close after its third page")

func _replay() -> void:
	_trace("replay")
	var runs := sa.runs
	await _ops("Ops · replay", func(): return sa.runs > runs)
	await _ticks(5)
	if sa.phase != "LIVE" or sa.t() > 60.0 or str(sa.ring.source["state"]) != "LEAKING" or sa.ring.S0 != float(sa.sc["source"]["inventory_kg"]):
		fail("replay did not restart from the start: %s t %s %s" % [sa.phase, sa.t(), sa.ring.source["state"]])
	var air := 0.0
	for v in sa.ring.c:
		air += float(v)
	if sa.t() == 0.0 and air != 0.0:
		fail("replay kept NH3 in the air")
	notes["replay"] = {"runs": sa.runs, "t_s": sa.t(), "node": sa.ids[int(sa.people[0]["node"])]}

func _finish() -> void:
	if sa != null and sa.verified:
		notes["record"] = sa.record()
	var out := {"result": "PASS" if fails.is_empty() else "FAIL", "fails": fails, "notes": notes,
		"wall_s": snappedf((Time.get_ticks_msec() - t0) / 1000.0, 0.1), "physics_frames": Engine.get_physics_frames()}
	print("WF_GODOT_SHARED_AIR " + JSON.stringify(out))
	h.get_tree().quit(0 if fails.is_empty() else 1)
