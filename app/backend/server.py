from pathlib import Path
from flask import Flask, jsonify, send_from_directory

STATIC = Path(__file__).parent / "static"

app = Flask(__name__, static_folder=str(STATIC))


# ── API routes ────────────────────────────────────────────────────────────────

@app.route("/api/ping")
def ping():
    return jsonify({"status": "ok", "message": "Flask backend is alive"})


# ── Serve Next.js static export ───────────────────────────────────────────────

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
