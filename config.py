import os

BOT_TOKEN = os.getenv("BOT_TOKEN")

# ==========================================================================
# ASSET REGISTRY
# ==========================================================================
ASSETS = {
    "gold": {
        "symbol":   "XAUUSD=X",
        "fallback": "GC=F",
        "binance":  None,
        "decimals": 2,
        "label":    "GOLD",
    },
    "btc": {
        "symbol":   "BTC-USD",
        "fallback": None,
        "binance":  "BTCUSDT",
        "decimals": 2,
        "label":    "BTC",
    },
    "oil": {
        "symbol":   "CL=F",
        "fallback": None,
        "binance":  None,
        "decimals": 2,
        "label":    "OIL (WTI)",
    },
    "eurusd": {
        "symbol":   "EURUSD=X",
        "fallback": None,
        "binance":  None,
        "decimals": 5,
        "label":    "EUR/USD",
    },
    "usdjpy": {
        "symbol":   "USDJPY=X",
        "fallback": None,
        "binance":  None,
        "decimals": 3,
        "label":    "USD/JPY",
    },
    "link": {
        "symbol":   "LINK-USD",
        "fallback": None,
        "binance":  "LINKUSDT",
        "decimals": 4,
        "label":    "LINK",
    },
    "atom": {
        "symbol":   "ATOM-USD",
        "fallback": None,
        "binance":  "ATOMUSDT",
        "decimals": 4,
        "label":    "ATOM",
    },
}

ASSET_LIST = list(ASSETS.keys())

GOLD_SYMBOL          = ASSETS["gold"]["symbol"]
GOLD_SYMBOL_FUTURES  = ASSETS["gold"]["fallback"]
BTC_SYMBOL           = ASSETS["btc"]["symbol"]
SYMBOL               = GOLD_SYMBOL

INTERVAL = "1min"
