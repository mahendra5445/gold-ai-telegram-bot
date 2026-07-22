import pandas as pd
import numpy as np


def ema(values, period):
    return round(pd.Series(values).ewm(span=period, adjust=False).mean().iloc[-1], 6)


def _wilder(series, period):
    """Wilder's smoothing = EWM with alpha 1/period. MT5/TradingView isi ko
    use karte hain. Pehle yahan simple rolling().mean() tha, isliye bot ke
    RSI/ATR/ADX chart pe dikhne wale values se match nahi karte the."""
    return series.ewm(alpha=1 / period, adjust=False).mean()


def rsi(values, period=14):
    """FIX: Wilder smoothing (pehle simple rolling mean tha -> MT5 se mismatch)."""
    close = pd.Series(values)
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)

    avg_gain = _wilder(gain, period)
    avg_loss = _wilder(loss, period)

    rs = avg_gain / avg_loss.replace(0, np.nan)
    value = (100 - (100 / (1 + rs))).iloc[-1]

    if pd.isna(value):
        # avg_loss = 0 matlab sirf up-moves -> RSI 100. Dono zero -> flat -> 50.
        return 100.0 if avg_gain.iloc[-1] > 0 else 50.0
    return round(float(value), 2)


def macd(values):
    close = pd.Series(values)
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal = macd_line.ewm(span=9, adjust=False).mean()
    return {
        "macd": round(macd_line.iloc[-1], 6),
        "signal": round(signal.iloc[-1], 6),
        "trend": "Bullish" if macd_line.iloc[-1] >= signal.iloc[-1] else "Bearish",
    }


def _true_range(high, low, close):
    high, low, close = pd.Series(high), pd.Series(low), pd.Series(close)
    return pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs(),
    ], axis=1).max(axis=1)


def atr(high, low, close, period=14):
    """FIX: Wilder smoothing instead of rolling mean."""
    value = _wilder(_true_range(high, low, close), period).iloc[-1]
    return round(float(value), 6) if not pd.isna(value) else 0.0


def adx(high, low, close, period=14):
    """
    FIX (critical): purana code Wilder ka directional-movement rule hi skip
    kar raha tha --

        plus_dm  = high.diff().clip(lower=0)
        minus_dm = (-low.diff()).clip(lower=0)

    Asli rule: +DM sirf tab count hota hai jab up-move DOWN-move se bada ho
    (aur ulta bhi) -- warna 0. Purane code mein dono ek saath count ho rahe
    the, isliye ADX bahut inflated aata tha (same data pe 51.96 vs sahi
    33.09), aur `adx >= 22` gate pure noise pe bhi 143/200 baar pass ho
    jaata tha. Ab sahi rule + Wilder smoothing.

    NOTE: values ab kaafi kam aayenge. ADX_MIN (strategy.py) isi hisaab se
    dobara calibrate karna hoga -- backtest se, guess se nahi.
    """
    high, low, close = pd.Series(high), pd.Series(low), pd.Series(close)

    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = pd.Series(
        np.where((up_move > down_move) & (up_move > 0), up_move, 0.0),
        index=high.index,
    )
    minus_dm = pd.Series(
        np.where((down_move > up_move) & (down_move > 0), down_move, 0.0),
        index=high.index,
    )

    atr_w = _wilder(_true_range(high, low, close), period)
    safe_atr = atr_w.replace(0, np.nan)

    plus_di = 100 * _wilder(plus_dm, period) / safe_atr
    minus_di = 100 * _wilder(minus_dm, period) / safe_atr

    denom = (plus_di + minus_di).replace(0, np.nan)
    dx = ((plus_di - minus_di).abs() / denom) * 100
    value = _wilder(dx.fillna(0), period).iloc[-1]

    return round(float(value), 2) if not pd.isna(value) else 0.0


def trend_strength(adx_value):
    if adx_value >= 40:
        return "Very Strong"
    if adx_value >= 25:
        return "Strong"
    if adx_value >= 20:
        return "Moderate"
    return "Weak"


def vwap(high, low, close, volume, session_bars=None):
    """
    FIX: pehle cumsum() poore 5-din ke array pe chalta tha -- 5-day cumulative
    VWAP ka koi trading matlab nahi hota. Asli VWAP session pe anchor hota hai.
    `session_bars` = kitni recent candles ek session maani jaayein
    (5m candles pe 288 = 24 ghante).

    Ab volume na hone pe None return karta hai (pehle caller `price` set kar
    deta tha jisse `price > vwap` hamesha False ho jaata tha).
    """
    tp = (pd.Series(high) + pd.Series(low) + pd.Series(close)) / 3
    vol = pd.Series(volume)

    if session_bars:
        tp = tp.iloc[-session_bars:]
        vol = vol.iloc[-session_bars:]

    total_vol = vol.sum()
    if total_vol <= 0:
        return None
    return round(float((tp * vol).sum() / total_vol), 6)


def bollinger_bands(values, period=20, std_dev=2):
    s = pd.Series(values)
    mid = s.rolling(period).mean()
    std = s.rolling(period).std()
    return {
        "upper": round((mid + std * std_dev).iloc[-1], 6),
        "middle": round(mid.iloc[-1], 6),
        "lower": round((mid - std * std_dev).iloc[-1], 6),
    }


def bollinger_signal(close, high, low, period=20, std_dev=2):
    bb = bollinger_bands(close, period, std_dev)
    last_close, last_low, last_high = close[-1], low[-1], high[-1]

    if last_low <= bb["lower"] and last_close > bb["lower"]:
        return "Bullish Bounce"
    if last_high >= bb["upper"] and last_close < bb["upper"]:
        return "Bearish Rejection"
    return "None"


def atr_moving_average(high, low, close, atr_period=14, ma_period=20):
    """ATR series ka apna average -- volatility expand ho rahi hai ya contract."""
    atr_series = _wilder(_true_range(high, low, close), atr_period)
    value = atr_series.rolling(ma_period).mean().iloc[-1]
    return round(float(value), 6) if not pd.isna(value) else 0.0


def supertrend(high, low, close, period=10, multiplier=3):
    """Stateful Supertrend. ATR ab Wilder-smoothed hai (baaki logic same)."""
    high_s, low_s, close_s = pd.Series(high), pd.Series(low), pd.Series(close)
    atr_series = _wilder(_true_range(high_s, low_s, close_s), period)

    hl2 = (high_s + low_s) / 2
    basic_upper = hl2 + multiplier * atr_series
    basic_lower = hl2 - multiplier * atr_series

    start = atr_series.first_valid_index()
    if start is None or start >= len(close_s) - 1:
        return {"trend": "Neutral", "value": round(close[-1], 6)}

    final_upper = basic_upper.copy()
    final_lower = basic_lower.copy()
    trend = ["Bullish"] * len(close_s)
    trend[start] = "Bullish" if close_s.iloc[start] >= hl2.iloc[start] else "Bearish"

    for i in range(start + 1, len(close_s)):
        if basic_upper.iloc[i] < final_upper.iloc[i - 1] or close_s.iloc[i - 1] > final_upper.iloc[i - 1]:
            final_upper.iloc[i] = basic_upper.iloc[i]
        else:
            final_upper.iloc[i] = final_upper.iloc[i - 1]

        if basic_lower.iloc[i] > final_lower.iloc[i - 1] or close_s.iloc[i - 1] < final_lower.iloc[i - 1]:
            final_lower.iloc[i] = basic_lower.iloc[i]
        else:
            final_lower.iloc[i] = final_lower.iloc[i - 1]

        if trend[i - 1] == "Bullish":
            trend[i] = "Bearish" if close_s.iloc[i] < final_lower.iloc[i] else "Bullish"
        else:
            trend[i] = "Bullish" if close_s.iloc[i] > final_upper.iloc[i] else "Bearish"

    last_trend = trend[-1]
    last_value = final_lower.iloc[-1] if last_trend == "Bullish" else final_upper.iloc[-1]
    return {"trend": last_trend, "value": round(last_value, 6)}
