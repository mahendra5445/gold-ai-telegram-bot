from indicators import ema, rsi, macd, atr, adx
from risk import calculate_trade
from trend import get_trend


def get_signal(close_prices, high_prices, low_prices, timeframes, volume=None):

    trend_1m = get_trend(timeframes["1m"])
    trend_5m = get_trend(timeframes["5m"])
    trend_15m = get_trend(timeframes["15m"])

    ema20 = round(ema(close_prices, 20), 2)
    ema50 = round(ema(close_prices, 50), 2)
    ema200 = round(ema(close_prices, 200), 2)

    rsi_value = round(rsi(close_prices), 2)
    macd_data = macd(close_prices)
    atr_value = round(atr(high_prices, low_prices, close_prices), 2)
    adx_value = round(adx(high_prices, low_prices, close_prices), 2)

    price = round(close_prices[-1], 2)

    signal = "NO TRADE"
    trend_strength = "Sideways"
    ai_score = 0
    grade = "C"
    market_status = "Sideways"
    reasons = []
    buy_count = 0
    sell_count = 0

    for trend in [trend_1m, trend_5m, trend_15m]:
        if trend == "Bullish":
            buy_count += 1
        elif trend == "Bearish":
            sell_count += 1

    if buy_count == 3 or sell_count == 3:
        ai_score += 25
        reasons.append("MTF Confirmed")
    if ema20 > ema50 > ema200 or ema20 < ema50 < ema200:
        ai_score += 20
        reasons.append("EMA Alignment")
    if macd_data["trend"] in ["Bullish","Bearish"]:
        ai_score += 15
        reasons.append("MACD Confirmed")
    if adx_value >= 25:
        ai_score += 15
        reasons.append("Strong ADX")
    if atr_value > 0:
        ai_score += 10
        reasons.append("Healthy Volatility")
    if rsi_value >= 55 or rsi_value <= 45:
        ai_score += 15
        reasons.append("RSI Confirmed")

    if adx_value >= 30:
        market_status = "Trending"
    elif adx_value >= 20:
        market_status = "Moderate"

    if buy_count == 3 and ai_score >= 80 and ema20 > ema50 > ema200 and rsi_value >= 55 and macd_data["trend"] == "Bullish" and adx_value >= 25:
        signal = "BUY"
        trend_strength = "Strong Bullish"
    elif buy_count >= 2 and ema20 > ema50 and macd_data["trend"] == "Bullish" and adx_value >= 20:
        signal = "BUY"
        trend_strength = "Bullish"
    elif sell_count == 3 and ai_score >= 80 and ema20 < ema50 < ema200 and rsi_value <= 45 and macd_data["trend"] == "Bearish" and adx_value >= 25:
        signal = "SELL"
        trend_strength = "Strong Bearish"
    elif sell_count >= 2 and ema20 < ema50 and macd_data["trend"] == "Bearish" and adx_value >= 20:
        signal = "SELL"
        trend_strength = "Bearish"

    confidence = min(ai_score,99)
    if signal == "NO TRADE":
        confidence = min(ai_score,60)

    if ai_score >= 95:
        signal_quality = "⭐⭐⭐⭐⭐"
        grade = "A+"
    elif ai_score >= 85:
        signal_quality = "⭐⭐⭐⭐"
        grade = "A"
    elif ai_score >= 70:
        signal_quality = "⭐⭐⭐"
        grade = "B"
    elif ai_score >= 55:
        signal_quality = "⭐⭐"
    else:
        signal_quality = "⭐"

    trade = calculate_trade(signal=signal, price=price, atr=atr_value)

    return {
        "ema20": ema20,
        "ema50": ema50,
        "ema200": ema200,
        "rsi": rsi_value,
        "macd": macd_data,
        "atr": atr_value,
        "adx": adx_value,
        "trend_1m": trend_1m,
        "trend_5m": trend_5m,
        "trend_15m": trend_15m,
        "signal": signal,
        "entry": trade["entry"],
        "sl": trade["sl"],
        "tp1": trade["tp1"],
        "tp2": trade["tp2"],
        "risk_reward": trade["risk_reward"],
        "confidence": confidence,
        "signal_quality": signal_quality,
        "trend_strength": trend_strength,
        "ai_score": ai_score,
        "grade": grade,
        "market_status": market_status,
        "buy_confirmations": buy_count,
        "sell_confirmations": sell_count,
        "reasons": reasons,
    }
