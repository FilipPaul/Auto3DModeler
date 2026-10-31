# Auto-dims should trim overlaps and add its own construction geometry; an MCP trim / union tool for sketches

- **Kind:** tool request
- **Date:** 2026-10-28 21:58:38
- **App version:** 0.9.0 (main @ fe12e22, 2026-10-28)
- **Reported by:** the AI agent (MCP report_problem)

## What happened

The user (via the AI) says a final sketch should be one outline with the inner lines trimmed (✂ Oříznout). Auto-dims should be able to finish dimensioning by adding its own construction lines: arc centres, the line between centres, an axis of symmetry, and tangent lines. Through MCP there is no trim tool, so the only way to get one outline from overlapping shapes is to rewrite the sketch as a profile with tangent points worked out by hand. That loses the tangent and equal constraints and froze the app.

## What was expected

1) sketch_trim {sketch, shape, at} and sketch_union {sketch} (merge overlapping closed shapes into one outline as lines and arcs, keeping tangent / equal constraints). 2) Auto-dims adds construction geometry when a size cannot be dimensioned directly (an arc's centre via a construction line to an edge or the origin, a slot's centre line with its length and angle), and prefers dims from the origin and edges. 3) It can also add constraints it detects (tangent, equal radius, horizontal / vertical), not only dims.

## Workaround

I wrote the outline as a profile with hand-computed tangent points.
