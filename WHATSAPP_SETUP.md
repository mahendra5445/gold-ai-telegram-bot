# WhatsApp Cloud API Setup

Bot ab Telegram ke saath-saath WhatsApp pe bhi signals bhej sakta hai.

## 1. Meta se credentials lo

[developers.facebook.com](https://developers.facebook.com) → apni app → **WhatsApp → API Setup**:

| Cheez | Kahan milegi |
|---|---|
| **Phone number ID** | API Setup page pe, "From" number ke neeche |
| **Access token** | Temporary token 24 ghante mein expire hota hai. **Permanent token banao**: Business Settings → System Users → Add → Assign the WhatsApp app → Generate token (`whatsapp_business_messaging` + `whatsapp_business_management` permissions) |

## 2. Railway pe environment variables set karo

Railway → project → **Variables**:

```
WHATSAPP_TOKEN            = <permanent access token>
WHATSAPP_PHONE_NUMBER_ID  = <phone number id>
WHATSAPP_VERIFY_TOKEN     = ai_scalper_pro_2026
```

`PORT` set mat karo — Railway khud inject karta hai.

Deploy hone ke baad browser mein khol ke check karo:

```
https://gold-ai-telegram-bot-production.up.railway.app/health
```

`{"status":"ok", ...}` aana chahiye. Agar ye nahi aaya to webhook bhi verify nahi hoga — pehle isko theek karo.

> **Railway note:** Service ko public domain hona chahiye. Settings → Networking → **Generate Domain**. Bina domain ke Meta reach hi nahi kar payega.

## 3. Meta mein webhook configure karo

**WhatsApp → Configuration → Webhook → Edit**:

- **Callback URL:** `https://gold-ai-telegram-bot-production.up.railway.app/webhook`
- **Verify token:** `ai_scalper_pro_2026` (bilkul wahi jo env var mein hai)

**Verify and Save** dabao. Green tick aana chahiye.

Phir neeche **Manage** → `messages` field ko **Subscribe** karo. Ye step bhool gaye to verification pass ho jayegi par koi message kabhi nahi aayega.

## 4. Test karo

Apne WhatsApp se business number pe bhejo:

| Message | Kya hoga |
|---|---|
| `START` | Subscribe — ab har signal aayega |
| `STOP` | Unsubscribe |
| `STATUS` | Live stats (expectancy, win rate, open trades) |

Subscribers `data/wa_subscribers.json` mein save hote hain — restart ke baad bhi rehte hain (bashart-e DATA_DIR persistent disk pe ho).

## 5. Zaroori: 24-hour window

Meta free-form text sirf tab bhejne deta hai jab user ne pichhle **24 ghante** mein aapko koi message bheja ho. Uske baad signals silently fail honge (log mein `131047` error dikhega).

Do options:

1. **Aasan:** users ko bolo roz ek baar `STATUS` bhej dein — window reset ho jaati hai.
2. **Proper:** Meta mein ek **message template** approve karao aur us se signals bhejo. Template approval mein 1-2 din lagte hain.

Abhi code option 1 pe chal raha hai.

## Troubleshooting

| Problem | Wajah |
|---|---|
| Webhook verify fail | Verify token match nahi, ya `/health` hi nahi khul raha (service down / domain generate nahi hua) |
| Verify pass, messages nahi aate | `messages` field subscribe nahi kiya |
| Messages aate hain, reply nahi jaata | Token expire (temporary token tha) ya galat Phone number ID |
| `ModuleNotFoundError: flask` | `requirements.txt` mein `flask==3.0.3` missing |
| Kuch der baad sends fail | 24-hour window band ho gayi — upar section 5 dekho |

Logs mein sab kuch `[WA]` prefix ke saath aata hai — Railway logs mein `WA` search karo.
