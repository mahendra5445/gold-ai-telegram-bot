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
        return "Very High"
    elif score >= 75:
        return "High"
    elif score >= 60:
        return "Medium"
    else:
        return "Low"


def get_signal(close, high, low, timeframes, volume):

    price = round(close[-1], 2)

    ema20 = ema(close, 20)
    ema50 = ema(close, 50)
    ema200 = ema(close, 200)

    rsi_value = rsi(close)

    macd_data = macd(close)
    macd_value = macd_data["macd"]
    macd_signal = macd_data["signal"]
    macd_trend = macd_data["trend"]

    atr_value = atr(high, low, close)

    adx_value = adx(high, low, close)
    adx_strength = trend_strength(adx_value)

    vwap_value = vwap(high, low, close, volume)

    bb = bollinger_bands(close)
    bb_upper = bb["upper"]
    bb_middle = bb["middle"]
    bb_lower = bb["lower"]

    st = supertrend(high, low, close)
    st_trend = st["trend"]
    st_value = st["value"]

    trend_1m = get_trend(timeframes["1m"])
    trend_5m = get_trend(timeframes["5m"])
    trend_15m = get_trend(timeframes["15m"])

    buy_score = 0
    sell_score = 0    # ==========================
    # BUY SCORE
    # ==========================

    if price > ema20:
        buy_score += 10

    if ema20 > ema50:
        buy_score += 10

    if ema50 > ema200:
        buy_score += 15

    if 50 < rsi_value < 70:
        buy_score += 10

    if macd_value > macd_signal:
        buy_score += 15

    if st_trend == "Bullish":
        buy_score += 15

    if price > vwap_value:
        buy_score += 10

    if trend_1m in ["Bullish", "Strong Bullish"]:
        buy_score += 5

    if trend_5m in ["Bullish", "Strong Bullish"]:
        buy_score += 5

    if trend_15m in ["Bullish", "Strong Bullish"]:
        buy_score += 5

    # ==========================
    # SELL SCORE
    # ==========================

    if price < ema20:
        sell_score += 10

    if ema20 < ema50:
        sell_score += 10

    if ema50 < ema200:
        sell_score += 15

    if 30 < rsi_value < 50:
        sell_score += 10

    if macd_value < macd_signal:
        sell_score += 15

    if st_trend == "Bearish":
        sell_score += 15

    if price < vwap_value:
        sell_score += 10

    if trend_1m in ["Bearish", "Strong Bearish"]:
        sell_score += 5

    if trend_5m in ["Bearish", "Strong Bearish"]:
        sell_score += 5

    if trend_15m in ["Bearish", "Strong Bearish"]:
        sell_score += 5

    # ==========================
    # FINAL SIGNAL
    # ==========================

    signal = "NO TRADE"
    score = max(buy_score, sell_score)

    if buy_score >= 70 and adx_value >= 20:
        signal = "BUY"

    elif sell_score >= 70 and adx_value >= 20:
        signal = "SELL"

    confidence = confidence_label(score)

    trade = calculate_trade(
        signal,
        price,
        atr_value,
    )    return {
        "signal": signal,
        "confidence": confidence,
        "score": score,

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
        "macd_signal": macd_signal,
        "macd_trend": macd_trend,

        "atr": atr_value,

        "adx": adx_value,
        "adx_strength": adx_strength,

        "vwap": vwap_value,

        "bb_upper": bb_upper,
        "bb_middle": bb_middle,
        "bb_lower": bb_lower,

        "supertrend": st_trend,
        "supertrend_value": st_value,

        "trend_1m": trend_1m,
        "trend_5m": trend_5m,
        "trend_15m": trend_15m,

        "buy_score": buy_score,
        "sell_score": sell_score,
    }
