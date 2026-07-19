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


def supertrend(high, low, close, period=10, multiplier=3):
    atr_value = atr(high, low, close, period)
    hl2 = (pd.Series(high).iloc[-1] + pd.Series(low).iloc[-1]) / 2
    upper = hl2 + multiplier * atr_value
    lower = hl2 - multiplier * atr_value
    trend = "Bullish" if close[-1] > upper else "Bearish" if close[-1] < lower else "Bullish"
    return {"trend": trend, "value": round(lower if trend=="Bullish" else upper,2)}
