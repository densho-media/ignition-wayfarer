extends SceneTree
## Integration check against independently recorded Blender-space measurements.
var found := {}
var materials := {}
var bounds := AABB()
var first := true

func fail(message: String) -> void:
	push_error(message)
	quit(1)

func _initialize() -> void:
	var docked := "--docked" in OS.get_cmdline_user_args()
	var manifest_file := "manifest_docked.json" if docked else "manifest.json"
	var manifest = JSON.parse_string(FileAccess.get_file_as_string("res://generated/" + manifest_file))
	var rig = JSON.parse_string(FileAccess.get_file_as_string("res://generated/wf_sim_rig.json"))
	if manifest == null or rig == null:
		fail("Missing runtime manifest or rig")
		return
	if not (int(manifest.contract_version) in [1, 2]) or manifest.spec_hash != rig.spec_hash or manifest.source_map_hash != rig.source_map_hash:
		fail("Mixed or unsupported runtime package")
		return
	for file in manifest.files:
		if FileAccess.get_sha256("res://generated/" + file) != manifest.files[file]:
			fail("Package hash mismatch: " + file)
			return
	if not docked:
		# RT-003: the timeline copy must be the one the rig hashes, and every ring binding must reach imported meshes.
		var timeline = JSON.parse_string(FileAccess.get_file_as_string("res://generated/" + manifest.timeline.file))
		if timeline == null or not manifest.files.has(manifest.timeline.file) or FileAccess.get_sha256("res://generated/" + manifest.timeline.file) != rig.flight_timeline.sha256:
			fail("The First Ignition timeline is missing or does not match the rig")
			return
		for key in manifest.timeline.mechanisms:
			var binding: Dictionary = manifest.timeline.mechanisms[key]
			if not timeline.channels.has(binding.channel) or not manifest.nodes.any(func(record): return record.get("frame", "") == key):
				fail("Mechanism binding without a channel or meshes: " + key)
				return
	if docked and (manifest.preset != "DOCKED" or rig.induction_route.rail.size() < 2 or rig.induction_route.stops.is_empty() or float(rig.induction_route.get("envelope", {}).get("radius_m", 0.0)) <= 0.0):
		fail("Boarding requires a DOCKED package and the rig's induction route with its envelope")
		return
	if docked:
		# RT-004: every closure the route opens has a binding and meshes; the route's ring and drum have bindings and carry meshes.
		var mech: Dictionary = manifest.induction.get("mechanisms", {})
		var route: Dictionary = rig.induction_route
		if mech.is_empty() or not route.has("frames") or not mech.rotors.has(route.frames.RING) or not mech.drums.has(route.frames.DRUM):
			fail("Boarding requires the transfer mechanisms and the route's frames")
			return
		for id in [route.frames.RING, route.frames.DRUM]:
			if not manifest.nodes.any(func(record): return record.get("frame", "") == id):
				fail("No mesh turns with " + id)
				return
		for leg in route.legs:
			for opening in leg.openings:
				for name in opening.closures:
					if not mech.closures.has(name) or not manifest.nodes.any(func(record): return record.get("closure", "") == name):
						fail("Route closure without a binding or meshes: " + name)
						return
	var packed = load("res://generated/wayfarer_docked.glb" if docked else "res://generated/wayfarer.glb") as PackedScene
	if packed == null:
		fail("GLB failed to import")
		return
	var ship = packed.instantiate()
	root.add_child(ship)
	visit(ship, Transform3D.IDENTITY)
	for record in manifest.nodes:
		if not found.has(record.node):
			fail("Missing imported mesh " + record.node)
			return
	if found.size() != manifest.nodes.size():
		fail("Unexpected imported meshes")
		return
	# FUT-003: the S004 look's emitters each carry a light class and an emitter centre; the count matches the manifest's summary.
	var lights: Array = manifest.nodes.filter(func(record): return record.has("light"))
	if not manifest.has("look") or lights.size() != int(manifest.look.lights) or lights.is_empty() \
			or lights.any(func(record): return record.light.centre_local_runtime_m.size() != 3 or float(record.light.range_m) <= 0.0):
		fail("S004 look lights missing or malformed")
		return
	# M7 (manifest v2): every production node names its assembly and maturity, and the count matches the manifest's summary.
	if int(manifest.contract_version) >= 2:
		var prod: Array = manifest.nodes.filter(func(record): return record.get("layer", "") == "PRODUCTION")
		if prod.size() != int(manifest.production.nodes) or prod.any(func(record): return str(record.get("assembly", "")) == "" or str(record.get("maturity", "")) == ""):
			fail("Production layer nodes missing their assembly or maturity")
			return
		# M8: each node's maturity is its own assembly's (M8 candidates never carry M7's acceptance)
		elif prod.any(func(record): return not manifest.production.assemblies.has(record.assembly) or str(manifest.production.assemblies[record.assembly].maturity) != str(record.maturity)):
			fail("Production layer node maturity differs from its assembly's")
			return
	# FUT-003 step 2: the flight timeline's First Ignition look finds its hot-face materials in the imported package.
	if not docked:
		var exterior: Dictionary = manifest.look.get("exterior", {})
		if exterior.is_empty() or exterior.sun_runtime.size() != 3 or Array(exterior.hot_face).any(func(name): return not materials.has(name)):
			fail("First Ignition look missing or its hot-face materials not imported")
			return
	var lo: Array = manifest.bounds_runtime_m.min
	var hi: Array = manifest.bounds_runtime_m.max
	if bounds.position.distance_to(Vector3(lo[0], lo[1], lo[2])) > 0.02 or bounds.end.distance_to(Vector3(hi[0], hi[1], hi[2])) > 0.02:
		fail("Imported bounds differ from Blender export")
		return
	print("WF_GODOT_CHECK PASS meshes=", found.size(), " lights=", lights.size(), " bounds=", bounds)
	ship.free()
	quit(0)

func visit(node: Node, parent_transform: Transform3D) -> void:
	var transform := parent_transform
	if node is Node3D:
		transform = parent_transform * node.transform
	if node is MeshInstance3D:
		found[str(node.name)] = true
		for surface in range(node.mesh.get_surface_count()):
			var material: Material = node.mesh.surface_get_material(surface)
			if material:
				var name := material.resource_name.trim_prefix("Runtime_WF_MAT_")
				materials[name.substr(0, name.rfind("_"))] = true
		# Transform vertices, not local AABB corners (which overestimate rotated parts).
		for surface in range(node.mesh.get_surface_count()):
			var arrays = node.mesh.surface_get_arrays(surface)
			for vertex in arrays[Mesh.ARRAY_VERTEX]:
				var point: Vector3 = transform * vertex
				if first:
					bounds = AABB(point, Vector3.ZERO)
					first = false
				else:
					bounds = bounds.expand(point)
	for child in node.get_children():
		visit(child, transform)
