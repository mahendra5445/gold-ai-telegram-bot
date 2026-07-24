"""
Risk guardrails — signal bot ke liye jo REALISTIC hai wahi.

Ye bot orders place nahi karta, isliye lot size / margin / free margin
/ equity protection yahan implement nahi ho sakte -- unke liye broker
account ka connection chahiye. Jo cheezein signal level par sach mein
lag sakti hain, sirf wo yahan hain.
"""

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

MAX_OPEN_TRADES       = 4     # ek waqt par kitne assets par trade khula rahe
MAX_SIGNALS_PER_DAY   = 12    # roz ki signal limit (UTC din)
MAX_CONSEC_LOSSES     = 4     # itni lagataar haar ke baad auto-pause
PAUSE_AFTER_LOSS_HRS  = 6     # pause kitne ghante chale


_paused_until: datetime | None = None


def _utc_today(ts) -> bool:
    try:
        d = ts if isinstance(ts, datetime) else datetime.fromisoformat(str(ts))
    except Exception:
        return False
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.date() == datetime.now(timezone.utc).date()


def consecutive_losses(trades: list[dict]) -> int:
    """Sabse haal ke closed trades se peeche ki taraf ginte hain."""
    from analytics import realized_r
    n = 0
    for t in reversed(trades):
        r = realized_r(t)
        if r is None:
            continue
        if r < 0:
            n += 1
        else:
            break
    return n


def check(trades: list[dict]) -> tuple[bool, str | None]:
    """
    (allowed, reason) lautata hai. auto_signal isse trade banane se
    PEHLE call kare.
    """
    global _paused_until
    now = datetime.now(timezone.utc)

    if _paused_until and now < _paused_until:
        return False, f"auto-pause active until {_paused_until:%H:%M} UTC"
    if _paused_until and now >= _paused_until:
        _paused_until = None
        logger.info("[GUARD] pause khatm — trading dobara chalu")

    open_n = sum(1 for t in trades if t.get("status") == "OPEN")
    if open_n >= MAX_OPEN_TRADES:
        return False, f"{open_n} trades pehle se khule hain (limit {MAX_OPEN_TRADES})"

    today_n = sum(1 for t in trades if _utc_today(t.get("time")))
    if today_n >= MAX_SIGNALS_PER_DAY:
        return False, f"aaj {today_n} signals ho chuke (limit {MAX_SIGNALS_PER_DAY})"

    cl = consecutive_losses(trades)
    if cl >= MAX_CONSEC_LOSSES:
        _paused_until = now.replace(microsecond=0) + \
            __import__("datetime").timedelta(hours=PAUSE_AFTER_LOSS_HRS)
        logger.warning(
            f"[GUARD] {cl} lagataar haar — {PAUSE_AFTER_LOSS_HRS}h ka auto-pause"
        )
        return False, f"{cl} lagataar haar — {PAUSE_AFTER_LOSS_HRS}h pause"

    return True, None
