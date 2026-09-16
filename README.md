# Team D — DL-07: Agentic AI System II

โปรเจกต์กลุ่มวิชา Advanced Topics in Computer Software (04622404)
พัฒนาตามแผนของอาจารย์ใน [`DL-07-Agentic-AI-System-II/`](DL-07-Agentic-AI-System-II/)

> โฟลเดอร์แผนเปลี่ยนชื่อจาก `DL-07: Agentic AI System II` (ตัดเครื่องหมาย `:` ออก)
> เพราะ Windows ใช้ `:` ในชื่อไฟล์ไม่ได้ เนื้อหาข้างในเหมือนต้นฉบับ 100%

## Travel Risk & Recommendation Agent — 8 โมดูล

| # | โมดูล | หน้าที่ | ผู้รับผิดชอบ |
|---|---|---|---|
| 01 | `01_web_app` | Next.js + TypeScript, แผนที่, live alert | _TBD_ |
| 02 | `02_api_backend` | FastAPI gateway, auth, CORS | _TBD_ |
| 03 | `03_travel_ai_agent` | LLM planner, tool routing | _TBD_ |
| 04 | `04_external_data_services` | adapter: weather / transport / disaster | _TBD_ |
| 05 | `05_data_integration` | normalize เป็น canonical schema | _TBD_ |
| 06 | `06_risk_knowledge_services` | risk model + RAG knowledge base | _TBD_ |
| 07 | `07_decision_llm_engine` | ตัดสินใจ + อธิบายผล | _TBD_ |
| 08 | `08_recommendation_feedback` | ข้อเสนอแนะ + feedback loop | _TBD_ |

แต่ละโมดูลมี `01_env.txt` (สภาพแวดล้อม), `02_step.txt` (ขั้นตอน), `03_process.txt` (เทคนิค)

## เริ่มงาน (สมาชิกใหม่)

```bash
git clone <repo-url>
cd Advanced-Topic-in-Computer-Software-Course-Team-D
cp .env.example .env    # แล้วเติมค่าจริงลงใน .env
```

`.env` ถูก `.gitignore` กันไว้ — **ห้าม commit เด็ดขาด** ถ้าต้องเพิ่มตัวแปรใหม่
ให้เพิ่มชื่อตัวแปร (ค่าว่าง) ใน `.env.example` แล้ว commit เฉพาะไฟล์นั้น

## Git workflow — GitHub Flow

`main` ใช้งานได้เสมอ **ห้าม push ตรง** ทุกอย่างเข้าผ่าน Pull Request

```bash
git switch main && git pull                  # 1. อัปเดตก่อนเสมอ
git switch -c feat/03-travel-ai-agent        # 2. แตก branch
git add -A && git commit -m "feat(03): ..."  # 3. commit
git push -u origin feat/03-travel-ai-agent   # 4. push แล้วเปิด PR
```

### ชื่อ branch

| ประเภท | รูปแบบ | ตัวอย่าง |
|---|---|---|
| ฟีเจอร์ใหม่ | `feat/<เลขโมดูล>-<ชื่อ>` | `feat/04-external-data` |
| แก้บั๊ก | `fix/<เลขโมดูล>-<ชื่อ>` | `fix/02-cors-header` |
| เอกสาร | `docs/<ชื่อ>` | `docs/api-contract` |
| งานบ้าน | `chore/<ชื่อ>` | `chore/ci-pipeline` |

### commit message

`<type>(<เลขโมดูล>): <สิ่งที่ทำ>` เช่น `feat(06): เพิ่ม hybrid retrieval BM25 + vector`
type ที่ใช้: `feat` `fix` `docs` `chore` `refactor` `test`

### กฎ PR

- 1 PR = 1 โมดูล/1 เรื่อง อย่ารวมหลายเรื่อง
- ต้องมีคนอื่นอย่างน้อย 1 คน approve
- merge แบบ **Squash** เท่านั้น เพื่อให้ประวัติ `main` เป็นเส้นตรง
- merge แล้วลบ branch ทิ้ง

เพราะแต่ละโมดูลอยู่คนละโฟลเดอร์ ถ้าแบ่งงานตามตารางข้างบน **conflict จะเกิดน้อยมาก**
ยกเว้นไฟล์ที่ใช้ร่วมกัน (`.env.example`, `docker-compose.yml`, README) — ถ้าจะแก้ให้บอกในกลุ่มก่อน

## Stack ตามแผน

- **Frontend** Node.js 20 LTS, Next.js, TypeScript, Tailwind, MapLibre GL JS
- **Backend** Python 3.12, FastAPI, Pydantic, httpx, Tenacity
- **Data** PostgreSQL, Redis, Vector DB
- **Orchestration** Docker Compose (ยังไม่ได้เขียน — อยู่ในเฟส implement)
- **Monitoring** Prometheus, Grafana, OpenTelemetry
