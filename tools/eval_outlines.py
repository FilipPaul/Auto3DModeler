"""Benchmark outline detection on a dataset with ground-truth masks (ECSSD layout).

Measures top-1 and best-of-N IoU of auto3d.outline.detect_outlines against the hole-filled
ground truth: best-of-N is what matters in the app (the user picks one of N candidates).

Dataset (not in the repo): ECSSD, 1000 photos + masks —
  https://www.cse.cuhk.edu.hk/leojia/projects/hsaliency/data/ECSSD/images.zip
  https://www.cse.cuhk.edu.hk/leojia/projects/hsaliency/data/ECSSD/ground_truth_mask.zip
unzipped into <dir>/images/*.jpg and <dir>/ground_truth_mask/*.png.

usage: py -I tools/eval_outlines.py <dataset dir> <n images> <out.json> [step]
  e.g. 150 images, every 6th:  py -I tools/eval_outlines.py data/ecssd 150 data/eval.json 6
Baseline (2026-10-25, 150 imgs, step 6): top-1 mean IoU 0.53, best-of-10 0.71 (44 % > 0.8).
"""
import base64
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

data, n, out = Path(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
step = int(sys.argv[4]) if len(sys.argv) > 4 else 1
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from auto3d.outline import detect_outlines  # noqa: E402


def fill(m):
    cnts, _ = cv2.findContours(m.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    o = np.zeros(m.shape, np.uint8)
    cv2.drawContours(o, cnts, -1, 1, -1)
    return o > 0


def raster(polys, shape):
    m = np.zeros(shape, np.uint8)
    for poly in polys:
        cv2.fillPoly(m, [np.round(np.array(poly[0]) - 0.5).astype(np.int32)], 1)
        for hole in poly[1:]:
            cv2.fillPoly(m, [np.round(np.array(hole) - 0.5).astype(np.int32)], 0)
    return m > 0


imgs = sorted((data / "images").glob("*.jpg"))[::step][:n]
rows = []
t0 = time.time()
for p in imgs:
    gt = fill(cv2.imread(str(data / "ground_truth_mask" / (p.stem + ".png")), 0) > 128)
    url = "data:image/jpeg;base64," + base64.b64encode(p.read_bytes()).decode()
    t = time.time()
    res = detect_outlines(url, {"count": 10})
    dt = time.time() - t
    ious = []
    for c in res["candidates"]:
        m = raster(c["polygons"], gt.shape)
        ious.append(float((m & gt).sum() / max(1, (m | gt).sum())))
    rows.append({"img": p.name, "ious": ious, "t": dt, "conf": [c["confidence"] for c in res["candidates"]]})
    print(p.name, f"{dt:.2f}s", " ".join(f"{v:.2f}" for v in ious[:5]), flush=True)


def best(k):
    return [max(r["ious"][:k], default=0) for r in rows]


summary = {"n": len(rows), "secs": round(time.time() - t0, 1)}
for k in (1, 3, 5, 10):
    b = np.array(best(k))
    summary[f"best{k}"] = {"mean_iou": round(float(b.mean()), 3), "iou>0.8": round(float((b > 0.8).mean()), 3),
                           "iou>0.9": round(float((b > 0.9).mean()), 3)}
print(json.dumps(summary, indent=1))
json.dump({"summary": summary, "rows": rows}, open(out, "w"), indent=0)
