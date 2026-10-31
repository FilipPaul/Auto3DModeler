# Fillet with "Celý řetěz" on a disc's top outer edge also rounds the hole's top edge

- **Kind:** bug
- **Date:** 2026-10-29 21:31:21
- **App version:** 0.9.0 (main @ 92d0e37, 2026-10-29)
- **Reported by:** the AI agent (MCP report_problem)

## What happened

3D model 8: a Ø70×10 disc with a Ø9.5 through hole. Zaoblení, one click on the top outer circular edge, ⛓ Celý řetěz on (the default), R2, OK -> Zaoblení 1 says "R 2 · 2 edge(s)": the hole's top edge is rounded too. The two circles are not connected or tangent, so they are not one chain. The preview showed it, but it is easy to miss.

## What was expected

A chain only follows edges joined end to end and tangent; a click on the outer edge rounds just that edge (1 edge).

## Steps

Sketch circle Ø70 on Top, extrude 10, hole Ø9.5 at (6, 13) through, Zaoblení -> click the top outer edge at the front -> r 2 -> OK.
