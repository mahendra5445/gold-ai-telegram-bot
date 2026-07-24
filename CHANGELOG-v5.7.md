# v5.7 — bug fixes + real broker spreads

## Do bugs jo v5.6 mein the

1. **backtest.py crash** — `min_sl_pct` `run()` mein nikalta tha par
   `_engine()` ko pass nahi hota tha → `NameError`. Koi bhi backtest
   chalta hi nahi tha. Per-asset min_sl_pct wala fix adhoora reh gaya tha.
2. **`--sweep-sl` / `--sweep-tp` `--csv` ignore karte the** — chupchaap
   Yahoo se data khinchte the. Purane sweep results galat data pe the.

## Naya

- **Real broker spreads** config mein (24-Jul-2026 MT5 screenshots se).
  EURUSD pehle 0.8 pip maana gaya tha, asli 0.2 pip hai — 4x farq.
- **silver (XAGUSD)** asset registry mein add hua.
- **`--tf-mult N`** — signal timeframe scaler. 1 = 1m/5m/15m (default),
  3 = 3m/15m/45m. `--max-bars` ab tf ke hisaab se apne aap scale hota hai.

## Naapa gaya (100 din M1, asli spread par)

| asset  | expectancy | trades | spread |
|--------|-----------|--------|--------|
| gold   | +0.160 R  | 287    | 0.35   |
| eurusd | +0.025 R  | 302    | 0.2 pip|
| silver | -0.001 R  | 320    | 0.040  |
| gbpusd | -0.074 R  | 297    | 1.4 pip|
| usdjpy | -0.077 R  | 263    | 1.2 pip|

ASSET_LIST mein sirf gold + eurusd on hain. Baaki comment kiye hain,
ek line hata ke on kiye ja sakte hain.

## Warning

Ye spreads EK screenshot ke hain (1:16-1:19 baje). News, rollover aur
patli liquidity mein spread chaudha hota hai. Agar account ECN/raw hai
to **commission alag se lagta hai** — wo bhi cost hai aur abhi count
nahi hui. Live jaane se pehle demo par forward test zaroori hai.
