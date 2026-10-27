class_name WfLine
extends RefCounted
## One body line of the excursion (EXC-001): the poses a body takes hand over hand (the M2 line technique of body_tour), from the rig: centre
## p, head direction up, the line parameter s (the larger of the centre travel and the ends' travel) and the phase; the stretches with no grip
## in reach (coasts: the hands neither push nor brake), the spans a closure blocks while shut, and the frame the line lives in.
## Godot axes, index-pose coordinates (the frame the stage's colliders are built in). Computes no geometry of its own.

var id := ""
var zone := "SHIP"              # SHIP, or RING_A / RING_B for a ring's access line (the drum frame, then the ring's)
var p: Array = []
var up: Array = []
var s: Array = []
var phase: Array = []
var vmax: Array = []            # per pose: the largest speed at which the turn there changes the velocity by at most `accel` in one step
var coasts: Array = []          # [s0, s1]
var gates: Array = []           # {id, s: [s0, s1]}: the body may not be inside while the closure is not fully open
var marks := {}                 # name -> s (junctions, the restraint pose, the port, the run top)
var accel := 0.5

static func g(v: Array) -> Vector3:
	return Vector3(v[0], v[2], -v[1])

func add(pt: Vector3, head: Vector3, ph: String, sv := -1.0) -> void:
	if sv < 0.0:
		sv = 0.0 if s.is_empty() else float(s[-1]) + maxf((pt - (p[-1] as Vector3)).length(), 0.0)
	p.append(pt)
	up.append(head.normalized())
	s.append(sv)
	phase.append(ph)

func length() -> float:
	return float(s[-1])

## Poses' turn limits, once the poses are in (dt: the physics step).
func finish(dt: float) -> void:
	vmax = [0.0]
	for k in range(1, p.size() - 1):
		var d1: Vector3 = ((p[k] as Vector3) - (p[k - 1] as Vector3)) / maxf(float(s[k]) - float(s[k - 1]), 1e-9)
		var d2: Vector3 = ((p[k + 1] as Vector3) - (p[k] as Vector3)) / maxf(float(s[k + 1]) - float(s[k]), 1e-9)
		var dv := (d2 - d1).length()
		vmax.append(accel * dt / dv if dv > 1e-9 else INF)
	vmax.append(0.0)

## Centre, head direction and phase at s (centre lerp, axis nlerp between the poses).
func at(sv: float) -> Array:
	var i := 0
	while i < s.size() - 2 and sv > float(s[i + 1]):
		i += 1
	var span: float = float(s[i + 1]) - float(s[i])
	var f := clampf((sv - float(s[i])) / span, 0.0, 1.0) if span > 1e-9 else 1.0
	return [(p[i] as Vector3).lerp(p[i + 1], f), (up[i] as Vector3).lerp(up[i + 1], f).normalized(), phase[i + 1]]

## Unit tangent of the centre's motion at s (toward increasing s); the head direction where the centre does not move (a pivot in place).
func tangent(sv: float) -> Vector3:
	var a: Vector3 = at(maxf(sv - 0.05, 0.0))[0]
	var b: Vector3 = at(minf(sv + 0.05, length()))[0]
	var d := b - a
	return d.normalized() if d.length() > 1e-4 else (at(sv)[1] as Vector3)

func coast_at(sv: float, dir: float) -> Array:
	for c in coasts:
		if (dir > 0.0 and sv >= float(c[0]) - 1e-9 and sv < float(c[1])) or (dir < 0.0 and sv > float(c[0]) and sv <= float(c[1]) + 1e-9):
			return c
	return []

## Line length between s0 and s1 on which the hands can act (outside the coasts).
func held_length(s0: float, s1: float) -> float:
	var d := absf(s1 - s0)
	for c in coasts:
		d -= maxf(0.0, minf(maxf(s0, s1), float(c[1])) - maxf(minf(s0, s1), float(c[0])))
	return maxf(d, 0.0)

func nearest_s(pt: Vector3) -> float:
	var best := 0.0
	var d := INF
	for k in range(p.size() - 1):
		var a: Vector3 = p[k]
		var b: Vector3 = p[k + 1]
		var ab := b - a
		var f := clampf((pt - a).dot(ab) / maxf(ab.length_squared(), 1e-12), 0.0, 1.0)
		var dd := (a + ab * f).distance_to(pt)
		if dd < d:
			d = dd
			best = float(s[k]) + (float(s[k + 1]) - float(s[k])) * f
	return best
