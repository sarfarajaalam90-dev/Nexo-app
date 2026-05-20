from flask import Flask, render_template, request, jsonify, send_from_directory
from datetime import datetime
from pywebpush import webpush, WebPushException
import os, json

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24))

# ── VAPID config — set these as environment variables on Render ──────────────
# In Render dashboard → Environment → Add:
#   VAPID_PRIVATE_KEY = qgIPEeJdGTTevefFs1NRIJ1aZZplgsMRnDwBZz1pOSc
#   VAPID_PUBLIC_KEY  = BIayh8Hp_-6TosLl50O5xGmK1F7mP6RAmdul3m22nEwCWd3tL5Rm1BRWp_Oq-fzafRIvo2gr-lFokY2TFuQjWlw
#   VAPID_CLAIMS_EMAIL = sarfarajaalam90@gmail.com
VAPID_PRIVATE_KEY   = os.environ.get("VAPID_PRIVATE_KEY",   "qgIPEeJdGTTevefFs1NRIJ1aZZplgsMRnDwBZz1pOSc")
VAPID_PUBLIC_KEY    = os.environ.get("VAPID_PUBLIC_KEY",    "BIayh8Hp_-6TosLl50O5xGmK1F7mP6RAmdul3m22nEwCWd3tL5Rm1BRWp_Oq-fzafRIvo2gr-lFokY2TFuQjWlw")
VAPID_CLAIMS_EMAIL  = os.environ.get("VAPID_CLAIMS_EMAIL",  "sarfarajaalam90@gmail.com")

# ── In-memory subscription store (keyed by uid) ──────────────────────────────
# For production, replace this with a Firestore collection read/write.
# Structure: { uid: { subscription_json } }
_subscriptions: dict = {}

# ── NOTE ────────────────────────────────────────────────────────────────────
# Auth, contacts, and messages are fully handled by Firebase on the frontend.
# Flask serves the HTML page and handles push notification delivery.
# ────────────────────────────────────────────────────────────────────────────

@app.route('/manifest.json')
def manifest():
    return send_from_directory(
        os.path.join(app.root_path, 'static'),
        'manifest.json',
        mimetype='application/manifest+json'
    )

@app.route('/sw.js')
def service_worker():
    response = send_from_directory(
        os.path.join(app.root_path, 'static'),
        'sw.js',
        mimetype='application/javascript'
    )
    # Required: SW must not be cached aggressively
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['Service-Worker-Allowed'] = '/'
    return response

@app.route("/")
def index():
    """Serve the main app page."""
    return render_template("index.html")

# ── Save push subscription from browser ─────────────────────────────────────
@app.route("/api/push/subscribe", methods=["POST"])
def push_subscribe():
    """
    Called by the frontend after pushManager.subscribe().
    Saves the subscription so we can send pushes to this user later.
    Expects JSON body: { uid, subscription: { endpoint, keys: { p256dh, auth } } }
    """
    body = request.get_json(silent=True) or {}
    uid  = body.get("uid")
    sub  = body.get("subscription")

    if not uid or not sub:
        return jsonify({"ok": False, "error": "Missing uid or subscription"}), 400

    _subscriptions[uid] = sub
    print(f"[Push] Subscription saved for uid={uid}")
    return jsonify({"ok": True})

# ── Send a push notification to a specific user ──────────────────────────────
@app.route("/api/push/send", methods=["POST"])
def push_send():
    """
    Called by the frontend (sender side) after a Firestore message write.
    Sends a Web Push notification to the recipient.
    Expects JSON body: { recipientUid, title, body, type ('message'|'call'), callId? }
    """
    body         = request.get_json(silent=True) or {}
    recipient_uid = body.get("recipientUid")
    title        = body.get("title", "Secret")
    msg_body     = body.get("body",  "New message")
    notif_type   = body.get("type",  "message")   # 'message' | 'call'
    call_id      = body.get("callId", "")

    if not recipient_uid:
        return jsonify({"ok": False, "error": "Missing recipientUid"}), 400

    sub = _subscriptions.get(recipient_uid)
    if not sub:
        return jsonify({"ok": False, "error": "No subscription found for this user"}), 404

    payload = json.dumps({
        "title"  : title,
        "body"   : msg_body,
        "type"   : notif_type,
        "callId" : call_id,
        "icon"   : "/static/icon-192.png",
        "badge"  : "/static/icon-192.png",
        "tag"    : "secret-call" if notif_type == "call" else "secret-msg",
    })

    try:
        webpush(
            subscription_info    = sub,
            data                 = payload,
            vapid_private_key    = VAPID_PRIVATE_KEY,
            vapid_claims         = {"sub": f"mailto:{VAPID_CLAIMS_EMAIL}"}
        )
        print(f"[Push] Sent to uid={recipient_uid} type={notif_type}")
        return jsonify({"ok": True})

    except WebPushException as ex:
        print(f"[Push] WebPushException for uid={recipient_uid}: {ex}")
        # 410 Gone = subscription expired, remove it
        if ex.response and ex.response.status_code == 410:
            _subscriptions.pop(recipient_uid, None)
            return jsonify({"ok": False, "error": "Subscription expired, removed"}), 410
        return jsonify({"ok": False, "error": str(ex)}), 500

# ── Lightweight send ack (unchanged) ────────────────────────────────────────
@app.route("/api/send", methods=["POST"])
def send_message():
    data = request.get_json(silent=True) or {}
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"ok": False, "error": "Empty message"}), 400
    return jsonify({
        "ok": True,
        "message": {
            "id":     f"msg_{datetime.now().timestamp()}",
            "text":   text,
            "sender": "me",
            "time":   datetime.now().strftime("%I:%M %p"),
        }
    })

@app.route("/health")
def health():
    return jsonify({"status": "ok", "app": "Nexo"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("\n╔══════════════════════════════════════╗")
    print("║  Nexo — Firebase Edition             ║")
    print(f"║  Running on http://0.0.0.0:{port}      ║")
    print("║  Push notifications: ENABLED         ║")
    print("╚══════════════════════════════════════╝\n")
    app.run(host="0.0.0.0", port=port, debug=False)
