import requests
from config import TWELVE_DATA_API_KEY, SYMBOL

BASE_URL = "https://api.twelvedata.com/time_series"


def get_tf(interval):
    params = {
        "symbol": SYMBOL,
        "interval": interval,
        "outputsize": 200,
        "apikey": TWELVE_DATA_API_KEY,
    }

    try:
        response = requests.get(BASE_URL, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
    except Exception:
        return None

    if "values" not in data:
        return None

    candles = list(reversed(data["values"]))

    try:
        return {
            "close": [float(x["close"]) for x in candles],
            "high": [float(x["high"]) for x in candles],
            "low": [float(x["low"]) for x in candles],
            "volume": [float(x.get("volume", 1)) for x in candles],
            "price": float(candles[-1]["close"]),
        }
    except (KeyError, ValueError):
        return None


def get_candles():
    tf1 = get_tf("1min")
    tf5 = get_tf("5min")
    tf15 = get_tf("15min")

    if not all([tf1, tf5, tf15]):
        return None

    return {
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
