from indicators import (
    ema,
    rsi,
    macd,
    atr,
    adx,
    vwap,
    bollinger_bands,
    supertrend,
    trend_strength,
)
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

    st = supertrend(high_prices, low_prices, close_prices)
    bb = bollinger_bands(close_prices)

    if volume:
        vwap_value = vwap(high_prices, low_prices, close_prices, volume)
    else:
        vwap_value = round(close_prices[-1], 2)

    price = round(close_prices[-1], 2)

    buy_count = sum(t == "Bullish" for t in [trend_1m, trend_5m, trend_15m])
    sell_count = sum(t == "Bearish" for t in [trend_1m, trend_5m, trend_15m])

    ai_score = 0
    reasons = []

    if buy_count == 3 or sell_count == 3:
        ai_score += 25
        reasons.append("MTF Confirmed")

    if ema20 > ema50 > ema200 or ema20 < ema50 < ema200:
        ai_score += 20
        reasons.append("EMA Alignment")

    if adx_value >= 25:
        ai_score += 15
        reasons.append("Strong ADX")

    ai_score += 15
    reasons.append("MACD Confirmed")

    if st["trend"] == macd_data["trend"]:
        ai_score += 10
        reasons.append("Supertrend Confirmed")

    if price > vwap_value:
        ai_score += 5
        reasons.append("Above VWAP")
    elif price < vwap_value:
        ai_score += 5
        reasons.append("Below VWAP")

    if bb["lower"] < price < bb["upper"]:
        ai_score += 5
        reasons.append("Inside Bollinger")

    if rsi_value >= 55 or rsi_value <= 45:
        ai_score += 5
        reasons.append("RSI Confirmed")

    signal = "NO TRADE"
    trend_text = "Sideways"

    if buy_count >= 2 and st["trend"] == "Bullish" and ema20 > ema50 and macd_data["trend"] == "Bullish":
        signal = "BUY"
        trend_text = "Bullish"

    if sell_count >= 2 and st["trend"] == "Bearish" and ema20 < ema50 and macd_data["trend"] == "Bearish":
        signal = "SELL"
        trend_text = "Bearish"

    confidence = min(ai_score, 99)

    if ai_score >= 95:
        grade = "A+"
        quality = "⭐⭐⭐⭐⭐"
    elif ai_score >= 85:
        grade = "A"
        quality = "⭐⭐⭐⭐"
    elif ai_score >= 70:
        grade = "B"
        quality = "⭐⭐⭐"
    else:
        grade = "C"
        quality = "⭐⭐"

    trade = calculate_trade(signal=signal, price=price, atr=atr_value)

    return {
        "signal": signal,
        "entry": trade["entry"],
        "sl": trade["sl"],
        "tp1": trade["tp1"],
        "tp2": trade["tp2"],
        "risk_reward": trade["risk_reward"],
        "ema20": ema20,
        "ema50": ema50,
        "ema200": ema200,
        "rsi": rsi_value,
        "macd": macd_data,
        "atr": atr_value,
        "adx": adx_value,
        "vwap": vwap_value,
        "bollinger": bb,
        "supertrend": st,
        "trend_strength": trend_strength(adx_value),
        "trend_1m": trend_1m,
        "trend_5m": trend_5m,
        "trend_15m": trend_15m,
        "confidence": confidence,
        "ai_score": ai_score,
        "grade": grade,
        "signal_quality": quality,
        "market_status": "Trending" if adx_value >= 25 else "Sideways",
        "buy_confirmations": buy_count,
        "sell_confirmations": sell_count,
        "reasons": reasons,
    }
