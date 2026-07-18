from datetime import datetime

trades = []

stats = {
    "buy": 0,
    "sell": 0,
    "tp": 0,
    "sl": 0,
}


def save_trade(result):
    signal = result.get("signal")

    if signal not in ("BUY", "SELL"):
        return

    trade = {
        "id": len(trades) + 1,
        "signal": signal,
        "entry": float(result["entry"]),
        "sl": float(result["sl"]),
        "tp1": float(result["tp1"]),
        "tp2": float(result["tp2"]),
        "status": "OPEN",
        "time": datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
    }

    trades.append(trade)

    if signal == "BUY":
        stats["buy"] += 1
    else:
        stats["sell"] += 1


def get_open_trades():
    return [t for t in trades if t["status"] == "OPEN"]


def update_trade(trade_id, status):
    for trade in trades:

        if trade["id"] != trade_id:
            continue

        # दोबारा update नहीं होगा
        if trade["status"] != "OPEN":
            return False

        trade["status"] = status

        if status == "TP":
            stats["tp"] += 1

        elif status == "SL":
            stats["sl"] += 1

        return True

    return False


def get_stats():
    total = stats["buy"] + stats["sell"]

    win_rate = 0

    closed = stats["tp"] + stats["sl"]

    if closed > 0:
        win_rate = round((stats["tp"] / closed) * 100, 2)

    return {
        "total": total,
        "buy": stats["buy"],
        "sell": stats["sell"],
        "tp": stats["tp"],
        "sl": stats["sl"],
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
            f"#{trade['id']} | {trade['signal']}\n"
            f"Entry : {trade['entry']}\n"
            f"SL : {trade['sl']}\n"
            f"TP1 : {trade['tp1']}\n"
            f"TP2 : {trade['tp2']}\n"
            f"Status : {trade['status']}\n"
            f"{trade['time']}\n\n"
        )

    return text
