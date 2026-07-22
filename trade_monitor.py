"""
Trade Monitor Job

Naye fixes:
  - TP1/TP2 ab realized R record karte hain (partial exits), sirf flag nahi.
  - Trade expiry enforce hoti hai -- ek stuck trade ab asset ko hamesha ke
    liye block nahi karega.
  - Har notification mein trade ka running R dikhta hai.
"""

import asyncio
import logging

from config import ASSETS
from data import get_latest_price
from shared_state import trade_lock
from trade_tracker import (
    get_open_trades, get_expired_trades, mark_tp_hit, close_trade,
)

logger = logging.getLogger(__name__)

CHECK_INTERVAL = 60   # FIX: 120s -> 60s. 2-minute sampling pe TP touches
                      # miss ho jaate the (monitor point-price dekhta hai,
                      # candle high/low nahi). 60s se miss kam honge, lekin
                      # ye poori tarah theek nahi hota -- iske liye candle
                      # data chahiye hoga, ye ek known limitation hai.

SL_BUFFER_PCT = 0.0003


async def _notify_all(application, text: str) -> None:
    admins = application.bot_data.get("admins", [])
    for chat_id in admins:
        try:
            await application.bot.send_message(chat_id=chat_id, text=text)
        except Exception as e:
            logger.error(f"[MONITOR SEND ERROR] chat_id={chat_id}: {e}")


def _compute_events(trade: dict, price: float) -> list[str]:
    is_buy = trade["signal"] == "BUY"
    events: list[str] = []

    sl_buffer = abs(trade["sl"]) * SL_BUFFER_PCT
    sl_hit = (
        (is_buy and price <= trade["sl"] - sl_buffer) or
        (not is_buy and price >= trade["sl"] + sl_buffer)
    )
    if sl_hit:
        events.append("be" if trade["hit_tp1"] else "sl")
        return events

    # FIX: pehle teenon TP hardcoded the. Ab sirf wahi targets check hote
    # hain jo actually set hain -- single-TP structure ke liye zaroori.
    n = trade.get("n_targets") or sum(1 for k in ("tp1", "tp2", "tp3")
                                      if trade.get(k) is not None)
    for i in range(1, n + 1):
        lvl = trade.get(f"tp{i}")
        if lvl is None or trade.get(f"hit_tp{i}"):
            continue
        if (is_buy and price >= lvl) or (not is_buy and price <= lvl):
            events.append(f"tp{i}")

    return events


async def _check_trade(application, trade: dict, price: float) -> None:
    notifications: list[str] = []
    decimals = ASSETS.get(trade["asset"].lower(), {}).get("decimals", 2)
    px = round(price, decimals)
    head = f"#{trade['id']} | {trade['asset'].upper()} | {trade['signal']}"

    async with trade_lock:
        if trade["status"] != "OPEN":
            return

        events = _compute_events(trade, price)
        if not events:
            return

        for level in events:
            if level in ("sl", "be"):
                status = "SL" if level == "sl" else "BE"
                if close_trade(trade, price, status):
                    r = trade["realized_r"]
                    if level == "sl":
                        notifications.append(
                            f"🛑 SL HIT\n\n{head}\n"
                            f"Entry : {trade['entry']}\nSL    : {trade['sl']}\n"
                            f"Price : {px}\n\nResult: {r:+.2f}R ❌"
                        )
                    else:
                        notifications.append(
                            f"⚪ CLOSED AT BREAKEVEN STOP\n\n{head}\n"
                            f"Entry : {trade['entry']}\nPrice : {px}\n\n"
                            f"TP1 pehle secure ho chuka tha.\nResult: {r:+.2f}R"
                        )
                break

            elif level.startswith("tp"):
                n = int(level[-1])
                is_last = n >= (trade.get("n_targets") or 3)
                gained = mark_tp_hit(trade, n)
                if is_last or trade["remaining"] <= 1e-9:
                    close_trade(trade, price, "TP")
                    notifications.append(
                        f"{'🎯' * n} TP{n} HIT — TARGET COMPLETE\n\n{head}\n"
                        f"Entry : {trade['entry']}\nTP{n}   : {trade[f'tp{n}']}\n"
                        f"Price : {px}\n\nResult: {trade['realized_r']:+.2f}R 🏆"
                    )
                    break
                extra = "\n✅ SL moved to Breakeven" if n == 1 else ""
                notifications.append(
                    f"{'🎯' * n} TP{n} HIT\n\n{head}\n"
                    f"Entry : {trade['entry']}\nTP{n}   : {trade[f'tp{n}']}\n"
                    f"Price : {px}\n\n"
                    f"Booked: +{gained:.2f}R  |  Total: {trade['realized_r']:+.2f}R\n"
                    f"Remaining: {trade['remaining']:.0%}{extra}"
                )

    for msg in notifications:
        await _notify_all(application, msg)


async def _expire_trades(application, prices: dict) -> None:
    """NAYA: purane open trades ko time pe band karo taaki asset unblock ho."""
    expired = get_expired_trades()
    if not expired:
        return

    notes = []
    async with trade_lock:
        for trade in expired:
            if trade["status"] != "OPEN":
                continue
            price = prices.get(trade["asset"])
            if price is None:
                continue
            if close_trade(trade, price, "EXPIRED"):
                dec = ASSETS.get(trade["asset"].lower(), {}).get("decimals", 2)
                notes.append(
                    f"⏳ TRADE EXPIRED\n\n"
                    f"#{trade['id']} | {trade['asset'].upper()} | {trade['signal']}\n"
                    f"Entry : {trade['entry']}\nPrice : {round(price, dec)}\n\n"
                    f"Time limit reached — closed.\nResult: {trade['realized_r']:+.2f}R"
                )

    for msg in notes:
        await _notify_all(application, msg)


async def trade_monitor_job(application) -> None:
    logger.info("[MONITOR] Trade monitor started")
    while True:
        try:
            open_trades = get_open_trades()

            if open_trades:
                asset_list = list({t["asset"] for t in open_trades})
                fetched = await asyncio.gather(
                    *(asyncio.to_thread(get_latest_price, a) for a in asset_list),
                    return_exceptions=True,
                )
                prices: dict[str, float | None] = {}
                for a, res in zip(asset_list, fetched):
                    if isinstance(res, Exception):
                        logger.error(f"[MONITOR] Price fetch failed for {a.upper()}: {res}")
                        prices[a] = None
                    else:
                        prices[a] = res

                for trade in list(open_trades):
                    price = prices.get(trade["asset"])
                    if price is None:
                        logger.warning(f"[MONITOR] No price for {trade['asset'].upper()} — skipping")
                        continue
                    await _check_trade(application, trade, price)

                await _expire_trades(application, prices)

        except Exception as e:
            logger.error(f"[MONITOR ERROR] {e}")

        await asyncio.sleep(CHECK_INTERVAL)
