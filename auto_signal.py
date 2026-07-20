"""
Auto Signal Job

Fixes applied:
  #1  Duplicate save bug    — save_trade() now called AFTER all duplicate /
                              cooldown / open-trade checks pass.
  #2  Open trade lock       — has_open_trade() prevents stacking trades on the
                              same asset.
  #7  Race condition        — trade_lock (asyncio.Lock) serialises the critical
                              check-and-save section; I/O (API fetch, Telegram
                              send) happens outside the lock.
 #10  Cooldown system       — per-asset time-based cooldown (SIGNAL_COOLDOWN_SEC)
                              replaces brittle message-string comparison.
 #14  Persistent admin list — admins restored from disk on bot startup (in
                              main.py); this module just reads them from bot_data.
"""

import asyncio
import logging
import time

from data import get_candles
from formatter import format_signal
from news import is_high_impact_news
from shared_state import trade_lock
from strategy import get_signal
from trade_tracker import has_open_trade, save_trade

logger = logging.getLogger(__name__)

# ── per-asset cooldown ────────────────────────────────────────────────────
# After a signal fires we ignore further signals for this asset until
# SIGNAL_COOLDOWN_SEC seconds have passed.  This is independent of the
# 30-min polling cycle and survives message-string changes (price drift).
SIGNAL_COOLDOWN_SEC: int = 25 * 60   # 25 minutes

_last_signal_time: dict[str, float] = {}   # asset -> unix timestamp of last sent signal
_last_signal_msg:  dict[str, str | None] = {"gold": None, "btc": None}


def _in_cooldown(asset: str) -> bool:
    last = _last_signal_time.get(asset, 0.0)
    elapsed   = time.monotonic() - last
    remaining = SIGNAL_COOLDOWN_SEC - elapsed
    if remaining > 0:
        logger.info(
            f"[COOLDOWN] {asset.upper()} — "
            f"{int(remaining // 60)}m {int(remaining % 60)}s remaining"
        )
        return True
    return False


# ── per-asset check ───────────────────────────────────────────────────────

async def _check_asset(application, asset: str) -> None:

    # ── 1. Fetch data (outside lock — network I/O can be slow) ───────────
    candles = get_candles(asset)
    result  = get_signal(
        candles["close"],
        candles["high"],
        candles["low"],
        candles["timeframes"],
        candles.get("volume"),
        candles.get("open"),
    )

    if result["signal"] == "NO TRADE":
        logger.info(f"[AUTO] {asset.upper()} → No Trade")
        return

    # Build message outside lock (pure CPU, no I/O)
    message = format_signal(candles, result)

    # ── 2. Critical section (hold lock only for state checks + write) ─────
    async with trade_lock:

        # Cooldown check
        if _in_cooldown(asset):
            return

        # Exact duplicate message check (same price, same signal)
        if message == _last_signal_msg.get(asset):
            logger.info(f"[AUTO] {asset.upper()} duplicate signal skipped")
            return

        # One open trade per asset at a time
        if has_open_trade(asset):
            logger.info(
                f"[AUTO] {asset.upper()} already has an open trade — "
                f"new signal skipped"
            )
            return

        # All checks passed → persist trade and update cooldown atomically
        save_trade(result, asset=asset)
        _last_signal_msg[asset]  = message
        _last_signal_time[asset] = time.monotonic()

    # ── 3. Send Telegram messages (outside lock — I/O) ────────────────────
    admins = application.bot_data.get("admins", [])
    if not admins:
        logger.warning("[AUTO] No registered users — send /start first.")
        return

    sent = 0
    for chat_id in admins:
        try:
            await application.bot.send_message(chat_id=chat_id, text=message)
            sent += 1
        except Exception as e:
            logger.error(f"[SEND ERROR] chat_id={chat_id}: {e}")

    logger.info(f"[AUTO] {asset.upper()} signal sent to {sent}/{len(admins)} users")


# ── main job loop ─────────────────────────────────────────────────────────

async def auto_signal_job(application) -> None:
    logger.info("[AUTO] Signal job started")
    while True:
        # News filter
        try:
            if is_high_impact_news():
                logger.info("[NEWS FILTER] High-impact USD news — signals paused 5 min")
                await asyncio.sleep(300)
                continue
        except Exception as e:
            logger.error(f"[AUTO] News check failed: {e}")

        # Check each asset independently so one failure can't block the other
        for asset in ("gold", "btc"):
            try:
                await _check_asset(application, asset)
            except Exception as e:
                logger.error(f"[AUTO] {asset.upper()} error: {e}")

        await asyncio.sleep(1800)   # 30-minute cycle
