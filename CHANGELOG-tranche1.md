# Tranche 1 — kya hua, kya nahi hua

## Fix (verify kiye hue)

1. **TP detect hi nahi hota tha.** monitor 120s par `get_latest_price()`
   poochta tha = aakhri 5 one-minute closes ka MEDIAN. Median spikes hata
   deta hai aur TP spike par hi lagta hai; do poll ke beech ka TP touch
   invisible tha. SL persist karta hai isliye hamesha pakda jaata tha.
   Isi asymmetry se win rate random baseline (~28%) se neeche 5.41% gira.
   -> ab last 3 one-minute candles ka **high/low**, poll 60s.

2. **Jeete trades "breakeven" gine ja rahe the.** status "TP" sirf TP3 par
   set hota tha. Aapke 11 "Breakeven" trades asal mein jeete the — sahi
   win rate 5.41% nahi, ~20% tha.

3. **TP1 pahunchne layak nahi tha.** 2.5R / 4R / 6R -> ab 1.2R / 2R / 3R.

4. **HTF alignment gate.** `trend15` sirf ek score mein judta tha, kisi
   trade ko rok nahi sakta tha — isliye BTC signal 5M Bullish/15M Weak
   Bullish ke saath MACD Bearish aur RSI 36.7 par bhi nikal gaya. Ab 15m
   trend ke khilaaf signal block hota hai (directional gate — sirf apni
   side maarta hai).

5. **Risk guardrails** (`guards.py`): max 4 open trades, max 12 signals/din,
   4 lagataar haar par 6 ghante ka auto-pause.

6. **Performance tracking** (`analytics.py`): expectancy, profit factor,
   avg win/loss R, max drawdown, lagataar jeet/haar, per-asset aur
   per-side breakdown, CSV + JSON export. `/stats` mein apne aap aa jayega.

7. **Dead code hataya**: risk_FIXED_OPTION1/2/3.py (koi import nahi karta tha).

## Audit — jo pehle se THEEK tha

- **Look-ahead bias nahi hai.** `auto_signal.py` band ho chuki candle
  use karta hai, phir live price se levels refresh karta hai. Sahi.
- **Duplicate protection sahi hai**: 15-min per-asset cooldown, exact
  duplicate message check, one-open-trade-per-asset. "3 signals ek saath"
  bug nahi tha — 3 alag coins the.
- **Secrets sahi hain**: BOT_TOKEN / CHANNEL_ID env vars se aate hain.
- **Thread safety**: trade_lock state mutations par lagta hai.

## R-MODEL — padhna zaroori

Bot orders execute nahi karta, isliye asli P&L kahin record nahi hota.
Metrics ek likhe hue model par bante hain: har trade equal one-third
TP1/TP2/TP3 par book, bacha hua SL/BE par. Ye ASLI paisa NAHI hai —
ye settings compare karne ka yardstick hai.

## Jo NAHI hua — aur kyun

**Is architecture mein possible hi nahi** (broker connection chahiye):
spread filter, max spread, slippage protection, execution quality,
dynamic position sizing, lot size validation, margin/free margin
validation, equity protection.
Ye ek *signal* bot hai — na account hai, na lot, na bid/ask.

**Data ke bina naapa nahi ja sakta** (backtester + history chahiye):
walk-forward, Monte Carlo, out-of-sample, realistic spread/commission
backtest, adaptive scoring, historical setup performance.

**Baaki (SMC detection, divergence, candle patterns, news filter,
RVOL, ATR percentile)**: ho sakta hai, par filters add karne se signals
girte hain aur bina backtester ke pata nahi chalega ki fayda hua ya
nuksaan. Isliye pehle backtester.

## Zaroori

Purane 84 signals ke stats galat measurement the. Deploy se PEHLE
`trades.json` ki copy bacha lo, phir stats zero se jama karo.
