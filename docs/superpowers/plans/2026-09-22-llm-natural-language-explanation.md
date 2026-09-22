# แผนปฏิบัติการ: ระบบสร้างคำอธิบายการตัดสินใจด้วยโมเดลภาษาขนาดใหญ่ (LLM Natural Language Explanation Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** เชื่อมต่อโมเดลภาษาขนาดใหญ่ (Google Gemini REST API) เข้ากับ `07_decision_llm_engine` เพื่อสร้างคำอธิบายสภาพเส้นทางและคำแนะนำการขับขี่ภาษาไทยที่สละสลวย พร้อมระบบ Guardrail ล็อกคำตัดสินใจความปลอดภัย 100% และ Graceful Fallback อัตโนมัติ

**Architecture:** สร้าง `GeminiExplanationProvider` ใน `07_decision_llm_engine` เชื่อมต่อผ่าน `httpx.AsyncClient` ในรูปแบบ Structured JSON output โดยปรับปรุงกลไกตรวจสอบใน `explain()` ให้ยืนยัน Action Code ตรงกับกฎ และ Evidence IDs อ้างอิงจากหลักฐานจริง หากเกิดปัญหาหรือไม่มี Key จะสลับไปใช้ Template Baseline เดิมทันที

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, HTTPX, Pytest, Docker Compose

**Spec:** `docs/superpowers/specs/2026-09-22-llm-natural-language-explanation-design.md`

## Global Constraints
- ห้ามมี AI watermarks, signatures หรือแท็กระบุตัวตน AI ในซอร์สโค้ดและเอกสาร
- ผลลัพธ์ `action_code` ต้องล็อกตามที่ Rule Engine ตัดสินใจ ห้ามโมเดลปรับลดระดับความเสี่ยง
- Evidence IDs ในคำอธิบายต้องเป็น Subset ของหลักฐานที่มีอยู่จริง ห้ามกุ ID ขึ้นมาเอง
- หากไม่มี API Key, Timeout (> 5 วิ), หรือเกิด Network Error ต้อง Fallback ไปใช้ Template ทันทีโดยไม่เกิด HTTP 500
- การ Commit และ Push ขึ้น Git ต้องได้รับความยินยอมจากผู้ใช้ก่อนเสมอ

## Review Focus
1. **API Key ว่างเปล่าหรือยังไม่ได้ตั้งค่า:** ระบบต้องรันผ่านและส่งข้อความ Template Baseline (`mode="template"`, `degraded_services: ["llm"]`)
2. **โมเดลตอบ Action Code ไม่ตรงกับที่ระบบคำนวณ:** ระบบต้องปฏิเสธผลลัพธ์ของโมเดลทันทีและ Fallback สู่ Template
3. **โมเดลพยายามแต่งเติม Evidence IDs ที่ไม่มีในระบบ:** ระบบต้องปฏิเสธผลลัพธ์และ Fallback สู่ Template
4. **เครือข่ายภายนอกล่าช้าหรือ Timeout เกิน 5 วินาที:** ระบบต้องตัดการรอและส่งผลลัพธ์ Template กลับทันเวลา
5. **ความเข้ากันได้กับการทดสอบเดิม (Backward Compatibility):** Unit Tests ทั้งหมดใน `test_explanation_audit.py` และ `test_live_pipeline_contract.py` ต้องผ่าน 100%

---

### Task 1: อัปเดตการตั้งค่าระบบใน `config.py` และ Environment

**Files:**
- Modify: `DL-07-Agentic-AI-System-II/07_decision_llm_engine/decision_engine/config.py`
- Modify: `DL-07-Agentic-AI-System-II/07_decision_llm_engine/.env.example`
- Modify: `docker-compose.integration.yml`

**Interfaces:**
- Produces: `Settings.gemini_api_base`, `Settings.llm_model_explainer`, `Settings.llm_api_key` (รองรับทั้ง `LLM_API_KEY` และ `GEMINI_API_KEY`)

- [ ] **Step 1: เขียน Unit Test ตรวจสอบ Settings ใน `tests/test_config.py`**

```python
from decision_engine.config import Settings
import os

def test_settings_gemini_config():
    s = Settings(
        _env_file=None,
        llm_model_explainer="gemini-2.0-flash",
        llm_api_key="test-key",
    )
    assert s.llm_model_explainer == "gemini-2.0-flash"
    assert s.llm_api_key.get_secret_value() == "test-key"
    assert s.gemini_api_base == "https://generativelanguage.googleapis.com/v1beta"
```

- [ ] **Step 2: อัปเดต `decision_engine/config.py`**
เพิ่มฟิลด์ `gemini_api_base: str = "https://generativelanguage.googleapis.com/v1beta"`, ปรับ `llm_timeout: float = Field(default=5.0, gt=0, le=60)`, และรองรับ `GEMINI_API_KEY` ผ่าน Pydantic field alias หรือ validator

- [ ] **Step 3: รันการทดสอบ**
Run: `pytest DL-07-Agentic-AI-System-II/07_decision_llm_engine/tests/test_config.py -v`

---

### Task 2: พัฒนา `GeminiExplanationProvider` ใน `provider.py`

**Files:**
- Create: `DL-07-Agentic-AI-System-II/07_decision_llm_engine/decision_engine/provider.py`
- Create: `DL-07-Agentic-AI-System-II/07_decision_llm_engine/tests/test_provider.py`

**Interfaces:**
- Produces: `GeminiExplanationProvider` implementing `ExplanationProvider` protocol:
  `async def generate(self, package: dict, *, max_output_tokens: int) -> dict`

- [ ] **Step 1: เขียน Unit Test จำลองการทำงานของ `GeminiExplanationProvider`**
ทดสอบการประกอบ Prompt, การส่ง Header/URL ไปยัง Gemini endpoint, และการ parse JSON Response

- [ ] **Step 2: สร้างไฟล์ `decision_engine/provider.py`**
สร้างคลาส `GeminiExplanationProvider` ที่รับ `settings: Settings` ใช้ `httpx.AsyncClient` เรียก `POST {gemini_api_base}/models/{model}:generateContent?key={api_key}` พร้อมสร้าง System Instruction ภาษาไทย และกำหนด `response_mime_type="application/json"`

- [ ] **Step 3: รัน Unit Test ตรวจสอบ Provider**
Run: `pytest DL-07-Agentic-AI-System-II/07_decision_llm_engine/tests/test_provider.py -v`

---

### Task 3: ปรับปรุง `explanation.py` ให้รองรับ Natural Language และ Guardrails

**Files:**
- Modify: `DL-07-Agentic-AI-System-II/07_decision_llm_engine/decision_engine/explanation.py`
- Modify: `DL-07-Agentic-AI-System-II/07_decision_llm_engine/tests/test_explanation_audit.py`

**Interfaces:**
- Consumes: `Candidate`, `ExplanationProvider`, `Settings`
- Produces: `explain(decision, request, settings, provider, citation_ids) -> tuple[Explanation, list[str]]`

- [ ] **Step 1: ตรวจสอบและปรับปรุง Guardrail Validation ใน `explanation.py`**
  - ตรวจสอบ `candidate.action_code == decision.action` (ล็อกผลลัพธ์)
  - ตรวจสอบ `set(candidate.evidence_ids).issubset(set(citation_ids))` (ห้ามกุ Evidence ID)
  - รองรับข้อความสรุปและคำแนะนำภาษาไทยแบบอิสระที่มีความยาวเหมาะสม (> 5 ตัวอักษร)
  - รักษาระบบตรวจสอบแบบเดิมเมื่อ package ระบุ `strict_sentence_bank=True` เพื่อให้ชุดทดสอบเดิมผ่านทั้งหมด

- [ ] **Step 2: รันการทดสอบเดิมทั้งหมดใน `test_explanation_audit.py`**
Run: `pytest DL-07-Agentic-AI-System-II/07_decision_llm_engine/tests/test_explanation_audit.py -v`
Expected: 7 passed

---

### Task 4: เชื่อมต่อ Provider เข้ากับ FastAPI Lifecycle และ Compose

**Files:**
- Modify: `DL-07-Agentic-AI-System-II/07_decision_llm_engine/decision_engine/api.py`
- Modify: `docker-compose.integration.yml`

**Interfaces:**
- Produces: `app.state.provider` ได้รับอินสแตนซ์ `GeminiExplanationProvider` เมื่อมี API Key

- [ ] **Step 1: อัปเดต `decision_engine/api.py`**
ใน `create_app()`: หาก `settings.llm_model_explainer != "disabled"` และมี `settings.llm_api_key.get_secret_value()` ให้สร้าง `GeminiExplanationProvider(settings)` ผูกเข้ากับ `app.state.provider`

- [ ] **Step 2: อัปเดต `docker-compose.integration.yml`**
ส่งผ่าน `LLM_API_KEY`, `GEMINI_API_KEY`, `LLM_MODEL_EXPLAINER` เข้าสู่ container `decision-engine`

---

### Task 5: การทดสอบความถูกต้องและบูรณาการทั้งระบบ (Verification & Integration)

**Files:**
- Test: `DL-07-Agentic-AI-System-II/07_decision_llm_engine/tests/test_live_pipeline_contract.py`

- [ ] **Step 1: รันทดสอบชุดสัญญาการทำงานทั้งหมดของ Module 07**
Run: `pytest DL-07-Agentic-AI-System-II/07_decision_llm_engine/tests/ -v`
Expected: All tests pass

- [ ] **Step 2: รัน Rebuild และทดสอบ Container `decision-engine`**
Run: `docker compose -f docker-compose.integration.yml up -d --build decision-engine travel-agent`

- [ ] **Step 3: ตรวจสอบความพร้อมผ่าน Health Check**
Run: `curl http://127.0.0.1:8050/health`
Expected: `{"status": "ok", "module": "07", ...}`
