def analyze_smart_money(high, low, close):
    """
    Basic Smart Money Concepts
    Version 1.0
    """

    bos = False
    choch = False
    order_block = "None"
    fvg = False
    liquidity = False

    # Break Of Structure
    if close[-1] > max(close[-6:-1]):
        bos = True

    if close[-1] < min(close[-6:-1]):
        bos = True

    # Change Of Character
    if len(close) > 20:
        if close[-1] > close[-5] and close[-5] < close[-10]:
            choch = True

        elif close[-1] < close[-5] and close[-5] > close[-10]:
            choch = True

    # Order Block
    if close[-1] > close[-2]:
        order_block = "Bullish"

    elif close[-1] < close[-2]:
        order_block = "Bearish"

    # Fair Value Gap
    if high[-3] < low[-1]:
        fvg = True

    elif low[-3] > high[-1]:
        fvg = True

    # Liquidity Sweep
    if high[-1] > max(high[-6:-1]):
        liquidity = True

    elif low[-1] < min(low[-6:-1]):
        liquidity = True

    return {
        "bos": bos,
        "choch": choch,
        "order_block": order_block,
        "fvg": fvg,
        "liquidity": liquidity,
    }
