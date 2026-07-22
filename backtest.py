"""
backtest.py — AI Scalper Pro V5 ke liye honest backtester

Ye aapki HI strategy.py aur risk.py use karta hai. Koi alag logic nahi.
Jo yahan dikhega wohi bot live karega — sirf costs ke saath aur proper
accounting ke saath.

Kyun zaroori hai:
  - Aapka trade_tracker sirf TP3 ko "win" ginta hai. Ye script har trade ka
    REALIZED R (risk multiple) nikalta hai, partial exits ke saath.
  - Spread har trade se subtract hota hai.
  - Sabse important output WIN RATE nahi, EXPECTANCY hai (avg R per trade).
    Expectancy > 0 = strategy paisa banati hai. Win rate 80% bhi ho aur
    expectancy negative ho sakti hai.

Chalane ka tareeqa (repo folder ke andar rakhein):
    python backtest.py --asset gold --days 60
    python backtest.py --asset gold --days 60 --min-score 70 --min-confirmations 10
    python backtest.py --asset gold --days 60 --walk-forward

Note: Yahoo 1m/5m data sirf last ~30-60 din ka deta hai. Isse zyada history
ke liye paid data source chahiye hoga (Dukascopy free tick data ek option hai).
"""

import argparse
import sys
import time
from dataclasses import dataclass, field

import requests

try:
    import strategy
    import risk
    from config import ASSETS
except ImportError:
    sys.exit("ERROR: ye file repo folder ke andar rakhein (strategy.py ke saath).")


# ─────────────────────────── data ───────────────────────────

YF_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0"}


def fetch(symbol: str, interval: str, days: int):
    """Return list of (ts, o, h, l, c, v) — forming candle dropped."""
    r = requests.get(
        YF_URL.format(symbol=symbol),
        params={"interval": interval, "range": f"{days}d"},
        headers=HEADERS, timeout=20,
    )
    r.raise_for_status()
    res = r.json()["chart"]["result"][0]
    ts = res.get("timestamp") or []
    q = res["indicators"]["quote"][0]
    opens = q.get("open") or []
    highs = q.get("high") or []
    lows = q.get("low") or []
    closes = q.get("close") or []
    vols = q.get("volume") or []

    def at(series, i):
        return series[i] if i < len(series) else None

    rows = []
    for i in range(len(ts)):
        o, h, l, c = at(opens, i), at(highs, i), at(lows, i), at(closes, i)
        if None in (o, h, l, c):
            continue
        rows.append((ts[i], o, h, l, c, at(vols, i) or 0))
    return rows[:-1]   # forming candle drop


def resample(rows, factor):
    """1m rows -> factor-minute rows."""
    out = []
    for i in range(0, len(rows) - factor + 1, factor):
        chunk = rows[i:i + factor]
        out.append((
            chunk[0][0], chunk[0][1],
            max(x[2] for x in chunk), min(x[3] for x in chunk),
            chunk[-1][4], sum(x[5] for x in chunk),
        ))
    return out


# ─────────────────────────── trade model ───────────────────────────

@dataclass
class Trade:
    idx: int
    side: str
    entry: float
    sl: float
    tp1: float
    tp2: float
    tp3: float
    risk: float
    hit_tp1: bool = False
    hit_tp2: bool = False
    realized_r: float = 0.0
    remaining: float = 1.0
    closed_at: int | None = None
    outcome: str = ""
    bars_held: int = 0
    path: list = field(default_factory=list)


# Position ka kitna hissa har TP pe band hota hai.
# Ye aapke Telegram messages ke logic se match karta hai
# (TP1 -> partial + SL breakeven, TP2 -> partial + trail, TP3 -> full).
from config import SCALE_OUT as SCALE_OUT_CFG, TP_MULTIPLES as TP_MULTIPLES_CFG


def simulate(trade: Trade, bars, start_i, spread, max_bars, targets=None):
    """
    Bar-by-bar walk-forward. Har bar pe high/low dono check hote hain.
    Conservative: agar ek hi bar mein SL aur TP dono touch ho sakte hain,
    SL pehle maana jaata hai (worst case) -- 5m bar ke andar order kya tha
    ye pata nahi hota.

    `targets` = [(R_multiple, portion), ...]. None do to config wala
    structure use hota hai. Isse TP structures sweep kiye ja sakte hain.
    """
    if targets is None:
        targets = list(zip(TP_MULTIPLES_CFG, SCALE_OUT_CFG))

    is_buy = trade.side == "BUY"
    sl = trade.sl
    filled = [False] * len(targets)

    for j in range(start_i, min(start_i + max_bars, len(bars))):
        _, o, h, l, c, _ = bars[j]
        trade.bars_held = j - start_i + 1

        if (l <= sl) if is_buy else (h >= sl):
            r = (sl - trade.entry) / trade.risk if is_buy else (trade.entry - sl) / trade.risk
            trade.realized_r += r * trade.remaining
            trade.remaining = 0.0
            trade.closed_at = j
            trade.outcome = "BE" if filled[0] else "SL"
            break

        for k, (mult, portion) in enumerate(targets):
            if filled[k]:
                continue
            lvl = trade.entry + trade.risk * mult if is_buy else trade.entry - trade.risk * mult
            reached = (h >= lvl) if is_buy else (l <= lvl)
            if not reached:
                break                      # targets order mein hain
            filled[k] = True
            trade.realized_r += mult * portion
            trade.remaining = round(trade.remaining - portion, 6)
            trade.path.append(f"TP{k+1}")
            if k == 0:
                sl = trade.entry           # breakeven, jaise live bot karta hai

        if trade.remaining <= 1e-9:
            trade.closed_at = j
            trade.outcome = "TP_FULL"
            break
    else:
        j = min(start_i + max_bars, len(bars)) - 1

    if trade.closed_at is None:
        c = bars[j][4]
        r = (c - trade.entry) / trade.risk if is_buy else (trade.entry - c) / trade.risk
        trade.realized_r += r * trade.remaining
        trade.remaining = 0.0
        trade.closed_at = j
        trade.outcome = "EXPIRED"

    trade.hit_tp1 = filled[0]
    trade.realized_r -= (spread / trade.risk)     # round-trip cost, R units
    return trade


# ─────────────────────────── engine ───────────────────────────

def run(asset, days, spread, cooldown_bars, max_bars, overrides, targets=None):
    cfg = ASSETS[asset]
    dec = cfg["decimals"]

    for k, v in overrides.items():
        if v is not None:
            setattr(strategy, k, v)

    print(f"Fetching {cfg['label']} ({cfg['symbol']}) — {days}d of 1m data...")
    m1 = fetch(cfg["symbol"], "1m", min(days, 7))
    if len(m1) < 5000:
        print(f"  1m gave only {len(m1)} bars; using 5m directly for longer history.")
        m5 = fetch(cfg["symbol"], "5m", days)
        m15 = fetch(cfg["symbol"], "15m", days)
        m1 = m5
    else:
        m5 = resample(m1, 5)
        m15 = resample(m1, 15)

    print(f"  bars: 1m={len(m1)}  5m={len(m5)}  15m={len(m15)}")
    if len(m5) < 300:
        sys.exit("Not enough 5m bars to backtest (need 200 warmup + samples).")

    trades = []
    last_signal_bar = -10 ** 9
    open_until = -1

    for i in range(200, len(m5) - 1):
        if i < open_until or (i - last_signal_bar) < cooldown_bars:
            continue

        c5 = [b[4] for b in m5[:i + 1]]
        h5 = [b[2] for b in m5[:i + 1]]
        l5 = [b[3] for b in m5[:i + 1]]
        o5 = [b[1] for b in m5[:i + 1]]
        v5 = [b[5] for b in m5[:i + 1]]
        if sum(v5) == 0:
            v5 = None

        t_now = m5[i][0]
        c1 = [b[4] for b in m1 if b[0] <= t_now][-400:]
        c15 = [b[4] for b in m15 if b[0] <= t_now]
        if len(c1) < 200 or len(c15) < 200:
            continue

        res = strategy.get_signal(c5, h5, l5,
                                  {"1m": c1, "5m": c5, "15m": c15},
                                  v5, o5, decimals=dec, spread=spread)
        if res["signal"] == "NO TRADE":
            continue

        # Entry = agle bar ka open (koi look-ahead nahi)
        entry = m5[i + 1][1]
        lv = risk.calculate_trade(res["signal"], entry, res["atr_value"],
                                  decimals=dec,
                                  session_active=res.get("session_active", True),
                                  spread=spread)
        rsk = abs(lv["entry"] - lv["sl"])
        if rsk <= 0:
            continue

        t = Trade(i, res["signal"], lv["entry"], lv["sl"],
                  lv["tp1"], lv["tp2"], lv["tp3"], rsk)
        simulate(t, m5, i + 1, spread, max_bars, targets)
        trades.append(t)
        last_signal_bar = i
        open_until = t.closed_at

    return trades


def report(trades, label):
    if not trades:
        print("\nKoi trade nahi mila. Thresholds bahut tight hain ya data kam hai.")
        return

    n = len(trades)
    total_r = sum(t.realized_r for t in trades)
    wins = [t for t in trades if t.realized_r > 0]
    losses = [t for t in trades if t.realized_r <= 0]
    expectancy = total_r / n

    # max drawdown in R
    peak = cum = mdd = 0.0
    for t in trades:
        cum += t.realized_r
        peak = max(peak, cum)
        mdd = min(mdd, cum - peak)

    outcomes = {}
    for t in trades:
        outcomes[t.outcome] = outcomes.get(t.outcome, 0) + 1

    print(f"\n{'=' * 58}")
    print(f"  {label}")
    print(f"{'=' * 58}")
    print(f"  Trades taken       : {n}")
    print(f"  Win rate (R > 0)   : {len(wins) / n * 100:.1f}%")
    print(f"  Reached TP1        : {sum(1 for t in trades if t.hit_tp1) / n * 100:.1f}%")
    print(f"  Full target hit    : {sum(1 for t in trades if t.outcome == 'TP_FULL') / n * 100:.1f}%")
    print(f"  Outcomes           : {outcomes}")
    print(f"  Avg bars held      : {sum(t.bars_held for t in trades) / n:.1f}")
    print(f"  {'-' * 54}")
    print(f"  Total R            : {total_r:+.2f}")
    print(f"  EXPECTANCY (R/trd) : {expectancy:+.4f}   <-- ye number matter karta hai")
    print(f"  Max drawdown       : {mdd:.2f} R")
    if losses:
        print(f"  Avg win / avg loss : "
              f"{sum(t.realized_r for t in wins) / max(len(wins), 1):+.2f}R / "
              f"{sum(t.realized_r for t in losses) / len(losses):+.2f}R")
    print(f"{'=' * 58}")

    if expectancy > 0.05:
        print("  Expectancy positive hai. Ab OUT-OF-SAMPLE period pe verify karein")
        print("  (--walk-forward). Ek hi period pe acha result overfitting ho sakta hai.")
    elif expectancy > 0:
        print("  Expectancy bilkul zero ke aas-paas hai — ye noise bhi ho sakta hai.")
        print("  Zyada data aur out-of-sample test ke bina bharosa na karein.")
    else:
        print("  Expectancy NEGATIVE hai. Is settings pe bot paisa kho raha hai.")
        print("  Threshold dheela karne se ye theek NAHI hoga — aur trades = aur loss.")
        print("  Pehle costs ke baad koi bhi combination positive nikalti hai ya nahi, wo dekhein.")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--asset", default="gold", choices=list(ASSETS))
    p.add_argument("--days", type=int, default=30)
    p.add_argument("--spread", type=float, default=None,
                   help="broker spread in price units (gold default 0.25)")
    p.add_argument("--cooldown-bars", type=int, default=3)
    p.add_argument("--max-bars", type=int, default=48,
                   help="trade expiry — kitne 5m bars ke baad forcibly close (48 = 4 hrs)")
    p.add_argument("--min-score", type=int, default=None)
    p.add_argument("--min-confirmations", type=int, default=None)
    p.add_argument("--walk-forward", action="store_true",
                   help="pehle aadhe data pe result, doosre aadhe pe alag se — overfit check")
    p.add_argument("--sweep-tp", action="store_true",
                   help="alag TP structures test karo (TP3 hata ke bhi)")
    p.add_argument("--sweep-sl", action="store_true",
                   help="SL multiplier ko 1.0 se 4.0 tak test karo — "
                        "khud dekho tight SL ka asli asar kya hai")
    a = p.parse_args()

    spread = a.spread if a.spread is not None else ASSETS[a.asset].get("spread", 0.0)

    if a.sweep_tp:
        structures = [
            ("A. Abhi (3 targets)",      [(2.5, 0.50), (4.0, 0.25), (6.0, 0.25)]),
            ("B. TP3 hataya (2 target)", [(2.5, 0.50), (4.0, 0.50)]),
            ("C. Sab TP1 pe band",       [(2.5, 1.00)]),
            ("D. Kareeb targets",        [(1.5, 0.50), (2.5, 0.50)]),
            ("E. Sab 2R pe band",        [(2.0, 1.00)]),
        ]
        print(f"\n  TP structure sweep — {ASSETS[a.asset]['label']}, "
              f"{a.days}d, spread={spread}\n")
        print(f"  {'Structure':<26}{'trades':>7}{'win%':>7}{'expectancy':>13}{'total R':>10}")
        print("  " + "-" * 63)
        for name, tg in structures:
            ts = run(a.asset, a.days, spread, a.cooldown_bars, a.max_bars,
                     {"MIN_SCORE": a.min_score,
                      "MIN_TOTAL_CONFIRMATIONS": a.min_confirmations}, targets=tg)
            if not ts:
                print(f"  {name:<26}{0:>7}      —            —         —")
                continue
            tot = sum(t.realized_r for t in ts)
            wr = sum(1 for t in ts if t.realized_r > 0) / len(ts) * 100
            print(f"  {name:<26}{len(ts):>7}{wr:>6.1f}%{tot/len(ts):>+12.4f}{tot:>+9.2f}")
        print("\n  Sabse upar EXPECTANCY wala structure chunein, win% wala nahi.\n")
        return

    if a.sweep_sl:
        import risk as risk_mod
        print(f"\n  SL multiplier sweep — {ASSETS[a.asset]['label']}, "
              f"{a.days}d, spread={spread}\n")
        print(f"  {'SL mult':>8} {'trades':>7} {'win%':>7} {'expectancy':>12} {'total R':>9}")
        print("  " + "-" * 48)
        for mult in (1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0):
            risk_mod.SL_ATR_MULT = mult
            ts = run(a.asset, a.days, spread, a.cooldown_bars, a.max_bars,
                     {"MIN_SCORE": a.min_score,
                      "MIN_TOTAL_CONFIRMATIONS": a.min_confirmations})
            if not ts:
                print(f"  {mult:>8.1f} {0:>7}       —            —         —")
                continue
            tot = sum(t.realized_r for t in ts)
            wr = sum(1 for t in ts if t.realized_r > 0) / len(ts) * 100
            print(f"  {mult:>8.1f} {len(ts):>7} {wr:>6.1f}% "
                  f"{tot/len(ts):>+11.4f} {tot:>+8.2f}")
        print("\n  Dhyan dein: SL chhota karne se win% girta hai. Expectancy "
              "column dekhein,\n  win% nahi — wahi batata hai net mein faayda "
              "hua ya nuqsaan.\n")
        return

    t0 = time.time()
    trades = run(a.asset, a.days, spread, a.cooldown_bars, a.max_bars,
                 {"MIN_SCORE": a.min_score, "MIN_TOTAL_CONFIRMATIONS": a.min_confirmations})

    tag = (f"{ASSETS[a.asset]['label']} | {a.days}d | spread={spread} | "
           f"score>={a.min_score or strategy.MIN_SCORE} | "
           f"conf>={a.min_confirmations or strategy.MIN_TOTAL_CONFIRMATIONS}")

    if a.walk_forward and len(trades) > 10:
        mid = len(trades) // 2
        report(trades[:mid], "IN-SAMPLE (pehla aadha)")
        report(trades[mid:], "OUT-OF-SAMPLE (doosra aadha)")
        print("\n  Agar out-of-sample expectancy in-sample se bahut kam hai,")
        print("  to settings us period pe fit ho gayi hai — live pe kaam nahi karegi.")
    else:
        report(trades, tag)

    print(f"\n  ({time.time() - t0:.1f}s)")


if __name__ == "__main__":
    main()
