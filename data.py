import requests
from config import TWELVE_DATA_API_KEY, SYMBOL


def get_tf(interval):
    url = (
        f"https://api.twelvedata.com/time_series"
        f"?symbol={SYMBOL}"
        f"&interval={interval}"
        f"&outputsize=200"
        f"&apikey={TWELVE_DATA_API_KEY}"
    )

    response = requests.get(url)
    data = response.json()

    if "values" not in data:
        return None

    candles = list(reversed(data["values"]))

    return {
        "close": [float(x["close"]) for x in candles],
        "high": [float(x["high"]) for x in candles],
        "low": [float(x["low"]) for x in candles],
        "price": float(candles[-1]["close"])
    }


def get_candles():
    tf1 = get_tf("1min")
    tf5 = get_tf("5min")
    tf15 = get_tf("15min")

    if tf1 is None or tf5 is None or tf15 is None:
        return None

    return {
        "price": tf5["price"],

        "close": tf5["close"],
        "high": tf5["high"],
        "low": tf5["low"],

        "timeframes": {
            "1m": tf1["close"],
            "5m": tf5["close"],
            "15m": tf15["close"]
        }
    }
