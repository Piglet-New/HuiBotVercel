# HuiBot Telegram - Quản lý thẻ tín dụng (VN)

Bot Telegram hỗ trợ quản lý thẻ tín dụng, tư vấn thẻ tốt nhất cho chi tiêu, ghi nhận giao dịch theo xác nhận, theo dõi ưu đãi và nhắc thanh toán. Chạy trên **Google Cloud Run** và dùng **Firestore Native mode**.

## Bật API cần thiết (GCP)
- Cloud Run API
- Cloud Scheduler API
- Firestore API
- Secret Manager API (nếu dùng)

## Thiết lập Firestore
1. Tạo project GCP.
2. Tạo Firestore ở **Native mode**.
3. Bật service account có quyền Firestore (Cloud Run dùng mặc định).

## Biến môi trường
Xem `.env.example`.
- `TELEGRAM_BOT_TOKEN` (bắt buộc)
- `WEBHOOK_SECRET` (bắt buộc)
- `JOB_SECRET` (bắt buộc)
- `GCP_PROJECT_ID` (bắt buộc)
- `REGION` (mặc định `asia-southeast1`)
- `GEMINI_API_KEY` (tuỳ chọn)
- `ADMIN_TELEGRAM_USER_IDS` (tuỳ chọn)

## Thiết lập Secret Manager (tuỳ chọn)
```bash
echo -n "YOUR_TOKEN" | gcloud secrets create TELEGRAM_BOT_TOKEN --data-file=-
gcloud run services update hui-bot \
  --set-secrets TELEGRAM_BOT_TOKEN=TELEGRAM_BOT_TOKEN:latest
```

## Chạy local
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8080
```

## Thiết lập webhook Telegram
```bash
curl -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook" \
  -d "url=https://YOUR_DOMAIN/telegram/webhook/$WEBHOOK_SECRET"
```

## Deploy Cloud Run
```bash
gcloud run deploy hui-bot \
  --source . \
  --region $REGION \
  --allow-unauthenticated \
  --set-env-vars TELEGRAM_BOT_TOKEN=... \
  --set-env-vars WEBHOOK_SECRET=... \
  --set-env-vars JOB_SECRET=... \
  --set-env-vars GCP_PROJECT_ID=...
```

## Cloud Scheduler (nhắc thanh toán)
Tạo job gọi mỗi ngày 09:00 Asia/Ho_Chi_Minh:
```bash
gcloud scheduler jobs create http hui-bot-reminders \
  --schedule="0 9 * * *" \
  --time-zone="Asia/Ho_Chi_Minh" \
  --uri="https://YOUR_DOMAIN/jobs/send_reminders?job_secret=$JOB_SECRET" \
  --http-method=POST
```

## Job crawl ưu đãi
```bash
curl -X POST "https://YOUR_DOMAIN/jobs/crawl_offers?job_secret=$JOB_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"urls": ["https://example.com/uu-dai"]}'
```

## Seed ưu đãi
`promos.yaml` được nạp vào Firestore khi app khởi động (marked `needs_confirmation=true`).

## Kiểm thử
**Checklist**
- `pytest` (nếu có môi trường Firestore giả lập).
- Kiểm tra webhook hoạt động.
- Kiểm tra tư vấn và xác nhận giao dịch.
- Kiểm tra job nhắc thanh toán.

## Checklist hoàn thành
- Webhook hoạt động, gửi/nhận tin.
- Tư vấn thẻ bằng tiếng Việt.
- Lưu giao dịch khi có "xác nhận".
- Nhắc thanh toán với nút "✅ Đã thanh toán".
