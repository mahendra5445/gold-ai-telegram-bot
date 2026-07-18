def format_signal(candles, result):
    return f"""
🤖 GOLD AI SCALPER PRO v2.0.2

💰 Price : {candles['price']}

━━━━━━━━━━━━━━━━━━

⏱️ 1M Trend : {result['trend_1m']}
⏱️ 5M Trend : {result['trend_5m']}
⏱️ 15M Trend : {result['trend_15m']}

━━━━━━━━━━━━━━━━━━

📈 EMA20 : {result['ema20']}
📈 EMA50 : {result['ema50']}
📈 EMA200 : {result['ema200']}

━━━━━━━━━━━━━━━━━━

📊 RSI : {result['rsi']}
📊 MACD : {result['macd']['trend']}
📊 ATR : {result['atr']}
📊 ADX : {result['adx']}

━━━━━━━━━━━━━━━━━━

📢 Signal : {result['signal']}

🎯 Entry : {result['entry']}
🛑 Stop Loss : {result['sl']}

✅ TP1 : {result['tp1']}
✅ TP2 : {result['tp2']}

━━━━━━━━━━━━━━━━━━

📈 Overall Trend : {result['trend_strength']}

🔥 Confidence : {result['confidence']}%

⚖️ Risk Reward : {result['risk_reward']}
"""
