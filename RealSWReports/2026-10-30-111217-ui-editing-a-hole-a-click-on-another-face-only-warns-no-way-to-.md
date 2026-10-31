# Editing a hole: a click on another face only warns – no way to put the same holes there

- **Kind:** ui
- **Date:** 2026-10-30 11:12:17
- **App version:** 0.9.0 (main @ a059fa4, 2026-10-30)
- **Reported by:** the AI agent (MCP report_problem)

## What happened

User edited 'Díra 3' (2× M3 on F4:end) with ✎ Upravit díru and wanted the same holes on the second pad F6:end. Clicks on F6:end gave first 'klikněte nejdřív na ＋ Přidat pozici', after ＋ Přidat pozici the warning 'Díry jednoho kroku jsou na jedné ploše — stiskněte OK a pro druhou plochu udělejte další Díru'. After OK they selected F6:end, saw the table 'Extrude 3 · horní plocha' and gave up (clicked empty space) — the way on was not clear.

## What was expected

In hole edit, a click on another flat face should offer a button in the toast/panel: '＋ Nová díra na této ploše' (same size/type, the hole placed there) or 'Zkopírovat díry sem' (the same pattern relative to the face's edges). Also the hint 'klikněte nejdřív na ＋ Přidat pozici' should not appear for a face where adding is not allowed anyway.

## Steps

Rameno (P2): select edge F4:end|F9:hole:1 → ✎ Upravit díru → click F6:end (info toast twice) → ＋ Přidat pozici → click F6:end (warning) → OK → select F6:end → table without a clear next step.
