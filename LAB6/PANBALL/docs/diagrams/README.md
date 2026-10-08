# PANBALL — UML และการไหลของข้อมูล

อ้างอิงโค้ด commit `18208d5` วันที่ 6 ตุลาคม 2026 (Asia/Bangkok) ตรวจจาก source code ไม่ใช่การทดสอบล็อกอินกับระบบที่กำลังทำงาน

เปิด `panball-uml-data-flow.html` เพื่อดู 8 แผนภาพพร้อมคำอธิบายและตารางทุกหน้าเว็บ ไฟล์ HTML มี SVG/CSS ในตัว; Google Fonts เป็นส่วนเสริมและมี font fallback

## แผนภาพและต้นฉบับ UML

- [UML Use Case — ผู้ใช้ทั่วไป](01-user-use-cases.puml): ขอบเขตการใช้งานหลังเข้าสู่ระบบ รวมข้อมูลฟุตบอล แชท และการตั้งค่าส่วนตัว
- [UML Use Case — ผู้ดูแลระบบ](02-admin-use-cases.puml): แอดมินมีความสามารถของผู้ใช้ทั่วไป และเพิ่มงานดูแลระบบ
- [เส้นทางหน้าเว็บ](03-website-navigation.puml): ภาพนี้เป็น Navigation Map; แชท ประวัติ และการตั้งค่าไม่ใช่หน้า URL แยก
- [สถาปัตยกรรมทั้ง 8 โมดูล](04-system-architecture.puml): เส้นหลักเป็นทิศทางการเรียกใช้; เส้นทางนำเข้าและสร้างรายงานแยกในภาพถัดไป
- [UML Sequence — แชทแบบ RAG](05-chat-sequence.puml): กรณี session เดิมและค้นเจอข้อมูล; อ่านลำดับจากบนลงล่าง
- [การนำเข้าข้อมูลฟุตบอล](06-data-ingestion.puml): งานตามเวลาและคำสั่งแอดมินส่ง trigger; 07 เป็นผู้ทำงานนำเข้า
- [รายงานประจำสัปดาห์: ร่าง → เผยแพร่](07-weekly-report-flow.puml): ค่าปกติ REPORT_AUTO_PUBLISH=false; แอดมินตรวจฉบับร่างก่อนให้ผู้ใช้เห็น
- [การทำนายและจำลองฤดูกาล](08-prediction-flow.puml): ข้อมูลสถิติที่เก็บไว้ → ค่าความแข็งแกร่งของทีม → แบบจำลอง local

## ประเด็นสำคัญ

- Admin สืบทอดความสามารถผู้ใช้; เว็บตรวจ role และ API ตรวจ require_admin โดยโหลดผู้ใช้จากฐานข้อมูลทุกคำขอ
- หน้าแสดงข้อมูลฟุตบอลเรียก 02 → 07 โดยตรง ส่วนแชทเรียก 03 เพื่อเลือก route
- 05 มี SQLite เป็น durable KB store และ FAISS/BM25 เป็นดัชนีค้นหาผสม
- 02 เก็บข้อมูลผู้ใช้ใน schema app; 07 เก็บข้อมูลฟุตบอลใน schema football ของ Postgres ตัวเดียว
- Beat/Worker ผ่าน Redis ส่ง trigger ให้ 07 ทำงาน การบันทึกคำตอบแชทใช้ FastAPI BackgroundTasks
- รายงานเริ่มเป็น draft; ผู้ใช้ทั่วไปเห็นเฉพาะ published โดยค่าปกติ auto-publish ปิด
- ฟีเจอร์ player/coach/historical indexing และ LLM ขึ้นกับการตั้งค่าและ provider
- การนำเข้า archive ด้วยสคริปต์แยกจาก scheduled ingest; IndexTask ในฐานข้อมูลรองรับ retry
- ภาพสถาปัตยกรรมแสดงทิศ request; response กลับตามเส้นทางย้อนกลับ
- ไม่มีข้อมูลบัญชีจริง รหัสผ่าน token หรือ API key ในชุดเอกสาร

## หน้าเว็บ / API

| บทบาท | หน้า / จุดเข้า | หน้าที่ | API |
|---|---|---|---|
| ผู้เยี่ยมชม | /login | เข้าสู่ระบบ | POST /api/auth/login |
| ผู้เยี่ยมชม | /register | สมัครบัญชีผู้ใช้ทั่วไป | POST /api/auth/register |
| ผู้ใช้ | / | หน้าหลัก แผงแชท แหล่งอ้างอิง ประวัติ Feedback | POST /api/chat · GET /api/sessions · GET /api/history/{id} · POST /api/feedback |
| ผู้ใช้ | /football/fixtures | ผลและโปรแกรมการแข่งขัน | GET /api/football/fixtures |
| ผู้ใช้ | /matches/{id} | รายละเอียดแมตช์ และ prediction ก่อนแข่ง | GET /api/football/matches/{id} · GET /api/football/predict |
| ผู้ใช้ | /football/standings | ตารางคะแนนและข้อมูลฟอร์มทีม | GET /api/football/standings · GET /api/football/fixtures |
| ผู้ใช้ | /football/simulation | โอกาสแชมป์ อันดับ ท็อป 4 และตกชั้น | GET /api/football/simulation |
| ผู้ใช้ | /football/reports | รายงานที่เผยแพร่แล้ว | GET /api/football/reports/weekly |
| ผู้ใช้ | Settings modal | ทีมโปรด ภาษา; ทีมที่กำลังดูแยกจากทีมโปรด | PATCH /api/me/preferences |
| แอดมิน | /admin | ภาพรวมสถิติ | GET /api/admin/stats |
| แอดมิน | /admin/pipeline | สถานะ นำเข้า สร้างรายงาน ติดตามงาน | GET /api/admin/pipeline · POST /api/admin/pipeline/ingest · POST /api/admin/reports/generate · GET /api/admin/jobs/{id} |
| แอดมิน | /admin/feedback | Feedback และรายละเอียดคำตอบพร้อม Trace | GET /api/admin/feedback · GET /api/admin/messages/{id} |
| แอดมิน | /admin/logs | ประวัติคำขอและข้อผิดพลาด | GET /api/admin/logs |
| แอดมิน | /admin/audit | ประวัติการจัดการระบบ | GET /api/admin/audit |
| แอดมิน | /admin/reports | ตรวจ แก้ไข เผยแพร่ ถอนเผยแพร่ | GET /api/admin/reports · PATCH /api/admin/reports/{season}/{mw} · POST .../publish · POST .../unpublish |
| แอดมิน | /admin/users | ค้นหา เปลี่ยนบทบาท ระงับ/ปลดระงับบัญชี | GET /api/admin/users · PATCH /api/admin/users/{id} |
| แอดมิน | /admin/kb | สถิติดัชนี สร้างดัชนี ลบเอกสารรายตัว | GET /api/admin/kb/stats · POST /api/admin/kb/reindex · DELETE /api/admin/kb/documents/{id} |

## หลักฐานจากโค้ด

- สิทธิ์/การนำทาง: `services/01_web_app/components/AppShell.tsx`
- หน้าแอดมิน: `services/01_web_app/app/admin/[[...section]]/page.tsx`
- Users/KB: `services/01_web_app/components/AdminExtras.tsx`
- Proxy: `services/01_web_app/app/api/[...path]/route.ts`
- Auth / Admin guard: `services/02_api_backend/app/api/deps.py`
- การตอบแชท: `services/02_api_backend/app/services/chat_service.py`
- บันทึกคำตอบ: `services/02_api_backend/app/response_log/recorder.py`
- การเลือก route: `services/03_ai_router_agent/app/router.py`
- นำเข้า/รายงาน: `services/07_football_data/app/service.py`
- ทำนาย: `services/07_football_data/app/simulation.py`
- งานตามเวลา: `services/02_api_backend/app/workers/tasks.py`
- คลังความรู้: `services/05_retrieval_knowledge/app/core/config.py`
- การติดตั้ง: `docker-compose.yml`

## รูปแบบ

ใช้พื้น #030d15 และสีแดง #e9474e จากธีม Man United เริ่มต้นของ PANBALL พร้อม Inter/Noto Sans Thai และ Barlow Condensed ผ่าน Google Fonts; technical labels ใช้ Geist Mono ตาม diagram skill มี font fallback เมื่อ offline ไม่ได้เปลี่ยนไฟล์ skill หรือธีมแอป

## ข้อจำกัด

ไม่ได้ทดสอบด้วยบัญชีที่ได้รับ จึงไม่ยืนยันสถานะ container, feature flags ที่ใช้อยู่จริง หรือความสดของข้อมูล provider แผนภาพแสดงโครงสร้างที่มีใน implementation และอธิบายข้อยกเว้นไว้ใน HTML
