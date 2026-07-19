
import asyncio

from data import get_latest_price
from trade_tracker import get_open_trades, update_trade, find_trade

CHECK_INTERVAL = 60  # seconds


async def _notify_all(application, text):
    admins = application.bot_data.get("admins", [])
    for chat_id in admins:
        try:
            await application.bot.send_message(chat_id=chat_id, text=text)
        except Exception as e:
            print(f"[MONITOR SEND ERROR] {e}")


def _target_hit(trade, price):
    """
    Returns a list of (level_key, label) newly hit at this price,
    in order (TP1 -> TP2 -> TP3 -> SL close), plus whether the trade
    should now be closed.
    """
    is_buy = trade["signal"] == "BUY"
    events = []

    # Stop Loss checked first - protects capital, closes trade immediately
    sl_hit = (is_buy and price <= trade["sl"]) or (not is_buy and price >= trade["sl"])
    if sl_hit:
        return [("sl", None)]

    if not trade["hit_tp1"]:
        if (is_buy and price >= trade["tp1"]) or (not is_buy and price <= trade["tp1"]):
            events.append(("tp1", None))

    if not trade["hit_tp2"]:
        if (is_buy and price >= trade["tp2"]) or (not is_buy and price <= trade["tp2"]):
            events.append(("tp2", None))

    if not trade["hit_tp3"]:
        if (is_buy and price >= trade["tp3"]) or (not is_buy and price <= trade["tp3"]):
            events.append(("tp3", None))

    return events


async def _check_trade(application, trade, price):
    events = _target_hit(trade, price)

    for level, _ in events:
        if level == "sl":
            update_trade(trade["id"], "SL")
            await _notify_all(
                application,
                f"🛑 SL HIT\n\n"
                f"#{trade['id']} | {trade['asset'].upper()} | {trade['signal']}\n"
                f"Entry : {trade['entry']}\n"
                f"SL : {trade['sl']}\n"
                f"Price : {round(price, 2)}\n\n"
                f"Trade Closed ❌",
            )
            return  # trade closed, nothing else to check

        if level == "tp1":
            trade["hit_tp1"] = True
            await _notify_all(
                application,
                f"🎯 TP1 HIT\n\n"
                f"#{trade['id']} | {trade['asset'].upper()} | {trade['signal']}\n"
                f"Entry : {trade['entry']}\n"
                f"TP1 : {trade['tp1']}\n"
                f"Price : {round(price, 2)}\n\n"
                f"✅ Move SL to breakeven",
            )

        elif level == "tp2":
            trade["hit_tp2"] = True
            await _notify_all(
                application,
                f"🎯🎯 TP2 HIT\n\n"
                f"#{trade['id']} | {trade['asset'].upper()} | {trade['signal']}\n"
                f"Entry : {trade['entry']}\n"
                f"TP2 : {trade['tp2']}\n"
                f"Price : {round(price, 2)}\n\n"
                f"✅ Trail SL for remaining position",
            )

        elif level == "tp3":
            trade["hit_tp3"] = True
            update_trade(trade["id"], "TP")
            await _notify_all(
                application,
                f"🎯🎯🎯 TP3 HIT - FINAL TARGET\n\n"
                f"#{trade['id']} | {trade['asset'].upper()} | {trade['signal']}\n"
                f"Entry : {trade['entry']}\n"
                f"TP3 : {trade['tp3']}\n"
                f"Price : {round(price, 2)}\n\n"
                f"✅ Trade Closed - Full Target Hit 🏆",
            )


async def trade_monitor_job(application):
    while True:
        try:
            open_trades = get_open_trades()

            if open_trades:
                needed_assets = {t["asset"] for t in open_trades}
                prices = {}

                for asset in needed_assets:
                    prices[asset] = get_latest_price(asset)

                for trade in open_trades:
                    price = prices.get(trade["asset"])
                    if price is None:
                        continue
                    await _check_trade(application, trade, price)

        except Exception as e:
            print(f"[MONITOR ERROR] {e}")

        await asyncio.sleep(CHECK_INTERVAL)
