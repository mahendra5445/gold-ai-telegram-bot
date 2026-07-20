from datetime import datetime

trades = []

stats = {
    "buy": 0,
    "sell": 0,
    "tp": 0,
    "sl": 0,
    "be": 0,
}


def save_trade(result, asset="gold"):
    signal = result.get("signal")

    if signal not in ["BUY", "SELL"]:
        return None

    trade = {
        "id": len(trades) + 1,
        "asset": asset,
        "signal": signal,
        "entry": float(result["entry"]),
        "sl": float(result["sl"]),
        "tp1": float(result["tp1"]),
        "tp2": float(result["tp2"]),
        "tp3": float(result["tp3"]),
        "hit_tp1": False,
        "hit_tp2": False,
        "hit_tp3": False,
        "status": "OPEN",
        "time": datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
    }

    trades.append(trade)

    if signal == "BUY":
        stats["buy"] += 1
    else:
        stats["sell"] += 1

    return trade


def get_open_trades():
    return [t for t in trades if t["status"] == "OPEN"]


def update_trade(trade_id, status):

    for trade in trades:

        if trade["id"] != trade_id:
            continue

        if trade["status"] != "OPEN":
            return False

        trade["status"] = status

        if status == "TP":
            stats["tp"] += 1

        elif status == "SL":
            stats["sl"] += 1

        elif status == "BE":
            stats["be"] += 1

        return True

    return False


def find_trade(trade_id):
    for trade in trades:
        if trade["id"] == trade_id:
            return trade
    return None


def get_stats():

    total = stats["buy"] + stats["sell"]
    closed = stats["tp"] + stats["sl"] + stats["be"]

    win_rate = 0

    if closed > 0:
        win_rate = round((stats["tp"] / closed) * 100, 2)

    return {
        "total": total,
        "buy": stats["buy"],
        "sell": stats["sell"],
        "tp": stats["tp"],
        "sl": stats["sl"],
        "be": stats["be"],
        "win_rate": win_rate,
    }


def get_last_trades(limit=10):
    return trades[-limit:]


def history_text(limit=10):

    if not trades:
        return "❌ No trades available."

    text = "📜 LAST TRADES\n\n"

    for trade in trades[-limit:][::-1]:

        text += (
            f"#{trade['id']} | {trade.get('asset','gold').upper()} | {trade['signal']}\n"
            f"Entry : {trade['entry']}\n"
            f"SL : {trade['sl']}\n"
            f"TP1 : {trade['tp1']}\n"
            f"TP2 : {trade['tp2']}\n"
            f"TP3 : {trade.get('tp3', '-')}\n"
            f"Status : {trade['status']}\n"
            f"{trade['time']}\n\n"
        )

    return text
