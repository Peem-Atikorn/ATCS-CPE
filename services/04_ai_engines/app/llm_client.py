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


class ProviderResponseInvalid(Exception):
    """
    Provider ตอบ 200 แต่ใช้งานไม่ได้จริง — เช่น content ว่าง, finish_reason == 'length'
    (โมเดล reasoning ใช้ token คิดหมดก่อนตอบ), หรือ choices ว่าง/ผิดรูป
    ถือว่าเป็นความล้มเหลวแบบเดียวกับ timeout/429 เพื่อให้ไป fallback ต่อ ไม่ใช่ตอบ 200 เปล่า ๆ
    """


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
) -> tuple[str, str, dict]:
    """คืน (content, model, token_usage_dict) หรือ raise ให้ผู้เรียกไปลอง provider ถัดไป"""
    client = _client(base_url, api_key)
    t0 = time.monotonic()
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        timeout=timeout,
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
            f"{provider} ตอบรูปแบบผิดปกติ (choices ว่าง/ไม่มี message): {e}"
        ) from e

    # [ข้อ 2] content ว่าง หรือ finish_reason == "length" (โมเดล reasoning ใช้ token
    # คิดหมดใน max_tokens ก่อนได้คำตอบ) ถือเป็นความล้มเหลว ไม่ใช่คำตอบสำเร็จที่ตอบ 200 ด้วย content=""
    if not content or finish_reason == "length":
        raise ProviderResponseInvalid(
            f"{provider} ตอบ content ว่างหรือถูกตัดกลางคัน (finish_reason={finish_reason})"
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
    *, messages: list[dict], max_tokens: int, request_id: str
) -> tuple[str, str, dict]:
    """
    ลอง Groq ก่อน ถ้า error / 429 / timeout / response ใช้งานไม่ได้ ค่อยลอง Gemini หนึ่งครั้ง
    ทั้งคู่ล่ม -> LLMUnavailableError
    """
    retryable = (
        APITimeoutError,
        RateLimitError,
        APIConnectionError,
        APIStatusError,
        ProviderResponseInvalid,  # [ข้อ 2+3] รวม response ผิดปกติเข้ากลุ่มที่ trigger fallback ด้วย
    )

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
        )
    except retryable as primary_err:
        logger.warning(
            '{"event":"llm_call_fallback","provider":"groq","error":"%s","request_id":"%s"}',
            str(primary_err),
            request_id,
        )
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
            )
        except retryable as fallback_err:
            logger.error(
                '{"event":"llm_call_failed","provider":"gemini","error":"%s","request_id":"%s"}',
                str(fallback_err),
                request_id,
            )
            raise LLMUnavailableError(
                f"groq: {primary_err} | gemini: {fallback_err}"
            ) from fallback_err