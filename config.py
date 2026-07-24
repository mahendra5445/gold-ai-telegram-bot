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
        "spread":   0.35,
        "min_sl_pct": 0.0015,
    },
    "silver": {
        "symbol":   "XAGUSD=X",
        "fallback": "SI=F",
        "binance":  None,
        "decimals": 3,
        "label":    "SILVER",
        "spread":   0.040,
        "min_sl_pct": 0.0015,
    },
    "eurusd": {
        "symbol":   "EURUSD=X",
        "fallback": None,
        "binance":  None,
        "decimals": 5,
        "label":    "EUR/USD",
        "spread":   0.00002,
        "min_sl_pct": 0.00025,
    },
    "gbpusd": {
        "symbol":   "GBPUSD=X",
        "fallback": None,
        "binance":  None,
        "decimals": 5,
        "label":    "GBP/USD",
        "spread":   0.00014,
        "min_sl_pct": 0.00025,
    },
    "usdjpy": {
        "symbol":   "USDJPY=X",
        "fallback": None,
        "binance":  None,
        "decimals": 3,
        "label":    "USD/JPY",
        "spread":   0.012,
        "min_sl_pct": 0.00020,
    },
}

# ─────────────────────────── ASSET_LIST ────────────────────────────
# 100 din ke M1 backtest ka NAAP (aapke asli broker spread par,
# 24-Jul-2026 ke MT5 screenshots se). Expectancy = R per trade:
#
#   gold    +0.160   287 trades   <- kaam karta hai
#   eurusd  +0.025   302 trades   <- kaam karta hai (0.2 pip spread)
#   silver  -0.001   320 trades   <- bilkul flat, koi edge nahi
#   gbpusd  -0.074   297 trades   <- paisa khaata hai
#   usdjpy  -0.077   263 trades   <- paisa khaata hai
#
# Neeche sirf wahi on hain jinka edge naapa gaya hai. Baaki chahiye to
# comment hata do -- par numbers upar likhe hain.
ASSET_LIST = [
    "gold",
    "eurusd",
    # "silver",   # flat
    # "gbpusd",   # negative
    # "usdjpy",   # negative
]

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

# Minimum SL, price ka fraction — sirf FALLBACK default hai.
# Asli value har asset ke apne ASSETS["<asset>"]["min_sl_pct"] se aati hai.
#
# KYUN PER-ASSET (ye asli bug tha): ek hi 0.0015 sab pe lagta tha. Gold ka
# ATR price ke muqable itna bada hai ki floor kabhi bind hi nahi karta —
# uska SL sach mein volatility se banta hai. Forex pairs pe ulta tha:
#
#   asset    ATR x 2.5      floor 0.15%     kaun jeeta    TP1 distance
#   GOLD       6.50            5.03           ATR           ~17.0  ✅
#   EURUSD     0.00032         0.00163        FLOOR (5.0x)  ~43 pips ❌
#   GBPUSD     0.00040         0.00192        FLOOR (4.8x)  ~51 pips ❌
#   USDJPY     0.0650          0.2325         FLOOR (3.6x)  ~61 pips ❌
#
# Yaani forex pe SL apni volatility se 3.5-5 guna chauda tha, aur TP (2.5R)
# lagbhag AADHE DIN ki range ban jaata tha. 5-minute scalp signal se aisa
# target 8 ghante mein aata hi nahi — isliye gold target ki taraf jaata
# dikhta tha aur ye teen bas expire/SL hote the.
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
# 120 -> 480 (8 ghante).
#
# WAJAH (test se): 120 min pe 61.7% trades TP ya SL kisi tak nahi pahunchte
# the -- bas time-out ho jaate the. Ye geometry ka masla hai: SL 1R door hai
# aur TP 2.5R, to SL hamesha pehle resolve hota hai. Chhota window jeetne
# wale trades ko zyada kaatta hai, haarne walon ko kam.
#
# Test se resolved trades mein TP ka hissa:
#     2 hr  -> 16.7%
#     8 hr  -> 33.3%    <- ab yahan
#    24 hr  -> 35.9%    (aur faayda kam, par asset poora din block)
#
# 8 ghante pe expired trades 61.7% se girkar ~14% reh jaate hain, aur asset
# ek session ke andar free bhi ho jaata hai.
TRADE_EXPIRY_MINUTES = 480

# ── SIGNAL TIMING — ek hi jagah, warna teen alag sach ban jaate hain ──────
# BUG jo tha: strategy.py mein SIGNAL_VALID_MINUTES = 8 hardcoded tha aur
# Telegram message "Valid : 8 Minutes" chhaapta tha. Lekin auto_signal_job
# har 15 MINUTE pe check karta hai (yaani 8-minute wali window ka koi matlab
# hi nahi tha), aur trade upar wali 480 MINUTE expiry tak open rehta tha.
# User ko lagta tha signal 8 minute ka hai -- bot 8 GHANTE hold kar raha tha.
# Ab teenon yahan se aate hain aur message dono numbers dikhata hai.
SIGNAL_CYCLE_MINUTES = 15        # auto_signal_job kitni der baad dobara dekhta hai
SIGNAL_VALID_MINUTES = 15        # entry level kitni der kaam ka hai
SIGNAL_COOLDOWN_MINUTES = 15     # ek hi asset pe do signals ke beech ka farq

# ==========================================================================
# CIRCUIT BREAKER -- ek kharab din ko rokne ke liye
# ==========================================================================
# NOTE: 8-ghante ki expiry + one-open-trade-per-asset lock ki wajah se
# practically 2-3 trades hi aate hain per asset per day. Isliye ye dono
# numbers us hisaab se set kiye hain -- warna trigger hi nahi hote.
MAX_TRADES_PER_DAY = 4          # per asset (safety cap, normally 2-3 aayenge)

# Pehle -4.0R tha, jo 3 trades ke din mein KABHI trigger nahi hota
# (3 x -1R = -3R max). Ab -2.5R -- yaani lagbhag 2.5 full stop-outs ke baad
# us asset pe us din ke liye signals band.
MAX_DAILY_LOSS_R = -2.5


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
# "any"      = sab chalega (filter off)
# "not_range"= sirf "Ranging" block hota hai  <- purana behaviour
# "strict"   = SIRF "Trending" pe trade, "Transition" bhi block
#
# Test se (choppy data pe regime classification):
#     Ranging 72% | Transition 25% | Trending 3%
# "not_range" pe wo 28% nikal jaata tha -- aur unhi trades ne 0% jeeta,
# -0.86R per trade. "strict" us leak ko band karta hai.
REGIME_MODE = "strict"
REQUIRE_BOS = False           # Break of Structure zaroori
REQUIRE_ORDER_BLOCK = False   # Order Block zaroori
REQUIRE_FVG = False           # Fair Value Gap zaroori
REQUIRE_HTF_ALIGN = True      # 15m trend signal ke saath hona chahiye
MIN_RR = 2.0                  # is se kam RR wale trades skip
