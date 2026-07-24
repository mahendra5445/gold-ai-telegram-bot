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

# ── POSTGRES BACKEND ──────────────────────────────────────────────────────
# Railway par volume ke bina container ka filesystem har deploy/restart pe
# mit jaata hai — isi wajah se 84 trades do baar gaye. DATABASE_URL set ho
# to trades Postgres mein jaate hain aur deploy se kabhi nahi jaate.
# DATABASE_URL na ho to sab kuch pehle jaisa hi chalta hai (JSON file).
# Railway Postgres add karte hi DATABASE_URL apne aap set kar deta hai.
DATABASE_URL = os.getenv("DATABASE_URL")


def _pg():
    import psycopg
    return psycopg.connect(DATABASE_URL, connect_timeout=10)


def _pg_init() -> None:
    with _pg() as c:
        c.execute(
            "CREATE TABLE IF NOT EXISTS bot_state ("
            "  key   TEXT PRIMARY KEY,"
            "  value JSONB NOT NULL,"
            "  updated TIMESTAMPTZ NOT NULL DEFAULT now())"
        )


def _pg_load() -> tuple[list, int] | None:
    """(trades, next_id) ya None agar Postgres available/khaali nahi."""
    try:
        _pg_init()
        with _pg() as c:
            row = c.execute(
                "SELECT value FROM bot_state WHERE key = 'trades'"
            ).fetchone()
        if not row:
            logger.info("[PERSISTENCE] Postgres khaali — fresh start")
            return [], 1
        data = row[0]
        trades = data.get("trades", [])
        next_id = data.get("next_id")
        if not next_id or not isinstance(next_id, int):
            ids = [t.get("id", 0) for t in trades if isinstance(t.get("id"), int)]
            next_id = (max(ids) + 1) if ids else 1
        logger.info(f"[PERSISTENCE] Postgres se {len(trades)} trades, next_id={next_id}")
        return trades, next_id
    except Exception as e:
        logger.error(f"[PERSISTENCE] Postgres load fail ({e}) — file par gir rahe hain")
        return None


def _pg_save(trades: list, next_id: int) -> bool:
    try:
        _pg_init()
        with _pg() as c:
            c.execute(
                "INSERT INTO bot_state (key, value, updated) "
                "VALUES ('trades', %s, now()) "
                "ON CONFLICT (key) DO UPDATE "
                "SET value = EXCLUDED.value, updated = now()",
                (json.dumps({"next_id": next_id, "trades": trades}),),
            )
        return True
    except Exception as e:
        logger.error(f"[PERSISTENCE] Postgres save fail ({e}) — file par gir rahe hain")
        return False

TRADES_FILE  = os.path.join(DATA_DIR, "trades.json")


def _ensure_dir() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)


# ─────────────────────────── trades ───────────────────────────

def load_trades_from_disk() -> tuple[list, int]:
    """
    Returns (trades_list, next_id).

    DATABASE_URL set ho to Postgres se, warna JSON file se.
    next_id is guaranteed to be > every id already in the list
    so there can never be a duplicate ID even after cleanup.
    """
    if DATABASE_URL:
        got = _pg_load()
        if got is not None:
            return got

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
    if DATABASE_URL and _pg_save(trades, next_id):
        return

    _ensure_dir()
    tmp = TRADES_FILE + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"next_id": next_id, "trades": trades}, f,
                      ensure_ascii=False, indent=2)
        os.replace(tmp, TRADES_FILE)
    except Exception as e:
        logger.error(f"[PERSISTENCE] Save trades error: {e}")

