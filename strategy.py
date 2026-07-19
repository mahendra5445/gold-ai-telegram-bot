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
from smart_money import analyze_smart_money
from patterns import detect_pattern
from session import get_current_session

# ==========================
# SCORE WEIGHTS (total = 100)
# ==========================
W_EMA = 15
W_SUPERTREND = 20
W_ADX = 15
W_MACD = 15
W_RSI = 10
W_VWAP = 10
W_MTF = 15

BASE_MIN_SCORE = 70          # normal minimum score to trigger a signal
OFF_SESSION_MIN_SCORE = 85   # stricter minimum during low-liquidity sessions
LOW_VOLUME_RATIO = 0.7       # current volume must be >= 70% of recent average
SIGNAL_VALID_MINUTES = 8


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


def get_signal(close, high, low, timeframes, volume=None, open_=None):

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
    smc = analyze_smart_money(high, low, close)

    session_name, session_active = get_current_session()

    # ==========================
    # Pattern detection (needs open prices; fall back gracefully)
    # ==========================
    if open_:
        pattern_name, pattern_direction = detect_pattern(open_, high, low, close)
    else:
        pattern_name, pattern_direction = "None", None

    reasons = []
    buy_score = 0
    sell_score = 0

    buy_confirmations = 0
    sell_confirmations = 0

    ema_bull = ema20 > ema50 > ema200
    ema_bear = ema20 < ema50 < ema200

    # ==========================
    # EMA (15)
    # ==========================
    if ema_bull:
        buy_score += W_EMA
        buy_confirmations += 1
        reasons.append("EMA Bullish Stack")
    if ema_bear:
        sell_score += W_EMA
        sell_confirmations += 1
        reasons.append("EMA Bearish Stack")

    # ==========================
    # Supertrend (20)
    # ==========================
    if st["trend"] == "Bullish":
        buy_score += W_SUPERTREND
        buy_confirmations += 1
        reasons.append("Bullish Supertrend")
    else:
        sell_score += W_SUPERTREND
        sell_confirmations += 1
        reasons.append("Bearish Supertrend")

    # ==========================
    # ADX (15) - strength only, added to whichever side already leads
    # ==========================
    if adx_value >= 25:
        if buy_score >= sell_score:
            buy_score += W_ADX
            buy_confirmations += 1
        else:
            sell_score += W_ADX
            sell_confirmations += 1
        reasons.append("Strong ADX")

    # ==========================
    # MACD (15)
    # ==========================
    if macd_value["trend"] == "Bullish":
        buy_score += W_MACD
        buy_confirmations += 1
        reasons.append("Bullish MACD")
    else:
        sell_score += W_MACD
        sell_confirmations += 1
        reasons.append("Bearish MACD")

    # ==========================
    # RSI (10)
    # ==========================
    if 55 <= rsi_value <= 75:
        buy_score += W_RSI
        buy_confirmations += 1
        reasons.append("Healthy RSI (Bullish)")
    elif 25 <= rsi_value <= 45:
        sell_score += W_RSI
        sell_confirmations += 1
        reasons.append("Healthy RSI (Bearish)")

    # ==========================
    # VWAP (10)
    # ==========================
    if price > vwap_value:
        buy_score += W_VWAP
        buy_confirmations += 1
        reasons.append("Above VWAP")
    else:
        sell_score += W_VWAP
        sell_confirmations += 1
        reasons.append("Below VWAP")

    # ==========================
    # Multi-Timeframe Trend (15) - full credit only if
