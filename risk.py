import math


def calculate_trade(signal, price, atr, decimals=2):
    """
    Smart Risk Management
    - ATR based Stop Loss
    - TP1, TP2, TP3 built off the risk distance so Risk:Reward
      is always at least 1:2

    `decimals` controls rounding precision — gold/BTC/oil use 2, but a pair
    like EUR/USD needs 4-5 decimals or a 0.01 rounding would erase ~100 pips
    of precision. Defaults to 2 for backward compatibility with old callers.
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

    entry = round(price, decimals)

    # BUG FIX: SL was only 1.5x ATR(5m). On gold that's often just $1-2,
    # which sits inside normal broker spread + tick noise, so trades were
    # getting stopped out almost immediately even when direction was
    # right (this is why SL Hit was far higher than TP Hit / win rate
    # was ~0%). Widened to 2.5x ATR — a more realistic scalping stop.
    sl_mult = 2.0

    # atr can come through as NaN if upstream data had a gap - guard that
    # explicitly since `nan <= 0` is False in Python, so the old
    # "risk <= 0" fallback below would silently let NaN through and turn
    # every SL/TP into "nan" in the Telegram message.
    if atr is None or (isinstance(atr, float) and math.isnan(atr)):
        atr = 0

    risk = round(atr * sl_mult, decimals)

    # BUG FIX: minimum SL floor. Previously the price*0.001 fallback only
    # kicked in when risk was <= 0. In quiet markets ATR could still
    # produce a small positive risk (e.g. ~$1) that slipped straight
    # through spread/noise and got stopped out instantly. Now we always
    # enforce a floor of 0.15% of price, regardless of how small ATR is.
    min_risk = round(price * 0.0015, decimals)
    if risk < min_risk:
        risk = min_risk

    # Reward multiples of risk -> TP1 = 2.5R, TP2 = 4R, TP3 = 6R (runner target)
    tp1_reward = risk * 2.5
    tp2_reward = risk * 4.0
    tp3_reward = risk * 6.0

    if signal == "BUY":
        sl = round(entry - risk, decimals)
        tp1 = round(entry + tp1_reward, decimals)
        tp2 = round(entry + tp2_reward, decimals)
        tp3 = round(entry + tp3_reward, decimals)

    else:  # SELL
        sl = round(entry + risk, decimals)
        tp1 = round(entry - tp1_reward, decimals)
        tp2 = round(entry - tp2_reward, decimals)
        tp3 = round(entry - tp3_reward, decimals)

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
