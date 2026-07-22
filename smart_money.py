"""
Smart Money Concepts — V2 (asli implementation)

PURANA CODE KYA KAR RAHA THA (aur kyun galat tha):

  BOS          : close[-1] > max(close[-6:-1])
                 -> ye sirf "5-candle high" hai. Break of Structure ka
                    matlab hota hai pichhla SWING HIGH toota, na ki
                    pichhli 5 candles ka high.

  Order Block  : close[-1] > close[-2]  -> "Bullish"
                 -> ye sirf "aaj ki candle green hai" hai. Order block
                    wo aakhri opposite candle hoti hai jahan se impulsive
                    move shuru hua. Purane code ka OB se koi taalluq nahi tha.

  CHoCH        : close[-1] > close[-5] and close[-5] < close[-10]
                 -> ye ek zig-zag pattern hai, Change of Character nahi.
                    CHoCH tab hota hai jab trend ka structure ulat jaaye.

Ab teenon asli swing points pe based hain.
"""


def _find_swings(high, low, lookback=3):
    """
    Swing high = jis candle ka high apne dono taraf `lookback` candles se
    upar ho. Swing low ulta. Ye SMC ki buniyaad hai.
    Returns: (swing_highs, swing_lows) — [(index, price), ...]
    """
    highs, lows = [], []
    n = len(high)
    for i in range(lookback, n - lookback):
        wh = high[i - lookback:i + lookback + 1]
        wl = low[i - lookback:i + lookback + 1]
        if high[i] == max(wh) and wh.count(high[i]) == 1:
            highs.append((i, high[i]))
        if low[i] == min(wl) and wl.count(low[i]) == 1:
            lows.append((i, low[i]))
    return highs, lows


def analyze_smart_money(high, low, close, open_=None):
    result = {
        "bos": False, "bos_direction": "None",
        "choch": False, "choch_direction": "None",
        "order_block": "None", "order_block_zone": None,
        "fvg": False, "fvg_direction": "None",
        "liquidity": False, "liquidity_side": "None",
        "fake_breakout": False,
        "premium_discount": "Equilibrium",
        "structure": "None",
        "smc_score": 0,
    }

    if len(close) < 40:
        return result

    swing_highs, swing_lows = _find_swings(list(high), list(low))
    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return result

    last_sh, prev_sh = swing_highs[-1], swing_highs[-2]
    last_sl, prev_sl = swing_lows[-1], swing_lows[-2]
    price = close[-1]

    # ── STRUCTURE (HH/HL vs LH/LL) ────────────────────────────────────────
    hh = last_sh[1] > prev_sh[1]
    hl = last_sl[1] > prev_sl[1]
    if hh and hl:
        result["structure"] = "Bullish (HH/HL)"
    elif not hh and not hl:
        result["structure"] = "Bearish (LH/LL)"
    else:
        result["structure"] = "Mixed"

    # ── BREAK OF STRUCTURE — asli swing high/low toota ────────────────────
    if price > last_sh[1]:
        result["bos"] = True
        result["bos_direction"] = "Bullish"
        result["smc_score"] += 20
    elif price < last_sl[1]:
        result["bos"] = True
        result["bos_direction"] = "Bearish"
        result["smc_score"] += 20

    # ── CHoCH — trend ka character badla ──────────────────────────────────
    if result["structure"].startswith("Bullish") and price < last_sl[1]:
        result["choch"] = True
        result["choch_direction"] = "Bearish"
        result["smc_score"] += 15
    elif result["structure"].startswith("Bearish") and price > last_sh[1]:
        result["choch"] = True
        result["choch_direction"] = "Bullish"
        result["smc_score"] += 15

    # ── ORDER BLOCK — impulsive move se pehle wali aakhri opposite candle ──
    if open_ and len(open_) == len(close):
        for i in range(len(close) - 2, max(len(close) - 20, 11), -1):
            body = abs(close[i] - open_[i])
            avg_body = sum(abs(close[j] - open_[j]) for j in range(i - 10, i)) / 10
            if avg_body <= 0 or body < avg_body * 1.8:
                continue
            if close[i] > open_[i] and close[i - 1] < open_[i - 1]:
                result["order_block"] = "Bullish"
                result["order_block_zone"] = (low[i - 1], high[i - 1])
                result["smc_score"] += 15
            elif close[i] < open_[i] and close[i - 1] > open_[i - 1]:
                result["order_block"] = "Bearish"
                result["order_block_zone"] = (low[i - 1], high[i - 1])
                result["smc_score"] += 15
            break

    # ── FAIR VALUE GAP — 3-candle imbalance ───────────────────────────────
    if high[-3] < low[-1]:
        result["fvg"] = True
        result["fvg_direction"] = "Bullish"
        result["smc_score"] += 10
    elif low[-3] > high[-1]:
        result["fvg"] = True
        result["fvg_direction"] = "Bearish"
        result["smc_score"] += 10

    # ── LIQUIDITY SWEEP — swing level ke paar gaya phir wapas aa gaya ─────
    if high[-1] > last_sh[1] and close[-1] < last_sh[1]:
        result["liquidity"] = True
        result["liquidity_side"] = "Buy Side"
        result["smc_score"] += 20
    elif low[-1] < last_sl[1] and close[-1] > last_sl[1]:
        result["liquidity"] = True
        result["liquidity_side"] = "Sell Side"
        result["smc_score"] += 20

    # ── FAKE BREAKOUT — sweep hua par koi structural follow-through nahi ──
    if result["liquidity"] and not result["bos"]:
        result["fake_breakout"] = True

    # ── PREMIUM / DISCOUNT ────────────────────────────────────────────────
    rng_high = max(h for _, h in swing_highs[-3:])
    rng_low = min(l for _, l in swing_lows[-3:])
    mid = (rng_high + rng_low) / 2
    if price > mid * 1.0005:
        result["premium_discount"] = "Premium"
    elif price < mid * 0.9995:
        result["premium_discount"] = "Discount"

    return result
