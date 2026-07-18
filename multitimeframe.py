from indicators import ema


def analyze_timeframes(data):
    """
    Multi Timeframe Analysis
    """

    result = {}

    for timeframe, close_prices in data.items():

        ema20 = ema(close_prices, 20)
        ema50 = ema(close_prices, 50)
        ema200 = ema(close_prices, 200)

        if ema20 > ema50 > ema200:
            trend = "BUY"

        elif ema20 < ema50 < ema200:
            trend = "SELL"

        else:
            trend = "SIDEWAYS"

        result[timeframe] = {
            "ema20": ema20,
            "ema50": ema50,
            "ema200": ema200,
            "trend": trend
        }

    buy = sum(
        1 for tf in result.values()
        if tf["trend"] == "BUY"
    )

    sell = sum(
        1 for tf in result.values()
        if tf["trend"] == "SELL"
    )

    if buy >= 2:
        overall = "BUY"

    elif sell >= 2:
        overall = "SELL"

    else:
        overall = "NO TRADE"

    return {
        "timeframes": result,
        "overall": overall
    }
