class_name WfHandhold
extends StaticBody3D
## A marked handhold (DYN-011): the only place a hand can close. `anchor_id` names it; the anchor point is where the grip is measured.
## A rail has a segment (local `seg_a`..`seg_b`): the hand closes on the point of the segment nearest to the body.

var anchor_id := ""
var anchor_local := Vector3.ZERO
var seg_a := Vector3.ZERO
var seg_b := Vector3.ZERO

func anchor_point() -> Vector3:
	return global_transform * anchor_local

## Where a hand at p would close: the anchor point, or the nearest point of the rail segment.
func anchor_near(p: Vector3) -> Vector3:
	if seg_a == seg_b:
		return anchor_point()
	var a := global_transform * seg_a
	var ab := global_transform * seg_b - a
	return a + ab * clampf((p - a).dot(ab) / ab.length_squared(), 0.0, 1.0)
