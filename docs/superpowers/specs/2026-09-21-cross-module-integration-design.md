# สเปกการรวมระบบและแก้ไขจุดขัดแย้งข้ามโมดูล (Cross-Module Integration & Contract Alignment Design Specification)

**วันที่มีผล:** 21 กันยายน 2026  
**สถานะ:** Approved Design — พร้อมสำหรับการจัดทำแผนปฏิบัติการ (Implementation Plan)  
**เอกสารอ้างอิง:** 
- ทะเบียนสัญญาระหว่างโมดูล (Cross-Module Contract Register) ฉบับที่ 10 (21 กันยายน 2026)
- ข้อกำหนดระบบ `DL-07-Agentic-AI-System-II/02_api_backend/docs/02_api_spec.md`

---

## 1. บริบทและปัญหาที่ต้องแก้ไข (Context & Problem Statement)

จากการประเมินสัญญาระหว่างโมดูลฉบับที่ 10 พบว่าแม้ระบบหลักจะมีการทดสอบผ่านในระดับหน่วยย่อย (รวม 1,297 เคส) แต่เมื่อรัน Pipeline เชื่อมต่อจริงระหว่าง `03_travel_ai_agent` สู่โมดูลข้อมูล `04/05/06` และ `07_decision_llm_engine` กลับพบปัญหาสำคัญที่ทำให้ระบบไม่สามารถทำงานร่วมกันได้อย่างสมบูรณ์:

1. **คอขวดผลลัพธ์ AVOID ทุกกรณี (05 → 03 → 07):** 
   - `05_data_integration` ไม่ได้คำนวณและส่งค่า `confidence` และ `active_restriction` ออกมาจากฟังก์ชัน `build_context()`
   - ส่งผลให้ `03_travel_ai_agent` ต้องใช้ค่า fallback (`confidence = "LOW"`, `active_restriction = None`)
   - `07_decision_llm_engine` จึงบังคับยกระดับการตัดสินใจ (Escalation) ให้ทุกเส้นทางตอบกลับเป็น `action_code = "AVOID"` เสมอ แม้เส้นทางจะปลอดภัย 100%
2. **ปัญหา Coverage 6 Kinds (05 → 06 → 07):** 
   - `06_risk_knowledge_services` บังคับให้ segment ต้องครอบคลุมข้อมูลครบ 6 kinds (`current_weather`, `weather_forecast`, `transport_status`, `closure`, `disaster_event`, `official_alert`)
   - ในความเป็นจริง `04_external_data_services` มีผู้ผลิตจริงเพียง 4 kinds (ขาด `closure` และ `official_alert`) และ 03 ยังไม่ได้เชื่อมต่อ canonical weather ส่งเข้า 05 ทำให้ทุก segment ติดสถานะ `missing` ตลอดเวลา
3. **สัญญา API ไม่ตรงกัน (01 ↔ 02):** 
   - หน้าบ้าน `01_web_app` ส่งโครงสร้าง Request ไม่ตรงกับ Gateway `02_api_backend` (เช่น ชื่อ field พิกัด, รูปแบบเวลา, และขาด `timezone`) ซึ่ง 02 ตั้งค่า `extra="forbid"` ทำให้ตอบกลับด้วย `422 Unprocessable Entity` ทุกครั้ง
   - 01 ยังไม่มีการต่อ Keycloak OIDC (ไม่มี Bearer Token) ทำให้ติด `401 Unauthenticated`
   - 01 มีค่า Enum `RiskLevel.CRITICAL` ซึ่งระบบส่วนกลางไม่มี
4. **ความเสี่ยงพอร์ตชนกันบน Host (02 ↔ 03 ↔ 08):** 
   - การรัน Docker Compose ของแต่ละโมดูลพร้อมกันจะทำให้พอร์ต 5432 (Postgres), 6379 (Redis) และ 8010 (Agent) ชนกัน

สเปกฉบับนี้กำหนดวิธีแก้ไขจุดขัดแย้งเหล่านี้อย่างเป็นระบบ และกำหนดมาตรฐานการทดสอบการใช้งานจริงบน Docker Stack (Containerized E2E Test)

---

## 2. ภาพรวมสถาปัตยกรรมการเชื่อมต่อ (System Architecture Overview)

```
[01 Web App (Next.js)]
         │
         │  1. OAuth 2.0 PKCE Login
         ▼
[Keycloak OIDC :8180] ──► ได้รับ JWT Access Token
         │
         │  2. POST /v1/travel/recommendations (Bearer Token)
         ▼
[02 API Backend Gateway (FastAPI) :8000]
         │
         │  3. POST /runs (Agent Contract §9)
         ▼
[03 Travel AI Agent (LangGraph) :8010]
   ├── [04 External Data Services] ──► TomTom (Transport) + GDACS (Disaster) + Canonical Weather
   ├── [05 Data Integration]      ──► build_context() (คำนวณ confidence & active_restriction)
   └── [06 Risk Knowledge]         ──► assess_risk() & analyze_routes() (ตรวจ Essential Kinds)
         │
         │  4. POST /v1/decisions (DecisionRequest)
         ▼
[07 Decision Engine (FastAPI) :8050]
         │
         ▼  5. Action: NORMAL / CHANGE_ROUTE / DELAY_TRAVEL / AVOID_TRAVEL
   ตอบกลับตามสายงานสู่ 03 ──► 02 ──► 01
```

---

## 3. รายละเอียดการออกแบบรายโมดูล (Detailed Module Specifications)

### 3.1 Data Integration & Risk Model (Modules 05 & 06)

#### การแบ่งกลุ่ม Record Kinds ใน Module 05
ในไฟล์ `05_data_integration/integration.py` ให้จำแนก Kinds ออกเป็น 2 ระดับ:
* **Essential Kinds (4 kinds):**
  - `current_weather`
  - `weather_forecast`
  - `transport_status`
  - `disaster_event`
* **Optional Kinds (2 kinds):**
  - `closure`
  - `official_alert`

#### เกณฑ์การประเมิน Coverage ใน Module 05
* Segment ใดที่มีข้อมูลครบทั้ง 4 Essential Kinds และข้อมูลยังไม่หมดอายุ (`freshness != "stale"`) จะได้รับสถานะ `coverage = "covered"`
* การขาดข้อมูลของ Optional Kinds จะไม่ถูกนับเป็น `missing` หรือ `partial` และจะไม่สร้าง flag คุณภาพที่ทำให้ข้อมูลถูกมองว่า degraded

#### การคำนวณและส่งค่าใน `build_context()`
ฟังก์ชัน `build_context()` จะคำนวณและคืนค่า dictionary เพิ่มเติม 2 fields:
1. **`confidence` ("HIGH" | "MEDIUM" | "LOW"):**
   - `"HIGH"`: ทุก segment ของเส้นทางหลักมีสถานะ `covered` ครบ 4 Essential Kinds และไม่มี flag `stale`, `missing`, หรือ `incomplete`
   - `"MEDIUM"`: Essential Kinds ครอบคลุมเป็นส่วนใหญ่ แต่มี flag ข้อจำกัดระดับรอง
   - `"LOW"`: ขาดข้อมูลของ Essential Kind ตัวใดตัวหนึ่ง หรือข้อมูลหลักไม่สามารถเข้าถึงได้
2. **`active_restriction` (bool | None):**
   - `False`: ประเมิน Essential Kinds ครบถ้วนแล้ว และไม่พบข้อมูลที่เป็นอุปสรรคต่อการเดินทาง
   - `True`: พบข้อมูลยืนยันว่ามีเหตุการณ์ปิดเส้นทางหรือภัยพิบัติรุนแรง (`status == "CLOSED"` หรือ `severity in ("HIGH", "CRITICAL")`)
   - `None`: ข้อมูลขาดหาย (`confidence == "LOW"`) จนไม่สามารถระบุสถานะของอุปสรรคได้

#### การปรับเกณฑ์ใน Module 06
ในไฟล์ `06_risk_knowledge_services/risk_knowledge/routing.py`:
* ฟังก์ชัน `_has_complete_coverage(route: IntegratedRoute) -> bool` ปรับให้ตรวจสอบว่าสถานะเป็น `covered` เฉพาะสำหรับ 4 Essential Kinds

---

### 3.2 Agent Orchestrator & Tool Wiring (Modules 03 & 04)

#### การเชื่อมโยง Weather จาก 04 สู่ 05
* ใน `03_travel_ai_agent/travel_agent/tools/live.py`:
  - ปรับเมธอด `integrate()` โดยยกเลิกคำสั่งตัดข้อมูลสภาพอากาศ (`del weather`)
  - เรียกใช้ `to_canonical_weather_record()` จาก `04_external_data_services/weather_to_canonical.py`
  - นำ Canonical Records ของสภาพอากาศ (`current_weather` และ `weather_forecast`) รวมเข้าในลิสต์ `canonical` ส่งต่อให้ `_build_context()` ของ Module 05

#### การเชื่อมต่อ Route Candidates
* ใน `LiveToolSet` ให้เชื่อมเข้ากับ `04_external_data_services/route_candidates.py` เพื่อดึงข้อมูลเส้นทางหลักและเส้นทางสำรองที่ถูกต้องทางภูมิศาสตร์

#### การส่งต่อ Emergency Context (03 → 07)
* ใน `03_travel_ai_agent/travel_agent/evidence.py` ที่ฟังก์ชัน `build_decision_request()`:
  - กำหนดค่า `emergency_context`:
    ```python
    payload["emergency_context"] = {
        "context": context,
        "region": "TH",      # ยึดตาม D-11 (พื้นที่ให้บริการประเทศไทย)
        "hazard": "GENERAL", # ปรับตาม alert ที่ตรวจพบ หรือ GENERAL เมื่อไม่มีภัยเฉพาะ
    }
    ```
  - เพื่อป้องกันไม่ให้ 07 ติด issue `emergency_context_missing`

#### การรองรับ Emergency Contact Metadata (07 → 03 → 02)
* ใน `02_api_backend/app/infrastructure/agent/contracts.py`:
  - ปรับ schema `EmergencyContact` ให้รองรับ field เสริม `metadata: dict | None = None` เพื่อป้องกัน Pydantic ตรวจสอบล้มเหลวเมื่อ 07 แนบ metadata กลับมา

---

### 3.3 Gateway & Client Contracts (Modules 01 & 02)

#### การปรับ Schema ฝั่งหน้าบ้าน (Module 01)
ปรับ `01_web_app/lib/api.ts` และ `01_web_app/lib/types.ts` ให้ตรงกับสัญญาของ 02:
1. **Request Body (`POST /v1/travel/recommendations`):**
   - `origin`: `{ "lat": float, "lon": float }`
   - `destination`: `{ "lat": float, "lon": float }`
   - `departure_time`: ISO-8601 string (เช่น `"2026-09-22T08:00:00Z"`)
   - `timezone`: `"Asia/Bangkok"` (string บังคับ)
   - `preferences`: `{ "travel_modes": ["CAR"], "avoid": [] }`
2. **Response Body:**
   - อ่านข้อมูลแบบ Nested ตาม RFC:
     - `recommendation_id` (UUIDv7)
     - `risk.level` ("LOW" | "MEDIUM" | "HIGH")
     - `recommendation.type` ("TRAVEL_NORMALLY" | "CHANGE_ROUTE" | "DELAY_TRAVEL" | "AVOID_TRAVEL")
     - `routes`, `hazards`
3. **Enums:**
   - ตัด `CRITICAL` ออกจาก `RiskLevel` เหลือเพียง `LOW`, `MEDIUM`, `HIGH`

#### การเชื่อมต่อ OIDC Authentication
* 01 Web App เชื่อมต่อ Keycloak realm `travel-safety` ด้วย client `web-app` (Authorization Code + PKCE)
* ทุก Request ที่เรียกเข้า 02 ต้องแนบ `Authorization: Bearer <access_token>`

#### การส่งมอบสัญญา (Contract Handoff)
* รัน `python -m scripts.export_openapi` ใน 02 เพื่อสร้าง `openapi.json` ฉบับทางการสำหรับนำไป generate client ให้ 01

---

### 3.4 สถาปัตยกรรม Docker และการจัดสรรพอร์ต (Unified Docker Stack)

สร้างไฟล์คอนฟิก **`docker-compose.integration.yml`** ที่ root ของโปรเจกต์:

```yaml
version: "3.8"
name: tsa-integration

services:
  keycloak:
    image: quay.io/keycloak/keycloak:26.7.4
    command: ["start-dev", "--import-realm"]
    ports:
      - "127.0.0.1:8180:8080"
    environment:
      KC_BOOTSTRAP_ADMIN_USERNAME: admin
      KC_BOOTSTRAP_ADMIN_PASSWORD: admin-dev-change-me
      KC_HOSTNAME: http://localhost:8180
      KC_HTTP_ENABLED: "true"
    volumes:
      - ./identity/keycloak:/opt/keycloak/data/import:ro

  postgres:
    image: postgres:16-alpine
    ports:
      - "127.0.0.1:5433:5432"
    environment:
      POSTGRES_USER: tsa
      POSTGRES_PASSWORD: tsa
      POSTGRES_DB: tsa

  redis-core:
    image: redis:7-alpine
    ports:
      - "127.0.0.1:6380:6379"

  decision-engine:
    build:
      context: ./DL-07-Agentic-AI-System-II/07_decision_llm_engine
      target: runtime
    ports:
      - "127.0.0.1:8050:8050"
    environment:
      DECISION_POLICY_VERSION: prototype-v3

  travel-agent:
    build:
      context: ./DL-07-Agentic-AI-System-II
      dockerfile: 03_travel_ai_agent/Dockerfile
      target: runtime
    ports:
      - "127.0.0.1:8010:8010"
    environment:
      DECISION_SERVICE_URL: http://decision-engine:8050
      USE_MOCK_TOOLS: "false"
    depends_on:
      - decision-engine

  api:
    build:
      context: ./DL-07-Agentic-AI-System-II/02_api_backend
      target: dev
    ports:
      - "127.0.0.1:8000:8000"
    environment:
      APP_ENV: dev
      DATABASE_URL: postgresql+asyncpg://tsa:tsa@postgres:5432/tsa
      REDIS_URL: redis://redis-core:6379/0
      AGENT_SERVICE_URL: http://travel-agent:8010
      DEV_JWT_SIGNING_KEY: ""
      JWT_ISSUER: http://localhost:8180/realms/travel-safety
      JWT_AUDIENCE: travel-safety-api
      JWKS_URL: http://host.docker.internal:8180/realms/travel-safety/protocol/openid-connect/certs
    extra_hosts:
      - "host.docker.internal:host-gateway"
    depends_on:
      - postgres
      - redis-core
      - travel-agent
      - keycloak
```

---

## 4. แผนการทดสอบจริงข้ามโมดูล (Cross-Module Integration Verification Plan)

ชุดทดสอบ E2E จะจัดทำขึ้นในไฟล์ `tests/integration/test_live_docker_e2e.py` โดยทำงานร่วมกับ Docker Stack จริง:

### กรณีทดสอบที่ 1: เส้นทางปกติและปลอดภัย (Safe Path Verification)
* **เงื่อนไข:** พิกัดจากกรุงเทพฯ ไปชลบุรี สภาพอากาศปกติ ไม่มีน้ำท่วมหรือปิดทาง
* **ผลลัพธ์ที่ต้องการ:**
  - HTTP Status: `200` หรือ `201`
  - `risk.level`: `LOW`
  - `recommendation.type`: `TRAVEL_NORMALLY`
  - ยืนยันว่าคอขวด `AVOID` หมดไปเมื่อข้อมูลความปลอดภัยได้รับการยืนยัน

### กรณีทดสอบที่ 2: เส้นทางพบภัยพิบัติ (Hazard Verification)
* **เงื่อนไข:** จำลองสถานการณ์น้ำท่วมหรือปิดทางในเส้นทาง
* **ผลลัพธ์ที่ต้องการ:**
  - HTTP Status: `200` หรือ `201`
  - `risk.level`: `HIGH`
  - `recommendation.type`: `CHANGE_ROUTE` (หากมีทางเลี่ยง) หรือ `AVOID_TRAVEL`

### กรณีทดสอบที่ 3: ระบบความปลอดภัยและขอบเขต (Security & Region Boundary)
* **เงื่อนไข:** 
  - คำขอไม่มี Bearer Token → ตรวจสอบการตอบ `401 Unauthenticated`
  - พิกัดนอกประเทศไทย (เช่น โตเกียว) → ตรวจสอบการตอบ `422 UNSUPPORTED_REGION` ทันที

---

## 5. กระบวนการตรวจทานและขั้นตอนต่อไป (Next Steps)

1. ผู้ใช้ตรวจสอบและอนุมัติเอกสารสเปกฉบับนี้
2. จัดทำแผนการทำงานแบบทีละก้าว (Implementation Plan) ด้วย writing-plans
3. ดำเนินการปรับปรุงโค้ดและคอนฟิกตามลำดับความปลอดภัย (TDD & Staged Execution)
4. รันการทดสอบและสรุปผล Walkthrough
