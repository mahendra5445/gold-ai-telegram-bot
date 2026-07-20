"""
Bot entry point.

Fixes applied:
 #13  Graceful restart        — Application.post_shutdown saves admins + logs exit.
 #14  Persistent admin list   — admins loaded from disk at startup; saved on every
                                /start and on shutdown.
 #17  Proper logging          — setup_logging() configures rotating file + console
                                before anything else runs.
"""

import asyncio
import logging
import traceback

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from auto_signal import auto_signal_job
from config import BOT_TOKEN
from data import get_candles, get_latest_price
from formatter import format_signal
from logger_setup import setup_logging
from persistence import load_admins, save_admins
from risk import calculate_trade
from strategy import get_signal
from trade_monitor import trade_monitor_job
from trade_tracker import get_stats, history_text

# ── logging must be configured before any module uses it ─────────────────
setup_logging()
logger = logging.getLogger(__name__)


# ── lifecycle callbacks ───────────────────────────────────────────────────

async def post_init(application: Application) -> None:
    """Runs after the bot is fully initialised but before polling starts."""

    # Restore persisted admin list so users don't need to /start again
    saved_admins = load_admins()
    if saved_admins:
        application.bot_data["admins"] = saved_admins
        logger.info(f"[INIT] Restored {len(saved_admins)} admins from disk")
    else:
        application.bot_data.setdefault("admins", [])

    # Launch background jobs as independent tasks.
    # BUG FIX: task references save karna zaroori hai — asyncio sirf weak
    # reference rakhta hai, aur bina strong reference ke garbage collector
    # kabhi bhi task ko silently kill kar sakta hai (Python docs ka official
    # warning hai). Isse auto-signal/monitor kuch ghanton baad chupchaap
    # band ho sakta tha bina kisi error ke.
    application.bot_data["_bg_tasks"] = [
        asyncio.create_task(auto_signal_job(application), name="auto_signal"),
        asyncio.create_task(trade_monitor_job(application), name="trade_monitor"),
    ]
    logger.info("[INIT] Background tasks started")


async def post_shutdown(application: Application) -> None:
    """Runs after polling has stopped — flush state before the process exits."""
    # Cancel background loops cleanly so they don't error mid-shutdown
    for task in application.bot_data.get("_bg_tasks", []):
        task.cancel()

    admins = application.bot_data.get("admins", [])
    save_admins(admins)
    logger.info(f"[SHUTDOWN] Saved {len(admins)} admins. Goodbye.")


# ── command helpers ───────────────────────────────────────────────────────

def _build_result(candles: dict, asset: str = "gold") -> dict:
    result = get_signal(
        candles["close"],
        candles["high"],
        candles["low"],
        candles["timeframes"],
        candles.get("volume"),
        candles.get("open"),
    )

    # BUG FIX (MT5 price mismatch): manual /gold aur /btc commands mein
    # price last CLOSED 5-minute candle ka close tha — jo message aane
    # tak 5+ minute purana ho sakta hai, isliye MT5 ke live price se
    # alag dikhta tha. Auto-signal mein yeh fix pehle se tha; ab manual
    # commands mein bhi live quote fetch karke price + entry/SL/TP
    # levels refresh karte hain. Live fetch fail ho to candle-based
    # levels hi rehte hain (message block nahi hota).
    live_price = get_latest_price(asset)
    if live_price is not None:
        candles["price"] = live_price
        if result["signal"] in ("BUY", "SELL"):
            result.update(
                calculate_trade(result["signal"], live_price, result.get("atr_value", 0))
            )

    return result


# ── command handlers ──────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    admins  = context.application.bot_data.setdefault("admins", [])

    if chat_id not in admins:
        admins.append(chat_id)
        save_admins(admins)   # persist immediately
        logger.info(f"[ADMIN] Registered new user {chat_id} ({len(admins)} total)")

    await update.message.reply_text(
        "🤖 GOLD AI SCALPER PRO V5.0\n\n"
        "✅ Bot Online\n"
        "📡 AI Signal Engine Active\n\n"
        "Commands:\n"
        "/gold    — Manual gold signal\n"
        "/btc     — Manual BTC signal\n"
        "/signal  — Same as /gold\n"
        "/trend   — Trend summary\n"
        "/stats   — Trade statistics\n"
        "/history — Last 10 trades"
    )


async def gold(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        candles = get_candles()
        result  = _build_result(candles)
        await update.message.reply_text(format_signal(candles, result))
    except Exception as e:
        traceback.print_exc()
        logger.error(f"[CMD /gold] {e}")
        await update.message.reply_text(f"❌ ERROR\n\n{type(e).__name__}: {e}")


async def btc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        candles = get_candles("btc")
        result  = _build_result(candles, "btc")
        await update.message.reply_text(format_signal(candles, result))
    except Exception as e:
        traceback.print_exc()
        logger.error(f"[CMD /btc] {e}")
        await update.message.reply_text(f"❌ ERROR\n\n{type(e).__name__}: {e}")


async def signal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await gold(update, context)


async def trend(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        candles = get_candles()
        result  = _build_result(candles)
        await update.message.reply_text(
            f"📊 1M Trend      : {result['trend_1m']}\n"
            f"📊 5M Trend      : {result['trend_5m']}\n"
            f"📊 15M Trend     : {result['trend_15m']}\n\n"
            f"📈 Trend Strength: {result['trend_strength']}\n"
            f"📢 Signal        : {result['signal']}\n"
            f"🤖 AI Score      : {result['ai_score']}\n"
            f"🎖 Grade         : {result['grade']}\n"
            f"🔥 Confidence    : {result['confidence']}%\n"
            f"📍 Market        : {result['market_status']}"
        )
    except Exception as e:
        traceback.print_exc()
        logger.error(f"[CMD /trend] {e}")
        await update.message.reply_text(f"❌ ERROR\n\n{type(e).__name__}: {e}")


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # BUG FIX: /stats aur /history mein try/except nahi tha jabki baaki sab
    # handlers mein tha — koi bhi exception yahan user ko bina reply ke
    # chhod deta tha.
    try:
        await _stats_impl(update)
    except Exception as e:
        logger.error(f"[CMD /stats] {e}")
        await update.message.reply_text(f"❌ ERROR\n\n{type(e).__name__}: {e}")


async def _stats_impl(update: Update) -> None:
    s = get_stats()
    await update.message.reply_text(
        f"📊 TRADE STATISTICS\n\n"
        f"📈 Total Signals : {s['total']}\n"
        f"🟢 BUY Signals   : {s['buy']}\n"
        f"🔴 SELL Signals  : {s['sell']}\n"
        f"🎯 TP Hit        : {s['tp']}\n"
        f"⚪ Breakeven     : {s['be']}\n"
        f"🛑 SL Hit        : {s['sl']}\n"
        f"🏆 Win Rate      : {s['win_rate']}%"
    )


async def history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        await update.message.reply_text(history_text())
    except Exception as e:
        logger.error(f"[CMD /history] {e}")
        await update.message.reply_text(f"❌ ERROR\n\n{type(e).__name__}: {e}")


# ── entry point ───────────────────────────────────────────────────────────

def main() -> None:
    if not BOT_TOKEN:
        logger.critical("BOT_TOKEN environment variable is not set. Exiting.")
        return

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    app.add_handler(CommandHandler("start",   start))
    app.add_handler(CommandHandler("gold",    gold))
    app.add_handler(CommandHandler("btc",     btc))
    app.add_handler(CommandHandler("signal",  signal))
    app.add_handler(CommandHandler("trend",   trend))
    app.add_handler(CommandHandler("stats",   stats))
    app.add_handler(CommandHandler("history", history))

    logger.info("🚀 Gold AI Scalper Pro V5.0 starting…")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
