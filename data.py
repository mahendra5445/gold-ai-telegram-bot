import requests
from config import GOLD_SYMBOL, BTC_SYMBOL

# Yahoo Finance's unofficial chart endpoint - no API key, no daily credit
# cap (unlike Twelve Data's free 800/day). It's undocumented/unofficial
# though, so it can occasionally return gaps or change shape without
# notice - the error handling below surfaces whatever goes wrong instead
# of hiding it.
YF_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
YF_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}

# 1m data on Yahoo is only available for the last few days, but that's
# far more than the 200 closed candles we need for any of these intervals.
_YF_INTERVAL = {"1min": "1m", "5min": "5m", "15min": "15m"}
_YF_RANGE = {"1min": "5d", "5min": "5d", "15min": "5d"}


def _fetch_tf(symbol, interval_key, label):
    """
    Fetch one timeframe from Yahoo Finance.
    Raises RuntimeError with the real reason on failure (same pattern as
    before) so /gold and /btc show the actual problem instead of a
    generic "unavailable" message.
    """
    yf_interval = _YF_INTERVAL[interval_key]
    yf_range = _YF_RANGE[interval_key]
    url = YF_URL.format(symbol=symbol)
    params = {"interval": yf_interval, "range": yf_range}

    try:
        r = requests.get(url, params=params, headers=YF_HEADERS, timeout=15)
        r.raise_for_status()
        payload = r.json()
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(f"[{label} {interval_key}] HTTP {e.response.status_code}: {e.response.text[:300]}")
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"[{label} {interval_key}] Network/timeout error: {e}")
    except ValueError as e:
        raise RuntimeError(f"[{label} {interval_key}] Bad JSON from Yahoo Finance: {e}")

    chart = payload.get("chart", {})
    if chart.get("error"):
        raise RuntimeError(f"[{label} {interval_key}] Yahoo Finance error: {chart['error']}")

    result = chart.get("result")
    if not result:
        raise RuntimeError(f"[{label} {interval_key}] No data returned by Yahoo Finance.")

    r0 = result[0]
    timestamps = r0.get("timestamp") or []
    quote = (r0.get("indicators", {}).get("quote") or [{}])[0]

    opens = quote.get("open") or []
    highs = quote.get("high") or []
    lows = quote.get("low") or []
    closes = quote.get("close") or []
    volumes = quote.get("volume") or []

    # Drop candles with any missing OHLC value - gaps around market
    # open/close are common in Yahoo's free feed
    rows = []
    for i in range(len(timestamps)):
        o = opens[i] if i < len(opens) else None
        h = highs[i] if i < len(highs) else None
        l = lows[i] if i < len(lows) else None
        c = closes[i] if i < len(closes) else None
        if None in (o, h, l, c):
            continue
        v = volumes[i] if i < len(volumes) and volumes[i] is not None else 0
        rows.append((o, h, l, c, v))

    if not rows:
        raise RuntimeError(f"[{label} {interval_key}] Yahoo Finance returned no usable candles.")

    rows = rows[:-1]  # drop the current forming candle - only trade closed candles

    if len(rows) < 200:
        raise RuntimeError(
            f"[{label} {interval_key}] Only got {len(rows)} closed candles (need >=200). "
            f"Yahoo's free feed can have gaps - try again shortly."
        )

    opens_f = [row[0] for row in rows]
    highs_f = [row[1] for row in rows]
    lows_f = [row[2] for row in rows]
    closes_f = [row[3] for row in rows]
    volumes_f = [row[4] for row in rows]

    # Spot forex/metals tickers (like XAUUSD=X) often report zero volume
    # on Yahoo. If it's all zero, pass None instead - that tells the
    # strategy "no volume data" rather than "zero volume", so it doesn't
    # divide by zero on VWAP or permanently block every gold signal.
    if sum(volumes_f) == 0:
        volumes_f = None

    return {
        "open": opens_f,
        "close": closes_f,
        "high": highs_f,
        "low": lows_f,
        "volume": volumes_f,
        "price": closes_f[-1],
    }


def get_gold_tf(interval):
    return _fetch_tf(GOLD_SYMBOL, interval, "GOLD")


def get_btc_tf(interval):
    return _fetch_tf(BTC_SYMBOL, interval, "BTC")


def get_latest_price(asset="gold"):
    """
    Lightweight single-price check used by the trade monitor.
    Returns None (not raise) on failure - the monitor loop just skips
    this cycle and retries next time.
    """
    symbol = BTC_SYMBOL if asset.lower() == "btc" else GOLD_SYMBOL
    url = YF_URL.format(symbol=symbol)
    params = {"interval": "1m", "range": "1d"}

    try:
        r = requests.get(url, params=params, headers=YF_HEADERS, timeout=15)
        r.raise_for_status()
        payload = r.json()
        result = payload["chart"]["result"][0]
        closes = result["indicators"]["quote"][0]["close"] or []
        for c in reversed(closes):
            if c is not None:
                return float(c)
        return None
    except Exception as e:
        print(f"[PRICE ERROR] {asset}: {e}")
        return None


def get_candles(asset="gold"):
    """
    Raises RuntimeError (with the real reason) on failure instead of
    returning None - callers in main.py already catch exceptions and
    show them to the user.
    """
    if asset.lower() == "btc":
        tf1 = get_btc_tf("1min")
        tf5 = get_btc_tf("5min")
        tf15 = get_btc_tf("15min")
    else:
        tf1 = get_gold_tf("1min")
        tf5 = get_gold_tf("5min")
        tf15 = get_gold_tf("15min")

    return {
        "asset": asset.upper(),
        "price": tf5["price"],
        "open": tf5["open"],
        "close": tf5["close"],
        "high": tf5["high"],
        "low": tf5["low"],
        "volume": tf5["volume"],
        "timeframes": {
            "1m": tf1["close"],
            "5m": tf5["close"],
            "15m": tf15["close"],
        },
    }
