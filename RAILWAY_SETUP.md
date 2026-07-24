# Railway Deploy Guide (Hindi)

## 1. Project banao
- Railway dashboard → New Project → Deploy from GitHub repo
  (ya "Empty Project" + code upload)

## 2. Environment Variables set karo
Project → Variables tab mein add karo:

| Variable   | Value              |
|------------|--------------------|
| BOT_TOKEN  | <apna telegram bot token> |
| DATA_DIR   | /data              |
| LOG_DIR    | /data/logs         |

## 3. Volume attach karo (IMPORTANT!)
Railway ka filesystem bhi ephemeral hai — har deploy/restart pe
files delete ho jaati hain. Volume ke bina trades.json aur
admins.json har baar reset ho jayenge.

- Service pe right-click (ya service settings) → "Attach Volume"
- Mount path: `/data`
- Bas — ab DATA_DIR=/data ki wajah se saara data volume pe
  save hoga aur restarts/deploys pe bacha rahega.

Note: Volumes Railway ke Hobby plan ($5/month) pe milte hain.
Agar volume nahi lagate to bot phir bhi chalega, lekin har
restart pe trade history aur registered users reset ho jayenge
(users ko dobara /start bhejna padega).

## 4. Deploy
Push/deploy karo — logs mein yeh dikhna chahiye:
```
[INIT] Background tasks started
🚀 Gold AI Scalper Pro V5.0 starting…
```

## 5. Test
Telegram pe bot ko /start bhejo, phir /gold, /eurusd, /gbpusd
ya /usdjpy.
