from flask import Flask, render_template, request, jsonify
from datetime import datetime
import os

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24))
from flask import send_from_directory
import os

@app.route('/manifest.json')
def manifest():
    return send_from_directory(
        os.path.join(app.root_path, 'static'),
        'manifest.json',
        mimetype='application/manifest+json'
    )

@app.route('/sw.js')
def service_worker():
    return send_from_directory(
        os.path.join(app.root_path, 'static'),
        'sw.js',
        mimetype='application/javascript'
    )

# ── NOTE ────────────────────────────────────────────────────────────────────
# Auth, contacts, and messages are now fully handled by Firebase on the
# frontend. Flask only serves the HTML page and provides one lightweight
# helper route (/api/send) used to update the contact preview timestamp.
# All hardcoded USERS, CONTACTS, MESSAGES, STATUS data has been removed.
# ────────────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Serve the main app page."""
    return render_template("index.html")

@app.route("/api/send", methods=["POST"])
def send_message():
    """
    Lightweight helper — called by the frontend after a Firestore write
    just to acknowledge the send. Message data lives in Firestore,
    not here. Returns a timestamped ack so the contact list preview updates.
    """
    data = request.get_json(silent=True) or {}
    text = data.get("text", "").strip()

    if not text:
        return jsonify({"ok": False, "error": "Empty message"}), 400

    return jsonify({
        "ok":  True,
        "message": {
            "id":     f"msg_{datetime.now().timestamp()}",
            "text":   text,
            "sender": "me",
            "time":   datetime.now().strftime("%I:%M %p"),
        }
    })

@app.route("/health")
def health():
    """Render health-check endpoint."""
    return jsonify({"status": "ok", "app": "Nexo"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("\n╔══════════════════════════════════════╗")
    print("║  Nexo — Firebase Edition             ║")
    print(f"║  Running on http://0.0.0.0:{port}      ║")
    print("║  Auth & data handled by Firebase     ║")
    print("╚══════════════════════════════════════╝\n")
    app.run(host="0.0.0.0", port=port, debug=False)
