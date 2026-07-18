import asyncio

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from config import BOT_TOKEN
from data import get_candles
from strategy import get_signal
from formatter import format_signal
from auto_signal import auto_signal_job


async def post_init(application):
    asyncio.create_task(auto_signal_job(application))


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    admins = context.application.bot_data.setdefault("admins", [])
    if chat_id not in admins:
        admins.append(chat_id)

    await update.message.reply_text(
        "🤖 GOLD AI SCALPER PRO v2.0.1\n\n"
        "✅ Bot Online\n\n"
        "📡 Auto Signal Enabled\n\n"
        "Commands:\n"
        "/gold - Gold Analysis\n"
        "/signal - Trading Signal\n"
        "/trend - Trend Analysis\n"
        "/start - Start Bot"
    )


async def gold(update: Update, context: ContextTypes.DEFAULT_TYPE):
    candles = get_candles()

    if candles is None:
        await update.message.reply_text(
            "❌ Market data unavailable."
        )
        return

    result = get_signal(
        candles["close"],
        candles["high"],
        candles["low"],
        candles["timeframes"]
    )

    message = format_signal(candles, result)

    await update.message.reply_text(message)


async def signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await gold(update, context)


async def trend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    candles = get_candles()

    if candles is None:
        await update.message.reply_text(
            "❌ Market data unavailable."
        )
        return

    result = get_signal(
        candles["close"],
        candles["high"],
        candles["low"],
        candles["timeframes"]
    )

    await update.message.reply_text(
        f"📊 1M Trend : {result['trend_1m']}\n"
        f"📊 5M Trend : {result['trend_5m']}\n"
        f"📊 15M Trend : {result['trend_15m']}\n\n"
        f"📈 Overall Trend : {result['trend_strength']}\n"
        f"📢 Signal : {result['signal']}\n"
        f"🔥 Confidence : {result['confidence']}%"
    )


def main():
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("gold", gold))
    app.add_handler(CommandHandler("signal", signal))
    app.add_handler(CommandHandler("trend", trend))

    print("🚀 Gold AI Scalper Pro v2.0.1 Started...")

    app.run_polling()


if __name__ == "__main__":
    main()
