---
name: fits-and-tolerances
description: Use when a part must fit something exactly — a bearing seat, a shaft, a dowel pin, a sliding fit, a press fit — or for general tolerances, clearance and tap-drill holes, counterbores and threads of machined (and printed) parts. ISO 286 fits, ISO 2768, ISO 273.
---

# Fits and tolerances

The model is drawn at the **nominal size** (a Ø8 H7 hole is modelled Ø8). Name the step after its fit
("Hole Ø8 H7 — dowel pin") so the fit is not lost, and tell the user the fits in your summary. For **printed**
holes use the print allowances at the end instead (ISO fits cannot be printed).

## ISO 286 — the usual fits

| Fit | Use |
|---|---|
| H7/g6 | sliding / turning with little play (a pin in a guide, a gear on a shaft that slides) |
| H7/h6 | locating, can be pushed together by hand (a centring boss) |
| H7/k6 | transition: located, light tap with a mallet (a ball bearing's inner ring on a turning shaft) |
| H7/m6 | transition, tighter (a dowel pin in one part, gears that must not slip) |
| H7/p6 | press fit (a bushing pressed in) |
| H8/f7 | running with clear play (plain bearings, levers on pins) |

Deviations in µm (1 µm = 0.001 mm), by nominal Ø in mm:

| Ø (mm) | H7 | H8 | g6 | h6 | k6 | m6 | p6 |
|---|---|---|---|---|---|---|---|
| over 3 to 6 | +12 / 0 | +18 / 0 | −4 / −12 | 0 / −8 | +9 / +1 | +12 / +4 | +20 / +12 |
| over 6 to 10 | +15 / 0 | +22 / 0 | −5 / −14 | 0 / −9 | +10 / +1 | +15 / +6 | +24 / +15 |
| over 10 to 18 | +18 / 0 | +27 / 0 | −6 / −17 | 0 / −11 | +12 / +1 | +18 / +7 | +29 / +18 |
| over 18 to 30 | +21 / 0 | +33 / 0 | −7 / −20 | 0 / −13 | +15 / +2 | +21 / +8 | +35 / +22 |
| over 30 to 50 | +25 / 0 | +39 / 0 | −9 / −25 | 0 / −16 | +18 / +2 | +25 / +9 | +42 / +26 |

Ball bearings (e.g. 608-2Z, Ø22 × Ø8): housing **H7** (outer ring still), shaft **k6** (turning inner ring) or
**h6/g6** when the inner ring must slide on. Dowel pins (ISO 8734 m6): the hole **H7**.

## ISO 2768 — general tolerances (sizes without their own tolerance)

Write "ISO 2768-m" on machined parts unless told: linear sizes in mm, ±:

| Size (mm) | 0.5–3 | over 3–6 | over 6–30 | over 30–120 | over 120–400 | over 400–1000 |
|---|---|---|---|---|---|---|
| f (fine) | 0.05 | 0.05 | 0.1 | 0.15 | 0.2 | 0.3 |
| m (medium) | 0.1 | 0.1 | 0.2 | 0.3 | 0.5 | 0.8 |
| c (coarse) | 0.2 | 0.3 | 0.5 | 0.8 | 1.2 | 2 |

## Holes for screws and threads (metric)

| Thread | M2 | M2.5 | M3 | M4 | M5 | M6 | M8 | M10 | M12 |
|---|---|---|---|---|---|---|---|---|---|
| Clearance, ISO 273 medium | 2.4 | 2.9 | 3.4 | 4.5 | 5.5 | 6.6 | 9 | 11 | 13.5 |
| Tap drill (core hole) | 1.6 | 2.05 | 2.5 | 3.3 | 4.2 | 5 | 6.8 | 8.5 | 10.2 |
| Counterbore Ø × depth, ISO 4762 head | 4.3 × 2.4 | 5 × 2.9 | 6.5 × 3.4 | 8 × 4.4 | 10 × 5.4 | 11 × 6.4 | 15 × 8.6 | 18 × 10.6 | 20 × 12.6 |

Thread depth in steel ≈ 1–1.5 × d, in aluminium ≈ 2 × d; the tapped hole ≈ 3 mm deeper than the thread when blind.
A tapped hole is modelled at the tap-drill Ø (name it "M5 thread").

## Printed fits (FDM, 0.4 mm nozzle) — instead of ISO fits

- Hole for a screw: clearance + 0.2 (M3 Ø3.4–3.6). A hole printed upright comes out ≈ 0.1–0.2 mm small.
- Bearing seat: Ø D + 0.1 … 0.15 (608: Ø22.1–22.15), a shaft Ø d − 0 … 0.05.
- Sliding fit 0.3 mm per side, snug 0.15, press 0 … −0.1 (small pins only); dowel holes Ø d + 0.1.
- For an exact fit, model it with the allowance and say which size to correct after a test print.
