from indicators import (
    ema,
    rsi,
    macd,
    atr,
    adx,
    trend_strength,
    vwap,
    bollinger_bands,
    supertrend,
)

from trend import get_trend
from risk import calculate_trade


def confidence_label(score):
    if score >= 90:
        return "Excellent"
    elif score >= 80:
        return "Very Strong"
    elif score >= 70:
        return "Strong"
    elif score >= 60:
        return "Good"
    elif score >= 50:
        return "Average"
    return "Weak"


def get_signal(close, high, low, timeframes, volume=None):

    if close is None or len(close) < 200:
        return {
            "signal": "NO TRADE",
            "confidence": 0,
            "reasons": ["Not enough candles"],
        }

    price = round(close[-1], 2)

    ema20 = ema(close, 20)
    ema50 = ema(close, 50)
    ema200 = ema(close, 200)

    rsi_value = rsi(close)
    macd_value = macd(close)
    atr_value = atr(high, low, close)
    adx_value = adx(high, low, close)

    trend1 = get_trend(timeframes["1m"])
    trend5 = get_trend(timeframes["5m"])
    trend15 = get_trend(timeframes["15m"])

    trend_power = trend_strength(adx_value)

    if volume:
        vwap_value = vwap(high, low, close, volume)
    else:
        vwap_value = price

    bb = bollinger_bands(close)
    st = supertrend(high, low, close)

    buy_score = 0
    sell_score = 0

    buy_confirmations = 0
    sell_confirmations = 0
    reasons = []

    # ==========================
    # BUY CONDITIONS
    # ==========================

    if ema20 > ema50:
        buy_score += 10
        buy_confirmations += 1
        reasons.append("EMA20 above EMA50")

    if ema50 > ema200:
        buy_score += 10
        buy_confirmations += 1
        reasons.append("EMA50 above EMA200")

    if price > ema20:
        buy_score += 10
        buy_confirmations += 1
        reasons.append("Price above EMA20")

    if macd_value["trend"] == "Bullish":
        buy_score += 10
        buy_confirmations += 1
        reasons.append("Bullish MACD")

    if 55 <= rsi_value <= 75:
        buy_score += 10
        buy_confirmations += 1
        reasons.append("Healthy RSI")

    if adx_value >= 25:
        buy_score += 10
        buy_confirmations += 1
        reasons.append("Strong ADX")

    if price > vwap_value:
        buy_score += 10
        buy_confirmations += 1
        reasons.append("Above VWAP")

    if st["trend"] == "Bullish":
        buy_score += 10
        buy_confirmations += 1
        reasons.append("Bullish Supertrend")

    # ==========================
    # SELL CONDITIONS
    # ==========================

    if ema20 < ema50:
        sell_score += 10
        sell_confirmations += 1

    if ema50 < ema200:
        sell_score += 10
        sell_confirmations += 1

    if price < ema20:
        sell_score += 10
        sell_confirmations += 1

    if macd_value["trend"] == "Bearish":
        sell_score += 10
        sell_confirmations += 1

    if 25 <= rsi_value <= 45:
        sell_score += 10
        sell_confirmations += 1

    if adx_value >= 25:
        sell_score += 10
        sell_confirmations += 1

    if price < vwap_value:
        sell_score += 10
        sell_confirmations += 1

    if st["trend"] == "Bearish":
        sell_score += 10
        sell_confirmations += 1

    # ==========================
    # FINAL SIGNAL
    if buy_score >= 60 and buy_score > sell_score:
        signal = "BUY"
        ai_score = buy_score

    elif sell_score >= 60 and sell_score > buy_score:
        signal = "SELL"
        ai_score = sell_score

    else:
        signal = "NO TRADE"
        ai_score = max(buy_score, sell_score)

    confidence = min(ai_score, 100)
    grade = confidence_label(confidence)
    signal_quality = grade

    trade = calculate_trade(signal, price, atr_value)

    return {
        "signal": signal,
        "confidence": confidence,
        "grade": grade,
        "ai_score": ai_score,
        "signal_quality": signal_quality,
        "price": price,
        "entry": trade["entry"],
        "sl": trade["sl"],
        "tp1": trade["tp1"],
        "tp2": trade["tp2"],
        "tp3": trade["tp3"],
        "risk_reward": trade["risk_reward"],
        "ema20": ema20,
        "ema50": ema50,
        "ema200": ema200,
        "rsi": rsi_value,
        "macd": macd_value,
        "atr": atr_value,
        "adx": adx_value,
        "vwap": vwap_value,
        "bollinger": bb,
        "supertrend": st,
        "trend_1m": trend1,
        "trend_5m": trend5,
        "trend_15m": trend15,
        "trend_strength": trend_power,
        "buy_confirmations": buy_confirmations,
        "sell_confirmations": sell_confirmations,
        "market_status": "TRENDING" if adx_value >= 25 else "RANGING",
        "reasons": reasons,
    }
