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
        "/gold - Live Gold Price\n"
        "/signal - Trading Signal\n"
        "/trend - Market Trend"
    )


async def gold(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        url = f"https://api.twelvedata.com/price?symbol=XAU/USD&apikey={API_KEY}"
        response = requests.get(url, timeout=10)
        data = response.json()

        if "price" in data:
            price = float(data["price"])
            trend = "📈 BULLISH" if price >= 4000 else "📉 BEARISH"

            await update.message.reply_text(
                f"📊 GOLD ANALYSIS\n\n"
                f"💰 Price: {price:.2f}\n"
                f"📈 Trend: {trend}\n\n"
                "EMA / RSI analysis will be added next."
            )
        else:
            await update.message.reply_text(f"API Error:\n{data}")

    except Exception as e:
        await update.message.reply_text(f"Error:\n{e}")


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
