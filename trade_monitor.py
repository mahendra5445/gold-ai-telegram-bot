"""
Trade Monitor Job

BADA FIX — bar-based detection (pehle: point-price sampling)
-----------------------------------------------------------
Purana monitor har cycle mein sirf EK live price dekhta tha. Agar do checks
ke beech price TP ya SL ko chhoo kar wapas aa gaya, bot ko pata hi nahi
chalta tha. Purane code ka apna comment isko "known limitation" maanta tha.

Iska asar sirf missed notification nahi tha -- ye STATS ko systematically
galat kar raha tha:
  - jeetne wale trades TP register kiye bina EXPIRED ho jaate the
  - expectancy asli se kam dikhti thi
  - expired ka ratio phoola hua aata tha
Yaani strategy ka koi bhi faisla galat data pe ho raha tha.

Ab har cycle mein pichhle check ke baad bani har 1-minute candle ka poora
HIGH/LOW check hota hai, ek-ek karke, time order mein. Do checks ke beech
ka koi bhi minute ab chhootta nahi.

Saath mein do aur choti par asli galtiyan theek ki gayi hain:
  1. EXIT PRICE: pehle SL/TP hit hone pe trade us LIVE price pe band hota
     tha jahan bot ne notice kiya -- jo level se kaafi aage ho sakta hai.
     Isse loss bada aur profit chhota record hota tha. Ab exit us actual
     level pe hota hai jo touch hua.
  2. TRAILING KA ORDER: pehle SL trail PEHLE hota tha, events baad mein.
     Ek hi candle ke andar iska matlab: candle ka high SL ko upar kheench
     deta tha, phir usi candle ka low us naye SL se takra kar jhoota
     stop-out bana deta tha -- jabki asal mein low pehle aaya ho sakta hai.
     Ab har bar pe pehle events check hote hain, trail baad mein.

Baaki purane fixes waise hi hain:
  - TP1/TP2 realized R record karte hain (partial exits), sirf flag nahi.
  - Trade expiry enforce hoti hai.
  - Har notification mein trade ka running R dikhta hai.
"""

import asyncio
import logging
import time
from datetime import datetime

from config import ASSETS, TRADE_EXPIRY_MINUTES
from data import get_latest_price, get_1m_bars
from shared_state import trade_lock
from trade_tracker import (
    get_open_trades, get_expired_trades, mark_tp_hit, close_trade,
    update_trailing_stop, persist_now, TIME_FMT,
)

logger = logging.getLogger(__name__)

# Ab 120s theek hai. Detection ki accuracy sampling rate pe depend nahi
# karti -- bars beech ka har minute cover kar dete hain. Purana code 60s pe
# bhagta tha kyunki wo har miss ko sampling se bharne ki koshish kar raha
# tha; wo kabhi kaam nahi kar sakta tha.
CHECK_INTERVAL = 120

# Kitne bars peechhe tak dekhein.
#
# Expiry window (+ margin) ke barabar rakha hai. Ek hi HTTP call se Yahoo 5
# din ka 1m data deta hai, to zyada bars maangna MUFT hai -- sirf ek list
# slice bada hota hai. Faayda: bot restart ho ya ghanton down rahe, wapas
# aate hi wo poora gap scan kar leta hai. Chhota lookback rakhne ka matlab
# hota: downtime ke dauraan lage TP/SL hamesha ke liye gum.
BAR_LOOKBACK = TRADE_EXPIRY_MINUTES + 60

SL_BUFFER_PCT = 0.0003


async def _notify_all(application, text: str) -> None:
    admins = application.bot_data.get("admins", [])
    for chat_id in admins:
        try:
            await application.bot.send_message(chat_id=chat_id, text=text)
        except Exception as e:
            logger.error(f"[MONITOR SEND ERROR] chat_id={chat_id}: {e}")


def _trade_start_ts(trade: dict) -> float:
    """
    Trade kab bana -- unix seconds mein.

    FALLBACK KYUN "ab" HAI, 0 NAHI: agar timestamp parse na ho paaye aur hum
    0 return kar dein, to har bar "trade ke baad ka" ban jaata hai -- monitor
    ENTRY SE PEHLE ka price action scan karke trade ko jhoothe SL/TP pe band
    kar deta. Parse fail hone pe kuch na dekhna hi mehfooz hai; agli candle se
    normal chalu ho jayega.
    """
    try:
        return datetime.strptime(trade["time"], TIME_FMT).timestamp()
    except Exception:
        logger.error(f"[MONITOR] #{trade.get('id')} bad time field "
                     f"{trade.get('time')!r} — bars skipped this cycle")
        return time.time()


def _compute_events(trade: dict, high: float, low: float) -> list[tuple[str, float]]:
    """
    Ek candle ke range (high/low) pe kaunse events lage.

    Return: [(event, exit_price), ...]
    event: "sl" | "be" | "tp1" | "tp2" | "tp3"

    AMBIGUITY RULE: agar ek hi candle mein SL aur TP dono touch hue, to hum
    maante hain ki SL PEHLE laga. 1-minute candle ke andar order ka pata
    lagana namumkin hai (uske liye tick data chahiye). Aisi soorat mein
    khud ko haraana hi imaandaar hai -- ulta maan lena stats ko phula dega
    aur wahi bharosa aapko live paise se bhugatna padega.
    """
    is_buy = trade["signal"] == "BUY"
    sl_level = trade["sl"]
    sl_buffer = abs(sl_level) * SL_BUFFER_PCT

    # BUY ka SL neeche hai -> candle ka LOW usko todta hai.
    # SELL ka SL upar hai -> candle ka HIGH usko todta hai.
    sl_hit = (
        (is_buy and low <= sl_level - sl_buffer) or
        (not is_buy and high >= sl_level + sl_buffer)
    )
    if sl_hit:
        return [("be" if trade["hit_tp1"] else "sl", sl_level)]

    events: list[tuple[str, float]] = []
    n = trade.get("n_targets") or sum(1 for k in ("tp1", "tp2", "tp3")
                                      if trade.get(k) is not None)
    for i in range(1, n + 1):
        lvl = trade.get(f"tp{i}")
        if lvl is None or trade.get(f"hit_tp{i}"):
            continue
        # BUY ka TP upar -> candle ka HIGH usko chhoota hai.
        if (is_buy and high >= lvl) or (not is_buy and low <= lvl):
            events.append((f"tp{i}", lvl))

    return events


async def _apply_events(trade: dict, events: list[tuple[str, float]],
                        decimals: int, notifications: list[str]) -> bool:
    """
    Events apply karo. Caller ko trade_lock hold karna hoga.
    Return: True agar trade band ho gaya.
    """
    head = f"#{trade['id']} | {trade['asset'].upper()} | {trade['signal']}"

    for level, exit_price in events:
        px = round(exit_price, decimals)

        if level in ("sl", "be"):
            status = "SL" if level == "sl" else "BE"
            if close_trade(trade, exit_price, status):
                r = trade["realized_r"]
                if level == "sl":
                    notifications.append(
                        f"🛑 SL HIT\n\n{head}\n"
                        f"Entry : {trade['entry']}\nSL    : {trade['sl']}\n"
                        f"Exit  : {px}\n\nResult: {r:+.2f}R ❌"
                    )
                else:
                    notifications.append(
                        f"⚪ CLOSED AT BREAKEVEN STOP\n\n{head}\n"
                        f"Entry : {trade['entry']}\nExit  : {px}\n\n"
                        f"TP1 pehle secure ho chuka tha.\nResult: {r:+.2f}R"
                    )
            return True

        n = int(level[-1])
        is_last = n >= (trade.get("n_targets") or 3)
        gained = mark_tp_hit(trade, n)

        if is_last or trade["remaining"] <= 1e-9:
            close_trade(trade, exit_price, "TP")
            notifications.append(
                f"{'🎯' * n} TP{n} HIT — TARGET COMPLETE\n\n{head}\n"
                f"Entry : {trade['entry']}\nTP{n}   : {trade[f'tp{n}']}\n"
                f"Exit  : {px}\n\nResult: {trade['realized_r']:+.2f}R 🏆"
            )
            return True

        extra = "\n✅ SL moved to Breakeven" if n == 1 else ""
        notifications.append(
            f"{'🎯' * n} TP{n} HIT\n\n{head}\n"
            f"Entry : {trade['entry']}\nTP{n}   : {trade[f'tp{n}']}\n"
            f"Exit  : {px}\n\n"
            f"Booked: +{gained:.2f}R  |  Total: {trade['realized_r']:+.2f}R\n"
            f"Remaining: {trade['remaining']:.0%}{extra}"
        )

    return False


async def _check_trade(application, trade: dict, bars: list[dict],
                       price: float | None) -> None:
    notifications: list[str] = []
    decimals = ASSETS.get(trade["asset"].lower(), {}).get("decimals", 2)
    head = f"#{trade['id']} | {trade['asset'].upper()} | {trade['signal']}"
    atr_value = trade.get("atr_at_entry")

    async with trade_lock:
        if trade["status"] != "OPEN":
            return

        # Sirf wo bars jo (a) trade banne ke baad ke hain aur (b) pichhle
        # check mein dekhe nahi gaye. max() dono shart ek saath lagata hai --
        # entry se pehle ka koi bar kabhi scan nahi hoga, chahe disk pe
        # last_bar_ts kharab ho ya purana.
        seen_ts = max(trade.get("last_bar_ts") or 0, _trade_start_ts(trade))
        fresh = [b for b in bars
                 if b.get("ts") is not None and b["ts"] > seen_ts
                 and b["high"] is not None and b["low"] is not None]

        closed = False
        for bar in fresh:            # time order mein, ek-ek bar
            # PEHLE events (us SL pe jo is candle ke shuru mein tha),
            # PHIR trail. Ulta karne se jhoote stop-out bante hain.
            events = _compute_events(trade, bar["high"], bar["low"])
            if events:
                closed = await _apply_events(trade, events, decimals, notifications)
                if closed:
                    break

            update_trailing_stop(trade, bar["close"], atr_value)
            trade["last_bar_ts"] = bar["ts"]

        if not closed and fresh:
            persist_now()

        # Abhi ban rahi candle bars mein nahi hoti (uska high/low final
        # nahi hai). Us gap ke liye live price ka ek check -- isse
        # notification turant milti hai, agli candle band hone ka
        # intezar nahi karna padta.
        if not closed and price is not None:
            events = _compute_events(trade, price, price)
            if events:
                closed = await _apply_events(trade, events, decimals, notifications)

            if not closed:
                trailed = update_trailing_stop(trade, price, atr_value)
                if trailed:
                    notifications.append(
                        f"🔒 SL TRAILED\n\n{head}\n"
                        f"Naya SL : {trailed}\nPrice : {round(price, decimals)}\n\n"
                        f"Profit lock ho gaya."
                    )

    for msg in notifications:
        await _notify_all(application, msg)


async def _expire_trades(application, prices: dict, bars: dict) -> None:
    """
    Purane open trades ko time pe band karo taaki asset unblock ho.

    FIX: pehle live price None hone pe trade `continue` kar ke chhod diya
    jaata tha. Agar us asset ka feed lagataar fail kare, trade KABHI expire
    nahi hota -- aur has_open_trade() us asset ko hamesha ke liye block kar
    deta. Ye theek wahi bimari hai jiske liye expiry banayi gayi thi.
    Ab aakhri bar ka close fallback price ki tarah use hota hai.
    """
    expired = get_expired_trades()
    if not expired:
        return

    notes = []
    async with trade_lock:
        for trade in expired:
            if trade["status"] != "OPEN":
                continue

            a = trade["asset"]
            price = prices.get(a)
            if price is None:
                asset_bars = bars.get(a) or []
                price = asset_bars[-1]["close"] if asset_bars else None
                if price is not None:
                    logger.warning(f"[MONITOR] #{trade['id']} expiring on last "
                                   f"bar close {price} — live price unavailable")
            if price is None:
                logger.error(f"[MONITOR] #{trade['id']} overdue but no price "
                             f"from any source — {a.upper()} stays blocked")
                continue

            if close_trade(trade, price, "EXPIRED"):
                dec = ASSETS.get(a.lower(), {}).get("decimals", 2)
                notes.append(
                    f"⏳ TRADE EXPIRED\n\n"
                    f"#{trade['id']} | {a.upper()} | {trade['signal']}\n"
                    f"Entry : {trade['entry']}\nPrice : {round(price, dec)}\n\n"
                    f"Time limit reached — closed.\nResult: {trade['realized_r']:+.2f}R"
                )

    for msg in notes:
        await _notify_all(application, msg)


async def _fetch_for_assets(assets: list[str]) -> tuple[dict, dict]:
    """Har asset ke liye bars + live price, parallel mein."""
    bar_res = await asyncio.gather(
        *(asyncio.to_thread(get_1m_bars, a, BAR_LOOKBACK) for a in assets),
        return_exceptions=True,
    )
    price_res = await asyncio.gather(
        *(asyncio.to_thread(get_latest_price, a) for a in assets),
        return_exceptions=True,
    )

    bars: dict[str, list] = {}
    prices: dict[str, float | None] = {}

    for a, res in zip(assets, bar_res):
        if isinstance(res, Exception):
            logger.error(f"[MONITOR] Bar fetch failed for {a.upper()}: {res}")
            bars[a] = []
        else:
            bars[a] = res

    for a, res in zip(assets, price_res):
        if isinstance(res, Exception):
            logger.error(f"[MONITOR] Price fetch failed for {a.upper()}: {res}")
            prices[a] = None
        else:
            prices[a] = res

    return bars, prices


async def trade_monitor_job(application) -> None:
    logger.info("[MONITOR] Trade monitor started (bar-based detection)")
    while True:
        try:
            open_trades = get_open_trades()

            if open_trades:
                asset_list = list({t["asset"] for t in open_trades})
                bars, prices = await _fetch_for_assets(asset_list)

                for trade in list(open_trades):
                    a = trade["asset"]
                    if not bars.get(a) and prices.get(a) is None:
                        logger.warning(f"[MONITOR] No data for {a.upper()} — skipping")
                        continue
                    await _check_trade(application, trade, bars.get(a, []), prices.get(a))

                await _expire_trades(application, prices, bars)

        except Exception as e:
            logger.error(f"[MONITOR ERROR] {e}")

        await asyncio.sleep(CHECK_INTERVAL)
