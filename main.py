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
from config import ASSETS, BOT_TOKEN
from daily_summary import daily_summary_job
from data import get_candles, get_latest_price
from formatter import format_signal
from logger_setup import setup_logging
from persistence import load_admins, save_admins
from risk import calculate_trade
from strategy import get_signal
from trade_monitor import trade_monitor_job
from trade_tracker import get_stats, history_text
from watchdog import watchdog_job

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
        asyncio.create_task(watchdog_job(application), name="watchdog"),
        asyncio.create_task(daily_summary_job(application), name="daily_summary"),
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

async def _build_result(candles: dict, asset: str = "gold") -> dict:
    cfg = ASSETS[asset.lower()]
    decimals = cfg["decimals"]
    spread = cfg.get("spread", 0.0)
    result = get_signal(
        candles["close"],
        candles["high"],
        candles["low"],
        candles["timeframes"],
        candles.get("volume"),
        candles.get("open"),
        decimals=decimals,
        spread=spread,
    )

    # BUG FIX (MT5 price mismatch): manual /gold aur /btc commands mein
    # price last CLOSED 5-minute candle ka close tha — jo message aane
    # tak 5+ minute purana ho sakta hai, isliye MT5 ke live price se
    # alag dikhta tha. Auto-signal mein yeh fix pehle se tha; ab manual
    # commands mein bhi live quote fetch karke price + entry/SL/TP
    # levels refresh karte hain. Live fetch fail ho to candle-based
    # levels hi rehte hain (message block nahi hota).
    #
    # BUG FIX (event-loop block): get_latest_price() is a blocking
    # requests.get() call — running it directly here (a sync function
    # called from an async handler) blocked the whole bot on every single
    # /gold, /btc, /trend etc. command. asyncio.to_thread() moves it off
    # the event loop.
    live_price = await asyncio.to_thread(get_latest_price, asset)
    if live_price is not None:
        candles["price"] = live_price
        if result["signal"] in ("BUY", "SELL"):
            result.update(
                calculate_trade(
                    result["signal"], live_price, result.get("atr_value", 0),
                    decimals=decimals, session_active=result.get("session_active", True),
                    spread=spread,
                )
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

    asset_lines = "\n".join(
        f"/{a}    — Manual {cfg['label']} signal" for a, cfg in ASSETS.items()
    )

    await update.message.reply_text(
        "🤖 AI SCALPER PRO V5.5\n\n"
        "✅ Bot Online\n"
        "📡 AI Signal Engine Active\n\n"
        "Commands:\n"
        f"{asset_lines}\n"
        "/signal  — Same as /gold\n"
        "/trend   — Trend summary (gold)\n"
        "/stats   — Trade statistics (add asset name for one asset, e.g. /stats eurusd)\n"
        "/history — Last 10 trades (add asset name to filter, e.g. /history btc)"
    )


def _make_asset_handler(asset: str):
    """Builds a /<asset> command handler — same logic as the old hardcoded
    gold()/btc() functions, just parameterised so every asset in
    config.ASSETS gets a command without duplicating this block."""
    cfg      = ASSETS[asset]
    decimals = cfg["decimals"]
    label    = cfg["label"]

    async def _handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            candles = await asyncio.to_thread(get_candles, asset)
            result  = await _build_result(candles, asset)
            await update.message.reply_text(
                format_signal(candles, result, decimals=decimals, label=label)
            )
        except Exception as e:
            traceback.print_exc()
            logger.error(f"[CMD /{asset}] {e}")
            await update.message.reply_text(f"❌ ERROR\n\n{type(e).__name__}: {e}")

    return _handler


# One handler per configured asset (dynamically created from ASSETS config)
_asset_handlers = {a: _make_asset_handler(a) for a in ASSETS}
gold = _asset_handlers["gold"]
# Dynamically create handlers for all configured assets (no hardcoded asset names)
eurusd = _asset_handlers.get("eurusd")
gbpusd = _asset_handlers.get("gbpusd")
usdjpy = _asset_handlers.get("usdjpy")


async def signal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await gold(update, context)


async def trend(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        candles = await asyncio.to_thread(get_candles)
        result  = await _build_result(candles)
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
        await _stats_impl(update, context)
    except Exception as e:
        logger.error(f"[CMD /stats] {e}")
        await update.message.reply_text(f"❌ ERROR\n\n{type(e).__name__}: {e}")



def _stats_block(title: str, s: dict) -> str:
    """
    NAYA: expectancy ab sabse upar hai, win rate ke neeche.
    Expectancy = avg R per trade. YEHI batata hai strategy paisa banati hai
    ya nahi. Win rate 80% ho sakta hai aur expectancy phir bhi negative --
    agar jeetein chhoti aur haarein badi hon.
    """
    verdict = ("🟢 profitable is sample pe" if s["expectancy"] > 0.05 else
               "🟡 flat — noise bhi ho sakta hai" if s["expectancy"] > 0 else
               "🔴 paisa kho rahe hain")
    return (
        f"📊 {title}\n\n"
        f"📈 Total Signals : {s['total']}  (open: {s['open']})\n"
        f"🟢 BUY / 🔴 SELL : {s['buy']} / {s['sell']}\n"
        f"✅ Closed        : {s['closed']}\n\n"
        f"💰 EXPECTANCY    : {s['expectancy']:+.4f} R/trade  {verdict}\n"
        f"📊 Total         : {s['total_r']:+.2f} R\n"
        f"📉 Max Drawdown  : {s['max_dd_r']:.2f} R\n\n"
        f"🏆 Win Rate      : {s['win_rate']}%\n"
        f"   Avg Win       : {s['avg_win_r']:+.2f} R\n"
        f"   Avg Loss      : {s['avg_loss_r']:+.2f} R\n\n"
        f"🎯 Reached TP1   : {s['tp1_reached']}\n"
        f"🎯 Reached TP3   : {s['tp3_reached']}\n"
        f"🛑 SL Hit        : {s['sl']}\n"
        f"⚪ Breakeven     : {s['be']}\n"
        f"⏳ Expired       : {s['expired']}"
    )


async def _stats_impl(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # /stats <asset> -> just that asset. /stats -> combined + per-asset table.
    arg = context.args[0].lower() if context.args else None

    if arg:
        if arg not in ASSETS:
            await update.message.reply_text(
                f"❌ Unknown asset '{arg}'. Valid: {', '.join(ASSETS)}"
            )
            return
        s = get_stats(asset=arg)
        await update.message.reply_text(_stats_block(f"TRADE STATISTICS — {ASSETS[arg]['label']}", s))
        return

    s = get_stats()
    breakdown_lines = []
    for a, cfg in ASSETS.items():
        a_stats = get_stats(asset=a)
        if a_stats["total"] == 0:
            continue
        breakdown_lines.append(
            f"  {cfg['label']:<10} {a_stats['total']:>3} sig | "
            f"{a_stats['expectancy']:+.3f}R/trade | {a_stats['win_rate']}% win"
        )
    breakdown = "\n".join(breakdown_lines) if breakdown_lines else "  (no signals yet)"

    await update.message.reply_text(
        _stats_block("TRADE STATISTICS (All Assets)", s)
        + f"\n\nPer-Asset:\n{breakdown}\n\n"
        f"Tip: /stats <asset> for one asset's detail (e.g. /stats eurusd)"
    )


async def history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        arg = context.args[0].lower() if context.args else None
        if arg and arg not in ASSETS:
            await update.message.reply_text(
                f"❌ Unknown asset '{arg}'. Valid: {', '.join(ASSETS)}"
            )
            return
        await update.message.reply_text(history_text(asset=arg))
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
    for asset_name, handler_fn in _asset_handlers.items():
        app.add_handler(CommandHandler(asset_name, handler_fn))
    app.add_handler(CommandHandler("signal",  signal))
    app.add_handler(CommandHandler("trend",   trend))
    app.add_handler(CommandHandler("stats",   stats))
    app.add_handler(CommandHandler("history", history))

    logger.info("🚀 Gold AI Scalper Pro V5.5 starting…")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
