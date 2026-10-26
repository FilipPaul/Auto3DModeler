// The AI chat: Claude Code (the user's own installation and sign-in) works on the open part through the
// app's MCP tools. The server relays each tool call to this page (long-poll), the page applies it like
// the user would (visible at once, undoable) and posts the result back. The chat itself streams from
// the server as Server-Sent Events.

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

/** Run tool calls from the server: handlers = {tool: async (args) => ({text, image?, error?, body?})}. */
export function startBridge(handlers) {
  let alive = true;
  // with several app tabs open the server sends the AI's tool calls to the one in use (visible)
  const client = Math.random().toString(36).slice(2);
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
        const res = await fetch(`/api/agent/poll?client=${client}&active=${active}`, { signal: poller.signal });
        if (res.status === 200) cmd = await res.json();
      } catch (e) {
        if (e.name !== 'AbortError') await new Promise((r) => setTimeout(r, 2000));
        continue;
      }
      if (!cmd) continue;
      let result = done.get(cmd.id);
      if (!result) try {
        const fn = handlers[cmd.cmd];
        result = fn ? await fn(cmd.args || {}) : { text: `The page does not know '${cmd.cmd}'.`, error: true };
        bridgeStats.calls++;
      } catch (e) {
        result = { text: `${cmd.cmd} failed: ${e.message || e}`, error: true };
      }
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
  turn_off_feature: 'turning a step off / on', prepare_print: 'preparing the print', set_material: 'setting the material', new_assembly: 'starting an assembly', suggest_fasteners: 'finding where fasteners fit', add_fasteners: 'adding fasteners',
  get_assembly: 'reading the assembly', insert_part: 'inserting a part', library_search: 'searching the parts library', library_add: 'adding a library part', check_collisions: 'checking for collisions', snap_faces: 'snapping parts together', place_part: 'placing a part', remove_from_assembly: 'taking a part out', get_guide: 'reading a guide', Skill: 'reading a guide',
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

export class ChatPanel {
  constructor(root, { toast, onUndo, canUndo, onTurnDone, onHistory }) {
    this.root = root;
    this.toast = toast;
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
          <button class="mini ai-new" title="Start a new conversation">New chat</button>
        </span>
      </div>
      <div class="ai-log"><div class="ai-empty">
        <p><b>Describe what you want</b> — Claude works on the part in the app: opens drawings, traces pictures, sets
        sizes, adds holes, text and objects, checks the printer and exports.</p>
        <p><b>3D models and assemblies</b> too — it sketches, extrudes, drills, rounds and puts parts together.</p>
        <p class="hint">e.g. “Make a 90 mm cookie cutter from C:\\pics\\star.png with a hanging hole” · “Add a 5 mm hole 8 mm from the top”
        · “Engrave my name on the flange”.</p>
        <p class="hint">“Make a 60 × 40 × 5 mm plate with four Ø4 holes 6 mm from the corners and rounded edges” · “Put the pin into
        the hole of the plate”.</p>
        <p class="hint">📎 Attach a photo (or paste / drop it here) — “Make a cookie cutter from this, 90 mm wide”.</p>
        <p class="hint">Runs on your own Claude Code sign-in (Claude subscription or API key) — the app only gives Claude its part tools.</p>
      </div></div>
      <form class="ai-form">
        <div class="ai-photos" hidden></div>
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
    this.$('.ai-stop').addEventListener('click', () => fetch('/api/chat/stop', { method: 'POST' }));
    this.$('.ai-new').addEventListener('click', () => fetch('/api/chat/reset', { method: 'POST' }));
    this.$('.ai-undo').addEventListener('click', () => this.onUndo());
    this.$('.ai-hist').addEventListener('click', () => onHistory?.());
    this.updateUndo();
    this.checkStatus();
    this.connect();
  }

  async checkStatus() {
    try {
      const s = await (await fetch('/api/chat/status')).json();
      this.setStatus(s.claude ? (s.running ? 'Claude Code connected' : 'Claude Code ready — send a message to start') : 'Claude Code not found',
        s.claude ? '' : 'err');
      if (!s.claude) this.note('Claude Code is not installed (or not found). Install it from claude.com/claude-code and sign in once; or set AUTO3D_CLAUDE to the path of claude.exe and restart the app.', 'err');
      this.setBusy(s.busy);
    } catch { this.setStatus('The app server is not reachable', 'err'); }
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
    const text = ta.value.trim();
    if ((!text && !this.photos.length) || this.busy) return;
    const photos = this.photos;
    ta.value = '';
    this.photos = [];
    this.renderPhotos();
    this.setBusy(true);
    try {
      const res = await fetch('/api/chat/send', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text, photos }) });
      if (!res.ok) throw new Error((await res.json()).error || res.statusText);
    } catch (e) {
      this.setBusy(false);
      this.note(e.message, 'err');
    }
  }

  connect() {
    this.es = new EventSource('/api/chat/events');
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
      case 'user':
        this.current = null;
        this.turnPrompt = ev.text || '';
        this.bubble('user', `${(ev.photos || []).map((ph) => `<a href="${escapeHtml(ph.url)}" target="_blank" title="${escapeHtml(ph.name)}"><img class="ai-msg-photo" src="${escapeHtml(ph.url)}" alt=""></a>`).join('')}${escapeHtml(ev.text).replace(/\n/g, '<br>')}`);
        this.setBusy(true);
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
        this.setBusy(false);
        this.setStatus('Claude Code connected', 'ok');
        if (ev.error) this.note(ev.text || 'Claude stopped with an error.', 'err');
        this.updateUndo();
        this.onTurnDone?.({ prompt: this.turnPrompt });
        break;
      case 'exit':
        this.current = null;
        this.setBusy(false);
        if (ev.code) {
          this.setStatus('Claude Code stopped', 'warn');
          if (ev.stderr) this.note(ev.stderr, 'err');
        } else this.setStatus('Claude Code ready — send a message to start');
        break;
      default:
        break;
    }
  }
}
