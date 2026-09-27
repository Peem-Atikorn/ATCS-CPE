"""
เรียก LLM ผ่านไลบรารี `openai` ตัวเดียว สลับเจ้าด้วย base_url (CONTRACT.md §8)
ลำดับ: Groq (หลัก) → error/429/timeout/response ผิดปกติ → Gemini (สำรอง) 1 ครั้ง → ล่มทั้งคู่ → LLMUnavailableError (ให้ router 503)
"""
import logging
import time

from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI, RateLimitError

from .config import settings

logger = logging.getLogger("engines")


class LLMUnavailableError(Exception):
    """ทั้ง Groq และ Gemini เรียกไม่สำเร็จ — main.py แปลงเป็น 503 LLM_UNAVAILABLE"""


class AnswerTooLongError(LLMUnavailableError):
    """
    [ข้อ 4] ทั้ง Groq และ Gemini เรียกสำเร็จ (provider ปกติดี) แต่ทุกครั้งตอบยาวเกิน max_tokens
    (finish_reason == "length") — สาเหตุคือ token budget ไม่พอ ไม่ใช่ provider ล่ม
    main.py ควรแยกเคสนี้ออกจาก LLM_UNAVAILABLE ทั่วไป เพราะข้อความ "ทั้ง Groq และ Gemini
    เรียกไม่สำเร็จ" ทำให้เข้าใจผิดว่า provider พัง ทั้งที่จริงคำถามแค่ต้องการคำตอบยาวกว่าที่ตั้งไว้
    ยังเป็น subclass ของ LLMUnavailableError อยู่ เพื่อให้ except LLMUnavailableError เดิมใน
    main.py ยังจับได้เหมือนเดิมโดยไม่ต้องแก้ทุกจุดที่เรียก — main.py แค่เช็ค isinstance เพิ่มถ้าอยากตอบ
    error message ที่ตรงสาเหตุกว่า
    """


class ProviderResponseInvalid(Exception):
    """
    Provider ตอบ 200 แต่ใช้งานไม่ได้จริง — เช่น content ว่าง, finish_reason == 'length'
    (โมเดล reasoning ใช้ token คิดหมดก่อนตอบ), หรือ choices ว่าง/ผิดรูป
    ถือว่าเป็นความล้มเหลวแบบเดียวกับ timeout/429 เพื่อให้ไป fallback ต่อ ไม่ใช่ตอบ 200 เปล่า ๆ

    [ข้อ 3+4] มี reason แยกกรณี "length" (ตัดกลางคันเพราะ max_tokens ไม่พอ — ไม่ใช่ provider
    พัง) ออกจาก "malformed" (response รูปแบบผิดจริง ๆ) เพื่อให้ call_general_ai รู้ว่าจะลอง
    ลด reasoning_effort ก่อน fallback ดีไหม และเพื่อให้ main.py ตอบ error ที่ตรงสาเหตุกว่าเดิม
    """

    def __init__(self, message: str, *, reason: str = "malformed"):
        super().__init__(message)
        self.reason = reason  # "length" | "malformed"


def _client(base_url: str, api_key: str) -> OpenAI:
    # [ข้อ 1] max_retries=0: ปิด retry อัตโนมัติของ SDK (ค่าเริ่มต้นคือ 2 ครั้ง + backoff)
    # เพราะ retry ในตัว client ทำให้ fallback ไป Gemini ช้าเกินงบ 25s ของ router
    # การ retry/fallback ทั้งหมดคุมเองที่ call_general_ai ชั้นเดียวพอ
    return OpenAI(base_url=base_url, api_key=api_key or "missing-key", max_retries=0)


def _try_provider(
    *,
    provider: str,
    base_url: str,
    api_key: str,
    model: str,
    timeout: float,
    messages: list[dict],
    max_tokens: int,
    request_id: str,
    reasoning_effort: str | None = None,
) -> tuple[str, str, dict]:
    """คืน (content, model, token_usage_dict) หรือ raise ให้ผู้เรียกไปลอง provider ถัดไป"""
    client = _client(base_url, api_key)

    # [ข้อ 3+4] reasoning_effort: ลดจำนวน token ที่โมเดล reasoning (เช่น gpt-oss-120b บน Groq)
    # ใช้ "คิด" ก่อนตอบ เพื่อเหลือ token ในงบ max_tokens ให้คำตอบจริงมากขึ้น โดยไม่ต้องขยับ
    # max_tokens/GENERAL_MAX_TOKENS เอง — SDK เวอร์ชันที่ pin ไว้ (openai==1.51.0) ยังไม่มี
    # พารามิเตอร์นี้ตรง ๆ จึงส่งผ่าน extra_body (Groq รับ "reasoning_effort" เป็นฟิลด์บน request
    # body ของโมเดลตระกูล gpt-oss) ถ้า provider ไม่รองรับฟิลด์นี้ (เช่น Gemini) จะถูกเมินเฉย ๆ
    # ไม่ error เพราะ Groq/Gemini เดินผ่าน endpoint แบบ OpenAI-compatible ที่ไม่เข้มงวดกับ unknown field
    extra_body = {"reasoning_effort": reasoning_effort} if reasoning_effort else None

    t0 = time.monotonic()
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        timeout=timeout,
        extra_body=extra_body,
    )
    ms = int((time.monotonic() - t0) * 1000)

    # [ข้อ 3] ครอบการอ่าน choices/message ด้วย try/except แทนที่จะปล่อยให้
    # IndexError/TypeError หลุดไปถึง handler กลาง (500 โดยไม่ได้ลอง Gemini)
    try:
        choice_obj = resp.choices[0]
        content = choice_obj.message.content
        finish_reason = choice_obj.finish_reason
    except (IndexError, TypeError, AttributeError) as e:
        raise ProviderResponseInvalid(
            f"{provider} ตอบรูปแบบผิดปกติ (choices ว่าง/ไม่มี message): {e}",
            reason="malformed",
        ) from e

    # [ข้อ 2] content ว่าง หรือ finish_reason == "length" (โมเดล reasoning ใช้ token
    # คิดหมดใน max_tokens ก่อนได้คำตอบ) ถือเป็นความล้มเหลว ไม่ใช่คำตอบสำเร็จที่ตอบ 200 ด้วย content=""
    if not content or finish_reason == "length":
        raise ProviderResponseInvalid(
            f"{provider} ตอบ content ว่างหรือถูกตัดกลางคัน (finish_reason={finish_reason})",
            reason="length" if finish_reason == "length" else "malformed",
        )

    usage = resp.usage
    token_usage = {
        "input": getattr(usage, "prompt_tokens", 0) or 0,
        "output": getattr(usage, "completion_tokens", 0) or 0,
    }
    logger.info(
        '{"event":"llm_call_ok","provider":"%s","model":"%s","ms":%d,"request_id":"%s"}',
        provider,
        model,
        ms,
        request_id,
    )
    return content, model, token_usage


def call_general_ai(
    *, messages: list[dict], max_tokens: int, request_id: str, reasoning_effort: str | None = None
) -> tuple[str, str, dict]:
    """
    ลอง Groq ก่อน ถ้า error / 429 / timeout / response ใช้งานไม่ได้ ค่อยลอง Gemini หนึ่งครั้ง
    ทั้งคู่ล่ม -> LLMUnavailableError (หรือ AnswerTooLongError ถ้าล่มเพราะ "length" ล้วน ๆ)

    reasoning_effort: ส่งต่อให้ทุก provider ที่ลองเรียก (ใช้ตอนที่รู้ล่วงหน้าว่าอยากได้คำตอบสั้น
    เช่น eval/llm_classifier.py ที่ต้องการแค่ JSON บรรทัดเดียว) ปล่อยเป็น None ตามปกติสำหรับ /general

    [ข้อ 4] ถ้า Groq ตอบครั้งแรกแล้วโดนตัดเพราะ "length" (ไม่ใช่ error/timeout จริง) จะลอง Groq
    ซ้ำอีกครั้งด้วย reasoning_effort="low" ก่อน ค่อย fallback ไป Gemini — ลดโอกาสเจอ 503 ปลอม ๆ
    ที่เกิดจาก token budget ไม่พอ โดยไม่ต้องขยับ GENERAL_MAX_TOKENS เอง (ข้ามขั้นนี้ถ้าผู้เรียก
    ตั้ง reasoning_effort มาเองอยู่แล้ว เพื่อไม่ให้ลองซ้ำด้วยค่าเดิม)
    """
    retryable = (
        APITimeoutError,
        RateLimitError,
        APIConnectionError,
        APIStatusError,
        ProviderResponseInvalid,  # [ข้อ 2+3] รวม response ผิดปกติเข้ากลุ่มที่ trigger fallback ด้วย
    )

    def _reason(err: Exception) -> str | None:
        return getattr(err, "reason", None)

    try:
        return _try_provider(
            provider="groq",
            base_url=settings.GROQ_BASE_URL,
            api_key=settings.GROQ_API_KEY,
            model=settings.GROQ_MODEL,
            timeout=settings.PRIMARY_TIMEOUT_SECONDS,
            messages=messages,
            max_tokens=max_tokens,
            request_id=request_id,
            reasoning_effort=reasoning_effort,
        )
    except retryable as primary_err:
        logger.warning(
            '{"event":"llm_call_fallback","provider":"groq","error":"%s","request_id":"%s"}',
            str(primary_err),
            request_id,
        )

        # [ข้อ 4] เจอ length ตั้งแต่ครั้งแรกและยังไม่เคยลด reasoning_effort มาก่อน -> ลอง Groq
        # อีกรอบแบบ "คิดน้อยลง" ก่อนจะเสียเวลาไป Gemini
        if _reason(primary_err) == "length" and reasoning_effort is None:
            try:
                return _try_provider(
                    provider="groq",
                    base_url=settings.GROQ_BASE_URL,
                    api_key=settings.GROQ_API_KEY,
                    model=settings.GROQ_MODEL,
                    timeout=settings.PRIMARY_TIMEOUT_SECONDS,
                    messages=messages,
                    max_tokens=max_tokens,
                    request_id=request_id,
                    reasoning_effort="low",
                )
            except retryable as retry_err:
                logger.warning(
                    '{"event":"llm_call_fallback","provider":"groq_low_effort",'
                    '"error":"%s","request_id":"%s"}',
                    str(retry_err),
                    request_id,
                )
                primary_err = retry_err  # ใช้ตัวหลังสุดตัดสิน reason ตอนสร้าง error รวมท้ายสุด

        try:
            return _try_provider(
                provider="gemini",
                base_url=settings.GEMINI_BASE_URL,
                api_key=settings.GEMINI_API_KEY,
                model=settings.GEMINI_MODEL,
                timeout=settings.FALLBACK_TIMEOUT_SECONDS,
                messages=messages,
                max_tokens=max_tokens,
                request_id=request_id,
                reasoning_effort=reasoning_effort,
            )
        except retryable as fallback_err:
            logger.error(
                '{"event":"llm_call_failed","provider":"gemini","error":"%s","request_id":"%s"}',
                str(fallback_err),
                request_id,
            )
            combined_msg = f"groq: {primary_err} | gemini: {fallback_err}"
            # [ข้อ 4] ทั้งสองรอบล่มเพราะ "length" ล้วน ๆ (ไม่ใช่ provider พัง) -> แยก error type
            # ให้ main.py ตอบสาเหตุที่ตรงกว่าเดิมได้ ไม่ปนกับ LLM_UNAVAILABLE ทั่วไป
            if _reason(primary_err) == "length" and _reason(fallback_err) == "length":
                raise AnswerTooLongError(combined_msg) from fallback_err
            raise LLMUnavailableError(combined_msg) from fallback_err