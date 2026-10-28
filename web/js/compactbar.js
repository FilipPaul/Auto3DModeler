// Command bars on a narrow view: when the tools with their names would take more than 3 rows, the tools show only
// their icons ("⬆ Extrude" -> "⬆"; the name leads the tooltip) and the groups keep their places and colours; a wider
// view brings the names back. Measured after each render (the bar's content changes, a translation too) and when the
// view is resized — for the 3D model's, the sketch's and the assembly's bar (and its 🔗 Joint row).

import { t } from './i18n.js';

const TOOLS = 'button[data-a], button[data-joint], button[data-origin], .as-jlabel';
const MAX_ROWS = 3; // (a wide window, 1600 px, shows 3 rows of names, as it always did)

/** "⬆ Extrude" -> "⬆"; "⚠ 3 collision(s)" -> "⚠ 3"; "⟂ Relations ▾" -> "⟂▾"; a label without an icon: null. */
function shortOf(text) {
  const m = text.replace(/\s+/g, ' ').trim().match(/^(\S+) (\S.*)$/u);
  if (!m || (/[A-Za-z0-9]/.test(m[1]) && m[1] !== 'Aa')) return null; // ("Top", "Front": a word, kept)
  const num = m[2].match(/^\d+/);
  return { icon: `${m[1]}${num ? ` ${num[0]}` : ''}${/▾$/.test(m[2]) ? '▾' : ''}`, name: m[2].replace(/\s*▾$/, '') };
}

/** How many rows the bar's controls take (by their tops). */
export function barRows(bar) {
  const tops = [];
  for (const e of bar.querySelectorAll('button, label, .m-mode, .m-say, .as-jlabel')) {
    if (e.closest('.mp-actions, .menu-list') || !e.offsetWidth) continue;
    tops.push(e.getBoundingClientRect().top);
  }
  tops.sort((a, b) => a - b);
  let rows = 0, last = -1e9;
  for (const y of tops) if (y > last + 10) { rows++; last = y; }
  return rows;
}

function setCompact(bar, on) {
  bar.classList.toggle('cb-compact', on);
  for (const el of bar.querySelectorAll(TOOLS)) {
    if (el.closest('.mp-actions, .menu-list')) continue;
    if (el.__cbTip !== undefined && el.title === el.__cbTip) el.title = el.__cbTitle; // (the tooltip as it was)
    delete el.__cbTip;
    el.removeAttribute('data-icon');
    const s = on && shortOf(el.textContent);
    if (!s) continue;
    el.dataset.icon = s.icon;
    // (in the current language: t() here, so the translation does not see — and miss — the joined text)
    const tip = el.__cbTitle = el.title, name = t(s.name), tr = t(tip);
    el.__cbTip = el.title = !tr ? name : tr.startsWith(name) ? tr : `${name}: ${tr}`;
  }
}

function fit(bar) {
  if (!bar.isConnected || !bar.offsetWidth) return;
  const was = bar.classList.contains('cb-compact'), before = bar.offsetHeight;
  setCompact(bar, false);
  const on = barRows(bar) > MAX_ROWS;
  if (on) setCompact(bar, true);
  if (on === was && bar.offsetHeight === before) return;
  const h = bar.parentElement?.querySelector(':scope > .m-hint'); // (under the bar)
  if (h) h.style.top = `${bar.offsetTop + bar.offsetHeight + 8}px`;
}

/** Fit the bar now, and again whenever its content or its view's size changes (set up once per bar). */
export function fitBar(bar) {
  if (!bar) return;
  if (!bar.__cbWatch) {
    bar.__cbWatch = true;
    new MutationObserver(() => fit(bar)).observe(bar, { childList: true, subtree: true, characterData: true });
    if (window.ResizeObserver && bar.parentElement) new ResizeObserver(() => fit(bar)).observe(bar.parentElement);
  }
  fit(bar);
}
