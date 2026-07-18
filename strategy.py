from indicators import ema, rsi, macd, atr
from risk import calculate_trade


def get_signal(close_prices, high_prices, low_prices):
    ema20 = ema(close_prices, 20)
    ema50 = ema(close_prices, 50)
    ema200 = ema(close_prices, 200)

    rsi_value = rsi(close_prices)
    macd_data = macd(close_prices)
    atr_value = atr(high_prices, low_prices, close_prices)

    signal = "NO TRADE"
    confidence = 50
    trend_strength = "Sideways"

    if (
        ema20 > ema50 > ema200
        and rsi_value > 55
        and macd_data["trend"] == "Bullish"
    ):
        signal = "BUY"
        confidence = 90 if rsi_value > 60 else 80
        trend_strength = "Strong Bullish"

    elif (
        ema20 < ema50 < ema200
        and rsi_value < 45
        and macd_data["trend"] == "Bearish"
    ):
        signal = "SELL"
        confidence = 90 if rsi_value < 40 else 80
        trend_strength = "Strong Bearish"

    price = round(close_prices[-1], 2)

    trade = calculate_trade(
        signal=signal,
        price=price,
        atr=atr_value
    )

    return {
        "ema20": ema20,
        "ema50": ema50,
        "ema200": ema200,
        "rsi": rsi_value,
        "macd": macd_data,
        "atr": atr_value,
        "signal": signal,
        "entry": trade["entry"],
        "sl": trade["sl"],
        "tp1": trade["tp1"],
        "tp2": trade["tp2"],
        "risk_reward": trade["risk_reward"],
        "confidence": confidence,
        "trend_strength": trend_streng"ai_score": confidence,

"grade": (
    "A+" if confidence >= 90 else
    "A" if confidence >= 80 else
    "B" if confidence >= 70 else
    "C" if confidence >= 60 else
    "D"
),th,
    }
