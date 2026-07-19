import requests
from config import TWELVE_DATA_API_KEY, GOLD_SYMBOL, BTC_SYMBOL

TD_URL = "https://api.twelvedata.com/time_series"


def get_gold_tf(interval):
    params = {
        "symbol": GOLD_SYMBOL,
        "interval": interval,
        "outputsize": 200,
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

    candles = list(reversed(data["values"]))

    return {
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
        "outputsize": 200,
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

    candles = list(reversed(data["values"]))

    return {
        "close": [float(x["close"]) for x in candles],
        "high": [float(x["high"]) for x in candles],
        "low": [float(x["low"]) for x in candles],
        "volume": [float(x.get("volume", 1)) for x in candles],
        "price": float(candles[-1]["close"]),
    }


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
