# Hole on a pin's top face: 'through all' removes nothing, a 24 mm deep one leaves 2 solids

- **Kind:** bug
- **Date:** 2026-10-30 00:32:03
- **App version:** 0.9.0 (main @ 92d0e37, 2026-10-29)
- **Reported by:** the AI agent (MCP report_problem)

## What happened

Základna (plate 120×120×8 + Ø12 pin 16 high, F4). GUI: ◎ Díra, clicked the pin top F4:end (snapped to centre), Ø4, Skrz vše, OK -> step F5 ok, no warning, volume_change 0 (volume 117009.557 unchanged, faces 8). edit_feature points [[0,0]] -> still 0. edit_feature through false, depth 24 -> -891 mm³ (Ø4×24 should be ~302 mm³) and body says solids: 2. Section view along y=60 shows a strange conical hole.

## What was expected

A Ø4 through hole along the pin axis through pin and plate (-302 mm³), one solid; a hole that removes nothing should warn.

## Steps

open_part Základna; gui_action ◎ Díra; pick F4:end; d=4; OK; get_model; edit_feature F5 {points:[[0,0]]}; edit_feature F5 {through:false, depth:24}

## Workaround

Deleted the hole; sketch circle Ø4 on the base's bottom face + extrude cut.
