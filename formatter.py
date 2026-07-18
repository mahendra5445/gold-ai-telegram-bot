def format_signal(candles, result):
    """
    Format Telegram Message
    """

    trend = result["trend"]["trend"]
    trend_score = result["trend"]["score"]

    reasons = result["reason"]

    if len(reasons) == 0:
        reason_text = "No confirmation"

    else:
        reason_text = "\n".join([f"• {x}" for x in reasons])

    smc = result["smart_money"]

    mtf_text = "Not Available"

    if result["mtf"]:

        mtf = result["mtf"]

        mtf_text = ""

        for tf, signal in mtf["timeframes"].items():
            mtf_text += f"{tf} : {signal}\n"

        mtf_text += f"\nOverall : {mtf['overall']}"

    message = f"""
🤖 GOLD AI SCALPER PRO V3

━━━━━━━━━━━━━━━━━━

📈 Signal : {result['signal']}

💰 Price : {result['price']}

🎯 Entry : {result['entry']}

🛑 Stop Loss : {result['sl']}

✅ TP1 : {result['tp1']}

✅ TP2 : {result['tp2']}

━━━━━━━━━━━━━━━━━━

🤖 AI Score : {result['score']}

📊 Confidence : {result['confidence']}%

📈 Trend : {trend}

🔥 Trend Score : {trend_score}

━━━━━━━━━━━━━━━━━━

📊 EMA20 : {round(result['ema20'],2)}

📊 EMA50 : {round(result['ema50'],2)}

📊 EMA200 : {round(result['ema200'],2)}

RSI : {round(result['rsi'],2)}

ATR : {round(result['atr'],2)}

━━━━━━━━━━━━━━━━━━

🧠 SMART MONEY

BOS : {"✅" if smc["bos"] else "❌"}

CHOCH : {"✅" if smc["choch"] else "❌"}

ORDER BLOCK : {smc["order_block"]}

FVG : {"✅" if smc["fvg"] else "❌"}

LIQUIDITY : {"✅" if smc["liquidity"] else "❌"}

━━━━━━━━━━━━━━━━━━

⏰ MULTI TIMEFRAME

{mtf_text}

━━━━━━━━━━━━━━━━━━

⚖ Risk Reward

{result['risk_reward']}

━━━━━━━━━━━━━━━━━━

💡 WHY THIS TRADE?

{reason_text}

━━━━━━━━━━━━━━━━━━

⚠ Trade Responsibly
"""

    return message
