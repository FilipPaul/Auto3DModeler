# Joint panel: free-turn slider greyed out on locked joints, and dragging it locks the turn

- **Date:** 2026-10-27 12:31:22
- **App version:** 0.9.0 (main @ 4d79ca0, 2026-10-27)
- **Reported by:** the AI agent (MCP report_problem)

## What happened

Assembly: Stojan s čepem (I1) → Bearing 608-2Z (I2, J1 axis + J2 gap, rotation free) → Otočné rameno (I3, J3 axis + J4 gap, rotation locked to the bearing). move_free works fine on I2 and on I3, and each one carries the other along. But in the GUI: (1) With J1 locked 🔒, the slider '◎ Concentric J1 › ↻ °🔓 free' is disabled ('unlock the joint to change it'), so the user can't drive the free motion without unlocking the joint. (2) After unlocking J1, dragging that slider to 60 turned the parts but ALSO set J1 rotation_locked = true, so I2 and I3 became fully_held and the mechanism no longer moves. (3) gui_state lists no control for picking a part (e.g. clicking Otočné rameno) that would show a slider for its free motion. Also J2's free-turn slider shows +30 while the bearing is at -30 (sign flipped against J1 / get_assembly 'at').

## What was expected

A free motion (🔓 free) should stay draggable even when the joint is locked (the lock should only stop the joint from being edited or broken), and dragging it should move the part along the free motion (like move_free) without locking the rotation. Clicking a part should give a slider for its free motion (I3: 'turn — with Bearing'). The angle sign should match across joints.

## Steps

edit_joint J2 lock_rotation false, locked true; move_free I3 to 45 (ok, I2 follows); move_free I2 to -30 (ok, I3 follows); gui_action on the J1 ↻ slider → disabled; edit_joint J1 locked false; gui_action J1 ↻ slider = 60 → get_assembly shows J1 rotation_locked true, both parts fully_held.

## Workaround

edit_joint J1 lock_rotation false, then locked true again. The user drives it with move_free (through the AI) for now.

## Resolved

2026-10-27 (after 0.9.0 @ 4d79ca0): the ↻ slider of a joint whose turn is free now turns the part about the joint and
leaves the turn free (it no longer locks it); on a locked 🔒 joint that slider stays usable (driving is not changing
the joint) — the rest of the row stays greyed. gui_state lists the parts of the list (kind "part"), so gui_action
can choose one and its Moves (e.g. "turn — with Bearing") show. Not changed: the sign of a flat joint's ↻ is seen
along its face's normal, a concentric one's along its axis — two joints of one part can show opposite signs.
tools/e2e_assembly_lever.py.
