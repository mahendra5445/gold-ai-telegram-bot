"""
WhatsApp Cloud API integration for AI Scalper Pro V5.5

Kyun zaroori hai: repo mein sirf run_polling() tha, koi HTTP server nahi —
isliye Meta ka webhook verification (jo ek GET request bhejta hai) hamesha
fail hota tha. Ye module ek chhota Flask server ek daemon thread mein
chalata hai, Telegram polling loop ko bilkul touch kiye bina.

Endpoints:
  GET  /          — plain "alive" text
  GET  /health    — JSON uptime check (Railway healthcheck ke liye)
  GET  /webhook   — Meta verification handshake (hub.challenge echo)
  POST /webhook   — incoming messages: START / STOP / STATUS

Env vars:
  WHATSAPP_TOKEN            Meta access token (permanent token recommended)
  WHATSAPP_PHONE_NUMBER_ID  Meta dashboard se Phone number ID
  WHATSAPP_VERIFY_TOKEN     Meta mein jo token type kiya, default ai_scalper_pro_2026
  PORT                      Railway khud inject karta hai (default 8080)
"""

import logging
import os
import threading

import requests
from flask import Flask, request

from persistence import load_wa_subscribers, save_wa_subscribers

logger = logging.getLogger(__name__)

# ─────────────────────────── config ───────────────────────────
WA_TOKEN = os.getenv("WHATSAPP_TOKEN", "")
WA_PHONE_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
WA_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "ai_scalper_pro_2026")
GRAPH_API_VERSION = os.getenv("WHATSAPP_API_VERSION", "v20.0")
PORT = int(os.getenv("PORT", "8080"))

# Meta ki 24-hour customer service window ke bahar sirf approved template
# bheja ja sakta hai. Free-form text tabhi jaata hai jab user ne pichhle
# 24 ghante mein kuch bheja ho — isliye users ko roz kam se kam ek baar
# STATUS bhejne ko kaha jaata hai (WHATSAPP_SETUP.md dekho).
GRAPH_URL = (
    f"https://graph.facebook.com/{GRAPH_API_VERSION}/{WA_PHONE_ID}/messages"
)

# Subscriber list disk pe hai, par writes ko serialise karna zaroori hai —
# Flask threaded=True hai, do requests ek saath aa sakti hain.
_subs_lock = threading.Lock()


def is_configured() -> bool:
    """True agar dono credentials set hain. Warna server chalega hi nahi."""
    return bool(WA_TOKEN and WA_PHONE_ID)


# ───────────────────── subscriber helpers ─────────────────────

def get_subscribers() -> list[str]:
    try:
        return load_wa_subscribers()
    except Exception as e:
        logger.error(f"[WA] Subscriber load failed: {e}")
        return []


def _add_subscriber(number: str) -> bool:
    with _subs_lock:
        subs = set(get_subscribers())
        if number in subs:
            return False
        subs.add(number)
        save_wa_subscribers(list(subs))
        logger.info(f"[WA] New subscriber ({len(subs)} total)")
        return True


def _remove_subscriber(number: str) -> bool:
    with _subs_lock:
        subs = set(get_subscribers())
        if number not in subs:
            return False
        subs.discard(number)
        save_wa_subscribers(list(subs))
        logger.info(f"[WA] Subscriber removed ({len(subs)} left)")
        return True


# ─────────────────────── outbound sending ──────────────────────

def send_text(to: str, body: str) -> bool:
    """Ek plain text message bhejo. Blocking call — async code se
    asyncio.to_thread() ke through call karna."""
    if not is_configured():
        logger.warning("[WA] Token/phone-id missing — send skipped")
        return False

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "text",
        "text": {"preview_url": False, "body": body[:4000]},
    }
    headers = {
        "Authorization": f"Bearer {WA_TOKEN}",
        "Content-Type": "application/json",
    }
    try:
        r = requests.post(GRAPH_URL, json=payload, headers=headers, timeout=15)
        if r.status_code >= 400:
            logger.error(f"[WA] Send failed {r.status_code}: {r.text[:300]}")
            return False
        return True
    except Exception as e:
        logger.error(f"[WA] Send exception: {e}")
        return False


def broadcast(text: str) -> int:
    """Sab subscribers ko message bhejo. Kitne successfully gaye wo return
    karta hai. BLOCKING — auto_signal se asyncio.to_thread() ke saath."""
    subs = get_subscribers()
    if not subs:
        return 0
    sent = sum(1 for number in subs if send_text(number, text))
    logger.info(f"[WA] Broadcast {sent}/{len(subs)} delivered")
    return sent


# ───────────────────────── commands ────────────────────────────

def _status_text() -> str:
    """Live bot status. trade_tracker lazily import hota hai taake
    import cycle na bane."""
    try:
        from trade_tracker import get_stats

        s = get_stats()
        return (
            "🤖 AI SCALPER PRO V5.5 — ONLINE\n\n"
            f"📈 Total signals : {s['total']}  (open: {s['open']})\n"
            f"💰 Expectancy    : {s['expectancy']:+.4f} R/trade\n"
            f"🏆 Win rate      : {s['win_rate']}%\n"
            f"📊 Total         : {s['total_r']:+.2f} R\n\n"
            f"👥 Subscribers   : {len(get_subscribers())}"
        )
    except Exception as e:
        logger.error(f"[WA] Status build failed: {e}")
        return (
            "🤖 AI SCALPER PRO V5.5 — ONLINE\n\n"
            f"👥 Subscribers: {len(get_subscribers())}\n"
            "Stats abhi available nahi."
        )


_HELP = (
    "Commands:\n"
    "START  — signals receive karna shuru karo\n"
    "STOP   — signals band karo\n"
    "STATUS — bot status aur stats"
)


def handle_command(from_number: str, text: str) -> None:
    cmd = (text or "").strip().upper()

    if cmd in ("START", "/START", "SUBSCRIBE", "HI", "HELLO"):
        added = _add_subscriber(from_number)
        send_text(
            from_number,
            "✅ Subscribed! Ab har naya signal yahan aayega.\n\n" + _HELP
            if added
            else "Aap pehle se subscribed hain.\n\n" + _HELP,
        )

    elif cmd in ("STOP", "/STOP", "UNSUBSCRIBE"):
        removed = _remove_subscriber(from_number)
        send_text(
            from_number,
            "🛑 Unsubscribed. START bhej kar dobara shuru kar sakte hain."
            if removed
            else "Aap subscribed nahi hain. START bhejein.",
        )

    elif cmd in ("STATUS", "/STATUS", "STATS"):
        send_text(from_number, _status_text())

    else:
        send_text(from_number, _HELP)


# ─────────────────────────── Flask app ─────────────────────────
app = Flask(__name__)


@app.get("/")
def _root():
    return "AI Scalper Pro V5.5 is running", 200


@app.get("/health")
def _health():
    return {
        "status": "ok",
        "whatsapp_configured": is_configured(),
        "subscribers": len(get_subscribers()),
    }, 200


@app.get("/webhook")
def _verify():
    """Meta ise ek baar call karta hai jab aap 'Verify and Save' dabate hain."""
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == WA_VERIFY_TOKEN:
        logger.info("[WA] Webhook verified ✅")
        return challenge or "", 200

    logger.warning(f"[WA] Webhook verification failed (mode={mode})")
    return "forbidden", 403


@app.post("/webhook")
def _incoming():
    """Incoming messages. Hamesha 200 turant return karo warna Meta
    baar-baar retry karta hai aur webhook ko disable kar deta hai."""
    data = request.get_json(silent=True) or {}
    try:
        for entry in data.get("entry", []) or []:
            for change in entry.get("changes", []) or []:
                value = change.get("value", {}) or {}
                for msg in value.get("messages", []) or []:
                    if msg.get("type") != "text":
                        continue
                    from_number = msg.get("from")
                    body = (msg.get("text") or {}).get("body", "")
                    if from_number:
                        handle_command(from_number, body)
    except Exception as e:
        logger.error(f"[WA] Webhook processing error: {e}")
    return "ok", 200


# ────────────────────── server bootstrap ───────────────────────

def _run_server() -> None:
    # use_reloader=False zaroori hai — reloader process fork karta hai,
    # jo Telegram polling loop ko duplicate kar dega.
    app.run(host="0.0.0.0", port=PORT, threaded=True, use_reloader=False)


def start_whatsapp_server() -> threading.Thread | None:
    """Flask ko daemon thread mein start karo. Daemon isliye taake main
    process exit ho to ye bhi mar jaaye."""
    thread = threading.Thread(
        target=_run_server, name="whatsapp-server", daemon=True
    )
    thread.start()
    if is_configured():
        logger.info(f"[WA] Server started on port {PORT} — webhook ready")
    else:
        logger.warning(
            f"[WA] Server started on port {PORT}, but WHATSAPP_TOKEN / "
            "WHATSAPP_PHONE_NUMBER_ID set nahi hain — webhook verify ho "
            "jayega par messages send nahi honge."
        )
    return thread


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _run_server()
