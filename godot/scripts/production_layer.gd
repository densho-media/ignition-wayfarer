class_name WfProductionLayer
## M7: runtime handling of the production layer (manifest v2 nodes with layer PRODUCTION). Presentation only: the detail draws within
## RANGE_M of the camera and fades out beyond, so whole-ship views do not pay for interior panels; nothing here changes geometry,
## colliders or spacecraft facts. Each node keeps its assembly and maturity as metadata for inspection.

const RANGE_M := 28.0
const FADE_M := 4.0

static func apply(model: Node, manifest: Dictionary) -> int:
	var records := {}
	for record in manifest.get("nodes", []):
		if record.get("layer", "") == "PRODUCTION":
			records[record.node] = record
	if records.is_empty():
		return 0
	var count := 0
	for item in model.find_children("WF_*", "MeshInstance3D", true, false):
		var id := str(item.name).get_slice(".", 0)
		if not records.has(id):
			continue
		var mesh := item as MeshInstance3D
		# M8 exterior nodes carry their own range (panels from far, fasteners and lettering close); M7 interiors keep RANGE_M.
		mesh.visibility_range_end = float(records[id].get("detail_range_m", RANGE_M))
		mesh.visibility_range_end_margin = FADE_M
		mesh.visibility_range_fade_mode = GeometryInstance3D.VISIBILITY_RANGE_FADE_SELF
		mesh.set_meta("assembly", records[id].get("assembly", ""))
		mesh.set_meta("maturity", records[id].get("maturity", ""))
		count += 1
	return count
