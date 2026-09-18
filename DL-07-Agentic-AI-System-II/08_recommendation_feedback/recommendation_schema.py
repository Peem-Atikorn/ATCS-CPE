"""
RecommendationResponse Schema
Module 08: Recommendation and Feedback

สัญญา (contract) ระหว่าง Module 07 (Decision & LLM Engine) และ Module 08
สร้างตามฟิลด์ที่กำหนดใน 03_process.txt

อัปเดตตาม README ของงาน 07 (prototype) — จุดที่เปลี่ยนจากร่างแรก:
  1. action_code เปลี่ยนมาใช้ชื่อภายในของ 07 (NORMAL/CHANGE_ROUTE/DELAY/AVOID)
     ไม่ใช่ TRAVEL_NORMALLY/... ที่เดาไว้ก่อนหน้า — เพิ่ม backend_action_code
     เป็น mapping ที่ 07 "เสนอ" ไว้ แต่ยังไม่ยืนยันว่าตรงกับ Backend 02 จริง
  2. confidence เปลี่ยนจาก float(0-1) เป็น ordinal HIGH/MEDIUM/LOW
     พร้อม escalation flag แยก — 07 ระบุชัดว่านี่ "ไม่ใช่ probability ที่สอบเทียบแล้ว"
  3. แยก citations (หลักฐานที่กฎใช้จริง) ออกจาก evidence_status
     (หลักฐานทั้งหมดที่ตรวจ รวมที่ไม่ได้ใช้) ตามที่ 07 เก็บสองชุดแยกกัน

⚠️ สถานะ: 07 เป็น prototype ทดลอง ยังไม่ผ่านการอนุมัตินโยบายให้ใช้ตัดสินใจ
   การเดินทางจริง (POLICY_APPROVED=true อย่างเดียวไม่พอ) — เช่นเดียวกัน schema
   นี้เป็นฉบับร่างที่ยังต้องนัดยืนยัน contract กับทีม 07 และทีม 02 ก่อนใช้จริง

⚠️ จุดที่ "เดา" ไว้ชั่วคราว ต้องถามทีม 07 ให้ชัดก่อน freeze:
   - ค่า RiskLevel มี CRITICAL จริงหรือไม่ (README ของ 07 พูดถึงแค่ระดับ HIGH)
   - เงื่อนไขที่ต้องมี emergency_instructions/official_contacts (ผู้เขียนสมมติว่า
     ผูกกับ escalation=True เพราะ 07 บอกว่า AVOID+escalation คือ fallback เวลา
     ข้อมูลไม่ครบ/กำกวม — แต่ 07 ไม่ได้กำหนด field emergency_instructions ไว้ตรงๆ)
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ============================================================
# 1) ENUM: จำกัดค่าที่รับได้ ป้องกันการพิมพ์ผิดหรือส่งค่าที่ไม่รู้จัก
# ============================================================

class ActionCode(str, Enum):
    """
    ใช้ชื่อภายในตาม guide ของ 07 ตรงตามที่ README ของ 07 ระบุ
    ("ชื่อ action ภายในใช้ตาม guide ของ 07: NORMAL, CHANGE_ROUTE, DELAY, AVOID")
    ห้ามเปลี่ยนชื่อเหล่านี้เอง — ถ้าฝั่ง UI ต้องการชื่อที่อ่านง่ายกว่า
    ให้ทำผ่าน backend_action_code (ดูใน RecommendationResponse) ไม่ใช่แก้ enum นี้
    """
    NORMAL = "NORMAL"
    CHANGE_ROUTE = "CHANGE_ROUTE"
    DELAY = "DELAY"
    AVOID = "AVOID"


class RiskLevel(str, Enum):
    """
    ⚠️ 07 ยืนยันแค่ระดับ HIGH ชัดเจน (กฎ: "ความเสี่ยง HIGH จะไม่ถูกลดเป็น
    CHANGE_ROUTE") ส่วน LOW/MEDIUM/CRITICAL ผู้เขียนเติมให้ครบตามแพทเทิร์น
    ต้องยืนยันกับทีม 07 ว่ามีค่าเหล่านี้จริงหรือไม่ก่อน freeze
    """
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ConfidenceLevel(str, Enum):
    """
    เปลี่ยนจาก float(0.0-1.0) เป็น ordinal ตาม 07:
    "confidence แบบลำดับ HIGH / MEDIUM / LOW ... ไม่ใช่ความน่าจะเป็นที่ผ่าน
    การสอบเทียบ" — ห้ามนำไปคำนวณทางสถิติเหมือน probability
    """
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class FeedbackCategory(str, Enum):
    """ตาม 03_process.txt: 'Classify feedback as helpful, incorrect, ...'"""
    HELPFUL = "HELPFUL"
    INCORRECT = "INCORRECT"
    STALE = "STALE"
    UNSAFE = "UNSAFE"
    ROUTE_ISSUE = "ROUTE_ISSUE"
    SOURCE_ISSUE = "SOURCE_ISSUE"


# ============================================================
# 2) NESTED MODELS: ส่วนประกอบย่อยที่ใช้ซ้ำได้
# ============================================================

class Route(BaseModel):
    """ใช้ทั้งกับ primary_route และ alternatives"""
    route_id: str
    description: str
    estimated_time_minutes: Optional[int] = Field(default=None, ge=0)
    trade_offs: Optional[str] = Field(
        default=None,
        description="ใช้อธิบายข้อดี-ข้อเสียเทียบกับ primary_route (เฉพาะ alternatives)",
    )


class SourceCitation(BaseModel):
    """
    หลักฐานที่ "ผ่านการตรวจและกฎใช้จริง" เท่านั้น — ตาม 07:
    "citations เก็บเฉพาะหลักฐานที่กฎใช้และผ่านการตรวจเวลา/ประเภท/สถานะทางการ"
    ห้ามใช้ list นี้เป็นรายการหลักฐานทั้งหมด ให้ดู EvidenceStatus แทน
    """
    source_name: str
    url: Optional[str] = None
    retrieved_at: datetime


class EvidenceStatus(BaseModel):
    """
    หลักฐาน "ทุกชิ้น" ที่ถูกตรวจ รวมชิ้นที่ไม่ได้ถูกใช้อ้างอิงด้วย — ตาม 07:
    "evidence_status แสดง ID และผลตรวจของหลักฐานทั้งหมด รวมถึงรายการที่ไม่ได้
    ใช้อ้างอิง" — สำคัญมากสำหรับ 08 ตอนอธิบายเหตุผลให้ผู้ใช้: ถ้าหลักฐาน
    บางชิ้นถูกตัดออกจาก citations ไม่ได้แปลว่า "ถนนเปิดแล้ว"
    field `check_result` เป็น string อิสระตอนนี้ (เช่น "STALE", "VALID",
    "UNOFFICIAL") — ยังไม่มี enum ตายตัวจาก 07 ต้องขอ field จริงจาก /docs
    """
    evidence_id: str
    used_in_citation: bool
    check_result: str
    note: Optional[str] = None


class EmergencyContact(BaseModel):
    """
    ตาม 01_env.txt: 'Emergency text and contact numbers must match
    the user's location and have a valid effective date.'
    """
    name: str
    phone: str
    region: str
    effective_date: datetime


# ============================================================
# 3) MAIN MODEL: RecommendationResponse
# ============================================================

class RecommendationResponse(BaseModel):
    # --- Metadata / version ---
    request_id: str
    schema_version: str = Field(
        ..., description="ต้องตรงกับ RECOMMENDATION_SCHEMA_VERSION ที่ config ไว้"
    )

    # --- Core decision (จาก Module 07) ---
    action_code: ActionCode  # ชื่อภายในของ 07: NORMAL/CHANGE_ROUTE/DELAY/AVOID
    backend_action_code: Optional[str] = Field(
        default=None,
        description=(
            "Mapping ที่ 07 'เสนอ' มาให้ (เช่น NORMAL -> TRAVEL_NORMALLY) "
            "ยังไม่ยืนยันว่าตรงกับ Backend 02 จริง — ห้าม hardcode logic ที่อิง "
            "field นี้จนกว่าจะยืนยัน contract ร่วมกันแล้ว"
        ),
    )
    risk_level: RiskLevel
    confidence: ConfidenceLevel  # ordinal, ไม่ใช่ probability
    escalation: bool = Field(
        ..., description="true เมื่อ 07 ยกระดับความระมัดระวัง (เช่น ข้อมูลไม่ครบ/กำกวม)"
    )

    # --- ลำดับการแสดงผล ตาม 02_step.txt:
    #     immediate action -> reason -> options -> sources ---
    short_summary: str
    immediate_actions: list[str] = Field(default_factory=list)

    primary_route: Optional[Route] = None
    alternatives: list[Route] = Field(default_factory=list)

    emergency_instructions: Optional[list[str]] = None
    official_contacts: list[EmergencyContact] = Field(default_factory=list)

    reasons: list[str] = Field(default_factory=list)
    citations: list[SourceCitation] = Field(
        default_factory=list, description="เฉพาะหลักฐานที่กฎใช้จริงและผ่านการตรวจ"
    )
    evidence_status: list[EvidenceStatus] = Field(
        default_factory=list, description="หลักฐานทั้งหมดที่ตรวจ รวมที่ไม่ได้ใช้อ้างอิง"
    )

    # --- Data freshness ---
    observed_at: datetime
    fetched_at: datetime
    expires_at: datetime

    # --- Transparency ---
    limitations: Optional[list[str]] = None
    degraded_services: Optional[list[str]] = None

    # ========================================================
    # 4) CUSTOM VALIDATION: กฎ safety-critical จาก 03_process.txt
    # ========================================================

    # ⚠️ 07 ไม่มี action_code = EMERGENCY (มีแค่ NORMAL/CHANGE_ROUTE/DELAY/AVOID)
    # ผู้เขียนสมมติว่ากรณีต้องมี emergency_instructions คือตอน escalation=True
    # ร่วมกับ risk_level สูง เพราะ 07 บอกว่า AVOID+escalation คือ fallback เวลา
    # ข้อมูลไม่ครบ/กำกวม — นี่คือ "สมมติฐานชั่วคราว" ต้องเอาไปถามทีม 07 ให้ชัด
    # ว่าเขาคาดหวังให้ 08 ใส่ emergency_instructions เองทั้งหมด หรือมี field
    # ส่งมาจาก 07 ตรงๆ ที่เรายังไม่เห็นใน README
    @field_validator("official_contacts")
    @classmethod
    def escalation_should_have_contacts(cls, v, info):
        escalation = info.data.get("escalation")
        risk = info.data.get("risk_level")
        if escalation and risk in (RiskLevel.HIGH, RiskLevel.CRITICAL) and not v:
            raise ValueError(
                "escalation=True และ risk_level สูง ควรมี official_contacts "
                "อย่างน้อย 1 รายการ (สมมติฐานชั่วคราว — ยืนยันกับทีม 07 ก่อน freeze)"
            )
        return v

    @field_validator("expires_at")
    @classmethod
    def expires_after_fetched(cls, v, info):
        fetched = info.data.get("fetched_at")
        if fetched and v <= fetched:
            raise ValueError("expires_at ต้องมากกว่า fetched_at (ข้อมูลต้องยังไม่หมดอายุตอนที่ fetch)")
        return v

    @field_validator("alternatives")
    @classmethod
    def alternatives_need_primary(cls, v, info):
        primary = info.data.get("primary_route")
        if v and not primary:
            raise ValueError("มี alternatives ได้ก็ต่อเมื่อมี primary_route แล้ว")
        return v


# ============================================================
# 5) FEEDBACK SCHEMA (แยกจาก RecommendationResponse)
#    ตาม 02_step.txt: "Store explicit feedback separately from
#    automatic telemetry" + "Use a pseudonymous ID"
# ============================================================

class FeedbackSubmission(BaseModel):
    request_id: str  # อ้างอิงกลับไปยัง RecommendationResponse ที่ถูก feedback
    pseudonymous_user_id: str
    category: FeedbackCategory
    comment: Optional[str] = None
    submitted_at: datetime

    @field_validator("comment")
    @classmethod
    def unsafe_needs_comment(cls, v, info):
        category = info.data.get("category")
        if category == FeedbackCategory.UNSAFE and not v:
            raise ValueError("feedback ประเภท UNSAFE ต้องมี comment อธิบายเหตุผลเสมอ")
        return v