import requests
from config import TWELVE_DATA_API_KEY, GOLD_SYMBOL, BTC_SYMBOL

TD_URL = "https://api.twelvedata.com/time_series"


def get_gold_tf(interval):
    params = {
        "symbol": GOLD_SYMBOL,
        "interval": interval,
        "outputsize": 210,
        "apikey": TWELVE_DATA_API_KEY,
    }

    try:
        r = requests.get(TD_URL, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print("GOLD ERROR:", e)
        return None

    if "values" not in data:
        print(data)
        return None

    candles = list(reversed(data["values"]))[:-1]  # drop current forming candle - only trade closed candles

    return {
        "open": [float(x["open"]) for x in candles],
        "close": [float(x["close"]) for x in candles],
        "high": [float(x["high"]) for x in candles],
        "low": [float(x["low"]) for x in candles],
        "volume": [float(x.get("volume", 1)) for x in candles],
        "price": float(candles[-1]["close"]),
    }


def get_btc_tf(interval):
    params = {
        "symbol": BTC_SYMBOL,
        "interval": interval,
        "outputsize": 210,
        "apikey": TWELVE_DATA_API_KEY,
    }

    try:
        r = requests.get(TD_URL, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print("BTC ERROR:", e)
        return None

    if "values" not in data:
        print(data)
        return None

    candles = list(reversed(data["values"]))[:-1]  # drop current forming candle - only trade closed candles

    return {
        "open": [float(x["open"]) for x in candles],
        "close": [float(x["close"]) for x in candles],
        "high": [float(x["high"]) for x in candles],
        "low": [float(x["low"]) for x in candles],
        "volume": [float(x.get("volume", 1)) for x in candles],
        "price": float(candles[-1]["close"]),
    }


def get_latest_price(asset="gold"):
    """
    Lightweight price check (single latest candle) used by the trade
    monitor, so we don't burn API quota pulling 200 candles just to
    check if a target/SL was hit.
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
        print(data)
        return None

    return float(data["values"][0]["close"])


def get_candles(asset="gold"):
    if asset.lower() == "btc":
        tf1 = get_btc_tf("1min")
        tf5 = get_btc_tf("5min")
        tf15 = get_btc_tf("15min")
    else:
        tf1 = get_gold_tf("1min")
        tf5 = get_gold_tf("5min")
        tf15 = get_gold_tf("15min")

    if not all([tf1, tf5, tf15]):
        return None

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
