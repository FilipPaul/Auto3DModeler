// ✨ AI settings: how the chat's AI works on this project — the design profile, manufacturing, when it asks, how long it
// answers, its design rules and modes (📌 This file only: only the workspace's tools — kept under its old key `lean`,
// once ⚡ Lean mode). Kept per project (its file:
// `ai_settings`, travels in the .a3d); a new project gets the app's default ("Use as default", localStorage). The server
// turns them into one short line before a message (auto3d/ai_settings.py, the same names); #tags in a message change
// them for that message only.

import { t } from './i18n.js';

// what picking a profile sets (asking, answers, modes and internet stay as they are)
export const PROFILES = {
  automation: { make: ['cnc'], standard: true, dfm: true, dfa: true, review: true },
  print: { make: ['print'], standard: true, dfm: true, dfa: true, review: true },
  deco: { make: ['print'], standard: false, dfm: false, dfa: false, review: false },
};
const DEFAULTS = { profile: 'automation', ...PROFILES.automation, ask: 'key', answers: 'short', teach: false, bugs: false, internet: true, lean: false };
const MAKES = ['cnc', 'print', 'laser'];
const CHOICES = { profile: [...Object.keys(PROFILES), 'custom'], ask: ['key', 'all', 'none'], answers: ['short', 'normal', 'explain'] };
const FLAGS = ['standard', 'dfm', 'dfa', 'review', 'teach', 'bugs', 'internet', 'lean'];
const KEY = 'a3d.aiSettings'; // (the app's default)
const TAGS_KEY = 'a3d.chatTags'; // (the tags under the chat's box shown: '0' hidden — the app's, not the project's)

/** The message tags (the chat's # autocomplete, the chips under its box): each changes the settings for its message only;
 *  tip: what it does (the chip's tooltip). */
export const TAGS = [
  { tag: 'uc', label: '🎓 Teach me', tip: 'This message: the AI shows you where to click and explains — you do the steps' },
  { tag: 'chyby', label: '🐞 Bug hunter', tip: 'This message: the AI works through the GUI only and reports every problem it finds' },
  { tag: 'kontrola', label: '🔍 Design review', tip: 'This message: the AI checks the design against the rules before it says it is done' },
  { tag: 'rychle', label: '⚡ Quick: this file only, no review, brief', tip: 'This message: only the tools of the file open now, no design review, a brief answer' },
  { tag: 'cnc', label: 'CNC machining', tip: 'This message: design it for CNC machining' },
  { tag: 'tisk', label: '3D print', tip: 'This message: design it for 3D printing' },
  { tag: 'bez-otazek', label: 'Don\'t ask, decide', tip: 'This message: the AI asks nothing — it decides and says what it chose' },
];

/** The tags under the chat's box shown (the panel's "Show the tags under the chat"; kept in this browser). */
export function tagsShown() { try { return localStorage.getItem(TAGS_KEY) !== '0'; } catch { return true; } }

export function showTags(on) {
  try { localStorage.setItem(TAGS_KEY, on ? '1' : '0'); } catch { /* private window: not kept */ }
  window.dispatchEvent(new Event('a3d:chat-tags'));
}

/** Anything (a project file's, the stored default) -> complete, valid settings. */
export function cleanSettings(v) {
  const s = { ...DEFAULTS, make: [...DEFAULTS.make] };
  if (!v || typeof v !== 'object') return s;
  for (const [k, ok] of Object.entries(CHOICES)) if (ok.includes(v[k])) s[k] = v[k];
  if (Array.isArray(v.make)) s.make = MAKES.filter((m) => v.make.includes(m));
  for (const k of FLAGS) if (typeof v[k] === 'boolean') s[k] = v[k];
  return s;
}

const sameAs = (s, p) => Object.entries(p).every(([k, v]) => (Array.isArray(v) ? v.length === s[k].length && v.every((x) => s[k].includes(x)) : s[k] === v));

/** Tokens per task (thousands, a range) and the speed (1–5) the settings give — a rough guide, as the panel shows it. */
export function estimate(s) {
  let lo = 25, hi = 40;
  const add = (on, a, b) => { if (on) { lo += a; hi += b; } };
  add(s.review, 3, 6);
  add(s.teach, 10, 25);
  add(s.bugs, 15, 40);
  add(s.lean, -12, -18);
  add(s.ask === 'all', 1, 3);
  add(s.answers === 'normal', 1, 2);
  add(s.answers === 'explain', 2, 5);
  const mid = (lo + hi) / 2;
  return { lo, hi, speed: mid < 25 ? 5 : mid < 38 ? 4 : mid < 55 ? 3 : mid < 80 ? 2 : 1 };
}

class AiSettings {
  constructor() {
    this.s = this.appDefault();
    this.listeners = new Set();
  }

  appDefault() { try { return cleanSettings(JSON.parse(localStorage.getItem(KEY) || 'null')); } catch { return cleanSettings(null); } }

  get() { return { ...this.s, make: [...this.s.make] }; }

  /** A change from the panel: a profile sets its defaults; a changed default of the profile makes it ✎ Custom. */
  set(patch) {
    const s = { ...this.s, ...patch };
    if (patch.profile && PROFILES[patch.profile]) Object.assign(s, PROFILES[patch.profile], { make: [...PROFILES[patch.profile].make] });
    else if (PROFILES[s.profile] && !sameAs(s, PROFILES[s.profile])) s.profile = 'custom';
    this.s = cleanSettings(s);
    this.notify();
    window.dispatchEvent(new Event('a3d:changed')); // (autosave: they are the project's)
  }

  /** A project opened: its settings, else (a new or an older project) the app's default. */
  load(saved) {
    this.s = saved && typeof saved === 'object' ? cleanSettings(saved) : this.appDefault();
    this.notify();
  }

  /** For the project file. */
  toJSON() { return this.get(); }

  /** "Use as default": new projects start with these. */
  saveDefault() { try { localStorage.setItem(KEY, JSON.stringify(this.s)); } catch { /* private window: not kept */ } this.notify(); }

  isDefault() { return JSON.stringify(this.s) === JSON.stringify(this.appDefault()); }

  listen(fn) { this.listeners.add(fn); }

  notify() { for (const fn of this.listeners) fn(this.get()); }
}
export const aiSettings = new AiSettings();

const seg = (k, opts) => `<div class="ais-seg" data-k="${k}">${opts.map(([v, label, tip]) => `<button type="button" data-v="${v}"${tip ? ` title="${tip}"` : ''}>${label}</button>`).join('')}</div>`;
const TOGGLES = [
  ['standard', '📦 Standard parts', '+0', 'Bought, standard parts from the library, as few kinds as possible'],
  ['dfm', '🏭 Easy manufacture', '+0', 'Shapes the chosen manufacturing makes easily and cheaply'],
  ['dfa', '🔩 Easy assembly', '+0', 'Few fastener kinds, assembled from one side, parts that locate themselves'],
  ['review', '🔍 Design review', '+3–6k', 'The AI checks the design against the rules before it says it is done'],
  ['teach', '🎓 Teach me', '+10–25k', 'The AI shows you where to click and explains — you do the steps'],
  ['bugs', '🐞 Bug hunter', '+15–40k', 'The AI works through the GUI only and reports every problem it finds in the app'],
  ['internet', '🌐 Search the internet for parts', '', 'The AI may look up bought parts and their 3D models on the internet'],
  ['lean', '📌 Limit the AI to the file open now', '−12–18k', 'The AI gets only the tools of the file (workspace) on screen — fewer tokens, faster; the same as 📌 This file only under the chat'],
];

/** The ✨ AI settings panel in `box` (the chat's): every change applies at once and is kept with the project. */
export function settingsPanel(box, { onClose, toast }) {
  box.innerHTML = `
    <div class="ais-head"><b>✨ AI settings</b><span class="ais-proj">for this project</span><button type="button" class="mini ais-x" title="Close the settings">✕</button></div>
    <div class="ais-h">Design profile</div>
    ${seg('profile', [['automation', '⚙ Automation / ICT', 'Machines, fixtures: CNC, standard parts, easy manufacture and assembly, review'],
    ['print', '🖨 Functional print', 'Functional 3D-printed parts: standard parts, easy print and assembly, review'],
    ['deco', '🎨 Decoration', 'Graphic, decorative 3D prints: no engineering rules'], ['custom', '✎ Custom', 'Your own choice of the settings below']])}
    <div class="ais-h">Manufacturing</div>
    ${seg('make', [['cnc', 'CNC machining'], ['print', '3D print'], ['laser', 'Laser / sheet metal']])}
    <div class="ais-h">Ask before designing</div>
    ${seg('ask', [['key', 'Key sizes only'], ['all', 'Everything'], ['none', 'Don\'t ask, decide']])}
    <div class="ais-h">Answers</div>
    ${seg('answers', [['short', 'Brief'], ['normal', 'Normal'], ['explain', 'With explanation']])}
    <div class="ais-h">Behaviour</div>
    <div class="ais-togs">${TOGGLES.map(([k, label, cost, tip]) => `<label class="ais-tog" title="${tip}"><input type="checkbox" data-k="${k}"><span>${label}</span>${cost ? `<span class="ais-cost">${cost}</span>` : ''}</label>`).join('')}</div>
    <div class="ais-meter"><div class="ais-bar"><i></i></div><span class="ais-est" data-no-i18n></span><span class="ais-speed" data-no-i18n></span></div>
    <div class="ais-tip">Tags in a message change it for that message: #uc #chyby #kontrola #rychle #cnc #tisk #bez-otazek</div>
    <label class="ais-tog ais-ui" title="A thin row of the tags under the box to write in — a click puts one in"><input type="checkbox" class="ais-tagbar"><span>Show the tags under the chat</span></label>
    <div class="ais-acts"><button type="button" class="btn small ais-default" title="New projects start with these settings">Use as default</button><span class="ais-isdef">The app's default</span>
      <span class="ai-grow"></span><button type="button" class="btn small primary ais-done">Done</button></div>`;
  const update = (s) => {
    for (const g of box.querySelectorAll('.ais-seg')) {
      for (const b of g.querySelectorAll('button')) b.classList.toggle('on', g.dataset.k === 'make' ? s.make.includes(b.dataset.v) : s[g.dataset.k] === b.dataset.v);
    }
    for (const c of box.querySelectorAll('.ais-tog input[data-k]')) c.checked = !!s[c.dataset.k];
    box.querySelector('.ais-tagbar').checked = tagsShown();
    const e = estimate(s);
    box.querySelector('.ais-bar i').style.width = `${Math.min(100, ((e.lo + e.hi) / 2 / 90) * 100)}%`;
    box.querySelector('.ais-est').textContent = t('≈ {lo}–{hi}k tokens per task').replace('{lo}', e.lo).replace('{hi}', e.hi);
    box.querySelector('.ais-speed').textContent = `${t('Speed')} ${'●'.repeat(e.speed)}${'○'.repeat(5 - e.speed)}`;
    box.querySelector('.ais-speed').dataset.speed = e.speed;
    const def = aiSettings.isDefault();
    box.querySelector('.ais-default').hidden = def;
    box.querySelector('.ais-isdef').hidden = !def;
  };
  for (const g of box.querySelectorAll('.ais-seg')) {
    g.addEventListener('click', (e) => {
      const b = e.target.closest('button');
      if (!b) return;
      const k = g.dataset.k, v = b.dataset.v;
      if (k !== 'make') { aiSettings.set({ [k]: v }); return; }
      const make = aiSettings.get().make;
      aiSettings.set({ make: make.includes(v) ? make.filter((m) => m !== v) : [...make, v] });
    });
  }
  for (const c of box.querySelectorAll('.ais-tog input[data-k]')) c.addEventListener('change', () => aiSettings.set({ [c.dataset.k]: c.checked }));
  box.querySelector('.ais-tagbar').addEventListener('change', (e) => showTags(e.target.checked));
  box.querySelector('.ais-default').addEventListener('click', () => { aiSettings.saveDefault(); toast?.(t('New projects start with these AI settings.'), 'ok'); });
  box.querySelector('.ais-x').addEventListener('click', () => onClose());
  box.querySelector('.ais-done').addEventListener('click', () => onClose());
  aiSettings.listen((s) => { if (!box.hidden) update(s); });
  window.addEventListener('a3d:lang', () => update(aiSettings.get()));
  update(aiSettings.get());
  return { update: () => update(aiSettings.get()) };
}
