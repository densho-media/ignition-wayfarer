class_name WfVestibule
extends RefCounted
## Rotary vestibule handoff (46 DYN-027, 15 CREW-MODE-004; mirror of crew_dynamics.vestibule_gate / vestibule_ramp_allowed), SIMULATION_ONLY.
## Two independent closures, STATIONARY (trunk side) and RING (tube side), around a drum that synchronizes between the stationary spine
## (omega 0) and its ring (signed omega about +X). The drum changes speed only with the occupant restrained and both closures shut; a
## closure opens only when the drum matches that side's speed within the rig tolerance, the other closure is shut and the pressure is
## shown equalized (the threshold is OPEN, so `dp_equalized` is an input, unknown = null = refused). The occupant's state crosses frames
## through WfFrames.to_ring / to_ship (position and velocity, including w x r): never a bare reparent.
## The drum cycle time is OPEN (MEC-019): `start_sync(side, seconds)` takes it as a labelled presentation input at constant alpha.

var dyn: Dictionary
var ring := 0
var drum_w := 0.0                    # signed rad/s about +X
var closures := {"STATIONARY": true, "RING": true}     # true = closed
var restrained := false
var dp_equalized = null              # true / false / null (unknown)
var ramp_from := 0.0
var ramp_to := 0.0
var ramp_s := 0.0
var ramp_t := 0.0
var ramping := false
var log: Array = []
var reason := ""

func _init(d: Dictionary, ring_index := 0) -> void:
	dyn = d
	ring = ring_index

func tol() -> float:
	return float(dyn["vestibule"]["match_tol_rad_s"])

## Angular speed of a side: the spine is stationary (ship frame, attitude rate taken as 0); the ring side turns at `ring_w` (the mode
## controller's current omega of this ring, signed).
func side_w(side: String, ring_w: float) -> float:
	return 0.0 if side == "STATIONARY" else ring_w

func _entry(what: String, ok: bool, why: String) -> Dictionary:
	reason = why
	var e := {"status": "SIMULATION_ONLY", "action": what, "ok": ok, "reason": why, "drum_w": drum_w, "closures": closures.duplicate(), "restrained": restrained}
	log.append(e)
	return e

func ramp_allowed() -> Dictionary:
	if not restrained:
		return {"allowed": false, "reason": "occupant not restrained"}
	if not (closures["STATIONARY"] and closures["RING"]):
		return {"allowed": false, "reason": "a boundary is open"}
	return {"allowed": true, "reason": "restrained, both boundaries closed"}

## Begin synchronizing the drum to `side` (STATIONARY or RING at ring_w) over `seconds` (PROTOTYPE presentation; cycle time OPEN).
func start_sync(side: String, ring_w: float, seconds: float) -> Dictionary:
	var g := ramp_allowed()
	if not g["allowed"]:
		return _entry("sync to " + side, false, g["reason"])
	ramp_from = drum_w
	ramp_to = side_w(side, ring_w)
	ramp_s = maxf(seconds, 1e-6)
	ramp_t = 0.0
	ramping = true
	return _entry("sync to " + side, true, "drum ramp %.4f -> %.4f rad/s over %.1f s (PROTOTYPE presentation; cycle time OPEN)" % [ramp_from, ramp_to, ramp_s])

func alpha() -> float:
	return (ramp_to - ramp_from) / ramp_s if ramping else 0.0

func step(dt: float) -> void:
	if not ramping:
		return
	if not (restrained and closures["STATIONARY"] and closures["RING"]):
		ramping = false                                  # fail closed: a ramp stops if a precondition is lost
		_entry("ramp", false, "precondition lost during the ramp: drum held at %.4f rad/s" % drum_w)
		return
	ramp_t = minf(ramp_t + dt, ramp_s)
	drum_w = ramp_from + (ramp_to - ramp_from) * ramp_t / ramp_s
	if ramp_t >= ramp_s:
		drum_w = ramp_to
		ramping = false
		_entry("ramp", true, "drum at %.4f rad/s" % drum_w)

func gate(side: String, ring_w: float) -> Dictionary:
	var other := "RING" if side == "STATIONARY" else "STATIONARY"
	if ramping:
		return {"open": false, "reason": "drum changing speed: both boundaries stay closed" + ("" if restrained else "; occupant NOT restrained")}
	if not closures[other]:
		return {"open": false, "reason": "%s closure is open: never both open" % other.to_lower()}
	var sw := side_w(side, ring_w)
	if absf(drum_w - sw) > tol():
		return {"open": false, "reason": "drum %+.5f rad/s does not match the %s side %+.5f rad/s" % [drum_w, side.to_lower(), sw]}
	if dp_equalized != true:
		return {"open": false, "reason": "pressure not shown equalized (threshold OPEN, PRESS-004)"}
	return {"open": true, "reason": "matched to the %s side, pressure equalized, other boundary closed" % side.to_lower()}

func open(side: String, ring_w: float) -> Dictionary:
	var g := gate(side, ring_w)
	if g["open"]:
		closures[side] = false
	return _entry("open " + side, g["open"], g["reason"])

func close(side: String) -> Dictionary:
	closures[side] = true
	return _entry("close " + side, true, "closed")

## Occupant state across the open interface (ship metres, Godot axes, PackedFloat64Array). Ship -> ring frame when entering the ring side,
## ring -> ship when leaving; centre_x and angle are the ring's, w its signed spin vector.
static func handoff_to_ring(r, v, centre_x: float, angle: float, w) -> Array:
	return WfFrames.to_ring(r, v, centre_x, angle, w)

static func handoff_to_ship(r, v, centre_x: float, angle: float, w) -> Array:
	return WfFrames.to_ship(r, v, centre_x, angle, w)

func hud_text(ring_w: float) -> String:
	return "vestibule %s  drum %+.4f rad/s%s  stationary %s  ring %s  restrained %s  dp %s\n  %s\n" % [dyn["rings"][ring]["name"], drum_w,
		" (ramping)" if ramping else "", "closed" if closures["STATIONARY"] else "OPEN", "closed" if closures["RING"] else "OPEN",
		"yes" if restrained else "NO", "equalized" if dp_equalized == true else ("unknown" if dp_equalized == null else "NOT equalized"), reason]
