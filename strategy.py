from indicators import (
    ema,
    rsi,
    macd,
    atr,
    atr_moving_average,
    adx,
    trend_strength,
    vwap,
    bollinger_bands,
    bollinger_signal,
    supertrend,
)

from trend import get_trend
from risk import calculate_trade
from smart_money import analyze_smart_money
from patterns import detect_pattern
from session import get_current_session

# ==========================
# GOLD AI SCALPER PRO V5 - SCORE WEIGHTS (total = 100)
# ==========================
W_EMA = 15
W_ADX = 10
W_SUPERTREND = 15
W_VWAP = 10
W_MACD = 10
W_RSI = 10
W_VOLUME = 10
W_ATR = 5
W_MTF = 15
W_LIQUIDITY = 10

MIN_SCORE = 80               # V5: nothing fires below this
SIGNAL_VALID_MINUTES = 8

STRICT_BULL = {"Strong Bullish", "Bullish"}
STRICT_BEAR = {"Strong Bearish", "Bearish"}


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


def _empty_result(reason="Not enough candles"):
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
        "atr_ok": False,
        "liquidity_ok": False,
        "macd": {"macd": 0, "signal": 0, "trend": "-"},
        "rsi": 0,
        "pattern": "None",
        "liquidity_sweep": "NO",
        "bollinger": "None",
        "buy_confirmations": 0,
        "sell_confirmations": 0,
        "reasons": [reason],
        "valid_minutes": SIGNAL_VALID_MINUTES,
        "entry": None,
        "sl": None,
        "tp1": None,
        "tp2": None,
        "tp3": None,
        "risk_reward": "-",
    }


def get_signal(close, high, low, timeframes, volume=None, open_=None):

    if close is None or len(close) < 200:
        return _empty_result()

    price = round(close[-1], 2)

    ema20 = ema(close, 20)
    ema50 = ema(close, 50)
    ema200 = ema(close, 200)

    rsi_value = rsi(close)
    macd_value = macd(close)
    atr_value = atr(high, low, close)
    atr_ma_value = atr_moving_average(high, low, close)
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
    bb_signal = bollinger_signal(close, high, low)
    st = supertrend(high, low, close)
    smc = analyze_smart_money(high, low, close)

    session_name, session_active = get_current_session()

    if open_:
        pattern_name, pattern_direction = detect_pattern(open_, high, low, close)
    else:
        pattern_name, pattern_direction = "None", None

    # ==========================
    # 2. EMA FILTER
    # ==========================
    ema_bull = ema20 > ema50 > ema200
    ema_bear = ema20 < ema50 < ema200

    # ==========================
    # 3. ADX FILTER
    # ==========================
    adx_ok = adx_value >= 25

    # ==========================
    # 4. SUPERTREND
    # ==========================
    st_bull = st["trend"] == "Bullish"
    st_bear = st["trend"] == "Bearish"

    # ==========================
    # 5. VWAP
    # ==========================
    vwap_bull = price > vwap_value
    vwap_bear = price < vwap_value

    # ==========================
    # 6. RSI (widened bands)
    # ==========================
    rsi_bull = 55 <= rsi_value <= 72
    rsi_bear = 28 <= rsi_value <= 45

    # ==========================
    # 7. MACD (line vs signal + histogram)
    # ==========================
    histogram = round(macd_value["macd"] - macd_value["signal"], 4)
    macd_bull = macd_value["macd"] > macd_value["signal"] and histogram > 0
    macd_bear = macd_value["macd"] < macd_value["signal"] and histogram < 0

    # ==========================
    # 8. MULTI TIMEFRAME (2-of-3 agreement, includes Weak variants)
    # ==========================
    bullish_trends = {"Strong Bullish", "Bullish", "Weak Bullish"}
    bearish_trends = {"Strong Bearish", "Bearish", "Weak Bearish"}
    mtf_bull_count = sum(t in bullish_trends for t in [trend1, trend5, trend15])
    mtf_bear_count = sum(t in bearish_trends for t in [trend1, trend5, trend15])
    mtf_bull = mtf_bull_count >= 2
    mtf_bear = mtf_bear_count >= 2

    # ==========================
    # 9. VOLUME FILTER (current >= 85% of 20-candle average)
    # ==========================
    volume_ok = False
    if volume and len(volume) >= 20:
        recent_avg = sum(volume[-20:-1]) / len(volume[-20:-1])
        current_vol = volume[-1]
        volume_ok = recent_avg > 0 and current_vol >= recent_avg * 0.85

    # ==========================
    # 10. ATR FILTER (scoring bonus only, not a hard gate)
    # ==========================
    atr_ok = bool(atr_ma_value) and atr_value > atr_ma_value

    # ==========================
    # 12. LIQUIDITY FILTER (avoid fake breakouts / raw sweep entries)
    # ==========================
    liquidity_ok = not smc["fake_breakout"]

    # ==========================
    # 14. SESSION FILTER - info only now, not a hard gate
    # (BTC trades 24/7 and this was cutting too many valid gold setups)
    # ==========================
    session_ok = True

    # ==========================
    # SCORE (only counts the side currently being evaluated)
    # ==========================
    def score_side(is_bull):
        s = 0
        s += W_EMA if (ema_bull if is_bull else ema_bear) else 0
        s += W_ADX if adx_ok else 0
        s += W_SUPERTREND if (st_bull if is_bull else st_bear) else 0
        s += W_VWAP if (vwap_bull if is_bull else vwap_bear) else 0
        s += W_MACD if (macd_bull if is_bull else macd_bear) else 0
        s += W_RSI if (rsi_bull if is_bull else rsi_bear) else 0
        s += W_VOLUME if volume_ok else 0
        s += W_ATR if atr_ok else 0
        s += W_MTF if (mtf_bull if is_bull else mtf_bear) else 0
        s += W_LIQUIDITY if liquidity_ok else 0
        return s

    buy_score = score_side(True)
    sell_score = score_side(False)

    buy_confirmations = sum([
        ema_bull, adx_ok, st_bull, vwap_bull, macd_bull,
        rsi_bull, volume_ok, atr_ok, mtf_bull, liquidity_ok,
    ])
    sell_confirmations = sum([
        ema_bear, adx_ok, st_bear, vwap_bear, macd_bear,
        rsi_bear, volume_ok, atr_ok, mtf_bear, liquidity_ok,
    ])

    # ==========================
    # 17. FINAL CONFIRMATION
    # ==========================
    buy_all_true = all([
        ema_bull, adx_ok, st_bull, vwap_bull, rsi_bull, macd_bull,
        mtf_bull, volume_ok, liquidity_ok, session_ok,
    ])
    sell_all_true = all([
        ema_bear, adx_ok, st_bear, vwap_bear, rsi_bear, macd_bear,
        mtf_bear, volume_ok, liquidity_ok, session_ok,
    ])

    reasons = []
    final_signal = "NO TRADE"

    if buy_all_true and buy_score >= MIN_SCORE:
        final_signal = "BUY"
        reasons = [
            "EMA Bullish Stack", "ADX Strong", "Bullish Supertrend",
            "Above VWAP", f"RSI Healthy ({rsi_value})", "Bullish MACD",
            "MTF Bullish Alignment", "Volume OK",
            "No Fake Breakout / Clean Liquidity",
        ]
    elif sell_all_true and sell_score >= MIN_SCORE:
        final_signal = "SELL"
        reasons = [
            "EMA Bearish Stack", "ADX Strong", "Bearish Supertrend",
            "Below VWAP", f"RSI Healthy ({rsi_value})", "Bearish MACD",
            "MTF Bearish Alignment", "Volume OK",
            "No Fake Breakout / Clean Liquidity",
        ]
    else:
        checklist_bull = {
            "EMA": ema_bull, "ADX": adx_ok, "Supertrend": st_bull,
            "VWAP": vwap_bull, "RSI": rsi_bull, "MACD": macd_bull,
            "MTF": mtf_bull, "Volume": volume_ok, "ATR": atr_ok,
            "Liquidity": liquidity_ok, "Session": session_ok,
        }
        checklist_bear = {
            "EMA": ema_bear, "ADX": adx_ok, "Supertrend": st_bear,
            "VWAP": vwap_bear, "RSI": rsi_bear, "MACD": macd_bear,
            "MTF": mtf_bear, "Volume": volume_ok, "ATR": atr_ok,
            "Liquidity": liquidity_ok, "Session": session_ok,
        }
        checklist = checklist_bull if buy_score >= sell_score else checklist_bear
        failed = [k for k, v in checklist.items() if not v]
        reasons = [f"NO TRADE - failed: {', '.join(failed)}"] if failed else ["NO TRADE - score below threshold"]
        if pattern_direction:
            reasons.append(f"{pattern_direction} Pattern (info only): {pattern_name}")
        if bb_signal != "None":
            reasons.append(f"Bollinger (info only): {bb_signal}")

    ai_score = round(buy_score if final_signal == "BUY" else sell_score if final_signal == "SELL" else max(buy_score, sell_score), 2)

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
        "adx_ok": adx_ok,
        "vwap_ok": vwap_bull,
        "supertrend_ok": st_bull,
        "volume_ok": volume_ok,
        "atr_ok": atr_ok,
        "liquidity_ok": liquidity_ok,
        "macd": macd_value,
        "rsi": rsi_value,
        "pattern": pattern_name,
        "liquidity_sweep": smc["liquidity_side"] if smc["liquidity"] else "NO",
        "bollinger": bb_signal,
        "buy_confirmations": buy_confirmations,
        "sell_confirmations": sell_confirmations,
        "reasons": reasons,
        "valid_minutes": SIGNAL_VALID_MINUTES,
        **trade_levels,
    }
