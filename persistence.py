"""
Atomic JSON persistence for trades and admin list.

Write strategy: write to .tmp then os.replace() — this is atomic on
POSIX filesystems, so a crash mid-write never corrupts the live file.
If the live file is corrupt (bad JSON), it's renamed to .corrupt and
we start fresh rather than crashing the bot.
"""

import json
import logging
import os

logger = logging.getLogger(__name__)

# BUG FIX (Render data loss): Render/Heroku jaise platforms ka filesystem
# EPHEMERAL hota hai — har deploy/restart pe local files delete ho jaati
# hain, matlab trades.json aur admins.json har baar reset ho rahe the
# (open trades ka crash-recovery aur admin list kaam nahi kar rahe the).
# Ab DATA_DIR env variable se persistent disk ka path set kar sakte hain
# (render.yaml dekho). Env na ho to local "data" folder hi use hota hai.
DATA_DIR = os.getenv("DATA_DIR", "data")
TRADES_FILE  = os.path.join(DATA_DIR, "trades.json")
ADMINS_FILE  = os.path.join(DATA_DIR, "admins.json")


def _ensure_dir() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)


# ─────────────────────────── trades ───────────────────────────

def load_trades_from_disk() -> tuple[list, int]:
    """
    Returns (trades_list, next_id).
    next_id is guaranteed to be > every id already in the list
    so there can never be a duplicate ID even after cleanup.
    """
    _ensure_dir()
    if not os.path.exists(TRADES_FILE):
        return [], 1

    try:
        with open(TRADES_FILE, encoding="utf-8") as f:
            data = json.load(f)

        trades  = data.get("trades", [])
        next_id = data.get("next_id")

        # Recompute if missing / stale (e.g. file was hand-edited)
        if not next_id or not isinstance(next_id, int):
            ids     = [t.get("id", 0) for t in trades if isinstance(t.get("id"), int)]
            next_id = (max(ids) + 1) if ids else 1

        logger.info(f"[PERSISTENCE] Loaded {len(trades)} trades, next_id={next_id}")
        return trades, next_id

    except Exception as e:
        logger.error(f"[PERSISTENCE] Corrupt trades file ({e}); backing up and starting fresh.")
        try:
            os.rename(TRADES_FILE, TRADES_FILE + ".corrupt")
        except OSError:
            pass
        return [], 1


def save_trades_to_disk(trades: list, next_id: int) -> None:
    _ensure_dir()
    tmp = TRADES_FILE + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"next_id": next_id, "trades": trades}, f,
                      ensure_ascii=False, indent=2)
        os.replace(tmp, TRADES_FILE)
    except Exception as e:
        logger.error(f"[PERSISTENCE] Save trades error: {e}")


# ─────────────────────────── admins ───────────────────────────

def load_admins() -> list[int]:
    _ensure_dir()
    if not os.path.exists(ADMINS_FILE):
        return []
    try:
        with open(ADMINS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return [int(x) for x in data] if isinstance(data, list) else []
    except Exception as e:
        logger.warning(f"[PERSISTENCE] Admin load error: {e}")
        return []


def save_admins(admins: list[int]) -> None:
    _ensure_dir()
    tmp = ADMINS_FILE + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(admins, f)
        os.replace(tmp, ADMINS_FILE)
    except Exception as e:
        logger.error(f"[PERSISTENCE] Save admins error: {e}")

# ────────────────────── WhatsApp subscribers ──────────────────────
# whatsapp.py ke liye: jin numbers ne START bheja hai unki list.
# Wahi atomic write pattern jo admins/trades ke liye use hota hai.

WA_SUBS_FILE = os.path.join(DATA_DIR, "wa_subscribers.json")


def load_wa_subscribers() -> list[str]:
    _ensure_dir()
    if not os.path.exists(WA_SUBS_FILE):
        return []
    try:
        with open(WA_SUBS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return [str(x) for x in data] if isinstance(data, list) else []
    except Exception as e:
        logger.warning(f"[PERSISTENCE] WhatsApp subscriber load error: {e}")
        return []


def save_wa_subscribers(numbers: list[str]) -> None:
    _ensure_dir()
    tmp = WA_SUBS_FILE + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(sorted({str(n) for n in numbers}), f)
        os.replace(tmp, WA_SUBS_FILE)
    except Exception as e:
        logger.error(f"[PERSISTENCE] Save WhatsApp subscribers error: {e}")
