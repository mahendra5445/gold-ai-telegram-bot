def format_signal(candles, result):
    message = (
        "📊 GOLD AI SCALPER PRO\n\n"
        f"💰 Price : {candles['price']}\n\n"
        f"📈 EMA20 : {result['ema20']}\n"
        f"📈 EMA50 : {result['ema50']}\n"
        f"📈 EMA200 : {result['ema200']}\n\n"
        f"📉 RSI : {result['rsi']}\n"
        f"📊 MACD : {result['macd']['trend']}\n\n"
        f"🎯 Signal : {result['signal']}\n"
    )

    if result["entry"] is not None:
        message += (
            f"\n💰 Entry : {result['entry']}\n"
            f"🛑 Stop Loss : {result['sl']}\n"
            f"🎯 TP1 : {result['tp1']}\n"
            f"🎯 TP2 : {result['tp2']}\n"
            f"\n📈 Confidence : {result['confidence']}%"
        )

        if "risk_reward" in result:
            message += f"\n⚖️ Risk : Reward : {result['risk_reward']}"

        if "atr" in result:
            message += f"\n📉 ATR : {result['atr']}"

        if "trend_strength" in result:
            message += f"\n📊 Trend : {result['trend_strength']}"

    return message
