import asyncio
from strategy import get_signal

_last_signal = None


async def auto_signal_job(application):
    global _last_signal

    while True:
        try:
            signal = get_signal()

            if signal:
                signal_text = str(signal)

                if signal_text != _last_signal:
                    for admin_id in application.bot_data.get("admins", []):
                        await application.bot.send_message(
                            chat_id=admin_id,
                            text=signal_text
                        )

                    _last_signal = signal_text

        except Exception as e:
            print(f"[AUTO SIGNAL ERROR] {e}")

        await asyncio.sleep(300)   # 5 minutes
