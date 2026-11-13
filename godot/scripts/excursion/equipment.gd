class_name WfEquipment
extends RefCounted
## SYS-001 (Phase 0 proof, `#interior-systems` / `-- --systems`): one piece of real equipment in the walk that operates an engineering
## state. The ring A sector 3 ECLSS bay (the package's binding) houses the ring's CO2-removal unit (WfCabinAir). Ops at the bay isolates
## or restores the unit through the model's own transitions; the bay's status board and the HUD line show the model's readout. This is
## the interaction and display layer only: the numbers, transitions and bands all come from the package (src/wayfarer/cabin_air.py).
## The default Explore Interior start does not create it.

const TIMELAPSE := 60.0          # PROTOTYPE display: simulated seconds per real second (shown on the board)
const BAND_COLOURS := {"NOMINAL": Color(0.45, 0.85, 0.55), "ABOVE_TARGET": Color(0.95, 0.80, 0.35), "CONTROL": Color(0.98, 0.55, 0.25),
	"DEGRADED": Color(0.98, 0.40, 0.30), "DANGER": Color(1.0, 0.25, 0.25)}

var air: WfCabinAir = null
var binding := {}
var mesh: MeshInstance3D = null
var board := Label3D.new()
var host: Node = null
var timelapse := TIMELAPSE
var operations := 0

func _init(by_name: Dictionary, manifest: Dictionary, owner: Node) -> void:
	host = owner
	air = WfCabinAir.load_package()
	if air == null:
		push_warning("SYS-001: wf_cabin_air.json is not in the package; run runtime-export")
		return
	binding = air.doc["binding"]
	var by_source := {}
	for r in manifest.get("nodes", []):
		by_source[str(r.get("source_name", ""))] = str(r.get("node", ""))
	mesh = WfLearning._mesh(by_name.get(by_source.get(binding["node"], binding["node"])))
	if mesh == null:
		push_warning("SYS-001: equipment node %s not in the package" % binding["node"])
		return
	board.pixel_size = 0.0022
	board.font_size = 32
	board.outline_size = 10
	board.billboard = BaseMaterial3D.BILLBOARD_ENABLED   # faces the viewer, upright in their view (world Y is not up in a spinning ring)
	board.no_depth_test = false
	board.horizontal_alignment = HORIZONTAL_ALIGNMENT_LEFT
	mesh.add_child(board)                      # rides the ring with the bay
	board.position = _board_at()
	update()

## Above the bay in spin gravity: towards the ring's spin axis from the bay's centre, past the bay's top, in the mesh's frame.
func _board_at() -> Vector3:
	var box := mesh.get_aabb()
	var g := mesh.global_transform * box.get_center()
	var frames = host.get("frames")
	if frames is Dictionary:
		for id in frames:
			var f: Dictionary = frames[id]
			if id != "STATIONARY" and (f["node"] as Node).is_ancestor_of(mesh):
				var piv: Node3D = f["node"]
				var c := piv.global_transform.affine_inverse() * g
				var ax: Vector3 = (f["axis"] as Vector3).normalized()
				var inward := -(c - ax * c.dot(ax)).normalized()
				var local_in := (mesh.global_transform.basis.inverse() * (piv.global_transform.basis * inward)).normalized()
				var half := 0.5 * absf(box.size.dot(local_in.abs()))
				return box.get_center() + local_in * (half + 0.35)
	return box.get_center() + Vector3(0, box.size.y * 0.5 + 0.35, 0)

func ready() -> bool:
	return air != null and mesh != null and air.verified

## The bay's centre in the walking body's frame (the same rule as WfLearning.centre: a ring's meshes ride its spinning pivot).
func centre() -> Vector3:
	return to_body(mesh.global_transform * mesh.get_aabb().get_center())

## A world point on the ring (for example the board's) in the walking body's frame.
func to_body(g: Vector3) -> Vector3:
	var frames = host.get("frames")
	if frames is Dictionary:
		for id in frames:
			var f: Dictionary = frames[id]
			if id != "STATIONARY" and (f["node"] as Node).is_ancestor_of(mesh):
				var piv: Node3D = f["node"]
				return piv.get_parent().global_transform * (f["rest"] + piv.global_transform.affine_inverse() * g)
	return g

func in_reach(p: Vector3, zone: String) -> bool:
	return ready() and zone == str(binding["ring"]) and p.distance_to(centre()) <= float(binding["reach_m"])

## The operation Ops would request now.
func next_op() -> String:
	return "isolate" if air.state == "RUNNING" else "restore"

func op_label() -> String:
	return "isolate CO2 unit" if next_op() == "isolate" else "restore CO2 unit"

## Ops at the bay: ask the model for the operation; the model decides (refusals come back as text).
func operate() -> String:
	var op := next_op()
	var r := air.operate(op)
	operations += 1
	update()
	if r != "":
		return "ECLSS: " + r
	if op == "isolate":
		return "ECLSS: CO2-removal unit ISOLATED (powered off and valved out for maintenance). Ring A's CO2 now rises with every breath."
	return "ECLSS: CO2-removal unit RUNNING again. The bed scrubs the ring back towards its steady state."

func step(dt: float) -> void:
	if ready():
		air.step(dt * timelapse)

func _hm(h) -> String:
	if h == null:
		return "-"
	var mins := int(round(float(h) * 60.0))
	return "%d h %02d min" % [mins / 60, mins % 60]

## The board's text: only what the model reads out.
func text() -> String:
	if air == null:
		return ""
	if not air.verified:
		return "RING A CO2 MODEL\nREFERENCE CHECK FAILED\n" + str(air.errors[0])
	var r := air.readout()
	var trend := "%+.3f %%/h" % (100.0 * float(r["dxdt_per_h"]))
	var limit := "Control limit %.1f %%: %s" % [100.0 * float(air.p["co2_max"]),
		"in " + _hm(r["hours_to_control_limit"]) if r["hours_to_control_limit"] != null else "not approaching"]
	return "RING A CABIN CO2\nSIMULATION x%d\n%.3f %%  ·  %.2f kPa\ntrend %s\nUnit %s  ·  %s\n%s" % [int(timelapse),
		100.0 * float(r["x"]), float(r["pp_kpa"]), trend, r["state"], str(r["band"]).replace("_", " "), limit]

func update() -> void:
	if mesh == null or air == null:
		return
	board.text = text()
	board.modulate = BAND_COLOURS.get(str(air.readout()["band"]), Color.WHITE) if air.verified else Color(1, 0.3, 0.3)

## The HUD prompt line while the bay is in reach.
func prompt(key_text: String) -> String:
	var r := air.readout()
	return "%s %s  ·  CO2 %.3f %% (%s)" % [key_text, op_label(), 100.0 * float(r["x"]), air.band_meaning(str(r["band"])) if r["band"] != "NOMINAL" else "within the control band"]

## The browser/headless record (window.wayfarerWalk.systems).
func record() -> Dictionary:
	if air == null:
		return {}
	var r := air.readout()
	return {"verified": air.verified, "state": air.state, "x": snappedf(float(r["x"]), 1e-7), "band": r["band"], "t_s": snappedf(air.t_s, 0.01),
		"operations": operations}
