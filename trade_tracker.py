"""
Trade Tracker — single source of truth for all trade state.

BADA FIX (#5 in report): win rate mathematically toota hua tha.
Pehle trade sirf TP3 (6R) pe "TP" mark hota tha. TP1 aur TP2 hits kisi win
column mein jaate hi nahi the -- ek trade jo TP1 (+2.5R, asli profit) hit
kare aur wapas aa jaaye wo "BE" record hota tha. Isiliye code comments mein
likha tha "win rate was ~0%": wo strategy ka fail hona nahi tha, accounting
ka bug tha.

Ab har trade ka REALIZED R track hota hai, partial exits ke saath. Aur
stats ka main number win rate nahi -- EXPECTANCY (avg R per trade) hai.
Win rate 80% ho sakta hai aur expectancy phir bhi negative.
"""

import logging
from datetime import datetime, timedelta

from config import SCALE_OUT, TP_MULTIPLES, TRADE_EXPIRY_MINUTES, \
    MAX_TRADES_PER_DAY, MAX_DAILY_LOSS_R
from persistence import load_trades_from_disk, save_trades_to_disk

logger = logging.getLogger(__name__)

MAX_TRADE_HISTORY = 500
TIME_FMT = "%Y-%m-%d %H:%M:%S"

_trades: list[dict]
_next_id: int
_trades, _next_id = load_trades_from_disk()


def _persist() -> None:
    save_trades_to_disk(_trades, _next_id)


def _trim_history() -> None:
    global _trades
    if len(_trades) <= MAX_TRADE_HISTORY:
        return
    open_trades = [t for t in _trades if t["status"] == "OPEN"]
    closed_trades = [t for t in _trades if t["status"] != "OPEN"]
    keep_closed = max(0, MAX_TRADE_HISTORY - len(open_trades))
    trimmed = len(closed_trades) - keep_closed
    closed_trades = closed_trades[-keep_closed:] if keep_closed > 0 else []
    _trades = closed_trades + open_trades
    _trades.sort(key=lambda t: t.get("id", 0))
    if trimmed > 0:
        logger.info(f"[TRACKER] History trimmed: removed {trimmed} old closed trades")


def has_open_trade(asset: str) -> bool:
    a = asset.lower()
    return any(t["status"] == "OPEN" and t["asset"].lower() == a for t in _trades)


# ── circuit breaker ───────────────────────────────────────────────────────

def can_trade_today(asset: str) -> tuple[bool, str]:
    """
    NAYA: pehle koi daily limit nahi thi -- ek kharab din bina rukawat chalta
    rehta tha. Ab per-asset daily trade count aur daily realized R dono check
    hote hain.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    a = asset.lower()
    todays = [t for t in _trades if t["asset"].lower() == a and t["time"] >= today]

    if len(todays) >= MAX_TRADES_PER_DAY:
        return False, f"daily limit ({MAX_TRADES_PER_DAY} trades) reached"

    day_r = sum(t.get("realized_r", 0.0) for t in todays if t["status"] != "OPEN")
    if day_r <= MAX_DAILY_LOSS_R:
        return False, f"daily loss limit hit ({day_r:.2f}R)"

    return True, ""


def save_trade(result: dict, asset: str = "gold") -> dict | None:
    """Caller MUST hold shared_state.trade_lock."""
    global _next_id

    signal = result.get("signal")
    if signal not in ("BUY", "SELL"):
        return None

    entry = float(result["entry"])
    sl = float(result["sl"])
    risk = result.get("risk_per_unit") or abs(entry - sl)

    trade = {
        "id": _next_id,
        "asset": asset.lower(),
        "signal": signal,
        "entry": round(entry, 5),
        "sl": round(sl, 5),
        "original_sl": round(sl, 5),
        "targets": [round(float(x), 5) for x in result.get("targets", [])],
        "tp1": round(float(result["tp1"]), 5) if result.get("tp1") is not None else None,
        "tp2": round(float(result["tp2"]), 5) if result.get("tp2") is not None else None,
        "tp3": round(float(result["tp3"]), 5) if result.get("tp3") is not None else None,
        "risk_per_unit": round(risk, 5),
        "hit_tp1": False, "hit_tp2": False, "hit_tp3": False,
        "n_targets": len(result.get("targets", [])),
        # NAYA: realized R aur bacha hua position size
        "realized_r": 0.0,
        "remaining": 1.0,
        "status": "OPEN",
        "time": datetime.now().strftime(TIME_FMT),
        "expires_at": (datetime.now() + timedelta(minutes=TRADE_EXPIRY_MINUTES)
                       ).strftime(TIME_FMT),
    }

    _next_id += 1
    _trades.append(trade)
    _trim_history()
    _persist()
    logger.info(f"[TRADE] Saved #{trade['id']} {asset.upper()} {signal} "
                f"entry={trade['entry']} sl={trade['sl']} risk={trade['risk_per_unit']}")
    return trade


def get_open_trades() -> list[dict]:
    return [t for t in _trades if t["status"] == "OPEN"]


def get_expired_trades() -> list[dict]:
    """
    NAYA: pehle koi expiry thi hi nahi. SIGNAL_VALID_MINUTES sirf Telegram
    message mein print hota tha. Trade OPEN rehta tha jab tak TP3 ya SL na
    lage -- aur has_open_trade() us asset ko tab tak block kar deta tha.
    Gold hafton tak block reh sakta tha.
    """
    now = datetime.now().strftime(TIME_FMT)
    return [t for t in _trades
            if t["status"] == "OPEN" and t.get("expires_at", "9999") <= now]


def _r_at(trade: dict, price: float) -> float:
    """Ek price pe bacha hua position kitne R pe hai."""
    risk = trade.get("risk_per_unit") or abs(trade["entry"] - trade["original_sl"])
    if risk <= 0:
        return 0.0
    diff = (price - trade["entry"]) if trade["signal"] == "BUY" else (trade["entry"] - price)
    return diff / risk


def mark_tp_hit(trade: dict, level: int) -> float:
    """
    NAYA: TP1/TP2/TP3 hit hone pe position ka hissa band karta hai aur
    realized R mein add karta hai. Pehle TP1/TP2 sirf boolean flag set karte
    the -- unka profit kahin record hi nahi hota tha.
    Returns: is exit se mila R.
    """
    idx = level - 1
    portion = SCALE_OUT[idx]
    gained = TP_MULTIPLES[idx] * portion

    trade[f"hit_tp{level}"] = True
    trade["realized_r"] = round(trade.get("realized_r", 0.0) + gained, 4)
    trade["remaining"] = round(max(0.0, trade.get("remaining", 1.0) - portion), 4)

    if level == 1:
        trade["sl"] = trade["entry"]        # breakeven

    _persist()
    logger.info(f"[TRADE] #{trade['id']} TP{level} hit — +{gained:.2f}R "
                f"(total {trade['realized_r']:.2f}R, {trade['remaining']:.0%} left)")
    return gained


def close_trade(trade: dict, price: float, status: str) -> bool:
    """
    Bache hue position ko current price pe band karo aur final R likho.
    status: SL / BE / TP / EXPIRED
    Caller MUST hold trade_lock.
    """
    if trade["status"] != "OPEN":
        logger.warning(f"[TRADE] #{trade['id']} already '{trade['status']}'")
        return False

    remaining = trade.get("remaining", 1.0)
    if remaining > 0:
        trade["realized_r"] = round(
            trade.get("realized_r", 0.0) + _r_at(trade, price) * remaining, 4)
        trade["remaining"] = 0.0

    trade["status"] = status
    trade["exit_price"] = round(price, 5)
    trade["closed_time"] = datetime.now().strftime(TIME_FMT)
    _persist()
    logger.info(f"[TRADE] #{trade['id']} closed {status} @ {price} "
                f"→ {trade['realized_r']:+.2f}R")
    return True


def update_trade(trade_id: int, status: str) -> bool:
    """Backward-compatible wrapper."""
    for trade in _trades:
        if trade["id"] == trade_id:
            return close_trade(trade, trade.get("exit_price", trade["entry"]), status)
    logger.warning(f"[TRADE] #{trade_id} not found for update → {status}")
    return False


def find_trade(trade_id: int) -> dict | None:
    return next((t for t in _trades if t["id"] == trade_id), None)


def get_stats(asset: str | None = None, since: str | None = None) -> dict:
    """
    FIX: pehle win_rate = tp/(tp+sl+be), aur "tp" sirf TP3 pe set hota tha.
    Ab sab kuch realized R se derive hota hai.

    EXPECTANCY hi wo number hai jo batata hai strategy paisa banati hai ya
    nahi. Win rate akela kuch nahi batata.
    """
    trades = _trades
    if asset:
        a = asset.lower()
        trades = [t for t in trades if t["asset"].lower() == a]
    if since:
        trades = [t for t in trades if t["time"] >= since]

    closed = [t for t in trades if t["status"] != "OPEN"]
    buy = sum(1 for t in trades if t["signal"] == "BUY")
    sell = sum(1 for t in trades if t["signal"] == "SELL")

    wins = [t for t in closed if t.get("realized_r", 0) > 0]
    losses = [t for t in closed if t.get("realized_r", 0) <= 0]
    total_r = sum(t.get("realized_r", 0.0) for t in closed)
    n = len(closed)

    # Max drawdown in R
    peak = cum = mdd = 0.0
    for t in sorted(closed, key=lambda x: x.get("id", 0)):
        cum += t.get("realized_r", 0.0)
        peak = max(peak, cum)
        mdd = min(mdd, cum - peak)

    return {
        "total": buy + sell,
        "buy": buy,
        "sell": sell,
        "open": sum(1 for t in trades if t["status"] == "OPEN"),
        "closed": n,
        "tp1_reached": sum(1 for t in closed if t.get("hit_tp1")),
        "tp3_reached": sum(1 for t in closed if t.get("hit_tp3")),
        "sl": sum(1 for t in closed if t["status"] == "SL"),
        "be": sum(1 for t in closed if t["status"] == "BE"),
        "expired": sum(1 for t in closed if t["status"] == "EXPIRED"),
        "win_rate": round(len(wins) / n * 100, 2) if n else 0.0,
        "total_r": round(total_r, 2),
        "expectancy": round(total_r / n, 4) if n else 0.0,
        "avg_win_r": round(sum(t["realized_r"] for t in wins) / len(wins), 2) if wins else 0.0,
        "avg_loss_r": round(sum(t["realized_r"] for t in losses) / len(losses), 2) if losses else 0.0,
        "max_dd_r": round(mdd, 2),
        # legacy key -- purana code "tp" expect karta tha
        "tp": len(wins),
    }


def get_last_trades(limit: int = 10, asset: str | None = None) -> list[dict]:
    trades = _trades
    if asset:
        a = asset.lower()
        trades = [t for t in trades if t["asset"].lower() == a]
    return list(reversed(trades[-limit:]))


def history_text(limit: int = 10, asset: str | None = None) -> str:
    trades = get_last_trades(limit, asset=asset)
    if not trades:
        return "❌ No trades available."

    icons = {"OPEN": "🔵", "TP": "✅", "SL": "🛑", "BE": "⚪", "EXPIRED": "⏳"}
    lines = ["📜 LAST TRADES\n"]

    for t in trades:
        icon = icons.get(t["status"], "❓")
        r = t.get("realized_r", 0.0)
        hits = "".join(f"TP{i} " for i in (1, 2, 3) if t.get(f"hit_tp{i}")) or "—"
        lines.append(
            f"#{t['id']} | {t['asset'].upper()} | {t['signal']} {icon}\n"
            f"Entry  : {t['entry']}\n"
            f"SL     : {t['sl']}\n"
            f"Hits   : {hits}\n"
            f"Result : {r:+.2f}R\n"
            f"Status : {t['status']}\n"
            f"{t['time']}\n"
        )

    return "\n".join(lines)
