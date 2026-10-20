class_name WfNavPolicy
extends RefCounted
## Ship Navigator guidance modes (S&E 49 NAV-003, NAV-020; Tale 26 NAV-TOUR-02/07): GUIDED follows the existing induction stop order,
## ASSISTED (default) shows the route to a stop the visitor picks and suggests nearby systems, FREE keeps only a chosen stop's marker.
## A policy returns guidance only. It never sees the route planner's state and has no way to open a closure or allow an edge.

## The next stop of the existing tour per demonstrator chapter (TOUR-01..04 order; display, not a procedure).
const TOUR_TARGET := {"EXTERIOR": "arrival", "ENTRY": "spine", "MICROGRAVITY": "spine", "MODE": "transfer", "TRANSFER": "transfer",
	"DESCENT": "habitat", "GRAVITY": "habitat", "ARRIVAL": "habitat", "INSPECT": "habitat"}

var modes: Array = []

func _init(nav: Dictionary) -> void:
	modes = nav["modes"]

func ids() -> Array:
	return modes.map(func(m): return m["id"])

func default_id() -> String:
	for m in modes:
		if m.get("default", false):
			return m["id"]
	return modes[0]["id"]

func get_mode(id: String) -> Dictionary:
	for m in modes:
		if m["id"] == id:
			return m
	return {}

## {mode, title, target (stop key or ""), show_route, hints, narration}
func guidance(id: String, chapter: String, chosen: String) -> Dictionary:
	var m := get_mode(id)
	var target := str(TOUR_TARGET.get(chapter, "")) if m["target"] == "TOUR" else chosen
	return {"mode": id, "title": m["title"], "target": target, "show_route": bool(m["route"]) and target != "", "hints": bool(m["hints"]),
		"narration": bool(m["narration"])}
