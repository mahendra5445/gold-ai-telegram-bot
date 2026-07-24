import math

from config import (
    SL_ATR_MULT,
    MIN_SL_PCT,
    LOW_LIQUIDITY_FACTOR,
    TP_MULTIPLES,
)


def calculate_trade(signal, price, atr, decimals=2, session_active=True,
                    spread=0.0, sl_mult=None, tp_multiples=None,
                    min_sl_pct=None):
    """
    ATR-based SL aur R-multiple TPs.

    Naya kya hai:
      - Multipliers ab config.py se aate hain (hardcoded nahi), aur
        arguments se override ho sakte hain -- taaki backtest inhe sweep
        kar sake bina file edit kiye.
      - `spread` ab risk mein add hota hai. Broker ka spread ek REAL cost
        hai jo pehle kahin count hi nahi hota tha: gold pe $0.25 spread
        $3.60 ke minimum SL ka ~7% hai. Ab RR jo dikhta hai wo cost ke
        baad ka honest number hai.
      - `risk_per_unit` return hota hai taaki tracker realized R nikaal sake.
    """

    if signal not in ["BUY", "SELL"]:
        return {
            "entry": None, "sl": None, "tp1": None, "tp2": None, "tp3": None,
            "targets": [], "risk_reward": "-", "risk_per_unit": None,
        }

    sl_mult = SL_ATR_MULT if sl_mult is None else sl_mult
    tp_multiples = TP_MULTIPLES if tp_multiples is None else tp_multiples

    entry = round(price, decimals)

    session_factor = 1.0 if session_active else LOW_LIQUIDITY_FACTOR
    effective_mult = sl_mult * session_factor

    if atr is None or (isinstance(atr, float) and math.isnan(atr)):
        atr = 0

    risk = atr * effective_mult

    # Minimum SL floor -- quiet market mein ATR itna chhota ho sakta hai ki
    # SL spread/noise ke andar hi aa jaaye aur turant hit ho.
    floor_pct = MIN_SL_PCT if min_sl_pct is None else min_sl_pct
    min_risk = price * floor_pct * session_factor
    risk = max(risk, min_risk)

    # Spread ko risk mein jodo -- aap entry pe hi spread ke barabar peeche
    # hote hain, to asli stop distance utni hi zyada hai.
    risk = round(risk + spread, decimals)

    # FIX: pehle `r1, r2, r3 = tp_multiples` tha -- exactly 3 targets zaroori
    # the, warna crash. Ab kitne bhi targets chal jaate hain (1, 2, ya 3),
    # taaki single-TP structure config se set kiya ja sake.
    sign = 1 if signal == "BUY" else -1
    sl = round(entry - sign * risk, decimals)
    tps = [round(entry + sign * risk * m, decimals) for m in tp_multiples]

    # Purane keys backward-compatible rakhe -- jo target hai hi nahi wo None.
    tp1 = tps[0] if len(tps) > 0 else None
    tp2 = tps[1] if len(tps) > 1 else None
    tp3 = tps[2] if len(tps) > 2 else None

    actual_risk = abs(entry - sl)
    # RR ab spread ke baad ka net hai (round-trip cost = 1 spread).
    net_reward = abs(tp1 - entry) - spread
    rr = round(net_reward / actual_risk, 2) if actual_risk > 0 else 0

    return {
        "entry": entry,
        "sl": sl,
        "tp1": tp1,
        "tp2": tp2,
        "tp3": tp3,
        "targets": tps,
        "risk_reward": f"1:{rr}",
        "risk_per_unit": actual_risk,
    }
