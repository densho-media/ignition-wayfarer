class_name WfFrames
## Frame helpers for the local crew physics (PHYS-001; mirror of crew_dynamics.to_ring / to_ship). Vectors are PackedFloat64Array(3)
## in double precision, because Vector3 is float32 and the fixtures are compared to 1e-9. The rig is Blender (+X bow, +Z dorsal, +Y left);
## Godot (x, y, z) = (x, z, -y). The spin axis +X is the same in both.

static func v3(x: float, y: float, z: float) -> PackedFloat64Array:
	return PackedFloat64Array([x, y, z])

static func b2g(b) -> PackedFloat64Array:
	return v3(b[0], b[2], -b[1])

static func g2b(g) -> PackedFloat64Array:
	return v3(g[0], -g[2], g[1])

static func from_vec(v: Vector3) -> PackedFloat64Array:
	return v3(v.x, v.y, v.z)

static func to_vec(a) -> Vector3:
	return Vector3(a[0], a[1], a[2])

static func add(a, b) -> PackedFloat64Array: return v3(a[0] + b[0], a[1] + b[1], a[2] + b[2])
static func sub(a, b) -> PackedFloat64Array: return v3(a[0] - b[0], a[1] - b[1], a[2] - b[2])
static func mul(a, k: float) -> PackedFloat64Array: return v3(a[0] * k, a[1] * k, a[2] * k)
static func cross(a, b) -> PackedFloat64Array:
	return v3(a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])

static func rot_x(a, angle: float) -> PackedFloat64Array:
	var c := cos(angle)
	var s := sin(angle)
	return v3(a[0], c * a[1] - s * a[2], s * a[1] + c * a[2])

static func ring_index(zone: String) -> int:
	return 0 if zone == "RING_A" else (1 if zone == "RING_B" else -1)

static func ring(dyn: Dictionary, k: int) -> Dictionary:
	return dyn["rings"][k]

## Signed spin vector (Godot axes) of ring k in a mode; zero when the mode stops and locks the rings (rig modes[m].omega_rad_s).
static func ring_omega(dyn: Dictionary, k: int, mode: String) -> PackedFloat64Array:
	return b2g(dyn["modes"][mode]["omega_rad_s"][k])

## Ship frame -> ring frame of a ring at `angle` turning at w: position from the ring centre, and velocity with the rotation removed.
static func to_ring(r, v, centre_x: float, angle: float, w) -> Array:
	var rel := sub(r, v3(centre_x, 0.0, 0.0))
	return [rot_x(rel, -angle), rot_x(sub(v, cross(w, rel)), -angle)]

static func to_ship(r, v, centre_x: float, angle: float, w) -> Array:
	var rel := rot_x(r, angle)
	return [add(rel, v3(centre_x, 0.0, 0.0)), add(rot_x(v, angle), cross(w, rel))]

## Angular velocity of a free body seen from the ring frame: the inertial one minus the frame's spin (angular momentum is conserved).
static func angvel_to_ring(wb, angle: float, w) -> PackedFloat64Array:
	return rot_x(sub(wb, w), -angle)

static func angvel_to_ship(wb, angle: float, w) -> PackedFloat64Array:
	return add(rot_x(wb, angle), w)
