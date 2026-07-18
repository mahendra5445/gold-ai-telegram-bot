def calculate_trade(signal, price, atr):
    """
    Calculate Entry, Stop Loss, Take Profit and Risk Reward
    """

    if signal == "BUY":
        entry = round(price, 2)
        sl = round(price - (atr * 1.5), 2)
        tp1 = round(price + (atr * 2), 2)
        tp2 = round(price + (atr * 4), 2)

    elif signal == "SELL":
        entry = round(price, 2)
        sl = round(price + (atr * 1.5), 2)
        tp1 = round(price - (atr * 2), 2)
        tp2 = round(price - (atr * 4), 2)

    else:
        return {
            "entry": None,
            "sl": None,
            "tp1": None,
            "tp2": None,
            "risk_reward": "-"
        }

    risk = abs(entry - sl)
    reward = abs(tp1 - entry)

    rr = round(reward / risk, 2) if risk > 0 else 0

    return {
        "entry": entry,
        "sl": sl,
        "tp1": tp1,
        "tp2": tp2,
        "risk_reward": f"1:{rr}"
    }
