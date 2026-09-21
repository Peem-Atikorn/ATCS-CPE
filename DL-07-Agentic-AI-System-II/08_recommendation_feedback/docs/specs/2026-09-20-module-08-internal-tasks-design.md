# Design Specification: Module 08 Internal Tasks & Architecture Alignment

- **Date:** 2026-09-20
- **Status:** Proposed (Under Review)
- **Module:** `08_recommendation_feedback`
- **Related Modules:** `01_web_app`, `02_api_backend`, `07_decision_llm_engine`

---

## 1. Background & Architectural Resolution (02 vs 08)

### ปัญหาเดิม:
โมดูล 08 ถูกออกแบบให้มี endpoint `GET /recommendation/{id}` และ `POST /feedback` ซึ่งเลียนแบบสไตล์ public API ทำให้เกิดความสับสนในตารางกลาง (Contract Register v4) ว่า:
> *"01 (Web App) ต้องเรียกคำแนะนำจาก 02 หรือ 08 กันแน่?"*

เพราะโมดูล 08 พยายามทำตัวเป็นทั้ง **"หน้าร้าน (Public Storefront)"** และ **"ผู้ประมวลผล (Worker/Engine)"** ในเวลาเดียวกัน

### ข้อยุติทางสถาปัตยกรรม (Architecture Decision):
1. **02_api_backend เป็น Single Public Gateway / BFF หน้าร้านเดียวสำหรับ 01**:
   - Client หน้าบ้าน (01 Web App) คุยกับ 02 เท่านั้น (`/v1/travel/...`, `/v1/recommendations/...`)
   - 02 มีหน้าที่ดูแล Auth (Keycloak JWT), Rate Limiting, Idempotency, Session, และ Routing
2. **08_recommendation_feedback เป็น Internal Domain Service / Worker**:
   - ทำหน้าที่เฉพาะทาง (Single Responsibility) ด้าน:
     - การจัดรูปแบบคำแนะนำ (`RecommendationResponse`)
     - การตรวจสอบความถูกต้องและปลอดภัยของข้อมูลฉุกเฉิน (`emergency.py`)
     - การจัดเก็บประวัติและสถิติการแสดงผลคำแนะนำ (`recommendation_log`)
     - ระบบคัดกรองและคิวตรวจสอบความปลอดภัยของข้อเสนอแนะ (`user_feedback`, `safety review queue`)
     - กลไก Throttling / Cooldown สำหรับ Live Update (`live_update.py`)
3. **ไม่สร้าง Alias `/v1/...` ในโมดูล 08**:
   - เพื่อป้องกันไม่ให้ path ชนหรือทับซ้อนกับ Public API ของ 02 โดยเด็ดขาด
   - Endpoint ของ 08 จะใช้ Prefix ภายในของตนเอง เช่น `/recommendation/...` และ `/feedback/...` เพื่อให้เป็น internal service ชัดเจน

---

## 2. Specification of Internal Tasks

### Task 1: แก้ไข Assertion ใน `tests/test_decision_client.py`
- **สาเหตุ:** เคส `test_adapter_emergency_contacts_filtered_on_mismatched_region` ตรวจหาคำว่า `"region"` ใน `reco.limitations` ซึ่งตามกฎของ `app/emergency.py` ข้อความ `NO_VERIFIED_CONTACTS_NOTE` ใช้คำว่า `"location"` ส่วนรหัสเหตุผล `"region_mismatch"` ถูกบันทึกไว้ใน `reco.degraded_services[0].detail`
- **การแก้ไข:** ปรับ assertion ให้ตรวจสอบ:
  - `reco.official_contacts == []`
  - `any("region_mismatch" in deg.detail for deg in reco.degraded_services)`
  - `NO_VERIFIED_CONTACTS_NOTE in reco.limitations`
- **เป้าหมาย:** ผ่าน 54/54 tests ครบ 100%

### Task 2: จัดการ Endpoint ใน `app/main.py`
- **ฟื้นฟู Endpoint Internal Query `GET /recommendation/{request_id}`**:
  - ใช้สำหรับ service ภายใน หรือ Ops เครื่องมือตรวจสอบ ดึงข้อมูลคำแนะนำที่บันทึกไว้ใน `recommendation_log`
  - มี validation schema และ re-check emergency contacts ตามภูมิภาค
- **คงไว้ซึ่ง `POST /recommendation/generate`**:
  - เป็น Internal Endpoint สำหรับรับ payload การตัดสินใจจาก Module 07 มา format และ persist

### Task 3: ระบบ Automated Feedback Retention Cleanup (180 วัน)
- **ฟังก์ชันใน `app/db.py`**:
  - `async def purge_expired_feedback(retention_days: int = 180) -> int`
  - รันคำสั่ง SQL ลบแถวใน `user_feedback` ที่มี `submitted_at < NOW() - retention_days` และคืนค่าจำนวนแถวที่ถูกลบ
- **Background Runner ใน `app/main.py` lifespan**:
  - สร้าง background task ทำงานแบบ periodic (ทุก 24 ชั่วโมง) คอยเรียก `purge_expired_feedback` โดยไม่บล็อก startup loop
- **Internal Trigger Endpoint**:
  - `POST /feedback/cleanup` สำหรับให้ Cron ภายนอกหรือ Operator สั่ง trigger รันล้างข้อมูลทันที

### Task 4: โครงสร้าง Notification Provider & Directory Version
- **ใน `app/live_update.py`**:
  - เพิ่ม helper class `NotificationDispatcher` จัดการการส่งแจ้งเตือนผ่าน Provider ต่างๆ
  - หาก `settings.notification_provider_keys` เป็นค่าว่าง ให้ fallback เป็น structured logging (`logger.info("notification_dispatched_noop", ...)`) โดยไม่ crash
- **Directory Version**:
  - รองรับการตรวจสอบ field `directory_version` ใน metadata ของเบอร์ฉุกเฉินเมื่อส่งมาจาก 07

### Task 5: อัปเดต Root `.env.example`
- ปรับค่า `FEEDBACK_RETENTION_DAYS=180` ใน root `.env.example` ให้สอดคล้องกับ Module 02 (P-23) และ `08_recommendation_feedback/app/config.py`

---

## 3. Verification Plan
1. รัน `pytest` ครบทุกไฟล์ใน `08_recommendation_feedback/tests/` (54+ เคสต้องผ่านทั้งหมด)
2. เขียน Unit Test เพิ่มเติมสำหรับ:
   - `GET /recommendation/{request_id}` (เคสพบข้อมูล / ไม่พบข้อมูล)
   - `purge_expired_feedback` (การลบข้อมูลตามช่วงเวลา)
   - Background retention loop
3. ตรวจสอบ syntax และ linter ไม่ให้มีข้อผิดพลาด
