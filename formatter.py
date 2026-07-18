def format_signal(candles, result):
    reasons = "\n".join([f"✅ {reason}" for reason in result["reasons"]])

    return f"""
🤖 GOLD AI SCALPER PRO v2.0.3

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

🏆 Grade : {result['grade']}

🤖 AI Score : {result['ai_score']}/100

📈 Market : {result['market_status']}

━━━━━━━━━━━━━━━━━━

📢 Signal : {result['signal']}

🎯 Entry : {result['entry']}
🛑 Stop Loss : {result['sl']}

✅ TP1 : {result['tp1']}
✅ TP2 : {result['tp2']}

━━━━━━━━━━━━━━━━━━

📋 Reasons

{reasons}

━━━━━━━━━━━━━━━━━━

📈 Overall Trend : {result['trend_strength']}

🔥 Confidence : {result['confidence']}%

⚖️ Risk Reward : {result['risk_reward']}
"""
