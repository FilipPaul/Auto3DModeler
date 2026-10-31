# Assembly panel (CZ): English labels, unnamed 'input' sliders, motions named after a library part's internal face

- **Kind:** ui
- **Date:** 2026-10-29 01:56:47
- **App version:** 0.9.0 (main @ 63d5c3a, 2026-10-28)
- **Reported by:** the AI agent (MCP report_problem)

## What happened

With a placed part selected (Klika I3) in the Czech UI: buttons "◆ Open its part" and "📌 Fix in place", and the joint-name tooltip "Double-click: give it your own name" are in English (others say "Dvojklik: dát jí vlastní název"). Three slider + box pairs under the X / Y / Z boxes are labelled only "input" (probably rotation about X / Y / Z). The crank's free motion is named "Otočit kolem osy: stěna Revolve 2 (Bearing 608-2Z)" — an internal face name of the library bearing that the user never made. Also "◆ Otevřít jeho díl" and "◆ Open its part", "⧉ Udělat z něj vlastní díl" twice, "📌 Ukotvit na místě" and "📌 Fix in place", "✕ Vyjmout" and "Vyjmout" appear twice in the same panel.

## What was expected

All labels in Czech; the rotation sliders labelled (↻ X / ↻ Y / ↻ Z); a motion named by the joint the user named ("Otočit: čep kliky v ložisku") or by a readable face ("vnitřní kroužek – Bearing 608-2Z"); each action once in the panel.

## Steps

Assembly Klikový mechanismus, click part "Klika I3" in the list, gui_state where: panel.
