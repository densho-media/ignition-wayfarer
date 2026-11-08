class_name WfEvaBody
extends WfFreeBody
## An EVA body (EVA-OPS-001): the suited astronaut or the companion drone. WfFreeBody adds the ship-frame field (no gravity, no
## damping); this adds only physically modelled forces, all in the same fixed physics step:
##   thrust   the allocator's duties on the configuration's nozzles, fed by the body's tanks in feed-pressure order (gas = F / ve dt);
##            short of gas, every valve is scaled down together (a regulator dropping out), never refilled;
##   contact  Jolt's collision; standing exists only where the apparent acceleration presses the body into a supporting surface, and
##            walking is a friction-limited foot force (walk_friction x normal load), never a speed set from a key;
##   grip     a hand or foot restraint on a marked hold: the body moves with the ship (the hold takes the load);
##   tether   inextensible line to an anchor: at full length the outward relative velocity is removed (inelastic);
##   impulse  queued momentum exchanges (a push-off, a dock spring), applied once.
## Rotation integrates Euler's equations with the body's inertia tensor (gyroscopic term included). Nothing is frozen or damped
## unless a modelled controller fires thrusters to do it.

var kind := ""                      # "suit" / "drone" / "cartridge"
var ve := 637.4                     # effective exhaust velocity, from the package (Isp g0)
var dry_kg := 1.0
var carried_kg := 0.0               # what is attached and moves with this body (a docked drone, a held cartridge)
var feeds: Array = []               # WfN2Tank, tried in feed-pressure order (check valves: the higher regulated feed wins)
var onboard: Array = []             # every WfN2Tank this body carries (its mass counts), fed or isolated
var inertia_t := Basis.IDENTITY     # inertia tensor about the mass centre, body frame (kg m2), symmetric
var alloc: WfAllocator
var cmd_f := Vector3.ZERO           # commanded force and torque, body frame (set by the controller every physics step)
var cmd_t := Vector3.ZERO
var delivered_f := Vector3.ZERO     # what the valves actually produced last step (body frame)
var delivered_t := Vector3.ZERO
var saturation := 1.0
var gas_short := false              # last step wanted more gas than the feeds could give
var thrust_enabled := true
var standing := false               # feet on a supporting surface under apparent gravity
var support_normal := Vector3.UP
var walk_cmd := Vector3.ZERO        # desired walking velocity on the surface (world), set by the controller
var walk_friction := 0.6
var support_cos := 0.5
var turn_rate := 0.0                # yaw request while standing (rad/s), feet torque
var hold_anchor := Vector3.ZERO     # world point of the grip
var tether_on := false
var tether_anchor := Vector3.ZERO
var tether_len := 15.0
var tether_taut := false
var impulse_dv := Vector3.ZERO      # queued velocity change (world)
var impulse_w := Vector3.ZERO       # queued angular velocity change (world)
var passenger := false              # docked drone: carried by the suit body, no dynamics of its own
var max_contact_speed := 0.0
var gas_used_kg := 0.0
var contact_with := ""            # what the body last touched (diagnostics and HUD)
var boots: WfMagBoots = null        # LOCO-002: the suit's magnetic boots (null: none)
var mag_a := 0.0                    # the boots' pull this step (m/s2 toward the plate)
var walk_dir_now := Vector3.ZERO    # the walking request actually used this step (world)

func setup_eva(k: String, dry: float, inertia_diag: Vector3, exhaust_v: float) -> void:
	kind = k
	dry_kg = dry
	ve = exhaust_v
	inertia_t = Basis(Vector3(inertia_diag.x, 0, 0), Vector3(0, inertia_diag.y, 0), Vector3(0, 0, inertia_diag.z))
	setup_body(total_mass())
	center_of_mass_mode = RigidBody3D.CENTER_OF_MASS_MODE_CUSTOM   # the body origin is the mass centre, not the collision shape's centre
	center_of_mass = Vector3.ZERO
	inertia = inertia_diag

func gas_kg() -> float:
	var m := 0.0
	for t in onboard:
		m += (t as WfN2Tank).n2_kg
	return m

func usable_kg() -> float:
	var m := 0.0
	for t in feeds:
		m += (t as WfN2Tank).usable()
	return m

func total_mass() -> float:
	return dry_kg + gas_kg() + carried_kg

## Delta-v left on everything this body can burn now.
func dv_left() -> float:
	return WfEvaPkg.dv(total_mass(), usable_kg(), ve)

func world_inertia() -> Basis:
	var r := global_transform.basis.orthonormalized()
	return r * inertia_t * r.transposed()

func _after_field(state: PhysicsDirectBodyState3D, a_field: Vector3) -> void:
	var dt := state.step
	if passenger:
		return
	var r := state.transform.basis.orthonormalized()
	var v := state.linear_velocity
	var w := state.angular_velocity
	# ---- thrust: duties -> gas -> delivered wrench
	delivered_f = Vector3.ZERO
	delivered_t = Vector3.ZERO
	gas_short = false
	if alloc != null and thrust_enabled and not held:
		saturation = alloc.mix(cmd_f, cmd_t)
		var need := alloc.gas(dt, ve)
		if need > 0.0:
			var got := 0.0
			for t in feeds:
				got += (t as WfN2Tank).draw(need - got)
				if got >= need - 1e-12:
					break
			gas_used_kg += got
			if got < need - 1e-12:
				gas_short = true
				alloc.scale(got / need)
			var wr := alloc.wrench()
			delivered_f = wr[0]
			delivered_t = wr[1]
	var m := total_mass()
	if absf(mass - m) > 0.005:
		mass = m
	v += r * delivered_f / m * dt
	var iw := r * inertia_t * r.transposed()
	var tw: Vector3 = r * delivered_t
	w += iw.inverse() * (tw - w.cross(iw * w)) * dt
	# ---- queued impulses
	v += impulse_dv
	w += impulse_w
	impulse_dv = Vector3.ZERO
	impulse_w = Vector3.ZERO
	# ---- magnetic boots: attach / break away, and the pull of the attached pads (a bounded force, added like a field)
	mag_a = 0.0
	var mag_n := Vector3.ZERO
	if boots != null and not held:
		var res := boots.step(state.transform, v, m)
		mag_a = res[0]
		mag_n = res[1]
		v += -mag_n * mag_a * dt
	var press := a_field - mag_n * mag_a                       # what presses the body into a surface (field and pads)
	# ---- contact support: standing needs the apparent acceleration (or the pads' pull) to press into a supporting surface
	standing = false
	var n_sum := Vector3.ZERO
	for i in state.get_contact_count():
		var n := state.get_contact_local_normal(i)
		var o = state.get_contact_collider_object(i)
		contact_with = (o as Node).name if o is Node else "?"
		max_contact_speed = maxf(max_contact_speed, absf(v.dot(n)))
		n_sum += n
	var a_mag := press.length()
	if n_sum.length() > 0.1 and a_mag > 0.05:
		var n := n_sum.normalized()
		if n.dot(-press / a_mag) >= support_cos:
			standing = true
			# attached pads sit flat on the walkway plate: its smooth normal, not the faceted contact normal of the hull mesh (which
			# jumps between lathe segments and made the uprighting moment hunt at about 2 deg/s)
			support_normal = mag_n if mag_a > 0.0 and mag_n.dot(n) > 0.9 else n
	walk_dir_now = Vector3.ZERO
	var was_slipping := false
	if boots != null:
		was_slipping = boots.slipping
		boots.slipping = false
	if standing and not held:
		var an := -press.dot(support_normal)                   # normal load per kg (field and pads)
		var vt := v - support_normal * v.dot(support_normal)
		var want := walk_cmd - support_normal * walk_cmd.dot(support_normal)
		var mu := walk_friction
		if boots != null and mag_a > 0.0:
			mu = boots.mu
			if boots.blocked != "":
				want = Vector3.ZERO                           # a stepping boot cannot land: the planted one holds the body
		walk_dir_now = want
		var dv := want - vt
		var lim := mu * an * dt                               # Coulomb friction: the feet can change the tangential speed this much
		if dv.length() > lim:
			dv = dv.normalized() * lim
		if boots != null and mag_a > 0.0:
			var shear := (press - support_normal * press.dot(support_normal)).length()
			if shear > mu * an:                               # the field's shear exceeds what the pads' friction can hold: the boots slide
				if not was_slipping:
					boots.slips += 1
				boots.slipping = true
			var vn := v.dot(support_normal)
			if vn < 0.0:
				v -= support_normal * vn                      # the plate's reaction to the pads' pull (the contact takes it; nothing rebounds)
		v += dv
		# the feet also hold the body upright on the surface (a contact moment, not a thruster)
		var up := r.y
		var axis := up.cross(support_normal)
		var w_des := axis * 3.0 + support_normal * turn_rate
		var dw := w_des - w
		var wlim := walk_friction * an * dt * 4.0
		if dw.length() > wlim:
			dw = dw.normalized() * wlim
		w += dw
	if boots != null and not held:
		var vt2 := v - support_normal * v.dot(support_normal)
		boots.advance(state.transform, vt2.length() if standing else 0.0, (walk_cmd - support_normal * walk_cmd.dot(support_normal)) if standing else Vector3.ZERO, dt)
	if held:
		v = Vector3.ZERO
		w = Vector3.ZERO
	# ---- tether: inextensible line at full length
	tether_taut = false
	if tether_on:
		var d := state.transform.origin - tether_anchor
		var L := d.length()
		if L >= tether_len and L > 0.0:
			var u := d / L
			var out := v.dot(u)
			if out > 0.0:
				v -= u * out
			tether_taut = true
	state.linear_velocity = v
	state.angular_velocity = w

## A momentum exchange with something much heavier (the ship): the body gains dv (world) at the next step.
func add_impulse(dv: Vector3) -> void:
	impulse_dv += dv
