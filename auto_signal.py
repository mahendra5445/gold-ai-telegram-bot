import asyncio

from data import get_candles
from strategy import get_signal
from formatter import format_signal
from news import is_high_impact_news
from trade_tracker import save_trade

_last_signal = {"gold": None, "btc": None}


async def _check_asset(application, asset):
    global _last_signal

    candles = get_candles(asset)

    result = get_signal(
        candles["close"],
        candles["high"],
        candles["low"],
        candles["timeframes"],
        candles.get("volume"),
        candles.get("open"),
    )

    if result["signal"] == "NO TRADE":
        print(f"[AUTO] {asset.upper()} No Trade")
        return

    save_trade(result, asset=asset)

    message = format_signal(candles, result)

    if message == _last_signal.get(asset):
        return

    admins = application.bot_data.get("admins", [])

    if not admins:
        print("[AUTO] No users registered. Send /start first.")
        return

    for chat_id in admins:
        try:
            await application.bot.send_message(
                chat_id=chat_id,
                text=message,
            )
        except Exception as e:
            print(f"[SEND ERROR] {e}")

    _last_signal[asset] = message
    print(f"[AUTO] {asset.upper()} Signal Sent")


async def auto_signal_job(application):
    while True:
        try:
            if is_high_impact_news():
                print("[NEWS FILTER] High Impact USD News - Signal Blocked")
                await asyncio.sleep(300)
                continue

            await _check_asset(application, "gold")
            await _check_asset(application, "btc")

        except Exception as e:
            print(f"[AUTO ERROR] {e}")

        await asyncio.sleep(300)
