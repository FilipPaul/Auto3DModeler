// The AI chat: Claude Code (the user's own installation and sign-in) works on the open part through the
// app's MCP tools. The server relays each tool call to this page (long-poll), the page applies it like
// the user would (visible at once, undoable) and posts the result back. The chat itself streams from
// the server as Server-Sent Events. Its conversations are kept on the server (auto3d/chat_history.py): 🕘 Previous
// conversations lists them, one opened goes on (Claude's session resumed, or a new one told it in short).

import { t } from './i18n.js';
import { recorder } from './recorder.js';
import { pageBuild } from './stale.js';

const escapeHtml = (s) => s.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

/** Minimal markdown for chat replies: paragraphs, lists, **bold**, `code`. */
function md(text) {
  const inline = (t) => escapeHtml(t).replace(/\*\*(.+?)\*\*/g, '<b>$1</b>').replace(/`([^`]+)`/g, '<code>$1</code>');
  const out = [];
  let list = null;
  for (const line of text.split('\n')) {
    const m = line.match(/^\s*(?:[-*•]|\d+[.)])\s+(.*)/);
    if (m) {
      if (!list) { list = []; out.push(list); }
      list.push(inline(m[1]));
    } else {
      list = null;
      out.push(line.trim() ? `<p>${inline(line)}</p>` : '');
    }
  }
  return out.map((x) => (Array.isArray(x) ? `<ul>${x.map((li) => `<li>${li}</li>`).join('')}</ul>` : x)).join('');
}

/** How many of the AI's tool calls this page has run (a turn that ran none here changed nothing here). */
export const bridgeStats = { calls: 0 };

const CALL_BUDGET_S = 140; // a tool call's most time here (the server waits 150 s for it)

// This window's id: its chat is its own (the server keeps one per window) and the chat's tool calls act here only.
// A reload keeps it (sessionStorage: this window's), as does 📄 New project (keepChatClient); a new window — also one
// opened from here, which gets a copy of the sessionStorage — has its own.
const CLIENT_KEY = 'a3d.chatClient', KEEP_KEY = 'a3d.chatKeep', CONV_KEY = 'a3d.chatConv'; // (+ this window's conversation: back after a restart)
function windowClient() {
  const fresh = () => (crypto.randomUUID ? crypto.randomUUID() : `${Date.now().toString(36)}${Math.random().toString(36).slice(2)}`);
  try {
    const nav = performance.getEntriesByType?.('navigation')?.[0]?.type, keep = sessionStorage.getItem(KEEP_KEY) === '1';
    sessionStorage.removeItem(KEEP_KEY);
    let id = nav === 'reload' || keep ? sessionStorage.getItem(CLIENT_KEY) : null;
    if (!id) { id = fresh(); sessionStorage.setItem(CLIENT_KEY, id); }
    return id;
  } catch { return fresh(); } // (no sessionStorage: a new chat after a reload)
}
export const CLIENT = windowClient();
/** The next page load in this window (📄 New project) goes on with this window's chat. */
export function keepChatClient() { try { sessionStorage.setItem(KEEP_KEY, '1'); } catch { /* private window */ } }
const withClient = (url) => `${url}${url.includes('?') ? '&' : '?'}client=${encodeURIComponent(CLIENT)}`;

/** Run tool calls from the server: handlers = {tool: async (args) => ({text, image?, error?, body?})}. */
export function startBridge(handlers) {
  let alive = true;
  // the calls of this window's chat come here only; an AI of its own (an MCP client without a window) works in the
  // window in use (visible)
  const client = CLIENT;
  // closing: its chat's calls fail at once instead of waiting (a reload is back within seconds)
  window.addEventListener('pagehide', () => navigator.sendBeacon?.(withClient('/api/agent/bye')));
  let poller = null;
  const repoll = () => poller?.abort();
  document.addEventListener('visibilitychange', repoll);
  window.addEventListener('focus', repoll);
  const done = new Map(); // id -> result: a command handed out again (lease expired) is not run twice

  const loop = async () => {
    while (alive) {
      let cmd = null;
      try {
        poller = new AbortController();
        const active = document.visibilityState === 'visible' ? 1 : 0;
        const res = await fetch(`/api/agent/poll?client=${encodeURIComponent(client)}&active=${active}${pageBuild() ? `&build=${pageBuild()}` : ''}`, { signal: poller.signal });
        if (res.status === 200) cmd = await res.json();
      } catch (e) {
        if (e.name !== 'AbortError') await new Promise((r) => setTimeout(r, 2000));
        continue;
      }
      if (!cmd) continue;
      let result = done.get(cmd.id);
      // (a long call: the server hears every 10 s that this window is still there — not closed)
      const alive = setInterval(() => fetch(withClient('/api/agent/alive'), { method: 'POST' }).catch(() => {}), 10000);
      if (!result) try {
        const fn = handlers[cmd.cmd];
        // (a call that never ends must not stop this loop: the page would stop asking for calls and look closed)
        let late;
        const budget = new Promise((r) => { late = setTimeout(() => r({ text: `${cmd.cmd} took longer than ${CALL_BUDGET_S} s and was given up — the app goes on; check what it changed (get_model / gui_state).`, error: true }), CALL_BUDGET_S * 1000); });
        result = fn ? await Promise.race([fn(cmd.args || {}), budget]) : { text: `The page does not know '${cmd.cmd}'.`, error: true };
        clearTimeout(late);
        bridgeStats.calls++;
      } catch (e) {
        result = { text: `${cmd.cmd} failed: ${e.message || e}`, error: true };
      }
      clearInterval(alive);
      done.set(cmd.id, result);
      if (done.size > 100) done.delete(done.keys().next().value);
      try {
        await fetch('/api/agent/result', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: cmd.id, result }) });
      } catch { /* the server went away: the call times out there */ }
    }
  };
  loop();
  return () => { alive = false; };
}

const TOOL_LABEL = {
  get_part: 'reading the part', get_screenshot: 'looking at the 3D view', open_file: 'opening a file', open_sample: 'opening the sample',
  trace_picture: 'tracing the picture', use_outline: 'making the part from the outline', set_dimensions: 'setting dimensions',
  set_make: 'choosing what to make', set_part_options: 'changing part options', add_object: 'adding a 3D object',
  add_shape: 'adding a 2D shape', add_design_layer: 'adding a design layer', update_item: 'changing an item', remove_item: 'removing an item',
  add_dimension: 'adding a dimension', check_print: 'checking the printer fit', export: 'exporting', undo: 'undoing',
  list_parts: 'looking at the parts', open_part: 'opening a part', duplicate_part: 'copying a part', new_model: 'starting a 3D model', get_model: 'reading the 3D model',
  find_refs: 'finding faces and edges', add_feature: 'adding a step', edit_feature: 'changing a step', delete_feature: 'deleting a step',
  turn_off_feature: 'turning a step off / on', rollback: 'moving the rollback bar', simplify_sketch: 'simplifying a sketch', get_sketch: 'reading a sketch', sketch_auto_dims: 'dimensioning a sketch', sketch_dim: 'setting a sketch dimension', get_parameters: 'reading the parameters', set_parameter: 'setting a parameter', list_versions: 'listing the versions', save_version: 'saving a version', restore_version: 'restoring a version', compare_versions: 'comparing versions', create_variant: 'making a variant', sketch_trim: 'trimming a sketch', sketch_union: 'uniting shapes in a sketch', prepare_print: 'preparing the print', set_material: 'setting the material', new_assembly: 'starting an assembly', suggest_fasteners: 'finding where fasteners fit', add_fasteners: 'adding fasteners',
  get_assembly: 'reading the assembly', add_harness: 'routing a cable', edit_harness: 'changing a cable', get_bom: 'reading the bill of materials', insert_part: 'inserting a part', library_search: 'searching the parts library', set_look: 'colouring a part', paint_faces: 'painting faces', move_free: 'moving a part', sheet_open: 'opening a drawing', get_sheet: 'reading the drawing', sheet_edit: 'editing the drawing', ask_user: 'asking you', gui_state: 'looking at the screen', gui_action: 'clicking in the app', gui_highlight: 'showing you where', list_reports: 'reading the problem reports', drawing_delete: 'deleting shapes', drawing_add: 'drawing shapes', drawing_units: 'setting the drawing units', set_travel: 'setting a motion\'s limits', check_travel: 'checking a motion for collisions', lock_motion: 'locking a motion', drive_mechanism: 'driving a mechanism', record_animation: 'recording an animation', name_motion: 'naming a motion', save_to_library: 'saving to the library', report_problem: 'writing a problem report', library_add: 'adding a library part', library_pair: 'adding what goes with a part', check_collisions: 'checking for collisions', snap_faces: 'snapping parts together', place_part: 'placing a part', remove_from_assembly: 'taking a part out', get_guide: 'reading a guide', Skill: 'reading a guide',
  switch_variant: 'switching the variant', take_part: 'taking a part from a variant', rename_variant: 'renaming a variant', delete_variant: 'deleting a variant',
  add_missing_joint: 'adding the missing joint', edit_chain: 'changing an energy chain', set_layout: 'arranging the widgets', new_project: 'starting a new project',
  start_recording: 'starting to record your moves', stop_recording: 'stopping the recording', get_recording: 'reading your recorded moves', get_recording_screenshot: 'looking at a recorded screenshot',
  list_demos: 'looking at the demo projects', open_demo: 'opening a demo project',
  get_drawing: 'reading the 2D drawing', drawing_find: 'finding shapes', drawing_layers: 'setting the layers', drawing_set_size: 'sizing shapes', drawing_use: 'making something of the drawing', measure: 'measuring', list_measurements: 'reading the measurements', clear_measurements: 'clearing the measurements', set_view: 'setting the view', rename_part: 'renaming a part', delete_part: 'deleting a part', edit_joint: 'changing a joint', remove_joint: 'removing a joint', bolt_parts: 'bolting parts together',
};

const MAX_PHOTOS = 5, PHOTO_EDGE = 2400; // a longer side than this is scaled down (Claude sees ~1600 px anyway)

/** A photo file -> data URL, scaled down when very large (keeps PNG for small pictures, else JPEG). */
async function photoData(file) {
  if (!/^image\/(png|jpeg|webp|gif)$/.test(file.type)) throw new Error('not a photo');
  const url = await new Promise((ok, fail) => { const r = new FileReader(); r.onload = () => ok(r.result); r.onerror = fail; r.readAsDataURL(file); });
  const img = await new Promise((ok, fail) => { const i = new Image(); i.onload = () => ok(i); i.onerror = fail; i.src = url; });
  const k = Math.min(1, PHOTO_EDGE / Math.max(img.naturalWidth, img.naturalHeight));
  if (k === 1 && file.size < 4 * 1024 * 1024) return url;
  const c = document.createElement('canvas');
  c.width = Math.round(img.naturalWidth * k);
  c.height = Math.round(img.naturalHeight * k);
  c.getContext('2d').drawImage(img, 0, 0, c.width, c.height);
  return c.toDataURL('image/jpeg', 0.9);
}

const when = (s) => new Date(s * 1000).toLocaleString(undefined, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
const tn = (text, n) => t(text).replace('{n}', n);
const session = { get: (k) => { try { return sessionStorage.getItem(k); } catch { return null; } },
  set: (k, v) => { try { if (v) sessionStorage.setItem(k, v); else sessionStorage.removeItem(k); } catch { /* private window */ } } };

export class ChatPanel {
  /** hooks: project() -> {id, name} (the project on screen: a new conversation is about it), onShow() (the chat in sight). */
  constructor(root, { toast, onUndo, canUndo, onTurnDone, onHistory, project, onShow }) {
    this.root = root;
    this.toast = toast;
    this.project = project;
    this.onShow = onShow;
    this.conv = null; // the conversation on screen ({id, title, created …}; null: a new one, made with its first message)
    this.onTurnDone = onTurnDone; // ({prompt}) after each AI turn
    this.turnPrompt = '';
    this.onUndo = onUndo;
    this.canUndo = canUndo;
    this.lastSeq = 0;
    this.current = null; // the assistant bubble being written
    root.innerHTML = `
      <div class="ai-head">
        <span class="ai-status">Checking for Claude Code…</span>
        <span class="ai-acts">
          <button class="mini ai-undo" title="Undo the last change (Ctrl+Z) — the AI's changes are steps in the app's undo history">↶ Undo</button>
          <button class="mini ai-hist" title="The project after each change Claude made — browse it and load one back">🕘 History</button>
          <button class="mini ai-key" title="Sign in, change the API key or sign out">🔑 Access</button>
        </span>
      </div>
      <div class="ai-convbar">
        <span class="ai-convtitle" data-no-i18n></span>
        <button class="mini ai-convs-btn" title="The earlier chats — open one to read it and go on with it">🕘 Previous conversations</button>
        <button class="mini ai-new" title="Start a new conversation">＋ New conversation</button>
      </div>
      <div class="ai-convs" hidden></div>
      <div class="ai-access" hidden></div>
      <div class="ai-log"><div class="ai-empty">
        <p><b>Describe what you want</b> — Claude works on the part in the app: opens drawings, traces pictures, sets
        sizes, adds holes, text and objects, checks the printer and exports.</p>
        <p><b>3D models and assemblies</b> too — it sketches, extrudes, drills, rounds and puts parts together.</p>
        <p class="hint">e.g. “Make a 90 mm cookie cutter from C:\\pics\\star.png with a hanging hole” · “Add a 5 mm hole 8 mm from the top”
        · “Engrave my name on the flange”.</p>
        <p class="hint">“Make a 60 × 40 × 5 mm plate with four Ø4 holes 6 mm from the corners and rounded edges” · “Put the pin into
        the hole of the plate”.</p>
        <p class="hint">📎 Attach a photo (or paste / drop it here) — “Make a cookie cutter from this, 90 mm wide”.</p>
        <p class="hint">“Show me how to add a hole” — Claude points at each button in turn and waits for your click.</p>
        <p class="hint">/uiTester — Claude designs test parts, tries the app's buttons and reports what does not work · /suggest — ideas for new features.</p>
        <p class="hint">Runs on your own Claude Code sign-in (Claude subscription or API key) — the app only gives Claude its part tools.</p>
      </div></div>
      <form class="ai-form">
        <div class="ai-photos" hidden></div>
        <div class="ai-rec" hidden data-no-i18n></div>
        <textarea rows="3" placeholder="Message Claude… (Enter = send, Shift+Enter = new line)"></textarea>
        <div class="ai-send">
          <label class="btn small ai-attach" title="Attach photos — or paste (Ctrl+V) or drop them here. Claude sees them and can trace one into a part.">📎 Photo<input type="file" accept="image/*" multiple hidden></label>
          <span class="ai-grow"></span>
          <button type="submit" class="btn primary small">Send</button><button type="button" class="btn small ai-stop" hidden>Stop</button>
        </div>
      </form>`;
    this.$ = (s) => root.querySelector(s);
    this.log = this.$('.ai-log');
    const ta = this.$('textarea');
    ta.addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); this.send(); } });
    this.$('.ai-form').addEventListener('submit', (e) => { e.preventDefault(); this.send(); });
    // photos: 📎, paste or drop — shown as thumbnails until sent
    this.photos = [];
    const fileIn = this.$('.ai-attach input');
    fileIn.addEventListener('change', () => { this.addPhotos(fileIn.files); fileIn.value = ''; });
    ta.addEventListener('paste', (e) => {
      const files = [...(e.clipboardData?.files || [])].filter((f) => f.type.startsWith('image/'));
      if (files.length) { e.preventDefault(); this.addPhotos(files); }
    });
    root.addEventListener('dragover', (e) => { if ([...e.dataTransfer.items].some((i) => i.type.startsWith('image/'))) { e.preventDefault(); e.stopPropagation(); root.classList.add('drop'); } });
    root.addEventListener('dragleave', (e) => { if (!root.contains(e.relatedTarget)) root.classList.remove('drop'); });
    root.addEventListener('drop', (e) => {
      root.classList.remove('drop');
      const files = [...e.dataTransfer.files].filter((f) => f.type.startsWith('image/'));
      if (files.length) { e.preventDefault(); e.stopPropagation(); this.addPhotos(files); }
    });
    this.$('.ai-stop').addEventListener('click', () => fetch(withClient('/api/chat/stop'), { method: 'POST' }));
    this.$('.ai-new').addEventListener('click', () => { this.showConvs(false); fetch(withClient('/api/chat/reset'), { method: 'POST' }); });
    this.$('.ai-convs-btn').addEventListener('click', () => this.showConvs(this.$('.ai-convs').hidden));
    document.addEventListener('pointerdown', (e) => { if (!this.$('.ai-convs').hidden && !e.target.closest('.ai-convs, .ai-convs-btn')) this.showConvs(false); });
    this.$('.ai-undo').addEventListener('click', () => this.onUndo());
    this.$('.ai-hist').addEventListener('click', () => onHistory?.());
    this.$('.ai-key').addEventListener('click', () => this.showAccess(true));
    this.updateUndo();
    this.checkStatus();
    this.connect();
    recorder.listen(() => this.renderRec()); // (⏺ a stopped recording: 📎 attached to the next message with one click)
    window.addEventListener('a3d:lang', () => { this.renderRec(); this.renderConv(); });
    this.renderRec();
  }

  /** 📎 Attach the recording (n events): a stopped recording of moves goes with the next message (a click; again: not). */
  renderRec() {
    const box = this.$('.ai-rec'), n = recorder.attachable();
    if (!n) this.recOn = false;
    const key = n ? `${n}|${this.recOn}|${t('Attach')}` : '';
    if (key === box.dataset.key) return;
    box.dataset.key = key;
    box.hidden = !n;
    box.innerHTML = !n ? '' : this.recOn
      ? `<button type="button" class="btn small on" title="${escapeHtml(t('Click: the recording does not go with the message'))}">📎 ${escapeHtml(t('The recording goes with the message'))} ✕</button>`
      : `<button type="button" class="btn small" title="${escapeHtml(t('Your recorded moves go with the next message — the AI reads what you did'))}">📎 ${escapeHtml(t('Attach the recording ({n} events)').replace('{n}', n))}</button>`;
    box.querySelector('button')?.addEventListener('click', () => { this.recOn = !this.recOn; this.renderRec(); this.$('textarea').focus(); });
  }

  // ------------------------------------------------------------------ 🕘 previous conversations (kept on the server)
  /** The conversation on screen: its title above the log. */
  renderConv() {
    const el = this.$('.ai-convtitle');
    el.textContent = this.conv?.title || '';
    el.title = this.conv?.created ? `${this.conv.title} · ${when(this.conv.created)}` : '';
  }

  /** The list of the kept conversations (this project's first): open one, ✕ delete one. */
  async showConvs(open = true) {
    const box = this.$('.ai-convs');
    box.hidden = !open;
    this.$('.ai-convs-btn').classList.toggle('on', open);
    if (!open) return;
    let list = [], current = null;
    try { ({ conversations: list, current } = await (await fetch(withClient('/api/chat/conversations'))).json()); } catch { /* the list stays empty */ }
    if (box.hidden) return;
    const pid = this.project?.()?.id;
    const mine = list.filter((c) => c.project && c.project === pid), other = list.filter((c) => !mine.includes(c));
    const row = (c) => `<div class="ai-conv ${c.id === current ? 'on' : ''}" data-id="${escapeHtml(c.id)}">
        <div class="ai-conv-text"><b data-no-i18n>${escapeHtml(c.title || '…')}</b>
        <span class="ai-conv-when">${escapeHtml(when(c.updated || c.created))} · ${escapeHtml(tn('{n} messages', c.messages))}${c.project !== pid && c.project_name ? ` · <span data-no-i18n>${escapeHtml(c.project_name)}</span>` : ''}</span></div>
        <button type="button" class="mini ai-conv-x" title="${escapeHtml(t('Delete this conversation'))}">✕</button></div>`;
    box.innerHTML = !list.length ? `<div class="ai-conv-none">${escapeHtml(t('No earlier conversations yet.'))}</div>`
      : `${mine.length ? `<div class="ai-conv-h">${escapeHtml(t('This project'))}</div>${mine.map(row).join('')}` : ''}
         ${other.length ? `<div class="ai-conv-h">${escapeHtml(t(mine.length ? 'Other projects' : 'Earlier conversations'))}</div>${other.map(row).join('')}` : ''}`;
    for (const r of box.querySelectorAll('.ai-conv')) {
      r.addEventListener('click', async (e) => {
        if (e.target.closest('.ai-conv-x')) {
          if (!confirm(t('Delete this conversation? It cannot be brought back.'))) return;
          await fetch(`/api/chat/conversations/${encodeURIComponent(r.dataset.id)}`, { method: 'DELETE' });
          this.showConvs(true);
          return;
        }
        if (this.busy) { this.toast(t('Wait until Claude has answered (or Stop it) first.'), 'warning'); return; }
        this.showConvs(false);
        await this.openConv(r.dataset.id);
      });
    }
  }

  /** A kept conversation back in this chat (its messages replayed by the server) — the next message goes on with it. */
  async openConv(id) {
    try {
      const res = await fetch('/api/chat/open', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id, client: CLIENT }) });
      if (!res.ok) throw new Error((await res.json()).error || res.statusText);
      return true;
    } catch (e) {
      if (session.get(CONV_KEY) === `${CLIENT}|${id}`) session.set(CONV_KEY, null);
      this.toast(e.message, 'error');
      return false;
    }
  }

  async checkStatus() {
    try {
      const s = await (await fetch(withClient('/api/chat/status'))).json();
      this.setStatus(s.claude ? (s.running ? 'Claude Code connected' : 'Claude Code ready — send a message to start') : 'Claude Code not found',
        s.claude ? '' : 'err');
      this.setBusy(s.busy);
      // a reload after the app restarted: this window's conversation back (the server no longer has it in memory)
      const [kc, keep] = (session.get(CONV_KEY) || '').split('|'); // (this window's: a new window opened from here has its own chat)
      if (s.conversation) { this.conv = s.conversation; this.renderConv(); } else if (keep && kc === CLIENT && !s.busy) this.openConv(keep);
      await this.showAccess(false);
    } catch { this.setStatus('The app server is not reachable', 'err'); }
  }

  // ------------------------------------------------------------------ access: set up the AI at any time (auto3d/ai_access.py)
  /** The set-up screen when the AI cannot run yet (Claude Code not installed, not signed in, a refused key) — or
   *  always (force: 🔑 Access) to change the key or sign out. It follows a sign-in by itself; the chat comes back once
   *  it works, without a restart. */
  async showAccess(force, why = '') {
    let s;
    try { s = await (await fetch('/api/ai/access')).json(); } catch { return; }
    this.access = s;
    const open = force || s.state !== 'ok' || !!why;
    const box = this.$('.ai-access');
    box.hidden = !open;
    this.log.hidden = open;
    this.$('.ai-form').hidden = open;
    this.root.classList.toggle('ai-setup', open);
    clearTimeout(this.accessTimer);
    if (!open) return;
    if (s.state !== 'ok') this.setStatus(s.state === 'no_claude' ? 'Claude Code not found' : 'The AI is not set up yet', 'warn');
    box.innerHTML = this.accessHtml(s, why);
    this.wireAccess(box, s);
    // signing in (a browser page) or installing: look again every 2 s until it works
    if (s.state !== 'ok' && (s.logging_in || this.waitingLogin)) this.accessTimer = setTimeout(() => this.showAccess(false, why), 2000);
    if (s.state === 'ok' && this.waitingLogin) { this.waitingLogin = false; this.toast('The AI is connected — you can write to Claude now.', 'success'); this.showAccess(false); }
  }

  accessHtml(s, why) {
    const link = (url, text) => `<a href="${url}" target="_blank" rel="noopener">${text}</a>`;
    const msg = why || (s.state === 'invalid' ? 'The API key was refused (wrong, revoked or expired). Enter another one or sign in with your Claude account.' : '');
    let html = `<h3>Set up the AI assistant</h3>
      <p>The rest of the app works without it. The assistant is Claude (by Anthropic) — it needs Claude Code on this computer and a Claude account or an API key. You can set it up now or any time later, without restarting.</p>`;
    if (msg) html += `<p class="ai-acc-msg err">${escapeHtml(msg)}</p>`;
    if (s.state === 'no_claude') {
      return `${html}<p class="ai-acc-msg warn">Claude Code is not installed on this computer — the assistant runs through it.</p>
        <ol class="ai-acc-steps"><li><span>Install it: open PowerShell and run this command (no administrator rights needed):</span>
          <div><code data-no-i18n>${escapeHtml(s.install_cmd)}</code></div>${link(s.links.install, 'Instructions: claude.com/claude-code')}</li>
        <li>Then click Check again — no restart needed.</li></ol>
        <div class="ai-acc-row"><button type="button" class="btn small primary ai-recheck">Check again</button></div>`;
    }
    if (s.state === 'ok') {
      const who = s.method === 'key' ? `an API key (…${escapeHtml(s.key_end || '')})` : `the Claude account ${escapeHtml(s.email || '')}`;
      html += `<p class="ai-acc-msg ok">Connected through ${who}.</p>
        <div class="ai-acc-row"><button type="button" class="btn small primary ai-back">Back to the chat</button>
        <button type="button" class="btn small ai-logout">${s.method === 'key' ? 'Sign out / change the key' : 'Sign out'}</button></div>`;
      if (s.method !== 'key') return html;
    }
    if (s.state !== 'ok') {
      html += `<div class="ai-way"><b>Claude account</b> <span class="hint">(Claude Pro or Max subscription)</span>
          <div class="ai-acc-row"><button type="button" class="btn small primary ai-signin">Sign in with Claude</button>
          ${link(s.links.register, 'No account? Register at claude.ai')}</div>
          ${s.logging_in || this.waitingLogin ? '<p class="hint ai-acc-wait">Finish the sign-in in the window and the browser page that opened — this screen updates by itself.</p>' : ''}</div>`;
    }
    html += `<div class="ai-way"><b>API key</b> <span class="hint">(pay per use, from the Anthropic Console)</span>
        <div class="ai-acc-row"><input type="password" class="ai-keyin" placeholder="sk-ant-…" autocomplete="off" spellcheck="false" data-no-i18n>
        <button type="button" class="btn small ai-usekey">Use this key</button></div>
        <div>${link(s.links.console, 'Get a key at console.anthropic.com')}</div>
        <div class="hint">The key is kept encrypted for your Windows user only and is only ever sent to Anthropic.</div></div>`;
    if (s.state !== 'ok' && s.state !== 'no_claude') html += '<div class="ai-acc-row"><button type="button" class="btn small ai-recheck">Check again</button></div>';
    return html;
  }

  wireAccess(box, s) {
    const on = (sel, fn) => box.querySelector(sel)?.addEventListener('click', fn);
    const post = async (url, body) => {
      const res = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) });
      const out = await res.json();
      if (!res.ok) throw new Error(out.error || res.statusText);
      return out;
    };
    on('.ai-recheck', () => this.showAccess(false));
    on('.ai-back', () => this.showAccess(false));
    on('.ai-signin', async () => {
      try { await post('/api/ai/login'); this.waitingLogin = true; this.showAccess(true); } catch (e) { this.toast(e.message, 'error'); }
    });
    const useKey = async () => {
      const key = box.querySelector('.ai-keyin').value.trim();
      if (!key) return;
      const btn = box.querySelector('.ai-usekey');
      btn.disabled = true;
      btn.textContent = 'Checking…';
      try {
        const r = await post('/api/ai/key', { key });
        this.toast(r.checked ? 'The key works — you can write to Claude now.' : 'The key is kept, but it could not be checked now (no connection?).', r.checked ? 'success' : 'warning');
        this.showAccess(false);
      } catch (e) { this.showAccess(true, e.message); }
    };
    on('.ai-usekey', useKey);
    box.querySelector('.ai-keyin')?.addEventListener('keydown', (e) => { if (e.key === 'Enter') useKey(); });
    on('.ai-logout', async () => {
      const claude = s.method !== 'key';
      if (claude && !confirm(t('Sign Claude Code out on this computer? (Also its use outside this app.)'))) return;
      try { await post('/api/ai/logout', { claude }); this.showAccess(true); } catch (e) { this.toast(e.message, 'error'); }
    });
  }

  setStatus(text, cls = '') {
    const el = this.$('.ai-status');
    el.textContent = text;
    el.className = `ai-status ${cls}`;
  }

  setBusy(on) {
    this.busy = on;
    this.$('.ai-stop').hidden = !on;
    this.$('.ai-form button[type=submit]').disabled = on;
    this.root.classList.toggle('ai-busy', on); // (not 'busy': that is the floating badge's style)
  }

  updateUndo() { this.$('.ai-undo').disabled = !this.canUndo(); }

  /** The AI asks (its tool ask_user): the question with its options as buttons — its recommended one first (★); a
   *  click answers. The answers go as the next message once every open question has one ("✎ Other…": typed). */
  ask({ question, options = [], recommended = 0 }) {
    const opts = options.map((o, i) => ({ ...(typeof o === 'string' ? { label: o } : o), rec: i === recommended }));
    opts.sort((a, b) => b.rec - a.rec);
    const card = this.bubble('ask', `<div class="ai-q" data-no-i18n>${escapeHtml(question)}</div><div class="ai-opts">${opts.map((o, i) => `<button type="button" class="ai-opt ${o.rec ? 'rec' : ''}" data-i="${i}">
        <b data-no-i18n>${escapeHtml(o.label)}</b>${o.rec ? ' <span class="ai-rec">★ recommended</span>' : ''}${o.description ? `<span class="ai-opt-d" data-no-i18n>${escapeHtml(o.description)}</span>` : ''}</button>`).join('')}
      <button type="button" class="ai-opt other" data-i="other">✎ Other…</button></div>`);
    card.question = question;
    this.pendingAsks = [...(this.pendingAsks || []), card];
    for (const b of card.querySelectorAll('.ai-opt')) {
      b.addEventListener('click', () => {
        if (card.answered) return;
        card.classList.add('done');
        b.classList.add('on');
        if (b.dataset.i === 'other') { // typed in the box: the open questions go with it
          card.answered = '…';
          const ta = this.$('textarea');
          ta.value = `${this.askText()}${ta.value ? '\n' : ''}${question} → `;
          this.pendingAsks = [];
          ta.focus();
          return;
        }
        card.answered = opts[+b.dataset.i].label;
        if (this.pendingAsks.some((c) => !c.answered)) return; // more to answer
        const text = this.askText();
        this.pendingAsks = [];
        const go = () => { if (this.busy) { setTimeout(go, 300); return; } this.$('textarea').value = text; this.send(); }; // (after its turn)
        go();
      });
    }
    this.toBottom();
  }

  /** The answered questions as the message. */
  askText() { return (this.pendingAsks || []).filter((c) => c.answered && c.answered !== '…').map((c) => `${c.question} → ${c.answered}`).join('\n'); }

  async addPhotos(files) {
    for (const f of [...files]) {
      if (this.photos.length >= MAX_PHOTOS) { this.toast(`At most ${MAX_PHOTOS} photos per message.`, 'warning'); break; }
      try {
        this.photos.push({ name: f.name || 'photo.png', data: await photoData(f) });
      } catch { this.toast(`${f.name} is not a photo (PNG, JPG, WEBP or GIF).`, 'error'); }
    }
    this.renderPhotos();
    this.$('textarea').focus();
  }

  renderPhotos() {
    const box = this.$('.ai-photos');
    box.hidden = !this.photos.length;
    box.innerHTML = '';
    this.photos.forEach((ph, i) => {
      const d = document.createElement('div');
      d.className = 'ai-thumb';
      d.title = ph.name;
      d.innerHTML = '<img alt=""><button type="button" class="ai-thumb-x" title="Remove this photo">✕</button>';
      d.querySelector('img').src = ph.data;
      d.querySelector('button').addEventListener('click', () => { this.photos.splice(i, 1); this.renderPhotos(); });
      box.appendChild(d);
    });
  }

  async send() {
    const ta = this.$('textarea');
    let text = ta.value.trim();
    if ((!text && !this.photos.length && !this.recOn) || this.busy) return;
    if (this.access && this.access.state !== 'ok') { this.showAccess(true); return; } // (set it up first: the typed text stays)
    const photos = this.photos;
    if (this.recOn) { text = `${text || t('Look at what I did.')}

${recorder.forChat()}`; this.recOn = false; } // (⏺ the recording with it)
    ta.value = '';
    this.photos = [];
    this.renderPhotos();
    this.setBusy(true);
    try {
      const res = await fetch('/api/chat/send', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text, photos, client: CLIENT, project: this.project?.() || null }) });
      if (!res.ok) throw new Error((await res.json()).error || res.statusText);
    } catch (e) {
      this.setBusy(false);
      this.note(e.message, 'err');
    }
  }

  connect() {
    this.es = new EventSource(withClient('/api/chat/events'));
    this.es.onmessage = (m) => {
      const ev = JSON.parse(m.data);
      if (ev.seq <= this.lastSeq) {
        if (ev.seq !== 1 || this.lastSeq <= 1) return; // replayed history we already show
        this.clear();                                   // the server restarted: start over
      }
      this.lastSeq = ev.seq;
      this.handle(ev);
    };
  }

  clear() {
    this.log.innerHTML = '';
    this.current = null;
    this.lastSeq = 0;
  }

  bubble(cls, html) {
    this.log.querySelector('.ai-empty')?.remove();
    const d = document.createElement('div');
    d.className = `ai-msg ${cls}`;
    d.innerHTML = html;
    const follow = this.atBottom();
    this.log.appendChild(d);
    if (follow || cls === 'user') this.toBottom();
    return d;
  }

  /** Whether the log shows its end — new text then keeps it there; scrolled up to read, it stays put. */
  atBottom() { return this.log.scrollHeight - this.log.scrollTop - this.log.clientHeight < 40; }

  toBottom() { this.log.scrollTop = this.log.scrollHeight; }

  note(text, cls = '') { this.bubble(`note ${cls}`, escapeHtml(text)); }

  assistant() {
    if (!this.current) {
      this.current = this.bubble('assistant', '');
      this.current.raw = '';
    }
    return this.current;
  }

  handle(ev) {
    switch (ev.type) {
      case 'reset':
        this.clear();
        this.setBusy(false);
        this.setStatus('New chat');
        break;
      case 'conv': // the conversation on screen (id null: a new one) — kept for a reload after a restart
        this.conv = ev.id ? ev : null;
        session.set(CONV_KEY, ev.id && `${CLIENT}|${ev.id}`);
        this.renderConv();
        if (ev.opened) this.setStatus('Claude Code ready — send a message to start');
        if (ev.opened) this.note(`${t('Earlier conversation from')} ${when(ev.created)} — ${t('write to go on with it.')}`);
        break;
      case 'note': // the server's: a new Claude session got the conversation in short
        if (ev.key === 'summary') this.note(t('Claude\'s earlier session could not be resumed — a new one got a short summary of this conversation.'));
        else if (ev.text) this.note(ev.text);
        break;
      case 'user':
        this.current = null;
        this.turnPrompt = ev.text || '';
        this.bubble('user', `${(ev.photos || []).map((ph) => `<a href="${escapeHtml(ph.url)}" target="_blank" title="${escapeHtml(ph.name)}"><img class="ai-msg-photo" src="${escapeHtml(ph.url)}" alt=""></a>`).join('')}${escapeHtml(ev.text).replace(/\n/g, '<br>')}`);
        if (!ev.old) this.setBusy(true); // (a kept conversation's message, shown again: no turn runs)
        if (this.conv && !this.conv.title) { this.conv.title = (ev.text || '').trim().split('\n')[0].slice(0, 80); this.renderConv(); }
        break;
      case 'status':
        this.setStatus(ev.text);
        break;
      case 'ready':
        this.setStatus(`Claude Code connected${ev.model ? ` · ${ev.model}` : ''}${ev.mcp !== 'connected' ? ` · app tools: ${ev.mcp}` : ''}`, ev.mcp === 'connected' ? 'ok' : 'warn');
        break;
      case 'turn':
        break;
      case 'delta': {
        const b = this.assistant();
        const follow = this.atBottom();
        b.raw += ev.text;
        b.innerHTML = md(b.raw);
        if (follow) this.toBottom();
        break;
      }
      case 'text': {
        // the complete text block (also when partial messages were not streamed)
        const b = this.assistant();
        if (!b.raw.trim()) { b.raw = ev.text; b.innerHTML = md(b.raw); }
        this.current = null;
        break;
      }
      case 'tool_start':
        this.current = null;
        this.setStatus(`Claude is ${TOOL_LABEL[ev.name] || ev.name}…`);
        break;
      case 'tool': {
        const args = ev.input && Object.keys(ev.input).length ? ` <code>${escapeHtml(JSON.stringify(ev.input).slice(0, 160))}</code>` : '';
        this.lastTool = this.bubble('tool', `🔧 ${escapeHtml(TOOL_LABEL[ev.name] || ev.name)}${args}`);
        break;
      }
      case 'tool_result':
        if (ev.error && this.lastTool) {
          this.lastTool.classList.add('err');
          this.lastTool.title = ev.text;
        }
        this.updateUndo();
        break;
      case 'done':
        this.current = null;
        if (ev.old) { if (ev.error) this.note(ev.text || 'Claude stopped with an error.', 'err'); break; } // (a kept conversation's)
        this.setBusy(false);
        this.setStatus('Claude Code connected', 'ok');
        if (ev.error) this.note(ev.text || 'Claude stopped with an error.', 'err');
        if (ev.auth) this.showAccess(true, 'Claude refused the access — the key is wrong or expired, or you were signed out. Sign in again or enter another key.');
        this.updateUndo();
        this.onTurnDone?.({ prompt: this.turnPrompt });
        break;
      case 'exit':
        this.current = null;
        this.setBusy(false);
        if (ev.code) {
          this.setStatus('Claude Code stopped', 'warn');
          if (ev.stderr) this.note(ev.stderr, 'err');
          if (ev.auth) this.showAccess(true, 'Claude refused the access — the key is wrong or expired, or you were signed out. Sign in again or enter another key.');
        } else this.setStatus('Claude Code ready — send a message to start');
        break;
      default:
        break;
    }
  }
}
