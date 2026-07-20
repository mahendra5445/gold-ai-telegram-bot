import os

BOT_TOKEN = os.getenv("BOT_TOKEN")

# Gold - Primary: XAUUSD=X (Yahoo Finance spot gold).
# Ye MT5 ke XAU/USD price se match karta hai.
#
# GC=F (COMEX Futures) pehle use hota tha - lekin woh spot se $10-25
# zyada hota hai kyunki usme futures contango/premium hota hai.
# MT5 spot price dikhata hai, isliye XAUUSD=X sahi hai.
#
# Agar XAUUSD=X Yahoo Finance pe kisi wajah se fail ho to
# data.py apne aap GC=F pe fallback kar leta hai.
GOLD_SYMBOL = "XAUUSD=X"          # Spot XAU/USD  ← MT5 se match
GOLD_SYMBOL_FUTURES = "GC=F"       # Futures fallback (contango premium hota hai)

# Bitcoin - Yahoo Finance ticker
BTC_SYMBOL = "BTC-USD"

# Compatibility (purane code ke liye)
SYMBOL = GOLD_SYMBOL

INTERVAL = "1min"
