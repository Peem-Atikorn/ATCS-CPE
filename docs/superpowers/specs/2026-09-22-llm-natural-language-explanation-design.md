# สเปกการออกแบบ: ระบบสร้างคำอธิบายการตัดสินใจด้วยโมเดลภาษาขนาดใหญ่ (LLM Natural Language Explanation Design Specification)

**วันที่มีผล:** 22 กันยายน 2026  
**สถานะ:** Draft Design — รอการตรวจสอบ (Review)  
**ขอบเขต:** เฟสที่ 1 — การสร้างคำอธิบายสภาพเส้นทางและคำแนะนำการขับขี่ภาษาไทยในโมดูล `07_decision_llm_engine`  
**เอกสารอ้างอิง:** 
- ทะเบียนสัญญาระหว่างโมดูล ฉบับที่ 10
- ข้อกำหนดความปลอดภัยและการตรวจสอบ `DL-07-Agentic-AI-System-II/07_decision_llm_engine/03_process.txt`

---

## 1. บริบทและวัตถุประสงค์ (Context & Objectives)

ในระบบปัจจุบัน `07_decision_llm_engine` ทำหน้าที่เป็น Decision Engine ที่ประเมินความเสี่ยงและออกคำวินิจฉัยความปลอดภัยในการเดินทาง (`NORMAL`, `CAUTION`, `CHANGE_ROUTE`, `DELAY_TRAVEL`, `AVOID_TRAVEL`) แต่ในส่วนการสร้างคำอธิบาย (`Explanation`) ยังคงใช้ **Template-based Baseline (`template-v1`)** ซึ่งมีข้อจำกัด:

1. **ความยืดหยุ่นของภาษา:** ข้อความสรุปและคำแนะนำถูกดึงจากชุดประโยคคงที่ (Sentence Bank) ทำให้คำอธิบายขาดรายละเอียดเชิงลึกของเหตุการณ์จริง เช่น ไม่ระบุกิโลเมตรที่มีน้ำท่วมขัง หรือลักษณะฝนตกในแต่ละช่วงเวลา
2. **ความเชื่อมโยงของหลักฐาน:** ข้อมูลจราจรสด (เช่น ข้อมูลอุบัติเหตุ/ปิดถนนจาก Longdo Traffic) และข้อมูลสภาพอากาศสด ไม่ถูกนำมาเรียบเรียงเป็นคำแนะนำการขับขี่ภาษาไทยที่เข้าใจง่ายและสละสลวย

### วัตถุประสงค์หลัก
1. เชื่อมต่อโมเดลภาษาขนาดใหญ่ (LLM Provider) ผ่าน REST API เข้าสู่กระบวนการสร้างคำอธิบายของ `07_decision_llm_engine`
2. สร้างคำอธิบายสถานการณ์ (`summary`), รายการเหตุผลความเสี่ยง (`reasons`) และคำแนะนำการขับขี่ (`instructions`) ภาษาไทยที่สละสลวย ชัดเจน และสอดคล้องกับสภาพแวดล้อมจริง
3. คงมาตรฐานความปลอดภัยสูงสุด (**Zero Hallucination & Safety Guardrail**): ล็อกรหัสการตัดสินใจที่ผ่านการคำนวณจากกฎ ห้ามโมเดลปรับลดระดับความเสี่ยงเอง และมีระบบ Graceful Fallback หากเกิดข้อผิดพลาดในการเชื่อมต่อ

---

## 2. สถาปัตยกรรมระบบและการไหลของข้อมูล (System Architecture & Data Flow)

```
[03 Travel AI Agent]
        │
        ▼ (POST /v1/decisions: DecisionRequest)
[07 Decision Engine Service]
        │
        ├── 1. Rule Evaluation (evaluate) ────────► ล็อก Action Code ทันที (ห้ามแก้ไข)
        ├── 2. Emergency Catalog (build_emergency) ─► รวบรวมเบอร์โทรและแนวทางฉุกเฉิน
        ├── 3. Citation Mapping (references) ──────► ดึง Evidence IDs ทั้งหมดที่ใช้งานจริง
        │
        ▼
[LLM Explanation Pipeline: explain()]
        │
        ├── ตรวจสอบการตั้งค่า Provider:
        │     ├── หากไม่มี LLM_API_KEY หรือ LLM_MODEL_EXPLAINER="disabled"
        │     │     └──► เรียก fixed_explanation() (Fallback เป็น Template ทันที)
        │     │
        │     └── หากเปิดใช้งาน Provider
        │           │
        │           ▼
        │     [GeminiExplanationProvider]
        │           │── รวมหลักฐานจริง (Weather, Longdo Traffic, Disaster, Risk Level)
        │           │── ส่ง Request ผ่าน httpx Async Client ไปยัง REST API Endpoint
        │           │── กำหนด Structured JSON Schema สำหรับผลลัพธ์
        │           │
        │           ▼
        │     [Guardrails & Output Validation]
        │           ├── ตรวจสอบ Action Code ต้องตรงกับค่าที่ล็อกไว้ 100%
        │           ├── ตรวจสอบ Evidence IDs ต้องเป็น Subset ของหลักฐานจริง (ห้ามกุ ID ใหม่)
        │           ├── ตรวจสอบความสมบูรณ์ของข้อความภาษาไทย (ความยาว, จำนวนข้อ)
        │           │
        │           ├── ผ่านการตรวจสอบ ──► ส่งคืน Explanation(mode="provider")
        │           └── ไม่ผ่าน/Timeout  ──► Fallback เป็น Explanation(mode="template")
        │
        ▼
[Audit Logging & Response]
        ├── บันทึกรายละเอียด, Version, และ Validation Results ลง audit.jsonl
        └── ส่งกลับ DecisionResponse สู่ 03 Travel AI Agent
```

---

## 3. ข้อมูลที่ส่งให้โมเดลและสัญญาผลลัพธ์ (Payload & Response Schema)

### 3.1 ข้อมูลนำเข้าสำหรับโมเดล (Grounding Package)
โมเดลจะได้รับเฉพาะข้อมูลหลักฐานที่ผ่านการตรวจสอบแล้วเท่านั้น เพื่อป้องกัน Prompt Injection และการสร้างข้อมูลเท็จ:

```json
{
  "system_instruction": "คุณคือผู้เชี่ยวชาญด้านความปลอดภัยในการเดินทาง วิเคราะห์และอธิบายสถานการณ์การเดินทางตามหลักฐานที่กำหนดอย่างตรงไปตรงมา สุภาพ ชัดเจน และสละสลวยเป็นภาษาไทย",
  "locked_action": "CAUTION",
  "route_summary": {
    "origin": "มหาวิทยาลัยเทคโนโลยีราชมงคลธัญบุรี",
    "destination": "สยามพารากอน",
    "departure_time": "2026-09-22T08:00:00+07:00",
    "distance_km": 42.5,
    "duration_minutes": 55
  },
  "risk_assessment": {
    "level": "MEDIUM",
    "score": 0.45,
    "primary_factors": ["ฝนตกปานกลางตามแนวเส้นทาง", "การจราจรหนาแน่นช่วงดอนเมือง"]
  },
  "evidence_items": [
    {
      "id": "weather-rain-seg-2",
      "type": "weather",
      "summary": "มีฝนตกปานกลาง ปริมาณน้ำฝน 8.5 มม./ชม. ช่วงถนนวิภาวดีรังสิต"
    },
    {
      "id": "traffic-longdo-1042",
      "type": "traffic",
      "summary": "อุบัติเหตุกีดขวาง 1 ช่องทางจราจร บริเวณแยกหลักสี่ การจราจรเคลื่อนตัวช้า"
    }
  ],
  "valid_evidence_ids": ["weather-rain-seg-2", "traffic-longdo-1042"],
  "emergency_contacts": [
    {"name": "ตำรวจทางหลวง", "phone": "1193"}
  ]
}
```

### 3.2 สัญญาผลลัพธ์แบบโครงสร้าง (Structured JSON Schema)
ใช้ `Pydantic` กำหนด Schema ที่โมเดลต้องตอบกลับ:

```python
class CandidateExplanation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action_code: Action
    summary: str = Field(
        description="สรุปภาพรวมสภาพเส้นทางและความปลอดภัยในการเดินทางภาษาไทยที่กระชับและสละสลวย",
        max_length=2000,
    )
    reasons: list[str] = Field(
        description="รายการเหตุผลความเสี่ยงหลัก 2-4 ข้อที่ตรวจพบตามหลักฐานจริง",
        min_length=1,
        max_length=8,
    )
    instructions: list[str] = Field(
        description="คำแนะนำข้อควรปฏิบัติในการขับขี่หรือการเตรียมตัวของผู้เดินทาง",
        min_length=1,
        max_length=8,
    )
    uncertainty: list[str] = Field(
        default_factory=list,
        description="ข้อจำกัดของข้อมูลสภาพแวดล้อม (ถ้ามี)",
        max_length=4,
    )
    evidence_ids: list[str] = Field(
        description="รหัสหลักฐานที่นำมาใช้อ้างอิง ต้องเป็นรหัสที่มีอยู่ใน valid_evidence_ids เท่านั้น",
        max_length=32,
    )
```

---

## 4. กลไกความปลอดภัยและระบบสำรอง (Safety & Resilience Guardrails)

1. **การล็อกคำตัดสินใจ (Action Code Locking):**
   * โมเดลไม่มีสิทธิ์ปรับเปลี่ยนผลลัพธ์ `action_code` จากที่ Rule Engine คำนวณได้ หากโมเดลตอบกลับค่าไม่ตรง ระบบจะตัดสิทธิ์และสลับไปใช้ Template ทันที
2. **การตรวจสอบการอ้างอิงหลักฐาน (Citation Grounding):**
   * ทุก ID ใน `evidence_ids` จะต้องเป็นสมาชิกของ `citation_ids` ที่ผ่านการรับรองแล้วเท่านั้น ห้ามโมเดลกุ ID ขึ้นมาเอง
3. **การควบคุมเวลาและทรัพยากร (Timeout & Budget):**
   * กำหนด `LLM_TIMEOUT = 5.0` วินาที
   * มีจำนวนการลองซ้ำสูงสุด `LLM_MAX_ATTEMPTS = 2` รอบ
   * หากเกินเวลาหรือเกิด Network Error ระบบจะบันทึกรหัส `LLM_TIMEOUT` หรือ `LLM_PROVIDER_OR_SCHEMA_ERROR` แล้วส่งข้อความ Template ทันทีโดยไม่ส่งผลให้ HTTP 500 แก่ Client
4. **การรักษาความปลอดภัยของข้อมูล (Data Privacy):**
   * ไม่มีการส่งข้อมูลระบุตัวตนของผู้ใช้ (User ID, ชื่อ, อีเมล, Token) ไปยังโมเดลภายนอก ส่งเฉพาะข้อมูลพิกัด เวลา และสภาพแวดล้อมเท่านั้น
   * ซ่อนและไม่ Log ข้อมูลที่เป็น Secret หรือ API Key ลงใน Audit Log

---

## 5. การปรับปรุงส่วนประกอบและโค้ด (Components & Implementation Details)

### 5.1 โมดูล `07_decision_llm_engine`
1. **`decision_engine/config.py`**:
   * เพิ่มตัวแปร `gemini_api_base: str = "https://generativelanguage.googleapis.com/v1beta"`
   * เพิ่มค่าเริ่มต้นรองรับ `gemini-2.0-flash` / `gemini-1.5-flash` ใน `llm_model_explainer`
   * ปรับ `llm_timeout: float = Field(default=5.0, gt=0, le=60)`
2. **`decision_engine/provider.py` (ไฟล์ใหม่)**:
   * สร้างคลาส `GeminiExplanationProvider` ที่สอดคล้องกับโปรโตคอล `ExplanationProvider`
   * ใช้งาน `httpx.AsyncClient` เรียก REST API `generateContent` พร้อมกำหนด `response_mime_type="application/json"` และ JSON Schema
3. **`decision_engine/explanation.py`**:
   * ปรับปรุงฟังก์ชัน `explain()` ให้อนุญาตข้อความสรุปภาษาธรรมชาติที่สร้างโดย Provider จริง โดยทำการตรวจสอบความถูกต้องตามเกณฑ์ (Action Code, Citation IDs, Text Length) แทนการเทียบกับ Sentence Bank แบบตายตัว
   * คงความสามารถในการทดสอบร่วมกับ Mock Provider เดิม
4. **`decision_engine/api.py`**:
   * ตรวจสอบการตั้งค่าเมื่อเริ่มต้นแอป หากพบ `LLM_API_KEY` และ `LLM_MODEL_EXPLAINER != "disabled"` จะสร้างอินสแตนซ์ของ `GeminiExplanationProvider` ผูกเข้ากับ `app.state.provider`
5. **`docker-compose.integration.yml` & `.env.example`**:
   * เพิ่มการส่งผ่านตัวแปร `LLM_API_KEY`, `GEMINI_API_KEY`, `LLM_MODEL_EXPLAINER` เข้าสู่ Container `decision-engine`

---

## 6. แผนการตรวจสอบและทดสอบ (Verification Plan)

### 6.1 Automated Unit Tests
* **`tests/test_explanation_audit.py`**:
  * รันทดสอบกรณี Provider พยายามเปลี่ยน Action Code (ต้องถูกปฏิเสธและใช้ Template)
  * รันทดสอบกรณี Provider กุ Evidence ID ที่ไม่มีอยู่ (ต้องถูกปฏิเสธและใช้ Template)
  * รันทดสอบกรณี Provider เกิด Timeout หรือ Network Error (ต้อง Fallback ทันที)
* **`tests/test_gemini_provider.py` (ทดสอบใหม่)**:
  * จำลอง HTTP Response ด้วย `pytest-mock` หรือ `respx` ตรวจสอบการแปลง Schema และการประกอบ Prompt

### 6.2 Live Pipeline Integration Test
* ทดสอบยิง Request ผ่าน `03_travel_ai_agent` สู่ `07_decision_llm_engine` ทั้งในกรณี:
  1. `LLM_MODEL_EXPLAINER=disabled` -> ได้รับคำตอบจาก Template (`mode="template"`, `degraded_services: ["llm"]`)
  2. ใส่ API Key จริงและเปิดใช้งาน -> ได้รับคำอธิบายภาษาไทยสละสลวย (`mode="provider"`, `degraded_services: []`)
