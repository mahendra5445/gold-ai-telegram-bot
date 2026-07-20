"""
Data fetching from Yahoo Finance.

Fixes applied:
  #8  API retry + exponential backoff — _fetch_tf wraps a single-attempt
                                        helper with up to 3 retries.
  #9  API timeout                     — explicit 15-s timeout on every request.
 #11  Stale candle validation         — last candle timestamp checked; warning
                                        logged if data is older than MAX_STALE_H.
  MT5 price fix                       — XAUUSD=X (spot) tried first; GC=F
                                        (futures, ~$10-25 premium) is fallback.
"""

import logging
import time as _time

import requests

from config import BTC_SYMBOL, GOLD_SYMBOL, GOLD_SYMBOL_FUTURES

logger = logging.getLogger(__name__)

YF_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
YF_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

_YF_INTERVAL = {"1min": "1m", "5min": "5m", "15min": "15m"}
_YF_RANGE    = {"1min": "5d", "5min": "5d", "15min": "5d"}

# Log a warning (but don't block the signal) when the newest closed
# candle is older than this many hours.
MAX_STALE_H = 8

# Retry settings
MAX_RETRIES      = 3
RETRY_BASE_DELAY = 1.0   # seconds; actual delays: 1 s, 2 s (2^0, 2^1)


# ── single-attempt fetch (no retry) ──────────────────────────────────────

def _fetch_tf_once(symbol: str, interval_key: str, label: str) -> dict:
    yf_interval = _YF_INTERVAL[interval_key]
    yf_range    = _YF_RANGE[interval_key]
    url         = YF_URL.format(symbol=symbol)
    params      = {"interval": yf_interval, "range": yf_range}

    try:
        r = requests.get(url, params=params, headers=YF_HEADERS, timeout=15)
        r.raise_for_status()
        payload = r.json()
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(
            f"[{label} {interval_key}] HTTP {e.response.status_code}: "
            f"{e.response.text[:300]}"
        )
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"[{label} {interval_key}] Network/timeout error: {e}")
    except ValueError as e:
        raise RuntimeError(f"[{label} {interval_key}] Bad JSON: {e}")

    chart = payload.get("chart", {})
    if chart.get("error"):
        raise RuntimeError(f"[{label} {interval_key}] Yahoo Finance error: {chart['error']}")

    result = chart.get("result")
    if not result:
        raise RuntimeError(f"[{label} {interval_key}] No data returned.")

    r0         = result[0]
    timestamps = r0.get("timestamp") or []
    quote      = (r0.get("indicators", {}).get("quote") or [{}])[0]

    opens   = quote.get("open")   or []
    highs   = quote.get("high")   or []
    lows    = quote.get("low")    or []
    closes  = quote.get("close")  or []
    volumes = quote.get("volume") or []

    rows = []
    for i in range(len(timestamps)):
        o = opens[i]   if i < len(opens)   else None
        h = highs[i]   if i < len(highs)   else None
        l = lows[i]    if i < len(lows)    else None
        c = closes[i]  if i < len(closes)  else None
        if None in (o, h, l, c):
            continue
        v = volumes[i] if i < len(volumes) and volumes[i] is not None else 0
        ts = timestamps[i] if i < len(timestamps) else None
        rows.append((o, h, l, c, v, ts))

    if not rows:
        raise RuntimeError(f"[{label} {interval_key}] No usable candles in response.")

    rows = rows[:-1]   # drop the still-forming candle

    if len(rows) < 200:
        raise RuntimeError(
            f"[{label} {interval_key}] Only {len(rows)} closed candles "
            f"(need ≥200). Yahoo can have gaps — retry shortly."
        )

    opens_f   = [r[0] for r in rows]
    highs_f   = [r[1] for r in rows]
    lows_f    = [r[2] for r in rows]
    closes_f  = [r[3] for r in rows]
    volumes_f = [r[4] for r in rows]
    last_ts   = rows[-1][5]   # unix timestamp of the last closed candle

    # ── Stale-data warning ────────────────────────────────────────────────
    if last_ts is not None:
        age_h = (_time.time() - last_ts) / 3600
        if age_h > MAX_STALE_H:
            logger.warning(
                f"[STALE] {label} {interval_key}: last candle is "
                f"{age_h:.1f}h old — market may be closed."
            )

    # Spot forex/metals tickers report zero volume on Yahoo.
    # Pass None so strategy knows "no data" rather than "zero volume".
    if sum(volumes_f) == 0:
        volumes_f = None

    return {
        "open":    opens_f,
        "close":   closes_f,
        "high":    highs_f,
        "low":     lows_f,
        "volume":  volumes_f,
        "price":   closes_f[-1],
        "last_ts": last_ts,
    }


# ── fetch with retry + exponential backoff ────────────────────────────────

def _fetch_tf(symbol: str, interval_key: str, label: str) -> dict:
    """
    Up to MAX_RETRIES attempts with exponential back-off (1 s, 2 s).
    Uses time.sleep() — acceptable because the bot only fetches data
    every 30 minutes and a brief event-loop pause is far better than
    a missing candle.
    """
    last_err: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            return _fetch_tf_once(symbol, interval_key, label)
        except RuntimeError as e:
            last_err = e
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_BASE_DELAY * (2 ** attempt)   # 1 s, 2 s
                logger.warning(
                    f"[RETRY] {label} {interval_key} attempt {attempt + 1}/"
                    f"{MAX_RETRIES} failed — retrying in {delay:.0f}s. {e}"
                )
                _time.sleep(delay)

    raise last_err   # type: ignore[misc]


# ── public helpers ────────────────────────────────────────────────────────

def get_gold_tf(interval: str) -> dict:
    """
    Spot gold (XAUUSD=X) first — matches MT5 XAU/USD prices.
    Falls back to COMEX Futures (GC=F) if spot is unavailable;
    a warning is logged because futures carry a ~$10-25 premium.
    """
    try:
        return _fetch_tf(GOLD_SYMBOL, interval, "GOLD(Spot)")
    except RuntimeError as spot_err:
        logger.warning(
            f"[GOLD] Spot ticker failed ({spot_err}); "
            f"falling back to futures {GOLD_SYMBOL_FUTURES}"
        )
        try:
            data = _fetch_tf(GOLD_SYMBOL_FUTURES, interval, "GOLD(Futures)")
            logger.warning(
                "[GOLD] Using futures price — may differ from MT5 spot by $10-25."
            )
            return data
        except RuntimeError as fut_err:
            raise RuntimeError(
                f"Both spot and futures unavailable. "
                f"Spot: {spot_err} | Futures: {fut_err}"
            )


def get_btc_tf(interval: str) -> dict:
    return _fetch_tf(BTC_SYMBOL, interval, "BTC")


def get_latest_price(asset: str = "gold") -> float | None:
    """
    Lightweight price check for the trade monitor.
    Returns None on failure (monitor skips and retries next cycle).
    Gold uses spot first, then futures fallback.
    """
    if asset.lower() == "btc":
        symbol   = BTC_SYMBOL
        fallback = None
    else:
        symbol   = GOLD_SYMBOL
        fallback = GOLD_SYMBOL_FUTURES

    def _single(sym: str) -> float | None:
        url    = YF_URL.format(symbol=sym)
        params = {"interval": "1m", "range": "1d"}
        r = requests.get(url, params=params, headers=YF_HEADERS, timeout=15)
        r.raise_for_status()
        payload = r.json()
        closes  = (
            payload["chart"]["result"][0]
            ["indicators"]["quote"][0]
            .get("close") or []
        )
        # BUG FIX: previously returned the single most recent tick.
        # Yahoo's free spot-gold feed occasionally reports one bad/stale
        # tick (a brief spike or a stuck value) that doesn't match a real
        # broker/MT5 price at all — this alone can fake-trigger an SL
        # that never really happened. Taking the median of the last few
        # valid ticks filters out that kind of single-tick glitch while
        # still tracking the live price closely.
        recent = [float(c) for c in reversed(closes) if c is not None][:5]
        if not recent:
            return None
        recent.sort()
        return recent[len(recent) // 2]

    try:
        price = _single(symbol)
        if price is not None:
            return price
        if fallback:
            return _single(fallback)
        return None
    except Exception as primary_err:
        if fallback:
            try:
                return _single(fallback)
            except Exception as fb_err:
                logger.error(f"[PRICE ERROR] {asset}: spot={primary_err} futures={fb_err}")
                return None
        logger.error(f"[PRICE ERROR] {asset}: {primary_err}")
        return None


def get_candles(asset: str = "gold") -> dict:
    """
    Fetch all three timeframes.
    Raises RuntimeError with a descriptive message on failure.
    """
    if asset.lower() == "btc":
        tf1  = get_btc_tf("1min")
        tf5  = get_btc_tf("5min")
        tf15 = get_btc_tf("15min")
    else:
        tf1  = get_gold_tf("1min")
        tf5  = get_gold_tf("5min")
        tf15 = get_gold_tf("15min")

    return {
        "asset":  asset.upper(),
        "price":  tf5["price"],
        "open":   tf5["open"],
        "close":  tf5["close"],
        "high":   tf5["high"],
        "low":    tf5["low"],
        "volume": tf5["volume"],
        "timeframes": {
            "1m":  tf1["close"],
            "5m":  tf5["close"],
            "15m": tf15["close"],
        },
    }
