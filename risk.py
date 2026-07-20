def calculate_trade(signal, price, atr):
    """
    Smart Risk Management
    - ATR based Stop Loss
    - TP1, TP2, TP3 built off the risk distance so Risk:Reward
      is always at least 1:2
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

    sl_mult = 1.0
    risk = round(atr * sl_mult, 2)

    if risk <= 0:
        risk = round(price * 0.001, 2)  # fallback tiny risk to avoid div by 0

    tp1_reward = risk * 2.0
    tp2_reward = risk * 3.0
    tp3_reward = risk * 4.0

    if signal == "BUY":
        sl = round(entry - risk, 2)
        tp1 = round(entry + tp1_reward, 2)
        tp2 = round(entry + tp2_reward, 2)
        tp3 = round(entry + tp3_reward, 2)

    else:  # SELL
        sl = round(entry + risk, 2)
        tp1 = round(entry - tp1_reward, 2)
        tp2 = round(entry - tp2_reward, 2)
        tp3 = round(entry - tp3_reward, 2)

    actual_risk = abs(entry - sl)
    actual_reward = abs(tp1 - entry)

    rr = round(actual_reward / actual_risk, 2) if actual_risk > 0 else 0

    return {
        "entry": entry,
        "sl": sl,
        "tp1": tp1,
        "tp2": tp2,
        "tp3": tp3,
        "risk_reward": f"1:{rr}"
    }
