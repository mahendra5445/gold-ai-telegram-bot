
import pandas as pd

def ema(values, period):
    return round(pd.Series(values).ewm(span=period, adjust=False).mean().iloc[-1], 2)

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

    return {
        "macd": round(macd_line.iloc[-1], 2),
        "signal": round(signal_line.iloc[-1], 2),
        "trend": "Bullish" if macd_line.iloc[-1] > signal_line.iloc[-1] else "Bearish"
    }
