"""
Auto Signal Job

Naye fixes:
  - Broker spread strategy/risk ko pass hota hai (pehle kahin count hi nahi hota tha).
  - Daily circuit breaker: per-asset max trades aur max daily loss in R.
  - Duplicate-message check hata diya (wo dead code tha -- poore formatted
    message ko compare karta tha jismein live price hota hai, kabhi match
    nahi karta tha). Cooldown + open-trade lock kaafi hain.
"""

import asyncio
import logging
import time

from config import ASSETS, ASSET_LIST
from data import get_candles, get_latest_price
from formatter import format_signal
from news import is_high_impact_news
from risk import calculate_trade
from shared_state import trade_lock, heartbeat
from strategy import get_signal
from trade_tracker import has_open_trade, save_trade, can_trade_today

logger = logging.getLogger(__name__)

SIGNAL_COOLDOWN_SEC: int = 15 * 60

_last_signal_time: dict[str, float] = {}


def _in_cooldown(asset: str) -> bool:
    last = _last_signal_time.get(asset)
    if last is None:
        return False
    remaining = SIGNAL_COOLDOWN_SEC - (time.monotonic() - last)
    if remaining > 0:
        logger.info(f"[COOLDOWN] {asset.upper()} — "
                    f"{int(remaining // 60)}m {int(remaining % 60)}s remaining")
        return True
    return False


async def _check_asset(application, asset: str) -> None:
    cfg = ASSETS[asset.lower()]
    decimals = cfg["decimals"]
    label = cfg["label"]
    spread = cfg.get("spread", 0.0)

    candles = await asyncio.to_thread(get_candles, asset)
    result = get_signal(
        candles["close"], candles["high"], candles["low"],
        candles["timeframes"], candles.get("volume"), candles.get("open"),
        decimals=decimals, spread=spread,
    )

    if result["signal"] == "NO TRADE":
        logger.info(f"[AUTO] {asset.upper()} → No Trade")
        return

    live_price = await asyncio.to_thread(get_latest_price, asset)
    if live_price is not None:
        result.update(calculate_trade(
            result["signal"], live_price, result.get("atr_value", 0),
            decimals=decimals, session_active=result.get("session_active", True),
            spread=spread,
        ))
        candles["price"] = live_price

    message = format_signal(candles, result, decimals=decimals, label=label)

    admins = application.bot_data.get("admins", [])
    if not admins:
        logger.warning("[AUTO] No registered users — send /start first.")
        return

    async with trade_lock:
        if _in_cooldown(asset):
            return

        if has_open_trade(asset):
            logger.info(f"[AUTO] {asset.upper()} already has an open trade — skipped")
            return

        # NAYA: circuit breaker
        allowed, why = can_trade_today(asset)
        if not allowed:
            logger.info(f"[AUTO] {asset.upper()} blocked — {why}")
            return

        save_trade(result, asset=asset)
        _last_signal_time[asset] = time.monotonic()

    sent = 0
    for chat_id in admins:
        try:
            await application.bot.send_message(chat_id=chat_id, text=message)
            sent += 1
        except Exception as e:
            logger.error(f"[SEND ERROR] chat_id={chat_id}: {e}")

    logger.info(f"[AUTO] {asset.upper()} signal sent to {sent}/{len(admins)} users")


async def auto_signal_job(application) -> None:
    logger.info("[AUTO] Signal job started")
    heartbeat["last_cycle"] = time.time()
    while True:
        try:
            if await asyncio.to_thread(is_high_impact_news):
                logger.info("[NEWS FILTER] High-impact USD news — signals paused 5 min")
                heartbeat["last_cycle"] = time.time()
                await asyncio.sleep(300)
                continue
        except Exception as e:
            logger.error(f"[AUTO] News check failed: {e}")

        for asset in ASSET_LIST:
            try:
                await _check_asset(application, asset)
            except Exception as e:
                logger.error(f"[AUTO] {asset.upper()} error: {e}")

        heartbeat["last_cycle"] = time.time()
        await asyncio.sleep(900)
