def calculate_trade(signal, price, atr):
    """
    Smart Risk Management
    - Dynamic ATR Stop Loss
    - TP1, TP2, TP3
    - Better Risk : Reward
    """

    if signal not in ["BUY", "SELL"]:
        return {
            "entry": None,
            "sl": None,
            "tp1": None,
            "tp2": None,
            "tp3": None,
            "risk_reward": "-"
        }

    entry = round(price, 2)

    # ATR multiplier
    sl_mult = 1.8
    tp1_mult = 2.0
    tp2_mult = 3.5
    tp3_mult = 5.0

    if signal == "BUY":
        sl = round(entry - (atr * sl_mult), 2)
        tp1 = round(entry + (atr * tp1_mult), 2)
        tp2 = round(entry + (atr * tp2_mult), 2)
        tp3 = round(entry + (atr * tp3_mult), 2)

    else:  # SELL
        sl = round(entry + (atr * sl_mult), 2)
        tp1 = round(entry - (atr * tp1_mult), 2)
        tp2 = round(entry - (atr * tp2_mult), 2)
        tp3 = round(entry - (atr * tp3_mult), 2)

    risk = abs(entry - sl)
    reward = abs(tp1 - entry)

    rr = round(reward / risk, 2) if risk > 0 else 0

    return {
        "entry": entry,
        "sl": sl,
        "tp1": tp1,
        "tp2": tp2,
        "tp3": tp3,
        "risk_reward": f"1:{rr}"
    }
