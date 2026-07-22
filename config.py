import os

BOT_TOKEN = os.getenv("BOT_TOKEN")

# ==========================================================================
# ASSET REGISTRY - GOLD + TIER 1 FOREX (Most Liquid Pairs)
# ==========================================================================
ASSETS = {
    "gold": {
        "symbol":   "XAUUSD=X",
        "fallback": "GC=F",
        "binance":  None,
        "decimals": 2,
        "label":    "GOLD",
    },
    "eurusd": {
        "symbol":   "EURUSD=X",
        "fallback": None,
        "binance":  None,
        "decimals": 5,
        "label":    "EUR/USD",
    },
    "gbpusd": {
        "symbol":   "GBPUSD=X",
        "fallback": None,
        "binance":  None,
        "decimals": 5,
        "label":    "GBP/USD",
    },
    "usdjpy": {
        "symbol":   "USDJPY=X",
        "fallback": None,
        "binance":  None,
        "decimals": 3,
        "label":    "USD/JPY",
    },
}

ASSET_LIST = list(ASSETS.keys())

GOLD_SYMBOL          = ASSETS["gold"]["symbol"]
GOLD_SYMBOL_FUTURES  = ASSETS["gold"]["fallback"]
SYMBOL               = GOLD_SYMBOL

INTERVAL = "1min"
