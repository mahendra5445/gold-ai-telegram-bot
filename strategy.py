from indicators import (
    ema,
    rsi,
    macd,
    atr,
    adx,
    vwap,
    bollinger_bands,a
    supertrend,
    trend_strength,
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

    atr_value = atr(
        high_prices,
        low_prices,
        close_prices,
    )

    adx_value = adx(
        high_prices,
        low_prices,
        close_prices,
    )

    st = supertrend(
        high_prices,
        low_prices,
        close_prices,
    )

    bb = bollinger_bands(close_prices)

    price = round(close_prices[-1], 2)

    if volume:
        vwap_value = vwap(
            high_prices,
            low_prices,
            close_prices,
            volume,
        )
    else:
        vwap_value = price

    buy = 0
    sell = 0
    score = 0
    reasons = []

    # ===========================
    # Multi Timeframe Trend
    # ===========================

    if trend_1m.startswith("Strong") or trend_1m == "Bullish":
        buy += 1
        score += 5

    elif trend_1m.endswith("Bearish"):
        sell += 1
        score += 5

    if trend_5m.startswith("Strong") or trend_5m == "Bullish":
        buy += 2
        score += 10

    elif trend_5m.endswith("Bearish"):
        sell += 2
        score += 10

    if trend_15m.startswith("Strong") or trend_15m == "Bullish":
        buy += 3
        score += 15

    elif trend_15m.endswith("Bearish"):
        sell += 3
        score += 15

    # ===========================
    # EMA
    # ===========================

    if ema20 > ema50 > ema200:
        buy += 2
        score += 20
        reasons.append("EMA Bullish")

    elif ema20 < ema50 < ema200:
        sell += 2# ===========================
    # ADX
    # ===========================

    if adx_value >= 30:
        score += 20
        reasons.append("Strong Trend")

    elif adx_value >= 20:
        score += 10
        reasons.append("Trending")

    # ===========================
    # RSI
    # ===========================

    if 55 <= rsi_value <= 70:
        buy += 1
        score += 10
        reasons.append("RSI Bullish")

    elif 30 <= rsi_value <= 45:
        sell += 1
        score += 10
        reasons.append("RSI Bearish")

    # ===========================
    # MACD
    # ===========================

    if macd_data["trend"] == "Bullish":
        buy += 1
        score += 10
        reasons.append("MACD Bullish")

    elif macd_data["trend"] == "Bearish":
        sell += 1
        score += 10
        reasons.append("MACD Bearish")

    # ===========================
    # Supertrend
    # ===========================

    if st["trend"] == "Bullish":
        buy += 1
        score += 10
        reasons.append("Supertrend Bullish")

    elif st["trend"] == "Bearish":
        sell += 1
        score += 10
        reasons.append("Supertrend Bearish")

    # ===========================
    # VWAP
    # ===========================

    if price > vwap_value:
        buy += 1
        score += 10
        reasons.append("Above VWAP")

    elif price < vwap_value:
        sell += 1
        score += 10
        reasons.append("Below VWAP")

    # ===========================
    # Bollinger Bands
    # ===========================

    if bb["lower"] < price < bb["upper"]:
        score += 5
        reasons.append("Inside Bollinger")

    # ===========================
    # Sideways Filter
    # ===========================

    if adx_value < 20:
        signal = "NO TRADE"

    else:

        if buy > sell:

            if buy >= 7 and score >= 75:
                signal = "STRONG BUY"

            elif buy >= 5 and score >= 60:
                signal = "BUY"

            else:
                signal = "NO TRADE"

        elif sell > buy:

            if sell >= 7 and score >= 75:
                signal = "STRONG SELL"

            elif sell >= 5 and score >= 60:
                signal = "SELL"

            else:
                signal = "NO TRADE"

        else:
            signal = "NO TRADE"# ===========================
    # Trade Calculation
    # ===========================

    trade = calculate_trade(
        "BUY" if "BUY" in signal else
        "SELL" if "SELL" in signal else
        signal,
        price,
        atr_value,
    )

    # ===========================
    # Confidence
    # ===========================

    confidence = min(score, 99)

    if confidence >= 90:
        grade = "A+"
        stars = "⭐⭐⭐⭐⭐"

    elif confidence >= 80:
        grade = "A"
        stars = "⭐⭐⭐⭐"

    elif confidence >= 70:
        grade = "B"
        stars = "⭐⭐⭐"

    else:
        grade = "C"
        stars = "⭐⭐"

    # ===========================
    # Return Result
    # ===========================

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
        "signal_quality": stars,

        "trend_strength": trend_strength(adx_value),

        "ai_score": score,
        "grade": grade,

        "market_status": (
            "Trending"
            if adx_value >= 20
            else "Sideways"
        ),

        "buy_confirmations": buy,
        "sell_confirmations": sell,

        "reasons": reasons,
    }
        score += 20
        reasons.append("EMA Bearish")
