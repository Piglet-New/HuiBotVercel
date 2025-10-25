# Huibot — Neon Postgres (Vercel)

## Env
- `TELEGRAM_TOKEN` — BotFather token
- `PUBLIC_URL` — your `https://*.vercel.app`
- `WEBHOOK_SECRET` — random string (for protecting admin endpoints)
- `DATABASE_URL` — from Neon (e.g. `postgresql://.../db?sslmode=require`)

## Deploy
1. Import this repo to Vercel → Python.
2. Set Environment Variables (above) → Redeploy.
3. Run migration **one time**:
   - `POST /api/migrate?secret=YOUR_SECRET`
4. Register Telegram webhook:
   - `POST /api/register-webhook?secret=YOUR_SECRET`
   - will call `https://api.telegram.org/bot<TOKEN>/setWebhook?url=<PUBLIC_URL>/webhook`
5. Chat your bot on Telegram.

## Cron (optional)
- Monthly: `GET /api/cron/monthly?secret=...`
- Reminders: `GET /api/cron/reminders?secret=...`