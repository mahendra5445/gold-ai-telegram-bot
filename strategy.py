from indicators import (
    ema, rsi, macd, atr, adx,
    vwap, bollinger_bands,
    supertrend, trend_strength,
)
from risk import calculate_trade
from trend import get_trend


def get_signal(close_prices, high_prices, low_prices, timeframes, volume=None):
    trend_1m = get_trend(timeframes["1m"])
    trend_5m = get_trend(timeframes["5m"])
    trend_15m = get_trend(timeframes["15m"])

    ema20 = ema(close_prices, 20)
    ema50 = ema(close_prices, 50)
    ema200 = ema(close_prices, 200)

    rsi_value = rsi(close_prices)
    macd_data = macd(close_prices)
    atr_value = atr(high_prices, low_prices, close_prices)
    adx_value = adx(high_prices, low_prices, close_prices)

    st = supertrend(high_prices, low_prices, close_prices)
    bb = bollinger_bands(close_prices)

    price = round(close_prices[-1], 2)
    vwap_value = vwap(high_prices, low_prices, close_prices, volume) if volume else price

    buy = sell = score = 0
    reasons = []

    if trend_1m.startswith("Strong") or trend_1m == "Bullish":
        buy += 1
    if trend_5m.startswith("Strong") or trend_5m == "Bullish":
        buy += 1
    if trend_15m.startswith("Strong") or trend_15m == "Bullish":
        buy += 1

    if trend_1m.endswith("Bearish"):
        sell += 1
    if trend_5m.endswith("Bearish"):
        sell += 1
    if trend_15m.endswith("Bearish"):
        sell += 1

    if ema20 > ema50 > ema200:
        score += 20
        reasons.append("EMA Alignment")

    if adx_value >= 25:
        score += 15
        reasons.append("Strong ADX")

    if st["trend"] == macd_data["trend"]:
        score += 15
        reasons.append("Supertrend")

    if price > vwap_value:
        score += 10
        reasons.append("Above VWAP")

    if bb["lower"] < price < bb["upper"]:
        score += 10
        reasons.append("Bollinger OK")

    if rsi_value >= 55 or rsi_value <= 45:
        score += 10
        reasons.append("RSI")

    score += 10
    reasons.append("MACD")

    signal = "NO TRADE"
    trend = "Sideways"

    if buy >= 2 and score >= 60:
        signal = "BUY"
        trend = "Bullish"
    elif sell >= 2 and score >= 60:
        signal = "SELL"
        trend = "Bearish"

    trade = calculate_trade(signal, price, atr_value)

    return {
        "ema20": ema20, "ema50": ema50, "ema200": ema200,
        "rsi": rsi_value, "macd": macd_data,
        "atr": atr_value, "adx": adx_value,
        "trend_1m": trend_1m, "trend_5m": trend_5m,
        "trend_15m": trend_15m,
        "signal": signal,
        "entry": trade["entry"], "sl": trade["sl"],
        "tp1": trade["tp1"], "tp2": trade["tp2"],
        "risk_reward": trade["risk_reward"],
        "confidence": min(score, 99),
        "signal_quality": "⭐⭐⭐⭐" if score >= 80 else "⭐⭐⭐" if score >= 60 else "⭐⭐",
        "trend_strength": trend_strength(adx_value),
        "ai_score": score,
        "grade": "A" if score >= 80 else "B" if score >= 60 else "C",
        "market_status": "Trending" if adx_value >= 25 else "Sideways",
        "buy_confirmations": buy,
        "sell_confirmations": sell,
        "reasons": reasons,
    }
