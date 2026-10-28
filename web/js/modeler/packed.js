// A rebuilt part as one binary message (auto3d/modeler/packed.py): a JSON header and the meshes' arrays as they are —
// viewed as Float32Array / Uint32Array, nothing decoded (a big board: 88 -> 80 MB, no base64 to undo).

const TYPES = { f32: Float32Array, u32: Uint32Array, u8: Uint8Array };

/** POST /api/model/rebuild {part, rid, what} -> {res, r}: the result as from JSON, its meshes' positions / face_ids typed
 *  arrays. An error or a Cancel comes as JSON and is read as JSON. what: the part's name (the ⚙ jobs list; else the tab's). */
export async function fetchRebuild(part, rid, what) {
  const res = await fetch('/api/model/rebuild', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ part, rid, bin: true, ...(what ? { what } : {}) }) });
  const binary = (res.headers.get('Content-Type') || '').startsWith('application/octet-stream');
  return { res, r: binary ? unpack(await res.arrayBuffer()) : await res.json() };
}

/** The message -> the result (the arrays put back where they were). */
export function unpack(buf) {
  const dv = new DataView(buf);
  if (dv.getUint32(0) !== 0x4133444d) throw new Error('Not a packed model.'); // "A3DM"
  const n = dv.getUint32(4, true), base = 8 + n;
  const { arrays, result } = JSON.parse(new TextDecoder().decode(new Uint8Array(buf, 8, n)));
  for (const a of arrays) {
    let o = result;
    for (const k of a.at.slice(0, -1)) o = o[k];
    const T = TYPES[a.type];
    o[a.at[a.at.length - 1]] = new T(buf, base + a.off, a.n / T.BYTES_PER_ELEMENT);
  }
  return result;
}
