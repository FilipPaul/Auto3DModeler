"""Auto3DModeler local web app.

Run:  python server.py   (then open http://127.0.0.1:5173)
"""
from __future__ import annotations

import argparse
import base64
import io
import re
import threading
import webbrowser
import zipfile
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_from_directory

from auto3d.bend import bend_info, bend_solid
from auto3d.design import trace_image
from auto3d.export import build_solid, mesh_payload, to_step, to_stl
from auto3d.extract import render_page_png
from auto3d.joints import joint_catalog
from auto3d.printing import PrinterStore, assembly_text, bend_pieces, plan
from auto3d.sketch import build_model
from auto3d.solver import solve

ROOT = Path(__file__).parent
WEB = ROOT / "web"
SAMPLE = ROOT / "initial draft.pdf"
printers = PrinterStore(ROOT / "data" / "printers.json")

app = Flask(__name__, static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024


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
    solution = solve(model, body.get("values"))
    solid = final = bender = None
    if solution["ok"]:
        solid = build_solid(solution, model["unit"], body.get("layers"))
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


def _parse(pdf: bytes, page: int, filename: str):
    try:
        model, pg, _doc = build_model(pdf, page)
    except Exception as exc:  # corrupt / encrypted / not a PDF
        return jsonify({"error": f"Could not read the PDF: {exc}"}), 400
    model["source"] = filename
    preview = {"png": base64.b64encode(render_page_png(pg)).decode(), "width": pg.rect.width,
               "height": pg.rect.height}
    return jsonify({"model": model, "preview": preview})


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


@app.post("/api/solve")
def api_solve():
    body = request.get_json(force=True)
    _model, solution, final, _flat, _bender = _solve_full(body)
    if final is not None and body.get("mesh", True):
        solution["mesh"] = mesh_payload(final)
    return jsonify(solution)


@app.post("/api/trace")
def api_trace():
    body = request.get_json(force=True)
    try:
        return jsonify(trace_image(body["image"], int(body.get("threshold", 128)), bool(body.get("invert"))))
    except Exception as exc:
        return jsonify({"error": f"Could not trace the image: {exc}"}), 400


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


def _plan(body, solid, model, bender=None):
    printer = printers.get(body.get("printer"))
    if printer is None:
        raise ValueError("Unknown printer.")
    avoid = [(bender.axis, op["s"], op["e"]) for op in bender.ops] if bender else []
    result = plan(solid, model["unit"], printer, float(body.get("margin", 5)), bool(body.get("split")),
                  body.get("joint"), avoid=avoid)
    if bender is not None:
        bend_pieces(result, bender, model["unit"], float(body.get("margin", 5)))
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
        result = _plan(body, solid, model, bender)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    for p in result["pieces"]:
        p["mesh"] = mesh_payload(p.pop("solid"))
    for g in result.get("connectors", []):
        for inst in g["instances"]:
            inst["mesh"] = mesh_payload(inst.pop("solid"))
    return jsonify(result)


@app.get("/api/joints")
def api_joints():
    return jsonify(joint_catalog())


# --------------------------------------------------------------------------- export
@app.post("/api/export/<fmt>")
def api_export(fmt):
    body = request.get_json(force=True)
    model, solution, final, solid, bender = _solve_full(body)
    if solid is None:
        return jsonify({"error": "The model is invalid and cannot be exported.", "issues": solution["issues"]}), 400
    if not solution.get("design_ok", True):
        msgs = " ".join(i["message"] for i in solution["design_issues"] if i["severity"] == "error")
        return jsonify({"error": f"Fix the design layers first: {msgs}"}), 400
    if fmt not in ("stl", "step"):
        return jsonify({"error": f"Unknown format {fmt}"}), 404
    name = re.sub(r"[^A-Za-z0-9_-]+", "_", Path(model.get("source", "part")).stem).strip("_") or "part"
    writer = to_stl if fmt == "stl" else to_step
    mime = "model/stl" if fmt == "stl" else "model/step"

    if body.get("split") and body.get("printer"):
        try:
            result = _plan(body, solid, model, bender)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        if not result["pieces"]:
            return jsonify({"error": " ".join(i["message"] for i in result["issues"]) or "Nothing to export."}), 400
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
        return Response(buf.getvalue(), mimetype="application/zip",
                        headers={"Content-Disposition": f'attachment; filename="{name}_{fmt}_pieces.zip"'})

    return Response(writer(final, model["unit"], name), mimetype=mime,
                    headers={"Content-Disposition": f'attachment; filename="{name}.{fmt}"'})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=5173)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()
    url = f"http://127.0.0.1:{args.port}"
    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    print(f"Auto3DModeler running at {url}")
    app.run(host="127.0.0.1", port=args.port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
