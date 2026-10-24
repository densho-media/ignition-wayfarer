extends Node
## ACI-02 (references/ACI_PLAN_2026-10-17.md): the one player-action registry, autoloaded as WfInput. Actions are semantic ids
## bound through Godot's InputMap; the player's bindings, onboarding preference, discovered actions and learned lessons live in
## user://wayfarer_controls.cfg (never in data/ or generated/). Gameplay asks Input/InputEvent for the action, prompts ask label().
## Bindings change which input triggers an action, never forces, speeds or permissions (S&E 46 DYN-007, 47 SIM-010, 49 NAV-003).
## Scenes not yet migrated read raw keys; those keys are RESERVED per context so a rebind cannot collide with them.
## MOB-001 (docs/wayfarer-mobile-controls-plan.md): touch is a fourth device of the same registry. The touch layer (wf_touch.gd) feeds
## hold actions through set_virtual() (read by strength()), press actions through trigger() (an InputEventAction that reaches the same
## scene handlers as the key) and looking through add_look() / take_look(); it never calls physics or bypasses a scene's own checks.

const SCHEMA := 3                       # 2: ACI-10 scene actions and the [access] settings; 3: MOB-001 [touch] settings
const PROFILE := "user://wayfarer_controls.cfg"
const PREFS := ["PERSONAL", "SUGGESTED", "EXPERIENCED"]
const DEADZONE := 0.5
const CAPTURE_AXIS := 0.6               # an analog stick counts as a capture only past this (drift filter)

# Contexts: ui is always active; walk (boarding rail camera) and body (body tour) exclude each other; menu is the review menu.
# ACI-09: nav is the Ship Navigator (demonstrator 01, beside the body tour: LINKED); space is the navigator's SPACE view, which takes
# the inputs it owns while it shows (the ship map and the body wait for those), so space shares inputs with nav and body freely.
# explorer is the navigator's SHOW ME sub-view (forward explorer, drone demo), read only while it is open on the ship map; demo is the
# demonstrator's chapter keys beside the walk, the body and the map. The other scenes each have their own context.
const CONTEXTS := {"ui": "Everywhere", "menu": "Review menu", "walk": "Induction walk (review camera)", "body": "Body mode (crew physics)",
	"nav": "Ship Navigator (demonstrator)", "space": "Space Navigator (SPACE view)", "explorer": "Navigator SHOW ME views",
	"demo": "Demonstrator 01 chapters", "inspector": "Ship inspector", "flight": "First Ignition timeline",
	"thermal": "Heat balance explorer (timeline)", "life": "Life-support simulator", "lab": "Physics lab", "eva": "EVA drift and tethers",
	"holo": "Subsystem hologram (M5 / M6)"}
const LINKED := {"nav": ["body", "demo", "explorer"], "body": ["nav", "demo"], "walk": ["demo"], "demo": ["walk", "body", "nav"],
	"explorer": ["nav"], "flight": ["thermal"], "thermal": ["flight"]}   # contexts whose scenes read input in the same frame

# kind: press / hold / axis. layout: physical (position on the keyboard, follows QWERTZ/AZERTY) or logical (the printed character).
const BASE_ACTIONS := [
	{"id": "ui.confirm", "name": "Confirm", "ctx": ["ui"], "kind": "press", "required": true, "layout": "logical",
		"keys": [KEY_ENTER, KEY_KP_ENTER], "joy": [{"t": "joyb", "b": JOY_BUTTON_A}],
		"what": "Confirm a choice and continue."},
	{"id": "ui.cancel", "name": "Back / cancel", "ctx": ["ui"], "kind": "press", "required": true, "layout": "logical",
		"keys": [KEY_ESCAPE], "joy": [{"t": "joyb", "b": JOY_BUTTON_B}], "locked": KEY_ESCAPE,
		"what": "Go back, close a panel or cancel a capture. Esc always works and cannot be reassigned."},
	{"id": "ui.codex", "name": "Control Codex", "ctx": ["ui"], "kind": "press", "required": true, "layout": "logical",
		"keys": [KEY_F10], "joy": [{"t": "joyb", "b": JOY_BUTTON_BACK}],
		"what": "Open this list of your controls: rebind, restore defaults, replay lessons."},
	{"id": "ui.guide", "name": "Hide / show guide", "ctx": ["ui"], "kind": "press", "layout": "logical", "keys": [KEY_F1], "joy": [],
		"what": "Hide or show the review guide's step card and key bar."},
	{"id": "ui.details", "name": "Guide details", "ctx": ["ui"], "kind": "press", "layout": "logical", "keys": [KEY_TAB], "joy": [],
		"what": "Expand or fold the engineering detail line of the review guide."},
	{"id": "player.move_forward", "name": "Move forward", "ctx": ["walk", "body", "lab", "eva"], "kind": "hold", "layout": "physical",
		"keys": [KEY_W], "joy": [{"t": "joya", "a": JOY_AXIS_LEFT_Y, "s": -1}],
		"what": "Walk on along the route, or forward on a ring deck; climb up a ladder.",
		"why": "On a ring deck you walk because spin gravity presses you onto it; in the weightless trunk this key adds no force (S&E 46 DYN-007)."},
	{"id": "player.move_back", "name": "Move back", "ctx": ["walk", "body", "lab", "eva"], "kind": "hold", "layout": "physical",
		"keys": [KEY_S], "joy": [{"t": "joya", "a": JOY_AXIS_LEFT_Y, "s": 1}],
		"what": "Walk back along the route or the deck; climb down a ladder."},
	{"id": "player.move_left", "name": "Move left", "ctx": ["walk", "body", "lab"], "kind": "hold", "layout": "physical",
		"keys": [KEY_A], "joy": [{"t": "joya", "a": JOY_AXIS_LEFT_X, "s": -1}],
		"what": "Step left on a ring deck (free flight: slide left)."},
	{"id": "player.move_right", "name": "Move right", "ctx": ["walk", "body", "lab"], "kind": "hold", "layout": "physical",
		"keys": [KEY_D], "joy": [{"t": "joya", "a": JOY_AXIS_LEFT_X, "s": 1}],
		"what": "Step right on a ring deck (free flight: slide right)."},
	{"id": "player.grab", "name": "Grab handhold", "ctx": ["body", "lab"], "kind": "press", "layout": "logical",
		"keys": [KEY_G], "joy": [{"t": "joyb", "b": JOY_BUTTON_X}],
		"what": "Grip the nearest rail within hand reach.",
		"why": "Holding the ship lets you exchange momentum with it: the grip takes your drift away (S&E 46 DYN-007, DYN-011)."},
	{"id": "player.release", "name": "Release", "ctx": ["body", "lab"], "kind": "press", "layout": "logical",
		"keys": [KEY_R], "joy": [{"t": "joyb", "b": JOY_BUTTON_Y}],
		"what": "Let go of the rail you hold.",
		"why": "Released, you keep the velocity you had; nothing slows you until you touch something."},
	{"id": "player.push", "name": "Push off", "ctx": ["body", "lab"], "kind": "press", "layout": "logical",
		"keys": [KEY_SPACE], "joy": [{"t": "joyb", "b": JOY_BUTTON_RIGHT_SHOULDER}],
		"what": "Push off the rail you hold, along your view.",
		"why": "Your arm pushes the ship and the ship pushes you: only a hand on a rail can change your speed (S&E 27 STG-001)."},
	# ACI-09 Ship Navigator (SNAV-001) and its SPACE view (SPACE-001): view state only, never the host, body, rings, doors or route.
	{"id": "ship.map", "name": "Ship map", "ctx": ["nav"], "kind": "press", "layout": "logical", "keys": [KEY_M], "joy": [],
		"what": "Cycle the ship map: corner locator, enlarged overview, hidden."},
	{"id": "ship.space", "name": "SHIP / SPACE view", "ctx": ["nav", "space"], "kind": "press", "layout": "logical", "keys": [KEY_B], "joy": [],
		"what": "Switch the navigator between the ship and where Wayfarer is in space."},
	{"id": "ship.mode", "name": "Guidance mode", "ctx": ["nav", "space"], "kind": "press", "layout": "logical", "keys": [KEY_J], "joy": [],
		"what": "Next guidance mode (Guided / Assisted / Free); both views share it.",
		"why": "A mode changes what the navigator explains, never what you may do aboard (S&E 48 WF-028, 49 NAV-003)."},
	{"id": "ship.target_next", "name": "Next target stop", "ctx": ["nav"], "kind": "press", "layout": "logical", "keys": [KEY_PERIOD], "joy": [],
		"what": "Choose the next stop for the route line on the ship map."},
	{"id": "ship.target_prev", "name": "Previous target stop", "ctx": ["nav"], "kind": "press", "layout": "logical", "keys": [KEY_COMMA], "joy": [],
		"what": "Choose the previous stop for the route line."},
	{"id": "ship.card", "name": "Systems card", "ctx": ["nav"], "kind": "press", "layout": "logical", "keys": [KEY_I], "joy": [],
		"what": "Open the systems card of the module you are in: WHAT, WHY THIS DESIGN, SHOW ME, close."},
	{"id": "ship.cutaway", "name": "Hull cutaway", "ctx": ["nav"], "kind": "press", "layout": "logical", "keys": [KEY_H], "joy": [],
		"what": "Cut the hull away on the enlarged ship map."},
	{"id": "ship.isolate", "name": "Isolate next module", "ctx": ["nav"], "kind": "press", "layout": "logical", "keys": [KEY_U], "joy": [],
		"what": "Show one module at a time on the enlarged ship map."},
	{"id": "space.step_next", "name": "Next route sample", "ctx": ["space"], "kind": "press", "layout": "logical", "keys": [KEY_PERIOD], "joy": [],
		"what": "Step to the next released route row (hold Shift for 30 rows).",
		"why": "Every value shown is one released row of 23_ROUTE_FRAMES: no interpolation, no new samples."},
	{"id": "space.step_prev", "name": "Previous route sample", "ctx": ["space"], "kind": "press", "layout": "logical", "keys": [KEY_COMMA], "joy": [],
		"what": "Step to the previous released route row (hold Shift for 30 rows)."},
	{"id": "space.live", "name": "Back to live", "ctx": ["space"], "kind": "press", "layout": "logical", "keys": [KEY_HOME], "joy": [],
		"what": "Leave the route rows: show the running scene (LIVE)."},
	{"id": "space.burn_end", "name": "Burn end row", "ctx": ["space"], "kind": "press", "layout": "logical", "keys": [KEY_END], "joy": [],
		"what": "Jump to the last released row."},
	{"id": "space.replay", "name": "Replay route", "ctx": ["space"], "kind": "press", "layout": "logical", "keys": [KEY_P], "joy": [],
		"what": "Play or pause the released rows at the route's own clock."},
	{"id": "space.card", "name": "Motion card", "ctx": ["space"], "kind": "press", "layout": "logical", "keys": [KEY_H], "joy": [],
		"what": "Open the MOTION card of the selected row: WHAT, WHY, HOW, close."},
	{"id": "space.attitude", "name": "Turn display hull", "ctx": ["space"], "kind": "press", "layout": "logical", "keys": [KEY_R], "joy": [],
		"what": "LOCAL scale: show and turn the display hull by 45° (Shift removes it).",
		"why": "The attitude is OPEN (C-013): the drawn hull is a display aid, never the ship's heading."},
	{"id": "space.inspect", "name": "Inspect / card page", "ctx": ["space"], "kind": "press", "layout": "logical", "keys": [KEY_I], "joy": [],
		"what": "Inspect the ship in the SHIP view; on the Solar System chart, page the selected body's card."},
	{"id": "space.chart_mode", "name": "Chart mode", "ctx": ["space"], "kind": "press", "layout": "logical", "keys": [KEY_M], "joy": [],
		"what": "Solar System chart: switch analytical / presentation drawing."},
	{"id": "space.zoom_out", "name": "Chart zoom out", "ctx": ["space"], "kind": "press", "layout": "logical", "keys": [KEY_MINUS], "joy": [],
		"what": "Solar System chart: zoom out."},
	{"id": "space.zoom_in", "name": "Chart zoom in", "ctx": ["space"], "kind": "press", "layout": "logical", "keys": [KEY_EQUAL], "joy": [],
		"what": "Solar System chart: zoom in."},
	{"id": "space.select_prev", "name": "Previous body", "ctx": ["space"], "kind": "press", "layout": "logical", "keys": [KEY_UP], "joy": [],
		"what": "Solar System chart: select the previous body or guide."},
	{"id": "space.select_next", "name": "Next body", "ctx": ["space"], "kind": "press", "layout": "logical", "keys": [KEY_DOWN], "joy": [],
		"what": "Solar System chart: select the next body or guide."},
	{"id": "space.scale_prev", "name": "Previous scale", "ctx": ["space"], "kind": "press", "layout": "logical", "keys": [KEY_BRACKETLEFT], "joy": [],
		"what": "Local space, mission journey, Solar System: the previous scale."},
	{"id": "space.scale_next", "name": "Next scale", "ctx": ["space"], "kind": "press", "layout": "logical", "keys": [KEY_BRACKETRIGHT], "joy": [],
		"what": "The next map scale."},
]

# ACI-09/10: every other scene's keys, compact: [contexts, [[id, name, default keys, what, controller defaults (optional), kind (optional)]]].
# A scene handler asks key_of(event, its contexts) and matches the action by its default key, so a rebind changes the input, not the code.
const SCENE_ACTIONS := [
	[["menu"], [["menu.session_1", "Open session 1", [KEY_1], "Open the first review session."], ["menu.session_2", "Open session 2", [KEY_2], "Open the second review session."],
		["menu.session_3", "Open session 3", [KEY_3], "Open the third review session."], ["menu.session_4", "Open session 4", [KEY_4], "Open the fourth review session."],
		["menu.session_5", "Open session 5", [KEY_5], "Open the fifth review session."], ["menu.session_6", "Open session 6", [KEY_6], "Open the sixth review session."],
		["menu.session_7", "Open session 7", [KEY_7], "Open the seventh review session."], ["menu.session_8", "Open session 8", [KEY_8], "Open the eighth review session."]]],
	[["walk"], [["walk.reset_view", "Reset view", [KEY_R], "Look straight along the route again."],
		["walk.free_flight", "Free flight", [KEY_F], "Leave the rail: fly the review camera freely (a review tool, not a crew capability)."],
		["walk.body_pace", "Body pace", [KEY_B], "Switch the review camera between review pace and body pace (rung by rung on ladders)."],
		["walk.collision", "Free-flight collision", [KEY_C], "Free flight: switch collision with the ship on or off."],
		["walk.light", "Inspection light", [KEY_L], "Switch between the inspection light and the S004 look."],
		["walk.fly_down", "Fly down", [KEY_Q], "Free flight: down.", [], "hold"], ["walk.fly_up", "Fly up", [KEY_E], "Free flight: up.", [], "hold"]]],
	[["walk", "eva"], [["player.fast", "Review pace ×8", [KEY_SHIFT], "Hold to move the review camera faster (free flight ×8, EVA review pace); not a crew speed.", [], "hold"]]],
	[["walk", "body"], [["tour.body_mode", "Body mode", [KEY_N], "Enter or leave body mode: the newcomer's body moved by the crew physics."]]],
	[["body"], [["body.spine", "Trunk beat", [KEY_1], "Body mode: back to the weightless trunk, holding the start rail."],
		["body.ring_a", "Ring A beat", [KEY_2], "Body mode: the ring A aisle in spin gravity."], ["body.ring_b", "Ring B beat", [KEY_3], "Body mode: the ring B deck in spin gravity."],
		["body.colliders", "Show colliders", [KEY_K], "Show the boxes the physics uses (the rig's rooms)."],
		["body.drop_tool", "Drop the tool", [KEY_T], "Drop a tool on a ring deck and watch where it lands (Coriolis)."]]],
	[["body", "demo"], [["body.view", "View from outside", [KEY_V], "Switch between first person and a view of the body from outside."]]],
	[["demo"], [["demo.pause", "Pause chapter", [KEY_P], "Pause or resume the demonstrator chapter."],
		["demo.autoplay", "Autoplay", [KEY_F2], "Let the chapter's body actions run by themselves (review aid; was A, which also walks left)."],
		["demo.occupants", "Occupant not secured", [KEY_O], "Fault drill: an occupant is not secured, so the ring sequence holds."],
		["demo.holo", "Hologram style", [KEY_F3], "Show the ship as the subsystem hologram, the engine hologram or its standard look (presentation only)."]]],
	[["explorer"], [["explorer.next", "Next", [KEY_X], "SHOW ME views: the next case or drone class."], ["explorer.view", "Explorer view", [KEY_Y], "SHOW ME views: switch the view."],
		["explorer.step", "Step", [KEY_K], "SHOW ME views: step the sequence."], ["explorer.back", "Back", [KEY_Z], "SHOW ME views: back."],
		["explorer.cycle", "Drone cycle", [KEY_C], "Drone demo: cycle the overlay."],
		["explorer.bay_1", "Forward bay 1", [KEY_1], "Forward explorer: bay 1."], ["explorer.bay_2", "Forward bay 2", [KEY_2], "Forward explorer: bay 2."],
		["explorer.bay_3", "Forward bay 3", [KEY_3], "Forward explorer: bay 3."], ["explorer.bay_4", "Forward bay 4", [KEY_4], "Forward explorer: bay 4."],
		["explorer.bay_5", "Forward bay 5", [KEY_5], "Forward explorer: bay 5."], ["explorer.bay_6", "Forward bay 6", [KEY_6], "Forward explorer: bay 6."],
		["explorer.bay_7", "Forward bay 7", [KEY_7], "Forward explorer: bay 7."], ["explorer.bay_8", "Forward bay 8", [KEY_8], "Forward explorer: bay 8."],
		["explorer.bay_9", "Forward bay 9", [KEY_9], "Forward explorer: bay 9."]]],
	[["space"], [["space.layer_1", "Track layer", [KEY_1], "SPACE: show or hide the track."], ["space.layer_2", "Motion layer", [KEY_2], "SPACE: the motion arrows."],
		["space.layer_3", "Events layer", [KEY_3], "SPACE: the events."], ["space.layer_4", "Orbits layer", [KEY_4], "SPACE: the orbits."],
		["space.layer_5", "Kuiper guide layer", [KEY_5], "SPACE: the Kuiper belt guide."], ["space.layer_6", "Grid layer", [KEY_6], "SPACE: the grid."],
		["space.layer_7", "Notes layer", [KEY_7], "SPACE: the notes."], ["space.layer_8", "Legend layer", [KEY_8], "SPACE: the legend."]]],
	[["inspector"], [["insp.view_side", "Side view", [KEY_1], "Inspector: side view."], ["insp.view_top", "Top view", [KEY_2], "Inspector: top view."],
		["insp.view_whole", "Whole ship", [KEY_3, KEY_HOME], "Inspector: three-quarter view of the whole ship."],
		["insp.focus", "Focus selection", [KEY_F], "Inspector: frame the selected subsystem."], ["insp.hide", "Hide selected", [KEY_H], "Inspector: hide or show the selected subsystem."],
		["insp.isolate", "Isolate selected", [KEY_I], "Inspector: show only the selected subsystem."],
		["insp.legend", "Radiator mount legend", [KEY_L], "Inspector: the radiator mount review legend (red datum / yellow slide)."]]],
	[["holo"], [["holo.chapter_1", "Thrust chain", [KEY_1], "M5 hologram: chapter 1, reactor, manifold and nozzles."],
		["holo.chapter_2", "Fuel and packaging", [KEY_2], "M5 hologram: chapter 2, fuel need against the BODY-C packaging."],
		["holo.chapter_3", "Refrigeration", [KEY_3], "M5 hologram: chapter 3, refrigeration, isolation and coil cooling."],
		["holo.chapter_4", "Nozzle load path", [KEY_4], "M5 hologram: chapter 4, as-built pickup against the axial bipod study."],
		["holo.chapter_5", "Attitude and comms", [KEY_5], "M5 hologram: chapter 5, attitude modes, antenna contact, light time and store and forward."],
		["holo.chapter_6", "EYE and shield", [KEY_6], "M6 hologram: chapter 6, the forward EYE, Dust Lance, Crown and shield."],
		["holo.chapter_7", "Habitat rings", [KEY_7], "M6 hologram: chapter 7, the counter-rotating rings, the spine and a crew walk."],
		["holo.chapter_8", "Radiators", [KEY_8], "M6 hologram: chapter 8, the radiator blades, loops, damage and isolation."],
		["holo.state", "Next state", [KEY_N], "M6 chapters: the next state (defence pose; stop and lock or spin up the rings; radiator operating step)."],
		["holo.event", "Event", [KEY_X], "M6 chapters: the chapter's event (dust stream; crew walk; damage radiator cells)."],
		["holo.response", "Response", [KEY_V], "M6 chapters: the chapter's response (ram alignment error; isolate or requalify radiator cells)."],
		["holo.loop", "Blade loop", [KEY_K], "M6 radiator chapter: isolate or restore one blade's coolant loop."],
		["holo.mode", "Attitude mode", [KEY_M], "M5 chapter 5: the next attitude mode (FORWARD_PROTECTED, LOW_HAZARD_SLEW, MAINTENANCE_HOLD)."],
		["holo.burn", "Burn on / off", [KEY_U], "M5 chapter 5: start or end a burn (FORWARD_PROTECTED only); Earth goes behind the plume."],
		["holo.range", "Distance", [KEY_R], "M5 chapter 5: the next distance from the Sun (light time, Earth angle)."],
		["holo.warp_down", "Slower clock", [KEY_BRACKETLEFT], "M5 chapter 5: slower mission clock."],
		["holo.warp_up", "Faster clock", [KEY_BRACKETRIGHT], "M5 chapter 5: faster mission clock."],
		["holo.overview", "Whole ship", [KEY_0, KEY_HOME], "M5 hologram: all twelve subsystems."],
		["holo.next", "Next subsystem", [KEY_PERIOD], "M5 hologram: the next subsystem on its own."], ["holo.prev", "Previous subsystem", [KEY_COMMA], "M5 hologram: the previous subsystem."],
		["holo.isolate", "Isolate", [KEY_I], "M5 hologram: show only the subjects, or bring the context back."],
		["holo.cutaway", "Dorsal cutaway", [KEY_C], "M5 hologram: cut the context away above the spine."],
		["holo.studies", "Study parts", [KEY_B], "M5 hologram: show or hide the STUDY parts (BODY-C, nozzle supports)."],
		["holo.frame", "Frame subjects", [KEY_F], "M5 hologram: frame the camera on the subjects."]]],
	[["flight"], [["flight.play", "Play / pause", [KEY_SPACE], "Timeline: play or pause."], ["flight.frame_next", "Frame forward", [KEY_RIGHT], "Timeline: one frame on (Shift: 24)."],
		["flight.frame_prev", "Frame back", [KEY_LEFT], "Timeline: one frame back (Shift: 24)."],
		["flight.view_1", "Camera 1", [KEY_1], "Timeline camera 1."], ["flight.view_2", "Camera 2", [KEY_2], "Timeline camera 2."], ["flight.view_3", "Camera 3", [KEY_3], "Timeline camera 3."],
		["flight.view_4", "Camera 4", [KEY_4, KEY_HOME], "Timeline camera 4 (whole ship)."], ["flight.view_5", "Camera 5", [KEY_5], "Timeline camera 5."],
		["flight.view_6", "Camera 6", [KEY_6], "Timeline camera 6."], ["flight.look", "Exterior look", [KEY_X], "Timeline: cycle the physically lit exterior looks (grammar, grammar with wear, proxy grey, off)."],
		["flight.scenario", "Radiator scenario", [KEY_Y], "Timeline: the next Y155 radiator scenario (DIAGNOSTIC)."],
		["thermal.toggle", "Heat balance", [KEY_T], "Open or close the heat balance explorer (HYPOTHETICAL inputs)."]]],
	[["thermal"], [["thermal.row_prev", "Previous input", [KEY_UP], "Heat balance: the previous input row."], ["thermal.row_next", "Next input", [KEY_DOWN], "Heat balance: the next input row."],
		["thermal.less", "Decrease", [KEY_MINUS], "Heat balance: decrease the selected input."], ["thermal.more", "Increase", [KEY_EQUAL], "Heat balance: increase the selected input."],
		["thermal.reset", "Owner values", [KEY_BACKSPACE], "Heat balance: back to the owner's reference values."]]],
	[["life"], [["life.row_prev", "Previous input", [KEY_UP], "Life support: the previous input row."], ["life.row_next", "Next input", [KEY_DOWN], "Life support: the next input row."],
		["life.less", "Decrease", [KEY_MINUS], "Life support: decrease the selected input."], ["life.more", "Increase", [KEY_EQUAL], "Life support: increase the selected input."],
		["life.reset", "Owner defaults", [KEY_BACKSPACE], "Life support: back to the owner's 41 defaults."],
		["life.day_prev", "Day back", [KEY_COMMA], "Life support: one day back (Shift: 30)."], ["life.day_next", "Day on", [KEY_PERIOD], "Life support: one day on (Shift: 30)."],
		["life.start", "Mission start", [KEY_HOME], "Life support: day 0."], ["life.end", "Mission end", [KEY_END], "Life support: the last mission day."],
		["life.play", "Play / pause", [KEY_P], "Life support: run the six years."]]],
	[["lab"], [["lab.tool", "Hold / let go of the tool", [KEY_T], "Physics lab: take or let go of the 2 kg tool."],
		["lab.zone_ship", "Ship zone", [KEY_1], "Physics lab: the weightless ship compartment."], ["lab.zone_ring_a", "Ring A zone", [KEY_2], "Physics lab: ring A spin gravity."],
		["lab.zone_ring_b", "Ring B zone", [KEY_3], "Physics lab: ring B spin gravity."], ["lab.mode", "Next ship mode", [KEY_M], "Physics lab: request the next ship operating mode."],
		["lab.skip", "Skip ahead", [KEY_K], "Physics lab: skip the mode transition ahead."], ["lab.profile", "Body profile", [KEY_P], "Physics lab: the next body profile."],
		["lab.tether", "Tethered body", [KEY_E], "Physics lab: the training tether case."], ["lab.clip", "Clip / unclip", [KEY_U], "Physics lab: clip or unclip the training tether."],
		["lab.occupants", "Occupant not secured", [KEY_O], "Physics lab: fault drill, an occupant not secured."],
		["lab.vestibule", "Vestibule step", [KEY_V], "Vestibule drill: the next of the seven handoff steps."]]],
	[["eva"], [["eva.drift", "Step out / back to hatch", [KEY_F], "EVA: out of the hatch into the drift, or back to the hatch anchor.", [{"t": "joyb", "b": JOY_BUTTON_DPAD_UP}]],
		["eva.grab", "Grab handhold", [KEY_H], "EVA: grip the handhold in reach (hand over hand on the rail).", [{"t": "joyb", "b": JOY_BUTTON_X}]],
		["eva.push", "Push off", [KEY_SPACE], "EVA: push off the anchor you hold, along your view.", [{"t": "joyb", "b": JOY_BUTTON_RIGHT_SHOULDER}]],
		["eva.aimed_push", "Aimed push (review aid)", [KEY_G], "EVA review aid: the profile push aimed at the step's target."],
		["eva.jet", "Thruster (experimental)", [KEY_J], "EVA: the experimental thruster, only where the scenario enables it (no pack in induction, S&E 46 DYN-017)."],
		["eva.clip", "Clip tether", [KEY_T], "EVA: clip the free tether to an anchor in reach.", [{"t": "joyb", "b": JOY_BUTTON_LEFT_SHOULDER}]],
		["eva.tug_test", "Tug-test tether", [KEY_Y], "EVA: tug-test the untested tether.", [{"t": "joyb", "b": JOY_BUTTON_Y}]],
		["eva.release_tether", "Release older tether", [KEY_R], "EVA: release the older tether (only with the other tested).", [{"t": "joyb", "b": JOY_BUTTON_DPAD_DOWN}]],
		["eva.what", "Station: what", [KEY_1], "EVA station: what is it."], ["eva.why", "Station: why", [KEY_2], "EVA station: why this design."],
		["eva.show", "Station: show me", [KEY_3], "EVA station: show me."], ["eva.next_station", "Next station", [KEY_N], "EVA: the next station."],
		["eva.keepout", "Keep-out zones", [KEY_K], "EVA: show or hide the keep-out zones."], ["eva.view", "First person / outside", [KEY_V], "EVA: switch the view."],
		["eva.abort", "Abort", [KEY_X], "EVA: start the abort back to the airlock."]]],
]

static func _expand(table: Array) -> Array:
	var out := []
	for group in table:
		for r in group[1]:
			out.append({"id": r[0], "name": r[1], "ctx": group[0], "keys": r[2], "what": r[3], "joy": r[4] if r.size() > 4 else [],
				"kind": r[5] if r.size() > 5 else "press", "layout": "logical"})
	return out

var ACTIONS: Array = BASE_ACTIONS + _expand(SCENE_ACTIONS)

# Lessons in the induction order of Tale 26 TOUR-02 then Tale 27 STG-001 / STG-012 (move with handrails, then grab, push, release).
# proof: the actions that must succeed (performed() by the scene) before the lesson counts as learned.
const LESSONS := [
	{"id": "move_rail", "title": "MOVE", "ctx": "walk", "actions": ["player.move_forward", "player.move_back"], "proof": ["player.move_forward"],
		"text": "Walk on along the induction route.", "try": "Hold %s to walk on (%s goes back).", "try_ids": ["player.move_forward", "player.move_back"],
		"steps": [[["player.move_forward"], "hold to walk on"], [["player.move_back"], "walk back"]]},
	{"id": "grab", "title": "GRAB / RELEASE", "ctx": "body", "actions": ["player.grab", "player.release", "player.push"], "proof": ["player.release", "player.grab"],
		"text": "You are weightless, holding a rail. Contact with the ship is the only way to change your motion.",
		"try": "Let go with %s, then grip again with %s. With a hand on the rail, %s pushes you off.",
		"try_ids": ["player.release", "player.grab", "player.push"],
		"steps": [[["player.release"], "let go of the rail"], [["player.grab"], "grip it again"], [["player.push"], "push off (hand on a rail)"]]},
	{"id": "move_deck", "title": "WALK THE DECK", "ctx": "body", "actions": ["player.move_left", "player.move_right"], "proof": ["player.move_forward"],
		"text": "Spin gravity holds you on the ring deck: here your feet can walk.", "try": "Walk with %s %s %s %s.", "try_ids": ["player.move_forward", "player.move_left", "player.move_back", "player.move_right"],
		"steps": [[["player.move_forward", "player.move_left", "player.move_back", "player.move_right"], "walk on the deck"]]},
	{"id": "inspect", "title": "INSPECT COMPONENT", "ctx": "nav", "actions": ["ship.card"], "proof": ["ship.card"],
		"text": "The ship navigator knows the module you are in. Its systems card explains it: what it is, why it is built so, and where.",
		"try": "Press %s to open the systems card, again for WHY THIS DESIGN and SHOW ME.", "try_ids": ["ship.card"],
		"steps": [[["ship.card"], "systems card: what, why, show me"]]},
	{"id": "tether", "title": "TWO TETHERS", "ctx": "eva", "actions": ["eva.clip", "eva.tug_test", "eva.release_tether"],
		"proof": ["eva.clip", "eva.tug_test", "eva.release_tether"],
		"text": "Outside, one tether is always clipped. Before you let the older one go, the new one must be clipped and tested (two-tether protocol).",
		"try": "At the rail: %s clips the free tether, %s tug-tests it, %s releases the older one.", "try_ids": ["eva.clip", "eva.tug_test", "eva.release_tether"],
		"steps": [[["eva.clip"], "clip the free tether"], [["eva.tug_test"], "tug-test it"], [["eva.release_tether"], "release the older one"]]},
]

# Raw keys still read directly by a scene of a context, which a binding may not take. Since ACI-10 every player-facing key is a
# registry action, so the table is empty; a scene that adds a raw key again lists it here until it becomes an action.
const RESERVED := {}

signal bindings_changed
signal lesson_learned(id: String)

var profile_path := PROFILE
var preference := "SUGGESTED"
var bindings := {}                   # action id -> Array of event dicts
var discovered := {}                 # action id -> true
var shown := {}                      # lesson id -> true (prompted once; never asked again in unrelated scenes)
var learned := {}                    # lesson id -> true
var first_launch_done := false
var device := "keyboard"             # last used: keyboard / joypad / touch
var context := "ui":                 # the scene's context; changing it drops latched toggles and the hazard flag
	set(v):
		if v != context:
			latched = {}
			hazard = false
		context = v
var hazard := false                  # a scene sets this during EVA hazards, cinematics or fast motion: no binding prompt then
# ACI-10 accessibility (saved in the profile): hold actions that latch on a press instead, the stick dead zone and sensitivity,
# and the size of every 2-D panel (the root content scale; the 3-D views are not scaled).
var toggles := {}                    # hold action id -> true: one press starts it, the next press stops it
var latched := {}                    # hold action id -> true while latched on
var stick_deadzone := DEADZONE
var stick_sensitivity := 1.0
var ui_scale := 1.0
const UI_SCALES := [1.0, 1.25, 1.5]
const DEADZONES := [0.2, 0.35, 0.5, 0.65]
const SENSITIVITIES := [0.75, 1.0, 1.5, 2.0]
var force_prompts := false           # headless checks only
var performed_now := {}              # lesson id -> {action: true}, this session
var had_profile := false
var overlay: CanvasLayer
# MOB-001 touch: the touch layer, its settings (saved in [touch]) and the semantic channels it feeds.
var touch: CanvasLayer
var touch_look := 1.0                # look speed factor (drag across the short screen side turns LOOK_RAD radians at 1.0)
var touch_stick := "floating"        # floating: the stick centres where the thumb lands; fixed: a fixed base in the lower left
var touch_controls := "auto"         # auto: shown while touch is the device in use; on: always; off: never
var touch_intro_done := false
const TOUCH_LOOKS := [0.5, 0.75, 1.0, 1.5, 2.0]
var virtual := {}                    # hold action id -> 0..1 from the touch stick (strength() takes the larger of it and the device's)
var look_acc := Vector2.ZERO         # touch look not yet taken, radians (x yaw, y pitch; the sign of a mouse drag)
var look_frame := -100               # the process frame a scene last took the look (a look owner exists while it keeps taking it)
var triggered: Array = []            # action ids sent by trigger() (headless checks)
var touch_provider := Callable()     # the scene's touch controls now: {} or {move, actions, utility, look} (wf_touch.gd)

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	load_profile()
	overlay = load("res://scripts/controls/control_overlay.gd").new()
	add_child(overlay)
	touch = load("res://scripts/controls/wf_touch.gd").new()
	add_child(touch)
	Input.joy_connection_changed.connect(_on_joy)

# ---- registry -----------------------------------------------------------------------------------------------------------------------

func action(id: String) -> Dictionary:
	for a in ACTIONS:
		if a.id == id:
			return a
	return {}

func lesson(id: String) -> Dictionary:
	for l in LESSONS:
		if l.id == id:
			return l
	return {}

func default_events(id: String) -> Array:
	var a := action(id)
	var out := []
	for k in a["keys"]:
		out.append({"t": "key", "k": k, "p": a.layout == "physical"})
	for j in a["joy"]:
		out.append(j.duplicate())
	return out

func defaults() -> Dictionary:
	var out := {}
	for a in ACTIONS:
		out[a.id] = default_events(a.id)
	return out

static func to_event(d: Dictionary) -> InputEvent:
	match str(d.t):
		"key":
			var e := InputEventKey.new()
			if d.get("p", false):
				e.physical_keycode = int(d.k)
			else:
				e.keycode = int(d.k)
			e.shift_pressed = d.get("shift", false)
			e.ctrl_pressed = d.get("ctrl", false)
			e.alt_pressed = d.get("alt", false)
			return e
		"joyb":
			var b := InputEventJoypadButton.new()
			b.button_index = int(d.b)
			return b
		"joya":
			var m := InputEventJoypadMotion.new()
			m.axis = int(d.a)
			m.axis_value = float(d.s)
			return m
		"mouse":
			var mb := InputEventMouseButton.new()
			mb.button_index = int(d.b)
			return mb
	return null

func apply() -> void:
	for a in ACTIONS:
		if not InputMap.has_action(a.id):
			InputMap.add_action(a.id, stick_deadzone)
		InputMap.action_set_deadzone(a.id, stick_deadzone)
		InputMap.action_erase_events(a.id)
		for d in bindings.get(a.id, []):
			var e := to_event(d)
			if e != null:
				InputMap.action_add_event(a.id, e)
	if is_inside_tree():
		get_tree().root.content_scale_factor = ui_scale * (touch.ui_density() if touch != null else 1.0)
	bindings_changed.emit()

## How strongly a hold action is held now (0..1): a latched toggle reads 1; a stick reads past the dead zone, scaled by the
## sensitivity. Gameplay uses this instead of Input.get_action_strength so the accessibility settings apply everywhere.
func strength(id: String) -> float:
	var v: float = virtual.get(id, 0.0)
	if toggles.has(id):
		return maxf(1.0 if latched.has(id) else 0.0, v)
	return maxf(clampf(Input.get_action_strength(id) * stick_sensitivity, 0.0, 1.0), v)

func held(id: String) -> bool:
	return strength(id) > 0.0

func set_toggle(id: String, on: bool) -> void:
	if on and action(id).get("kind", "") == "hold":
		toggles[id] = true
	else:
		toggles.erase(id)
	latched.erase(id)
	save_profile()
	bindings_changed.emit()

## Capture filter (ACI-06): a fresh press of a key, joypad button or extra mouse button, or a stick past CAPTURE_AXIS. Releases,
## repeats, mouse motion, left/right/middle clicks (pointer UI, look, pan) and stick drift return {}. Esc returns {"t": "cancel"}.
func capture_of(e: InputEvent, layout := "logical") -> Dictionary:
	if e is InputEventKey:
		if not e.pressed or e.echo:
			return {}
		var k: int = e.keycode if e.keycode != KEY_NONE else from_physical(e.physical_keycode)
		if k == KEY_ESCAPE or e.physical_keycode == KEY_ESCAPE:
			return {"t": "cancel"}
		if k in [KEY_SHIFT, KEY_CTRL, KEY_ALT, KEY_META]:
			return {}                                   # a modifier alone waits for its key
		var d := {"t": "key", "k": (e.physical_keycode if e.physical_keycode != KEY_NONE else k) if layout == "physical" else k, "p": layout == "physical"}
		if e.shift_pressed: d["shift"] = true
		if e.ctrl_pressed: d["ctrl"] = true
		if e.alt_pressed: d["alt"] = true
		return d
	if e is InputEventJoypadButton and e.pressed:
		return {"t": "joyb", "b": e.button_index}
	if e is InputEventJoypadMotion and absf(e.axis_value) >= CAPTURE_AXIS:
		return {"t": "joya", "a": e.axis, "s": 1 if e.axis_value > 0 else -1}
	if e is InputEventMouseButton and e.pressed and e.button_index in [MOUSE_BUTTON_XBUTTON1, MOUSE_BUTTON_XBUTTON2]:   # middle drag pans
		return {"t": "mouse", "b": e.button_index}
	return {}

## The logical key of a key binding (physical bindings resolved through the current layout), for labels and comparisons.
static func logical_key(d: Dictionary) -> int:
	return from_physical(int(d.k)) if d.get("p", false) else int(d.k)

## The current layout's key at a physical position (the headless display server has no layout and the Web one cannot map keys:
## the US position is returned).
static func from_physical(pk: int) -> int:
	if DisplayServer.get_name() == "headless" or OS.has_feature("web"):
		return pk
	var k := DisplayServer.keyboard_get_keycode_from_physical(pk)
	return k if k != KEY_NONE else pk

static func same_input(a: Dictionary, b: Dictionary) -> bool:
	if str(a.t) != str(b.t):
		return false
	match str(a.t):
		"key":
			return logical_key(a) == logical_key(b) and a.get("shift", false) == b.get("shift", false) and a.get("ctrl", false) == b.get("ctrl", false) \
				and a.get("alt", false) == b.get("alt", false)
		"joyb", "mouse":
			return int(a.get("b", -1)) == int(b.get("b", -1))
		"joya":
			return int(a.a) == int(b.a) and int(a.s) == int(b.s)
	return false

## d is one of id's own defaults (an unchanged default never pushes a new action's default out).
func same_input_default(id: String, d: Dictionary) -> bool:
	return default_events(id).any(func(x): return same_input(x, d))

static func co_active(a: Array, b: Array) -> bool:
	for x in a:
		for y in b:
			if x == y or x == "ui" or y == "ui" or y in LINKED.get(x, []):
				return true
	return false

## ACI-06: what taking input d for action id would collide with. {kind: "none" | "reserved" | "conflict" | "reuse", ...}.
## reuse = the same input on an action in a context that is never active together (harmless, allowed).
## An action's own default key is never refused as reserved: the shipped layout was audited per scene (the demonstrator's guide uses
## Tab for details because the navigator owns I), and the context table is coarser than that audit.
func conflict_of(id: String, d: Dictionary) -> Dictionary:
	var a := action(id)
	var own_default := str(d.t) == "key" and default_events(id).any(func(x): return str(x.t) == "key" and same_input(x, d))
	if str(d.t) == "key" and not own_default and not d.get("shift", false) and not d.get("ctrl", false) and not d.get("alt", false):
		var k := logical_key(d)
		for c in RESERVED:
			if co_active(a.ctx, [c]) and RESERVED[c].has(k) and not (a.has("locked") and a.locked == k):
				return {"kind": "reserved", "context": c, "what": RESERVED[c][k]}
	var reuse := ""
	var others := []
	for o in ACTIONS:
		if o.id == id:
			continue
		for od in bindings.get(o.id, []):
			if same_input(od, d):
				if co_active(a.ctx, o.ctx):
					if not o.id in others:
						others.append(o.id)
				else:
					reuse = o.id
	if not others.is_empty():
		return {"kind": "conflict", "other": others[0], "others": others}
	return {"kind": "reuse", "other": reuse} if reuse != "" else {"kind": "none"}

func _kind(d: Dictionary) -> String:
	return "joypad" if str(d.t).begins_with("joy") else "keyboard"

## Set the binding of id for d's device family (keyboard+mouse or joypad); the other family is kept. resolution: "" (no conflict
## expected), "swap" (the other action takes id's old input of the same family), "replace" (the other action loses d). Returns
## {ok, why}. Never leaves a required action without an input, never takes a reserved key.
func assign(id: String, d: Dictionary, resolution := "") -> Dictionary:
	var c := conflict_of(id, d)
	if c.kind == "reserved":
		return {"ok": false, "why": "%s is still used for %s (%s) and cannot be reassigned yet" % [describe(d), c.what, CONTEXTS[c.context]]}
	var fam := _kind(d)
	var old: Array = bindings.get(id, []).filter(func(x): return _kind(x) == fam)
	var lock = action(id).get("locked", null)
	if c.kind == "conflict":
		if resolution == "":
			return {"ok": false, "why": "conflict", "other": c.other, "others": c.others}
		if resolution == "swap" and c.others.size() > 1:
			return {"ok": false, "why": "%s is used by %d actions here; swap works with one, replace clears it from all" % [describe(d), c.others.size()]}
		var changed := {}
		for other in c.others:
			var theirs: Array = bindings[other].filter(func(x): return not same_input(x, d))
			if resolution == "swap":
				for x in old:
					if not (lock != null and str(x.t) == "key" and int(x.k) == lock):
						theirs.append(x)
			if action(other).get("required", false) and not has_keyboard(theirs):
				return {"ok": false, "why": "%s would be left with no keyboard input; choose swap or another input" % action(other).name}
			changed[other] = theirs
		for other in changed:
			bindings[other] = changed[other]
	var keep: Array = bindings.get(id, []).filter(func(x): return _kind(x) != fam or (lock != null and str(x.t) == "key" and int(x.k) == lock))
	keep.insert(0, d)
	bindings[id] = keep
	apply()
	save_profile()
	return {"ok": true, "why": ""}

## A required action keeps at least one keyboard or mouse input: the keyboard is the device assumed always present.
static func has_keyboard(evs: Array) -> bool:
	return evs.any(func(x): return str(x.t) in ["key", "mouse"])

func restore(id: String) -> Dictionary:
	# Restoring one action may collide with a rebind elsewhere: then the other keeps it and this action keeps its own (reported).
	var out := {"ok": true, "why": ""}
	var mine := []
	for d in default_events(id):
		var c := conflict_of(id, d)
		if c.kind == "conflict":
			out = {"ok": false, "why": "%s is now on %s; restore that one or rebind" % [describe(d), action(c.other).name]}
		else:
			mine.append(d)
	if not mine.is_empty() or not action(id).get("required", false):
		bindings[id] = mine
	apply()
	save_profile()
	return out

func restore_all() -> void:
	bindings = defaults()
	apply()
	save_profile()

# ---- labels and prompts (ACI-07) ----------------------------------------------------------------------------------------------------

const JOY_NAMES := {JOY_BUTTON_A: "A button", JOY_BUTTON_B: "B button", JOY_BUTTON_X: "X button", JOY_BUTTON_Y: "Y button",
	JOY_BUTTON_BACK: "Back/View", JOY_BUTTON_START: "Start/Menu", JOY_BUTTON_LEFT_SHOULDER: "LB", JOY_BUTTON_RIGHT_SHOULDER: "RB",
	JOY_BUTTON_LEFT_STICK: "L3", JOY_BUTTON_RIGHT_STICK: "R3", JOY_BUTTON_DPAD_UP: "D-pad up", JOY_BUTTON_DPAD_DOWN: "D-pad down",
	JOY_BUTTON_DPAD_LEFT: "D-pad left", JOY_BUTTON_DPAD_RIGHT: "D-pad right"}
const AXIS_NAMES := {JOY_AXIS_LEFT_X: ["left stick left", "left stick right"], JOY_AXIS_LEFT_Y: ["left stick up", "left stick down"],
	JOY_AXIS_RIGHT_X: ["right stick left", "right stick right"], JOY_AXIS_RIGHT_Y: ["right stick up", "right stick down"],
	JOY_AXIS_TRIGGER_LEFT: ["LT", "LT"], JOY_AXIS_TRIGGER_RIGHT: ["RT", "RT"]}

# ACI-09: printed glyphs for punctuation and arrows (OS names read "BracketRight", "Period" in a HUD line).
const KEY_GLYPHS := {KEY_PERIOD: ".", KEY_COMMA: ",", KEY_MINUS: "-", KEY_EQUAL: "=", KEY_BRACKETLEFT: "[", KEY_BRACKETRIGHT: "]",
	KEY_SEMICOLON: ";", KEY_APOSTROPHE: "'", KEY_SLASH: "/", KEY_BACKSLASH: "\\", KEY_QUOTELEFT: "`",
	KEY_UP: "↑", KEY_DOWN: "↓", KEY_LEFT: "←", KEY_RIGHT: "→", KEY_ESCAPE: "Esc"}

# MOB-001: what the on-screen control of an action is called, for prompts while the player uses touch (the keyboard label otherwise).
const TOUCH_LABELS := {"ui.confirm": "Next", "ui.codex": "Help", "player.move_forward": "stick up", "player.move_back": "stick down",
	"player.move_left": "stick left", "player.move_right": "stick right", "player.grab": "Grab", "player.release": "Release",
	"player.push": "Push off", "ship.map": "Map", "ship.card": "Systems", "demo.pause": "Pause", "demo.autoplay": "Auto",
	"demo.occupants": "Occupant", "body.view": "View", "body.drop_tool": "Drop"}

static func describe(d: Dictionary) -> String:
	match str(d.t):
		"key":
			var mods := ("Ctrl+" if d.get("ctrl", false) else "") + ("Alt+" if d.get("alt", false) else "") + ("Shift+" if d.get("shift", false) else "")
			var k := logical_key(d)
			return mods + (KEY_GLYPHS[k] if KEY_GLYPHS.has(k) else OS.get_keycode_string(k))
		"joyb":
			return JOY_NAMES.get(int(d.b), "button %d" % int(d.b))
		"joya":
			var n: Array = AXIS_NAMES.get(int(d.a), ["axis %d -" % int(d.a), "axis %d +" % int(d.a)])
			return n[0] if int(d.s) < 0 else n[1]
		"mouse":
			return {MOUSE_BUTTON_MIDDLE: "Middle click", MOUSE_BUTTON_XBUTTON1: "Mouse back", MOUSE_BUTTON_XBUTTON2: "Mouse forward"}.get(int(d.b), "mouse %d" % int(d.b))
	return "?"

## The input that triggers id now, for the device in use (keyboard or joypad); falls back to the other family; "unassigned".
func label(id: String, all := false) -> String:
	if device == "touch" and TOUCH_LABELS.has(id):
		return TOUCH_LABELS[id]
	var mine: Array = bindings.get(id, [])
	var fam: Array = mine.filter(func(x): return _kind(x) == ("keyboard" if device == "touch" else device))
	if fam.is_empty():
		fam = mine
	if fam.is_empty():
		return "unassigned"
	return " / ".join(fam.map(func(x): return describe(x))) if all else describe(fam[0])

## Every input of id, keyboard and controller (the Codex).
func label_all(id: String) -> String:
	var mine: Array = bindings.get(id, [])
	return " · ".join(mine.map(func(x): return describe(x))) if not mine.is_empty() else "unassigned"

## Help text with the player's inputs: every {action.id} becomes that action's label ("{flight.play}: play" -> "Space: play").
func keys(text: String) -> String:
	var out := ""
	var i := 0
	while true:
		var a := text.find("{", i)
		var b := text.find("}", a + 1) if a >= 0 else -1
		if a < 0 or b < 0:
			return out + text.substr(i)
		var id := text.substr(a + 1, b - a - 1)
		out += text.substr(i, a - i) + (label(id) if not action(id).is_empty() else "{" + id + "}")
		i = b + 1
	return out

func labels(ids: Array) -> Array:
	return ids.map(func(i): return label(i))

## The contexts read in the current scene: ui, the scene's context and the contexts linked to it.
func active_contexts() -> Array:
	return ["ui", context] + LINKED.get(context, [])

## The default key of the registry action e triggers among the actions of ctxs (ui always included), so a scene's handler matches
## the action, not the physical input: KEY_NONE for an input that triggers none of them (including a default key rebound away).
func key_of(e: InputEvent, ctxs: Array) -> int:
	var cs := ["ui"] + ctxs
	for a in ACTIONS:
		if not a["keys"].is_empty() and a.ctx.any(func(c): return c in cs) and e.is_action(a.id, false):
			return a["keys"][0]
	return KEY_NONE

## A press (not a release; repeats only when allowed) of a key, controller button, bindable mouse button or a trigger() action.
static func pressed(e: InputEvent, repeat := false) -> bool:
	var device: bool = e is InputEventKey or e is InputEventJoypadButton or e is InputEventAction \
		or (e is InputEventMouseButton and e.button_index in [MOUSE_BUTTON_XBUTTON1, MOUSE_BUTTON_XBUTTON2])
	return device and e.is_pressed() and (repeat or not e.is_echo())

## Shift as a step multiplier (×24 frames, ×30 days, ×30 rows): a modifier, not an action.
static func shifted(e: InputEvent) -> bool:
	return e is InputEventWithModifiers and e.shift_pressed

## For the review guide: the default key of the action e triggers in the current scene's contexts; KEY_NONE if none.
func canonical_key(e: InputEvent) -> int:
	return key_of(e, active_contexts())

func available(id: String) -> bool:
	var cs := active_contexts()
	return action(id).ctx.any(func(c): return c in cs)

func _input(e: InputEvent) -> void:
	if e.device == InputEvent.DEVICE_ID_EMULATION:
		pass                                    # a mouse event Godot made from a touch: still the touch device
	elif e is InputEventScreenTouch or e is InputEventScreenDrag:
		set_device("touch")
	elif e is InputEventJoypadButton or (e is InputEventJoypadMotion and absf(e.axis_value) > DEADZONE):
		set_device("joypad")
	elif (e is InputEventKey and e.pressed) or e is InputEventMouseButton:
		set_device("keyboard")
	if modal():
		latched = {}
		release_touch()
		return
	for id in toggles:                       # a latched hold flips on each fresh press of its input
		if e.is_action_pressed(id) and not e.is_echo():
			if latched.has(id):
				latched.erase(id)
			else:
				latched[id] = true
	if e.is_action_pressed("ui.codex") and not e.is_echo():
		overlay.open_codex()
		get_viewport().set_input_as_handled()

func set_device(d: String) -> void:
	if device != d:
		device = d
		bindings_changed.emit()

## A modal control panel is open (first launch, capture, Codex, the touch welcome or help): the scene tree is paused meanwhile.
func modal() -> bool:
	return overlay.is_modal() or (touch != null and touch.is_modal())

# ---- touch channels (MOB-001) -------------------------------------------------------------------------------------------------------

## The touch stick holds a hold action at strength v (0 releases it). Only hold actions; a press needs trigger().
func set_virtual(id: String, v: float) -> void:
	if v > 0.0 and action(id).get("kind", "") == "hold" and not modal():
		virtual[id] = clampf(v, 0.0, 1.0)
	else:
		virtual.erase(id)

## Releases everything touch holds: the stick, the look not yet taken (finger up, cancel, modal, focus loss, resize, scene change).
func release_touch() -> void:
	virtual = {}
	look_acc = Vector2.ZERO
	if touch != null:
		touch.release_all()

## A touch button's press of a press action: the same InputEventAction a key bound to it is matched as, so it reaches the same
## handler with the same checks (a refused grab stays refused). The press and its release go through Input like device events.
func trigger(id: String) -> bool:
	var a := action(id)
	if a.is_empty() or a.get("kind", "press") != "press" or modal():
		return false
	for down in [true, false]:
		var e := InputEventAction.new()
		e.action = id
		e.pressed = down
		e.strength = 1.0 if down else 0.0
		Input.parse_input_event(e)
	triggered.append(id)
	return true

func add_look(rad: Vector2) -> void:
	if not modal():
		look_acc += rad

## The look owner (the body or the rail camera) takes the touch look once per frame; while a scene keeps taking it, the touch layer
## offers look dragging (a guided camera that takes none gets none).
func take_look() -> Vector2:
	look_frame = Engine.get_process_frames()
	var out := look_acc
	look_acc = Vector2.ZERO
	return out

func look_wanted() -> bool:
	return Engine.get_process_frames() - look_frame <= 3

## MOB-001: the compact (phone and tablet) layout: decided once from the device, never from the window size alone, so a desktop window
## keeps the desktop layout.
func compact() -> bool:
	return touch != null and touch.primary

func _notification(what: int) -> void:
	if what in [NOTIFICATION_APPLICATION_FOCUS_OUT, NOTIFICATION_WM_WINDOW_FOCUS_OUT, NOTIFICATION_APPLICATION_PAUSED]:
		release_touch()                     # never a stuck stick after the page loses focus or goes to the background

func _on_joy(_id: int, connected: bool) -> void:
	if not connected and device == "joypad":
		device = "keyboard"                 # the keyboard and mouse keep working; nothing is lost with the controller
		bindings_changed.emit()
	overlay.toast("Controller %s. %s" % ["connected" if connected else "disconnected", "Keyboard and mouse still work." if not connected else "Prompts follow the device you use."])

# ---- discovery and lessons (ACI-04/05) ----------------------------------------------------------------------------------------------

func prompts_enabled() -> bool:
	if force_prompts:
		return true
	if DisplayServer.get_name() == "headless":
		return false
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--check") or a.begins_with("--capture") or a == "--autoplay" or a == "--demo":
			return false
	return true

## A scene calls this when a lesson's actions become relevant and the moment is safe (it may call it every frame). Returns true if
## a prompt opened. Never during a hazard, never twice for the same lesson, never in checks or autoplay (S&E 59 POL-005).
func discover(id: String) -> bool:
	if shown.has(id) or learned.has(id) or hazard or not prompts_enabled() or overlay.is_modal():
		return false
	var l := lesson(id)
	shown[id] = true
	for a in l.actions:
		discovered[a] = true
	save_profile()
	match preference:
		"EXPERIENCED":
			return false
		"PERSONAL":
			overlay.open_discovery(l)
		_:
			overlay.show_lesson(l)
	return true

## A scene reports that an action succeeded (moved, gripped, released ...). Completes any shown lesson whose proof is met.
func performed(action_id: String) -> void:
	for l in LESSONS:
		if not shown.has(l.id) or learned.has(l.id) or not action_id in l.proof:
			continue
		var p: Dictionary = performed_now.get(l.id, {})
		p[action_id] = true
		performed_now[l.id] = p
		if l.proof.all(func(x): return p.has(x)):
			learned[l.id] = true
			save_profile()
			overlay.lesson_done(l)
			lesson_learned.emit(l.id)

func lesson_try(l: Dictionary) -> String:
	return str(l["try"]) % labels(l.try_ids)

func replay_lessons() -> void:
	shown = {}
	learned = {}
	performed_now = {}
	save_profile()

# ---- profile (ACI-06 persistence) ---------------------------------------------------------------------------------------------------

func has_profile() -> bool:
	return had_profile and first_launch_done

func load_profile() -> void:
	bindings = defaults()
	var cf := ConfigFile.new()
	had_profile = cf.load(profile_path) == OK
	if not had_profile:
		preference = "SUGGESTED"
		discovered = {}
		shown = {}
		learned = {}
		first_launch_done = false
		toggles = {}
		stick_deadzone = DEADZONE
		stick_sensitivity = 1.0
		ui_scale = 1.0
		touch_look = 1.0
		touch_stick = "floating"
		touch_controls = "auto"
		touch_intro_done = false
		apply()
		return
	migrate(cf)
	apply()

## Old or partial profiles keep working: unknown actions are dropped, new actions get their defaults (and stay undiscovered, so the
## player's preference decides whether they are introduced), a required action left without input gets its defaults back.
func migrate(cf: ConfigFile) -> void:
	var schema := int(cf.get_value("meta", "schema", 0))
	preference = str(cf.get_value("meta", "preference", "SUGGESTED"))
	if not preference in PREFS:
		preference = "SUGGESTED"
	first_launch_done = bool(cf.get_value("meta", "first_launch_done", schema >= 1))
	for a in ACTIONS:
		if cf.has_section_key("bindings", a.id):
			var evs: Array = cf.get_value("bindings", a.id, []).filter(func(x): return x is Dictionary and x.has("t") and to_event(x) != null)
			if a.get("required", false) and not has_keyboard(evs):
				evs += default_events(a.id).filter(func(x): return _kind(x) == "keyboard")
			bindings[a.id] = evs
		if a.has("locked") and not bindings[a.id].any(func(x): return str(x.t) == "key" and logical_key(x) == a.locked):
			bindings[a.id].append({"t": "key", "k": a.locked, "p": false})
	# An action new since the profile was saved takes its defaults, except an input the player already gave to another action that
	# can be active with it: the player's choice wins and the new action starts without that input (the Codex shows it).
	var saved: Array = Array(cf.get_section_keys("bindings")) if cf.has_section("bindings") else []
	for a in ACTIONS:
		if a.id in saved:
			continue
		bindings[a.id] = bindings[a.id].filter(func(d): return not saved.any(func(o): return action(o).has("ctx") and co_active(a.ctx, action(o).ctx) \
			and bindings.get(o, []).any(func(x): return same_input(x, d)) and not same_input_default(o, d)))
	discovered = _set_of(cf.get_value("progress", "discovered", []))
	shown = _set_of(cf.get_value("progress", "shown", []))
	learned = _set_of(cf.get_value("progress", "learned", []))
	toggles = {}
	for id in cf.get_value("access", "toggles", []):
		if action(str(id)).get("kind", "") == "hold":
			toggles[str(id)] = true
	stick_deadzone = clampf(float(cf.get_value("access", "stick_deadzone", DEADZONE)), 0.05, 0.9)
	stick_sensitivity = clampf(float(cf.get_value("access", "stick_sensitivity", 1.0)), 0.25, 4.0)
	ui_scale = clampf(float(cf.get_value("access", "ui_scale", 1.0)), 0.75, 2.0)
	# schema 3 (MOB-001): touch settings; an older profile keeps everything above and starts with the touch defaults.
	touch_look = clampf(float(cf.get_value("touch", "look", 1.0)), 0.25, 4.0)
	touch_stick = str(cf.get_value("touch", "stick", "floating"))
	if not touch_stick in ["floating", "fixed"]:
		touch_stick = "floating"
	touch_controls = str(cf.get_value("touch", "controls", "auto"))
	if not touch_controls in ["auto", "on", "off"]:
		touch_controls = "auto"
	touch_intro_done = bool(cf.get_value("touch", "intro_done", false))

static func _set_of(a) -> Dictionary:
	var out := {}
	if a is Array:
		for x in a:
			out[str(x)] = true
	return out

func save_profile() -> void:
	var cf := ConfigFile.new()
	cf.set_value("meta", "schema", SCHEMA)
	cf.set_value("meta", "preference", preference)
	cf.set_value("meta", "first_launch_done", first_launch_done)
	cf.set_value("meta", "device", device)
	for a in ACTIONS:
		cf.set_value("bindings", a.id, bindings.get(a.id, []))
	cf.set_value("progress", "discovered", discovered.keys())
	cf.set_value("progress", "shown", shown.keys())
	cf.set_value("progress", "learned", learned.keys())
	cf.set_value("access", "toggles", toggles.keys())
	cf.set_value("access", "stick_deadzone", stick_deadzone)
	cf.set_value("access", "stick_sensitivity", stick_sensitivity)
	cf.set_value("access", "ui_scale", ui_scale)
	cf.set_value("touch", "look", touch_look)
	cf.set_value("touch", "stick", touch_stick)
	cf.set_value("touch", "controls", touch_controls)
	cf.set_value("touch", "intro_done", touch_intro_done)
	cf.save(profile_path)
	had_profile = true

func set_preference(p: String) -> void:
	if p in PREFS:
		preference = p
		save_profile()
