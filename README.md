# Gold AI Scalper Pro V5.0

Telegram bot jo Gold (XAU/USD) aur Bitcoin ke liye AI-scored trading
signals deta hai — technical indicators, multi-timeframe trend,
smart-money concepts (BOS/CHoCH/liquidity), aur candlestick patterns
ko combine karke.

## Kaise kaam karta hai

- Har **15 minute** mein bot dono assets (gold, btc) ka data check
  karta hai (`auto_signal.py`).
- Signal 12 confirmation checks (EMA, ADX, Supertrend, VWAP, MACD,
  RSI, multi-timeframe trend, volume, ATR, liquidity, volume spike,
  candle confirmation) ke against score hota hai — sirf tab fire
  hota hai jab score aur confirmations dono threshold cross karein
  (`strategy.py` → `MIN_SCORE`, `MIN_CONFIRMATIONS`).
- Ek signal ke baad us asset ke liye **15-minute cooldown** lagta hai
  aur jab tak purana trade close nahi hota, naya signal nahi aata
  (ek time pe ek open trade per asset).
- Entry/SL/TP ATR-based hain (`risk.py`) — SL = 2.0× ATR, TP1/TP2/TP3
  = 2.5R / 4R / 6R.
- Open trades `trade_monitor.py` har 2 minute mein price check karke
  track karta hai (SL / breakeven / TP1 / TP2 / TP3 hits) aur
  Telegram par update bhejta hai.
- Sab trades `data/trades.json` mein persist hote hain (atomic
  writes), registered users `data/admins.json` mein.

## Commands

| Command    | Kaam |
|------------|------|
| `/start`   | Bot se signals paane ke liye register karo |
| `/gold`    | Manual gold signal check |
| `/btc`     | Manual BTC signal check |
| `/signal`  | `/gold` jaisa hi |
| `/trend`   | 1M/5M/15M trend summary |
| `/stats`   | Total signals, win rate, TP/SL/BE count |
| `/history` | Last 10 trades |

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
| `risk.py` | SL/TP calculation (ATR-based) |
| `auto_signal.py` | Background loop jo signals check/bhejta hai |
| `trade_monitor.py` | Open trades ko SL/TP ke against track karta hai |
| `data.py` | Yahoo Finance se price data (+ fallback sources) |
| `config.py` | Symbols (gold/btc), interval settings |

## Config tuning

Signal frequency aur risk:reward `strategy.py` aur `risk.py` ke top
par defined constants se control hote hain — waha comments mein
explain kiya gaya hai ki har value ka kya effect hai.
