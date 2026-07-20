def _check(ok):
    return "✅" if ok else "❌"


def format_signal(candles, result):
    is_no_trade = result.get("signal") == "NO TRADE"
    reason_icon = "ℹ️" if is_no_trade else "✅"
    reasons = "\n".join(f"{reason_icon} {r}" for r in result.get("reasons", []))

    signal_emoji = {
        "BUY": "🟢",
        "SELL": "🔴",
        "NO TRADE": "🟡",
    }.get(result.get("signal"), "⚪")

    price = round(float(candles["price"]), 2)

    session_line = result.get("session", "-")
    if not result.get("session_active", True):
        session_line += " ⚠️"

    # Display-side safety net - always clamp to 100 even if a future edit
    # upstream forgets to cap them.
    ai_score_display = min(result['ai_score'], 100)
    confidence_display = min(result['confidence'], 100)

    return f"""🤖 GOLD AI SCALPER PRO V5.0

💰 Price : {price:.2f}

━━━━━━━━━━━━━━━━━━

🟢 AI Score : {ai_score_display}/100
🏆 Grade : {result['grade']}
⭐ Confidence : {confidence_display}%
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
📐 Tier : {result.get('signal_tier', '-')} ({result.get('position_size', '-')} Position Size)

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
