def _check(ok, available=True):
    """FIX: pehle sirf ✅/❌ tha. Ab jis check ka data hi nahi hai wo '➖'
    dikhta hai -- warna user ko lagta tha VWAP fail ho raha hai, jabki
    asal mein wo check chal hi nahi raha tha."""
    if not available:
        return "➖ (no data)"
    return "✅" if ok else "❌"


def format_signal(candles, result, decimals=2, label=None):
    is_no_trade = result.get("signal") == "NO TRADE"
    reason_icon = "ℹ️" if is_no_trade else "✅"
    reasons = "\n".join(f"{reason_icon} {r}" for r in result.get("reasons", []))

    signal_emoji = {"BUY": "🟢", "SELL": "🔴", "NO TRADE": "🟡"}.get(
        result.get("signal"), "⚪")

    price = round(float(candles["price"]), decimals)
    asset_label = label or candles.get("asset", "GOLD")

    session_line = result.get("session", "-")
    if not result.get("session_active", True):
        session_line += " ⚠️"

    def _lvl(key):
        v = result.get(key)
        return v if v is not None else "-"

    def _targets():
        """Sirf wahi TP lines dikhao jo actually set hain -- single-target
        mode mein 'TP2 : -' dikhana confusing tha."""
        lines = []
        for i in (1, 2, 3):
            v = result.get(f"tp{i}")
            if v is not None:
                lines.append(f"✅ TP{i} : {v}")
        return "\n".join(lines) if lines else "✅ TP : -"

    ai_score = min(result["ai_score"], 100)

    return f"""🤖 AI SCALPER PRO V5.1 — {asset_label}

💰 Price : {price:.{decimals}f}

━━━━━━━━━━━━━━━━━━

🟢 AI Score : {ai_score}/100
🏆 Grade : {result['grade']}
📐 Setup : {result.get('confidence', '-')}
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
📊 ADX : {_check(result.get('adx_ok'))} ({result.get('adx_value', '-')})
📊 VWAP : {_check(result.get('vwap_ok'), result.get('vwap_available', True))}
📊 Supertrend : {_check(result.get('supertrend_ok'))}
📊 Volume : {_check(result.get('volume_ok'), result.get('volume_available', True))}
📊 Pattern : {result.get('pattern', 'None')}
📊 Liquidity Sweep : {result.get('liquidity_sweep', 'NO')}

━━━━━━━━━━━━━━━━━━

{signal_emoji} SIGNAL : {result['signal']}
📐 Tier : {result.get('signal_tier', '-')} ({result.get('position_size', '-')} of your normal risk)

🎯 Entry : {_lvl('entry')}
🛑 SL : {_lvl('sl')}
{_targets()}

⚖️ RR (net of spread) : {result['risk_reward']}

━━━━━━━━━━━━━━━━━━

📋 Reasons

{reasons if reasons else 'No confirmations'}

━━━━━━━━━━━━━━━━━━

📊 Buy : {result.get('buy_directional', 0)} directional / {result['buy_confirmations']} total
📉 Sell : {result.get('sell_directional', 0)} directional / {result['sell_confirmations']} total

⏰ Valid : {result.get('valid_minutes', 8)} Minutes
"""
