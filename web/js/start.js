// The start screen: a project with no part — or with every tab closed — shows the four ways to begin (✏ New part,
// 📂 Open a file, 🎬 Demo, ✨ Ask the AI) big in the middle, and nothing else; the panels of a workspace come with the
// first part. A file dropped anywhere in the window opens (as from 📂 Open). No tour: the four cards say it.

const $ = (id) => document.getElementById(id);

/** hooks: {project (parts.js Project), newPart(), openFiles(files), demos(), askAI(), onChange(on)} */
export function initStart(hooks) {
  const el = $('startScreen');
  if (!el) return { update() {} };
  const run = { new: () => hooks.newPart(), open: () => $('anyInput').click(), demo: () => hooks.demos(), ai: () => hooks.askAI() };
  for (const b of el.querySelectorAll('[data-start]')) b.addEventListener('click', () => run[b.dataset.start]());
  $('anyInput').addEventListener('change', (e) => {
    const files = [...e.target.files];
    e.target.value = '';
    if (files.length) hooks.openFiles(files);
  });
  // ←→ / ↑↓ between the cards, Enter runs one (a button's own)
  el.addEventListener('keydown', (e) => {
    const cards = [...el.querySelectorAll('.st-card')], i = cards.indexOf(document.activeElement);
    const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key];
    if (!step || i < 0) return;
    e.preventDefault();
    cards[(i + step + cards.length) % cards.length].focus();
  });

  const update = () => {
    const p = hooks.project, on = !p.parts.length || !!p.none;
    const b = document.body.classList, was = b.contains('start-open');
    b.toggle('start-open', on);
    b.toggle('start-fresh', !p.parts.length); // (no project tree to show beside it)
    if (on !== was) hooks.onChange?.(on);
  };
  window.addEventListener('a3d:changed', update);
  update();
  return { update };
}

/** A file dragged over the window: a dashed frame says it opens; dropped where nothing else takes it (a view, the
 *  chat, the assembly … take theirs first): opened. open(files, {shift}). */
export function initWindowDrop(open) {
  let depth = 0;
  const files = (e) => [...(e.dataTransfer?.types || [])].includes('Files');
  const mark = (on) => document.body.classList.toggle('file-over', on);
  window.addEventListener('dragenter', (e) => { if (files(e)) { depth++; mark(true); } });
  window.addEventListener('dragleave', (e) => { if (files(e) && --depth <= 0) { depth = 0; mark(false); } });
  window.addEventListener('dragover', (e) => { if (files(e)) e.preventDefault(); }); // (a drop anywhere is allowed)
  window.addEventListener('drop', (e) => {
    depth = 0;
    mark(false);
    if (!files(e) || e.defaultPrevented) return; // (taken already: the quick part's view, the assembly's)
    e.preventDefault(); // (never the browser's own: it would leave the app to show the file)
    const list = [...e.dataTransfer.files];
    if (list.length) open(list, { shift: e.shiftKey });
  });
}
