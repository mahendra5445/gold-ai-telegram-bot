import asyncio
import traceback

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from config import BOT_TOKEN
from data import get_candles
from strategy import get_signal
from formatter import format_signal
from auto_signal import auto_signal_job
from trade_tracker import get_stats, history_text


async def post_init(application):
    asyncio.create_task(auto_signal_job(application))


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    admins = context.application.bot_data.setdefault("admins", [])

    if chat_id not in admins:
        admins.append(chat_id)

    await update.message.reply_text(
        "🤖 GOLD AI SCALPER PRO v3.1\n\n"
        "✅ Bot Online\n"
        "📡 AI Signal Engine Active\n\n"
        "Commands:\n"
        "/gold\n"
        "/signal\n"
        "/trend\n"
        "/stats\n"
        "/history"
    )


def build_result(candles):
    return get_signal(
        candles["close"],
        candles["high"],
        candles["low"],
        candles["timeframes"],
        candles.get("volume"),
    )


async def gold(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:

        candles = get_candles()

        if candles is None:
            await update.message.reply_text(
                "❌ Market data unavailable."
            )
            return

        result = build_result(candles)

        message = format_signal(candles, result)

        await update.message.reply_text(message)

    except Exception as e:

        traceback.print_exc()

        await update.message.reply_text(
            f"❌ GOLD ERROR\n\n"
            f"{type(e).__name__}\n\n"
            f"{e}"
        )


async def signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await gold(update, context)async def trend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:

        candles = get_candles()

        if candles is None:
            await update.message.reply_text(
                "❌ Market data unavailable."
            )
            return

        result = build_result(candles)

        await update.message.reply_text(
            f"📊 1M Trend : {result['trend_1m']}\n"
            f"📊 5M Trend : {result['trend_5m']}\n"
            f"📊 15M Trend : {result['trend_15m']}\n\n"
            f"📈 Trend Strength : {result['trend_strength']}\n"
            f"📢 Signal : {result['signal']}\n"
            f"🤖 AI Score : {result['ai_score']}\n"
            f"🎖 Grade : {result['grade']}\n"
            f"🔥 Confidence : {result['confidence']}%\n"
            f"📍 Market : {result['market_status']}"
        )

    except Exception as e:

        traceback.print_exc()

        await update.message.reply_text(
            f"❌ TREND ERROR\n\n"
            f"{type(e).__name__}\n\n"
            f"{e}"
        )


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):

    s = get_stats()

    await update.message.reply_text(
        f"📊 TRADE STATISTICS\n\n"
        f"📈 Total Signals : {s['total']}\n"
        f"🟢 BUY Signals : {s['buy']}\n"
        f"🔴 SELL Signals : {s['sell']}\n"
        f"🎯 TP Hit : {s['tp']}\n"
        f"🛑 SL Hit : {s['sl']}"
    )


async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(history_text())


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
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("history", history))

    print("🚀 Gold AI Scalper Pro v3.1 Started...")

    app.run_polling()


if __name__ == "__main__":
    main()
