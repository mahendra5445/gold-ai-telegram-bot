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

    if signal not in ["BUY", "SELL"]:
        return

    trade = {
        "id": len(trades) + 1,
        "signal": signal,
        "entry": result["entry"],
        "sl": result["sl"],
        "tp1": result["tp1"],
        "tp2": result["tp2"],
        "status": "OPEN",
        "time": datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
    }

    trades.append(trade)

    if signal == "BUY":
        stats["buy"] += 1
    else:
        stats["sell"] += 1


def get_stats():
    total = stats["buy"] + stats["sell"]

    return {
        "total": total,
        "buy": stats["buy"],
        "sell": stats["sell"],
        "tp": stats["tp"],
        "sl": stats["sl"],
    }


def get_last_trades(limit=10):
    return trades[-limit:]
