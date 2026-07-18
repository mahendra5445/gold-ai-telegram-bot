from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from config import BOT_TOKEN
from data import get_candles
from strategy import get_signal
from formatter import format_signal


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 GOLD AI SCALPER PRO\n\n"
        "✅ Bot Online\n\n"
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
        candles["low"]
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
        candles["low"]
    )

    await update.message.reply_text(
        f"📈 Trend : {result['trend_strength']}\n"
        f"📊 Signal : {result['signal']}\n"
        f"📈 Confidence : {result['confidence']}%"
    )


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("gold", gold))
    app.add_handler(CommandHandler("signal", signal))
    app.add_handler(CommandHandler("trend", trend))

    print("🚀 Gold AI Scalper Pro Started...")

    app.run_polling()


if __name__ == "__main__":
    main()
