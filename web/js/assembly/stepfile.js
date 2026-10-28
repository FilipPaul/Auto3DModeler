// STEP assemblies — how SolidWorks, CATIA and Solid Edge exchange them (their own files are closed): a STEP that holds
// an assembly tree opens as parts + assemblies (a part placed several times is one part with several instances,
// sub-assemblies nested, the file's names and colours, exact placements); an assembly goes back out as such a tree
// (/api/assembly/export/step {tree}).
import { t } from '../i18n.js';
import { choose } from '../choose.js';

const t2 = (text, vars) => t(text).replace(/\{(\w+)\}/g, (_, k) => vars[k]);
const BIG = 150; // more parts + sub-assemblies than this (an ECAD board holds hundreds): one body is the first choice

/** Does the STEP (/api/model/import's answer) hold an assembly? */
export const hasTree = (r) => !!r?.structure && (r.structure.parts > 1 || r.structure.placements > 1);

/** A STEP with an assembly tree: ask how to open it -> 'assembly' | 'body' | null (cancelled). A plain one: 'body'. */
export function askHowToOpen(r) {
  if (!hasTree(r)) return Promise.resolve('body');
  const s = r.structure, big = s.parts + s.subs > BIG;
  return choose(t2('{name} is an assembly: {parts} different parts placed {placements} times, {subs} sub-assemblies.', { name: r.name, ...s }), [
    { value: 'assembly', label: 'Open as an assembly', hint: 'a part per part, placed as in the file', primary: !big },
    { value: 'body', label: 'Open as one body', hint: 'one solid to build on', primary: big },
  ]);
}

/** The file's tree (made on the server: a STEP blob per part) -> new project parts: a 3D model per part (one `solid`
 *  step), an assembly per sub-assembly (in the background) -> {name, data: {instances, light?}} of the top assembly.
 *  hooks: {addModelPart(name, data) -> id, addAssembly(name, data) -> id}. */
export function addTree(tree, hooks, fallbackName) {
  const ids = {};
  for (const [k, p] of Object.entries(tree.parts)) {
    ids[k] = hooks.addModelPart(p.name, { features: [{ id: 'F1', type: 'solid', name: p.name, blob: p.blob, file: `${p.name}.step`, op: 'add' }] });
  }
  // a big tree (a board: hundreds of parts): every part 🪶 simplified — quick to show; full data a click away (Look)
  const big = Object.keys(tree.parts).length + Object.keys(tree.assemblies).length > BIG;
  const light = big ? { light: Object.fromEntries(Object.values(ids).map((id) => [id, true])) } : {};
  const doc = (a) => ({ instances: a.instances.filter((i) => ids[i.ref]).map((i, k) => ({ id: `I${k + 1}`, part: ids[i.ref], matrix: i.matrix,
    ...(i.colour ? { colour: i.colour } : {}), ...(k ? {} : { fixed: true }) })), ...light }); // (the first part fixed in place, as on insert)
  // sub-assemblies before the ones that hold them
  const done = new Set([tree.root]), order = [];
  const visit = (k) => {
    for (const i of tree.assemblies[k]?.instances || []) {
      if (tree.assemblies[i.ref] && !done.has(i.ref)) { done.add(i.ref); visit(i.ref); order.push(i.ref); }
    }
  };
  visit(tree.root);
  for (const k of order) ids[k] = hooks.addAssembly(tree.assemblies[k].name, doc(tree.assemblies[k]));
  const root = tree.assemblies[tree.root];
  return { name: root.name || fallbackName, data: doc(root) };
}

/** How many parts / sub-assemblies a tree made, for the message. */
export const treeSize = (tree) => ({ parts: Object.keys(tree.parts).length, subs: Object.keys(tree.assemblies).length - 1,
  placements: Object.values(tree.assemblies).reduce((n, a) => n + a.instances.filter((i) => tree.parts[i.ref]).length, 0) });
