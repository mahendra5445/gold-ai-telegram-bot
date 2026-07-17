import os
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")
API_KEY = os.getenv("TWELVE_DATA_API_KEY")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✅ Gold AI Bot Online!\n\n"
        "Commands:\n"
     async def gold(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        url = f"https://api.twelvedata.com/price?symbol=XAU/USD&apikey={API_KEY}"
        response = requests.get(url, timeout=10)
        data = response.json()

        if "price" in data:
            price = float(data["price"])

            if price > 4000:
                trend = "📈 BULLISH"
                signal = "🟢 BUY"
                entry = f"{price:.2f}"
                sl = f"{price - 8:.2f}"
                tp1 = f"{price + 10:.2f}"
                tp2 = f"{price + 20:.2f}"
            else:
                trend = "📉 BEARISH"
                signal = "🔴 SELL"
                entry = f"{price:.2f}"
                sl = f"{price + 8:.2f}"
                tp1 = f"{price - 10:.2f}"
                tp2 = f"{price - 20:.2f}"

            await update.message.reply_text(
                f"📊 GOLD ANALYSIS\n\n"
                f"💰 Price: {price:.2f}\n"
                f"Trend: {trend}\n"
                f"Signal: {signal}\n\n"
                f"🎯 Entry: {entry}\n"
                f"🛑 Stop Loss: {sl}\n"
                f"🎯 TP1: {tp1}\n"
                f"🎯 TP2: {tp2}"
            )
        else:
            await update.message.reply_text("❌ API Error")

    except Exception as e:
        await update.message.reply_text(f"❌ Error:\n{e}")   "/gold - Gold Analysis\n"
        "/signal - Trading Signal\n"
        "/trend - Market Trend"
    )



async def signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📡 Signal:\n"
        "No Trade\n\n"
        "Wait for confirmation."
    )


async def trend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📈 Trend:\n"
        "Analyzing Market..."
    )


def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("gold", gold))
    app.add_handler(CommandHandler("signal", signal))
    app.add_handler(CommandHandler("trend", trend))

    app.run_polling()


if __name__ == "__main__":
    main()
