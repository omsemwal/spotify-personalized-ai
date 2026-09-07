# 👤 Member 1 — Ingestion API

**Folder**: `services/ingestion-api/`  
**Assigned To**: Member 1 (Ingestion Developer)

---

## 🎯 What is this service for? (Simple Words)
This is the **front door** of the system. Whenever a user plays a song, chats with AI, or changes a setting, this API receives the event, checks if it's allowed, and sends it to Kafka so other services can process it.

---

## 📥 API to Build
- **URL**: `POST /v1/events`
- **Input**: User event data (`subject_id`, `event_type`, `payload`, `consent_state`)

---

## 📝 Simple Steps to Complete
1. **Create FastAPI app**: Write main app code in `main.py`.
2. **Check Consent**: If user consent is `"denied"`, reject the request (`403 Forbidden`).
3. **Check Duplicate (Redis)**: Look up `idempotency_key` in Redis. If seen before, reject duplicate (`400 Bad Request`).
4. **Send to Kafka**: Push the event to Kafka topic `interaction-events`.
5. **Return Success**: Send back `202 Accepted` with an `event_id`.

---

## 🧪 How to Test
1. Run `uvicorn main:app --reload`
2. Send a POST request to `http://localhost:8000/v1/events` using Postman or cURL.
3. Check Kafka to make sure the event arrived!
