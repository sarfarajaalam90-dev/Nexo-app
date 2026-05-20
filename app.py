from flask import Flask, render_template, request, jsonify, send_from_directory
from datetime import datetime
from pywebpush import webpush, WebPushException
import os, json

# ── Firebase Admin ────────────────────────────────────────────────────────────
import firebase_admin
from firebase_admin import credentials, firestore as fb_firestore

_fb_initialized = False
_fs_client = None

def _init_firebase():
    global _fb_initialized, _fs_client
    if _fb_initialized:
        return
    try:
        sa_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
        if sa_json:
            cred = credentials.Certificate(json.loads(sa_json))
        else:
            key_path = os.path.join(os.path.dirname(__file__),
                                    "nexo-app-b9ec4-firebase-adminsdk-fbsvc-4f17bf7bb7.json")
            cred = credentials.Certificate(key_path)
        firebase_admin.initialize_app(cred)
        _fs_client = fb_firestore.client()
        _fb_initialized = True
        print("[Firebase] Admin SDK initialised ✅")
    except Exception as e:
        print(f"[Firebase] ❌ Init failed: {e}")

_init_firebase()

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24))

# ── VAPID config ──────────────────────────────────────────────────────────────
VAPID_PRIVATE_KEY  = os.environ.get("VAPID_PRIVATE_KEY",  "qgIPEeJdGTTevefFs1NRIJ1aZZplgsMRnDwBZz1pOSc")
VAPID_PUBLIC_KEY   = os.environ.get("VAPID_PUBLIC_KEY",   "BIayh8Hp_-6TosLl50O5xGmK1F7mP6RAmdul3m22nEwCWd3tL5Rm1BRWp_Oq-fzafRIvo2gr-lFokY2TFuQjWlw")
VAPID_CLAIMS_EMAIL = os.environ.get("VAPID_CLAIMS_EMAIL", "sarfarajaalam90@gmail.com")

# ── In-memory cache ───────────────────────────────────────────────────────────
_sub_cache: dict = {}


def _get_subscription(uid: str):
    """Cache first, then Firestore fallback."""
    if uid in _sub_cache:
        return _sub_cache[uid]
    if _fs_client:
        try:
            doc = _fs_client.collection("pushSubscriptions").document(uid).get()
            if doc.exists:
                sub = doc.to_dict().get("subscription")
                if sub:
                    _sub_cache[uid] = sub
                    return sub
        except Exception as e:
            print(f"[Firebase] Firestore read failed for uid={uid}: {e}")
    return None


@app.route('/manifest.json')
def manifest():
    return send_from_directory(
        os.path.join(app.root_path, 'static'),
        'manifest.json', mimetype='application/manifest+json')

@app.route('/sw.js')
def service_worker():
    resp = send_from_directory(
        os.path.join(app.root_path, 'static'),
        'sw.js', mimetype='application/javascript')
    resp.headers['Cache-Control'] = 'no-cache'
    resp.headers['Service-Worker-Allowed'] = '/'
    return resp

@app.route("/")
def index():
    return render_template("index.html")

# ── Save subscription ─────────────────────────────────────────────────────────
@app.route("/api/push/subscribe", methods=["POST"])
def push_subscribe():
    body = request.get_json(silent=True) or {}
    uid  = body.get("uid")
    sub  = body.get("subscription")
    if not uid or not sub:
        return jsonify({"ok": False, "error": "Missing uid or subscription"}), 400

    # 1. Cache in memory
    _sub_cache[uid] = sub

    # 2. Persist to Firestore so it survives restarts
    if _fs_client:
        try:
            _fs_client.collection("pushSubscriptions").document(uid).set({
                "subscription": sub,
                "updatedAt": fb_firestore.SERVER_TIMESTAMP
            })
            print(f"[Push] ✅ Subscription saved to Firestore for uid={uid}")
        except Exception as e:
            print(f"[Push] ⚠️ Firestore save failed for uid={uid}: {e}")
    else:
        print(f"[Push] ⚠️ Firebase not ready — subscription only cached for uid={uid}")

    return jsonify({"ok": True})

# ── Send push notification ────────────────────────────────────────────────────
@app.route("/api/push/send", methods=["POST"])
def push_send():
    body          = request.get_json(silent=True) or {}
    recipient_uid = body.get("recipientUid")
    title         = body.get("title", "Secret")
    msg_body      = body.get("body",  "New message")
    notif_type    = body.get("type",  "message")
    call_id       = body.get("callId", "")

    if not recipient_uid:
        return jsonify({"ok": False, "error": "Missing recipientUid"}), 400

    sub = _get_subscription(recipient_uid)
    if not sub:
        print(f"[Push] No subscription found for uid={recipient_uid}")
        return jsonify({"ok": False, "error": "No subscription found"}), 404

    payload = json.dumps({
        "title" : title,
        "body"  : msg_body,
        "type"  : notif_type,
        "callId": call_id,
        "icon"  : "/static/icon-192.png",
        "badge" : "/static/icon-192.png",
        "tag"   : "secret-call" if notif_type == "call" else "secret-msg",
    })

    try:
        webpush(
            subscription_info = sub,
            data              = payload,
            vapid_private_key = VAPID_PRIVATE_KEY,
            vapid_claims      = {"sub": f"mailto:{VAPID_CLAIMS_EMAIL}"}
        )
        print(f"[Push] ✅ Sent to uid={recipient_uid} type={notif_type}")
        return jsonify({"ok": True})

    except WebPushException as ex:
        print(f"[Push] ❌ WebPushException uid={recipient_uid}: {ex}")
        if ex.response and ex.response.status_code == 410:
            _sub_cache.pop(recipient_uid, None)
            if _fs_client:
                try:
                    _fs_client.collection("pushSubscriptions").document(recipient_uid).delete()
                except Exception:
                    pass
            return jsonify({"ok": False, "error": "Subscription expired"}), 410
        return jsonify({"ok": False, "error": str(ex)}), 500

@app.route("/api/send", methods=["POST"])
def send_message():
    data = request.get_json(silent=True) or {}
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"ok": False, "error": "Empty message"}), 400
    return jsonify({"ok": True, "message": {
        "id": f"msg_{datetime.now().timestamp()}",
        "text": text, "sender": "me",
        "time": datetime.now().strftime("%I:%M %p"),
    }})

@app.route("/health")
def health():
    return jsonify({"status": "ok", "app": "Secret",
                    "firebase": _fb_initialized,
                    "cached_subs": len(_sub_cache)})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n╔══════════════════════════════════════╗")
    print(f"║  Secret — Firestore Push Edition     ║")
    print(f"║  Running on http://0.0.0.0:{port}      ║")
    print(f"╚══════════════════════════════════════╝\n")
    app.run(host="0.0.0.0", port=port, debug=False)
