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

BASE_MIN_SCORE = 55          # normal minimum score to trigger a signal
OFF_SESSION_MIN_SCORE = 70   # stricter minimum during low-liquidity sessions
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
            "ai_score": 0,
            "grade": "-",
            "market_status": "-",
            "session": "-",
            "session_active": True,
            "trend_1m": "-",
            "trend_5m": "-",
            "trend_15m": "-",
            "trend_strength": "-",
            "ema_ok": False,
            "adx_ok": False,
            "vwap_ok": False,
            "supertrend_ok": False,
            "volume_ok": False,
            "macd": {"macd": 0, "signal": 0, "trend": "-"},
            "rsi": 0,
            "pattern": "None",
            "liquidity_sweep": "NO",
            "buy_confirmations": 0,
            "sell_confirmations": 0,
            "reasons": ["Not enough candles"],
            "valid_minutes": SIGNAL_VALID_MINUTES,
            "entry": None,
            "sl": None,
            "tp1": None,
            "tp2": None,
            "tp3": None,
            "risk_reward": "-",
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
    # all three timeframes agree with the leading side
    # ==========================
    bullish_trends = {"Strong Bullish", "Bullish", "Weak Bullish"}
    bearish_trends = {"Strong Bearish", "Bearish", "Weak Bearish"}

    mtf_bull_count = sum(t in bullish_trends for t in [trend1, trend5, trend15])
    mtf_bear_count = sum(t in bearish_trends for t in [trend1, trend5, trend15])

    if mtf_bull_count == 3:
        buy_score += W_MTF
        buy_confirmations += 1
        reasons.append("MTF Full Bullish Alignment")
    elif mtf_bull_count == 2:
        buy_score += W_MTF * 0.5
        reasons.append("MTF Partial Bullish Alignment")

    if mtf_bear_count == 3:
        sell_score += W_MTF
        sell_confirmations += 1
        reasons.append("MTF Full Bearish Alignment")
    elif mtf_bear_count == 2:
        sell_score += W_MTF * 0.5
        reasons.append("MTF Partial Bearish Alignment")

    # ==========================
    # Volume Filter (not scored, acts as a gate)
    # ==========================
    volume_ok = True
    if volume and len(volume) >= 20:
        recent_avg = sum(volume[-20:-1]) / len(volume[-20:-1])
        current_vol = volume[-1]
        if recent_avg > 0:
            volume_ok = current_vol >= recent_avg * LOW_VOLUME_RATIO
            if not volume_ok:
                reasons.append("Low Volume Warning")

    # ==========================
    # Candlestick pattern bonus
    # ==========================
    if pattern_direction == "Bullish":
        buy_score += 5
        reasons.append(f"Bullish Pattern: {pattern_name}")
    elif pattern_direction == "Bearish":
        sell_score += 5
        reasons.append(f"Bearish Pattern: {pattern_name}")

    # ==========================
    # Smart Money Concepts bonus
    # ==========================
    if smc["bos_direction"] == "Bullish" or smc["choch_direction"] == "Bullish":
        buy_score += 5
    if smc["bos_direction"] == "Bearish" or smc["choch_direction"] == "Bearish":
        sell_score += 5

    if smc["liquidity"]:
        reasons.append(f"Liquidity Sweep: {smc['liquidity_side']}")

    # ==========================
    # Final decision
    # ==========================
    min_score = BASE_MIN_SCORE if session_active else OFF_SESSION_MIN_SCORE
    ai_score = round(max(buy_score, sell_score), 2)

    if buy_score > sell_score and buy_score >= min_score and volume_ok:
        final_signal = "BUY"
    elif sell_score > buy_score and sell_score >= min_score and volume_ok:
        final_signal = "SELL"
    else:
        final_signal = "NO TRADE"

    if ai_score >= 90:
        grade = "A+"
    elif ai_score >= 80:
        grade = "A"
    elif ai_score >= 70:
        grade = "B"
    elif ai_score >= 60:
        grade = "C"
    else:
        grade = "D"

    market_status = "Active" if session_active else "Low Liquidity"

    trade_levels = calculate_trade(final_signal, price, atr_value)

    return {
        "signal": final_signal,
        "confidence": ai_score,
        "ai_score": ai_score,
        "grade": grade,
        "market_status": market_status,
        "session": session_name,
        "session_active": session_active,
        "trend_1m": trend1,
        "trend_5m": trend5,
        "trend_15m": trend15,
        "trend_strength": trend_power,
        "ema_ok": ema_bull or ema_bear,
        "adx_ok": adx_value >= 25,
        "vwap_ok": price > vwap_value,
        "supertrend_ok": st["trend"] == "Bullish",
        "volume_ok": volume_ok,
        "macd": macd_value,
        "rsi": rsi_value,
        "pattern": pattern_name,
        "liquidity_sweep": smc["liquidity_side"] if smc["liquidity"] else "NO",
        "buy_confirmations": buy_confirmations,
        "sell_confirmations": sell_confirmations,
        "reasons": reasons,
        "valid_minutes": SIGNAL_VALID_MINUTES,
        **trade_levels,
    }
