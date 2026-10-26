"""Outline from a picture: detection, real-size model, cookie cutter / solid presets, 3D object booleans.

Run:  python -m unittest discover -s tests -v
"""
import base64
import math
import unittest
from pathlib import Path

import cv2
import numpy as np

from auto3d.outline import PRESETS, detect_outlines, outline_from_mask, outline_model, preset_objects, solve_outline
from auto3d.export import to_step, to_stl
from test_design_print import mesh_stats

ROOT = Path(__file__).resolve().parent.parent
PERNICEK = ROOT / "pernicek.png"


def data_url(img_rgb):
    ok, buf = cv2.imencode(".png", cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR))
    return "data:image/png;base64," + base64.b64encode(buf.tobytes()).decode()


def synthetic(frame=True, seed=3):
    """A brown star-ish blob with white 'icing' on a shaded green background, optionally framed in white."""
    rng = np.random.default_rng(seed)
    h, w = 300, 420
    yy, xx = np.mgrid[0:h, 0:w]
    img = np.zeros((h, w, 3), np.float32)
    shade = 0.75 + 0.5 * xx / w  # lighting gradient
    img[...] = np.array([110, 150, 95]) * shade[..., None]
    img += rng.normal(0, 6, img.shape)
    t = np.arctan2(yy - 150, xx - 210)
    r = np.hypot((yy - 150) / 0.8, xx - 210)
    shape = r < 110 + 18 * np.cos(5 * t)
    img[shape] = [120, 60, 40]
    icing = shape & (np.abs(np.sin(xx / 6)) > 0.93)
    img[icing] = [240, 238, 232]
    if frame:
        img[:5], img[-5:], img[:, :5], img[:, -5:] = 255, 255, 255, 255
    return np.clip(img, 0, 255).astype(np.uint8), shape


def iou_of(cand, gt):
    m = np.zeros(gt.shape, np.uint8)
    for poly in cand["polygons"]:
        cv2.fillPoly(m, [np.round(np.array(poly[0]) - 0.5).astype(np.int32)], 1)
        for hole in poly[1:]:
            cv2.fillPoly(m, [np.round(np.array(hole) - 0.5).astype(np.int32)], 0)
    m = m > 0
    return (m & gt).sum() / (m | gt).sum()


class TestDetection(unittest.TestCase):
    def test_object_on_shaded_background_with_frame(self):
        img, gt = synthetic()
        res = detect_outlines(data_url(img), {"count": 5})
        self.assertEqual((res["width"], res["height"]), (420, 300))
        self.assertGreaterEqual(len(res["candidates"]), 1)
        self.assertGreater(iou_of(res["candidates"][0], gt), 0.95)
        confs = [c["confidence"] for c in res["candidates"]]
        self.assertEqual(confs, sorted(confs, reverse=True))

    def test_count_limits_candidates(self):
        img, _ = synthetic(frame=False)
        for n in (3, 8):
            self.assertLessEqual(len(detect_outlines(data_url(img), {"count": n})["candidates"]), n)

    def test_user_colours(self):
        img, gt = synthetic()
        res = detect_outlines(data_url(img), {"count": 3, "object_colors": [[120, 60, 40], [240, 238, 232]],
                                              "background_colors": [[110, 150, 95], [150, 200, 130]]})
        self.assertGreater(max(iou_of(c, gt) for c in res["candidates"]), 0.95)

    def test_seed_keeps_only_regions_containing_it(self):
        img, _ = synthetic()
        res = detect_outlines(data_url(img), {"count": 10, "seeds": [[0.5, 0.5]]})
        self.assertTrue(res["candidates"])
        for c in res["candidates"]:
            inside = any(cv2.pointPolygonTest(np.array(p[0], np.float32), (210, 150), False) >= 0 for p in c["polygons"])
            self.assertTrue(inside)

    def test_not_this_point_and_box(self):
        img, gt = synthetic()
        url = data_url(img)
        # a 'not this' point on the object drops every candidate containing it
        res = detect_outlines(url, {"count": 10, "bg_seeds": [[0.5, 0.5]]})
        for c in res["candidates"]:
            self.assertFalse(any(cv2.pointPolygonTest(np.array(p[0], np.float32), (210, 150), False) >= 0
                                 for p in c["polygons"]))
        # a box around the object: candidates stay inside it (+ the 3 % search margin), and the object is found
        res = detect_outlines(url, {"count": 5, "rect": [60 / 420, 20 / 300, 360 / 420, 280 / 300]})
        self.assertGreater(iou_of(res["candidates"][0], gt), 0.95)
        for c in res["candidates"]:
            pts = np.array([p for poly in c["polygons"] for p in poly[0]])
            self.assertTrue((pts[:, 0] >= 60 - 14).all() and (pts[:, 0] <= 360 + 14).all())

    def test_mask_to_outline(self):
        mask = np.zeros((200, 300, 4), np.uint8)
        cv2.rectangle(mask, (50, 40), (249, 159), (255, 255, 255, 255), -1)
        cv2.circle(mask, (150, 100), 30, (0, 0, 0, 0), -1)   # a hole
        cv2.circle(mask, (10, 10), 1, (255, 255, 255, 255), -1)  # a brush speck: dropped
        ok, buf = cv2.imencode(".png", mask)
        url = "data:image/png;base64," + base64.b64encode(buf.tobytes()).decode()
        res = outline_from_mask(url, smoothing=0.5, holes=False)
        self.assertEqual((res["width"], res["height"]), (300, 200))
        self.assertEqual(len(res["polygons"]), 1)
        xs = [p[0] for p in res["polygons"][0][0]]
        self.assertAlmostEqual(min(xs), 50, delta=1)
        self.assertAlmostEqual(max(xs), 250, delta=1)
        res = outline_from_mask(url, smoothing=0.5, holes=True)
        self.assertEqual(len(res["polygons"][0]), 2)  # shell + hole

    def test_pernicek_whole_cookie_first(self):
        """The sample photo: the best candidate is the whole cookie (wheels, chimney, cabin)."""
        res = detect_outlines("data:image/png;base64," + base64.b64encode(PERNICEK.read_bytes()).decode(), {"count": 6})
        best = res["candidates"][0]
        pts = np.array([p for poly in best["polygons"] for p in poly[0]])
        x0, y0 = pts.min(0)
        x1, y1 = pts.max(0)
        # the cookie spans ~ x 12..392, y 18..245 of the 404 x 273 picture
        self.assertLess(x0, 20)
        self.assertGreater(x1, 385)
        self.assertLess(y0, 26)
        self.assertGreater(y1, 236)
        self.assertGreater(best["area"], 0.5)


def square_model(**kw):
    """A 100 x 50 px rectangle outline -> real size 100 x 50 mm (easy volumes)."""
    poly = [[[10, 10], [110, 10], [110, 60], [10, 60]]]
    return outline_model([poly], 200, 100, width=kw.pop("width", 100), **kw)


class TestOutlineModel(unittest.TestCase):
    def test_size_and_aspect(self):
        m = square_model(width=40)
        self.assertAlmostEqual(m["params"][1]["value"], 20)
        sol, solid = solve_outline({**m, "preset": "solid", "preset_opts": {"thickness": 3, "offset": 0}})
        self.assertTrue(sol["ok"])
        self.assertEqual([round(v, 6) for v in sol["bbox"]], [0, 0, 40, 20])
        self.assertAlmostEqual(solid.volume(), 40 * 20 * 3, places=4)

    def test_solid_preset_watertight_and_offset(self):
        m = {**square_model(), "preset": "solid", "preset_opts": {"thickness": 5, "offset": 2}}
        sol, solid = solve_outline(m)
        vol, bad = mesh_stats(solid)
        self.assertEqual(bad, 0)
        grown = 104 * 54 - (4 - math.pi) * 4  # rounded corners of the 2 mm offset
        self.assertAlmostEqual(vol, grown * 5, delta=grown * 5 * 0.002)

    def test_cookie_cutter(self):
        o = dict(PRESETS["cutter"])
        sol, solid = solve_outline({**square_model(), "preset": "cutter", "preset_opts": o})
        self.assertTrue(sol["ok"], sol["issues"])
        self.assertEqual(sol["z_range"], [0.0, o["height"]])
        vol, bad = mesh_stats(solid)
        self.assertEqual(bad, 0)
        # inner wall face is exactly on the outline: the cookie is 100 x 50 mm
        top = solid.slabs[-1][2]
        self.assertAlmostEqual(top.geoms[0].interiors[0].bounds[2] - top.geoms[0].interiors[0].bounds[0], 100, places=4)
        band = lambda r0, r1: (100 + 2 * r1) * (50 + 2 * r1) - (4 - math.pi) * r1 ** 2 - 100 * 50
        expect = (band(0, o["wall"] + o["flange_w"]) * o["flange_t"]
                  + band(0, o["wall"]) * (o["height"] - o["flange_t"] - o["tip_h"]) + band(0, o["tip"]) * o["tip_h"])
        self.assertAlmostEqual(vol, expect, delta=expect * 0.003)
        self.assertGreater(len(to_stl(solid, "mm")), 84)
        self.assertIn(b"MANIFOLD_SOLID_BREP", to_step(solid, "mm"))

    def test_layer_faces_and_levels(self):
        """Design layers go on the first object (the cutter's flange); all face heights are listed for picking."""
        o = dict(PRESETS["cutter"])
        sol, solid = solve_outline({**square_model(), "preset": "cutter", "preset_opts": o})
        self.assertEqual(sol["layer_faces"], {"top": o["flange_t"], "bottom": 0.0, "object": "Flange"})
        self.assertEqual(sol["z_levels"], [0.0, o["flange_t"], o["height"] - o["tip_h"], o["height"]])
        # an engraved layer lands in the flange top, not at the top of the cutting edge
        layer = {"id": "L", "op": "engrave", "depth": 0.5, "face": "top",
                 "mask": {"kind": "rect", "x": -3, "y": 25, "w": 2, "h": 10}}
        sol2, solid2 = solve_outline({**square_model(), "preset": "cutter", "preset_opts": o}, layers=[layer])
        self.assertAlmostEqual(solid.volume() - solid2.volume(), 2 * 10 * 0.5, places=4)
        self.assertEqual(mesh_stats(solid2)[1], 0)

    def test_cutter_without_thinner_edge(self):
        objs = preset_objects("cutter", {**PRESETS["cutter"], "tip": 1.0})
        self.assertEqual([o["name"] for o in objs], ["Flange", "Wall"])
        self.assertEqual(objs[1]["z1"], PRESETS["cutter"]["height"])

    def test_boolean_objects(self):
        base = {"source": "outline", "mode": "fill", "offset": 0, "z0": 0, "z1": 10, "op": "union", "name": "Base"}
        hole = {"source": "circle", "x": 50, "y": 25, "w": 20, "h": 20, "z0": 0, "z1": 10, "op": "subtract", "name": "Hole"}
        post = {"source": "rect", "x": 50, "y": 25, "w": 10, "h": 10, "z0": 0, "z1": 20, "op": "union", "name": "Post"}
        clip = {"source": "rect", "x": 25, "y": 25, "w": 50, "h": 50, "z0": 0, "z1": 30, "op": "intersect", "name": "Clip"}
        m = {**square_model(), "preset": "custom"}
        circle = math.pi * 100 * (1 - 0.0016)  # 32-segment approximation

        m["objects"] = [base, hole]
        _, s = solve_outline(m)
        self.assertAlmostEqual(s.volume(), (5000 - circle) * 10, delta=5)
        self.assertEqual(mesh_stats(s)[1], 0)

        m["objects"] = [base, hole, post]
        _, s = solve_outline(m)
        self.assertAlmostEqual(s.volume(), (5000 - circle) * 10 + 100 * 20, delta=5)

        m["objects"] = [base, hole, post, clip]  # keep only the left half
        _, s = solve_outline(m)
        self.assertAlmostEqual(s.volume(), (2500 - circle / 2) * 10 + 50 * 20, delta=5)
        self.assertEqual(mesh_stats(s)[1], 0)

    def test_2d_shapes_change_the_outline(self):
        m = {**square_model(), "preset": "solid", "preset_opts": {"thickness": 1, "offset": 0}}
        m["shapes"] = [{"kind": "rect", "x": 100, "y": 25, "w": 20, "h": 10, "op": "add"},
                       {"kind": "circle", "x": 20, "y": 25, "w": 10, "h": 10, "op": "subtract"},
                       {"kind": "line", "x": 40, "y": 0, "x2": 40, "y2": 50, "width": 2, "op": "subtract"}]
        sol, s = solve_outline(m)
        self.assertTrue(sol["ok"])
        self.assertAlmostEqual(sol["bbox"][2], 110)  # the rectangle sticks out 10 mm
        expect = 5000 + 100 - math.pi * 25 * 0.9936 - 2 * 50
        self.assertAlmostEqual(s.volume(), expect, delta=1)
        self.assertEqual(len(sol["outline_2d"]), 2)  # the line cuts the outline in two pieces

    def test_mirror(self):
        # picture (y down): the only vertex on the bottom edge is the bottom-left one
        poly = [[[0, 0], [100, 0], [0, 50]]]
        m = {**outline_model([poly], 100, 50, width=100), "preset": "solid", "preset_opts": {"thickness": 1}}
        sol, _ = solve_outline(m)
        corner = lambda sol: min(sol["loops"][0]["points"], key=lambda p: p[1])[0]  # x of the bottom vertex
        self.assertAlmostEqual(corner(sol), 0)
        m["outline"]["mirror"] = True
        sol, _ = solve_outline(m)
        self.assertAlmostEqual(corner(sol), 100)

    def test_cleanup(self):
        # a 100 x 50 rectangle with a 2 mm slot, a 20 x 20 hole and a separate 5 x 5 island
        shell = [[0, 0], [48, 0], [48, 30], [50, 30], [50, 0], [100, 0], [100, 50], [0, 50]]
        hole = [[70, 15], [90, 15], [90, 35], [70, 35]]
        island = [[110, 0], [115, 0], [115, 5], [110, 5]]
        m = {**outline_model([[shell[::-1], hole], [island]], 200, 100, width=115), "preset": "solid",
             "preset_opts": {"thickness": 1, "offset": 0}}

        def area(**cleanup):
            m["outline"]["cleanup"] = cleanup
            sol, s = solve_outline(m)
            self.assertTrue(sol["ok"], sol["issues"])
            self.assertEqual(mesh_stats(s)[1], 0)
            return s.volume(), sol

        plain = 5000 - 60 - 400 + 25
        self.assertAlmostEqual(area()[0], plain, delta=0.1)
        self.assertAlmostEqual(area(fill_holes=True)[0], plain + 400, delta=0.1)
        # the 2 mm slot is bridged; closing also rounds the 4 inner corners of the hole: (1 - pi/4) r^2 each
        self.assertAlmostEqual(area(close=1.5)[0], plain + 60 + 4 * (1 - math.pi / 4) * 1.5 ** 2, delta=0.6)
        self.assertAlmostEqual(area(keep="largest")[0], plain - 25, delta=0.1)
        v, sol = area(hull=True)
        self.assertGreater(v, 5000 + 25)                                          # hull spans the island too
        # rounding with r = 3 also bridges the 2 mm slot (+60) and drops the 5 mm island (-25);
        # the outer corners lose (1 - pi/4) r^2 each, the hole corners gain the same
        v, sol = area(smooth=3)
        self.assertEqual(len(sol["outline_2d"]), 1)
        self.assertAlmostEqual(v, plain + 60 - 25, delta=2)

    def test_text_shape(self):
        # 'poly' primitives: traced polygons in a unit box, placed by centre / size / rotation
        unit_square = [[[-0.5, -0.5], [0.5, -0.5], [0.5, 0.5], [-0.5, 0.5]]]
        m = {**square_model(), "preset": "solid", "preset_opts": {"thickness": 2, "offset": 0}}
        m["shapes"] = [{"kind": "poly", "polygons": [unit_square], "x": 50, "y": 25, "w": 20, "h": 10, "op": "subtract"}]
        _, s = solve_outline(m)
        self.assertAlmostEqual(s.volume(), (5000 - 200) * 2, places=3)
        m = {**square_model(), "preset": "custom", "objects": [
            {"source": "outline", "mode": "fill", "z0": 0, "z1": 2, "name": "Base"},
            {"source": "poly", "polygons": [unit_square], "x": 50, "y": 25, "w": 20, "h": 10, "rot": 90, "z0": 2, "z1": 3,
             "name": "Raised text"}]}
        sol, s = solve_outline(m)
        self.assertAlmostEqual(s.volume(), 5000 * 2 + 200, places=3)
        self.assertEqual(sol["z_range"], [0.0, 3.0])

    def test_custom_start_has_the_outline(self):
        m = square_model(preset="custom")
        sol, s = solve_outline(m)
        self.assertTrue(sol["ok"])
        self.assertAlmostEqual(s.volume(), 5000 * PRESETS["solid"]["thickness"], places=3)

    def test_invalid_input_is_reported(self):
        m = {**square_model(), "preset": "custom"}
        m["objects"] = [{"source": "outline", "mode": "band", "inner": 2, "outer": 1, "z0": 0, "z1": 5, "name": "Bad band"},
                        {"source": "outline", "mode": "fill", "z0": 5, "z1": 5, "name": "Flat"}]
        sol, s = solve_outline(m)
        self.assertIsNone(s)
        msgs = " ".join(i["message"] for i in sol["issues"])
        self.assertIn("outer offset", msgs)
        self.assertIn("must be above", msgs)
        sol, s = solve_outline(square_model(), {"width": 0})
        self.assertFalse(sol["ok"])
        self.assertIsNone(s)

    def test_thin_wall_warning(self):
        sol, _ = solve_outline({**square_model(), "preset": "cutter", "preset_opts": {**PRESETS["cutter"], "tip": 0.3}})
        self.assertTrue(any("thinner than 0.4" in i["message"] for i in sol["issues"]))


class TestServer(unittest.TestCase):
    def test_detect_model_solve_export(self):
        from server import app
        c = app.test_client()
        img, _ = synthetic()
        res = c.post("/api/outline/detect", json={"image": data_url(img), "hints": {"count": 3}}).get_json()
        cand = res["candidates"][0]
        made = c.post("/api/outline/model", json={"polygons": cand["polygons"], "img_w": 420, "img_h": 300,
                                                  "width": 80, "preset": "cutter", "source": "star.png"}).get_json()
        model = made["model"]
        self.assertEqual(model["kind"], "outline")
        sol = c.post("/api/solve", json={"model": model, "values": {}}).get_json()
        self.assertTrue(sol["ok"])
        self.assertGreater(sol["mesh"]["count"], 100)
        stl = c.post("/api/export/stl", json={"model": model, "values": {}})
        self.assertEqual(stl.status_code, 200)
        step = c.post("/api/export/step", json={"model": model, "values": {}})
        self.assertEqual(step.status_code, 200)
        plan = c.post("/api/print/plan", json={"model": model, "values": {}, "printer": "creality-ender3-pro", "margin": 5})
        self.assertEqual(plan.status_code, 200, plan.get_json())


if __name__ == "__main__":
    unittest.main()
