import requests
from config import TWELVE_DATA_API_KEY, GOLD_SYMBOL, BTC_SYMBOL

TD_URL = "https://api.twelvedata.com/time_series"


def _fetch_tf(symbol, interval, label):
    """
    Fetch one timeframe from Twelve Data.
    Raises RuntimeError with the REAL reason on failure instead of
    silently swallowing it - the old code only printed to server logs,
    so /gold and /btc just showed a generic "unavailable" message with
    no way to tell what actually went wrong from Telegram.
    """
    params = {
        "symbol": symbol,
        "interval": interval,
        "outputsize": 210,
        "apikey": TWELVE_DATA_API_KEY,
    }

    if not TWELVE_DATA_API_KEY:
        raise RuntimeError(
            f"[{label} {interval}] TWELVE_DATA_API_KEY is empty/not set on the server."
        )

    try:
        r = requests.get(TD_URL, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(f"[{label} {interval}] HTTP {e.response.status_code}: {e.response.text[:300]}")
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"[{label} {interval}] Network/timeout error: {e}")

    if "values" not in data:
        # Twelve Data puts the real reason here, e.g. invalid API key,
        # rate limit exceeded, invalid symbol, etc.
        code = data.get("code")
        message = data.get("message", str(data))
        raise RuntimeError(f"[{label} {interval}] API error (code {code}): {message}")

    candles = list(reversed(data["values"]))[:-1]  # drop current forming candle - only trade closed candles

    if len(candles) < 200:
        raise RuntimeError(
            f"[{label} {interval}] Only got {len(candles)} closed candles (need >=200). "
            f"Check outputsize/plan limits on Twelve Data."
        )

    return {
        "open": [float(x["open"]) for x in candles],
        "close": [float(x["close"]) for x in candles],
        "high": [float(x["high"]) for x in candles],
        "low": [float(x["low"]) for x in candles],
        "volume": [float(x.get("volume", 1)) for x in candles],
        "price": float(candles[-1]["close"]),
    }


def get_gold_tf(interval):
    return _fetch_tf(GOLD_SYMBOL, interval, "GOLD")


def get_btc_tf(interval):
    return _fetch_tf(BTC_SYMBOL, interval, "BTC")


def get_latest_price(asset="gold"):
    """
    Lightweight price check (single latest candle) used by the trade
    monitor, so we don't burn API quota pulling 200 candles just to
    check if a target/SL was hit.
    Returns None (not raise) on failure - the monitor loop just skips
    this cycle and retries next time, no need to surface an error to a user.
    """
    symbol = BTC_SYMBOL if asset.lower() == "btc" else GOLD_SYMBOL
    params = {
        "symbol": symbol,
        "interval": "1min",
        "outputsize": 1,
        "apikey": TWELVE_DATA_API_KEY,
    }

    try:
        r = requests.get(TD_URL, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"[PRICE ERROR] {asset}: {e}")
        return None

    if "values" not in data:
        print(f"[PRICE ERROR] {asset}: {data}")
        return None

    return float(data["values"][0]["close"])


def get_candles(asset="gold"):
    """
    Raises RuntimeError (with the real reason) on failure instead of
    returning None. Callers in main.py already catch exceptions and
    show them to the user - this just lets that path actually fire.
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
