import json
from pathlib import Path

from flask import Flask, Response, abort, jsonify, send_from_directory

_HERE = Path(__file__).parent

# In Docker: server.py is at /app/server.py, data lives at /app/data/
# Locally:   server.py is at app/backend/server.py, data lives at data/ (3 up)
_docker_data = _HERE / "data/processed/predictions"
_local_data  = _HERE.parent.parent.parent / "data/processed/predictions"
PREDICTIONS_DIR = _docker_data if _docker_data.exists() else _local_data

STATIC = _HERE / "static"

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
