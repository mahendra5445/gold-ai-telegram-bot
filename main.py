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
        "/gold - Gold Analysis\n"
        "/signal - Trading Signal\n"
        "/trend - Market Trend"
    )


async def gold(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        url = f"https://api.twelvedata.com/price?symbol=XAU/USD&apikey={API_KEY}"

        response = requests.get(url, timeout=10)
        data = response.json()

        if "price" in data:
            price = data["price"]

            await update.message.reply_text(
                f"📊 LIVE GOLD PRICE\n\n"
                f"💰 XAUUSD: {price}\n\n"
                f"✅ Live data from Twelve Data"
            )
        else:
            await update.message.reply_text(f"API Error:\n{data}")

    except Exception as e:
        await update.message.reply_text(f"Error:\n{e}")
    await update.message.reply_text(
        "📊 GOLD ANALYSIS\n\n"
        "Trend: ⏳ Checking...\n"
        "Signal: ⏳ Waiting...\n"
        "Entry: --\n"
        "Stop Loss: --\n"
        "TP1: --\n"
        "TP2: --\n\n"
        "⚠️ AI Live Analysis will be added soon."
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
