def _check(ok):
    return "✅" if ok else "❌"


def format_signal(candles, result):
    reasons = "\n".join(f"✅ {r}" for r in result.get("reasons", []))

    signal_emoji = {
        "BUY": "🟢",
        "SELL": "🔴",
        "NO TRADE": "🟡",
    }.get(result.get("signal"), "⚪")

    price = round(float(candles["price"]), 2)

    session_line = result.get("session", "-")
    if not result.get("session_active", True):
        session_line += " ⚠️"

    return f"""🤖 GOLD AI SCALPER PRO v4.0

💰 Price : {price:.2f}

━━━━━━━━━━━━━━━━━━

🟢 AI Score : {result['ai_score']}/100
🏆 Grade : {result['grade']}
⭐ Confidence : {result['confidence']}%
📈 Market : {result['market_status']}
🕘 Session : {session_line}

━━━━━━━━━━━━━━━━━━

🕒 1M : {result['trend_1m']}
🕒 5M : {result['trend_5m']}
🕒 15M : {result['trend_15m']}

━━━━━━━━━━━━━━━━━━

📊 EMA : {_check(result.get('ema_ok'))}
📊 MACD : {result['macd']['trend']}
📊 RSI : {result['rsi']}
📊 ADX : {_check(result.get('adx_ok'))}
📊 VWAP : {_check(result.get('vwap_ok'))}
📊 Supertrend : {_check(result.get('supertrend_ok'))}
📊 Volume : {_check(result.get('volume_ok'))}
📊 Pattern : {result.get('pattern', 'None')}
📊 Liquidity Sweep : {result.get('liquidity_sweep', 'NO')}

━━━━━━━━━━━━━━━━━━

{signal_emoji} SIGNAL : {result['signal']}

🎯 Entry : {result['entry']}
🛑 SL : {result['sl']}
✅ TP1 : {result['tp1']}
✅ TP2 : {result['tp2']}
✅ TP3 : {result['tp3']}

⚖️ RR : {result['risk_reward']}

━━━━━━━━━━━━━━━━━━

📋 Reasons

{reasons if reasons else 'No confirmations'}

━━━━━━━━━━━━━━━━━━

📊 Buy Confirmations : {result['buy_confirmations']}
📉 Sell Confirmations : {result['sell_confirmations']}

⏰ Valid : {result.get('valid_minutes', 8)} Minutes
"""
