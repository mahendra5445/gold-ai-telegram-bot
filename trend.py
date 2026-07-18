from indicators import ema


def get_trend(close_prices):
    ema20 = ema(close_prices, 20)
    ema50 = ema(close_prices, 50)
    ema200 = ema(close_prices, 200)

    if ema20 > ema50 > ema200:
        return "Bullish"

    if ema20 < ema50 < ema200:
        return "Bearish"

    return "Sideways"
