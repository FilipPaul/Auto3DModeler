# 🪄 Automatické kóty silently do nothing on a hand-drawn sketch (lines + tangent arcs)

- **Kind:** bug
- **Date:** 2026-10-28 21:48:33
- **App version:** 0.9.0 (main @ fe12e22, 2026-10-28)
- **Reported by:** the AI agent (MCP report_problem)

## What happened

Sketch F1 in '3D model 4': 5 lines + 2 arcs (in fact a 65×65 rectangle unioned with a slot: two equal arcs r 23.2155 at (45, 8.94) and (15, 35) joined by a tangent line), 4 locked sizes, 6 free sizes (🔓 Volné in the panel). Clicking 🪄 Automatické kóty: no change (locked_sizes stays 4), no toast, no message. The user reported getting errors when using it. The odd values (r 23.2155, y 8.94) show the solver made them from tangent / equal constraints.

## What was expected

Auto-dims locks every free size (radius, arc centres, tangent line), or when it can't, it shows a toast saying which shape / constraint stopped it (e.g. 'the arc centre is set twice: by tangent + equal + a dimension').

## Steps

get_model (F1: line 5, arc 2, locked 4) → gui_action double-click 'Skica 1' → gui_action '🪄 Automatické kóty' → toasts [], get_model locked_sizes still 4.

## Workaround

I replaced the sketch through edit_feature with rect {-20,-30,65,65} + slot {(45,9)-(15,35), w 46}. On that sketch, auto-dims worked (14 locked).
