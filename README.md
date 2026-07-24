# AI Scalper Pro V5.5

Telegram bot jo Gold, BTC, Oil, EUR/USD, USD/JPY, LINK, aur ATOM ke liye
AI-scored trading signals deta hai — technical indicators, multi-timeframe
trend, smart-money concepts (BOS/CHoCH/liquidity), aur candlestick
patterns ko combine karke.

## Kaise kaam karta hai

- Har **15 minute** mein bot saare configured assets (`config.py` →
  `ASSET_LIST`) ka data check karta hai (`auto_signal.py`).
- Signal 12 confirmation checks (EMA, ADX, Supertrend, VWAP, MACD,
  RSI, multi-timeframe trend, volume, ATR, liquidity, volume spike,
  candle confirmation) ke against score hota hai — sirf tab fire
  hota hai jab score aur confirmations dono threshold cross karein
  (`strategy.py` → `MIN_SCORE`, `MIN_CONFIRMATIONS`).
- Ek signal ke baad us asset ke liye **15-minute cooldown** lagta hai
  aur jab tak purana trade close nahi hota, naya signal nahi aata
  (ek time pe ek open trade per asset).
- Entry/SL/TP ATR-based hain (`risk.py`) — SL = 2.0× ATR, TP1/TP2/TP3
  = 2.5R / 4R / 6R. Har asset ka display/rounding precision uske
  `decimals` config se control hota hai (gold/btc/oil = 2, USD/JPY = 3,
  LINK/ATOM = 4, EUR/USD = 5) — forex jaise chhote-price pairs ke liye
  ye precision zaroori hai warna signal levels galat round ho jaate hain.
- Open trades `trade_monitor.py` har 2 minute mein price check karke
  track karta hai (SL / breakeven / TP1 / TP2 / TP3 hits) aur
  Telegram par update bhejta hai.
- `watchdog.py` har 5 minute mein check karta hai ki auto-signal loop
  zinda hai ya nahi (agar 40+ minute se koi cycle complete na hui ho,
  matlab kahin stuck/silently failed hai, to alert bhejta hai).
- `daily_summary.py` roz ek fixed time pe (default 18:00 server-local)
  us din ka combined + per-asset signal count aur win rate bhejta hai.
- Sab trades `data/trades.json` mein persist hote hain (atomic
  writes), registered users `data/admins.json` mein.

## Assets

| Asset | Command | Yahoo Symbol | Decimals |
|-------|---------|-------------|----------|
| Gold | `/gold` | `XAUUSD=X` (fallback `GC=F`) | 2 |
| Bitcoin | `/btc` | `BTC-USD` | 2 |
| Oil (WTI) | `/oil` | `CL=F` | 2 |
| EUR/USD | `/eurusd` | `EURUSD=X` | 5 |
| USD/JPY | `/usdjpy` | `USDJPY=X` | 3 |
| Chainlink | `/link` | `LINK-USD` | 4 |
| Cosmos | `/atom` | `ATOM-USD` | 4 |

Naya asset add karna ho to bas `config.py` → `ASSETS` dict mein ek
entry add karo — baaki sab code (`data.py`, `main.py`,
`auto_signal.py`) generic hai aur apne aap naya asset pick kar leta hai.

## Commands

| Command    | Kaam |
|------------|------|
| `/start`   | Bot se signals paane ke liye register karo |
| `/gold`, `/btc`, `/oil`, `/eurusd`, `/usdjpy`, `/link`, `/atom` | Manual signal check us asset ka |
| `/signal`  | `/gold` jaisa hi |
| `/trend`   | 1M/5M/15M trend summary (gold) |
| `/stats`   | Trade statistics (add asset name for one asset, e.g. `/stats eurusd`; no arg = combined + per-asset breakdown) |
| `/history` | Last 10 trades (add asset name to filter, e.g. `/history btc`) |

## Setup

1. `pip install -r requirements.txt`
2. `.env.example` ko `.env` bana lo aur `BOT_TOKEN` fill karo
   (@BotFather se milega)
3. `python main.py`

Production deploy (Railway) ke liye `RAILWAY_SETUP.md` dekho — wahan
persistent volume attach karna zaroori hai warna restarts pe trade
history aur registered users reset ho jayenge.

## Key files

| File | Kaam |
|------|------|
| `strategy.py` | Signal scoring engine — thresholds yahan hain |
| `risk.py` | SL/TP calculation (ATR-based, decimals-aware) |
| `auto_signal.py` | Background loop jo saare assets ke signals check/bhejta hai |
| `trade_monitor.py` | Open trades ko SL/TP ke against track karta hai |
| `data.py` | Yahoo Finance se price data (+ fallback sources), sab assets ke liye generic |
| `config.py` | `ASSETS` registry — symbols, decimals, fallback/external sources |
| `watchdog.py` | Auto-signal loop stuck/dead detect karke alert bhejta hai |
| `daily_summary.py` | Roz ka signal/win-rate digest bhejta hai |

## Config tuning

Signal frequency aur risk:reward `strategy.py` aur `risk.py` ke top
par defined constants se control hote hain — waha comments mein
explain kiya gaya hai ki har value ka kya effect hai.

## Known limitations

- News filter (`news.py`) sirf high-impact **USD** events check karta
  hai — saare assets ke liye ek hi filter hai (koi asset-specific
  currency filter nahi, e.g. JPY ya EUR news alag se check nahi hoti).
- Oil aur forex pairs (EUR/USD, USD/JPY) ke liye koi independent
  fallback price source configured nahi hai (`data.py` →
  `get_external_price`) — sirf Yahoo Finance retry hi available hai
  in ke liye. Gold aur crypto assets ke paas fallback sources hain.
- `daily_summary.py` server ke local time-zone se chalta hai (jo
  Railway pe usually UTC hota hai) — `SUMMARY_HOUR` constant adjust
  karke apna preferred IST time set kar sakte ho.
