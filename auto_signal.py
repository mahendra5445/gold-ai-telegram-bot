import asyncio

from data import get_candles
from strategy import get_signal
from formatter import format_signal

_last_signal = None


async def auto_signal_job(application):
    global _last_signal

    while True:
        try:
            candles = get_candles()

            if candles is None:
                await asyncio.sleep(300)
                continue

            result = get_signal(
                candles["close"],
                candles["high"],
                candles["low"],
                candles["timeframes"]
            )

            # NO TRADE पर कोई मैसेज नहीं
            if result["signal"] == "NO TRADE":
                await asyncio.sleep(300)
                continue

            message = format_signal(candles, result)

            # Duplicate Signal Protection
            if message != _last_signal:

                admins = application.bot_data.get("admins", [])

                for chat_id in admins:
                    try:
                        await application.bot.send_message(
                            chat_id=chat_id,
                            text=message
                        )
                    except Exception as e:
                        print(f"[SEND ERROR] {e}")

                _last_signal = message

        except Exception as e:
            print(f"[AUTO SIGNAL ERROR] {e}")

        await asyncio.sleep(300)
