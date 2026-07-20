"""
Trade Monitor Job

Fixes applied:
  #4  TP1/BE persistence   — mark_tp1_hit() / mark_tp2_hit() now persist the
                             updated trade dict to disk immediately.
  #7  Race condition       — trade_lock acquired during state mutations; Telegram
                             sends happen outside the lock.
 #12  Crash recovery       — open trades survive restart via JSON persistence.
"""

import asyncio
import logging

from config import ASSETS
from data import get_latest_price
from shared_state import trade_lock
from trade_tracker import (
    get_open_trades,
    mark_tp1_hit,
    mark_tp2_hit,
    update_trade,
)

logger = logging.getLogger(__name__)

CHECK_INTERVAL = 120   # seconds — check every 2 min for responsive TP tracking


# ── helpers ───────────────────────────────────────────────────────────────

async def _notify_all(application, text: str) -> None:
    admins = application.bot_data.get("admins", [])
    for chat_id in admins:
        try:
            await application.bot.send_message(chat_id=chat_id, text=text)
        except Exception as e:
            logger.error(f"[MONITOR SEND ERROR] chat_id={chat_id}: {e}")


def _compute_events(trade: dict, price: float) -> list[str]:
    """
    Returns a list of event strings that have just been triggered at
    this price, in priority order (SL/BE first, then TP1→TP2→TP3).
    The list is computed against the trade's CURRENT state so that
    levels already hit are correctly excluded.
    """
    is_buy = trade["signal"] == "BUY"
    events: list[str] = []

    # ── Stop Loss / Breakeven ─────────────────────────────────────────────
    sl_hit = (
        (is_buy     and price <= trade["sl"]) or
        (not is_buy and price >= trade["sl"])
    )
    if sl_hit:
        # If TP1 was already hit, SL at entry = breakeven close
        events.append("be" if trade["hit_tp1"] else "sl")
        return events   # trade closes here — no TPs to check

    # ── Take Profits ──────────────────────────────────────────────────────
    if not trade["hit_tp1"]:
        if (is_buy and price >= trade["tp1"]) or (not is_buy and price <= trade["tp1"]):
            events.append("tp1")

    if not trade["hit_tp2"]:
        if (is_buy and price >= trade["tp2"]) or (not is_buy and price <= trade["tp2"]):
            events.append("tp2")

    if not trade["hit_tp3"]:
        if (is_buy and price >= trade["tp3"]) or (not is_buy and price <= trade["tp3"]):
            events.append("tp3")

    return events


# ── per-trade check ───────────────────────────────────────────────────────

async def _check_trade(application, trade: dict, price: float) -> None:
    notifications: list[str] = []
    trade_closed = False

    decimals = ASSETS.get(trade["asset"].lower(), {}).get("decimals", 2)
    price_display = round(price, decimals)

    # ── Critical section: mutate state atomically ─────────────────────────
    async with trade_lock:
        # Re-check status inside lock (another coroutine may have closed
        # this trade between the price fetch and acquiring the lock)
        if trade["status"] != "OPEN":
            return

        # BUG FIX: events pehle lock ke BAHAR compute hote the — us waqt ka
        # trade state (hit_tp1, sl) purana ho sakta tha. Example: TP1 abhi
        # hit hua aur SL entry pe move hua, lekin purane state se compute
        # kiya "sl" event ab bhi purane SL pe fire karke trade ko galat
        # "SL Hit" mark kar deta. Ab events lock ke andar fresh state se
        # compute hote hain.
        events = _compute_events(trade, price)
        if not events:
            return

        for level in events:
            if level in ("sl", "be"):
                status = "SL" if level == "sl" else "BE"
                if update_trade(trade["id"], status):
                    if level == "sl":
                        notifications.append(
                            f"🛑 SL HIT\n\n"
                            f"#{trade['id']} | {trade['asset'].upper()} | {trade['signal']}\n"
                            f"Entry : {trade['entry']}\n"
                            f"SL    : {trade['sl']}\n"
                            f"Price : {price_display}\n\n"
                            f"Trade Closed ❌"
                        )
                    else:
                        notifications.append(
                            f"⚪ BREAKEVEN\n\n"
                            f"#{trade['id']} | {trade['asset'].upper()} | {trade['signal']}\n"
                            f"Entry : {trade['entry']}\n"
                            f"Price : {price_display}\n\n"
                            f"Closed at Breakeven — TP1 was already secured ✅"
                        )
                trade_closed = True
                break   # trade closed — ignore remaining events

            elif level == "tp1":
                mark_tp1_hit(trade)   # sets hit_tp1=True, sl=entry, persists
                notifications.append(
                    f"🎯 TP1 HIT\n\n"
                    f"#{trade['id']} | {trade['asset'].upper()} | {trade['signal']}\n"
                    f"Entry : {trade['entry']}\n"
                    f"TP1   : {trade['tp1']}\n"
                    f"Price : {price_display}\n\n"
                    f"✅ SL moved to Breakeven"
                )

            elif level == "tp2":
                mark_tp2_hit(trade)   # persists
                notifications.append(
                    f"🎯🎯 TP2 HIT\n\n"
                    f"#{trade['id']} | {trade['asset'].upper()} | {trade['signal']}\n"
                    f"Entry : {trade['entry']}\n"
                    f"TP2   : {trade['tp2']}\n"
                    f"Price : {price_display}\n\n"
                    f"✅ Trail SL for remaining position"
                )

            elif level == "tp3":
                trade["hit_tp3"] = True
                if update_trade(trade["id"], "TP"):   # persists inside
                    notifications.append(
                        f"🎯🎯🎯 TP3 HIT — FULL TARGET\n\n"
                        f"#{trade['id']} | {trade['asset'].upper()} | {trade['signal']}\n"
                        f"Entry : {trade['entry']}\n"
                        f"TP3   : {trade['tp3']}\n"
                        f"Price : {price_display}\n\n"
                        f"✅ Trade Closed — Full Target Hit 🏆"
                    )
                trade_closed = True
                break   # trade closed — ignore remaining events

    # ── Send notifications outside lock ───────────────────────────────────
    for msg in notifications:
        await _notify_all(application, msg)


# ── main job loop ─────────────────────────────────────────────────────────

async def trade_monitor_job(application) -> None:
    logger.info("[MONITOR] Trade monitor started")
    while True:
        try:
            open_trades = get_open_trades()

            if open_trades:
                # Fetch prices for all needed assets in one batch
                needed_assets = {t["asset"] for t in open_trades}
                prices: dict[str, float | None] = {}
                for asset in needed_assets:
                    prices[asset] = get_latest_price(asset)

                # Iterate over a snapshot copy so mutations don't affect the loop
                for trade in list(open_trades):
                    price = prices.get(trade["asset"])
                    if price is None:
                        logger.warning(
                            f"[MONITOR] No price for {trade['asset'].upper()} — skipping"
                        )
                        continue
                    await _check_trade(application, trade, price)

        except Exception as e:
            logger.error(f"[MONITOR ERROR] {e}")

        await asyncio.sleep(CHECK_INTERVAL)
