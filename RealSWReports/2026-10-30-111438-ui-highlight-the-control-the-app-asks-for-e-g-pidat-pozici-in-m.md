# Highlight the control the app asks for (e.g. ＋ Přidat pozici) – in moderation

- **Kind:** ui
- **Date:** 2026-10-30 11:14:38
- **App version:** 0.9.0 (main @ a059fa4, 2026-10-30)
- **Reported by:** the AI agent (MCP report_problem)

## What happened

When a toast tells the user to use a control ('Chcete-li sem přidat díru, klikněte nejdřív na ＋ Přidat pozici', 'stiskněte OK a pro druhou plochu udělejte další Díru'), the control itself is not marked – the user has to search the panel for it. In the recording the user clicked the face twice before finding ＋ Přidat pozici, and after OK did not find the Díra row in the suggestions table.

## What was expected

A message that names a control should briefly highlight it (a short pulse / outline for a few seconds, the button scrolled into view; in the suggestions table the named row, e.g. Díra). Only to a reasonable degree, so the UI does not keep glowing: only the one control the message names, only when it was asked for (after a refused / hinted click), it fades out after ~2–3 s or on the next click, no permanent glow and no several highlights at once, and not again for the same hint repeated right away.

## Steps

Rameno (P2): ✎ Upravit díru on Díra 3 → click on another face → info toast naming ＋ Přidat pozici (button not highlighted) → ＋ Přidat pozici → click F6:end → warning 'stiskněte OK … další Díru' (OK and later the Díra row not highlighted).
