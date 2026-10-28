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
from auto3d.agent import ChatSession, Relay, find_claude
from auto3d.ai_history import HistoryError, delete_state, list_states, load_state, save_state
from auto3d import library as parts_library
from auto3d import autosave
from auto3d.agent_tools import BROWSER_TOOLS, TOOL_NAMES
from auto3d.bend import bend_info, bend_solid
from auto3d.design import profile_polygon, trace_image
from auto3d.export import build_solid, mesh_payload, to_step, to_stl
from auto3d.extract import render_page_png
from auto3d.joints import joint_catalog
from auto3d.importers import DRAWING_FORMATS, MESH_FORMATS, ImportError_, dwg_to_dxf, read_dxf
from auto3d.meshpart import mesh_model, register, solve_mesh
from auto3d.outline import add_objects, apply_shapes, detect_outlines, outline_from_mask, outline_model, preset_objects, solve_outline
from auto3d.modeler import status as modeler_status
from auto3d.modeler.worker import WORKER as MODEL_WORKER, KernelFailed, KernelUnavailable
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


PROJECTS = DATA / "projects"  # autosave: the projects kept on the server (auto3d/autosave.py)


@app.post("/api/projects/<pid>")
def api_project_autosave(pid):
    """{project} -> kept as the project's latest state -> its meta."""
    body = request.get_json(force=True, silent=True) or {}
    try:
        return jsonify(autosave.save(PROJECTS, pid, body.get("project")))
    except autosave.AutosaveError as e:
        return jsonify({"error": str(e)}), 400


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
    except autosave.AutosaveError as e:
        return jsonify({"error": str(e)}), 404
    return jsonify({"ok": True})


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
    """Whether the optional 3D model workspace packages (CAD kernel, sketch solver) are installed."""
    return jsonify(modeler_status())


@app.post("/api/solve")
def api_solve():
    body = request.get_json(force=True)
    with progress.operation(body.get("rid")):
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
    """DXF / DWG -> outline model (real size); STL / OBJ / STEP -> mesh model (sliced)."""
    f = request.files.get("file")
    if f is None:
        return jsonify({"error": "No file uploaded."}), 400
    name, data = f.filename or "part", f.read()
    try:
        with progress.operation(request.form.get("rid")):
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
    raise ValueError(f"Unsupported file type {ext} (PDF, DXF, DWG, STL, OBJ, STEP).")


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
    body = request.get_json(force=True)
    model, solution, final, solid, bender = _solve_full(body)
    if solid is None:
        return jsonify({"error": "The model is invalid."}), 400
    if bender is None and body.get("bends") and not solution.get("design_ok", True):
        return jsonify({"error": " ".join(i["message"] for i in solution["design_issues"] if i["severity"] == "error")}), 400
    try:
        result = _plan(body, solid, model, bender, final)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    # the preview shows bent pieces / connectors in their assembled position
    for p in result["pieces"]:
        solid_p = p.pop("solid")
        p["mesh"] = mesh_payload(p.pop("assembled", solid_p))
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
    """Run a kernel op in the worker process -> (result, None) or (None, error response)."""
    try:
        return MODEL_WORKER.run(op, arg, timeout), None
    except KernelUnavailable as exc:
        return None, (jsonify({"error": str(exc), "install": "py -m pip install -r requirements-modeler.txt"}), 501)
    except KernelFailed as exc:
        return None, (jsonify({"error": str(exc)}), 500)


@app.post("/api/model/rebuild")
def api_model_rebuild():
    """{part, rid} -> the body (mesh with one face id per triangle, faces, edges), each feature's status."""
    body = request.get_json(force=True)
    try:
        with progress.operation(body.get("rid")):
            res, err = _model_call("rebuild", body.get("part") or {})
    except progress.Cancelled:
        return jsonify({"cancelled": True})
    if err:
        return err
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
    """A STEP / STL / OBJ file -> a solid step for a 3D model: {blob, faces, bbox, volume} (form: file, rid)."""
    from auto3d.modeler import blobs
    f = request.files.get("file")
    if f is None:
        return jsonify({"error": "No file uploaded."}), 400
    name = f.filename or "part.step"
    try:
        with progress.operation(request.form.get("rid")):
            progress.report(f"Reading {name}")
            sha = blobs.put(f.read())
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
    try:
        with progress.operation(body.get("rid")):
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
    data, err = _model_call("assembly_clashes", {"instances": body.get("instances") or [], "quick": bool(body.get("quick"))})
    if err:
        return err
    return jsonify({"clashes": data})


@app.post("/api/sheet/build")
def api_sheet_build():
    """{part, preset: light | medium | full, paper} -> {geometry (views, points), layout, dims} — a drawing sheet."""
    body = request.get_json(force=True)
    data, err = _model_call("sheet", {"part": body.get("part") or {}, "preset": body.get("preset") or "medium", "paper": body.get("paper"),
                                      "per_view": body.get("per_view") or {}, "section": bool(body.get("section"))})
    if err:
        return err
    return jsonify(data)


@app.post("/api/sheet/assembly")
def api_sheet_assembly():
    """{instances (placed, as for clashes), paper} -> {geometry, layout, dims, marks} — an assembly's drawing sheet."""
    body = request.get_json(force=True)
    data, err = _model_call("assembly_sheet", {"instances": body.get("instances") or [], "paper": body.get("paper"), "explode": body.get("explode") or 0})
    if err:
        return err
    return jsonify(data)


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


@app.post("/api/assembly/sweep")
def api_assembly_sweep():
    """{instances: [...as for clashes, at the start], steps: [{at, matrices: {id: [16]}}]} -> {steps: [{at, clashes}]}
    — the collisions of the moving parts at each step of a motion."""
    body = request.get_json(force=True)
    steps = (body.get("steps") or [])[:200]
    data, err = _model_call("assembly_sweep", {"instances": body.get("instances") or [], "steps": steps})
    if err:
        return err
    return jsonify({"steps": data})


@app.post("/api/assembly/export/step")
def api_assembly_step():
    """{instances: [{part: {features}, matrix: [16]}], name} -> one STEP file with every placed part."""
    body = request.get_json(force=True)
    data, err = _model_call("assembly_step", {"instances": body.get("instances") or []})
    if err:
        return err
    name = re.sub(r'[\/:*?"<>|]+', "_", body.get("name") or "assembly").strip() or "assembly"
    return Response(data, mimetype="model/step", headers={"Content-Disposition": attachment(f"{name}.step")})


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
    """{part: {features}, id} -> {field: [min, max]}: the values each number of that step can take."""
    body = request.get_json(force=True)
    data, err = _model_call("limits", {"features": (body.get("part") or {}).get("features") or [], "id": body.get("id")})
    if err:
        return err
    return jsonify(data)


@app.post("/api/model/export/<fmt>")
def api_model_export(fmt):
    if fmt not in ("stl", "step", "pdf"):
        return jsonify({"error": f"Unknown format {fmt}"}), 404
    body = request.get_json(force=True)
    name = re.sub(r'[\\/:*?"<>|]+', "_", body.get("name") or "part").strip() or "part"
    data, err = _model_call("export", {"part": body.get("part") or {}, "fmt": fmt, "name": name})
    if err:
        return err
    return Response(data, mimetype={"step": "model/step", "stl": "model/stl", "pdf": "application/pdf"}[fmt],
                    headers={"Content-Disposition": attachment(f"{name}.{fmt}")})


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

    if body.get("split") and body.get("printer"):
        result = _plan(body, solid, model, bender, final)
        if not result["pieces"]:
            raise ValueError(" ".join(i["message"] for i in result["issues"]) or "Nothing to export.")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for p in result["pieces"]:
                pname = f"{name}_part{p['index']}"
                piece = p["solid"].flipped() if p["flip"] else p["solid"]
                z.writestr(f"{pname}.{fmt}", writer(piece.at_origin(), model["unit"], pname))
            for k, g in enumerate(result.get("connectors", []), 1):
                cname = f"{name}_{g['kind']}{k}_x{g['qty']}"
                z.writestr(f"{cname}.{fmt}", writer(g["instances"][0]["solid"].at_origin(), model["unit"], cname))
            z.writestr("ASSEMBLY.txt", assembly_text(result, name))
        return buf.getvalue(), f"{name}_{fmt}_pieces.zip", "application/zip"
    return writer(final, model["unit"], name), f"{name}.{fmt}", mime


# --------------------------------------------------------------------------- AI agent (MCP tools + chat)
RELAY = Relay()
CHAT: ChatSession | None = None
APP_URL = "http://127.0.0.1:5173"
LAST_TRACE: dict = {}
PICTURE_FORMATS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff"}


def _chat() -> ChatSession:
    global CHAT
    if CHAT is None:
        CHAT = ChatSession(APP_URL)
    return CHAT


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
    def q(v):
        s = "" if v is None else str(v)
        return f'"{s.replace(chr(34), chr(34) * 2)}"' if any(c in s for c in ';"' + LF) else s
    head = ["Pos", "Qty", "Name", "Maker", "Part number", *[f"Order ({s})" for s in shops], "Description", "Material", "Mass each (g)", "Bought / made"]
    lines = [";".join(map(q, head))]
    for i, r in enumerate(rows, start=1):
        mass = "" if r.get("mass_g") is None else str(r["mass_g"]).replace(".", ",")
        lines.append(";".join(map(q, [i, r.get("qty"), r.get("name"), r.get("maker"), r.get("pn"), *[(r.get("order") or {}).get(s, "") for s in shops],
                                       r.get("description"), r.get("material"), mass, "bought" if r.get("library") else "made (3D print)"])))
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
    from auto3d.drawing2d import to_dxf
    return to_dxf(d.get("drawing") or {}), f"{name}.dxf"


def tool_export(args):
    fmt = args.get("format", "stl")
    if fmt not in ("stl", "step", "pdf", "3mf", "bom", "dxf"):
        raise ValueError("format: stl, step, pdf (a 2D drawing of a 3D model), 3mf (with colours), bom (an assembly's CSV) or dxf (a 2D drawing)")
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
    if res["body"].get("assembly"):
        raise ValueError("Export an assembly with the Export menu in the app (STL or STEP).")
    if res["body"].get("model_part") is not None:  # a 3D model part: the CAD kernel writes it
        name = re.sub(r'[\\/:*?"<>|]+', "_", res["body"].get("name") or "part").strip()
        data, err = _model_call("export", {"part": res["body"]["model_part"], "fmt": fmt, "name": name})
        if err:
            raise ValueError(err[0].get_json().get("error"))
        filename = f"{name}.{fmt}"
    elif fmt == "pdf":
        raise ValueError("A 2D drawing is made from a 3D model part — open one (or ◆ To 3D model) first.")
    else:
        data, filename, _ = _export_bytes(res["body"], fmt)
    target = Path(args["path"]).expanduser() if args.get("path") else Path.home() / "Downloads"
    if target.is_dir() or not target.suffix:
        target.mkdir(parents=True, exist_ok=True)
        target = target / filename
    target.write_bytes(data)
    return {"text": f"Exported {len(data) // 1024} kB to {target}"}


REPORTS = ROOT / "RealSWReports"  # the AI's reports of things that did not behave as expected


def tool_report_problem(args):
    """A dated report (Markdown) of something that did not behave as expected -> RealSWReports/<date>-<title>.md."""
    title = str(args.get("title") or "").strip()[:120]
    what = str(args.get("what") or "").strip()
    if not title or not what:
        raise ValueError("A report needs a title and what happened.")
    now = time.localtime()
    kind = str(args.get("kind") or "bug").strip().lower()
    kind = kind if kind in ("bug", "tool request", "ui") else "bug"
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower().encode("ascii", "ignore").decode()).strip("-")[:60] or "report"
    REPORTS.mkdir(parents=True, exist_ok=True)
    path = REPORTS / f"{time.strftime('%Y-%m-%d-%H%M%S', now)}-{'request-' if kind == 'tool request' else 'ui-' if kind == 'ui' else ''}{slug}.md"
    from auto3d import version
    parts = [f"# {title}", "", f"- **Kind:** {kind}", f"- **Date:** {time.strftime('%Y-%m-%d %H:%M:%S', now)}", f"- **App version:** {version.text()}",
             "- **Reported by:** the AI agent (MCP report_problem)", "",
             "## What happened", "", what]
    for key, head in (("expected", "What was expected"), ("steps", "Steps"), ("workaround", "Workaround")):
        if str(args.get(key) or "").strip():
            parts += ["", f"## {head}", "", str(args[key]).strip()]
    path.write_text(LF.join(parts) + LF, encoding="utf-8")
    return {"text": f"Reported: {path.relative_to(ROOT).as_posix()} — thank you. Tell the user, then carry on."}


SERVER_TOOLS = {"open_file": tool_open_file, "report_problem": tool_report_problem, "open_sample": tool_open_sample, "trace_picture": tool_trace_picture,
                "use_outline": tool_use_outline, "export": tool_export}


@app.get("/api/version")
def api_version():
    """The app's version and the git commit it runs from."""
    from auto3d import version
    return jsonify({**version.build(), "text": version.text()})


@app.post("/api/agent/call")
def api_agent_call():
    """An MCP tool call (from auto3d/mcp_server.py)."""
    body = request.get_json(force=True)
    tool, args = body.get("tool", ""), body.get("args") or {}
    if tool not in TOOL_NAMES:
        return jsonify(_mcp_result(f"Unknown tool {tool}.", error=True))
    try:
        res = RELAY.call(tool, args) if tool in BROWSER_TOOLS else SERVER_TOOLS[tool](args)
    except Exception as exc:  # report to the agent instead of failing the call
        return jsonify(_mcp_result(f"{tool} failed: {exc}", error=True))
    return jsonify(_mcp_result(res.get("text", ""), res.get("image"), bool(res.get("error"))))


@app.get("/api/agent/poll")
def api_agent_poll():
    """The page long-polls for tool calls to apply."""
    cmd = RELAY.poll(20.0, request.args.get("client") or None, request.args.get("active", "1") == "1")
    return jsonify(cmd) if cmd else ("", 204)


@app.post("/api/agent/result")
def api_agent_result():
    body = request.get_json(force=True)
    RELAY.resolve(body.get("id", ""), body.get("result") or {})
    return jsonify({"ok": True})


@app.get("/api/chat/status")
def api_chat_status():
    chat = _chat()
    return jsonify({"claude": find_claude(), "running": chat.running(), "busy": chat.busy})


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
        _chat().send(text, photos)
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"ok": True})


@app.post("/api/chat/stop")
def api_chat_stop():
    _chat().stop()
    return jsonify({"ok": True})


@app.post("/api/chat/reset")
def api_chat_reset():
    _chat().reset()
    return jsonify({"ok": True})


@app.get("/api/chat/events")
def api_chat_events():
    """Server-Sent Events: the chat (history first, then live)."""
    chat = _chat()
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
    app.run(host="127.0.0.1", port=args.port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
