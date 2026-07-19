def get_btc_tf(interval):
    mapping = {
        "1min": "1m",
        "5min": "5m",
        "15min": "15m",
    }

    params = {
        "symbol": BTC_SYMBOL,
        "interval": mapping[interval],
        "limit": 200,
    }

    try:
        r = requests.get(BINANCE_URL, params=params, timeout=15)

        print("BTC URL:", r.url)
        print("Status:", r.status_code)
        print("Response:", r.text[:500])

        r.raise_for_status()
        data = r.json()

    except Exception as e:
        print("BTC ERROR:", str(e))
        return {
            "error": str(e)
        }

    if not isinstance(data, list):
        print("Unexpected Binance response:", data)
        return {
            "error": str(data)
        }

    return {
        "close": [float(x[4]) for x in data],
        "high": [float(x[2]) for x in data],
        "low": [float(x[3]) for x in data],
        "volume": [float(x[5]) for x in data],
        "price": float(data[-1][4]),
    }
