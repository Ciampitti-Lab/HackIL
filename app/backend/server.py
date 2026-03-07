import csv
import json
import random
from pathlib import Path

from flask import Flask, Response, abort, jsonify, send_from_directory

_HERE = Path(__file__).parent

# In Docker: server.py is at /app/server.py, data and models live at /app/
# Locally:   server.py is at app/backend/server.py, so project root is 2 up
_docker_root = _HERE
_local_root  = _HERE.parent.parent
_ROOT = _docker_root if (_docker_root / "models").exists() else _local_root

PREDICTIONS_DIR = _ROOT / "data/processed/predictions"
STATIC = _HERE / "static"

# Load precomputed proximal sensing predictions from the CSV at startup.
# Schema: image_path, true_class, predicted_class, confidence, correct, dataset
_PROXIMAL_CSV = PREDICTIONS_DIR / "proximal_sensing.csv"
_PROXIMAL_ROWS: list[dict] = []
_PROXIMAL_CLASSES = ["ALL Present", "ALLAB", "KAB", "NAB", "PAB", "ZNAB"]
if _PROXIMAL_CSV.exists():
    with open(_PROXIMAL_CSV, newline="") as _f:
        _PROXIMAL_ROWS = list(csv.DictReader(_f))
    print(f"[proximal] loaded {len(_PROXIMAL_ROWS)} precomputed predictions")
else:
    print(f"[proximal] CSV not found at {_PROXIMAL_CSV}")

# Pre-load all trial GeoJSONs into memory at startup so every request is a
# simple dict lookup with no disk I/O. Simplified workflow for this demo app
_TRIALS: dict[int, dict] = {}
for _p in sorted(PREDICTIONS_DIR.glob("trial_*.geojson")):
    _trial_id = int(_p.stem.split("_")[1])
    with open(_p) as _f:
        _TRIALS[_trial_id] = json.load(_f)

# Site index: {trial_id: {trial, site, state}}; used by the site-list endpoint
SITES = [
    {"trial": tid, "site": d["site"], "state": d["state"]}
    for tid, d in sorted(_TRIALS.items())
]

app = Flask(__name__, static_folder=str(STATIC))


# ── API routes
@app.route("/api/ping")
def ping():
    return jsonify({"status": "ok", "message": "Flask backend is alive"})


@app.route("/api/sites")
def sites():
    """List of available trial sites for the site selector dropdown."""
    return jsonify(SITES)


@app.route("/api/predictions/<int:trial_id>")
def predictions(trial_id: int):
    """
    Return the precomputed GeoJSON for a trial site.

    Each feature's properties contain all 20 prediction fields:
      remote_{1-5}_prob / remote_{1-5}_pred
      fusion_{1-5}_prob  / fusion_{1-5}_pred
    plus ground-truth fields (nni, is_deficient, n_trt, plant_n_kgha, side_n_kgha).

    The frontend filters by (n_stages, model_type) client-side — no further
    API calls are needed when the user changes stage or model type.
    """
    if trial_id not in _TRIALS:
        abort(404, description=f"Trial {trial_id} not found")
    # Return raw JSON string; avoids re-serialising the pre-loaded dict.
    payload = json.dumps(_TRIALS[trial_id], separators=(",", ":"))
    return Response(payload, mimetype="application/json")


@app.route("/api/proximal/stats")
def proximal_stats():
    """Per-class accuracy on the test split from precomputed predictions."""
    test_rows = [r for r in _PROXIMAL_ROWS if r["dataset"] == "test"]
    stats = {}
    for cls in _PROXIMAL_CLASSES:
        cls_rows = [r for r in test_rows if r["true_class"] == cls]
        if cls_rows:
            accuracy = sum(1 for r in cls_rows if r["correct"] == "True") / len(cls_rows)
            stats[cls] = {"accuracy": round(accuracy, 4), "n": len(cls_rows)}
    overall = sum(1 for r in test_rows if r["correct"] == "True") / len(test_rows) if test_rows else 0
    return jsonify({"overall_accuracy": round(overall, 4), "per_class": stats, "n_test": len(test_rows)})


@app.route("/api/proximal/samples")
def proximal_samples():
    """Return a random sample of precomputed predictions for each class.

    Query param: n (default 3) — number of samples per class.
    Query param: dataset (default 'test') — split to sample from.
    """
    from flask import request as req
    n = int(req.args.get("n", 3))
    dataset = req.args.get("dataset", "test")
    result = {}
    for cls in _PROXIMAL_CLASSES:
        pool = [r for r in _PROXIMAL_ROWS if r["true_class"] == cls and r["dataset"] == dataset]
        result[cls] = random.sample(pool, min(n, len(pool)))
    return jsonify(result)


# Next.js static export
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_frontend(path: str):
    # Serve the requested file if it exists (JS, CSS, images, etc.)
    target = STATIC / path
    if path and target.exists():
        return send_from_directory(STATIC, path)
    # Fall back to index.html for SPA-style client-side routing
    return send_from_directory(STATIC, "index.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
