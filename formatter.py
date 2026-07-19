def format_signal(candles, result):
    reasons = "\n".join(f"✅ {r}" for r in result.get("reasons", []))

    signal_emoji = {
        "BUY": "🟢",
        "SELL": "🔴",
        "NO TRADE": "🟡",
    }.get(result.get("signal"), "⚪")

    price = round(float(candles["price"]), 2)

    return f"""🤖 GOLD AI SCALPER PRO v3.2

💰 Price : {price:.2f}

━━━━━━━━━━━━━━━━━━

⏱️ 1M Trend : {result['trend_1m']}
⏱️ 5M Trend : {result['trend_5m']}
⏱️ 15M Trend : {result['trend_15m']}

━━━━━━━━━━━━━━━━━━

📈 EMA20 : {result['ema20']}
📈 EMA50 : {result['ema50']}
📈 EMA200 : {result['ema200']}

📊 RSI : {result['rsi']}
📊 MACD : {result['macd']['trend']}
📊 ATR : {result['atr']}
📊 ADX : {result['adx']}

━━━━━━━━━━━━━━━━━━

🏆 Grade : {result['grade']}
🤖 AI Score : {result['ai_score']}/100
⭐ Signal Quality : {result['signal_quality']}
📈 Market : {result['market_status']}

━━━━━━━━━━━━━━━━━━

{signal_emoji} Signal : {result['signal']}

🎯 Entry : {result['entry']}
🛑 Stop Loss : {result['sl']}
✅ TP1 : {result['tp1']}
✅ TP2 : {result['tp2']}

━━━━━━━━━━━━━━━━━━

📊 Buy Confirmations : {result['buy_confirmations']}
📉 Sell Confirmations : {result['sell_confirmations']}

━━━━━━━━━━━━━━━━━━

📋 Reasons

{reasons if reasons else 'No confirmations'}

━━━━━━━━━━━━━━━━━━

📈 Overall Trend : {result['trend_strength']}
🔥 Confidence : {result['confidence']}%
⚖️ Risk Reward : {result['risk_reward']}
"""
