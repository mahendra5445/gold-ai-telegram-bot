import pandas as pd


def ema(values, period):
    return round(
        pd.Series(values).ewm(span=period, adjust=False).mean().iloc[-1], 2
    )


def rsi(values, period=14):
    close = pd.Series(values)

    delta = close.diff()

    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()

    rs = gain / loss

    rsi = 100 - (100 / (1 + rs))

    return round(rsi.iloc[-1], 2)


def macd(values):
    close = pd.Series(values)

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()

    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()

    trend = "Bullish"

    if macd_line.iloc[-1] < signal_line.iloc[-1]:
        trend = "Bearish"

    return {
        "macd": round(macd_line.iloc[-1], 2),
        "signal": round(signal_line.iloc[-1], 2),
        "trend": trend,
    }


def atr(high, low, close, period=14):
    high = pd.Series(high)
    low = pd.Series(low)
    close = pd.Series(close)

    previous_close = close.shift(1)

    tr1 = high - low
    tr2 = (high - previous_close).abs()
    tr3 = (low - previous_close).abs()

    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr_value = true_range.rolling(period).mean()

    return round(atr_value.iloc[-1], 2)


def adx(high, low, close, period=14):
    high = pd.Series(high)
    low = pd.Series(low)
    close = pd.Series(close)

    plus_dm = high.diff()
    minus_dm = -low.diff()

    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)

    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr_value = tr.rolling(period).mean()

    plus_di = 100 * plus_dm.rolling(period).mean() / atr_value
    minus_di = 100 * minus_dm.rolling(period).mean() / atr_value

    dx = ((plus_di - minus_di).abs() / (plus_di + minus_di)) * 100

    adx_value = dx.rolling(period).mean()

    return round(adx_value.iloc[-1], 2)


def vwap(high, low, close, volume):
    high = pd.Series(high)
    low = pd.Series(low)
    close = pd.Series(close)
    volume = pd.Series(volume)

    typical_price = (high + low + close) / 3
    value = (typical_price * volume).cumsum() / volume.cumsum()

    return round(value.iloc[-1], 2)


def bollinger_bands(values, period=20, std_dev=2):
    close = pd.Series(values)

    sma = close.rolling(period).mean()
    std = close.rolling(period).std()

    upper = sma + (std * std_dev)
    lower = sma - (std * std_dev)

    return {
        "upper": round(upper.iloc[-1], 2),
        "middle": round(sma.iloc[-1], 2),
        "lower": round(lower.iloc[-1], 2),
    }


def trend_strength(adx_value):
    if adx_value >= 40:
        return "Very Strong"
    if adx_value >= 25:
        return "Strong"
    if adx_value >= 20:
        return "Moderate"
    return "Weak"


def supertrend(high, low, close, period=10, multiplier=3):
    high = pd.Series(high).reset_index(drop=True)
    low = pd.Series(low).reset_index(drop=True)
    close = pd.Series(close).reset_index(drop=True)

    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()

    hl2 = (high + low) / 2

    upperband = hl2 + (multiplier * atr)
    lowerband = hl2 - (multiplier * atr)

    final_upper = upperband.copy()
    final_lower = lowerband.copy()

    trend = [True] * len(close)

    for i in range(1, len(close)):
        if close.iloc[i] > final_upper.iloc[i - 1]:
            trend[i] = True
        elif close.iloc[i] < final_lower.iloc[i - 1]:
            trend[i] = False
        else:
            trend[i] = trend[i - 1]
            if trend[i] and final_lower.iloc[i] < final_lower.iloc[i - 1]:
                final_lower.iloc[i] = final_lower.iloc[i - 1]
            if (not trend[i]) and final_upper.iloc[i] > final_upper.iloc[i - 1]:
                final_upper.iloc[i] = final_upper.iloc[i - 1]

    return {
        "trend": "Bullish" if trend[-1] else "Bearish",
        "value": round(final_lower.iloc[-1] if trend[-1] else final_upper.iloc[-1], 2),
    }
