// The loading card: a slow thing the user started (a file dropped or opened, a project, a demo, an export, a drawing
// sheet …) says so at once, big in the middle of the window, in every workspace and on the start screen:
// "⏳ Loading part.step (12.4 MB)…", the step it is on (Uploading… / Reading the STEP… / Drawing…), the seconds so far.
// It is painted before the heavy work starts (await b.painted): the page may freeze a moment after, never before the
// card is on screen. Its spinner turns on the compositor (a CSS transform), so it keeps turning through a freeze.
// While a card is up the busy box's server stage and ✕ Cancel (progressbox.js) show on it instead of the small box.
import { t, getLang } from './i18n.js';
import { cancelAll, setStageSink } from './progressbox.js';

const cards = []; // the open ones, newest last: {text, step, at, pct, shown}
let el = null, ticker = null, stage = null; // stage: the busy box's {text, frac, cancelling} while a card is up

const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const t2 = (text, vars) => t(text).replace(/\{(\w+)\}/g, (_, k) => vars[k]);

/** Two frames and a task later: what was put on the page is on screen. */
export const painted = () => new Promise((ok) => requestAnimationFrame(() => requestAnimationFrame(() => setTimeout(ok, 0))));

/** A file's size in words: "12.4 MB" ("12,4 MB" in Czech). */
export function sizeText(bytes) {
  const [v, u] = bytes >= 1e6 ? [bytes / 1e6, 'MB'] : bytes >= 1e3 ? [bytes / 1e3, 'kB'] : [bytes, 'B'];
  const s = u === 'B' ? String(v) : v.toFixed(v < 10 ? 1 : 0);
  return `${getLang() === 'cs' ? s.replace('.', ',') : s} ${u}`;
}

function card() {
  if (!el) {
    el = document.createElement('div');
    el.id = 'loadCard';
    el.className = 'load-card';
    el.hidden = true;
    el.setAttribute('role', 'status');
    el.setAttribute('aria-live', 'polite');
    el.innerHTML = `<span class="load-spin" aria-hidden="true"></span><div class="load-body"><b class="load-text" data-no-i18n></b>
      <span class="load-step" data-no-i18n></span><span class="load-bar" hidden><i></i></span></div>
      <span class="load-secs" data-no-i18n></span><button class="mini load-cancel" hidden title="${esc(t('Stop this (the part stays as it was)'))}">${esc(t('Cancel'))}</button>`;
    el.querySelector('.load-cancel').addEventListener('click', () => { const c = top(); if (!stage && c?.onCancel) { c.cancelling = true; draw(); c.onCancel(); } else cancelAll(); });
    document.body.appendChild(el);
  }
  return el;
}

const top = () => cards.filter((c) => c.shown).pop();

function draw() {
  const c = top(), box = card();
  if (!c) { box.hidden = true; clearInterval(ticker); ticker = null; return; }
  // (the server's stage over the card's own step — after a count of its own: "Built 12 of 254 parts… · Waiting for the
  // CAD kernel…", its bar the count's; cancelling: only that)
  const own = c.count && !stage?.cancelling, said = stage?.text ? t(stage.text) : '';
  const step = own ? [c.step, said].filter(Boolean).join(' · ') : said || c.step, frac = own ? c.pct : stage?.frac ?? c.pct;
  box.querySelector('.load-text').textContent = c.text;
  box.querySelector('.load-step').textContent = step || '';
  const bar = box.querySelector('.load-bar');
  bar.hidden = frac == null;
  if (frac != null) bar.firstElementChild.style.width = `${Math.round(frac * 100)}%`;
  const cancel = box.querySelector('.load-cancel');
  cancel.hidden = !stage && !c.onCancel; // (the card's own ✕ Cancel: busy(text, {onCancel}))
  cancel.disabled = !!(stage ? stage.cancelling : c.cancelling);
  secs();
  box.hidden = false;
  if (!ticker) ticker = setInterval(secs, 1000);
}

/** The seconds so far (shown after the first one: the server's reading cannot be interrupted part-way). */
function secs() {
  const c = top();
  if (!c || !el) return;
  const s = Math.floor((performance.now() - c.at) / 1000);
  el.querySelector('.load-secs').textContent = s >= 1 ? `${s} s` : '';
}

/** A card for a slow operation (text: what it does, in English — translated here) -> {step(text, frac?), done(),
 *  painted: a promise for when the card is on screen}. step(): the step it is on (frac 0…1: a bar, e.g. the upload).
 *  delay (ms): shown only if it takes that long (a quick export does not flash it; its work is the server's).
 *  onCancel: the card has its own ✕ Cancel (once: then disabled) — the caller stops its work itself. */
export function busy(text, { delay = 0, onCancel = null } = {}) {
  const c = { text: t(text), step: '', pct: null, at: performance.now(), shown: !delay, onCancel };
  cards.push(c);
  if (delay) setTimeout(() => { if (cards.includes(c) && !c.aside) { c.shown = true; draw(); } }, delay);
  draw();
  return {
    painted: delay ? Promise.resolve() : painted(),
    step(s, frac = null) { if (!cards.includes(c)) return; Object.assign(c, { step: s ? t(s) : '', pct: frac, count: false }); draw(); },
    done() { const i = cards.indexOf(c); if (i >= 0) { cards.splice(i, 1); if (!top()) stage = null; draw(); } },
  };
}

/** A card for a file (opened, dropped): "Loading part.step (12.4 MB)…". */
export const busyFile = (file, text = 'Loading {name} ({size})…') => busy(t2(text, { name: file.name, size: sizeText(file.size) }));

/** A project being opened (🕘 Recent projects, a project file, a 🎬 demo, the last one offered after a restart …):
 *  its card (text, e.g. "Opening ‹name›…") on screen and painted before work(card) starts — the start screen never just
 *  stands still — and up until the opened project's first frame is painted -> what work returns. */
export async function busyOpen(text, work) {
  const b = busy(text);
  await b.painted;
  try { return await work(b); } finally { await painted(); b.done(); }
}

/** With a card up: a count on it ("Built 12 of 254 parts…", frac 0…1 its bar), drawn at once (not waited for). */
export function busyCount(text, frac) {
  const c = top();
  if (!c) return;
  Object.assign(c, { step: t(text), pct: frac, count: true });
  draw();
}

/** Is a card on screen? */
export const busyShown = () => !!top();

/** The cards up now stand aside (the Save dialog, a question comes): hidden until they are done. */
export function busyAside() {
  for (const c of cards) Object.assign(c, { shown: false, aside: true });
  stage = null;
  draw();
}

/** With a card up: its step set and painted (the work after it may block the page); without one: at once. */
export async function busyStep(text) {
  const c = top();
  if (!c) return;
  Object.assign(c, { step: t(text), pct: null, count: false });
  draw();
  await painted();
}

/** POST a body with its upload's progress (fetch cannot tell it) -> a Response, as fetch's. onUp(frac) while it
 *  goes up, onSent() once it is all on the server. headers: e.g. the jobs list's marks. */
export function postWithProgress(url, body, { onUp, onSent, headers = {} } = {}) {
  return new Promise((ok, fail) => {
    const x = new XMLHttpRequest();
    x.open('POST', url);
    for (const [k, v] of Object.entries(headers)) x.setRequestHeader(k, v);
    x.responseType = 'blob';
    x.upload.onprogress = (e) => { if (e.lengthComputable) onUp?.(e.loaded / e.total); };
    x.upload.onload = () => onSent?.();
    x.onload = () => ok(new Response(x.response, { status: x.status, statusText: x.statusText, headers: { 'Content-Type': x.getResponseHeader('Content-Type') || '' } }));
    x.onerror = () => fail(new Error(t('The server did not answer — is it running?')));
    x.onabort = () => fail(new Error('Cancelled'));
    x.send(body);
  });
}

// the busy box's stage (the server's progress, ✕ Cancel) on the card while one is up
setStageSink((s) => {
  if (!top()) return false;
  if (!s && stage?.cancelling) return true; // (cancelled: "Cancelling…" until the card is done, never its step again)
  if (JSON.stringify(s) !== JSON.stringify(stage)) { stage = s; draw(); }
  return true;
});
