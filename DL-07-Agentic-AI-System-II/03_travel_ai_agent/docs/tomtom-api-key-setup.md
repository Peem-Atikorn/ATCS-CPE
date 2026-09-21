# คู่มือสมัคร TomTom Developer Portal และสร้าง API key

**ใช้ทำอะไร:** [`04_external_data_services/tomtom_transport.py`](../../04_external_data_services/tomtom_transport.py)
เรียก TomTom Orbis **Traffic Incidents API** เพื่อดึงเหตุการณ์จราจรจริงตามเส้นทาง — ถ้าไม่ตั้งค่า
`TOMTOM_API_KEY` โค้ดจะคืนค่า record สถานะ `unavailable` (`PROVIDER_NOT_CONFIGURED`) เสมอ ไม่ crash
แต่ทำให้ `transport_status` เป็น "ไม่มีข้อมูล" และลด confidence ของคำแนะนำทั้งระบบ (ดู
[`05_data_integration/integration.py`](../../05_data_integration/integration.py))

ตรวจสอบขั้นตอนสมัครจริงผ่านเบราว์เซอร์แล้วเมื่อ 21 กันยายน 2026 — ของจริงหน้าตาตรงตามที่เขียนไว้ด้านล่าง
ยกเว้นขั้นตอนหลัง "ยืนยันอีเมล" เป็นต้นไปที่มาจากความรู้ทั่วไปเรื่องแดชบอร์ด TomTom (UI ส่วนนี้อาจเปลี่ยนได้)

---

## 1. สมัครบัญชี TomTom

1. เปิด **<https://docs.tomtom.com>** (พอร์ทัลนักพัฒนาเดิมที่ `developer.tomtom.com` ย้ายมาที่นี่แล้ว)
2. กด **Sign In** มุมขวาบน
3. หน้าเข้าสู่ระบบจะมี 2 ทางเลือก:
   - **Register / sign in** — ใช้ทางนี้ถ้ายังไม่มีบัญชี (บัญชี TomTom แบบรวมศูนย์ตัวใหม่)
   - **Sign in to developer portal account** — สำหรับคนที่มีบัญชี `developer.tomtom.com` เดิมอยู่แล้วเท่านั้น
4. กด **Register / sign in** → กด **No account? Create one**
5. หน้า **Create an account** จะขอ **Email** ก่อน กด **Next**
6. ระบบจะส่งรหัสยืนยัน (verification code) ไปที่อีเมล — กรอกรหัส ตั้งรหัสผ่าน และกรอกข้อมูลเพิ่มเติม
   (ชื่อ/บริษัท) ตามที่ฟอร์มขอ
7. ยืนยันอีเมลเสร็จแล้วจะเข้าสู่แดชบอร์ดของ TomTom Developer Portal อัตโนมัติ

> ใช้อีเมลที่เข้าถึงได้จริงของทีม (ไม่ใช่อีเมลส่วนตัวคนเดียว) เผื่อทีมคนอื่นต้องเข้าไปดู/ต่ออายุคีย์ทีหลัง

---

## 2. สร้าง API key ในแดชบอร์ด

1. ในแดชบอร์ด มองหาเมนู **My Apps** / **Apps & keys** (ชื่ออาจต่างกันเล็กน้อยตาม UI ปัจจุบัน)
2. กด **Create app** / **Add API key** แล้วตั้งชื่อ เช่น `travel-safety-transport`
3. เลือกผลิตภัณฑ์ที่ต้องใช้:
   - **Traffic API** (จำเป็น — โค้ดของโปรเจกต์นี้เรียก endpoint `traffic/incidents/details`)
   - ไม่ต้องเปิด Maps/Routing/Search API อื่นถ้าไม่ได้ใช้ — คีย์เดียวใช้ได้กับหลายผลิตภัณฑ์ที่เปิดไว้
4. กดสร้าง ระบบจะสร้าง **API key** เป็นสตริงตัวอักษร/ตัวเลข (ไม่มี prefix พิเศษ) ให้คัดลอกเก็บไว้ทันที
5. ระดับฟรี (Freemium) ของ TomTom ให้โควตาจำกัดต่อวัน/ต่อเดือนต่อผลิตภัณฑ์ — เพียงพอสำหรับ dev/testing
   แต่ถ้าจะใช้จริงกับผู้ใช้จำนวนมาก ต้องดูแผนราคาที่ **Pricing** บน docs.tomtom.com

---

## 3. ตั้งค่าในโปรเจกต์

ห้าม commit คีย์จริงลง git เด็ดขาด — ใส่เฉพาะใน `.env` (อยู่ใน `.gitignore` แล้ว) หรือ secret ของ
environment ที่รันจริง

**Local dev** — [`03_travel_ai_agent/.env`](../.env.example) (คัดลอกจาก `.env.example`):

```bash
TOMTOM_API_KEY=<คีย์ที่ได้จากแดชบอร์ด>
```

**Docker Compose ของโมดูล 03** ([`compose.yaml`](../compose.yaml)) อ่านจากตัวแปรแวดล้อมของเครื่องที่รัน
`docker compose` อยู่แล้ว (`TOMTOM_API_KEY: "${TOMTOM_API_KEY:-}"`) — ตั้งใน shell หรือไฟล์ `.env` ที่
`docker compose` มองเห็นก่อนสั่งรัน:

```bash
export TOMTOM_API_KEY=<คีย์ที่ได้จากแดชบอร์ด>
docker compose up -d
```

**Docker Compose รวมทั้งระบบ** (`docker-compose.integration.yml` ที่ root) ยังไม่ได้ส่งต่อ
`TOMTOM_API_KEY` ให้ service `travel-agent` — ถ้าจะใช้คีย์จริงกับสแตกนี้ ต้องเพิ่มบรรทัด
`TOMTOM_API_KEY: "${TOMTOM_API_KEY:-}"` ในส่วน `environment:` ของ service นั้นเองก่อน (ยังไม่ได้แก้ให้
เพราะไฟล์นี้อยู่นอกขอบเขตงานที่ทำไปแล้ว)

---

## 4. ทดสอบว่าคีย์ใช้งานได้

```bash
cd DL-07-Agentic-AI-System-II/04_external_data_services
python -c "
from datetime import datetime, timezone
from tomtom_transport import fetch_canonical_transport
# กรุงเทพฯ (bbox ทดสอบ)
records = fetch_canonical_transport(
    (100.40, 13.65, 100.60, 13.85),
    now=datetime.now(timezone.utc),
    api_key='<คีย์ที่ได้จากแดชบอร์ด>',
)
print(records[0]['status'], records[0].get('error_code'))
"
```

- `status` เป็น `"available"` (หรือ `[]` ถ้าไม่มีเหตุการณ์ในพื้นที่ตอนนั้น) → คีย์ใช้ได้
- `status` เป็น `"unavailable"` กับ `error_code = "PROVIDER_AUTH_FAILED"` → คีย์ผิดหรือยังไม่ได้เปิดสิทธิ์ Traffic API
- `error_code = "PROVIDER_NOT_CONFIGURED"` → ลืมส่งคีย์ (ทดสอบไม่ได้ใส่ `api_key=`)
