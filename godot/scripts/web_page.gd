class_name WfWebPage
extends RefCounted
## WEB-002: the few words the Godot scenes exchange with the browser page (web/play/shell.html). Native builds get the defaults.
## The page says which experience was chosen (its #hash: "interior" the walk, "exterior" or "eva" EVA Operations); the scenes tell the
## page when they change scene (so its title, Exit link and address follow) and publish a small state record once a second for the
## browser check (window.wayfarerWalk, window.wayfarerEva). Display plumbing only: no spacecraft fact lives here.

static func _web() -> bool:
	return OS.has_feature("web") and Engine.has_singleton("JavaScriptBridge")

## The experience the page asked for, from its hash: "exterior", "interior" or "" (no page, or no hash).
static func requested() -> String:
	if not _web():
		return ""
	var h = JavaScriptBridge.eval("location.hash", true)
	var s := String(h).to_lower() if h != null else ""
	if s.contains("eva") or s.contains("exterior"):
		return "exterior"
	if s.contains("interior"):
		return "interior"
	return ""

## LOCO-001: the start the page asked for within its experience: "systems" (#interior-systems: the ring start with the SYS-001 proof),
## "excursion" (#interior-excursion: the full walk from the station),
## "hatch" (#exterior-hatch or the older #eva: EVA Operations at the EVA hatch), or "" (the default locomotion starts).
static func start_variant() -> String:
	if not _web():
		return ""
	var h = JavaScriptBridge.eval("location.hash", true)
	var s := String(h).to_lower() if h != null else ""
	if s.contains("systems"):
		return "systems"
	if s.contains("excursion") or s.contains("station"):
		return "excursion"
	if s.contains("first"):
		return "first_flight"
	if s.contains("hatch") or s == "#eva":
		return "hatch"
	return ""

## Tell the page which experience is now running (it updates its title, Exit link and the address hash).
static func scene(experience: String) -> void:
	if _web():
		JavaScriptBridge.eval("window.wayfarerScene && window.wayfarerScene(%s);" % JSON.stringify(experience), true)

## Publish a small state record to the page (the browser check reads it; nothing in the page acts on it).
static func publish(name: String, state: Dictionary) -> void:
	if _web():
		JavaScriptBridge.eval("window.%s = %s;" % [name, JSON.stringify(state)], true)
