from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from config import BOT_TOKEN
from data import get_candles
from strategy import get_signal


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Gold AI Bot Online!\n\n"
        "Commands:\n"
        "/gold - Gold Analysis\n"
        "/start - Start Bot"
    )


async def gold(update: Update, context: ContextTypes.DEFAULT_TYPE):
    candles = get_candles()

    if candles is None:
        await update.message.reply_text("❌ Market data unavailable.")
        return

    result = get_signal(candles["close"])

    message = (
        "📊 GOLD AI SCALPING\n\n"
        f"💰 Price : {candles['price']}\n\n"
        f"📈 EMA20 : {result['ema20']}\n"
        f"📈 EMA50 : {result['ema50']}\n"
        f"📈 EMA200 : {result['ema200']}\n\n"
        f"📉 RSI : {result['rsi']}\n"
        f"📊 MACD : {result['macd']['trend']}\n\n"
        f"🟢 Signal : {result['signal']}\n"
    )

    if result["entry"] is not None:
        message += (
            f"\n🎯 Entry : {result['entry']}\n"
            f"🛑 Stop Loss : {result['sl']}\n"
            f"🎯 TP1 : {result['tp1']}\n"
            f"🎯 TP2 : {result['tp2']}\n"
            f"\n📊 Confidence : {result['confidence']}%"
        )

    await update.message.reply_text(message)


async def signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await gold(update, context)


async def trend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    candles = get_candles()

    if candles is None:
        await update.message.reply_text("❌ Market data unavailable.")
        return

    result = get_signal(candles["close"])

    await update.message.reply_text(
        f"📈 Current Trend: {result['signal']}"
    )


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("gold", gold))
    app.add_handler(CommandHandler("signal", signal))
    app.add_handler(CommandHandler("trend", trend))

    print("Gold AI Bot Started...")

    app.run_polling()


if __name__ == "__main__":
    main()
