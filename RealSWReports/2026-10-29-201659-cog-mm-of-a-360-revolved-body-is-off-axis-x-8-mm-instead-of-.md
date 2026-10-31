# cog_mm of a 360° revolved body is off-axis (x ≈ 8 mm instead of 0)

- **Kind:** bug
- **Date:** 2026-10-29 20:16:59
- **App version:** 0.9.0 (main @ 92d0e37, 2026-10-29)
- **Reported by:** the AI agent (MCP report_problem)

## What happened

A profile on XZ revolved 360° about y (an apple-shaped bottle, Ø75, then shelled 2 mm) reports cog_mm [7.5…8.8, 0, 60]. A full revolve is axially symmetric, so x must be 0. Also z≈60 of 72 looks too high for a mostly round body.

## What was expected

cog_mm [0, 0, ~33] for the solid revolve.

## Steps

new_model; sketch XZ profile [[0,0],[16,0],{smooth:[...]},[7.5,58],...,[0,72]]; revolve axis y 360 -> cog [8.789,0,59.077]; shell top face t 2 -> cog [7.74,0,60.1].
