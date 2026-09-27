from types import SimpleNamespace
from unittest.mock import patch

import pytest
from openai import APITimeoutError

from app.llm_client import LLMUnavailableError, call_general_ai


def _fake_response(text: str, prompt_tokens: int, completion_tokens: int, finish_reason: str = "stop"):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=text),
                finish_reason=finish_reason,
            )
        ],
        usage=SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
    )

def test_primary_groq_success_no_fallback_called():
    with patch("app.llm_client._client") as mock_client_factory:
        mock_client = mock_client_factory.return_value
        mock_client.chat.completions.create.return_value = _fake_response("hi", 5, 5)

        content, model, usage = call_general_ai(
            messages=[{"role": "user", "content": "hello"}],
            max_tokens=100,
            request_id="r1",
        )

    assert content == "hi"
    assert usage == {"input": 5, "output": 5}
    # เรียก client แค่ครั้งเดียว (groq เท่านั้น) เพราะสำเร็จตั้งแต่ตัวแรก
    assert mock_client_factory.call_count == 1


def test_groq_timeout_falls_back_to_gemini():
    with patch("app.llm_client._client") as mock_client_factory:
        groq_client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(
                    create=lambda **kw: (_ for _ in ()).throw(
                        APITimeoutError(request=SimpleNamespace())
                    )
                )
            )
        )
        gemini_client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(
                    create=lambda **kw: _fake_response("fallback answer", 8, 12)
                )
            )
        )
        mock_client_factory.side_effect = [groq_client, gemini_client]

        content, model, usage = call_general_ai(
            messages=[{"role": "user", "content": "hello"}],
            max_tokens=100,
            request_id="r2",
        )

    assert content == "fallback answer"
    assert usage == {"input": 8, "output": 12}
    assert mock_client_factory.call_count == 2


def test_both_providers_fail_raises_llm_unavailable():
    with patch("app.llm_client._client") as mock_client_factory:
        broken = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(
                    create=lambda **kw: (_ for _ in ()).throw(
                        APITimeoutError(request=SimpleNamespace())
                    )
                )
            )
        )
        mock_client_factory.side_effect = [broken, broken]

        with pytest.raises(LLMUnavailableError):
            call_general_ai(
                messages=[{"role": "user", "content": "hello"}],
                max_tokens=100,
                request_id="r3",
            )

def test_groq_finish_reason_length_falls_back_to_gemini():
    """[ข้อ 2] Groq ตอบ content ว่าง + finish_reason='length' ต้อง fallback ไป Gemini ไม่ใช่ตอบ 200 เปล่า"""
    with patch("app.llm_client._client") as mock_client_factory:
        groq_client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(
                    create=lambda **kw: _fake_response("", 300, 350, finish_reason="length")
                )
            )
        )
        gemini_client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(
                    create=lambda **kw: _fake_response("คำตอบจาก Gemini", 8, 12)
                )
            )
        )
        mock_client_factory.side_effect = [groq_client, gemini_client]

        content, model, usage = call_general_ai(
            messages=[{"role": "user", "content": "hello"}],
            max_tokens=350,
            request_id="r4",
        )

    assert content == "คำตอบจาก Gemini"
    assert mock_client_factory.call_count == 2


def test_groq_empty_choices_falls_back_to_gemini():
    """[ข้อ 3] choices ว่างจาก Groq ต้องไม่โยน IndexError ออกไปถึง 500 แต่ fallback แทน"""
    with patch("app.llm_client._client") as mock_client_factory:
        broken_response = SimpleNamespace(choices=[], usage=None)
        groq_client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(create=lambda **kw: broken_response)
            )
        )
        gemini_client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(
                    create=lambda **kw: _fake_response("สำรอง", 8, 12)
                )
            )
        )
        mock_client_factory.side_effect = [groq_client, gemini_client]

        content, model, usage = call_general_ai(
            messages=[{"role": "user", "content": "hello"}],
            max_tokens=100,
            request_id="r5",
        )

    assert content == "สำรอง"
    assert mock_client_factory.call_count == 2


def test_client_created_with_max_retries_zero():
    """[ข้อ 1] ยืนยันว่า OpenAI client ถูกสร้างด้วย max_retries=0 จริง ไม่ใช้ default ของ SDK"""
    from app.llm_client import _client

    with patch("app.llm_client.OpenAI") as mock_openai_cls:
        _client("https://api.groq.com/openai/v1", "fake-key")

    _, kwargs = mock_openai_cls.call_args
    assert kwargs["max_retries"] == 0
