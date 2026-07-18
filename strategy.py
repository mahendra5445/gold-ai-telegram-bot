from indicators import ema, rsi, macd, atr
from risk import calculate_trade


def get_signal(close_prices, high_prices, low_prices):
    ema20 = round(ema(close_prices, 20), 2)
    ema50 = round(ema(close_prices, 50), 2)
    ema200 = round(ema(close_prices, 200), 2)

    rsi_value = round(rsi(close_prices), 2)
    macd_data = macd(close_prices)
    atr_value = round(atr(high_prices, low_prices, close_prices), 2)

    price = round(close_prices[-1], 2)

    signal = "NO TRADE"
    confidence = 50
    trend_strength = "Sideways"

    # Trend distance
    ema_gap = abs(ema20 - ema50)

    # Strong Bullish
    if (
        ema20 > ema50 > ema200
        and ema_gap > atr_value * 0.10
        and rsi_value >= 60
        and macd_data["trend"] == "Bullish"
    ):
        signal = "BUY"
        confidence = 95
        trend_strength = "Strong Bullish"

    # Medium Bullish
    elif (
        ema20 > ema50 > ema200
        and rsi_value >= 55
        and macd_data["trend"] == "Bullish"
    ):
        signal = "BUY"
        confidence = 85
        trend_strength = "Bullish"

    # Strong Bearish
    elif (
        ema20 < ema50 < ema200
        and ema_gap > atr_value * 0.10
        and rsi_value <= 40
        and macd_data["trend"] == "Bearish"
    ):
        signal = "SELL"
        confidence = 95
        trend_strength = "Strong Bearish"

    # Medium Bearish
    elif (
        ema20 < ema50 < ema200
        and rsi_value <= 45
        and macd_data["trend"] == "Bearish"
    ):
        signal = "SELL"
        confidence = 85
        trend_strength = "Bearish"

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
        "trend_strength": trend_strength,
    }
