from indicators import ema

def get_signal(close_prices):
    ema20 = ema(close_prices, 20)
    ema50 = ema(close_prices, 50)
    ema200 = ema(close_prices, 200)

    signal = "NO TRADE"

    if ema20 and ema50 and ema200:
        if ema20 > ema50 > ema200:
            signal = "BUY"
        elif ema20 < ema50 < ema200:
            signal = "SELL"

    return {
        "ema20": ema20,
        "ema50": ema50,
        "ema200": ema200,
        "signal": signal
    }
