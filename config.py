import os

BOT_TOKEN = os.getenv("BOT_TOKEN")

# ==========================================================================
# ASSET REGISTRY - GOLD + TIER 1 FOREX (Most Liquid Pairs)
#
# NAYA: `spread` = aapke broker ka typical spread, price units mein.
# Ye ab har trade ki risk calculation mein add hota hai aur backtest mein
# cost ki tarah kata jaata hai. Apne broker ka actual spread daalein --
# ye number seedha aapki expectancy pe asar karta hai.
# ==========================================================================
ASSETS = {
    "gold": {
        "symbol":   "XAUUSD=X",
        "fallback": "GC=F",
        "binance":  None,
        "decimals": 2,
        "label":    "GOLD",
        "spread":   0.25,
    },
    "eurusd": {
        "symbol":   "EURUSD=X",
        "fallback": None,
        "binance":  None,
        "decimals": 5,
        "label":    "EUR/USD",
        "spread":   0.00008,
    },
    "gbpusd": {
        "symbol":   "GBPUSD=X",
        "fallback": None,
        "binance":  None,
        "decimals": 5,
        "label":    "GBP/USD",
        "spread":   0.00012,
    },
    "usdjpy": {
        "symbol":   "USDJPY=X",
        "fallback": None,
        "binance":  None,
        "decimals": 3,
        "label":    "USD/JPY",
        "spread":   0.010,
    },
}

ASSET_LIST = list(ASSETS.keys())

GOLD_SYMBOL          = ASSETS["gold"]["symbol"]
GOLD_SYMBOL_FUTURES  = ASSETS["gold"]["fallback"]
SYMBOL               = GOLD_SYMBOL

INTERVAL = "1min"


# ==========================================================================
# RISK TUNING -- ek hi jagah, taaki backtest se calibrate kar sakein
# ==========================================================================
# SL = SL_ATR_MULT x ATR. Kam karne se trades zyada baar stop out hote hain
# aur spread risk ka bada hissa kha jaata hai -- backtest ke bina mat badlein.
SL_ATR_MULT = 2.5

# Minimum SL, price ka fraction. Noise/spread se bachne ke liye floor.
MIN_SL_PCT = 0.0015

# Asian / off-hours mein SL aur floor dono itne guna chaude.
LOW_LIQUIDITY_FACTOR = 1.4

# ── TARGET STRUCTURE ──────────────────────────────────────────────────────
# TP_MULTIPLES = targets, risk (R) ke multiples mein.
# SCALE_OUT    = har target pe position ka kitna hissa band ho (sum = 1.0).
# Dono ki length same honi chahiye. Code ab 1, 2, ya 3 -- kitne bhi
# targets support karta hai.
#
# SAFE MODE (abhi active): ek hi target, poori position 2.5R pe band.
#   - Break-even win rate sirf 28.6% (3-target structure mein 44.4% tha)
#   - Trade jaldi band -> asset jaldi free -> zyada setups
#   - Runner ka 0R pe marna khatam
#   - Trade-off: bade moves ka faayda nahi milega
TP_MULTIPLES = (2.5,)
SCALE_OUT = (1.00,)

# Purana 3-target structure (compare karne ke liye):
#   TP_MULTIPLES = (2.5, 4.0, 6.0)
#   SCALE_OUT    = (0.50, 0.25, 0.25)

# Trade expiry -- itne minutes baad open trade forcibly close.
# Pehle koi expiry thi hi nahi: ek stuck trade us asset ko hamesha ke liye
# block kar deta tha (has_open_trade).
# Single-target mein lambe runner ka intezaar nahi karna, isliye 240 -> 120.
TRADE_EXPIRY_MINUTES = 120

# ==========================================================================
# CIRCUIT BREAKER -- ek kharab din ko rokne ke liye
# ==========================================================================
MAX_TRADES_PER_DAY = 6          # per asset
MAX_DAILY_LOSS_R = -4.0         # is R pe pahunchne ke baad us din naye signals band


# ==========================================================================
# ATR TRAILING STOP (Feature #7) — NAYA
# Pehle TP2 ke baad message aata tha "Trail SL for remainder" lekin code
# trail karta hi nahi tha — SL entry pe hi khada rehta tha. Ab asli
# trailing hai: price ke saath SL ATR ke faasle pe peechhe chalta hai,
# aur kabhi ulti taraf nahi jaata.
# ==========================================================================
TRAILING_ENABLED = True
TRAILING_ATR_MULT = 2.0      # SL price se itne ATR peechhe chalega
TRAILING_START_R = 1.0       # itne R profit ke baad trailing shuru

# ==========================================================================
# SPREAD FILTER (Feature #11) — NAYA
# Agar live spread normal se zyada chauda ho (news, low liquidity, rollover)
# to trade skip. Sirf gold pe kaam karta hai — Swissquote bid/ask deta hai.
# Baaki pairs pe Yahoo bid/ask nahi deta, wahan config ka spread hi use hoga.
# ==========================================================================
SPREAD_FILTER_ENABLED = True
MAX_SPREAD_MULT = 2.0        # config spread se itne guna se zyada = skip

# ==========================================================================
# TRADE QUALITY FILTER (Feature #15) — NAYA
# Har item optional hai. True karne se wo condition ZAROORI ho jaati hai.
#
# ⚠️ SAAVDHAANI: jitne zyada True karenge, utne kam signals aayenge.
# Sab ek saath True karne pe hafton tak ek bhi signal nahi aayega.
# Ek-ek karke on karein aur backtest se dekhein ki expectancy behtar hui
# ya sirf trades kam ho gaye.
# ==========================================================================
REQUIRE_TREND_REGIME = True   # Ranging market mein trade nahi
REQUIRE_BOS = False           # Break of Structure zaroori
REQUIRE_ORDER_BLOCK = False   # Order Block zaroori
REQUIRE_FVG = False           # Fair Value Gap zaroori
REQUIRE_HTF_ALIGN = True      # 15m trend signal ke saath hona chahiye
MIN_RR = 2.0                  # is se kam RR wale trades skip
