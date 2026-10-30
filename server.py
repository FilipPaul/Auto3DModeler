"""Auto3DModeler local web app.

Run:  python server.py   (then open http://127.0.0.1:5173)
"""
from __future__ import annotations

import argparse
import base64
import io
import re
import threading
import time
import uuid
import webbrowser
import zipfile
from pathlib import Path

import json
import queue

import cv2
import numpy as np
from flask import Flask, Response, jsonify, request, send_file, send_from_directory, stream_with_context

from auto3d import progress
from auto3d import timings
from auto3d.agent import ROUTE, ChatSession, Relay, find_claude
from auto3d.ai_history import HistoryError, delete_state, list_states, load_state, save_state
from auto3d import chat_history
from auto3d import library as parts_library
from auto3d import title_templates
from auto3d import autosave
from auto3d import versions
from auto3d import demos
from auto3d import animation
from auto3d.agent_tools import BROWSER_TOOLS, TOOL_NAMES
from auto3d.bend import bend_info, bend_solid
from auto3d.design import profile_polygon, trace_image
from auto3d.export import build_solid, mesh_payload, to_step, to_stl
from auto3d.extract import render_page_png
from auto3d.joints import joint_catalog
from auto3d.importers import DRAWING_FORMATS, MESH_FORMATS, ImportError_, dwg_to_dxf, read_dxf
from auto3d.meshpart import mesh_model, register, solve_mesh
from auto3d.mcp_server import OLDER_SERVER  # ("Unknown tool …: this app server is older than the tool list")
from auto3d.outline import add_objects, apply_shapes, detect_outlines, outline_from_mask, outline_model, preset_objects, solve_outline
from auto3d.modeler import status as modeler_status
from auto3d.modeler.worker import WORKER as MODEL_WORKER, KernelFailed, KernelUnavailable
from auto3d import printexact
from auto3d.printing import PrinterStore, assembly_text, bend_pieces, plan
from auto3d.project import ProjectError, migrate as migrate_project
from auto3d.sketch import build_model
from auto3d.solver import solve

ROOT = Path(__file__).parent
DATA = Path(__import__("os").environ.get("A3D_DATA") or ROOT / "data")  # the server's own data (A3D_DATA: e.g. a test server's)
LF = "\n"
WEB = ROOT / "web"
SAMPLE = ROOT / "initial draft.pdf"
printers = PrinterStore(DATA / "printers.json")

app = Flask(__name__, static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024  # big STEP files


@app.before_request
def _request_label():
    """What a request works on, for the jobs list: the page's request id (X-A3D-Req) and its part's name — the body's
    `what`, else the tab on screen (X-A3D-Tab, URL-encoded)."""
    from urllib.parse import unquote
    body = request.get_json(silent=True) if request.is_json else None
    what = (body or {}).get("what") if isinstance(body, dict) else None
    progress.begin_request(what or unquote(request.headers.get("X-A3D-Tab", "")) or None, request.headers.get("X-A3D-Req"))
    request.environ["a3d.t0"] = time.perf_counter()


@app.after_request
def _request_time(resp):
    """Each API request's time and size by its route (GET /api/timings)."""
    t0 = request.environ.get("a3d.t0")
    if t0 is not None and request.path.startswith("/api/") and request.url_rule is not None:
        # a streamed answer (the chat's events, a file): its header only — calculate_content_length() would read the
        # whole stream first, and the chat's never ends (nothing reached the page: the chat looked dead)
        size = resp.content_length if resp.is_streamed or resp.direct_passthrough else resp.calculate_content_length()
        timings.note(f"{request.method} {request.url_rule.rule}", (time.perf_counter() - t0) * 1000, size or 0)
    return resp


@app.get("/api/timings")
def api_timings():
    """How long the requests and the kernel's calls took since the start (?reset=1: and clear them)."""
    return jsonify(timings.report(reset=request.args.get("reset") == "1"))


@app.get("/")
def index():
    return send_from_directory(WEB, "index.html")


@app.get("/<path:path>")
def static_files(path):
    return send_from_directory(WEB, path)


def _solve_full(body):
    """Solve the sketch and build the 3D solid incl. design layers and bends.

    Returns (model, solution, final_solid, flat_solid, bender): the final solid is bent when bends
    apply; joints / splitting work on the flat solid and are bent afterwards.
    """
    model = body["model"]
    solid = final = bender = None
    if model.get("kind") == "outline":
        solution, solid = solve_outline(model, body.get("values"), body.get("layers"))
    elif model.get("kind") == "mesh":
        solution, solid = solve_mesh(model, body.get("values"), body.get("layers"))
    else:
        solution = solve(model, body.get("values"))
        if solution["ok"]:
            # 2D shapes change the drawn profile; extra 3D objects are booleaned onto the part —
            # their problems are reported like design-layer problems
            extra = []
            issue = lambda sev, msg, code="design", params=(): extra.append(
                {"severity": sev, "code": code, "message": msg, "params": list(params)})
            profile = profile_polygon(solution)
            if model.get("shapes"):
                profile = apply_shapes(profile, model["shapes"], issue)
                solution["_profile"] = profile
            if profile.is_empty:
                solution["issues"].append({"severity": "error", "code": "invalid_geometry", "params": [],
                                           "message": "The profile is empty after the 2D shapes were applied."})
                solution["ok"] = False
            else:
                solid = build_solid(solution, model["unit"], body.get("layers"))
                solution["object_regions"] = []
                solid = add_objects(solid, model.get("extras"), profile, issue, solution["object_regions"])
                solid.issues = solid.issues + extra
                solution["z_levels"] = list(solid.levels)
            solution.pop("_profile", None)
    if solid is not None:
        final, bender, bend_issues = bend_solid(solid, body.get("bends"), model["unit"])
        solution["design_issues"] = solid.issues + bend_issues
        solution["volume"] = final.volume()
        solution["z_range"] = final.z_range()
        solution["guides"] = solid.guide_rings()
        solution["design_ok"] = not any(i["severity"] == "error" for i in solution["design_issues"])
        if bender is not None:
            solution["bent"] = True
            solution["bends_info"] = bend_info(bender.ops, model["unit"])
            solution["bbox3"] = [*final.xy_bounds(), *final.z_range()]
            lift = solution["thickness"] * 1.002
            for a in solution["annotations"]:
                q = final.place([[*a["p1"], lift], [*a["p2"], lift]])
                a["p1_3d"], a["p2_3d"] = q[0].tolist(), q[1].tolist()
            x0, y0, x1, _ = solution["bbox"]
            q = final.place([[x1, y0, 0.0], [x1, y0, solution["thickness"]]])
            solution["thickness_3d"] = [q[0].tolist(), q[1].tolist()]
    return model, solution, final, solid, bender


def _pdf_data(pdf: bytes, page: int, filename: str) -> dict:
    try:
        model, pg, _doc = build_model(pdf, page)
    except Exception as exc:  # corrupt / encrypted / not a PDF
        raise ValueError(f"Could not read the PDF: {exc}") from exc
    model["source"] = filename
    preview = {"png": base64.b64encode(render_page_png(pg)).decode(), "width": pg.rect.width,
               "height": pg.rect.height}
    return {"model": model, "preview": preview}


def _parse(pdf: bytes, page: int, filename: str):
    try:
        return jsonify(_pdf_data(pdf, page, filename))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@app.post("/api/parse")
def api_parse():
    f = request.files.get("file")
    if f is None:
        return jsonify({"error": "No file uploaded."}), 400
    return _parse(f.read(), int(request.form.get("page", 0)), f.filename or "drawing.pdf")


@app.get("/api/sample")
def api_sample():
    if not SAMPLE.exists():
        return jsonify({"error": "Sample drawing not found."}), 404
    return _parse(SAMPLE.read_bytes(), 0, SAMPLE.name)


@app.post("/api/project/migrate")
def api_project_migrate():
    """Any project file -> version 3 (several parts); the browser opens what comes back."""
    try:
        return jsonify(migrate_project(request.get_json(force=True, silent=True)))
    except ProjectError as e:
        return jsonify({"error": str(e)}), 400


def _package_of(proj: dict, versions_of=None, thumbnail=None) -> tuple[bytes, list[str]]:
    """A project (Save project's JSON) -> the .a3d package (auto3d/package.py): its imported files from the blob store,
    🕘 the version history of the project `versions_of` (its autosave id) when given, its picture (a PNG data URL; none:
    a drawn box — a project of quick parts or drawings only)."""
    from auto3d import package
    from auto3d.modeler import blobs
    hist = versions.bundle(VERSIONS, versions_of) if versions_of else None
    return package.write(proj, blobs.get, hist or proj.get("versions"), _png_of(thumbnail) or _box_png())


def _png_of(url) -> bytes | None:
    """A PNG data URL -> its bytes (anything else: None)."""
    if isinstance(url, str) and url.startswith("data:image/png;base64,"):
        try:
            data = base64.b64decode(url.split(",", 1)[1], validate=True)
        except ValueError:
            return None
        return data if data[:8] == b"\x89PNG\r\n\x1a\n" else None
    return None


def _box_png(w=512, h=384) -> bytes:
    """The picture of a project with no 3D part to draw: a box in iso, outlined."""
    img = np.full((h, w, 3), (46, 38, 33), np.uint8)
    c, r = np.array([w / 2, h / 2]), min(w, h) * 0.2
    iso = lambda x, y, z: (c + r * np.array([(x - y) * 0.866, (x + y) * 0.5 - z])).astype(np.int32)
    top = [iso(-1, -1, 1), iso(1, -1, 1), iso(1, 1, 1), iso(-1, 1, 1)]
    left = [iso(-1, 1, 1), iso(1, 1, 1), iso(1, 1, -1), iso(-1, 1, -1)]
    right = [iso(1, -1, 1), iso(1, 1, 1), iso(1, 1, -1), iso(1, -1, -1)]
    for poly, col in ((top, (224, 139, 169)), (left, (170, 100, 125)), (right, (130, 75, 95))):
        cv2.fillPoly(img, [np.array(poly)], col, cv2.LINE_AA)
        cv2.polylines(img, [np.array(poly)], True, (250, 220, 230), 2, cv2.LINE_AA)
    return cv2.imencode(".png", img)[1].tobytes()


def _project_from(data: bytes) -> tuple[dict, dict | None]:
    """A project file's bytes (.a3d) -> (the project as version 3, its 🕘 version history or None); its imported files
    put into the blob store. Raises ValueError (package.PackageError, ProjectError) when it is no project."""
    from auto3d import package
    from auto3d.modeler import blobs
    got = package.load(data)
    return migrate_project(package.store(got, blobs.put)), got["versions"]


@app.post("/api/project/package")
def api_project_package():
    """{project, versions_of?, thumbnail?} -> the project file as Save project writes it: <name>.a3d (a ZIP)."""
    b = request.get_json(force=True, silent=True) or {}
    if not isinstance(b.get("project"), dict):
        return jsonify({"error": "No project."}), 400
    try:
        data, missing = _package_of(b["project"], b.get("versions_of"), b.get("thumbnail"))
    except versions.VersionError as e:
        return jsonify({"error": str(e)}), 400
    res = Response(data, mimetype="application/zip")
    res.headers["X-Missing-Files"] = str(len(missing))  # (imported files no longer in the store: left out)
    return res


@app.post("/api/project/open")
def api_project_open():
    """A project file's bytes (.a3d) -> {project (version 3), versions}: its imported files back in the blob store,
    binary — the browser opens what comes back."""
    data = request.get_data()
    try:
        proj, hist = _project_from(data)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"project": proj, "versions": hist})


DEMOS = ROOT / "demos"  # 🎬 ready-made projects (auto3d/demos.py): read-only, opened as a copy


@app.get("/api/demos")
def api_demos():
    return jsonify({"demos": demos.listing(DEMOS)})


@app.get("/api/demos/<name>")
def api_demo(name):
    from auto3d.modeler import blobs
    try:
        return jsonify(demos.load(DEMOS, name, blobs.put))
    except demos.DemoError as e:
        return jsonify({"error": str(e)}), 404


@app.get("/api/demos/<name>/thumb")
def api_demo_thumb(name):
    """A demo's picture (its .a3d's thumbnail.png) for its card."""
    try:
        data = demos.thumbnail(DEMOS, name)
    except demos.DemoError as e:
        return jsonify({"error": str(e)}), 404
    return Response(data, mimetype="image/png") if data else (jsonify({"error": "No picture."}), 404)


LIBRARY_APP = ROOT / "library"            # 📚 the app's parts library (auto3d/library.py)
LIBRARY_USER = DATA / "library"   # the user's own parts


@app.get("/api/library")
def api_library():
    return jsonify(parts_library.load(LIBRARY_APP, LIBRARY_USER))


@app.post("/api/library")
def api_library_save():
    """{item} -> the user's own part kept in data/library/."""
    body = request.get_json(force=True, silent=True) or {}
    try:
        return jsonify(parts_library.save_user_item(LIBRARY_USER, body.get("item")))
    except parts_library.LibraryError as e:
        return jsonify({"error": str(e)}), 400


@app.post("/api/library/model")
def api_library_model():
    """{item, key ('size|length'), blob (from /api/model/import), file} -> the maker's real model used for that choice;
    without blob: the drawn one again."""
    body = request.get_json(force=True, silent=True) or {}
    try:
        return jsonify({"models": parts_library.set_model(LIBRARY_USER, body.get("item"), body.get("key"), body.get("blob"), body.get("file", ""))})
    except parts_library.LibraryError as e:
        return jsonify({"error": str(e)}), 400


@app.delete("/api/library/<item_id>")
def api_library_delete(item_id):
    try:
        parts_library.delete_user_item(LIBRARY_USER, item_id)
    except parts_library.LibraryError as e:
        return jsonify({"error": str(e)}), 404
    return jsonify({"ok": True})


@app.get("/api/title-templates")
def api_title_templates():
    """The title-block templates of drawing sheets: the app's, then the user's (data/title_templates.json)."""
    return jsonify({"templates": title_templates.load(DATA)})


@app.post("/api/title-templates")
def api_title_template_save():
    """{template: {name, layout, hide, texts, logo, frame}} -> it kept (one of the same name replaced) + the list."""
    body = request.get_json(force=True, silent=True) or {}
    try:
        kept = title_templates.save(DATA, body.get("template"))
    except title_templates.TemplateError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"template": kept, "templates": title_templates.load(DATA)})


@app.delete("/api/title-templates/<path:name>")
def api_title_template_delete(name):
    try:
        title_templates.delete(DATA, name)
    except title_templates.TemplateError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"templates": title_templates.load(DATA)})


PROJECTS = DATA / "projects"  # autosave: the projects kept on the server (auto3d/autosave.py)


@app.post("/api/projects/<pid>")
def api_project_autosave(pid):
    """{project} -> kept as the project's latest state -> its meta."""
    body = request.get_json(force=True, silent=True) or {}
    try:
        return jsonify(autosave.save(PROJECTS, pid, body.get("project")))
    except autosave.AutosaveError as e:
        return jsonify({"error": str(e)}), 400
    except OSError as e:  # (the disk: the last kept state stays; the next autosave tries again)
        return jsonify({"error": str(e.strerror or e)}), 503


@app.post("/api/projects/<pid>/thumb")
def api_project_thumb_put(pid):
    """{thumbnail: a PNG data URL} -> kept as the kept project's picture (🕘 Recent projects, the start screen)."""
    png = _png_of((request.get_json(force=True, silent=True) or {}).get("thumbnail"))
    if not png:
        return jsonify({"error": "Not a PNG picture."}), 400
    try:
        return jsonify({"thumb": autosave.save_thumb(PROJECTS, pid, png)})
    except autosave.AutosaveError as e:
        return jsonify({"error": str(e)}), 404
    except OSError as e:
        return jsonify({"error": str(e.strerror or e)}), 503


@app.get("/api/projects/<pid>/thumb")
def api_project_thumb(pid):
    try:
        return send_file(autosave.thumb_path(PROJECTS, pid), mimetype="image/png", max_age=0)
    except autosave.AutosaveError as e:
        return jsonify({"error": str(e)}), 404


@app.get("/api/projects")
def api_projects_recent():
    return jsonify({"projects": autosave.recent(PROJECTS)})


@app.post("/api/projects-cleanup")
def api_projects_cleanup():
    """🧹 {keep: the project on screen, dry_run} -> {projects: [meta]} — the empty ones with default names (deleted
    unless dry_run)."""
    body = request.get_json(force=True, silent=True) or {}
    return jsonify({"projects": autosave.cleanup(PROJECTS, body.get("keep"), bool(body.get("dry_run")))})


@app.get("/api/projects/<pid>")
def api_project_load(pid):
    try:
        return jsonify(autosave.load(PROJECTS, pid))
    except autosave.AutosaveError as e:
        return jsonify({"error": str(e)}), 404


@app.delete("/api/projects/<pid>")
def api_project_forget(pid):
    try:
        autosave.delete(PROJECTS, pid)
        versions.drop(VERSIONS, pid)  # (its 🕘 versions too)
    except (autosave.AutosaveError, versions.VersionError) as e:
        return jsonify({"error": str(e)}), 404
    return jsonify({"ok": True})


VERSIONS = DATA / "versions"  # 🕘 the projects' versions, one content-addressed store each (auto3d/versions.py)


def _thumb_of(body):
    """A version's thumbnail sent as base64 JPEG (a data URL too) -> its bytes, or None."""
    t = body.get("thumb")
    if not isinstance(t, str) or not t:
        return None
    try:
        return base64.b64decode(t.split(",", 1)[-1], validate=True)
    except ValueError:
        raise versions.VersionError("The thumbnail is not a small JPEG picture.")


def _versions_call(fn):
    try:
        return jsonify(fn())
    except versions.VersionError as e:
        return jsonify({"error": str(e)}), 400
    except OSError as e:  # (the disk: nothing half written; tried again next time)
        return jsonify({"error": str(e.strerror or e)}), 503


@app.get("/api/versions/<pid>")
def api_versions_list(pid):
    """-> {current, variant, variants, versions (the newest first), base} — of ?variant= (default: the one on screen)."""
    return _versions_call(lambda: versions.versions(VERSIONS, pid, request.args.get("variant") or None,
                                                    request.args.get("all") == "1"))


@app.post("/api/versions/<pid>")
def api_versions_save(pid):
    """{project, label, auto, force, thumb (base64 JPEG), volumes {part id: mm³}} -> the version's manifest (same: true
    when not kept — nothing changed, or an automatic one too soon)."""
    b = request.get_json(force=True, silent=True) or {}
    return _versions_call(lambda: versions.save(VERSIONS, pid, b.get("project"), b.get("label") or "", bool(b.get("auto")),
                                                _thumb_of(b), b.get("volumes"), bool(b.get("force"))))


@app.get("/api/versions/<pid>/v/<vid>")
def api_versions_get(pid, vid):
    return _versions_call(lambda: versions.get(VERSIONS, pid, vid))


@app.get("/api/versions/<pid>/v/<vid>/thumb")
def api_versions_thumb(pid, vid):
    try:
        data = versions.thumb(VERSIONS, pid, vid)
    except versions.VersionError as e:
        return jsonify({"error": str(e)}), 404
    return Response(data, mimetype="image/jpeg", headers={"Cache-Control": "max-age=86400"})


@app.post("/api/versions/<pid>/v/<vid>/restore")
def api_versions_restore(pid, vid):
    """{project: the one on screen (kept first), thumb, volumes} -> {version, before, project}."""
    b = request.get_json(force=True, silent=True) or {}
    return _versions_call(lambda: versions.restore(VERSIONS, pid, vid, b.get("project"), _thumb_of(b), b.get("volumes")))


@app.post("/api/versions/<pid>/diff")
def api_versions_diff(pid):
    """{a, b: version ids or "current", project + volumes: the one on screen} -> what changed from a to b."""
    b = request.get_json(force=True, silent=True) or {}
    return _versions_call(lambda: versions.compare(VERSIONS, pid, b.get("a"), b.get("b") or "current", b.get("project"), b.get("volumes")))


@app.post("/api/versions/<pid>/variants")
def api_versions_variant_new(pid):
    """{from: a version id, name} -> {variant, project, variants} (the new variant on screen)."""
    b = request.get_json(force=True, silent=True) or {}
    return _versions_call(lambda: versions.create_variant(VERSIONS, pid, b.get("from"), b.get("name")))


@app.post("/api/versions/<pid>/variants/<var>/switch")
def api_versions_variant_switch(pid, var):
    return _versions_call(lambda: versions.switch_variant(VERSIONS, pid, var))


@app.post("/api/versions/<pid>/variants/<var>/rename")
def api_versions_variant_rename(pid, var):
    """{name} -> the variant."""
    b = request.get_json(silent=True) or {}
    return _versions_call(lambda: versions.rename_variant(VERSIONS, pid, var, b.get("name")))


@app.post("/api/versions/<pid>/variants/<var>/delete")
def api_versions_variant_delete(pid, var):
    """The variant and its versions deleted -> {deleted, versions, objects, current, variants, project?}."""
    return _versions_call(lambda: versions.delete_variant(VERSIONS, pid, var))


@app.post("/api/versions/<pid>/take-part")
def api_versions_take_part(pid):
    """{variant, part} -> {part: its JSON in that variant's newest version, version}."""
    b = request.get_json(force=True, silent=True) or {}
    return _versions_call(lambda: versions.take_part(VERSIONS, pid, b.get("variant"), b.get("part")))


@app.get("/api/versions/<pid>/bundle")
def api_versions_bundle(pid):
    """The store for the project file (Save project … with version history) -> {versions: the bundle or null}."""
    return _versions_call(lambda: {"versions": versions.bundle(VERSIONS, pid)})


@app.post("/api/versions/<pid>/bundle")
def api_versions_unbundle(pid):
    """{versions: a project file's bundle} -> {versions, objects} put into this project's store."""
    b = request.get_json(force=True, silent=True) or {}
    return _versions_call(lambda: versions.unbundle(VERSIONS, pid, b.get("versions")))


AI_HISTORY = DATA / "history"  # the project after each AI turn (auto3d/ai_history.py)


@app.get("/api/history")
def api_history_list():
    return jsonify({"states": list_states(AI_HISTORY)})


@app.post("/api/history")
def api_history_save():
    """{project, prompt, tools, kind} -> the saved state's meta (same: true when it equals the newest one)."""
    body = request.get_json(force=True, silent=True) or {}
    try:
        return jsonify(save_state(AI_HISTORY, body.get("project"), body.get("prompt", ""), body.get("tools", 0), body.get("kind", "ai")))
    except HistoryError as e:
        return jsonify({"error": str(e)}), 400


@app.get("/api/history/<sid>")
def api_history_get(sid):
    try:
        return jsonify(load_state(AI_HISTORY, sid))
    except HistoryError as e:
        return jsonify({"error": str(e)}), 404


@app.delete("/api/history/<sid>")
def api_history_delete(sid):
    try:
        delete_state(AI_HISTORY, sid)
    except HistoryError as e:
        return jsonify({"error": str(e)}), 404
    return jsonify({"ok": True})


@app.get("/api/kernel")
def api_kernel():
    """Whether the optional 3D model workspace packages (CAD kernel, sketch solver) are installed; workers: how many
    kernel processes work at once (A3D_WORKERS)."""
    return jsonify({**modeler_status(), "workers": MODEL_WORKER.n})


@app.post("/api/solve")
def api_solve():
    body = request.get_json(force=True)
    with progress.operation(body.get("rid"), "Building a quick part"):
        try:
            progress.report("Building the part")
            _model, solution, final, _flat, bender = _solve_full(body)
            if final is not None and body.get("mesh", True):
                progress.report("Building the 3D view")
                solution["mesh"] = mesh_payload(final)
                if bender is None:  # holes, bosses and faces for the measure tool (flat parts)
                    solution["features"] = final.features()
        except progress.Cancelled:
            return jsonify({"cancelled": True, "ok": False, "issues": []})
    return jsonify(solution)


@app.get("/api/progress/<rid>")
def api_progress(rid):
    return jsonify(progress.status(rid))


@app.post("/api/progress/<rid>/cancel")
def api_progress_cancel(rid):
    progress.cancel(rid)
    return jsonify({"ok": True})


@app.get("/api/jobs")
def api_jobs():
    """What runs now, for the top bar's ⚙ list (every window sees all): the kernel's jobs waiting or running, and the
    slow requests not in the kernel (a quick part's slicing, a file being read) -> {jobs: [{id, kind, what, worker,
    state: waiting | running, elapsed (s), stage?, done?, total?, rid?, req?, stopping}]}."""
    jobs = MODEL_WORKER.list_jobs()
    now = time.time()
    ops = dict(progress.running())
    for j in jobs:
        op = ops.get(j["rid"]) if j["rid"] else None
        if op:
            j.update(stage=op["stage"], done=op["done"], total=op["total"], stopping=j["stopping"] or op["cancel"])
    inside = {j["rid"] for j in jobs if j["rid"]}
    for rid, op in ops.items():
        if rid not in inside:
            jobs.append({"id": f"r{rid}", "kind": op["kind"], "what": op["what"], "rid": rid, "req": op["req"], "worker": None,
                         "state": "running", "elapsed": round(now - op["started"], 1), "stage": op["stage"], "done": op["done"],
                         "total": op["total"], "stopping": op["cancel"]})
    return jsonify({"jobs": jobs})


@app.post("/api/jobs/<job_id>/cancel")
def api_jobs_cancel(job_id):
    """✕ Stop of a job in the list: a kernel job ("k…") as its request's Cancel does (only its process is killed), a
    request outside the kernel ("r<rid>") through its rid. 404: it has ended meanwhile."""
    if job_id.startswith("r"):
        if not any(r == job_id[1:] for r, _ in progress.running()):
            return jsonify({"error": "That job has ended."}), 404
        progress.cancel(job_id[1:])
        return jsonify({"ok": True})
    if not MODEL_WORKER.cancel(job_id):
        return jsonify({"error": "That job has ended."}), 404
    return jsonify({"ok": True})


@app.post("/api/trace")
def api_trace():
    body = request.get_json(force=True)
    try:
        return jsonify(trace_image(body["image"], int(body.get("threshold", 128)), bool(body.get("invert")),
                                   min(int(body.get("max_px", 256)), 1024)))
    except Exception as exc:
        return jsonify({"error": f"Could not trace the image: {exc}"}), 400


# --------------------------------------------------------------------------- image outlines
@app.post("/api/outline/detect")
def api_outline_detect():
    body = request.get_json(force=True)
    try:
        return jsonify(detect_outlines(body["image"], body.get("hints")))
    except Exception as exc:
        return jsonify({"error": f"Could not analyse the image: {exc}"}), 400


@app.post("/api/outline/mask")
def api_outline_mask():
    body = request.get_json(force=True)
    try:
        return jsonify(outline_from_mask(body["mask"], float(body.get("smoothing", 1)), bool(body.get("holes"))))
    except Exception as exc:
        return jsonify({"error": f"Could not read the edited outline: {exc}"}), 400


@app.post("/api/outline/model")
def api_outline_model():
    body = request.get_json(force=True)
    try:
        model = outline_model(body["polygons"], body["img_w"], body["img_h"], body.get("width"), body.get("height"),
                              body.get("preset", "cutter"), body.get("source") or "image.png")
    except (KeyError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"model": model, "preview": {"image": body.get("image"), "width": body["img_w"],
                                                "height": body["img_h"]}})


@app.post("/api/import")
def api_import():
    """DXF / DWG -> outline model (real size); STL / OBJ / 3MF / STEP -> mesh model (sliced)."""
    f = request.files.get("file")
    if f is None:
        return jsonify({"error": "No file uploaded."}), 400
    name, data = f.filename or "part", f.read()
    progress.name(name)
    try:
        with progress.operation(request.form.get("rid"), "Importing a file"):
            return jsonify(_import_data(data, name))
    except progress.Cancelled:
        return jsonify({"error": "Import cancelled.", "cancelled": True}), 409
    except (ImportError_, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:  # broken / unexpected files
        return jsonify({"error": f"Could not read {name}: {exc}"}), 400


def _import_data(data: bytes, name: str) -> dict:
    ext = Path(name).suffix.lower()
    if ext in DRAWING_FORMATS:
        polys, issues = read_dxf(dwg_to_dxf(data) if ext == ".dwg" else data)
        xs = [p[0] for poly in polys for p in poly[0]]
        ys = [p[1] for poly in polys for p in poly[0]]
        model = outline_model(polys, max(xs) - min(xs), max(ys) - min(ys), preset="solid", source=name, space="mm")
        model["issues"] = issues
        return {"model": model, "preview": {"vector": True}}
    if ext in MESH_FORMATS:
        return {"model": mesh_model(data, name), "preview": {"mesh": True},
                "import_file": {"name": name, "data": base64.b64encode(data).decode()}}
    raise ValueError(f"Unsupported file type {ext} (PDF, DXF, DWG, STL, OBJ, 3MF, STEP).")


@app.post("/api/import/register")
def api_import_register():
    """A project with an imported 3D file: give the server the file again (same id)."""
    body = request.get_json(force=True)
    try:
        return jsonify({"mesh_id": register(base64.b64decode(body["data"]), body["name"])})
    except (KeyError, ImportError_) as exc:
        return jsonify({"error": str(exc)}), 400


@app.post("/api/outline/preset")
def api_outline_preset():
    body = request.get_json(force=True)
    return jsonify(preset_objects(body.get("preset"), body.get("opts")))


# --------------------------------------------------------------------------- printers
@app.get("/api/printers")
def api_printers():
    return jsonify(printers.all())


@app.post("/api/printers")
def api_printer_save():
    try:
        return jsonify(printers.save(request.get_json(force=True)))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@app.delete("/api/printers/<pid>")
def api_printer_delete(pid):
    try:
        printers.delete(pid)
        return jsonify({"ok": True})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


def _plan(body, solid, model, bender=None, final=None):
    printer = printers.get(body.get("printer"))
    if printer is None:
        raise ValueError("Unknown printer.")
    avoid = [(bender.axis, op["s"], op["e"]) for op in bender.ops] if bender else []
    zones = [(bender.axis, op["s"], op["e"], op["rn"]) for op in bender.ops] if bender else []
    result = plan(solid, model["unit"], printer, float(body.get("margin", 5)), bool(body.get("split")),
                  body.get("joint"), avoid=avoid, bend_zones=zones)
    if bender is not None:
        bend_pieces(result, bender, model["unit"], float(body.get("margin", 5)), getattr(final, "frame", None))
    return result


@app.post("/api/print/plan")
def api_print_plan():
    """A part split for a printer (body.rid: the progress box's Cancel -> 409, the kernel job stopped)."""
    body = request.get_json(force=True)
    try:
        with progress.operation(body.get("rid"), "Splitting for print"):
            return _print_plan(body)
    except progress.Cancelled:
        return jsonify({"error": "Cancelled.", "cancelled": True}), 409


def _print_plan(body):
    progress.report("Splitting the part")
    model, solution, final, solid, bender = _solve_full(body)
    if solid is None:
        return jsonify({"error": "The model is invalid."}), 400
    if bender is None and body.get("bends") and not solution.get("design_ok", True):
        return jsonify({"error": " ".join(i["message"] for i in solution["design_issues"] if i["severity"] == "error")}), 400
    try:
        result = _plan(body, solid, model, bender, final)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    # a part with an exact model (a 3D model part's printing copy, a STEP): the pieces cut from it, smooth
    src = printexact.source(model, solution, bender) if body.get("split") else None
    exact = printexact.cut(result, src, MODEL_WORKER) if src else None
    # the preview shows bent pieces / connectors in their assembled position
    for k, p in enumerate(result["pieces"]):
        solid_p = p.pop("solid")
        p.pop("cell_region", None)
        p.pop("voids", None)
        g = exact[k] if exact else None
        p["mesh"] = printexact.mesh_payload(g) if g else mesh_payload(p.pop("assembled", solid_p))
        p.pop("assembled", None)
    for g in result.get("connectors", []):
        for inst in g["instances"]:
            solid_i = inst.pop("solid")
            inst["mesh"] = mesh_payload(inst.pop("assembled", solid_i))
    return jsonify(result)


@app.get("/api/joints")
def api_joints():
    return jsonify(joint_catalog())


# --------------------------------------------------------------------------- export
# ------------------------------------------------------------------ 3D model parts (sketch -> features -> B-rep)
def attachment(filename: str) -> str:
    """The Content-Disposition of a download named `filename`: HTTP headers are Latin-1, so an ASCII name for old
    browsers and the real one (Czech letters, "—" …) UTF-8 encoded (RFC 6266 / 5987) for the others."""
    import unicodedata
    from urllib.parse import quote
    plain = unicodedata.normalize("NFKD", filename.replace("—", "-").replace("–", "-"))
    plain = plain.encode("ascii", "ignore").decode().replace('"', "").replace("\\", "_").strip() or "download"
    return f"attachment; filename=\"{plain}\"; filename*=UTF-8''{quote(filename, safe='')}"


def _model_call(op, arg, timeout=120):
    """Run a kernel op in its part's worker process (worker.Pool) -> (result, None) or (None, error response)."""
    try:
        with timings.timed(f"kernel {op}"):
            return MODEL_WORKER.run(op, arg, timeout), None
    except progress.Cancelled:  # (✕ Stop in the jobs list, or the request's Cancel)
        return None, (jsonify({"error": "Cancelled.", "cancelled": True}), 409)
    except KernelUnavailable as exc:
        return None, (jsonify({"error": str(exc), "install": "py -m pip install -r requirements-modeler.txt"}), 501)
    except KernelFailed as exc:
        return None, (jsonify({"error": str(exc)}), 500)


@app.post("/api/model/rebuild")
def api_model_rebuild():
    """{part, rid, bin, later, cut} -> the body (mesh with one face id per triangle, faces, edges), each feature's status.
    bin: one binary message (auto3d/modeler/packed.py: the arrays as they are, a big body encoded once), else JSON
    with the arrays in base64. later: 🔩 real threads not cut yet are left for later (threads.real.pending) — when the
    kernel has more than one process, so the cut can run beside the part's next edits; cut (with bin): that cut, in
    a process of its own (the jobs list: Cutting real threads)."""
    body = request.get_json(force=True)
    part, op = body.get("part") or {}, "rebuild_bin" if body.get("bin") else "rebuild"
    if body.get("later") and MODEL_WORKER.n > 1:
        part = {**part, "_later": True}
    if body.get("cut") and body.get("bin"):
        op = "threads_bin"
    try:
        with progress.operation(body.get("rid"), "Cutting real threads" if op == "threads_bin" else "Building a part"):
            res, err = _model_call(op, part)
    except progress.Cancelled:
        return jsonify({"cancelled": True})
    if err:
        return err
    if body.get("bin"):
        return Response(res, mimetype="application/octet-stream")
    for b in [res.get("body"), *(res.get("refs") or [])]:
        if b:
            b["positions"] = base64.b64encode(b["positions"]).decode("ascii")
            b["face_ids"] = base64.b64encode(b["face_ids"]).decode("ascii")
    return jsonify(res)


@app.post("/api/drawing/import")
def api_drawing_import():
    """A DXF / DWG -> the drawing as it is (layers, entities in mm) for the 2D drawing editor."""
    from auto3d.drawing2d import read_drawing
    fs = request.files.getlist("file")
    if not fs:
        return jsonify({"error": "No file uploaded."}), 400
    try:
        if len(fs) > 1:  # loose Gerber / drill files picked together: one board
            from auto3d.pcb import read_gerber_set
            return jsonify({**read_gerber_set([(f.filename or f"file{i}", f.read()) for i, f in enumerate(fs)]), "source": fs[0].filename or "board"})
        f = fs[0]
        return jsonify(read_drawing(f.read(), f.filename or "drawing.dxf"))
    except (ImportError_, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400


@app.post("/api/drawing/dxf")
def api_drawing_dxf():
    """A drawing (its shown layers) -> a DXF file."""
    from auto3d.drawing2d import to_dxf
    d = request.get_json(force=True) or {}
    try:
        data = to_dxf(d, fills=d.get("fills", True))
    except (ImportError_, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400
    return Response(data, mimetype="application/dxf")


@app.post("/api/drawing/outline")
def api_drawing_outline():
    """A drawing (its shown layers) -> a quick part from its closed outlines, as a DXF import gives."""
    from auto3d.drawing2d import outline_of
    d = request.get_json(force=True) or {}
    try:
        polys, issues = outline_of(d)
    except (ImportError_, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400
    xs = [q[0] for poly in polys for q in poly[0]]
    ys = [q[1] for poly in polys for q in poly[0]]
    model = outline_model(polys, max(xs) - min(xs), max(ys) - min(ys), preset="solid", source=d.get("source") or "drawing", space="mm")
    model["issues"] = issues
    return jsonify({"model": model, "preview": {"vector": True}})


@app.post("/api/blob")
def api_blob_put():
    """A file a 3D model step uses (an imported STEP): kept by its SHA-256 -> {sha}. Raw body or a form file."""
    from auto3d.modeler import blobs
    f = request.files.get("file")
    data = f.read() if f else request.get_data()
    if not data:
        return jsonify({"error": "No file uploaded."}), 400
    return jsonify({"sha": blobs.put(data), "size": len(data)})


@app.get("/api/blob/<sha>")
def api_blob_get(sha):
    from auto3d.modeler import blobs
    try:
        return send_file(blobs.path(sha), mimetype="application/octet-stream")
    except blobs.Missing:
        return jsonify({"error": "No such file here."}), 404


@app.post("/api/model/import")
def api_model_import():
    """A STEP / IGES / STL / OBJ / 3MF file -> a solid step for a 3D model: {blob, faces, bbox, volume, op?, warning?} (form:
    file, rid). An IGES of surfaces that do not close comes as op "ref" (a reference body) with a warning. Several files
    (an assembly STEP and the part files it refers to, picked together): the top one opens, with the others."""
    from auto3d.modeler import blobs
    fs = [f for f in request.files.getlist("file") if f]
    if not fs:
        return jsonify({"error": "No file uploaded."}), 400
    name = fs[0].filename or "part.step"
    progress.name(name)
    try:
        with progress.operation(request.form.get("rid"), "Importing a file"):
            progress.report(f"Reading {name}")
            if len(fs) > 1:
                files = {f.filename or f"part{i}.step": blobs.put(f.read()) for i, f in enumerate(fs)}
                res, err = _model_call("import_solid", {"files": files}, timeout=600)
                name = (res or {}).get("name") or name
            else:
                sha = blobs.put(fs[0].read())
                res, err = _model_call("import_solid", {"blob": sha, "name": name})
    except progress.Cancelled:
        return jsonify({"error": "Import cancelled.", "cancelled": True}), 409
    if err:
        return err
    return jsonify({**res, "name": name})


@app.post("/api/model/import/assembly")
def api_model_import_assembly():
    """{blob (a STEP from /api/model/import), name, rid} -> its assembly tree: {root, parts: {key: {name, blob, faces,
    bbox, volume}}, assemblies: {key: {name, instances: [{ref, matrix, name, colour?}]}}} — a part per different part
    (each its own STEP blob), an instance per placement, sub-assemblies nested."""
    body = request.get_json(force=True) or {}
    name = body.get("name") or "assembly.step"
    progress.name(name)
    try:
        with progress.operation(body.get("rid"), "Reading an assembly"):
            progress.report(f"Reading the assembly of {name}")
            res, err = _model_call("import_assembly", {"blob": body.get("blob"), "name": name}, timeout=600)
    except progress.Cancelled:
        return jsonify({"error": "Import cancelled.", "cancelled": True}), 409
    if err:
        return err
    return jsonify({**res, "name": name})


@app.post("/api/model/sketch/offset")
def api_model_sketch_offset():
    """{polys: [[outer ring, hole rings…]…] (a sketch outline), d} -> the outline grown by d mm (shrunk when d < 0),
    sharp corners kept sharp."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union

    from auto3d.design import polygons_of
    body = request.get_json(force=True)
    try:
        d = float(body.get("d"))
        g = unary_union([Polygon(p[0], p[1:]) for p in body.get("polys") or [] if p and len(p[0]) >= 3]).buffer(0)
    except (TypeError, ValueError):
        return jsonify({"error": "Give an outline and a distance."}), 400
    g = g.buffer(d, join_style=2, mitre_limit=4)
    if g.is_empty:
        return jsonify({"error": "Nothing is left — the outline is thinner than that."}), 400
    ring = lambda r: [[round(x, 5), round(y, 5)] for x, y in list(r.coords)[:-1]]  # noqa: E731
    return jsonify({"polys": [[ring(p.exterior)] + [ring(h) for h in p.interiors] for p in polygons_of(g)]})


@app.post("/api/model/sketch/clean")
def api_model_sketch_clean():
    """{op: "simplify" | "join" | "outline", sketch, ids?, tol?} -> {sketch: {points, entities, constraints, dims},
    report}: 🧹 Simplify (the picks or the whole sketch), ⛓ Join into one curve, ◆ One outline (sketchclean.py)."""
    from auto3d.modeler import sketchclean
    body = request.get_json(force=True) or {}
    op, sk, ids = body.get("op"), body.get("sketch") or {}, body.get("ids") or None
    try:
        if op == "simplify":
            new, rep = sketchclean.simplify(sk, ids, body.get("tol"))
        elif op == "join":
            new, rep = sketchclean.join(sk, ids, body.get("tol"))
        elif op == "outline":
            new, rep = sketchclean.outline(sk, ids, body.get("name") or "Outline", body.get("tol"))
        else:
            return jsonify({"error": "Ask for simplify, join or outline."}), 400
    except (ValueError, KeyError, TypeError) as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"sketch": new, "report": rep})


@app.post("/api/drawing/sketch")
def api_drawing_sketch():
    """A drawing (its chosen shapes) -> a sketch, cleaned: ends welded, crumbs absorbed, lines / arcs joined, smooth
    curves as splines -> {sketch: {points, entities, constraints, dims}, report: before / after counts}."""
    from auto3d.modeler import sketchclean
    d = request.get_json(force=True) or {}
    try:
        new, rep = sketchclean.from_drawing(d, d.get("tol"))
    except (ValueError, KeyError, TypeError) as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"sketch": new, "report": rep})


@app.post("/api/model/profile")
def api_model_profile():
    """A classic part (picture outline, DXF, PDF drawing, 3D file's footprint) -> its outline in mm, lower-left
    corner at (0, 0), for a sketch block in the 3D model workspace."""
    from shapely.affinity import scale as sh_scale, translate as sh_translate
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    from auto3d.design import polygons_of
    from auto3d.export import UNIT_IN_MM
    body = request.get_json(force=True)
    model = body.get("model") or {}
    try:
        if model.get("kind") in ("outline", "mesh"):
            _, solution, *_ = _solve_full(body)
            polys = [Polygon(p[0], p[1:]) for p in solution.get("outline_2d") or [] if len(p[0]) >= 3]
            k = 1.0
        else:
            solution = solve(model, body.get("values"))
            if not solution["ok"]:
                raise ValueError("The drawing has errors — fix them in Checks first.")
            prof = profile_polygon(solution)
            if model.get("shapes"):
                prof = apply_shapes(prof, model["shapes"], lambda *a, **kw: None)
            polys, k = polygons_of(prof), UNIT_IN_MM.get(model.get("unit"), 1.0)
    except (KeyError, ValueError, TypeError) as exc:
        return jsonify({"error": str(exc) or "This part has no outline to use."}), 400
    g = unary_union([p.buffer(0) for p in polys if not p.is_empty])
    if g.is_empty:
        return jsonify({"error": "This part has no outline to use."}), 400
    g = sh_scale(g, k, k, origin=(0, 0))
    x0, y0, x1, y1 = g.bounds
    g = sh_translate(g, -x0, -y0).simplify(max(x1 - x0, y1 - y0) * 2e-4)  # fewer points, no visible change
    ring = lambda r: [[round(x, 5), round(y, 5)] for x, y in list(r.coords)[:-1]]  # noqa: E731
    out = [[ring(p.exterior)] + [ring(h) for h in p.interiors] for p in polygons_of(g)]
    name = re.sub(r"\.[A-Za-z0-9]+$", "", model.get("source") or "outline")
    return jsonify({"polygons": out, "width": x1 - x0, "height": y1 - y0, "name": name})


@app.post("/api/export/3mf")
def api_export_3mf():
    """{groups: [{name, color, positions}], title} -> a 3MF with a coloured object per colour (multi-material printing)."""
    from auto3d.export3mf import to_3mf
    body = request.get_json(force=True, silent=True) or {}
    try:
        data = to_3mf(body.get("groups") or [], body.get("title") or "Auto3DModeler")
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return Response(data, mimetype="model/3mf")


@app.post("/api/assembly/clashes")
def api_assembly_clashes():
    """{instances: [{id, part: {features}, matrix: [16]}]} -> {clashes: [{a, b, volume, bbox}]} — parts that overlap."""
    body = request.get_json(force=True)
    try:
        with progress.operation(body.get("rid"), "Checking collisions"):  # (a newer check, ✕ Stop: this one's kernel job stopped)
            data, err = _model_call("assembly_clashes", {"instances": body.get("instances") or [], "quick": bool(body.get("quick"))})
    except progress.Cancelled:
        err = (None, 409)
    if err and err[1] == 409:  # (200: a check overtaken by a newer one is not an error the browser should log)
        return jsonify({"cancelled": True, "clashes": None})
    if err:
        return err
    return jsonify({"clashes": data})


@app.post("/api/assembly/clearance")
def api_assembly_clearance():
    """📏 {instances: [{id, part: {features}, matrix: [16]}], a: [the ids on one side] (none: the first)} -> {a, b,
    distance (mm), pa, pb, overlap?} — the least distance between two placed parts (their clearance)."""
    body = request.get_json(force=True)
    data, err = _model_call("assembly_clearance", {"instances": body.get("instances") or [], "a": body.get("a")}, timeout=60)
    return err or jsonify(data)


EXACT_SHEET_TIMEOUT = 150  # s: the exact hidden-line drawing; longer (it can hang on some shapes): drawn from the mesh
SHEET_TIMEOUT = 600  # s: the drawing from the mesh (MIT E-Vent's 41 placements: ~25 s); the page can Cancel either


def _sheet_call(op, arg, body):
    """A sheet's kernel job (its own limits, the request's rid for progress and Cancel) -> (data, None) or (None, an
    error the page shows on the sheet: 422 with the reason, 409 when cancelled). An exact drawing over
    EXACT_SHEET_TIMEOUT is stopped and made again from the mesh (geometry.simple: no hidden lines)."""
    try:
        with progress.operation(body.get("rid"), "Making a drawing"):
            try:
                return MODEL_WORKER.run(op, arg, EXACT_SHEET_TIMEOUT), None
            except KernelFailed as exc:
                if not str(exc).startswith("Building took longer"):
                    raise
                progress.report("The exact drawing takes too long — drawing it from the mesh")
                return MODEL_WORKER.run(op, {**arg, "simple": True}, SHEET_TIMEOUT), None
    except progress.Cancelled:
        return None, (jsonify({"error": "Cancelled.", "cancelled": True}), 409)
    except KernelUnavailable as exc:
        return None, (jsonify({"error": str(exc), "install": "py -m pip install -r requirements-modeler.txt"}), 501)
    except KernelFailed as exc:  # (the kernel's message: why this part / assembly cannot be drawn)
        return None, (jsonify({"error": str(exc)}), 422)


@app.post("/api/sheet/build")
def api_sheet_build():
    """{part, preset: light | medium | full, paper, scale ("1:2522", else the fit's), frame, rid} -> {geometry (views,
    points), layout, dims} — a drawing sheet."""
    body = request.get_json(force=True)
    data, err = _sheet_call("sheet", {"part": body.get("part") or {}, "preset": body.get("preset") or "medium", "paper": body.get("paper"),
                                      "per_view": body.get("per_view") or {}, "section": bool(body.get("section"))}, body)
    if err:
        return err
    return _sheet_layout(data, body)


def _sheet_layout(data, body):
    """A sheet's layout made for its own scale ("1:2522") and frame ({m: [l, t, r, b], title}) when it has them (its
    holes' positions and callouts placed clear again for it)."""
    if body.get("scale") or body.get("frame"):
        from auto3d.modeler.sheet import layout, place
        try:
            data["layout"] = layout(data["geometry"], body.get("paper"), body.get("scale") or None, body.get("frame") or None)
            if data.get("dims"):
                data["dims"] = place(data["geometry"], data["layout"], data["dims"])
        except (ValueError, TypeError, KeyError) as exc:
            return jsonify({"error": f"The sheet's layout could not be made: {exc}"}), 422
    return jsonify(data)


@app.post("/api/sheet/assembly")
def api_sheet_assembly():
    """{instances (placed, as for clashes), paper, scale, frame, base (the id of the part it stands on: its free holes
    dimensioned), rid} -> {geometry, layout, dims, marks} — an assembly's drawing sheet."""
    body = request.get_json(force=True)
    data, err = _sheet_call("assembly_sheet", {"instances": body.get("instances") or [], "paper": body.get("paper"), "explode": body.get("explode") or 0,
                                               "base": body.get("base")}, body)
    if err:
        return err
    return _sheet_layout(data, body)


@app.post("/api/sheet/place")
def api_sheet_place():
    """{geometry, layout (its views where the user moved them, vscale: {view: [a, b]}), dims} -> {dims} — the holes'
    positions and callouts placed clear again after a view was moved or given its own scale (sheet.place)."""
    from auto3d.modeler.sheet import place
    body = request.get_json(force=True)
    try:
        return jsonify({"dims": place(body["geometry"], body["layout"], body.get("dims") or [])})
    except (ValueError, TypeError, KeyError, IndexError) as exc:
        return jsonify({"error": f"The dimensions could not be placed: {exc}"}), 400


@app.post("/api/sheet/pdf")
def api_sheet_pdf():
    """{svg | svgs: [...], name} -> the sheet (or a drawing set, a page each) as a PDF, drawn as the editor shows it."""
    from auto3d.modeler.sheet import pdf
    body = request.get_json(force=True)
    name = re.sub(r'[\\/:*?"<>|]+', "_", body.get("name") or "drawing").strip() or "drawing"
    try:
        data = pdf(body["svgs"] if isinstance(body.get("svgs"), list) and body["svgs"] else str(body.get("svg") or ""))
    except Exception as exc:  # noqa: BLE001 — a broken SVG
        return jsonify({"error": f"The sheet could not be made a PDF: {exc}"}), 400
    return Response(data, mimetype="application/pdf", headers={"Content-Disposition": attachment(f"{name}.pdf")})


@app.get("/api/bom/xlsx")
def api_bom_xlsx_ok():
    """Whether a BOM can be written as Excel (.xlsx): openpyxl installed."""
    from auto3d.bomxlsx import available
    return jsonify({"available": available()})


@app.post("/api/bom/xlsx")
def api_bom_xlsx():
    """{name, sheets: [{title, head, rows, levels, keys}]} -> the BOM as an Excel workbook (a sheet per view)."""
    from auto3d.bomxlsx import available, to_xlsx
    if not available():
        return jsonify({"error": "Excel needs the openpyxl package (py -m pip install openpyxl) — the BOM can be saved as CSV."}), 501
    body = request.get_json(force=True)
    name = re.sub(r'[\\/:*?"<>|]+', "_", body.get("name") or "BOM").strip() or "BOM"
    try:
        data = to_xlsx(body.get("sheets") or [], name)
    except Exception as exc:  # noqa: BLE001 — cells it cannot write
        return jsonify({"error": f"The BOM could not be written as Excel: {exc}"}), 400
    return Response(data, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": attachment(f"{name}.xlsx")})


@app.post("/api/sheet/dxf")
def api_sheet_dxf():
    """{svg, dims, scale, name} -> the sheet as a DXF: the paper 1:1 in mm, the views at the sheet's scale, real
    dimensions (showing the part's sizes), the title block; layers visible / hidden / dims / hatch / text / frame."""
    from auto3d.modeler.sheetdxf import to_dxf
    body = request.get_json(force=True)
    name = re.sub(r'[\\/:*?"<>|]+', "_", body.get("name") or "drawing").strip() or "drawing"
    try:
        data = to_dxf(str(body.get("svg") or ""), body.get("dims") or [], float(body.get("scale") or 1))
    except Exception as exc:  # noqa: BLE001 — a broken SVG
        return jsonify({"error": f"The sheet could not be made a DXF: {exc}"}), 400
    return Response(data, mimetype="image/vnd.dxf", headers={"Content-Disposition": attachment(f"{name}.dxf")})


@app.post("/api/assembly/sweep")
def api_assembly_sweep():
    """{instances: [...as for clashes, at the start], steps: [{at, matrices: {id: [16]}}], quick} -> {steps: [{at, clashes}]}
    — the collisions of the moving parts at each step of a motion."""
    body = request.get_json(force=True)
    steps = (body.get("steps") or [])[:200]
    data, err = _model_call("assembly_sweep", {"instances": body.get("instances") or [], "steps": steps, "quick": bool(body.get("quick"))})
    if err:
        return err
    return jsonify({"steps": data})


ANIMATIONS = DATA / "animations"  # 🎬 the mechanisms' animations saved (auto3d/animation.py)


@app.post("/api/anim/<aid>/frame/<int:n>")
def api_anim_frame(aid, n):
    """A frame (the raw PNG) of the animation `aid` being recorded -> {frames: how many it has}."""
    try:
        return jsonify({"frames": animation.add_frame(ANIMATIONS, aid, n, request.get_data())})
    except animation.AnimationError as e:
        return jsonify({"error": str(e)}), 400


@app.post("/api/anim/<aid>/gif")
def api_anim_gif(aid):
    """{name, fps, rid} -> the frames of `aid` made into a looping GIF in the data folder: {file, path, url, frames,
    width, height, bytes, fps} — a job of the ⚙ list (rid: its progress, Cancel)."""
    body = request.get_json(force=True)
    with progress.operation(body.get("rid"), "Making an animation"):
        try:
            res = animation.write_gif(ANIMATIONS, aid, body.get("name") or "", float(body.get("fps") or 20))
        except progress.Cancelled:
            animation.discard(ANIMATIONS, aid)
            return jsonify({"cancelled": True})
        except animation.AnimationError as e:
            return jsonify({"error": str(e)}), 400
    return jsonify({**res, "url": f"/api/anim/file/{res['file']}"})


@app.post("/api/anim/<aid>/video/<kind>")
def api_anim_video(aid, kind):
    """A video the browser recorded (the raw WebM / MP4; ?name= the mechanism's) kept in the data folder -> {file,
    path, url, bytes}."""
    try:
        animation.discard(ANIMATIONS, aid)
        res = animation.save_file(ANIMATIONS, request.args.get("name") or "", kind, request.get_data())
    except animation.AnimationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({**res, "url": f"/api/anim/file/{res['file']}"})


@app.delete("/api/anim/<aid>")
def api_anim_discard(aid):
    """A recording cancelled: its frames gone."""
    try:
        animation.discard(ANIMATIONS, aid)
    except animation.AnimationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"ok": True})


@app.get("/api/anim/file/<name>")
def api_anim_file(name):
    return send_from_directory(ANIMATIONS, name, as_attachment=True)


ASSEMBLY_FILES = {"step":("model/step", "step"), "iges": ("model/iges", "igs"), "glb": ("model/gltf-binary", "glb")}  # format -> (mime, extension)


@app.post("/api/assembly/export/<fmt>")
def api_assembly_step(fmt):
    """{tree: {root, parts: {id: {name, features, colour?}}, assemblies: {id: {name, instances: [{ref, matrix,
    colour?}]}}}, name} -> a structured STEP (AP214: a product per part, placed instances, sub-assemblies nested), as
    SolidWorks / CATIA / Solid Edge open an assembly; iges: every part placed in one IGES (names, colours; IGES has no
    tree); glb: a binary glTF for viewers / rendering (a node per placed part, names, PBR materials). {instances:
    [{part: {features}, matrix: [16]}]} (no tree): every placed body in one compound (STEP / IGES)."""
    if fmt not in ASSEMBLY_FILES:
        return jsonify({"error": f"Unknown format {fmt}"}), 404
    body = request.get_json(force=True)
    name = re.sub(r'[\\/:*?"<>|]+', "_", body.get("name") or "assembly").strip() or "assembly"
    data, err = _model_call("assembly_step", {"instances": body.get("instances") or [], "tree": body.get("tree"), "name": name, "fmt": fmt}, timeout=600)
    if err:
        return err
    mime, ext = ASSEMBLY_FILES[fmt]
    return Response(data, mimetype=mime, headers={"Content-Disposition": attachment(f"{name}.{ext}")})


@app.post("/api/model/sketch/solve")
def api_model_sketch_solve():
    """{sketch, drag?: {point: [u, v]}} -> solved points and radii, free degrees, conflicting locks.
    planegcs is quick and safe in-process (no CAD kernel involved)."""
    from auto3d.modeler import available
    if not available("planegcs"):
        return jsonify({"error": "Locked sketch sizes need the sketch solver: py -m pip install -r requirements-modeler.txt",
                        "install": "py -m pip install -r requirements-modeler.txt"}), 501
    from auto3d.modeler.constraints import SketchError, solve as solve_sketch
    body = request.get_json(force=True)
    try:
        return jsonify(solve_sketch(body.get("sketch") or {}, body.get("drag"), body.get("keep"), bool(body.get("detail"))))
    except SketchError as exc:
        return jsonify({"error": str(exc)}), 400


@app.post("/api/model/limits")
def api_model_limits():
    """{part: {features}, id} -> {field: [min, max], _approx: [field…], _soft: [field…]}: the values each number of that step can take.
    Only a hint for the sliders: a kernel failure (or a search past 30 s) gives no ranges ({_error}), not a 500."""
    body = request.get_json(force=True)
    data, err = _model_call("limits", {"features": (body.get("part") or {}).get("features") or [], "id": body.get("id")}, timeout=30)
    if err and err[1] == 500:
        return jsonify({"_error": err[0].get_json().get("error")})
    if err:
        return err
    return jsonify(data)


MODEL_FILES = {"stl": ("model/stl", "stl"), "step": ("model/step", "step"), "iges": ("model/iges", "igs"), "pdf": ("application/pdf", "pdf"),
               "glb": ("model/gltf-binary", "glb"), "obj": ("model/obj", "obj")}


@app.post("/api/model/export/<fmt>")
def api_model_export(fmt):
    if fmt not in MODEL_FILES:
        return jsonify({"error": f"Unknown format {fmt}"}), 404
    body = request.get_json(force=True)
    name = re.sub(r'[\\/:*?"<>|]+', "_", body.get("name") or "part").strip() or "part"
    data, err = _model_call("export", {"part": body.get("part") or {}, "fmt": fmt, "name": name})
    if err:
        return err
    mime, ext = MODEL_FILES[fmt]
    return Response(data, mimetype=mime, headers={"Content-Disposition": attachment(f"{name}.{ext}")})


@app.post("/api/export/<fmt>")
def api_export(fmt):
    if fmt not in ("stl", "step"):
        return jsonify({"error": f"Unknown format {fmt}"}), 404
    try:
        data, filename, mime = _export_bytes(request.get_json(force=True), fmt)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return Response(data, mimetype=mime, headers={"Content-Disposition": attachment(filename)})


def _export_bytes(body: dict, fmt: str):
    """(bytes, file name, mime type) of the part — whole, or split for the printer as a ZIP."""
    model, solution, final, solid, bender = _solve_full(body)
    if solid is None:
        raise ValueError("The model is invalid and cannot be exported: "
                         + " ".join(i["message"] for i in solution["issues"] if i["severity"] == "error"))
    if not solution.get("design_ok", True):
        msgs = " ".join(i["message"] for i in solution["design_issues"] if i["severity"] == "error")
        raise ValueError(f"Fix the design layers first: {msgs}")
    name = re.sub(r"[^A-Za-z0-9_-]+", "_", Path(model.get("source", "part")).stem).strip("_") or "part"
    writer = to_stl if fmt == "stl" else to_step
    mime = "model/stl" if fmt == "stl" else "model/step"
    src = printexact.source(model, solution, bender)  # an exact model: the files from it (smooth curved walls)

    if body.get("split") and body.get("printer"):
        result = _plan(body, solid, model, bender, final)
        if not result["pieces"]:
            raise ValueError(" ".join(i["message"] for i in result["issues"]) or "Nothing to export.")
        exact = printexact.cut(result, src, MODEL_WORKER, fmt) if src else None
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for k, p in enumerate(result["pieces"]):
                pname = f"{name}_part{p['index']}"
                if exact and exact[k]:
                    z.writestr(f"{pname}.{fmt}", exact[k]["data"])
                    continue
                piece = p["solid"].flipped() if p["flip"] else p["solid"]
                z.writestr(f"{pname}.{fmt}", writer(piece.at_origin(), model["unit"], pname))
            for k, g in enumerate(result.get("connectors", []), 1):
                cname = f"{name}_{g['kind']}{k}_x{g['qty']}"
                z.writestr(f"{cname}.{fmt}", writer(g["instances"][0]["solid"].at_origin(), model["unit"], cname))
            z.writestr("ASSEMBLY.txt", assembly_text(result, name))
        return buf.getvalue(), f"{name}_{fmt}_pieces.zip", "application/zip"
    whole = printexact.whole(src, MODEL_WORKER, fmt) if src else None
    return whole or writer(final, model["unit"], name), f"{name}.{fmt}", mime


# --------------------------------------------------------------------------- AI agent (MCP tools + chat)
RELAY = Relay()
CHATS: dict[str, ChatSession] = {}  # the app window's client id ("": none given) -> its chat
CHAT_IDLE_GONE = 600  # s: the chat of a window closed this long ago ends (its Claude Code process)
CHAT_STORE = DATA / "chats"  # the chat's conversations (auto3d/chat_history.py): 🕘 Previous conversations
APP_URL = "http://127.0.0.1:5173"
LAST_TRACE: dict = {}
PICTURE_FORMATS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff"}


def _client() -> str:
    """The app window a chat request comes from (?client= or {"client"}): each window has its own chat."""
    body = request.get_json(silent=True) if request.is_json else None
    return str(request.args.get("client") or (body or {}).get("client") or "")[:64]


def _chat(client: str = "") -> ChatSession:
    """The chat of the window `client` (made at its first use; its tool calls act in that window). The chats of
    windows closed for CHAT_IDLE_GONE seconds, not answering now, end."""
    now = time.time()
    for cid, chat in list(CHATS.items()):
        if cid in RELAY.seen and cid != client and not chat.busy and not chat.subscribers and now - RELAY.seen[cid] > CHAT_IDLE_GONE:
            chat.stop()
            del CHATS[cid]
    if client not in CHATS:
        CHATS[client] = ChatSession(APP_URL, client or None, CHAT_STORE)
    return CHATS[client]


def stop_chats():
    """Every window's chat ends (the app quits; the AI's access changed: the next message starts afresh)."""
    for chat in list(CHATS.values()):
        chat.stop()


def _mcp_result(text: str, image: str | None = None, error: bool = False) -> dict:
    content = [{"type": "text", "text": text}]
    if image:
        content.append({"type": "image", "data": image, "mimeType": "image/png"})
    return {"content": content, "isError": error}


def _file(path: str) -> Path:
    p = Path(path).expanduser()
    if not p.is_file():
        raise ValueError(f"No such file: {p}")
    return p


def _load_in_page(data: dict, extra: dict | None = None) -> str:
    res = RELAY.call("load", {"data": data, **(extra or {})})
    if res.get("error"):
        raise ValueError(res.get("text") or "The page could not open it.")
    return res.get("text", "Opened.")


def _png_b64(img_bgr, max_px=900) -> str:
    h, w = img_bgr.shape[:2]
    s = min(1.0, max_px / max(h, w))
    if s < 1:
        img_bgr = cv2.resize(img_bgr, (round(w * s), round(h * s)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".png", img_bgr)
    return base64.b64encode(buf.tobytes()).decode()


def _load_drawing(d: dict, name: str) -> str:
    """A drawing JSON (auto3d/drawing2d.py) opened in the page as a 📐 2D drawing (its own tab)."""
    res = RELAY.call("load_drawing", {"data": d, "name": name})
    if res.get("error"):
        raise ValueError(res.get("text") or "The page could not open it.")
    return res.get("text", "Opened.")


def tool_open_file(args):
    from auto3d.drawing2d import PCB_EXT, read_drawing
    raw = Path(str(args["path"])).expanduser()
    if raw.is_dir():  # loose Gerber / drill files in a folder: one board
        from auto3d.pcb import read_gerber_set
        files = [(f.name, f.read_bytes()) for f in sorted(raw.iterdir()) if f.is_file() and f.stat().st_size < 50_000_000]
        return {"text": _load_drawing({**read_gerber_set(files), "source": raw.name}, raw.name)}
    p = _file(args["path"])
    ext = p.suffix.lower()
    if ext == ".a3d":  # a saved project: on screen as a new one (the one there is kept)
        return {"text": _open_project_file(p)}
    if ext in (".igs", ".iges"):  # IGES (older CAD exchange): a 3D model part with the file's solid
        from auto3d.modeler import blobs
        res = RELAY.call("load_solid", {"blob": blobs.put(p.read_bytes()), "name": p.name}, timeout=600)
        if res.get("error"):
            raise ValueError(res.get("text") or "The page could not open it.")
        return {"text": res.get("text", "Opened.")}
    if args.get("as") == "assembly":  # a STEP assembly (SolidWorks, CATIA, Solid Edge …): parts + an assembly
        if ext not in (".step", ".stp"):
            raise ValueError('as "assembly" is for a STEP file (.step / .stp).')
        from auto3d.modeler import blobs
        res = RELAY.call("load_step_assembly", {"blob": blobs.put(p.read_bytes()), "name": p.name}, timeout=900)
        if res.get("error"):
            raise ValueError(res.get("text") or "The page could not open it.")
        return {"text": res.get("text", "Opened.")}
    if ext in PICTURE_FORMATS:
        raise ValueError("That is a picture: use trace_picture to find its outline, then use_outline.")
    if p.name.lower().endswith(PCB_EXT) or (ext in DRAWING_FORMATS and (args.get("as") or "drawing") == "drawing"):
        return {"text": _load_drawing(read_drawing(p.read_bytes(), p.name), re.sub(r"\.(tar\.gz|[^.]+)$", "", p.name, flags=re.I))}
    data = _pdf_data(p.read_bytes(), int(args.get("page") or 0), p.name) if ext == ".pdf" else _import_data(p.read_bytes(), p.name)
    return {"text": _load_in_page(data)}


def _load_project(proj: dict, versions=None) -> str:
    res = RELAY.call("load_project", {"project": proj, **({"versions": versions} if versions else {})}, timeout=600)
    if res.get("error"):
        raise ValueError(res.get("text") or "The page could not open it.")
    return res.get("text", "Opened.")


def _open_project_file(p: Path) -> str:
    """A project file (.a3d, as Save project writes it): its imported files back into the blob store, then the project
    (any version -> 3) on screen; its 🕘 version history too when it was saved with it."""
    proj, hist = _project_from(p.read_bytes())
    return _load_project(proj, hist)


def _demo_named(name: str) -> dict:
    """A demo by its file name, its name (English or Czech) or words of it."""
    rows = demos.listing(DEMOS)
    w = str(name or "").strip().lower()
    hit = next((d for d in rows if w in (d["file"].lower(), d["name"].lower(), d["name_cs"].lower())), None) or next(
        (d for d in rows if w and (w in d["name"].lower() or w in d["name_cs"].lower() or w in d["file"].lower())), None)
    if not hit:
        raise ValueError(f"No demo “{name}”. The demos: " + "; ".join(f"{d['file']} ({d['name']})" for d in rows))
    return hit


def tool_list_demos(args):
    rows = demos.listing(DEMOS)
    return {"text": json.dumps([{"file": d["file"], "name": d["name"], "name_cs": d["name_cs"], "shows": d["text"], "parts": d["parts"]}
                                for d in rows], ensure_ascii=False) if rows else "No demo projects here."}


def tool_open_demo(args):
    d = _demo_named(args.get("name", ""))
    from auto3d.modeler import blobs
    text = _load_project(demos.load(DEMOS, d["file"], blobs.put))
    return {"text": f"Demo “{d['name']}” ({d['name_cs']}) opened as a new project (a copy; the project that was on screen is kept in "
                    f"🕘 Recent projects). {text}"}


def tool_open_sample(args):
    return {"text": _load_in_page(_pdf_data(SAMPLE.read_bytes(), 0, SAMPLE.name))}


def tool_trace_picture(args):
    p = _file(args["path"])
    img = cv2.imdecode(np.frombuffer(p.read_bytes(), np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Not a readable picture.")
    # the same picture the outline editor works on: at most 1600 px
    s = min(1.0, 1600 / max(img.shape[:2]))
    if s < 1:
        img = cv2.resize(img, (round(img.shape[1] * s), round(img.shape[0] * s)), interpolation=cv2.INTER_AREA)
    url = "data:image/png;base64," + base64.b64encode(cv2.imencode(".png", img)[1].tobytes()).decode()
    hints = {**(args.get("hints") or {}), "count": int(args.get("count") or 6)}
    res = detect_outlines(url, hints)
    cands = res["candidates"]
    LAST_TRACE.clear()
    LAST_TRACE.update({"url": url, "w": res["width"], "h": res["height"], "cands": cands, "name": p.name, "hints": hints})
    # one tile per candidate (overlapping outlines would hide each other), numbered, in a grid
    tiles, lines = [], []
    lw = max(2, img.shape[1] // 250)
    for i, c in enumerate(cands, 1):
        tile = img.copy()
        pts = np.concatenate([np.array(poly[0]) for poly in c["polygons"]])
        for poly in c["polygons"]:
            for ring in poly:
                cv2.polylines(tile, [np.round(np.array(ring)).astype(np.int32)], True, (149, 45, 255), lw)
        scale = max(1.0, tile.shape[1] / 400)
        cv2.rectangle(tile, (0, 0), (int(90 * scale), int(40 * scale)), (0, 0, 0), -1)
        cv2.putText(tile, f"#{i}", (int(8 * scale), int(30 * scale)), cv2.FONT_HERSHEY_SIMPLEX, 0.9 * scale, (255, 255, 255), max(2, int(2 * scale)))
        tiles.append(tile)
        x0, y0 = pts.min(0)
        x1, y1 = pts.max(0)
        lines.append(f"{i}. confidence {c['confidence']}%, {round(c['area'] * 100)}% of the picture, "
                     f"box x {x0:.0f}..{x1:.0f} y {y0:.0f}..{y1:.0f} px (aspect {(x1 - x0) / max(y1 - y0, 1):.3f}), "
                     f"{len(c['polygons'])} piece(s), found by {', '.join(c['methods'])}")
    over = img.copy()
    if tiles:
        cols = 1 if len(tiles) == 1 else 2 if len(tiles) <= 4 else 3
        while len(tiles) % cols:
            tiles.append(np.zeros_like(img))
        gap = np.full((img.shape[0], 6, 3), 40, np.uint8)
        rows = [np.hstack(sum(([t, gap] for t in tiles[r:r + cols]), [])[:-1]) for r in range(0, len(tiles), cols)]
        hgap = np.full((6, rows[0].shape[1], 3), 40, np.uint8)
        over = np.vstack(sum(([r, hgap] for r in rows), [])[:-1])
    text = (f"{p.name}: {res['width']} x {res['height']} px, {len(cands)} candidate(s):\n" + "\n".join(lines)
            if cands else "No outline found — give hints (seeds / bg_seeds / rect / colours).")
    return {"text": text, "image": _png_b64(over, 1200)}


def tool_use_outline(args):
    if not LAST_TRACE.get("cands"):
        raise ValueError("Call trace_picture first.")
    n = int(args["candidate"])
    if not 1 <= n <= len(LAST_TRACE["cands"]):
        raise ValueError(f"Candidate {n} does not exist (1..{len(LAST_TRACE['cands'])}).")
    c = LAST_TRACE["cands"][n - 1]
    model = outline_model(c["polygons"], LAST_TRACE["w"], LAST_TRACE["h"], args.get("width"), args.get("height"),
                          args.get("make") or "cutter", LAST_TRACE["name"])
    data = {"model": model, "preview": {"image": LAST_TRACE["url"], "width": LAST_TRACE["w"], "height": LAST_TRACE["h"]}}
    return {"text": _load_in_page(data, {"editor": {"mask": None, "hints": LAST_TRACE["hints"]}})}


def bom_csv(rows, shops) -> bytes:
    """The BOM rows of an assembly -> a CSV for Excel (; separated, UTF-8 with its mark)."""
    from auto3d.modeler.materials import made_how

    def q(v):
        s = "" if v is None else str(v)
        return f'"{s.replace(chr(34), chr(34) * 2)}"' if any(c in s for c in ';"' + LF) else s
    head = ["Pos", "Qty", "Name", "Maker", "Part number", *[f"Order ({s})" for s in shops], "Description", "Material", "Mass each (g)", "Bought / made"]
    lines = [";".join(map(q, head))]
    for i, r in enumerate(rows, start=1):
        mass = "" if r.get("mass_g") is None else str(r["mass_g"]).replace(".", ",")
        lines.append(";".join(map(q, [i, r.get("qty"), r.get("name"), r.get("maker"), r.get("pn"), *[(r.get("order") or {}).get(s, "") for s in shops],
                                       r.get("description"), r.get("material"), mass, r.get("made") or made_how(r)])))
    return ("\ufeff" + "\r\n".join(lines)).encode("utf-8")


def _from_page(fmt):
    """What the page gives for a file the server writes: (bytes, file name)."""
    res = RELAY.call("export_data", {"format": fmt})
    if res.get("error"):
        raise ValueError(res.get("text") or "Nothing to export.")
    d = res.get("data") or {}
    name = re.sub(r'[\\/:*?"<>|]+', "_", d.get("name") or d.get("title") or "export").strip() or "export"
    if fmt == "3mf":
        from auto3d.export3mf import to_3mf
        return to_3mf(d.get("groups") or [], d.get("title") or name), f"{name}.3mf"
    if fmt == "bom":
        return bom_csv(d.get("rows") or [], d.get("shops") or []), f"{name} BOM.csv"
    if d.get("sheet"):  # a drawing sheet: the paper 1:1, its views, real dimensions
        from auto3d.modeler.sheetdxf import to_dxf as sheet_dxf
        sh = d["sheet"]
        return sheet_dxf(str(sh.get("svg") or ""), sh.get("dims") or [], float(sh.get("scale") or 1)), f"{name}.dxf"
    from auto3d.drawing2d import to_dxf
    return to_dxf(d.get("drawing") or {}), f"{name}.dxf"


def tool_export(args):
    fmt = args.get("format", "stl")
    if fmt not in ("stl", "step", "iges", "glb", "obj", "pdf", "3mf", "bom", "dxf", "project"):
        raise ValueError("format: stl, step, iges, glb (glTF with colours), obj, pdf (a 2D drawing of a 3D model), 3mf (with colours), bom (an assembly's CSV), dxf (a 2D drawing or a sheet) or project (the .a3d package)")
    if fmt == "project":  # the whole project as Save project writes it (its imported files in it; its 🕘 history when asked)
        res = RELAY.call("export_data", {"format": "project", "history": bool(args.get("history"))}, timeout=600)
        if res.get("error"):
            raise ValueError(res.get("text") or "No project to save.")
        d = res.get("data") or {}
        p = d.get("project") or {}
        data, missing = _package_of(p, d.get("versions_of"), d.get("thumbnail"))
        name = re.sub(r'[\\/:*?"<>|]+', "_", d.get("name") or "project").strip() or "project"
        target = Path(args["path"]).expanduser() if args.get("path") else Path.home() / "Downloads"
        if target.is_dir() or not target.suffix:
            target.mkdir(parents=True, exist_ok=True)
            target = target / f"{name}.a3d"
        elif target.name.lower().endswith(".json"):  # (an old name, .a3d.json: the file is a package now)
            target = target.with_name(re.sub(r"(\.a3d)?\.json$", "", target.name, flags=re.I) + ".a3d")
        target.write_bytes(data)
        hist = bool(d.get("versions_of") or p.get("versions"))
        return {"text": f"Saved the project ({len(p.get('parts') or [])} parts{', with its version history' if hist else ''}"
                        f"{f'; {len(missing)} imported file(s) were not here and are left out' if missing else ''}; "
                        f"{max(1, len(data) // 1024)} kB) to {target} — open_file opens it again."}
    if fmt == "pdf":  # a drawing sheet on screen: the sheet as it is drawn
        res = RELAY.call("export_data", {"format": "pdf"})
        if not res.get("error") and ((res.get("data") or {}).get("svg") or (res.get("data") or {}).get("svgs")):
            from auto3d.modeler.sheet import pdf as sheet_pdf
            d = res["data"]
            name = re.sub(r'[\\/:*?"<>|]+', "_", d.get("name") or "drawing").strip() or "drawing"
            target = Path(args["path"]).expanduser() if args.get("path") else Path.home() / "Downloads"
            if target.is_dir() or not target.suffix:
                target.mkdir(parents=True, exist_ok=True)
                target = target / f"{name}.pdf"
            data = sheet_pdf(d.get("svgs") or d["svg"])
            target.write_bytes(data)
            what = f"the drawing set, {len(d['svgs'])} pages ({', '.join(d.get('pages') or [])})" if d.get("svgs") else "the drawing sheet"
            return {"text": f"Exported {what} ({max(1, len(data) // 1024)} kB) to {target}"}
    if fmt in ("3mf", "bom", "dxf"):
        data, filename = _from_page(fmt)
        target = Path(args["path"]).expanduser() if args.get("path") else Path.home() / "Downloads"
        if target.is_dir() or not target.suffix:
            target.mkdir(parents=True, exist_ok=True)
            target = target / filename
        target.write_bytes(data)
        return {"text": f"Exported {max(1, len(data) // 1024)} kB to {target}"}
    res = RELAY.call("get_body", {})
    if res.get("error"):
        raise ValueError(res.get("text") or "No part is open.")
    if res["body"].get("assembly"):  # a structured STEP: its parts, placed, sub-assemblies nested
        if fmt not in ASSEMBLY_FILES or not res["body"].get("step_tree"):
            raise ValueError("An assembly exports as step (its parts as an assembly tree), iges (its parts placed, one file), glb (glTF: a node per part, colours), 3mf or bom — STL from the Export menu in the app.")
        name = re.sub(r'[\\/:*?"<>|]+', "_", res["body"].get("name") or "assembly").strip() or "assembly"
        data, err = _model_call("assembly_step", {"tree": res["body"]["step_tree"], "name": name, "fmt": fmt}, timeout=600)
        if err:
            raise ValueError(err[0].get_json().get("error"))
        target = Path(args["path"]).expanduser() if args.get("path") else Path.home() / "Downloads"
        if target.is_dir() or not target.suffix:
            target.mkdir(parents=True, exist_ok=True)
            target = target / f"{name}.{ASSEMBLY_FILES[fmt][1]}"
        target.write_bytes(data)
        what = {"step": "a STEP assembly (AP214: a product per part, sub-assemblies nested)",
                "iges": "one IGES file (every part placed, with names and colours; IGES has no assembly tree)",
                "glb": "a binary glTF (a node per placed part with its name, sub-assemblies nested, colours and materials; metres, Y up)"}[fmt]
        return {"text": f"Exported the assembly as {what} — {max(1, len(data) // 1024)} kB to {target}"}
    if res["body"].get("model_part") is not None:  # a 3D model part: the CAD kernel writes it
        name = re.sub(r'[\\/:*?"<>|]+', "_", res["body"].get("name") or "part").strip()
        data, err = _model_call("export", {"part": res["body"]["model_part"], "fmt": fmt, "name": name})
        if err:
            raise ValueError(err[0].get_json().get("error"))
        filename = f"{name}.{MODEL_FILES[fmt][1]}"
    elif fmt == "pdf":
        raise ValueError("A 2D drawing is made from a 3D model part — open one (or ◆ To 3D model) first.")
    elif fmt in ("iges", "glb", "obj"):
        raise ValueError(f"{fmt.upper()} is written from a 3D model part or an assembly — for a quick part use step or stl (GLB: the Export menu).")
    else:
        data, filename, _ = _export_bytes(res["body"], fmt)
    target = Path(args["path"]).expanduser() if args.get("path") else Path.home() / "Downloads"
    if target.is_dir() or not target.suffix:
        target.mkdir(parents=True, exist_ok=True)
        target = target / filename
    target.write_bytes(data)
    return {"text": f"Exported {len(data) // 1024} kB to {target}"}


REPORTS = Path(__import__("os").environ.get("A3D_REPORTS") or (DATA if getattr(__import__("sys"), "frozen", False) else ROOT) / "RealSWReports")  # the AI's reports of things that did not behave as expected (the built app: in the user's data; A3D_REPORTS: a test server's)


def _report_attachments(args: dict) -> tuple[dict | None, dict | None, bytes | None]:
    """(the project, the ⏺ recording, the project's picture) to go with a report: given in args (a test), else asked
    from the page — the project as Save project writes it and a recording running or stopped in the last 30 min. None:
    none / no page."""
    if "project" in args or "recording" in args:
        return args.get("project") or None, args.get("recording") or None, None
    try:
        got = RELAY.call("report_attachments", {}, timeout=60)
    except Exception:  # (no page open, an older page: the report is written without them)
        return None, None, None
    proj, rec = got.get("project"), got.get("recording")
    return ((proj if isinstance(proj, dict) and proj.get("parts") else None), (rec if isinstance(rec, dict) and rec.get("events") else None),
            _png_of(got.get("thumbnail")))


# the AI's screenshots in this conversation (get_screenshot's pictures, by the window whose chat took them): a report
# can attach "last" (what the AI just looked at) or one by its id (s3)
SHOTS: dict[str, list[tuple[str, str]]] = {}  # client -> [(id, base64 picture)], the oldest first
SHOTS_KEPT, SHOT_IDS = 12, __import__("itertools").count(1)


def _keep_shot(image: str, client: str) -> str:
    """Remember one of the AI's screenshots (of the window `client`'s chat) -> its id (s1, s2 …)."""
    sid = f"s{next(SHOT_IDS)}"
    kept = SHOTS.setdefault(client, [])
    kept.append((sid, image))
    del kept[:-SHOTS_KEPT]
    return sid


def _shot_file(image: str) -> tuple[bytes, str]:
    """A screenshot (base64 PNG / JPEG) as a report's picture file -> (its bytes, ".png" / ".webp"): at most
    reports.SHOT_PX across, under about reports.SHOT_BYTES (a PNG, else a WebP, smaller until it fits)."""
    from auto3d import reports
    img = cv2.imdecode(np.frombuffer(base64.b64decode(image.split(",")[-1]), np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("not a picture")
    while True:
        s = min(1.0, reports.SHOT_PX / max(img.shape[:2]))
        if s < 1:
            img = cv2.resize(img, (round(img.shape[1] * s), round(img.shape[0] * s)), interpolation=cv2.INTER_AREA)
        data = cv2.imencode(".png", img, [cv2.IMWRITE_PNG_COMPRESSION, 9])[1].tobytes()
        if len(data) <= reports.SHOT_BYTES:
            return data, ".png"
        for q in (90, 75, 60):
            data = cv2.imencode(".webp", img, [cv2.IMWRITE_WEBP_QUALITY, q])[1].tobytes()
            if len(data) <= reports.SHOT_BYTES:
                return data, ".webp"
        img = cv2.resize(img, (img.shape[1] * 3 // 4, img.shape[0] * 3 // 4), interpolation=cv2.INTER_AREA)


SHOT_NAMES = {"ui": "the whole window", "view": "the view", "last": "the AI's last screenshot"}


def _report_shots(args: dict) -> tuple[list[tuple[str, str]], list[str]]:
    """report_problem's screenshots -> ([(base64 picture, caption)], notes on what could not be attached). Each item:
    "ui" / "view" (taken now by the page, as get_screenshot takes them), "last" / an id ("s3": one the AI took), or
    {shot, caption}; {image: base64} gives the picture itself (a test)."""
    from auto3d import reports
    items = args.get("screenshots") or []
    items = [items] if isinstance(items, (str, dict)) else items if isinstance(items, list) else []
    items = [it if isinstance(it, dict) else {"shot": str(it)} for it in items]
    notes = [f"only {reports.SHOTS_MAX} screenshots go with a report — the rest left out"] if len(items) > reports.SHOTS_MAX else []
    items = items[:reports.SHOTS_MAX]
    kept, got = SHOTS.get(ROUTE.get() or "", []), {}
    live = [str(it.get("shot") or "").strip().lower() for it in items if not it.get("image") and str(it.get("shot") or "").strip().lower() in ("ui", "view")]
    if live:  # (the page takes them in one go, the AI's last picture left as it was)
        try:
            res = RELAY.call("report_shots", {"shots": live}, timeout=60).get("images") or []
        except Exception as exc:  # (no page open)
            res = [{"error": str(exc).rstrip(".")}] * len(live)
        got = dict(enumerate(res))
    out, n = [], 0
    for it in items:
        shot = str(it.get("shot") or "").strip()
        caption = re.sub(r"[\[\]\s]+", " ", str(it.get("caption") or "")).strip()[:200]
        if it.get("image"):
            image = str(it["image"])
        elif shot.lower() in ("ui", "view"):
            r = got.get(n) or {}
            n += 1
            image = r.get("image") if isinstance(r, dict) else None
            if not image:
                notes.append(f"{shot}: {r.get('error') if isinstance(r, dict) and r.get('error') else 'no picture'}")
                continue
        elif shot.lower() == "last" or re.fullmatch(r"s\d+", shot.lower()):
            hit = kept[-1:] if shot.lower() == "last" else [k for k in kept if k[0] == shot.lower()]
            if not hit:
                notes.append(f"{shot}: " + (f"no such screenshot (yours: {', '.join(k[0] for k in kept)})" if kept else "you have taken no get_screenshot yet"))
                continue
            image = hit[0][1]
            if shot.lower() == "last":
                shot = hit[0][0]
        else:
            notes.append(f"{shot or '?'}: not a screenshot — \"ui\", \"view\", \"last\" or an id (s3)")
            continue
        out.append((image, caption or SHOT_NAMES.get(shot.lower(), f"the AI's screenshot {shot}")))
    return out, notes


def _shown(path: Path) -> str:
    """A report's file as said to the AI: from the app's folder when it is in it."""
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def tool_report_problem(args):
    """A dated report (Markdown) of something that did not behave as expected -> RealSWReports/<date>-<title>.md."""
    title = str(args.get("title") or "").strip()[:120]
    what = str(args.get("what") or "").strip()
    if not title or not what:
        raise ValueError("A report needs a title and what happened.")
    from auto3d import reports
    same = [] if args.get("again") else reports.similar(REPORTS, title)
    if same:  # (one thing reported twice is noise for the developers)
        listed = "; ".join(f"“{r['title']}” ({r['kind']}, {r['date']}, {r['file']})" for r in same)
        return {"text": f"Not written — a similar report exists: {listed}. If it is the same problem, tell the user it is reported "
                        f"already and carry on. Only if yours is really another one, call report_problem again with again: true "
                        f"and a title that says how it differs."}
    now = time.localtime()
    kind = str(args.get("kind") or "bug").strip().lower()
    kind = kind if kind in ("bug", "tool request", "ui") else "bug"
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower().encode("ascii", "ignore").decode()).strip("-")[:60] or "report"
    REPORTS.mkdir(parents=True, exist_ok=True)
    path = REPORTS / f"{time.strftime('%Y-%m-%d-%H%M%S', now)}-{'request-' if kind == 'tool request' else 'ui-' if kind == 'ui' else ''}{slug}.md"
    from auto3d import version
    parts = [f"# {title}", "", f"- **Kind:** {kind}", f"- **Date:** {time.strftime('%Y-%m-%d %H:%M:%S', now)}", f"- **App version:** {version.text(PAGE_BUILDS.get(ROUTE.get() or '') or PAGE_BUILDS.get('', ''))}",
             "- **Reported by:** the AI agent (MCP report_problem)"]
    # the project on screen (compacted) and a recent ⏺ recording next to it, so someone else can reproduce the problem
    proj, rec, pic = _report_attachments(args)
    attached = []
    if proj:
        from auto3d.modeler import blobs
        data, left = reports.compact_project(proj, blobs.get, thumbnail=pic or _box_png())  # (its imported files from the store, binary)
        att = path.with_name(path.stem + reports.PROJECT_EXT)
        att.write_bytes(data)
        attached.append("the project")
        names = ", ".join(str(q.get("name") or q.get("id") or "?") for q in proj["parts"])
        out = "; ".join(f"{x['name'] or x['blob'][:12]} ({x['bytes'] // 1024} kB)" for x in left)
        parts.append(f"- **Project:** `{att.name}` (open it in the app: 📂 Open ▾ › File…) — {len(proj['parts'])} part(s): {names}; "
                     f"{max(1, len(data) // 1024)} kB" + (f"; imported files left out: {out}" if left else ""))
    if rec:
        att = path.with_name(path.stem + reports.RECORDING_EXT)
        rec = {k: v for k, v in rec.items() if k != "shots"}  # (the events only — no screenshots)
        att.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
        attached.append("the recording of moves")
        parts.append(f"- **Recording:** `{att.name}` (⏺ the user's moves: {len(rec['events'])} events over {rec.get('seconds', 0)} s, "
                     f"{'still running' if rec.get('running') else 'stopped'}; without screenshots)")
    # screenshots the AI chose (the state of the app: a missing button, a glitch): <base>.shot-1.png … shown in the .md
    shots, notes = _report_shots(args)
    pics = []
    for image, caption in shots:
        try:
            data, ext = _shot_file(image)
        except Exception as exc:  # (not a picture)
            notes.append(f"{caption}: {exc}")
            continue
        att = path.with_name(f"{path.stem}{reports.SHOT_EXT}{len(pics) + 1}{ext}")
        att.write_bytes(data)
        pics.append((att.name, caption))
    if pics:
        attached.append(f"{len(pics)} screenshot{'s' if len(pics) > 1 else ''}")
        parts.append(f"- **Screenshots:** {len(pics)} (below): " + ", ".join(f"`{n}`" for n, _ in pics))
    parts += ["", "## What happened", "", what]
    for key, head in (("expected", "What was expected"), ("steps", "Steps"), ("workaround", "Workaround")):
        if str(args.get(key) or "").strip():
            parts += ["", f"## {head}", "", str(args[key]).strip()]
    if pics:
        parts += ["", "## Screenshots"]
        for i, (name, caption) in enumerate(pics, 1):
            parts += ["", f"![{caption}]({name})", f"*{i}. {caption}*"]
    path.write_text(LF.join(parts) + LF, encoding="utf-8")
    with_ = f" — with {', '.join(attached[:-1])} and {attached[-1]}" if len(attached) > 1 else f" — with {attached[0]}" if attached else ""
    left = f" Not attached: {'; '.join(notes)}." if notes else ""
    return {"text": f"Reported: {_shown(path)}{with_} — thank you.{left} Tell the user, then carry on."}


def tool_list_reports(args):
    """The problem reports written so far (newest first): those of a kind, those sharing a word with `search`."""
    from auto3d import reports
    kind = str(args.get("kind") or "").strip().lower()
    rows = reports.search(REPORTS, str(args.get("search") or ""), kind if kind in ("bug", "tool request", "ui") else "")
    if not rows:
        return {"text": "No reports" + (" match" if args.get("search") or kind else " yet") + "."}
    return {"text": json.dumps([{"title": r["title"], "kind": r["kind"], "date": r["date"], **({"project": r["project"]} if r["project"] else {}),
                                 **({"recording": r["recording"]} if r["recording"] else {}),
                                 **({"screenshots": r["shots"]} if r["shots"] else {})} for r in rows], ensure_ascii=False)}


def _solid_from_path(args: dict) -> dict:
    """add_feature {type: "solid", path}: the file read as ▣ Solid from a file reads it (/api/model/import) — into the
    blob store, a mesh / IGES made a STEP — and handed to the page as the step's blob and file name."""
    from auto3d.modeler import blobs
    p = _file(args["path"])
    if p.suffix.lower() not in (".step", ".stp", ".igs", ".iges", ".stl", ".obj", ".3mf"):
        raise ValueError("path: a STEP / IGES / STL / OBJ / 3MF file.")
    res, err = _model_call("import_solid", {"blob": blobs.put(p.read_bytes()), "name": p.name}, timeout=600)
    if err:
        raise ValueError(err[0].get_json().get("error") or "The file could not be read.")
    out = {k: v for k, v in args.items() if k != "path"}
    out.update({"blob": res["blob"], "file": p.name, **({"warning": res["warning"]} if res.get("warning") else {})})
    if res.get("op") == "ref":  # (an IGES whose surfaces do not close: a reference body only)
        out["op"] = "ref"
    return out


SERVER_TOOLS = {"open_file": tool_open_file, "report_problem": tool_report_problem, "list_reports": tool_list_reports, "open_sample": tool_open_sample, "trace_picture": tool_trace_picture,
                "use_outline": tool_use_outline, "export": tool_export, "list_demos": tool_list_demos, "open_demo": tool_open_demo}


PAGE_BUILDS: dict[str, str] = {}  # window (client id) -> the commit its page was loaded with ("": the latest any said)


@app.get("/api/version")
def api_version():
    """The app's version and the git commit it runs from; head: the checkout's commit now, stale: true when it moved
    on since the server started (the page shows ⟳ New version — restart the app)."""
    from auto3d import version
    return jsonify({**version.build(), "text": version.text(), "head": version.head(), "stale": bool(version.stale())})


@app.post("/api/agent/call")
def api_agent_call():
    """An MCP tool call (from auto3d/mcp_server.py). {client}: the window whose chat made it — what it does to the
    page (also through a server tool: open_file …) goes to that window only."""
    body = request.get_json(force=True)
    tool, args = body.get("tool", ""), body.get("args") or {}
    if tool not in TOOL_NAMES:  # listed: the MCP server (newer code, started by the chat) knows it — this server is older
        return jsonify(_mcp_result(OLDER_SERVER.format(tool=tool) if body.get("listed") else f"Unknown tool {tool}.", error=True))
    route = ROUTE.set(str(body.get("client") or "") or None)
    try:
        if tool == "add_feature" and args.get("type") == "solid" and args.get("path"):
            args = _solid_from_path(args)
        res = RELAY.call(tool, args) if tool in BROWSER_TOOLS else SERVER_TOOLS[tool](args)
    except Exception as exc:  # report to the agent instead of failing the call
        return jsonify(_mcp_result(f"{tool} failed: {exc}", error=True))
    finally:
        ROUTE.reset(route)
    text = res.get("text", "")
    if tool == "get_screenshot" and res.get("image"):  # (kept: report_problem can attach it — "last" or its id)
        text += f"\n(Screenshot {_keep_shot(res['image'], str(body.get('client') or ''))}: report_problem screenshots can attach it.)"
    return jsonify(_mcp_result(text, res.get("image"), bool(res.get("error"))))


def _hung_up(environ) -> bool:
    """True when the page closed this request's connection (it reloaded, or aborted the fetch): the socket reads as
    ended. False when that cannot be told (no socket in this server)."""
    import select
    import socket
    sock = environ.get("werkzeug.socket")
    if sock is None:
        return False
    try:
        if not select.select([sock], [], [], 0)[0]:
            return False
        return sock.recv(1, socket.MSG_PEEK) == b""
    except (OSError, ValueError):
        return True


@app.get("/api/agent/poll")
def api_agent_poll():
    """The page long-polls for tool calls to apply. ?build=: the commit the page was loaded with (said in reports).
    It ends as soon as the page hangs up (a reload), not after its 20 s: no call is taken by a page that is gone."""
    if request.args.get("build"):
        PAGE_BUILDS[request.args.get("client") or ""] = PAGE_BUILDS[""] = request.args["build"][:40]
    env = request.environ
    cmd = RELAY.poll(20.0, request.args.get("client") or None, request.args.get("active", "1") == "1", lambda: _hung_up(env))
    return jsonify(cmd) if cmd else ("", 204)


@app.post("/api/agent/bye")
def api_agent_bye():
    """?client=: the window is closing (a beacon from the page) — its chat's calls fail from now on unless it comes
    back at once (a reload)."""
    if request.args.get("client"):
        RELAY.bye(request.args["client"])
    return jsonify({"ok": True})


@app.post("/api/agent/alive")
def api_agent_alive():
    """?client=: the window is there — running a long tool call, it does not poll meanwhile."""
    if request.args.get("client"):
        RELAY.alive(request.args["client"])
    return jsonify({"ok": True})


@app.post("/api/agent/result")
def api_agent_result():
    body = request.get_json(force=True)
    RELAY.resolve(body.get("id", ""), body.get("result") or {})
    return jsonify({"ok": True})


@app.get("/api/chat/status")
def api_chat_status():
    chat = _chat(_client())
    return jsonify({"claude": find_claude(), "running": chat.running(), "busy": chat.busy,
                    "conversation": getattr(chat, "conv_meta", lambda: None)()})


@app.get("/api/ai/access")
def api_ai_access():
    """How the chat reaches Claude (auto3d/ai_access.py): no_claude / signed_out / invalid / ok — the ✨ AI panel's
    set-up screen, at any time while the app runs."""
    from auto3d import ai_access
    return jsonify(ai_access.state())


@app.post("/api/ai/key")
def api_ai_key():
    """{key}: an Anthropic API key, checked with Anthropic first; kept (DPAPI) when it works or cannot be checked
    (offline), refused when Anthropic refuses it. The chat restarts with it at the next message."""
    from auto3d import ai_access
    key = str((request.get_json(force=True) or {}).get("key") or "").strip()
    if not ai_access.looks_like_key(key):
        return jsonify({"error": "This is not an Anthropic API key (it starts with sk-ant-).", "code": "invalid"}), 400
    got = ai_access.check_key(key)
    if got == "invalid":
        return jsonify({"error": "Anthropic refused this key (wrong, revoked or expired).", "code": "invalid"}), 400
    ai_access.save_key(key)
    stop_chats()
    return jsonify({**ai_access.state(), "checked": got == "ok"})


@app.post("/api/ai/login")
def api_ai_login():
    """Claude Code's sign-in in a window of its own ({console: true}: the Anthropic Console's); poll /api/ai/access."""
    from auto3d import ai_access
    exe = find_claude()
    if not exe:
        return jsonify({"error": "Claude Code is not installed.", "code": "no_claude"}), 400
    try:
        ai_access.start_login(exe, bool((request.get_json(silent=True) or {}).get("console")))
    except OSError as exc:
        return jsonify({"error": f"The sign-in could not start ({exc})."}), 500
    stop_chats()
    return jsonify(ai_access.state())


@app.post("/api/ai/logout")
def api_ai_logout():
    """Forget the stored key; {claude: true}: also sign Claude Code out (all its uses on this computer)."""
    from auto3d import ai_access
    ai_access.forget_key()
    exe = find_claude()
    if exe and (request.get_json(silent=True) or {}).get("claude"):
        ai_access.logout_claude(exe)
    stop_chats()
    return jsonify(ai_access.state())


CHAT_PHOTOS = DATA / "agent" / "photos"
CHAT_PHOTO_TYPES = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp", "image/gif": ".gif"}
MAX_CHAT_PHOTOS, MAX_CHAT_PHOTO_BYTES = 5, 10 * 1024 * 1024


def _save_chat_photo(p):
    """A photo attached to a chat message ({name, data: data URL}) -> saved under data/agent/photos, so Claude
    can also trace it; returns what ChatSession.send needs."""
    m = re.match(r"^data:(image/[\w.+-]+);base64,(.+)$", p.get("data") or "", re.S)
    if not m or m.group(1) not in CHAT_PHOTO_TYPES:
        raise ValueError(f"{p.get('name') or 'The file'} is not a photo (PNG, JPG, WEBP or GIF).")
    raw = base64.b64decode(m.group(2))
    if len(raw) > MAX_CHAT_PHOTO_BYTES:
        raise ValueError(f"{p.get('name') or 'The photo'} is larger than 10 MB.")
    stem = re.sub(r"[^\w.-]+", "_", Path(p.get("name") or "photo").stem)[:40] or "photo"
    name = f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}-{stem}{CHAT_PHOTO_TYPES[m.group(1)]}"
    CHAT_PHOTOS.mkdir(parents=True, exist_ok=True)
    (CHAT_PHOTOS / name).write_bytes(raw)
    return {"name": p.get("name") or name, "media_type": m.group(1), "data": base64.b64encode(raw).decode("ascii"),
            "path": str(CHAT_PHOTOS / name), "url": f"/api/chat/photo/{name}"}


@app.get("/api/chat/photo/<name>")
def api_chat_photo(name):
    return send_from_directory(CHAT_PHOTOS, name)


@app.post("/api/chat/send")
def api_chat_send():
    body = request.get_json(force=True)
    text = (body.get("text") or "").strip()
    try:
        photos = [_save_chat_photo(p) for p in (body.get("photos") or [])[:MAX_CHAT_PHOTOS]]
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    if not text and not photos:
        return jsonify({"error": "Empty message."}), 400
    try:
        chat = _chat(_client())
        if isinstance(body.get("project"), dict):  # (the project on the page: a new conversation is about it)
            chat.project = {"id": str(body["project"].get("id") or ""), "name": str(body["project"].get("name") or "")}
        chat.send(text, photos)
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"ok": True})


@app.post("/api/chat/stop")
def api_chat_stop():
    _chat(_client()).stop()
    return jsonify({"ok": True})


@app.post("/api/chat/reset")
def api_chat_reset():
    _chat(_client()).reset()
    return jsonify({"ok": True})


@app.get("/api/chat/conversations")
def api_chat_conversations():
    """🕘 Previous conversations: their meta, the last changed first ({conversations, current: this window's id})."""
    chat = _chat(_client())
    return jsonify({"conversations": chat_history.list_convs(CHAT_STORE), "current": (chat.conv or {}).get("id")})


@app.post("/api/chat/open")
def api_chat_open():
    """{id, client}: the kept conversation in this window's chat again — the next message goes on with it."""
    body = request.get_json(force=True, silent=True) or {}
    try:
        _chat(_client()).open(str(body.get("id") or ""))
    except (chat_history.ChatHistoryError, ValueError) as e:
        return jsonify({"error": str(e)}), 404
    return jsonify({"ok": True})


@app.delete("/api/chat/conversations/<cid>")
def api_chat_delete(cid):
    """A kept conversation deleted (a window that has it on screen starts a new one)."""
    try:
        chat_history.delete(CHAT_STORE, cid)
    except chat_history.ChatHistoryError as e:
        return jsonify({"error": str(e)}), 404
    for chat in list(CHATS.values()):
        if (chat.conv or {}).get("id") == cid:
            chat.reset()
    return jsonify({"ok": True})


@app.get("/api/chat/events")
def api_chat_events():
    """Server-Sent Events: the chat (history first, then live)."""
    chat = _chat(_client())
    q = chat.subscribe()

    def gen():
        try:
            yield "retry: 2000\n\n"
            while True:
                try:
                    ev = q.get(timeout=15)
                    yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
                except queue.Empty:
                    yield ": keep-alive\n\n"
        finally:
            chat.unsubscribe(q)

    return Response(stream_with_context(gen()), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=5173)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()
    url = f"http://127.0.0.1:{args.port}"
    global APP_URL
    APP_URL = url  # the MCP server started by the chat calls back here
    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    print(f"Auto3DModeler running at {url}")
    MODEL_WORKER.warm()  # (the kernel processes started now, not by the first part opened)
    app.run(host="127.0.0.1", port=args.port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
