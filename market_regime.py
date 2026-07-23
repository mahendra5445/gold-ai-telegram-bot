"""
Market Regime Detection (Feature #6) — NAYA

Kyun zaroori hai: trend-following filters (EMA stack, Supertrend, MTF)
ranging market mein sabse zyada fake signals dete hain. Price upar-neeche
hilta rehta hai, EMA cross hote rehte hain, aur har baar SL lag jaata hai.

Ye module market ko teen halaton mein baantta hai, aur strategy usi hisaab
se sakht ya narm ho jaati hai.

Teen alag measurements use hote hain (ek akela bharosemand nahi):
  1. ADX          -> directional strength
  2. BB width     -> volatility expand ho rahi hai ya squeeze mein hai
  3. EMA spread   -> EMAs khule hue hain ya aapas mein uljhe hue
"""

import pandas as pd

from indicators import adx, ema


def _bb_width_percentile(close, period=20, lookback=100):
    """
    Aaj ki Bollinger width pichhle `lookback` candles ke muqable kahan hai.
    0.2 = pichhle 80% waqt se tighter (squeeze). 0.8 = expansion.
    """
    s = pd.Series(close)
    mid = s.rolling(period).mean()
    std = s.rolling(period).std()
    width = ((mid + 2 * std) - (mid - 2 * std)) / mid

    recent = width.dropna().iloc[-lookback:]
    if len(recent) < 20:
        return 0.5
    current = width.iloc[-1]
    return float((recent < current).sum() / len(recent))


def detect_regime(close, high, low):
    """
    Returns dict:
      regime          : "Trending" | "Ranging" | "Transition"
      trend_ok        : bool  -- trend-following trade lena theek hai?
      adx             : float
      bb_percentile   : float (0-1)
      ema_spread_pct  : float -- EMA20 aur EMA50 ke beech ka faasla, % mein
      note            : str
    """
    if close is None or len(close) < 100:
        return {
            "regime": "Unknown", "trend_ok": True, "adx": 0.0,
            "bb_percentile": 0.5, "ema_spread_pct": 0.0,
            "note": "not enough candles",
        }

    adx_v = adx(high, low, close)
    bb_pct = _bb_width_percentile(close)

    e20, e50 = ema(close, 20), ema(close, 50)
    price = close[-1]
    ema_spread = abs(e20 - e50) / price * 100 if price else 0.0

    # Teenon signals ko vote karne do
    votes_trend = 0
    votes_range = 0

    # 1. ADX -- NOTE: ab ye sahi Wilder ADX hai, values purane inflated
    #    version se kam aati hain. 20 ek reasonable trend threshold hai.
    if adx_v >= 20:
        votes_trend += 1
    elif adx_v < 15:
        votes_range += 1

    # 2. Bollinger width -- squeeze = range, expansion = trend
    if bb_pct >= 0.60:
        votes_trend += 1
    elif bb_pct <= 0.30:
        votes_range += 1

    # 3. EMA spread -- EMAs chipke hue = koi direction nahi
    if ema_spread >= 0.15:
        votes_trend += 1
    elif ema_spread <= 0.05:
        votes_range += 1

    if votes_trend >= 2:
        regime, trend_ok = "Trending", True
        note = "Trend-following setups theek hain"
    elif votes_range >= 2:
        regime, trend_ok = "Ranging", False
        note = "Ranging market — trend signals yahan sabse zyada fail hote hain"
    else:
        regime, trend_ok = "Transition", True
        note = "Mila-jula — reduced size"

    return {
        "regime": regime,
        "trend_ok": trend_ok,
        "adx": adx_v,
        "bb_percentile": round(bb_pct, 2),
        "ema_spread_pct": round(ema_spread, 3),
        "note": note,
    }
