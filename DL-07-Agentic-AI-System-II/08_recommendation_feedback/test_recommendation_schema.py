"""
ตัวอย่างการใช้งาน + เทส RecommendationResponse (เวอร์ชันอัปเดตตาม README ของงาน 07)
รันด้วย: pytest test_recommendation_schema.py -v
"""

from datetime import datetime, timedelta

import pytest
from pydantic import ValidationError

from recommendation_schema import (
    ActionCode,
    ConfidenceLevel,
    EmergencyContact,
    EvidenceStatus,
    FeedbackCategory,
    FeedbackSubmission,
    RecommendationResponse,
    Route,
    RiskLevel,
    SourceCitation,
)

NOW = datetime.utcnow()


# ============================================================
# CASE 1: เคสปกติ - Change Route (valid, ไม่มี escalation)
# ============================================================
def test_change_route_valid():
    resp = RecommendationResponse(
        request_id="req-001",
        schema_version="1.0.0",
        action_code=ActionCode.CHANGE_ROUTE,
        backend_action_code="CHANGE_ROUTE",  # ชื่อเดียวกันตามที่ 07 ระบุ
        risk_level=RiskLevel.MEDIUM,
        confidence=ConfidenceLevel.HIGH,
        escalation=False,
        short_summary="ฝนตกหนักบนเส้นทางหลัก แนะนำเปลี่ยนเส้นทาง",
        immediate_actions=["ใช้เส้นทางสำรอง B", "ลดความเร็วบนถนนเปียก"],
        primary_route=Route(
            route_id="R-01",
            description="ทางหลวงสาย 1 (ปิดบางส่วนจากน้ำท่วม)",
        ),
        alternatives=[
            Route(
                route_id="R-02",
                description="ทางเลี่ยงผ่านถนนย่อย",
                estimated_time_minutes=45,
                trade_offs="ใช้เวลานานขึ้น 15 นาที แต่ปลอดภัยกว่า",
            )
        ],
        reasons=["ตรวจพบน้ำท่วมสูง 30 ซม. บนเส้นทางหลัก"],
        citations=[
            SourceCitation(source_name="กรมอุตุนิยมวิทยา", retrieved_at=NOW)
        ],
        evidence_status=[
            EvidenceStatus(
                evidence_id="EV-001",
                used_in_citation=True,
                check_result="VALID",
            ),
            EvidenceStatus(
                evidence_id="EV-002",
                used_in_citation=False,
                check_result="STALE",
                note="ประกาศปิดถนนเก่ากว่า 6 ชม. ไม่ได้ใช้อ้างอิง",
            ),
        ],
        observed_at=NOW,
        fetched_at=NOW,
        expires_at=NOW + timedelta(hours=1),
    )
    assert resp.confidence == ConfidenceLevel.HIGH
    assert len(resp.evidence_status) == 2  # เก็บครบ รวมชิ้นที่ไม่ได้ใช้อ้างอิง
    print("\n✅ CASE 1 ผ่าน:", resp.action_code.value)


# ============================================================
# CASE 2: เคส AVOID + escalation (fallback เวลาข้อมูลไม่ครบ/กำกวม)
#          risk สูง -> ต้องมี official_contacts
# ============================================================
def test_avoid_with_escalation_valid():
    resp = RecommendationResponse(
        request_id="req-002",
        schema_version="1.0.0",
        action_code=ActionCode.AVOID,
        backend_action_code="AVOID_TRAVEL",
        risk_level=RiskLevel.HIGH,
        confidence=ConfidenceLevel.LOW,  # ข้อมูลกำกวม -> confidence ต่ำ
        escalation=True,
        short_summary="ข้อมูลเส้นทางไม่ครบถ้วน ระบบแนะนำหลีกเลี่ยงเป็นการป้องกันไว้ก่อน",
        immediate_actions=["หลีกเลี่ยงเส้นทางนี้จนกว่าจะมีข้อมูลเพิ่มเติม"],
        emergency_instructions=["ติดต่อหน่วยงานท้องถิ่นก่อนเดินทาง"],
        official_contacts=[
            EmergencyContact(
                name="กรมป้องกันและบรรเทาสาธารณภัย",
                phone="1784",
                region="ภาคเหนือ",
                effective_date=NOW,
            )
        ],
        reasons=["หลักฐานบางส่วนหมดอายุ (stale) ไม่สามารถยืนยันความปลอดภัยได้"],
        evidence_status=[
            EvidenceStatus(
                evidence_id="EV-010",
                used_in_citation=False,
                check_result="STALE",
            )
        ],
        observed_at=NOW,
        fetched_at=NOW,
        expires_at=NOW + timedelta(minutes=30),
    )
    assert resp.escalation is True
    print("✅ CASE 2 ผ่าน:", resp.action_code.value, "| escalation:", resp.escalation)


# ============================================================
# CASE 3: เคสผิด - escalation=True + risk HIGH แต่ไม่มี official_contacts
#          (ต้อง raise error ตามสมมติฐาน safety ที่ตั้งไว้)
# ============================================================
def test_escalation_missing_contacts_fails():
    with pytest.raises(ValidationError) as exc_info:
        RecommendationResponse(
            request_id="req-003",
            schema_version="1.0.0",
            action_code=ActionCode.AVOID,
            risk_level=RiskLevel.HIGH,
            confidence=ConfidenceLevel.LOW,
            escalation=True,
            short_summary="สถานการณ์ไม่ชัดเจน",
            observed_at=NOW,
            fetched_at=NOW,
            expires_at=NOW + timedelta(minutes=30),
            # ❌ ไม่มี official_contacts -> ต้อง error
        )
    assert "official_contacts" in str(exc_info.value)
    print("✅ CASE 3 ผ่าน (จับ error ได้ถูกต้อง):", exc_info.value.error_count(), "errors")


# ============================================================
# CASE 4: เคสผิด - confidence ส่งเป็น float ตามร่างเก่า (ต้อง error เพราะ
#          schema เปลี่ยนเป็น ordinal enum แล้ว)
# ============================================================
def test_confidence_as_float_fails():
    with pytest.raises(ValidationError):
        RecommendationResponse(
            request_id="req-004",
            schema_version="1.0.0",
            action_code=ActionCode.NORMAL,
            risk_level=RiskLevel.LOW,
            confidence=0.9,  # ❌ ของเก่าใช้ float ของใหม่ต้องเป็น enum
            escalation=False,
            short_summary="เดินทางได้ตามปกติ",
            observed_at=NOW,
            fetched_at=NOW,
            expires_at=NOW + timedelta(hours=1),
        )
    print("✅ CASE 4 ผ่าน (จับ confidence แบบ float เก่าไม่ให้ผ่านได้)")


# ============================================================
# CASE 5: เคสผิด - expires_at น้อยกว่าหรือเท่ากับ fetched_at
# ============================================================
def test_expired_data_fails():
    with pytest.raises(ValidationError):
        RecommendationResponse(
            request_id="req-005",
            schema_version="1.0.0",
            action_code=ActionCode.NORMAL,
            risk_level=RiskLevel.LOW,
            confidence=ConfidenceLevel.HIGH,
            escalation=False,
            short_summary="ทดสอบข้อมูลหมดอายุ",
            observed_at=NOW,
            fetched_at=NOW,
            expires_at=NOW - timedelta(minutes=1),  # ❌ หมดอายุก่อน fetch
        )
    print("✅ CASE 5 ผ่าน (จับ expires_at ผิดได้)")


# ============================================================
# CASE 6: Feedback submission - UNSAFE ต้องมี comment
# ============================================================
def test_unsafe_feedback_needs_comment_fails():
    with pytest.raises(ValidationError):
        FeedbackSubmission(
            request_id="req-001",
            pseudonymous_user_id="user-hash-abc123",
            category=FeedbackCategory.UNSAFE,
            submitted_at=NOW,
            # ❌ ไม่มี comment -> ต้อง error
        )
    print("✅ CASE 6 ผ่าน (จับ UNSAFE ไม่มี comment ได้)")


def test_valid_feedback():
    fb = FeedbackSubmission(
        request_id="req-001",
        pseudonymous_user_id="user-hash-abc123",
        category=FeedbackCategory.UNSAFE,
        comment="เส้นทางที่แนะนำจริงๆ ปิดไปแล้ว 2 วัน",
        submitted_at=NOW,
    )
    assert fb.category == FeedbackCategory.UNSAFE
    print("✅ CASE 7 ผ่าน:", fb.category.value)


if __name__ == "__main__":
    # รันแบบไม่ใช้ pytest ก็ได้ เพื่อดูผลเร็วๆ
    test_change_route_valid()
    test_avoid_with_escalation_valid()
    test_escalation_missing_contacts_fails()
    test_confidence_as_float_fails()
    test_expired_data_fails()
    test_unsafe_feedback_needs_comment_fails()
    test_valid_feedback()
    print("\n🎉 ทุกเคสผ่านหมด!")