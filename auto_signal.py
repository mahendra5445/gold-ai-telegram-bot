import asyncio

from data import get_candles
from strategy import get_signal
from formatter import format_signal
from news import is_high_impact_news
from trade_tracker import save_trade

_last_signal = None


async def auto_signal_job(application):
    global _last_signal

    while True:
        try:
            candles = get_candles()

            if candles is None:
                print("[AUTO] Market data unavailable.")
                await asyncio.sleep(300)
                continue

            # ==========================
            # HIGH IMPACT NEWS FILTER
            # ==========================
            if is_high_impact_news():
                print("[NEWS FILTER] High Impact USD News - Signal Blocked")
                await asyncio.sleep(300)
                continue

            result = get_signal(
                candles["close"],
                candles["high"],
                candles["low"],
                candles["timeframes"],
                candles.get("volume"),
                candles.get("open"),
            )

            # NO TRADE होने पर कोई मैसेज नहीं भेजना
            if result["signal"] == "NO TRADE":
                print("[AUTO] No Trade")
                await asyncio.sleep(300)
                continue

            # Trade Save
            save_trade(result)

            message = format_signal(candles, result)

            # Duplicate Signal रोकना
            if message != _last_signal:

                admins = application.bot_data.get("admins", [])

                if not admins:
                    print("[AUTO] No users registered. Send /start first.")
                else:
                    for chat_id in admins:
                        try:
                            await application.bot.send_message(
                                chat_id=chat_id,
                                text=message,
                            )
                        except Exception as e:
                            print(f"[SEND ERROR] {e}")

                    _last_signal = message
                    print("[AUTO] Signal Sent")

        except Exception as e:
            print(f"[AUTO ERROR] {e}")

        # हर 5 मिनट बाद नया Signal Check करेगा
        await asyncio.sleep(300)
