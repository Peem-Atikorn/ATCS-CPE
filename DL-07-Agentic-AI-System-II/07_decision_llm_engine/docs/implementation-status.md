# สถานะการทำตาม guide — Module 07

ตรวจเมื่อ 19 กันยายน 2026 รุ่น 0.2.0 / policy `prototype-v2` / output schema `07-draft-v2`

| ข้อกำหนด | สิ่งที่มีในต้นแบบ | ขอบเขตที่ยังรอ |
|---|---|---|
| Python 3.12, FastAPI, Pydantic | `pyproject.toml`, `uv.lock`, `decision_engine/api.py`, `models.py` | ยืนยัน draft contract กับ 03/06/08 |
| รับหลักฐาน risk/weather/transport/routes/RAG/quality | `DecisionRequest` มีข้อมูลแต่ละส่วนและ evidence package | ข้อมูลจริงจาก 04–06; RAG excerpt ไม่ถูกใช้สร้างคำสั่งอิสระ |
| ตรวจ request/route/time | ตรวจทุก scoped input ให้ตรงกับ context กลาง | ความแท้จริงของข้อมูลต้องรับประกันจากระบบต้นทาง |
| deterministic policy | `policies/prototype-v2.json`, `policy.py`; เก็บไฟล์ v1 เดิมเพื่อประวัติ | อนุมัติลำดับกฎ เกณฑ์ risk และข้อยกเว้น |
| official warnings first | ประกาศปิด/งดเดินทางชนะกฎอื่น; caution ส่งตรวจต่อ | mapping ประกาศจริงกับระดับข้อจำกัด |
| confidence/escalation | float 0–1 + confidence_details; รับ ordinal input เดิมผ่านเกณฑ์ที่ระบุใน policy v2; threshold < 0.5 | ไม่ใช่ probability calibration |
| Emergency Instructions | object ตาม field ของ 02; local catalog + URL/hash/scope/time validation; fallback ไทย/อังกฤษ; citations และ audit | ยังไม่มีเอกสาร/เบอร์ฉุกเฉินจริงใน catalog; 03 ต้องส่งต่อ field ใหม่ |
| lock action before LLM | `Decision` immutable; provider ได้สำเนาของ package; ตรวจ action ซ้ำ | ประเมินกับ LLM จริง |
| grounded structured explanation | sentence bank ภาษาไทย/อังกฤษ, schema, allowlist citations | ยังไม่มี live SDK/provider และยังไม่รองรับ free-form explanation |
| timeout/token/retry/fallback | จำกัดเวลาและ attempts; byte budget; fixed template | ใช้ tokenizer ของ provider เมื่อเชื่อมจริง |
| prompt injection / secrets | ไม่ส่ง raw evidence/summary หรือ API key ให้ provider seam; ไม่ echo request ใน 422 | ทดสอบ provider จริงและระบบ authentication |
| version metadata | policy version + SHA256, prompt/model/data versions | approved policy registry, retention และ rollback workflow เต็มรูปแบบ |
| audit trace | JSONL เฉพาะ correlation ID, rules, evidence IDs/status, versions และผล validation | PostgreSQL/shared storage, rotation, access control, retention |
| Redis / PostgreSQL / tracing | แยกขอบเขตไว้ ยังไม่บังคับใช้งานในต้นแบบ | ทำเมื่อออกแบบ infrastructure ร่วมกับทีม |
| golden/property/red-team tests | 87 tests ครอบคลุม action, precedence, stale/conflict, provider failure, audit | end-to-end กับบริการของเพื่อน |
| Docker | Dockerfile nonroot, Compose เปิดเฉพาะ 07, healthcheck, audit volume | Docker CLI มีแล้ว; compose config ผ่าน; Engine ไม่ทำงาน จึงยังไม่ได้ build/run container |

## ผลตรวจที่ทำแล้ว

- ใช้ environment Python 3.12.14 เดิม; อัปเดต lock metadata ของ project เป็น 0.2.0 แบบ offline ไม่เปลี่ยน dependency versions
- Ruff lint ผ่าน และ formatting ผ่าน
- pytest ผ่าน 87 tests; มี deprecation warnings 2 รายการจาก Starlette/httpx/AnyIO ใน dependency ชุดที่ล็อกไว้
- เปิด Uvicorn จริงบน loopback และส่ง HTTP ผ่าน `/health`, `/ready`, `/v1/decisions` ครบ 10 สถานการณ์จำลอง ผล action/confidence/emergency status ตรงตามคาด; หยุด test server แล้ว
- `docker compose config --quiet` ผ่าน; `docker version` ติดต่อ Docker Engine ไม่ได้ (ไม่พบ dockerDesktopLinuxEngine pipe) จึงไม่อ้างผล build/container
- ผล emergency object ผ่าน Pydantic model จริงของ 02; response ผ่าน Pydantic schema ของ 03 ที่อ่านและ compile เฉพาะ declaration (ไม่ได้รัน HTTP client/retry ของ 03 เพราะ environment ของ 07 ไม่มี tenacity) ไม่ใช่ end-to-end ทั้งระบบ
- ตัวอย่างผลลัพธ์ใหม่อยู่ใน `examples/emergency_fallback_response.json`; request มีตัวอย่าง numeric_confidence และ emergency_fallback
- ไฟล์ guide เดิมทั้งสามไฟล์ไม่มี diff และไฟล์ใหม่ทั้งหมดอยู่ภายในโมดูล 07

## ข้อจำกัดของเครื่องตรวจ

Python 3.12 สร้างโฟลเดอร์ temporary แบบ owner-only ทำให้ pytest `tmp_path` ปกติใช้ไม่ได้ภายใต้ Windows sandbox นี้ จึงรันทดสอบด้วย temporary-directory fixture ภายนอก repo ที่สร้างโฟลเดอร์ด้วยสิทธิ์สืบทอดปกติ ไม่มีการข้าม assertions หรือแก้ production code เพื่อให้ tests ผ่าน การรันทั่วไปบนเครื่องผู้ใช้ยังใช้ `uv run pytest` ตาม README

มีโฟลเดอร์ชั่วคราว `pytest-cache-files-12huxshy` และ `pytest-cache-files-mbvpfjts` จากการรันทดสอบครั้งแรกที่ไม่สามารถลบภายใต้สิทธิ์ปัจจุบันได้ ระบบอนุมัติอัตโนมัติปฏิเสธคำสั่งปรับสิทธิ์เพื่อเก็บกวาด จึงเก็บไว้และกันออกจาก Git/Docker ด้วย ignore patterns ไม่ใช่ source code หรือสิ่งที่ติดมากับ guide
