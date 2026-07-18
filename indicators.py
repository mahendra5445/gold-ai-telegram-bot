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

    true_range = pd.concat(
        [tr1, tr2, tr3],
        axis=1
    ).max(axis=1)

    atr = true_range.rolling(period).mean()

    return round(atr.iloc[-1], 2)


def adx(high, low, close, period=14):
    high = pd.Series(high)
    low = pd.Series(low)
    close = pd.Series(close)

    plus_dm = high.diff()
    minus_dm = -low.diff()

    plus_dm = plus_dm.where(
        (plus_dm > minus_dm) & (plus_dm > 0),
        0
    )

    minus_dm = minus_dm.where(
        (minus_dm > plus_dm) & (minus_dm > 0),
        0
    )

    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()

    tr = pd.concat(
        [tr1, tr2, tr3],
        axis=1
    ).max(axis=1)

    atr_value = tr.rolling(period).mean()

    plus_di = (
        100
        * plus_dm.rolling(period).mean()
        / atr_value
    )

    minus_di = (
        100
        * minus_dm.rolling(period).mean()
        / atr_value
    )

    dx = (
        (plus_di - minus_di).abs()
        / (plus_di + minus_di)
    ) * 100

    adx_value = dx.rolling(period).mean()

    return round(adx_value.iloc[-1], 2)
