import os

BOT_TOKEN = os.getenv("BOT_TOKEN")

# Gold - Yahoo Finance ticker. XAUUSD=X returns 404 on Yahoo's chart
# endpoint (that spot-forex-style ticker isn't served there), so we use
# COMEX Gold Futures instead - it tracks spot XAU/USD very closely and
# is reliably available on Yahoo's free feed.
GOLD_SYMBOL = "GC=F"

# Bitcoin - Yahoo Finance ticker
BTC_SYMBOL = "BTC-USD"

# Compatibility (purane code ke liye)
SYMBOL = GOLD_SYMBOL

INTERVAL = "1min"
