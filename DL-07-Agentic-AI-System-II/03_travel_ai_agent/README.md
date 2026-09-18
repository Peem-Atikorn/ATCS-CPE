# งาน 03 — Travel AI Agent

ต้นแบบของงาน 03 ตาม `01_env.txt`, `02_step.txt` และ `03_process.txt` ทำหน้าที่รับคำขอจาก Module 02 วางแผนว่าจะเรียก tool ใด เรียก tool ตามลำดับ รวมหลักฐาน แล้วส่งต่อให้ Module 07 เป็นผู้ตัดสิน

**Agent ไม่ตัดสินระดับความปลอดภัยหรือ action เอง** ขั้นตอนนี้เป็นหน้าที่ของกฎใน Module 07 ส่วน agent ทำหน้าที่รวบรวมหลักฐานและประสานงานเท่านั้น

## สถานะรุ่นนี้ (ขั้นที่ 1)

| ส่วน | สถานะ |
|---|---|
| API ให้ 02 เรียก `POST /v1/agent/runs` | ✅ ตาม contract ใน `02_api_backend/docs/02_api_spec.md` §9 |
| Progress แบบ NDJSON / ยกเลิก run ด้วย `DELETE` / `X-Deadline` | ✅ |
| เรียก Module 07 ตัวจริง (`POST /v1/decisions`) | ✅ เทสกับ engine ของ 07 ตัวจริงแบบ in-process |
| Module 04 / 05 / 06 | 🟡 **mock** (`travel_agent/tools/mocks.py`) เพราะยังไม่มี service จริง |
| จำกัด step, tool call และเวลา / ให้ tool ที่ล้มไม่ล้มทั้ง run | ✅ |
| Intent และ planner ด้วย LLM, LangGraph, checkpoint สำหรับคำถามต่อ | ⏳ ขั้นถัดไป ตอนนี้ใช้ `intent_hint` จาก 02 และลำดับ tool ที่กำหนดไว้ตายตัว |
| Emergency instructions | ⏳ รอตกลงในทีมว่าเป็นงานของ 07 หรือ 08 |

## ลำดับการทำงานของหนึ่ง run

```
understand ─▶ fetch_external ─▶ integrate ─▶ assess ─────────────▶ decide ─▶ finish
 (intent,      weather ┐          (05)        risk → knowledge →    (07)
  ถามกลับ)     transport├ ขนาน                 routes (06)
               disasters┘ (04)
```

- ถ้าข้อมูลสำคัญผิดหรือขาด เช่น ต้นทางกับปลายทางเป็นจุดเดียวกัน หรือเวลาออกเดินทางผ่านไปแล้ว agent จะตอบ `needs_clarification` และไม่เดาเอง
- ถ้า tool ใดล้ม, timeout หรือส่งข้อมูลที่ไม่ผ่าน schema service นั้นจะถูกบันทึกเป็น `unavailable` แล้ว run ทำงานต่อ ผลลัพธ์จะเป็น `partial_result` และ 07 จะไม่ถือว่าข้อมูลที่ขาดหมายถึงปลอดภัย
- ถ้า 07 ใช้งานไม่ได้ จะตอบ `503 DECISION_UNAVAILABLE` เพราะไม่มีคำแนะนำที่ใช้ได้ให้ส่งกลับ

## ข้อมูลที่ต้องตกลงกับทีม

- **02 (sakda):** `travel_agent/contracts.py` คัดลอกมาจาก contract ของ 02 ถ้าฝั่งไหนแก้ ต้องแก้อีกฝั่งด้วย
- **04 / 05 / 06:** `travel_agent/tools/schemas.py` เป็น**ร่าง** contract ที่ 03 เสนอ ทุก record ต้องมี `source`, `url` (https), `observed_at`, `fetched_at` และ `expires_at` ตามที่ 07 บังคับ
- **07 (mekmai):** 07 ให้ confidence เป็น LOW/MEDIUM/HIGH ส่วน 02 ต้องการตัวเลข 0–1 ตอนนี้ agent จึงส่ง `risk.confidence = null` เพื่อไม่แต่งตัวเลขขึ้นมาเอง

## เริ่มใช้งานด้วย Python

ต้องมี Python 3.12 ขึ้นไปและ `uv` รันจากโฟลเดอร์นี้:

```powershell
uv sync
Copy-Item .env.example .env
uv run pytest
```

รัน 07 และ 03 พร้อมกัน (เปิด PowerShell 2 หน้าต่างจากโฟลเดอร์นี้):

```powershell
uv run uvicorn decision_engine.api:app --port 8050   # Module 07
uv run uvicorn travel_agent.api:app --port 8010      # Module 03
```

เปิดดู [API docs](http://localhost:8010/docs) แล้วลองส่ง request ตามตัวอย่างใน `tests/conftest.py` (`run_body`) เลือกสถานการณ์จำลองได้ด้วย `request.preferences.mock_scenario` ซึ่งมีค่า `low_risk`, `high_risk`, `closure`, `safer_route`, `safer_time` และ `weather_down`

port 8010 ตรงกับค่าเริ่มต้นของ `AGENT_SERVICE_URL` ใน Module 02

## เริ่มใช้งานด้วย Docker Compose

```powershell
docker compose up --build -d
```

`compose.yaml` จะเปิด 03 พร้อม 07 container รันด้วย user ที่ไม่ใช่ root, เป็น read-only และตัด capability ทั้งหมด

## โครงสร้าง

```
travel_agent/
├── api.py          # FastAPI: POST/DELETE /v1/agent/runs, /health, /ready
├── pipeline.py     # AgentState + node ต่าง ๆ + การเรียก tool ที่มี budget/timeout
├── evidence.py     # สร้าง DecisionRequest ให้ 07
├── response.py     # แปลงผลของ 07 เป็น AgentRunResponse ให้ 02
├── contracts.py    # contract 02 ↔ 03
├── budget.py       # จำกัด step/tool call + AgentError
├── config.py       # ค่าจาก .env
└── tools/
    ├── base.py     # allowlist ของ tool + ToolSet interface
    ├── schemas.py  # ร่าง contract ของ 04/05/06
    ├── mocks.py    # ข้อมูลจำลองของ 04/05/06
    └── decision.py # HTTP client ของ 07 (retry ด้วย Tenacity)
```
