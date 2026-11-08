class_name WfCharacterRig
extends Node3D
## LOCO-001/002 (docs/LOCOMOTION.md): the visible character of a physics body. It shows the exported MPFB game_engine character (the
## newcomer, or a Y155 suit) and plays its clips; it never moves the body. Physics owns position, velocity and contact; this follows.
##
## Root motion: the walk, run and magnetic-walk clips were authored with the Root bone carrying the ground travel. At load the Root's
## translation track is removed from every clip (in place), and the travel it carried becomes the clip's speed (m/s): play() runs a clip at
## physics speed / clip speed, so a planted foot keeps its place on the floor instead of sliding. The movement is applied once, by the
## physics body, never twice.
##
## A missing GLB is a failure the caller sees (ok == false and `missing`), never a silent proxy.

var ok := false
var missing := ""
var model: Node3D = null
var anim: AnimationPlayer = null
var clip_speed := {}              # clip -> authored travel speed (m/s), from the stripped Root track
var current := ""
var reversed := false
var meta := {}                    # characters.json / eva_characters.json record of this character (loop flags, actions)

## path: res:// GLB; record: the character's entry of characters.json (its "actions" give the loop flags).
func setup(path: String, record: Dictionary) -> bool:
	meta = record
	model = WfCharacterRig.load_scene(path)
	if model == null:
		missing = path
		return false
	add_child(model)
	anim = model.find_child("AnimationPlayer", true, false) as AnimationPlayer
	if anim == null:
		missing = path + " (no AnimationPlayer)"
		return false
	var acts: Dictionary = record.get("actions", {})
	for lib_name in anim.get_animation_library_list():
		var lib := anim.get_animation_library(lib_name)
		for n in lib.get_animation_list():
			var a: Animation = lib.get_animation(n).duplicate(true)
			var info: Dictionary = acts.get(n, {})
			a.loop_mode = Animation.LOOP_LINEAR if info.get("loop", false) else Animation.LOOP_NONE
			clip_speed[n] = _strip_root(a)
			lib.add_animation(n, a)
	ok = true
	return true

static func load_scene(path: String) -> Node3D:
	if ResourceLoader.exists(path):
		var r = load(path)
		if r is PackedScene:
			return r.instantiate()
	var abs_p := ProjectSettings.globalize_path(path)
	if FileAccess.file_exists(abs_p):
		var doc := GLTFDocument.new()
		var st := GLTFState.new()
		if doc.append_from_file(abs_p, st) == OK:
			return doc.generate_scene(st)
	return null

## Remove the Root bone's position track; return the horizontal travel speed it carried (0 for an in-place clip).
static func _strip_root(a: Animation) -> float:
	for i in a.get_track_count():
		var p := String(a.track_get_path(i))
		if a.track_get_type(i) == Animation.TYPE_POSITION_3D and p.ends_with(":Root"):
			var n := a.track_get_key_count(i)
			var v := 0.0
			if n > 1 and a.length > 0.0:
				var d: Vector3 = a.track_get_key_value(i, n - 1) - a.track_get_key_value(i, 0)
				d.y = 0.0                     # glTF +Y up: the vertical part is not travel
				# the last key is one frame short of the cycle: travel over (n - 1) frames in (n - 1) / n of the loop
				var t1: float = a.track_get_key_time(i, n - 1) - a.track_get_key_time(i, 0)
				v = d.length() / t1 if t1 > 0.0 else 0.0
			a.remove_track(i)
			return v
	return 0.0

func has(clip: String) -> bool:
	return anim != null and anim.has_animation(clip)

func length(clip: String) -> float:
	return anim.get_animation(clip).length if has(clip) else 0.0

## Play `clip` (crossfading over `blend` s) at `rate` x its authored speed; negative rate plays it backwards (walking backward).
func play(clip: String, rate := 1.0, blend := 0.2) -> void:
	if not ok or not has(clip):
		return
	var back := rate < 0.0
	if clip != current or back != reversed:
		if back:
			anim.play_backwards(clip, blend)
		else:
			anim.play(clip, blend)
		current = clip
		reversed = back
	anim.speed_scale = maxf(absf(rate), 0.05)

## The rate that makes a travel clip match a physics speed (1 for an in-place clip).
func rate_for(clip: String, speed_m_s: float) -> float:
	var v: float = clip_speed.get(clip, 0.0)
	return speed_m_s / v if v > 1e-3 else 1.0

func finished() -> bool:
	return anim == null or not anim.is_playing() or (anim.current_animation_position >= anim.current_animation_length - 1e-3 and not reversed)

func position_of(clip: String) -> float:
	return anim.current_animation_position if current == clip and anim != null else 0.0

## World position of a bone's head (for foot checks).
func bone_world(bone: String) -> Vector3:
	var sk := model.find_children("*", "Skeleton3D", true, false)
	if sk.is_empty():
		return Vector3.INF
	var s: Skeleton3D = sk[0]
	var i := s.find_bone(bone)
	return s.global_transform * s.get_bone_global_pose(i).origin if i >= 0 else Vector3.INF
