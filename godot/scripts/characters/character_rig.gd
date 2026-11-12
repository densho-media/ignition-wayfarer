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
# LOCO-003 gait tree (enable_gait(), Explore Interior only): idle, walk and run blended by the measured floor speed with one shared gait
# phase, so the feet of the walk and the run strike together while the two mix (a speed-indexed blend space with phase-synchronised
# cycles, the usual game technique; a plain crossfade between two cycles of different length scissors the legs). Every other clip goes
# through a crossfading transition. The EVA suit keeps the plain AnimationPlayer.
var tree: AnimationTree = null
var phase := 0.0                  # 0..1 of the gait cycle; 0 = the right heel strikes
var gait_w := 0.0                 # walk 0 .. run 1
var move_w := 0.0                 # idle 0 .. moving 1
const ACT_FADE := 0.2

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
				d.y = 0.0                     # glTF +Y up: the vertical part is not travel over the floor
				# the last key is one frame short of the cycle: travel over (n - 1) frames in (n - 1) / n of the loop
				var t1: float = a.track_get_key_time(i, n - 1) - a.track_get_key_time(i, 0)
				var travel := d.length()
				if travel < 1e-3:
					# a vertical clip (the ladder climb carries the body up +Y): its travel is the climb (LOCO-003; read as 0 before, the
					# climb then played at the 0.05 m/s floor, ten times too fast)
					travel = absf(float((a.track_get_key_value(i, n - 1) - a.track_get_key_value(i, 0)).y))
				v = travel / t1 if t1 > 0.0 else 0.0
			a.remove_track(i)
			return v
	return 0.0

## Build the gait tree over the AnimationPlayer's (root-stripped) clips; false if the idle, walk or run clip is missing.
func enable_gait() -> bool:
	if not ok or not (has("idle") and has("walk") and has("run")):
		return false
	var bt := AnimationNodeBlendTree.new()
	var add_anim := func(name: String, clip: String) -> void:
		var a := AnimationNodeAnimation.new()
		a.animation = StringName(clip)
		bt.add_node(name, a)
	add_anim.call("walk", "walk")
	add_anim.call("run", "run")
	add_anim.call("idle", "idle")
	for n in ["walk", "run"]:
		bt.add_node(n + "_seek", AnimationNodeTimeSeek.new())
		bt.connect_node(n + "_seek", 0, n)
	bt.add_node("gait", AnimationNodeBlend2.new())
	bt.connect_node("gait", 0, "walk_seek")
	bt.connect_node("gait", 1, "run_seek")
	bt.add_node("move", AnimationNodeBlend2.new())
	bt.connect_node("move", 0, "idle")
	bt.connect_node("move", 1, "gait")
	var tr := AnimationNodeTransition.new()
	tr.xfade_time = ACT_FADE
	var others: Array = []
	for n in anim.get_animation_list():
		if not str(n) in ["walk", "run", "idle", "RESET"]:
			others.append(str(n))
	tr.input_count = 1 + others.size()
	tr.set_input_name(0, "loco")
	for i in others.size():
		var c: String = others[i]
		tr.set_input_name(i + 1, c)
		tr.set_input_reset(i + 1, true)
		add_anim.call("a_" + c, c)
		bt.add_node("ts_" + c, AnimationNodeTimeScale.new())
		bt.connect_node("ts_" + c, 0, "a_" + c)
	bt.add_node("act", tr)
	bt.connect_node("act", 0, "move")
	for i in others.size():
		bt.connect_node("act", i + 1, "ts_" + others[i])
	bt.connect_node("output", 0, "act")
	tree = AnimationTree.new()
	tree.name = "GaitTree"
	anim.get_parent().add_child(tree)
	tree.anim_player = tree.get_path_to(anim)
	tree.root_node = tree.get_path_to(anim.get_node(anim.root_node))
	tree.tree_root = bt
	anim.stop()
	tree.active = true
	return true

## The gait at floor speed v (m/s; back: walking backward), for one rendered frame of dt s. The phase advances by the distance walked over
## the blended stride, so neither cycle's planted foot slides by more than the two strides differ.
func gait(v: float, back: bool, dt: float, run_from: float, run_to: float) -> void:
	if tree == null:
		return
	var lw := length("walk")
	var lr := length("run")
	gait_w = 0.0 if back else smoothstep(run_from, run_to, v)
	move_w = smoothstep(0.03, 0.35, v)
	var stride := lerpf(float(clip_speed.get("walk", 1.0)) * lw, float(clip_speed.get("run", 2.4)) * lr, gait_w)
	phase = fposmod(phase + (-1.0 if back else 1.0) * v * dt / maxf(stride, 0.05), 1.0)
	tree.set("parameters/walk_seek/seek_request", phase * lw)
	tree.set("parameters/run_seek/seek_request", phase * lr)
	tree.set("parameters/gait/blend_amount", gait_w)
	tree.set("parameters/move/blend_amount", move_w)
	_act("loco")
	current = "run" if gait_w > 0.5 and move_w > 0.5 else ("walk" if move_w > 0.5 else "idle")
	reversed = back

func _act(input: String) -> void:
	if str(tree.get("parameters/act/current_state")) != input:
		tree.set("parameters/act/transition_request", input)

func has(clip: String) -> bool:
	return anim != null and anim.has_animation(clip)

func length(clip: String) -> float:
	return anim.get_animation(clip).length if has(clip) else 0.0

## Play `clip` (crossfading over `blend` s) at `rate` x its authored speed; negative rate plays it backwards (walking backward).
func play(clip: String, rate := 1.0, blend := 0.2) -> void:
	if not ok or not has(clip):
		return
	if tree != null:
		if clip in ["walk", "run", "idle"]:
			return                     # the gait tree plays these (gait())
		tree.set("parameters/ts_%s/scale" % clip, maxf(absf(rate), 0.05) * signf(rate) if rate != 0.0 else 0.05)
		_act(clip)
		current = clip
		reversed = rate < 0.0
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
	if tree != null:
		return phase * length(clip) if clip in ["walk", "run"] else 0.0
	return anim.current_animation_position if current == clip and anim != null else 0.0

## World position of a bone's head (for foot checks).
func bone_world(bone: String) -> Vector3:
	var sk := model.find_children("*", "Skeleton3D", true, false)
	if sk.is_empty():
		return Vector3.INF
	var s: Skeleton3D = sk[0]
	var i := s.find_bone(bone)
	return s.global_transform * s.get_bone_global_pose(i).origin if i >= 0 else Vector3.INF
