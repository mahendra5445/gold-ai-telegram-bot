from indicators import ema


def analyze_trend(close_prices):
    ema20 = ema(close_prices, 20)
    ema50 = ema(close_prices, 50)
    ema200 = ema(close_prices, 200)

    score = 50
    trend = "Sideways"

    if ema20 > ema50 > ema200:
        trend = "Strong Bullish"
        score = 90

    elif ema20 > ema50:
        trend = "Bullish"
        score = 75

    elif ema20 < ema50 < ema200:
        trend = "Strong Bearish"
        score = 90

    elif ema20 < ema50:
        trend = "Bearish"
        score = 75

    return {
        "trend": trend,
        "score": score
    }
