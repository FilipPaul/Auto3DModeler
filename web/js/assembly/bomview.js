// 📋 BOM: the bill of materials of an assembly in a window over the page — Summary (a row per part, its total from
// every level) or Structured (the tree: assembly -> sub-assemblies -> parts, the quantity in each parent and the running
// total; ▾ / ▸ folds a sub-assembly), for the open assembly or any sub-assembly in it; ⬇ CSV, ⬇ Excel (.xlsx, when the
// server has openpyxl). The numbers are the drawing set's positions (the balloons').
import { t } from '../i18n.js';
import { bomOf, bomTable, bomCsv } from './bom.js';

const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const t2 = (text, vars) => t(text).replace(/\{(\w+)\}/g, (_, k) => vars[k]);
const num = (v, d = 1) => (v === null || v === undefined || v === '' ? '—' : (+(+v).toFixed(d)).toLocaleString(undefined, { maximumFractionDigits: d }));
const KEY = 'a3d.bomMode';

let xlsxOk = null; // (asked once: does the server write Excel?)
async function canXlsx() {
  if (xlsxOk === null) { try { xlsxOk = !!(await (await fetch('/api/bom/xlsx')).json()).available; } catch { xlsxOk = false; } }
  return xlsxOk;
}

/** The BOM as an Excel workbook: both views, a sheet each -> a Blob (or throws the server's reason). */
export async function bomXlsx(ctx, aid, numbering, name) {
  const sheets = ['summary', 'structured'].map((mode) => {
    const tb = bomTable(bomOf(ctx, aid, { mode, numbering }), t);
    return { title: t(mode === 'summary' ? 'Summary' : 'Structured'), ...tb };
  });
  const res = await fetch('/api/bom/xlsx', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name, sheets }) });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).error || res.statusText);
  return res.blob();
}

/** Open the window. o: {ctx (bom.js), aid (the assembly), choices: [{id, name, depth}] (it and its sub-assemblies),
 *  numberingOf(aid) -> the assembly whose drawing set numbers it, download(blob, name), toast(text, kind)}. */
export function openBomWindow(o) {
  document.querySelector('.bom-back')?.remove();
  const back = document.createElement('div');
  back.className = 'choose-back bom-back';
  let aid = o.aid, mode = localStorage.getItem(KEY) === 'structured' ? 'structured' : 'summary';
  const folded = new Set();
  const close = () => { document.removeEventListener('keydown', onKey, true); back.remove(); };
  const onKey = (e) => { if (e.key === 'Escape') { e.stopPropagation(); close(); } };
  const bomNow = () => bomOf(o.ctx, aid, { mode, numbering: o.numberingOf(aid) });

  const render = async () => {
    const bom = bomNow(), name = o.ctx.partName(aid) || aid, structured = mode === 'structured';
    const head = structured ? ['Pos.', 'Name', 'Qty per parent', 'Total qty', 'Material', 'Mass each', 'Mass total', 'Maker', 'Part number', 'Make / buy']
      : ['Pos.', 'Name', 'Qty', 'Material', 'Mass each', 'Mass total', 'Maker', 'Part number', 'Make / buy'];
    // structured: the tree's lines, each with its path (part ids down to it) — a folded sub-assembly hides what is under it
    const lines = [];
    const walk = (nodes, depth, path, hidden) => {
      for (const n of nodes) {
        const key = `${path}/${n.part}`;
        if (!hidden) lines.push({ n, depth, key });
        if (n.children) walk(n.children, depth + 1, key, hidden || folded.has(key));
      }
    };
    if (structured) walk(bom.tree, 0, '', false);
    const how = (r) => (r.kind === 'assembly' ? `<span class="bom-asm">${esc(t('assembly'))}</span>` : `<span class="bom-${r.buy ? 'buy' : 'make'}">${esc(t(r.how))}</span>`);
    const cells = (r, depth = 0, key = '') => {
      const isAsm = r.kind === 'assembly', fold = isAsm ? `<button class="mini bom-fold" data-fold="${esc(key)}" title="${esc(t(folded.has(key) ? 'Show its parts' : 'Hide its parts'))}">${folded.has(key) ? '▸' : '▾'}</button>` : '<span class="bom-leaf"></span>';
      const nm = `<span class="bom-name" style="padding-left:${depth * 18}px">${structured ? fold : ''}${isAsm ? '◇ ' : ''}<span data-no-i18n>${esc(r.name)}</span></span>`;
      const tot = structured ? r.total : r.qty;
      return `<td class="bom-pos">${r.pos ?? ''}</td><td>${nm}</td>${structured ? `<td class="num">${r.qty}</td><td class="num"><b>${r.total}</b></td>` : `<td class="num"><b>${r.qty}</b></td>`}
        <td data-no-i18n>${esc(r.material || '')}</td><td class="num">${isAsm ? '' : `${num(r.mass_g, 2)}${r.mass_g === null ? '' : ' g'}`}</td>
        <td class="num">${isAsm || r.mass_g === null ? (isAsm ? '' : '—') : `${num(r.mass_g * tot, 1)} g`}</td>
        <td data-no-i18n>${esc(r.maker || '')}</td><td data-no-i18n>${esc(r.pn || '')}</td><td>${how(r)}</td>`;
    };
    const body = structured
      ? lines.map(({ n, depth, key }) => `<tr class="${n.kind === 'assembly' ? 'bom-sub' : ''}" data-depth="${depth}">${cells(n, depth, key)}</tr>`).join('')
      : bom.rows.map((r) => `<tr title="${esc(r.in.map((w) => (w.times > 1 ? `${w.assembly}: ${w.qty} × ${w.times}` : `${w.assembly}: ${w.qty}`)).join(' + '))}">${cells(r)}</tr>`).join('');
    const x = await canXlsx();
    back.innerHTML = `<div class="choose bom-win" role="dialog" aria-modal="true">
      <div class="bom-head"><b>📋 ${esc(t('Bill of materials'))}</b>
        ${o.choices.length > 1 ? `<select class="bom-of" title="${esc(t('The assembly whose BOM is shown — this one or any sub-assembly in it'))}">${o.choices.map((c) => `<option value="${esc(c.id)}"${c.id === aid ? ' selected' : ''} data-no-i18n>${'  '.repeat(c.depth)}${c.depth ? '◇ ' : ''}${esc(c.name)}</option>`).join('')}</select>` : `<span class="bom-title" data-no-i18n>${esc(name)}</span>`}
        <span class="seg bom-mode"><button class="${structured ? '' : 'on'}" data-mode="summary" title="${esc(t('One row per part: how many in all, from every level of the assembly'))}">${esc(t('Summary'))}</button><button class="${structured ? 'on' : ''}" data-mode="structured" title="${esc(t('The assembly tree: each sub-assembly with its parts, how many in each and in all'))}">${esc(t('Structured'))}</button></span>
        <button class="mini choose-x" data-a="close" title="${esc(t('Close'))}">✕</button></div>
      <p class="bom-sum">${esc(t2('{kinds} different part(s), {pieces} piece(s) in all', { kinds: bom.kinds, pieces: bom.pieces }))}${bom.mass_g ? ` · ${esc(t2('mass {m} g', { m: num(bom.mass_g, 1) }))}${bom.mass_unknown ? ` (${esc(t2('{n} without a mass', { n: bom.mass_unknown }))})` : ''}` : ''}</p>
      <div class="bom-scroll"><table class="bom-table ${structured ? 'bom-tree' : ''}"><thead><tr>${head.map((h, i) => `<th class="${(structured ? [0, 2, 3, 5, 6] : [0, 2, 4, 5]).includes(i) ? 'num' : ''}">${esc(t(h))}</th>`).join('')}</tr></thead>
        <tbody>${body || `<tr><td colspan="${head.length}" class="hint">${esc(t('No parts in it yet.'))}</td></tr>`}</tbody></table></div>
      <p class="hint bom-note">${esc(t(structured ? 'Qty per parent: how many in the assembly above it; Total qty: how many in all (multiplied through the levels).' : 'Pos. — the numbers of the drawing set\'s balloons. Hover a row: where its count comes from.'))}</p>
      <div class="row-actions"><button class="btn small primary" data-a="csv" title="${esc(t('The BOM as shown, for Excel (; separated)'))}">⬇ CSV</button>
        <button class="btn small" data-a="xlsx" ${x ? '' : 'disabled'} title="${esc(t(x ? 'Both views as sheets of one Excel workbook' : 'Excel needs the openpyxl package on the server — CSV only'))}">⬇ Excel (.xlsx)</button>
        ${x ? '' : `<span class="hint">${esc(t('Excel: not installed (openpyxl) — CSV only.'))}</span>`}</div></div>`;
    back.querySelector('[data-a=close]').addEventListener('click', close);
    back.querySelector('.bom-of')?.addEventListener('change', (e) => { aid = e.target.value; folded.clear(); render(); });
    for (const b of back.querySelectorAll('[data-mode]')) b.addEventListener('click', () => { mode = b.dataset.mode; localStorage.setItem(KEY, mode); render(); });
    for (const b of back.querySelectorAll('[data-fold]')) b.addEventListener('click', () => { const k = b.dataset.fold; if (folded.has(k)) folded.delete(k); else folded.add(k); render(); });
    back.querySelector('[data-a=csv]').addEventListener('click', async () => {
      const file = `${name} — ${t('BOM')}${structured ? ` (${t('structured')})` : ''}.csv`;
      if (await o.download(new Blob([bomCsv(bom, t)], { type: 'text/csv' }), file)) o.toast(t2('BOM saved: {n} line(s).', { n: bom.lines.length }), 'ok');
    });
    back.querySelector('[data-a=xlsx]').addEventListener('click', async () => {
      try {
        const blob = await bomXlsx(o.ctx, aid, o.numberingOf(aid), `${name} — ${t('BOM')}`);
        if (await o.download(blob, `${name} — ${t('BOM')}.xlsx`)) o.toast(t2('BOM saved: {n} line(s).', { n: bom.rows.length }), 'ok');
      } catch (e) { o.toast(e.message, 'error', 8000); }
    });
  };
  back.addEventListener('click', (e) => { if (e.target === back) close(); });
  document.addEventListener('keydown', onKey, true);
  document.body.appendChild(back);
  render();
  return { close, render, get aid() { return aid; }, get mode() { return mode; } };
}
