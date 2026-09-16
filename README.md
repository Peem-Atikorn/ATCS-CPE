# Team D — DL-07: Agentic AI System II

โปรเจกต์กลุ่มวิชา Advanced Topics in Computer Software (04622404)
พัฒนาตามแผนของอาจารย์ใน [`DL-07-Agentic-AI-System-II/`](DL-07-Agentic-AI-System-II/)

## 👥 ตารางแบ่งงาน — 1 คน 1 โมดูล

7 คน 8 โมดูล → มี 1 คนรับ 2 โมดูล (ตกลงกันในทีม)

| # | โมดูล | งานหลัก | ผู้รับผิดชอบ | GitHub | branch |
|---|---|---|---|---|---|
| 01 | `01_web_app` | Next.js, TypeScript, แผนที่, live alert | _TBD_ | `@_TBD_` | `ชื่อ-01-web-app` |
| 02 | `02_api_backend` | FastAPI gateway, auth, CORS | _TBD_ | `@_TBD_` | `ชื่อ-02-api-backend` |
| 03 | `03_travel_ai_agent` | LLM planner, tool routing | _TBD_ | `@_TBD_` | `ชื่อ-03-travel-ai-agent` |
| 04 | `04_external_data_services` | adapter weather / transport / disaster | _TBD_ | `@_TBD_` | `ชื่อ-04-external-data` |
| 05 | `05_data_integration` | normalize → canonical schema | _TBD_ | `@_TBD_` | `ชื่อ-05-data-integration` |
| 06 | `06_risk_knowledge_services` | risk model + RAG knowledge base | _TBD_ | `@_TBD_` | `ชื่อ-06-risk-knowledge` |
| 07 | `07_decision_llm_engine` | ตัดสินใจ + อธิบายผล | _TBD_ | `@_TBD_` | `ชื่อ-07-decision-llm` |
| 08 | `08_recommendation_feedback` | ข้อเสนอแนะ + feedback loop | _TBD_ | `@_TBD_` | `ชื่อ-08-recommendation` |

แต่ละโมดูลมี `01_env.txt` (สภาพแวดล้อม) · `02_step.txt` (ขั้นตอน) · `03_process.txt` (เทคนิค)

---

## 🌿 โครงสร้าง branch

```
main                    ← เวอร์ชันส่งอาจารย์ / ใช้งานได้จริงเสมอ
 │                        merge จาก develop เฉพาะตอนถึง milestone
 └── develop            ← branch รวมงานของทุกคน (integration)
      │
      ├── sakda-03-travel-ai-agent        ← branch ประจำตัว อยู่ยาวทั้งเทอม
      ├── somchai-04-external-data        ← ไม่ลบหลัง merge
      ├── nattapong-01-web-app
      └── ... (1 คน 1 branch)
```

### กฎการตั้งชื่อ branch

```
<ชื่อตัวเอง>-<เลขโมดูล>-<ชื่อโมดูลย่อ>
```

| ตัวอย่าง | ถูก/ผิด |
|---|---|
| `sakda-03-travel-ai-agent` | ✅ |
| `somchai-04-external-data` | ✅ |
| `nattapong-07-decision-llm` | ✅ |
| `sakda` | ❌ ไม่รู้ว่าทำโมดูลไหน |
| `feature-3` | ❌ ไม่รู้ว่าใครทำ |
| `Sakda_03_Travel_AI_Agent` | ❌ ใช้ตัวพิมพ์เล็กและขีดกลางเท่านั้น |

**คนที่รับ 2 โมดูล** ให้สร้าง 2 branch แยกกัน เช่น `somchai-07-decision-llm` และ `somchai-08-recommendation`
เพื่อให้ PR แยกกันชัดเจน อาจารย์ตรวจง่าย

### หน้าที่ของแต่ละ branch

| branch | ใครแก้ได้ | push ตรงได้ไหม |
|---|---|---|
| `main` | ไม่มีใคร | ❌ เข้าผ่าน PR จาก `develop` เท่านั้น |
| `develop` | ไม่มีใคร | ❌ เข้าผ่าน PR จาก branch ส่วนตัวเท่านั้น |
| `ชื่อ-NN-โมดูล` | เจ้าของ branch คนเดียว | ✅ push ได้ตามใจ วันละกี่ครั้งก็ได้ |

---

## 🚀 วันแรก — ทำครั้งเดียว

### 1. ตั้งชื่อตัวเองให้ถูก (สำคัญที่สุด เพราะอาจารย์ตรวจรายบุคคล)

```bash
git config --global user.name "ชื่อจริงภาษาอังกฤษ"
```

```bash
git config --global user.email "email-ที่ใช้สมัคร-github@example.com"
```

> ⚠️ **email ต้องตรงกับที่ใช้สมัคร GitHub** ไม่งั้น commit ของคุณจะไม่ผูกกับโปรไฟล์
> และไม่ขึ้นในหน้า Contributors — **แก้ย้อนหลังไม่ได้**

เช็คว่าถูกแล้ว:

```bash
git config --global user.name; git config --global user.email
```

### 2. clone repo

```bash
git clone https://github.com/sakda1306/Advanced-Topic-in-Computer-Software-Course-Team-D.git
```

### 3. สร้าง `.env` ของตัวเอง

```bash
copy .env.example .env
```

แล้วเปิด `.env` เติมค่าจริง — **ไฟล์นี้ไม่ขึ้น git** ทุกคนมีของตัวเอง
ถ้าต้องเพิ่มตัวแปรใหม่ ให้เพิ่ม**ชื่อตัวแปรค่าว่าง**ใน `.env.example` แล้ว commit เฉพาะไฟล์นั้น

### 4. สร้าง branch ประจำตัว — ครั้งเดียว ใช้ทั้งเทอม

```bash
git switch develop
```

```bash
git switch -c sakda-03-travel-ai-agent
```

*(เปลี่ยนเป็นชื่อและโมดูลของตัวเอง — ดูตารางแบ่งงานข้างบน)*

```bash
git push -u origin sakda-03-travel-ai-agent
```

---

## 🔄 การทำงานประจำวัน

### A. เขียนงานของตัวเอง — ทำได้ตลอด ไม่ต้องรอใคร

```bash
git switch sakda-03-travel-ai-agent
```

```bash
git add -A; git commit -m "feat(03): เพิ่ม intent router"
```

```bash
git push
```

**commit และ push บ่อย ๆ ได้เลย** วันละ 5 ครั้งก็ได้ ไม่กระทบใคร เพราะอยู่ใน branch ตัวเอง
ข้อดี: เป็นหลักฐานว่าคุณทำงานสม่ำเสมอ ไม่ใช่มาทำรอบเดียวคืนก่อนส่ง

### B. งานเสร็จเป็นก้อน → ส่งขึ้น `develop`

1. push งานล่าสุดขึ้น branch ตัวเองให้ครบ
2. เปิด PR บนเว็บ: `ชื่อ-03-travel-ai-agent` → **`develop`**
3. ขอเพื่อน 1 คน approve
4. กด **Create a merge commit** *(ห้ามใช้ Squash — ดูเหตุผลข้างล่าง)*
5. **ไม่ต้องลบ branch** — ใช้ต่อได้เลย

### C. ดึงงานเพื่อนมาใช้ — ทำทุกเช้า

พอเพื่อนคนที่ 1 merge ขึ้น `develop` แล้ว คนที่ 2 ดึงมาใช้แบบนี้:

```bash
git switch develop; git pull
```

```bash
git switch sakda-03-travel-ai-agent
```

```bash
git merge develop
```

```bash
git push
```

> 💡 **ทำทุกเช้าก่อนเริ่มงาน** อย่ารอเป็นอาทิตย์
> ยิ่ง branch ตัวเองห่างจาก `develop` นาน ยิ่ง conflict หนักตอน merge
> merge ทุกวัน = conflict เล็ก ๆ แก้ 2 นาที · merge เดือนละครั้ง = conflict 200 บรรทัด

### ภาพรวมทั้งวงจร

```
     branch ตัวเอง                develop                 branch เพื่อน
          |                          |                          |
  commit -|                          |                          |
  commit -|                          |                          |
  push ---|                          |                          |
          |                          |                          |
          |---- PR + merge --------->|                          |
          |                          |<---- PR + merge ---------|
          |                          |                          |
          |<--- git merge develop ---|                          |
          |     (ได้งานเพื่อนมา)      |---- git merge develop -->|
          |                          |                          |
```

---

## ❓ ทำไมห้ามใช้ Squash merge

เพราะ branch ของเราอยู่ยาวและ merge กลับไปกลับมา:

- **Squash** จะยุบ commit ทั้งหมดเป็นก้อนใหม่ที่ `develop` มองว่า "ไม่เคยเห็น" → รอบหน้าที่คุณ `git merge develop` กลับเข้า branch ตัวเอง git จะเจอการเปลี่ยนแปลงเดิมซ้ำสองรอบ → **conflict แปลก ๆ ที่หาสาเหตุยากมาก**
- **Merge commit** เก็บสายสัมพันธ์ไว้ครบ git รู้ว่าอะไร merge ไปแล้ว → merge กี่รอบก็ไม่ชน และ commit ทุกอันของคุณยังคงชื่อคุณครบ

---

## 🏆 เครดิตรายบุคคล — อาจารย์ตรวจว่าใครทำส่วนไหน

### กฎเหล็ก 3 ข้อ

1. **ตั้ง `git config` ให้ถูกก่อนเขียนโค้ดบรรทัดแรก** (ดูหัวข้อวันแรก ข้อ 1)
2. **push จากเครื่องตัวเอง ด้วยบัญชีตัวเอง เปิด PR ด้วยตัวเอง**
   - ❌ ห้าม "ส่งไฟล์ให้เพื่อน push ให้" → **คุณจะได้เครดิต 0**
   - ❌ ห้ามยืมเครื่องเพื่อน commit → เครดิตไปเพื่อนทั้งก้อน
3. **ถ้าช่วยกันเขียนจริง** ใส่ trailer ท้าย commit message ให้ GitHub นับเครดิตทั้งคู่:

   ```
   feat(03): เพิ่ม intent router

   Co-authored-by: Somchai <somchai@example.com>
   ```

### เช็คเครดิตตัวเองทุกสัปดาห์

```bash
git shortlog -sne --all
```

```bash
git log --pretty=%an -- "DL-07-Agentic-AI-System-II/03_travel_ai_agent/" | sort | uniq -c | sort -rn
```

*(เปลี่ยน path เป็นโมดูลของตัวเอง)* ถ้าชื่อคุณไม่ขึ้น หรือขึ้นเป็นคนอื่น → **แก้ทันที อย่ารอถึงวันส่ง**

### ที่อาจารย์เปิดดูได้

| หน้า | บอกอะไร |
|---|---|
| Insights › Contributors | กราฟจำนวน commit / บรรทัด แยกตามคน |
| Pull requests › Closed | ใครเปิด PR อะไร เมื่อไหร่ กี่อัน |
| ปุ่ม Blame ในไฟล์ | ใครเขียนบรรทัดไหน |
| `CODEOWNERS` | ใครรับผิดชอบโฟลเดอร์ไหน |

---

## 💬 commit message

```
<type>(<เลขโมดูล>): <ทำอะไร>
```

| type | ใช้เมื่อ | ตัวอย่าง |
|---|---|---|
| `feat` | เพิ่มของใหม่ | `feat(04): เพิ่ม weather adapter` |
| `fix` | แก้บั๊ก | `fix(02): แก้ CORS header ผิด` |
| `docs` | เอกสาร | `docs(06): อธิบาย risk threshold` |
| `refactor` | รื้อโค้ดโดยไม่เปลี่ยนพฤติกรรม | `refactor(05): แยก schema validator` |
| `test` | เทส | `test(03): เพิ่มเทส intent router` |
| `chore` | งานบ้าน config | `chore: อัปเดต .env.example` |

เขียนภาษาไทยได้ ขอแค่บอกให้ชัดว่าทำอะไร

---

## 🚨 ไฟล์ที่ conflict ได้ — ต้องบอกในกลุ่มก่อนแก้

เพราะ 8 โมดูลอยู่คนละโฟลเดอร์ ปกติจะไม่ชนกันเลย ยกเว้นไฟล์กลางเหล่านี้:

| ไฟล์ | เพราะ |
|---|---|
| `.env.example` | ทุกคนอยากเพิ่มตัวแปรของตัวเอง |
| `docker-compose.yml` | ทุกคนอยากเพิ่ม service ของตัวเอง |
| `README.md` | ตารางแบ่งงานอยู่ในนี้ |
| `.gitignore` · `.gitattributes` | มีคนเพิ่ม pattern |

**กฎ:** แก้ไฟล์กลาง = แยกเป็น PR เล็กของมันเอง merge ให้ไวที่สุด อย่าปนกับ PR ฟีเจอร์

---

## 📅 ลำดับการทำงาน

8 โมดูลเริ่มพร้อมกันได้ **แต่ต้องตกลงสัญญาข้อมูลก่อน** ไม่งั้นจะเจอ "ผมเขียนเสร็จแล้ว แต่ข้อมูลที่ได้มาหน้าตาไม่ตรงที่คิด"

```
เฟส 0   ทุกคนนั่งตกลงร่วมกัน  ← สำคัญที่สุด ห้ามข้าม
        canonical schema + API contract ของแต่ละโมดูล
        เขียนลง PR เดียวเข้า develop ให้ทุกคนอ้างอิง

เฟส 1   04 external data ──▶ 05 integration ──▶ 06 risk/RAG
        02 api gateway     (ทำขนานได้)
        01 web app         (ทำขนานได้ ใช้ mock data ไปก่อน)

เฟส 2   03 agent + 07 decision   (ต้องรอ 04-06 มีของจริงให้เรียก)

เฟส 3   08 recommendation + เชื่อมทุกอย่างด้วย docker compose
```

**ระหว่างรอคนอื่น ไม่ต้องนั่งเฉย** — เขียนโครงโมดูลตัวเอง เขียนเทส เขียนเอกสาร ทำ mock ไปก่อนได้เลย
พอเพื่อนส่งของจริงขึ้น `develop` ค่อย `git merge develop` แล้วสลับจาก mock เป็นของจริง

---

## ⚙️ ตั้งค่า GitHub (เจ้าของ repo ทำครั้งเดียว)

### Settings › General › Pull Requests

| ตั้งค่า | ค่า |
|---|---|
| Allow merge commits | ✅ **เปิด** |
| Allow squash merging | ❌ **ปิด** (ชนกับ long-lived branch) |
| Allow rebase merging | ❌ ปิด |
| Automatically delete head branches | ❌ **ปิด** (branch เราอยู่ยาว ห้ามให้ลบ) |

### Settings › General › Default branch

ตั้งเป็น **`develop`**

> เพราะ GitHub จะตั้ง base ของ PR เป็น default branch ให้อัตโนมัติ
> ถ้าปล่อยเป็น `main` ทุกคนจะเผลอเปิด PR เข้า `main` แทน `develop` ซึ่งผิด
> อาจารย์ยังเปิดดู repo ได้ปกติ เพราะ README เหมือนกันทั้งสอง branch

### Settings › Rules › Rulesets — สร้าง 2 อัน

| ruleset | target | กฎ |
|---|---|---|
| protect-main | `main` | Require a pull request · Required approvals **2** |
| protect-develop | `develop` | Require a pull request · Required approvals **1** |

### Settings › Collaborators

เชิญเพื่อนทั้ง 7 คน role **Write**

> ⚠️ เชิญเพื่อนให้เสร็จ **ก่อน** เปิด ruleset ไม่งั้นจะติดกฎตัวเองตอนทำงานคนเดียว

---

## 🛠 Stack ตามแผนอาจารย์

- **Frontend** Node.js 20 LTS · Next.js · TypeScript · Tailwind · MapLibre GL JS
- **Backend** Python 3.12 · FastAPI · Pydantic · httpx · Tenacity
- **Data** PostgreSQL · Redis · Vector DB
- **Orchestration** Docker Compose *(ยังไม่ได้เขียน อยู่ในเฟส implement)*
- **Monitoring** Prometheus · Grafana · OpenTelemetry

---

## 🆘 ติดปัญหาบ่อย

| อาการ | แก้ |
|---|---|
| `git switch develop` ขึ้น `pathspec did not match` | ยังไม่มี local develop → `git switch -c develop origin/develop` |
| merge แล้วขึ้น CONFLICT | เปิดไฟล์ หา `<<<<<<<` เลือกเก็บส่วนที่ถูก ลบเครื่องหมายออก แล้ว `git add` + `git commit` |
| push แล้วขึ้น `rejected` | มีคน push ทับ → `git pull` ก่อน แล้ว push อีกครั้ง |
| เผลอ commit `.env` | บอกในกลุ่ม**ทันที** และ **revoke API key ทุกตัว** — ลบ commit ทีหลังไม่พอ |
| ทำงานผิด branch | `git stash` → `git switch <branch-ถูก>` → `git stash pop` |
