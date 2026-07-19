"""
strategy.py

Placeholder template for Gold AI Telegram Bot.
Replace with the final implementation that matches your project.
"""

from indicators import ema, rsi, macd

def get_signal(df):
    """
    Basic example.
    Returns:
        dict with signal information.
    """
    if df is None or len(df) < 200:
        return {
            "signal": "NO TRADE",
            "confidence": 0,
            "reason": "Not enough candles"
        }

    ema20 = ema(df["close"], 20).iloc[-1]
    ema50 = ema(df["close"], 50).iloc[-1]
    ema200 = ema(df["close"], 200).iloc[-1]

    if ema20 > ema50 > ema200:
        signal = "BUY"
        confidence = 70
    elif ema20 < ema50 < ema200:
        signal = "SELL"
        confidence = 70
    else:
        signal = "NO TRADE"
        confidence = 40

    return {
        "signal": signal,
        "confidence": confidence,
        "ema20": float(ema20),
        "ema50": float(ema50),
        "ema200": float(ema200),
    }
