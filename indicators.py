import pandas as pd


def ema(values, period):
    return round(pd.Series(values).ewm(span=period, adjust=False).mean().iloc[-1], 2)


def rsi(values, period=14):
    close = pd.Series(values)
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss
    return round((100 - (100 / (1 + rs))).iloc[-1], 2)


def macd(values):
    close = pd.Series(values)
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal = macd_line.ewm(span=9, adjust=False).mean()
    return {
        "macd": round(macd_line.iloc[-1], 2),
        "signal": round(signal.iloc[-1], 2),
        "trend": "Bullish" if macd_line.iloc[-1] >= signal.iloc[-1] else "Bearish",
    }


def atr(high, low, close, period=14):
    high = pd.Series(high)
    low = pd.Series(low)
    close = pd.Series(close)
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs(),
    ], axis=1).max(axis=1)
    return round(tr.rolling(period).mean().iloc[-1], 2)


def adx(high, low, close, period=14):
    high = pd.Series(high)
    low = pd.Series(low)
    close = pd.Series(close)
    plus_dm = high.diff().clip(lower=0)
    minus_dm = (-low.diff()).clip(lower=0)
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs(),
    ], axis=1).max(axis=1)
    atrv = tr.rolling(period).mean()
    plus = 100 * plus_dm.rolling(period).mean() / atrv
    minus = 100 * minus_dm.rolling(period).mean() / atrv
    dx = ((plus - minus).abs() / (plus + minus)) * 100
    return round(dx.rolling(period).mean().iloc[-1], 2)


def trend_strength(adx_value):
    if adx_value >= 40:
        return "Very Strong"
    if adx_value >= 25:
        return "Strong"
    if adx_value >= 20:
        return "Moderate"
    return "Weak"


def vwap(high, low, close, volume):
    tp = (pd.Series(high) + pd.Series(low) + pd.Series(close)) / 3
    vol = pd.Series(volume)
    return round(((tp * vol).cumsum() / vol.cumsum()).iloc[-1], 2)


def bollinger_bands(values, period=20, std_dev=2):
    s = pd.Series(values)
    mid = s.rolling(period).mean()
    std = s.rolling(period).std()
    return {
        "upper": round((mid + std * std_dev).iloc[-1], 2),
        "middle": round(mid.iloc[-1], 2),
        "lower": round((mid - std * std_dev).iloc[-1], 2),
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
    high_s = pd.Series(high)
    low_s = pd.Series(low)
    close_s = pd.Series(close)
    tr = pd.concat([
        high_s - low_s,
        (high_s - close_s.shift()).abs(),
        (low_s - close_s.shift()).abs(),
    ], axis=1).max(axis=1)
    atr_series = tr.rolling(atr_period).mean()
    return round(atr_series.rolling(ma_period).mean().iloc[-1], 2)


def supertrend(high, low, close, period=10, multiplier=3):
    high_s = pd.Series(high)
    low_s = pd.Series(low)
    close_s = pd.Series(close)

    tr = pd.concat([
        high_s - low_s,
        (high_s - close_s.shift()).abs(),
        (low_s - close_s.shift()).abs(),
    ], axis=1).max(axis=1)
    atr_series = tr.rolling(period).mean()

    hl2 = (high_s + low_s) / 2
    basic_upper = hl2 + multiplier * atr_series
    basic_lower = hl2 - multiplier * atr_series

    start = atr_series.first_valid_index()
    if start is None or start >= len(close_s) - 1:
        return {"trend": "Bearish", "value": round(close[-1], 2)}

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
    return {"trend": last_trend, "value": round(last_value, 2)}
