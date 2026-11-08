# CTRL-001 — player-chosen controls (branch claude/project-thread-yulo0d)

Function: both playable experiences ask the player for their own movement keys on a first visit, keep them per browser profile,
share the moves between Interior and Exterior, and change any key from the Controls menu. No physics, rig or canon change.

Fixed constraints: the existing WfInput registry, InputMap, profile file and overlay are kept and extended (no second input system,
no JavaScript profile store). Bindings never change forces, propellant, collisions or permissions.

Decisions: essential actions per experience (`setup`), shared EVA moves (`share`), profile schema 4 with `[setup] confirmed`,
movement on physical key positions with the pressed character as label, retired scene contexts never block a playable key.

Review stills: `review_stills.gd` draws the setup and Controls panels over a plain background (copy it to `godot/` and run
`xvfb-run godot-4 --path godot --rendering-driver opengl3 --script res://review_stills.gd`); the stills are in the project files
under `controls/`. The browser check's own screenshots are in the CI artifact.
