from indicators import (
    ema, rsi, macd, atr, atr_moving_average, adx, trend_strength,
    vwap, bollinger_bands, bollinger_signal, supertrend,
)

from trend import get_trend
from risk import calculate_trade
from smart_money import analyze_smart_money
from patterns import detect_pattern
from session import get_current_session
from market_regime import detect_regime
from config import (REQUIRE_BOS, REQUIRE_ORDER_BLOCK, REQUIRE_FVG,
                    REQUIRE_HTF_ALIGN, MIN_RR, REGIME_MODE)

# ==========================================================================
# SCORE WEIGHTS
#
# FIX (critical): pehle jab koi check ka data hi na ho, uska weight
# chupchaap muft mil jaata tha (volume_ok = True default), ya check hamesha
# fail hota tha (VWAP). Ab har check ka ek AVAILABILITY flag hai:
#   - available nahi  -> weight total se hi nikal diya jaata hai, baaki
#                        weights 100 pe renormalize ho jaate hain
#   - available hai   -> normally score karta hai
# Isse na muft points milte hain, na permanent penalty lagta hai.
# ==========================================================================
WEIGHTS = {
    "ema": 14, "supertrend": 14, "mtf": 14,        # directional, bhaari
    "adx": 9, "vwap": 9, "macd": 9, "rsi": 9,
    "volume": 9, "liquidity": 9,
    "atr": 4,
}

# --- Directional checks: BUY aur SELL ke liye ALAG result dete hain ---
DIRECTIONAL = {"ema", "supertrend", "mtf", "vwap", "macd", "rsi", "candle"}
# --- Non-directional: dono sides ko barabar milte hain ---
NON_DIRECTIONAL = {"adx", "volume", "volume_spike", "atr", "liquidity"}

# ==========================================================================
# THRESHOLDS -- sab ek jagah. Ye numbers BACKTEST se calibrate karein.
# ==========================================================================
MIN_SCORE = 62

# FIX: pehle sirf ek total count (MIN_CONFIRMATIONS = 8 of 12) tha, aur
# usmein se 5 non-directional the jo dono sides ko milte the -- yaani
# "8 confirmations" mein direction ka evidence sirf 3 ka bhi ho sakta tha.
# Ab directional evidence ka apna alag minimum hai.
MIN_DIRECTIONAL = 4          # 7 directional checks mein se
MIN_TOTAL_CONFIRMATIONS = 7  # sab milakar

# FIX: pehle BUY aur SELL dono qualify kar sakte the (250 test mein 5 baar
# hua) aur code chupchaap BUY chun leta tha (`elif`). Ab dono ka score
# compare hota hai, aur farq itna hona chahiye -- warna NO TRADE.
SCORE_MARGIN = 10

ADX_MIN = 22                 # NOTE: ADX ab sahi (Wilder) hai aur values kam
                             # aayengi -- ye threshold recalibrate karein
RSI_BULL = (52, 75)
RSI_BEAR = (25, 48)
VOLUME_MIN_RATIO = 0.85
VOLUME_SPIKE_RATIO = 1.05
VWAP_SESSION_BARS = 288      # 5m candles pe ~24 ghante

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
        "signal": "NO TRADE", "confidence": 0, "ai_score": 0, "grade": "-",
        "signal_tier": "-", "position_size": "-", "market_status": "-",
        "session": "-", "session_active": True,
        "trend_1m": "-", "trend_5m": "-", "trend_15m": "-", "trend_strength": "-",
        "ema_ok": False, "adx_ok": False, "vwap_ok": False, "supertrend_ok": False,
        "volume_ok": False, "atr_ok": False, "liquidity_ok": False,
        "macd": {"macd": 0, "signal": 0, "trend": "-"}, "rsi": 0,
        "pattern": "None", "liquidity_sweep": "NO", "bollinger": "None",
        "regime": "-", "regime_note": "-", "bb_percentile": 0,
        "structure": "-", "bos": "No", "choch": "No",
        "order_block": "None", "fvg": "No", "premium_discount": "-",
        "quality_fails": [],
        "buy_confirmations": 0, "sell_confirmations": 0,
        "buy_directional": 0, "sell_directional": 0,
        "unavailable": [], "reasons": [reason],
        "valid_minutes": SIGNAL_VALID_MINUTES, "atr_value": 0,
        "entry": None, "sl": None, "tp1": None, "tp2": None, "tp3": None,
        "risk_reward": "-", "risk_per_unit": None,
    }


def get_signal(close, high, low, timeframes, volume=None, open_=None,
               decimals=2, spread=0.0):

    if close is None or len(close) < 200:
        return _empty_result()

    price = round(close[-1], decimals)

    ema20, ema50, ema200 = ema(close, 20), ema(close, 50), ema(close, 200)
    rsi_value = rsi(close)
    macd_value = macd(close)
    atr_value = atr(high, low, close)
    atr_ma_value = atr_moving_average(high, low, close)
    adx_value = adx(high, low, close)

    trend1 = get_trend(timeframes["1m"])
    trend5 = get_trend(timeframes["5m"])
    trend15 = get_trend(timeframes["15m"])
    trend_power = trend_strength(adx_value)

    bb_signal = bollinger_signal(close, high, low)
    st = supertrend(high, low, close)
    smc = analyze_smart_money(high, low, close, open_)
    regime = detect_regime(close, high, low)      # Feature #6
    session_name, session_active = get_current_session()

    if open_:
        pattern_name, pattern_direction = detect_pattern(open_, high, low, close)
    else:
        pattern_name, pattern_direction = "None", None

    # ======================================================================
    # AVAILABILITY -- kaunsa check is data pe chal bhi sakta hai
    # ======================================================================
    available = {k: True for k in WEIGHTS}
    available["candle"] = bool(open_)
    available["volume_spike"] = False
    unavailable_notes = []

    volume_usable = bool(volume) and len(volume) >= 20 and sum(volume[-20:]) > 0

    # ── VWAP ──────────────────────────────────────────────────────────────
    # FIX (critical): pehle volume na hone pe `vwap_value = price` set hota
    # tha, jisse `price > vwap_value` HAMESHA False -- yaani VWAP check har
    # asset pe permanently fail. Test mein 400/400 baar fail hua. Yahoo
    # XAUUSD=X / EURUSD=X / GBPUSD=X / USDJPY=X charon pe volume zero hai,
    # to ye check kabhi pass hi nahi hota tha. Ab: data nahi = check hi
    # nahi (weight redistribute ho jaata hai).
    vwap_value = vwap(high, low, close, volume, VWAP_SESSION_BARS) if volume_usable else None
    if vwap_value is None:
        available["vwap"] = False
        unavailable_notes.append("VWAP (no volume data)")

    # ── VOLUME ────────────────────────────────────────────────────────────
    # FIX: pehle volume_ok aur volume_spike_ok dono `True` default the --
    # 9 points + 2 confirmations har signal ko MUFT mil jaate the bina kisi
    # information ke. Ab data na ho to check count hi nahi hota.
    if volume_usable:
        recent_avg = sum(volume[-20:-1]) / len(volume[-20:-1])
        current_vol = volume[-1]
        volume_ok = recent_avg > 0 and current_vol >= recent_avg * VOLUME_MIN_RATIO
        volume_spike_ok = recent_avg > 0 and current_vol >= recent_avg * VOLUME_SPIKE_RATIO
        available["volume_spike"] = True
    else:
        volume_ok = False
        volume_spike_ok = False
        available["volume"] = False
        unavailable_notes.append("Volume (no volume data)")

    # ======================================================================
    # CHECKS
    # ======================================================================
    ema_bull = ema20 > ema50 > ema200
    ema_bear = ema20 < ema50 < ema200

    adx_ok = adx_value >= ADX_MIN

    st_bull = st["trend"] == "Bullish"
    st_bear = st["trend"] == "Bearish"

    vwap_bull = vwap_value is not None and price > vwap_value
    vwap_bear = vwap_value is not None and price < vwap_value

    rsi_bull = RSI_BULL[0] <= rsi_value <= RSI_BULL[1]
    rsi_bear = RSI_BEAR[0] <= rsi_value <= RSI_BEAR[1]

    histogram = round(macd_value["macd"] - macd_value["signal"], 6)
    macd_bull = macd_value["macd"] > macd_value["signal"] and histogram > 0
    macd_bear = macd_value["macd"] < macd_value["signal"] and histogram < 0

    bullish_trends = {"Strong Bullish", "Bullish", "Weak Bullish"}
    bearish_trends = {"Strong Bearish", "Bearish", "Weak Bearish"}
    mtf_bull = sum(t in bullish_trends for t in [trend1, trend5, trend15]) >= 2
    mtf_bear = sum(t in bearish_trends for t in [trend1, trend5, trend15]) >= 2

    atr_ok = bool(atr_ma_value) and atr_value > atr_ma_value

    # Candle confirmation -- FIX: pehle open_ na hone pe dono True the
    # (muft confirmation). Ab available flag se handle hota hai.
    if open_:
        candle_bull_ok = close[-1] > open_[-1]
        candle_bear_ok = close[-1] < open_[-1]
    else:
        candle_bull_ok = candle_bear_ok = False
        unavailable_notes.append("Candle confirm (no open prices)")

    liquidity_ok = not smc["fake_breakout"] and not (smc["liquidity"] and not smc["bos"])

    # ======================================================================
    # SCORING -- available weights ko 100 pe renormalize
    # ======================================================================
    active_total = sum(w for k, w in WEIGHTS.items() if available[k])
    scale = 100.0 / active_total if active_total else 0.0

    def score_side(is_bull):
        hits = {
            "ema": ema_bull if is_bull else ema_bear,
            "supertrend": st_bull if is_bull else st_bear,
            "mtf": mtf_bull if is_bull else mtf_bear,
            "vwap": vwap_bull if is_bull else vwap_bear,
            "macd": macd_bull if is_bull else macd_bear,
            "rsi": rsi_bull if is_bull else rsi_bear,
            "adx": adx_ok, "volume": volume_ok,
            "liquidity": liquidity_ok, "atr": atr_ok,
        }
        return sum(WEIGHTS[k] for k, ok in hits.items() if ok and available[k]) * scale

    buy_score = score_side(True)
    sell_score = score_side(False)

    if pattern_direction == "Bullish":
        buy_score += 5
    elif pattern_direction == "Bearish":
        sell_score += 5

    if "London" in session_name or "New York" in session_name:
        buy_score += 3
        sell_score += 3

    if not session_active:
        buy_score -= 8
        sell_score -= 8

    buy_score = round(max(0, min(buy_score, 100)), 2)
    sell_score = round(max(0, min(sell_score, 100)), 2)

    # ======================================================================
    # CONFIRMATIONS -- directional aur non-directional ALAG
    # ======================================================================
    def count_side(is_bull):
        directional = {
            "ema": ema_bull if is_bull else ema_bear,
            "supertrend": st_bull if is_bull else st_bear,
            "mtf": mtf_bull if is_bull else mtf_bear,
            "vwap": vwap_bull if is_bull else vwap_bear,
            "macd": macd_bull if is_bull else macd_bear,
            "rsi": rsi_bull if is_bull else rsi_bear,
            "candle": candle_bull_ok if is_bull else candle_bear_ok,
        }
        non_dir = {
            "adx": adx_ok, "volume": volume_ok, "volume_spike": volume_spike_ok,
            "atr": atr_ok, "liquidity": liquidity_ok,
        }
        d = sum(1 for k, ok in directional.items() if ok and available.get(k, True))
        n = sum(1 for k, ok in non_dir.items() if ok and available.get(k, True))
        return d, n

    buy_dir, buy_non = count_side(True)
    sell_dir, sell_non = count_side(False)
    buy_confirmations = buy_dir + buy_non
    sell_confirmations = sell_dir + sell_non

    buy_qualifies = (
        buy_dir >= MIN_DIRECTIONAL
        and buy_confirmations >= MIN_TOTAL_CONFIRMATIONS
        and buy_score >= MIN_SCORE
    )
    sell_qualifies = (
        sell_dir >= MIN_DIRECTIONAL
        and sell_confirmations >= MIN_TOTAL_CONFIRMATIONS
        and sell_score >= MIN_SCORE
    )

    # ======================================================================
    # TRADE QUALITY FILTER (Feature #15)
    # Har gate config.py se on/off hota hai. Default: sirf regime aur HTF
    # on hain -- baaki off, kyunki sab ek saath on karne pe signals
    # lagbhag zero ho jaate hain.
    # ======================================================================
    quality_fails = []

    if REGIME_MODE == "strict":
        if regime["regime"] != "Trending":
            quality_fails.append(f"Regime: {regime['regime']} (strict mode)")
    elif REGIME_MODE == "not_range":
        if not regime["trend_ok"]:
            quality_fails.append(f"Regime: {regime['regime']}")

    if REQUIRE_HTF_ALIGN:
        htf_bull = trend15 in bullish_trends
        htf_bear = trend15 in bearish_trends
        if buy_qualifies and not htf_bull:
            quality_fails.append("15m trend BUY ke saath nahi")
        if sell_qualifies and not htf_bear:
            quality_fails.append("15m trend SELL ke saath nahi")

    if REQUIRE_BOS and not smc["bos"]:
        quality_fails.append("No Break of Structure")

    if REQUIRE_ORDER_BLOCK and smc["order_block"] == "None":
        quality_fails.append("No Order Block")

    if REQUIRE_FVG and not smc["fvg"]:
        quality_fails.append("No Fair Value Gap")

    if quality_fails:
        buy_qualifies = sell_qualifies = False

    # ======================================================================
    # FINAL -- conflict resolution ke saath
    # ======================================================================
    conflict_note = None
    if buy_qualifies and sell_qualifies:
        # FIX: pehle `elif` tha, to BUY hamesha jeet jaata tha chahe SELL ka
        # score zyada ho. Ab margin chahiye, warna koi trade nahi.
        if abs(buy_score - sell_score) < SCORE_MARGIN:
            buy_qualifies = sell_qualifies = False
            conflict_note = (
                f"NO TRADE - BUY ({buy_score}) aur SELL ({sell_score}) dono "
                f"qualify kar rahe hain, farq {SCORE_MARGIN} se kam hai"
            )
        elif sell_score > buy_score:
            buy_qualifies = False
        else:
            sell_qualifies = False

    def build_reasons(is_bull):
        checks = [
            (ema_bull if is_bull else ema_bear, "ema",
             "EMA Bullish Stack" if is_bull else "EMA Bearish Stack"),
            (st_bull if is_bull else st_bear, "supertrend",
             "Bullish Supertrend" if is_bull else "Bearish Supertrend"),
            (mtf_bull if is_bull else mtf_bear, "mtf",
             "MTF Bullish Alignment" if is_bull else "MTF Bearish Alignment"),
            (vwap_bull if is_bull else vwap_bear, "vwap",
             "Above VWAP" if is_bull else "Below VWAP"),
            (macd_bull if is_bull else macd_bear, "macd",
             "Bullish MACD" if is_bull else "Bearish MACD"),
            (rsi_bull if is_bull else rsi_bear, "rsi", f"RSI Healthy ({rsi_value})"),
            (candle_bull_ok if is_bull else candle_bear_ok, "candle",
             "Bullish Candle Confirmed" if is_bull else "Bearish Candle Confirmed"),
            (adx_ok, "adx", f"ADX Strong ({adx_value})"),
            (volume_ok, "volume", "Volume OK"),
            (volume_spike_ok, "volume_spike", "Volume Spike"),
            (atr_ok, "atr", "ATR Expansion"),
            (liquidity_ok, "liquidity", "No Fake Breakout / Clean Liquidity"),
        ]
        return [label for ok, key, label in checks if ok and available.get(key, True)]

    if buy_qualifies:
        final_signal, reasons = "BUY", build_reasons(True)
    elif sell_qualifies:
        final_signal, reasons = "SELL", build_reasons(False)
    else:
        final_signal = "NO TRADE"
        if conflict_note:
            reasons = [conflict_note]
        elif quality_fails:
            reasons = [f"NO TRADE - quality filter: {', '.join(quality_fails)}"]
        else:
            side_bull = buy_score >= sell_score
            checklist = {
                "EMA": ema_bull if side_bull else ema_bear,
                "Supertrend": st_bull if side_bull else st_bear,
                "MTF": mtf_bull if side_bull else mtf_bear,
                "VWAP": vwap_bull if side_bull else vwap_bear,
                "MACD": macd_bull if side_bull else macd_bear,
                "RSI": rsi_bull if side_bull else rsi_bear,
                "Candle": candle_bull_ok if side_bull else candle_bear_ok,
                "ADX": adx_ok, "Volume": volume_ok, "ATR": atr_ok,
                "Liquidity": liquidity_ok,
            }
            failed = [k for k, v in checklist.items()
                      if not v and available.get(k.lower(), True)]
            d = buy_dir if side_bull else sell_dir
            reasons = [
                f"NO TRADE - directional {d}/{MIN_DIRECTIONAL} needed, "
                f"score {max(buy_score, sell_score)}/{MIN_SCORE} needed"
            ]
            if failed:
                reasons.append(f"Failed: {', '.join(failed)}")
        if pattern_direction:
            reasons.append(f"{pattern_direction} Pattern (info only): {pattern_name}")
        if bb_signal != "None":
            reasons.append(f"Bollinger (info only): {bb_signal}")

    if unavailable_notes:
        reasons.append(f"Not scored (no data): {', '.join(unavailable_notes)}")

    ai_score = buy_score if final_signal == "BUY" else \
        sell_score if final_signal == "SELL" else max(buy_score, sell_score)

    active_dir = buy_dir if final_signal == "BUY" else \
        sell_dir if final_signal == "SELL" else max(buy_dir, sell_dir)
    active_conf = buy_confirmations if final_signal == "BUY" else \
        sell_confirmations if final_signal == "SELL" else max(buy_confirmations, sell_confirmations)

    # ======================================================================
    # SETUP STRENGTH (pehle ise "Confidence %" kaha jaata tha)
    #
    # FIX: purana code confirmations ko seedha percent bana deta tha
    # (11 -> "90%", 12 -> "98-100%"). Wo ek lookup table thi, probability
    # nahi -- kisi data se derive nahi hui thi, lekin user ko aisa lagta tha
    # ki 90% chance hai jeetne ka. Ab ye ek saaf X/Y count hai. Asli
    # win probability sirf backtest se aati hai, indicator ginti se nahi.
    # ======================================================================
    max_dir = sum(1 for k in DIRECTIONAL if available.get(k, True))
    max_conf = max_dir + sum(1 for k in NON_DIRECTIONAL if available.get(k, True))
    setup_strength = f"{active_dir}/{max_dir} directional, {active_conf}/{max_conf} total"

    def position_sizing(d, total_dir):
        if total_dir <= 0:
            return "Not Traded", "0%"
        ratio = d / total_dir
        if ratio >= 0.85:
            return "Full Size", "100%"
        if ratio >= 0.70:
            return "Standard Size", "75%"
        if ratio >= 0.55:
            return "Reduced Risk - Half Size", "50%"
        return "Reduced Risk - Quarter Size", "25%"

    signal_tier, position_size_pct = position_sizing(active_dir, max_dir) \
        if final_signal != "NO TRADE" else ("-", "-")

    grade = "A+" if ai_score >= 90 else "A" if ai_score >= 80 else \
            "B" if ai_score >= 70 else "C" if ai_score >= 60 else "D"

    market_status = "Active" if session_active else "Low Liquidity"

    trade_levels = calculate_trade(
        final_signal, price, atr_value, decimals=decimals,
        session_active=session_active, spread=spread,
    )

    # MIN_RR gate — spread ke baad RR itna to hona hi chahiye
    if final_signal != "NO TRADE" and MIN_RR:
        try:
            rr_val = float(str(trade_levels["risk_reward"]).split(":")[1])
            if rr_val < MIN_RR:
                reasons = [f"NO TRADE - RR {rr_val} < required {MIN_RR} "
                           f"(spread ke baad)"]
                final_signal = "NO TRADE"
                trade_levels = calculate_trade("NO TRADE", price, atr_value,
                                               decimals=decimals)
                signal_tier, position_size_pct = "-", "-"
        except (ValueError, IndexError):
            pass

    return {
        "signal": final_signal,
        "confidence": setup_strength,
        "ai_score": ai_score,
        "grade": grade,
        "signal_tier": signal_tier,
        "position_size": position_size_pct,
        "market_status": market_status,
        "session": session_name,
        "session_active": session_active,
        "trend_1m": trend1, "trend_5m": trend5, "trend_15m": trend15,
        "trend_strength": trend_power,
        "ema_ok": ema_bull or ema_bear,
        "adx_ok": adx_ok,
        "vwap_ok": vwap_bear if final_signal == "SELL" else vwap_bull,
        "vwap_available": available["vwap"],
        "supertrend_ok": st_bear if final_signal == "SELL" else st_bull,
        "volume_ok": volume_ok,
        "volume_available": available["volume"],
        "atr_ok": atr_ok,
        "liquidity_ok": liquidity_ok,
        "macd": macd_value,
        "rsi": rsi_value,
        "adx_value": adx_value,
        "regime": regime["regime"],
        "regime_note": regime["note"],
        "bb_percentile": regime["bb_percentile"],
        "structure": smc["structure"],
        "bos": smc["bos_direction"] if smc["bos"] else "No",
        "choch": smc["choch_direction"] if smc["choch"] else "No",
        "order_block": smc["order_block"],
        "fvg": smc["fvg_direction"] if smc["fvg"] else "No",
        "premium_discount": smc["premium_discount"],
        "quality_fails": quality_fails,
        "pattern": pattern_name,
        "liquidity_sweep": smc["liquidity_side"] if smc["liquidity"] else "NO",
        "bollinger": bb_signal,
        "buy_confirmations": buy_confirmations,
        "sell_confirmations": sell_confirmations,
        "buy_directional": buy_dir,
        "sell_directional": sell_dir,
        "unavailable": unavailable_notes,
        "reasons": reasons,
        "valid_minutes": SIGNAL_VALID_MINUTES,
        "atr_value": atr_value,
        **trade_levels,
    }
