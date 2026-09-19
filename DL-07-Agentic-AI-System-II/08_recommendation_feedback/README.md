# 08_recommendation_feedback

รื้อสร้างโมดูลนี้ใหม่ทั้งหมด รันจริงผ่าน Docker Compose: FastAPI +
PostgreSQL + Redis ไม่ใช้ mock ในหน่วยความจำสำหรับการเก็บข้อมูลอีกต่อไป

## โครงสร้าง

```
08_recommendation_feedback/
├── app/
│   ├── config.py        # ค่าตั้งจาก environment (pydantic-settings)
│   ├── schema.py         # RecommendationResponse / FeedbackSubmission (ตัว contract)
│   ├── mock_data.py       # fixture 5 ชุด (4 action code + สถานการณ์ฉุกเฉิน) พร้อม waypoint สำหรับแผนที่
│   ├── emergency.py       # ตรวจ official_contacts (region / effective_date / เบอร์โทร) ก่อนส่งให้ผู้ใช้
│   ├── db.py              # async SQLAlchemy + asyncpg — อ่าน/เขียน Postgres จริง
│   ├── feedback.py         # จัดหมวด feedback + ส่งต่อเข้าคิว safety review (เก็บใน DB)
│   ├── live_update.py      # consent/dedup/cooldown ของ alert บน Redis
│   ├── monitoring.py       # structlog + Prometheus แยก metric ด้านความปลอดภัยออกจาก UX
│   └── main.py             # FastAPI app / routes
├── tests/
│   ├── test_recommendation.py        # unit test — ไม่ต้องมี DB/Redis
│   ├── test_emergency_validation.py  # กฎตรวจเบอร์ฉุกเฉิน + การต่อกับ endpoint (patch db)
│   └── test_db_integration.py        # integration test — ต้อง `docker compose up` ก่อน
├── db_schema.sql           # DDL ของ Postgres รันอัตโนมัติตอน container เริ่มครั้งแรก
├── migrations/             # SQL รันครั้งเดียวสำหรับ volume ที่สร้างจาก schema เก่า
├── pytest.ini              # ให้ test แบบ async ที่ใช้ DB ใช้ event loop ร่วมกัน
├── Dockerfile
├── docker-compose.yml       # app + postgres + redis พร้อม healthcheck
├── .env.example             # คัดลอกเป็น .env ก่อนรัน
├── Makefile                 # make up / down / logs / rebuild / test
└── requirements.txt
```

## วิธีรัน

```bash
cp .env.example .env          # แก้ค่า credential ได้ตามต้องการ
docker compose up -d --build  # หรือ: make rebuild
docker compose ps             # ทั้ง 3 service ควรขึ้น "healthy" / "running"
```

ลองเรียกใช้:

```bash
curl http://localhost:8080/health
curl http://localhost:8080/recommendation/mock/avoid_travel
curl http://localhost:8080/recommendation/mock-req-004      # ดึงซ้ำจาก Postgres

curl -X POST http://localhost:8080/feedback -H "Content-Type: application/json" -d '{
  "request_id": "mock-req-004",
  "pseudonymous_user_id": "anon-42",
  "category": "UNSAFE",
  "comment": "This was wrong",
  "submitted_at": "2026-09-19T12:00:00Z"
}'

curl http://localhost:8080/feedback/safety-queue

curl -X POST http://localhost:8080/feedback/mock-req-004/review -H "Content-Type: application/json" -d '{
  "reviewer": "ops-alice",
  "approve_for_training": true
}'
```

รัน test:

```bash
make test              # unit test อย่างเดียว ไม่ต้องมี DB
make test-integration  # ทดสอบกับ container จริง (รัน `make up` ก่อน)
```

หยุดทุกอย่าง:

```bash
docker compose down          # เก็บ volume pgdata ไว้ (ประวัติคำแนะนำไม่หาย)
docker compose down -v       # ลบ volume ด้วย — ครั้งหน้าได้ DB ใหม่เปล่า
```

## การปรับให้ตรงกับ Contract (ทะเบียนสัญญาฉบับที่ 3)

ค่าที่ใช้ร่วมกันตอนนี้ตรงกับ 02 / 06 / 07 แล้ว:

- `risk_level` เป็น `LOW | MEDIUM | HIGH` (ไม่มี `MODERATE` และไม่มี `CRITICAL`)
- `action_code` เป็น `TRAVEL_NORMALLY | CHANGE_ROUTE | DELAY_TRAVEL | AVOID_TRAVEL`
  คำแนะนำฉุกเฉิน**ไม่ใช่** action ตัวที่ 5 แต่ส่งผ่าน
  `emergency_instructions` / `official_contacts` ซ้อนบน action ใดใน 4 ตัวนี้
  (สถานการณ์จำลอง `emergency_instructions` ใช้ `AVOID_TRAVEL` + `HIGH`)
- `emergency_instructions` / `official_contacts` รับค่า `null` ได้ (ตอนนี้ 03
  ส่ง `null` มา) และถือเป็นลิสต์ว่าง
- `db_schema.sql` มี CHECK constraint ของทั้งสองคอลัมน์แล้ว

**มี database เดิมอยู่แล้ว?** `db_schema.sql` รันเฉพาะตอนเริ่มครั้งแรก ดังนั้น
volume `pgdata` เก่ายังมีแถวที่เป็น `MODERATE` / `CRITICAL` (และ Redis อาจยังเก็บค่า
`live_update:last_risk:*` แบบเก่า ซึ่งระบบแปลงให้อัตโนมัติ) ให้เลือกอย่างใดอย่างหนึ่ง:
`docker compose down -v` (ตอน dev) หรือรัน
`docker compose exec -T postgres psql -U reco_user -d reco_db < migrations/001_three_risk_levels_four_actions.sql`
แถวที่ยังไม่ได้ migrate จะทำให้ `GET /recommendation/{id}` ตอบ 500 โดยตั้งใจ
เพื่อไม่ส่งข้อมูลที่ไม่ตรงกับ schema ปัจจุบันออกไป

## การตรวจเบอร์ฉุกเฉิน

`GET /recommendation/...` ทั้งสอง endpoint รับ `?region=TH` (ภูมิภาคของผู้เดินทาง)
และเรียก `emergency.validate_emergency_content` กับทุก response:

- เบอร์ที่ `effective_date` ยังไม่ถึง, รูปแบบเบอร์ผิด หรือ `region` ไม่ตรงกับผู้เดินทาง
  จะถูก**ตัดออก** (ไม่แก้ค่า)
- response จะมีข้อความใน `limitations` และรายการ `emergency_contacts` สถานะ
  `DEGRADED` ใน `degraded_services`
- ถ้าไม่ทราบ region จะคงเบอร์ไว้ แต่ใส่ข้อความใน limitation ว่ายังไม่ได้ยืนยัน
  (ตั้ง `strict_region=True` ในโค้ดเพื่อให้ตัดออกแทน)
- ถ้ายังมีคำแนะนำฉุกเฉินแต่ไม่เหลือเบอร์ที่ยืนยันได้เลย response จะบอกตรง ๆ

เบอร์ถูกเก็บตามที่ได้รับ และตรวจซ้ำทุกครั้งที่ส่งให้ผู้ใช้

## สิ่งที่เปลี่ยนจากเวอร์ชันก่อน

- **เก็บข้อมูลจริง** `feedback.py` และ `db.py` ตัวใหม่เขียนลงตาราง PostgreSQL
  (`recommendation_log`, `user_feedback`) แทน Python list ที่หายเมื่อ process รีสตาร์ท
- **ใช้ Redis จริง** `live_update.py` เชื่อม Redis container เป็นค่าเริ่มต้น
  ส่วน `FakeRedis` เก็บไว้ใช้เฉพาะ unit test ที่ไม่ควรต้องพึ่ง container
- **เพิ่ม waypoint ใน `RouteOption`** เพื่อให้ Web App วาดแผนที่ได้
  (ช่องโหว่ที่พบตอนเทียบกับแผนภาพสถาปัตยกรรม)
- **จัดโครงเป็น package** (`app/` + `tests/`) แทนไฟล์แบน ให้ตรงกับที่ Dockerfile
  คัดลอกและรัน (`uvicorn app.main:app`)
- **`db.wait_for_db()`** ลองเชื่อมซ้ำตอนเริ่ม เพราะ Postgres อาจใช้เวลาสองสามวินาที
  หลัง `docker compose up` แอปจึงรอแทนที่จะ crash วนซ้ำ

## การตัดสินใจที่ปิดแล้ว (บันทึกไว้เป็นประวัติ)

- **Emergency instructions เป็นหน้าที่ของ 07 ไม่ใช่ 08** ✅ ทีมตกลงแล้ว:
  07 สร้างข้อความ `emergency_instructions` และรายการ `official_contacts` ทั้งหมด
  ส่วน 08 รับ ตรวจ และแสดงผลเท่านั้น ไม่ต้องแก้ schema เพราะ
  `RecommendationResponse` ออกแบบไว้แบบนี้อยู่แล้ว หน้าที่ของ 08 (ตาม 01_env.txt:
  "Emergency text and contact numbers must match the user's location and have a
  valid effective date") คือตรวจสิ่งที่ 07 ส่งมาก่อนแสดง ซึ่งทำใน
  `app/emergency.py` แล้ว ดูหัวข้อ "การตรวจเบอร์ฉุกเฉิน" ด้านบน

## คำถามที่ยังค้างกับ upstream (03 / 07)

- **`confidence` เป็น nullable แล้ว** README ของ 03_travel_ai_agent ยืนยันว่า 07
  ส่ง confidence เป็น `LOW`/`MEDIUM`/`HIGH` ไม่ใช่ตัวเลข 0–1 และ 03 ส่งค่าตัวเลขเป็น
  `null` เพราะไม่ตรงกับ float ที่ 02 ต้องการ ดังนั้น
  `RecommendationResponse.confidence` เป็น `Optional[float]` และมี
  `confidence_level: Optional[ConfidenceLevel]` ใหม่เก็บค่าแบบหมวดหมู่ที่มีจริงตอนนี้
  ดู fixture `mock_data.DELAY_TRAVEL` ซึ่งจำลองกรณีจริงนี้
  (`confidence=None`, `confidence_level=MEDIUM`)
  **ยังค้าง:** ถ้า 07/02 ตกลงใช้ตัวเลขในภายหลัง ต้องตัดสินว่า 08 จะแปลง
  LOW/MEDIUM/HIGH เป็นตัวเลขเอง หรือรอให้ 07 ส่งมาทั้งสองแบบ
- **`SourceCitation` ง่ายกว่า canonical record ของ 05_data_integration** 05 แยก
  `observed_at`/`valid_at`/`issued_at`/`event_time` และสถานะ
  `missing`/`stale`/`unavailable` ต่อ record แต่ `SourceCitation` ของเรามีแค่
  `published_at` ยังไม่เป็นปัญหา เพราะข้อมูลละเอียดขนาดนั้นยังไม่ไหลจาก 07→08
  จริง ควรทบทวนเมื่อ 06/07 ส่ง evidence จริงมา

## ยังเป็น mock / ยังต้องเชื่อมต่อ

- `/recommendation/mock/{scenario}` ยังส่ง fixture 5 ชุดแทนผลการตัดสินใจจริงของ
  โมดูล 07 เมื่อ 07 พร้อมให้เพิ่ม endpoint `/recommendation/live` โดย schema และ
  เส้นทางเขียน DB (`db.save_recommendation`) ไม่ต้องแก้
- **การตรวจเบอร์ฉุกเฉินทำไปบางส่วน** บังคับ region, effective date และรูปแบบเบอร์แล้ว
  (ดูด้านบน) ที่ยังค้างและต้องตกลงกับทีม:
  1. `EMERGENCY_CONTACT_DIRECTORY_VERSION` อ่านเข้า config แต่ยังไม่ได้บังคับใช้ เพราะ
     เบอร์แต่ละรายการไม่มี directory version 07 ต้องส่งมาให้
  2. region ของผู้เดินทางมาจากไหน (ตอนนี้คือ query param `region` ที่ผู้เรียกส่งมา)
     เกี่ยวกับคำถามเรื่องพื้นที่ให้บริการ (ไทยอย่างเดียว หรือรวมต่างประเทศ)
- การส่งแจ้งเตือน (email/SMS/push) ยังไม่ได้ทำ — `NOTIFICATION_PROVIDER_KEYS`
  ถูกอ่านเข้า config แต่ยังไม่ถูกใช้จนกว่าจะเลือก provider
  (ตาม 01_env.txt: "install a provider SDK only after a provider is selected")
- OpenTelemetry มีการ import แต่ยังไม่ได้ต่อกับ collector — `monitoring.py`
  ตั้งค่าแค่ structlog และ Prometheus counter ในตอนนี้