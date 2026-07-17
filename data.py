import requests
from config import TWELVE_DATA_API_KEY, SYMBOL, INTERVAL, OUTPUTSIZE

def get_candles():
    url = (
        f"https://api.twelvedata.com/time_series"
        f"?symbol={SYMBOL}"
        f"&interval={INTERVAL}"
        f"&outputsize={OUTPUTSIZE}"
        f"&apikey={TWELVE_DATA_API_KEY}"
    )

    response = requests.get(url)
    data = response.json()

    if "values" not in data:
        return None

    candles = list(reversed(data["values"]))

    closes = [float(c["close"]) for c in candles]
    highs = [float(c["high"]) for c in candles]
    lows = [float(c["low"]) for c in candles]

    return {
        "close": closes,
        "high": highs,
        "low": lows,
        "price": closes[-1]
    }
