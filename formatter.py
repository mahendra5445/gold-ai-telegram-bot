def format_signal(candles, result):
    return f"""
🤖 GOLD AI SCALPER PRO

💰 Price : {candles['price']}

━━━━━━━━━━━━━━

📈 EMA20 : {result['ema20']}
📈 EMA50 : {result['ema50']}
📈 EMA200 : {result['ema200']}

━━━━━━━━━━━━━━

📊 RSI : {result['rsi']}

📊 MACD : {result['macd']['trend']}

━━━━━━━━━━━━━━

📢 Signal : {result['signal']}

🎯 Entry : {result['entry']}

🛑 Stop Loss : {result['sl']}

✅ TP1 : {result['tp1']}

✅ TP2 : {result['tp2']}

━━━━━━━━━━━━━━

⚖ Risk Reward : {result['risk_reward']}

📈 Trend : {result['trend_strength']}

🔥 Confidence : {result['confidence']}%
"""
