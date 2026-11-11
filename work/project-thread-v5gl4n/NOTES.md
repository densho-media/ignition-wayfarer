# MOB-002 touch controls for Explore Exterior (claude/project-thread-v5gl4n)

Function: Explore Exterior (EVA Operations) playable by touch on a phone, with a compact readable HUD; desktop keyboard and
controller unchanged. Fixed: the registry actions and EVA physics (touch sends the same actions as keys), the MOB-001 touch layer
and device detection. Design freedom: layout, labels, which buttons show when. Decisions: docs/wayfarer-mobile-controls-plan.md §11b.

`touch_shots.gd`: native phone-size stills with synthetic touches (study only; delete on squash):
  xvfb-run godot-4 --path godot --resolution 844x390 --rendering-driver opengl3 --script $PWD/work/project-thread-v5gl4n/touch_shots.gd -- --touch --shots-out=<dir>
Without godot/generated (no runtime-export in this session) the stills show the EVA proxy world and CHARACTER MISSING labels.
