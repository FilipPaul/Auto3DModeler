"""📚 The parts library: real parts (standard screws, bearings, SMC, SICK…) described as data, built into 3D models in the
browser (web/js/library/build.js). The app's own library is library/*.json; the user's own parts are
data/library/*.json next to the server (one file each), so the library can grow — saved from a 3D model, or written by
hand (the same format: see library/README.md).
"""
import json
import re
import time
from pathlib import Path

STEP_KINDS = ("revolve", "extrude")


class LibraryError(Exception):
    pass


def check_item(item: dict) -> list:
    """What is wrong with an item -> [messages] (empty: fine)."""
    bad = []
    if not isinstance(item, dict):
        return ["An item is an object."]
    if not re.match(r"^[A-Za-z0-9][\w.-]{0,79}$", str(item.get("id") or "")):
        bad.append("id: letters, digits, - _ . (it names the part).")
    if not str(item.get("name") or "").strip():
        bad.append("name is missing.")
    if not str(item.get("category") or "").strip():
        bad.append("category is missing (e.g. \"Fasteners / Screws\").")
    sizes = item.get("sizes")
    if sizes is not None and (not isinstance(sizes, dict) or not sizes):
        bad.append("sizes: an object of sizes, each one an object of its values.")
    shape, features = item.get("shape"), item.get("features")
    if not shape and not features:
        bad.append("shape (steps) or features (a fixed 3D model) is missing.")
    for k, step in enumerate(shape or []):
        if not isinstance(step, dict) or not any(s in step for s in STEP_KINDS):
            bad.append(f"shape step {k + 1}: revolve or extrude.")
    return bad


def _read(path: Path, source: str) -> list:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [{"_broken": f"{path.name}: {exc}"}]
    items = data.get("items") if isinstance(data, dict) and "items" in data else [data]
    out = []
    for it in items:
        if not isinstance(it, dict):
            continue
        out.append({**it, "source": source, "file": path.name, **({"problems": check_item(it)} if check_item(it) else {})})
    return out


MODELS = "models.json"  # the maker's real 3D models (STEP, in the blob store) attached to a choice of an item


def _models(user_dir: Path) -> dict:
    try:
        return json.loads((Path(user_dir) / MODELS).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def set_model(user_dir: Path, item_id: str, key: str, blob: str = None, file: str = "") -> dict:
    """Attach a real model (its blob, the file's name) to a choice (key 'size|length') of an item, or with no blob
    take it away -> that item's models."""
    if not re.match(r"^[A-Za-z0-9][\w.-]{0,79}$", str(item_id or "")) or not isinstance(key, str) or len(key) > 120:
        raise LibraryError("No such part.")
    if blob is not None and not re.match(r"^[0-9a-f]{64}$", str(blob)):
        raise LibraryError("The model is not a stored file.")
    models = _models(user_dir)
    mine = models.setdefault(item_id, {})
    if blob:
        mine[key] = {"blob": blob, "file": str(file or "model.step")[:200], "added": time.strftime("%Y-%m-%d")}
    else:
        mine.pop(key, None)
    if not mine:
        models.pop(item_id, None)
    Path(user_dir).mkdir(parents=True, exist_ok=True)
    (Path(user_dir) / MODELS).write_text(json.dumps(models, ensure_ascii=False, indent=1), encoding="utf-8")
    return models.get(item_id, {})


def load(app_dir: Path, user_dir: Path) -> dict:
    """Every item of the app's library and the user's -> {items (with the real models attached to them), broken
    (files that cannot be read)}."""
    items, broken, seen = [], [], set()
    for folder, source in ((Path(user_dir), "user"), (Path(app_dir), "app")):  # the user's first: same id wins
        if not folder.is_dir():
            continue
        for path in sorted(p for p in folder.glob("*.json") if p.name != MODELS):
            for it in _read(path, source):
                if "_broken" in it:
                    broken.append(it["_broken"])
                    continue
                if it["id"] in seen:
                    continue
                seen.add(it["id"])
                items.append(it)
    models = _models(user_dir)
    for it in items:
        if models.get(it["id"]):
            it["models"] = models[it["id"]]
    return {"items": items, "broken": broken}


def save_user_item(user_dir: Path, item: dict) -> dict:
    """Keep the user's own item (a new one, or one changed) as data/library/<id>.json -> the item."""
    problems = check_item(item)
    if problems:
        raise LibraryError(" ".join(problems))
    clean = {k: v for k, v in item.items() if k not in ("source", "file", "problems")}
    clean.setdefault("added", time.strftime("%Y-%m-%d"))
    user_dir = Path(user_dir)
    user_dir.mkdir(parents=True, exist_ok=True)
    (user_dir / f"{clean['id']}.json").write_text(json.dumps(clean, ensure_ascii=False, indent=1), encoding="utf-8")
    return {**clean, "source": "user", "file": f"{clean['id']}.json"}


def delete_user_item(user_dir: Path, item_id: str) -> None:
    if not re.match(r"^[A-Za-z0-9][\w.-]{0,79}$", str(item_id or "")):
        raise LibraryError("No such part.")
    path = Path(user_dir) / f"{item_id}.json"
    if not path.exists():
        raise LibraryError("Only your own parts can be deleted (the app's library stays).")
    path.unlink()
