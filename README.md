
# Huibot — Neon Postgres (Vercel)

## Env
- `TELEGRAM_TOKEN` — BotFather token
- `PUBLIC_URL` — https://<project>.vercel.app
- `WEBHOOK_SECRET` — random string
- `DATABASE_URL` — from Neon (e.g. postgres://... or postgresql://...), SSL required

## Deploy
1) Import project to Vercel → Deploy
2) Add env vars above → Redeploy
3) Open `/api/register-webhook` to set Telegram webhook

## Cron (optional)
- Monthly: `/api/cron/monthly` (add similar to previous if needed)
- Reminders: `/api/cron/reminders` (you can port same code from sqlite version if desired)
