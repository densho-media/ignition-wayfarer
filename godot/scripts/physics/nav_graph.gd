class_name WfNavGraph
extends RefCounted
## PHYS-001 phase 6: the crew navigation graph from the rig's `dynamics.nav` (S&E 46 DYN-018; PROTOTYPE route logic, not qualification).
## Mirror of crew_dynamics.route(): fewest edges, breadth first, neighbours in edge order, so ties break the same way. An edge is removed by
## a closed pressure boundary ("from-to" in `closed`, only where the edge has a boundary), a mode or actor it does not allow, and (Godot
## side, DYN-009) a PORT_GATE while the drum is not synchronized with its ring (`synced` false). Docks exist only in DOCKED and the
## exterior only for the suited actor in EVA, because the edges say so. The casualty query is always HOLD (DYN-020): never a route.

var nav: Dictionary
var edges: Array = []

func _init(dyn: Dictionary) -> void:
	nav = dyn["nav"]
	edges = nav["edges"]

## {status "ROUTE"/"NO_ROUTE", path [nodes], edges [edge indices], techniques [technique per edge in `mode`]}
func route(start: String, goal: String, mode: String, actor: String, closed: Array = [], synced := true) -> Dictionary:
	var adj := {}
	for i in edges.size():
		var e: Dictionary = edges[i]
		if not (mode in e["modes"] and actor in e["actors"]):
			continue
		if e["pressure_boundary"] != null and ("%s-%s" % [e["from"], e["to"]]) in closed:
			continue
		if e["pressure_boundary"] == "PORT_GATE" and not synced:
			continue
		if not adj.has(e["from"]):
			adj[e["from"]] = []
		if not adj.has(e["to"]):
			adj[e["to"]] = []
		adj[e["from"]].append([e["to"], i])
		adj[e["to"]].append([e["from"], i])
	var prev := {start: null}
	var todo := [start]
	while not todo.is_empty():
		var n: String = todo.pop_front()
		if n == goal:
			var path := [n]
			var used := []
			while prev[path[-1]] != null:
				var p: Array = prev[path[-1]]
				path.append(p[0])
				used.append(p[1])
			path.reverse()
			used.reverse()
			var tech := []
			for i in used:
				tech.append(nav["technique_by_mode"][mode][i])
			return {"status": "ROUTE", "path": path, "edges": used, "techniques": tech}
		for m in adj.get(n, []):
			if not prev.has(m[0]):
				prev[m[0]] = [n, m[1]]
				todo.append(m[0])
	return {"status": "NO_ROUTE", "path": [], "edges": [], "techniques": []}

## DYN-020: no qualified casualty clearance; a route the walking mannequin passes is not a rescue route.
func casualty(_start := "", _goal := "", _mode := "", _actor := "") -> Dictionary:
	var c: Dictionary = nav["casualty"]
	return {"status": c["result"], "source": "DYN-020", "reason": c["reason"]}
