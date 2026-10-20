class_name WfM5Gnc
extends Node3D
## M5 chapter 5 (owner 2026-10-18, S&E 15!A210/A211/A212, 98!A116): the attitude modes and the COAST comms picture played over the
## hologram. Presentation only: every limit, grid, light time and jet pattern comes from the chapter's gnc block in
## generated/m5/wf_m5_holo.json (references/m5_gnc_comms.json). Nothing here is a flight rate, a link budget or a release:
##   - contact per antenna is the built-model ray screen (blades, rings, shield, hull; the 15 deg plume study cone in a burn), looked up
##     in the exported sky grids for the current attitude and Earth phase (radial outbound coast: Earth asin(1/d) off -X, one turn a year);
##   - light time is d x 499 s; data is counted in hours of generation (bytes and kb/s stay null);
##   - the backlog drains at the ILLUSTRATIVE display ratio in the data (the real downlink rate is null);
##   - the FORWARD_PROTECTED wander inside the 0.2 deg target is ILLUSTRATIVE (disturbances OPEN);
##   - slews run at the 0.05 deg/s reference rate; the RCS cones that light are the B1F force-free start / stop pattern.

const MODES := ["FORWARD_PROTECTED", "LOW_HAZARD_SLEW", "MAINTENANCE_HOLD"]
const WARPS := [60.0, 600.0, 3600.0, 21600.0, 86400.0]          # mission seconds per real second
const SLEW_TARGET_DEG := 90.0                                   # LOW_HAZARD_SLEW demonstration turn (yaw), display choice
const BEAM_M := 140.0
const CONE_M := 160.0

var host: Node                      # m5_holo.gd
var g: Dictionary                   # the chapter's gnc block
var body: Node3D                    # ship + studies, turned about the centre of mass
var com := Vector3.ZERO             # runtime frame
var mesh := ImmediateMesh.new()
var draw := MeshInstance3D.new()
var line_mat := StandardMaterial3D.new()
var cones := {}                     # nozzle name -> MeshInstance3D (Study_RCSB_Plume_Alt_* and _Built_*)
# Simulation state (read by the panel, the guided session and the headless check).
var active := false
var mode := 0
var burning := false
var dist_i := 0
var warp_i := 1
var t := 0.0                        # mission seconds since the demo started
var yaw := 0.0                      # deg, body about +Z (Blender) = +Y (runtime)
var slew_from := 0.0
var slew_t0 := -1.0
var contact := {}                   # antenna -> bool
var onboard: Array = []             # FIFO of [gen_t0, gen_t1] not yet sent
var flight: Array = []              # [gen_t0, gen_t1, send_t, arrive_t]
var received_s := 0.0
var earth_newest := 0.0             # newest generation time Earth has received
var outage_t0 := -1.0
var last_outage := [-1.0, -1.0]
var refused := ""
var max_backlog := 0.0

func _init(h: Node, gnc: Dictionary, b: Node3D) -> void:
	host = h
	g = gnc
	body = b
	var c: Array = g.com_m
	com = Vector3(c[0], c[2], -c[1])
	dist_i = maxi(0, g.distances_au.find(30.0))
	line_mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	line_mat.vertex_color_use_as_albedo = true
	line_mat.no_depth_test = true
	draw.mesh = mesh
	draw.material_override = line_mat
	draw.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF

func _ready() -> void:
	add_child(draw)
	for item in host.meshes:
		var r: Dictionary = host.info[item.get_meta("node")].record
		var n := str(r.get("name", ""))
		if n.begins_with("Study_RCSB_Plume_"):
			cones[n.trim_prefix("Study_RCSB_Plume_Alt_").trim_prefix("Study_RCSB_Plume_Built_")] = item
	for a in g.sky:
		contact[a] = false

func au() -> float:
	return float(g.distances_au[dist_i])

func light_s() -> float:
	return au() * float(g.au_light_s)

func backlog_s() -> float:
	return onboard.reduce(func(s, c): return s + c[1] - c[0], 0.0)

func in_flight_s() -> float:
	return flight.reduce(func(s, c): return s + c[1] - c[0], 0.0)

func aligned() -> bool:
	return absf(yaw) < 0.2

func slewing() -> bool:
	return absf(yaw - target_yaw()) > 1e-6

func target_yaw() -> float:
	return SLEW_TARGET_DEG if mode == 1 else 0.0

func set_active(on: bool) -> void:
	active = on
	draw.visible = on
	if not on:
		body.transform = Transform3D.IDENTITY
	else:
		_apply_body()

# ---- controls (refusals carry the rule that refuses them) ------------------------------------------------------------------------

func cycle_mode() -> void:
	if burning:
		refused = "End the burn first: a burn is FORWARD_PROTECTED flight."
		return
	mode = (mode + 1) % MODES.size()
	refused = ""

func toggle_burn() -> void:
	if not burning and mode != 0:
		refused = "Burns only in FORWARD_PROTECTED (MAINTENANCE_HOLD needs DRIVE_SAFE; a slew is not protected flight)."
		return
	if not burning and not aligned():
		refused = "Not aligned to ram yet: wait for the return slew to finish."
		return
	burning = not burning
	refused = ""

func cycle_range(d := 1) -> void:
	dist_i = posmod(dist_i + d, g.distances_au.size())

func cycle_warp(d: int) -> void:
	warp_i = clampi(warp_i + d, 0, WARPS.size() - 1)

# ---- simulation ------------------------------------------------------------------------------------------------------------------

func _process(dt: float) -> void:
	if not active:
		return
	step(dt * WARPS[warp_i])
	_draw()

## Advance the mission clock by dt seconds (sub-stepped so a fast warp does not skip a contact change).
func step(dt: float) -> void:
	var n := maxi(1, ceili(dt / 600.0))
	for k in n:
		_tick(dt / n)

func _tick(dt: float) -> void:
	t += dt
	# attitude: constant reference rate toward the mode's target (start / stop impulses shown as cone pulses)
	var tgt := target_yaw()
	if slewing():
		if slew_t0 < 0.0:
			slew_t0 = t - dt
			slew_from = yaw
		var rate := 0.05 * dt
		yaw = tgt if absf(tgt - yaw) <= rate else yaw + signf(tgt - yaw) * rate
	else:
		slew_t0 = -1.0
	_apply_body()
	# contact per antenna for the current attitude, Earth phase and burn state
	var any := false
	for a in g.sky:
		contact[a] = clear(a)
		any = any or contact[a]
	if not any and outage_t0 < 0.0:
		outage_t0 = t
	elif any and outage_t0 >= 0.0:
		last_outage = [outage_t0, t]
		outage_t0 = -1.0
	# generation (one hour of data per hour), store and forward FIFO, light-time flight
	if not onboard.is_empty() and is_equal_approx(onboard[-1][1], t - dt):
		onboard[-1][1] = t
	else:
		onboard.append([t - dt, t])
	if any:
		var cap: float = float(g.backlog.display_drain_ratio) * dt
		while cap > 1e-9 and not onboard.is_empty():
			var c: Array = onboard[0]
			var take := minf(cap, c[1] - c[0])
			flight.append([c[0], c[0] + take, t, t + light_s()])
			c[0] += take
			cap -= take
			if c[1] - c[0] <= 1e-9:
				onboard.pop_front()
	while not flight.is_empty() and flight[0][3] <= t:
		var f: Array = flight.pop_front()
		received_s += f[1] - f[0]
		earth_newest = maxf(earth_newest, f[1])
	max_backlog = maxf(max_backlog, backlog_s())

func earth_dir_blender() -> Vector3:
	var off := asin(minf(1.0, 1.0 / au()))
	var ph := TAU * t / float(g.year_s)
	return Vector3(-cos(off), sin(off) * cos(ph), sin(off) * sin(ph))

## The exported ray screen for antenna a: Earth's direction turned into the body frame, looked up in the coast or burn grid.
func clear(a: String) -> bool:
	var e := earth_dir_blender()
	var p := deg_to_rad(yaw)
	var b := Vector3(cos(p) * e.x + sin(p) * e.y, -sin(p) * e.x + cos(p) * e.y, e.z)
	var pol := rad_to_deg(acos(clampf(-b.x, -1.0, 1.0)))
	var az := fposmod(rad_to_deg(atan2(b.z, b.y)), 360.0)
	var sky: Dictionary = g.sky[a]
	var step_deg: float = sky.step_deg
	var rows: Array = sky.burn if burning else sky.coast
	var j := clampi(int(pol / step_deg), 0, rows.size() - 1)
	var row: String = rows[j]
	return row[clampi(int(az / step_deg), 0, row.length() - 1)] == "1"

func _apply_body() -> void:
	var basis := Basis(Vector3.UP, deg_to_rad(yaw))
	body.transform = Transform3D(basis, com - basis * com)

# ---- drawing ---------------------------------------------------------------------------------------------------------------------

static func rt(v: Array) -> Vector3:
	return Vector3(v[0], v[2], -v[1])

func _line(a: Vector3, b: Vector3, c: Color) -> void:
	mesh.surface_set_color(c)
	mesh.surface_add_vertex(a)
	mesh.surface_set_color(c)
	mesh.surface_add_vertex(b)

func _draw() -> void:
	mesh.clear_surfaces()
	mesh.surface_begin(Mesh.PRIMITIVE_LINES)
	var B := body.transform
	var shield := B * Vector3(float(g.shadow.shield_x_m), 0, 0)
	var axis := B.basis * Vector3.RIGHT
	# velocity (inertial +X) and the body axis; in FORWARD_PROTECTED an ILLUSTRATIVE wander inside the 0.2 deg target
	var wander := Vector3.ZERO
	if mode == 0 and aligned():
		var w := deg_to_rad(0.12)
		wander = Vector3(0, sin(t / 5400.0) * w, cos(t / 7300.0) * w)
	_line(shield, shield + (Vector3.RIGHT + wander) * CONE_M, Color(1, 1, 1))
	_line(shield, shield + axis * CONE_M * 0.6, Color(0.95, 0.85, 0.3))
	# shield-shadow limit per azimuth (red, built geometry, no margin) and the 0.2 deg design target (green), both body-fixed
	var limit: Array = g.shadow.per_azimuth
	var prev := Vector3.ZERO
	for k in limit.size() + 1:
		var r: Array = limit[k % limit.size()]
		var th := deg_to_rad(float(r[1]))
		var ph := deg_to_rad(float(r[0]))
		var d := Vector3(cos(th), sin(th) * sin(ph), -sin(th) * cos(ph))       # Blender (x, y, z) tilt toward phi, in runtime axes
		var p := shield + B.basis * d.normalized() * CONE_M
		if k > 0:
			_line(prev, p, Color(0.9, 0.3, 0.3))
		if k % 12 == 0:
			_line(shield, p, Color(0.5, 0.2, 0.2))
		prev = p
	for k in 49:
		var a := TAU * k / 48.0
		var th := deg_to_rad(0.2)
		var p := shield + B.basis * Vector3(cos(th), sin(th) * sin(a), -sin(th) * cos(a)) * CONE_M
		if k > 0:
			_line(prev, p, Color(0.3, 0.9, 0.5))
		prev = p
	# Earth line from each gimbal (inertial direction): green clear, red blocked; packets in flight ride the first clear line
	var e := earth_dir_blender()
	var ew := Vector3(e.x, e.z, -e.y)
	var lead := ""
	for a in g.sky:
		var gp := B * rt(g.sky[a].gimbal)
		var col := Color(0.25, 0.9, 0.45) if contact[a] else Color(0.95, 0.3, 0.25)
		_line(gp, gp + ew * BEAM_M, col)
		if contact[a] and lead == "":
			lead = a
	if lead != "":
		var gp := B * rt(g.sky[lead].gimbal)
		for f in flight:
			var u := clampf((t - float(f[2])) / maxf(1.0, float(f[3]) - float(f[2])), 0.0, 1.0)
			var p := gp + ew * BEAM_M * u
			for d in [Vector3(0, 3, 0), Vector3(0, 0, 3), Vector3(3, 0, 0)]:
				_line(p - d, p + d, Color(0.6, 0.85, 1.0))
	mesh.surface_end()
	_cones()

## RCS display cones: B1F start / stop pattern lights while a slew starts or stops; MAINTENANCE_HOLD inhibits the aft jets.
func _cones() -> void:
	var lit := {}
	if slew_t0 >= 0.0:
		var pat: Dictionary = g.rcs_patterns.B1F
		var tgt := target_yaw()
		var dir := "yaw+" if tgt > slew_from else "yaw-"
		var stop := "yaw-" if dir == "yaw+" else "yaw+"
		var burn_s: float = float(pat[dir].burn_s)
		var left := absf(tgt - yaw) / 0.05
		var which := dir if t - slew_t0 < burn_s else (stop if left < burn_s else "")
		if which != "":
			for j in pat[which].jets:
				lit[str(j).replace("Study_RCSBF_Fwd_", "Study_RCSB_Fwd_")] = true
	for n in cones:
		var item: MeshInstance3D = cones[n]
		if not item.visible:
			continue
		var c := Color(0.2, 0.75, 0.95)
		var role := "ghost"
		if lit.has(n):
			role = "subject"
		elif mode == 2 and "_Aft_" in n:
			c = Color(0.95, 0.25, 0.2)
			role = "subject"
		elif n.begins_with("Ext_RCS"):
			c = Color(0.95, 0.3, 0.22)
		item.material_override = host._material(c, role)

# ---- panel -----------------------------------------------------------------------------------------------------------------------

static func hours(s: float) -> String:
	return "%.1f d" % (s / 86400.0) if s >= 172800.0 else "%.1f h" % (s / 3600.0)

func panel_lines() -> Array[String]:
	var L: Array[String] = []
	var m: Dictionary = g.modes[MODES[mode]]
	L.append("[b]MODE  %s[/b]   ·   mission clock %s   ·   warp %s per s" % [MODES[mode], hours(t), hours(WARPS[warp_i])])
	L.append("[color=#888780]%s[/color]" % m.purpose)
	if mode == 0:
		L.append("Hold target ≤ %.1f° (3σ, TARGET) inside the %.2f° geometric shadow limit (red). %s" % [float(m.pointing_target_deg_3sigma),
			float(m.geometric_limit_deg), "Aligned; the wander shown is ILLUSTRATIVE." if aligned() else "Returning to ram at the reference rate."])
	elif mode == 1:
		L.append("Yaw %.1f° → %.0f° at 0.05°/s reference: %s. Shield NOT aligned: only below the dust-speed limit (OPEN). B1F start / stop jets light." % [
			yaw, target_yaw(), "slewing" if slewing() else "holding"])
		L.append("[color=#F09595]180° flip FORBIDDEN at speed; the ideal %s min flip is SENSITIVITY ONLY.[/color]" % str(m.flip_sensitivity_only.ideal_180_min_as_built))
	else:
		L.append("DRIVE_SAFE · BLADES_COLD · aft RCS INHIBITED (red). Forward pods alone give roll only; pitch / yaw hold needs momentum storage (OPEN).")
	L.append("")
	L.append("[b]COMMS  %s AU[/b]   ·   one-way light time %s   ·   %s" % [str(g.distances_au[dist_i]), hours(light_s()),
		"[color=#F09595]BURN: Earth behind the plume (planned outage, 15!C210)[/color]" if burning else "coast"])
	var parts: Array[String] = []
	for a in g.sky:
		parts.append("%s [color=#%s]%s[/color]" % [a, "97C459" if contact[a] else "F09595", "contact" if contact[a] else "blocked"])
	L.append(" · ".join(parts))
	L.append("On board (store and forward): %s   ·   in flight: %s   ·   received at Earth: %s" % [hours(backlog_s()), hours(in_flight_s()), hours(received_s)])
	L.append("Earth's newest ship data is %s old (light time + backlog)." % hours(t - earth_newest) if received_s > 0.0 else
		"Earth has received nothing yet: the first data needs one light time (%s)." % hours(light_s()))
	L.append("[color=#888780]Data counted in hours of generation: bytes and kb/s NULL for GROUND_34M and Y155_RELAY. Drain ×%s is ILLUSTRATIVE.[/color]" % str(g.backlog.display_drain_ratio))
	if refused != "":
		L.append("[color=#F09595]✗ %s[/color]" % refused)
	L.append("[color=#888780]%s[/color]" % WfInput.keys("{holo.mode} mode · {holo.burn} burn · {holo.range} distance · {holo.warp_down}/{holo.warp_up} time warp"))
	return L
