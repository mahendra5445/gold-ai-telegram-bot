from indicators import ema, rsi, macd

def get_signal(close_prices):
    ema20 = ema(close_prices, 20)
    ema50 = ema(close_prices, 50)
    ema200 = ema(close_prices, 200)

    rsi_value = rsi(close_prices)
    macd_data = macd(close_prices)

    signal = "NO TRADE"
    confidence = 50

    if (
        ema20 > ema50 > ema200
        and rsi_value > 55
        and macd_data["trend"] == "Bullish"
    ):
        signal = "BUY"
        confidence = 90

    elif (
        ema20 < ema50 < ema200
        and rsi_value < 45
        and macd_data["trend"] == "Bearish"
    ):
        signal = "SELL"
        confidence = 90

    price = close_prices[-1]

    if signal == "BUY":
        entry = round(price, 2)
        sl = round(price - 5, 2)
        tp1 = round(price + 10, 2)
        tp2 = round(price + 20, 2)

    elif signal == "SELL":
        entry = round(price, 2)
        sl = round(price + 5, 2)
        tp1 = round(price - 10, 2)
        tp2 = round(price - 20, 2)

    else:
        entry = sl = tp1 = tp2 = None

    return {
        "ema20": ema20,
        "ema50": ema50,
        "ema200": ema200,
        "rsi": rsi_value,
        "macd": macd_data,
        "signal": signal,
        "entry": entry,
        "sl": sl,
        "tp1": tp1,
        "tp2": tp2,
        "confidence": confidence,
    }
