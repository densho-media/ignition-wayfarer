class_name WfNavRoute
extends RefCounted
## Ship Navigator route planner (SNAV-001; S&E 49 NAV-010..013, PROTOTYPE route logic, not qualification). Two stages over the rig's own data:
##  1. topology: WfNavGraph over dynamics.nav with the operating mode, the actor and the vestibule rule (an edge through the spine port only
##     while the drum can match: ring A stopped at its index or running steady; never while the ring changes speed, DYN-027);
##  2. geometry: the induction rail between the current place and the target stop, the line the body and the review camera actually use,
##     split at every opening it crosses. Up to the first closure that is not open now the route is GO; past it nothing is GO: HOLD with the
##     opening's reason (it cycles only in its sequence). A mode or actor the edges do not allow is RESTRICTED. The guidance mode is not an
##     input: modes change hints, never this result (NAV-003).

var rig: Dictionary
var nav: Dictionary          # rig.navigator
var graph: WfNavGraph
var rail_m: Array[float] = []
var rail_nodes: Array = []
var stops := {}              # key -> stop
var openings: Array = []     # navigator.openings, rail order

const REASONS := {
	"AIRLOCK_OUTER": "airlock outer hatch closed; the two airlock hatches are never open together and cycle in sequence",
	"AIRLOCK_INNER": "airlock inner hatch closed; the two airlock hatches are never open together and cycle in sequence",
	"PORT_GATE": "spine port gate closed; it opens only with the drum matched to the spine and the far boundary shut (DYN-027)",
	"DRUM_DOOR_TUBE_HATCH": "drum door closed; it opens only with the drum synchronized with ring A and the port gate shut (DYN-027)",
	"SECTOR_LEAF": "sector hatch closed",
}

const SHORT := {
	"AIRLOCK_OUTER": "airlock hatch cycles in sequence",
	"AIRLOCK_INNER": "airlock hatch cycles in sequence",
	"PORT_GATE": "port gate shut until the drum matches",
	"DRUM_DOOR_TUBE_HATCH": "drum door shut until the drum syncs",
	"SECTOR_LEAF": "sector hatch shut",
}
const ARRIVED_M := 1.5        # PROTOTYPE display: within this of a stop along the rail the visitor is "at" it

func _init(r: Dictionary) -> void:
	rig = r
	nav = r["navigator"]
	graph = WfNavGraph.new(r["dynamics"])
	for p in r["induction_route"]["rail"]:
		rail_m.append(float(p["rail_m"]))
	rail_nodes = nav["rail_nodes"]
	for s in r["induction_route"]["stops"]:
		stops[s["key"]] = s
	openings = nav["openings"].duplicate()
	openings.sort_custom(func(a, b): return float(a["rail_m"]) < float(b["rail_m"]))

## The nav node of a place on the rail (the waypoint at or before it).
func node_at(at: float) -> String:
	var i := 0
	while i < rail_m.size() - 1 and rail_m[i + 1] <= at + 1e-6:
		i += 1
	return str(rail_nodes[i])

## Whether the drum can match for a crossing in this ring state: stopped at the index, or turning steadily at full speed.
static func drum_can_match(ring_mode: String) -> bool:
	return ring_mode in ["STOPPED", "RUNNING"]

## state: {mode: DOCKED/COAST/..., actor, ring_mode: STOPPED/SPIN_UP/RUNNING/..., open: {opening id: 0..1}} (an id missing = no closure).
func plan(at: float, target: String, state: Dictionary) -> Dictionary:
	var out := {"target": target, "from_m": at, "status": "NONE", "path": [], "techniques": [], "go_m": [at, at], "hold_m": [], "block": {},
		"reason": "", "tags": ["PROTOTYPE route", "SIMULATION_ONLY"]}
	if not stops.has(target):
		out["reason"] = "no such stop"
		return out
	var to := float(stops[target]["rail_m"])
	out["to_m"] = to
	var start := node_at(at)
	var goal := str(nav["stop_nodes"][target])
	var mode := str(state.get("mode", "DOCKED"))
	var actor := str(state.get("actor", "human_iva"))
	var can_match := drum_can_match(str(state.get("ring_mode", "STOPPED")))
	var r := graph.route(start, goal, mode, actor, [], can_match)
	if r["status"] != "ROUTE":
		var any := graph.route(start, goal, mode, actor, [], true)
		if any["status"] == "ROUTE":
			out["status"] = "HOLD"
			out["reason"] = "ring A changing speed: the drum cannot match, the spine port stays shut (DYN-027)"
			out["short"] = "ring A changing speed"
		else:
			out["status"] = "RESTRICTED"
			out["reason"] = "no edge from %s to %s for %s in %s (dynamics.nav modes/actors)" % [start, goal, actor, mode]
			out["short"] = "not connected in " + mode
		out["hold_m"] = [at, to]
		return out
	out["path"] = r["path"]
	out["techniques"] = r["techniques"]
	if absf(to - at) < ARRIVED_M:
		out["status"] = "ARRIVED"
		return out
	var dir := 1.0 if to > at else -1.0
	var crossed := openings.filter(func(o): return (float(o["rail_m"]) - at) * dir > 1e-6 and (to - float(o["rail_m"])) * dir >= -1e-6)
	if dir < 0.0:
		crossed.reverse()
	var open: Dictionary = state.get("open", {})
	for o in crossed:
		var v := float(open.get(o["id"], 1.0))
		if v < 0.999:
			out["status"] = "HOLD"
			out["block"] = {"id": o["id"], "kind": o["kind"], "rail_m": o["rail_m"], "open": v}
			out["reason"] = REASONS.get(o["kind"], "closure not open")
			out["short"] = SHORT.get(o["kind"], "closure not open")
			out["go_m"] = [at, float(o["rail_m"])]
			out["hold_m"] = [float(o["rail_m"]), to]
			return out
	out["status"] = "GO"
	out["go_m"] = [at, to]
	return out

## The direct nav query for nodes off the induction rail (EVA, ring B): never GO for the exterior (FLIGHT_EVA HOLD, NAV-014).
func plan_node(start: String, goal: String, state: Dictionary) -> Dictionary:
	var r := graph.route(start, goal, str(state.get("mode", "DOCKED")), str(state.get("actor", "human_iva")), [], drum_can_match(str(state.get("ring_mode", "STOPPED"))))
	var status := "RESTRICTED" if r["status"] != "ROUTE" else "TOPOLOGY_ONLY"
	for i in r["edges"]:
		var e: Dictionary = graph.edges[i]
		if str(e.get("status", "")).contains("HOLD"):
			status = "HOLD"
	return {"status": status, "path": r["path"], "reason": "" if status != "HOLD" else "FLIGHT_EVA HOLD (DYN-013): simulation only, never a navigable area"}
