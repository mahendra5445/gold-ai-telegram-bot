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
import bisect
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



# ─────────────────────── CSV LOADER (offline mode) ───────────────────────

def load_csv(path):
    """
    Historical data CSV se padho -- internet ki zaroorat nahi.

    Ye formats apne aap pehchaan leta hai:
      MT5 export   : <DATE><TAB><TIME><TAB><OPEN><TAB><HIGH>...
      MT4 export   : 2024.01.15,09:30,2030.5,2031.2,2029.8,2030.9,120
      TradingView  : time,open,high,low,close,Volume
      Generic      : koi bhi header jismein open/high/low/close ho

    Separator (comma / tab / semicolon) khud detect hota hai.
    Returns: [(index, open, high, low, close, volume), ...]
    """
    import csv as _csv

    with open(path, "r", encoding="utf-8-sig", errors="replace") as fh:
        sample = fh.read(8192)
        fh.seek(0)
        try:
            sep = _csv.Sniffer().sniff(sample, delimiters=",\t;").delimiter
        except Exception:
            sep = "\t" if "\t" in sample else ","
        rows = [r for r in _csv.reader(fh, delimiter=sep) if r]

    if not rows:
        sys.exit(f"CSV khaali hai: {path}")

    header = [h.strip().lower().lstrip("<").rstrip(">") for h in rows[0]]
    has_header = any(k in header for k in ("open", "high", "low", "close"))

    if has_header:
        idx = {}
        for want in ("open", "high", "low", "close", "volume", "vol", "tickvol"):
            for i, h in enumerate(header):
                if h == want or h.endswith(want):
                    idx.setdefault(want, i)
        o_i, h_i = idx.get("open"), idx.get("high")
        l_i, c_i = idx.get("low"), idx.get("close")
        v_i = idx.get("volume", idx.get("vol", idx.get("tickvol")))
        if None in (o_i, h_i, l_i, c_i):
            sys.exit(f"CSV mein open/high/low/close columns nahi mile. "
                     f"Header dikha: {header}")
        data_rows = rows[1:]
    else:
        first = rows[0]
        nums = []
        for i, v in enumerate(first):
            try:
                float(v); nums.append(i)
            except ValueError:
                pass
        if len(nums) < 4:
            sys.exit("CSV samajh nahi aayi. Header ke saath export karein.")
        o_i, h_i, l_i, c_i = nums[0], nums[1], nums[2], nums[3]
        v_i = nums[4] if len(nums) > 4 else None
        data_rows = rows

    out, skipped = [], 0
    for n, r in enumerate(data_rows):
        try:
            o = float(r[o_i]); h = float(r[h_i])
            l = float(r[l_i]); c = float(r[c_i])
            v = float(r[v_i]) if v_i is not None and v_i < len(r) and r[v_i] else 0.0
            if h < l or o <= 0 or c <= 0:
                skipped += 1
                continue
            out.append((n, o, h, l, c, v))
        except (ValueError, IndexError):
            skipped += 1
            continue

    if len(out) < 300:
        sys.exit(f"Sirf {len(out)} valid candles mile -- kam se kam 300 chahiye.")

    print(f"  CSV loaded: {len(out)} candles"
          + (f" ({skipped} rows skipped)" if skipped else ""))
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
    atr: float = 0.0          # NAYA: trailing stop ke liye chahiye
    hit_tp1: bool = False
    hit_tp2: bool = False
    trail_active: bool = False
    realized_r: float = 0.0
    remaining: float = 1.0
    closed_at: int | None = None
    outcome: str = ""
    bars_held: int = 0
    path: list = field(default_factory=list)


# Position ka kitna hissa har TP pe band hota hai.
from config import (SCALE_OUT as SCALE_OUT_CFG,
                    TP_MULTIPLES as TP_MULTIPLES_CFG,
                    TRAILING_ENABLED, TRAILING_ATR_MULT, TRAILING_START_R,
                    TRADE_EXPIRY_MINUTES)


def _trail_sl(trade: Trade, sl: float, price: float) -> float:
    """
    Live bot ka ATR trailing stop, hu-ba-hu.

    KYUN ZAROORI HAI: pehle backtest trailing simulate karta hi nahi tha --
    sirf TP1 ke baad breakeven. Lekin live pe TRAILING_ENABLED=True hai.
    Yaani backtest ek ALAG strategy test kar raha tha us se jo bot chalata
    hai. Us se nikla har number live pe bekaar tha.

    trade_tracker.update_trailing_stop() se rules copy kiye gaye hain:
      - sirf TRAILING_START_R profit ke baad
      - SL kabhi ulti taraf nahi jaata
      - TP1 ke baad breakeven se neeche nahi
    """
    if not TRAILING_ENABLED or not trade.atr or trade.atr <= 0:
        return sl
    if trade.risk <= 0:
        return sl

    is_buy = trade.side == "BUY"
    r_now = ((price - trade.entry) if is_buy else (trade.entry - price)) / trade.risk
    if r_now < TRAILING_START_R:
        return sl

    gap = trade.atr * TRAILING_ATR_MULT
    cand = price - gap if is_buy else price + gap

    if trade.hit_tp1:
        cand = max(cand, trade.entry) if is_buy else min(cand, trade.entry)

    improved = cand > sl if is_buy else cand < sl
    if not improved:
        return sl

    trade.trail_active = True
    return cand


def simulate(trade: Trade, bars, start_i, spread, max_bars, targets=None,
             slippage=0.0):
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
            if filled[0]:
                trade.outcome = "BE"
            elif trade.trail_active:
                # Trail se nikla -- ye raw SL nahi hai, R positive ho sakta
                # hai. Alag ginna zaroori hai warna "SL%" jhootha dikhega.
                trade.outcome = "TRAIL"
            else:
                trade.outcome = "SL"
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

        # Trail SL bar ke CLOSE pe -- events ke BAAD.
        # Ulta karne se ek hi bar ka high SL ko upar kheench deta aur usi
        # bar ka low us naye SL se takra kar jhoota stop-out banata.
        sl = _trail_sl(trade, sl, c)
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

    # COSTS. Spread ek baar (buy at ask, sell at bid = ek crossing).
    # Slippage DO baar -- entry pe bhi, exit pe bhi. Gold scalping mein ye
    # asli kharcha hai aur pehle iska koi hisaab hi nahi tha.
    trade.realized_r -= (spread + 2.0 * slippage) / trade.risk
    return trade


# ─────────────────────────── engine ───────────────────────────

_DATA_CACHE: dict = {}


def load_data(asset, days, csv_path=None, csv_tf=1, quiet=False, tf_mult=1):
    """
    Data ek hi baar load karo, phir cache se do.

    NAYA: pehle har run() call apna data dobara fetch karti thi. Grid search
    mein wo 30+ baar Yahoo ko hit karta -- dheema, aur rate-limit ka khatra.
    """
    key = (asset, days, csv_path, csv_tf, tf_mult)
    if key in _DATA_CACHE:
        return _DATA_CACHE[key]

    cfg = ASSETS[asset]

    if csv_path:
        if not quiet:
            print(f"Loading {csv_path} (offline mode — no network needed)...")
        base = load_csv(csv_path)
        if csv_tf == 1:
            # tf_mult = signal timeframe scaler. 1 -> 1m/5m/15m (default,
            # gold ke liye). 3 -> 3m/15m/45m. Poora triple saath scale hota
            # hai taaki MTF ka rishta (1:5:15) waisa hi rahe.
            m1 = base if tf_mult == 1 else resample(base, tf_mult)
            m5 = resample(base, 5 * tf_mult)
            m15 = resample(base, 15 * tf_mult)
        elif csv_tf == 5:
            m1, m5, m15 = base, base, resample(base, 3)
            if tf_mult != 1:
                sys.exit("--tf-mult sirf 1-minute CSV ke saath chalega")
        else:
            sys.exit("--csv-timeframe sirf 1 ya 5 ho sakta hai")
    else:
        if not quiet:
            print(f"Fetching {cfg['label']} ({cfg['symbol']}) — {days}d of 1m data...")
        m1 = fetch(cfg["symbol"], "1m", min(days, 7))
        if len(m1) < 5000:
            # Yahoo ne 1m theek se nahi diya. Yahan 5m ko "1m" bana kar
            # aage bhejna PEHLE chupchaap hota tha -- live bot asli 1m
            # dekhta hai, to backtest aur live alag data pe chalte the.
            # Ab kam se kam saaf warning milti hai.
            print(f"  ⚠️  1m gave only {len(m1)} bars — falling back to 5m.")
            print(f"      MTF check ab live jaisa NAHI hai. Bharosemand "
                  f"result ke liye --csv se 1m history dein.")
            m5 = fetch(cfg["symbol"], "5m", days)
            m15 = fetch(cfg["symbol"], "15m", days)
            m1 = m5
        else:
            m5, m15 = resample(m1, 5), resample(m1, 15)

    if not quiet:
        print(f"  bars: 1m={len(m1)}  5m={len(m5)}  15m={len(m15)}")
    if len(m5) < 300:
        sys.exit("Not enough 5m bars to backtest (need 200 warmup + samples).")

    _DATA_CACHE[key] = (m1, m5, m15)
    return m1, m5, m15


def run(asset, days, spread, cooldown_bars, max_bars, overrides,
        targets=None, csv_path=None, csv_tf=1, slippage=0.0,
        m5_slice=None, quiet=False, tf_mult=1):
    cfg = ASSETS[asset]
    dec = cfg["decimals"]
    min_sl_pct = cfg.get("min_sl_pct")

    for k, v in overrides.items():
        if v is not None:
            setattr(strategy, k, v)

    m1, m5, m15 = load_data(asset, days, csv_path, csv_tf, quiet=quiet,
                            tf_mult=tf_mult)
    if m5_slice is not None:
        m5 = m5_slice

    return _engine(m1, m5, m15, cfg, dec, spread, cooldown_bars,
                   max_bars, targets, slippage, min_sl_pct)


def _volume_usable(vols) -> bool:
    """
    Volume series asli hai ya dikhawa?

    KYUN: MT5 se export ki gayi CSV mein aakhri column aksar tick volume
    nahi hota -- XAUUSD1.csv mein wo har row pe 1 hai, XAUUSD5.csv mein 5
    (yaani timeframe ka marker). Purana check sirf `sum(v) == 0` dekhta tha,
    to ye constant series "asli volume" gini jaati thi.

    Us se hota ye: strategy ka volume check (VOLUME_MIN_RATIO = 0.85) hamesha
    pass karta -- ratio hamesha 1.0 -- aur uska 9% weight MUFT mil jaata.
    Live pe Yahoo forex spot ka volume 0 aata hai, wahan wo weight HATA kar
    baaki weights renormalize hote hain. Yaani backtest har trade ko 9 extra
    points de raha hota jo live mein milte hi nahi.

    Ab constant/near-constant series ko bhi "no data" mana jaata hai.
    """
    if not vols:
        return False
    total = sum(vols)
    if total <= 0:
        return False
    if len(set(vols)) <= 5:
        return False
    mean = total / len(vols)
    if mean <= 0:
        return False
    var = sum((v - mean) ** 2 for v in vols) / len(vols)
    return (var ** 0.5) / mean >= 0.10      # asli volume ka CV 0.5-1.5 hota hai


# Strategy ko poori history ki zaroorat nahi -- EMA200/ADX/VWAP sab is
# window ke andar converge ho jaate hain. Purana code har bar pe list ko
# shuru se kaat kar deta tha (O(n^2)); 1 saal ke data pe wo ghanton chalta.
CALC_WINDOW = 400


def _engine(m1, m5, m15, cfg, dec, spread, cooldown_bars, max_bars,
            targets, slippage=0.0, min_sl_pct=None):
    trades = []
    last_signal_bar = -10 ** 9
    open_until = -1

    # Sab kuch EK baar nikaalo, phir har bar pe sirf slice lo.
    O5 = [b[1] for b in m5]; H5 = [b[2] for b in m5]
    L5 = [b[3] for b in m5]; C5 = [b[4] for b in m5]; V5 = [b[5] for b in m5]
    C1 = [b[4] for b in m1]; T1 = [b[0] for b in m1]
    C15 = [b[4] for b in m15]; T15 = [b[0] for b in m15]

    vol_ok = _volume_usable(V5)
    if not vol_ok:
        print("  note: volume data bekaar hai (constant ya zero) — "
              "volume checks off, bilkul live jaise.")

    for i in range(200, len(m5) - 1):
        if i < open_until or (i - last_signal_bar) < cooldown_bars:
            continue

        lo = max(0, i + 1 - CALC_WINDOW)
        c5 = C5[lo:i + 1]; h5 = H5[lo:i + 1]
        l5 = L5[lo:i + 1]; o5 = O5[lo:i + 1]
        v5 = V5[lo:i + 1] if vol_ok else None

        t_now = m5[i][0]
        # bisect -- pehle yahan poori m1 list har bar pe scan hoti thi
        j1 = bisect.bisect_right(T1, t_now)
        j15 = bisect.bisect_right(T15, t_now)
        c1 = C1[max(0, j1 - 400):j1]
        c15 = C15[max(0, j15 - CALC_WINDOW):j15]
        if len(c1) < 200 or len(c15) < 200:
            continue

        res = strategy.get_signal(c5, h5, l5,
                                  {"1m": c1, "5m": c5, "15m": c15},
                                  v5, o5, decimals=dec, spread=spread,
                                  min_sl_pct=min_sl_pct)
        if res["signal"] == "NO TRADE":
            continue

        # Entry = agle bar ka open (koi look-ahead nahi)
        entry = m5[i + 1][1]
        lv = risk.calculate_trade(res["signal"], entry, res["atr_value"],
                                  decimals=dec,
                                  session_active=res.get("session_active", True),
                                  spread=spread, min_sl_pct=min_sl_pct)
        rsk = abs(lv["entry"] - lv["sl"])
        if rsk <= 0:
            continue

        t = Trade(i, res["signal"], lv["entry"], lv["sl"],
                  lv["tp1"], lv["tp2"], lv["tp3"], rsk,
                  atr=float(res.get("atr_value") or 0.0))
        simulate(t, m5, i + 1, spread, max_bars, targets, slippage)
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



# ─────────────────── ASLI OUT-OF-SAMPLE SEARCH ───────────────────

MIN_TRADES_TO_TRUST = 30


def _summary(trades):
    if not trades:
        return None
    n = len(trades)
    tot = sum(t.realized_r for t in trades)
    return {
        "n": n,
        "total_r": tot,
        "expectancy": tot / n,
        "win_rate": sum(1 for t in trades if t.realized_r > 0) / n * 100,
    }


def oos_search(a, spread, train_frac=0.6, grid="quick"):
    """
    Ye wo hai jo `--walk-forward` HONE ka daawa karta tha par karta nahi tha.

    Purana --walk-forward: poora backtest EK settings pe chalao, phir trades
    ki list ko aadha-aadha kaat kar do report chhaap do. Kuch tune hi nahi
    hota tha -- wo stability check tha, overfit check nahi. Aur --sweep-tp /
    --sweep-sl POORE data pe best combo dhoondte the, jiske baad verify karne
    ko koi bacha hua period hi nahi tha. Us workflow mein overfit hona
    guarantee tha.

    Ab: TRAIN period pe grid search -> best combo chuno -> us EK combo ko
    TEST period pe chalao jise search ne kabhi dekha hi nahi.

    Test ka number hi wo hai jo live se milta-julta hoga. Train ka number
    hamesha khoobsurat hota hai -- wo aapne khud chun kar banaya hai.
    """
    m1, m5, m15 = load_data(a.asset, a.days, a.csv, a.csv_timeframe)
    split = int(len(m5) * train_frac)
    if split < 500 or (len(m5) - split) < 500:
        sys.exit(f"Data kam hai OOS ke liye (5m bars={len(m5)}). "
                 f"--days badhayein ya --csv se lambi history dein.")

    train_m5 = m5[:split]
    test_m5 = m5[split - 200:]        # 200 bars warmup, phir naya period

    if grid == "full":
        scores = (55, 62, 70, 78)
        sl_mults = (1.5, 2.0, 2.5, 3.0, 3.5)
    else:
        scores = (55, 62, 70)
        sl_mults = (2.0, 2.5, 3.0)

    structures = [
        ("1x2.5R",        [(2.5, 1.00)]),
        ("1x2.0R",        [(2.0, 1.00)]),
        ("2.5/4.0",       [(2.5, 0.50), (4.0, 0.50)]),
        ("2.5/4.0/6.0",   [(2.5, 0.50), (4.0, 0.25), (6.0, 0.25)]),
    ]

    import risk as risk_mod
    orig_sl = risk_mod.SL_ATR_MULT

    print(f"\n{'=' * 66}")
    print(f"  OUT-OF-SAMPLE SEARCH — {ASSETS[a.asset]['label']}")
    print(f"  train: {split} bars  |  test: {len(m5) - split} bars "
          f"(kabhi search mein use nahi hua)")
    print(f"  spread={spread}  slippage={a.slippage}  "
          f"combos={len(scores) * len(sl_mults) * len(structures)}")
    print(f"{'=' * 66}\n")
    print(f"  {'score':>6}{'sl':>6}{'structure':>16}{'trades':>8}"
          f"{'expectancy':>13}{'':>4}")
    print("  " + "-" * 55)

    results = []
    for sc in scores:
        for sm in sl_mults:
            for name, tg in structures:
                risk_mod.SL_ATR_MULT = sm
                ts = run(a.asset, a.days, spread, a.cooldown_bars, a.max_bars,
                         {"MIN_SCORE": sc}, targets=tg, csv_path=a.csv,
                         csv_tf=a.csv_timeframe, slippage=a.slippage,
                         m5_slice=train_m5, quiet=True)
                sm_r = _summary(ts)
                if sm_r is None:
                    print(f"  {sc:>6}{sm:>6.1f}{name:>16}{0:>8}"
                          f"{'—':>13}")
                    continue
                # Kam trades wale combo ko chunna hi overfitting hai.
                trusted = sm_r["n"] >= MIN_TRADES_TO_TRUST
                flag = "" if trusted else "  (kam)"
                print(f"  {sc:>6}{sm:>6.1f}{name:>16}{sm_r['n']:>8}"
                      f"{sm_r['expectancy']:>+13.4f}{flag}")
                if trusted:
                    results.append((sm_r["expectancy"], sc, sm, name, tg, sm_r))

    risk_mod.SL_ATR_MULT = orig_sl

    if not results:
        print(f"\n  Koi bhi combo {MIN_TRADES_TO_TRUST}+ trades tak nahi "
              f"pahuncha train period mein.")
        print("  Isse aage badhna bekaar hai — jo bhi 'best' dikhega wo "
              "5-10 trades ka ittefaq hoga.")
        print("  Zyada data chahiye (--csv se lambi history), ya filters "
              "dheele karne honge.")
        return

    results.sort(reverse=True, key=lambda x: x[0])
    best_e, sc, sm, name, tg, train_sm = results[0]

    print(f"\n  TRAIN ka best: score>={sc}, SL={sm}xATR, TP={name} "
          f"({train_sm['n']} trades, {best_e:+.4f} R/trade)")
    print("  Ab yahi settings TEST period pe — bina kisi tweak ke.\n")

    risk_mod.SL_ATR_MULT = sm
    test_ts = run(a.asset, a.days, spread, a.cooldown_bars, a.max_bars,
                  {"MIN_SCORE": sc}, targets=tg, csv_path=a.csv,
                  csv_tf=a.csv_timeframe, slippage=a.slippage,
                  m5_slice=test_m5, quiet=True)
    risk_mod.SL_ATR_MULT = orig_sl

    report(list(test_ts), f"OUT-OF-SAMPLE — score>={sc}, SL={sm}xATR, TP={name}")

    test_sm = _summary(test_ts)
    print(f"\n  {'=' * 62}")
    print(f"  FAISLA")
    print(f"  {'=' * 62}")
    print(f"  Train expectancy : {best_e:+.4f} R/trade  ({train_sm['n']} trades)")
    if test_sm is None:
        print("  Test  expectancy : koi trade nahi aaya")
        print("\n  Test period mein ek bhi trade na aana bhi ek jawab hai —")
        print("  settings itni tight hain ki wo train period ki shakl pe fit hain.")
        return
    print(f"  Test  expectancy : {test_sm['expectancy']:+.4f} R/trade  "
          f"({test_sm['n']} trades)")

    if test_sm["n"] < MIN_TRADES_TO_TRUST:
        print(f"\n  ⚠️  Test mein sirf {test_sm['n']} trades. Ye kisi bhi "
              f"nateeje ke liye kam hai.")
        print("  Kuch bhi decide karne se pehle zyada data chahiye.")
    elif test_sm["expectancy"] <= 0:
        print("\n  Test pe expectancy NEGATIVE hai.")
        print("  Train ka acha number overfitting tha — us settings ne")
        print("  us period ki shakl yaad ki thi, koi edge nahi seekha.")
        print("  Threshold aur dheela-tight karne se ye theek NAHI hoga.")
    elif test_sm["expectancy"] < best_e * 0.5:
        print("\n  Test expectancy positive hai par train se aadhi se bhi kam.")
        print("  Edge ka thoda ishaara ho sakta hai, par zyadatar overfit hai.")
        print("  Live paisa lagane se pehle demo pe forward test karein.")
    else:
        print("\n  Test period pe bhi expectancy tiki hui hai. Ye sabse")
        print("  behtar nateeja hai jo backtest de sakta hai — GUARANTEE nahi.")
        print("  Agla step: 2-3 mahine DEMO forward test, phir chhota size.")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--asset", default="gold", choices=list(ASSETS))
    p.add_argument("--days", type=int, default=30)
    p.add_argument("--spread", type=float, default=None,
                   help="broker spread in price units (gold default 0.25)")
    p.add_argument("--cooldown-bars", type=int, default=3)
    p.add_argument("--max-bars", type=int, default=None,
                   help=f"trade expiry, 5m bars mein. Default config ke "
                        f"TRADE_EXPIRY_MINUTES ({TRADE_EXPIRY_MINUTES}m) se "
                        f"aata hai taaki backtest aur live ek jaisa chalein.")
    p.add_argument("--slippage", type=float, default=0.0,
                   help="per-side slippage, price units mein (gold pe 0.05-0.15 "
                        "realistic hai). Entry aur exit dono pe lagta hai.")
    p.add_argument("--min-score", type=int, default=None)
    p.add_argument("--min-confirmations", type=int, default=None)
    p.add_argument("--walk-forward", action="store_true",
                   help="[KAMZOR] ek hi settings ke trades ko aadha-aadha "
                        "baant kar dikhata hai. Ye stability check hai, "
                        "overfit check NAHI. Uske liye --oos use karein.")
    p.add_argument("--oos", action="store_true",
                   help="ASLI out-of-sample: train period pe grid search, "
                        "phir best settings ko us test period pe chalao jise "
                        "search ne kabhi dekha nahi. Yahi bharosemand test hai.")
    p.add_argument("--train-frac", type=float, default=0.6,
                   help="data ka kitna hissa train ke liye (default 0.6)")
    p.add_argument("--grid", default="quick", choices=("quick", "full"),
                   help="--oos ke liye search grid ka size")
    p.add_argument("--csv", default=None,
                   help="historical data CSV se backtest karo (internet ki "
                        "zaroorat nahi). MT4/MT5/TradingView export chalega.")
    p.add_argument("--tf-mult", type=int, default=1,
                   help="signal timeframe scaler. 1 = 1m/5m/15m (default). "
                        "3 = 3m/15m/45m. Wide-spread assets (forex) pe R bada "
                        "karke spread ka hissa ghatata hai.")
    p.add_argument("--csv-timeframe", type=int, default=1, choices=(1, 5),
                   help="CSV mein candles kis timeframe ki hain (1 ya 5 min)")
    p.add_argument("--sweep-tp", action="store_true",
                   help="alag TP structures test karo (TP3 hata ke bhi)")
    p.add_argument("--sweep-sl", action="store_true",
                   help="SL multiplier ko 1.0 se 4.0 tak test karo — "
                        "khud dekho tight SL ka asli asar kya hai")
    a = p.parse_args()

    spread = a.spread if a.spread is not None else ASSETS[a.asset].get("spread", 0.0)

    # Expiry minutes mein fix hai -- bars mein badalte waqt bar ki lambai
    # ka hisaab rakhna zaroori hai, warna tf-mult 3 pe trade 3 guna zyada
    # der khula rehta aur comparison jhoota ho jaata.
    if a.max_bars is None:
        a.max_bars = max(1, TRADE_EXPIRY_MINUTES // (5 * a.tf_mult))

    if a.oos:
        oos_search(a, spread, train_frac=a.train_frac, grid=a.grid)
        return

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
                      "MIN_TOTAL_CONFIRMATIONS": a.min_confirmations},
                     targets=tg, csv_path=a.csv, csv_tf=a.csv_timeframe,
                     slippage=a.slippage, tf_mult=a.tf_mult, quiet=True)
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
                      "MIN_TOTAL_CONFIRMATIONS": a.min_confirmations},
                     csv_path=a.csv, csv_tf=a.csv_timeframe,
                     slippage=a.slippage, tf_mult=a.tf_mult, quiet=True)
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
                 {"MIN_SCORE": a.min_score,
                  "MIN_TOTAL_CONFIRMATIONS": a.min_confirmations},
                 csv_path=a.csv, csv_tf=a.csv_timeframe, slippage=a.slippage,
                 tf_mult=a.tf_mult)

    tag = (f"{ASSETS[a.asset]['label']} | {a.days}d | spread={spread} | "
           f"score>={a.min_score or strategy.MIN_SCORE} | "
           f"conf>={a.min_confirmations or strategy.MIN_TOTAL_CONFIRMATIONS}")

    if a.walk_forward and len(trades) > 10:
        mid = len(trades) // 2
        report(trades[:mid], "IN-SAMPLE (pehla aadha)")
        report(trades[mid:], "OUT-OF-SAMPLE (doosra aadha)")
        print("\n  ⚠️  Ye ASLI out-of-sample nahi hai — dono halves ek hi")
        print("  settings pe chale hain, kuch tune nahi hua. Ye sirf batata hai")
        print("  ki result period-dar-period stable hai ya nahi.")
        print("  Overfitting check ke liye --oos chalayein.")
    else:
        report(trades, tag)

    print(f"\n  ({time.time() - t0:.1f}s)")


if __name__ == "__main__":
    main()
